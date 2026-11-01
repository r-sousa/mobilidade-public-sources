#!/usr/bin/env python3
"""G44 seven actual previously terrain-studied station-location refs and TWO
shared G10/G30 city connectors: radius-conditional two-chord geometry screening.
Screen local 160/200/250 circular tangent length and original DGT2m terrain,
road access / COS source. DOES NOT represent engineered tangent-clothoid rail
station connection, service authorization, tunnel portal or CBA. All30 retained.
"""
from __future__ import annotations
import argparse,csv,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point,LineString,mapping
from pyproj import Transformer
from geo_rail_g42_original_terrain_LP_all30_module_evidence import ANCHORS,SEGMENTS
CITY_BOUNDS={
 "Vila_Real":{"west":ANCHORS[0],"east":ANCHORS[1],"local_sector":"Vila_Real_local_W_to_E"},
 "Braganca":{"west":ANCHORS[2],"east":ANCHORS[3],"local_sector":"Braganca_local_W_to_E"}}
RADIUS={160:1500,200:2400,250:3700}
TO_WGS=Transformer.from_crs(3763,4326,always_xy=True)
def site_key(xy):return tuple(round(float(v),2) for v in xy)
def check(g35,g42):
    if (g35["G10_all_routes"]!=27 or g35["G30_all_routes"]!=3 or
        g35["original_DGT2m_COS2025_road_study_coordinate_sites"]!=7 or
        len(g35["comparisons_all30_times_two_mandatory_cities"])!=60 or
        len(g35["all_historical_source_geometry_context_rows"])!=870):
        raise ValueError("G44_original_7_29_30_source_site_contexts")
    if g42["original_count"]!=30 or not g42["original_G10_27_G30_3_preserved"]:
        raise ValueError("G44_original_all30_five_sectors")
    sectors={r["sector"]:r for r in g42["source_30_options_geographic_five_module_summary"]}
    for city,part in CITY_BOUNDS.items():
        if sectors[part["local_sector"]]["distinct_spatial_source_lattice_paths"]!=1:
            raise ValueError("G44_city_connector_no_longer_universal")
    if len(g35["source_7_original_site_ref_coordinates"])!=7:
        raise ValueError("G44_source_7_unique_coordinates_missing")
def geom(xy,city,speed):
    site=site_key(xy)
    bound=CITY_BOUNDS[city]
    west,east=bound["west"],bound["east"]
    a=math.dist(west,site);b=math.dist(site,east)
    ow=(site[0]-west[0],site[1]-west[1])
    oe=(east[0]-site[0],east[1]-site[1])
    if a<100 or b<100:raise ValueError("G44_site_too_close_to_city_grid_control_reference")
    dot=(ow[0]*oe[0]+ow[1]*oe[1])/(a*b)
    theta=math.degrees(math.acos(max(-1.,min(1.,dot))))
    R=RADIUS[speed]
    tangent=R*math.tan(math.radians(theta/2)) if theta<175 else None
    # This is a two-chord CIRCULAR arc T=R tan(Delta/2), not a connected
    # railway with station straight/platform, transitions or ground profile.
    bare_two_chord_length=a+b
    old_between=math.dist(west,east)
    possible=(tangent is not None and tangent<=min(a,b))
    return {"research_city":city,"speed_label_kmh_not_operating_speed":speed,
      "compulsory_W_E_study_grid_anchor_chord_m":[round(a,2),round(b,2)],
      "between_anchors_minimal_direct_chord_m":round(old_between,2),
      "site_dogleg_two_chord_distance_m_NOT_RAIL":round(bare_two_chord_length,2),
      "source_site_two_chord_deflection_deg":round(theta,3),
      "circular_minimum_tangent_length_for_assumed_radius_m":round(tangent,2) if tangent is not None else None,
      "simple_radius_corner_arc_tangency_WITHIN_both_approach_chords":possible,
      "does_not_include_station_straight_or_clothoid_or_full_track_connection":True,
      "no_vertical_DTM_between_station_and_city_anchors":True}
