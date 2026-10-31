#!/usr/bin/env python3
"""G11: city service and road-intermodality SCREEN for 27 original G10 routes.

Six grounded city reference points. Source research lines are centre-to-centre
2km cells, NOT railway alignments or station property. A city->line shortest
straight distance is only geographic coverage; OSRM optional real OSM road
routing goes to a *road-snapped screening point*, NEVER an existing or
approved station. Fail-closed on OSRM/API errors, excessive nearest snap or
unroutable roads. No population catchments, ridership or capital cost.
"""
from __future__ import annotations
import argparse,hashlib,json,math,time,urllib.request,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
from collections import defaultdict
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString,Point,mapping
from shapely.ops import transform as shapetransform
from geo_rail_g10_27_macro_portfolio import compose,G3_SHA,G5_SHA

G10_SHA="7677ed95f822ee8ada510f984f50ee498851e3bd948f9ed960e08f8620cc7287"
# Point references represent urban centres/civic places, NEVER assumed stations.
CITY={
 "Guimaraes":{"label":"Guimarães","lon":-8.2956,"lat":41.4418,"source":"https://mapcarta.com/pt/Guimar%C3%A3es",
  "mandatory":False,"existing_rail_network":"Linha de Guimarães (CP), interchange baseline must be assessed"},
 "Amarante":{"label":"Amarante","lon":-8.0783029,"lat":41.2696065,"source":"https://portalautarquico.dgal.gov.pt/pt-PT/entidades_locais/concelhos/amarante/",
  "mandatory":False,"existing_rail_network":"not assessed"},
 "Vila_Real":{"label":"Vila Real","lon":-7.744,"lat":41.3006,"source":"G3/B1 original approved study city reference",
  "mandatory":True,"existing_rail_network":"not assessed"},
 "Mirandela":{"label":"Mirandela","lon":-7.1775,"lat":41.4896,"source":"https://mapcarta.com/pt/Mirandela",
  "mandatory":False,"existing_rail_network":"not assessed"},
 "Macedo_de_Cavaleiros":{"label":"Macedo de Cavaleiros","lon":-6.956,"lat":41.5362,"source":"https://mapcarta.com/pt/28366606",
  "mandatory":False,"existing_rail_network":"not assessed"},
 "Braganca":{"label":"Bragança","lon":-6.7576,"lat":41.8060,"source":"G3/B1 original approved study city reference",
  "mandatory":True,"existing_rail_network":"not assessed"},
}
OSRM="https://router.project-osrm.org/table/v1/driving/"
MAX_OSRM_BYTES=750_000
OSRM_SNAP_MAX_M=600.
OSRM_SERVER_MAX_CALLS=6
NETWORK_DELAY_SEC=1.20
# The numbers below are sensitivity hypotheses, NOT observed train dwell.
STOP_ASSUMPTIONS={"dwell_min_s":60.,"dwell_max_s":120.,
                  "accelerate_m_s2_range":[.4,.7],
                  "brake_m_s2_range":[.5,.8]}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def stop_time_cost_bounds(speed):
 v=speed/3.6
 # On a constant unrestricted line, penalty over non-stop passing time:
 # v/(2a)+v/(2b)+dwell. Excludes approach speed profiles and gradients.
 best=v/(2*.7)+v/(2*.8)+60.
 worst=v/(2*.4)+v/(2*.5)+120.
 return {"lower_minutes":round(best/60,2),"upper_minutes":round(worst/60,2),
         "hypothetical_acceleration_braking_dwell_not_scheduled":True}

def source_geometry():
 return None

def reachability_label(d):
 if d<=3:return "within_3km_line_proximity_not_station"
 if d<=8:return "3_to_8km_line_proximity_feeder_review"
 if d<=20:return "8_to_20km_requires_feeder_or_branch_assessment"
 return "more_than_20km_weak_direct_proximity"

