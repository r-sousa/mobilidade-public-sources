#!/usr/bin/env python3
"""POCTEP 2021-27 public operations: reproducible ingestion and conservative QA.
No Fxx identity is allocated; this is an external evidence register, not MN acceptance.
Uses Python stdlib to read source XLSX files. Does not fabricate missing values.
"""
import csv, hashlib, html, io, json, os, re, sys, time, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile

BASE = "https://www.poctep.eu/en/operations-partners-list/"
FALLBACKS = ["https://www.poctep.eu/proyectos-aprobados-poctep2127/",
             "https://www.poctep.eu/pt/lista-de-operacoes/"]
OUT = Path("external/poctep/data")
RAW = OUT / "source"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; POCTEP-public-inventory/1.0)",
           "Accept": "text/html,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"}
LABELS = ("calls_1_5", "call_6", "call_7", "call_8")
NAMESPACES = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
              "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
PROJECT_CODE = re.compile(r"(?<!\w)\d{3,5}_[A-Z0-9][A-Z0-9_-]{2,70}_[1-8]_[A-Z](?!\w)", re.I)

def normalize(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()

def fetch(url):
    err = None
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=45) as response:
                data = response.read(30_000_001)
                if len(data) > 30_000_000:
                    raise ValueError("Response exceeds 30MB safety cap")
                return data, response.geturl(), response.headers.get("Content-Type", "")
        except Exception as ex:
            err = ex
            print("fetch_retry", attempt, url, repr(ex), flush=True)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Unable to retrieve {url}: {err}")

class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.current, self.text = [], None, []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = {"href": dict(attrs).get("href", ""), "text": ""}
    def handle_data(self, data):
        self.text.append(data)
        if self.current is not None:
            self.current["text"] += data
    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append(self.current)
            self.current = None

def classify(label):
    t = normalize(label)
    if re.search(r"\b(?:1|1a|1st)\b.*\b(?:5|5a|5th)\b", t) or ("144" in t and "operaci" in t):
        return "calls_1_5"
    if re.search(r"\b(?:6|6a|6th)\b", t) and ("convoc" in t or "call" in t or "94" in t):
        return "call_6"
    if re.search(r"\b(?:7|7a|7th)\b", t) and ("convoc" in t or "call" in t or "6 oper" in t):
        return "call_7"
    if re.search(r"\b(?:8|8a|8th)\b", t) and ("convoc" in t or "call" in t):
        return "call_8"
    return None

def discover():
    diagnostics = []
    for page in [BASE] + FALLBACKS:
        try:
            data, actual, ctype = fetch(page)
            p = LinkCollector()
            p.feed(data.decode("utf-8", errors="replace"))
            candidates = []
            for a in p.links:
                target = urljoin(actual, html.unescape(a["href"]))
                label = html.unescape(a["text"]).strip()
                if "poctep.eu" not in urlparse(target).netloc.lower():
                    continue
                if not any(token in target.lower() for token in (".xlsx", ".xls", ".csv", "wp-content/uploads", "/download")):
                    continue
                candidates.append({"label": label, "url": target, "call": classify(label)})
            diagnostics.append({"page": page, "http_content_type": ctype,
                                "bytes": len(data), "candidate_links": candidates})
            selected = {item["call"]: item for item in candidates if item["call"]}
            if len(selected) == 4:
                return selected, diagnostics
            # Backup: if four spreadsheet links occur in exactly the expected call order,
            # keep their URLs only for a provenance diagnostic, not as approved matches.
        except Exception as ex:
            diagnostics.append({"page": page, "error": repr(ex)})
    return {}, diagnostics

def xlsx_sheets(blob):
    # Read the OOXML structure directly: no external spreadsheet dependencies.
    with ZipFile(io.BytesIO(blob)) as z:
        ns = NAMESPACES
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        mapping = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("x:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//x:t", ns)))
        output = []
        for s in workbook.findall("x:sheets/x:sheet", ns):
            title = s.attrib.get("name", "Sheet")
            rid = s.attrib.get("{"+ns["r"]+"}id")
            target = mapping.get(rid, "")
            path = target.lstrip("/") if target.startswith("/") else "xl/" + target.lstrip("/")
            path = re.sub(r"(^|/)xl/xl/", "xl/", path)
            if path not in z.namelist():
                path = "xl/" + target.split("/")[-1] if "/" not in target else "xl/worksheets/" + target.split("/")[-1]
            root = ET.fromstring(z.read(path))
            matrix = []
            for row in root.findall(".//x:sheetData/x:row", ns):
                vals = {}
                for c in row.findall("x:c", ns):
                    ref = c.attrib.get("r", "A1")
                    letters = re.match(r"[A-Z]+", ref)
                    if not letters: continue
                    pos = 0
                    for ch in letters.group(): pos = pos * 26 + ord(ch) - 64
                    typ = c.attrib.get("t", "")
                    if typ == "inlineStr":
                        value = "".join(n.text or "" for n in c.findall(".//x:is//x:t", ns))
                    else:
                        node = c.find("x:v", ns)
                        value = node.text if node is not None and node.text is not None else ""
                        if typ == "s" and value != "":
                            value = shared[int(value)]
                    vals[pos - 1] = value
                if not vals: continue
                matrix.append([vals.get(i, "") for i in range(max(vals) + 1)])
            output.append((title, matrix))
        return output

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

def key_candidates(row):
    return [m.group(0).upper() for value in row for m in PROJECT_CODE.finditer(str(value))]

