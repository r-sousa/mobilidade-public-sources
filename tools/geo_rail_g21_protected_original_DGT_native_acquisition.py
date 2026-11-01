#!/usr/bin/env python3
"""G21 original DGT2m exact G20 source IDs, protected-only acquisition/verify.

Credentials MUST be read only by the protected dgt-cdd GitHub environment
in an explicitly dispatched protected MAIN workflow. Signed asset hrefs,
authentication or cookies never appear in receipt or publication. Exact
original 1km GeoTIFF hash, CRS, transform, pixels verified twice in
separate no-secret publication job. Source research references NOT stations.
"""
from __future__ import annotations
import argparse,hashlib,json,math,os,re
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from geo_rail_pt_cdd_authenticated import (
 authenticated_session,request_bounded_redirects,read_metadata,allowed_url,
 TRUSTED_AUTH_REDIRECTS,TRUSTED_DATA_REDIRECTS,STAC,COLLECTION,IntakeError)
from geo_rail_pt_cdd_pair_pilot import download_small_native

MANIFEST_SHA=None
TILE=re.compile(r"^MDT-2m-(\d{3})(\d{3})-(0[67])-2024$")
MAX_NEW_TILES=54
MAX_BYTES_PER_TILE=25_000_000
MAX_TOTAL_BYTES=160_000_000
NATIVE_PIXELS_PER_TILE=250000
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as fd:
  for b in iter(lambda:fd.read(2**20),b""):h.update(b)
 return h.hexdigest()

def review(path):
 root=json.loads(path.read_text())
 if (root["new_original_DGT_1km_tiles_targeted"]>MAX_NEW_TILES or
   len(root["DGT_new_target_manifest_exact_verified_public_source_metadata"])!=root["new_original_DGT_1km_tiles_targeted"] or
   root["mandatory_urban_markets"]!=["Vila Real","Bragança"] or not root["Sanabria_excluded"] or
   not root["DGT_credentialed_original_source_requires_manual_dispatch_on_protected_main_and_environment"]=="dgt-cdd" or
   not root["do_not_trigger_credentialed_acquisition_via_branch_push_or_PR"] or
   not root["no_new_DGT_CDD_download_in_this_planning_stage"] or
   root["Fxx_accepted"] or root["Site_authorized"]):
  raise ValueError("G21_source_manifest_scope_credential_boundary_invalid")
 ids={}
 for z in root["DGT_new_target_manifest_exact_verified_public_source_metadata"]:
  ident=z["producer_ID"]
  match=TILE.fullmatch(ident)
  if not match or ident in ids or z["actual_original_GeoTIFF_bytes_present"] or z["native_2m_pixels_proven"]:
   raise ValueError("not_exact_unacquired_unique_reviewed_native_2m_source_identity")
  col,row=int(match.group(1)),int(match.group(2))
  expected=[(col-200)*1000,(row-301)*1000,(col-199)*1000,(row-300)*1000]
  if z["col_row"]!=[col,row] or z["expected_original_GeoTIFF_bbox_EPSG3763_m"]!=expected:
   raise ValueError("source_DGT_native_tile_grid_position_drift")
  ids[ident]=z
 if not ids:raise ValueError("empty_G20_original_DGT_acquisition_not_authorized")
 return root,ids

