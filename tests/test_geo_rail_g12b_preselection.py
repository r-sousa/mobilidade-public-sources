"""G12B no-gis source decision Pareto and equality-safe technical test."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from geo_rail_g12b_evidence_gated_preselection import pareto,evidence_gates
class TestG12B(unittest.TestCase):
 def test_dominated_not_selected(self):
  rows=[{"research_combination":"A","len":12,"pressure":.3,"P90":80},
        {"research_combination":"B","len":15,"pressure":.4,"P90":100},
        {"research_combination":"C","len":13,"pressure":.2,"P90":75}]
  out=pareto(rows,("len","pressure","P90"))
  self.assertEqual(out,["A","C"])
 def test_gates_explicit_missing_evidence(self):
  t=evidence_gates()
  self.assertEqual(len(t),5)
  self.assertTrue(any("F67" in x["upstream_source"] for x in t))
  self.assertTrue(any("CAPEX" in x["domain"] for x in t))
if __name__=="__main__":unittest.main()
