#!/usr/bin/env python3
"""G54 actual original DGT2m source-ground pixel audit of SIX G52 geographical
families at four historical physical station sites, 200km/h *horizontal radius*
screen, exact original G45 source 2D centerlines.

Do not transplant G53 P2-2-1 source ground profiles into another G52 family.
The only valid cross-family source ground is the same native DGT2m TIFF
re-sampled at each family's own 25m X/Y coordinates (121×3km by site).
Reuses *only* previously published original public GeoTIFFs indexed in G37
84 original DGT tiles. Missing sources/NoData stay null, not interpolated.
If all 121 real ground pixels valid for a candidate, calculate an optimistic
12.5/15 per-mille mathematical z(x) profile with 800m station 10 per-mille
and 20km vertical finite difference radius, no station height assumed.
No true railway alignment, rail speed, tunnel/viaduct lengths or CAPEX.
"""
from __future__ import annotations
import argparse,csv,json,math,sys,subprocess
from pathlib import Path
from collections import defaultdict
import numpy as np
import rasterio
from shapely.geometry import LineString,Point
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g47_original_DGT2m_station_3km_ground import (
   asset_map,sha
)
from geo_rail_g48_real_source_5grade_traffic_station_recalibration import minimax_grade_envelope

REPO="r-sousa/mobilidade-public-sources"
SITES=("VR2","VR1","BR4","BR3")
STEP=25.
HALF=1500.
GRADE=(12.5,15.)
def original_case_index(g52,g45,g37):
    if not g52["source_original_all30_preserved"] or g52["source_27_G10_3_G30_count"]!=30:
        raise ValueError("G54_original_30_G52_source_must_remain")
    ids=g52["G52_six_representative_original_source_routes_for_NEXT_ground_3D"]
    if len(ids)!=6 or len(set(ids))!=6:raise ValueError("G54_G52_six_unique_family")
    if not g45["all_G10_27_and_G30_3_retained"] or len(g45["all_630_route_site_speed_horizontal_screen_cases"])!=630:
        raise ValueError("G54_original_30_G45_630_splines_required")
    if len(g37["source_84_original_DGT_tile_ids_in_PTTM06"])!=84:
        raise ValueError("G54_original_DGT_84_source_required")
    existing={tuple(z) for z in g37["source_84_original_DGT_tile_ids_in_PTTM06"]}
    sites={s["candidate_site_id"]:s for s in g45["site_source_original_road_COS_DGT2m_from_G44"]}
    rec={(r["option_id"],r["historical_site_id"],r["illustrative_speed_label_kmh"]):r for r in
         g45["all_630_route_site_speed_horizontal_screen_cases"]}
    if len(rec)!=630 or not set(SITES)<=set(sites):
        raise ValueError("G54_source_7sites_630cases_drift")
    cases=[];needed=set()
    for id in ids:
        for sid in SITES:
            old=rec[(id,sid,200)]
            item={"source_family":id,"physical_study_site":sid,
              "city":sites[sid]["mandatory_city"],
              "source_original_G45_200kmh_curvature_screen_pass":
                   bool(old["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"]),
              "source_assumed_station_800m_not_standards_certified":True}
            if not item["source_original_G45_200kmh_curvature_screen_pass"]:
                item["status"]="NO_G45_PLANIMETRIC_RADIUS_CANDIDATE_WITHIN_TESTED_PARAMETERS"
                cases.append(item);continue
            sol=old["best_research_horizontal_solution"]
            if not sol:raise ValueError("G54_sampled_horizontal_true_but_missing")
            ll=LineString(sol["sampled_QA_path_PT_TM06"])
            physical=Point(sites[sid]["previous_source_original_XY_EPSG3763"])
            if ll.distance(physical)>5:raise ValueError("G54_true_original_station_not_on_family_2D")
            center=ll.project(physical)
            if center<HALF or ll.length-center<HALF:
                item["status"]="PLANNED_APPROACH_LINE_TOO_SHORT_FOR_3KM_CENTERED_GROUND"
                cases.append(item);continue
            points=[]
            for i in range(121):
                p=ll.interpolate(center-HALF+i*STEP)
                tile=(math.floor(p.x/1000)+200,math.floor(p.y/1000)+301)
                points.append({"chainage_relative_station_m":int(-HALF+i*STEP),
                  "XY_EPSG3763":[round(p.x,3),round(p.y,3)],
                  "tile_1km_original_DGT_ColRow":list(tile)})
                if tile in existing:needed.add(tile)
            item["status"]="SOURCE_COORDINATES_AVAILABLE_SAMPLE_NATIVE_DGT"
            item["source_candidate_2D_min_sampled_radius_m"]=sol["min_sampled_radius_m"]
            item["samples"]=points
            cases.append(item)
    if len(cases)!=24:raise ValueError("G54_required_all_six_times_four")
    return cases,needed,existing
