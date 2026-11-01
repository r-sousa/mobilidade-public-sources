#!/usr/bin/env python3
"""G38 bounded PT/ES bare-earth source discovery and Spain WCS MDT25 pilot.

Always reuse exact G37 84 official DGT 2m source tiles; no unapproved 1km tile
requests. European/Spanish services queried read-only with strictly bounded
response body and tiny representative original WCS GeoTIFF request (if supported).
A WCS response is NEVER ground terrain unless rasterio verifies actual pixels,
CRS, source extent and reasonable native resolution. Never present a DEM sample
as 3D railway design, rail speed, vertical datum harmonization or tunnel quantity.
"""
from __future__ import annotations
import argparse,datetime,hashlib,json,math,os,ssl,time,urllib.parse,urllib.request,urllib.error,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
from pyproj import Transformer
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import rowcol
WCS_ENDPOINTS=(
 "https://servicios.idee.es/wcs-inspire/mdt",
 "https://www.ign.es/wcs-inspire/mdt",
)
LNEG_ENDPOINTS=(
 "https://geoportal.lneg.pt/arcgis/services",
 "https://geoportal.lneg.pt",
)
TRIAL_TIMEOUT=22
MAX_CAP_BYTES=3_000_000
MAX_TIFF_BYTES=3_000_000
# On eastern part of PT–Zamora axis, within the Spanish municipality of Zamora;
# a pilot *source* test only, not a proposed station or a selected alignment.
SAMPLE_LON=-5.746
SAMPLE_LAT=41.503
WINDOW_HALF_M=500
def safe_get(url, max_bytes=MAX_CAP_BYTES, timeout=TRIAL_TIMEOUT):
    if not url.startswith("https://"):raise ValueError("G38_not_https_primary_source")
    req=urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte-MN-GEO-RAIL-001-G38-primary-DTM-pilot/1.0",
                                          "Accept":"application/xml,application/gml+xml,image/tiff,application/octet-stream,*/*"})
    start=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            data=resp.read(max_bytes+1)
            if len(data)>max_bytes:raise ValueError("G38_source_response_exceeds_safe_max_bytes")
            if not (200<=resp.status<300):
                raise ValueError("G38_non_success_HTTP")
            return data,{"http_status":resp.status,"content_type":resp.headers.get("Content-Type"),
                "bytes":len(data),"elapsed_s":round(time.monotonic()-start,2),
                "source_SHA256":hashlib.sha256(data).hexdigest()}
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError,ssl.SSLError) as exc:
        raise RuntimeError("G38_source_request_failed_"+type(exc).__name__+
                           ("_HTTP"+str(exc.code) if isinstance(exc,urllib.error.HTTPError) else "")) from exc
def url_of(endpoint,params):
    return endpoint+"?"+urllib.parse.urlencode(params,doseq=True,safe=":(),")
def parse_wcs_capabilities(raw):
    root=ET.fromstring(raw)
    if "Capabilities" not in root.tag:
        raise ValueError("G38_WCS_returned_non_capabilities")
    found=[]
    # WCS 2.0 or WCS1.0 CoverageSummary, cautious extraction
    for elem in root.iter():
        if elem.tag.split("}")[-1] in ("CoverageSummary","CoverageOfferingBrief"):
            rawids=[]
            for sub in elem.iter():
                if sub.tag.split("}")[-1] in ("CoverageId","name","identifier"):
                    if sub.text and len(sub.text)<250:rawids.append(sub.text.strip())
            found.extend(rawids)
    return sorted(set(found))
def choose_candidate(ids):
    # Actual official IGN/CNIG WCS 2.0.1 GetCapabilities response (2026-11-01)
    # advertises Elevacion25830_25, NOT a coverage named MDT25.
    if "Elevacion25830_25" in ids:return "Elevacion25830_25"
    preferred=sorted((name for name in ids if any(v in name.lower() for v in ("mdt25","mdt_25","mdt25m"))),key=len)
    return preferred[0] if preferred else None
