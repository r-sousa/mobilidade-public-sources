from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import zipfile
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
            ["pdf", "xls", "xlsx", "csv", "zip", "json", "geojson"]
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
        if "spreadsheet" in ctype.lower() and head.startswith(b"PK"):
            validate_xlsx(p)
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
}


def acquire(spec: dict, work: Path) -> dict:
    fn = ADAPTERS.get(spec["adapter"])
    if fn is None:
        raise ValueError(f"Unsupported adapter {spec['adapter']}")
    return fn(spec, work)
