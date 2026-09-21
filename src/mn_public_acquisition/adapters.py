from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import zipfile
from pathlib import Path

import requests

UA = "MobilidadeNorte-PublicAcquisition/0.1 (+source-preservation)"
TIMEOUT = 600


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def safe_name(url: str, fallback: str) -> str:
    name = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).name or fallback
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:180] or fallback


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    return s


def download(s: requests.Session, url: str, path: Path, work: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with s.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
        ctype = r.headers.get("content-type")
        final_url = r.url
    return {
        "path": str(path.relative_to(work)),
        "name": path.name,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "source_url": final_url,
        "content_type": ctype,
    }


def validate_xlsx(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
            raise ValueError(f"{path.name} is not a valid XLSX package")


def validate_gtfs(path: Path) -> None:
    required = {"agency.txt", "routes.txt", "stops.txt", "trips.txt", "stop_times.txt"}
    with zipfile.ZipFile(path) as z:
        names = {Path(n).name for n in z.namelist()}
    missing = sorted(required - names)
    if missing:
        raise ValueError(f"GTFS archive missing required files: {missing}")


def eurostat(spec: dict, work: Path) -> dict:
    code = spec["parameters"]["dataset_code"]
    params = {"format": "JSON", "lang": "EN"}
    params.update(spec["parameters"].get("query", {}))
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{urllib.parse.quote(code)}"
    s = session()
    p = work / "payload" / f"{code}.json"
    rec = download(s, url + "?" + urllib.parse.urlencode(params), p, work)
    obj = json.loads(p.read_text(encoding="utf-8-sig"))
    if isinstance(obj, dict) and isinstance(obj.get("warning"), dict) and obj["warning"].get("status") == 413:
        raise RuntimeError("Eurostat returned asynchronous-response warning; use a bounded or bulk route")
    rec["format"] = "JSON-stat/JSON"
    return {
        "acquired_at": now(),
        "assets": [rec],
        "validation_result": "PASS_JSON_MATERIALIZED",
        "source_period_or_edition": spec["parameters"].get("period"),
        "limitations": "Producer-native API response preserved; no consumer normalization performed."
    }


def ine_json(spec: dict, work: Path) -> dict:
    indicator = str(spec["parameters"]["indicator"]).zfill(7)
    target_year = spec["parameters"].get("year")
    base = "https://www.ine.pt/ine/json_indicador"
    s = session()
    assets = []
    meta_url = f"{base}/pindicaMeta.jsp?" + urllib.parse.urlencode({"varcd": indicator, "lang": "PT"})
    mp = work / "payload" / f"{indicator}-metadata.json"
    meta = download(s, meta_url, mp, work)
    meta["format"] = "JSON"
    assets.append(meta)
    obj = json.loads(mp.read_text(encoding="utf-8-sig"))
    period_re = re.compile(r"S7[A-Za-z0-9._-]*20\d{2}[A-Za-z0-9._-]*")
    found = set()
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(str(k)); walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            found.update(period_re.findall(x))
    walk(obj)
    periods = sorted(x for x in found if target_year is None or str(target_year) in x)
    if not periods:
        raise RuntimeError(f"INE metadata exposed no period code for requested year {target_year}")
    spacing = float(spec["parameters"].get("spacing_seconds", 2))
    for i, period in enumerate(periods):
        if i:
            time.sleep(spacing)
        url = f"{base}/pindica.jsp?" + urllib.parse.urlencode(
            {"op": "2", "varcd": indicator, "lang": "PT", "Dim1": period}
        )
        p = work / "payload" / f"{indicator}-{period}.json"
        rec = download(s, url, p, work)
        data_obj = json.loads(p.read_text(encoding="utf-8-sig"))
        blob = json.dumps(data_obj, ensure_ascii=False).lower()
        if '"sucesso": false' in blob or ('"falso"' in blob and '"sucesso"' in blob):
            raise RuntimeError(f"INE semantic failure for period {period}")
        rec["format"] = "JSON"
        assets.append(rec)
    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_INE_METADATA_AND_NATIVE_JSON",
        "source_period_or_edition": str(target_year) if target_year is not None else None,
        "limitations": "Raw INE metadata and bounded period responses preserved; missing/confidential values are not transformed."
    }


def static_http(spec: dict, work: Path) -> dict:
    s = session()
    assets = []
    for item in spec["parameters"]["assets"]:
        url = item["url"]
        key = item.get("key") or safe_name(url, "source.bin")
        name = item.get("filename") or safe_name(url, f"{key}.bin")
        p = work / "payload" / name
        rec = download(s, url, p, work)
        fmt = (item.get("format") or Path(name).suffix.lstrip(".") or "binary").upper()
        if fmt == "XLSX":
            validate_xlsx(p)
        elif fmt == "JSON":
            json.loads(p.read_text(encoding="utf-8-sig"))
        rec["format"] = fmt
        rec["name"] = f"{key}__{name}" if key != name else name
        assets.append(rec)
    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_STATIC_ASSETS_MATERIALIZED",
        "source_period_or_edition": spec["parameters"].get("period"),
        "limitations": spec["parameters"].get("limitations")
    }


