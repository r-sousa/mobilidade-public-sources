#!/usr/bin/env python3
"""G19: real native DGT-2m ground coverage vs 54 INE/road/DSM study-point candidates.

Classifies native pixel coverage *only where* original validated 2m tile
rectangles actually cover reference point and a separate 1km-square screen;
catalogue footprints/DSM 30m are NOT original ground pixels. Does not
certify stations, physical alignments, legal road interchange or EUR cost.
Also retains actual G18 hypothetical stopping-pattern 2021 resident road
coverage as a separate service axis; do not sum overlapping populations.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone
from shapely.geometry import box,Point
from shapely.ops import unary_union
from pyproj import Transformer

G16_SHA="e794c14b2d9101a7d6d31dd11f46081039e6dba40349b0e32018b57eeb79c7a9"
G18_SHA="6c9db058f0cd07966daf5afb5ec8fa8dbd411eb47409a24f6b83f8712b48f0f2"
FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
MANDATORY=("Vila_Real","Braganca")
MARKETS=("Guimaraes","Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca")
SOURCE_NATIVE_AUDIT="reports/mn-geo-rail-001/B1-DGT-native-2m-32km2-verified-ground-sector-review.json"
SOURCE_GRID12_AUDIT="reports/mn-geo-rail-001/pt-dgt-native-grid12-preserved-audit.json"
SOURCE_279503_AUDIT="reports/mn-geo-rail-001/pt-dgt-native-279503-NP159-source-qa-acceptance.json"
POPULATION_NOT_RAIL_DEMAND=True

def digest(p):
 h=hashlib.sha256()
 with p.open("rb") as fd:
  for chunk in iter(lambda:fd.read(2**20),b""):h.update(chunk)
 return h.hexdigest()

def coverage_native_sources(b1,grid12,tile):
 if (b1["total_distinct_native_DGT_ground_2m_area_km2"]!=45 or
    b1["original_source_GeoTIFF_count"]!=32 or
    b1["source_archive_sha256_verified_locally"] is not True or
    grid12["area_km2"]!=12 or grid12["all_native_bytes_preserved_in_prerelease"] is not True or
    tile["original_tif"]["valid_pixels"]!=250000):
  raise ValueError("verified_2m_primary_source_input_inconsistent")
 polys=[]
 for sector in b1["sectors"]:
  rect=box(*sector["bbox_epsg3763"])
  if rect.area!=4e6 or sector["valid_native_ground_cells_2m"]!=1000000:
   raise ValueError("B1_native_sector_2m_source_bbox_or_cell_count_drift")
  polys.append({"source":"B1_verified_native_2m_"+sector["city"]+"_"+sector["quadrant"],
   "geom":rect,"site_geography":sector["city"],
   "native_ground_source_verified":True,
   "elevation_p95_p05_m_of_4km2_sector_NOT_local_station":sector["observed_terrain_elevation_p95_minus_p05_m_rounded"]})
 # 12km2 source certified 3 x 4km contiguous footprint in actual original DGT.
 rect=box(*grid12["bbox_pttm06"])
 if rect.area!=12e6 or grid12["validated_cells"]!=3000000:
  raise ValueError("original_12km2_source_bbox_cells_inconsistent")
 polys.append({"source":"grid12_validated_native_2m_Mirandela","geom":rect,"site_geography":"Mirandela",
  "native_ground_source_verified":True,
  "elevation_p95_p05_m_of_4km2_sector_NOT_local_station":None})
 # Another 1km2 original strictly disjoint from the grid12 footprint.
 other=box(*tile["original_tif"]["bbox_epsg3763"])
 if other.area!=1e6 or other.intersects(rect):
  raise ValueError("native_original_279503_should_be_one_disjoint_km2")
 polys.append({"source":"279503_native_2m_Mirandela","geom":other,"site_geography":"Mirandela",
  "native_ground_source_verified":True,
  "elevation_p95_p05_m_of_4km2_sector_NOT_local_station":None})
 full=unary_union([p["geom"] for p in polys])
 if not abs(full.area/1e6-45)<.000001:
  raise ValueError("native_45km2_rectangles_nonoverlap_expected")
 return polys,full

def closest_native(site_xy,verified):
 pt=Point(*site_xy)
 indexed=[(round(pt.distance(p["geom"]),1),p) for p in verified]
 indexed.sort(key=lambda q:q[0])
 near,p=indexed[0]
 covered=any(pt.intersects(x["geom"]) for x in verified)
 # 1x1km centered tangent-free vicinity, NOT a 1km station platform.
 sq=box(site_xy[0]-500,site_xy[1]-500,site_xy[0]+500,site_xy[1]+500)
 union=unary_union([x["geom"] for x in verified])
 exact=round(sq.intersection(union).area/1e6,4)
 return {"direct_point_native_2m_pixel_coverage_in_verified_45km2":covered,
   "surrounding_1km_square_native_2m_source_covered_fraction":exact,
   "distance_to_nearest_preserved_QA_DGT_native_2m_footprint_m":near,
   "nearest_proven_ground_original_sector":p["source"],
   "closest_native_ground_sector_4km2_elevation_p95_p05_m_NOT_station_gradient":p["elevation_p95_p05_m_of_4km2_sector_NOT_local_station"],
   "metadata_source_tiles_not_downloaded_NOT_counted_as_verified_ground":True,
   "coverage_absence_not_terrain_coverage_absence_at_producer":True,
   "no_original_ground_station_grade_or_alignment_cross_section_yet":True}

def execute(g16file,g18file,b1file,grid12file,onefile,outfile,mdfile,geojsonfile):
 for p,hash_ in ((g16file,G16_SHA),(g18file,G18_SHA)):
  if digest(p)!=hash_:raise ValueError("G19_archived_original_G16_or_G18_SHA_drift")
 g16=json.loads(g16file.read_text());g18=json.loads(g18file.read_text())
 verified,source_union=coverage_native_sources(
  json.loads(b1file.read_text()),json.loads(grid12file.read_text()),json.loads(onefile.read_text()))
 if (g16["source_sites_screened"]!=54 or
    g16["two_mandatory_cities"]!=["Vila Real","Bragança"] or
    not g16["public_transport_coverage_at_NUTS2_Norte_unavailable_for_systematic_comparison"] or
    g16["Fxx_accepted"] or g16["Site_authorized"] or
    len(g18["36_family_stop_pattern_road_time_geographic_population_screens"])!=36 or
    not g18["Sanabria_excluded"] or g18["Fxx_accepted"]):
  raise ValueError("source_research_project_scope_or_authorizations_changed")
 winner={(z["research_family"],z["urban_market"]):set(z["nondominated_reference_offsets_km"])
   for z in g16["market_by_family_pareto_reference_screen"]}
 projection=Transformer.from_crs(4326,3763,always_xy=True)
 out=[]
 counts={}
 geo=[]
 for src in g16["all_54_source_research_station_reference_alternatives"]:
  family=src["research_family"];market=src["urban_market_key"]
  if family not in FAMILIES or market not in MARKETS:raise ValueError("unknown_original_city_or_family")
  lon,lat=src["WGS84_2km_research_grid_reference_NOT_station"]
  x,y=projection.transform(lon,lat)
  terrain=closest_native((x,y),verified)
  is_pareto=src["longitudinal_offset_km_from_nearest_grid_source_reference"] in winner[(family,market)]
  row={"research_family":family,"urban_market_key":market,
   "mandatory_market":market in MANDATORY,
   "research_offset_km":src["longitudinal_offset_km_from_nearest_grid_source_reference"],
   "not_engineered_source_point_lonlat":[lon,lat],
   "not_engineered_source_point_EPSG3763_xy_m":[round(x,2),round(y,2)],
   "already_G16_nondominated_population_road_DSM_reference":is_pareto,
   "2021_population_5km_geographic_circle_not_station_isochrone":src["original_2021_residents_within_5km_geographic_buffer"],
   "2021_population_10km_geographic_circle_not_station_isochrone":src["original_2021_residents_within_10km_geographic_buffer"],
   "OSRM_road_time_from_associated_city_to_road_snap_reference_min":src["OSRM_2026_urban_market_to_research_road_reference_min"],
   "one_km_DSM_25permille_vertical_P90_surface_residual_m_NOT_ground":src["DSM_25permille_1km_vertical_P90_surface_residual_m"],
   "DSM_125m_flank_P90_surface_difference_m":src["DSM_plusminus125m_lateral_P90_surface_difference_m"],
   **terrain,"railway_platform_grade_radius_land_use_property_and_access_legal_not_verified":True,
   "possible_station_CAPEX_EUR":None,"possible_link_or_deviation_CAPEX_EUR":None,
   "possible_line_tunnel_and_bridge_m":None,
   "no_measured_railway_grade_or_vertical_curve":True}
  out.append(row)
  geo.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
   "properties":{k:v for k,v in row.items() if k not in
     ("not_engineered_source_point_lonlat","not_engineered_source_point_EPSG3763_xy_m")}})
 if len(out)!=54:raise ValueError("G19_incomplete_54_original_site_reference_cases")
 study=[]
 for family in FAMILIES:
  for market in MARKETS:
   group=[x for x in out if x["research_family"]==family and x["urban_market_key"]==market]
   if len(group)!=3:raise ValueError("G19_original_3_site_positions_missing")
   options=[x for x in group if x["already_G16_nondominated_population_road_DSM_reference"]]
   if len(options)<1:raise ValueError("G19_G16_original_Pareto_positions_missing")
   study.append({"family":family,"market":market,"mandatory":market in MANDATORY,
    "three_along_grid_source_positions":3,
    "Pareto_research_reference_positions_from_original_G16":len(options),
    "Pareto_source_positions_with_native_DGT_verified_2m_point":sum(x["direct_point_native_2m_pixel_coverage_in_verified_45km2"] for x in options),
    "all_three_source_positions_with_native_DGT_verified_2m_point":sum(x["direct_point_native_2m_pixel_coverage_in_verified_45km2"] for x in group),
    "min_distance_from_Pareto_reference_to_original_native_DGT_coverage_m":min(x["distance_to_nearest_preserved_QA_DGT_native_2m_footprint_m"] for x in options),
    "best_2021_population_5km_among_original_Pareto_research_positions_NOT_demand":max(x["2021_population_5km_geographic_circle_not_station_isochrone"] for x in options),
    "source_native_2m_next_acquisition_needed_for_uncovered_reference":all(not x["direct_point_native_2m_pixel_coverage_in_verified_45km2"] for x in options),
    "minimum_technical_land_rail_geotechnical_validation_not_done":True})
 service30=[{"family":r["research_family"],"hypothetical_stop_pattern":r["hypothetical_rail_stop_pattern"],
    "hypothetical_stop_count":r["hypothetical_stop_count"],
    "2021_residents_road_reachable_in30min_to_study_point_union_NOT_rail_demand":r["2021_residents_reachable_by_auto_to_study_point_union_not_rail_demand"],
    "additional_2021_residents_road_reachable_vs_2_stop_pattern_NOT_demand":r["extra_2021_residents_geographically_reached_vs_VR_BR_only"],
    "actual_incremental_station_deviation_and_connection_capex_EUR":None,
    "actual_rail_in_vehicle_stop_delay_minutes":None,
    "station_location_and_train_stop_not_certified":True}
    for r in g18["36_family_stop_pattern_road_time_geographic_population_screens"]
      if r["reverse_road_arrival_time_minutes"]==30]
 result={"mission":"MN-GEO-RAIL-001","stage":"G19_verified_native_DGT_ground_footprint_vs_54_hypothetical_stations_and_G18_service_increment",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "source_original_g16_SHA256":G16_SHA,"source_original_g18_SHA256":G18_SHA,
  "original_native_DGT_2m_ground_verified_disconnected_area_km2":45,
  "native_original_ground_coverage_is_NOT_full_corridor_coverage":True,
  "native_ground_coverage_source_segments":["B1 8 2x2km audited native blocks Vila Real+Bragança (32km²)",
    "Mirandela 3x4km contiguous original DGT 2m 12km² grid",
    "Mirandela distinct 279503 original DGT 2m 1km² tile"],
  "source_catalogue_only_BBOX_polygon_not_a_valid_native_ground_raster":True,
  "selected_station_locations_approved_or_even_engineered":0,
  "native_ground_covered_source_points":sum(x["direct_point_native_2m_pixel_coverage_in_verified_45km2"] for x in out),
  "all_research_source_points":54,
  "mandatory_Pareto_positions_not_native_DGT_2m_coverage_count":sum(1 for x in out if x["mandatory_market"] and x["already_G16_nondominated_population_road_DSM_reference"] and not x["direct_point_native_2m_pixel_coverage_in_verified_45km2"]),
  "mandatory_urban_markets":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "unavailable_NUTS2_Norte_GTFS_not_score_penalty":True,
  "no_CBA_until_all_station_source_site_CAPEX_and_OD_frequencies_are_verified":True,
  "no_repeated_DGT_downloads":True,
  "further_work_order":["cross-check all source Pareto mandatory city sites against native ground footprint",
   "select near-ground-coverage mandatory points for original 2m detailed cross-section only after full source raster SHA + legal station feasibility",
   "then optional markets with high demographic incremental coverage and plausible rail curvature",
   "select 2–3 feasible site families before local train service/civil cost bill and unit price uncertainty"],
  "site_reference_54_true_native_ground_proximity_screens":out,
  "18_markets_by_family_source_native_ground_coverage_priority":study,
  "12_service_pattern_2021_30min_road_coverage_cross_reference":service30,
  "no_fabricated_EUR_tunnel_bridge_or_station_counts":True,
  "Fxx_accepted":False,"Site_authorized":False}
 outfile.parent.mkdir(parents=True,exist_ok=True)
 outfile.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 geojsonfile.parent.mkdir(parents=True,exist_ok=True)
 geojsonfile.write_text(json.dumps({"type":"FeatureCollection","name":"G19 54 source study points and coverage by real validated original DGT2m ground footprints — NOT proposed rail stations","features":geo},ensure_ascii=False)+"\n")
 md=["# G19 — Integração de relevo de solo nu realmente disponível, 54 pontos de estudo",
  "","A pesquisa original G16 compara população INE 2021 (círculos 5/10 km), tempos OSRM a referências rodoviárias e pressão MDS Copernicus 30m. **Nenhuma dessas referências equivale a uma estação**.",
  "","DGT: **45 km²** de MDT2m com píxeis do ficheiro original validados, apenas em manchas descontínuas. Desses, 32 km² em Vila Real e Bragança e 13 km² na área de Mirandela. A presente verificação mede se os pontos G16 caem dentro desses retângulos preservados; uma caixa de metadados DGT não conta como dados descarregados.",
  "","## Cobertura das posições G16 não dominadas",
  "| Família | Cidade | Obrigatório | Pontos em fronteira G16 | Dentro de MDT DGT2m original | Distância mínima ao MDT2m verificado (m) |",
  "|---|---|---|---:|---:|---:|"]
 for v in study:
  md.append(f"| {v['family']} | {v['market']} | {'Sim' if v['mandatory'] else 'Não'} | {v['Pareto_research_reference_positions_from_original_G16']} | {v['Pareto_source_positions_with_native_DGT_verified_2m_point']} | {v['min_distance_from_Pareto_reference_to_original_native_DGT_coverage_m']:.0f} |")
 md+=["","**Atenção:** ausência de MDT2m original preservado numa posição não significa ausência de cobertura disponível junto da DGT, apenas que a sua cópia ainda não foi adquirida e testada para esse ponto.",
  "","## Serviço de referência em 30min de automóvel (G18, não procura)",
  "| Família | Padrão hipotético | N.º de paragens hipotéticas | Residentes 2021 em isócronas de chegada (união) |",
  "|---|---|---:|---:|"]
 for v in service30:
  md.append(f"| {v['family']} | {v['hypothetical_stop_pattern']} | {v['hypothetical_stop_count']} | {v['2021_residents_road_reachable_in30min_to_study_point_union_NOT_rail_demand']} |")
 md+=["","## Portões necessários para validar locais e custos",
  "1. Definir 2–3 polígonos reais de implantação por cidade obrigatória, com continuidade da linha ferroviária, plataforma e acesso legal.",
  "2. Recolher MDT2m original estritamente na envolvente dos polígonos em falta; verificar datum vertical e terreno de solo nu com amostras/topografia.",
  "3. Verificar raios horizontais e transições, zonas de nível, critérios de carga e rampas/curvas verticais; custos de túneis, pontes, movimentação de terras e ligações viárias só depois de secções e quantidades.",
  "4. Comparar tempos de percurso e penalizações marginais de paragem por serviço, com procura OD e intervalos plausíveis de custos.",
  "5. **Não inferir procura ferroviária** da população existente em isócronas de automóvel a pontos hipotéticos.",
  "","Sem novas descargas de MDT, sem promoção Fxx/Site.",""]
 mdfile.parent.mkdir(parents=True,exist_ok=True)
 mdfile.write_text("\n".join(md))
 print("G19_REAL_GROUND_STATIONS="+json.dumps({
  "original_ground_area_km2":45,"research_points":len(out),
  "within_verified_native_ground_points":result["native_ground_covered_source_points"],
  "mandatory_Pareto_native_ground_missing":result["mandatory_Pareto_positions_not_native_DGT_2m_coverage_count"],
  "mandatory":[{"family":r["family"],"city":r["market"],
    "source_pareto_points":r["Pareto_research_reference_positions_from_original_G16"],
    "covered_original_ground":r["Pareto_source_positions_with_native_DGT_verified_2m_point"],
    "nearest_ground_m":r["min_distance_from_Pareto_reference_to_original_native_DGT_coverage_m"]} for r in study if r["mandatory"]]},
  ensure_ascii=False,separators=(",",":")))
 return result

def main():
 a=argparse.ArgumentParser()
 for arg in ("g16","g18","b1","grid12","native279503","json","markdown","geojson"):
  a.add_argument("--"+arg,required=True,type=Path)
 p=a.parse_args()
 execute(p.g16,p.g18,p.b1,p.grid12,p.native279503,p.json,p.markdown,p.geojson)
if __name__=="__main__":main()
