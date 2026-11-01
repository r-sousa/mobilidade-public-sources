"""G44 the old station positions are physical points, not 29 different stations."""
import unittest,importlib.util,pathlib
try:import scipy,shapely,pyproj,numpy,matplotlib
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 spec=importlib.util.spec_from_file_location("g44",root/"tools/geo_rail_g44_seven_original_station_sites_horizontal_chords.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G44 dedicated GIS stack")
class G44StudyStations(unittest.TestCase):
 def test_straight_chord_no_circular_tangent_requirement(self):
  a=g.CITY_BOUNDS["Vila_Real"]
  west,east=a["west"],a["east"]
  site=((west[0]+east[0])/2,(west[1]+east[1])/2)
  p=g.geom(site,"Vila_Real",200)
  self.assertAlmostEqual(p["source_site_two_chord_deflection_deg"],0.,places=4)
  self.assertAlmostEqual(p["circular_minimum_tangent_length_for_assumed_radius_m"],0.,places=3)
  self.assertTrue(p["does_not_include_station_straight_or_clothoid_or_full_track_connection"])
 def test_off_axis_study_station_circular_corner_tangent_changes_with_R(self):
  west,east=g.CITY_BOUNDS["Vila_Real"]["west"],g.CITY_BOUNDS["Vila_Real"]["east"]
  site=((west[0]+east[0])/2,west[1]+9000)
  a=g.geom(site,"Vila_Real",160)
  b=g.geom(site,"Vila_Real",250)
  self.assertGreater(b["circular_minimum_tangent_length_for_assumed_radius_m"],
                     a["circular_minimum_tangent_length_for_assumed_radius_m"])
 def test_assumptions_160_200_250(self):
  self.assertEqual(g.RADIUS,{160:1500,200:2400,250:3700})
  self.assertEqual(set(g.CITY_BOUNDS),{"Vila_Real","Braganca"})
 def test_legal_clearance_never_assumed(self):
  self.assertEqual(len(g.ANCHORS),4)
  self.assertEqual(len(g.SEGMENTS),5)
if __name__=="__main__":unittest.main()
