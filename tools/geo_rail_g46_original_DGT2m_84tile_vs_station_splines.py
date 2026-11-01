#!/usr/bin/env python3
"""G46 real source coverage of 84 existing original DGT2m 1km tiles against
G45 30x7x3 proposed 2D (NOT engineered rail) station approaches.
Exact native grid-index inventory from G37; whole route, +/-1.5km, +/-3km
longitudinal from actual 7 station study physical point with +/-200m lateral.
This maps missing original source tiles, not actual NoData pixel validation,
land permissions, railway engineering, or approval for DGT acquisition.
"""
from __future__ import annotations
import argparse,csv,json,math,sys
from pathlib import Path
from collections import defaultdict
from shapely.geometry import LineString,Point
from shapely.ops import substring,unary_union
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g26b_next_DGT2m_study_footprint_gate import indices

LONGITUDINAL=(1500,3000)
HALFWIDTH_M=200
KEY_OPTIONS=("P2-2-1","G30-geographic_diversity")
def validate(g45,g37):
    if (not g45["all_G10_27_and_G30_3_retained"] or g45["source_30_options"]!=30
        or g45["seven_original_DGT2m_study_sites"]!=7 or
        len(g45["all_630_route_site_speed_horizontal_screen_cases"])!=630):
        raise ValueError("G46_G45_full30_7_630_provenance")
    originals=g37["source_84_original_DGT_tile_ids_in_PTTM06"]
    if len(originals)!=84 or len({tuple(x) for x in originals})!=84:
        raise ValueError("G46_exact_original_DGT84_source_manifest_missing")
    if g37["tile_index_offset_original_DGT"]!=[200,301] or not g37["no_new_DGT_2m_tile_order"]:
        raise ValueError("G46_original_DGT_grids_or_not_ordered_drift")
    return {tuple(int(v) for v in x) for x in originals}
def segment_from_station(sol,site_xy,half_length):
    line=LineString(sol["sampled_QA_path_PT_TM06"])
    if line.is_empty or line.length<2000 or not line.is_simple:
        raise ValueError("G46_G45_planar_geometry_invalid")
    center=line.project(Point(site_xy))
    # Explicit G45 800m station straight; site point should be on candidate
    # centerline within original rounding uncertainty, not shifted territory.
    if line.distance(Point(site_xy))>5.0:
        raise ValueError("G46_previous_station_physical_point_not_on_new_straight")
    if half_length is None:return line
    return substring(line,max(0,center-half_length),
                           min(line.length,center+half_length))
def tile_footprint(geom,existing):
    # 2D centerline is still a study path, lateral width purely hypothetical
    required=indices(geom.buffer(HALFWIDTH_M,cap_style=2,join_style=2))
    return required,required&existing,required-existing
