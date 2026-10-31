"""Review-contract tests for bounded anonymous DGT Porto–Vila Real west metadata scan."""
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("w2_west",ROOT/"tools"/"geo_rail_pt_west_stac_screen.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class WestScreenContractTests(unittest.TestCase):
    def test_exact_scope_rectangles_and_queries(self):
        self.assertEqual(m.EXPECTED_QUERIES,32)
        self.assertEqual(len(m.WINDOWS),16)
        self.assertEqual(m.LON_EDGES[0],-8.65)
        self.assertEqual(m.LON_EDGES[-1],-7.85)
        self.assertEqual(m.LAT_BANDS,((41.05,41.20),(41.20,41.35)))
        self.assertEqual({x[0] for x in m.WINDOWS},{f"G08_{i:02d}_{j:02d}" for i in range(1,9) for j in (1,2)})
        self.assertEqual(m.WINDOWS[0][1],[-8.65,41.05,-8.55,41.2])
        self.assertEqual(m.WINDOWS[-1][1],[-7.95,41.2,-7.85,41.35])

    def test_rejects_out_of_scope_public_STAC_query(self):
        with self.assertRaises(ValueError):
            m.inspect("unreviewed",[-9,41,-8,41.5],"MDT-2m",transport=lambda *a,**kw:None)
        with self.assertRaises(ValueError):
            m.inspect(m.WINDOWS[0][0],m.WINDOWS[0][1],"other",transport=lambda *a,**kw:None)

    def sample(self, partial=False):
        rows=[]
        for i,(identifier,bbox) in enumerate(m.WINDOWS):
            for collection in m.COLLECTIONS:
                rows.append({
                    "window_id":identifier,"collection":collection,
                    "query_bbox_wgs84":bbox,
                    "status":("metadata_partial_next_page" if partial and i==3 else "metadata_complete_single_page"),
                    "metadata_footprint_count":1,
                    "footprints":[{"tile_id":f"{collection}-SOURCE{i:03d}-2026",
                                   "bbox_wgs84":bbox}]
                })
        return rows

    def test_complete_paired_metadata_only_not_native_rasters(self):
        report=m.aggregate(self.sample())
        self.assertTrue(report["queries_all_complete"])
        self.assertEqual(report["query_count"],32)
        self.assertEqual(report["grid_window_count"],16)
        self.assertEqual(report["unique_candidate_ids_by_collection"],{"MDT-2m":16,"MDT-50cm":16})
        self.assertEqual(report["paired_candidate_id_suffixes"],16)
        self.assertEqual(report["paired_bboxes_equal"],16)
        self.assertEqual(report["review_strip_bbox_wgs84"],[-8.65,41.05,-7.85,41.35])
        self.assertFalse(report["continuous_native_MDT_verified"])
        self.assertFalse(report["canonical_Fxx_accepted"])

    def test_partial_receipt_fails_closed_without_candidate_count_claim(self):
        report=m.aggregate(self.sample(partial=True))
        self.assertFalse(report["queries_all_complete"])
        self.assertIsNone(report["unique_candidate_ids_by_collection"])
        self.assertIsNone(report["paired_bboxes_equal"])

if __name__=="__main__":
    unittest.main()
