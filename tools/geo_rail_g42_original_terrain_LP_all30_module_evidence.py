#!/usr/bin/env python3
"""G42 first measured constrained-grade railway vertical RESEARCH envelope and
complete 30-route module-degeneracy analysis.

G39 exact 13 native 25m IGN/CNIG ground values at 500m; G40 exact 36 source
values at 5km (27 original source TIFF, nine verified identical site reuses).
Solve a linear-programming necessary-condition profile on *research-lattice*
sample chainage with grade limits 18/25 permille. It is an optimistic best
mathematical fit to sparse surface points, NOT a rail alignment, tunnels,
bridge lengths, cuts/fill volumes or timetable. Show endpoints tied and free.

Also break 27+3 source 2km lattice routes into five geographic modules using
the four original mandatory-city source-grid anchors, preserving all30 and
finding shared pieces and highest geographic differentiation. No DGT download.
"""
import argparse,collections,csv,hashlib,json,math
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer
from shapely.geometry import LineString,Point
ANCHORS=((21000.,181000.),(41000.,185000.),(111000.,235000.),(117000.,239000.))
SEGMENTS=("AFSC_to_Vila_Real_W","Vila_Real_local_W_to_E",
          "Vila_Real_E_to_Braganca_W","Braganca_local_W_to_E","Braganca_E_to_Zamora")
GRADES=(18,25)
CENSORED="UNKNOWN_NOT_RAILWAY_3D_ENGINEERING"
TO_PT=Transformer.from_crs(4326,3763,always_xy=True)
def canonical_point(p):
    # Original 2km grid centres are defined as 1000m+2000n.
    x,y=TO_PT.transform(*p)
    px=round((x-1000)/2000)*2000+1000
    py=round((y-1000)/2000)*2000+1000
    if math.dist((x,y),(px,py))>12:raise ValueError("G42_original_geographic_study_2km_cell_source_drift")
    return(int(px),int(py))
