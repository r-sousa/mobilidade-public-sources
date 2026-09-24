from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mn_public_acquisition.core import load_spec
from mn_public_acquisition.spec_packages import materialize_to_dir


ROOT = Path(__file__).resolve().parents[1]


class F195PackageTests(unittest.TestCase):
    def test_f195_materializes_exactly_five_bounded_private_ine_specs(self):
        expected = [
            ("F195-0014076-2025", "0014076", 2025),
            ("F195-0014077-2025", "0014077", 2025),
            ("F195-0014078-2025", "0014078", 2025),
            ("F195-0014450-2023", "0014450", 2023),
            ("F195-0012984-2024", "0012984", 2024),
        ]
        package = ROOT / "source_packages" / "F195.yml"
        with tempfile.TemporaryDirectory() as td:
            manifest = materialize_to_dir(package, Path(td))
            self.assertEqual(manifest["source_set_id"], "F195")
            self.assertEqual(
                manifest["product_key"],
                "ine.pt::icor-eu-silc::condicoes-vida-rendimento",
            )
            self.assertEqual(manifest["member_count"], 5)
            self.assertFalse(manifest["producer_contacted"])

            actual = []
            product_keys = set()
            for member in manifest["members"]:
                spec = load_spec(Path(member["spec_path"]))
                params = spec["parameters"]
                actual.append(
                    (
                        params["execution_request_identity"],
                        params["indicator"],
                        params["year"],
                    )
                )
                product_keys.add(spec["product_key"])
                self.assertEqual(spec["source_set_id"], "F195")
                self.assertEqual(spec["adapter"], "ine_json")
                self.assertEqual(spec["access"], "public")
                self.assertEqual(spec["sink"], "private")
                self.assertNotIn("members", params)
                self.assertRegex(params["indicator"], r"^[0-9]{7}$")
                self.assertIsInstance(params["year"], int)

            self.assertEqual(actual, expected)
            self.assertEqual(
                product_keys,
                {"ine.pt::icor-eu-silc::condicoes-vida-rendimento"},
            )


if __name__ == "__main__":
    unittest.main()
