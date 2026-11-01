#!/usr/bin/env python3
"""G41 bounded actual official LNEG geology/hydro/borehole WFS discovery for
Marão and Alvão. Preserve source HTTP receipts, feature-type identifiers,
GetFeature GML/GeoJSON samples if genuinely returned. Never infer legal
geology or borehole absence from WFS failure/zero sample.
"""
from __future__ import annotations
import argparse,hashlib,json,time,urllib.request,urllib.parse,urllib.error,xml.etree.ElementTree as ET
from pathlib import Path
from shapely.geometry import shape,box
DATA={
 "harmonised_geology_50k":{
  "url":"https://inspire.lneg.pt/arcgis/rest/services/CartografiaGeologica/CGP50k/MapServer/exts/InspireFeatureDownload/service",
  "source_metadata":"https://sig.lneg.pt/metadados/catalog/search/resource/details.page?uuid=23ffa8e0-5e40-4479-bb19-671ac85dca7e"},
 "harmonised_geology_200k":{
  "url":"https://inspire.lneg.pt/arcgis/rest/services/CartografiaGeologica/CGP200k/MapServer/exts/InspireFeatureDownload/service",
  "source_metadata":"https://sig.lneg.pt/metadados/catalog/search/resource/details.page?uuid=b2e7fda4-38a7-4d3e-bc35-f0c5050e5578"},
 "hydrogeology_200k_vector":{
  "url":"https://sig.lneg.pt/server/services/CHP200k_vetor/MapServer/WFSServer",
  "source_metadata":"https://sig.lneg.pt/metadados/catalog/search/resource/details.page?uuid=9bb77a39-6320-4e1d-a199-aa201f473c13"},
 "SONDABASE_boreholes":{
  "url":"https://sig.lneg.pt/server/services/Sondabase/MapServer/WFSServer",
  "source_metadata":"https://sig.lneg.pt/metadados/catalog/search/resource/details.page?uuid=25fc9f7335f34d9a80b5bb58de34d80a"}}
AREAS={
 "Marao":(-7.98,41.25,-7.75,41.39),
 "Alvao":(-7.87,41.36,-7.65,41.53)}
MAX_BYTES=2_500_000
def limited(url):
    if not url.startswith("https://"):raise ValueError("G41_only_primary_https")
    req=urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte-G41-GeoLNEG-source-WFS/1.0",
            "Accept":"application/json,application/geo+json,application/xml,text/xml,*/*"})
    try:
        with urllib.request.urlopen(req,timeout=24) as r:
            b=r.read(MAX_BYTES+1)
            if len(b)>MAX_BYTES:raise ValueError("G41_bounded_response_exceeded_2p5MB")
            return b,{"http_status":r.status,"bytes":len(b),
                "SHA256":hashlib.sha256(b).hexdigest(),"content_type":r.headers.get("content-type","")}
    except (urllib.error.URLError,TimeoutError,ValueError) as e:
        raise RuntimeError(type(e).__name__+("_HTTP"+str(e.code) if isinstance(e,urllib.error.HTTPError) else "")) from e
def cap_names(raw):
    root=ET.fromstring(raw)
    if not any(z in root.tag for z in ("WFS_Capabilities","WFS_Capabilities".lower(),"Capabilities")):
        raise ValueError("G41_not_OGC_service_capabilities")
    rows=[]
    for ft in root.iter():
        if ft.tag.rsplit("}",1)[-1]!="FeatureType":continue
        name,title=None,None
        for sub in ft.iter():
            last=sub.tag.rsplit("}",1)[-1]
            if last=="Name" and name is None:name=(sub.text or "").strip()
            if last=="Title" and title is None:title=(sub.text or "").strip()
        if name:rows.append({"source_typeName":name,"source_title":title})
    return rows
def pick_type(rows,label):
    if not rows:return None
    if label.startswith("harmonised_geology"):
        words=("geologicunit","geologic_unit","geology","geologico","geologia")
    elif label.startswith("hydrogeology"):
        words=("hydro","aquifer","aqui","litolog","geologico")
    else:words=("sonda","sond","bore","furo")
    cand=[r for r in rows if any(w in (r["source_typeName"]+" "+(r["source_title"] or "")).lower() for w in words)]
    return (cand[0] if cand else rows[0])
