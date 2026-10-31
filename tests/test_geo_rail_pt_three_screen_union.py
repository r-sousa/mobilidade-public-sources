"""Offline source QA of consolidated DGT anonymous catalog deduplication."""
import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("three_screen_union",ROOT/"tools"/"geo_rail_pt_three_screen_union.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ThreeScreenSourceContractTests(unittest.TestCase):
    def test_real_sanitized_sources_complete_and_paired(self):
        p=ROOT/"reports/mn-geo-rail-001"
        d=m.summarize_all(p)
        self.assertEqual(d["total_screen_windows"],32)
        self.assertEqual(d["total_complete_STAC_requests"],64)
        self.assertEqual(d["distinct_candidate_product_positions"],4333)
        self.assertEqual(d["unique_DGT_product_IDs_by_collection"],{"MDT-2m":4333,"MDT-50cm":4333})
        self.assertEqual(d["identical_2m_and_50cm_producer_id_suffix_pair_count"],4333)
        self.assertEqual(d["bbox_disagreement_across_screens_count"],0)
        self.assertFalse(d["entire_regional_native_DTM_coverage_verified"])
        self.assertTrue(d["catalogue_rectangles_are_NOT_validated_native_pixel_footprints"])
        self.assertEqual(d["native_raster_bytes_downloaded_in_these_screens"],0)
        self.assertEqual({x["name"] for x in d["source_screens"]},{"E01-E06","G07","G08"})

    def test_fails_closed_when_source_or_receipt_missing(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                m.summarize_all(Path(tmp))

if __name__=="__main__":
    unittest.main()
