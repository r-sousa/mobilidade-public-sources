from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .extract_w3c_shared import _csv, _html_extract, _pdf_extract, _resolve_member
from .extract_w4c_shared import _get_text, _put_text, _sha
from .private_bootstrap import download_release_asset, release_by_tag


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    q = " ".join(w3c.get("queue") or []).lower()
    required = set(cfg["members"])
    if w3c.get("worker") != "W3C" or not all(fid.lower() in q for fid in required):
        raise RuntimeError("W3C_CURRENT_MISSION_NO_LONGER_AUTHORIZES_SHARED_BACKLOG")

    release = release_by_tag(repo, tag, read_token)
    asset = next((x for x in release.get("assets", []) if int(x["id"]) == int(asset_cfg["id"])), None)
    if not asset:
        raise RuntimeError("PINNED_RELEASE_ASSET_ID_NOT_FOUND")
    if asset["name"] != asset_cfg["name"] or int(asset["size"]) != int(asset_cfg["bytes"]):
        raise RuntimeError("PINNED_RELEASE_ASSET_METADATA_MISMATCH")
    digest = str(asset.get("digest") or "").removeprefix("sha256:")
    if digest and digest != asset_cfg["sha256"]:
        raise RuntimeError("PINNED_RELEASE_ASSET_DIGEST_METADATA_MISMATCH")

    with tempfile.TemporaryDirectory(prefix="mn-w3c-shared-v2-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(repo, asset, read_token, local)
        if local.stat().st_size != int(asset_cfg["bytes"]):
            raise RuntimeError(f"ARCHIVE_SIZE_MISMATCH:{local.stat().st_size}")
        archive_sha = _file_sha256(local)
        if archive_sha != asset_cfg["sha256"]:
            raise RuntimeError(f"ARCHIVE_SHA_MISMATCH:{archive_sha}")

        results: dict[str, dict] = {}
        payloads: dict[str, tuple[str, str]] = {}
        blockers: dict[str, dict] = {}
        with zipfile.ZipFile(local) as zf:
            names = zf.namelist()
            for fid, spec in cfg["members"].items():
                try:
                    handoff_text, handoff_sha = _get_text(repo, branch, spec["handoff_path"], read_token)
                    if handoff_sha != spec["handoff_blob_sha"]:
                        raise RuntimeError(f"W3B_HANDOFF_BLOB_MISMATCH:{handoff_sha}")
                    handoff = json.loads(handoff_text)
                    if handoff.get("worker") != "W3B" or fid not in (handoff.get("field_ids") or []):
                        raise RuntimeError("W3B_HANDOFF_IDENTITY_MISMATCH")
                    preserved = handoff.get("preserved_input") or {}
                    if preserved.get("release_tag") != tag or preserved.get("asset") != spec["path"]:
                        raise RuntimeError("W3B_HANDOFF_RELEASE_MEMBER_MISMATCH")
                    try:
                        actual_path = _resolve_member(names, spec["path"])
                    except Exception as exc:
                        blockers[fid] = {
                            "source_set_id": fid,
                            "status": "BLOCKED_ARCHIVE_MEMBER_IDENTITY",
                            "logical_member_path": spec["path"],
                            "archive_name": asset_cfg["name"],
                            "archive_sha256": asset_cfg["sha256"],
                            "w3b_handoff_path": spec["handoff_path"],
                            "w3b_handoff_blob_sha": handoff_sha,
                            "error": str(exc),
                            "producer_reacquisition": False,
                        }
                        continue
                    member = zf.read(actual_path)
                    member_sha = _sha(member)
                    if spec["path"].lower().endswith(".html"):
                        candidates, admitted, method = _html_extract(member)
                    elif spec["path"].lower().endswith(".pdf"):
                        candidates, admitted, method = _pdf_extract(member)
                    else:
                        raise RuntimeError(f"UNSUPPORTED_MEMBER_TYPE:{spec['path']}")
                    status = "PASS_EXPLICIT_SOURCE_NATIVE_METRIC_ROWS" if admitted else "PASS_VALID_EMPTY_PRESERVED_SCOPE_NO_EXPLICIT_METRIC_ROWS"
                    identity = {
                        "release_tag": tag,
                        "release_id": release.get("id"),
                        "archive_asset_id": asset_cfg["id"],
                        "archive_name": asset_cfg["name"],
                        "archive_bytes": asset_cfg["bytes"],
                        "archive_sha256": asset_cfg["sha256"],
                        "archive_verified_once_before_extraction": True,
                        "w3b_handoff_path": spec["handoff_path"],
                        "w3b_handoff_blob_sha": handoff_sha,
                        "logical_member_path": spec["path"],
                        "actual_archive_member_path": actual_path,
                        "member_path_resolution": "EXACT" if actual_path == spec["path"] else "UNIQUE_PREFIXED_SUFFIX_MATCH",
                        "member_bytes": len(member),
                        "member_sha256": member_sha,
                    }
                    payload = {
                        "schema_version": "4.0.1",
                        "worker": "W3C",
                        "mission_generation": generation,
                        "source_set_id": fid,
                        "producer": spec["producer"],
                        "product": spec["product"],
                        "status": status,
                        "source_identity": identity,
                        "extraction_method": method,
                        "numeric_candidate_count": len(candidates),
                        "admitted_row_count": len(admitted),
                        "admitted_rows": admitted,
                        "candidate_rows_for_qa": candidates,
                        "normalization_guards": spec["guards"],
                        "producer_reacquisition": False,
                        "rights_adjudication": False,
                        "consumer_join": False,
                        "semantic_note": "Only exact preserved member bytes are parsed. Metric rows require explicit local metric context; no cross-source addition, annualization, missing-to-zero conversion or inferred joint cells.",
                    }
                    payloads[fid] = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", _csv(admitted))
                    results[fid] = {
                        "source_set_id": fid,
                        "status": status,
                        "producer": spec["producer"],
                        "product": spec["product"],
                        "logical_member_path": spec["path"],
                        "actual_archive_member_path": actual_path,
                        "member_bytes": len(member),
                        "member_sha256": member_sha,
                        "w3b_handoff_blob_sha": handoff_sha,
                        "numeric_candidate_count": len(candidates),
                        "admitted_row_count": len(admitted),
                        "extraction_method": method,
                    }
                except Exception as exc:
                    blockers[fid] = {
                        "source_set_id": fid,
                        "status": "BLOCKED_MEMBER_EXTRACTION",
                        "logical_member_path": spec.get("path"),
                        "w3b_handoff_path": spec.get("handoff_path"),
                        "error": str(exc),
                        "producer_reacquisition": False,
                    }

    fresh_team_text, _ = _get_text(repo, branch, team_path, read_token)
    if int(json.loads(fresh_team_text).get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W3C/{stamp}-G{generation}-W3C-shared-archive-rotation"
    handoffs: dict[str, str] = {}
    writes = 0
    for fid, result in results.items():
        jpath = f"{out_base}/{fid}/{fid.lower()}-source-native.json"
        cpath = f"{out_base}/{fid}/{fid.lower()}-source-native.csv"
        jtext, ctext = payloads[fid]
        _put_text(repo, branch, jpath, jtext, write_token, message=f"result(mn): W3C {fid} source-native extraction", immutable=True)
        _put_text(repo, branch, cpath, ctext, write_token, message=f"result(mn): W3C {fid} compact extraction", immutable=True)
        writes += 2
        handoff_path = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/{fid}/shared-archive-{asset_cfg['sha256']}-w3c-extraction.json"
        receipt = {
            "schema_version": "4.0.1",
            "worker": "W3C",
            "mission_generation": generation,
            "package": "W3C_SHARED_ARCHIVE_ROTATING_MEMBER_EXTRACTION",
            "source_set_id": fid,
            "status": result["status"],
            "release_tag": tag,
            "archive": {"asset_id": asset_cfg["id"], "name": asset_cfg["name"], "bytes": asset_cfg["bytes"], "sha256": asset_cfg["sha256"], "verified": True},
            "w3b_handoff": {"path": cfg["members"][fid]["handoff_path"], "blob_sha": result["w3b_handoff_blob_sha"], "verified": True},
            "member": {"logical_path": result["logical_member_path"], "actual_archive_path": result["actual_archive_member_path"], "bytes": result["member_bytes"], "sha256": result["member_sha256"]},
            "extraction_method": result["extraction_method"],
            "numeric_candidate_count": result["numeric_candidate_count"],
            "admitted_row_count": result["admitted_row_count"],
            "producer_reacquisition": False,
            "rights_adjudication": False,
            "consumer_join": False,
            "outputs": [jpath, cpath],
        }
        rtext = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        rpath = f"{out_base}/{fid}/extraction-receipt.json"
        _put_text(repo, branch, rpath, rtext, write_token, message=f"result(mn): W3C {fid} extraction receipt", immutable=True)
        _put_text(repo, branch, handoff_path, rtext, write_token, message=f"handoff(mn): W3C {fid} rotating shared archive extraction", immutable=True)
        writes += 2
        handoffs[fid] = handoff_path

    family = {
        "schema_version": "4.0.1",
        "worker": "W3C",
        "mission_generation": generation,
        "package": "W3C_SHARED_ARCHIVE_ROTATING_MEMBER_EXTRACTION",
        "status": "PASS_WITH_ROTATED_BLOCKERS" if results else "NO_MEMBER_MATERIALIZED",
        "release_tag": tag,
        "archive": {"asset_id": asset_cfg["id"], "name": asset_cfg["name"], "bytes": asset_cfg["bytes"], "sha256": asset_cfg["sha256"], "verified": True},
        "members_materialized": results,
        "member_blockers": blockers,
        "handoffs": handoffs,
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "canonical_catalogue_write": False,
    }
    family_path = f"{out_base}/family-receipt.json"
    _put_text(repo, branch, family_path, json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message="result(mn): W3C rotating shared archive family receipt", immutable=True)
    writes += 1

    worker_path = "statistics/recovery-20260920/simple-runtime/worker-W3C.json"
    prior_text, prior_sha = _get_text(repo, branch, worker_path, write_token)
    prior = json.loads(prior_text)
    completed = list(prior.get("cumulative_completed") or [])
    for fid in sorted(results):
        marker = f"GEN{generation}_V401_W3C_{fid}_SHARED_ARCHIVE_EXTRACTION"
        if marker not in completed:
            completed.append(marker)
    f30_already = any("F30_IGE4580_SOURCE_NATIVE_MATRIX_V2" in x for x in completed)
    material_count = len(results) + (1 if f30_already else 0)
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
        "last_output": family_path,
        "window": {
            "mission_generation": generation,
            "phase": "CLEANUP_NORMALIZATION_COMPLETENESS",
            "material_packages": material_count,
            "completed_this_family": sorted(results),
            "blocked_this_family": sorted(blockers),
            "archive_verified_once": True,
            "archive_sha256": asset_cfg["sha256"],
            "member_results": results,
            "member_blockers": blockers,
            "producer_reacquisitions": 0,
            "rights_adjudications": 0,
            "consumer_tables_built": 0,
            "canonical_manifest_index_catalogue_writes": 0,
            "site_deployments": 0,
            "drive_refreshes": 0,
            "scheduler_changes": 0,
            "outputs": [family_path, *[handoffs[k] for k in sorted(handoffs)]],
            "next_cursor": ["Continue P114/F166 and P123/F10 if still current and non-overlapping.", "Resolve shared member blockers only with an exact changed archive/member identity; no producer reacquisition.", "Do not repeat F148 current 2024+ valid-empty package."],
        },
        "cumulative_completed": completed,
        "metrics": {"material_packages_this_window": material_count, "shared_archives_verified_this_window": 1, "members_extracted_this_family": len(results), "member_blockers_this_family": len(blockers), "producer_reacquisitions_this_window": 0},
        "blocker": None if results else {"type": "SHARED_ARCHIVE_MEMBER_IDENTITY", "members": sorted(blockers)},
    }
    _put_text(repo, branch, worker_path, json.dumps(worker, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message="result(mn): W3C rotating shared preserved extraction", expected_sha=prior_sha, immutable=False)

    return {
        "schema_version": "1.0.0",
        "private_repository": repo,
        "private_release_tag": tag,
        "results": [{"source_set_id": fid, "status": result["status"], "member_sha256": result["member_sha256"], "member_bytes": result["member_bytes"], "admitted_row_count": result["admitted_row_count"], "private_handoff": handoffs[fid]} for fid, result in sorted(results.items())],
        "failures": [blockers[fid] for fid in sorted(blockers)],
        "complete": True,
        "family_output": family_path,
        "private_write_count": writes + 1,
    }
