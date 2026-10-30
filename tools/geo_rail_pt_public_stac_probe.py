#!/usr/bin/env python3
"""W2 public metadata-only DGT STAC access probe (NO CDD login).

Unauthenticated GET collections / POST bounded search. Never saves source
asset URLs, signed downloads, cookies or raster bytes. HTTP 401/403 is a
controlled-access observation, NOT evidence of missing geographic coverage.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://cdd.dgterritorio.gov.pt/dgt-be/v1"
MAX_RESPONSE_BYTES = 2_000_000
SEARCH_BBOX = [-7.2, 41.6, -6.8, 41.9]  # Exploratory PT frontier-region window (WGS84)


def call_api(method: str, suffix: str, payload: dict | None = None) -> dict:
    assert method in ("GET", "POST")
    assert suffix in ("/collections", "/search")
    data = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
    headers = {"Accept": "application/json", "User-Agent": "MN-GEO-RAIL-001-public-metadata-probe/1.0"}
    if data:
        headers["Content-Type"] = "application/json"
    outcome = {"method": method, "path": suffix, "status": "unverified", "http_status": None,
               "bytes_read": None, "response_sha256": None, "collection_ids": None,
               "returned_features_count": None, "authentication_supplied": False}
    try:
        request = Request(BASE + suffix, data=data, headers=headers, method=method)
        with urlopen(request, timeout=20) as response:
            outcome["http_status"] = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        outcome["bytes_read"] = len(raw)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("response over bounded metadata budget")
        outcome["response_sha256"] = hashlib.sha256(raw).hexdigest()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("unexpected non-object JSON")
        if isinstance(value.get("collections"), list):
            outcome["collection_ids"] = sorted(set(
                x["id"] for x in value["collections"]
                if isinstance(x, dict) and isinstance(x.get("id"), str)))[:100]
        if isinstance(value.get("features"), list):
            outcome["returned_features_count"] = len(value["features"])
            # Never serialize their asset URLs, signatures, or raw properties.
            outcome["returned_collection_counts"] = {}
            for feature in value["features"]:
                if isinstance(feature, dict):
                    c = str(feature.get("collection", "unknown"))
                    if len(c) <= 100:
                        outcome["returned_collection_counts"][c] = (
                            outcome["returned_collection_counts"].get(c, 0) + 1)
        outcome["status"] = "public_metadata_read"
    except HTTPError as exc:
        outcome["http_status"] = exc.code
        outcome["status"] = ("unauthenticated_access_denied"
                             if exc.code in (401, 403) else "http_error_not_coverage_absence")
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        outcome["status"] = "unverified_error"
        outcome["error_class"] = type(exc).__name__
    return outcome


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    attempts = [
        call_api("GET", "/collections"),
        call_api("POST", "/search",
                 {"bbox": SEARCH_BBOX, "collections": ["MDT-2m"], "limit": 1}),
    ]
    receipt = {
        "mission": "MN-GEO-RAIL-001", "worker": "W2",
        "stage": "pt_dgt_cdd_public_stac_access_only",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "producer": "Direcao-Geral do Territorio, CDD (Portugal)",
        "tested_bbox_wgs84": SEARCH_BBOX,
        "endpoint_discovered_from": "https://github.com/qgispt/dgtcd_downer",
        "source_access_policy": "No account, token, cookie, login or TLS bypass supplied",
        "did_not_download_native_elevation": True,
        "coverage_not_proven_when_access_denied": True,
        "canonical_acceptance": False,
        "attempts": attempts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps([{"path": a["path"], "http": a["http_status"], "status": a["status"],
                       "collections": a["collection_ids"],
                       "feature_count": a["returned_features_count"]} for a in attempts]))


if __name__ == "__main__":
    main()
