from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

VALID_ACTIONS = {
    "PUBLIC_RECOVERED": {"USE_PUBLIC_RECOVERED"},
    "PRIVATE_RELEASE_PRESENT": {"READ_PRIVATE_RELEASE_FIRST"},
    "MIDDLE_TIER_PRESENT": {"REVIEW_MIDDLE_TIER_FIRST"},
    "PRIVATE_RELEASE_ERROR_EVIDENCE": {
        "REVIEW_MIDDLE_TIER_FIRST",
        "PRIMARY_ALLOWED_AFTER_ERROR_EVIDENCE",
    },
    "NO_PRESERVED_DATA_ACKNOWLEDGED": {"PRIMARY_ALLOWED"},
    "REFERENCE_ONLY": {"NO_DATA_ACQUISITION"},
    "CONTROLLED_METADATA_ONLY": {"PRIVATE_CONTROLLED_LANE_ONLY"},
    "NO_AUTOMATIC_ACQUISITION": {"NO_DATA_ACQUISITION"},
}


def _load_index(root: Path) -> dict:
    path = root / "preserved_state" / "index.json"
    if not path.is_file():
        raise RuntimeError("preserved_state/index.json is missing")
    return json.loads(path.read_text(encoding="utf-8"))


def _source_specs(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "source_specs").glob("*.y*ml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        rows.append({
            "source_set_id": spec["source_set_id"],
            "adapter": spec["adapter"],
            "sink": spec["sink"],
            "access": spec["access"],
            "path": str(path.relative_to(root)),
        })
    return rows


def _receipt_counts(root: Path, dirname: str) -> dict[str, int]:
    base = root / dirname
    if not base.is_dir():
        return {}
    out = {}
    for child in sorted(base.iterdir()):
        if child.is_dir() and child.name.startswith("F"):
            out[child.name] = sum(1 for p in child.rglob("*.json") if p.is_file())
    return out


def build_report(root: Path = ROOT) -> dict:
    idx = _load_index(root)
    rows = idx.get("source_sets") or []
    errors = []

    ids = [r.get("source_set_id") for r in rows]
    duplicates = sorted(k for k, v in Counter(ids).items() if k and v > 1)
    if duplicates:
        errors.append({"kind": "duplicate_source_set_id", "ids": duplicates})

    for row in rows:
        state = row.get("preservation_state")
        action = row.get("default_action")
        allowed = VALID_ACTIONS.get(state)
        if allowed is None:
            errors.append({
                "kind": "unknown_preservation_state",
                "source_set_id": row.get("source_set_id"),
                "state": state,
            })
        elif action not in allowed:
            errors.append({
                "kind": "state_action_mismatch",
                "source_set_id": row.get("source_set_id"),
                "state": state,
                "action": action,
                "allowed": sorted(allowed),
            })

    specs = _source_specs(root)
    spec_ids = [x["source_set_id"] for x in specs]
    duplicate_specs = sorted(k for k, v in Counter(spec_ids).items() if v > 1)
    if duplicate_specs:
        errors.append({"kind": "duplicate_spec_id", "ids": duplicate_specs})

    indexed = {r.get("source_set_id"): r for r in rows}
    for spec in specs:
        if spec["source_set_id"] not in indexed:
            errors.append({
                "kind": "spec_without_preserved_state_entry",
                "source_set_id": spec["source_set_id"],
            })

    receipts = _receipt_counts(root, "receipts")
    compositions = _receipt_counts(root, "composition_receipts")
    state_counts = Counter(r.get("preservation_state") for r in rows)
    adapter_counts = Counter(x["adapter"] for x in specs)
    sink_counts = Counter(x["sink"] for x in specs)

    specs_by_state = Counter(
        indexed.get(x["source_set_id"], {}).get("preservation_state", "UNINDEXED")
        for x in specs
    )

    evidence_by_source = defaultdict(
        lambda: {"native_receipts": 0, "composition_receipts": 0}
    )
    for sid, n in receipts.items():
        evidence_by_source[sid]["native_receipts"] = n
    for sid, n in compositions.items():
        evidence_by_source[sid]["composition_receipts"] = n

    return {
        "schema_version": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "catalogue": {
            "source_sets": len(rows),
            "preservation_states": dict(sorted(state_counts.items())),
        },
        "execution_plane": {
            "source_specs": len(specs),
            "adapters": dict(sorted(adapter_counts.items())),
            "sinks": dict(sorted(sink_counts.items())),
            "specs_by_preservation_state": dict(sorted(specs_by_state.items())),
        },
        "evidence": {
            "source_sets_with_native_receipts": len(receipts),
            "native_receipt_files": sum(receipts.values()),
            "source_sets_with_composition_receipts": len(compositions),
            "composition_receipt_files": sum(compositions.values()),
            "by_source_set": dict(sorted(evidence_by_source.items())),
        },
        "interpretation": {
            "catalogue_coverage_is_not_acquisition_completeness": True,
            "source_spec_presence_means_execution_route_exists_not_that_source_is_complete": True,
            "receipt_presence_means_acquisition_evidence_exists_not_canonical_acceptance": True,
        },
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# Public acquisition quality report",
        "",
        "Status: **%s**" % report["status"],
        "",
        "## Catalogue",
        "",
        "- Source sets acknowledged: %s" % report["catalogue"]["source_sets"],
    ]
    for k, v in report["catalogue"]["preservation_states"].items():
        lines.append("- %s: %s" % (k, v))

    lines += [
        "",
        "## Execution plane",
        "",
        "- Source specs: %s" % report["execution_plane"]["source_specs"],
    ]
    for k, v in report["execution_plane"]["adapters"].items():
        lines.append("- Adapter %s: %s spec(s)" % (k, v))

    lines += [
        "",
        "## Evidence",
        "",
        "- Source sets with native receipts: %s" % report["evidence"]["source_sets_with_native_receipts"],
        "- Native receipt files: %s" % report["evidence"]["native_receipt_files"],
        "- Source sets with composition receipts: %s" % report["evidence"]["source_sets_with_composition_receipts"],
        "- Composition receipt files: %s" % report["evidence"]["composition_receipt_files"],
        "",
        "Receipt/spec counts are execution evidence only; they do not imply canonical acceptance, reuse clearance or consumer readiness.",
    ]

    if report["errors"]:
        lines += ["", "## Errors", ""]
        for err in report["errors"]:
            lines.append("- " + json.dumps(err, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--markdown-out", type=Path)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    report = build_report(args.root)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(to_markdown(report), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.check and report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
