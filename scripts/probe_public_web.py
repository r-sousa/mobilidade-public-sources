#!/usr/bin/env python3
"""Bounded technology probe for one declared public HTML page."""
from __future__ import annotations
import argparse, hashlib, json, re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qsl
import requests

TECH_TOKENS = {
    "drupal": ["drupalsettings", "/core/", "/sites/default/files/", "drupal."],
    "highcharts": ["highcharts"],
    "chartjs": ["chart.min.js", "chart.js", "new chart("],
    "plotly": ["plotly"],
    "flourish": ["flourish-embed", "flourish.studio", "flourish.live"],
    "datawrapper": ["datawrapper", "dwcdn.net"],
    "powerbi": ["app.powerbi.com", "powerbi"],
    "tableau": ["tableau"],
    "echarts": ["echarts"],
    "amcharts": ["amcharts"],
    "d3": ["d3.min.js", "d3js.org"],
    "google_charts": ["google.charts", "gstatic.com/charts"],
    "vega": ["vega-lite", "vega.min.js"],
}
URL_RE = re.compile(r'https?://[^\s"\'<>\\]+', re.I)
DATA_EXT_RE = re.compile(r'\.(?:csv|tsv|json|geojson|xlsx?|ods|zip|xml|gml|gpkg|avro)(?:$|[?#])', re.I)

def safe_url(url):
    try:
        p = urlsplit(url)
        if not p.scheme:
            return url
        keys = sorted({k for k, _ in parse_qsl(p.query, keep_blank_values=True)})
        q = "&".join(f"{k}=<value>" for k in keys)
        return p._replace(query=q, fragment="").geturl()
    except Exception:
        return url

def uniq(values):
    out, seen = [], set()
    for value in values:
        value = safe_url(value)
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out

class ProbeParser(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.meta = []
        self.scripts = []
        self.iframes = []
        self.links = []
        self.forms = []
        self.inline = []
        self.in_script = False
        self.data_attrs = []

    def handle_starttag(self, tag, attrs):
        a = {str(k).lower(): str(v or "") for k, v in attrs}
        if tag == "meta":
            self.meta.append(a)
        elif tag == "script":
            if a.get("src"):
                self.scripts.append(urljoin(self.base, a["src"]))
            else:
                self.in_script = True
                self.inline.append("")
        elif tag == "iframe" and a.get("src"):
            self.iframes.append(urljoin(self.base, a["src"]))
        elif tag in {"a", "link"} and a.get("href"):
            self.links.append(urljoin(self.base, a["href"]))
        elif tag == "form" and a.get("action"):
            self.forms.append(urljoin(self.base, a["action"]))
        for k, v in a.items():
            if k.startswith("data-") and v:
                self.data_attrs.append({"attribute": k, "value": v[:500]})

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script and self.inline:
            self.inline[-1] += data

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    args = ap.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "MobilidadeNorte-PublicWebTechnologyProbe/1.1"
    response = session.get(args.url, timeout=90, allow_redirects=True)
    response.raise_for_status()
    raw = response.content
    text = raw.decode(response.encoding or "utf-8", errors="replace")
    lower = text.casefold()

    parser = ProbeParser(response.url)
    parser.feed(text)

    generators = []
    for meta in parser.meta:
        key = (meta.get("name") or meta.get("property") or "").casefold()
        if "generator" in key:
            generators.append(meta.get("content", ""))

    tech = {}
    for name, tokens in TECH_TOKENS.items():
        matches = [token for token in tokens if token in lower]
        tech[name] = {"detected": bool(matches), "tokens": matches}

    urls = uniq(parser.links + parser.scripts + parser.iframes + URL_RE.findall(text))
    inline = []
    for i, block in enumerate(parser.inline):
        block_lower = block.casefold()
        markers = [name for name, tokens in TECH_TOKENS.items() if any(t in block_lower for t in tokens)]
        found_urls = uniq(URL_RE.findall(block))
        if markers or found_urls:
            item = {
                "index": i,
                "bytes": len(block.encode("utf-8")),
                "technology_markers": markers,
                "urls": found_urls[:100],
            }
            if any(name in markers for name in {"drupal", "highcharts"}):
                item["content_sample"] = block[:12000]
            inline.append(item)

    selected_headers = {}
    allowed_headers = {
        "server", "content-type", "content-language", "x-powered-by", "x-generator",
        "x-drupal-cache", "x-drupal-dynamic-cache", "cache-control", "etag", "last-modified"
    }
    for key, value in response.headers.items():
        if key.casefold() in allowed_headers:
            selected_headers[key] = value

    out = {
        "probe_version": 2,
        "requested_url": args.url,
        "final_url": response.url,
        "status": response.status_code,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "headers": selected_headers,
        "meta_generator": generators,
        "technology_fingerprints": tech,
        "script_src": uniq(parser.scripts)[:300],
        "iframe_src": uniq(parser.iframes)[:100],
        "form_actions": uniq(parser.forms)[:100],
        "data_attributes": parser.data_attrs[:300],
        "data_asset_candidates": [u for u in urls if DATA_EXT_RE.search(u)][:300],
        "inline_script_evidence": inline[:200],
        "limitations": [
            "Static HTML only; JavaScript is not executed.",
            "Query values are redacted.",
            "Discovery only; no acceptance or reuse decision."
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
