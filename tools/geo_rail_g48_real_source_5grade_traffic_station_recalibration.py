#!/usr/bin/env python3
"""G48 recalibrate existing ORIGINAL-source G43/G47 vertical research screens.

No new terrain acquisitions. Reuse 241 native 25m IGN ground point readings
from G43 (original 13 verified Spanish TIFF) + 4x121 2m original DGT pixels
from G47 (original 18 original public TIFF).

Compute tight minimax z(s) LP with grades (12.5,15,18,20,25) per mille,
free vs ground-tied endpoints; optional vertical radius finite difference
for G43; original 800m centered straight station with function-specific
local grade 10 or 2.5 per mille vs unconstrained for G47.

All minima are optimistically constrained horizontal-study-axis mathematical
GRADE envelopes, NOT infrastructure compliance, costs, tunnels, cant,
traction simulation, platforms, or finished 3D rail lines.
"""
from __future__ import annotations
import argparse,csv,json,math,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_gradient_policy_G48 import (
  NOMINAL_GRADES_PERMILLE,REFERENCE_VERTICAL_RADII_M,STATION_SENSITIVITIES,
  STATION_STRAIGHT_STUDY_M,SPEED_SCREENS_KMH,EU_TSI,ES_IFI,REGIME_VERSION,classify
)
def source_profiles(g43,g47):
    if (not g43["source_all30_preserved_previous_G42"] or
        g43["original_IGN_source_1km_TIFF_reused"]!=13 or
        g43["G43_original_25m_ground_sampling_n"]!=241 or
        g43["G43_original_dense_ground_valid_n"]!=241 or
        g43["G43_original_dense_ground_missing_n"]!=0):
        raise ValueError("G48_G43_true_241_original_ground_required")
    if (not g47["all_30_G10_27_G30_3_retained"] or
        g47["reused_existing_original_DGT_2m_GitHub_public_tile_assets_count"]!=18
        or not g47["no_new_DGT_credentialed_source_acquisition"]
        or len(g47["source_18_native_original_DGT2m_tile_file_SHA_receipts"])!=18
        or len(g47["real_4x121_25m_sample_original_native_DGT2m_pixel_rows"])!=484):
        raise ValueError("G48_G47_four_x_121_real_original_DGT2m_required")
    sp=sorted(g43["all_source_points"],key=lambda z:z["source_research_chainage_m"])
    if len(sp)!=241 or any(p["source_status"]!="ACTUAL_ORIGINAL_IGN25_PIXEL_QA" or
         not p.get("ground_source_raster_SHA256") for p in sp):
        raise ValueError("G48_G43_no_source_interpolation_or_unverified_origins")
    esx=np.asarray([v["source_research_chainage_m"] for v in sp],dtype=float)
    esy=np.asarray([v["actual_IGN25_original_ground_m"] for v in sp],dtype=float)
    assert np.allclose(np.diff(esx),25)
    sites=[]
    by=defaultdict(list)
    for v in g47["real_4x121_25m_sample_original_native_DGT2m_pixel_rows"]:
        by[v["site_id"]].append(v)
    if set(by)!={"VR1","VR2","BR3","BR4"}:raise ValueError("G48_original_four_sites_drift")
    qa={c["site_id"]:c for c in g47["four_real_original_source_native_ground_station_3km_profiles"]}
    for site in ("VR2","VR1","BR4","BR3"):
        r=sorted(by[site],key=lambda z:z["source_station_chainage_relative_m"])
        if (len(r)!=121 or qa[site]["native_DGT2m_terrain_pixels_valid_n"]!=121
          or any(q["source_status"]!="VALID_ORIGINAL_DGT_2M_GROUND_PIXEL" or
            not q.get("original_file_SHA256") for q in r)):
            raise ValueError("G48_original_DGT2m_pixels_not_fully_valid_"+site)
        sx=np.asarray([q["source_station_chainage_relative_m"] for q in r],float)
        sy=np.asarray([q["original_DGT_2m_ground_elevation_m"] for q in r],float)
        if not np.allclose(np.diff(sx),25) or not np.all(np.isfinite(sy)):
            raise ValueError("G48_G47_original_2m_source_chainage_bad")
        sites.append({"site_id":site,"mandatory_city":qa[site]["mandatory_city"],
            "x_m":sx,"y_m":sy,"original_source_resolution_m":2,
            "original_ground_source_file_count":18,
            "data_reference":"G47_exact_484_original_DGT2m_samples"})
    return {"site_id":"ZAMORA_G43_6KM","mandatory_city":"Zamora",
        "x_m":esx,"y_m":esy,"original_source_resolution_m":25,
        "original_ground_source_file_count":13,
        "data_reference":"G43_exact_241_original_IGN25_samples"},sites
