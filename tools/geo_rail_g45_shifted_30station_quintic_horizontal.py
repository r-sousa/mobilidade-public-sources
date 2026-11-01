#!/usr/bin/env python3
"""G45 first real geometric *continuous planar* research connectors to seven
previously investigated station locations, with shifted intercity contact.
27 G10 + 3 G30 ORIGINAL 2km research routes; original G25 29 orientation
cases and G44 seven DGT2m physical sites/road/land constraints.

Quintic position+heading C2 connectors with zero endpoint accelerations, an
explicit 800m station straight, flexible contact at 0/3/6/9km beyond the
old anchors, and dense analytic curvature checks for 160/200/250 radius
screening. Does NOT certify EN standards: no transition-curve cant, lateral
jerk, braking, 3D ground, vertical station grades, water/portal, cost/EIA.
"""
import argparse,csv,json,math,sys,hashlib
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from shapely.geometry import LineString,Point
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g44_seven_original_station_sites_horizontal_chords import CITY_BOUNDS,RADIUS,site_key
TO_PT=Transformer.from_crs(4326,3763,always_xy=True)
TO_WGS=Transformer.from_crs(3763,4326,always_xy=True)
EXT=(0,3000,6000,9000)
STATION_LENGTH=800.
DERIV_SCALES=(.75,1.1)
TVAL=np.linspace(0,1,101)
def quintic(p0,p1,tan0,tan1,scale=0.9,t=TVAL):
    p0=np.asarray(p0,float);p1=np.asarray(p1,float)
    L=np.linalg.norm(p1-p0)
    if L<300:raise ValueError("G45_very_short_connector")
    d0=np.asarray(tan0,float)*L*scale
    d1=np.asarray(tan1,float)*L*scale
    a0=p0;a1=d0;a2=np.zeros(2)
    a3=10*(p1-p0)-6*d0-4*d1
    a4=-15*(p1-p0)+8*d0+7*d1
    a5=6*(p1-p0)-3*d0-3*d1
    tt=t[:,None]
    q=a0+tt*(a1+tt*(a2+tt*(a3+tt*(a4+tt*a5))))
    dq=a1+tt*(2*a2+tt*(3*a3+tt*(4*a4+tt*5*a5)))
    d2q=2*a2+tt*(6*a3+tt*(12*a4+tt*20*a5))
    vnorm=np.linalg.norm(dq,axis=1)
    if min(vnorm)<20:return None
    kappa=np.abs(dq[:,0]*d2q[:,1]-dq[:,1]*d2q[:,0])/np.maximum(vnorm**3,1)
    length=float(np.sum(np.linalg.norm(np.diff(q,axis=0),axis=1)))
    return q,float(np.max(kappa)),length
def unit(v):
    a=np.asarray(v,float);n=np.linalg.norm(a)
    if n<1:raise ValueError("G45_source_2km_route_heading_unresolved")
    return a/n
def oriented_station_heading(axis_deg,entry,exit):
    ang=math.radians(axis_deg%180)
    u=np.array([math.cos(ang),math.sin(ang)])
    if np.dot(u,np.asarray(exit)-np.asarray(entry))<0:u=-u
    return u
def original_path(feature):
    coords=[TO_PT.transform(*p) for p in feature["geometry"]["coordinates"]]
    return LineString(coords)
def stations(g25,g44):
    raw=g25["source_shortlisted_road_reference_route_cases"]
    old=g44["original_seven_previous_physical_DGT2m_station_study_refs"]
    if len(raw)!=29 or len(old)!=7:raise ValueError("G45_original_seven_29_source_must_exist")
    grouped=defaultdict(list)
    for r in raw:
        loc=site_key(r["original_study_EPSG3763_XY"])
        angle=r["G24_source_station_straight_heading_deg"]
        if not(0<=angle<360):raise ValueError("G45_invalid_original_heading")
        grouped[loc].append(float(angle)%180.)
    if set(grouped)!={site_key(v["previous_source_original_XY_EPSG3763"]) for v in old}:
        raise ValueError("G45_G25_G44_seven_sites_are_not_same")
    result={}
    for site in old:
        id=site["candidate_site_id"];loc=site_key(site["previous_source_original_XY_EPSG3763"])
        angles=sorted(set(round(a,6) for a in grouped[loc]))
        if not angles:raise ValueError("G45_site_orientation_missing")
        result[id]={"meta":site,"xy":loc,"angles":angles}
    if sum(len(grouped[loc]) for loc in grouped)!=29:raise ValueError("G45_old29_not_reused")
    return result
