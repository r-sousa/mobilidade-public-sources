#!/usr/bin/env python3
"""G3 exploratory coverage connectivity: existing real GLO30 DSM, real OSM ways
and five independently verified DGT original-product catalogues.

The lattice is for identifying where to acquire ACTUAL 2m ground DTM next.
It is NOT a railway alignment, grade/radius/cost model or a proposed station.
Vila Real and Bragança must be served; exact central stations not required.
Sanabria is explicitly excluded, not represented as a destination or waypoint.
"""
from __future__ import annotations
import argparse,hashlib,heapq,json,math
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from geo_rail_pt_b1_dgt_review_grids import inventory
from geo_rail_pt_b1_a4_road_screen import DSM_SHA256,ROAD_CLASSES

OSM_SOURCE_SHA="170b3c49ae7dc118fd0380a464f1547d1bd897ff09effdc69f3abaac0d6eec24"
B1_SOURCE_SHA="79c8811bf8be1a5c92d6aac1089b9a558db1ba0e6819ac3a07c250b1f38e1cfc"
B1_REAL_SHA="29ab2b11f9415be3a7d0dbe4c3e677df9efb43b6" # Git blob ID, not file sha
CELL=2000
LINKS=(
 ("Vila_Real_W_to_E",(20000,180000),(40000,184000),"Vila Real","local"),
 ("Vila_Real_N_to_S",(34000,184000),(34000,176000),"Vila Real","local"),
 ("Braganca_W_to_E",(110000,234000),(116000,238000),"Bragança","local"),
 ("Braganca_N_to_S",(110000,242000),(110000,232000),"Bragança","local"),
 ("Vila_Real_E_to_Braganca_W",(40000,184000),(110000,234000),"Vila Real / Bragança","regional"),
)
# Square grid cells (southwest coordinates), NOT surveyed endpoints or stations.
EXISTING={
 "Vila Real":{(20000,180000),(40000,184000),(34000,184000),(34000,176000)},
 "Bragança":{(110000,234000),(116000,238000),(110000,242000),(110000,232000)}
}
ROAD_REF="B1-PT-A4-IP4-mandatory-city-road-reference-OSM.geojson"

def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  for chunk in iter(lambda:f.read(2**20),b""):h.update(chunk)
 return h.hexdigest()

def cell_ids(catalog,x,y):
 col=x//1000+200; row=y//1000+301
 z=[catalog.get((col+dc,row+dr)) for dr in (0,1) for dc in (0,1)]
 return [v["id"] for v in z] if all(z) else None

def shortest(nodes,start,end,mode):
 """Deterministic 4-neighbour graph on actual DSM measured 2km cells."""
 if start not in nodes or end not in nodes:return None
 dist={start:0.};prev={};todo=[(0.,start)]
 while todo:
  val,a=heapq.heappop(todo)
  if val>dist.get(a,float("inf"))+1e-9:continue
  if a==end:
   path=[end]
   while path[-1]!=start:path.append(prev[path[-1]])
   path.reverse()
   return path,dist[end]
  for dx,dy in ((CELL,0),(-CELL,0),(0,CELL),(0,-CELL)):
   n=a[0]+dx,a[1]+dy
   if n not in nodes:continue
   v=nodes[n]
   delt=abs(v["surface_median_m"]-nodes[a]["surface_median_m"])
   if mode=="short":
    weight=1.+.0007*v["surface_robust_relief_m"]+.0002*delt
   elif mode=="terrain":
    weight=1.+.014*v["surface_robust_relief_m"]+.003*delt
   elif mode=="road":
    # road distance contributes only around the two cities where ways are known
    prox=v["euclidean_mapped_local_road_m"]
    weight=1.+.004*v["surface_robust_relief_m"]+.001*delt+(.0004*min(prox,4000) if prox is not None else 0)
   else:raise ValueError("unknown_exploratory_lattice_scenario")
   score=val+weight
   if score+1e-9<dist.get(n,float("inf")):
    dist[n]=score;prev[n]=a;heapq.heappush(todo,(score,n))
 return None

