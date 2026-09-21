from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import re
import tempfile
import unicodedata
import urllib.parse
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests
from pypdf import PdfReader

from .private_bootstrap import download_release_asset, release_by_tag

API = "https://api.github.com"
UA = "MobilidadeNorte-W4CSharedExtractor/1.0"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _get_text(repo: str, branch: str, path: str, token: str) -> tuple[str, str]:
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}"
    r = requests.get(url, params={"ref": branch}, headers=_headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(f"PRIVATE_CONTENT_READ_FAILED:{path}:{r.status_code}:{r.text[:300]}")
    obj = r.json()
    return base64.b64decode(obj["content"]).decode("utf-8"), obj["sha"]


def _put_text(
    repo: str,
    branch: str,
    path: str,
    text: str,
    token: str,
    *,
    message: str,
    expected_sha: str | None = None,
    immutable: bool = False,
) -> dict:
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}"
    g = requests.get(url, params={"ref": branch}, headers=_headers(token), timeout=120)
    existing_sha = None
    if g.status_code == 200:
        obj = g.json()
        existing = base64.b64decode(obj["content"]).decode("utf-8")
        if existing == text:
            return {"path": path, "status": "IDENTICAL_ALREADY_PRESENT", "sha": obj["sha"]}
        if immutable:
            raise RuntimeError(f"IMMUTABLE_PRIVATE_OUTPUT_CONFLICT:{path}")
        existing_sha = obj["sha"]
        if expected_sha is not None and existing_sha != expected_sha:
            raise RuntimeError(f"PRIVATE_CONTENT_STALE_SHA:{path}:{existing_sha}")
    elif g.status_code != 404:
        raise RuntimeError(f"PRIVATE_CONTENT_LOOKUP_FAILED:{path}:{g.status_code}:{g.text[:300]}")
    elif expected_sha is not None:
        raise RuntimeError(f"PRIVATE_CONTENT_EXPECTED_EXISTING:{path}")

    body = {
        "message": message,
        "branch": branch,
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }
    if existing_sha:
        body["sha"] = existing_sha
    r = requests.put(url, headers={**_headers(token), "Content-Type": "application/json"}, json=body, timeout=120)
    if not r.ok:
        raise RuntimeError(f"PRIVATE_CONTENT_WRITE_FAILED:{path}:{r.status_code}:{r.text[:300]}")
    obj = r.json()
    return {"path": path, "status": "WRITTEN", "commit": obj["commit"]["sha"], "sha": obj["content"]["sha"]}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(cell for cell in self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None


_NUMERIC = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:[,.]\d+)?(?:\s*%)?(?!\w)")
_UNIT = re.compile(r"\b(?:tep|ktep|mtep|twh|gwh|mwh|kwh|tj|gj|mj|m3|m³|nm3|nm³|kt|toneladas?|tonnes?|litros?|litres?|kg|%)\b", re.I)
_TRANSPORT_TERMS = ("transport", "transporte", "transportes", "mobilidade", "mobilidad", "mobility")
_ROAD_TERMS = (
    "transporte por carretera",
    "road transport",
    "automocion",
    "automovil",
    "automotive",
    "carburante de automocion",
    "uso automocion",
)


def _extract_html(fid: str, data: bytes) -> tuple[list[dict], list[dict], str]:
    text = data.decode("utf-8", errors="replace")
    parser = _TableParser()
    parser.feed(text)
    candidates: list[dict] = []
    admitted: list[dict] = []
    for ti, table in enumerate(parser.tables, 1):
        for ri, row in enumerate(table, 1):
            raw = " | ".join(row)
            folded = _fold(raw)
            matched = [term for term in _TRANSPORT_TERMS if term in folded]
            if not matched:
                continue
            rec = {
                "table_index": ti,
                "row_index": ri,
                "cells": row,
                "raw_text": raw,
                "matched_terms": matched,
                "numeric_tokens": _NUMERIC.findall(raw),
                "unit_tokens": _UNIT.findall(raw),
            }
            candidates.append(rec)
            if _NUMERIC.search(raw):
                admitted.append(rec)
    if not candidates:
        plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
        for li, line in enumerate(plain.splitlines(), 1):
            raw = " ".join(line.split())
            if not raw:
                continue
            folded = _fold(raw)
            matched = [term for term in _TRANSPORT_TERMS if term in folded]
            if matched:
                candidates.append(
                    {
                        "line_no": li,
                        "raw_text": raw,
                        "matched_terms": matched,
                        "numeric_tokens": _NUMERIC.findall(raw),
                        "unit_tokens": _UNIT.findall(raw),
                        "qa_only": True,
                    }
                )
    return candidates, admitted, "stdlib_html_table_parser_v1"