def route_parts(g10,g30,g36,g35):
    fs=g10["features"]+g30["features"]
    ids=[f["properties"]["id"] for f in fs]
    orig={"P"+str(a)+"-"+str(b)+"-"+str(c) for a in range(1,4) for b in range(1,4) for c in range(1,4)}
    new={"G30-avoid_surface_overlap","G30-potential_deep_tunnel","G30-geographic_diversity"}
    if len(fs)!=30 or set(ids)!=(orig|new):raise ValueError("G42_REQUIRE_27_ORIGINAL_AND_3_NEW")
    if g36["source_all_original_G10_count"]!=27 or g36["source_all_original_G30_count"]!=3 or g36["rows_n"]!=90:
        raise ValueError("G42_REQUIRE_PREVIOUS_ALL90")
    if (g35["G10_all_routes"]!=27 or g35["G30_all_routes"]!=3 or
        g35["original_DGT2m_COS2025_road_study_coordinate_sites"]!=7 or
        len(g35["comparisons_all30_times_two_mandatory_cities"])!=60):
        raise ValueError("G42_REQUIRE_OLD_ACTUAL_STATION_STUDY")
    groups={k:[] for k in SEGMENTS};cases=[]
    for feat in fs:
        id=feat["properties"]["id"]
        path=[canonical_point(p) for p in feat["geometry"]["coordinates"]]
        if len(path)!=len(set(path)) or len(path)<35:raise ValueError("G42_SOURCE_UNEXPECTED_PATH")
        ix=[]
        for anchor in ANCHORS:
            if anchor not in path:raise ValueError("G42_MANDATORY_CITY_SOURCE_ANCHOR_MISSING_"+id)
            ix.append(path.index(anchor))
        if ix!=sorted(ix) or len(set(ix))!=4 or min(ix)==0 or max(ix)==len(path)-1:
            raise ValueError("G42_INVALID_4_CITY_ANCHOR_ORDER_"+id)
        cuts=[0]+ix+[len(path)-1]
        subs=[]
        for k,a,b in zip(SEGMENTS,cuts[:-1],cuts[1:]):
            sub=path[a:b+1]
            if len(sub)<2:raise ValueError("G42_EMPTY_MODULE")
            if any(math.dist(x,y)>2830 for x,y in zip(sub,sub[1:])):
                raise ValueError("G42_SOURCE_STEP_LARGER_THAN_ORIGINAL_2KM_LATTICE")
            edges=frozenset(tuple(sorted((a,b))) for a,b in zip(sub,sub[1:]))
            groups[k].append((id,tuple(sub),edges))
            subs.append({"name":k,"length_research_grid_km":round(sum(math.dist(x,y) for x,y in zip(sub,sub[1:]))/1000,3),
                         "source_2km_grid_cells":len(sub)})
        cases.append({"id":id,"family":"G30" if id.startswith("G30-") else "G10",
                      "five_research_source_modules":subs,
                      "all_route_source_length_research_km":round(sum(q["length_research_grid_km"] for q in subs),3)})
    table=[];source_footprint={}
    for sector,items in groups.items():
        unique_paths={i[1] for i in items}
        edge_groups={frozenset(it[2]) for it in items}
        common=set.intersection(*(set(i[2]) for i in items))
        un=set.union(*(set(i[2]) for i in items))
        unique_edge_bundles=len(edge_groups)
        all_lengths=[sum(math.dist(a,b) for a,b in zip(p,p[1:]))/1000 for _,p,_ in items]
        # Differences between route families calculated on edge geometry only,
        # not generic research corridor names.
        for route_id,path,edges in items:
            source_footprint[(route_id,sector)]={"edge_set":edges,"path":path}
        table.append({"sector":sector,"routes":30,
             "distinct_spatial_source_lattice_paths":len(unique_paths),
             "unique_undirected_edge_bundles":unique_edge_bundles,
             "edges_shared_by_all30":len(common),
             "edges_in_union_of_all30":len(un),
             "common_edge_fraction_of_union":round(len(common)/len(un),5) if un else None,
             "original_grid_length_min_km":round(min(all_lengths),3),
             "original_grid_length_max_km":round(max(all_lengths),3),
             "source_30_repeated_modules_not_30_independent_engineered_routes":True})
    comparison=[]
    for id in sorted(ids):
        m={}
        for name in SEGMENTS:
            own=source_footprint[(id,name)]["edge_set"]
            others=[j for j in ids if j!=id]
            best=max(((len(own&source_footprint[(j,name)]["edge_set"])/len(own|source_footprint[(j,name)]["edge_set"])
                  if (own|source_footprint[(j,name)]["edge_set"]) else 1.,j) for j in others),key=lambda v:v[0])
            m[name]={"max_Jaccard_overlap_with_other_route":round(best[0],5),
                "source_nearest_other_route":best[1]}
        comparison.append({"option_id":id,"sectors":m})
    return table,cases,comparison,source_footprint
