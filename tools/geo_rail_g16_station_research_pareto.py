#!/usr/bin/env python3
"""G16: Pareto shortlisting three along-grid reference sites per city.

INE original 2021 BGRI residential population within 5/10km circles; actual
G12 OSRM road-snap to an *unbuilt 2km research grid* reference; G13 1km
Copernicus 30m surface grade-proxy (NOT bare earth, structures or CAPEX).

No routes for bus/public transport are fabricated, nor missing data treated
as zero. No legal station parcel, rail tangent/platform or risk certified.
Outputs research-site Pareto sets, no arbitrary utility score or 'best station'.
"""
from __future__ import annotations
import argparse,hashlib,json,sqlite3,tempfile
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
from shapely.geometry import Point
from pyproj import Transformer
from geo_rail_g14_bgri2021_station_population import (
 F67_SHA,unpack_exact,native_qa,catchment
)

G13_SHA="063c1ddae2eb8020edc530bfef09fe8239208068b918a56d6054005ad31bfaee"
FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
MARKETS=("Guimaraes","Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca")
MANDATORY=("Vila_Real","Braganca")
RADII=(5000.,10000.)

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(2**20),b""):h.update(chunk)
 return h.hexdigest()

def source_station_positions(g13):
 selected=[z for z in g13["all_108_observed_source_research_surface_points"]
   if z["research_combination"] in FAMILIES]
 if len(selected)!=54:raise ValueError("G13A_three_families_six_markets_three_points_missing")
 r={(x["research_combination"],x["urban_market_key"],x["offset_along_2km_research_grid_km"]):x for x in selected}
 if len(r)!=54:raise ValueError("duplicate_G13_station_source_reference")
 return r

def pareto(points):
 # More resident 2021 geographic coverage is favorable; lower tested
 # urban-reference road minutes and lower local DSM relief pressure are
 # favorable. No CAPEX or demand derived from these values.
 valid=[q for q in points if q["OSRM_2026_urban_market_to_research_road_reference_min"] is not None
 and q["DSM_25permille_1km_vertical_P90_surface_residual_m"] is not None]
 def objective(q):
  return (-q["original_2021_residents_within_5km_geographic_buffer"],
   q["OSRM_2026_urban_market_to_research_road_reference_min"],
   q["DSM_25permille_1km_vertical_P90_surface_residual_m"],
   q["DSM_plusminus125m_lateral_P90_surface_difference_m"])
 winners=[]
 for x in valid:
  if any(y is not x and all(a<=b+1e-8 for a,b in zip(objective(y),objective(x)))
      and any(a<b-1e-8 for a,b in zip(objective(y),objective(x))) for y in valid):
   continue
  winners.append(x)
 return sorted(winners,key=lambda p:p["OSRM_2026_urban_market_to_research_road_reference_min"])

