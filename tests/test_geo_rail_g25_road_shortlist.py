"""G25 road snap shortlist source safety and dedup without network requests."""
import unittest,importlib.util,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
READY=all(importlib.util.find_spec(x) is not None for x in ("shapely","numpy","pyproj","rasterio","scipy"))
if READY:
 from geo_rail_g25_OSRM_original_G24_road_shortlist import samples,MAX_CITY_DESTINATIONS,MARKETS,OSRM_PUBLIC_REQUEST_BUDGET
@unittest.skipUnless(READY,"G25 specialist source GIS/public OSRM tests; global lean CI skips")
class G25(unittest.TestCase):
 def test_only_two_public_demo_table_queries(self):
  self.assertEqual(OSRM_PUBLIC_REQUEST_BUDGET,2)
  self.assertEqual(MARKETS,("Vila_Real","Braganca"))
  self.assertLessEqual(MAX_CITY_DESTINATIONS,32)
 def test_deduplicate_different_family_same_real_site(self):
  rows=[{"mandatory_market":"Vila_Real","candidate_original_DGT_study_EPSG3763_XY":[30000,180000]},
        {"mandatory_market":"Vila_Real","candidate_original_DGT_study_EPSG3763_XY":[30000,180000]},
        {"mandatory_market":"Braganca","candidate_original_DGT_study_EPSG3763_XY":[115000,239000]}]
  vals=rows+[{"mandatory_market":"Braganca","candidate_original_DGT_study_EPSG3763_XY":[115000,239000]} for _ in range(10)]
  j={"13_groups_2to3_source_ground_vs_grid_geometry_reference_shortlist":vals,
    "351_original_source_geometry_station_tangent_screening_cases":[None]*351,
    "Fxx_accepted":False,"Site_authorized":False}
  _,group=samples(j)
  self.assertEqual(len(group["Vila_Real"]),1)
  self.assertEqual(len(group["Braganca"]),1)
 def test_nonmandatory_city_forbidden(self):
  rows=[{"mandatory_market":"Guimaraes","candidate_original_DGT_study_EPSG3763_XY":[1,2]} for _ in range(13)]
  j={"13_groups_2to3_source_ground_vs_grid_geometry_reference_shortlist":rows,
    "351_original_source_geometry_station_tangent_screening_cases":[None]*351,
    "Fxx_accepted":False,"Site_authorized":False}
  with self.assertRaises(ValueError):samples(j)
if __name__=="__main__":unittest.main()
