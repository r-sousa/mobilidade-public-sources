"""Deterministic W3 transect tests; no network or rasters required."""
import importlib.util
from pathlib import Path
import sys
import unittest
from pyproj import Transformer

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("geo_rail_es_transect", TOOLS / "geo_rail_es_transect.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TransectTests(unittest.TestCase):
    def test_five_grounded_points_and_perimeters(self):
        self.assertEqual(len(mod.SITES), 5)
        proj = Transformer.from_crs(4326, 25830, always_xy=True)
        for name, lon, lat, ref in mod.SITES:
            self.assertTrue(ref.startswith("https://pares.cultura.gob.es/"))
            box = mod.tile_bbox_from_longlat(lon, lat, proj)
            self.assertEqual(box[2] - box[0], 1000)
            self.assertEqual(box[3] - box[1], 1000)
            self.assertTrue(box[0] % 25 == 0)
            self.assertTrue(box[1] % 25 == 0)
            for res in (5, 25):
                url = mod.build_coverage_url(res, box)
                self.assertIn(f"Elevacion25830_{res}", url)
                self.assertIn("GetCoverage", url)

    def test_reject_unreviewed_out_of_scope_requests(self):
        proj = Transformer.from_crs(4326, 25830, always_xy=True)
        with self.assertRaises(ValueError):
            mod.tile_bbox_from_longlat(-9, 42, proj)
        with self.assertRaises(ValueError):
            mod.build_coverage_url(2, [200000, 4600000, 201000, 4601000])
        with self.assertRaises(ValueError):
            mod.build_coverage_url(25, [200000, 4600000, 205000, 4605000])

    def test_response_size_limit(self):
        from geo_rail_es_wcs_sample import MAX_BYTES
        self.assertLessEqual(MAX_BYTES, 5_000_000)


if __name__ == "__main__":
    unittest.main()
