"""G10 synthetic portfolio and Pareto tests. Requires no GIS dependencies in lean CI."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
try:
 from geo_rail_g10_27_macro_portfolio import nondominated, research_grid_length_km
 HAVE=True
except ImportError as e:
 HAVE=False
@unittest.skipUnless(HAVE,"full G10 GIS tests executed in dedicated geospatial workflow")
class TestG10(unittest.TestCase):
 def test_distance_diagonal(self):
  self.assertEqual(research_grid_length_km([(0,0),(2000,0),(4000,2000)]),4.828)
 def test_pareto_technical_proxy_is_not_cost(self):
  a={"combination_id":"A","horizontal_radius_research_screen_pass":True,
    "smoothed_research_grid_length_km_not_rail_track":280.0,
    "passenger25_DSM_p90_m":100.,"passenger25_DSM_fraction_gt25m":.35}
  b={"combination_id":"B","horizontal_radius_research_screen_pass":True,
    "smoothed_research_grid_length_km_not_rail_track":300.0,
    "passenger25_DSM_p90_m":70.,"passenger25_DSM_fraction_gt25m":.25}
  c={"combination_id":"C","horizontal_radius_research_screen_pass":True,
    "smoothed_research_grid_length_km_not_rail_track":350.0,
    "passenger25_DSM_p90_m":120.,"passenger25_DSM_fraction_gt25m":.45}
  self.assertEqual(nondominated([a,b,c],"passenger25"),["A","B"])
if __name__=="__main__":unittest.main()
