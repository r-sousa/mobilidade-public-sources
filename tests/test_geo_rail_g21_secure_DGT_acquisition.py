"""G21 exact G20 source identity/QA guards, specialist dependencies optional in global test suite."""
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(n) is not None for n in ("requests","rasterio","numpy"))
if HAVE:
 from geo_rail_g21_protected_original_DGT_native_acquisition import TILE,MAX_TOTAL_BYTES,MAX_NEW_TILES
@unittest.skipUnless(HAVE,"G21 original native raster authorization tests only specialist job")
class G21(unittest.TestCase):
 def test_exact_pinned_source_tile_identifier(self):
  self.assertTrue(TILE.fullmatch("MDT-2m-228481-07-2024"))
  self.assertTrue(TILE.fullmatch("MDT-2m-313539-06-2024"))
  self.assertFalse(TILE.fullmatch("MDT-2m-other"))
  self.assertFalse(TILE.fullmatch("MDT-50cm-313539-06-2024"))
 def test_bound_total_unproven_raster_source(self):
  self.assertLessEqual(MAX_NEW_TILES,54)
  self.assertLessEqual(MAX_TOTAL_BYTES,160000000)
if __name__=="__main__":unittest.main()
