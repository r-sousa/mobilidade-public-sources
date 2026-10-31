#!/usr/bin/env python3
"""G12B: decision-gated source-evidence scenario audit, not a cost-benefit analysis.

Compares 6 source geometries × 6 markets × 3 research-position choices,
plus all 160/200/250 stop-pattern sensitivities. All financial cost in EUR,
real service frequencies, population catchments and approved station sites
remain NULL, with explicit source dependencies and verifiability gates.
"""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path

G10_SHA="7677ed95f822ee8ada510f984f50ee498851e3bd948f9ed960e08f8620cc7287"
A_OPTIONS=("P1-1-1","P1-2-1","P2-2-1","P2-2-3","P1-3-1","P3-1-3")
CITY_KEYS=("Guimaraes","Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca")
MANDATORY=("Vila_Real","Braganca")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pareto(arr,fields):
 keep=[]
 for v in arr:
  if any(v is not u and all(u[f]<=v[f]+1.e-7 for f in fields) and
       any(u[f]<v[f]-1.e-7 for f in fields) for u in arr):
   continue
  keep.append(v["research_combination"])
 return keep
def compare_sources(g10,a):
 if g10["total_combinations"]!=27 or len(a["six_corridor_city_reference_road_snap_minute_matrix"])!=6:
  raise ValueError("source_27_and_6_contract_break")
 rows=[]
 for row in a["six_corridor_city_reference_road_snap_minute_matrix"]:
  option=row["research_combination"]
  g=next(x for x in g10["scenario_rows"] if x["combination_id"]==option and x["speed_scenario_kmh"]==200)
  cities=row["urban_markets"]
  route_road={k:cities[k]["best_road_snap_research_point_only"]["road_minutes"]
        if cities[k]["best_road_snap_research_point_only"] else None for k in CITY_KEYS}
  if any(route_road[k] is None for k in MANDATORY):
   raise ValueError("mandatory_city_road_reference_missing_in_G12A")
  info={"research_combination":option,
   "G10_200kmh_horizontal_radius_study_screen_pass":g["horizontal_radius_research_screen_pass"],
   "G10_200kmh_length_index_km_NOT_railway":g["smoothed_research_grid_length_km_not_rail_track"],
   "G10_200kmh_25permille_DSM_P90_vertical_residual_m_NOT_structure":g["passenger25_DSM_p90_m"],
   "G10_200kmh_25permille_DSM_fraction_residual_gt25m_NOT_cost":g["passenger25_DSM_fraction_gt25m"],
   "road_to_station_access_min_actual":None,
   "road_to_study_road_snap_from_urban_centre_minutes":route_road,
   "road_to_study_snap_verified_as_rail_access":False,
   "high_level_road_snap_access_20min_coverage_optional_count":sum(route_road[k] is not None and route_road[k]<=20 for k in CITY_KEYS if k not in MANDATORY),
   "high_level_road_snap_access_15min_coverage_optional_count":sum(route_road[k] is not None and route_road[k]<=15 for k in CITY_KEYS if k not in MANDATORY),
   "population_jobs_catchment_observed":None,
   "observed_rail_OD_ridership":None,
   "CAPEX_EUR":None,"annual_OPEX_EUR":None,"rail_station_CAPEX_EUR":None,
   "railway_travel_time_actual_minutes":None,
   "fare_and_rail_frequency_current_data":None,
   "all_missing_are_explicit":True}
  rows.append(info)
 if set(x["research_combination"] for x in rows)!=set(A_OPTIONS):
  raise ValueError("source_shortlist_membership_changed")
 rows.sort(key=lambda x:A_OPTIONS.index(x["research_combination"]))
 return rows

def contrasts(rows):
 mp={r["research_combination"]:r for r in rows}
 # Same two other modules: test the marginal P1 / P3 / P5 choices.
 pairs=(("P1-1-1","P1-2-1","P3 - mandatory cities + Mirandela/Macedo"),
        ("P1-2-1","P2-2-1","P1 - Guimaraes vs Amarante"),
        ("P2-2-1","P2-2-3","P5 - border alternatives"),
        ("P1-1-1","P1-3-1","P3 - extra reference"),
        ("P1-1-1","P3-1-3","diversity - multiple modules"))
 results=[]
 for a,b,kind in pairs:
  one,two=mp[a],mp[b]
  towns={}
  for k in CITY_KEYS:
   z1=one["road_to_study_road_snap_from_urban_centre_minutes"][k]
   z2=two["road_to_study_road_snap_from_urban_centre_minutes"][k]
   towns[k]={"first":z1,"second":z2,
     "change_second_minus_first_minutes":round(z2-z1,2) if z1 is not None and z2 is not None else None}
  results.append({"first":a,"second":b,"comparison":kind,
   "source_research_grid_length_second_minus_first_km":round(two["G10_200kmh_length_index_km_NOT_railway"]-one["G10_200kmh_length_index_km_NOT_railway"],3),
   "DSM_residual_fraction_second_minus_first_percentage_points":round(100*(two["G10_200kmh_25permille_DSM_fraction_residual_gt25m_NOT_cost"]-one["G10_200kmh_25permille_DSM_fraction_residual_gt25m_NOT_cost"]),2),
   "road_reference_access_changes":towns,
   "not_actual_railway_cost_time_or_service_difference":True})
 return results