def retrieve(g52,g45,g37,releases,rawdir,receipts):
    cases,tiles,existing=original_case_index(g52,g45,g37)
    available=asset_map(releases,tiles) # Fail closed if an original promised in DGT84 is missing from source releases
    rawdir.mkdir(parents=True,exist_ok=True)
    by={}
    for i,(tile,meta) in enumerate(sorted(available.items())):
        path=rawdir/meta["filename"]
        if not path.exists():
            subprocess.run(["gh","release","download",meta["tag"],"--repo",REPO,
                  "--pattern",meta["filename"],"--dir",str(rawdir)],
                  check=True,stdout=subprocess.DEVNULL,timeout=100)
        if not path.exists() or not 1000<path.stat().st_size<32_000_000:
            raise ValueError("G54_original_DGT_native_TIFF_absent_or_size_invalid")
        bounds=((tile[0]-200)*1000,(tile[1]-301)*1000,
                (tile[0]-199)*1000,(tile[1]-300)*1000)
        with rasterio.open(path) as ds:
            if ds.count!=1 or ds.width!=500 or ds.height!=500 or not ds.crs or ds.crs.to_epsg()!=3763:
                raise ValueError("G54_original_DGT_2m_500x500_source_CRS_mismatch")
            if not np.allclose(ds.res,[2,2],atol=.001) or not np.allclose(tuple(ds.bounds),bounds,atol=1.):
                raise ValueError("G54_actual_original_DGT_native_1km_bbox_incorrect")
            valid=int(np.count_nonzero(ds.read_masks(1)>0))
            if valid==0:raise ValueError("G54_original_source_file_has_all_NoData")
            by[tile]={"tile_index_col_row":list(tile),"source_release_tag":meta["tag"],
                "source_asset_original":meta["filename"],
                "source_original_SHA256":sha(path),
                "native_2m_valid_pixel_count":valid,
                "native_2m_NoData_pixel_count":250000-valid,
                "native_original_EPSG":3763,"native_original_pixel_size_m":2,
                "native_original_bounds":list(bounds)}
        print("G54_FETCH_ORIGINAL",i+1,len(tiles),tile,flush=True)
    receipts.write_text(json.dumps({"original_reused_GitHub_release_DGT2m_tiles":list(by.values()),
       "original_manifest_84_verified":True,"raw_originals_not_republished":True},indent=2)+"\n")
