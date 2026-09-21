from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "preserved_state" / "index.json"

BLOCK_PRIMARY = {
    "USE_PUBLIC_RECOVERED",
    "READ_PRIVATE_RELEASE_FIRST",
    "REVIEW_MIDDLE_TIER_FIRST",
    "NO_DATA_ACQUISITION",
    "PRIVATE_CONTROLLED_LANE_ONLY",
}
NEVER_FORCE = {
    "NO_DATA_ACQUISITION",
    "PRIVATE_CONTROLLED_LANE_ONLY",
}


def load_index() -> dict:
    if not INDEX.is_file():
        return {"source_sets": []}
    return json.loads(INDEX.read_text(encoding="utf-8"))


def lookup(source_set_id: str) -> dict | None:
    for row in load_index().get("source_sets") or []:
        if row.get("source_set_id") == source_set_id:
            return row
    return None


def primary_decision(source_set_id: str, *, force_primary: bool = False) -> dict:
    row = lookup(source_set_id)
    if row is None:
        return {
            "source_set_id": source_set_id,
            "preservation_state": "UNACKNOWLEDGED",
            "default_action": "PRIMARY_ALLOWED",
            "decision": "ALLOW_PRIMARY",
            "reason": "NO_PRESERVED_STATE_ENTRY",
        }

    action = row.get("default_action") or "PRIMARY_ALLOWED"
    if action in NEVER_FORCE:
        decision = "BLOCK_PRIMARY"
        reason = action
    elif action in BLOCK_PRIMARY and not force_primary:
        decision = "SKIP_PRIMARY_USE_PRESERVED_FIRST"
        reason = action
    elif action in BLOCK_PRIMARY and force_primary:
        decision = "ALLOW_PRIMARY_EXPLICIT_OVERRIDE"
        reason = "EXPLICIT_FORCE_PRIMARY_AFTER_PRESERVATION_REVIEW"
    else:
        decision = "ALLOW_PRIMARY"
        reason = action

    return {
        "source_set_id": source_set_id,
        "preservation_state": row.get("preservation_state"),
        "default_action": action,
        "decision": decision,
        "reason": reason,
        "release_count": row.get("release_count", 0),
        "runtime_overlay_count": row.get("runtime_overlay_count", 0),
        "private_locator": row.get("private_locator"),
        "canonical_authority": row.get("canonical_authority"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_set_id")
    ap.add_argument("--force-primary", action="store_true")
    args = ap.parse_args()
    result = primary_decision(args.source_set_id, force_primary=args.force_primary)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["decision"] == "BLOCK_PRIMARY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
