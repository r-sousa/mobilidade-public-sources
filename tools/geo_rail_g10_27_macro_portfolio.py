#!/usr/bin/env python3
"""MN-GEO-RAIL-001 G10: expand 3 independent spatial alternatives per module into 27.

This is a REAL-SOURCE prefeasibility screening portfolio over archived G5/G3/G4
and regional Copernicus GLO30 *surface* pixels, not rail track alignments.
Provides transparent running-time geometry index and DSM earthwork-pressure
risk PROXIES. Never implies investment euros, actual station catchments,
road travel times, rail speeds or verified rail engineering feasibility.
"""
from __future__ import annotations
import argparse,itertools,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
from collections import Counter
import numpy as np
import rasterio
from geo_rail_g6_full_research_chains import join_checked,validate_sources
from geo_rail_g3_continuity_open_dsm_sources import cell_ids
from geo_rail_pt_b1_dgt_review_grids import inventory
from geo_rail_g7_rail_screen import choose_geometry,sample_dsm,vertical_pressure,DSM_SHA,SPEEDS

G3_SHA="ab001fb17ba359d939294b505bc199d459d474095f255f17099c1cdaafd57d9c"
G4_SHA="7d7a513fd248fcef86453da1967baf20d7359e9f66672fd7e5c4d2e7899ed200"
G5_SHA="a4cb8be1443b8be484303934595dfb8ffecaeb6b7857dc0a1ee1569956adfc32"
G6_SHA="faa2f1d218c79a3647a0d32217ab7bd460cc8aed418750ac62b41844d2d5bc9d"
LEG_NAMES=("P1_AFSC_to_Vila_Real_W","P3_Vila_Real_E_to_Braganca_W","P5_Braganca_E_to_Zamora")
CITY_CONNECTORS=("Vila_Real_W_to_E","Braganca_W_to_E")
CITY_ANCHORS=((20000,180000),(40000,184000),(110000,234000),(116000,238000))
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()

def research_grid_length_km(path):
 return round(sum(math.dist(a,b) for a,b in zip(path,path[1:]))/1000,3)

def local_links(g3):
 links={q["link"]:q for q in g3["links"]}
 out={}
 for name in CITY_CONNECTORS:
  scenarios=[v for v in links[name]["solutions"] if v["mode"]=="short"]
  if len(scenarios)!=1 or scenarios[0]["status"]!="exploratory_2km_DSM_source_catalog_lattice_connected":
   raise ValueError("G3_verified_city_connector_missing")
  out[name]=[tuple(p) for p in scenarios[0]["route_sector_cells"]]
 return out

def compose(g3,g5):
 city=local_links(g3)
 legs={q["leg"]:q["variants"] for q in g5["legs"]}
 if set(legs)!=set(LEG_NAMES) or any(len(legs[k])!=3 for k in LEG_NAMES):
  raise ValueError("source_G5_not_three_variants_per_research_module")
 out=[]
 for choices in itertools.product(range(3),repeat=3):
  parts=[[tuple(p) for p in legs[LEG_NAMES[0]][choices[0]]["source_grid_positions_pttm06"]],
         city[CITY_CONNECTORS[0]],
         [tuple(p) for p in legs[LEG_NAMES[1]][choices[1]]["source_grid_positions_pttm06"]],
         city[CITY_CONNECTORS[1]],
         [tuple(p) for p in legs[LEG_NAMES[2]][choices[2]]["source_grid_positions_pttm06"]]]
  path=join_checked(parts)
  if len(set(path))!=len(path):
   raise ValueError("source_G5_combination_self_crossed_lattice")
  if not all(p in path for p in CITY_ANCHORS):
   raise ValueError("G10_city_service_anchor_not_contained")
  cid="P"+str(choices[0]+1)+"-"+str(choices[1]+1)+"-"+str(choices[2]+1)
  out.append((cid,tuple(x+1 for x in choices),path))
 if len(out)!=27 or len(set(cid for cid,_,_ in out))!=27:
  raise ValueError("G10_not_27_distinct_combinations")
 # All combinations must be geographically unique, not merely relabelled.
 if len({tuple(path) for _,_,path in out})!=27:
  raise ValueError("G10_duplicate_route_lattice_geometries")
 return out