def parse_wcs_description(raw):
    root=ET.fromstring(raw)
    names=set();crs_refs=set()
    for el in root.iter():
        name=el.tag.split("}")[-1]
        if name in ("axisLabels","axisLabel") and el.text:
            names.update(el.text.strip().split())
        for key,val in el.attrib.items():
            if "srsName" in key or "crs" in key.lower():
                crs_refs.add(val)
    return {"axis_labels":sorted(names),"crs_refs":sorted(crs_refs),
            "wcs_describe_source_xml_sha256":hashlib.sha256(raw).hexdigest()}
def sanity_ground_tiff(raw,epsg=25830):
    if raw[:4] not in (b"II*\x00",b"MM\x00*"):
        raise ValueError("G38_response_not_GeoTIFF_signature")
    with MemoryFile(raw) as mem:
        with mem.open() as ds:
            if ds.count!=1 or ds.width>800 or ds.height>800 or ds.width<5 or ds.height<5:
                raise ValueError("G38_raster_band_or_dimensions_out_of_bound")
            if ds.crs is None or ds.crs.to_epsg() not in (25830,25829,4326):
                raise ValueError("G38_raster_CRS_not_original_IGNEvidence")
            bounds=ds.bounds
            array=ds.read(1,masked=True)
            valid=np.asarray(array.compressed(),dtype=float)
            if len(valid)<25 or not np.isfinite(valid).all():
                raise ValueError("G38_raster_has_insufficient_valid_terrain")
            xres,yres=abs(ds.res[0]),abs(ds.res[1])
            if ds.crs.to_epsg() in (25830,25829) and not (5<=xres<=50 and 5<=yres<=50):
                raise ValueError("G38_unexpected_metric_pixel_resolution")
            if not (min(valid)>-200 and max(valid)<5000):
                raise ValueError("G38_unreasonable_ground_elevations")
            return {"verified_actual_original_raster":True,
              "source_role":"IGN_CNIG_WCS_mdt25_bare_earth_sample_only",
              "pixels_valid":len(valid),
              "dimensions":[ds.width,ds.height],"source_crs":str(ds.crs),
              "resolution":[round(xres,3),round(yres,3)],
              "geographic_source_bounds_as_native_CRS":[round(k,2) for k in bounds],
              "raster_min_m":round(float(np.min(valid)),2),
              "raster_p50_m":round(float(np.median(valid)),2),
              "raster_max_m":round(float(np.max(valid)),2),
              "raster_vertical_datum_NOT_harmonized_with_PT_Cascais1938":True,
              "no_rail_3D_profile_or_station_elevation_proved":True}
