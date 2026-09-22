from __future__ import annotations
import ast
import datetime as dt
import csv
import hashlib
import json
import re
import time
import urllib.parse
import zipfile
import xml.etree.ElementTree as ET
import ssl
from html.parser import HTMLParser
from pathlib import Path

import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .chunking import compose_geojson_pages, compose_json_record_pages, series_manifest
from .ine_partitioned import acquire as ine_partitioned_acquire

UA = "MobilidadeNorte-PublicAcquisition/0.2 (+source-preservation)"
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


def repair_incomplete_chain_session(host: str) -> requests.Session:
    """Build a verified session for servers that omit intermediate CA certs.

    The data request itself remains fully TLS-verified. We retrieve only the
    public leaf certificate without verification, follow its CA-Issuers AIA
    links, and retry against the system trust store plus those intermediates.
    """
    pem = ssl.get_server_certificate((host, 443))
    cert = x509.load_pem_x509_certificate(pem.encode("ascii"))
    chain_pems = []
    seen = set()

    for _ in range(3):
        try:
            aia = cert.extensions.get_extension_for_class(
                x509.AuthorityInformationAccess
            ).value
        except x509.ExtensionNotFound:
            break

        issuer_urls = [
            d.access_location.value
            for d in aia
            if d.access_method == x509.AuthorityInformationAccessOID.CA_ISSUERS
            and isinstance(d.access_location, x509.UniformResourceIdentifier)
        ]
        if not issuer_urls:
            break

        next_cert = None
        for url in issuer_urls:
            if url in seen:
                continue
            seen.add(url)
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            raw = r.content
            try:
                next_cert = x509.load_der_x509_certificate(raw)
            except ValueError:
                next_cert = x509.load_pem_x509_certificate(raw)
            chain_pems.append(
                next_cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
            )
            break
        if next_cert is None:
            break
        cert = next_cert
        if cert.issuer == cert.subject:
            break

    if not chain_pems:
        raise RuntimeError(f"Could not discover issuer chain for {host}")

    bundle = Path("/tmp") / f"mn-ca-{host.replace('.', '_')}.pem"
    system = Path("/etc/ssl/certs/ca-certificates.crt")
    if not system.is_file():
        raise RuntimeError("System CA bundle unavailable")
    bundle.write_text(
        system.read_text(encoding="utf-8", errors="ignore")
        + "\n"
        + "\n".join(chain_pems),
        encoding="utf-8",
    )
    s = session()
    s.verify = str(bundle)
    return s


