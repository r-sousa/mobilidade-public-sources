#!/usr/bin/env python3
"""G23B local coordinate/heading original DGT2m terrain sensitivity, NOT station design.

No DGT download. Reuse 39 original G21 GeoTIFF + four historic B1 originals
through G22 audited source-original SHA and mask checks. Shift 5 mandatory
city study reference sites ±300m along source tangent, ±250m laterally, and
rotate hypothetical 400m and 1000m straight strips ±20° in 20° steps.
G22 exact unshifted tangent must reproduce source baseline. All footprints
are mathematically imposed; do not call them viable, surveyed or costed rail
stations. No road service claim is carried to moved candidate positions.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
import numpy as np
from geo_rail_g22_native_dgt2m_station_strips import (
 source_originals,reference_heading,strip,SITE,APPROACH
)
from geo_rail_g23a_native_ground_station_pareto import G22_SHA,G20_SHA,STATION,APP18
from pyproj import Transformer
G19_SHA="9f4d290f3fb2718c1a49a921c10d17b7f8c4dd97ccd28e3e6854486a8917dbe2"
G21_SHA="753335ae118c74df3d256cbfe853a47e34aa929a862401efcaf8721883c8f23e"
OFFSETS_ALONG=(-300.,0.,300.)
OFFSETS_CROSS=(-250.,0.,250.)
HEADING_DEG=(-20.,0.,20.)
TOTAL_PER_CASE=27
SAMPLE_COVERAGE_GATE=.98

def sha(file):
 h=hashlib.sha256()
 with file.open("rb") as f:
  for data in iter(lambda:f.read(2**20),b""):h.update(data)
 return h.hexdigest()

def pareto(source):
 # Partial ordered comparisons with absolute fixed source risk dimensions.
 # No station price or 2021 population/time of new alternative extrapolated.
 keys=("station_p90_m","approach18_p90_m","lateral_shift_absolute_m","longitudinal_shift_absolute_m","heading_rotation_absolute_deg")
 passed=[x for x in source if x["valid_coverage_98pct_station_and_approach"]]
 return [x for x in passed if not any(y is not x and all(y[k]<=x[k]+1e-6 for k in keys)
                and any(y[k]<x[k]-1e-6 for k in keys) for y in passed)]

def scenario(study,original_dir,src_g19,src_g20,src_g21,src_g22,b1,outpath,mdpath,geopath):
 for p,digest in ((src_g19,G19_SHA),(src_g20,G20_SHA),(src_g21,G21_SHA),(src_g22,G22_SHA)):
  if sha(p)!=digest:raise ValueError("G23B_previous_original_source_SHA_changed")
 g19=json.loads(src_g19.read_text());g20=json.loads(src_g20.read_text())
 g21=json.loads(src_g21.read_text());g22=json.loads(src_g22.read_text())
 b1=json.loads(b1.read_text())
 matrices,sourceqa=source_originals(original_dir,g20,g21,b1)
 if len(matrices)!=43 or len(g20["selected_reference_points_NOT_real_stations"])!=5 or g22["Fxx_accepted"]:
  raise ValueError("G23B_original_DGT_43_tiles_5_sites_not_available")
 baseline={(s["G20_source_reference_id"],s["research_family"]):s for s in g22["five_site_by_family_original_terrain_study_screens"]}
 if len(baseline)!=13:raise ValueError("G23B_baseline_13_original_sites_missing")
 cases=[];summary=[];points=[]
 to_ll=Transformer.from_crs(3763,4326,always_xy=True)
 for seed in g20["selected_reference_points_NOT_real_stations"]:
  center=seed["original_EPSG3763_XY_study_reference_m"]
  market=seed["mandatory_urban_market"]
  for family in seed["geographical_source_families_sharing_reference"]:
   source=baseline[(seed["id"],family)]
   unit,baseangle=reference_heading(g19,market,family)
   srcbase=source["native_DGT2m_primary_source_site_and_approach_terrain_screens"]
   options=[]
   for along in OFFSETS_ALONG:
    for cross in OFFSETS_CROSS:
     x=center[0]+along*unit[0]-cross*unit[1]
     y=center[1]+along*unit[1]+cross*unit[0]
     for delta in HEADING_DEG:
      rad=math.radians(delta)
      direction=(unit[0]*math.cos(rad)-unit[1]*math.sin(rad),
        unit[0]*math.sin(rad)+unit[1]*math.cos(rad))
      st=strip((x,y),direction,matrices,*SITE)
      approach=strip((x,y),direction,matrices,*APPROACH,.018)
      valid=(st["source_profile_fit_status"]=="eligible_original_ground_screen_NOT_station" and
             approach["source_profile_fit_status"]=="eligible_original_ground_screen_NOT_station")
      row={"study_seed_id":seed["id"],"mandatory_market":market,
        "source_family":family,
        "source_origin_EPSG3763_XY":center,
        "candidate_EPSG3763_XY":[round(x,2),round(y,2)],
        "source_study_tangent_heading_deg":baseangle,
        "longitude_shift_along_source_tangent_m":along,
        "lateral_shift_relative_to_source_tangent_m":cross,
        "source_tangent_heading_rotation_deg":delta,
        "longitudinal_shift_absolute_m":abs(along),
        "lateral_shift_absolute_m":abs(cross),
        "heading_rotation_absolute_deg":abs(delta),
        "study_site_location_unchanged":along==0 and cross==0,
        "study_line_orientation_unchanged":delta==0,
        "valid_coverage_98pct_station_and_approach":valid,
        "station_valid_native_ground_fraction":st["source_valid_ground_fraction"],
        "approach_valid_native_ground_fraction":approach["source_valid_ground_fraction"],
        "station_p90_m":st.get("source_vertical_deviation_p90_m") if valid else None,
        "approach18_p90_m":approach.get("source_vertical_deviation_p90_m") if valid else None,
        "station_terrain_grade_unclamped_per_mille":st.get("source_linear_grade_required_before_clamp_per_mille") if valid else None,
        "station_theoretical_cut_plus_fill_m3_NOT_engineering_cost":st.get("modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY") if valid else None,
        "approach18_theoretical_cut_plus_fill_m3_NOT_engineering_cost":approach.get("modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY") if valid else None,
        "this_candidate_city_to_road_access_travel_time_unmeasured":True,
        "this_candidate_is_not_a_feasible_station_or_track_alignment":True,
        "public_transport_route_access_unknown_not_zero":True}
      options.append(row)
   if len(options)!=TOTAL_PER_CASE:raise ValueError("G23B_incomplete_source_offset_heading_lattice")
   original=next(x for x in options if x["longitude_shift_along_source_tangent_m"]==0
           and x["lateral_shift_relative_to_source_tangent_m"]==0
           and x["source_tangent_heading_rotation_deg"]==0)
   ground=srcbase[STATION];app=srcbase[APP18]
   if not original["valid_coverage_98pct_station_and_approach"]:
    raise ValueError("G23B_source_G22_base_unexpected_missing_ground")
   if abs(original["station_p90_m"]-ground["source_vertical_deviation_p90_m"])>.01 or abs(original["approach18_p90_m"]-app["source_vertical_deviation_p90_m"])>.01:
    raise ValueError("G23B_station_source_ground_NOT_reproduced_against_G22")
   nondom=pareto(options)
   for x in options:
    x["nondominated_original_ground_and_source_offset_only"]=x in nondom
   eligible=[x for x in options if x["valid_coverage_98pct_station_and_approach"]]
   lower_both=[x for x in eligible if x["station_p90_m"]+1e-6<original["station_p90_m"] and
          x["approach18_p90_m"]+1e-6<original["approach18_p90_m"]]
   best=sorted(lower_both,key=lambda x:(x["station_p90_m"]/max(original["station_p90_m"],.01)+
          x["approach18_p90_m"]/max(original["approach18_p90_m"],.01),
          x["lateral_shift_absolute_m"]+x["longitudinal_shift_absolute_m"],x["heading_rotation_absolute_deg"]))[0] if lower_both else None
   summary.append({"source_seed_id":seed["id"],"mandatory_market":market,"study_family":family,
     "valid_original_DGT_2m_400m_and_1000m_screen_count":len(eligible),
     "source_candidate_positions_or_heading_combinations_tested":len(options),
     "nondominated_physical_ground_vs_shift_source_candidates":len(nondom),
     "baseline_station_vertical_p90_m":original["station_p90_m"],
     "baseline_approach_vertical_p90_m":original["approach18_p90_m"],
     "strict_both_platform_and_approach_p90_reductions_count":len(lower_both),
     "source_research_best_joint_relief_improvement_sample_if_exists":{
       "candidate_EPSG3763_XY":best["candidate_EPSG3763_XY"],
       "shift_along_m":best["longitude_shift_along_source_tangent_m"],
       "shift_lateral_m":best["lateral_shift_relative_to_source_tangent_m"],
       "source_heading_delta_deg":best["source_tangent_heading_rotation_deg"],
       "platform_p90_m":best["station_p90_m"],"approach_p90_m":best["approach18_p90_m"]
     } if best else None,
     "new_road_distance_from_city_legal_access_land_ownership_unknown":True,
     "G22_baseline_mathematical_reproduced_from_same_original_native_ground":True})
   for x in nondom:
    lon,lat=to_ll.transform(*x["candidate_EPSG3763_XY"])
    points.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
      "properties":{k:v for k,v in x.items() if k not in ("source_origin_EPSG3763_XY",)}})
   cases.extend(options)
 if len(cases)!=13*27 or len(summary)!=13:raise ValueError("G23B_351_source_sensitivity_cases_not_complete")
 if not all(x["G22_baseline_mathematical_reproduced_from_same_original_native_ground"] for x in summary):
  raise ValueError("G22_original_source_incompatibility")
 doc={"mission":"MN-GEO-RAIL-001",
  "stage":"G23B_true_DGT_2m_native_ground_shift_angle_physical_sensitivity_at_five_UNBUILT_research_points",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "original_releases_sha256":{"G19":G19_SHA,"G20":G20_SHA,"G21":G21_SHA,"G22":G22_SHA},
  "original_DGT_tile_count":len(matrices),
  "original_G21_valid_ground_pixels":g21["source_original_native_pixels_verified"],
  "original_G21_NoData_ground_pixels_preserved":g21["source_original_nodata_pixels_preserved"],
  "mandatory_cities":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "distinct_original_source_study_seeds":5,"source_families_study_cases":13,
  "local_site_shift_heading_sensitivity_scenarios":len(cases),
  "sample_assumed_400x50m_platform_grade_2p5permille_NOT_railway_standard":True,
  "sample_assumed_1000x60m_approach_grade_18permille_NOT_railway_design":True,
  "non_monetary_source_comparison_only":True,
  "no_CBA_euros_tunnel_bridge_structural_volumes":True,
  "no_new_candidate_legal_highway_roadtime_measured":True,
  "no_passenger_OD_modal_choice_or_GTFS":True,
  "no_platform_or_station_engineering_feasibility_approved":True,
  "no_new_DGT_data_acquisition":True,
  "13_family_source_ground_sensitivity_summaries":summary,
  "351_original_source_shift_angle_terrain_cases":cases,
  "Fxx_accepted":False,"Site_authorized":False}
 outpath.parent.mkdir(parents=True,exist_ok=True);outpath.write_text(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 # GeoJSON WGS84 geometry for interoperable mapping; original EPSG3763 study XY in properties.
 geopath.parent.mkdir(parents=True,exist_ok=True)
 geopath.write_text(json.dumps({"type":"FeatureCollection",
  "name":"G23B WGS84 original source terrain Pareto points not stations",
  "features":points},ensure_ascii=False)+"\n")
 md=["# G23B — Sensibilidade local às posições e direções de estudo (MDT original DGT2m)",
  "","Cinco referências obrigatórias × famílias de corredor: **13 combinações**, cada uma avaliada em 27 configurações de deslocamento (±300m longitudinal; ±250m transversal) e rotação da direção original (±20°). As posições permanecem **hipóteses não aprovadas de estudo**, sem acessos rodoviários verificados.",
  "","A origem matemática dos perfis reconstitui os resultados G22 sem alteração de base topográfica e preserva células NoData.",
  "","| Mercado | Referência | Família | Casos com MDT suficiente / 27 | P90 inicial estação (m) | P90 inicial aproximação (m) | Alternativas com ambas as pressões reduzidas |",
  "|---|---|---|---:|---:|---:|---:|"]
 for x in summary:
  md.append(f"| {x['mandatory_market']} | {x['source_seed_id']} | {x['study_family']} | {x['valid_original_DGT_2m_400m_and_1000m_screen_count']} | {x['baseline_station_vertical_p90_m']} | {x['baseline_approach_vertical_p90_m']} | {x['strict_both_platform_and_approach_p90_reductions_count']} |")
 md+=["","## Condições obrigatórias para a pré-viabilidade",
  "- Excluir qualquer deslocamento com acesso legal inviável, sem caminho de ferro geometricamente contínuo, em área ocupada/protegida ou sem articulação rodoviária.",
  "- Estimar o custo de obras de terra apenas após geologia, limites efetivos de intervenção, taludes, contenções, plataformas de dimensão adequadas e perfil longitudinal ferroviário compatível.",
  "- Não transportar automaticamente os tempos rodoviários da posição de origem para as posições deslocadas; seria uma extrapolação injustificada.",
  "- As diferenças matemáticas de relevo entre posições não constituem benefícios socioeconómicos nem poupança de CAPEX confirmada.",
  "- Incluir interfaces opcionais com custos marginais de paragem e de desvio na avaliação posterior.",
  "","Sem nova aquisição DGT, sem Fxx ou Site.",""]
 mdpath.parent.mkdir(parents=True,exist_ok=True);mdpath.write_text("\n".join(md))
 print("G23B_NATIVE_SHIFT_SCREEN="+json.dumps({"source_sites":5,"study_families":13,
    "variants":len(cases),
    "valid_total":sum(z["valid_original_DGT_2m_400m_and_1000m_screen_count"] for z in summary),
    "strict_joint_improve_total":sum(z["strict_both_platform_and_approach_p90_reductions_count"] for z in summary),
    "seed_cases":[{"id":z["source_seed_id"],"f":z["study_family"],
      "valid":z["valid_original_DGT_2m_400m_and_1000m_screen_count"],
      "better":z["strict_both_platform_and_approach_p90_reductions_count"],
      "sample":z["source_research_best_joint_relief_improvement_sample_if_exists"]} for z in summary]},
     ensure_ascii=False,separators=(",",":")))
 return doc

def main():
 p=argparse.ArgumentParser()
 for key in ("g19","g20","g21","g22","b1","tiles","json","markdown","geojson"):
  p.add_argument("--"+key,type=Path,required=True)
 a=p.parse_args();scenario(None,a.tiles,a.g19,a.g20,a.g21,a.g22,a.b1,a.json,a.markdown,a.geojson)
if __name__=="__main__":main()
