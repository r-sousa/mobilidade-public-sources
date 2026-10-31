#!/usr/bin/env python3
"""G12a source-audited PRE-STATION siting and feeder access exploration.

6 geographically diverse G10 source 2km research corridors × 6 urban markets
× 3 track-grid reference positions (-3km, nearest, +3km along research line).
The output points ARE NOT railway stations, rails or viable civil-engineering
sites. OSRM public road routing is for research only; legal road entrance,
land-use, urban population/job catchment, public transport and CAPEX unknown.
"""
from __future__ import annotations
import argparse,hashlib,json,math,time
from datetime import datetime,timezone
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import LineString,Point
from geo_rail_g10_27_macro_portfolio import compose,G3_SHA,G5_SHA
from geo_rail_g11_urban_service import CITY,_read_osrm,OSRM_SNAP_MAX_M,stop_time_cost_bounds

G10_SHA="7677ed95f822ee8ada510f984f50ee498851e3bd948f9ed960e08f8620cc7287"
G11_SHA="ab09a1d383e0152b79c0fb1ca36c050d938021e6e11775dd158cb3b675990e46"
STUDY_COMBINATIONS=("P1-1-1","P1-2-1","P2-2-1","P2-2-3","P1-3-1","P3-1-3")
OFFSETS_KM=(-3.,0.,3.)
MIN_ENDPOINT_BUFFER_KM=2.
POTENTIAL_FEEDER_SCREEN_MIN=15.
MAX_REQUESTS=6
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(2**20),b""):h.update(b)
 return h.hexdigest()

def station_research_points(geometry, key, ref, to_pt,to_wgs):
 city=Point(*to_pt.transform(ref["lon"],ref["lat"]))
 s0=geometry.project(city)
 length=geometry.length
 if length<20000:raise ValueError("invalid_long_research_chain")
 points=[]
 for off in OFFSETS_KM:
  chainage=min(max(s0+off*1000,MIN_ENDPOINT_BUFFER_KM*1000),length-MIN_ENDPOINT_BUFFER_KM*1000)
  loc=geometry.interpolate(chainage)
  lon,lat=to_wgs.transform(loc.x,loc.y)
  points.append({"urban_market":ref["label"],"urban_market_key":key,
   "offset_along_2km_research_grid_km":off,
   "reference_study_chainage_km":round(chainage/1000,3),
   "WGS84_research_coordinate":[round(lon,7),round(lat,7)],
   "urban_reference_to_research_point_euclidean_km":round(city.distance(loc)/1000,3),
   "is_existing_or_proposed_station":False,
   "road_network_drive_minutes_to_research_road_snap":None,
   "road_routing_valid_to_a_road_near_study_point":False,
   "parcel_and_actual_station_platform_or_site_checked":False,
   "railway_curve_gradient_and_station_vertical_level_checked":False})
 return points

def network_access(rows, enabled):
 if not enabled:return [{"city":k,"status":"network_explicitly_disabled"} for k in CITY]
 receipts=[]
 if len(CITY)>MAX_REQUESTS:raise ValueError("bounded_public_demo_request_cap")
 for city in CITY:
  candidate=[(r,p) for r in rows for p in r["research_station_points"] if p["urban_market_key"]==city]
  uniq={}
  for r,p in candidate:
   key=tuple(p["WGS84_research_coordinate"])
   uniq.setdefault(key,[]).append(p)
  unique=list(uniq)
  if len(unique)>60:
   receipts.append({"city":city,"status":"too_many_public_OSRM_destinations_not_routed"})
   continue
  try:
   response=_read_osrm(city,unique)
   assert len(response["destinations"])==len(unique)
   receipts.append({"city":city,"status":"OSRM_observed_public_road_snapshot_not_station",
    "OSRM_response_sha256":response["response_SHA256"],
    "city_road_snap_m":round(response["waypoint_source_snap_m"],2),
    "distinct_city_to_study_point_destinations":len(unique)})
   for coordinate,dest in zip(unique,response["destinations"]):
    valid=response["waypoint_source_snap_m"]<=OSRM_SNAP_MAX_M and dest["snap_distance_m"]<=OSRM_SNAP_MAX_M and dest["network_duration_minutes"] is not None
    for point in uniq[coordinate]:
     point["road_routing_city_road_snap_m"]=round(response["waypoint_source_snap_m"],2)
     point["road_routing_study_point_road_snap_m"]=round(dest["snap_distance_m"],2)
     point["road_routing_valid_to_a_road_near_study_point"]=bool(valid)
     if valid:
      point["road_network_drive_minutes_to_research_road_snap"]=dest["network_duration_minutes"]
      point["road_network_drive_km_to_research_road_snap"]=dest["network_distance_km"]
  except Exception as ex:
   receipts.append({"city":city,"status":"no_road_result_fail_closed",
     "error_type":type(ex).__name__,"distinct_destinations_attempted":len(unique)})
  time.sleep(1.15)
 return receipts

