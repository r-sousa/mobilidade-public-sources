"""G23A Pareto nonmonetary strict objective regression."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from geo_rail_g23a_native_ground_station_pareto import pareto
class TestG23A(unittest.TestCase):
 def test_pareto_nondominated_all_independent_dimensions(self):
  cases=[{"x":1,"y":6},{"x":2,"y":3},{"x":4,"y":4},{"x":2,"y":7}]
  p=pareto(cases,("x","y"))
  self.assertEqual([cases.index(z) for z in p],[0,1])
 def test_missing_cost_data_never_counted_as_zero(self):
  cases=[{"x":1,"y":3},{"x":None,"y":0},{"x":2,"y":3}]
  self.assertEqual(pareto(cases,("x","y")),[cases[0]])
if __name__=="__main__":unittest.main()
