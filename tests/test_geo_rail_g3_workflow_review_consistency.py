"""Regression against stale 20-group protected workflow preflight; no DGT auth."""
import pathlib,re,unittest
from unittest import mock

ROOT=pathlib.Path(__file__).resolve().parents[1]
FLOW=ROOT/".github/workflows/mn-geo-pt-g3-80-native-registered.yml"
SOURCE=ROOT/"tools/geo_rail_g3_native80.py"
class TestG3WorkflowPreflight(unittest.TestCase):
 def test_protected_workflow_uses_current_review_model(self):
  y=FLOW.read_text(encoding="utf8")
  self.assertIn("  workflow_dispatch:",y)
  self.assertNotIn("\n  push:",y)
  self.assertNotIn("\n  pull_request:",y)
  self.assertIn("environment: dgt-cdd",y)
  self.assertIn("github.ref == 'refs/heads/main'",y)
  self.assertIn("assert len(d)==sum(BATCHES.values())==19",y)
  self.assertIn('sum(len(g["tile_ids"]) for g in d)==76',y)
  self.assertIn('len({tid for g in d for tid in g["tile_ids"]})==76',y)
  self.assertNotIn("assert len(d)==20",y)
 def test_preflight_python_code_parses(self):
  y=FLOW.read_text(encoding="utf8")
  match=re.search(r"          python - <<'PY'\n(.*?)\n          PY",y,re.DOTALL)
  self.assertIsNotNone(match,"Protected workflow preflight code missing")
  code="\n".join(line[10:] if line.startswith("          ") else line
                 for line in match.group(1).splitlines())
  compile(code,"embedded_g3_protected_preflight.py","exec")
 def test_source_counts_consistent(self):
  # No requests to DGT. The test checks same import relied upon by workflow preflight.
  import sys
  sys.path.insert(0,str(ROOT/"tools"))
  import geo_rail_g3_native80 as m
  self.assertEqual(m.BATCHES,{"vila_real":7,"braganca":5,"regional":7})
  self.assertEqual(sum(m.BATCHES.values()),19)
  self.assertEqual(sum(m.BATCHES.values())*4,76)
  self.assertEqual(len(m.PRIOR_MIRANDELA_IDS),13)
if __name__=="__main__":unittest.main()
