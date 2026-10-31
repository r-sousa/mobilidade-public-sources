"""Contract tests for the protected DGT adjacent-native pair runner, no secrets."""
import importlib.util
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("dgt_adjacent",ROOT/"tools"/"geo_rail_pt_cdd_pair_pilot.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def info(tile,bbox):
    return {"producer_tile_id":tile,"raster":{
        "horizontal_crs":"EPSG:3763","resolution_m":[2.0,2.0],
        "width_px":500,"height_px":500,"bounds_pttm06":bbox}}

class PairBounds(unittest.TestCase):
    def test_exact_adjacent_1km_pair(self):
        north=info(m.NORTH_TILE,[82000,209000,83000,210000])
        south=info(m.SOUTH_TILE,[82000,208000,83000,209000])
        x=m.pair_geometry(north,south)
        self.assertEqual(x["combined_sample_area_km2"],2)
        self.assertEqual(x["shared_boundary_y_m"],209000)

    def test_gap_or_overlap_rejected(self):
        north=info(m.NORTH_TILE,[82000,209000,83000,210000])
        south=info(m.SOUTH_TILE,[82000,207998,83000,208998])
        with self.assertRaisesRegex(ValueError,"not_exact_adjacent"):
            m.pair_geometry(north,south)

    def test_mismatched_crs_rejected(self):
        north=info(m.NORTH_TILE,[82000,209000,83000,210000])
        south=info(m.SOUTH_TILE,[82000,208000,83000,209000])
        south["raster"]["horizontal_crs"]="EPSG:25830"
        with self.assertRaisesRegex(ValueError,"not_in_PT_TM06"):
            m.pair_geometry(north,south)

    def test_hard_limited_download(self):
        class FakeResponse:
            status_code=200
            headers={"Content-Length":"99999999","Content-Type":"image/tiff"}
            def close(self):pass
        with TemporaryDirectory() as folder:
            with patch.object(m,"native_response_from_dgt_with_single_storage_hop",return_value=(FakeResponse(),None)):
                with self.assertRaisesRegex(m.IntakeError,"exceeds_25MB"):
                    m.download_small_native(object(),"https://unneeded.example",Path(folder)/"n.tif")

    def test_exactly_two_approved_tile_ids_and_no_new_public_release(self):
        self.assertEqual(m.ITEMS,("MDT-2m-282510-09-2024","MDT-2m-282509-09-2024"))
        self.assertEqual(m.MAX_AGGREGATE_BYTES,50_000_000)
        self.assertEqual(m.COLLECTION,"MDT-2m")

@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("rasterio"),"geospatial runner")
class NativeSeamTests(unittest.TestCase):
    def test_real_tiff_mock_seam_continuity(self):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin
        with TemporaryDirectory() as tmp:
            paths=[Path(tmp)/"north.tif",Path(tmp)/"south.tif"]
            for file,y,value in [(paths[0],210000,100.0),(paths[1],209000,101.0)]:
                with rasterio.open(file,"w",driver="GTiff",height=500,width=500,count=1,
                    dtype="float32",crs="EPSG:3763",transform=from_origin(82000,y,2,2),
                    nodata=-999.0) as d:
                    d.write(np.full((500,500),value,dtype="float32"),1)
            report=m.seam_report(*paths)
            self.assertEqual(report["edge_pairs_both_valid"],500)
            self.assertEqual(report["max_abs_neighbor_cell_elevation_difference_m"],1.0)
            self.assertTrue(report["edge_mask_continuity_all_valid"])

if __name__=="__main__":
    unittest.main()