def analyze(g52,g45,g37,receipts,rawdir,outjson,outcsv,outpng,outmd):
    original=original_case_index(g52,g45,g37)
    cases,tiles,existing=original
    d=json.loads(receipts.read_text())
    sr={tuple(s["tile_index_col_row"]):s for s in d["original_reused_GitHub_release_DGT2m_tiles"]}
    if set(sr)!=tiles:raise ValueError("G54_local_original_DGT_raster_incomplete_receipts")
    ds={}
    try:
        for tile,s in sr.items():
            p=rawdir/s["source_asset_original"]
            if not p.exists() or sha(p)!=s["source_original_SHA256"]:
                raise ValueError("G54_original_pixel_file_sha_drift_before_ground")
            ds[tile]=rasterio.open(p)
        rec=[];points=[];lines=[]
        for c in cases:
            info={k:v for k,v in c.items() if k!="samples"}
            if c["status"]!="SOURCE_COORDINATES_AVAILABLE_SAMPLE_NATIVE_DGT":
                info.update({"source_original_121_ground_samples_valid":0,
                  "source_native_25m_ground_samples_NoData":0,
                  "source_original_G37_unavailable_DGT_tile_samples":0,
                  "source_original_DGT2m_TIFF_not_in_archive_tile_samples":0,
                  "full_3km_original_bareearth_ground_available":False,
                  "12p5_15_mathematical_profiles":None,
                  "no_fabricated_ground":True})
                rec.append(info);continue
            valid=[]
            for v in c["samples"]:
                tile=tuple(v["tile_1km_original_DGT_ColRow"])
                px=v["XY_EPSG3763"]
                status="SOURCE_DGT_TILE_OUTSIDE_EXISTING_84"
                z=None;data_sha=None
                if tile in ds:
                    got=next(ds[tile].sample([px],masked=True))[0]
                    status="DGT2M_ACTUAL_ORIGINAL_PIXEL_NoData"
                    if not np.ma.is_masked(got) and math.isfinite(float(got)):
                        z=float(got);status="DGT2M_ACTUAL_ORIGINAL_BAREEARTH_VALID"
                    data_sha=sr[tile]["source_original_SHA256"]
                elif tile in existing:status="DGT84_INDEX_TILE_NOT_RETRIEVED_SOURCE_ERROR"
                valid.append(z)
                points.append({"source_family":c["source_family"],"physical_study_site":c["physical_study_site"],
                  "relative_chainage_m":v["chainage_relative_station_m"],"point_EPSG3763":px,
                  "original_1km_tile":list(tile),
                  "source_ground_native_DGT_2m_height_m":round(z,3) if z is not None else None,
                  "source_original_TIFF_SHA256":data_sha,
                  "source_status":status})
            good=sum(z is not None for z in valid)
            missing=121-good
            absent=sum(tuple(v["tile_1km_original_DGT_ColRow"]) not in existing for v in c["samples"])
            nodata=missing-absent
            runs=[];start=None
            for i,z in enumerate(valid+[None]):
                if z is not None and start is None:start=i
                if z is None and start is not None:
                    runs.append((start,i-1));start=None
            longest=max(((b-a)*STEP for a,b in runs),default=0)
            fits=[]
            if good==121:
                for grade in (12.5,15.):
                    fit=minimax_grade_envelope(
                       np.arange(121,dtype=float)*25-1500,
                       valid,grade,station_max_permille=10.,
                       vertical_radius_m=20000.,fixed_endpoints=False)
                    if fit["status"]!="OPTIMISTIC_LP_MATHEMATICAL_GRADE_ENVELOPE_NOT_PROJECT":
                        raise ValueError("G54_math_profile_source_fit_fail")
                    fits.append({"grade_permille":grade,
                      "source_real_G45_family_geometry_3D_local_optimistic_only":True,
                      "max_abs_ground_vs_optimal_math_Z_m":fit["minimum_maximum_vertical_ground_separation_m"],
                      "actual_sampled_mixed_grade_max_permille":fit["actual_maximum_fitted_gradient_permille"],
                      "sample_121_mathematical_Z_m":fit["mathematical_rail_height_AT_SOURCE_SAMPLES_NOT_CONSTRUCTED"]})
                    lines.append({"source_family":c["source_family"],"study_site":c["physical_study_site"],
                      "grade_permille":grade,
                      "horizontal_CRS":"EPSG:3763",
                      "vertical_height_reference":"NATIVE_DGT_ORIGINAL_VERTICAL_UNHARMONIZED_NOT_WGS84",
                      "LINESTRING_Z_WKT":"LINESTRING Z ("+
                      ", ".join(f"{v['XY_EPSG3763'][0]:.3f} {v['XY_EPSG3763'][1]:.3f} {zz:.3f}"
                        for v,zz in zip(c["samples"],fit["mathematical_rail_height_AT_SOURCE_SAMPLES_NOT_CONSTRUCTED"]))+")"})
            info.update({"source_original_121_ground_samples_valid":good,
                "source_original_DGT2m_missing_ground_samples":missing,
                "source_native_25m_ground_samples_NoData_or_unavailable_within_existing_index":nodata,
                "source_original_G37_unavailable_DGT_tile_samples":absent,
                "source_original_DGT2m_TIFF_not_in_archive_tile_samples":0,
                "full_3km_original_bareearth_ground_available":good==121,
                "longest_contiguous_real_native_DGT_ground_km":round(longest/1000,3),
                "original_native_height_minmax_m":[round(min(z for z in valid if z is not None),3),
                         round(max(z for z in valid if z is not None),3)] if good else None,
                "12p5_15_mathematical_profiles":fits if fits else None,
                "real_original_DGT2m_2m_ground_not_extrapolated":True,
                "no_fabricated_ground":True})
            rec.append(info)
        if len(rec)!=24 or len(points)>24*121:raise ValueError("G54_original_6x4_governance")
        complete=[q for q in rec if q["full_3km_original_bareearth_ground_available"]]
        if len(lines)!=2*len(complete):raise ValueError("G54_model_when_no_original_full_ground")
        out={"mission":"MN-GEO-RAIL-001","stage":"G54_original_DGT2m_source_ground_resample_six_geographic_family_station_3km",
         "full_30_G10_G30_research_routes_preserved":True,
         "six_original_G52_spatially_distinct_families":g52["G52_six_representative_original_source_routes_for_NEXT_ground_3D"],
         "four_prior_DGT2m_study_sites":list(SITES),
         "all_24_six_family_times_four_station_true_source_checks":rec,
         "sampled_true_original_DGT2m_ground_source_points_on_G45_family_specific_XY":points,
         "reused_native_original_DGT2m_release_SHA_and_tiles":list(sr.values()),
         "total_original_TIFF_1km2_reused":len(sr),
         "source_ground_valid_samples_count":sum(q["source_original_121_ground_samples_valid"] for q in rec),
         "real_G45_family_3km_ground_fully_verified_case_count":len(complete),
         "real_family_specific_optimistic_XYZ_WKT_if_source_complete":lines,
         "no_original_DGT_archive_reacquired_or_duplicate_raw_download":True,
         "no_imputation_for_missing_2m_raster_source":True,
         "vertical_z_is_native_DGT_unharmonized_not_WGS84_ellipsoidal":True,
         "mixed_line_grade_12p5_15_station_10_Rv20k_non_normative":True,
         "station_2D_quintic_not_EN_built_rail_and_not_true_full_corridor":True,
         "original_DGT_pixel_sampling_not_new_station_road_access_approval":True,
         "no_tunnel_bridge_groundwater_natura_PIC_CAPEX_or_actual_train_time":True,
         "Fxx_accepted":False,"Site_authorized":False}
        outjson.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
        fields=("source_family","physical_study_site","city","status",
          "source_original_G45_200kmh_curvature_screen_pass",
          "source_original_121_ground_samples_valid",
          "source_original_DGT2m_missing_ground_samples",
          "source_original_G37_unavailable_DGT_tile_samples",
          "full_3km_original_bareearth_ground_available",
          "longest_contiguous_real_native_DGT_ground_km")
        with outcsv.open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
            for q in rec:w.writerow({k:q.get(k) for k in fields})
        M=np.array([[next(x["source_original_121_ground_samples_valid"] for x in rec if
           x["source_family"]==family and x["physical_study_site"]==site)
           for site in SITES] for family in out["six_original_G52_spatially_distinct_families"]])
        fig,ax=plt.subplots(figsize=(9,6),layout="constrained")
        im=ax.imshow(M,aspect="auto",vmin=0,vmax=121,cmap="viridis")
        ax.set_yticks(range(6),out["six_original_G52_spatially_distinct_families"],fontsize=8)
        ax.set_xticks(range(4),SITES)
        for i in range(6):
            for k in range(4):ax.text(k,i,f"{M[i,k]}/121",ha="center",va="center",
                                      color="white" if M[i,k]<60 else "black",fontsize=8)
        ax.set_title("G54 · Píxeis de terreno DGT2m ORIGINAL verificáveis nas novas seis famílias e quatro estações",loc="left")
        fig.colorbar(im,ax=ax,label="Amostras reais válidas de 121 (3 km)")
        fig.savefig(outpng,dpi=160,bbox_inches="tight");plt.close(fig)
        md=["# G54 — Terreno verdadeiro das seis famílias G52 nas quatro posições de estação",
           "","Pela primeira vez os novos eixos horizontais G52 foram amostrados nas respetivas coordenadas, sobre GeoTIFF DGT2m **originais já públicos**. Anteriormente só a hipótese P2-2-1 tinha 484 pontos originais; não foram transpostos. Cada caso utiliza até 121 amostras de 25m ao longo dos 3km centrados na estação (o raster é de 2m), e mantém explicitamente NoData e quadrículas ausentes.",
           "","| Família | VR2: válidos/121 | VR1 | BR4 | BR3 |",
           "|---|---:|---:|---:|---:|"]
        for family in out["six_original_G52_spatially_distinct_families"]:
            row=[next(x for x in rec if x["source_family"]==family and x["physical_study_site"]==site) for site in SITES]
            md.append("| "+family+" | "+" | ".join(str(x["source_original_121_ground_samples_valid"]) for x in row)+" |")
        md+=["",f"Total: **{len(sr)}** GeoTIFF originais DGT reutilizados, **{len(complete)} de 24** geometrias com amostras de solo nu contínuas de 3km. Os casos completos permitem rasantes matemáticas preliminares a 12,5/15‰; os incompletos permanecem **sem** rasante 3D, por falta de terreno ou de geometria horizontal testada.",
         "","A matriz é suporte para selecionar onde desenhar e adquirir MDT adicional, não classificação de viabilidade. A falta de píxeis não significa que o terreno seja impróprio. Os 30 corredores continuam no acervo; os 3km são apenas aproximações locais. Não se obtiveram comprimentos de túneis, volumes, CAPEX nem tempos de marcha.",
         "","**Prioridade concreta seguinte:** ampliar apenas as aproximações e os módulos que não estejam cobertos por solo nu contínuo e que continuem competitivos na geometria em planta; iniciar pelo Marão–Alvão e VR2, em simultâneo com a verificação geológica, evitando qualquer aquisição massiva nas células de grelha G10.",
         "","**Fonte DGT2m com EPSG:3763 e alturas originais não harmonizadas com Espanha. Sem Fxx/Site.**"]
        outmd.write_text("\n".join(md)+"\n")
        print("G54_RESULT",json.dumps({"cases":24,"actual_1km_native_original_rasters_reused":len(sr),
          "fully_source_valid_family_specific_3km_cases":len(complete),
          "valid_real_source_pixels":out["source_ground_valid_samples_count"],
          "by_case":[{k:q.get(k) for k in ("source_family","physical_study_site",
           "source_original_121_ground_samples_valid","source_original_G37_unavailable_DGT_tile_samples",
           "status")} for q in rec],
          "no_source_reacquisition":True},ensure_ascii=False),flush=True)
    finally:
        for rdr in ds.values():rdr.close()
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--mode",choices=("retrieve","analyze"),required=True)
    for k in ("g52","g45","g37","releases","rawdir","receipts","json","csv","plot","markdown"):
        a.add_argument("--"+k,type=Path)
    x=a.parse_args()
    g52=json.loads(x.g52.read_text());g45=json.loads(x.g45.read_text());g37=json.loads(x.g37.read_text())
    if x.mode=="retrieve":
        retrieve(g52,g45,g37,json.loads(x.releases.read_text()),x.rawdir,x.receipts)
    else:analyze(g52,g45,g37,x.receipts,x.rawdir,x.json,x.csv,x.plot,x.markdown)
if __name__=="__main__":main()
