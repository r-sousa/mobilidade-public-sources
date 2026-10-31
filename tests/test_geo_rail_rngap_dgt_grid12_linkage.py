"""Original W4 RNGAP mark vs W2 DGT 12km2 source QA and target tile contract."""
import importlib.util
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("link",ROOT/"tools"/"geo_rail_rngap_dgt_grid12_linkage.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_original_real_sources_select_single_target_tile(self):
  d=m.source_sample(ROOT/"reports/mn-geo-rail-001/pt-rngap-three-window-complete-ALTH38-source.json",
                    ROOT/"reports/mn-geo-rail-001/pt-dgt-mdt-sector-footprints.json")
  self.assertEqual(d["original_DGT_WFS_marks_in_three_reviewed_windows"],427)
  self.assertEqual(d["original_RNGAP_marks_in_validated_12km2_mosaic"],0)
  self.assertEqual(d["next_priority_1km2_DGT_original_raster_candidate"],"MDT-2m-279503-09-2024")
  self.assertEqual(d["next_priority_benchmark_mark_count"],5)
  self.assertEqual(d["next_priority_native_raster_bounds_epsg3763"],[79000,202000,80000,203000])
  self.assertEqual(d["grid_index_formula"],"col=200+floor(x/1000); row=301+floor(y/1000)")
  self.assertTrue(all(79000<=m["xy_PT_TM06"][0]<80000 and
                      202000<=m["xy_PT_TM06"][1]<203000
                      for m in d["next_priority_mark_records"]))
  self.assertEqual(d["next_priority_benchmark_distinct_planimetric_positions"],1)
  self.assertGreater(d["next_priority_same_XY_published_height_spread_m"],1)
  self.assertTrue(d["selected_source_tile_is_NOT_yet_acquired_or_pixel_QA_validated"])
  self.assertFalse(d["crossborder_vertical_benchmark_control_accepted"])
 def test_no_untrusted_missing_source(self):
  with self.assertRaises(FileNotFoundError):
   m.source_sample(ROOT/"missing.json",ROOT/"reports/mn-geo-rail-001/pt-dgt-mdt-sector-footprints.json")
if __name__=="__main__":unittest.main()
