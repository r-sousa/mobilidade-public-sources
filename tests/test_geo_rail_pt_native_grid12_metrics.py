"""12km² DGT source-mosaic and 2m terrain derivation contracts; no Internet."""
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("native_grid12_metrics",ROOT/"tools"/"geo_rail_pt_native_grid12_metrics.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class SourceIdentityTests(unittest.TestCase):
    def test_expected_source_release_and_scope(self):
        self.assertEqual(m.SOURCE_RELEASE,
            "mn-geo-rail-001-dgt-grid12-preacceptance-41158397813")
        self.assertEqual(m.EXPECTED_EXTENT,(80000,206000,83000,210000))
        self.assertEqual(len(m.EXPECTED_TILES),12)
        self.assertEqual(m.TOTAL_EXPECTED_CELLS,3000000)

    def test_untrusted_wrong_source_provenance_rejected(self):
        with TemporaryDirectory() as d:
            p=Path(d)
            index=p/"index.json"
            manifest=p/"manifest.json"
            manifest.write_text('{}')
            index.write_text(json.dumps({
                "mission":"MN-GEO-RAIL-001","area_km2":12,
                "origin_release":"https://unreviewed.example/releases/tag/fake",
                "source_tiles":[]}))
            with self.assertRaisesRegex(ValueError,"unexpected_DGT_source_release"):
                m.verified_source_records(index,p,manifest)

@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("rasterio"),"needs numpy/rasterio")
class RasterMosaicTests(unittest.TestCase):
    @staticmethod
    def generate_source(tmp):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin
        paths={}
        for row in m.ROWS:
            for col in m.COLS:
                name=f"grid_{col}_{row}.tif"
                path=tmp/name
                y,x=np.indices((500,500),dtype="float32")
                arr=(300+(col-280)*2.2+(row-507)*1.3+x*.01+y*.012).astype("float32")
                with rasterio.open(path,"w",driver="GTiff",height=500,width=500,
                                   count=1,dtype="float32",crs="EPSG:3763",
                                   transform=from_origin((col-200)*1000,(row-300)*1000,2,2)) as ds:
                    ds.write(arr,1)
                paths[name]=dict(id=f"MDT-2m-{col}{row}-09-2024",
                                 bytes=path.stat().st_size,
                                 sha256=m.sha256(path))
        return paths

    def test_build_exact_native_mosaic_and_reopen(self):
        import rasterio
        with TemporaryDirectory() as d:
            temp=Path(d)
            inputs=temp/"source";inputs.mkdir()
            paths=self.generate_source(inputs)
            raster=temp/"mosaic.tif";rec=temp/"qa.json"
            r=m.mosaic_native(paths,inputs,raster,rec)
            self.assertEqual(r["n_native_source_tiles"],12)
            self.assertEqual(r["pixel_count_valid"],3000000)
            self.assertEqual(r["adjacent_source_cells_verified"],8500)
            self.assertEqual(r["geographic_area_km2"],12)
            self.assertEqual(r["mosaic_bbox_pttm06"],[80000.0,206000.0,83000.0,210000.0])
            self.assertEqual(r["mosaic_dimensions"],[1500,2000])
            self.assertGreater(r["terrain_slope_percent_quantiles"]["50"],0)
            self.assertGreater(r["terrain_slope_percent_quantiles"]["99"],
                               r["terrain_slope_percent_quantiles"]["50"])
            self.assertEqual(r["derived_mosaic_sha256"],m.sha256(raster))
            with rasterio.open(raster) as ds:
                self.assertEqual(ds.crs.to_epsg(),3763)
                self.assertEqual((ds.width,ds.height),(1500,2000))
                self.assertTrue(ds.tags()["LICENSE"].startswith("CC BY 4.0"))
            self.assertFalse(r["Fxx_canonical_accepted"])
            self.assertFalse(r["rail_alignment_ready"])
            self.assertTrue(rec.exists())

    def test_fails_on_unnative_grid_transform(self):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin
        with TemporaryDirectory() as d:
            temp=Path(d)
            inputs=temp/"source";inputs.mkdir()
            paths=self.generate_source(inputs)
            bad=inputs/"grid_281_509.tif"
            with rasterio.open(bad,"w",driver="GTiff",height=500,width=500,
                               count=1,dtype="float32",crs="EPSG:3763",
                               transform=from_origin(81300,210000,2,2)) as ds:
                ds.write(np.ones((500,500),dtype="float32"),1)
            with self.assertRaisesRegex(ValueError,"transform_mismatch"):
                m.mosaic_native(paths,inputs,temp/"bad.tif",temp/"qa.json")

if __name__=="__main__":
    unittest.main()
