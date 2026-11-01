#!/usr/bin/env python3
"""G30: source-locked Natura-aware NEW 2km research lattice sequences; never rail track.
Distinguish environmental legal gate from hypothetical subsurface construction case.
"""
import argparse,heapq,hashlib,json,math,collections
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import shape,Point,LineString,mapping,box
from shapely.ops import transform,unary_union
from shapely.prepared import prep
from pyproj import Transformer

TO_PT=Transformer.from_crs(4326,3763,always_xy=True).transform
TO_WGS=Transformer.from_crs(3763,4326,always_xy=True).transform
CELL=2000
ANCHORS=((20000,180000),(40000,184000),(110000,234000),(116000,238000))
ROUTING=("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity")
DIRECTIONS=((2000,0),(-2000,0),(0,2000),(0,-2000),
            (2000,2000),(2000,-2000),(-2000,2000),(-2000,-2000))
def snap(x,y):
    return (int(math.floor(x/CELL))*CELL,int(math.floor(y/CELL))*CELL)
def centre(a):
    return a[0]+1000,a[1]+1000
def length(route):
    return sum(math.dist(centre(a),centre(b)) for a,b in zip(route,route[1:]))/1000
def validate(g10,g28,polys,original_bytes):
    if len(g10.get("features",[]))!=27 or len({f["properties"]["id"] for f in g10["features"]})!=27:
        raise ValueError("G10_27_verified_source_mandatory")
    if not all(f["properties"].get("this_is_not_an_approved_or_proposed_railway_alignment")
               for f in g10["features"]):raise ValueError("G10_research_only_marker")
    if g28.get("mission")!="MN-GEO-RAIL-001" or len(g28["corridor_grid_research_27"])!=27:
        raise ValueError("G28_mission_or_portfolio")
    if len(g28["city_research_circles_7"])!=7:raise ValueError("G28_city_count")
    if g28["PIC"]!="UNKNOWN_NOT_DEFINED_OFFICIAL_SPATIAL_SOURCE_REQUIRED":
        raise ValueError("PIC_must_remain_UNRESOLVED")
    if any(g28["source_receipts"][s]["status"]!="VERIFIED" for s in ("PT_ICNF","ES_MITECO")):
        raise ValueError("G28_official_source_unverified")
    if hashlib.sha256(original_bytes).hexdigest()!=g28["producer_clipped_natura_polygon_cache_sha256"]:
        raise ValueError("G28_source_polygon_SHA_not_matched")
    if len(polys.get("features",[]))!=g28["producer_clipped_natura_polygon_count"]:
        raise ValueError("G28_exact_polygon_count")
def split_source(g10):
    f=next(f for f in g10["features"] if f["properties"]["id"]=="P2-2-1")
    cells=[snap(*TO_PT(*xy)) for xy in f["geometry"]["coordinates"]]
    if len(cells)!=len(set(cells)):raise ValueError("source_grid_repeats")
    ix=[cells.index(v) for v in ANCHORS]
    if ix!=sorted(ix) or ix[0]==0 or ix[-1]==len(cells)-1:raise ValueError("anchors_out_of_order")
    parts=[cells[:ix[0]+1],cells[ix[0]:ix[1]+1],
           cells[ix[1]:ix[2]+1],cells[ix[2]:ix[3]+1],cells[ix[3]:]]
    if any(math.dist(a,b)>CELL*1.415 for part in parts for a,b in zip(part,part[1:])):
        raise ValueError("source_disconnected_grid")
    return parts
