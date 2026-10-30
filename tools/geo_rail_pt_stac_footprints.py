#!/usr/bin/env python3
"""W2: bounded anonymous DGT CDD MDT-2m footprint discovery in NE Portugal.

Only public STAC metadata; never downloads rasters or persists asset URLs,
signed links, cookies, authentication tokens or unrestricted STAC properties.
A returned footprint is NOT a verified elevation raster or complete LiDAR
coverage. Non-success/partial pages are retained as observations, not zeros.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL = "https://cdd.dgterritorio.gov.pt/dgt-be/v1/search"
MAX_BYTES_PER_RESPONSE = 2_000_000
LIMIT = 100
# Diagnostic boxes, WGS84; selected to sample alternative east-west sectors
# without defining a rail alignment or implying a rail stop at box centres.
WINDOWS = (
    ("E01_east_north", [-6.90, 41.78, -6.80, 41.88]),
    ("E02_east_south", [-6.92, 41.52, -6.82, 41.62]),
    ("E03_macedo_sector", [-7.08, 41.48, -6.98, 41.58]),
    ("E04_mirandela_sector", [-7.25, 41.45, -7.15, 41.55]),
    ("E05_vila_real_sector", [-7.85, 41.25, -7.75, 41.35]),
    ("E06_amarante_sector", [-8.15, 41.22, -8.05, 41.32]),
)
COLLECTIONS = ("MDT-2m", "MDT-50cm")


def summary(bbox, collection, response: dict) -> dict:
    """Strictly whitelist fields, so private signed STAC links never leak."""
    if response.get("type") != "FeatureCollection":
        raise ValueError("unexpected type instead of GeoJSON FeatureCollection")
    features = response.get("features")
    if not isinstance(features, list) or len(features) > LIMIT:
        raise ValueError("invalid STAC features/limit contract")
    result = []
    for f in features:
        if not isinstance(f, dict):
            continue
        bb = f.get("bbox")
        if bb is None:
            continue
        if not isinstance(bb, list) or len(bb) < 4 or not all(isinstance(v,(int,float)) for v in bb[:4]):
            continue
        x0,y0,x1,y1 = bb[:4]
        if not (-11 <= x0 <= x1 <= -5 and 36 <= y0 <= y1 <= 43):
            continue
        ident = f.get("id")
        if not isinstance(ident, str) or len(ident) > 160:
            continue
        result.append({"tile_id": ident, "bbox_wgs84": bb[:4],
                       "collection": str(f.get("collection", collection))[:50]})
    return {
        "returned_count": len(features),
        "metadata_footprint_count": len(result),
        "has_next_page": any(x.get("rel")=="next" for x in response.get("links",[]) if isinstance(x,dict)),
        "number_matched_reported": response.get("numberMatched") if isinstance(response.get("numberMatched"),int) else None,
        "number_returned_reported": response.get("numberReturned") if isinstance(response.get("numberReturned"),int) else None,
        "footprints": result,
    }


def inspect_window(box_name: str, bbox: list[float], collection: str, transport=urlopen) -> dict:
    if collection not in COLLECTIONS or (box_name, bbox) not in WINDOWS:
        raise ValueError("unreviewed DGT metadata scope")
    payload = {"bbox":bbox,"collections":[collection],"limit":LIMIT}
    r = {"box_id":box_name, "query_bbox_wgs84":bbox,"collection":collection,
         "http_status":None,"status":"unverified","authentication_supplied":False,
         "source_response_sha256":None, "original_native_asset_downloaded":False}
    try:
        request = Request(URL, data=json.dumps(payload).encode("utf-8"), method="POST",
                          headers={"User-Agent":"MN-GEO-RAIL-001-public-inventory/1.0",
                                   "Content-Type":"application/json","Accept":"application/json"})
        with transport(request,timeout=30) as response:
            r["http_status"]=response.status
            raw=response.read(MAX_BYTES_PER_RESPONSE+1)
        if len(raw)>MAX_BYTES_PER_RESPONSE:
            raise ValueError("STAC response exceeds 2MB cap")
        r["source_response_sha256"]=sha256(raw).hexdigest()
        r["response_byte_count"]=len(raw)
        r.update(summary(bbox,collection,json.loads(raw)))
        r["status"]="metadata_returned_partial" if r["has_next_page"] else "metadata_returned_one_page"
    except HTTPError as e:
        r["http_status"]=e.code
        r["status"]="unauthorized_metadata" if e.code in (401,403) else "http_error"
    except (OSError,URLError,TimeoutError,ValueError,json.JSONDecodeError) as e:
        r["status"]="unverified_error"
        r["error_class"]=type(e).__name__
    return r


def run(transport=urlopen):
    rows=[]
    for name,bbox in WINDOWS:
        for collection in COLLECTIONS:
            rows.append(inspect_window(name,bbox,collection,transport=transport))
    return {
        "mission":"MN-GEO-RAIL-001","worker":"W2",
        "stage":"pt_dgt_anonymous_stac_mdt_candidate_footprints",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "source_url":"https://cdd.dgterritorio.gov.pt/",
        "search_url":URL,
        "used_public_anonymous_metadata_only":True,
        "feature_ids_not_source_download_permissions":True,
        "coverage_polygon_verified":False,
        "surface_raster_checked":False,
        "native_assets_preserved":0,
        "canonical_identity_assigned":False,
        "canonical_acceptance":False,
        "window_count":len(WINDOWS),
        "request_count":len(rows),
        "requests":[*rows]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    outcome=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(outcome,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps([{"id":x["box_id"],"source":x["collection"],"http":x["http_status"],
                       "state":x["status"],"items":x.get("returned_count"),
                       "footprints":x.get("metadata_footprint_count"),
                       "has_next":x.get("has_next_page")} for x in outcome["requests"]]))
    if any(x["status"] not in ("metadata_returned_one_page","metadata_returned_partial")
           for x in outcome["requests"]):
        raise SystemExit("At least one DGT metadata window unverified; inspect receipt.")


if __name__=="__main__":main()
