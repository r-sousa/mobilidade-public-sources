#!/usr/bin/env python3
"""G53 first inspectable LOCAL sampled 3D ground/grade alternatives in Portugal.

Source EXACT G47 18 authentic DGT2m source raster earlier SHA-verified, 484
real native ground pixel samples at 25m on FOUR prior P2-2-1 G45 preliminary
2D station planimetric approaches. Those 3km centerlines are not railway
EN-standard approved and are not one of the six G52 chosen intercity lines.
Strictly bind X,Y from G47 to G45 old source 2D centerline, and solve 64
mathematical elevation series: 12.5/15 permille, local 10 / 2.5 permille
station operational sensitivity, optimistic vertical radii 10/20km, track
height free vs track height at station center tied to true ground.

Outputs XYZ coordinates in EPSG3763 east/north + original DGT height.
Vertical datum intentionally NOT assigned a combined EPSG; NOT transform to
WGS84 lon/lat/z as that would fake ellipsoidal altitude. No bridges/tunnels,
rail certification, geology, cross-border datum, CAPEX or 3D route elsewhere.
"""
from __future__ import annotations
import argparse,csv,json,math,sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from shapely.geometry import LineString,Point
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g48_real_source_5grade_traffic_station_recalibration import minimax_grade_envelope
from geo_rail_gradient_policy_G48 import classify
SITE_ORDER=("VR2","VR1","BR4","BR3")
GRADES=(12.5,15.)
STATION_CLASS={"PAT_10permille_Spanish_reference":10.,"COUPLING_OR_STABLING_2p5_if_applicable":2.5}
VERTICAL_R=(10000.,20000.)
REGIONAL_SIX_EXPECTED=6
def original_sources(g47,g45,g46,g48,g52):
    if not g47["all_30_G10_27_G30_3_retained"] or len(g47["real_4x121_25m_sample_original_native_DGT2m_pixel_rows"])!=484:
        raise ValueError("G53_requires_true_original_DGT2m_484")
    if g47["reused_existing_original_DGT_2m_GitHub_public_tile_assets_count"]!=18 or not g47["all_invalid_pixels_kept_missing_not_imputed"]:
        raise ValueError("G53_18_true_original_DGT2m_rasters_and_NoData_QA")
    if not g45["all_G10_27_and_G30_3_retained"] or len(g45["all_630_route_site_speed_horizontal_screen_cases"])!=630:
        raise ValueError("G53_old_G45_P2_2_1_station_2D")
    if not g46["full30_options_still_studied"] or g46["old_verified_DGT_original_1km_tile_manifest"]!=84:
        raise ValueError("G53_original_84_source_tile_inventory")
    if g48["primary_mixed_line_screens_permille"]!=[12.5,15] or not g48["G47_original_DGT2m_4x121_source_points_verified"]:
        raise ValueError("G53_original_G48_mixed_gradient_recalibration")
    if not g52["source_original_all30_preserved"] or len(g52["G52_six_representative_original_source_routes_for_NEXT_ground_3D"])!=REGIONAL_SIX_EXPECTED:
        raise ValueError("G53_G52_research_six_canonical")
    if g52["source_27_G10_3_G30_count"]!=30 or not g52["geology_hydro_Natura2000_PIC_NOT_CLEARED"]:
        raise ValueError("G53_must_not_claim_6_railway_3D")
    by=defaultdict(list)
    for p in g47["real_4x121_25m_sample_original_native_DGT2m_pixel_rows"]:
        by[p["site_id"]].append(p)
    oldsites={s["candidate_site_id"]:s for s in g45["site_source_original_road_COS_DGT2m_from_G44"]}
    oldgeom={(r["option_id"],r["historical_site_id"],r["illustrative_speed_label_kmh"]):r
        for r in g45["all_630_route_site_speed_horizontal_screen_cases"]}
    if set(by)!=set(SITE_ORDER) or len(oldgeom)!=630:raise ValueError("G53_canonical_4_original_stations")
    stations=[]
    for site in SITE_ORDER:
        sample=sorted(by[site],key=lambda p:p["source_station_chainage_relative_m"])
        if len(sample)!=121 or any(s["source_status"]!="VALID_ORIGINAL_DGT_2M_GROUND_PIXEL" or
          not s["original_file_SHA256"] or s["original_DGT_2m_ground_elevation_m"] is None for s in sample):
            raise ValueError("G53_DGT_original_source_pixel_invalid_"+site)
        x=np.array([s["source_station_chainage_relative_m"] for s in sample],float)
        xy=np.array([s["sample_XY_EPSG3763_m"] for s in sample],float)
        g=np.array([s["original_DGT_2m_ground_elevation_m"] for s in sample],float)
        if not np.allclose(np.diff(x),25) or not np.allclose(np.linalg.norm(np.diff(xy,axis=0),axis=1),25,atol=1):
            raise ValueError("G53_source_horizontal_25m_chainage_invalid")
        prev=oldgeom[("P2-2-1",site,200)]
        if not prev["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"]:
            raise ValueError("G53_original_reference_P2_2_1_200_not_found")
        line=LineString(prev["best_research_horizontal_solution"]["sampled_QA_path_PT_TM06"])
        loc=Point(oldsites[site]["previous_source_original_XY_EPSG3763"])
        if line.distance(loc)>5.:raise ValueError("G53_station_does_not_lie_on_source_G45_straight")
        center=line.project(loc)
        for i,row in enumerate(xy):
            target=line.interpolate(center-1500+i*25)
            if target.distance(Point(row))>1.0:
                raise ValueError("G53_G47_true_XY_drift_from_G45_planimetric_"+site)
        if abs(x[60])>1e-5:raise ValueError("G53_original_study_station_center_not_zero")
        stations.append({"site":site,"city":oldsites[site]["mandatory_city"],
            "x":x,"xy":xy,"ground":g,"old_road_minutes":oldsites[site]["G25_original_OSRM_city_to_road_reference_minutes"]})
    return stations
