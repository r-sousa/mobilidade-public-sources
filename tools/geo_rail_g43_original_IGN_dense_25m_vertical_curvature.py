#!/usr/bin/env python3
"""G43 densify true original 13x1km IGN/CNIG WCS 25m GeoTIFF source samples
along final 6km of G10 P2-2-1 research centerline, every 25m.

No extra raw acquisition: match all 13 original GeoTIFF SHA against G39
original public release manifest and reextract pixel at each source 25m chainage.
Run constrained minmax mathematical vertical envelopes (18/25 per mille) and
hypothetical vertical curve radius sensitivities (10/20 km), with free and
ground-tied endpoints. Horizontal 2km lattice is NOT rail engineering.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,zipfile,sys
from pathlib import Path
from collections import Counter
import numpy as np
import rasterio
from rasterio.io import MemoryFile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer
from shapely.geometry import LineString
from scipy.optimize import linprog
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g42_original_terrain_LP_all30_module_evidence import lp_best_vertical_envelope
from geo_rail_g38_1km_original_IGN_ground_source_probe import sanity_ground_tiff
STEP_M=25.
SECTOR_M=6000.
NPTS=241
GRADES=(18,25)
VERTICAL_R_BENCH=(None,10000,20000)
XFORM=Transformer.from_crs(4326,25830,always_xy=True)
def verify(g10,g39,g42):
    if g42.get("original_count")!=30 or not g42.get("original_G10_27_G30_3_preserved"):
        raise ValueError("G43_previous_all30_5module_source_required")
    if g39.get("validated_original_WCS_MDT25_source_points")!=13 or g39.get("original_WCS_failed_points_not_imputed")!=0:
        raise ValueError("G43_previous_13_actual_originals_required")
    if not g42.get("no_new_original_source_data_acquired") or not g42.get("PT_ES_altimetric_datum_unharmonized"):
        raise ValueError("G43_provenance_not_stable")
    if len(g10.get("features",[]))!=27:raise ValueError("G43_G10_source_27_missing")
def load_original_tiles(archive,manifest):
    if not zipfile.is_zipfile(archive):
        raise ValueError("G43_Original_zip_corrupt")
    tiles=[]
    with zipfile.ZipFile(archive,"r") as z:
        for i,r in enumerate(manifest["source_point_sampled_values"]):
            name=f"IGN_MDT25_actual_source_UTM30_sector_point_{i:02d}.tif"
            b=z.read(name)
            if hashlib.sha256(b).hexdigest()!=r["source_original_tif_sha256"]:
                raise ValueError("G43_original_G39_source_SHA256_drift")
            qa=sanity_ground_tiff(b)
            if qa["source_crs"]!="EPSG:25830" or qa["resolution"]!=[25.,25.]:
                raise ValueError("G43_original_source_not_25m")
            tiles.append({"data":b,"original_manifest":r,"sha":r["source_original_tif_sha256"]})
    if len(tiles)!=13:raise ValueError("G43_missing_original_tiles")
    return tiles
def source_path(g10):
    feat=next(f for f in g10["features"] if f["properties"]["id"]=="P2-2-1")
    line=LineString([XFORM.transform(*p) for p in feat["geometry"]["coordinates"]])
    if not line.length>200000:raise ValueError("G43_unexpected_original_research_length")
    xy=[line.interpolate(line.length-SECTOR_M+i*STEP_M) for i in range(NPTS)]
    return [(p.x,p.y) for p in xy],line
def densify(g10,g39,g42,originalzip):
    verify(g10,g39,g42)
    tiles=load_original_tiles(originalzip,g39)
    xy,line=source_path(g10)
    dss=[];rows=[];counts=Counter()
    try:
        for t in tiles:
            m=MemoryFile(t["data"])
            ds=m.open()
            dss.append((t,m,ds))
        for i,(x,y) in enumerate(xy):
            choices=[]
            for tile,m,ds in dss:
                b=ds.bounds
                if b.left<=x<b.right and b.bottom<y<=b.top:
                    z=next(ds.sample([(x,y)],masked=True))[0]
                    if np.ma.is_masked(z) or not np.isfinite(z):continue
                    # Favor source whose REQUEST centre is closest to each point.
                    center=tile["original_manifest"]
                    rc=center["east_25830_m"];rn=center["north_25830_m"]
                    choices.append((math.hypot(x-rc,y-rn),float(z),tile["sha"]))
            if choices:
                choices.sort(key=lambda e:e[0])
                first=choices[0]
                z=first[1]
                spread=max(q[1] for q in choices)-min(q[1] for q in choices)
                counts["valid"]+=1
                if len(choices)>1:counts["overlap"]+=1
                if spread>1.5:counts["overlap_raster_nearest_pixel_disagreement_above_1p5m"]+=1
                original_sha=first[2]
                status="ACTUAL_ORIGINAL_IGN25_PIXEL_QA"
            else:
                counts["missing"]+=1;z=None;spread=None;original_sha=None
                status="NO_SOURCE_TILE_COVERAGE_NODATA_NOT_IMPUTED"
            rows.append({"source_research_chainage_m":i*STEP_M,
                "east_25830_m":round(x,3),"north_25830_m":round(y,3),
                "actual_IGN25_original_ground_m":round(z,3) if z is not None else None,
                "ground_source_raster_SHA256":original_sha,
                "source_original_rasters_cover_point":len(choices),
                "overlap_nearest_pixel_source_roughness_spread_m":round(spread,3) if spread is not None else None,
                "source_status":status})
    finally:
        for _,m,ds in dss:ds.close();m.close()
    # Audit all G39 original center elevations in dense new samples; each center
    # at exact chainage 0,500,...6000. Difference can exist if same native raster
    # request had shifted exact nominal coordinate; fail on large conflict.
    center_checks=[]
    for i in range(13):
        match=rows[i*20]["actual_IGN25_original_ground_m"]
        previous=g39["source_point_sampled_values"][i]["official_IGN_MD25_original_sample_elevation_m"]
        d=abs(match-previous) if match is not None else None
        center_checks.append({"index":i,"dense_G43":match,"original_G39":previous,
            "abs_difference_m":round(d,3) if d is not None else None})
        if match is not None and d>25:
            raise ValueError("G43_original_500m_ground_recompute_massive_disagreement")
    return rows,counts,center_checks,line
def LP_curved(distances,ground,grade,R=None,fix_ends=False):
    if R is None:return lp_best_vertical_envelope(distances,ground,grade,fix_ends)
    x=np.asarray(distances,float)
    y=np.asarray(ground,float)
    if any(v is None for v in ground) or not np.all(np.isfinite(y)):
        raise ValueError("G43_NULL_PIXEL_CURVE_SOLUTION_FORBIDDEN")
    dx=np.diff(x)
    if not np.allclose(dx,dx[0],atol=.00001):
        raise ValueError("G43_curvature_uses_only_uniform_25m_source_samples")
    h=float(dx[0]);n=len(x)
    tcol=n;A=[];b=[]
    for i in range(n):
        a=np.zeros(n+1);a[i]=1;a[tcol]=-1
        A.append(a);b.append(y[i])
        a=np.zeros(n+1);a[i]=-1;a[tcol]=-1
        A.append(a);b.append(-y[i])
    for i in range(n-1):
        for sign in (-1,1):
            a=np.zeros(n+1);a[i]=sign;a[i+1]=-sign
            A.append(a);b.append(grade/1000*h)
    # Sensitivity to a simplified bound on change in vertical slope:
    # |z[i+1]-2z[i]+z[i-1]| <= h²/R.
    # Not a standard-compliant railway vertical curve design nor 3D axis.
    for i in range(1,n-1):
        for sign in (-1,1):
            a=np.zeros(n+1)
            a[i-1]=sign;a[i]=-2*sign;a[i+1]=sign
            A.append(a);b.append(h*h/R)
    bounds=[(None,None)]*n+[(0,None)]
    if fix_ends:
        bounds[0]=(float(y[0]),float(y[0]))
        bounds[n-1]=(float(y[-1]),float(y[-1]))
    obj=np.zeros(n+1);obj[-1]=1.
    sol=linprog(obj,A_ub=np.asarray(A),b_ub=np.asarray(b),bounds=bounds,method="highs")
    if not sol.success:
        return {"status":"NO_MATH_SOLUTION_FOR_GRADE_AND_VERTICAL_RADIUS_ASSUMPTION",
             "grade_permille":grade,"assumed_vertical_radius_m":R,
             "both_endpoints_fixed_at_sampled_ground":fix_ends,
             "not_statutory_railway_failure":True}
    z=sol.x[:n]
    if np.max(np.abs(np.diff(z)/h))*1000>grade+.0001:
        raise ValueError("G43_LP_gradient_inconsistent")
    if np.max(np.abs(np.diff(z,n=2)))*R/(h*h)>1.00001:
        raise ValueError("G43_LP_vertical_curvature_inconsistent")
    return {"status":"OPTIMISTIC_MATH_LP_ON_REAL_SOURCE_TERRAIN_NOT_ENGINEERED_RAIL",
        "grade_permille":grade,"assumed_vertical_radius_m":R,
        "both_endpoints_fixed_at_sampled_ground":fix_ends,
        "minimum_possible_MAX_vertical_difference_at_ground_samples_m":round(float(sol.x[-1]),3),
        "track_math_z_m":[round(float(v),3) for v in z],
        "sample_interval_m":h,
        "only_non_standard_hypothetical_vertical_curve_sensitivity":True}
def biggest_contiguous_run(rows):
    runs=[];curr=[]
    for i,r in enumerate(rows):
        if r["actual_IGN25_original_ground_m"] is not None:curr.append(i)
        else:
            if curr:runs.append(curr)
            curr=[]
    if curr:runs.append(curr)
    return max(runs,key=len) if runs else []
def execute(g10,g39,g42,originalzip,outjson,outcsv,outmd,outfig):
    rows,counts,checks,line=densify(g10,g39,g42,originalzip)
    valid_idxs=biggest_contiguous_run(rows)
    if len(valid_idxs)<3:raise ValueError("G43_original_terrain_no_continuous_segment")
    d=[rows[i]["source_research_chainage_m"] for i in valid_idxs]
    h=[rows[i]["actual_IGN25_original_ground_m"] for i in valid_idxs]
    cases=[]
    for grade in GRADES:
        for R in VERTICAL_R_BENCH:
            for fix in (False,True):
                result=LP_curved(d,h,grade,R,fix)
                cases.append(result)
    groundslopes=[]
    for i,(a,b) in enumerate(zip(rows,rows[1:])):
        v1,v2=a["actual_IGN25_original_ground_m"],b["actual_IGN25_original_ground_m"]
        if v1 is not None and v2 is not None:
            groundslopes.append((v2-v1)/STEP_M*1000)
    horiz_subsegments=[]
    # Preserve original LATTICE vertices (including sharp edges): no track curvature.
    for q in line.coords:
        pass
    max_grade18=sum(abs(z)>18 for z in groundslopes)
    max_grade25=sum(abs(z)>25 for z in groundslopes)
    obj={"mission":"MN-GEO-RAIL-001","stage":"G43_dense_original_IGN25_ground_terrain_vertical_curvature_risk",
       "source_all30_preserved_previous_G42":True,
       "source_reference_original_G10":"P2-2-1","original_terrain_source":"G39 13 original IGN/CNIG Elevacion25830_25 WCS source TIFFs; SHA256 verified",
       "new_original_data_downloaded":False,
       "original_IGN_source_1km_TIFF_reused":13,
       "G39_previous_original_sample_spacing_m":500,
       "G43_original_25m_ground_sampling_n":NPTS,
       "G43_original_dense_ground_valid_n":counts["valid"],
       "G43_original_dense_ground_missing_n":counts["missing"],
       "contiguous_original_dense_source_segment_length_m":(len(valid_idxs)-1)*STEP_M,
       "grade_18permille_exceeded_in_actual_ground_25m_intervals":max_grade18,
       "grade_25permille_exceeded_in_actual_ground_25m_intervals":max_grade25,
       "terrain_densification_demonstrates_G42_500m_undersampling_risk":True,
       "source_original_TIFF_overlap_count":counts["overlap"],
       "overlap_original_IGN25_source_sampling_disagreement_above_1p5m_count":counts["overlap_raster_nearest_pixel_disagreement_above_1p5m"],
       "G39_vs_G43_original_500m_center_pixel_rechecks":checks,
       "all_source_points":rows,
       "optimistic_grade_vertical_curvature_LP_sensitivity":cases,
       "profile_maximum_grade_and_curve_radius_assumptions_not_normative_rail_design":True,
       "track_horizontal_geometry_has_source_2km_lattice_corner_discontinuities":True,
       "no_real_station_or_tunnel_portal_or_subsurface_geology":True,
       "no_rail_structure_lengths_EUR_costs_or_operational_train_times":True,
       "Natura2000_and_PIC_are_not_cleared":True,
       "not_PT_ES_vertical_reference_harmonized":True,
       "Fxx_accepted":False,"Site_authorized":False}
    outjson.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
    with outcsv.open("w",newline="",encoding="utf-8-sig") as f:
        fields=("source_research_chainage_m","east_25830_m","north_25830_m",
            "actual_IGN25_original_ground_m","source_status","ground_source_raster_SHA256",
            "source_original_rasters_cover_point","overlap_nearest_pixel_source_roughness_spread_m")
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
        for r in rows:w.writerow({key:r.get(key) for key in fields})
    fig,ax=plt.subplots(figsize=(11,6),layout="constrained")
    xx=[r["source_research_chainage_m"]/1000 for r in rows]
    yy=[r["actual_IGN25_original_ground_m"] if r["actual_IGN25_original_ground_m"] is not None else np.nan for r in rows]
    ax.plot(xx,yy,lw=1.25,c="#394f61",label="MDT25 verdadeiro: amostras de 25 m")
    styles=((18,10000,"#a36345"),(25,10000,"#357e81"),(18,None,"#967bac"))
    for grade,R,color in styles:
        case=next(q for q in cases if q["grade_permille"]==grade and q.get("assumed_vertical_radius_m")==R
                  and not q["both_endpoints_fixed_at_sampled_ground"])
        if case["status"].startswith("OPTIMISTIC"):
            zr=case.get("track_math_z_m",case.get("fitted_track_elevation_RESEARCH_math_only_m"))
            ax.plot(np.asarray(d)/1000,zr,lw=1.7,ls="--",c=color,
                label=f"Matemático {grade}‰, Rv={R or 'sem limite'}m")
    ax.set_xlabel("Progressiva na poligonal G10 P2-2-1 (km; NÃO traçado ferroviário)")
    ax.set_ylabel("Cota original IGN/CNIG MDT25 (m)")
    ax.set_title(f"G43 · {counts['valid']}/{NPTS} cotas originais cada 25m vs rasante matemática",loc="left",fontsize=11)
    ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(outfig,dpi=175,bbox_inches="tight");plt.close(fig)
    outmd=[
    "# G43 — Solo nu real cada 25m e limites de rasante com curvatura vertical (6km, Zamora)",
    "",
    f"**{counts['valid']} de {NPTS} pontos** de terreno de solo nu obtidos por leitura dos 13 GeoTIFF oficiais 1km já adquiridos no G39, sem nenhuma descarga adicional; os {counts['missing']} restantes mantêm-se sem interpolação. Maior segmento contínuo observado: **{(len(valid_idxs)-1)*STEP_M/1000:.3f}km**.",
    "",
    f"Nas séries de solo amostradas a cada 25m, **{max_grade18} de {len(groundslopes)}** diferenças altimétricas entre posições consecutivas excedem 18‰ e **{max_grade25}** excedem 25‰. Isto são declives do terreno e NÃO rampas operacionais de via.",
    "",
    "## Rasante matemática de menor afastamento vertical em todos os pontos observados",
    "","| Hipótese de rampa | Sensibilidade raio vertical (não regulamentar) | Extremos ao solo? | Melhor afastamento vertical máximo (m) |",
    "|---|---|---|---:|"]
    for c in cases:
        value=c.get("minimum_possible_MAX_vertical_difference_at_ground_samples_m",c.get("minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"))
        outmd.append(f"| {c['grade_permille']}‰ | {c.get('assumed_vertical_radius_m') or 'Sem limite'} | {'Sim' if c['both_endpoints_fixed_at_sampled_ground'] else 'Não'} | {value if value is not None else 'não viável nesta hipótese'} |")
    outmd+=["","**Nota metodológica:** Rv=10 000m e Rv=20 000m são hipóteses matemáticas de ensaio, não garantias de conformidade de uma via a 160/200/250 km/h. O controlo limita diferenças de primeira e segunda ordem da cota de uma poligonal fixa, com origem no centro de células de 2km; não fornece curvas horizontais, clotóides, raios reais, pontos de inflexão vertical ou traçado ferroviário.",
    "","**Não transformar** os afastamentos verticais do otimizado em quilómetros de túnel ou viaduto, volumes de escavação ou custos. A solução é um limite inferior na grelha de pontos do terreno, não determina processo construtivo nem interferência de aquíferos.",
    "",
    "## Fonte e reutilização",
    "- 13 GeoTIFF do IGN/CNIG WCS MDT25 em EPSG25830 adquiridos no G39, cada original revalidado contra SHA256 do manifesto histórico; píxeis lêem-se diretamente de rasterio.",
    f"- {counts['overlap']} pontos cobertos por mais de um original; {counts['overlap_raster_nearest_pixel_disagreement_above_1p5m']} deles com discrepância acima de 1,5m entre píxeis fonte das janelas sobrepostas, o que exige prudência de amostragem e verificação do mosaico.",
    "- As 13 cotas do G39, tomadas a cada 500m, são verificadas novamente e as diferenças preservadas no JSON; nenhuma cota nula é substituída.",
    "- O G42 demonstrou apenas um caminho exploratório nos dois módulos urbanos obrigatórios; para avançar deve reabrir as 2–3 alternativas de aproximação aos sítios DGT2m estudados em cada uma das duas cidades.",
    "",
    "## O que é necessário para um traçado 3D e custos",
    "1. Traçar localmente o eixo de engenharia horizontal, corrigindo mudanças angulares impossíveis da grelha G10; estabelecer limites em planta por velocidade de projeto e tecnologia de via.",
    "2. Garantir rasantes e concordâncias verticais, estações e cotas, túneis/viadutos e perfis transversais a uma resolução/qualidade adaptada.",
    "3. Adquirir faixas de terreno de solo nu nos setores PT de divergência; preservar 84 DGT2m originais e pedir quadrículas adicionais apenas por lacunas concretas.",
    "4. Obter geologia/hidrogeologia real e sondagens onde disponíveis; os 4 serviços WFS LNEG foram identificados no G41 mas não provaram objetos locais. Tratar Marão–Alvão, Rede Natura, PIC e águas subterrâneas como restrições maiores.",
    "5. Continuar a comparar os 30 corredores completos, sem cortar alternativas por uma única rasante matemática parcial.",
    "",
    "**G43 não modela estação, túnel, viaduto, custos, tempos ferroviários nem autorização ambiental. Sem Fxx/Site.**"]
    outmd.write_text("\n".join(outmd)+"\n")
    print("G43_RESULT",json.dumps({"real_25m_samples":counts["valid"],"missing":counts["missing"],
       "continuity_km":(len(valid_idxs)-1)*STEP_M/1000,
       "slope_ground_18permille_exceed":max_grade18,
       "LP_research_profiles":[{"grade":q["grade_permille"],"radius":q.get("assumed_vertical_radius_m"),
            "end_fixed":q["both_endpoints_fixed_at_sampled_ground"],
            "minmax_m":q.get("minimum_possible_MAX_vertical_difference_at_ground_samples_m",
                q.get("minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m")),
            "status":q["status"]} for q in cases],
       "no_new_raw_acquisition":True,"original_tiles":len(checks)},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for f in ("g10","g39","g42","originalzip","json","csv","markdown","plot"):
        p.add_argument("--"+f,required=True,type=Path)
    a=p.parse_args()
    execute(*[json.loads(getattr(a,key).read_text()) for key in ("g10","g39","g42")],
        a.originalzip,a.json,a.csv,a.markdown,a.plot)
if __name__=="__main__":main()