def _extract_pdf(fid: str, data: bytes) -> tuple[list[dict], list[dict], str]:
    reader = PdfReader(io.BytesIO(data), strict=False)
    terms = _TRANSPORT_TERMS if fid == "F176" else _ROAD_TERMS
    candidates: list[dict] = []
    admitted: list[dict] = []
    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode="layout") or ""
        for line_no, line in enumerate(text.splitlines(), 1):
            raw = " ".join(line.split())
            if not raw:
                continue
            folded = _fold(raw)
            matched = [term for term in terms if term in folded]
            if not matched:
                continue
            rec = {
                "page": page_no,
                "line_no": line_no,
                "raw_text": raw,
                "matched_terms": matched,
                "numeric_tokens": _NUMERIC.findall(raw),
                "unit_tokens": _UNIT.findall(raw),
            }
            candidates.append(rec)
            if _NUMERIC.search(raw):
                admitted.append(rec)
    return candidates, admitted, "pypdf_layout_pagewise_v1"


def _csv_text(rows: list[dict]) -> str:
    sio = io.StringIO(newline="")
    fields = [
        "table_index",
        "row_index",
        "page",
        "line_no",
        "raw_text",
        "matched_terms_json",
        "cells_json",
        "numeric_tokens_json",
        "unit_tokens_json",
    ]
    writer = csv.DictWriter(sio, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "table_index": row.get("table_index", ""),
                "row_index": row.get("row_index", ""),
                "page": row.get("page", ""),
                "line_no": row.get("line_no", ""),
                "raw_text": row.get("raw_text", ""),
                "matched_terms_json": json.dumps(row.get("matched_terms", []), ensure_ascii=False, separators=(",", ":")),
                "cells_json": json.dumps(row.get("cells", []), ensure_ascii=False, separators=(",", ":")),
                "numeric_tokens_json": json.dumps(row.get("numeric_tokens", []), ensure_ascii=False, separators=(",", ":")),
                "unit_tokens_json": json.dumps(row.get("unit_tokens", []), ensure_ascii=False, separators=(",", ":")),
            }
        )
    return sio.getvalue()


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
    asset = next((x for x in release.get("assets", []) if int(x["id"]) == int(asset_cfg["id"])), None)
    if not asset:
        raise RuntimeError("PINNED_RELEASE_ASSET_ID_NOT_FOUND")
    if asset["name"] != asset_cfg["name"] or int(asset["size"]) != int(asset_cfg["bytes"]):
        raise RuntimeError("PINNED_RELEASE_ASSET_METADATA_MISMATCH")
    api_digest = str(asset.get("digest") or "").removeprefix("sha256:")
    if api_digest and api_digest != asset_cfg["sha256"]:
        raise RuntimeError("PINNED_RELEASE_ASSET_DIGEST_METADATA_MISMATCH")

    with tempfile.TemporaryDirectory(prefix="mn-w4c-shared-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(private_repo, asset, read_token, local)
        data = local.read_bytes()
    actual_sha = _sha(data)
    if len(data) != int(asset_cfg["bytes"]) or actual_sha != asset_cfg["sha256"]:
        raise RuntimeError(f"ARCHIVE_VERIFICATION_FAILED:{len(data)}:{actual_sha}")

    members = cfg["members"]
    results: dict[str, dict] = {}
    outputs: list[tuple[str, str, bool]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        for fid, spec in members.items():
            member_path = spec["path"]
            if member_path not in names:
                raise RuntimeError(f"ARCHIVE_MEMBER_MISSING:{fid}:{member_path}")
            member = zf.read(member_path)
            member_sha = _sha(member)
            if member_path.lower().endswith(".html"):
                candidates, admitted, method = _extract_html(fid, member)
            elif member_path.lower().endswith(".pdf"):
                candidates, admitted, method = _extract_pdf(fid, member)
            else:
                raise RuntimeError(f"UNSUPPORTED_MEMBER_TYPE:{fid}:{member_path}")

            status = "PASS_EXPLICIT_MOBILITY_ROWS" if admitted else "PASS_VALID_EMPTY_EXPLICIT_MOBILITY_SCOPE"
            source_identity = {
                "release_tag": release_tag,
                "release_id": release.get("id"),
                "archive_asset_id": asset_cfg["id"],
                "archive_name": asset_cfg["name"],
                "archive_bytes": asset_cfg["bytes"],
                "archive_sha256": asset_cfg["sha256"],
                "archive_verified_once_before_extraction": True,
                "member_path": member_path,
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
            jtext = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ctext = _csv_text(admitted)
            results[fid] = {
                "source_set_id": fid,
                "status": status,
                "member_path": member_path,
                "member_bytes": len(member),
                "member_sha256": member_sha,
                "explicit_candidate_count": len(candidates),
                "admitted_row_count": len(admitted),
                "extraction_method": method,
            }
            # Paths are filled after the common output directory stamp is known.
            results[fid]["_json_text"] = jtext
            results[fid]["_csv_text"] = ctext

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W4C/{stamp}-G39-W4C-shared-rhomolo-energy-extraction"
    handoffs: dict[str, str] = {}
    for fid, result in results.items():
        json_path = f"{out_base}/{fid}/{fid.lower()}-source-native.json"
        csv_path = f"{out_base}/{fid}/{fid.lower()}-source-native.csv"
        jtext = result.pop("_json_text")
        ctext = result.pop("_csv_text")
        outputs.extend([(json_path, jtext, True), (csv_path, ctext, True)])
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
                "path": result["member_path"],
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
        rtext = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        outputs.extend([(f"{out_base}/{fid}/extraction-receipt.json", rtext, True), (handoff, rtext, True)])
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
    outputs.append((family_path, json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n", True))

    # Recheck generation immediately before any private write.
    fresh_team_text, _ = _get_text(
        private_repo,
        branch,
        "statistics/recovery-20260920/simple-runtime/team-missions.json",
        read_token,
    )
    if int(json.loads(fresh_team_text).get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")

    write_results = []
    for path, text, immutable in outputs:
        write_results.append(
            _put_text(
                private_repo,
                branch,
                path,
                text,
                write_token,
                message=f"result(mn): W4C shared extraction {Path(path).name}",
                immutable=immutable,
            )
        )

    worker_path = "statistics/recovery-20260920/simple-runtime/worker-W4C.json"
    prior_text, prior_sha = _get_text(private_repo, branch, worker_path, write_token)
    prior = json.loads(prior_text)
    worker = {
        "schema_version": "4.0.1",
        "worker": "W4C",
        "team": "W4",
        "partner": "C",
        "mission_generation": generation,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "READY_CONTINUE_WINDOW",
        "elastic_state": "ACTIVE_COMPLETENESS_AND_SHARED_ARCHIVE_EXTRACTION",
        "current_task": None,
        "last_output": family_path,
        "window": {
            "mission_generation": generation,
            "phase": "CLEANUP_NORMALIZATION_COMPLETENESS",
            "work_window_contract": "v4.0.1 multi-package; shared archive extraction is one material family and does not end the window",
            "material_packages": 1,
            "package": "W4C_SHARED_RHOMOLO_ENERGY_MEMBER_EXTRACTION",
            "archive_verified_once": True,
            "archive_sha256": asset_cfg["sha256"],
            "member_results": results,
            "producer_reacquisitions": 0,
            "rights_adjudications": 0,
            "consumer_tables_built": 0,
            "canonical_manifest_index_catalogue_writes": 0,
            "site_deployments": 0,
            "drive_refreshes": 0,
            "scheduler_changes": 0,
            "outputs": [family_path, *[handoffs[k] for k in sorted(handoffs)]],
            "next_cursor": [
                "Continue the same W4C work window with changed P1 externalities/resources completeness reconciliation using these extraction results.",
                "Then reconcile W4B context/accessibility and remaining lineage/extraction backlog if materially changed.",
            ],
        },
        "cumulative_completed": list(
            dict.fromkeys((prior.get("cumulative_completed") or []) + ["GEN39_V401_W4C_SHARED_ARCHIVE_F169_F170_F176_F179_EXTRACTION"])
        ),
        "metrics": {
            "material_packages_this_window": 1,
            "shared_archives_verified_this_window": 1,
            "members_extracted_this_window": 4,
            "producer_reacquisitions_this_window": 0,
            "rights_adjudications_this_window": 0,
        },
        "blocker": None,
    }
    _put_text(
        private_repo,
        branch,
        worker_path,
        json.dumps(worker, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        write_token,
        message="result(mn): W4C shared preserved energy extraction",
        expected_sha=prior_sha,
        immutable=False,
    )

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
        "private_write_count": len(write_results) + 1,
    }
