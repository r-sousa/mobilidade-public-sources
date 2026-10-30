#!/usr/bin/env python3
"""Metadata-only Copernicus GLO-30 R1 candidate tile inventory.

This tool never downloads/validates rasters, changes Fxx identity or grants reuse.
The optional producer tileList.txt is discovery evidence, not asset validation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

TILE_RE = re.compile(r"Copernicus_DSM_COG_10_[NS]\\d{2}_00_[EW]\\d{3}_00_DEM")
SOURCE = "https://copernicus-dem-30m.s3.amazonaws.com/readme.html"
TILE_LIST = "https://copernicus-dem-30m.s3.amazonaws.com/tileList.txt"


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        vals = tuple(float(x.strip()) for x in value.split(","))
    except ValueError as exc:
        raise ValueError("bbox must be minlon,minlat,maxlon,maxlat") from exc
    if len(vals) != 4 or not all(math.isfinite(v) for v in vals):
        raise ValueError("bbox must have four finite coordinates")
    west, south, east, north = vals
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("bbox must be ordered within longitude/latitude ranges")
    return vals


def tile_id(lon: int, lat: int) -> str:
    if not (-180 <= lon < 180 and -90 <= lat < 90):
        raise ValueError("invalid 1-degree tile origin")
    north = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00"
    east = f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00"
    return f"Copernicus_DSM_COG_10_{north}_{east}_DEM"


def indexed_tiles(bbox: tuple[float, float, float, float]) -> list[tuple[int, int]]:
    west, south, east, north = bbox
    return [(lon, lat) for lat in range(math.floor(south), math.ceil(north))
            for lon in range(math.floor(west), math.ceil(east))]


def read_available_tile_names(path: Path) -> tuple[set[str], str]:
    data = path.read_bytes()
    names = set(TILE_RE.findall(data.decode("utf-8-sig")))
    if not names:
        raise ValueError("tileList input contains no recognizable GLO-30 tile names")
    return names, hashlib.sha256(data).hexdigest()


def build_inventory(bbox: tuple[float, float, float, float], available: set[str] | None = None,
                    tile_list_sha256: str | None = None) -> dict:
    features = []
    for lon, lat in indexed_tiles(bbox):
        ident = tile_id(lon, lat)
        status = "unverified" if available is None else (
            "listed_not_validated" if ident in available else "not_in_supplied_list")
        features.append({
            "type": "Feature", "id": ident,
            "geometry": {"type": "Polygon", "coordinates": [[
                [lon, lat], [lon + 1, lat], [lon + 1, lat + 1],
                [lon, lat + 1], [lon, lat]]]},
            "properties": {
                "tile_id": ident,
                "source_product": "Copernicus DEM GLO-30 Public",
                "model_class": "DSM_not_DTM",
                "nominal_resolution_m": 30,
                "horizontal_crs": "EPSG:4326",
                "vertical_datum": "EGM2008_EPSG:3855",
                "discovery_status": status,
                "native_raster_acquired": False,
                "native_raster_validated": False,
                "canonical_acceptance": False,
            }})
    counts = {s: sum(1 for f in features if f["properties"]["discovery_status"] == s)
              for s in sorted({f["properties"]["discovery_status"] for f in features})}
    return {"type": "FeatureCollection",
            "metadata": {
                "mission": "MN-GEO-RAIL-001",
                "stage": "R1_candidate_tile_index_only",
                "bbox_wgs84": list(bbox),
                "data_kind": "DSM — not a lidar-derived bare-earth DTM",
                "producer_readme": SOURCE, "producer_tile_list_url": TILE_LIST,
                "supplied_tile_list_sha256": tile_list_sha256,
                "is_coverage_verified": False,
                "native_assets_preserved": 0,
                "tile_count": len(features), "status_counts": counts,
                "note": "Bounding cells are discovery units, not measured raster coverage."},
            "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", required=True, help="minlon,minlat,maxlon,maxlat WGS84")
    parser.add_argument("--tile-list", type=Path, help="Downloaded producer tileList.txt")
    parser.add_argument("--output", type=Path, required=True, help="GeoJSON path")
    args = parser.parse_args()
    try:
        bbox = parse_bbox(args.bbox)
        names, sha = read_available_tile_names(args.tile_list) if args.tile_list else (None, None)
        inventory = build_inventory(bbox, names, sha)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(inventory["metadata"], ensure_ascii=False))


if __name__ == "__main__":
    main()
