#!/usr/bin/env python3
"""G17 — actual Valhalla reverse-driving isochrones + original INE BGRI 2021.

This is an original 2021 resident population *road driving isochrone* screen
for research road points, never a railway passenger demand forecast. Source
2021 statistical subsection archive is SHA-locked and the public routing API
is low-rate, deduplicated, explicit 15/30/45 minute reverse arrival contours.
NO fabricated GTFS or uniformly unavailable NUTS2 Norte public transport.
No approved railway station, legal road entrance, timetable or EUR costs.
"""
from __future__ import annotations
import argparse,hashlib,json,math,sqlite3,tempfile,time,urllib.request,urllib.error
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from shapely.geometry import shape,mapping
from shapely.ops import transform,unary_union
from shapely.validation import explain_validity
from pyproj import Transformer
from geo_rail_g14_bgri2021_station_population import (
 F67_SHA,unpack_exact,native_qa,catchment
)

G14_SHA="af16f552634f066ad5723445d9bd6e389f5769a522b2782d7064bc206acc216d"
FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
CITIES=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
TIME_MINUTES=(15,30,45)
ROUTER="https://valhalla1.openstreetmap.de/isochrone"
MAX_CALLS=18
MAX_RESPONSE_BYTES=5_000_000
SLEEP_BETWEEN_REQUESTS_S=1.35

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for block in iter(lambda:f.read(2**20),b""):h.update(block)
 return h.hexdigest()

def sites(report):
 if len(report["all_54_city_research_geographic_buffer_census_cases"])!=54 or not report["Sanabria_excluded"]:
  raise ValueError("G17_2021_original_source_54_study_points_not_available")
 rows=[x for x in report["all_54_city_research_geographic_buffer_census_cases"]
       if x["research_geographic_radius_km"]==10 and x["research_corridor"] in FAMILIES]
 if len(rows)!=18:raise ValueError("G17_18_family_market_points_missing")
 points={}
 for r in rows:
  key=(r["research_corridor"],r["urban_market"])
  if key in points:raise ValueError("duplicate_site_family_market")
  points[key]=tuple(r["chosen_original_G13A_research_lonlat"])
 return points

def validate_road_contours(response,reference,to_pt):
 if response.get("type")!="FeatureCollection" or len(response.get("features",[]))!=3:
  raise ValueError("not_3_valhalla_isochrone_polygon_features")
 contours={}
 details={}
 for f in response["features"]:
  prop=f.get("properties",{})
  if prop.get("metric")!="time":raise ValueError("isochrone_not_time_metric")
  minute=float(prop.get("contour",-1))
  if minute not in TIME_MINUTES or int(minute) in contours:
   raise ValueError("time_contour_missing_or_repeated")
  g=shape(f.get("geometry",{}))
  if g.geom_type not in ("Polygon","MultiPolygon") or g.is_empty or not g.is_valid:
   raise ValueError("Valhalla_invalid_polygon_"+explain_validity(g))
  mapped=transform(to_pt.transform,g)
  if not mapped.is_valid or mapped.is_empty or mapped.area<=0:
   raise ValueError("nonpositive_Valhalla_epsg3763_polygon")
  if mapped.area>30_000_000_000:raise ValueError("45min_polygon_exceeds_reasonable_max_area")
  contours[int(minute)]=mapped
  details[str(int(minute))]={"polygon_area_km2":round(mapped.area/1_000_000,3),
    "polygon_component_count":len(mapped.geoms) if hasattr(mapped,"geoms") else 1,
    "original_metric":prop["metric"]}
 if sorted(contours)!=list(TIME_MINUTES):raise ValueError("missing_15_30_45")
 # Public router shapes are raster approximations, not always strictly nested.
 for small,big in ((15,30),(30,45)):
  miss=contours[small].difference(contours[big]).area/max(contours[small].area,1)
  details[str(small)][f"fraction_area_outside_next_{big}_minute_polygon"]=round(miss,5)
  if miss>.015:
   raise ValueError("contours_are_not_nesting_to_required_1p5pct_tolerance")
 return contours,details