def probe_wcs(outdir):
    to_es=Transformer.from_crs(4326,25830,always_xy=True)
    x,y=to_es.transform(SAMPLE_LON,SAMPLE_LAT)
    bounds=(round(x-WINDOW_HALF_M,1),round(y-WINDOW_HALF_M,1),
            round(x+WINDOW_HALF_M,1),round(y+WINDOW_HALF_M,1))
    receipts=[];result={"pilot_source_point_WGS84":[SAMPLE_LON,SAMPLE_LAT],
      "pilot_window_width_height_m":[1000,1000],
      "pilot_bbox_original_requested_UTM30_25830":bounds,
      "real_original_IGN_MDT25_GeoTIFF_acquired_and_QA":False,
      "no_approval_of_rail_station_or_rail_alignment":True,
      "source_query_receipts":receipts}
    for endpoint in WCS_ENDPOINTS:
        caps_params={"service":"WCS","request":"GetCapabilities","version":"2.0.1"}
        capurl=url_of(endpoint,caps_params)
        receipt={"source_endpoint":endpoint,"stage":"GetCapabilities"}
        try:
            raw,meta=safe_get(capurl)
            ids=parse_wcs_capabilities(raw)
            candidate=choose_candidate(ids)
            receipt.update(meta)
            receipt["reported_coverage_ids_sample"]=ids[:30]
            receipt["matching_mdt25_coverage_id"]=candidate
            receipt["status"]="WCS_2_CAPABILITY_VERIFIED"
            receipts.append(receipt)
            if not candidate:continue
            descurl=url_of(endpoint,{"service":"WCS","request":"DescribeCoverage",
                          "version":"2.0.1","coverageId":candidate})
            d_raw,d_meta=safe_get(descurl)
            try:desc=parse_wcs_description(d_raw)
            except ET.ParseError as exc:
                receipts.append({"stage":"DescribeCoverage","status":"XML_INVALID","source_endpoint":endpoint})
                continue
            receipts.append({"stage":"DescribeCoverage","status":"XML_PARSED",
                       "source_endpoint":endpoint,**d_meta,**desc})
            labels=desc["axis_labels"]
            # WCS outputs vary; probing 2 orders is permitted but restricted to 1km².
            plans=[("E","N"),("x","y")] if not labels else [
                ("E","N"),("X","Y")]
            for east,north in plans[:2]:
                req=[("service","WCS"),("request","GetCoverage"),("version","2.0.1"),
                     ("coverageId",candidate),("format","image/tiff"),
                     ("subset",east+"("+str(bounds[0])+","+str(bounds[2])+")"),
                     ("subset",north+"("+str(bounds[1])+","+str(bounds[3])+")")]
                covurl=url_of(endpoint,req)
                rec={"stage":"GetCoverage","source_endpoint":endpoint,
                     "coverage_id":candidate,"axis_parameters":[east,north],
                     "source_window_km2":1,
                     "status":"ATTEMPTED_BOUNDED_1km_original_MDT25"}
                try:
                    tif,t_meta=safe_get(covurl,MAX_TIFF_BYTES,timeout=30)
                    rec.update(t_meta)
                    qa=sanity_ground_tiff(tif)
                    rec["status"]="SOURCE_ORIGINAL_Geotiff_SHA_AND_RASTER_QA_PASS"
                    receipts.append(rec)
                    out=(outdir/"G38-IGN-CNIG-WCS-actual-MDT25-1km-Zamora-pilot.tif")
                    out.write_bytes(tif)
                    result.update({"real_original_IGN_MDT25_GeoTIFF_acquired_and_QA":True,
                       "original_source_pilot_raster_filename":out.name,
                       "original_source_pilot_raster_SHA256":t_meta["source_SHA256"],
                       "producer":endpoint,"coverage_id":candidate,
                       "verified_raster_QA":qa})
                    return result
                except (RuntimeError,ValueError) as exc:
                    rec.update({"status":"NO_VALID_ORIGINAL_RASTER_NOT_IMPUTED",
                        "error":str(exc)[:200]})
                    receipts.append(rec)
        except (RuntimeError,ValueError,ET.ParseError) as exc:
            receipt.update({"status":"SERVICE_NOT_VALIDATED","error":str(exc)[:200]})
            receipts.append(receipt)
    return result
def probe_lneg():
    # Do not confuse a successful HTTP site page with a vector WFS layer.
    # Bound read, explicitly leave geology and groundwater data *not acquired*.
    base="https://geoportal.lneg.pt/pt/dados_abertos/servicosdados/"
    ret={"producer":"LNEG","catalog_official":base,"actual_vector_geology_hydrogeology_data_acquired":False,
         "potentially_relevant_official_service_sets":["geologia_50k_harmonizada",
            "hidrogeologia_200k_vetor","SONDABASE","recursos_hidrogeologicos",
            "falhas_ativas_quaternarias"],"wfs_clip_not_yet_verified":True}
    try:
        raw,receipt=safe_get(base,1500000)
        snippet=raw.decode("utf-8",errors="ignore").lower()
        ret.update({"catalog_HTTP_status":receipt["http_status"],
                    "catalog_HTML_response_SHA256":receipt["source_SHA256"],
                    "mentions_geologia":("geologia" in snippet),
                    "mentions_hidrogeologia":("hidrogeologia" in snippet),
                    "mentions_sondagens":("sondagens" in snippet)})
    except RuntimeError as exc:ret["catalog_status"]="UNAVAILABLE_"+str(exc)[:100]
    return ret
