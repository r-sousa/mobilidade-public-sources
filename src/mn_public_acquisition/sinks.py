from __future__ import annotations
import base64
import hashlib
import json
import os
import urllib.parse
from pathlib import Path

import requests

API = "https://api.github.com"
PRIVATE_REPO = "r-sousa/EU-transp-weekly"
PRIVATE_BRANCH = "mobilidade-norte-recovery-20260919"
UA = "MobilidadeNorte-PublicAcquisition/0.1"


def headers(token: str, accept: str = "application/vnd.github+json") -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28"
    }


def req(method: str, url: str, token: str, **kwargs) -> requests.Response:
    h = headers(token)
    h.update(kwargs.pop("headers", {}))
    r = requests.request(method, url, headers=h, timeout=600, **kwargs)
    if not r.ok:
        raise RuntimeError(
            f"GitHub API {method} {url} -> {r.status_code}: {r.text[:500]}"
        )
    return r


def release_for_tag(repo: str, tag: str, token: str):
    r = requests.get(
        f"{API}/repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe='')}",
        headers=headers(token), timeout=90
    )
    if r.status_code == 404:
        return None
    if not r.ok:
        raise RuntimeError(f"GitHub release lookup failed: {r.status_code} {r.text[:500]}")
    return r.json()


def create_release(repo: str, tag: str, token: str, *, target: str, name: str, body: str):
    existing = release_for_tag(repo, tag, token)
    if existing:
        return existing
    return req(
        "POST", f"{API}/repos/{repo}/releases", token,
        json={
            "tag_name": tag,
            "target_commitish": target,
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": True,
            "make_latest": "false"
        }
    ).json()


def hash_stream_response(r: requests.Response) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    for chunk in r.iter_content(1024 * 1024):
        if chunk:
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def verify_asset(repo: str, asset: dict, token: str, expected_sha: str, expected_size: int) -> None:
    r = requests.get(
        f"{API}/repos/{repo}/releases/assets/{asset['id']}",
        headers=headers(token, "application/octet-stream"),
        timeout=600, stream=True, allow_redirects=True
    )
    if not r.ok:
        raise RuntimeError(f"Cannot verify release asset {asset['name']}: {r.status_code}")
    got_sha, got_size = hash_stream_response(r)
    if got_sha != expected_sha or got_size != expected_size:
        raise RuntimeError(f"Release asset digest mismatch: {asset['name']}")


def upload_or_verify(
    repo: str, release: dict, path: Path, name: str, token: str,
    sha: str, size: int
) -> dict:
    assets = req(
        "GET", f"{API}/repos/{repo}/releases/{release['id']}/assets?per_page=100", token
    ).json()
    existing = next((a for a in assets if a["name"] == name), None)
    if existing:
        verify_asset(repo, existing, token, sha, size)
        return existing

    upload = release["upload_url"].split("{", 1)[0]
    with path.open("rb") as f:
        r = requests.post(
            upload,
            params={"name": name},
            data=f,
            headers={
                **headers(token),
                "Content-Type": "application/octet-stream",
                "Content-Length": str(size)
            },
            timeout=1200
        )
    if not r.ok:
        raise RuntimeError(f"Release upload failed {name}: {r.status_code} {r.text[:500]}")
    asset = r.json()
    verify_asset(repo, asset, token, sha, size)
    return asset


def receipt_bytes(receipt: dict) -> bytes:
    return (
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_immutable_receipt(
    repo: str, branch: str, path: str, receipt: dict, token: str
) -> dict:
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}"
    expected = receipt_bytes(receipt)
    g = requests.get(url, params={"ref": branch}, headers=headers(token), timeout=90)
    if g.status_code == 200:
        existing = base64.b64decode(g.json()["content"])
        if existing != expected:
            raise RuntimeError(f"IMMUTABLE_RECEIPT_CONFLICT: {path}")
        return {"path": path, "status": "IDENTICAL_ALREADY_PRESENT"}
    if g.status_code != 404:
        raise RuntimeError(f"Receipt lookup failed: {g.status_code} {g.text[:500]}")

    body = {
        "message": (
            f"receipt(mn): public acquisition {receipt['source_set_id']} "
            f"{receipt['native_asset_fingerprint'][:12]}"
        ),
        "branch": branch,
        "content": base64.b64encode(expected).decode("ascii")
    }
    p = requests.put(url, headers=headers(token), json=body, timeout=120)
    if not p.ok:
        raise RuntimeError(f"Receipt create failed: {p.status_code} {p.text[:500]}")
    return {
        "path": path,
        "status": "CREATED",
        "commit": p.json()["commit"]["sha"]
    }


