#!/usr/bin/env python3
"""Source-constrained official DGT RNGAP NP159 physical-mark variant metadata.

Only a 100m x 100m window at the original provider NP159 coordinates, capped
at 30 WFS GeoJSON features and 0.6MB. Preserve reviewed non-sensitive original
description, secondary marks and road/side labels. Does not imply physical
horizontal 0cm coincidence, independent survey, or ground-surface benchmark.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from geo_rail_pt_cdd_rngap_tile279503 import SOURCE_MARKS,producer_mark_records
from geo_rail_rngap_catalogue_wfs_schema import HOST

BASE="https://geo2.dgterritorio.gov.pt/geoserver/RGN/ows"
WINDOW=(79418,202238,79518,202338)
MAX_BYTES=600000
MAX_FEATURES=30
ATTRIBUTES=("MARCA","MARCA2","MARCA3","MARCA4","MARCA5","LIN_SEC",
            "LIN_SEC2","LIN_SEC3","LIN_SEC4","LIN_SEC5","ALTH38",
            "ESTRADA","ESTLADO","DESCRICAO")

def url_for_source():
    return BASE+"?"+urlencode([
        ("service","WFS"),("version","2.0.0"),("request","GetFeature"),
        ("typeNames","RGN:RedeNivelamento"),("count",MAX_FEATURES),
        ("srsName","EPSG:3763"),
        ("bbox",",".join(str(z) for z in WINDOW)+",EPSG:3763"),
        ("outputFormat","application/json")])

def bounded_fetch(opener=urlopen):
    url=url_for_source()
    req=Request(url,headers={"User-Agent":"MN-GEO-RAIL-001-NP159-original-physical-mark-audit/1.0",
                            "Accept":"application/json"})
    count=0;h=hashlib.sha256();chunks=[]
    with opener(req,timeout=30) as response:
        from urllib.parse import urlsplit
        final=urlsplit(response.geturl())
        if response.status!=200 or final.scheme!="https" or final.hostname!=HOST:
            raise ValueError("DGT_RNGAP_redirect_or_HTTP_status_not_approved")
        while piece:=response.read(65536):
            count+=len(piece)
            if count>MAX_BYTES:raise ValueError("NP159_DGT_source_600kB_cap_exceeded")
            h.update(piece);chunks.append(piece)
    return b"".join(chunks),{"source_response_sha256":h.hexdigest(),"source_bytes":count}

def inspect(raw,expected_marks):
    doc=json.loads(raw)
    features=doc.get("features")
    if doc.get("type")!="FeatureCollection" or not isinstance(features,list):
        raise ValueError("DGT_RNGAP_expected_GeoJSON_missing")
    if len(features)>MAX_FEATURES:raise ValueError("NP159_oversized_source_mark_count")
    evidence=[]
    for f in features:
        if not isinstance(f,dict) or f.get("id") not in SOURCE_MARKS:
            continue
        props=f.get("properties")
        geom=f.get("geometry")
        if not isinstance(props,dict) or not isinstance(geom,dict) or geom.get("type")!="Point":
            raise ValueError("NP159_original_WFS_source_geometry_not_point")
        coord=geom.get("coordinates")
        if not isinstance(coord,list) or len(coord)<2 or not all(
                isinstance(z,(int,float)) and math.isfinite(z) for z in coord[:2]):
            raise ValueError("NP159_original_coordinates_not_numeric")
        if not (WINDOW[0]<=coord[0]<=WINDOW[2] and WINDOW[1]<=coord[1]<=WINDOW[3]):
            raise ValueError("NP159_outside_approved_100m_source_bbox")
        d={"WFS_source_feature_id":f["id"],"native_provider_xy_epsg3763":[float(coord[0]),float(coord[1])]}
        d["original_attributes"]={k:props.get(k) for k in ATTRIBUTES if k in props}
        original=expected_marks[f["id"]]
        if (str(props.get("MARCA"))!=original["mark_label_MARCA"] or
            abs(float(original["DGT_original_ALTH38_height_m"])-float(props.get("ALTH38")))>.000001):
            raise ValueError("NP159_original_source_attribute_changed")
        evidence.append(d)
    if len(evidence)!=len(SOURCE_MARKS) or len({e["WFS_source_feature_id"] for e in evidence})!=len(SOURCE_MARKS):
        raise ValueError("NP159_five_reviewed_source_marks_not_found_in_small_bbox")
    evidence.sort(key=lambda x:x["WFS_source_feature_id"])
    return {"matching_reviewed_source_records":len(evidence),
            "selected_mark_physical_identification_fields":evidence,
            "all_source_feature_identifiers_matched_previous_427_RNGAP_WFS":True,
            "all_source_mark_original_ALTH38_match_previous_catalogue":True,
            "physical_mark_height_offset_explained_by_detailed_source":False,
            "independent_remeasurement_of_marks_performed":False,
            "same_WFS_XY_does_not_prove_same_physical_reference_point":True}

def run(original,opener=urlopen):
    marks,sha=producer_mark_records(original)
    data,payload=bounded_fetch(opener)
    report=inspect(data,{x["WFS_feature_id"]:x for x in marks})
    report.update({"mission":"MN-GEO-RAIL-001","stage":"W4_DGT_NP159_original_5_mark_variants_descriptive_metadata",
      "observed_utc":datetime.now(timezone.utc).isoformat(),
      "producer":"Direção-Geral do Território","source_layer":"RGN:RedeNivelamento",
      "source_height_field":"ALTH38","catalogue_mark_original_SHA256":sha,
      "bbox_epsg3763":list(WINDOW),
      "native_tile_source_candidate":"MDT-2m-279503-09-2024",
      "actual_DGT_native_tile_pixel_comparison_performed":False,
      "vertical_crossborder_benchmark_accepted":False,
      "Fxx_canonical_accepted":False,"Site_publication_authorized":False,
      **payload})
    return report

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--source",required=True,type=Path)
    a.add_argument("--output",required=True,type=Path)
    args=a.parse_args()
    try:j=run(args.source)
    except Exception as e:
        j={"mission":"MN-GEO-RAIL-001","status":"NP159_original_source_metadata_not_verified",
           "safe_error":str(e)[:130] if isinstance(e,ValueError) else type(e).__name__,
           "Fxx_canonical_accepted":False}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(j,indent=2)+"\n")
        raise SystemExit("NP159 small bbox source metadata verification failed closed")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(j,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"reviewed_marks":j["matching_reviewed_source_records"],
        "physical_description_claim":j["physical_mark_height_offset_explained_by_detailed_source"],
        "crossborder_height_accuracy_accepted":False}))
if __name__=="__main__":main()
