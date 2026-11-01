#!/usr/bin/env python3
"""G27C bounded ORIGINAL DGT SNIT GeoMedia WFS geometry intersections of 7
COS2025 site RESEARCH circles, not legal approvals, rankings or property rights.

WFS GetFeature per source × study circle; record full raw response SHA; parse
GML via GDAL/pyogrio strictly if source CRS EPSG3763 and source full response
not truncated. Any errors or maxFeatures cap => incomplete UNKNOWN.
REN original source can contain 'Exclusões': geometry intersection is NOT
automatically statutory REN restriction; compare final DR legal raster.
"""
from __future__ import annotations
import argparse,hashlib,json,time,urllib.request,urllib.error,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
from shapely.geometry import Point,mapping
from shapely.ops import unary_union,transform as geom_transform
from pyproj import Transformer
import pyogrio
from geo_rail_g27a_DGT_SNIT_territorial_constraints_probe import SERVICES,G26C_SHA
COLLECTIONS={"REN_NORTE":"gmgml:REN_Norte","RAN_PT":"gmgml:RAN","CRUS_NATIONAL":"gmgml:CRUS"}
RADIUS=400
MAXFEATURES=5
MAXSOURCEBYTES=10_000_000
SLEEP=.5
MAX_CLIPPED_OUTPUT_FEATURES=500

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def query(layer,cityxy,topic,work):
 url=SERVICES[topic]
 x,y=cityxy
 bbox=",".join(str(z) for z in (x-RADIUS,y-RADIUS,x+RADIUS,y+RADIUS))+",EPSG:3763"
 args={"SERVICE":"WFS","VERSION":"1.1.0","REQUEST":"GetFeature",
       "TYPENAME":layer,"BBOX":bbox,"MAXFEATURES":MAXFEATURES}
 u=url+"?"+urllib.parse.urlencode(args)
 req=urllib.request.Request(u,headers={"User-Agent":"MobilidadeNorte-G27-official-SNIT-real-geometry-study/1.0","Accept":"text/xml,application/gml+xml,*/*"})
 result={"topic":topic,"source_original_WFS_url_without_transient_credentials":url,
    "source_original_typename":layer,"requested_bbox_EPSG3763_m":[x-RADIUS,y-RADIUS,x+RADIUS,y+RADIUS],
    "bounded_MAXFEATURES":MAXFEATURES,"legal_absence_cannot_be_inferred_from_this_query":True}
 try:
  with urllib.request.urlopen(req,timeout=45) as resp:
   if urllib.parse.urlparse(resp.url).hostname!="servicos.dgterritorio.pt":raise ValueError("untrusted_DGT_redirect")
   raw=resp.read(MAXSOURCEBYTES+1)
   result["HTTP_status"]=resp.status
 except urllib.error.HTTPError as err:
  result["HTTP_status"]=err.code
  result["source_coverage_status"]="UNAVAILABLE_UNKNOWN";return result,[]
 except Exception as err:
  result["source_coverage_status"]="UNAVAILABLE_UNKNOWN"
  result["source_error_class"]=type(err).__name__;return result,[]
 if len(raw)>MAXSOURCEBYTES:
  result["source_coverage_status"]="TRUNCATED_UNKNOWN"
  result["raw_response_over_10MB_not_preserved"]=True;return result,[]
 result["original_raw_GML_SHA256"]=hashlib.sha256(raw).hexdigest()
 result["original_response_byte_size"]=len(raw)
 try:root=ET.fromstring(raw)
 except ET.ParseError:
  result["source_coverage_status"]="INVALID_XML_UNKNOWN";return result,[]
 if "Exception" in root.tag:
  result["source_coverage_status"]="SOURCE_EXCEPTION_UNKNOWN";return result,[]
 features=int(root.attrib.get("numberOfFeatures",root.attrib.get("numberMatched","-1")))
 result["WFS_reported_numberOfFeatures"]=features
 if features<0:
  result["source_coverage_status"]="REPORTED_FEATURE_COUNT_UNKNOWN"
  return result,[]
 if features==0:
  result["source_coverage_status"]="WFS_NO_FEATURES_IN_THIS_BBOX_UNVERIFIED_LEGAL_ABSENCE"
  result["no_original_polygons_in_source_WFS_bbox"]=True
  return result,[]
 if features>=MAXFEATURES:
  result["response_may_be_cut_at_maxFeatures_limit"]=True
  # Geometry evidence positive could still be observed but completeness unknown.
 temporary=work/(topic+".gml")
 temporary.write_bytes(raw)
 try:
  g=pyogrio.read_dataframe(temporary)
  if g.empty:raise ValueError("source_count_positive_but_geometry_empty")
  if g.crs is None or g.crs.to_epsg()!=3763:
   raise ValueError("source_real_GML_CRS_not_3763")
  if len(g)>MAXFEATURES:raise ValueError("source_GML_over_maxFeatures")
  circle=Point(x,y).buffer(RADIUS,quad_segs=32)
  convert=Transformer.from_crs(3763,4326,always_xy=True)
  rec=[];seen=set();geoms=[]
  for n,item in g.iterrows():
   geometry=item.geometry
   if geometry is None or geometry.is_empty:continue
   if not geometry.is_valid:
    result["invalid_source_GEOMETRY_cannot_assess_legally"]=True
    continue
   crop=geometry.intersection(circle)
   if crop.is_empty or crop.area<.01:continue
   original_hash=hashlib.sha256(geometry.wkb).hexdigest()
   if original_hash in seen:continue
   seen.add(original_hash);geoms.append(crop)
   attributes={str(k):str(v)[:150] for k,v in item.items() if k!="geometry" and v is not None}
   rec.append({"type":"Feature","geometry":mapping(geom_transform(convert.transform,crop)),
     "properties":{"topic":topic,"source_site_xy_EPSG3763_m":[x,y],
       "source_original_gml_geometry_SHA256":original_hash,
       "original_producer_layer_attribute_sample":attributes,
       "observed_clipped_geometry_ha":round(crop.area/10000,6),
       "REN_exclusoes_or_class_must_be_independently_distinguished":topic=="REN_NORTE",
       "intersection_does_NOT_prove_legal_prohibition_or_permit":True}})
  result["source_geometric_positive_intersection_count"]=len(rec)
  result["observed_source_geometry_union_ha_NOT_legal_restriction_area"]=round(unary_union(geoms).area/10000,6) if geoms else 0
  result["original_GML_parsed_features"]=len(g)
  result["source_original_GML_column_names"]=list(g.columns)
  result["source_coverage_status"]="SOURCE_INTERSECTIONS_OBSERVED_BUT_INCOMPLETE" if features>=MAXFEATURES else "BOUNDED_GML_GEOMETRY_OBSERVED_PRELEGAL"
  return result,rec
 except Exception as err:
  result["source_coverage_status"]="SOURCE_GML_NOT_PARSEABLE_UNKNOWN"
  result["source_parser_error_type"]=type(err).__name__
  result["source_GML_first_160_bytes"] = raw[:160].decode("utf8","replace")
  return result,[]

