from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from pathlib import Path

import pdfplumber
import yaml
from pypdf import PdfReader

from .extract_w4c_shared import _get_text, _put_text, _sha
from .private_bootstrap import download_release_asset, release_by_tag


def _json_text(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _numeric_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip("\r")
        if len(re.findall(r"\d+(?:[.,]\d+)?", line)) >= 2:
            out.append(line)
    return out


def _verify_receipt(cfg: dict, receipt: dict) -> None:
    sid = cfg["source_set_id"]
    asset = cfg["asset"]
    if receipt.get("source_set_id") != sid:
        raise RuntimeError(f"{sid}:RECEIPT_SOURCE_SET_MISMATCH")
    if receipt.get("native_asset_fingerprint") != cfg["fingerprint"]:
        raise RuntimeError(f"{sid}:RECEIPT_FINGERPRINT_MISMATCH")
    disp = receipt.get("disposition") or {}
    if disp.get("release_tag") != cfg["release_tag"] or disp.get("status") != "PRIVATE_SINK_PRESERVED":
        raise RuntimeError(f"{sid}:RECEIPT_RELEASE_DISPOSITION_MISMATCH")
    match = next((x for x in disp.get("assets") or [] if int(x.get("id", -1)) == int(asset["id"])), None)
    if not match:
        raise RuntimeError(f"{sid}:RECEIPT_ASSET_ID_NOT_FOUND")
    checks = {
        "name": asset["name"],
        "bytes": int(asset["bytes"]),
        "sha256": asset["sha256"],
    }
    for key, expected in checks.items():
        got = match.get(key)
        if key == "bytes":
            got = int(got)
        if got != expected:
            raise RuntimeError(f"{sid}:RECEIPT_ASSET_{key.upper()}_MISMATCH:{got!r}:{expected!r}")


def _extract_pdf(path: Path, cfg: dict, actual_sha: str) -> dict:
    sid = cfg["source_set_id"]
    fp = cfg["fingerprint"]
    asset_name = cfg["asset"]["name"]
    reader = PdfReader(str(path), strict=False)

    inventory_rows: list[dict] = []
    page_text_rows: list[dict] = []
    candidate_rows: list[dict] = []
    machine_tables: list[dict] = []
    candidate_pages: set[int] = set()
    page_numeric: dict[int, list[str]] = {}

    for i, page in enumerate(reader.pages):
        page_no = i + 1
        error = None
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            text = ""
            error = f"{type(exc).__name__}:{exc}"
        nums = _numeric_lines(text)
        heading = bool(re.search(r"(?im)^\s*(tabela|quadro|table|figura|gr[aá]fico)\b", text))
        candidate = len(nums) >= 4 or heading
        if candidate:
            candidate_pages.add(i)
            page_numeric[i] = nums
        try:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
        except Exception:
            width = None
            height = None
        inv = {
            "source_set_id": sid,
            "native_asset_fingerprint": fp,
            "asset_sha256": actual_sha,
            "asset_name": asset_name,
            "page_number": page_no,
            "width_points": width,
            "height_points": height,
            "rotation": getattr(page, "rotation", None),
            "extractable_text": bool(text),
            "text_characters": len(text),
            "text_lines": len(text.splitlines()),
            "numeric_candidate_lines": len(nums),
            "table_candidate_page": candidate,
            "text_extraction_error": error,
        }
        inventory_rows.append(inv)
        page_text_rows.append({
            "source_set_id": sid,
            "native_asset_fingerprint": fp,
            "asset_sha256": actual_sha,
            "asset_name": asset_name,
            "page_number": page_no,
            "text": text,
            "text_extraction_error": error,
        })
        if candidate:
            candidate_rows.append({
                "source_set_id": sid,
                "native_asset_fingerprint": fp,
                "asset_sha256": actual_sha,
                "asset_name": asset_name,
                "page_number": page_no,
                "candidate_type": "TEXT_NUMERIC_OR_TABLE_HEADING_PAGE",
                "numeric_lines": nums,
                "machine_readable_table_emitted": False,
            })

    # Conservative deterministic table extraction: only pages already identified
    # by embedded text, and only line-defined tables found by pdfplumber defaults.
    with pdfplumber.open(str(path)) as pdf:
        if len(pdf.pages) != len(reader.pages):
            raise RuntimeError(f"{sid}:PDF_PAGE_COUNT_DISAGREEMENT:{len(reader.pages)}:{len(pdf.pages)}")
        for i in sorted(candidate_pages):
            page = pdf.pages[i]
            page_no = i + 1
            try:
                found = page.find_tables()
            except Exception as exc:
                candidate_rows.append({
                    "source_set_id": sid,
                    "native_asset_fingerprint": fp,
                    "asset_sha256": actual_sha,
                    "asset_name": asset_name,
                    "page_number": page_no,
                    "candidate_type": "LINE_TABLE_DETECTOR_ERROR",
                    "error": f"{type(exc).__name__}:{exc}",
                    "machine_readable_table_emitted": False,
                })
                continue
            for ti, table in enumerate(found):
                rows = table.extract() or []
                bbox = [float(x) for x in table.bbox]
                max_cols = max((len(r or []) for r in rows), default=0)
                nonempty = sum(1 for r in rows for cell in (r or []) if cell not in (None, ""))
                deterministic = len(rows) >= 2 and max_cols >= 2 and nonempty >= 4
                try:
                    above = page.crop((0, max(0, bbox[1] - 72), page.width, bbox[1])).extract_text() or ""
                except Exception:
                    above = ""
                try:
                    below = page.crop((0, bbox[3], page.width, min(page.height, bbox[3] + 72))).extract_text() or ""
                except Exception:
                    below = ""
                cand = {
                    "source_set_id": sid,
                    "native_asset_fingerprint": fp,
                    "asset_sha256": actual_sha,
                    "asset_name": asset_name,
                    "page_number": page_no,
                    "candidate_type": "PDFPLUMBER_LINE_DEFINED_TABLE",
                    "table_index": ti,
                    "bbox_points": bbox,
                    "row_count": len(rows),
                    "max_column_count": max_cols,
                    "nonempty_cell_count": nonempty,
                    "context_above_72pt": above,
                    "context_below_72pt": below,
                    "machine_readable_table_emitted": deterministic,
                }
                candidate_rows.append(cand)
                if deterministic:
                    machine_tables.append({
                        "source_set_id": sid,
                        "native_asset_fingerprint": fp,
                        "asset_sha256": actual_sha,
                        "asset_name": asset_name,
                        "page_number": page_no,
                        "table_index": ti,
                        "bbox_points": bbox,
                        "context_above_72pt": above,
                        "context_below_72pt": below,
                        "rows": rows,
                        "extraction_method": "pdfplumber.find_tables(default line-defined strategy)",
                        "semantic_interpretation": None,
                    })

    # Mark the text-page candidates that produced at least one deterministic table.
    pages_with_tables = {x["page_number"] for x in machine_tables}
    for row in candidate_rows:
        if row.get("candidate_type") == "TEXT_NUMERIC_OR_TABLE_HEADING_PAGE" and row["page_number"] in pages_with_tables:
            row["machine_readable_table_emitted"] = True

    csv_io = io.StringIO(newline="")
    writer = csv.writer(csv_io, lineterminator="\n")
    writer.writerow(["source_set_id", "native_asset_fingerprint", "asset_sha256", "asset_name", "page_number", "table_index", "row_index", "column_index", "cell_text"])
    for t in machine_tables:
        for ri, row in enumerate(t["rows"]):
            for ci, cell in enumerate(row or []):
                writer.writerow([sid, fp, actual_sha, asset_name, t["page_number"], t["table_index"], ri, ci, "" if cell is None else cell])

    inventory_payload = {
        "schema_version": "1.0.0",
        "worker": "W3C",
        "mission_generation": 57,
        "source_set_id": sid,
        "native_asset_fingerprint": fp,
        "asset": {"name": asset_name, "bytes": path.stat().st_size, "sha256": actual_sha},
        "page_count": len(inventory_rows),
        "pages": inventory_rows,
        "guards": {
            "semantic_normalization_performed": False,
            "validation_counts_interpreted_as_passengers_or_trips": False,
            "imob_variables_semantically_normalized": False,
            "controlled_microdata_touched": False,
        },
    }
    outputs = {
        "page-inventory.json": _json_text(inventory_payload),
        "page-text.jsonl": _jsonl(page_text_rows),
        "table-candidates.jsonl": _jsonl(candidate_rows),
        "machine-tables.jsonl": _jsonl(machine_tables),
        "machine-table-cells.csv": csv_io.getvalue(),
    }
    return {
        "outputs": outputs,
        "page_count": len(inventory_rows),
        "pages_with_text": sum(1 for x in inventory_rows if x["extractable_text"]),
        "candidate_pages": len(candidate_pages),
        "table_candidate_records": len(candidate_rows),
        "machine_table_count": len(machine_tables),
        "machine_table_cell_rows": sum(len(r or []) for t in machine_tables for r in t["rows"]),
    }


def _run_one(cfg: dict, read_token: str, write_token: str) -> dict:
    sid = cfg["source_set_id"]
    repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    item = cfg["item"]

    receipt_text, receipt_blob_sha = _get_text(repo, branch, item["receipt_path"], read_token)
    receipt = json.loads(receipt_text)
    _verify_receipt(item, receipt)

    release = release_by_tag(repo, item["release_tag"], read_token)
    asset_cfg = item["asset"]
    asset = next((x for x in release.get("assets") or [] if int(x.get("id", -1)) == int(asset_cfg["id"])), None)
    if not asset:
        raise RuntimeError(f"{sid}:PINNED_RELEASE_ASSET_ID_NOT_FOUND")
    if asset.get("name") != asset_cfg["name"] or int(asset.get("size", -1)) != int(asset_cfg["bytes"]):
        raise RuntimeError(f"{sid}:PINNED_RELEASE_ASSET_METADATA_MISMATCH")
    digest = str(asset.get("digest") or "").removeprefix("sha256:")
    if digest and digest != asset_cfg["sha256"]:
        raise RuntimeError(f"{sid}:PINNED_RELEASE_DIGEST_MISMATCH:{digest}")

    with tempfile.TemporaryDirectory(prefix=f"mn-w3c-g57-{sid.lower()}-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(repo, asset, read_token, local)
        raw_size = local.stat().st_size
        actual_sha = _sha(local.read_bytes())
        if raw_size != int(asset_cfg["bytes"]) or actual_sha != asset_cfg["sha256"]:
            raise RuntimeError(f"{sid}:ASSET_VERIFICATION_FAILED:{raw_size}:{actual_sha}")
        extracted = _extract_pdf(local, item, actual_sha)

    out_base = item["output_base"]
    output_meta: list[dict] = []
    for name, text in extracted["outputs"].items():
        path = f"{out_base}/{name}"
        _put_text(repo, branch, path, text, write_token, message=f"result(mn): G57 W3C {sid} deterministic PDF descendant {name}", immutable=True)
        output_meta.append({"path": path, "bytes": len(text.encode("utf-8")), "sha256": _hash_text(text)})

    receipt_obj = {
        "schema_version": "1.0.0",
        "worker": "W3C",
        "mission_generation": 57,
        "source_set_id": sid,
        "status": "PASS_EXACT_PRIVATE_RELEASE_BYTES_VERIFIED_AND_DETERMINISTIC_PDF_DESCENDANTS_EMITTED",
        "source_receipt": {"path": item["receipt_path"], "blob_sha": receipt_blob_sha, "fingerprint": item["fingerprint"]},
        "private_release": {"tag": item["release_tag"], "release_id": release.get("id")},
        "asset": {"id": asset_cfg["id"], "name": asset_cfg["name"], "bytes": int(asset_cfg["bytes"]), "sha256": actual_sha, "verified_before_extraction": True},
        "page_count": extracted["page_count"],
        "pages_with_text": extracted["pages_with_text"],
        "candidate_pages": extracted["candidate_pages"],
        "table_candidate_records": extracted["table_candidate_records"],
        "machine_table_count": extracted["machine_table_count"],
        "machine_table_cell_rows": extracted["machine_table_cell_rows"],
        "outputs": output_meta,
        "semantic_guards": {
            "passenger_semantic_normalization": False,
            "validation_counts_relabelled_as_passengers_trips_journeys": False,
            "imob_variables_normalized": False,
            "controlled_microdata_accessed_or_reconstructed": False,
            "producer_reacquisition": False,
            "rights_changed": False,
        },
    }
    rtext = _json_text(receipt_obj)
    rpath = f"{out_base}/extraction-receipt.json"
    _put_text(repo, branch, rpath, rtext, write_token, message=f"receipt(mn): G57 W3C {sid} PDF extraction", immutable=True)
    receipt_obj["receipt_path"] = rpath
    return receipt_obj


def run(config: dict, read_token: str, write_token: str) -> dict:
    repo = config["private_repository"]
    branch = config["private_branch"]
    team_text, _ = _get_text(repo, branch, config["team_missions_path"], read_token)
    team = json.loads(team_text)
    if team.get("schema_version") != "5.2.2" or int(team.get("mission_generation", -1)) != 57:
        raise RuntimeError("CURRENT_G57_SCHEMA_522_NOT_ACTIVE")
    w3c = (((team.get("teams") or {}).get("W3") or {}).get("C") or {})
    mission = str(w3c.get("mission") or "")
    if w3c.get("worker") != "W3C" or "F193" not in mission or "F194" not in mission or "exact-byte" not in mission:
        raise RuntimeError("CURRENT_W3C_MISSION_DOES_NOT_AUTHORIZE_F193_F194_EXACT_BYTE_INGRESS")

    results: list[dict] = []
    failures: list[dict] = []
    for item in config.get("sources") or []:
        scoped = {"private_repository": repo, "private_branch": branch, "item": item, "source_set_id": item["source_set_id"]}
        try:
            results.append(_run_one(scoped, read_token, write_token))
        except Exception as exc:
            failures.append({"source_set_id": item.get("source_set_id"), "error": f"{type(exc).__name__}:{exc}"})

    handoff = {
        "schema_version": "1.0.0",
        "from_worker": "W3C",
        "to_worker": "W2A",
        "mission_generation": 57,
        "status": "READY_AVAILABLE_PACKAGES_FOR_W2A_SEMANTIC_NORMALIZATION" if results else "BLOCKED_NO_EXTRACTED_PACKAGE",
        "results": [{
            "source_set_id": r["source_set_id"],
            "source_fingerprint": r["source_receipt"]["fingerprint"],
            "asset": r["asset"],
            "page_count": r["page_count"],
            "pages_with_text": r["pages_with_text"],
            "table_candidate_records": r["table_candidate_records"],
            "machine_table_count": r["machine_table_count"],
            "receipt_path": r["receipt_path"],
            "outputs": r["outputs"],
        } for r in results],
        "failures": failures,
        "handoff_rules": [
            "W2A owns passenger semantic normalization; W3C descendants are byte-verified extraction evidence only.",
            "For F193, validation events must not be interpreted as passengers/persons/journeys/trips without producer-published semantics.",
            "For F194, only PUBLIC_AGGREGATE_DISSEMINATION is represented; CONTROLLED_MICRODATA_AMP_AML remains out of scope and not acquired.",
            "Exact page/table provenance pointers and source labels/headers/footnotes are retained in page text, table candidate context and raw table cells.",
        ],
    }
    _put_text(repo, branch, config["w2a_handoff_path"], _json_text(handoff), write_token, message="handoff(mn): G57 W3C F193/F194 PDF extraction to W2A", immutable=True)

    # Update W3C state only if G57 remains CURRENT. If the orchestrator has already
    # advanced, keep the append-only packages/handoff and leave current state untouched.
    fresh_team_text, _ = _get_text(repo, branch, config["team_missions_path"], read_token)
    fresh_team = json.loads(fresh_team_text)
    worker_updated = False
    if int(fresh_team.get("mission_generation", -1)) == 57:
        prior_text, prior_sha = _get_text(repo, branch, config["worker_path"], write_token)
        prior = json.loads(prior_text)
        completed = list(dict.fromkeys((prior.get("cumulative_completed") or []) + [f"GEN57_W3C_{r['source_set_id']}_PUBLIC_PDF_EXACT_BYTE_EXTRACTION" for r in results]))
        worker = {
            "schema_version": "5.2.2",
            "worker": "W3C",
            "team": "W3",
            "partner": "C",
            "mission_generation": 57,
            "status": "READY_W2A_SEMANTIC_NORMALIZATION" if results else "BLOCKED_G57_PUBLIC_PDF_BYTE_INGRESS",
            "elastic_state": w3c.get("status"),
            "current_task": None,
            "blocker": failures or None,
            "last_output": config["w2a_handoff_path"],
            "cumulative_completed": completed,
            "metrics": {
                "material_packages_this_window": len(results),
                "producer_reacquisitions_this_window": 0,
                "controlled_microdata_acquisitions_this_window": 0,
                "semantic_normalizations_this_window": 0,
                "scheduler_changes_this_window": 0,
            },
            "window": {
                "mission_generation": 57,
                "phase": team.get("phase"),
                "completed_source_sets": [r["source_set_id"] for r in results],
                "failed_source_sets": failures,
                "w2a_handoff": config["w2a_handoff_path"],
                "next_cursor": "W2A may consume only the exact receipt-pinned descendants listed in the G57 W3C handoff; W3C performs no passenger semantic normalization.",
            },
        }
        _put_text(repo, branch, config["worker_path"], _json_text(worker), write_token, message="result(mn): G57 W3C F193/F194 exact-byte ingress state", expected_sha=prior_sha, immutable=False)
        worker_updated = True

    return {"schema_version": "1.0.0", "complete": bool(results), "results": results, "failures": failures, "w2a_handoff": config["w2a_handoff_path"], "worker_updated": worker_updated}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    read_token = os.environ.get("MN_PRIVATE_READ_TOKEN", "") or os.environ.get("MN_PRIVATE_SINK_TOKEN", "")
    write_token = os.environ.get("MN_PRIVATE_SINK_TOKEN", "")
    if not read_token:
        raise SystemExit("MN_PRIVATE_READ_OR_SINK_TOKEN_MISSING")
    if not write_token:
        raise SystemExit("MN_PRIVATE_SINK_TOKEN_MISSING")
    try:
        result = run(cfg, read_token, write_token)
    except Exception as exc:
        result = {"schema_version": "1.0.0", "complete": False, "results": [], "failures": [{"error": f"{type(exc).__name__}:{exc}"}]}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(_json_text(result), encoding="utf-8")
        print(_json_text(result))
        raise
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(_json_text(result), encoding="utf-8")
    print(_json_text(result))


if __name__ == "__main__":
    main()
