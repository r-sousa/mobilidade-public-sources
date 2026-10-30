"""No-network tests for DGT W2 candidate-footprint inventory."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock
import unittest

path=Path(__file__).resolve().parents[1]/"tools"/"geo_rail_pt_stac_footprints.py"
spec=importlib.util.spec_from_file_location("w2footprints",path)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Response:
    status=200
    def __init__(self,payload):self.body=json.dumps(payload).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,size):return self.body


class W2FootprintTests(unittest.TestCase):
    def test_strips_signed_assets_and_unrestricted_properties(self):
        source={"type":"FeatureCollection","features":[{
          "type":"Feature","id":"MDT2-EXAMPLE","collection":"MDT-2m",
          "bbox":[-7.0,41.5,-6.99,41.51],
          "assets":{"tif":{"href":"https://example.org/secret?token=HIDDEN"}},
          "properties":{"authorization":"HIDDEN"}}],"links":[]}
        obj=m.summary(m.WINDOWS[2][1],"MDT-2m",source)
        self.assertEqual(obj["metadata_footprint_count"],1)
        self.assertNotIn("HIDDEN",json.dumps(obj))
        self.assertFalse(obj["has_next_page"])

    def test_pagination_cannot_claim_completeness(self):
        obj=m.summary(m.WINDOWS[0][1],"MDT-2m",
          {"type":"FeatureCollection","features":[],"links":[{"rel":"next","href":"?token=HIDDEN"}]})
        self.assertTrue(obj["has_next_page"])
        self.assertNotIn("HIDDEN",json.dumps(obj))

    def test_reject_disallowed_scope(self):
        with self.assertRaises(ValueError):
            m.inspect_window("not-a-site",[-7,41,-6,42],"MDT-2m")
        with self.assertRaises(ValueError):
            m.inspect_window(m.WINDOWS[0][0],m.WINDOWS[0][1],"LAZ")

    def test_requests_carry_no_user_credentials(self):
        def transport(req,timeout):
            self.assertIsNone(req.get_header("Authorization"))
            self.assertIsNone(req.get_header("Cookie"))
            return Response({"type":"FeatureCollection","features":[],"links":[]})
        x=m.inspect_window(*m.WINDOWS[0],"MDT-2m",transport=transport)
        self.assertEqual(x["status"],"metadata_returned_one_page")
        self.assertEqual(x["returned_count"],0)


if __name__=="__main__":unittest.main()
