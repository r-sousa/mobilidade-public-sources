#!/usr/bin/env python3
"""G51 full30 updated source-only multi-criteria engineering-investigation
priorities after G50 12.5/15 mixed gradient revision.

Reuses G36's exact G33 original OSRM optional cities road-to-study-grid,
INE2021 10km Euclidean market, Natura2D and study length proxies.
Replaces ONLY G36 historical 25‰ DSM research pressure with G50 same-source
12.5,15,18,20,25. No fabricated rail times, CAPEX, GTFS, real demand.

Recompute same three speeds x four weights in each of 5 gradients (60
research sensitivity tests); reproduce G36 historical 25‰ ranking and
retain all30, including G30-deep-tunnel even if low in source score.
Any shortlist only prioritizes NEXT real DTM/geotechnical design tasks.
"""
from __future__ import annotations
import argparse,csv,json,collections
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from geo_rail_g36_all30_robust_source_only_selection import (
 score_rows,SCENARIOS,PROFILES,METRIC_NAMES
)
from geo_rail_gradient_policy_G48 import NOMINAL_GRADES_PERMILLE,classify
DEEP="G30-potential_deep_tunnel"
PRIMARY=(12.5,15.)
def reuse(g36,g50):
    base=g36["rows_90"]
    allgrad=g50["grade_scenarios_on_same_original_90_geometries"]
    if not(g36["all30_retained"] and g36["rows_n"]==90
           and g36["source_all_original_G10_count"]==27 and g36["source_all_original_G30_count"]==3
           and g36["source_G33_OSRM_road_to_grid_only_not_station"]
           and g36["source_G34_INE2021_10km_union_not_passenger_rail_demand"]
           and g50["original_G10_27_G30_3_retained"] and g50["count_equal_source_route_speed_grade_cases"]==450
           and g50["DSM_is_surface_vegetation_and_buildings_NOT_terrain"]):
        raise ValueError("G51_original_road_pop_grade_30_sources_not_valid")
    old={(r["option_id"],r["speed_kmh"]):r for r in base}
    new={(r["option_id"],r["scenario_speed_kmh"],r["gradient_permille"]):r for r in allgrad}
    opts={r["option_id"] for r in base}
    if (len(opts)!=30 or len(old)!=90 or len(new)!=450 or DEEP not in opts):
        raise ValueError("G51_unmatched_original_all30_90_450")
    datasets={}
    for grade in NOMINAL_GRADES_PERMILLE:
        rows=[]
        for speed in SCENARIOS:
            for opt in sorted(opts):
                v=dict(old[(opt,speed)])
                terrain=new[(opt,speed,float(grade))]
                valid=terrain.get("source_G32_horizontal_6km_screen_pass",False)
                if bool(v["g32_horizontal_proxy_6km"])!=bool(valid):
                    raise ValueError("G51_original_G32_G50_horizontal_geometry_drift")
                value=terrain.get("original_DSM_400m_mean_abs_height_deviation_m_proxy") if valid else None
                v["DSM_proxy_mean_abs_m"]=value
                v["G51_regime_gradient_permille"]=float(grade)
                v["G51_regime_function"]=classify(grade)
                v["G51_reused_original_DSM_NOT_bareearth"]=True
                v["G51_preserved_original_G33_road_to_grid_not_station"]=True
                v["G51_preserved_original_G34_2021_Euclidean_10km_not_demand"]=True
                rows.append(v)
        ranks,priority=score_rows(rows)
        datasets[grade]={"rows":rows,"ranks":ranks,"priority":priority}
    # historical G36 based on 25‰ DSM must be EXACT: same 90 and same
    # research weights and road/INE/length source, no new invented metrics.
    oldfreq={x["option_id"]:x["in_top8_of_twelve_sensitivity_tests"] for x in g36["review_priority_NOT_viability_OR_final_selection"]}
    new25={x["option_id"]:x["in_top8_of_twelve_sensitivity_tests"] for x in datasets[25.]["priority"]}
    if oldfreq!=new25:
        diffs={k:(oldfreq[k],new25[k]) for k in oldfreq if oldfreq[k]!=new25[k]}
        raise ValueError("G51_G36_historical_25permille_not_reproduced:"+str(diffs)[:180])
    return opts,datasets
