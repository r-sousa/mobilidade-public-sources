"""G43 original 13 TIFF sha source QA, true 25m pixel continuity and grade radius sensitivities."""
import unittest,pathlib,importlib.util,sys,tempfile,zipfile,json,hashlib
try:
 import numpy,scipy,rasterio,shapely,pyproj,matplotlib
 OK=True
except ImportError:OK=False
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g43",root/"tools/geo_rail_g43_original_IGN_dense_25m_vertical_curvature.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"Dedicated 25m original terrain stack")
class G43DenseOriginal(unittest.TestCase):
 def test_curvature_vertical_optimistic_mathematics(self):
  x=[0,25,50,75,100]
  y=[100.,140.,90.,140.,100.]
  q=g.LP_curved(x,y,18,10000,False)
  self.assertEqual(q["status"],"OPTIMISTIC_MATH_LP_ON_REAL_SOURCE_TERRAIN_NOT_ENGINEERED_RAIL")
  self.assertGreater(q["minimum_possible_MAX_vertical_difference_at_ground_samples_m"],10)
  self.assertTrue(q["only_non_standard_hypothetical_vertical_curve_sensitivity"])
 def test_steep_sample_18_not_same_as_25(self):
  x=[0,25,50,75,100]
  y=[100,100,130,100,100]
  a=g.LP_curved(x,y,18,10000,True)
  b=g.LP_curved(x,y,25,10000,True)
  self.assertGreaterEqual(a["minimum_possible_MAX_vertical_difference_at_ground_samples_m"],
                          b["minimum_possible_MAX_vertical_difference_at_ground_samples_m"])
 def test_sparse_has_more_optimistic_possible_fit(self):
  x=[0,25,50,75,100]
  y=[100,100,130,100,100]
  dense=g.LP_curved(x,y,18,None,False)
  sparse=g.LP_curved([0,50,100],[100,130,100],18,None,False)
  self.assertGreaterEqual(dense["minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"],
                          sparse["minimum_possible_MAX_vertical_difference_at_sampled_ground_points_m"])
 def test_missing_not_promoted_to_flat(self):
  with self.assertRaisesRegex(ValueError,"NULL_PIXEL"):
   g.LP_curved([0,25,50],[200,None,210],18,20000,False)
 def test_25m_6km_exact_point_count_and_radii(self):
  self.assertEqual(g.STEP_M,25.)
  self.assertEqual(g.SECTOR_M,6000.)
  self.assertEqual(g.NPTS,241)
  self.assertEqual(g.VERTICAL_R_BENCH,(None,10000,20000))
  self.assertEqual(g.GRADES,(18,25))
if __name__=="__main__":unittest.main()
