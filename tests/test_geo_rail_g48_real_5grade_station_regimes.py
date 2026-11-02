"""G48 Portuguese rail project evidence source-faithful five-gradient policy tests."""
import unittest,sys,pathlib,importlib.util
try:
 import numpy,scipy,matplotlib
 OK=True
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g48",root/"tools/geo_rail_g48_real_source_5grade_traffic_station_recalibration.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G48 dedicated scipy runner")
class SourceNormsRecalibration(unittest.TestCase):
 def test_primary_mixed_replaces_18_25_not_auto_legal(self):
  self.assertEqual(g.NOMINAL_GRADES_PERMILLE,(12.5,15.,18.,20.,25.))
  self.assertEqual(g.classify(12.5)["screen"],"primary_reference")
  self.assertEqual(g.classify(15)["screen"],"primary_normal")
  self.assertTrue(g.classify(18)["exceptional"])
  self.assertTrue(g.classify(20)["exceptional"])
  self.assertEqual(g.classify(25)["screen"],"passenger_functional_alternative")
  self.assertEqual(g.SPEED_SCREENS_KMH,(160,200,250))
 def test_true_18_to_12p5_tightening_does_not_improve_mathematical_fit(self):
  x=[0,25,50,75,100,125,150]
  y=[100,120,100,150,100,120,100]
  a=g.minimax_grade_envelope(x,y,12.5)["minimum_maximum_vertical_ground_separation_m"]
  b=g.minimax_grade_envelope(x,y,18)["minimum_maximum_vertical_ground_separation_m"]
  c=g.minimax_grade_envelope(x,y,25)["minimum_maximum_vertical_ground_separation_m"]
  self.assertGreaterEqual(a,b)
  self.assertGreaterEqual(b,c)
 def test_fixed_both_ends_cannot_improve_optimistic_distance(self):
  x=[0,25,50,75,100]
  y=[100,150,100,120,100]
  a=g.minimax_grade_envelope(x,y,15,fixed_endpoints=False)
  b=g.minimax_grade_envelope(x,y,15,fixed_endpoints=True)
  self.assertLessEqual(a["minimum_maximum_vertical_ground_separation_m"],
                      b["minimum_maximum_vertical_ground_separation_m"])
 def test_impossible_source_ground_tied_endpoints_are_not_rail_corridor_rejection(self):
  r=g.minimax_grade_envelope([0,25,50,75,100],[100,150,100,120,80],12.5,fixed_endpoints=True)
  self.assertEqual(r["status"],"INFEASIBLE_ONLY_FOR_BOTH_GROUND_TIED_ENDS_AND_THIS_GRADE")
  self.assertIsNone(r["minimum_maximum_vertical_ground_separation_m"])
  self.assertTrue(r["not_a_proof_of_corridor_or_railway_infeasibility"])
 def test_station_freight_engagement_2p5_is_not_every_passenger_platform_rule(self):
  import numpy as np
  x=np.arange(121,dtype=float)*25-1500
  y=np.asarray([400+i*0.022 for i in x])
  no=g.minimax_grade_envelope(x,y,25)["minimum_maximum_vertical_ground_separation_m"]
  passenger=g.minimax_grade_envelope(x,y,25,station_max_permille=10)["minimum_maximum_vertical_ground_separation_m"]
  coupling=g.minimax_grade_envelope(x,y,25,station_max_permille=2.5)["minimum_maximum_vertical_ground_separation_m"]
  self.assertLessEqual(no,passenger)
  self.assertLessEqual(passenger,coupling)
  self.assertGreater(coupling,no)
 def test_vertical_curve_sensitivity_is_conditional_not_certified(self):
  x=list(range(0,1025,25))
  y=[100+20*(i%3) for i in range(len(x))]
  free=g.minimax_grade_envelope(x,y,15)
  curved=g.minimax_grade_envelope(x,y,15,vertical_radius_m=10000)
  self.assertGreaterEqual(curved["minimum_maximum_vertical_ground_separation_m"],
      free["minimum_maximum_vertical_ground_separation_m"]-.002)
 def test_no_missing_source_no_unregistered_grade(self):
  with self.assertRaisesRegex(ValueError,"no_missing"):
   g.minimax_grade_envelope([0,25,50],[500,float("nan"),510],15)
  with self.assertRaisesRegex(ValueError,"unregistered"):
   g.minimax_grade_envelope([0,25,50],[500,505,510],35)
 def test_source_profile_exact_n_four_original_sites_and_no_missing(self):
  g43={"source_all30_preserved_previous_G42":True,
      "original_IGN_source_1km_TIFF_reused":13,
      "G43_original_25m_ground_sampling_n":241,
      "G43_original_dense_ground_valid_n":241,
      "G43_original_dense_ground_missing_n":0,
      "all_source_points":[{"source_research_chainage_m":i*25,
        "actual_IGN25_original_ground_m":650+i/10,
        "source_status":"ACTUAL_ORIGINAL_IGN25_PIXEL_QA",
        "ground_source_raster_SHA256":"a"*64} for i in range(241)]}
  g47={"all_30_G10_27_G30_3_retained":True,
      "reused_existing_original_DGT_2m_GitHub_public_tile_assets_count":18,
      "no_new_DGT_credentialed_source_acquisition":True,
      "source_18_native_original_DGT2m_tile_file_SHA_receipts":[{} for _ in range(18)],
      "real_4x121_25m_sample_original_native_DGT2m_pixel_rows":[
        {"site_id":s,"source_station_chainage_relative_m":i*25-1500,
         "original_DGT_2m_ground_elevation_m":430+i/10,
         "source_status":"VALID_ORIGINAL_DGT_2M_GROUND_PIXEL",
         "original_file_SHA256":"b"*64}
         for s in ("VR1","VR2","BR3","BR4") for i in range(121)],
      "four_real_original_source_native_ground_station_3km_profiles":[
        {"site_id":s,"mandatory_city":"Vila_Real" if s.startswith("VR") else "Braganca",
         "native_DGT2m_terrain_pixels_valid_n":121} for s in ("VR1","VR2","BR3","BR4")]}
  east,cities=g.source_profiles(g43,g47)
  self.assertEqual(len(east["x_m"]),241)
  self.assertEqual([s["site_id"] for s in cities],["VR2","VR1","BR4","BR3"])
if __name__=="__main__":unittest.main()
