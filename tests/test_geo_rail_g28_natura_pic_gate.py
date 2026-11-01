import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from shapely.geometry import LineString,Polygon
from geo_rail_g28_natura_pic_constraint_gate import hit,SITES
class TestG28(unittest.TestCase):
 def test_unknown_never_free(self):
  self.assertEqual(hit(LineString([(0,0),(10,0)]),([],
    {"status":"UNKNOWN_SOURCE"}))["status"],"UNKNOWN_SOURCE")
 def test_crossing_is_major_risk(self):
  q=hit(LineString([(0,0),(10,0)]),([(Polygon([(2,-1),(4,-1),(4,1),(2,1)]),{"site_name":"X"})],
      {"status":"VERIFIED"}),0)
  self.assertEqual(q["status"],"AVOIDANCE_PRIORITY")
  self.assertEqual(q["line_overlap_km"],0.002)
 def test_no_polygons_does_not_clear(self):
  self.assertIn("NOT_LEGAL_CLEARANCE",hit(LineString([(0,0),(1,1)]),
      ([],{"status":"VERIFIED"}))["status"])
 def test_mandatory_sites(self):
  self.assertEqual((len(SITES),[x[0] for x in SITES].count("Vila Real"),
                    [x[0] for x in SITES].count("Bragança")),(7,3,4))
if __name__=="__main__":unittest.main()
