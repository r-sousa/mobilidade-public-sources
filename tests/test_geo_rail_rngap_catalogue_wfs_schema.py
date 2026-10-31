"""Official RNGAP exact catalogued WFS metadata-only contract tests."""
import importlib.util
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("rngap_wfs",ROOT/"tools"/"geo_rail_rngap_catalogue_wfs_schema.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_catalogue_exact_WFS_resource_only(self):
  data=b'{"resources":[{"id":"wfs-1","format":"wfs","title":"Rede de Nivelamento Geometrico de Alta Precisao RNGAP","url":"http://geo2.dgterritorio.gov.pt/geoserver/rngap/wfs"}]}'
  base,source=m.resource_wfs_url(data)
  self.assertEqual(base,"https://geo2.dgterritorio.gov.pt/geoserver/rngap/wfs")
  self.assertTrue(source["HTTPS_probed_on_same_DGT_host_and_path"])
 def test_wrong_host_and_getfeature_disallowed(self):
  data=b'{"resources":[{"id":"x","format":"wfs","title":"RNGAP","url":"https://evil.invalid/steal"}]}'
  with self.assertRaises(ValueError):m.resource_wfs_url(data)
  with self.assertRaises(ValueError):m.query("https://geo2.dgterritorio.gov.pt/wfs","WFS","GetFeature","2.0.0")
 def test_parse_GML_WFS_capabilities(self):
  xml=b'<WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0"><FeatureTypeList><FeatureType><Name>rngap:marcas</Name><Title>RNGAP nivelamento</Title></FeatureType><FeatureType><Name>aux:ruas</Name></FeatureType></FeatureTypeList></WFS_Capabilities>'
  out=m.parse_capabilities(xml)
  self.assertEqual(len(out["candidate_RNGAP_layers"]),1)
  self.assertEqual(out["total_layer_count"],2)
 def test_schema_field_names_are_not_height_values(self):
  xml=b'<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"><xsd:complexType name="m"><xsd:sequence><xsd:element name="ID"/><xsd:element name="ALTITUDE"/><xsd:element name="GEOM"/></xsd:sequence></xsd:complexType></xsd:schema>'
  x=m.parse_xsd_schema(xml)
  self.assertIn("ALTITUDE",x["possible_height_field_names"])
  self.assertFalse(x["schema_has_verified_numeric_height_VALUES"])
 def test_no_data_on_network_failure(self):
  def offline(*a,**k):raise OSError("offline")
  x=m.run(opener=offline)
  self.assertEqual(x["DGT_actual_survey_marks_retrieved"],0)
  self.assertFalse(x["crossborder_datum_validated"])
if __name__=="__main__":unittest.main()