def minimax_grade_envelope(x,y,max_grade_permille,station_max_permille=None,
                            station_half_m=400,vertical_radius_m=None,
                            fixed_endpoints=False):
    """Sparse LP objective min t with grade and optional C2 finite-diff gate.
    A result is only a best mathematical fit at measured ground samples.
    """
    x=np.asarray(x,float);y=np.asarray(y,float);n=len(x)
    if n<3 or len(y)!=n or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("G48_no_missing_source_ground_and_three_points")
    dx=np.diff(x)
    if np.any(dx<=0) or not np.allclose(dx,dx[0],atol=.01):
        raise ValueError("G48_step_must_be_positive_uniform")
    if (max_grade_permille not in NOMINAL_GRADES_PERMILLE or
        vertical_radius_m not in REFERENCE_VERTICAL_RADII_M or
        station_max_permille not in (None,10.0,2.5)):
        raise ValueError("G48_unregistered_grade_radius_or_station_function")
    if station_max_permille is not None and n!=121:
        raise ValueError("G48_platform_gradient_only_four_original_stations")
    rr=[];cc=[];vv=[];rhs=[];row=0
    def constraint(cols,coeff,b):
        nonlocal row
        for i,v in zip(cols,coeff):
            if v:rr.append(row);cc.append(i);vv.append(float(v))
        rhs.append(float(b));row+=1
    for i in range(n):
        constraint((i,n),(1,-1),y[i])
        constraint((i,n),(-1,-1),-y[i])
    center=(x[0]+x[-1])/2
    for i,dd in enumerate(dx):
        grade=max_grade_permille
        if station_max_permille is not None and abs((x[i]+x[i+1])/2-center)<=station_half_m:
            grade=min(grade,station_max_permille)
        for sign in (1,-1):
            constraint((i,i+1),(sign,-sign),grade/1000*dd)
    if vertical_radius_m:
        # Finite-difference bound on gradient curvature, NOT certified Rv.
        dd=dx[0];max_second=dd*dd/vertical_radius_m
        for i in range(1,n-1):
            for sign in (1,-1):
                constraint((i-1,i,i+1),(sign,-2*sign,sign),max_second)
    A=coo_matrix((vv,(rr,cc)),shape=(row,n+1)).tocsr()
    c=np.zeros(n+1);c[-1]=1
    bounds=[(None,None)]*n+[(0,None)]
    if fixed_endpoints:
        bounds[0]=(float(y[0]),float(y[0]))
        bounds[n-1]=(float(y[-1]),float(y[-1]))
    result=linprog(c,A_ub=A,b_ub=np.asarray(rhs),bounds=bounds,method="highs")
    if not result.success:
        # If endpoints are fixed at both originally sampled ground elevations,
        # source terrain may differ by more than a grade-limited rail vertical
        # line can overcome. This is INFEASIBILITY OF THE PARTICULAR
        # artificial endpoint hypothesis, NOT railway route impossibility.
        if result.status==2 and fixed_endpoints:
            return {"status":"INFEASIBLE_ONLY_FOR_BOTH_GROUND_TIED_ENDS_AND_THIS_GRADE",
                "minimum_maximum_vertical_ground_separation_m":None,
                "mathematical_rail_height_AT_SOURCE_SAMPLES_NOT_CONSTRUCTED":None,
                "actual_maximum_fitted_gradient_permille":None,
                "samples_measured":n,
                "not_a_proof_of_corridor_or_railway_infeasibility":True,
                "theoretical_lower_bound_only_not_tunnel_bridge_or_CAPEX":True}
        raise RuntimeError("G48_optimization_failed_without_feasibility_evidence_"+
                           str(result.message)[:140])
    z=np.asarray(result.x[:-1],float)
    if np.max(np.abs(z-y))>result.x[-1]+.0001:raise ValueError("G48_minimax_audit_fail")
    fitted_grade=np.abs(np.diff(z)/dx)*1000
    lims=np.asarray([min(max_grade_permille,station_max_permille)
        if station_max_permille is not None and abs((x[i]+x[i+1])/2-center)<=station_half_m
        else max_grade_permille for i in range(n-1)])
    if np.any(fitted_grade>lims+.0001):raise ValueError("G48_segment_gradient_audit_fail")
    if vertical_radius_m:
        if np.max(np.abs(np.diff(z,n=2)))*vertical_radius_m/(dx[0]**2)>1.0001:
            raise ValueError("G48_vertical_curve_second_derivative_audit_fail")
    return {"status":"OPTIMISTIC_LP_MATHEMATICAL_GRADE_ENVELOPE_NOT_PROJECT",
        "minimum_maximum_vertical_ground_separation_m":round(float(result.x[-1]),3),
        "mathematical_rail_height_AT_SOURCE_SAMPLES_NOT_CONSTRUCTED":[round(float(v),3) for v in z],
        "actual_maximum_fitted_gradient_permille":round(float(max(fitted_grade)),4),
        "samples_measured":n,
        "theoretical_lower_bound_only_not_tunnel_bridge_or_CAPEX":True}
