"""G22 original 2m DGT ground sampling tests: missing masks NEVER synthetic ground."""
import sys,unittest,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(q) is not None for q in ("numpy","rasterio","pyproj"))
if HAVE:
 import numpy as np
 from geo_rail_g22_native_dgt2m_station_strips import evaluate_cell,strip
@unittest.skipUnless(HAVE,"specialist raster georeferencing test; global lean CI skips")
class G22(unittest.TestCase):
 def original(self):
  a=np.ma.array(np.full((500,500),525.,dtype="float32"),mask=np.zeros((500,500),dtype=bool))
  return {(228,481):a}
 def test_original_ground_and_outside_are_distinguished(self):
  orig=self.original()
  self.assertEqual(evaluate_cell(28500,180500,orig),525.)
  self.assertIsNone(evaluate_cell(35000,180500,orig))
  orig[228,481][250,250]=np.ma.masked
  self.assertIsNone(evaluate_cell(28500,180500,orig))
 def test_level_ground_no_fictitious_earthworks(self):
  src=self.original()
  out=strip((28500,180500),(1,0),src,400,50,10,10,.0025)
  self.assertEqual(out["source_profile_fit_status"],"eligible_original_ground_screen_NOT_station")
  self.assertEqual(out["modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY"],0)
  self.assertEqual(out["source_original_DGT2m_valid_sample_count"],200)
  self.assertFalse(out["engineering_suitability_demonstrated"])
 def test_absent_original_ground_fails_closed(self):
  out=strip((35500,180500),(1,0),self.original(),400,50,10,10,.0025)
  self.assertEqual(out["source_profile_fit_status"],"insufficient_original_ground_pixels")
  self.assertIsNone(out["modelled_total_terrain_cut_plus_fill_m3_NOT_ENGINEERING_QUANTITY"])
 def test_study_strip_void_is_not_filled(self):
  src=self.original()
  src[228,481][:,:]=np.ma.masked
  out=strip((28500,180500),(1,0),src,400,50,10,10,.0025)
  self.assertEqual(out["source_original_DGT2m_valid_sample_count"],0)
  self.assertEqual(out["source_missing_samples_count"],200)
  self.assertIsNone(out["source_vertical_deviation_p90_m"])
if __name__=="__main__":unittest.main()
