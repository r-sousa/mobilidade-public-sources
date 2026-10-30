#!/usr/bin/env python3
"""CDD -> GitHub Actions authenticated, bounded native MDT intake.

Registered-user pilot. Uses an encrypted GitHub Actions *environment secret*
(username/password), validates HTTPS, rejects redirects to unreviewed hosts,
limits input to two reviewed MDT-2m tiles, and inspects only one GeoTIFF.
No passwords, tokens, cookies, signed hrefs or raw rasters are persisted.
Public GitHub branch stores a sanitized JSON evidence receipt only.

This is a best-effort Keycloak browser-login compatibility client (not an
official DGT machine API); it deliberately fails closed if the CDD flow
changes or requires interactive verification.
"""
from __future__ import annotations
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode, urljoin, urlsplit
from datetime import datetime, timezone

from geo_rail_pt_native_intake_qa import (
    audit, APPROVED_COLLECTIONS, MAX_NATIVE_BYTES,
)

PORTAL = "https://cdd.dgterritorio.gov.pt"
STAC = PORTAL + "/dgt-be/v1/search"
LOGIN = "https://auth.cdd.dgterritorio.gov.pt/realms/dgterritorio/protocol/openid-connect/auth"
CALLBACK = PORTAL + "/auth/callback"
CLIENT = "aai-oidc-dgt"
AUTH_HOST = "auth.cdd.dgterritorio.gov.pt"
DATA_HOST = "cdd.dgterritorio.gov.pt"
TRUSTED_AUTH_REDIRECTS = frozenset((AUTH_HOST, DATA_HOST))
TRUSTED_DATA_REDIRECTS = frozenset((DATA_HOST,))
MAX_REDIRECTS = 9
MAX_STAC_BYTES = 6_000_000
COLLECTION = "MDT-2m"
PILOT_SITES = {
    "mirandela": {
        "bbox": [-7.25, 41.45, -7.15, 41.55],
        "tile_id": "MDT-2m-282510-09-2024",
    },
    "amarante": {
        "bbox": [-8.15, 41.22, -8.05, 41.32],
        "tile_id": "MDT-2m-200484-07-2025",
    },
}
# Public pilot must not automatically publish native bytes.
USER_AGENT = "MobilidadeNorte-DGT-CDDAuthenticated-Pilot/1.0"