def session(*, system_ca: bool = False, read_retries: int = 3) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    retry = Retry(
        total=4,
        connect=4,
        read=read_retries,
        status=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    if system_ca:
        bundle = Path("/etc/ssl/certs/ca-certificates.crt")
        if bundle.is_file():
            s.verify = str(bundle)
    return s


def download(
    s: requests.Session, url: str, path: Path, work: Path, *, timeout: int = TIMEOUT
) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with s.get(url, timeout=timeout, stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
        ctype = r.headers.get("content-type")
        final_url = r.url
    if path.stat().st_size == 0:
        raise RuntimeError(f"Empty source response: {url}")
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


def validate_ods(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "mimetype" not in names or "content.xml" not in names:
            raise ValueError(f"{path.name} is not a valid ODS package")
        mimetype = z.read("mimetype").decode("ascii", errors="ignore").strip()
        if mimetype != "application/vnd.oasis.opendocument.spreadsheet":
            raise ValueError(f"{path.name} has unexpected ODS mimetype {mimetype!r}")


def validate_xls(path: Path) -> None:
    head = path.read_bytes()[:8]
    if head != bytes.fromhex("D0CF11E0A1B11AE1"):
        raise ValueError(f"{path.name} is not a legacy OLE/XLS workbook")


def validate_avro_container(path: Path) -> None:
    if path.read_bytes()[:4] != b"Obj\x01":
        raise ValueError(f"{path.name} is not an Avro object container")


def validate_xml(path: Path) -> None:
    try:
        ET.fromstring(path.read_bytes())
    except ET.ParseError as e:
        raise ValueError(f"{path.name} is not well-formed XML") from e


def validate_xml_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        xml_names = [
            name for name in z.namelist()
            if not name.endswith("/") and name.lower().endswith(".xml")
        ]
        if not xml_names:
            raise ValueError(f"{path.name} contains no XML members")
        parsed = 0
        for name in xml_names:
            try:
                ET.fromstring(z.read(name))
                parsed += 1
            except ET.ParseError as e:
                raise ValueError(
                    f"{path.name} contains malformed XML member {name}"
                ) from e
        if parsed <= 0:
            raise ValueError(f"{path.name} contains no parseable XML members")


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
    if not isinstance(obj, dict) or "value" not in obj:
        raise RuntimeError("Eurostat response is not a materialized JSON-stat dataset")
    rec["format"] = "JSON-stat/JSON"
    return {
        "acquired_at": now(),
        "assets": [rec],
        "validation_result": "PASS_JSON_MATERIALIZED",
        "source_period_or_edition": spec["parameters"].get("period"),
        "limitations": "Producer-native API response preserved; no consumer normalization performed."
    }


def _ine_record(obj):
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj[0]
    if isinstance(obj, dict):
        return obj
    raise RuntimeError("Unexpected INE response shape")


def _ine_guard(obj) -> None:
    rec = _ine_record(obj)
    success = rec.get("Sucesso", rec.get("sucesso"))
    if isinstance(success, dict):
        false_part = success.get("Falso", success.get("false"))
        if false_part is not None:
            raise RuntimeError(f"INE semantic failure: {false_part}")
    if success is False or (isinstance(success, str) and success.strip().lower() in {"false", "falso", "0"}):
        raise RuntimeError("INE semantic failure")
    dados = rec.get("Dados", rec.get("dados"))
    if not isinstance(dados, dict):
        raise RuntimeError("INE response has no Dados object")
    rows = sum(len(v) for v in dados.values() if isinstance(v, list))
    if rows <= 0:
        raise RuntimeError("INE response contains zero observation records")


def _ine_dimension_members(meta, dim_num: int) -> dict[str, dict]:
    rec = _ine_record(meta)
    dims = rec.get("Dimensoes", rec.get("dimensoes"))
    found: dict[str, dict] = {}

    if isinstance(dims, dict):
        cats = dims.get("Categoria_Dim")
        if isinstance(cats, list) and cats and isinstance(cats[0], dict):
            for values in cats[0].values():
                if not isinstance(values, list) or not values or not isinstance(values[0], dict):
                    continue
                item = values[0]
                if str(item.get("dim_num")) != str(dim_num):
                    continue
                code = item.get("categ_cod")
                if code is not None:
                    found[str(code)] = item
            if found:
                return found

    if isinstance(dims, list):
        target = f"dim{dim_num}".lower()
        for d in dims:
            if not isinstance(d, dict) or str(d.get("Dim", "")).lower() != target:
                continue
            members = d.get("Membros")
            if not isinstance(members, list):
                continue
            for item in members:
                if isinstance(item, dict) and item.get("Codigo") is not None:
                    found[str(item["Codigo"])] = item
    return found


def _ine_resolve_label(meta, dim_num: int, wanted: str) -> str:
    members = _ine_dimension_members(meta, dim_num)
    if not members:
        raise RuntimeError(f"INE metadata exposes no members for Dim{dim_num}")

    needle = str(wanted).strip().casefold()
    exact = []
    contains = []
    for code, item in members.items():
        strings = []
        for value in item.values():
            if isinstance(value, (str, int, float)):
                strings.append(str(value).strip())
        folded = [s.casefold() for s in strings]
        if needle in folded:
            exact.append(code)
        elif any(needle in s for s in folded):
            contains.append(code)

    matches = exact if exact else contains
    if len(matches) != 1:
        sample = [
            {"code": code, "member": item}
            for code, item in list(members.items())[:8]
        ]
        raise RuntimeError(
            f"INE label resolution for Dim{dim_num} {wanted!r} returned {len(matches)} matches; "
            f"sample={json.dumps(sample, ensure_ascii=False)}"
        )
    return matches[0]


def ine_json(spec: dict, work: Path) -> dict:
    indicator = str(spec["parameters"]["indicator"]).zfill(7)
    target_year = spec["parameters"].get("year")
    base = "https://www.ine.pt/ine/json_indicador"
    s = session(read_retries=0)
    assets = []
    meta_url = f"{base}/pindicaMeta.jsp?" + urllib.parse.urlencode({"varcd": indicator, "lang": "PT"})
    mp = work / "payload" / f"{indicator}-metadata.json"
    meta = download(s, meta_url, mp, work, timeout=90)
    meta["format"] = "JSON"
    assets.append(meta)
    obj = json.loads(mp.read_text(encoding="utf-8-sig"))
    period_re = re.compile(r"S7[A-Za-z0-9._-]*20\d{2}[A-Za-z0-9._-]*")
    found = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(str(k))
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            found.update(period_re.findall(x))

    walk(obj)
    label_contains = spec["parameters"].get("period_label_contains")
    periods = sorted(x for x in found if target_year is None or str(target_year) in x)
    dim1 = _ine_dimension_members(obj, 1)

    if label_contains and dim1:
        needle = str(label_contains).lower()
        periods = sorted(
            code for code, item in dim1.items()
            if needle in code.lower()
            or needle in json.dumps(item, ensure_ascii=False).lower()
        )
    elif not periods and dim1:
        if target_year is None:
            periods = sorted(dim1)
        else:
            year = str(target_year)
            periods = sorted(
                code for code, item in dim1.items()
                if year in code or year in json.dumps(item, ensure_ascii=False)
            )

    if not periods:
        wanted = label_contains if label_contains else target_year
        sample = [
            {"code": code, "member": item}
            for code, item in list(dim1.items())[:8]
        ]
        raise RuntimeError(
            f"INE metadata exposed no Dim1 member for requested period {wanted}; "
            f"sample={json.dumps(sample, ensure_ascii=False)}"
        )
    if target_year is None and len(periods) > 24:
        raise RuntimeError(
            "Unbounded INE acquisition refused: specify a target year or a bounded period selection"
        )

    selections = {}
    for k, label in (spec["parameters"].get("dimension_labels") or {}).items():
        dim = int(k)
        if dim <= 1:
            raise RuntimeError("dimension_labels may only target Dim2 and higher")
        selections[dim] = _ine_resolve_label(obj, dim, str(label))

    print(json.dumps(
        {
            "ine_resolution": {
                "indicator": indicator,
                "periods": periods,
                "dimension_codes": {f"Dim{k}": v for k, v in sorted(selections.items())}
            }
        },
        ensure_ascii=False
    ), flush=True)

    spacing = max(2.0, float(spec["parameters"].get("spacing_seconds", 2)))
    for i, period in enumerate(periods):
        if i:
            time.sleep(spacing)
        params = {"op": "2", "varcd": indicator, "lang": "PT", "Dim1": period}
        params.update({f"Dim{dim}": code for dim, code in sorted(selections.items())})
        url = f"{base}/pindica.jsp?" + urllib.parse.urlencode(params)
        p = work / "payload" / f"{indicator}-{period}.json"
        rec = download(s, url, p, work, timeout=120)
        data_obj = json.loads(p.read_text(encoding="utf-8-sig"))
        _ine_guard(data_obj)
        rec["format"] = "JSON"
        assets.append(rec)

    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_INE_METADATA_AND_NATIVE_JSON",
        "source_period_or_edition": str(target_year) if target_year is not None else None,
        "limitations": (
            "Raw INE metadata and bounded producer-native responses preserved; "
            "requested dimension labels are resolved against producer metadata before acquisition; "
            "missing/confidential values are not transformed."
        )
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

        min_bytes = int(item.get("min_bytes", 1))
        if p.stat().st_size < min_bytes:
            raise RuntimeError(f"{name} smaller than minimum expected size {min_bytes}")

        if fmt == "XLSX":
            validate_xlsx(p)
        elif fmt == "XLS":
            validate_xls(p)
        elif fmt == "ODS":
            validate_ods(p)
        elif fmt == "AVRO":
            validate_avro_container(p)
        elif fmt == "XML":
            validate_xml(p)
        elif fmt in {"XML_ZIP", "NETEX_ZIP", "DATEX2_ZIP"}:
            validate_xml_zip(p)
        elif fmt == "JSON":
            json.loads(p.read_text(encoding="utf-8-sig"))
        elif fmt in {"HTML", "HTM"}:
            text = p.read_text(encoding="utf-8", errors="replace")
            if "<html" not in text.lower() and "<table" not in text.lower():
                raise RuntimeError(f"{name} is not recognizable HTML/table content")
            marker = item.get("contains")
            if marker and marker.lower() not in text.lower():
                raise RuntimeError(f"{name} does not contain required marker {marker!r}")
        elif fmt in {"CSV", "TSV"}:
            head = p.read_bytes()[:500].lower()
            if b"<html" in head or b"<!doctype" in head:
                raise RuntimeError(f"{name} returned HTML instead of tabular data")

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


def gtfs_static(spec: dict, work: Path) -> dict:
    url = spec["parameters"]["url"]
    s = session()
    p = work / "payload" / (spec["parameters"].get("filename") or "gtfs.zip")
    rec = download(s, url, p, work)
    validate_gtfs(p)
    rec["format"] = "GTFS/ZIP"
    return {
        "acquired_at": now(),
        "assets": [rec],
        "validation_result": "PASS_STATIC_GTFS_VALIDATED",
        "source_period_or_edition": spec["parameters"].get("period"),
        "limitations": "Scheduled supply only; producer-native GTFS files and missingness are preserved."
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
    fmt = spec["parameters"].get("format", "json").lower()
    if fmt not in {"csv", "json"}:
        raise ValueError("IGE table adapter supports csv or json")
    selection = str(spec["parameters"].get("selection", "")).strip("/")
    url = f"https://www.ige.gal/igebdt/igeapi/{fmt}/datos/{code}"
    if selection:
        url += "/" + selection

    s = session(system_ca=True)
    p = work / "payload" / f"IGE-{code}.{fmt}"
    try:
        rec = download(s, url, p, work)
    except requests.exceptions.SSLError:
        s = repair_incomplete_chain_session("www.ige.gal")
        rec = download(s, url, p, work)
    rec["format"] = fmt.upper()

    if fmt == "json":
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("iso-8859-1")
        obj = json.loads(text)
        if not isinstance(obj, dict) or not isinstance(obj.get("variables"), list) or not isinstance(obj.get("datos"), list):
            raise RuntimeError("IGE response does not match the documented table JSON structure")
        if not obj["datos"]:
            raise RuntimeError("IGE table returned zero rows")
    else:
        if p.stat().st_size < 20:
            raise RuntimeError("IGE CSV response unexpectedly small")
        head = p.read_bytes()[:500].lower()
        if b"<html" in head or b"<!doctype" in head:
            raise RuntimeError("IGE CSV route returned HTML instead of CSV")

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
    limit = min(100, int(spec["parameters"].get("page_size", 100)))
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
            "format": "JSON",
            "role": "native"
        })
        observed += len(rows)
        if not rows or len(rows) < limit:
            break
        offset += len(rows)

    if total is not None and observed < total:
        raise RuntimeError(f"OpenDataSoft pagination incomplete: {observed}/{total}")
    if not assets or observed <= 0:
        raise RuntimeError("OpenDataSoft dataset returned zero records")

    recomposed = compose_json_record_pages(work, assets, results_key="results")
    return {
        "acquired_at": now(),
        "assets": [*assets, *recomposed],
        "validation_result": "PASS_OPENDATASOFT_PAGINATED_RECOMPOSED",
        "source_period_or_edition": None,
        "limitations": (
            "Exact API pages are preserved as native chunks and deterministically recomposed "
            "to JSONL without coercing null/missing producer fields."
        )
    }



class _TableCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self._table = None
        self._row = None
        self._cell = None
        self._cell_parts = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "table":
            self._table = []
        elif t == "tr" and self._table is not None:
            self._row = []
        elif t in {"td", "th"} and self._row is not None:
            self._cell = {"kind": t, "text": ""}
            self._cell_parts = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in {"td", "th"} and self._cell is not None:
            self._cell["text"] = " ".join(" ".join(self._cell_parts).split())
            self._row.append(self._cell)
            self._cell = None
            self._cell_parts = []
        elif t == "tr" and self._row is not None:
            if any(cell.get("text") for cell in self._row):
                self._table.append(self._row)
            self._row = None
        elif t == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None


class _LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append({
                "href": self._href,
                "text": " ".join(" ".join(self._text).split())
            })
            self._href = None
            self._text = []


def html_assets(spec: dict, work: Path) -> dict:
    """Discover and acquire downloadable public assets from a producer landing page."""
    pms = spec["parameters"]
    landing = pms.get("landing_url") or spec["source"]["landing_url"]
    s = session(system_ca=bool(pms.get("system_ca", False)))
    r = s.get(landing, timeout=180, allow_redirects=True)
    r.raise_for_status()
    raw = r.content
    text = raw.decode(r.encoding or "utf-8", errors="replace")
    if "<html" not in text.lower() and "<a " not in text.lower():
        raise RuntimeError("Landing route did not return recognizable HTML")

    lp = work / "payload" / "landing.html"
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_bytes(raw)
    landing_rec = {
        "path": str(lp.relative_to(work)),
        "name": "landing.html",
        "sha256": sha256(lp),
        "bytes": lp.stat().st_size,
        "source_url": r.url,
        "format": "HTML",
        "role": "native"
    }

    parser = _LinkCollector()
    parser.feed(text)
    href_re = re.compile(pms.get("include_href_regex", ".*"), re.I)
    text_re = re.compile(pms.get("include_text_regex", ".*"), re.I)
    allowed_exts = {
        x.lower() if x.startswith(".") else "." + x.lower()
        for x in pms.get(
            "allowed_extensions",
            ["pdf", "xls", "xlsx", "ods", "csv", "zip", "json", "geojson", "gpkg", "gml", "xml", "avro"]
        )
    }
    allowed_hosts = [x.lower() for x in pms.get("allowed_host_suffixes", [])]
    max_assets = max(1, int(pms.get("max_assets", 10)))
    ctype_re = re.compile(pms.get("content_type_regex", ".*"), re.I)

    candidates = []
    seen = set()
    for link in parser.links:
        href = (link.get("href") or "").strip()
        label = (link.get("text") or "").strip()
        if not href:
            continue
        url = urllib.parse.urljoin(r.url, href)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if allowed_hosts and not any(parsed.hostname and parsed.hostname.lower().endswith(x) for x in allowed_hosts):
            continue
        ext = Path(parsed.path).suffix.lower()
        if ext not in allowed_exts and not href_re.search(url):
            continue
        if not href_re.search(url) or not text_re.search(label):
            continue
        if url in seen:
            continue
        seen.add(url)
        candidates.append((url, label))
        if len(candidates) >= max_assets:
            break

    if not candidates:
        raise RuntimeError("Landing page exposed no downloadable asset matching the declared rules")

    assets = [landing_rec]
    for i, (url, label) in enumerate(candidates, 1):
        ext = Path(urllib.parse.urlparse(url).path).suffix
        fallback = f"asset-{i:03d}{ext or '.bin'}"
        name = safe_name(url, fallback)
        p = work / "payload" / name
        rec = download(s, url, p, work)
        ctype = rec.get("content_type") or ""
        if not ctype_re.search(ctype):
            raise RuntimeError(
                f"Discovered asset {url} content type {ctype!r} failed declared check"
            )
        head = p.read_bytes()[:16]
        if "pdf" in ctype.lower() and not head.startswith(b"%PDF"):
            raise RuntimeError(f"Discovered PDF asset failed signature check: {url}")
        if ext.lower() == ".xlsx":
            validate_xlsx(p)
        elif ext.lower() == ".xls":
            validate_xls(p)
        elif ext.lower() == ".ods":
            validate_ods(p)
        elif ext.lower() == ".avro":
            validate_avro_container(p)
        rec["format"] = ctype or (ext.lstrip(".").upper() if ext else "BINARY")
        rec["link_text"] = label
        rec["role"] = "native"
        assets.append(rec)

    recomposed = series_manifest(
        work,
        assets[1:],
        series_key=str(pms.get("series_key") or spec["product_key"])
    )
    return {
        "acquired_at": now(),
        "assets": [*assets, *recomposed],
        "validation_result": "PASS_HTML_ASSET_DISCOVERY_SERIES_COMPOSED",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Producer landing HTML and selected linked assets are preserved natively. "
            "Multiple linked files are recomposed as an ordered logical series manifest; "
            "heterogeneous files are not row-concatenated without a product-specific semantic assembler."
        )
    }


def arcgis_feature_service(spec: dict, work: Path) -> dict:
    """Acquire a complete public ArcGIS Feature Layer query as native GeoJSON pages."""
    pms = spec["parameters"]
    layer_url = pms["layer_url"].rstrip("/")
    s = session(system_ca=bool(pms.get("system_ca", False)))

    mr = s.get(layer_url, params={"f": "json"}, timeout=180)
    mr.raise_for_status()
    meta = mr.json()
    if meta.get("error"):
        raise RuntimeError(f"ArcGIS layer metadata error: {meta['error']}")
    if not meta.get("geometryType") or not isinstance(meta.get("fields"), list):
        raise RuntimeError("ArcGIS route is not a queryable feature layer")

    mp = work / "payload" / "layer-metadata.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assets = [{
        "path": str(mp.relative_to(work)),
        "name": mp.name,
        "sha256": sha256(mp),
        "bytes": mp.stat().st_size,
        "source_url": mr.url,
        "format": "JSON",
        "role": "native"
    }]

    where = str(pms.get("where", "1=1"))
    cr = s.get(
        layer_url + "/query",
        params={"f": "json", "where": where, "returnCountOnly": "true"},
        timeout=180
    )
    cr.raise_for_status()
    count_obj = cr.json()
    if count_obj.get("error"):
        raise RuntimeError(f"ArcGIS count query error: {count_obj['error']}")
    total = int(count_obj.get("count", 0))
    if total <= 0:
        raise RuntimeError("ArcGIS query returned zero features")

    page_size = min(
        int(pms.get("page_size", meta.get("maxRecordCount") or 1000)),
        int(meta.get("maxRecordCount") or 2000)
    )
    out_fields = str(pms.get("out_fields", "*"))
    out_sr = str(pms.get("out_sr", 4326))
    oid = meta.get("objectIdField") or meta.get("objectIdFieldName")
    offset = 0
    observed = 0

    while offset < total:
        params = {
            "f": "geojson",
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": out_sr,
            "resultOffset": offset,
            "resultRecordCount": page_size
        }
        if oid:
            params["orderByFields"] = f"{oid} ASC"
        qr = s.get(layer_url + "/query", params=params, timeout=TIMEOUT)
        qr.raise_for_status()
        obj = qr.json()
        if obj.get("error"):
            raise RuntimeError(f"ArcGIS page query error: {obj['error']}")
        features = obj.get("features")
        if not isinstance(features, list) or not features:
            raise RuntimeError(f"ArcGIS pagination stopped early at offset {offset}")

        pp = work / "payload" / f"features-{offset:06d}.geojson"
        pp.write_text(json.dumps(obj, ensure_ascii=False) + "\n", encoding="utf-8")
        assets.append({
            "path": str(pp.relative_to(work)),
            "name": pp.name,
            "sha256": sha256(pp),
            "bytes": pp.stat().st_size,
            "source_url": qr.url,
            "format": "GeoJSON",
            "role": "native"
        })
        observed += len(features)
        offset += len(features)

    if observed != total:
        raise RuntimeError(f"ArcGIS completeness mismatch: observed {observed}, expected {total}")

    recomposed = compose_geojson_pages(work, assets[1:])
    return {
        "acquired_at": now(),
        "assets": [*assets, *recomposed],
        "validation_result": "PASS_ARCGIS_COMPLETE_FEATURE_QUERY_RECOMPOSED",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Complete producer feature query is preserved as native layer metadata and ordered "
            "GeoJSON pages, then deterministically recomposed to one FeatureCollection; "
            "no geometry simplification or classification remapping."
        )
    }


