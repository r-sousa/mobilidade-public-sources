"""Synthetic DGT MDT GeoTIFF intake QA, with no real user credentials or native data."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

source=Path(__file__).resolve().parents[1]/"tools"/"geo_rail_pt_native_intake_qa.py"
spec=importlib.util.spec_from_file_location("dgt_native_intake",source)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

HAS_GEO=importlib.util.find_spec("rasterio") is not None and importlib.util.find_spec("numpy") is not None


class IndexContractTests(unittest.TestCase):
    def test_requires_single_correct_source_item_and_proxy(self):
        item={"type":"Feature","properties":{
            "source_collection":"MDT-2m","producer_tile_id":"MDT-2m-PILOT-2026",
            "geometry_is_bbox_proxy_not_original_footprint":True,
            "bbox_method":"geometry_recovered","query_window_ids":["E01"]},
            "geometry":{"type":"Polygon","coordinates":[[
                [-7.20,41.50],[-7.19,41.50],[-7.19,41.51],
                [-7.20,41.51],[-7.20,41.50]]]}}
        result=m.catalogue_record({"type":"FeatureCollection","features":[item]},
                                  "MDT-2m","MDT-2m-PILOT-2026")
        self.assertEqual(result["bbox_method"],"geometry_recovered")
        self.assertEqual(result["bbox_wgs84"],[-7.2,41.5,-7.19,41.51])
        with self.assertRaises(ValueError):
            m.catalogue_record({"type":"FeatureCollection","features":[item,item]},
                               "MDT-2m","MDT-2m-PILOT-2026")

    def test_refuses_nonapproved_source_name(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                m.audit(Path(directory)/"fake.tif",Path(directory)/"index.json",
                        "LAZ-PILOT-2026","LAZ")


@unittest.skipUnless(HAS_GEO,"rasterio and numpy installed in standalone W2 intake tests")
class RasterPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix="mn-dgt-intake-test-")
        self.dir=Path(self.temp.name)
        self.path=self.dir/"source_data.tif"
        self.index=self.dir/"safe-index.geojson"
        self.tile_id="MDT-2m-PILOT-2026"

    def tearDown(self):
        self.temp.cleanup()

    def make_input(self,crs="EPSG:3763",pix=2.0,nodata=-9999.0):
        import rasterio
        import numpy as np
        from rasterio.transform import from_origin
        from rasterio.warp import transform_bounds
        west,south=60000,220000
        dims=40
        transform=from_origin(west,south+dims*pix,pix,pix)
        arr=np.arange(dims*dims,dtype="float32").reshape(dims,dims)/10+100
        arr[3,4]=nodata
        with rasterio.open(self.path,"w",driver="GTiff",height=dims,width=dims,
                           count=1,dtype="float32",crs=crs,transform=transform,
                           nodata=nodata,compress="lzw") as out:out.write(arr,1)
        geo=list(transform_bounds("EPSG:3763","EPSG:4326",
                                  west,south,west+dims*pix,south+dims*pix))
        # approximate source bbox proxy; STAC native geometry is not published
        x0,y0,x1,y1=geo
        item={"type":"Feature",
              "properties":{"source_collection":"MDT-2m",
              "producer_tile_id":self.tile_id,
              "geometry_is_bbox_proxy_not_original_footprint":True,
              "bbox_method":"geometry_recovered","query_window_ids":["E04"]},
              "geometry":{"type":"Polygon","coordinates":[[
                  [x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]]}}
        self.index.write_text(json.dumps({"type":"FeatureCollection",
                                          "features":[item]}),encoding="utf-8")

    def test_native_raster_checks_with_no_raw_data_in_receipt(self):
        self.make_input()
        record=m.audit(self.path,self.index,self.tile_id,"MDT-2m")
        self.assertEqual(record["raster"]["horizontal_crs"],"EPSG:3763")
        self.assertEqual(record["raster"]["valid_pixels"],1599)
        self.assertEqual(record["raster"]["masked_pixels"],1)
        self.assertEqual(record["raster"]["resolution_m"],[2.0,2.0])
        self.assertEqual(len(record["native_sha256"]),64)
        self.assertNotIn(str(self.path),json.dumps(record))
        self.assertFalse(record["canonical_Fxx_accepted"])
        self.assertFalse(record["site_publication_authorized"])

    def test_reject_wrong_pixel_resolution(self):
        self.make_input(pix=5.0)
        with self.assertRaisesRegex(ValueError,"resolution"):
            m.audit(self.path,self.index,self.tile_id,"MDT-2m")


if __name__=="__main__":
    unittest.main()
