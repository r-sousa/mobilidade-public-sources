#!/usr/bin/env python3
"""Bounded technology probe for one declared public HTML page."""
from __future__ import annotations
import argparse, hashlib, json, re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qsl
import requests

TECH = {
    "drupal": [r"drupalSettings", r"/core/(?:assets|misc|modules)/", r"/sites/default/files/", r"Drupal\\."],
    "highcharts": [r"highcharts"],
    "chartjs": [r"chart(?:\\.min)?\\.js", r"new\\s+Chart\\s*\\("],
    "plotly": [r"plotly"],
    "flourish": [r"flourish(?:-embed|\\.studio|\\.live)"],
    "datawrapper": [r"datawrapper", r"dwcdn\\.net"],
    "powerbi": [r"app\\.powerbi\\.com", r"powerbi"],
    "tableau": [r"tableau"],
    "echarts": [r"echarts"],
    "amcharts": [r"amcharts"],
    "d3": [r"d3(?:\\.min)?\\.js", r"d3js\\.org"],
    "google_charts": [r"google\\.charts", r"www\\.gstatic\\.com/charts"],
    "vega": [r"vega(?:-lite)?"],
}
DATA_EXT = re.compile(r"\\.(?:csv|tsv|json|geojson|xlsx?|ods|zip|xml|gml|gpkg|avro)(?:$|[?#])", re.I)
URL_RE = re.compile(r"https?://[^\\s\\\"'<>\\\\]+", re.I)

def safe_url(url):
    try:
        p=urlsplit(url)
        if not p.scheme: return url
        keys=sorted({k for k,_ in parse_qsl(p.query,keep_blank_values=True)})
        q="&".join(f"{k}=<value>" for k in keys)
        return p._replace(query=q,fragment="").geturl()
    except Exception:
        return url

def uniq(xs):
    out=[]; seen=set()
    for x in xs:
        x=safe_url(x)
        if x and x not in seen: seen.add(x); out.append(x)
    return out

class P(HTMLParser):
    def __init__(self,base):
        super().__init__(convert_charrefs=True); self.base=base
        self.meta=[]; self.scripts=[]; self.iframes=[]; self.links=[]; self.forms=[]
        self.inline=[]; self._in_script=False; self.data_attrs=[]
    def handle_starttag(self,tag,attrs):
        a={str(k).lower():str(v or "") for k,v in attrs}
        if tag=="meta": self.meta.append(a)
        elif tag=="script":
            if a.get("src"): self.scripts.append(urljoin(self.base,a["src"]))
            else: self._in_script=True; self.inline.append("")
        elif tag=="iframe" and a.get("src"): self.iframes.append(urljoin(self.base,a["src"]))
        elif tag in {"a","link"} and a.get("href"): self.links.append(urljoin(self.base,a["href"]))
        elif tag=="form" and a.get("action"): self.forms.append(urljoin(self.base,a["action"]))
        for k,v in a.items():
            if k.startswith("data-") and v: self.data_attrs.append({"attribute":k,"value":v[:500]})
    def handle_endtag(self,tag):
        if tag=="script": self._in_script=False
    def handle_data(self,data):
        if self._in_script and self.inline: self.inline[-1]+=data

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("url"); args=ap.parse_args()
    s=requests.Session(); s.headers["User-Agent"]="MobilidadeNorte-PublicWebTechnologyProbe/1.0"
    r=s.get(args.url,timeout=90,allow_redirects=True); r.raise_for_status()
    raw=r.content; text=raw.decode(r.encoding or "utf-8",errors="replace")
    p=P(r.url); p.feed(text)
    generators=[]
    for m in p.meta:
        key=(m.get("name") or m.get("property") or "").casefold()
        if "generator" in key: generators.append(m.get("content",""))
    tech={n:{"detected":any(re.search(x,text,re.I) for x in pats),
             "patterns":[x for x in pats if re.search(x,text,re.I)]} for n,pats in TECH.items()}
    urls=uniq(p.links+p.scripts+p.iframes+URL_RE.findall(text))
    inline=[]
    for i,b in enumerate(p.inline):
        marks=[n for n,pats in TECH.items() if any(re.search(x,b,re.I) for x in pats)]
        bu=uniq(URL_RE.findall(b))
        if marks or bu: inline.append({"index":i,"bytes":len(b.encode()),"technology_markers":marks,"urls":bu[:50]})
    headers={k:v for k,v in r.headers.items() if k.casefold() in {
        "server","content-type","content-language","x-powered-by","x-generator",
        "x-drupal-cache","x-drupal-dynamic-cache","cache-control","etag","last-modified"}}
    out={
      "probe_version":1,"requested_url":args.url,"final_url":r.url,"status":r.status_code,
      "sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"headers":headers,
      "meta_generator":generators,"technology_fingerprints":tech,
      "script_src":uniq(p.scripts)[:200],"iframe_src":uniq(p.iframes)[:100],
      "form_actions":uniq(p.forms)[:100],"data_attributes":p.data_attrs[:200],
      "data_asset_candidates":[u for u in urls if DATA_EXT.search(u)][:200],
      "inline_script_evidence":inline[:100],
      "limitations":["Static HTML only; JavaScript is not executed.","Query values are redacted.","Discovery only; no acceptance or reuse decision."]
    }
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
