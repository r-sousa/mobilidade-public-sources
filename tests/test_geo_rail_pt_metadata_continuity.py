"""Offline controls for metadata-only DGT W2 bounding-box audit."""
import copy
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "geo_rail_pt_metadata_continuity.py"
spec = importlib.util.spec_from_file_location("dgt_bbox_review", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

WINDOWS = (
    ("E01_east_north", [-6.90, 41.78, -6.80, 41.88]),
    ("E02_east_south", [-6.92, 41.52, -6.82, 41.62]),
    ("E03_macedo_sector", [-7.08, 41.48, -6.98, 41.58]),
    ("E04_mirandela_sector", [-7.25, 41.45, -7.15, 41.55]),
    ("E05_vila_real_sector", [-7.85, 41.25, -7.75, 41.35]),
    ("E06_amarante_sector", [-8.15, 41.22, -8.05, 41.32]),
)


def fixture():
    rows = []
    for index, (site, window) in enumerate(WINDOWS):
        w, s, e, n = window
        rect = [w, s, (w + e) / 2, (s + n) / 2]
        for source in ("MDT-2m", "MDT-50cm"):
            rows.append({
                "box_id": site, "collection": source,
                "status": "metadata_returned_one_page",
                "has_next_page": False, "http_status": 200,
                "query_bbox_wgs84": window,
                "metadata_footprint_count": 1,
                "footprints": [{
                    "tile_id": f"{source}-{index:06d}-TEST",
                    "bbox_wgs84": rect.copy(), "bbox_method": "source_bbox",
                    "collection": source,
                }],
            })
    return {"mission": "MN-GEO-RAIL-001", "requests": rows,
            "observed_utc": "2026-10-30T22:43:49Z"}


class DgtMetaAuditTests(unittest.TestCase):
    def test_exact_union_with_overlap(self):
        self.assertEqual(
            m.rectangle_union_fraction([0, 0, 2, 2],
                                       [[0, 0, 2, 1], [0, 0, 1, 2]]), 0.75
        )

    def test_no_metadata_proxies_become_raster_evidence(self):
        out = m.audit(fixture(), "sha-mock")
        self.assertEqual(out["input_complete_queries"], 12)
        self.assertEqual(out["candidate_positions_paired_across_resolutions"], 6)
        self.assertTrue(all(x["window_bbox_proxy_union_fraction"] == .25
                            for x in out["sectors"]))
        self.assertFalse(out["full_corridor_coverage_verified"])
        self.assertFalse(out["valid_raster_pixel_coverage_measured"])
        self.assertFalse(out["canonical_Fxx_accepted"])
        self.assertEqual(len(out["unsampled_window_separations"]), 5)

    def test_pair_mismatch_fails_closed(self):
        rec = fixture()
        rec["requests"][1]["footprints"][0]["bbox_wgs84"][2] -= .001
        with self.assertRaisesRegex(ValueError, "pairing_differs"):
            m.audit(rec, "mock")

    def test_incomplete_stac_page_fails_closed(self):
        rec = fixture()
        rec["requests"][0]["has_next_page"] = True
        with self.assertRaisesRegex(ValueError, "incomplete_or_failed"):
            m.audit(rec, "mock")

    def test_rejects_duplicated_and_mismatched_queries(self):
        rec = fixture()
        rec["requests"][0] = copy.deepcopy(rec["requests"][1])
        with self.assertRaisesRegex(ValueError, "unreviewed_or_duplicate"):
            m.audit(rec, "mock")

    def test_rejects_invalid_or_secret_bearing_tile_identifiers(self):
        rec = fixture()
        rec["requests"][0]["footprints"][0]["tile_id"] = "https://example.org/file?token=secret"
        with self.assertRaisesRegex(ValueError, "unexpected_tile_id"):
            m.audit(rec, "mock")

    def test_rejects_invalid_wgs84_bbox_and_float_nan(self):
        with self.assertRaises(ValueError):
            m.bbox([110000, 200000, 111000, 201000])
        with self.assertRaises(ValueError):
            m.bbox([-7, float("nan"), -6.9, 41.4])


if __name__ == "__main__":
    unittest.main()
