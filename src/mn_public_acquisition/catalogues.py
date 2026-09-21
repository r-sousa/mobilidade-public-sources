from __future__ import annotations
import argparse
import hashlib
import json
import urllib.parse
from pathlib import Path

import requests
import yaml

UA = "MobilidadeNorte-CatalogueResolver/0.1"


def sess():
    s=requests.Session()
    s.headers.update({"User-Agent":UA})
    return s


def sha256_bytes(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()


def write(path:Path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def probe_udata(cfg:dict)->dict:
    s=sess()
    url=cfg["endpoint"].rstrip("/")+"/api/1/datasets/"
    params={"page_size":int(cfg.get("page_size",3))}
    if cfg.get("query"): params["q"]=cfg["query"]
    r=s.get(url,params=params,timeout=120); r.raise_for_status()
    obj=r.json()
    rows=obj.get("data") if isinstance(obj,dict) else None
    if not isinstance(rows,list) or not rows:
        raise RuntimeError("udata catalogue returned no datasets")
    sample=[]
    for d in rows[:3]:
        resources=d.get("resources") or []
        sample.append({
            "id":d.get("id"),
            "title":d.get("title"),
            "organization":(d.get("organization") or {}).get("name") if isinstance(d.get("organization"),dict) else d.get("organization"),
            "page":d.get("page"),
            "resource_urls":[x.get("url") for x in resources[:5] if isinstance(x,dict) and x.get("url")]
        })
    return {"status":"PASS","catalogue_role":"DISCOVERY_AND_DISTRIBUTION_RESOLVER","format":"udata-json","endpoint":r.url,"sample":sample}


def probe_datos_gob(cfg:dict)->dict:
    s=sess()
    url=cfg["endpoint"].rstrip("/")+"/apidata/catalog/dataset.json"
    params={"_pageSize":int(cfg.get("page_size",3)),"_page":0}
    r=s.get(url,params=params,timeout=120); r.raise_for_status()
    obj=r.json()
    if not isinstance(obj,(dict,list)):
        raise RuntimeError("datos.gob.es catalogue returned unexpected JSON")
    blob=json.dumps(obj,ensure_ascii=False)
    urls=sorted(set(x for x in __import__("re").findall(r'https?://[^"\\\s]+',blob) if "datos.gob.es" not in x))[:20]
    return {
        "status":"PASS",
        "catalogue_role":"DISCOVERY_AND_DISTRIBUTION_RESOLVER",
        "format":"datos-gob-semantic-json",
        "endpoint":r.url,
        "top_level_type":type(obj).__name__,
        "external_urls_sample":urls
    }


def probe_data_europa(cfg:dict)->dict:
    s=sess()
    endpoint=cfg["endpoint"].rstrip("/")
    q="""PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?dataset ?title ?publisher ?distribution ?accessURL ?downloadURL
WHERE {
  ?dataset a dcat:Dataset .
  OPTIONAL { ?dataset dct:title ?title . FILTER(lang(?title) = "" || langMatches(lang(?title), "en")) }
  OPTIONAL { ?dataset dct:publisher ?publisher . }
  OPTIONAL {
    ?dataset dcat:distribution ?distribution .
    OPTIONAL { ?distribution dcat:accessURL ?accessURL . }
    OPTIONAL { ?distribution dcat:downloadURL ?downloadURL . }
  }
} LIMIT 5"""
    r=s.get(endpoint,params={"query":q,"format":"application/sparql-results+json"},
            headers={"Accept":"application/sparql-results+json"},timeout=180)
    r.raise_for_status()
    obj=r.json()
    rows=((obj.get("results") or {}).get("bindings") or []) if isinstance(obj,dict) else []
    if not rows:
        raise RuntimeError("data.europa.eu SPARQL returned no DCAT datasets")
    sample=[]
    for row in rows:
        sample.append({k:v.get("value") for k,v in row.items() if isinstance(v,dict)})
    return {
        "status":"PASS",
        "catalogue_role":"DISCOVERY_AND_DISTRIBUTION_RESOLVER",
        "format":"DCAT-AP/SPARQL",
        "endpoint":endpoint,
        "sample":sample
    }


PROBES={"dados_gov_pt":probe_udata,"datos_gob_es":probe_datos_gob,"data_europa_eu":probe_data_europa}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("config",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    cfg=yaml.safe_load(a.config.read_text(encoding="utf-8"))
    result={"schema_version":"1.0.0","role":"CATALOGUE_RESOLVER_NOT_CANONICAL_SOURCE","catalogues":[]}
    for item in cfg["catalogues"]:
        provider=item["provider"]
        if provider not in PROBES:
            raise RuntimeError(f"unsupported catalogue provider {provider}")
        rec={"name":item["name"],"provider":provider,**PROBES[provider](item)}
        result["catalogues"].append(rec)
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    result["fingerprint"]=sha256_bytes(raw)
    write(a.out,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
