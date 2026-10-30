"""No-network security tests for anonymous DGT native-asset HEAD preflight."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

p=Path(__file__).resolve().parents[1]/"tools"/"geo_rail_pt_asset_preflight.py"
spec=importlib.util.spec_from_file_location("dgt_access",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AssetPreflightSafetyTests(unittest.TestCase):
    def test_signed_or_offhost_links_never_requested_or_exposed(self):
        signed="https://cdd.dgterritorio.gov.pt/data/secret.tif?X-Amz-Signature=PRIVATE"
        evil="https://other.example/data/secret.tif"
        with patch.object(m,"build_opener") as op:
            a=m.anonymous_head_if_safe(signed)
            b=m.anonymous_head_if_safe(evil)
        op.assert_not_called()
        self.assertEqual(a["status"],"query_or_credentials_in_link_not_sent")
        self.assertEqual(b["status"],"host_or_scheme_not_approved")
        self.assertNotIn("PRIVATE",repr(a))
        self.assertNotIn("secret.tif",repr(a))
        self.assertNotIn("secret.tif",repr(b))

    def test_successful_head_never_downloads_body(self):
        class Reply:
            status=200
            headers={"Content-Length":"6400000","Content-Type":"image/tiff"}
            def __enter__(self):return self
            def __exit__(self,*args):pass
        class Opener:
            def open(self, req, timeout):
                self.req=req
                return Reply()
        o=Opener()
        a=m.anonymous_head_if_safe("https://cdd.dgterritorio.gov.pt/open/object.tif",o)
        self.assertEqual(o.req.get_method(),"HEAD")
        self.assertEqual(a["status"],"anonymous_head_200")
        self.assertEqual(a["native_bytes_downloaded"],0)
        self.assertEqual(a["content_length_bytes"],6400000)
        self.assertNotIn("object.tif",repr(a))

    def test_restricted_status_classified_without_implying_absent(self):
        class Opener:
            def open(self,req,timeout):
                raise HTTPError(req.full_url,403,"forbidden",{},None)
        a=m.anonymous_head_if_safe("https://cdd.dgterritorio.gov.pt/data.tif",Opener())
        self.assertEqual(a["status"],"anonymous_head_access_denied")

    def test_unfollowed_redirect(self):
        class Opener:
            def open(self,req,timeout):
                raise HTTPError(req.full_url,302,"redirect",{"Location":"https://s3.amazonaws.com/something?token=SECRET"},None)
        a=m.anonymous_head_if_safe("https://cdd.dgterritorio.gov.pt/redirect",Opener())
        self.assertEqual(a["status"],"redirect_not_followed")
        self.assertEqual(a["redirect_target_host"],"s3.amazonaws.com")
        self.assertNotIn("SECRET",repr(a))


if __name__=="__main__":unittest.main()
