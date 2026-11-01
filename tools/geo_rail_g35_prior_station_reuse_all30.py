#!/usr/bin/env python3
"""G35 reconcile actual historic DGT2m study station sites G23-G27 with ALL 30 routes.

G23B 351 physical local bearing/shift sensitivities -> G24 29 context shortlist
-> G25 source-measured road access -> G27B native COS2025 land -> G27C
original official legal source queries. Reuse, NEVER restart siting or grant
permission. Evaluate same physical candidates against each new ORIGINAL research
grid with position+3/6km chord heading screens, 160/200/250 radius context,
not a connected rail approach or true station buildability.
"""
import argparse,csv,hashlib,json,math,sys
from pathlib import Path
from collections import Counter,defaultdict
from shapely.geometry import Point,LineString,shape,mapping
from shapely.ops import transform as shtransform,unary_union
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g24_grid_station_connection_geometry import (
    chord_axis,axis_bearing_mismatch_deg,RADIUS_BY_SPEED
)
TO_PT=Transformer.from_crs(4326,3763,always_xy=True)
TO_WGS=Transformer.from_crs(3763,4326,always_xy=True)
MANDATORY=("Vila_Real","Braganca")
SOURCE_G25_SHA="be35181c882c2f6ede4d07f7e0a68b084bb6247c54a7da0d1d566a66f844dffd"
SITE_RAD=400
def digest(raw):return hashlib.sha256(raw).hexdigest()
def xykey(xy):return tuple(round(float(v),2) for v in xy)
def file_json(path):return json.loads(path.read_bytes())
def validate(g10,g30geo,g25,g27b,g27c,g32,g33,g34):
    originals=g10.get("features",[]);news=g30geo.get("features",[])
    expected={"P"+str(a)+"-"+str(b)+"-"+str(c) for a in range(1,4) for b in range(1,4) for c in range(1,4)}
    if len(originals)!=27 or {f["properties"]["id"] for f in originals}!=expected:
        raise ValueError("G35_preserve_every_original_G10")
    if len(news)!=3 or {f["properties"]["id"] for f in news}!={"G30-"+p for p in ("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity")}:
        raise ValueError("G35_preserve_all_three_G30")
    if len(g25.get("source_shortlisted_road_reference_route_cases",[]))!=g25.get("G24_same_city_original_study_shortlist_rows"):
        raise ValueError("G35_G25_real_station_prior_road_cases_incomplete")
    if g25.get("G24_3_corridor_source_lines_not_real_rail_alignments")!=True or g25.get("Fxx_accepted") or g25.get("Site_authorized"):
        raise ValueError("G35_G25_not_approved_station_source")
    if not (g27b.get("seven_mandatory_city_station_research_sector_dossiers") and
            len(g27b["seven_mandatory_city_station_research_sector_dossiers"])==7 and
            not g27b["Fxx_accepted"] and not g27b["Site_authorized"]):
        raise ValueError("G35_G27B_seven_real_land_studies_required")
    if g27c.get("source_research_sites")!=7 or len(g27c.get("seven_research_site_by_service_source_status",[]))!=7:
        raise ValueError("G35_G27C_original_official_SNiT_sources_missing")
    if not g27c.get("all_PDM_REN_official_DR_legal_map_validation_pending") or not g27c.get("no_station_eliminated_or_approved"):
        raise ValueError("G35_G27C_legal_warning_mandatory")
    if g32.get("total_rows")!=90 or g32.get("G10_count")!=27 or g32.get("G30_count")!=3 or not g32.get("canonical_portfolio_next_stages_all_27_G10_plus_3_G30"):
        raise ValueError("G35_G32_30x3_technical_missing")
    if g33.get("six_city_combinations")!=180 or g33.get("G10")!=27 or g33.get("G30")!=3 or len(g33.get("six_city_all_180_records",[]))!=180:
        raise ValueError("G35_G33_30x6_city_source_missing")
    if not (g34.get("all30_same_method") and g34.get("30_times_six_city_study_geographic_census_cases")==180
            and len(g34.get("corridor_six_city_radius10km_unions_no_overlap_duplication",[]))==30):
        raise ValueError("G35_G34_30_demographic_union_must_not_be_lost")
    if not g25.get("two_compulsory_cities")==["Vila Real","Bragança"] or not g25.get("Sanabria_excluded"):
        raise ValueError("G35_mandatory_cities_or_Sanabria")
    for x in (g25,g27b,g27c):
        if x.get("Fxx_accepted") or x.get("Site_authorized"):raise ValueError("G35_no_canonical_publication")
    return originals+news
