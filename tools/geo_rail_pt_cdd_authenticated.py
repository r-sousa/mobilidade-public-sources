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
import ipaddress
import re
import socket
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode, urljoin, urlsplit
from datetime import datetime, timezone

from geo_rail_pt_native_intake_qa import audit, MAX_NATIVE_BYTES, stream_sha256

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

    def __init__(self, code, *, phase="not_identified", redirect=None):
        self.code = code
        self.phase = phase
        self.redirect = redirect
        super().__init__(code)


def sanitized_redirect_diagnostic(url):
    """Only DGT-owned hostnames, protocol class and numeric port; never path/query."""
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower().rstrip(".")
        scheme = p.scheme.lower() if p.scheme.lower() in ("https", "http") else "other"
        port = p.port
        if host == "dgterritorio.gov.pt" or host.endswith(".dgterritorio.gov.pt"):
            host_class = host
        else:
            host_class = "outside_DGT_hostname_allowlist"
        return {
            "redirect_hostname_class": host_class,
            "redirect_scheme_class": scheme,
            "redirect_port": port,
        }
    except (ValueError, TypeError):
        return {
            "redirect_hostname_class": "unparseable",
            "redirect_scheme_class": "unparseable",
            "redirect_port": None,
        }


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
    phase="not_identified",
):
    """All redirects checked BEFORE being followed, no arbitrary host/network."""
    if not allowed_url(url, allowed_hosts):
        raise IntakeError("unapproved_https_host_or_url", phase=phase)
    for _ in range(MAX_REDIRECTS+1):
        try:
            response = session.request(
                method, url, data=form, json=json_body,
                headers={"User-Agent": USER_AGENT}, allow_redirects=False,
                stream=stream, timeout=timeout,
            )
        except Exception:
            raise IntakeError("network_request_failed", phase=phase) from None
        status = response.status_code
        if status not in (301, 302, 303, 307, 308):
            return response
        location = response.headers.get("Location")
        if not isinstance(location, str) or not location:
            response.close()
            raise IntakeError("redirect_without_location", phase=phase)
        dest = urljoin(url, location)
        if not allowed_url(dest, allowed_hosts):
            response.close()
            raise IntakeError("unapproved_redirect_destination",
                              phase=phase,
                              redirect=sanitized_redirect_diagnostic(dest))
        response.close()
        if stop_at is not None and not allowed_url(dest, stop_at):
            raise IntakeError("redirect_outside_download_host_allowlist",
                              phase=phase,
                              redirect=sanitized_redirect_diagnostic(dest))
        # RFC semantics: 302/303 after POST are GET navigation.
        if status == 303 or (status in (301, 302) and method == "POST"):
            method, form, json_body = "GET", None, None
        url = dest
    raise IntakeError("too_many_redirects", phase=phase)


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
        with request_bounded_redirects(s,"GET",PORTAL,TRUSTED_AUTH_REDIRECTS,
                                       phase="portal_public_entry") as r:
            if r.status_code!=200:
                raise IntakeError("portal_unavailable")
        q=urlencode({
            "client_id":CLIENT, "response_type":"code",
            "redirect_uri":CALLBACK, "scope":"openid profile email"
        })
        with request_bounded_redirects(s,"GET",LOGIN+"?"+q,TRUSTED_AUTH_REDIRECTS,
                                       phase="keycloak_public_form") as page:
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
                                       form=form,timeout=35,
                                       phase="keycloak_credentials_submission") as done:
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
        session, "POST", STAC, TRUSTED_AUTH_REDIRECTS, json_body=payload,
        stream=True,phase="stac_after_authentication")
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



def verified_public_storage_endpoint(url, *, dns_lookup=None):
    """One CDD-issued storage URL; HTTPS :9000, strictly public IP/DNS.

    Never evaluates URL path or query; they are opaque signed data.
    Forbid all private/loopback/reserved DNS results and embedded credentials.
    This validation is a conservative preflight, not a replacement for TLS
    certificate checks on the actual HTTPS request.
    """
    try:
        p=urlsplit(url)
        host=(p.hostname or "").lower().rstrip(".")
        if (p.scheme!="https" or p.port!=9000 or
            p.username or p.password or p.fragment or not host):
            return False
        if host==DATA_HOST or host==AUTH_HOST:
            return False
        try:
            literal=ipaddress.ip_address(host)
        except ValueError:
            literal=None
        if literal is not None:
            return literal.is_global
        if not re.fullmatch(r"[a-z0-9.-]{4,253}",host):
            return False
        if any(not label or label.startswith("-") or label.endswith("-")
               for label in host.split(".")):
            return False
        if (host=="localhost" or "." not in host or
            host.endswith((".localhost",".local",".internal",".test",
                           ".invalid",".example",".onion"))):
            return False
        if dns_lookup is None:
            dns_lookup=socket.getaddrinfo
        addresses=dns_lookup(host,9000,proto=socket.IPPROTO_TCP)
        if not addresses:
            return False
        return all(ipaddress.ip_address(info[4][0]).is_global for info in addresses)
    except (ValueError, TypeError, OSError):
        return False


