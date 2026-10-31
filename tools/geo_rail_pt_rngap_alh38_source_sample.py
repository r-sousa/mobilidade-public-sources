#!/usr/bin/env python3
"""Bounded real DGT RNGAP layer sampling from catalog-verified HTTPS WFS.

The specific geo2 DGT WFS RGN:RedeNivelamento layer and ALTH38 schema are
validated via official data.gov.pt metadata separately. This method downloads
up to 3 x 40 source features within 3 explicit PT-TM06 review windows;
never claims full coverage, epoch accuracy, survey benchmark independence
or source mark availability outside tested windows. GeoJSON geometries must
be exact PT-TM06 points; nonpoint features are diagnosed and NOT counted as
official benchmark marks. No DGT credentials or huge transfers.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from geo_rail_rngap_catalogue_wfs_schema import CATALOGUE,fetch,resource_wfs_url,query,parse_capabilities,parse_xsd_schema

LAYER="RGN:RedeNivelamento"
HEIGHT_FIELD="ALTH38"
LIMIT=40
SAMPLES=(
 ("Mirandela", [70000,175000,105000,235000]),
 ("VilaReal_Mirandela", [10000,125000,85000,205000]),
 ("Nordeste_fronteira", [105000,205000,175000,290000])
)
MAX_SOURCE_RESPONSE_BYTES=1_500_000

def feature_url(base,bbox):
    if bbox not in [x[1] for x in SAMPLES]:
        raise ValueError("unapproved_source_sampling_window")
    return base+"?"+urlencode([
        ("service","WFS"),("request","GetFeature"),("version","2.0.0"),
        ("typeNames",LAYER),("count",LIMIT),
        ("srsName","EPSG:3763"),
        ("bbox",",".join(str(x) for x in bbox)+",EPSG:3763"),
        ("outputFormat","application/json")])

def parse_source_features(raw,bbox):
    obj=json.loads(raw)
    if obj.get("type")!="FeatureCollection" or not isinstance(obj.get("features"),list):
        raise ValueError("DGT_WFS_response_not_GeoJSON_FeatureCollection")
    rows=obj["features"]
    if len(rows)>LIMIT:raise ValueError("DGT_WFS_ignored_bounded_max_features")
    retained=[];invalid=[]
    for i,x in enumerate(rows):
        geom=x.get("geometry")
        props=x.get("properties")
        if not isinstance(props,dict) or not isinstance(geom,dict):
            invalid.append({"row":i,"reason":"missing_source_properties_or_geometry"});continue
        kind=geom.get("type")
        coords=geom.get("coordinates")
        if kind!="Point" or not isinstance(coords,list) or len(coords)<2:
            invalid.append({"row":i,"reason":"WFS_geometry_not_Point","geometry_type":str(kind)[:50]});continue
        xx,yy=coords[:2]
        if not all(isinstance(z,(int,float)) and math.isfinite(z) for z in (xx,yy)):
            invalid.append({"row":i,"reason":"bad_source_coordinate"});continue
        if not bbox[0]-1<=xx<=bbox[2]+1 or not bbox[1]-1<=yy<=bbox[3]+1:
            invalid.append({"row":i,"reason":"coordinate_not_in_PT_TM06_bbox"});continue
        h=props.get(HEIGHT_FIELD)
        if h is None or isinstance(h,bool):
            invalid.append({"row":i,"reason":"missing_original_ALTH38"});continue
        # Never silently coerce a qualitative or ambiguous height value.
        if not isinstance(h,(int,float)) or not math.isfinite(h) or not -20<h<2600:
            invalid.append({"row":i,"reason":"non_numeric_or_out_of_range_ALTH38"});continue
        id_value=x.get("id")
        if not isinstance(id_value,(int,str)) or not str(id_value).strip() or len(str(id_value))>160:
            invalid.append({"row":i,"reason":"missing_official_source_feature_ID"});continue
        name=props.get("MARCA")
        if not isinstance(name,(int,str)) or len(str(name))>120:
            invalid.append({"row":i,"reason":"unidentified_survey_MARK"});continue
        retained.append({
            "WFS_feature_id":str(id_value),
            "mark_label_MARCA":str(name),
            "native_xy_epsg3763":[float(xx),float(yy)],
            "DGT_original_ALTH38_height_m":float(h),
            "source_vertical_reference":"Cascais Helmert 38 (ALTH38; DGT official documentation)",
            "original_layer":LAYER,
            "original_property_keys_present":sorted(str(k) for k in props.keys())[:45],
            "source_mark_physical_quality_not_verified":True,
            "independent_survey_remeasurement_not_performed":True,
            "no_raster_height_comparison_yet":True})
    rawmatched=obj.get("numberMatched")
    matched=int(rawmatched) if isinstance(rawmatched,int) and not isinstance(rawmatched,bool) else None
    return {"returned_features":len(rows),
            "numberMatched":matched,
            "source_response_potentially_paged":len(rows)==LIMIT or
              (matched is not None and matched>len(rows)),
            "observations_validated":retained,
            "invalid_records":invalid[:40],
            "valid_original_marks":len(retained),
            "not_full_source_coverage":True}

def run(opener=urlopen):
    out={"mission":"MN-GEO-RAIL-001","stage":"bounded_real_DGT_RNGAP_WFS_ALTH38_source_mark_intake",
         "timestamp_utc":datetime.now(timezone.utc).isoformat(),
         "expected_WFS_service":"https://geo2.dgterritorio.gov.pt/geoserver/RGN/ows",
         "selected_layer":LAYER,"original_height_field":HEIGHT_FIELD,
         "source_producer":"Direção-Geral do Território",
         "source_catalogue":"https://dados.gov.pt/pt/datasets/rede-de-nivelamento-geometrico-de-alta-precisao-rngap",
         "spatial_crs":"EPSG:3763","vertical_reference_documented":"Cascais Helmert 38",
         "window_count":3,"features_limit_per_window":LIMIT,
         "windows":[],"unique_source_mark_count":0,
         "full_corridor_benchmark_coverage":False,
         "original_source_height_validation_without_independent_control":True,
         "benchmark_remeasured_physically":False,
         "independent_PT_ES_height_datum_harmonized":False,
         "Fxx_canonical_accepted":False,"Site_approved":False}
    try:
        data,catmeta=fetch(CATALOGUE,opener=opener)
        base,identity=resource_wfs_url(data)
        if base!=out["expected_WFS_service"]:
            raise ValueError("catalogue_WFS_service_URL_changed_since_schema_validation")
        out["catalogue_sha256"]=catmeta["sha256"]
        out["WFS_resource_ID"]=identity["official_catalogue_resource_ID"]
        cap,meta=fetch(query(base,"WFS","GetCapabilities","2.0.0"),opener=opener)
        caps=parse_capabilities(cap)
        if [x["name"] for x in caps["candidate_RNGAP_layers"]] !=[LAYER]:
            raise ValueError("WFS_RNGAP_layer_differed_from_reviewed_identity")
        xsd,xmeta=fetch(query(base,"WFS","DescribeFeatureType","2.0.0",LAYER),opener=opener)
        schema=parse_xsd_schema(xsd)
        if HEIGHT_FIELD not in schema["declared_fields"] or "MARCA" not in schema["declared_fields"]:
            raise ValueError("WFS_source_critical_fields_not_present")
        out["WFS_getcapabilities_sha256"]=meta["sha256"]
        out["WFS_feature_type_XSD_sha256"]=xmeta["sha256"]
        unique={}
        for label,bbox in SAMPLES:
            rec={"name":label,"bbox_PT_TM06":bbox,"status":"unverified"}
            try:
                src,rmeta=fetch(feature_url(base,bbox),opener=opener,max_bytes=MAX_SOURCE_RESPONSE_BYTES)
                rec["source_payload_SHA256"]=rmeta["sha256"]
                rec["source_bytes"]=rmeta["size_bytes"]
                rec.update(parse_source_features(src,bbox))
                for mark in rec["observations_validated"]:
                    previous=unique.get(mark["WFS_feature_id"])
                    if previous is not None and previous!=mark:
                        raise ValueError("same_source_mark_ID_conflicting_records")
                    unique[mark["WFS_feature_id"]]=mark
                rec["status"]="sampled_original_DGT_WFS_feature_response"
            except Exception as exc:
                rec["status"]="source_GeoJSON_or_mark_attributes_not_validated"
                rec["error_class"]=type(exc).__name__
                if isinstance(exc,ValueError):rec["safe_error_code"]=str(exc)[:120]
            out["windows"].append(rec)
        out["unique_source_mark_count"]=len(unique)
    except Exception as exc:
        out["status"]="source_not_validated"
        out["error_class"]=type(exc).__name__
        if isinstance(exc,ValueError):out["safe_error_code"]=str(exc)[:120]
    return out

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--output",required=True,type=Path)
    arg=a.parse_args();out=run()
    arg.output.parent.mkdir(parents=True,exist_ok=True)
    arg.output.write_text(json.dumps(out,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"source_mark_count":out["unique_source_mark_count"],
          "window_stats":[[w["name"],w["status"],w.get("returned_features"),w.get("valid_original_marks"),w.get("invalid_records",[])[:2]]
                     for w in out["windows"]],
          "cross_border_datum_accepted":False,"canonical":False}))
if __name__=="__main__":main()