def solve_center_tied(x,ground,grade,station_permille,vertical_R,anchor_center=True):
    """Separate strict LP only for station center fixed at measured ground;
    endpoints are free. Shared G48 LP produces the FREE station case.
    """
    n=len(x)
    if n!=121 or len(ground)!=n or not np.allclose(np.diff(x),25):
        raise ValueError("G53_source_profile_bad")
    dx=float(x[1]-x[0])
    i0=n//2
    nr=[];nc=[];vv=[];rhs=[]
    def add(items,b):
        r=len(rhs)
        for col,val in items:
            nr.append(r);nc.append(col);vv.append(float(val))
        rhs.append(float(b))
    for i,h in enumerate(ground):
        add(((i,1),(n,-1)),h)
        add(((i,-1),(n,-1)),-h)
    for i in range(n-1):
        cap=min(grade,station_permille) if abs((x[i]+x[i+1])/2)<=400 else grade
        for sign in (1,-1):add(((i,sign),(i+1,-sign)),cap/1000*dx)
    for i in range(1,n-1):
        for sign in (1,-1):
            add(((i-1,sign),(i,-2*sign),(i+1,sign)),dx*dx/vertical_R)
    A=coo_matrix((vv,(nr,nc)),shape=(len(rhs),n+1)).tocsr()
    bounds=[(None,None)]*n+[(0,None)]
    if anchor_center:bounds[i0]=(float(ground[i0]),float(ground[i0]))
    c=np.zeros(n+1);c[-1]=1
    sol=linprog(c,A_ub=A,b_ub=np.asarray(rhs),bounds=bounds,method="highs")
    if not sol.success:
        raise ValueError("G53_linerail_station_center_tied_calculation_failed_"+str(sol.message)[:100])
    z=sol.x[:-1]
    if max(abs(np.diff(z)/dx)*1000)>grade+.0001 or (anchor_center and abs(z[i0]-ground[i0])>.001):
        raise ValueError("G53_station_center_or_grade_constraints_mismatch")
    if max(abs(np.diff(z,n=2)))*vertical_R/(dx*dx)>1.0001:
        raise ValueError("G53_vertical_curve_bound_error")
    return z,round(float(sol.x[-1]),3)
