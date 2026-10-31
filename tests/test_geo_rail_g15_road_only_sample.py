"""G15 road-only population sampling never treats missing public transport as zero."""
import sys,unittest,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
AV=all(importlib.util.find_spec(x) is not None for x in ("shapely","pyproj"))
if AV:
 from geo_rail_g15_road_only_census_sample import aggregate_access,station_sites
@unittest.skipUnless(AV,"Source GIS contract tested in GitHub Actions")
class G15Tests(unittest.TestCase):
 def test_unknown_population_is_not_unreachable(self):
  s={"original_BRGI_representative_points_in_30km_circle_population":300,
  "sampled_cells":[
   {"INE_2021_census_residents_in_sampled_cell":80,"INE_2021_census_age65_in_sampled_cell":20,"router_2026_network_duration_minutes":12},
   {"INE_2021_census_residents_in_sampled_cell":100,"INE_2021_census_age65_in_sampled_cell":50,"router_2026_network_duration_minutes":27},
   {"INE_2021_census_residents_in_sampled_cell":60,"INE_2021_census_age65_in_sampled_cell":10,"router_2026_network_duration_minutes":None}]}
  d=aggregate_access(s)
  self.assertEqual(d["population_2021_with_a_classified_routing_reference"],180)
  self.assertEqual(d["population_2021_without_a_classified_routing_reference"],120)
  self.assertTrue(d["unclassified_must_not_be_treated_as_unreachable"])
  self.assertEqual(d["conservative_nonstation_sampled_road_coverage_by_time_minutes"]["15"]["qualifying_population_2021_from_road_samplings"],80)
 def test_both_families_populate_same_unique_references(self):
  g={"all_54_city_research_geographic_buffer_census_cases":[]}
  with self.assertRaises(ValueError):station_sites(g)
if __name__=="__main__":unittest.main()