def fetch_features(endpoint,typename,area):
    minlon,minlat,maxlon,maxlat=area
    plan=[
       {"service":"WFS","version":"2.0.0","request":"GetFeature","typeNames":typename,
        "count":"5","srsName":"EPSG:4326","bbox":f"{minlon},{minlat},{maxlon},{maxlat},EPSG:4326",
        "outputFormat":"application/json"},
       {"service":"WFS","version":"2.0.0","request":"GetFeature","typeNames":typename,
        "count":"5","srsName":"EPSG:4326","bbox":f"{minlat},{minlon},{maxlat},{maxlon},EPSG:4326",
        "outputFormat":"application/json"}]
    results=[]
    for k,params in enumerate(plan):
        url=endpoint+"?"+urllib.parse.urlencode(params)
        try:
            b,receipt=limited(url)
            try:
                data=json.loads(b)
            except (json.JSONDecodeError,UnicodeDecodeError):
                # Could be GML or WFS exception; do not treat as GeoJSON.
                root=ET.fromstring(b)
                typ=root.tag.rsplit("}",1)[-1]
                results.append({"status":"ORIGINAL_WFS_NON_GEOJSON_NOT_CLAIMED_AS_VECTOR",
                    "source_XML_root":typ,"query_axis_order_attempt":k,
                    **receipt})
                continue
            fs=data.get("features",[]) if isinstance(data,dict) else []
            if data.get("type")!="FeatureCollection" or not isinstance(fs,list) or len(fs)>5:
                results.append({"status":"JSON_NOT_VALID_BOUNDED_GEOJSON_FEATURECOLLECTION",
                   "query_axis_order_attempt":k,**receipt})
                continue
            valid=[]
            for f in fs:
                try:
                    geom=shape(f["geometry"])
                    if geom.is_empty or not geom.is_valid:continue
                    # Axis order may change; avoid asserting intersecting features
                    # from remotely malformed crs or bbox order.
                    if geom.intersects(box(*area)):valid.append(f)
                except (KeyError,ValueError,TypeError):continue
            if valid:
                return {"status":"ORIGINAL_LNEG_WFS_GEOJSON_FEATURES_OBSERVED",
                    "original_service_query_geometries_in_requested_bbox":len(valid),
                    "response_truncated_to_maximum_5":len(fs)>=5,
                    "not_exhaustive_or_statutory_coverage":True,
                    "source_query_axis_order_attempt":k,**receipt},\
                    json.dumps({"type":"FeatureCollection","features":valid},ensure_ascii=False).encode()
            results.append({"status":"WFS_VALID_GEOJSON_BUT_NO_VERIFIED_FEATURE_INTERSECTIONS",
                "returned_count":len(fs),"query_axis_order_attempt":k,**receipt})
        except (RuntimeError,ValueError,ET.ParseError) as e:
            results.append({"status":"SOURCE_WFS_GETFEATURE_UNAVAILABLE_NOT_ZERO_EVIDENCE",
                "error":str(e)[:190],"query_axis_order_attempt":k})
    return {"status":"NOT_PROVEN_NO_ABSENCE_INFERENCE","attempts":results},None
