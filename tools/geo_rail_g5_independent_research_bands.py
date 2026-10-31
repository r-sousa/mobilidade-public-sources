#!/usr/bin/env python3
"""MN-GEO-RAIL-001 G5 source-grounded *research bands*, NOT railway alignments.

New source-aware spatially distinct alternatives from the actual archived
Copernicus GLO-30 30m DSM, official DGT MDT2m metadata and QA footprints.
Algorithms may identify substantially different study bands but DO NOT compute
rail geometry, slope, curvature, tunnelling, viaducts, cost or road access.
"""
from __future__ import annotations
import argparse,hashlib,heapq,json,math,statistics
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import numpy as np
from pyproj import Transformer
import rasterio
from shapely.geometry import LineString, Point, mapping
from shapely.ops import transform as transform_geometry
from geo_rail_g3_continuity_open_dsm_sources import dsm_stats,cell_ids
from geo_rail_pt_b1_dgt_review_grids import inventory
from geo_rail_pt_b1_a4_road_screen import DSM_SHA256

CELL=2000
G4_SHA256="7d7a513fd248fcef86453da1967baf20d7359e9f66672fd7e5c4d2e7899ed200"
# The airport anchor is the NAV Portugal AIP LPPR reference, NOT an assumed station.
# Zamora coordinates and local VR/Bragança sectors are research references, NOT stations.
STUDY_LEGS=(
 ("P1_AFSC_to_Vila_Real_W",("wgs",-8.678056,41.235556),("pt",20000,180000),19000),
 ("P3_Vila_Real_E_to_Braganca_W",("pt",40000,184000),("pt",110000,234000),19000),
 ("P5_Braganca_E_to_Zamora",("pt",116000,238000),("wgs",-5.746992,41.50378),21000),
)
WEIGHT_MODES=("distance","relief","balanced")
OFFSETS=((CELL,0),(-CELL,0),(0,CELL),(0,-CELL),
         (CELL,CELL),(CELL,-CELL),(-CELL,CELL),(-CELL,-CELL))

def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()

def snap(x,y):
 return (int(math.floor(x/CELL))*CELL,int(math.floor(y/CELL))*CELL)

def centre(p):
 return (p[0]+CELL/2,p[1]+CELL/2)

def anchor(ref,transformer):
 if ref[0]=="pt":return snap(ref[1],ref[2])
 if ref[0]=="wgs":
  x,y=transformer.transform(ref[1],ref[2])
  return snap(x,y)
 raise ValueError("unreviewed_anchor_type")

def grid(dsm,link,source_catalog,project):
 _,start,end,buffer_m=link
 ax,ay=centre(start);bx,by=centre(end)
 line=LineString([(ax,ay),(bx,by)])
 left=min(ax,bx)-buffer_m-CELL;right=max(ax,bx)+buffer_m+CELL
 low=min(ay,by)-buffer_m-CELL;high=max(ay,by)+buffer_m+CELL
 nodes={}
 for x in range(int(math.floor(left/CELL))*CELL,int(math.ceil(right/CELL))*CELL+CELL,CELL):
  for y in range(int(math.floor(low/CELL))*CELL,int(math.ceil(high/CELL))*CELL+CELL,CELL):
   c=(x+1000,y+1000)
   if line.distance(Point(c))>buffer_m:continue
   stats=dsm_stats(dsm,x,y,project)
   if stats is None:continue
   ids=cell_ids(source_catalog,x,y)
   nodes[(x,y)]={"surface_median_m":stats["surface_median_m"],
                 "surface_relief_p95_minus_p05_m":stats["surface_robust_relief_m"],
                 "official_PT_DGT2m_four_source_ids_if_catalogued":ids,
                 "source_surface_pixels":stats["native_source_surface_pixels_sampled"]}
 if start not in nodes or end not in nodes:
  raise ValueError("real_DSM_missing_at_reviewed_anchor_"+link[0])
 return nodes

def cost(nodes,a,b,mode,repulse,avoid):
 dx=b[0]-a[0];dy=b[1]-a[1]
 if (dx,dy) not in OFFSETS:raise ValueError("nonadjacent_2km_screening_sector")
 km=math.hypot(dx,dy)/1000.
 s=nodes[a];t=nodes[b]
 relief=(s["surface_relief_p95_minus_p05_m"]+t["surface_relief_p95_minus_p05_m"])/2
 delta=abs(s["surface_median_m"]-t["surface_median_m"])
 if mode=="distance": w=km*(1+.035*min(relief/120,4))
 elif mode=="relief": w=km*(1+.35*min(relief/120,4))+.012*delta
 elif mode=="balanced":w=km*(1+.15*min(relief/120,4))+.005*delta
 else:raise ValueError("invalid_source_proxy_cost")
 # Penalize overlap in the middle of each previously selected alternative.
 # No negative weights and no forced imaginary rail points.
 if avoid and b in avoid:w+=repulse
 return w

