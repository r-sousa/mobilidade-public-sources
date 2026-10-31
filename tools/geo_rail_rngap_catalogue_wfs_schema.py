#!/usr/bin/env python3
"""Discover exact DGT RNGAP official WFS via the Portuguese data.gov catalog.

Only official-host HTTPS, bounded OGC GetCapabilities and DescribeFeatureType;
NO GetFeature yet, so the result is NOT actual survey point data. A later
bounded GetFeature intake must verify true height fields and original datum.
"""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit
from urllib.request import Request,urlopen
from xml.etree import ElementTree as ET

CATALOGUE="https://dados.gov.pt/api/1/datasets/rede-de-nivelamento-geometrico-de-alta-precisao-rngap/"
HOST="geo2.dgterritorio.gov.pt"
MAX_BYTES=1_500_000
ALLOWED_NAMES=("rngap","nivelamento","altim")
PROBE_VERSIONS=("2.0.0","1.1.0")

def fetch(url,max_bytes=MAX_BYTES,opener=urlopen,allowed_hosts=("dados.gov.pt",HOST)):
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in allowed_hosts or p.username or p.password:
        raise ValueError("source_not_official_allowed_HTTPS")
    req=Request(url,headers={"Accept":"application/json,application/xml,text/xml;q=0.9",
                             "User-Agent":"MN-GEO-RAIL-001-DGT-RNGAP-verified-WFS-metadata/1.0"})
    chunks=[];total=0;digest=hashlib.sha256()
    with opener(req,timeout=18) as response:
        end=urlsplit(response.geturl())
        if response.status!=200 or end.scheme!="https" or end.hostname not in allowed_hosts:
            raise ValueError("unsafe_redirect_or_bad_WFS_status")
        while part:=response.read(65536):
            total+=len(part)
            if total>max_bytes:raise ValueError("bounded_WFS_response_limit_exceeded")
            chunks.append(part);digest.update(part)
    return b"".join(chunks),{"size_bytes":total,"sha256":digest.hexdigest()}

def resource_wfs_url(catalogue_bytes):
    d=json.loads(catalogue_bytes)
    if not isinstance(d,dict) or not isinstance(d.get("resources"),list):
        raise ValueError("unexpected_official_national_data_catalogue")
    candidates=[r for r in d["resources"] if isinstance(r,dict) and
                "wfs" in str(r.get("format","")).lower() and
                "rngap" in str(r.get("title","")).lower()]
    if len(candidates)!=1:raise ValueError("official_RNGAP_WFS_resource_not_unique")
    c=candidates[0];u=str(c.get("url") or "").strip()
    p=urlsplit(u)
    if p.scheme not in ("https","http") or p.hostname!=HOST or p.username or p.password:
        raise ValueError("official_catalogue_WFS_resource_origin_wrong")
    # Upgrade a historical HTTP link only to the SAME known official host and path,
    # document this change as a probe (not claim returned original HTTP was secure).
    if any(x in p.path.lower() for x in ("..","%2e","%2f")):
        raise ValueError("unsafe_feature_service_path")
    return urlunsplit(("https",HOST,p.path,"","")),{
        "official_catalogue_resource_ID":str(c.get("id")),
        "official_catalogue_resource_format":str(c.get("format")),
        "original_catalogue_resource_scheme":p.scheme,
        "HTTPS_probed_on_same_DGT_host_and_path":p.scheme=="http",
        "service_host":HOST,"service_path":p.path,
        "resource_title":str(c.get("title"))[:180]}

def query(base,service,request,version,typename=None):
    if service!="WFS" or request not in ("GetCapabilities","DescribeFeatureType"):
        raise ValueError("nonmetadata_WFS_request_forbidden")
    if version not in PROBE_VERSIONS:raise ValueError("unsupported_WFS_version")
    if request=="DescribeFeatureType" and (not typename or len(typename)>150):
        raise ValueError("invalid_selected_WFS_typename")
    args=[("service","WFS"),("request",request),("version",version)]
    if typename:args.append(("typeName" if version=="1.1.0" else "typeNames",typename))
    return base+"?"+urlencode(args)

