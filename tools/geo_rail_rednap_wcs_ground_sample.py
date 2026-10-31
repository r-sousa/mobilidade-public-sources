#!/usr/bin/env python3
"""W4 experimental REDNAP survey-mark vs IGN 5m/25m terrain pixel diagnostics.

Source marks and both heights are taken ONLY from previously verified bounded
official IGN REDNAP OGC API-Features receipt (151 observations). Six marks
are selected reproducibly by nearest geographic *anchor* among available
height pairs; no selection based on observed residuals.
Two 2x2km official IGN WCS rasters per mark are downloaded in temporary
runner, SHA256-checked by native intake. Source raster is NOT an on-mark
survey (mark can be on bridges, masonry and other non-bare-ground features);
residuals do not establish raster accuracy or PT-ES datum compatibility.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from geo_rail_es_continuity_qa import acquire,build_url
REDNAP_SOURCE="reports/mn-geo-rail-001/ign-rednap-aliste-zamora-bounded-benchmarks.json"
SRC_COLLECTION="https://api-features.ign.es/collections/red_nap"
ANCHORS=(
 ("Alcanices_west",(-6.48,41.70),"Alcanices"),
 ("Alcanices_central",(-6.36,41.72),"Alcanices"),
 ("Alcanices_east",(-6.25,41.66),"Alcanices"),
 ("Zamora_west",(-5.88,41.48),"Zamora"),
 ("Zamora_central",(-5.76,41.51),"Zamora"),
 ("Zamora_east",(-5.64,41.52),"Zamora"),
)
SOURCE_WINDOWS={
 "Alcanices":(-6.55,41.58,-6.18,41.88),
 "Zamora":(-5.97,41.38,-5.55,41.69),
}
RESOLUTIONS=(5,25)
EXPECTED_WCS_CALLS=12

def official_candidates(report_path):
    raw=Path(report_path).read_bytes()
    doc=json.loads(raw)
    if (doc.get("source_collection")!=SRC_COLLECTION or
        doc.get("distinct_survey_mark_candidates")!=151 or
        doc.get("distinct_marks_with_both_heights")!=119 or
        not doc.get("source_fully_retrieved_in_all_windows") or
        doc.get("cross_border_harmonization_validated") is not False):
        raise ValueError("REDNAP_source_receipt_not_preverified")
    rows=doc.get("survey_mark_candidates")
    if not isinstance(rows,list) or len(rows)!=151:raise ValueError("REDNAP_missing_source_marks")
    selected={}
    for name,anchor,sector in ANCHORS:
        bb=SOURCE_WINDOWS[sector]
        pool=[r for r in rows if r.get("both_heights_published") and
              bb[0]<=r["lon_etrs89"]<=bb[2] and bb[1]<=r["lat_etrs89"]<=bb[3] and
              r["local_deduplication_key"] not in {s["local_deduplication_key"] for s in selected.values()}]
        if not pool: raise ValueError("no_published_RED_NAP_marks_for_reviewed_anchor")
        # Geographic angular distance is only for fixed deterministic ordering,
        # not a metric for choosing a route or declaring survey proximity.
        pool.sort(key=lambda p:((p["lon_etrs89"]-anchor[0])**2+
                                 (p["lat_etrs89"]-anchor[1])**2,
                                p["local_deduplication_key"]))
        selected[name]=pool[0]
    return selected,hashlib.sha256(raw).hexdigest()

def requested_box(lon,lat,transformer):
    x,y=transformer.transform(lon,lat)
    x0=int(round(x/25)*25)
    y0=int(round(y/25)*25)
    bbox=[x0-1000,y0-1000,x0+1000,y0+1000]
    # Exact previous W3 2x2km approved native WCS grid scope.
    for resolution in RESOLUTIONS:
        build_url(resolution,bbox)
    return bbox,x,y

def sample_original_raster(path,x,y):
    import numpy as np
    import rasterio
    with rasterio.open(path) as src:
        row,col=src.index(x,y)
        if not (1<=row<src.height-1 and 1<=col<src.width-1):
            raise ValueError("REDNAP_marker_not_in_interior_of_requested_WCS")
        box=src.read(1,window=((row-1,row+2),(col-1,col+2)),masked=True)
        if box.shape!=(3,3) or int(box.count())!=9:
            raise ValueError("marker_WCS_3x3_neighborhood_contains_NoData")
        centre=float(box[1,1]);med=float(np.median(box.compressed()))
        xx,yy=src.xy(row,col)
        pixel_dist=math.hypot(x-xx,y-yy)
        expected_max=0.708*max(src.res)
        if pixel_dist>expected_max:
            raise ValueError("WCS_mark_nearest_pixel_distance_above_half_diagonal")
        return {"sample_value_m":centre,"neighbor_3x3_median_m":med,
                "neighbor_3x3_min_m":float(box.min()),
                "neighbor_3x3_max_m":float(box.max()),
                "nearest_pixel_distance_to_mark_m":float(pixel_dist),
                "native_resolution_m":float(src.res[0]),
                "source_raster_horizontal_crs":"EPSG:25830",
                "pixel_row":row,"pixel_column":col}

def run(report_path):
    from pyproj import Transformer
    selection,source_sha=official_candidates(report_path)
    transformer=Transformer.from_crs(4326,25830,always_xy=True)
    report={"mission":"MN-GEO-RAIL-001","worker":"W4",
      "stage":"REDNAP_orthometric_marks_vs_original_IGN_WCS_ground_cells_exploratory",
      "observed_utc":datetime.now(timezone.utc).isoformat(),
      "official_mark_source":"IGN REDNAP OGC API-Features",
      "REDNAP_public_source_sha256":source_sha,
      "REDNAP_source_observation_count":151,
      "source_marks_with_both_height_types":119,
      "selection_method":"fixed six geographic anchors; nearest available REDNAP height pair; NO elevation/residual-based filtering",
      "native_WCS_provider":"IGN/CNIG WCS 2.0.1",
      "WCS_source_native_vertical_datum_explicit_from_GeoTIFF":False,
      "published_mark_not_necessarily_local_bare_ground_height":True,
      "mark_vs_raster_differences_not_assessed_as_vertical_datum_bias":True,
      "raster_elevation_accuracy_certified_by_this_test":False,
      "real_crossborder_vertical_benchmark_harmonization_proven":False,
      "canonical_Fxx_accepted":False,
      "Site_publication_authorized":False,
      "native_rasters_preserved":False,
      "comparisons":[],"total_WCS_native_requests":0}
    with TemporaryDirectory(prefix="mn-ign-rednap-wcs-") as tmp:
        for name,anchor,region in ANCHORS:
            mark=selection[name]
            lon,lat=mark["lon_etrs89"],mark["lat_etrs89"]
            bbox,x,y=requested_box(lon,lat,transformer)
            rec={"anchor_label":name,"anchor_lonlat":list(anchor),
                 "rednap_mark_name":mark.get("nombre"),
                 "rednap_mark_local_key":mark["local_deduplication_key"],
                 "rednap_published_orthometric_height_m":mark["orthometric_height_m"],
                 "rednap_published_ellipsoidal_height_m":mark["ellipsoidal_height_m"],
                 "mark_lonlat_etrs89":[lon,lat],"native_window_bbox_epsg25830":bbox,
                 "NOT_same_point_ground_survey":True,
                 "same_vertical_CRS_not_confirmed_from_WCS_GeoTIFF":True,
                 "WCS_pilots":[]}
            for res in RESOLUTIONS:
                filebase=f"{name}-{res}"
                raster_pixels,raster_meta=acquire(
                    build_url(res,bbox),bbox,res,tmp,filebase)
                report["total_WCS_native_requests"]+=1
                details=sample_original_raster(Path(tmp)/(filebase+".tif"),x,y)
                difference=details["sample_value_m"]-mark["orthometric_height_m"]
                rec["WCS_pilots"].append({
                    "resolution_m":res,"original_WCS_object":raster_meta,
                    "terrain_pixel_sampling":details,
                    "WCS_cell_minus_RED_NAP_mark_orthometric_height_m":float(difference),
                    "residual_is_not_surveyed_ground_error":True,
                    "raster_original_not_persisted":True})
            report["comparisons"].append(rec)
    if (report["total_WCS_native_requests"]!=EXPECTED_WCS_CALLS or
        len(report["comparisons"])!=len(ANCHORS)):
        raise ValueError("incomplete_native_WCS_and_REDNAP_mark_comparisons")
    summary={}
    for res in RESOLUTIONS:
        d=[x["WCS_cell_minus_RED_NAP_mark_orthometric_height_m"]
             for p in report["comparisons"] for x in p["WCS_pilots"]
             if x["resolution_m"]==res]
        sd=sorted(d)
        summary[str(res)]={"n_mark_cell_comparisons":len(d),
                           "mean_signed_raster_minus_mark_m":sum(d)/len(d),
                           "median_signed_raster_minus_mark_m":(sd[2]+sd[3])/2,
                           "min_signed_raster_minus_mark_m":min(d),
                           "max_signed_raster_minus_mark_m":max(d),
                           "interpretation":"includes geometry/mark-type/support and pixel scale differences; NOT datum bias or certified raster accuracy"}
    report["descriptive_terrain_mark_residual_statistics"]=summary
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--REDNAP-source",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    arg=p.parse_args()
    try:
        j=run(arg.REDNAP_source)
    except Exception as exc:
        j={"mission":"MN-GEO-RAIL-001","stage":"REDNAP_vs_WCS_sample_not_validated",
           "error_class":type(exc).__name__,
           "crossborder_vertical_harmonization_proven":False,
           "canonical_Fxx_accepted":False}
        arg.output.parent.mkdir(parents=True,exist_ok=True)
        arg.output.write_text(json.dumps(j,indent=2)+"\n")
        raise SystemExit("REDNAP WCS exploratory marker QA failed safely")
    arg.output.parent.mkdir(parents=True,exist_ok=True)
    arg.output.write_text(json.dumps(j,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":"six_official_mark_vs_WCS_source_cell_checks",
                      "calls":j["total_WCS_native_requests"],
                      "sampled_marks":len(j["comparisons"]),
                      "median_signed_residuals_m":{k:v["median_signed_raster_minus_mark_m"]
                         for k,v in j["descriptive_terrain_mark_residual_statistics"].items()},
                      "canonical":False}))

if __name__=="__main__":
    main()