def ckan_gtfs(spec: dict, work: Path) -> dict:
    s = session()
    api = spec["parameters"]["package_show_url"]
    r = s.get(api, timeout=180)
    r.raise_for_status()
    raw = r.content
    meta_path = work / "payload" / "ckan-package-show.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_bytes(raw)
    meta_rec = {
        "path": "payload/ckan-package-show.json",
        "name": "ckan-package-show.json",
        "sha256": sha256(meta_path),
        "bytes": meta_path.stat().st_size,
        "source_url": r.url,
        "format": "JSON"
    }
    obj = r.json()
    if not obj.get("success") or not isinstance(obj.get("result"), dict):
        raise RuntimeError("CKAN package_show did not return a successful dataset")
    resources = obj["result"].get("resources") or []
    candidates = [
        x for x in resources
        if str(x.get("format", "")).upper() in {"GTFS", "ZIP"}
        or str(x.get("url", "")).lower().endswith(".zip")
    ]
    if not candidates:
        raise RuntimeError("No GTFS/ZIP resource discovered in CKAN package")
    candidates.sort(
        key=lambda x: str(x.get("last_modified") or x.get("created") or ""),
        reverse=True
    )
    chosen = candidates[0]
    url = chosen["url"]
    p = work / "payload" / safe_name(url, "gtfs.zip")
    rec = download(s, url, p, work)
    validate_gtfs(p)
    rec["format"] = "GTFS/ZIP"
    return {
        "acquired_at": now(),
        "assets": [meta_rec, rec],
        "validation_result": "PASS_CKAN_GTFS_VALIDATED",
        "source_period_or_edition": chosen.get("last_modified") or chosen.get("created"),
        "limitations": "Scheduled supply only; GTFS validity is governed by the calendars in the feed."
    }


def ige_table(spec: dict, work: Path) -> dict:
    code = str(spec["parameters"]["table_code"])
    fmt = spec["parameters"].get("format", "csv").lower()
    if fmt not in {"csv", "json"}:
        raise ValueError("IGE table adapter supports csv or json")
    selection = str(spec["parameters"].get("selection", "")).lstrip("/")
    url = f"https://www.ige.gal/igebdt/igeapi/{fmt}/datos/{code}/" + selection
    s = session()
    p = work / "payload" / f"IGE-{code}.{fmt}"
    rec = download(s, url, p, work)
    rec["format"] = fmt.upper()
    if fmt == "json":
        json.loads(p.read_text(encoding="utf-8-sig"))
    elif p.stat().st_size < 20:
        raise RuntimeError("IGE CSV response unexpectedly small")
    return {
        "acquired_at": now(),
        "assets": [rec],
        "validation_result": "PASS_IGE_NATIVE_API_RESPONSE",
        "source_period_or_edition": spec["parameters"].get("period"),
        "limitations": "Producer-native DatoN/DatoT semantics are preserved; confidential/missing markers are not converted to zero."
    }


def opendatasoft(spec: dict, work: Path) -> dict:
    base = spec["parameters"]["base_url"].rstrip("/")
    dataset = spec["parameters"]["dataset_id"]
    limit = int(spec["parameters"].get("page_size", 100))
    s = session()
    assets = []
    offset = 0
    total = None
    observed = 0
    while total is None or offset < total:
        url = f"{base}/api/explore/v2.1/catalog/datasets/{urllib.parse.quote(dataset)}/records"
        r = s.get(url, params={"limit": limit, "offset": offset}, timeout=180)
        r.raise_for_status()
        b = r.content
        obj = r.json()
        if total is None:
            total = int(obj.get("total_count", 0))
        rows = obj.get("results") or []
        p = work / "payload" / f"records-{offset:06d}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
        assets.append({
            "path": str(p.relative_to(work)),
            "name": p.name,
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
            "source_url": r.url,
            "format": "JSON"
        })
        observed += len(rows)
        if not rows or len(rows) < limit:
            break
        offset += len(rows)
    if total is not None and observed < total:
        raise RuntimeError(f"OpenDataSoft pagination incomplete: {observed}/{total}")
    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_OPENDATASOFT_PAGINATED_NATIVE_JSON",
        "source_period_or_edition": None,
        "limitations": "Exact API pages preserved; null/missing producer fields are not coerced."
    }


ADAPTERS = {
    "eurostat": eurostat,
    "ine_json": ine_json,
    "static_http": static_http,
    "ckan_gtfs": ckan_gtfs,
    "ige_table": ige_table,
    "opendatasoft": opendatasoft,
}


def acquire(spec: dict, work: Path) -> dict:
    fn = ADAPTERS.get(spec["adapter"])
    if fn is None:
        raise ValueError(f"Unsupported adapter {spec['adapter']}")
    return fn(spec, work)
