"""Unit tests: no producer access and no elevation files required."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "geo_rail_r1_index.py"
spec = importlib.util.spec_from_file_location("geo_rail_r1_index", MODULE_PATH)
geo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)


class R1InventoryTests(unittest.TestCase):
    def test_bbox_covers_twelve_candidate_cells(self):
        bbox = geo.parse_bbox("-9,40.8,-5.5,42.5")
        result = geo.build_inventory(bbox)
        self.assertEqual(result["metadata"]["tile_count"], 12)
        self.assertEqual(result["metadata"]["status_counts"], {"unverified": 12})
        self.assertIn("Copernicus_DSM_COG_10_N41_00_W009_00_DEM",
                      [f["id"] for f in result["features"]])
        self.assertTrue(all(not f["properties"]["native_raster_validated"]
                            for f in result["features"]))

    def test_tile_list_does_not_validate_native_asset(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tileList.txt"
            p.write_text("Copernicus_DSM_COG_10_N41_00_W009_00_DEM/\n")
            names, digest = geo.read_available_tile_names(p)
            inventory = geo.build_inventory((-9, 41, -8, 42), names, digest)
            self.assertEqual(inventory["metadata"]["status_counts"],
                             {"listed_not_validated": 1})
            self.assertFalse(inventory["metadata"]["is_coverage_verified"])
            self.assertEqual(len(digest), 64)

    def test_unlisted_is_not_synonymous_with_absent(self):
        result = geo.build_inventory((-9, 41, -8, 42), set())
        self.assertEqual(result["metadata"]["status_counts"],
                         {"not_in_supplied_list": 1})

    def test_bbox_validation(self):
        for box in ["-8,41,-9,42", "nan,41,-7,42", "-8,41,-7", "-800,41,-7,42"]:
            with self.assertRaises(ValueError):
                geo.parse_bbox(box)

    def test_exact_boundary_not_extra_tile(self):
        self.assertEqual(geo.indexed_tiles((-9, 41, -8, 42)), [(-9, 41)])


if __name__ == "__main__":
    unittest.main()