def match_source(g25,g27b,g27c):
    # Historical G25 29 shortlisted source cases contain repeated physical
    # positions with different family and platform-bearing hypotheses.
    sites=g25["source_shortlisted_road_reference_route_cases"]
    seen=defaultdict(list)
    for v in sites:
        if v["mandatory_market"] not in MANDATORY:raise ValueError("G35_nonmandatory_ground_site")
        x=xykey(v["original_study_EPSG3763_XY"])
        if not v.get("not_a_legal_station_road_access_or_last_mile",False):
            raise ValueError("G35_no_road_site_permit_claim")
        seen[x].append(v)
    land={xykey(r["original_study_xy_EPSG3763"]):r for r in g27b["seven_mandatory_city_station_research_sector_dossiers"]}
    legal={xykey(r["source_xy_EPSG3763"]):r for r in g27c["seven_research_site_by_service_source_status"]}
    if len(seen)!=7 or set(seen)!=set(land) or set(seen)!=set(legal):
        raise ValueError("G35_seven_source_site_dossiers_fail_closed")
    # For each same physical location, service time is intrinsic to city/site,
    # NOT different merely because assigned to another study family.
    for xy,rr in seen.items():
        if len({r["mandatory_market"] for r in rr})!=1:raise ValueError("G35_same_xy_city_conflict")
        if len({r["OSRM_2026_city_to_snapped_road_reference_time_min"] for r in rr})!=1:
            raise ValueError("G35_same_original_location_inconsistent_road")
        if len({r["OSRM_destination_study_point_to_nearest_routable_road_m"] for r in rr})!=1:
            raise ValueError("G35_same_original_location_inconsistent_snap")
    return sites,seen,land,legal
def geo_routes(features):
    routes={}
    for f in features:
        id=f["properties"]["id"]
        if id in routes:raise ValueError("G35_repeated_route_id")
        l=LineString([TO_PT.transform(*v) for v in f["geometry"]["coordinates"]])
        if len(l.coords)<8 or l.length<160000:raise ValueError("G35_line_not_geographic_research")
        routes[id]=l
    return routes