def evidence_gates():
 return [
 {"domain":"population_and_employment_catchments","upstream_source":"F67 INE BGRI 2021 original 246754080 bytes SHA 3eb49fb9e262e9d6ccb4b493811b7e21e2bbb31b0afe1431851ddd459ad7f171 privately preserved per original manifest",
  "upstream_source_path":"source_specs/F67.yml","state":"source_manifest_registered_but_actual_GIS_population_and_jobs_not_read_in_this_run",
  "next_qa":"verify original in private canonical, identify native layers and demographic/employment joins, CRS, year, municipal and subsection share, access licensing"},
 {"domain":"observed_transport_demand_and_OD","upstream_source":"Mobilidade Norte canonical INE pendularidade + transport surveys / IMT / CP as applicable",
  "upstream_source_path":"canonical_Fxx_to_be_resolved","state":"source_catalogue_candidates_only_not_a_validated_OD_dataset_in_this_run",
  "next_qa":"locate original OD matrix at finest consistent unit, year, expansion factors; do not invent flows"},
 {"domain":"road_bus_and_rail_interchange","upstream_source":"TIP/TMP 2025 F193 event totals limited AMP; current GTFS or approved operator timetable required",
  "upstream_source_path":"source_specs/F193.yml","state":"public_source_schema_known_not_general_Norte_timetables_or_station_access",
  "next_qa":"source verified road junction / stops + bus GTFS / CP route interchange Guimaraes"},
 {"domain":"civil_construction_CAPEX_and_OPEX","upstream_source":"real DGT 2m / CNIG 5m bare-earth + geotechnical constraints + published comparable unit rates",
  "upstream_source_path":"MN-GEO-RAIL-001-G4/G9","state":"121km2_discontinuous_PT_DGT2m_ground_and_96km2_in_two_ES_patches_only",
  "next_qa":"3D rail centreline and section bills; price library by geology, tunnels, viaducts, cut/fill, environmental safeguards and rolling-stock scope"},
 {"domain":"rail_speed_and_travel_time","upstream_source":"G10 and G12A screening are only speed/grade/stop sensitivities",
  "upstream_source_path":"MN-GEO-RAIL-001-G7/G10/G12A","state":"NO_real_rail_timetable_or_turnout_platform_curve_vertical_proof",
  "next_qa":"speed envelopes 160/200/250 with transition curves, grade, stations, accelerations and sectional travel times"}
 ]
