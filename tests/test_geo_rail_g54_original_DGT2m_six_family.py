"""G54 six geographical families native pixel grade source checks."""
import importlib.util,sys,pathlib,unittest
try:
 import scipy,numpy,rasterio,shapely,matplotlib
 OK=True
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g54",root/"tools/geo_rail_g54_six_source_families_native_DGT2m_pixels.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G54 native raster stack")
class OriginalNewFamilyGround(unittest.TestCase):
 def test_four_original_sites_and_real_station_local_scope(self):
  self.assertEqual(g.SITES,("VR2","VR1","BR4","BR3"))
  self.assertEqual(g.STEP,25.)
  self.assertEqual(g.HALF,1500.)
  self.assertEqual(g.GRADE,(12.5,15.))
 def test_six_by_four_mock_source_families_never_assume_p2_geometry(self):
  g52={"source_original_all30_preserved":True,"source_27_G10_3_G30_count":30,
      "G52_six_representative_original_source_routes_for_NEXT_ground_3D":[f"R{i}" for i in range(6)]}
  oldsites=[{"candidate_site_id":x,"mandatory_city":"Vila_Real" if x.startswith("VR") else "Braganca",
      "previous_source_original_XY_EPSG3763":[1000,2000]} for x in g.SITES]
  rec=[{"option_id":f"R{i}","historical_site_id":s,"illustrative_speed_label_kmh":200,
      "C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found":False,
      "best_research_horizontal_solution":None}
      for i in range(6) for s in g.SITES]
  # G45 contains 630 original comparisons. Other entries must be UNIQUE.
  for i in range(606):
   rec.append({"option_id":f"OTHER{i}","historical_site_id":"EXTRA",
      "illustrative_speed_label_kmh":160,"C2_planar_quintic_800m_station_straight_centerline_at_sampled_points_found":False,
      "best_research_horizontal_solution":None})
  g45={"all_G10_27_and_G30_3_retained":True,
      "all_630_route_site_speed_horizontal_screen_cases":rec,
      "site_source_original_road_COS_DGT2m_from_G44":oldsites}
  g37={"source_84_original_DGT_tile_ids_in_PTTM06":[[i,401] for i in range(84)]}
  cases,tiles,existing=g.original_case_index(g52,g45,g37)
  self.assertEqual(len(cases),24)
  self.assertEqual(len(tiles),0)
  self.assertTrue(all(q["status"].startswith("NO_G45") for q in cases))
 def test_exact_source_original_asset_matching_requires_catalog(self):
  with self.assertRaisesRegex(ValueError,"public_DGT_raster_missing"):
   g.asset_map([], {(228,481)})
 def test_original_no_imputation_mathematical_slope_requires_valid_series(self):
  import numpy as np
  x=np.arange(121,dtype=float)*25-1500
  y=np.array([500+0.02*z for z in x])
  a=g.minimax_grade_envelope(x,y,12.5,station_max_permille=10.,vertical_radius_m=20000.)
  self.assertEqual(a["status"],"OPTIMISTIC_LP_MATHEMATICAL_GRADE_ENVELOPE_NOT_PROJECT")
  y[20]=np.nan
  with self.assertRaisesRegex(ValueError,"no_missing"):
   g.minimax_grade_envelope(x,y,12.5,station_max_permille=10.,vertical_radius_m=20000.)
if __name__=="__main__":unittest.main()
