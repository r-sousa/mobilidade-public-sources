#!/usr/bin/env python3
"""Bounded technology/distribution probe for one declared public HTML page."""
from __future__ import annotations
import argparse, hashlib, json, re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qsl
import requests

MARKERS = {
    "drupal": ["drupalsettings", "/core/", "/sites/default/files/"],
    "highcharts": ["highcharts", "highcharts.chart", "highcharts.chart(", "highcharts.stockchart"],
    "chartjs": ["chart.js", "chart.min.js", "new chart("],
    "plotly": ["plotly"],
    "flourish": ["flourish"],
    "datawrapper": ["datawrapper", "dwcdn.net"],
    "powerbi": ["app.powerbi.com", "powerbi"],
    "tableau": ["tableau"],
    "echarts": ["echarts"],
    "amcharts": ["amcharts"],
}
URL_RE = re.compile(r"https?://[^\\s\\\"'<>\\\\]+", re.I)
REL_ENDPOINT_RE = re.compile(
    r"""(?P<q>["'])(?P<u>/[^"'<>]{1,500}(?:api|ajax|json|csv|data|chart|graph|dataset|download)[^"'<>]{0,500})(?P=q)""",
    re.I,
)
DATA_EXT_RE = re.compile(r"\\.(?:csv|tsv|json|geojson|xlsx?|ods|zip|xml|gml|gpkg|avro)(?:$|[?#])", re.I)

def safe_url(url):
    try:
        p=urlsplit(url)
        if not p.scheme:
            return url
        keys=sorted({k for k,_ in parse_qsl(p.query,keep_blank_values=True)})
        q="&".join(f"{k}=<value>" for k in keys)
        return p._replace(query=q,fragment="").geturl()
    except Exception:
        return url

def uniq(xs):
    out=[]; seen=set()
    for x in xs:
        x=safe_url(x)
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

class P(HTMLParser):
    def __init__(self,base):
        super().__init__(convert_charrefs=True)
        self.base=base; self.meta=[]; self.scripts=[]; self.iframes=[]; self.links=[]; self.forms=[]
        self.inline=[]; self._in_script=False; self.data_attrs=[]
    def handle_starttag(self,tag,attrs):
        a={str(k).lower():str(v or "") for k,v in attrs}
        if tag=="meta":
            self.meta.append(a)
        elif tag=="script":
            if a.get("src"):
                self.scripts.append(urljoin(self.base,a["src"]))
            else:
                self._in_script=True; self.inline.append("")
        elif tag=="iframe" and a.get("src"):
            self.iframes.append(urljoin(self.base,a["src"]))
        elif tag in {"a","link"} and a.get("href"):
            self.links.append(urljoin(self.base,a["href"]))
        elif tag=="form" and a.get("action"):
            self.forms.append(urljoin(self.base,a["action"]))
        for k,v in a.items():
            if k.startswith("data-") and v:
                self.data_attrs.append({"attribute":k,"value":v[:500]})
    def handle_endtag(self,tag):
        if tag=="script":
            self._in_script=False
    def handle_data(self,data):
        if self._in_script and self.inline:
            self.inline[-1]+=data

def highcharts_context(block, limit=30):
    lower=block.casefold()
    out=[]
    pos=0
    while True:
        i=lower.find("highcharts",pos)
        if i<0 or len(out)>=limit:
            break
        start=max(0,i-600); end=min(len(block),i+1800)
        excerpt=" ".join(block[start:end].split())
        out.append(excerpt[:2400])
        pos=i+10
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("url"); args=ap.parse_args()
    s=requests.Session()
    s.headers.update({
        "User-Agent":"Mozilla/5.0 (compatible; MobilidadeNorte-PublicWebTechnologyProbe/1.1)",
        "Accept":"text/html,application/xhtml+xml",
    })
    r=s.get(args.url,timeout=90,allow_redirects=True); r.raise_for_status()
    raw=r.content; text=raw.decode(r.encoding or "utf-8",errors="replace")
    p=P(r.url); p.feed(text)
    low=text.casefold()

    generators=[]
    for m in p.meta:
        key=(m.get("name") or m.get("property") or "").casefold()
        if "generator" in key:
            generators.append(m.get("content",""))

    tech={k:{"detected":any(m in low for m in markers),
             "markers":[m for m in markers if m in low]} for k,markers in MARKERS.items()}

    all_urls=uniq(p.links+p.scripts+p.iframes+URL_RE.findall(text))
    relative_hints=[urljoin(r.url,m.group("u")) for m in REL_ENDPOINT_RE.finditer(text)]
    highcharts_inline=[]
    for i,b in enumerate(p.inline):
        ctx=highcharts_context(b)
        if ctx:
            highcharts_inline.append({
                "index":i,
                "bytes":len(b.encode("utf-8")),
                "contexts":ctx,
                "absolute_urls":uniq(URL_RE.findall(b))[:100],
                "relative_endpoint_hints":uniq([urljoin(r.url,m.group("u")) for m in REL_ENDPOINT_RE.finditer(b)])[:100],
            })

    highcharts_scripts=[u for u in uniq(p.scripts) if "highchart" in u.casefold()]
    data_assets=[u for u in all_urls if DATA_EXT_RE.search(u)]

    headers={k:v for k,v in r.headers.items() if k.casefold() in {
        "server","content-type","content-language","x-powered-by","x-generator",
        "x-drupal-cache","x-drupal-dynamic-cache","cache-control","etag","last-modified"}}

    out={
        "probe_version":2,
        "requested_url":args.url,
        "final_url":r.url,
        "status":r.status_code,
        "sha256":hashlib.sha256(raw).hexdigest(),
        "bytes":len(raw),
        "headers":headers,
        "meta_generator":generators,
        "technology_fingerprints":tech,
        "highcharts_script_src":highcharts_scripts,
        "script_src":uniq(p.scripts)[:250],
        "iframe_src":uniq(p.iframes)[:100],
        "form_actions":uniq(p.forms)[:100],
        "data_attributes":p.data_attrs[:300],
        "data_asset_candidates":data_assets[:300],
        "relative_endpoint_hints":uniq(relative_hints)[:300],
        "highcharts_inline_evidence":highcharts_inline[:100],
        "limitations":[
            "Static HTML response only; JavaScript is not executed.",
            "Query values are redacted from recorded absolute URLs.",
            "Discovery only; no source acceptance, rights promotion, or publication decision."
        ],
    }
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
