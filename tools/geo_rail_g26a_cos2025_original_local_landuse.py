#!/usr/bin/env python3
"""G26A: bounded original DGT COS2025 OGC features for seven original G25
station RESEARCH neighborhoods. COS land use != legal site or zoning.
Preserve original source polygon class, clip to 400m circle, no DGT raster.
"""
import argparse,hashlib,json,time,urllib.request,urllib.parse,math
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
from shapely.geometry import Point,shape,mapping
from shapely.ops import transform
from pyproj import Transformer

SOURCE_SHA="be35181c882c2f6ede4d07f7e0a68b084bb6247c54a7da0d1d566a66f844dffd"
ENDPOINT="https://ogcapi.dgterritorio.gov.pt/collections/cos2025v1/items"
RADIUS=400
PAGES=10
LIMIT=200
MAX_BYTES=15000000

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def site_points(g25):
 if g25["two_compulsory_cities"]!=["Vila Real","Bragança"] or g25["Fxx_accepted"] or g25["Site_authorized"]:raise ValueError("G26A_bad_G25_source")
 sites={}
 for q in g25["source_shortlisted_road_reference_route_cases"]:
  xy=tuple(round(float(z),2) for z in q["original_study_EPSG3763_XY"])
  sites.setdefault(xy,{"xy":xy,"city":q["mandatory_market"],"families":set(),"seeds":set()})
  sites[xy]["families"].add(q["source_corridor_family"])
  sites[xy]["seeds"].add(q["source_G24_reference_seed"])
 if len(sites)!=7 or sum(v["city"]=="Vila_Real" for v in sites.values())!=3 or sum(v["city"]=="Braganca" for v in sites.values())!=4:
  raise ValueError("G26A_not_seven_unique_source_study_points")
 return list(sites.values())

def get_page(url):
 u=urllib.parse.urlparse(url)
 if (u.scheme,u.hostname,u.path)!=("https","ogcapi.dgterritorio.gov.pt","/collections/cos2025v1/items"):
  raise ValueError("G26A_untrusted_producer")
 request=urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte-original-COS2025-targeted/1.0","Accept":"application/geo+json,application/json"})
 with urllib.request.urlopen(request,timeout=65) as response:
  if response.status!=200 or urllib.parse.urlparse(response.url).hostname!=u.hostname:raise ValueError("G26A_untrusted_redirect")
  raw=response.read(MAX_BYTES+1)
 if len(raw)>MAX_BYTES:raise ValueError("G26A_source_page_too_large")
 obj=json.loads(raw)
 if obj.get("type")!="FeatureCollection" or not isinstance(obj.get("features"),list) or len(obj["features"])>LIMIT:
  raise ValueError("G26A_invalid_COS2025_source_collection")
 return obj,hashlib.sha256(raw).hexdigest()

def inspect_site(site,to_utm,to_wgs):
 pt=Point(*site["xy"])
 roi=pt.buffer(RADIUS,quad_segs=32)
 bbox=transform(to_wgs.transform,roi.envelope).bounds
 url=ENDPOINT+"?"+urllib.parse.urlencode({"bbox":",".join(f"{z:.8f}" for z in bbox),"f":"json","limit":LIMIT})
 seen=set();rows=[];provenance=[];finished=False
 for page in range(PAGES):
  if page:time.sleep(.65)
  obj,digest=get_page(url)
  links=[z["href"] for z in obj.get("links",[]) if isinstance(z,dict) and z.get("rel")=="next" and z.get("href")]
  provenance.append({"page":page+1,"raw_response_SHA256":digest,"returned":len(obj["features"]),"has_next":bool(links)})
  for f in obj["features"]:
   ident=str(f.get("id",f.get("properties",{}).get("objectid","")))
   if not ident:raise ValueError("G26A_missing_original_COS_feature_id")
   if ident in seen:continue
   seen.add(ident)
   p=f.get("properties",{})
   required=("cos25v1_n1_c","cos25v1_n1_l","cos25v1_n4_c","cos25v1_n4_l")
   if not all(z in p for z in required):raise ValueError("G26A_missing_original_COS2025_level_class")
   g=transform(to_utm.transform,shape(f["geometry"]))
   if g.is_empty or not g.is_valid:raise ValueError("G26A_invalid_original_COS_geometry")
   clipped=g.intersection(roi)
   if clipped.is_empty or clipped.area<=0:continue
   rows.append({"type":"Feature","geometry":mapping(transform(to_wgs.transform,clipped)),
     "properties":{"source_site_EPSG3763_XY":list(site["xy"]),"source_city":site["city"],
       "DGT_COS2025_original_polygon_id":ident,
       "DGT_COS2025_n1_c":str(p["cos25v1_n1_c"]),"DGT_COS2025_n1_l":str(p["cos25v1_n1_l"]),
       "DGT_COS2025_n4_c":str(p["cos25v1_n4_c"]),"DGT_COS2025_n4_l":str(p["cos25v1_n4_l"]),
       "clipped_original_COS2025_intersection_area_ha":round(clipped.area/10000,5),
       "polygon_does_not_establish_station_land_rights_or_zoning":True}})
  if len(seen)>1800:raise ValueError("G26A_unbounded_COS2025_source_features")
  if not links:finished=True;break
  if len(links)!=1:raise ValueError("G26A_unexpected_source_pagination")
  url=urllib.parse.urljoin(url,links[0])
 if not finished:raise ValueError("G26A_COS2025_pagination_incomplete")
 if not rows:raise ValueError("G26A_original_COS2025_no_polygons_for_site")
 by_class=defaultdict(float)
 for row in rows:
  p=row["properties"];by_class[(p["DGT_COS2025_n1_c"],p["DGT_COS2025_n1_l"])]+=p["clipped_original_COS2025_intersection_area_ha"]
 coverage=sum(by_class.values())/(roi.area/10000)
 if not (.92<=coverage<=1.08):raise ValueError("G26A_COS_source_area_incomplete_or_overlapping_"+str(coverage))
 info={"city":site["city"],"study_EPSG3763_XY":list(site["xy"]),
  "original_source_families":sorted(site["families"]),
  "source_400m_circle_area_ha":round(roi.area/10000,3),
  "original_COS2025_polygon_count":len(rows),
  "original_COS2025_covered_circle_fraction":round(coverage,4),
  "landuse_N1_classes":[{"code":c,"label":label,"ha":round(area,4),"percent":round(100*area*10000/roi.area,2)}
    for (c,label),area in sorted(by_class.items())],
  "original_DGT_response_SHA_receipts":provenance,
  "original_landuse_2025_is_not_legal_parcel_or_station_viability":True}
 return info,rows

