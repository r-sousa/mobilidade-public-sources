#!/usr/bin/env python3
"""G56 identify whether G30-geographic_diversity original BR3/BR4 200kmh
sampled-horizontal-radius failure was a LIMITED ANCHOR search artifact.

Extend original G45 old G25 angle alternatives by explicitly labelled
±10/20 degree orientation sensitivity (never presume existing land/road legal
access) and station connector west/east 0,3,6,9,12,15km outward contact
shifts, derivative scales 0.55,0.75,0.9,1.1,1.35. Keep EXACT same two
historically measured station physical points and original G30 route.

True original source route grid, source G25 headings & G44 site data; 800m
station study tangent, sampled C2 quintic curvature radius 1.5/2.4/3.7km.
No cant/clothoid, engineered 3D, speed performance, tunnel/cost/Natura/PIC,
access redesign or full corridor proof. Geometry may remain unfitted.
"""
from __future__ import annotations
import argparse,csv,json,math,sys
from pathlib import Path
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g45_shifted_30station_quintic_horizontal import (
   original_path,stations,controls,station_case_geometry,RADIUS,EXT,DERIV_SCALES)
CID="G30-geographic_diversity"
SITE_IDS=("BR3","BR4")
EXTENDED=(0,3000,6000,9000,12000,15000)
NEW_SCALES=(0.55,0.75,0.9,1.1,1.35)
ANGLE_SHIFT=(-20.,-10.,0.,10.,20.)
WGS=Transformer.from_crs(3763,4326,always_xy=True)
def proposals(g30,g25,g44,g45):
    if not g45["all_G10_27_and_G30_3_retained"] or len(g45["all_630_route_site_speed_horizontal_screen_cases"])!=630:
        raise ValueError("G56_old_full30_source_governance")
    if g45["exit_entry_shift_set_m"]!=list(EXT):
        raise ValueError("G56_original_G45_9km_anchor_policy_changed")
    fs=[v for v in g30["features"] if v["properties"]["id"]==CID]
    if len(fs)!=1:raise ValueError("G56_must_use_original_real_G30_geographic_diversity")
    line=original_path(fs[0])
    west,east=controls(line,"Braganca")
    opts=stations(g25,g44)
    if not set(SITE_IDS)<=set(opts):raise ValueError("G56_old_BR3_BR4_source_station_missing")
    old={(r["option_id"],r["historical_site_id"],r["illustrative_speed_label_kmh"]):r
         for r in g45["all_630_route_site_speed_horizontal_screen_cases"]}
    for site in SITE_IDS:
        if old[(CID,site,200)]["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"]:
            raise ValueError("G56_source_old_G45_BR_200_should_have_failed")
    results=[];source_count=0
    for site in SITE_IDS:
        meta=opts[site];basis=meta["angles"]
        sampled_angles=sorted({round((a+offset)%180,4) for a in basis for offset in ANGLE_SHIFT})
        best={speed:None for speed in RADIUS}
        overall=Counter();num_tested=0
        for ew in EXTENDED:
            for ee in EXTENDED:
                for angle in sampled_angles:
                    matches=any(abs(((angle-a+90)%180)-90)<.001 for a in basis)
                    for scale in NEW_SCALES:
                        num_tested+=1
                        q=station_case_geometry(line,meta["xy"],west,east,ew,ee,angle,scale)
                        if not q:continue
                        source_count+=1
                        for speed,rad in RADIUS.items():
                            overall[str(speed)+"_tested_valid_geometry"]+=1
                            if q["min_sampled_radius_m"]+.01<rad:continue
                            overall[str(speed)+"_sampled_horizontal_radius_pass"]+=1
                            if not matches:
                                angle_class="ROTATED_OLD_HEADINGS_NEW_STATION_ACCESS_UNTESTED"
                            else:angle_class="ORIGINAL_G25_STATION_HEADING_REUSED"
                            info={"old_original_station":site,"illustrative_speed_kmh":speed,
                                "old_G45_original_9km_source_missed_R200":speed==200,
                                "source_original_station_XY_PT_TM06":list(meta["xy"]),
                                "source_original_road_access_min":meta["meta"]["G25_original_OSRM_city_to_road_reference_minutes"],
                                "source_original_route_id":CID,
                                "new_search_contact_west_outward_m":q["shift_west_anchor_outward_m"],
                                "new_search_contact_east_outward_m":q["shift_east_anchor_outward_m"],
                                "heading_source_class":angle_class,
                                "heading_applied_deg":round(angle,3),
                                "new_derivative_scale":scale,
                                "source_sampled_2D_radius_m":q["min_sampled_radius_m"],
                                "source_geometry":q,
                                "requires_original_DGT2m_on_new_XY_for_grade_profile":True,
                                "no_current_road_legal_access_or_station_approval_from_rotated_axis":True,
                                "no_250_rail_speed_guarantee_from_sampled_radius":True}
                            rank=(round((ew+ee)/3000,4),
                              0 if matches else 1,
                              q["planimetric_length_excess_over_direct_chord_m"],
                              -q["min_sampled_radius_m"])
                            if best[speed] is None or rank<best[speed][0]:
                                best[speed]=(rank,info)
        result={"station_id":site,"source_original_G25_headings_n":len(basis),
             "new_tested_headings_with_explicit_rotation_n":len(sampled_angles),
             "source_original_station_heading_deg":basis,
             "new_tested_horizontal_start_end_shift_m":list(EXTENDED),
             "new_tested_axis_rotations_relative_to_G25_deg":list(ANGLE_SHIFT),
             "new_tested_quintic_derivative_scales":list(NEW_SCALES),
             "real_station_physical_location_unchanged":True,
             "number_horizontal_trial_parameters":num_tested,
             "nondegenerate_new_geometry_candidate_trial_counts":dict(overall),
             "per_speed":{}}
        for speed in RADIUS:
            b=best[speed]
            result["per_speed"][str(speed)]={"illustrative_speed_kmh":speed,
               "horizontal_2D_curvature_sampled_candidate_found":b is not None,
               "G56_best_source_research_geometry_or_null":b[1] if b else None,
               "G45_original_found":bool(old[(CID,site,speed)]["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"]),
               "not_railway_vertical_ground_vigour_or_clothoid":True}
        results.append(result)
        print("G56_SITE",site,json.dumps({"trials":num_tested,
          "found":{str(speed):best[speed] is not None for speed in RADIUS},
          "passed":dict(overall)},ensure_ascii=False),flush=True)
    return results,source_count
