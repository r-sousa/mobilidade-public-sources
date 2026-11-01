#!/usr/bin/env python3
"""G24A: join 3 actual G10 2km research corridor polylines with 351 G23B original
DGT MDT2m mandatory-city local study-strip variants. Not railway geometry.

Necessary-context screens only: shortest planimetric distance to the source
2km grid polyline; 3/6-km source-grid chord bearing uncertainty; candidate
undirected platform-bearing mismatch; and a theoretical pure circular-turn
lower-bound arc length R*theta at illustrative radii from G7.
NO track construction, route connection, curvature compliance or €/m3 inferred.
No new DGT/INE/router/GTFS acquisition. WGS84 GeoJSON for GIS, original
coordinates in PT-TM06 EPSG3763.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
from collections import defaultdict
from shapely.geometry import shape,Point,mapping
from shapely.ops import transform as trgeom
from pyproj import Transformer

G10_SHA="77d226cc842d33e2f799f2c269ddde57a17cb7d868791770c1624dda1b86136d"
G23B_SHA="7a623066e2cc8e512db652f14bc70b50ebe12e0d80d1ae4c9ccabb1c3d290dce"
FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
MARKETS=("Vila_Real","Braganca")
RADIUS_BY_SPEED={160:1500.0,200:2400.0,250:3700.0}
SOURCE_BAND_HALF_WIDTH_M=3000
CHORD_WINDOWS_M=(3000.,6000.)

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for data in iter(lambda:f.read(1024*1024),b""):h.update(data)
 return h.hexdigest()

def axis_bearing_mismatch_deg(a,b):
 """Undirected tangent axes: a station may be entered from either end."""
 diff=abs((a-b+90.)%180.-90.)
 assert 0<=diff<=90
 return diff

def chord_axis(line,station_m,window):
 low=max(0.,station_m-window)
 high=min(line.length,station_m+window)
 a=line.interpolate(low);b=line.interpolate(high)
 if a.distance(b)<100:raise ValueError("G24_source_polyline_local_chord_degenerate")
 return (math.degrees(math.atan2(b.y-a.y,b.x-a.x))%180.)

def source_angular_context(line,point,station_heading):
 s=line.project(point)
 near=line.interpolate(s)
 bearings=[chord_axis(line,s,w) for w in CHORD_WINDOWS_M]
 mismatch=[axis_bearing_mismatch_deg(z,station_heading) for z in bearings]
 uncertainty=axis_bearing_mismatch_deg(*bearings)
 # This R*delta is PURE turning-arc length lower bound when heading change
 # occurs on a curvature bound R, not a minimum actual station connector
 # length, speed feasibility, or construction distance.
 screening={str(speed):{
  "hypothetical_radius_m_NOT_certified_design":radius,
  "pure_constant_radius_turn_arc_length_m_lower_bound_for_this_angle":round(radius*math.radians(mismatch[0]),1),
  "transition_curve_cant_and_tangent_entry_NOT_modelled":True
 } for speed,radius in RADIUS_BY_SPEED.items()}
 return {"distance_to_original_G10_2km_grid_route_m":round(point.distance(line),2),
  "nearest_G10_original_2km_polyline_point_EPSG3763_XY":[round(near.x,2),round(near.y,2)],
  "nearest_position_along_G10_2km_grid_route_km":round(s/1000.,3),
  "G10_2km_source_grid_local_3km_chord_axis_degrees":round(bearings[0],3),
  "G10_2km_source_grid_local_6km_chord_axis_degrees":round(bearings[1],3),
  "local_source_grid_bearing_window_uncertainty_deg":round(uncertainty,3),
  "hypothetical_station_straight_heading_mismatch_to_3km_source_grid_chord_deg":round(mismatch[0],3),
  "hypothetical_station_heading_mismatch_to_6km_source_grid_chord_deg":round(mismatch[1],3),
  "within_original_3km_halfwidth_research_band_NOT_rail_corridor":point.distance(line)<=SOURCE_BAND_HALF_WIDTH_M,
  "illustrative_speed_radius_pure_heading_change_arc_lower_bounds":screening}

def choose_shortlist(cases):
 """Separate geometry/terrain objectives; no invented single cost ranking."""
 valid=[x for x in cases if x["G23B_original_DGT2m_platform_and_approach_coverage_ge_98pct"]]
 if not valid:return []
 old=[x for x in valid if x["original_source_reference_position_and_heading_unchanged"]]
 if len(old)!=1:raise ValueError("G24_reference_baseline_exactly_once_required")
 chosen=[("BASELINE",old[0])]
 # Geometric screen best first; no implied crossing or legal access.
 s1=min(valid,key=lambda x:(not x["within_original_3km_halfwidth_research_band_NOT_rail_corridor"],
   x["distance_to_original_G10_2km_grid_route_m"],
   x["hypothetical_station_straight_heading_mismatch_to_3km_source_grid_chord_deg"],
   x["G23B_station_vertical_p90_DGT2m_m"]))
 # Terrain screen best first, but prefer within 3km original source grid
 # research band; no extrapolation of true road access at new location.
 shortlist_pool=[x for x in valid if x["within_original_3km_halfwidth_research_band_NOT_rail_corridor"]] or valid
 s2=min(shortlist_pool,key=lambda x:(x["G23B_station_vertical_p90_DGT2m_m"]+
     x["G23B_approach_18permille_vertical_p90_DGT2m_m"],
     x["distance_to_original_G10_2km_grid_route_m"],
     x["hypothetical_station_straight_heading_mismatch_to_3km_source_grid_chord_deg"]))
 for label,record in (("GEOMETRIC_SOURCE_CONTEXT",s1),("GROUND_RELIEF_SOURCE_CONTEXT",s2)):
  if all(record is not already for _,already in chosen):
   chosen.append((label,record))
 return chosen

def compute(g10path,g23path,outpath,geopath,mdpath):
 if sha(g10path)!=G10_SHA or sha(g23path)!=G23B_SHA:
  raise ValueError("G24_exact_published_original_G10_G23B_SHA_drift")
 g10=json.loads(g10path.read_text());g23=json.loads(g23path.read_text())
 features=g10.get("features",[])
 if len(features)!=27 or len(g23["351_original_source_shift_angle_terrain_cases"])!=351 or not g23["Sanabria_excluded"] or g23["Fxx_accepted"] or g23["Site_authorized"]:
  raise ValueError("G24_source_27_corridors_351_local_DGT2m_trials_not_complete")
 topt=Transformer.from_crs(4326,3763,always_xy=True)
 togeo=Transformer.from_crs(3763,4326,always_xy=True)
 routes={}
 for f in features:
  id=f["properties"]["id"]
  if id not in FAMILIES:continue
  if f["properties"]["this_is_not_an_approved_or_proposed_railway_alignment"] is not True:
   raise ValueError("G10_cannot_be_accepted_as_a_real_rail_alignment")
  route=trgeom(topt.transform,shape(f["geometry"]))
  if route.geom_type!="LineString" or route.length<100000:raise ValueError("G10_wrong_route_geometry")
  routes[id]=route
 if set(routes)!=set(FAMILIES):raise ValueError("G24_three_corridor_families_missing")
 measured=[];groups=defaultdict(list)
 for row in g23["351_original_source_shift_angle_terrain_cases"]:
  fam=row["source_family"];city=row["mandatory_market"]
  if fam not in routes or city not in MARKETS:raise ValueError("G24_non_mandatory_site_or_family")
  x,y=row["candidate_EPSG3763_XY"]
  original_heading=(row["source_study_tangent_heading_deg"]+row["source_tangent_heading_rotation_deg"])%180.
  hit=source_angular_context(routes[fam],Point(x,y),original_heading)
  v={"source_research_family":fam,"mandatory_market":city,
     "G23B_study_seed_id":row["study_seed_id"],
     "candidate_original_DGT_study_EPSG3763_XY":[x,y],
     "G23B_station_straight_source_tangent_heading_deg":round(original_heading,3),
     "G23B_original_DGT2m_platform_and_approach_coverage_ge_98pct":row["valid_coverage_98pct_station_and_approach"],
     "G23B_station_vertical_p90_DGT2m_m":row["station_p90_m"],
     "G23B_approach_18permille_vertical_p90_DGT2m_m":row["approach18_p90_m"],
     "G23B_shift_longitudinal_from_original_reference_m":row["longitude_shift_along_source_tangent_m"],
     "G23B_shift_lateral_from_original_reference_m":row["lateral_shift_relative_to_source_tangent_m"],
     "G23B_source_tangent_rotation_delta_deg":row["source_tangent_heading_rotation_deg"],
     "original_source_reference_position_and_heading_unchanged":row["study_site_location_unchanged"] and row["study_line_orientation_unchanged"],
     **hit,
     "unmeasured_candidate_road_drive_minutes":None,
     "unmeasured_land_rights_and_road_legal_access":True,
     "horizontal_track_transition_and_s_curve_NOT_engineered":True,
     "vertical_profile_curves_and_earthwork_structures_NOT_engineered":True,
     "no_real_railway_station_or_design_speed_certified":True}
  measured.append(v)
  groups[(city,fam,row["study_seed_id"])].append(v)
 if len(measured)!=351 or len(groups)!=13:raise ValueError("G24_351_original_G23B_cases_13_study_groups_missing")
 short=[];fgeo=[]
 for (city,fam,seed),cases in sorted(groups.items()):
  a=choose_shortlist(cases)
  if not a:raise ValueError("G24_original_ground_valid_study_seed_missing")
  for kind,case in a:
   s={**case,"screening_role":kind,
      "original_G10_2km_polyline_NOT_railway_geometry":True,
      "new_road_access_assessment_required":True,
      "new_local_native_profile_multiaxis_not_tunnel_viaduct_quantification":True}
   short.append(s)
   lon,lat=togeo.transform(*case["candidate_original_DGT_study_EPSG3763_XY"])
   fgeo.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
    "properties":{k:v for k,v in s.items() if k not in ("illustrative_speed_radius_pure_heading_change_arc_lower_bounds",)}})
 # Keep source 2km lines in same collection, visibly marked as grid
 # sketches, never modeled connectors from G23B point to G10 line.
 for fam in FAMILIES:
  line=trgeom(togeo.transform,routes[fam])
  fgeo.append({"type":"Feature","geometry":mapping(line),
    "properties":{"layer":"G10_original_2km_research_grid_route_NOT_a_railway_alignment",
      "source_research_family":fam,
      "not_engineered_horizontal_geometry":True,
      "not_station_to_corridor_connection":True}})
 states=defaultdict(lambda:{"n":0,"original_valid":0,"in_band":0,"within_band_and_native":0,"heading_over30_within_band":0,"nearest_distance_m":float("inf")})
 for v in measured:
  st=states[(v["mandatory_market"],v["source_research_family"])]
  st["n"]+=1
  st["original_valid"]+=bool(v["G23B_original_DGT2m_platform_and_approach_coverage_ge_98pct"])
  st["in_band"]+=v["within_original_3km_halfwidth_research_band_NOT_rail_corridor"]
  st["within_band_and_native"]+=(v["G23B_original_DGT2m_platform_and_approach_coverage_ge_98pct"] and v["within_original_3km_halfwidth_research_band_NOT_rail_corridor"])
  st["heading_over30_within_band"]+=(v["within_original_3km_halfwidth_research_band_NOT_rail_corridor"] and v["hypothetical_station_straight_heading_mismatch_to_3km_source_grid_chord_deg"]>30)
  st["nearest_distance_m"]=min(st["nearest_distance_m"],v["distance_to_original_G10_2km_grid_route_m"])
 summary=[{"mandatory_market":k[0],"research_family":k[1],**v} for k,v in sorted(states.items())]
 doc={"mission":"MN-GEO-RAIL-001",
  "stage":"G24_source_grid_2km_to_original_DGT2m_station_site_planimetric_tangent_and_radius_context_NOT_engineered_alignment",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "immutable_source_SHA256":{"G10_original_27_corridor_geography":G10_SHA,"G23B_original_DGT2m_351_site_terrain_variants":G23B_SHA},
  "original_G10_2km_lattice_research_line_count":27,
  "original_G10_selected_three_research_families":list(FAMILIES),
  "original_G23B_local_DGT2m_source_study_variants":351,
  "original_G23B_mandatory_city_study_groups":13,
  "source_3km_halfwidth_IS_original_research_buffer_not_right_of_way":True,
  "illustrative_radius_speeds_m":{str(k):v for k,v in RADIUS_BY_SPEED.items()},
  "G10_grid_local_bearing_is_3km_6km_chord_not_railway_tangent":True,
  "R_times_angle_is_pure_circular_turn_arc_length_lower_bound_only":True,
  "does_not_model_transition_curves_cant_or_cant_deficiency":True,
  "does_not_model_actual_3D_curve_continuity_gradient_or_runoff":True,
  "does_not_confirm_grade_or_rail_station_curve_and_access":True,
  "no_geometry_innovation_claim_rail_alignment_constructible":True,
  "unmeasured_moved_location_city_to_station_road_time_is_NULL_not_imputed":True,
  "unmeasured_source_land_plot_geology_environment_tunnel_viaduct_and_CAPEX_EUR":True,
  "no_new_DGT_GLO30_OSM_GTFS_INE_downloads":True,
  "mandatory_markets":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "no_public_transport_access_assumed":True,
  "13_mandatory_market_by_family_source_geometry_summary":summary,
  "13_groups_2to3_source_ground_vs_grid_geometry_reference_shortlist":short,
  "351_original_source_geometry_station_tangent_screening_cases":measured,
  "Fxx_accepted":False,"Site_authorized":False}
 outpath.parent.mkdir(parents=True,exist_ok=True)
 outpath.write_text(json.dumps(doc,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 geopath.parent.mkdir(parents=True,exist_ok=True)
 geopath.write_text(json.dumps({"type":"FeatureCollection",
  "name":"G24 source research route grid plus station research points, NOT railway designs",
  "features":fgeo},ensure_ascii=False)+"\n")
 md=["# G24 — Enquadramento geométrico das estações exploratórias e dos corredores G10",
  "","**Não existem ainda traçados ferroviários projetados.** Foram cruzadas três linhas de centros de quadrículas originais de 2 km dos corredores G10 com as 351 variantes geométricas locais G23B suportadas por terreno DGT de 2 m.",
  "","Compara-se a distância ao eixo da **grelha de estudo**, o ângulo não orientado entre a faixa reta de estudo e a direção aproximada desse eixo em janelas de 3 e 6 km e a extensão **teórica mínima de arco de viragem** R×θ, sob raios ilustrativos G7 de 1 500/2 400/3 700 m. Esses arcos não constituem geometria ferroviária, nem ligações projetadas aos eixos.",
  "","## Indicadores de continuidade em planta dos 13 grupos por cidade e família",
  "| Cidade | Família | Pontos testados | Com terreno válido | Dentro da faixa de estudo 3 km | Terreno válido e dentro da faixa | Ponto mais próximo do eixo da grelha (m) |",
  "|---|---|---:|---:|---:|---:|---:|"]
 for x in summary:
  md.append(f"| {x['mandatory_market']} | {x['research_family']} | {x['n']} | {x['original_valid']} | {x['in_band']} | {x['within_band_and_native']} | {x['nearest_distance_m']:.0f} |")
 md+=["","## Referências propostas apenas para análise subsequente",
  "| Cidade | Família | Referência | Papel da triagem | Distância à grelha G10 (m) | Diferença de direção (graus, janela 3 km) | P90 estação DGT2m (m) |",
  "|---|---|---|---|---:|---:|---:|"]
 for x in short:
  md.append(f"| {x['mandatory_market']} | {x['source_research_family']} | {x['G23B_study_seed_id']} | {x['screening_role']} | {x['distance_to_original_G10_2km_grid_route_m']:.0f} | {x['hypothetical_station_straight_heading_mismatch_to_3km_source_grid_chord_deg']:.1f} | {x['G23B_station_vertical_p90_DGT2m_m'] if x['G23B_station_vertical_p90_DGT2m_m'] is not None else 'N/D'} |")
 md+=["","## Portões que permanecem abertos",
  "- **A proximidade ao eixo de grelha não garante uma conexão ferroviária.** A grelha G10 admite mudanças bruscas de direção que não são alinhamentos reais; o azimute de janela de 3/6 km é apenas uma referência territorial.",
  "- Mesmo cumprindo uma condição necessária de raio, faltam transições (clotoides), superelevação, dinâmica, perfil longitudinal, zonas de plataforma e eventual geometria elevada/subterrânea.",
  "- Para cada deslocamento G23B **não se transferem os tempos de acesso rodoviário** do ponto G20, porque os acessos legais ainda são desconhecidos.",
  "- Só após definir corredores de aproximação contínuos com restrições ambientais, atravessamentos, geotecnia e propriedades se deverão quantificar túneis, viadutos, movimentos de terra e custos.",
  "- As manchas atuais de solo nu MDT de 2 m são locais e não cobrem a extensão completa das aproximações nem todo o AFSC–Zamora.",
  "","Sem nova aquisição de dados, sem promoção canónica Fxx e sem atualização ao Site.",""]
 mdpath.parent.mkdir(parents=True,exist_ok=True);mdpath.write_text("\n".join(md))
 print("G24_GRID_STATION_GEOMETRIC_SCREEN="+json.dumps({
  "source_routes":len(routes),"local_study_variants":len(measured),"groups":len(groups),
  "shortlist_rows":len(short),
  "source_within_3km_band":sum(x["within_original_3km_halfwidth_research_band_NOT_rail_corridor"] for x in measured),
  "valid_original_native_ground_and_source_band":sum(x["G23B_original_DGT2m_platform_and_approach_coverage_ge_98pct"] and x["within_original_3km_halfwidth_research_band_NOT_rail_corridor"] for x in measured),
  "city_family_summaries":summary},ensure_ascii=False,separators=(",",":")))
 return doc

def main():
 p=argparse.ArgumentParser()
 for arg in ("g10","g23b","json","geojson","markdown"):p.add_argument("--"+arg,required=True,type=Path)
 a=p.parse_args();compute(a.g10,a.g23b,a.json,a.geojson,a.markdown)
if __name__=="__main__":main()
