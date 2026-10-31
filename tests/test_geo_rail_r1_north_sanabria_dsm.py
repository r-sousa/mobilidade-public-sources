"""Offline Sanabria north extension guardrails, no network."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sp=importlib.util.spec_from_file_location("a1b",ROOT/"tools"/"geo_rail_r1_north_sanabria_dsm.py")
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class NorthReview(unittest.TestCase):
    def test_exact_four_sources_and_real_sanabria_coverage(self):
        self.assertEqual(m.SOURCE_TILE_COORDS,((41,-7),(41,-6),(42,-7),(42,-6)))
        self.assertEqual(m.BBOX,(-7,41.92,-5.55,42.30))
        self.assertEqual(int(round((m.BBOX[2]-m.BBOX[0])/m.ARC)),5220)
        self.assertEqual(int(round((m.BBOX[3]-m.BBOX[1])/m.ARC)),1368)
        self.assertTrue(m.BBOX[0] <= -6.6336 <= m.BBOX[2])
        self.assertTrue(m.BBOX[1] <= 42.0552 <= m.BBOX[3])
        self.assertTrue(m.OUT.endswith(".tif"))
        self.assertIn("SURFACE",m.__doc__)
        self.assertIn("Airbus Defence and Space",m.SOURCE_NOTICE)
        for lat,lon in m.SOURCE_TILE_COORDS:
            self.assertIn(m.tile(lat,lon),"Copernicus_"+m.tile(lat,lon))
        with self.assertRaises(ValueError):m.tile(42,-8)
if __name__=="__main__":unittest.main()