def metric(lines):
 xform=Transformer.from_crs(4326,3763,always_xy=True)
 inverse=Transformer.from_crs(3763,4326,always_xy=True)
 result=[]
 for id,mods,cells in lines:
  corridor=LineString([(p[0]+1000,p[1]+1000) for p in cells])
  for key,ref in CITY.items():
   cx,cy=xform.transform(ref["lon"],ref["lat"])
   city=Point(cx,cy)
   position=corridor.project(city)
   closest=corridor.interpolate(position)
   lon,lat=inverse.transform(closest.x,closest.y)
   d=city.distance(closest)/1000.
   result.append({"combination_id":id,"P1_variant":mods[0],"P3_variant":mods[1],"P5_variant":mods[2],
    "city_key":key,"city":ref["label"],"mandatory_service_city":ref["mandatory"],
    "city_reference_coordinates_lon_lat":[ref["lon"],ref["lat"]],
    "city_reference_source":ref["source"],
    "closest_source_research_grid_path_coordinate_WGS84":[round(lon,7),round(lat,7)],
    "minimum_straight_distance_urban_reference_to_source_lattice_km":round(d,3),
    "nearest_research_chainage_km":round(position/1000,3),
    "geographic_service_proximity_class":reachability_label(d),
    "rail_station_constructibility_legal_access_verified":False,
    "rail_stop_time_and_reliable_train_travel_time_measured":False,
    "road_network_minutes_to_existing_station_measured":False,
    "road_routing_network_minutes_to_research_point":None,
    "road_routing_network_km_to_research_point":None,
    "road_routing_source_snap_city_m":None,
    "road_routing_source_snap_research_point_m":None,
    "road_service_point_is_not_a_proven_rail_station":True})
 return result

def _read_osrm(city_key,unique):
 city=CITY[city_key]
 # Official OSRM demo rate <=1 request/s, public best effort.
 origin=(city["lon"],city["lat"])
 points=[origin]+[(latlon[0],latlon[1]) for latlon in unique]
 positions=";".join(f"{lon:.7f},{lat:.7f}" for lon,lat in points)
 url=OSRM+positions+"?sources=0&annotations=duration,distance"
 if len(url)>7800:raise ValueError("OSRM_URL_exceeds_reasonable_public_demo")
 req=urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte-research-rail-intermodality/1.0 (public,low-rate)","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=45) as res:
  if res.status!=200:raise RuntimeError("OSRM_non200")
  raw=res.read(MAX_OSRM_BYTES+1)
 if len(raw)>MAX_OSRM_BYTES:raise ValueError("OSRM_response_exceeds_bound")
 reply=json.loads(raw)
 if reply.get("code")!="Ok" or len(reply.get("destinations",[]))!=len(points):
  raise ValueError("OSRM_route_table_invalid_or_not_available")
 if len(reply.get("durations",[]))!=1 or len(reply["durations"][0])!=len(points):
  raise ValueError("OSRM_one_origin_route_duration_shape")
 if len(reply.get("distances",[]))!=1 or len(reply["distances"][0])!=len(points):
  raise ValueError("OSRM_distance_shape_invalid")
 if len(reply.get("sources",[]))!=1:raise ValueError("OSRM_no_source_waypoint")
 return {"endpoint_base":OSRM,"response_SHA256":hashlib.sha256(raw).hexdigest(),
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "waypoint_source_snap_m":float(reply["sources"][0].get("distance",1e9)),
  "destinations":[{"source_position":i,
    "snap_distance_m":float(reply["destinations"][i+1].get("distance",1e9)),
    "name":str(reply["destinations"][i+1].get("name",""))[:90],
    "network_duration_minutes":round(float(reply["durations"][0][i+1])/60.,2) if reply["durations"][0][i+1] is not None else None,
    "network_distance_km":round(float(reply["distances"][0][i+1])/1000.,2) if reply["distances"][0][i+1] is not None else None}
      for i in range(len(unique))]}
 
