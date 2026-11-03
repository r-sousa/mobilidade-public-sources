"""G56 strict original BR3 BR4 source geographic diversity angle/shift research."""
import unittest,sys,importlib.util,pathlib
try:
 import numpy,scipy,shapely,pyproj,matplotlib
 OK=True
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g56",root/"tools/geo_rail_g56_BR3_BR4_G30_diversity_extended_curvature.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G56 source GIS stack")
class G56ResearchNoFalseBuildability(unittest.TestCase):
 def test_4_extra_km_per_end_without_redefining_original_limits(self):
  self.assertEqual(g.EXTENDED,(0,3000,6000,9000,12000,15000))
  self.assertEqual(g.EXT,(0,3000,6000,9000))
  self.assertEqual(g.ANGLE_SHIFT,(-20.,-10.,0.,10.,20.))
 def test_exact_mandatory_physical_Braganca_study_sites_and_source_G30(self):
  self.assertEqual(g.SITE_IDS,("BR3","BR4"))
  self.assertEqual(g.CID,"G30-geographic_diversity")
  self.assertNotIn("Sanabria",g.CID)
 def test_horizontal_radii_illustrative_not_train_service_cert(self):
  self.assertEqual(g.RADIUS,{160:1500,200:2400,250:3700})
  self.assertEqual(g.NEW_SCALES,(.55,.75,.9,1.1,1.35))
 def test_sampled_quintic_geometric_solution_not_standard_gauge(self):
  from shapely.geometry import LineString
  p=LineString([(-20000,0),(-16000,0),(-12000,0),(-8000,0),(-4000,0),
     (0,0),(4000,0),(8000,0),(12000,0),(16000,0),(20000,0)])
  q=g.station_case_geometry(p,(0,500),12000,28000,3000,3000,0,0.9)
  self.assertIsNotNone(q)
  self.assertEqual(q["station_straight_research_m"],800.)
  self.assertGreater(q["min_sampled_radius_m"],500)
if __name__=="__main__":unittest.main()