def parse_capabilities(data):
    root=ET.fromstring(data)
    tag=root.tag.rsplit("}",1)[-1]
    if tag!="WFS_Capabilities":raise ValueError("not_WFS_Capabilities")
    rows=[]
    for feature in root.iter():
        if feature.tag.rsplit("}",1)[-1]!="FeatureType":continue
        name=next(((x.text or "").strip() for x in feature
                   if x.tag.rsplit("}",1)[-1]=="Name"),"")
        title=next(((x.text or "").strip() for x in feature
                    if x.tag.rsplit("}",1)[-1]=="Title"),"")
        if name:rows.append({"name":name[:150],"title":title[:200]})
    exact=[x for x in rows if any(k in (x["name"]+" "+x["title"]).lower()
                                   for k in ALLOWED_NAMES)]
    return {"total_layer_count":len(rows),"candidate_RNGAP_layers":exact[:30]}

def parse_xsd_schema(data):
    root=ET.fromstring(data)
    tag=root.tag.rsplit("}",1)[-1]
    if tag!="schema":raise ValueError("DescribeFeatureType_not_XSD_schema")
    names=[]
    for element in root.iter():
        if element.tag.rsplit("}",1)[-1]=="element" and element.attrib.get("name"):
            n=element.attrib["name"]
            if n not in names and len(n)<=120:names.append(n)
    height=[x for x in names if any(y in x.lower() for y in
            ("alt","cota","ort","nivel","height","z_"))]
    return {"declared_fields":names[:120],"possible_height_field_names":height[:40],
            "schema_has_verified_numeric_height_VALUES":False,
            "schema_does_not_establish_vertical_datum":True}

def run(opener=urlopen):
    report={"mission":"MN-GEO-RAIL-001","stage":"official_data_gov_pt_WFS_exact_resource_metadata_only",
            "utc":datetime.now(timezone.utc).isoformat(),
            "official_catalogue":CATALOGUE,"DGT_actual_survey_marks_retrieved":0,
            "official_PT_Cascais_heights_retrieved":0,
            "has_retrieved_verified_RNGAP_attributes":False,
            "Fxx_canonical_accepted":False,"crossborder_datum_validated":False,
            "probes":[]}
    try:
        raw,meta=fetch(CATALOGUE,opener=opener)
        base,identity=resource_wfs_url(raw)
        report["catalogue_source_sha256"]=meta["sha256"]
        report["candidate_source"]=identity
        for version in PROBE_VERSIONS:
            attempt={"WFS_version":version,"status":"unverified"}
            try:
                xml,receipt=fetch(query(base,"WFS","GetCapabilities",version),opener=opener)
                attempt.update(receipt)
                caps=parse_capabilities(xml)
                attempt.update(caps)
                if len(caps["candidate_RNGAP_layers"])!=1:
                    raise ValueError("RNGAP_layer_not_unique")
                typename=caps["candidate_RNGAP_layers"][0]["name"]
                xsd,xsd_receipt=fetch(query(base,"WFS","DescribeFeatureType",version,typename),
                                      opener=opener)
                attempt["schema_response_SHA256"]=xsd_receipt["sha256"]
                attempt["schema_response_bytes"]=xsd_receipt["size_bytes"]
                attempt["selected_layer"]=typename
                attempt.update(parse_xsd_schema(xsd))
                attempt["status"]="official_WFS_layer_and_XSD_schema_verified"
            except Exception as exc:
                attempt["status"]="WFS_or_schema_not_validated"
                attempt["error_type"]=type(exc).__name__
                if isinstance(exc,ValueError):attempt["safe_error_code"]=str(exc)[:120]
            report["probes"].append(attempt)
    except Exception as exc:
        report["catalogue_status"]="not_verified"
        report["error_type"]=type(exc).__name__
        if isinstance(exc,ValueError):report["safe_error_code"]=str(exc)[:120]
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    a=parser.parse_args();res=run()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(res,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"catalogue_status":res.get("catalogue_status","retrieved"),
                      "metadata_probes":[[x["WFS_version"],x["status"],x.get("possible_height_field_names")]
                        for x in res["probes"]],"survey_marks_acquired":0,
                      "crossborder_benchmarks_validated":False}))

if __name__=="__main__":main()
