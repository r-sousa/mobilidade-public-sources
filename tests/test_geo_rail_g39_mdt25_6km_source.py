"""G39 sample exactly 13 official source-ground reference points, fail closed."""
import unittest,importlib.util,pathlib,sys
try:
 import shapely,pyproj,numpy,rasterio,matplotlib
 OK=True
except ImportError:OK=False
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g39",root/"tools/geo_rail_g39_mdt25_real_6km_zamora_terrain_profile.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G39 source raster stack in dedicated runner")
class G39SourceContinuityTests(unittest.TestCase):
 def sources(self):
  coords=[(-8.67+(-5.746+8.67)*i/99.,41.23+(41.503-41.23)*i/99.) for i in range(100)]
  feats=[]
  for a in (1,2,3):
   for b in (1,2,3):
    for c in (1,2,3):
     feats.append({"properties":{"id":f"P{a}-{b}-{c}"},
                 "geometry":{"type":"LineString","coordinates":coords}})
  g10={"features":feats}
  g36={"source_all_original_G10_count":27,"source_all_original_G30_count":3,
       "review_priority_NOT_viability_OR_final_selection":[
        {"option_id":"P2-2-1","next_engineering_work_priority_only":True}]}
  g38={"Spain_CNIG_IGN_WCS_MDT25_small_source":{
       "real_original_IGN_MDT25_GeoTIFF_acquired_and_QA":True,
       "coverage_id":"Elevacion25830_25"}}
  return g10,g36,g38
 def test_13_eastern_source_points(self):
  points=g.samples(*self.sources())
  self.assertEqual(len(points),13)
  self.assertAlmostEqual(points[0]["distance_from_source_endpoint_km"],-6)
  self.assertEqual(points[-1]["distance_from_source_endpoint_km"],0)
  self.assertTrue(all(-6.2<p["lon"]<-5.3 for p in points))
 def test_never_run_without_exact_native_Pilot(self):
  a,b,c=self.sources()
  c["Spain_CNIG_IGN_WCS_MDT25_small_source"]["real_original_IGN_MDT25_GeoTIFF_acquired_and_QA"]=False
  with self.assertRaisesRegex(ValueError,"previous_genuine_original_raster"):
   g.samples(a,b,c)
 def test_no_omission_original_G10_portfolio(self):
  a,b,c=self.sources();a["features"].pop()
  with self.assertRaisesRegex(ValueError,"original_G10_27"):
   g.samples(a,b,c)
 def test_incomplete_3D_sample_spacing(self):
  self.assertEqual(g.NPTS,13)
  self.assertEqual(g.SAMPLE_M,500.)
  self.assertEqual(g.SOURCE_COVERAGE,"Elevacion25830_25")
if __name__=="__main__":unittest.main()
