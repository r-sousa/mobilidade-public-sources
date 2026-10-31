#!/usr/bin/env python3
"""One-tile R1 technical acquisition pilot. No native raster publication.

Downloads one previously HEAD-confirmed public Copernicus COG to temporary
runner disk, validates its basic GeoTIFF metadata and a small interior window,
computes native SHA-256 and discards native bytes after closing the file.
Creates a metadata-only receipt; never grants canonical acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen

SOURCE_ID = "Copernicus_DSM_COG_10_N41_00_W008_00_DEM"
SOURCE_URL = (f"https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/"
              f"{SOURCE_ID}/{SOURCE_ID}.tif")
EXPECTED_SOURCE_BYTES = 44_038_002  # 2026-10-30 producer HEAD observation
MAX_SOURCE_BYTES = 60_000_000


def bounded_download(url: str, dest: Path) -> tuple[int, str]:
    hasher = hashlib.sha256()
    byte_count = 0
    with urlopen(Request(url, headers={"User-Agent": "MN-GEO-RAIL-001-R1-sample/1.0"}),
                 timeout=40) as response, dest.open("wb") as stream:
        if response.status != 200:
            raise RuntimeError(f"source status HTTP {response.status}")
        while True:
            data = response.read(1024 * 1024)
            if not data:
                break
            byte_count += len(data)
            if byte_count > MAX_SOURCE_BYTES:
                raise RuntimeError("source exceeds one-tile byte ceiling")
            hasher.update(data)
            stream.write(data)
    if byte_count != EXPECTED_SOURCE_BYTES:
        raise RuntimeError(
            f"source edition/size changed: expected {EXPECTED_SOURCE_BYTES}, got {byte_count}")
    return byte_count, hasher.hexdigest()


def inspect_raster(path: Path) -> dict:
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(path) as ds:
        if ds.driver != "GTiff" or ds.count != 1:
            raise RuntimeError(f"unsupported raster: {ds.driver}, {ds.count} bands")
        if ds.width != 3600 or ds.height != 3600:
            raise RuntimeError(f"unexpected raster shape {ds.width}x{ds.height}")
        if ds.crs is None or ds.crs.to_epsg() != 4326:
            raise RuntimeError(f"unexpected horizontal CRS: {ds.crs}")
        bounds = list(ds.bounds)
        if not (-8.01 <= bounds[0] <= -7.99 and
                40.99 <= bounds[1] <= 41.01 and
                -7.01 <= bounds[2] <= -6.99 and
                41.99 <= bounds[3] <= 42.01):
            raise RuntimeError(f"unexpected footprint: {bounds}")
        window = Window(1672, 1672, 256, 256)
        data = ds.read(1, window=window, masked=True)
        valid = data.compressed()
        if len(valid) < 1000:
            raise RuntimeError("insufficient valid cells in 256x256 pilot window")
        return {
            "driver": ds.driver,
            "width_px": ds.width, "height_px": ds.height,
            "band_count": ds.count, "dtype": ds.dtypes[0],
            "horizontal_crs": str(ds.crs),
            "bounds_wgs84": bounds,
            "pixel_size_degrees": [abs(ds.transform.a), abs(ds.transform.e)],
            "nodata_declared": ds.nodata,
            "is_tiled": ds.is_tiled,
            "overviews": ds.overviews(1),
            "sample_window": {
                "row_off": 1672, "col_off": 1672,
                "width_px": 256, "height_px": 256,
                "valid_cell_count": int(len(valid)),
                "min_surface_height_m": float(valid.min()),
                "max_surface_height_m": float(valid.max()),
                "mean_surface_height_m": float(valid.mean()),
            }
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="mn-geo-rail-one-tile-") as workspace:
        source = Path(workspace) / "producer-native-cog.tif"
        byte_count, sha = bounded_download(SOURCE_URL, source)
        metadata = inspect_raster(source)
    receipt = {
        "mission": "MN-GEO-RAIL-001",
        "stage": "R1_single_cog_technical_sample",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "producer": "ESA Copernicus DEM GLO-30 Public via AWS/Sinergise",
        "source_kind": "DSM_not_DTM",
        "source_tile": SOURCE_ID, "source_url": SOURCE_URL,
        "native_asset_bytes": byte_count, "native_asset_sha256": sha,
        "checked_raster_metadata": metadata,
        "validation_scope": "one complete COG, first-band georeferencing and 256x256 centre window",
        "native_asset_retained_in_repository": False,
        "native_asset_preserved_canonically": False,
        "vertical_datum_verified_from_native_file": False,
        "canonical_identity_assigned": False,
        "reuse_publication_clearance": False,
        "canonical_acceptance": False,
        "ready_for_rail_alignment_profiles": False,
        "warnings": [
            "DSM surface includes vegetation and buildings and must not be relabelled as DTM.",
            "One validated tile does not prove full 12-tile coverage or cross-border datum continuity.",
            "Temporary native bytes were removed. This is a provenance/technical-test receipt only."
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({k:receipt[k] for k in ["stage","native_asset_bytes","native_asset_sha256",
                    "native_asset_preserved_canonically","canonical_acceptance"]}))


if __name__ == "__main__":
    main()
