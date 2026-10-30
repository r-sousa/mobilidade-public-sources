"""Tests for public, review-only DGT bounding envelope GeoJSON."""
import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/"tools"/"geo_rail_pt_normalize_index.py"
spec=importlib.util.spec_from_file_location("normalizer",path)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def receipt():
    rows=[]
    for i in range(6):
        for resolution in ("MDT-2m","MDT-50cm"):
            rows.append({
                "box_id":f"E{i+1:02d}","collection":resolution,
                "status":"metadata_returned_one_page","has_next_page":False,
                "source_response_sha256":"f"*64,
                "footprints":[{"tile_id":f"TILE-{i}","collection":resolution,
                               "bbox_wgs84":[-7.0,41.5,-6.99,41.51],
                               "bbox_method":"geometry_recovered"}]
            })
    return {"stage":"pt_dgt_anonymous_stac_mdt_candidate_footprints",
            "observed_utc":"2026-10-30T00:00:00Z","requests":rows}


class IndexTests(unittest.TestCase):
    def test_unique_counts_and_caveats(self):
        a=m.make_geojson(receipt())
        self.assertEqual(len(a["features"]),12)
        self.assertEqual(a["metadata"]["source_collection_counts"],{
            "MDT-2m":6,"MDT-50cm":6})
        self.assertFalse(a["metadata"]["continuous_area_coverage_proven"])
        self.assertTrue(a["features"][0]["properties"]["geometry_is_bbox_proxy_not_original_footprint"])
        self.assertFalse(a["features"][0]["properties"]["native_raster_validated"])

    def test_partial_receipt_rejected(self):
        a=receipt()
        a["requests"][0]["has_next_page"]=True
        with self.assertRaises(ValueError):
            m.make_geojson(a)

    def test_conflicting_duplicate_tile_rejected(self):
        a=receipt()
        a["requests"][2]["footprints"][0]["tile_id"]="TILE-0"
        a["requests"][2]["footprints"][0]["bbox_wgs84"]=[-6.9,41.5,-6.89,41.51]
        with self.assertRaises(ValueError):
            m.make_geojson(a)


if __name__=="__main__":unittest.main()
