from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.parse
from pathlib import Path

import requests

API = "https://api.github.com"
PRIVATE_REPO = "r-sousa/EU-transp-weekly"
PRIVATE_REF = "mobilidade-norte-recovery-20260919"
PRIVATE_INVENTORY = "statistics/recovery-20260920/simple-runtime/preserved-first/inventory.json"
UA = "MobilidadeNorte-PreservedStateSync/1.0"


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def private_json(path: str, token: str) -> dict:
    url = f"{API}/repos/{PRIVATE_REPO}/contents/{urllib.parse.quote(path, safe='/')}"
    r = requests.get(url, params={"ref": PRIVATE_REF}, headers=headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(f"Private metadata read failed {r.status_code}: {r.text[:500]}")
    obj = r.json()
    return json.loads(base64.b64decode(obj["content"]).decode("utf-8"))


def private_directory(path: str, token: str) -> list[dict]:
    url = f"{API}/repos/{PRIVATE_REPO}/contents/{urllib.parse.quote(path, safe='/')}"
    r = requests.get(url, params={"ref": PRIVATE_REF}, headers=headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(f"Private directory read failed {r.status_code}: {r.text[:500]}")
    obj = r.json()
    if not isinstance(obj, list):
        raise RuntimeError(f"Private directory route did not return a listing: {path}")
    return obj


def _inventory_ids(inv: dict) -> set[str]:
    out = set()
    for queue in (inv.get("queues") or {}).values():
        if not isinstance(queue, list):
            continue
        for row in queue:
            if isinstance(row, dict) and str(row.get("id") or "").startswith("F"):
                out.add(str(row["id"]))
    final = (
        inv.get("terminal_source_checkpoints", {})
        .get("final_preservation_states", {})
    )
    for values in final.values():
        if isinstance(values, list):
            out.update(str(x) for x in values if str(x).startswith("F"))
    return out


def _manifest_overlay(manifest: dict) -> dict:
    preservation = manifest.get("preservation") or {}
    runtime = manifest.get("runtime_overlay") or {}
    rights = manifest.get("rights") or {}
    releases = preservation.get("release_tags") or []
    paths = runtime.get("paths") or []
    consumer_paths = runtime.get("consumer_paths") or []
    return {
        "id": manifest.get("source_set_id"),
        "title": manifest.get("title"),
        "theme": manifest.get("theme"),
        "audit_status": preservation.get("audit_status"),
        "public_reuse_status": rights.get("public_reuse_status"),
        "release_count": len(releases),
        "runtime_overlay_count": len(paths),
        "consumer_overlay_count": len(consumer_paths),
        "release_backed": bool(releases),
        "runtime_only": bool(paths) and not releases,
        "manifest_path": manifest.get("canonical_path"),
        "release_tags": releases,
    }


def build_index(
    inv: dict,
    bootstrap: dict,
    *,
    source_ids: list[str] | None = None,
    canonical_manifests: dict[str, dict] | None = None,
) -> dict:
    by_id = {}
    for x in inv.get("queues", {}).get("release_backed", []):
        by_id[x["id"]] = {**x, "release_backed": True}
    for x in inv.get("queues", {}).get("runtime_only", []):
        by_id[x["id"]] = {**by_id.get(x["id"], x), "runtime_only": True}
    for x in inv.get("queues", {}).get("primary_source_only_after_preservation_review", []):
        by_id[x["id"]] = {**by_id.get(x["id"], x), "primary_candidate": True}
    for x in inv.get("queues", {}).get("no_acquisition_reference_or_controlled", []):
        by_id[x["id"]] = {**by_id.get(x["id"], x), "no_acquisition": True}

    recovered = set(
        (bootstrap.get("coverage", {}).get("already_public_direct") or [])
        + (bootstrap.get("coverage", {}).get("recovered_from_private") or [])
    )
    final = (
        inv.get("terminal_source_checkpoints", {})
        .get("final_preservation_states", {})
    )
    v1 = set(final.get("preserved_in_rhomolo_v1_release") or [])
    mm = set(final.get("preserved_in_rhomolo_mm_release") or [])
    controlled = set(final.get("controlled_access_metadata_only_by_design") or [])

    for sid, manifest in (canonical_manifests or {}).items():
        overlay = _manifest_overlay(manifest)
        if sid in by_id:
            merged = dict(overlay)
            merged.update(by_id[sid])
            by_id[sid] = merged
        else:
            by_id[sid] = overlay

    if source_ids is None:
        source_ids = sorted(
            by_id,
            key=lambda sid: int(sid[1:]) if sid[1:].isdigit() else sid,
        )

    rows = []
    for sid in source_ids:
        x = by_id.get(sid, {})
        locator = None
        if sid in recovered:
            state, action = "PUBLIC_RECOVERED", "USE_PUBLIC_RECOVERED"
        elif sid in controlled or x.get("audit_status") == "CONTROLLED_ACCESS":
            state, action = "CONTROLLED_METADATA_ONLY", "PRIVATE_CONTROLLED_LANE_ONLY"
        elif x.get("audit_status") == "REFERENCE_ONLY":
            state, action = "REFERENCE_ONLY", "NO_DATA_ACQUISITION"
        elif x.get("release_backed"):
            if x.get("audit_status") == "ERROR_RESPONSE_ONLY":
                state = "PRIVATE_RELEASE_ERROR_EVIDENCE"
                action = (
                    "REVIEW_MIDDLE_TIER_FIRST"
                    if int(x.get("runtime_overlay_count") or 0) > 0
                    else "PRIMARY_ALLOWED_AFTER_ERROR_EVIDENCE"
                )
            else:
                state, action = "PRIVATE_RELEASE_PRESENT", "READ_PRIVATE_RELEASE_FIRST"
            if sid in v1:
                locator = {"container": "source-rhomolo-2024-release2-869769b3829dd3017824"}
            elif sid in mm:
                locator = {"container": "source-rhomolo-mm-2024-f36c666af69512fe897a"}
            elif x.get("release_tags"):
                locator = {"container": str(x["release_tags"][0])}
        elif x.get("runtime_only") or int(x.get("runtime_overlay_count") or 0) > 0:
            state, action = "MIDDLE_TIER_PRESENT", "REVIEW_MIDDLE_TIER_FIRST"
        elif x.get("no_acquisition"):
            state, action = "NO_AUTOMATIC_ACQUISITION", "NO_DATA_ACQUISITION"
        else:
            state, action = "NO_PRESERVED_DATA_ACKNOWLEDGED", "PRIMARY_ALLOWED"

        rows.append({
            "source_set_id": sid,
            "title": x.get("title"),
            "theme": x.get("theme"),
            "audit_status": x.get("audit_status"),
            "public_reuse_status": x.get("public_reuse_status"),
            "preservation_state": state,
            "default_action": action,
            "release_count": int(x.get("release_count") or 0),
            "runtime_overlay_count": int(x.get("runtime_overlay_count") or 0),
            "consumer_overlay_count": int(x.get("consumer_overlay_count") or 0),
            "private_locator": locator,
            "canonical_authority": PRIVATE_REPO,
        })

    counts = {}
    for row in rows:
        counts[row["preservation_state"]] = counts.get(row["preservation_state"], 0) + 1

    return {
        "schema_version": "1.0.0",
        "generated_at": bootstrap.get("updated_at") or inv.get("generated_at"),
        "purpose": (
            "Metadata-only acknowledgement of canonical preserved Releases and middle-tier "
            "evidence in the private Mobilidade Norte control plane."
        ),
        "authority": {
            "canonical_repository": PRIVATE_REPO,
            "canonical_ref": PRIVATE_REF,
            "public_execution_repository": os.environ.get(
                "GITHUB_REPOSITORY", "r-sousa/mobilidade-public-sources"
            ),
            "rule": (
                "This index does not copy unresolved-rights bytes, change canonical "
                "rights/acceptance state, or make private preservation public."
            ),
        },
        "precedence": [
            "PUBLIC_RECOVERED",
            "PRIVATE_RELEASE_FIRST",
            "MIDDLE_TIER_FIRST",
            "PRIMARY_ALLOWED_ONLY_AFTER_PRESERVED_STATE_REVIEW",
        ],
        "counts": counts,
        "source_sets": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", type=Path, default=Path("recovery_receipts/bootstrap/current.json"))
    ap.add_argument("--out", type=Path, default=Path("preserved_state/index.json"))
    args = ap.parse_args()

    token = (
        os.environ.get("MN_PRIVATE_READ_TOKEN", "")
        or os.environ.get("MN_PRIVATE_SINK_TOKEN", "")
    )
    if not token:
        raise SystemExit("PRIVATE_READ_TOKEN_MISSING")

    inv = private_json(PRIVATE_INVENTORY, token)
    bootstrap = json.loads(args.bootstrap.read_text(encoding="utf-8"))

    listing = private_directory("statistics/source-sets", token)
    canonical_ids = sorted(
        [
            str(item.get("name"))
            for item in listing
            if item.get("type") == "dir"
            and str(item.get("name") or "").startswith("F")
            and str(item.get("name") or "")[1:].isdigit()
        ],
        key=lambda sid: int(sid[1:]),
    )
    if not canonical_ids:
        raise RuntimeError("No canonical Fxx source-set directories discovered")

    known_ids = _inventory_ids(inv)
    missing_from_inventory = [sid for sid in canonical_ids if sid not in known_ids]
    canonical_manifests = {
        sid: private_json(f"statistics/source-sets/{sid}/manifest.json", token)
        for sid in missing_from_inventory
    }

    out = build_index(
        inv,
        bootstrap,
        source_ids=canonical_ids,
        canonical_manifests=canonical_manifests,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"counts": out["counts"], "out": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
