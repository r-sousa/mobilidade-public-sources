"""G47 native DGT 2m real source release asset and registry audit tests."""
import unittest,sys,pathlib,importlib.util
try:import numpy,rasterio,shapely,matplotlib,scipy,pyproj
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g47",root/"tools/geo_rail_g47_original_DGT2m_station_3km_ground.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G47 full native GIS stack required")
class NativeDGTSourceAndExistingInfrastructure(unittest.TestCase):
 def test_actual_original_DGT2m_index_filename(self):
  a=g.ASSET_RE.fullmatch("MDT-2m-228481-07-2024.tif")
  self.assertEqual((int(a.group(1)),int(a.group(2))),(228,481))
  self.assertIsNone(g.ASSET_RE.fullmatch("MDT-2m-999999-07-2024.tif?query=secret"))
 def test_public_release_only_and_tile_specific_asset(self):
  releases=[{"tag_name":"mn-geo-rail-001-g21-native-DGT2m-39-mandatory-site-original-41256814847",
     "assets":[{"name":"MDT-2m-228481-07-2024.tif","id":123,"size":10000}]}]
  chosen=g.asset_map(releases,{(228,481)})
  self.assertEqual(chosen[(228,481)]["source_GitHub_release_asset_id"],123)
  self.assertEqual(chosen[(228,481)]["filename"],"MDT-2m-228481-07-2024.tif")
 def test_fail_closed_missing_no_private_fallback(self):
  with self.assertRaisesRegex(ValueError,"public_DGT_raster_missing"):
   g.asset_map([],{(228,481)})
 def test_four_pilot_stations_require_eighteen_covered_native_tiles(self):
  g45={"all_G10_27_and_G30_3_retained":True,"source_30_options":30}
  g46={"full30_options_still_studied":True,"old_verified_DGT_original_1km_tile_manifest":84,
   "pilot_four_prior_station_site_ids_for_data_coverage_ONLY_not_site_ranking":
      ["VR2","VR1","BR4","BR3"],
   "four_pilot_station_combined_G45_source_2D_terrain_footprint_gaps":{
     "local_1p5km":{"required_1km_DGT2m_tiles":18,
       "already_preserved_original_tiles":18,"missing_tile_count":0}}}
  self.assertEqual(len(g.validate(g45,g46)),4)
  g46["four_pilot_station_combined_G45_source_2D_terrain_footprint_gaps"]["local_1p5km"]["missing_tile_count"]=1
  with self.assertRaisesRegex(ValueError,"18_of_18"):g.validate(g45,g46)
 def test_sample_interval_and_caveat(self):
  self.assertEqual(g.STEP,25.)
  self.assertEqual(g.HALF,1500.)
  self.assertEqual(g.BAND,200.)
if __name__=="__main__":unittest.main()