def controls(route,city):
    geom=CITY_BOUNDS[city]
    cc=list(route.coords)
    def closest(target):
        d=[math.dist(c,target) for c in cc]
        j=int(np.argmin(d))
        if d[j]>30:raise ValueError("G45_missing_original_common_station_grid_anchor")
        return route.project(Point(cc[j]))
    west=closest(geom["west"]);east=closest(geom["east"])
    if east-west<3000:raise ValueError("G45_west_east_not_ordered")
    return west,east
def station_case_geometry(route,site,west,east,ew,ee,axis,scale):
    sw=max(1500,west-ew)
    se=min(route.length-1500,east+ee)
    if se-sw<6000:return None
    # Source anchor reference tangent from 3km chord NOT certified curve
    w=route.interpolate(sw);e=route.interpolate(se)
    w0=route.interpolate(max(0,sw-1500));w1=route.interpolate(min(route.length,sw+1500))
    e0=route.interpolate(max(0,se-1500));e1=route.interpolate(min(route.length,se+1500))
    wxy=np.array([w.x,w.y]);exy=np.array([e.x,e.y])
    wu=unit([w1.x-w0.x,w1.y-w0.y])
    eu=unit([e1.x-e0.x,e1.y-e0.y])
    stxy=np.asarray(site,float)
    su=oriented_station_heading(axis,wxy,exy)
    station_start=stxy-su*(STATION_LENGTH/2)
    station_end=stxy+su*(STATION_LENGTH/2)
    if np.dot(station_start-wxy,su)<-5000 or np.dot(exy-station_end,su)<-5000:return None
    a=quintic(wxy,station_start,wu,su,scale=scale)
    b=quintic(station_end,exy,su,eu,scale=scale)
    if a is None or b is None:return None
    kmax=max(a[1],b[1])
    if kmax<=0:rad=1e10
    else:rad=1/kmax
    linecoords=np.vstack((a[0],station_end[None,:],b[0][1:]))
    path=LineString(linecoords)
    if not path.is_simple:return None
    # Ensure a continuous explicit straight station tangent; source route
    # endpoints may still be discontinuous with actual intercity 2km grid.
    gross_length=a[2]+STATION_LENGTH+b[2]
    direct=float(np.linalg.norm(exy-wxy))
    if gross_length>1.75*direct:return None
    return {"min_sampled_radius_m":round(rad,1),
      "max_sampled_curvature_per_m":round(kmax,8),
      "approach_west_chainage_research_km":round(sw/1000,3),
      "approach_east_chainage_research_km":round(se/1000,3),
      "shift_west_anchor_outward_m":round(west-sw,1),
      "shift_east_anchor_outward_m":round(se-east,1),
      "station_straight_research_m":STATION_LENGTH,
      "total_connected_2D_centerline_length_m":round(gross_length,1),
      "between_contact_points_chord_m":round(direct,1),
      "planimetric_length_excess_over_direct_chord_m":round(gross_length-direct,1),
      "original_station_platform_heading_axis_deg":round(axis%180,3),
      "quintic_station_connector_derivative_scale":scale,
      "source_entry_point_PT_TM06":[round(float(z),2) for z in wxy],
      "source_exit_point_PT_TM06":[round(float(z),2) for z in exy],
      "source_straight_station_start_PT_TM06":[round(float(z),2) for z in station_start],
      "source_straight_station_end_PT_TM06":[round(float(z),2) for z in station_end],
      "sampled_QA_path_PT_TM06":[[round(float(z),2) for z in point] for point in linecoords[::4]]}