def report(g10path,g12path,jsonpath,markdown):
 if sha(g10path)!=G10_SHA:raise ValueError("source_G10_SHA_changed")
 g10=json.loads(g10path.read_text());a=json.loads(g12path.read_text())
 if (a["cities_x_corridors_x_source_research_point_offsets"]!=[6,6,3] or
   a["railway_urban_nodes_mandatory"]!=["Vila Real","Bragança"] or
   not a["Sanabria_excluded"] or a["Fxx_accepted"] or a["Site_authorized"]):
  raise ValueError("source_G12A_governance_contradiction")
 rows=compare_sources(g10,a)
 contrast=contrasts(rows)
 # Pareto over OBSERVABLE same-scale tech proxy only, excluding speculative
 # financial/OD/rail access and station costs.
 technical=pareto(rows,("G10_200kmh_length_index_km_NOT_railway",
   "G10_200kmh_25permille_DSM_fraction_residual_gt25m_NOT_cost",
   "G10_200kmh_25permille_DSM_P90_vertical_residual_m_NOT_structure"))
 # Robust typology portfolio. Diversity is a deliberate constraint,
 # not a score-based claim of optimum: preserve 1-2-1 and 2-2-1 as two P1
 # families, and 2-2-3 as P5 independent scenario.
 anchors=["P1-2-1","P2-2-1","P2-2-3"]
 if any(x not in [r["research_combination"] for r in rows] for x in anchors):
  raise ValueError("loss_of_qualifying_source_corridor_family")
 result={"mission":"MN-GEO-RAIL-001","stage":"G12B_evidence_gated_service_technical_tradeoff_not_CBA",
  "utc":datetime.now(timezone.utc).isoformat(),
  "sources_sha256":{"G10":G10_SHA,"G12A":sha(g12path)},
  "required_urban_service":["Vila Real","Bragança"],
  "Sanabria_excluded":True,
  "provisional_3_family_anchors_NOT_final_selection":anchors,
  "other_geographically_diverse_reserve":["P1-1-1","P1-3-1","P3-1-3"],
  "pareto_on_only_length_and_DSM_proxies_not_cost":technical,
  "do_not_claim_minimum_financial_cost_or_maximum_accessibility":True,
  "road_to_study_point_is_NOT_station_road_access":True,
  "population_junction_and_employment_OD_unavailable_to_current_analysis":True,
  "no_CBA_without_actual_OD_CAPEX_OPEX_and_verified_station_geography":True,
  "cost_EUR_and_train_service_frequency_all_null":True,
  "gated_upstream_sources_and_next_validation":evidence_gates(),
  "per_alternative_source_comparison":rows,
  "marginal_module_alternative_contrasts":contrast,
  "Fxx_accepted":False,"Site_authorized":False}
 jsonpath.parent.mkdir(parents=True,exist_ok=True)
 jsonpath.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
 md=["# G12B — portão de seleção: 6 alternativas, 3 famílias a detalhar e lacunas impeditivas",
  "","**Não existe ainda informação para declarar o menor custo em euros nem o maior benefício territorial.** Comparação apoiada no G10/G12A: indicativos de comprimento e MDS e tempos OSRM até pontos de estrada próximos de linhas de estudo, não estações.",
  "","| Alternativa | Comprimento de estudo 200km/h (km, não ferrovia) | Fração MDS >25m (%) (não CAPEX) | Guimarães acesso OSRM (min, não estação) | Amarante acesso OSRM (min, não estação) | Mirandela (min) | Macedo (min) |",
  "|---|---:|---:|---:|---:|---:|---:|"]
 for r in rows:
  z=r["road_to_study_road_snap_from_urban_centre_minutes"]
  form=lambda k: str(z[k]) if z[k] is not None else "N/D"
  md.append(f"| {r['research_combination']} | {r['G10_200kmh_length_index_km_NOT_railway']} | {r['G10_200kmh_25permille_DSM_fraction_residual_gt25m_NOT_cost']*100:.1f} | {form('Guimaraes')} | {form('Amarante')} | {form('Mirandela')} | {form('Macedo_de_Cavaleiros')} |")
 md+=["","## Comparações modulares (uma mudança de cada vez)"]
 for z in contrast:
  md.append(f"- **{z['first']} → {z['second']}** ({z['comparison']}): distância de grelha Δ{z['source_research_grid_length_second_minus_first_km']:+.1f}km; pressão MDS Δ{z['DSM_residual_fraction_second_minus_first_percentage_points']:+.1f} p.p. Não é ganho ou perda financeiro.")
 md+=["","## Três âncoras de diversidade a aprofundar antes de adquirir MDT extenso",
   "**P1-2-1** (família Amarante), **P2-2-1** (família Guimarães) e **P2-2-3** (teste da opção transfronteiriça diferente). Manter referências de reserva, inclusive 1-1-1, para não perder a hipótese de um eixo muito mais direto.",
   "A shortlist é apenas uma carteira de hipóteses: as quatro famílias de padrões de serviço G12A não substituem o estudo real de horários, procura ou serviço transferível da linha existente.",
   "","## Dados que bloqueiam seleção económica e de serviço efetiva"]
 for gate in evidence_gates():
  md.append(f"- **{gate['domain']}**: {gate['state']}. Seguinte: {gate['next_qa']}.")
 md+=["","## Hipóteses de custos a preparar, sem EUR inventados",
 "A decomposição de custos deve distinguir: plataforma em superfície e drenagem; movimentos de terras; túneis e portais; viadutos; eletrificação/sinalização; estações/interfaces e ligações de acesso; ambiente/expropriações; material circulante quando incluído no projeto; contingência geológica; operação/manutenção. Cada rubrica terá quantidades e preços unitários com fontes auditadas e três intervalos de incerteza; **nenhuma está calculada nesta fase**.",
 "A regra de seleção será não-dominação sobre custo anualizado e tempo generalizado ponderado pela procura **após** validar os dados, com restrições mínimas de serviço obrigatório e robustez às diferentes ponderações de coesão regional.",
 "Sem novas aquisições DGT ou autorizações Fxx/Site.", ""]
 markdown.parent.mkdir(parents=True,exist_ok=True)
 markdown.write_text("\n".join(md))
 print("G12B_GATE="+json.dumps({"anchors":anchors,"technical_pareto":technical,
   "rows":[{"id":r["research_combination"],"k":r["G10_200kmh_length_index_km_NOT_railway"],
    "pressure":r["G10_200kmh_25permille_DSM_fraction_residual_gt25m_NOT_cost"],
    "access":{x:r["road_to_study_road_snap_from_urban_centre_minutes"][x] for x in ("Guimaraes","Amarante","Mirandela","Macedo_de_Cavaleiros")}} for r in rows],
   "population_data_verified":False,"CAPEX_eur":None},ensure_ascii=False,separators=(',',':')))
 return result
def main():
 a=argparse.ArgumentParser()
 for n in ("g10","g12","json","markdown"):a.add_argument("--"+n,type=Path,required=True)
 p=a.parse_args()
 report(p.g10,p.g12,p.json,p.markdown)
if __name__=="__main__":main()
