from __future__ import annotations

import csv
import io
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .extract_w3c_f30_v2 import _decode_source_json
from .extract_w4c_shared import _get_text, _put_text, _sha
from .private_bootstrap import download_release_asset, release_by_tag


def _rows_from_ige(obj: object) -> tuple[list[str], list[dict], list[dict]]:
    if not isinstance(obj, dict):
        raise RuntimeError("IGE_JSON_ROOT_NOT_OBJECT")
    variables = obj.get("variables")
    datos = obj.get("datos")
    if not isinstance(variables, list) or not all(isinstance(x, str) for x in variables):
        raise RuntimeError("IGE_VARIABLES_NOT_STRING_LIST")
    if not isinstance(datos, list):
        raise RuntimeError("IGE_DATOS_NOT_LIST")
    if len(set(variables)) != len(variables):
        raise RuntimeError("IGE_DUPLICATE_VARIABLE_NAMES")

    rows: list[dict] = []
    qa: list[dict] = []
    for idx, native in enumerate(datos):
        if not isinstance(native, list):
            qa.append({"row_index": idx, "status": "NON_LIST_NATIVE_ROW", "native_type": type(native).__name__})
            continue
        if len(native) != len(variables):
            qa.append({"row_index": idx, "status": "ROW_LENGTH_MISMATCH", "native_length": len(native), "variable_count": len(variables)})
            continue
        record = {name: value for name, value in zip(variables, native)}
        rows.append({"native_row_index": idx, "record": record})
    return variables, rows, qa


