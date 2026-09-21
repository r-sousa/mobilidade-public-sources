from __future__ import annotations
import base64
import json
import hashlib
import os
import sys
import time
import urllib.parse
from pathlib import Path

import requests

API = "https://api.github.com"
UA = "MobilidadeNorte-PublicReceipt/1.0"


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _native_assets(receipt: dict) -> list[dict]:
    out = []
    for a in receipt.get("assets") or []:
        if a.get("role", "native") == "recomposed":
            continue
        out.append({
            "name": a.get("name"),
            "sha256": a.get("sha256"),
            "bytes": a.get("bytes"),
            "format": a.get("format"),
            "source_url": a.get("source_url"),
        })
    return sorted(out, key=lambda x: (str(x.get("name")), str(x.get("sha256"))))


def _recomposed_assets(receipt: dict) -> list[dict]:
    out = []
    for a in receipt.get("assets") or []:
        if a.get("role") != "recomposed":
            continue
        out.append({
            "name": a.get("name"),
            "sha256": a.get("sha256"),
            "bytes": a.get("bytes"),
            "format": a.get("format"),
        })
    return sorted(out, key=lambda x: (str(x.get("name")), str(x.get("sha256"))))


def same_source_object(a: dict, b: dict) -> bool:
    return (
        a.get("source_set_id") == b.get("source_set_id")
        and a.get("native_asset_fingerprint") == b.get("native_asset_fingerprint")
        and _native_assets(a) == _native_assets(b)
    )


def _persist_composition_evidence(receipt: dict, token: str, repo: str, branch: str) -> dict | None:
    derived = _recomposed_assets(receipt)
    if not derived:
        return None
    payload = {
        "schema_version": "1.0.0",
        "source_set_id": receipt["source_set_id"],
        "native_asset_fingerprint": receipt["native_asset_fingerprint"],
        "validation_result": receipt.get("validation_result"),
        "acquisition_code_commit": receipt.get("acquisition_code_commit"),
        "recomposed_assets": derived,
        "limitations": receipt.get("limitations"),
    }
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    efp = hashlib.sha256(raw).hexdigest()
    dest = (
        f"composition_receipts/{receipt['source_set_id']}/"
        f"{receipt['native_asset_fingerprint']}/{efp}.json"
    )
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(dest, safe='/')}"
    g = requests.get(url, params={"ref": branch}, headers=headers(token), timeout=90)
    if g.status_code == 200:
        existing = base64.b64decode(g.json()["content"])
        if existing != raw:
            raise RuntimeError(f"IMMUTABLE_COMPOSITION_RECEIPT_CONFLICT: {dest}")
        return {"status": "IDENTICAL_ALREADY_PRESENT", "path": dest}
    if g.status_code != 404:
        raise RuntimeError(f"Composition receipt lookup failed {g.status_code}: {g.text[:500]}")
    body = {
        "message": f"receipt(mn): composition {receipt['source_set_id']} {efp[:12]}",
        "branch": branch,
        "content": base64.b64encode(raw).decode("ascii"),
    }
    p = requests.put(url, json=body, headers=headers(token), timeout=120)
    if p.status_code not in (200, 201):
        raise RuntimeError(f"Composition receipt create failed {p.status_code}: {p.text[:500]}")
    return {"status": "CREATED", "path": dest, "commit": p.json()["commit"]["sha"]}


def persist(path: Path) -> dict:
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    receipt = json.loads(path.read_text(encoding="utf-8"))

    sid = receipt["source_set_id"]
    fp = receipt["native_asset_fingerprint"]
    dest = f"receipts/{sid}/{fp}.json"
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(dest, safe='/')}"
    canonical = (
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    for attempt in range(1, 6):
        g = requests.get(
            url, params={"ref": branch}, headers=headers(token), timeout=90
        )
        if g.status_code == 200:
            prior = json.loads(base64.b64decode(g.json()["content"]).decode("utf-8"))
            if not same_source_object(prior, receipt):
                raise RuntimeError(f"IMMUTABLE_PUBLIC_RECEIPT_CONFLICT: {dest}")
            composition = _persist_composition_evidence(receipt, token, repo, branch)
            return {
                "status": "SOURCE_OBJECT_ALREADY_RECEIPTED",
                "path": dest,
                "first_acquisition_timestamp": prior.get("acquisition_timestamp"),
                "composition_evidence": composition,
            }
        if g.status_code != 404:
            raise RuntimeError(
                f"Receipt lookup failed {g.status_code}: {g.text[:500]}"
            )

        body = {
            "message": f"receipt(mn): {sid} {fp[:12]}",
            "branch": branch,
            "content": base64.b64encode(canonical).decode("ascii"),
        }
        p = requests.put(url, json=body, headers=headers(token), timeout=120)
        if p.status_code in (200, 201):
            composition = _persist_composition_evidence(receipt, token, repo, branch)
            return {
                "status": "CREATED",
                "path": dest,
                "commit": p.json()["commit"]["sha"],
                "composition_evidence": composition,
            }
        if p.status_code not in (409, 422):
            raise RuntimeError(
                f"Receipt create failed {p.status_code}: {p.text[:500]}"
            )
        time.sleep(attempt)

    raise RuntimeError("PUBLIC_RECEIPT_CONTENTION")


if __name__ == "__main__":
    result = persist(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False))
