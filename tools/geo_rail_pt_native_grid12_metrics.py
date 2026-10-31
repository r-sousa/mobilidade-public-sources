#!/usr/bin/env python3
"""Reproducibly assemble a 3x4 km DGT source-native 2m MDT raster for pilot QA.

Pinned original GitHub prerelease is independently downloaded by public CI,
then every original byte is checked against the protected DGT acquisition
SHA-256. This process contains no DGT account credentials or signed URLs.

Outputs: a *derived* native-CRS GeoTIFF mosaic and explicit terrain QA stats.
This is a local terrain source pilot, NOT an alignment, Fxx acceptance,
verified vertical datum, or full Porto-Zamora coverage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime,timezone

COLS=(280,281,282)
ROWS=(507,508,509,510)
CRS="EPSG:3763"
RESOLUTION=2.0
EXPECTED_EXTENT=(80000,206000,83000,210000)
EXPECTED_TILES={f"grid_{c}_{r}.tif" for c in COLS for r in ROWS}
TOTAL_EXPECTED_CELLS=3_000_000
ORIGINAL_MANIFEST_SHA256="6c2e064d2a43299ac26db127469f27eac183f96cd1dd8e6852c25d834a6d15ec"
SOURCE_RELEASE="mn-geo-rail-001-dgt-grid12-preacceptance-41158397813"

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        while part:=f.read(1024*1024):
            h.update(part)
    return h.hexdigest()

def verified_source_records(index,source_dir,original_manifest):
    """Fail closed on source identity, DGT producer provenance and byte identity."""
    summary=json.loads(Path(index).read_text(encoding="utf-8"))
    if summary.get("mission")!="MN-GEO-RAIL-001" or summary.get("area_km2")!=12:
        raise ValueError("unexpected_preacceptance_source_identity")
    if (summary.get("origin_release")!=
        "https://github.com/r-sousa/mobilidade-public-sources/releases/tag/"+SOURCE_RELEASE):
        raise ValueError("unexpected_DGT_source_release")
    if summary.get("native_manifest_sha256")!=ORIGINAL_MANIFEST_SHA256:
        raise ValueError("published_DGT_manifest_digest_mismatch")
    if sha256(original_manifest)!=ORIGINAL_MANIFEST_SHA256:
        raise ValueError("downloaded_DGT_manifest_sha256_mismatch")
    manifest=json.loads(Path(original_manifest).read_text(encoding="utf-8"))
    if (manifest.get("status")!="twelve_native_DGT_GeoTIFFs_and_all_17_seams_validated"
        or manifest.get("valid_native_pixel_cells")!=TOTAL_EXPECTED_CELLS
        or manifest.get("joint_neighbor_cell_pairs_valid")!=8500
        or manifest.get("native_files_sha_verified_in_temporary_release_staging")!=12):
        raise ValueError("DGT_protected_source_QA_manifest_not_verified")
    if summary.get("source")!="Direção-Geral do Território (DGT), CDD, CC BY 4.0 attribution required":
        raise ValueError("DGT_attribution_not_preserved")
    objs=summary.get("source_tiles")
    if not isinstance(objs,list) or len(objs)!=12:
        raise ValueError("not_twelve_source_objects")
    directory=Path(source_dir)
    if {x.name for x in directory.glob("*.tif") }!=EXPECTED_TILES:
        raise ValueError("unexpected_native_raster_file_set")
    validated={}
    original={rec["producer_tile_id"]:rec for rec in manifest["tile_receipts"]}
    for obj in objs:
        name=obj.get("asset")
        id=obj.get("id")
        if name not in EXPECTED_TILES or name in validated:
            raise ValueError("nonunique_or_unapproved_DGT_mosaic_asset")
        coords=name.removeprefix("grid_").removesuffix(".tif").split("_")
        if len(coords)!=2 or any(not n.isdigit() for n in coords):
            raise ValueError("invalid_DGT_tile_name")
        c,r=map(int,coords)
        if c not in COLS or r not in ROWS or id!=f"MDT-2m-{c}{r}-09-2024":
            raise ValueError("incorrect_source_tile_mapping")
        path=directory/name
        if path.stat().st_size!=obj.get("bytes") or path.stat().st_size>25_000_000:
            raise ValueError("source_native_byte_count_mismatch")
        digest=sha256(path)
        if digest!=obj.get("sha256") or digest!=original[id]["native_sha256"]:
            raise ValueError("native_raster_SHA256_not_trusted")
        if original[id]["native_file_bytes"]!=path.stat().st_size:
            raise ValueError("producer_native_raster_size_mismatch")
        validated[name]=dict(obj,col=c,row=r,actual_sha256=digest)
    if sum(x["bytes"] for x in validated.values())!=summary["native_bytes_total"]:
        raise ValueError("DGT_total_source_byte_count_mismatch")
    return validated,summary

def mosaic_native(record_map,native_dir,out_path,qa_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    m=np.empty((2000,1500),dtype="float32")
    tiles=[]
    for row in ROWS:
        for col in COLS:
            name=f"grid_{col}_{row}.tif"
            desc=record_map[name]
            with rasterio.open(Path(native_dir)/name) as src:
                expected=from_origin((col-200)*1000,(row-300)*1000,2.0,2.0)
                if src.driver!="GTiff" or src.count!=1 or not src.crs or src.crs.to_epsg()!=3763:
                    raise ValueError("native_DGT_geometry_or_driver_mismatch")
                if src.width!=500 or src.height!=500 or src.dtypes[0]!="float32":
                    raise ValueError("native_DGT_pixel_layout_mismatch")
                if any(not math.isclose(a,b,abs_tol=0.001) for a,b in zip(src.transform[:6],expected[:6])):
                    raise ValueError("native_DGT_pixel_transform_mismatch")
                img=src.read(1,masked=True)
                if int(img.count())!=250_000 or not np.isfinite(img.data).all():
                    raise ValueError("source_missing_or_nonfinite_DGT_elevations")
                # north row first, west col first; exact two-metre square cells.
                ro=(510-row)*500
                co=(col-280)*500
                m[ro:ro+500,co:co+500]=img.data
                tiles.append({"producer_tile_id":desc["id"],"native_sha256":desc["sha256"],
                              "mosaic_pixel_start_row":ro,"mosaic_pixel_start_column":co})
    if not np.isfinite(m).all() or m.size!=TOTAL_EXPECTED_CELLS:
        raise ValueError("DGT_mosaic_contains_missing_elevation")

    # Cell-centre source terrain slopes, *not* railway vertical gradients.
    # Calculate 2m finite differences across the entire mosaic, including joins.
    north_south,east_west=np.gradient(m.astype("float64"),RESOLUTION,RESOLUTION)
    slope_percent=100*np.hypot(east_west,north_south)
    if not np.isfinite(slope_percent).all():
        raise ValueError("invalid_native_mosaic_gradient")
    # Independent joins: gradient jumps describe terrain, never require zero.
    edge_qa=[]
    for ci in (500,1000):
        differences=np.abs(m[:,ci]-m[:,ci-1]).astype("float64")
        edge_qa.append({"orientation":"west_east","mosaic_column":ci,
                        "neighbor_pairs":2000,"valid_pairs":int(np.isfinite(differences).sum()),
                        "max_abs_elevation_delta_m":float(differences.max())})
    for ri in (500,1000,1500):
        differences=np.abs(m[ri,:]-m[ri-1,:]).astype("float64")
        edge_qa.append({"orientation":"north_south","mosaic_row":ri,
                        "neighbor_pairs":1500,"valid_pairs":int(np.isfinite(differences).sum()),
                        "max_abs_elevation_delta_m":float(differences.max())})
    if sum(x["valid_pairs"] for x in edge_qa)!=8500:
        raise ValueError("DGT_mosaic_source_grid_seams_not_complete")

    out_path=Path(out_path);out_path.parent.mkdir(parents=True,exist_ok=True)
    profile={"driver":"GTiff","height":2000,"width":1500,"count":1,
             "dtype":"float32","crs":CRS,"transform":from_origin(80000,210000,2,2),
             "compress":"deflate","predictor":3,"tiled":True,"blockxsize":256,"blockysize":256}
    with rasterio.open(out_path,"w",**profile) as dst:
        dst.write(m,1)
        dst.update_tags(
            SOURCE="Direcao-Geral do Territorio, Centro de Dados DGT",
            LICENSE="CC BY 4.0; credit DGT",
            PARENT_RELEASE=SOURCE_RELEASE,
            ACCEPTANCE="EXPLORATORY_NOT_CANONICAL_FXX_NOT_COMPLETE_RAIL_CORRIDOR",
            VERTICAL_DATUM="Source documents Cascais; NOT independently benchmarked"
        )
    with rasterio.open(out_path) as ds:
        reread=ds.read(1)
        if (ds.crs.to_epsg()!=3763 or ds.width!=1500 or ds.height!=2000
           or not np.array_equal(reread,m)):
            raise ValueError("derived_mosaic_roundtrip_pixels_differ")
        bounds=[float(x) for x in ds.bounds]
    if bounds!=list(EXPECTED_EXTENT):
        raise ValueError("derived_mosaic_wrong_bbox")
    percentiles={str(q):float(np.percentile(slope_percent,q)) for q in (5,25,50,75,90,95,99)}
    elev_percentiles={str(q):float(np.percentile(m,q)) for q in (5,25,50,75,90,95,99)}
    result={
        "mission":"MN-GEO-RAIL-001","stage":"real_DGT_12km2_derived_source_mosaic_slope_QA",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "producer":"Direção-Geral do Território","license":"CC BY 4.0; attribution DGT required",
        "original_source_release":SOURCE_RELEASE,
        "source_native_tiles":tiles,
        "n_native_source_tiles":len(tiles),
        "original_native_bytes_used":sum(x["bytes"] for x in record_map.values()),
        "original_raster_SHA256_rechecked":True,
        "geographic_area_km2":12,
        "native_resolution_m":RESOLUTION,
        "mosaic_bbox_pttm06":bounds,"mosaic_dimensions":[1500,2000],
        "source_native_crs":CRS,
        "pixel_count_total":int(m.size),
        "pixel_count_valid":int(np.isfinite(m).sum()),
        "native_internal_edge_join_qa":edge_qa,
        "adjacent_source_cells_verified":8500,
        "elevation_min_m":float(m.min()),
        "elevation_max_m":float(m.max()),
        "elevation_mean_m":float(m.mean(dtype="float64")),
        "elevation_std_m":float(m.std(dtype="float64")),
        "elevation_quantiles_m":elev_percentiles,
        "terrain_slope_percent_quantiles":percentiles,
        "terrain_slope_percent_cell_fraction_by_max_threshold":{
            str(th):float(np.mean(slope_percent<=th)) for th in (5,10,20,35,50,100)
        },
        "terrain_slope_interpretation":"2m-scale local ground DTM central differences; NOT longitudinal gradient of any prospective railway alignment",
        "derived_mosaic_filename":out_path.name,
        "derived_mosaic_bytes":out_path.stat().st_size,
        "derived_mosaic_sha256":sha256(out_path),
        "derived_raster_is_source_not_canonical":True,
        "full_Norte_Zamora_corridor_coverage_verified":False,
        "Portugal_Spain_vertical_datum_harmonized":False,
        "official_vertical_benchmarks_checked":False,
        "Fxx_canonical_accepted":False,
        "Site_approved":False,
        "rail_alignment_ready":False
    }
    qa_path=Path(qa_path);qa_path.parent.mkdir(parents=True,exist_ok=True)
    qa_path.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--native-dir",required=True,type=Path)
    p.add_argument("--source-index",required=True,type=Path)
    p.add_argument("--original-manifest",required=True,type=Path)
    p.add_argument("--output-raster",required=True,type=Path)
    p.add_argument("--receipt",required=True,type=Path)
    args=p.parse_args()
    records,_=verified_source_records(args.source_index,args.native_dir,args.original_manifest)
    report=mosaic_native(records,args.native_dir,args.output_raster,args.receipt)
    print(json.dumps({"status":"real_DGT_source_mosaic_QA_passed",
                      "source_tiles":report["n_native_source_tiles"],
                      "cells":report["pixel_count_valid"],
                      "slope_50th_pct":report["terrain_slope_percent_quantiles"]["50"],
                      "mosaic_sha256":report["derived_mosaic_sha256"],
                      "canonical":False}))

if __name__=="__main__":
    main()
