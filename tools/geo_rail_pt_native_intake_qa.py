#!/usr/bin/env python3
"""MN-GEO-RAIL-001 W2: validate ONE user-authorized native DGT CDD MDT GeoTIFF.

Run only after the registered user has downloaded a DGT file through the
official site (or authorized QGIS plugin). No credentials, cookies, URLs or
raw pixels go to the safe receipt; raster remains at its user-owned location.
The public STAC index is *discovery metadata*, not validated raster coverage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

MAX_NATIVE_BYTES = 350_000_000
MAX_RASTER_CELLS = 125_000_000
MAX_ACCEPTABLE_BBOX_DEVIATION_DEGREES = 0.03
APPROVED_COLLECTIONS = {"MDT-2m": 2.0, "MDT-50cm": 0.5}


def catalogue_record(index, collection, tile_id):
    if index.get("type") != "FeatureCollection":
        raise ValueError("unexpected source index type")
    features=index.get("features")
    if not isinstance(features,list):
        raise ValueError("invalid source index")
    matching=[f for f in features if isinstance(f,dict)
              and f.get("properties",{}).get("source_collection")==collection
              and f.get("properties",{}).get("producer_tile_id")==tile_id]
    if len(matching)!=1:
        raise ValueError("DGT tile ID not found exactly once in reviewed public STAC discovery")
    props=matching[0]["properties"]
    if props.get("geometry_is_bbox_proxy_not_original_footprint") is not True:
        raise ValueError("unexpected source index geometry contract")
    coords=matching[0].get("geometry",{}).get("coordinates",[])
    points=coords[0] if coords and isinstance(coords[0],list) else []
    if len(points)!=5 or points[0]!=points[-1]:
        raise ValueError("invalid expected source bbox proxy")
    b=[min(v[0] for v in points),min(v[1] for v in points),
       max(v[0] for v in points),max(v[1] for v in points)]
    if not (-11<=b[0]<b[2]<=-5 and 36<=b[1]<b[3]<=43):
        raise ValueError("source geometry outside Portugal WGS84")
    return {"bbox_wgs84":b,"bbox_method":props["bbox_method"],
            "source_window_ids":props.get("query_window_ids",[])}


def stream_sha256(path, max_bytes=MAX_NATIVE_BYTES):
    size=path.stat().st_size
    if size<=0 or size>max_bytes:
        raise ValueError("native data file is empty or exceeds 350MB pilot cap")
    digest=hashlib.sha256()
    count=0
    with path.open("rb") as fd:
        while True:
            block=fd.read(2**20)
            if not block: break
            count+=len(block)
            if count>max_bytes:
                raise ValueError("file grew beyond permitted pilot cap")
            digest.update(block)
    if count!=size:
        raise ValueError("file size changed during hash")
    return count,digest.hexdigest()


def raster_quality(path, resolution, expected_bbox):
    import rasterio
    import numpy as np
    from rasterio.warp import transform_bounds

    with rasterio.open(path) as ds:
        if ds.driver!="GTiff" or ds.count!=1:
            raise ValueError("expected one-band native DGT GeoTIFF")
        if ds.crs is None or ds.crs.to_epsg()!=3763:
            raise ValueError(f"unexpected DGT source horizontal CRS: {ds.crs}")
        if ds.width*ds.height > MAX_RASTER_CELLS or ds.width<1 or ds.height<1:
            raise ValueError("unexpected DGT raster cell count")
        px,py=abs(ds.transform.a),abs(ds.transform.e)
        if not (math.isclose(px,resolution,abs_tol=0.01) and
                math.isclose(py,resolution,abs_tol=0.01)):
            raise ValueError("DGT native raster does not match collection resolution")
        if not all(math.isfinite(z) for z in ds.bounds):
            raise ValueError("native raster bounds are not finite")
        geographic=list(transform_bounds(ds.crs,"EPSG:4326",*ds.bounds,densify_pts=21))
        if not (-11<=geographic[0]<geographic[2]<=-5 and
                36<=geographic[1]<geographic[3]<=43):
            raise ValueError("native raster bounds outside Portugal")
        # The STAC index contains only bbox proxies and some source bboxes are wrong;
        # use overlap, not exact equality or an invented footprint guarantee.
        intersection_w=max(0,min(geographic[2],expected_bbox[2])-
                           max(geographic[0],expected_bbox[0]))
        intersection_h=max(0,min(geographic[3],expected_bbox[3])-
                           max(geographic[1],expected_bbox[1]))
        if intersection_w==0 or intersection_h==0:
            raise ValueError("GeoTIFF does not overlap registered STAC item bbox")
        n_valid=0
        n_masked=0
        elevation_min=float("inf")
        elevation_max=-float("inf")
        elevation_sum=0.0
        for _,window in ds.block_windows(1):
            values=ds.read(1,window=window,masked=True)
            mask=np.ma.getmaskarray(values)
            good=np.asarray(values.data)[~mask]
            finite=np.isfinite(good)
            if not finite.all():
                raise ValueError("non-finite valid elevation values")
            n_valid+=len(good)
            n_masked+=int(mask.sum())
            if len(good)>0:
                elevation_min=min(elevation_min,float(np.min(good)))
                elevation_max=max(elevation_max,float(np.max(good)))
                elevation_sum+=float(np.sum(good,dtype="float64"))
        if n_valid==0:
            raise ValueError("raster contains no valid elevations")
        if n_valid+n_masked != ds.width*ds.height:
            raise ValueError("pixel and mask counts do not add up")
        return {
            "driver":ds.driver,
            "horizontal_crs":str(ds.crs),
            "vertical_crs_in_raster_confirmed":False,
            "vertical_crs_from_DGT_source_documentation":"Datum Altimétrico de Cascais",
            "resolution_m":[px,py],
            "width_px":ds.width,"height_px":ds.height,
            "count":ds.count,"dtype":ds.dtypes[0],
            "nodata_value":ds.nodata,
            "bounds_pttm06":[float(x) for x in ds.bounds],
            "bounds_wgs84":[float(x) for x in geographic],
            "source_bbox_proxy_wgs84":expected_bbox,
            "bbox_intersects_source_proxy":True,
            "valid_pixels":n_valid,
            "masked_pixels":n_masked,
            "valid_pixel_fraction":round(n_valid/(n_valid+n_masked),7),
            "min_elevation_raw_m":elevation_min,
            "max_elevation_raw_m":elevation_max,
            "mean_elevation_raw_m":elevation_sum/n_valid,
            "no_external_vertical_benchmark_test":True,
        }


def audit(path, index_path, tile_id, collection):
    if collection not in APPROVED_COLLECTIONS:
        raise ValueError("only DGT MDT-2m and MDT-50cm are allowed")
    if not (isinstance(tile_id,str) and 1<=len(tile_id)<=160
            and tile_id.startswith(collection+"-")
            and all(ch.isalnum() or ch in "-_" for ch in tile_id)):
        raise ValueError("invalid STAC DGT producer item identifier")
    if not path.is_file() or path.is_symlink():
        raise ValueError("pilot expects an ordinary local downloaded file")
    record=catalogue_record(json.loads(index_path.read_text(encoding="utf-8")),
                            collection,tile_id)
    length,digest=stream_sha256(path)
    q=raster_quality(path,APPROVED_COLLECTIONS[collection],record["bbox_wgs84"])
    return {
        "mission":"MN-GEO-RAIL-001","worker":"W2",
        "stage":"pt_dgt_native_mdt_registered_user_intake_pilot",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "producer":"Direção-Geral do Território",
        "source_portal":"https://cdd.dgterritorio.gov.pt/",
        "download_method":"registered_user_manual_official_CDD_OR_authorized_tool",
        "registered_access_user_confirmed_not_programmatically_verified":True,
        "original_raster_filename_not_recorded":True,
        "original_native_asset_url_not_recorded":True,
        "credentials_or_session_material_in_receipt":False,
        "native_raster_committed_to_git":False,
        "native_raster_uploaded_publicly":False,
        "collection":collection,"producer_tile_id":tile_id,
        "native_file_bytes":length,"native_sha256":digest,
        "source_stac_bbox_method":record["bbox_method"],
        "source_STAC_windows":record["source_window_ids"],
        "raster":q,
        "source_license":"DGT Centro de Dados, CC BY 4.0 attribution required",
        "individual_asset_use_rights_rechecked":False,
        "crossborder_vertical_harmonization_done":False,
        "canonical_Fxx_accepted":False,
        "site_publication_authorized":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--native",type=Path,required=True,
                   help="user-authorized local GeoTIFF; never committed")
    p.add_argument("--collection",choices=sorted(APPROVED_COLLECTIONS),required=True)
    p.add_argument("--tile-id",required=True)
    p.add_argument("--index",type=Path,required=True,
                   help="pre-acceptance W2 DGT public candidate GeoJSON")
    p.add_argument("--receipt",type=Path,required=True,
                   help="safe JSON; no paths, credentials or pixels")
    a=p.parse_args()
    result=audit(a.native,a.index,a.tile_id,a.collection)
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
                         encoding="utf-8")
    print(json.dumps({"state":"native_MDT_sample_QA_passed",
                      "collection":a.collection,
                      "tile_id":a.tile_id,
                      "sha256":result["native_sha256"],
                      "valid_pixels":result["raster"]["valid_pixels"],
                      "masked_pixels":result["raster"]["masked_pixels"],
                      "canonical_accepted":False},ensure_ascii=False))


if __name__=="__main__":
    main()
