"""G20 native DGT grid and road/terrain/2021 Pareto source guards."""
import sys,unittest,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(x) is not None for x in ("shapely","pyproj"))
if HAVE:
 from geo_rail_g20_targeted_DGT_original_station_grid import cells,choose,MAX_TILES
@unittest.skipUnless(HAVE,"specialist G20 GIS tests (not lean public global CI)")
class G20Source(unittest.TestCase):
 def test_original_tile_center_and_neighbors(self):
  q=cells((35500,184500))
  self.assertEqual(len(q),9)
  self.assertIn((235,485),q)
  self.assertIn((234,484),q)
 def test_unknown_urban_market_fail(self):
  with self.assertRaises(ValueError):choose([],"Vila_Real")
 def test_strict_budget(self):
  self.assertLessEqual(MAX_TILES,54)
if __name__=="__main__":unittest.main()
