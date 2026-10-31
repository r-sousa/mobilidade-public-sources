"""G16 Pareto guard and scope; no site or PT services invented."""
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
OK=all(importlib.util.find_spec(x) is not None for x in ("shapely","pyproj"))
if OK:
 from geo_rail_g16_station_research_pareto import pareto,FAMILIES
@unittest.skipUnless(OK,"Native BGRI tests in geospatial GitHub CI")
class G16Tests(unittest.TestCase):
 def test_original_three_family_choice(self):
  self.assertEqual(FAMILIES,("P1-2-1","P2-2-1","P2-2-3"))
 def test_pareto_no_weights_and_no_rail_station_certification(self):
  def p(pop,road,relief,cross):
   return {"original_2021_residents_within_5km_geographic_buffer":pop,
   "OSRM_2026_urban_market_to_research_road_reference_min":road,
   "DSM_25permille_1km_vertical_P90_surface_residual_m":relief,
   "DSM_plusminus125m_lateral_P90_surface_difference_m":cross}
  a,b,c=p(1000,10,20,15),p(1500,9,10,5),p(1700,13,20,4)
  self.assertEqual(pareto([a,b,c]),[b,c])
if __name__=="__main__":unittest.main()