def lp_best_vertical_envelope(distances_m,ground_m,grade_permille,fix_ends=False):
    d=np.asarray(distances_m,dtype=float);h=np.asarray(ground_m,dtype=float)
    if len(d)<3 or len(d)!=len(h) or not np.all(np.isfinite(h)) or not np.all(np.diff(d)>0):
        raise ValueError("G42_NO_MISSING_TERRAIN_IMPUTATION")
    n=len(d);lim=grade_permille/1000.
    # x = n track elevations, plus scalar t >= max |track-ground|;
    # no endpoint or station artificially assumed unless explicit sensitivity.
    obj=np.zeros(n+1);obj[-1]=1.
    A=[];b=[]
    for i in range(n):
        a=np.zeros(n+1);a[i]=1;a[-1]=-1
        A.append(a);b.append(h[i])
        a=np.zeros(n+1);a[i]=-1;a[-1]=-1
        A.append(a);b.append(-h[i])
    for i,dx in enumerate(np.diff(d)):
        for sign in (-1,1):
            a=np.zeros(n+1);a[i]=sign;a[i+1]=-sign
            A.append(a);b.append(lim*dx)
    bounds=[(None,None)]*n+[(0,None)]
    if fix_ends:
        bounds[0]=(float(h[0]),float(h[0]))
        bounds[n-1]=(float(h[-1]),float(h[-1]))
    sol=linprog(obj,A_ub=np.asarray(A),b_ub=np.asarray(b),
       bounds=bounds,method="highs")
    if not sol.success:
        return {"status":"NO_SOLUTION_UNDER_THIS_BOTH_ENDS_TIED_GRADE_TEST",
             "grade_permille":grade_permille,"both_endpoints_fixed_at_sampled_ground":fix_ends,
             "not_project_railway_infeasible":True}
    z=sol.x[:n];t=float(sol.x[-1])
    if np.max(np.abs(np.diff(z)/np.diff(d)*1000))>grade_permille+1e-4:
        raise ValueError("G42_LP_GRADE_AUDIT_FAIL")
    if np.max(abs(z-h))>t+1e-4:raise ValueError("G42_LP_ENVELOPE_AUDIT_FAIL")
    return {"status":"OPTIMISTIC_LP_MATHEMATICAL_PROFILE_ONLY",
      "grade_permille":grade_permille,
      "both_endpoints_fixed_at_sampled_ground":fix_ends,
      "minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m":round(t,3),
      "fitted_track_elevation_RESEARCH_math_only_m":[round(float(v),3) for v in z],
      "ground_minus_math_rail_level_at_samples_m":[round(float(a-b),3) for a,b in zip(h,z)],
      "max_absolute_fitted_grade_permille":round(float(np.max(np.abs(np.diff(z)/np.diff(d)*1000))),4),
      "does_not_calculate_tunnel_bridge_meters_or_earthwork_volumes":True,
      "only_necessary_condition_no_vertical_curves_acceleration_station_constraints":True}
def terrain_cases(g39,g40):
    if (g39["validated_original_WCS_MDT25_source_points"]!=13 or
        g39["original_WCS_failed_points_not_imputed"]!=0 or
        g40["original_source_terrain_locations_measured_even_if_reused"]!=36 or
        g40["source_WCS_duplicate_queries_avoided"]!=9 or
        g40["actual_IGN_source_original_TIFF_verified_count"]!=27):
        raise ValueError("G42_SOURCE_ACTUAL_G39_G40_NOT_VERIFIED")
    groups=[]
    gr39=g39["source_point_sampled_values"]
    d39=[(x["distance_from_source_endpoint_km"]+6)*1000 for x in gr39]
    h39=[x["official_IGN_MD25_original_sample_elevation_m"] for x in gr39]
    groups.append(("G39_P2-2-1_Zamora_last6km_500m",d39,h39,
       "13 actual native source samples, 500m, eastern 6km G10 research grid"))
    for key in ("P1-2-1","G30-avoid_surface_overlap","G30-potential_deep_tunnel","G30-geographic_diversity"):
        samples=[r for r in g40["source_original_25m_samples_and_sha256"] if r["option_id"]==key]
        samples.sort(key=lambda r:r["study_grid_distance_from_Zamora_end_km"])
        if len(samples)!=9:raise ValueError("G42_G40_9_SAMPLES_EACH")
        d=[(r["study_grid_distance_from_Zamora_end_km"]+55)*1000 for r in samples]
        h=[r["original_IGN_25m_elevation_m"] for r in samples]
        groups.append(("G40_"+key+"_sparse40km_5km",d,h,
          "9 actual samples every 5km; cannot screen sub-5km relief/rail structures"))
    result=[]
    for id,dist,ground,method in groups:
        if any(v is None for v in ground):raise ValueError("G42_SOURCE_MISSING_ELEVATION")
        checks=[]
        for grade in GRADES:
            for fixed in (False,True):
                checks.append(lp_best_vertical_envelope(dist,ground,grade,fixed))
        result.append({"observed_source_profile_id":id,
           "sample_source_method":method,"sample_n":len(ground),
           "length_ground_sample_chainage_km":round((max(dist)-min(dist))/1000,3),
           "actual_IGN25_bareearth_sampled_elevation_minmax_m":[min(ground),max(ground)],
           "ground_values_m":ground,"distance_from_profile_start_m":dist,
           "two_speed_independent_slope_assumptions_permille":list(GRADES),
           "grade_constrained_mathematical_optimistic_LP_tests":checks})
    # Exact identical source geometry in eastern sector, same original data
    b=result[2]["ground_values_m"];c=result[3]["ground_values_m"]
    if b!=c:raise ValueError("G42_G30_ORIGINAL_SOURCE_SAME_GROUND_NOT_REUSED")
    return result