def original_qa(path,entry):
 if path.stat().st_size>MAX_BYTES_PER_TILE or path.stat().st_size<1000:
  raise ValueError("DGT_native_source_file_byte_size_out_of_bounds")
 with rasterio.open(path) as ds:
  if ds.driver!="GTiff" or ds.count!=1 or ds.crs is None or ds.crs.to_epsg()!=3763:
   raise ValueError("original_DGT_single_band_native_EPSG3763_required")
  if (ds.width,ds.height)!=(500,500) or any(abs(x-2)>.001 for x in ds.res):
   raise ValueError("original_DGT_natively_500x500_2m_required")
  if any(abs(a-b)>.005 for a,b in zip(ds.bounds,entry["expected_original_GeoTIFF_bbox_EPSG3763_m"])):
   raise ValueError("unexpected_original_DGT_native_raster_cell_bounds")
  z=ds.read(1,masked=True)
  data=z.compressed()
  if (data.size!=NATIVE_PIXELS_PER_TILE or np.ma.count_masked(z) or
     not np.isfinite(data).all() or float(data.min())< -500 or float(data.max())>4000):
   raise ValueError("original_DGT_native_terrain_pixels_missing_or_invalid")
  return {"source_original_bytes":path.stat().st_size,
   "source_original_sha256":sha(path),
   "EPSG":3763,"source_resolution_m":2,
   "source_native_valid_pixels":len(data),
   "source_nodata_pixels":0,
   "original_native_grid_bbox_EPSG3763_m":list(entry["expected_original_GeoTIFF_bbox_EPSG3763_m"]),
   "source_terrain_original_z_min_max_m":[round(float(data.min()),3),round(float(data.max()),3)],
   "independent_vertical_survey_benchmark_not_done":True}

def original_urls(session,manifest):
 wanted={z["producer_ID"] for z in manifest["DGT_new_target_manifest_exact_verified_public_source_metadata"]}
 result={};receipts=[]
 for seed in manifest["selected_reference_points_NOT_real_stations"]:
  xy=[tuple(q) for q in seed["source_grid_3x3km_1km_cells"]]
  x0=min((x-200)*1000 for x,y in xy)
  x1=max((x-199)*1000 for x,y in xy)
  y0=min((y-301)*1000 for x,y in xy)
  y1=max((y-300)*1000 for x,y in xy)
  box=list(transform_bounds("EPSG:3763","EPSG:4326",x0,y0,x1,y1,densify_pts=8))
  bbox=[box[0]-.003,box[1]-.003,box[2]+.003,box[3]+.003]
  response=request_bounded_redirects(session,"POST",STAC,TRUSTED_AUTH_REDIRECTS,
     json_body={"bbox":bbox,"collections":[COLLECTION],"limit":250},
     stream=True,phase="G21_DGT_mandatory_city_G20_target_original_metadata")
  doc,digest=read_metadata(response)
  items=doc.get("features")
  if (doc.get("type")!="FeatureCollection" or not isinstance(items,list) or len(items)>250 or
    any(q.get("rel")=="next" for q in doc.get("links",[]) if isinstance(q,dict))):
   raise IntakeError("incomplete_or_unbounded_G21_native_producer_STAC")
  needed={f"MDT-2m-{x:03d}{y:03d}-"+("07-2024" if seed["mandatory_urban_market"]=="Vila_Real" else "06-2024")
    for x,y in xy}&wanted
  if not needed.issubset({j.get("id") for j in items}):
   raise IntakeError("original_STAC_does_not_contain_required_selected_source_tile")
  for tile in needed:
   item=[v for v in items if v.get("id")==tile and v.get("collection")==COLLECTION]
   if len(item)!=1:raise IntakeError("ambiguous_reviewed_original_DGT_tile_ID")
   assets=item[0].get("assets")
   a=assets.get("data") if isinstance(assets,dict) else None
   url=a.get("href") if isinstance(a,dict) else None
   if not (isinstance(a,dict) and str(a.get("type","")).lower().startswith(("image/tiff","image/geotiff")) and
     allowed_url(url,TRUSTED_DATA_REDIRECTS)):
    raise IntakeError("invalid_or_unapproved_DGT_original_source_asset")
   result[tile]=url
  receipts.append({"study_seed_id":seed["id"],"official_STAC_response_SHA256":digest,
   "number_of_required_still_unacquired_source_items_verified_in_response":len(needed)})
 if set(result)!=wanted:raise IntakeError("G21_original_DGT_sources_not_all_recovered_from_live_STAC")
 return result,receipts