def calc(g45,g37):
    existing=validate(g45,g37)
    sites={s["candidate_site_id"]:s for s in g45["site_source_original_road_COS_DGT2m_from_G44"]}
    if len(sites)!=7:raise ValueError("G46_seven_original_sites_distinct")
    rows=[];tile_by_case={}
    for record in g45["all_630_route_site_speed_horizontal_screen_cases"]:
        case=(record["option_id"],record["historical_site_id"],record["illustrative_speed_label_kmh"])
        if record["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"] is not True:
            rows.append({"option_id":case[0],"site_id":case[1],"speed_label_kmh":case[2],
              "source_G45_geometric_candidate_exists":False,"DGT_2m_tile_count":"NOT_ASSESSED",
              "no_buildability_without_terrain":True})
            continue
        site=sites[case[1]]
        xy=site["previous_source_original_XY_EPSG3763"]
        sol=record["best_research_horizontal_solution"]
        for domain_name,half in (("local_1p5km",1500),("local_3km",3000),("entire_horizontal_study_connector",None)):
            gg=segment_from_station(sol,xy,half)
            req,old,gap=tile_footprint(gg,existing)
            key=case+(domain_name,)
            tile_by_case[key]=(req,old,gap)
            row={
              "option_id":case[0],"site_id":case[1],
              "mandatory_city":site["mandatory_city"],
              "speed_label_kmh":case[2],
              "source_G45_geometric_candidate_exists":True,
              "source_original_existing_DGT_tile_index_producer_basis":84,
              "candidate_local_domain":domain_name,
              "candidate_planimetric_halfwidth_m_NOT_RAILWAY_WORKS":HALFWIDTH_M,
              "required_1km_original_DGT_tile_count_conditional":len(req),
              "already_in_84_original_DGT_tile_manifest":len(old),
              "missing_tile_count_IF_this_2D_buffer_study_adopted":len(gap),
              "missing_original_1km_DGT_tile_ColRow_conditional":[list(x) for x in sorted(gap)],
              "tile_present_does_not_prove_valid_2m_pixels_or_raster_coverage":True,
              "no_authorized_DGT2m_download":True,
              "station_tangent_800m_not_full_3D_railway":True,
              "speed_radius_only_not_operating_speed":True}
            rows.append(row)
    by_site=defaultdict(list)
    for r in rows:
        if (r.get("source_G45_geometric_candidate_exists") and
           r["candidate_local_domain"]=="local_1p5km" and
           r["speed_label_kmh"]==200 and r["option_id"]=="P2-2-1"):
            by_site[r["site_id"]].append(r)
    # A deliberate source acquisition pilot, NOT an overall station ranking:
    # retain special Bragança BR4 for the shiftable-anchor finding, and sample
    # one contrasting old DGT2m station siting location per city.
    selected=[]
    for city in ("Vila_Real","Braganca"):
        avail=[s for s in sites.values() if s["mandatory_city"]==city and s["candidate_site_id"] in by_site]
        if len(avail)<2:raise ValueError("G46_not_two_old_station_reference_sites_200")
        def priority(s):
            r=by_site[s["candidate_site_id"]][0]
            return (r["missing_tile_count_IF_this_2D_buffer_study_adopted"],
                    s["G25_original_OSRM_city_to_road_reference_minutes"],s["candidate_site_id"])
        first=("BR4" if city=="Braganca" and "BR4" in by_site else min(avail,key=priority)["candidate_site_id"])
        second=min((s for s in avail if s["candidate_site_id"]!=first),key=priority)["candidate_site_id"]
        selected.extend([first,second])
    p2=[next(r for r in rows if r.get("option_id")=="P2-2-1" and r.get("site_id")==id and
              r.get("speed_label_kmh")==200 and r.get("candidate_local_domain")=="local_1p5km")
        for id in selected]
    unions={}
    for half_name in ("local_1p5km","local_3km","entire_horizontal_study_connector"):
        ids=set().union(*(tile_by_case[("P2-2-1",site,200,half_name)][0] for site in selected))
        unions[half_name]={"pilot_four_original_station_sites":list(selected),
          "required_1km_DGT2m_tiles":len(ids),
          "already_preserved_original_tiles":len(ids&existing),
          "missing_if_this_specific_pilot_domain":"NOT_PURCHASE_ORDER",
          "conditional_missing_indices":[list(x) for x in sorted(ids-existing)],
          "missing_tile_count":len(ids-existing)}
    per_city=[]
    for city in ("Vila_Real","Braganca"):
        refs=[r for r in rows if r.get("mandatory_city")==city and r.get("candidate_local_domain")=="local_1p5km"]
        for speed in (160,200,250):
            speedrows=[r for r in refs if r["speed_label_kmh"]==speed]
            per_city.append({"city":city,"speed_label_kmh":speed,
              "source_G45_solutions_with_DGT_tiled_footprint_tested":len(speedrows),
              "median_missing_tile_count_per_2D_site_1p5km":(sorted(r["missing_tile_count_IF_this_2D_buffer_study_adopted"] for r in speedrows)[len(speedrows)//2] if speedrows else None),
              "existing_only_original_tile_manifest_no_raster_pixel_QA":True})
    return rows,unions,p2,selected,per_city,existing
def execute(g45,g37,outjson,csvpath,mdout,pngout):
    rows,union,pilot,sites,city,existing=calc(g45,g37)
    out={"mission":"MN-GEO-RAIL-001","stage":"G46_G45_real_study_2D_station_approach_DGT2m_tile_gaps_all30",
      "full30_options_still_studied":True,"source_630_station_speed_cases_reused":630,
      "old_verified_DGT_original_1km_tile_manifest":84,
      "seven_original_study_sites_retained":7,
      "all30_station_study_radius_source_cases_and_buffer_gaps":rows,
      "pilot_four_prior_station_site_ids_for_data_coverage_ONLY_not_site_ranking":sites,
      "pilot_each_station_1p5km_G45_200kmh_P2_2_1_reference":pilot,
      "four_pilot_station_combined_G45_source_2D_terrain_footprint_gaps":union,
      "by_city_and_speed_coverage_summary":city,
      "sampled_G45_spline_not_compliant_engineered_rail":True,
      "DGT_source_tiles_existing_does_NOT_mean_2m_pixel_are_valid":True,
      "requires_continuous_DTM2m_and_survey_for_real3D":True,
      "no_new_DGT_original_downloads":True,
      "no_statutory_or_tunnel_geology_natura_PIC_clearance":True,
      "no_tunnel_bridge_or_cost_or_real_train_timetable":True,
      "Fxx_accepted":False,"Site_authorized":False}
    outjson.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    keys=("option_id","site_id","speed_label_kmh","candidate_local_domain",
       "required_1km_original_DGT_tile_count_conditional","already_in_84_original_DGT_tile_manifest",
       "missing_tile_count_IF_this_2D_buffer_study_adopted")
    with csvpath.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=keys,delimiter=";");w.writeheader()
        for r in rows:w.writerow({k:r.get(k) for k in keys})
    fig,ax=plt.subplots(figsize=(10,5.5),layout="constrained")
    labels=[r["site_id"] for r in pilot]
    covers=[r["already_in_84_original_DGT_tile_manifest"] for r in pilot]
    missing=[r["missing_tile_count_IF_this_2D_buffer_study_adopted"] for r in pilot]
    xx=range(len(pilot))
    ax.bar(xx,covers,label="Já existem (1km de MDT DGT original)",color="#416c87")
    ax.bar(xx,missing,bottom=covers,label="Em falta, se faixa 2D ±200m adotada",color="#b6814c")
    ax.set_xticks(list(xx),labels);ax.set_ylabel("Quadrículas originais DGT 1 km²")
    ax.set_title("G46 · Faixa de 1,5km para quatro sítios — cobertura de dados, NÃO custos",loc="left")
    ax.grid(axis="y",alpha=.17);ax.legend(fontsize=8)
    fig.savefig(pngout,dpi=160,bbox_inches="tight");plt.close(fig)
    lines=["# G46 — Cobertura real do inventário MDT2m DGT em aproximações de estação G45",
       "","**G45 não é projeto ferroviário 3D.** A presente etapa não adquire dados adicionais: cruza as 630 combinações originais (27 G10 + 3 G30, sete posições antigas, três velocidades de ensaio) com os **84 identificadores originais de quadrículas 1km DGT de solo nu** anteriormente verificados no G37.",
       "","A geometria das alternativas com solução de planta é aproximada por poligonais G45 amostradas, com faixas de 200m de cada lado ao longo de 1,5km e 3km da posição física de estudo e também ao longo de toda a aproximação candidata. A contagem de quadrículas é um **inventário condicionado de dados**, não extensão de expropriação, obra ou encomenda DGT.",
       "","## Quatro locais de ensaio para um primeiro aprofundamento do MDT",
       "","A escolha de dois locais por cidade procura combinar diversidade com reutilização de terreno; **BR4 entra deliberadamente** por representar o problema de concordância corrigido em G45. É uma prioridade de aquisição experimental, não seleção da localização ferroviária definitiva.",
       "","| Cidade | Sítio de estudo | Quadrículas necessárias a ±1,5km e ±200m | Já no inventário DGT84 | Em falta |",
       "|---|---|---:|---:|---:|"]
    sites_lookup={s["candidate_site_id"]:s for s in g45["site_source_original_road_COS_DGT2m_from_G44"]}
    for p in pilot:
        lines.append(f"| {sites_lookup[p['site_id']]['mandatory_city']} | {p['site_id']} | {p['required_1km_original_DGT_tile_count_conditional']} | {p['already_in_84_original_DGT_tile_manifest']} | {p['missing_tile_count_IF_this_2D_buffer_study_adopted']} |")
    lines+=["","## União de quadrículas dos quatro estudos",
      "","| Domínio condicional | Quadrículas distintas | Já disponíveis | Em falta |",
      "|---|---:|---:|---:|"]
    for key,q in union.items():
        lines.append(f"| {key} | {q['required_1km_DGT2m_tiles']} | {q['already_preserved_original_tiles']} | {q['missing_tile_count']} |")
    lines+=["","## Decisão operativa",
       "1. **Não repetir DGT84.** Confrontar os índices em falta com a cobertura vigente do portal DGT e os direitos/credenciais já criados; só pedir as quadrículas identificadas e documentar o mosaico original.",
       "2. Se houver muitos pedidos para a aproximação completa, obter primeiro o segmento próximo da estação, 1,5km–3km, mantendo alternativas e velocidades em comparação.",
       "3. Testar a rasante e o MDT2m através de perfis continuamente ao longo das novas geometrias, com validação de NoData, sistema de alturas, 18‰/25‰ e curvas verticais.",
       "4. Confirmar geologia, aquíferos, falhas e condicionantes em portais antes de afirmar existência de túneis ou viadutos, custos ou tempos comerciais.",
       "5. Os 30 corredores e sete locais de estudo permanecem disponíveis na matriz integral. PIC sem delimitação oficial; Natura 2000 não aprovado.",
       "","**Fontes de dados e condição:** existência de quadrícula DGT2m não equivale a raster válido em todo o eixo. O G46 é um portão para aquisição, não ordem executada, estimativa de custo ou traçado legalmente implantável. Sem Fxx/Site."]
    mdout.write_text("\n".join(lines)+"\n")
    print("G46_RESULT",json.dumps({"pilot_sites":sites,"pilots":[{k:p[k] for k in ("site_id","required_1km_original_DGT_tile_count_conditional","already_in_84_original_DGT_tile_manifest","missing_tile_count_IF_this_2D_buffer_study_adopted")} for p in pilot],
      "unions":{k:{key:v for key,v in q.items() if key!="conditional_missing_indices"} for k,q in union.items()},
      "observed_84_source_tiles":84,"all630_compared":True,"no_new_downloads":True},ensure_ascii=False),flush=True)
def main():
    ap=argparse.ArgumentParser()
    for key in ("g45","g37","json","csv","markdown","plot"):ap.add_argument("--"+key,required=True,type=Path)
    a=ap.parse_args()
    execute(json.loads(a.g45.read_text()),json.loads(a.g37.read_text()),a.json,a.csv,a.markdown,a.plot)
if __name__=="__main__":main()