def road_network_probe(rows,enabled=True):
 receipts=[]
 if not enabled:
  return [{"city":k,"status":"explicitly_disabled"} for k in CITY]
 for key in CITY:
  rows_city=[z for z in rows if z["city_key"]==key]
  seen={}
  for z in rows_city:
   # Using rounded 2km source grid closest point. Coincident candidates
   # share request; distinct geographic alternatives still count separately.
   point=tuple(z["closest_source_research_grid_path_coordinate_WGS84"])
   seen.setdefault(point,[]).append(z)
  unique=list(seen)
  if len(unique)>54: # fail closed on too many public-demo destinations
   receipts.append({"city":key,"status":"not_probed_too_many_unique_study_points","count":len(unique)})
   continue
  try:
   d=_read_osrm(key,unique)
   d["city"]=key
   d["unique_destinations"]=len(unique)
   d["status"]="OSRM_public_demo_road_snapshot_not_real_station_access"
   receipts.append({k:v for k,v in d.items() if k!="destinations"})
   src_ok=d["waypoint_source_snap_m"]<=OSRM_SNAP_MAX_M
   for point,entry in zip(unique,d["destinations"]):
    dst_ok=entry["snap_distance_m"]<=OSRM_SNAP_MAX_M
    usable=src_ok and dst_ok and entry["network_duration_minutes"] is not None
    for z in seen[point]:
     z["road_routing_usable_as_research_access_proxy"]=bool(usable)
     z["road_routing_source_snap_city_m"]=round(d["waypoint_source_snap_m"],1)
     z["road_routing_source_snap_research_point_m"]=round(entry["snap_distance_m"],1)
     if usable:
      z["road_routing_network_minutes_to_research_point"]=entry["network_duration_minutes"]
      z["road_routing_network_km_to_research_point"]=entry["network_distance_km"]
      z["road_to_snap_point_label_not_station"]=entry["name"]
  except Exception as ex:
   receipts.append({"city":key,"status":"unavailable_no_road_access_claim",
                    "exception_type":type(ex).__name__,
                    "unique_destinations_attempted":len(unique)})
  time.sleep(NETWORK_DELAY_SEC)
 return receipts

def summary(rows,portfolio):
 per_city=[]
 for key,ref in CITY.items():
  data=[z for z in rows if z["city_key"]==key]
  d=[z["minimum_straight_distance_urban_reference_to_source_lattice_km"] for z in data]
  route_ok=[z for z in data if z["road_routing_network_minutes_to_research_point"] is not None]
  per_city.append({"city":ref["label"],"mandatory":ref["mandatory"],
   "across_27_min_geometric_straightline_km":round(min(d),2),
   "across_27_max_geometric_straightline_km":round(max(d),2),
   "options_within_3km_straightline":sum(x<=3 for x in d),
   "options_within_8km_straightline":sum(x<=8 for x in d),
   "options_within_20km_straightline":sum(x<=20 for x in d),
   "options_with_qualified_road_network_proxy":len(route_ok),
   "road_proxy_best_min_from_city_to_snapped_research_point_min":round(min(
    x["road_routing_network_minutes_to_research_point"] for x in route_ok),2) if route_ok else None,
   "road_proxy_worst_min_from_city_to_snapped_research_point_min":round(max(
    x["road_routing_network_minutes_to_research_point"] for x in route_ok),2) if route_ok else None,
   "still_no_approved_rail_station":True})
 choose=["P1-1-1","P1-2-1","P2-2-1","P2-2-3","P1-3-1","P3-1-3"]
 detailed=[]
 for id in choose:
  all_stops={x["city_key"]:x for x in rows if x["combination_id"]==id}
  proxy=next(x for x in portfolio["scenario_rows"] if x["combination_id"]=="P"+id and x["speed_scenario_kmh"]==200) if False else None
  detailed.append({"id":id,"cities":{k:{"straight_km":all_stops[k]["minimum_straight_distance_urban_reference_to_source_lattice_km"],
      "road_to_candidate_min":all_stops[k]["road_routing_network_minutes_to_research_point"],
      "class":all_stops[k]["geographic_service_proximity_class"]} for k in CITY}})
 return per_city,detailed

