from __future__ import annotations

import io
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .extract_w4c_shared import (
    _csv_text,
    _extract_html,
    _extract_pdf,
    _get_text,
    _put_text,
    _sha,
)
from .private_bootstrap import download_release_asset, release_by_tag


def _resolve_member(names: list[str], logical_path: str) -> str:
    if logical_path in names:
        return logical_path
    suffix = "/" + logical_path.lstrip("/")
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"ARCHIVE_MEMBER_MISSING:{logical_path}")
    raise RuntimeError(f"ARCHIVE_MEMBER_AMBIGUOUS:{logical_path}:{matches[:10]}")


def run(cfg: dict, read_token: str, write_token: str) -> dict:
    if not write_token:
        raise RuntimeError("PRIVATE_SINK_TOKEN_REQUIRED_FOR_W4C_EXTRACTION")

    private_repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    release_tag = cfg["release_tag"]
    asset_cfg = cfg["asset"]

    team_text, _ = _get_text(
        private_repo,
        branch,
        "statistics/recovery-20260920/simple-runtime/team-missions.json",
        read_token,
    )
    team = json.loads(team_text)
    if int(team.get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED")
    w4c = ((team.get("teams") or {}).get("W4") or {}).get("C") or {}
    queue_text = " ".join(w4c.get("queue") or []).lower()
    if w4c.get("worker") != "W4C" or "f169" not in queue_text or "f179" not in queue_text:
        raise RuntimeError("W4C_CURRENT_MISSION_NO_LONGER_AUTHORIZES_SHARED_ARCHIVE")

    release = release_by_tag(private_repo, release_tag, read_token)
    asset = next(
        (x for x in release.get("assets", []) if int(x["id"]) == int(asset_cfg["id"])),
        None,
    )
    if not asset:
        raise RuntimeError("PINNED_RELEASE_ASSET_ID_NOT_FOUND")
    if asset["name"] != asset_cfg["name"] or int(asset["size"]) != int(asset_cfg["bytes"]):
        raise RuntimeError("PINNED_RELEASE_ASSET_METADATA_MISMATCH")
    api_digest = str(asset.get("digest") or "").removeprefix("sha256:")
    if api_digest and api_digest != asset_cfg["sha256"]:
        raise RuntimeError("PINNED_RELEASE_ASSET_DIGEST_METADATA_MISMATCH")

    with tempfile.TemporaryDirectory(prefix="mn-w4c-shared-v2-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(private_repo, asset, read_token, local)
        archive_bytes = local.read_bytes()

    actual_sha = _sha(archive_bytes)
    if len(archive_bytes) != int(asset_cfg["bytes"]) or actual_sha != asset_cfg["sha256"]:
        raise RuntimeError(f"ARCHIVE_VERIFICATION_FAILED:{len(archive_bytes)}:{actual_sha}")

    results: dict[str, dict] = {}
    payloads: dict[str, tuple[str, str]] = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = zf.namelist()
        for fid, spec in cfg["members"].items():
            logical_path = spec["path"]
            actual_path = _resolve_member(names, logical_path)
            member = zf.read(actual_path)
            member_sha = _sha(member)

            if logical_path.lower().endswith(".html"):
                candidates, admitted, method = _extract_html(fid, member)
            elif logical_path.lower().endswith(".pdf"):
                candidates, admitted, method = _extract_pdf(fid, member)
            else:
                raise RuntimeError(f"UNSUPPORTED_MEMBER_TYPE:{fid}:{logical_path}")

            status = (
                "PASS_EXPLICIT_MOBILITY_ROWS"
                if admitted
                else "PASS_VALID_EMPTY_EXPLICIT_MOBILITY_SCOPE"
            )
            source_identity = {
                "release_tag": release_tag,
                "release_id": release.get("id"),
                "archive_asset_id": asset_cfg["id"],
                "archive_name": asset_cfg["name"],
                "archive_bytes": asset_cfg["bytes"],
                "archive_sha256": asset_cfg["sha256"],
                "archive_verified_once_before_extraction": True,
                "logical_member_path": logical_path,
                "actual_archive_member_path": actual_path,
                "member_path_resolution": (
                    "EXACT" if actual_path == logical_path else "UNIQUE_PREFIXED_SUFFIX_MATCH"
                ),
                "member_bytes": len(member),
                "member_sha256": member_sha,
            }
            payload = {
                "schema_version": "4.0.1",
                "worker": "W4C",
                "mission_generation": generation,
                "source_set_id": fid,
                "status": status,
                "source_identity": source_identity,
                "extraction_method": method,
                "explicit_candidate_count": len(candidates),
                "admitted_row_count": len(admitted),
                "admitted_rows": admitted,
                "candidate_rows_for_qa": candidates,
                "normalization_guards": spec["guards"],
                "producer_reacquisition": False,
                "rights_adjudication": False,
                "consumer_join": False,
            }
            payloads[fid] = (
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                _csv_text(admitted),
            )
            results[fid] = {
                "source_set_id": fid,
                "status": status,
                "logical_member_path": logical_path,
                "actual_archive_member_path": actual_path,
                "member_path_resolution": source_identity["member_path_resolution"],
                "member_bytes": len(member),
                "member_sha256": member_sha,
                "explicit_candidate_count": len(candidates),
                "admitted_row_count": len(admitted),
                "extraction_method": method,
            }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = (
        "statistics/recovery-20260920/simple-runtime/outputs/W4C/"
        f"{stamp}-G39-W4C-shared-rhomolo-energy-extraction"
    )
    handoffs: dict[str, str] = {}
    private_writes = 0

    fresh_team_text, _ = _get_text(
        private_repo,
        branch,
        "statistics/recovery-20260920/simple-runtime/team-missions.json",
        read_token,
    )
    if int(json.loads(fresh_team_text).get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")

    for fid, result in results.items():
        json_path = f"{out_base}/{fid}/{fid.lower()}-source-native.json"
        csv_path = f"{out_base}/{fid}/{fid.lower()}-source-native.csv"
        json_text, csv_text = payloads[fid]
        _put_text(
            private_repo,
            branch,
            json_path,
            json_text,
            write_token,
            message=f"result(mn): W4C {fid} source-native extraction",
            immutable=True,
        )
        _put_text(
            private_repo,
            branch,
            csv_path,
            csv_text,
            write_token,
            message=f"result(mn): W4C {fid} compact extraction",
            immutable=True,
        )
        private_writes += 2

        handoff = (
            "statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/"
            f"{fid}/shared-archive-{asset_cfg['sha256']}-extraction.json"
        )
        receipt = {
            "schema_version": "4.0.1",
            "worker": "W4C",
            "mission_generation": generation,
            "package": "W4C_SHARED_RHOMOLO_ENERGY_MEMBER_EXTRACTION",
            "source_set_id": fid,
            "status": result["status"],
            "release_tag": release_tag,
            "archive": {
                "asset_id": asset_cfg["id"],
                "name": asset_cfg["name"],
                "bytes": asset_cfg["bytes"],
                "sha256": asset_cfg["sha256"],
                "verified_once_before_member_extraction": True,
            },
            "member": {
                "logical_path": result["logical_member_path"],
                "actual_archive_path": result["actual_archive_member_path"],
                "path_resolution": result["member_path_resolution"],
                "bytes": result["member_bytes"],
                "sha256": result["member_sha256"],
            },
            "extraction_method": result["extraction_method"],
            "explicit_candidate_count": result["explicit_candidate_count"],
            "admitted_row_count": result["admitted_row_count"],
            "valid_empty_is_success": True,
            "producer_reacquisition": False,
            "rights_adjudication": False,
            "consumer_join": False,
            "outputs": [json_path, csv_path],
        }
        receipt_text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        receipt_path = f"{out_base}/{fid}/extraction-receipt.json"
        _put_text(
            private_repo,
            branch,
            receipt_path,
            receipt_text,
            write_token,
            message=f"result(mn): W4C {fid} extraction receipt",
            immutable=True,
        )
        _put_text(
            private_repo,
            branch,
            handoff,
            receipt_text,
            write_token,
            message=f"handoff(mn): W4C {fid} shared archive extraction",
            immutable=True,
        )
        private_writes += 2
        handoffs[fid] = handoff

    family = {
        "schema_version": "4.0.1",
        "worker": "W4C",
        "mission_generation": generation,
        "package": "W4C_SHARED_RHOMOLO_ENERGY_MEMBER_EXTRACTION",
        "status": "PASS_SHARED_ARCHIVE_VERIFIED_FOUR_MEMBERS_EXTRACTED",
        "release_tag": release_tag,
        "archive": {
            "asset_id": asset_cfg["id"],
            "name": asset_cfg["name"],
            "bytes": asset_cfg["bytes"],
            "sha256": asset_cfg["sha256"],
            "verified_once_before_member_extraction": True,
        },
        "members": results,
        "handoffs": handoffs,
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "canonical_catalogue_write": False,
    }
    family_path = f"{out_base}/family-receipt.json"
    _put_text(
        private_repo,
        branch,
        family_path,
        json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        write_token,
        message="result(mn): W4C shared archive family receipt",
        immutable=True,
    )
    private_writes += 1

    return {
        "schema_version": "1.0.0",
        "private_repository": private_repo,
        "private_release_tag": release_tag,
        "results": [
            {
                "source_set_id": fid,
                "status": result["status"],
                "member_sha256": result["member_sha256"],
                "member_bytes": result["member_bytes"],
                "admitted_row_count": result["admitted_row_count"],
                "private_handoff": handoffs[fid],
            }
            for fid, result in sorted(results.items())
        ],
        "failures": [],
        "complete": True,
        "family_output": family_path,
        "private_write_count": private_writes,
    }