def shortest(nodes,start,end,mode="balanced",avoid=frozenset(),repulse=0.0):
 if start not in nodes or end not in nodes:return None
 best={start:0.};prev={};pq=[(0.,start)]
 while pq:
  val,a=heapq.heappop(pq)
  if val>best.get(a,float("inf"))+1e-9:continue
  if a==end:
   out=[end]
   while out[-1]!=start:out.append(prev[out[-1]])
   out.reverse()
   return out
  for ox,oy in OFFSETS:
   b=(a[0]+ox,a[1]+oy)
   if b not in nodes:continue
   c=val+cost(nodes,a,b,mode,repulse,avoid)
   if c<best.get(b,float("inf"))-1e-9:
    best[b]=c;prev[b]=a
    heapq.heappush(pq,(c,b))
 return None

def length_km(route):
 return round(sum(math.dist(centre(route[i-1]),centre(route[i])) for i in range(1,len(route)))/1000,3)

def interior(route,start,end):
 ax,ay=centre(start);bx,by=centre(end)
 ux,uy=bx-ax,by-ay
 d=ux*ux+uy*uy
 return [p for p in route if .18<=((centre(p)[0]-ax)*ux+(centre(p)[1]-ay)*uy)/d<=.82]

def blockaround(selected, start, end, radius=1):
 existing=set()
 for s in selected:
  for p in interior(s,start,end):
   for i in range(-radius,radius+1):
    for j in range(-radius,radius+1):
     existing.add((p[0]+CELL*i,p[1]+CELL*j))
 return existing

def spatial_metrics(route,others,start,end):
 a=set(route);mid=interior(route,start,end)
 if not others:return {"max_jaccard":0.,"min_mid_cells_far_4km_fraction":1.0,
                         "mid_length_km":length_km(mid)}
 jac=[];far=[]
 for other in others:
  b=set(other)
  jac.append(len(a&b)/len(a|b))
  target=LineString([centre(p) for p in other])
  far.append(sum(target.distance(Point(centre(p)))>=4000 for p in mid)/len(mid) if mid else 0.)
 return {"max_jaccard":round(max(jac),4),
         "min_mid_cells_far_4km_fraction":round(min(far),4),
         "mid_length_km":length_km(mid)}

