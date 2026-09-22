from __future__ import annotations

import gzip
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import extract_w4c_ine_census_pair as base
from .extract_w4c_ine_census_pair_v3 import _compact_mapping
from .extract_w4c_ine_census_pair_v4 import _parse_preserved_cache
from .private_bootstrap import download_release_asset, release_by_tag

_ORIGINAL_PUT = base._put_text


def _put_text_retry(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Retry only transient branch-head 409 conflicts; never overwrite immutable output."""
    delays = (0.5, 1.0, 2.0, 4.0, 8.0)
    last: Exception | None = None
    for attempt in range(len(delays) + 1):
        try:
            return _ORIGINAL_PUT(*args, **kwargs)
        except RuntimeError as exc:
            last = exc
            if ":409:" not in str(exc) or attempt >= len(delays):
                raise
            time.sleep(delays[attempt])
    assert last is not None
    raise last


def _existing_handoff_path(sid: str, asset_sha: str, generation: int) -> str:
    return (
        "statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/"
        f"{sid}/{asset_sha[:24]}-g{generation}-v4-extraction.json"
    )


def _validate_reusable_handoff(h: dict[str, Any], sid: str, asset: dict[str, Any]) -> None:
    expected = {
        "asset_id": int(asset["id"]),
        "name": asset["name"],
        "bytes": int(asset["bytes"]),
        "sha256": asset["sha256"],
    }
    if h.get("asset") != expected:
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_ASSET_IDENTITY_MISMATCH")
    if h.get("source_set_id") != sid:
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_SOURCE_ID_MISMATCH")
    if h.get("status") != "PASS_SOURCE_NATIVE_EXTRACTION_INGRESS":
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_NOT_PASS")
    if h.get("state_after_ingress") != "ACQUIRED_NOT_NORMALIZED":
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_STATE_MISMATCH")
    if h.get("semantic_owner_after_return") != "W4B":
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_SEMANTIC_OWNER_MISMATCH")
    if h.get("metadata_rows_excluded") is not True:
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_METADATA_GUARD_MISSING")
    if h.get("producer_reacquisition") is not False or h.get("rights_adjudication") is not False:
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_SCOPE_GUARD_MISMATCH")
    if h.get("consumer_built") is not False:
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_CONSUMER_GUARD_MISMATCH")
    if int(h.get("source_native_row_count", 0)) <= 0:
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_EMPTY")
    if not h.get("json_parts") or not h.get("csv_parts") or not h.get("private_extraction_receipt"):
        raise RuntimeError(f"{sid}:EXISTING_HANDOFF_INCOMPLETE")
    for family in ("json_parts", "csv_parts"):
        for p in h[family]:
            if int(p.get("rows", 0)) <= 0 or int(p.get("bytes", 0)) <= 0 or len(str(p.get("sha256", ""))) != 64:
                raise RuntimeError(f"{sid}:EXISTING_HANDOFF_PART_LINEAGE_INVALID")


def _write_f26(
    cfg: dict[str, Any],
    verified: dict[str, dict[str, Any]],
    compressed: dict[str, bytes],
    team_sha: str,
    write_token: str,
    out_base: str,
) -> dict[str, Any]:
    sid = "F26"
    private_repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    execution_attempt = int(cfg.get("execution_attempt", 6))

    raw = gzip.decompress(compressed[sid])
    obj = json.loads(raw.decode("utf-8-sig"))
    response_info, metadata, rows = _parse_preserved_cache(obj)
    if not rows:
        raise RuntimeError("F26:NO_EXPLICIT_SOURCE_NATIVE_RECORDS")
    expected = (metadata[0] if metadata else {}).get("record_count")
    if isinstance(expected, int) and expected != len(rows):
        raise RuntimeError(f"F26:CACHE_RECORD_COUNT_MISMATCH:{expected}!={len(rows)}")

    inv = base._field_inventory(rows)
    json_parts, csv_parts = base._write_parts(
        private_repo, branch, sid, out_base, metadata, rows, write_token, generation
    )
    compact_metadata = [_compact_mapping(m) for m in metadata]
    summary = {
        "schema_version": "4.1.0",
        "worker": "W4C",
        "mission_generation": generation,
        "execution_attempt": execution_attempt,
        "source_set_id": sid,
        "status": "PASS_SOURCE_NATIVE_EXTRACTION_INGRESS",
        "semantic_owner_after_return": "W4B",
        "source_identity": {
            "private_release": cfg["release_tag"],
            **verified[sid],
            "gzip_decompressed_bytes": len(raw),
            "gzip_decompressed_sha256": base._sha(raw),
            "verified_before_parse": True,
        },
        "cache_structure": response_info,
        "cache_metadata_compact": compact_metadata,
        "metadata_observation_guard": "CACHE_METADATA_EXCLUDED_FROM_SOURCE_NATIVE_ROWS",
        "producer_payload_shape": {
            "source_native_rows": len(rows),
            "field_inventory": inv,
        },
        "json_parts": json_parts,
        "csv_parts": csv_parts,
        "guards": cfg["semantic_guards"][sid],
        "interpretation_performed": False,
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "consumer_interpretation": False,
    }
    summary_text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    summary_path = f"{out_base}/{sid}/f26-source-native-summary.json"
    _put_text_retry(
        private_repo, branch, summary_path, summary_text, write_token,
        message=f"W4C G{generation} F26: resumable source-native summary"
    )

    receipt = {
        "schema_version": "4.1.0",
        "worker": "W4C",
        "mission_generation": generation,
        "execution_attempt": execution_attempt,
        "source_set_id": sid,
        "status": "PASS_SOURCE_NATIVE_EXTRACTION_INGRESS",
        "asset": verified[sid],
        "gzip_decompressed_bytes": len(raw),
        "gzip_decompressed_sha256": base._sha(raw),
        "source_native_row_count": len(rows),
        "field_count": inv["field_count"],
        "field_names": inv["fields"],
        "metadata_rows_excluded": True,
        "summary": {
            "path": summary_path,
            "sha256": base._sha(summary_text.encode("utf-8")),
            "bytes": len(summary_text.encode("utf-8")),
        },
        "json_parts": json_parts,
        "csv_parts": csv_parts,
        "semantic_owner_after_return": "W4B",
        "state_after_ingress": "ACQUIRED_NOT_NORMALIZED",
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "consumer_built": False,
        "complete": True,
    }
    receipt_text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    receipt_hash = base._sha(receipt_text.encode("utf-8"))
    receipt_path = f"{out_base}/{sid}/f26-extraction-receipt.json"
    _put_text_retry(
        private_repo, branch, receipt_path, receipt_text, write_token,
        message=f"W4C G{generation} F26: resumable final extraction receipt"
    )

    handoff = {
        **receipt,
        "handoff_type": "DETERMINISTIC_EXTRACTION_INGRESS_TO_W4B",
        "private_extraction_receipt": receipt_path,
        "private_extraction_receipt_sha256": receipt_hash,
        "binding_team_missions_blob_sha": team_sha,
        "corrects_prior_attempts": cfg.get("corrects_prior_attempts"),
        "changed_method_reason": cfg.get("changed_method_reason"),
    }
    handoff_path = _existing_handoff_path(sid, verified[sid]["sha256"], generation)
    _put_text_retry(
        private_repo, branch, handoff_path,
        json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        write_token, message=f"W4C G{generation} F26: final extraction handoff to W4B"
    )
    return {
        "status": receipt["status"],
        "source_native_row_count": len(rows),
        "field_names": inv["fields"],
        "summary": summary_path,
        "receipt": receipt_path,
        "receipt_sha256": receipt_hash,
        "handoff": handoff_path,
        "json_parts": json_parts,
        "csv_parts": csv_parts,
        "reused_existing_valid_handoff": False,
    }


def run(cfg: dict[str, Any], read_token: str, write_token: str) -> dict[str, Any]:
    private_repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    release_tag = cfg["release_tag"]
    execution_attempt = int(cfg.get("execution_attempt", 6))

    team_text, team_sha = base._get_text(
        private_repo, branch,
        "statistics/recovery-20260920/simple-runtime/team-missions.json",
        read_token,
    )
    team = json.loads(team_text)
    if int(team.get("mission_generation", -1)) != generation:
        raise RuntimeError(f"MISSION_GENERATION_CHANGED:{team.get('mission_generation')}!=G{generation}")
    current_w4c = (((team.get("teams") or {}).get("W4") or {}).get("C") or {})
    current_text = json.dumps(current_w4c, ensure_ascii=False)
    if "F25" not in current_text or "F26" not in current_text:
        raise RuntimeError("CURRENT_W4C_MISSION_DOES_NOT_ASSIGN_F25_F26")

    release = release_by_tag(private_repo, release_tag, read_token)
    assets_by_id = {int(x["id"]): x for x in release.get("assets", [])}
    verified: dict[str, dict[str, Any]] = {}
    compressed: dict[str, bytes] = {}

    # Verify both exact preserved assets before any new parse.
    with tempfile.TemporaryDirectory(prefix="mn-w4c-f25-f26-v6-") as td:
        tdir = Path(td)
        for sid in ("F25", "F26"):
            acfg = cfg["assets"][sid]
            asset = assets_by_id.get(int(acfg["id"]))
            if not asset:
                raise RuntimeError(f"{sid}:PINNED_RELEASE_ASSET_ID_NOT_FOUND")
            if asset.get("name") != acfg["name"] or int(asset.get("size", -1)) != int(acfg["bytes"]):
                raise RuntimeError(f"{sid}:PINNED_RELEASE_ASSET_METADATA_MISMATCH")
            local = tdir / acfg["name"]
            download_release_asset(private_repo, asset, read_token, local)
            comp = local.read_bytes()
            digest = base._sha(comp)
            if len(comp) != int(acfg["bytes"]) or digest != acfg["sha256"]:
                raise RuntimeError(f"{sid}:ASSET_VERIFICATION_FAILED:{len(comp)}:{digest}")
            verified[sid] = {
                "asset_id": int(asset["id"]),
                "name": asset["name"],
                "bytes": len(comp),
                "sha256": digest,
            }
            compressed[sid] = comp

        # F25 already has a complete metadata-safe handoff from attempt 4. Reuse it only
        # after strict lineage/scope validation; never overwrite the immutable handoff.
        f25_handoff_path = _existing_handoff_path("F25", verified["F25"]["sha256"], generation)
        f25_text, _ = base._get_text(private_repo, branch, f25_handoff_path, read_token)
        f25_handoff = json.loads(f25_text)
        _validate_reusable_handoff(f25_handoff, "F25", cfg["assets"]["F25"])

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_base = (
            "statistics/recovery-20260920/simple-runtime/outputs/W4C/"
            f"{stamp}-G{generation}-F25-F26-INE-EXTRACTION-RESUME-A{execution_attempt}"
        )

        validation = {
            "schema_version": "4.1.0",
            "worker": "W4C",
            "mission_generation": generation,
            "execution_attempt": execution_attempt,
            "source_set_id": "F25",
            "status": "REUSED_VALID_EXISTING_EXTRACTION_HANDOFF",
            "asset_verified_this_operation": verified["F25"],
            "existing_handoff": f25_handoff_path,
            "existing_private_extraction_receipt": f25_handoff["private_extraction_receipt"],
            "existing_private_extraction_receipt_sha256": f25_handoff["private_extraction_receipt_sha256"],
            "source_native_row_count": f25_handoff["source_native_row_count"],
            "metadata_rows_excluded": True,
            "semantic_owner_after_return": "W4B",
            "state_after_ingress": "ACQUIRED_NOT_NORMALIZED",
            "producer_reacquisition": False,
            "rights_adjudication": False,
            "consumer_built": False,
            "reason": "Attempt-4 F25 handoff is metadata-safe, exact-fingerprint pinned and complete. Attempt 5 failed only because it tried to replace that non-identical immutable handoff. This operation validates and reuses it instead of duplicating F25 outputs.",
        }
        validation_path = f"{out_base}/F25/f25-existing-handoff-reuse-validation.json"
        _put_text_retry(
            private_repo, branch, validation_path,
            json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            write_token, message=f"W4C G{generation} F25: validate reusable extraction handoff"
        )

        old_put = base._put_text
        base._put_text = _put_text_retry
        try:
            f26_result = _write_f26(cfg, verified, compressed, team_sha, write_token, out_base)
        finally:
            base._put_text = old_put

    f25_result = {
        "status": "PASS_SOURCE_NATIVE_EXTRACTION_INGRESS_REUSED",
        "source_native_row_count": f25_handoff["source_native_row_count"],
        "field_names": f25_handoff["field_names"],
        "summary": f25_handoff["summary"]["path"],
        "receipt": f25_handoff["private_extraction_receipt"],
        "receipt_sha256": f25_handoff["private_extraction_receipt_sha256"],
        "handoff": f25_handoff_path,
        "json_parts": f25_handoff["json_parts"],
        "csv_parts": f25_handoff["csv_parts"],
        "reuse_validation": validation_path,
        "reused_existing_valid_handoff": True,
    }
    results = {"F25": f25_result, "F26": f26_result}
    family = {
        "schema_version": "4.1.0",
        "worker": "W4C",
        "mission_generation": generation,
        "execution_attempt": execution_attempt,
        "operation": "DETERMINISTIC_PRIVATE_PRESERVED_INE_CENSUS_PAIR_EXTRACTION_RESUME",
        "release_tag": release_tag,
        "assets_verified_before_new_parse": True,
        "F25_existing_valid_handoff_reused": True,
        "F26_new_parse_performed": True,
        "cache_metadata_excluded_from_observations": True,
        "results": results,
        "semantic_owner_after_return": "W4B",
        "producer_requests_made": 0,
        "rights_state_changed": False,
        "consumer_tables_built": False,
        "corrects_prior_attempts": cfg.get("corrects_prior_attempts"),
        "changed_method_reason": cfg.get("changed_method_reason"),
        "complete": True,
    }
    family_path = f"{out_base}/f25-f26-family-extraction-receipt.json"
    _put_text_retry(
        private_repo, branch, family_path,
        json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        write_token, message=f"W4C G{generation}: complete resumable F25/F26 extraction family"
    )
    return {
        "schema_version": "4.1.0",
        "complete": True,
        "out_base": out_base,
        "family_receipt": family_path,
        "results": results,
    }
