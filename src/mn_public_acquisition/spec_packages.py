from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path

import yaml

FXX_RE = re.compile(r"^F[0-9]{2,4}$")
INDICATOR_RE = re.compile(r"^[0-9]{7}$")


def _need(obj: dict, key: str):
    if key not in obj:
        raise ValueError(f"Package missing required field: {key}")
    return obj[key]


def load_package(path: Path) -> dict:
    package = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(package, dict):
        raise ValueError("Package must be a YAML object")

    if _need(package, "schema_version") != "1.0.0":
        raise ValueError("Unsupported package schema_version")
    sid = str(_need(package, "source_set_id"))
    if not FXX_RE.fullmatch(sid):
        raise ValueError(f"Invalid source_set_id: {sid!r}")
    if _need(package, "adapter") != "ine_json":
        raise ValueError("Package materializer only supports native ine_json members")
    if _need(package, "access") != "public":
        raise ValueError("Only public producer requests may be packaged")
    if _need(package, "sink") != "private":
        raise ValueError("Packaged requests must preserve bytes in the private sink")

    for key in (
        "title",
        "producer",
        "product_key",
        "cadence",
        "expected_format",
        "source",
        "raw_native",
        "reuse",
    ):
        _need(package, key)

    members = _need(package, "members")
    if not isinstance(members, list) or not members:
        raise ValueError("members must be a non-empty list")

    seen_requests: set[str] = set()
    seen_indicator_year: set[tuple[str, int]] = set()
    for member in members:
        if not isinstance(member, dict):
            raise ValueError("Each package member must be an object")
        request_identity = str(_need(member, "request_identity"))
        indicator = str(_need(member, "indicator")).zfill(7)
        year = int(_need(member, "year"))
        landing_url = str(_need(member, "landing_url"))
        if not request_identity or request_identity in seen_requests:
            raise ValueError(f"Duplicate/empty request_identity: {request_identity!r}")
        if not INDICATOR_RE.fullmatch(indicator):
            raise ValueError(f"Invalid INE indicator: {indicator!r}")
        if not (1900 <= year <= 2100):
            raise ValueError(f"Invalid reference year: {year}")
        if not landing_url.startswith("https://www.ine.pt/"):
            raise ValueError("F195 member landing_url must remain on the official INE surface")
        key = (indicator, year)
        if key in seen_indicator_year:
            raise ValueError(f"Duplicate indicator/year member: {key}")
        seen_requests.add(request_identity)
        seen_indicator_year.add(key)

    return package


def materialize_specs(package: dict) -> list[tuple[str, dict]]:
    """Expand a canonical package into ordinary one-indicator source specs.

    No producer request is issued here. Each returned object conforms to the
    existing source-spec contract and can be passed unchanged to core.run().
    """
    specs: list[tuple[str, dict]] = []
    for member in package["members"]:
        indicator = str(member["indicator"]).zfill(7)
        year = int(member["year"])
        request_identity = str(member["request_identity"])
        spec = {
            "schema_version": "1.0.0",
            "source_set_id": package["source_set_id"],
            "title": package["title"],
            "producer": package["producer"],
            "product_key": package["product_key"],
            "adapter": "ine_json",
            "access": "public",
            "sink": "private",
            "cadence": package["cadence"],
            "expected_format": package["expected_format"],
            "source": {
                **deepcopy(package["source"]),
                "landing_url": member["landing_url"],
            },
            "raw_native": deepcopy(package["raw_native"]),
            "reuse": deepcopy(package["reuse"]),
            "parameters": {
                "indicator": indicator,
                "year": year,
                "spacing_seconds": float(member.get("spacing_seconds", 2)),
                "execution_request_identity": request_identity,
            },
        }
        filename = f"{package['source_set_id']}__{indicator}__{year}.yml"
        specs.append((filename, spec))
    return specs


def materialize_to_dir(package_path: Path, out_dir: Path) -> dict:
    package = load_package(package_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for filename, spec in materialize_specs(package):
        path = out_dir / filename
        path.write_text(
            yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        records.append(
            {
                "request_identity": spec["parameters"]["execution_request_identity"],
                "source_set_id": spec["source_set_id"],
                "product_key": spec["product_key"],
                "adapter": spec["adapter"],
                "sink": spec["sink"],
                "indicator": spec["parameters"]["indicator"],
                "year": spec["parameters"]["year"],
                "spec_path": str(path),
            }
        )
    return {
        "schema_version": "1.0.0",
        "source_set_id": package["source_set_id"],
        "product_key": package["product_key"],
        "package_path": str(package_path),
        "member_count": len(records),
        "members": records,
        "producer_contacted": False,
        "semantics": "EXACTLY_ONE_STANDARD_INE_JSON_SPEC_PER_MEMBER",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--paths-only", action="store_true")
    args = parser.parse_args()

    manifest = materialize_to_dir(args.package, args.out_dir)
    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.paths_only:
        for member in manifest["members"]:
            print(member["spec_path"])
    else:
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
