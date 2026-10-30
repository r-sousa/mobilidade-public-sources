"""CDD authenticated GitHub worker - security and bounded transport tests (offline)."""
from __future__ import annotations
import hashlib
import io
import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("dgt_auth",ROOT/"tools"/"geo_rail_pt_cdd_authenticated.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StubResponse:
    def __init__(self, url, status=200, headers=None, body=b""):
        self.url=url
        self.status_code=status
        self.headers=headers or {}
        self.body=body
        self.closed=False
        self.raw=StubRaw(body)

    def __enter__(self): return self

    def __exit__(self,*args): self.close()

    def close(self): self.closed=True

    def iter_content(self,chunk_size): 
        for i in range(0,len(self.body),chunk_size):
            yield self.body[i:i+chunk_size]


class StubRaw:
    def __init__(self,body):self.reader=io.BytesIO(body)
    def read(self,n,decode_content=False):return self.reader.read(n)


class StubSession:
    def __init__(self, replies):
        self.replies=list(replies)
        self.calls=[]

    def request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs))
        if not self.replies:raise RuntimeError("unexpected request")
        return self.replies.pop(0)


class SecurityTests(unittest.TestCase):
    def test_explicit_host_tls_no_userinfo_or_custom_ports(self):
        valid="https://cdd.dgterritorio.gov.pt/dgt-be/v1/anything?asset=SIGNED"
        self.assertTrue(m.allowed_url(valid,m.TRUSTED_DATA_REDIRECTS))
        for url in (
            "http://cdd.dgterritorio.gov.pt/data",
            "https://cdd.dgterritorio.gov.pt.attacker.invalid/data",
            "https://cdd.dgterritorio.gov.pt@attacker.invalid/data",
            "https://username:password@cdd.dgterritorio.gov.pt/data",
            "https://cdd.dgterritorio.gov.pt:8080/data",
            "https://evil.invalid/asset",
            "https://cdd.dgterritorio.gov.pt/data#fragment",
            "https://cdd.dgterritorio.gov.pt/data\\evil",
        ):
            self.assertFalse(m.allowed_url(url,m.TRUSTED_DATA_REDIRECTS),url)

    def test_redirect_outside_DGT_is_not_followed(self):
        uri="https://cdd.dgterritorio.gov.pt/data"
        res=StubResponse(uri,302,{"Location":"https://external.example/secret"})
        s=StubSession([res])
        with self.assertRaises(m.IntakeError) as err:
            m.request_bounded_redirects(s,"GET",uri,m.TRUSTED_DATA_REDIRECTS)
        self.assertEqual(err.exception.code,"unapproved_redirect_destination")
        self.assertEqual(len(s.calls),1)
        self.assertTrue(res.closed)

    def test_safe_same_host_redirect_succeeds(self):
        orig="https://cdd.dgterritorio.gov.pt/data"
        first=StubResponse(orig,302,{"Location":"/dl/item"})
        second=StubResponse("https://cdd.dgterritorio.gov.pt/dl/item",200,body=b"data")
        s=StubSession([first,second])
        ret=m.request_bounded_redirects(s,"GET",orig,m.TRUSTED_DATA_REDIRECTS)
        self.assertIs(ret,second)
        self.assertEqual([c[0] for c in s.calls],["GET","GET"])
        self.assertTrue(first.closed)

    def test_login_form_parser_extracts_only_hidden_fields(self):
        parser=m.KeycloakLoginForm()
        parser.feed("""<form id='kc-form-login' action='https://auth.cdd.dgterritorio.gov.pt/login'>
            <input type='hidden' name='execution' value='abc'>
            <input type='text' name='username'>
            <input type='password' name='password'>
            </form>""")
        self.assertEqual(parser.hidden,{"execution":"abc"})
        self.assertEqual(parser.action,"https://auth.cdd.dgterritorio.gov.pt/login")

    def test_native_data_download_only_tiff_and_one_budget(self):
        uri="https://cdd.dgterritorio.gov.pt/path/to/data.tif?token=HIDDEN"
        payload=b"II*\x00"+b"\x00"*1040
        res=StubResponse(uri,200,{"Content-Type":"image/tiff",
                                     "Content-Length":str(len(payload))},body=payload)
        s=StubSession([res])
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"untracked.tif"
            byte_count,digest=m.download_native(s,uri,p)
            self.assertEqual(byte_count,len(payload))
            self.assertEqual(digest,hashlib.sha256(payload).hexdigest())
            self.assertEqual(p.read_bytes(),payload)
        self.assertEqual(s.calls[0][0],"GET")
        self.assertFalse(s.calls[0][2]["allow_redirects"])
        self.assertTrue(s.calls[0][2]["stream"])
        self.assertNotIn("HIDDEN",repr((byte_count,digest)))

    def test_native_error_document_rejected_without_leaking_url(self):
        uri="https://cdd.dgterritorio.gov.pt/private/signed?secret=DO_NOT_LOG"
        s=StubSession([StubResponse(uri,200,{"Content-Type":"text/html"},
                                   b"<html>login</html>")])
        with TemporaryDirectory() as tmp:
            with self.assertRaises(m.IntakeError) as ctx:
                m.download_native(s,uri,Path(tmp)/"output.tif")
            self.assertEqual(ctx.exception.code,"native_response_is_html_or_api_error")
            self.assertNotIn("DO_NOT_LOG",str(ctx.exception))


if __name__=="__main__":
    unittest.main()
