"""G57 real original DGT2m 2 BR station recovered 200 curvature research source."""
import unittest,importlib.util,pathlib,sys
try:import numpy,scipy,rasterio,shapely,matplotlib
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g57",root/"tools/geo_rail_g57_new_BR3_BR4_G56_real_original_DGT2m.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G57 native DGT2m original raster stack")
class G57SourceStrict(unittest.TestCase):
 def test_only_two_true_Braganca_old_physical_station_sites(self):
  self.assertEqual(g.SITES,("BR3","BR4"))
  self.assertEqual(g.REPO,"r-sousa/mobilidade-public-sources")
 def test_G56_new_profiles_121_per_site_strict_gate(self):
  import numpy as np
  g56={"original_full30_research_study_alternatives_preserved":True,
       "old_G45_original_BR3_BR4_200_no_sampled_radius_solution":True,
       "no_new_original_DGT2m_source_ground_samples_for_changed_XY":True,
       "two_sites_three_speeds_source_2D_curvature_screen":[]}
  for site in g.SITES:
   g56["two_sites_three_speeds_source_2D_curvature_screen"].append({
     "station_id":site,"per_speed":{"200":{
       "horizontal_2D_curvature_sampled_candidate_found":False,
       "G56_best_source_research_geometry_or_null":None}}})
  g37={"source_84_original_DGT_tile_ids_in_PTTM06":[[i+200,401] for i in range(84)]}
  cases,need,old=g.prepare(g56,g37)
  self.assertEqual(len(cases),2)
  self.assertTrue(all(c["status"]=="G56_EXTENDED_GEOMETRY_NOT_FOUND" for c in cases))
  self.assertEqual(len(need),0)
 def test_fail_if_source_provenance_changes_or_not_prior_br_solutions(self):
  g56={"original_full30_research_study_alternatives_preserved":False,
       "old_G45_original_BR3_BR4_200_no_sampled_radius_solution":True}
  with self.assertRaisesRegex(ValueError,"full30_old200_fail"):g.prepare(g56,{})
 def test_optimistic_grade_still_strictly_12p5_and15(self):
  import numpy as np
  x=np.arange(121)*25.-1500.
  ground=np.sin(x/200)*30+650
  r=g.minimax_grade_envelope(x,ground,12.5,station_max_permille=10,vertical_radius_m=20000)
  self.assertTrue(r["minimum_maximum_vertical_ground_separation_m"]>0)
  ground[30]=np.nan
  with self.assertRaisesRegex(ValueError,"no_missing"):
   g.minimax_grade_envelope(x,ground,12.5,station_max_permille=10,vertical_radius_m=20000)
if __name__=="__main__":unittest.main()
