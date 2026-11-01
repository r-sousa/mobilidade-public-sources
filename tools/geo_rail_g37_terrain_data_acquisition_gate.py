#!/usr/bin/env python3
"""G37 targeted DGT source gap and phased genuine rail design data requirements.

All 30 existing G10+G30 study lines retained. First engineering review candidate
family 13 from G36, but NO new original DGT2m order from grid-center polylines.
Original 84 1km DGT ground tiles retained, plus 7 already studied station
positions with exact G26B native grid accounting. PT-only research corridor
bounds from Eurostat/GISCO 2024 1:1m geographical border (approximate).
GISCO source used only for preliminary country partition, not treaty boundary,
and source lines never railway alignments. No fabricated tunnels / cost/ETA.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sys
from collections import defaultdict
from pathlib import Path
from shapely.geometry import shape,LineString,Point,box,mapping
from shapely.ops import transform as geomtransform,unary_union
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g26b_next_DGT2m_study_footprint_gate import (
    native_grid_old,existing_tiles,indices,build as build_previous_site)
from geo_rail_g26b_next_DGT2m_study_footprint_gate import G20_SHA,G21_SHA,G25_SHA
TO_PT=Transformer.from_crs(4326,3763,always_xy=True).transform
GISCO_URL="https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_01M_2024_4326_LEVL_0.geojson"
MAX_GISCO_BOUNDARY_BYTES=15_000_000
MARGIN=(250,500)
def read(path):return json.loads(path.read_bytes())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def source_boundary(blob):
    if len(blob)>MAX_GISCO_BOUNDARY_BYTES or len(blob)<100:
        raise ValueError("G37_GISCO_boundary_size_gate")
    doc=json.loads(blob)
    feats=doc.get("features",[])
    portugal=[x for x in feats if (x.get("properties",{}).get("CNTR_ID") or x.get("properties",{}).get("NUTS_ID") or x.get("properties",{}).get("CNTR_CODE"))=="PT"]
    spain=[x for x in feats if (x.get("properties",{}).get("CNTR_ID") or x.get("properties",{}).get("NUTS_ID") or x.get("properties",{}).get("CNTR_CODE"))=="ES"]
    if len(portugal)!=1 or len(spain)!=1:raise ValueError("G37_official_GISCO_PT_ES_codes_missing")
    # Select the mainland polygon only, avoiding islands/autonomous regions.
    pt=geomtransform(TO_PT,shape(portugal[0]["geometry"]))
    es=geomtransform(TO_PT,shape(spain[0]["geometry"]))
    if pt.geom_type=="MultiPolygon":
        pt=max(pt.geoms,key=lambda p:p.area)
    if es.geom_type=="MultiPolygon":
        es=max(es.geoms,key=lambda p:p.area)
    if not pt.is_valid or not es.is_valid:raise ValueError("G37_GISCO_2024_invalid_country_polygon")
    return pt,es,{"source":"Eurostat GISCO NUTS0 2024 01M generalized NUTS_RG_01M_2024_4326_LEVL_0",
       "original_producer_url":GISCO_URL,
       "raw_full_geojson_sha256":hashlib.sha256(blob).hexdigest(),
       "regional_boundary_scale":"1:1,000,000; GENERALIZED, NOT precise jurisdiction/tile availability",
       "PT_ES_approx_partition_only":True,
       "PT_polygon_area_km2_in_projected_CRS":round(pt.area/1e6)}
def test_qa(g10,g30,g36,g20,g21,g25):
    originals=g10.get("features",[]);new=g30.get("features",[])
    expect={"P"+str(a)+"-"+str(b)+"-"+str(c) for a in (1,2,3) for b in (1,2,3) for c in (1,2,3)}
    if {x["properties"]["id"] for x in originals}!=expect or len(originals)!=27:
        raise ValueError("G37_must_preserve_G10_27")
    expectnew={"G30-"+z for z in ("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity")}
    if {x["properties"]["id"] for x in new}!=expectnew or len(new)!=3:
        raise ValueError("G37_must_preserve_G30_3")
    if g36.get("source_all_original_G10_count")!=27 or g36.get("source_all_original_G30_count")!=3 or g36.get("rows_n")!=90:
        raise ValueError("G37_requires_G36_all30_complete")
    if g36.get("PIC_still_UNRESOLVED_official_source")!=True or not g36.get("no_actual_rail_timings_or_EUR_CAPEX_or_tunnel_quantities"):
        raise ValueError("G37_no_approval_or_fake_cost")
    priority={x["option_id"] for x in g36["review_priority_NOT_viability_OR_final_selection"] if x["next_engineering_work_priority_only"]}
    if len(priority)!=13 or "G30-potential_deep_tunnel" not in priority:
        raise ValueError("G37_research13_must_include_tunnel_sensitivity")
    if digest(g20)!=G20_SHA or digest(g21)!=G21_SHA or digest(g25)!=G25_SHA:
        raise ValueError("G37_original_DGT_G25_G20_G21_hash_drift")
    return originals+new,priority
def tile_references_for_buffer(lines,region,halfwidth):
    """Per-segment grid enumeration; avoids brute-force 300km x 100km bbox."""
    multi=(list(lines.geoms) if lines.geom_type=="MultiLineString" else [lines])
    candidates=set()
    for geom in multi:
        coords=list(geom.coords)
        for aa,bb in zip(coords[:-1],coords[1:]):
            xmin=math.floor((min(aa[0],bb[0])-halfwidth-2)/1000)
            xmax=math.ceil((max(aa[0],bb[0])+halfwidth+2)/1000)
            ymin=math.floor((min(aa[1],bb[1])-halfwidth-2)/1000)
            ymax=math.ceil((max(aa[1],bb[1])+halfwidth+2)/1000)
            if (xmax-xmin)*(ymax-ymin)>140:
                raise ValueError("G37_source_segment_not_local_2km_grid")
            candidates.update((col+200,row+301) for col in range(xmin,xmax) for row in range(ymin,ymax))
    return {p for p in candidates if region.intersects(box((p[0]-200)*1000,(p[1]-301)*1000,
                                          (p[0]-199)*1000,(p[1]-300)*1000))}
def tile_rows(routes,priority,covered,pt,es,meta):
    rows=[];tilecache={};ptbands={250:[],500:[]}
    for feature in routes:
        id=feature["properties"]["id"]
        line=geomtransform(TO_PT,shape(feature["geometry"]))
        if not isinstance(line,LineString) or line.length<150000:raise ValueError("G37_invalid_source_line")
        # clip BEFORE buffering and reclip, not DGT data requests into Spain.
        ptline=line.intersection(pt)
        esline=line.intersection(es)
        if ptline.length<100000 or esline.length<10000:
            raise ValueError("G37_source_line_country_partition_implausible_"+id)
        origgrid_km=round(line.length/1000,2)
        for halfwidth in MARGIN:
            domain=ptline.buffer(halfwidth,cap_style=2,join_style=2).intersection(pt)
            if not domain.is_valid or domain.is_empty:raise ValueError("G37_no_PT_corridor_domain")
            # project generalized GISCO border; use native DGT index formula.
            ids=tile_references_for_buffer(ptline,domain,halfwidth)
            existing=ids&covered
            missing=ids-covered
            # tiles adjacent to generalized border require precise later validation.
            # Count tiles intersecting the approximated international border.
            border=pt.boundary.intersection(box(*domain.bounds).buffer(1500))
            approximate={p for p in ids if border.distance(Point((p[0]-200+.5)*1000,(p[1]-301+.5)*1000))<1500}
            row={
              "option_id":id,"family":"G30" if id.startswith("G30-") else "G10",
              "G36_selected_for_next_engineering_research":id in priority,
              "hypothetical_2D_grid_research_halfwidth_m":halfwidth,
              "entire_current_study_grid_length_km":origgrid_km,
              "Portugal_generalized_GISCO_grid_length_km":round(ptline.length/1000,2),
              "Spain_generalized_GISCO_grid_length_km":round(esline.length/1000,2),
              "Portugal_study_band_candidate_source_1km_DGT_tile_ids":len(ids),
              "original_84_DGT2m_tile_ids_intersecting_rough_PT_band":len(existing),
              "gap_candidate_1km_DGT_source_ids_IF_this_exact_buffer_were_approved":len(missing),
              "generalized_border_neighbor_cells_1p5km_uncertain":len(approximate),
              "not_tender_quantity_or_acquisition_order":True,
              "only_G10_G30_2km_grid_centerlines_not_engineered_axis":True,
              "Spain_CNIG_terrain_needed_separately":True,
              "GISCO_1M_country_border_not_a_precise_legal_boundary":True,
              "source_pixels_NoData_not_included_in_tile_count_coverage":True}
            rows.append(row)
            tilecache[(id,halfwidth)]=ids
            if id in priority:ptbands[halfwidth].append(ids)
    if len(rows)!=60:raise ValueError("G37_30x2_coverage_required")
    union={}
    for width,bands in ptbands.items():
        ids=set().union(*bands)
        union[str(width)]={"study_line_source_buffer_halfwidth_m":width,
          "priority_research_lines":len(bands),
          "distinct_approx_PT_1km_source_tile_ids_intersecting_union":len(ids),
          "already_covered_1km_DGT2m_tile_ids_in_union":len(ids&covered),
          "additional_1km_tile_ids_if_entire_unapproved_grid_buffer_were_acquired":len(ids-covered),
          "not_actionable_acquisition_request":True}
    return rows,union
def execute(g10,g30,g36,g20file,g21file,g25file,b1,grid12,one,countryraw,outjson,outcsv,outmd,outgaps):
    original,priority=test_qa(g10,g30,g36,g20file,g21file,g25file)
    g20=read(g20file);g21=read(g21file);g25=read(g25file)
    pt,es,meta=source_boundary(countryraw)
    old=native_grid_old(read(b1),read(grid12),read(one))
    covered=existing_tiles(old,g20,g21)
    if len(covered)!=84:raise ValueError("G37_original_84_not_preserved")
    # Reuse actual older station approach conditional acquisition gate exactly.
    previous=build_previous_site(g25,g20,g21,read(b1),read(grid12),read(one))
    if previous["total_distinct_original_DGT2m_1km_source_tiles_preserved"]!=84:
        raise ValueError("G37_site_previous_source_count_changed")
    route_rows,union=tile_rows(original,priority,covered,pt,es,meta)
    stage_approach=previous["conditional_1p5_3_6km_screen_union_gap_summary"]
    if len(stage_approach)!=3:raise ValueError("G37_no_prior_3approach_research_envelopes")
    # Official DGT tile ordering would require: actual selected centerline and
    # high-accuracy administrative map, exact native producer tile URLs and
    # current availability/NoData checking. This is ONLY conditional budgeting.
    out={
      "mission":"MN-GEO-RAIL-001","stage":"G37_existing_original_DGT2m_vs_30_research_routes_13_prioritized_acquisition_gates",
      "source_all_G10":27,"source_all_G30":3,"all_30_route_alt_preserved":True,
      "prioritized_for_future_3D_railway_investigation_not_track_selection":sorted(priority),
      "G36_high_priority_research_options":len(priority),
      "source_original_DGT2m_preserved_1km_tiles":84,
      "source_original_DGT2m_ground_nominal_area_km2":84,
      "source_existing_ground_NoData_not_imputed":True,
      "GISCO_geometry_2024_provenance":meta,
      "GISCO_country_polygon_generalized_do_not_issue_exact_border_tiles":True,
      "conditional_source_halfwidths_m":list(MARGIN),
      "all30_perwidth_country_research_envelope_gaps":route_rows,
      "approx_country_partitioned_13_prioritized_study_envelope_union":union,
      "G26B_previous_seven_station_original_DGT_1p5_3_6km_contexts":stage_approach,
      "priority_next_data":"DGT_MDT10m_narrow_realistic_approaches_first_IGN_CNIG_MDT25_Spain_LNEG_hydrogeo",
      "DGT_MDT10m_coverage_not_yet_verified_or_acquired":True,
      "Spain_IGN_CNIG_MDT25_needs_targeted_download_and_vertical_datum_harmonization":True,
      "LNEG_geology_and_hydrogeology_screen_official_services_need_clip":True,
      "tunnel_portal_faults_groundwater_levels_rock_quality_boreholes_not_yet_available":True,
      "COS2025_G27C_official_REN_RAN_WFS_not_final_statutory_PDM":True,
      "Natura_ICNF_MITECO_must_still_review_habitats_and_portal_water":True,
      "PIC_official_definition_and_boundary_UNRESOLVED":True,
      "no_approved_railway_alignment_or_fitted_clothoid_vertical_curve":True,
      "no_actual_tunnel_viaduct_quantities_cost_time_or_CBA":True,
      "original_source_large_bulk_acquisition_performed":False,
      "GISCO_country_boundary_small_metadata_retrieved":True,
      "new_DGT_2m_tiles":0,"no_Fxx_or_site":True}
    outjson.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    with outcsv.open("w",newline="",encoding="utf-8-sig") as h:
        keys=list(route_rows[0]);w=csv.DictWriter(h,fieldnames=keys,delimiter=";");w.writeheader();w.writerows(route_rows)
    gapdoc={"mission":"MN-GEO-RAIL-001","stage":"G37_no_download_future_DGT2m_candidate_tile_ID_index",
         "source_84_original_DGT_tile_ids_in_PTTM06":[list(p) for p in sorted(covered)],
         "tile_index_offset_original_DGT":[200,301],
         "tile_pixel_resolution_m":2,"tile_footprint_m":1000,
         "all30_source_corridor_250_and_500m_only_summary_not_full_download_list":route_rows,
         "priority_gaps_are_approx_only_from_GISCO_1M_country":True,
         "first_bulk_acquisition_should_be_small_DGT_MDT10m_clip_to_REAL_3D_alignment_bands":True,
         "no_new_DGT_2m_tile_order":True}
    outgaps.write_text(json.dumps(gapdoc,ensure_ascii=False,indent=2)+"\n")
    md=["# G37 — Aquisição de dados para desenho ferroviário: auditoria de cobertura e plano faseado",
      "","## Decisão operacional",
      "**Sim, é necessária aquisição adicional de MDT de solo nu contínuo, geologia/hidrogeologia e cartografia espanhola antes de projetar o perfil 3D ferroviário. Não é necessária nem razoável a descarga integral e antecipada de MDT2m para os 30 eixos de malha.**",
      "","Dados existentes verificados: 27 G10 + 3 G30, 13 opções priorizadas para investigação pelo G36; 84 GeoTIFF DGT2m de 1×1km verificados (45 antigos +39 G21), 7 sítios de estação G23–G27, topografia de superfície Copernicus GLO30 para a região e cartografia Natura 2000 PT/ES G28. Nenhum dos eixos atuais é alinhamento ferroviário projetado.",
      "","## Etapa 0 — Prioridade a serviço e geometria (sem descarregar quadrículas agora)",
      "Reusar as sete posições de estudo anteriores com os 29 contextos localizados de orientação e acesso. Definir 2–3 modos de aproximação ferroviária por nó obrigatório (Vila Real, Bragança); identificar diversificação de serviço para Guimarães, Amarante, Mirandela e Macedo de Cavaleiros; delimitar faixas de 3D com curvatura/gradiente. Manter as 30 alternativas comparadas. A distinção geográfica é necessária, visto que módulos obrigatórios de estação são atualmente comuns por construção.",
      "","## Etapa 1 — Adquirir terreno de solo nu de dimensão gerível (próxima ação)",
      "1. **DGT MDT10 m original** em faixas estreitas PT de investigação melhor delineadas, priorizando Marão–Alvão e segmentos de aproximação. Confirmar previamente disponibilidade real da resolução 10m e origem, dado que o acervo anterior só verifica concretamente os MDT2m locais. Se só houver MDT2m, pedir poucos ficheiros 1×1km nas zonas de maior incerteza geométrica. Usar credenciais DGT no GitHub secret; guardar a fonte em releases imutáveis, os hashes e os dados derivados, não exigir transferência manual.",
      "2. **CNIG/IGN MDT25 Espanha**, usar para primeira triangulação contínua dos perfis até Zamora e MDT02/MDT05 somente nos segmentos de maior conflito. Verificar sistema vertical espanhol e transformação para o sistema do MDT português.",
      "3. **LNEG 1:50 000 cartografia geológica** e **1:200 000 hidrogeológica** em recortes finitos perto dos locais onde são previstos túneis; verificar cobertura, falhas, nascentes, recursos hídricos, áreas de recarga e habitats dependentes da água. Isto não substitui levantamento geotécnico.",
      "4. Verificar PDM e mapas legais atuais de REN/RAN, domínio hídrico e sistemas de condicionantes; **PIC mantém estatuto não definido** e nenhuma alternativa recebe classificação ambiental positiva.",
      "","## Etapa 2 — Necessidades condicionais de MDT2m",
      "O cálculo GISCO NUTS_RG_01M_2024 aproxima a repartição Portugal/Espanha apenas na escala **1:1 000 000**. Cada conjunto abaixo é uma *faixa arbitrária sobre o centro da grelha 2km* (não eixo de ferrovia), cujo número de quadrículas não é pedido de download. As quadrículas de fronteira exigem mapa mais rigoroso. O resultado identifica ordem de grandeza e mostra que tentar obter toda a cobertura de MDT2m seria desproporcionado.",
      "","| Envelope da shortlist G36 de 13 alternativas | Quadrículas DGT 1km no PT aprox. | Intersetadas com as 84 antigas | Novas se descarregássemos todo o envelope (NÃO REQUISITAR) |",
      "|---|---:|---:|---:|"]
    for width in MARGIN:
        u=union[str(width)]
        md.append(f"| ±{width} m ao eixo de malha 2km | {u['distinct_approx_PT_1km_source_tile_ids_intersecting_union']} | {u['already_covered_1km_DGT2m_tile_ids_in_union']} | {u['additional_1km_tile_ids_if_entire_unapproved_grid_buffer_were_acquired']} |")
    md+=["","## Etapa 2A — Sete sítios históricos de estação: expansão condicional (G26B)",
     "","| Meia extensão de aproximação hipotética | Meia largura | Quadrículas 1km requeridas (todas orientações) | Já arquivadas na envolvente | Falta potencial |",
     "|---|---:|---:|---:|---:|"]
    for q in stage_approach:
        md.append(f"| ±{q['hypothetical_source_approach_half_length_m']/1000:g} km | {q['hypothetical_study_envelope_half_width_m']}m | {q['distinct_required_original_1km_DGT2m_tiles_across_ALL_study_directions']} | {q['distinct_already_preserved_1km_DGT2m_tiles']} | {q['distinct_gap_1km_original_DGT2m_tiles_IF_ALL_ORIENTATIONS_STUDIED']} |")
    md+=["","## O que fica por validar antes de qualquer custo ou tempo",
      "- Clotóides, raios de transição e superelevação, pendentes de geometria ferroviária horizontal contínua; gradientes com rasantes e curvas verticais; velocidade diferenciada por troço e acessos a estações.",
      "- Luz, profundidade, portais, poços, geotecnia do maciço, falhas, hidrologia e hidrogeologia subterrânea no atravessamento Marão–Alvão e em outros setores; túneis não são isenção Natura.",
      "- Obras de arte e movimento de terras, cotas de aterro/escavação, custo e cronograma com preços unitários verificáveis; ainda não se estimam quilómetros de túnel ou custos.",
      "- Precisas localizações de estação e entrada legal de passageiros/estrada, operação ferroviária e intermodalidade, serviço a Guimarães/Amarante/Mirandela/Macedo.",
      "- Regras de operação ibéricas, tecnologias de eletrificação, mercadorias/passageiros, necessidades de ligação transfronteiriça, licença ambiental, titularidade.",
      "","## Fontes oficiais já identificadas",
      "- DGT cartografia digital: https://www.dgterritorio.gov.pt/atividades/cartografia/cartografia-topografica/modelos-digitais",
      "- CNIG/IGN MDT25/MDT02: https://centrodedescargas.cnig.es/CentroDescargas/modelos-digitales-elevaciones",
      "- LNEG geologia/hidrogeologia: https://geoportal.lneg.pt/pt/dados_abertos/servicosdados/",
      "- GISCO 2024 fronteiras administrativas generalizadas: "+GISCO_URL,
      "","**G37 não descarrega MDT2m adicional, MDT10m, CNIG nem mapas geológicos em bruto nesta execução; apenas usa limite administrativo GISCO de pequeno volume.** Os valores acima são triagem da aquisição, não geometria ferroviária, título jurídico ou orçamento. Não enviar Fxx/Site.",""]
    outmd.write_text("\n".join(md))
    print("G37_RESULTS",json.dumps({"prioritized_routes":len(priority),"all_routes":30,
       "PT_13_study_band_unions":union,"station_original_source_gaps":stage_approach,
       "old_tiles":len(covered),"border":"GENERALIZED","no_bulk_DGT":True},ensure_ascii=False))
def main():
    a=argparse.ArgumentParser()
    for key in ("g10","g30","g36","g20","g21","g25","b1","grid12","tile279503","country","json","csv","markdown","gaps"):
        a.add_argument("--"+key,required=True,type=Path)
    q=a.parse_args()
    execute(read(q.g10),read(q.g30),read(q.g36),q.g20,q.g21,q.g25,
            q.b1,q.grid12,q.tile279503,q.country.read_bytes(),
            q.json,q.csv,q.markdown,q.gaps)
if __name__=="__main__":main()
