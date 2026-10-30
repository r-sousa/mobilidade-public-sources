#!/usr/bin/env python3
"""MN-GEO-RAIL-001 W4: reproduce vertical CRS operation/grid availability.

This is a technical CRS/grid audit, NOT harmonization of any source raster.
The only downloads are two bounded public PROJ geoid grids from cdn.proj.org;
files are temporary, SHA-256 identified, and never committed/published.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen

GRIDS=(
 "pt_dgt_GeodPT08.tif",
 "es_ign_egm08-rednap.tif",
)
ORIGIN="https://cdn.proj.org"
MAX_EACH_BYTES=20_000_000
EXAMPLES=(
 {"label":"PT_Mirandela_exploratory","longitude":-7.2,"latitude":41.5},
 {"label":"PT_Nordeste_exploratory","longitude":-6.9,"latitude":41.75},
)


def transfer_grid(name: str, workspace: Path, opener=urlopen) -> dict:
    if name not in GRIDS:
        raise ValueError("grid not in reviewed public PROJ source list")
    url=f"{ORIGIN}/{name}"
    response={"filename":name,"source_url":url,"status":"unverified",
              "preserved_in_git":False,"open_license_indicated_by_proj_catalogue":True}
    try:
        destination=workspace / name
        sha=hashlib.sha256()
        bytes_seen=0
        with opener(Request(url,headers={"User-Agent":"MN-GEO-RAIL-001-vertical-grid-audit/1.0"}),timeout=35) as download:
            if download.status!=200:
                raise RuntimeError(f"Grid CDN HTTP {download.status}")
            declared=download.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared)>MAX_EACH_BYTES:
                raise ValueError("CDN grid larger than 20MB configured bound")
            with destination.open("wb") as output:
                while True:
                    b=download.read(262144)
                    if not b: break
                    bytes_seen+=len(b)
                    if bytes_seen>MAX_EACH_BYTES:
                        raise ValueError("CDN grid exceeded 20MB bound")
                    sha.update(b)
                    output.write(b)
        if bytes_seen<1024:
            raise ValueError("Grid unexpectedly small")
        with destination.open("rb") as file:
            if file.read(4) not in (bytes((73,73,42,0)), bytes((77,77,0,42)),
                                   bytes((73,73,43,0)), bytes((77,77,0,43))):
                raise ValueError("PROJ grid not TIFF format")
        response.update(status="downloaded_temporary_tiff",bytes=bytes_seen,sha256=sha.hexdigest())
    except Exception as error:
        response.update(status="unverified",error_type=type(error).__name__,
                        error_excerpt=str(error)[:200])
    return response


def summarize_group(group):
    ops=[]
    for transformer in group.transformers:
        ops.append({"description":transformer.description,"accuracy_m":transformer.accuracy,
                    "definition":transformer.definition[:900]})
    missing=[]
    for op in group.unavailable_operations:
        missing.append({"description":op.name,"accuracy_m":op.accuracy,
                        "grids":[{"short_name":g.short_name,"available":g.available,
                                  "url":g.url,"open_license":g.open_license}
                                 for g in op.grids]})
    return {"best_available":bool(group.best_available),"available_operations":ops,
            "unavailable_operations":missing}


def run():
    import pyproj
    from pyproj import CRS,datadir
    from pyproj.transformer import TransformerGroup
    report={
        "mission":"MN-GEO-RAIL-001","worker":"W4",
        "stage":"vertical_cascais_alicante_proj_operation_audit",
        "observed_utc":datetime.now(timezone.utc).isoformat(),
        "references":{
            "portugal_horizontal":"EPSG:3763",
            "portugal_vertical":"EPSG:5780",
            "spain_horizontal":"EPSG:25830",
            "spain_vertical":"EPSG:5782",
            "copernicus_egm2008_vertical":"EPSG:3855",
            "vertical_grid_issuer":"https://cdn.proj.org/",
            "portugal_geoid_official":"https://www.gov.pt/servicos/aceder-online-ao-modelo-do-geoide-geodpt08-",
            "spain_geoid_ign":"https://datos-geodesia.ign.es/geoide/Leeme_Readme.pdf"
        },
        "pyproj_version":pyproj.__version__,
        "source_crs_name":CRS.from_epsg(5780).name,
        "target_crs_name":CRS.from_epsg(5782).name,
        "is_real_terrain_harmonization":False,
        "vertical_crs_of_CNIG_wcs_native_raster_explicitly_verified":False,
        "actual_PT_ES_benchmark_observation_checked":False,
        "native_rasters_reprojected":0,
        "canonical_acceptance":False,
    }
    with TemporaryDirectory(prefix="mn-vertical-grids-") as tmp:
        workspace=Path(tmp)
        # No network grid discovery; initial baseline exposes missing resources.
        before=TransformerGroup(CRS.from_epsg(5780),CRS.from_epsg(5782),
                                allow_ballpark=False)
        report["before"] = summarize_group(before)
        downloads=[transfer_grid(name,workspace) for name in GRIDS]
        report["grid_downloads"]=downloads
        if all(item["status"]=="downloaded_temporary_tiff" for item in downloads):
            datadir.append_data_dir(str(workspace))
            after=TransformerGroup(CRS.from_epsg(5780),CRS.from_epsg(5782),
                                   allow_ballpark=False)
            report["after"]=summarize_group(after)
            report["best_grid_operation_reproducibly_available"]=bool(after.best_available)
            if after.best_available and after.transformers:
                transformer=after.transformers[0]
                report["transformation_examples_not_observed_altitudes"]=[]
                for site in EXAMPLES:
                    lon,lat=site["longitude"],site["latitude"]
                    x,y,height=transformer.transform(lon,lat,0.0)
                    valid=all(math.isfinite(v) for v in (x,y,height))
                    report["transformation_examples_not_observed_altitudes"].append({
                        "label":site["label"],"longitude":lon,"latitude":lat,
                        "synthetic_input_Cascais_height_m":0,
                        "synthetic_output_Alicante_height_m":height if valid else None,
                        "operation_returns_finite":valid
                    })
        else:
            report["best_grid_operation_reproducibly_available"]=False
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    doc=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(doc,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"grid_downloads":[(x["filename"],x["status"],x.get("bytes"))
        for x in doc["grid_downloads"]],"best_available":doc["best_grid_operation_reproducibly_available"]}))
    if not doc["best_grid_operation_reproducibly_available"]:
        raise SystemExit("Best grid-based vertical transformation not available; inspect audit")


if __name__=="__main__":
    main()
