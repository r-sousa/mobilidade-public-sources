"""Offline invariants for real CNIG WCS preserved-source descriptive 5m vs 25m QA."""
from pathlib import Path
import unittest,json
R=Path(__file__).resolve().parents[1]
P=R/"reports"/"mn-geo-rail-001"/"es-cnig-zamora-WCS-5m-25m-resolution-QA.json"
class WCS5vs25MetadataQA(unittest.TestCase):
    def test_source_sha_and_fixed_area_pinned_without_mislabelled_vertical_accuracy(self):
        q=json.loads(P.read_text())
        self.assertEqual(q["distinct_territory_km2"],1)
        self.assertEqual(q["bbox_epsg25830"],[270500,4597800,271500,4598800])
        self.assertEqual(q["data_by_resolution_m"]["5"]["valid_cells"],40000)
        self.assertEqual(q["data_by_resolution_m"]["25"]["valid_cells"],1600)
        self.assertEqual(q["data_by_resolution_m"]["5"]["source_sha256"],"b3ddf00ccbbfbafe2e46e21769a4be6076a4df1e8d5de186e92eb429862a99db")
        self.assertEqual(q["data_by_resolution_m"]["25"]["source_sha256"],"1983cd9f53ed8f3e9ade85c7316cd6a6dd94cbef2f944a1ef8fb7ed109471dd4")
        for s in ("5","25"):
            r=q["data_by_resolution_m"][s]
            self.assertTrue(r["value_integer_encoded"])
            self.assertEqual(r["GeoTIFF_dtype"],"int16")
            self.assertEqual(r["unique_elevation_values_count"],37)
        self.assertEqual(q["comparison_cells"],1600)
        self.assertAlmostEqual(q["difference_RMS_m"],1.0197411436242032,places=9)
        self.assertAlmostEqual(q["difference_MAE_m"],0.51275,places=9)
        self.assertTrue(q["this_is_not_an_estimate_of_vertical_error_or_RMSE_vs_survey_marks"])
        self.assertFalse(q["independent_national_vertical_datum_validation"])
        self.assertFalse(q["PT_ES_vertical_harmonization_validated"])
        self.assertFalse(q["continuity_of_rail_corridor_pixels_validated"])
        self.assertFalse(q["Fxx_accepted"])
        self.assertFalse(q["Site_authorized"])
if __name__=="__main__":unittest.main()
