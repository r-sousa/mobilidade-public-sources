#!/usr/bin/env python3
"""B1: select reviewed DGT original 2m source groups only AFTER real road+DSM screen.

All four exact 1km DGT official STAC product IDs must exist for each 2x2km
research sector. Actual OSM ways and actual Copernicus DSM are secondary
acquisition screens, not railway alignment or accessible station designs.
Vila Real and Bragança compulsory, no Sanabria.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from geo_rail_pt_b1_dgt_review_grids import inventory, SITES

ROAD_SHA256="e54cbbd0786c4eac5024dd0d9652b16b51abfebb4326ebe0ed9882c4a829d215"
def join(report_dir,road_source):
    if hashlib.sha256(road_source.read_bytes()).hexdigest()!=ROAD_SHA256:
        raise ValueError("OSM_road_and_DSM_source_receipt_changed")
    roads=json.loads(road_source.read_text())
    if (roads.get("mandatory_service_areas")!=["Vila Real","Bragança"]
        or roads.get("road_proximity_screen_by_city")!={"Vila_Real":65,"Braganca":31}
        or not roads["Sanabria_excluded"] or roads.get("road_ways_total")!=2801
        or roads.get("sectors_total")!=222):
        raise ValueError("wrong_source_road_DSM_review_receipt")
    catalog,proofs=inventory(report_dir)
    valid=[]
    missing=[]
    for a in roads["research_sectors"]:
        if not a["inside_peripheral_road_proximity_discovery_threshold"]:continue
        city="Vila Real" if a["city"]=="Vila_Real" else "Bragança"
        (x0,y0,x1,y1)=a["sector_EPSG3763"]
        if (x1-x0,y1-y0)!=(2000,2000) or x0%1000 or y0%1000:
            raise ValueError("not_a_source_aligned_2x2km_grid")
        col=x0//1000+200
        row=y0//1000+301
        tiles=[catalog.get((col+dx,row+dy)) for dy in (0,1) for dx in (0,1)]
        if not all(tiles):
            missing.append({"city":city,"sector_id":a["id"],
                            "reason":"official_STAC_2m_four_original_product_IDs_not_fully_sourced"})
            continue
        lon,lat=SITES[city]
        left,bottom,right,top=a["sector_WGS84_bbox_proxy"]
        mx,my=(left+right)/2,(bottom+top)/2
        dx=(mx-lon)*111.195*math.cos(math.radians(lat))
        dy=(my-lat)*111.195
        quadrant=("E" if dx>0 else "W") if abs(dx)>abs(dy) else ("N" if dy>0 else "S")
        valid.append({
            "city":city,"quadrant":quadrant,
            "sector_id":a["id"],
            "research_sector_grid_epsg3763":[x0,y0,x1,y1],
            "official_DGT_original_MDT2m_tile_IDs":[z["id"] for z in tiles],
            "official_source_vintages":[{"id":z["id"],"source_screen":z["source"]} for z in tiles],
            "city_centre_Euclidean_distance_km":a["city_straightline_distance_km"],
            "mapped_major_local_road_Euclidean_distance_m":a["minimum_Euclidean_distance_to_mapped_local_major_road_m"],
            "mapped_A4_like_motorway_trunk_Euclidean_distance_m":a["minimum_Euclidean_distance_to_motorway_or_trunk_m"],
            "actual_GLO30_DSM_surface_relief_P95_minus_P05_m":a["DSM"]["robust_surface_relief_P95_minus_P05_m"],
            "original_DGT_native_2m_rasters_downloaded_for_this_sector":False,
            "station_road_travel_time_or_access_proven":False,
            "railway_track_terrain_suitability_proven":False
        })
    chosen=[]
    for city in SITES:
        used=set()
        for quadrant in ("W","E","N","S"):
            candidates=sorted([g for g in valid if g["city"]==city and g["quadrant"]==quadrant],
              key=lambda g:(g["actual_GLO30_DSM_surface_relief_P95_minus_P05_m"],
               g["mapped_major_local_road_Euclidean_distance_m"],
               g["mapped_A4_like_motorway_trunk_Euclidean_distance_m"]))
            for g in candidates:
                if not set(g["official_DGT_original_MDT2m_tile_IDs"])&used:
                    chosen.append(g)
                    used.update(g["official_DGT_original_MDT2m_tile_IDs"])
                    break
    return {
      "mission":"MN-GEO-RAIL-001","stage":"B1_actual_OSM_road_DSM_and_official_DGT_MDT2m_preacquisition_join",
      "binding_transport_requirement":["Vila Real","Bragança"],
      "city_centre_stations_required":False,
      "Sanabria_excluded_from_active_scope":True,
      "sources":{
        "original_source_5_DGT_catalogues_SHA256":proofs,
        "OSM_road_plus_real_GLO30_DSM_source_receipt_SHA256":ROAD_SHA256,
        "source_GLO30_DSM_SHA256":roads["base_DSM_original_release_SHA256"],
        "source_road_geojson":"https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-b1-a4-mandatory-city-roads-source-preacceptance-41200362181",
        "DGT_original_source_assets_downloaded_now":False
      },
      "real_road_source_ways":roads["road_ways_total"],
      "source_road_screened_sectors":sum(roads["road_proximity_screen_by_city"].values()),
      "fully_catalogued_candidate_2km_DGT_grids":len(valid),
      "incomplete_official_catalogue_grids_after_road_screen":len(missing),
      "missing_catalogue_grid_examples":missing[:20],
      "candidate_groups_per_city":{s:sum(z["city"]==s for z in valid) for s in SITES},
      "preselected_review_groups":chosen,
      "preselected_groups_per_city":{s:sum(z["city"]==s for z in chosen) for s in SITES},
      "preselected_original_DGT_1km_tile_ID_count":len(set(i for z in chosen for i in z["official_DGT_original_MDT2m_tile_IDs"])),
      "actual_road_driving_time_to_candidate_station_verified":False,
      "actual_DGT_2m_ground_pixel_continuity_in_preselected_groups_verified":False,
      "this_does_not_rank_railway_alignment":True,
      "next_safe_acquisition_requires_workflow_dispatch_on_protected_main_dgt_cdd":True,
      "Fxx_accepted":False,"Site_authorized":False
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dgt-reports",required=True,type=Path)
    p.add_argument("--road-review",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    r=join(a.dgt_reports,a.road_review)
    if any(r["candidate_groups_per_city"][x]<2 for x in SITES):raise ValueError("insufficient_complete_DGT_2m_groups_for_compulsory_city")
    if any(r["preselected_groups_per_city"][x]<2 for x in SITES):raise ValueError("unbalanced_DGT_2m_peripheral_preselection")
    if r["preselected_original_DGT_1km_tile_ID_count"]>32:raise ValueError("preacquisition_budget_excessive")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"REAL_ROADS_DSM_OFFICIAL_DGT_SOURCE_INTERSECTION_PASS",
        "eligible_2km_source_groups":r["fully_catalogued_candidate_2km_DGT_grids"],
        "preselected_source_groups":r["preselected_groups_per_city"],
        "exact_native_DGT_1km_tiles_reviewed":r["preselected_original_DGT_1km_tile_ID_count"],
        "native_DGT_new_bytes_acquired":0},ensure_ascii=False))
if __name__=="__main__":main()