def _json_path(obj, path: str | None):
    if not path:
        return obj
    cur = obj
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise RuntimeError(f"JSON path {path!r} not found at {part!r}")
    return cur


def rest_json(spec: dict, work: Path) -> dict:
    """Acquire one or more bounded public REST/JSON endpoints without inventing pagination."""
    pms = spec["parameters"]
    declared = pms.get("requests")
    if declared is None:
        declared = [{
            "key": pms.get("key", "response"),
            "url": pms["url"],
            "query": pms.get("query", {}),
            "records_path": pms.get("records_path"),
            "min_records": pms.get("min_records", 0),
        }]
    if not isinstance(declared, list) or not declared:
        raise RuntimeError("rest_json requires at least one declared request")

    s = session(system_ca=bool(pms.get("system_ca", False)))
    assets = []
    for i, item in enumerate(declared, 1):
        url = str(item["url"])
        key = re.sub(r"[^A-Za-z0-9._-]+", "_", str(item.get("key") or f"response-{i}"))
        r = s.get(url, params=item.get("query") or {}, timeout=180, allow_redirects=True)
        r.raise_for_status()
        raw = r.content
        obj = r.json()

        expected = str(item.get("expected_top_level") or "").lower()
        if expected == "object" and not isinstance(obj, dict):
            raise RuntimeError(f"REST JSON {key} expected an object")
        if expected == "array" and not isinstance(obj, list):
            raise RuntimeError(f"REST JSON {key} expected an array")

        records_path = item.get("records_path")
        target = _json_path(obj, records_path) if records_path else obj
        min_records = int(item.get("min_records", 0))
        if min_records:
            if not isinstance(target, (list, dict)):
                raise RuntimeError(f"REST JSON {key} records target is not countable")
            if len(target) < min_records:
                raise RuntimeError(
                    f"REST JSON {key} returned {len(target)} records below minimum {min_records}"
                )

        p = work / "payload" / f"{key}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        assets.append({
            "path": str(p.relative_to(work)),
            "name": p.name,
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
            "source_url": r.url,
            "format": "JSON",
            "role": "native",
        })

    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_BOUNDED_REST_JSON",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Only explicitly declared bounded REST requests are executed. "
            "No implicit pagination or joining of heterogeneous endpoint responses is performed."
        ),
    }