def main():
 p=argparse.ArgumentParser()
 for x in ("g25","json","geojson","markdown"):p.add_argument("--"+x,type=Path,required=True)
 a=p.parse_args()
 if sha(a.g25)!=SOURCE_SHA:raise ValueError("G26A_original_G25_SHA_drift")
 sites=site_points(json.loads(a.g25.read_text()))
 forward=Transformer.from_crs(4326,3763,always_xy=True)
 reverse=Transformer.from_crs(3763,4326,always_xy=True)
 output=[];features=[]
 for i,site in enumerate(sites):
  if i:time.sleep(.75)
  info,rows=inspect_site(site,forward,reverse)
  output.append(info);features.extend(rows)
 summary={"mission":"MN-GEO-RAIL-001","stage":"G26A_original_DGT_COS2025v1_S2_7_study_site_landuse",
  "utc":datetime.now(timezone.utc).isoformat(),"G25_SHA256":SOURCE_SHA,
  "DGT_original_COS2025_endpoint":ENDPOINT,"license":"DGT CC-BY 4.0",
  "source_year_not_present_day_survey":2025,
  "study_radius_m":RADIUS,"study_sites":len(output),
  "original_COS2025_polygon_feature_count":len(features),
  "original_2025_COS_landuse_by_site":output,
  "not_an_official_PDM_REN_RAN_SRUP_cadastre_or_legal_buildability_check":True,
  "no_new_DGT_2m_elevation_acquisitions":True,"Fxx_accepted":False,"Site_authorized":False,
  "mandatory_cities":["Vila Real","Bragança"],"Sanabria_excluded":True}
 a.json.parent.mkdir(parents=True,exist_ok=True);a.json.write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 a.geojson.parent.mkdir(parents=True,exist_ok=True)
 a.geojson.write_text(json.dumps({"type":"FeatureCollection","name":"DGT COS2025 clipped 400m study research, not stations","features":features},ensure_ascii=False)+"\n")
 md=["# G26A — COS2025 original DGT: uso e ocupação de sete áreas de estudo",
  "","A COS 2025 é vetorial e representa uso/ocupação do solo; não certifica parcelas acessíveis ou livre de condicionantes. Círculos de 400m não correspondem à implantação de estações.",
  "","| Cidade | Ponto PT-TM06 | Polígonos COS2025 | Cobertura | Classes N1 (ha) |",
  "|---|---|---:|---:|---|"]
 for z in output:
  classes="; ".join(f"{c['label']} {c['ha']}" for c in z["landuse_N1_classes"])
  md.append(f"| {z['city']} | {z['study_EPSG3763_XY']} | {z['original_COS2025_polygon_count']} | {z['original_COS2025_covered_circle_fraction']} | {classes} |")
 md+=["","É necessário validar separadamente PDM, REN/RAN/SRUP, domínio hídrico, rede viária, servidões e cadastro antes de selecionar local de estação.","Fonte original DGT COS2025v1, CC-BY 4.0; sem novos MDT2m, sem Fxx/Site."]
 a.markdown.parent.mkdir(parents=True,exist_ok=True);a.markdown.write_text("\n".join(md))
 print("G26A_COS2025="+json.dumps({"sites":len(output),"polygons":len(features),
  "pages":sum(len(x["original_DGT_response_SHA_receipts"]) for x in output),
  "by_city":[{"city":z["city"],"xy":z["study_EPSG3763_XY"],"land_classes":z["landuse_N1_classes"]} for z in output]},
  ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
