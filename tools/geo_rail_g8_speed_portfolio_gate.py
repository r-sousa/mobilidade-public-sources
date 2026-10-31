#!/usr/bin/env python3
"""G8 audited pre-acquisition speed-specific portfolio gate.

Use actual G6 three connected research screens, and real DSM-backed G7
160/200/250 km/h curvature + gradient proxy results. Screen for robust,
non-dominated RESEARCH alternatives without pretending railway feasibility.
No original DGT acquisition. Never infer engineering or tunnel quantities.
"""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone

G6_SHA="faa2f1d218c79a3647a0d32217ab7bd460cc8aed418750ac62b41844d2d5bc9d"
G7_SHA="9379e6d07b8bca0aec43052224477c11928299008f5caca8e04934c1e52205fd"
FRACTION_SCREEN_TOLERANCE=0.02 # sensitivity only: 2 percentage points, NOT source uncertainty
CRITICAL_P90_M=50.
CRITICAL_FRACTION=0.20

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def row(g7):
 p=g7["selected_horizontal_smoothing"]
 v=g7["longitudinal_gradient_screening"]["passenger_25permille"]
 m=g7["longitudinal_gradient_screening"]["mixed_18permille"]
 return {
  "chain_id":g7["chain_id"],"speed_kmh":g7["speed_scenario_kmh"],
  "study_grid_smooth_length_km_NOT_track":p["screening_length_km_not_rail_distance"],
  "smoothed_xy_max_shift_from_source_research_grid_m":p["max_distance_to_source_research_polyline_m"],
  "minimum_curvature_radius_screen_m":g7["conservative_hypothetical_radius_screen_m"],
  "passenger25_DSM_L1_p90_absolute_vertical_departure_m":v["p90_abs_line_vs_DSM_surface_m"],
  "passenger25_fraction_DSM_absolute_departure_above25m":v["fraction_of_profile_distance_with_DSM_pressure_gt25m_proxy"],
  "mixed18_DSM_L1_p90_absolute_vertical_departure_m":m["p90_abs_line_vs_DSM_surface_m"],
  "mixed18_fraction_DSM_absolute_departure_above25m":m["fraction_of_profile_distance_with_DSM_pressure_gt25m_proxy"],
  "unresolved_very_high_terrain_earthwork_pressure_proxy":
    (v["p90_abs_line_vs_DSM_surface_m"]>CRITICAL_P90_M or
    v["fraction_of_profile_distance_with_DSM_pressure_gt25m_proxy"]>CRITICAL_FRACTION),
  "rail_feasibility_demonstrated":False}

def dominates(a,b):
 # Permit a nominal difference <=2 percentage points in one coarse DSM
 # fraction screen to prevent noise treating an option as independently better.
 names=("study_grid_smooth_length_km_NOT_track",
        "passenger25_DSM_L1_p90_absolute_vertical_departure_m",
        "passenger25_fraction_DSM_absolute_departure_above25m")
 return (a[names[0]]<=b[names[0]] and
         a[names[1]]<=b[names[1]] and
         a[names[2]]<=b[names[2]]+FRACTION_SCREEN_TOLERANCE and
         (a[names[0]]<b[names[0]] or a[names[1]]<b[names[1]]))

