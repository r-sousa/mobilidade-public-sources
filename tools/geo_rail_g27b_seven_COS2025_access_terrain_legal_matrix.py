#!/usr/bin/env python3
"""G27B observational seven station-sector matrix, never legal accept/reject.
Combine exact original COS2025 source area inventory G26C with G25 measured
OSRM source road-snap time and G23B DGT2m terrain screens passed through G25.
Do not collapse different study headings into a fictitious constructible track.
REN/RAN/PDM/SRUP/water/heritage UNKNOWN pending official vector and legal docs.
"""
from __future__ import annotations
import argparse,hashlib,json,csv
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict

G26C_SHA="caf506f6bd114fe200f3f95d29951e97b8c1d9e18c8c654fa64c4ae3f75e81e4"
G25_SHA="be35181c882c2f6ede4d07f7e0a68b084bb6247c54a7da0d1d566a66f844dffd"
LEGAL=("REN","RAN","PDM_in_force_and_regulation","CRUS_harmonized_context_NOT_legal",
       "other_SRUP","public_water_domain","road_access_legal_connectivity",
       "land_ownership","ecological_network_and_natura","cultural_heritage")
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build(a,b):
 if (a.get("seven_distinct_source_study_sites")!=7 or a.get("Fxx_accepted") or
  a.get("Site_authorized") or b.get("two_compulsory_cities")!=["Vila Real","Bragança"] or
  b.get("Fxx_accepted") or b.get("Site_authorized")):
  raise ValueError("G27B_exact_previous_source_gates_not_satisfied")
 by_xy=defaultdict(list)
 for z in b["source_shortlisted_road_reference_route_cases"]:
  key=tuple(round(float(x),2) for x in z["original_study_EPSG3763_XY"])
  by_xy[key].append(z)
 result=[]
 for rec in a["original_COS2025_local_7_site_summary"]:
  key=tuple(round(float(x),2) for x in rec["research_EPSG3763_XY"])
  rows=by_xy.pop(key,None)
  if not rows:raise ValueError("G27B_COS2025_site_missing_G25_real_road_source")
  access={x["OSRM_2026_city_to_snapped_road_reference_time_min"] for x in rows}
  snap={x["OSRM_destination_study_point_to_nearest_routable_road_m"] for x in rows}
  if len(access)!=1 or len(snap)!=1:raise ValueError("G27B_same_source_coordinate_road_snap_inconsistent")
  land={x["description"]:x["share_pct"] for x in rec["original_COS2025_2025_n1_land_use_ha"]}
  artificial=round(land.get("Territórios artificializados",0),2)
  terr=[{"family":x["source_corridor_family"],"role":x["source_G24_screening_role"],
         "station_ground_p90_m":x["G24_original_DGT2m_station_p90_m"],
         "approach_ground_p90_m":x["G24_original_DGT2m_approach_p90_m"],
         "g10_grid_distance_m":x["G24_original_grid_distance_m"],
         "g10_source_chord_heading_mismatch_deg":x["G24_local_source_grid_heading_mismatch_deg"],
         "source_straight_tangent_axis_deg":x["G24_source_station_straight_heading_deg"]}
    for x in rows]
  result.append({"city":rec["mandatory_market"],"original_study_xy_EPSG3763":list(key),
    "cos2025_400m_radius_original_polygon_count":rec["producer_COS_polygon_count"],
    "cos2025_original_valid_area_fraction":rec["COS2025_original_covered_fraction"],
    "cos2025_land_use_n1_shares_pct":land,
    "cos2025_artificialized_area_percent_2025_observation_NOT_legal_constraint":artificial,
    "cos2025_study_circle_area_ha":rec["original_2025_COS_study_circle_area_ha"],
    "OSRM_city_center_to_nearest_road_snap_minutes_NOT_station_access":list(access)[0],
    "OSRM_dgt_study_coordinate_to_nearest_routable_road_m_NOT_legal_access":list(snap)[0],
    "G25_study_orientation_specific_original_2m_terrain_observations_NOT_design":terr,
    "legal_or_environmental_constraint_status":{x:"UNKNOWN_NOT_EXAMINED" for x in LEGAL},
    "ground_is_not_translated_to_station_cost_or_viability":True,
    "COS_level1_artificial_is_not_hard_stop_or_suitable_land":True})
 if by_xy:raise ValueError("G27B_G25_source_study_area_not_matched_to_COS2025")
 if len(result)!=7:raise ValueError("G27B_not_seven_studies")
 return result
