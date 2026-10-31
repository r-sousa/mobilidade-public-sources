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


    def test_failure_receipt_is_parseable_json_without_secrets(self):
        import json
        import contextlib
        import os
        from unittest.mock import patch
        with TemporaryDirectory() as tmp:
            receipt=Path(tmp)/"receipt.json"
            index=Path(tmp)/"index.geojson"
            index.write_text('{"type":"FeatureCollection","features":[]}',encoding="utf-8")
            argv=["prog","--site","mirandela","--index",str(index),
                  "--receipt",str(receipt)]
            with patch("sys.argv",argv),patch.dict(os.environ,{},clear=True):
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        m.main()
            data=json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(data["safe_error_code"],"environment_secrets_not_set")
            self.assertEqual(data["status"],"acquisition_or_native_quality_not_verified")
            self.assertNotIn("password",json.dumps(data).lower())



    def test_production_workflow_requires_branch_protection_and_manual_environment(self):
        y=(ROOT/".github/workflows/mn-geo-pt-cdd-registered.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:",y)
        self.assertNotIn("\\n  push:",y)
        self.assertNotIn("\\n  pull_request:",y)
        self.assertIn("verify-protected-main:",y)
        self.assertIn("needs: verify-protected-main",y)
        self.assertIn("if [[ \"$protected\" != \"true\" ]]",y)
        self.assertIn("environment: dgt-cdd",y)
        self.assertIn("github.ref == 'refs/heads/main'",y)
        self.assertIn("secrets.DGT_CDD_USERNAME",y)
        self.assertIn("secrets.DGT_CDD_PASSWORD",y)
        self.assertIn("persist-credentials: false",y)



    def test_unapproved_redirect_reports_only_phase_and_domain_class(self):
        uri="https://auth.cdd.dgterritorio.gov.pt/realms/dgterritorio/login-actions"
        secret="PRIVATE_CREDENTIALS_AND_QUERY_SHOULD_NOT_BE_SAVED"
        redirect=(
            "https://unknown.example.invalid/login?code="+secret+
            "&session_state="+secret
        )
        s=StubSession([StubResponse(uri,302,{"Location":redirect})])
        with self.assertRaises(m.IntakeError) as ctx:
            m.request_bounded_redirects(s,"POST",uri,m.TRUSTED_AUTH_REDIRECTS,
                                        form={"username":"HIDDEN","password":secret},
                                        phase="keycloak_credentials_submission")
        failure=ctx.exception
        self.assertEqual(failure.code,"unapproved_redirect_destination")
        self.assertEqual(failure.phase,"keycloak_credentials_submission")
        self.assertEqual(failure.redirect["redirect_hostname_class"],
                         "outside_DGT_hostname_allowlist")
        import json
        sanitized=json.dumps(failure.redirect)
        self.assertNotIn(secret,sanitized)
        self.assertNotIn("code=",sanitized)
        self.assertNotIn("session_state",sanitized)
        self.assertNotIn("HIDDEN",sanitized)
        self.assertEqual(len(s.calls),1)

    def test_official_unlisted_domain_reported_without_path_or_query(self):
        diagnostic=m.sanitized_redirect_diagnostic(
            "https://files.cdd.dgterritorio.gov.pt:8081/dl?key=SECRET")
        self.assertEqual(diagnostic["redirect_hostname_class"],
                         "files.cdd.dgterritorio.gov.pt")
        self.assertEqual(diagnostic["redirect_port"],8081)
        self.assertEqual(diagnostic["redirect_scheme_class"],"https")
        self.assertNotIn("SECRET",str(diagnostic))
        self.assertNotIn("/dl",str(diagnostic))

    def test_invalid_redirect_location_cannot_be_silently_followed(self):
        origin="https://cdd.dgterritorio.gov.pt/data"
        response=StubResponse(origin,302,
                              {"Location":"http://cdd.dgterritorio.gov.pt/non-https"})
        s=StubSession([response])
        with self.assertRaises(m.IntakeError) as ctx:
            m.request_bounded_redirects(s,"GET",origin,m.TRUSTED_DATA_REDIRECTS,
                                        phase="native_geotiff_download")
        self.assertEqual(ctx.exception.redirect["redirect_scheme_class"],"http")
        self.assertEqual(ctx.exception.redirect["redirect_hostname_class"],
                         "cdd.dgterritorio.gov.pt")
        self.assertTrue(response.closed)
        self.assertEqual(len(s.calls),1)


    def test_single_DGT_issued_https_9000_hop_uses_isolated_cookie_free_session(self):
        from unittest.mock import MagicMock,patch
        uri="https://cdd.dgterritorio.gov.pt/private/file"
        signed="https://storage.public-example.net:9000/some/object?signature=NEVER_LOG_THIS"
        payload=b"II*\\x00"+b"\\x00"*1032
        first=StubResponse(uri,302,{"Location":signed})
        cdd=StubSession([first])
        remote=MagicMock()
        remote.request.return_value=StubResponse(signed,200,
            {"Content-Type":"image/tiff","Content-Length":str(len(payload))},
            payload)
        with patch.object(m,"verified_public_storage_endpoint",return_value=True) as guard:
            with patch("requests.Session",return_value=remote):
                with TemporaryDirectory() as tmp:
                    count,_=m.download_native(cdd,uri,Path(tmp)/"native.tif")
        self.assertEqual(count,len(payload))
        guard.assert_called_once_with(signed)
        remote.headers.clear.assert_called()
        remote.cookies.clear.assert_called()
        remote.close.assert_called()
        sent=remote.request.call_args
        self.assertEqual(sent.args,("GET",signed))
        self.assertFalse(sent.kwargs["allow_redirects"])
        self.assertNotIn("Authorization",sent.kwargs["headers"])
        self.assertNotIn("Cookie",sent.kwargs["headers"])
        self.assertTrue(first.closed)

    def test_external_storage_must_not_follow_second_redirect(self):
        from unittest.mock import MagicMock,patch
        uri="https://cdd.dgterritorio.gov.pt/assets/one"
        signed="https://storage.public-example.net:9000/part?sig=SECRET"
        initial=StubSession([StubResponse(uri,302,{"Location":signed})])
        external=MagicMock()
        external.request.return_value=StubResponse(signed,302,{"Location":"https://elsewhere.net/file"})
        with patch.object(m,"verified_public_storage_endpoint",return_value=True):
            with patch("requests.Session",return_value=external):
                with TemporaryDirectory() as tmp:
                    with self.assertRaises(m.IntakeError) as e:
                        m.download_native(initial,uri,Path(tmp)/"native.tif")
        self.assertEqual(e.exception.code,"storage_second_redirect_not_allowed")
        self.assertNotIn("SECRET",str(e.exception))
        external.close.assert_called()

    def test_https_9000_storage_host_rejects_private_dns_and_untrusted_ports(self):
        valid="https://example-public-storage.net:9000/obj?token=SECRET"
        def public_dns(host,port,proto):
            return [(2,1,6,"",("93.184.216.34",port))]
        def private_dns(host,port,proto):
            return [(2,1,6,"",("10.0.0.5",port))]
        self.assertTrue(m.verified_public_storage_endpoint(valid,dns_lookup=public_dns))
        self.assertFalse(m.verified_public_storage_endpoint(valid,dns_lookup=private_dns))
        self.assertFalse(m.verified_public_storage_endpoint(
            valid.replace(":9000",":8081"),dns_lookup=public_dns))
        self.assertFalse(m.verified_public_storage_endpoint(
            valid.replace("https:", "http:"),dns_lookup=public_dns))
        self.assertFalse(m.verified_public_storage_endpoint(
            "https://127.0.0.1:9000/private",dns_lookup=public_dns))
        self.assertFalse(m.verified_public_storage_endpoint(
            "https://169.254.169.254:9000/metadata",dns_lookup=public_dns))
        self.assertFalse(m.verified_public_storage_endpoint(
            "https://foo.local:9000/object",dns_lookup=public_dns))

    def test_reject_unapproved_storage_hop_without_request(self):
        from unittest.mock import patch
        uri="https://cdd.dgterritorio.gov.pt/assets/x"
        redirected="https://untrusted.example.org:9000/file?secret=HIDDEN"
        cdd=StubSession([StubResponse(uri,302,{"Location":redirected})])
        with patch.object(m,"verified_public_storage_endpoint",return_value=False):
            with TemporaryDirectory() as tmp:
                with self.assertRaises(m.IntakeError) as e:
                    m.download_native(cdd,uri,Path(tmp)/"native.tif")
        self.assertEqual(e.exception.code,"unapproved_redirect_destination")
        self.assertEqual(e.exception.phase,"native_geotiff_download")
        self.assertEqual(len(cdd.calls),1)
        self.assertNotIn("HIDDEN",str(e.exception))


if __name__=="__main__":
    unittest.main()