def make_nodes(a,b,old,buffer_km):
    direct=LineString([centre(a),centre(b)])
    x0,y0,x1,y1=direct.bounds
    nodes=set()
    for x in range(int(math.floor((x0-buffer_km*1000)/CELL))*CELL,
                   int(math.ceil((x1+buffer_km*1000)/CELL))*CELL+CELL,CELL):
        for y in range(int(math.floor((y0-buffer_km*1000)/CELL))*CELL,
                       int(math.ceil((y1+buffer_km*1000)/CELL))*CELL+CELL,CELL):
            node=(x,y)
            if direct.distance(Point(centre(node)))<=buffer_km*1000:
                lon,lat=TO_WGS(*centre(node))
                # Conservative interior of G28 official polygon clip bounds;
                # never obtain artificially low Natura exposure by escaping a cached source.
                if -8.70<=lon<=-5.52 and 41.07<=lat<=42.10:
                    nodes.add(node)
    nodes.update(old)
    if a not in nodes or b not in nodes:raise ValueError("missing_start_end")
    # Exclude a generous no-service investigation neighbourhood of Puebla de Sanabria.
    # This is only a research screening rule, not a legal protected polygon.
    sx,sy=TO_PT(-6.634,42.055)
    nodes={p for p in nodes if p in (a,b) or math.dist(centre(p),(sx,sy))>=15000}
    return nodes
def exposure(edge,protected,prepared):
    seg=LineString([centre(edge[0]),centre(edge[1])])
    return seg.intersection(protected).length/1000 if prepared.intersects(seg) else 0.
def route(nodes,start,end,protected,prepared,mode,repulse=frozenset(),max_steps=300000):
    """Soft *research* utility, never legal go/no-go or railway construction cost."""
    penalty={"avoid_surface_overlap":14.0,"potential_deep_tunnel":0.55,
             "geographic_diversity":3.3}[mode]
    cached={}
    best={start:0.};back={};pq=[(0.0,start)];steps=0
    while pq:
        current,a=heapq.heappop(pq)
        if current>best.get(a,float("inf"))+1e-8:continue
        if a==end:
            ans=[end]
            while ans[-1]!=start:ans.append(back[ans[-1]])
            return list(reversed(ans))
        steps+=1
        if steps>max_steps:raise ValueError("routing_search_limit")
        for dx,dy in DIRECTIONS:
            b=a[0]+dx,a[1]+dy
            if b not in nodes:continue
            # Reuse an undirected protected polygon exact segment calculation.
            edge=tuple(sorted((a,b)))
            if edge not in cached:cached[edge]=exposure(edge,protected,prepared)
            km=math.hypot(dx,dy)/1000
            diversion=5.0 if mode=="geographic_diversity" and b in repulse and b not in (start,end) else 0.0
            score=current+km+penalty*cached[edge]+diversion
            if score+1e-8<best.get(b,float("inf")):
                best[b]=score;back[b]=a;heapq.heappush(pq,(score,b))
    return None
def exposure_line(route,protected,prepared):
    return sum(exposure((a,b),protected,prepared) for a,b in zip(route,route[1:]))