def main():
 p=argparse.ArgumentParser()
 for x in ("g26c","g25","json","csv","markdown"):p.add_argument("--"+x,type=Path,required=True)
 z=p.parse_args()
 if sha(z.g26c)!=G26C_SHA or sha(z.g25)!=G25_SHA:raise ValueError("G27B_source_release_hash_drift")
 q=build(json.loads(z.g26c.read_text()),json.loads(z.g25.read_text()))
 doc={"mission":"MN-GEO-RAIL-001",
 "stage":"G27B_official_COS2025_plus_original_DGT2m_OSRM_seven_source_study_sector_screen_PRELEGAL",
 "utc":datetime.now(timezone.utc).isoformat(),
 "verified_source_sha256":{"G26C":G26C_SHA,"G25":G25_SHA},
 "primary_source_reference_year_COS":2025,"measured_road_source_OSRM_without_traffic":2026,
 "seven_mandatory_city_station_research_sector_dossiers":q,
 "legal_constraint_not_verified_must_not_mark_legal_permitted":True,
 "DGT_COS2025_landuse_not_pdm_ren_ran_or_land_ownership":True,
 "ground_p90_per_heading_math_not_actual_earthworks":True,
 "no_real_rail_geometry_CAPEX_bus_access_or_passenger_demand":True,
 "recommended_next_source_task":"G27C SNIT WFS REN RAN and CRUS: confirm published DR legal boundary and official PDM before elimination",
 "no_new_DGT_2m_terrain_source_acquisition":True,
 "mandatory_markets":["Vila Real","Bragança"],"Sanabria_excluded":True,
 "Fxx_accepted":False,"Site_authorized":False}
 z.json.parent.mkdir(parents=True,exist_ok=True);z.json.write_text(json.dumps(doc,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
 cols=("city","source_EPSG3763_XY","COS2025_400m_artificialized_pct","COS2025_polygons",
       "OSRM_road_snap_city_min","nearby_road_distance_m","legal_RAN","legal_REN","PDM","legal_SRUP")
 with z.csv.open("w",encoding="utf-8",newline="") as f:
  w=csv.writer(f);w.writerow(cols)
  for z0 in q:
   w.writerow((z0["city"],str(z0["original_study_xy_EPSG3763"]),
      z0["cos2025_artificialized_area_percent_2025_observation_NOT_legal_constraint"],
      z0["cos2025_400m_radius_original_polygon_count"],
      z0["OSRM_city_center_to_nearest_road_snap_minutes_NOT_station_access"],
      z0["OSRM_dgt_study_coordinate_to_nearest_routable_road_m_NOT_legal_access"],
      "UNKNOWN","UNKNOWN","UNKNOWN","UNKNOWN"))
 lines=["# G27B — Matriz preliminar de sete áreas de estudo, sem validação jurídica",
  "","Dados reais já conservados: DGT COS2025 original, sete círculos de 400 m, e G25 tempos de referência rodoviária ao ponto de estrada próximo. Relevo 2 m G22–G23 por orientação. **Nada nesta matriz confirma viabilidade de estação, classificação legal de parcela ou direito de acesso.**",
  "","| Mercado | Coordenadas PT-TM06 | Artificializado COS2025 (%) | Tempo viário de referência (min) | REN | RAN | PDM | SRUP |",
  "|---|---|---:|---:|---|---|---|---|"]
 for t in q:
  lines.append(f"| {t['city']} | {t['original_study_xy_EPSG3763']} | {t['cos2025_artificialized_area_percent_2025_observation_NOT_legal_constraint']} | {t['OSRM_city_center_to_nearest_road_snap_minutes_NOT_station_access']} | Por verificar | Por verificar | Por verificar | Por verificar |")
 lines+=["","## Próximas verificações necessárias",
 "- Cruzar polígonos REN e RAN atuais, separando alterações publicadas em DR de cartografia apenas indicativa.",
 "- Ler plantas de condicionantes e regulamentos PDM municipais em vigor; CRUS é harmonização de enquadramento, não título habilitante.",
 "- Identificar domínio hídrico, linhas de água e atravessamentos, património e demais SRUP, áreas classificadas.",
 "- Inventariar terrenos efetivamente disponíveis e entradas viárias legais; cruzar com faixas ferroviárias contínuas ainda não projetadas.",
 "","Sem novas aquisições MDT, sem Fxx ou Site."]
 z.markdown.parent.mkdir(parents=True,exist_ok=True);z.markdown.write_text("\n".join(lines))
 print("G27B_SEVEN="+json.dumps([{"city":x["city"],"xy":x["original_study_xy_EPSG3763"],"artificial_pct":x["cos2025_artificialized_area_percent_2025_observation_NOT_legal_constraint"],"road_minutes":x["OSRM_city_center_to_nearest_road_snap_minutes_NOT_station_access"],"legal":"UNKNOWN"} for x in q],ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
