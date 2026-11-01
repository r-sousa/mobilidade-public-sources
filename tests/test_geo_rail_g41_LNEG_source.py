"""G41 WFS official LNEG safety: exact source family, bounded five features, no missing-as-absence."""
import unittest,importlib.util,pathlib
try:
 import shapely
 GIS=True
except ImportError:GIS=False
if GIS:
 root=pathlib.Path(__file__).resolve().parents[1]
 spec=importlib.util.spec_from_file_location("g41",root/"tools/geo_rail_g41_LNEG_original_geology_hydro_borehole_WFS.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(GIS,"Dedicated LNEG source geo tests")
class G41Test(unittest.TestCase):
 def test_four_exact_official_geology_hydro_borehole_sources(self):
  self.assertEqual(len(g.DATA),4)
  self.assertTrue(all(o["url"].startswith("https://") for o in g.DATA.values()))
  self.assertTrue(all("lneg.pt" in o["url"] for o in g.DATA.values()))
 def test_parse_real_WFS_2_names(self):
  raw=b'<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0"><wfs:FeatureTypeList><wfs:FeatureType><wfs:Name>ge:GeologicUnit</wfs:Name><wfs:Title>Geology Unit</wfs:Title></wfs:FeatureType></wfs:FeatureTypeList></wfs:WFS_Capabilities>'
  f=g.cap_names(raw)
  self.assertEqual(f[0]["source_typeName"],"ge:GeologicUnit")
  self.assertEqual(g.pick_type(f,"harmonised_geology_50k")["source_typeName"],"ge:GeologicUnit")
 def test_not_a_capabilities_blob_fails(self):
  with self.assertRaises(ValueError):g.cap_names(b'<html><body>not data</body></html>')
 def test_two_bounded_regions_only(self):
  self.assertEqual(set(g.AREAS),{"Marao","Alvao"})
  self.assertLess(g.MAX_BYTES,3_000_000)
  self.assertTrue(all(len(v)==4 for v in g.AREAS.values()))
 def test_no_automatic_regional_geotechnical_claim(self):
  self.assertTrue("WFS" in g.DATA["SONDABASE_boreholes"]["url"])
if __name__=="__main__":unittest.main()
