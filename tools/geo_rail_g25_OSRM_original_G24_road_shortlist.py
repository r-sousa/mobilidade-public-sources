#!/usr/bin/env python3
"""G25 source-targeted OSRM reference road access remeasure for NEW G24 sites.

ONLY two low-rate OSM public demo table calls, one per compulsory city.
Each G24 shortlisted shifted source-station reference location is routed
from the already grounded G11 city reference to a ROAD-SNAPPED destination.
No legal station road entrance, route to a platform, railway engineering,
trains, bus/GTFS, passenger demand, tolls or congestion is inferred.
No lost/missing sample imputation: absent or >600m road-snap stays null.
"""
from __future__ import annotations
import argparse,hashlib,json,time
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone
from pyproj import Transformer
from geo_rail_g11_urban_service import CITY,_read_osrm,OSRM_SNAP_MAX_M

G24_SHA="19c165db201356aa497ec3915bb2794e8c51e6eff596fc37a9a310d77b30c303"
MARKETS=("Vila_Real","Braganca")
MAX_CITY_DESTINATIONS=32
OSRM_PUBLIC_REQUEST_BUDGET=2
SLEEP_SECONDS=1.5

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(2**20),b""):h.update(chunk)
 return h.hexdigest()

def samples(j):
 rows=j["13_groups_2to3_source_ground_vs_grid_geometry_reference_shortlist"]
 if not 13<=len(rows)<=39:raise ValueError("G25_source_shortlist_size_unexpected")
 if len(j["351_original_source_geometry_station_tangent_screening_cases"])!=351 or j["Fxx_accepted"] or j["Site_authorized"]:
  raise ValueError("G25_original_source_G24_line_geometry_invalid")
 by_city=defaultdict(dict)
 for record in rows:
  city=record["mandatory_market"]
  if city not in MARKETS:raise ValueError("G25_optional_city_route_not_requested")
  xy=tuple(record["candidate_original_DGT_study_EPSG3763_XY"])
  # The SAME physical point can be shared across G10 families/heading. True
  # road travel for that point should be sampled only once per city.
  by_city[city].setdefault(xy,[]).append(record)
 if any(len(by_city[c])>MAX_CITY_DESTINATIONS for c in MARKETS):
  raise ValueError("G25_demo_rate_limit_or_overlong_table")
 if set(by_city)!=set(MARKETS):raise ValueError("two_mandatory_cities_missing")
 return rows,by_city

