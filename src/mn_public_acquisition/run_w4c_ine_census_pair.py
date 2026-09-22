from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml

from .extract_w4c_ine_census_pair_v3 import run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    read_token = os.environ.get("MN_PRIVATE_READ_TOKEN", "") or os.environ.get("MN_PRIVATE_SINK_TOKEN", "")
    write_token = os.environ.get("MN_PRIVATE_SINK_TOKEN", "")
    if not read_token or not write_token:
        raise SystemExit("MN_PRIVATE_READ_AND_SINK_TOKEN_REQUIRED")
    try:
        result = run(cfg, read_token, write_token)
    except Exception as exc:
        result = {"schema_version": "4.1.0", "complete": False, "error": str(exc)}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