def figures(profile,sector_table,heatout,profileout):
    names=[x["sector"].replace("_"," ") for x in sector_table]
    fig,ax=plt.subplots(figsize=(10,4),layout="constrained")
    x=np.arange(5)
    ax.bar(x,[q["distinct_spatial_source_lattice_paths"] for q in sector_table])
    ax.set_xticks(x,names,rotation=20,ha="right",fontsize=8)
    ax.set_ylabel("Poligonais espacialmente distintas / 30 alternativas")
    ax.set_title("G42 · 30 opções: módulos realmente distintos (sem engenharia ferroviária)",loc="left")
    ax.set_ylim(0,31);ax.grid(axis="y",alpha=.2);fig.savefig(heatout,dpi=160,bbox_inches="tight");plt.close(fig)
    q=profile[0]
    x=np.array(q["distance_from_profile_start_m"])/1000
    fig,ax=plt.subplots(figsize=(11,5.5),layout="constrained")
    ax.plot(x,q["ground_values_m"],"o-",lw=2,color="#353e55",label="IGN MDT25: solo nu observado")
    schemes=[("18‰, extremidades livres","#3b79a2",False,18),
             ("25‰, extremidades livres","#b57b38",False,25),
             ("18‰, extremidades ao solo","#a04f6e",True,18)]
    for label,color,fix,grade in schemes:
        r=next(v for v in q["grade_constrained_mathematical_optimistic_LP_tests"]
               if v["grade_permille"]==grade and v["both_endpoints_fixed_at_sampled_ground"]==fix)
        if r["status"]=="OPTIMISTIC_LP_MATHEMATICAL_PROFILE_ONLY":
            ax.plot(x,r["fitted_track_elevation_RESEARCH_math_only_m"],ls="--",
                    lw=1.6,color=color,label=label)
    ax.set_title("G42 · Zamora, 6km: limites matemáticos de rasante vs terreno verdadeiro",loc="left")
    ax.set_xlabel("Progressiva nos últimos 6 km da linha de grelha G10 P2-2-1 (km)")
    ax.set_ylabel("Cota (m; datum IGN não harmonizado com Portugal)")
    ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(profileout,dpi=160,bbox_inches="tight");plt.close(fig)
