#!/usr/bin/env python3
"""G18 actual 2021 INE resident road accessibility by hypothetical train stop pattern.

NO new routing queries: source is exact G17 Valhalla reverse-drive polygon
evidence. Four G12-type hypothetical stopping patterns, including compulsory
Vila Real and Bragança, are evaluated separately to avoid assuming all six
candidate urban nodes become actual stations with trains stopping. No PT
coverage is imputed; road driving times are not rail travel times or ridership.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,sqlite3,tempfile
from pathlib import Path
from datetime import datetime,timezone
from shapely.geometry import shape
from shapely.ops import transform,unary_union
from pyproj import Transformer
from geo_rail_g14_bgri2021_station_population import F67_SHA,unpack_exact,native_qa,catchment

FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
MINUTES=(15,30,45)
REQUIRED={"Vila Real","Bragança"}
CITIES=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
SCENARIOS={
 "EXP_VR_BR_only":("Vila Real","Bragança"),
 "REG_VR_BR_Amarante_Mirandela_Macedo":("Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança"),
 "REG_VR_BR_Guimaraes_Mirandela_Macedo":("Guimarães","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança"),
 "REG_all_six":CITIES
}

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as fd:
  for x in iter(lambda:fd.read(2**20),b""):h.update(x)
 return h.hexdigest()

def source_polygons(g17,geo):
 if len(g17["54_source_city_minutes_cases"])!=54 or len(g17["9_original_2021_road_catchment_union_aggregates"])!=9:
  raise ValueError("G18_original_G17_real_roads_source_missing")
 if g17["source_ine_F67_original_sha256"]!=F67_SHA or not g17["unknown_PT_network_not_zero_PT_supply"]:
  raise ValueError("G18_do_not_impute_public_transport_or_mismatch_original_census")
 if not g17["Sanabria_excluded"] or g17["Fxx_accepted"] or g17["Site_authorized"]:
  raise ValueError("G18_original_governance_scope_failed")
 features=[f for f in geo["features"] if f.get("properties",{}).get("road_polygon_research_study") is not True
     and "associated_urban_market" in f.get("properties",{})]
 # All city/time source geometry features are actual source polygons, not union layers.
 if len(features)!=54:raise ValueError("G18_missing_54_city_time_source_geojson_features")
 to_pt=Transformer.from_crs(4326,3763,always_xy=True)
 polygons={}
 for x in features:
  p=x["properties"]
  key=(p["study_family"],p["associated_urban_market"],p["reverse_automobile_isochrone_arrival_minutes"])
  if key in polygons:raise ValueError("duplicate_real_road_isochrone_site")
  polygons[key]=transform(to_pt.transform,shape(x["geometry"]))
 if len(polygons)!=54:raise ValueError("source_geometry_key_incomplete")
 return polygons

def calc(zipfile,g17source,g17geo,jsonpath,csvpath,mdpath):
 g17=json.loads(g17source.read_text()); geo=json.loads(g17geo.read_text())
 poly=source_polygons(g17,geo)
 source_all={(r["research_family"],r["reverse_road_travel_time_minutes"]):r
     for r in g17["9_original_2021_road_catchment_union_aggregates"]}
 for names in SCENARIOS.values():
  if not REQUIRED.issubset(names):raise ValueError("hypothetical_train_pattern_omits_required_city")
 results=[]
 counted={}
 with tempfile.TemporaryDirectory(prefix="MN-G18-original-INe-") as t:
  gpkg=unpack_exact(zipfile,Path(t))
  db=sqlite3.connect(f"file:{gpkg}?mode=ro",uri=True,timeout=45)
  try:
   qa=native_qa(db)
   for family in FAMILIES:
    for case,cities in SCENARIOS.items():
     for minute in MINUTES:
      sources=[poly[(family,city,minute)] for city in cities]
      # Share an exact hash of native polygon shapes across P2/2 family references
      # but never share different urban markets merely because city names match.
      sig=hashlib.sha256(b"|".join(sorted(p.wkb for p in sources))).hexdigest()
      if sig not in counted:
       merged=unary_union(sources)
       census=catchment(db,merged,qa["rtree"])
       counted[sig]={"population":census["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
        "area_weighted":census["area_weighted_uniform_within_subsection_population_estimates"]["N_INDIVIDUOS"],
        "age65":census["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS_65_OU_MAIS"],
        "source_original_subsections":census["original_subsections_intersecting_area"],
        "road_polygon_union_km2":round(merged.area/1e6,2)}
      entry=counted[sig]
      results.append({"research_family":family,"hypothetical_rail_stop_pattern":case,
       "hypothetical_stop_markets":list(cities),
       "hypothetical_stop_count":len(cities),
       "reverse_road_arrival_time_minutes":minute,
       "2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand":entry["population"],
       "2021_residents_area_weighted_sensitivity":entry["area_weighted"],
       "2021_residents_age65plus":entry["age65"],
       "original_subsections_intersected":entry["source_original_subsections"],
       "surface_area_km2":entry["road_polygon_union_km2"],
       "source_2021_census_not_current_residents":True,
       "every_named_market_stop_is_HYPOTHETICAL_and_not_engineered":True,
       "no_bus_or_PT_access_estimates":True,
       "no_rail_dwell_time_station_capex_or_actual_rail_service_feasibility":True})
  finally:db.close()
 if len(results)!=36:raise ValueError("G18_3_families_x_4_train_service_patterns_x_3_road_arrival_times_not_complete")
 ix={(r["research_family"],r["hypothetical_rail_stop_pattern"],r["reverse_road_arrival_time_minutes"]):r for r in results}
 for f in FAMILIES:
  for case in SCENARIOS:
   series=[ix[f,case,t]["2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"] for t in MINUTES]
   if series!=sorted(series):raise ValueError("nonmonotonic_source_road_reachable_2021_population_by_time")
  for t in MINUTES:
   # All six stations must reproduce the independently calculated G17 true source:
   actual=ix[f,"REG_all_six",t]["2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"]
   ref=source_all[f,t]["total_2021_residents_in_nonoverlapping_road_isochrone_union"]
   if actual!=ref:raise ValueError(f"G18_true_six_site_union_not_equal_G17_source_{f}_{t}")
   exp=ix[f,"EXP_VR_BR_only",t]["2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"]
   if exp>actual:raise ValueError("express_only_cannot_exceed_all_sites_reachability")
 for rec in results:
  base=ix[rec["research_family"],"EXP_VR_BR_only",rec["reverse_road_arrival_time_minutes"]]
  rec["extra_2021_residents_geographically_reached_vs_VR_BR_only"]=rec[
     "2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"]-base[
     "2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"]
  rec["incremental_residents_NOT_passenger_ridership_or_real_travel_benefit"]=True
 out={"mission":"MN-GEO-RAIL-001",
  "stage":"G18_actual_2021_INE_resident_auto_reach_by_hypothetical_rail_station_stopping_pattern",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "sources_SHA256":{"F67_original_INE_2021":F67_SHA,
    "G17_true_reverse_road_census_json":sha(g17source),
    "G17_true_reverse_road_geojson":sha(g17geo)},
  "source_native_2021_population_QA":qa,
  "source_original_valhalla_real_road_response_SHA_receipts_reused_no_new_OSM_queries":True,
  "unique_population_polygon_unions_calculated":len(counted),
  "three_geographic_research_families":list(FAMILIES),
  "two_obligatory_rail_service_cities":["Vila Real","Bragança"],
  "additional_cities_are_potential_not_compulsory":["Guimarães","Amarante","Mirandela","Macedo de Cavaleiros"],
  "Sanabria_excluded":True,
  "uniform_NUTS2_Norte_GTFS_unavailable_and_never_imputed":True,
  "actual_proven_station_sites":0,
  "study_service_patterns_have_no_actual_railway_geometry_or_CBA_CAPEX":True,
  "2021_population_on_2026_network_not_current_or_train_ridership":True,
  "auto_transport_only_not_public_transit_or_last_mile_to_platform":True,
  "36_family_stop_pattern_road_time_geographic_population_screens":results,
  "Fxx_accepted":False,"Site_authorized":False}
 jsonpath.parent.mkdir(parents=True,exist_ok=True)
 jsonpath.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 csvpath.parent.mkdir(parents=True,exist_ok=True)
 with csvpath.open("w",encoding="utf8",newline="") as file:
  w=csv.DictWriter(file,fieldnames=("family","pattern","stops","auto_time_minutes",
    "2021_reachable_residents","additional_residents_vs_express"))
  w.writeheader()
  for v in results:w.writerow({"family":v["research_family"],"pattern":v["hypothetical_rail_stop_pattern"],
    "stops":v["hypothetical_stop_count"],"auto_time_minutes":v["reverse_road_arrival_time_minutes"],
    "2021_reachable_residents":v["2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"],
    "additional_residents_vs_express":v["extra_2021_residents_geographically_reached_vs_VR_BR_only"]})
 md=["# G18 — Cenários de paragens ferroviárias e população acessível por estrada",
  "","**Quatro hipóteses de serviço, sem qualquer estação validada:** expresso obrigatório Vila Real–Bragança; regional com Amarante/Mirandela/Macedo; regional com Guimarães/Mirandela/Macedo; e opção hipotética que serve os seis pontos. As áreas são isócronas de automóvel de chegada aos pontos (Valhalla/OSM) e residentes INE 2021, não previsões de procura ou horário ferroviário.",
  "","O transporte público não foi estimado porque não existe cobertura sistemática utilizável para toda a NUTS II Norte; a falta de dados não representa ausência de serviço.",
  "","## Residentes geograficamente abrangidos em 30 minutos de automóvel, por padrão de serviço",
  "| Família | Apenas VR–BR | Com Amarante/Mirandela/Macedo | Com Guimarães/Mirandela/Macedo | Todos os seis pontos |",
  "|---|---:|---:|---:|---:|"]
 for f in FAMILIES:
  md.append(f"| {f} | "+" | ".join(str(ix[f,p,30][
   "2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"]) for p in SCENARIOS)+" |")
 md+=["","A população adicional face ao expresso mede apenas um maior universo de residentes na envolvente rodoviária de **pontos de investigação adicionais**. Não representa novos passageiros, melhoria de bem-estar, ocupação de comboios nem acessos comprovados a uma estação. A solução em seis pontos poderá exigir desvios de traçado, interfaces adicionais, paragens e custos relevantes.",
  "A prioridade seguinte é uma análise geométrica de estação/traçado que valide quais os mercados opcionais podem efetivamente ser servidos em cada família; depois avaliar tempos ferroviários e custos marginais das paragens.",
  "","Sem novos acessos à rede OSM nem nova aquisição F67; sem publicação canónica Fxx/Site.",""]
 mdpath.parent.mkdir(parents=True,exist_ok=True)
 mdpath.write_text("\n".join(md))
 print("G18_REAL_STOP_PATTERNS="+json.dumps({"unique_source_unions":len(counted),
  "30minutes":[{"f":f,"case":p,"n":ix[f,p,30]["2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"],
     "increment":ix[f,p,30]["extra_2021_residents_geographically_reached_vs_VR_BR_only"]} for f in FAMILIES for p in SCENARIOS],
  "all_six_verified_matches_source":True,"no_rail_cost_or_PT_imputation":True},ensure_ascii=False,separators=(',',':')))
 return out

def main():
 a=argparse.ArgumentParser()
 for n in ("f67","g17","geojson","json","csv","markdown"):a.add_argument("--"+n,type=Path,required=True)
 p=a.parse_args()
 calc(p.f67,p.g17,p.geojson,p.json,p.csv,p.markdown)
if __name__=="__main__":main()
