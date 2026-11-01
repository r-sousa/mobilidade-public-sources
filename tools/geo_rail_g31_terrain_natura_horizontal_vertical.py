#!/usr/bin/env python3
"""G31: 3 G30 NEW + G10 reference railway NECESSARY CONDITION research screens.

Source-verified real Copernicus 30m DSM, G28 original Natura polygons, and G7
horizontal/vertical mathematical screening. NOT a railway axis, approval, or
tunnel/viaduct length. Refuse invented engineering and price estimates.
"""
import argparse,hashlib,json,math,sys
from pathlib import Path
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import shape,Point,LineString
from shapely.ops import transform,unary_union
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g7_rail_screen import (
    DSM_SHA,SPEEDS,GRADIENTS_PERMILLE,
    dense,smooth,radius_screen,distance_from_source,sample_dsm,grade_envelopes
)
TO_PT=Transformer.from_crs(4326,3763,always_xy=True).transform
TO_WGS=Transformer.from_crs(3763,4326,always_xy=True).transform
SPEEDS_KMH=(160,200,250)
GRADIENTS=(18,25)
SIGMAS_M=(600.,1100.,1700.,2400.,3400.,4800.,6500.,8500.,11000.)
MAX_SHIFT_M=(3000.,6000.)
STEP_M=400.
ALVAO_KEYWORDS=("alvão","marão","alvao","marao")
LABELS={"avoid_surface_overlap":"G30 evitamento superficie",
        "potential_deep_tunnel":"G30 hipotese de tunel",
        "geographic_diversity":"G30 diversidade",
        "P2-2-1":"G10 P2-2-1 referencia"}
def sha(b):
    return hashlib.sha256(b).hexdigest()
def projection_points(feature):
    line=shape(feature["geometry"])
    if line.geom_type!="LineString" or len(line.coords)<10:raise ValueError("G31_not_source_polyline")
    xy=np.asarray([TO_PT(*p) for p in line.coords],dtype=float)
    if np.any(~np.isfinite(xy)):raise ValueError("G31_coordinate_nan")
    if np.max(np.linalg.norm(np.diff(xy,axis=0),axis=1))>2880.:raise ValueError("G31_not_2km_grid_topology")
    return xy
def validate(g10,g28,g30,gj30,g28poly,polybytes,dsm):
    if sha(dsm.read_bytes())!=DSM_SHA:raise ValueError("G31_primary_Copernicus_DSM_SHA_mismatch")
    if len(g10.get("features",[]))!=27 or len(gj30.get("features",[]))!=3:
        raise ValueError("G31_expected_27_plus_3_geojson")
    if set(f["properties"]["id"] for f in gj30["features"])!=set("G30-"+x for x in LABELS if x!="P2-2-1"):
        raise ValueError("G31_G30_three_named_scenarios_missing")
    if g30.get("number_new_independent_search_scenarios")!=3 or not g30.get("deep_tunnel_is_only_hypothesis_no_verified_3D_alignment"):
        raise ValueError("G31_not_exact_G30_research_evidence")
    if g28.get("mission")!="MN-GEO-RAIL-001" or g28.get("PIC")!="UNKNOWN_NOT_DEFINED_OFFICIAL_SPATIAL_SOURCE_REQUIRED":
        raise ValueError("G31_G28_PIC_contract_unresolved")
    if sha(polybytes)!=g28["producer_clipped_natura_polygon_cache_sha256"]:
        raise ValueError("G31_producer_Natura_SHA_mismatch")
    if len(g28poly["features"])!=g28["producer_clipped_natura_polygon_count"]:
        raise ValueError("G31_G28_polygon_count_mismatch")
    if any(g28["source_receipts"][x]["status"]!="VERIFIED" for x in ("PT_ICNF","ES_MITECO")):
        raise ValueError("G31_official_PT_ES_Natura_unverified")
    if not all(f["properties"].get("NOT_an_engineered_railway") and
               f["properties"].get("legal_Natura_screen")=="ASSESSMENT_REQUIRED"
               for f in gj30["features"]):
        raise ValueError("G31_G30_legal_gate_must_remain")
