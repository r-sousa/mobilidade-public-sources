"""G19 original DGT2m footprint vs study reference tests, conditional GIS dependency."""
import unittest,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(q) is not None for q in ("shapely","pyproj"))
if HAVE:
 from shapely.geometry import box
 from geo_rail_g19_native_DGT_station_ground_gates import closest_native,coverage_native_sources
@unittest.skipUnless(HAVE,"G19 geographic geometry tests run on specialist GIS job")
class NativeProof(unittest.TestCase):
 def test_actual_bbox_contains_2m_source_reference(self):
  src=[{"geom":box(100,100,2100,2100),"source":"original_DGT_native","elevation_p95_p05_m_of_4km2_sector_NOT_local_station":45}]
  c=closest_native((1100,1100),src)
  self.assertTrue(c["direct_point_native_2m_pixel_coverage_in_verified_45km2"])
  self.assertEqual(c["surrounding_1km_square_native_2m_source_covered_fraction"],1.0)
 def test_proximity_never_claims_native_pixels(self):
  src=[{"geom":box(0,0,1000,1000),"source":"original_DGT_native","elevation_p95_p05_m_of_4km2_sector_NOT_local_station":21}]
  c=closest_native((1050,500),src)
  self.assertFalse(c["direct_point_native_2m_pixel_coverage_in_verified_45km2"])
  self.assertEqual(c["distance_to_nearest_preserved_QA_DGT_native_2m_footprint_m"],50.0)
  self.assertTrue(c["coverage_absence_not_terrain_coverage_absence_at_producer"])
if __name__=="__main__":unittest.main()
