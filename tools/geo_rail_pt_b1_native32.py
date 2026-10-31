#!/usr/bin/env python3
"""MN-GEO-RAIL-001 B1: acquire small DGT native 2m terrestrial grids.

Only manually dispatched from branch-protected MAIN, environment dgt-cdd.
No credential, session cookie, or signed source download link is persisted.
Eight exact source groups are approved AFTER comparing real OSM road geometry
and real GLO30 DSM relief. Vila Real and Bragança compulsory service areas;
these are peripheral acquisition trial sectors, NOT stations/rail alignments.
Do not acquire Sanabria. Four original native DGT 1km source tiles per sector.
"""
from __future__ import annotations
import argparse,hashlib,json,math,os,re
from pathlib import Path
from datetime import datetime,timezone
from tempfile import TemporaryDirectory

from geo_rail_pt_cdd_authenticated import (
 authenticated_session,request_bounded_redirects,read_metadata,allowed_url,
 TRUSTED_AUTH_REDIRECTS,TRUSTED_DATA_REDIRECTS,STAC,COLLECTION,IntakeError)
from geo_rail_pt_cdd_pair_pilot import download_small_native
from geo_rail_pt_cdd_grid12 import compare_shared_edges

CITY=("vila_real","braganca")
CONFIG="configs/MN-GEO-RAIL-001-B1-DGT32-source-IDs.json"
PINNED_REVIEW_SHA256="79c8811bf8be1a5c92d6aac1089b9a558db1ba0e6819ac3a07c250b1f38e1cfc"
PATTERN=re.compile(r"^MDT-2m-(\d{3})(\d{3})-(0[67])-2024$")
MAX_PER_TILE=25_000_000
MAX_CITY_BYTES=110_000_000
NATIVE_PIXEL_M=2
NATIVE_CELLS=250000
SOURCE_ORIGINAL_LICENCE="DGT Centro de Dados, CC BY 4.0; attribution Direção-Geral do Território"
ALLOWED_COLUMNS=(220,221,240,241,234,235,310,311,316,317)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            b=f.read(1024*1024)
            if not b:break
            h.update(b)
    return h.hexdigest()

def parse_tile(t):
    z=PATTERN.fullmatch(str(t))
    if not z:raise ValueError("non-approved_DGT_native_source_ID")
    c,r=int(z.group(1)),int(z.group(2))
    if c not in ALLOWED_COLUMNS or not 450<=r<=560:
        raise ValueError("source_original_grid_outside_reviewed_regions")
    return c,r,z.group(3)