def identify_alvao_site(features):
    """Official producer label/fields, never assume any polygon is Alvão/Marão."""
    matched=[]
    for f in features:
        props=f.get("properties") or {}
        if props.get("source")!="PT_ICNF":continue
        candidate=str(props.get("site_label","")).casefold()
        if any(term in candidate for term in ALVAO_KEYWORDS):
            matched.append(transform(TO_PT,shape(f["geometry"])))
    return unary_union(matched) if matched else None
def choose_horizontal(source,needed_radius,allowed_m):
    """G7 Gaussian curvature proxy at 400m, no clothoids, 3/6km envelope."""
    _,initial=dense(source,step_m=STEP_M)
    for sigma in SIGMAS_M:
        q=smooth(initial,sigma,step_m=STEP_M)
        radius=radius_screen(q)
        if radius is None or not math.isfinite(radius[0]):continue
        max_shift,p95=distance_from_source(q,source)
        if radius[0]>=needed_radius and max_shift<=allowed_m:
            kmdist=float(np.linalg.norm(np.diff(q,axis=0),axis=1).sum()/1000)
            return q,{"sigma_m":sigma,"proxy_min_radius_m":round(radius[0],1),
                      "max_shift_from_source_grid_m":round(max_shift,1),
                      "p95_shift_from_source_grid_m":round(p95,1),
                      "research_smoothed_length_km":round(kmdist,3),
                      "smoothing_is_NOT_an_engineered_horizontal_alignment":True}
    return None,None
def length_in_poly(poly,line):
    if poly is None:return None
    return round(float(line.intersection(poly).length/1000),3)
def profile(z,coords,grade_permille):
    seg=np.linalg.norm(np.diff(coords,axis=0),axis=1)
    ss=np.r_[0.,np.cumsum(seg)]
    h=grade_envelopes(z,ss,grade_permille/1000.)
    delta=h-z
    if np.any(np.abs(np.diff(h))>grade_permille/1000.*np.diff(ss)+.01):
        raise ValueError("G31_derived_vertical_envelope_gradient_violated")
    return ss,h,delta
def pressure_summary(s,z,delta,points,alvao):
    diff=np.diff(s)
    offset=0.5*(delta[1:]+delta[:-1])
    midpoints=(points[1:]+points[:-1])/2
    negative25=offset < -25
    negative50=offset < -50
    positive25=offset >25
    result={
        "mean_abs_DSM_deviation_m_proxy":round(float(np.average(abs(offset),weights=diff)),2),
        "max_abs_DSM_deviation_m_proxy":round(float(max(abs(delta))),2),
        "profile_km_line_below_DSM_over25m_NOT_tunnel_km":round(float(sum(diff[negative25])/1000),3),
        "profile_km_line_below_DSM_over50m_NOT_tunnel_km":round(float(sum(diff[negative50])/1000),3),
        "profile_km_line_above_DSM_over25m_NOT_viaduct_km":round(float(sum(diff[positive25])/1000),3),
        "all_absolute_DSM_proxy_lengths_not_structure_lengths":True}
    if alvao is None:
        result["Alvao_Marao_official_site"]="UNKNOWN_NOT_FOUND_IN_G28_LABELS"
        result["Alvao_Marao_coincident_below_DSM_25m_km_NOT_tunnel"]=None
    else:
        # Midpoint sampling of 400m gradient screen; GIS overlay measured separately.
        in_site=np.fromiter((alvao.intersects(Point(float(x),float(y)))
                             for x,y in midpoints),dtype=bool,count=len(midpoints))
        result["Alvao_Marao_official_site"]="LABEL_FOUND_PT_ICNF"
        result["Alvao_Marao_coincident_below_DSM_25m_km_NOT_tunnel"]=round(
            float(sum(diff[negative25 & in_site])/1000),3)
        result["Alvao_Marao_coincident_below_DSM_50m_km_NOT_tunnel"]=round(
            float(sum(diff[negative50 & in_site])/1000),3)
    return result