def ckan_resource(spec: dict, work: Path) -> dict:
    """Resolve and preserve arbitrary public CKAN resources, without assuming GTFS."""
    pms = spec["parameters"]
    api = str(pms["package_show_url"])
    s = session(system_ca=bool(pms.get("system_ca", False)))

    r = s.get(api, timeout=180)
    r.raise_for_status()
    obj = r.json()
    if not obj.get("success") or not isinstance(obj.get("result"), dict):
        raise RuntimeError("CKAN package_show did not return a successful dataset")

    mp = work / "payload" / "ckan-package-show.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_bytes(r.content)
    assets = [{
        "path": str(mp.relative_to(work)),
        "name": mp.name,
        "sha256": sha256(mp),
        "bytes": mp.stat().st_size,
        "source_url": r.url,
        "format": "JSON",
        "role": "native",
    }]

    result = obj["result"]
    resources = result.get("resources") or []
    name_re = re.compile(str(pms.get("resource_name_regex") or ".*"), re.I)
    url_re = re.compile(str(pms.get("resource_url_regex") or ".*"), re.I)
    formats = {str(x).upper() for x in (pms.get("formats") or [])}
    candidates = []
    for resource in resources:
        name = str(resource.get("name") or resource.get("description") or "")
        url = str(resource.get("url") or "")
        fmt = str(resource.get("format") or "").upper()
        if not url or not name_re.search(name) or not url_re.search(url):
            continue
        if formats and fmt not in formats:
            continue
        candidates.append(resource)

    candidates.sort(
        key=lambda x: (
            str(x.get("last_modified") or x.get("created") or ""),
            str(x.get("name") or ""),
            str(x.get("url") or ""),
        ),
        reverse=True,
    )
    if pms.get("latest_only") and candidates:
        candidates = candidates[:1]
    max_assets = max(1, int(pms.get("max_assets", 20)))
    candidates = candidates[:max_assets]
    if not candidates:
        raise RuntimeError("No CKAN resource matched the declared selection")

    native_downloads = []
    for i, resource in enumerate(candidates, 1):
        url = str(resource["url"])
        fmt = str(resource.get("format") or Path(urllib.parse.urlparse(url).path).suffix.lstrip(".") or "binary").upper()
        name = safe_name(url, f"resource-{i:03d}.{fmt.lower()}")
        p = work / "payload" / name
        rec = download(s, url, p, work)
        if fmt == "XLSX":
            validate_xlsx(p)
        elif fmt == "XLS":
            validate_xls(p)
        elif fmt == "ODS":
            validate_ods(p)
        elif fmt == "AVRO":
            validate_avro_container(p)
        elif fmt == "JSON":
            json.loads(p.read_text(encoding="utf-8-sig"))
        elif fmt in {"CSV", "TSV"}:
            head = p.read_bytes()[:500].lower()
            if b"<html" in head or b"<!doctype" in head:
                raise RuntimeError(f"CKAN resource {name} returned HTML")
        rec.update({"format": fmt, "role": "native"})
        assets.append(rec)
        native_downloads.append(rec)

    recomposed = series_manifest(
        work,
        native_downloads,
        series_key=str(pms.get("series_key") or spec["product_key"]),
    )
    return {
        "acquired_at": now(),
        "assets": [*assets, *recomposed],
        "validation_result": "PASS_CKAN_RESOURCE_SERIES",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "CKAN metadata and matched producer resources are preserved natively. "
            "Multiple resources are represented as an ordered series manifest and are not row-joined."
        ),
    }


