#!/usr/bin/env python3
"""G23A source-traceable mandatory-city station research Pareto.

Reads immutable source G22 13 native DGT2m original ground screens and G20 five
reference sites; does not assign €/m3 nor assume stations already exist.
Compare independent terrain, access and 2021 census measures, with source
tangent/approach limitations. Pareto dimensions exclude population/road time
if missing; no fabricated zero imputation. Report at seed and family scale.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone

G22_SHA="785ee7a2cf1e0f81916e6feb9d85ec6228c0a12286e118a6f17a2514802f3e7c"
G20_SHA="614e16b25dbcfe245deda15af2640a79f968d4981939916fff9b39df1b3901ff"
STATION="hypothetical_station_400m_50m_max_grade_2p5permille"
APP18="hypothetical_approach_1000m_60m_max_grade_18permille"
APP25="hypothetical_approach_1000m_60m_max_grade_25permille"
MARKETS=("Vila_Real","Braganca")

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for z in iter(lambda:f.read(2**20),b""):h.update(z)
 return h.hexdigest()

def pareto(rows,keys):
 good=[r for r in rows if all(r.get(k) is not None for k in keys)]
 result=[]
 for a in good:
  if not any(b is not a and all(b[k]<=a[k]+1e-8 for k in keys)
          and any(b[k]<a[k]-1e-8 for k in keys) for b in good):
   result.append(a)
 return result

def render(g22path,g20path,jsonpath,csvpath,mdpath):
 if sha(g22path)!=G22_SHA or sha(g20path)!=G20_SHA:raise ValueError("released_native_G22_G20_source_digest_changed")
 g22=json.loads(g22path.read_text());g20=json.loads(g20path.read_text())
 if (len(g22["five_site_by_family_original_terrain_study_screens"])!=13
    or len(g22["source_tiles_native_original_observation_inventory"])!=43
    or g22["total_new_G21_original_2m_valid_ground_pixels"]!=9687239
    or g22["new_G21_original_NoData_pixels_preserved"]!=62761
    or len(g20["selected_reference_points_NOT_real_stations"])!=5
    or g22["Fxx_accepted"] or g22["Site_authorized"]):
  raise ValueError("G23_source_contract_incomplete")
 xs=[]
 for z in g22["five_site_by_family_original_terrain_study_screens"]:
  profiles=z["native_DGT2m_primary_source_site_and_approach_terrain_screens"]
  ss=profiles[STATION];aa=profiles[APP18];bb=profiles[APP25]
  rid=z["G20_source_reference_id"];city=z["mandatory_market"]
  if city not in MARKETS:raise ValueError("G23_city_source_not_mandatory")
  for p in (ss,aa,bb):
   if not p["source_profile_fit_status"]=="eligible_original_ground_screen_NOT_station":
    raise ValueError("G23_unexpected_insufficient_source_pixels_at_mandatory_site")
   if p["source_valid_ground_fraction"]<.98:
    raise ValueError("G23_source_ground_completeness_below_98percent")
  xs.append({
   "source_reference_id":rid,
   "mandatory_market":city,
   "source_corridor_family":z["research_family"],
   "EPSG3763_reference_XY":z["source_only_EPSG3763_XY_study_reference_m"],
   "original_source_tangent_degrees":z["source_G19_straight_reference_heading_degrees_EastCounterClockwise"],
   "2021_residents_geographic_5km_original_G20_not_riders":z["original_2021_5km_circle_residents_not_ridership"],
   "city_center_to_nearby_road_snap_min_not_station":z["original_road_time_city_to_nearby_grid_reference_not_station_min"],
   "station_400x50_ground_valid_fraction":ss["source_valid_ground_fraction"],
   "station_400x50_terrain_surface_relief_p05_p95_m":ss["source_terrain_p05_p95_relief_m"],
   "station_400x50_vertical_p90_deviation_m":ss["source_vertical_deviation_p90_m"],
   "station_400x50_source_observed_grade_before_2p5permille_clamp":ss["source_linear_grade_required_before_clamp_per_mille"],
   "station_400x50_mathematical_terrain_cut_plus_fill_m3_NOT_a_construction_estimate":
     ss["modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY"],
   "approach_1000x60_18permille_vertical_p90_deviation_m":aa["source_vertical_deviation_p90_m"],
   "approach_1000x60_18permille_mathematical_cut_plus_fill_m3_NOT_construction":
     aa["modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY"],
   "approach_1000x60_25permille_vertical_p90_deviation_m":bb["source_vertical_deviation_p90_m"],
   "approach_1000x60_25permille_mathematical_cut_plus_fill_m3_NOT_construction":
     bb["modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY"],
   "unresolved_road_legal_access_and_land_parcel":True,
   "station_site_rail_geometry_not_verified":True,
   "not_railway_engineering_volumes_or_CAPEX":True
  })
 if len(xs)!=13:raise ValueError("expected_13_site_by_family_profiles")
 # Pareto on purely measured original-ground source tangent relief, plus
 # associated original G20 city-centre driving time. No €/km or ridership.
 ks=("station_400x50_vertical_p90_deviation_m",
     "approach_1000x60_18permille_vertical_p90_deviation_m",
     "city_center_to_nearby_road_snap_min_not_station")
 selected=[]
 for market in MARKETS:
  subset=[x for x in xs if x["mandatory_market"]==market]
  frontier=pareto(subset,ks)
  for x in subset:
   x["non_dominated_original_terrain_vs_original_road_reference_screen"]=x in frontier
  selected.extend(frontier)
 # Deduplicate variants to avoid inventing independent site options from
 # repeats of one coordinate under corridor-family labels.
 source_sites={}
 for x in xs:
  id=x["source_reference_id"]
  source_sites.setdefault(id,{"city":x["mandatory_market"],"families":set(),"nondominated":False,
     "min_station_p90_m":float("inf"),"min_approach_p90_m":float("inf"),
     "reference_road_min":x["city_center_to_nearby_road_snap_min_not_station"],
     "source_study_XY":x["EPSG3763_reference_XY"]})
  source_sites[id]["families"].add(x["source_corridor_family"])
  source_sites[id]["nondominated"]|=x["non_dominated_original_terrain_vs_original_road_reference_screen"]
  source_sites[id]["min_station_p90_m"]=min(source_sites[id]["min_station_p90_m"],x["station_400x50_vertical_p90_deviation_m"])
  source_sites[id]["min_approach_p90_m"]=min(source_sites[id]["min_approach_p90_m"],x["approach_1000x60_18permille_vertical_p90_deviation_m"])
 if len(source_sites)!=5:raise ValueError("same_source_site_ids_not_five")
 site_recs=[{"research_source_id":id,"city":v["city"],
   "study_shared_families":sorted(v["families"]),
   "has_some_source_tangent_family_on_3_axis_Pareto":v["nondominated"],
   "min_station_400m_source_p90_m":round(v["min_station_p90_m"],3),
   "min_approach_1000m_source_p90_m":round(v["min_approach_p90_m"],3),
   "associated_original_city_road_reference_time_min_not_new_candidate":v["reference_road_min"],
   "original_study_xy_EPSG3763":v["source_study_XY"]}
   for id,v in sorted(source_sites.items())]
 nby={c:sum(x["has_some_source_tangent_family_on_3_axis_Pareto"] for x in site_recs if x["city"]==c) for c in MARKETS}
 out={"mission":"MN-GEO-RAIL-001","stage":"G23A_native_original_DGT2m_road_reference_nonmonetary_Pareto",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "original_release_SHA256":{"G20":G20_SHA,"G22":G22_SHA},
  "original_native_source_1km_tiles":43,
  "original_source_site_count":5,
  "original_site_family_source_strip_screens":13,
  "non_dominated_screening_dimensions":list(ks),
  "source_corridor_screens_on_pareto_count":len(selected),
  "unique_source_references_with_at_least_one_nondominated_family_by_mandatory_city":nby,
  "5_unique_mandatory_source_site_summaries":site_recs,
  "13_original_terrain_and_existing_city_road_reference_options":xs,
  "earthworks_terrain_m3_are_mathematical_only_not_constructible_or_costs":True,
  "original_source_tangent_NOT_engineered_horizontal_or_vertical_rail_curve":True,
  "g22_station_center_NOT_validated_legal_access_or_parcel":True,
  "public_transport_unavailable_NOT_set_to_zero":True,
  "mandatory_markets":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "all_2021_resident_5km_source_pop_not_rail_passengers":True,
  "stage_next":"G23B local alternate offset+rail-heading terrain QA with source DGT pixels, then road/legal/geotechnical gates",
  "no_new_DGT_downloads":True,"Fxx_accepted":False,"Site_authorized":False}
 jsonpath.parent.mkdir(parents=True,exist_ok=True);jsonpath.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 csvpath.parent.mkdir(parents=True,exist_ok=True)
 with csvpath.open("w",newline="",encoding="utf8") as f:
  names=list(xs[0]);w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(xs)
 md=["# G23A — Comparação original MDT DGT2m de cinco referências obrigatórias",
  "","**Apenas análise de fonte e topografia; nenhuma estação aprovada.** Cinco coordenadas distintas em Vila Real/Bragança; 13 variantes de orientação associadas às três famílias de corredor, 43 GeoTIFFs originais. A geometria é uma tangente à grelha exploratória G19, não um projeto ferroviário.",
  "","## Indicadores observados para o cenário 400×50m (2,5‰ hipotéticos) e aproximação 1000×60m (18‰ hipotéticos)",
  "| Mercado | Referência | Família | Estação p90 (m) | Aproximação p90 (m) | Acesso rodoviário de referência (min) | Pareto de fonte |",
  "|---|---|---|---:|---:|---:|---|"]
 for x in sorted(xs,key=lambda z:(z["mandatory_market"],z["source_reference_id"],z["source_corridor_family"])):
  md.append(f"| {x['mandatory_market']} | {x['source_reference_id']} | {x['source_corridor_family']} | {x['station_400x50_vertical_p90_deviation_m']} | {x['approach_1000x60_18permille_vertical_p90_deviation_m']} | {x['city_center_to_nearby_road_snap_min_not_station']} | {'Sim' if x['non_dominated_original_terrain_vs_original_road_reference_screen'] else 'Não'} |")
 md+=["","**Frente de Pareto:** nenhum indicador monetário; reduz desvios verticais da plataforma e aproximação e o acesso rodoviário da **referência antiga**, não verifica a entrada legal numa estação. As dimensões são de fontes diferentes e não se aplica ponderação arbitrária. Famílias na mesma posição não constituem diferentes localizações.",
  "","## Condições para decidir",
  "- A configuração da plataforma foi imposta matematicamente e os volumes de terra são proxies sem geometria de taludes, geotecnia ou limites reais de escavação; não permitem CAPEX.",
  "- O acesso rodoviário é o tempo até via próxima do ponto G20 original e não cobre estacionamento, transporte público, entradas legais ou outras posições deslocadas.",
  "- Antes de escolher uma estação, verificar a continuidade de traçado, raios, rampa e curvas verticais, constrangimentos legais, áreas efetivamente disponíveis e intermodalidade viária.",
  "- Guimarães, Amarante, Mirandela e Macedo de Cavaleiros continuam oportunidades de serviço opcional e necessitam de tratamento consistente com os custos/tempos de desvios.",
  "","Sem nova descarga DGT, sem alteração Fxx/Site.",""]
 mdpath.parent.mkdir(parents=True,exist_ok=True);mdpath.write_text("\n".join(md))
 print("G23A_NATURAL_PARETO="+json.dumps({"source_cases":len(xs),
   "source_sites":site_recs,
   "non_dominated_cases":len(selected),"by_city":nby},ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":
 a=argparse.ArgumentParser()
 for k in ("g20","g22","json","csv","markdown"):a.add_argument("--"+k,type=Path,required=True)
 q=a.parse_args();render(q.g22,q.g20,q.json,q.csv,q.markdown)
