#!/usr/bin/env python3
"""W4: fully page the THREE reviewed current official RNGAP DGT WFS windows.

Official catalog source: dados.gov.pt RNGAP WFS, geo2.dgterritorio.gov.pt.
Each 100-feature response capped at 1.5MB; max five pages per window;
fail closed on incomplete pages, inconsistent feature IDs or source heights.
Retrieves a *regional review-window* inventory, NOT all Portuguese RNGAP,
nor independent verification of source accuracy, reference datum links,
geoid fitting independence, mark status or full Porto-Zamora corridor.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from geo_rail_pt_rngap_alh38_source_sample import (
    SAMPLES,LAYER,HEIGHT_FIELD,parse_source_features)
from geo_rail_rngap_catalogue_wfs_schema import (
    CATALOGUE,fetch,resource_wfs_url,query,parse_capabilities,parse_xsd_schema)

BASE="https://geo2.dgterritorio.gov.pt/geoserver/RGN/ows"
PAGE_SIZE=100
MAX_PAGES_PER_WINDOW=5
MAX_FEATURES_PER_WINDOW=PAGE_SIZE*MAX_PAGES_PER_WINDOW

def page_url(bbox,offset):
    if bbox not in [r[1] for r in SAMPLES] or offset not in range(0,MAX_FEATURES_PER_WINDOW,PAGE_SIZE):
        raise ValueError("unreviewed_WFS_page_or_bbox")
    return BASE+"?"+urlencode([
      ("service","WFS"),("request","GetFeature"),("version","2.0.0"),
      ("typeNames",LAYER),("count",PAGE_SIZE),("startIndex",offset),
      ("srsName","EPSG:3763"),("bbox",",".join(str(v) for v in bbox)+",EPSG:3763"),
      ("outputFormat","application/json")])

def verify_pages(fetcher=fetch,opener=urlopen):
    out={"mission":"MN-GEO-RAIL-001","worker":"W4",
         "stage":"three_W4_review_windows_official_DGT_RNGAP_all_paged_marks",
         "timestamp_utc":datetime.now(timezone.utc).isoformat(),
         "official_catalogue_source":CATALOGUE,
         "DGT_native_source":BASE,"source_layer":LAYER,
         "source_height_property":HEIGHT_FIELD,
         "horizontal_reference":"EPSG:3763","vertical_reference":"Cascais Helmert 38 (ALTH38 documented)",
         "max_page_size":PAGE_SIZE,"max_pages_per_window":MAX_PAGES_PER_WINDOW,
         "completeness_scoped_to_three_review_windows_only":True,
         "entire_Norte_RNGAP_source_dataset_covered":False,
         "independent_control_against_other_PT_ES_survey_geodesy":False,
         "survey_mark_condition_not_remeasured":True,
         "full_PT_ES_corridor_terrain_available":False,
         "Fxx_canonical_accepted":False,"Site_publication_authorized":False,
         "windows":[],"unique_real_DGT_source_mark_count":0,
         "unique_DGT_source_marks":[],"status":"incomplete"}
    raw,catmeta=fetcher(CATALOGUE,opener=opener)
    url,source=resource_wfs_url(raw)
    if url!=BASE:raise ValueError("DGT_catalogue_WFS_source_changed")
    out["catalogue_sha256"]=catmeta["sha256"]
    out["catalogue_resource_ID"]=source["official_catalogue_resource_ID"]
    xml,cmeta=fetcher(query(BASE,"WFS","GetCapabilities","2.0.0"),opener=opener)
    layers=parse_capabilities(xml)
    if [r["name"] for r in layers["candidate_RNGAP_layers"]] != [LAYER]:
        raise ValueError("RNGAP_layer_identity_changed")
    xsd,smeta=fetcher(query(BASE,"WFS","DescribeFeatureType","2.0.0",LAYER),opener=opener)
    fields=parse_xsd_schema(xsd)["declared_fields"]
    if not {HEIGHT_FIELD,"MARCA"}.issubset(set(fields)):
        raise ValueError("official_WFS_height_and_source_mark_missing")
    out["WFS_caps_sha256"]=cmeta["sha256"]
    out["WFS_schema_sha256"]=smeta["sha256"]
    unique={}
    for label,bbox in SAMPLES:
        window={"review_window":label,"bbox_PT_TM06":bbox,"pages":[],
                "source_layer":LAYER,"status":"incomplete"}
        combined=[]
        matched=None
        for page in range(MAX_PAGES_PER_WINDOW):
            offset=page*PAGE_SIZE
            original,meta=fetcher(page_url(bbox,offset),opener=opener)
            rec=parse_source_features(original,bbox)
            if rec["invalid_records"] or rec["returned_features"] != rec["valid_original_marks"]:
                raise ValueError("source_RNGAP_page_contains_unverified_mark_or_height")
            if matched is None:
                matched=rec["numberMatched"]
            if matched is None or rec["numberMatched"]!=matched:
                raise ValueError("official_WFS_numberMatched_missing_or_changed")
            if rec["returned_features"]>PAGE_SIZE:
                raise ValueError("DGT_WFS_pagination_ignored_limit")
            if rec["returned_features"]!=min(PAGE_SIZE,matched-offset):
                raise ValueError("source_WFS_page_size_or_offset_inconsistent")
            window["pages"].append({"startIndex":offset,"page_sha256":meta["sha256"],
                     "bytes":meta["size_bytes"],"returned":rec["returned_features"],
                     "numberMatched":matched})
            combined.extend(rec["observations_validated"])
            if len(combined)==matched:break
        if len(combined)!=matched:
            raise ValueError("source_WFS_window_not_completely_paged")
        if len({x["WFS_feature_id"] for x in combined})!=len(combined):
            raise ValueError("duplicate_source_ID_inside_WFS_window")
        for x in combined:
            prev=unique.get(x["WFS_feature_id"])
            if prev is not None and prev!=x:
                raise ValueError("same_DGT_mark_conflicting_attributes_across_windows")
            unique[x["WFS_feature_id"]]=x
        window["status"]="all_bounded_pages_complete"
        window["validated_original_mark_count"]=len(combined)
        window["official_WFS_numberMatched"]=matched
        out["windows"].append(window)
    out["unique_real_DGT_source_mark_count"]=len(unique)
    out["unique_DGT_source_marks"]=sorted(unique.values(),key=lambda x:x["WFS_feature_id"])
    out["total_source_features_in_windows_before_deduplication"]=sum(x["validated_original_mark_count"] for x in out["windows"])
    out["status"]="complete_for_three_requested_windows_no_corridor_claim"
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    try:out=verify_pages()
    except Exception as e:
        out={"mission":"MN-GEO-RAIL-001","stage":"W4_RNGAP_WFS_full_paging_failed_closed",
             "error_class":type(e).__name__,
             "safe_error_code":str(e)[:120] if isinstance(e,ValueError) else None,
             "unique_real_DGT_source_mark_count":0,
             "Fxx_canonical_accepted":False,"Site_publication_authorized":False}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":out.get("status"),"mark_count":out["unique_real_DGT_source_mark_count"],
                      "windows":[(x["review_window"],x["validated_original_mark_count"]) for x in out.get("windows",[])]}))
    if out.get("status")!="complete_for_three_requested_windows_no_corridor_claim":
        raise SystemExit("Source WFS three-window mark inventory did not validate")
if __name__=="__main__":main()