def six_option_service_table(all_rows,g10,g11):
 existing={(r["combination_id"],r["city_key"]):r for r in g11["all_162_source_route_city_pairs"]}
 portfolio={(r["combination_id"],r["speed_scenario_kmh"]):r for r in g10["scenario_rows"]}
 out=[]
 for r in all_rows:
  result={"research_combination":r["combination_id"],"urban_markets":{},
    "city_market_screen_no_validated_station_sites":True,
    "scenario_200kmh_source_surface_and_length":{}}
  technical=portfolio[(r["combination_id"],200)]
  result["scenario_200kmh_source_surface_and_length"]={
   "historical_G10_curvature_200_screen_pass":technical["horizontal_radius_research_screen_pass"],
   "L1_25permille_DSM_fraction_above25m":technical.get("passenger25_DSM_fraction_gt25m"),
   "L1_25permille_DSM_P90_offset_m":technical.get("passenger25_DSM_p90_m"),
   "smoothed_research_grid_length_km_not_real_rail":technical.get("smoothed_research_grid_length_km_not_rail_track")}
  for k,city in CITY.items():
   options=[z for z in r["research_station_points"] if z["urban_market_key"]==k]
   valid=[z for z in options if z["road_routing_valid_to_a_road_near_study_point"]]
   rank=sorted(valid,key=lambda z:(z["road_network_drive_minutes_to_research_road_snap"],
                      z["urban_reference_to_research_point_euclidean_km"],abs(z["offset_along_2km_research_grid_km"])))
   previous=existing[(r["combination_id"],k)]
   result["urban_markets"][k]={"label":city["label"],"mandatory":city["mandatory"],
     "original_nearest_2km_source_grid_straight_km":previous["minimum_straight_distance_urban_reference_to_source_lattice_km"],
     "original_G11_road_to_nearest_source_grid_road_snap_min":previous["road_routing_network_minutes_to_research_point"],
     "three_new_study_points_road_valid_count":len(valid),
     "study_points":options,
     "best_road_snap_research_point_only":({"offset_km":rank[0]["offset_along_2km_research_grid_km"],
       "road_minutes":rank[0]["road_network_drive_minutes_to_research_road_snap"],
       "study_point_WGS84":rank[0]["WGS84_research_coordinate"]} if rank else None),
     "not_verified_real_station_or_scheduled_access":True}
  out.append(result)
 return out

def service_scenario_proxies(tab,g10):
 # This is strictly a service-plan stopping sensitivity, not a rail
 # timetable, population-weighted monetized benefit or speed forecast.
 modes={
  "EXP_VR_BR_only":{"stop_at":["Vila_Real","Braganca"],"other_city_mode":"feeder_transfers_not_timed"},
  "REG_VR_BR_Amarante_Mirandela_Macedo":{"stop_at":["Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca"],"other_city_mode":"Guimaraes_existing_rail_or_feeder"},
  "REG_VR_BR_Guimaraes_Mirandela_Macedo":{"stop_at":["Guimaraes","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca"],"other_city_mode":"Amarante_road_feeder"},
  "REG_all_six":{"stop_at":list(CITY),"other_city_mode":"all_six_hypothetical_rail_stops_not_station_feasibility"}
 }
 result=[]
 for r in tab:
  rid=r["research_combination"]
  for speed in (160,200,250):
   g=next(z for z in g10["scenario_rows"] if z["combination_id"]==rid and z["speed_scenario_kmh"]==speed)
   penalty=stop_time_cost_bounds(speed)
   for name,mode in modes.items():
    n=len(mode["stop_at"])
    if n<2 or not {"Vila_Real","Braganca"}.issubset(set(mode["stop_at"])):raise ValueError("mandatory_stop_omitted")
    gap=g.get("hypothetical_length_divided_by_speed_minutes_NOT_train_travel_time")
    result.append({"research_combination":rid,"speed_kmh":speed,"service_pattern":name,
      "hypothetical_stop_markets":mode["stop_at"],
      "other_cities_served_by":"feeder_only_unverified" if n<6 else "all_stops_if_constructible",
      "conceptual_stops_including_two_mandatory":n,
      "not_a_timetable":True,
      "incremental_stop_count_beyond_two_mandatory":n-2,
      "additional_stop_motion_plus_dwell_penalty_lower_min":round((n-2)*penalty["lower_minutes"],2),
      "additional_stop_motion_plus_dwell_penalty_upper_min":round((n-2)*penalty["upper_minutes"],2),
      "G10_source_grid_length_divided_by_speed_index_min_not_train_time":gap,
      "not_counted": "rail_stations_not_engineered; stop market may need branch/rail connection; terminal braking and network connections not modeled",
      "not_additive_to_end_to_end_passenger_door_to_door":True,
      "source_G10_horizontal_proxy_screen_pass":g["horizontal_radius_research_screen_pass"],
      "has_cost_eur_or_population_demand_estimate":False})
 return modes,result

