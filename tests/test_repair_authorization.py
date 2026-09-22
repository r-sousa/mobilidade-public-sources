import base64
import json
import os
import unittest
from unittest.mock import Mock, patch

from mn_public_acquisition import repair_authorization


class RepairAuthorizationTests(unittest.TestCase):
    def _response(self, payload):
        raw = json.dumps(payload).encode("utf-8")
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "content": base64.b64encode(raw).decode("ascii"),
            "sha": "blob-sha",
        }
        return response

    def _valid(self):
        return {
            "decision": "AUTHORISED_PRIMARY_REPAIR_AFTER_PRESERVED_STATE_REVIEW",
            "source_set_ids": ["F999"],
            "execution": {
                "plane": "r-sousa/mobilidade-public-sources",
                "sink": "private",
            },
            "publication": "NO_PUBLICATION_AUTHORISED_BY_THIS_OBJECT",
        }

    @patch.dict(os.environ, {
        "MN_PRIVATE_SINK_TOKEN": "not-a-real-token",
        "GITHUB_REPOSITORY": "r-sousa/mobilidade-public-sources",
    }, clear=False)
    @patch("mn_public_acquisition.repair_authorization.requests.get")
    def test_valid_pinned_authorization_passes(self, get):
        get.return_value = self._response(self._valid())
        result = repair_authorization.verify("F999", "path/auth.json", "commit-sha")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["authorization_ref"], "commit-sha")

    @patch.dict(os.environ, {
        "MN_PRIVATE_SINK_TOKEN": "not-a-real-token",
        "GITHUB_REPOSITORY": "r-sousa/mobilidade-public-sources",
    }, clear=False)
    @patch("mn_public_acquisition.repair_authorization.requests.get")
    def test_unlisted_source_is_rejected(self, get):
        payload = self._valid()
        payload["source_set_ids"] = ["F998"]
        get.return_value = self._response(payload)
        with self.assertRaisesRegex(RuntimeError, "NOT_LISTED"):
            repair_authorization.verify("F999", "path/auth.json", "commit-sha")

    @patch.dict(os.environ, {
        "MN_PRIVATE_SINK_TOKEN": "not-a-real-token",
        "GITHUB_REPOSITORY": "r-sousa/mobilidade-public-sources",
    }, clear=False)
    @patch("mn_public_acquisition.repair_authorization.requests.get")
    def test_publication_permission_is_rejected(self, get):
        payload = self._valid()
        payload["publication"] = "PUBLICATION_ALLOWED"
        get.return_value = self._response(payload)
        with self.assertRaisesRegex(RuntimeError, "PUBLICATION_GUARD"):
            repair_authorization.verify("F999", "path/auth.json", "commit-sha")

    @patch.dict(os.environ, {
        "MN_PRIVATE_SINK_TOKEN": "not-a-real-token",
        "GITHUB_REPOSITORY": "r-sousa/mobilidade-public-sources",
    }, clear=False)
    @patch("mn_public_acquisition.repair_authorization.requests.get")
    def test_non_private_sink_authorization_is_rejected(self, get):
        payload = self._valid()
        payload["execution"]["sink"] = "public_release"
        get.return_value = self._response(payload)
        with self.assertRaisesRegex(RuntimeError, "PRIVATE_SINK"):
            repair_authorization.verify("F999", "path/auth.json", "commit-sha")


if __name__ == "__main__":
    unittest.main()
