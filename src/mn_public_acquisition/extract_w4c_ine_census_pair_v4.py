from __future__ import annotations

import gzip
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .extract_w4c_ine_census_pair import _field_inventory, _get_text, _put_text, _sha, _write_parts
from .extract_w4c_ine_census_pair_v3 import _compact_mapping
from .private_bootstrap import download_release_asset, release_by_tag


def _parse_preserved_cache(obj: Any) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse only the cache's explicit records array as source-native rows.

    The preservation cache contract is {metadata: {...}, records: [...]}. Metadata is
    lineage/context, never an observation. This function fails closed for malformed
    explicit-record caches and otherwise falls back only for already-row arrays.
    """
    if isinstance(obj, dict) and "records" in obj:
        records = obj.get("records")
        metadata = obj.get("metadata")
        if not isinstance(records, list):
            raise RuntimeError("PRESERVED_CACHE_RECORDS_NOT_LIST")
        if metadata is not None and not isinstance(metadata, dict):
            raise RuntimeError("PRESERVED_CACHE_METADATA_NOT_OBJECT")
        rows: list[dict[str, Any]] = []
        for idx, rec in enumerate(records):
            if not isinstance(rec, dict):
                raise RuntimeError(f"PRESERVED_CACHE_NON_OBJECT_RECORD:{idx}")
            rows.append({"indicator_index": 0, "context_path": ["records"], "source_row": rec})
        meta = dict(metadata or {})
        meta["indicator_index"] = 0
        return (
            {
                "cache_contract": "EXPLICIT_METADATA_PLUS_RECORDS",
                "root_keys": sorted(str(k) for k in obj.keys()),
                "metadata_is_observation": False,
                "records_is_observation_container": True,
            },
            [meta],
            rows,
        )
    if isinstance(obj, list) and all(isinstance(x, dict) for x in obj):
        return (
            {"cache_contract": "ROOT_ROW_ARRAY", "metadata_is_observation": False},
            [{"indicator_index": 0}],
            [{"indicator_index": 0, "context_path": [], "source_row": x} for x in obj],
        )
    raise RuntimeError("UNSUPPORTED_PRESERVED_CACHE_SHAPE")


def run(cfg: dict[str, Any], read_token: str, write_token: str) -> dict[str, Any]:
    private_repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    release_tag = cfg["release_tag"]
    execution_attempt = int(cfg.get("execution_attempt", 4))

    team_text, team_sha = _get_text(
        private_repo,
        branch,
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
    payloads: dict[str, tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], bytes]] = {}

    with tempfile.TemporaryDirectory(prefix="mn-w4c-f25-f26-v4-") as td:
        tdir = Path(td)
        compressed: dict[str, bytes] = {}
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
            digest = _sha(comp)
            if len(comp) != int(acfg["bytes"]) or digest != acfg["sha256"]:
                raise RuntimeError(f"{sid}:ASSET_VERIFICATION_FAILED:{len(comp)}:{digest}")
            verified[sid] = {
                "asset_id": int(asset["id"]),
                "name": asset["name"],
                "bytes": len(comp),
                "sha256": digest,
            }
            compressed[sid] = comp

        for sid in ("F25", "F26"):
            raw = gzip.decompress(compressed[sid])
            obj = json.loads(raw.decode("utf-8-sig"))
            response_info, metadata, rows = _parse_preserved_cache(obj)
            if not rows:
                raise RuntimeError(f"{sid}:NO_EXPLICIT_SOURCE_NATIVE_RECORDS")
            expected = (metadata[0] if metadata else {}).get("record_count")
            if isinstance(expected, int) and expected != len(rows):
                raise RuntimeError(f"{sid}:CACHE_RECORD_COUNT_MISMATCH:{expected}!={len(rows)}")
            payloads[sid] = (response_info, metadata, rows, raw)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = (
        f"statistics/recovery-20260920/simple-runtime/outputs/W4C/"
        f"{stamp}-G{generation}-F25-F26-INE-EXTRACTION-V4"
    )
    results: dict[str, Any] = {}

    for sid in ("F25", "F26"):
        response_info, metadata, rows, raw = payloads[sid]
        inv = _field_inventory(rows)
        json_parts, csv_parts = _write_parts(
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
                "private_release": release_tag,
                **verified[sid],
                "gzip_decompressed_bytes": len(raw),
                "gzip_decompressed_sha256": _sha(raw),
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
        if len(summary_text.encode("utf-8")) > 5_000_000:
            raise RuntimeError(f"{sid}:SUMMARY_TOO_LARGE:{len(summary_text.encode('utf-8'))}")
        summary_path = f"{out_base}/{sid}/{sid.lower()}-source-native-summary.json"
        _put_text(
            private_repo, branch, summary_path, summary_text, write_token,
            message=f"W4C G{generation} {sid}: metadata-safe source-native summary"
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
            "gzip_decompressed_sha256": _sha(raw),
            "source_native_row_count": len(rows),
            "field_count": inv["field_count"],
            "field_names": inv["fields"],
            "metadata_rows_excluded": True,
            "summary": {
                "path": summary_path,
                "sha256": _sha(summary_text.encode("utf-8")),
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
        receipt_hash = _sha(receipt_text.encode("utf-8"))
        receipt_path = f"{out_base}/{sid}/{sid.lower()}-extraction-receipt.json"
        _put_text(
            private_repo, branch, receipt_path, receipt_text, write_token,
            message=f"W4C G{generation} {sid}: final extraction receipt"
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
        handoff_path = (
            "statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/"
            f"{sid}/{verified[sid]['sha256'][:24]}-g{generation}-v4-extraction.json"
        )
        _put_text(
            private_repo, branch, handoff_path,
            json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            write_token, message=f"W4C G{generation} {sid}: final extraction handoff to W4B"
        )
        results[sid] = {
            "status": receipt["status"],
            "source_native_row_count": len(rows),
            "field_names": inv["fields"],
            "summary": summary_path,
            "receipt": receipt_path,
            "receipt_sha256": receipt_hash,
            "handoff": handoff_path,
            "json_parts": json_parts,
            "csv_parts": csv_parts,
        }

    family = {
        "schema_version": "4.1.0",
        "worker": "W4C",
        "mission_generation": generation,
        "execution_attempt": execution_attempt,
        "operation": "DETERMINISTIC_PRIVATE_PRESERVED_INE_CENSUS_PAIR_EXTRACTION",
        "release_tag": release_tag,
        "assets_verified_before_parse": True,
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
    _put_text(
        private_repo, branch, family_path,
        json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        write_token, message=f"W4C G{generation}: final F25/F26 family extraction receipt"
    )
    return {
        "schema_version": "4.1.0",
        "complete": True,
        "out_base": out_base,
        "family_receipt": family_path,
        "results": results,
    }