def execute(g30,g25,g44,g45,outjson,outcsv,outgeo,outpng,outmd):
    cases,ngeom=proposals(g30,g25,g44,g45)
    geos=[];rows=[]
    for c in cases:
        for speed,r in c["per_speed"].items():
            v=r["G56_best_source_research_geometry_or_null"]
            rows.append({"original_site":c["station_id"],"speed_screen_kmh":int(speed),
               "G45_old_0_9km_solution_exists":r["G45_original_found"],
               "G56_new_extended_15km_heading_sensitivity_2D_solution_exists":
                   r["horizontal_2D_curvature_sampled_candidate_found"],
               "new_contact_2D_length_m":v["source_geometry"]["total_connected_2D_centerline_length_m"] if v else None,
               "new_sampled_radius_m":v["source_sampled_2D_radius_m"] if v else None,
               "new_horizontal_detour_over_contacts_chord_m":v["source_geometry"]["planimetric_length_excess_over_direct_chord_m"] if v else None,
               "new_station_heading_source_class":v["heading_source_class"] if v else None,
               "shift_west_m":v["new_search_contact_west_outward_m"] if v else None,
               "shift_east_m":v["new_search_contact_east_outward_m"] if v else None})
            if v is not None:
                points=v["source_geometry"]["sampled_QA_path_PT_TM06"]
                geos.append({"type":"Feature","geometry":{"type":"LineString",
                     "coordinates":[list(WGS.transform(*xy)) for xy in points]},
                    "properties":{"site_id":c["station_id"],"speed_screen_kmh":int(speed),
                        "original_G30_source_diversity_line":CID,
                        "sampled_2D_radius_m":v["source_sampled_2D_radius_m"],
                        "source_heading_rotation_needs_road_access_reassessment":v["heading_source_class"]!=
                                      "ORIGINAL_G25_STATION_HEADING_REUSED",
                        "not_railway_3D_or_approved_station":True}})
    out={"mission":"MN-GEO-RAIL-001","stage":"G56_extended_G30_diversity_BR3_BR4_200kmh_curvature_search",
       "original_full30_research_study_alternatives_preserved":True,
       "original_source_G45_all630_curvature_scenarios_untouched":True,
       "original_city_br3_br4_physical_sites_unchanged":True,
       "original_search_0_3_6_9km_and_new_12_15km_contacts_explored":True,
       "new_station_axis_rotations_are_not_original_approved_station_location":True,
       "illustrative_horizontal_radius_speeds_kmh":[160,200,250],
       "new_geometry_candidates_non_degenerate_total":ngeom,
       "two_sites_three_speeds_source_2D_curvature_screen":cases,
       "old_G45_original_BR3_BR4_200_no_sampled_radius_solution":True,
       "any_200kmh_geometry_found_in_this_EXTENDED_RESEARCH":any(c["per_speed"]["200"]
           ["horizontal_2D_curvature_sampled_candidate_found"] for c in cases),
       "no_new_original_DGT2m_source_ground_samples_for_changed_XY":True,
       "no_horizontal_clothoid_cant_transition_rail_standards_approval":True,
       "no_3D_real_track_on_new_G56_geometry_yet":True,
       "no_Natura2000_PIC_freight_rail_timings_CAPEX_legal":True,
       "no_new_DGT_acquisition":True,
       "Fxx_accepted":False,"Site_authorized":False}
    outjson.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    with outcsv.open("w",newline="",encoding="utf-8-sig") as f:
        h=list(rows[0])
        w=csv.DictWriter(f,fieldnames=h,delimiter=";");w.writeheader();w.writerows(rows)
    outgeo.write_text(json.dumps({"type":"FeatureCollection","features":geos},ensure_ascii=False)+"\n")
    fig,ax=plt.subplots(figsize=(10,7),layout="constrained")
    for q in geos:
        p=np.array(q["geometry"]["coordinates"])
        col={"BR3":"#3d7c9a","BR4":"#b46b3f"}[q["properties"]["site_id"]]
        ax.plot(p[:,0],p[:,1],c=col,lw=1.7,alpha=.7,
           label=q["properties"]["site_id"]+" "+str(q["properties"]["speed_screen_kmh"])+"kmh")
    for k,c in enumerate(cases):
        # use real published original old physical site; transform here
        x,y=c["per_speed"]["160"]["G56_best_source_research_geometry_or_null"]["source_original_station_XY_PT_TM06"] if c["per_speed"]["160"]["G56_best_source_research_geometry_or_null"] else (None,None)
        if x is not None:
            wlon,wlat=WGS.transform(x,y)
            ax.scatter(wlon,wlat,marker="o",s=60,ec="white",c=("#3d7c9a" if c["station_id"]=="BR3" else "#b46b3f"))
    ax.set_xlabel("Longitude");ax.set_ylabel("Latitude")
    ax.set_title("G56 · G30 diversidade geográfica, aproximações a BR3/BR4 — raios amostrados, NÃO via desenhada",loc="left")
    ax.grid(alpha=.2)
    if geos:ax.legend(fontsize=8)
    fig.savefig(outpng,dpi=170,bbox_inches="tight");plt.close(fig)
    md=["# G56 — Recuperação de ligações em planta da família G30-diversidade a Bragança",
       "","Em G54, BR3/BR4 nesta família não tinham candidatos de raio mínimo amostrado a 200km/h sob o conjunto antigo de pontos de ligação 0/3/6/9km e orientações de estação de G25. Isso não demonstra impossibilidade ferroviária. O G56 **mantém as coordenadas físicas** dos sítios BR3 e BR4 e o original G30, alarga contactos até ±15km, ensaia inclinação da orientação de plataforma ±10° e ±20° (a validar com acessos/terrenos) e escala de derivadas das curvas de ligação.",
       "","| Sítio | Ensaio de velocidade | Antigo G45 | Pesquisa ampliada G56 | Raio mínimo amostrado (m) |",
       "|---|---:|---|---|---:|"]
    for a in rows:
        md.append(f"| {a['original_site']} | {a['speed_screen_kmh']} km/h | {a['G45_old_0_9km_solution_exists']} | {a['G56_new_extended_15km_heading_sensitivity_2D_solution_exists']} | {a['new_sampled_radius_m']} |")
    md+=["","**A existência de solução de curvatura em planta não garante velocidade real, geometria vertical, comprimento de infraestrutura, intercâmbio com estrada, plataforma, superelevação ou licença.** A rotação de orientação pode alterar o acesso rodoviário e o impacte local, pelo que não deve ser aceite sem recalcular entradas e servidões.",
     "","O passo imediato se houver geometria de 200km/h é **amostrar MDT DGT2m original nas coordenadas desta nova curva**, testando as duas funções de estação e 12,5‰/15‰ em solo nu. Sem amostragem não se deve atribuir 3D a estas novas variantes.",
     "","Os 30 corredores e os outros seis representantes G52 permanecem intactos; estes ensaios são somente de uma família e dois sítios. Não se alterou o inventário DGT nem se autorizaram novas aquisições."]
    outmd.write_text("\n".join(md)+"\n")
    print("G56_RESULT",json.dumps({"source_route":CID,"G56_results":[{"station":c["station_id"],
      "tested":c["number_horizontal_trial_parameters"],
      "per_speed":{s:{"found":q["horizontal_2D_curvature_sampled_candidate_found"],
         "best_new_axis":q["G56_best_source_research_geometry_or_null"]["heading_source_class"]
            if q["G56_best_source_research_geometry_or_null"] else None,
         "Rmin_m":q["G56_best_source_research_geometry_or_null"]["source_sampled_2D_radius_m"]
            if q["G56_best_source_research_geometry_or_null"] else None}
          for s,q in c["per_speed"].items()}} for c in cases],
      "no_original_DGT_new_ground":True},ensure_ascii=False),flush=True)
def main():
    a=argparse.ArgumentParser()
    for k in ("g30","g25","g44","g45","json","csv","geojson","figure","markdown"):
        a.add_argument("--"+k,type=Path,required=True)
    p=a.parse_args()
    execute(*[json.loads(getattr(p,k).read_text()) for k in ("g30","g25","g44","g45")],
        p.json,p.csv,p.geojson,p.figure,p.markdown)
if __name__=="__main__":main()
