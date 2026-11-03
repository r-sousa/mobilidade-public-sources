#!/usr/bin/env python3
"""G57 source DGT2m actual original bare-earth after G56 recovered 200kmh
sampled horizontal-radius candidate geometries for BR3 BR4 (G30 diversity).

Uses EXACT G56 new sample XY, not any G54 historical failed geometry,
resamples only already acquired original public GitHub-release DGT2m TIFFs.
2×121 positions at 25m along 3km centered on real previous physical BR
station, original native 2m pixels, SHA256 original plus tile EPSG3763,
500×500 pixels 2m and original NoData. A true 3D mathematical grade z(s)
at 12.5/15 only if ALL native ground source samples valid. Missing stays null.
Station rotated BR3 => road access must be rechecked (G25 previous time
not valid for new orientation).

No actual railway 200kmh guarantee, 3D full route, tunnel/bridge, CAPEX,
station land access approval, groundwater/PIC/Natura EIA or new DGT purchase.
"""
from __future__ import annotations
import argparse,json,math,csv,subprocess,sys
from pathlib import Path
import numpy as np
import rasterio
from shapely.geometry import LineString,Point
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g47_original_DGT2m_station_3km_ground import sha,asset_map
from geo_rail_g48_real_source_5grade_traffic_station_recalibration import minimax_grade_envelope
REPO="r-sousa/mobilidade-public-sources"
SITES=("BR3","BR4")
def prepare(g56,g37):
    if not g56["original_full30_research_study_alternatives_preserved"] or
       not g56["old_G45_original_BR3_BR4_200_no_sampled_radius_solution"]:
        raise ValueError("G57_original_G56_full30_old200_fail_source_required")
    if g56["no_new_original_DGT2m_source_ground_samples_for_changed_XY"] is not True:
        raise ValueError("G57_G56_source_ground_not_yet_acquired_required")
    old={tuple(v) for v in g37["source_84_original_DGT_tile_ids_in_PTTM06"]}
    if len(old)!=84:raise ValueError("G57_original_DGT84_source")
    by={p["station_id"]:p for p in g56["two_sites_three_speeds_source_2D_curvature_screen"]}
    if set(by)!=set(SITES):raise ValueError("G57_only_two_original_Braganca_sites")
    cases=[];needed=set()
    for sid in SITES:
        item=by[sid]["per_speed"]["200"]
        if not item["horizontal_2D_curvature_sampled_candidate_found"]:
            cases.append({"site_id":sid,"status":"G56_EXTENDED_GEOMETRY_NOT_FOUND","samples":[]})
            continue
        info=item["G56_best_source_research_geometry_or_null"]
        if not info or info["source_original_route_id"]!="G30-geographic_diversity":
            raise ValueError("G57_only_source_G30_real_diversity_candidate")
        station=Point(info["source_original_station_XY_PT_TM06"])
        path=LineString(info["source_geometry"]["sampled_QA_path_PT_TM06"])
        if path.distance(station)>5:raise ValueError("G57_station_old_phys_point_not_on_new_G56")
        center=path.project(station)
        if min(center,path.length-center)<1500:raise ValueError("G57_new_G56_3km_station_scope_incomplete")
        points=[]
        for i in range(121):
            p=path.interpolate(center-1500+i*25)
            tile=(math.floor(p.x/1000)+200,math.floor(p.y/1000)+301)
            points.append({"relative_chainage_m":i*25-1500,
                "XY_original_G56_EPSG3763":[round(p.x,3),round(p.y,3)],
                "DGT_native_tile_ColRow":list(tile)})
            if tile in old:needed.add(tile)
        cases.append({"site_id":sid,"status":"G56_200kmh_CURVATURE_RESEARCH_XY_AVAILABLE",
          "source_G56_original_station_heading_class":info["heading_source_class"],
          "source_G56_original_sampled_Rmin_m":info["source_sampled_2D_radius_m"],
          "source_G56_new_station_axis_road_access_NOT_VERIFIED":
             info["heading_source_class"]!="ORIGINAL_G25_STATION_HEADING_REUSED",
          "source_new_connected_2D_length_m":info["source_geometry"]["total_connected_2D_centerline_length_m"],
          "original_site_XY":list(station.coords)[0],
          "samples":points})
    return cases,needed,old
