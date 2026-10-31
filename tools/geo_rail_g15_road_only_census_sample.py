#!/usr/bin/env python3
"""G15: sparse, explicitly incomplete road-only access evidence from INE BGRI21.

The NUTS2 Norte does not have uniformly verified GTFS bus/PT coverage for
integrated accessibility. NEVER treat unknown public transport as zero supply
or penalize a corridor for missing PT data. G15 uses 2021 residents near
sampled, road-snapped points; exact routings are OSRM non-traffic travel
durations. Unknown cells and untested rings remain unknown, not unreachable.

Primary INE 2021 BGRI geometric census + 2026 OSM routing demonstration.
Not a full road-network isochrone, municipal population, rail demand,
investment, validated station site or a PT service ranking.
"""
from __future__ import annotations
import argparse,hashlib,json,math,sqlite3,tempfile,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
from pyproj import Transformer
from shapely.geometry import Point
from geo_rail_g14_bgri2021_station_population import (
 F67_SHA,parse_gpkg_geometry,unpack_exact,native_qa,nonnegative_population
)

G14_SHA="af16f552634f066ad5723445d9bd6e389f5769a522b2782d7064bc206acc216d"
FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
CITIES=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
SAMPLE_GRID_M=4000
RADIUS_M=30000
MAX_CELLS_PER_SITE=145
MAX_BATCH_SIZE=40
MAX_GLOBAL_REQUESTS=48
PER_REQUEST_SLEEP_SEC=1.15
SOURCE_SNAP_LIMIT_M=600
DEST_SNAP_LIMIT_M=600
ROUTING="https://router.project-osrm.org/table/v1/driving/"
TIME_THRESHOLDS=(15,30,45)
MAX_BYTES_RESPONSE=220_000

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(2**20),b""):h.update(b)
 return h.hexdigest()

def station_sites(g14):
 cases=g14["all_54_city_research_geographic_buffer_census_cases"]
 if len(cases)!=54 or not g14["Sanabria_excluded"] or g14["Fxx_accepted"] or g14["Site_authorized"]:
  raise ValueError("original_G14_demography_research_scope_not_valid")
 out={}
 for f in FAMILIES:
  for c in CITIES:
   z=next((x for x in cases if x["research_corridor"]==f
     and x["urban_market"]==c and x["research_geographic_radius_km"]==10),None)
   if z is None:raise ValueError("missing_census_research_station_reference")
   out[(f,c)]=tuple(z["chosen_original_G13A_research_lonlat"])
 return out

