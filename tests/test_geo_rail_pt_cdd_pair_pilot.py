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


class FullProtectedPairFlowTests(unittest.TestCase):
    """Exercise complete run() contract without credentials, network or real downloads."""

    def _fake_run(self, fail_at_seam=False):
        import hashlib
        import json

        with TemporaryDirectory() as d:
            index=Path(d)/"reviewed-index.json"
            index.write_text(json.dumps({"type":"FeatureCollection","features":[]}))
            fake_session=MagicMock()
            fake_secret_href="https://cdd.dgterritorio.gov.pt/path?signature=DO_NOT_PERSIST"
            assets={tile:fake_secret_href for tile in m.ITEMS}

            def fake_download(session,href,destination):
                self.assertEqual(session,fake_session)
                self.assertEqual(href,fake_secret_href)
                content=(destination.name+"-mock-geotiff").encode()
                destination.write_bytes(content)
                return len(content),hashlib.sha256(content).hexdigest()

            def fake_audit(destination,index_path,tile,collection):
                content=destination.read_bytes()
                bounds=([82000,209000,83000,210000] if tile==m.NORTH_TILE
                        else [82000,208000,83000,209000])
                return dict(info(tile,bounds),
                            native_file_bytes=len(content),
                            native_sha256=hashlib.sha256(content).hexdigest())

            def inspect_seam(north,south):
                self.assertIsInstance(north,Path)
                self.assertIsInstance(south,Path)
                self.assertTrue(north.is_file() and south.is_file())
                self.assertEqual((north.name,south.name),("north.tif","south.tif"))
                if fail_at_seam:
                    raise ValueError("synthetic_raster_test_failure")
                return {"edge_mask_continuity_all_valid":True,"edge_pairs_total":500,
                        "edge_pairs_both_valid":500}

            progress={}
            with (
                patch.object(m,"catalogue_record",return_value={"bbox_wgs84":[-7.2,41.5,-7.19,41.51]}),
                patch.object(m,"authenticated_session",return_value=fake_session),
                patch.object(m,"select_exact_assets",return_value=(assets,"a"*64)),
                patch.object(m,"download_small_native",side_effect=fake_download),
                patch.object(m,"audit",side_effect=fake_audit),
                patch.object(m,"seam_report",side_effect=inspect_seam),
                patch.dict(m.os.environ,{"DGT_CDD_USERNAME":"fake","DGT_CDD_PASSWORD":"fake"}),
            ):
                if fail_at_seam:
                    with self.assertRaisesRegex(ValueError,"synthetic_raster_test_failure"):
                        m.run(index,progress)
                    self.assertEqual(progress["safe_phase"],"native_seam_pixels")
                    return None
                result=m.run(index,progress)
                self.assertEqual(progress["safe_phase"],"validated")
                self.assertTrue(result["native_pair_geometry"]["adjacent_1km_tiles_confirmed"])
                self.assertEqual(result["native_pair_seam_qa"]["edge_pairs_both_valid"],500)
                self.assertNotIn("DO_NOT_PERSIST",json.dumps(result))
                self.assertEqual(result["source_rasters_newly_published"],0)
                return result

    def test_full_flow_passes_and_uses_paths_not_nested_indices(self):
        result=self._fake_run()
        self.assertEqual(result["status"],"two_native_GeoTIFFs_authenticated_QA_and_seam_validated")

    def test_failures_record_only_safe_phase(self):
        self._fake_run(fail_at_seam=True)


if __name__=="__main__":
    unittest.main()