def execute(rawzip,g13path,outjson,outmarkdown):
 if sha(g13path)!=G13_SHA:raise ValueError("G13A_original_research_site_SHA_mismatch")
 g13=json.loads(g13path.read_text())
 if g13["site_counts"]["original_research_points"]!=108 or not g13["Sanabria_excluded"] or g13["Fxx_accepted"]:
  raise ValueError("G13A_source_not_accepted")
 originals=source_station_positions(g13)
 converter=Transformer.from_crs(4326,3763,always_xy=True)
 cases=[]
 unique={}
 with tempfile.TemporaryDirectory(prefix="G16_original_F67_") as tmp:
  native=unpack_exact(rawzip,Path(tmp))
  db=sqlite3.connect(f"file:{native}?mode=ro",uri=True,timeout=45)
  try:
   qa=native_qa(db)
   for (family,city,offset),site in originals.items():
    location=tuple(site["WGS84_research_coordinate"])
    if location not in unique:
     x,y=converter.transform(*location)
     census={}
     for radius in RADII:
      study=catchment(db,Point(x,y).buffer(radius,quad_segs=24),qa["rtree"])
      census[int(radius/1000)]={
       "2021_population_representative_subsection_assignment":study["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
       "2021_population_area_weighted_within_subsection_sensitivity":study["area_weighted_uniform_within_subsection_population_estimates"]["N_INDIVIDUOS"],
       "2021_age65_representative_subsection_assignment":study["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS_65_OU_MAIS"],
       "subsections_intersecting_circle":study["original_subsections_intersecting_area"]}
     unique[location]=census
    grade=site["terrain"].get("grade_sensitivity_profile",{}).get("25",{})
    cases.append({"research_family":family,"urban_market_key":city,
      "mandatory_service_market":city in MANDATORY,
      "longitudinal_offset_km_from_nearest_grid_source_reference":offset,
      "WGS84_2km_research_grid_reference_NOT_station":list(location),
      "original_2021_residents_within_5km_geographic_buffer":unique[location][5]["2021_population_representative_subsection_assignment"],
      "original_2021_residents_within_10km_geographic_buffer":unique[location][10]["2021_population_representative_subsection_assignment"],
      "residents_5km_area_weighted_sensitivity":unique[location][5]["2021_population_area_weighted_within_subsection_sensitivity"],
      "residents_10km_area_weighted_sensitivity":unique[location][10]["2021_population_area_weighted_within_subsection_sensitivity"],
      "population_age65_5km_2021":unique[location][5]["2021_age65_representative_subsection_assignment"],
      "OSRM_2026_urban_market_to_research_road_reference_min":site["road_network_drive_minutes_to_research_road_snap"],
      "road_snap_reference_is_NOT_approved_station":True,
      "DSM_25permille_1km_vertical_P90_surface_residual_m":grade.get("L1_p90_vertical_DSM_residual_m"),
      "DSM_plusminus125m_lateral_P90_surface_difference_m":site["terrain"].get("lateral_plusminus_125m_p90_absolute_surface_difference_m"),
      "DSM_is_surface_not_bare_earth":True,
      "population_not_demand_and_no_legal_rail_station_location":True})
  finally:db.close()
 if len(cases)!=54:raise ValueError("source_only_54_candidate_study_points_expected")
 sets=[]
 for family in FAMILIES:
  for city in MARKETS:
   options=[c for c in cases if c["research_family"]==family and c["urban_market_key"]==city]
   if len(options)!=3:raise ValueError("three_reference_sites_missing")
   selected=pareto(options)
   if not selected:raise ValueError("no_valid_study_reference_candidates_at_mandatory_service_city")
   sets.append({"research_family":family,"urban_market":city,
    "mandatory":city in MANDATORY,"three_original_reference_positions_screened":3,
    "nondominated_reference_positions":len(selected),
    "nondominated_reference_offsets_km":[x["longitudinal_offset_km_from_nearest_grid_source_reference"] for x in selected],
    "references_not_rail_station_sites":True})
 result={"mission":"MN-GEO-RAIL-001","stage":"G16_three_positions_per_six_markets_x_three_research_corridors_BRGI2021_service_and_DSM_access_proxy",
  "run_utc":datetime.now(timezone.utc).isoformat(),
  "sources_SHA256":{"INE_BRGI2021_CONT_exact":F67_SHA,"G13A_108_source_terrain_road_sites":G13_SHA},
  "2021_residents_are_not_2026_population_nor_train_demand":True,
  "geographic_census_circles_not_accessibility_isochrones":True,
  "public_transport_coverage_at_NUTS2_Norte_unavailable_for_systematic_comparison":True,
  "no_PT_data_is_not_no_actual_PT_service_and_no_PT_score_imposed":True,
  "two_mandatory_cities":["Vila Real","Bragança"],
  "other_cities_optional":["Guimarães","Amarante","Mirandela","Macedo de Cavaleiros"],
  "Sanabria_excluded":True,
  "sites_not_validated_and_legal_road_access_unverified":True,
  "station_engineering_and_capex_unknown":True,
  "select_only_nondominated_source_reference_locations_not_approved_station_sites":True,
  "GPKG_original_native_QA":qa,
  "source_sites_screened":len(cases),
  "physically_distinct_reference_locations":len(unique),
  "market_by_family_pareto_reference_screen":sets,
  "all_54_source_research_station_reference_alternatives":cases,
  "Fxx_accepted":False,"Site_authorized":False}
 outjson.parent.mkdir(parents=True,exist_ok=True)
 outjson.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 md=["# G16 — Três posições por cidade e por família: população 2021, acesso por estrada e relevo",
 "","Todas as posições continuam a ser pontos da grelha ferroviária exploratória, não terrenos de estação. Vila Real e Bragança obrigatórias; Sanábria excluída.",
 "A avaliação não contém transporte público: cobertura sistemática de serviço em NUTS II Norte não disponível para medição uniforme, mas a ausência de dados não é ausência de serviço.",
 "Foi calculada a população real do INE BGRI 2021 num círculo de 5 e 10 km em torno de cada posição. Não equivale a isócronas nem a procura de passageiros.",
 "Não houve custos ou localização legal/geométrica de plataformas aferidos.",
 "","| Família | Nó | Referências da grelha mantidas na fronteira de Pareto | Deslocações longitudinais ao centro de referência (km) |",
 "|---|---|---:|---|"]
 for s in sets:
  md.append(f"| {s['research_family']} | {s['urban_market']} | {s['nondominated_reference_positions']}/3 | {', '.join(str(x) for x in s['nondominated_reference_offsets_km'])} |")
 md+=["","A fronteira é construída sem pesos arbitrários: maximiza a população residente num círculo de 5 km, minimiza tempo rodoviário observado até um ponto de estrada, minimiza pressão vertical e lateral do MDS Copernicus 30 m. Pode conter as três posições; não é avaliação financeira nem de viabilidade ferroviária.",
  "A mesma posição pode ser comum a 2–2–1 e 2–2–3, mas a solução Bragança–Zamora difere. O próximo portão exige topografia solo nu, uso do solo, acesso legal, plataforma e engenharia horizontal e vertical do traçado antes de selecionar terrenos.",
  "","Sem nova aquisição de INE, sem Fxx ou Site.",""]
 outmarkdown.parent.mkdir(parents=True,exist_ok=True)
 outmarkdown.write_text("\n".join(md))
 print("G16_SITE_PORTFOLIO="+json.dumps({"source_sites":len(cases),"unique_coordinates":len(unique),
  "sets":[{"f":z["research_family"],"city":z["urban_market"],"n":z["nondominated_reference_positions"],
   "offsets":z["nondominated_reference_offsets_km"]} for z in sets]},ensure_ascii=False,separators=(',',':')))
 return result

def main():
 p=argparse.ArgumentParser()
 for n in ("zip","g13a","json","markdown"):p.add_argument("--"+n,required=True,type=Path)
 a=p.parse_args()
 execute(a.zip,a.g13a,a.json,a.markdown)
if __name__=="__main__":main()
