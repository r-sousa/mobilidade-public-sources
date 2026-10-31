#!/usr/bin/env python3
"""W2: conservative DGT catalogue-envelope continuity audit (metadata only).

The fractions below are unions of WGS84 rectangular *bounding proxies* within
the six search windows, NOT valid MDT pixel coverage, altimetric QA, a corridor,
or rights to download/publish any source file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

COLLECTIONS = ("MDT-2m", "MDT-50cm")
SECTORS = (
    "E01_east_north", "E02_east_south", "E03_macedo_sector",
    "E04_mirandela_sector", "E05_vila_real_sector", "E06_amarante_sector",
)
MAX_INPUT_BYTES = 2_000_000


def bbox(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("invalid_bbox")
    if any(type(x) not in (float, int) or not math.isfinite(x) for x in value):
        raise ValueError("non_finite_bbox")
    w, s, e, n = value
    if not (-11 <= w < e <= -5 and 36 <= s < n <= 43):
        raise ValueError("out_of_scope_bbox")
    return tuple(value)


def clipped(rect, window):
    w, s, e, n = rect
    W, S, E, N = window
    result = (max(w, W), max(s, S), min(e, E), min(n, N))
    return result if result[0] < result[2] and result[1] < result[3] else None


def rectangle_union_fraction(window, rectangles):
    """Exact planar union of rectangles clipped to one small WGS84 window.

    Ratio is in local longitude/latitude degree-squared coordinates, *not*
    geodetic surface area and never raster cell coverage.
    """
    W, S, E, N = window
    clipped_rects = [r for box in rectangles if (r := clipped(box, window))]
    xs = sorted({W, E} | {x for r in clipped_rects for x in (r[0], r[2])})
    total = 0.0
    for left, right in zip(xs, xs[1:]):
        if left == right:
            continue
        mid = (left + right) / 2
        spans = sorted((r[1], r[3]) for r in clipped_rects if r[0] < mid < r[2])
        if not spans:
            continue
        lower, upper = spans[0]
        covered_y = 0.0
        for a, b in spans[1:]:
            if a <= upper:
                upper = max(upper, b)
            else:
                covered_y += upper - lower
                lower, upper = a, b
        covered_y += upper - lower
        total += (right - left) * covered_y
    ratio = total / ((E - W) * (N - S))
    if not (-1e-9 <= ratio <= 1 + 1e-9):
        raise ValueError("invalid_union_fraction")
    return round(max(0.0, min(1.0, ratio)), 6)


def audit(receipt, source_sha256):
    if receipt.get("mission") != "MN-GEO-RAIL-001":
        raise ValueError("unexpected_mission")
    rows = receipt.get("requests")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ValueError("expected_12_sector_collection_queries")
    seen_rows = {}
    for row in rows:
        k = (row.get("box_id"), row.get("collection"))
        if k[0] not in SECTORS or k[1] not in COLLECTIONS or k in seen_rows:
            raise ValueError("unreviewed_or_duplicate_query")
        if row.get("status") != "metadata_returned_one_page" or row.get("has_next_page") is not False or row.get("http_status") != 200:
            raise ValueError("incomplete_or_failed_STAC_query")
        window = bbox(row.get("query_bbox_wgs84"))
        items = row.get("footprints")
        if not isinstance(items, list) or len(items) > 500:
            raise ValueError("invalid_footprints")
        if row.get("metadata_footprint_count") != len(items):
            raise ValueError("inconsistent_metadata_count")
        normalised = {}
        for item in items:
            ident = item.get("tile_id")
            if not isinstance(ident, str) or not ident.startswith(row["collection"] + "-") or len(ident) > 160:
                raise ValueError("unexpected_tile_id")
            rect = bbox(item.get("bbox_wgs84"))
            if clipped(rect, window) is None:
                raise ValueError("tile_outside_query")
            if ident in normalised and normalised[ident] != rect:
                raise ValueError("conflicting_duplicate_tile")
            normalised[ident] = rect
        seen_rows[k] = (window, normalised)

    if set(seen_rows) != {(s, c) for s in SECTORS for c in COLLECTIONS}:
        raise ValueError("missing_sector_or_product")
    sector_rows = []
    total = 0
    for sector in SECTORS:
        win2, tiles2 = seen_rows[(sector, "MDT-2m")]
        win50, tiles50 = seen_rows[(sector, "MDT-50cm")]
        if win2 != win50:
            raise ValueError("product_query_windows_differ")
        suffixes2 = {k.removeprefix("MDT-2m-"): v for k, v in tiles2.items()}
        suffixes50 = {k.removeprefix("MDT-50cm-"): v for k, v in tiles50.items()}
        if suffixes2 != suffixes50:
            raise ValueError("product_catalogue_pairing_differs")
        fraction = rectangle_union_fraction(win2, list(suffixes2.values()))
        total += len(suffixes2)
        sector_rows.append({
            "sector_id": sector,
            "query_window_bbox_wgs84": list(win2),
            "mdt2m_candidate_items": len(tiles2),
            "mdt50cm_candidate_items": len(tiles50),
            "paired_item_suffixes_with_same_bbox": len(suffixes2),
            "window_bbox_proxy_union_fraction": fraction,
            "window_bbox_proxy_uncovered_fraction": round(1 - fraction, 6),
            "measurement": "WGS84 local degree-plane union of catalogue bounding boxes only",
            "native_raster_valid_cell_coverage_verified": False,
        })
    # Differences between *sampled* windows are not evidence of absent data.
    ordered = sorted(sector_rows, key=lambda x: x["query_window_bbox_wgs84"][0])
    separations = []
    for a, b in zip(ordered, ordered[1:]):
        gap = max(0.0, b["query_window_bbox_wgs84"][0] - a["query_window_bbox_wgs84"][2])
        separations.append({
            "west_sample": a["sector_id"], "east_sample": b["sector_id"],
            "unqueried_longitude_interval_degrees": round(gap, 6),
            "does_not_measure_source_data_gap": True,
        })
    return {
        "mission": "MN-GEO-RAIL-001",
        "stage": "W2_six_sample_windows_bbox_proxy_continuity_review",
        "input_source_sha256": source_sha256,
        "input_observed_utc": receipt.get("observed_utc"),
        "source_collection": list(COLLECTIONS),
        "input_complete_queries": 12,
        "candidate_positions_paired_across_resolutions": total,
        "sectors": sector_rows,
        "unsampled_window_separations": separations,
        "valid_raster_pixel_coverage_measured": False,
        "full_corridor_study_envelope_defined": False,
        "full_corridor_coverage_verified": False,
        "metadata_bbox_proxy_not_valid_pixel_coverage": True,
        "canonical_Fxx_accepted": False,
        "site_publication_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise SystemExit("unreviewed_input_size")
    payload = json.loads(raw)
    outcome = audit(payload, hashlib.sha256(raw).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "metadata_review_only",
        "paired_candidate_positions": outcome["candidate_positions_paired_across_resolutions"],
        "sector_proxy_fractions": {x["sector_id"]: x["window_bbox_proxy_union_fraction"] for x in outcome["sectors"]},
        "full_corridor_coverage_verified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
