"""G50 all 30 regional source G32 Copernicus DSM grade recalibration quality."""
import importlib.util,sys,pathlib,unittest
try:
 import scipy,numpy,rasterio,shapely,pyproj,matplotlib
 OK=True
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g50",root/"tools/geo_rail_g50_full30_actual_Copernicus_DSM_mixed_12p5_15.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"Copernicus terrain original GIS runner")
class G50TrueSourceDSM(unittest.TestCase):
 def test_five_corrected_rail_regimes(self):
  self.assertEqual(g.NOMINAL_GRADES_PERMILLE,(12.5,15.,18.,20.,25.))
  self.assertEqual(g.classify(12.5)["screen"],"primary_reference")
  self.assertEqual(g.classify(15)["screen"],"primary_normal")
  self.assertTrue(g.classify(18)["exceptional"])
  self.assertTrue(g.classify(20)["exceptional"])
  self.assertNotEqual(g.classify(25)["traffic"],g.classify(12.5)["traffic"])
 def test_original_surface_not_track_coverage(self):
  import numpy as np
  xy=np.array([[0.,0.],[200.,0.],[400.,0.]])
  h=np.array([100.,150.,90.])
  track=np.array([100.,110.,105.])
  m=g.stats(xy,h,track,12.5)
  self.assertAlmostEqual(m["original_DSM_400m_mean_abs_height_deviation_m_proxy"],21.25)
  self.assertTrue(m["DSM_contains_buildings_canopy_and_not_ground"])
  self.assertTrue(m["sparse_400m_study_smoothing_and_vertical_profile_NOT_3D_rail_design"])
 def test_no_fake_negative_geometry_just_unknown(self):
  self.assertEqual(g.SCENARIOS,(160,200,250))
  self.assertEqual(len(g.NOMINAL_GRADES_PERMILLE)*30*len(g.SCENARIOS),450)
 def test_18_25_baseline_consistency_math(self):
  from geo_rail_g31_terrain_natura_horizontal_vertical import profile
  import numpy as np
  xy=np.column_stack((np.arange(0,4400,400,dtype=float),np.zeros(11)))
  h=np.array([100.,120.,125.,90.,110.,130.,140.,150.,170.,180.,185.])
  for grad in (12.5,15.,18.,20.,25.):
   _,z,delta=profile(h,xy,grad)
   self.assertTrue(np.all(np.abs(np.diff(z))<=grad/1000*400+.011))
if __name__=="__main__":unittest.main()
