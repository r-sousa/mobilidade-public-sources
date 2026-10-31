#!/usr/bin/env python3
"""G3 acquire DGT original MDT2m original cells only from reviewed pinned source IDs.

Reviewed G3 proposed 80 tiles; 4 are ALREADY original sources in Mirandela.
Avoid re-download of the whole overlapping 2km group: 76 NEW original source
1km2 tiles in 19 non-overlapping sectors, not 80 new physical km2.
Three bounded independently verifiable batches: Vila Real (7 study sectors),
Bragança (5 sectors), inter-city research (7 NEW sectors). This is NOT a railway
alignment or station choice. Credentials only on manual protected-main GitHub
Actions job with existing dgt-cdd Environment, never in published QA.
"""
from __future__ import annotations
import argparse,hashlib,json,math,os,re
from pathlib import Path
from datetime import datetime,timezone
from geo_rail_pt_b1_native32 import source_tiles_for_group,download_small_native
from geo_rail_pt_cdd_authenticated import authenticated_session,IntakeError
from geo_rail_pt_cdd_grid12 import compare_shared_edges

PINNED_G3_SHA256="ab001fb17ba359d939294b505bc199d459d474095f255f17099c1cdaafd57d9c"
BATCHES={"vila_real":7,"braganca":5,"regional":7}
# EXACT 13 previously acquired original Mirandela producer tiles (12-tile 3x4 grid plus NP159).
PRIOR_MIRANDELA_IDS={f"MDT-2m-{c}{r}-09-2024"
 for c in (280,281,282) for r in (507,508,509,510)}|{"MDT-2m-279503-09-2024"}
REVIEWED_DUPLICATE_BLOCK=[80000,206000,82000,208000]

PAT=re.compile(r"^MDT-2m-(\d{3})(\d{3})-(\d{2})-(20\d{2})$")
MAX_ONE_SOURCE_BYTES=25_000_000
MAX_BATCH_SOURCE_BYTES=240_000_000

def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()

def parse_id(id):
 m=PAT.fullmatch(str(id))
 if not m:raise ValueError("not_a_pinned_original_DGT2m_source_id")
 col,row=int(m.group(1)),int(m.group(2))
 if not (190<=col<=360 and 430<=row<=590):raise ValueError("tile_grid_outside_reviewed_Norte_corridor")
 return col,row

def tile_bounds(id):
 col,row=parse_id(id)
 return [(col-200)*1000,(row-301)*1000,(col-199)*1000,(row-300)*1000]

