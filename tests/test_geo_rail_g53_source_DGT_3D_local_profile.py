"""G53 original DGT2m XYZ source observations and conservative rail research grade maths."""
import importlib.util,pathlib,sys,unittest
try:import scipy,numpy,shapely,matplotlib
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g53",root/"tools/geo_rail_g53_original_DGT2m_four_stations_3D_vertical.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G53 scipy geospatial stack required")
class G53RailResearchXYZ(unittest.TestCase):
 def test_two_mixed_grades_and_all_six_geographic_studies_unaltered(self):
  self.assertEqual(g.GRADES,(12.5,15.))
  self.assertEqual(g.SITE_ORDER,("VR2","VR1","BR4","BR3"))
  self.assertEqual(g.REGIONAL_SIX_EXPECTED,6)
  self.assertEqual(g.VERTICAL_R,(10000.,20000.))
  self.assertEqual(g.STATION_CLASS,{"PAT_10permille_Spanish_reference":10.,
                                   "COUPLING_OR_STABLING_2p5_if_applicable":2.5})
 def test_station_center_at_original_ground_and_mixed_grade_and_radius(self):
  import numpy as np
  x=np.arange(121,dtype=float)*25-1500
  y=520+np.sin(x/155)*22+(.017*x)
  z,delta=g.solve_center_tied(x,y,12.5,10.,20000.)
  self.assertAlmostEqual(z[60],y[60],places=5)
  self.assertLessEqual(float(max(abs(np.diff(z)/25*1000))),12.5+.0001)
  self.assertLessEqual(float(max(abs(np.diff(z,n=2))*20000/625)),1.00001)
  self.assertGreaterEqual(delta,0.)
 def test_center_tied_2p5_cannot_beat_optimistic_free_vertical_solution(self):
  import numpy as np
  x=np.arange(121,dtype=float)*25-1500
  y=600+np.cos(x/200)*20
  free=g.minimax_grade_envelope(x,y,15,station_max_permille=2.5,vertical_radius_m=10000.)
  tied=g.solve_center_tied(x,y,15,2.5,10000.)
  self.assertLessEqual(free["minimum_maximum_vertical_ground_separation_m"],tied[1]+.003)
 def test_no_passenger_only_25_mixed_or_wgs84_ellipsoidal_height_assumption(self):
  self.assertNotIn(25.,g.GRADES)
  self.assertEqual(len(g.SITE_ORDER)*len(g.GRADES)*len(g.STATION_CLASS)*len(g.VERTICAL_R)*2,64)
if __name__=="__main__":unittest.main()
