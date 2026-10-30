#!/usr/bin/env python3
"""MN-GEO-RAIL-001 W3: two-block/union WCS overlap consistency pilot.

In each of two exploratory non-route areas, request adjacent 2x2 km MDT
blocks at 25 m and 5 m, then request their 4x2 km union independently.
Compare every pixel against the corresponding union cells. Native rasters
are temporary, bounded to 5 MB per GET, and never published.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

SERVICE = "https://servicios.idee.es/wcs-inspire/mdt"
# Centres in EPSG:25830 are projected from published W3 site coordinates.
LOCATIONS = {
    "Alcanices": (-6.346470, 41.699400),
    "Vinas": (-6.471160, 41.773300),
}
RESOLUTIONS = (25, 5)
MAX_BYTES = 5_000_000


def site_boxes(lon, lat, transformer):
    east, north = transformer.transform(lon, lat)
    # Align to 25m so 5m and 25m grids share the same requested boundaries.
    east = int(round(east / 25) * 25)
    north = int(round(north / 25) * 25)
    west, south = east - 2000, north - 1000
    return (
        [west, south, east, north + 1000],
        [east, south, east + 2000, north + 1000],
        [west, south, east + 2000, north + 1000],
    )


def build_url(resolution, bbox):
    if resolution not in RESOLUTIONS or len(bbox) != 4:
        raise ValueError("unsupported WCS resolution/geometry")
    x0, y0, x1, y1 = bbox
    if (x1 - x0, y1 - y0) not in ((2000, 2000), (4000, 2000)):
        raise ValueError("only 2x2 or 4x2 km samples are approved")
    if not (150000 <= x0 < x1 <= 350000 and 4550000 <= y0 < y1 <= 4700000):
        raise ValueError("window outside approved Zamora-region scope")
    q = [("service","WCS"), ("request","GetCoverage"), ("version","2.0.1"),
         ("coverageId",f"Elevacion25830_{resolution}"), ("format","image/tiff"),
         ("subset",f"x({x0},{x1})"), ("subset",f"y({y0},{y1})")]
    return SERVICE + "?" + urlencode(q)


def acquire(url, bbox, resolution, tempdir, suffix, opener=None):
    import numpy as np
    import rasterio
    from urllib.request import urlopen, Request

    opener = opener or urlopen
    path = Path(tempdir) / f"{suffix}.tif"
    digest = hashlib.sha256()
    count = 0
    with opener(Request(url, headers={
            "User-Agent": "MN-GEO-RAIL-001-W3-seam-qa/1.0"}), timeout=40) as response:
        if response.status != 200:
            raise RuntimeError(f"WCS HTTP {response.status}")
        with path.open("wb") as out:
            while True:
                block = response.read(262144)
                if not block:
                    break
                count += len(block)
                if count > MAX_BYTES:
                    raise ValueError("WCS response exceeded 5 MB per-object budget")
                out.write(block)
                digest.update(block)
    with rasterio.open(path) as ds:
        expected_w = int((bbox[2]-bbox[0]) / resolution)
        expected_h = int((bbox[3]-bbox[1]) / resolution)
        if (ds.driver != "GTiff" or ds.count != 1 or ds.crs is None
                or ds.crs.to_epsg() != 25830 or ds.width != expected_w or ds.height != expected_h
                or not np.allclose(list(ds.bounds), bbox, atol=0.001)):
            raise ValueError("non-matching coverage grid, band count, extent or CRS")
        values = ds.read(1, masked=True)
        valid = int(values.count())
        if valid <= 0:
            raise ValueError("no valid terrain cells in selected window")
        info = {"bytes": count, "sha256": digest.hexdigest(), "bbox_utm30": bbox,
                "width_px": ds.width, "height_px": ds.height, "valid_cells": valid,
                "missing_cells": expected_w*expected_h-valid, "dtype": ds.dtypes[0],
                "masked_values": int(np.ma.count_masked(values)),
                "min_m": float(values.min()), "max_m": float(values.max()),
                "nodata_reported": ds.nodata}
    # Keep arrays in runner memory for QA. No native raster is preserved in Git.
    return values, info


def compare_blocks(left, right, union):
    import numpy as np
    if left.shape[0] != right.shape[0] or left.shape[0] != union.shape[0]:
        raise ValueError("WCS output grid row mismatch")
    width = left.shape[1]
    if union.shape[1] != width + right.shape[1]:
        raise ValueError("WCS union width not equal to sum of blocks")
    expected = np.ma.concatenate([left, right], axis=1)
    masks_equal = bool(np.array_equal(np.ma.getmaskarray(expected),
                                      np.ma.getmaskarray(union)))
    overlap = ~np.ma.getmaskarray(expected) & ~np.ma.getmaskarray(union)
    equal_values = bool(np.array_equal(expected.data[overlap], union.data[overlap]))
    return {
        "all_mask_flags_identical": masks_equal,
        "all_valid_sample_values_identical": equal_values,
        "jointly_valid_cells": int(overlap.sum()),
        "cells_total": int(expected.size),
        "block_grid_equals_independent_union": masks_equal and equal_values,
        "max_abs_diff_m": (
            float(np.max(np.abs(expected.data[overlap].astype("float64")-
                                union.data[overlap].astype("float64"))))
            if overlap.any() else None),
    }


def run():
    from pyproj import Transformer
    t = Transformer.from_crs(4326, 25830, always_xy=True)
    report = {"mission":"MN-GEO-RAIL-001", "worker":"W3",
        "stage":"es_wcs_adjacent_blocks_union_continuity_qa",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "producer":"IGN/CNIG Spain, public WCS GetCoverage",
        "is_rail_alignment":False,
        "geographic_selection":"two exploratory 4x2 km windows, NOT an optimized rail line",
        "expected_tests":len(LOCATIONS)*len(RESOLUTIONS),
        "validated_tests":0,
        "native_rasters_preserved":0,
        "continuous_coverage_between_sites_verified":False,
        "vertical_datum_crossborder_verified":False,
        "licence_and_canonical_acceptance":False,
        "results":[]}
    for name,(lon,lat) in LOCATIONS.items():
        boxes = site_boxes(lon,lat,t)
        for resolution in RESOLUTIONS:
            rec = {"site":name,"site_lonlat":[lon,lat],"resolution_m":resolution,
                   "windows":boxes,"status":"unverified"}
            try:
                with TemporaryDirectory(prefix="mn-w3-qa-") as tmp:
                    samples = [acquire(build_url(resolution,bbox),bbox,resolution,tmp,
                                       f"{name}-{resolution}-{i}")
                               for i,bbox in enumerate(boxes)]
                    comparison = compare_blocks(*(x[0] for x in samples))
                    rec["parts"] = [x[1] for x in samples]
                    rec["comparison"] = comparison
                    if not comparison["block_grid_equals_independent_union"]:
                        raise ValueError("adjacent blocks disagree with independent WCS union")
                    if rec["parts"][2]["missing_cells"] > 0:
                        raise ValueError("NoData in tested union (not complete pixel coverage)")
                    rec["status"] = "validated_adjacent_and_union_no_missing_cells"
                    report["validated_tests"] += 1
            except Exception as exc:
                rec["status"] = "not_validated"
                rec["error_type"] = type(exc).__name__
                rec["error_excerpt"] = str(exc)[:160]
            report["results"].append(rec)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    receipt=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"expected":receipt["expected_tests"],"validated":receipt["validated_tests"],
                      "statuses":[(x["site"],x["resolution_m"],x["status"]) for x in receipt["results"]]}))
    if receipt["validated_tests"] != receipt["expected_tests"]:
        raise SystemExit("One or more grid-union QA checks did not validate; see receipt")


if __name__ == "__main__":
    main()