def alternatives(nodes,start,end):
 base=shortest(nodes,start,end,"distance")
 if not base:return [],"NO_CONNECTED_SOURCE_DSM_GRID"
 selected=[base];trace=[{"mode":"distance","repulsion_per_sector_km_equivalent":0.0,
                          "spatial_metrics":spatial_metrics(base,[],start,end)}]
 base_len=length_km(base)
 for attempts in range(24):
  if len(selected)>=3:break
  mode=("relief","balanced","distance")[attempts%3]
  step=(attempts//3)
  repulse=(2.+step*2.5)
  candidate=shortest(nodes,start,end,mode,blockaround(selected,start,end,radius=1),repulse)
  if candidate is None:continue
  diff=spatial_metrics(candidate,selected,start,end)
  if (diff["max_jaccard"]<=.68 and
      diff["min_mid_cells_far_4km_fraction"]>=.19 and
      length_km(candidate)<=1.48*base_len):
   selected.append(candidate)
   trace.append({"mode":mode,"repulsion_per_sector_km_equivalent":repulse,
                 "spatial_metrics":diff})
 return list(zip(selected,trace)),"THREE_DISTINCT_STUDY_PATHS" if len(selected)>=3 else "FEWER_THAN_THREE_SPATIALLY_DISTINCT_STUDY_PATHS"

def reference_2km_ground(g4,b1):
 g3=g4["G3_sector_details"]
 if len(g3)!=19:raise ValueError("G4_actual_DGT2m_source_area_no_19_groups")
 b1c=[tuple(s["bbox_epsg3763"][:2]) for s in b1["sectors"]]
 if len(set(b1c))!=8:raise ValueError("B1_original_32_tiles_not_eight_distinct_2km_sectors")
 good={tuple(z["grid_epsg3763"][:2]):z for z in g3}
 if len(good)!=19 or set(b1c)&set(good):
  raise ValueError("DGT2m_original_B1_G3_overlap")
 good.update({p:{"valid_cell_count":1_000_000,"source_NoData_cell_count":0} for p in b1c})
 # Mirandela 2x2km original block was reused from prior 13km2 without reacquisition.
 m=(80000,206000)
 if m in good:raise ValueError("repeated_Mirandela_sector")
 good[m]={"valid_cell_count":1_000_000,"source_NoData_cell_count":0}
 return good

def measure_route(route,nodes,native):
 samples=[nodes[p] for p in route]
 gradients=[abs(samples[i]["surface_median_m"]-samples[i-1]["surface_median_m"])
            for i in range(1,len(samples))]
 full=sum(p in native for p in route)
 area_valid=sum(native[p]["valid_cell_count"] for p in route if p in native)*4/1_000_000
 catalog=sum(bool(nodes[p]["official_PT_DGT2m_four_source_ids_if_catalogued"]) for p in route)
 return {"research_grid_cell_count":len(route),
   "orthogonal_or_diagonal_2km_lattice_length_km_NOT_track_length":length_km(route),
   "real_Copernicus_DSM_surface_median_elevation_range_m":
       [min(z["surface_median_m"] for z in samples),max(z["surface_median_m"] for z in samples)],
   "median_source_DSM_2km_cell_P95minusP05_m":round(statistics.median(z["surface_relief_p95_minus_p05_m"] for z in samples),2),
   "max_adjacent_source_DSM_2km_cell_median_difference_m_NOT_rail_gradient":round(max(gradients),2),
   "full_original_DGT_MDT2m_2km_grid_sectors_along_lattice_count":full,
   "full_original_DGT_MDT2m_sector_fraction":round(full/len(route),4),
   "valid_original_DGT_MDT2m_ground_area_inside_full_crossed_2km_cells_km2":round(area_valid,6),
   "official_DGT_source_metadata_four_tiles_catalogued_in_lattice_cells":catalog,
   "NO_claim_of_railway_gradient_or_tunnel_or_curve_radius":True}

def output(dsm_file,g4_file,b1_file,catalog_path,geojson_path,report_path):
 from shapely.geometry import shape
 if sha(dsm_file)!=DSM_SHA256:raise ValueError("real_Copernicus_source_SHA_changed")
 if sha(g4_file)!=G4_SHA256:raise ValueError("G4_121km2_original_DGT_receipt_SHA_changed")
 g4=json.loads(g4_file.read_text());b1=json.loads(b1_file.read_text())
 if (g4["DGT_2m_total_distinct_original_tile_footprint_km2"]!=121 or
     not g4["Sanabria_excluded"] or g4["G3_total_native_NoData_2m_pixels"]!=31451 or
     not g4["source_only_no_DGT_secrets"]):
  raise ValueError("native_source_evidence_failed")
 catalog,proofs=inventory(catalog_path)
 native=reference_2km_ground(g4,b1)
 # PT-TM06 used as a *screening* plane on both sides, never vertical height datum.
 forward=Transformer.from_crs(4326,3763,always_xy=True)
 backward=Transformer.from_crs(3763,4326,always_xy=True)
 legs=[]
 features=[]
 with rasterio.open(dsm_file) as ds:
  if ds.crs is None or ds.crs.to_epsg()!=4326:raise ValueError("not_source_DSM")
  proj=Transformer.from_crs(3763,4326,always_xy=True)
  for name,left,right,width in STUDY_LEGS:
   start,end=anchor(left,forward),anchor(right,forward)
   if start==end:raise ValueError("not_distinct_anchors")
   graph=grid(ds,(name,start,end,width),catalog,proj)
   choices,status=alternatives(graph,start,end)
   if not choices:raise ValueError("no_real_DSM_graph_link_at_"+name)
   paths=[]
   for idx,(route,method) in enumerate(choices):
    research_label=f"{name}_A{idx+1}"
    line=LineString([centre(c) for c in route])
    band=line.buffer(3000,cap_style=2,join_style=1)
    locstats=measure_route(route,graph,native)
    # No invented access nodes: endpoints are original research anchors,
    # not a legal site or station, and road network access remains UNKNOWN.
    data={"id":research_label,"leg":name,"variant":idx+1,"mode":method["mode"],
      "scope":"study_3km_halfwidth_screening_band_NOT_railway_right_of_way",
      **locstats,**method["spatial_metrics"],
      "screening_band_halfwidth_m":3000,
      "endpoint_study_cells_pttm06":[list(start),list(end)],
      "source_grid_positions_pttm06":[list(p) for p in route],
      "actual_road_driving_minutes_computed":False,
      "station_service_access_to_Vila_Real_and_Braganca_proven":False,
      "terrain_vertical_datum_harmonized_between_countries":False}
    paths.append(data)
    for ftype,geom in [("exploratory_2km_cell_center_screen",line),
                       ("exploratory_screening_band_3km",band)]:
     geom4326=transform_geometry(backward.transform,geom)
     features.append({"type":"Feature","geometry":mapping(geom4326),
       "properties":{"research_id":research_label,"layer":ftype,
         "screening_not_railway_alignment":True,"scope":name,
         "method":method["mode"],"source_DSM_SHA256":DSM_SHA256}})
   legs.append({"leg":name,"status":status,
     "actual_Copernicus_DSM_2km_candidate_cells_examined":len(graph),
     "study_start_sector_SW_pttm06":list(start),"study_end_sector_SW_pttm06":list(end),
     "research_strip_width_from_direct_reference_km_each_side":width/1000,
     "variants":paths})
 result={"mission":"MN-GEO-RAIL-001","stage":"G5_real_DSM_multi_leg_spatially_distinct_research_bands",
   "utc":datetime.now(timezone.utc).isoformat(),
   "actual_source_DSM_sha256":DSM_SHA256,"actual_source_G4_ground_receipt_sha256":G4_SHA256,
   "official_DGT_STAC_source_receipts":proofs,
   "mandatory_service_areas":["Vila Real","Bragança"],"station_centres_required":False,
   "Sanabria_excluded":True,"research_legs":[a["leg"] for a in legs],
   "geometric_line_is_centres_of_exploratory_2km_sector_not_rail_track":True,
   "research_band_halfwidth_m":3000,
   "research_alternatives_are_not_approved_rail_alignments":True,
   "no_authorized_rail_curvature_grade_tunnel_viaduct_cost_or_travel_time":True,
   "no_claim_of_real_city_road_network_access":True,
   "crossborder_vertical_datum_not_harmonized":True,
   "r1_glo30_DSM_has_buildings_and_vegetation":True,
   "existing_native_DGT_MDT2m_original_area_km2":121,
   "railway_link_completeness_through_city_service_areas_not_proven":True,
   "Fxx_accepted":False,"Site_authorized":False,"legs":legs}
 if len(legs)!=3:raise ValueError("did_not_model_three_study_legs")
 # Assert genuine spatial independence or admit inability, do not fabricate three.
 for leg in legs:
  for v in leg["variants"][1:]:
   if v["max_jaccard"]>.68 or v["min_mid_cells_far_4km_fraction"]<.19:
    raise ValueError("G5_variants_not_geospatially_distinct")
 geojson_path.parent.mkdir(parents=True,exist_ok=True)
 geojson_path.write_text(json.dumps({"type":"FeatureCollection",
          "name":"G5 research screens - NOT rail alignments",
          "features":features},ensure_ascii=False,indent=2)+"\n")
 report_path.parent.mkdir(parents=True,exist_ok=True)
 report_path.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 print("G5_REAL_SOURCE_RESEARCH="+json.dumps({"legs":[
    {"leg":l["leg"],"status":l["status"],"grid_cells":l["actual_Copernicus_DSM_2km_candidate_cells_examined"],
      "variants":[{"id":v["id"],"length_km":v["orthogonal_or_diagonal_2km_lattice_length_km_NOT_track_length"],
       "DGT2m_full_share":v["full_original_DGT_MDT2m_sector_fraction"],
       "max_jaccard":v["max_jaccard"],
       "mid_far4km":v["min_mid_cells_far_4km_fraction"]} for v in l["variants"]]} for l in legs]},ensure_ascii=False))
 return result

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--dsm",type=Path,required=True)
 ap.add_argument("--g4",type=Path,required=True)
 ap.add_argument("--b1",type=Path,required=True)
 ap.add_argument("--catalogues",type=Path,required=True)
 ap.add_argument("--geojson",type=Path,required=True)
 ap.add_argument("--report",type=Path,required=True)
 p=ap.parse_args()
 output(p.dsm,p.g4,p.b1,p.catalogues,p.geojson,p.report)
if __name__=="__main__":main()
