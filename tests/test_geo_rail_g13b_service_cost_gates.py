"""G13B empty price and demand guards and prioritization tests."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from geo_rail_g13b_service_site_cost_evidence import COST_COMPONENTS,PRIORITIES,site_market_matrix
class TestG13B(unittest.TestCase):
 def test_three_prioritized_without_cost_optimum(self):
  self.assertEqual(set(PRIORITIES),{"P1-2-1","P2-2-1","P2-2-3"})
 def test_cost_components_have_units_and_gates(self):
  self.assertEqual(len(COST_COMPONENTS),10)
  self.assertTrue(all(len(x)==3 and len(x[1]) for x in COST_COMPONENTS))
 def test_missing_g13_source_screens_fail(self):
  with self.assertRaises(ValueError):site_market_matrix({"non_dominated_reference_site_screens_per_market":[]})
if __name__=="__main__":unittest.main()
