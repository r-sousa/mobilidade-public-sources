#!/usr/bin/env python3
"""W3: preserve two bounded, *actual WCS response* TIFFs from IGN/CNIG Spain.

A WCS response GeoTIFF is NOT represented as the producer's original
LiDAR/MDT source archive. Public service URL and original response bytes
only, with no account, credentials, signed URLs, or route inference.
One 1-km2 Zamora sample in both 5m and 25m: NOT 2 km2 or corridor coverage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

from geo_rail_es_wcs_sample import (
    BASE,COVERAGES,WEST,SOUTH,EAST,NORTH,
    coverage_url,download_bounded,
)

EXPECTED_CRS_EPSG=25830
AREA_BBOX=[WEST,SOUTH,EAST,NORTH]
FILE_BY_COVERAGE={
    "Elevacion25830_5":"cnig-zamora-WCS-response-5m.tif",
    "Elevacion25830_25":"cnig-zamora-WCS-response-25m.tif",
}
LICENSE="CC BY 4.0, with attribution to Instituto Geografico Nacional (IGN)/CNIG"
LICENSE_EVIDENCE="https://datos.gob.es/es/catalogo/e0dat0002-wcs-de-modelos-digitales-del-terreno-de-espana1"

def _check_tiff(path:Path,coverage_id:str):
    import numpy as np
    import rasterio
    if coverage_id not in FILE_BY_COVERAGE or not path.is_file():
        raise ValueError("missing_preapproved_WCS_source_response")
    resolution=int(coverage_id.rsplit("_",1)[1])
    expected_width=(EAST-WEST)//resolution
    expected_height=(NORTH-SOUTH)//resolution
    with rasterio.open(path) as ds:
        if ds.driver!="GTiff" or ds.count!=1 or ds.crs is None or ds.crs.to_epsg()!=EXPECTED_CRS_EPSG:
            raise ValueError("not_expected_IGN_WCS_EPSG25830_GeoTIFF")
        if (ds.width,ds.height)!=(expected_width,expected_height):
            raise ValueError("wrong_WCS_source_response_shape")
        if (abs(ds.res[0]-resolution)>0.001 or abs(ds.res[1]-resolution)>0.001 or
            not np.allclose(tuple(ds.bounds),(WEST,SOUTH,EAST,NORTH),atol=0.001,rtol=0)):
            raise ValueError("wrong_WCS_source_response_bounds_or_resolution")
        values=ds.read(1,masked=True)
        valid=int(values.count())
        if valid!=expected_width*expected_height:
            raise ValueError("not_all_WCS_sample_cells_valid")
        if not np.isfinite(values.filled(np.nan)).all():
            raise ValueError("non_finite_WCS_terrain_cells")
        wkt=ds.crs.to_wkt()
        return {
            "crs_horizontal_epsg":EXPECTED_CRS_EPSG,
            "vertical_crs_encoded_in_GeoTIFF":("VERTCRS[" in wkt or "VERT_CS[" in wkt),
            "vertical_datum_by_independent_geodetic_control_verified":False,
            "width_px":ds.width,"height_px":ds.height,
            "pixel_resolution_m":resolution,
            "bbox_epsg25830":AREA_BBOX,
            "valid_cells":valid,"masked_cells":int(np.ma.count_masked(values)),
            "min_terrain_m":float(values.min()),"max_terrain_m":float(values.max()),
            "dtype":ds.dtypes[0],"nodata":ds.nodata
        }

def sample_all(destination:Path):
    destination.mkdir(parents=True,exist_ok=True)
    result={
        "mission":"MN-GEO-RAIL-001","worker":"W3",
        "stage":"official_CNIG_WCS_response_GeoTIFF_immutable_preservation_candidate",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "producer":"Instituto Geografico Nacional / Centro Nacional de Informacion Geografica, Spain",
        "public_WCS_base":BASE,
        "reuse_license":LICENSE,
        "reuse_license_evidence":LICENSE_EVIDENCE,
        "one_identical_sample_area_for_both_resolutions":True,
        "study_sample_bbox_epsg25830":AREA_BBOX,
        "sample_area_distinct_km2":1,
        "is_original_source_producer_tile":False,
        "is_byte_for_byte_original_public_WCS_response":True,
        "native_raster_coverage_between_exploratory_sites_verified":False,
        "datum_PT_ES_harmonized":False,
        "Fxx_accepted":False,"Site_publication_authorized":False,
        "entries":[]
    }
    for coverage_id in sorted(COVERAGES):
        dest=destination/FILE_BY_COVERAGE[coverage_id]
        response_bytes,received_sha,content_type=download_bounded(coverage_url(coverage_id),dest)
        metadata=_check_tiff(dest,coverage_id)
        if response_bytes != dest.stat().st_size or hashlib.sha256(dest.read_bytes()).hexdigest()!=received_sha:
            raise ValueError("WCS_response_byte_count_or_hash_changed")
        result["entries"].append({
            "coverage_id":coverage_id,
            "filename":dest.name,
            "bytes":response_bytes,
            "sha256":received_sha,
            "content_type":content_type,
            "status":"exact_original_WCS_response_qualified",
            "raster":metadata
        })
    if len(result["entries"])!=2:
        raise ValueError("both_WCS_resolutions_required")
    (destination/"cnig-zamora-WCS-source-QA.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8"
    )
    return result

def verify_existing(destination:Path):
    manifest=json.loads((destination/"cnig-zamora-WCS-source-QA.json").read_text())
    if (manifest.get("sample_area_distinct_km2")!=1
       or manifest.get("Fxx_accepted") is not False
       or manifest.get("Site_publication_authorized") is not False
       or manifest.get("datum_PT_ES_harmonized") is not False
       or manifest.get("is_original_source_producer_tile") is not False):
        raise ValueError("unsafe_WCS_metadata_or_licensing_governance")
    pairs=manifest["entries"]
    if len(pairs)!=2 or set(x["coverage_id"] for x in pairs)!=set(COVERAGES):
        raise ValueError("missing_WCS_COVERAGES")
    for item in pairs:
        coverage_id=item["coverage_id"]
        expected=FILE_BY_COVERAGE[coverage_id]
        if item["filename"]!=expected or item["status"]!="exact_original_WCS_response_qualified":
            raise ValueError("nonapproved_WCS_asset_or_status")
        p=destination/expected
        if not p.is_file() or p.stat().st_size!=item["bytes"] or p.stat().st_size>5_000_000:
            raise ValueError("incorrect_WCS_file_size")
        if hashlib.sha256(p.read_bytes()).hexdigest()!=item["sha256"]:
            raise ValueError("native_WCS_SHA256_not_verified")
        if _check_tiff(p,coverage_id)!=item["raster"]:
            raise ValueError("native_WCS_raster_metadata_recheck_disagrees")
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--acquire",type=Path)
    g.add_argument("--verify-existing",type=Path)
    a=p.parse_args()
    d=sample_all(a.acquire) if a.acquire else verify_existing(a.verify_existing)
    print(json.dumps({"status":"verified","source":"public WCS response, not producer original MDT",
        "n_distinct_sample_km2":d["sample_area_distinct_km2"],
        "rasters":[{"coverage":r["coverage_id"],"size":r["bytes"],"sha256":r["sha256"],"valid_cells":r["raster"]["valid_cells"],
          "vertical_crs_encoded":r["raster"]["vertical_crs_encoded_in_GeoTIFF"]}
          for r in d["entries"]]},sort_keys=True))
if __name__=="__main__":main()