def evaluate(g10,g30,g25,g44,g42):
    if len(g10["features"])!=27 or len(g30["features"])!=3 or not g42["original_G10_27_G30_3_preserved"]:
        raise ValueError("G45_30_original_routes_missing")
    opts=stations(g25,g44)
    features=g10["features"]+g30["features"]
    ids=[f["properties"]["id"] for f in features]
    if len(set(ids))!=30:raise ValueError("G45_not_unique_30")
    cases=[];route_data={};total=0;passed=0
    cache={}
    for f in features:
        id=f["properties"]["id"]
        route=original_path(f)
        for city in CITY_BOUNDS:
            west,east=controls(route,city)
            route_data[(id,city)]={"west":west,"east":east,"length":round(route.length,1)}
            for sid,entry in opts.items():
                if entry["meta"]["mandatory_city"]!=city:continue
                site=entry["xy"]
                best={speed:None for speed in RADIUS}
                attempts={speed:0 for speed in RADIUS}
                passedcnt={speed:0 for speed in RADIUS}
                for ew in EXT:
                    for ee in EXT:
                        for orientation in entry["angles"]:
                            for scale in DERIV_SCALES:
                                total+=1
                                key=(city,tuple(round(q,1) for q in route.interpolate(max(1500,west-ew)).coords[0]),
                                  tuple(round(q,1) for q in route.interpolate(min(route.length-1500,east+ee)).coords[0]),
                                  tuple(round(q,1) for q in site),orientation,scale,
                                  tuple(round(q,4) for q in (west,east)))
                                # Omit global caching due source-grid endpoint tangent
                                # uncertainty; verify all 30 on their own approach.
                                q=station_case_geometry(route,site,west,east,ew,ee,orientation,scale)
                                if q is None:continue
                                for speed,rad in RADIUS.items():
                                    attempts[speed]+=1
                                    if q["min_sampled_radius_m"]<rad:continue
                                    passedcnt[speed]+=1
                                    # Prefer smallest shifted domain, followed by
                                    # shorter curved centerline and radius margin.
                                    rank=(ew+ee,q["planimetric_length_excess_over_direct_chord_m"],
                                          -q["min_sampled_radius_m"])
                                    if best[speed] is None or rank<best[speed][0]:
                                        best[speed]=(rank,q)
                for speed in RADIUS:
                    ok=best[speed] is not None
                    if ok:passed+=1
                    cases.append({"option_id":id,"source_family":"G30" if id.startswith("G30") else "G10",
                      "mandatory_city":city,"historical_site_id":sid,
                      "source_existing_original_road_minutes":entry["meta"]["G25_original_OSRM_city_to_road_reference_minutes"],
                      "historical_G25_original_heading_options":len(entry["angles"]),
                      "illustrative_speed_label_kmh":speed,"illustrative_horizontal_min_radius_m":rad if (rad:=RADIUS[speed]) else None,
                      "C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found":ok,
                      "screened_candidate_2D_geometries":attempts[speed],
                      "geometries_passing_sampled_horizontal_radius":passedcnt[speed],
                      "best_research_horizontal_solution":best[speed][1] if ok else None,
                      "source_grids_and_outward_9km_endpoints_NOT_railroad_accepted":True,
                      "station_area_vertical_2m_only_not_continuous_ground_rail_3D":True,
                      "road_legal_landslide_hydro_Natura_PIC_unknown":True,
                      "not_engineered_clothoid_cant_transitions_safety_civil_station_alignment":True})
    if len(cases)!=30*7*3:raise ValueError("G45_incomplete_630")
    return opts,cases,route_data,total,passed