def release_disposition(
    spec: dict, work: Path, records: list[dict], receipt: dict,
    repo: str, token: str, target: str, public: bool
) -> dict:
    fp = receipt["native_asset_fingerprint"]

    if public:
        reuse = spec["reuse"]
        if (
            reuse["status"] != "verified"
            or reuse["public_redistribution_gate"] != "asset_check_required"
        ):
            raise RuntimeError("Public release denied by fail-closed reuse gate")

        check = reuse.get("asset_check")
        if check == "eurostat_official_output":
            if not all(
                "ec.europa.eu/eurostat/" in (r.get("source_url") or "")
                for r in records
            ):
                raise RuntimeError("Eurostat asset-level check failed")
        elif check == "ckan_declared_cc0":
            metadata = json.loads(
                (work / "payload/ckan-package-show.json").read_text()
            )
            result = metadata.get("result") or {}
            lic = str(
                result.get("license_id") or result.get("license_title") or ""
            ).lower()
            if not any(
                x in lic for x in ("cc0", "cc-zero", "cc zero", "creative commons zero")
            ):
                raise RuntimeError(f"CKAN asset-level licence check failed: {lic!r}")
        else:
            raise RuntimeError(
                "No supported asset-level redistribution check declared"
            )

    tag = f"mn-src-{spec['source_set_id'].lower()}-{fp[:20]}"
    body = (
        f"Source set: {spec['source_set_id']}\n\n"
        f"Producer: {spec['producer']}\n\n"
        f"Source: {spec['source']['landing_url']}\n\n"
        f"Native asset fingerprint: `{fp}`\n\n"
        "This release preserves producer-native source bytes. "
        "Canonical acceptance and consumer publication remain separate."
    )
    rel = create_release(
        repo, tag, token, target=target,
        name=f"{spec['source_set_id']} — {spec['title']} — native source preservation",
        body=body
    )

    published = []
    for r in records:
        asset = upload_or_verify(
            repo, rel, work / r["path"], r["name"], token,
            r["sha256"], int(r["bytes"])
        )
        published.append({
            "name": asset["name"],
            "id": asset["id"],
            "sha256": r["sha256"],
            "bytes": r["bytes"],
            "url": asset.get("browser_download_url")
        })

    return {
        "repository": repo,
        "release_tag": tag,
        "release_url": rel["html_url"],
        "assets": published
    }


def disposition(spec: dict, work: Path, records: list[dict], receipt: dict) -> dict:
    if spec["sink"] == "public_release":
        token = os.environ.get("GITHUB_TOKEN", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if not token or not repo:
            raise RuntimeError("GITHUB_TOKEN/GITHUB_REPOSITORY unavailable")

        target = os.environ.get("GITHUB_SHA", "main")
        result = release_disposition(
            spec, work, records, receipt, repo, token, target, True
        )

        final = {**receipt, "disposition": result}
        rp = work / "acquisition-receipt.json"
        rp.write_bytes(receipt_bytes(final))
        rr_sha = hashlib.sha256(rp.read_bytes()).hexdigest()

        rel = release_for_tag(repo, result["release_tag"], token)
        a = upload_or_verify(
            repo, rel, rp, rp.name, token, rr_sha, rp.stat().st_size
        )
        result["receipt_asset"] = {
            "id": a["id"],
            "name": a["name"],
            "sha256": rr_sha
        }
        return result

    token = os.environ.get("MN_PRIVATE_SINK_TOKEN", "")
    if not token:
        raise RuntimeError(
            "MN_PRIVATE_SINK_TOKEN is required for a private sink; "
            "source bytes were not persisted publicly"
        )

    result = release_disposition(
        spec, work, records, receipt,
        PRIVATE_REPO, token, PRIVATE_BRANCH, False
    )
    private_receipt = {**receipt, "disposition": result}
    path = (
        "statistics/recovery-20260920/simple-runtime/acquisition-bridge/results/"
        f"public-plane/{spec['source_set_id']}/"
        f"{receipt['native_asset_fingerprint']}.json"
    )
    result["private_receipt"] = write_immutable_receipt(
        PRIVATE_REPO, PRIVATE_BRANCH, path, private_receipt, token
    )
    return result
