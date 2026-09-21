from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import urllib.parse

import requests

API = "https://api.github.com"
PRIVATE_REPO = "r-sousa/EU-transp-weekly"
UA = "MobilidadeNorte-RepairAuthorization/1.0"
DECISION = "AUTHORISED_PRIMARY_REPAIR_AFTER_PRESERVED_STATE_REVIEW"


def _token() -> str:
    token = (
        os.environ.get("MN_PRIVATE_READ_TOKEN", "")
        or os.environ.get("MN_PRIVATE_SINK_TOKEN", "")
    )
    if not token:
        raise RuntimeError("PRIVATE_REPOSITORY_TOKEN_MISSING")
    return token


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def verify(source_set_id: str, path: str, ref: str) -> dict:
    if not path or not ref:
        raise RuntimeError("PRIMARY_REPAIR_REQUIRES_PINNED_PRIVATE_AUTHORIZATION")
    token = _token()
    url = f"{API}/repos/{PRIVATE_REPO}/contents/{urllib.parse.quote(path, safe='/')}"
    r = requests.get(url, params={"ref": ref}, headers=_headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(
            f"PRIMARY_REPAIR_AUTHORIZATION_READ_FAILED {r.status_code}: {r.text[:300]}"
        )
    obj = r.json()
    raw = base64.b64decode(obj["content"])
    auth = json.loads(raw.decode("utf-8"))

    if auth.get("decision") != DECISION:
        raise RuntimeError("PRIMARY_REPAIR_NOT_AUTHORISED_BY_ORCHESTRATOR")
    if source_set_id not in set(auth.get("source_set_ids") or []):
        raise RuntimeError(f"{source_set_id} NOT_LISTED_IN_PRIMARY_REPAIR_AUTHORIZATION")
    execution = auth.get("execution") or {}
    if execution.get("plane") != os.environ.get(
        "GITHUB_REPOSITORY", "r-sousa/mobilidade-public-sources"
    ):
        raise RuntimeError("PRIMARY_REPAIR_EXECUTION_PLANE_MISMATCH")
    if execution.get("sink") != "private":
        raise RuntimeError("PRIMARY_REPAIR_AUTHORIZATION_MUST_REQUIRE_PRIVATE_SINK")
    if auth.get("publication") != "NO_PUBLICATION_AUTHORISED_BY_THIS_OBJECT":
        raise RuntimeError("PRIMARY_REPAIR_AUTHORIZATION_PUBLICATION_GUARD_MISSING")

    return {
        "status": "PASS",
        "source_set_id": source_set_id,
        "authorization_repository": PRIVATE_REPO,
        "authorization_path": path,
        "authorization_ref": ref,
        "authorization_blob_sha": obj.get("sha"),
        "authorization_sha256": hashlib.sha256(raw).hexdigest(),
        "decision": auth["decision"],
        "publication": auth["publication"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_set_id")
    ap.add_argument("authorization_path")
    ap.add_argument("authorization_ref")
    args = ap.parse_args()
    print(
        json.dumps(
            verify(args.source_set_id, args.authorization_path, args.authorization_ref),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
