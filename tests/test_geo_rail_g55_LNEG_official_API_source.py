"""G55 LNEG official source-only bounded API and 25km west Vila Real gate."""
import unittest,importlib.util,pathlib,sys
try:import numpy,requests,pyproj,shapely,matplotlib
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g55",root/"tools/geo_rail_g55_original_LNEG_Marao_west_VR_OGC_geology.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"GIS source runner required")
class G55OfficialGeology(unittest.TestCase):
 def test_exact_known_official_geoportal_collection_ids(self):
  self.assertEqual(set(g.COLLECTIONS),{
   "cgp50k-prt-lneg-en-50k-lithology",
   "cgp200k-prt-lneg-en-200k-lithology",
   "cgp1m-ge-geologicfault",
   "sondabase-sondagem",
   "recursoshidro-pontos-de-gua"})
 def test_bounded_west_VR_not_fake_Marao_boundary(self):
  self.assertEqual(g.LEG_KM,25)
  self.assertEqual(g.BUFFER_M,1250)
  self.assertEqual(g.PAGE_CAP,3)
  self.assertEqual(g.PAGE_LIMIT,100)
 def test_geoportal_does_not_allow_cross_site_next_pagination(self):
  class Mock:
   def get(self,*args,**kw):
    class Response:
     status_code=200
     content=b'{"type":"FeatureCollection","features":[],"links":[{"rel":"next","href":"https://evil.org/hijack"}]}'
     def json(self):return {"type":"FeatureCollection","features":[],"links":[{"rel":"next","href":"https://evil.org/hijack"}]}
    return Response()
  from shapely.geometry import box
  meta,feats=g.get_collection(Mock(),"cgp200k-prt-lneg-en-200k-lithology",
    [-8.1,41.1,-7.6,41.4],box(-80000,100000,80000,250000))
  self.assertEqual(meta["status"],"OFFICIAL_SOURCE_UNAVAILABLE_OR_GEOJSON_REJECTED")
  self.assertEqual(len(feats),0)
 def test_true_original_geological_features_must_be_spatially_intersected(self):
  from shapely.geometry import Point
  p=g.TO_PT.transform(-7.85,41.3)
  self.assertTrue(-100000<p[0]<100000 and 100000<p[1]<250000)
 def test_original_source_not_misclassified_as_DGT2m_ground_or_rail3D(self):
  self.assertEqual(g.BASE,"https://ogcapi.lneg.pt")
  self.assertTrue(g.COLLECTIONS["cgp1m-ge-geologicfault"]["scale"]=="1:1 000 000")
if __name__=="__main__":unittest.main()