def ogc_api_features(spec: dict, work: Path) -> dict:
    """Acquire OGC API - Features collection pages by following producer next links."""
    pms = spec["parameters"]
    collection_url = str(pms["collection_url"]).rstrip("/")
    items_url = str(pms.get("items_url") or (collection_url + "/items"))
    s = session(system_ca=bool(pms.get("system_ca", False)))

    mr = s.get(collection_url, timeout=180, allow_redirects=True)
    mr.raise_for_status()
    meta = mr.json()
    if not isinstance(meta, dict):
        raise RuntimeError("OGC collection metadata is not a JSON object")
    mp = work / "payload" / "collection-metadata.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_bytes(mr.content)
    assets = [{
        "path": str(mp.relative_to(work)),
        "name": mp.name,
        "sha256": sha256(mp),
        "bytes": mp.stat().st_size,
        "source_url": mr.url,
        "format": "JSON",
        "role": "native",
    }]

    params = dict(pms.get("query") or {})
    params.setdefault("limit", min(10000, int(pms.get("page_size", 1000))))
    next_url = items_url
    next_params = params
    page = 0
    observed = 0
    matched = None
    seen_urls = set()
    native_pages = []
    max_pages = max(1, int(pms.get("max_pages", 10000)))

    while next_url:
        page += 1
        if page > max_pages:
            raise RuntimeError("OGC API pagination exceeded declared max_pages")
        r = s.get(next_url, params=next_params, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        canonical_url = r.url
        if canonical_url in seen_urls:
            raise RuntimeError("OGC API pagination loop detected")
        seen_urls.add(canonical_url)

        obj = r.json()
        if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
            raise RuntimeError("OGC API items response is not a GeoJSON FeatureCollection")
        if matched is None and obj.get("numberMatched") is not None:
            matched = int(obj["numberMatched"])

        pp = work / "payload" / f"features-{page:05d}.geojson"
        pp.write_bytes(r.content)
        rec = {
            "path": str(pp.relative_to(work)),
            "name": pp.name,
            "sha256": sha256(pp),
            "bytes": pp.stat().st_size,
            "source_url": canonical_url,
            "format": "GeoJSON",
            "role": "native",
        }
        assets.append(rec)
        native_pages.append(rec)
        observed += len(obj["features"])

        next_link = None
        for link in obj.get("links") or []:
            if str(link.get("rel") or "").lower() == "next" and link.get("href"):
                next_link = urllib.parse.urljoin(canonical_url, str(link["href"]))
                break
        next_url = next_link
        next_params = None

    if not native_pages:
        raise RuntimeError("OGC API returned no feature pages")
    if matched is not None and observed != matched:
        raise RuntimeError(f"OGC API completeness mismatch: observed {observed}, matched {matched}")

    recomposed = compose_geojson_pages(work, native_pages)
    return {
        "acquired_at": now(),
        "assets": [*assets, *recomposed],
        "validation_result": "PASS_OGC_API_FEATURES_RECOMPOSED",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Collection metadata and every producer GeoJSON page are preserved natively. "
            "Pagination follows producer rel=next links; recomposition does not simplify geometries."
        ),
    }


def atom_feed(spec: dict, work: Path) -> dict:
    """Acquire downloadable assets exposed by an Atom feed."""
    pms = spec["parameters"]
    feed_url = str(pms["feed_url"])
    s = session(system_ca=bool(pms.get("system_ca", False)))
    r = s.get(feed_url, timeout=180, allow_redirects=True)
    r.raise_for_status()
    raw = r.content
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise RuntimeError("ATOM feed is not valid XML") from e

    fp = work / "payload" / "feed.xml"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(raw)
    feed_rec = {
        "path": str(fp.relative_to(work)),
        "name": fp.name,
        "sha256": sha256(fp),
        "bytes": fp.stat().st_size,
        "source_url": r.url,
        "format": "ATOM/XML",
        "role": "native",
    }

    href_re = re.compile(str(pms.get("include_href_regex") or ".*"), re.I)
    allowed_exts = {
        x.lower() if str(x).startswith(".") else "." + str(x).lower()
        for x in pms.get("allowed_extensions", ["zip", "gpkg", "shp", "csv", "json", "geojson", "tif", "tiff"])
    }
    links = []
    seen = set()
    for elem in root.iter():
        if elem.tag.split("}")[-1].lower() != "link":
            continue
        href = str(elem.attrib.get("href") or "").strip()
        if not href:
            continue
        url = urllib.parse.urljoin(r.url, href)
        parsed = urllib.parse.urlparse(url)
        ext = Path(parsed.path).suffix.lower()
        if not href_re.search(url):
            continue
        if allowed_exts and ext not in allowed_exts:
            continue
        if url in seen:
            continue
        seen.add(url)
        links.append(url)

    max_assets = max(1, int(pms.get("max_assets", 20)))
    links = links[:max_assets]
    if not links:
        raise RuntimeError("ATOM feed exposed no downloadable asset matching declared rules")

    assets = [feed_rec]
    downloads = []
    for i, url in enumerate(links, 1):
        ext = Path(urllib.parse.urlparse(url).path).suffix
        name = safe_name(url, f"atom-asset-{i:03d}{ext or '.bin'}")
        p = work / "payload" / name
        rec = download(s, url, p, work)
        rec.update({
            "format": (ext.lstrip(".").upper() if ext else "BINARY"),
            "role": "native",
        })
        assets.append(rec)
        downloads.append(rec)

    recomposed = series_manifest(
        work,
        downloads,
        series_key=str(pms.get("series_key") or spec["product_key"]),
    )
    return {
        "acquired_at": now(),
        "assets": [*assets, *recomposed],
        "validation_result": "PASS_ATOM_DOWNLOAD_SERIES",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "The producer Atom feed and selected linked distributions are preserved natively. "
            "The composition output is an ordered series manifest only."
        ),
    }


def bpstat_jsonstat(spec: dict, work: Path) -> dict:
    """Acquire bounded BPstat series from the documented public JSON-stat API."""
    pms = spec["parameters"]
    domain_id = str(pms["domain_id"])
    dataset_id = str(pms["dataset_id"])
    series_ids = pms.get("series_ids")
    if isinstance(series_ids, (str, int)):
        series_ids = [str(series_ids)]
    else:
        series_ids = [str(x) for x in (series_ids or [])]
    if not series_ids:
        raise RuntimeError("bpstat_jsonstat requires one or more explicit series_ids")

    lang = str(pms.get("lang", "PT")).upper()
    base = (
        "https://bpstat.bportugal.pt/data/v1/domains/"
        + urllib.parse.quote(domain_id)
        + "/datasets/"
        + urllib.parse.quote(dataset_id)
    )
    s = session()
    assets = []
    for series_id in series_ids:
        r = s.get(
            base,
            params={"lang": lang, "series_ids": series_id},
            timeout=180,
            allow_redirects=True,
        )
        r.raise_for_status()
        obj = r.json()
        if not isinstance(obj, dict) or "value" not in obj:
            raise RuntimeError(f"BPstat series {series_id} is not a JSON-stat response")
        if not isinstance(obj.get("value"), (list, dict)):
            raise RuntimeError(f"BPstat series {series_id} has invalid JSON-stat values")

        p = work / "payload" / f"bpstat-{domain_id}-{dataset_id}-{series_id}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
        assets.append({
            "path": str(p.relative_to(work)),
            "name": p.name,
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
            "source_url": r.url,
            "format": "JSON-stat/JSON",
            "role": "native",
        })

    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_BPSTAT_BOUNDED_JSONSTAT",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Only explicitly identified BPstat series are acquired. "
            "Producer JSON-stat is preserved without consumer normalization or cross-series joining."
        ),
    }


