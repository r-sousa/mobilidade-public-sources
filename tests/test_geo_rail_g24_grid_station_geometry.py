"""G24 source grid vs native original ground site orientation screen regression."""
import unittest,sys,importlib.util,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(z) is not None for z in ("shapely","pyproj"))
if HAVE:
 from shapely.geometry import LineString,Point
 from geo_rail_g24_grid_station_connection_geometry import axis_bearing_mismatch_deg,source_angular_context,choose_shortlist
@unittest.skipUnless(HAVE,"G24 source geometry tests run in specialist GIS job")
class G24(unittest.TestCase):
 def test_rail_heading_axis_not_direction(self):
  self.assertAlmostEqual(axis_bearing_mismatch_deg(0,180),0)
  self.assertAlmostEqual(axis_bearing_mismatch_deg(170,10),20)
  self.assertAlmostEqual(axis_bearing_mismatch_deg(10,170),20)
  self.assertAlmostEqual(axis_bearing_mismatch_deg(90,0),90)
 def test_straight_source_horizontal_proximity_is_not_station_feasibility(self):
  route=LineString([(0,0),(2000,0),(4000,0),(6000,0),(8000,0),(10000,0)])
  x=source_angular_context(route,Point(4000,1000),40)
  self.assertAlmostEqual(x["distance_to_original_G10_2km_grid_route_m"],1000)
  self.assertTrue(x["within_original_3km_halfwidth_research_band_NOT_rail_corridor"])
  self.assertAlmostEqual(x["hypothetical_station_straight_heading_mismatch_to_3km_source_grid_chord_deg"],40)
  self.assertAlmostEqual(x["illustrative_speed_radius_pure_heading_change_arc_lower_bounds"]["200"]["pure_constant_radius_turn_arc_length_m_lower_bound_for_this_angle"],2400*math.radians(40),delta=.1)
  self.assertTrue(x["illustrative_speed_radius_pure_heading_change_arc_lower_bounds"]["200"]["transition_curve_cant_and_tangent_entry_NOT_modelled"])
 def test_over_3km_does_not_imply_false_connection(self):
  route=LineString([(0,0),(3000,0),(6000,0),(9000,0)])
  x=source_angular_context(route,Point(4500,3101),0)
  self.assertFalse(x["within_original_3km_halfwidth_research_band_NOT_rail_corridor"])
 def test_shortlist_cannot_fabricate_missing_terrain(self):
  base={"G23B_original_DGT2m_platform_and_approach_coverage_ge_98pct":True,
    "original_source_reference_position_and_heading_unchanged":True,
    "within_original_3km_halfwidth_research_band_NOT_rail_corridor":True,
    "distance_to_original_G10_2km_grid_route_m":100,
    "hypothetical_station_straight_heading_mismatch_to_3km_source_grid_chord_deg":10,
    "G23B_station_vertical_p90_DGT2m_m":2,"G23B_approach_18permille_vertical_p90_DGT2m_m":4}
  invalid={**base,"G23B_original_DGT2m_platform_and_approach_coverage_ge_98pct":False,
   "original_source_reference_position_and_heading_unchanged":False,
   "G23B_station_vertical_p90_DGT2m_m":0}
  self.assertEqual(choose_shortlist([base,invalid]),[("BASELINE",base)])
if __name__=="__main__":unittest.main()
