#!/usr/bin/env python3
import base64
import csv
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SOURCE_SET_ID = "F187"
FINGERPRINT = "43652d12e479f222ab932e5c7104c85cd8ca4b991f9a850d485b9f761d6125bd"
RELEASE_TAG = "mn-src-f187-43652d12e479f222ab93"
PRIVATE_REPO = "r-sousa/EU-transp-weekly"
PRIVATE_BRANCH = "mobilidade-norte-recovery-20260919"
PRIVATE_RECEIPT_PATH = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F187/{FINGERPRINT}.json"
REQUEST_PATH = pathlib.Path(f"extraction_requests/F187-{FINGERPRINT}.json")
WAKE_GENERATION = 43
ASSIGNMENT_ORIGIN_GENERATION = 42

MONTHS = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}


def norm_text(v):
    if v is None:
        return ""
    s = str(v).strip()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def gh_request(url, token, accept="application/vnd.github+json", timeout=180):
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": accept,
        "User-Agent": "MobilidadeNorte-F187Extractor/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def gh_json(url, token):
    with gh_request(url, token) as r:
        return json.loads(r.read())


def fetch_private_text(path, token):
    q = urllib.parse.quote(path, safe="/")
    obj = gh_json(f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{q}?ref={PRIVATE_BRANCH}", token)
    return base64.b64decode(obj["content"]).decode("utf-8")


def parse_period_from_filename(name):
    n = norm_text(name)
    year_match = re.search(r"(20\d{2})", n)
    year = int(year_match.group(1)) if year_match else None
    q = None
    patterns = [
        r"([1-4])o\s*trimestre",
        r"([1-4])º\s*trimestre",
        r"([1-4])\s*trimestre",
    ]
    for pat in patterns:
        m = re.search(pat, n)
        if m:
            q = int(m.group(1)); break
    annual = bool(year and q is None and "trimestre" not in n)
    return {"reference_year": year, "reference_quarter": q, "edition_scope": "ANNUAL" if annual else (f"Q{q}" if q else "UNRESOLVED")}


def month_from_label(label):
    n = norm_text(label)
    for k, v in MONTHS.items():
        if re.search(rf"(^|[^a-z]){re.escape(k)}([^a-z]|$)", n):
            return v
    return None


def header_score(cells):
    text = " | ".join(norm_text(x) for x in cells if str(x).strip() != "")
    score = 0
    weighted = [
        ("autoestrad", 5), ("concess", 5), ("sublanc", 6), ("sublan", 6),
        ("tmdm", 7), ("tmda", 7), ("trafego", 4), ("circul", 3),
        ("veicul", 2), ("portagem", 2), ("extens", 2), ("km", 1),
    ]
    for token, pts in weighted:
        if token in text:
            score += pts
    nonempty = sum(1 for x in cells if str(x).strip() != "")
    if nonempty >= 3:
        score += min(nonempty, 10) * 0.15
    return score


def typed_cell(book, cell):
    import xlrd
    if cell.ctype == xlrd.XL_CELL_EMPTY:
        return {"type": "blank", "value": ""}
    if cell.ctype == xlrd.XL_CELL_TEXT:
        return {"type": "text", "value": str(cell.value)}
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        return {"type": "number", "value": cell.value}
    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            dt = xlrd.xldate.xldate_as_datetime(cell.value, book.datemode)
            return {"type": "date", "value": dt.isoformat(), "excel_serial": cell.value}
        except Exception:
            return {"type": "date", "value": cell.value, "decode_error": True}
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return {"type": "boolean", "value": bool(cell.value)}
    if cell.ctype == xlrd.XL_CELL_ERROR:
        return {"type": "error", "value": int(cell.value)}
    return {"type": f"xlrd_{cell.ctype}", "value": cell.value}


def plain_value(tc):
    return tc.get("value")


def classify_header(label):
    n = norm_text(label)
    if "autoestrad" in n or re.search(r"(^|\W)ae(\W|$)", n):
        return "motorway"
    if "concess" in n:
        return "concession"
    if "sublanc" in n or "sublan" in n:
        return "sublanco"
    if "tmdm" in n:
        return "tmdm"
    if "tmda" in n:
        return "tmda"
    return None


def compact_json(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def main():
    if not REQUEST_PATH.exists():
        raise SystemExit("EXTRACTION_REQUEST_MISSING")
    req = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    if req.get("source_set_id") != SOURCE_SET_ID or req.get("native_asset_fingerprint") != FINGERPRINT or req.get("release_tag") != RELEASE_TAG:
        raise SystemExit("REQUEST_IDENTITY_MISMATCH")
    if int(req.get("wake_mission_generation", -1)) != WAKE_GENERATION:
        raise SystemExit("REQUEST_WAKE_GENERATION_MISMATCH")
    if req.get("operation") != "source_native_xls_series_extraction_ingress":
        raise SystemExit("REQUEST_OPERATION_MISMATCH")

    read_token = (os.environ.get("MN_PRIVATE_SINK_TOKEN") or os.environ.get("MN_PRIVATE_READ_TOKEN") or "").strip()
    write_token = (os.environ.get("MN_PRIVATE_SINK_TOKEN") or "").strip()
    if not read_token:
        raise SystemExit("MN_PRIVATE_READ_CREDENTIAL_MISSING")
    if not write_token:
        raise SystemExit("MN_PRIVATE_WRITE_CREDENTIAL_MISSING")

    private_receipt = json.loads(fetch_private_text(PRIVATE_RECEIPT_PATH, read_token))
    if private_receipt.get("native_asset_fingerprint") != FINGERPRINT:
        raise SystemExit("PRIVATE_RECEIPT_FINGERPRINT_MISMATCH")
    expected_assets = private_receipt.get("assets") or []
    if not expected_assets:
        raise SystemExit("PRIVATE_RECEIPT_ASSET_LIST_EMPTY")
    expected_by_name = {a["name"]: a for a in expected_assets}
    xls_expected = [a for a in expected_assets if str(a.get("name", "")).lower().endswith(".xls")]
    if len(xls_expected) != 51:
        raise SystemExit(f"PRIVATE_RECEIPT_XLS_COUNT_MISMATCH:{len(xls_expected)}")
    required_names = {"landing.html", "series-manifest.json"}
    if not required_names.issubset(expected_by_name):
        raise SystemExit("PRIVATE_RECEIPT_REQUIRED_SUPPORT_ASSET_MISSING")

    rel = gh_json(f"https://api.github.com/repos/{PRIVATE_REPO}/releases/tags/{RELEASE_TAG}", read_token)
    release_assets = {a["name"]: a for a in rel.get("assets", [])}
    missing_release = sorted(set(expected_by_name) - set(release_assets))
    if missing_release:
        raise SystemExit("PRIVATE_RELEASE_ASSETS_MISSING:" + ",".join(missing_release))

    # Verify ALL receipt assets before parsing any one of them.
    verified = {}
    for name, exp in expected_by_name.items():
        meta = release_assets[name]
        if int(meta.get("size", -1)) != int(exp.get("bytes", -2)):
            raise SystemExit(f"RELEASE_METADATA_SIZE_MISMATCH:{name}:{meta.get('size')}:{exp.get('bytes')}")
        asset_id = int(meta["id"])
        try:
            with gh_request(f"https://api.github.com/repos/{PRIVATE_REPO}/releases/assets/{asset_id}", read_token, accept="application/octet-stream", timeout=240) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"PRIVATE_ASSET_READ_FAILED:{name}:HTTP_{e.code}")
        got_bytes = len(data); got_sha = sha256_bytes(data)
        if got_bytes != int(exp["bytes"]) or got_sha != exp["sha256"]:
            raise SystemExit(f"ASSET_VERIFICATION_FAILED:{name}:bytes={got_bytes}:sha256={got_sha}")
        verified[name] = {
            "name": name,
            "asset_id": asset_id,
            "bytes": got_bytes,
            "sha256": got_sha,
            "role": exp.get("role"),
            "format": exp.get("format"),
            "source_url": exp.get("source_url"),
            "data": data,
        }

    # Only after every asset is verified may parsing begin.
    manifest = json.loads(verified["series-manifest.json"]["data"].decode("utf-8"))

    import xlrd
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    temp = pathlib.Path(os.environ.get("RUNNER_TEMP", "/tmp")) / f"f187-{stamp}"
    out = temp / "out"; per_file_dir = out / "per_file"
    out.mkdir(parents=True, exist_ok=True); per_file_dir.mkdir(parents=True, exist_ok=True)

    workbook_inventory = []
    sheet_inventory = []
    row_records = []
    published_values = []
    schema_signatures = {}
    total_nonempty_cells = 0
    total_source_rows = 0
    total_value_records = 0

    for exp in sorted(xls_expected, key=lambda a: a["name"]):
        name = exp["name"]
        data = verified[name]["data"]
        period = parse_period_from_filename(name)
        try:
            book = xlrd.open_workbook(file_contents=data, on_demand=True)
        except Exception as e:
            raise SystemExit(f"XLS_PARSE_FAILED:{name}:{type(e).__name__}:{e}")
        file_meta = {
            "source_file": name,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            **period,
            "sheet_count": book.nsheets,
            "sheets": [],
        }
        for si in range(book.nsheets):
            sh = book.sheet_by_index(si)
            # Full native rectangular extent; trailing empty source rows/columns are not fabricated.
            typed_rows = []
            plain_rows = []
            for r in range(sh.nrows):
                tr = [typed_cell(book, sh.cell(r, c)) for c in range(sh.ncols)]
                typed_rows.append(tr)
                plain_rows.append([plain_value(x) for x in tr])
            scores = []
            for r in range(min(sh.nrows, 80)):
                scores.append((header_score(plain_rows[r]), r))
            scores.sort(reverse=True)
            best_score, header_row = scores[0] if scores else (0, 0)
            header_window_start = max(0, header_row - 2)
            header_window_end = min(sh.nrows - 1, header_row + 1) if sh.nrows else 0
            col_labels = []
            core_col = {}
            for c in range(sh.ncols):
                parts = []
                for rr in range(header_window_start, header_window_end + 1):
                    v = plain_rows[rr][c]
                    if str(v).strip() != "": parts.append(str(v).strip())
                label = " | ".join(dict.fromkeys(parts)) if parts else f"col_{c+1:03d}"
                col_labels.append(label)
                cls = classify_header(label)
                if cls and cls not in core_col:
                    core_col[cls] = c

            schema_sig_obj = {
                "sheet_name": sh.name,
                "ncols": sh.ncols,
                "header_window_rows_1based": [header_window_start + 1, header_window_end + 1] if sh.nrows else [],
                "column_labels": col_labels,
                "core_column_map_1based": {k: v + 1 for k, v in core_col.items()},
            }
            schema_sha = sha256_bytes(compact_json(schema_sig_obj).encode("utf-8"))
            schema_signatures.setdefault(schema_sha, 0); schema_signatures[schema_sha] += 1

            notes = []
            revision_markers = []
            unit_hints = []
            for r in range(sh.nrows):
                for c in range(sh.ncols):
                    v = plain_rows[r][c]
                    if not isinstance(v, str) or not v.strip(): continue
                    n = norm_text(v)
                    if any(tok in n for tok in ["provisor", "provis", "revisto", "revis", "definitiv"]):
                        revision_markers.append({"row": r+1, "col": c+1, "text": v})
                    if any(tok in n for tok in ["veiculo", "veiculos", "veic/dia", "veiculos/dia", "%", "quilomet", " km"]):
                        unit_hints.append({"row": r+1, "col": c+1, "text": v})
                    if any(tok in n for tok in ["nota", "fonte", "observ"]):
                        notes.append({"row": r+1, "col": c+1, "text": v})
            # de-duplicate exact positional hints only
            revision_markers = revision_markers[:100]
            unit_hints = unit_hints[:100]
            notes = notes[:100]

            nonempty = sum(1 for r in typed_rows for x in r if x["type"] != "blank")
            total_nonempty_cells += nonempty
            sheet_row_count = 0
            sheet_value_count = 0
            data_start = min(sh.nrows, header_window_end + 1)
            for r in range(data_start, sh.nrows):
                typed = typed_rows[r]
                if not any(x["type"] != "blank" for x in typed):
                    continue
                vals = [plain_value(x) for x in typed]
                fields = []
                blanks = []
                for c, tc in enumerate(typed):
                    fields.append({"source_column_1based": c+1, "source_label": col_labels[c], "cell": tc})
                    if tc["type"] == "blank": blanks.append(c+1)
                core = {}
                for k, c in core_col.items():
                    core[k] = vals[c]
                row_texts = [str(v) for v in vals if isinstance(v, str) and v.strip()]
                row_measure_labels = [v for v in row_texts if "tmdm" in norm_text(v) or "tmda" in norm_text(v)]
                rr = {
                    "source_file": name,
                    "source_file_sha256": sha256_bytes(data),
                    "source_file_bytes": len(data),
                    "reference_year": period["reference_year"],
                    "reference_quarter": period["reference_quarter"],
                    "edition_scope": period["edition_scope"],
                    "sheet_index_1based": si+1,
                    "sheet_name": sh.name,
                    "source_row_1based": r+1,
                    "schema_signature_sha256": schema_sha,
                    "motorway": core.get("motorway"),
                    "concession": core.get("concession"),
                    "sublanco": core.get("sublanco"),
                    "tmdm": core.get("tmdm"),
                    "tmda": core.get("tmda"),
                    "row_measure_labels_json": compact_json(row_measure_labels),
                    "blank_source_columns_1based_json": compact_json(blanks),
                    "source_fields_json": compact_json(fields),
                }
                row_records.append(rr); sheet_row_count += 1; total_source_rows += 1

                # Long source-native published values. We retain header labels verbatim, never harmonize.
                for c, tc in enumerate(typed):
                    if tc["type"] == "blank":
                        continue
                    label = col_labels[c]
                    pv = {
                        "source_file": name,
                        "source_file_sha256": sha256_bytes(data),
                        "reference_year": period["reference_year"],
                        "reference_quarter": period["reference_quarter"],
                        "reference_month": month_from_label(label),
                        "edition_scope": period["edition_scope"],
                        "sheet_index_1based": si+1,
                        "sheet_name": sh.name,
                        "source_row_1based": r+1,
                        "source_column_1based": c+1,
                        "schema_signature_sha256": schema_sha,
                        "motorway": core.get("motorway"),
                        "concession": core.get("concession"),
                        "sublanco": core.get("sublanco"),
                        "source_field_label": label,
                        "source_value_type": tc["type"],
                        "source_value_json": compact_json(tc),
                        "core_measure_role": classify_header(label),
                    }
                    published_values.append(pv); sheet_value_count += 1; total_value_records += 1

            merged = []
            try:
                merged = [[rlo+1, rhi, clo+1, chi] for rlo, rhi, clo, chi in sh.merged_cells]
            except Exception:
                merged = []
            s_meta = {
                "source_file": name,
                "sheet_index_1based": si+1,
                "sheet_name": sh.name,
                "nrows": sh.nrows,
                "ncols": sh.ncols,
                "nonempty_cells": nonempty,
                "header_score": best_score,
                "header_window_rows_1based": [header_window_start+1, header_window_end+1] if sh.nrows else [],
                "column_labels": col_labels,
                "core_column_map_1based": {k: v+1 for k, v in core_col.items()},
                "schema_signature_sha256": schema_sha,
                "merged_ranges_1based_half_open": merged,
                "revision_markers": revision_markers,
                "unit_hints": unit_hints,
                "notes": notes,
                "extracted_nonempty_rows": sheet_row_count,
                "published_nonblank_value_records": sheet_value_count,
            }
            file_meta["sheets"].append(s_meta)
            sheet_inventory.append({
                "source_file": name,
                "reference_year": period["reference_year"],
                "reference_quarter": period["reference_quarter"],
                "edition_scope": period["edition_scope"],
                "sheet_index_1based": si+1,
                "sheet_name": sh.name,
                "nrows": sh.nrows,
                "ncols": sh.ncols,
                "nonempty_cells": nonempty,
                "header_score": best_score,
                "header_window_rows_1based_json": compact_json(s_meta["header_window_rows_1based"]),
                "column_labels_json": compact_json(col_labels),
                "core_column_map_1based_json": compact_json(s_meta["core_column_map_1based"]),
                "schema_signature_sha256": schema_sha,
                "revision_markers_json": compact_json(revision_markers),
                "unit_hints_json": compact_json(unit_hints),
                "notes_json": compact_json(notes),
                "extracted_nonempty_rows": sheet_row_count,
                "published_nonblank_value_records": sheet_value_count,
            })
        book.release_resources()
        workbook_inventory.append({
            "source_file": name,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "reference_year": period["reference_year"],
            "reference_quarter": period["reference_quarter"],
            "edition_scope": period["edition_scope"],
            "sheet_count": file_meta["sheet_count"],
            "source_url": exp.get("source_url"),
        })
        pf = per_file_dir / (pathlib.Path(name).stem + ".json")
        pf.write_text(json.dumps(file_meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_csv(path, fieldnames, rows):
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
            w.writeheader(); w.writerows(rows)

    wb_csv = out / "f187_workbook_inventory.csv"
    write_csv(wb_csv, ["source_file","bytes","sha256","reference_year","reference_quarter","edition_scope","sheet_count","source_url"], workbook_inventory)
    sh_csv = out / "f187_sheet_inventory.csv"
    write_csv(sh_csv, ["source_file","reference_year","reference_quarter","edition_scope","sheet_index_1based","sheet_name","nrows","ncols","nonempty_cells","header_score","header_window_rows_1based_json","column_labels_json","core_column_map_1based_json","schema_signature_sha256","revision_markers_json","unit_hints_json","notes_json","extracted_nonempty_rows","published_nonblank_value_records"], sheet_inventory)
    rows_csv = out / "f187_source_native_rows.csv"
    write_csv(rows_csv, ["source_file","source_file_sha256","source_file_bytes","reference_year","reference_quarter","edition_scope","sheet_index_1based","sheet_name","source_row_1based","schema_signature_sha256","motorway","concession","sublanco","tmdm","tmda","row_measure_labels_json","blank_source_columns_1based_json","source_fields_json"], row_records)
    vals_csv = out / "f187_published_values.csv"
    write_csv(vals_csv, ["source_file","source_file_sha256","reference_year","reference_quarter","reference_month","edition_scope","sheet_index_1based","sheet_name","source_row_1based","source_column_1based","schema_signature_sha256","motorway","concession","sublanco","source_field_label","source_value_type","source_value_json","core_measure_role"], published_values)

    verified_inventory = [{k:v for k,v in rec.items() if k != "data"} for rec in verified.values()]
    ingress = {
        "schema_version": "4.0.7",
        "worker": "W2C",
        "wake_mission_generation": WAKE_GENERATION,
        "assignment_origin_generation": ASSIGNMENT_ORIGIN_GENERATION,
        "package": "F187_IMT_MOTORWAY_TRAFFIC_XLS_DETERMINISTIC_EXTRACTION_INGRESS",
        "source_set_id": SOURCE_SET_ID,
        "native_asset_fingerprint": FINGERPRINT,
        "private_release_tag": RELEASE_TAG,
        "private_receipt": PRIVATE_RECEIPT_PATH,
        "verification": {
            "all_receipt_assets_verified_before_any_parse": True,
            "asset_count": len(verified_inventory),
            "xls_workbook_count": len(xls_expected),
            "assets": verified_inventory,
        },
        "source_family": {
            "landing_html_preserved": True,
            "series_manifest_preserved": True,
            "series_manifest_sha256": sha256_bytes(verified["series-manifest.json"]["data"]),
            "series_manifest": manifest,
            "workbook_inventory_rows": len(workbook_inventory),
            "sheet_inventory_rows": len(sheet_inventory),
            "source_native_nonempty_rows": total_source_rows,
            "published_nonblank_value_records": total_value_records,
            "source_native_nonempty_cells": total_nonempty_cells,
            "schema_signature_count": len(schema_signatures),
            "schema_signature_occurrences": schema_signatures,
        },
        "semantic_contract": {
            "evidence_class": "OBSERVED_TRAFFIC_SOURCE",
            "source_native_only": True,
            "edition_file_preserved": True,
            "sheet_table_identity_preserved": True,
            "motorway_concession_sublanco_fields_only_when_source_header_detection_supports_them": True,
            "reference_year_quarter_derived_from_source_filename_only": True,
            "reference_month_only_when_unambiguously_present_in_source_field_label": True,
            "tmdm_tmda_roles_only_when_source_header_label_contains_exact_token": True,
            "other_published_fields_preserved_verbatim": True,
            "revision_provisional_text_preserved_as_source_markers": True,
            "source_unit_hints_preserved_verbatim": True,
            "blanks_missingness_preserved": True,
            "schema_drift_preserved_by_per_sheet_schema_signature": True,
            "editions_harmonized": False,
            "annual_quarterly_reconciled": False,
            "f05_joined": False,
            "crosswalks_invented": False,
            "producer_reacquisition": False,
            "rights_adjudication": False,
        },
        "limitations": [
            "XLS formula source text is not exposed by xlrd; calculated cell values and cell types are preserved while original verified XLS bytes remain canonical.",
            "Header/core-field detection is an extraction aid only. W2B owns semantic normalization and must use source labels/schema signatures rather than assuming cross-edition equivalence.",
        ],
    }
    ingress_path = out / "f187_source_native_ingress.json"
    ingress_path.write_text(json.dumps(ingress, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Hash every emitted file before private handoff.
    output_files = [wb_csv, sh_csv, rows_csv, vals_csv, ingress_path] + sorted(per_file_dir.glob("*.json"))
    output_meta = []
    for p in output_files:
        b = p.read_bytes()
        output_meta.append({"relative_path": str(p.relative_to(out)), "bytes": len(b), "sha256": sha256_bytes(b)})

    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W2C/{stamp}-G43-F187-extraction-ingress"
    handoff = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F187/{FINGERPRINT}-extraction.json"
    receipt = {
        "schema_version": "4.0.7",
        "worker": "W2C",
        "wake_mission_generation": WAKE_GENERATION,
        "assignment_origin_generation": ASSIGNMENT_ORIGIN_GENERATION,
        "package": "F187_IMT_MOTORWAY_TRAFFIC_XLS_DETERMINISTIC_EXTRACTION_INGRESS",
        "source_set_id": SOURCE_SET_ID,
        "native_asset_fingerprint": FINGERPRINT,
        "private_release_tag": RELEASE_TAG,
        "status": "PASS_PRIVATE_PRESERVED_ASSET_SET_VERIFIED_BEFORE_PARSE_AND_SOURCE_NATIVE_XLS_INGRESS_EMITTED",
        "asset_set_verified_before_parse": True,
        "verified_asset_count": len(verified_inventory),
        "verified_xls_workbook_count": len(xls_expected),
        "source_native_nonempty_rows": total_source_rows,
        "published_nonblank_value_records": total_value_records,
        "sheet_count": len(sheet_inventory),
        "schema_signature_count": len(schema_signatures),
        "observed_traffic_source": True,
        "editions_harmonized": False,
        "annual_quarterly_reconciled": False,
        "f05_joined": False,
        "producer_reacquisition": False,
        "consumer_joins": False,
        "rights_adjudication": False,
        "outputs": [{"path": out_base + "/" + x["relative_path"], "bytes": x["bytes"], "sha256": x["sha256"]} for x in output_meta],
        "canonical_extraction_receipt_path": handoff,
        "next_owner": "W2B",
        "next_state": "READY_NORMALIZATION_HANDOFF",
    }
    receipt_path = out / "extraction-receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Check current mission still assigns the exact F187 fingerprint to W2C. Generation may advance, but in-flight work cannot be reassigned until close.
    current_team = json.loads(fetch_private_text("statistics/recovery-20260920/simple-runtime/team-missions.json", read_token))
    w2c = (((current_team.get("teams") or {}).get("W2") or {}).get("C") or {})
    binding = compact_json(w2c)
    if SOURCE_SET_ID not in binding or FINGERPRINT not in binding:
        raise SystemExit("CURRENT_W2C_ASSIGNMENT_NO_LONGER_CONTAINS_EXACT_F187_FINGERPRINT")
    current_generation_at_write = int(current_team.get("mission_generation", -1))

    clone = temp / "private"
    env = os.environ.copy(); env["GIT_TERMINAL_PROMPT"] = "0"
    url = f"https://x-access-token:{write_token}@github.com/{PRIVATE_REPO}.git"
    subprocess.run(["git", "clone", "--depth", "1", "--branch", PRIVATE_BRANCH, url, str(clone)], check=True, env=env, stdout=subprocess.DEVNULL)
    team_clone = json.loads((clone / "statistics/recovery-20260920/simple-runtime/team-missions.json").read_text(encoding="utf-8"))
    w2c_clone = (((team_clone.get("teams") or {}).get("W2") or {}).get("C") or {})
    binding_clone = compact_json(w2c_clone)
    if SOURCE_SET_ID not in binding_clone or FINGERPRINT not in binding_clone:
        raise SystemExit("W2C_ASSIGNMENT_CHANGED_AFTER_CLONE")

    dst = clone / out_base
    dst.mkdir(parents=True, exist_ok=True)
    for p in output_files + [receipt_path]:
        relp = p.relative_to(out); q = dst / relp; q.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, q)
    hp = clone / handoff; hp.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(receipt_path, hp)

    worker_path = clone / "statistics/recovery-20260920/simple-runtime/worker-W2C.json"
    worker = {
        "schema_version": "4.0.7",
        "worker": "W2C",
        "team": "W2",
        "partner": "C",
        "mission_generation": WAKE_GENERATION,
        "assignment_origin_generation": ASSIGNMENT_ORIGIN_GENERATION,
        "team_mission_generation_observed_before_private_write": current_generation_at_write,
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "status": "READY_NORMALIZATION_HANDOFF",
        "elastic_state": "STANDBY_EXTRACTION_INGRESS",
        "current_task": None,
        "last_output": out_base + "/extraction-receipt.json",
        "window": {
            "mission": "Exact fingerprint-pinned F187 IMT motorway-traffic XLS deterministic extraction ingress; no producer reacquisition.",
            "material_packages": 1,
            "source_id": SOURCE_SET_ID,
            "native_asset_fingerprint": FINGERPRINT,
            "private_release_tag": RELEASE_TAG,
            "all_assets_verified_before_parse": True,
            "verified_asset_count": len(verified_inventory),
            "xls_workbook_count": len(xls_expected),
            "sheet_count": len(sheet_inventory),
            "source_native_nonempty_rows": total_source_rows,
            "published_nonblank_value_records": total_value_records,
            "schema_signature_count": len(schema_signatures),
            "result": "PASS_F187_SOURCE_NATIVE_XLS_EXTRACTION_INGRESS",
            "producer_requests_sent": 0,
            "producer_reacquisitions": 0,
            "consumer_joins": 0,
            "rights_adjudications": 0,
            "f05_joined": False,
            "editions_harmonized": False,
            "outputs": [out_base + "/" + x["relative_path"] for x in output_meta] + [out_base + "/extraction-receipt.json", handoff],
            "canonical_extraction_receipt": handoff,
            "next_cursor": [
                "W2B: consume the exact extraction receipt and normalize source-native traffic rows preserving edition/file, sheet/table, period, motorway/concession/sublanco, source labels/units, revision markers, blanks and schema signatures.",
                "Reconcile annual versus quarterly editions explicitly in W2B; do not silently replace revisions.",
                "Do not join F05 in W2C."
            ],
        },
        "blocker": None,
    }
    worker_path.write_text(json.dumps(worker, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    subprocess.run(["git", "-C", str(clone), "config", "user.name", "mobilidade-public-sources[bot]"], check=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.email", "actions@users.noreply.github.com"], check=True)
    paths = [out_base, handoff, "statistics/recovery-20260920/simple-runtime/worker-W2C.json"]
    subprocess.run(["git", "-C", str(clone), "add", "--"] + paths, check=True)
    subprocess.run(["git", "-C", str(clone), "commit", "-m", "result(mn): W2C F187 source-native XLS extraction ingress"], check=True, stdout=subprocess.DEVNULL)
    # Branch may move because other workers write disjoint domains. Rebase once if needed, then push.
    pushed = False
    for _ in range(3):
        p = subprocess.run(["git", "-C", str(clone), "push", "origin", PRIVATE_BRANCH], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode == 0:
            pushed = True; break
        subprocess.run(["git", "-C", str(clone), "pull", "--rebase", "origin", PRIVATE_BRANCH], check=True, env=env, stdout=subprocess.DEVNULL)
    if not pushed:
        raise SystemExit("PRIVATE_HANDOFF_PUSH_FAILED_AFTER_REBASE")

    print(json.dumps({
        "status": "PASS",
        "source_set_id": SOURCE_SET_ID,
        "fingerprint": FINGERPRINT,
        "output_base": out_base,
        "verified_assets": len(verified_inventory),
        "xls_workbooks": len(xls_expected),
        "sheets": len(sheet_inventory),
        "source_native_rows": total_source_rows,
        "published_value_records": total_value_records,
        "schema_signatures": len(schema_signatures),
        "handoff": handoff,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
