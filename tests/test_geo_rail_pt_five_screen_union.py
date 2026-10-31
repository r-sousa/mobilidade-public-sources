"""Deterministic public producer five-screen union with G10 gap-review receipt."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("geo_five_screen",ROOT/"tools"/"geo_rail_pt_five_screen_union.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FiveSourceReviewQA(unittest.TestCase):
    def test_whitelisted_five_receipts_and_G10_interface(self):
        self.assertEqual([(x[0],x[2],x[3]) for x in m.SOURCE_SPECS],
          [("E01-E06",6,12),("G07",10,20),("G08",16,32),("G09",24,48),("G10",2,4)])
        r=m.summarize_all(ROOT/"reports"/"mn-geo-rail-001")
        self.assertEqual(r["total_screen_windows"],58)
        self.assertEqual(r["total_complete_STAC_requests"],116)
        self.assertEqual(r["prior_four_screen_positions"],7070)
        self.assertEqual(r["prior_three_screen_positions"],4333)
        self.assertEqual(r["G10_metadata_positions_per_resolution"],230)
        self.assertEqual(r["G10_new_positions_vs_four_screens"]+r["G10_overlapping_positions_vs_four_screens"],230)
        self.assertEqual(r["distinct_candidate_product_positions"],7070+r["G10_new_positions_vs_four_screens"])
        self.assertEqual(r["matched_tile_suffixes_both_resolutions"],r["distinct_candidate_product_positions"])
        self.assertTrue(r["G10_no_unqueried_longitude_between_G08_G07_review_boxes"])
        self.assertTrue(r["G10_does_not_prove_raster_pixel_connectivity"])
        self.assertEqual(len(r["source_screens"]),5)
        self.assertFalse(r["entire_regional_native_DTM_coverage_verified"])
        self.assertFalse(r["vertical_datum_crossborder_harmonized"])
        self.assertFalse(r["Fxx_canonical_accepted"])
        self.assertFalse(r["Site_publication_authorized"])
        self.assertEqual(r["native_raster_bytes_downloaded_in_these_screens"],0)
        self.assertFalse(r["bbox_disagreement_across_screens_count"])
        self.assertGreaterEqual(r["G10_shared_position_IDs_with_G08"],0)
        self.assertGreaterEqual(r["G10_shared_position_IDs_with_G07"],0)
        self.assertEqual(len(r["bbox_exception_records"]),r["bbox_exceptions_2m_vs_50cm"])
if __name__=="__main__":unittest.main()
