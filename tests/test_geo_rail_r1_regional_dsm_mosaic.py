"""Light offline contract tests for first actual 30m regional DSM acquisition."""
import importlib.util,sys,unittest,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("r1regional",ROOT/"tools"/"geo_rail_r1_regional_dsm_mosaic.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class R1RegionalContract(unittest.TestCase):
    def test_four_prelisted_native_sources_and_bounded_envelope(self):
        self.assertEqual(m.SOURCE_LENGTHS,{-9:37449439,-8:44038002,-7:41406815,-6:38671067})
        self.assertEqual(sum(m.SOURCE_LENGTHS.values()),161565323)
        self.assertEqual(m.OUTPUT_BBOX_WGS84,(-8.75,41.08,-5.55,41.92))
        self.assertEqual(m.ARCSEC,1/3600)
        self.assertTrue(all(x in m.SOURCE_LENGTHS for x in (-9,-8,-7,-6)))
        # Official LPPR airport reference point 41°14'08"N, 008°40'41"W
        airport=(-8-(40+41/60)/60,41+(14+8/60)/60)
        self.assertTrue(m.OUTPUT_BBOX_WGS84[0] < airport[0] < m.OUTPUT_BBOX_WGS84[2])
        self.assertTrue(m.OUTPUT_BBOX_WGS84[1] < airport[1] < m.OUTPUT_BBOX_WGS84[3])
        self.assertGreater((airport[0]-m.OUTPUT_BBOX_WGS84[0])*111195*0.753,6000)
        self.assertEqual(round((m.OUTPUT_BBOX_WGS84[2]-m.OUTPUT_BBOX_WGS84[0])*3600),11520)
        for x in (-9,-8,-7,-6):
            self.assertIn(m.source_id(x),m.source_url(x))
            self.assertIn("amazonaws.com",m.source_url(x))
        with self.assertRaises(ValueError):m.source_url(-5)
    def test_strict_license_and_not_a_dtm_or_accepted_engineering_raster(self):
        self.assertIn("Produced using Copernicus WorldDEM-30",m.LICENSE_NOTICE)
        self.assertIn("Airbus Defence and Space",m.LICENSE_NOTICE)
        self.assertIn("DSM",m.__doc__)
        self.assertIn("GLO30-DSM",m.OUT_NAME)
        self.assertLess(sum(m.SOURCE_LENGTHS.values()),m.MAX_ALL_SOURCE_BYTES)
    def test_seam_validity_calculation_has_explicit_meridian_checks(self):
        try:
            import numpy as np
            from rasterio.transform import from_origin
        except ImportError:
            self.skipTest("rasterio/numpy installed in dedicated real raster GitHub workflow")
        width=3610
        arr=np.zeros((7,width),dtype="float32")
        transform=from_origin(-8.000833333333333,41.9,m.ARCSEC,m.ARCSEC)
        # Only -8 meridian is within synthetic sample; _seam_qa deliberately
        # fails without all 3 meridians (guards against invented connectivity).
        with self.assertRaises(ValueError):
            m._seam_qa(arr,transform)
if __name__=="__main__":unittest.main()