def collect(g35,g42):
    check(g35,g42)
    original=[r for r in g35["all_historical_source_geometry_context_rows"] if r["corridor"]=="P2-2-1"]
    if len(original)!=29:raise ValueError("G44_one_original_source_29_contexts_missing")
    by=defaultdict(list)
    for r in original:
        by[(r["mandatory_market"],site_key(r["source_original_site_XY"]))].append(r)
    if len(by)!=7 or {sum(bool(k[0]=="Vila_Real") for k in by),sum(bool(k[0]=="Braganca") for k in by)}!={3,4}:
        # The physical split is fixed from G25 historical source.
        raise ValueError("G44_unexpected_original_station_site_counts_city")
    sites=[];contexts=[]
    for city in ("Vila_Real","Braganca"):
        elements=sorted(((xy,rec) for (c,xy),rec in by.items() if c==city),key=lambda a:a[0])
        for i,(xy,records) in enumerate(elements):
            id=("VR" if city=="Vila_Real" else "BR")+str(i+1)
            roads=[r["G25_OSRM_2026_city_to_road_near_study_site_minutes"] for r in records]
            if len(set(roads))!=1 or None in roads:
                raise ValueError("G44_original_measured_site_road_drift")
            measured=[r["G23B_400m_ground_native_DGT2m_station_p90_m"] for r in records]
            approaches=[r["G23B_1000m_ground_native_DGT2m_approach18permille_p90_m"] for r in records]
            val={
              "candidate_site_id":id,"mandatory_city":city,
              "previous_source_original_XY_EPSG3763":list(xy),
              "original_source_G25_different_platform_orientation_contexts":len(records),
              "G25_original_OSRM_city_to_road_reference_minutes":roads[0],
              "source_nearest_routable_road_snap_m":records[0]["G25_road_to_site_snap_m"],
              "station_400m_original_DGT2m_source_p90_lowest_studied_m":min(measured),
              "station_400m_original_DGT2m_source_p90_highest_studied_m":max(measured),
              "approach_1000m_original_DGT2m_18permille_p90_lowest_studied_m":min(approaches),
              "approach_1000m_original_DGT2m_18permille_p90_highest_studied_m":max(approaches),
              "COS2025_400m_original_artificialized_area_pct":records[0]["COS2025_400m_artificialized_area_pct"],
              "COS2025_original_fraction_covered":records[0]["COS2025_original_fraction_covered"],
              "original_REN_RAN_CRUS_limited_WFS_status":records[0]["G27C_official_DGT_SNIT_wfs_bounded_source_status"],
              "original_legal_clearance":"UNKNOWN_NOT_APPROVED",
              "site_placement_only_previous_DGT_research_not_an_operable_station":True}
            site_geoms=[geom(xy,city,speed) for speed in RADIUS]
            val["horizontal_two_chord_local_geometry_sensitivities"]=site_geoms
            sites.append(val)
            for r in site_geoms:contexts.append({"candidate_site_id":id,**r})
    if sum(x["original_source_G25_different_platform_orientation_contexts"] for x in sites)!=29:
        raise ValueError("G44_all_29_station_orientation_contexts_lost")
    # Blind minimax or cost ranking would be invalid with unmeasured tunnels,
    # land, platform site geotech and future road access. Show transparent
    # observable tradeoffs and Pareto on original data only.
    dims=("G25_original_OSRM_city_to_road_reference_minutes",
          "station_400m_original_DGT2m_source_p90_lowest_studied_m",
          "approach_1000m_original_DGT2m_18permille_p90_lowest_studied_m",
          "source_nearest_routable_road_snap_m")
    for c in ("Vila_Real","Braganca"):
        group=[s for s in sites if s["mandatory_city"]==c]
        for x in group:
            front=not any(all(y[v]<=x[v]+1e-7 for v in dims) and any(y[v]<x[v]-1e-7 for v in dims)
                      for y in group if y is not x)
            x["non_dominated_using_only_four_old_road_terrain_proxies"]=front
            x["retain_for_railway_horizontal_vertical_site_fit_anyway"]=True
    return sites,contexts
