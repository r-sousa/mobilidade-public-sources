from __future__ import annotations

import csv
import io
import json
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from .extract_w4c_shared import _TableParser, _get_text, _put_text, _sha
from .private_bootstrap import download_release_asset, release_by_tag

_NUMERIC = re.compile(r"(?<!\\w)[+-]?(?:\\d{1,3}(?:[ .]\\d{3})+|\\d+)(?:[,.]\\d+)?(?:\\s*%)?(?!\\w)")
_UNIT = re.compile(r"\\b(?:passageiros?|passengers?|pasajeros?|movimentos?|movements?|operations?|opera[cç][oõ]es|operaciones|voos?|vuelos?|aeronaves?|aircraft|toneladas?|tonnes?|tonnes|t|kg|teu|navios?|vessels?|buques?|gt|arquea[cç][aã]o|gross tonnage|%)\\b", re.I)
_METRICS = {
    "passengers": ("passageir", "passenger", "pasajer"),
    "aircraft_movements": ("movimento", "movement", "opera", "aeronave", "aircraft", "voo", "vuelo"),
    "freight_cargo": ("carga", "cargo", "freight", "mercadoria", "mercancia"),
    "tonnes": ("tonelada", "tonne", " toneladas", " tonnes"),
    "teu": ("teu",),
    "vessels": ("navio", "vessel", "buque", "embarca"),
    "gross_tonnage": ("gross tonnage", "arqueacao", "arqueação", " tonelaje bruto", " gt "),
}


def _fold(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _metric_tags(text: str) -> list[str]:
    f = " " + _fold(text) + " "
    return [name for name, terms in _METRICS.items() if any(term in f for term in terms)]


def _csv(rows: list[dict]) -> str:
    fields = ["locator", "metric_tags", "raw_text", "cells_json", "context_json", "numeric_tokens_json", "unit_tokens_json"]
    out = io.StringIO(newline="")
    w = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({
            "locator": r.get("locator", ""),
            "metric_tags": "|".join(r.get("metric_tags", [])),
            "raw_text": r.get("raw_text", ""),
            "cells_json": json.dumps(r.get("cells", []), ensure_ascii=False, separators=(",", ":")),
            "context_json": json.dumps(r.get("context", []), ensure_ascii=False, separators=(",", ":")),
            "numeric_tokens_json": json.dumps(r.get("numeric_tokens", []), ensure_ascii=False, separators=(",", ":")),
            "unit_tokens_json": json.dumps(r.get("unit_tokens", []), ensure_ascii=False, separators=(",", ":")),
        })
    return out.getvalue()


def _html_extract(data: bytes) -> tuple[list[dict], list[dict], dict]:
    text = data.decode("utf-8", errors="replace")
    p = _TableParser(); p.feed(text)
    candidates: list[dict] = []; admitted: list[dict] = []
    for ti, table in enumerate(p.tables, 1):
        header = table[:2]
        header_text = " | ".join(" | ".join(x) for x in header)
        for ri, row in enumerate(table, 1):
            raw = " | ".join(row)
            nums = _NUMERIC.findall(raw)
            if not nums:
                continue
            context_text = header_text + " | " + raw
            rec = {
                "locator": f"html:table={ti}:row={ri}",
                "cells": row,
                "context": header,
                "raw_text": raw,
                "metric_tags": _metric_tags(context_text),
                "numeric_tokens": nums,
                "unit_tokens": _UNIT.findall(context_text),
            }
            candidates.append(rec)
            if rec["metric_tags"]:
                admitted.append(rec)
    links = re.findall(r"href=[\"']([^\"']+)[\"']", text, flags=re.I)
    return candidates, admitted, {"method": "stdlib_html_tables_numeric_rows_v1", "table_count": len(p.tables), "embedded_link_count": len(links), "external_links_followed": 0}


def _pdf_extract(data: bytes) -> tuple[list[dict], list[dict], dict]:
    reader = PdfReader(io.BytesIO(data), strict=False)
    candidates: list[dict] = []; admitted: list[dict] = []
    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode="layout") or ""
        lines = [" ".join(x.split()) for x in text.splitlines()]
        nonempty: list[str] = []
        for line_no, raw in enumerate(lines, 1):
            if not raw:
                continue
            context = nonempty[-3:]
            nums = _NUMERIC.findall(raw)
            if nums:
                combined = " | ".join(context + [raw])
                rec = {
                    "locator": f"pdf:page={page_no}:line={line_no}",
                    "raw_text": raw,
                    "context": context,
                    "metric_tags": _metric_tags(combined),
                    "numeric_tokens": nums,
                    "unit_tokens": _UNIT.findall(combined),
                }
                candidates.append(rec)
                if rec["metric_tags"]:
                    admitted.append(rec)
            nonempty.append(raw)
    return candidates, admitted, {"method": "pypdf_layout_numeric_lines_with_3line_context_v1", "page_count": len(reader.pages)}


