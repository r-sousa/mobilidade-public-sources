#!/usr/bin/env python3
"""One small (1 km²) IGN/CNIG WCS GetCoverage technical sample near Zamora.

No full geographic series is downloaded. A max 5MB response is inspected as
a temporary raster; only metadata/SHA-256 is published. Fxx governance stays
private, vertical compatibility and reuse remain unresolved.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://servicios.idee.es/wcs-inspire/mdt"
COVERAGE = "Elevacion25830_25"
# Exploratory 1x1-km window near city of Zamora in ETRS89 / UTM 30N.
WEST, SOUTH, EAST, NORTH = (270_500, 4_597_800, 271_500, 4_598_800)
MAX_BYTES = 5_000_000


def coverage_url():
    params = [
        ("service", "WCS"), ("request", "GetCoverage"), ("version", "2.0.1"),
        ("coverageId", COVERAGE), ("format", "image/tiff"),
        ("subset", f"x({WEST},{EAST})"),
        ("subset", f"y({SOUTH},{NORTH})"),
    ]
    return BASE + "?" + urlencode(params)


def download_bounded(url, dest):
    total = 0
    sha = hashlib.sha256()
    with urlopen(Request(url, headers={"User-Agent": "MN-GEO-RAIL-001-ES-sample/1.0"}),
                 timeout=40) as response, dest.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"unexpected status {response.status}")
        content_type = response.headers.get("Content-Type")
        while True:
            chunk = response.read(512 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                raise RuntimeError("GetCoverage exceeds 5 MB safety cap")
            sha.update(chunk)
            out.write(chunk)
    return total, sha.hexdigest(), content_type


def inspect(path):
    import rasterio
    with rasterio.open(path) as ds:
        if ds.driver != "GTiff" or ds.count < 1:
            raise RuntimeError(f"unexpected coverage type {ds.driver}")
        if ds.crs is None or ds.crs.to_epsg() != 25830:
            raise RuntimeError(f"unexpected coverage CRS {ds.crs}")
        if ds.width > 1000 or ds.height > 1000:
            raise RuntimeError(f"unexpected large coverage {ds.width}x{ds.height}")
        values = ds.read(1, masked=True).compressed()
        if len(values) == 0:
            raise RuntimeError("no valid terrain cells found in sample")
        return {
            "driver": ds.driver, "crs": str(ds.crs), "width_px": ds.width,
            "height_px": ds.height, "dtype": ds.dtypes[0],
            "nodata": ds.nodata, "bounds_utm30": list(ds.bounds),
            "pixel_size_m": [abs(ds.transform.a),abs(ds.transform.e)],
            "valid_cells": int(len(values)), "min_terrain_m": float(values.min()),
            "max_terrain_m": float(values.max()), "mean_terrain_m": float(values.mean())
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = coverage_url()
    receipt = {
        "mission": "MN-GEO-RAIL-001", "worker": "W3",
        "stage": "ES_WCS_25m_Zamora_1km2_pilot",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "coverage_id": COVERAGE,
        "query_bbox_utm30_epsg25830": [WEST,SOUTH,EAST,NORTH],
        "source_url": url, "status": "unverified",
        "native_raster_preserved": False,
        "canonical_acceptance": False, "licence_clearance": False,
        "vertical_compatibility_verified": False,
        "ready_for_rail_alignment": False,
    }
    try:
        with TemporaryDirectory(prefix="mn-geo-es-wcs-") as workspace:
            native = Path(workspace) / "wcs-native-response.bin"
            size, sha, content_type = download_bounded(url, native)
            receipt["response_bytes"] = size
            receipt["response_sha256"] = sha
            receipt["content_type"] = content_type
            with native.open("rb") as raster_stream:
                prefix = raster_stream.read(4)
                if prefix not in (bytes([73,73,42,0]), bytes([77,77,0,42]),
                                  bytes([73,73,43,0]), bytes([77,77,0,43])):
                    raster_stream.seek(0)
                    receipt["response_excerpt"] = raster_stream.read(240).decode("utf-8", "replace")
                    raise RuntimeError("WCS response is not TIFF")
            receipt["raster"] = inspect(native)
            receipt["status"] = "one_coverage_sample_validated"
    except Exception as exc:
        receipt["status"] = "sample_unverified_error"
        receipt["error_type"] = type(exc).__name__
        receipt["error_excerpt"] = str(exc)[:240]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status":receipt["status"],"raster":receipt.get("raster"),
                      "error":receipt.get("error_excerpt")}, ensure_ascii=False))
    if receipt["status"] != "one_coverage_sample_validated":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
