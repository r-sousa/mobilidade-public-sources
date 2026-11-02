#!/usr/bin/env python3
"""G49 engineering decision intelligence: original 4 station source profiles
by mixed freight grades 12.5/15 and station function, 200 km/h G45 planar
approaches / G46 original tile coverage and G44 source road access; plus
grade-only gravity tractive effort/power/downgrade braking FLOOR for a few
transparent payload mass and speed hypotheses.

DO NOT mistake physics minimum for validated locomotive capability; power
also needed for rolling, curve, aero, acceleration and mechanical losses.
This makes no freight mixed claim at 25 per mille, no tunnel quantification
or route-level service/commercial analysis.
"""
from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path

G=9.80665
MASS_T=(1000,1500,2000)
SPEED_KMH=(40,60,80)
FREIGHT_GRADES=(12.5,15.,18.,20.)
STATION_CLASSES=("general_through_track_exploratory",
   "passenger_stop_PAT_ES_IFI_10_reference",
   "coupling_or_stabling_EU_TSI_2p5")
MIXED=(12.5,15.)
SITES=("VR2","VR1","BR4","BR3")
def grade_only(mass_t,grade_permille,speed_kmh):
    if mass_t<=0 or grade_permille<=0 or speed_kmh<=0:
        raise ValueError("G49_positive_physical_scenarios_only")
    force_kN=mass_t*1000*G*(grade_permille/1000)/1000
    # W = Newton x m/s. This is gross consist weight, not payload;
    # 1000/1500/2000 t do not imply 740m train automatically.
    power_MW=force_kN*1000*(speed_kmh/3.6)/1_000_000
    return {"gross_train_mass_t_HYPOTHESIS_NOT_REAL_STOCK":mass_t,
      "gradient_permille":float(grade_permille),
      "speed_constant_kmh_HYPOTHESIS":speed_kmh,
      "grade_gravity_only_force_kN":round(force_kN,3),
      "grade_gravity_only_ideal_rail_power_MW":round(power_MW,4),
      "grade_downgrade_energy_dissipation_floor_MW_if_same_speed":round(power_MW,4),
      "excluded_resistance_acceleration_adhesion_mechanical_losses":True,
      "not_train_brake_rating_or_locotractor_performance":True}
def input_guard(g48,g45,g46,g44):
    if (not g48["all30_G10_27_G30_3_still_preserved"] or
        g48["primary_mixed_line_screens_permille"]!=[12.5,15]
        or g48["exceptional_freight_screens_permille"]!=[18,20]
        or g48["passenger_majority_not_freight_baseline_permille"]!=[25]
        or len(g48["all_150_mathematical_regime_sensitivity_cases"])!=150
        or len(g48["10_exact_G43_G47_legacy_18_25_sensitivity_reproductions"])!=10):
        raise ValueError("G49_must_use_G48_real_ground_norm_recalibration")
    if (not g45["all_G10_27_and_G30_3_retained"] or
        len(g45["all_630_route_site_speed_horizontal_screen_cases"])!=630):
        raise ValueError("G49_source_G45_630_horizontal_required")
    if not g46["full30_options_still_studied"] or g46["old_verified_DGT_original_1km_tile_manifest"]!=84:
        raise ValueError("G49_source_G46_actual_DGT84_required")
    if not g44["all_original_G10_27_G30_3_maintained"] or len(g44["original_seven_previous_physical_DGT2m_station_study_refs"])!=7:
        raise ValueError("G49_source_G44_seven_old_stations")