def execute(g3path,g5path,g10path,g11path,out_path,doc_path,geo_path,network):
 for p,h in ((g3path,G3_SHA),(g5path,G5_SHA),(g10path,G10_SHA),(g11path,G11_SHA)):
  if sha(p)!=h:raise ValueError("G12_invalid_archived_original_source_"+p.name)
 g3=json.loads(g3path.read_text());g5=json.loads(g5path.read_text())
 g10=json.loads(g10path.read_text());g11=json.loads(g11path.read_text())
 if (g11["city_route_pairs"]!=162 or g10["total_combinations"]!=27 or
   g11["mandatory_nodes"]!=["Vila Real","Bragança"] or
   not g11["Sanabria_excluded"] or g11["Site_authorized"] or g10["Fxx_accepted"]):
  raise ValueError("source_scope_mandatory_city_sanabria_governance")
 lines=compose(g3,g5)
 chosen=[(id,mods,route) for id,mods,route in lines if id in STUDY_COMBINATIONS]
 if len(chosen)!=6:raise ValueError("did_not_preserve_six_review_geographies")
 to_pt=Transformer.from_crs(4326,3763,always_xy=True)
 to_wgs=Transformer.from_crs(3763,4326,always_xy=True)
 rows=[]
 features=[]
 for rid,mods,route in chosen:
  line=LineString([(p[0]+1000,p[1]+1000) for p in route])
  row={"combination_id":rid,"source_P1_P3_P5":list(mods),"research_station_points":[]}
  for key,ref in CITY.items():
   points=station_research_points(line,key,ref,to_pt,to_wgs)
   row["research_station_points"]+=points
   for point in points:
    features.append({"type":"Feature","geometry":{"type":"Point","coordinates":point["WGS84_research_coordinate"]},
      "properties":{"research_combination":rid,"urban_market":ref["label"],
        "longitudinal_offset_km":point["offset_along_2km_research_grid_km"],
        "not_an_existing_or_proposed_railway_station":True}})
  rows.append(row)
 assert sum(len(r["research_station_points"]) for r in rows)==108
 receipts=network_access(rows,network)
 table=six_option_service_table(rows,g10,g11)
 patterns,services=service_scenario_proxies(table,g10)
 summary=[]
 for name,ref in CITY.items():
  routable=[t["urban_markets"][name]["best_road_snap_research_point_only"]
             for t in table if t["urban_markets"][name]["best_road_snap_research_point_only"] is not None]
  summary.append({"city":ref["label"],"mandatory":ref["mandatory"],
   "reviewed_6_geographic_options":6,
   "options_with_at_least_one_public_road_snap_route_to_study_point":len(routable),
   "min_observed_city_reference_to_study_road_snap_minutes":round(min(x["road_minutes"] for x in routable),2) if routable else None,
   "max_observed_city_reference_to_study_road_snap_minutes":round(max(x["road_minutes"] for x in routable),2) if routable else None,
   "not_real_station_or_feeder_bus_door_to_door":True})
 result={"mission":"MN-GEO-RAIL-001",
  "stage":"G12A_six_corridors_x_six_cities_x_three_2km_source_line_placement_offsets_plus_service_patterns",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "sources_SHA256":{"G3":G3_SHA,"G5":G5_SHA,"G10":G10_SHA,"G11":G11_SHA},
  "source_corridors":list(STUDY_COMBINATIONS),
  "railway_urban_nodes_mandatory":["Vila Real","Bragança"],
  "other_cities_optional":["Guimarães","Amarante","Mirandela","Macedo de Cavaleiros"],
  "Sanabria_excluded":True,
  "station_centre_not_required":True,
  "city_reference_points":CITY,
  "cities_x_corridors_x_source_research_point_offsets":[6,6,3],
  "108_source_line_research_points_are_NOT_validated_station_sites":True,
  "source_2km_grid_line_cannot_evidence_station_vertical_gradient_or_land":True,
  "candidate_longitudinal_offsets_in_km":list(OFFSETS_KM),
  "OSRM_road_snapping_within_m":OSRM_SNAP_MAX_M,
  "OSRM_demo_source_receipts":receipts,
  "zero_confirmed_railway_station_locations":True,
  "zero_travel_time_to_real_railway_station":True,
  "zero_observed_population_or_employment_catchment":True,
  "station_constructability_land_use_and_road_legal_access_unverified":True,
  "no_source_DGT_new_acquisition":True,"Fxx_accepted":False,"Site_authorized":False,
  "six_corridor_city_reference_road_snap_minute_matrix":table,
  "city_summary":summary,
  "operating_service_patterns":patterns,
  "station_stop_penalty_sensitivity_not_schedules":services}
 for path,data in ((out_path,result),
                   (geo_path,{"type":"FeatureCollection","name":"G12A experimental station study point seeds, NEVER actual railway stations","features":features})):
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
 md=["# G12A — posicionamento exploratório de interfaces e padrão de paragens",
  "","Reutiliza seis faixas G10/G11. **Os 108 pontos da grelha G3/G5 não são terrenos aptos a estações ferroviárias, não validam plataforma, rampas, curvas, acesso legal, custos ou disponibilidade.**",
  "São apenas três centros de teste longitudinais por combinação e mercado (−3/0/+3 km da projeção mais próxima da referência urbana). OSRM dá tempos de automóvel até a uma via rodoviária próxima, nunca ao interface ou transportes públicos e apenas se o snap das duas extremidades for ≤600m.",
  "","## Qualidade do acesso rodoviário exploratório", "| Cidade | Combinações com teste de rede válido / 6 | Mínimo (min) | Máximo (min) |","|---|---:|---:|---:|"]
 for row in summary:
  md.append(f"| {row['city']} | {row['options_with_at_least_one_public_road_snap_route_to_study_point']} | {row['min_observed_city_reference_to_study_road_snap_minutes'] if row['min_observed_city_reference_to_study_road_snap_minutes'] is not None else 'N/D'} | {row['max_observed_city_reference_to_study_road_snap_minutes'] if row['max_observed_city_reference_to_study_road_snap_minutes'] is not None else 'N/D'} |")
 md+=["","## Alternativas de exploração e penalizações hipotéticas",
  "Três velocidades 160/200/250 km/h. Em cada alternativa, expresso VR/Bragança, regional com Amarante, regional com Guimarães, e regional todas as seis cidades. Não constitui horário, nem garante estação: a opção por Guimarães pode exigir ramal, desvio ou transferência ferroviária existente.",
  "","| Família | Paragens hipotéticas | Acréscimo por paragens opcionais a 200 km/h (min) |",
  "|---|---|---|"]
 for mode,desc in patterns.items():
  n=len(desc["stop_at"])-2
  lim=stop_time_cost_bounds(200)
  md.append(f"| {mode} | {', '.join(CITY[k]['label'] for k in desc['stop_at'])} | {n*lim['lower_minutes']:.1f}–{n*lim['upper_minutes']:.1f} |")
 md+=["","## Condições de passagem G12B/C",
   "1. Não selecionar interfaces com base apenas no encaminhamento OSRM: testar solo nu, estrutura, acesso rodoviário legal, transporte coletivo e ligação à linha existente de Guimarães.",
   "2. Cruzar população/emprego do INE/BGRI21 (F67, original preservado em circuito privado mas publicação e cobertura ainda a verificar) e matrizes de mobilidade. Não inventar número de utentes ou valor atualizado de dados.",
   "3. Apenas após análise geométrica 3D: quantificar volumes de túneis/viadutos e custo por intervalos, e finalmente CBA territorial.",
   "4. Manter alternativas dominadas em qualquer critério ainda por medir como reserva: custos e serviço podem inverter a escolha. Sanábria excluída; Vila Real e Bragança obrigatórias.",
   "","Sem novas aquisições autênticas DGT. Nenhum Fxx ou Site autorizado.",""]
 doc_path.parent.mkdir(parents=True,exist_ok=True);doc_path.write_text("\n".join(md))
 print("G12A_REAL_SOURCE="+json.dumps({"study_points":108,
  "public_road_receipts":[{"city":z["city"],"status":z["status"],"dest":z.get("distinct_city_to_study_point_destinations")} for z in receipts],
  "cities":summary,"service_patterns":list(patterns),"sensitivity_200":stop_time_cost_bounds(200),
  "new_DGT_downloads":0},ensure_ascii=False,separators=(',',':')))
 return result

def main():
 a=argparse.ArgumentParser()
 for name in ("g3","g5","g10","g11","json","geojson","markdown"):
  a.add_argument("--"+name,type=Path,required=True)
 a.add_argument("--no-network",action="store_true")
 p=a.parse_args()
 execute(p.g3,p.g5,p.g10,p.g11,p.json,p.markdown,p.geojson,not p.no_network)
if __name__=="__main__":main()