def native_response_from_dgt_with_single_storage_hop(session, href):
    """Follow same-host DGT redirects; allow one isolated HTTPS :9000 hop.

    Only DGT-authenticated response may issue the storage link. A fresh,
    cookie-free HTTP session is used for the storage request, so DGT login
    credentials, DGT cookies and Authorization never leave DGT.
    """
    import requests
    if not allowed_url(href,TRUSTED_DATA_REDIRECTS):
        raise IntakeError("unapproved_native_asset_href",
                          phase="native_geotiff_download")
    url=href
    for _ in range(MAX_REDIRECTS+1):
        try:
            result=session.request("GET",url,
                headers={"User-Agent":USER_AGENT},
                stream=True,allow_redirects=False,timeout=60)
        except Exception:
            raise IntakeError("dgt_native_request_failed",
                              phase="native_geotiff_download") from None
        if result.status_code not in (301,302,303,307,308):
            return result,None
        loc=result.headers.get("Location","")
        destination=urljoin(url,loc)
        result.close()
        if allowed_url(destination,TRUSTED_DATA_REDIRECTS):
            url=destination
            continue
        if not verified_public_storage_endpoint(destination):
            raise IntakeError(
                "unapproved_redirect_destination",
                phase="native_geotiff_download",
                redirect=sanitized_redirect_diagnostic(destination))
        # Request URL is an opaque time-limited storage link provided by DGT;
        # it is not logged or stored in any receipt. Do not forward account
        # cookies or headers. Forbid further redirects, including to DGT.
        storage=requests.Session()
        storage.verify=True
        storage.trust_env=False
        storage.headers.clear()
        storage.cookies.clear()
        try:
            response=storage.request("GET",destination,
                headers={"User-Agent":USER_AGENT},
                stream=True,allow_redirects=False,timeout=60)
            if response.status_code in (301,302,303,307,308):
                response.close()
                raise IntakeError("storage_second_redirect_not_allowed",
                                  phase="native_geotiff_download")
            return response,storage
        except IntakeError:
            storage.close()
            raise
        except Exception:
            storage.close()
            raise IntakeError(
                "external_storage_https_or_network_failed",
                phase="native_geotiff_download") from None
    raise IntakeError("too_many_dgt_native_redirects",
                      phase="native_geotiff_download")


def download_native(session, href, destination):
    # No POST credentials ever travel to the data asset. Cookies are
    # managed by requests on the DGT domain. HTTPS verification is ON.
    result,storage_session=native_response_from_dgt_with_single_storage_hop(
        session,href)
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
                    b"II*\x00",b"MM\x00*",b"II+\x00",b"MM\x00+"):
                raise IntakeError("native_response_not_tiff")
        return size,digest.hexdigest()
    finally:
        result.close()
        if storage_session is not None:
            storage_session.close()


def execute(site,source_index, retain_verified_native=None):
    if site not in PILOT_SITES:
        raise IntakeError("unapproved_site")
    if retain_verified_native is not None:
        # Explicit initial release pilot only; unreviewed regions remain disabled.
        if site != "mirandela":
            raise IntakeError("native_release_pilot_only_mirandela")
        target=Path(retain_verified_native)
        if not target.is_absolute() or target.exists() or target.is_symlink():
            raise IntakeError("unsafe_or_existing_native_release_staging_path")
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
        result["native_staged_for_reviewed_public_release"]=False
        if retain_verified_native is not None:
            # Copy only AFTER native SHA, shape, CRS and pixel QA passed.
            # The staging path must be runner-managed; the next step uploads
            # the exact same verified bytes to a prerelease.
            target=Path(retain_verified_native)
            shutil.copyfile(native,target,follow_symlinks=False)
            copied_bytes,copied_sha=stream_sha256(target)
            if copied_bytes!=downloaded_size or copied_sha!=downloaded_sha:
                target.unlink(missing_ok=True)
                raise IntakeError("staged_native_raster_sha256_mismatch")
            result["native_staged_for_reviewed_public_release"]=True
        result["no_login_urls_credentials_cookies_or_signed_hrefs_saved"]=True
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site",choices=tuple(PILOT_SITES),required=True)
    p.add_argument("--index",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--retain-verified-native",type=Path,default=None,
                   help="restricted pilot: stage validated Mirandela GeoTIFF in runner temp for approved release upload")
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
        full=execute(args.site,args.index,args.retain_verified_native)
        report=full
        report["status"]="native_tiff_authenticated_and_validated_pilot"
        status="success"
    except IntakeError as error:
        report["status"]="acquisition_or_native_quality_not_verified"
        report["safe_error_code"]=error.code
        report["safe_error_phase"]=error.phase
        if error.redirect:
            report.update(error.redirect)
    except Exception:
        # Suppress all HTTP errors/exception details, which may contain
        # session tokens or secret URL query parameters.
        report["status"]="acquisition_or_native_quality_not_verified"
        report["safe_error_code"]="unexpected_error_inspect_code_without_logging_secrets"
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+"\n",
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

