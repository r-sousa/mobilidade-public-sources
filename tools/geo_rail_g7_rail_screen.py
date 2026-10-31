#!/usr/bin/env python3
"""G7 corridor *necessary-condition screening*, 160/200/250 km/h.

Source: immutable actual R1 Copernicus GLO30 DSM + G6 grid-center
exploratory chains. Smooths those grid paths to assess horizontal curvature
and minimum vertical profile departure under illustrative gradient caps.
Cannot certify a railway alignment, structure quantity or feasible speed.
Native ground DGT/IGN is NOT continuous across any full chain.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import rasterio
from pyproj import Transformer
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from shapely.geometry import Point,LineString,mapping
from shapely.ops import transform as shape_transform

G6_SHA="faa2f1d218c79a3647a0d32217ab7bd460cc8aed418750ac62b41844d2d5bc9d"
DSM_SHA="a708b502b2eb86236c70f2d74322e9d8e2ea1417eb24094d0e43536845407bd9"
# Conservative screening radii, not automatic regulatory minima. See source references in report.
# Broad gauge 1668mm, illustrative 1740mm effective running-centre separation;
# screen D=160 mm, I=100 mm. Physics R= e*V^2 /(12.96*g*(D+I)).
# Round upward to permit screening margin for transition/cant rate uncertainties.
SPEEDS={160:1500.,200:2400.,250:3700.}
GRADIENTS_PERMILLE={"mixed_18permille":18.0,"passenger_25permille":25.0,
                     "passenger_sensitivity_35permille":35.0}
SMOOTH_SCALE_M=(450.,750.,1100.,1500.,2000.,2700.,3600.,4800.,6500.,8500.)
MAX_REF_DISPLACEMENT_M=3000.
STEP_M=200.
SOURCE_NOTE={
 "TSI_INF_2023":"https://eur-lex.europa.eu/eli/reg/2014/1299/2023-09-28/eng",
 "equilibrium_cant_iberian_gauge_research":"https://www.mdpi.com/2071-1050/14/14/8377"
}
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()

def dense(path,step_m=STEP_M):
 p=np.asarray(path,dtype=float)
 if len(p)<6:raise ValueError("source_research_route_too_short")
 if not np.isfinite(p).all():raise ValueError("invalid_coordinates")
 d=np.linalg.norm(np.diff(p,axis=0),axis=1)
 if np.any(d<=0) or np.any(d>2829.):raise ValueError("invalid_2km_source_grid_topology")
 dist=np.r_[0.,np.cumsum(d)]
 ss=np.arange(0.,dist[-1],step_m)
 if ss[-1]!=dist[-1]:ss=np.r_[ss,dist[-1]]
 return ss,np.column_stack([np.interp(ss,dist,p[:,axis]) for axis in (0,1)])

def smooth(points,sigma_m,step_m=STEP_M):
 sigma=sigma_m/step_m
 q=np.column_stack([gaussian_filter1d(points[:,k],sigma,mode="nearest") for k in (0,1)])
 t=np.linspace(0.,1.,len(points))
 q+=(1.-t)[:,None]*(points[0]-q[0])+t[:,None]*(points[-1]-q[-1])
 return q

def radius_screen(points):
 x=points[:,0];y=points[:,1]
 # Derivatives by cumulative *smoothed* arc distance, not the input lattice path.
 s=np.r_[0.,np.cumsum(np.hypot(np.diff(x),np.diff(y)))]
 if np.any(np.diff(s)<2.):return None
 dx=np.gradient(x,s,edge_order=2);dy=np.gradient(y,s,edge_order=2)
 ddx=np.gradient(dx,s,edge_order=2);ddy=np.gradient(dy,s,edge_order=2)
 k=np.abs(dx*ddy-dy*ddx)/(dx*dx+dy*dy)**1.5
 # Filter only derivative edge neighbourhood; fixed endpoints and source
 # interfaces need independently engineered transitions (NOT accepted here).
 k=k[10:-10]
 if not len(k) or not np.isfinite(k).all():return None
 r=1./np.maximum(k,1.e-10)
 return float(np.min(r)),float(np.quantile(r,.05))

def distance_from_source(points,reference):
 line=LineString(reference)
 d=np.asarray([line.distance(Point(float(x),float(y))) for x,y in points])
 return float(d.max()),float(np.quantile(d,.95))

def choose_geometry(source,minimum_radius):
 original_s,original=dense(source)
 best=None
 attempts=[]
 for sigma in SMOOTH_SCALE_M:
  q=smooth(original,sigma)
  rr=radius_screen(q)
  if rr is None:continue
  deviation=distance_from_source(q,source)
  length=float(np.sum(np.linalg.norm(np.diff(q,axis=0),axis=1))/1000.)
  ok=rr[0]>=minimum_radius and deviation[0]<=MAX_REF_DISPLACEMENT_M
  attempts.append({"smoothing_scale_m":sigma,"min_proxy_radius_m":round(rr[0],1),
    "p05_proxy_radius_m":round(rr[1],1),
    "max_distance_to_source_research_polyline_m":round(deviation[0],1),
    "screening_length_km_not_rail_distance":round(length,3),"passes_both_screening_checks":ok})
  if ok:
   best=(q,attempts[-1])
   break
 return best,attempts

def grade_envelopes(z,s,grade_per_m):
 """Optimal Chebyshev L-infinity Lipschitz fit to DSM signal on a 1D chain.

 h=(max_j[z_j-g*|s_i-s_j|]+min_j[z_j+g*|s_i-s_j|])/2
 obeys |h_i-h_{i-1}|<=g*|s_i-s_{i-1}|, but is NOT a cost-optimal
 vertical alignment and does not enforce real station elevations.
 """
 lhs=np.maximum.accumulate(z+grade_per_m*s)-grade_per_m*s
 rhs=np.maximum.accumulate((z-grade_per_m*s)[::-1])[::-1]+grade_per_m*s
 lower=np.maximum(lhs,rhs)
 lhs2=np.minimum.accumulate(z-grade_per_m*s)+grade_per_m*s
 rhs2=np.minimum.accumulate((z+grade_per_m*s)[::-1])[::-1]-grade_per_m*s
 upper=np.minimum(lhs2,rhs2)
 h=(lower+upper)/2
 assert np.all(np.abs(np.diff(h))<=grade_per_m*np.diff(s)+1.e-5)
 return h

def sample_dsm(ds,projected):
 to_wgs=Transformer.from_crs(3763,4326,always_xy=True)
 lon,lat=to_wgs.transform(projected[:,0].tolist(),projected[:,1].tolist())
 raw=np.asarray([t[0] for t in ds.sample(zip(lon,lat),masked=True)],dtype=float)
 if len(raw)!=len(projected) or not np.isfinite(raw).all() or np.any(raw<-500):
  raise ValueError("GLO30_source_surface_data_invalid")
 return raw

def grade_L1_profile(z,s,grade_per_m):
 """Least-absolute-departure vertical PROFILE PROXY on source DSM (not rail).

 Sparse HiGHS LP: minimise sum_i u_i subject to |h_i-z_i|<=u_i,
 |h_(i+1)-h_i|<=grade*segment_length. No station heights, structures,
 vertical-curve radii, or bare-earth measurements are represented.
 """
 n=len(z)
 if n<2:raise ValueError("too_short_vertical_DSM_source")
 I=[];J=[];V=[];bound=[]
 def constraint(vs,b):
  k=len(bound)
  for j,val in vs:
   I.append(k);J.append(j);V.append(val)
  bound.append(b)
 for i in range(n):
  constraint(((i,1.),(n+i,-1.)),float(z[i]))
  constraint(((i,-1.),(n+i,-1.)),float(-z[i]))
 for i in range(n-1):
  d=grade_per_m*(s[i+1]-s[i])
  constraint(((i,-1.),(i+1,1.)),float(d))
  constraint(((i,1.),(i+1,-1.)),float(d))
 A=coo_matrix((V,(I,J)),shape=(len(bound),2*n)).tocsr()
 c=np.r_[np.zeros(n),np.ones(n)]
 sol=linprog(c,A_ub=A,b_ub=np.asarray(bound),
             bounds=[(None,None)]*n+[(0,None)]*n,
             method="highs",options={"time_limit":90.0})
 if not sol.success or sol.x is None:
  raise ValueError("conservative_L1_source_DSM_gradient_program_no_solution_"+str(sol.message))
 h=sol.x[:n]
 if np.any(np.abs(np.diff(h))>grade_per_m*np.diff(s)+.001):
  raise ValueError("L1_vertical_screen_exceeds_grade_limit")
 return h

def vertical_pressure(points,heights,gradient):
 seg=np.linalg.norm(np.diff(points,axis=0),axis=1)
 s=np.r_[0,np.cumsum(seg)]
 h=grade_L1_profile(heights,s,gradient/1000.)
 delta=h-heights
 # No turn values into tunnel/viaduct counts; DSM can include treetops/buildings.
 threshold={}
 for t in (10.,25.,50.):
  threshold[f"residual_abs_gt_{int(t)}m_screening_fraction"]=round(float(np.mean(np.abs(delta)>t)),4)
  threshold[f"line_below_DSM_gt_{int(t)}m_fraction"]=round(float(np.mean(delta< -t)),4)
  threshold[f"line_above_DSM_gt_{int(t)}m_fraction"]=round(float(np.mean(delta>t)),4)
 return {"longitudinal_grade_cap_permille_hypothetical":gradient,
   "L1_minimum_total_abs_line_vs_DSM_max_departure_m":round(float(np.max(np.abs(delta))),2),
   "vertical_objective":"minimum_total_absolute_DSM_departure_under_simple_gradient_cap_NOT_railway_design",
   "p90_abs_line_vs_DSM_surface_m":round(float(np.quantile(np.abs(delta),.9)),2),
   "fraction_of_profile_distance_with_DSM_pressure_gt25m_proxy":threshold["residual_abs_gt_25m_screening_fraction"],
   "endpoint_line_DSM_vertical_differences_m":[round(float(delta[0]),2),round(float(delta[-1]),2)],
   **threshold,"NOT_tunnel_viaduct_earthwork_or_train_profile":True}

def evaluate(dsm_path,g6_path,jsonout,geoout,markdown):
 if sha(dsm_path)!=DSM_SHA or sha(g6_path)!=G6_SHA:raise ValueError("immutable_primary_source_sha256_mismatch")
 g6=json.loads(g6_path.read_text())
 if (len(g6["end_to_end_research_chains"])!=3 or
     g6["mandatory_service_areas"]!=["Vila Real","Bragança"] or
     not g6["Sanabria_excluded"] or
     g6["Fxx_accepted"] or g6["Site_authorized"]):
  raise ValueError("source_G6_preacceptance_contract_mismatch")
 rows=[];features=[]
 t=Transformer.from_crs(3763,4326,always_xy=True)
 with rasterio.open(dsm_path) as ds:
  if ds.crs.to_epsg()!=4326:raise ValueError("wrong_30m_surface_CRS")
  for chain in g6["end_to_end_research_chains"]:
   source=[(p[0]+1000,p[1]+1000) for p in chain["source_grid_cells_epsg3763"]]
   for speed,rad in SPEEDS.items():
    candidate,attempts=choose_geometry(source,rad)
    scenario={"chain_id":chain["study_chain_id"],"speed_scenario_kmh":speed,
     "conservative_hypothetical_radius_screen_m":rad,
     "source_route_length_km":chain["diagonal_and_orthogonal_study_grid_length_km_NOT_railway_distance"],
     "candidate_within_3km_of_source_grid_found":candidate is not None,
     "all_tested_horizontal_smoothing_scale_screens":attempts,
     "design_speed_along_every_cell_not_guaranteed":True,
     "functional_station_area_access_not_verified":True}
    if candidate is None:
     scenario["status"]="HORIZONTAL_SCREEN_NOT_DEMONSTRATED_WITHIN_3KM_G6_BAND"
     rows.append(scenario)
     continue
    pts,proof=candidate
    heights=sample_dsm(ds,pts)
    pressures={name:vertical_pressure(pts,heights,g) for name,g in GRADIENTS_PERMILLE.items()}
    scenario.update({"status":"BASIC_CURVATURE_RADIUS_PROXY_SCREEN_ONLY_NOT_FEASIBILITY",
       "selected_horizontal_smoothing":proof,
       "source_GLO30_DSM_sample_count":len(heights),
       "DSM_profile_min_max_m":[round(float(heights.min()),2),round(float(heights.max()),2)],
       "longitudinal_gradient_screening":pressures,
       "no_survey_ground_DTM_no_vertical_reference_compatibility":True,
       "no_cant_ramp_transition_spiral_or_vertical_curve_designed":True,
       "corridor_hazardous_structure_pressure_is_proxy_only":True,
       "cannot_be_classified_feasible_in_engineering":True})
    lon,lat=t.transform(pts[:,0].tolist(),pts[:,1].tolist())
    geometry=LineString(list(zip(lon,lat)))
    features.append({"type":"Feature","geometry":mapping(geometry),
     "properties":{"chain_id":chain["study_chain_id"],"scenario_kmh":speed,
      "geometry":"smoothed_source_grid_study_screen_NOT_track_alignment",
      "radius_screen_m":rad,"max_reference_deviation_m":proof["max_distance_to_source_research_polyline_m"],
      "all_stations_unverified":True,"railway_feasibility_not_certified":True}})
    rows.append(scenario)
 result={"mission":"MN-GEO-RAIL-001","stage":"G7_speed_curve_and_vertical_DSM_necessary_condition_screen",
   "timestamp_utc":datetime.now(timezone.utc).isoformat(),
   "speed_scenarios_kmh":list(SPEEDS),
   "conservative_research_radius_thresholds_m":{str(k):v for k,v in SPEEDS.items()},
   "vertical_gradient_sensitivities_permille":GRADIENTS_PERMILLE,
   "nominal_iberian_gauge_mm":1668,
   "radius_thresholds_NOT_TSI_mandated_values":True,
   "source_references":SOURCE_NOTE,
   "source_G6_SWA_filename_sha256":G6_SHA,
   "source_GLO30_original_grid_SHA256":DSM_SHA,
   "mandatory_service_areas":["Vila Real","Bragança"],
   "city_center_stations_required":False,"Sanabria_excluded":True,
   "research_corridor_3000m_halfwidth_is_not_reserved_land":True,
   "geometry_screen_estimates_conservative_min_radius_not_transition_clothoid":True,
   "longitudinal_fit_does_not_enforce_station_height_or_vertical_curve":True,
   "source_GLO30_is_DSM_including_vegetation_buildings_not_bare_earth":True,
   "PT_ES_vertical_datum_not_harmonized":True,
   "no_tunnel_viaduct_earthwork_cost_or_station_travel_time_estimates":True,
   "gauge_international_interoperability_not_confirmed":True,
   "Fxx_accepted":False,"Site_authorized":False,
   "scenarios":rows}
 for path,obj in [(jsonout,result),(geoout,{"type":"FeatureCollection",
   "name":"G7 radius-DSM screening only; NOT railway alignments",
   "features":features})]:
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
 md=["# G7 — triagem de curvatura e pressão de relevo (não certificação de viabilidade)",
   "","Bitola ibérica ilustrativa 1668 mm; cenários **160, 200, 250 km/h**; raios de triagem conservadores **1500, 2400, 3700 m**. Não são mínimos normativos universais. Sensibilidades de rampa **18‰ misto, 25‰ passageiros, 35‰ apenas sensibilidade**; 35‰ exige restrições adicionais e não se aplica automaticamente.",
   "", "| Cadeia | Velocidade | Raio indicativo | Admite suavização no corredor 3 km? | Distância suavizada km (não ferroviária) | Desvio máximo ao eixo G6 m | P90 desvio vertical MDS a 25‰ m | Fração perfil com desvio MDS >25m a 25‰ |",
   "|---|---:|---:|---|---:|---:|---:|---:|"]
 for r in rows:
  p=r.get("selected_horizontal_smoothing",{})
  vv=r.get("longitudinal_gradient_screening",{}).get("passenger_25permille",{})
  md.append(f"| {r['chain_id']} | {r['speed_scenario_kmh']} | {r['conservative_hypothetical_radius_screen_m']:.0f} | {'sim' if r['candidate_within_3km_of_source_grid_found'] else 'não demonstrado'} | {p.get('screening_length_km_not_rail_distance','—')} | {p.get('max_distance_to_source_research_polyline_m','—')} | {vv.get('p90_abs_line_vs_DSM_surface_m','—')} | {vv.get('fraction_of_profile_distance_with_DSM_pressure_gt25m_proxy','—')} |")
 md+=["","## Limites que impedem declarar um corredor viável",
  "- Uma poligonal suavizada não é uma sucessão projetada de retas, clotóides e curvas circulares, nem inclui rampas de transição, drenagem, pontes, túneis, plataformas ferroviárias e implantação de estações.",
  "- Os desvios verticais são **MDS Copernicus 30m**, incluem vegetação e edifícios; o ajuste vertical de 18/25/35‰ apenas limita o declive matemático. Não são extensões de túnel nem viaduto.",
  "- A velocidade máxima de projeto pode ser menor nas aproximações às duas áreas urbanas, mesmo havendo viabilidade em plena via; os tempos de viagem não se deduzem desta grelha.",
  "- Limite artificial de 3 km à linha da grelha G6: não demonstrar uma opção neste envelope não significa inviabilidade fora dele.",
  "- **35‰** só na sensibilidade teórica de passageiros; considerar regras relativas a gradiente médio, extensão e material circulante, e avaliação específica de engenharia. Não impor a tráfego misto.",
  "- Sem harmonização altimétrica Portugal–Espanha, rede viária para acesso às estações ou geometria de solo nu contínua.",
  "","Fontes normativas e físicas: "+SOURCE_NOTE["TSI_INF_2023"]+" ; "+SOURCE_NOTE["equilibrium_cant_iberian_gauge_research"],
  "","**Estado: pré-aceitação, sem Fxx e Site.**"]
 markdown.parent.mkdir(parents=True,exist_ok=True);markdown.write_text("\n".join(md)+"\n")
 concise=[{"chain":r["chain_id"],"speed":r["speed_scenario_kmh"],
   "geometry_pass":r["candidate_within_3km_of_source_grid_found"],
   "max_deviation_m":r.get("selected_horizontal_smoothing",{}).get("max_distance_to_source_research_polyline_m"),
   "p90_dsm_vertical_offset_m":r.get("longitudinal_gradient_screening",{}).get("passenger_25permille",{}).get("p90_abs_line_vs_DSM_surface_m"),
   "frac_DSM_pressure_gt25m":r.get("longitudinal_gradient_screening",{}).get("passenger_25permille",{}).get("fraction_of_profile_distance_with_DSM_pressure_gt25m_proxy")} for r in rows]
 print("G7_SPEED_SCREEN="+json.dumps(concise,separators=(',',':')))
 return result

def main():
 a=argparse.ArgumentParser()
 for name in ("dsm","g6","json","geojson","markdown"):
  a.add_argument("--"+name,required=True,type=Path)
 z=a.parse_args()
 evaluate(z.dsm,z.g6,z.json,z.geojson,z.markdown)
if __name__=="__main__":main()
