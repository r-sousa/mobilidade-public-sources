from __future__ import annotations
import datetime as dt
import email.utils
import hashlib
import json
import math
import threading
import time
import urllib.parse
import unicodedata
from pathlib import Path
from typing import Any

import requests

from .chunking import compose_ine_chunks

BASE = "https://www.ine.pt/ine/json_indicador"
MAX_CELLS = 40_000
MAX_URL_LENGTH = 1800
MAX_RESPONSE_BYTES = 30_000_000
MIN_START_INTERVAL_SECONDS = 2.0
RETRY_DELAY_SECONDS = 15
UA = "MobilidadeNorte-PublicAcquisition-INE/1.0"

_lock = threading.Lock()
_last_start = 0.0


class INESemanticError(RuntimeError):
    pass


class INERowLimitError(INESemanticError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def _record(obj: Any) -> dict:
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj[0]
    if isinstance(obj, dict):
        return obj
    raise INESemanticError("Unexpected INE response shape")


def _dimension_items(meta: Any, dim_num: int) -> dict[str, dict]:
    rec = _record(meta)
    dims = rec.get("Dimensoes", rec.get("dimensoes"))
    found: dict[str, dict] = {}
    if isinstance(dims, dict):
        cats = dims.get("Categoria_Dim")
        if isinstance(cats, list):
            for group in cats:
                if not isinstance(group, dict):
                    continue
                for entries in group.values():
                    if not isinstance(entries, list):
                        continue
                    for item in entries:
                        if (
                            isinstance(item, dict)
                            and str(item.get("dim_num")) == str(dim_num)
                            and item.get("categ_cod") is not None
                        ):
                            found[str(item["categ_cod"])] = item
    elif isinstance(dims, list):
        target = f"dim{dim_num}".lower()
        for d in dims:
            if not isinstance(d, dict) or str(d.get("Dim", "")).lower() != target:
                continue
            for item in d.get("Membros") or []:
                if isinstance(item, dict) and item.get("Codigo") is not None:
                    found[str(item["Codigo"])] = item
    return found


def _dimensions(meta: Any) -> dict[str, list[str]]:
    result = {}
    for dim in range(1, 10):
        items = _dimension_items(meta, dim)
        if not items:
            if dim > 4:
                break
            continue
        result[f"Dim{dim}"] = list(items)
    if "Dim1" not in result:
        raise INESemanticError("INE metadata has no period dimension")
    return result


def _resolve_label(meta: Any, dim_num: int, wanted: str) -> str:
    items = _dimension_items(meta, dim_num)
    needle = str(wanted).strip().casefold()
    exact, contains = [], []
    for code, item in items.items():
        vals = [str(v).strip() for v in item.values() if isinstance(v, (str, int, float))]
        folded = [v.casefold() for v in vals]
        if needle in folded:
            exact.append(code)
        elif any(needle in v for v in folded):
            contains.append(code)
    matches = exact if exact else contains
    if len(matches) != 1:
        sample = [{"code": k, "member": v} for k, v in list(items.items())[:8]]
        raise INESemanticError(
            f"INE label resolution Dim{dim_num}={wanted!r} returned {len(matches)} matches; "
            f"sample={json.dumps(sample, ensure_ascii=False)}"
        )
    return matches[0]


def _period_labels(meta: Any) -> dict[str, str]:
    out = {}
    for code, item in _dimension_items(meta, 1).items():
        label = (
            item.get("categ_dsg")
            or item.get("Designacao")
            or item.get("Descricao")
            or item.get("label")
        )
        if label is not None:
            out[code] = str(label)
    return out


def _errors(obj: Any) -> list[dict]:
    rec = _record(obj)
    success = rec.get("Sucesso", rec.get("sucesso"))
    if isinstance(success, dict):
        false_part = success.get("Falso", success.get("false"))
        if isinstance(false_part, list):
            return [x for x in false_part if isinstance(x, dict)]
        if isinstance(false_part, dict):
            return [false_part]
    if success is False or (
        isinstance(success, str)
        and success.strip().casefold() in {"false", "falso", "0"}
    ):
        return [{"Cod": rec.get("Cod"), "Msg": rec.get("Msg") or rec.get("Mensagem")}]
    return []


def _guard(obj: Any) -> dict:
    errs = _errors(obj)
    for err in errs:
        code = str(err.get("Cod", err.get("cod", "")))
        msg = str(err.get("Msg", err.get("msg", err.get("Mensagem", ""))))
        if code == "7" or (
            code == "3" and "character string buffer too small" in msg.casefold()
        ):
            raise INERowLimitError(msg or f"INE row-limit response code {code}")
    if errs:
        raise INESemanticError("INE semantic failure: " + json.dumps(errs, ensure_ascii=False))
    rec = _record(obj)
    if not isinstance(rec.get("Dados"), dict):
        raise INESemanticError("INE successful-looking response has no Dados object")
    return rec


def _flatten(obj: Any) -> list[dict]:
    rec = _guard(obj)
    rows = []
    for period, observations in rec["Dados"].items():
        if not isinstance(observations, list):
            continue
        for row in observations:
            if not isinstance(row, dict):
                continue
            if "valor" not in row and not row.get("sinal_conv"):
                raise INESemanticError(
                    "INE observation has neither valor nor status/confidentiality marker"
                )
            rows.append({"period": str(period), **row})
    return rows


def _norm_label(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().replace("-", " ").replace("_", " ").split())


def _member_label_map(meta: Any) -> dict[str, dict[str, set[str]]]:
    result: dict[str, dict[str, set[str]]] = {}
    for dim_num in range(1, 10):
        items = _dimension_items(meta, dim_num)
        if not items:
            if dim_num > 4:
                break
            continue
        by_code: dict[str, set[str]] = {}
        for code, item in items.items():
            vals = set()
            for k, value in item.items():
                if not isinstance(value, (str, int, float)):
                    continue
                key = str(k).casefold()
                if "cod" in key or key in {"dim_num", "ord", "order"}:
                    continue
                text = _norm_label(str(value))
                if text:
                    vals.add(text)
            by_code[code] = vals
        result[f"Dim{dim_num}"] = by_code
    return result


def _response_label_candidates(row: dict, dim_num: int) -> set[str]:
    vals = set()
    if dim_num == 2:
        preferred = ("geodsg", "geo_dsg", "geodesignacao", "geonome", "geo_nome")
        for key in preferred:
            if row.get(key) is not None:
                vals.add(_norm_label(str(row[key])))
        for key, value in row.items():
            k = str(key).casefold()
            if "geo" in k and any(x in k for x in ("dsg", "des", "nome", "name", "label")):
                if isinstance(value, (str, int, float)):
                    vals.add(_norm_label(str(value)))
    else:
        prefix = f"dim_{dim_num}"
        for key, value in row.items():
            k = str(key).casefold()
            if k.startswith(prefix) and k != prefix and isinstance(value, (str, int, float)):
                vals.add(_norm_label(str(value)))
    return {x for x in vals if x}


def _coordinate(
    row: dict,
    dim: str,
    labels: dict[str, str],
    allowed: list[str],
    member_labels: dict[str, dict[str, set[str]]],
) -> str:
    if dim == "Dim1":
        value = str(row["period"])
        matches = [
            code for code in allowed
            if value == code or value == labels.get(code)
        ]
        if len(matches) != 1:
            raise INESemanticError(f"INE returned unrequested period {value!r}")
        return matches[0]

    n = int(dim[3:])
    key = "geocod" if n == 2 else f"dim_{n}"
    if row.get(key) is None:
        raise INESemanticError(f"INE observation lacks {key}")
    value = str(row[key])
    if value in allowed:
        return value

    response_labels = _response_label_candidates(row, n)
    if response_labels:
        matches = []
        for code in allowed:
            producer_labels = member_labels.get(dim, {}).get(code, set())
            if response_labels & producer_labels:
                matches.append(code)
        if len(matches) == 1:
            return matches[0]

    raise INESemanticError(
        f"INE ignored {dim} filter: returned_code={value!r}; "
        f"response_labels={sorted(response_labels)!r}; requested={allowed!r}"
    )


def _validate_rows(
    rows: list[dict],
    selection: dict[str, list[str]],
    labels: dict[str, str],
    member_labels: dict[str, dict[str, set[str]]],
) -> tuple[list[dict], dict[str, list[str]]]:
    observed = {k: set() for k in selection}
    unique = {}
    for row in rows:
        coords = []
        for dim, allowed in selection.items():
            value = _coordinate(row, dim, labels, allowed, member_labels)
            observed[dim].add(value)
            coords.append((dim, value))
        key = tuple(coords)
        if key in unique and unique[key] != row:
            raise INESemanticError("Conflicting duplicate INE observation")
        unique[key] = row
    return list(unique.values()), {k: sorted(v) for k, v in observed.items()}


def _split(selection: dict[str, list[str]]) -> list[dict[str, list[str]]]:
    candidates = [k for k, v in selection.items() if len(v) > 1]
    if not candidates:
        raise INERowLimitError("Cannot subdivide atomic INE selection")
    dim = "Dim2" if "Dim2" in candidates else max(candidates, key=lambda k: len(selection[k]))
    values = selection[dim]
    cut = (len(values) + 1) // 2
    return [
        {**selection, dim: values[:cut]},
        {**selection, dim: values[cut:]},
    ]


def _request_url(
    indicator: str,
    selection: dict[str, list[str]],
    dimensions: dict[str, list[str]],
    *,
    explicit: bool,
) -> str:
    filters = {}
    for dim, values in selection.items():
        if dim == "Dim1" or explicit or values != dimensions.get(dim):
            filters[dim] = ",".join(values)
    return BASE + "/pindica.jsp?" + urllib.parse.urlencode(
        {"op": "2", "varcd": indicator, "lang": "PT", **filters}
    )


def _plan(
    indicator: str,
    dimensions: dict[str, list[str]],
    *,
    full_dimensions: dict[str, list[str]] | None = None,
    max_cells: int = MAX_CELLS,
    max_url_length: int = MAX_URL_LENGTH,
) -> list[dict[str, list[str]]]:
    result = []

    def visit(selection):
        url = _request_url(
            indicator, selection, full_dimensions or dimensions, explicit=False
        )
        cells = math.prod(len(v) for v in selection.values())
        if cells > max_cells or len(url) > max_url_length:
            for child in _split(selection):
                visit(child)
        else:
            result.append(selection)

    for period in dimensions["Dim1"]:
        visit({**dimensions, "Dim1": [period]})
    return result


def _start_slot(spacing: float) -> None:
    global _last_start
    with _lock:
        wait = max(0.0, spacing - (time.monotonic() - _last_start))
        if wait:
            time.sleep(wait)
        _last_start = time.monotonic()


def _fetch(session: requests.Session, url: str, *, spacing: float, attempts: int = 3) -> tuple[bytes, str]:
    for attempt in range(attempts):
        _start_slot(spacing)
        try:
            r = session.get(url, timeout=(20, 120))
            if r.status_code in (403, 429, 503):
                retry = r.headers.get("Retry-After", "")
                try:
                    delay = float(retry)
                except Exception:
                    try:
                        delay = max(
                            0.0,
                            (
                                email.utils.parsedate_to_datetime(retry)
                                - dt.datetime.now(dt.timezone.utc)
                            ).total_seconds(),
                        )
                    except Exception:
                        delay = RETRY_DELAY_SECONDS
                if attempt == attempts - 1:
                    r.raise_for_status()
                time.sleep(max(RETRY_DELAY_SECONDS, delay))
                continue
            r.raise_for_status()
            body = r.content
            if len(body) > MAX_RESPONSE_BYTES:
                raise INERowLimitError("INE response exceeds local 30MB budget")
            return body, r.url
        except INERowLimitError:
            raise
        except requests.RequestException:
            if attempt == attempts - 1:
                raise
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError("INE fetch exhausted attempts")


def acquire(spec: dict, work: Path) -> dict:
    pms = spec["parameters"]
    indicator = str(pms["indicator"]).zfill(7)
    spacing = max(MIN_START_INTERVAL_SECONDS, float(pms.get("spacing_seconds", 2)))
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})

    meta_url = BASE + "/pindicaMeta.jsp?" + urllib.parse.urlencode(
        {"varcd": indicator, "lang": "PT"}
    )
    meta_bytes, final_meta_url = _fetch(s, meta_url, spacing=spacing, attempts=3)
    meta_obj = json.loads(meta_bytes.decode("utf-8-sig"))
    meta_path = work / "payload" / f"{indicator}-metadata.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_bytes(meta_bytes)
    metadata_asset = {
        "path": str(meta_path.relative_to(work)),
        "name": meta_path.name,
        "sha256": _sha(meta_path),
        "bytes": meta_path.stat().st_size,
        "source_url": final_meta_url,
        "format": "JSON",
        "role": "native",
    }

    all_dims = _dimensions(meta_obj)
    dims = {k: list(v) for k, v in all_dims.items()}
    labels = _period_labels(meta_obj)
    member_labels = _member_label_map(meta_obj)

    target_year = pms.get("year")
    period_contains = pms.get("period_label_contains")
    if target_year is not None or period_contains:
        wanted = []
        for code in all_dims["Dim1"]:
            blob = (code + " " + labels.get(code, "")).casefold()
            if target_year is not None and str(target_year) not in blob:
                continue
            if period_contains and str(period_contains).casefold() not in blob:
                continue
            wanted.append(code)
        if not wanted:
            raise INESemanticError("Requested INE period is absent from producer metadata")
        dims["Dim1"] = wanted

    for k, wanted in (pms.get("dimension_labels") or {}).items():
        dim_num = int(k)
        dims[f"Dim{dim_num}"] = [_resolve_label(meta_obj, dim_num, str(wanted))]

    for k, codes in (pms.get("dimension_codes") or {}).items():
        dim_num = int(k)
        dim = f"Dim{dim_num}"
        requested = [str(x) for x in (codes if isinstance(codes, list) else [codes])]
        unknown = sorted(set(requested) - set(all_dims.get(dim, [])))
        if unknown:
            raise INESemanticError(f"Requested {dim} codes absent from metadata: {unknown}")
        dims[dim] = requested

    selected_meta = {}
    for dim, codes in dims.items():
        n = int(dim[3:])
        items = _dimension_items(meta_obj, n)
        selected_meta[dim] = {code: items.get(code) for code in codes}
    print(json.dumps({"ine_selected_metadata": selected_meta}, ensure_ascii=False), flush=True)

    max_cells = min(MAX_CELLS, int(pms.get("max_cells_per_chunk", MAX_CELLS)))
    plan = _plan(
        indicator, dims, full_dimensions=all_dims, max_cells=max_cells
    )

    pending = [{"selection": x, "explicit": False} for x in plan]
    raw_assets = []
    chunk_details = []
    observed_global = {k: set() for k in dims}
    chunk_index = 0

    while pending:
        job = pending.pop(0)
        selection = job["selection"]
        explicit = bool(job["explicit"])
        url = _request_url(indicator, selection, all_dims, explicit=explicit)
        try:
            body, final_url = _fetch(s, url, spacing=spacing, attempts=3)
            obj = json.loads(body.decode("utf-8-sig"))
            rows = _flatten(obj)
            if len(rows) >= max_cells:
                raise INERowLimitError(
                    f"INE response reached chunk threshold {len(rows)} >= {max_cells}"
                )
            rows, observed = _validate_rows(rows, selection, labels, member_labels)

            omitted = [
                dim for dim, values in selection.items()
                if dim != "Dim1" and values == all_dims.get(dim)
            ] if not explicit else []
            if any(set(observed[dim]) != set(selection[dim]) for dim in omitted):
                pending.insert(0, {"selection": selection, "explicit": True})
                continue

            chunk_index += 1
            chunk_path = work / "payload" / f"{indicator}-chunk-{chunk_index:05d}.json"
            chunk_path.write_bytes(body)
            asset = {
                "path": str(chunk_path.relative_to(work)),
                "name": chunk_path.name,
                "sha256": _sha(chunk_path),
                "bytes": chunk_path.stat().st_size,
                "source_url": final_url,
                "format": "JSON",
                "role": "native",
            }
            raw_assets.append(asset)
            for dim, values in observed.items():
                observed_global[dim].update(values)
            chunk_details.append(
                {
                    "chunk": chunk_path.name,
                    "selection": selection,
                    "explicit": explicit,
                    "cells_planned": math.prod(len(v) for v in selection.values()),
                    "row_count": len(rows),
                    "observed": observed,
                    "sha256": asset["sha256"],
                    "bytes": asset["bytes"],
                }
            )
        except INERowLimitError:
            for child in reversed(_split(selection)):
                pending.insert(0, {"selection": child, "explicit": explicit})
            continue

    missing = {
        dim: sorted(set(values) - observed_global[dim])
        for dim, values in dims.items()
    }
    complete = not any(missing.values())
    if pms.get("require_category_coverage", False) and not complete:
        raise INESemanticError(
            "INE acquisition completed requests but category coverage is incomplete: "
            + json.dumps(missing, ensure_ascii=False)
        )

    plan_path = work / "recomposed" / "ine-plan-and-coverage.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_payload = {
        "schema_version": "1.0.0",
        "indicator": indicator,
        "max_cells_per_chunk": max_cells,
        "max_url_length": MAX_URL_LENGTH,
        "spacing_seconds": spacing,
        "planned_initial_chunks": len(plan),
        "completed_chunks": len(raw_assets),
        "dimensions_requested": dims,
        "observed_categories": {k: sorted(v) for k, v in observed_global.items()},
        "missing_categories": missing,
        "category_coverage_complete": complete,
        "chunks": chunk_details,
    }
    plan_path.write_text(
        json.dumps(plan_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    plan_asset = {
        "path": str(plan_path.relative_to(work)),
        "name": plan_path.name,
        "sha256": _sha(plan_path),
        "bytes": plan_path.stat().st_size,
        "source_url": None,
        "format": "JSON",
        "role": "recomposed",
    }

    recomposed = compose_ine_chunks(
        work, raw_assets, metadata_asset=metadata_asset
    )

    return {
        "acquired_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "assets": [metadata_asset, *raw_assets, plan_asset, *recomposed],
        "validation_result": (
            "PASS_INE_PARTITIONED_RECOMPOSED_COMPLETE"
            if complete else "PASS_INE_PARTITIONED_RECOMPOSED_WITH_STRUCTURAL_MISSINGNESS"
        ),
        "source_period_or_edition": str(target_year) if target_year is not None else None,
        "limitations": (
            "INE requests are metadata-defined and recursively partitioned below the 40,000-cell "
            "contract and URL-length bound. Cod=7 or saturated responses trigger further splitting. "
            "Raw chunks remain native; recomposed JSONL is derived without replacing missing or "
            "confidential values with zero."
        ),
    }
