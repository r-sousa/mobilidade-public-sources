#!/usr/bin/env python3
"""MN-GEO-RAIL-001 W4: bounded *current* official RNGAP publication discovery.

This checks the actual DGT geodesy and digital product pages, the current
DGT visualization portal entry point, and the national data catalogue API.
Only public metadata (HTTP body max 1MB). It never queries full survey marks,
no WFS GetFeature, no historic insecure WMS and no DGT login. A catalog record
is never represented as geodetic observations or permission to infer heights.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen,Request
from html.parser import HTMLParser

PROBES={
 "dgt_rngap_authoritative":{
  "url":"https://www.dgterritorio.gov.pt/atividades/geodesia/infraestrutura-geodesica",
  "host":"www.dgterritorio.gov.pt","format":"html"},
 "dgt_official_digital_height_product":{
  "url":"https://www.dgterritorio.gov.pt/loja/geodesia",
  "host":"www.dgterritorio.gov.pt","format":"html"},
 "dgt_current_map_viewer":{
  "url":"https://geo2.dgterritorio.gov.pt/dgt",
  "host":"geo2.dgterritorio.gov.pt","format":"html"},
 "national_catalogue_API_RNGAP":{
  "url":"https://dados.gov.pt/api/1/datasets/rede-de-nivelamento-geometrico-de-alta-precisao-rngap/",
  "host":"dados.gov.pt","format":"json"}
}
MAX_BYTES=1_000_000
SAFE_RESOURCE_HOSTS={
 "www.dgterritorio.gov.pt","dgterritorio.gov.pt",
 "geo2.dgterritorio.gov.pt","snig.dgterritorio.gov.pt",
 "dados.gov.pt","www.dados.gov.pt"}
KNOWN_KEYWORDS=("rngap","nivelamento","cascais","altitudes","geodes","geodés",
                "digital","gratuito")

class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside=False
        self.title=[]
        self.hit_links=[]
        self.current=None
    def handle_starttag(self,t,a):
        d=dict(a)
        if t=="title":self.inside=True
        if t=="a":
            self.current={"href":d.get("href","")[:240],"text":""}
    def handle_data(self,data):
        if self.inside:self.title.append(data[:240])
        if self.current:self.current["text"]+=(data[:160])
    def handle_endtag(self,t):
        if t=="title":self.inside=False
        if t=="a" and self.current:
            if any(s in (self.current["href"]+" "+self.current["text"]).lower()
                   for s in KNOWN_KEYWORDS):
                self.hit_links.append(self.current)
            self.current=None

def _bounded(url,host,opener):
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname!=host or p.username or p.password:
        raise ValueError("unreviewed_source_origin")
    req=Request(url,headers={"Accept":"application/json,text/html;q=0.9",
                             "User-Agent":"MN-GEO-RAIL-001-W4-RNGAP-meta-only/1.0"})
    with opener(req,timeout=15) as r:
        f=urlsplit(r.geturl())
        if r.status!=200 or f.scheme!="https" or f.hostname not in SAFE_RESOURCE_HOSTS:
            raise ValueError("unapproved_redirect_or_HTTP_status")
        declared=r.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared)>MAX_BYTES:
            raise ValueError("source_metadata_exceeds_cap")
        h=hashlib.sha256();chunks=[];size=0
        while part:=r.read(65536):
            size+=len(part)
            if size>MAX_BYTES:raise ValueError("source_metadata_exceeds_cap")
            h.update(part);chunks.append(part)
    return b"".join(chunks),{"sha256":h.hexdigest(),"bytes":size,
                            "safe_final_host":f.hostname}

def extract_catalogue(data):
    doc=json.loads(data)
    if not isinstance(doc,dict):raise ValueError("unexpected_national_catalogue_type")
    resources=doc.get("resources") or []
    if not isinstance(resources,list):raise ValueError("unexpected_resources_type")
    sanitized=[]
    for x in resources[:35]:
        if not isinstance(x,dict):continue
        u=x.get("url")
        host=urlsplit(u).hostname if isinstance(u,str) else None
        sanitized.append({
            "title":str(x.get("title") or "")[:180],
            "format":str(x.get("format") or "")[:60],
            "resource_id":str(x.get("id") or "")[:90],
            "safe_url_host":host if host in SAFE_RESOURCE_HOSTS else None,
            "url_in_allowlisted_official_host":host in SAFE_RESOURCE_HOSTS,
            "raw_url_deliberately_not_persisted":True,
            "candidate_attribute_heights_verified":False})
    return {"metadata_dataset_title":str(doc.get("title") or "")[:240],
            "metadata_resource_count":len(resources),
            "potential_official_catalogue_resources":sanitized,
            "dataset_record_not_survey_observations":True}

def inspect(opener=urlopen):
    report={"mission":"MN-GEO-RAIL-001","worker":"W4",
            "stage":"current_DGT_rngap_public_metadata_official_source_discovery",
            "observed_utc":datetime.now(timezone.utc).isoformat(),
            "results":[],"official_height_products_are_free":None,
            "RNGAP_source_mark_coordinates_collected":0,
            "RNGAP_official_Cascais_altitudes_collected":0,
            "actual_source_feature_height_schema_validated":False,
            "DGT_account_secrets_used":False,
            "unverified_web_service_not_evidence_of_missing_marks":True,
            "PT_ES_crossborder_survey_benchmark_validation_complete":False,
            "canonical_Fxx_accepted":False,"Site_publication_authorized":False}
    for name,p in PROBES.items():
        rec={"name":name,"source_url":p["url"],"status":"unverified"}
        try:
            raw,meta=_bounded(p["url"],p["host"],opener)
            rec.update(meta)
            if p["format"]=="json":
                rec.update(extract_catalogue(raw))
                rec["format"]="national_open_data_metadata_JSON"
            else:
                html=raw.decode("utf-8",errors="replace")
                parser=TitleParser();parser.feed(html)
                rec["document_title"]="".join(parser.title)[:180]
                rec["RNGAP_term_in_page"]="rngap" in html.lower()
                rec["nivelamento_term_in_page"]="nivelamento" in html.lower()
                rec["altitudes_term_in_page"]="altitudes" in html.lower()
                rec["reference_links"]=parser.hit_links[:12]
                rec["format"]="HTML"
                if name=="dgt_official_digital_height_product":
                    rec["advertised_free_height_product"]=(
                        "altitudes de marcas de nivelamento" in html.lower() and
                        "gratuito" in html.lower())
                    report["official_height_products_are_free"]=rec["advertised_free_height_product"]
            rec["status"]="metadata_HTTP_200_integrity_sha_recorded"
        except Exception as e:
            rec["status"]="source_metadata_not_retrieved"
            rec["error_class"]=type(e).__name__
            # Avoid exposing page/body URLs from exception.
        report["results"].append(rec)
    report["metadata_sources_HTTP_200"]=sum(x["status"].startswith("metadata_HTTP")
                                           for x in report["results"])
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    out=inspect()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"metadata_sites_retrieved":out["metadata_sources_HTTP_200"],
                      "official_digital_heights_free_observed":out["official_height_products_are_free"],
                      "geodetic_mark_altitudes_acquired":0,
                      "sites":{r["name"]:r["status"] for r in out["results"]}}))

if __name__=="__main__":
    main()