def wfs(spec: dict, work: Path) -> dict:
    """Acquire a bounded WFS feature type, preserving capabilities and producer pages."""
    pms = spec["parameters"]
    service_url = str(pms["service_url"])
    version = str(pms.get("version", "2.0.0"))
    type_name = str(pms["type_name"])
    output_format = str(pms.get("output_format", "application/json"))
    page_size = max(1, int(pms.get("page_size", 1000)))
    max_pages = max(1, int(pms.get("max_pages", 10000)))
    s = session(system_ca=bool(pms.get("system_ca", False)))

    cap_params = {"SERVICE": "WFS", "REQUEST": "GetCapabilities", "VERSION": version}
    cap = s.get(service_url, params=cap_params, timeout=180, allow_redirects=True)
    cap.raise_for_status()
    try:
        cap_root = ET.fromstring(cap.content)
    except ET.ParseError as e:
        raise RuntimeError("WFS GetCapabilities is not valid XML") from e

    feature_names = {
        (el.text or "").strip()
        for el in cap_root.iter()
        if el.tag.split("}")[-1] == "Name" and (el.text or "").strip()
    }
    if feature_names and type_name not in feature_names:
        local = type_name.split(":")[-1]
        if not any(x.split(":")[-1] == local for x in feature_names):
            raise RuntimeError(f"WFS feature type {type_name!r} absent from capabilities")

    cp = work / "payload" / "wfs-capabilities.xml"
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_bytes(cap.content)
    assets = [{
        "path": str(cp.relative_to(work)),
        "name": cp.name,
        "sha256": sha256(cp),
        "bytes": cp.stat().st_size,
        "source_url": cap.url,
        "format": "WFS-Capabilities/XML",
        "role": "native",
    }]

    hits_params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "VERSION": version,
        "TYPENAMES": type_name,
        "RESULTTYPE": "hits",
    }
    hits = s.get(service_url, params=hits_params, timeout=180, allow_redirects=True)
    hits.raise_for_status()
    total = None
    try:
        hits_root = ET.fromstring(hits.content)
        raw_total = (
            hits_root.attrib.get("numberMatched")
            or hits_root.attrib.get("numberOfFeatures")
        )
        if raw_total not in (None, "unknown"):
            total = int(raw_total)
    except ET.ParseError:
        pass

    native_pages = []
    observed = 0
    start = 0
    page = 0
    use_json = "json" in output_format.lower()

    while total is None or start < total:
        page += 1
        if page > max_pages:
            raise RuntimeError("WFS pagination exceeded declared max_pages")
        params = {
            "SERVICE": "WFS",
            "REQUEST": "GetFeature",
            "VERSION": version,
            "TYPENAMES": type_name,
            "OUTPUTFORMAT": output_format,
            "COUNT": page_size,
            "STARTINDEX": start,
        }
        params.update(pms.get("query") or {})
        r = s.get(service_url, params=params, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()

        if use_json:
            obj = r.json()
            if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
                raise RuntimeError("WFS JSON response is not a GeoJSON FeatureCollection")
            count = len(obj["features"])
            if total is None and obj.get("numberMatched") not in (None, "unknown"):
                total = int(obj["numberMatched"])
            suffix = "geojson"
            fmt = "GeoJSON"
        else:
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as e:
                raise RuntimeError("WFS feature response is neither valid JSON nor XML") from e
            count = sum(
                1 for el in root.iter()
                if el.tag.split("}")[-1] in {"member", "featureMember"}
            )
            raw_total = root.attrib.get("numberMatched") or root.attrib.get("numberOfFeatures")
            if total is None and raw_total not in (None, "unknown"):
                total = int(raw_total)
            suffix = "gml"
            fmt = "GML/XML"

        if count <= 0:
            if total in (0, None) and page == 1:
                raise RuntimeError("WFS feature type returned zero features")
            break

        pp = work / "payload" / f"wfs-features-{start:07d}.{suffix}"
        pp.write_bytes(r.content)
        rec = {
            "path": str(pp.relative_to(work)),
            "name": pp.name,
            "sha256": sha256(pp),
            "bytes": pp.stat().st_size,
            "source_url": r.url,
            "format": fmt,
            "role": "native",
        }
        assets.append(rec)
        native_pages.append(rec)
        observed += count
        start += count

        if count < page_size and total is None:
            total = observed

    if total is not None and observed != total:
        raise RuntimeError(f"WFS completeness mismatch: observed {observed}, expected {total}")

    recomposed = compose_geojson_pages(work, native_pages) if use_json else series_manifest(
        work, native_pages, series_key=str(pms.get("series_key") or spec["product_key"])
    )
    return {
        "acquired_at": now(),
        "assets": [*assets, *recomposed],
        "validation_result": (
            "PASS_WFS_GEOJSON_RECOMPOSED"
            if use_json else "PASS_WFS_GML_SERIES"
        ),
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "WFS capabilities and every bounded producer feature page are preserved natively. "
            "GeoJSON pages are deterministically recomposed; GML pages remain an ordered series."
        ),
    }


def sdmx_rest(spec: dict, work: Path) -> dict:
    """Acquire an explicitly bounded SDMX REST query and optional structure response."""
    pms = spec["parameters"]
    data_url = str(pms["data_url"])
    data_params = pms.get("query") or {}
    fmt = str(pms.get("format", "json")).lower()
    if fmt not in {"json", "csv", "xml"}:
        raise RuntimeError("sdmx_rest format must be json, csv or xml")

    accept = {
        "json": str(pms.get("accept") or "application/vnd.sdmx.data+json;version=2.0.0"),
        "csv": str(pms.get("accept") or "text/csv"),
        "xml": str(pms.get("accept") or "application/vnd.sdmx.genericdata+xml;version=2.1"),
    }[fmt]
    s = session()
    headers = {"Accept": accept}

    assets = []
    structure_url = pms.get("structure_url")
    if structure_url:
        sr = s.get(
            str(structure_url),
            params=pms.get("structure_query") or {},
            headers={"Accept": str(pms.get("structure_accept") or "application/vnd.sdmx.structure+json;version=2.0.0")},
            timeout=180,
            allow_redirects=True,
        )
        sr.raise_for_status()
        sp = work / "payload" / "sdmx-structure.json"
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_bytes(sr.content)
        if "json" in str(sr.headers.get("content-type") or "").lower():
            json.loads(sr.content.decode("utf-8-sig"))
        assets.append({
            "path": str(sp.relative_to(work)),
            "name": sp.name,
            "sha256": sha256(sp),
            "bytes": sp.stat().st_size,
            "source_url": sr.url,
            "format": "SDMX-Structure",
            "role": "native",
        })

    r = s.get(
        data_url,
        params=data_params,
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    r.raise_for_status()
    suffix = {"json": "json", "csv": "csv", "xml": "xml"}[fmt]
    dp = work / "payload" / f"sdmx-data.{suffix}"
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_bytes(r.content)

    if fmt == "json":
        obj = r.json()
        valid = (
            isinstance(obj, dict)
            and (
                "dataSets" in obj
                or "value" in obj
                or "data" in obj
                or "structure" in obj
            )
        )
        if not valid:
            raise RuntimeError("SDMX JSON response does not expose a recognized data container")
    elif fmt == "csv":
        head = dp.read_bytes()[:1000]
        if b"<html" in head.lower() or b"<!doctype" in head.lower():
            raise RuntimeError("SDMX CSV route returned HTML")
        if b"," not in head and b";" not in head and b"\t" not in head:
            raise RuntimeError("SDMX CSV response has no recognizable delimiter")
    else:
        try:
            ET.fromstring(r.content)
        except ET.ParseError as e:
            raise RuntimeError("SDMX XML response is not valid XML") from e

    assets.append({
        "path": str(dp.relative_to(work)),
        "name": dp.name,
        "sha256": sha256(dp),
        "bytes": dp.stat().st_size,
        "source_url": r.url,
        "format": "SDMX-" + fmt.upper(),
        "role": "native",
    })
    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_SDMX_BOUNDED_NATIVE_RESPONSE",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Only the explicitly declared bounded SDMX query is acquired. "
            "The adapter does not infer or enumerate unrestricted datasets."
        ),
    }


