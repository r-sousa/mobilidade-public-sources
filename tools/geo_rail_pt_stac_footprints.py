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
MAX_BYTES_PER_RESPONSE = 6_000_000
LIMIT = 500
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


def geojson_bounds(geometry: dict | None):
    """Only accept GeoJSON polygons with plausible PT WGS84 positions."""
    if not isinstance(geometry,dict) or geometry.get("type") not in ("Polygon","MultiPolygon"):
        return None
    points=[]
    def visit(node,depth=0):
        if depth>9 or len(points)>10000 or not isinstance(node,list):
            return
        if len(node)>=2 and all(isinstance(z,(int,float)) and not isinstance(z,bool) for z in node[:2]):
            lon,lat=node[:2]
            if not (-11 <= lon <= -5 and 36 <= lat <= 43):
                raise ValueError("GeoJSON coordinates outside PT WGS84 expected range")
            points.append((lon,lat))
        else:
            for child in node:
                visit(child,depth+1)
    try:
        visit(geometry.get("coordinates"))
    except ValueError:
        return None
    if len(points)<4 or len(points)>10000:
        return None
    return [min(x for x,y in points),min(y for x,y in points),
            max(x for x,y in points),max(y for x,y in points)]


def is_wgs84_bbox(bbox):
    return (isinstance(bbox,list) and len(bbox)>=4 and
            all(isinstance(z,(int,float)) and not isinstance(z,bool) for z in bbox[:4]) and
            -11 <= bbox[0] <= bbox[2] <= -5 and 36 <= bbox[1] <= bbox[3] <= 43)


def intersects(a,b):
    return not (a[2]<b[0] or a[0]>b[2] or a[3]<b[1] or a[1]>b[3])


def summary(bbox, collection, response: dict) -> dict:
    """Strictly whitelist fields, so private signed STAC links never leak."""
    if response.get("type") != "FeatureCollection":
        raise ValueError("unexpected type instead of GeoJSON FeatureCollection")
    features = response.get("features")
    if not isinstance(features, list) or len(features) > LIMIT:
        raise ValueError("invalid STAC features/limit contract")
    result=[]
    diagnostics={"missing_bbox":0,"bad_bbox":0,"source_bbox_not_wgs84":0,
                 "geometry_recovered":0,"geometry_invalid":0,
                 "not_intersecting_requested_window":0,"missing_or_long_id":0}
    example=None
    for f in features:
        if not isinstance(f,dict):
            continue
        bb=f.get("bbox")
        if example is None:
            example={"top_level_keys":sorted(str(k) for k in f.keys())[:30],
                     "bbox_first_four_numbers":(bb[:4] if isinstance(bb,list) and len(bb)>=4 and all(isinstance(z,(int,float)) for z in bb[:4]) else None),
                     "geometry_type":(f.get("geometry") or {}).get("type") if isinstance(f.get("geometry"),dict) else None,
                     "geometry_bbox":geojson_bounds(f.get("geometry"))}
        origin="source_bbox"
        if not is_wgs84_bbox(bb):
            if bb is None: diagnostics["missing_bbox"]+=1
            elif isinstance(bb,list) and len(bb)>=4: diagnostics["source_bbox_not_wgs84"]+=1
            else: diagnostics["bad_bbox"]+=1
            bb=geojson_bounds(f.get("geometry"))
            origin="geometry_recovered"
            if bb is None:
                diagnostics["geometry_invalid"]+=1
                continue
            diagnostics["geometry_recovered"]+=1
        else:
            bb=bb[:4]
        if not intersects(bb,bbox):
            diagnostics["not_intersecting_requested_window"]+=1
            continue
        ident=f.get("id")
        if not isinstance(ident,str) or len(ident)>160:
            diagnostics["missing_or_long_id"]+=1
            continue
        result.append({"tile_id":ident,"bbox_wgs84":bb[:4],
                       "bbox_method":origin,
                       "collection":str(f.get("collection",collection))[:50]})
    return {
        "returned_count": len(features),
        "metadata_footprint_count": len(result),
        "has_next_page": any(x.get("rel")=="next" for x in response.get("links",[]) if isinstance(x,dict)),
        "number_matched_reported": response.get("numberMatched") if isinstance(response.get("numberMatched"),int) else None,
        "number_returned_reported": response.get("numberReturned") if isinstance(response.get("numberReturned"),int) else None,
        "footprints": result,
        "whitelist_rejection_counts":diagnostics,
        "first_record_safe_shape":example,
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
            raise ValueError("STAC response exceeds 6MB cap")
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
