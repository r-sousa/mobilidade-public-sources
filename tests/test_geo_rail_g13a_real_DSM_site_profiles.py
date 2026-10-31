"""G13A station-proxy sensitivity unit tests; no real station certification."""
import unittest,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
DEPS=all(importlib.util.find_spec(p) is not None for p in ("rasterio","scipy","numpy","pyproj","shapely"))
if DEPS:
 from geo_rail_g13a_real_DSM_site_profiles import non_dominated,ANCHORS,PROFILE_HALFLENGTH_M
class G13Tests(unittest.TestCase):
 @unittest.skipUnless(DEPS,"Specialist GIS CI dependency")
 def test_not_a_station_and_no_financial_conclusion(self):
  self.assertEqual(len(ANCHORS),3)
  self.assertEqual(PROFILE_HALFLENGTH_M,500.)
 @unittest.skipUnless(DEPS,"Specialist GIS CI dependency")
 def test_road_and_vertical_proxy_pareto(self):
  def site(time,p90,lat):
   return {"terrain":{"status":"source_30m_DSM_screened",
    "grade_sensitivity_profile":{"25":{"L1_p90_vertical_DSM_residual_m":p90}},
    "lateral_plusminus_125m_p90_absolute_surface_difference_m":lat},
    "road_routing_valid_to_a_road_near_study_point":True,
    "road_network_drive_minutes_to_research_road_snap":time}
  a,b,c=site(8,12,3),site(10,10,4),site(12,13,5)
  self.assertEqual(non_dominated([a,b,c]),[a,b])
if __name__=="__main__":unittest.main()
