#!/usr/bin/env python3
"""G29 research-only source map and 2km environmental conflict cells.
Not a new physical railway and not an environmental authorization.
"""
import argparse,collections,hashlib,json,math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import shape,LineString,Point,MultiPolygon
from shapely.ops import transform,unary_union
from shapely.prepared import prep
from pyproj import Transformer
TRANS=Transformer.from_crs(4326,3035,always_xy=True).transform
SELECT=('P2-2-1','P1-2-1','P2-2-3')
COLORS={'P2-2-1':'#08755b','P1-2-1':'#3264aa','P2-2-3':'#bd532e'}
CITY=[('AFSC',-8.678056,41.235556),('Vila Real',-7.744,41.3006),
      ('Bragança',-6.7576,41.806),('Zamora',-5.746992,41.50378)]
def validate(g10,g28,natura,natura_bytes):
    if (g10.get('type')!='FeatureCollection' or len(g10.get('features',[]))!=27
        or len({f['properties']['id'] for f in g10['features']})!=27):
        raise ValueError('G10 source 27 path contract')
    if not all(f['properties'].get('this_is_not_an_approved_or_proposed_railway_alignment')
               for f in g10['features']):raise ValueError('G10 geometry not verified')
    if not(g28.get('mission')=='MN-GEO-RAIL-001'
       and len(g28['corridor_grid_research_27'])==27
       and len(g28['city_research_circles_7'])==7
       and all(g28['source_receipts'][p]['status']=='VERIFIED' for p in ('PT_ICNF','ES_MITECO'))
       and g28['PIC'].startswith('UNKNOWN')):
        raise ValueError('G28 source verified PIC unresolved contract')
    if hashlib.sha256(natura_bytes).hexdigest()!=g28['producer_clipped_natura_polygon_cache_sha256']:
        raise ValueError('G28 exact geometries do not match source receipt')
    if len(natura['features'])!=g28['producer_clipped_natura_polygon_count']:
        raise ValueError('G28 polygon count mismatch')
def plot_shapely(ax,geometry,fc):
    geoms=list(geometry.geoms) if geometry.geom_type=='MultiPolygon' else [geometry]
    for p in geoms:
        if p.is_empty or p.geom_type!='Polygon':continue
        p=p.simplify(125,preserve_topology=True) # preview only; analysis uses full originals
        x,y=p.exterior.xy
        ax.fill([z/1000 for z in x],[z/1000 for z in y],facecolor=fc,edgecolor='none',alpha=.28)
def annot_cities(ax):
    for city,lon,lat in CITY:
        x,y=TRANS(lon,lat);ax.scatter([x/1000],[y/1000],s=27,c='#172d43',zorder=6)
        ax.annotate(city,(x/1000,y/1000),xytext=(6,6),textcoords='offset points',fontsize=9,
                    color='#14283e',bbox=dict(facecolor='white',alpha=.7,edgecolor='none'))
