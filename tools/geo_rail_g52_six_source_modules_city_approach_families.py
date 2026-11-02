#!/usr/bin/env python3
"""G52: turn G51 high-priority 8 + G30 deep-tunnel into a deliberately diverse
set of 6 original-source geographical *families* for subsequent 3D design.

Reuses original 27 G10 +3 G30 geographic source research lines, G42 five
explicit anchor-delimited 2km lattice modules, G45 630 original station
geometry tests, G51 functional 12.5/15mm/m top8 research prioritisation.

No smoothing is misrepresented as railway centerline; site approaches are
separate research hypotheses, no continuity guaranteed at original anchors.
No acquisition; retain full30 and mandatory VR/BR stations; no Sanabria.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sys
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import LineString
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g42_original_terrain_LP_all30_module_evidence import ANCHORS,SEGMENTS,canonical_point

DIFF_SECTORS=(SEGMENTS[0],SEGMENTS[2],SEGMENTS[4])
SITES={"Vila_Real":("VR1","VR2"),"Braganca":("BR3","BR4")}
ESG=Transformer.from_crs(3763,4326,always_xy=True)
TOP_REPS=6
DEEP="G30-potential_deep_tunnel"
def split_one(f):
    path=[canonical_point(p) for p in f["geometry"]["coordinates"]]
    if len(path)!=len(set(path)) or len(path)<35:raise ValueError("G52_original_geographic_route_source_corrupt")
    ids=[]
    for city in ANCHORS:
        if city not in path:raise ValueError("G52_original_vr_or_braganca_anchor_missing")
        ids.append(path.index(city))
    if sorted(ids)!=ids or len(set(ids))!=4:raise ValueError("G52_original_crossing_order_invalid")
    cuts=[0]+ids+[len(path)-1]
    res={}
    for name,a,b in zip(SEGMENTS,cuts[:-1],cuts[1:]):
        p=path[a:b+1]
        edges=tuple(sorted(tuple(sorted((u,v))) for u,v in zip(p,p[1:])))
        sig=hashlib.sha256(json.dumps(edges,separators=(",",":")).encode()).hexdigest()[:12]
        res[name]={"study_cells_PT_TM06":len(p),
            "study_length_2km_grid_km":round(sum(math.dist(u,v) for u,v in zip(p,p[1:]))/1000,3),
            "source_grid_edge_digest":sig,"paths_grid_original_PT_TM06":p}
    return res
def derive(g10,g30,g42,g45,g51):
    ff=g10["features"]+g30["features"]
    if len(ff)!=30 or len({f["properties"]["id"] for f in ff})!=30:raise ValueError("G52_all30_source_paths")
    if not g42["original_G10_27_G30_3_preserved"] or g42["original_count"]!=30:raise ValueError("G52_original_G42_30_contract")
    if not g45["all_G10_27_and_G30_3_retained"] or len(g45["all_630_route_site_speed_horizontal_screen_cases"])!=630:
        raise ValueError("G52_original_G45_630_contract")
    if not g51["original_30_G10_27_G30_3_untouched"] or g51["research_sensitivity_tests_5grades_x_3speeds_x_4weight_profiles"]!=60:
        raise ValueError("G52_original_G51_12p5_15_30_contract")
    full={f["properties"]["id"]:split_one(f) for f in ff}
    reference={r["id"]:r for r in g42["full30_individual_five_segment_research_geometry"]}
    if set(reference)!=set(full):raise ValueError("G52_G42_source_all30_not_same")
    for id,sectors in full.items():
        for old in reference[id]["five_research_source_modules"]:
            new=sectors[old["name"]]
            if abs(new["study_length_2km_grid_km"]-old["length_research_grid_km"])>.02:
                raise ValueError("G52_G42_true_geographic_path_length_changed_"+id)
    summary={r["sector"]:r for r in g42["source_30_options_geographic_five_module_summary"]}
    for s in (SEGMENTS[1],SEGMENTS[3]):
        if summary[s]["distinct_spatial_source_lattice_paths"]!=1:raise ValueError("G52_city_grid_old_fixed_module_changed")
    original_rank={r["option_id"]:r for r in g51["full30_source_only_mixed_vs_passenger_selection_sensitivity"]}
    if set(original_rank)!=set(full):raise ValueError("G52_priority_not_cover_all30")
    priority=g51["research_only_next_terrain_alignment_acquisition_priority"]
    first=priority["mixed_grade_source_only_8_for_priority_original_DTM_engineering"]
    if len(first)!=8 or DEEP in first and priority["extra_deep_tunnel_requires_geology_before_exclusion"]:
        raise ValueError("G52_old_G51_priority_contract")
    nine=list(dict.fromkeys(first+[DEEP]))
    if len(nine) not in (8,9) or not set(nine)<=set(full):raise ValueError("G52_nine_source_research_coverage")
    station={(r["option_id"],r["historical_site_id"],r["illustrative_speed_label_kmh"]):r
            for r in g45["all_630_route_site_speed_horizontal_screen_cases"]}
    if len(station)!=630:raise ValueError("G52_station_630_not_unique")
    # Greedy deterministic source diversity: prioritize alternatives carrying
    # currently unseen distinct modules, then mixed original top8 frequency.
    # These six are *sampling design*, not a claim of a globally optimal rail.
    chosen=[DEEP,first[0]] if first[0]!=DEEP else [DEEP]
    def units(id):return {(s,full[id][s]["source_grid_edge_digest"]) for s in DIFF_SECTORS}
    while len(chosen)<min(TOP_REPS,len(nine)):
        done=set().union(*(units(r) for r in chosen))
        left=[id for id in nine if id not in chosen]
        def key(id):
            new=units(id)-done
            hits=original_rank[id]["mixed_grade_total_top8_hits_across_24_research_tests"]
            return (len(new),sum(3 if s==SEGMENTS[0] else 2 for s,v in new),
                    hits,-first.index(id) if id in first else -999)
        chosen.append(max(left,key=key))
    nine_unique={s:len({full[id][s]["source_grid_edge_digest"] for id in nine}) for s in DIFF_SECTORS}
    six_unique={s:len({full[id][s]["source_grid_edge_digest"] for id in chosen}) for s in DIFF_SECTORS}
    coverage={s:{"shortlist_9_spatial_modules":nine_unique[s],
                  "six_sample_representatives_modules":six_unique[s],
                  "fraction_of_shortlist_spatial_diversity_covered":round(six_unique[s]/nine_unique[s],3)}
             for s in DIFF_SECTORS}
    # Important: representative reduction is a next-data-acquisition workplan,
    # NOT elimination of other route research variants.
    rows=[]
    for id in sorted(full):
        old=original_rank[id]
        local=[]
        for city,site_ids in SITES.items():
            for site in site_ids:
                for speed in (160,200,250):
                    r=station[(id,site,speed)]
                    sol=r["best_research_horizontal_solution"]
                    local.append({"city":city,"site_id":site,"speed_screen_kmh":speed,
                       "sampled_curvature_condition_source_pass":bool(r["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"]),
                       "source_2D_horizontal_length_m":sol["total_connected_2D_centerline_length_m"] if sol else None,
                       "source_2D_detour_over_contact_chord_m":sol["planimetric_length_excess_over_direct_chord_m"] if sol else None,
                       "contact_east_shift_m":sol["shift_east_anchor_outward_m"] if sol else None,
                       "original_source_not_constructed_railway":True})
        rows.append({"option_id":id,"in_G51_high_priority_8":id in first,
          "included_G52_six_distinct_source_family_samples":id in chosen,
          "G30_deep_tunnel_geology_must_be_studied":id==DEEP,
          "mixed_research_top8_hits_24":old["mixed_grade_total_top8_hits_across_24_research_tests"],
          "original_local_city_grid_connectors_still_two_fixed_paths_NOT_rail":True,
          "regional_source_modules":{s:{k:v for k,v in val.items() if k!="paths_grid_original_PT_TM06"}
                                     for s,val in full[id].items()},
          "road_grid_city_service_original_mean_minutes_NOT_station":
              old["source_G33_four_optional_city_road_to_grid_mean_minutes_NOT_station"],
          "source_2021_Euclidean_10km_population_union_NOT_rail_demand":
              old["source_G34_INE2021_residents_6x10km_Euclidean_union_NOT_demand"],
          "station_sites_4_source_horizontal_speed_sensitivities":local})
    return full,first,nine,chosen,coverage,rows,station
def write(g10,g30,g42,g45,g51,jout,csvout,geoout,figout,mdout):
    full,first,nine,chosen,cover,rows,station=derive(g10,g30,g42,g45,g51)
    features=[]
    projected={f["properties"]["id"]:f for f in g10["features"]+g30["features"]}
    fig,ax=plt.subplots(figsize=(12,7),layout="constrained")
    for id in nine:
        coords=projected[id]["geometry"]["coordinates"]
        xy=[canonical_point(p) for p in coords]
        line=np.array(xy,dtype=float)/1000
        if id in chosen:
            c="#2f697e" if id!=DEEP else "#963f65"
            ax.plot(line[:,0],line[:,1],lw=2,alpha=.6,c=c)
        else:ax.plot(line[:,0],line[:,1],lw=.9,alpha=.38,c="#a0a7a9",ls="--")
    for i,id in enumerate(chosen):
        coords=projected[id]["geometry"]["coordinates"]
        features.append({"type":"Feature","geometry":projected[id]["geometry"],
            "properties":{"source_route_id":id,"status":"SOURCE_2km_GRID_NOT_ENGINEERED_RAIL",
                          "source_30_original_options_retained":True,
                          "sampling_family":i+1,"may_include_shared_modules":True}})
    for city,sids in SITES.items():
        for id in chosen:
            for sid in sids:
                r=station[(id,sid,200)]
                if not r["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"]:continue
                samples=r["best_research_horizontal_solution"]["sampled_QA_path_PT_TM06"]
                projected_coords=[ESG.transform(*p) for p in samples]
                features.append({"type":"Feature",
                  "geometry":{"type":"LineString","coordinates":[list(p) for p in projected_coords]},
                  "properties":{"status":"G45_200kmh_2D_QUINTIC_CURVATURE_RESEARCH_NOT_RAILWAY",
                    "original_route":id,"site":sid,"mandatory_city":city,
                    "station_interface_not_full_3D":True}})
    for label,p in [("VR_W",ANCHORS[0]),("VR_E",ANCHORS[1]),("BR_W",ANCHORS[2]),("BR_E",ANCHORS[3])]:
        ax.scatter([p[0]/1000],[p[1]/1000],s=25,c="#131b25")
        ax.annotate(label,(p[0]/1000,p[1]/1000),xytext=(4,5),textcoords="offset points",fontsize=8)
    ax.set_title("G52 · Amostragem de 6 famílias na shortlist de 9 — grelha inicial 2 km, NÃO ferrovia",loc="left")
    ax.set_xlabel("PT-TM06, km E");ax.set_ylabel("PT-TM06, km N")
    ax.set_aspect("equal",adjustable="datalim");ax.grid(alpha=.14)
    fig.savefig(figout,dpi=155,bbox_inches="tight");plt.close(fig)
    geoout.write_text(json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False)+"\n")
    with csvout.open("w",newline="",encoding="utf-8-sig") as f:
        headers=("route_id","G51_top8","G52_6_sampling_families","combined_mixed_source_top8_hits",
                 "west_module_digest","mid_module_digest","east_module_digest","rail_station_3D_ground_validated")
        w=csv.writer(f,delimiter=";");w.writerow(headers)
        for r in rows:
            id=r["option_id"]
            w.writerow([id,id in first,id in chosen,r["mixed_research_top8_hits_24"]]+
                [full[id][s]["source_grid_edge_digest"] for s in DIFF_SECTORS]+["NO"])
    output={"mission":"MN-GEO-RAIL-001","stage":"G52_distinct_geographic_modules_6_families_station_design_screen",
      "source_original_all30_preserved":True,"source_27_G10_3_G30_count":30,
      "G51_original_mixed_high_priority_eight":first,
      "extra_deep_tunnel_branch_not_eliminated":DEEP,
      "source_9_investigation_candidates":nine,
      "G52_six_representative_original_source_routes_for_NEXT_ground_3D":chosen,
      "source_module_diversity_preserved_by_six_samples_relative_to_nine":cover,
      "G42_local_two_city_research_grid_paths_each_shared_by_all30":True,
      "source_all30_module_and_four_station_planimetric_sensitivity":rows,
      "original_G45_C2_station_planar_approaches_only_not_railway":True,
      "G53_required_actual_DGT_original_DTM_pixel_alignment_and_vertical_curves":True,
      "mandatory_cities":["Vila_Real","Braganca"],
      "Sanabria_not_station_or_required_node":True,
      "no_eng_rail_3D_project_or_approved_horizontal_clothoids_yet":True,
      "cannot_calculate_real_tunnel_viaduct_lengths_earthworks_costs_or_train_times":True,
      "geology_hydro_Natura2000_PIC_NOT_CLEARED":True,
      "no_original_source_data_reacquired":True,
      "Fxx_accepted":False,"Site_authorized":False}
    jout.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n")
    md=["# G52 — Famílias de desenho para passar da shortlist à engenharia 3D",
        "","A carteira conserva as **30 alternativas originais**. A shortlist anterior G51 (8 casos com maior presença nos 24 testes para 12,5/15‰) é complementada pelo cenário G30 de túnel profundo. Para evitar estudar repetidamente módulos idênticos, seis casos foram **selecionados apenas como amostragem espacial de aquisição e engenharia**; não são seis projetos ferroviários, nem excluem qualquer alternativa.",
        "","## Seis poligonais-família para aprofundar, não corredores aprovados",
        "","**"+", ".join(chosen)+"**.",
        "","## Preservação dos módulos geograficamente distintos na carteira G51+Túnel",
        "","| Setor | Módulos distintos nos 9 estudos | Representados nas seis amostras | Cobertura |",
        "|---|---:|---:|---:|"]
    for s,c in cover.items():
        md.append(f"| {s} | {c['shortlist_9_spatial_modules']} | {c['six_sample_representatives_modules']} | {100*c['fraction_of_shortlist_spatial_diversity_covered']:.0f}% |")
    md+=["","Os módulos locais Vila Real W–E e Bragança W–E são **idênticos nas 30 poligonais originais G10/G30**, logo a sua multiplicação não constitui diversidade ferroviária. **É obrigatório redesenhá-los** em torno dos pontos DGT originais VR2/VR1 e BR3/BR4 antes de criar configurações de projeto.",
       "","## Critérios para G53",
       "1. Construir perfis **localmente** 3D para a faixa central de 3 km das quatro posições de estação usando as **484 observações DGT2m originais validadas**, com 12,5‰/15‰ de via geral, 10‰ de paragem PAT como referência de função e sensibilidade a raios verticais 10/20 km; testar 2,5‰ apenas nas operações que o exigirem.",
       "2. Expor os cinco módulos originais como eixos de investigação com coordenadas, partilha entre famílias e pontos em que faltam dados DGT/IGN de solo nu. Um corredor sem terreno contínuo permanece **SEM PERFIL 3D VERIFICADO**.",
       "3. Não inferir comprimentos de túneis/viadutos da diferença entre rasante matemática e terreno, nem aplicar 25‰ a tráfego misto.",
       "4. Testar o Marão–Alvão e as aproximações a Vila Real num conjunto de eixos horizontais reprojetados com curvas e transições, evitando tratar a grelha original de 2 km como geometria ferroviária.",
       "5. Manter as oito alternativas mais túnel como referência de diversidade, e as 30 como conjunto mestre sem eliminação prematura.",
       "","**G52 é uma decomposição e plano espacial de investigação. Não contém eixos ferroviários 3D aprovados, nem estimativas de custos, tempos ou licenças ambientais.**"]
    mdout.write_text("\n".join(md)+"\n")
    print("G52_RESULT",json.dumps({"G51_8":first,"deep":DEEP,
      "six_sample":chosen,"3_sectors_unique_coverage":cover,
      "mandatory_station_cases_reviewed":len(rows)*4*3,"full30_kept":True},
        ensure_ascii=False),flush=True)
def main():
    a=argparse.ArgumentParser()
    for k in ("g10","g30","g42","g45","g51","json","csv","geojson","figure","markdown"):
        a.add_argument("--"+k,required=True,type=Path)
    p=a.parse_args()
    write(*[json.loads(getattr(p,k).read_text()) for k in ("g10","g30","g42","g45","g51")],
      p.json,p.csv,p.geojson,p.figure,p.markdown)
if __name__=="__main__":main()
