"""G51 robust all30 original research weights and five gradient source score tests."""
import importlib.util,sys,pathlib,unittest
try:import numpy,matplotlib
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g51",root/"tools/geo_rail_g51_all30_mixed_grade_technical_priority_reassessment.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"Need numpy original source decision stack")
class G51All30SourceOnly(unittest.TestCase):
 def test_preserve_30_and_source_functional_gradient_distinction(self):
  self.assertEqual(g.NOMINAL_GRADES_PERMILLE,(12.5,15.,18.,20.,25.))
  self.assertEqual(g.PRIMARY,(12.5,15.))
  self.assertEqual(g.DEEP,"G30-potential_deep_tunnel")
  self.assertEqual(g.SCENARIOS,(160,200,250))
 def test_original_full_five_MCA_metrics_with_population_not_demand(self):
  self.assertEqual(set(g.METRIC_NAMES),{
   "research_length_km","surface_Natura2000_km","DSM_proxy_mean_abs_m",
   "optional_road_to_grid_minutes_mean","geographic_union_2021_residents"})
 def test_original_weight_profiles_not_redefined(self):
  self.assertEqual(len(g.PROFILES),4)
  for w in g.PROFILES.values():
   self.assertAlmostEqual(sum(w.values()),1.,places=8)
   self.assertEqual(set(w),set(g.METRIC_NAMES))
 def test_original_25_historical_grade_policy_passenger_not_freight(self):
  self.assertNotEqual(g.classify(25)["traffic"],g.classify(12.5)["traffic"])
  self.assertEqual(g.classify(15)["screen"],"primary_normal")
 def test_workflow_60_methodological_scoring_sensitivities(self):
  self.assertEqual(len(g.NOMINAL_GRADES_PERMILLE)*len(g.SCENARIOS)*len(g.PROFILES),60)
if __name__=="__main__":unittest.main()
