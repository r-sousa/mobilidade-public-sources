#!/usr/bin/env python3
"""A1b actual northern Sanabria DSM acquisition: 4 public 1-degree Copernicus
GLO30 COGs (N41/N42, W007/W006). This is SURFACE not bare earth DTM.
Window abuts A1 at latitude 41.92, and adds genuine northwards study area.
All files hashed and all A1b source pixels QA; never label track gradients.
"""
from __future__ import annotations
import argparse, hashlib,json, math
from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime,timezone
from contextlib import ExitStack

ARC=1/3600
BBOX=(-7.0,41.92,-5.55,42.30)
SOURCE_TILE_COORDS=((41,-7),(41,-6),(42,-7),(42,-6))
HOST="https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"
MAX_BYTES_PER_TILE=65_000_000
MAX_TOTAL_BYTES=250_000_000
NODATA=-32767.0
OUT="MN-GEO-RAIL-001-A1b-Sanabria-northern-GLO30-DSM.tif"
REPORT="MN-GEO-RAIL-001-A1b-Sanabria-northern-DSM-QA.json"
SOURCE_NOTICE="Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved"
TERMS_URL="https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM"

def tile(lat,lon):
    if (lat,lon) not in SOURCE_TILE_COORDS:raise ValueError("unapproved source grid")
    return f"Copernicus_DSM_COG_10_N{lat:02d}_00_W{abs(lon):03d}_00_DEM"

def acquire_one(dest,lat,lon):
    import rasterio
    name=tile(lat,lon)
    url=f"{HOST}/{name}/{name}.tif"
    h=hashlib.sha256();n=0
    with urlopen(Request(url,headers={"User-Agent":"MN-GEO-RAIL-001-A1b-Sanabria-geospatial/1"}),timeout=55) as r,dest.open("wb") as out:
        if r.status!=200:raise ValueError("source_COG_status_not_200")
        while True:
            part=r.read(1024*1024)
            if not part:break
            n+=len(part)
            if n>MAX_BYTES_PER_TILE:raise ValueError("source_exceeds_65MB_bound")
            out.write(part);h.update(part)
    if not (1_000_000<n<=MAX_BYTES_PER_TILE):raise ValueError("unexpected_source_COG_bytes")
    with rasterio.open(dest) as ds:
        if (ds.driver!="GTiff" or ds.count!=1 or ds.crs is None or ds.crs.to_epsg()!=4326
            or (ds.width,ds.height)!=(3600,3600)
            or abs(ds.res[0]-ARC)>1e-10 or abs(ds.res[1]-ARC)>1e-10
            or abs(ds.bounds.left-lon)>0.0005 or abs(ds.bounds.bottom-lat)>0.0005):
            raise ValueError("unexpected_source_native_COG_grid")
        valid=int(ds.read(1,masked=True).count())
        if valid<0.99*3600*3600:raise ValueError("unexpected_source_COG_valid_pixel_drop")
        return {"tile":name,"source_url":url,"source_bytes":n,"source_sha256":h.hexdigest(),
                "native_valid_cells":valid,"native_cells":3600*3600,
                "bbox_wgs84":list(ds.bounds),"source_type":"DSM_not_DTM"}

def inspect(path):
    import rasterio,numpy as np
    if not path.exists() or path.stat().st_size>90_000_000:raise ValueError("missing_or_oversize_clip")
    with rasterio.open(path) as ds:
        if ds.crs is None or ds.crs.to_epsg()!=4326 or ds.count!=1 or ds.driver!="GTiff":
            raise ValueError("invalid_clipped_DSM_GeoTIFF_CRS")
        if abs(ds.res[0]-ARC)>1e-10 or abs(ds.res[1]-ARC)>1e-10:
            raise ValueError("not_one_arc_second")
        expected=(int(round((BBOX[2]-BBOX[0])/ARC)),int(round((BBOX[3]-BBOX[1])/ARC)))
        if (ds.width,ds.height)!=expected:
            raise ValueError("clipped_DSM_grid_dimensions_wrong")
        if any(abs(a-b)>1e-7 for a,b in zip(ds.bounds,BBOX)):
            raise ValueError("wrong_A1b_bbox")
        v=ds.read(1,masked=True)
        if int(v.count())!=int(v.size):raise ValueError("A1b_DSM_has_missing_native_pixels")
        a=v.filled(NODATA)
        if not np.isfinite(a).all() or a.min()<-500 or a.max()>4000:raise ValueError("elevation_range_bad")
        loncol=int(round((-6-ds.bounds.left)/ARC))
        latrow=int(round((ds.bounds.top-42.0)/ARC))
        c_valid=int((a[:,loncol-1]!=NODATA).sum()+ (a[:,loncol]!=NODATA).sum())
        r_valid=int((a[latrow-1,:]!=NODATA).sum()+ (a[latrow,:]!=NODATA).sum())
        if c_valid!=ds.height*2 or r_valid!=ds.width*2:raise ValueError("missing_original_COG_meridian_or_parallel_pixel_pair")
        return {"bbox_wgs84":list(ds.bounds),"grid_crs_horizontal":"EPSG:4326",
            "nominal_terrain_reference_from_Copernicus_docs":"EGM2008 EPSG:3855 (not embedded or independently surveyed)",
            "pixel_count":int(v.size),"valid_pixel_count":int(v.count()),"nodata_count":0,
            "width_px":ds.width,"height_px":ds.height,
            "meridian_minus6_valid_adjacent_pairs":ds.height,
            "parallel_42_valid_adjacent_pairs":ds.width,
            "study_area_includes_Sanabria_city_proxy":[-6.6336,42.0552],
            "A1b_abuts_previous_A1_south_at_latitude":41.92,
            "A1_to_A1b_cross_release_seam_values_compared":False,
            "is_DSM_not_bare_earth_DTM":True,"is_certified_railway_profile":False,
            "observed_range_m":[float(a.min()),float(a.max())]}