def combine(g48,g45,g46,g44):
    input_guard(g48,g45,g46,g44)
    prof=g48["all_150_mathematical_regime_sensitivity_cases"]
    station={x["candidate_site_id"]:x for x in g44["original_seven_previous_physical_DGT2m_station_study_refs"]}
    candidate=[]
    for sid in SITES:
        if sid not in station:raise ValueError("G49_missing_old_physical_station")
        geo=[x for x in g45["all_630_route_site_speed_horizontal_screen_cases"]
           if x["option_id"]=="P2-2-1" and x["historical_site_id"]==sid
           and x["illustrative_speed_label_kmh"]==200]
        if len(geo)!=1 or not geo[0]["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"]:
            raise ValueError("G49_G45_pilot_200_missing_planar_candidate")
        region=station[sid]["mandatory_city"]
        ground={};full=[]
        for grad in (12.5,15.,18.,20.,25.):
            for func in STATION_CLASSES:
                rr=[z for z in prof if z["profile_id"]==sid and z["gradient_permille"]==grad
                      and not z["endpoints_fixed_to_original_ground"]
                      and z["hypothetical_vertical_radius_m"] is None
                      and z["station_function_sensitivity"]==func]
                if len(rr)!=1:raise ValueError("G49_original_G48_station_full_gradient_missing")
                r=rr[0]
                val=r["minimum_maximum_vertical_ground_separation_m"]
                if val is None:raise ValueError("G49_freely_fitted_real_ground_unavailable")
                ground[(grad,func)]=val
                full.append({"grade_permille":grad,"station_function":func,
                    "minimax_terrain_source_m":val})
        x=geo[0]["best_research_horizontal_solution"]
        old=station[sid]
        base=ground[(12.5,STATION_CLASSES[0])]
        mixed_station=ground[(12.5,STATION_CLASSES[1])]
        mixed_coupling=ground[(12.5,STATION_CLASSES[2])]
        candidate.append({"site_id":sid,"mandatory_city":region,
          "old_source_original_city_road_minutes":old["G25_original_OSRM_city_to_road_reference_minutes"],
          "old_source_routable_road_snap_m":old["source_nearest_routable_road_snap_m"],
          "source_G45_200kmh_best_2D_approach_path_m":x["total_connected_2D_centerline_length_m"],
          "source_G45_200kmh_curvature_radius_sample_m":x["min_sampled_radius_m"],
          "source_G45_200kmh_horizontal_detour_over_contact_chord_m":x["planimetric_length_excess_over_direct_chord_m"],
          "source_G45_200kmh_contact_east_shift_out_m":x["shift_east_anchor_outward_m"],
          "full_grade_and_station_functional_source_profile":full,
          "source_grade_12p5_rail_not_actual_reference_m":base,
          "mixed_12p5_station_passenger_10permille_profile_minimax_m":mixed_station,
          "mixed_12p5_station_coupling_2p5permille_profile_minimax_m":mixed_coupling,
          "station_10permille_increment_vs_unrestricted_m":round(mixed_station-base,3),
          "station_2p5permille_increment_vs_unrestricted_m":round(mixed_coupling-base,3),
          "mixed_15_station_10permille_profile_minimax_m":ground[(15.,STATION_CLASSES[1])],
          "passenger_25_station_10permille_profile_minimax_m":ground[(25.,STATION_CLASSES[1])],
          "site_original_3km_2m_ground_observed_not_entire_rail_to_city":True,
          "no_cost_estimation_from_minimax_or_planimetric_length":True})
    # Pareto separate by city, and only for observed measurable information.
    dims=("old_source_original_city_road_minutes",
      "source_G45_200kmh_horizontal_detour_over_contact_chord_m",
      "mixed_12p5_station_passenger_10permille_profile_minimax_m")
    for r in candidate:
        relevant=[other for other in candidate if other["mandatory_city"]==r["mandatory_city"] and other is not r]
        r["strict_three_observed_proxy_criteria"]=list(dims)
        r["dominated_on_three_proxies_by"]=[s["site_id"] for s in relevant
          if all(s[k]<=r[k]+1e-5 for k in dims) and any(s[k]<r[k]-1e-5 for k in dims)]
        r["old_site_must_not_be_eliminated_until_3D_traction_Natura_CAPEX"]=True
    # Freight physics just lower limits by gross weight, not commercial timetable.
    freight=[grade_only(mass,grade,v) for mass in MASS_T for grade in FREIGHT_GRADES for v in SPEED_KMH]
    ratios={str(k):round(k/12.5,3) for k in FREIGHT_GRADES}
    return candidate,freight,ratios
