#!/usr/bin/env python3
"""Anonymous audit of DGT CDD native-data redirect authority, no credentials.

Read-only: a bounded public STAC POST + one HEAD with allow_redirects=False,
never GET native bytes, never follow a redirect or send cookies/tokens.
Persist only the redirect hostname, HTTPS scheme, port and status. Never
store location path/query, signed asset URLs, session values or headers.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime, timezone

STAC = "https://cdd.dgterritorio.gov.pt/dgt-be/v1/search"
SITE = [-7.25, 41.45, -7.15, 41.55]
TARGET = "MDT-2m-282510-09-2024"
MAX_RESPONSE_BYTES = 5_000_000


def public_hostname(url):
    try:
        p = urlsplit(url)
        if not p.hostname or p.username or p.password or p.fragment:
            return None
        host = p.hostname.lower().rstrip(".")
        if p.scheme != "https" or p.port not in (None,443):
            return None
        if host != "cdd.dgterritorio.gov.pt":
            return None
        return host
    except ValueError:
        return None


def host_safety_class(host):
    try:
        ip=ipaddress.ip_address(host)
        return "public_ip" if ip.is_global else "nonpublic_ip"
    except ValueError:
        h=host.lower().rstrip(".")
        if h=="localhost" or not h or "." not in h:
            return "nonpublic_or_invalid_hostname"
        if h.endswith((".local",".internal",".localhost",".test",".invalid",".example")):
            return "nonpublic_or_invalid_hostname"
        return "dns_hostname"


def run():
    import requests
    out = {
        "mission":"MN-GEO-RAIL-001","worker":"W2",
        "stage":"public_anonymous_DGT_native_redirect_host_audit",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "source_host":"cdd.dgterritorio.gov.pt",
        "target_collection":"MDT-2m","target_id":TARGET,
        "request_method":"one_STAC_POST_and_one_asset_HEAD_without_redirect",
        "submitted_credentials":False,"native_bytes_downloaded":0,
        "redirect_followed":False,"cookies_tokens_query_paths_stored":False,
        "status":"unverified"
    }
    s=requests.Session()
    s.trust_env=True
    s.verify=True
    try:
        meta=s.post(STAC,json={"bbox":SITE,"collections":["MDT-2m"],"limit":300},
                    timeout=30,allow_redirects=False,stream=True)
        out["stac_http_status"]=meta.status_code
        if meta.status_code!=200:
            out["status"]="stac_non_200"
            return out
        with meta:
            raw=meta.raw.read(MAX_RESPONSE_BYTES+1,decode_content=True)
        if len(raw)>MAX_RESPONSE_BYTES:
            out["status"]="stac_too_large"
            return out
        d=json.loads(raw)
        found=[f for f in d.get("features",[]) if f.get("id")==TARGET]
        if len(found)!=1:
            out["status"]="target_id_missing_or_ambiguous"
            return out
        a=found[0].get("assets",{}).get("data",{})
        href=a.get("href","")
        if public_hostname(href)!="cdd.dgterritorio.gov.pt":
            out["status"]="source_asset_host_unapproved"
            return out
        head=s.head(href,timeout=30,allow_redirects=False,stream=True)
        out["asset_head_http_status"]=head.status_code
        loc=head.headers.get("Location","")
        head.close()
        if not loc or out["asset_head_http_status"] not in (301,302,303,307,308):
            out["status"]="no_redirect_in_anonymous_head"
            return out
        p=urlsplit(loc)
        hostname=p.hostname.lower().rstrip(".") if p.hostname else ""
        out["redirect_destination_scheme"]=(p.scheme if p.scheme in ("http","https") else "other")
        out["redirect_destination_port"]=p.port
        out["redirect_destination_hostname"]=hostname
        out["redirect_destination_host_class"]=host_safety_class(hostname)
        out["redirect_location_has_query"]=bool(p.query)
        out["status"]="observed_redirect_without_following"
        return out
    except Exception:
        out["status"]="audit_error_no_sensitive_details_logged"
        return out
    finally:
        s.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    result=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
                      "redirect_destination_hostname":result.get("redirect_destination_hostname"),
                      "redirect_destination_port":result.get("redirect_destination_port"),
                      "redirect_destination_scheme":result.get("redirect_destination_scheme")},
                     ensure_ascii=False))
    if result["status"] not in ("observed_redirect_without_following",
                                "no_redirect_in_anonymous_head"):
        raise SystemExit(1)


if __name__=="__main__":
    main()
