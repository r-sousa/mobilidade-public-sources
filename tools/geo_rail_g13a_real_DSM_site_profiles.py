#!/usr/bin/env python3
"""G13A: site-specific real Copernicus GLO30 DSM validation of G12 research points.

G12A points are ~source 2km lattice nearest points ±3km along a reference
line, NOT real stations. Here, real 30m surface elevations are profiled 1km
along the local research tangent, ±125m transverse, and vertical 18/25‰ L1
pressure is computed. Road minutes are actual OSRM to an OSM-snapped point
near that reference, NOT railway or real station access. Cost EUR and
station feasibility remain unknown. No private original acquisition.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import Point,LineString
from geo_rail_g7_rail_screen import DSM_SHA,grade_L1_profile
from geo_rail_g10_27_macro_portfolio import compose,G3_SHA,G5_SHA
from geo_rail_g11_urban_service import CITY
from geo_rail_g12_station_siting_and_operations import STUDY_COMBINATIONS

G12_SHA="d4f80818afb71a34632f86de9a1dca483b3406075d0cc003139aa0e82eb7c753"
G10_SHA="7677ed95f822ee8ada510f984f50ee498851e3bd948f9ed960e08f8620cc7287"
ANCHORS=("P1-2-1","P2-2-1","P2-2-3")
PROFILE_HALFLENGTH_M=500.
PROFILE_STEP_M=25.
TERRAIN_LATERAL_M=125.
LOCAL_DSM_ELEVATION_REFERENCE="Copernicus_GLO30_DSM_NOT_BARE_EARTH"
GRADE_CASES=(18.,25.)

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for ch in iter(lambda:f.read(2**20),b""):h.update(ch)
 return h.hexdigest()

def sampled_surface(ds,point_set,to_wgs):
 lon,lat=to_wgs.transform(point_set[:,0],point_set[:,1])
 cells=list(ds.sample(zip(lon.tolist(),lat.tolist()),masked=True))
 vals=[]
 for x in cells:
  # rasterio masked data can use np.ma mask; never coerce no-data to zero
  if bool(np.ma.getmaskarray(x)[0]):return None
  value=float(x[0])
  if not math.isfinite(value) or value<=-500:return None
  vals.append(value)
 return np.asarray(vals)

def one_site(site,line,ds,to_tm,to_wgs):
 xx,yy=to_tm.transform(*site["WGS84_research_coordinate"])
 q=Point(xx,yy)
 chainage=line.project(q)
 if chainage<PROFILE_HALFLENGTH_M or chainage>line.length-PROFILE_HALFLENGTH_M:
  return {"status":"not_screened_near_end_of_source_grid_line","DSMsample_source":"none"}
 a=line.interpolate(chainage-PROFILE_HALFLENGTH_M)
 b=line.interpolate(chainage+PROFILE_HALFLENGTH_M)
 dx=b.x-a.x;dy=b.y-a.y
 n=math.hypot(dx,dy)
 if n<500:return {"status":"not_screened_degenerate_1km_local_tangent","DSMsample_source":"none"}
 dx/=n;dy/=n
 distances=np.arange(-PROFILE_HALFLENGTH_M,PROFILE_HALFLENGTH_M+1.,PROFILE_STEP_M)
 xy=np.column_stack([xx+distances*dx,yy+distances*dy])
 east=xy.copy();west=xy.copy()
 east[:,0]-=dy*TERRAIN_LATERAL_M;east[:,1]+=dx*TERRAIN_LATERAL_M
 west[:,0]+=dy*TERRAIN_LATERAL_M;west[:,1]-=dx*TERRAIN_LATERAL_M
 mid=sampled_surface(ds,xy,to_wgs)
 flank_a=sampled_surface(ds,east,to_wgs)
 flank_b=sampled_surface(ds,west,to_wgs)
 if any(x is None for x in (mid,flank_a,flank_b)):
  return {"status":"real_DSM_NoData_or_outside_extent_fail_closed","DSMsample_source":"none"}
 lateral=np.maximum(np.abs(flank_a-mid),np.abs(flank_b-mid))
 profiles={}
 for grade in GRADE_CASES:
  fit=grade_L1_profile(mid,distances+PROFILE_HALFLENGTH_M,grade/1000.)
  resid=np.abs(fit-mid)
  assert np.all(np.abs(np.diff(fit))<=grade/1000.*np.diff(distances)+.001)
  profiles[str(int(grade))]={"gradient_cap_permille_mathematical":grade,
    "L1_p90_vertical_DSM_residual_m":round(float(np.quantile(resid,.9)),2),
    "L1_max_vertical_DSM_residual_m":round(float(np.max(resid)),2),
    "fraction_samples_DSM_vertical_residual_gt10m":round(float(np.mean(resid>10)),4),
    "fraction_samples_DSM_vertical_residual_gt25m":round(float(np.mean(resid>25)),4)}
 return {"status":"source_30m_DSM_1000m_ground_reference_proxy_sampled",
   "DSMsample_source":LOCAL_DSM_ELEVATION_REFERENCE,
   "total_real_DSM_pixels_sampled":len(mid)*3,
   "platform_screen_length_m":1000.,
   "surface_z_min_max_m":[round(float(np.min(mid)),2),round(float(np.max(mid)),2)],
   "one_km_DSM_p90_minus_p10_m":round(float(np.quantile(mid,.9)-np.quantile(mid,.1)),2),
   "one_km_DSM_endpoint_height_change_m":round(float(mid[-1]-mid[0]),2),
   "lateral_plusminus_125m_p90_absolute_surface_difference_m":round(float(np.quantile(lateral,.9)),2),
   "grade_sensitivity_profile":profiles,
   "continuous_surface_sample_is_NOT_native_DGT_or_IGN_terrain":True,
   "station_platform_grade_straightness_tangent_transition_and_elevation_unverified":True,
   "earthworks_tunnels_viaducts_and_costs_NOT_computed":True}

def non_dominated(sites):
 valid=[x for x in sites if x["terrain"]["status"].startswith("source_30m_DSM") and
   x["road_routing_valid_to_a_road_near_study_point"] and
   x["road_network_drive_minutes_to_research_road_snap"] is not None]
 dims=lambda x:(x["road_network_drive_minutes_to_research_road_snap"],
    x["terrain"]["grade_sensitivity_profile"]["25"]["L1_p90_vertical_DSM_residual_m"],
    x["terrain"]["lateral_plusminus_125m_p90_absolute_surface_difference_m"])
 result=[]
 for a in valid:
  if not any(b is not a and all(u<=v+1e-8 for u,v in zip(dims(b),dims(a))) and
      any(u<v-1e-8 for u,v in zip(dims(b),dims(a))) for b in valid):
   result.append(a)
 return sorted(result,key=lambda z:z["road_network_drive_minutes_to_research_road_snap"])

def main_work(g3path,g5path,g10path,g12path,dsmpath,jsonpath,mdpath):
 for p,d in ((g3path,G3_SHA),(g5path,G5_SHA),(g10path,G10_SHA),
             (g12path,G12_SHA),(dsmpath,DSM_SHA)):
  if sha(p)!=d:raise ValueError("G13_source_sha256_mismatch_"+p.name)
 g3=json.loads(g3path.read_text());g5=json.loads(g5path.read_text())
 g10=json.loads(g10path.read_text());g12=json.loads(g12path.read_text())
 if (g10["total_combinations"]!=27 or g12["cities_x_corridors_x_source_research_point_offsets"]!=[6,6,3] or
     not g12["Sanabria_excluded"] or g12["Fxx_accepted"] or g12["Site_authorized"]):
  raise ValueError("G13_source_G10_G12_and_governance_inconsistent")
 routes={id:LineString([(p[0]+1000,p[1]+1000) for p in route]) for id,_,route in compose(g3,g5)}
 to_tm=Transformer.from_crs(4326,3763,always_xy=True)
 to_wgs=Transformer.from_crs(3763,4326,always_xy=True)
 all_sites=[]
 with rasterio.open(dsmpath) as ds:
  if ds.crs.to_epsg()!=4326:raise ValueError("G13_source_DSM_wrong_CRS")
  for row in g12["six_corridor_city_reference_road_snap_minute_matrix"]:
   id=row["research_combination"]
   line=routes[id]
   for key in CITY:
    points=row["urban_markets"][key]["study_points"]
    if len(points)!=3:raise ValueError("G12_missing_three_study_points")
    for original in points:
     entry={k:v for k,v in original.items()}
     entry["research_combination"]=id
     entry["urban_market_key"]=key
     entry["terrain"]=one_site(original,line,ds,to_tm,to_wgs)
     all_sites.append(entry)
 if len(all_sites)!=108:raise ValueError("G13_only_partial_site_research")
 selection=[]
 for cid in STUDY_COMBINATIONS:
  for key in CITY:
   slots=[z for z in all_sites if z["research_combination"]==cid and z["urban_market_key"]==key]
   winners=non_dominated(slots)
   selection.append({"research_combination":cid,"urban_market":CITY[key]["label"],
     "mandatory":CITY[key]["mandatory"],"three_source_grid_research_points_considered":3,
     "passing_surface_DSM_source_profile_count":sum(z["terrain"]["status"].startswith("source_30m_DSM") for z in slots),
     "passing_real_road_to_study_point_count":sum(z["road_routing_valid_to_a_road_near_study_point"] for z in slots),
     "non_dominated_road_time_vs_DSM_terrain_reference_points":[
       {"offset_km":z["offset_along_2km_research_grid_km"],
        "real_road_time_to_nearest_grid_road_snap_min":z["road_network_drive_minutes_to_research_road_snap"],
        "L1_25permille_p90_vertical_surface_residual_m":z["terrain"]["grade_sensitivity_profile"]["25"]["L1_p90_vertical_DSM_residual_m"],
        "lateral_surface_p90_difference_125m_m":z["terrain"]["lateral_plusminus_125m_p90_absolute_surface_difference_m"],
        "reference_lon_lat":z["WGS84_research_coordinate"],
        "NOT_an_actual_station":True} for z in winners],
     "no_site_accepted_as_railway_station":True})
 summary=[]
 for cid in STUDY_COMBINATIONS:
  sub=[z for z in selection if z["research_combination"]==cid]
  summary.append({"research_combination":cid,
    "mandatory_markets_with_some_road_and_DSM_research_point":sum(x["mandatory"] and
      len(x["non_dominated_road_time_vs_DSM_terrain_reference_points"])>0 for x in sub),
    "additional_markets_with_some_road_and_DSM_research_point":sum(not x["mandatory"] and
      len(x["non_dominated_road_time_vs_DSM_terrain_reference_points"])>0 for x in sub),
    "all_six_markets_have_at_least_one_sensible_source_probe":all(len(x["non_dominated_road_time_vs_DSM_terrain_reference_points"])>0 for x in sub),
    "no_station_rail_engineering_accepted":True})
 result={"mission":"MN-GEO-RAIL-001","stage":"G13A_actual_Copernicus_surface_1km_near_research_station_108_reference_sites",
   "utc":datetime.now(timezone.utc).isoformat(),
   "source_sha256":{"G3":G3_SHA,"G5":G5_SHA,"G10":G10_SHA,"G12A":G12_SHA,"original_GLO30_DSM":DSM_SHA},
   "actual_surface_sampled_not_ground":True,"one_km_local_tangent_not_real_track_curve":True,
   "ineligible_to_infer_feasible_station_platform":True,
   "allowed_rail_engineering_speeds_kmh":[160,200,250],
   "mandatory_service_markets":["Vila Real","Bragança"],"Sanabria_excluded":True,
   "source_G12A_real_OSRM_road_access_is_ONLY_nearby_road_to_source_point":True,
   "no_actual_station_parcel_landuse_ground_level_or_road_legal_access":True,
   "no_census_job_catchment_cost_eur_passenger_demand":True,
   "no_new_authenticated_DGT_or_CNIG_ground_download":True,
   "site_counts":{"original_research_points":len(all_sites),
      "actual_GLO30_source_DSM_cross_and_longitudinal_profile_success":sum(z["terrain"]["status"].startswith("source_30m_DSM") for z in all_sites),
      "real_OSRM_road_reference_route_valid":sum(bool(z["road_routing_valid_to_a_road_near_study_point"]) for z in all_sites)},
   "theoretical_vertical_profile_grade_caps_permille":list(GRADE_CASES),
   "site_local_screen_parameters":{"line_length_m":1000,"step_m":25,"cross_line_offsets_m":[-125,0,125]},
   "non_dominated_reference_site_screens_per_market":selection,
   "six_corridor_research_summary":summary,
   "all_108_observed_source_research_surface_points":all_sites,
   "Fxx_accepted":False,"Site_authorized":False}
 jsonpath.parent.mkdir(parents=True,exist_ok=True)
 jsonpath.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 md=["# G13A — exposição real ao relevo dos pontos de interface em estudo",
  "","Ensaio sobre MDS Copernicus 30m: amostragem longitudinal de 1000 m, separação de 25 m, duas amostras transversais ±125m e ajuste vertical matemático a 18‰/25‰. É solo *superficial* com vegetação e edifícios, não MDT de terreno nem projeto de plataforma ferroviária.",
  "", "| Combinação | Nós obrigatórios com pelo menos um teste rodoviário + MDS | Outros nós com pelo menos um teste | Estação de engenharia validada |",
  "|---|---:|---:|---|"]
 for q in summary:md.append(f"| {q['research_combination']} | {q['mandatory_markets_with_some_road_and_DSM_research_point']}/2 | {q['additional_markets_with_some_road_and_DSM_research_point']}/4 | Não |")
 md+=["","## Candidaturas de investigação não dominadas entre três posições de cada cidade",
   "Não é ordenação de terrenos. Comparar apenas o tempo rodoviário medido até uma via próxima e o desvio vertical de superfície perante uma rampa matemática; ambos podem melhorar ou piorar quando se defina uma estação real.",
   "", "| Combinação | Cidade | Deslocação longitudinal ao ponto central | Acesso por estrada a ponto de grelha (min) | Perfil MDS 25‰ P90 (m) |",
   "|---|---|---:|---:|---:|"]
 for z in selection:
  for q in z["non_dominated_road_time_vs_DSM_terrain_reference_points"]:
   md.append(f"| {z['research_combination']} | {z['urban_market']} | {q['offset_km']:+g} km | {q['real_road_time_to_nearest_grid_road_snap_min']} | {q['L1_25permille_p90_vertical_surface_residual_m']} |")
 md+=["","O portão de validação de eventual estação requer: geometria em reta ou curva admissível, desenvolvimento e comprimento de plataforma, rampas na plataforma e aproximações, implantação à cota do MDT real, acesso público legal, ciclovias/peões/transportes coletivos, compatibilidade de ordenamento do território e propriedade, ambiente, riscos geotécnicos e procura de transporte.",
  "Sem novos originais DGT, sem dados privados, sem Fxx/Site.", ""]
 mdpath.parent.mkdir(parents=True,exist_ok=True);mdpath.write_text("\n".join(md))
 print("G13A_STATION_DSM="+json.dumps({"counts":result["site_counts"],"summary":summary,
   "few_verified":selection[:3]},ensure_ascii=False,separators=(',',':')))
 return result

def main():
 p=argparse.ArgumentParser()
 for k in ("g3","g5","g10","g12","dsm","json","markdown"):
  p.add_argument("--"+k,type=Path,required=True)
 a=p.parse_args()
 main_work(a.g3,a.g5,a.g10,a.g12,a.dsm,a.json,a.markdown)
if __name__=="__main__":main()
