#!/usr/bin/env python3
"""G47: Re-read truly original DGT2m source pixels for four station approaches
already fully covered by original 84 DGT source tiles. Only reuse existing
public GitHub-release TIFF assets, NO DGT private account or fresh acquisition.

For pilot VR2, VR1, BR4, BR3 on original P2-2-1 G45 200km/h horizontal
research splines, source G46 1.5km each side, 200m lateral source tile budget,
sample ORIGINAL 2m ground rasters every 25m along centerline, QA TIFF geometry
SHA, source NoData, assess strict 18/25permille optimistic rail-grade LP.
No engineered full 3D alignment or station, no tunnels, costs, approvals.
"""
import argparse,csv,hashlib,json,math,re,subprocess,sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import LineString,Point
from shapely.ops import substring
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g26b_next_DGT2m_study_footprint_gate import indices
from geo_rail_g42_original_terrain_LP_all30_module_evidence import lp_best_vertical_envelope

REPO="r-sousa/mobilidade-public-sources"
STEP=25.
HALF=1500.
BAND=200.
ASSET_RE=re.compile(r"^MDT-2m-(\d{3})(\d{3})-(\d{2})-(\d{4})\.tif$")
RELEASE_TAG_PREFIXES=("mn-geo-rail-001-g21-native-DGT2m-39",
  "mn-geo-rail-001-g3-original-DGT2m-",
  "mn-geo-rail-001-g3-DGT2m-regional-",
  "mn-geo-rail-001-b1-DGT2m-")
def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1_000_000),b""):h.update(block)
    return h.hexdigest()
def validate(g45,g46):
    if not g45.get("all_G10_27_and_G30_3_retained") or g45.get("source_30_options")!=30:
        raise ValueError("G47_must_keep_all30")
    if not g46.get("full30_options_still_studied") or g46.get("old_verified_DGT_original_1km_tile_manifest")!=84:
        raise ValueError("G47_must_reuse_original_84_DGT")
    ids=g46["pilot_four_prior_station_site_ids_for_data_coverage_ONLY_not_site_ranking"]
    if len(ids)!=4 or set(ids)!={"VR1","VR2","BR3","BR4"}:
        raise ValueError("G47_four_prior_site_source_2026_locked")
    source=g46["four_pilot_station_combined_G45_source_2D_terrain_footprint_gaps"]["local_1p5km"]
    if source["required_1km_DGT2m_tiles"]!=18 or source["already_preserved_original_tiles"]!=18 or source["missing_tile_count"]!=0:
        raise ValueError("G47_original_18_of_18_DGT2m_tile_gate")
    return ids
def pilots(g45,g46):
    ids=validate(g45,g46)
    meta={x["candidate_site_id"]:x for x in g45["site_source_original_road_COS_DGT2m_from_G44"]}
    existing=set()
    records=[]
    for sid in ids:
        s=meta[sid]
        found=[r for r in g45["all_630_route_site_speed_horizontal_screen_cases"]
          if r["option_id"]=="P2-2-1" and r["historical_site_id"]==sid and r["illustrative_speed_label_kmh"]==200]
        if len(found)!=1 or not found[0]["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"]:
            raise ValueError("G47_must_have_original_P2_2_1_200kmh_planar_solution_"+sid)
        sol=found[0]["best_research_horizontal_solution"]
        line=LineString(sol["sampled_QA_path_PT_TM06"])
        station=Point(s["previous_source_original_XY_EPSG3763"])
        if line.distance(station)>5.:raise ValueError("G47_reference_site_not_on_2D_candidate")
        c=line.project(station)
        if c<HALF or line.length-c<HALF:raise ValueError("G47_study_2D_route_does_not_cover_1p5km")
        sub=substring(line,c-HALF,c+HALF)
        required=indices(sub.buffer(BAND,cap_style=2,join_style=2))
        records.append({"sid":sid,"site":s,"line":line,"middle":c,"segment":sub,
          "required":required,"sol":sol})
        existing|=required
    if len(existing)!=18:
        raise ValueError("G47_source_tile_union_drift_from_G46")
    return records,existing
