#!/usr/bin/env python3
"""G9: local lateral + vertical source DSM screening in TWO G8 retained corridors.

This is a deterministic research-stage 2.5D search, NOT a railway design.
Actual 30m Copernicus GLO-30 DSM is sampled after bounded normal offsets
within the two original G6 geographic routes (160, 200, 250 km/h).
Vila Real / Braganca source-city connector sectors are intentionally anchored.
Vertical profiles minimise absolute DSM separation at simple 18/25 per mille
gradient caps. No vertical curves, station elevations, legal access, true DTM,
interoperability, engineering feasibility, tunnel/viaduct quantities or costs.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import LineString,Point,mapping
from shapely.ops import transform as transform_geom
from geo_rail_g7_rail_screen import (choose_geometry,grade_L1_profile,DSM_SHA,SPEEDS,
    sample_dsm,radius_screen,distance_from_source,dense,MAX_REF_DISPLACEMENT_M)
from geo_rail_g6_full_research_chains import validate_sources,G4_SHA
from geo_rail_g3_continuity_open_dsm_sources import cell_ids
from geo_rail_pt_b1_dgt_review_grids import inventory

G6_SHA="faa2f1d218c79a3647a0d32217ab7bd460cc8aed418750ac62b41844d2d5bc9d"
G8_SHA="be32b2c4a711aa311924772b3d8fc63e32d6c71deae9331291c2f402fff5294d"
RETAINED=("G6-SCREEN-1","G6-SCREEN-2")
GRADES={"mixed_18permille":18.,"passenger_25permille":25.}
OFFSETS_M=(-1200.,0.,1200.)
SOURCE_CITY_POINTS=(
    ("Vila_Real_W",(20000,180000)),
    ("Vila_Real_E",(40000,184000)),
    ("Braganca_W",(110000,234000)),
    ("Braganca_E",(116000,238000)),
)
BLOCK_M=5000.
# Transparent heuristic for selecting only a DEM validation target, not
# an economic project score or technical approval.
OBJECTIVE={"fraction_abs_DSM_offset_gt25m":100.,
           "p90_abs_DSM_offset_m":.08,
           "smoothed_research_length_km":.03}

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(2**20),b""):h.update(b)
 return h.hexdigest()

def city_modules(source):
 """Locate actual source lattice city connector endpoints by *exact* sector ID."""
 ids={tuple(p):i for i,p in enumerate(source)}
 anchor=[(p[0]+1000,p[1]+1000) for _,p in SOURCE_CITY_POINTS]
 if any(p not in ids for p in anchor):
  raise ValueError("G6_mandatory_city_service_research_sector_disappeared")
 ii=[ids[p] for p in anchor]
 if not (0<ii[0]<ii[1]<ii[2]<ii[3]<len(source)-1):
  raise ValueError("G6_city_research_passage_sequence_not_retained")
 s=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(np.asarray(source,dtype=float),axis=0),axis=1))]
 return ((float(s[0]),float(s[ii[0]]),"P1_AFSC_to_Vila_Real_W"),
         (float(s[ii[1]]),float(s[ii[2]]),"P3_Vila_Real_E_to_Braganca_W"),
         (float(s[ii[3]]),float(s[-1]),"P5_Braganca_E_to_Zamora")), [float(s[i]) for i in ii]

def normal_perturbation(baseline_xy,original_route,leg,offset_m):
 """Broad sinusoidal side translation, exactly zero at module boundaries."""
 s_dense,_=dense(original_route)
 if baseline_xy.shape[0]!=len(s_dense):
  raise ValueError("G7_source_sampling_not_identical")
 a,b,_=leg
 out=np.zeros_like(s_dense)
 if offset_m:
  mask=(s_dense>a)&(s_dense<b)
  t=(s_dense[mask]-a)/(b-a)
  out[mask]=offset_m*np.sin(math.pi*t)**2
 dx=np.gradient(baseline_xy[:,0],s_dense,edge_order=2)
 dy=np.gradient(baseline_xy[:,1],s_dense,edge_order=2)
 mag=np.hypot(dx,dy)
 if np.any(mag<.002):raise ValueError("G9_invalid_horizontal_tangent")
 norm=np.column_stack([-dy/mag,dx/mag])
 return baseline_xy+out[:,None]*norm,out

def lp_dsm_proxy(xy,z,grade):
 s=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
 if np.any(np.diff(s)<2.):raise ValueError("too_short_screening_sample_step")
 fit=grade_L1_profile(z,s,grade/1000.)
 residual=fit-z
 a=np.abs(residual)
 if np.any(np.abs(np.diff(fit))>grade/1000.*np.diff(s)+.001):
  raise ValueError("screen_profile_exceeds_gradient")
 return {
  "p90_absolute_DSM_vertical_difference_m":round(float(np.quantile(a,.9)),2),
  "median_absolute_DSM_vertical_difference_m":round(float(np.median(a)),2),
  "fraction_samples_absolute_DSM_difference_gt25m":round(float(np.mean(a>25)),4),
  "fraction_samples_absolute_DSM_difference_gt50m":round(float(np.mean(a>50)),4),
  "maximum_absolute_DSM_vertical_difference_m":round(float(a.max()),2),
  "mean_absolute_DSM_vertical_difference_m":round(float(np.mean(a)),2),
  "max_abs_mathematical_gradient_permille":round(float(np.max(np.abs(np.diff(fit))/np.diff(s))*1000),3),
  "curve_and_station_heights_not_enforced":True
 },residual,s

def score(v,length):
 return round(OBJECTIVE["fraction_abs_DSM_offset_gt25m"]*
              v["fraction_samples_absolute_DSM_difference_gt25m"]+
              OBJECTIVE["p90_abs_DSM_offset_m"]*v["p90_absolute_DSM_vertical_difference_m"]+
              OBJECTIVE["smoothed_research_length_km"]*length,5)

def hotspot_windows(xy,z,r,s,leg_intervals,crs,top=4):
 groups={}
 for i,dist in enumerate(s):
  k=int(dist//BLOCK_M)
  groups.setdefault(k,[]).append(i)
 rows=[]
 for k,ind in groups.items():
  if len(ind)<6:continue
  a=np.abs(r[ind]);mid=ind[len(ind)//2]
  lon,lat=crs.transform(float(xy[mid,0]),float(xy[mid,1]))
  seg=next((label for low,high,label in leg_intervals if low<=dist<=high),"urban_reference_connector")
  # Order by fraction suffering high DSM displacement, then magnitude.
  rows.append({"five_km_block":k,"chainage_grid_smoothed_km":[round(float(s[ind[0]]/1000),2),round(float(s[ind[-1]]/1000),2)],
    "terrain_service_module_by_original_grid_reference":seg,
    "source_DSM_P90_absolute_offset_m":round(float(np.quantile(a,.9)),2),
    "source_DSM_fraction_absolute_offset_gt25m":round(float(np.mean(a>25)),4),
    "source_DSM_fraction_absolute_offset_gt50m":round(float(np.mean(a>50)),4),
    "indicative_WGS84_lonlat":[round(lon,6),round(lat,6)],
    "PT_TM06_2km_SW_sector_for_metadata_only":[int(math.floor(xy[mid,0]/2000)*2000),int(math.floor(xy[mid,1]/2000)*2000)],
    "NOT_observed_tunnel_viaduct_or_railway_profile":True})
 rows.sort(key=lambda q:(-q["source_DSM_fraction_absolute_offset_gt25m"],
                          -q["source_DSM_P90_absolute_offset_m"],q["five_km_block"]))
 return rows[:top],rows

def run(dsm_path,g6_path,g8_path,g4_path,b1_path,cat_path,out_json,out_geojson,out_md):
 for f,expected in ((dsm_path,DSM_SHA),(g6_path,G6_SHA),
                    (g8_path,G8_SHA),(g4_path,G4_SHA)):
  if sha(f)!=expected:raise ValueError("SOURCE_SHA256_DRIFT_"+f.name)
 g6=json.loads(g6_path.read_text())
 g8=json.loads(g8_path.read_text())
 g4=json.loads(g4_path.read_text())
 b1=json.loads(b1_path.read_text())
 if (g6["mandatory_service_areas"]!=["Vila Real","Bragança"] or
     g8["retained_research_chains"]!=list(RETAINED) or
     not g6["Sanabria_excluded"] or not g8["Sanabria_excluded"] or
     g8["original_source_DGT2m_acquisition_now_authorized"] or
     g4["DGT_2m_total_distinct_original_tile_footprint_km2"]!=121):
  raise ValueError("G8_research_selection_or_DGT_source_provenance_invalid")
 catalogue,proofs=inventory(cat_path)
 native,acquired=validate_sources(
     {"mandatory_cities":["Vila Real","Bragança"],"Sanabria_excluded":True},
     g4,{"mandatory_service_areas":["Vila Real","Bragança"],
         "Fxx_accepted":False,"Site_authorized":False,"legs":[1,2,3]},
     b1,catalogue)
 # validate_sources only relies on explicit G3/G4/G5 invariants, and
 # source original DGT/B1 provenances are independently checked.
 source_chains={x["study_chain_id"]:x for x in g6["end_to_end_research_chains"]}
 if set(source_chains)!={"G6-SCREEN-1","G6-SCREEN-2","G6-SCREEN-3"}:
  raise ValueError("G6_source_identity_drift")
 to_wgs=Transformer.from_crs(3763,4326,always_xy=True)
 outputs=[];geos=[];review_targets={}
 with rasterio.open(dsm_path) as ds:
  if ds.crs.to_epsg()!=4326:raise ValueError("not_source_Copernicus_DSM")
  for cid in RETAINED:
   c=source_chains[cid]
   source=[(p[0]+1000,p[1]+1000) for p in c["source_grid_cells_epsg3763"]]
   leg_intervals,anchors=city_modules(source)
   for speed,radius in SPEEDS.items():
    baseline,attempts=choose_geometry(source,radius)
    if baseline is None:raise ValueError("G7_original_radius_proxy_no_longer_passes")
    base_xy,source_geometry=baseline
    candidates=[]
    offsets=[("baseline",None,0.)]+[(leg[2]+("_left" if o<0 else "_right"),leg,o)
                                  for leg in leg_intervals for o in (-1200.,1200.)]
    for label,leg,offset in offsets:
     xy,shift=normal_perturbation(base_xy,source,leg,offset) if leg else (base_xy,np.zeros(len(base_xy)))
     curve=radius_screen(xy)
     deviation=distance_from_source(xy,source)[0] if curve else float("inf")
     if curve is None or curve[0]<radius or deviation>MAX_REF_DISPLACEMENT_M:
      candidates.append({"id":label,"geometry_screen_pass":False,
         "max_distance_to_G6_source_grid_m":round(deviation,1) if math.isfinite(deviation) else None,
         "screen_min_radius_m":round(curve[0],1) if curve else None,
         "screen_only_not_proof_of_railway_infeasibility":True})
      continue
     z=sample_dsm(ds,xy)
     length=float(np.sum(np.linalg.norm(np.diff(xy,axis=0),axis=1))/1000)
     profiles={};details={}
     for gname,g in GRADES.items():
      profile,delta,s=lp_dsm_proxy(xy,z,g)
      profiles[gname]=profile
      details[gname]=(delta,s)
     candidates.append({"id":label,"geometry_screen_pass":True,
        "research_length_km_not_railway":round(length,3),
        "max_distance_to_G6_source_grid_m":round(deviation,1),
        "max_exploratory_normal_offset_m":round(float(np.max(np.abs(shift))),1),
        "min_proxy_horizontal_radius_m":round(curve[0],1),
        "gradient_DSM_pressures":profiles,
        "_xy":xy,"_z":z,"_details":details})
    feasible_proxy=[x for x in candidates if x["geometry_screen_pass"]]
    if not feasible_proxy or not any(x["id"]=="baseline" for x in feasible_proxy):
     raise ValueError("G9_baseline_horizontal_screen_regressed")
    winners={}
    for grade in GRADES:
     rank=sorted(feasible_proxy,key=lambda row:(score(row["gradient_DSM_pressures"][grade],
                                      row["research_length_km_not_railway"]),row["id"]))
     chosen=rank[0]
     baseline_row=next(z for z in feasible_proxy if z["id"]=="baseline")
     victory=score(baseline_row["gradient_DSM_pressures"][grade],
                   baseline_row["research_length_km_not_railway"])-score(
                       chosen["gradient_DSM_pressures"][grade],chosen["research_length_km_not_railway"])
     xy=chosen["_xy"];d,s=chosen["_details"][grade]
     hot,all_hot=hotspot_windows(xy,chosen["_z"],d,s,leg_intervals,to_wgs)
     for zone in hot:
      p=tuple(zone["PT_TM06_2km_SW_sector_for_metadata_only"])
      IDs=cell_ids(catalogue,*p)
      if IDs is not None and len(IDs)==4 and not any(id in acquired for id in IDs):
       key=p
       item=review_targets.setdefault(key,{"SW_grid_EPSG3763":list(p),
                "original_official_DGT_MDT2m_tile_IDs":IDs,
                "source_G8_retained_chains_crossed_in_winner_hotspots":set(),
                "max_source_DSM_fraction_gt25m":0.})
       item["source_G8_retained_chains_crossed_in_winner_hotspots"].add(cid)
       item["max_source_DSM_fraction_gt25m"]=max(item["max_source_DSM_fraction_gt25m"],
                                          zone["source_DSM_fraction_absolute_offset_gt25m"])
     winners[grade]={"winning_candidate":chosen["id"],
       "baseline_candidate":baseline_row["id"],"winning_proxy_objective":score(
           chosen["gradient_DSM_pressures"][grade],chosen["research_length_km_not_railway"]),
       "baseline_proxy_objective":score(baseline_row["gradient_DSM_pressures"][grade],
                                                 baseline_row["research_length_km_not_railway"]),
       "proxy_improvement_vs_baseline":round(victory,5),
       "winning_profile":chosen["gradient_DSM_pressures"][grade],
       "top_high_pressure_5km_source_DSM_windows":hot,
       "all_5km_source_DSM_windows_count":len(all_hot),
       "cannot_infer_structures_or_engineering_feasibility":True}
     lon,lat=to_wgs.transform(xy[:,0].tolist(),xy[:,1].tolist())
     geos.append({"type":"Feature","geometry":mapping(LineString(list(zip(lon,lat)))),
       "properties":{"research_chain":cid,"speed_research_kmh":speed,"gradient_research_case":grade,
        "selected_lateral_exploration":chosen["id"],"geometry_is_not_engineered_railway":True}})
     for zone in hot:
      geos.append({"type":"Feature",
        "geometry":{"type":"Point","coordinates":zone["indicative_WGS84_lonlat"]},
        "properties":{"research_chain":cid,"speed_research_kmh":speed,
          "gradient_research_case":grade,"layer":"source_DSM_conflict_window",
          "source_DSM_fraction_abs_gt25m":zone["source_DSM_fraction_absolute_offset_gt25m"],
          "source_DSM_p90_abs_m":zone["source_DSM_P90_absolute_offset_m"],
          "NOT_a_tunnel_or_viaduct_location":True}})
    # Never copy full arrays into JSON; keep the evidence auditable as methods.
    inspected=[]
    for z in candidates:
     inspected.append({k:v for k,v in z.items() if not k.startswith("_")})
    outputs.append({"source_G6_territorial_chain":cid,"speed_scenario_kmh":speed,
      "conservative_curvature_radius_screen_m":radius,
      "G7_original_smoothing_scale_m":source_geometry["smoothing_scale_m"],
      "source_G6_city_passage_reference_knots_PT_TM06":[list(p[1]) for p in SOURCE_CITY_POINTS],
      "source_G6_city_connector_lateral_offset_forced_zero":True,
      "lateral_research_amplitude_trials_m":[-1200,0,1200],
      "candidate_count":len(candidates),
      "candidates_passed_xy_curvature_and_3km_source_envelope":len(feasible_proxy),
      "inspected_candidates":inspected,
      "separate_best_candidates_by_18permille_and_25permille":winners,
      "not_certified_railway_feasible":True})
 records=[]
 for q in review_targets.values():
  q["source_G8_retained_chains_crossed_in_winner_hotspots"]=sorted(q["source_G8_retained_chains_crossed_in_winner_hotspots"])
  q["max_source_DSM_fraction_gt25m"]=round(q["max_source_DSM_fraction_gt25m"],4)
  q["requires_further_corridor_geometry_and_source_validation_before_DGT_download"]=True
  records.append(q)
 records.sort(key=lambda z:(-len(z["source_G8_retained_chains_crossed_in_winner_hotspots"]),
   -z["max_source_DSM_fraction_gt25m"],z["SW_grid_EPSG3763"]))
 shortlist=records[:12]
 all_ids=[id for q in shortlist for id in q["original_official_DGT_MDT2m_tile_IDs"]]
 if len(set(all_ids))!=len(all_ids) or any(z in acquired for z in all_ids):
  raise ValueError("potential_original_DGT_duplicates_or_reacquisitions")
 result={"mission":"MN-GEO-RAIL-001","stage":"G9_two_corridors_lateral_vertical_DSM_source_screening",
  "utc":datetime.now(timezone.utc).isoformat(),
  "source_SHA256":{"R1_original_GLO30_DSM":DSM_SHA,"G6_source_terrain_lattice":G6_SHA,
     "G8_speed_two_corridor_selection":G8_SHA,"G4_real_DGT2m_footprint":G4_SHA},
  "DGT_five_original_official_STAC_catalogue_receipts":proofs,
  "scope":"two_retained_G8_source_research_corridors_three_speeds_18and25permille",
  "mandatory_service_areas":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "city_centre_stations_not_required":True,
  "functional_access_by_road_network_not_verified":True,
  "source_GLO30_is_DSM_including_vegetation_not_bare_earth":True,
  "real_original_DGT_MDT2m_acquired_so_far_km2":121,
  "crossborder_vertical_reference_not_harmonized":True,
  "new_original_DGT_rasters_acquired":0,
  "max_lateral_normal_move_m":1200,
  "max_departure_from_each_original_G6_grid_m":3000,
  "research_degrees_per_speed_and_chain":7,
  "relative_score_weights_NOT_an_economic_or_engineering_approval":OBJECTIVE,
  "ramp_cases_permille":GRADES,
  "max_L1_vertical_slope_does_not_design_vertical_curves":True,
  "horizontal_screen_does_not_design_clothoids_or_real_rail_platform":True,
  "not_validated_railway_alignment_or_speed":True,
  "do_not_interpret_negative_DSM_residuals_as_tunnel_requirements":True,
  "all_source_terrain_study_scenarios":outputs,
  "source_DSM_conflict_windows_with_original_DGT_catalogue_not_yet_acquired":len(records),
  "ranked_metadata_only_DGT_2km_sectors_for_further_review_max12":shortlist,
  "official_original_DGT_tile_downloads_approved_or_performed":0,
  "Fxx_accepted":False,"Site_authorized":False}
 out_json.parent.mkdir(parents=True,exist_ok=True)
 out_json.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 out_geojson.parent.mkdir(parents=True,exist_ok=True)
 out_geojson.write_text(json.dumps({"type":"FeatureCollection",
   "name":"G9 2.5D DSM-only terrain research screening, not railways","features":geos},
    ensure_ascii=False)+"\n")
 md=["# G9 — duas faixas prioritárias: triagem lateral e vertical por velocidade",
   "", "**Pré-viabilidade / MDS Copernicus real de 30m. Não é um traçado ferroviário viável aprovado.**",
   "", "Foram consideradas 7 variantes por cadeia e velocidade: base e 6 deslocações laterais com amplitude máxima de 1,2 km, confinadas a cada um dos três módulos, sem desviar os setores locais de investigação de Vila Real e Bragança.",
   "Critérios: 160/200/250 km/h, raios exploratórios G7 (1,5/2,4/3,7 km), máximo de 3 km da linha da grelha original, ajuste vertical matemático 18‰ misto ou 25‰ passageiros, sobre MDS (não MDT).",
   "", "| Cadeia | Velocidade | Variantes XY válidas/7 | Melhor 18‰ | Melhoria indicativa 18‰ | Melhor 25‰ | Melhoria indicativa 25‰ |",
   "|---|---:|---:|---|---:|---|---:|"]
 for z in outputs:
  a=z["separate_best_candidates_by_18permille_and_25permille"]
  md.append(f"| {z['source_G6_territorial_chain']} | {z['speed_scenario_kmh']} | {z['candidates_passed_xy_curvature_and_3km_source_envelope']}/7 | {a['mixed_18permille']['winning_candidate']} | {a['mixed_18permille']['proxy_improvement_vs_baseline']} | {a['passenger_25permille']['winning_candidate']} | {a['passenger_25permille']['proxy_improvement_vs_baseline']} |")
 md+=["","## Áreas que justificam investigação com solo nu",
  f"Apenas {len(records)} setores de 2km presentes nas janelas de maior conflito MDS dos melhores percursos possuem quatro IDs DGT originais de catálogo ainda não adquiridos; máximo {len(shortlist)} na seleção abaixo. Não confundir o número de setores com cobertura contínua do corredor.",
  "Áreas críticas fora dos catálogos DGT auditados, ou no território espanhol, carecem de localização das fontes próprias, não de autorização fictícia de aquisição portuguesa.",
  ""]
 for z in shortlist:
  md.append(f"- PT-TM06 {z['SW_grid_EPSG3763']} · {','.join(z['source_G8_retained_chains_crossed_in_winner_hotspots'])} · MDS fração com desvio >25m: {z['max_source_DSM_fraction_gt25m']:.1%} · quatro IDs oficiais já validados")
 md+=["","## Portão de decisão", "Sem geometria de traçado ferrovia, espirais, curvas verticais, altitude de estações, MDT contínuo, geodesia PT–ES ou acessibilidade rodoviária efetiva, não classificar um corredor como construtivamente viável. O modelo de altimetria não fornece comprimentos de túneis/viadutos nem custos. Nenhum original DGT novo adquirido. Nenhum Fxx/Site autorizado.",""]
 out_md.parent.mkdir(parents=True,exist_ok=True)
 out_md.write_text("\n".join(md))
 summary=[{"chain":z["source_G6_territorial_chain"],"speed":z["speed_scenario_kmh"],
  "XYpass":z["candidates_passed_xy_curvature_and_3km_source_envelope"],
  "best18":z["separate_best_candidates_by_18permille_and_25permille"]["mixed_18permille"]["winning_candidate"],
  "deltaScore18":z["separate_best_candidates_by_18permille_and_25permille"]["mixed_18permille"]["proxy_improvement_vs_baseline"],
  "best25":z["separate_best_candidates_by_18permille_and_25permille"]["passenger_25permille"]["winning_candidate"],
  "deltaScore25":z["separate_best_candidates_by_18permille_and_25permille"]["passenger_25permille"]["proxy_improvement_vs_baseline"]} for z in outputs]
 print("G9_SOURCE_2P5D="+json.dumps({"screens":summary,"review_source_sectors":len(shortlist),"new_DGT_downloads":0},ensure_ascii=False,separators=(',',':')))
 return result

def main():
 a=argparse.ArgumentParser()
 for name in ("dsm","g6","g8","g4","b1","catalogues","json","geojson","markdown"):
  a.add_argument("--"+name,required=True,type=Path)
 p=a.parse_args()
 run(p.dsm,p.g6,p.g8,p.g4,p.b1,p.catalogues,p.json,p.geojson,p.markdown)
if __name__=="__main__":main()
