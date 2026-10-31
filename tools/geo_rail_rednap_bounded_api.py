#!/usr/bin/env python3
"""W4: bounded public IGN REDNAP observations in three selected border areas.

Collect only public survey signal identifiers, coordinates, published
orthometric and ellipsoidal heights from official Spanish OGC API Features.
May support subsequent checks; published REDNAP height pairs are *not*
independent of a geoid fitted against REDNAP, nor proof of MDT elevation
accuracy. No entire Spain download, no DGT credentials.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen

ORIGIN="https://api-features.ign.es"
ENDPOINT="/collections/red_nap/items"
WINDOWS=(
 ("Border_Aliste",(-6.85,41.58,-6.55,41.88)),
 ("Alcanices",(-6.55,41.58,-6.18,41.88)),
 ("Zamora",(-5.97,41.38,-5.55,41.69)),
)
MAX_PER_PAGE=100
MAX_PAGES_PER_WINDOW=4
MAX_RESPONSE_BYTES=2_000_000
ALLOWED_FIELDS=("nombre","nombre_muni","nombre_prov","tipo","linea",
                "latitud_etrs89","longitud_etrs89","ortometrica",
                "altitud_elipsoidal","nodo")

def query_url(bbox,offset):
    if bbox not in [x[1] for x in WINDOWS]:
        raise ValueError("unreviewed_RED_NAP_bbox")
    if offset not in [i*MAX_PER_PAGE for i in range(MAX_PAGES_PER_WINDOW)]:
        raise ValueError("unreviewed_RED_NAP_pagination")
    args=urlencode({"bbox":",".join(str(x) for x in bbox),
                    "limit":MAX_PER_PAGE,"offset":offset,"f":"json"})
    return ORIGIN+ENDPOINT+"?"+args

def bounded_query(url,opener=urlopen):
    parts=urlsplit(url)
    if (parts.scheme!="https" or parts.netloc!="api-features.ign.es"
        or parts.path!=ENDPOINT or parts.fragment):
        raise ValueError("REDNAP_source_origin_not_allowed")
    hasher=hashlib.sha256()
    count=0
    request=Request(url,headers={"User-Agent":"MN-GEO-RAIL-001-REDNAP-bounded-qa/1.0",
                                 "Accept":"application/geo+json,application/json"})
    with opener(request,timeout=30) as response:
        if response.status!=200:raise ValueError("REDNAP_API_HTTP_not_200")
        chunks=[]
        while part:=response.read(131072):
            count+=len(part)
            if count>MAX_RESPONSE_BYTES:
                raise ValueError("REDNAP_page_over_2MB")
            hasher.update(part);chunks.append(part)
    result=json.loads(b"".join(chunks))
    if result.get("type")!="FeatureCollection" or not isinstance(result.get("features"),list):
        raise ValueError("REDNAP_not_GeoJSON_FeatureCollection")
    if len(result["features"])>MAX_PER_PAGE:
        raise ValueError("REDNAP_page_ignored_requested_limit")
    return result,{"sha256":hasher.hexdigest(),"bytes":count}

def parse_public_signal(item,bbox):
    if not isinstance(item,dict) or item.get("type")!="Feature":
        raise ValueError("not_a_RED_NAP_GeoJSON_feature")
    geom=item.get("geometry")
    if not isinstance(geom,dict) or geom.get("type")!="Point":
        raise ValueError("REDNAP_signal_not_point")
    ll=geom.get("coordinates")
    if not isinstance(ll,list) or len(ll)<2 or not all(
            isinstance(v,(int,float)) and math.isfinite(v) for v in ll[:2]):
        raise ValueError("invalid_RED_NAP_position")
    lon,lat=map(float,ll[:2])
    if not(bbox[0]-0.000001<=lon<=bbox[2]+0.000001 and
           bbox[1]-0.000001<=lat<=bbox[3]+0.000001):
        raise ValueError("API_returned_signal_outside_requested_bbox")
    props=item.get("properties")
    if not isinstance(props,dict):raise ValueError("REDNAP_properties_missing")
    lonattr=props.get("longitud_etrs89"); latattr=props.get("latitud_etrs89")
    if isinstance(lonattr,(float,int)) and abs(lon-lonattr)>0.002:
        raise ValueError("REDNAP_geometry_longitude_disagrees_with_attribute")
    if isinstance(latattr,(float,int)) and abs(lat-latattr)>0.002:
        raise ValueError("REDNAP_geometry_latitude_disagrees_with_attribute")
    # Some public OGC API features have no standard GeoJSON id and no
    # 'numero' in properties. Do NOT invent an authoritative IGN number.
    signal_id=item.get("id")
    if signal_id is None or signal_id=="":
        signal_id=props.get("numero")
    authority_id=(str(signal_id) if isinstance(signal_id,(int,str)) and
                  signal_id!="" and len(str(signal_id))<=80 else None)
    if authority_id is None:
        fingerprint=json.dumps({"coordinates":[lon,lat],
                    "name":props.get("nombre"),"line":props.get("linea")},
                    sort_keys=True,ensure_ascii=False)
        local_key="local_no_official_id_sha256:"+hashlib.sha256(
                    fingerprint.encode("utf-8")).hexdigest()[:24]
    else:
        local_key="IGN_RED_NAP:"+authority_id
    h_orth=props.get("ortometrica")
    h_ell=props.get("altitud_elipsoidal")
    for h in (h_orth,h_ell):
        if h is not None and(not isinstance(h,(int,float)) or not math.isfinite(h)
                             or not -100<h<4500):
            raise ValueError("nonfinite_or_outlying_RED_NAP_height")
    out={"producer_id":authority_id,
         "official_source_id_available":authority_id is not None,
         "local_deduplication_key":local_key,
         "lon_etrs89":lon,"lat_etrs89":lat,
         "orthometric_height_m":h_orth,"ellipsoidal_height_m":h_ell,
         "both_heights_published":h_orth is not None and h_ell is not None,
         "original_source":"IGN REDNAP OGC API-Features public survey mark"}
    if out["both_heights_published"]:
        diff=float(h_ell-h_orth)
        if not 30<diff<80:
            raise ValueError("implausible_RED_NAP_ellipsoidal_orthometric_difference")
        out["ellipsoidal_minus_orthometric_m"]=diff
    for k in ("nombre","nombre_muni","nombre_prov","tipo","linea","nodo"):
        if props.get(k) is not None:out[k]=str(props[k])[:180]
    return out

def run(opener=urlopen):
    result={"mission":"MN-GEO-RAIL-001","worker":"W4",
      "stage":"official_IGN_RED_NAP_bounded_benchmark_candidates",
      "timestamp_utc":datetime.now(timezone.utc).isoformat(),
      "authority":"Instituto Geográfico Nacional de España, REDNAP",
      "source_collection":ORIGIN+"/collections/red_nap",
      "sampling_strategy":"three reviewed geographic windows; NOT total REDNAP dataset",
      "vertical_reference_documented":"Alicante / REDNAP",
      "source_respects_CC_BY_attribution":"Instituto Geográfico Nacional / CNIG",
      "request_windows":[],
      "survey_mark_candidates":[],
      "queries_successful":0,"source_fully_retrieved_in_all_windows":True,
      "independent_geoid_holdout_data":False,
      "observations_used_for_rail_datum_control":False,
      "source_original_WCS_MDT_grid_datum_verified":False,
      "no_DGT_authenticated_download":True,
      "cross_border_harmonization_validated":False,
      "canonical_Fxx_accepted":False}
    dedup={}
    for name,bbox in WINDOWS:
        w={"name":name,"bbox_wgs84":list(bbox),"pages":[],"status":"incomplete"}
        collected=[]
        try:
            for page in range(MAX_PAGES_PER_WINDOW):
                offset=page*MAX_PER_PAGE
                data,metadata=bounded_query(query_url(bbox,offset),opener=opener)
                w["pages"].append({"offset":offset,"returned":len(data["features"]),
                                   "response_SHA256":metadata["sha256"],"bytes":metadata["bytes"],
                                   "numberMatched":data.get("numberMatched")})
                result["queries_successful"]+=1
                rows=[parse_public_signal(x,bbox) for x in data["features"]]
                collected+=rows
                matched=data.get("numberMatched")
                if (isinstance(matched,int) and offset+len(rows)>=matched) or len(rows)<MAX_PER_PAGE:
                    w["status"]="complete";break
            if w["status"]!="complete":
                result["source_fully_retrieved_in_all_windows"]=False
            for signal in collected:
                key=signal["local_deduplication_key"]
                previous=dedup.get(key)
                if previous is not None and previous!=signal:
                    raise ValueError("same_RED_NAP_signal_conflicting_values_across_windows")
                dedup[key]=signal
            w["signals_retrieved"]=len(collected)
            w["signals_with_both_heights"]=sum(s["both_heights_published"] for s in collected)
        except Exception as e:
            result["source_fully_retrieved_in_all_windows"]=False
            w["status"]="failed_closed"
            w["error_class"]=type(e).__name__
            w["error_code"]=str(e)[:110] if isinstance(e,ValueError) else "network_or_schema_error"
        result["request_windows"].append(w)
    result["survey_mark_candidates"]=sorted(dedup.values(),key=lambda z:z["local_deduplication_key"])
    result["distinct_survey_mark_candidates"]=len(dedup)
    result["survey_marks_with_official_source_id"]=sum(x["official_source_id_available"] for x in dedup.values())
    result["survey_marks_without_official_source_id"]=sum(not x["official_source_id_available"] for x in dedup.values())
    result["distinct_marks_with_both_heights"]=sum(s["both_heights_published"] for s in dedup.values())
    result["published_height_pairs_not_independent_geoid_benchmarks"]=True
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    x=p.parse_args()
    report=run()
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"windows":[(w["name"],w["status"],w.get("signals_retrieved"))
                 for w in report["request_windows"]],
                "queries":report["queries_successful"],
                "survey_marks":report["distinct_survey_mark_candidates"],
                "paired_heights":report["distinct_marks_with_both_heights"],
                "independent_cross_border_validation":False},ensure_ascii=False))
    if not report["source_fully_retrieved_in_all_windows"]:
        raise SystemExit("REDNAP bounded windows not complete; do not treat sample as exhaustive")

if __name__=="__main__":
    main()
