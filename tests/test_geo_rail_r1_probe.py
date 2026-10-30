"""Remote probe unit tests use fixtures; never issue network calls."""
import importlib.util
from pathlib import Path
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
spec = importlib.util.spec_from_file_location("geo_rail_r1_probe", TOOLS / "geo_rail_r1_probe.py")
import sys
sys.path.insert(0, str(TOOLS))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.sample = "Copernicus_DSM_COG_10_N41_00_W009_00_DEM"
        self.metadata = {"sha256": "a" * 64, "url": probe.TILE_LIST,
                         "byte_count": 100, "listed_tiles_global": 100}

    def test_listed_head_receipt_not_validated_as_raster(self):
        result = probe.run((-9, 41, -8, 42), {self.sample}, self.metadata,
                           head_probe=lambda _: {"head_state": "object_reported_not_validated",
                                                  "head_http_status": 200,
                                                  "content_length_bytes": 12_000_000})
        self.assertEqual(result["metadata"]["head_status_counts"],
                         {"object_reported_not_validated": 1})
        self.assertEqual(result["metadata"]["native_raster_bytes_downloaded"], 0)
        self.assertFalse(result["metadata"]["is_coverage_verified"])
        self.assertFalse(result["features"][0]["properties"]["native_raster_validated"])
        self.assertFalse(result["features"][0]["properties"]["canonical_acceptance"])

    def test_unlisted_tile_is_not_network_probed(self):
        def explode(_):
            raise AssertionError("Must not network probe a tile absent from producer list")
        result = probe.run((-9, 41, -8, 42), set(), self.metadata, explode)
        self.assertEqual(result["metadata"]["head_status_counts"], {"not_probed": 1})
        self.assertEqual(result["features"][0]["properties"]["discovery_status"],
                         "not_in_supplied_list")

    def test_no_fake_coverage_on_head_error(self):
        result = probe.run((-9, 41, -8, 42), {self.sample}, self.metadata,
                           head_probe=lambda _: {"head_state": "head_failed",
                                                  "head_http_status": 403})
        self.assertFalse(result["metadata"]["is_coverage_verified"])
        self.assertEqual(result["features"][0]["properties"]["head_http_status"], 403)

    def test_reject_arbitrary_tile_in_direct_probe(self):
        with self.assertRaises(ValueError):
            probe.probe_head("../../somewhere")


if __name__ == "__main__":
    unittest.main()
