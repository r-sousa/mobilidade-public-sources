#!/usr/bin/env python3
"""G36 integrated 30x160/200/250 GEO research option comparison with true provenance.

Three transparent source-only multi-objective sensitivities, NEVER a feasibility
ranking, cost-benefit, EIA or approval. All G10 27 and G30 3 remain in output.
Use G35 original station siting reference: shared obligatory-city study modules
are not valid *differentiating* factors between routes.
"""
import argparse,csv,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
SCENARIOS=(160,200,250)
MANDATORY=("Vila_Real","Braganca")
OPTIONAL=("Guimaraes","Amarante","Mirandela","Macedo_de_Cavaleiros")
METRIC_NAMES=("research_length_km","surface_Natura2000_km","DSM_proxy_mean_abs_m",
              "optional_road_to_grid_minutes_mean","geographic_union_2021_residents")
PROFILES={
 "length_and_relief_research":{"research_length_km":.40,"surface_Natura2000_km":.17,
           "DSM_proxy_mean_abs_m":.22,"optional_road_to_grid_minutes_mean":.12,
           "geographic_union_2021_residents":.09},
 "optional_service_geography":{"research_length_km":.12,"surface_Natura2000_km":.20,
           "DSM_proxy_mean_abs_m":.12,"optional_road_to_grid_minutes_mean":.30,
           "geographic_union_2021_residents":.26},
 "surface_Natura_research_precaution":{"research_length_km":.12,"surface_Natura2000_km":.50,
           "DSM_proxy_mean_abs_m":.15,"optional_road_to_grid_minutes_mean":.12,
           "geographic_union_2021_residents":.11},
 "underground_unknown_no_2D_Natura_score":{"research_length_km":.35,"surface_Natura2000_km":0.0,
           "DSM_proxy_mean_abs_m":.28,"optional_road_to_grid_minutes_mean":.20,
           "geographic_union_2021_residents":.17}}
MINIMIZE=set(METRIC_NAMES)-{"geographic_union_2021_residents"}
def validate(g32,g33,g34,g35):
    a=g32.get("rows",[])
    if g32.get("G10_count")!=27 or g32.get("G30_count")!=3 or len(a)!=90:
        raise ValueError("G36_requires_original_all30x3_G32")
    if not g32.get("canonical_portfolio_next_stages_all_27_G10_plus_3_G30"):
        raise ValueError("G36_do_not_drop_original_corridors")
    if g32.get("PIC_status")!="UNRESOLVED_MUST_NOT_RANK_AS_LEGALLY_CLEARED":
        raise ValueError("G36_PIC_is_strict_unknown")
    if g33.get("G10")!=27 or g33.get("G30")!=3 or len(g33.get("six_city_all_180_records",[]))!=180:
        raise ValueError("G36_G33_180_same_run_road_samples")
    if g34.get("G10_count")!=27 or g34.get("G30_count")!=3 or not g34.get("all30_same_method"):
        raise ValueError("G36_G34_uniform_2021_census_missing")
    if len(g34.get("corridor_six_city_radius10km_unions_no_overlap_duplication",[]))!=30:
        raise ValueError("G36_G34_no_double_count_union_missing")
    if not(g35.get("G10_all_routes")==27 and g35.get("G30_all_routes")==3 and
       len(g35.get("comparisons_all30_times_two_mandatory_cities",[]))==60
       and g35.get("original_DGT2m_COS2025_road_study_coordinate_sites")==7
       and g35.get("legal_PIC_unknown")):
        raise ValueError("G36_G35_real_previous_stations_not_reused")
    ids={v["option_id"] for v in a}
    if len(ids)!=30 or sum(x.startswith("G30-") for x in ids)!=3:
        raise ValueError("G36_original_G10_or_G30_loss")
    for speed in SCENARIOS:
        case=[r for r in a if r["scenario_speed_kmh"]==speed]
        if len(case)!=30 or {r["option_id"] for r in case}!=ids:
            raise ValueError("G36_30_per_speed_not_proven")
    rc={(r["option_id"],r["urban_key"]) for r in g33["six_city_all_180_records"]}
    if rc!={(key,city) for key in ids for city in (*OPTIONAL,*MANDATORY)}:
        raise ValueError("G36_all_six_market_comparability_mandatory")
    union={r["option_id"] for r in g34["corridor_six_city_radius10km_unions_no_overlap_duplication"]}
    if union!=ids:raise ValueError("G36_2021_census_not_all30")
    st={(r["option_id"],r["mandatory_city"]) for r in g35["comparisons_all30_times_two_mandatory_cities"]}
    if st!={(id,city) for id in ids for city in MANDATORY}:
        raise ValueError("G36_mandatory_city_site_comparison_omitted")
    # G35 found original 12+17 physical study orientation context for ALL 30,
    # so using it as a differentiating quality score would be misleading.
    for city in MANDATORY:
        n={r["prior_original_ground_and_road_within_3km_context_cases"] for r in g35["comparisons_all30_times_two_mandatory_cities"] if r["mandatory_city"]==city}
        if len(n)!=1:raise ValueError("G36_sites_not_common_verify_before_omitting_score")
    return sorted(ids,key=lambda s:(s.startswith("G30-"),s))