def _csv_text(variables: list[str], rows: list[dict]) -> str:
    out = io.StringIO(newline="")
    fields = ["_native_row_index", *variables]
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        rec = {"_native_row_index": row["native_row_index"], **row["record"]}
        writer.writerow(rec)
    return out.getvalue()


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

    with tempfile.TemporaryDirectory(prefix="mn-w3c-f30-v3-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(repo, asset, read_token, local)
        raw = local.read_bytes()
    actual_sha = _sha(raw)
    if len(raw) != int(asset_cfg["bytes"]) or actual_sha != asset_cfg["sha256"]:
        raise RuntimeError(f"F30_ASSET_VERIFICATION_FAILED:{len(raw)}:{actual_sha}")

    obj, source_encoding = _decode_source_json(raw)
    variables, rows, row_qa = _rows_from_ige(obj)
    if "DatoN" not in variables or "DatoT" not in variables:
        raise RuntimeError(f"IGE_DATON_DATOT_MISSING:{variables}")

    daton_idx = variables.index("DatoN")
    datot_idx = variables.index("DatoT")
    daton_blank = sum(1 for row in rows if row["record"].get("DatoN") in (None, ""))
    datot_nonblank = sum(1 for row in rows if row["record"].get("DatoT") not in (None, ""))
    missing_markers = {"*": 0, "..": 0, "-": 0}
    for row in rows:
        val = row["record"].get("DatoT")
        if val in missing_markers:
            missing_markers[val] += 1

    dimension_dictionary = [
        {
            "native_position": i,
            "native_name": name,
            "role": "numeric_value" if i == daton_idx else "text_value_or_flag" if i == datot_idx else "producer_dimension_or_label",
            "semantic_policy": "PRESERVE_NATIVE_NO_RECODE",
        }
        for i, name in enumerate(variables)
    ]
    status = "PASS_SOURCE_NATIVE_IGE_MATRIX_ROWS" if rows else "PASS_VALID_EMPTY_SOURCE_NATIVE_IGE_MATRIX"
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
            "w3b_handoff_path": cfg["handoff_path"],
            "w3b_handoff_blob_sha": handoff_sha,
        },
        "native_structure": "IGE_JSON_VARIABLES_PLUS_DATOS_MATRIX",
        "variables": variables,
        "dimension_dictionary": dimension_dictionary,
        "record_count": len(rows),
        "row_qa": row_qa,
        "DatoN_blank_count": daton_blank,
        "DatoT_nonblank_count": datot_nonblank,
        "DatoT_exact_marker_counts": missing_markers,
        "records": rows,
        "preservation_rules": [
            "Each datos row is mapped positionally to variables without renaming or type coercion.",
            "DatoN and DatoT are retained independently and verbatim.",
            "Empty DatoN and DatoT markers *, .. and - are preserved and never converted to zero.",
            "No airport-period-metric cells are synthesized from independent margins.",
            "IGE, Aena and DGAC observations remain alternative/control evidence unless a later consumer contract explicitly reconciles them."
        ],
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "consumer_join": False,
    }
    jtext = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ctext = _csv_text(variables, rows)

    fresh_team_text, _ = _get_text(repo, branch, team_path, read_token)
    if int(json.loads(fresh_team_text).get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W3C/{stamp}-G{generation}-W3C-F30-IGE4580-source-native-matrix"
    jpath = f"{out_base}/F30-source-native.json"
    cpath = f"{out_base}/F30-source-native.csv"
    rpath = f"{out_base}/extraction-receipt.json"
    handoff_path = "statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F30/92525a31c1907715c00fc82add5df4e53b19b479d18380b107013db6758813ac-extraction-v2.json"

    _put_text(repo, branch, jpath, jtext, write_token, message="result(mn): W3C F30 source-native IGE matrix", immutable=True)
    _put_text(repo, branch, cpath, ctext, write_token, message="result(mn): W3C F30 compact IGE matrix", immutable=True)
    receipt = {
        "schema_version": "4.0.1",
        "worker": "W3C",
        "mission_generation": generation,
        "package": "W3C_F30_IGE4580_SOURCE_NATIVE_MATRIX_V2",
        "source_set_id": "F30",
        "status": status,
        "supersedes_semantic_interpretation_of": "statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F30/92525a31c1907715c00fc82add5df4e53b19b479d18380b107013db6758813ac-extraction.json",
        "release_tag": tag,
        "asset": {"id": asset_cfg["id"], "name": asset_cfg["name"], "bytes": len(raw), "sha256": actual_sha, "verified": True, "source_encoding": source_encoding},
        "w3b_handoff": {"path": cfg["handoff_path"], "blob_sha": handoff_sha, "verified": True},
        "native_structure": "variables+datos",
        "variable_count": len(variables),
        "record_count": len(rows),
        "row_qa_issue_count": len(row_qa),
        "DatoN_blank_count": daton_blank,
        "DatoT_nonblank_count": datot_nonblank,
        "DatoT_exact_marker_counts": missing_markers,
        "outputs": [jpath, cpath],
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "consumer_join": False,
    }
    rtext = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _put_text(repo, branch, rpath, rtext, write_token, message="result(mn): W3C F30 matrix extraction receipt", immutable=True)
    _put_text(repo, branch, handoff_path, rtext, write_token, message="handoff(mn): W3C F30 corrected source-native matrix", immutable=True)

    worker_path = "statistics/recovery-20260920/simple-runtime/worker-W3C.json"
    prior_text, prior_sha = _get_text(repo, branch, worker_path, write_token)
    prior = json.loads(prior_text)
    completed = list(dict.fromkeys((prior.get("cumulative_completed") or []) + [f"GEN{generation}_V401_W3C_F30_IGE4580_SOURCE_NATIVE_MATRIX_V2"]))
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
            "completed_packages": ["P124_F30_IGE4580_SOURCE_NATIVE_MATRIX_V2"],
            "source_sets": ["F30"],
            "record_count": len(rows),
            "variable_count": len(variables),
            "source_encoding": source_encoding,
            "producer_reacquisitions": 0,
            "rights_adjudications": 0,
            "consumer_tables_built": 0,
            "canonical_manifest_index_catalogue_writes": 0,
            "site_deployments": 0,
            "drive_refreshes": 0,
            "scheduler_changes": 0,
            "outputs": [jpath, cpath, rpath, handoff_path],
            "shared_backlog_note": "P115/F162 logical snapshots/F162.pdf was absent in both tested pinned shared archives; do not producer-reacquire. Other backlog members remain executable independently.",
            "next_cursor": ["Continue non-overlapping W3B backlog P114-P123, rotating around P115/F162 member-identity blocker.", "Do not repeat F148 current 2024+ valid-empty package."],
        },
        "cumulative_completed": completed,
        "metrics": {"material_packages_this_window": 1, "members_extracted_this_window": 1, "source_native_records_this_window": len(rows), "producer_reacquisitions_this_window": 0},
        "blocker": None,
    }
    _put_text(repo, branch, worker_path, json.dumps(worker, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message="result(mn): W3C F30 corrected IGE source-native matrix", expected_sha=prior_sha, immutable=False)
    return {"schema_version": "1.0.0", "complete": True, "results": [{"source_set_id": "F30", "status": status, "record_count": len(rows), "variable_count": len(variables), "private_handoff": handoff_path}], "failures": [], "private_write_count": 5}
