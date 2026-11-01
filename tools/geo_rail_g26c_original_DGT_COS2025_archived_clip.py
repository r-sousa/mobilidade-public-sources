#!/usr/bin/env python3
"""G26C one-off official DGT original COS2025 national GeoPackage ZIP -> seven
400m study-circle CLIPPED ORIGINAL polygon land-use, public small release.
The national 876,190,334-byte archive exists only in transient GitHub runner,
never committed or retained. Spatial GPKG indexed bounding box queries.
No legal parcel, railway engineering, RAN/REN/PDM or station conclusion.
"""
from __future__ import annotations
import argparse,hashlib,json,zipfile,math
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
import geopandas as gpd
import pyogrio
from pyproj import Transformer
from shapely.geometry import Point,mapping
from shapely.ops import transform as sh_transform
from geo_rail_g26a_cos2025_original_local_landuse import site_points,SOURCE_SHA,RADIUS

DGT_SOURCE="https://geo2.dgterritorio.gov.pt/cos/S2/COS2025/COS2025v1-S2-gpkg.zip"
NATIONAL_ZIP_EXPECTED_BYTES=876190334
MAX_UNPACK_GPKG_BYTES=9_000_000_000
REQUIRED=("cos25v1_n1_c","cos25v1_n1_l","cos25v1_n4_c","cos25v1_n4_l")

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(2**20),b""):h.update(b)
 return h.hexdigest()

def unpack(archive,folder):
 if archive.stat().st_size!=NATIONAL_ZIP_EXPECTED_BYTES:raise ValueError("original_DGT_COS2025_national_zip_byte_count_changed")
 with zipfile.ZipFile(archive) as z:
  bad=z.testzip()
  if bad:raise ValueError("source_original_DGT_COS2025_zip_CRC_invalid")
  gpkg=[x for x in z.infolist() if x.filename.lower().endswith(".gpkg") and not x.is_dir()]
  if len(gpkg)!=1 or gpkg[0].file_size>MAX_UNPACK_GPKG_BYTES or gpkg[0].file_size<100000000:
   raise ValueError("exact_one_bounded_original_DGT_COS2025_GPKG_expected")
  filename=Path(gpkg[0].filename).name
  dest=folder/filename
  with z.open(gpkg[0]) as f,dest.open("wb") as out:
   import shutil
   shutil.copyfileobj(f,out,length=1048576)
  if dest.stat().st_size!=gpkg[0].file_size:raise ValueError("DGT_original_GPKG_uncompressed_bytes_incorrect")
 return dest,{"original_zip_SHA256":sha(archive),"original_zip_bytes":archive.stat().st_size,
   "source_archive_contains_one_GPKG":True,"original_uncompressed_GPKG_bytes":dest.stat().st_size,
   "original_GPKG_SHA256":sha(dest),"original_GPKG_basename":filename}

def get_layer(gpkg):
 layers=pyogrio.list_layers(gpkg)
 choices=[str(z[0]) for z in layers if "polygon" in str(z[1]).lower() or "multi" in str(z[1]).lower()]
 if len(choices)!=1:raise ValueError("COS2025_original_GPKG_one_polygon_layer_not_identified_"+str(layers))
 layer=choices[0]
 info=pyogrio.read_info(gpkg,layer=layer)
 crs=str(info.get("crs"))
 if not ("3763" in crs):raise ValueError("original_COS2025_GPKG_expected_PT_TM06_EPSG3763_"+crs)
 return layer,{"original_geopackage_layer":layer,"source_feature_count":int(info.get("features") or 0),
   "source_layer_CRS":crs,"source_fields":list(info.get("fields",[]))}

def clip(gpkg,layer,site,to_wgs):
 point=Point(*site["xy"])
 area=point.buffer(RADIUS,quad_segs=32)
 features=[]
 bbox=area.bounds
 original=pyogrio.read_dataframe(gpkg,layer=layer,bbox=bbox)
 if len(original)==0 or len(original)>3000:raise ValueError("DGT_COS2025_GPKG_spatial_index_result_missing_or_excessive")
 cols={x.lower():x for x in original.columns}
 if not all(k.lower() in cols for k in REQUIRED):
  raise ValueError("COS2025_original_GPKG_class_fields_not_identified_"+str(list(cols)))
 records={}
 for _,row in original.iterrows():
  g=row.geometry
  if g is None or g.is_empty or not g.is_valid:raise ValueError("invalid_COS_source_GPKG_polygon_geometry")
  inter=g.intersection(area)
  if inter.is_empty or inter.area<=0:continue
  data={k:str(row[cols[k]]) for k in REQUIRED}
  nativehash=hashlib.sha256(g.wkb).hexdigest()
  uid=str(row.get("objectid",row.get("fid",nativehash)))
  if uid in records:continue
  records[uid]={"type":"Feature","geometry":mapping(sh_transform(to_wgs.transform,inter)),
    "properties":{"source_DGT_COS2025_original_polygon_id_or_WKB_SHA":uid,
      "source_DGT_COS2025_n1_code":data["cos25v1_n1_c"],
      "source_DGT_COS2025_n1_label":data["cos25v1_n1_l"],
      "source_DGT_COS2025_n4_code":data["cos25v1_n4_c"],
      "source_DGT_COS2025_n4_label":data["cos25v1_n4_l"],
      "original_COS2025_polygon_clipped_area_ha":round(inter.area/10000,6),
      "source_research_city":site["city"],"source_research_EPSG3763_xy":list(site["xy"]),
      "not_station_property_or_buildable_land":True}}
 if not records:raise ValueError("G26C_no_original_source_polygons_intersect_400m_study")
 byclass=defaultdict(float)
 for z in records.values():
  p=z["properties"]
  byclass[(p["source_DGT_COS2025_n1_code"],p["source_DGT_COS2025_n1_label"])]+=p["original_COS2025_polygon_clipped_area_ha"]
 coverage=sum(byclass.values())/(area.area/10000)
 if not(.92<=coverage<=1.08):raise ValueError("G26C_polygon_coverage_incomplete_or_overlap_"+str(coverage))
 data={"mandatory_market":site["city"],"research_EPSG3763_XY":list(site["xy"]),
  "original_2025_COS_study_circle_area_ha":round(area.area/10000,4),
  "producer_COS_polygon_count":len(records),
  "COS2025_original_covered_fraction":round(coverage,4),
  "original_COS2025_2025_n1_land_use_ha":[{"code":k[0],"description":k[1],"area_ha":round(v,4),
    "share_pct":round(v/(area.area/10000)*100,2)} for k,v in sorted(byclass.items())],
  "G25_original_source_research_seed_labels":sorted(site["seeds"]),
  "source_G25_corridor_families":sorted(site["families"]),
  "COS2025_NOT_PDM_RAN_REN_SRUP_cadastre_or_station_feasibility":True}
 return data,list(records.values())