def guess_headers(matrix):
    tokens = ("proyect", "opera", "codigo", "codig", "acr", "sigla", "beneficia",
              "entidad", "presup", "feder", "prioridad", "area", "territ", "objetiv",
              "project", "nome", "nombre", "custo", "coste", "fundo")
    scored = [(sum(any(t in normalize(x) for t in tokens) for x in row), i)
              for i, row in enumerate(matrix[:30])]
    if not scored: return -1
    score, idx = max(scored)
    return idx if score >= 2 else -1

def field(row, headers, terms):
    for i, h in enumerate(headers):
        n = normalize(h)
        if any(x in n for x in terms) and i < len(row) and str(row[i]).strip():
            return str(row[i]).strip()
    return ""

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    selected, attempts = discover()
    discovery = {"source_page": BASE, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                 "pages_attempted": attempts, "selected": selected}
    (OUT / "discovery.json").write_text(json.dumps(discovery, indent=2, ensure_ascii=False), encoding="utf-8")
    if len(selected) != 4:
        print("ERROR source discovery found", len(selected), "of four call lists")
        for x in attempts:
            print(json.dumps(x, ensure_ascii=False)[:6000])
        sys.exit(2)
    sheets_meta, all_record_rows = [], []
    observed_codes = defaultdict(lambda: {"calls": set(), "rows": 0, "names": set(),
                                          "thematics": set(), "territories": set(),
                                          "budget_values": set(), "feder_values": set()})
    for call in LABELS:
        entry = selected[call]
        payload, actual, ctype = fetch(entry["url"])
        is_xlsx = payload[:4] == b"PK\x03\x04"
        if not is_xlsx:
            raise ValueError(f"{call}: linked download is not an XLSX zip: {actual}, {ctype}, {payload[:100]!r}")
        digest = hashlib.sha256(payload).hexdigest()
        tables = xlsx_sheets(payload)
        for k, (sheet_name, matrix) in enumerate(tables):
            if not matrix: continue
            suffix = f"{call}_sheet{k+1}.csv"
            write_csv(RAW / suffix, matrix)
            header_idx = guess_headers(matrix)
            headers = matrix[header_idx] if header_idx >= 0 else []
            sheet_codes = set()
            for idx, r in enumerate(matrix):
                codes = key_candidates(r)
                for code in codes:
                    sheet_codes.add(code)
                    ent = observed_codes[code]
                    ent["calls"].add(call)
                    ent["rows"] += 1
                    ent["names"].add(field(r, headers, ("nombre del proyecto", "nombre de la oper",
                                   "nome do projeto", "acronimo", "acronym", "titulo", "title")))
                    ent["thematics"].add(field(r, headers, ("prioridad", "prioridade", "objetivo espec", "objetivo espec")))
                    ent["territories"].add(field(r, headers, ("area de cooper", "area de coop", "ambito territor", "territorio")))
                    ent["budget_values"].add(field(r, headers, ("coste total", "custo total", "presupuesto total", "inversion total")))
                    ent["feder_values"].add(field(r, headers, ("ayuda feder", "ajuda feder", "feder aproba")))
                if idx > header_idx >= 0:
                    all_record_rows.append([call, sheet_name, idx + 1, *r])
            sheets_meta.append({"call": call, "sheet": sheet_name, "rows": len(matrix),
                                "max_cols": max(map(len, matrix)), "header_idx_0based": header_idx,
                                "header": headers, "unique_codes_regex": len(sheet_codes),
                                "sha256_source": digest, "download_url": actual,
                                "raw_csv": suffix})
        entry.update({"download_url": actual, "sha256": digest, "bytes": len(payload),
                      "sheet_count": len(tables)})
        print(call, len(tables), len(payload), "bytes", flush=True)
    cols = ["project_code", "call_group", "project_name_candidate",
            "priority_or_objective_candidate", "territory_candidate",
            "total_budget_candidate", "erdf_candidate", "source_rows"]
    output = [cols]
    for code, ent in sorted(observed_codes.items()):
        value = lambda k: " | ".join(sorted(x for x in ent[k] if x))
        output.append([code, " | ".join(sorted(ent["calls"])), value("names"),
                       value("thematics"), value("territories"),
                       value("budget_values"), value("feder_values"), ent["rows"]])
    write_csv(OUT / "projects_candidates.csv", output)
    write_csv(OUT / "all_source_rows.csv", [["call_group", "sheet", "source_row_index", "source_cells..."]] + all_record_rows)
    counts = Counter()
    for x in observed_codes.values():
        for c in x["calls"]: counts[c] += 1
    quality = {"as_of_utc": datetime.now(timezone.utc).isoformat(),
               "source_latest_page_date": "2026-04-16",
               "official_project_total_2026_11": 259,
               "expected_by_call": {"calls_1_5": 144, "call_6": 94, "call_7": 6, "call_8": 15},
               "unique_codes_detected_regex": len(observed_codes),
               "regex_counts_by_call": dict(counts),
               "sheet_manifest": sheets_meta,
               "project_register_status": "candidate_only_not_verified",
               "note": "Regex-based extraction is preliminary; source workbook may use different project IDs. Financial figures are unparsed strings and must not be aggregated or treated as approved totals."}
    quality["expected_total_match"] = len(observed_codes) == 259
    (OUT / "quality.json").write_text(json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "discovery.json").write_text(json.dumps(discovery, indent=2, ensure_ascii=False), encoding="utf-8")
    print("SOURCE_QA", json.dumps({"unique": len(observed_codes), "by_call": dict(counts),
                                  "sheets": len(sheets_meta)}), flush=True)
    if not all_record_rows: sys.exit(3)

if __name__ == "__main__":
    main()
