import gzip
import json
import tempfile
import unittest
from pathlib import Path

from mn_public_acquisition.chunking import compose_json_record_pages
from mn_public_acquisition.ine_partitioned import _plan, _request_url, MAX_CELLS


class ChunkingTests(unittest.TestCase):
    def test_ine_plan_splits_above_40k_and_prefers_dim2(self):
        dims = {
            "Dim1": ["P1"],
            "Dim2": [f"G{i:03d}" for i in range(500)],
            "Dim3": [f"C{i:03d}" for i in range(100)],
        }
        plan = _plan("0012349", dims)
        self.assertGreaterEqual(len(plan), 2)
        self.assertTrue(all(
            len(x["Dim1"]) * len(x["Dim2"]) * len(x["Dim3"]) <= MAX_CELLS
            for x in plan
        ))
        self.assertTrue(all(len(x["Dim2"]) < len(dims["Dim2"]) for x in plan))

    def test_json_pages_recompose_exactly_once(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            payload = work / "payload"
            payload.mkdir()
            chunks = []
            for offset, rows in [(0, [{"id": 1}, {"id": 2}]), (2, [{"id": 3}])]:
                p = payload / f"records-{offset:06d}.json"
                p.write_text(json.dumps({"results": rows}), encoding="utf-8")
                import hashlib
                h = hashlib.sha256(p.read_bytes()).hexdigest()
                chunks.append({
                    "path": str(p.relative_to(work)),
                    "name": p.name,
                    "sha256": h,
                    "bytes": p.stat().st_size,
                    "source_url": f"https://example.test/?offset={offset}",
                    "format": "JSON",
                    "role": "native",
                })
            outputs = compose_json_record_pages(work, chunks)
            data = next(x for x in outputs if x["name"] == "records.jsonl.gz")
            with gzip.open(work / data["path"], "rt", encoding="utf-8") as f:
                ids = [json.loads(line)["id"] for line in f if line.strip()]
            self.assertEqual(ids, [1, 2, 3])
            self.assertEqual(data["role"], "recomposed")


if __name__ == "__main__":
    unittest.main()
