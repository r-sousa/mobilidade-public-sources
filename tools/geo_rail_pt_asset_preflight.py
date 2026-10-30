#!/usr/bin/env python3
"""MN-GEO-RAIL-001 W2: anonymous access preflight of 2 DGT native asset records.

Fetches two selected published STAC items for metadata and classifies native
asset links without persisting href, query, credentials or response bodies.
Only for HTTPS DGT-owned hosts with NO query string, issue HEAD with redirects
DISABLED; never GET native bytes or use an authenticated session.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, urlopen
from urllib.error import HTTPError, URLError

API="https://cdd.dgterritorio.gov.pt/dgt-be/v1/search"
SOURCE_WINDOWS={
  "Mirandela": [-7.25,41.45,-7.15,41.55],
  "Amarante": [-8.15,41.22,-8.05,41.32],
}
COLLECTION="MDT-2m"
MAX_META_BYTES=300_000
MAX_ASSETS_PER_ITEM=12
MAX_HEAD_REQUESTS=2


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def public_dgt_host(hostname):
    if not hostname:
        return False
    host=hostname.lower().rstrip(".")
    return host=="dgterritorio.gov.pt" or host.endswith(".dgterritorio.gov.pt")


def anonymous_head_if_safe(href, transport=None):
    parsed=urlparse(href)
    base={"scheme":parsed.scheme,"host":parsed.hostname,"has_query":bool(parsed.query),
          "status":"not_probed","http_status":None,"content_length_bytes":None,
          "content_type":None,"redirect_target_host":None,
          "sent_authentication":False,"native_bytes_downloaded":0}
    if parsed.scheme!="https" or not public_dgt_host(parsed.hostname):
        base["status"]="host_or_scheme_not_approved"
        return base
    if parsed.query or parsed.username or parsed.password or parsed.fragment:
        base["status"]="query_or_credentials_in_link_not_sent"
        return base
    opener=transport or build_opener(NoRedirects())
    try:
        req=Request(href,method="HEAD",headers={"User-Agent":"MN-GEO-RAIL-001-DGT-HEAD/1.0"})
        with opener.open(req,timeout=15) as response:
            base["http_status"]=response.status
            base["content_type"]=response.headers.get("Content-Type")
            n=response.headers.get("Content-Length")
            base["content_length_bytes"]=int(n) if n and n.isdigit() else None
        base["status"]="anonymous_head_200" if base["http_status"]==200 else "head_indeterminate"
    except HTTPError as err:
        base["http_status"]=err.code
        if err.code in (301,302,303,307,308):
            base["status"]="redirect_not_followed"
            location=err.headers.get("Location","")
            base["redirect_target_host"]=urlparse(location).hostname if location else None
        elif err.code in (401,403):
            base["status"]="anonymous_head_access_denied"
        elif err.code==404:
            base["status"]="head_not_found_unverified"
        else:
            base["status"]="head_http_error"
    except (OSError,URLError,TimeoutError):
        base["status"]="head_unverified_error"
    return base


def fetch_candidate(window, opener=urlopen):
    bbox=SOURCE_WINDOWS[window]
    payload={"bbox":bbox,"collections":[COLLECTION],"limit":1}
    req=Request(API,data=json.dumps(payload).encode("utf-8"),method="POST",
                headers={"Accept":"application/json","Content-Type":"application/json",
                         "User-Agent":"MN-GEO-RAIL-001-DGT-asset-metadata/1.0"})
    with opener(req,timeout=25) as res:
        if res.status!=200:
            raise RuntimeError(f"STAC HTTP {res.status}")
        raw=res.read(MAX_META_BYTES+1)
    if len(raw)>MAX_META_BYTES:
        raise ValueError("STAC metadata response too large")
    body=json.loads(raw)
    features=body.get("features",[])
    if not isinstance(features,list) or len(features)!=1:
        raise ValueError("expected one STAC feature")
    feature=features[0]
    if not isinstance(feature,dict) or not isinstance(feature.get("assets"),dict):
        raise ValueError("no assets dictionary")
    return feature,hashlib.sha256(raw).hexdigest()


def probe():
    report={"mission":"MN-GEO-RAIL-001","worker":"W2",
            "stage":"pt_anonymous_native_asset_HEAD_access_preflight",
            "observed_utc":datetime.now(timezone.utc).isoformat(),
            "producer":"DGT Centro de Dados",
            "metadata_only":True,"native_raster_bytes_downloaded":0,
            "no_credentials_used":True,"signed_links_never_persisted":True,
            "no_redirects_followed":True,
            "native_data_quality_validated":False,
            "canonical_acceptance":False,
            "cases":[]}
    for name,bbox in SOURCE_WINDOWS.items():
        item={"diagnostic_window":name,"bbox_wgs84":bbox,
              "collection":COLLECTION,"status":"unverified"}
        try:
            feature,digest=fetch_candidate(name)
            ident=feature.get("id")
            item["item_id"]=ident if isinstance(ident,str) and len(ident)<=160 else None
            item["source_stac_response_sha256"]=digest
            assets=feature["assets"]
            item["asset_count"]=len(assets)
            item["native_asset_candidates"]=[]
            if len(assets)>MAX_ASSETS_PER_ITEM:
                raise ValueError("asset count exceeds inspection cap")
            attempted=0
            for key,meta in sorted(assets.items()):
                if not isinstance(key,str) or not isinstance(meta,dict):
                    continue
                href=meta.get("href")
                if not isinstance(href,str):
                    continue
                roles=meta.get("roles")
                v={"asset_key":key[:80],
                   "reported_media_type":str(meta.get("type") or "")[:100],
                   "roles":roles[:6] if isinstance(roles,list) else []}
                # Do not store links or even paths. HEAD must have vetted host/no query.
                if attempted<MAX_HEAD_REQUESTS:
                    v["preflight"]=anonymous_head_if_safe(href)
                    if v["preflight"]["status"] in (
                            "anonymous_head_200","anonymous_head_access_denied",
                            "redirect_not_followed","head_http_error",
                            "head_not_found_unverified","head_unverified_error"):
                        attempted+=1
                else:
                    v["preflight"]={"status":"head_request_budget_reached"}
                item["native_asset_candidates"].append(v)
            item["status"]="metadata_accessible_asset_preflight_done"
        except Exception as exc:
            item["status"]="metadata_or_asset_preflight_unverified"
            item["error_class"]=type(exc).__name__
        report["cases"].append(item)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=probe()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
                           encoding="utf-8")
    print(json.dumps([{"window":x["diagnostic_window"],"status":x["status"],
        "asset_classes":[(a["asset_key"],a["preflight"]["status"]) for a in x.get("native_asset_candidates",[])]}
        for x in report["cases"]],ensure_ascii=False))
    if any(x["status"]!="metadata_accessible_asset_preflight_done" for x in report["cases"]):
        raise SystemExit("Native asset preflight incomplete; inspect sanitized receipt")


if __name__=="__main__":
    main()