def run(g10,g30,g36,g35,g39,g40,jout,csvout,mdout,partfig,vertfig):
    table,src,comparison,footprint=route_parts(g10,g30,g36,g35)
    surface=terrain_cases(g39,g40)
    figures(surface,table,partfig,vertfig)
    # source-verified spatial identity of G30 variants only on eastern portion,
    # do not claim identical profiles in the full route.
    obj={"mission":"MN-GEO-RAIL-001","stage":"G42_30_route_five_geographic_modules_and_native_G39_G40_grade_LP",
     "original_G10_27_G30_3_preserved":True,"original_count":30,"research_velocity_screen_speeds":[160,200,250],
     "observed_source_ground_profiles":len(surface),
     "original_IGN_ground_samples_all_cases":49,
     "original_IGN_G40_distinct_source_TIFF_reused":27,
     "original_G35_seven_physical_studies_reused_not_redesigned":True,
     "four_city_study_anchors_in_PT_Tm06_center":ANCHORS,
     "source_30_options_geographic_five_module_summary":table,
     "full30_individual_five_segment_research_geometry":src,
     "all30_by_sector_closest_geometry_undirected_Jaccard":comparison,
     "G39_500m_plus_G40_5km_measured_bareearth_constrained_vertical_optimistic_only":surface,
     "G30_avoid_and_tunnel_east_identical_sample_ground_not_independent_rail_design":True,
     "no_earthwork_structure_quantities_or_time_CAPEX":True,
     "no_station_3D_horizontal_radius_checked_here":True,
     "no_vertical_curves_or_geology_or_water_Natura_PIC_clearance":True,
     "no_new_original_source_data_acquired":True,
     "source_DGT84_reusable_no_new_tiles":True,
     "PT_ES_altimetric_datum_unharmonized":True,
     "Fxx_accepted":False,"Site_authorized":False}
    jout.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
    with csvout.open("w",newline="",encoding="utf-8-sig") as out:
        fields=("sector","routes","distinct_spatial_source_lattice_paths","edges_shared_by_all30",
         "edges_in_union_of_all30","common_edge_fraction_of_union",
         "original_grid_length_min_km","original_grid_length_max_km")
        w=csv.DictWriter(out,fieldnames=fields,delimiter=";");w.writeheader()
        for r in table:w.writerow({k:r.get(k) for k in fields})
    a=surface[0]
    lines=["# G42 — Geometria realmente independente e primeira rasante matemática baseada em terreno verdadeiro",
     "","**Avanço de engenharia exploratória, não projeto ferroviário:** os 30 corredores G10/G30 foram decompostos nos 5 módulos espaciais originais (AFSC–Vila Real, conector de Vila Real, Vila Real–Bragança, conector de Bragança, Bragança–Zamora). Foram resolvidos problemas de otimização linear de uma **rasante matemática** limitada a 18‰ e 25‰ sobre as **cotas originais IGN MDT25** já adquiridas. Continuam por justificar raio em planta, clotóides, curvas verticais, posição da estação, volume e tipo de escavação, passagens de água, custos e tempos comerciais.",
      "","## 1. Até que ponto as 30 alternativas são geométricas distintas por setor?",
      "","| Módulo de investigação | Poligonais distintas (em 30) | Arestas comuns a todas | Arestas da união | Extensão de grelha mínima–máxima (km) |",
      "|---|---:|---:|---:|---|"]
    for q in table:
        lines.append(f"| {q['sector']} | {q['distinct_spatial_source_lattice_paths']} | {q['edges_shared_by_all30']} | {q['edges_in_union_of_all30']} | {q['original_grid_length_min_km']}–{q['original_grid_length_max_km']} |")
    lines+=["","O desdobramento em cinco módulos evita confundir combinações de 27 rotas com 27 soluções de engenharia totalmente independentes. Os dois setores urbanos obrigatórios reutilizam os mesmos pontos e os locais de estudo de estação G35; isso é **cobertura de serviço exploratória comum, não qualidade ferroviária aprovada**.",
        "","## 2. Teste vertical 6 km de Zamora: otimização linear com MDT25 original",
        "","A rasante minimiza **o maior afastamento vertical absoluto** dos 13 pontos do terreno original (passo 500m), com \u007c\u0394z/\u0394s\u007c ≤ 18‰ ou 25‰. A solução com extremidades livres constitui limite inferior de afastamento entre pontos amostrados. O ensaio com extremidades fixadas à cota do terreno nos dois extremos é apenas outra hipótese matemática (não plataformas de estação). Não inclui curvas verticais, rampas de aproximação ou condicionantes geotécnicas.",
        "","| Gradiente matemático máximo | Extremidades | Melhor afastamento vertical máximo aos 13 pontos de solo nu (m) | Estado |",
        "|---|---|---:|---|"]
    for q in a["grade_constrained_mathematical_optimistic_LP_tests"]:
        delta=q.get("minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m")
        lines.append(f"| {q['grade_permille']}‰ | {'Fixadas à cota do solo' if q['both_endpoints_fixed_at_sampled_ground'] else 'Livres'} | {delta if delta is not None else 'N/D'} | {q['status']} |")
    lines+=["","**Esta diferença não pode ser multiplicada pela extensão do corredor para calcular túneis/viadutos/terraplenagens.** É um limite inferior para uma linha matemática de declive limitado nos pontos amostrados, com posição horizontal fixa na grelha de estudo. As cotas não foram verificadas entre amostras, e o MDS regional não corrige estas lacunas.",
        "","## 3. Quatro perfis orientais G40 — controle de cobertura e redundância",
        "","| Hipótese | Pontos originais | Intervalo observado (m) | Melhor afastamento máximo (18‰, extremidades livres, m) |",
        "|---|---:|---|---:|"]
    for q in surface[1:]:
        fit=next(v for v in q["grade_constrained_mathematical_optimistic_LP_tests"] if v["grade_permille"]==18 and not v["both_endpoints_fixed_at_sampled_ground"])
        lines.append(f"| {q['observed_source_profile_id']} | {q['sample_n']} | {q['actual_IGN25_bareearth_sampled_elevation_minmax_m']} | {fit.get('minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m','N/D')} |")
    lines+=["","**Os 9 pontos orientais dos dois modos G30 de túnel e evitamento da superfície são idênticos.** Os respetivos resultados não são evidência independente. Entre os pontos G40 existem 5 km sem observação, logo qualquer menor afastamento vertical nos testes G40 é muito otimista para determinar obras.",
       "","## 4. Próxima faixa de desenho e aquisição dirigida",
       "","1. Usar a decomposição G42 de setores realmente distintos para obter no máximo 2–3 **perfis contínuos** de terreno representativos num setor crítico, sem adquirir novamente segmentos coincidentes.",
       "2. Para cada aproximação a Vila Real/Bragança, conservar as sete posições DGT2m anteriormente ensaiadas; construir e testar 2–3 eixos 3D com curvas de transição, plataformas e geometrias de acesso rodoviário.", 
       "3. Nas faixas portuguesas, verificar mosaicos do MDT DGT 2m já arquivado e obter poucos blocos adicionais apenas depois de localizar o conflito; na Espanha, alargar WCS a intervalos <500m onde os perfis forem distintos.",
       "4. Obter cartografia geológica local real (LNEG WFS com formatos GML e/ou raster por folhas), validar água subterrânea, falhas, hidrogeologia, Natura 2000, portais e **PIC** ainda não cartografado.",
       "5. Só com traçado 3D, condicionantes e estruturas justificadas calcular tempos 160/200/250 km/h e custos com intervalos de incerteza e comparar os 30 casos sem eliminar alternativas prematuramente.",
       "","**Portão: G42 acrescenta uma restrição matemática real sobre solo nu; não comprova um metro de ferrovia em túnel, viaduto, expropriação ou rasante operacional. Sem Fxx/Site.**"]
    mdout.write_text("\n".join(lines)+"\n")
    print("G42_RESULT",json.dumps({"sector_diversity":table,
         "G39_optimistic_grade_results":a["grade_constrained_mathematical_optimistic_LP_tests"],
         "four_G40_18permille_best":{q["observed_source_profile_id"]:next(v["minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"] for v in q["grade_constrained_mathematical_optimistic_LP_tests"] if v["grade_permille"]==18 and not v["both_endpoints_fixed_at_sampled_ground"]) for q in surface[1:]},
         "all30_retained":True,"no_new_data":True},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for f in ("g10","g30","g36","g35","g39","g40","json","csv","markdown","segments","profile"):
        p.add_argument("--"+f,required=True,type=Path)
    a=p.parse_args()
    run(*[json.loads(getattr(a,f).read_text()) for f in ("g10","g30","g36","g35","g39","g40")],
      a.json,a.csv,a.markdown,a.segments,a.profile)
if __name__=="__main__":main()
