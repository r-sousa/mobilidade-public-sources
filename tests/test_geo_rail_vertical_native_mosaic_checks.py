"""W4 regression tests: official source pins, vertical-shift sign, domain and trust labels."""
import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("vertical_mosaic",ROOT/"tools"/"geo_rail_vertical_native_mosaic_checks.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ProvenanceTests(unittest.TestCase):
    def test_authoritative_source_and_sha_pins(self):
        self.assertEqual(len(m.GRIDS),2)
        self.assertEqual(m.SOURCE_MOSAIC_RELEASE,
                         "mn-geo-rail-001-pt-dgt-grid12-mosaic-41158983022")
        self.assertEqual(len(m.SAMPLE_PIXELS),9)
        self.assertEqual(m.PT_VERTICAL,"EPSG:5780")
        self.assertEqual(m.ES_VERTICAL,"EPSG:5782")
        self.assertEqual(m.MAX_BYTES,2_000_000)
        self.assertTrue(all(len(x[0])==64 and x[1]<m.MAX_BYTES for x in m.GRIDS.values()))

    def test_bad_grid_identity_fails_without_network_call(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                m.bounded_grid("unexpected.tif",("0"*64,1),Path(d),fetcher=lambda *_:None)

    def test_synthetic_vertical_closure_and_outside_portuguese_domain_fail_closed(self):
        class FakeTransform:
            def transform(self,lon,lat,h,direction=None,errcheck=False):
                if lon>-6: return lon,lat,float("inf")
                if direction is not None: return lon,lat,h-0.12
                return lon,lat,h+0.12
        r=m.site_numeric_checks(FakeTransform())
        self.assertEqual(len(r),5)
        self.assertTrue(all(not z["vertical_transform_supported"] for z in r if z["site"]=="ES_Zamora"))
        self.assertTrue(all(abs(z["computed_Cascais_to_Alicante_vertical_offset_m"]-.12)<1e-8
                            for z in r if z["vertical_transform_supported"]))
        self.assertTrue(all(z["synthetic_only"] for z in r))

    def test_wrong_mosaic_hash_stops_before_any_raster_use(self):
        with TemporaryDirectory() as d:
            source=Path(d)/"source.tif"
            source.write_bytes(b"untrusted user raster")
            with self.assertRaisesRegex(ValueError,"SHA256_not_as_published"):
                m.source_mosaic_checks(source,object())

if __name__=="__main__":
    unittest.main()