def run(src,outjson,report):
 if sha(src)!=G24_SHA:raise ValueError("G24_original_main_source_file_SHA_changed")
 origin=json.loads(src.read_text())
 rows,by_city=samples(origin)
 to_wgs=Transformer.from_crs(3763,4326,always_xy=True)
 results=[];receipts=[]
 for n,city in enumerate(MARKETS):
  if n:time.sleep(SLEEP_SECONDS)
  points=list(by_city[city])
  geo=[tuple(to_wgs.transform(*p)) for p in points]
  raw=_read_osrm(city,geo)
  if len(raw["destinations"])!=len(points):
   raise ValueError("G25_actual_osrm_source_road_destinations_missing")
  receipts.append({"city":city,"original_source_OSRM_response_sha256":raw["response_SHA256"],
   "OSRM_public_route_table_observed_utc":raw["observed_utc"],
   "unique_routing_destinations":len(points),
   "city_reference_origin_snap_m":round(raw["waypoint_source_snap_m"],2),
   "provider":"OSRM public OSM routing test, car no traffic",
   "full_original_OSRM_network_routing_response_NOT_preserved":True,
   "original_reference_city_coordinates_WGS84":[CITY[city]["lon"],CITY[city]["lat"]],
   "single_OSRM_demo_table_query_per_city":True})
  city_snap_good=raw["waypoint_source_snap_m"]<=OSRM_SNAP_MAX_M
  for key,network in zip(points,raw["destinations"]):
   destination_valid=network["snap_distance_m"]<=OSRM_SNAP_MAX_M
   travel_ok=city_snap_good and destination_valid and network["network_duration_minutes"] is not None and network["network_distance_km"] is not None
   for item in by_city[city][key]:
    results.append({"mandatory_market":city,
      "source_G24_reference_seed":item["G23B_study_seed_id"],
      "source_corridor_family":item["source_research_family"],
      "source_G24_screening_role":item["screening_role"],
      "original_study_EPSG3763_XY":list(key),
      "WGS84_road_reference_point_not_station":list(to_wgs.transform(*key)),
      "G24_original_DGT2m_station_p90_m":item["G23B_station_vertical_p90_DGT2m_m"],
      "G24_original_DGT2m_approach_p90_m":item["G23B_approach_18permille_vertical_p90_DGT2m_m"],
      "G24_original_grid_distance_m":item["distance_to_original_G10_2km_grid_route_m"],
      "G24_local_source_grid_heading_mismatch_deg":item["hypothetical_station_straight_heading_mismatch_to_3km_source_grid_chord_deg"],
      "G24_source_station_straight_heading_deg":item["G23B_station_straight_source_tangent_heading_deg"],
      "G24_reference_unchanged":item["original_source_reference_position_and_heading_unchanged"],
      "OSRM_2026_city_to_snapped_road_reference_time_min":network["network_duration_minutes"] if travel_ok else None,
      "OSRM_2026_city_to_snapped_road_reference_distance_km":network["network_distance_km"] if travel_ok else None,
      "OSRM_reference_city_road_snap_m":round(raw["waypoint_source_snap_m"],2),
      "OSRM_destination_study_point_to_nearest_routable_road_m":round(network["snap_distance_m"],2),
      "OSRM_road_reference_snap_both_ends_within_600m_and_route_exists":bool(travel_ok),
      "nearby_road_reference_way_name":network["name"],
      "road_time_unavailable_is_NULL_and_not_zero":True,
      "not_a_legal_station_road_access_or_last_mile":True,
      "road_does_not_demonstrate_rail_route_feasibility":True,
      "2021_residents_not_rail_demand":True})
 if len(results)!=len(rows):
  raise ValueError("G25_wrong_number_of_shortlisted_site_family_route_screens")
 if not all(any(q["OSRM_road_reference_snap_both_ends_within_600m_and_route_exists"] for q in results if q["mandatory_market"]==c) for c in MARKETS):
  raise ValueError("G25_two_mandatory_city_road_source_coverage_not_observed")
 byseed={}
 for row in results:
  key=(row["mandatory_market"],row["source_corridor_family"],row["source_G24_reference_seed"])
  group=byseed.setdefault(key,[])
  group.append(row)
 if len(byseed)!=13:raise ValueError("G25_source_13_site_family_mandatory_groups_not_preserved")
 improvements=[]
 for key,group in sorted(byseed.items()):
  baseline=[x for x in group if x["G24_reference_unchanged"]]
  if len(baseline)!=1:raise ValueError("G25_source_shortlist_original_reference_missing")
  base=baseline[0]
  for x in group:
   if x["OSRM_road_reference_snap_both_ends_within_600m_and_route_exists"] and base["OSRM_road_reference_snap_both_ends_within_600m_and_route_exists"]:
    difference=round(x["OSRM_2026_city_to_snapped_road_reference_time_min"]-base["OSRM_2026_city_to_snapped_road_reference_time_min"],2)
   else:difference=None
   x["OSRM_2026_road_reference_delta_vs_same_G24_family_seed_baseline_min"]=difference
   if not x["G24_reference_unchanged"]:
    improvements.append({"city":key[0],"family":key[1],"seed":key[2],"role":x["source_G24_screening_role"],
     "road_reference_delta_min":difference,
     "original_source_study_station_p90_m":x["G24_original_DGT2m_station_p90_m"],
     "moved_site_road_valid":x["OSRM_road_reference_snap_both_ends_within_600m_and_route_exists"]})
 data={"mission":"MN-GEO-RAIL-001","stage":"G25_original_G24_29_mandatory_city_study_shortlist_real_OSRM_reference_road_driving",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "original_G24_source_SHA256":G24_SHA,
  "G24_same_city_original_study_shortlist_rows":len(rows),
  "deduplicated_unique_G24_road_target_points":sum(map(len,by_city.values())),
  "OSRM_source_real_network_table_queries":len(receipts),
  "observed_live_source_OSRM_response_hash_receipts":receipts,
  "source_road_snap_max_m":OSRM_SNAP_MAX_M,
  "two_compulsory_cities":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "G24_3_corridor_source_lines_not_real_rail_alignments":True,
  "G23B_original_DGT2m_reference_ground_not_stations":True,
  "OSRM_road_snap_point_does_NOT_certify_station_legal_road_access":True,
  "road_times_to_moved_positions_NOW_measured_without_imputing_original":True,
  "OSRM_road_network_no_live_congestion":True,
  "unobserved_bus_GTFS_not_imputed_as_zero":True,
  "no_train_journey_time_rail_engineering_CAPEX_or_CBA":True,
  "source_13_families_city_reference_road_time_deltas_at_new_study_points":improvements,
  "source_shortlisted_road_reference_route_cases":results,
  "Fxx_accepted":False,"Site_authorized":False}
 outjson.parent.mkdir(parents=True,exist_ok=True);outjson.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 md=["# G25 — Tempo rodoviário real para as referências deslocadas G24, não estações",
  "","Serviço OSRM (malha OpenStreetMap), uma consulta de tabela por cada cidade obrigatória. Exige snap do ponto urbano e do ponto exploratório a via navegável até 600 m e caminho existente. **Não demonstra acesso legal, posição de entrada numa estação ou prazo de obra.**",
  "",
  "## Todas as shortlist de cidade e família com posição e tráfego de referência",
  "| Cidade | Família | Referência | Papel G24 | Distância à grelha G10 (m) | Tempo centro-via próxima OSRM (min) | Delta face à referência original (min) | Snap da via ao ponto (m) |",
  "|---|---|---|---|---:|---:|---:|---:|"]
 for x in results:
  time1=x["OSRM_2026_city_to_snapped_road_reference_time_min"]
  difference=x["OSRM_2026_road_reference_delta_vs_same_G24_family_seed_baseline_min"]
  md.append(f"| {x['mandatory_market']} | {x['source_corridor_family']} | {x['source_G24_reference_seed']} | {x['source_G24_screening_role']} | {x['G24_original_grid_distance_m']:.0f} | {time1 if time1 is not None else 'N/D'} | {difference if difference is not None else 'N/D'} | {x['OSRM_destination_study_point_to_nearest_routable_road_m']:.0f} |")
 md+=["","Os tempos diferem das medições G12 anteriores porque os pontos foram deslocados e o grafo OSM pode ter evoluído. Delta calculado **na mesma consulta de rede e mesmo ponto urbano**, não por subtração de estudos de datas distintas.",
  "","## Condições para seleção posterior",
  "- Local sem estrada navegável no raio de 600 m mantém tempo nulo (N/D); não é acesso zero.",
  "- A proximidade a uma estrada pública não confere direito de construir interface, acesso ou parqueamento.",
  "- O G24/G25 não contém geotecnia nem traçado 3D contínuo, curvas de transição, estruturas ou custo monetário.",
  "- A prioridade seguinte é verificar fotointerpretação, ocupação do solo, atravessamentos, plataformas e custos de localização, não aumentar indiscriminadamente os pontos estudados.",
  "","Sem novas aquisições DGT, nem Fxx ou Site.",""]
 report.parent.mkdir(parents=True,exist_ok=True);report.write_text("\n".join(md))
 print("G25_NEW_ROAD_SHORTLIST="+json.dumps({
  "source_shortlist":len(rows),"unique_road_target_points":sum(map(len,by_city.values())),
  "OSRM_table_calls":len(receipts),
  "valid_rows":sum(x["OSRM_road_reference_snap_both_ends_within_600m_and_route_exists"] for x in results),
  "city_bounds":[{"city":city,"reference_points":len(by_city[city])} for city in MARKETS],
  "moved_road_deltas":[{"city":x["city"],"family":x["family"],"seed":x["seed"],
    "delta_min":x["road_reference_delta_min"]} for x in improvements]},ensure_ascii=False,separators=(",",":")))
 return data

def main():
 a=argparse.ArgumentParser()
 for name in ("g24","json","markdown"):a.add_argument("--"+name,type=Path,required=True)
 z=a.parse_args();run(z.g24,z.json,z.markdown)
if __name__=="__main__":main()
