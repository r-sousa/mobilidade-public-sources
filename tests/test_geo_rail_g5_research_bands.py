"""Deterministic G5 audit against invented routes/unsupported engineering."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from geo_rail_g5_independent_research_bands import (
  snap,anchor,cost,shortest,alternatives,spatial_metrics,length_km,CELL,
  reference_2km_ground
)
class TestG5SourceGridMethods(unittest.TestCase):
 def test_graph_route_never_skips_missing_cells(self):
  nodes={(i*CELL,j*CELL):{"surface_median_m":10,"surface_relief_p95_minus_p05_m":10}
         for i in range(20) for j in range(-6,7)}
  start=(0,0);end=(18*CELL,0)
  for j in range(-1,2):
   nodes.pop((8*CELL,j*CELL))
  p=shortest(nodes,start,end)
  self.assertIsNotNone(p)
  self.assertNotIn((8*CELL,0),p)
  for a,b in zip(p,p[1:]):
   self.assertTrue(abs(a[0]-b[0])<=CELL and abs(a[1]-b[1])<=CELL)
 def test_distinctness_not_just_objective_label(self):
  nodes={(i*CELL,j*CELL):{"surface_median_m":50,"surface_relief_p95_minus_p05_m":20}
         for i in range(27) for j in range(-10,11)}
  pairs,status=alternatives(nodes,(0,0),(26*CELL,0))
  self.assertTrue(pairs)
  self.assertGreaterEqual(len(pairs),2)
  for route,meta in pairs[1:]:
   self.assertLessEqual(meta["spatial_metrics"]["max_jaccard"],.68)
   self.assertGreaterEqual(meta["spatial_metrics"]["min_mid_cells_far_4km_fraction"],.19)
   self.assertTrue(all(a!=b for a,b in zip(route,route[1:])))
 def test_invalid_cost_rejected(self):
  nodes={(0,0):{"surface_median_m":1,"surface_relief_p95_minus_p05_m":1},
         (CELL,0):{"surface_median_m":1,"surface_relief_p95_minus_p05_m":1}}
  with self.assertRaises(ValueError):cost(nodes,(0,0),(2*CELL,0),"balanced",0,())
  with self.assertRaises(ValueError):cost(nodes,(0,0),(CELL,0),"railway_engineering",0,())
if __name__=="__main__":unittest.main()
