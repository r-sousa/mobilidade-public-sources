#!/usr/bin/env python3
"""Characterize G3 exploratory source lattice paths against G4 original DGT 2m coverage.

Read-only publicly archived SHA-pinned sources. Neither paths nor scores are rail
alignments, real road-network travel times or engineering feasibility.
"""
import argparse,collections,json
from pathlib import Path

def contiguous_groups(positions, missing):
    blocks=[];active=[]
    for p in positions:
        if p in missing:
            active.append(p)
        elif active:
            blocks.append(active);active=[]
    if active:blocks.append(active)
    return blocks

def describe(g3,g4):
    if g3.get("mandatory_cities")!=["Vila Real","Bragança"] or not g3.get("Sanabria_excluded"):
        raise ValueError("incorrect_target_scope")
    if g4.get("DGT_2m_total_distinct_original_tile_footprint_km2")!=121 or g4.get("G3_total_native_NoData_2m_pixels")!=31451:
        raise ValueError("unverified_G4_real_source_coverage")
    links={r["link"]:r for r in g4["five_reviewed_original_DSM_OSM_catalogue_lattice_links"]}
    if len(links)!=5 or len(g3["links"])!=5:
        raise ValueError("wrong_5_source_link_count")
    results=[];all_missing=collections.Counter();family_coverage={}
    for row in g3["links"]:
        lname=row["link"]; link=links[lname]
        refs={z["mode"]:z for z in link["path_variants"]}
        if len(refs)!=len(row["solutions"]):raise ValueError("G3_G4_path_variant_count_conflict")
        rows=[];covered_union=set();missing_union=set();variant_routes={}
        for p in row["solutions"]:
            mode=p["mode"];o=refs[mode]
            if p["status"]!=o.get("status",p["status"]) and p["status"]!="exploratory_2km_DSM_source_catalog_lattice_connected":
                raise ValueError("source_variant_status_conflict")
            path=[tuple(z) for z in p["route_sector_cells"]]
            if not path:
                rows.append({"mode":mode,"connected_in_source_lattice":False,"status":p["status"]})
                continue
            missing={tuple(x) for x in o["missing_sector_positions_epsg3763"]}
            if not missing.issubset(set(path)):raise ValueError("unknown_G4_missing_cell")
            expected_m=o["missing_whole_2km_source_sector_count"]
            if len(missing)!=expected_m or len(path)!=o["source_lattice_2km_cells"]:
                raise ValueError("unverified_G4_lattice_sector_counts")
            covered=set(path)-missing
            runs=contiguous_groups(path,missing)
            for pos in missing:all_missing[pos]+=1
            covered_union.update(covered);missing_union.update(missing)
            variant_routes[mode]=set(path)
            maxblock=max((len(z) for z in runs),default=0)
            rows.append({"mode":mode,"connected_in_source_lattice":True,
                 "study_lattice_steps":p["lattice_steps"],
                 "orthogonal_lattice_length_km_not_rail_distance":p["orthogonal_lattice_distance_km"],
                 "all_referenced_lattice_2km_cells":len(path),
                 "full_native_DGT2m_cell_count":len(covered),
                 "without_full_native_DGT2m_cell_count":len(missing),
                 "native_terrain_full_cell_percent":round(100*len(covered)/len(path),1),
                 "number_of_discontinuous_missing_terrain_blocks":len(runs),
                 "largest_consecutive_missing_lattice_cell_block":maxblock,
                 "largest_consecutive_missing_lattice_span_approx_km":max(0,(maxblock-1)*2),
                 "surface_proxy_sum_robust_relief_m_not_track_grade":p.get("sum_of_grid_surface_relief_values_m_not_railway_ramp"),
                 "max_neighbour_DSM_median_elevation_change_m_not_track_grade":p.get("max_adjacent_cell_median_elevation_change_m_not_track_gradient"),
                 "median_DSM_surface_elevation_m":p.get("median_of_DSM_surface_median_elevations_m"),
                 "arbitrary_research_cost_not_comparable_across_objectives":p.get("arbitrary_exploratory_cell_cost"),
                 "first_missing_2km_SW_grid_epsg3763":[list(x) for x in next(iter(runs),[])[:8]],
                 "never_infer_track_from_2km_square_route":True})
        family_coverage[lname]=(covered_union,missing_union)
        # Shared positions between all available scenarios are better priorities for future
        # terrain acquisition than differences of routes (but not engineering feasibility).
        common=set.intersection(*(z for z in variant_routes.values())) if variant_routes else set()
        common_missing=sorted(common&missing_union)
        for pos in common_missing:all_missing[pos]+=0 # already ranked by variant crossings
        results.append({"link":lname,"kind":row["category"],"variants":rows,
            "unique_missing_native_2km_cells_across_link_variants":len(missing_union),
            "cells_traversed_by_all_link_variants":len(common),
            "common_to_all_variants_but_without_full_native_2km_ground":[list(p) for p in common_missing],
            "no_validated_station_or_railway_alignment":True})
    if len(all_missing)!=len(g4["missing_sector_ranked_by_number_of_exploratory_variants"]):
        raise ValueError("G4_missing_union_size_disagrees")
    top=[]
    for p,count in sorted(all_missing.items(),key=lambda item:(-item[1],item[0]))[:25]:
        top.append({"cell_SW_grid_epsg3763":list(p),"study_variant_crossings":count,
                    "links_crossing_without_full_native_DGT2m":[x["link"] for x in results if p in family_coverage[x["link"]][1]]})
    return {"mission":"MN-GEO-RAIL-001","stage":"G4_source_lattice_five_link_characterisation",
       "datum":"Source G3 Copernicus GLO-30 DSM + OSM + official DGT catalog; G4 real DGT 2m source footprints and NoData QA",
       "source_lattice_cell_metres":2000,"mandatory_service_areas":["Vila Real","Bragança"],
       "stations_can_be_peripheral":True,"Sanabria_excluded":True,
       "source_alternative_link_count":len(results),
       "source_lattice_path_variants":sum(len(q["variants"]) for q in results),
       "distinct_missing_full_2km_native_DGT_terrain_cells_in_existing_source_lattice_variants":len(all_missing),
       "actual_all_DGT_2m_source_footprint_km2":121,
       "geometry_is_orthogonal_lattice_not_track":True,
       "source_lattice_road_distance_is_Euclidean_not_road_network":True,
       "slope_curvature_tunnels_viaducts_alignment_timing_and_cost_not_evaluated":True,
       "no_full_Porto_Zamora_detailed_ground_corridor_coverage_proven":True,
       "links":results,"high_recurrence_uncovered_source_lattice_cells":top,
       "Fxx_accepted":False,"Site_authorized":False}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--g3",type=Path,required=True)
    a.add_argument("--g4",type=Path,required=True)
    a.add_argument("--json",type=Path,required=True)
    a.add_argument("--markdown",type=Path,required=True)
    z=describe(json.loads(a.g3.read_text()),json.loads(a.g4.read_text()))
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(z,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    md=["# MN-GEO-RAIL-001 — G4 avaliação das cinco ligações exploratórias",
        "",
        "**Estado: análise de cobertura e relevo superficial, não traçado ferroviário nem tempos de viagem.**",
        "Vila Real e Bragança obrigatórias, estações centrais não obrigatórias, Sanábria excluída.",
        f"Total DGT original MDT2m: **121 km²** (não contínuos); {z['distinct_missing_full_2km_native_DGT_terrain_cells_in_existing_source_lattice_variants']} quadrículas de 2 km distintas sem MDT2m integral ao longo das alternativas representadas.",
        "",
        "| Ligação | Modo | Quadrículas percorridas | DGT2m integral | Falta integral | Cobertura | Comprimento ortogonal da grelha (km, não ferrovia) | Blocos em falta | Maior bloco consecutivo em falta (células) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for link in z["links"]:
        for v in link["variants"]:
            if not v.get("connected_in_source_lattice"):
                md.append(f"| {link['link']} | {v['mode']} | sem ligação na grelha | — | — | — | — | — | — |")
                continue
            md.append(f"| {link['link']} | {v['mode']} | {v['all_referenced_lattice_2km_cells']} | {v['full_native_DGT2m_cell_count']} | {v['without_full_native_DGT2m_cell_count']} | {v['native_terrain_full_cell_percent']}% | {v['orthogonal_lattice_length_km_not_rail_distance']} | {v['number_of_discontinuous_missing_terrain_blocks']} | {v['largest_consecutive_missing_lattice_cell_block']} |")
    md += ["", "## Gaps e interpretação",
        "Cada quadrícula é uma área 2×2 km da **grelha exploratória DSM/OSM**, não uma faixa projetada nem um troço de via. 'Sem MDT integral' não significa ausência de todo o terreno (podem existir quadrículas DGT originais parciais).",
        "Os valores de relevo são de **superfície Copernicus**, não perfis de terreno nu ou rampas ferroviárias. Distâncias sobre a grelha ortogonal são diferentes do comprimento de um traçado.",
        "Os 58 setores identificados não abrangem as aproximações Porto–Marão nem Bragança–fronteira–Zamora; estas continuam a exigir estudos de continuidade próprios.",
        "",
        "## Quadrículas repetidamente atravessadas nas alternativas sem MDT2m integral",
        "| Grelha PT-TM06, canto SW (m) | Presenças nas variantes | Ligações |",
        "|---|---:|---|"]
    for row in z["high_recurrence_uncovered_source_lattice_cells"]:
        md.append(f"| {row['cell_SW_grid_epsg3763']} | {row['study_variant_crossings']} | {'; '.join(row['links_crossing_without_full_native_DGT2m'])} |")
    md += ["","**Nota:** priorização indicativa para a próxima recolha MDT, nunca escolha de estações ou decisão ferroviária. Devem seguir-se continuidade do solo nu, critérios de raio/gradiente por cenário, obras de arte, topografia e acessibilidade rodoviária por rede navegável. Não integrar no catálogo Fxx/Site sem aceitação técnica.",""]
    a.markdown.write_text("\n".join(md))
    print("G4_SOURCE_CHARACTERISATION="+json.dumps(z,ensure_ascii=False,separators=(',',':')))
if __name__=="__main__":main()