def fetch_orig(g56,g37,releases,rawdir,receipts):
    cases,need,old=prepare(g56,g37)
    found=asset_map(releases,need)
    rawdir.mkdir(parents=True,exist_ok=True)
    result=[]
    for i,(tile,v) in enumerate(sorted(found.items())):
        path=rawdir/v["filename"]
        if not path.exists():
            subprocess.run(["gh","release","download",v["tag"],"--repo",REPO,
               "--pattern",v["filename"],"--dir",str(rawdir)],
               check=True,timeout=100,stdout=subprocess.DEVNULL)
        bx=((tile[0]-200)*1000,(tile[1]-301)*1000,(tile[0]-199)*1000,(tile[1]-300)*1000)
        with rasterio.open(path) as ds:
            if not ds.crs or ds.crs.to_epsg()!=3763 or ds.width!=500 or ds.height!=500 or ds.count!=1:
                raise ValueError("G57_native_original_DGT2m_EPSG_500px_crs")
            if not np.allclose(ds.res,(2,2),atol=.001) or not np.allclose(tuple(ds.bounds),bx,atol=1):
                raise ValueError("G57_original_DGT_2m_tile_bbox_drift")
            count=int(np.count_nonzero(ds.read_masks(1)>0))
            if count==0:raise ValueError("G57_all_source_500x500_NoData")
        result.append({"tile_ColRow":list(tile),"original_source_release":v["tag"],
            "original_TIFF_filename":v["filename"],"original_TIFF_SHA256":sha(path),
            "source_valid_original_2m_pixel_n":count,"source_original_NoData_pixel_n":250000-count})
        print("G57_REUSED_ORIGINAL_DGT",i+1,len(need),tile,flush=True)
    receipts.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
