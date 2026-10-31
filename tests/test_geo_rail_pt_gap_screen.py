"""Offline contract tests for bounded DGT anonymous gap screening."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("dgt_gap",ROOT/"tools"/"geo_rail_pt_gap_screen.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Response:
    status=200
    def __init__(self,content):
        self.content=json.dumps(content).encode("utf-8")
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.content[:n]


def transport(request,timeout):
    assert timeout==30
    assert request.get_header("Authorization") is None
    assert request.get_header("Cookie") is None
    payload=json.loads(request.data)
    bbox=payload["bbox"]
    index=[w[1] for w in m.WINDOWS].index(bbox)
    collection=payload["collections"][0]
    feature={"type":"Feature","id":f"{collection}-SYN-{index}",
             "collection":collection,"bbox":bbox,
             "assets":{"data":{"href":"https://example.org?token=TOKEN_SHOULD_NOT_APPEAR"}}}
    return Response({"type":"FeatureCollection","features":[feature],"links":[]})


class GapReviewTests(unittest.TestCase):
    def test_ten_review_windows_and_two_products_each(self):
        self.assertEqual(len(m.WINDOWS),10)
        self.assertEqual(m.EXPECTED_QUERIES,20)
        self.assertEqual(m.WINDOWS[0][1][0],-7.75)
        self.assertEqual(m.WINDOWS[-1][1][2],-7.25)
        with self.assertRaisesRegex(ValueError,"out_of_review_scope"):
            m.inspect("malicious",[-10,40,-5,43],"MDT-2m",transport)

    def test_no_credentials_or_signed_asset_leak(self):
        out=m.run(transport)
        self.assertTrue(out["queries_all_complete"])
        self.assertEqual(out["query_count"],20)
        self.assertEqual(out["unique_candidate_ids_by_collection"],{"MDT-2m":10,"MDT-50cm":10})
        self.assertEqual(out["paired_candidate_id_suffixes"],10)
        self.assertEqual(out["paired_bboxes_equal"],10)
        self.assertNotIn("TOKEN_SHOULD_NOT_APPEAR",json.dumps(out))
        self.assertFalse(out["continuous_native_MDT_verified"])
        self.assertEqual(out["source_raster_bytes_transferred"],0)

    def test_partial_pagination_does_not_claim_completeness(self):
        def next_page(req,timeout):
            r=transport(req,timeout)
            d=json.loads(r.content)
            d["links"]=[{"rel":"next","href":"https://example.org?token=SENSITIVE"}]
            return Response(d)
        out=m.run(next_page)
        self.assertFalse(out["queries_all_complete"])
        self.assertIsNone(out["paired_candidate_id_suffixes"])
        self.assertIsNone(out["unique_candidate_ids_by_collection"])
        self.assertNotIn("SENSITIVE",json.dumps(out))

    def test_nonmatching_cross_window_bbox_is_rejected(self):
        rows=[m.inspect(name,bbox,product,transport) for name,bbox in m.WINDOWS for product in m.COLLECTIONS]
        rows[2]["footprints"][0]["tile_id"]=rows[0]["footprints"][0]["tile_id"]
        with self.assertRaisesRegex(ValueError,"conflicting_cross_window_bbox"):
            m.aggregate(rows)

    def test_reject_nonallowlisted_collection(self):
        with self.assertRaises(ValueError):
            m.inspect(*m.WINDOWS[0],collection="LAZ",transport=transport)


if __name__=="__main__":
    unittest.main()
