"""Original DGT RNGAP ALTH38 mark source constraints, no network."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("rngap_src",ROOT/"tools"/"geo_rail_pt_rngap_alh38_source_sample.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class TestSource(unittest.TestCase):
 def test_valid_sample_point(self):
  b=m.SAMPLES[0][1]
  feature={"type":"Feature","id":"RGN.RedeNivelamento.123",
    "geometry":{"type":"Point","coordinates":[82000,205000]},
    "properties":{"MARCA":"M1","ALTH38":225.375,"LIN_SEC":"a"}}
  j=json.dumps({"type":"FeatureCollection","features":[feature],"numberMatched":1}).encode()
  out=m.parse_source_features(j,b)
  self.assertEqual(out["valid_original_marks"],1)
  self.assertEqual(out["observations_validated"][0]["DGT_original_ALTH38_height_m"],225.375)
  self.assertTrue(out["observations_validated"][0]["source_mark_physical_quality_not_verified"])
 def test_decimal_comma_text_converts_but_original_preserved(self):
  b=m.SAMPLES[0][1]
  feature={"type":"Feature","id":"RGN.RedeNivelamento.501",
   "geometry":{"type":"Point","coordinates":[82000,205000]},
   "properties":{"MARCA":"M501","ALTH38":" 225,375 "}}
  j=json.dumps({"type":"FeatureCollection","features":[feature]}).encode()
  result=m.parse_source_features(j,b)
  self.assertEqual(result["valid_original_marks"],1)
  height=result["observations_validated"][0]
  self.assertEqual(height["DGT_original_ALTH38_height_m"],225.375)
  self.assertEqual(height["DGT_ALTH38_original_source_value"]," 225,375 ")
  self.assertTrue(height["source_original_height_was_text"])
  self.assertIsNone(m.normalize_original_ALTH38("225 metres"))
  self.assertIsNone(m.normalize_original_ALTH38("2.225,500"))
  self.assertIsNone(m.normalize_original_ALTH38("NaN"))
 def test_no_numeric_height_not_claimed(self):
  b=m.SAMPLES[0][1]
  feature={"type":"Feature","id":"f1","geometry":{"type":"Point","coordinates":[82000,205000]},
           "properties":{"MARCA":"A","ALTH38":"invalid"}}
  j=json.dumps({"type":"FeatureCollection","features":[feature]}).encode()
  out=m.parse_source_features(j,b)
  self.assertEqual(out["valid_original_marks"],0)
  self.assertEqual(out["invalid_records"][0]["reason"],"non_numeric_or_out_of_range_ALTH38")
 def test_unsafe_request_geometry_blocked(self):
  with self.assertRaises(ValueError):
   m.feature_url("https://geo2.dgterritorio.gov.pt/geoserver/RGN/ows",[0,0,100000,300000])
 def test_non_point_not_benchmark(self):
  b=m.SAMPLES[0][1]
  f={"type":"Feature","id":"f1","geometry":{"type":"LineString","coordinates":[[82000,205000],[83000,205000]]},
   "properties":{"MARCA":"A","ALTH38":225}}
  x=m.parse_source_features(json.dumps({"type":"FeatureCollection","features":[f]}).encode(),b)
  self.assertEqual(x["valid_original_marks"],0)
  self.assertEqual(x["invalid_records"][0]["geometry_type"],"LineString")
 def test_fail_closed_without_network(self):
  def no(*a,**k):raise OSError("offline")
  x=m.run(opener=no)
  self.assertEqual(x["unique_source_mark_count"],0)
  self.assertFalse(x["independent_PT_ES_height_datum_harmonized"])
if __name__=="__main__":unittest.main()
