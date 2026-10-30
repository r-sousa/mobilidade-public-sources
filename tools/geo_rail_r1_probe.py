#!/usr/bin/env python3
"""Bounded producer-metadata probe for MN-GEO-RAIL-001 (no raster downloads).

Fetches the official GLO-30 public tile list and checks only object headers,
then writes a GeoJSON inventory. Neither native raster bytes nor derived
altimetry are acquired. A successful HEAD is *not* a raster quality check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from geo_rail_r1_index import TILE_LIST, TILE_RE, build_inventory, parse_bbox

MAX_LIST_BYTES = 8_000_000
S3_ORIGIN = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"
TIMEOUT_S = 18


def load_primary_index():
    request = Request(TILE_LIST, headers={"User-Agent": "MN-GEO-RAIL-001-metadata-probe/1.0"})
    with urlopen(request, timeout=TIMEOUT_S) as response:
        if response.status != 200:
            raise RuntimeError(f"tileList HTTP {response.status}")
        raw = response.read(MAX_LIST_BYTES + 1)
        source_etag = response.headers.get("ETag")
        source_modified = response.headers.get("Last-Modified")
    if len(raw) > MAX_LIST_BYTES:
        raise RuntimeError("tileList over maximum permitted byte budget")
    names = set(TILE_RE.findall(raw.decode("utf-8-sig")))
    if len(names) < 100:
        raise RuntimeError(f"tileList unexpectedly small/invalid ({len(names)} names)")
    return names, {
        "url": TILE_LIST,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw),
        "listed_tiles_global": len(names),
        "etag": source_etag,
        "last_modified": source_modified,
    }


def probe_head(tile: str) -> dict:
    # The path comes exclusively from the validated tile_id constructor.
    if re.fullmatch(TILE_RE.pattern, tile) is None:
        raise ValueError("untrusted tile identifier")
    url = f"{S3_ORIGIN}/{tile}/{tile}.tif"
    result = {"asset_url": url, "head_http_status": None,
              "head_state": "unverified", "content_length_bytes": None,
              "content_type": None, "etag": None, "last_modified": None}
    try:
        with urlopen(Request(url, method="HEAD"), timeout=TIMEOUT_S) as response:
            result["head_http_status"] = response.status
            result["content_type"] = response.headers.get("Content-Type")
            result["etag"] = response.headers.get("ETag")
            result["last_modified"] = response.headers.get("Last-Modified")
            size = response.headers.get("Content-Length")
            result["content_length_bytes"] = int(size) if size and size.isdigit() else None
            if response.status == 200 and (result["content_length_bytes"] or 0) > 0:
                result["head_state"] = "object_reported_not_validated"
            else:
                result["head_state"] = "head_insufficient_metadata"
    except HTTPError as exc:
        result["head_http_status"] = exc.code
        result["head_state"] = "head_not_found" if exc.code == 404 else "head_failed"
    except (OSError, URLError, TimeoutError) as exc:
        result["head_state"] = "head_failed"
        result["error_class"] = type(exc).__name__
    return result


def run(bbox, names, list_meta, head_probe=probe_head):
    inventory = build_inventory(bbox, names, list_meta["sha256"])
    for feature in inventory["features"]:
        props = feature["properties"]
        if props["discovery_status"] == "listed_not_validated":
            props.update(head_probe(props["tile_id"]))
    states = {}
    for feature in inventory["features"]:
        status = feature["properties"].get("head_state", "not_probed")
        states[status] = states.get(status, 0) + 1
    inventory["metadata"].update({
        "stage": "R1_producer_tile_listing_and_object_head_probe",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "producer_tile_list": list_meta,
        "head_status_counts": states,
        "native_raster_bytes_downloaded": 0,
        "raster_content_validated": False,
        "raster_footprint_validated": False,
        "licence_clearance": "pending_canonical_check",
        "canonical_acceptance": False,
        "is_coverage_verified": False,
        "note": "Tile-list membership and HEAD response alone do not establish valid raster coverage.",
    })
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--skip-head", action="store_true")
    args = parser.parse_args()
    bbox = parse_bbox(args.bbox)
    names, meta = load_primary_index()
    result = run(bbox, names, meta, head_probe=(
        (lambda _: {"head_state": "skipped"}) if args.skip_head else probe_head))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(result["metadata"], ensure_ascii=False))


if __name__ == "__main__":
    main()