def source_cells(db,road_reference,to_tm,to_geo):
 px,py=to_tm.transform(*road_reference)
 rt="rtree_BGRI21_CONT_geom"
 minx,miny,maxx,maxy=px-RADIUS_M,py-RADIUS_M,px+RADIUS_M,py+RADIUS_M
 q='''SELECT p.geom,p.N_INDIVIDUOS,p.N_INDIVIDUOS_65_OU_MAIS FROM "BGRI21_CONT" p
 JOIN "rtree_BGRI21_CONT_geom" rt ON rt.id=p.fid
 WHERE rt.maxx>=? AND rt.minx<=? AND rt.maxy>=? AND rt.miny<=?'''
 grouped=defaultdict(lambda:{"population":0,"age65":0,"records":0,
                    "max_pop":-1,"reference_xy":None})
 orig_total=orig_65=invalid=0
 center=Point(px,py)
 for raw,pop,age65 in db.execute(q,(minx,maxx,miny,maxy)):
  try:
   poly=parse_gpkg_geometry(raw)
   point=poly.representative_point()
  except Exception:
   invalid+=1;continue
  if point.distance(center)>RADIUS_M:continue
  n=nonnegative_population(pop)
  old=nonnegative_population(age65)
  if n is None:continue
  orig_total+=int(round(n))
  if old is not None:orig_65+=int(round(old))
  cell=(math.floor(point.x/SAMPLE_GRID_M),math.floor(point.y/SAMPLE_GRID_M))
  g=grouped[cell]
  g["population"]+=int(round(n))
  g["age65"]+=int(round(old)) if old is not None else 0
  g["records"]+=1
  if n>g["max_pop"]:
   g["max_pop"]=n;g["reference_xy"]=(point.x,point.y)
 # Select high-population cells first; NO claim of full coverage.
 ranked=sorted(grouped.items(),key=lambda p:(-p[1]["population"],p[0]))
 chosen=ranked[:MAX_CELLS_PER_SITE]
 samples=[]
 for (col,row),data in chosen:
  x,y=data["reference_xy"]
  lon,lat=to_geo.transform(x,y)
  samples.append({"grid_EPSG3763_4km_cell":[col,row],
   "source_subsections_assigned":data["records"],
   "INE_2021_census_residents_in_sampled_cell":data["population"],
   "INE_2021_census_age65_in_sampled_cell":data["age65"],
   "source_representative_populated_subsection_reference_lonlat":[round(lon,7),round(lat,7)],
   "router_2026_network_duration_minutes":None,
   "router_2026_network_distance_km":None,
   "road_snapping_accepted":False,
   "reason_unclassified":"not_queried_or_unroutable",
   "residents_are_2021_while_road_snapshot_is_2026":True})
 included=sum(x["INE_2021_census_residents_in_sampled_cell"] for x in samples)
 return {"screening_circle_radius_km":RADIUS_M//1000,
  "original_BRGI_representative_points_in_30km_circle_population":orig_total,
  "original_BRGI_65plus_in_30km_circle_population":orig_65,
  "original_intersections_unreadable_geometry":invalid,
  "populated_4km_cells_in_30km_circle":len(ranked),
  "4km_cells_sampled_most_populated_first":len(chosen),
  "sampled_cells_census_population":included,
  "excluded_unqueried_cells_2021_population":orig_total-included,
  "coarse_sample_grid_width_m":SAMPLE_GRID_M,
  "sampling_is_population_prioritized_and_not_random":True,
  "entire_study_universe_is_only_30km_euclidean":True,
  "sampled_cells":samples}

def osrm_table(station,points):
 # One list of sources (population reference locations) -> destination
 # (research point). No fallback_speed: missing route is unknown, not imputed.
 destinations=[station]+points
 coords=";".join(f"{lon:.7f},{lat:.7f}" for lon,lat in destinations)
 sources=";".join(str(i) for i in range(1,len(destinations)))
 url=ROUTING+coords+"?sources="+sources+"&destinations=0&annotations=duration,distance"
 if len(destinations)>MAX_BATCH_SIZE+1 or len(url)>6000:raise ValueError("source_road_table_URL_or_coordinate_budget")
 req=urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte-G15-road-sampled-census-research/1.0","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=55) as resp:
  if resp.status!=200:raise ValueError("OSRM_unavailable_HTTP_status")
  raw=resp.read(MAX_BYTES_RESPONSE+1)
 if len(raw)>MAX_BYTES_RESPONSE:raise ValueError("OSRM_response_exceeds_bound")
 d=json.loads(raw)
 if d.get("code")!="Ok":raise RuntimeError("OSRM_response_code_"+str(d.get("code")))
 if len(d.get("sources",[]))!=len(points) or len(d.get("destinations",[]))!=1:
  raise ValueError("source_destination_alignment_wrong")
 if len(d.get("durations",[]))!=len(points) or len(d.get("distances",[]))!=len(points):
  raise ValueError("OSRM_inconsistent_duration_distance")
 return {"receipt_SHA256":hashlib.sha256(raw).hexdigest(),
  "destination_snap_m":float(d["destinations"][0].get("distance",1e8)),
  "rows":[{"source_snap_m":float(item.get("distance",1e8)),
   "duration_minutes":round(float(d["durations"][i][0])/60,2)
      if d["durations"][i][0] is not None else None,
   "distance_km":round(float(d["distances"][i][0])/1000,2)
      if d["distances"][i][0] is not None else None}
    for i,item in enumerate(d["sources"])]}