def execute(g40,outdir,report,markdown):
    if (not g40.get("all_30_portfolio_retained") or g40.get("actual_IGN_source_original_TIFF_verified_count")!=27
        or not g40.get("G30_avoid_vs_tunnel_eastern_2D_same_ground_not_two_independent_east_solutions")):
        raise ValueError("G41_must_reuse_G40_30_and_identical_G30_east")
    outdir.mkdir(parents=True,exist_ok=True)
    registry=[];read_features=[]
    for label,source in DATA.items():
        endpoint=source["url"]
        params={"service":"WFS","version":"2.0.0","request":"GetCapabilities"}
        url=endpoint+"?"+urllib.parse.urlencode(params)
        record={"source_dataset":label,"official_LNEG_metadata_url":source["source_metadata"],
            "official_LNEG_WFS_endpoint":endpoint,"source_actual_vector_count_unknown_unless_verified":True}
        try:
            blob,receipt=limited(url)
            types=cap_names(blob)
            record.update({"capabilities_status":"VERIFIED_ORIGINAL_WFS_XML",
                "actual_LNEG_WFS_featureTypes_reported":types[:40],
                "total_source_FeatureTypes":len(types),
                "GetCapabilities_source":receipt})
            chosen=pick_type(types,label)
            record["candidate_original_source_typeName"]=chosen["source_typeName"] if chosen else None
            if chosen:
                for area,bbox in AREAS.items():
                    ans,vector=fetch_features(endpoint,chosen["source_typeName"],bbox)
                    result={"area":area,"requested_WGS84_bbox":list(bbox),**ans}
                    if vector is not None:
                        path=outdir/f"G41-LNEG-original-{label}-{area}-max5.geojson"
                        path.write_bytes(vector)
                        result["verified_original_bounded_GeoJSON_name"]=path.name
                        result["verified_original_bounded_GeoJSON_SHA256"]=hashlib.sha256(vector).hexdigest()
                        read_features.append({"dataset":label,"area":area,
                            "filename":path.name,"SHA256":result["verified_original_bounded_GeoJSON_SHA256"]})
                    record.setdefault("original_WFS_area_probes",[]).append(result)
        except (RuntimeError,ValueError,ET.ParseError) as e:
            record.update({"capabilities_status":"NO_VALID_WFS_SOURCE_EVIDENCE",
                  "source_error":str(e)[:200],"not_source_absence_or_zero_geological_hazards":True})
        registry.append(record)
        print("G41_SOURCE",json.dumps({"dataset":label,"WFS":record["capabilities_status"],
          "featureTypes":record.get("total_source_FeatureTypes"),
          "selected_type":record.get("candidate_original_source_typeName"),
          "areas":[{"name":a["area"],"status":a["status"],"kind":a.get("source_XML_root"),"attempts":a.get("attempts")} for a in record.get("original_WFS_area_probes",[])]},ensure_ascii=False),flush=True)
    out={"mission":"MN-GEO-RAIL-001","stage":"G41_official_LNEG_geology_hydrogeo_borehole_OGC_source_Marao_Alvao",
       "source_G40_30_routes_preserved":True,"all30_G10_G30":30,
       "official_source_count":len(DATA),"bounded_target_areas":AREAS,
       "official_LNEG_WFS_source_registry":registry,
       "original_bounded_GeoJSON_feature_observations":read_features,
       "not_complete_geological_coverage_of_Marao_Alvao":True,
       "1_to_50000_geology_partial_sheet_coverage_not_assume_no_geology_where_no_data":True,
       "not_all_boreholes_exist_in_Sondabase_or_access_to_reports":True,
       "WFS_count5_is_intentionally_non_exhaustive":True,
       "no_tunnel_geotechnics_3D_hydrogeological_analysis_or_EIA":True,
       "Natura2000_Art6_and_PIC_unresolved":True,
       "new_DGT_2m_tiles":0,"Fxx_accepted":False,"Site_authorized":False}
    report.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
    md=["# G41 — Auditoria de fontes geológicas e hidrogeológicas LNEG no Marão–Alvão",
       "","**Não são sondagens de projeto nem uma caracterização geotécnica.** Foram consultados quatro serviços oficiais WFS de geologia harmonizada 1:50k e 1:200k, hidrogeologia vetorial 1:200k e SONDABASE, com pedidos GetCapabilities e GetFeature **limitados a cinco objetos** em duas áreas pequenas.",
       "","| Serviço | Capabilities original | N.º de tipos observados | Áreas com geometrias GeoJSON originais verificadas |",
       "|---|---|---:|---|"]
    for o in registry:
        valid=[x["area"] for x in o.get("original_WFS_area_probes",[]) if x["status"]=="ORIGINAL_LNEG_WFS_GEOJSON_FEATURES_OBSERVED"]
        md.append(f"| {o['source_dataset']} | {o['capabilities_status']} | {o.get('total_source_FeatureTypes','N/D')} | {', '.join(valid) if valid else 'não comprovado'} |")
    md+=["","## Interpretação",
       "- Uma resposta WFS válida apenas prova **disponibilidade da interface**; um resultado vazio ou erro não prova ausência de formações, recursos hídricos, furos ou riscos.",
       "- A geologia 1:50k está harmonizada apenas para um subconjunto de folhas; é necessário verificar cobertura local da geologia 1:200k e cartas mais detalhadas. Atributos INSPIRE não substituem perfis geotécnicos.",
       "- Hidrogeologia 1:200k não determina níveis piezométricos locais, permeabilidade do maciço, interferência de túnel, efeitos nos habitats, drenagem ou qualidade da água.",
       "- SONDABASE agrega sondagens de origens e objetivos diversos: mesmo uma ocorrência próxima não equivale a sondagem adequada ao eixo e método de escavação proposto.",
       "- A carta Natura 2000 ICNF/MITECO G28 e os estudos anteriores de estações G23–G27 devem permanecer condicionantes do traçado. PIC não foi resolvido.",
       "","**Portão para engenharia:** obter recortes completos quando se souberem os eixos candidatos 3D, validar escala e cobertura geológica, registar proveniência e compatibilizar altimetria antes de atribuir quantidades de túnel ou custos.",
       "","Dados originalmente devolvidos em GeoJSON são publicados só quando validada a geometria e a interseção real com a área de ensaio. Sem novas quadrículas DGT, Fxx/Site.",""]
    markdown.write_text("\n".join(md))
    print("G41_RESULT",json.dumps({"service_verified":sum(q["capabilities_status"]=="VERIFIED_ORIGINAL_WFS_XML" for q in registry),
         "real_original_lneg_bounded_geojson_outputs":len(read_features),"source_count":len(registry),
         "not_geotechnical_exploration":True},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for k in ("g40","outdir","json","markdown"):p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args()
    execute(json.loads(a.g40.read_text()),a.outdir,a.json,a.markdown)
if __name__=="__main__":main()