def execute(g10,g30,g25,g44,g42,outjson,outcsv,outmd,plot,geo):
    sites,cases,route_data,ncand,nfound=evaluate(g10,g30,g25,g44,g42)
    report={"mission":"MN-GEO-RAIL-001",
      "stage":"G45_all30_station_historical_study_sites_shiftable_entry_exit_quintic_horizontal",
      "all_G10_27_and_G30_3_retained":True,"source_30_options":30,
      "seven_original_DGT2m_study_sites":7,"original_G25_platform_orientation_contexts":29,
      "station_straight_assumed_m":STATION_LENGTH,
      "exit_entry_shift_set_m":list(EXT),"quintic_heading_derivative_scales":list(DERIV_SCALES),
      "radii_m_by_illustrative_speed":RADIUS,
      "site_source_original_road_COS_DGT2m_from_G44":[v["meta"] for v in sites.values()],
      "all_630_route_site_speed_horizontal_screen_cases":cases,
      "source_city_contact_chainages_by_route":{r+"_"+c:v for (r,c),v in route_data.items()},
      "exploratory_horizontal_geometries_attempted":ncand,
      "site_speed_route_cases_with_a_sampled_R_planar_solution":nfound,
      "source_horizontal_curvature_sample_only_NOT_design_railway_compliance":True,
      "station_platform_straight_assumed_not_standard_certified":True,
      "no_true_horizontal_clothoid_superelevation_gauge_transition_rail_approval":True,
      "no_station_centerline_vertical_grade_or_underlying_ground_full_route":True,
      "no_constructed_tunnel_viaduct_lengths_costs_times":True,
      "no_Natura2000_PIC_legal_freight_passenger_approval":True,
      "no_new_DGT_geology_or_original_raster_acquisition":True,
      "Fxx_accepted":False,"Site_authorized":False}
    outjson.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    with outcsv.open("w",newline="",encoding="utf-8-sig") as f:
        keys=("option_id","mandatory_city","historical_site_id","illustrative_speed_label_kmh",
          "C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found",
          "screened_candidate_2D_geometries","geometries_passing_sampled_horizontal_radius",
          "source_existing_original_road_minutes")
        w=csv.DictWriter(f,fieldnames=keys,delimiter=";");w.writeheader()
        for row in cases:w.writerow({k:row.get(k) for k in keys})
    # Draw P2-2-1 geometries (one per physical site) at 200 km/h plus original
    # G10 grid reference. All plotted bearings were previously source studied.
    fig,axs=plt.subplots(1,2,figsize=(14,6),layout="constrained")
    mapfeatures=[]
    for ax,city in zip(axs,CITY_BOUNDS):
        originals=original_path(next(f for f in g10["features"] if f["properties"]["id"]=="P2-2-1"))
        west,east=controls(originals,city)
        old=[originals.interpolate(v) for v in np.linspace(west,east,30)]
        ax.plot([p.x/1000 for p in old],[p.y/1000 for p in old],ls=":",lw=1.8,c="#8c979c",label="G10 grelha antiga")
        for sid,entry in sites.items():
            if entry["meta"]["mandatory_city"]!=city:continue
            r=next(row for row in cases if row["option_id"]=="P2-2-1" and row["historical_site_id"]==sid and row["illustrative_speed_label_kmh"]==200)
            x,y=entry["xy"]
            ax.scatter([x/1000],[y/1000],c="#a04c42",s=30,zorder=5)
            ax.annotate(sid,(x/1000,y/1000),xytext=(4,6),textcoords="offset points",fontsize=8)
            sol=r["best_research_horizontal_solution"]
            if sol:
                coords=sol["sampled_QA_path_PT_TM06"]
                ax.plot([u[0]/1000 for u in coords],[u[1]/1000 for u in coords],
                        lw=1.2,label=sid)
                loc=[TO_WGS.transform(*u) for u in coords]
                mapfeatures.append({"type":"Feature","geometry":{"type":"LineString","coordinates":loc},
                    "properties":{"reference_route":"P2-2-1","mandatory_city":city,"site_id":sid,
                      "source_speed_hypothesis_200kmh_radius_only":True,
                      "not_viable_constructed_railway_3D":True}})
        ax.set_aspect("equal",adjustable="datalim");ax.grid(alpha=.16)
        ax.set_title(city.replace("_"," ")+" · novas aproximações de estudo (200 km/h)",loc="left",fontsize=10)
        ax.set_xlabel("E PT-TM06 (km)");ax.set_ylabel("N PT-TM06 (km)")
        ax.legend(fontsize=7)
    fig.savefig(plot,dpi=160,bbox_inches="tight");plt.close(fig)
    geo.write_text(json.dumps({"type":"FeatureCollection","features":mapfeatures},ensure_ascii=False)+"\n")
    counts=[]
    for city in CITY_BOUNDS:
        for speed in RADIUS:
            rows=[r for r in cases if r["mandatory_city"]==city and r["illustrative_speed_label_kmh"]==speed]
            best_count=sum(r["C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found"] for r in rows)
            counts.append({"city":city,"speed":speed,"passing_route_site_pairs":best_count,"total_route_site_pairs":len(rows)})
    md=["# G45 — Reabrir aproximações em planta: sete sítios anteriores e 30 corredores, 160/200/250",
      "","Reutilizam-se as **sete localizações DGT2m efetivamente estudadas** e todas as **29 orientações originais do G25**. Contrariamente ao G44, as entradas e saídas no corredor não ficam presas às âncoras da grelha G10: admitem deslocamentos para fora de 0, 3, 6 ou 9 km, mantendo o sítio de plataforma.",
      "","## Geometria contínua condicionada (sem relevo 3D)",
      "Cada hipótese é formada por curva polinomial de 5.º grau com posição, tangente e 2.ª derivada nula nos contactos com uma **reta de estação de 800 m**, terminando em dois pontos móveis da grelha de referência. A curvatura é amostrada ao longo da geometria e verificada para raios hipotéticos 1 500 / 2 400 / 3 700 m (rótulos 160/200/250 km/h). **Não há garantia de conformidade** com parâmetros EN, clotóides ou transições de superelevação; nem terreno, geologia, licenças ou continuidade do eixo interurbano.",
      "","| Cidade | Velocidade de ensaio | Pares corredor–sítio com uma geometria 2D amostrada que passa o raio | Total de pares |",
      "|---|---:|---:|---:|"]
    for row in counts:md.append(f"| {row['city']} | {row['speed']} | {row['passing_route_site_pairs']} | {row['total_route_site_pairs']} |")
    md+=["","## BR4 — mudança de abordagem metodológica",
       "A incompatibilidade do BR4 com a âncora oriental fixa original no G44 é uma incompatibilidade da geometria anterior, não da posição de estação em abstrato. O G45 permite que a concordância se estenda para além do último ponto urbano da grelha e verifica geometricamente se existe um **eixo 2D suave candidato** com a reta de plataforma. Quando existe, passa apenas o teste amostrado de curvatura, não a validação construtiva. Quando não existe no conjunto ensaiado, a situação é **não encontrada**, não impossibilidade técnica de construir.",
       "","## Critérios seguintes de engenharia",
       "1. Selecionar para cada cidade 2–3 configurações de estudo de não dominância (acesso rodoviário G25, topografia DGT2m G23B, deslocamento de contactos, curvatura e acessibilidade territorial), sem fixar 1 das 30 alternativas globais.",
       "2. Para cada geometria 2D selecionada, obter terreno original **contínuo** ao longo dos eixos candidatos; as 84 quadrículas DGT2m já disponíveis devem ser consultadas e reutilizadas primeiro, identificando apenas lacunas concretas.",
       "3. Testar rasantes de estação e curvas verticais, incluindo mudanças 160/200/250 na entrada de estação, e depois construir combinações 3D com geologia, Natura 2000, PIC, portais e hidrogeologia.",
       "4. Só depois quantificar extensões de túnel, viaduto, plataforma e tempos de marcha; incluir a qualidade de serviço para Guimarães, Amarante, Mirandela e Macedo de Cavaleiros.",
       "","**A prova geométrica G45, mesmo positiva, não é projeto ferroviário. Todos os 30 corredores permanecem em estudo; nenhuma autorização ambiental, de tráfego ou custo foi inferida.**"]
    outmd.write_text("\n".join(md)+"\n")
    print("G45_RESULT",json.dumps({"candidate_evaluations":ncand,"site_speeds_covered":nfound,"counts":counts,
      "BR4_P221":{str(speed):next(r["best_research_horizontal_solution"] for r in cases if r["option_id"]=="P2-2-1" and r["historical_site_id"]=="BR4" and r["illustrative_speed_label_kmh"]==speed) for speed in RADIUS},
      "original_29_orientations":29,"all30":True},ensure_ascii=False),flush=True)
def main():
    a=argparse.ArgumentParser()
    for k in ("g10","g30","g25","g44","g42","json","csv","markdown","map","geojson"):
        a.add_argument("--"+k,required=True,type=Path)
    p=a.parse_args()
    execute(*[json.loads(getattr(p,k).read_text()) for k in ("g10","g30","g25","g44","g42")],
           p.json,p.csv,p.markdown,p.map,p.geojson)
if __name__=="__main__":main()
