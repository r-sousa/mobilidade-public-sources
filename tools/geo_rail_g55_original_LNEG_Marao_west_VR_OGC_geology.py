#!/usr/bin/env python3
"""G55 obtain ACTUAL official LNEG OGC API geology and hydro features in a
BOUNDED 25 km west-of-Vila-Real source-grid approach study window.

Select the LAST 25km of the AFSC -> Vila Real W original G10/G30 first
sector for each of the SIX G52 source family representatives. Use union
1.25km study buffer in original Portuguese PT-TM06 EPSG3763, project bbox
to CRS84 for OGC API Features discovery.

Official original source https://ogcapi.lneg.pt, collections:
- harmonized lithology 1:50k,1:200k
- geological faults 1:1M (coarse caution)
- SONDABASE public borehole POINT locations (not logs)
- public water POINT locations (not groundwater flow model).

Bound 12x100 pages per collection; mark TRUNCATED if not complete. Official
licence CC-BY 4.0. No source claims outside extracted footprint.
Output clipped original-derived GeoJSON with source IDs not edited in place,
projection checks, selected 25km source approach research centerlines,
intersections and source coverage, official-source status. This is GEOLOGY
CONTEXT, not tunnel prediction, geotechnical risk clearance, engineering
rail line, original large-scale fault trace or borehole core properties.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,time,sys
from pathlib import Path
from urllib.parse import urljoin,urlparse
from collections import Counter
import requests
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString,shape,mapping,box,Point
from shapely.ops import unary_union,substring,transform
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g42_original_terrain_LP_all30_module_evidence import ANCHORS,canonical_point
from geo_rail_g26b_next_DGT2m_study_footprint_gate import indices

BASE="https://ogcapi.lneg.pt"
LEG_KM=25
BUFFER_M=1250
PAGE_LIMIT=100
PAGE_CAP=12
COLLECTIONS={
 "cgp50k-prt-lneg-en-50k-lithology":{"type":"geology_50k_polygon","scale":"1:50 000"},
 "cgp200k-prt-lneg-en-200k-lithology":{"type":"geology_200k_polygon","scale":"1:200 000"},
 "cgp1m-ge-geologicfault":{"type":"geological_fault_1m_line","scale":"1:1 000 000"},
 "sondabase-sondagem":{"type":"sondabase_borehole_location","scale":"point inventory"},
 "recursoshidro-pontos-de-gua":{"type":"hydro_water_location","scale":"point inventory"}
}
TO_PT=Transformer.from_crs(4326,3763,always_xy=True)
TO_WGS=Transformer.from_crs(3763,4326,always_xy=True)
def original_west_window(g10,g30,g52,g37):
    if (not g52["source_original_all30_preserved"] or
        g52["source_27_G10_3_G30_count"]!=30 or
        len(g52["G52_six_representative_original_source_routes_for_NEXT_ground_3D"])!=6):
        raise ValueError("G55_original_G52_30_6_governance")
    old={tuple(v) for v in g37["source_84_original_DGT_tile_ids_in_PTTM06"]}
    if len(old)!=84:raise ValueError("G55_G37_true_84_original_DGT_source")
    source={f["properties"]["id"]:f for f in g10["features"]+g30["features"]}
    if len(source)!=30:raise ValueError("G55_original_thirty_geographic_G10_G30")
    chosen=g52["G52_six_representative_original_source_routes_for_NEXT_ground_3D"]
    trajectories={}
    for name in chosen:
        f=source[name]
        pts=[canonical_point(a) for a in f["geometry"]["coordinates"]]
        if ANCHORS[0] not in pts:raise ValueError("G55_source_W_Vila_Real_orig_anchor_missing")
        first=pts.index(ANCHORS[0])
        line=LineString(pts[:first+1])
        if line.length<LEG_KM*1000:raise ValueError("G55_source_original_first_rail_research_module_short")
        near=substring(line,line.length-LEG_KM*1000,line.length)
        trajectories[name]=near
    roi=unary_union([l.buffer(BUFFER_M,cap_style=2,join_style=2) for l in trajectories.values()])
    if roi.is_empty or not roi.is_valid:raise ValueError("G55_original_site_2km_grid_buffer_bad")
    west=transform(TO_WGS.transform,roi)
    bbox=[round(float(t),6) for t in west.bounds]
    if not(-9.9<bbox[0]<-6.0 and -9.9<bbox[2]<-6.0 and 40.0<bbox[1]<43 and 40.0<bbox[3]<43):
        raise ValueError("G55_study_window_outside_North_Portugal")
    if bbox[2]-bbox[0]>1.4 or bbox[3]-bbox[1]>.6:
        raise ValueError("G55_bounded_study_window_too_wide")
    tilereq=indices(roi)
    return trajectories,roi,bbox,{
      "source_original_DGT84_known_tiles":84,
      "source_original_DGT_1km_tile_required_IF_this_study_polygon":len(tilereq),
      "source_original_DGT_1km_tile_already_known":len(tilereq&old),
      "source_original_DGT_1km_tile_not_in_current_manifest":len(tilereq-old),
      "coverage_is_only_of_source_2km_grid_study_polygon_not_rail_project":True,
      "no_additional_raw_DGT_tile_authorized":True}
def getpage(session,url,params=None):
    # Only fetch approved official OGC API endpoints; avoid redirecting to
    # arbitrary providers or following cross-site pagination URL.
    if not url.startswith(BASE+"/collections/"):
        raise ValueError("G55_refuse_nonofficial_collection_URL")
    errors=[]
    for i in range(2):
        try:
            r=session.get(url,params=params,timeout=48,
                    headers={"Accept":"application/geo+json, application/json",
                             "User-Agent":"MobilidadeNorte-GeoscienceSourceResearch/1.0"})
            if r.status_code!=200:
                raise ValueError("HTTP_"+str(r.status_code))
            if len(r.content)>17_000_000:raise ValueError("OGC_json_response_17MB_cap")
            obj=r.json()
            if not isinstance(obj,dict):raise ValueError("OGC_response_not_JSON_object")
            return obj,hashlib.sha256(r.content).hexdigest()
        except (requests.RequestException,ValueError) as exc:
            errors.append(str(exc)[:180])
            if i==0:time.sleep(1)
    raise ValueError("G55_official_bounded_query_unavailable_"+";".join(errors))
def get_collection(session,id,bbox,roi):
    meta={"collection_id":id,"source_official_URL":BASE+"/collections/"+id,
       "query_CR84_bbox_lonlat":[round(z,6) for z in bbox],
       "page_cap":PAGE_CAP,"per_page_items_cap":PAGE_LIMIT,
       "licensed_CC_BY_4_0_official_LNEG":True,"source_query_complete":False,
       "no_geotechnical_drilling_logs":True}
    url=BASE+"/collections/"+id+"/items"
    next_url=url;params={"bbox":",".join(str(x) for x in bbox),"limit":PAGE_LIMIT,"f":"json"}
    seen=set();feats=[];rejected=0;checksums=[]
    try:
        for page in range(PAGE_CAP):
            if next_url in seen:raise ValueError("repeated_pagination_link")
            seen.add(next_url)
            v,h=getpage(session,next_url,params)
            checksums.append(h)
            if v.get("type")!="FeatureCollection" or not isinstance(v.get("features"),list):
                raise ValueError("official_LNEG_OgcItems_not_FeatureCollection")
            for x in v["features"]:
                geom=x.get("geometry")
                if not geom:rejected+=1;continue
                g=shape(geom)
                if g.is_empty or not g.is_valid:
                    rejected+=1;continue
                if not(-12<g.bounds[0]<-5 and 36<g.bounds[1]<43 and
                        -12<g.bounds[2]<-5 and 36<g.bounds[3]<43):
                    raise ValueError("official_LNEG_geographic_geometry_not_CRS84")
                gp=transform(TO_PT.transform,g)
                if not gp.intersects(roi):continue
                cut=gp.intersection(roi)
                if cut.is_empty or not cut.is_valid:
                    rejected+=1;continue
                geo=transform(TO_WGS.transform,cut)
                info={"source_original_feature_id":str(x.get("id",""))[:160],
                    "LNEG_source_collection_id":id,
                    "geometry_is_CLIPPED_DERIVED_FROM_original_source":True}
                # Original original OGC attributes: preserve a bounded copy
                # for provenance, not harmful original personal details.
                props=x.get("properties") or {}
                important={k:v for k,v in props.items() if
                   any(c in k.lower() for c in ("lith","unidade","litolog","tipo","falha","descricao","geol","age","name","id"))
                   and isinstance(v,(str,int,float,bool,type(None)))}
                info["LNEG_source_litho_fault_attrs_extracted"]={k:str(v)[:150] if isinstance(v,str) else v
                                                                  for k,v in list(important.items())[:14]}
                feats.append({"type":"Feature","geometry":mapping(geo),"properties":info})
            more=next((l.get("href") for l in v.get("links",[])
                       if l.get("rel")=="next" and l.get("href")),None)
            if more:
                joined=urljoin(next_url,more)
                if not joined.startswith(BASE+"/collections/"+id+"/items"):
                    raise ValueError("G55_OGC_next_pages_official_url_only")
                next_url=joined;params=None
            else:
                next_url=None;break
        meta.update({"status":"BOUNDED_OFFICIAL_GEOJSON_RETRIEVED",
          "source_query_complete":next_url is None,
          "partial_pagecap_or_limited":next_url is not None,
          "queried_pages":len(checksums),
          "source_page_SHA256":checksums,
          "actual_official_source_features_intersecting_ROI":len(feats),
          "source_feature_geom_invalid_or_missing_skipped":rejected,
          "provider_numberMatched_not_verified_total_coverage":True})
    except ValueError as e:
        meta.update({"status":"OFFICIAL_SOURCE_UNAVAILABLE_OR_GEOJSON_REJECTED",
          "source_error":str(e)[:250],"source_query_complete":False,
          "queried_pages":len(checksums),"source_page_SHA256":checksums,
          "actual_official_source_features_intersecting_ROI":len(feats),
          "source_feature_geom_invalid_or_missing_skipped":rejected})
    return meta,feats
def execute(g10,g30,g52,g37,jsonout,geoout,csvout,pngout,mdout):
    tracks,roi,bbox,inventory=original_west_window(g10,g30,g52,g37)
    session=requests.Session()
    datasets={};source_features=[];ready=0
    for id in COLLECTIONS:
        d,f=get_collection(session,id,bbox,roi)
        datasets[id]=d;source_features+=f
        if d["status"]=="BOUNDED_OFFICIAL_GEOJSON_RETRIEVED":ready+=1
        print("G55_LNEG_OFFICIAL_SOURCE",id,d["status"],d.get("actual_official_source_features_intersecting_ROI"),flush=True)
    if ready==0:
        raise RuntimeError("G55_NOT_ONE_AUTHENTIC_LNEG_COLLECTION_RETRIEVED_CANNOT_PUBLISH_GEOTECHNICAL_SOURCE_ACQUISITION")
    # Source-feature overlap can be counted for line and point separately.
    source_geoms={id:[] for id in COLLECTIONS}
    for f in source_features:
        p=f["properties"];id=p["LNEG_source_collection_id"]
        pp=transform(TO_PT.transform,shape(f["geometry"]))
        source_geoms[id].append(pp)
    rows=[]
    for name,line in tracks.items():
        result={"source_original_route_family":name,"west_25km_research_path_km":round(line.length/1000,3),
          "last_25km_before_G42_Vila_Real_W_anchor_only_NOT_exact_Marao_geographic_boundary":True}
        for id,gs in source_geoms.items():
            matched=sum(a.intersects(line) for a in gs)
            result["LNEG_"+id+"_features_touch_original_research_25km_line"]=matched
            d=datasets[id]
            result["LNEG_"+id+"_official_query_complete"]=d["source_query_complete"]
            result["LNEG_"+id+"_status"]=d["status"]
        rows.append(result)
    shapes=[]
    for name,line in tracks.items():
        geom=transform(TO_WGS.transform,line)
        shapes.append({"type":"Feature","geometry":mapping(geom),
          "properties":{"source_2km_G10_G30_family":name,
             "line":"LAST_25KM_OF_SOURCE_GRID_GEOGRAPHIC_MODULE_BEFORE_VR_W",
             "no_engineered_RTE_T_RAILWAY_ALIGNMENT":True}})
    source_geo={"type":"FeatureCollection","features":shapes+source_features}
    geoout.write_text(json.dumps(source_geo,ensure_ascii=False)+"\n")
    out={"mission":"MN-GEO-RAIL-001","stage":"G55_first_actual_LNEG_OGC_geology_water_borehole_original_source_bounded_VilaReal_west_research_window",
      "official_LNEG_base":BASE,"official_licence":"CC-BY 4.0","study_ROI_definition":
        "Union buffered 1250m of LAST 25km of original first G10/G30 2km research module to Vila Real WEST anchor",
      "study_ROI_not_official_Marao_Alvao_boundary":True,"official_source_bbox_CRS84":[float(x) for x in bbox],
      "six_research_family_original_source_tracks_25km":list(tracks),
      "source_original_all30_preserved":True,"original_DGT84_previous_tiles_not_reacquired":True,
      "original_DGT_source_tile_coverage_study_buffer_only":inventory,
      "LNEG_actual_official_geojson_collections_metadata":datasets,
      "LNEG_actual_source_spatial_intersection_count_by_research_family":rows,
      "LNEG_source_features_in_output_derived_CLIPPED_for_bounded_footprint":len(source_features),
      "source_clipped_LNEG_features_are_NOT_geotechnical_TUNNEL_parameters":True,
      "borehole_location_does_not_mean_exposed_log_or_depth":True,
      "one_to_one_million_faults_not_precise_local_fault_traces":True,
      "no_Natura2000_PIC_aquifer_LNEG_tunnel_environmental_clearance":True,
      "no_rail_3D_line_minimum_cover_portals_costs_or_times":True,
      "no_original_DGT_OR_IGN_reacquisition":True,
      "Fxx_accepted":False,"Site_authorized":False}
    jsonout.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    with csvout.open("w",newline="",encoding="utf-8-sig") as f:
        fields=["source_original_route_family","west_25km_research_path_km"]+[
           "LNEG_"+q+"_features_touch_original_research_25km_line" for q in COLLECTIONS]
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";")
        w.writeheader()
        for a in rows:w.writerow({k:a.get(k) for k in fields})
    fig,ax=plt.subplots(figsize=(10,7),layout="constrained")
    pl=source_geoms["cgp200k-prt-lneg-en-200k-lithology"]
    for k,g in enumerate(pl):
        if g.geom_type in ("Polygon","MultiPolygon"):
            for geom in [g] if g.geom_type=="Polygon" else g.geoms:
                xs,ys=geom.exterior.xy
                ax.fill(np.asarray(xs)/1000,np.asarray(ys)/1000,
                    color=plt.cm.tab20(k%20),alpha=.16,ec="#999999",lw=.3)
    for id,marker,color in (("sondabase-sondagem","o","#bd6530"),
                              ("recursoshidro-pontos-de-gua","^","#337f99")):
        geoms=source_geoms[id]
        for g in geoms:
            if g.geom_type=="Point":
                ax.scatter([g.x/1000],[g.y/1000],marker=marker,c=color,s=10,alpha=.8)
    for i,(name,line) in enumerate(tracks.items()):
        xx,yy=line.xy
        ax.plot(np.asarray(xx)/1000,np.asarray(yy)/1000,lw=1.6,
                 alpha=.86,label=name)
    ax.set_aspect("equal",adjustable="datalim")
    ax.set_xlabel("E (PT-TM06 km)");ax.set_ylabel("N (PT-TM06 km)")
    ax.set_title("G55 · Fonte oficial LNEG: geologia e pontos (onde fornecidos), janela oeste de Vila Real — NÃO túnel desenhado",loc="left")
    ax.grid(alpha=.14);ax.legend(loc="best",fontsize=7)
    fig.savefig(pngout,dpi=160,bbox_inches="tight");plt.close(fig)
    md=["# G55 — Primeiro acesso efetivo à geologia e hidrogeologia oficiais do LNEG",
       "","O portal LNEG não foi apenas listado: foram executadas chamadas OGC API a coleções oficiais para uma janela **restrita** definida pelos últimos 25km dos seis traçados de investigação G52 antes da âncora ocidental de Vila Real, com buffer de ±1250m. A janela **não** é um perímetro oficial do Marão–Alvão nem um eixo ferroviário construído.",
       "","| Coleção LNEG | Consultas | Feições oficiais que intercetam a janela | Cobertura da resposta |",
       "|---|---:|---:|---|"]
    for id,m in datasets.items():
        md.append(f"| {id} | {m.get('queried_pages',0)} | {m.get('actual_official_source_features_intersecting_ROI',0)} | {m['status']} / {'integral na janela de consulta' if m['source_query_complete'] else 'parcial/não confirmada'} |")
    md+=["",f"Total: **{len(source_features)} geometrias efetivamente extraídas e recortadas**, de {ready} coleções que devolveram GeoJSON validado. Fonte: "+BASE+" (CC BY 4.0). As contagens são de feições oficiais e não de unidades geotécnicas distintas ou sondagens com relatório completo.",
      "","## Consequência para o atravessamento do Marão–Alvão",
      "1. A geologia cartográfica e as localizações de sondagens/pontos de água entram pela primeira vez em dados espaciais de estudo; confirmar escalas, cobertura, atributos e onde há mapas de detalhe antes de afirmar qualquer vantagem de túnel.",
      "2. A cartografia 1:50 000 não é geologia geotécnica de projeto. A 1:1 000 000, as falhas são apenas contexto regional, nunca localização milimétrica de fratura ou determinação de riscos de túnel.",
      "3. A janela derivada das poligonais G10/G30 não deve orientar aquisições de MDT em massa. Os eixos em planta com raio e ligações às estações devem ser deslocados/otimizados antes de definir a faixa real de obra e sondagens.",
      "4. Não presumir posição de um aquífero ou proteção de captações apenas a partir de pontos; requer delimitações hidrogeológicas e avaliação de escoamento.",
      "5. Confrontar este conjunto com o terreno de solo nu DGT e com o desenho longitudinal mista 12,5/15‰, depois passar aos possíveis portais e zonas de atravessamento, identificando ausências de cobertura por fonte.",
      "","**A publicação guarda a geometria derivada recortada, IDs e metadados de origem. Incompletude ou falhas das consultas estão registadas, sem preenchimento. Nenhuma estrutura, custo ou licença está demonstrada.**"]
    mdout.write_text("\n".join(md)+"\n")
    print("G55_RESULT",json.dumps({"original_source_LNEG_collections_responded":ready,
      "actual_official_source_features_clipped":len(source_features),
      "LNEG_sources":{k:{"status":v["status"],"features":v.get("actual_official_source_features_intersecting_ROI"),
                 "complete":v["source_query_complete"]} for k,v in datasets.items()},
      "six_source_west_research_tracks":len(tracks),"G37_native_DGT_tile_study_buffer":inventory,
      "bbox":bbox},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for k in ("g10","g30","g52","g37","json","geojson","csv","plot","markdown"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args()
    execute(*[json.loads(getattr(a,k).read_text()) for k in ("g10","g30","g52","g37")],
            a.json,a.geojson,a.csv,a.plot,a.markdown)
if __name__=="__main__":main()