def run(g3path,g5path,g10path,outjson,outgeo,outmd,network=True):
 for path,expected in ((g3path,G3_SHA),(g5path,G5_SHA),(g10path,G10_SHA)):
  if sha(path)!=expected:raise ValueError("SHA_changed_"+path.name)
 g3=json.loads(g3path.read_text());g5=json.loads(g5path.read_text())
 portfolio=json.loads(g10path.read_text())
 if (portfolio["total_combinations"]!=27 or
    portfolio["service_cities"]!=["Vila Real","Bragança"] or
    not portfolio["Sanabria_excluded"] or
    portfolio["Fxx_accepted"] or portfolio["Site_authorized"]):
  raise ValueError("G10_original_scope_not_matching")
 lines=compose(g3,g5)
 rows=metric(lines)
 if len(rows)!=162:raise ValueError("G11_six_by_27_service_matrix_missing")
 receipts=road_network_probe(rows,enabled=network)
 city_summary,priority=summary(rows,portfolio)
 src=Transformer.from_crs(4326,3763,always_xy=True)
 inv=Transformer.from_crs(3763,4326,always_xy=True)
 feats=[]
 for key,ref in CITY.items():
  feats.append({"type":"Feature","geometry":{"type":"Point","coordinates":[ref["lon"],ref["lat"]]},
      "properties":{"city":ref["label"],"mandatory":ref["mandatory"],
       "urban_reference_not_station":True,"coordinate_source":ref["source"]}})
 for id,mods,route in lines:
  line=LineString([(x+1000,y+1000) for x,y in route])
  feats.append({"type":"Feature","geometry":mapping(shapetransform(inv.transform,line)),
    "properties":{"study_option":"P"+id,"layer":"real_G3_G5_source_sector_centres_NOT_railway","source_only":True}})
  for z in rows:
   if z["combination_id"]!=id:continue
   o=CITY[z["city_key"]]
   feats.append({"type":"Feature","geometry":{"type":"LineString","coordinates":[
       [o["lon"],o["lat"]],z["closest_source_research_grid_path_coordinate_WGS84"]]},
     "properties":{"option":"P"+id,"city":o["label"],"straightline_km":z[
       "minimum_straight_distance_urban_reference_to_source_lattice_km"],
       "connector_is_straightline_not_road_or_rail":True,
       "verified_road_proxy_minutes":z["road_routing_network_minutes_to_research_point"]}})
 for path,content in [(outgeo,{"type":"FeatureCollection",
     "name":"G11 27 real source study routes, six geographic city anchors and straight-line connectors, NOT rail","features":feats})]:
  path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(content,ensure_ascii=False)+"\n")
 data={"mission":"MN-GEO-RAIL-001","stage":"G11_six_city_service_and_candidate_road_access_screen",
   "observed_utc":datetime.now(timezone.utc).isoformat(),
   "sources_SHA256":{"G3_original_lattice":G3_SHA,"G5_original_geographic_bands":G5_SHA,"G10_27_option_evidence":G10_SHA},
   "real_source_six_city_reference_points":CITY,
   "mandatory_nodes":["Vila Real","Bragança"],"Sanabria_excluded":True,
   "secondary_service_nodes":["Guimarães","Amarante","Mirandela","Macedo de Cavaleiros"],
   "total_source_research_27_corridors":27,"city_route_pairs":len(rows),
   "definition_of_quality":"geographic directness + qualified road routing to a snapped study reference only, not station or service quality certification",
   "city_station_locations_approved":False,"genuine_station_sites_road_legal_access_verified":False,
   "walk_bus_access_frequencies_not_yet_modelled":True,
   "observed_population_jobs_catchments_not_yet_modelled":True,
   "rail_stopping_scenario_sensitivity":{str(s):stop_time_cost_bounds(s) for s in (160,200,250)},
   "OSRM_public_demo_best_effort_source_road_snap_limit_m":OSRM_SNAP_MAX_M,
   "OSRM_demo_road_routing_receipts":receipts,
   "all_road_minutes_are_to_a_snapped_road_near_an_unbuilt_study_geometry_not_to_a_station":True,
   "city_reference_to_research_line_nearest_is_euclidean_not_network_access":True,
   "no_auth_original_DGT_acquisitions":True,"Fxx_accepted":False,"Site_authorized":False,
   "city_overview":city_summary,"selected_combination_service_comparison":priority,"all_162_source_route_city_pairs":rows}
 outjson.parent.mkdir(parents=True,exist_ok=True);outjson.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 md=["# G11 — qualidade potencial de serviço de seis cidades em 27 alternativas territoriais",
   "","**Vila Real e Bragança são obrigações funcionais ainda não demonstradas.** Guimarães, Amarante, Mirandela e Macedo de Cavaleiros são nós de serviço adicionais a testar. Estações e frequências não estão decididas.",
   "","| Nó | Menor afastamento à grelha (km, sem estrada) | Maior afastamento (km) | Alternativas até 3 km | Até 8 km | Até 20 km | Proxies rodoviários válidos/27 |",
   "|---|---:|---:|---:|---:|---:|---:|"]
 for x in city_summary:
  md.append(f"| {x['city']} | {x['across_27_min_geometric_straightline_km']} | {x['across_27_max_geometric_straightline_km']} | {x['options_within_3km_straightline']} | {x['options_within_8km_straightline']} | {x['options_within_20km_straightline']} | {x['options_with_qualified_road_network_proxy']} |")
 md+=["","## Matriz de nós para seis combinações a 200 km/h",
   "Distância em linha reta da referência urbana à linha que une os centros de quadrículas G3/G5. O tempo rodoviário, quando disponível, mede até ao ponto de acesso rodoviário para o qual a rede OSM foi ajustada, não até a uma estação e não valida entrada a uma propriedade.",
   "","| Combinação | Guimarães km | Amarante km | Vila Real km | Mirandela km | Macedo km | Bragança km |",
   "|---|---:|---:|---:|---:|---:|---:|"]
 for r in priority:
  vals=[str(r["cities"][city]["straight_km"]) for city in CITY]
  md.append(f"| {r['id']} | "+" | ".join(vals)+" |")
 md+=["","## Sensibilidade a paragens (não é horário)",
   "| Velocidade de referência | Intervalo hipotético por paragem adicional |",
   "|---:|---:|"]
 for s in (160,200,250):
  y=stop_time_cost_bounds(s)
  md.append(f"| {s} km/h | {y['lower_minutes']}–{y['upper_minutes']} min |")
 md+=["","Estas hipóteses decorrem de aceleração 0,4–0,7 m/s², desaceleração 0,5–0,8 m/s² e paragem 60–120s; sem perfil real de via, energia, gradientes nem velocidade local. Não somar automaticamente a todos os comboios: pode existir serviço expresso e serviço com paragens.",
  "Guimarães já integra a Linha de Guimarães (serviço CP), logo deve ser considerada também a integração e a transferência com a rede existente, não só uma nova estação de passagem. Fonte: https://servicos.infraestruturasdeportugal.pt/estacoes?estacaoId=9424000",
  "","## Limites",
  "As 27 linhas continuam a ser sequências de quadrículas de 2km, não traçados projetados. O roteamento rodoviário público de demonstração OSRM é um teste de potencial de acesso a pontos de rede e NÃO valida uma estação, um interface, caminhos pedonais, transporte coletivo, horários, legalidade dos acessos, procura nem custos. Se falhar, usa-se N/D, sem substituição por tempos fictícios.",
  "A prioridade seguinte será escolher 2–3 áreas candidatas de estação por cidade onde se cruzem corredor e vias públicas adequadas, testar acesso multi-origem por rede e população/emprego abrangidos, e depois recalcular o portefólio 27×3.",
  "","**Sem aquisição MDT extensa. Pré-aceitação, Fxx/Site indisponíveis.**",""]
 outmd.parent.mkdir(parents=True,exist_ok=True);outmd.write_text("\n".join(md))
 print("G11_CITY_SERVICE="+json.dumps({
   "cities":city_summary,"road_receipts":[{"city":r["city"],"status":r["status"],"n":r.get("unique_destinations")} for r in receipts],
   "selected_200":priority,"stopping_scenarios":data["rail_stopping_scenario_sensitivity"]},ensure_ascii=False,separators=(',',':')))
 return data

def main():
 a=argparse.ArgumentParser()
 for n in ("g3","g5","g10","json","geojson","markdown"):a.add_argument("--"+n,type=Path,required=True)
 a.add_argument("--no-network",action="store_true")
 p=a.parse_args()
 run(p.g3,p.g5,p.g10,p.json,p.geojson,p.markdown,network=not p.no_network)
if __name__=="__main__":main()
