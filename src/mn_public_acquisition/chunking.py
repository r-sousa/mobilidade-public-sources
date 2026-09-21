from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
from typing import Iterable


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def asset_record(path: Path, work: Path, *, name: str | None = None, fmt: str | None = None,
                 role: str = "recomposed", source_url: str | None = None) -> dict:
    return {
        "path": str(path.relative_to(work)),
        "name": name or path.name,
        "sha256": sha256_path(path),
        "bytes": path.stat().st_size,
        "format": fmt,
        "source_url": source_url,
        "role": role,
    }


def write_manifest(work: Path, *, adapter: str, chunks: list[dict], output_assets: list[dict],
                   row_count: int | None = None, feature_count: int | None = None,
                   completeness: str = "PASS") -> dict:
    out = work / "recomposed" / "composition-manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "adapter": adapter,
        "chunk_count": len(chunks),
        "chunks": [
            {
                "name": c["name"],
                "sha256": c["sha256"],
                "bytes": int(c["bytes"]),
                "source_url": c.get("source_url"),
            }
            for c in chunks
        ],
        "outputs": [
            {"name": a["name"], "sha256": a["sha256"], "bytes": int(a["bytes"]), "format": a.get("format")}
            for a in output_assets
        ],
        "row_count": row_count,
        "feature_count": feature_count,
        "completeness": completeness,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return asset_record(out, work, fmt="JSON", role="recomposed")


def compose_json_record_pages(work: Path, chunks: list[dict], *, results_key: str = "results") -> list[dict]:
    out = work / "recomposed" / "records.jsonl.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for chunk in chunks:
            obj = json.loads((work / chunk["path"]).read_text(encoding="utf-8-sig"))
            rows = obj.get(results_key) if isinstance(obj, dict) else None
            if not isinstance(rows, list):
                raise RuntimeError(f"Chunk {chunk['name']} has no list at {results_key!r}")
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                count += 1
    data = asset_record(out, work, fmt="JSONL.GZ", role="recomposed")
    manifest = write_manifest(work, adapter="json_pages", chunks=chunks, output_assets=[data], row_count=count)
    return [data, manifest]


def compose_geojson_pages(work: Path, chunks: list[dict]) -> list[dict]:
    out = work / "recomposed" / "features.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    features = []
    for chunk in chunks:
        obj = json.loads((work / chunk["path"]).read_text(encoding="utf-8-sig"))
        rows = obj.get("features") if isinstance(obj, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError(f"Chunk {chunk['name']} is not a GeoJSON FeatureCollection")
        features.extend(rows)
    payload = {"type": "FeatureCollection", "features": features}
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    data = asset_record(out, work, fmt="GeoJSON", role="recomposed")
    manifest = write_manifest(work, adapter="geojson_pages", chunks=chunks, output_assets=[data], feature_count=len(features))
    return [data, manifest]


def compose_ine_chunks(work: Path, chunks: list[dict], *, metadata_asset: dict | None = None) -> list[dict]:
    out = work / "recomposed" / "observations.jsonl.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    seen = set()
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for chunk in chunks:
            obj = json.loads((work / chunk["path"]).read_text(encoding="utf-8-sig"))
            rec = obj[0] if isinstance(obj, list) and obj and isinstance(obj[0], dict) else obj
            if not isinstance(rec, dict) or not isinstance(rec.get("Dados"), dict):
                raise RuntimeError(f"Chunk {chunk['name']} has no INE Dados object")
            for period, rows in rec["Dados"].items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    outrow = {"period": str(period), **row}
                    fp = hashlib.sha256(
                        json.dumps(outrow, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
                    if fp in seen:
                        continue
                    seen.add(fp)
                    f.write(json.dumps(outrow, ensure_ascii=False, separators=(",", ":")) + "\n")
                    count += 1
    data = asset_record(out, work, fmt="JSONL.GZ", role="recomposed")
    native_chunks = ([metadata_asset] if metadata_asset else []) + chunks
    manifest = write_manifest(work, adapter="ine_partitioned", chunks=native_chunks, output_assets=[data], row_count=count)
    return [data, manifest]


def series_manifest(work: Path, chunks: list[dict], *, series_key: str) -> list[dict]:
    out = work / "recomposed" / "series-manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "series_key": series_key,
        "chunk_count": len(chunks),
        "ordered_chunks": [
            {"name": c["name"], "sha256": c["sha256"], "bytes": int(c["bytes"]), "source_url": c.get("source_url")}
            for c in chunks
        ],
        "composition": "logical_series_manifest",
        "note": "Heterogeneous producer files are not row-concatenated unless an adapter-specific semantic assembler exists.",
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [asset_record(out, work, fmt="JSON", role="recomposed")]
