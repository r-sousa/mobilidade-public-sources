"""G36 conservation of all 30 and transparent source-only normalized sensitivity."""
import importlib.util,pathlib,unittest
try:
 import numpy,matplotlib
 GIS=True
except ImportError:GIS=False
if GIS:
 p=pathlib.Path(__file__).resolve().parents[1]
 spec=importlib.util.spec_from_file_location("g36",p/"tools/geo_rail_g36_all30_robust_source_only_selection.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(GIS,"G36 GIS graphics dependencies on dedicated runner")
class G36All30(unittest.TestCase):
 def test_3_speeds_3_explicit_profile_weights(self):
  self.assertEqual(g.SCENARIOS,(160,200,250))
  self.assertEqual(len(g.PROFILES),3)
  self.assertTrue(all(abs(sum(w.values())-1)<1e-9 for w in g.PROFILES.values()))
 def test_missing_not_imputed_as_zero(self):
  cases=[{"option_id":"A","research_length_km":100.},
         {"option_id":"B","research_length_km":None},
         {"option_id":"C","research_length_km":200.}]
  n=g.norm(cases,"research_length_km")
  self.assertEqual(n["A"],0.)
  self.assertIsNone(n["B"])
  self.assertEqual(n["C"],1.)
 def test_pareto_min_and_max(self):
  mini=[]
  for name,a,b,c in (("A",100,1,200),("B",200,2,100),("C",150,1,200)):
   mini.append({"option_id":name,"research_length_km":a,
     "surface_Natura2000_km":b,"DSM_proxy_mean_abs_m":1.,
     "optional_road_to_grid_minutes_mean":1.,
     "geographic_union_2021_residents":c})
  self.assertEqual(g.dominance(mini),["A"])
 def test_source_only_conservation_90(self):
  a=[]
  for speed in g.SCENARIOS:
   for i in range(30):
    a.append({"option_id":f"P{i}","speed_kmh":speed,
      "research_length_km":100+i,
      "surface_Natura2000_km":i/2,
      "DSM_proxy_mean_abs_m":float(i),
      "optional_road_to_grid_minutes_mean":float(30-i),
      "geographic_union_2021_residents":340000+i*200})
  _,freq=g.score_rows(a)
  self.assertEqual(len(a),90)
  self.assertEqual(len(freq),30)
  self.assertTrue(all(x["must_still_remain_in_full30_portfolio"] for x in freq))
if __name__=="__main__":unittest.main()
