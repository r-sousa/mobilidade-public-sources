#!/usr/bin/env python3
"""G27A bounded primary DGT SNIT services REN Norte/RAN PT/CRUS.
Metadata and ONE-feature source probe only. Missing/HTTP errors documented,
NOT interpreted as an absence of legal constraint. No parcels/railways rated.
"""
import argparse,hashlib,json,urllib.request,urllib.error,urllib.parse,time
from pathlib import Path
from datetime import datetime,timezone
import xml.etree.ElementTree as ET

SERVICES={
 "REN_NORTE":"https://servicos.dgterritorio.pt/SDISNITWFSSRUP_REN_NORTE/WFService.aspx",
 "RAN_PT":"https://servicos.dgterritorio.pt/SDISNITWFSSRUP_RAN_PT1/WFService.aspx",
 "CRUS_NATIONAL":"https://servicos.dgterritorio.pt/SDISNITWFSCRUS/WFService.aspx",
}
MAX_BYTES=2_500_000
G26C_SHA="caf506f6bd114fe200f3f95d29951e97b8c1d9e18c8c654fa64c4ae3f75e81e4"

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def req(url,limit=MAX_BYTES):
 u=urllib.parse.urlparse(url)
 if u.scheme!="https" or u.hostname!="servicos.dgterritorio.pt":raise ValueError("G27_untrusted_official_DGT_endpoint")
 rr=urllib.request.Request(url,headers={"Accept":"application/xml,text/xml,*/*","User-Agent":"MobilidadeNorte-g27-official-SNIT-feature-discovery/1.0"})
 try:
  with urllib.request.urlopen(rr,timeout=42) as f:
   if urllib.parse.urlparse(f.url).hostname!=u.hostname:raise ValueError("untrusted_SNIT_redirect")
   b=f.read(limit+1)
   if len(b)>limit:raise ValueError("G27_SNIT_source_response_exceeds_limit")
   return b,{"HTTP_status":f.status,"bytes":len(b),"response_SHA256":hashlib.sha256(b).hexdigest(),
     "response_content_type":f.headers.get("Content-Type","")}
 except urllib.error.HTTPError as e:
  return None,{"HTTP_status":e.code,"source_endpoint_error_not_a_zero_constraint":True}
 except Exception as e:
  return None,{"error_class":type(e).__name__,"source_endpoint_error_not_a_zero_constraint":True}

def capability_names(payload):
 if not payload:return []
 try:root=ET.fromstring(payload)
 except ET.ParseError:return []
 names=[]
 for x in root.iter():
  if x.tag.rsplit("}",1)[-1]!="FeatureType":continue
  child=next((y for y in x if y.tag.rsplit("}",1)[-1]=="Name"),None)
  if child is not None and child.text:names.append(child.text.strip())
 return names

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--g26c",type=Path,required=True)
 p.add_argument("--json",type=Path,required=True)
 a=p.parse_args()
 if sha(a.g26c)!=G26C_SHA:raise ValueError("G27_G26C_source_sha_pin_changed")
 j=json.loads(a.g26c.read_text())
 if j["seven_distinct_source_study_sites"]!=7 or j["Fxx_accepted"] or j["Site_authorized"]:raise ValueError("G27_source_7_study_sites_invalid")
 probes=[]
 for i,(key,url) in enumerate(SERVICES.items()):
  if i:time.sleep(1)
  capurl=url+"?"+urllib.parse.urlencode({"SERVICE":"WFS","VERSION":"1.1.0","REQUEST":"GetCapabilities"})
  body,meta=req(capurl)
  names=capability_names(body)
  expected={"REN_NORTE":"REN_NORTE","RAN_PT":"RAN","CRUS_NATIONAL":"CRUS"}[key]
  matches=[x for x in names if expected.upper() in x.upper()]
  if not matches and names and key=="REN_NORTE":matches=[x for x in names if "REN" in x.upper()]
  probe={"topic":key,"DGT_official_SNIT_WFS_endpoint":url,
    "WFS_get_capabilities_result":meta,"source_feature_types":names[:80],
    "source_feature_type_matching_expected_topic":matches,
    "source_service_for_G27_is_verified_vector_only_if_real_features_return":True}
  if matches:
   sample=matches[0]
   # tiny source municipal study bbox selected from G26C. No national download.
   xy=j["original_COS2025_local_7_site_summary"][0]["research_EPSG3763_XY"]
   bbox=",".join(str(x) for x in (xy[0]-400,xy[1]-400,xy[0]+400,xy[1]+400))+",EPSG:3763"
   featurequery={"service":"WFS","version":"1.1.0","request":"GetFeature",
    "typeName":sample,"bbox":bbox,"maxFeatures":1}
   fbody,fmeta=req(url+"?"+urllib.parse.urlencode(featurequery))
   probe["bounded_one_feature_at_original_Vila_Real_G26C_study_reference"]=fmeta
   probe["bounded_one_feature_response_start_tags"]=(fbody[:160].decode("utf-8","replace") if fbody else None)
  else:
   probe["no_matching_capabilities_is_NOT_confirmation_of_no_RAN_REN_or_CRUS"]=True
  probes.append(probe)
 q={"mission":"MN-GEO-RAIL-001","stage":"G27A_original_DGT_SNIT_REN_RAN_CRUS_source_WFS_discovery_no_false_legal_constraint",
  "utc":datetime.now(timezone.utc).isoformat(),
  "G26C_SHA256":G26C_SHA,
  "DGT_original_SNIT_licence":"CC BY 4.0 subject to official individual feature/metadata verification",
  "sources":probes,
  "REN_official_legally_published_DR_georeferenced_map_overrules_vector_disagreement":True,
  "RAN_PDM_legal_plants_govern":True,
  "CRUS_territorial_statistical_harmonization_NOT_licensing":True,
  "if_official_vector_source_unavailable_missing_legal_constraint_status_UNKNOWN_not_absent":True,
  "no_station_or_corridor_declared_legally_permitted":True,
  "PDM_REN_RAN_SRUP_hydrological_heritage_domain_status_NOT_YET_ASSESSED":True,
  "no_new_DGT_terrain_raster_acquisition":True,
  "mandatory_cities":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "Fxx_accepted":False,"Site_authorized":False}
 a.json.parent.mkdir(parents=True,exist_ok=True)
 a.json.write_text(json.dumps(q,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 print("G27A_SNIT_SERVICES="+json.dumps({"sources":[{"topic":x["topic"],"HTTP":x["WFS_get_capabilities_result"].get("HTTP_status"),
  "layers":len(x["source_feature_types"]),
  "matches":x["source_feature_type_matching_expected_topic"],
  "one_feature_probe":x.get("bounded_one_feature_at_original_Vila_Real_G26C_study_reference",{})} for x in probes]},ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
