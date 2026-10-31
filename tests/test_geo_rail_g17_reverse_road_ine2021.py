"""G17 reliable reverse road isochrone contract checks; no census imputation."""
import unittest,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(k) for k in ("shapely","pyproj"))
if HAVE:
 from shapely.geometry import Point,mapping
 from pyproj import Transformer
 from geo_rail_g17_valhalla_reverse_road_ine_census import validate_road_contours,sites,TIME_MINUTES
@unittest.skipUnless(HAVE,"G17 specialist original INE spatial test job")
class G17(unittest.TestCase):
 def test_3_actual_nested_contours(self):
  t=Transformer.from_crs(4326,3763,always_xy=True)
  features=[{"type":"Feature","properties":{"metric":"time","contour":minute},
     "geometry":mapping(Point(-7.744,41.3006).buffer(.001*(minute/15)))} for minute in (45,30,15)]
  # above geometries are nested by minute
  d,r=validate_road_contours({"type":"FeatureCollection","features":features},(-7.744,41.3006),t)
  self.assertEqual(sorted(d),[15,30,45])
  self.assertGreater(d[45].area,d[30].area)
 def test_missing_contour_fails_closed(self):
  with self.assertRaises(ValueError):
   validate_road_contours({"type":"FeatureCollection","features":[]},(-7.744,41.3006),
    Transformer.from_crs(4326,3763,always_xy=True))
 def test_only_verified_15_30_45(self):
  self.assertEqual(TIME_MINUTES,(15,30,45))
if __name__=="__main__":unittest.main()