def run(g37,outdir,jsonout,mdout):
    if g37.get("source_all_G10")!=27 or g37.get("source_all_G30")!=3:
        raise ValueError("G38_source_G37_must_hold_all30")
    if g37.get("G36_high_priority_research_options")!=13 or g37.get("source_original_DGT2m_preserved_1km_tiles")!=84:
        raise ValueError("G38_source_original_84_and_13_priority")
    if not g37.get("PIC_official_definition_and_boundary_UNRESOLVED") or g37.get("new_DGT_2m_tiles")!=0:
        raise ValueError("G38_infer_no_legal_or_new_mdt2m")
    outdir.mkdir(exist_ok=True,parents=True)
    wcs=probe_wcs(outdir)
    lneg=probe_lneg()
    result={"mission":"MN-GEO-RAIL-001","stage":"G38_live_official_source_bare_earth_1km_pilot_probes",
       "status":"ORIGINAL_MD25_SAMPLE_ACQUIRED" if wcs["real_original_IGN_MDT25_GeoTIFF_acquired_and_QA"] else
                "WCS_SOURCE_PROBED_BUT_NO_VALID_GROUND_SAMPLE",
       "G37_prior_source_verified_30_study_corridors":30,
       "G36_priority_research_corridors_for_future_real_3D":13,
       "G37_existing_verified_original_DGT2m_tiles":84,
       "G37_conditional_13_lines_not_actual_rail":True,
       "Spain_CNIG_IGN_WCS_MDT25_small_source":wcs,
       "Portugal_DGT_MDT10m_open_usable_download_status":"NOT_VERIFIED_FROM_PUBLIC_SERVICE_DO_NOT_ASSERT_DOWNLOAD",
       "Portugal_DGT_original_2m_LiDAR_product":"AVAILABLE_VIA_existing_credentialed_source_and_releases_NO_NEW_2M",
       "LNEG_original_geology_service_catalog_probe":lneg,
       "three_source_probes_not_whole_3D_alignment":True,
       "Spain_IGN_vertical_reference_vs_PT_Cascais1938_not_harmonized":True,
       "Natura2000_Art6_Alvao_Marao_groundwater_tunnel_evaluation_required":True,
       "PIC_definition_official_data_unavailable":True,
       "no_train_time_CAPEX_tunnel_length_or_rail_grade":True,
       "no_new_DGT_tiles":True,"Fxx_accepted":False,"Site_authorized":False}
    jsonout.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    md=["# G38 — Primeiro ensaio real e limitado de fontes MDT de solo nu: Portugal e Espanha",
       "","**Resultado de fonte real:** "+result["status"],
       "","O ensaio mantém 27 corredores G10 e três G30, com os 13 casos de aprofundamento do G36, e reutiliza o inventário de 84 quadrículas originais DGT2m. Não encomenda quadrículas adicionais, não escolhe a localização da estação e não afirma ter construído perfis ferroviários.",
       "","## Piloto oficial espanhol IGN/CNIG",
       "- Requisição original ao WCS público de MDT25 com GetCapabilities/DescribeCoverage e, quando o serviço expõe a cobertura adequada, GetCoverage de **1×1 km** no entorno de Zamora, fora de Sanábria. O piloto usa um ponto de teste do serviço, não geometria de alinhamento.",
       "- Origem solicitada: "+", ".join(WCS_ENDPOINTS),
       "- Estado de aquisição de dados raster com geometria, píxeis, resolução, valores, EPSG e SHA verificados: **"+("SIM" if wcs["real_original_IGN_MDT25_GeoTIFF_acquired_and_QA"] else "NÃO")+"**.",
       "- As respostas de erro, códigos HTTP e cobertura anunciada constam do JSON. Qualquer raster fornecido só é aceite depois de verificar a assinatura TIFF, número de bandas, resolução, georreferenciação e cotas numéricas.",
       "","## Terreno português",
       "- DGT confirmou disponibilidade LiDAR em GeoTIFF de **50 cm e 2 m**, mas uma especificação técnica que prevê MDT de 10 m **não comprova que exista descarga aberta operativa dessa cobertura**. Estado específico: **NÃO VERIFICADO**.",
       "- 84 quadrículas 1×1km de solo nu com resolução 2m já estão no repositório. Nenhuma foi novamente descarregada por esta execução.",
       "- A aquisição complementar de terreno será restrita às faixas 3D efetivamente escolhidas, começando pelos sete locais DGT já estudados de Vila Real e Bragança e segmento crítico Marão–Alvão.",
       "","## Geologia, hidrogeologia e condições ambientais",
       "- LNEG mantém geoportal de serviços geográficos e cartografia de geologia/hidrogeologia, incluindo SONDABASE e bases de dados hidrogeológicas; o G38 apenas testa o catálogo. **Não confundir HTTP 200 com dados vetoriais já adquiridos**.",
       "- Para uma travessia profunda Natura 2000, portais, poços, água subterrânea, habitats húmidos e geologia são fatores que carecem de caracterização; passagem sob proteção não significa dispensa de avaliação ambiental. PIC continua sem fonte oficial definida.",
       "","## Critérios para o primeiro alinhamento 3D",
       "1. Escolher 2–3 faixas com cobertura territorial e soluções Natura diferentes entre os 13 casos priorizados, sem eliminar da comparação os 30 corredores.",
       "2. Em cada nó obrigatório, usar os sete locais históricos de solo DGT2m (G23–G27) e só testar ligações horizontais contínuas que conservem raio, gradiente e possibilidade de implantação 3D.",
       "3. Unir os MDT de fontes e países apenas após confirmar **referências altimétricas**, datums e transformação vertical (Portugal Cascais 1938 vs Espanha altitudes ortométricas). Rejeitar mosaicos que ignorem offset vertical.",
       "4. Adquirir recortes delimitados da cartografia geológica/hidrogeológica LNEG e terreno de maior resolução em pontos críticos; então quantificar estruturas por cenários e incerteza, sem custos determinísticos prematuros.",
       "","**Nenhuma licença ambiental, análise custo-benefício, avaliação geotécnica ou proposta de obra é produzida pelo piloto.**"]
    mdout.write_text("\n".join(md)+"\n")
    print("G38_WCS_CAPABILITY_ID_SAMPLE",json.dumps([{"endpoint":r.get("source_endpoint"),"candidate":r.get("matching_mdt25_coverage_id"),"ids":r.get("reported_coverage_ids_sample")} for r in wcs["source_query_receipts"] if r.get("stage")=="GetCapabilities"],ensure_ascii=False),flush=True)
    print("G38_SOURCE_DIAGNOSTICS",json.dumps([{"endpoint":r.get("source_endpoint"),"step":r.get("stage"),"status":r.get("status"),"error":r.get("error")} for r in wcs["source_query_receipts"]],ensure_ascii=False),flush=True)
    print("G38_RESULT",json.dumps({"actual_IGN_CNIG_GeoTIFF_sample":wcs["real_original_IGN_MDT25_GeoTIFF_acquired_and_QA"],
         "WCS_requests":len(wcs["source_query_receipts"]),"LNEG_catalog_probe":lneg.get("catalog_HTTP_status",None),
         "no_new_DGT":True,"all30_retained":True},ensure_ascii=False),flush=True)
def main():
    a=argparse.ArgumentParser()
    for x in ("g37","outdir","json","markdown"):a.add_argument("--"+x,required=True,type=Path)
    args=a.parse_args()
    run(json.loads(args.g37.read_text()),args.outdir,args.json,args.markdown)
if __name__=="__main__":main()
