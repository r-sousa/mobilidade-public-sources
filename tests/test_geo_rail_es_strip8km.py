"""Offline bounded geometry and real-grid comparison contracts for W3."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("w3_strip",ROOT/"tools"/"geo_rail_es_strip8km.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class StripGeometryTests(unittest.TestCase):
    def test_rejects_out_of_bounds_and_unreviewed_size(self):
        self.assertIn("Elevacion25830_5",m.build_url(5,[200000,4599000,208000,4601000]))
        self.assertIn("Elevacion25830_25",m.build_url(25,[200000,4599000,202000,4601000]))
        for bb in ([200000,4599000,212000,4601000],
                   [100000,4599000,108000,4601000],
                   [200000.1,4599000,208000,4601000]):
            with self.assertRaises(ValueError):
                m.build_url(5,bb)
        with self.assertRaises(ValueError):
            m.build_url(0,[200000,4599000,208000,4601000])

    @unittest.skipUnless(importlib.util.find_spec("pyproj"),"requires pyproj for geometry")
    def test_four_adjacent_blocks_align(self):
        from pyproj import Transformer
        t=Transformer.from_crs(4326,25830,always_xy=True)
        for lon,lat in m.LOCATIONS.values():
            blocks,union=m.strip_boxes(lon,lat,t)
            self.assertEqual(len(blocks),4)
            self.assertEqual(sum(b[2]-b[0] for b in blocks),8000)
            self.assertEqual(blocks[0][0],union[0])
            self.assertEqual(blocks[-1][2],union[2])
            self.assertEqual([b[0] for b in blocks],[union[0]+i*2000 for i in range(4)])

@unittest.skipUnless(importlib.util.find_spec("numpy"),"requires numpy for grid comparison")
class StripPixelTests(unittest.TestCase):
    def test_match_full_valid_strip(self):
        import numpy as np
        blocks=[np.ma.array([[1,2],[3,4]]) for _ in range(4)]
        whole=np.ma.concatenate(blocks,axis=1)
        out=m.compare_all(blocks,whole)
        self.assertTrue(out["verified"])
        self.assertEqual(out["total_cells"],16)
        self.assertEqual(out["maximum_abs_difference_m"],0.0)

    def test_reject_mismatched_pixel_or_mask(self):
        import numpy as np
        blocks=[np.ma.array([[1,2]]) for _ in range(4)]
        whole=np.ma.concatenate(blocks,axis=1)
        bad=whole.copy()
        bad[0,3]=99
        self.assertFalse(m.compare_all(blocks,bad)["verified"])
        missing=whole.copy()
        missing.mask=np.zeros(missing.shape,dtype=bool)
        missing.mask[0,0]=True
        self.assertFalse(m.compare_all(blocks,missing)["verified"])

if __name__=="__main__":
    unittest.main()