def _resolve_member(names: list[str], logical: str) -> str:
    if logical in names:
        return logical
    suffix = "/" + logical.lstrip("/")
    matches = [n for n in names if n.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"ARCHIVE_MEMBER_MISSING:{logical}")
    raise RuntimeError(f"ARCHIVE_MEMBER_AMBIGUOUS:{logical}:{matches[:10]}")


def run(cfg: dict, read_token: str, write_token: str) -> dict:
    if not write_token:
        raise RuntimeError("PRIVATE_SINK_TOKEN_REQUIRED_FOR_W3C_EXTRACTION")
    repo = cfg["private_repository"]; branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"]); tag = cfg["release_tag"]; asset_cfg = cfg["asset"]
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
    with tempfile.TemporaryDirectory(prefix="mn-w3c-shared-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(repo, asset, read_token, local)
        archive = local.read_bytes()
    if len(archive) != int(asset_cfg["bytes"]) or _sha(archive) != asset_cfg["sha256"]:
        raise RuntimeError(f"ARCHIVE_VERIFICATION_FAILED:{len(archive)}:{_sha(archive)}")

    results: dict[str, dict] = {}; payloads: dict[str, tuple[str, str]] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        names = zf.namelist()
        for fid, spec in cfg["members"].items():
            handoff_text, handoff_sha = _get_text(repo, branch, spec["handoff_path"], read_token)
            if handoff_sha != spec["handoff_blob_sha"]:
                raise RuntimeError(f"W3B_HANDOFF_BLOB_MISMATCH:{fid}:{handoff_sha}")
            handoff = json.loads(handoff_text)
            if handoff.get("worker") != "W3B" or fid not in (handoff.get("field_ids") or []):
                raise RuntimeError(f"W3B_HANDOFF_IDENTITY_MISMATCH:{fid}")
            preserved = handoff.get("preserved_input") or {}
            if preserved.get("release_tag") != tag or preserved.get("asset") != spec["path"]:
                raise RuntimeError(f"W3B_HANDOFF_RELEASE_MEMBER_MISMATCH:{fid}")
            actual_path = _resolve_member(names, spec["path"])
            member = zf.read(actual_path); member_sha = _sha(member)
            if spec["path"].lower().endswith(".html"):
                candidates, admitted, method = _html_extract(member)
            elif spec["path"].lower().endswith(".pdf"):
                candidates, admitted, method = _pdf_extract(member)
            else:
                raise RuntimeError(f"UNSUPPORTED_MEMBER_TYPE:{fid}:{spec['path']}")
            status = "PASS_EXPLICIT_SOURCE_NATIVE_METRIC_ROWS" if admitted else "PASS_VALID_EMPTY_PRESERVED_SCOPE_NO_EXPLICIT_METRIC_ROWS"
            identity = {
                "release_tag": tag, "release_id": release.get("id"),
                "archive_asset_id": asset_cfg["id"], "archive_name": asset_cfg["name"],
                "archive_bytes": asset_cfg["bytes"], "archive_sha256": asset_cfg["sha256"],
                "archive_verified_once_before_extraction": True,
                "w3b_handoff_path": spec["handoff_path"], "w3b_handoff_blob_sha": handoff_sha,
                "logical_member_path": spec["path"], "actual_archive_member_path": actual_path,
                "member_path_resolution": "EXACT" if actual_path == spec["path"] else "UNIQUE_PREFIXED_SUFFIX_MATCH",
                "member_bytes": len(member), "member_sha256": member_sha,
                "member_hash_contract": "COMPUTED_FROM_ARCHIVE_AFTER_EXACT_HANDOFF_AND_ARCHIVE_VERIFICATION",
            }
            payload = {
                "schema_version": "4.0.1", "worker": "W3C", "mission_generation": generation,
                "source_set_id": fid, "producer": spec["producer"], "product": spec["product"], "status": status,
                "source_identity": identity, "extraction_method": method,
                "numeric_candidate_count": len(candidates), "admitted_row_count": len(admitted),
                "admitted_rows": admitted, "candidate_rows_for_qa": candidates,
                "normalization_guards": spec["guards"], "producer_reacquisition": False,
                "rights_adjudication": False, "consumer_join": False,
                "semantic_note": "Metric tags are admitted only from explicit row/header or local page-line context; no cross-source addition, annualization, OD synthesis, or missing-to-zero conversion is performed."
            }
            payloads[fid] = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", _csv(admitted))
            results[fid] = {
                "source_set_id": fid, "status": status, "producer": spec["producer"], "product": spec["product"],
                "logical_member_path": spec["path"], "actual_archive_member_path": actual_path,
                "member_bytes": len(member), "member_sha256": member_sha, "w3b_handoff_blob_sha": handoff_sha,
                "numeric_candidate_count": len(candidates), "admitted_row_count": len(admitted),
                "extraction_method": method,
            }

    fresh_team_text, _ = _get_text(repo, branch, team_path, read_token)
    if int(json.loads(fresh_team_text).get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W3C/{stamp}-G{generation}-W3C-shared-rhomolo-aviation-ports-extraction"
    handoffs: dict[str, str] = {}; writes = 0
    for fid, result in results.items():
        jpath = f"{out_base}/{fid}/{fid.lower()}-source-native.json"; cpath = f"{out_base}/{fid}/{fid.lower()}-source-native.csv"
        jtext, ctext = payloads[fid]
        _put_text(repo, branch, jpath, jtext, write_token, message=f"result(mn): W3C {fid} source-native extraction", immutable=True)
        _put_text(repo, branch, cpath, ctext, write_token, message=f"result(mn): W3C {fid} compact extraction", immutable=True); writes += 2
        handoff_path = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/{fid}/shared-archive-{asset_cfg['sha256']}-w3c-extraction.json"
        receipt = {
            "schema_version": "4.0.1", "worker": "W3C", "mission_generation": generation,
            "package": "W3C_SHARED_RHOMOLO_AVIATION_PORTS_MEMBER_EXTRACTION", "source_set_id": fid,
            "status": result["status"], "release_tag": tag,
            "archive": {"asset_id": asset_cfg["id"], "name": asset_cfg["name"], "bytes": asset_cfg["bytes"], "sha256": asset_cfg["sha256"], "verified_once_before_member_extraction": True},
            "w3b_handoff": {"path": cfg["members"][fid]["handoff_path"], "blob_sha": result["w3b_handoff_blob_sha"], "verified": True},
            "member": {"logical_path": result["logical_member_path"], "actual_archive_path": result["actual_archive_member_path"], "bytes": result["member_bytes"], "sha256": result["member_sha256"]},
            "extraction_method": result["extraction_method"], "numeric_candidate_count": result["numeric_candidate_count"], "admitted_row_count": result["admitted_row_count"],
            "producer_reacquisition": False, "rights_adjudication": False, "consumer_join": False,
            "outputs": [jpath, cpath],
        }
        rtext = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        rpath = f"{out_base}/{fid}/extraction-receipt.json"
        _put_text(repo, branch, rpath, rtext, write_token, message=f"result(mn): W3C {fid} extraction receipt", immutable=True)
        _put_text(repo, branch, handoff_path, rtext, write_token, message=f"handoff(mn): W3C {fid} shared archive extraction", immutable=True); writes += 2
        handoffs[fid] = handoff_path

    family = {
        "schema_version": "4.0.1", "worker": "W3C", "mission_generation": generation,
        "package": "W3C_SHARED_RHOMOLO_AVIATION_PORTS_MEMBER_EXTRACTION",
        "status": "PASS_SHARED_ARCHIVE_VERIFIED_EIGHT_HANDOFFS_EXTRACTED",
        "release_tag": tag,
        "archive": {"asset_id": asset_cfg["id"], "name": asset_cfg["name"], "bytes": asset_cfg["bytes"], "sha256": asset_cfg["sha256"], "verified_once_before_member_extraction": True},
        "members": results, "handoffs": handoffs,
        "producer_reacquisition": False, "rights_adjudication": False, "canonical_catalogue_write": False,
    }
    family_path = f"{out_base}/family-receipt.json"
    _put_text(repo, branch, family_path, json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message="result(mn): W3C shared aviation ports family receipt", immutable=True); writes += 1

    worker_path = "statistics/recovery-20260920/simple-runtime/worker-W3C.json"
    prior_text, prior_sha = _get_text(repo, branch, worker_path, write_token); prior = json.loads(prior_text)
    completed = list(dict.fromkeys((prior.get("cumulative_completed") or []) + ["GEN45_V401_W3C_P115_P122_SHARED_ARCHIVE_EXTRACTION"]))
    worker = {
        "schema_version": "4.0.1", "worker": "W3C", "team": "W3", "partner": "C", "mission_generation": generation,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "READY_CONTINUE_WINDOW", "elastic_state": "ACTIVE_W3B_P114_P124_EXTRACTION_BACKLOG", "current_task": None,
        "last_output": family_path,
        "window": {
            "mission_generation": generation, "phase": "CLEANUP_NORMALIZATION_COMPLETENESS",
            "work_window_contract": "v4.0.1 multi-package; eight non-overlapping W3B handoffs drained in one shared-archive family operation",
            "material_packages": 8, "source_sets": sorted(results), "archive_verified_once": True,
            "archive_sha256": asset_cfg["sha256"], "member_results": results,
            "producer_reacquisitions": 0, "rights_adjudications": 0, "consumer_tables_built": 0,
            "canonical_manifest_index_catalogue_writes": 0, "site_deployments": 0, "drive_refreshes": 0, "scheduler_changes": 0,
            "outputs": [family_path, *[handoffs[k] for k in sorted(handoffs)]],
            "next_cursor": ["Continue W3B backlog with P114/F166, P123/F10 and P124/F30 only if still CURRENT and non-overlapping.", "Do not repeat F148 current 2024+ valid-empty rail package."],
        },
        "cumulative_completed": completed,
        "metrics": {"material_packages_this_window": 8, "shared_archives_verified_this_window": 1, "members_extracted_this_window": 8, "producer_reacquisitions_this_window": 0},
        "blocker": None,
    }
    _put_text(repo, branch, worker_path, json.dumps(worker, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message="result(mn): W3C shared preserved aviation ports extraction", expected_sha=prior_sha, immutable=False)

    return {
        "schema_version": "1.0.0", "private_repository": repo, "private_release_tag": tag,
        "results": [{"source_set_id": fid, "status": r["status"], "member_sha256": r["member_sha256"], "member_bytes": r["member_bytes"], "admitted_row_count": r["admitted_row_count"], "private_handoff": handoffs[fid]} for fid, r in sorted(results.items())],
        "failures": [], "complete": True, "family_output": family_path, "private_write_count": writes + 1,
    }