def run(outdir):
    import rasterio
    from rasterio.merge import merge
    from rasterio.windows import from_bounds,transform as window_transform
    outdir.mkdir(parents=True,exist_ok=True)
    rows=[];sources=[]
    for lat,lon in SOURCE_TILE_COORDS:
        p=outdir/(tile(lat,lon)+".tif")
        rows.append(acquire_one(p,lat,lon))
        sources.append(p)
    if sum(x["source_bytes"] for x in rows)>MAX_TOTAL_BYTES:raise ValueError("total_source_budget_exceeded")
    # Two-pixel overscan prevents the one-column output loss seen in A1 initial.
    b=BBOX
    overscan=(b[0]-2*ARC,b[1]-2*ARC,b[2]+2*ARC,b[3]+2*ARC)
    with ExitStack() as stack:
        readers=[stack.enter_context(rasterio.open(p)) for p in sources]
        raw,transform=merge(readers,bounds=overscan,res=(ARC,ARC),
                            target_aligned_pixels=True,nodata=NODATA,method="first")
    target=from_bounds(*BBOX,transform=transform)
    c=int(round(target.col_off));r=int(round(target.row_off))
    width=int(round((BBOX[2]-BBOX[0])/ARC))
    height=int(round((BBOX[3]-BBOX[1])/ARC))
    data=raw[0,r:r+height,c:c+width]
    if data.shape!=(height,width):raise ValueError("missing_final_overscanned_region")
    dst=outdir/OUT
    with rasterio.open(dst,"w",driver="GTiff",count=1,width=width,height=height,
             dtype="float32",crs="EPSG:4326",transform=window_transform(rasterio.windows.Window(c,r,width,height),transform),
             nodata=NODATA,compress="DEFLATE",predictor=3,zlevel=6,
             tiled=True,blockxsize=512,blockysize=512) as w:
        w.write(data.astype("float32"),1)
        w.update_tags(MISSION="MN-GEO-RAIL-001",DATA_CLASS="COPERNICUS DIGITAL SURFACE MODEL, NOT GROUND DTM",
                      DATA_LICENSE_ATTRIBUTION=SOURCE_NOTICE,RAILWAY="PREACCEPTANCE: NOT AN ALIGNMENT")
    qa=inspect(dst)
    manifest={"mission":"MN-GEO-RAIL-001","stage":"A1b_Sanabria_north_DSM_region_original_COGs",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "origin":"Copernicus DEM GLO30 Public Digital SURFACE Model, not bare earth",
        "source_licence":TERMS_URL,"attribution_notice":SOURCE_NOTICE,
        "full_source_COGs_acquired_and_verified":rows,
        "full_source_bytes_sum":sum(x["source_bytes"] for x in rows),
        "original_1degree_COGs_republished":False,
        "derivative":{"filename":OUT,"size_bytes":dst.stat().st_size,
           "sha256":hashlib.sha256(dst.read_bytes()).hexdigest(),"geo_validation":qa},
        "datum_PT_ES_calibrated":False,"bare_earth_DTM_completed":False,
        "Fxx_accepted":False,"Site_authorized":False,"engineering_alignment_validated":False}
    (outdir/REPORT).write_text(json.dumps(manifest,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    return manifest

def verify_existing(folder):
    from pathlib import Path
    data=json.loads((folder/REPORT).read_text())
    if data["Fxx_accepted"] or data["Site_authorized"] or data["bare_earth_DTM_completed"]:
        raise ValueError("guardrail incorrect")
    d=data["derivative"];p=folder/OUT
    if d["filename"]!=OUT or p.stat().st_size!=d["size_bytes"] or hashlib.sha256(p.read_bytes()).hexdigest()!=d["sha256"]:
        raise ValueError("derivative changed")
    if inspect(p)!=d["geo_validation"]:
        raise ValueError("source raster pixel QA mismatch")
    if len(data["full_source_COGs_acquired_and_verified"])!=4:
        raise ValueError("four sources not verified")
    return data

def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--acquire",type=Path)
    g.add_argument("--verify-existing",type=Path)
    a=p.parse_args()
    d=run(a.acquire) if a.acquire else verify_existing(a.verify_existing)
    print(json.dumps({"status":"A1b_real_DSM_QA_passed",
        "n_original_COGs":len(d["full_source_COGs_acquired_and_verified"]),
        "total_original_bytes":d["full_source_bytes_sum"],
        "valid_pixels":d["derivative"]["geo_validation"]["valid_pixel_count"],
        "missing_pixels":d["derivative"]["geo_validation"]["nodata_count"],
        "output_sha256":d["derivative"]["sha256"],"output_bytes":d["derivative"]["size_bytes"]}))
if __name__=="__main__":main()