def make_rows(g32,g33,g34,g35):
    ids=validate(g32,g33,g34,g35)
    access={(r["option_id"],r["urban_key"]):r for r in g33["six_city_all_180_records"]}
    census={r["option_id"]:r["2021_residents_in_unduplicated_union_of_six_10km_study_circles"]["residents_2021_representative_subsection"]
         for r in g34["corridor_six_city_radius10km_unions_no_overlap_duplication"]}
    cases=[]
    for s in SCENARIOS:
        by={r["option_id"]:r for r in g32["rows"] if r["scenario_speed_kmh"]==s}
        for id in ids:
            v=by[id]
            road=[access[id,city]["road_drive_minutes_to_snapped_grid_road_not_station"] for city in OPTIONAL]
            geo=[access[id,city]["nearest_source_research_grid_direct_distance_km"] for city in OPTIONAL]
            if any(x is None or not math.isfinite(x) for x in road):
                # Never rank null road as zero; skip numerical decision ranking.
                road_avg=None
            else:road_avg=round(float(np.mean(road)),3)
            len_km=v["length_smoothed_km"]
            nat=v["Natura_smoothed_km"]
            dsm=v["DSM_25permille_mean_abs_deviation_m"]
            if not v.get("pass_6km") or any(x is None for x in (len_km,nat,dsm)):
                len_km=nat=dsm=None
            data={"option_id":id,"family":"G30" if id.startswith("G30-") else "G10",
              "speed_kmh":s,"g32_horizontal_proxy_3km":v.get("pass_3km"),
              "g32_horizontal_proxy_6km":v.get("pass_6km"),
              "research_length_km":len_km,"surface_Natura2000_km":nat,
              "Alvao_Marao_smoothed_line_overlap_km_NOT_impacts":v.get("Alvao_smoothed_km"),
              "DSM_proxy_mean_abs_m":dsm,
              "optional_road_to_grid_minutes_mean":road_avg,
              "optional_market_geographic_directness_mean_km":round(float(np.mean(geo)),3),
              "geographic_union_2021_residents":census[id],
              "mandatory_station_research_reused_G35_without_discriminating_scores":True,
              "population_year":2021,"station_access_and_rail_service_not_verified":True,
              "Natura_surface_overlap_not_hard_legal_exclusion_and_tunnel_unknown":True,
              "PIC_not_mapped_official_source":True,
              "cost_EUR_and_rail_time":"UNKNOWN_NO_DESIGNED_3D_TRACK"}
            cases.append(data)
    if len(cases)!=90:raise ValueError("G36_complete_90_source_comparison")
    return ids,cases
def norm(cases,name):
    values=[r[name] for r in cases if r[name] is not None]
    if not values:return {r["option_id"]:None for r in cases}
    lo,hi=min(values),max(values)
    if hi-lo<1e-9:
        return {r["option_id"]:0.5 if r[name] is not None else None for r in cases}
    return {r["option_id"]:(None if r[name] is None else
             (r[name]-lo)/(hi-lo) if name in MINIMIZE else (hi-r[name])/(hi-lo))
            for r in cases}
def dominance(cases):
    dimensions=METRIC_NAMES
    usable=[r for r in cases if all(r[m] is not None for m in dimensions)]
    nondominated=[]
    for current in usable:
        def weakbetter(other):
            diff=[other[k]-current[k] if k in MINIMIZE else current[k]-other[k] for k in dimensions]
            return all(z<=1e-8 for z in diff) and any(z<-1e-8 for z in diff)
        if not any(other["option_id"]!=current["option_id"] and weakbetter(other) for other in usable):
            nondominated.append(current["option_id"])
    return nondominated
