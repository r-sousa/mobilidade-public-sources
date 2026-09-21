from __future__ import annotations

import json
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .extract_w3c_f30 import _csv, _dedup_rows, _walk
from .extract_w4c_shared import _get_text, _put_text, _sha
from .private_bootstrap import download_release_asset, release_by_tag


def _decode_source_json(raw: bytes) -> tuple[object, str]:
    try:
        text = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        # The preserved IGE native response is not UTF-8. ISO-8859-1 is a
        # reversible byte-to-codepoint mapping and avoids replacement/loss.
        text = raw.decode("iso-8859-1")
        encoding = "iso-8859-1"
    return json.loads(text), encoding


def run(cfg: dict, read_token: str, write_token: str) -> dict:
    repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    tag = cfg["release_tag"]
    asset_cfg = cfg["asset"]
    team_path = "statistics/recovery-20260920/simple-runtime/team-missions.json"

    team_text, _ = _get_text(repo, branch, team_path, read_token)
    team = json.loads(team_text)
    if int(team.get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED")
    w3c = ((team.get("teams") or {}).get("W3") or {}).get("C") or {}
    if w3c.get("worker") != "W3C" or "f30" not in " ".join(w3c.get("queue") or []).lower():
        raise RuntimeError("W3C_CURRENT_MISSION_NO_LONGER_AUTHORIZES_F30")

    handoff_text, handoff_sha = _get_text(repo, branch, cfg["handoff_path"], read_token)
    if handoff_sha != cfg["handoff_blob_sha"]:
        raise RuntimeError(f"W3B_HANDOFF_BLOB_MISMATCH:{handoff_sha}")
    handoff = json.loads(handoff_text)
    preserved = handoff.get("preserved_input") or {}
    if handoff.get("worker") != "W3B" or "F30" not in (handoff.get("field_ids") or []):
        raise RuntimeError("W3B_HANDOFF_IDENTITY_MISMATCH")
    if preserved.get("release_tag") != tag or preserved.get("asset") != asset_cfg["name"]:
        raise RuntimeError("W3B_HANDOFF_RELEASE_ASSET_MISMATCH")
    if int(preserved.get("native_bytes", -1)) != int(asset_cfg["bytes"]) or preserved.get("native_sha256") != asset_cfg["sha256"]:
        raise RuntimeError("W3B_HANDOFF_BYTE_HASH_CONTRACT_MISMATCH")

    release = release_by_tag(repo, tag, read_token)
    asset = next((x for x in release.get("assets", []) if int(x["id"]) == int(asset_cfg["id"])), None)
    if not asset:
        raise RuntimeError("PINNED_RELEASE_ASSET_ID_NOT_FOUND")
    if asset["name"] != asset_cfg["name"] or int(asset["size"]) != int(asset_cfg["bytes"]):
        raise RuntimeError("PINNED_RELEASE_ASSET_METADATA_MISMATCH")
    digest = str(asset.get("digest") or "").removeprefix("sha256:")
    if digest and digest != asset_cfg["sha256"]:
        raise RuntimeError("PINNED_RELEASE_ASSET_DIGEST_MISMATCH")

    with tempfile.TemporaryDirectory(prefix="mn-w3c-f30-v2-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(repo, asset, read_token, local)
        raw = local.read_bytes()
    actual_sha = _sha(raw)
    if len(raw) != int(asset_cfg["bytes"]) or actual_sha != asset_cfg["sha256"]:
        raise RuntimeError(f"F30_ASSET_VERIFICATION_FAILED:{len(raw)}:{actual_sha}")

    obj, source_encoding = _decode_source_json(raw)
    key_stats = defaultdict(Counter)
    candidates: list[dict] = []
    _walk(obj, [], key_stats, candidates)
    rows = _dedup_rows(candidates)
    dimension_dictionary = [
        {
            "native_key": key,
            "observed_value_types": dict(sorted(types.items())),
            "occurrences": sum(types.values()),
            "semantic_policy": "PRESERVE_NATIVE_NO_RECODE",
        }
        for key, types in sorted(key_stats.items())
    ]

    status = "PASS_SOURCE_NATIVE_IGE_JSON_INGRESS" if rows else "PASS_VALID_EMPTY_SOURCE_NATIVE_IGE_JSON"
    payload = {
        "schema_version": "4.0.1",
        "worker": "W3C",
        "mission_generation": generation,
        "source_set_id": "F30",
        "producer": "Instituto Galego de Estatística",
        "product": "IGE 4580 — Tráfego comercial nos aeroportos",
        "status": status,
        "source_identity": {
            "release_tag": tag,
            "release_id": release.get("id"),
            "asset_id": asset_cfg["id"],
            "asset_name": asset_cfg["name"],
            "asset_bytes": len(raw),
            "asset_sha256": actual_sha,
            "source_encoding": source_encoding,
            "source_encoding_policy": "STRICT_UTF8_ELSE_REVERSIBLE_ISO_8859_1_NO_REPLACEMENT",
            "w3b_handoff_path": cfg["handoff_path"],
            "w3b_handoff_blob_sha": handoff_sha,
        },
        "record_count": len(rows),
        "records": rows,
        "dimension_dictionary": dimension_dictionary,
        "preservation_rules": [
            "DatoN and DatoT are preserved verbatim when present.",
            "Native records, flags, missing/confidential markers and scalar types are preserved; missing/suppressed is never converted to zero.",
            "Source byte hash is checked before decoding; encoding fallback performs no replacement or transliteration.",
            "No airport-period-metric cells are synthesized from independent margins.",
            "Overlapping IGE, Aena and DGAC representations remain alternative/control evidence and are never additive."
        ],
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "consumer_join": False,
    }
    jtext = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ctext = _csv(rows)

    fresh_team_text, _ = _get_text(repo, branch, team_path, read_token)
    if int(json.loads(fresh_team_text).get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W3C/{stamp}-G{generation}-W3C-F30-IGE4580-extraction-ingress"
    jpath = f"{out_base}/F30-source-native.json"
    cpath = f"{out_base}/F30-source-native.csv"
    rpath = f"{out_base}/extraction-receipt.json"
    handoff_path = "statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F30/92525a31c1907715c00fc82add5df4e53b19b479d18380b107013db6758813ac-extraction.json"

    _put_text(repo, branch, jpath, jtext, write_token, message="result(mn): W3C F30 source-native IGE extraction", immutable=True)
    _put_text(repo, branch, cpath, ctext, write_token, message="result(mn): W3C F30 compact IGE extraction", immutable=True)
    receipt = {
        "schema_version": "4.0.1",
        "worker": "W3C",
        "mission_generation": generation,
        "package": "W3C_F30_IGE4580_EXTRACTION_INGRESS",
        "source_set_id": "F30",
        "status": status,
        "release_tag": tag,
        "asset": {
            "id": asset_cfg["id"],
            "name": asset_cfg["name"],
            "bytes": len(raw),
            "sha256": actual_sha,
            "verified": True,
            "source_encoding": source_encoding,
        },
        "w3b_handoff": {"path": cfg["handoff_path"], "blob_sha": handoff_sha, "verified": True},
        "record_count": len(rows),
        "dimension_key_count": len(dimension_dictionary),
        "outputs": [jpath, cpath],
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "consumer_join": False,
    }
    rtext = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _put_text(repo, branch, rpath, rtext, write_token, message="result(mn): W3C F30 extraction receipt", immutable=True)
    _put_text(repo, branch, handoff_path, rtext, write_token, message="handoff(mn): W3C F30 IGE extraction", immutable=True)

    worker_path = "statistics/recovery-20260920/simple-runtime/worker-W3C.json"
    prior_text, prior_sha = _get_text(repo, branch, worker_path, write_token)
    prior = json.loads(prior_text)
    completed = list(dict.fromkeys((prior.get("cumulative_completed") or []) + [f"GEN{generation}_V401_W3C_F30_IGE4580_EXTRACTION"]))
    worker = {
        "schema_version": "4.0.1",
        "worker": "W3C",
        "team": "W3",
        "partner": "C",
        "mission_generation": generation,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "READY_CONTINUE_WINDOW",
        "elastic_state": "ACTIVE_W3B_P114_P124_EXTRACTION_BACKLOG",
        "current_task": None,
        "last_output": rpath,
        "window": {
            "mission_generation": generation,
            "phase": "CLEANUP_NORMALIZATION_COMPLETENESS",
            "material_packages": 1,
            "completed_packages": ["P124_F30_IGE4580"],
            "source_sets": ["F30"],
            "record_count": len(rows),
            "dimension_key_count": len(dimension_dictionary),
            "source_encoding": source_encoding,
            "producer_reacquisitions": 0,
            "rights_adjudications": 0,
            "consumer_tables_built": 0,
            "canonical_manifest_index_catalogue_writes": 0,
            "site_deployments": 0,
            "drive_refreshes": 0,
            "scheduler_changes": 0,
            "outputs": [jpath, cpath, rpath, handoff_path],
            "shared_backlog_note": "P115/F162 exact logical member snapshots/F162.pdf was absent in both tested pinned shared-archive candidates; do not producer-reacquire. Continue other exact W3B handoffs and resolve archive/member identity separately.",
            "next_cursor": [
                "Continue non-overlapping W3B backlog P114-P123, rotating around P115/F162 member-identity blocker.",
                "Do not repeat F148 current 2024+ valid-empty package."
            ],
        },
        "cumulative_completed": completed,
        "metrics": {
            "material_packages_this_window": 1,
            "members_extracted_this_window": 1,
            "source_native_records_this_window": len(rows),
            "producer_reacquisitions_this_window": 0,
        },
        "blocker": None,
    }
    _put_text(
        repo,
        branch,
        worker_path,
        json.dumps(worker, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        write_token,
        message="result(mn): W3C F30 IGE extraction ingress",
        expected_sha=prior_sha,
        immutable=False,
    )
    return {
        "schema_version": "1.0.0",
        "complete": True,
        "results": [{"source_set_id": "F30", "status": status, "record_count": len(rows), "source_encoding": source_encoding, "private_handoff": handoff_path}],
        "failures": [],
        "private_write_count": 5,
    }