def read_review(config):
    d=json.loads(Path(config).read_text(encoding="utf8"))
    if (d.get("review_receipt_sha256")!=PINNED_REVIEW_SHA256 or
        d.get("mandatory_cities")!=list(CITY) or d.get("sanabria_excluded") is not True
        or d.get("active_railway_line_defined") is not False
        or d.get("station_location_determined") is not False):
        raise ValueError("unreviewed_DGT_native_study_scope")
    gs=d.get("groups")
    if not isinstance(gs,list) or len(gs)!=8:raise ValueError("expected_eight_source_groups")
    if {(g["city"],g["direction"]) for g in gs}!={(s,q) for s in CITY for q in ("W","E","N","S")}:
        raise ValueError("missing_mandatory_city_geographic_alternatives")
    ids=[]
    for g in gs:
        x0,y0,x1,y1=g["grid_epsg3763"]
        if x1-x0!=2000 or y1-y0!=2000 or x0%1000 or y0%1000:
            raise ValueError("not_exact_DGT_2km_grid")
        wanted={(x0//1000+200+dc,y0//1000+301+dr) for dr in (0,1) for dc in (0,1)}
        actual=set()
        for t in g["tile_ids"]:
            c,r,month=parse_tile(t);actual.add((c,r))
            if (g["city"]=="vila_real")!=(month=="07"):
                raise ValueError("wrong_edition_for_city")
            ids.append(t)
        if len(g["tile_ids"])!=4 or actual!=wanted:
            raise ValueError("group_does_not_match_exact_2km_source_indices")
    if len(ids)!=32 or len(set(ids))!=32:
        raise ValueError("repeated_or_missing_original_DGT_sources")
    return d

def city_groups(config,city):
    if city not in CITY:raise ValueError("unknown_or_unapproved_city")
    groups=[g for g in config["groups"] if g["city"]==city]
    if len(groups)!=4:raise ValueError("not_four_reviewed_alternatives_per_city")
    return groups

def source_tiles_for_group(session,g):
    from rasterio.warp import transform_bounds
    x0,y0,x1,y1=g["grid_epsg3763"]
    box=list(transform_bounds("EPSG:3763","EPSG:4326",x0,y0,x1,y1,densify_pts=5))
    bbox=[box[0]-.003,box[1]-.003,box[2]+.003,box[3]+.003]
    response=request_bounded_redirects(session,"POST",STAC,TRUSTED_AUTH_REDIRECTS,
        json_body={"bbox":bbox,"collections":[COLLECTION],"limit":250},
        stream=True,phase="DGT_2km_native_source_STAC")
    doc,digest=read_metadata(response)
    items=doc.get("features")
    if (doc.get("type")!="FeatureCollection" or not isinstance(items,list) or
        len(items)>250 or any(isinstance(q,dict) and q.get("rel")=="next"
              for q in doc.get("links",[]))):
        raise IntakeError("incomplete_or_unbounded_exact_DGT_STAC")
    out={}
    for id in g["tile_ids"]:
        matches=[q for q in items if isinstance(q,dict) and q.get("id")==id and
                 q.get("collection")==COLLECTION]
        if len(matches)!=1:raise IntakeError("reviewed_original_DGT_source_ID_missing_from_live_STAC")
        assets=matches[0].get("assets")
        a=assets.get("data") if isinstance(assets,dict) else None
        if not isinstance(a,dict) or not str(a.get("type","")).lower().startswith(
               ("image/tiff","image/geotiff")):
            raise IntakeError("native_DGT_source_asset_is_not_a_TIFF")
        url=a.get("href")
        if not allowed_url(url,TRUSTED_DATA_REDIRECTS):
            raise IntakeError("native_DGT_source_url_not_approved")
        out[id]=url
    return out,digest

def native_qa(path,identity):
    import numpy as np,rasterio
    c,r,_=parse_tile(identity)
    bbox=[(c-200)*1000,(r-301)*1000,(c-199)*1000,(r-300)*1000]
    if path.stat().st_size<1024 or path.stat().st_size>MAX_PER_TILE:
        raise ValueError("native_GeoTIFF_bytes_outside_reviewed_budget")
    with rasterio.open(path) as ds:
        if ds.crs is None or ds.crs.to_epsg()!=3763 or ds.driver!="GTiff" or ds.count!=1:
            raise ValueError("DGT_original_source_not_single_band_EPSG3763_GeoTIFF")
        if (ds.width,ds.height)!=(500,500) or any(abs(a-2)>0.0001 for a in ds.res):
            raise ValueError("DGT_original_not_2m_500x500")
        if any(abs(a-b)>0.002 for a,b in zip(ds.bounds,bbox)):
            raise ValueError("DGT_original_bbox_not_matching_tile_ID")
        z=ds.read(1,masked=True)
        if z.count()!=NATIVE_CELLS or int(np.ma.count_masked(z))!=0:
            raise ValueError("DGT_original_source_has_masked_pixels")
        data=z.compressed()
        if not np.isfinite(data).all() or float(data.min())< -500 or float(data.max())>4000:
            raise ValueError("DGT_source_nonfinite_or_out_of_country_elevations")
        return {"bbox_pttm06":bbox,"pixels":NATIVE_CELLS,
                "valid_pixels":int(z.count()),"nodata_pixels":0,"dtype":ds.dtypes[0],
                "range_m":[float(data.min()),float(data.max())],
                "horizontal_crs":"EPSG:3763","pixel_size_m":2,
                "vertical_datum_surveyed_here":False}

def source_file(stage,id):
    parse_tile(id)
    return stage/(id+".tif")

def create_mosaic(stage,g):
    import rasterio,numpy as np
    from rasterio.transform import from_origin
    x0,y0,x1,y1=g["grid_epsg3763"]
    first=source_file(stage,g["tile_ids"][0])
    with rasterio.open(first) as f:dtype=f.dtypes[0]
    if not np.issubdtype(np.dtype(dtype),np.number):
        raise ValueError("non_numeric_DGT_native_terrain")
    merged=np.zeros((1000,1000),dtype=dtype)
    for ident in g["tile_ids"]:
        c,r,_=parse_tile(ident)
        dx=(c-200)*1000-x0;dy=(r-301)*1000-y0
        col=dx//2;row=(2000-dy-1000)//2
        if col not in (0,500) or row not in (0,500):
            raise ValueError("tile_not_aligned_in_official_native_2km_group")
        with rasterio.open(source_file(stage,ident)) as ds:
            z=ds.read(1)
            if z.dtype!=merged.dtype:raise ValueError("mixed_native_dtypes")
            merged[row:row+500,col:col+500]=z
    if not np.isfinite(merged).all():raise ValueError("invalid_source_merge_terrain")
    out=stage/f"{g['city']}-{g['direction']}-DGT-native-2m-2x2km-mosaic.tif"
    with rasterio.open(out,"w",driver="GTiff",count=1,width=1000,height=1000,
        dtype=dtype,crs="EPSG:3763",transform=from_origin(x0,y1,2,2),
        compress="DEFLATE",predictor=(3 if np.issubdtype(merged.dtype,np.floating) else 2),
        tiled=True,blockxsize=256,blockysize=256) as ds:
        ds.write(merged,1)
        ds.update_tags(PRODUCER="Direção-Geral do Território",
                       LICENSE="CC BY 4.0, attribution required",
                       SOURCE="4 full native producer DGT MDT2m GeoTIFFs, exact original cell values",
                       PROVENANCE="PREACCEPTANCE, NOT a railway station or alignment")
    return out

def check_mosaic(stage,g,path):
    import rasterio,numpy as np
    x0,y0,x1,y1=g["grid_epsg3763"]
    with rasterio.open(path) as ds:
        if (ds.crs is None or ds.crs.to_epsg()!=3763 or
            (ds.width,ds.height)!=(1000,1000) or ds.count!=1 or
            any(abs(a-b)>.002 for a,b in zip(ds.bounds,[x0,y0,x1,y1]))):
            raise ValueError("incorrect_native_2km_merged_geometry")
        result=ds.read(1,masked=True)
        if result.count()!=1_000_000:raise ValueError("masked_native_mosaic")
        for ident in g["tile_ids"]:
            c,r,_=parse_tile(ident)
            col=((c-200)*1000-x0)//2
            row=(2000-((r-301)*1000-y0)-1000)//2
            with rasterio.open(source_file(stage,ident)) as src:
                expected=src.read(1)
            if not np.array_equal(result.data[row:row+500,col:col+500],expected):
                raise ValueError("mosaic_source_data_not_byte_for_byte_equal_per_pixel")
    return {"pixels":1_000_000,"valid_pixels":1_000_000,
            "source_native_tiles_matched_pixel_for_pixel":4,
            "source_seams_expected":4,"NoData":0}

def check_seams(stage,g):
    positions={(parse_tile(t)[0],parse_tile(t)[1]):t for t in g["tile_ids"]}
    cols=sorted({x for x,y in positions});rows=sorted({y for x,y in positions})
    seams=[]
    for row in rows:
        a=positions[(cols[0],row)];b=positions[(cols[1],row)]
        seams.append({"tile_A":a,"tile_B":b,**compare_shared_edges(source_file(stage,a),source_file(stage,b),"west_east")})
    for col in cols:
        a=positions[(col,rows[1])];b=positions[(col,rows[0])]
        seams.append({"tile_A":a,"tile_B":b,**compare_shared_edges(source_file(stage,a),source_file(stage,b),"north_south")})
    if len(seams)!=4 or any(s["pairs_valid"]!=500 for s in seams):
        raise ValueError("missing_exact_four_500_pixel_source_edges")
    return seams

def inspect(stage,config,city,receipt):
    groups=city_groups(config,city)
    if (receipt["city"]!=city or receipt["source_tile_count"]!=16 or
        len(receipt["groups"])!=4 or receipt["valid_native_ground_pixels"]!=4_000_000 or
        receipt["Fxx_accepted"] or receipt["Site_authorized"] or
        receipt["new_distinct_native_ground_area_km2"]!=16):
        raise ValueError("unexpected_DGT_original_ground_acquisition_receipt")
    sha_by_id={z["source_tile_id"]:z for z in receipt["native_tile_receipts"]}
    if len(sha_by_id)!=16:raise ValueError("duplicate_source_original_DGT_tile_ids")
    for g in groups:
        for id in g["tile_ids"]:
            r=sha_by_id[id];f=source_file(stage,id)
            if r["bytes"]!=f.stat().st_size or r["sha256"]!=sha(f) or r["native_raster_QA"]!=native_qa(f,id):
                raise ValueError("changed_original_DGT_source_GeoTIFF")
        file=stage/f"{city}-{g['direction']}-DGT-native-2m-2x2km-mosaic.tif"
        m=next(x for x in receipt["groups"] if x["direction"]==g["direction"])
        if (m["mosaic_sha256"]!=sha(file) or m["mosaic_bytes"]!=file.stat().st_size or
            m["mosaic_QA"]!=check_mosaic(stage,g,file) or
            m["original_source_seams"]!=check_seams(stage,g)):
            raise ValueError("native_source_mosaic_reverification_failed")
    return receipt

def acquire(stage,config,city):
    groups=city_groups(config,city)
    stage.mkdir(parents=True,exist_ok=False)
    username=os.environ.get("DGT_CDD_USERNAME","")
    password=os.environ.get("DGT_CDD_PASSWORD","")
    if not(username and password):raise IntakeError("protected_DGT_CDD_secrets_not_configured")
    records=[];source_hashes=[];total=0
    session=authenticated_session(username,password)
    try:
        for g in groups:
            hrefs,stac_sha=source_tiles_for_group(session,g)
            source_hashes.append({"direction":g["direction"],"response_sha256":stac_sha})
            for id in g["tile_ids"]:
                p=source_file(stage,id)
                count,digest=download_small_native(session,hrefs[id],p)
                total+=count
                if total>MAX_CITY_BYTES:raise ValueError("native_DGT_city_aggregate_bytes_over_110MB")
                qa=native_qa(p,id)
                records.append({"source_tile_id":id,"bytes":count,"sha256":digest,
                    "native_raster_QA":qa,"licence":SOURCE_ORIGINAL_LICENCE})
    finally:
        session.close()
    mosaics=[]
    for g in groups:
        seam=check_seams(stage,g)
        p=create_mosaic(stage,g)
        q=check_mosaic(stage,g,p)
        mosaics.append({"direction":g["direction"],"grid_epsg3763":g["grid_epsg3763"],
            "mosaic_file":p.name,"mosaic_sha256":sha(p),
            "mosaic_bytes":p.stat().st_size,"mosaic_QA":q,"original_source_seams":seam})
    receipt={"mission":"MN-GEO-RAIL-001",
       "stage":"B1_original_DGT_2m_native_raster_acquisition",
       "observed_utc":datetime.now(timezone.utc).isoformat(),
       "city":city,"mandatory_city":True,
       "service_station_centre_not_required":True,
       "Sanabria_excluded":True,"producer":"Direção-Geral do Território",
       "licence":"DGT open data CC BY 4.0 with attribution",
       "review_receipt_sha256":PINNED_REVIEW_SHA256,
       "actual_native_producer_GeoTIFF_bytes_acquired":total,
       "source_STAC_query_response_hashes":source_hashes,
       "source_tile_count":len(records),
       "valid_native_ground_pixels":sum(z["native_raster_QA"]["valid_pixels"] for z in records),
       "new_distinct_native_ground_area_km2":16,
       "native_tile_receipts":records,"groups":mosaics,
       "all_source_tile_pixels_and_internal_source_seams_verified":True,
       "network_driving_time_to_peripheral_station_measured":False,
       "peripheral_station_selected":False,
       "railway_alignment_determined":False,
       "vertical_geodetic_control_independently_verified":False,
       "Fxx_accepted":False,"Site_authorized":False,
       "credentials_or_signed_links_persisted":False}
    path=stage/f"B1-DGT-native-MDT2m-{city}-source-QA.json"
    path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf8")
    inspect(stage,config,city,receipt)
    return receipt

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--config",type=Path,default=Path(CONFIG))
    a.add_argument("--city",choices=CITY,required=True)
    p=a.add_mutually_exclusive_group(required=True)
    p.add_argument("--acquire",type=Path)
    p.add_argument("--verify",type=Path)
    args=a.parse_args()
    config=read_review(args.config)
    if args.acquire:
        result=acquire(args.acquire,config,args.city)
    else:
        result=json.loads((args.verify/f"B1-DGT-native-MDT2m-{args.city}-source-QA.json").read_text())
        inspect(args.verify,config,args.city,result)
    print(json.dumps({"status":"B1_DGT_ACTUAL_16_NATIVE_2M_TILES_AND_4_MOSAICS_VERIFIED",
      "city":args.city,"original_source_tiles":result["source_tile_count"],
      "distinct_km2":result["new_distinct_native_ground_area_km2"],
      "valid_source_pixels":result["valid_native_ground_pixels"],
      "original_source_bytes":result["actual_native_producer_GeoTIFF_bytes_acquired"]}))
if __name__=="__main__":main()
