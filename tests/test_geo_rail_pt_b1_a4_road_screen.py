"""Offline mandatory-node road network acquisition scope, no Sanabria."""
import sys,importlib.util,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sp=importlib.util.spec_from_file_location("geo_b1",ROOT/"tools"/"geo_rail_pt_b1_a4_road_screen.py")
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class B1(unittest.TestCase):
    def test_bounded_compulsory_service_city_locations(self):
        self.assertEqual(set(m.CITY),{"Vila_Real","Braganca"})
        self.assertEqual(len(m.SOURCE_ORIGINS),2)
        for city in m.CITY:
            self.assertIn('out tags geom',m._overpass_query(city))
            self.assertNotIn("Sanabria",m._overpass_query(city))
        self.assertEqual(m.DSM_SHA256,"a708b502b2eb86236c70f2d74322e9d8e2ea1417eb24094d0e43536845407bd9")
        self.assertIn("motorway",m.ROAD_CLASSES)
        self.assertIn("secondary",m.ROAD_CLASSES)
    def test_no_track_or_station_claim(self):
        self.assertIn("NOT establish station accessibility",m.__doc__)
        self.assertIn("NO Sanabria",m.__doc__)
if __name__=="__main__":unittest.main()
