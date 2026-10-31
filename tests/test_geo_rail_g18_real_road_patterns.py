"""G18 mandatory two-city train-pattern contract. GIS imports are specialist CI only."""
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(n) is not None for n in ("shapely","pyproj"))
if HAVE:
 from geo_rail_g18_rail_stop_pattern_road_2021 import SCENARIOS,FAMILIES,MINUTES,REQUIRED
@unittest.skipUnless(HAVE,"G18 spatial tests run on specialist source GIS CI, not lean global pipeline")
class G18(unittest.TestCase):
 def test_study_four_patterns(self):
  self.assertEqual(len(SCENARIOS),4)
  self.assertEqual(len(FAMILIES),3)
  self.assertEqual(MINUTES,(15,30,45))
  self.assertTrue(all(REQUIRED.issubset(set(s)) for s in SCENARIOS.values()))
  self.assertEqual(len(SCENARIOS["EXP_VR_BR_only"]),2)
  self.assertEqual(len(SCENARIOS["REG_all_six"]),6)
 def test_no_public_transit_claims(self):
  self.assertNotIn("PT",tuple(SCENARIOS))
if __name__=="__main__":unittest.main()
