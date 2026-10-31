"""W4 official REDNAP vs real WCS terrain pixel pilot: no acceptance or datum claims."""
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("rednap_wcs",ROOT/"tools"/"geo_rail_rednap_wcs_ground_sample.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class RedNapGroundSamplingTests(unittest.TestCase):
    def test_six_fixed_reviewed_anchors_12_native_requests(self):
        self.assertEqual(len(m.ANCHORS),6)
        self.assertEqual(len({x[0] for x in m.ANCHORS}),6)
        self.assertEqual(m.RESOLUTIONS,(5,25))
        self.assertEqual(m.EXPECTED_WCS_CALLS,12)
        self.assertEqual({x[2] for x in m.ANCHORS},{"Zamora","Alcanices"})

    def test_six_real_source_marks_have_original_both_heights(self):
        selected,sha=m.official_candidates(ROOT/m.REDNAP_SOURCE)
        self.assertEqual(len(selected),6)
        self.assertEqual(len({x["local_deduplication_key"] for x in selected.values()}),6)
        self.assertTrue(all(x["both_heights_published"] for x in selected.values()))
        self.assertEqual(len(sha),64)
        self.assertTrue(all(x["original_source"].startswith("IGN REDNAP")
                            for x in selected.values()))

    @unittest.skipUnless(importlib.util.find_spec("pyproj"),"requires pyproj")
    def test_reviewed_native_WCS_2km_boxes_are_source_bounded(self):
        from pyproj import Transformer
        t=Transformer.from_crs(4326,25830,always_xy=True)
        selected,_=m.official_candidates(ROOT/m.REDNAP_SOURCE)
        for source in selected.values():
            bbox,x,y=m.requested_box(source["lon_etrs89"],source["lat_etrs89"],t)
            self.assertEqual(bbox[2]-bbox[0],2000)
            self.assertEqual(bbox[3]-bbox[1],2000)
            self.assertTrue(bbox[0]<x<bbox[2])
            self.assertTrue(bbox[1]<y<bbox[3])

    def test_missing_source_receipt_fails_closed(self):
        with self.assertRaises(FileNotFoundError):
            m.official_candidates(ROOT/"nonexistent-w4-original-receipt.json")

if __name__=="__main__":
    unittest.main()
