"""Offline contract tests for DGT native GeoTIFF release preservation, no secrets."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location(
    "dgt_persist",ROOT/"tools"/"geo_rail_pt_cdd_preserve_manifest.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def safe_receipt(sha,size):
    return {
        "status":"native_tiff_authenticated_and_validated_pilot",
        "producer_tile_id":"MDT-2m-282510-09-2024",
        "collection":"MDT-2m",
        "diagnostic_site":"mirandela",
        "native_staged_for_reviewed_public_release":True,
        "native_file_bytes":size,"native_sha256":sha,
        "raster":{
            "horizontal_crs":"EPSG:3763","resolution_m":[2.0,2.0],
            "width_px":500,"height_px":500,"valid_pixels":250000,
            "bbox_intersects_source_proxy":True
        }
    }


class PublicReleaseContractTests(unittest.TestCase):
    def test_successful_pinned_bytes_writes_ccby_manifest_without_secret(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);native=root/"native.tif";qa=root/"qa.json"
            raw=b"II*\x00"+b"\x00"*1024
            sha=hashlib.sha256(raw).hexdigest()
            native.write_bytes(raw)
            qa.write_text(json.dumps(safe_receipt(sha,len(raw))))
            with patch.object(m,"EXPECTED_SHA",sha),patch.object(m,"EXPECTED_BYTES",len(raw)):
                result=m.verify_and_prepare(native,qa,root/"release")
            manifest=json.loads((root/"release"/m.MANIFEST_NAME).read_text())
            self.assertEqual(result["sha256"],sha)
            self.assertEqual(manifest["original_native_sha256"],sha)
            self.assertEqual(manifest["original_native_bytes"],len(raw))
            self.assertIn("CC BY 4.0",manifest["source_license"])
            self.assertFalse(manifest["canonical_Fxx_accepted"])
            self.assertFalse(manifest["site_publication_authorized"])
            self.assertNotIn("password",str(manifest).lower())
            self.assertNotIn("cookie",str(manifest).lower())

    def test_mutated_native_bytes_refused_before_publishing(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);native=root/"native.tif";qa=root/"qa.json"
            original=b"II*\x00"+b"\x00"*1024
            native.write_bytes(original+b"corrupt")
            sha=hashlib.sha256(original).hexdigest()
            qa.write_text(json.dumps(safe_receipt(sha,len(original))))
            with patch.object(m,"EXPECTED_SHA",sha),patch.object(m,"EXPECTED_BYTES",len(original)):
                with self.assertRaisesRegex(ValueError,"not_identical"):
                    m.verify_and_prepare(native,qa,root/"release")
            self.assertFalse((root/"release").exists())

    def test_unreviewed_tile_refused(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);native=root/"native.tif";qa=root/"qa.json"
            b=b"II*\x00"+b"\x00"*1024
            native.write_bytes(b)
            sha=hashlib.sha256(b).hexdigest()
            rec=safe_receipt(sha,len(b));rec["producer_tile_id"]="MDT-2m-OTHER"
            qa.write_text(json.dumps(rec))
            with patch.object(m,"EXPECTED_SHA",sha),patch.object(m,"EXPECTED_BYTES",len(b)):
                with self.assertRaisesRegex(ValueError,"not_approved"):
                    m.verify_and_prepare(native,qa,root/"release")

    def test_manual_protected_release_workflow_constrains_source(self):
        y=(ROOT/".github/workflows/mn-geo-pt-cdd-registered.yml").read_text()
        self.assertIn("workflow_dispatch:",y)
        self.assertIn("needs: verify-protected-main",y)
        self.assertIn("environment: dgt-cdd",y)
        self.assertIn("permissions:\n  contents: write",y)
        self.assertIn("if: inputs.preserve_native == true && inputs.site == 'mirandela'",y)
        self.assertIn("--retain-verified-native",y)
        self.assertIn("tools/geo_rail_pt_cdd_preserve_manifest.py",y)
        self.assertIn("gh release create",y)
        self.assertIn("--prerelease",y)
        self.assertIn("gh release download",y)
        self.assertIn('sha256sum "$root/existing-release-check/$filename"',y)
        self.assertNotIn("--clobber",y)
        self.assertNotIn("pull_request_target:",y)


if __name__=="__main__":
    unittest.main()
