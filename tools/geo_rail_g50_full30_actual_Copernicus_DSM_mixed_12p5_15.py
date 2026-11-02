#!/usr/bin/env python3
"""G50 restore full30 equal-method 160/200/250 regional grade comparison under
mixed 12.5/15, conditional 18/20, passenger 25 per mille.

Uses EXACT original source-locked G10+G30 research lattice, previous G32
selected smoothing, Copernicus GLO30 DSM (NOT original bare-earth DTM).
18 and 25 metric regression MUST match G32 historical 90 scenarios.
Separate module G48 physical DGT2m/IGN25 ground station profiles have much
higher evidential strength and must not be mixed with this DSM proxy.

No engineering, cost, tunnel length, train speed, service approval or legal
PIC conclusion; all 30 and all 90 research options remain.
"""
from __future__ import annotations
import argparse,csv,json,hashlib,math,sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g32_unified_30_90_comparison import (
  projection_points,radius_candidates,sample_dsm,SCENARIOS,DSM_SHA
)
from geo_rail_g31_terrain_natura_horizontal_vertical import profile
from geo_rail_gradient_policy_G48 import NOMINAL_GRADES_PERMILLE,classify
def verify(g10,g30,g32,dsm):
    paths=g10["features"]+g30["features"]
    ids={f["properties"]["id"] for f in paths}
    oldids={r["option_id"] for r in g32["rows"]}
    if len(paths)!=30 or len(ids)!=30 or ids!=oldids or len(g32["rows"])!=90:
        raise ValueError("G50_original_thirty_90_equal_source_study_options")
    if (g32["G10_count"]!=27 or g32["G30_count"]!=3 or
        g32["independent_source_original_Copernicus_GLO30_sha256"]!=DSM_SHA or
        g32["gradients_per_mille"]!=[18,25] or
        not g32["DSM_is_surface_vegetation_buildings_not_bare_earth"]):
        raise ValueError("G50_G32_real_historical_DSM_source_contract")
    if hashlib.sha256(dsm.read_bytes()).hexdigest()!=DSM_SHA:
        raise ValueError("G50_Copernicus_DSM_original_raster_SHA256_mismatch")
    if not all(r["not_railway_alignment"] and r["PIC_legal_source_UNRESOLVED"] for r in g32["rows"]):
        raise ValueError("G50_no_original_railway_or_PIC_clearance")
    return {f["properties"]["id"]:f for f in paths},{(r["option_id"],r["scenario_speed_kmh"]):r for r in g32["rows"]}
def stats(source,height,z,gradient):
    dist=np.linalg.norm(np.diff(source,axis=0),axis=1)
    if np.any(dist<=0):raise ValueError("G50_geometry_degenerate_original_400m")
    delta=np.asarray(z)-np.asarray(height)
    offset=(delta[:-1]+delta[1:])/2
    m=float(np.average(np.abs(offset),weights=dist))
    return {"gradient_permille":float(gradient),
      "traffic_and_exception_classification":classify(gradient),
      "original_DSM_400m_mean_abs_height_deviation_m_proxy":round(m,2),
      "original_DSM_400m_max_abs_height_deviation_m_proxy":round(float(np.max(np.abs(delta))),2),
      "original_DSM_distance_below_surface_by_more_than25m_km_NOT_tunnel":round(float(np.sum(dist[offset< -25])/1000),3),
      "original_DSM_distance_below_surface_by_more_than50m_km_NOT_tunnel":round(float(np.sum(dist[offset< -50])/1000),3),
      "original_DSM_distance_above_surface_by_more_than25m_km_NOT_viaduct":round(float(np.sum(dist[offset>25])/1000),3),
      "DSM_contains_buildings_canopy_and_not_ground":True,
      "sparse_400m_study_smoothing_and_vertical_profile_NOT_3D_rail_design":True}