def draw(inputs,report,geo,geo_path,map_path,hot_path,md_path,json_path):
    validate(inputs,report,geo,geo_path.read_bytes())
    poly={}
    for producer in ('PT_ICNF','ES_MITECO'):
        poly[producer]=[transform(TRANS,shape(f['geometry'])) for f in geo['features']
                        if f['properties']['source']==producer]
    full=unary_union(poly['PT_ICNF']+poly['ES_MITECO'])
    if not full.is_valid:raise ValueError('invalid original protected polygon union')
    prepared=prep(full)
    lines={f['properties']['id']:transform(TRANS,shape(f['geometry'])) for f in inputs['features']}
    # Risk-segment cell counts across options, not land parcels or a rail construction strip.
    cells=collections.defaultdict(set)
    for key,line in lines.items():
        pts=list(line.coords)
        for p,q in zip(pts,pts[1:]):
            piece=LineString([p,q])
            if not prepared.intersects(piece):continue
            # Segment midpoint cell is an index, not the actual polygon crossing location.
            mid=piece.interpolate(.5,normalized=True)
            cell=(int(math.floor(mid.x/2000)),int(math.floor(mid.y/2000)))
            cells[cell].add(key)
    common=[cell for cell,ids in cells.items() if len(ids)==27]
    rows=[]
    g28by={r['id']:r for r in report['corridor_grid_research_27']}
    for key,line in lines.items():
        j=g28by[key]
        pt,es=j['PT']['line_overlap_km'],j['ES']['line_overlap_km']
        assert pt is not None and es is not None
        rows.append({'option':key,'research_source_line_km_NOT_track':round(line.length/1000,3),
                     'protected_PT_km':pt,'protected_ES_km':es,
                     'protected_sum_two_countries_km':round(pt+es,3),
                     'Natura_study_centerline_exposure_not_impact':True})
    rows.sort(key=lambda r:(r['protected_sum_two_countries_km'],r['research_source_line_km_NOT_track']))
    fig,ax=plt.subplots(figsize=(12.8,8.4),layout='constrained')
    for country,color in [('PT_ICNF','#bc9954'),('ES_MITECO','#a88c5f')]:
        for p in poly[country]:plot_shapely(ax,p,color)
    for key,line in lines.items():
        if key in SELECT:continue
        x,y=line.xy;ax.plot([v/1000 for v in x],[v/1000 for v in y],c='#738396',alpha=.25,lw=.6)
    for key in SELECT:
        line=lines[key];x,y=line.xy
        ax.plot([v/1000 for v in x],[v/1000 for v in y],c=COLORS[key],lw=2.5,
                zorder=5,label=f'{key} · G10 estudo')
    annot_cities(ax);ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.12)
    ax.set_xlabel('ETRS89-LAEA EPSG:3035 · Este (km)')
    ax.set_ylabel('ETRS89-LAEA EPSG:3035 · Norte (km)')
    ax.set_title('Rede Natura 2000 PT/ES e 27 alternativas geográficas de investigação',loc='left',fontsize=15)
    ax.legend(loc='upper left',fontsize=9)
    map_path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(map_path,dpi=170,bbox_inches='tight');plt.close(fig)
    fig,ax=plt.subplots(figsize=(12.8,8.4),layout='constrained')
    for country,color in [('PT_ICNF','#aa9a78'),('ES_MITECO','#a6a08e')]:
        for p in poly[country]:plot_shapely(ax,p,color)
    for key,line in lines.items():
        x,y=line.xy;ax.plot([v/1000 for v in x],[v/1000 for v in y],c='#8b99aa',alpha=.10,lw=.55)
    if cells:
        x=[(p[0]+.5)*2 for p in cells];y=[(p[1]+.5)*2 for p in cells]
        weight=[len(s) for s in cells.values()]
        sc=ax.scatter(x,y,c=weight,cmap='plasma',s=20,marker='s',vmin=1,vmax=27,zorder=4)
        fig.colorbar(sc,ax=ax,label='N.º de alternativas G10 com segmento potencialmente exposto no bloco de investigação')
    annot_cities(ax);ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.12)
    ax.set_title('Zonas de conflito Natura observadas nas alternativas G10 · índice por célula 2 km',loc='left',fontsize=14)
    ax.set_xlabel('ETRS89-LAEA EPSG:3035 · Este (km)')
    ax.set_ylabel('ETRS89-LAEA EPSG:3035 · Norte (km)')
    fig.savefig(hot_path,dpi=170,bbox_inches='tight');plt.close(fig)
    out={'mission':'MN-GEO-RAIL-001','stage':'G29_G28_reuse_Natura2km_conflict_visual_first_prediversification',
         'G28_original_polygon_sha256':hashlib.sha256(geo_path.read_bytes()).hexdigest(),
         'G10_original_source_27_paths':len(lines),'natura_geometry_polygons':len(geo['features']),
         'conflict_2km_study_midpoint_grid_cells':len(cells),'common_conflict_cells_in_all_27':len(common),
         'ranked_27_research_line_Natura_overlaps_NOT_rail_or_impact':rows,
         'selected_three_families':list(SELECT),'all_require_PIC_source':True,
         'source_grid_does_not_show_legal_land_or_suitable_railway':True,
         'new_alignment_families_generated':False,'next_decision':'G30 explore geographically new Natura avoiding study corridors with DSM/road and physical rail constraints',
         'no_G29_DGT_or_MITECO_download':True,'no_Fxx_or_Site':True}
    json_path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    text=['# G29 — Padrão geográfico dos conflitos e necessidade de diversificação',
      '','Reutiliza G28 (ICNF + MITECO oficiais recortados) e as 27 cadeias G10, sem nova descarga nacional ou MDT.',
      '','| Indicador | Resultado |','|---|---:|',
      f'| Alternativas G10 com Natura em PT e ES | {len(lines)} / {len(lines)} |',
      f'| Células 2 km de conflito com segmento de alguma alternativa | {len(cells)} |',
      f'| Células de conflito comuns às 27 | {len(common)} |',
      '','| Variante G10 | Comprimento linha (km) | Natura PT (km) | Natura ES (km) | Soma PT+ES (km) |',
      '|---|---:|---:|---:|---:|']
    for r in rows:
        text.append(f"| {r['option']} | {r['research_source_line_km_NOT_track']} | {r['protected_PT_km']} | {r['protected_ES_km']} | {r['protected_sum_two_countries_km']} |")
    text+=['','**Soma PT+ES** é extensão de linhas geográficas em polígonos, não impacto ecológico, custo, ilegalidade, prioridade oficial nem traçado ferroviário.',
           'As 27 alternativas partilham segmentos geográficos: a contagem de conflitos comuns permite identificar onde alterar primeiro a carteira, **não** quais novas linhas serão construíveis.',
           'PIC permanece bloqueio maior de fonte, definição e cartografia. O próximo G30 deve diversificar verdadeiramente o espaço de procura, preservando Vila Real e Bragança obrigatórias e Sanábria excluída, antes das novas aquisições de MDT DGT2m.',
           'Os mapas utilizam polígonos simplificados apenas para renderização, mas a análise usa o original sem simplificação. Sem Fxx/Site.']
    md_path.write_text('\n'.join(text)+'\n')
    print('G29=',json.dumps({'G10':len(lines),'common_27_cells':len(common),'exposed_cells':len(cells),'top5':rows[:5]},ensure_ascii=False))
def main():
    p=argparse.ArgumentParser()
    for name in ('g10','g28','polygons','map','hotspot','markdown','json'):
        p.add_argument('--'+name,type=Path,required=True)
    q=p.parse_args()
    draw(json.loads(q.g10.read_text()),json.loads(q.g28.read_text()),
         json.loads(q.polygons.read_text()),q.polygons,q.map,q.hotspot,q.markdown,q.json)
if __name__=='__main__':main()