def cases(g47,g45,g46,g48,g52):
    stations=original_sources(g47,g45,g46,g48,g52)
    rows=[];profiles=[];wkt=[];comparison=[]
    for s in stations:
        sid=s["site"];xx=s["x"];xy=s["xy"];ground=s["ground"]
        for grade in GRADES:
            for label,cap in STATION_CLASS.items():
                for radius in VERTICAL_R:
                    ref=minimax_grade_envelope(xx,ground,grade,
                      station_max_permille=cap,vertical_radius_m=radius,fixed_endpoints=False)
                    if ref["status"]!="OPTIMISTIC_LP_MATHEMATICAL_GRADE_ENVELOPE_NOT_PROJECT":
                        raise ValueError("G53_source_G48_free_vertical_profile_unexpected_status")
                    for tied in (False,True):
                        # Fit directly at full numerical precision: the public
                        # G48 profiles round Z to millimetres, which can
                        # generate false exact 2nd-difference curvature breaches.
                        z,hi=solve_center_tied(xx,ground,grade,cap,radius,anchor_center=tied)
                        if not tied and abs(hi-ref["minimum_maximum_vertical_ground_separation_m"])>.02:
                            raise ValueError("G53_free_case_changed_from_verified_G48_LP")
                        if hi is None:raise ValueError("G53_null_altimetry_imputation_prohibited")
                        gs=np.abs(np.diff(z)/25)*1000
                        caploc=np.array([min(grade,cap) if abs((xx[i]+xx[i+1])/2)<=400 else grade for i in range(120)])
                        if np.any(gs>caploc+.0001):
                            raise ValueError("G53_original_3D_horizontal_grade_audit")
                        if float(max(abs(np.diff(z,n=2))))*radius/(25**2)>1.001:
                            raise ValueError("G53_local_3D_vertical_curve_audit")
                        difference=z-ground
                        modelid=f"{sid}_G{grade:g}_S{cap:g}_Rv{int(radius)}_{'CENTER_TIED' if tied else 'FREE'}"
                        record={"case_id":modelid,"old_original_physical_station":sid,
                          "mandatory_city":s["city"],"original_line_study":"P2-2-1",
                          "original_G45_speed_scope_kmh_planar_radius_illustrative":200,
                          "mainline_research_max_grade_permille":grade,
                          "station_operational_case":label,
                          "station_800m_grade_cap_permille":cap,
                          "hypothetical_nonnormative_vertical_radius_m":radius,
                          "station_centre_at_real_ground_elevation":tied,
                          "source_original_station_ground_center_m":round(float(ground[60]),3),
                          "research_math_3D_track_center_z_original_DGT_height_m":round(float(z[60]),3),
                          "source_ground_minmax_m":[round(float(ground.min()),3),round(float(ground.max()),3)],
                          "math_minimax_max_vertical_offset_at_121_ground_points_m":hi,
                          "actual_max_horizontal_route_gradient_permille":round(float(gs.max()),4),
                          "absolute_vertical_offset_median_across_121_ground_points_m":round(float(np.median(abs(difference))),3),
                          "fraction_sample_points_abs_alt_difference_above_25m_NOT_STRUCTURE_LENGTH":round(float(np.mean(abs(difference)>25)),4),
                          "sample_ground_25m_count":121,
                          "3D_crs_horizontal":"EPSG:3763",
                          "vertical_height_reference":"NATIVE_DGT_ORIGINAL_HEIGHT_UNHARMONIZED_EPSG_VERTICAL_NOT_ASSIGNED",
                          "not_design_rail_grade_straight_clothoid_or_cant":True,
                          "no_tunnel_viaduct_earthwork_volume_or_EUR_CAPEX_inferred":True}
                        rows.append(record)
                        if (label=="PAT_10permille_Spanish_reference" and radius==20000 and grade in (12.5,15)
                              and tied):
                            # WKT stays native projected east,north,DGT original
                            # source height, with explicit unharmonized vertical
                            # metadata. DO NOT silently transform to WGS84 z.
                            coords=[[round(float(x),2),round(float(y),2),round(float(zz),3)]
                                for (x,y),zz in zip(xy,z)]
                            wkt.append({"case_id":modelid,"horizontal_CRS":"EPSG:3763",
                                "height":"ORIGINAL_DGT_HEIGHT_UNHARMONIZED",
                                "LINESTRING_Z_wkt":"LINESTRING Z ("+
                                ", ".join(f"{q[0]} {q[1]} {q[2]}" for q in coords)+")"})
                            profiles.append({"case_id":modelid,"site_id":sid,
                               "sample_121_source_original_DGT2m_XYZ_ground_track":[
                                {"study_chainage_from_station_m":float(x_m),
                                 "east_EPSG3763_m":xyz[0],"north_EPSG3763_m":xyz[1],
                                 "source_original_DGT_ground_Z_m":round(float(h),3),
                                 "research_math_track_Z_m":xyz[2],
                                 "vertical_difference_track_minus_ground_m":round(float(xyz[2]-h),3),
                                 "not_project_railway":True}
                                   for x_m,xyz,h in zip(xx,coords,ground)]})
        # Cases all found or fail closed, no missing.
        if len([r for r in rows if r["old_original_physical_station"]==sid])!=16:
            raise ValueError("G53_missing_4grade_operational_radius_anchor_station_cases")
    if len(rows)!=64 or len(profiles)!=8 or len(wkt)!=8:
        raise ValueError("G53_incomplete_64_case_8_xyz_3D")
    # G52 research 6 representative intercity options (not P2-2-1),
    # G46 original DGT coverage for each of their 4 old station sites, 200kmh.
    short=g52["G52_six_representative_original_source_routes_for_NEXT_ground_3D"]
    match={}
    for r in g46["all30_station_study_radius_source_cases_and_buffer_gaps"]:
        if (r.get("option_id") in short and r.get("site_id") in SITE_ORDER and
           r.get("speed_label_kmh")==200 and
           (r.get("candidate_local_domain")=="local_1p5km" or
            r.get("source_G45_geometric_candidate_exists") is False)):
            key=(r["option_id"],r["site_id"])
            if key in match:raise ValueError("G53_duplicate_source_24_tile_study")
            match[key]=r
    if len(match)!=24:raise ValueError("G53_6families_x_4source_old_station_screens_not_available")
    for opt in short:
        for sid in SITE_ORDER:
            k=(opt,sid);r=match[k]
            comparison.append({"source_geographic_3D_followup_family":opt,
                 "original_city_station_pilot":sid,
                 "source_2D_radius_candidate_at_200_exists":r["source_G45_geometric_candidate_exists"],
                 "conditionally_required_original_DGT2m_1km_tiles_for_center3km":r.get("required_1km_original_DGT_tile_count_conditional"),
                 "original_DGT84_manifest_tiles_already_present":r.get("already_in_84_original_DGT_tile_manifest"),
                 "original_DGT2m_additional_1km_tiles_if_this_family_selected":r.get("missing_tile_count_IF_this_2D_buffer_study_adopted"),
                 "this_geographic_family_has_not_yet_been_sampled_with_native_DGT2m_3D":True,
                 "not_railway_buildability_or_acquisition_authorisation":True})
    return rows,profiles,wkt,comparison