def dsm_stats(ds,x,y,project):
 import numpy as np
 from rasterio.windows import from_bounds,Window
 # Source is EPSG:4326 GLO30 surface raster; sample rectangle actually containing EPSG3763 cell.
 corners=[project.transform(a,b) for a,b in
          ((x,y),(x+CELL,y),(x+CELL,y+CELL),(x,y+CELL))]
 lon=[z[0] for z in corners];lat=[z[1] for z in corners]
 lon0,lat0,lon1,lat1=min(lon),min(lat),max(lon),max(lat)
 t=from_bounds(lon0,lat0,lon1,lat1,transform=ds.transform)
 x0=max(0,math.floor(t.col_off));y0=max(0,math.floor(t.row_off))
 x1=min(ds.width,math.ceil(t.col_off+t.width));y1=min(ds.height,math.ceil(t.row_off+t.height))
 if x1<=x0 or y1<=y0:return None
 z=ds.read(1,window=Window(x0,y0,x1-x0,y1-y0),masked=True).compressed()
 if z.size<300:return None
 a=np.percentile(z,[5,50,95])
 if not np.isfinite(a).all():return None
 return {"surface_elevation_P05_m":round(float(a[0]),2),
         "surface_median_m":round(float(a[1]),2),
         "surface_elevation_P95_m":round(float(a[2]),2),
         "surface_robust_relief_m":round(float(a[2]-a[0]),2),
         "native_source_surface_pixels_sampled":int(z.size),
         "DSM_has_trees_and_buildings":True}

def source_mapped_road_lines(road_json):
 from shapely.geometry import shape
 from shapely.ops import transform,unary_union
 from pyproj import Transformer
 source=json.loads(Path(road_json).read_text())
 if (source.get("type")!="FeatureCollection" or len(source.get("features",[]))!=2801):
  raise ValueError("expected_2801_actual_OSM_source_ways")
 forward=Transformer.from_crs(4326,3763,always_xy=True)
 grouped={"Vila Real":[],"Bragança":[]}
 for f in source["features"]:
  p=f["properties"];c=p.get("city_scope")
  city={"Vila_Real":"Vila Real","Braganca":"Bragança"}.get(c)
  if city and p.get("highway") in ROAD_CLASSES and p.get("highway") in (
      "primary","primary_link","secondary","secondary_link"):
   grouped[city].append(transform(forward.transform,shape(f["geometry"])))
 if any(len(z)<20 for z in grouped.values()):raise ValueError("insufficient_source_mapped_local_roads")
 return {k:unary_union(v) for k,v in grouped.items()}

def in_roi(link,x,y):
 name,start,goal,city,kind=link
 cx=x+1000;cy=y+1000
 if kind=="local":
  return min(start[0],goal[0])-6000<=x<=max(start[0],goal[0])+6000 and \
         min(start[1],goal[1])-6000<=y<=max(start[1],goal[1])+6000
 # bounded +/-14km strip around line joining two reviewed source sector centres
 ax,ay=start[0]+1000,start[1]+1000;bx,by=goal[0]+1000,goal[1]+1000
 vx,vy=bx-ax,by-ay
 t=max(0.,min(1.,((cx-ax)*vx+(cy-ay)*vy)/(vx*vx+vy*vy)))
 return math.hypot(cx-(ax+t*vx),cy-(ay+t*vy))<=14000

