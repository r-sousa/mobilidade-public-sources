from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import re
import tempfile
import time
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
    """Write one UTF-8 private-repo file with collision-safe retry.

    GitHub's contents API can return 409 when the branch head moves because an
    unrelated worker commits between this function's lookup and PUT.  That is
    not a semantic conflict.  On 409 we re-read the *same path*, accept an
    identical immutable result, enforce expected_sha if supplied, and retry
    only when the target path itself is still safe to write.  This never
    overwrites a changed immutable output and therefore preserves collision-
    first semantics while allowing concurrent append-only worker outputs.
    """
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}"

    for attempt in range(5):
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
        if r.ok:
            obj = r.json()
            return {"path": path, "status": "WRITTEN", "commit": obj["commit"]["sha"], "sha": obj["content"]["sha"]}
        if r.status_code != 409 or attempt == 4:
            raise RuntimeError(f"PRIVATE_CONTENT_WRITE_FAILED:{path}:{r.status_code}:{r.text[:300]}")
        time.sleep(0.35 * (attempt + 1))

    raise RuntimeError(f"PRIVATE_CONTENT_WRITE_RETRY_EXHAUSTED:{path}")


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


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        for k, v in attrs:
            if k.lower() == "href" and v:
                self.links.append(v)


def _num(s: str):
    raw = (s or "").strip().replace("\u00a0", " ")
    if not raw or raw in {"-", "—", "..", ":"}:
        return None
    cleaned = re.sub(r"[^0-9,\.\-]", "", raw)
    if not cleaned or cleaned in {"-", ".", ","}:
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts[-1]) == 3 and len(parts) > 1:
            cleaned = "".join(parts)
        else:
            cleaned = cleaned.replace(",", ".")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _table_rows_html(data: bytes) -> tuple[list[list[str]], list[str]]:
    text = data.decode("utf-8", errors="replace")
    p = _TableParser()
    p.feed(text)
    links = _LinkParser()
    links.feed(text)
    rows: list[list[str]] = []
    for table in p.tables:
        rows.extend(table)
    return rows, links.links


def _pdf_pages(data: bytes) -> list[tuple[int, str]]:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for idx, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            text = page.extract_text() or ""
        pages.append((idx, " ".join(text.split())))
    return pages


def _metric_from_context(text: str) -> str | None:
    f = _fold(text)
    if any(x in f for x in ["passageir", "passenger", "pasajer"]):
        return "PASSENGERS"
    if any(x in f for x in ["movimento", "movements", "operacion", "operacoes", "operações", "aeronaves"]):
        return "MOVEMENTS"
    if any(x in f for x in ["carga", "freight", "cargo", "mercador"]):
        return "FREIGHT"
    if "teu" in f:
        return "TEU"
    if any(x in f for x in ["navio", "vessel", "buque"]):
        return "VESSELS"
    return None


def _unit_from_context(text: str, metric: str | None) -> str | None:
    f = _fold(text)
    if "teu" in f:
        return "TEU"
    if any(x in f for x in ["tonelad", "tonnes", "tons", " t "]):
        return "tonnes"
    if metric == "PASSENGERS":
        return "passengers"
    if metric == "MOVEMENTS":
        return "movements"
    if metric == "VESSELS":
        return "vessels"
    return None


def _html_extract(data: bytes) -> tuple[list[dict], list[dict], dict]:
    rows, links = _table_rows_html(data)
    candidates: list[dict] = []
    admitted: list[dict] = []
    for ti, row in enumerate(rows, 1):
        context = " | ".join(row)
        metric = _metric_from_context(context)
        unit = _unit_from_context(context, metric)
        nums = []
        for ci, cell in enumerate(row):
            val = _num(cell)
            if val is not None:
                nums.append({"cell_index": ci, "raw": cell, "value": val})
        if nums:
            rec = {"table_row_index": ti, "cells": row, "metric_context": metric, "unit_context": unit, "numeric_cells": nums}
            candidates.append(rec)
            if metric and unit:
                admitted.append(rec)
    return candidates, admitted, {"method": "stdlib_html_tables_numeric_rows_v1", "table_count": len(set(r["table_row_index"] for r in candidates)), "embedded_link_count": len(links), "external_links_followed": 0}


def _pdf_extract(data: bytes) -> tuple[list[dict], list[dict], dict]:
    pages = _pdf_pages(data)
    candidates: list[dict] = []
    admitted: list[dict] = []
    line_re = re.compile(r"(?P<label>[^\n]{3,100}?)\s+(?P<value>-?[0-9][0-9 .,'’]*)\s*(?P<unit>TEU|t|toneladas?|tonnes?|passageiros?|passengers?|movimentos?|operations?|navios?|vessels?)?", re.I)
    for page_no, text in pages:
        for match in line_re.finditer(text):
            label = " ".join(match.group("label").split())
            raw_value = match.group("value")
            val = _num(raw_value)
            if val is None:
                continue
            context = f"{label} {match.group('unit') or ''}"
            metric = _metric_from_context(context)
            unit = _unit_from_context(context, metric)
            rec = {"page": page_no, "label": label, "raw_value": raw_value, "value": val, "metric_context": metric, "unit_context": unit}
            candidates.append(rec)
            if metric and unit:
                admitted.append(rec)
    return candidates, admitted, {"method": "pypdf_layout_numeric_metric_rows_v1", "page_count": len(pages), "external_links_followed": 0}


def _csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["row_index", "row_json"])
    for i, row in enumerate(rows, 1):
        writer.writerow([i, json.dumps(row, ensure_ascii=False, sort_keys=True)])
    return buf.getvalue()


def run(cfg: dict, read_token: str, write_token: str) -> dict:
    raise NotImplementedError("This shared module exposes helpers used by bounded W4/W3 extractors.")
