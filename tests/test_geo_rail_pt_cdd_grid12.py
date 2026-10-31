"""DGT W2 12-square source-grounded bounds and full simulated raster-grid QA."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("dgt_grid12",ROOT/"tools"/"geo_rail_pt_cdd_grid12.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
INDEX=ROOT/"reports/mn-geo-rail-001/pt-dgt-mdt-candidate-envelopes.geojson"

class IndexAndContractTests(unittest.TestCase):
    def test_twelve_distinct_pre_reviewed_tile_ids(self):
        self.assertEqual(len(m.GRID_TILES),12)
        self.assertEqual(len(set(x[2] for x in m.GRID_TILES)),12)
        self.assertEqual(m.GRID_TILES[0][2],"MDT-2m-280507-09-2024")
        self.assertEqual(m.GRID_TILES[-1][2],"MDT-2m-282510-09-2024")
        self.assertEqual(m.MAX_TOTAL_NATIVE_BYTES,60_000_000)
        self.assertEqual(m.expected_bbox(280,507),[80000,206000,81000,207000])
        self.assertEqual(m.expected_bbox(282,510),[82000,209000,83000,210000])
        with self.assertRaises(ValueError):
            m.expected_bbox(283,510)

    def test_all_twelve_objects_in_actual_pre_reviewed_public_source_index(self):
        self.assertTrue(INDEX.is_file())
        m.reviewed_grid_index(INDEX)

    def test_native_grid_allows_only_exact_shapes_and_bounds(self):
        xs={}
        for col,row,tile in m.GRID_TILES:
            xs[tile]={"raster":{"horizontal_crs":"EPSG:3763",
                "resolution_m":[2.0,2.0],"width_px":500,"height_px":500,
                "bounds_pttm06":m.expected_bbox(col,row),
                "valid_pixels":250000,"masked_pixels":0}}
        self.assertTrue(m.validate_native_grid_geometry(xs))
        xs["MDT-2m-281509-09-2024"]["raster"]["masked_pixels"]=1
        with self.assertRaisesRegex(ValueError,"pixels_incomplete"):
            m.validate_native_grid_geometry(xs)

@unittest.skipUnless(importlib.util.find_spec("rasterio") and importlib.util.find_spec("numpy"),"needs native raster test environment")
class FullGridSyntheticRasterTests(unittest.TestCase):
    @staticmethod
    def make_native(path,col,row,missing_edge=False):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin
        bbox=m.expected_bbox(col,row)
        elevation=np.full((500,500),300+col*.1+row*.1,dtype="float32")
        if missing_edge: elevation[200,0]=-999.0
        with rasterio.open(path,"w",driver="GTiff",count=1,
            width=500,height=500,dtype="float32",crs="EPSG:3763",
            transform=from_origin(bbox[0],bbox[3],2,2),nodata=-999.0) as ds:
            ds.write(elevation,1)

    def test_all_17_joins_have_8500_valid_pairs(self):
        with TemporaryDirectory() as d:
            paths={}
            for col,row,tile in m.GRID_TILES:
                dest=Path(d)/f"{col}_{row}.tif"
                self.make_native(dest,col,row)
                paths[tile]=dest
            joins=m.evaluate_seams(paths)
            self.assertEqual(len(joins),17)
            self.assertEqual(sum(x["pairs_valid"] for x in joins),8500)
            self.assertTrue(all(x["max_abs_neighbor_diff_m"]<1 for x in joins))

    def test_missing_edge_pixel_fails_closed(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"a.tif"
            q=Path(d)/"b.tif"
            self.make_native(p,280,508)
            self.make_native(q,281,508,missing_edge=True)
            with self.assertRaisesRegex(ValueError,"incomplete_or_masked"):
                m.compare_shared_edges(p,q,"west_east")

    def test_complete_protected_flow_simulated_no_credentials(self):
        with TemporaryDirectory() as d:
            folder=Path(d)
            index=folder/"reviewed_index.json"
            index.write_text('{"type":"FeatureCollection","features":[]}')
            mock_session=MagicMock()
            signed_fake="https://cdd.dgterritorio.gov.pt/n/asset?secret=NEVER_PERSIST"
            stac={tile:signed_fake for _,_,tile in m.GRID_TILES}

            def fake_download(session,url,dest):
                self.assertEqual(session,mock_session)
                self.assertEqual(url,signed_fake)
                ids=dest.stem.split("_")
                self.make_native(dest,int(ids[1]),int(ids[2]))
                b=dest.read_bytes()
                return len(b),hashlib.sha256(b).hexdigest()

            def fake_audit(path,index_path,tile,collection):
                col,row=next((c,r) for c,r,name in m.GRID_TILES if tile==name)
                b=path.read_bytes()
                return {"native_file_bytes":len(b),"native_sha256":hashlib.sha256(b).hexdigest(),
                    "raster":{"horizontal_crs":"EPSG:3763","resolution_m":[2.0,2.0],
                    "width_px":500,"height_px":500,"bounds_pttm06":m.expected_bbox(col,row),
                    "valid_pixels":250000,"masked_pixels":0}}
            progress={}
            with (
                patch.object(m,"reviewed_grid_index",return_value={}),
                patch.object(m,"authenticated_session",return_value=mock_session),
                patch.object(m,"select_exact_assets",return_value=(stac,"e"*64)),
                patch.object(m,"download_small_native",side_effect=fake_download),
                patch.object(m,"audit",side_effect=fake_audit),
                patch.dict(m.os.environ,{"DGT_CDD_USERNAME":"dummy","DGT_CDD_PASSWORD":"dummy"}),
            ):
                receipt=m.run(index,progress,folder/"staged")
            self.assertEqual(progress["safe_phase"],"validated")
            self.assertEqual(receipt["native_files_sha_verified_in_temporary_release_staging"],12)
            self.assertEqual(len(list((folder/"staged").glob("grid_*.tif"))),12)
            self.assertEqual(receipt["tile_count"],12)
            self.assertEqual(receipt["joins_total"],17)
            self.assertEqual(receipt["joint_neighbor_cell_pairs_valid"],8500)
            self.assertEqual(receipt["valid_native_pixel_cells"],3_000_000)
            self.assertNotIn("NEVER_PERSIST",json.dumps(receipt))
            self.assertTrue(receipt["no_source_raster_publication"])

if __name__=="__main__":
    unittest.main()
