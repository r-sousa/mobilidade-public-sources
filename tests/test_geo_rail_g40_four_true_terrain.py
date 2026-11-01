"""G40 30-option route source governance and four genuine Spanish potential profiles."""
import unittest,sys,pathlib,importlib.util,json
try:
 import numpy,shapely,pyproj,rasterio,matplotlib
 GIS=True
except ImportError:GIS=False
if GIS:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g40",root/"tools/geo_rail_g40_all30_reference_four_true_IGN_terrain.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(GIS,"G40 geo tests require dedicated runner")
class G40Tests(unittest.TestCase):
 def sources(self):
  # Fake long but monotonically eastwards source line only for tests
  coords=[[-8.55+2.8*i/100,41.22+.28*i/100] for i in range(101)]
  g10={"features":[{"properties":{"id":f"P{a}-{b}-{c}"},
          "geometry":{"type":"LineString","coordinates":coords}} for a in range(1,4)
          for b in range(1,4) for c in range(1,4)]}
  g30={"features":[{"properties":{"id":key},
          "geometry":{"type":"LineString","coordinates":coords}}
       for key in g.FOUR if key.startswith("G30-")]}
  g36={"source_all_original_G10_count":27,"source_all_original_G30_count":3,"rows_n":90}
  g39={"validated_original_WCS_MDT25_source_points":13,
       "requested_source_points":13,"original_WCS_failed_points_not_imputed":0,
       "PT_ES_vertical_reference_harmonization_NOT_PROVEN":True}
  return g10,g30,g36,g39
 def test_source_portfolio_exact_30(self):
  self.assertEqual(len(g.validate(*self.sources())),30)
  self.assertEqual(len(g.FOUR),4)
  self.assertEqual(g.DISTANCES_KM,(15,20,25,30,35,40,45,50,55))
 def test_portfolio_loss_fail_closed(self):
  a,b,c,d=self.sources();a["features"].pop()
  with self.assertRaisesRegex(ValueError,"30_original"):
   g.validate(a,b,c,d)
 def test_only_genuine_IGN25_with_proven_G39(self):
  a,b,c,d=self.sources();d["validated_original_WCS_MDT25_source_points"]=12
  with self.assertRaisesRegex(ValueError,"G39_original"):
   g.validate(a,b,c,d)
 def test_synthetic_4x9_source_points_and_spatial_spread(self):
  from shapely.geometry import mapping,box
  a,b,c,d=self.sources()
  zones={"type":"FeatureCollection","features":[
   {"type":"Feature","properties":{"CNTR_ID":code},
    "geometry":mapping(box(*bounds))} for code,bounds in
     (("PT",(-10,36,-6.8,44)),("ES",(-6.8,36,-5.0,44)))]}
  out,spread,meta=g.points(a,b,c,d,json.dumps(zones).encode())
  self.assertEqual(len(out),36)
  self.assertEqual(len(spread),9)
  self.assertTrue(all(v["no_rail_3D_earthworks_or_operational_grade"] for v in out))
 def test_source_WCS_only_correct_coverage(self):
  self.assertEqual(g.COVERAGE,"Elevacion25830_25")
  self.assertLessEqual(g.MAX_RAW_REQUESTS,36)
  self.assertEqual(g.MIN_ES_BORDER_DISTANCE_M,1500)
if __name__=="__main__":unittest.main()
