import unittest,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(k) is not None for k in ("pyogrio","pyproj","shapely"))
if HAVE:
 from geo_rail_g27c_original_SNIT_REN_RAN_CRUS_seven_WFS_intersections import COLLECTIONS,MAXFEATURES,RADIUS,MAXSOURCEBYTES
@unittest.skipUnless(HAVE,"specialist GIS original SNIT source preflight")
class G27C(unittest.TestCase):
 def test_legal_original_source_and_bounded_work(self):
  self.assertEqual(set(COLLECTIONS),{"REN_NORTE","RAN_PT","CRUS_NATIONAL"})
  self.assertEqual(MAXFEATURES,5)
  self.assertEqual(RADIUS,400)
  self.assertLessEqual(MAXSOURCEBYTES,10000000)
if __name__=="__main__":unittest.main()
