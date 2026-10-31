"""Protected 279503 DGT native raster + true DGT 427 RNGAP source mark contracts."""
import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("protected_tile",ROOT/"tools"/"geo_rail_pt_cdd_rngap_tile279503.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class OriginalSourceContracts(unittest.TestCase):
    def test_approved_source_tile_exact_279503_and_five_real_wfs_marks(self):
        self.assertEqual(m.SOURCE_TILE,"MDT-2m-279503-09-2024")
        self.assertEqual(m.SOURCE_BOUNDS,[79000,202000,80000,203000])
        marks,sha=m.producer_mark_records(ROOT/"reports/mn-geo-rail-001/pt-rngap-three-window-complete-ALTH38-source.json")
        self.assertEqual(len(marks),5)
        self.assertEqual(len(sha),64)
        descriptions,proof=m.inspected_physical_mark_descriptions(ROOT/m.SOURCE_DESCRIPTORS,marks)
        self.assertEqual(len(descriptions),5)
        self.assertEqual(len(set(descriptions.values())),5)
        self.assertEqual(len(proof),64)
        self.assertEqual({tuple(x["native_xy_epsg3763"]) for x in marks},{(79468.618,202288.178)})
        self.assertEqual(len({x["WFS_feature_id"] for x in marks}),5)

    def test_no_unreviewed_source_record(self):
        with self.assertRaises(FileNotFoundError):
            m.producer_mark_records(ROOT/"missing-pt-rngap-source.json")

    @unittest.skipUnless(importlib.util.find_spec("rasterio"),"requires optional rasterio")
    def test_synthetic_native_pixel_versus_all_five_real_mark_heights(self):
        import rasterio
        import numpy as np
        from rasterio.transform import from_origin
        marks,_=m.producer_mark_records(ROOT/"reports/mn-geo-rail-001/pt-rngap-three-window-complete-ALTH38-source.json")
        with TemporaryDirectory() as d:
            f=Path(d)/"synthetic.tif"
            with rasterio.open(f,"w",driver="GTiff",width=500,height=500,
                               count=1,dtype="float32",crs="EPSG:3763",
                               transform=from_origin(79000,203000,2,2),
                               nodata=-9999) as src:
                src.write(np.full((500,500),229.0,dtype="float32"),1)
            descriptions,_=m.inspected_physical_mark_descriptions(ROOT/m.SOURCE_DESCRIPTORS,marks)
            report=m.compare_real_mark_native_terrain(f,marks,descriptions)
            self.assertEqual(report["nominal_raster_pixel_at_shared_surrogate_xy_m"],229)
            self.assertEqual(len(report["source_mark_descriptions_and_heights"]),5)
            self.assertTrue(report["individual_pointwise_raster_mark_residuals_not_computed"])
            self.assertTrue(all(x["individual_ground_pixel_residual_m"] is None for x in report["source_mark_descriptions_and_heights"]))

    @unittest.skipUnless(importlib.util.find_spec("rasterio"),"requires optional rasterio")
    def test_wrong_original_raster_bbox_rejected(self):
        import rasterio
        import numpy as np
        from rasterio.transform import from_origin
        marks,_=m.producer_mark_records(ROOT/"reports/mn-geo-rail-001/pt-rngap-three-window-complete-ALTH38-source.json")
        with TemporaryDirectory() as d:
            f=Path(d)/"wrong-southern-tile.tif"
            with rasterio.open(f,"w",driver="GTiff",width=500,height=500,
                               count=1,dtype="float32",crs="EPSG:3763",
                               transform=from_origin(79000,202000,2,2)) as src:
                src.write(np.full((500,500),229.0,dtype="float32"),1)
            with self.assertRaisesRegex(ValueError,"exact_bbox"):
                m.compare_real_mark_native_terrain(f,marks,{x["WFS_feature_id"]:"Distinct physical mark" for x in marks})
if __name__=="__main__":
    unittest.main()
