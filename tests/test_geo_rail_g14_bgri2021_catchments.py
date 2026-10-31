"""G14 portable GPKG geometry and population aggregation guard tests."""
import sys,unittest,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
DEPS=all(importlib.util.find_spec(x) is not None for x in ("shapely","pyproj"))
if DEPS:
 from shapely.geometry import Polygon
 from shapely import wkb
 from geo_rail_g14_bgri2021_station_population import parse_gpkg_geometry,nonnegative_population
@unittest.skipUnless(DEPS,"G14 full geometry tests execute in dedicated GIS job")
class G14Original(unittest.TestCase):
 def test_wkb_gpkg_geom_with_no_envelope(self):
  poly=Polygon([(0,0),(1,0),(1,1),(0,1)])
  raw=b"GP"+bytes([0,1])+int(3763).to_bytes(4,"little")+wkb.dumps(poly)
  self.assertAlmostEqual(parse_gpkg_geometry(raw).area,1)
 def test_population_must_not_be_imputed(self):
  self.assertEqual(nonnegative_population(125),125)
  self.assertIsNone(nonnegative_population(None))
  self.assertIsNone(nonnegative_population("-"))
  self.assertIsNone(nonnegative_population(-9))
if __name__=="__main__":unittest.main()
