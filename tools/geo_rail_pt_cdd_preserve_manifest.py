#!/usr/bin/env python3
"""Verify first original DGT MDT tile for immutable public prerelease preservation.

Only the already-validated native Mirandela raster is authorized for this
pilot. Fail closed if source bytes, metadata, geometry, resolution or native QA
changed. Does NOT publish, contact GitHub, or access CDD credentials.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from geo_rail_pt_native_intake_qa import stream_sha256,MAX_NATIVE_BYTES

TILE_ID="MDT-2m-282510-09-2024"
EXPECTED_SHA="761bc7ee18ef9377cca97556b6dececc14b8765c017c168dbf15552d8c9d78ba"
EXPECTED_BYTES=1_219_159
TAG="mn-geo-rail-001-dgt-mdt2m-mirandela-sha256-"+EXPECTED_SHA[:16]
RASTER_NAME=TILE_ID+".tif"
MANIFEST_NAME=TILE_ID+".sha256.json"
PRODUCER="Direção-Geral do Território (DGT)"


def verify_and_prepare(native:Path,receipt:Path,out_dir:Path):
    if not receipt.is_file() or receipt.stat().st_size>100_000:
        raise ValueError("missing_or_oversized_source_QA_receipt")
    q=json.loads(receipt.read_text(encoding="utf-8"))
    if (q.get("status")!="native_tiff_authenticated_and_validated_pilot"
            or q.get("producer_tile_id")!=TILE_ID
            or q.get("collection")!="MDT-2m"
            or q.get("diagnostic_site")!="mirandela"
            or q.get("native_staged_for_reviewed_public_release") is not True):
        raise ValueError("source_QA_not_approved_for_public_release")
    grid=q.get("raster",{})
    if (grid.get("horizontal_crs")!="EPSG:3763"
            or grid.get("resolution_m")!=[2.0,2.0]
            or grid.get("width_px")!=500 or grid.get("height_px")!=500
            or grid.get("valid_pixels")!=250_000
            or grid.get("bbox_intersects_source_proxy") is not True):
        raise ValueError("unexpected_native_raster_specification")
    if not native.is_file() or native.is_symlink():
        raise ValueError("invalid_or_missing_native_raster")
    n,sha=stream_sha256(native,MAX_NATIVE_BYTES)
    if (n!=EXPECTED_BYTES or sha!=EXPECTED_SHA or
            n!=q.get("native_file_bytes") or sha!=q.get("native_sha256")):
        raise ValueError("native_bytes_not_identical_to_first_verified_DGT_source")
    out_dir.mkdir(parents=True,exist_ok=True)
    manifest={
        "mission":"MN-GEO-RAIL-001","stage":"DGT_source_preacceptance_archive",
        "producer":PRODUCER,"source_portal":"https://cdd.dgterritorio.gov.pt/",
        "source_license":"CC BY 4.0, attribute Direção-Geral do Território",
        "source_collection":"MDT-2m","producer_tile_id":TILE_ID,
        "original_native_bytes":n,"original_native_sha256":sha,
        "raster_quality":grid,
        "initial_source_QA_run":"https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41149632416",
        "original_pixels_unchanged":True,
        "continuous_corridor_coverage_verified":False,
        "crossborder_vertical_harmonization_verified":False,
        "canonical_Fxx_accepted":False,"site_publication_authorized":False
    }
    (out_dir/MANIFEST_NAME).write_text(
        json.dumps(manifest,sort_keys=True,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    text=(
        "Original DGT MDT-2m GeoTIFF — Mirandela; PRE-ACCEPTANCE EVIDENCE.\n\n"
        "Source: Direção-Geral do Território (DGT), Centro de Dados, "
        "https://cdd.dgterritorio.gov.pt/\n"
        "License: CC BY 4.0, attribution DGT, "
        "https://creativecommons.org/licenses/by/4.0/\n"
        "Tile "+TILE_ID+", original "+str(n)+" bytes, SHA-256 "+sha+".\n"
        "Original source QA https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41149632416\n\n"
        "The unchanged 1 km2 native file is retained for evidence. It is NOT "
        "validated continuous corridor coverage; NO cross-border vertical "
        "harmonization, canonical Fxx assignment or Mobilidade Norte Site "
        "publication is authorized.\n")
    (out_dir/"release-notes.txt").write_text(text,encoding="utf-8")
    return {"status":"verified_for_preacceptance_source_release",
            "tag":TAG,"asset_filename":RASTER_NAME,
            "manifest_filename":MANIFEST_NAME,
            "size_bytes":n,"sha256":sha}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native",type=Path,required=True)
    parser.add_argument("--qa",type=Path,required=True)
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    result=verify_and_prepare(args.native,args.qa,args.out_dir)
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