def make(g6,g7):
 if (g6.get("mandatory_service_areas")!=["Vila Real","Bragança"] or
     g7.get("mandatory_service_areas")!=["Vila Real","Bragança"] or
     not g6.get("Sanabria_excluded") or not g7.get("Sanabria_excluded") or
     g6.get("Fxx_accepted") or g7.get("Fxx_accepted") or
     g6.get("Site_authorized") or g7.get("Site_authorized")):
  raise ValueError("source_scope_or_governance_mismatch")
 assert len(g6["end_to_end_research_chains"])==3 and len(g7["scenarios"])==9
 metrics=[]
 for z in g7["scenarios"]:
  if not z.get("candidate_within_3km_of_source_grid_found"):
   raise ValueError("G7_did_not_pass_one_basic_necessary_screen")
  metrics.append(row(z))
 prior={v["study_chain_id"]:v for v in g6["end_to_end_research_chains"]}
 if set(prior)!={"G6-SCREEN-1","G6-SCREEN-2","G6-SCREEN-3"}:
  raise ValueError("G6_source_chain_identity_changed")
 speeds=[]
 for speed in (160,200,250):
  group=[r for r in metrics if r["speed_kmh"]==speed]
  viable_for_further_research=[r for r in group if not any(dominates(z,r) for z in group if z is not r)]
  # This is provisional convergence, not an engineering exclusion.
  retained=[r["chain_id"] for r in viable_for_further_research]
  if len(retained)!=2 or set(retained)!={"G6-SCREEN-1","G6-SCREEN-2"}:
   raise ValueError("G8_speed_sensitivity_did_not_robustly_converge_on_two_reference_options")
  speeds.append({"speed_kmh":speed,
    "screen_only_retained_research_chains":retained,
    "third_chain_deprioritized_not_technically_excluded":"G6-SCREEN-3",
    "radius_proxy_screen_passed_but_railway_feasible":False,
    "all_retained_chains_have_critical_vertical_DSM_pressure":all(r["unresolved_very_high_terrain_earthwork_pressure_proxy"] for r in viable_for_further_research),
    "metrics":group})
 common=set(tuple(p) for p in prior["G6-SCREEN-1"]["source_grid_cells_epsg3763"]) & set(tuple(p) for p in prior["G6-SCREEN-2"]["source_grid_cells_epsg3763"])
 first=set(tuple(p) for p in prior["G6-SCREEN-1"]["source_grid_cells_epsg3763"])
 second=set(tuple(p) for p in prior["G6-SCREEN-2"]["source_grid_cells_epsg3763"])
 checked=[]
 for sector in g6["next_at_most_12_source_review_cells_not_auto_acquisition"]:
  xy=tuple(sector["2km_SW_epsg3763"])
  ids=sector["official_four_producer_DGT2m_source_IDs"]
  if len(ids)!=4 or len(set(ids))!=4:
   raise ValueError("new_original_source_IDs_invalid")
  if xy not in first and xy not in second:
   # It might be useful solely for third-chain reserve; do not acquire now.
   role="backup_only_deprioritized"
  elif xy in common:role="shared_by_two_retained_source_chains"
  else:role="discriminates_two_retained_source_chains"
  checked.append({"grid_SW_EPSG3763":list(xy),"role":role,
    "source_original_DGT2m_1km_tile_ids":ids,
    "new_original_DGT_download_authorized":False,
    "requires_bare_earth_to_test_track_geometry_and_structure":True})
 relevant=[q for q in checked if q["role"]!="backup_only_deprioritized"]
 return {
  "mission":"MN-GEO-RAIL-001","stage":"G8_speed_scenario_convergence_and_preacquisition_gate",
  "timestamp_utc":datetime.now(timezone.utc).isoformat(),
  "sources_SHA256":{"G6_real_grid_research":G6_SHA,"G7_real_Copernicus_DSM_speed_tests":G7_SHA},
  "speed_scenarios":[160,200,250],
  "mandatory_service_areas":["Vila Real","Bragança"],
  "city_centres_not_required":True,"Sanabria_excluded":True,
  "convergence":"two_non_dominated_study_bands_for_all_speed_cases_G6_SCREEN_1_and_2",
  "retained_research_chains":["G6-SCREEN-1","G6-SCREEN-2"],
  "reserve_only_research_chain":"G6-SCREEN-3",
  "no_railway_corridor_certified_feasible":True,
  "original_source_GLO30_is_DSM_not_bare_earth":True,
  "vertical_gradient_cases":{"mixed_permille":18,"passenger_permille":25},
  "source_vertical_datum_crossborder_not_harmonized":True,
  "station_access_legal_road_driving_times_not_measured":True,
  "requires_new_terrain_aware_lateral_3D_route_optimization":True,
  "speed_sensitivity":speeds,
  "source_G6_review_only_original_2km_sector_candidates_total":len(checked),
  "source_catalogued_DGT2m_review_sectors_intersecting_retained_chains":len(relevant),
  "review_only_retained_sector_candidates":relevant,
  "source_research_sectors_only_on_deprioritized_backup":len(checked)-len(relevant),
  "original_source_DGT2m_acquisition_now_authorized":False,
  "extensive_ground_raster_acquisition_should_not_proceed":True,
  "Fxx_accepted":False,"Site_authorized":False}

