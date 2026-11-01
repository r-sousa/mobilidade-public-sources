#!/usr/bin/env python3
"""G26A DGT COS2025 official OGC service exact bounded access diagnostic.
No claims of source polygons or municipal site land rights. Retries low-rate
source collection and one point-sized bbox with several standard parameters.
No national dataset downloaded and no secrets used."""
import urllib.request,urllib.error,urllib.parse,json,hashlib,time
from datetime import datetime,timezone
from pathlib import Path
import argparse

HOST="https://ogcapi.dgterritorio.gov.pt"
URL=HOST+"/collections/cos2025v1/items"
TRIALS=(
 ("collection","/collections/cos2025v1?f=json"),
 ("single_no_bbox","/collections/cos2025v1/items?limit=1&f=json"),
 ("tiny_bbox_json","/collections/cos2025v1/items?bbox=-7.750,41.300,-7.749,41.301&limit=1&f=json"),
 ("tiny_bbox_geojson","/collections/cos2025v1/items?bbox=-7.750,41.300,-7.749,41.301&limit=1&f=geojson"),
 ("tiny_bbox_default","/collections/cos2025v1/items?bbox=-7.750,41.300,-7.749,41.301&limit=1"),
)
def run(out):
 data=[]
 for i,(label,path) in enumerate(TRIALS):
  if i:time.sleep(.5)
  req=urllib.request.Request(HOST+path,headers={"User-Agent":"MobilidadeNorte-source-availability-probe-COS2025/1.0","Accept":"application/geo+json,application/json"})
  try:
   with urllib.request.urlopen(req,timeout=25) as resp:
    raw=resp.read(200001)
    record={"test":label,"HTTP_status":resp.status,"small_limited_response_SHA256":hashlib.sha256(raw).hexdigest(),
      "response_bytes_read_max200k":len(raw),"truncated_response_bytes_check":len(raw)==200001}
    if label!="collection" and resp.status==200 and len(raw)<200001:
     j=json.loads(raw)
     record["original_COS2025_collection_type"]=j.get("type")
     record["actual_vector_feature_count"]=len(j.get("features",[])) if isinstance(j.get("features"),list) else None
  except urllib.error.HTTPError as e:
   record={"test":label,"HTTP_status":e.code,"backend_error_not_local_source_data":True}
  except Exception as e:
   record={"test":label,"error_type":type(e).__name__,"backend_response_not_original_source_data":True}
  data.append(record)
 source_ok=any(x.get("HTTP_status")==200 and x.get("original_COS2025_collection_type")=="FeatureCollection" for x in data)
 doc={"mission":"MN-GEO-RAIL-001","stage":"G26A_DGT_COS2025_original_OGC_API_health_no_source_data_claim",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "original_public_DGT_collection":"cos2025v1",
  "source_CAN_return_COS2025_vector_features_with_bounded_query":source_ok,
  "no_claim_original_COS2025_features_acquired":True,
  "producer_endpoint_status_probe":data,
  "no_DGT_elevation_or_COS_bulk_download":True,
  "Fxx_accepted":False,"Site_authorized":False}
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 print("G26A_COS_DGT_PROBE="+json.dumps({"service_returns_vector":source_ok,"status":[(x["test"],x.get("HTTP_status",x.get("error_type"))) for x in data]},separators=(",",":")))
 return source_ok
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--json",type=Path,required=True);a=p.parse_args();run(a.json)