class IntakeError(Exception):
    """Generic, non-sensitive error code only. Never include URLs or headers."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def allowed_url(url, allowed_hosts):
    if not isinstance(url, str) or any(c in url for c in ("\r", "\n", "\\", "\x00")):
        return False
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname in allowed_hosts
                and p.port in (None, 443) and not p.username and not p.password
                and not p.fragment)
    except ValueError:
        return False


def request_bounded_redirects(
    session, method, url, allowed_hosts, *,
    timeout=30, form=None, json_body=None, stream=False, stop_at=None,
):
    """All redirects checked BEFORE being followed, no arbitrary host/network."""
    if not allowed_url(url, allowed_hosts):
        raise IntakeError("unapproved_https_host_or_url")
    for _ in range(MAX_REDIRECTS+1):
        try:
            response = session.request(
                method, url, data=form, json=json_body,
                headers={"User-Agent": USER_AGENT}, allow_redirects=False,
                stream=stream, timeout=timeout,
            )
        except Exception:
            raise IntakeError("network_request_failed") from None
        status = response.status_code
        if status not in (301, 302, 303, 307, 308):
            return response
        location = response.headers.get("Location")
        if not isinstance(location, str) or not location:
            response.close()
            raise IntakeError("redirect_without_location")
        dest = urljoin(url, location)
        if not allowed_url(dest, allowed_hosts):
            response.close()
            raise IntakeError("unapproved_redirect_destination")
        response.close()
        if stop_at is not None and not allowed_url(dest, stop_at):
            raise IntakeError("redirect_outside_download_host_allowlist")
        # RFC semantics: 302/303 after POST are GET navigation.
        if status == 303 or (status in (301, 302) and method == "POST"):
            method, form, json_body = "GET", None, None
        url = dest
    raise IntakeError("too_many_redirects")


class KeycloakLoginForm(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.action = None
        self.hidden = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.active = True
            self.action = values.get("action")
        if tag == "input" and self.active and values.get("type") == "hidden":
            key = values.get("name")
            if key:
                self.hidden[key] = values.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = False


def read_metadata(response, max_bytes=MAX_STAC_BYTES):
    try:
        if response.status_code != 200:
            raise IntakeError("stac_http_non_200")
        raw = response.raw.read(max_bytes+1, decode_content=True)
        if len(raw)>max_bytes:
            raise IntakeError("stac_response_too_large")
        try:
            doc=json.loads(raw)
        except (ValueError,UnicodeError):
            raise IntakeError("stac_response_not_json") from None
        return doc,hashlib.sha256(raw).hexdigest()
    finally:
        response.close()


def authenticated_session(username, password):
    import requests
    if not username or not password:
        raise IntakeError("environment_secrets_not_set")
    s = requests.Session()
    s.trust_env = True
    # Default requests CA trust IS REQUIRED. No verify=False, no SSL bypass.
    s.verify = True
    s.headers.update({"Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    try:
        with request_bounded_redirects(s,"GET",PORTAL,TRUSTED_AUTH_REDIRECTS) as r:
            if r.status_code!=200:
                raise IntakeError("portal_unavailable")
        q=urlencode({
            "client_id":CLIENT, "response_type":"code",
            "redirect_uri":CALLBACK, "scope":"openid profile email"
        })
        with request_bounded_redirects(s,"GET",LOGIN+"?"+q,TRUSTED_AUTH_REDIRECTS) as page:
            if page.status_code!=200:
                raise IntakeError("login_form_unavailable")
            parser=KeycloakLoginForm()
            parser.feed(page.text[:300_000])
            action=urljoin(page.url,parser.action or "")
            referer=page.url
        if not parser.action or not allowed_url(action,frozenset((AUTH_HOST,))):
            raise IntakeError("keycloak_form_action_invalid_or_interactive_auth_needed")
        form=dict(parser.hidden)
        form.update(username=username,password=password)
        # NO credential-bearing text, headers, HTML or URLs are logged.
        with request_bounded_redirects(s,"POST",action,TRUSTED_AUTH_REDIRECTS,
                                       form=form,timeout=35) as done:
            if done.status_code!=200 or urlsplit(done.url).hostname!=DATA_HOST:
                raise IntakeError("authentication_not_confirmed_or_mfa_required")
            # A final 200 on CDD is not a guarantee of a usable native download.
            # Authentication is only evidenced once an actual TIFF passes QA.
        return s
    except Exception:
        s.close()
        raise


def find_native_asset(session,site):
    config=PILOT_SITES[site]
    payload={"bbox":config["bbox"],"collections":[COLLECTION],"limit":500}
    response=request_bounded_redirects(
        session, "POST", STAC, TRUSTED_AUTH_REDIRECTS, json_body=payload)
    data,response_sha=read_metadata(response)
    if data.get("type")!="FeatureCollection":
        raise IntakeError("stac_response_not_feature_collection")
    records=data.get("features")
    if not isinstance(records,list) or len(records)>500:
        raise IntakeError("stac_unexpected_feature_count")
    found=[f for f in records if isinstance(f,dict)
           and f.get("id")==config["tile_id"]]
    if len(found)!=1:
        raise IntakeError("expected_reviewed_tile_not_found")
    feature=found[0]
    if feature.get("collection")!=COLLECTION:
        raise IntakeError("wrong_tile_collection")
    assets=feature.get("assets")
    if not isinstance(assets,dict) or not isinstance(assets.get("data"),dict):
        raise IntakeError("native_data_asset_missing")
    asset=assets["data"]
    mime=str(asset.get("type") or "")
    if not mime.lower().startswith(("image/tiff", "image/geotiff")):
        raise IntakeError("native_asset_not_tiff_media_type")
    href=asset.get("href")
    if not allowed_url(href,TRUSTED_DATA_REDIRECTS):
        raise IntakeError("unapproved_native_asset_href")
    # Never persist href even if it contains an access signature.
    return href,response_sha


def download_native(session, href, destination):
    # No POST credentials ever travel to the data asset. Cookies are
    # managed by requests on the DGT domain. HTTPS verification is ON.
    result=request_bounded_redirects(
        session,"GET",href,TRUSTED_DATA_REDIRECTS,stream=True,timeout=60,
        stop_at=TRUSTED_DATA_REDIRECTS)
    size=0
    digest=hashlib.sha256()
    try:
        if result.status_code != 200:
            raise IntakeError("native_asset_not_http_200")
        content_type=(result.headers.get("Content-Type") or "").lower()
        if ("html" in content_type or "json" in content_type
                or "xml" in content_type):
            raise IntakeError("native_response_is_html_or_api_error")
        declared=result.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared)>MAX_NATIVE_BYTES:
            raise IntakeError("native_asset_exceeds_budget")
        with destination.open("xb") as output:
            for block in result.iter_content(chunk_size=512*1024):
                if not block: continue
                size+=len(block)
                if size>MAX_NATIVE_BYTES:
                    raise IntakeError("native_asset_exceeds_budget")
                output.write(block)
                digest.update(block)
        if size<1024:
            raise IntakeError("native_tiff_unexpectedly_small")
        with destination.open("rb") as fd:
            if fd.read(4) not in (
                    b"II*\\x00",b"MM\\x00*",b"II+\\x00",b"MM\\x00+"):
                raise IntakeError("native_response_not_tiff")
        return size,digest.hexdigest()
    finally:
        result.close()


def execute(site,source_index):
    if site not in PILOT_SITES:
        raise IntakeError("unapproved_site")
    username=os.environ.get("DGT_CDD_USERNAME","")
    password=os.environ.get("DGT_CDD_PASSWORD","")
    if not username or not password:
        raise IntakeError("environment_secrets_not_set")
    with TemporaryDirectory(prefix="mn-cdd-registered-") as tmp:
        session=authenticated_session(username,password)
        try:
            href,stac_sha=find_native_asset(session,site)
            native=Path(tmp)/"native.tif"
            downloaded_size,downloaded_sha=download_native(session,href,native)
        finally:
            session.close()
        # This call streams pixels in-memory by blocks, validates the real
        # raster and emits a sanitized receipt (never the native file).
        result=audit(
            native,source_index,PILOT_SITES[site]["tile_id"],COLLECTION)
        if result["native_file_bytes"]!=downloaded_size or result["native_sha256"]!=downloaded_sha:
            raise IntakeError("stream_and_intake_checksums_disagree")
        result["stage"]="pt_dgt_CDD_environment_secret_authenticated_direct_pilot"
        result["acquisition_method"]="HTTPS_Keycloak_registered_GitHub_Environment"
        result["auth_source"]="GitHub environment secret (values excluded)"
        result["authenticated_native_download_evidenced_by_valid_tiff"]=True
        result["source_stac_response_sha256"]=stac_sha
        result["diagnostic_site"]=site
        result["data_did_not_pass_via_user_device"]=True
        result["native_file_preserved_after_runner_exit"]=False
        result["native_file_release_published"]=False
        result["no_login_urls_credentials_cookies_or_signed_hrefs_saved"]=True
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site",choices=tuple(PILOT_SITES),required=True)
    p.add_argument("--index",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    args=p.parse_args()
    status="not_attempted"
    report={
        "mission":"MN-GEO-RAIL-001","worker":"W2",
        "stage":"pt_dgt_registered_direct_pilot",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "diagnostic_site":args.site,
        "collection":COLLECTION,
        "producer_tile_id":PILOT_SITES[args.site]["tile_id"],
        "status":"unverified",
        "no_native_bytes_or_credentials_in_receipt":True,
        "canonical_acceptance":False,
        "site_publication_authorized":False,
    }
    try:
        if not args.index.is_file():
            raise IntakeError("reviewed_source_index_missing")
        full=execute(args.site,args.index)
        report=full
        report["status"]="native_tiff_authenticated_and_validated_pilot"
        status="success"
    except IntakeError as error:
        report["status"]="acquisition_or_native_quality_not_verified"
        report["safe_error_code"]=error.code
    except Exception:
        # Suppress all HTTP errors/exception details, which may contain
        # session tokens or secret URL query parameters.
        report["status"]="acquisition_or_native_quality_not_verified"
        report["safe_error_code"]="unexpected_error_inspect_code_without_logging_secrets"
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+"\\n",
                            encoding="utf-8")
    print(json.dumps({
        "status":report["status"],"site":args.site,
        "native_bytes":report.get("native_file_bytes",0),
        "safe_error_code":report.get("safe_error_code"),
        "receipt":str(args.receipt),
    },ensure_ascii=False))
    if status!="success":
        raise SystemExit(1)


if __name__=="__main__":
    main()

