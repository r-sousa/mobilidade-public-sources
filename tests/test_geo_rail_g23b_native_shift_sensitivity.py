"""G23B source-offset physical soil screen Pareto and geometry tests."""
import sys,unittest,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(k) is not None for k in ("numpy","rasterio","pyproj"))
if HAVE:
 from geo_rail_g23b_native_shift_heading_sensitivity import pareto,OFFSETS_ALONG,OFFSETS_CROSS,HEADING_DEG,TOTAL_PER_CASE
@unittest.skipUnless(HAVE,"G23B raster verification specialist job")
class G23B(unittest.TestCase):
 def test_lattice_3_by_3_by_3(self):
  self.assertEqual(len(OFFSETS_ALONG)*len(OFFSETS_CROSS)*len(HEADING_DEG),27)
  self.assertEqual(TOTAL_PER_CASE,27)
  self.assertIn(0.,OFFSETS_ALONG)
  self.assertIn(0.,OFFSETS_CROSS)
  self.assertIn(0.,HEADING_DEG)
 def test_no_missing_terrain_accepted_as_optimum(self):
  base={"station_p90_m":3,"approach18_p90_m":6,
       "lateral_shift_absolute_m":0,"longitudinal_shift_absolute_m":0,
       "heading_rotation_absolute_deg":0,"valid_coverage_98pct_station_and_approach":True}
  shifted={**base,"station_p90_m":2,"approach18_p90_m":5,
       "lateral_shift_absolute_m":200}
  absent={**base,"station_p90_m":0,"approach18_p90_m":0,
       "valid_coverage_98pct_station_and_approach":False}
  self.assertEqual(pareto([base,shifted,absent]),[base,shifted])
 def test_true_source_improvement_can_dominate_equal_shift(self):
  a={"station_p90_m":8,"approach18_p90_m":5,
     "lateral_shift_absolute_m":200,"longitudinal_shift_absolute_m":0,
     "heading_rotation_absolute_deg":20,"valid_coverage_98pct_station_and_approach":True}
  b={**a,"station_p90_m":7,"approach18_p90_m":4}
  self.assertEqual(pareto([a,b]),[b])
if __name__=="__main__":unittest.main()
