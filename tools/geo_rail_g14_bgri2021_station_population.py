#!/usr/bin/env python3
"""G14 original INE BGRI21_CONT demographic catchment RESEARCH.

Use exact published F67 original SHA-verified native 2021 BGRI geopackage;
integrate G13A 108 research interface references. Population counts use
centroid-within-circle and intersected-area-weighted sensitivity rather
than inventing station access by road or passenger demand. Accumulate
population once per 6-site corridor union, never sum overlapping circles.
No real stations, generalized travel time, current 2026 population, employment
or rail ridership is inferred.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sqlite3,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
from shapely.geometry import Point,mapping
from shapely.ops import unary_union
from shapely import wkb,make_valid
from shapely.prepared import prep
from pyproj import Transformer

F67_SHA="3eb49fb9e262e9d6ccb4b493811b7e21e2bbb31b0afe1431851ddd459ad7f171"
F67_BYTES=246754080
G13_SHA="063c1ddae2eb8020edc530bfef09fe8239208068b918a56d6054005ad31bfaee"
FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
CITIES=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
RADII_M=(5000.,10000.,20000.)
FIELDS=("N_INDIVIDUOS","N_INDIVIDUOS_0_14","N_INDIVIDUOS_15_24",
        "N_INDIVIDUOS_25_64","N_INDIVIDUOS_65_OU_MAIS")
GPKG_LAYER="BGRI21_CONT"
GPKG_MEMBER="BGRI21_CONT.gpkg"

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for part in iter(lambda:f.read(2**20),b""):h.update(part)
 return h.hexdigest()

def unpack_exact(path,temp):
 if path.stat().st_size!=F67_BYTES or sha(path)!=F67_SHA:
  raise ValueError("source_exact_BRGI2021_original_zip_sha_and_length_mismatch")
 if not zipfile.is_zipfile(path):raise ValueError("G14_original_not_zip")
 with zipfile.ZipFile(path) as z:
  matches=[m for m in z.infolist() if Path(m.filename).name==GPKG_MEMBER]
  if len(matches)!=1 or matches[0].file_size>7*1024**3:
   raise ValueError("original_required_single_GPKG_missing_or_oversize")
  target=temp/GPKG_MEMBER
  with z.open(matches[0]) as src,target.open("wb") as dst:
   while True:
    part=src.read(2**20)
    if not part:break
    dst.write(part)
 return target

def parse_gpkg_geometry(data):
 if not data or data[:2]!=b"GP":raise ValueError("invalid_original_geopackage_binary_geometry_magic")
 flags=data[3]
 # GPKG v1: (flags >> 1) & 7 specifies bounding-box envelope length.
 envelope={0:0,1:32,2:48,3:48,4:64}
 typ=(flags>>1)&7
 if typ not in envelope:raise ValueError("unsupported_gpkg_envelope_bitmask")
 offset=8+envelope[typ]
 geom=wkb.loads(data[offset:])
 if not geom.is_valid:geom=make_valid(geom)
 if not geom.is_valid or geom.is_empty:raise ValueError("invalid_original_BRGI_geometry")
 return geom

def native_qa(db):
 tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 rtree="rtree_"+GPKG_LAYER+"_geom"
 if rtree not in tables:
  raise ValueError("BGRI_original_has_no_GPKG_RTree; do not scan all mainland without spatial access")
 cols={x[1] for x in db.execute('PRAGMA table_info("BGRI21_CONT")')}
 if not {"fid","geom","BGRI2021","DTMN21","NUTS2",*FIELDS}.issubset(cols):
  raise ValueError("BGRI_geography_demography_schema_not_exact")
 srs=db.execute("SELECT srs_id FROM gpkg_contents WHERE table_name=?",(GPKG_LAYER,)).fetchone()
 if not srs or srs[0]!=3763:raise ValueError("GPKG_original_spatial_srs_should_3763")
 count=db.execute('SELECT count(*) FROM "BGRI21_CONT"').fetchone()[0]
 if count!=203264:raise ValueError("original_203264_subsections_drift")
 return {"record_count":count,"srs":srs[0],"rtree":rtree,"demographic_columns":list(FIELDS)}

def nonnegative_population(value):
 if isinstance(value,int) and value>=0:return float(value)
 if isinstance(value,float) and math.isfinite(value) and value>=0:return value
 # No imputation. Suppressed, null and unknown values stay missing.
 return None

def catchment(db,polygon,rtree):
 minx,miny,maxx,maxy=polygon.bounds
 q=f"""SELECT p.fid,p.geom,{','.join('p.'+x for x in FIELDS)}
 FROM "BGRI21_CONT" p
 JOIN "{rtree}" r ON r.id=p.fid
 WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?"""
 cursor=db.execute(q,(minx,maxx,miny,maxy))
 prepared=prep(polygon)
 n_bbox=n_intersect=n_invalid=n_census_unknown=0
 area_weighted={x:0. for x in FIELDS}
 centroid_inside={x:0. for x in FIELDS}
 for row in cursor:
  n_bbox+=1
  fid,raw,*stats=row
  try:shape=parse_gpkg_geometry(raw)
  except Exception:n_invalid+=1;continue
  if not prepared.intersects(shape):continue
  n_intersect+=1
  if shape.area<=0:continue
  frac=max(0.,min(1.,shape.intersection(polygon).area/shape.area))
  centre=polygon.covers(shape.representative_point())
  for key,value in zip(FIELDS,stats):
   x=nonnegative_population(value)
   if x is None:
    n_census_unknown+=1
    continue
   area_weighted[key]+=x*frac
   if centre:centroid_inside[key]+=x
 return {"original_subsections_in_spatial_bbox":n_bbox,
    "original_subsections_intersecting_area":n_intersect,
    "invalid_original_geometries_skipped":n_invalid,
    "missing_census_field_observations":n_census_unknown,
    "centroid_or_interior_point_population_counts":{x:round(v) for x,v in centroid_inside.items()},
    "area_weighted_uniform_within_subsection_population_estimates":{x:round(v) for x,v in area_weighted.items()},
    "statistical_method":"both point-in-polygon assignment and area fraction; area-weighted assumes uniform residents inside each small geographic subsection",
    "NOT_people_by_road_access_or_train_station_demand":True}

def choose_study_point(g13,route,city):
 row=next((z for z in g13["non_dominated_reference_site_screens_per_market"]
           if z["research_combination"]==route and z["urban_market"]==city),None)
 if row is None:raise ValueError("missing_G13_reference_market_"+route+"_"+city)
 pts=row["non_dominated_road_time_vs_DSM_terrain_reference_points"]
 if not pts:raise ValueError("no_qualifying_road_and_local_DSM_screen_"+route+"_"+city)
 # Transparent policy: favor public road access to a still hypothetical
 # station location, then surface relief. Choice is NOT station approval.
 s=sorted(pts,key=lambda p:(p["real_road_time_to_nearest_grid_road_snap_min"],
   p["L1_25permille_p90_vertical_surface_residual_m"],
   p["lateral_surface_p90_difference_125m_m"],abs(p["offset_km"])))
 return s[0]

def compute(rawzip,g13file,jpath,csvpath,mdpath):
 if sha(g13file)!=G13_SHA:raise ValueError("G13A_source_SHA_changed")
 g13=json.loads(g13file.read_text())
 if g13["site_counts"]["original_research_points"]!=108 or not g13["Sanabria_excluded"] or g13["Fxx_accepted"] or g13["Site_authorized"]:
  raise ValueError("G13A_research_reference_auth_contract_invalid")
 to_tm=Transformer.from_crs(4326,3763,always_xy=True)
 cases=[];coverage=[]
 with tempfile.TemporaryDirectory(prefix="bgri2021_cont_original_") as folder:
  native=unpack_exact(rawzip,Path(folder))
  db=sqlite3.connect(f"file:{native}?mode=ro",uri=True,timeout=45)
  try:
   qa=native_qa(db)
   family_seeds={}
   for corridor in FAMILIES:
    points=[]
    for city in CITIES:
     seed=choose_study_point(g13,corridor,city)
     lon,lat=seed["reference_lon_lat"]
     x,y=to_tm.transform(lon,lat)
     points.append(Point(x,y))
     for radius in RADII_M:
      polygon=Point(x,y).buffer(radius,quad_segs=24)
      result=catchment(db,polygon,qa["rtree"])
      cases.append({"research_corridor":corridor,"urban_market":city,
       "research_geographic_radius_km":int(radius/1000),
       "chosen_original_G13A_research_lonlat":[lon,lat],
       "chosen_reference_road_snap_minutes_not_station":seed["real_road_time_to_nearest_grid_road_snap_min"],
       "reference_local_surface_25permille_P90_m":seed["L1_25permille_p90_vertical_surface_residual_m"],
       "research_site_is_not_station":True,**result})
    family_seeds[corridor]=points
   # Union whole-corridor 10 and 20 km research service envelopes:
   # do not add overlapping station-level census counts.
   for corridor,points in family_seeds.items():
    for radius in (10000.,20000.):
     polygon=unary_union([p.buffer(radius,quad_segs=24) for p in points])
     result=catchment(db,polygon,qa["rtree"])
     coverage.append({"research_corridor":corridor,"union_geographic_radius_km":int(radius/1000),
       "six_reference_city_markets":list(CITIES),
       "overlap_between_station_reference_buffers_counted_once":True,
       "NOT_a_travel_time_catchment_or_distinct_ridership_market":True,**result})
  finally:db.close()
 if len(cases)!=54 or len(coverage)!=6:raise ValueError("BGRI_3_families_6_city_3_radii_not_complete")
 doc={"mission":"MN-GEO-RAIL-001","stage":"G14_actual_INE_BRGI2021_2021_demographic_geographic_service_envelopes",
   "observed_utc":datetime.now(timezone.utc).isoformat(),
   "sources":{"F67_public_exact_INE_cont_2021_sha256":F67_SHA,"G13A_108_study_sites_sha256":G13_SHA,
    "official_source":"Instituto Nacional de Estatística, Censos 2021 BGRI, BGRI21_CONT.gpkg",
    "canonical_Fxx_state_unchanged":True,"original_raster_or_geometry_not_edited":True},
   "source_schema_validation":qa,"research_corridors":list(FAMILIES),
   "mandatory_service_markets":["Vila Real","Bragança"],
   "other_considered_markets":["Guimarães","Amarante","Mirandela","Macedo de Cavaleiros"],
   "Sanabria_excluded":True,
   "this_is_2021_census_resident_population_not_current_2026_estimate":True,
   "geographic_buffers_are_not_road_public_transport_isochrones":True,
   "road_snap_research_locations_are_not_approved_station_sites":True,
   "no_actual_daily_rail_demand_or_modal_choice":True,
   "no_new_original_INE_download_this_run":True,
   "no_actual_employment_journey_OD_or_cost_EUR":True,
   "all_54_city_research_geographic_buffer_census_cases":cases,
   "six_family_population_nonoverlapping_buffer_union_cases":coverage,
   "Fxx_accepted":False,"Site_authorized":False}
 jpath.parent.mkdir(parents=True,exist_ok=True)
 jpath.write_text(json.dumps(doc,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 csvpath.parent.mkdir(parents=True,exist_ok=True)
 with csvpath.open("w",encoding="utf-8",newline="") as f:
  fieldnames=["research_corridor","urban_market","research_geographic_radius_km",
    "N_INDIVIDUOS_centroid","N_INDIVIDUOS_area_fraction",
    "N_INDIVIDUOS_65_OU_MAIS_centroid","subsections_intersecting"]
  w=csv.DictWriter(f,fieldnames=fieldnames)
  w.writeheader()
  for row in cases:
   w.writerow({"research_corridor":row["research_corridor"],"urban_market":row["urban_market"],
    "research_geographic_radius_km":row["research_geographic_radius_km"],
    "N_INDIVIDUOS_centroid":row["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
    "N_INDIVIDUOS_area_fraction":row["area_weighted_uniform_within_subsection_population_estimates"]["N_INDIVIDUOS"],
    "N_INDIVIDUOS_65_OU_MAIS_centroid":row["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS_65_OU_MAIS"],
    "subsections_intersecting":row["original_subsections_intersecting_area"]})
 md=["# G14 — Cobertura demográfica de 2021 dos pontos exploratórios de interface",
  "","Fonte original INE: BGRI 2021 (subsecções, Continente), release pública F67, 203264 registos, EPSG:3763, SHA256 inalterado. A população é de **2021**, não uma projeção para 2026.",
  "A avaliação utiliza áreas circulares de 5, 10 e 20 km em torno dos pontos G13A com menor tempo de acesso rodoviário a vias próximas; os pontos não constituem estações de caminho de ferro. Distância euclidiana não é tempo de acesso.",
  "","## População residente em áreas de 10 km por cidade (contagem do ponto interior da subsecção)",
  "| Família | Guimarães | Amarante | Vila Real* | Mirandela | Macedo de Cavaleiros | Bragança* |",
  "|---|---:|---:|---:|---:|---:|---:|"]
 for corridor in FAMILIES:
  vals=[]
  for city in CITIES:
   z=next(x for x in cases if x["research_corridor"]==corridor and x["urban_market"]==city and x["research_geographic_radius_km"]==10)
   vals.append(str(z["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"]))
  md.append(f"| {corridor} | "+" | ".join(vals)+" |")
 md+=["","## População nas uniões de seis áreas de serviço (evita dupla contagem)",
  "| Família | Raio de 10 km | Raio de 20 km |",
  "|---|---:|---:|"]
 for corridor in FAMILIES:
  entries={x["union_geographic_radius_km"]:x for x in coverage if x["research_corridor"]==corridor}
  md.append(f"| {corridor} | {entries[10]['centroid_or_interior_point_population_counts']['N_INDIVIDUOS']} | {entries[20]['centroid_or_interior_point_population_counts']['N_INDIVIDUOS']} |")
 md+=["","## Limitações essenciais",
  "- As contagens por ponto usam o ponto representativo de cada subsecção; foi também calculada a sensibilidade ponderada pela área da interseção, assumindo distribuição uniforme no interior da subsecção. Nenhuma metodologia converte estas áreas em população que efetivamente chega à estação em 15/30 minutos.",
  "- Populações das áreas de várias estações sobrepõem-se e não podem ser somadas: utilizar as uniões por corredor. Cada referência urbana e posição de estudo continua sujeita a viabilidade física e acesso legal.",
  "- A origem BGRI 2021 contabiliza residentes, não empregos nos locais de destino, deslocações pendulares efetivamente ferroviárias, procura, rendimentos, custos ou preferências modais.",
  "- É necessário calcular isócronas reais (automóvel, transporte público, caminhada), procura OD, traçado ferroviário e custos antes de escolher corredor por serviço monetizado.",
  "","Nenhum Fxx foi automaticamente promovido a publicação canónica e nenhum Site foi atualizado.",""]
 mdpath.parent.mkdir(parents=True,exist_ok=True)
 mdpath.write_text("\n".join(md))
 print("G14_BRGI_POPULATION="+json.dumps({"count":len(cases),"unions":coverage,
  "sample_10km":[{"option":x["research_corridor"],"city":x["urban_market"],
    "population":x["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"]} for x in cases if x["research_geographic_radius_km"]==10]},separators=(',',':'),ensure_ascii=False))
 return doc

def main():
 a=argparse.ArgumentParser()
 for key in ("zip","g13a","json","csv","markdown"):a.add_argument("--"+key,required=True,type=Path)
 q=a.parse_args()
 compute(q.zip,q.g13a,q.json,q.csv,q.markdown)
if __name__=="__main__":main()
