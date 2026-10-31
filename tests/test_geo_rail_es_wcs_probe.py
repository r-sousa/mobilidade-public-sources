"""Synthetic fixtures for CNIG WCS metadata-only probe."""
import importlib.util
from pathlib import Path
import unittest

script = Path(__file__).resolve().parents[1] / "tools" / "geo_rail_es_wcs_probe.py"
spec = importlib.util.spec_from_file_location("geo_rail_es_wcs_probe", script)
geo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)

EXAMPLE = b'''<?xml version="1.0"?>
<wcs:Capabilities xmlns:wcs="http://www.opengis.net/wcs/2.0"
    xmlns:ows="http://www.opengis.net/ows/2.0">
  <ows:ServiceIdentification><ows:Title>MDT sample</ows:Title></ows:ServiceIdentification>
  <wcs:Contents><wcs:CoverageSummary><wcs:CoverageId>mdt25_test</wcs:CoverageId>
  </wcs:CoverageSummary></wcs:Contents>
</wcs:Capabilities>'''


class WCSProbeTests(unittest.TestCase):
    def test_wcs_capabilities_parse(self):
        info = geo.parse_wcs_capabilities(EXAMPLE)
        self.assertEqual(info["service_title"], "MDT sample")
        self.assertEqual(info["coverage_summary_count"], 1)
        self.assertEqual(info["coverage_ids"], ["mdt25_test"])

    def test_wcs_reject_non_capabilities(self):
        with self.assertRaises(ValueError):
            geo.parse_wcs_capabilities(b"<html/>")

    def test_network_response_receipt_does_not_claim_raster(self):
        class Reply:
            status = 200
            headers = {"Content-Type": "application/xml"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, limit):
                return EXAMPLE
        result = geo.probe(lambda req, timeout: Reply())
        self.assertEqual(result["status"], "capabilities_parsed")
        self.assertFalse(result["zamora_coverage_verified"])
        self.assertFalse(result["native_raster_acquired"])
        self.assertFalse(result["canonical_acceptance"])
        self.assertEqual(len(result["response_sha256"]), 64)

    def test_network_failure_is_reported_not_as_absence(self):
        def broken(req, timeout):
            raise OSError("connection down")
        result = geo.probe(broken)
        self.assertEqual(result["status"], "capabilities_unverified_error")
        self.assertFalse(result["zamora_coverage_verified"])


if __name__ == "__main__":
    unittest.main()
