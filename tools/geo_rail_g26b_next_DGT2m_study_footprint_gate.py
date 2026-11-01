#!/usr/bin/env python3
"""G26B exact original DGT MDT2m coverage gate for candidate source-only G25
station road shortlist. "2 km cells" are G10 research grid; ORIGINAL terrain
is 2 m-resolution 1x1 km producer TIFFs. No new producer downloads.
3/6km straight-line envelopes are NOT projected railway approaches; tile
counts are conditional sampling requirements, never an acquisition order.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
from shapely.geometry import box,LineString
from shapely.ops import unary_union
from geo_rail_g19_native_DGT_station_ground_gates import coverage_native_sources

G25_SHA="be35181c882c2f6ede4d07f7e0a68b084bb6247c54a7da0d1d566a66f844dffd"
G20_SHA="614e16b25dbcfe245deda15af2640a79f968d4981939916fff9b39df1b3901ff"
G21_SHA="753335ae118c74df3d256cbfe853a47e34aa929a862401efcaf8721883c8f23e"
ENVELOPES=((1500.,300.),(3000.,300.),(6000.,1000.))
MAX_BOXES_PER_STUDY=6000

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def native_grid_old(b1,grid12,one):
 rects,_=coverage_native_sources(b1,grid12,one)
 old=set()
 for entry in rects:
  x0,y0,x1,y1=[int(z) for z in entry["geom"].bounds]
  for x in range(x0,x1,1000):
   for y in range(y0,y1,1000):
    old.add((x//1000+200,y//1000+301))
 if len(old)!=45:raise ValueError("G26B_original_old_DGT_45_1km_tiles_inventory_drift")
 return old

def existing_tiles(old,g20,g21):
 new={tuple(a["col_row"]) for a in g20["DGT_new_target_manifest_exact_verified_public_source_metadata"]}
 if len(new)!=39 or new&old:raise ValueError("G26B_original_39_new_source_tiles_not_distinct_from_45_previous")
 if g21["source_original_tiles_acquired"]!=39 or g21["source_original_native_pixels_verified"]!=9687239:
  raise ValueError("G26B_G21_original_verified_39_source_coverage_drift")
 alltiles=old|new
 if len(alltiles)!=84:raise ValueError("G26B_original_84_source_1km_tiles_not_preserved")
 return alltiles

def indices(shapegeom):
 minx,miny,maxx,maxy=shapegeom.bounds
 xmin=math.floor(minx/1000);xmax=math.ceil(maxx/1000)
 ymin=math.floor(miny/1000);ymax=math.ceil(maxy/1000)
 if (xmax-xmin)*(ymax-ymin)>MAX_BOXES_PER_STUDY:raise ValueError("G26B_unbounded_original_DGT_2m_footprint_scan")
 return {(x+200,y+301) for x in range(xmin,xmax) for y in range(ymin,ymax)
   if shapegeom.intersects(box(x*1000,y*1000,(x+1)*1000,(y+1)*1000))}

def envelope(xy,heading_deg,half_length_m,half_width_m):
 rad=math.radians(heading_deg)
 ux,uy=math.cos(rad),math.sin(rad)
 x,y=xy
 l=LineString([(x-half_length_m*ux,y-half_length_m*uy),(x+half_length_m*ux,y+half_length_m*uy)])
 return l.buffer(half_width_m,cap_style=2,join_style=2)

def build(g25,g20,g21,b1,grid12,tile):
 if g25["two_compulsory_cities"]!=["Vila Real","Bragança"] or g25["Fxx_accepted"] or g25["Site_authorized"]:
  raise ValueError("G26B_G25_mandatory_road_source_contract")
 old=native_grid_old(b1,grid12,tile)
 covered=existing_tiles(old,g20,g21)
 points={}
 for z in g25["source_shortlisted_road_reference_route_cases"]:
  xyt=tuple(z["original_study_EPSG3763_XY"])
  points.setdefault(xyt,{"city":z["mandatory_market"],"angles":set(),"families":set()})
  d=points[xyt]
  d["angles"].add(round(z["G24_source_station_straight_heading_deg"]%180,2))
  d["families"].add(z["source_corridor_family"])
 if len(points)!=7:raise ValueError("G26B_G25_original_seven_unique_city_research_coordinates_missing")
 cases=[];union_by_width={str(e):set() for e in ENVELOPES}
 source_distinct_2km={}
 for xy,v in sorted(points.items()):
  for heading in sorted(v["angles"]):
   rec={"city":v["city"],"source_xy_EPSG3763_m":list(xy),"reference_straight_heading_not_railtrack_deg":heading,
     "source_families_using_point":sorted(v["families"]),"conditional_length_width_original_DGT2m_grid_tile_gaps":[]}
   for length,width in ENVELOPES:
    geom=envelope(xy,heading,length,width)
    tileids=indices(geom)
    missing=tileids-covered
    key=str((length,width))
    union_by_width[key].update(tileids)
    cellids={(math.floor((col-200)/2),math.floor((row-301)/2)) for col,row in tileids}
    full={(x,y) for x,y in cellids if all((2*x+i+200,2*y+j+301) in covered for i in (0,1) for j in (0,1))}
    rec["conditional_length_width_original_DGT2m_grid_tile_gaps"].append({
     "hypothetical_source_approach_half_length_m":length,
     "hypothetical_lateral_screen_half_width_m":width,
     "original_required_1km_x_1km_DGT_2m_tiles":len(tileids),
     "original_verified_1km_x_1km_DGT_2m_tiles_within_envelope":len(tileids&covered),
     "additional_1km_DGT_2m_tiles_required_if_this_straight_envelope_becomes_actual_study_area":len(missing),
     "2km_original_G10_research_grid_cells_intersected":len(cellids),
     "2km_research_grid_cells_with_all_four_original_1km_DGT_2m_tiles_available":len(full),
     "missing_native_original_DGT_1km_grid_indices":[list(p) for p in sorted(missing)],
     "source_line_is_NOT_engineered_rail_corridor":True})
   cases.append(rec)
 scenario_summaries=[]
 for length,width in ENVELOPES:
  req=union_by_width[str((length,width))]
  if not req:raise ValueError("G26B_no_envelope_research_tile_intersections")
  missing=req-covered
  geo_2km={(math.floor((c-200)/2),math.floor((r-301)/2)) for c,r in req}
  scenario_summaries.append({
    "hypothetical_source_approach_half_length_m":length,
    "hypothetical_study_envelope_half_width_m":width,
    "distinct_required_original_1km_DGT2m_tiles_across_ALL_study_directions":len(req),
    "distinct_already_preserved_1km_DGT2m_tiles":len(req&covered),
    "distinct_gap_1km_original_DGT2m_tiles_IF_ALL_ORIENTATIONS_STUDIED":len(missing),
    "original_2km_grid_cells_in_conditional_study_envelopes":len(geo_2km),
    "conditional_acquisition_not_authorized":True})
 return {"mission":"MN-GEO-RAIL-001",
  "stage":"G26B_existing_84km2_original_DGT2m_coverage_vs_conditional_1p5_3_6km_city_station_connection_study_envelopes",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "source_SHA256":{"G25":G25_SHA,"G20":G20_SHA,"G21":G21_SHA},
  "original_DGT_2m_source_resolution_m":2,
  "original_DGT_2m_SOURCE_TILE_SIDE_m":1000,
  "G10_original_SCREENING_GRID_CELL_SIDE_m":2000,
  "original_DGT_1km_source_tile_count_previously_verified":45,
  "original_DGT_1km_source_tile_count_G21_additional":39,
  "total_distinct_original_DGT2m_1km_source_tiles_preserved":len(covered),
  "original_native_2m_source_tiles_not_entirely_valid_elevation_due_to_NoData":True,
  "seven_distinct_mandatory_city_study_coordinates":len(points),
  "hypothetical_tangent_orientation_scenarios":len(cases),
  "conditional_1p5_3_6km_screen_union_gap_summary":scenario_summaries,
  "per_road_reference_site_and_source_tangent_conditional_terrain_grid_gap":cases,
  "no_station_or_route_alignment_has_been_engineered":True,
  "current_G23B_400m_station_and_1000m_approach_source_ground_is_sufficient_for_sensitivity":True,
  "new_DGT2m_should_not_be_requested_before_COS_PDM_SRU_land_condition_triage":True,
  "next_DGT_tile_acquisition_gate":"Only after a SHORTLIST OF ACTUAL APPROACH ENVELOPES that are continuous in rail horizontal and vertical geometry and pass necessary COS/PDM/environmental constraints, acquire exact 1km original DGT2m tiles intersecting those corridors minus 84 verified existing source tiles; never all scenarios at once.",
  "conditional_gap_counts_are_not_order_quantities_or_approved_survey_area":True,
  "no_new_original_DGT_source_downloads":True,
  "mandatory_cities":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "Fxx_accepted":False,"Site_authorized":False}

def main():
 p=argparse.ArgumentParser()
 for arg in ("g25","g20","g21","b1","grid12","tile279503","json","markdown"):p.add_argument("--"+arg,type=Path,required=True)
 a=p.parse_args()
 for path,expected in ((a.g25,G25_SHA),(a.g20,G20_SHA),(a.g21,G21_SHA)):
  if sha(path)!=expected:raise ValueError("G26B_pinned_original_source_SHA_drift_"+path.name)
 q=build(json.loads(a.g25.read_text()),json.loads(a.g20.read_text()),json.loads(a.g21.read_text()),
         json.loads(a.b1.read_text()),json.loads(a.grid12.read_text()),json.loads(a.tile279503.read_text()))
 a.json.parent.mkdir(parents=True,exist_ok=True);a.json.write_text(json.dumps(q,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 md=["# G26B — Quando será necessário adquirir mais MDT original de 2 m?",
  "","**Esclarecimento:** a resolução altimétrica é 2 m; os ficheiros originais DGT têm 1×1 km. As linhas exploratórias G10 usam quadrículas 2×2 km, que não constituem ficheiros MDT.",
  "","O Mobilidade Norte preserva 45 quadrículas antigas + 39 G21 = **84 km² nominais** de produtos originais, com áreas NoData explicitamente descontadas. G23B já tem dados para as faixas exploratórias de 400 e 1000 m avaliadas. Sem aquisição automática nesta etapa.",
  "","## Quanta topografia falta sob horizontes condicionais, NÃO linhas projetadas",
  "| Envolvente de estudo (cada lado) | Meia largura | Quadrículas DGT 1km originais necessárias | Já preservadas | Faltantes se todas as variantes forem mantidas |",
  "|---|---:|---:|---:|---:|"]
 for z in q["conditional_1p5_3_6km_screen_union_gap_summary"]:
  md.append(f"| ±{z['hypothetical_source_approach_half_length_m']/1000:g} km | {z['hypothetical_study_envelope_half_width_m']} m | {z['distinct_required_original_1km_DGT2m_tiles_across_ALL_study_directions']} | {z['distinct_already_preserved_1km_DGT2m_tiles']} | {z['distinct_gap_1km_original_DGT2m_tiles_IF_ALL_ORIENTATIONS_STUDIED']} |")
 md+=["","**Gatilho operacional:** adquirir só depois de depurar COS2025, condicionantes legais (REN/RAN/SRUP/PDM), cartografia de infraestruturas, e escolher aproximações ferroviárias contínuas a analisar. Então cruzar a envolvente de trabalho selecionada com as 84 quadrículas já preservadas e pedir apenas os novos identificadores originais DGT 1km. O inventário integral de variantes é limite condicional, não requisição.",
  "","Fora dos setores de estação, o futuro alinhamento completo AFSC–Zamora exigirá também cobertura adicional de terreno, preferencialmente em faixas estreitas definidas a partir do MDS 30 m, mas não em manchas arbitrárias de 2km de grelha.",
  "","Sem novas aquisições DGT, sem Fxx ou Site.",""]
 a.markdown.parent.mkdir(parents=True,exist_ok=True);a.markdown.write_text("\n".join(md))
 print("G26B_GROUND_NEED="+json.dumps({
   "existing_original_1km_DGT_tiles":q["total_distinct_original_DGT2m_1km_source_tiles_preserved"],
   "site_points":q["seven_distinct_mandatory_city_study_coordinates"],
   "tangents":q["hypothetical_tangent_orientation_scenarios"],
   "conditional_gap_scenarios":q["conditional_1p5_3_6km_screen_union_gap_summary"],
   "no_new_DGT_acquisitions":True},ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