def main():
 a=argparse.ArgumentParser()
 for p in ("g6","g7","json","markdown"):a.add_argument("--"+p,required=True,type=Path)
 p=a.parse_args()
 for n,expected in ((p.g6,G6_SHA),(p.g7,G7_SHA)):
  if digest(n)!=expected:raise ValueError("G8_SHA256_source_mismatch")
 obj=make(json.loads(p.g6.read_text()),json.loads(p.g7.read_text()))
 p.json.parent.mkdir(parents=True,exist_ok=True)
 p.json.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
 md=["# G8 — decisão preliminar de convergência antes de aquisição MDT extensa",
  "","**Reter G6-SCREEN-1 (mais curto) e G6-SCREEN-2 (menor pressão altimétrica do MDS) para 160, 200 e 250 km/h.** Manter G6-SCREEN-3 apenas em reserva; não é uma exclusão técnica comprovada.",
  "","## Matriz de sensibilidade de velocidade e relevo superficial",
  "| Cenário | Faixa | km de grelha suavizada, não ferroviária | P90 diferença vertical MDS-25‰ (m) | Fração MDS >25m | Decisão de triagem |",
  "|---|---|---:|---:|---:|---|"]
 for z in obj["speed_sensitivity"]:
  for r in z["metrics"]:
   status="reter para otimização 3D" if r["chain_id"] in z["screen_only_retained_research_chains"] else "reserva"
   md.append(f"| {z['speed_kmh']} km/h | {r['chain_id']} | {r['study_grid_smooth_length_km_NOT_track']} | {r['passenger25_DSM_L1_p90_absolute_vertical_departure_m']} | {r['passenger25_fraction_DSM_absolute_departure_above25m']} | {status} |")
 md+=["","## Portão para a recolha de dados de detalhe",
  f"Das {obj['source_G6_review_only_original_2km_sector_candidates_total']} quadrículas DGT já propostas em G6, {obj['source_catalogued_DGT2m_review_sectors_intersecting_retained_chains']} atravessam pelo menos uma das duas alternativas mantidas. Só estas justificam primeira revisão geográfica; não foi autorizada qualquer descarga.",
  "Não adquirir grandes faixas MDT antes de otimização tridimensional dos eixos, análise dos pontos de conflito, verificação de acessibilidade e calibração pontual com solo nu. A alta pressão observada no MDS não constitui previsão de quantidade de túneis/viadutos.",
  "A diferença de 2 pontos percentuais usada para desempatar um indicador impreciso é apenas uma sensibilidade da regra de triagem, não uma incerteza estatística do MDS.",
  "Nenhuma velocidade ou traçado ferroviário está validado tecnicamente. Sem Fxx/Site.",""]
 p.markdown.write_text("\n".join(md))
 print("G8_PRE_ACQUISITION_GATE="+json.dumps({"speeds":obj["speed_scenarios"],"retain":obj["retained_research_chains"],"backup":obj["reserve_only_research_chain"],"review_cells":len(obj["review_only_retained_sector_candidates"]),"new_DGT_downloads":0},separators=(',',':')))
if __name__=="__main__":main()
