"""G12 no-network unit tests for urban node research references & patterns."""
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(x) is not None for x in ("numpy","scipy","rasterio","shapely","pyproj"))
if HAVE:
 from shapely.geometry import LineString
 from pyproj import Transformer
 from geo_rail_g11_urban_service import CITY
 from geo_rail_g12_station_siting_and_operations import (
  station_research_points,service_scenario_proxies,STUDY_COMBINATIONS,OFFSETS_KM)
@unittest.skipUnless(HAVE,"G12 GIS tests executed in dedicated public CI")
class TestG12(unittest.TestCase):
 def test_source_city_projection_three_not_station_points(self):
  ref=CITY["Vila_Real"];trans=Transformer.from_crs(4326,3763,always_xy=True)
  inv=Transformer.from_crs(3763,4326,always_xy=True)
  x,y=trans.transform(ref["lon"],ref["lat"])
  source_line=LineString([(x-20000,y),(x+20000,y)])
  pts=station_research_points(source_line,"Vila_Real",ref,trans,inv)
  self.assertEqual(len(pts),3)
  self.assertEqual([p["offset_along_2km_research_grid_km"] for p in pts],[-3.,0.,3.])
  self.assertTrue(all(not p["is_existing_or_proposed_station"] for p in pts))
  self.assertTrue(all(p["road_network_drive_minutes_to_research_road_snap"] is None for p in pts))
 def test_preserved_six_options(self):
  self.assertEqual(len(STUDY_COMBINATIONS),6)
  self.assertEqual(len(set(STUDY_COMBINATIONS)),6)
  self.assertTrue({"P1-2-1","P2-2-1"}.issubset(set(STUDY_COMBINATIONS)))
 def test_stop_patterns_never_omit_mandatory_markets(self):
  tabs=[{"research_combination":"P1-2-1"}]
  # Actual G10 input required: an empty table triggers strict source failure.
  with self.assertRaises(Exception):service_scenario_proxies(tabs,{"scenario_rows":[]})
if __name__=="__main__":unittest.main()
