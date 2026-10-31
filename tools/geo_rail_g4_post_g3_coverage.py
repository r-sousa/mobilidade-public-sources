#!/usr/bin/env python3
"""G4: inspect actual public DGT producer-original QA receipts and G3 source-only lattice.

This is a source-cover/NoData inventory, NOT an engineering alignment or station
proposal. No DGT credentials, TIFFs, source signed URLs or new downloads.
"""
from __future__ import annotations
import argparse,collections,json
from pathlib import Path
from geo_rail_g3_native80 import load_review, BATCHES, PRIOR_MIRANDELA_IDS, REVIEWED_DUPLICATE_BLOCK

M2_PIXELS_PER_SQUARE_KM=250_000
EXPECTED={"vila_real":(28,74),"braganca":(20,31_377),"regional":(28,0)}
ALLOWED_LOCS=("Vila Real","Bragança")

def cell(box):
    if len(box)!=4 or box[2]-box[0]!=2000 or box[3]-box[1]!=2000:
        raise ValueError("study_sector_not_a_real_2km_square")
    if box[0]%2000 or box[1]%2000:
        raise ValueError("study_sector_unaligned")
    return (int(box[0]),int(box[1]))

def summarize(review,receipts,b1):
    groups=load_review(review) # also checks original-source SHA256 and all 76 producer IDs
    expected={g["group_id"]:g for g in groups}
    g3_cells={}; all_tiles=set();batch_q={}
    for batch in BATCHES:
        doc=receipts[batch]
        target_count, expected_void=EXPECTED[batch]
        if doc.get("batch")!=batch or doc.get("real_original_DGT2m_tile_count")!=target_count:
            raise ValueError("incorrect_real_source_receipt_for_"+batch)
        if doc.get("review_original_source_SHA256")!="ab001fb17ba359d939294b505bc199d459d474095f255f17099c1cdaafd57d9c":
            raise ValueError("source_selection_receipt_not_pinned")
        if doc.get("Sanabria_excluded") is not True or doc.get("Fxx_accepted") or doc.get("Site_authorized"):
            raise ValueError("incorrect_source_provenance_or_scope")
        ids={o["id"]:o for o in doc["native_originals"]}
        these={g["group_id"]:g for g in groups if g["batch"]==batch}
        if len(ids)!=target_count or len(doc["mosaics"])!=target_count//4:
            raise ValueError("wrong_actual_original_tile_or_mosaic_counts")
        if any(i in all_tiles or i in PRIOR_MIRANDELA_IDS for i in ids):
            raise ValueError("previous_Mirandela_or_G3_duplicate_reacquired")
        all_tiles.update(ids)
        valid=0; void=0
        for i,src in ids.items():
            qa=src["native_original_QA"]
            if src["sha256"] is None or len(src["sha256"])!=64 or qa["native_original_source_tile_id"]!=i:
                raise ValueError("missing_original_source_sha256_or_bad_tile_id")
            n=qa["real_valid_ground_pixels"];missing=qa["source_nodata_pixels"]
            if not isinstance(n,int) or not isinstance(missing,int) or n+missing!=250_000:
                raise ValueError("native_source_pixel_mask_inconsistent")
            valid+=n;void+=missing
        if void!=expected_void or valid!=target_count*M2_PIXELS_PER_SQUARE_KM-void:
            raise ValueError("unexpected_original_DGT_source_NoData: "+batch)
        if doc["valid_original_ground_pixels"]!=valid:
            raise ValueError("receipt_pixel_sum_inconsistent")
        for mosaic in doc["mosaics"]:
            gid=mosaic["group_id"]
            if gid not in these:raise ValueError("mosaic_outside_reviewed_2km_sectors")
            original=these[gid]
            pos=cell(original["grid_epsg3763"])
            if pos in g3_cells:raise ValueError("G3_duplicate_source_mosaic_cell")
            proof=mosaic["pixel_exact_QA"]
            if proof["pixel_exact_native_sources"]!=4 or len(mosaic["seams"])!=4:
                raise ValueError("not_four_source_native_verified_mosaic")
            if any(s["pairs_total"]!=500 for s in mosaic["seams"]):
                raise ValueError("invalid_edge_QA")
            original_ids={o["id"] for o in doc["native_originals"]}
            if not set(original["tile_ids"])<=original_ids:
                raise ValueError("reviewed_tile_ids_not_in_actual_source_receipt")
            g3_cells[pos]={"batch":batch,"grid_epsg3763":list(original["grid_epsg3763"]),
                          "valid_cell_count":sum(ids[i]["native_original_QA"]["real_valid_ground_pixels"] for i in original["tile_ids"]),
                          "source_NoData_cell_count":sum(ids[i]["native_original_QA"]["source_nodata_pixels"] for i in original["tile_ids"])}
        batch_q[batch]={"source_original_tile_count":target_count,"grid_footprint_km2":target_count,
                        "valid_ground_2m_pixel_count":valid,"native_NoData_2m_pixel_count":void,
                        "valid_ground_area_km2":round(valid*4/1_000_000,6)}
    if len(all_tiles)!=76 or len(g3_cells)!=19:
        raise ValueError("not_all_76_real_G3_producer_originals_accounted_for")
    if b1.get("original_source_GeoTIFF_count")!=32 or b1.get("original_native_ground_2m_pixels_valid")!=8_000_000 or b1.get("original_native_ground_no_data_pixels")!=0:
        raise ValueError("B1_32_original_verified_ground_receipt_missing")
    if b1.get("mandatory_service_areas")!=list(ALLOWED_LOCS) or b1.get("sanabria_excluded") is not True:
        raise ValueError("B1_mandatory_cities_not_preserved")
    b1_cells={cell(s["bbox_epsg3763"]) for s in b1["sectors"]}
    if len(b1_cells)!=8 or b1_cells&set(g3_cells):
        raise ValueError("previous_B1_and_G3_2km_coverage_not_distinct")
    mir=cell(REVIEWED_DUPLICATE_BLOCK)
    if mir in b1_cells or mir in g3_cells:raise ValueError("Mirandela_overlap_not_excluded")
    observed=b1_cells|set(g3_cells)|{mir}
    # Only the documented 2x2km Mirandela previously held block is representable
    # as a whole 2km cell here; the other 9 original 1km2 tiles remain separate.
    rows=[];uncovered=collections.Counter()
    for link in review.read_text() and json.loads(review.read_text())["links"]:
        paths=[]
        for p in link["solutions"]:
            route=[tuple(q) for q in p["route_sector_cells"]]
            if not route:
                paths.append({"mode":p["mode"],"status":p["status"]});continue
            present=[q for q in route if q in observed]
            missing=[q for q in route if q not in observed]
            for pos in missing:uncovered[pos]+=1
            paths.append({"mode":p["mode"],"source_lattice_2km_cells":len(route),
                          "covered_by_native_DGT2m_whole_2km_sector":len(present),
                          "missing_whole_2km_source_sector_count":len(missing),
                          "covered_fraction_of_lattice_sectors":round(len(present)/len(route),4),
                          "missing_sector_positions_epsg3763":[list(x) for x in missing],
                          "NOT_a_railway_route":True})
        rows.append({"link":link["link"],"path_variants":paths})
    return {"mission":"MN-GEO-RAIL-001","stage":"G4_post_G3_reconciled_real_DGT_native_2m_coverage",
      "source_only_no_DGT_secrets":True,"mandatory_service_cities":list(ALLOWED_LOCS),
      "central_stations_required":False,"Sanabria_excluded":True,
      "DGT_2m_total_distinct_original_tile_footprint_km2":121,
      "DGT_2m_prior_Mirandela_original_tiles_km2":13,
      "DGT_2m_prior_B1_original_tiles_km2":32,"G3_original_tiles_km2":76,
      "G3":batch_q,"G3_total_native_NoData_2m_pixels":sum(z["native_NoData_2m_pixel_count"] for z in batch_q.values()),
      "fully_located_2km_sectors_G3_and_B1_plus_Mirandela":28,
      "verified_full_2km_ground_sector_footprint_km2":112,
      "remaining_earlier_1km2_originals_not_claimed_as_full_2km_sectors":9,
      "G3_sector_details":list(g3_cells.values()),
      "five_reviewed_original_DSM_OSM_catalogue_lattice_links":rows,
      "missing_sector_ranked_by_number_of_exploratory_variants":[{"grid_2km_SW_epsg3763":list(k),"variants":v}
          for k,v in sorted(uncovered.items(),key=lambda x:(-x[1],x[0]))],
      "all_missing_sectors_are_source_metadata_candidates_only":True,
      "native_ground_2m_full_Porto_Zamora_rail_corridor_continuity_proven":False,
      "cross_border_vertical_accuracy_calibrated":False,
      "real_road_network_station_access_minutes_established":False,
      "railway_geometry_grade_curve_radius_costs_established":False,
      "Fxx_accepted":False,"Site_authorized":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--review",type=Path,required=True)
    parser.add_argument("--b1",type=Path,required=True)
    for key in EXPECTED:parser.add_argument("--"+key.replace("_","-"),type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    a=parser.parse_args()
    files={k:getattr(a,k.replace("-","_")) for k in EXPECTED}
    result=summarize(a.review,{k:json.loads(p.read_text()) for k,p in files.items()},json.loads(a.b1.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":"SOURCE_AUDITED_G4_RECONCILIATION","native_DGT2m_footprint_km2":121,
       "G3_void_pixels":result["G3_total_native_NoData_2m_pixels"],
       "measured_lattice_links":len(result["five_reviewed_original_DSM_OSM_catalogue_lattice_links"]),
       "missing_2km_sector_candidates":len(result["missing_sector_ranked_by_number_of_exploratory_variants"])},ensure_ascii=False))
if __name__=="__main__":main()