def new_portfolio(g10,g28,polys,bytes_blob,report,geopath,mappath,markdown):
    validate(g10,g28,polys,bytes_blob)
    parts=split_source(g10)
    oldpaths={f["properties"]["id"]:[snap(*TO_PT(*v)) for v in f["geometry"]["coordinates"]]
              for f in g10["features"]}
    # Buffer-free polygon analysis in projected PT-TM06, valid for both countries.
    polygons=[transform(TO_PT,shape(f["geometry"])) for f in polys["features"]]
    union=unary_union(polygons)
    if not union.is_valid:raise ValueError("G28_polygon_union_invalid")
    prepared=prep(union)
    # Modules use identical compulsory city connector RESEARCH cells; no station claim.
    modes={}
    for mode in ROUTING:
        built=[];module_stats=[]
        for j,p in enumerate((parts[0],parts[2],parts[4])):
            nodes=make_nodes(p[0],p[-1],p,26.0 if mode!="potential_deep_tunnel" else 20.0)
            # Spatially repel the existing reference route in diversity mode.
            near=frozenset(v for original in oldpaths.values() for v in original)
            res=route(nodes,p[0],p[-1],union,prepared,mode,near)
            if res is None:raise ValueError("G30_source_search_failed_module_"+str(j))
            built.append(res)
            module_stats.append({"module":("AFSC_to_Vila_Real_W","Vila_Real_E_to_Braganca_W","Braganca_E_to_Zamora")[j],
                  "grid_steps":len(res),"source_line_km":round(length(res),3),
                  "natura_intersection_km_if_at_surface":round(exposure_line(res,union,prepared),3)})
        out=built[0]+parts[1][1:]+built[1][1:]+parts[3][1:]+built[2][1:]
        if len(out)!=len(set(out)):
            # A study can cross its own lattice elsewhere; suppress false viable geometry.
            module_stats.append({"warning":"source_grid_self_overlap_not_feasibility"})
        identical_to=[label for label,v in oldpaths.items() if v==out]
        if identical_to:raise ValueError("G30_alternative_duplicates_original_G10")
        overlap=exposure_line(out,union,prepared)
        modes[mode]={"route":out,"module_stats":module_stats,
             "source_2km_research_length_km":round(length(out),3),
             "natura_line_intersection_km_if_surface":round(overlap,3),
             "source_G10_max_cell_jaccard":round(max(len(set(out)&set(p))/len(set(out)|set(p)) for p in oldpaths.values()),4),
             "identical_existing_G10":False}
    if len({tuple(modes[m]["route"]) for m in ROUTING})!=len(ROUTING):
        raise ValueError("G30_modes_not_geographically_distinct")
    feats=[]
    for mode,v in modes.items():
        ln=LineString([centre(p) for p in v["route"]])
        feats.append({"type":"Feature","properties":{
            "id":"G30-"+mode,"hypothetical_construction_case":mode,
            "NOT_an_engineered_railway":True,"legal_Natura_screen":"ASSESSMENT_REQUIRED",
            "no_approved_tunnel_depth_or_portal_or_water_model":True,
            "PIC_status":"UNKNOWN_OFFICIAL_SOURCE",
            "research_grid_2km_NOT_buildable_alignment":True},
            "geometry":mapping(transform(TO_WGS,ln))})
    geopath.write_text(json.dumps({"type":"FeatureCollection","features":feats},ensure_ascii=False)+"\n")
    present={}
    for k,v in modes.items():present[k]={kk:vv for kk,vv in v.items() if kk!="route"}
    obj={"mission":"MN-GEO-RAIL-001","stage":"G30_new_Natura_legal_gate_tunnel_hypothesis_diversification",
         "source_G28_polygon_cache_sha256":hashlib.sha256(bytes_blob).hexdigest(),
         "G10_reference":"P2-2-1","original_G10_portfolio":27,
         "number_new_independent_search_scenarios":len(modes),
         "research_route_modes":present,"mandatory_grid_connectors_preserved":True,
         "Vila_Real_Braganca_service_not_physically_verified":True,
         "Sanabria_station_excluded":True,"surface_Natura_overlap_not_impacts":True,
         "deep_tunnel_is_only_hypothesis_no_verified_3D_alignment":True,
         "legally_appropriate_assessment_required_if_significant_effects":True,
         "no_tunnel_depth_portals_hydrogeology_geotech_rail_radius_station_cost_or_timetable":True,
         "PIC_UNRESOLVED":True,"additional_DGT_tiles":0,
         "Fxx_accepted":False,"Site_authorized":False}
    report.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
    fig,ax=plt.subplots(figsize=(12.5,8.0),layout="constrained")
    for geo in polygons:
        small=geo.simplify(170,preserve_topology=True)
        for poly in (small.geoms if small.geom_type=="MultiPolygon" else [small]):
            if poly.geom_type=="Polygon" and not poly.is_empty:
                x,y=poly.exterior.xy
                ax.fill([i/1000 for i in x],[i/1000 for i in y],color="#b3a37d",alpha=.29,lw=0)
    base=LineString([centre(p) for p in oldpaths["P2-2-1"]])
    x,y=base.xy;ax.plot([z/1000 for z in x],[z/1000 for z in y],ls="--",c="#929292",lw=1.4,label="G10 P2-2-1 referência")
    colors=("#c35f31","#277e70","#405bbb")
    for mode,color in zip(ROUTING,colors):
        ln=LineString([centre(p) for p in modes[mode]["route"]])
        x,y=ln.xy;ax.plot([z/1000 for z in x],[z/1000 for z in y],lw=2,color=color,label="G30 "+mode)
    for name,pos in (("AFSC",oldpaths["P2-2-1"][0]),("Vila Real (zona)",ANCHORS[0]),
                     ("Bragança (zona)",ANCHORS[2]),("Zamora",oldpaths["P2-2-1"][-1])):
        x,y=centre(pos)
        ax.scatter([x/1000],[y/1000],s=19,c="#1d304a",zorder=5)
        ax.annotate(name,(x/1000,y/1000),xytext=(5,5),textcoords="offset points",fontsize=8,
                    bbox=dict(facecolor="white",alpha=.7,edgecolor="none"))
    ax.set_aspect("equal",adjustable="datalim")
    ax.set_xlabel("PT-TM06 EPSG:3763, E (km)");ax.set_ylabel("N (km)")
    ax.set_title("G30 · novas cadeias de investigação 2 km; Natura 2000 PT+ES",loc="left")
    ax.legend(loc="upper left",fontsize=8);ax.grid(alpha=.12)
    fig.savefig(mappath,dpi=160,bbox_inches="tight");plt.close(fig)
    lines=["# G30 · Novas cadeias espaciais, hipótese de túnel, portão Natura",
       "","Três novas cadeias de investigação em malha 2 km produzidas sobre os polígonos oficiais cache G28 e a geometria G10. Não são geometrias ferroviárias aprovadas, nem projetos de túnel.",
       "","**Diretiva Habitats artigo 6.º, n.os 3/4**: avaliar efeitos nos objetivos de conservação; passagem subterrânea pode reduzir ocupação superficial, mas não há dispensa por túnel. Para a ZEC Alvão/Marão: DL 28/2025 artigo 5.º e Portaria 135/2025/1.",
       "","| Nova hipótese | Comprimento linha-grelha (km) | Interseção de linha com Natura se superfície (km) | Semelhança máx. Jaccard com G10 |",
       "|---|---:|---:|---:|"]
    for mode,v in modes.items():
        lines.append(f"| {mode} | {v['source_2km_research_length_km']} | {v['natura_line_intersection_km_if_surface']} | {v['source_G10_max_cell_jaccard']} |")
    lines+=["","Os coeficientes de penalização da busca são **heurísticos de exploração** e não fatores monetários, jurídicos ou de impacte ecológico. O cenário potencial_deep_tunnel não demonstra uma passagem em túnel: não existem eixo 3D, cota, geologia, perfil de gradientes, portais ou modelação de águas subterrâneas. **NÃO atribuir km de túnel ou autorização**.",
       "","A malha exploratória preserva as duas ligações urbanas G10, mas NÃO prova serviço ferroviário a Vila Real/Bragança nem acesso rodoviário às estações. As velocidades 160/200/250 km/h continuam cenários de ensaio a avaliar em engenharia; não foram determinadas nesta execução. PIC mantém restrição maior não cartografada.",
       "","Para converter estes resultados em escolha: 1) cenários geométricos 160/200/250 com perfis DSM/MDT; 2) análise hidrogeológica Alvão/Marão e delimitação precisa de portais/poços; 3) acesso rodoviário BGRI/OSRM e ocupação COS; 4) custos de túnel/viaduto com incerteza; 5) avaliação apropriada Natura + PIC esclarecido antes de selecionar e adquirir novas quadrículas DGT.","",
       "Fontes: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=oj%3AJOC_2021_437_R ; https://diariodarepublica.pt/dr/detalhe/decreto-lei/28-2025-911648874 ; https://diariodarepublica.pt/dr/detalhe/portaria/135-2025-912820664 ; G28 fontes ICNF + MITECO e G10.", ""]
    markdown.write_text("\n".join(lines))
    print("G30",json.dumps({"new":len(modes),"scenarios":present},ensure_ascii=False))
def main():
    p=argparse.ArgumentParser()
    for k in ("g10","g28","polygons","json","geojson","map","markdown"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args();blob=a.polygons.read_bytes()
    new_portfolio(json.loads(a.g10.read_text()),json.loads(a.g28.read_text()),
                  json.loads(blob),blob,a.json,a.geojson,a.map,a.markdown)
if __name__=="__main__":main()
