"""G26A no fictional source COS, city and release dedup tests."""
import unittest,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(n) is not None for n in ("shapely","pyproj"))
if HAVE:
 from geo_rail_g26a_cos2025_original_local_landuse import site_points,ENDPOINT,RADIUS,PAGES
@unittest.skipUnless(HAVE,"G26A specialist COS source geometry preflight")
class COS2025(unittest.TestCase):
 def test_bounded_small_COS_queries_only(self):
  self.assertIn("cos2025v1/items",ENDPOINT)
  self.assertEqual(RADIUS,400)
  self.assertLessEqual(PAGES,10)
 def test_exact_G25_seven_deduplicated_research_coordinates(self):
  a=[]
  for i in range(3):
   a.append({"original_study_EPSG3763_XY":[30000+i*10,180000],"mandatory_market":"Vila_Real","source_corridor_family":"P1-2-1","source_G24_reference_seed":"Vila_Real-reference-1"})
  for i in range(4):
   a.append({"original_study_EPSG3763_XY":[110000+i*10,235000],"mandatory_market":"Braganca","source_corridor_family":"P2-2-3","source_G24_reference_seed":"Braganca-reference-3"})
  a.extend(a)
  x={"two_compulsory_cities":["Vila Real","Bragança"],"Fxx_accepted":False,"Site_authorized":False,"source_shortlisted_road_reference_route_cases":a}
  self.assertEqual(len(site_points(x)),7)
  x["source_shortlisted_road_reference_route_cases"]=[a[0]]*8
  with self.assertRaises(ValueError):site_points(x)
if __name__=="__main__":unittest.main()