def sparql_json(spec: dict, work: Path) -> dict:
    """Acquire a bounded SPARQL SELECT/ASK result as standard SPARQL JSON."""
    pms = spec["parameters"]
    endpoint = str(pms["endpoint"])
    query = str(pms["query"]).strip()
    if not query:
        raise RuntimeError("sparql_json requires a query")
    forbidden = re.compile(r"\b(INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|MOVE|COPY|ADD|WITH)\b", re.I)
    if forbidden.search(query):
        raise RuntimeError("SPARQL update operation is forbidden")
    upper = query.lstrip().upper()
    if not (upper.startswith("SELECT") or upper.startswith("ASK") or upper.startswith("PREFIX") or upper.startswith("BASE")):
        raise RuntimeError("sparql_json supports read-only SELECT/ASK queries only")

    s = session()
    method = str(pms.get("method", "POST")).upper()
    headers = {"Accept": "application/sparql-results+json"}
    if method == "GET":
        r = s.get(endpoint, params={"query": query}, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    elif method == "POST":
        r = s.post(
            endpoint,
            data={"query": query},
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
    else:
        raise RuntimeError("sparql_json method must be GET or POST")
    r.raise_for_status()
    obj = r.json()
    if not isinstance(obj, dict):
        raise RuntimeError("SPARQL response is not a JSON object")
    if "boolean" not in obj:
        bindings = ((obj.get("results") or {}).get("bindings"))
        if not isinstance(bindings, list):
            raise RuntimeError("SPARQL JSON has neither boolean nor results.bindings")
        max_rows = int(pms.get("max_rows", 100000))
        if len(bindings) > max_rows:
            raise RuntimeError(
                f"SPARQL result {len(bindings)} exceeds declared max_rows {max_rows}"
            )

    p = work / "payload" / "sparql-results.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return {
        "acquired_at": now(),
        "assets": [{
            "path": str(p.relative_to(work)),
            "name": p.name,
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
            "source_url": r.url,
            "format": "SPARQL-Results/JSON",
            "role": "native",
        }],
        "validation_result": "PASS_SPARQL_JSON_BOUNDED",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Read-only SELECT/ASK result preservation only. "
            "Query design and semantic joining remain product-specific."
        ),
    }


def html_table(spec: dict, work: Path) -> dict:
    """Preserve public HTML table pages and deterministically extract declared tables."""
    pms = spec["parameters"]
    urls = pms.get("urls")
    if urls is None:
        urls = [pms.get("url") or spec["source"]["landing_url"]]
    urls = [str(x) for x in urls if x]
    if not urls:
        raise RuntimeError("html_table requires at least one URL")

    s = session(system_ca=bool(pms.get("system_ca", False)))
    assets = []
    extracted = []
    required_headers = [
        str(x).strip().casefold()
        for x in (pms.get("required_headers") or [])
    ]
    min_rows = int(pms.get("min_rows", 1))
    chosen_index = pms.get("table_index")

    for page_no, url in enumerate(urls, 1):
        r = s.get(url, timeout=180, allow_redirects=True)
        r.raise_for_status()
        raw = r.content
        text = raw.decode(r.encoding or "utf-8", errors="replace")
        parser = _TableCollector()
        parser.feed(text)
        if not parser.tables:
            raise RuntimeError(f"HTML page exposed no table: {url}")

        hp = work / "payload" / f"html-table-page-{page_no:03d}.html"
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_bytes(raw)
        assets.append({
            "path": str(hp.relative_to(work)),
            "name": hp.name,
            "sha256": sha256(hp),
            "bytes": hp.stat().st_size,
            "source_url": r.url,
            "format": "HTML",
            "role": "native",
        })

        candidates = parser.tables
        if chosen_index is not None:
            idx = int(chosen_index)
            if idx < 0 or idx >= len(candidates):
                raise RuntimeError(
                    f"Declared table_index {idx} outside {len(candidates)} tables"
                )
            candidates = [candidates[idx]]

        matched = []
        for table in candidates:
            header_cells = table[0] if table else []
            headers = [cell.get("text", "") for cell in header_cells]
            folded = [x.strip().casefold() for x in headers]
            if required_headers and not all(
                any(req in header for header in folded)
                for req in required_headers
            ):
                continue
            body_rows = table[1:] if any(
                cell.get("kind") == "th" for cell in header_cells
            ) else table
            if len(body_rows) < min_rows:
                continue
            matched.append({
                "source_url": r.url,
                "headers": headers,
                "rows": [
                    [cell.get("text", "") for cell in row]
                    for row in body_rows
                ],
            })

        if not matched:
            raise RuntimeError(
                f"No HTML table matched declared header/row rules: {url}"
            )
        extracted.extend(matched)

    jp = work / "recomposed" / "tables.json"
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "table_count": len(extracted),
                "tables": extracted,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    derived = [{
        "path": str(jp.relative_to(work)),
        "name": jp.name,
        "sha256": sha256(jp),
        "bytes": jp.stat().st_size,
        "source_url": None,
        "format": "JSON",
        "role": "recomposed",
    }]
    return {
        "acquired_at": now(),
        "assets": [*assets, *derived],
        "validation_result": "PASS_HTML_TABLE_EXTRACTED",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Raw HTML is the native source object. Extracted tables are deterministic derived "
            "representations and do not replace the producer page or imply reuse clearance."
        ),
    }


class _InlineScriptCollector(HTMLParser):
    """Collect inline script bodies without executing producer JavaScript."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self._capture = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attr = {str(k).lower(): str(v or "") for k, v in attrs}
        self._capture = not bool(attr.get("src"))
        if self._capture:
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self._capture = False

    def handle_data(self, data):
        if self._capture and self.scripts:
            self.scripts[-1] += data


def _js_call_argument(script: str, function_name: str):
    """Return the single call argument for a bounded Easychart method.

    This is a lexical scanner, not a JavaScript evaluator. Parentheses inside
    quoted strings are ignored and nested function-call parentheses are
    balanced before the outer call is closed.
    """
    match = re.search(
        rf"\b{re.escape(function_name)}\s*\(",
        script,
    )
    if not match:
        return None

    start = match.end()
    depth = 1
    quote = None
    escaped = False
    for pos in range(start, len(script)):
        ch = script[pos]
        if quote is not None:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == quote:
                quote = None
            continue

        if ch in {"'", '"'}:
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return script[start:pos].strip()

    raise RuntimeError(
        f"Unterminated Easychart call argument for {function_name}"
    )


def _js_string_literal(value: str, label: str) -> str:
    """Decode a quoted JavaScript string using Python's safe literal parser."""
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError) as exc:
        raise RuntimeError(
            f"Easychart {label} is not a supported quoted string literal"
        ) from exc
    if not isinstance(parsed, str):
        raise RuntimeError(f"Easychart {label} is not a string")
    return parsed


def _json_value(value: str, label: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Easychart {label} is not strict JSON"
        ) from exc


def _easychart_csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return value


