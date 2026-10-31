#!/usr/bin/env python3
"""W4: bounded DGT geodesy OGC WFS/WMS metadata access diagnostics.

Purpose: locate a provider-authenticated RNGAP source for actual official
Portuguese leveling marks and Cascais heights. DGT confirms it offers WMS/WFS
location layers, but specific endpoints and attributes need verification.
Only GetCapabilities XML is requested, NEVER whole-country GetFeature,
and no credentials are used. Failure cannot mean RNGAP marks are absent.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET

HOST="mapas.dgterritorio.pt"
BASE="https://mapas.dgterritorio.pt/ows/geodesia/continente"
APPROVED=(
 ("WFS_2_0_0","WFS","2.0.0"),
 ("WFS_1_1_0","WFS","1.1.0"),
 ("WMS_1_3_0","WMS","1.3.0")
)
MAX_RESPONSE_BYTES=2_000_000
KEYWORDS=("nivelamento","rngap","nivel","nivelacao","altim","geodes",
          "gravimet","marca","bench")

def capabilities_url(service,version):
    if (service,version) not in {(x[1],x[2]) for x in APPROVED}:
        raise ValueError("unsupported_DGT_geodesy_capabilities_probe")
    return BASE+"?"+urlencode({"SERVICE":service,"REQUEST":"GetCapabilities","VERSION":version})

def bounded_fetch(url,opener=urlopen):
    parts=urlsplit(url)
    if parts.scheme!="https" or parts.hostname!=HOST or parts.path!="/ows/geodesia/continente":
        raise ValueError("unapproved_DGT_capabilities_origin")
    request=Request(url,headers={"User-Agent":"MN-GEO-RAIL-001-geodesy-metadata-probe/1.0",
                                 "Accept":"text/xml,application/xml"})
    total=0;parts_data=[];digest=hashlib.sha256()
    with opener(request,timeout=28) as response:
        final=urlsplit(response.geturl())
        if response.status!=200 or final.scheme!="https" or final.hostname!=HOST:
            raise ValueError("OGC_capabilities_redirect_or_status_not_approved")
        while chunk:=response.read(65536):
            total+=len(chunk)
            if total>MAX_RESPONSE_BYTES:
                raise ValueError("OGC_capabilities_over_2MB")
            digest.update(chunk);parts_data.append(chunk)
    xml=b"".join(parts_data)
    return xml,{"bytes":total,"sha256":digest.hexdigest()}

def parse_layers(content):
    root=ET.fromstring(content)
    root_name=root.tag.rsplit("}",1)[-1]
    if root_name not in ("WFS_Capabilities","WMS_Capabilities","WMT_MS_Capabilities"):
        raise ValueError("DGT_response_not_OGC_capabilities")
    found=[]
    # Inspect only whitelisted Name, Title pairs to avoid source URLs,
    # email addresses and other unrelated metadata or complex XML payloads.
    for feature in root.iter():
        tag=feature.tag.rsplit("}",1)[-1]
        if tag not in ("FeatureType","Layer"):continue
        title=None;name=None
        for kid in feature:
            kind=kid.tag.rsplit("}",1)[-1]
            if kind=="Name":name=(kid.text or "").strip()
            if kind=="Title":title=(kid.text or "").strip()
        if name:
            found.append({"name":name[:160],"title":(title or "")[:200]})
    unique={z["name"]:z for z in found}
    matched=[z for z in unique.values() if any(k in
           (z["name"]+" "+z["title"]).casefold() for k in KEYWORDS)]
    return {"root_element":root_name,"total_named_layers":len(unique),
            "geodesy_keyword_matching_layers":matched[:50],
            "geodesy_candidate_layer_count":len(matched),
            "all_layer_names_are_Not_assumed_RNGAP_marks":True,
            "altitude_attribute_schema_checked":False}

def run(opener=urlopen):
    report={"mission":"MN-GEO-RAIL-001","worker":"W4",
       "stage":"portugal_DGT_RNGAP_official_OGC_capabilities_no_data_download_probe",
       "observed_utc":datetime.now(timezone.utc).isoformat(),
       "DGT_official_geodesy_information_page":"https://www.dgterritorio.gov.pt/atividades/geodesia/infraestrutura-geodesica",
       "DGT_official_service_information_page":"https://www.dgterritorio.gov.pt/node/1433",
       "OGC_endpoint_candidate_provenance":"DGT-hosted URL also indexed in third-party service catalogue; must verify live official response",
       "candidate_OGC_url":BASE,
       "results":[],"successful_valid_OGC_service_responses":0,
       "verified_DGT_RNGAP_feature_type_with_official_heights":False,
       "Portuguese_RNGAP_mark_coordinates_acquired":0,
       "Portuguese_RNGAP_official_altitudes_acquired":0,
       "full_country_source_feature_downloaded":False,
       "absence_of_RNGAP_marks_inferred_from_failed_probe":False,
       "crossborder_benchmark_validation_complete":False,
       "canonical_Fxx_accepted":False}
    for name,service,version in APPROVED:
        rec={"probe":name,"service":service,"version":version,"status":"unverified"}
        try:
            xml,metadata=bounded_fetch(capabilities_url(service,version),opener)
            rec.update(metadata);rec.update(parse_layers(xml));rec["status"]="valid_OGC_capabilities"
            report["successful_valid_OGC_service_responses"]+=1
        except Exception as e:
            rec["status"]="not_accessible_or_not_validated"
            rec["error_class"]=type(e).__name__
            rec["no_coverage_absence_claim"]=True
        report["results"].append(rec)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True,type=Path)
    x=p.parse_args()
    report=run()
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"valid_OGC_responses":report["successful_valid_OGC_service_responses"],
                      "probe_statuses":[(x["probe"],x["status"],x.get("geodesy_candidate_layer_count"))
                        for x in report["results"]],
                      "RNGAP_marks_acquired":0,
                      "crossborder_datum_proven":False}))

if __name__=="__main__":
    main()
