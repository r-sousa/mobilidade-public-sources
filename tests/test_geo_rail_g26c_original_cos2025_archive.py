import unittest,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
OK=all(importlib.util.find_spec(x) is not None for x in ("geopandas","pyogrio","shapely","pyproj"))
if OK:
 from geo_rail_g26c_original_DGT_COS2025_archived_clip import NATIONAL_ZIP_EXPECTED_BYTES,DGT_SOURCE,REQUIRED
@unittest.skipUnless(OK,"specialist original COS2025 GPKG source test")
class Source(unittest.TestCase):
 def test_original_size_and_edition(self):
  self.assertEqual(NATIONAL_ZIP_EXPECTED_BYTES,876190334)
  self.assertIn("COS2025v1-S2-gpkg.zip",DGT_SOURCE)
 def test_n1_and_n4_attributes(self):
  self.assertIn("cos25v1_n1_c",REQUIRED)
  self.assertIn("cos25v1_n4_l",REQUIRED)
if __name__=="__main__":unittest.main()