def easychart_html(spec: dict, work: Path) -> dict:
    """Preserve HTML and extract explicitly embedded Drupal Easychart payloads.

    The adapter supports the producer-rendered pattern used by Drupal Easychart:
    a chart container, setConfigStringified()/setConfig(), and setData(). It
    intentionally does not execute JavaScript or infer undisclosed endpoints.
    """
    pms = spec["parameters"]
    url = str(pms.get("url") or spec["source"]["landing_url"])
    min_charts = max(1, int(pms.get("min_charts", 1)))
    max_charts = max(min_charts, int(pms.get("max_charts", 100)))
    require_inline_data = bool(pms.get("require_inline_data", True))
    emit_csv = bool(pms.get("emit_csv", True))

    s = session(system_ca=bool(pms.get("system_ca", False)))
    r = s.get(url, timeout=180, allow_redirects=True)
    r.raise_for_status()
    raw = r.content
    text = raw.decode(r.encoding or "utf-8", errors="replace")
    if "<html" not in text.lower() and "<script" not in text.lower():
        raise RuntimeError("Easychart source did not return recognizable HTML")

    hp = work / "payload" / "easychart-page.html"
    hp.parent.mkdir(parents=True, exist_ok=True)
    hp.write_bytes(raw)
    assets = [{
        "path": str(hp.relative_to(work)),
        "name": hp.name,
        "sha256": sha256(hp),
        "bytes": hp.stat().st_size,
        "source_url": r.url,
        "format": "HTML",
        "role": "native",
    }]

    parser = _InlineScriptCollector()
    parser.feed(text)
    chart_id_re = re.compile(
        r"""getElementById\s*\(\s*(['"])(easychart-chart-[^'"]+)\1\s*\)""",
        re.I,
    )

    charts = []
    seen_ids = set()
    for script_no, script in enumerate(parser.scripts, 1):
        chart_ids = []
        for match in chart_id_re.finditer(script):
            chart_id = match.group(2)
            if chart_id not in chart_ids:
                chart_ids.append(chart_id)
        if not chart_ids:
            continue
        if len(chart_ids) != 1:
            raise RuntimeError(
                f"Easychart inline script {script_no} references multiple chart containers"
            )
        chart_id = chart_ids[0]
        if chart_id in seen_ids:
            raise RuntimeError(f"Duplicate Easychart container {chart_id}")
        seen_ids.add(chart_id)

        config = None
        config_arg = _js_call_argument(script, "setConfigStringified")
        if config_arg is not None:
            config_text = _js_string_literal(config_arg, "config")
            config = _json_value(config_text, "config")
        else:
            config_arg = _js_call_argument(script, "setConfig")
            if config_arg is not None:
                config = _json_value(config_arg, "config")

        data = None
        data_arg = _js_call_argument(script, "setData")
        if data_arg is not None:
            data = _json_value(data_arg, "data")

        data_url = None
        data_url_arg = _js_call_argument(script, "setDataUrl")
        if data_url_arg is not None:
            data_url = _js_string_literal(data_url_arg, "data URL")

        if config is None:
            raise RuntimeError(f"Easychart {chart_id} has no supported embedded config")
        if require_inline_data and data is None:
            raise RuntimeError(
                f"Easychart {chart_id} has no embedded setData payload"
            )

        charts.append({
            "sequence": len(charts) + 1,
            "container_id": chart_id,
            "config": config,
            "data": data,
            "data_url": data_url,
        })

    if len(charts) < min_charts:
        raise RuntimeError(
            f"Easychart page exposed {len(charts)} charts below declared minimum {min_charts}"
        )
    if len(charts) > max_charts:
        raise RuntimeError(
            f"Easychart page exposed {len(charts)} charts above declared maximum {max_charts}"
        )

    jp = work / "recomposed" / "easychart-charts.json"
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "source_url": r.url,
                "chart_count": len(charts),
                "charts": charts,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    assets.append({
        "path": str(jp.relative_to(work)),
        "name": jp.name,
        "sha256": sha256(jp),
        "bytes": jp.stat().st_size,
        "source_url": None,
        "format": "JSON",
        "role": "recomposed",
    })

    if emit_csv:
        for chart in charts:
            data = chart["data"]
            if not data or not isinstance(data, list):
                continue
            if not all(isinstance(row, list) for row in data):
                continue
            name = re.sub(
                r"[^A-Za-z0-9._-]+",
                "_",
                chart["container_id"],
            )
            cp = work / "recomposed" / f"{name}.csv"
            with cp.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, lineterminator="\n")
                for row in data:
                    writer.writerow([_easychart_csv_cell(v) for v in row])
            assets.append({
                "path": str(cp.relative_to(work)),
                "name": cp.name,
                "sha256": sha256(cp),
                "bytes": cp.stat().st_size,
                "source_url": None,
                "format": "CSV",
                "role": "recomposed",
            })

    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_EASYCHART_HTML_EXTRACTED",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Raw producer HTML is the native source object. Embedded Easychart "
            "configuration/data are extracted lexically without JavaScript execution; "
            "derived JSON/CSV mirror the chart payload and do not assert that it is the "
            "producer's upstream canonical table or that redistribution is cleared."
        ),
    }


def rest_xml(spec: dict, work: Path) -> dict:
    """Acquire one or more bounded public XML endpoints such as DATEX II or NeTEx."""
    pms = spec["parameters"]
    declared = pms.get("requests")
    if declared is None:
        declared = [{
            "key": pms.get("key", "response"),
            "url": pms["url"],
            "query": pms.get("query", {}),
            "expected_root": pms.get("expected_root"),
            "namespace_contains": pms.get("namespace_contains"),
            "min_bytes": pms.get("min_bytes", 1),
        }]
    if not isinstance(declared, list) or not declared:
        raise RuntimeError("rest_xml requires at least one declared request")

    s = session(system_ca=bool(pms.get("system_ca", False)))
    assets = []
    for i, item in enumerate(declared, 1):
        url = str(item["url"])
        key = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            str(item.get("key") or f"response-{i}"),
        )
        headers = {}
        if item.get("accept"):
            headers["Accept"] = str(item["accept"])
        r = s.get(
            url,
            params=item.get("query") or {},
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        r.raise_for_status()
        raw = r.content
        if len(raw) < int(item.get("min_bytes", 1)):
            raise RuntimeError(f"XML response {key} below declared minimum size")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            raise RuntimeError(f"XML response {key} is not well formed") from e

        local = root.tag.split("}")[-1]
        expected_root = item.get("expected_root")
        if expected_root and local.casefold() != str(expected_root).casefold():
            raise RuntimeError(
                f"XML response {key} root {local!r} != {expected_root!r}"
            )
        namespace_contains = item.get("namespace_contains")
        if namespace_contains and str(namespace_contains) not in str(root.tag):
            raise RuntimeError(
                f"XML response {key} root namespace does not contain "
                f"{namespace_contains!r}"
            )

        p = work / "payload" / f"{key}.xml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        assets.append({
            "path": str(p.relative_to(work)),
            "name": p.name,
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
            "source_url": r.url,
            "format": "XML",
            "role": "native",
        })

    return {
        "acquired_at": now(),
        "assets": assets,
        "validation_result": "PASS_BOUNDED_REST_XML",
        "source_period_or_edition": pms.get("period"),
        "limitations": (
            "Only explicitly declared bounded XML requests are acquired. "
            "Schema/profile validation remains product-specific; the adapter preserves well-formed native XML."
        ),
    }


ADAPTERS = {
    "eurostat": eurostat,
    "ine_json": ine_partitioned_acquire,
    "static_http": static_http,
    "gtfs_static": gtfs_static,
    "ckan_gtfs": ckan_gtfs,
    "ige_table": ige_table,
    "opendatasoft": opendatasoft,
    "html_assets": html_assets,
    "arcgis_feature_service": arcgis_feature_service,
    "rest_json": rest_json,
    "ckan_resource": ckan_resource,
    "ogc_api_features": ogc_api_features,
    "atom_feed": atom_feed,
    "bpstat_jsonstat": bpstat_jsonstat,
    "wfs": wfs,
    "sdmx_rest": sdmx_rest,
    "sparql_json": sparql_json,
    "html_table": html_table,
    "easychart_html": easychart_html,
    "rest_xml": rest_xml,
}


def acquire(spec: dict, work: Path) -> dict:
    fn = ADAPTERS.get(spec["adapter"])
    if fn is None:
        raise ValueError(f"Unsupported adapter {spec['adapter']}")
    return fn(spec, work)
