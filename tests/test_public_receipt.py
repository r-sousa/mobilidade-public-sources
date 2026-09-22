import unittest

from mn_public_acquisition.public_receipt import (
    _public_view,
    same_source_object,
)


class PublicReceiptTests(unittest.TestCase):
    def _receipt(self):
        return {
            "source_set_id": "F999",
            "native_asset_fingerprint": "abc123",
            "sink": "private",
            "assets": [
                {
                    "name": "native.json",
                    "sha256": "n1",
                    "bytes": 10,
                    "format": "JSON",
                    "source_url": "https://producer.example/native.json",
                    "role": "native",
                },
                {
                    "name": "derived.jsonl.gz",
                    "sha256": "d1",
                    "bytes": 5,
                    "format": "JSONL.GZ",
                    "source_url": None,
                    "role": "recomposed",
                },
            ],
            "disposition": {
                "status": "PRIVATE_SINK_PRESERVED",
                "bytes_persisted": True,
                "release_url": "https://github.com/private/release",
                "assets": [{"url": "https://github.com/private/download"}],
                "private_receipt": {"path": "private/path.json"},
            },
        }

    def test_recomposition_does_not_change_source_object_identity(self):
        a = self._receipt()
        b = self._receipt()
        b["assets"][1]["sha256"] = "different-derived-output"
        b["assets"][1]["bytes"] = 999
        self.assertTrue(same_source_object(a, b))

    def test_native_change_changes_source_object_identity(self):
        a = self._receipt()
        b = self._receipt()
        b["assets"][0]["sha256"] = "different-native"
        self.assertFalse(same_source_object(a, b))

    def test_public_view_redacts_private_release_details(self):
        view = _public_view(self._receipt())
        disposition = view["disposition"]
        self.assertEqual(disposition["status"], "PRIVATE_SINK_PRESERVED")
        self.assertTrue(disposition["bytes_persisted"])
        self.assertTrue(disposition["private_receipt_written"])
        self.assertNotIn("release_url", disposition)
        self.assertNotIn("assets", disposition)

    def test_probe_private_view_reports_no_persistence(self):
        receipt = self._receipt()
        receipt["disposition"] = {
            "status": "PROBE_ONLY_NO_PERSISTENCE",
            "bytes_persisted": False,
        }
        view = _public_view(receipt)
        self.assertEqual(view["disposition"]["status"], "PROBE_ONLY_NO_PERSISTENCE")
        self.assertFalse(view["disposition"]["bytes_persisted"])


if __name__ == "__main__":
    unittest.main()