def analyse(paths,g28,g30,poly,polybytes,dsm,outjson,outmd,outfig):
    validate(paths["g10"],g28,g30,paths["g30"],poly,polybytes,dsm)
    poly_geoms=[transform(TO_PT,shape(f["geometry"])) for f in poly["features"]]
    natura=unary_union(poly_geoms)
    alvao=identify_alvao_site(poly["features"])
    if alvao is None:
        print("WARNING: Alvao/Marão official site label not resolved; do not invent zero.")
    g30paths={f["properties"]["id"].removeprefix("G30-"):f for f in paths["g30"]["features"]}
    reference=next(f for f in paths["g10"]["features"] if f["properties"]["id"]=="P2-2-1")
    candidates={**g30paths,"P2-2-1":reference}
    rows=[];profiles={}
    with rasterio.open(dsm) as ds:
        if ds.crs is None or ds.crs.to_epsg()!=4326:raise ValueError("G31_real_DSM_CRS_not_4326")
        for key,f in candidates.items():
            source=projection_points(f)
            if key!="P2-2-1" and (key not in g30["research_route_modes"]):
                raise ValueError("G31_input_scenario_id_not_in_original_G30")
            original=LineString(source)
            base_natura=length_in_poly(natura,original)
            base_alvao=length_in_poly(alvao,original)
            for speed in SPEEDS_KMH:
                row={"study_option":key,"speed_scenario_kmh":speed,
                     "conservative_horizontal_radius_screen_m":SPEEDS[speed],
                     "original_research_grid_km_NOT_track":round(original.length/1000,3),
                     "original_grid_Natura_intersection_km_NOT_impact":base_natura,
                     "original_grid_Alvao_Marao_intersection_km_NOT_impact":base_alvao,
                     "gradient_sensitivity_permille":list(GRADIENTS),
                     "preference_for_tunnel_not_a_legal_exemption":True,
                     "existing_stations_and_road_access_not_revalidated":True,
                     "PIC":"UNKNOWN",
                     "terrain":"original_Copernicus_GLO30_DSM_surface_NOT_ground"}
                output=None
                for envelope in MAX_SHIFT_M:
                    candidate,proof=choose_horizontal(source,SPEEDS[speed],envelope)
                    if candidate is not None:
                        output=(candidate,proof,envelope)
                        break
                if output is None:
                    row.update({"status":"HORIZONTAL_RADIUS_NOT_DEMONSTRATED_WITHIN_6KM_STUDY_ENVELOPE",
                                "horizontal_screen_pass_3km":False,
                                "horizontal_screen_pass_6km":False,"vertical_screen":"NOT_COMPUTED"})
                    rows.append(row);continue
                q,pr,envelope=output
                row["status"]="GEOMETRY_PROXY_ONLY_NOT_FEASIBLE_RAILWAY"
                row["horizontal_screen_pass_3km"]=envelope==3000
                row["horizontal_screen_pass_6km"]=True
                row["selected_source_corridor_halfwidth_sensitivity_m"]=envelope
                row["horizontal_proxy"]=pr
                smoothed=LineString(q)
                row["smoothed_study_line_Natura_intersection_km_NOT_impact"]=length_in_poly(natura,smoothed)
                row["smoothed_study_line_Alvao_Marao_intersection_km_NOT_impact"]=length_in_poly(alvao,smoothed)
                dsm_z=sample_dsm(ds,q)
                row["GLO30_DSM_samples"]=len(dsm_z)
                row["source_DSM_min_max_m"]=list(map(lambda x:round(float(x),2),
                                                  (min(dsm_z),max(dsm_z))))
                graded={}
                for grade in GRADIENTS:
                    ss,h,delta=profile(dsm_z,q,grade)
                    graded[str(grade)]=pressure_summary(ss,dsm_z,delta,q,alvao)
                    if speed==200 and grade==25:
                        profiles[key]={"km":ss/1000,"z":dsm_z,"h":h,
                                       "alvao_line_overlap_km":row["smoothed_study_line_Alvao_Marao_intersection_km_NOT_impact"]}
                row["vertical_source_DSM_screen_by_gradient_permille"]=graded
                row["vertical_profile_has_unbounded_station_levels_and_no_vertical_curves"]=True
                rows.append(row)
    if len(rows)!=12:raise ValueError("G31_expected_4x3_speed_rows")
    fig,axs=plt.subplots(4,1,figsize=(12.2,10.8),layout="constrained",sharex=False)
    for ax,(k,lab) in zip(axs,LABELS.items()):
        if k in profiles:
            z=profiles[k];x=z["km"]
            ax.plot(x,z["z"],c="#667b64",lw=1,label="MDS Copernicus 30m")
            ax.plot(x,z["h"],c="#b85735",lw=1,label="Ajuste matemático gradiente ≤25‰")
            ax.set_title(lab+" · 200 km/h (apenas raio geométrico de triagem)",fontsize=10,loc="left")
        else:
            ax.text(.05,.5,"Sem suavização admissível no envelope de 6 km a 200 km/h; perfil não calculado",
                    transform=ax.transAxes,fontsize=9)
            ax.set_title(lab+" · teste de raio não demonstrado",fontsize=10,loc="left")
        ax.set_xlabel("Extensão ao longo da linha suavizada de estudo (km)",fontsize=8)
        ax.set_ylabel("Cota aprox. MDS (m)",fontsize=8)
        ax.grid(alpha=.2)
    axs[0].legend(loc="upper right",fontsize=8) if profiles and next(iter(profiles)) in profiles else None
    fig.suptitle("G31 · Portugal–Zamora: relevo e perfis matemáticos (NÃO são ferrovia nem túneis)",fontsize=13)
    fig.savefig(outfig,dpi=150,bbox_inches="tight");plt.close(fig)
    out={"mission":"MN-GEO-RAIL-001","stage":"G31_horizontal_radius_and_DSM_gradient_necessary_conditions",
         "source_GLO30_DSM_sha256":DSM_SHA,
         "source_G28_exact_official_polygon_cache_sha256":sha(polybytes),
         "original_G10_paths":27,"G30_new_distinct_paths":3,
         "scenarios":len(rows),"speed_scenarios":[160,200,250],
         "Alvao_Marao_official_ICNF_site_label_found":alvao is not None,
         "Alvao_Marao_specific_legal_management_review_required":True,
         "PIC_official_source_still_unknown":True,
         "projected_PTTM06_used_across_border_spatial_screen_only":True,
         "PT_ES_vertical_datum_unharmonized":True,
         "surface_DSM_not_ground_DTM":True,"gradient_profile_free_endpoints_no_stations":True,
         "no_3d_railway_crest_cut_volumes_tunnel_portal_groundwater_earthworks":True,
         "no_estimated_tunnel_viaduct_length_cost_or_travel_time":True,
         "no_additional_DGT_original_tile_acquisition":True,
         "no_accepted_Fxx_or_Site":True,"results":rows}
    outjson.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
    md=["# G31 — Curvatura e MDS dos três corredores novos G30 + referência G10",
      "","**Cadeias geográficas de investigação, não traçados ferroviários viáveis.** Fonte física: Copernicus GLO30 MDS original verificado SHA. G28 polígonos originais ICNF e MITECO. G30 três variantes novas. Sem descarga DGT/MITECO/ICNF.",
      "","Ensaios 160/200/250 km/h; raios de triagem conservadores G7 **1500, 2400, 3700 m**; envelopes máximo de deslocação lateral 3 km (principal), 6 km (sensibilidade mais permissiva). Não substituem raios normativos específicos, clotóides, sobrelarguras, perfil longitudinal ou projeto.",
      "","| Cadeia | km/h | Curvatura no envelope 3 km | Curvatura no envelope 6 km | Extensão suavizada km | Natura km (linha suavizada) | Alvão/Marão km (linha suavizada) | 25‰ pressão MDS abaixo >25m km |",
      "|---|---:|---|---|---:|---:|---:|---:|"]
    for r in rows:
        p=r.get("horizontal_proxy",{})
        v=r.get("vertical_source_DSM_screen_by_gradient_permille",{}).get("25",{})
        md.append(f"| {r['study_option']} | {r['speed_scenario_kmh']} | {'sim' if r.get('horizontal_screen_pass_3km') else 'não'} | {'sim' if r.get('horizontal_screen_pass_6km') else 'não'} | {p.get('research_smoothed_length_km','—')} | {r.get('smoothed_study_line_Natura_intersection_km_NOT_impact','—')} | {r.get('smoothed_study_line_Alvao_Marao_intersection_km_NOT_impact','—')} | {v.get('profile_km_line_below_DSM_over25m_NOT_tunnel_km','—')} |")
    md+=["","**Nunca converter o proxy de linha abaixo do MDS em quilómetros de túnel.** A cota de MDS inclui copa florestal e edifícios; a aproximação geométrica pode exigir deslocação para fora de corredor de 3 km, e o ajuste de 18/25‰ não contém cota obrigatória das estações nem curvas verticais. O percurso suavizado não contém clotóides e condições de exploração para a velocidade estudada.",
      "","**No Marão–Alvão:** os segmentos de interseção com o sítio Natura 2000 são de linha de estudo (2D). A coincidência com pressão topográfica negativa não prova túnel profundo nem ausência de drenagem de aquíferos. Verificar geologia, águas subterrâneas, turfeiras, nascentes, portais e poços, método construtivo e objetivos de conservação da ZEC PTCON0003.",
      "","**Portões não resolvidos:** PIC, perfil ferroviário 3D e sondagens, efeitos ambientais indiretos, estações/acessos rodoviários BGRI/OSRM, custos/tempos reais, bitola, interoperabilidade e harmonização altimétrica PT/ES. Evitar autorizações implícitas; não publicar no catálogo Fxx/Site.",
      "","Base legal: Diretiva Habitats art. 6.º, DL 140/99 (art. 10.º), DL 28/2025 e Portaria 135/2025/1 para Alvão/Marão; presença de túnel não gera isenção. Sem novas quadrículas DGT nesta fase.",
      ""]
    outmd.write_text("\n".join(md))
    counts={k:sum(r.get("horizontal_screen_pass_3km",False) for r in rows if r["study_option"]==k) for k in candidates}
    print("G31",json.dumps({"rows":len(rows),"pass3_by_chain":counts,"Alvao_found":alvao is not None,
                              "first_rows":[{x:r.get(x) for x in ("study_option","speed_scenario_kmh","status","horizontal_screen_pass_3km","smoothed_study_line_Alvao_Marao_intersection_km_NOT_impact")} for r in rows]},ensure_ascii=False))
def main():
    p=argparse.ArgumentParser()
    for k in ("g10","g28","g30","g30geo","polygons","dsm","json","markdown","figure"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args()
    analyse({"g10":json.loads(a.g10.read_text()),"g30":json.loads(a.g30geo.read_text())},
            json.loads(a.g28.read_text()),json.loads(a.g30.read_text()),
            json.loads(a.polygons.read_bytes()),a.polygons.read_bytes(),a.dsm,
            a.json,a.markdown,a.figure)
if __name__=="__main__":main()