def calculate(g10,g30,g32,src,output,csvout,mdout,plot):
    paths,old=verify(g10,g30,g32,src)
    result=[];regress=[]
    with rasterio.open(src) as ds:
        if ds.crs is None or ds.crs.to_epsg()!=4326:raise ValueError("G50_DSM_original_CRS_not_WGS84")
        for i,(key,f) in enumerate(paths.items(),1):
            xy=projection_points(f)
            fits=radius_candidates(xy)
            for speed in SCENARIOS:
                orig=old[(key,speed)]
                if speed not in fits:
                    if orig["pass_6km"]:
                        raise ValueError("G50_G32_qualifying_horizontal_original_failed_to_reproduce")
                    for grad in NOMINAL_GRADES_PERMILLE:
                        result.append({"option_id":key,"source_family":"G30" if key.startswith("G30") else "G10",
                             "scenario_speed_kmh":speed,
                             "gradient_permille":float(grad),
                             "status":"ORIGINAL_G32_6KM_RADIUS_PROXY_NOT_FOUND_NOT_NO_RAILWAY",
                             "source_G32_horizontal_6km_screen_pass":False,
                             "study_Natura_original_smoothed_overlap_km":orig["Natura_smoothed_km"],
                             "study_Alvao_Marao_original_smoothed_overlap_km":orig["Alvao_smoothed_km"],
                             "source_original_DSM_400m_horizontal_radius_unchanged":True,
                             "sparse_DSM_not_bareearth_cannot_infer_structures":True})
                    continue
                x,proof,envelope=fits[speed]
                if not orig["pass_6km"] or orig["shift_envelope_m"]!=envelope:
                    raise ValueError("G50_exact_G32_selected_horizontal_envelope_changed")
                height=sample_dsm(ds,x)
                for grad in NOMINAL_GRADES_PERMILLE:
                    ss,z,delta=profile(height,x,grad)
                    m=stats(x,height,z,grad)
                    row={"option_id":key,"source_family":"G30" if key.startswith("G30") else "G10",
                         "scenario_speed_kmh":speed,
                         "study_horizontal_source_length_km":orig["length_smoothed_km"],
                         "study_Natura_original_smoothed_overlap_km":orig["Natura_smoothed_km"],
                         "study_Alvao_Marao_original_smoothed_overlap_km":orig["Alvao_smoothed_km"],
                         "original_G32_source_horizontal_radius_proxy_m":orig["radius_estimate_m"],
                         "original_G32_source_planar_shift_envelope_m":envelope,
                         "source_G32_horizontal_6km_screen_pass":True,
                         "status":"ACTUAL_COPERNICUS_ORIGINAL_DSM_REGIONAL_GRADE_ONLY_NOT_BARE_EARTH",
                         **m}
                    result.append(row)
                    if grad in (18.,25.):
                        oldv=(orig["DSM_18permille_below25_km_not_tunnel"]
                              if grad==18 else orig["DSM_25permille_mean_abs_deviation_m"])
                        newv=(m["original_DSM_distance_below_surface_by_more_than25m_km_NOT_tunnel"]
                              if grad==18 else m["original_DSM_400m_mean_abs_height_deviation_m_proxy"])
                        if abs(float(oldv)-float(newv))>.02:
                            raise ValueError("G50_historical_G32_18_25_DEM_source_reference_regression_"+key+str(speed))
                        regress.append({"option_id":key,"speed_kmh":speed,"grade_permille":grad,
                            "historical_G32_value":oldv,"G50_recomputed_same_method_value":newv,
                            "within_0p02_original_units":True})
            print(f"G50_REGIONAL_RECALIBRATION {i}/30 {key}",flush=True)
    if len(result)!=450 or len({r["option_id"] for r in result})!=30:
        raise ValueError("G50_all_90_by_five_450_not_complete")
    selected=[r for r in result if r["scenario_speed_kmh"]==200
               and r.get("source_G32_horizontal_6km_screen_pass")]
    # Quantitative relative change across same source DSM. Not costs, not tunnel km.
    sensitivities=[]
    for key in paths:
        rr={r["gradient_permille"]:r for r in selected if r["option_id"]==key}
        if len(rr)!=5:
            sensitivities.append({"option_id":key,"has_200kmh_original_G32_horizontal_proxy":False,
                "not_evidence_of_unbuildability":True})
            continue
        a=rr[12.5]["original_DSM_400m_mean_abs_height_deviation_m_proxy"]
        b=rr[15.]["original_DSM_400m_mean_abs_height_deviation_m_proxy"]
        c=rr[25.]["original_DSM_400m_mean_abs_height_deviation_m_proxy"]
        sensitivities.append({"option_id":key,"has_200kmh_original_G32_horizontal_proxy":True,
           "MIXED_12p5_DSM_mean_abs_deviation_m":a,
           "MIXED_15_DSM_mean_abs_deviation_m":b,
           "PASSENGER_25_DSM_mean_abs_deviation_m":c,
           "MIXED_12p5_vs_passenger25_DSM_proxy_difference_m":round(a-c,2),
           "MIXED_15_vs_passenger25_DSM_proxy_difference_m":round(b-c,2),
           "source_Natura_2D_overlap_km_NOT_impact":rr[12.5]["study_Natura_original_smoothed_overlap_km"],
           "source_line_smoothing_length_km_NOT_rail_length":rr[12.5]["study_horizontal_source_length_km"],
           "no_rail_design_ranking_without_true_DTM_geology":True})
    out={"mission":"MN-GEO-RAIL-001","stage":"G50_regional_original_Copernicus_DSM_full30_corrected_five_gradients",
         "source_G48_gradient_policy":"G48-2026-11-02",
         "source_exact_original_Copernicus_GLO30_DSM_SHA256":DSM_SHA,
         "original_G10_27_G30_3_retained":True,"original_30_routes":30,
         "same_source_90_horizontal_speed_routes":[160,200,250],
         "regime_mixed_freight_main_permille":[12.5,15],
         "regime_exceptional_conditional_freight_permille":[18,20],
         "regime_passenger_not_mixed_permille":[25],
         "count_equal_source_route_speed_grade_cases":len(result),
         "grade_scenarios_on_same_original_90_geometries":result,
         "historical_G32_18_and_25_2016style_proxy_matches":regress,
         "200kmh_mixed_vs_passenger_regional_DSM_proxy_screen":sensitivities,
         "old_G32_mixed_gradients_18_25_superseded_not_deleted":True,
         "DSM_is_surface_vegetation_and_buildings_NOT_terrain":True,
         "no_DSM_25m_vertical_distances_are_actual_tunnel_or_viaduct":True,
         "new_DGT_raster_tiles_acquired":0,
         "Natura_PIC_geology_and_cultivated_land_legal_NOT_CLEARED":True,
         "does_not_replace_G48_735_ground_station_local_original_DTM":True,
         "not_railway_3D_curve_or_traction_running_time_COST":True,
         "Fxx_accepted":False,"Site_authorized":False}
    output.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
    fields=("option_id","source_family","scenario_speed_kmh","gradient_permille",
      "status","study_horizontal_source_length_km","study_Natura_original_smoothed_overlap_km",
      "original_DSM_400m_mean_abs_height_deviation_m_proxy",
      "original_DSM_distance_below_surface_by_more_than25m_km_NOT_tunnel",
      "original_DSM_distance_above_surface_by_more_than25m_km_NOT_viaduct")
    with csvout.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
        for r in result:w.writerow({k:r.get(k) for k in fields})
    chartdata=[q for q in sensitivities if q["has_200kmh_original_G32_horizontal_proxy"]]
    names=[q["option_id"] for q in chartdata]
    fig,ax=plt.subplots(figsize=(15,7),layout="constrained")
    ii=np.arange(len(chartdata));width=.27
    for k,shift,label in (("MIXED_12p5_DSM_mean_abs_deviation_m",-width,"Mista 12,5‰"),
                          ("MIXED_15_DSM_mean_abs_deviation_m",0,"Mista 15‰"),
                          ("PASSENGER_25_DSM_mean_abs_deviation_m",width,"Passageiros 25‰")):
        ax.bar(ii+shift,[q[k] for q in chartdata],width,label=label)
    ax.set_xticks(ii,names,rotation=65,ha="right",fontsize=7)
    ax.set_ylabel("Desvio vertical absoluto médio vs DSM (m) — NÃO obras")
    ax.set_title("G50 · Carteira completa a 200km/h, DSM original: 12,5‰/15‰ vs 25‰",loc="left")
    ax.legend();ax.grid(axis="y",alpha=.2)
    fig.savefig(plot,dpi=170,bbox_inches="tight");plt.close(fig)
    md=["# G50 — Reavaliar os 30 corredores e três velocidades para tráfego misto 12,5‰/15‰",
        "","**Mudança essencial:** o G32 inicialmente aplicou 18‰/25‰ como sensibilidades. O G50 recalcula **30 corredores × 3 cenários de velocidade × 5 gradientes = 450 observações** sobre EXATAMENTE os mesmos eixos de investigação e o mesmo **Copernicus GLO30 DSM original**. Os 18‰ e 25‰ históricos são reconstituídos e confrontados com o G32 como controlo de regressão.",
        "","**ATENÇÃO À FONTE:** o Copernicus DSM é **modelo de superfície**, com edifícios e vegetação, NÃO terreno de solo nu nem projeto ferroviário. Os desvios verticais apresentados são indicadores de pressão orográfica e enviesamento por superfície; não são quilómetros de túnel/viaduto, custos, expropriações, ou aprovação de qualquer linha. Os perfis G43/G47/G48 de terreno original DGT/IGN têm maior qualidade mas cobrem somente zonas locais.",
        "","## Matriz funcional a 200km/h (mesma geometria exploratória, fonte e método)",
        "","| Alternativa | 12,5‰ — MDS abs médio (m) | 15‰ — MDS abs médio (m) | 25‰ — MDS abs médio (m) | Natura na linha 2D (km; não impacte) |",
        "|---|---:|---:|---:|---:|"]
    for r in sensitivities:
        if not r["has_200kmh_original_G32_horizontal_proxy"]:
            md.append(f"| {r['option_id']} | Não demonstrado | Não demonstrado | Não demonstrado | Não avaliado |")
            continue
        md.append(f"| {r['option_id']} | {r['MIXED_12p5_DSM_mean_abs_deviation_m']:.2f} | {r['MIXED_15_DSM_mean_abs_deviation_m']:.2f} | {r['PASSENGER_25_DSM_mean_abs_deviation_m']:.2f} | {r['source_Natura_2D_overlap_km_NOT_impact']} |")
    md+=["","## Consequências para a seleção",
        "1. Preservar a função de mercadorias em **12,5‰ e 15‰ como comparadores fundamentais**. A comparação a 25‰ só informa alternativa predominantemente de passageiros, sem garantir frequência ferroviária ou tempos de marcha.",
        "2. Identificar setores onde a diferença 12,5‰ vs 15‰ é consistente e estudar com MDT de solo nu, não rejeitar corredores em função do DSM.",
        "3. Não utilizar os 18‰ e 20‰ como solução comum de mercadorias: são casos condicionados e requerem requisitos técnicos e legais próprios.",
        "4. Cruzar o rastreio regional com os **sete locais reais de estudo de estações**, as quatro análises MDT2m G47/G49 e as ligações rodoviárias; o melhor perfil geográfico da grelha não implica o melhor serviço territorial.",
        "5. Avançar para perfis 3D reais nos setores Alvão–Marão e Vila Real–Bragança, com DGT/CNIG nos troços em falta, geologia e hidrogeologia, Natura e PIC, antes de custos e shortlist definitiva.",
        "","Sem aquisição de dados novos, sem Fxx/Site."]
    mdout.write_text("\n".join(md)+"\n")
    print("G50_RESULT",json.dumps({"rows":len(result),"previous_regressions":len(regress),
       "200kmh_measured":len(chartdata),"cases":[{k:r[k] for k in ("option_id","MIXED_12p5_DSM_mean_abs_deviation_m","MIXED_15_DSM_mean_abs_deviation_m","PASSENGER_25_DSM_mean_abs_deviation_m")} for r in chartdata[:14]],
       "all30":True,"no_costs":True},ensure_ascii=False),flush=True)
def main():
    a=argparse.ArgumentParser()
    for f in ("g10","g30","g32","dsm","json","csv","markdown","plot"):
        a.add_argument("--"+f,required=True,type=Path)
    p=a.parse_args()
    calculate(*[json.loads(getattr(p,k).read_text()) for k in ("g10","g30","g32")],
      p.dsm,p.json,p.csv,p.markdown,p.plot)
if __name__=="__main__":main()
