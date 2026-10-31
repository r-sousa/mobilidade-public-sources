#!/usr/bin/env python3
"""G13B integrated station ROAD reference access vs real DSM 30m surface pressure.

Uses SHA pinned G10 + G12B published evidence and tested G13A 108 source
profiles, without making up train times, station plots, catchments, CAPEX
or costs. Geographic portfolio choice: no financial optimum is established.
"""
from __future__ import annotations
import argparse,json,hashlib,statistics
from datetime import datetime,timezone
from pathlib import Path

G10_SHA="7677ed95f822ee8ada510f984f50ee498851e3bd948f9ed960e08f8620cc7287"
G12B_SHA="6a238e90e6eef962079e5b7704c3e143524eecf009d1ee12af7a27e3a065ba57"
PRIORITIES=("P1-2-1","P2-2-1","P2-2-3")
CITY_MANDATORY=("Vila Real","Bragança")
CITY_OPTIONAL=("Guimarães","Amarante","Mirandela","Macedo de Cavaleiros")
COST_COMPONENTS=(
 ("earthworks","m3","real bare-earth cut/fill and rock classification"),
 ("tunnels_and_portals","m","bored/cut-cover dimensions, geology, portals and drainage"),
 ("viaducts_and_bridges","m","height/width, geology, foundation and river/environment obstacles"),
 ("permanent_way","km","track gauge, slab/ballast and passing loops"),
 ("electrification_and_energy","km","power integration, electrification and substations"),
 ("signalling_safety_and_interoperability","km","ERTMS/ETCS, control, cross-border network systems"),
 ("stations_and_transfers","count","station type/platforms, accesses, bus interchange and access roads"),
 ("land_and_environment","hectares","land take, expropriation and compensation ecological works"),
 ("construction_management_and_contingency","percent","quantity risk geotechnical allowance, owner engineering"),
 ("operations_maintenance_and_rolling_stock","EUR_per_year","service frequency, fleets, staffing and asset upkeep"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def site_market_matrix(g13):
 result=[]
 for corridor in PRIORITIES+("P1-1-1","P1-3-1","P3-1-3"):
  sub=[x for x in g13["non_dominated_reference_site_screens_per_market"]
         if x["research_combination"]==corridor]
  if len(sub)!=6:raise ValueError("G13A_six_urban_markets_absent")
  best_access={}
  best_surface={}
  flags={}
  for city in sub:
   places=city["non_dominated_road_time_vs_DSM_terrain_reference_points"]
   if not places: 
    best_access[city["urban_market"]]=None;best_surface[city["urban_market"]]=None
   else:
    best_access[city["urban_market"]]=min(p["real_road_time_to_nearest_grid_road_snap_min"] for p in places)
    best_surface[city["urban_market"]]=min(p["L1_25permille_p90_vertical_surface_residual_m"] for p in places)
   flags[city["urban_market"]]=len(places)
  if any(best_access.get(city) is None for city in CITY_MANDATORY):
   raise ValueError("G13B_cannot_claim_compulsory_markets_studied")
  road_optional=[best_access[x] for x in CITY_OPTIONAL]
  if any(x is None for x in road_optional):
   # No penalty as fictional travel time: absence is a hard data flag.
   optional_mean=None
  else:optional_mean=round(statistics.mean(road_optional),2)
  result.append({"research_combination":corridor,
   "urban_reference_road_minutes_at_non_dominated_study_points":best_access,
   "minimum_L1_25permille_DSM_P90_surface_residual_m_among_study_points":best_surface,
   "road_access_not_actual_station":True,
   "site_profile_mds_not_ground_or_rail_platform":True,
   "road_reachable_optional_nodes_within15min_source_screen":sum(x is not None and x<=15 for x in road_optional),
   "road_reachable_optional_nodes_within30min_source_screen":sum(x is not None and x<=30 for x in road_optional),
   "mean_optional_urban_market_road_reference_minutes_unweighted_not_demand":optional_mean,
   "reference_points_relevant_per_city":flags,
   "all_rail_station_and_property_feasibilities_unverified":True})
 return result

def technical_by_speed(g10,options):
 return [
 {"research_combination":name,
  "speed_kmh":speed,
  "G10_horizontal_radius_proxy_passes_within3km_source_band":g["horizontal_radius_research_screen_pass"],
  "research_line_km_not_engineered_rail":g.get("smoothed_research_grid_length_km_not_rail_track"),
  "gradient25_DSM_vertical_fraction_gt25m_NOT_tunnel_cost":g.get("passenger25_DSM_fraction_gt25m"),
  "gradient18_DSM_vertical_fraction_gt25m_NOT_tunnel_cost":g.get("mixed18_DSM_fraction_gt25m"),
  "pass_250_failure_is_not_geographic_impossibility":speed==250 and not g["horizontal_radius_research_screen_pass"]}
 for name in options for speed in (160,200,250)
 for g in [next((r for r in g10["scenario_rows"] if r["combination_id"]==name and r["speed_scenario_kmh"]==speed),None)]
 if g is not None]

def compute(g10path,g12bpath,g13path,jpath,mdpath):
 for p,h in ((g10path,G10_SHA),(g12bpath,G12B_SHA)):
  if sha(p)!=h:raise ValueError("sha_pinned_source_drift_"+p.name)
 g10=json.loads(g10path.read_text());g12b=json.loads(g12bpath.read_text());g13=json.loads(g13path.read_text())
 if (g13["site_counts"]["original_research_points"]!=108 or
    g13["site_counts"]["actual_GLO30_source_DSM_cross_and_longitudinal_profile_success"]<90 or
    g13["Sanabria_excluded"] is not True or
    g12b["provisional_3_family_anchors_NOT_final_selection"]!=list(PRIORITIES) or
    g12b["Fxx_accepted"] or g13["Site_authorized"]):
  raise ValueError("G13A_evidence_not_sufficient_for_three_families")
 comparisons=site_market_matrix(g13)
 tech=technical_by_speed(g10,[x["research_combination"] for x in comparisons])
 if len(tech)!=18:raise ValueError("not_3_speed_for_six_source_alternatives")
 cost_schema=[{"component":n,"quantity_unit":u,"actual_source_measurement":None,
       "validated_construction_quantity":None,"price_EUR_per_unit":None,
       "investment_EUR":None,"quality_gate":purpose} for n,u,purpose in COST_COMPONENTS]
 gates=[
  {"dependency":"true station land parcels and legal road accesses","status":"not_validated","next":"identify publicly accessible realistic 2–3 sites per mandatory and optional city"},
  {"dependency":"INE BGRI 2021 F67 private original","status":"catalogue_manifest_exists_but_current_connected_Google_Drive_could_not_find_original","next":"verify private-preserved GPKG accessible to original archive team, license and statistical join; do not claim missing producer data"},
  {"dependency":"current employment distribution by actual location","status":"not_in_G13A","next":"inspect Mobilidade Norte Fxx census/employment reference and correct scale"},
  {"dependency":"observed train and road OD and generalized service cost","status":"not_measured","next":"INE daily mobility, CP/IMT and bus timetables, OD from canonical primary sources"},
  {"dependency":"actual geo-engineering and vertical datum","status":"source_30m_surface_only","next":"use only bounded native original DGT/IGN ground in critical risk sectors after shortlist"},
  {"dependency":"construction and lifecycle pricing","status":"no_quantity_or_unit_price_proof","next":"civil price library, local geology and annualized 40–60yr OPEX; separate 18permille mixed vs 25permille passenger"}
 ]
 result={"mission":"MN-GEO-RAIL-001",
  "stage":"G13B_three_diverse_corridor_service_site_terrain_and_financial_evidence_gate",
  "utc":datetime.now(timezone.utc).isoformat(),
  "source_sha256":{"G10":G10_SHA,"G12B":G12B_SHA,"G13A":sha(g13path)},
  "three_prioritized_diverse_not_cost_optimal_corridor_families":list(PRIORITIES),
  "other_three_explicit_reserve_study_families":["P1-1-1","P1-3-1","P3-1-3"],
  "mandatory_stops":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "georeferenced_station_sites_validated":0,
  "source_true_DEM_bareearth_line_coverage_continuous":False,
  "population_job_access_catchments_observed":False,
  "cost_EUR_estimates_validated":False,
  "intermodal_bus_rail_timetable_validated":False,
  "demand_weighted_access_per_passenger_not_yet_available":True,
  "G13A_108_source_surface_local_profiles_all_not_railway_station":True,
  "all_six_source_combinations_access_and_surface_screen":comparisons,
  "18_speed_scenario_geometry_and_surface_checks":tech,
  "engineering_and_financial_COST_BOM_schema_all_unknowns":cost_schema,
  "source_gaps_and_tangible_unlock_tasks":gates,
  "no_new_source_terrain_downloads":True,
  "no_economic_Pareto_optimization_until_CAPEX_and_OD":True,
  "Fxx_accepted":False,"Site_authorized":False}
 jpath.parent.mkdir(parents=True,exist_ok=True)
 jpath.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 md=["# G13B — integração dos três corredores prioritários e condições para investimento",
  "","Dados G10/G12B com SHA de release e G13A: 108 perfis de superfície locais associados a pontos de investigação já acessíveis por estrada pública; não há locais de estação validados.",
  "","## Qualidade potencial de serviço em função do acesso a pontos de investigação",
  "| Combinação | Nós opcionais com referência rodoviária ≤15 min (de 4) | Média não ponderada dos 4 nós (min) | 250 km/h — filtro geométrico original G10 |",
  "|---|---:|---:|---|"]
 for q in comparisons:
  opt=next(x for x in tech if x["research_combination"]==q["research_combination"] and x["speed_kmh"]==250)
  md.append(f"| {q['research_combination']} | {q['road_reachable_optional_nodes_within15min_source_screen']} | {q['mean_optional_urban_market_road_reference_minutes_unweighted_not_demand']} | {'passa o proxy dentro de 3km' if opt['G10_horizontal_radius_proxy_passes_within3km_source_band'] else 'não demonstrado na faixa testada'} |")
 md+=["","**Advertência:** municípios têm dimensão de procura diferente. Esta média não ponderada não é acessibilidade efetiva do território, nem pode ser usada para financiar uma alternativa. O acesso rodoviário termina num ponto de estrada perto da grelha, não num interface aprovado.",
  "","## Componentes de custo por medir antes de avaliar custos em euros",
  "| Componente | Quantidade requerida | Unidade | Estado |",
  "|---|---|---|---|"]
 for row in cost_schema:md.append(f"| {row['component']} | {row['quality_gate']} | {row['quantity_unit']} | N/D |")
 md+=["","## Portões de informação e ações"]
 for g in gates:md.append(f"- {g['dependency']} — **{g['status']}**. Próximo: {g['next']}.")
 md+=["","## Continuidade do trabalho sem aquisições extensas",
  "Rever os pontos não dominados para Vila Real/Bragança e para Amarante/Guimarães, confrontando referência de estrada e relevo com mapas de ordenamento e via existente. Priorizar levantamentos pontuais apenas depois de validar pertença à mesma família e potencial de instalação física.",
  "A avaliação económica deve calcular tempos de acesso e tempos ferroviários REALISTAS para fluxos OD, benefícios e custos a preço comum com incerteza, e não classificar como custo o indicador MDS.",
  "As três alternativas continuam como *famílias para estudar*, não como melhores soluções confirmadas.", ""]
 mdpath.parent.mkdir(parents=True,exist_ok=True)
 mdpath.write_text("\n".join(md))
 print("G13B_MULTICRITERIA="+json.dumps({"priorities":result["three_prioritized_diverse_not_cost_optimal_corridor_families"],
   "rows":[{"name":r["research_combination"],"n15":r["road_reachable_optional_nodes_within15min_source_screen"],
     "mean":r["mean_optional_urban_market_road_reference_minutes_unweighted_not_demand"]} for r in comparisons],
   "fail250":[r["research_combination"] for r in tech if r["speed_kmh"]==250 and not r["G10_horizontal_radius_proxy_passes_within3km_source_band"]],
   "cost_fields_measured":0,"geographical_site_validation":0},ensure_ascii=False,separators=(',',':')))
 return result

def main():
 a=argparse.ArgumentParser()
 for key in ("g10","g12b","g13a","json","markdown"):a.add_argument("--"+key,type=Path,required=True)
 p=a.parse_args();compute(p.g10,p.g12b,p.g13a,p.json,p.markdown)
if __name__=="__main__":main()
