"""G46 actual DGT84 1km-source tile list vs research 2D station spline gaps."""
import unittest,sys,pathlib,importlib.util
try:import numpy,shapely,matplotlib
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g46",root/"tools/geo_rail_g46_original_DGT2m_84tile_vs_station_splines.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"Dedicated source GIS stack")
class G46ActualSourceTileGate(unittest.TestCase):
 def test_dgt_original_index_from_PT_Tm06_coordinates(self):
  from shapely.geometry import LineString
  domain=LineString([(1000,1500),(1900,1500)])
  required,covered,missing=g.tile_footprint(domain,{(201,302)})
  self.assertTrue((201,302) in required)
  self.assertEqual(len(covered),1)
  self.assertEqual(len(missing),len(required)-1)
 def test_station_3km_clipping_center_measured_on_horizontal_path(self):
  sol={"sampled_QA_path_PT_TM06":[[0,0],[3000,0],[3500,0],[6500,0],[8500,0]]}
  sub=g.segment_from_station(sol,[5000,0],1500)
  self.assertAlmostEqual(sub.length,3000,places=1)
 def test_site_must_be_on_actual_approach_not_guessed(self):
  sol={"sampled_QA_path_PT_TM06":[[0,0],[3000,0],[7000,0]]}
  with self.assertRaisesRegex(ValueError,"physical_point_not_on"):
   g.segment_from_station(sol,[5000,200],1500)
 def test_original_84_exact_and_no_final_acquisition(self):
  g45={"all_G10_27_and_G30_3_retained":True,"source_30_options":30,
       "seven_original_DGT2m_study_sites":7,
       "all_630_route_site_speed_horizontal_screen_cases":[{}]*630}
  g37={"source_84_original_DGT_tile_ids_in_PTTM06":[[i+201,302] for i in range(84)],
       "tile_index_offset_original_DGT":[200,301],"no_new_DGT_2m_tile_order":True}
  self.assertEqual(len(g.validate(g45,g37)),84)
  g37["source_84_original_DGT_tile_ids_in_PTTM06"][0]=g37["source_84_original_DGT_tile_ids_in_PTTM06"][1]
  with self.assertRaisesRegex(ValueError,"original_DGT84"):g.validate(g45,g37)
if __name__=="__main__":unittest.main()
