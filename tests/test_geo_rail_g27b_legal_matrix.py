"""G27B research landuse, road, terrain matrix must keep legal unknown."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from geo_rail_g27b_seven_COS2025_access_terrain_legal_matrix import LEGAL
class TestG27B(unittest.TestCase):
 def test_legal_unknown_default(self):
  self.assertIn("REN",LEGAL);self.assertIn("RAN",LEGAL)
  self.assertIn("PDM_in_force_and_regulation",LEGAL)
  self.assertIn("public_water_domain",LEGAL)
  self.assertIn("land_ownership",LEGAL)
if __name__=="__main__":unittest.main()
