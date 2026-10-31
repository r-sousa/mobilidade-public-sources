#!/usr/bin/env python3
"""W2: protected two-tile DGT Mirandela native MDT seam pilot.

Manually dispatched ONLY on protected public main with the dgt-cdd Environment.
Downloads two exact previously indexed MDT-2m producer IDs, checks native
GeoTIFFs and one shared 1km seam, retains ONLY a sanitized JSON receipt.
Native data files and credentials leave neither temporary runner nor DGT's
secured session. No automatic Release publication or canonical Fxx acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from geo_rail_pt_native_intake_qa import audit, catalogue_record
from geo_rail_pt_cdd_authenticated import (
    authenticated_session, request_bounded_redirects, read_metadata,
    native_response_from_dgt_with_single_storage_hop, allowed_url,
    TRUSTED_AUTH_REDIRECTS, TRUSTED_DATA_REDIRECTS, STAC, COLLECTION,
    IntakeError
)

NORTH_TILE="MDT-2m-282510-09-2024"
SOUTH_TILE="MDT-2m-282509-09-2024"
ITEMS=(NORTH_TILE,SOUTH_TILE)
SEARCH_BBOX=[-7.25,41.45,-7.13,41.56]
MAX_TILE_BYTES=25_000_000
MAX_AGGREGATE_BYTES=50_000_000

def select_exact_assets(session):
    response=request_bounded_redirects(
        session,"POST",STAC,TRUSTED_AUTH_REDIRECTS,
        json_body={"bbox":SEARCH_BBOX,"collections":[COLLECTION],"limit":500},
        stream=True,phase="protected_dgt_pair_stac")
    features,receipt_hash=read_metadata(response)
    if features.get("type")!="FeatureCollection":
        raise IntakeError("unexpected_STAC_feature_collection")
    rows=features.get("features")
    if not isinstance(rows,list) or len(rows)>500 or any(
        isinstance(x,dict) and x.get("rel")=="next"
        for x in features.get("links",[]) if isinstance(x,dict)
    ):
        raise IntakeError("incomplete_reviewed_STAC")
    safe_assets={}
    for tile in ITEMS:
        found=[r for r in rows if isinstance(r,dict) and r.get("id")==tile and r.get("collection")==COLLECTION]
        if len(found)!=1:
            raise IntakeError("missing_exact_reviewed_native_tile")
        assets=found[0].get("assets")
        item=assets.get("data") if isinstance(assets,dict) else None
        if not isinstance(item,dict) or not str(item.get("type","")).lower().startswith(("image/tiff","image/geotiff")):
            raise IntakeError("unexpected_native_media_type")
        href=item.get("href")
        if not allowed_url(href,TRUSTED_DATA_REDIRECTS):
            raise IntakeError("disallowed_native_asset_url")
        safe_assets[tile]=href
    return safe_assets,receipt_hash

def download_small_native(session,href,target):
    response,storage=native_response_from_dgt_with_single_storage_hop(session,href)
    digest=hashlib.sha256()
    n=0
    try:
        if response.status_code!=200:
            raise IntakeError("native_response_not_200")
        ctype=(response.headers.get("Content-Type") or "").lower()
        if any(x in ctype for x in ("html","xml","json")):
            raise IntakeError("native_response_is_not_raster")
        length=response.headers.get("Content-Length")
        if length and length.isdigit() and int(length)>MAX_TILE_BYTES:
            raise IntakeError("pilot_tile_exceeds_25MB_limit")
        with target.open("xb") as out:
            for piece in response.iter_content(chunk_size=262144):
                if not piece:continue
                n+=len(piece)
                if n>MAX_TILE_BYTES: raise IntakeError("pilot_tile_exceeds_25MB_limit")
                out.write(piece);digest.update(piece)
        if n<1024: raise IntakeError("native_tiff_unexpectedly_small")
        with target.open("rb") as fh:
            if fh.read(4) not in (b"II*\x00",b"MM\x00*",b"II+\x00",b"MM\x00+"):
                raise IntakeError("native_response_not_tiff")
        return n,digest.hexdigest()
    finally:
        response.close()
        if storage is not None: storage.close()

def pair_geometry(north,south):
    a=north["raster"];b=south["raster"]
    if a["horizontal_crs"]!="EPSG:3763" or b["horizontal_crs"]!="EPSG:3763":
        raise ValueError("pair_not_in_PT_TM06")
    if a["resolution_m"]!=[2.0,2.0] or b["resolution_m"]!=[2.0,2.0]:
        raise ValueError("pair_not_2m")
    if any(z["width_px"]!=500 or z["height_px"]!=500 for z in (a,b)):
        raise ValueError("pair_unexpected_1km_shape")
    na=list(a["bounds_pttm06"]);sb=list(b["bounds_pttm06"])
    if not all(math.isclose(na[i],v,abs_tol=.01) for i,v in enumerate([82000,209000,83000,210000])):
        raise ValueError("north_raster_extent_not_verified")
    if not all(math.isclose(sb[i],v,abs_tol=.01) for i,v in enumerate([82000,208000,83000,209000])):
        raise ValueError("south_raster_not_exact_adjacent")
    return {"north_bbox_pttm06":na,"south_bbox_pttm06":sb,
            "shared_boundary_y_m":209000,
            "adjacent_1km_tiles_confirmed":True,
            "combined_sample_area_km2":2}

def seam_report(north_path,south_path):
    import numpy as np
    import rasterio
    with rasterio.open(north_path) as north, rasterio.open(south_path) as south:
        upper=north.read(1,window=((north.height-1,north.height),(0,north.width)),masked=True).ravel()
        lower=south.read(1,window=((0,1),(0,south.width)),masked=True).ravel()
        both_valid=~np.ma.getmaskarray(upper)&~np.ma.getmaskarray(lower)
        valid=int(both_valid.sum())
        delta=lower.data[both_valid].astype("float64")-upper.data[both_valid].astype("float64")
        if not np.isfinite(delta).all():
            raise ValueError("non_finite_native_seam")
        return {
            "edge_pairs_total":int(upper.size),
            "edge_pairs_both_valid":valid,
            "edge_pairs_incomplete":int(upper.size-valid),
            "edge_mask_continuity_all_valid":valid==int(upper.size),
            "median_abs_neighbor_cell_elevation_difference_m":float(np.median(np.abs(delta))) if valid else None,
            "max_abs_neighbor_cell_elevation_difference_m":float(np.max(np.abs(delta))) if valid else None,
            "mean_signed_south_minus_north_neighbor_cell_difference_m":float(np.mean(delta)) if valid else None,
            "different_terrain_cell_elevations_not_required_to_be_equal":True,
            "vertical_datum_independently_verified":False,
        }

def run(index, progress=None):
    """Execute with non-sensitive phase-only progress for safe error receipts."""
    def phase(label):
        if progress is not None:
            progress["safe_phase"] = label

    phase("reviewed_STAC_index")
    if not index.is_file() or index.is_symlink():
        raise IntakeError("reviewed_STAC_index_missing")
    source_index=json.loads(index.read_text(encoding="utf-8"))
    for tile in ITEMS:
        catalogue_record(source_index,COLLECTION,tile)
    phase("credentials_presence")
    username=os.environ.get("DGT_CDD_USERNAME","")
    password=os.environ.get("DGT_CDD_PASSWORD","")
    if not username or not password:
        raise IntakeError("environment_credentials_unavailable")
    with TemporaryDirectory(prefix="mn-dgt-pair-") as temp:
        folder=Path(temp)
        phase("protected_CDD_authentication")
        session=authenticated_session(username,password)
        try:
            phase("exact_STAC_assets")
            assets,stac_sha=select_exact_assets(session)
            native={}
            for tile in ITEMS:
                file=folder/("north.tif" if tile==NORTH_TILE else "south.tif")
                phase("native_download_north" if tile==NORTH_TILE else "native_download_south")
                size,digest=download_small_native(session,assets[tile],file)
                native[tile]=(file,size,digest)
            if sum(v[1] for v in native.values())>MAX_AGGREGATE_BYTES:
                raise IntakeError("pair_exceeds_aggregate_budget")
        finally:
            session.close()
        receipts=[]
        for tile in ITEMS:
            file,size,digest=native[tile]
            phase("native_QA_north" if tile==NORTH_TILE else "native_QA_south")
            qa=audit(file,index,tile,COLLECTION)
            if qa["native_file_bytes"]!=size or qa["native_sha256"]!=digest:
                raise IntakeError("pair_native_digest_disagrees_with_QA")
            receipts.append(qa)
        phase("exact_pair_geometry")
        geometry=pair_geometry(receipts[0],receipts[1])
        phase("native_seam_pixels")
        seam=seam_report(native[NORTH_TILE][0],native[SOUTH_TILE][0])
        if not seam["edge_mask_continuity_all_valid"]:
            raise IntakeError("native_seam_contains_masked_cells")
        phase("validated")
        return {
            "mission":"MN-GEO-RAIL-001","stage":"W2_DGT_native_two_tile_seam_2km2",
            "status":"two_native_GeoTIFFs_authenticated_QA_and_seam_validated",
            "producer":"Direção-Geral do Território",
            "collection":COLLECTION,
            "source_stac_response_sha256":stac_sha,
            "source_tile_ids":list(ITEMS),
            "tile_receipts":receipts,
            "native_pair_geometry":geometry,
            "native_pair_seam_qa":seam,
            "secrets_session_native_urls_saved":False,
            "native_bytes_persisted_after_runner":False,
            "source_rasters_newly_published":0,
            "crossborder_vertical_harmonized":False,
            "continuity_outside_2km2":False,
            "canonical_Fxx_accepted":False,
            "site_publication_authorized":False,
        }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index",required=True,type=Path)
    p.add_argument("--receipt",required=True,type=Path)
    args=p.parse_args()
    result={
        "mission":"MN-GEO-RAIL-001",
        "stage":"W2_DGT_native_two_tile_seam_2km2",
        "status":"not_validated",
        "source_tile_ids":list(ITEMS),
        "canonical_Fxx_accepted":False,
        "site_publication_authorized":False,
        "native_bytes_persisted_after_runner":False,
        "observed_utc":datetime.now(timezone.utc).isoformat(),
    }
    progress={"safe_phase":"not_started"}
    try:
        result=run(args.index,progress)
        result["observed_utc"]=datetime.now(timezone.utc).isoformat()
    except IntakeError as err:
        result["safe_error_code"]=err.code
        result["safe_failure_phase"]=progress["safe_phase"]
    except Exception:
        result["safe_failure_phase"]=progress["safe_phase"]
        result["safe_error_code"]="internal_or_raster_QA_error_no_sensitive_details"
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
                      "tiles":result["source_tile_ids"],
                      "error":result.get("safe_error_code")},ensure_ascii=False))
    if result["status"]!="two_native_GeoTIFFs_authenticated_QA_and_seam_validated":
        raise SystemExit("pair_not_validated")

if __name__=="__main__":
    main()