def report(g48,g45,g46,g44,jsonout,csvout,mdout):
    sites,freight,ratio=combine(g48,g45,g46,g44)
    out={"mission":"MN-GEO-RAIL-001","stage":"G49_mixed_station_and_freight_gravitational_lower_bounds",
        "source_G48_grade_policy":"G48-2026-11-02",
        "source_241_real_IGN25_and_484_real_DGT2m_ground_retained":True,
        "source_all30_G10_27_G30_3_retained":True,
        "stations_all7_old_sites_retained_four_detailed_two_by_city":True,
        "source_four_original_G47_DGT2m_3km_station_pilots":sites,
        "freight_gravity_only_scenario_mass_t":list(MASS_T),
        "freight_gravity_only_speed_kmh":list(SPEED_KMH),
        "freight_line_grades_reference_or_conditional_permille":list(FREIGHT_GRADES),
        "freight_gravity_only_force_and_ideal_power_lower_bounds":freight,
        "freight_grade_traction_gravity_load_multiplier_relative_12p5":ratio,
        "freight_25permille_NOT_accepted_in_mixed_line_scenarios":True,
        "no_740m_train_mass_to_length_conversion":True,
        "no_traction_adhesion_rolling_aero_resistance_curve_cant_braking_certificate":True,
        "mixed_normal_12p5_15_compared_to_station_10_or_2p5_operational_constraint":True,
        "original_station_3km_profiles_not_whole_city_RTE_T_corridor":True,
        "full30_still_requires_linked_stations_terrain_3D_capacity_geo_PIC_environment":True,
        "no_additional_original_DGT_OR_IGN_data_acquired":True,
        "Natura_PIC_and_administrative_approvals_NOT_cleared":True,
        "Fxx_accepted":False,"Site_authorized":False}
    jsonout.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    with csvout.open("w",newline="",encoding="utf-8-sig") as f:
        fields=("site_id","mandatory_city","old_source_original_city_road_minutes",
            "mixed_12p5_station_passenger_10permille_profile_minimax_m",
            "mixed_12p5_station_coupling_2p5permille_profile_minimax_m",
            "mixed_15_station_10permille_profile_minimax_m",
            "passenger_25_station_10permille_profile_minimax_m",
            "source_G45_200kmh_horizontal_detour_over_contact_chord_m",
            "source_G45_200kmh_contact_east_shift_out_m")
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
        for q in sites:w.writerow({key:q[key] for key in fields})
    lines=["# G49 — Decisões ferroviárias: rampa mista, função de estação e esforço físico mínimo de mercadorias",
       "","A partir dos **mesmos 241 pontos MDT25 IGN** e **484 pontos MDT2m DGT já validados** no G48, foram cruzadas as quatro estações de estudo com **acessibilidade rodoviária G44**, **geometria em planta G45 para 200km/h** e três funções alternativas de estação. Nada foi inferido sobre túnel ou custo a partir da altura relativa terreno–rasante.",
       "","## 1. O compromisso nas aproximações a estações",
       "","| Sítio | Acesso rodoviário anterior (min) | 12,5‰, PAT 10‰: afastamento minimax (m) | 12,5‰, engate/estac. 2,5‰ (m) | 15‰, PAT 10‰ (m) | 25‰ passageiros, PAT 10‰ (m) | Desvio de planta G45 (m) |",
       "|---|---:|---:|---:|---:|---:|---:|"]
    for q in sites:
        lines.append(f"| {q['site_id']} | {q['old_source_original_city_road_minutes']} | {q['mixed_12p5_station_passenger_10permille_profile_minimax_m']:.2f} | {q['mixed_12p5_station_coupling_2p5permille_profile_minimax_m']:.2f} | {q['mixed_15_station_10permille_profile_minimax_m']:.2f} | {q['passenger_25_station_10permille_profile_minimax_m']:.2f} | {q['source_G45_200kmh_horizontal_detour_over_contact_chord_m']:.0f} |")
    lines+=["","Os afastamentos são **mínimos matemáticos** em pontos de terreno amostrados na hipótese horizontal anterior, NÃO alturas de viadutos/túneis. O desvio em planta compara exclusivamente o eixo ensaiado com a corda entre contactos do mesmo ensaio; NÃO é acréscimo líquido ao percurso Porto–Zamora.",
       "","## 2. A inclinação de 12,5‰ vs 15‰ e a tração de mercadorias",
       "","A força gravitacional em rampa, antes de qualquer resistência de rolamento, curva, vento, aceleração, perdas ou limitação de aderência, obedece a **F = m·g·i** (i em fração). A potência ideal para velocidade constante é **P = F·v**. Na descida, a mesma potência é somente uma referência energética ideal a dissipar/recuperar, não rating do freio.",
       "","| Massa bruta hipotética do comboio | Rampa 12,5‰: força / P a 60 km/h | Rampa 15‰: força / P a 60 km/h | 18‰ excecional: força / P a 60 km/h | 20‰ excecional: força / P a 60 km/h |",
       "|---|---|---|---|---|"]
    for mass in MASS_T:
        vals=[next(z for z in freight if z["gross_train_mass_t_HYPOTHESIS_NOT_REAL_STOCK"]==mass
              and z["gradient_permille"]==r and z["speed_constant_kmh_HYPOTHESIS"]==60) for r in FREIGHT_GRADES]
        lines.append(f"| {mass} t | "+" | ".join(f"{z['grade_gravity_only_force_kN']:.1f} kN / {z['grade_gravity_only_ideal_rail_power_MW']:.2f} MW" for z in vals)+" |")
    lines+=["","Relativamente a 12,5‰, as forças gravitacionais sobem **20% a 15‰, 44% a 18‰ e 60% a 20‰**, para a mesma massa e velocidade. Os valores são limites inferiores da força/potência requerida, NÃO comprovam número de locomotivas, massa rebocável ou desempenho comercial. O comprimento de 740/750m não determina massa bruta sem composição real.",
       "","A maior carga rebocada e a rampa efetiva devem ser testadas com curvas oficiais de esforço de tração e potência das locomotivas disponíveis, aderência, forças resistentes, travagem, condições climáticas, declive máximo contínuo e zonas de paragem; **não usar 25‰ para justificar tráfego de mercadorias**.",
       "","## 3. Critérios que já diferenciam a escolha",
       "","Além do melhor ajuste altimétrico matemático, as quatro opções apresentam tempos de acesso rodoviário e desvios em planta diferentes. A dominância geométrica parcial calculada só usa estas três variáveis observadas e **não elimina locais**: geologia, comprimento de túneis/viadutos, travessia ambiental, posição da via geral, intermodalidade e CAPEX permanecem desconhecidos.",
       "","## 4. Continuidade de engenharia — sem repetições de aquisições",
       "1. Projetar duas famílias funcionais em cada um dos cinco módulos (mista com 12,5‰/15‰ e passageiros a 25‰), preservando todas as 30 alternativas de origem.",
       "2. Nas estações, diferenciar plataforma de passageiros, estacionamento e operações de engate/desengate, fixando zonas retilíneas e transições no relevo medido.",
       "3. Usar os blocos já preservados DGT2m e o registo exato G46 das 10 quadrículas condicionais para estender os perfis de ±1,5km para ±3km apenas nos eixos que mostrarem possibilidade de concordância horizontal/vertical; identificar carência de píxeis e datum.",
       "4. Confrontar geologia Marão–Alvão, águas, Natura 2000, PIC, velocidade verdadeira, capacidade de passageiros/mercadorias e qualidade de serviço a Guimarães, Amarante, Mirandela e Macedo de Cavaleiros antes de uma seleção final.",
       "","**Sem custos, tempos de marcha, traçado ferroviário homologado nem aprovação ambiental. Sem novas quadrículas DGT, Fxx/Site.**"]
    mdout.write_text("\n".join(lines)+"\n")
    print("G49_RESULT",json.dumps({"stations":[{k:v for k,v in q.items() if k in ("site_id","mandatory_city","old_source_original_city_road_minutes","mixed_12p5_station_passenger_10permille_profile_minimax_m","mixed_12p5_station_coupling_2p5permille_profile_minimax_m","mixed_15_station_10permille_profile_minimax_m","source_G45_200kmh_horizontal_detour_over_contact_chord_m","dominated_on_three_proxies_by")} for q in sites],
        "freight_1500t_60kmh":[z for z in freight if z["gross_train_mass_t_HYPOTHESIS_NOT_REAL_STOCK"]==1500 and z["speed_constant_kmh_HYPOTHESIS"]==60],
        "scenarios":len(freight),"all30":True},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for q in ("g48","g45","g46","g44","json","csv","markdown"):
        p.add_argument("--"+q,required=True,type=Path)
    a=p.parse_args()
    report(*[json.loads(getattr(a,q).read_text()) for q in ("g48","g45","g46","g44")],
       a.json,a.csv,a.markdown)
if __name__=="__main__":main()