def compute(g43,g47):
    east,stations=source_profiles(g43,g47)
    rows=[]
    for profile in [east]+stations:
        stage=profile["site_id"]
        for grade in NOMINAL_GRADES_PERMILLE:
            for fixed in (False,True):
                params=((None,REFERENCE_VERTICAL_RADII_M) if stage=="ZAMORA_G43_6KM"
                       else ("station",(None,)))
                for R in params[1]:
                    funcs=("not_a_station",) if stage=="ZAMORA_G43_6KM" else tuple(STATION_SENSITIVITIES)
                    for function in funcs:
                        st=STATION_SENSITIVITIES[function]["station_max_permille"] if function in STATION_SENSITIVITIES else None
                        fit=minimax_grade_envelope(profile["x_m"],profile["y_m"],grade,
                           station_max_permille=st,vertical_radius_m=R,fixed_endpoints=fixed)
                        rows.append({"profile_id":stage,"city":profile["mandatory_city"],
                           "data_reference":profile["data_reference"],
                           "source_native_resolution_m":profile["original_source_resolution_m"],
                           "sample_count":len(profile["y_m"]),
                           "gradient_permille":grade, "grade_regime":classify(grade),
                           "ground_profile_length_km":round(float((profile["x_m"][-1]-profile["x_m"][0])/1000),3),
                           "terrain_elevation_min_m":round(float(np.min(profile["y_m"])),3),
                           "terrain_elevation_max_m":round(float(np.max(profile["y_m"])),3),
                           "station_function_sensitivity":function,
                           "station_local_grade_max_permille":st,
                           "station_straight_study_length_m":STATION_STRAIGHT_STUDY_M if st is not None else None,
                           "hypothetical_vertical_radius_m":R,
                           "endpoints_fixed_to_original_ground":fixed,
                           **fit})
    # Regression against previous exact actual G43 + G47 18/25 results, both free ends.
    regression=[]
    for grade in (18.0,25.0):
        old=next(c for c in g43["optimistic_grade_vertical_curvature_LP_sensitivity"]
           if c["grade_permille"]==grade and c["assumed_vertical_radius_m"] is None
              and not c["both_endpoints_fixed_at_sampled_ground"])
        new=next(q for q in rows if q["profile_id"]=="ZAMORA_G43_6KM"
            and q["gradient_permille"]==grade and q["hypothetical_vertical_radius_m"] is None
            and not q["endpoints_fixed_to_original_ground"])
        original=old["minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"]
        if abs(original-new["minimum_maximum_vertical_ground_separation_m"])>.015:
            raise ValueError("G48_G43_original_legacy_result_not_reproduced")
        regression.append({"source":"G43","gradient_permille":grade,
                           "old_minimax_m":original,"new_minimax_m":new["minimum_maximum_vertical_ground_separation_m"]})
    for site in stations:
        old_profile=next(c for c in g47["four_real_original_source_native_ground_station_3km_profiles"] if c["site_id"]==site["site_id"])
        for grade in (18.0,25.0):
            old=next(v for v in old_profile["real_original_DGT2m_18_25permille_minmax_optimistic_grade_tests"]
                     if v["grade_permille"]==grade)
            new=next(q for q in rows if q["profile_id"]==site["site_id"] and q["gradient_permille"]==grade
                   and q["station_function_sensitivity"]=="general_through_track_exploratory"
                   and not q["endpoints_fixed_to_original_ground"])
            original=old["minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"]
            if abs(original-new["minimum_maximum_vertical_ground_separation_m"])>.015:
                raise ValueError("G48_G47_original_legacy_result_not_reproduced_"+site["site_id"])
            regression.append({"source":"G47","profile":site["site_id"],"gradient_permille":grade,
                 "old_minimax_m":original,"new_minimax_m":new["minimum_maximum_vertical_ground_separation_m"]})
    # Strong policy sensitivity invariants: softer grade >= 12.5 can't increase best minimum.
    for profile in [east]+stations:
        id=profile["site_id"]
        subset=[q for q in rows if q["profile_id"]==id
            and not q["endpoints_fixed_to_original_ground"]
            and q["hypothetical_vertical_radius_m"] is None
            and q["station_function_sensitivity"] in ("not_a_station","general_through_track_exploratory")]
        vals=[next(q["minimum_maximum_vertical_ground_separation_m"] for q in subset
                    if q["gradient_permille"]==grade) for grade in NOMINAL_GRADES_PERMILLE]
        if any(a+.003<b for a,b in zip(vals,vals[1:])):
            raise ValueError("G48_grade_constraint_nesting_invariant_failed_"+id)
    for site in stations:
        for grade in NOMINAL_GRADES_PERMILLE:
            rs=[q for q in rows if q["profile_id"]==site["site_id"]
                 and q["gradient_permille"]==grade and not q["endpoints_fixed_to_original_ground"]]
            by={q["station_function_sensitivity"]:q["minimum_maximum_vertical_ground_separation_m"] for q in rs}
            if not(by["general_through_track_exploratory"]<=by["passenger_stop_PAT_ES_IFI_10_reference"]+.003<=
                   by["coupling_or_stabling_EU_TSI_2p5"]+.006):
                raise ValueError("G48_station_function_restriction_nesting_failed_"+site["site_id"])
    if len(rows)!=150 or len(regression)!=10:
        raise ValueError("G48_expected_150_source_mathematical_scenarios_and_10_backchecks")
    return rows,regression
