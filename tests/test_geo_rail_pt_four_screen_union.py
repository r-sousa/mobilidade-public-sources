"""Deterministic QA against the four official, whitelisted DGT STAC source receipts."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("geo_four_screen",ROOT/"tools"/"geo_rail_pt_four_screen_union.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FourSourceScreenQA(unittest.TestCase):
    def test_four_source_immutable_observation_contract(self):
        self.assertEqual([(x[0],x[2],x[3]) for x in m.SOURCE_SPECS],
          [("E01-E06",6,12),("G07",10,20),("G08",16,32),("G09",24,48)])
        result=m.summarize_all(ROOT/"reports"/"mn-geo-rail-001")
        self.assertEqual(result["total_screen_windows"],56)
        self.assertEqual(result["total_complete_STAC_requests"],112)
        self.assertEqual(result["distinct_candidate_product_positions"],7070)
        self.assertEqual(result["prior_three_screen_positions"],4333)
        self.assertEqual(result["G09_positions_new_vs_prior_three_screens"],2737)
        self.assertEqual(result["G09_positions_overlapping_prior_three_screens"],462)
        self.assertEqual(result["matched_tile_suffixes_both_resolutions"],7070)
        self.assertEqual(result["identical_pair_bbox_proxy_count"],7016)
        self.assertEqual(result["bbox_exceptions_2m_vs_50cm"],54)
        self.assertEqual(len(result["bbox_exception_records"]),54)
        self.assertEqual(result["bbox_disagreement_across_screens_count"],0)
        self.assertTrue(result["catalogue_rectangles_are_NOT_validated_native_pixel_footprints"])
        self.assertTrue(result["bbox_disagreement_IS_not_proven_native_pixel_void"])
        self.assertFalse(result["entire_regional_native_DTM_coverage_verified"])
        self.assertFalse(result["Fxx_canonical_accepted"])
        self.assertFalse(result["Site_publication_authorized"])
        self.assertEqual(result["native_raster_bytes_downloaded_in_these_screens"],0)
        self.assertTrue(all(0 < r["max_bbox_edge_displacement_approx_m"] < 3
                            for r in result["bbox_exception_records"]))
        self.assertEqual(len({r["source_tile_suffix"] for r in result["bbox_exception_records"]}),54)

if __name__=="__main__":unittest.main()
