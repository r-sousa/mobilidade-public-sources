#!/usr/bin/env python3
"""Protected DGT original 2m tile 279503 + genuine NP159 RNGAP comparison.

ONLY approved manual workflow_dispatch on protected main and dgt-cdd GitHub
Environment may execute this script against authenticated native DGT CDD.
The original 1 km2 native TIFF is temporarily downloaded, source SHA/raster
identity verified, and candidate NP159 marks are compared to the raw nearest
terrain pixel with physical mark height and datum caveats. Temporary original
rasters may be staged for separate no-credential public CC BY prerelease
ONLY if reviewed explicitly in workflow_dispatch input.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import shutil
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from geo_rail_pt_native_intake_qa import audit,catalogue_record,stream_sha256
from geo_rail_pt_cdd_authenticated import (
 authenticated_session,request_bounded_redirects,read_metadata,
 allowed_url,TRUSTED_AUTH_REDIRECTS,TRUSTED_DATA_REDIRECTS,
 STAC,COLLECTION,IntakeError)
from geo_rail_pt_cdd_pair_pilot import download_small_native

SOURCE_TILE="MDT-2m-279503-09-2024"
SOURCE_BOUNDS=[79000,202000,80000,203000]
SOURCE_MARKS=("RedeNivelamento.4662","RedeNivelamento.4663",
              "RedeNivelamento.4664","RedeNivelamento.4665","RedeNivelamento.4666")
TARGET_STAC_QUERY=[-7.195,41.478,-7.170,41.497]
ORIGINAL_RNGAP_SOURCE="reports/mn-geo-rail-001/pt-rngap-three-window-complete-ALTH38-source.json"
MAX_SOURCE_MARKS=427
MAX_NATIVE_BYTES=25_000_000

def producer_mark_records(path):
    doc=json.loads(Path(path).read_text(encoding="utf-8"))
    if (doc.get("source_layer")!="RGN:RedeNivelamento" or
        doc.get("source_height_property")!="ALTH38" or
        doc.get("unique_real_DGT_source_mark_count")!=MAX_SOURCE_MARKS):
        raise ValueError("RNGAP_427_original_mark_receipt_not_verified")
    originals={x["WFS_feature_id"]:x for x in doc["unique_DGT_source_marks"]}
    if len(originals)!=427:raise ValueError("source_original_RNGAP_mark_ids_not_unique")
    selected=[originals[x] for x in SOURCE_MARKS]
    xy={tuple(x["native_xy_epsg3763"]) for x in selected}
    if xy!={(79468.618,202288.178)}:
        raise ValueError("NP159_source_mark_XY_changed")
    if any(not (SOURCE_BOUNDS[0]<=x["native_xy_epsg3763"][0]<SOURCE_BOUNDS[2] and
                SOURCE_BOUNDS[1]<=x["native_xy_epsg3763"][1]<SOURCE_BOUNDS[3])
           for x in selected):
        raise ValueError("NP159_not_within_exact_source_DGT_native_tile")
    heights=[x["DGT_original_ALTH38_height_m"] for x in selected]
    if not (1.13<max(heights)-min(heights)<1.14):
        raise ValueError("NP159_variants_change_unexpected")
    return selected,hashlib.sha256(Path(path).read_bytes()).hexdigest()

def exact_source_asset(session):
    response=request_bounded_redirects(
        session,"POST",STAC,TRUSTED_AUTH_REDIRECTS,
        json_body={"bbox":TARGET_STAC_QUERY,"collections":[COLLECTION],"limit":200},
        stream=True,phase="reviewed_tile_279503_STAC")
    data,sha=read_metadata(response)
    if data.get("type")!="FeatureCollection" or not isinstance(data.get("features"),list):
        raise IntakeError("unexpected_STAC_feature_response")
    if any(isinstance(z,dict) and z.get("rel")=="next" for z in data.get("links",[])):
        raise IntakeError("STAC_tile_response_paginated_unreviewed")
    matches=[z for z in data["features"] if isinstance(z,dict) and
             z.get("collection")==COLLECTION and z.get("id")==SOURCE_TILE]
    if len(matches)!=1:raise IntakeError("reviewed_DGT_tile_not_once_in_live_STAC")
    assets=matches[0].get("assets")
    data_asset=assets.get("data") if isinstance(assets,dict) else None
    if not isinstance(data_asset,dict) or not str(data_asset.get("type","")).lower().startswith(
            ("image/tiff","image/geotiff")):
        raise IntakeError("source_DGT_GeoTIFF_asset_type_not_verified")
    href=data_asset.get("href")
    if not allowed_url(href,TRUSTED_DATA_REDIRECTS):
        raise IntakeError("unapproved_source_DGT_native_asset")
    return href,sha

def compare_real_mark_native_terrain(path,marks):
    import rasterio
    import numpy as np
    x,y=marks[0]["native_xy_epsg3763"]
    with rasterio.open(path) as ds:
        if (ds.crs.to_epsg()!=3763 or ds.count!=1 or
            ds.width!=500 or ds.height!=500):
            raise ValueError("native_DGT_279503_1km_geometry_unexpected")
        if any(abs(float(a)-b)>0.01 for a,b in zip(ds.bounds,SOURCE_BOUNDS)):
            raise ValueError("DGT_tile_279503_exact_bbox_did_not_match")
        row,col=ds.index(x,y)
        if not (1<=row<499 and 1<=col<499):
            raise ValueError("mark_not_inside_source_raster_interior")
        values=ds.read(1,window=((row-1,row+2),(col-1,col+2)),masked=True)
        if values.shape!=(3,3) or values.count()!=9:
            raise ValueError("raster_3x3_at_NP159_has_nodata")
        z=float(values[1,1])
        pixel_x,pixel_y=ds.xy(row,col)
        px_offset=math.hypot(pixel_x-x,pixel_y-y)
        if px_offset>math.sqrt(2)*ds.res[0]/2+.01:
            raise ValueError("unexpected_pixel_center_versus_mark_offset")
        per_mark=[]
        for mark in marks:
            h=float(mark["DGT_original_ALTH38_height_m"])
            per_mark.append({
              "DGT_original_WFS_feature_id":mark["WFS_feature_id"],
              "DGT_mark_label":mark["mark_label_MARCA"],
              "producer_ALTH38_source_value":mark["DGT_ALTH38_original_source_value"],
              "published_ALTH38_height_m":h,
              "MDT_raw_nearest_pixel_minus_published_mark_m":z-h,
              "same_geographic_XY_as_other_4_marks":True,
              "mark_Z_may_refer_to_physical_offset_or_distinct_point_not_bare_ground":True})
        return {"native_source_tile":SOURCE_TILE,
          "mark_xy_epsg3763":[x,y],
          "raw_DGT_2m_nearest_pixel_height_m":z,
          "raw_DGT_2m_3x3_median_height_m":float(np.median(values.compressed())),
          "raw_DGT_2m_3x3_min_height_m":float(values.min()),
          "raw_DGT_2m_3x3_max_height_m":float(values.max()),
          "pixel_center_distance_to_mark_m":px_offset,
          "physical_mark_offset_not_verified":True,
          "not_an_independent_survey_error_estimate":True,
          "not_DGT_MDT_accuracy_RMSE":True,
          "not_PT_ES_datum_validation":True,
          "comparisons_to_five_mark_VARIANT_heights":per_mark}

def run(index,mark_source,retain_file=None,phase=None):
    def step(label):
        if phase is not None:phase["safe_phase"]=label
    step("official_source_index_and_mark_QA")
    doc=json.loads(Path(index).read_text(encoding="utf-8"))
    catalogue_record(doc,COLLECTION,SOURCE_TILE)
    marks,mark_sha=producer_mark_records(mark_source)
    u=os.getenv("DGT_CDD_USERNAME","")
    p=os.getenv("DGT_CDD_PASSWORD","")
    if not (u and p):raise IntakeError("dgt_environment_credentials_missing")
    with TemporaryDirectory(prefix="mn-rngap-dgt279503-") as tmp:
        dest=Path(tmp)/"native-source-279503.tif"
        step("DGT_protected_CDD_login")
        session=authenticated_session(u,p)
        try:
            step("source_STAC_single_asset")
            href,stac_sha=exact_source_asset(session)
            step("download_bounded_native_GeoTIFF")
            native_bytes,native_sha=download_small_native(session,href,dest)
        finally:
            session.close()
        if native_bytes>MAX_NATIVE_BYTES:
            raise ValueError("unexpected_DGT_single_source_native_size")
        step("audit_full_native_source_raster")
        q=audit(dest,index,SOURCE_TILE,COLLECTION)
        if (q["native_file_bytes"],q["native_sha256"])!=(native_bytes,native_sha):
            raise ValueError("source_native_SHA256_not_equal_to_authenticated_download")
        ras=q["raster"]
        if (ras["width_px"]!=500 or ras["height_px"]!=500 or
            ras["masked_pixels"]!=0 or ras["valid_pixels"]!=250000 or
            ras["resolution_m"]!=[2,2] or
            any(abs(float(z)-t)>.01 for z,t in zip(ras["bounds_pttm06"],SOURCE_BOUNDS))):
            raise ValueError("native_source_pixels_or_shape_not_complete")
        step("real_RNGAP_source_vs_DGT_terrain_comparison")
        pixels=compare_real_mark_native_terrain(dest,marks)
        staged=False
        if retain_file is not None:
            step("stage_verified_native_source_for_separate_no_credentials_release")
            target=Path(retain_file)
            if not target.is_absolute() or target.exists() or target.is_symlink():
                raise IntakeError("source_native_staging_not_safe")
            shutil.copyfile(dest,target)
            if stream_sha256(target,max_bytes=MAX_NATIVE_BYTES)!=(native_bytes,native_sha):
                target.unlink(missing_ok=True)
                raise ValueError("staged_source_GeoTIFF_SHA256_changed")
            staged=True
        return {
          "mission":"MN-GEO-RAIL-001","status":"actual_original_DGT_RNGAP_tile_pixel_QA_passed",
          "stage":"W4_one_native_DGT_tile_with_real_RNGAP_mark_height_sample",
          "timestamp_utc":datetime.now(timezone.utc).isoformat(),
          "producer":"Direção-Geral do Território",
          "source_tile":SOURCE_TILE,
          "reviewed_raster_bbox_epsg3763":list(SOURCE_BOUNDS),
          "original_RNGAP_427_marks_source_SHA256":mark_sha,
          "authenticated_DGT_STAC_response_SHA256":stac_sha,
          "native_source_file_sha256":native_sha,
          "native_source_file_bytes":native_bytes,
          "raster_source_QA":q,
          "mark_terrain_descriptive_comparison":pixels,
          "original_native_raster_staged_for_nonsecret_prerelease":staged,
          "unverified_mark_physical_height_offsets":True,
          "observed_geodetic_PT_ES_vertical_harmonization":False,
          "DGT_MDT_ground_accuracy_established":False,
          "corridor_vertical_profile_ready":False,
          "Fxx_canonical_accepted":False,"Site_publication_authorized":False,
          "credentials_signed_urls_cookies_never_in_receipt":True}
def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--index",type=Path,required=True)
    a.add_argument("--RNGAP-source",type=Path,required=True)
    a.add_argument("--receipt",type=Path,required=True)
    a.add_argument("--retain-file",type=Path,default=None)
    opt=a.parse_args()
    receipt={"mission":"MN-GEO-RAIL-001","status":"not_validated",
      "source_tile":SOURCE_TILE,"Fxx_canonical_accepted":False,
      "Site_publication_authorized":False}
    phase={"safe_phase":"not_started"}
    try:receipt=run(opt.index,opt.RNGAP_source,opt.retain_file,phase)
    except IntakeError as err:
        receipt["safe_error_code"]=err.code
        receipt["safe_failure_phase"]=phase["safe_phase"]
    except Exception:
        receipt["safe_error_code"]="unexpected_error_no_sensitive_details"
        receipt["safe_failure_phase"]=phase["safe_phase"]
    opt.receipt.parent.mkdir(parents=True,exist_ok=True)
    opt.receipt.write_text(json.dumps(receipt,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":receipt["status"],"source_tile":SOURCE_TILE,
       "safe_failure_phase":receipt.get("safe_failure_phase"),
       "safe_error_code":receipt.get("safe_error_code")}))
    if receipt["status"]!="actual_original_DGT_RNGAP_tile_pixel_QA_passed":
        raise SystemExit("Native DGT NP159 original raster/mark QA not validated")
if __name__=="__main__":main()