def score_rows(rows):
    for name,weights in PROFILES.items():
        if set(weights)!=set(METRIC_NAMES) or abs(sum(weights.values())-1)>1e-7:
            raise ValueError("G36_weights_must_covered_and_sum_one")
    ranked={};counter=Counter();scored=[]
    for speed in SCENARIOS:
        cases=[r for r in rows if r["speed_kmh"]==speed]
        normal={k:norm(cases,k) for k in METRIC_NAMES}
        front=dominance(cases)
        for r in cases:r["source_only_pareto_5_measured_dimensions"]=r["option_id"] in front
        ranked[str(speed)]={"source_only_pareto_5dimensions":front,"profile_top8":{}}
        for profile,weights in PROFILES.items():
            vals=[]
            for r in cases:
                terms=[normal[k][r["option_id"]] for k in METRIC_NAMES]
                if any(v is None for v in terms):score=None
                else:score=sum(weights[k]*normal[k][r["option_id"]] for k in weights)
                r["source_only_weighted_normalized_"+profile]=round(score,6) if score is not None else None
                if score is not None:vals.append((score,r["option_id"]))
            vals.sort(key=lambda z:(z[0],z[1]))
            first=[id for _,id in vals[:8]]
            ranked[str(speed)]["profile_top8"][profile]=first
            for ix,id in enumerate(first):
                counter[id]+=1
            for ix,(_,id) in enumerate(vals):
                next(r for r in cases if r["option_id"]==id)["rank_source_only_"+profile]=ix+1
        ranked[str(speed)]["valid_all_five_measured_dimensions"]=sum(
            all(r[m] is not None for m in METRIC_NAMES) for r in cases)
    # The count is across 3 speeds × 4 illustrative profiles = 12 ranking slots.
    # All 30 remain available. A shortlist is ONLY for next data collection,
    # not an evaluated railway scheme.
    present={r["option_id"] for r in rows}
    frequencies={id:counter[id] for id in sorted(present)}
    review=sorted(present,key=lambda id:(-counter[id],id))
    ranking=[{"option_id":id,"in_top8_of_twelve_sensitivity_tests":counter[id],
       "next_engineering_work_priority_only":(counter[id]>=3 or id=="G30-potential_deep_tunnel"),
       "G30_potential_deep_tunnel_explicitly_retained_for_uncertain_3D_hydro_environmental_test":id=="G30-potential_deep_tunnel",
       "must_still_remain_in_full30_portfolio":True} for id in review]
    return ranked,ranking
def figures(cases,rank,scatter,heat):
    ids=[x["option_id"] for x in rank]
    v={r["option_id"]:r for r in cases if r["speed_kmh"]==200}
    xs=[v[x]["research_length_km"] for x in ids]
    ys=[v[x]["optional_road_to_grid_minutes_mean"] for x in ids]
    fig,ax=plt.subplots(figsize=(10.8,7),layout="constrained")
    for family,color,marker in (("G10","#7890a6","o"),("G30","#c76e37","D")):
        pts=[k for k in ids if ("G30" if k.startswith("G30-") else "G10")==family and xs[ids.index(k)] is not None]
        ax.scatter([v[k]["research_length_km"] for k in pts],
                   [v[k]["optional_road_to_grid_minutes_mean"] for k in pts],
                   s=28 if family=="G10" else 72,c=color,marker=marker,
                   edgecolors="white",alpha=.8,label=family)
    for k in ids:
        if k.startswith("G30-"):
            ax.annotate(k.replace("G30-",""),(v[k]["research_length_km"],
                         v[k]["optional_road_to_grid_minutes_mean"]),
                        xytext=(4,5),textcoords="offset points",fontsize=7)
    ax.set_xlabel("Comprimento matemático do corredor 200 km/h (km) · NÃO via projetada")
    ax.set_ylabel("Média das quatro viagens OSRM cidade→via próxima da malha (min) · NÃO estação")
    ax.set_title("G36 · 30 corredores: extensão vs acesso exploratório a mercados opcionais",loc="left")
    ax.legend();ax.grid(alpha=.2);fig.savefig(scatter,dpi=165,bbox_inches="tight");plt.close(fig)
    metric={"natura":"surface_Natura2000_km","terrain":"DSM_proxy_mean_abs_m",
            "length":"research_length_km","optional road":"optional_road_to_grid_minutes_mean",
            "population 2021":"geographic_union_2021_residents"}
    arr=np.array([[v[x].get(m) for m in metric.values()] for x in ids],float)
    nrm=np.zeros_like(arr)
    for j,col in enumerate(arr.T):
        mask=np.isfinite(col)
        lo,hi=np.nanmin(col),np.nanmax(col)
        nrm[:,j]=.5 if hi-lo<1e-7 else (col-lo)/(hi-lo)
        if list(metric)[j]=="population 2021":nrm[:,j]=1-nrm[:,j]
    fig,ax=plt.subplots(figsize=(9.6,11.7),layout="constrained")
    m=ax.imshow(nrm,cmap="YlOrRd",aspect="auto",vmin=0,vmax=1)
    ax.set_xticks(range(len(metric)),list(metric),rotation=22,ha="right",fontsize=9)
    ax.set_yticks(range(len(ids)),ids,fontsize=8)
    ax.axhline(sum(not x.startswith("G30-") for x in ids)-.5,color="white",lw=2)
    fig.colorbar(m,ax=ax,label="Variável normalizada (maior = menos favorável no proxy, sem custo real)")
    ax.set_title("G36 · 200km/h: todas as 30 opções, cinco critérios observados, mesma escala",loc="left")
    fig.savefig(heat,dpi=165,bbox_inches="tight");plt.close(fig)
