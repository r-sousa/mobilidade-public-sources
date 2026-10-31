#!/usr/bin/env python3
"""W3 Zamora: real MDT 5m and 25m native raster QA at one 8 x 2 km sampling strip.

Four adjacent 2 x 2 km blocks per strip/resolution are independently compared
with one independently requested 8 x 2 km WCS GetCoverage. This is LOCAL, not continuous
Portugal-Zamora terrain, route options or vertical harmonization.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

from geo_rail_es_continuity_qa import acquire, SERVICE

# Zamora exploratory regional city sample, NOT a proposed rail alignment.
LOCATIONS={"Zamora":(-5.746992,41.503780)}

RESOLUTIONS=(5,25)
TOTAL_WIDTH_M=8000
HEIGHT_M=2000
CHUNK_WIDTH_M=2000
MAX_QUERIES=10

def strip_boxes(lon,lat,transformer):
    x,y=transformer.transform(lon,lat)
    x=int(round(x/25)*25)
    y=int(round(y/25)*25)
    whole=[x-4000,y-1000,x+4000,y+1000]
    blocks=[[whole[0]+i*2000,whole[1],whole[0]+(i+1)*2000,whole[3]] for i in range(4)]
    if blocks[0][0]!=whole[0] or blocks[-1][2]!=whole[2]:
        raise ValueError("non_contiguous_wcs_grid")
    return blocks,whole

def build_url(resolution,box):
    if resolution not in RESOLUTIONS or not isinstance(box,list) or len(box)!=4:
        raise ValueError("unapproved_WCS_request")
    if any(type(x) is not int for x in box):
        raise ValueError("WCS_grid_requires_integer_coordinate")
    west,south,east,north=box
    if (east-west,north-south) not in ((2000,2000),(8000,2000)):
        raise ValueError("window_not_preapproved")
    if not (150000<=west<east<=350000 and 4550000<=south<north<=4700000):
        raise ValueError("WCS_window_outside_Zamora_region")
    params=[("service","WCS"),("request","GetCoverage"),("version","2.0.1"),
            ("coverageId",f"Elevacion25830_{resolution}"),("format","image/tiff"),
            ("subset",f"x({west},{east})"),("subset",f"y({south},{north})")]
    return SERVICE+"?"+urlencode(params)

def compare_all(parts,whole):
    import numpy as np
    if len(parts)!=4:
        raise ValueError("expected_four_original_blocks")
    if any(x.shape!=parts[0].shape for x in parts):
        raise ValueError("mismatched_block_shapes")
    reconstructed=np.ma.concatenate(parts,axis=1)
    if reconstructed.shape!=whole.shape:
        raise ValueError("wide_request_shape_mismatch")
    mask_equal=bool(np.array_equal(np.ma.getmaskarray(reconstructed),np.ma.getmaskarray(whole)))
    joint=~np.ma.getmaskarray(reconstructed)&~np.ma.getmaskarray(whole)
    equal=bool(np.array_equal(reconstructed.data[joint],whole.data[joint]))
    valid=int(joint.sum())
    return {"same_mask":mask_equal,"same_valid_pixels":equal,
            "total_cells":int(whole.size),"valid_cells":valid,
            "masked_or_missing_cells":int(whole.size-valid),
            "maximum_abs_difference_m":(float(np.max(np.abs(reconstructed.data[joint].astype("float64")-whole.data[joint].astype("float64")))) if valid else None),
            "verified":mask_equal and equal and valid==int(whole.size)}

def run():
    from pyproj import Transformer
    transformer=Transformer.from_crs(4326,25830,always_xy=True)
    result={"mission":"MN-GEO-RAIL-001","stage":"W3_Zamora_single_local_8_by_2_km_real_MDT_seam_validation",
            "observed_utc":datetime.now(timezone.utc).isoformat(),
            "producer":"IGN/CNIG WCS", "worker":"W3",
            "sample_area_per_site_km2":16,"distinct_total_tested_area_km2":16,
            "separate_site_from_Alcanices_and_Vinas":True,
            "horizontal_crs":"EPSG:25830",
            "expected_resolutions_m":list(RESOLUTIONS),
            "requests_maximum":MAX_QUERIES,
            "requested_native_rasters_per_site_and_resolution":5,
            "samples_expected":len(LOCATIONS)*len(RESOLUTIONS),
            "samples_validated":0,
            "native_raster_bytes_persisted":0,
            "full_corridor_terrain_coverage_verified":False,
            "native_vertical_datum_verified":False,
            "crossborder_vertical_harmonization_verified":False,
            "Fxx_canonical_accepted":False,
            "site_publication_authorized":False,
            "sites":[]}
    for site,(lon,lat) in LOCATIONS.items():
        blocks,union=strip_boxes(lon,lat,transformer)
        for res in RESOLUTIONS:
            item={"site":site,"centre_wgs84":[lon,lat],"resolution_m":res,
                  "bbox_union_epsg25830":union,"status":"not_validated",
                  "native_geo_tiffs_saved":False}
            try:
                with TemporaryDirectory(prefix="mn-es-zamora-8km-") as tmp:
                    b=[acquire(build_url(res,bb),bb,res,tmp,f"{site}-{res}-part-{i}") for i,bb in enumerate(blocks)]
                    wide=acquire(build_url(res,union),union,res,tmp,f"{site}-{res}-union")
                    qa=compare_all([x[0] for x in b],wide[0])
                    item["files"]=[x[1] for x in b]+[wide[1]]
                    item["qa"]=qa
                    if not qa["verified"]:
                        raise ValueError("real_WCS_adjacent_cells_disagree_or_are_missing")
                    item["status"]="validated_local_8km_strip"
                    result["samples_validated"]+=1
            except Exception as exc:
                item["error_type"]=type(exc).__name__
                # Do not persist untrusted URL/headers in exception messages.
                item["error_classification"]="bounded_download_or_raster_QA_failure"
            result["sites"].append(item)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"expected":report["samples_expected"],"passed":report["samples_validated"],
                      "statuses":[[x["site"],x["resolution_m"],x["status"]] for x in report["sites"]]}))
    if report["samples_validated"]!=report["samples_expected"]:
        raise SystemExit("Incomplete real MDT QA; inspect sanitized receipt.")

if __name__=="__main__":
    main()
