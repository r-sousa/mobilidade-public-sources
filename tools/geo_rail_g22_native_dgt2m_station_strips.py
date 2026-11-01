#!/usr/bin/env python3
"""G22: evaluate ORIGINAL DGT 2m ground at five mandatory rail study references.

Reuse authentic G21 39 + exact four previously preserved B1 original GeoTIFFs;
no new DGT credentials/downloads or 30m DSM substituted for bare-earth ground.
Compare hypothetical 400m×50m near-level station EARTHWORKS SCREEN oriented
along G19 source-grid study tangent, plus 1000m×60m 18/25 per mille
reference approach screens. Modelled cut/fill metres cubed are deliberately
NOT constructible engineering quantities, railway feasibility or costs EUR.
Source missing cells stay missing; source study tangent is NOT a rail alignment.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone
from contextlib import ExitStack
import numpy as np,rasterio
from pyproj import Transformer
from geo_rail_g3_native80 import native_raster_QA

G19_SHA="9f4d290f3fb2718c1a49a921c10d17b7f8c4dd97ccd28e3e6854486a8917dbe2"
G20_SHA="614e16b25dbcfe245deda15af2640a79f968d4981939916fff9b39df1b3901ff"
G21_SHA="753335ae118c74df3d256cbfe853a47e34aa929a862401efcaf8721883c8f23e"
NATIVE_PIXELS=250000
SITE=(400.,50.,10.,10.,.0025)
APPROACH=(1000.,60.,20.,10.)
GRADES=(.018,.025)
PAT=re.compile(r"^MDT-2m-(\d{3})(\d{3})-(\d{2})-(20\d{2})$")
MAX_SOURCE_TILES=43

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for part in iter(lambda:f.read(2**20),b""):h.update(part)
 return h.hexdigest()

def source_originals(directory,manifest,receipt,b1):
 new={q["producer_ID"]:q for q in manifest["DGT_new_target_manifest_exact_verified_public_source_metadata"]}
 old={i for group in b1["groups"] for i in group["tile_ids"]}
 if len(old)!=32 or len(new)!=39:raise ValueError("G22_exact_39_new_32_B1_original_inventory_needed")
 required_coords={tuple(x) for seed in manifest["selected_reference_points_NOT_real_stations"]
    for x in seed["source_grid_3x3km_1km_cells"]}
 ids={}
 for sourceid in list(new)+list(old):
  m=PAT.fullmatch(sourceid)
  if not m:raise ValueError("source_tile_ID_invalid")
  position=(int(m.group(1)),int(m.group(2)))
  if position in required_coords:
   if position in ids:raise ValueError("duplicate_original_DGT_tile_from_different_release")
   ids[position]=sourceid
 if set(ids)!=required_coords or len(ids)!=43:
  raise ValueError("G22_mandatory_43_source_1km_cells_not_complete")
 g21={x["producer_original_ID"]:x for x in receipt["native_GeoTIFF_producer_source_checksums_and_QA"]}
 if set(g21)!=set(new):raise ValueError("G21_source_receipt_39_originals_inconsistent")
 matrices={}
 qa={}
 for coord,ident in ids.items():
  path=directory/(ident+".tif")
  if not path.is_file():raise ValueError("MISSING_RELEASED_ORIGINAL_SOURCE_FILE_"+ident)
  measured=native_raster_QA(path,ident)
  if ident in g21:
   if (sha(path)!=g21[ident]["source_original_sha256"] or
       measured["real_valid_ground_pixels"]!=g21[ident]["source_native_valid_pixels"] or
       measured["source_nodata_pixels"]!=g21[ident]["source_nodata_pixels"]):
    raise ValueError("source_G21_original_tile_SHA_or_mask_drift_"+ident)
  # Old B1 original releases already have producer-pinned assets;
  # repeat native per-file QA here, never treat a mosaic as original.
  with rasterio.open(path) as ds:
   data=ds.read(1,masked=True)
   mask=np.ma.getmaskarray(data)|~np.isfinite(data.data)
   matrices[coord]=np.ma.array(data.data,mask=mask,copy=True)
  qa[ident]={"source":("G21_verified_39" if ident in new else "B1_original_reused"),
   "sha256":sha(path),"ground_valid_pixels":measured["real_valid_ground_pixels"],
   "original_source_NoData_pixels":measured["source_nodata_pixels"],
   "original_tile_EPSG3763_bbox":measured["bbox_pttm06_m"]}
 return matrices,qa

def evaluate_cell(x,y,matrices):
 col=math.floor(x/1000)+200
 row=math.floor(y/1000)+301
 matrix=matrices.get((col,row))
 if matrix is None:return None
 # EPSG3763 1km original DGT grid; upper-left = y(row+1)
 lx=(x-(col-200)*1000)/2
 ly=((row-300)*1000-y)/2
 ix,iy=int(math.floor(lx)),int(math.floor(ly))
 if not(0<=ix<500 and 0<=iy<500):return None
 v=matrix[iy,ix]
 if np.ma.is_masked(v) or not math.isfinite(float(v)):return None
 return float(v)

def reference_heading(g19,city,family):
 rows=[r for r in g19["site_reference_54_true_native_ground_proximity_screens"]
       if r["urban_market_key"]==city and r["research_family"]==family]
 if len(rows)!=3:raise ValueError("G19_three_source_positions_required_for_study_heading")
 sortedrows=sorted(rows,key=lambda x:x["research_offset_km"])
 a=sortedrows[0]["not_engineered_source_point_EPSG3763_xy_m"]
 b=sortedrows[-1]["not_engineered_source_point_EPSG3763_xy_m"]
 dx,dy=b[0]-a[0],b[1]-a[1]
 if math.hypot(dx,dy)<100:raise ValueError("G19_original_source_tangent_geometry_degenerate")
 return (dx/math.hypot(dx,dy),dy/math.hypot(dx,dy)),round(math.degrees(math.atan2(dy,dx)),3)

def strip(site,direction,matrices,length,width,step_long,step_cross,max_grade):
 # Fixed 2m actual ground samples on a 10/20m regular sample grid.
 nx=int(round(length/step_long))
 ny=int(round(width/step_cross))
 if nx<5 or ny<3:raise ValueError("unacceptable_profile_template")
 along=(np.arange(nx)+.5-nx/2)*step_long
 across=(np.arange(ny)+.5-ny/2)*step_cross
 ux,uy=direction
 coords=[(site[0]+t*ux-c*uy,site[1]+t*uy+c*ux,t) for t in along for c in across]
 points=[evaluate_cell(x,y,matrices) for x,y,t in coords]
 ok=[(a[2],z) for a,z in zip(coords,points) if z is not None]
 covered=len(ok)/len(coords)
 summary={"study_template_length_m":length,"study_template_width_m":width,
   "study_max_vertical_grade_per_mille":max_grade*1000,
   "total_expected_ground_samples":len(coords),
   "source_original_DGT2m_valid_sample_count":len(ok),
   "source_valid_ground_fraction":round(covered,5),
   "source_missing_samples_count":len(coords)-len(ok),
   "engineering_suitability_demonstrated":False,
   "route_tangent_only_from_G19_source_2km_lattice_NOT_rail_geometry":True,
   "original_ground_NoData_samples_are_not_interpolated":True}
 if covered<.98 or len(ok)<10:
  return {**summary,"source_profile_fit_status":"insufficient_original_ground_pixels",
   "modelled_terrain_cut_volume_m3_NOT_ENGINEERING_QUANTITY":None,
   "modelled_terrain_fill_volume_m3_NOT_ENGINEERING_QUANTITY":None,
   "modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY":None,
   "source_vertical_deviation_p90_m":None,
   "source_linear_grade_required_before_clamp_per_mille":None}
 t=np.array([v[0] for v in ok],dtype="float64")
 z=np.array([v[1] for v in ok],dtype="float64")
 grad=float(np.dot(t-t.mean(),z-z.mean())/np.sum((t-t.mean())**2))
 imposed=float(np.clip(grad,-max_grade,max_grade))
 intercept=float(np.median(z-t*imposed))
 residual=z-(intercept+imposed*t)
 cellarea=step_long*step_cross
 cut=float(np.maximum(residual,0).sum()*cellarea)
 fill=float(np.maximum(-residual,0).sum()*cellarea)
 return {**summary,"source_profile_fit_status":"eligible_original_ground_screen_NOT_station",
  "source_terrain_elevation_min_max_m":[round(float(z.min()),2),round(float(z.max()),2)],
  "source_terrain_p05_p95_relief_m":round(float(np.percentile(z,95)-np.percentile(z,5)),3),
  "source_vertical_deviation_p90_m":round(float(np.percentile(abs(residual),90)),3),
  "source_linear_grade_required_before_clamp_per_mille":round(1000*grad,3),
  "hypothetical_plane_grade_clamped_per_mille":round(1000*imposed,3),
  "modelled_terrain_cut_volume_m3_NOT_ENGINEERING_QUANTITY":round(cut),
  "modelled_terrain_fill_volume_m3_NOT_ENGINEERING_QUANTITY":round(fill),
  "modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY":round(cut+fill),
  "terrain_volumes_are_straight_plane_screen_NOT_actual_civil_earthworks":True,
  "this_does_NOT_resolve_ground_conditions_roads_platform_tunnels_viaducts":True}

def run(g19path,g20path,g21path,b1path,tile_dir,jout,mdout):
 for path,expected in ((g19path,G19_SHA),(g20path,G20_SHA),(g21path,G21_SHA)):
  if sha(path)!=expected:raise ValueError("source_original_release_SHA_drift_"+path.name)
 g19=json.loads(g19path.read_text());g20=json.loads(g20path.read_text());g21=json.loads(g21path.read_text())
 b1=json.loads(b1path.read_text())
 if (g20["study_reference_points_selected_for_two_mandatory_urban_markets"]!=5 or
   g20["new_original_DGT_1km_tiles_targeted"]!=39 or
   g20["existing_original_DGT_1km_tiles_reused_within_neighbourhoods"]!=4 or
   g21["source_original_tiles_acquired"]!=39 or
   g21["source_original_native_pixels_verified"]!=9687239 or
   g21["source_original_nodata_pixels_preserved"]!=62761 or
   g21["source_original_tile_count_entirely_NoData_unusable_for_ground"]!=0 or
   g21["Fxx_accepted"] or g21["Site_authorized"]):
  raise ValueError("G22_expected_verified_G21_2021_source_contract_failed")
 matrices,qa=source_originals(tile_dir,g20,g21,b1)
 allrows=[]
 for site in g20["selected_reference_points_NOT_real_stations"]:
  place=site["mandatory_urban_market"]
  city=place
  xy=site["original_EPSG3763_XY_study_reference_m"]
  for family in site["geographical_source_families_sharing_reference"]:
   direction,heading=reference_heading(g19,city,family)
   strips={
    "hypothetical_station_400m_50m_max_grade_2p5permille":
       strip(xy,direction,matrices,*SITE),
    "hypothetical_approach_1000m_60m_max_grade_18permille":
       strip(xy,direction,matrices,*APPROACH,.018),
    "hypothetical_approach_1000m_60m_max_grade_25permille":
       strip(xy,direction,matrices,*APPROACH,.025)}
   allrows.append({
    "G20_source_reference_id":site["id"],"mandatory_market":place,"research_family":family,
    "source_only_EPSG3763_XY_study_reference_m":xy,
    "source_G19_straight_reference_heading_degrees_EastCounterClockwise":heading,
    "not_railway_engineered_tangent":True,
    "original_2021_5km_circle_residents_not_ridership":site["original_2021_population_in_5km_circle_NOT_rail_demand"],
    "original_road_time_city_to_nearby_grid_reference_not_station_min":site["source_road_access_from_urban_reference_min_NOT_station"],
    "native_DGT2m_primary_source_site_and_approach_terrain_screens":strips,
    "original_ground_can_demonstrate_rail_station_legal_or_engineering_feasibility":False,
    "no_actual_station_CAPEX_or_validated_tunnel_bridge_quantities":True})
 if len(allrows)<5:raise ValueError("missing_G22_five_mandatory_site_study_axis_screens")
 stats={"geographic_study_point_cases_with_family":len(allrows),
   "hypothetical_station_screen_with_98percent_native_ground":sum(
    v["native_DGT2m_primary_source_site_and_approach_terrain_screens"][
     "hypothetical_station_400m_50m_max_grade_2p5permille"]["source_profile_fit_status"]
       =="eligible_original_ground_screen_NOT_station" for v in allrows),
   "hypothetical_approach_18permille_screen_with_98percent_native_ground":sum(
    v["native_DGT2m_primary_source_site_and_approach_terrain_screens"][
     "hypothetical_approach_1000m_60m_max_grade_18permille"]["source_profile_fit_status"]
       =="eligible_original_ground_screen_NOT_station" for v in allrows)}
 result={"mission":"MN-GEO-RAIL-001",
  "stage":"G22_original_2m_DGT_ground_hypothetical_station_strip_and_approach_screen_NO_RAILWAY_FEASIBILITY",
  "observed_utc":datetime.now(timezone.utc).isoformat(),
  "original_sources_SHA256":{"G19":G19_SHA,"G20":G20_SHA,"G21":G21_SHA},
  "new_native_1km2_DGT_producer_original_tiles_39":True,
  "previous_preserved_B1_original_1km2_tiles_reused_4":True,
  "all_43_required_source_terrain_tiles_checked_original_pixel_masks":True,
  "total_new_G21_original_2m_valid_ground_pixels":9687239,
  "new_G21_original_NoData_pixels_preserved":62761,
  "source_RasterNoData_never_filled_or_called_real_elevation":True,
  "hypothetical_platform_earthworks_NOT_engineering_quantities_m3":True,
  "hypothetical_study_platform_grade_2p5_permille_not_local_design_standard":True,
  "grid_tangent_from_G19_3_study_points_not_engineered_track_line":True,
  "all_five_research_seeds_are_NOT_legally_approved_real_station_sites":True,
  "no_tunnel_viaduct_bridge_risk_euro_construction_unit_cost":True,
  "no_road_legal_last_mile_geotechnical_or_train_service_validation":True,
  "no_new_DGT_downloads":True,"Fxx_accepted":False,"Site_authorized":False,
  "mandatory_urban_markets":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "source_tiles_native_original_observation_inventory":qa,
  "validation_summary":stats,
  "five_site_by_family_original_terrain_study_screens":allrows}
 jout.parent.mkdir(parents=True,exist_ok=True)
 jout.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 md=["# G22 — MDT2m DGT original: relevo local em cinco referências de estação obrigatória",
  "","Utilizados os **39 GeoTIFFs originais G21** e as **quatro quadrículas originais B1** já preservadas, sem descarregar MDT novamente. A avaliação incide nos cinco pontos G20 de Vila Real e Bragança, em orientações de referência derivados dos três pontos G19 de cada família. Não existem estações projetadas ou terrenos legalmente verificados.",
  "","Os valores de corte/aterro são **somente proxies matemáticas** obtidas sobre um plano de referência em 400 × 50 m com declive máximo hipotético de 2,5‰. Estudam-se adicionalmente faixas de 1000 × 60 m com 18‰ e 25‰. Não representam medições de obra, volumes de custo nem CBA.",
  "","## Medição do original terreno para a plataforma exploratória",
  "| Referência | Família | Azimute a partir da grelha (°) | Originais válidos | P90 desvio vertical (m) | Volume proxy de solo (m³; NÃO custo) |",
  "|---|---|---:|---:|---:|---:|"]
 for item in allrows:
  profile=item["native_DGT2m_primary_source_site_and_approach_terrain_screens"]["hypothetical_station_400m_50m_max_grade_2p5permille"]
  val=profile.get("modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY")
  p90=profile.get("source_vertical_deviation_p90_m")
  md.append(f"| {item['G20_source_reference_id']} | {item['research_family']} | {item['source_G19_straight_reference_heading_degrees_EastCounterClockwise']} | {profile['source_original_DGT2m_valid_sample_count']}/{profile['total_expected_ground_samples']} | {p90 if p90 is not None else 'N/D'} | {val if val is not None else 'N/D'} |")
 md+=["","## Portões antes de estimar custos",
  "1. Verificar a integração geométrica da linha e raio horizontal real com a plataforma, curvas verticais e inclinação regulamentar em projeto (2,5‰ aqui é só hipótese).",
  "2. Avaliar acessibilidade rodoviária legal, restrições de solo, expropriação, servidões e geologia. A cobertura por pixels DGT2m não resolve estas questões.",
  "3. Delimitar footprints reais e comparar movimentos de terras, viadutos, túneis e custos unitários; nenhuma quantidade em euros é inferida dos volumes proxy.",
  "4. Considerar dois perfis de exploração: expresso Vila Real/Bragança e alternativas com interfaces opcionais, mantendo a cobertura G18 como potencial e não procura ferroviária.",
  "","O G22 não promove Fxx nem altera Site. Sanábria excluída.",""]
 mdout.parent.mkdir(parents=True,exist_ok=True);mdout.write_text("\n".join(md))
 print("G22_NATIVE_STATION_TERRAIN="+json.dumps({"five_research_sites":5,
   "source_original_tiles":len(qa),"families_source_approach_profiles":len(allrows),
   "station_original_screen_sufficient":stats["hypothetical_station_screen_with_98percent_native_ground"],
   "approach_original_screen_sufficient":stats["hypothetical_approach_18permille_screen_with_98percent_native_ground"],
   "do_not_interpret_volumes_as_construction_quantities":True},separators=(",",":")))
 return result

def main():
 a=argparse.ArgumentParser()
 for k in ("g19","g20","g21","b1","tiles","json","markdown"):a.add_argument("--"+k,type=Path,required=True)
 p=a.parse_args();run(p.g19,p.g20,p.g21,p.b1,p.tiles,p.json,p.markdown)
if __name__=="__main__":main()
