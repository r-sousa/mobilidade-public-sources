#!/usr/bin/env python3
"""R1: acquire the FULL four public Copernicus GLO-30 COGs and preserve
ONE clipped regional 1-arcsecond digital SURFACE model (DSM), not a DTM.

Coverage is a source-pixel tested exploratory rectangular analysis area
Porto–Trás-os-Montes–Zamora. It is NOT a chosen railway route, track
gradient dataset or bare-earth ground survey. Source 1-degree COGs are
downloaded boundedly to temporary GitHub runner space and hashed, then
a correctly-attributed derived GeoTIFF is published by a SEPARATE job.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request,urlopen

# All four exact producer URLs were independently HEAD / Range tested
# in reports/mn-geo-rail-001/r1-20261030-producer-list-and-head.geojson.
SOURCE_LENGTHS = {
    -9:37449439, -8:44038002, -7:41406815, -6:38671067
}
SOURCE_DATE_LIST_SHA256="10604e3052c98a09e9216f1a8f0a555a04148419757575f783d4937fd44316dc"
SOURCE_HOST="https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"
LAT_TILE=41
OUTPUT_BBOX_WGS84=(-8.75,41.08,-5.55,41.92)
ARCSEC=1/3600
MAX_SINGLE_COG_BYTES=55_000_000
MAX_ALL_SOURCE_BYTES=200_000_000
NODATA=-32767.0
OUT_NAME="MN-GEO-RAIL-001-AFSC-Zamora-GLO30-DSM-1arcsec.tif"
QA_NAME="MN-GEO-RAIL-001-AFSC-Zamora-GLO30-DSM-source-QA.json"
LICENSE_NOTICE="Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved"
LICENSE_URL="https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM"

def source_id(lon):
    if lon not in SOURCE_LENGTHS:
        raise ValueError("unapproved source longitude")
    return f"Copernicus_DSM_COG_10_N41_00_W{abs(lon):03d}_00_DEM"

def source_url(lon):
    i=source_id(lon)
    return f"{SOURCE_HOST}/{i}/{i}.tif"

def download(lon,dest):
    expected=SOURCE_LENGTHS[lon]
    count=0
    h=hashlib.sha256()
    with urlopen(Request(source_url(lon),headers={"User-Agent":"MN-GEO-RAIL-001-regional-public-DSM-1.0"}),timeout=60) as r, dest.open("wb") as out:
        if r.status!=200:
            raise ValueError("public source COG did not return HTTP200")
        while True:
            buf=r.read(1024*1024)
            if not buf: break
            count+=len(buf)
            if count>MAX_SINGLE_COG_BYTES:
                raise ValueError("public COG exceeds bounded byte cap")
            h.update(buf)
            out.write(buf)
    if count!=expected:
        raise ValueError(f"source COG {source_id(lon)} producer size changed: {count} not {expected}")
    return h.hexdigest(),count

def check_source(path,lon,digest,size):
    import rasterio
    import numpy as np
    if not path.is_file() or path.stat().st_size!=size or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise ValueError("source SHA/size mismatch")
    with rasterio.open(path) as ds:
        if ds.driver!="GTiff" or ds.count!=1 or ds.crs is None or ds.crs.to_epsg()!=4326:
            raise ValueError("source GeoTIFF/CRS wrong")
        if (ds.width,ds.height)!=(3600,3600) or abs(ds.res[0]-ARCSEC)>1e-10 or abs(ds.res[1]-ARCSEC)>1e-10:
            raise ValueError("unexpected source native 1arcsec grid")
        bounds=[float(z) for z in ds.bounds]
        if not (abs(bounds[0]-lon)<=0.0005 and abs(bounds[2]-(lon+1))<=0.0005
                and abs(bounds[1]-41)<=0.0005 and abs(bounds[3]-42)<=0.0005):
            raise ValueError("source raster not in expected original one-degree cell")
        d=ds.read(1,masked=True)
        n_valid=int(d.count())
        if n_valid==0 or not np.isfinite(d.compressed()).all():
            raise ValueError("source has zero/nonfinite usable pixels")
        return {"tile_id":source_id(lon),"source_url":source_url(lon),
                "expected_HEAD_bytes":SOURCE_LENGTHS[lon],"actual_bytes":size,
                "original_COG_sha256":digest,"bbox_wgs84":bounds,
                "native_pixels":[ds.width,ds.height],
                "native_valid_pixels":n_valid,
                "native_masked_pixels":int(d.size-n_valid),
                "dtype":ds.dtypes[0],"nominal_resolution":"1 arc-second",
                "source_kind":"DSM_not_bare_earth_DTM"}

def _seam_qa(data,transform):
    """Count actual source-pixel validity at every internal degree meridian."""
    import numpy as np
    west=float(transform.c)
    arc=float(transform.a)
    valid=np.isfinite(data) & (data!=NODATA)
    h,w=data.shape
    out=[]
    for meridian in (-8,-7,-6):
        col=int(round((meridian-west)/arc))
        if col<1 or col>=w:
            raise ValueError("missing meridian from output window")
        left=valid[:,col-1]
        right=valid[:,col]
        pair=left & right
        deltas=np.abs(data[pair,col].astype("float64")-data[pair,col-1].astype("float64"))
        out.append({"meridian_lon":meridian,"adjacent_col":col,
                    "tested_rows":h,"both_adjacent_valid":int(pair.sum()),
                    "either_missing":int(h-pair.sum()),
                    "fraction_both_adjacent_valid":float(pair.mean()),
                    "elevation_delta_abs_p95_m":float(np.percentile(deltas,95)) if len(deltas) else None,
                    "not_a_railway_gradient":True})
    return out

def inspect_output(path):
    import rasterio
    import numpy as np
    if not path.is_file() or path.stat().st_size>280_000_000:
        raise ValueError("derived clip output file absent/oversize")
    with rasterio.open(path) as ds:
        if ds.driver!="GTiff" or ds.count!=1 or ds.crs is None or ds.crs.to_epsg()!=4326:
            raise ValueError("derived mosaic not EPSG4326 single-band GTiff")
        if (abs(ds.res[0]-ARCSEC)>1e-10 or abs(ds.res[1]-ARCSEC)>1e-10):
            raise ValueError("derived native 1arcsec resolution changed")
        bounds=[float(x) for x in ds.bounds]
        src=OUTPUT_BBOX_WGS84
        if not (bounds[0]<=src[0]+ARCSEC and bounds[1]<=src[1]+ARCSEC and
                bounds[2]>=src[2]-ARCSEC and bounds[3]>=src[3]-ARCSEC):
            raise ValueError("mosaic does not cover approved bound")
        if ds.width<10500 or ds.height<2800 or ds.width>12000 or ds.height>3400:
            raise ValueError("unexpected source tile clipping")
        pixels=ds.read(1,masked=True)
        valid=int(pixels.count())
        coverage=float(valid/pixels.size)
        if valid!=pixels.size:
            raise ValueError("regional DSM rectangle contains masked/missing pixels (zero tolerated)")
        v=pixels.compressed()
        if not np.isfinite(v).all() or float(v.min())<-500 or float(v.max())>4000:
            raise ValueError("implausible regional DSM range")
        raw=ds.read(1)
        seams=_seam_qa(raw,ds.transform)
        if any(x["either_missing"] for x in seams):
            raise ValueError("regional DSM failed internal tile seam pixel-validity gate")
        return {"bbox_wgs84":bounds,"horizontal_crs":"EPSG:4326",
                "vertical_reference_from_Copernicus_product_documentation":"EGM2008 (EPSG:3855)",
                "vertical_CRS_individually_encoded_in_output":False,
                "nominal_source_grid":"1 arc-second (around 30 m at these latitudes)",
                "width_px":ds.width,"height_px":ds.height,
                "output_cells_total":int(pixels.size),"output_cells_valid":valid,
                "output_cells_masked_or_missing":int(pixels.size-valid),
                "fraction_cells_valid":coverage,
                "min_surface_m":float(v.min()),"max_surface_m":float(v.max()),
                "mean_surface_m":float(v.mean()),
                "three_meridian_pixel_validity_tests":seams,
                "native_source_resolution_maintained":True,
                "is_continuous_surface_DSM_across_rectangular_review_envelope":True,
                "is_bare_earth_DTM":False,
                "not_validated_for_railway_ruling_gradient":True}

def acquire(work_dir:Path):
    import rasterio
    import rasterio.merge
    work_dir.mkdir(parents=True,exist_ok=True)
    src_paths=[]
    receipts=[]
    for lon in SOURCE_LENGTHS:
        p=work_dir/(source_id(lon)+".tif")
        sha,size=download(lon,p)
        receipts.append(check_source(p,lon,sha,size))
        src_paths.append(p)
    if sum(x["actual_bytes"] for x in receipts)>MAX_ALL_SOURCE_BYTES:
        raise ValueError("unexpected aggregate source volume")
    from contextlib import ExitStack
    with ExitStack() as stack:
        sources=[stack.enter_context(rasterio.open(p)) for p in src_paths]
        # Same WGS84 one-arcsec source grid, no interpolation to a coarser raster.
        # rasterio.merge may leave the last column unwritten when the requested
        # crop touches an independently rounded source window. Preserve 2 extra
        # source columns at the right then crop to the EXACT intended grid.
        # Without this guard 3024 cells were missing in one east-boundary column
        # despite the original fourth 1-degree COG having ALL pixels valid.
        west,south,east,north=OUTPUT_BBOX_WGS84
        expanded_bbox=(west,south,east+2*ARCSEC,north)
        pixels,transform=rasterio.merge.merge(
            sources,bounds=expanded_bbox,res=(ARCSEC,ARCSEC),
            method="first",nodata=NODATA,target_aligned_pixels=True
        )
        requested_width=int(round((east-west)/ARCSEC))
        requested_height=int(round((north-south)/ARCSEC))
        if pixels.shape[0]!=1 or pixels.shape[1]!=requested_height or pixels.shape[2]<requested_width:
            raise ValueError("unexpected source/output grid shape")
        pixels=pixels[:,:,:requested_width]
    if pixels.shape[0]!=1: raise ValueError("unapproved multi-band mosaic")
    out=work_dir/OUT_NAME
    with rasterio.open(out,"w",driver="GTiff",height=pixels.shape[1],width=pixels.shape[2],
                       count=1,dtype="float32",crs="EPSG:4326",transform=transform,
                       nodata=NODATA,tiled=True,blockxsize=512,blockysize=512,
                       compress="DEFLATE",predictor=3,zlevel=6,bigtiff="IF_SAFER") as ds:
        ds.write(pixels[0],1)
        ds.update_tags(
            SOURCE_PRODUCT="Copernicus DEM GLO-30 Public (Digital Surface Model)",
            SOURCE_VERTICAL_REFERENCE="EGM2008 EPSG:3855 from Copernicus product handbook, not embedded 3D CRS",
            LICENSE_NOTICE=LICENSE_NOTICE,
            ORIGINAL_DATA_CLASS="DSM surface incl. buildings/vegetation, NOT bare-earth DTM",
            MISSION="MN-GEO-RAIL-001",STAGE="preacceptance screening surface, NOT railway alignment"
        )
    del pixels
    checked=inspect_output(out)
    mosaic_sha=hashlib.sha256(out.read_bytes()).hexdigest()
    doc={
        "mission":"MN-GEO-RAIL-001","stage":"R1_regionally_continuous_GLO30_public_DSM_pixel_acquisition",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "producer":"Copernicus DEM GLO-30 Public / Airbus / DLR / ESA / EU",
        "source_kind":"DSM_NOT_bare_earth_DTM",
        "source_licence_and_attribution_url":LICENSE_URL,
        "derivative_notice":LICENSE_NOTICE,
        "producer_tile_list_SHA256_prior_evidence":SOURCE_DATE_LIST_SHA256,
        "four_full_source_COG_files_transferred_and_hashed":len(receipts),
        "full_source_transfer_total_bytes":sum(x["actual_bytes"] for x in receipts),
        "source_COGs":receipts,
        "derivative_GeoTIFF":{"filename":OUT_NAME,"sha256":mosaic_sha,
                              "bytes":out.stat().st_size,"raster":checked},
        "native_4_source_COG_TIFFs_published":False,
        "clipped_DSM_1arcsecond_GeoTIFF_published_by_separate_job":False,
        "reference_frame_vertical_transformation_applied":False,
        "crossborder_vertical_geodetic_accuracy_validated":False,
        "DSM_is_not_railway_earthwork_surface":True,
        "native_2m_DGT_and_5m_CNIG_sources_merged_here":False,
        "Fxx_canonical_accepted":False,"site_authorized":False,
        "rail_alignment_profiles_authorized":False}
    (work_dir/QA_NAME).write_text(json.dumps(doc,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    return doc

def verify_existing(work_dir:Path):
    doc=json.loads((work_dir/QA_NAME).read_text())
    if (doc.get("Fxx_canonical_accepted") is not False
        or doc.get("site_authorized") is not False
        or doc.get("rail_alignment_profiles_authorized") is not False
        or doc.get("source_kind")!="DSM_NOT_bare_earth_DTM"
        or doc.get("derivative_notice")!=LICENSE_NOTICE):
        raise ValueError("unsafe source/permission/provenance metadata")
    d=doc["derivative_GeoTIFF"]
    if d["filename"]!=OUT_NAME:raise ValueError("unapproved output filename")
    p=work_dir/OUT_NAME
    if p.stat().st_size!=d["bytes"] or hashlib.sha256(p.read_bytes()).hexdigest()!=d["sha256"]:
        raise ValueError("release candidate SHA256 mismatch")
    checked=inspect_output(p)
    if d["raster"]!=checked:
        raise ValueError("source QA is inconsistent with output pixel-coverage")
    if len(doc["source_COGs"])!=4 or [x["tile_id"] for x in doc["source_COGs"]]!=[source_id(x) for x in SOURCE_LENGTHS]:
        raise ValueError("incomplete/incorrect producer coverage tiles")
    if sum(x["actual_bytes"] for x in doc["source_COGs"])!=doc["full_source_transfer_total_bytes"]:
        raise ValueError("bad provenance source byte accounting")
    return doc

def main():
    p=argparse.ArgumentParser(description=__doc__)
    opts=p.add_mutually_exclusive_group(required=True)
    opts.add_argument("--acquire",type=Path)
    opts.add_argument("--verify-existing",type=Path)
    x=p.parse_args()
    doc=acquire(x.acquire) if x.acquire else verify_existing(x.verify_existing)
    print(json.dumps({"status":"regional_1arcsecond_DSM_QA_passed",
      "source_count":len(doc["source_COGs"]),
      "source_bytes":doc["full_source_transfer_total_bytes"],
      "derived_size":doc["derivative_GeoTIFF"]["bytes"],
      "output_sha256":doc["derivative_GeoTIFF"]["sha256"],
      "valid_cells":doc["derivative_GeoTIFF"]["raster"]["output_cells_valid"],
      "coverage":doc["derivative_GeoTIFF"]["raster"]["fraction_cells_valid"],
      "seams":doc["derivative_GeoTIFF"]["raster"]["three_meridian_pixel_validity_tests"],
      "Fxx":doc["Fxx_canonical_accepted"]},sort_keys=True))
if __name__=="__main__":main()
