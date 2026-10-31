"""Fail-closed offline contract for bounded anonymous G09 eastern DGT metadata scan."""
import importlib.util
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("geo_w2_east",ROOT/"tools"/"geo_rail_pt_east_stac_screen.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class EastScreenContractTests(unittest.TestCase):
    def test_review_grid_scope_without_a_rail_alignment(self):
        self.assertEqual(m.LON_EDGES,(-7.25,-7.15,-7.05,-6.95,-6.85,-6.75,-6.65))
        self.assertEqual(m.LAT_BANDS,((41.4,41.55),(41.55,41.7),(41.7,41.85),(41.85,42.0)))
        self.assertEqual(len(m.WINDOWS),24)
        self.assertEqual(m.EXPECTED_QUERIES,48)
        self.assertEqual(m.WINDOWS[0][1],[-7.25,41.4,-7.15,41.55])
        self.assertEqual(m.WINDOWS[-1][1],[-6.75,41.85,-6.65,42.0])
        self.assertEqual({z[0] for z in m.WINDOWS},{f"G09_{i:02d}_{j:02d}" for i in range(1,7) for j in range(1,5)})

    def test_out_of_scope_is_rejected_before_transport(self):
        with self.assertRaises(ValueError):
            m.inspect("G09_unknown",[0,0,1,1],"MDT-2m",transport=lambda *a,**kw:None)
        with self.assertRaises(ValueError):
            m.inspect(m.WINDOWS[0][0],m.WINDOWS[0][1],"unexpected",transport=lambda *a,**kw:None)

    def fixture(self,partial=False):
        rows=[]
        for i,(identifier,bbox) in enumerate(m.WINDOWS):
            for col in m.COLLECTIONS:
                rows.append({"window_id":identifier,"collection":col,"query_bbox_wgs84":bbox,
                             "status":"metadata_partial_next_page" if partial and i==0 else "metadata_complete_single_page",
                             "metadata_footprint_count":1,
                             "footprints":[{"tile_id":f"{col}-TEST_{i:03d}-2026","bbox_wgs84":bbox}]})
        return rows

    def test_complete_coverage_of_requests_is_metadata_only(self):
        doc=m.aggregate(self.fixture())
        self.assertTrue(doc["queries_all_complete"])
        self.assertEqual(doc["grid_window_count"],24)
        self.assertEqual(doc["query_count"],48)
        self.assertEqual(doc["paired_bboxes_equal"],24)
        self.assertEqual(doc["unique_candidate_ids_by_collection"],{"MDT-2m":24,"MDT-50cm":24})
        self.assertEqual(doc["review_strip_bbox_wgs84"],[-7.25,41.4,-6.65,42.0])
        self.assertFalse(doc["continuous_native_MDT_verified"])
        self.assertEqual(doc["source_raster_bytes_transferred"],0)
        self.assertFalse(doc["site_publication_authorized"])

    def test_partial_request_does_not_become_absence_claim(self):
        doc=m.aggregate(self.fixture(partial=True))
        self.assertFalse(doc["queries_all_complete"])
        self.assertIsNone(doc["paired_candidate_id_suffixes"])
        self.assertIsNone(doc["unique_candidate_ids_by_collection"])

if __name__=="__main__":
    unittest.main()
