#!/usr/bin/env python3
"""G40: source-based 25m bare-earth Spanish samples in FOUR DIFFERENT route
research hypotheses: G10 P1-2-1 plus ALL three G30. Do not transform a 2km
G10/G30 research grid into a designed rail alignment.

Exact original official IGN/CNIG WCS elevation25830_25 1km TIFF only;
fail-closed on malformed TIFF, provenance, CRS, elevations, geographic/source
border; unknowns never interpolated. Keep all 30 original routes in report.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sys,time,zipfile
from pathlib import Path
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import shape,LineString,Point
from shapely.ops import transform
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g38_1km_original_IGN_ground_source_probe import safe_get,url_of,sanity_ground_tiff,MAX_TIFF_BYTES
from geo_rail_g37_terrain_data_acquisition_gate import source_boundary
from rasterio.io import MemoryFile

EP="https://servicios.idee.es/wcs-inspire/mdt"
COVERAGE="Elevacion25830_25"
FOUR=("P1-2-1","G30-avoid_surface_overlap","G30-potential_deep_tunnel","G30-geographic_diversity")
DISTANCES_KM=tuple(range(15,56,5))
MIN_ES_BORDER_DISTANCE_M=1500
MAX_RAW_REQUESTS=36
XFORM=Transformer.from_crs(4326,25830,always_xy=True)
BACK=Transformer.from_crs(25830,4326,always_xy=True)
X_UTM_TO_PT=Transformer.from_crs(25830,3763,always_xy=True)
def validate(g10,g30,g36,g39):
    fs=g10.get("features",[])+g30.get("features",[])
    ids=[f["properties"]["id"] for f in fs]
    expected={"P"+str(i)+"-"+str(j)+"-"+str(k) for i in (1,2,3) for j in (1,2,3) for k in (1,2,3)}
    expected|={ "G30-"+x for x in ("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity") }
    if len(ids)!=30 or set(ids)!=expected:raise ValueError("G40_30_original_source_route_ledger_required")
    if not all(r in ids for r in FOUR):raise ValueError("G40_four_distinct_types_missing")
    if g36.get("source_all_original_G10_count")!=27 or g36.get("source_all_original_G30_count")!=3 or g36.get("rows_n")!=90:
        raise ValueError("G40_G36_90_comparative_speeds_required")
    if g39.get("validated_original_WCS_MDT25_source_points")!=13 or g39.get("requested_source_points")!=13 or g39.get("original_WCS_failed_points_not_imputed")!=0:
        raise ValueError("G40_G39_original_terrain_harmonization_not_observed")
    if not g39.get("PT_ES_vertical_reference_harmonization_NOT_PROVEN"):raise ValueError("G40_vertical_datum_not_proven")
    return {f["properties"]["id"]:f for f in fs}
def points(g10,g30,g36,g39,countryraw):
    features=validate(g10,g30,g36,g39)
    pt,es,bmeta=source_boundary(countryraw)
    out=[];profiles={}
    for key in FOUR:
        coords=features[key]["geometry"]["coordinates"]
        line=LineString([XFORM.transform(*ll) for ll in coords])
        if not (220_000<=line.length<=480_000):raise ValueError("G40_study_line_length_incoherent")
        profiles[key]=line
        for distance in DISTANCES_KM:
            p=line.interpolate(line.length-distance*1000)
            x,y=p.x,p.y
            px,py=X_UTM_TO_PT.transform(x,y)
            native=Point(px,py)
            lon,lat=BACK.transform(x,y)
            if not(-6.95<lon<-5.2 and 40.9<lat<42.4):
                raise ValueError("G40_current_position_outside_northwest_Spain_research")
            # Need original source generalised Spain inclusion + buffer to avoid border
            eligible=es.contains(native) and es.boundary.distance(native)>MIN_ES_BORDER_DISTANCE_M
            out.append({"option_id":key,"source_family":"G30" if key.startswith("G30-") else "G10",
                "study_grid_distance_from_Zamora_end_km":-distance,
                "original_study_grid_sample_WGS84":[round(lon,7),round(lat,7)],
                "original_study_grid_sample_UTM30":[round(x,3),round(y,3)],
                "generalized_GISCO_2024_ES_interior_1p5km":eligible,
                "distance_to_GISCO_ES_boundary_km":round(es.boundary.distance(native)/1000,3),
                "original_IGN_25m_elevation_m":None,
                "source_status":"ELIGIBLE_FOR_SMALL_SOURCE_QUERY" if eligible else "GENERALIZED_BORDER_CANNOT_ISSUE_QUERY",
                "no_rail_3D_earthworks_or_operational_grade":True})
    if len(out)!=len(FOUR)*len(DISTANCES_KM):raise ValueError("G40_not_four_research_routes_same_distances")
    # report pairwise diversity; no route is declared physically feasible
    spread=[]
    for d in DISTANCES_KM:
        sub=[r for r in out if r["study_grid_distance_from_Zamora_end_km"]==-d]
        xy={r["option_id"]:r["original_study_grid_sample_UTM30"] for r in sub}
        pairs={a+"|"+b:round(math.dist(xy[a],xy[b])/1000,3)
            for i,a in enumerate(FOUR) for b in FOUR[i+1:]}
        spread.append({"km_before_Zamora_study_endpoint":d,"pairwise_original_study_grid_sep_km":pairs,
           "max_sep_km":max(pairs.values()),"min_sep_km":min(pairs.values())})
    return out,spread,bmeta
def get_tile(row):
    x,y=row["original_study_grid_sample_UTM30"]
    bbox=[round(x-500,2),round(y-500,2),round(x+500,2),round(y+500,2)]
    params=[("service","WCS"),("request","GetCoverage"),("version","2.0.1"),
       ("coverageId",COVERAGE),("format","image/tiff"),
       ("subset",f"X({bbox[0]},{bbox[2]})"),("subset",f"Y({bbox[1]},{bbox[3]})")]
    b,receipt=safe_get(url_of(EP,params),max_bytes=MAX_TIFF_BYTES,timeout=25)
    qa=sanity_ground_tiff(b)
    if qa["source_crs"]!="EPSG:25830" or qa["resolution"]!=[25.0,25.0]:
        raise ValueError("G40_wrong_producer_25m_native_geotiff")
    minx,miny,maxx,maxy=qa["geographic_source_bounds_as_native_CRS"]
    if not(minx<=x<maxx and miny<y<=maxy):
        raise ValueError("G40_tif_does_not_cover_research_grid_reference")
    if not(700<maxx-minx<1300 and 700<maxy-miny<1300):
        raise ValueError("G40_wrong_1km_bounded_original_source_request")
    with MemoryFile(b) as f:
        with f.open() as src:
            z=next(src.sample([(x,y)],masked=True))[0]
            if np.ma.is_masked(z) or not np.isfinite(z):
                raise ValueError("G40_original_25m_pixel_missing")
            alt=float(z)
    if not -200<alt<5000:raise ValueError("G40_elevation_invalid")
    row.update({"original_IGN_25m_elevation_m":round(alt,2),
      "source_status":"ACTUAL_OFFICIAL_WCS_GEOtiff_QA_PASS",
      "source_original_SHA256":receipt["source_SHA256"],
      "source_raw_bytes":len(b),"source_raster_dimensions":qa["dimensions"],
      "source_verified_UTM30_bounds":qa["geographic_source_bounds_as_native_CRS"],
      "source_IGN_COVERAGE":COVERAGE,
      "original_ground_profile_NOT_engineered_rail_rasante":True})
    return b
def work(g10,g30,g36,g39,countryraw,outdir,outjson,outcsv,outmd,outpng,outmap,outzip):
    rows,spread,bmeta=points(g10,g30,g36,g39,countryraw)
    tofetch=[r for r in rows if r["generalized_GISCO_2024_ES_interior_1p5km"]]
    if len(tofetch)>MAX_RAW_REQUESTS:raise ValueError("G40_too_many_source_calls")
    outdir.mkdir(parents=True,exist_ok=True)
    file_bytes={};cache={}
    for i,r in enumerate(tofetch):
        xy=tuple(r["original_study_grid_sample_UTM30"])
        # Deduplicate only physically identical actual source sample coordinates.
        # 2D G30 avoid_surface and potential_deep_tunnel can share the same
        # eastern leg; no repeated WCS transfer, yet retain both scenarios.
        key=tuple(round(float(v),1) for v in xy)
        prior=cache.get(key)
        try:
            if prior is not None and math.dist(xy,prior["xy"])<=0.08:
                r.update({field:prior["record"][field] for field in
                    ("original_IGN_25m_elevation_m","source_status",
                     "source_original_SHA256","source_raw_bytes",
                     "source_raster_dimensions","source_verified_UTM30_bounds",
                     "source_IGN_COVERAGE")})
                # Prior original sample point identical within centimetres;
                # validate that the actual original TIFF still covers the point
                # and SAMPLE the pixel anew (not copying another elevation).
                b=prior["original_tif"]
                with MemoryFile(b) as mem:
                    with mem.open() as ds:
                        z=next(ds.sample([xy],masked=True))[0]
                        if np.ma.is_masked(z) or not np.isfinite(z):
                            raise ValueError("G40_identical_location_reused_TIFF_NoData")
                        r["original_IGN_25m_elevation_m"]=round(float(z),2)
                r["source_original_WCS_query_reused_same_ground_position"]=True
                r["source_reused_from_option_id"]=prior["record"]["option_id"]
            else:
                b=get_tile(r)
                name=f"IGN_original_G40_{i:02d}_{r['option_id']}.tif"
                file_bytes[name]=b
                cache[key]={"xy":xy,"record":dict(r),"original_tif":b}
                r["source_original_WCS_query_reused_same_ground_position"]=False
        except (RuntimeError,ValueError,OSError) as exc:
            r.update({"source_status":"SOURCE_FAILED_UNAVAILABLE_NOT_INTERPOLATED",
                "source_error_type":type(exc).__name__,"source_error":str(exc)[:180],
                "original_IGN_25m_elevation_m":None})
        if i<len(tofetch)-1 and not r.get("source_original_WCS_query_reused_same_ground_position"):
            time.sleep(.18)
        print(f"G40_ORIGINAL_DEM {i+1}/{len(tofetch)} {r['option_id']} {r['study_grid_distance_from_Zamora_end_km']}km {r['source_status']} {'reused' if r.get('source_original_WCS_query_reused_same_ground_position') else 'WCS'}",flush=True)
    with zipfile.ZipFile(outzip,"w",zipfile.ZIP_STORED) as z:
        for name,b in file_bytes.items():z.writestr(name,b)
        z.writestr("G40-real-IGN-source-attribution.txt",
           "Original IGN/CNIG WCS 2.0.1 Elevacion25830_25, 25m EPSG:25830. "+
           "Research-grid points only, no engineering railway, not statutory source for permissions.\n")
    sample_terrain=[]
    for key in FOUR:
        r=sorted((q for q in rows if q["option_id"]==key),
                 key=lambda q:q["study_grid_distance_from_Zamora_end_km"])
        adjacent=[]
        for a,b in zip(r,r[1:]):
            va,vb=a["original_IGN_25m_elevation_m"],b["original_IGN_25m_elevation_m"]
            if va is None or vb is None:continue
            # 5km chainage of research grid, NOT horizontal straight distance,
            # so this is mathematical source-grid terrain rise, not track design.
            adjacent.append(round((vb-va)/(b["study_grid_distance_from_Zamora_end_km"]-a["study_grid_distance_from_Zamora_end_km"]),3))
        sample_terrain.append({"option_id":key,
           "original_source_points_valid":sum(q["source_status"]=="ACTUAL_OFFICIAL_WCS_GEOtiff_QA_PASS" for q in r),
           "original_source_points_geographical":len(r),
           "sample_height_range_m":([min(q["original_IGN_25m_elevation_m"] for q in r if q["original_IGN_25m_elevation_m"] is not None),
                                     max(q["original_IGN_25m_elevation_m"] for q in r if q["original_IGN_25m_elevation_m"] is not None)]
                                     if any(q["original_IGN_25m_elevation_m"] is not None for q in r) else None),
           "source_ground_terrain_adjacent_5km_step_m_per_km_NOT_railway":adjacent})
    doc={"mission":"MN-GEO-RAIL-001","stage":"G40_four_original_P1_2_1_G30_variants_IGN_25m_terrain_profiles",
       "all_30_portfolio_retained":True,"all_G10_count":27,"all_G30_count":3,
       "selected_four_research_lattice_lines_not_rail_design":list(FOUR),
       "step_spacing_in_original_research_grid_chainage_km":5,
       "study_distances_from_Zamora_end_km":list(DISTANCES_KM),
       "original_geo_points":len(rows),"official_ES_1p5km_border_interior_eligible":len(tofetch),
       "actual_IGN_source_original_TIFF_verified_count":len(file_bytes),
       "original_source_terrain_locations_measured_even_if_reused":sum(r["source_status"]=="ACTUAL_OFFICIAL_WCS_GEOtiff_QA_PASS" for r in rows),
       "source_WCS_duplicate_queries_avoided":sum(r.get("source_original_WCS_query_reused_same_ground_position",False) for r in rows),
       "G30_avoid_vs_tunnel_eastern_2D_same_ground_not_two_independent_east_solutions":all(x["pairwise_original_study_grid_sep_km"]["G30-avoid_surface_overlap|G30-potential_deep_tunnel"]<.001 for x in spread),
       "origin_geography_and_research_route_diversity":spread,
       "original_Eurostat_2024_GISCO_PT_ES_metadata":bmeta,
       "sources_primary":"IGN-CNIG WCS Elevacion25830_25 actual original GeoTIFF EPSG25830 25m",
       "measured_terrain_only_four_study_profiles":sample_terrain,
       "source_original_25m_samples_and_sha256":rows,
       "no_non_sourced_samples_interpolated":True,
       "not_harmonized_PT_ES_vertical_datum":True,
       "no_eng_rail_line_clothoids_curves_station_platform":True,
       "no_tunnel_bridge_cost_timetable_assessed":True,
       "Natura2000_tunnel_groundwater_uncertainty":True,
       "PIC_official_source_UNRESOLVED":True,"no_new_DGT_tiles":True,
       "Fxx_accepted":False,"Site_authorized":False}
    outjson.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n")
    cols=("option_id","study_grid_distance_from_Zamora_end_km","original_study_grid_sample_WGS84",
         "original_IGN_25m_elevation_m","source_status","source_original_SHA256",
         "distance_to_GISCO_ES_boundary_km")
    with outcsv.open("w",newline="",encoding="utf-8-sig") as f:
        wr=csv.DictWriter(f,fieldnames=cols,delimiter=";");wr.writeheader()
        for r in rows:wr.writerow({x:r.get(x) for x in cols})
    fig,ax=plt.subplots(figsize=(11,6),layout="constrained")
    style={"P1-2-1":"#2a6377","G30-avoid_surface_overlap":"#a36c26",
        "G30-potential_deep_tunnel":"#8057a0","G30-geographic_diversity":"#367a58"}
    for key in FOUR:
        sub=sorted((r for r in rows if r["option_id"]==key),
                   key=lambda q:q["study_grid_distance_from_Zamora_end_km"])
        x=[r["study_grid_distance_from_Zamora_end_km"] for r in sub]
        v=[r["original_IGN_25m_elevation_m"] for r in sub]
        ax.plot(x,[t if t is not None else np.nan for t in v],marker="o",lw=1.6,
                color=style[key],label=key)
    ax.set_xlabel("km de progressiva inversa até à extremidade de Zamora (malha de estudo, não via)")
    ax.set_ylabel("Cota do terreno MDT25 (m; datum espanhol)")
    ax.set_title("G40 · 4 hipóteses geográficas · terreno original IGN/CNIG 25m",loc="left",fontsize=12)
    ax.grid(alpha=.2);ax.legend(fontsize=8);fig.savefig(outpng,dpi=160,bbox_inches="tight");plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,7),layout="constrained")
    for key in FOUR:
        sub=sorted((r for r in rows if r["option_id"]==key),
                   key=lambda q:q["study_grid_distance_from_Zamora_end_km"])
        lons=[r["original_study_grid_sample_WGS84"][0] for r in sub]
        lats=[r["original_study_grid_sample_WGS84"][1] for r in sub]
        ax.plot(lons,lats,marker=".",lw=1.3,c=style[key],label=key)
    ax.set_xlabel("Longitude ETRS89/WGS84 aprox.");ax.set_ylabel("Latitude")
    ax.set_title("G40 · pontos de amostragem, não alinhamentos ferroviários",loc="left",fontsize=11)
    ax.grid(alpha=.18);ax.legend(fontsize=8);fig.savefig(outmap,dpi=160,bbox_inches="tight");plt.close(fig)
    md=["# G40 — Quatro alternativas, terreno original IGN MDT25, amostragem transfronteiriça do setor espanhol",
       "","Esta etapa **mantém as 30 alternativas na carteira** e testa terreno de solo nu espanhol em quatro variantes representativas, todas com a mesma distância de estudo à extremidade de Zamora. O estudo não contém uma rasante ferroviária 3D, terreno contínuo português, túneis ou preços.",
       "","## Quantidades reais",
       f"- Amostras geográficas de investigação: **{len(rows)}** (4 × {len(DISTANCES_KM)}).",
       f"- Pontos interiores de Espanha com pelo menos 1,5 km de margem da fronteira GISCO generalizada: **{len(tofetch)}**.",
       f"- GeoTIFF originais WCS únicos adquiridos e validados: **{len(file_bytes)}**; posições medidas (incluindo reutilizações exatas): **{sum(r['source_status']=='ACTUAL_OFFICIAL_WCS_GEOtiff_QA_PASS' for r in rows)}**.",
       f"- Consultas repetidas evitadas devido à coincidência espacial de geometrias: **{sum(r.get('source_original_WCS_query_reused_same_ground_position',False) for r in rows)}**.",
       f"- Fonte: {EP}, cobertura **{COVERAGE}**, sistema EPSG:25830, píxeis 25m.",
       "","## Diferença espacial entre variantes (quatro linhas de grelha, não projeto)",
       "","| km antes de Zamora | Separação mínima entre duas linhas (km) | Separação máxima (km) |",
       "|---:|---:|---:|"]
    for r in spread:md.append(f"| {r['km_before_Zamora_study_endpoint']} | {r['min_sep_km']} | {r['max_sep_km']} |")
    md+=["","## Perfil por alternativa",
       "","| Alternativa | Pontos originais válidos | Intervalo altimétrico em pontos válidos (m) |",
       "|---|---:|---|"]
    for r in sample_terrain:
        md.append(f"| {r['option_id']} | {r['original_source_points_valid']} | {r['sample_height_range_m'] if r['sample_height_range_m'] is not None else 'N/D'} |")
    md+=["","**Limite crítico:** os gradientes extraídos das cotas de amostras de solo nu não são gradientes ferroviários. Os eixos de grelha podem convergir na região espanhola; se a separação for pequena, os quatro perfis não constituem quatro soluções independentes nesse setor. Nada se conclui sobre custo ou benefício de túnel.",
       "","## Próximos dados a obter",
       "- Terreno contínuo de solo nu nas aproximações ferroviárias reais aos sete locais DGT2m já estudados, e faixas PT selecionadas após testar geometria de curvas e rasantes.",
       "- Terreno espanhol em faixas com verdadeira diferenciação entre alternativas (não repetir pedidos em geometrias coincidentes).",
       "- Catálogos LNEG de falhas, cartas geológicas/hidrogeológicas e sondagens; verificar dados e limites realmente acedidos, especialmente Marão–Alvão.",
       "- Conferir datum altimétrico IGN–DGT antes de qualquer mosaico transfronteiriço; não extrapolar os 25m do IGN para resolução DGT2m.",
       "- Continuar comparação integral dos 30 por custos, tempo, proteção Natura 2000 e PIC — sem afirmar viabilidade ou autorização.",
       "","**Sem novas quadrículas DGT, Fxx ou Site.**"]
    outmd.write_text("\n".join(md)+"\n")
    print("G40_RESULT",json.dumps({"sample_rows":len(rows),"eligible":len(tofetch),"actual_original_GeoTIFF":len(file_bytes),
        "reused_source_same_exact_grid_point":sum(r.get("source_original_WCS_query_reused_same_ground_position",False) for r in rows),
        "profile_comparison":sample_terrain,
        "spread_at_15_55km":spread,
        "no_real_railway_3D":True},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for key in ("g10","g30","g36","g39","country","outdir","json","csv","markdown","plot","map","zip"):
        p.add_argument("--"+key,required=True,type=Path)
    a=p.parse_args()
    work(*[json.loads(getattr(a,k).read_text()) for k in ("g10","g30","g36","g39")],
        a.country.read_bytes(),a.outdir,a.json,a.csv,a.markdown,a.plot,a.map,a.zip)
if __name__=="__main__":main()
