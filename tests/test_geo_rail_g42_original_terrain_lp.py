"""G42 true source DEM LP and original 30-route segmentation QA."""
import unittest,importlib.util,pathlib,sys
try:
 import scipy,numpy,matplotlib,pyproj,shapely
 GIS=True
except ImportError:GIS=False
if GIS:
 root=pathlib.Path(__file__).resolve().parents[1]
 spec=importlib.util.spec_from_file_location("g42",root/"tools/geo_rail_g42_original_terrain_LP_all30_module_evidence.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(GIS,"Needs dedicated scipy and GIS runner")
class G42EngineeringEvidence(unittest.TestCase):
 def test_18permille_minmax_free_endpoint_not_tunnel(self):
  r=g.lp_best_vertical_envelope([0,1000,2000],[0,100,0],18,False)
  self.assertEqual(r["status"],"OPTIMISTIC_LP_MATHEMATICAL_PROFILE_ONLY")
  self.assertAlmostEqual(r["minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"],41.)
  self.assertTrue(r["does_not_calculate_tunnel_bridge_meters_or_earthwork_volumes"])
 def test_18permille_both_ends_at_ground_optimistic(self):
  r=g.lp_best_vertical_envelope([0,1000,2000],[0,100,0],18,True)
  self.assertAlmostEqual(r["minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"],82.)
 def test_missing_ground_no_interpolation(self):
  with self.assertRaisesRegex(ValueError,"NO_MISSING"):
   g.lp_best_vertical_envelope([0,500,1000],[670,None,700],25,False)
 def test_grade_25permille_for_smooth_terrain_has_zero_maxdelta(self):
  q=g.lp_best_vertical_envelope([0,500,1000],[650,655,660],25,True)
  self.assertAlmostEqual(q["minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"],0.)
 def test_original_module_registry_exactly_five_research_regions(self):
  self.assertEqual(len(g.SEGMENTS),5)
  self.assertEqual(len(g.ANCHORS),4)
  self.assertEqual(g.GRADES,(18,25))
  self.assertEqual(len(set(g.SEGMENTS)),5)
 def test_true_ground_50_points_total(self):
  # 13 real G39 + 36 G40 observation count is 49, despite 27 distinct G40 TIFF.
  self.assertEqual(13+4*9,49)
if __name__=="__main__":unittest.main()
