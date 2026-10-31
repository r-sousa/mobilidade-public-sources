"""No-secrets source-constrained DGT WFS/WMS GetCapabilities probe tests."""
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("rngap",ROOT/"tools"/"geo_rail_pt_rngap_service_probe.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class DGTServiceProbeContracts(unittest.TestCase):
    def test_only_three_official_source_metadata_queries(self):
        self.assertEqual(len(m.APPROVED),3)
        self.assertTrue(all(m.capabilities_url(s,v).startswith(m.BASE+"?")
                            for _,s,v in m.APPROVED))
        with self.assertRaises(ValueError):
            m.capabilities_url("WFS","3.0.0")
        with self.assertRaises(ValueError):
            m.bounded_fetch("https://untrusted.example/geodesy?service=WFS")

    def test_wfs_caps_parse_with_explicit_no_attribute_claim(self):
        xml=b'''<WFS_Capabilities><FeatureTypeList><FeatureType>
              <Name>geodesy:rngap_signals</Name><Title>Marcas de Nivelamento</Title>
              </FeatureType><FeatureType><Name>other:parcels</Name>
              <Title>Parcels</Title></FeatureType></FeatureTypeList></WFS_Capabilities>'''
        out=m.parse_layers(xml)
        self.assertEqual(out["total_named_layers"],2)
        self.assertEqual(out["geodesy_candidate_layer_count"],1)
        self.assertIn("rngap",out["geodesy_keyword_matching_layers"][0]["name"])
        self.assertFalse(out["altitude_attribute_schema_checked"])

    def test_reject_html_or_exception_reply_not_OGC(self):
        for txt in (b"<html><body>error</body></html>",
                    b"<ExceptionReport><Exception>x</Exception></ExceptionReport>"):
            with self.assertRaisesRegex(ValueError,"not_OGC_capabilities"):
                m.parse_layers(txt)

    def test_no_mark_acquisition_or_absence_claim_on_network_failure(self):
        def fake_fetch(request,timeout=1):
            raise OSError("network unavailable")
        out=m.run(opener=fake_fetch)
        self.assertEqual(out["successful_valid_OGC_service_responses"],0)
        self.assertEqual(out["Portuguese_RNGAP_mark_coordinates_acquired"],0)
        self.assertFalse(out["absence_of_RNGAP_marks_inferred_from_failed_probe"])
        self.assertFalse(out["crossborder_benchmark_validation_complete"])

if __name__=="__main__":
    unittest.main()
