#!/usr/bin/env python3
"""G6 compose three source-grounded geographic *study chains* AFSC–Zamora.

This routine joins reviewed cell-center research paths across two mandatory
city service areas. It does NOT prove stations, rail radii, gradients, costs,
legal road access, continuous native DTM, or engineering feasibility.
"""
from __future__ import annotations
import argparse,hashlib,json,math,collections
from pathlib import Path
from datetime import datetime,timezone
from pyproj import Transformer
from shapely.geometry import LineString,Point,mapping
from shapely.ops import transform as shapetransform
from geo_rail_pt_b1_dgt_review_grids import inventory
from geo_rail_g3_continuity_open_dsm_sources import cell_ids
from geo_rail_g3_native80 import PRIOR_MIRANDELA_IDS

G3_SHA="ab001fb17ba359d939294b505bc199d459d474095f255f17099c1cdaafd57d9c"
G4_SHA="7d7a513fd248fcef86453da1967baf20d7359e9f66672fd7e5c4d2e7899ed200"
G5_SHA="a4cb8be1443b8be484303934595dfb8ffecaeb6b7857dc0a1ee1569956adfc32"
LEG_NAMES=("P1_AFSC_to_Vila_Real_W","P3_Vila_Real_E_to_Braganca_W","P5_Braganca_E_to_Zamora")
CITY_CONNECTIONS=("Vila_Real_W_to_E","Braganca_W_to_E")
CNIG5M_SOURCE_PANELS_EPSG25830=(
 ("Alcanices",(218000,4619000,226000,4625000)),
 ("Muelas_del_Pan",(248000,4597000,256000,4603000)),
)
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for ch in iter(lambda:f.read(1024*1024),b""):h.update(ch)
 return h.hexdigest()

def centre(p):return (p[0]+1000,p[1]+1000)

def grid_length(route):
 return round(sum(math.dist(centre(a),centre(b))/1000 for a,b in zip(route,route[1:])),3)

def join_checked(parts):
 out=[]
 for seg in parts:
  if not seg or any(len(p)!=2 for p in seg):
   raise ValueError("missing_or_unrecognized_2km_source_research_sector")
  for p in seg:
   if any(int(x)%2000 for x in p):raise ValueError("non_aligned_2km_study_reference")
  if out and out[-1]!=seg[0]:raise ValueError("G6_city_research_connectors_disjoint")
  for p in seg[1:] if out else seg:
   if out and (abs(p[0]-out[-1][0])>2000 or abs(p[1]-out[-1][1])>2000 or p==out[-1]):
    raise ValueError("research_lattice_has_gap_or_duplicate_step")
   out.append(p)
 return out

def validate_sources(g3,g4,g5,b1,cat):
 if g3.get("mandatory_cities")!=["Vila Real","Bragança"] or not g3.get("Sanabria_excluded"):
  raise ValueError("G3_original_source_scope_changed")
 if g4.get("DGT_2m_total_distinct_original_tile_footprint_km2")!=121 or g4.get("G3_total_native_NoData_2m_pixels")!=31451:
  raise ValueError("G4_original_terrain_121km2_provenance_changed")
 if g5.get("mandatory_service_areas")!=["Vila Real","Bragança"] or g5.get("Fxx_accepted") or g5.get("Site_authorized"):
  raise ValueError("G5_source_scope_does_not_permit_rail_claims")
 if len(g5.get("legs",[]))!=3 or len(g4.get("G3_sector_details",[]))!=19 or len(b1.get("sectors",[]))!=8:
  raise ValueError("source_sector_counts_wrong")
 native={}
 for x in g4["G3_sector_details"]:
  p=tuple(x["grid_epsg3763"][:2])
  if p in native:raise ValueError("duplicate_G3_sector")
  native[p]=x
 for x in b1["sectors"]:
  p=tuple(x["bbox_epsg3763"][:2])
  if p in native:raise ValueError("previous_B1_G3_sector_overlap")
  native[p]={"valid_cell_count":1_000_000,"source_NoData_cell_count":0}
 if (80000,206000) in native:raise ValueError("reacquired_Mirandela_region")
 native[(80000,206000)]={"valid_cell_count":1_000_000,"source_NoData_cell_count":0}
 already=set(PRIOR_MIRANDELA_IDS)
 b1_ids=json.loads(Path("configs/MN-GEO-RAIL-001-B1-DGT32-source-IDs.json").read_text())
 already.update(id for g in b1_ids["groups"] for id in g["tile_ids"])
 if len(already)!=45:raise ValueError("original_Mirandela_B1_ID_count_wrong")
 for x in g4["G3_sector_details"]:
  p=x["grid_epsg3763"][:2];ids=cell_ids(cat,*p)
  if ids is None or set(ids)&already or len(set(ids))!=4:
   raise ValueError("G4_real_G3_source_cell_not_catalogued_or_overlaps")
  already.update(ids)
 if len(already)!=121:raise ValueError("incorrect_121_producer_original_IDs")
 return native,already

