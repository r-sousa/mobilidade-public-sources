"""A two mandatory city source join must reject unsourced and invented raster pixels."""
import unittest,importlib.util,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/"tools"))
sp=importlib.util.spec_from_file_location("b1joined",R/"tools"/"geo_rail_pt_b1_joined_preacquisition.py")
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class B1Join(unittest.TestCase):
    def test_exact_source_SHA_and_producer_contract(self):
        self.assertEqual(m.ROAD_SHA256,"e54cbbd0786c4eac5024dd0d9652b16b51abfebb4326ebe0ed9882c4a829d215")
        self.assertEqual(set(m.SITES),{"Vila Real","Bragança"})
        self.assertIn("Sanabria",m.__doc__)
if __name__=="__main__":unittest.main()
