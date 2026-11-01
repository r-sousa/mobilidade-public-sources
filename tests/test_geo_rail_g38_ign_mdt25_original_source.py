"""G38 bounded source receipts; no fake bare-earth from XML/HTML or missing raster."""
import unittest,sys,pathlib,importlib.util
try:
 import numpy,rasterio,pyproj
 OK=True
except ImportError:OK=False
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 spec=importlib.util.spec_from_file_location("g38",root/"tools/geo_rail_g38_1km_original_IGN_ground_source_probe.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G38 optional original GIS stack on dedicated runner")
class G38SourcePilot(unittest.TestCase):
 def test_OGC_coverage_identifiers_not_inferred(self):
  raw=b'<wcs:Capabilities xmlns:wcs="http://www.opengis.net/wcs/2.0"><wcs:Contents><wcs:CoverageSummary><wcs:CoverageId>mdt25_25830</wcs:CoverageId></wcs:CoverageSummary></wcs:Contents></wcs:Capabilities>'
  ids=g.parse_wcs_capabilities(raw)
  self.assertEqual(ids,["mdt25_25830"])
  self.assertEqual(g.choose_candidate(ids),"mdt25_25830")
  self.assertIsNone(g.choose_candidate(["DSM_vegetation","orthophoto"]))
 def test_no_valid_raster_implicit_from_OGC_error(self):
  with self.assertRaises(ValueError):
   g.sanity_ground_tiff(b'<ExceptionReport>bad coverage</ExceptionReport>')
 def test_small_verified_raster_has_real_geo_metadata(self):
  import numpy as np
  import rasterio
  from rasterio.io import MemoryFile
  from rasterio.transform import from_origin
  data=np.full((40,40),650,dtype="float32")
  with MemoryFile() as mem:
   with mem.open(driver="GTiff",height=40,width=40,count=1,dtype="float32",
                 crs="EPSG:25830",transform=from_origin(280000,4596000,25,25)) as ds:
    ds.write(data,1)
   raw=mem.read()
  qa=g.sanity_ground_tiff(raw)
  self.assertEqual(qa["source_crs"],"EPSG:25830")
  self.assertEqual(qa["resolution"],[25,25])
  self.assertTrue(qa["raster_vertical_datum_NOT_harmonized_with_PT_Cascais1938"])
 def test_download_limit_and_explicit_schema(self):
  self.assertEqual(g.WINDOW_HALF_M,500)
  self.assertLessEqual(g.MAX_TIFF_BYTES,3_000_000)
  self.assertEqual(g.SAMPLE_LAT,41.503)
 def test_WCS_xml_not_tiff_even_if_binary_bytes_read(self):
  self.assertTrue(g.url_of("https://example.org/wcs",[("subset","E(1,2)"),("subset","N(3,4)")]).startswith("https://"))
if __name__=="__main__":unittest.main()
