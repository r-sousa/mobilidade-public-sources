"""Bounded IGN REDNAP mark ingestion, source and height controls (no secrets)."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("rednap",ROOT/"tools"/"geo_rail_rednap_bounded_api.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def marker(lon,lat,mid,h=650.0,H=595.0):
    return {"type":"Feature","id":mid,
            "geometry":{"type":"Point","coordinates":[lon,lat]},
            "properties":{"numero":mid,"nombre":f"NAPA-{mid}","nombre_muni":"Alcañices",
                 "nombre_prov":"Zamora","tipo":"Principal","latitud_etrs89":lat,
                 "longitud_etrs89":lon,"ortometrica":H,"altitud_elipsoidal":h,
                 "resena":"https://datos-geodesia.ign.es/REDNAP/Lin/mark.pdf"}}

class ContractTests(unittest.TestCase):
    def test_only_reviewed_queries(self):
        self.assertEqual(len(m.WINDOWS),3)
        self.assertEqual(m.MAX_PAGES_PER_WINDOW,4)
        self.assertIn("api-features.ign.es",m.query_url(m.WINDOWS[0][1],0))
        with self.assertRaisesRegex(ValueError,"unreviewed_RED_NAP_bbox"):
            m.query_url((-7,41,-6,42),0)
        with self.assertRaisesRegex(ValueError,"unreviewed_RED_NAP_pagination"):
            m.query_url(m.WINDOWS[0][1],900)

    def test_mark_well_formed_and_pair_provenance(self):
        r=m.parse_public_signal(marker(-6.4,41.70,123),m.WINDOWS[1][1])
        self.assertEqual(r["producer_id"],"123")
        self.assertEqual(r["ellipsoidal_minus_orthometric_m"],55)
        self.assertTrue(r["both_heights_published"])
        self.assertNotIn("resena",r) # No PDF links or bulk source identifiers unnecessary for spatial QA.
        self.assertEqual(r["original_source"],"IGN REDNAP OGC API-Features public survey mark")

    def test_missing_official_ID_remains_null_with_local_dedup_key(self):
        row=marker(-6.4,41.70,123)
        del row["id"]
        del row["properties"]["numero"]
        out=m.parse_public_signal(row,m.WINDOWS[1][1])
        self.assertIsNone(out["producer_id"])
        self.assertFalse(out["official_source_id_available"])
        self.assertTrue(out["local_deduplication_key"].startswith("local_no_official_id_sha256:"))
        self.assertEqual(out["local_deduplication_key"],
                         m.parse_public_signal(row,m.WINDOWS[1][1])["local_deduplication_key"])

    def test_height_missing_is_not_invented(self):
        row=marker(-5.75,41.5,321,h=None)
        r=m.parse_public_signal(row,m.WINDOWS[2][1])
        self.assertFalse(r["both_heights_published"])
        self.assertNotIn("ellipsoidal_minus_orthometric_m",r)

    def test_out_of_bounds_and_outlying_height_rejected(self):
        with self.assertRaisesRegex(ValueError,"outside_requested_bbox"):
            m.parse_public_signal(marker(-5.75,41.5,123),m.WINDOWS[1][1])
        with self.assertRaisesRegex(ValueError,"implausible_RED_NAP"):
            m.parse_public_signal(marker(-6.4,41.7,125,h=2000),m.WINDOWS[1][1])

    def test_bounded_mocked_original_api_three_windows(self):
        def fake(query,opener=None):
            from urllib.parse import parse_qs,urlsplit
            q=parse_qs(urlsplit(query).query)
            bbox=tuple(map(float,q["bbox"][0].split(",")))
            lon=(bbox[0]+bbox[2])/2;lat=(bbox[1]+bbox[3])/2
            index=[w[1] for w in m.WINDOWS].index(bbox)
            return {"type":"FeatureCollection","numberMatched":1,
                    "features":[marker(lon,lat,index+1)]},{"sha256":"a"*64,"bytes":200}
        old=m.bounded_query
        try:
            m.bounded_query=fake
            out=m.run()
        finally:
            m.bounded_query=old
        self.assertTrue(out["source_fully_retrieved_in_all_windows"])
        self.assertEqual(out["queries_successful"],3)
        self.assertEqual(out["distinct_survey_mark_candidates"],3)
        self.assertEqual(out["distinct_marks_with_both_heights"],3)
        self.assertFalse(out["independent_geoid_holdout_data"])
        self.assertFalse(out["cross_border_harmonization_validated"])

if __name__=="__main__":
    unittest.main()
