#!/usr/bin/env python3
"""G32: 27 G10 and 3 G30 on ONE mandatory comparable environmental/terrain matrix.

Uses original source-locked G28 Natura polygons & Copernicus GLO30 DSM.
Reuses exact G31 horizontal proxy, gradient envelopes and Alvao review.
Research grids != engineered rail track; no verified tunnel quantities, costs or timetables.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sys
from collections import Counter
from pathlib import Path
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import shape,LineString,Point
from shapely.ops import transform,unary_union
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g31_terrain_natura_horizontal_vertical import (
    TO_PT,DSM_SHA,SPEEDS_KMH,GRADIENTS,MAX_SHIFT_M,choose_horizontal,
    identify_alvao_site,profile,pressure_summary,projection_points,
    length_in_poly,sample_dsm
)
from geo_rail_g7_rail_screen import SPEEDS
FAMILY_G10="G10"
FAMILY_G30="G30"
SCENARIOS=(160,200,250)
MARKERS={"G10":"o","G30":"D"}
COLORS={"G10":"#8196a5","G30":"#c15b28"}
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def collect(g10,g30,g30geo):
    original=g10.get("features",[])
    newer=g30geo.get("features",[])
    if len(original)!=27 or len(newer)!=3:raise ValueError("G32_fails_closed_27_plus_3")
    ids=[f["properties"]["id"] for f in original]
    if len(set(ids))!=27 or set(ids)!={"P"+str(a)+"-"+str(b)+"-"+str(c) for a in (1,2,3) for b in (1,2,3) for c in (1,2,3)}:
        raise ValueError("G32_G10_original_27_combinations_must_all_be_present")
    out={}
    for f in original:
        if not f["properties"].get("this_is_not_an_approved_or_proposed_railway_alignment"):
            raise ValueError("G32_original_G10_not_study_only")
        out[f["properties"]["id"]]={"family":"G10","feat":f}
    expected={"G30-avoid_surface_overlap","G30-potential_deep_tunnel","G30-geographic_diversity"}
    if {f["properties"]["id"] for f in newer}!=expected:
        raise ValueError("G32_G30_independent_variants_missing")
    if g30.get("number_new_independent_search_scenarios")!=3 or not g30.get("deep_tunnel_is_only_hypothesis_no_verified_3D_alignment"):
        raise ValueError("G32_G30_provenance_not_confirmed")
    for f in newer:
        p=f["properties"]
        if not(p.get("NOT_an_engineered_railway") and p.get("legal_Natura_screen")=="ASSESSMENT_REQUIRED"):
            raise ValueError("G32_G30_legal_screen_reclassified_illegally")
        out[p["id"]]={"family":"G30","feat":f}
    if len(out)!=30:raise ValueError("G32_expected_30_studies")
    return out
def validate(g10,g28,g30,g30geo,polys,polybytes,dsm_path):
    if sha_bytes(dsm_path.read_bytes())!=DSM_SHA:
        raise ValueError("G32_GLO30_primary_SHA_mismatch")
    if g28.get("mission")!="MN-GEO-RAIL-001" or g28.get("PIC")!="UNKNOWN_NOT_DEFINED_OFFICIAL_SPATIAL_SOURCE_REQUIRED":
        raise ValueError("G32_PIC_must_be_UNKNOWN")
    if sha_bytes(polybytes)!=g28.get("producer_clipped_natura_polygon_cache_sha256"):
        raise ValueError("G32_original_ICNF_MITECO_polygon_sha_mismatch")
    if len(polys.get("features",[]))!=g28.get("producer_clipped_natura_polygon_count"):
        raise ValueError("G32_producer_polygon_counts_not_unchanged")
    if any(g28["source_receipts"][k]["status"]!="VERIFIED" for k in ("PT_ICNF","ES_MITECO")):
        raise ValueError("G32_PT_ES_producer_not_verified")
    if len(g28.get("corridor_grid_research_27",[]))!=27:
        raise ValueError("G32_original_G28_comparators_lost")
    return collect(g10,g30,g30geo)
def strict_g30_lengths(items,g30):
    for key in ("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity"):
        data=items["G30-"+key]["feat"]
        length=shape(data["geometry"]).length
        # Geographic geometry length must be measured in metric CRS, not WGS degrees.
        route=projection_points(data)
        actual=LineString(route).length/1000
        expected=g30["research_route_modes"][key]["source_2km_research_length_km"]
        if abs(actual-expected)>.08:
            raise ValueError("G32_G30_cannot_preserve_length_"+key)
def radius_candidates(source):
    """G31 screen exactly; caching 3/6km selections across three speeds."""
    trials={}
    for speed in SCENARIOS:
        for envelope in MAX_SHIFT_M:
            candidate,proof=choose_horizontal(source,SPEEDS[speed],envelope)
            if candidate is not None:
                trials[speed]=(candidate,proof,envelope)
                break
    return trials
def compute(g10,g28,g30,g30geo,polys,polybytes,dsm_path,jsonout,csvout,mdout,figout,mapout):
    items=validate(g10,g28,g30,g30geo,polys,polybytes,dsm_path)
    strict_g30_lengths(items,g30)
    geoms=[transform(TO_PT,shape(f["geometry"])) for f in polys["features"]]
    protected=unary_union(geoms)
    alvao=identify_alvao_site(polys["features"])
    if alvao is None:raise ValueError("G32_Alvao_site_unverified_do_not_show_false_zero")
    # Union contains overlapping PT+ES classifications; overlap is not double counted.
    rows=[];profiles={}
    with rasterio.open(dsm_path) as ds:
        if not ds.crs or ds.crs.to_epsg()!=4326:
            raise ValueError("G32_DSM_not_source_EPSG4326")
        for i,(option,record) in enumerate(items.items(),start=1):
            original_xy=projection_points(record["feat"])
            original_line=LineString(original_xy)
            original_natura=length_in_poly(protected,original_line)
            original_alvao=length_in_poly(alvao,original_line)
            selections=radius_candidates(original_xy)
            for speed in SCENARIOS:
                common={"option_id":option,"source_family":record["family"],
                    "scenario_speed_kmh":speed,
                    "radius_screen_m":SPEEDS[speed],
                    "G10_or_G30_original_research_grid_length_km":round(original_line.length/1000,3),
                    "original_line_Natura2000_km_not_impact":original_natura,
                    "original_line_Alvao_Marao_km_not_impact":original_alvao,
                    "not_railway_alignment":True,
                    "not_evaluable_actual_train_time":True,
                    "PIC_legal_source_UNRESOLVED":True,
                    "service_Guimaraes_Amarante_Mirandela_Macedo":"UNKNOWN_FUNCTIONAL_SERVICE",
                    "service_Vila_Real_Braganca":"MANDATORY_STUDY_ANCHOR_ONLY_STATION_UNVERIFIED",
                    "road_access_minutes":"NOT_MEASURED_FOR_THIS_30_COMPARISON",
                    "cost_EUR":"NOT_CALCULABLE_WITH_EXISTING_3D_DATA",
                    "tunnel_km":"UNKNOWN_NO_3D_PROJECT",
                    "environmental_authorization":"NOT_ASSESSED_SITE_INTEGRITY"}
                if speed not in selections:
                    common.update({"status":"NO_HORIZONTAL_RADIUS_PROXY_DEMONSTRATED_WITHIN_6KM",
                        "pass_3km":False,"pass_6km":False,
                        "shift_envelope_m":None,
                        "length_smoothed_km":None,
                        "Natura_smoothed_km":None,
                        "Alvao_smoothed_km":None,
                        "DSM_25permille_below25_km_not_tunnel":None,
                        "DSM_25permille_below50_km_not_tunnel":None,
                        "DSM_25permille_above25_km_not_viaduct":None,
                        "DSM_25permille_mean_abs_deviation_m":None,
                        "DSM_18permille_below25_km_not_tunnel":None})
                    rows.append(common);continue
                q,proof,envelope=selections[speed]
                smoothline=LineString(q)
                heights=sample_dsm(ds,q)
                metric={}
                for grad in GRADIENTS:
                    ss,h,delta=profile(heights,q,grad)
                    metric[grad]=pressure_summary(ss,heights,delta,q,alvao)
                    if speed==200 and grad==25:
                        profiles[option]={"line":smoothline,"points":q,"height":heights,
                                          "profile":h}
                common.update({"status":"HORIZONTAL_AND_DSM_GRADIENT_PROXIES_ONLY",
                    "pass_3km":envelope==3000,"pass_6km":True,
                    "shift_envelope_m":envelope,
                    "radius_estimate_m":proof["proxy_min_radius_m"],
                    "max_source_shift_m":proof["max_shift_from_source_grid_m"],
                    "length_smoothed_km":proof["research_smoothed_length_km"],
                    "Natura_smoothed_km":length_in_poly(protected,smoothline),
                    "Alvao_smoothed_km":length_in_poly(alvao,smoothline),
                    "DSM_25permille_below25_km_not_tunnel":metric[25]["profile_km_line_below_DSM_over25m_NOT_tunnel_km"],
                    "DSM_25permille_below50_km_not_tunnel":metric[25]["profile_km_line_below_DSM_over50m_NOT_tunnel_km"],
                    "DSM_25permille_above25_km_not_viaduct":metric[25]["profile_km_line_above_DSM_over25m_NOT_viaduct_km"],
                    "DSM_25permille_mean_abs_deviation_m":metric[25]["mean_abs_DSM_deviation_m_proxy"],
                    "DSM_18permille_below25_km_not_tunnel":metric[18]["profile_km_line_below_DSM_over25m_NOT_tunnel_km"]})
                rows.append(common)
            print("G32_PROGRESS",i,"/30",option,flush=True)
    if len(rows)!=90 or len({r["option_id"] for r in rows})!=30:raise ValueError("G32_90_expected")
    keys=rows[0].keys()
    if any(r.keys()!=keys for r in rows):raise ValueError("G32_stable_comparison_schema")
    byspeed={speed:[r for r in rows if r["scenario_speed_kmh"]==speed] for speed in SCENARIOS}
    if any(len(v)!=30 or sum(r["source_family"]=="G10" for r in v)!=27 or
           sum(r["source_family"]=="G30" for r in v)!=3 for v in byspeed.values()):
        raise ValueError("G32_27_plus_3_in_each_of_three_speeds")
    # The all-portfolio Pareto is solely a source-geometry screen over 3 measured
    # dimensions (length, true polygon overlap, and DSM deviation); not a transport,
    # economic, environmental-permit, or territorial cohesion ranking.
    pareto={}
    for speed,group in byspeed.items():
        used=[r for r in group if r["pass_6km"]]
        dims=("length_smoothed_km","Natura_smoothed_km","DSM_25permille_mean_abs_deviation_m")
        front=[]
        for r in used:
            a=[r[d] for d in dims]
            dominated=any((s["option_id"]!=r["option_id"] and
              all(s[d]<=v+1e-7 for d,v in zip(dims,a)) and
              any(s[d]<v-1e-7 for d,v in zip(dims,a))) for s in used)
            if not dominated:front.append(r["option_id"])
        pareto[str(speed)]=front
    obj={"mission":"MN-GEO-RAIL-001",
         "stage":"G32_UNIFIED_27_G10_plus_3_G30_3speed_90source_only",
         "G10_count":27,"G30_count":3,"total_study_routes":30,
         "speed_scenarios_kmh":list(SCENARIOS),"total_rows":90,
         "canonical_portfolio_next_stages_all_27_G10_plus_3_G30":True,
         "independent_source_original_Natura_polygon_sha256":sha_bytes(polybytes),
         "independent_source_original_Copernicus_GLO30_sha256":DSM_SHA,
         "Alvao_Marao_official_source_label_found":True,
         "PIC_status":"UNRESOLVED_MUST_NOT_RANK_AS_LEGALLY_CLEARED",
         "radius_m_by_speed":{str(x):SPEEDS[x] for x in SCENARIOS},
         "max_offset_research_screen_m":[3000,6000],
         "gradients_per_mille":[18,25],
         "source_grid_2km_cannot_prove_tunnel_length":True,
         "DSM_is_surface_vegetation_buildings_not_bare_earth":True,
         "no_stations_service_quality_road_access_cost_CBA_or_running_time_estimates":True,
         "metric_only_Pareto_not_recommendation":pareto,
         "new_DGT_tiles":0,"Fxx_accepted":False,"Site_authorized":False,
         "rows":rows}
    jsonout.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
    with csvout.open("w",newline="",encoding="utf-8-sig") as file:
        writer=csv.DictWriter(file,fieldnames=list(keys),delimiter=";")
        writer.writeheader();writer.writerows(rows)
    # One same-scale scatter plot per speed, 27 G10 circles + 3 G30 diamonds.
    fig,axs=plt.subplots(1,3,figsize=(17,6.5),layout="constrained",sharey=True)
    for ax,speed in zip(axs,SCENARIOS):
        group=byspeed[speed]
        for family in (FAMILY_G10,FAMILY_G30):
            r=[x for x in group if x["source_family"]==family and x["pass_6km"]]
            if r:
                ax.scatter([x["Natura_smoothed_km"] for x in r],
                           [x["length_smoothed_km"] for x in r],
                           s=75 if family=="G30" else 26,c=COLORS[family],
                           marker=MARKERS[family],alpha=.9 if family=="G30" else .57,
                           edgecolors="white" if family=="G30" else "none",
                           linewidths=.5,zorder=5 if family=="G30" else 2)
                if family=="G30":
                    for x in r:ax.annotate(x["option_id"].replace("G30-",""),(
                        x["Natura_smoothed_km"],x["length_smoothed_km"]),
                        fontsize=7,xytext=(3,5),textcoords="offset points")
        fails=[x for x in group if not x["pass_6km"]]
        ax.set_title(f"{speed} km/h · {len(group)-len(fails)}/30 passam proxy no envelope 6 km",fontsize=10)
        ax.set_xlabel("Interseção da linha suavizada com Natura 2000 (km)\nNÃO impacte nem túnel",fontsize=8)
        ax.grid(alpha=.22)
        if fails:
            ax.text(.02,.98,"Sem curvatura demonstrada: "+", ".join(x["option_id"] for x in fails),
                    fontsize=7,va="top",ha="left",transform=ax.transAxes)
    axs[0].set_ylabel("Extensão da linha suavizada de investigação (km)\nNÃO extensão ferroviária",fontsize=8)
    fig.legend(handles=[Line2D([],[],marker="o",color="none",markerfacecolor=COLORS["G10"],label="27 G10",
                               markersize=7),Line2D([],[],marker="D",color="none",markerfacecolor=COLORS["G30"],
                               label="3 G30",markersize=8)],loc="outside upper center",ncol=2)
    fig.suptitle("G32 · Comparação obrigatória da carteira completa (G10 27 + G30 3) | fontes e métodos idênticos",fontsize=12)
    fig.savefig(figout,dpi=160,bbox_inches="tight");plt.close(fig)
    # Original research geometry backdrop; original producer Natura clipped region.
    fig,ax=plt.subplots(figsize=(13.0,8.3),layout="constrained")
    for p in geoms:
        simpl=p.simplify(250,preserve_topology=True)
        for poly in (simpl.geoms if simpl.geom_type=="MultiPolygon" else [simpl]):
            if poly.geom_type=="Polygon" and not poly.is_empty:
                xx,yy=poly.exterior.xy
                ax.fill(np.asarray(xx)/1000,np.asarray(yy)/1000,
                        color="#b1a079",alpha=.17,lw=0)
    for option,record in items.items():
        l=LineString(projection_points(record["feat"]))
        x,y=l.xy
        ax.plot(np.asarray(x)/1000,np.asarray(y)/1000,
                c=COLORS[record["family"]],lw=1.0 if record["family"]=="G10" else 2.0,
                alpha=.21 if record["family"]=="G10" else .94,
                zorder=1 if record["family"]=="G10" else 3)
        if record["family"]=="G30":
            mid=l.interpolate(.45,normalized=True)
            ax.annotate(option.replace("G30-",""),(mid.x/1000,mid.y/1000),fontsize=8,
                        bbox=dict(facecolor="white",alpha=.75,edgecolor="none"))
    ax.set_aspect("equal",adjustable="datalim")
    ax.set_xlabel("PT-TM06 EPSG:3763 E (km) · estudo PT/ES");ax.set_ylabel("N (km)")
    ax.set_title("27 linhas G10 + 3 novas G30 sobre sítios Natura 2000, fonte oficial original",fontsize=12,loc="left")
    ax.grid(alpha=.15)
    fig.savefig(mapout,dpi=160,bbox_inches="tight");plt.close(fig)
    # Complete comparable 200km/h matrix, not a short list hiding the other 26 G10.
    md=["# G32 — Carteira única comparável: 27 G10 + 3 G30 (160/200/250 km/h)",
        "","## Regras permanentes para os próximos ciclos",
        "Todos os **30 corredores** devem aparecer, lado a lado, em qualquer avaliação subsequente, com a mesma fonte e método. Novas variantes adicionam-se ao universo ou justificam-se as exclusões; não é legítimo comparar só G30 com uma referência G10 nem aprovar uma shortlist sem os 27 comparadores.",
        "","**Três velocidades** produzem **90 linhas** no CSV e JSON. Qualquer métrica ausente deve ser escrita como «não avaliada», não zero; nunca misturar MDS e MDT, comprimentos de linhas de grelha e traçados ferroviários, custos financeiros hipotéticos e dados observados.",
        "","## Matriz integral a 200 km/h (30 alternativas, ordenação por família e ID)",
        "","| Família | Alternativa | Comprimento suavizado de estudo (km) | Natura (km) | Alvão/Marão (km) | Proxy MDS abaixo >25 m (km) | Curvatura ≤3km | Curvatura ≤6km |",
        "|---|---|---:|---:|---:|---:|---|---|"]
    for r in byspeed[200]:
        fmt=lambda key:"—" if r.get(key) is None else str(r[key])
        md.append(f"| {r['source_family']} | {r['option_id']} | {fmt('length_smoothed_km')} | {fmt('Natura_smoothed_km')} | {fmt('Alvao_smoothed_km')} | {fmt('DSM_25permille_below25_km_not_tunnel')} | {'sim' if r['pass_3km'] else 'não'} | {'sim' if r['pass_6km'] else 'não'} |")
    md+=["","## Fronteira de não dominância — apenas indicadores matemáticos medidos",
         "Apenas comprimento da linha suavizada, interseção cartográfica e desvio médio absoluto MDS, todos menores-melhores e sem ponderação. **Não** é classificação de interesse público, ambiente, serviço, preço, tempo, economia nem conformidade jurídica.",
         "","| Velocidade de investigação | Alternativas não dominadas nos três indicadores source-only |",
         "|---:|---|"]
    for k,v in pareto.items():md.append(f"| {k} km/h | {', '.join(v) if v else 'sem candidatos demonstrados'} |")
    md+=["","## Critérios de decisão não medidos — igual tratamento para G10/G30",
         "| Dimensão decisiva | Estado da comparação atual |",
         "|---|---|",
         "| Estações e serviço de Vila Real/Bragança, Guimarães/Amarante/Mirandela/Macedo | Ligações de grelha exploratórias, sem estações 3D nem qualidade funcional comparável |",
         "| Acesso rodoviário, transporte público e BGRI21 | Fontes existentes, mas ainda sem reavaliação uniforme dos 30 percursos |",
         "| Custos de investimento, manutenção, túnel, viadutos, geotecnia | **Não calculáveis** a partir do MDS, sem desenho em 3D e solos nus contínuos |",
         "| Tempo de viagem / oferta | **Não calculado**; índice comprimento/velocidade não é marcha ferroviária |",
         "| Impacte Natura 2000 e adequação jurídica | Sobreposição geométrica observada; portais, águas e integridade ecológica desconhecidos |",
         "| PIC, REN, RAN e PDM, domínio hídrico | PIC ainda sem definição/cartografia; condicionantes municipais não verificadas ao longo de todos os corredores |",
         "","**Interpretação de túnel:** G30 «potencial_deep_tunnel» é o nome de uma hipótese de pesquisa 2D. O G32 não atribui metros de túnel, portais, cota ferroviária, volume de escavação, conformidade Natura ou efeito hidrogeológico. Não converter «perfil matemático abaixo de MDS >25m» em comprimento de túnel.",
         "","**Fontes imutáveis:** G10 GeoJSON, G30 GeoJSON e matriz, G28 recorte ICNF/MITECO com hash, Copernicus GLO30 raster original verificado por SHA256. Métodos G31/G7. Sem aquisições adicionais DGT. Sem publicação Fxx/Site.",
         "","**Gatilho da próxima decisão:** antes de escolher 3–6 faixas, medir intermodalidade, serviço e morfologia das estações em **todos os 30**, verificar viabilidade geométrica em solo nu apenas nas faixas críticas e caracterizar os efeitos de túneis no Alvão/Marão.",
         ""]
    mdout.write_text("\n".join(md))
    print("G32_RESULT",json.dumps({"n":len(rows),"by_speed":{s:Counter(r["source_family"] for r in byspeed[s]) for s in SCENARIOS},
             "horizontal_pass_3km":{s:sum(r["pass_3km"] for r in byspeed[s]) for s in SCENARIOS},
             "horizontal_pass_6km":{s:sum(r["pass_6km"] for r in byspeed[s]) for s in SCENARIOS},
             "Pareto_source_only":pareto},ensure_ascii=False,default=lambda x:dict(x)))
def main():
    p=argparse.ArgumentParser()
    for k in ("g10","g28","g30","g30geo","polygons","dsm","json","csv","markdown","scatter","map"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args()
    compute(json.loads(a.g10.read_text()),json.loads(a.g28.read_text()),
            json.loads(a.g30.read_text()),json.loads(a.g30geo.read_text()),
            json.loads(a.polygons.read_text()),a.polygons.read_bytes(),a.dsm,
            a.json,a.csv,a.markdown,a.scatter,a.map)
if __name__=="__main__":main()