def acquire(manifestpath,folder):
 if folder.exists():raise ValueError("new_source_staging_directory_must_not_exist")
 m,ids=review(manifestpath)
 user=os.environ.get("DGT_CDD_USERNAME")
 password=os.environ.get("DGT_CDD_PASSWORD")
 if not(user and password):raise IntakeError("protected_main_DGT_CDD_credentials_missing")
 folder.mkdir(parents=True,exist_ok=False)
 origin=authenticated_session(user,password)
 rows=[];total=0
 try:
  urls,receipts=original_urls(origin,m)
  for ident in sorted(ids):
   dest=folder/(ident+".tif")
   size,digest=download_small_native(origin,urls[ident],dest)
   total+=size
   if total>MAX_TOTAL_BYTES:raise ValueError("G21_native_DGT_39_source_tile_budget_exceeded")
   qa=original_qa(dest,ids[ident])
   if qa["source_original_sha256"]!=digest or qa["source_original_bytes"]!=size:
    raise ValueError("download_original_SHA_and_raster_integrity_disagree")
   rows.append({"producer_original_ID":ident,**qa})
 finally:origin.close()
 receipt={"mission":"MN-GEO-RAIL-001","stage":"G21_secure_original_DGT_native_MDT2m_exact_G20_manifest",
   "original_review_manifest_sha256":sha(manifestpath),
   "UTC":datetime.now(timezone.utc).isoformat(),
   "producer":"Direção-Geral do Território","licence":"DGT CC BY 4.0; cite DGT Centro de Dados",
   "source_original_tiles_acquired":len(rows),
   "source_original_native_pixels_verified":sum(x["source_native_valid_pixels"] for x in rows),
   "source_original_native_byte_count":total,
   "source_STAC_response_hash_receipts_without_URLs":receipts,
   "native_GeoTIFF_producer_source_checksums_and_QA":rows,
   "source_authentication_signed_asset_urls_or_secrets_persisted":False,
   "native_raster_files_are_not_railway_stations_or_tracks":True,
   "not_original_ground_CDD_vertical_accuracy_survey":True,
   "Sanabria_excluded":True,"Fxx_accepted":False,"Site_authorized":False}
 (folder/"G21-original-DGT-2m-source-QA.json").write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
 verify(manifestpath,folder)
 return receipt

def verify(manifestpath,folder):
 m,ids=review(manifestpath)
 receipt=json.loads((folder/"G21-original-DGT-2m-source-QA.json").read_text())
 if (receipt["original_review_manifest_sha256"]!=sha(manifestpath) or
     receipt["source_original_tiles_acquired"]!=len(ids) or
     receipt["source_authentication_signed_asset_urls_or_secrets_persisted"] or
     receipt["Fxx_accepted"] or receipt["Site_authorized"]):
  raise ValueError("G21_original_source_receipt_scope_or_hash_drift")
 old={x["producer_original_ID"]:x for x in receipt["native_GeoTIFF_producer_source_checksums_and_QA"]}
 if set(old)!=set(ids):raise ValueError("G21_downloaded_source_ids_not_exact_manifest")
 nbytes=0
 for tile in ids:
  path=folder/(tile+".tif")
  qa=original_qa(path,ids[tile])
  if old[tile]!={"producer_original_ID":tile,**qa}:
   raise ValueError("source_original_GeoTIFF_pixel_SHA_or_origin_drift_"+tile)
  nbytes+=qa["source_original_bytes"]
 if nbytes!=receipt["source_original_native_byte_count"]:
  raise ValueError("G21_source_total_native_bytes_changed")
 return receipt

def main():
 a=argparse.ArgumentParser()
 a.add_argument("--manifest",type=Path,required=True)
 a.add_argument("--stage",type=Path,required=True)
 g=a.add_mutually_exclusive_group(required=True)
 g.add_argument("--acquire",action="store_true")
 g.add_argument("--verify",action="store_true")
 v=a.parse_args()
 data=acquire(v.manifest,v.stage) if v.acquire else verify(v.manifest,v.stage)
 print("G21_NATIVE_ORIGINAL_QA="+json.dumps({
   "source_original_verified_tiles":data["source_original_tiles_acquired"],
   "original_2m_pixels":data["source_original_native_pixels_verified"],
   "original_bytes":data["source_original_native_byte_count"],
   "no_secret_persisted":True},separators=(",",":")))
if __name__=="__main__":main()