def write(g47,g45,g46,g48,g52,jout,csvout,wktout,figout,mdout):
    rows,profiles,wkt,comparison=cases(g47,g45,g46,g48,g52)
    output={"mission":"MN-GEO-RAIL-001","stage":"G53_first_original_PT_DGT2m_XYZ_3km_station_vertical_spline_research",
      "G52_original_all30_research_routes_preserved":True,
      "G52_six_representative_geographical_route_families_preserved":g52["G52_six_representative_original_source_routes_for_NEXT_ground_3D"],
      "G53_actual_original_DGT2m_4x121_ground_pixels_at_25m_source_G47":484,
      "G53_source_original_18_DGT2m_tiles_reused_no_reacquisition":True,
      "G53_XYZ_modelled_station_3km_source_horizontal_reference":"G45_P2-2-1_200kmh_research_2D",
      "G53_64_station_and_mainline_grade_vertical_radius_anchor_scenarios":rows,
      "G53_8_inspectable_121point_native_ground_plus_3D_grade_samples":profiles,
      "G53_native_EPSG3763_projected_XYZ_WKT_lines_height_DATUM_NOT_HARMONIZED":wkt,
      "G52_six_geographical_representatives_x_4_station_source_DGT84_data_coverage_screen":comparison,
      "sampled_DGT2m_ground_is_real_modelled_track_z_math_only":True,
      "operational_station_10_and_2p5_permille_separate_conditional_tests":True,
      "mainline_mixed_only_12p5_and_15_permille":True,
      "sensitivity_vertical_curve_radius_10km_and20km_not_normative_certification":True,
      "center_ground_tie_is_artificial_study_condition_not_actual_station_elevation":True,
      "no_full_railway_3D_corridor_geotechnical_alignment_or_horizontal_rail_clothoids":True,
      "cannot_extrapolate_P221_old_station_XY_ground_to_six_selected_G52_families":True,
      "no_train_times_CAPEX_tunnel_bridge_quantities_freight_rolling_stock_verified":True,
      "no_geology_hydro_Natura2000_PIC_legal_clearance":True,
      "no_new_DGT_or_IGN_original_downloads":True,
      "Fxx_accepted":False,"Site_authorized":False}
    jout.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n")
    fields=("case_id","old_original_physical_station","mainline_research_max_grade_permille",
        "station_800m_grade_cap_permille","hypothetical_nonnormative_vertical_radius_m",
        "station_centre_at_real_ground_elevation",
        "math_minimax_max_vertical_offset_at_121_ground_points_m",
        "research_math_3D_track_center_z_original_DGT_height_m",
        "absolute_vertical_offset_median_across_121_ground_points_m",
        "actual_max_horizontal_route_gradient_permille")
    with csvout.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";");w.writeheader()
        for r in rows:w.writerow({k:r.get(k) for k in fields})
    wktout.write_text("# EPSG:3763 east/north; Z native DGT source height (vertical datum unharmonized)\n"+
       "# Preliminary mathematical grade lines over G45 2D research paths, NOT engineering project\n"+
       "\n".join(q["case_id"]+"|"+q["LINESTRING_Z_wkt"] for q in wkt)+"\n")
    fig,axarr=plt.subplots(2,2,figsize=(12,8),layout="constrained")
    for ax,sid in zip(axarr.flat,SITE_ORDER):
        prof=next(v for v in profiles if v["site_id"]==sid and "_G12.5_" in v["case_id"])
        pts=prof["sample_121_source_original_DGT2m_XYZ_ground_track"]
        ax.plot([p["study_chainage_from_station_m"]/1000 for p in pts],
          [p["source_original_DGT_ground_Z_m"] for p in pts],color="#385f79",lw=1.6,
          label="Solo nu observado DGT2m")
        for grade,colour in ((12.5,"#bd703b"),(15,"#629566")):
            q=next(p for p in profiles if p["site_id"]==sid and "_G"+str(grade if grade!=15 else 15)+"_" in p["case_id"])
            ax.plot([p["study_chainage_from_station_m"]/1000 for p in q["sample_121_source_original_DGT2m_XYZ_ground_track"]],
              [p["research_math_track_Z_m"] for p in q["sample_121_source_original_DGT2m_XYZ_ground_track"]],
              color=colour,lw=1.2,ls="--",label=f"Modelo misto {grade:g}‰ PAT10 Rv20km")
        ax.axvspan(-.4,.4,color="#c1c4c5",alpha=.15)
        ax.set_title(sid+" · 3km, altura da estação centrada na cota do solo (hipótese)",loc="left",fontsize=9)
        ax.set_xlabel("km relativos ao centro da estação");ax.set_ylabel("Cota DGT original (m)")
        ax.grid(alpha=.15);ax.legend(fontsize=7)
    fig.suptitle("G53 · Quatro primeiras LINHAS XYZ de investigação — terreno original vs rasante matemática 3D",fontsize=11)
    fig.savefig(figout,dpi=170,bbox_inches="tight");plt.close(fig)
    md=["# G53 — Primeiros eixos XYZ locais, com MDT de solo nu original DGT de 2m",
      "","Estes são os **primeiros segmentos locais de eixo tridimensional matemático** do estudo. Em cada uma das quatro aproximações de 3km, os pares X,Y são os mesmos amostrados no G47 a cada 25m sobre a geometria horizontal G45 de investigação P2-2-1 a 200km/h. As cotas do terreno são observações **originais DGT2m** (484 pontos, de 18 GeoTIFF já recolhidos); a cota do eixo é otimizada matematicamente e não corresponde a obra desenhada.",
      "","Foram executados **64 ensaios**: rampa de via geral 12,5‰ ou 15‰, reta hipotética de estação 800m com limite local 10‰ (referência PAT) ou 2,5‰ (somente onde aplicável a engate/estacionamento), condição de curvatura vertical não normativa Rv=10/20km e altura da estação livre ou igual à cota observada no centro da estação.",
      "","## Comparação de linha mista 12,5‰/15‰, PAT10, Rv 20km",
      "","| Sítio | Máx. afastamento vertical matemático, altura da estação livre (m) 12,5 / 15‰ | Estação centrada na cota do terreno: máx. afastamento (m) 12,5 / 15‰ |",
      "|---|---|---|"]
    for sid in SITE_ORDER:
        def getval(grade,tied):
            return next(r["math_minimax_max_vertical_offset_at_121_ground_points_m"]
              for r in rows if r["old_original_physical_station"]==sid
               and r["mainline_research_max_grade_permille"]==grade
               and r["station_800m_grade_cap_permille"]==10
               and r["hypothetical_nonnormative_vertical_radius_m"]==20000
               and r["station_centre_at_real_ground_elevation"]==tied)
        md.append(f"| {sid} | {getval(12.5,False)} / {getval(15.,False)} | {getval(12.5,True)} / {getval(15.,True)} |")
    md+=["","**Os afastamentos são limites matemáticos sobre esta geometria horizontal fixa, NÃO profundidades de túnel ou alturas de viaduto**. Não se dimensionaram curvas horizontais ferroviárias, superelevação, estação realmente horizontal, fundações, escoamento, estruturas ou terreno fora dos 3km.",
      "","## Exportação da geometria",
      "Os resultados incluem 8 casos de eixo \`LINESTRING Z\` WKT com coordenadas E,N em **EPSG:3763** e Z referida às alturas originais DGT. **O datum vertical permanece por harmonizar**: não se converteu artificialmente a altitude em coordenada elipsoidal WGS84 GeoJSON. O conjunto completo dos 64 ensaios está em JSON/CSV com os valores e auditorias.",
      "","## Relação com seis famílias selecionadas pelo G52",
      "Os 3km originais DGT2m foram medidos para o antigo corredor de referência **P2-2-1**, que **não é uma das seis famílias representativas G52**. Logo não se podem transplantar as suas cotas para os outros eixos. Para as seis famílias foi cruzada a cobertura de dados DGT2m no entorno dos quatro locais de estação a 200 km/h, identificando onde poderemos reutilizar os raster originais para novas extrações reais em vez de adquirir dados.",
      "","## Próximos portões de engenharia",
      "1. Verificar e amostrar as geometrias horizontais escolhidas para cada família G52 junto às quatro estações, nos locais já cobertos por quadrículas DGT2m originais; não replicar artificialmente o perfil P2-2-1.",
      "2. Tratar Marão–Alvão e o setor transmontano como geometrias 3D **ainda sem terreno de solo nu contínuo**, para planear MDT adicional apenas na faixa de projeto, a partir da shortlist G52 e da base G46.",
      "3. Testar condições de exploração de mercadorias a 12,5/15‰ com perfis completos, velocidade comercial por troço e comprimento do comboio, sem usar 25‰ como hipótese mista.",
      "4. Antes de custos de túneis, investigar geologia e hidrogeologia reais, portais e impactos Natura 2000/PIC, mantendo todos os 30 corredores no acervo.",
      "","**Não estão validados traçados ferroviários contínuos em 3D Porto–Zamora. Estes 3km são eixos XYZ matemáticos com solo nu verdadeiro, não alinhamentos de execução. Sem Fxx/Site.**"]
    mdout.write_text("\n".join(md)+"\n")
    print("G53_RESULT",json.dumps({"n_models":len(rows),
        "modelled_4site":{site:[{k:r[k] for k in ("mainline_research_max_grade_permille","station_centre_at_real_ground_elevation",
                  "math_minimax_max_vertical_offset_at_121_ground_points_m")}
           for r in rows if r["old_original_physical_station"]==site and r["station_800m_grade_cap_permille"]==10 and
            r["hypothetical_nonnormative_vertical_radius_m"]==20000] for site in SITE_ORDER},
        "source_4site_6family_G46_checked":len(comparison),
        "families_3km_original_DGT_source_tiles_missing":[x for x in comparison if
                isinstance(x["original_DGT2m_additional_1km_tiles_if_this_family_selected"],int) and
                x["original_DGT2m_additional_1km_tiles_if_this_family_selected"]>0][:6],
        "source_true_ground":484,"no_reacquisition":True},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    for k in ("g47","g45","g46","g48","g52","json","csv","wkt","figure","markdown"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args()
    write(*[json.loads(getattr(a,k).read_text()) for k in ("g47","g45","g46","g48","g52")],
      a.json,a.csv,a.wkt,a.figure,a.markdown)
if __name__=="__main__":main()