def run(g3_path,g4_path,g5_path,b1_path,catalogue_path,json_out,geojson_out,markdown_out):
 if any(sha(f)!=s for f,s in ((g3_path,G3_SHA),(g4_path,G4_SHA),(g5_path,G5_SHA))):
  raise ValueError("source_original_G3_G4_G5_SHA256_mismatch")
 g3=json.loads(g3_path.read_text());g4=json.loads(g4_path.read_text())
 g5=json.loads(g5_path.read_text());b1=json.loads(b1_path.read_text())
 catalog,proofs=inventory(catalogue_path)
 native,acquired=validate_sources(g3,g4,g5,b1,catalog)
 links={z["link"]:z for z in g3["links"]}
 vconnect={}
 for l in CITY_CONNECTIONS:
  modes=[x for x in links[l]["solutions"] if x["mode"]=="short"]
  if len(modes)!=1 or modes[0]["status"]!="exploratory_2km_DSM_source_catalog_lattice_connected":
   raise ValueError("previous_G3_local_city_link_missing")
  vconnect[l]=[tuple(p) for p in modes[0]["route_sector_cells"]]
 variants={z["leg"]:z["variants"] for z in g5["legs"]}
 if set(variants)!=set(LEG_NAMES) or any(len(variants[k])!=3 for k in LEG_NAMES):
  raise ValueError("G5_missing_three_spatially_distinct_leg_variants")
 # Screen only: source city service regions have not been connected to actual stations.
 route_set=[]
 epsg3763_to4326=Transformer.from_crs(3763,4326,always_xy=True)
 epsg3763_to25830=Transformer.from_crs(3763,25830,always_xy=True)
 feature=[]
 freq=collections.Counter()
 for i in range(3):
  pt=[ [tuple(p) for p in variants[LEG_NAMES[0]][i]["source_grid_positions_pttm06"]],
       vconnect[CITY_CONNECTIONS[0]],
       [tuple(p) for p in variants[LEG_NAMES[1]][i]["source_grid_positions_pttm06"]],
       vconnect[CITY_CONNECTIONS[1]],
       [tuple(p) for p in variants[LEG_NAMES[2]][i]["source_grid_positions_pttm06"]] ]
  combined=join_checked(pt)
  if len(set(combined))!=len(combined):raise ValueError("self_intersection_at_source_grid_not_reviewed")
  for p in set(combined):freq[p]+=1
  tally=collections.Counter()
  wcs_inside=collections.Counter()
  missing_geo=[];native_valid=0
  for p in combined:
   src_ids=cell_ids(catalog,*p)
   if p in native:
    tally["real_original_full_DGT2m_source_sector"]+=1
    native_valid+=native[p]["valid_cell_count"]
   elif src_ids:
    if any(id in acquired for id in src_ids):
     tally["original_DGT2m_partially_acquired_1km_source_sector"]+=1
    else:tally["four_official_DGT2m_original_IDs_catalogued_but_not_acquired"]+=1
   else:
    tally["not_covered_by_five_reviewed_DGT_STAC_catalogue_windows"]+=1
   x,y=epsg3763_to25830.transform(*centre(p))
   for label,(l,b,r,t) in CNIG5M_SOURCE_PANELS_EPSG25830:
    if l<=x<=r and b<=y<=t:wcs_inside[label]+=1
  line=LineString([centre(p) for p in combined])
  feature.append({"type":"Feature","geometry":mapping(shapetransform(epsg3763_to4326.transform,line)),
    "properties":{"study_chain_id":f"G6-SCREEN-{i+1}","representation":"2km_source_grid_centres_NOT_railway_alignment",
      "service_stations_validated":False,"railway_engineering_validated":False,
      "nominal_Source_GLO30_DSM":True}})
  route_set.append({"study_chain_id":f"G6-SCREEN-{i+1}",
   "composition":"P1 G5 variant + G3 Vila Real W–E + P3 G5 variant + G3 Bragança W–E + P5 G5 variant",
   "study_cell_count":len(combined),
   "diagonal_and_orthogonal_study_grid_length_km_NOT_railway_distance":grid_length(combined),
   "actual_full_source_DGT2m_native_2km_sector_count":tally["real_original_full_DGT2m_source_sector"],
   "true_DGT2m_native_valid_area_in_full_source_sectors_km2":round(native_valid*4/1_000_000,6),
   "no_full_DGT2m_original_sector_count":len(combined)-tally["real_original_full_DGT2m_source_sector"],
   "sector_data_class_counts":dict(tally),
   "sector_centres_inside_preserved_C1_CNIG5m_Alcanices_or_Muelas_panels_NOT_full_coverage":dict(wcs_inside),
   "source_grid_cells_epsg3763":[list(p) for p in combined],
   "Vila_Real_and_Braganca_service_area_research_connectors_included":True,
   "station_locations_and_road_access_unverified":True,
   "PT_ES_vertical_harmonization_unverified":True,
   "train_speed_track_gradients_curves_and_structures_unverified":True})
 # Score missing source-specific acquisition cells across actual separated chains.
 candidate=[]
 for p,cnt in sorted(freq.items(),key=lambda z:(-z[1],z[0])):
  if p in native:continue
  ids=cell_ids(catalog,*p)
  if ids is None or any(z in acquired for z in ids):continue
  candidate.append({"2km_SW_epsg3763":list(p),"present_in_research_chain_variants":cnt,
    "role":"common_source_continuity" if cnt==3 else "between_alternative_discrimination",
    "official_four_producer_DGT2m_source_IDs":ids,
    "all_four_ids_genuinely_not_acquired":True})
 # Balanced small future source-review shortlist, not permission to download.
 common=[z for z in candidate if z["present_in_research_chain_variants"]==3]
 distinct=[z for z in candidate if z["present_in_research_chain_variants"]<3]
 shortlist=(common[:6]+distinct[:6])
 if len(shortlist)<12:
  used={tuple(z["2km_SW_epsg3763"]) for z in shortlist}
  shortlist += [z for z in candidate if tuple(z["2km_SW_epsg3763"]) not in used][:12-len(shortlist)]
 selected_ids=[src for z in shortlist for src in z["official_four_producer_DGT2m_source_IDs"]]
 if len(selected_ids)!=len(set(selected_ids)) or set(selected_ids)&acquired or len(selected_ids)>48:
  raise ValueError("G6_unreviewed_or_reacquired_source_tiles")
 similarities=[]
 for i,a in enumerate(route_set):
  for j,b in enumerate(route_set[:i]):
   aa={tuple(p) for p in a["source_grid_cells_epsg3763"]}
   bb={tuple(p) for p in b["source_grid_cells_epsg3763"]}
   similarities.append({"chain_a":a["study_chain_id"],"chain_b":b["study_chain_id"],
      "spatial_2km_cell_jaccard":round(len(aa&bb)/len(aa|bb),4)})
 obj={"mission":"MN-GEO-RAIL-001","stage":"G6_complete_territorial_research_chains_source_screen_only",
  "date_utc":datetime.now(timezone.utc).isoformat(),
  "source_G3_SHA256":G3_SHA,"source_G4_SHA256":G4_SHA,"source_G5_SHA256":G5_SHA,
  "DGT_five_official_catalogue_source_receipts":proofs,
  "source_Copernicus_GLO30_DSM_not_bare_earth_DTM":True,
  "two_metre_DGT_native_original_distinct_grid_footprint_km2":121,
  "mandatory_service_areas":["Vila Real","Bragança"],"Sanabria_excluded":True,
  "city_centre_station_not_required":True,
  "city_market_functional_access_still_unverified":True,
  "three_complete_study_chains_connect_five_research_modules_on_2km_grid_only":True,
  "genuine_railway_alignment_geometry_not_determined":True,
  "engineering_grade_radius_tunnel_viaduct_speed_cost_NOT_evaluated":True,
  "no_DGT_CDD_credentials_or_original_downloads":True,"Fxx_accepted":False,"Site_authorized":False,
  "end_to_end_research_chains":route_set,"pairwise_spatial_overlap":similarities,
  "reviewed_official_DGT2m_never_acquired_source_catalogue_2km_sectors_intersecting_chains":len(candidate),
  "next_at_most_12_source_review_cells_not_auto_acquisition":shortlist,
  "this_does_not_prove_continuous_native_DTM_in_Portugal_or_Spain":True}
 geo={"type":"FeatureCollection","name":"G6 AFSC–Zamora 3 complete source-grid screens; NOT train tracks",
      "features":feature}
 for path,dat in ((json_out,obj),(geojson_out,geo)):
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps(dat,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 md=["# G6 — Três cadeias exploratórias territoriais AFSC–Vila Real–Bragança–Zamora",
  "","**Não são traçados ferroviários.** Referências de investigação sobre células de 2 km do MDS Copernicus, ligadas por módulos de análise local em Vila Real e Bragança. Nenhuma estação, tempo de acesso ou parâmetro de engenharia foi validado.",
  "","| Cadeia | Distância de grelha (km, não linha férrea) | Setores 2km | Integrais DGT2m | Sem DGT2m integral |",
  "|---|---:|---:|---:|---:|"]
 for z in route_set:
  md.append(f"| {z['study_chain_id']} | {z['diagonal_and_orthogonal_study_grid_length_km_NOT_railway_distance']} | {z['study_cell_count']} | {z['actual_full_source_DGT2m_native_2km_sector_count']} | {z['no_full_DGT2m_original_sector_count']} |")
 md += ["","## Seleção estritamente preliminar de quadrículas para futura verificação DGT","Estas áreas foram escolhidas apenas onde os quatro IDs originais existem em catálogos oficiais previamente auditados e nenhum dos quatro originais foi adquirido. **Não é uma autorização de transferência autenticada nem demonstra aptidão ferroviária.**"]
 for z in shortlist:
  md.append(f"- {z['2km_SW_epsg3763']} · {z['role']} · {z['present_in_research_chain_variants']}/3 cadeias · 4 IDs oficiais ainda não adquiridos")
 md+=["","## Condições por resolver","- Serviço efetivo das duas cidades, acessibilidade rodoviária por rede navegável, implantação periférica, compatibilização vertical Cascais–Alicante e continuidade de MDT solo nu.","- Estudos de curvatura, rampas, velocidades, movimentos de terras, túneis, viadutos, custo e impacto ambiental.","- As duas áreas CNIG de 5m existentes em Alcañices e Muelas del Pan não constituem um MDT contínuo de Bragança a Zamora. Não confundir centros de quadrícula dentro de uma área CNIG com cobertura integral do quadrado.",""]
 markdown_out.parent.mkdir(parents=True,exist_ok=True)
 markdown_out.write_text("\n".join(md))
 print("G6_SOURCE_GRID_REVIEW="+json.dumps({"chains":[{"id":c["study_chain_id"],
   "lattice_km":c["diagonal_and_orthogonal_study_grid_length_km_NOT_railway_distance"],
   "sectors":c["study_cell_count"],"native_DGT2m_full":c["actual_full_source_DGT2m_native_2km_sector_count"],
   "CNIG5m_centres":c["sector_centres_inside_preserved_C1_CNIG5m_Alcanices_or_Muelas_panels_NOT_full_coverage"]} for c in route_set],
   "source_catalogue_new_2km_cells":len(candidate),
   "ranked_review_cells":len(shortlist),"max_original_DGT_downloads_not_authorized":len(selected_ids)},ensure_ascii=False))
 return obj

def main():
 p=argparse.ArgumentParser()
 for name in ("g3","g4","g5","b1","catalogues","json","geojson","markdown"):
  p.add_argument("--"+name,required=True,type=Path)
 a=p.parse_args()
 run(a.g3,a.g4,a.g5,a.b1,a.catalogues,a.json,a.geojson,a.markdown)
if __name__=="__main__":main()