def run(g26c,outjson,geojson,mdout,work):
 if sha(g26c)!=G26C_SHA:raise ValueError("G27C_source_G26C_SHA_mismatch")
 data=json.loads(g26c.read_text())
 if len(data["original_COS2025_local_7_site_summary"])!=7:raise ValueError("G27C_not_seven_source_sites")
 work.mkdir(parents=True,exist_ok=True)
 matrices=[];geo=[]
 for site in data["original_COS2025_local_7_site_summary"]:
  xy=site["research_EPSG3763_XY"]
  rec={"city":site["mandatory_market"],"source_xy_EPSG3763":xy,"legal_RAN_REN_CRUS_status":"NOT_ASSESSED_LEGAL_MAP_AND_PDM",
    "municipal_DR_REN_map_required":True,"SRUP_PDM_legal_plan_required":True,"source_service_queries":{}}
  for j,(topic,layer) in enumerate(COLLECTIONS.items()):
   if j:time.sleep(SLEEP)
   folder=work/(site["mandatory_market"]+"_"+str(xy[0])+"_"+str(xy[1]))
   folder.mkdir(parents=True,exist_ok=True)
   ret,clipped=query(layer,xy,topic,folder)
   rec["source_service_queries"][topic]=ret
   if len(geo)+len(clipped)>MAX_CLIPPED_OUTPUT_FEATURES:raise ValueError("G27C_source_output_large")
   geo.extend(clipped)
  matrices.append(rec)
 report={"mission":"MN-GEO-RAIL-001","stage":"G27C_original_DGT_SNIT_7_sites_REN_RAN_CRUS_source_GML_bounded_intersection_PRELEGAL",
  "utc":datetime.now(timezone.utc).isoformat(),
  "G26C_original_COS2025_source_sha256":G26C_SHA,
  "official_producer":"DGT - SNIT OGC WFS; real source GML raw SHA, no national dataset downloaded",
  "source_research_sites":7,"source_service_bounded_request_count":21,
  "primary_original_source_clipped_vector_geometry_count":len(geo),
  "seven_research_site_by_service_source_status":matrices,
  "all_PDM_REN_official_DR_legal_map_validation_pending":True,
  "RAN_WFS_zero_feature_does_not_mean_legal_RAN_absent":True,
  "REN_source_Exclusoes_must_not_be_counted_as_legal_REN":True,
  "CRUS_is_statistics_and_not_legal_PDM_buildability":True,
  "no_station_eliminated_or_approved":True,
  "no_original_2m_DGT_dem_acquisition":True,
  "mandatory_cities":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "Fxx_accepted":False,"Site_authorized":False}
 outjson.parent.mkdir(parents=True,exist_ok=True);outjson.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 geojson.parent.mkdir(parents=True,exist_ok=True);geojson.write_text(json.dumps({"type":"FeatureCollection","name":"G27C DGT SNIT bounded REN RAN CRUS observed source polygons only - NO LEGAL VERDICT","features":geo},ensure_ascii=False)+"\n")
 md=["# G27C — Cruzamento exploratório de fontes SNIT DGT nos sete setores de estudo",
  "","As interseções provêm de consultas limitadas WFS 1.1.0. A ausência de resultados, erros ou truncagens não comprovam ausência de RAN/REN, nem autorizam intervenção. As exclusões da REN não são automaticamente área interdita. A cartografia legal e PDM/DR prevalecem.",
  "","| Município | Referência PT-TM06 | REN (fonte) | RAN (fonte) | CRUS (fonte) |",
  "|---|---|---|---|---|"]
 for e in matrices:
  w=[e["source_service_queries"][t]["source_coverage_status"] for t in COLLECTIONS]
  md.append(f"| {e['city']} | {e['source_xy_EPSG3763']} | {w[0]} | {w[1]} | {w[2]} |")
 md+=["","Passos jurídicos por realizar: cartas REN publicadas em DR e alterações, RAN e PDM/plantas de condicionantes, outros SRUP, Rede Natura, domínio hídrico, proprietários e acessos. Não foram declaradas estações aptas.",""]
 mdout.parent.mkdir(parents=True,exist_ok=True);mdout.write_text("\n".join(md))
 summary={"cases":len(matrices),"observed_source_polygons":len(geo),
   "status":{t:{s:sum(r["source_service_queries"][t]["source_coverage_status"]==s for r in matrices) for s in sorted({q["source_service_queries"][t]["source_coverage_status"] for q in matrices})} for t in COLLECTIONS}}
 print("G27C_SOURCE_RESTRICTIONS="+json.dumps(summary,ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for k in ("g26c","json","geojson","markdown","work"):p.add_argument("--"+k,required=True,type=Path)
 a=p.parse_args();run(a.g26c,a.json,a.geojson,a.markdown,a.work)
