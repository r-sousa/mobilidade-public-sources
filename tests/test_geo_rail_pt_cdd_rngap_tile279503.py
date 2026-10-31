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
            report=m.compare_real_mark_native_terrain(f,marks)
            self.assertEqual(report["raw_DGT_2m_nearest_pixel_height_m"],229)
            self.assertEqual(len(report["comparisons_to_five_mark_VARIANT_heights"]),5)
            self.assertTrue(report["not_an_independent_survey_error_estimate"])
            self.assertTrue(all(x["same_geographic_XY_as_other_4_marks"] for x in report["comparisons_to_five_mark_VARIANT_heights"]))

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
                m.compare_real_mark_native_terrain(f,marks)
if __name__=="__main__":
    unittest.main()
