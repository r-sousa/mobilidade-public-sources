#!/usr/bin/env python3
"""Source-hashed *cross-resolution descriptive*, not geodetic, WCS response QA.

MDT5 and MDT25 are independently produced WCS output grids. Comparing 25m
values to the arithmetic mean of their 25 native 5m pixels is descriptive;
these discrepancies are NOT height errors, datum offsets or track gradients.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import rasterio
from geo_rail_es_wcs_preserve_response import verify_existing,FILE_BY_COVERAGE

def analyze(directory:Path):
    receipt=verify_existing(directory)
    data={}
    diag={}
    for resolution in (5,25):
        name=FILE_BY_COVERAGE[f"Elevacion25830_{resolution}"]
        content=(directory/name).read_bytes()
        with rasterio.open(directory/name) as ds:
            x=ds.read(1,masked=True)
            if bool(np.ma.getmaskarray(x).any()):raise ValueError("nonzero_mask_disallowed")
            z=np.array(x,dtype=np.float64)
            vals=np.unique(z)
            diag[str(resolution)]={
                "source_filename":name,
                "source_sha256":hashlib.sha256(content).hexdigest(),
                "width_px":ds.width,"height_px":ds.height,
                "value_integer_encoded":bool(np.all(z==np.rint(z))),
                "GeoTIFF_dtype":ds.dtypes[0],
                "unique_elevation_values_count":int(vals.size),
                "min_m":float(z.min()),"max_m":float(z.max()),
                "median_m":float(np.median(z)),
                "valid_cells":int(z.size)
            }
            data[resolution]=z
    coarse=data[25]
    fine_5x5_mean=data[5].reshape(40,5,40,5).mean(axis=(1,3))
    residual=coarse-fine_5x5_mean
    absd=np.abs(residual)
    return {
        "mission":"MN-GEO-RAIL-001","worker":"W3",
        "stage":"descriptive_resolution_comparison_between_actual_WCS_response_grids",
        "public_release":"https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-cnig-wcs-zamora-1km2-preacceptance-41194194127",
        "site":"Zamora exploratory 1km2, not a rail alignment",
        "bbox_epsg25830":[270500,4597800,271500,4598800],
        "distinct_territory_km2":1,
        "source_original_producer_tile":False,
        "GeoTIFF_WCS_response_exact_original_bytes":True,
        "raster_value_units_inferred_as_elevation_m_not_vertical_accuracy":True,
        "data_by_resolution_m":diag,
        "comparison_operation":"25m WCS elevation value minus arithmetic mean of its 5x5 contained 5m WCS elevation cells",
        "comparison_cells":int(residual.size),
        "difference_mean_m":float(residual.mean()),
        "difference_median_m":float(np.median(residual)),
        "difference_min_m":float(residual.min()),"difference_max_m":float(residual.max()),
        "difference_MAE_m":float(absd.mean()),
        "difference_RMS_m":float(np.sqrt(np.mean(residual**2))),
        "difference_abs_p95_m":float(np.quantile(absd,.95)),
        "difference_abs_p99_m":float(np.quantile(absd,.99)),
        "difference_fraction_abs_gt_1m":float(np.mean(absd>1)),
        "this_is_not_an_estimate_of_vertical_error_or_RMSE_vs_survey_marks":True,
        "independent_national_vertical_datum_validation":False,
        "PT_ES_vertical_harmonization_validated":False,
        "continuity_of_rail_corridor_pixels_validated":False,
        "Fxx_accepted":False,"Site_authorized":False
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    result=analyze(args.source_dir)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:result[k] for k in ("comparison_cells","difference_RMS_m","difference_MAE_m",
      "difference_min_m","difference_max_m")},sort_keys=True))
if __name__=="__main__":main()
