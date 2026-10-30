"""Mocked W3 grid-union continuity checks: no live network required."""
import importlib.util
from pathlib import Path
import sys
import unittest

TOOLS=Path(__file__).resolve().parents[1]/"tools"
sys.path.insert(0,str(TOOLS))
spec=importlib.util.spec_from_file_location("geo_rail_es_continuity_qa",TOOLS/"geo_rail_es_continuity_qa.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy only on geo runner")
class ContinuityComparisonTests(unittest.TestCase):
    def test_identical_adjacent_and_union(self):
        import numpy as np
        a=np.ma.array([[10,11],[12,13]])
        b=np.ma.array([[14,15],[16,17]])
        union=np.ma.concatenate((a,b),axis=1)
        d=mod.compare_blocks(a,b,union)
        self.assertTrue(d["block_grid_equals_independent_union"])
        self.assertEqual(d["max_abs_diff_m"],0.0)
        self.assertEqual(d["cells_total"],8)

    def test_mismatched_union_detected(self):
        import numpy as np
        a=np.ma.array([[10,11]])
        b=np.ma.array([[12,13]])
        c=np.ma.array([[10,11,12,999]])
        d=mod.compare_blocks(a,b,c)
        self.assertFalse(d["block_grid_equals_independent_union"])
        self.assertEqual(d["max_abs_diff_m"],986.0)

    def test_disagreement_in_mask_detected(self):
        import numpy as np
        a=np.ma.array([[10,11]],mask=[[False,True]])
        b=np.ma.array([[12,13]])
        u=np.ma.array([[10,11,12,13]],mask=False)
        self.assertFalse(mod.compare_blocks(a,b,u)["block_grid_equals_independent_union"])


class BoundingTests(unittest.TestCase):
    def test_exact_areas_and_no_unbounded_queries(self):
        bbox_left=[200000,4600000,202000,4602000]
        bbox_right=[202000,4600000,204000,4602000]
        bbox_union=[200000,4600000,204000,4602000]
        for box in (bbox_left,bbox_right,bbox_union):
            for res in (5,25):
                self.assertIn("GetCoverage",mod.build_url(res,box))
        with self.assertRaises(ValueError):
            mod.build_url(5,[200000,4600000,220000,4620000])
        with self.assertRaises(ValueError):
            mod.build_url(2,bbox_union)

    @unittest.skipUnless(importlib.util.find_spec("pyproj"),"projection only on geo runner")
    def test_adjacent_boxes_share_exact_grid(self):
        from pyproj import Transformer
        t=Transformer.from_crs(4326,25830,always_xy=True)
        for lon,lat in mod.LOCATIONS.values():
            a,b,c=mod.site_boxes(lon,lat,t)
            self.assertEqual(a[2],b[0])
            self.assertEqual(a[0],c[0])
            self.assertEqual(b[2],c[2])
            self.assertEqual(a[1],c[1])
            self.assertEqual(a[3],c[3])


if __name__=="__main__":unittest.main()
