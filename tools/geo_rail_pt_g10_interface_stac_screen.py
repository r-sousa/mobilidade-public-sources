#!/usr/bin/env python3
"""W2: bounded anonymous STAC screen of interface between G08 Porto–Vila Real and G07 Vila Real–Mirandela.

Two rectangles bridge a documented STAC REVIEW-GRID gap, not a rail line or a certified
route corridor. No account, raster, signed asset URL, cookies, or tokens.
No absence of data may be inferred from a failed or partial STAC page.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from geo_rail_pt_stac_footprints import COLLECTIONS, LIMIT, MAX_BYTES_PER_RESPONSE, URL, summary

# Screen the unqueried 0.10 degree longitude G08/G07 interface, as a bounded review rectangle.
# Two latitude bands, not an assumed railway centreline or full coverage map.
LON_EDGES = (-7.85,-7.75)
LAT_BANDS = ((41.20,41.30),(41.30,41.40))
WINDOWS = tuple(
    (f"G10_{col+1:02d}_{band+1:02d}",
     [LON_EDGES[col], LAT_BANDS[band][0], LON_EDGES[col+1], LAT_BANDS[band][1]])
    for col in range(len(LON_EDGES)-1) for band in range(len(LAT_BANDS))
)
EXPECTED_QUERIES = len(WINDOWS) * len(COLLECTIONS)
assert EXPECTED_QUERIES == 4


def inspect(window_id, window, collection, transport=urlopen):
    if (window_id, window) not in WINDOWS or collection not in COLLECTIONS:
        raise ValueError("out_of_review_scope")
    result = {
        "window_id": window_id,
        "query_bbox_wgs84": window,
        "collection": collection,
        "http_status": None,
        "status": "not_checked",
        "authenticated": False,
        "native_assets_downloaded": 0,
        "stac_sha256": None,
    }
    request = Request(
        URL,
        data=json.dumps({"bbox":window,"collections":[collection],"limit":LIMIT}).encode("utf-8"),
        headers={
            "User-Agent": "MN-GEO-RAIL-001-G10-interface-metadata-only/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with transport(request, timeout=30) as response:
            result["http_status"] = response.status
            if response.status != 200:
                raise ValueError("non_success_status")
            raw = response.read(MAX_BYTES_PER_RESPONSE + 1)
        if len(raw) > MAX_BYTES_PER_RESPONSE:
            raise ValueError("response_size_cap")
        result["stac_sha256"] = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw)
        safe = summary(window, collection, data)
        # Only whitelisted geometry and aggregated diagnostics; no STAC assets.
        for key in ("footprints", "returned_count", "metadata_footprint_count",
                    "has_next_page", "number_matched_reported",
                    "number_returned_reported", "whitelist_rejection_counts"):
            result[key] = safe[key]
        result["status"] = "metadata_partial_next_page" if safe["has_next_page"] else "metadata_complete_single_page"
    except HTTPError as e:
        result["http_status"] = e.code
        result["status"] = "unauthorized" if e.code in (401, 403) else "http_error"
    except (URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        result["status"] = "failed_closed"
        result["error_class"] = type(e).__name__
    return result


def aggregate(rows):
    if len(rows) != EXPECTED_QUERIES or {
        (r["window_id"], r["collection"]) for r in rows
    } != {(w[0], c) for w in WINDOWS for c in COLLECTIONS}:
        raise ValueError("incomplete_review_grid")
    complete = all(r["status"] == "metadata_complete_single_page" for r in rows)
    samples = {}
    per_window = []
    for window_id, window in WINDOWS:
        pairs = []
        for c in COLLECTIONS:
            record = next(r for r in rows if r["window_id"] == window_id and r["collection"] == c)
            count = record.get("metadata_footprint_count")
            pairs.append({"collection": c, "items": count, "complete": record["status"] == "metadata_complete_single_page"})
            if not complete:
                continue
            for item in record["footprints"]:
                ident = item["tile_id"]
                rect = item["bbox_wgs84"]
                if not isinstance(ident,str) or not ident.startswith(c+"-") or len(ident) > 160:
                    raise ValueError("unexpected_tile_identity")
                k = (c, ident)
                if k in samples and samples[k] != rect:
                    raise ValueError("conflicting_cross_window_bbox")
                samples[k] = rect
        per_window.append({"window_id": window_id, "bbox_wgs84": window,
                           "collections": pairs,
                           "metadata_only": True, "native_coverage_verified": False})
    groups = {}
    if complete:
        for c in COLLECTIONS:
            groups[c] = {key.removeprefix(c+"-"): val
                         for (source, key), val in samples.items() if source == c}
    matches = (set(groups.get("MDT-2m", {})) & set(groups.get("MDT-50cm", {}))) if complete else set()
    exact = sum(groups["MDT-2m"][k] == groups["MDT-50cm"][k] for k in matches) if complete else None
    return {
        "mission": "MN-GEO-RAIL-001", "worker": "W2",
        "stage": "G10_G08_G07_interface_anonymous_STAC_gap_screen",
        "review_strip_bbox_wgs84": [-7.85, 41.20, -7.75, 41.40],
        "grid_window_count": len(WINDOWS),
        "query_count": len(rows),
        "queries_all_complete": complete,
        "discovery_mode": "anonymous_public_STAC_metadata_only",
        "windows": per_window,
        "responses": rows,
        "unique_candidate_ids_by_collection": ({c:len(v) for c,v in groups.items()} if complete else None),
        "paired_candidate_id_suffixes": len(matches) if complete else None,
        "paired_bboxes_equal": exact if complete else None,
        "not_a_chosen_rail_alignment": True,
        "not_full_Portugal_geographical_CDD_coverage": True,
        "rectangles_not_valid_pixel_coverage": True,
        "continuous_native_MDT_verified": False,
        "canonical_Fxx_accepted": False,
        "site_publication_authorized": False,
        "source_raster_bytes_transferred": 0,
        "sensitive_urls_persisted": False,
    }


def run(transport=urlopen):
    return aggregate([
        inspect(name, box, collection, transport)
        for name, box in WINDOWS for collection in COLLECTIONS
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "all_complete" if result["queries_all_complete"] else "incomplete",
                      "queries": result["query_count"],
                      "unique_candidates": result["unique_candidate_ids_by_collection"],
                      "paired_bboxes_equal": result["paired_bboxes_equal"]}))
    if not result["queries_all_complete"]:
        raise SystemExit("One or more public STAC windows incomplete; do not extrapolate coverage.")


if __name__ == "__main__":
    main()
