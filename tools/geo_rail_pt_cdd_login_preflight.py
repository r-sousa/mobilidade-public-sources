#!/usr/bin/env python3
"""Anonymous, read-only verification of CDD Keycloak entry point.

Never submits username/password, never tries to download native assets and
never persists HTML/cookies/form URL or any hidden form field values.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

from geo_rail_pt_cdd_authenticated import (
    PORTAL, LOGIN, CALLBACK, CLIENT, AUTH_HOST,
    TRUSTED_AUTH_REDIRECTS, KeycloakLoginForm,
    allowed_url, request_bounded_redirects, IntakeError
)


def run():
    import requests
    receipt={"mission":"MN-GEO-RAIL-001","worker":"W2",
             "stage":"CDD_anonymous_login_form_https_preflight",
             "observed_utc":datetime.now(timezone.utc).isoformat(),
             "source":"https://cdd.dgterritorio.gov.pt/",
             "submitted_credentials":False,
             "executed_login_post":False,
             "stored_html_cookie_form_action_or_token":False,
             "native_bytes_downloaded":0,
             "status":"unverified"}
    s=requests.Session()
    s.verify=True
    try:
        with request_bounded_redirects(s,"GET",PORTAL,TRUSTED_AUTH_REDIRECTS) as home:
            receipt["portal_http_status"]=home.status_code
            if home.status_code!=200:
                raise IntakeError("portal_get_failed")
        q=urlencode({"client_id":CLIENT,"response_type":"code",
                     "redirect_uri":CALLBACK,"scope":"openid profile email"})
        with request_bounded_redirects(s,"GET",LOGIN+"?"+q,TRUSTED_AUTH_REDIRECTS) as login:
            receipt["login_http_status"]=login.status_code
            receipt["login_result_hostname"]=urlsplit(login.url).hostname
            if login.status_code!=200:
                raise IntakeError("login_get_failed")
            p=KeycloakLoginForm()
            p.feed(login.text[:300_000])
            action=urljoin(login.url,p.action or "")
            receipt["keycloak_login_form_detected"]=bool(p.action)
            receipt["form_action_is_trusted_https_auth_host"]=bool(
                p.action and allowed_url(action,frozenset((AUTH_HOST,))))
            receipt["hidden_field_names_count"]=len(p.hidden)
            if not receipt["form_action_is_trusted_https_auth_host"]:
                raise IntakeError("login_form_missing_or_untrusted")
        receipt["status"]="anonymous_https_form_preflight_passed"
    except IntakeError as e:
        receipt["status"]="anonymous_https_form_preflight_failed"
        receipt["safe_error_code"]=e.code
    except Exception:
        receipt["status"]="anonymous_https_form_preflight_failed"
        receipt["safe_error_code"]="unexpected_error_no_details_logged"
    finally:
        s.close()
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    receipt=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
                           encoding="utf-8")
    print(json.dumps({"status":receipt["status"],
                      "keycloak_form":receipt.get("keycloak_login_form_detected"),
                      "auth_host_verified":receipt.get("form_action_is_trusted_https_auth_host"),
                      "error":receipt.get("safe_error_code")},ensure_ascii=False))
    if receipt["status"]!="anonymous_https_form_preflight_passed":
        raise SystemExit(1)


if __name__=="__main__":
    main()