def prior_case(site,route,land,legal):
    x,y=xykey(site["original_study_EPSG3763_XY"]);pt=Point(x,y)
    along=route.project(pt)
    ch3=chord_axis(route,along,3000.)
    ch6=chord_axis(route,along,6000.)
    heading=float(site["G24_source_station_straight_heading_deg"])
    mismatch3=axis_bearing_mismatch_deg(ch3,heading)
    mismatch6=axis_bearing_mismatch_deg(ch6,heading)
    offset=route.distance(pt)
    site_legal=legal["source_service_queries"]
    # Observed source layer query status, not legal clearance.
    statuses={key:v["source_coverage_status"] for key,v in site_legal.items()}
    if set(statuses)!={"REN_NORTE","RAN_PT","CRUS_NATIONAL"}:
        raise ValueError("G35_three_official_layer_statuses_missing")
    original_road_valid=bool(site["OSRM_road_reference_snap_both_ends_within_600m_and_route_exists"])
    native=(site["G24_original_DGT2m_station_p90_m"] is not None
            and site["G24_original_DGT2m_approach_p90_m"] is not None)
    # Pure screening only; no title to a station, no constructed rail approach.
    ready=offset<=3000 and native and original_road_valid
    r={"original_G25_source_family":site["source_corridor_family"],
      "source_G24_reference_seed":site["source_G24_reference_seed"],
      "source_G24_screening_role":site["source_G24_screening_role"],
      "mandatory_market":site["mandatory_market"],
      "source_original_site_XY":list((x,y)),
      "original_study_not_station":True,
      "G23B_400m_ground_native_DGT2m_station_p90_m":site["G24_original_DGT2m_station_p90_m"],
      "G23B_1000m_ground_native_DGT2m_approach18permille_p90_m":site["G24_original_DGT2m_approach_p90_m"],
      "G25_OSRM_2026_city_to_road_near_study_site_minutes":site["OSRM_2026_city_to_snapped_road_reference_time_min"] if original_road_valid else None,
      "G25_original_route_proximity_m_not_for_current_route":site["G24_original_grid_distance_m"],
      "G25_road_to_site_snap_m":site["OSRM_destination_study_point_to_nearest_routable_road_m"],
      "road_sample_from_original_G25_not_rerouted":True,
      "source_site_to_current_research_grid_m":round(offset,2),
      "source_site_near_3km_current_grid":offset<=3000.,
      "source_site_near_6km_current_grid":offset<=6000.,
      "source_grid_research_chainage_km":round(along/1000,3),
      "station_straight_to_current_3km_grid_chord_axis_mismatch_deg":round(mismatch3,2),
      "station_straight_to_current_6km_grid_chord_axis_mismatch_deg":round(mismatch6,2),
      "curvature_250_chord_mismatch_is_not_250kmh_station_approval":True,
      "COS2025_400m_artificialized_area_pct":land["cos2025_artificialized_area_percent_2025_observation_NOT_legal_constraint"],
      "COS2025_original_fraction_covered":land["cos2025_original_valid_area_fraction"],
      "G27C_official_DGT_SNIT_wfs_bounded_source_status":statuses,
      "legal_REN_RAN_PDM_SRU_natura_PIC_site_clearance":"UNKNOWN_NOT_LEGALLY_VALIDATED",
      "land_ownership_and_legal_road_entrance":"UNKNOWN",
      "tunnel_approach_station_integration_geometry":"UNENGINEERED",
      "prior_original_source_existing_DGT_road_COS_and_within_3km":ready,
      "not_fully_railway_geometrically_compatible":True}
    for speed,R in RADIUS_BY_SPEED.items():
        r[f"screen_R{speed}_radius_times_3km_chord_angle_m_NOT_connector_length"]=round(
            R*math.radians(mismatch3),2)
    return r
def front(record):
    """Only positive original evidence, no green status for an unbuilt station."""
    good=[q for q in record if q["prior_original_source_existing_DGT_road_COS_and_within_3km"]]
    dims=("source_site_to_current_research_grid_m",
          "station_straight_to_current_3km_grid_chord_axis_mismatch_deg",
          "G23B_400m_ground_native_DGT2m_station_p90_m",
          "G23B_1000m_ground_native_DGT2m_approach18permille_p90_m",
          "G25_OSRM_2026_city_to_road_near_study_site_minutes")
    ready=[q for q in good if all(q[d] is not None for d in dims)]
    return [q for q in ready if not any(y is not q and all(y[d]<=q[d]+1e-7 for d in dims)
                  and any(y[d]<q[d]-1e-7 for d in dims) for y in ready)]