def asset_map(releases,tiles):
    candidates=defaultdict(list)
    for r in releases:
        tag=r.get("tag_name","")
        if not any(tag.startswith(p) for p in RELEASE_TAG_PREFIXES):continue
        for a in r.get("assets",[]):
            name=a.get("name","")
            m=ASSET_RE.fullmatch(name)
            if not m:continue
            key=(int(m.group(1)),int(m.group(2)))
            if key not in tiles:continue
            candidates[key].append({"tag":tag,"filename":name,"source_GitHub_release_asset_id":a["id"],
                "source_GitHub_release_asset_size":a["size"]})
    selected={}
    for tile in sorted(tiles):
        sources=candidates.get(tile,[])
        if not sources:raise ValueError("G47_original_public_DGT_raster_missing_"+str(tile))
        selected[tile]=sources[0]
    return selected
def retrieve(releases,tiles,folder):
    folder.mkdir(parents=True,exist_ok=True)
    selected=asset_map(releases,tiles)
    receipts=[]
    for ix,(tile,meta) in enumerate(selected.items()):
        path=folder/meta["filename"]
        if not path.exists():
            subprocess.run(["gh","release","download",meta["tag"],
                "--repo",REPO,"--pattern",meta["filename"],"--dir",str(folder)],
                check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=85)
        if not path.is_file() or not (1000<path.stat().st_size<32_000_000):
            raise ValueError("G47_wrong_original_DGT_TIFF_asset_size")
        bx=((tile[0]-200)*1000,(tile[1]-301)*1000,(tile[0]-199)*1000,(tile[1]-300)*1000)
        with rasterio.open(path) as ds:
            if ds.count!=1 or ds.width!=500 or ds.height!=500 or ds.crs is None or ds.crs.to_epsg()!=3763:
                raise ValueError("G47_actual_DGT_original_TIFF_CRS_500pixel_mismatch")
            if not(np.allclose(ds.res,[2,2],atol=.001) and np.allclose(tuple(ds.bounds),bx,atol=1.)):
                raise ValueError("G47_DGT_2m_original_source_tile_wrong_1km_bbox")
            good=ds.read_masks(1)>0
            validn=int(np.count_nonzero(good))
            if validn==0:raise ValueError("G47_DGT_tile_no_native_valid_ground_at_all")
            r={"source_1km_tile_ColRow":list(tile),"source_GitHub_release_tag":meta["tag"],
              "source_original_file":meta["filename"],"source_SHA256_on_reused_public_original":sha(path),
              "source_size_bytes":path.stat().st_size,"source_DGT_2m_valid_ground_mask_pixels":validn,
              "source_DGT_2m_native_nodata_pixels":250000-validn,
              "source_DGT_tile_EPSG":3763,"source_native_resolution_m":2,
              "source_verified_bounds_EPSG3763_m":list(bx),
              "source_GitHub_release_asset_id":meta["source_GitHub_release_asset_id"]}
            receipts.append(r)
        print(f"G47_REUSED_ORIGINAL_DGT {ix+1}/{len(tiles)} {tile} validpixels={validn}",flush=True)
    return receipts