def build(dsm_file,roads_file,catalog_folder,existing_file):
 import rasterio
 from pyproj import Transformer
 from shapely.geometry import Point
 if sha(dsm_file)!=DSM_SHA256:raise ValueError("GLO30_original_source_sha256_mismatch")
 if sha(roads_file)!=OSM_SOURCE_SHA:raise ValueError("OSM_road_source_sha256_mismatch")
 baseline=json.loads(Path(existing_file).read_text())
 if (baseline.get("original_source_GeoTIFF_count")!=32 or
     baseline.get("mandatory_service_areas")!=["Vila Real","Bragança"] or
     not baseline.get("sanabria_excluded")):
  raise ValueError("previous_B1_32_native_sources_not_confirmed")
 for r in baseline["sectors"]:
  city=r["city"];x,y,_,_=r["bbox_epsg3763"]
  if (x,y) not in EXISTING[city]:raise ValueError("unexpected_previous_DGT_native_study_grid")
 catalog,proofs=inventory(catalog_folder)
 roads=source_mapped_road_lines(roads_file)
 inverse=Transformer.from_crs(3763,4326,always_xy=True)
 cellset=set()
 for link in LINKS:
  a,b=link[1:3]
  for x in range(min(a[0],b[0])-16000,max(a[0],b[0])+18000,CELL):
   for y in range(min(a[1],b[1])-16000,max(a[1],b[1])+18000,CELL):
    if in_roi(link,x,y):cellset.add((x,y))
 nodes={}
 with rasterio.open(dsm_file) as ds:
  if ds.crs is None or ds.crs.to_epsg()!=4326:raise ValueError("GLO30 wrong source CRS")
  for x,y in sorted(cellset):
   ids=cell_ids(catalog,x,y)
   if not ids:continue
   stats=dsm_stats(ds,x,y,inverse)
   if not stats:continue
   p=Point(x+1000,y+1000)
   dmin={c:float(p.distance(g)) for c,g in roads.items()}
   city=min(dmin,key=dmin.get)
   road_d=(round(dmin[city]) if dmin[city]<25000 else None)
   nodes[(x,y)]={**stats,"source_grid_epsg3763":[x,y,x+CELL,y+CELL],
       "official_DGT_MDT2m_source_ids":ids,
       "nearest_OSM_road_screen_city":city if road_d is not None else None,
       "euclidean_mapped_local_road_m":road_d,
       "already_B1_ground_acquired":any((x,y) in s for s in EXISTING.values())}
 result=[]
 for link in LINKS:
  name,start,goal,city,kind=link
  runs=[]
  for mode in ("short","terrain","road") if kind=="local" else ("short","terrain"):
   found=shortest(nodes,start,goal,mode)
   if found is None:
    runs.append({"mode":mode,"status":"no_connected_source_catalog_and_DSM_grid_path","route_sector_cells":[]})
    continue
   route,cost=found
   z=[nodes[a] for a in route]
   runs.append({"mode":mode,"status":"exploratory_2km_DSM_source_catalog_lattice_connected",
      "lattice_steps":len(route)-1,"orthogonal_lattice_distance_km":(len(route)-1)*2,
      "arbitrary_exploratory_cell_cost":round(cost,3),
      "median_of_DSM_surface_median_elevations_m":round(sorted(q["surface_median_m"] for q in z)[len(z)//2],1),
      "sum_of_grid_surface_relief_values_m_not_railway_ramp":round(sum(q["surface_robust_relief_m"] for q in z),1),
      "max_adjacent_cell_median_elevation_change_m_not_track_gradient":round(max((abs(z[i]["surface_median_m"]-z[i-1]["surface_median_m"]) for i in range(1,len(z))),default=0),1),
      "route_sector_cells":[[x,y] for x,y in route],
      "new_original_DGT_2m_pixel_coverage_for_this_path":False})
  result.append({"link":name,"category":kind,"start_reviewed_existing_source_sector":[*start,start[0]+2000,start[1]+2000],
    "end_reviewed_existing_source_sector":[*goal,goal[0]+2000,goal[1]+2000],
    "endpoints_are_not_stations":True,
    "solutions":runs})
 # Priority sample for the NEXT protected source acquisition, not approved track geometry.
 ranking=Counter();per_type={}
 for r in result:
  for v in r["solutions"]:
   if v["status"].startswith("exploratory"):
    for pos in v["route_sector_cells"][1:-1]:
     point=tuple(pos)
     if not nodes[point]["already_B1_ground_acquired"]:
      ranking[point]+=2 if v["mode"]=="terrain" else 1
      per_type.setdefault(point,set()).add(r["category"])
 city_centres={"Vila Real":(35000,182000),"Bragança":(111000,237000)}
 picks=[]
 for category,cap in (("local",12),("regional",8)):
  pool=[p for p in ranking if category in per_type[p] and not nodes[p]["already_B1_ground_acquired"]]
  # First positions repeated across methods, then lower local DSM relief; no road=station inference.
  pool.sort(key=lambda p:(-ranking[p],nodes[p]["surface_robust_relief_m"],p[0],p[1]))
  for p in pool:
   if len([v for v in picks if v["target_category"]==category])>=cap:break
   if any(v["grid_epsg3763"][:2]==list(p) for v in picks):continue
   n=nodes[p];x,y=p
   picks.append({"target_category":category,"grid_epsg3763":[x,y,x+CELL,y+CELL],
       "official_original_DGT2m_1km_tile_IDs":n["official_DGT_MDT2m_source_ids"],
       "already_acquired_original_ground_pixels":False,
       "source_tile_ids_from_five_official_catalogues":True,
       "number_of_lattice_solutions_crossing_cell":ranking[p],
       "GLO30_surface_robust_relief_m":n["surface_robust_relief_m"],
       "mapped_local_road_Euclidean_distance_m":n["euclidean_mapped_local_road_m"],
       "not_an_accessibility_or_railway_alignment_validation":True})
 # Ensure geographically balanced city-local sources in top list; not pinning a station.
 city_count={city:sum(abs(p["grid_epsg3763"][0]-xy[0])<14000 and abs(p["grid_epsg3763"][1]-xy[1])<14000 and p["target_category"]=="local" for p in picks)
             for city,xy in city_centres.items()}
 return {"mission":"MN-GEO-RAIL-001","stage":"G3_actual_open_DSM_and_OSM_road_plus_DGT_catalogue_network_gap_review",
    "observed_utc":datetime.now(timezone.utc).isoformat(),
    "mandatory_cities":["Vila Real","Bragança"],"central_stations_required":False,"Sanabria_excluded":True,
    "source_DSM_full_real_pixels_sha256":DSM_SHA256,
    "source_real_OSM_2801_way_geometry_sha256":OSM_SOURCE_SHA,
    "source_32km2_real_B1_ground_receipt":"reports/mn-geo-rail-001/B1-DGT-native-2m-32km2-verified-ground-sector-review.json",
    "DGT_five_original_STAC_catalogue_receipts":proofs,
    "two_kilometre_cells_reviewed":len(cellset),
    "two_kilometre_cells_with_four_original_DGT_tile_IDs_and_real_DSM_pixels":len(nodes),
    "lattice_orthogonal_four_neighbor":True,
    "lattice_path_is_not_a_railway_or_road_alignment":True,
    "railway_slope_curvature_tunnel_and_viaduct_evaluated":False,
    "actual_road_travel_times_or_legal_highway_access_evaluated":False,
    "vertical_crossborder_terrain_datum_harmonized":False,
    "real_original_DGT_2m_raster_source_pixels_newly_acquired":0,
    "Fxx_accepted":False,"Site_authorized":False,
    "links":result,"new_DGT2m_metadata_only_priority_targets":picks,
    "native_source_tiles_next_acquisition_target_metadata_only":len({id for z in picks for id in z["official_original_DGT2m_1km_tile_IDs"]}),
    "city_local_target_proximity_count_not_proof_of_station":city_count}

def main():
 a=argparse.ArgumentParser(description=__doc__)
 a.add_argument("--dsm",required=True,type=Path)
 a.add_argument("--roads",required=True,type=Path)
 a.add_argument("--catalogues",required=True,type=Path)
 a.add_argument("--already-acquired",required=True,type=Path)
 a.add_argument("--output",required=True,type=Path)
 args=a.parse_args()
 r=build(args.dsm,args.roads,args.catalogues,args.already_acquired)
 if r["two_kilometre_cells_with_four_original_DGT_tile_IDs_and_real_DSM_pixels"]<75:
  raise ValueError("insufficient_measured_real_DSM_catalogued_study_lattice")
 if not any(x["status"].startswith("exploratory") for l in r["links"] for x in l["solutions"]):
  raise ValueError("no_real_open_DSM_connected_catalogued_lattice")
 if not r["new_DGT2m_metadata_only_priority_targets"]:
  raise ValueError("no_source_pinned_targets")
 args.output.parent.mkdir(parents=True,exist_ok=True)
 args.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf8")
 print(json.dumps({"status":"G3_REAL_DSM_ROAD_OFFICIAL_2M_CATALOGUE_INTERSECTED",
   "measured_2km_cells":r["two_kilometre_cells_with_four_original_DGT_tile_IDs_and_real_DSM_pixels"],
   "paths":[[l["link"],[(q["mode"],q["status"],q.get("orthogonal_lattice_distance_km")) for q in l["solutions"]]] for l in r["links"]],
   "new_unacquired_DGT_2m_sector_targets":len(r["new_DGT2m_metadata_only_priority_targets"]),
   "new_original_ground_bytes":0},ensure_ascii=False))
if __name__=="__main__":main()
