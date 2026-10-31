#!/usr/bin/env python3
"""Source-reproducible RNGAP survey-point adjacency to real 12km² DGT mosaic.

Finds next 1km² DGT source-native raster candidate nearest official marks.
Uses producer spatial reference EPSG:3763 and source catalogue ID pairing.
This is ONLY a prioritization of future controlled DGT raster acquisition,
not real pilot pixel QA for the selected 1km² tile, railway alignment or
independent benchmark validation.
"""
from __future__ import annotations
import argparse,json,hashlib,math
from datetime import datetime,timezone
from pathlib import Path

DTM_BBOX=(80000,206000,83000,210000)
ORIGINAL_DGT_TILE="MDT-2m-279503-09-2024"
VALIDATED_DGT_RELEASE="mn-geo-rail-001-dgt-grid12-preacceptance-41158397813"
EXPECTED_ORIGINAL_MARKS=427

def sha256(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()

def source_sample(mark_file,sector_catalog_file):
    doc=json.loads(Path(mark_file).read_text())
    if (doc.get("status")!="complete_for_three_requested_windows_no_corridor_claim" or
        doc.get("source_layer")!="RGN:RedeNivelamento" or
        doc.get("source_height_property")!="ALTH38" or
        doc.get("unique_real_DGT_source_mark_count")!=EXPECTED_ORIGINAL_MARKS):
        raise ValueError("DGT_427_mark_source_not_fully_verified")
    original=doc["unique_DGT_source_marks"]
    if len(original)!=EXPECTED_ORIGINAL_MARKS or len({x["WFS_feature_id"] for x in original})!=len(original):
        raise ValueError("source_WFS_mark_ID_count_not_unique")
    cat=json.loads(Path(sector_catalog_file).read_text())
    if cat.get("mission")!="MN-GEO-RAIL-001":
        raise ValueError("official_DGT_catalogue_mission_not_expected")
    ids={obj["tile_id"] for req in cat["requests"] if req.get("collection")=="MDT-2m"
         for obj in req.get("footprints",[])}
    if ORIGINAL_DGT_TILE not in ids:
        raise ValueError("local_RNGAP_target_tile_absent_in_previous_DGT_catalogue")
    bx=DTM_BBOX
    nearest=[]
    for m in original:
        xy=m["native_xy_epsg3763"]
        if not isinstance(xy,list) or len(xy)!=2:
            raise ValueError("WFS_source_mark_not_in_PT_TM06")
        x,y=xy
        dd=math.hypot(x-min(bx[2],max(x,bx[0])),y-min(bx[3],max(y,bx[1])))
        tile=f"MDT-2m-{int(200+math.floor(x/1000))}{int(301+math.floor(y/1000))}-09-2024"
        nearest.append({
          "WFS_feature_id":m["WFS_feature_id"],
          "mark":m["mark_label_MARCA"],"xy_PT_TM06":xy,
          "published_ALTH38_m":m["DGT_original_ALTH38_height_m"],
          "distance_to_real_mosaic_bbox_m":dd,
          "source_tile_candidate_by_1km_grid":tile})
    near=sorted(nearest,key=lambda x:(x["distance_to_real_mosaic_bbox_m"],x["WFS_feature_id"]))
    inside=[v for v in near if v["distance_to_real_mosaic_bbox_m"]<0.00001]
    target=[m for m in near if m["source_tile_candidate_by_1km_grid"]==ORIGINAL_DGT_TILE]
    if not target:
        raise ValueError("no_real_RNGAP_mark_in_target_DGT_tile_candidate")
    if len({tuple(x["xy_PT_TM06"]) for x in target})!=1:
        raise ValueError("target_contains_multiple_control_positions_review_required")
    # DGT naming: column 200 -> x=0 km, row 301 -> y=0 km.
    # Confirm point containment in the actual square, not just STAC bbox.
    expected_bounds=[79000,202000,80000,203000]
    if any(not (expected_bounds[0]<=v["xy_PT_TM06"][0]<expected_bounds[2] and
                expected_bounds[1]<=v["xy_PT_TM06"][1]<expected_bounds[3])
           for v in target):
        raise ValueError("RNGAP_survey_mark_not_in_selected_original_DGT_tile")
    values=[x["published_ALTH38_m"] for x in target]
    return {
      "mission":"MN-GEO-RAIL-001","stage":"DGT_verified_RNGAP_marks_vs_existing_original_native_DTM_scope",
      "timestamp_utc":datetime.now(timezone.utc).isoformat(),
      "RNGAP_source_427_original_mark_SHA256":sha256(mark_file),
      "DGT_MDТ_candidate_catalogue_SHA256":sha256(sector_catalog_file),
      "real_mosaic_source_release":VALIDATED_DGT_RELEASE,
      "real_mosaic_bbox_PT_TM06":list(DTM_BBOX),
      "original_DGT_WFS_marks_in_three_reviewed_windows":len(near),
      "original_RNGAP_marks_in_validated_12km2_mosaic":len(inside),
      "nearest_original_RNGAP_marks":near[:10],
      "next_priority_1km2_DGT_original_raster_candidate":ORIGINAL_DGT_TILE,
      "next_priority_candidate_is_in_existing_primary_DGT_STAC_inventory":True,
      "next_priority_native_raster_bounds_epsg3763":expected_bounds,
      "grid_index_formula":"col=200+floor(x/1000); row=301+floor(y/1000)",
      "correction_notice":"Previous audit incorrectly identified tile 279502. The original mark y=202288 belongs to DGT row 503. No wrong-tile raster was acquired.",
      "selected_source_tile_is_NOT_yet_acquired_or_pixel_QA_validated":True,
      "next_priority_benchmark_mark_count":len(target),
      "next_priority_benchmark_distinct_planimetric_positions":1,
      "next_priority_same_XY_published_height_spread_m":max(values)-min(values),
      "multiple_RNGAP_heights_at_same_XY_must_not_be_averaged":True,
      "potential_multiple_marks_or_height_reference_attributes_must_be_verified":True,
      "next_priority_mark_records":target,
      "Fxx_accepted":False,"Site_approved":False,
      "crossborder_vertical_benchmark_control_accepted":False
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mark-source",required=True,type=Path)
    p.add_argument("--DGT-catalogue",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    result=source_sample(a.mark_source,a.DGT_catalogue)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"sampled_marks":result["original_DGT_WFS_marks_in_three_reviewed_windows"],
                      "marks_in_validated_mosaic":result["original_RNGAP_marks_in_validated_12km2_mosaic"],
                      "target_tile":result["next_priority_1km2_DGT_original_raster_candidate"],
                      "selected_marks":result["next_priority_benchmark_mark_count"],
                      "distinct_XY":result["next_priority_benchmark_distinct_planimetric_positions"],
                      "same_XY_orthometric_height_spread_m":result["next_priority_same_XY_published_height_spread_m"]}))
if __name__=="__main__":main()
