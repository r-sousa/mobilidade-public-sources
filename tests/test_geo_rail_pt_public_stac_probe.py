"""Unit tests of W2 DGT public probe — no live HTTP calls."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import json
import unittest

path = Path(__file__).resolve().parents[1] / "tools/geo_rail_pt_public_stac_probe.py"
spec = importlib.util.spec_from_file_location("geo_rail_pt_public_stac_probe", path)
geo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)


class DummyResponse:
    status = 200
    def __init__(self, obj):
        self.data = json.dumps(obj).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, limit): return self.data


class DgtSafetyTests(unittest.TestCase):
    def test_public_search_never_logs_asset_urls_or_credentials(self):
        sample = {"features": [{"collection": "MDT-2m", "assets": {
            "download": {"href": "https://example.org/?token=SENSITIVE"}}}]}
        with patch.object(geo, "urlopen", return_value=DummyResponse(sample)) as fake:
            a = geo.call_api("POST", "/search",
                             {"bbox": geo.SEARCH_BBOX, "limit": 1})
        self.assertEqual(a["returned_features_count"], 1)
        self.assertNotIn("SENSITIVE", json.dumps(a))
        request = fake.call_args.args[0]
        self.assertNotIn("Authorization", request.headers)
        self.assertNotIn("Cookie", request.headers)

    def test_denied_access_does_not_assert_zero_coverage(self):
        with patch.object(geo, "urlopen", side_effect=HTTPError(
                geo.BASE + "/search", 401, "unauthorized", {}, None)):
            a = geo.call_api("POST", "/search", {"limit": 1})
        self.assertEqual(a["status"], "unauthenticated_access_denied")
        self.assertIsNone(a["returned_features_count"])

    def test_collection_list_is_reduced_to_ids(self):
        with patch.object(geo, "urlopen", return_value=DummyResponse({
                "collections": [{"id": "MDT-2m", "links": [{
                    "href": "https://private.example?session=SENSITIVE"}]}]})):
            a = geo.call_api("GET", "/collections")
        self.assertEqual(a["collection_ids"], ["MDT-2m"])
        self.assertNotIn("SENSITIVE", json.dumps(a))


if __name__ == "__main__": unittest.main()