def compare(g36,g50,outjson,outcsv,outmd,outpng):
    opts,data=reuse(g36,g50)
    hits={grad:{r["option_id"]:r["in_top8_of_twelve_sensitivity_tests"] for r in value["priority"]}
          for grad,value in data.items()}
    table=[]
    for id in sorted(opts):
        mixed=hits[12.5][id]+hits[15.][id]
        cases=[r for r in data[12.5]["rows"] if r["option_id"]==id and r["speed_kmh"]==200]
        if len(cases)!=1:raise ValueError("G51_200_source_case_missing")
        case=cases[0]
        a=data[12.5]["rows"][0]
        table.append({"option_id":id,"source_family":"G30" if id.startswith("G30") else "G10",
          "mixed_12p5_top8_hits_across_12_source_weight_speed_tests":hits[12.5][id],
          "mixed_15_top8_hits_across_12_source_weight_speed_tests":hits[15.][id],
          "mixed_grade_total_top8_hits_across_24_research_tests":mixed,
          "passenger_only_25_top8_hits_across_12_tests_NOT_mixed":hits[25.][id],
          "difference_mixed12p5_minus_passenger25_top8_hits":hits[12.5][id]-hits[25.][id],
          "200kmh_length_original_G32_study_km":case["research_length_km"],
          "200kmh_surface_Natura_original_G32_overlap_km_NOT_impact":case["surface_Natura2000_km"],
          "200kmh_DSM12p5_source_proxy_mean_abs_m_NOT_ground":case["DSM_proxy_mean_abs_m"],
          "source_G33_four_optional_city_road_to_grid_mean_minutes_NOT_station":
             case["optional_road_to_grid_minutes_mean"],
          "source_G34_INE2021_residents_6x10km_Euclidean_union_NOT_demand":
             case["geographic_union_2021_residents"],
          "must_retained_even_if_zero_research_weight_count":True,
          "G30_deep_tunnel_still_requires_3D_geology":id==DEEP})
    table.sort(key=lambda r:(-r["mixed_grade_total_top8_hits_across_24_research_tests"],r["option_id"]))
    # No unjustified quality thresholds; exactly eight highest hit COUNTs
    # priority for NEXT actual terrain tasks, plus deep-tunnel hypothesis.
    top8=[r["option_id"] for r in table[:8]]
    priority=top8+([DEEP] if DEEP not in top8 else [])
    oldtop8=sorted(hits[25.],key=lambda id:(-hits[25.][id],id))[:8]
    shortlist={"mixed_grade_source_only_8_for_priority_original_DTM_engineering":top8,
          "extra_deep_tunnel_requires_geology_before_exclusion":DEEP not in top8,
          "full_ground_engineering_priority_8plus_deep_tunnel_conditional":priority,
          "not_viability_selection_or_financial_CBA":True}
    out={"mission":"MN-GEO-RAIL-001",
      "stage":"G51_all30_60_mixed_12p5_15_explicit_source_selection_sensitivity",
      "source_G36_30x3_original_G33_G34_G35_policy_weights_reused":True,
      "source_G50_original_DSM_450_and_180_history_preserved":True,
      "original_30_G10_27_G30_3_untouched":True,
      "original_2021_population_is_Euclidean_market_not_transport_demand":True,
      "original_OSRM_4optional_city_access_is_to_source_grid_not_station":True,
      "same_original_G32_Copernicus_DSM_surface_not_bareearth":True,
      "Natura_overlap_is_2D_not_legal_EIA_or_hard_tunnel_exclusion":True,
      "all_five_gradient_sensitivity_regimes":[float(q) for q in NOMINAL_GRADES_PERMILLE],
      "research_sensitivity_tests_5grades_x_3speeds_x_4weight_profiles":60,
      "G36_historical_25_gradient_top8_frequencies_exactly_reproduced":True,
      "five_gradient_by_speed_top8_groups_and_pareto":{
          str(grad):dataset["ranks"] for grad,dataset in data.items()},
      "full30_source_only_mixed_vs_passenger_selection_sensitivity":table,
      "research_only_next_terrain_alignment_acquisition_priority":shortlist,
      "no_mixed_freight_grade25_legal_interpretation":True,
      "no_full_railway_3D_times_tunnels_viaducts_CAPEX":True,
      "no_original_DGT_or_INE_road_data_reacquired":True,
      "PIC_Natura_geology_hydro_status":"UNKNOWN_NOT_APPROVED",
      "Fxx_accepted":False,"Site_authorized":False}
    outjson.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    with outcsv.open("w",newline="",encoding="utf-8-sig") as f:
        fields=list(table[0].keys())
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader();w.writerows(table)
    fig,ax=plt.subplots(figsize=(14,7),layout="constrained")
    ids=[t["option_id"] for t in table]
    x=np.arange(len(ids))
    ax.bar(x-.27,[hits[12.5][i] for i in ids],.27,label="Mista 12,5‰")
    ax.bar(x,[hits[15.][i] for i in ids],.27,label="Mista 15‰")
    ax.bar(x+.27,[hits[25.][i] for i in ids],.27,label="Passageiros 25‰ (histórico)")
    ax.set_xticks(x,ids,rotation=65,ha="right",fontsize=7)
    ax.set_ylabel("Presenças no top 8 entre 12 testes de sensibilidade de PESOS — NÃO ranking de viabilidade")
    ax.set_title("G51 · 30 alternativas: seleção de INVESTIGAÇÃO muda com 12,5‰/15‰ vs passageiros 25‰",loc="left")
    ax.legend();ax.grid(axis="y",alpha=.18)
    fig.savefig(outpng,dpi=170,bbox_inches="tight");plt.close(fig)
    md=["# G51 — Shortlist de aquisição e desenho técnico após corrigir a função ferroviária",
       "","Reaplicámos os quatro conjuntos de pesos EXPLORATÓRIOS originais G36 aos 30 corredores x três velocidades para **12,5‰, 15‰, 18‰, 20‰ e 25‰** do G50: **60 testes** de sensibilidade (5 inclinações x 3 velocidades x 4 perfis). Apenas mudou o indicador de pressão vertical GLO30 DSM; os dados de origem sobre comprimento, Natura, acessibilidade rodoviária OSRM às quatro cidades opcionais e população INE2021 em 10km continuam os mesmos. O histórico G36 a 25‰ foi reproduzido integralmente.",
       "","**Não é análise custo-benefício nem ranking de linhas viáveis.** A fonte regional é DSM de superfície (edifícios/vegetação), a população em 10 km é proximidade euclidiana, não procura ferroviária; OSRM mede acesso à grelha de investigação, não às estações, e os efeitos Natura subterrâneos não foram avaliados.",
       "","## Diferenças de prioridade para adquirir MDT original e produzir eixos 3D",
       "","| Alternativa | Top8 com 12,5‰ (12 testes) | Top8 com 15‰ (12) | Top8 com 25‰ passageiros (12) |",
       "|---|---:|---:|---:|"]
    for t in table:md.append(f"| {t['option_id']} | {t['mixed_12p5_top8_hits_across_12_source_weight_speed_tests']} | {t['mixed_15_top8_hits_across_12_source_weight_speed_tests']} | {t['passenger_only_25_top8_hits_across_12_tests_NOT_mixed']} |")
    md+=["","## Prioridades de aprofundamento apenas metodológicas",
       "Os oito casos com maior frequência conjunta de presença no top8 dos regimes 12,5‰ e 15‰ são: **"+", ".join(top8)+"**.",
       "Mantém-se **"+DEEP+"** como cenário obrigatório de investigação geológica e de soluções de túnel (sem autorização ambiental ou comprimento de túnel presumido).",
       "Os restantes "+str(30-len(priority))+" corredores **não são excluídos**. A shortlist serve exclusivamente para decidir em quais os eixos vale a pena adquirir e validar o MDT de solo nu, manter diversidade geográfica e redesenhar estações.",
       "","## Condições seguintes para transformar investigação em engenharia",
       "1. Redesenhar dois ou três traçados 3D por módulo com rampas 12,5‰/15‰, geometrias horizontais e verticais contínuas e controle nos portais; evitar que a classificação de cobertura de DSM afaste alternativas tecnicamente melhores.",
       "2. Reutilizar as quatro faixas locais DGT2m do G47, as 84 quadrículas originais e a lista exata G46 de 10 quadrículas condicionais; evitar aquisições maciças e redundantes.",
       "3. Integrar serviço real a Guimarães, Amarante, Mirandela, Macedo de Cavaleiros e cidades obrigatórias, e modelar procura, marcha ferroviária, integração rodoviária, custos de investimento e de operação depois de definir locais de paragem.",
       "4. Verificar hidrogeologia e geologia Marão–Alvão, Natura 2000, PIC (ainda sem fonte espacial oficial) e compatibilidade com exploração ferroviária mista; 25‰ não é hipótese de mercadorias automática.",
       "","**Sem novas aquisições de terreno nem integração Fxx/Site.**"]
    outmd.write_text("\n".join(md)+"\n")
    print("G51_RESULT",json.dumps({"top8_for_new_original_DTM_alignment":top8,
      "deep_tunnel_remains":DEEP,"mixed_12p5_vs_passenger25_hitness":[{k:t[k] for k in ("option_id",
            "mixed_12p5_top8_hits_across_12_source_weight_speed_tests",
            "mixed_15_top8_hits_across_12_source_weight_speed_tests",
            "passenger_only_25_top8_hits_across_12_tests_NOT_mixed")}
            for t in table[:14]],"all30_preserved":True,"historic_25_reproduced":True},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for q in ("g36","g50","json","csv","markdown","figure"):p.add_argument("--"+q,type=Path,required=True)
    a=p.parse_args()
    compare(json.loads(a.g36.read_text()),json.loads(a.g50.read_text()),a.json,a.csv,a.markdown,a.figure)
if __name__=="__main__":main()
