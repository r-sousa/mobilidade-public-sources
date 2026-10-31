#!/usr/bin/env python3
"""W2: protected, reviewed 3 x 4 Mirandela DGT MDT-2m raster grid pilot.

Acquires only twelve previously indexed official 1km² tile IDs, verifies
each source-native raster and all seventeen grid joins in EPSG:3763.
Requires main-protected workflow_dispatch and dgt-cdd Environment secrets.
Native rasters stay temporary; only safe SHA-256 and QA receipts persist.
No raster release, canonical acceptance or rail-route analysis.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from geo_rail_pt_native_intake_qa import audit, catalogue_record
from geo_rail_pt_cdd_authenticated import (
    authenticated_session, request_bounded_redirects, read_metadata,
    allowed_url, TRUSTED_AUTH_REDIRECTS, TRUSTED_DATA_REDIRECTS, STAC,
    COLLECTION, IntakeError
)
from geo_rail_pt_cdd_pair_pilot import download_small_native

COLS=(280,281,282) # approved original source index candidates only
ROWS=(507,508,509,510)
GRID_TILES=tuple((c,r,f"MDT-2m-{c}{r}-09-2024") for r in ROWS for c in COLS)
SEARCH_BBOX=[-7.25,41.45,-7.13,41.56]
MAX_TOTAL_NATIVE_BYTES=60_000_000
SAMPLE_PROVENANCE_NOTE=("Producers' STAC bbox proxies and source tile IDs are "
                       "reviewed discovery evidence, not ground-truth rasters.")

def expected_bbox(col,row):
    if col not in COLS or row not in ROWS:
        raise ValueError("unapproved_source_grid_index")
    west=(col-200)*1000
    south=(row-301)*1000
    return [west,south,west+1000,south+1000]

def reviewed_grid_index(index):
    if not index.is_file() or index.is_symlink():
        raise IntakeError("reviewed_grid_STAC_index_missing")
    doc=json.loads(index.read_text(encoding="utf-8"))
    for _,_,tile in GRID_TILES:
        catalogue_record(doc,COLLECTION,tile)
    return doc

def select_exact_assets(session):
    response=request_bounded_redirects(
        session,"POST",STAC,TRUSTED_AUTH_REDIRECTS,
        json_body={"bbox":SEARCH_BBOX,"collections":[COLLECTION],"limit":500},
        stream=True,phase="protected_dgt_grid12_stac")
    data,response_sha=read_metadata(response)
    rows=data.get("features")
    if data.get("type")!="FeatureCollection" or not isinstance(rows,list) or len(rows)>500:
        raise IntakeError("invalid_or_unbounded_STAC_grid_response")
    if any(isinstance(link,dict) and link.get("rel")=="next"
           for link in data.get("links",[]) if isinstance(link,dict)):
        raise IntakeError("incomplete_paginated_grid_STAC")
    result={}
    for _,_,tile in GRID_TILES:
        found=[x for x in rows if isinstance(x,dict) and
               x.get("collection")==COLLECTION and x.get("id")==tile]
        if len(found)!=1:
            raise IntakeError("one_or_more_approved_grid_tiles_missing")
        a=found[0].get("assets")
        item=a.get("data") if isinstance(a,dict) else None
        if not isinstance(item,dict) or not str(item.get("type","")).lower().startswith(
                ("image/tiff","image/geotiff")):
            raise IntakeError("unexpected_DGT_grid_asset_type")
        href=item.get("href")
        if not allowed_url(href,TRUSTED_DATA_REDIRECTS):
            raise IntakeError("unapproved_DGT_grid_asset_href")
        result[tile]=href
    return result,response_sha

def validate_native_grid_geometry(per_tile):
    if set(per_tile)!={tile for _,_,tile in GRID_TILES}:
        raise ValueError("incomplete_DGT_grid")
    for col,row,tile in GRID_TILES:
        rec=per_tile[tile]
        raster=rec["raster"]
        got=raster["bounds_pttm06"]
        expected=expected_bbox(col,row)
        if raster["horizontal_crs"]!="EPSG:3763" or raster["resolution_m"]!=[2.0,2.0]:
            raise ValueError("DGT_grid_raster_CRS_or_pixel_size_mismatch")
        if raster["width_px"]!=500 or raster["height_px"]!=500:
            raise ValueError("DGT_grid_raster_dimensions_mismatch")
        if any(abs(float(a)-b)>0.001 for a,b in zip(got,expected)):
            raise ValueError("DGT_grid_raster_bounds_not_exact_PTTM06")
        if raster["valid_pixels"]!=250000 or raster["masked_pixels"]!=0:
            raise ValueError("DGT_grid_native_pixels_incomplete")
    return True

def compare_shared_edges(west_or_north_path,east_or_south_path,orientation):
    """Compare NEIGHBORING real cells; height equality is not required."""
    import numpy as np
    import rasterio
    with rasterio.open(west_or_north_path) as a,rasterio.open(east_or_south_path) as b:
        if orientation=="west_east":
            left=a.read(1,window=((0,a.height),(a.width-1,a.width)),masked=True).ravel()
            right=b.read(1,window=((0,b.height),(0,1)),masked=True).ravel()
        elif orientation=="north_south":
            left=a.read(1,window=((a.height-1,a.height),(0,a.width)),masked=True).ravel()
            right=b.read(1,window=((0,1),(0,b.width)),masked=True).ravel()
        else:
            raise ValueError("invalid_native_grid_pair_orientation")
    if left.shape!=right.shape or left.size!=500:
        raise ValueError("native_DGT_grid_seam_not_500_cell_pairs")
    joint=~np.ma.getmaskarray(left)&~np.ma.getmaskarray(right)
    count=int(joint.sum())
    if count!=500:
        raise ValueError("incomplete_or_masked_native_DGT_grid_join")
    delta=right.data[joint].astype("float64")-left.data[joint].astype("float64")
    if not bool(np.isfinite(delta).all()):
        raise ValueError("nonfinite_native_DGT_grid_join")
    return {"orientation":orientation,"pairs_total":500,"pairs_valid":count,
            "median_abs_neighbor_diff_m":float(np.median(np.abs(delta))),
            "max_abs_neighbor_diff_m":float(np.max(np.abs(delta))),
            "signed_mean_second_minus_first_neighbor_diff_m":float(np.mean(delta)),
            "same_point_vertical_accuracy_comparison":False}

def evaluate_seams(paths):
    seams=[]
    for row in ROWS:
        for i in range(len(COLS)-1):
            col,nextcol=COLS[i:i+2]
            a=f"MDT-2m-{col}{row}-09-2024"
            b=f"MDT-2m-{nextcol}{row}-09-2024"
            seams.append({"first_tile":a,"second_tile":b,
                          **compare_shared_edges(paths[a],paths[b],"west_east")})
    for col in COLS:
        for i in range(len(ROWS)-1):
            southrow,northrow=ROWS[i:i+2]
            a=f"MDT-2m-{col}{northrow}-09-2024"
            b=f"MDT-2m-{col}{southrow}-09-2024"
            seams.append({"first_tile":a,"second_tile":b,
                          **compare_shared_edges(paths[a],paths[b],"north_south")})
    if len(seams)!=17 or any(x["pairs_valid"]!=500 for x in seams):
        raise ValueError("expected_seventeen_complete_DGT_grid_joins")
    return seams

def run(index,progress=None):
    def phase(x):
        if progress is not None:
            progress["safe_phase"]=x
    phase("reviewed_grid_index")
    reviewed_grid_index(index)
    phase("credentials_presence")
    user=os.environ.get("DGT_CDD_USERNAME","")
    pwd=os.environ.get("DGT_CDD_PASSWORD","")
    if not user or not pwd:
        raise IntakeError("environment_credentials_unavailable")
    with TemporaryDirectory(prefix="mn-dgt-grid12-") as d:
        temp=Path(d)
        phase("protected_CDD_login")
        session=authenticated_session(user,pwd)
        try:
            phase("exact_grid_STAC_native_assets")
            assets,stac_sha=select_exact_assets(session)
            all_paths={}
            total=0
            downloaded={}
            for col,row,tile in GRID_TILES:
                phase("native_tile_download_grid_step_"+str(len(downloaded)+1))
                path=temp/f"grid_{col}_{row}.tif"
                size,sha=download_small_native(session,assets[tile],path)
                total+=size
                if total>MAX_TOTAL_NATIVE_BYTES:
                    raise IntakeError("total_native_grid_60MB_cap_exceeded")
                all_paths[tile]=path
                downloaded[tile]=(size,sha)
        finally:
            session.close()
        per_tile={}
        for col,row,tile in GRID_TILES:
            phase("native_tile_QA_grid_step_"+str(len(per_tile)+1))
            qa=audit(all_paths[tile],index,tile,COLLECTION)
            size,sha=downloaded[tile]
            if qa["native_file_bytes"]!=size or qa["native_sha256"]!=sha:
                raise IntakeError("DGT_grid_native_stream_SHA_mismatch")
            per_tile[tile]=qa
        phase("native_grid_geometry_validation")
        validate_native_grid_geometry(per_tile)
        phase("native_17_seam_pixel_validation")
        seams=evaluate_seams(all_paths)
        phase("validated")
        return {
            "mission":"MN-GEO-RAIL-001","worker":"W2",
            "stage":"W2_DGT_protected_12_real_tiles_3_by_4km_grid",
            "status":"twelve_native_DGT_GeoTIFFs_and_all_17_seams_validated",
            "observed_utc":datetime.now(timezone.utc).isoformat(),
            "producer":"Direção-Geral do Território",
            "source_collection":COLLECTION,
            "source_STAC_sha256":stac_sha,
            "grid_columns":list(COLS),"grid_rows":list(ROWS),
            "grid_extent_pttm06":[80000,206000,83000,210000],
            "grid_area_km2":12,"tile_count":len(per_tile),
            "valid_native_pixel_cells":sum(x["raster"]["valid_pixels"] for x in per_tile.values()),
            "joins_total":len(seams),
            "joint_neighbor_cell_pairs_valid":sum(x["pairs_valid"] for x in seams),
            "native_total_downloaded_bytes":total,
            "tile_receipts":list(per_tile.values()),
            "seams":seams,
            "original_native_rasters_preserved_after_job":False,
            "registered_CDD_credentials_signed_links_never_persisted":True,
            "no_source_raster_publication":True,
            "complete_Norte_Zamora_terrain_coverage_verified":False,
            "datum_vertical_cross_border_verified":False,
            "canonical_Fxx_accepted":False,
            "site_publication_authorized":False,
        }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index",required=True,type=Path)
    p.add_argument("--receipt",required=True,type=Path)
    args=p.parse_args()
    progress={"safe_phase":"not_started"}
    receipt={"mission":"MN-GEO-RAIL-001","stage":"W2_DGT_protected_12_real_tiles_3_by_4km_grid",
             "status":"not_validated","tile_count_validated":0,
             "canonical_Fxx_accepted":False,"site_publication_authorized":False,
             "source_native_rasters_preserved":False,
             "observed_utc":datetime.now(timezone.utc).isoformat()}
    try:
        receipt=run(args.index,progress)
    except IntakeError as e:
        receipt["safe_error_code"]=e.code
        receipt["safe_failure_phase"]=progress["safe_phase"]
    except Exception:
        receipt["safe_error_code"]="unexpected_grid_error_no_sensitive_details"
        receipt["safe_failure_phase"]=progress["safe_phase"]
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,indent=2,sort_keys=True,ensure_ascii=False)+"\n",
                            encoding="utf-8")
    print(json.dumps({"status":receipt["status"],"safe_error_code":receipt.get("safe_error_code"),
                      "safe_phase":receipt.get("safe_failure_phase"),
                      "validated_tiles":receipt.get("tile_count",0)},ensure_ascii=False))
    if receipt["status"]!="twelve_native_DGT_GeoTIFFs_and_all_17_seams_validated":
        raise SystemExit("twelve_native_DGT_grid_not_validated")

if __name__=="__main__":
    main()
