"""Exact bounded contract for missing G08/G07 anonymous STAC review interface."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("g10_interface",ROOT/"tools"/"geo_rail_pt_g10_interface_stac_screen.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class G10Review(unittest.TestCase):
    def test_exact_grid_gap_scope(self):
        self.assertEqual(m.LON_EDGES,(-7.85,-7.75))
        self.assertEqual(m.LAT_BANDS,((41.20,41.30),(41.30,41.40)))
        self.assertEqual(m.EXPECTED_QUERIES,4)
        self.assertEqual(m.WINDOWS,(("G10_01_01",[-7.85,41.20,-7.75,41.3]),("G10_01_02",[-7.85,41.3,-7.75,41.4])))
        self.assertEqual(set(m.COLLECTIONS),{"MDT-2m","MDT-50cm"})

    def rows(self,partial=False):
        out=[]
        for i,(n,b) in enumerate(m.WINDOWS):
            for collection in m.COLLECTIONS:
                out.append({"window_id":n,"collection":collection,"query_bbox_wgs84":b,
                    "status":"metadata_partial_next_page" if partial and i==1 else "metadata_complete_single_page",
                    "metadata_footprint_count":1,
                    "footprints":[{"tile_id":f"{collection}-SYNTHETIC{i}","bbox_wgs84":b}]})
        return out

    def test_offline_result_never_claims_native_raster(self):
        d=m.aggregate(self.rows())
        self.assertTrue(d["queries_all_complete"])
        self.assertEqual(d["query_count"],4)
        self.assertEqual(d["grid_window_count"],2)
        self.assertEqual(d["paired_candidate_id_suffixes"],2)
        self.assertEqual(d["paired_bboxes_equal"],2)
        self.assertFalse(d["continuous_native_MDT_verified"])
        self.assertFalse(d["canonical_Fxx_accepted"])
        self.assertFalse(d["site_publication_authorized"])
        self.assertEqual(d["source_raster_bytes_transferred"],0)

    def test_partial_never_reports_zero_coverage(self):
        d=m.aggregate(self.rows(partial=True))
        self.assertFalse(d["queries_all_complete"])
        self.assertIsNone(d["unique_candidate_ids_by_collection"])
        self.assertIsNone(d["paired_candidate_id_suffixes"])
        with self.assertRaises(ValueError):
            m.inspect("OUT_OF_SCOPE",[-7.85,41.4,-7.75,41.55],"MDT-2m",transport=lambda *a,**k:None)
if __name__=="__main__":unittest.main()
