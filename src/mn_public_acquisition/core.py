from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import jsonschema
import yaml

from .adapters import acquire
from .sinks import disposition

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "source-spec.schema.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_spec(path: Path) -> dict:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(spec)
    if spec["access"] != "public":
        raise ValueError(
            "Controlled/authenticated sources are metadata-only here and cannot execute on the public runner"
        )
    return spec


def fingerprint(records: list[dict]) -> str:
    material = [
        {"name": r["name"], "sha256": r["sha256"], "bytes": int(r["bytes"])}
        for r in sorted(records, key=lambda x: x["name"])
    ]
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def run(spec_path: Path) -> dict:
    spec = load_spec(spec_path)
    with tempfile.TemporaryDirectory(prefix=f"mn-{spec['source_set_id']}-") as td:
        work = Path(td)
        result = acquire(spec, work)
        records = result["assets"]
        if not records:
            raise RuntimeError("Acquisition produced no native source assets")
        for r in records:
            p = work / r["path"]
            if not p.is_file():
                raise RuntimeError(f"Missing acquired file: {r['path']}")
            actual = sha256_file(p)
            if actual != r["sha256"] or p.stat().st_size != int(r["bytes"]):
                raise RuntimeError(f"Local integrity mismatch: {r['name']}")
        fp = fingerprint(records)
        receipt = {
            "schema_version": "1.0.0",
            "source_set_id": spec["source_set_id"],
            "title": spec["title"],
            "producer": spec["producer"],
            "product_key": spec["product_key"],
            "source_url": spec["source"]["landing_url"],
            "adapter": spec["adapter"],
            "access": spec["access"],
            "sink": spec["sink"],
            "cadence": spec["cadence"],
            "expected_format": spec["expected_format"],
            "raw_native": spec["raw_native"],
            "reuse": spec["reuse"],
            "acquisition_timestamp": result["acquired_at"],
            "source_period_or_edition": result.get("source_period_or_edition"),
            "validation_result": result["validation_result"],
            "assets": [
                {
                    "name": r["name"],
                    "sha256": r["sha256"],
                    "bytes": r["bytes"],
                    "format": r.get("format"),
                    "source_url": r.get("source_url")
                }
                for r in records
            ],
            "native_asset_fingerprint": fp,
            "acquisition_code_commit": os.environ.get("GITHUB_SHA", "local"),
            "limitations": result.get("limitations"),
            "reuse_disposition": "NO_CANONICAL_RIGHTS_STATE_CHANGE"
        }
        receipt["disposition"] = disposition(spec, work, records, receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return receipt


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("spec", type=Path)
    args = p.parse_args()
    run(args.spec)


if __name__ == "__main__":
    main()