def road_enrich(stations,screens,network,request_cap=MAX_GLOBAL_REQUESTS):
 # Dedup by station research WGS84 point: P2-2-1/P2-2-3 share all sites.
 references={}
 for k,station in stations.items():
  references.setdefault(station,[]).append(k)
 budgets=[];count=0;halted=False
 for reference,keys in references.items():
  # same site may have multiple attached cities in rare cases; ensure source
  # populations and reference points match exactly before sharing.
  master=screens[keys[0]]
  for k in keys[1:]:
   if len(screens[k]["sampled_cells"])!=len(master["sampled_cells"]):
    raise ValueError("same_coordinate_different_population_site_aggregation")
  items=master["sampled_cells"]
  receipt={"site_coordinate":reference,"families_markets":[list(k) for k in keys],
    "sampled_populated_cells":len(items),"request_blocks_attempted":0,
    "requests_not_retried_due_to_public_demo_limit":0,
    "status":"public_OSRM_available" if network else "network_explicitly_disabled"}
  if network and not halted:
   for start in range(0,len(items),MAX_BATCH_SIZE):
    batch=items[start:start+MAX_BATCH_SIZE]
    if count>=request_cap:
     halted=True;receipt["status"]="public_demo_global_request_cap_reached";break
    count+=1;receipt["request_blocks_attempted"]+=1
    try:
     ans=osrm_table(reference,[tuple(x["source_representative_populated_subsection_reference_lonlat"]) for x in batch])
     budgets.append({"site":reference,"block":start//MAX_BATCH_SIZE,
       "SHA256_of_live_OSM_routing_response":ans["receipt_SHA256"],
       "destination_snap_m":round(ans["destination_snap_m"],1),
       "query_size":len(batch)})
     for item,row in zip(batch,ans["rows"]):
      ok=(row["source_snap_m"]<=SOURCE_SNAP_LIMIT_M and
          ans["destination_snap_m"]<=DEST_SNAP_LIMIT_M and
          row["duration_minutes"] is not None)
      item["road_snapping_accepted"]=ok
      item["reason_unclassified"]=None if ok else "unrouted_or_road_snap_greater_than_600m"
      if ok:
       item["router_2026_network_duration_minutes"]=row["duration_minutes"]
       item["router_2026_network_distance_km"]=row["distance_km"]
    except Exception as ex:
     receipt.setdefault("OSRM_failures",[]).append({"block":start//MAX_BATCH_SIZE,"kind":type(ex).__name__})
    time.sleep(PER_REQUEST_SLEEP_SEC)
  if network and halted:receipt["requests_not_retried_due_to_public_demo_limit"]=len(items)
  for k in keys[1:]:
   original=screens[k]["sampled_cells"]
   for old,new in zip(original,master["sampled_cells"]):
    old.update({x:new.get(x) for x in ("road_snapping_accepted","router_2026_network_duration_minutes",
      "router_2026_network_distance_km","reason_unclassified")})
  budgets.append(receipt)
 return {"observed_utc":datetime.now(timezone.utc).isoformat(),
  "actual_total_queries":count,"global_bound_requests":request_cap,"site_receipts":budgets,
  "no_network_skipping_is_never_assumed_unreachable":True}

def aggregate_access(s):
 cls={}
 for t in TIME_THRESHOLDS:
  included=[x for x in s["sampled_cells"]
    if x["router_2026_network_duration_minutes"] is not None and
       x["router_2026_network_duration_minutes"]<=t]
  cls[str(t)]={"qualifying_population_2021_from_road_samplings":sum(x["INE_2021_census_residents_in_sampled_cell"] for x in included),
   "qualifying_65plus_2021_from_road_samplings":sum(x["INE_2021_census_age65_in_sampled_cell"] for x in included),
   "qualifying_4km_cells":len(included)}
 classified=[x for x in s["sampled_cells"] if x["router_2026_network_duration_minutes"] is not None]
 validpop=sum(x["INE_2021_census_residents_in_sampled_cell"] for x in classified)
 unknown=s["original_BRGI_representative_points_in_30km_circle_population"]-validpop
 if unknown<0:raise ValueError("population_larger_than_source_geographic_universe")
 return {"route_times_to_nonstation_road_snap_during_2026_observation":True,
   "population_2021_with_a_classified_routing_reference":validpop,
   "population_2021_without_a_classified_routing_reference":unknown,
   "population_2021_original_study_geography_denominator":s["original_BRGI_representative_points_in_30km_circle_population"],
   "fraction_of_2021_population_sampled_and_routed":round(validpop/max(1,validpop+unknown),4),
   "unclassified_must_not_be_treated_as_unreachable":True,
   "conservative_nonstation_sampled_road_coverage_by_time_minutes":cls}

def workflow(original_zip,g14path,jsonpath,mdpath,network=True,cap=MAX_GLOBAL_REQUESTS):
 if sha(g14path)!=G14_SHA:raise ValueError("source_G14_SHA_original_changed")
 g14=json.loads(g14path.read_text())
 if g14["sources"]["F67_public_exact_INE_cont_2021_sha256"]!=F67_SHA:raise ValueError("G14_original_INE_wrong")
 sites=station_sites(g14)
 to_tm=Transformer.from_crs(4326,3763,always_xy=True)
 to_geo=Transformer.from_crs(3763,4326,always_xy=True)
 cases={}
 with tempfile.TemporaryDirectory(prefix="g15_exact_bgri_") as d:
  p=unpack_exact(original_zip,Path(d))
  db=sqlite3.connect(f"file:{p}?mode=ro",uri=True,timeout=30)
  try:
   native=native_qa(db)
   # First compute unique research sites only, then reuse identical evidence
   # for P2-2-1 and P2-2-3.
   cache={}
   for key,station in sites.items():
    if station not in cache:cache[station]=source_cells(db,station,to_tm,to_geo)
    cases[key]=json.loads(json.dumps(cache[station]))
  finally:db.close()
 route_receipts=road_enrich(sites,cases,network,cap)
 rows=[]
 for key,station in sites.items():
  case=cases[key]
  row=aggregate_access(case)
  rows.append({"research_family":key[0],"associated_urban_market":key[1],
   "road_snapped_research_point_lonlat":station,
   "source_population_coverage_30km_census_screen":{k:v for k,v in case.items() if k!="sampled_cells"},
   "road_sample_classification":row,"original_sampled_population_cells":case["sampled_cells"],
   "not_rail_station_access":True,"not_complete_isochrone":True})
 if len(rows)!=18:raise ValueError("18_source_market_cases_expected")
 result={"mission":"MN-GEO-RAIL-001","stage":"G15_road_only_BRGI2021_population_representative_point_routing_sample",
  "utc":datetime.now(timezone.utc).isoformat(),
  "source_sha256":{"INE_BRGI21_CONT":F67_SHA,"G14_source_market_references":G14_SHA},
  "population_year":2021,"OSM_road_routing_observation_year":2026,
  "mandatory_markets":["Vila Real","Bragança"],
  "additional_markets":["Guimarães","Amarante","Mirandela","Macedo de Cavaleiros"],
  "Sanabria_excluded":True,
  "public_transport_assessment_scope":"NUTS2 Norte systematic comparable service data not available: excluded from scoring",
  "lack_of_GTFS_or_service_data_DOES_NOT_mean_no_bus_or_public_transport":True,
  "PT_waiting_travel_frequency_door_to_door_times_not_inferred":True,
  "no_weight_or_zero_penalty_for_missing_PT_data":True,
  "feeder_bus_options_may_be_defined_as_unquantified_future_scenarios_only":True,
  "road_census_model":"2021 BGRI subsection resident counts aggregated to 4km cell; representative populated subsection used for OSRM to notional non-station study point",
  "road_sample_maximum_euclidean_radius_km":RADIUS_M//1000,
  "road_population_4km_grid_not_accurate_to_full_road_isochrone":True,
  "road_time_coverage_is_conditional_on_sample_and_snap_not_full_station_catchment":True,
  "no_network_response_means_unknown_not_zero":True,
  "no_station_legally_or_geometrically_verified":True,
  "no_census_2026_or_train_demand_claim":True,
  "Fxx_accepted":False,"Site_authorized":False,
  "GPKG_validation":native,"source_road_network_query_receipts":route_receipts,
  "all_18_family_city_population_road_research_screen":rows}
 jsonpath.parent.mkdir(parents=True,exist_ok=True)
 jsonpath.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 md=["# G15 — acessibilidade rodoviária exploratória e população residente INE 2021",
   "","Não se atribuiu zero a transporte público: a inexistência de dados comparáveis à escala NUTS II Norte impede classificá-lo. G15 exclui-o das pontuações; acessibilidade futura a pé, autocarro, frequência e espera ficam indeterminadas.",
   "A análise rodoviária é **incompleta por definição**: agrupamento de subsecções BGRI em quadrículas 4 km, ponto representativo do conjunto de maior população, consulta OSRM real de 2026 de cada ponto de origem ao *ponto rodoviário* próximo da localização G13A. Distâncias máximas 30 km em linha reta; nem todos os pontos têm vias validamente próximas (snap ≤600 m). As parcelas não amostradas ou não encaminhadas são desconhecidas, não inacessíveis.",
   "","| Família | Mercado associado | População INE 2021 no círculo de 30 km | População com tempo rodoviário classificado | ≤15 min (amostra) | ≤30 min (amostra) | % do universo classificado |",
   "|---|---|---:|---:|---:|---:|---:|"]
 for item in rows:
  data=item["road_sample_classification"];pop=item["source_population_coverage_30km_census_screen"]
  md.append(f"| {item['research_family']} | {item['associated_urban_market']} | {pop['original_BRGI_representative_points_in_30km_circle_population']} | {data['population_2021_with_a_classified_routing_reference']} | {data['conservative_nonstation_sampled_road_coverage_by_time_minutes']['15']['qualifying_population_2021_from_road_samplings']} | {data['conservative_nonstation_sampled_road_coverage_by_time_minutes']['30']['qualifying_population_2021_from_road_samplings']} | {100*data['fraction_of_2021_population_sampled_and_routed']:.1f}% |")
 md+=["","Os valores por mercado não podem ser somados para representar a população total da linha (as áreas de influência sobrepõem-se). A metodologia privilegia células com maior população residente, pelo que os limiares são indicadores de amostra, não estimativas não enviesadas de procura ou de acessibilidade de toda a população da área.",
 "A melhoria exigida antes de uma decisão financeira é utilizar um grafo rodoviário local completo versionado/validado, com modelação de todas as origens e destino de estação realmente implantável, procura OD e CBA. Manter cenários de transporte de ligação apenas como opção não quantificada, porque PT está fora de medição.",
 "Sem custos ou estação certificada; Sanábria excluída, Vila Real e Bragança obrigatórias; sem novos INE, Fxx, Site.",""]
 mdpath.parent.mkdir(parents=True,exist_ok=True);mdpath.write_text("\n".join(md))
 print("G15_ROAD_ONLY="+json.dumps({"count":len(rows),
  "routing":{k:v for k,v in route_receipts.items() if k!="site_receipts"},
  "families":[{"f":x["research_family"],"city":x["associated_urban_market"],
   "known":x["road_sample_classification"]["population_2021_with_a_classified_routing_reference"],
   "den":x["road_sample_classification"]["population_2021_original_study_geography_denominator"],
   "pop15":x["road_sample_classification"]["conservative_nonstation_sampled_road_coverage_by_time_minutes"]["15"]["qualifying_population_2021_from_road_samplings"],
   "pop30":x["road_sample_classification"]["conservative_nonstation_sampled_road_coverage_by_time_minutes"]["30"]["qualifying_population_2021_from_road_samplings"]} for x in rows]},ensure_ascii=False,separators=(',',':')))
 return result

def main():
 p=argparse.ArgumentParser()
 for n in ("original","g14","json","markdown"):p.add_argument("--"+n,required=True,type=Path)
 p.add_argument("--no-network",action="store_true")
 p.add_argument("--max-requests",type=int,default=MAX_GLOBAL_REQUESTS)
 a=p.parse_args()
 if not 0<=a.max_requests<=MAX_GLOBAL_REQUESTS:raise ValueError("public_network_request_cap")
 workflow(a.original,a.g14,a.json,a.markdown,not a.no_network,a.max_requests)
if __name__=="__main__":main()
