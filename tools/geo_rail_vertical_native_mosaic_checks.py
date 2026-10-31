#!/usr/bin/env python3
"""W4: source-pinned PROJ Cascais->Alicante numerical transform checks.

The input terrain is a tiny, public DGT 12km² original-source-derived mosaic.
This is NOT vertical control-point validation, not a converted full raster,
and not yet an accepted rail-alignment-ready Portugal/Spain height surface.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request,urlopen

GRIDS={
 "pt_dgt_GeodPT08.tif":("8c006ae3afa037c214d30e7ec97736452705773ccb663274e003ced1d08ccaa0",81638),
 "es_ign_egm08-rednap.tif":("d1758a580c2acc7cddcb814c2aebe1e5ab83f74dfaed8c1a885355bb3f85df58",827857),
}
GRID_ORIGIN="https://cdn.proj.org"
MAX_BYTES=2_000_000
SOURCE_MOSAIC_RELEASE="mn-geo-rail-001-pt-dgt-grid12-mosaic-41158983022"
SOURCE_MOSAIC_SHA256="3e0ccefb89035565f9329320ed83ff39dc38ab1a56a4903846f930d018ffef17"
PT_VERTICAL="EPSG:5780" # Cascais height
ES_VERTICAL="EPSG:5782" # Alicante height
SITE_POINTS={
 "PT_Amarante":(-8.1,41.26),
 "PT_Mirandela":(-7.2,41.50),
 "PT_Nordeste":(-6.9,41.75),
 "ES_Alcanices":(-6.346470,41.6994),
 "ES_Zamora":(-5.746992,41.503780),
}
SAMPLE_PIXELS=((375,250),(750,250),(1125,250),
               (375,1000),(750,1000),(1125,1000),
               (375,1750),(750,1750),(1125,1750))

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as fd:
        while p:=fd.read(1024*1024):
            h.update(p)
    return h.hexdigest()

def bounded_grid(name,expected,workspace,fetcher=urlopen):
    if name not in GRIDS or expected!=GRIDS[name]:
        raise ValueError("unapproved_vertical_grid")
    expected_sha,expected_bytes=expected
    url=f"{GRID_ORIGIN}/{name}"
    p=workspace/name
    h=hashlib.sha256()
    used=0
    with fetcher(Request(url,headers={"User-Agent":"MN-GEO-RAIL-001-W4-verification/1.0"}),
                 timeout=40) as response:
        if response.status!=200:raise ValueError("geoid_grid_HTTP_status")
        length=response.headers.get("Content-Length")
        if length and length.isdecimal() and int(length)>MAX_BYTES:
            raise ValueError("vertical_grid_exceeds_bound")
        with p.open("xb") as out:
            while chunk:=response.read(131072):
                used+=len(chunk)
                if used>MAX_BYTES:raise ValueError("vertical_grid_exceeds_bound")
                out.write(chunk);h.update(chunk)
    if (used,h.hexdigest())!=(expected_bytes,expected_sha):
        raise ValueError("geoid_grid_SHA_or_size_disagrees_with_prior_verified_grid")
    with p.open("rb") as fd:
        if fd.read(4) not in (b"II*\x00",b"MM\x00*",b"II+\x00",b"MM\x00+"):
            raise ValueError("geoid_grid_is_not_TIFF")
    return {"name":name,"bytes":used,"sha256":h.hexdigest(),"source_url":url,
            "SHA256_matches_previous_reproducible_W4_audit":True}

def verified_transform(tmp):
    from pyproj import CRS,datadir,Transformer
    from pyproj.transformer import TransformerGroup
    datadir.append_data_dir(str(tmp))
    group=TransformerGroup(CRS.from_epsg(5780),CRS.from_epsg(5782),
                           allow_ballpark=False,always_xy=True)
    if not group.best_available or not group.transformers:
        raise ValueError("authoritative_geoid_operation_not_available")
    options=[x for x in group.transformers if
             all(name in x.definition for name in GRIDS)]
    if not options:
        raise ValueError("two_authoritative_geoid_grids_not_in_same_operation")
    op=options[0]
    if op.accuracy<0 or op.accuracy>0.1:
        raise ValueError("not_expected_9cm_operation_accuracy_metadata")
    definition=op.definition
    if definition.count("step proj=axisswap order=2,1")!=2:
        raise ValueError("unexpected_EPSG_vertical_axis_order_pipeline")
    pipeline=definition.replace("step proj=axisswap order=2,1","")
    converter=Transformer.from_pipeline(pipeline)
    return converter,{"EPSG_operation_description":op.description,
                      "EPSG_declared_operation_accuracy_m":op.accuracy,
                      "source_vertical_crs":PT_VERTICAL,"target_vertical_crs":ES_VERTICAL,
                      "direct_lonlat_pipeline":pipeline,
                      "axis_swap_removed_explicitly_for_lonlat":True,
                      "proj_operation_contains_both_signed_official_grids":True}

def site_numeric_checks(converter):
    from pyproj.enums import TransformDirection
    result=[]
    for name,(lon,lat) in SITE_POINTS.items():
        lon0,lat0,h=converter.transform(lon,lat,100.0,errcheck=False)
        finite=all(math.isfinite(v) for v in (lon0,lat0,h))
        # Zamora lies beyond the Portuguese geoid grid. Fail closed there.
        if name=="ES_Zamora":
            if finite: raise ValueError("Zamora_outside_PT_grid_should_not_be_finite")
            result.append({"site":name,"longitude":lon,"latitude":lat,
                           "within_compatibility_grid_overlap":False,
                           "vertical_transform_supported":False,"synthetic_only":True})
            continue
        if not finite:raise ValueError("overlap_site_not_transformable")
        if abs(lon0-lon)>1e-8 or abs(lat0-lat)>1e-8:
            raise ValueError("unexpected_horizontal_change_in_vertical_operation")
        if not -1.0<(h-100.0)<1.0:
            raise ValueError("unreasonable_local_vertical_grid_difference")
        l2,p2,recovered=converter.transform(lon0,lat0,h,
                direction=TransformDirection.INVERSE,errcheck=True)
        residual=abs(recovered-100.0)
        if not math.isfinite(residual) or residual>0.005:
            raise ValueError("synthetic_roundtrip_vertical_closure_over_5mm")
        _,_,zero_h=converter.transform(lon,lat,0.0,errcheck=True)
        if abs(zero_h-(h-100.0))>1e-8:
            raise ValueError("vertical_transformation_not_affine_in_height")
        result.append({"site":name,"longitude":lon,"latitude":lat,
                       "within_compatibility_grid_overlap":True,
                       "vertical_transform_supported":True,
                       "synthetic_PT_Cascais_input_height_m":100.0,
                       "synthetic_candidate_ES_Alicante_output_height_m":float(h),
                       "computed_Cascais_to_Alicante_vertical_offset_m":float(h-100.0),
                       "synthetic_forward_inverse_residual_m":float(residual),
                       "synthetic_only":True})
    return result

def source_mosaic_checks(mosaic,converter):
    # Reject unauthenticated source bytes BEFORE importing optional raster libs.
    if digest(mosaic)!=SOURCE_MOSAIC_SHA256:
        raise ValueError("DGT_derived_source_mosaic_SHA256_not_as_published")
    import numpy as np
    import rasterio
    from pyproj import Transformer
    geom=Transformer.from_crs(3763,4326,always_xy=True)
    points=[]
    with rasterio.open(mosaic) as ds:
        if ds.crs.to_epsg()!=3763 or (ds.width,ds.height)!=(1500,2000):
            raise ValueError("wrong_DGT_mosaic_native_geometry")
        if list(ds.bounds)!=[80000,206000,83000,210000]:
            raise ValueError("wrong_DGT_mosaic_bounding_box")
        if ds.count!=1 or ds.dtypes[0]!="float32":
            raise ValueError("wrong_DGT_mosaic_raster_type")
        for col,row in SAMPLE_PIXELS:
            x,y=ds.xy(row,col)
            lon,lat=geom.transform(x,y)
            h=float(next(ds.sample([(x,y)],masked=True))[0])
            if not math.isfinite(h):
                raise ValueError("DGT_source_terrain_point_not_finite")
            _,_,converted=converter.transform(lon,lat,h,errcheck=True)
            if not math.isfinite(converted) or abs(converted-h)>1.0:
                raise ValueError("DGT_source_to_Alicante_candidate_numerically_invalid")
            points.append({"mosaic_cell_row":row,"mosaic_cell_column":col,
                           "PTTM06_x_m":x,"PTTM06_y_m":y,
                           "longitude_ETRS89":lon,"latitude_ETRS89":lat,
                           "original_DGT_Cascais_terrain_height_m":h,
                           "candidate_transformed_Alicante_height_m":float(converted),
                           "candidate_offset_m":float(converted-h),
                           "verified_vertical_reference_control_point":False})
    return points

def run(mosaic,fetcher=urlopen):
    import pyproj
    report={"mission":"MN-GEO-RAIL-001","worker":"W4",
            "stage":"source_geoid_grid_sha_pinned_numerical_vertical_checks",
            "observed_utc":datetime.now(timezone.utc).isoformat(),
            "producer_licence":"DGT GeodPT08 DGT+FCUL CC BY 4.0; Spain IGN EGM08-REDNAP per IGN",
            "official_sources":{
                "PT_DGT_geoid":"https://www.dgterritorio.gov.pt/atividades/geodesia/modelo-geoide",
                "PT_DGT_MDT":"https://www.dgterritorio.gov.pt/atividades/cartografia/cartografia-topografica/modelos-digitais",
                "ES_IGN_geodesic_calculator":"https://www.ign.es/web/calculadora-geodesica",
                "ES_IGN_MDT_orthometric_heights":"https://pnoa.ign.es/pnoa-lidar/productos-a-descarga"},
            "pyproj_version":pyproj.__version__,"DGT_mosaic_release":SOURCE_MOSAIC_RELEASE,
            "DGT_source_mosaic_SHA256":SOURCE_MOSAIC_SHA256,
            "geodesic_observed_benchmarks_used":0,
            "raster_independently_verified_vertical_datum":False,
            "IGN_WCS_original_raster_vertical_CRS_proven_by_GeoTIFF":False,
            "grid_nominal_EPSG_accuracy_is_empirical_PT_ES_validation":False,
            "actual_PT_ES_vertical_transform_acceptance":False,
            "whole_corridor_harmonization_done":False,
            "canonical_Fxx_accepted":False}
    with TemporaryDirectory(prefix="mn-w4-geoid-") as d:
        tmp=Path(d)
        report["verified_geoid_grids"]=[bounded_grid(n,details,tmp,fetcher=fetcher)
                                       for n,details in GRIDS.items()]
        converter,info=verified_transform(tmp)
        report["transformation_operation"]=info
        report["synthetic_site_checks"]=site_numeric_checks(converter)
        report["actual_DGT_terrain_sample_candidate_conversions"]=source_mosaic_checks(mosaic,converter)
    offsets=[x["candidate_offset_m"] for x in
             report["actual_DGT_terrain_sample_candidate_conversions"]]
    report["DGT_Mirandela_3x3_candidate_offset_min_m"]=min(offsets)
    report["DGT_Mirandela_3x3_candidate_offset_max_m"]=max(offsets)
    report["actual_DGT_points_9_processed"]=len(offsets)==9
    report["numeric_grid_pipeline_tested"]=True
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--DGT-mosaic",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=run(args.DGT_mosaic)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"verified_grids":len(report["verified_geoid_grids"]),
                      "DGT_real_sample_terrain_points":len(report["actual_DGT_terrain_sample_candidate_conversions"]),
                      "candidate_offset_min_m":report["DGT_Mirandela_3x3_candidate_offset_min_m"],
                      "candidate_offset_max_m":report["DGT_Mirandela_3x3_candidate_offset_max_m"],
                      "geodesic_benchmark_accepted":False,"Fxx":False}))

if __name__=="__main__":
    main()
