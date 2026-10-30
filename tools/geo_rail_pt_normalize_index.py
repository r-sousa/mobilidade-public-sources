#!/usr/bin/env python3
"""Create review-only GeoJSON rectangles from sanitized W2 DGT STAC inventory.

Rectangles are bbox envelopes, NOT original source geometries, validated
native rasters, or proof of interior coverage. No asset URLs/tokens permitted.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path


def make_geojson(receipt: dict) -> dict:
    if receipt.get("stage") != "pt_dgt_anonymous_stac_mdt_candidate_footprints":
        raise ValueError("expected approved DGT metadata receipt")
    observations=receipt.get("requests")
    if not isinstance(observations,list) or len(observations)!=12:
        raise ValueError("must contain all twelve reviewed collection-window requests")
    if any(x.get("status")!="metadata_returned_one_page" or x.get("has_next_page")
           for x in observations):
        raise ValueError("partial or unverified collection pages cannot build complete window index")
    seen={}
    provenance={}
    for row in observations:
        source=row.get("collection")
        if source not in ("MDT-2m","MDT-50cm"):
            raise ValueError("unknown source collection")
        provenance[(row["box_id"],source)]=row.get("source_response_sha256")
        for tile in row.get("footprints",[]):
            ident=tile.get("tile_id")
            bbox=tile.get("bbox_wgs84")
            if not isinstance(ident,str) or len(ident)>160:
                raise ValueError("bad tile identity")
            if (not isinstance(bbox,list) or len(bbox)!=4 or
                not (-11<=bbox[0]<bbox[2]<=-5 and 36<=bbox[1]<bbox[3]<=43)):
                raise ValueError("non-geographic bbox")
            key=(source,ident)
            if key in seen:
                if seen[key]["bbox"]!=bbox:
                    raise ValueError("conflicting bbox for repeated tile ID")
                seen[key]["windows"].add(row["box_id"])
                continue
            seen[key]={
                "bbox":bbox,
                "method":tile["bbox_method"],
                "windows":{row["box_id"]},
            }
    features=[]
    for ((collection,ident),item) in sorted(seen.items()):
        west,south,east,north=item["bbox"]
        features.append({
            "type":"Feature",
            "id":collection+"::"+ident,
            "geometry":{"type":"Polygon","coordinates":[[
                [west,south],[east,south],[east,north],[west,north],[west,south]
            ]]},
            "properties":{
                "mission":"MN-GEO-RAIL-001",
                "source_producer":"DGT CDD",
                "source_collection":collection,
                "producer_tile_id":ident,
                "query_window_ids":sorted(item["windows"]),
                "bbox_method":item["method"],
                "geometry_is_bbox_proxy_not_original_footprint":True,
                "native_raster_downloaded":False,
                "native_raster_validated":False,
                "public_redistribution_cleared":False,
                "canonical_accepted":False,
                "area_coverage_proven":False
            }
        })
    counts=Counter(x["properties"]["source_collection"] for x in features)
    return {
        "type":"FeatureCollection",
        "metadata":{
            "mission":"MN-GEO-RAIL-001",
            "stage":"W2_candidate_bbox_review_only",
            "source_receipt_observed_utc":receipt["observed_utc"],
            "source_reference":"https://cdd.dgterritorio.gov.pt/",
            "source_collection_counts":dict(sorted(counts.items())),
            "number_unique_source_collection_pairs":len(features),
            "all_reviewed_windows_resolved_one_page":True,
            "original_polygon_geometry_preserved":False,
            "rectangles_are_bounding_envelopes":True,
            "continuous_area_coverage_proven":False,
            "native_rasters_preserved":0,
            "canonical_identity_assigned":False,
            "canonical_acceptance":False,
            "no_raw_asset_links_or_credentials":True,
            "producer_response_sha256_by_window":{
                f"{window}:{collection}":digest
                for (window,collection),digest in sorted(provenance.items())
            }
        },
        "features":features,
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    output=make_geojson(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
                           encoding="utf-8")
    print(json.dumps(output["metadata"],ensure_ascii=False))


if __name__=="__main__":main()
