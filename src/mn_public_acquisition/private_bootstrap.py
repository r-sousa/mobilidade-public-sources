from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import tempfile
import urllib.parse
import zipfile
from pathlib import Path

import requests
import yaml

API = "https://api.github.com"
UA = "MobilidadeNorte-PrivateBootstrap/1.0"
PUBLIC_REPO = os.environ.get("GITHUB_REPOSITORY", "r-sousa/mobilidade-public-sources")


def gh_headers(token: str, accept: str = "application/vnd.github+json") -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_json(url: str, token: str) -> dict | list:
    r = requests.get(url, headers=gh_headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(f"GET {url} -> {r.status_code}: {r.text[:500]}")
    return r.json()


def private_file(repo: str, path: str, ref: str, token: str) -> bytes:
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}"
    r = requests.get(url, params={"ref": ref}, headers=gh_headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(f"Private file {path} -> {r.status_code}: {r.text[:500]}")
    obj = r.json()
    if obj.get("type") != "file":
        raise RuntimeError(f"Private content is not a file: {path}")
    return base64.b64decode(obj["content"])


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def release_by_tag(repo: str, tag: str, token: str) -> dict:
    url = f"{API}/repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe='')}"
    r = requests.get(url, headers=gh_headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(f"Release {repo}@{tag} -> {r.status_code}: {r.text[:500]}")
    return r.json()


def download_release_asset(repo: str, asset: dict, token: str, path: Path) -> None:
    url = f"{API}/repos/{repo}/releases/assets/{asset['id']}"
    with requests.get(
        url,
        headers=gh_headers(token, "application/octet-stream"),
        stream=True,
        allow_redirects=True,
        timeout=(30, 1200),
    ) as r:
        if not r.ok:
            raise RuntimeError(
                f"Release asset {asset['name']} -> {r.status_code}: {r.text[:500]}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)


def archive_evidence(path: Path, *, nested_limit: int = 80_000_000) -> dict:
    if not zipfile.is_zipfile(path):
        raise RuntimeError(f"{path.name} is not a ZIP package")
    names: list[str] = []
    text_parts: list[str] = []
    nested_names: list[str] = []
    safe_text_exts = {".json", ".txt", ".csv", ".tsv", ".md", ".yaml", ".yml", ".xml"}

    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts:
                raise RuntimeError(f"Unsafe archive path: {name}")
            names.append(name)
            ext = Path(name).suffix.lower()
            if ext in safe_text_exts and info.file_size <= 2_000_000:
                try:
                    data = z.read(info)[:2_000_000]
                    text_parts.append(data.decode("utf-8", errors="ignore"))
                except Exception:
                    pass
            if ext == ".zip" and info.file_size <= nested_limit:
                try:
                    nested = io.BytesIO(z.read(info))
                    if zipfile.is_zipfile(nested):
                        with zipfile.ZipFile(nested) as nz:
                            nested_names.extend(nz.namelist())
                except Exception:
                    pass

    joined = "\n".join(names + nested_names + text_parts).casefold()
    return {
        "top_level_members": len(names),
        "nested_members": len(nested_names),
        "member_names": names[:200],
        "nested_member_names": nested_names[:200],
        "_search_blob": joined,
    }


def canonical_gate(
    sid: str,
    item: dict,
    private_repo: str,
    private_ref: str,
    token: str,
    candidates: dict,
    ine_licences: dict,
) -> dict:
    candidate_ids = {x["id"] for x in candidates.get("sources", [])}
    if sid not in candidate_ids:
        raise RuntimeError(f"{sid} is not in canonical redistribution candidates")

    manifest_path = f"statistics/source-sets/{sid}/manifest.json"
    manifest = json.loads(private_file(private_repo, manifest_path, private_ref, token))
    rights = manifest.get("rights") or {}
    if rights.get("public_reuse_status") != "verified":
        raise RuntimeError(f"{sid} canonical reuse is not verified")
    gate = str(rights.get("public_redistribution_gate") or "")
    if "ELIGIBLE_FOR_PUBLIC_EXPORT" not in gate:
        raise RuntimeError(f"{sid} canonical redistribution gate is not eligible: {gate}")

    result = {
        "candidate_index": "PASS",
        "canonical_manifest": "PASS",
        "public_reuse_status": rights.get("public_reuse_status"),
        "public_redistribution_gate": gate,
        "licence": rights.get("license"),
    }

    check = item["asset_check"]
    if check == "ine_ccby_package":
        evidence = ine_licences.get(sid)
        if not evidence:
            raise RuntimeError(f"{sid} has no INE licence evidence")
        if evidence.get("license") != "cc-by":
            raise RuntimeError(f"{sid} INE licence is not cc-by")
        indicator = str(item["indicator"])
        if str((evidence.get("harvest") or {}).get("remote_id")) != indicator:
            raise RuntimeError(f"{sid} INE licence evidence indicator mismatch")
        result["licence_evidence"] = {
            "page": evidence.get("page"),
            "license": evidence.get("license"),
            "license_title": evidence.get("license_title"),
            "organization": evidence.get("organization"),
            "remote_id": indicator,
        }
    elif check == "gtfs_cc0_package":
        lic = rights.get("license") or {}
        if str(lic.get("identifier")) != "CC0-1.0":
            raise RuntimeError(f"{sid} canonical GTFS licence is not CC0-1.0")
    elif check == "eurostat_package":
        endpoints = (manifest.get("source") or {}).get("endpoints") or []
        if not any("ec.europa.eu/eurostat/" in str(x) for x in endpoints):
            raise RuntimeError(f"{sid} canonical endpoints do not establish Eurostat origin")
    else:
        raise RuntimeError(f"Unsupported asset check: {check}")

    return result


def asset_gate(path: Path, item: dict) -> dict:
    evidence = archive_evidence(path)
    blob = evidence.pop("_search_blob")
    check = item["asset_check"]

    if check == "eurostat_package":
        token = str(item["product_code"]).casefold()
        if token not in blob:
            raise RuntimeError(
                f"Eurostat package does not expose expected product token {token}"
            )
        detail = {"product_code": item["product_code"], "package_token": "PASS"}
    elif check == "ine_ccby_package":
        token = str(item["indicator"]).casefold()
        if token not in blob:
            raise RuntimeError(f"INE package does not expose indicator token {token}")
        detail = {"indicator": item["indicator"], "package_token": "PASS"}
    elif check == "gtfs_cc0_package":
        required = {"agency.txt", "routes.txt", "stops.txt", "trips.txt", "stop_times.txt"}
        member_basenames = {
            Path(x).name.casefold()
            for x in (evidence["member_names"] + evidence["nested_member_names"])
        }
        missing = sorted(x for x in required if x.casefold() not in member_basenames)
        if missing:
            raise RuntimeError(f"GTFS package missing required files: {missing}")
        detail = {"gtfs_required_members": "PASS"}
    else:
        raise RuntimeError(f"Unsupported asset-level check {check}")

    return {**evidence, **detail, "status": "PASS"}


def public_release_by_tag(tag: str, token: str) -> dict | None:
    url = f"{API}/repos/{PUBLIC_REPO}/releases/tags/{urllib.parse.quote(tag, safe='')}"
    r = requests.get(url, headers=gh_headers(token), timeout=120)
    if r.status_code == 404:
        return None
    if not r.ok:
        raise RuntimeError(f"Public release lookup -> {r.status_code}: {r.text[:500]}")
    return r.json()


def create_public_release(tag: str, name: str, body: str, token: str) -> dict:
    existing = public_release_by_tag(tag, token)
    if existing:
        return existing
    r = requests.post(
        f"{API}/repos/{PUBLIC_REPO}/releases",
        headers=gh_headers(token),
        json={
            "tag_name": tag,
            "target_commitish": os.environ.get("GITHUB_SHA", "main"),
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": True,
            "make_latest": "false",
        },
        timeout=120,
    )
    if not r.ok:
        raise RuntimeError(f"Create public release -> {r.status_code}: {r.text[:500]}")
    return r.json()


def upload_public_asset(release: dict, path: Path, name: str, token: str) -> dict:
    assets = get_json(
        f"{API}/repos/{PUBLIC_REPO}/releases/{release['id']}/assets?per_page=100",
        token,
    )
    expected_sha = sha256_path(path)
    expected_size = path.stat().st_size
    existing = next((x for x in assets if x["name"] == name), None)
    if existing:
        digest = str(existing.get("digest") or "").removeprefix("sha256:")
        if digest and digest != expected_sha:
            raise RuntimeError(f"Existing public asset digest conflict: {name}")
        if int(existing["size"]) != expected_size:
            raise RuntimeError(f"Existing public asset size conflict: {name}")
        return existing

    upload = release["upload_url"].split("{", 1)[0]
    with path.open("rb") as f:
        r = requests.post(
            upload,
            params={"name": name},
            data=f,
            headers={
                **gh_headers(token),
                "Content-Type": "application/octet-stream",
                "Content-Length": str(expected_size),
            },
            timeout=(30, 1800),
        )
    if not r.ok:
        raise RuntimeError(f"Upload public asset {name} -> {r.status_code}: {r.text[:500]}")
    obj = r.json()
    digest = str(obj.get("digest") or "").removeprefix("sha256:")
    if digest and digest != expected_sha:
        raise RuntimeError(f"Uploaded public asset digest mismatch: {name}")
    return obj


def publish_one(
    sid: str,
    item: dict,
    cfg: dict,
    private_token: str,
    public_token: str,
    candidates: dict,
    ine_licences: dict,
    work: Path,
) -> dict:
    private_repo = cfg["private_repository"]
    private_ref = cfg["private_branch"]
    source_tag = cfg["private_release_tag"]

    canonical = canonical_gate(
        sid, item, private_repo, private_ref, private_token, candidates, ine_licences
    )
    release = release_by_tag(private_repo, source_tag, private_token)
    asset = next((x for x in release.get("assets", []) if x["name"] == item["asset"]), None)
    if not asset:
        raise RuntimeError(f"{sid} missing private release asset {item['asset']}")

    api_digest = str(asset.get("digest") or "").removeprefix("sha256:")
    if api_digest and api_digest != item["sha256"]:
        raise RuntimeError(f"{sid} configured digest disagrees with GitHub Release digest")

    local = work / sid / item["asset"]
    download_release_asset(private_repo, asset, private_token, local)
    actual = sha256_path(local)
    if actual != item["sha256"]:
        raise RuntimeError(f"{sid} downloaded digest mismatch")
    if local.stat().st_size != int(asset["size"]):
        raise RuntimeError(f"{sid} downloaded byte-count mismatch")

    asset_check = asset_gate(local, item)
    tag = f"mn-recovered-{sid.lower()}-{actual[:20]}"
    body = (
        f"Recovered from the previously preserved private Mobilidade Norte source package.\n\n"
        f"Source set: {sid}\n\n"
        f"Producer: {item['producer']}\n\n"
        f"Private preservation tag: {source_tag}\n\n"
        f"SHA-256: `{actual}`\n\n"
        "Publication was allowed only after the canonical reuse gate and an asset-level check passed. "
        "This recovery does not change source identity, acceptance or rights state."
    )
    pub = create_public_release(
        tag,
        f"{sid} — recovered preserved public source package",
        body,
        public_token,
    )
    published = upload_public_asset(pub, local, item["asset"], public_token)

    receipt = {
        "schema_version": "1.0.0",
        "source_set_id": sid,
        "recovery_route": "PRIVATE_RELEASE_TO_PUBLIC_RELEASE",
        "private_repository": private_repo,
        "private_release_tag": source_tag,
        "private_release_id": release.get("id"),
        "source_asset": {
            "name": asset["name"],
            "bytes": asset["size"],
            "sha256": actual,
        },
        "canonical_gate": canonical,
        "asset_level_check": asset_check,
        "public_release": {
            "tag": tag,
            "id": pub["id"],
            "url": pub["html_url"],
            "asset_name": published["name"],
            "asset_id": published["id"],
        },
        "rights_disposition": "NO_CANONICAL_RIGHTS_STATE_CHANGE",
    }
    rp = work / sid / "recovery-receipt.json"
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    upload_public_asset(pub, rp, "recovery-receipt.json", public_token)
    return receipt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--source-set", action="append")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    private_token = os.environ.get("MN_PRIVATE_READ_TOKEN", "")
    public_token = os.environ.get("GITHUB_TOKEN", "")
    if not private_token:
        raise SystemExit("MN_PRIVATE_READ_TOKEN_MISSING")
    if not public_token:
        raise SystemExit("GITHUB_TOKEN_MISSING")

    private_repo = cfg["private_repository"]
    private_ref = cfg["private_branch"]
    candidates = json.loads(
        private_file(
            private_repo,
            cfg["policy"]["canonical_candidate_index"],
            private_ref,
            private_token,
        )
    )
    ine_licences = json.loads(
        private_file(
            private_repo,
            "statistics/releases/ine-license-evidence.json",
            private_ref,
            private_token,
        )
    )

    requested = set(args.source_set or [])
    rows = []
    failures = []
    with tempfile.TemporaryDirectory(prefix="mn-private-bootstrap-") as td:
        work = Path(td)
        for sid, item in cfg["items"].items():
            if requested and sid not in requested:
                continue
            if item.get("disposition") == "already_public_direct_source":
                rows.append({"source_set_id": sid, "status": "SKIPPED_ALREADY_PUBLIC_DIRECT_SOURCE"})
                continue
            try:
                receipt = publish_one(
                    sid,
                    item,
                    cfg,
                    private_token,
                    public_token,
                    candidates,
                    ine_licences,
                    work,
                )
                rows.append({
                    "source_set_id": sid,
                    "status": "RECOVERED_AND_PUBLICLY_PRESERVED",
                    "public_release": receipt["public_release"],
                    "sha256": receipt["source_asset"]["sha256"],
                    "bytes": receipt["source_asset"]["bytes"],
                })
            except Exception as e:
                failures.append({"source_set_id": sid, "error": str(e)})
                rows.append({"source_set_id": sid, "status": "FAILED", "error": str(e)})

    output = {
        "schema_version": "1.0.0",
        "private_repository": private_repo,
        "private_release_tag": cfg["private_release_tag"],
        "results": rows,
        "failures": failures,
        "complete": not failures,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