def load_review(path):
 if sha(path)!=PINNED_G3_SHA256:raise ValueError("G3_original_source_review_byte_digest_changed")
 d=json.loads(Path(path).read_text())
 if (d.get("mandatory_cities")!=["Vila Real","Bragança"] or
     not d.get("Sanabria_excluded") or
     not d.get("lattice_path_is_not_a_railway_or_road_alignment") or
     d.get("real_original_DGT_2m_raster_source_pixels_newly_acquired")!=0 or
     d.get("two_kilometre_cells_with_four_original_DGT_tile_IDs_and_real_DSM_pixels")!=753 or
     d.get("native_source_tiles_next_acquisition_target_metadata_only")!=80 or
     d.get("Fxx_accepted") or d.get("Site_authorized") or
     len(d.get("DGT_five_original_STAC_catalogue_receipts",[]))!=5):
  raise ValueError("G3_source_review_fails_provenance_scope_and_source_identity")
 groups=d.get("new_DGT2m_metadata_only_priority_targets")
 if not isinstance(groups,list) or len(groups)!=20:raise ValueError("G3_expected_twenty_reviewed_real_source_cells")
 ids=[]
 excluded=[]
 counter={k:0 for k in BATCHES}
 ready=[]
 for i,g in enumerate(groups):
  x,y,x1,y1=g["grid_epsg3763"]
  if (x1-x,y1-y)!=(2000,2000) or x%2000 or y%2000:
   raise ValueError("G3_target_not_official_2km_original_tile_aligned")
  category=g["target_category"]
  if category=="regional":batch="regional"
  elif category=="local" and x<70000:batch="vila_real"
  elif category=="local" and x>=100000:batch="braganca"
  else:raise ValueError("target_crosses_unapproved_city_or_intercity_source_scope")
  originals=g["official_original_DGT2m_1km_tile_IDs"]
  if not g.get("source_tile_ids_from_five_official_catalogues") or g.get("already_acquired_original_ground_pixels"):
   raise ValueError("G3_original_source_tile_not_reviewed_or_already_acquired")
  if not isinstance(originals,list) or len(originals)!=4:raise ValueError("four_original_DGT2m_tiles_required")
  expected={(x//1000+200+a,y//1000+301+b) for a in (0,1) for b in (0,1)}
  actual={parse_id(t) for t in originals}
  if len(actual)!=4 or actual!=expected:raise ValueError("G3_source_tile_ids_do_not_match_PT_TM06_grid")
  # Earlier G3 source-only shortlist could see the four original Mirandela tiles
  # as fresh metadata. Reject already downloaded producer originals BEFORE DGT login.
  if set(originals)&PRIOR_MIRANDELA_IDS:
   if (g["grid_epsg3763"]!=REVIEWED_DUPLICATE_BLOCK or
       len(set(originals)&PRIOR_MIRANDELA_IDS)!=4 or category!="regional"):
    raise ValueError("unreviewed_intersection_with_prior_original_DGT_sources")
   excluded.append((g["grid_epsg3763"],tuple(originals)))
   continue
  counter[batch]+=1;ids.extend(originals)
  ready.append({"grid_epsg3763":[x,y,x1,y1],"tile_ids":originals,
      "batch":batch,"group_id":f"G3-{batch}-{i+1:02d}"})
 if len(excluded)!=1 or len(excluded[0][1])!=4:
  raise ValueError("one_reviewed_4km2_Mirandela_overlap_must_be_excluded")
 # Guard against repeating any of the 32 already verified B1 city original sources.
 b1_path=Path("configs/MN-GEO-RAIL-001-B1-DGT32-source-IDs.json")
 if not b1_path.is_file():raise ValueError("previous_B1_original_source_inventory_missing")
 b1=json.loads(b1_path.read_text())
 old={id for g in b1["groups"] for id in g["tile_ids"]}
 if len(old)!=32 or set(ids)&(old|PRIOR_MIRANDELA_IDS):
  raise ValueError("refusing_to_reacquire_previously_acquired_DGT_original_source")
 if counter!=BATCHES or len(set(ids))!=76 or len(ids)!=76:
  raise ValueError("unexpected_unreviewed_80_original_DGT_tile_set")
 return ready

def native_raster_QA(path,id):
 import rasterio,numpy as np
 b=tile_bounds(id)
 if not(1024<=path.stat().st_size<=MAX_ONE_SOURCE_BYTES):
  raise ValueError("native_original_GeoTIFF_bytes_exceed_per_file_budget")
 with rasterio.open(path) as ds:
  if ds.driver!="GTiff" or ds.count!=1 or ds.crs is None or ds.crs.to_epsg()!=3763:
   raise ValueError("not_original_DGT_2m_EPSG3763_one_band_GeoTIFF")
  if ds.width!=500 or ds.height!=500 or any(abs(v-2)>.0001 for v in ds.res):
   raise ValueError("DGT_original_source_not_2m_resolution_500x500")
  if any(abs(v-w)>.002 for v,w in zip(ds.bounds,b)):
   raise ValueError("original_DGT_source_actual_bounds_disagree_with_producer_grid_id")
  a=ds.read(1,masked=True)
  if a.count()!=250000 or int(np.ma.count_masked(a)):
   raise ValueError("real_original_DGT2m_raster_has_NoData")
  v=a.compressed()
  if not np.isfinite(v).all() or v.min()<-500 or v.max()>4000:
   raise ValueError("source_original_DGT2m_unreasonable_terrain_values")
  return {"native_original_source_tile_id":id,"bbox_pttm06_m":b,
          "horizontal_crs":"EPSG:3763","resolution_m":2,
          "source_nodata_pixels":0,"real_valid_ground_pixels":250000,
          "range_m":[float(v.min()),float(v.max())],
          "verified_independent_vertical_RMSE":False}

def src(stage,id):
 parse_id(id);return stage/(id+".tif")

def four_seams(stage,g):
 ids={(parse_id(id)):id for id in g["tile_ids"]}
 cols=sorted({z[0] for z in ids});rows=sorted({z[1] for z in ids})
 s=[]
 for row in rows:
  a,b=ids[cols[0],row],ids[cols[1],row]
  s.append({"a":a,"b":b,**compare_shared_edges(src(stage,a),src(stage,b),"west_east")})
 for col in cols:
  a,b=ids[col,rows[1]],ids[col,rows[0]]
  s.append({"a":a,"b":b,**compare_shared_edges(src(stage,a),src(stage,b),"north_south")})
 if len(s)!=4 or any(v["pairs_valid"]!=500 for v in s):
  raise ValueError("four_original_DGT_source_cell_edges_not_all_valid")
 return s

def create_mosaic(stage,g):
 import rasterio,numpy as np
 from rasterio.transform import from_origin
 x,y,x1,y1=g["grid_epsg3763"]
 with rasterio.open(src(stage,g["tile_ids"][0])) as a:dtype=a.dtypes[0]
 if not np.issubdtype(np.dtype(dtype),np.number):
  raise ValueError("non_numeric_original_DGT_source")
 full=np.zeros((1000,1000),dtype=dtype)
 for id in g["tile_ids"]:
  col,row=parse_id(id)
  left=((col-200)*1000-x)//2
  top=(2000-((row-301)*1000-y)-1000)//2
  if left not in (0,500) or top not in (0,500):
   raise ValueError("native_source_outside_exact_original_2km_group")
  with rasterio.open(src(stage,id)) as ds:
   z=ds.read(1)
   if z.dtype!=full.dtype:raise ValueError("mixed_source_original_DGT_dtype")
   full[top:top+500,left:left+500]=z
 name=f"{g['group_id']}-original-DGT2m-2000m-ground-mosaic.tif"
 output=stage/name
 with rasterio.open(output,"w",driver="GTiff",count=1,width=1000,height=1000,
     dtype=dtype,crs="EPSG:3763",transform=from_origin(x,y1,2,2),
     compress="DEFLATE",tiled=True,blockxsize=256,blockysize=256,
     predictor=(3 if np.issubdtype(full.dtype,np.floating) else 2)) as ds:
  ds.write(full,1)
  ds.update_tags(DGT_original_source="Direção-Geral do Território / CDD",
      licensed_CC_BY_4_0="attribution to DGT mandatory",
      screening_only="G3 exploratory acquisition, NOT railway track or station")
 return output

def verify_mosaic(stage,g,path):
 import rasterio,numpy as np
 x,y,x1,y1=g["grid_epsg3763"]
 with rasterio.open(path) as ds:
  if (ds.crs is None or ds.crs.to_epsg()!=3763 or
     ds.driver!="GTiff" or ds.count!=1 or
     (ds.width,ds.height)!=(1000,1000) or
     any(abs(a-b)>.002 for a,b in zip(ds.bounds,(x,y,x1,y1)))):
   raise ValueError("native_source_mosaic_bad_geometry")
  got=ds.read(1,masked=True)
  if got.count()!=1_000_000:raise ValueError("mosaic_original_source_data_missing")
  for id in g["tile_ids"]:
   col,row=parse_id(id)
   left=((col-200)*1000-x)//2
   top=(2000-((row-301)*1000-y)-1000)//2
   with rasterio.open(src(stage,id)) as original:
    z=original.read(1)
   if not np.array_equal(got.data[top:top+500,left:left+500],z):
    raise ValueError("new_G3_mosaic_not_pixel_exact_with_original_source_tile")
 return {"cell_count":1000000,"all_cells_valid":True,
         "pixel_exact_native_sources":4,"source_seams":4}

def batch_groups(all_groups,batch):
 if batch not in BATCHES:raise ValueError("unknown_or_unauthorized_DGT_original_source_batch")
 gs=[g for g in all_groups if g["batch"]==batch]
 if len(gs)!=BATCHES[batch]:raise ValueError("missing_reviewed_DGT_original_source_groups_in_batch")
 return gs

def verify(stage,all_groups,batch,receipt):
 gs=batch_groups(all_groups,batch)
 if (receipt["batch"]!=batch or
     receipt["real_original_DGT2m_tile_count"]!=len(gs)*4 or
     receipt["real_native_2m_ground_area_km2"]!=len(gs)*4 or
     receipt["valid_original_ground_pixels"]!=len(gs)*1_000_000 or
     len(receipt["mosaics"])!=len(gs) or
     len(receipt["native_originals"])!=len(gs)*4 or
     receipt["review_original_source_SHA256"]!=PINNED_G3_SHA256 or
     receipt["Sanabria_excluded"] is not True or
     receipt["Fxx_accepted"] or receipt["Site_authorized"]):
  raise ValueError("incorrect_protected_DGT2m_G3_batch_receipt")
 original_records={r["id"]:r for r in receipt["native_originals"]}
 mosaic_records={r["group_id"]:r for r in receipt["mosaics"]}
 if len(original_records)!=len(gs)*4 or len(mosaic_records)!=len(gs):
  raise ValueError("duplicate_original_DGT2m_or_mosaic_receipts")
 for g in gs:
  for id in g["tile_ids"]:
   p=src(stage,id);q=original_records[id]
   if q["bytes"]!=p.stat().st_size or q["sha256"]!=sha(p) or q["native_original_QA"]!=native_raster_QA(p,id):
    raise ValueError("independent_source_original_reopen_QA_failed")
  m=mosaic_records[g["group_id"]];mosaic=stage/m["file"]
  if (m["sha256"]!=sha(mosaic) or m["bytes"]!=mosaic.stat().st_size or
      m["pixel_exact_QA"]!=verify_mosaic(stage,g,mosaic) or
      m["seams"]!=four_seams(stage,g)):
   raise ValueError("independent_original_source_seams_or_mosaic_QA_failed")
 return True

def acquire(stage,all_groups,batch):
 gs=batch_groups(all_groups,batch)
 username=os.environ.get("DGT_CDD_USERNAME","")
 pwd=os.environ.get("DGT_CDD_PASSWORD","")
 if not(username and pwd):raise IntakeError("protected_DGT_CDD_environment_secrets_missing")
 stage.mkdir(parents=True,exist_ok=False)
 source=[];total=0;stac=[]
 session=authenticated_session(username,pwd)
 try:
  for g in gs:
   links,digest=source_tiles_for_group(session,g)
   stac.append({"group_id":g["group_id"],"STAC_source_receipt_SHA256":digest})
   for id in g["tile_ids"]:
    target=src(stage,id)
    count,digest=download_small_native(session,links[id],target)
    total+=count
    if total>MAX_BATCH_SOURCE_BYTES:raise ValueError("protected_original_source_batch_bytes_over_cap")
    source.append({"id":id,"bytes":count,"sha256":digest,
        "native_original_QA":native_raster_QA(target,id)})
 finally:session.close()
 mosaic_records=[]
 for g in gs:
  seams=four_seams(stage,g)
  path=create_mosaic(stage,g)
  mosaic_records.append({"group_id":g["group_id"],"file":path.name,
   "grid_epsg3763":g["grid_epsg3763"],"bytes":path.stat().st_size,
   "sha256":sha(path),"seams":seams,
   "pixel_exact_QA":verify_mosaic(stage,g,path)})
 receipt={
   "mission":"MN-GEO-RAIL-001","stage":"G3_actual_producer_original_DGT2m_source_coverage",
   "observed_utc":datetime.now(timezone.utc).isoformat(),
   "batch":batch,"review_original_source_SHA256":PINNED_G3_SHA256,
   "mandatory_service_cities":["Vila Real","Bragança"],
   "station_city_centre_required":False,"Sanabria_excluded":True,
   "licence":"DGT open data CC BY 4.0 with attribution Direção-Geral do Território",
   "no_signed_source_asset_URLs_or_credentials_persisted":True,
   "source_original_tiles_STAC_response_hashes":stac,
   "source_original_bytes":total,
   "real_original_DGT2m_tile_count":len(source),
   "real_native_2m_ground_area_km2":len(source),
   "valid_original_ground_pixels":len(source)*250000,
   "source_original_nodata_pixels":0,
   "source_four_tile_seams":len(mosaic_records)*4,
   "source_adjacent_valid_cell_pairs":len(mosaic_records)*2000,
   "native_originals":source,"mosaics":mosaic_records,
   "continuous_native_2m_DGT_railway_corridor_verified":False,
   "railway_vertical_datum_RMSE_verified":False,
   "real_road_network_driving_access_verified":False,
   "station_and_railway_alignment_approved":False,
   "Fxx_accepted":False,"Site_authorized":False}
 name=f"G3-DGT-native2m-{batch}-original-source-QA.json"
 (stage/name).write_text(json.dumps(receipt,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
 verify(stage,all_groups,batch,receipt)
 return receipt

def main():
 a=argparse.ArgumentParser(description=__doc__)
 a.add_argument("--review",type=Path,required=True)
 a.add_argument("--batch",choices=list(BATCHES),required=True)
 p=a.add_mutually_exclusive_group(required=True)
 p.add_argument("--acquire",type=Path)
 p.add_argument("--verify",type=Path)
 args=a.parse_args()
 groups=load_review(args.review)
 if args.acquire:res=acquire(args.acquire,groups,args.batch)
 else:
  res=json.loads((args.verify/f"G3-DGT-native2m-{args.batch}-original-source-QA.json").read_text())
  verify(args.verify,groups,args.batch,res)
 print(json.dumps({"status":"REAL_G3_DGT_2M_ORIGINALS_AND_SOURCE_MOSAICS_INDEPENDENT_QA",
  "batch":args.batch,"new_original_ground_km2":res["real_native_2m_ground_area_km2"],
  "original_source_files":res["real_original_DGT2m_tile_count"],
  "valid_2m_source_pixels":res["valid_original_ground_pixels"]}))
if __name__=="__main__":main()