def render(rows,figure,figure2):
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout="constrained")
    for ax,site in zip(axes.flat,("VR2","VR1","BR4","BR3")):
        for name,style,color in (("general_through_track_exploratory","o-","#276a84"),
                  ("passenger_stop_PAT_ES_IFI_10_reference","s--","#8b7542"),
                  ("coupling_or_stabling_EU_TSI_2p5","^:", "#8a4c6c")):
            subset=[q for q in rows if q["profile_id"]==site and not q["endpoints_fixed_to_original_ground"]
             and q["station_function_sensitivity"]==name]
            ax.plot([q["gradient_permille"] for q in subset],
              [q["minimum_maximum_vertical_ground_separation_m"] for q in subset],
              style,c=color,ms=4,label=name.replace("_"," ")[:38])
        ax.set_title(site+" · MDT2m original, 3km",loc="left")
        ax.set_xlabel("Rampa máxima da via geral (‰)");ax.set_ylabel("Afastamento vertical matemático mínimo (m)")
        ax.set_xticks(NOMINAL_GRADES_PERMILLE)
        ax.axvline(15,c="gray",alpha=.3,ls="--")
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.suptitle("G48 · Sensibilidade linha mista vs passageiros e funções de estação — limites matemáticos, não custos",fontsize=11)
    fig.savefig(figure,dpi=170,bbox_inches="tight");plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5.2),layout="constrained")
    for R,sty in ((None,"o-"),(10000,"s--"),(20000,"^:")):
        subset=[r for r in rows if r["profile_id"]=="ZAMORA_G43_6KM" and r["hypothetical_vertical_radius_m"]==R
            and not r["endpoints_fixed_to_original_ground"]]
        ax.plot([r["gradient_permille"] for r in subset],
                [r["minimum_maximum_vertical_ground_separation_m"] for r in subset],
                sty,label=f"Rv: {R if R is not None else 'não condicionado'} m")
    ax.set_xticks(NOMINAL_GRADES_PERMILLE);ax.grid(alpha=.2)
    ax.set_xlabel("Gradiente máximo da rasante matemática (‰)")
    ax.set_ylabel("Afastamento vertical mínimo aos 241 pontos MDT25 (m)")
    ax.set_title("G48 · Zamora: perfis sobre solo nu real, 12,5–25‰",loc="left")
    ax.legend()
    fig.savefig(figure2,dpi=170,bbox_inches="tight");plt.close(fig)
