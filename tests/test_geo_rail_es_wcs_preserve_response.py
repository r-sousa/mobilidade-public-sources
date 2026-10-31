"""No-network W3 verification of bounded WCS 5m and 25m source TIFF contract."""
import importlib.util,sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("w3_cnig_original_response",ROOT/"tools"/"geo_rail_es_wcs_preserve_response.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CNIGWCSOriginalResponse(unittest.TestCase):
    def test_bounded_unambiguous_scope_and_no_secrets(self):
        self.assertEqual(m.AREA_BBOX,[270500,4597800,271500,4598800])
        self.assertEqual(set(m.FILE_BY_COVERAGE),{"Elevacion25830_5","Elevacion25830_25"})
        self.assertIn("CC BY 4.0",m.LICENSE)
        for c in m.FILE_BY_COVERAGE:
            u=m.coverage_url(c)
            self.assertIn("GetCoverage",u)
            self.assertIn("subset=x%28270500%2C271500%29",u)
            self.assertIn("subset=y%284597800%2C4598800%29",u)
            self.assertIn(c,u)

    def make_synthetic(self,p,c,bad=False):
        import rasterio
        import numpy as np
        from rasterio.transform import from_origin
        res=int(c.rsplit("_",1)[1])
        n=1000//res
        with rasterio.open(p,"w",driver="GTiff",count=1,dtype="float32",
                           width=n,height=n,crs="EPSG:25830",
                           transform=from_origin(270500,4598800,1 if bad else res,res)) as ds:
            ds.write(np.full((n,n),645.25,dtype="float32"),1)

    def test_real_binary_contract_in_synthetic_small_local_files(self):
        try:
            import rasterio  # provided by the W3 source workflow; optional in lean global CI
            import numpy
        except ImportError:
            self.skipTest("rasterio/numpy are source-raster QA extras; W3 workflow installs and executes this test")
        from geo_rail_es_wcs_preserve_response import _check_tiff
        with tempfile.TemporaryDirectory() as tmp:
            for coverage in m.FILE_BY_COVERAGE:
                p=Path(tmp)/m.FILE_BY_COVERAGE[coverage]
                self.make_synthetic(p,coverage)
                d=_check_tiff(p,coverage)
                self.assertEqual(d["crs_horizontal_epsg"],25830)
                self.assertFalse(d["vertical_crs_encoded_in_GeoTIFF"])
                self.assertFalse(d["vertical_datum_by_independent_geodetic_control_verified"])
                self.assertEqual(d["valid_cells"],(1000//d["pixel_resolution_m"])**2)
            c="Elevacion25830_5"
            p=Path(tmp)/m.FILE_BY_COVERAGE[c]
            self.make_synthetic(p,c,bad=True)
            with self.assertRaises(ValueError):
                _check_tiff(p,c)
if __name__=="__main__":unittest.main()
