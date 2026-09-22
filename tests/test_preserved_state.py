import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mn_public_acquisition import preserved_state


class PreservedStateTests(unittest.TestCase):
    def _index(self, action, state="TEST_STATE"):
        td = tempfile.TemporaryDirectory()
        path = Path(td.name) / "index.json"
        path.write_text(
            json.dumps({
                "source_sets": [{
                    "source_set_id": "F999",
                    "preservation_state": state,
                    "default_action": action,
                    "release_count": 1,
                    "runtime_overlay_count": 2,
                    "canonical_authority": "r-sousa/EU-transp-weekly",
                }]
            }),
            encoding="utf-8",
        )
        return td, path

    def test_private_release_skips_primary_by_default(self):
        td, path = self._index("READ_PRIVATE_RELEASE_FIRST", "PRIVATE_RELEASE_PRESENT")
        with td, patch.object(preserved_state, "INDEX", path):
            d = preserved_state.primary_decision("F999")
        self.assertEqual(d["decision"], "SKIP_PRIMARY_USE_PRESERVED_FIRST")

    def test_middle_tier_skips_primary_by_default(self):
        td, path = self._index("REVIEW_MIDDLE_TIER_FIRST", "MIDDLE_TIER_PRESENT")
        with td, patch.object(preserved_state, "INDEX", path):
            d = preserved_state.primary_decision("F999")
        self.assertEqual(d["decision"], "SKIP_PRIMARY_USE_PRESERVED_FIRST")

    def test_explicit_review_override_allows_repair(self):
        td, path = self._index("READ_PRIVATE_RELEASE_FIRST", "PRIVATE_RELEASE_PRESENT")
        with td, patch.object(preserved_state, "INDEX", path):
            d = preserved_state.primary_decision("F999", force_primary=True)
        self.assertEqual(d["decision"], "ALLOW_PRIMARY_EXPLICIT_OVERRIDE")

    def test_controlled_lane_cannot_be_force_overridden(self):
        td, path = self._index("PRIVATE_CONTROLLED_LANE_ONLY", "CONTROLLED_METADATA_ONLY")
        with td, patch.object(preserved_state, "INDEX", path):
            d = preserved_state.primary_decision("F999", force_primary=True)
        self.assertEqual(d["decision"], "BLOCK_PRIMARY")

    def test_reference_only_cannot_be_force_overridden(self):
        td, path = self._index("NO_DATA_ACQUISITION", "REFERENCE_ONLY")
        with td, patch.object(preserved_state, "INDEX", path):
            d = preserved_state.primary_decision("F999", force_primary=True)
        self.assertEqual(d["decision"], "BLOCK_PRIMARY")

    def test_primary_allowed_remains_allowed(self):
        td, path = self._index("PRIMARY_ALLOWED", "NO_PRESERVED_DATA_ACKNOWLEDGED")
        with td, patch.object(preserved_state, "INDEX", path):
            d = preserved_state.primary_decision("F999")
        self.assertEqual(d["decision"], "ALLOW_PRIMARY")


if __name__ == "__main__":
    unittest.main()