def write_outputs(g43,g47,jsonout,csvout,mdout,figout,fig2):
    rows,regression=compute(g43,g47)
    render(rows,figout,fig2)
    summary=[]
    for id in ("ZAMORA_G43_6KM","VR2","VR1","BR4","BR3"):
        selected=[q for q in rows if q["profile_id"]==id and not q["endpoints_fixed_to_original_ground"]
             and q["hypothetical_vertical_radius_m"] is None
             and q["station_function_sensitivity"] in ("not_a_station","general_through_track_exploratory")]
        summary.append({"profile":id,"reference_source":"G43_IGN25" if id.startswith("ZAMORA") else "G47_DGT2m",
          "grade_regime_minimax_envelope_m":{str(q["gradient_permille"]):q["minimum_maximum_vertical_ground_separation_m"] for q in selected}})
    output={"mission":"MN-GEO-RAIL-001","stage":"G48_gradient_policy_5cases_ground_source_G43_G47_recalibration",
       "policy_version":REGIME_VERSION,
       "primary_mixed_line_screens_permille":[12.5,15],
       "exceptional_freight_screens_permille":[18,20],
       "passenger_majority_not_freight_baseline_permille":[25],
       "traffic_function_must_be_decided_per_section_not_inferred_from_speed":True,
       "spanish_IFI_rules_are_not_blanket_portuguese_railway_permissions":True,
       "ES_IFI_official_source":ES_IFI,"EU_INF_TSI_official_source":EU_TSI,
       "EU_TSI_maximum_35permille_is_only_specific_P1_passenger_conditions_NOT_mixed":True,
       "G45_speed_research_screens_unchanged_kmh":list(SPEED_SCREENS_KMH),
       "all30_G10_27_G30_3_still_preserved":True,
       "G43_original_IGN25_241_source_points_verified":True,
       "G47_original_DGT2m_4x121_source_points_verified":True,
       "no_original_raster_reacquisition":True,
       "unconstrained_study_station_vs_10_PAT_reference_vs_2p5_if_operations_relevant":True,
       "mixed_freight_F1_F2_F3_exceptional_require_proven_eligibility_approvals_and_traction":True,
       "no_freight_traffic_fitted_at_25permille":True,
       "all_150_mathematical_regime_sensitivity_cases":rows,
       "10_exact_G43_G47_legacy_18_25_sensitivity_reproductions":regression,
       "five_profile_free_end_straight_case_comparison":summary,
       "no_terrain_subsurface_transition_station_engineering_or_timetable":True,
       "no_mobilidade_Norte_Fxx_or_site_publish":True,"Fxx_accepted":False,"Site_authorized":False,
       "PIC_Natura_hydrogeology_status":"UNKNOWN_NOT_LEGALLY_CLEARED"}
    jsonout.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    fields=("profile_id","city","data_reference","gradient_permille","station_function_sensitivity",
       "station_local_grade_max_permille","hypothetical_vertical_radius_m",
       "endpoints_fixed_to_original_ground","minimum_maximum_vertical_ground_separation_m",
       "actual_maximum_fitted_gradient_permille")
    with csvout.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
        for row in rows:w.writerow({k:row.get(k) for k in fields})
    md=["# G48 — Revisão normativa das inclinações e recálculo dos perfis originais G43 e G47",
      "","A partir de dados de solo nu originais **já adquiridos** (241 pontos MDT25 em Zamora, 484 pontos MDT2m nas quatro aproximações a estações), foi recalculado um problema de otimização linear de rasante **matemática**. Os **30 corredores e os cenários 160/200/250km/h continuam preservados**, mas as inclinações de 18‰/25‰ deixam de ser a dupla normativa de referência.",
      "","## 1 — Regimes de projeto (norma espanhola como referência, não aplicação automática em Portugal)",
      "",
      "| Limite | Interpretação funcional | Tratamento de engenharia |",
      "|---:|---|---|"]
    for grade in NOMINAL_GRADES_PERMILLE:
        q=classify(grade)
        md.append(f"| {grade:g}‰ | {q['traffic']} | {q['screen']} |")
    md+=["","A IFI espanhola distingue linha mista/mercadorias (12,5‰ referência, 15‰ normal condicionado, 18‰ exceção F1, 20‰ exceção F2–F3) e linhas de tráfego maioritário de passageiros (25‰ referência). **Estes limiares espanhóis NÃO são automaticamente aplicáveis ao território português.** O 25‰ **não valida mercadorias** no setor onde se aplique. A ETI europeia de infraestrutura não estabelece um 12,5‰ universal para todos os corredores; 35‰ aplica-se a casos P1 dedicados a passageiros com restrições específicas, não a linha mista.",
       "","## 2 — Perfis medidos: afastamento vertical matemático mínimo (extremos livres, sem raio vertical imposto)",
       "","| Sítio de estudo | 12,5‰ mista | 15‰ mista | 18‰ exceção | 20‰ exceção | 25‰ passageiros |",
       "|---|---:|---:|---:|---:|---:|"]
    for s in summary:
        vals=s["grade_regime_minimax_envelope_m"]
        md.append("| "+s["profile"]+" | "+" | ".join(f"{vals[str(float(g))]:.3f}" for g in NOMINAL_GRADES_PERMILLE)+" |")
    md+=["","O objetivo é minimizar o maior valor de **|z_ferrovia_math − z_terreno_medida|** nos pontos de terreno em planta já estudados. NÃO É um volume de escavação, profundidade de túnel ou altura de viaduto. A curva horizontal da grelha e as plataformas não foram validadas como ferrovia real; não há geologia nem obras ou custos modelados.",
       "","## 3 — Estações: função local distinta da via geral",
       "","Nas quatro aproximações de Vila Real e Bragança, além do gradiente máximo da via geral, ensaiaram-se três regimes num troço central hipotético de **800 m**:",
       "- sem limitação adicional de estação (comparação exploratória);",
       "- 10‰ como referência espanhola PAT para cruzamentos, ultrapassagens e paragem de passageiros sem estacionamento prolongado ou engate/desengate;",
       "- 2,5‰ quando aplicável a estacionamento prolongado ou operações regulares de engate/desengate (ETI e instrução nacional espanhola).",
       "Nenhum destes ensaios afirma que **todas** as plataformas exigem 2,5‰ nem valida uma estação real.",
       "","## 4 — Limites e continuidade",
       "- Os 150 ensaios incluem condições de extremos livres e fixados ao solo; o perfil espanhol testa também duas hipóteses não normativas de raio de concordância vertical (10 e 20km).",
       "- Foram reproduzidos como controlo de regressão os **10 valores anteriores 18‰/25‰** dos perfis G43/G47 sem restrição adicional. Os valores anteriores permanecem históricos, mas os novos cenários **12,5‰ e 15‰ passam a ser os principais**.",
       "- **18‰ e 20‰** só para sensibilidades condicionadas à classificação F1/F2/F3, decisão do gestor e aptidão real da exploração de mercadorias — nunca autorização presumida.",
       "- Análises de tração/frenagem com mercadorias, curvas de transição, geometria vertical longitudinal completa, geologia, hidrogeologia, Natura 2000 e PIC são condições futuras obrigatórias antes de quantificar obras.",
       "- Não houve novas aquisições DGT/CNIG; mantêm-se os 30 corredores, sete locais históricos e os três cenários de velocidade, com atualização da interpretação funcional por troço.",
       "","Fontes oficiais: "+ES_IFI+" ; "+EU_TSI,
       "","**Sem Fxx/Site. A avaliação demonstra apenas limites matemáticos com dados geográficos reais, não conformidade nem viabilidade de obra.**"]
    mdout.write_text("\n".join(md)+"\n")
    print("G48_RESULT",json.dumps({"profiles":summary,"total_lp_runs":len(rows),
      "legacy_values_verified":len(regression),"primary_mixed":[12.5,15],
      "exceptional_only":[18,20],"passenger_only_ref":25,
      "no_new_source":True,"no_fxx":True},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for k in ("g43","g47","json","csv","markdown","figure","figure2"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args()
    write_outputs(json.loads(a.g43.read_text()),json.loads(a.g47.read_text()),
        a.json,a.csv,a.markdown,a.figure,a.figure2)
if __name__=="__main__":main()
