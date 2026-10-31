"""DGT B1 mandatory city station area shortlist based on authentic source ID grids."""
import importlib.util,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/"tools"))
sp=importlib.util.spec_from_file_location("dgtb1",R/"tools"/"geo_rail_pt_b1_dgt_review_grids.py")
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class MandatorySourceGrid(unittest.TestCase):
    def test_city_and_catalogue_not_sanabria(self):
        self.assertEqual(set(m.SITES),{"Vila Real","Bragança"})
        self.assertEqual(sum(z[2] for z in m.SOURCE_SPECS),116)
        self.assertEqual(len(m.SOURCE_SPECS),5)
        self.assertIsNone(m.REGEX.fullmatch("MDT-2m-003003-X-2024"))
    def test_actual_source_receipts_select_grid_alternatives(self):
        q=m.run(R/"reports"/"mn-geo-rail-001")
        self.assertEqual(q["mandatory_service_cities"],["Vila Real","Bragança"])
        self.assertTrue(q["Sanabria_excluded"])
        self.assertFalse(q["stations_in_city_centres_required"])
        self.assertTrue(q["no_current_original_DGT_raster_bytes_downloaded"])
        self.assertTrue(q["use_real_road_geometry_and_terrain_before_protected_DGT_acquisition"])
        self.assertFalse(q["Fxx_accepted"])
        for city in m.SITES:
            self.assertGreater(q["review_groups_by_city"][city],0)
        for x in q["review_only_source_tile_groups"]:
            self.assertEqual(len(set(x["source_2m_native_tile_ids"])),4)
            self.assertFalse(x["is_candidate_station"])
if __name__=="__main__":unittest.main()
