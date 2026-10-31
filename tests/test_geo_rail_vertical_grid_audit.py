"""Deterministic W4 metadata/allowlist tests, without geoid downloads."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

path=Path(__file__).resolve().parents[1]/"tools"/"geo_rail_vertical_grid_audit.py"
spec=importlib.util.spec_from_file_location("geo_rail_vertical_grid_audit",path)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class GridAuditTests(unittest.TestCase):
    def test_two_exact_public_grid_names(self):
        self.assertEqual(m.GRIDS,("pt_dgt_GeodPT08.tif","es_ign_egm08-rednap.tif"))
        self.assertEqual(m.ORIGIN,"https://cdn.proj.org")
        self.assertLessEqual(m.MAX_EACH_BYTES,20_000_000)

    def test_reject_unreviewed_grid_without_network(self):
        with self.assertRaises(ValueError):
            m.transfer_grid("some-other-grid.tif",Path("/tmp"),opener=Mock())

    def test_summarize_missing_grids(self):
        class Grid:
            short_name="pt_dgt_GeodPT08.tif"
            available=False
            url="https://cdn.proj.org/pt_dgt_GeodPT08.tif"
            open_license=True
        group=Mock(best_available=False,transformers=[],unavailable_operations=[
            Mock(name="missing grid",accuracy=0.09,grids=[Grid()])])
        summary=m.summarize_group(group)
        self.assertFalse(summary["best_available"])
        self.assertFalse(summary["unavailable_operations"][0]["grids"][0]["available"])


if __name__=="__main__":
    unittest.main()