def run(g32,g33,g34,g35,jsonout,csvout,mdout,scatter,heat):
    ids,rows=make_rows(g32,g33,g34,g35)
    profiles,ranking=score_rows(rows)
    doc={"mission":"MN-GEO-RAIL-001","stage":"G36_all30_3speeds_3explicit_priority_sensitivity_screens",
      "source_all_original_G10_count":27,"source_all_original_G30_count":3,
      "all30_retained":True,"speed_scenarios":list(SCENARIOS),
      "rows_n":len(rows),"priority_profiles_research_only_not_policy_scores":PROFILES,
      "normalization_scope":"same_speed_all30_minmax_on_only_measured_variables",
      "measured_input_dimensions":list(METRIC_NAMES),
      "G35_all_30_share_same_7_prior_station_site_coordinates_and_29_contexts_not_discriminating":True,
      "source_G33_OSRM_road_to_grid_only_not_station":True,
      "source_G34_INE2021_10km_union_not_passenger_rail_demand":True,
      "Natura2000_overlap_is_2D_surface_research_not_an_EIA_or_hard_tunnel_exclusion":True,
      "PIC_still_UNRESOLVED_official_source":True,
      "no_actual_rail_timings_or_EUR_CAPEX_or_tunnel_quantities":True,
      "underground_Natura_unknown_not_scored_as_hard_surface_ban":True,
      "G30_potential_deep_tunnel_kept_as_mandatory_design_sensitivity_not_permit":True,
      "no_actual_30_corridor_station_site_3D_compatibility":True,
      "all_30_retained_before_any_legal_feasibility":True,
      "no_new_DGT_INE_OSRM_or_other_original_data_acquisition":True,
      "Fxx_accepted":False,"Site_authorized":False,
      "speed_source_only_comparisons":profiles,
      "review_priority_NOT_viability_OR_final_selection":ranking,
      "rows_90":rows}
    jsonout.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n")
    with csvout.open("w",newline="",encoding="utf-8-sig") as f:
        fieldnames=["option_id","family","speed_kmh","g32_horizontal_proxy_3km","research_length_km",
         "surface_Natura2000_km","Alvao_Marao_smoothed_line_overlap_km_NOT_impacts",
         "DSM_proxy_mean_abs_m","optional_road_to_grid_minutes_mean",
         "optional_market_geographic_directness_mean_km","geographic_union_2021_residents"]
        for key in PROFILES:fieldnames+=["source_only_weighted_normalized_"+key,"rank_source_only_"+key]
        w=csv.DictWriter(f,fieldnames=fieldnames,delimiter=";")
        w.writeheader()
        for row in rows:w.writerow({k:row.get(k) for k in fieldnames})
    figures(rows,ranking,scatter,heat)
    lines=["# G36 — 30 corredores G10+G30: análise conjunta de relevo, Natura e serviço geográfico",
     "","Todos os 27 corredores G10 e três G30 preservados. Esta é **uma comparação de indicadores medidos de investigação**, sem custos ferroviários, tempos de circulação, geometria de estação/obra nem avaliação apropriada Natura. As 7 posições antigas de estação G23–G27 estão preservadas G35; os seus dados de proximidade são comuns a todos os 30 e não discriminam a seleção.",
     "","Os pesos abaixo são **hipóteses de sensibilidade**, não valores normativos, prioridades institucionais decididas, benefícios monetários nem ranking final. O fator Natura quantifica **só extensão de sobreposição do centro de investigação com sítios oficiais**, não impacte ambiental ou dispensa de avaliação por túnel. PIC é impedimento jurídico/espacial ainda não esclarecido.",
     "","## Perfis de sensibilidade — todos aplicados igualmente aos 30 e a 160/200/250 km/h",
     "","| Perfil | Extensão | Natura 2D | Pressão MDS | Acesso rodoviário aos 4 mercados opcionais | Residentes 2021 (união 6 círculos) |",
     "|---|---:|---:|---:|---:|---:|"]
    for key,profile in PROFILES.items():
        lines.append("| "+key+" | "+" | ".join(f"{profile[k]*100:.0f}%" for k in METRIC_NAMES)+" |")
    lines+=["","## Alternativas com prioridade de recolha posterior — NÃO seleção de traçado",
         "","A contagem é o número de presenças entre as primeiras oito posições de cada combinação **3 velocidades × 4 perfis**, total de doze ensaios. A carteira de 30 não é truncada; uma contagem elevada apenas sugere investigação proporcional, sujeito a conformidade ambiental, serviço real e custos.",
         "","| Alternativa | Presenças no top8/12 | Próxima análise de engenharia sugerida? |",
         "|---|---:|---|"]
    for e in ranking:
        lines.append(f"| {e['option_id']} | {e['in_top8_of_twelve_sensitivity_tests']} | {'sim, hipótese de pesquisa' if e['next_engineering_work_priority_only'] else 'não prioritária neste teste; manter'} |")
    lines+=["","**Salvaguarda subterrânea:** o quarto perfil não pontua a sobreposição Natura 2D, porque tal sobreposição não permite distinguir superfície de túnel; NÃO transforma a restrição Natura em zero jurídico ou autorização. A variante G30-potential_deep_tunnel permanece no grupo de estudo tridimensional e hidrogeológico, qualquer que seja a sua frequência no top8. É uma decisão de cobertura de hipóteses, não uma recomendação baseada em custos ou impacte comprovados.",
        "","## Fronteiras não dominadas — apenas 5 variáveis investigadas",
        "","| Cenário | Linhas não dominadas do estudo (sem decisão de investimento) |",
        "|---|---|"]
    for speed in SCENARIOS:
        f=profiles[str(speed)]["source_only_pareto_5dimensions"]
        lines.append(f"| {speed} km/h | {', '.join(f)} |")
    lines+=["","## Limites que impedem encerrar a decisão",
       "- **Relevo:** MDS Copernicus 30m não é solo nu; amplitude de afastamento vertical não corresponde a escavação, viaduto ou euros. Velocidade é um requisito de raio matemático, não tempo de viagem.",
       "- **Estação e acessibilidade:** G35 confirmou 7 sítios antigos e 29 situações locais testadas, comuns nas duas zonas obrigatórias; o G36 não se permite valorizá-los diferencialmente. OSRM G33 mede automóvel até via próxima da malha, não acesso ao edifício ou paragem de transporte público.",
       "- **População:** BGRI2021 G34, círculos de 10 km de pontos de estudo, não isócronas reais, nem atuais residentes de 2026, nem procura ferroviária.",
       "- **Ambiente:** Natura2000 restrição maior e avaliação conforme Diretiva Habitats; efeitos de túnel Marão–Alvão, hidrogeologia, portais e poços desconhecidos. PIC permanece sem identificação oficial e não admite declaração de conformidade.",
       "- **Projetos comparáveis:** é necessário desenvolver 3D, curvas de transição, gradientes, viabilidade de estações periféricas, estrutura, método de escavação e custos por faixa; os G10/G30 continuam linhas de grelha.",
       "- **Próximo passo:** confirmar se as alternativas com prioridade de investigação podem realmente diferenciar-se na ligação a Guimarães/Amarante/Mirandela/Macedo, e definir faixas 3D e cobertura DGT suplementar estritamente necessária, sem aquisição alargada.",
       "","**Nenhuma alternativa é excluída automaticamente. Nenhuma é autorizada ou é uma escolha de investimento.**"]
    mdout.write_text("\n".join(lines)+"\n")
    freq=[v for v in ranking if v["next_engineering_work_priority_only"]]
    print("G36_RESULT",json.dumps({"rows":len(rows),"top8_frequency_12_trials":ranking,
       "next_engineering_research_count":len(freq),
       "source_pareto_count":{key:len(value["source_only_pareto_5dimensions"]) for key,value in profiles.items()},
       "no_imputed_cost_time_EIA":True},ensure_ascii=False))
def main():
    a=argparse.ArgumentParser()
    for k in ("g32","g33","g34","g35","json","csv","markdown","scatter","heatmap"):
        a.add_argument("--"+k,required=True,type=Path)
    q=a.parse_args()
    run(*[json.loads(getattr(q,k).read_text()) for k in ("g32","g33","g34","g35")],
        q.json,q.csv,q.markdown,q.scatter,q.heatmap)
if __name__=="__main__":main()