def analyze(records,receipts,folder,outjson,outcsv,mdout,figout):
    source={tuple(r["source_1km_tile_ColRow"]):r for r in receipts}
    readers={}
    try:
        for tile,r in source.items():readers[tile]=rasterio.open(folder/r["source_original_file"])
        cases=[];allrows=[];qa={}
        for entry in records:
            sid=entry["sid"]
            path=entry["segment"]
            site=entry["site"]
            samples=[]
            # 121 samples 25m apart, 3.0km fixed exact study domain
            for i in range(121):
                p=path.interpolate(i*STEP)
                x,y=p.x,p.y
                tile=(math.floor(x/1000)+200,math.floor(y/1000)+301)
                ds=readers.get(tile)
                z=None;status="ORIGINAL_DGT_SOURCE_NOT_AVAILABLE"
                if ds is not None:
                    v=next(ds.sample([(x,y)],masked=True))[0]
                    if not np.ma.is_masked(v) and math.isfinite(float(v)):
                        z=float(v);status="VALID_ORIGINAL_DGT_2M_GROUND_PIXEL"
                    else:status="ORIGINAL_DGT_2M_SOURCE_NoData_NOT_IMPUTED"
                samples.append({"site_id":sid,"source_station_chainage_relative_m":i*STEP-HALF,
                   "sample_XY_EPSG3763_m":[round(x,2),round(y,2)],
                   "original_DGT_2m_ground_elevation_m":round(z,3) if z is not None else None,
                   "original_1km_tile_index_ColRow":list(tile),
                   "original_file_SHA256":source[tile]["source_SHA256_on_reused_public_original"] if tile in source else None,
                   "source_status":status})
            allrows.extend(samples)
            valid=[x for x in samples if x["original_DGT_2m_ground_elevation_m"] is not None]
            maxrun=0;run=[];best=[]
            for i,x in enumerate(samples):
                if x["original_DGT_2m_ground_elevation_m"] is not None:
                    run.append(i)
                    if len(run)>maxrun:maxrun=len(run);best=list(run)
                else:run=[]
            fits=[]
            for grade in (18,25):
                if len(valid)==121:
                    result=lp_best_vertical_envelope([i*STEP for i in range(121)],
                        [r["original_DGT_2m_ground_elevation_m"] for r in samples],grade,False)
                    fits.append(result)
                else:
                    fits.append({"status":"UNTESTED_FULL_3KM_GROUND_NOT_CONTINUOUS_NO_INTERPOLATION",
                      "grade_permille":grade,
                      "minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m":None})
            source_terrain_slopes=[]
            for a,b in zip(samples,samples[1:]):
                va,vb=a["original_DGT_2m_ground_elevation_m"],b["original_DGT_2m_ground_elevation_m"]
                if va is not None and vb is not None:source_terrain_slopes.append((vb-va)/STEP*1000)
            cases.append({"site_id":sid,"mandatory_city":site["mandatory_city"],
               "previous_original_G25_city_to_road_reference_min":site["G25_original_OSRM_city_to_road_reference_minutes"],
               "source_2D_G45_station_curvature_Rmin_m":entry["sol"]["min_sampled_radius_m"],
               "source_2D_G45_deviates_from_direct_horizontal_chord_m":entry["sol"]["planimetric_length_excess_over_direct_chord_m"],
               "source_G45_planimetric_straight_station_m":800,
               "source_original_DGT2m_sample_count":121,
               "native_DGT2m_terrain_pixels_valid_n":len(valid),
               "native_DGT2m_terrain_pixels_missing_unfilled_n":121-len(valid),
               "longest_source_native_25m_chainage_contiguous_km":round(max(0,maxrun-1)*STEP/1000,3),
               "native_ground_source_elevation_minmax_m":
                  [min(x["original_DGT_2m_ground_elevation_m"] for x in valid),
                   max(x["original_DGT_2m_ground_elevation_m"] for x in valid)] if valid else None,
               "native_ground_25m_interval_exceeds_18permille_count":sum(abs(v)>18 for v in source_terrain_slopes),
               "native_ground_25m_interval_exceeds_25permille_count":sum(abs(v)>25 for v in source_terrain_slopes),
               "real_original_DGT2m_18_25permille_minmax_optimistic_grade_tests":fits,
               "does_not_extrapolate_3km_local_horizontal_to_both_long_rail_approaches":True,
               "no_station_platform_ground_geotechnical_approval":True})
        result={"mission":"MN-GEO-RAIL-001",
           "stage":"G47_reuse_18_public_original_DGT2m_source_rasters_for_4_new_station_2D_ground_profiles",
           "all_30_G10_27_G30_3_retained":True,
           "G45_all630_options_still_in_canonical_previous_evidence":True,
           "four_previous_physical_study_station_sites":[r["sid"] for r in records],
           "reused_existing_original_DGT_2m_GitHub_public_tile_assets_count":len(receipts),
           "source_18_native_original_DGT2m_tile_file_SHA_receipts":receipts,
           "real_4x121_25m_sample_original_native_DGT2m_pixel_rows":allrows,
           "four_real_original_source_native_ground_station_3km_profiles":cases,
           "no_new_DGT_credentialed_source_acquisition":True,
           "all_invalid_pixels_kept_missing_not_imputed":True,
           "source_25m_step_is_sampling_original_2m_not_25m_native":True,
           "sampled_planar_splines_not_railway_EN_compliant_3D_geometry":True,
           "no_Natura_PIC_water_legal_geotechnics_or_road_station_entrance_approved":True,
           "no_real_railway_structure_tunnel_viaduct_or_cost_timetable":True,
           "Fxx_accepted":False,"Site_authorized":False}
        outjson.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        with outcsv.open("w",newline="",encoding="utf-8-sig") as f:
            fields=("site_id","source_station_chainage_relative_m","original_DGT_2m_ground_elevation_m",
                 "original_1km_tile_index_ColRow","original_file_SHA256","source_status")
            w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
            for x in allrows:w.writerow({key:x.get(key) for key in fields})
        fig,axes=plt.subplots(2,2,figsize=(12,8),layout="constrained")
        for ax,case in zip(axes.flat,cases):
            sub=[x for x in allrows if x["site_id"]==case["site_id"]]
            ax.plot([x["source_station_chainage_relative_m"]/1000 for x in sub],
                [x["original_DGT_2m_ground_elevation_m"] if x["original_DGT_2m_ground_elevation_m"] is not None else np.nan for x in sub],
                c="#3b6983",lw=1.3,label="Original solo nu DGT2m")
            for q in case["real_original_DGT2m_18_25permille_minmax_optimistic_grade_tests"]:
                if q["status"].startswith("OPTIMISTIC"):
                    ax.plot([x["source_station_chainage_relative_m"]/1000 for x in sub],
                      q["fitted_track_elevation_RESEARCH_math_only_m"],ls="--",lw=1,
                      label=f"Rasante matemática {q['grade_permille']}‰")
            ax.set_title(case["site_id"]+" · "+case["mandatory_city"],loc="left")
            ax.set_xlabel("km da posição da estação estudada (eixo 2D não ferroviário)")
            ax.set_ylabel("Cota terreno DGT2m (m; original)")
            ax.grid(alpha=.2);ax.legend(fontsize=7)
        fig.suptitle("G47 · 4 perfis de solo nu original DGT de 2m ao longo das novas geometrias G45 — NÃO projeto ferroviário",fontsize=11)
        fig.savefig(figout,dpi=160,bbox_inches="tight");plt.close(fig)
        md=["# G47 — Quatro perfis contínuos de solo nu original MDT DGT 2m, sem novas aquisições",
            "",f"**{len(receipts)} ficheiros GeoTIFF DGT2m originais** reutilizados diretamente de releases públicas anteriores do Mobilidade Norte, com índice espacial do produtor, projeção EPSG3763, 500×500 píxeis nativos, 2m/píxel e SHA256 individual controlados.",
            "","Cada perfil tem 121 posições amostradas a intervalos de 25m ao longo dos 3km centrais da geometria horizontal **G45** de uma posição de estação (não é uma rasante de projeto). O G45 preserva 27+3 alternativas, mas o G47 aprofunda quatro locais representativos na variante de referência P2-2-1 para 200 km/h.",
            "","| Sítio | Cotas DGT2m válidas /121 | Intervalo do terreno (m) | Afastamento mínimo matemático 18‰ /25‰ (m) |",
            "|---|---:|---|---|"]
        for c in cases:
            def v(grade):
                p=next(z for z in c["real_original_DGT2m_18_25permille_minmax_optimistic_grade_tests"] if z["grade_permille"]==grade)
                return p.get("minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m")
            md.append(f"| {c['site_id']} | {c['native_DGT2m_terrain_pixels_valid_n']} | {c['native_ground_source_elevation_minmax_m']} | {v(18) if v(18) is not None else 'sem cobertura integral'} / {v(25) if v(25) is not None else 'sem cobertura integral'} |")
        md+=["","Um resultado de rasante matemática é um limite inferior do afastamento vertical aos pontos de terreno amostrados no eixo horizontal experimental. Não determina escavação, viaduto, túnel ou custos. Nenhuma curva vertical ou ligação ao corredor interurbano foi certificada; inclinações de plataforma e conforto ferroviário carecem de estudo.",
          "","**Importante:** o arquivo contém apenas os hashes e os registos de fonte originais, não duplica os grandes TIFF já públicos. Quadriculagem disponível não garante píxeis válidos, e os pontos NoData são preservados como lacunas sem interpolação.",
          "","## Continuidade de desenho",
          "1. Usar estes perfis para ajustar localmente as alternativas de orientação/rasante e verificar a implantação em plataformas de 800m **como hipótese**, com gradientes reais e curvas verticais, e só então aprofundar o contacto com os módulos de linha diferentes.",
          "2. Adquirir apenas as **10 quadrículas DGT2m do G46** ainda em falta para o ensaio de 3km, caso estas novas faixas sejam mantidas após análise e com autorização através do fluxo privado já existente.",
          "3. Mosaicos PT/ES exigem controlo de datum altimétrico; túnel Marão/Alvão exige geologia, hidrogeologia, Natura2000 e PIC oficial antes de quantificar estruturas.",
          "","**Sem novos acessos DGT protegidos, Fxx/Site, obra aprovada, custo ou tempos de serviço.**"]
        mdout.write_text("\n".join(md)+"\n")
        print("G47_RESULT",json.dumps({"original_public_DGT2m_files":len(receipts),
            "station_profiles":[{k:c[k] for k in ("site_id","native_DGT2m_terrain_pixels_valid_n","native_DGT2m_terrain_pixels_missing_unfilled_n","native_ground_source_elevation_minmax_m")} for c in cases],
            "all30_preserved":True,"no_new_DGT_source_download":True},ensure_ascii=False),flush=True)
    finally:
        for ds in readers.values():ds.close()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",required=True,choices=("retrieve","analyze"))
    for key in ("g45","g46","releases","rawdir","receipts","json","csv","markdown","plot"):
        ap.add_argument("--"+key,type=Path)
    a=ap.parse_args()
    g45=json.loads(a.g45.read_text());g46=json.loads(a.g46.read_text())
    records,needed=pilots(g45,g46)
    if a.mode=="retrieve":
        rec=retrieve(json.loads(a.releases.read_text()),needed,a.rawdir)
        a.receipts.write_text(json.dumps(rec,indent=2,ensure_ascii=False)+"\n")
    else:
        r=json.loads(a.receipts.read_text())
        if len(r)!=18 or {tuple(x["source_1km_tile_ColRow"]) for x in r}!=needed:
            raise ValueError("G47_original_reused_18_source_raster_manifest_mismatch")
        for v in r:
            f=a.rawdir/v["source_original_file"]
            if not f.is_file() or sha(f)!=v["source_SHA256_on_reused_public_original"]:
                raise ValueError("G47_original_public_raster_sha_changed_before_analysis")
        analyze(records,r,a.rawdir,a.json,a.csv,a.markdown,a.plot)
if __name__=="__main__":main()
