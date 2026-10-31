"""Offline contract checks for native 279503 real source QA summary (no network, no secrets)."""
from pathlib import Path
import unittest,json,re
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"reports"/"mn-geo-rail-001"/"pt-dgt-native-279503-NP159-source-qa-acceptance.json"

class Source279503Receipt(unittest.TestCase):
    def test_actual_source_and_unaccepted_gates(self):
        r=json.loads(P.read_text())
        self.assertEqual(r["status"],"verified_original_DGT_279503_and_preacceptance_preservation")
        self.assertEqual(r["tile"],"MDT-2m-279503-09-2024")
        t=r["original_tif"]
        self.assertEqual(t["bbox_epsg3763"],[79000,202000,80000,203000])
        self.assertEqual(t["res_m"],[2,2])
        self.assertEqual(t["valid_pixels"],250000)
        self.assertEqual(t["masked_pixels"],0)
        self.assertEqual(t["size_bytes"],1212288)
        self.assertTrue(re.fullmatch("[0-9a-f]{64}",t["sha256"]))
        self.assertTrue(re.fullmatch("[0-9a-f]{64}",r["full_QA_file"]["sha256"]))
        self.assertEqual(r["relation_to_existing_native_DGT_mosaic"]["distinct_total_native_QA_area_km2"],13)
        self.assertTrue(r["relation_to_existing_native_DGT_mosaic"]["newly_QA_tile_is_not_contiguous_with_grid12"])
        self.assertFalse(r["relation_to_existing_native_DGT_mosaic"]["full_corridor_native_coverage_verified"])
        self.assertFalse(t["vertical_crs_embedded_in_GeoTIFF"])
        for g in range(1,6):self.assertFalse(r[f"accepted_G{g}"])
        self.assertFalse(r["canonical_Fxx_assigned"])
        self.assertFalse(r["site_publication_authorized"])
        self.assertFalse(r["rail_alignment_ready"])

    def test_no_five_false_survey_residuals(self):
        r=json.loads(P.read_text())["NP159_context_only"]
        self.assertEqual(r["original_DGT_mark_count_sharing_surrogate_XY"],5)
        self.assertEqual(r["DGT_WFS_surrogate_XY_epsg3763"],[79468.618,202288.178])
        self.assertAlmostEqual(r["raster_cell_height_m"],229.54966735839844,places=5)
        self.assertFalse(r["individual_survey_mark_positions_validated"])
        self.assertFalse(r["per_mark_residuals_computed"])
        self.assertFalse(r["vertical_DTM_RMSE_estimated"])
if __name__=="__main__":unittest.main()
