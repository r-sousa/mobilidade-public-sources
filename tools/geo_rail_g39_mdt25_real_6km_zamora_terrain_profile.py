#!/usr/bin/env python3
"""G39 exact original IGN MDT25 sampled at 500m steps over 6km of original
G10 P2-2-1 eastern geographic *research GRID*, not an engineered railway.
Source 25m bare-earth TIFF from official GetCoverage X,Y in UTM 25830. Every
sample requires unique source native TIFF verified in space, CRS, pixel, SHA.
No interpolation across failed source; no travel time, rail gradient or costs.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sys,time,zipfile
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rasterio
from rasterio.io import MemoryFile
from shapely.geometry import LineString
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g38_1km_original_IGN_ground_source_probe import (
    safe_get,url_of,sanity_ground_tiff,MAX_TIFF_BYTES,
)
EP="https://servicios.idee.es/wcs-inspire/mdt"
SOURCE_COVERAGE="Elevacion25830_25"
ROUTE_ID="P2-2-1"
CHUNK_M=1000.
SAMPLE_M=500.
SECTOR_M=6000.
NPTS=int(SECTOR_M/SAMPLE_M)+1
def samples(g10,g36,g38):
    features=g10["features"]
    ids={f["properties"]["id"] for f in features}
    if len(features)!=27 or ROUTE_ID not in ids:raise ValueError("G39_requires_original_G10_27")
    if (g36.get("source_all_original_G10_count")!=27 or g36.get("source_all_original_G30_count")!=3
        or ROUTE_ID not in [q["option_id"] for q in g36.get("review_priority_NOT_viability_OR_final_selection",[]) if q["next_engineering_work_priority_only"]]):
        raise ValueError("G39_G36_priority_30_contract")
    if not g38["Spain_CNIG_IGN_WCS_MDT25_small_source"]["real_original_IGN_MDT25_GeoTIFF_acquired_and_QA"]:
        raise ValueError("G39_previous_genuine_original_raster_not_verified")
    if g38["Spain_CNIG_IGN_WCS_MDT25_small_source"]["coverage_id"]!=SOURCE_COVERAGE:
        raise ValueError("G39_original_WCS_source_coverage_drift")
    f=next(f for f in features if f["properties"]["id"]==ROUTE_ID)
    to_utm=Transformer.from_crs(4326,25830,always_xy=True)
    xy=[to_utm.transform(*point) for point in f["geometry"]["coordinates"]]
    line=LineString(xy)
    if line.length<SECTOR_M+100000:raise ValueError("G39_original_route_unexpected_length")
    positions=[]
    for i in range(NPTS):
        chain=line.length-SECTOR_M+i*SAMPLE_M
        p=line.interpolate(chain)
        x,y=float(p.x),float(p.y)
        lon,lat=Transformer.from_crs(25830,4326,always_xy=True).transform(x,y)
        # Zamora surrounding, not Sanabria; FAIL if original route source not here
        if not (-6.2<lon<-5.3 and 41.15<lat<41.85):
            raise ValueError("G39_eastern_original_route_not_Zamora_sector")
        positions.append({"distance_from_source_endpoint_km":round((chain-line.length)/1000,3),
             "east_25830_m":round(x,3),"north_25830_m":round(y,3),
             "lon":round(lon,7),"lat":round(lat,7)})
    return positions
def acquire(row):
    x,y=row["east_25830_m"],row["north_25830_m"]
    bb=[round(x-500,2),round(y-500,2),round(x+500,2),round(y+500,2)]
    params=[("service","WCS"),("request","GetCoverage"),("version","2.0.1"),
            ("coverageId",SOURCE_COVERAGE),("format","image/tiff"),
            ("subset",f"X({bb[0]},{bb[2]})"),("subset",f"Y({bb[1]},{bb[3]})")]
    raw,meta=safe_get(url_of(EP,params),MAX_TIFF_BYTES,timeout=30)
    qa=sanity_ground_tiff(raw)
    if qa["source_crs"]!="EPSG:25830" or qa["resolution"]!=[25.0,25.0]:
        raise ValueError("G39_not_original_correct_IGN_native_25m")
    extent=qa["geographic_source_bounds_as_native_CRS"]
    if not (extent[0]<=x<extent[2] and extent[1]<y<=extent[3]):
        raise ValueError("G39_original_raster_not_cover_requested_point")
    if not(800<=extent[2]-extent[0]<=1200 and 800<=extent[3]-extent[1]<=1200):
        raise ValueError("G39_original_WCS_tile_dimensions_unexpected")
    with MemoryFile(raw) as mem:
        with mem.open() as ds:
            h=next(ds.sample([(x,y)],masked=True))[0]
            if np.ma.is_masked(h) or not math.isfinite(float(h)):
                raise ValueError("G39_requested_original_source_ground_pixel_NoData")
            val=float(h)
    row.update({"official_IGN_MD25_original_sample_elevation_m":round(val,3),
           "source_original_tif_sha256":meta["source_SHA256"],
           "source_byte_count":meta["bytes"],
           "source_native_25m_raster_valid_pixels":qa["pixels_valid"],
           "source_raster_bounds_UTM30":extent,
           "source_request_UTM30_bbox_m":bb,
           "source_status":"ORIGINAL_WCS_GROUND_SAMPLE_QA_VALID",
           "not_operational_rail_design_gradient_or_cross_section":True})
    return raw
def run(g10,g36,g38,outdir,jpath,cpath,mdpath,pngpath,zpath):
    rows=samples(g10,g36,g38)
    assert len(rows)==13
    outdir.mkdir(parents=True,exist_ok=True)
    good=0;fail=0;raws=[]
    for i,row in enumerate(rows):
        try:
            raw=acquire(row)
            raws.append((i,raw))
            good+=1
        except (RuntimeError,ValueError,OSError) as exc:
            row.update({"source_status":"SOURCE_UNAVAILABLE_NO_ELEVATION_IMPUTATION",
                "source_error":str(exc)[:180],
                "official_IGN_MD25_original_sample_elevation_m":None,
                "not_operational_rail_design_gradient_or_cross_section":True})
            fail+=1
        if i<12:time.sleep(.25)
        print(f"G39_GENUINE_SOURCE_TILE {i+1}/13 {row['source_status']}",flush=True)
    # Preserve ORIGINAL bytes: per-request hash in JSON and exact TIFF in ZIP
    with zipfile.ZipFile(zpath,"w",compression=zipfile.ZIP_STORED) as z:
        for i,b in raws:
            z.writestr(f"IGN_MDT25_actual_source_UTM30_sector_point_{i:02d}.tif",b)
        z.writestr("G39-source-original-stated-license-and-QA.txt",
          "Original IGN/CNIG WCS 2.0.1 coverage Elevacion25830_25, EPSG:25830, 25m.\n"+
          "13 bounded 1km² source TIFF requests along original study lattice line P2-2-1.\n"+
          "No original data fabricated. Original licence per producer; attribution IGN/CNIG.\n")
    goodvalues=[r["official_IGN_MD25_original_sample_elevation_m"] for r in rows]
    segs=[]
    for i in range(12):
        a,b=goodvalues[i],goodvalues[i+1]
        if a is not None and b is not None:
            grade=round(1000*(b-a)/SAMPLE_M,2)
            segs.append({"source_ground_point_index_pair":[i,i+1],
               "sampled_ground_grade_permille_NOT_train_track":grade,
               "terrain_source_gradient_ABS_exceeds_18permille":abs(grade)>18,
               "terrain_source_gradient_ABS_exceeds_25permille":abs(grade)>25})
        else:
            segs.append({"source_ground_point_index_pair":[i,i+1],
               "sampled_ground_grade_permille_NOT_train_track":None,
               "terrain_source_gradient_ABS_exceeds_18permille":None,
               "terrain_source_gradient_ABS_exceeds_25permille":None})
    doc={"mission":"MN-GEO-RAIL-001",
       "stage":"G39_original_CNIG_MDT25_six_km_13_ground_samples_along_G10_research_grid",
       "G10_27_plus_G30_3_complete_portfolio_still_preserved":True,
       "one_study_reference_line_not_final_selection":"P2-2-1",
       "source_route_P2_2_1_original_2km_grid_NOT_projected_railway":True,
       "requested_source_points":len(rows),"validated_original_WCS_MDT25_source_points":good,
       "original_WCS_failed_points_not_imputed":fail,
       "physical_sample_interval_m":SAMPLE_M,"study_sector_length_km":6,
       "Spanish_IGN_original_bare_earth_resolution_m":25,
       "source_coverage_id":SOURCE_COVERAGE,"source_WCS_url":EP,
       "all_13_original_source_TIFF_bytes_preserved_in_zip_if_valid":True,
       "source_point_sampled_values":rows,
       "consecutive_sampled_ground_source_gradients_NOT_railway":segs,
       "3D_rail_profile_candidate_geometry_not_yet_built":True,
       "PT_ES_vertical_reference_harmonization_NOT_PROVEN":True,
       "no_new_DGT_2m_tiles":True,"PIC_Natura_Alvao_still_not_approved":True,
       "cost_tunnel_viaduct_train_time_NOT_CALCULATED":True,
       "Fxx_accepted":False,"Site_authorized":False}
    jpath.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n")
    with cpath.open("w",encoding="utf-8-sig",newline="") as f:
        fields=("distance_from_source_endpoint_km","lon","lat","east_25830_m","north_25830_m",
                "official_IGN_MD25_original_sample_elevation_m","source_original_tif_sha256",
                "source_status")
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
        for r in rows:w.writerow({k:r.get(k) for k in fields})
    fig,ax=plt.subplots(figsize=(10,5),layout="constrained")
    x=[z["distance_from_source_endpoint_km"] for z in rows]
    y=[float(v) if v is not None else np.nan for v in goodvalues]
    ax.plot(x,y,marker="o",lw=2)
    ax.grid(alpha=.24);ax.set_xlabel("Distância até à extremidade oriental da linha G10 P2-2-1 (km; eixo de grelha, NÃO ferrovia)")
    ax.set_ylabel("Cota MDT25 IGN/CNIG (m; datum espanhol ainda não harmonizado)")
    ax.set_title(f"G39 · Perfil de terreno de solo nu fonte original, setor final de {SECTOR_M/1000:g}km · {good}/{NPTS} pontos",loc="left",fontsize=11)
    fig.savefig(pngpath,dpi=160,bbox_inches="tight");plt.close(fig)
    txt=["# G39 — Primeira amostragem longitudinal de MDT de solo nu IGN/CNIG na região de Zamora",
       "",f"Original de **25m**, 13 solicitações independentes de 1km² ao serviço WCS IGN/CNIG (Elevacion25830_25), ao longo dos **últimos 6km da linha exploratória P2-2-1** da G10. Dos 13 pontos foram validados **{good}**, com **{fail} falhas sem preencher valores**.",
       "","**Isto não é rasante de ferrovia nem eixo de obra.** A poligonal da grelha G10 de 2km não tem curvas de transição, cota de estação, túneis, pontes, gradientes de construção, superelevação, velocidade de exploração nem estudo geológico.",
       "","## Medições originais de solo nu (25m)",
       "","| Distância até à extremidade de Zamora | Cota MDT25 nativa (m) | Original TIFF auditado |",
       "|---:|---:|---|"]
    for row in rows:
        txt.append(f"| {row['distance_from_source_endpoint_km']:.1f} km | {row.get('official_IGN_MD25_original_sample_elevation_m') if row.get('official_IGN_MD25_original_sample_elevation_m') is not None else 'N/D'} | {row['source_status']} |")
    txt+=["","## Decisão para aquisição seguinte",
       "O método fica replicável através do WCS oficial com blocos de 1km e SHA individual. Para sair dos perfis de solo nu e projetar uma ferrovia falta:",
       "1. Segmentar as alternativas G10/G30 num eixo ferroviário horizontal de curvas/retas e transições compatível com velocidades 160/200/250.",
       "2. Cobertura contínua de MDT de solo nu suficientemente densa no Portugal e Espanha (não só 13 pontos próximos de Zamora), com NoData e referências altimétricas PT/ES harmonizadas.",
       "3. Retomar as sete posições previamente avaliadas de estação em Vila Real e Bragança e criar aproximações reais com rasantes e plataformas.",
       "4. Geologia/hidrogeologia, Natura 2000, PIC, portais de túnel, acessos e infraestruturas em conflito antes de quantificar estruturas/custos.",
       "","Sem Fxx/Site; sem novas quadrículas DGT2m.",""]
    mdpath.write_text("\n".join(txt))
    print("G39_RESULT",json.dumps({"valid_original_IGN_ground_samples":good,
       "missing":fail,"samples":len(rows),"sample_terrain_minmax_m":[min(v for v in goodvalues if v is not None),max(v for v in goodvalues if v is not None)] if good else None,
       "terrain_segment_18permille_exceed_count":sum(q["terrain_source_gradient_ABS_exceeds_18permille"] is True for q in segs),
       "source_rail_3D_ready":False},ensure_ascii=False),flush=True)
def main():
    a=argparse.ArgumentParser()
    for key in ("g10","g36","g38","outdir","json","csv","markdown","plot","zip"):
        a.add_argument("--"+key,required=True,type=Path)
    p=a.parse_args()
    run(*[json.loads(getattr(p,k).read_text()) for k in ("g10","g36","g38")],
        p.outdir,p.json,p.csv,p.markdown,p.plot,p.zip)
if __name__=="__main__":main()
