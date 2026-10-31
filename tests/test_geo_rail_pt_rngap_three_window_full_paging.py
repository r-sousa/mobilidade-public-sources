"""Tests of complete and bounded reviewed DGT RNGAP official WFS source pagination."""
import importlib.util
import sys
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("rngap_full",ROOT/"tools"/"geo_rail_pt_rngap_three_window_full_paging.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Contracts(unittest.TestCase):
 def test_three_requested_windows_and_100_feature_pages(self):
  self.assertEqual(len(m.SAMPLES),3)
  self.assertEqual(m.PAGE_SIZE,100)
  self.assertEqual(m.MAX_PAGES_PER_WINDOW,5)
  self.assertIn("startIndex=100",m.page_url(m.SAMPLES[0][1],100))
  with self.assertRaises(ValueError):m.page_url(m.SAMPLES[0][1],500)
  with self.assertRaises(ValueError):m.page_url([0,0,1,1],0)
 def test_parser_accepts_bounded_100_realistic_features(self):
  rows=[{"type":"Feature","id":f"RedeNivelamento.{i}",
      "geometry":{"type":"Point","coordinates":[80000+i*5,205000]},
      "properties":{"MARCA":f"R{i}","ALTH38":f"{250+i/100:.5f}"}} for i in range(100)]
  raw=json.dumps({"type":"FeatureCollection","features":rows,"numberMatched":145}).encode()
  parsed=m.parse_source_features(raw,m.SAMPLES[0][1],max_rows=100)
  self.assertEqual(parsed["valid_original_marks"],100)
  self.assertTrue(parsed["source_response_potentially_paged"])
 def test_unsafe_hundred_and_one_features_rejected(self):
  rows=[{"type":"Feature","id":str(i),"geometry":{"type":"Point","coordinates":[80000,205000]},
        "properties":{"MARCA":"X","ALTH38":"200.4"}} for i in range(101)]
  with self.assertRaises(ValueError):
   m.parse_source_features(json.dumps({"type":"FeatureCollection","features":rows}).encode(),
                           m.SAMPLES[0][1],max_rows=100)
if __name__=="__main__":unittest.main()
