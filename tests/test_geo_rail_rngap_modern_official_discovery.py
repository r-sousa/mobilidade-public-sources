"""Contracts for metadata-only current official RNGAP discovery."""
import importlib.util
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("rngap_modern",ROOT/"tools"/"geo_rail_rngap_modern_official_discovery.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Contracts(unittest.TestCase):
    def test_explicit_four_current_official_sources(self):
        self.assertEqual(len(m.PROBES),4)
        self.assertTrue(all(v["url"].startswith("https://") for v in m.PROBES.values()))
        self.assertLessEqual(m.MAX_BYTES,1_000_000)
    def test_reject_wrong_source_host_without_call(self):
        with self.assertRaises(ValueError):
            m._bounded("https://untrusted.example/a","www.dgterritorio.gov.pt",lambda x:None)
    def test_no_survey_values_from_catalogue_metadata(self):
        data=b'{"title":"RNGAP","resources":[{"id":"x","title":"Leveling network","format":"WFS","url":"https://untrusted.test/api"}]}'
        x=m.extract_catalogue(data)
        self.assertEqual(x["metadata_resource_count"],1)
        self.assertFalse(x["potential_official_catalogue_resources"][0]["url_in_allowlisted_official_host"])
        self.assertFalse(x["potential_official_catalogue_resources"][0]["candidate_attribute_heights_verified"])
    def test_failed_fetch_does_not_claim_absent_marks(self):
        class Offline:
            def __call__(self,*args,**kwargs):raise OSError("offline")
        x=m.inspect(opener=Offline())
        self.assertEqual(x["metadata_sources_HTTP_200"],0)
        self.assertEqual(x["RNGAP_official_Cascais_altitudes_collected"],0)
        self.assertTrue(x["unverified_web_service_not_evidence_of_missing_marks"])
if __name__=="__main__": unittest.main()
