#!/usr/bin/env python3
"""G20 bounded native DGT2m source tile acquisition MANIFEST, not station plan.

From G19 choose <=3 distinct G16 Pareto research positions per mandatory
city (Vila Real, Braganca), on original road access, DSM surface relief and
2021 geographic residents. Select 3x3 native DGT 1km tiles around each,
deduplicate original 45km2 already preserved. STAC identities only: actual
download needs separate protected manual workflow_dispatch on main.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from datetime import datetime,timezone
from geo_rail_pt_b1_dgt_review_grids import inventory
from geo_rail_g19_native_DGT_station_ground_gates import coverage_native_sources

CITIES=("Vila_Real","Braganca")
MAX_TILES=54
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(2**20),b""):h.update(b)
 return h.hexdigest()

def choose(rows,city):
 raw=[r for r in rows if r["urban_market_key"]==city and r["already_G16_nondominated_population_road_DSM_reference"]]
 unique={}
 for r in raw:
  xy=tuple(round(v,1) for v in r["not_engineered_source_point_EPSG3763_xy_m"])
  if xy not in unique:unique[xy]={"xy":xy,"original":r,"families":set()}
  unique[xy]["families"].add(r["research_family"])
 records=list(unique.values())
 a=lambda z:z["original"]["OSRM_road_time_from_associated_city_to_road_snap_reference_min"]
 b=lambda z:z["original"]["one_km_DSM_25permille_vertical_P90_surface_residual_m_NOT_ground"]
 c=lambda z:z["original"]["2021_population_5km_geographic_circle_not_station_isochrone"]
 if not records or any(a(z) is None or b(z) is None for z in records):
  raise ValueError("no_observed_city_road_and_DSM_station_references")
 base=[min(records,key=lambda z:(a(z),b(z))),min(records,key=lambda z:(b(z),a(z))),
       max(records,key=lambda z:(c(z),-a(z)))]
 found=[];seen=set()
 for item in base:
  if item["xy"] not in seen:found.append(item);seen.add(item["xy"])
 if len(found)<2:
  rem=sorted((z for z in records if z["xy"] not in seen),key=lambda z:-math.dist(z["xy"],found[0]["xy"]))
  if rem:found.append(rem[0])
 return found[:3],len(records)

def original_tiles(b1,grid,tile):
 rects,_=coverage_native_sources(b1,grid,tile)
 old=set()
 for rec in rects:
  x0,y0,x1,y1=[int(q) for q in rec["geom"].bounds]
  for x in range(x0,x1,1000):
   for y in range(y0,y1,1000):old.add((x//1000+200,y//1000+301))
 if len(old)!=45:raise ValueError("source_45km2_DGT2m_original_tile_inventory_changed")
 return old

def cells(xy):
 col=math.floor(xy[0]/1000)+200
 row=math.floor(xy[1]/1000)+301
 return {(col+u,row+v) for u in (-1,0,1) for v in (-1,0,1)}

def build(g19,b1,grid,tile,reports):
 if g19["all_research_source_points"]!=54 or not g19["Sanabria_excluded"] or g19["Fxx_accepted"]:
  raise ValueError("G19_source_original_54_site_scope_invalid")
 candidates=g19["site_reference_54_true_native_ground_proximity_screens"]
 by_index,proofs=inventory(reports)
 acquired=original_tiles(b1,grid,tile)
 points=[]
 for city in CITIES:
  selected,total=choose(candidates,city)
  for i,p in enumerate(selected,1):
   base=p["original"];target=cells(p["xy"])
   points.append({"id":city+"-reference-"+str(i),"mandatory_urban_market":city,
      "original_EPSG3763_XY_study_reference_m":list(p["xy"]),
      "geographical_source_families_sharing_reference":sorted(p["families"]),
      "source_road_access_from_urban_reference_min_NOT_station":base["OSRM_road_time_from_associated_city_to_road_snap_reference_min"],
      "original_2021_population_in_5km_circle_NOT_rail_demand":base["2021_population_5km_geographic_circle_not_station_isochrone"],
      "one_km_Copernicus_25permille_vertical_P90_surface_pressure_m_NOT_native_ground":base["one_km_DSM_25permille_vertical_P90_surface_residual_m_NOT_ground"],
      "verified_original_native_2m_ground_at_study_point":base["direct_point_native_2m_pixel_coverage_in_verified_45km2"],
      "source_grid_3x3km_1km_cells":sorted([list(q) for q in target]),
      "existing_original_tiles_in_neighbourhood":len(target&acquired),
      "still_unacquired_tiles_in_neighbourhood":len(target-acquired),
      "station_alignment_legal_access_and_CAPEX_not_validated":True})
 if not 2<=len(points)<=6 or {p["mandatory_urban_market"] for p in points}!=set(CITIES):
  raise ValueError("mandatory_two_city_research_portfolio_not_retained")
 unique=set(tuple(q) for p in points for q in p["source_grid_3x3km_1km_cells"])
 missing=unique-acquired
 if len(unique)>MAX_TILES or len(missing)>MAX_TILES:
  raise ValueError("DGT_original_grid_study_acquisition_cap_exceeded")
 unlisted=missing-set(by_index)
 if unlisted:raise ValueError("official_DGT_STAC_metadata_not_verified_for_targets_"+str(sorted(unlisted)[:10]))
 target=[]
 for col,row in sorted(missing):
  prod=by_index[(col,row)]
  target.append({"producer_ID":prod["id"],"col_row":[col,row],
    "expected_original_GeoTIFF_bbox_EPSG3763_m":[(col-200)*1000,(row-301)*1000,
      (col-199)*1000,(row-300)*1000],
    "producer_STAC_receipt_group":prod["source"],
    "actual_original_GeoTIFF_bytes_present":False,
    "native_2m_pixels_proven":False,
    "only_authentic_producer_GeoTIFF_with_SHA_and_full_raster_QA_will_be_accepted":True})
 return {"mission":"MN-GEO-RAIL-001","stage":"G20_terrain_original_source_target_acquisition_Plan_NOT_real_station",
  "utc":datetime.now(timezone.utc).isoformat(),
  "G19_original_ground_reference_point_count":54,
  "original_DGT_native_2m_ground_existing_km2":45,
  "study_reference_points_selected_for_two_mandatory_urban_markets":len(points),
  "source_3x3km_neighbourhoods_union_tile_count":len(unique),
  "existing_original_DGT_1km_tiles_reused_within_neighbourhoods":len(unique&acquired),
  "new_original_DGT_1km_tiles_targeted":len(missing),
  "max_new_original_source_tile_count":MAX_TILES,
  "upstream_STAC_public_5_reviewed_receipts":proofs,
  "selected_reference_points_NOT_real_stations":points,
  "DGT_new_target_manifest_exact_verified_public_source_metadata":target,
  "mandatory_urban_markets":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "no_new_DGT_CDD_download_in_this_planning_stage":True,
  "DGT_credentialed_original_source_requires_manual_dispatch_on_protected_main_and_environment":"dgt-cdd",
  "do_not_trigger_credentialed_acquisition_via_branch_push_or_PR":True,
  "all_original_DGT_raster_SHA_and_pixel_QA_still_required":True,
  "no_source_terrain_or_cost_eur_railway_station_approved":True,
  "Fxx_accepted":False,"Site_authorized":False}

def main():
 p=argparse.ArgumentParser()
 for k in ("g19","b1","grid12","tile279503","reports","json","markdown"):
  p.add_argument("--"+k,type=Path,required=True)
 q=p.parse_args()
 g19=json.loads(q.g19.read_text())
 result=build(g19,json.loads(q.b1.read_text()),json.loads(q.grid12.read_text()),
   json.loads(q.tile279503.read_text()),q.reports)
 result["upstream_G19_original_sha256"]=sha(q.g19)
 q.json.parent.mkdir(parents=True,exist_ok=True)
 q.json.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 md=["# G20 — Plano alvo para MDT DGT2m dos interfaces obrigatórios",
  "","**Apenas recolha prioritária de relevo. Nenhum local de estação foi aprovado.**",
  "O estudo utiliza G19/G16 e revisita duas cidades obrigatórias: Vila Real e Bragança. Escolhem-se até três coordenadas únicas por cidade para testar, sem pontuações monetárias arbitrárias, a distância rodoviária, pressão de superfície e população residente em círculos (não passageiros).",
  "",
  "| Indicador | Quantidade |","|---|---:|",
  f"| Pontos G19 estudados | {result['G19_original_ground_reference_point_count']} |",
  f"| Referências obrigatórias prioritárias | {result['study_reference_points_selected_for_two_mandatory_urban_markets']} |",
  f"| Trama 3x3 km após eliminar sobreposição | {result['source_3x3km_neighbourhoods_union_tile_count']} km² |",
  f"| Quadrículas originais já preservadas nesta trama | {result['existing_original_DGT_1km_tiles_reused_within_neighbourhoods']} |",
  f"| **Novas quadrículas MDT2m por adquirir e verificar** | **{result['new_original_DGT_1km_tiles_targeted']}** |",
  "","## Coordenadas de investigação escolhidas",
  "| Referência | Famílias | Tempo até via próxima (min) | Originais MDT2m existentes (9 células) | Novos (9 células) |",
  "|---|---|---:|---:|---:|"]
 for z in result["selected_reference_points_NOT_real_stations"]:
  md.append(f"| {z['id']} | {', '.join(z['geographical_source_families_sharing_reference'])} | {z['source_road_access_from_urban_reference_min_NOT_station']} | {z['existing_original_tiles_in_neighbourhood']} | {z['still_unacquired_tiles_in_neighbourhood']} |")
 md+=["","Os IDs DGT em JSON correspondem ao catálogo oficial STAC já inspecionado, não a ficheiros nativos já adquiridos. A fase G20 não usa segredos e não descarrega os rasters. As aquisições credenciadas deverão manter a regra existente: despacho explícito no ramo principal protegido com ambiente dgt-cdd, seguida de validação individual de bytes, SHA e píxeis por publicador independente.",
  "A trama 3x3 km de investigação em torno de cada ponto ainda não representa uma estação fisicamente implantável, ligação viária legal ou traçado ferroviário projetado. Sem Fxx ou Site.",""]
 q.markdown.parent.mkdir(parents=True,exist_ok=True);q.markdown.write_text("\n".join(md))
 print("G20_MANIFEST="+json.dumps({"sites":len(result["selected_reference_points_NOT_real_stations"]),
   "new_DGT_tiles":result["new_original_DGT_1km_tiles_targeted"],
   "old_tiles_reused":result["existing_original_DGT_1km_tiles_reused_within_neighbourhoods"],
   "manifest_ids":[x["producer_ID"] for x in result["DGT_new_target_manifest_exact_verified_public_source_metadata"]],
   "downloaded_new_tiles":False},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
