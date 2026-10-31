"""G11 small-source checks, no packages in universal lean runner."""
import sys,unittest,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
AVAILABLE=all(importlib.util.find_spec(z) is not None for z in ("numpy","scipy","rasterio","shapely","pyproj"))
if AVAILABLE:
 from geo_rail_g11_urban_service import stop_time_cost_bounds,reachability_label,metric,CITY
@unittest.skipUnless(AVAILABLE,"G11 full source geography tests run only in specialist GIS CI")
class TestG11(unittest.TestCase):
 def test_stop_not_real_train_timetable(self):
  for speed in (160,200,250):
   o=stop_time_cost_bounds(speed)
   self.assertGreater(o["upper_minutes"],o["lower_minutes"])
   self.assertTrue(o["hypothetical_acceleration_braking_dwell_not_scheduled"])
 def test_cities_not_automatically_mandatory(self):
  self.assertEqual(sum(v["mandatory"] for v in CITY.values()),2)
  self.assertTrue(CITY["Vila_Real"]["mandatory"])
  self.assertTrue(CITY["Braganca"]["mandatory"])
  for k in ("Guimaraes","Amarante","Mirandela","Macedo_de_Cavaleiros"):
   self.assertFalse(CITY[k]["mandatory"])
 def test_euclidean_is_not_a_routing_timetable(self):
  self.assertIn("within_3km",reachability_label(2.8))
  self.assertIn("feeder",reachability_label(6.))
  self.assertIn("20km",reachability_label(11.))
  self.assertIn("weak",reachability_label(30.))
if __name__=="__main__":unittest.main()
