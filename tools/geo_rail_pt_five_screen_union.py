#!/usr/bin/env python3
"""Conservative DGT MDT 2m/50cm catalogue QA across five real public scans.

Metadata rectangle proxies and product ID suffix pairing ONLY.
Never infer native raster/pixel coverage, DGT rights approval for individual
assets, alignment availability, vertical datum, or site/Fxx acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

COLLECTIONS=("MDT-2m","MDT-50cm")
SOURCE_SPECS=(
  ("E01-E06","pt-dgt-mdt-sector-footprints.json",6,12),
  ("G07","pt-dgt-vilareal-mirandela-anonymous-strip.json",10,20),
  ("G08","pt-dgt-porto-vilareal-anonymous-strip.json",16,32),
  ("G09","pt-dgt-macedo-braganca-anonymous-strip.json",24,48),
  ("G10","pt-dgt-g10-g08-g07-interface-anonymous-strip.json",2,4)
)

def summarize_all(report_dir):
    report_dir=Path(report_dir)
    product_positions={collection:{} for collection in COLLECTIONS}
    sources=[]
    per_source_position_ids={}
    bbox_conflicts=[]
    for label,filename,windows,queries in SOURCE_SPECS:
        path=report_dir/filename
        content=path.read_bytes()
        doc=json.loads(content)
        requests=doc.get("requests") if label=="E01-E06" else doc.get("responses")
        if not isinstance(requests,list) or len(requests)!=queries:
            raise ValueError(f"incomplete_{label}_source_query_receipt")
        if label=="E01-E06":
            if doc.get("request_count")!=queries or doc.get("window_count")!=windows:
                raise ValueError("first_scan_missing_expected_windows")
        else:
            if not doc.get("queries_all_complete") or doc.get("grid_window_count")!=windows:
                raise ValueError(f"STAC_{label}_partial_query_receipt")
        source_set={c:set() for c in COLLECTIONS}
        query_ids=set()
        for record in requests:
            c=record.get("collection")
            if c not in COLLECTIONS:
                raise ValueError("unknown_DGT_collection")
            if (label=="E01-E06" and (record.get("http_status")!=200 or
                record.get("status")!="metadata_returned_one_page" or record.get("has_next_page"))):
                raise ValueError("incomplete_first_DGT_STAC_scan")
            if (label!="E01-E06" and (record.get("status")!="metadata_complete_single_page"
                or record.get("http_status")!=200 or record.get("has_next_page"))):
                raise ValueError("incomplete_subsequent_DGT_STAC_scan")
            identity=(record.get("box_id") or record.get("window_id"),c)
            if identity in query_ids:
                raise ValueError("duplicated_catalogue_STAC_query")
            query_ids.add(identity)
            rows=record.get("footprints")
            if not isinstance(rows,list) or not isinstance(record.get("metadata_footprint_count"),int):
                raise ValueError("missing_safe_DGT_source_metadata_footprints")
            if len(rows)!=record["metadata_footprint_count"]:
                raise ValueError("STAC_safe_footprint_count_disagrees")
            for item in rows:
                ident=item.get("tile_id")
                bbox=item.get("bbox_wgs84")
                if not isinstance(ident,str) or not ident.startswith(c+"-"):
                    raise ValueError("bad_source_product_id_prefix")
                if not isinstance(bbox,list) or len(bbox)!=4:
                    raise ValueError("missing_source_bbox_proxy")
                west,south,east,north=bbox
                if not all(isinstance(a,(int,float)) for a in bbox):
                    raise ValueError("source_bbox_not_numeric")
                if not (-11<=west<east<=-5 and 36<=south<north<=43):
                    raise ValueError("DGT_catalogue_bbox_outside_P_T")
                prior=product_positions[c].get(ident)
                if prior and prior["bbox_wgs84"]!=bbox:
                    bbox_conflicts.append({"collection":c,"tile_id":ident,"first_source":prior["first_source"],"next_source":label})
                source_set[c].add(ident)
                if prior is None:
                    product_positions[c][ident]={"bbox_wgs84":bbox,"first_source":label}
        if len(query_ids)!=queries:
            raise ValueError("unexpected_STAC_query_pair_count")
        count={k:len(v) for k,v in source_set.items()}
        if count[COLLECTIONS[0]]!=count[COLLECTIONS[1]]:
            raise ValueError("unpaired_product_counts_within_scan")
        per_source_position_ids[label]=source_set
        sources.append({"name":label,"file":filename,"source_file_sha256":hashlib.sha256(content).hexdigest(),
                        "verified_window_count":windows,"complete_query_count":queries,
                        "unique_candidates_by_collection":count,
                        "metadata_only":True})
    if bbox_conflicts:
        raise ValueError("same_DGT_source_product_ID_conflicting_bbox_proxies")
    matching={}
    for collection in COLLECTIONS:
        matching[collection]={id.removeprefix(collection+"-"):v for id,v in product_positions[collection].items()}
    if set(matching[COLLECTIONS[0]])!=set(matching[COLLECTIONS[1]]):
        raise ValueError("pairing_not_exact_across_collections")
    mismatched=[key for key,record in matching[COLLECTIONS[0]].items()
                if record["bbox_wgs84"]!=matching[COLLECTIONS[1]][key]["bbox_wgs84"]]
    # Producer's northern-border metadata has some small, REAL 2m/50cm
    # bbox differences. Report every one; never silently coerce polygons
    # to identical geometry or infer DTM pixel gaps from bbox disagreement.
    mismatch_details=[]
    for key in sorted(mismatched):
        b2=matching["MDT-2m"][key]["bbox_wgs84"]
        b05=matching["MDT-50cm"][key]["bbox_wgs84"]
        import math
        center_lat=(b2[1]+b2[3]+b05[1]+b05[3])/4
        scales=(111195*math.cos(math.radians(center_lat)),111195)
        max_shift=max(abs(b2[i]-b05[i])*scales[i%2] for i in range(4))
        mismatch_details.append({"source_tile_suffix":key,
            "bbox_mdt2m_wgs84":b2,"bbox_mdt50cm_wgs84":b05,
            "max_bbox_edge_displacement_approx_m":round(max_shift,3)})
    old_three=set().union(*(per_source_position_ids[name]["MDT-2m"]
                           for name in ("E01-E06","G07","G08")))
    g09=per_source_position_ids["G09"]["MDT-2m"]
    g10=per_source_position_ids["G10"]["MDT-2m"]
    prior_four=set().union(*(per_source_position_ids[name]["MDT-2m"]
                           for name in ("E01-E06","G07","G08","G09")))
    g10_cross_resolution_exceptions=sum(
        matching["MDT-2m"][v.removeprefix("MDT-2m-")]["bbox_wgs84"] !=
        matching["MDT-50cm"][v.removeprefix("MDT-2m-")]["bbox_wgs84"] for v in g10
    )
    overlaps=[]
    for i,(a,_,_,_) in enumerate(SOURCE_SPECS):
        for b,_,_,_ in SOURCE_SPECS[i+1:]:
            shared=per_source_position_ids[a][COLLECTIONS[0]] & per_source_position_ids[b][COLLECTIONS[0]]
            overlaps.append({"source_a":a,"source_b":b,"shared_DGT_product_positions":len(shared)})
    return {
        "mission":"MN-GEO-RAIL-001","worker":"W2",
        "stage":"DGT_five_screen_metadata_deduplication_with_cross_resolution_bbox_exceptions",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "producer":"Direção-Geral do Território, official anonymous STAC",
        "source_screens":sources,
        "total_screen_windows":sum(s[2] for s in SOURCE_SPECS),
        "total_complete_STAC_requests":sum(s[3] for s in SOURCE_SPECS),
        "distinct_candidate_product_positions":len(matching[COLLECTIONS[0]]),
        "unique_DGT_product_IDs_by_collection":{c:len(product_positions[c]) for c in COLLECTIONS},
        "identical_2m_and_50cm_producer_id_suffix_pair_count":len(matching[COLLECTIONS[0]]),
        "identical_pair_bbox_proxy_count":len(matching[COLLECTIONS[0]])-len(mismatch_details),
        "matched_tile_suffixes_both_resolutions":len(matching[COLLECTIONS[0]]),
        "bbox_exceptions_2m_vs_50cm":len(mismatch_details),
        "bbox_exception_records":mismatch_details,
        "G09_positions_new_vs_prior_three_screens":len(g09-old_three),
        "G09_positions_overlapping_prior_three_screens":len(g09 & old_three),
        "prior_three_screen_positions":len(old_three),
        "prior_four_screen_positions":len(prior_four),
        "G10_interface_review_bbox_wgs84":[-7.85,41.20,-7.75,41.40],
        "G10_metadata_positions_per_resolution":len(g10),
        "G10_new_positions_vs_four_screens":len(g10-prior_four),
        "G10_overlapping_positions_vs_four_screens":len(g10&prior_four),
        "G10_shared_position_IDs_with_G08":len(g10&per_source_position_ids["G08"]["MDT-2m"]),
        "G10_shared_position_IDs_with_G07":len(g10&per_source_position_ids["G07"]["MDT-2m"]),
        "G10_2m_50cm_producer_bbox_exceptions":g10_cross_resolution_exceptions,
        "G10_no_unqueried_longitude_between_G08_G07_review_boxes":True,
        "G10_does_not_prove_raster_pixel_connectivity":True,
        "bbox_disagreement_IS_not_proven_native_pixel_void":True,
        "bbox_disagreement_across_screens_count":len(bbox_conflicts),
        "per_screen_ID_overlaps":overlaps,
        "catalogue_rectangles_are_NOT_validated_native_pixel_footprints":True,
        "sample_windows_not_all_Porto_Zamora_corridor":True,
        "not_a_contiguous_native_raster_mosaic":True,
        "native_raster_bytes_downloaded_in_these_screens":0,
        "entire_regional_native_DTM_coverage_verified":False,
        "vertical_datum_crossborder_harmonized":False,
        "Fxx_canonical_accepted":False,
        "Site_publication_authorized":False,
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report-dir",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    x=p.parse_args()
    summary=summarize_all(x.report_dir)
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ("total_screen_windows",
        "total_complete_STAC_requests","distinct_candidate_product_positions",
        "identical_pair_bbox_proxy_count","bbox_exceptions_2m_vs_50cm",
        "G09_positions_new_vs_prior_three_screens","G10_new_positions_vs_four_screens")},ensure_ascii=False))

if __name__=="__main__":
    main()
