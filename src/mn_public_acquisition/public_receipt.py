from __future__ import annotations
import base64
import json
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


def same_source_object(a: dict, b: dict) -> bool:
    return (
        a.get("source_set_id") == b.get("source_set_id")
        and a.get("native_asset_fingerprint") == b.get("native_asset_fingerprint")
        and a.get("assets") == b.get("assets")
        and a.get("validation_result") == b.get("validation_result")
    )


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
            return {
                "status": "SOURCE_OBJECT_ALREADY_RECEIPTED",
                "path": dest,
                "first_acquisition_timestamp": prior.get("acquisition_timestamp"),
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
            return {
                "status": "CREATED",
                "path": dest,
                "commit": p.json()["commit"]["sha"],
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
