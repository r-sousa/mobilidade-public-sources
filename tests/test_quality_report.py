import json
import tempfile
import unittest
from pathlib import Path

from mn_public_acquisition.quality_report import build_report


class QualityReportTests(unittest.TestCase):
    def _root(self, rows, specs=None):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / "preserved_state").mkdir()
        (root / "source_specs").mkdir()
        (root / "preserved_state/index.json").write_text(
            json.dumps({"source_sets": rows}), encoding="utf-8"
        )
        for sid, adapter, sink in specs or []:
            lines = [
                "schema_version: 1.0.0",
                "source_set_id: " + sid,
                "title: test",
                "producer: test",
                "product_key: test::" + sid,
                "adapter: " + adapter,
                "access: public",
                "sink: " + sink,
                "cadence: annual",
                "expected_format: JSON",
                "source:",
                "  landing_url: https://example.test/",
                "raw_native:",
                "  geography: test",
                "  classification: test",
                "reuse:",
                "  status: not_verified",
                "  public_redistribution_gate: not_cleared",
                "",
            ]
            (root / "source_specs" / (sid + ".yml")).write_text(
                "\n".join(lines), encoding="utf-8"
            )
        return td, root

    def test_valid_state_action_contract_passes(self):
        rows = [{
            "source_set_id": "F01",
            "preservation_state": "PRIVATE_RELEASE_PRESENT",
            "default_action": "READ_PRIVATE_RELEASE_FIRST",
        }]
        td, root = self._root(rows, [("F01", "static_http", "private")])
        with td:
            report = build_report(root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["execution_plane"]["source_specs"], 1)

    def test_state_action_mismatch_fails(self):
        rows = [{
            "source_set_id": "F01",
            "preservation_state": "PRIVATE_RELEASE_PRESENT",
            "default_action": "PRIMARY_ALLOWED",
        }]
        td, root = self._root(rows)
        with td:
            report = build_report(root)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["errors"][0]["kind"], "state_action_mismatch")

    def test_duplicate_catalogue_id_fails(self):
        row = {
            "source_set_id": "F01",
            "preservation_state": "PUBLIC_RECOVERED",
            "default_action": "USE_PUBLIC_RECOVERED",
        }
        td, root = self._root([row, row])
        with td:
            report = build_report(root)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any(e["kind"] == "duplicate_source_set_id" for e in report["errors"])
        )


if __name__ == "__main__":
    unittest.main()