def make(g35,g42,jout,csvout,mdout,figout,geoout):
    sites,scenarios=collect(g35,g42)
    all30=[r["option_id"] for r in g35["comparisons_all30_times_two_mandatory_cities"] if r["mandatory_city"]=="Vila_Real"]
    if len(set(all30))!=30:raise ValueError("G44_not30")
    # Every site is tested against the same source-city connector by design.
    comparable=[{"option_id":r,"family":"G30" if r.startswith("G30-") else "G10",
       "Vila_Real_original_site_candidates":[x["candidate_site_id"] for x in sites if x["mandatory_city"]=="Vila_Real"],
       "Braganca_original_site_candidates":[x["candidate_site_id"] for x in sites if x["mandatory_city"]=="Braganca"],
       "original_city_connectors_are_identical_across_all30":True,
       "railway_station_to_different_intercity_route_CONNECTION_NOT_ENGINEERED":True} for r in all30]
    out={"mission":"MN-GEO-RAIL-001","stage":"G44_old_seven_ground_station_sites_three_speed_horizontal_tangency_independent_design",
        "all_original_G10_27_G30_3_maintained":True,
        "all30_side_by_side_mandatory_station_site_candidates":comparable,
        "original_seven_previous_physical_DGT2m_station_study_refs":sites,
        "original_29_previous_DGT2m_platform_bearing_contexts_preserved":29,
        "two_city_station_site_original_tangent_tests":scenarios,
        "three_speed_sensitivity":list(RADIUS),
        "city_two_anchor_connector_is_universal_not_an_engineered_station_approach":True,
        "two_chord_circular_radius_fit_is_only_necessary_corner_envelope_not_station_geometry":True,
        "no_design_3D_aligned_approach_grade_or_platform_level":True,
        "no_independent_30_repetitions_of_the_same_city_station_data":True,
        "Natura_PIC_REN_RAN_PDM_access_legal_not_cleared":True,
        "no_tunnel_bridge_structures_costs_or_travel_times":True,
        "no_new_DGT_or_OSRM_acquisition":True,
        "Fxx_accepted":False,"Site_authorized":False}
    jout.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    with csvout.open("w",newline="",encoding="utf-8-sig") as f:
        fields=("candidate_site_id","mandatory_city","speed_label_kmh_not_operating_speed",
           "site_dogleg_two_chord_distance_m_NOT_RAIL","source_site_two_chord_deflection_deg",
           "circular_minimum_tangent_length_for_assumed_radius_m",
           "simple_radius_corner_arc_tangency_WITHIN_both_approach_chords")
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
        for row in scenarios:w.writerow({key:row.get(key) for key in fields})
    # Schematic is explicitly exact projected sites plus straight *chords*
    # for necessary-condition angles, not a viable 3D transport route.
    fig,ax=plt.subplots(figsize=(10,7),layout="constrained")
    cols={"Vila_Real":"#2c6585","Braganca":"#ac6b36"}
    for city,ends in CITY_BOUNDS.items():
        west,east=ends["west"],ends["east"]
        ax.plot([west[0]/1000,east[0]/1000],[west[1]/1000,east[1]/1000],
                lw=2.8,c=cols[city],alpha=.25,label=f"{city} - corda original entre âncoras")
        for v in [west,east]:ax.scatter(v[0]/1000,v[1]/1000,s=25,c=cols[city])
        for s in [x for x in sites if x["mandatory_city"]==city]:
            x,y=s["previous_source_original_XY_EPSG3763"]
            ax.plot([west[0]/1000,x/1000,east[0]/1000],
                [west[1]/1000,y/1000,east[1]/1000],lw=1.2,alpha=.65,c=cols[city],ls="--")
            ax.scatter(x/1000,y/1000,s=42,c=cols[city],edgecolor="white",zorder=6)
            ax.annotate(s["candidate_site_id"],(x/1000,y/1000),
                        xytext=(5,6),textcoords="offset points",fontsize=9)
    ax.set_aspect("equal",adjustable="datalim")
    ax.grid(alpha=.15);ax.set_xlabel("PT-TM06 (km) E");ax.set_ylabel("PT-TM06 (km) N")
    ax.set_title("G44 · 7 posições DGT2m e cordas de ligação exploratórias (NÃO ferrovia)",loc="left")
    ax.legend(fontsize=8);fig.savefig(figout,dpi=170,bbox_inches="tight");plt.close(fig)
    feats=[]
    for x in sites:
        xx,yy=x["previous_source_original_XY_EPSG3763"]
        lon,lat=TO_WGS.transform(xx,yy)
        feats.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
          "properties":{"source_site_id":x["candidate_site_id"],"mandatory_city":x["mandatory_city"],
            "source_original_road_access_min":x["G25_original_OSRM_city_to_road_reference_minutes"],
            "source_station_ground_DGT2m_p90_min_m":x["station_400m_original_DGT2m_source_p90_lowest_studied_m"],
            "original_study_not_approved_railway_station":True}})
    geoout.write_text(json.dumps({"type":"FeatureCollection","features":feats},ensure_ascii=False)+"\n")
    md=["# G44 — Retomar sete locais físicos de estação em Vila Real e Bragança: comparação de geometria necessária 160/200/250",
      "","**Nesta etapa, não se relocalizam estações nem se compram novos dados.** Reutilizam-se as sete posições DGT2m e os 29 ensaios de orientação G23–G27. G42 demonstrou que os módulos locais da grelha são únicos para os 30 corredores. Assim, avaliam-se separadamente os locais de estudo, sem atribuir 30 vezes as mesmas vantagens.",
      "","## Locais já medidos e elementos de geometria de aproximação",
      "","| Sítio | Cidade | Orientações previamente estudadas | OSRM original cidade→via próxima (min) | P90 MDT2m local menor–maior (m) | Curva circular R=2400m: tangentes cabem nas duas cordas? |",
      "|---|---|---:|---:|---|---|"]
    for site in sites:
        r=next(x for x in site["horizontal_two_chord_local_geometry_sensitivities"] if x["speed_label_kmh_not_operating_speed"]==200)
        md.append(f"| {site['candidate_site_id']} | {site['mandatory_city']} | {site['original_source_G25_different_platform_orientation_contexts']} | {site['G25_original_OSRM_city_to_road_reference_minutes']} | {site['station_400m_original_DGT2m_source_p90_lowest_studied_m']}–{site['station_400m_original_DGT2m_source_p90_highest_studied_m']} | {'Sim, só nesta condição necessária' if r['simple_radius_corner_arc_tangency_WITHIN_both_approach_chords'] else 'Não, nesta geometria simplificada'} |")
    md+=["","A curva de raio R e deflexão Δ numa inflexão das duas cordas exige espaço de tangência **T = R·tan(Δ/2)** em cada lado. Se T excede uma corda, esta ligação geométrica PARTICULAR não cabe; se T cabe, **não se prova nenhuma via**: faltam clotóides, estação retilínea, plataformas, rasantes, túneis, solo de construção, acessos legais e ambiente. Os controlos da grelha urbana são âncoras de investigação, não nós ferroviários projetados.",
      "","## Próxima etapa decisiva para 3D",
      "1. Definir 2–3 variantes de **aproximação ferroviária real a cada cidade** a partir dos sítios antigos com melhor combinação de acessibilidade rodoviária, topografia local e disponibilidade de território, sem escolher com base num único proxy.",
      "2. Deixar os controlos de grelha G10/G30 variar entre as faixas de aproximação nas extremidades, criando distância para as concordâncias, e testar raios mínimos de 160/200/250 em planta e comprimento retilíneo de estação.",
      "3. Utilizar os 84 MDT2m antigos apenas onde cobrem o desenvolvimento geométrico; identificar quadrículas adicionais antes de pedir dados, especialmente junto a portais ou vias rápidas.",
      "4. Cruzar cada aproximação com COS2025, malha rodoviária real, fontes REN/RAN/PDM, sítios Natura e hidrogeologia; dados administrativos WFS limitados não equivalem a conformidade.",
      "5. Só então ligar as aproximações locais aos 6/6/5 módulos interurbanos distintos identificados no G42, mantendo a comparação das 30 alternativas.",
      "","**Estas são posições de estudo, não estações decididas. As métricas de raio são necessárias mas não suficientes, e nada mede comprimento ferroviário construível, custos ou tempo de viagem. PIC permanece sem delimitação oficial. Sem Fxx/Site.**"]
    mdout.write_text("\n".join(md)+"\n")
    print("G44_RESULT",json.dumps({"sites":len(sites),
       "city_sites":{c:sum(s["mandatory_city"]==c for s in sites) for c in CITY_BOUNDS},
       "original_orientation_contexts":sum(s["original_source_G25_different_platform_orientation_contexts"] for s in sites),
       "200kmh_two_chord_tangent_tests":{s["candidate_site_id"]:next(x for x in s["horizontal_two_chord_local_geometry_sensitivities"] if x["speed_label_kmh_not_operating_speed"]==200) for s in sites},
       "all30_retained":True,"no_new_ground_source":True},ensure_ascii=False),flush=True)
def main():
    a=argparse.ArgumentParser()
    for k in ("g35","g42","json","csv","markdown","map","geojson"):
        a.add_argument("--"+k,required=True,type=Path)
    p=a.parse_args()
    make(json.loads(p.g35.read_text()),json.loads(p.g42.read_text()),
         p.json,p.csv,p.markdown,p.map,p.geojson)
if __name__=="__main__":main()