def nondominated(rows,grade):
 if grade=="passenger25":
  p90="passenger25_DSM_p90_m";frac="passenger25_DSM_fraction_gt25m"
 else:
  p90="mixed18_DSM_p90_m";frac="mixed18_DSM_fraction_gt25m"
 suitable=[z for z in rows if z["horizontal_radius_research_screen_pass"]]
 ans=[]
 # A proxy Pareto front, not a feasibility or cost-benefit optimum.
 for a in suitable:
  ax=[a["smoothed_research_grid_length_km_not_rail_track"],a[p90],a[frac]]
  if not any((b is not a and
      b["smoothed_research_grid_length_km_not_rail_track"]<=ax[0]+1e-8 and
      b[p90]<=ax[1]+1e-8 and
      b[frac]<=ax[2]+1e-8 and
      (b["smoothed_research_grid_length_km_not_rail_track"]<ax[0]-1e-8 or
       b[p90]<ax[1]-1e-8 or b[frac]<ax[2]-1e-8)) for b in suitable):
   ans.append(a["combination_id"])
 return sorted(ans)

def compute(g3path,g4path,g5path,g6path,b1path,dsm_path,catalog_path,jpath,mdpath):
 for path,d in ((g3path,G3_SHA),(g4path,G4_SHA),(g5path,G5_SHA),
                (g6path,G6_SHA),(dsm_path,DSM_SHA)):
  if sha(path)!=d:raise ValueError("verified_source_SHA256_not_matched_"+path.name)
 g3=json.loads(g3path.read_text());g4=json.loads(g4path.read_text())
 g5=json.loads(g5path.read_text());g6=json.loads(g6path.read_text())
 b1=json.loads(b1path.read_text())
 cat,proofs=inventory(catalog_path)
 native,acquired=validate_sources(g3,g4,g5,b1,cat)
 if (g6["mandatory_service_areas"]!=["Vila Real","Bragança"] or
     not g6["Sanabria_excluded"] or g6["Fxx_accepted"] or g6["Site_authorized"]):
  raise ValueError("G6_source_governance_contract_not_preserved")
 links=compose(g3,g5)
 checked={l[0]:l[2] for l in links}
 for i in range(1,4):
  prior=g6["end_to_end_research_chains"][i-1]
  ref="P"+str(i)+"-"+str(i)+"-"+str(i)
  if [list(p) for p in checked[ref]]!=prior["source_grid_cells_epsg3763"]:
   raise ValueError("diagonal_G6_research_chain_not_exactly_preserved_"+ref)
 rows=[];coverage=Counter()
 with rasterio.open(dsm_path) as ds:
  if ds.crs is None or ds.crs.to_epsg()!=4326:
   raise ValueError("source_DSM_not_epsg4326")
  for cid,comb,path in links:
   full=sum(tuple(p) in native for p in path)
   catalogued=sum(cell_ids(cat,*p) is not None for p in path)
   for p in set(path):
    if p not in native:coverage[tuple(p)]+=1
   xy_source=[(p[0]+1000,p[1]+1000) for p in path]
   for speed,radius in SPEEDS.items():
    selection,attempts=choose_geometry(xy_source,radius)
    r={"combination_id":cid,
       "module_options":{"P1":comb[0],"P3":comb[1],"P5":comb[2]},
       "speed_scenario_kmh":speed,
       "source_2km_research_cell_count":len(path),
       "source_2km_grid_length_km_not_rail_track":research_grid_length_km(path),
       "DGT_original_ground_full_2km_grid_sector_count":full,
       "DGT_original_ground_full_2km_grid_sector_fraction":round(full/len(path),4),
       "official_DGT_original_catalog_4source_cell_count":catalogued,
       "horizontal_radius_screen_threshold_m":radius,
       "horizontal_radius_research_screen_pass":selection is not None,
       "mandatory_Vila_Real_Braganca_source_city_connector_present":True,
       "real_station_location_or_road_intermodal_access_evaluated":False,
       "actual_rail_travel_time_evaluated":False,
       "actual_rail_construction_and_lifecycle_costs_evaluated":False}
    if selection:
     xy,proof=selection
     dem=sample_dsm(ds,xy)
     v18=vertical_pressure(xy,dem,18.)
     v25=vertical_pressure(xy,dem,25.)
     length=proof["screening_length_km_not_rail_distance"]
     r.update({"smoothed_research_grid_length_km_not_rail_track":length,
       "research_radius_test_min_m":proof["min_proxy_radius_m"],
       "max_shift_from_lattice_source_research_m":proof["max_distance_to_source_research_polyline_m"],
       # It is a geometry-only comparison index; it is NOT a bound on the
       # actual passenger door-to-door nor a reliable train running time.
       "hypothetical_length_divided_by_speed_minutes_NOT_train_travel_time":round(length/speed*60,2),
       "mixed18_DSM_p90_m":v18["p90_abs_line_vs_DSM_surface_m"],
       "mixed18_DSM_fraction_gt25m":v18["fraction_of_profile_distance_with_DSM_pressure_gt25m_proxy"],
       "passenger25_DSM_p90_m":v25["p90_abs_line_vs_DSM_surface_m"],
       "passenger25_DSM_fraction_gt25m":v25["fraction_of_profile_distance_with_DSM_pressure_gt25m_proxy"]})
    rows.append(r)
 if len(rows)!=81:raise ValueError("G10_NOT_81_SPEED_ROWS")
 pareto={}
 for speed in SPEEDS:
  part=[v for v in rows if v["speed_scenario_kmh"]==speed]
  pareto[str(speed)]={k:nondominated(part,k) for k in ("mixed18","passenger25")}
  if not any(z["horizontal_radius_research_screen_pass"] for z in part):
   raise ValueError("G10_no_valid_radius_screen_at_speed")
  minlen=min(z["smoothed_research_grid_length_km_not_rail_track"] for z in part if z["horizontal_radius_research_screen_pass"])
  for z in part:
   z["research_length_index_relative_to_minimum_percent"]=round(100*z["smoothed_research_grid_length_km_not_rail_track"]/minlen,2) if z["horizontal_radius_research_screen_pass"] else None
 # Favor different geographic areas, not just different speed labels:
 # choose at most one of each pair of close geographic source-cell routes.
 jaccard=[]
 for i,(cid,_,path) in enumerate(links):
  a=set(path)
  jaccard.append({"id":cid,"maximum_source_cell_Jaccard_with_other_26":round(
     max(len(a&set(b))/len(a|set(b)) for k,_,b in links if k!=cid),4)})
 result={"mission":"MN-GEO-RAIL-001",
  "stage":"G10_27_G5_combinations_3speed_proxy_evidence_for_early_diversification",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "source_SHA256":{"G3":G3_SHA,"G4":G4_SHA,"G5":G5_SHA,"G6":G6_SHA,"source_Copernicus_DSM":DSM_SHA},
  "source_official_DGT_catalogues_sha_receipts":proofs,
  "total_combinations":27,"speed_scenarios":[160,200,250],
  "total_speed_reviews":81,"module_assembly":"3_P1_x_3_P3_x_3_P5_plus_mandatory_G3_city_connectors",
  "all_27_geometrically_distinct_source_lattice_sequences":True,
  "service_cities":["Vila Real","Bragança"],"peripheral_stations_allowed":True,
  "Sanabria_excluded":True,
  "city_service_connector_is_only_topological_proximity_not_proven_node_access":True,
  "no_actual_road_network_intermodality_minutes":True,
  "no_actual_station_catchment_or_interchange_penalty":True,
  "no_actual_train_running_timetable_dwell_or_door_to_door_minutes":True,
  "geometry_speed_index_is_just_research_grid_km_divided_by_aspirational_speed":True,
  "no_actual_cost_euros_or_earthwork_or_tunnel_viaduct_quantities":True,
  "DSM_30m_has_vegetation_buildings_is_not_true_terrain_DTM":True,
  "native_DGT_full_121km2_is_spatially_discontinuous":True,
  "technical_rail_speed_or_engineering_feasibility_not_proven":True,
  "do_minimum_CBA_reference_not_yet_modelled":True,
  "cost_pressure_DSM_only_not_construction_cost":True,
  "real_railway_station_and_road_driving_times_missing":True,
  "G6_three_reference_diagonal_combinations_preserved":True,
  "full_original_DGT_ground_coverage_km2":121,
  "recommended_portfolio_selection_rule":"pareto_length_and_surface_topographic_proxy_per_speed_plus_geographic_diversity; NEVER decision on unmeasured_cost_access_service",
  "Pareto_exploratory_study_front_by_speed_and_traffic_case":pareto,
  "similarity_to_nearest_other_candidate":jaccard,
  "distinct_without_full_DGT_original_grid_sectors_intersected":len(coverage),
  "not_new_DGT_auth_downloads":True,
  "Fxx_accepted":False,"Site_authorized":False,
  "scenario_rows":rows}
 jpath.parent.mkdir(parents=True,exist_ok=True)
 jpath.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
 md=["# G10 — 27 alternativas macroscópicas combinadas e 3 velocidades", "",
  "**27 combinações geograficamente distintas (P1, P3, P5) sobre as fontes reais G3–G6.** As 81 linhas de cenário usam MDS Copernicus 30 m real, não MDT solo nu nem traçado ferroviário.",
  "","Um corredor com menor indicador de tempo não significa menor tempo de viagem do passageiro. Os valores de 'comprimento/velocidade' são índices de geometria idealizada, sem velocidade real por troço, aceleração, paragens, acesso à estação ou interoperabilidade. Não usar como previsões.",
  "","O indicador de pressão do MDS traduz o afastamento do perfil matemático limitado a 18‰ (misto) ou 25‰ (passageiros), **não** custo em euros ou comprimento de túneis/viadutos.",
  "","## Disponibilidade dos quatro critérios necessários",
  "| Critério | Estado inicial | O que falta para avaliação válida |",
  "|---|---|---|",
  "| Tempo | Indicador geométrico distância da grelha/velocidade | Traçado com velocidades por troço, aceler./desaceler., paragens e tempos de transferência |",
  "| Custos | Pressão topográfica MDS, não custo | MDT bare-earth, quantidades por estrutura, custos unitários comparáveis e O&M |",
  "| Intermodalidade rodoviária | Não medido por rede navegável | Estações candidatas, rede rodoviária com ligação legal, nós de acesso, tempos porta-a-porta |",
  "| Serviço a Vila Real/Bragança | Ambos os módulos atravessam a grelha de investigação | Localização/aptidão dos terminais, cobertura de população/emprego e acesso real |",
  "", "## Fronteiras de Pareto preliminares por velocidade e função (comprimento vs MDS)",
  "| km/h | Função | Combinações não dominadas |",
  "|---:|---|---|"]
 for speed,v in pareto.items():
  for name,ids in v.items():md.append(f"| {speed} | {name} | {', '.join(ids)} |")
 md+=["","## Proposta de evolução antes de MDT extenso",
  "Aumentar a diversificação *dentro* de cada ligação se esta comparação mostrar que as 27 são localmente próximas; introduzir tipologias de estações periféricas e acessibilidade rodoviária, e separar soluções passageiros de misto. Desenhar uma matriz de cenários com critérios duros (serviço real de VR e Bragança, política de Sanábria) e Pareto técnico apenas para métricas efetivamente calculadas.",
  "Desenvolver custos só após volumes e contratos comparáveis, com faixas de incerteza explícitas; primeiro obter MDT de validação local nos setores onde a classificação muda.",
  "Os melhores índices observados não são garantia de proximidade do ótimo ferroviário físico: o G5 ainda restringe famílias geométricas, o relevo é MDS, e os nós urbanos são apenas atravessados por grelha.", "", "**Pré-aceitação. Sem novos originais DGT, sem aceitação Fxx/Site.**", ""]
 mdpath.parent.mkdir(parents=True,exist_ok=True)
 mdpath.write_text("\n".join(md))
 print("G10_27PORTFOLIO="+json.dumps({
   "count":len(links),"review_count":len(rows),
   "pareto":pareto,"best_proxy_at_200":sorted([z for z in rows if z["speed_scenario_kmh"]==200 and z["horizontal_radius_research_screen_pass"]],key=lambda z:(z["passenger25_DSM_fraction_gt25m"],z["smoothed_research_grid_length_km_not_rail_track"]))[:8],
   "pass_radius_at_250":sum(z["horizontal_radius_research_screen_pass"] for z in rows if z["speed_scenario_kmh"]==250),
   "new_ground_acquisitions":0},ensure_ascii=False,separators=(',',':')))
 print("G10_VISUAL_MATRIX="+json.dumps([
   {"id":z["combination_id"],"v":z["speed_scenario_kmh"],"km":z.get("smoothed_research_grid_length_km_not_rail_track"),
    "tm":z.get("hypothetical_length_divided_by_speed_minutes_NOT_train_travel_time"),
    "t":z.get("passenger25_DSM_fraction_gt25m"),"p":z.get("passenger25_DSM_p90_m"),
    "g":z.get("mixed18_DSM_fraction_gt25m"),
    "m":z["module_options"]["P3"],"pass":z["horizontal_radius_research_screen_pass"],
    "front":z["combination_id"] in pareto[str(z["speed_scenario_kmh"])]["passenger25"]}
   for z in rows],separators=(',',':')))
 return result

def main():
 a=argparse.ArgumentParser()
 for name in ("g3","g4","g5","g6","b1","dsm","catalogues","json","markdown"):
  a.add_argument("--"+name,required=True,type=Path)
 p=a.parse_args()
 compute(p.g3,p.g4,p.g5,p.g6,p.b1,p.dsm,p.catalogues,p.json,p.markdown)
if __name__=="__main__":main()