def compute(g56,g37,rawdir,receipts,jout,csvout,pngout,mdout):
    cases,need,old=prepare(g56,g37)
    records=json.loads(receipts.read_text())
    files={tuple(r["tile_ColRow"]):r for r in records}
    if set(files)!=need:raise ValueError("G57_original_retrieved_TIFF_inventory_incomplete")
    opened={}
    try:
        for tile,z in files.items():
            f=rawdir/z["original_TIFF_filename"]
            if not f.exists() or sha(f)!=z["original_TIFF_SHA256"]:
                raise ValueError("G57_source_original_SHA_before_sample_changed")
            opened[tile]=rasterio.open(f)
        points=[];result=[];research_3D=[]
        for s in cases:
            item={k:v for k,v in s.items() if k!="samples"}
            if s["status"]!="G56_200kmh_CURVATURE_RESEARCH_XY_AVAILABLE":
                item.update({"valid_original_2m_ground_n":0,
                  "missing_native_2m_ground_n":0,
                  "no_3D_due_to_unfitted_planar":True,
                  "research_grade_3D_when_121_original_ground_points":None})
                result.append(item);continue
            pts=[];values=[]
            for p in s["samples"]:
                t=tuple(p["DGT_native_tile_ColRow"])
                z=None;status="DGT_SOURCE_1KM_TILE_NOT_IN_EXISTING_84"
                if t in opened:
                    sample=next(opened[t].sample([p["XY_original_G56_EPSG3763"]],masked=True))[0]
                    status="ORIGINAL_DGT2M_NoData_SOURCE_NOT_FILLED"
                    if not np.ma.is_masked(sample) and math.isfinite(float(sample)):
                        z=float(sample);status="VALID_ORIGINAL_DGT2M_BARE_EARTH_PIXEL"
                elif t in old:status="DGT84_ORIGINAL_RASTER_NOT_RETRIEVED_ERROR"
                q={**p,"original_DGT2m_ground_Z_native_m":round(z,3) if z is not None else None,
                   "source_status":status,
                   "original_TIFF_SHA256":files[t]["original_TIFF_SHA256"] if t in files else None,
                   "site_id":s["site_id"]}
                values.append(z);pts.append(q)
            good=sum(x is not None for x in values)
            if len(pts)!=121:raise ValueError("G57_original_121_per_curvature_site")
            grades=[]
            if good==121:
                for grade in (12.5,15.):
                    fitted=minimax_grade_envelope(np.arange(121,dtype=float)*25-1500,
                        values,grade,station_max_permille=10.,vertical_radius_m=20000.)
                    if fitted["status"]!="OPTIMISTIC_LP_MATHEMATICAL_GRADE_ENVELOPE_NOT_PROJECT":
                        raise ValueError("G57_original_source_grade_12p5_15_failed")
                    grades.append({"grade_limit_per_mille":grade,
                       "research_math_max_abs_ground_distance_m":fitted["minimum_maximum_vertical_ground_separation_m"],
                       "research_3D_Z_original_DGT_native_height_m":
                              fitted["mathematical_rail_height_AT_SOURCE_SAMPLES_NOT_CONSTRUCTED"],
                       "actual_grade_sampled_per_mille":fitted["actual_maximum_fitted_gradient_permille"],
                       "no_NATURA_tunnels_approval_from_grade":True})
                    research_3D.append({"source_G30_route":"G30-geographic_diversity",
                        "source_old_station":s["site_id"],
                        "grade_permille":grade,
                        "geometry_EPSG3763_XY_original_DGT_height_Z_native":"LINESTRING Z ("+
                             ", ".join(f"{q['XY_original_G56_EPSG3763'][0]} {q['XY_original_G56_EPSG3763'][1]} {zz}"
                                      for q,zz in zip(pts,fitted["mathematical_rail_height_AT_SOURCE_SAMPLES_NOT_CONSTRUCTED"]))+")"})
            item.update({"valid_original_2m_ground_n":good,
                "missing_native_2m_ground_n":121-good,
                "missing_source_DGT_original_tile_n":sum(tuple(v["DGT_native_tile_ColRow"]) not in old for v in pts),
                "research_grade_3D_when_121_original_ground_points":grades if grades else None,
                "source_real_ground_not_transplanted_from_G54":True})
            result.append(item);points.extend(pts)
        out={"mission":"MN-GEO-RAIL-001","stage":"G57_recovered_G30_Braganca_G56_200kmh_new_XY_original_DGT2m_ground",
            "full30_G10_G30_original_still_retained":True,
            "original_G56_200kmh_BR3_BR4_candidates_resampled_not_G54_old_geometry":True,
            "two_old_physical_station_sites":list(SITES),
            "original_reused_DGT2m_tiles_SHA256_QA":records,
            "two_G56_200kmh_horizontal_research_actual_ground_profiles":result,
            "actual_new_G56_family_specific_DGT2m_25m_sample_rows":points,
            "mathematical_ground_source_confirmed_XYZ_only_if_121valid":research_3D,
            "no_original_DGT_acquisition_or_new_TIFFs_downloaded_from_DGT":True,
            "no_missing_source_pixel_imputation":True,
            "BR3_rotated_original_heading_road_access_must_be_resurveyed":True,
            "no_guaranteed_200kmh_operating_speed_by_curvature_sample":True,
            "no_full_3D_intercity_geotechnical_track_EN_design":True,
            "no_Natura2000_PIC_groundwater_capex_real_travel_time":True,
            "Fxx_accepted":False,"Site_authorized":False}
        jout.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
        with csvout.open("w",newline="",encoding="utf-8-sig") as f:
            fields=("site_id","relative_chainage_m","original_DGT2m_ground_Z_native_m",
                 "source_status","DGT_native_tile_ColRow","original_TIFF_SHA256")
            w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
            for p in points:w.writerow({k:p.get(k) for k in fields})
        fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout="constrained")
        for ax,s in zip(axes,SITES):
            ps=[p for p in points if p["site_id"]==s]
            if ps:
                ax.plot([p["relative_chainage_m"]/1000 for p in ps],
                   [p["original_DGT2m_ground_Z_native_m"] if p["original_DGT2m_ground_Z_native_m"] is not None else np.nan for p in ps],
                   label="Solo nu DGT original",c="#386f8b")
                for g in next(r for r in result if r["site_id"]==s)["research_grade_3D_when_121_original_ground_points"] or []:
                    ax.plot([p["relative_chainage_m"]/1000 for p in ps],
                       g["research_3D_Z_original_DGT_native_height_m"],
                       label=f"Matemático {g['grade_limit_per_mille']}‰",ls="--")
            ax.set_title(s+" · nova geometria G56; raio amostrado 200km/h",loc="left",fontsize=10)
            ax.set_xlabel("km relativos à estação");ax.set_ylabel("Altura DGT original (m)")
            ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.suptitle("G57 · Terreno original nas geometrias G56 recuperadas, sem transplante de perfis",fontsize=11)
        fig.savefig(pngout,dpi=170,bbox_inches="tight");plt.close(fig)
        md=["# G57 — Teste do terreno DGT original nas duas ligações G56 recuperadas para Bragança",
           "","A G56 encontrou geometria horizontal a 200 km/h (limiar teórico de raio mínimo em amostragem), em BR3 e BR4 para a família G30-diversidade. A G57 obriga agora a verificar a topografia real ORIGINAL nas respetivas novas coordenadas, com 121 pontos por aproximação e 25m de espaçamento, a partir de fichas DGT2m já públicas; não transplanta qualquer perfil anterior.",
           "","| Sítio | Amostras válidas originais / 121 | R original G56 (m) | Orientação da plataforma | Rasantes matemáticas 12,5/15‰ |",
           "|---|---:|---:|---|---|"]
        for r in result:
            md.append(f"| {r['site_id']} | {r['valid_original_2m_ground_n']} | {r.get('source_G56_original_sampled_Rmin_m')} | {r.get('source_G56_original_station_heading_class')} | {'calculadas, solo nu contínuo' if r['research_grade_3D_when_121_original_ground_points'] else 'bloqueadas por dados originais em falta'} |")
        md+=["","**A passagem de um raio em planta não constitui geometria ferroviária validada, nem comprova a velocidade de exploração.** O caso BR3 exigiu alterar o azimute de implantação da estação, pelo que o tempo OSRM anterior só corresponde ao sítio original, não à nova plataforma com acessos reais.",
         "","A falta de dados em píxeis originais deve levar a identificação da quadrícula e da observação, não a interpolação. Só quando os 121 pontos estão disponíveis se ajusta rasante matemática da via geral a 12,5/15‰, reta de 800m a 10‰ como referência PAT e raio vertical hipotético 20km.",
         "","Não há linha 3D completa, custos, estruturas, geologia verificada em Bragança, impacto Natura/PIC ou autorizações. A carteira de 30 corredores fica preservada e não houve nova aquisição protegida DGT."]
        mdout.write_text("\n".join(md)+"\n")
        print("G57_RESULT",json.dumps({"original_DGT2m_tiles_reused":len(records),
            "sites":[{"site":r["site_id"],"real_native_DGT2m_valid_ground_n":r["valid_original_2m_ground_n"],
              "missing_original_source":r["missing_native_2m_ground_n"],
              "math_3D_grade_source_cases":len(r["research_grade_3D_when_121_original_ground_points"] or [])}
              for r in result],"original_pixels_n":len(points),"complete_200_station_research_math_3D":len(research_3D),
              "no_new_DGT_original":True},ensure_ascii=False),flush=True)
    finally:
        for r in opened.values():r.close()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("retrieve","analyze"),required=True)
    for key in ("g56","g37","releases","rawdir","receipts","json","csv","plot","markdown"):
        p.add_argument("--"+key,type=Path)
    a=p.parse_args()
    g56=json.loads(a.g56.read_text());g37=json.loads(a.g37.read_text())
    if a.mode=="retrieve":fetch_orig(g56,g37,json.loads(a.releases.read_text()),a.rawdir,a.receipts)
    else:compute(g56,g37,a.rawdir,a.receipts,a.json,a.csv,a.plot,a.markdown)
if __name__=="__main__":main()