def query_valhalla(lat,lon):
 payload={"locations":[{"lat":lat,"lon":lon}],"costing":"auto",
   "contours":[{"time":m} for m in TIME_MINUTES],
   "polygons":True,"reverse":True,"denoise":0.2,"generalize":150}
 raw=json.dumps(payload,separators=(",",":")).encode()
 request=urllib.request.Request(ROUTER,data=raw,method="POST",
   headers={"Content-Type":"application/json","Accept":"application/json",
    "X-Client-Id":"mobilidade-norte-rail-isochrone-research",
    "User-Agent":"MobilidadeNorte-G17-2021census-road-access-scientific-research/1.0"})
 with urllib.request.urlopen(request,timeout=80) as resp:
  if resp.status!=200 or "json" not in resp.headers.get("Content-Type","").lower():
   raise ValueError("Valhalla_response_must_be_JSON_HTTP200")
  buf=resp.read(MAX_RESPONSE_BYTES+1)
 if len(buf)>MAX_RESPONSE_BYTES:raise ValueError("Valhalla_response_exceeds_budget")
 return json.loads(buf),hashlib.sha256(buf).hexdigest()

def execute(f67zip,g14file,jsonpath,geopath,markdown,network=True):
 if sha(g14file)!=G14_SHA:raise ValueError("G14_original_census_report_sha_mismatch")
 g14=json.loads(g14file.read_text())
 if (g14["sources"]["F67_public_exact_INE_cont_2021_sha256"]!=F67_SHA or
     g14["Fxx_accepted"] or g14["Site_authorized"] or not g14["Sanabria_excluded"]):
  raise ValueError("G14_canonical_scope_not_reusable")
 refs=sites(g14)
 inv=Transformer.from_crs(4326,3763,always_xy=True)
 out=Transformer.from_crs(3763,4326,always_xy=True)
 unique={}
 for key,coordinate in refs.items():
  unique.setdefault(coordinate,[]).append(key)
 if len(unique)>MAX_CALLS:raise ValueError("real_source_request_cap")
 received={}
 receipts=[]
 errors=[]
 if network:
  for i,(coordinate,keys) in enumerate(unique.items()):
   if i:time.sleep(SLEEP_BETWEEN_REQUESTS_S)
   try:
    response,digest=query_valhalla(coordinate[1],coordinate[0])
    polys,checks=validate_road_contours(response,coordinate,inv)
    received[coordinate]=polys
    receipts.append({"study_coordinate":coordinate,"markets":[list(k) for k in keys],
      "provider":"Valhalla FOSSGIS public demo OSM network",
      "response_sha256":digest,"three_reverse_arrive_by_road_minutes":list(TIME_MINUTES),
      "observed_utc":datetime.now(timezone.utc).isoformat(),
      "native_polygon_checks":checks,
      "automobile_no_live_congestion":True,"road_route_to_point_NOT_station":True})
   except Exception as ex:
    errors.append({"reference_coordinate":coordinate,"markets":[list(k) for k in keys],
     "error_type":type(ex).__name__,"error_message":str(ex)[:250]})
 if len(received)==0:raise RuntimeError("ALL_VALHALLA_REVERSE_ROAD_ISOCHRONES_FAILED_NO_CENSUS_CLAIM")
 # Any required case missing is fail closed, no invented imputed polygon.
 if len(received)!=len(unique):
  raise RuntimeError("INCOMPLETE_REAL_NETWORK_COVERAGE_no_report_or_release "+json.dumps(errors))
 single=[]
 unions=[]
 geo=[]
 with tempfile.TemporaryDirectory(prefix="MN-G17-INE2021-") as tmp:
  original=unpack_exact(f67zip,Path(tmp))
  db=sqlite3.connect(f"file:{original}?mode=ro",uri=True,timeout=45)
  try:
   qa=native_qa(db)
   popcache={}
   for coordinate,polygonset in received.items():
    popcache[coordinate]={}
    for minute,poly in polygonset.items():
     census=catchment(db,poly,qa["rtree"])
     popcache[coordinate][minute]=census
   for (family,city),coordinate in refs.items():
    for minute in TIME_MINUTES:
     c=popcache[coordinate][minute]
     geom=received[coordinate][minute]
     single.append({"research_family":family,"urban_market_reference":city,
       "reverse_road_travel_time_minutes":minute,
       "source_research_road_reference_WGS84":coordinate,
       "2021_INE_census_residents_representative_point":c["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
       "2021_INE_census_age65_representative_point":c["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS_65_OU_MAIS"],
       "2021_INE_census_residents_area_fraction_sensitivity":c["area_weighted_uniform_within_subsection_population_estimates"]["N_INDIVIDUOS"],
       "census_subsections_intersected":c["original_subsections_intersecting_area"],
       "road_covered_polygon_km2":round(geom.area/1_000_000,2),
       "not_approved_rail_station_no_last_mile":True,
       "not_2026_residents_or_actual_train_passengers":True})
     geo.append({"type":"Feature","geometry":mapping(transform(out.transform,geom)),
       "properties":{"study_family":family,"associated_urban_market":city,
         "reverse_automobile_isochrone_arrival_minutes":minute,
         "INE_2021_original_residents_representative_assignment":c["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
         "polygon_from_real_Valhalla_OSM_routing":True,
         "not_built_or_approved_station":True,
         "no_public_transport_routing_evidence":True}})
   for family in FAMILIES:
    for minute in TIME_MINUTES:
     polygon=unary_union([received[refs[(family,city)]][minute] for city in CITIES])
     if polygon.is_empty:raise ValueError("empty_research_corridor_union")
     c=catchment(db,polygon,qa["rtree"])
     unions.append({"research_family":family,"reverse_road_travel_time_minutes":minute,
       "geographic_reference_market_count":len(CITIES),
       "road_reachable_country_scope":"Portugal Continental BGRI Census 2021 only (not Spanish areas)",
       "overlap_between_six_candidate_study_point_isochrones_counted_once":True,
       "total_2021_residents_in_nonoverlapping_road_isochrone_union":c["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
       "2021_resident_area_fraction_sensitivity":c["area_weighted_uniform_within_subsection_population_estimates"]["N_INDIVIDUOS"],
       "2021_age65_nonoverlapping_representative_count":c["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS_65_OU_MAIS"],
       "area_km2":round(polygon.area/1_000_000,2),
       "original_subsections_intersected":c["original_subsections_intersecting_area"],
       "no_public_transport_isolation_or_modal_choice_assumed":True,
       "road_polygon_representative_population_not_rail_demand":True})
     geo.append({"type":"Feature","geometry":mapping(transform(out.transform,polygon)),
       "properties":{"study_family":family,"layer":"union_6_study_reference_reverse_isochrones",
         "reverse_automobile_isochrone_arrival_minutes":minute,
         "INE_2021_original_residents_no_overlapping_double_count":c["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
         "not_rail_station_or_transport_service_isochrone":True}})
  finally:db.close()
 if len(single)!=54 or len(unions)!=9:raise ValueError("G17_missing_54_market_time_cases_or_9_family_unions")
 values={(x["research_family"],x["reverse_road_travel_time_minutes"]):x["total_2021_residents_in_nonoverlapping_road_isochrone_union"] for x in unions}
 for f in FAMILIES:
  if not values[f,15]<=values[f,30]<=values[f,45]:
   raise ValueError("2021_census_nonmonotonic_real_road_isochrone_union")
 result={"mission":"MN-GEO-RAIL-001",
   "stage":"G17_Valhalla_real_OSM_reverse_road_isochrones_2021_INE_residents",
   "timestamp_utc":datetime.now(timezone.utc).isoformat(),
   "source_ine_F67_original_sha256":F67_SHA,
   "source_2021_G14_census_georeferenced_study_references_sha256":G14_SHA,
   "source_2021_census_native_QA":qa,
   "router_base":"https://valhalla1.openstreetmap.de/isochrone",
   "router_public_demo_fair_use_original_network_OBSERVED":True,
   "distinct_public_router_requests":len(receipts),
   "routing_response_source_SHA_receipts":receipts,
   "acquisition_retries_failed_points":errors,
   "road_direction":"reverse_road_isocrone_from_area_TO_study_reference_for_arrival",
   "costing":"auto",
   "car_no_traffic_congestion_or_fuel_cost_or_transfer_time":True,
   "2021_resident_population_not_2026_population_or_rail_demand":True,
   "unknown_PT_network_not_zero_PT_supply":True,
   "public_transport_full_NUTS2_Norte_no_uniform_verified_network_data":True,
   "reference_points_not_real_station_parcels_or_rail_platforms":True,
   "no_engineering_CAPEX_euros_train_timetable_or_passenger_OD":True,
   "NUTS2_norte_and_PT_continental_census_no_Spanish_residents":True,
   "mandatory_urban_markets":["Vila Real","Bragança"],
   "other_urban_markets":["Guimarães","Amarante","Mirandela","Macedo de Cavaleiros"],
   "Sanabria_excluded":True,
   "three_research_families":list(FAMILIES),
   "54_source_city_minutes_cases":single,
   "9_original_2021_road_catchment_union_aggregates":unions,
   "Fxx_accepted":False,"Site_authorized":False}
 jsonpath.parent.mkdir(parents=True,exist_ok=True)
 jsonpath.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 geopath.parent.mkdir(parents=True,exist_ok=True)
 geopath.write_text(json.dumps({"type":"FeatureCollection",
   "name":"G17 true Valhalla reverse road isochrones 15/30/45mins around UNBUILT source research points; INE 2021 census","features":geo},ensure_ascii=False)+"\n")
 md=["# G17 — Áreas rodoviárias reais (rede OSM) e população residente INE 2021",
   "","Acessibilidade calculada por Valhalla com automóvel até pontos de investigação da linha, em modo **inverso (origem → interface)**, a 15/30/45 minutos. Os pontos não são estações reais, não estão verificados os acessos legais, não se inclui estacionamento/última milha, congestionamento, nem qualquer transporte público.",
   "","População dos Censos 2021 via subsecções BGRI original 203264. População de 2021, nunca procura de comboio, nunca estimativa atual de 2026.",
   "","## População na união dos seis mercados por alternativa, sem dupla contagem",
   "| Família | 15 minutos por estrada | 30 minutos por estrada | 45 minutos por estrada |",
   "|---|---:|---:|---:|"]
 for family in FAMILIES:
  md.append(f"| {family} | "+" | ".join(str(values[family,m]) for m in TIME_MINUTES)+" |")
 md+=["","## População nas áreas de 15 minutos por referência urbana",
   "| Família | Guimarães | Amarante | Vila Real* | Mirandela | Macedo de Cavaleiros | Bragança* |",
   "|---|---:|---:|---:|---:|---:|"]
 for family in FAMILIES:
  z={(x["research_family"],x["urban_market_reference"]):x for x in single if x["reverse_road_travel_time_minutes"]==15}
  md.append(f"| {family} | "+" | ".join(str(z[family,city]["2021_INE_census_residents_representative_point"]) for city in CITIES)+" |")
 md+=["","## Limites e condições de seleção",
  "- **Não existem dados homogéneos de horários/cobertura de transporte público para a NUTS II Norte**. Não se interpreta essa lacuna como inexistência de serviço ou acessibilidade nula.",
  "- Modelação rodoviária sem trânsito em tempo real; chegar a uma via junto de um eixo de grelha não implica estação fisicamente possível, plataforma ferroviária, acesso legal nem tempo real até ao comboio.",
  "- Contagens dos seis pontos não podem ser somadas devido a sobreposição. As uniões por corredor removem dupla contagem das áreas 15/30/45min.",
  "- A BGRI INE cobre Portugal continental; não se contabilizam populações espanholas, mesmo onde uma isócrona se estenda para Espanha.",
  "- Os mercados identificados por nome não são necessariamente centros das respetivas áreas, e uma área alcançável pode não incluir o centro dessa cidade.",
  "- São necessários localizações legais de estações, os tempos ferroviários e os custos CAPEX/OPEX auditados antes da seleção económica.",
  "","Validação sem recriar F67, sem Fxx/Site e sem inventar acessibilidades por transporte público.",""]
 markdown.parent.mkdir(parents=True,exist_ok=True);markdown.write_text("\n".join(md))
 print("G17_REAL_ROAD_POPULATION="+json.dumps({"requests":len(receipts),
  "road_reverse_true":True,
  "unions":[{"f":r["research_family"],"t":r["reverse_road_travel_time_minutes"],
     "p":r["total_2021_residents_in_nonoverlapping_road_isochrone_union"],
     "area":r["area_km2"]} for r in unions],
  "15min_city_pop":[{"f":r["research_family"],"city":r["urban_market_reference"],
     "p":r["2021_INE_census_residents_representative_point"]} for r in single if r["reverse_road_travel_time_minutes"]==15],
  "missing_PT_not_imputed":True},ensure_ascii=False,separators=(',',':')))
 return result

def main():
 p=argparse.ArgumentParser()
 for n in ("f67","g14","json","geojson","markdown"):p.add_argument("--"+n,required=True,type=Path)
 p.add_argument("--no-network",action="store_true")
 a=p.parse_args();execute(a.f67,a.g14,a.json,a.geojson,a.markdown,not a.no_network)
if __name__=="__main__":main()
