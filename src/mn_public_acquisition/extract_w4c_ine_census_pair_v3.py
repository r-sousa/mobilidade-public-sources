from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .extract_w4c_ine_census_pair import (
    _extract_payload,
    _field_inventory,
    _get_text,
    _put_text,
    _sha,
    _write_parts,
)
from .private_bootstrap import download_release_asset, release_by_tag


def _compact_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    out: dict[str, Any] = {
        "preserved_in_exact_input": True,
        "type": type(value).__name__,
        "json_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if isinstance(value, dict):
        out["top_level_keys"] = sorted(str(k) for k in value.keys())[:200]
        out["top_level_key_count"] = len(value)
    elif isinstance(value, list):
        out["item_count"] = len(value)
    return out


def _compact_mapping(obj: dict[str, Any]) -> dict[str, Any]:
    return {str(k): _compact_value(v) for k, v in obj.items()}


def run(cfg: dict[str, Any], read_token: str, write_token: str) -> dict[str, Any]:
    private_repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    release_tag = cfg["release_tag"]
    execution_attempt = int(cfg.get("execution_attempt", 3))

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

    # Binding guard: verify both exact preserved assets before parsing either one.
    with tempfile.TemporaryDirectory(prefix="mn-w4c-f25-f26-v3-") as td:
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
            response_info, metadata, rows = _extract_payload(obj)
            if not rows:
                raise RuntimeError(f"{sid}:NO_SOURCE_NATIVE_ROWS_EXTRACTED")
            payloads[sid] = (response_info, metadata, rows, raw)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = (
        f"statistics/recovery-20260920/simple-runtime/outputs/W4C/"
        f"{stamp}-G{generation}-F25-F26-INE-EXTRACTION-V3"
    )
    results: dict[str, Any] = {}

    for sid in ("F25", "F26"):
        response_info, metadata, rows, raw = payloads[sid]
        inv = _field_inventory(rows)
        json_parts, csv_parts = _write_parts(
            private_repo, branch, sid, out_base, metadata, rows, write_token, generation
        )

        compact_response = {
            "wrapper_key": response_info.get("wrapper_key"),
            "core_type": response_info.get("core_type"),
            "response_metadata": _compact_mapping(response_info.get("response_metadata") or {}),
        }
        compact_metadata = []
        for i, meta in enumerate(metadata):
            compact = _compact_mapping(meta)
            compact["indicator_index"] = int(meta.get("indicator_index", i))
            compact_metadata.append(compact)

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
            "response_structure": compact_response,
            "indicator_metadata_compact": compact_metadata,
            "metadata_rule": (
                "Scalar producer metadata is copied verbatim. Large nested metadata is represented by "
                "type/byte-count/SHA-256 and remains preserved in the exact fingerprint-pinned input; "
                "source-native observation rows and their producer codes/labels/flags/missingness are "
                "materialized in the JSON/CSV parts without W4C semantic interpretation."
            ),
            "producer_payload_shape": {
                "indicator_objects": len(metadata),
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
            raise RuntimeError(f"{sid}:COMPACT_SUMMARY_UNEXPECTEDLY_LARGE:{len(summary_text.encode('utf-8'))}")
        summary_path = f"{out_base}/{sid}/{sid.lower()}-source-native-summary.json"
        _put_text(
            private_repo,
            branch,
            summary_path,
            summary_text,
            write_token,
            message=f"W4C G{generation} {sid}: compact source-native extraction summary",
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
            private_repo,
            branch,
            receipt_path,
            receipt_text,
            write_token,
            message=f"W4C G{generation} {sid}: extraction receipt v3",
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
            f"{sid}/{verified[sid]['sha256'][:24]}-g{generation}-v3-extraction.json"
        )
        _put_text(
            private_repo,
            branch,
            handoff_path,
            json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            write_token,
            message=f"W4C G{generation} {sid}: extraction handoff v3 to W4B",
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
        private_repo,
        branch,
        family_path,
        json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        write_token,
        message=f"W4C G{generation}: F25/F26 family extraction receipt v3",
    )
    return {
        "schema_version": "4.1.0",
        "complete": True,
        "out_base": out_base,
        "family_receipt": family_path,
        "results": results,
    }