def run(archive,g25,extract,jsonout,geoout,markdown):
 if sha(g25)!=SOURCE_SHA:raise ValueError("original_G25_road_study_SHA_mismatch")
 sites=site_points(json.loads(g25.read_text()))
 extract.mkdir(parents=True,exist_ok=True)
 gpkg,proof=unpack(archive,extract)
 layer,layerinfo=get_layer(gpkg)
 back=Transformer.from_crs(3763,4326,always_xy=True)
 cases=[];vectors=[]
 for s in sites:
  data,poly=clip(gpkg,layer,s,back)
  cases.append(data);vectors.extend(poly)
 result={"mission":"MN-GEO-RAIL-001",
  "stage":"G26C_true_original_DGT_COS2025_S2_seven_mandatory_city_study_circles_clip_of_official_full_country_2025_GPKG",
  "utc":datetime.now(timezone.utc).isoformat(),
  "COS2025_official_DGT_archived_source_url":DGT_SOURCE,
  "COS2025_source_archive_verified_hash_and_bytes":proof,
  "COS2025_original_geopackage_layer_schema":layerinfo,
  "original_G25_SHA256":SOURCE_SHA,
  "DGT_data_attribution":"Direção-Geral do Território; CC BY 4.0",
  "COS_map_reference_2025_not_current_ground_inspection":True,
  "research_circle_radius_m":RADIUS,
  "seven_distinct_source_study_sites":len(cases),
  "true_original_2025_COS_clipped_polygon_features":len(vectors),
  "original_COS2025_local_7_site_summary":cases,
  "original_zip_bytes_egress_or_public_repository_asset":False,
  "no_station_legal_access_RAN_REN_PDM_SRUP_cadastre_verified":True,
  "no_new_DGT2m_terrain_raster_acquisition":True,
  "Sanabria_excluded":True,"Fxx_accepted":False,"Site_authorized":False}
 jsonout.parent.mkdir(parents=True,exist_ok=True)
 jsonout.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 geoout.parent.mkdir(parents=True,exist_ok=True)
 geoout.write_text(json.dumps({"type":"FeatureCollection",
   "name":"DGT COS2025 original 400m research circles clipped from one-off official national GPKG, not stations",
   "features":vectors},ensure_ascii=False)+"\n")
 md=["# G26C — COS2025 DGT (dados originais): sete áreas de investigação",
  "","Fonte primária oficial: COS2025v1-S2 GPKG, série 2, DGT, CC BY 4.0. Copiada temporariamente no trabalhador GitHub; só os sete recortes serão preservados. Âmbito de 400m de raio por setor, não uma localização de plataforma.",
  "","| Cidade | Referência PT-TM06 | Polígonos oficiais | % da área | Classes de uso do solo COS2025 (ha) |",
  "|---|---|---:|---:|---|"]
 for z in cases:
  desc="; ".join(f"{t['description']} {t['area_ha']}" for t in z["original_COS2025_2025_n1_land_use_ha"])
  md.append(f"| {z['mandatory_market']} | {z['research_EPSG3763_XY']} | {z['producer_COS_polygon_count']} | {z['COS2025_original_covered_fraction']*100:.1f}% | {desc} |")
 md+=["","**Advertência:** solo artificializado, agrícola ou florestal não corresponde a um juízo de elegibilidade do terreno. PDM, REN/RAN, domínio público hídrico, servidões, geologia, expropriação e acessos legais exigem camadas primárias independentes.",
  "","Dados resultantes de polígonos COS2025 originais, sem importar o país completo para o repositório. Sem Fxx e Site.",""]
 markdown.parent.mkdir(parents=True,exist_ok=True);markdown.write_text("\n".join(md))
 print("G26C_ORIGINAL_COS2025="+json.dumps({"sites":len(cases),"clip_polygons":len(vectors),
   "national_official_source_bytes_verified":proof["original_zip_bytes"],
   "original_source_SHA256":proof["original_zip_SHA256"],
   "by_city":[{"city":z["mandatory_market"],"n":z["producer_COS_polygon_count"],"coverage":z["COS2025_original_covered_fraction"],
     "classes":[{"name":v["description"],"ha":v["area_ha"]} for v in z["original_COS2025_2025_n1_land_use_ha"]]} for z in cases]},ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for k in ("zip","g25","extract","json","geojson","markdown"):p.add_argument("--"+k,required=True,type=Path)
 a=p.parse_args();run(a.zip,a.g25,a.extract,a.json,a.geojson,a.markdown)
