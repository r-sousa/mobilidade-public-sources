"""G45 numerical genuine C2 station chord connectors, 30x7x3 governance."""
import unittest,pathlib,importlib.util,sys
try:import scipy,numpy,shapely,pyproj,matplotlib
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g45",root/"tools/geo_rail_g45_shifted_30station_quintic_horizontal.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G45 numerical regression requires official GIS runner")
class G45ApproachResearch(unittest.TestCase):
 def test_quintic_zero_endpoint_curvature(self):
  import numpy as np
  u=g.unit([1,0])
  a=g.quintic((0.,0.),(2000.,0.),u,u,.9)
  self.assertIsNotNone(a)
  self.assertLess(a[1],1e-8)
  self.assertAlmostEqual(a[2],2000,delta=10)
 def test_moderate_bend_requires_curvature(self):
  p=g.quintic((0.,0.),(2000.,1000.),[1,0],[1,0],1.1)
  self.assertGreater(p[1],0)
  self.assertGreater(1/p[1],100)
 def test_source_station_orientation_undirected_but_forward(self):
  import numpy as np
  u=g.oriented_station_heading(0.,(2000,0),(0,0))
  self.assertLess(u[0],0)
 def test_all30_research_rules(self):
  self.assertEqual(g.STATION_LENGTH,800.)
  self.assertEqual(g.EXT,(0,3000,6000,9000))
  self.assertEqual(g.RADIUS,{160:1500,200:2400,250:3700})
 def test_two_quintic_link_to_explicit_platform_straight(self):
  from shapely.geometry import LineString
  # Synthetic 20km original urban research grid, no earthworks implied.
  path=LineString([(-10000.,0.),(-8000.,0.),(-6000.,0.),(-4000.,0.),
       (-2000.,0.),(0.,0.),(2000.,0.),(4000.,0.),(6000.,0.),(8000.,0.),(10000.,0.)])
  c=g.station_case_geometry(path,(0.,500.),10000.,14000.,3000,3000,0.,.9)
  self.assertIsNotNone(c)
  self.assertEqual(c["station_straight_research_m"],800.)
  self.assertGreater(c["min_sampled_radius_m"],1000)
  self.assertTrue(len(c["sampled_QA_path_PT_TM06"])>20)
if __name__=="__main__":unittest.main()