def run(g10,g30geo,g25,g27b,g27c,g32,g33,g34,outjson,outcsv,outmd,outmap,outgeo):
    items=validate(g10,g30geo,g25,g27b,g27c,g32,g33,g34)
    sites,distinct,land,legal=match_source(g25,g27b,g27c)
    routes=geo_routes(items)
    cmp=[];cases=[];feat=[]
    for routeid,line in routes.items():
        for city in MANDATORY:
            candidates=[]
            for rec in sites:
                if rec["mandatory_market"]!=city:continue
                xy=xykey(rec["original_study_EPSG3763_XY"])
                r=prior_case(rec,line,land[xy],legal[xy])
                candidates.append(r)
                cases.append({"corridor":routeid,**r})
            f=front(candidates)
            close=sum(x["source_site_near_3km_current_grid"] for x in candidates)
            physical=sum(x["prior_original_source_existing_DGT_road_COS_and_within_3km"] for x in candidates)
            cum={"option_id":routeid,
              "family":"G30" if routeid.startswith("G30-") else "G10",
              "mandatory_city":city,"original_G23B_G24_G25_terrain_road_site_options_from_older_families":len(candidates),
              "original_unique_DGT2m_site_coordinates":len({tuple(x["source_original_site_XY"]) for x in candidates}),
              "source_reference_variants_within_3km_current_research_route":close,
              "prior_original_ground_and_road_within_3km_context_cases":physical,
              "no_original_terrain_or_road_for_new_station_required_to_score_prior_source":True,
              "prior_only_not_different_rail_station_solutions":True,
              "non_dominated_existing_source_context_probes":len(f),
              "three_provisional_context_probes":sorted(f,key=lambda z:(z["source_site_to_current_research_grid_m"],
                        z["station_straight_to_current_3km_grid_chord_axis_mismatch_deg"]))[:3],
              "no_railway_station_site_or_legal_clearance_proved":True,
              "to_assess_better_3D_approaches_not_new_regional_source_download":True}
            cmp.append(cum)
    if len(cmp)!=60 or len(cases)!=30*len(sites):
        raise ValueError("G35_all30_times_two_cities_and_entire_prior_screen_not_complete")
    # Current XY can have different orientation-level probes, so site locations
    # are printed just once while bearing screen is route-by-route.
    for xy,variants in sorted(distinct.items()):
        city=variants[0]["mandatory_market"]
        lon,lat=TO_WGS.transform(*xy)
        feat.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
           "properties":{"original_DGT2m_reference_site_XY_EPSG3763":list(xy),
             "mandatory_market":city,"original_G25_study_orientation_variants":len(variants),
             "COS2025_original_land_classification_observed":True,
             "G27C_REN_RAN_CRUS_WFS_only_bounded_not_legal_permit":True,
             "not_a_station_or_railway":True}})
    outgeo.write_text(json.dumps({"type":"FeatureCollection",
         "name":"G35 seven previously assessed actual DGT2m 400m land 2025 sites — NOT stations",
         "features":feat},ensure_ascii=False)+"\n")
    coverage_by={c:[z for z in cmp if z["mandatory_city"]==c] for c in MANDATORY}
    data={"mission":"MN-GEO-RAIL-001",
      "stage":"G35_prior_G12toG27_station_site_reuse_and_all30_original_correlation",
      "original_G24_source_examined_study_variants":351,
      "original_G23B_original_DGT2m_local_cases":351,
      "original_G24_G25_OSRM_real_source_shortlist_cases":len(sites),
      "original_DGT2m_COS2025_road_study_coordinate_sites":len(distinct),
      "G27C_original_official_layer_source_queries":7*3,
      "G10_all_routes":27,"G30_all_routes":3,"total_comparable_urban_rail_study_corridors":30,
      "mandatory_city_case_rows":len(cmp),
      "cross_checked_prior_G25_site_family_x_all_current_routes":len(cases),
      "legal_PIC_unknown":True,
      "original_stations_existing_screened_not_approved":True,
      "all_30_urban_grid_city_points_may_share_original_connector_by_design":True,
      "does_not_prove_160_200_250_design_speed_for_station_entry":True,
      "no_fresh_OSRM_or_original_DGT_2m_or_COS_acquisition":True,
      "no_station_rail_times_CBA_freight_passenger_demand":True,
      "source_G34_demography_preserved_not_extrapolated_to_moved_stations":True,
      "no_Fxx_or_site":True,
      "source_7_original_site_ref_coordinates":list(map(list,distinct)),
      "comparisons_all30_times_two_mandatory_cities":cmp,
      "all_historical_source_geometry_context_rows":cases}
    outjson.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    with outcsv.open("w",encoding="utf-8-sig",newline="") as h:
        keys=("option_id","family","mandatory_city",
              "original_G23B_G24_G25_terrain_road_site_options_from_older_families",
              "original_unique_DGT2m_site_coordinates",
              "source_reference_variants_within_3km_current_research_route",
              "prior_original_ground_and_road_within_3km_context_cases",
              "non_dominated_existing_source_context_probes")
        w=csv.DictWriter(h,fieldnames=keys,delimiter=";");w.writeheader()
        w.writerows({key:item[key] for key in keys} for item in cmp)
    # Spatially visible prior source research sites vs all 30 2km lines.
    fig,ax=plt.subplots(figsize=(12,8),layout="constrained")
    for name,route in routes.items():
        xx,yy=route.xy
        ax.plot([v/1000 for v in xx],[v/1000 for v in yy],
            color="#52708a" if name.startswith("P") else "#d07539",
            alpha=.15 if name.startswith("P") else .8,lw=.8 if name.startswith("P") else 1.6,
            zorder=1 if name.startswith("P") else 2)
    for xy,originals in distinct.items():
        city=originals[0]["mandatory_market"]
        ax.scatter(xy[0]/1000,xy[1]/1000,s=32 if city=="Vila_Real" else 45,
            marker="s" if city=="Vila_Real" else "^",edgecolors="white",
            linewidths=.6,c="#172d42",zorder=5)
    ax.set_aspect("equal",adjustable="datalim");ax.grid(alpha=.15)
    ax.set_title("G35 · 7 sítios DGT 2m já estudados (G23–G27) + 27 G10 e 3 G30",loc="left",fontsize=12)
    ax.set_xlabel("E PT-TM06 (km)");ax.set_ylabel("N PT-TM06 (km)")
    ax.legend(handles=[Line2D([0],[0],color="#52708a",label="27 G10 malhas antigas"),
          Line2D([0],[0],color="#d07539",label="3 G30 variantes"),
          Line2D([],[],color="none",marker="s",markerfacecolor="#172d42",label="Vila Real – referências DGT",
                     markersize=7),
          Line2D([],[],color="none",marker="^",markerfacecolor="#172d42",label="Bragança – referências DGT",
                     markersize=7)],fontsize=8)
    fig.savefig(outmap,dpi=165,bbox_inches="tight");plt.close(fig)
    lines=["# G35 — Recuperação e transferência condicionada da implantação de estações anterior",
      "","**Correção metodológica:** As estações não estavam por iniciar. G12–G27 já examinaram 108 sítios exploratórios, 54 referências BGRI/rede, 351 configurações de plataforma e aproximação com **MDT original DGT de 2m**, referências OSRM e COS2025 em sete localizações e fonte DGT REN/RAN/CRUS em 21 consultas limitadas. **Nenhuma estação ou ligação ao corredor foi validada para construção.**",
      "","A presente análise reutiliza integralmente as **sete posições de solo original** e todas as variantes de referência G25 contra a carteira completa **30 corredores (27 G10 + 3 G30)** em Vila Real e Bragança. Mede distância ao eixo de investigação e divergência angular de eixos de corda 3/6 km, sem transformar esta corda em traçado de aproximação.",
      "","## Cobertura da evidência física original, por corredor e nó obrigatório",
      "","| Corredor | VR: ensaios anteriores a ≤3km da grelha | VR: terreno + OSRM original próximos | BR: ensaios anteriores a ≤3km | BR: terreno + OSRM original próximos |",
      "|---|---:|---:|---:|---:|"]
    by={(x["option_id"],x["mandatory_city"]):x for x in cmp}
    for name in routes:
        v=by[name,"Vila_Real"];b=by[name,"Braganca"]
        lines.append(f"| {name} | {v['source_reference_variants_within_3km_current_research_route']} | {v['prior_original_ground_and_road_within_3km_context_cases']} | {b['source_reference_variants_within_3km_current_research_route']} | {b['prior_original_ground_and_road_within_3km_context_cases']} |")
    lines+=["","**Interpretação:** posições de origem G25 repetidas por orientação/família podem contar várias vezes na coluna de ensaios. Os sete pontos físicos são contabilizados separadamente no JSON, não constituem sete localizações de estação projetadas. Não converter estas contagens num índice ponderado de mérito.",
      "","## Avanços já realizados e ainda pendentes",
      "- G23B: 351 casos reais de terreno **local** para deslocamentos ±300m/±250m e rotações ±20°, não 351 estações ou eixos completos.",
      "- G24/G25: orientação e proximidade face a apenas 3 corredores históricos e rede rodoviária medida para a shortlist anterior; G35 faz o cruzamento contra os 30, sem extrapolar velocidades ou custos.",
      "- G26C/G27B: COS2025 e acessos rodoviários para 7 referências. G27C: REN/RAN/CRUS a partir de WFS oficial mas limitado; não certifica planta legal em vigor nem PDM, nem PIC/Natura e qualidade do acesso.",
      "- A população G34 é comparada sob pontos da grelha G10/G30, não sobre estas **posições deslocadas G23B**: não atribuir indevidamente o mesmo catchment a uma localização de estação alternativa.",
      "- Para discriminar verdadeira qualidade de VR e Bragança falta ligar as referências DGT de terreno a corredores de aproximação contínuos, testar posição e rasante ferroviária real, acessos públicos/legalidade, avaliar sítios Natura e eventuais túneis, custo e horários.",
      "","**Decisão para a fase seguinte:** selecionar para cada nó 2–3 sítios historicamente medidos que não estejam dominados no conjunto de fontes físicas e acessos, garantindo representação de tipos de aproximação diferentes. Antes de encomendar novos MDT 2m, verificar se os 84 ficheiros originais cobririam as ligações de engenharia a simular.",
      "","**Não há autorização ferroviária, aprovação ambiental, classificação final de estação nem nova aquisição DGT nesta fase.** PIC continua por definir/cartografar. A carteira G10+G30 mantém 30 alternativas em qualquer relatório de seleção.",
      ""]
    outmd.write_text("\n".join(lines))
    print("G35_RESULT",json.dumps({
      "source_G25_orientation_rows":len(sites),
      "source_original_G27_site_count":len(distinct),
      "all_corridors":len(routes),
      "site_crosswalk_cases":len(cases),
      "pairs":len(cmp),
      "near3_distribution":{city:Counter(z["source_reference_variants_within_3km_current_research_route"]
                           for z in coverage_by[city]) for city in MANDATORY},
      "source_terrain_and_road_evidence_near3_distribution":{city:Counter(z["prior_original_ground_and_road_within_3km_context_cases"]
                           for z in coverage_by[city]) for city in MANDATORY},
      "G30":{r["option_id"]+":"+r["mandatory_city"]:
          {"near3":r["source_reference_variants_within_3km_current_research_route"],
           "native_road":r["prior_original_ground_and_road_within_3km_context_cases"]}
           for r in cmp if r["family"]=="G30"}},default=lambda v:dict(v),ensure_ascii=False))
def main():
    parser=argparse.ArgumentParser()
    for opt in ("g10","g30geo","g25","g27b","g27c","g32","g33","g34","json","csv","markdown","map","geojson"):
        parser.add_argument("--"+opt,required=True,type=Path)
    a=parser.parse_args()
    run(*[file_json(getattr(a,k)) for k in ("g10","g30geo","g25","g27b","g27c","g32","g33","g34")],
        a.json,a.csv,a.markdown,a.map,a.geojson)
if __name__=="__main__":main()
