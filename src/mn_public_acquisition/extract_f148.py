from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

SOURCE_SET_ID = "F148"
DATASET = "tran_r_rago"
EXPECTED_BYTES = 42285
EXPECTED_SHA256 = "54921560492f54576da1d3bb9402bca02bde0932581d265cfbb3a3e18c19f868"
EXPECTED_DIMENSIONS = {"freq", "unit", "c_unload", "c_load", "geo", "time"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ordered_codes(dimension: dict, dimension_id: str, expected_size: int) -> list[str]:
    category = dimension.get("category") or {}
    index = category.get("index")
    if isinstance(index, dict):
        codes = [str(k) for k, _ in sorted(index.items(), key=lambda kv: int(kv[1]))]
    elif isinstance(index, list):
        codes = [str(x) for x in index]
    else:
        raise ValueError(f"JSONSTAT_CATEGORY_INDEX_MISSING:{dimension_id}")
    if len(codes) != expected_size:
        raise ValueError(
            f"JSONSTAT_CATEGORY_SIZE_MISMATCH:{dimension_id}:{len(codes)}:{expected_size}"
        )
    return codes


def _indexed_values(obj: object, cell_count: int, name: str) -> tuple[dict[int, object], str]:
    if isinstance(obj, list):
        if len(obj) != cell_count:
            raise ValueError(f"JSONSTAT_{name}_ARRAY_SIZE_MISMATCH:{len(obj)}:{cell_count}")
        return {i: value for i, value in enumerate(obj)}, "ARRAY"
    if isinstance(obj, dict):
        out: dict[int, object] = {}
        for key, value in obj.items():
            try:
                idx = int(key)
            except Exception as exc:
                raise ValueError(f"JSONSTAT_{name}_NONINTEGER_INDEX:{key}") from exc
            if idx < 0 or idx >= cell_count:
                raise ValueError(f"JSONSTAT_{name}_INDEX_OOB:{idx}:{cell_count}")
            out[idx] = value
        return out, "SPARSE_OBJECT"
    if obj is None:
        return {}, "ABSENT"
    raise ValueError(f"JSONSTAT_{name}_UNSUPPORTED_TYPE:{type(obj).__name__}")


def _coordinates(linear_index: int, sizes: list[int], ids: list[str], codes: dict[str, list[str]]) -> dict[str, str]:
    remaining = linear_index
    positions = [0] * len(sizes)
    for i in range(len(sizes) - 1, -1, -1):
        n = sizes[i]
        positions[i] = remaining % n
        remaining //= n
    if remaining:
        raise ValueError("JSONSTAT_LINEAR_INDEX_DECODE_OVERFLOW")
    return {dim: codes[dim][positions[i]] for i, dim in enumerate(ids)}


def extract(input_path: Path, output_dir: Path) -> dict:
    data = input_path.read_bytes()
    actual_bytes = len(data)
    actual_sha = sha256_bytes(data)
    if actual_bytes != EXPECTED_BYTES or actual_sha != EXPECTED_SHA256:
        raise ValueError(
            "F148_NATIVE_ASSET_VERIFICATION_FAILED:"
            f"bytes={actual_bytes}:sha256={actual_sha}"
        )

    raw = json.loads(data.decode("utf-8"))
    ids = raw.get("id")
    sizes_raw = raw.get("size")
    dimensions = raw.get("dimension")
    if not isinstance(ids, list) or not isinstance(sizes_raw, list) or len(ids) != len(sizes_raw):
        raise ValueError("JSONSTAT_DIMENSION_CONTRACT_INVALID")
    if not isinstance(dimensions, dict):
        raise ValueError("JSONSTAT_DIMENSION_METADATA_INVALID")
    ids = [str(x) for x in ids]
    sizes = [int(x) for x in sizes_raw]
    missing_dimensions = sorted(EXPECTED_DIMENSIONS - set(ids))
    if missing_dimensions:
        raise ValueError("JSONSTAT_EXPECTED_DIMENSIONS_MISSING:" + ",".join(missing_dimensions))

    codes_by_dim: dict[str, list[str]] = {}
    for i, dim in enumerate(ids):
        meta = dimensions.get(dim)
        if not isinstance(meta, dict):
            raise ValueError(f"JSONSTAT_DIMENSION_METADATA_MISSING:{dim}")
        codes_by_dim[dim] = _ordered_codes(meta, dim, sizes[i])

    cell_count = math.prod(sizes)
    values, value_encoding = _indexed_values(raw.get("value"), cell_count, "VALUE")
    statuses, status_encoding = _indexed_values(raw.get("status"), cell_count, "STATUS")
    explicit_positions = sorted(set(values) | set(statuses))

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "f148_tran_r_rago_source_native_ingress.csv"
    fieldnames = [
        "native_linear_index",
        *ids,
        "value_present",
        "value_json",
        "value_is_null",
        "status_present",
        "status_json",
        "status_is_null",
    ]
    value_nulls = 0
    status_nulls = 0
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for linear_index in explicit_positions:
            coords = _coordinates(linear_index, sizes, ids, codes_by_dim)
            value_present = linear_index in values
            status_present = linear_index in statuses
            value = values.get(linear_index)
            status = statuses.get(linear_index)
            if value_present and value is None:
                value_nulls += 1
            if status_present and status is None:
                status_nulls += 1
            writer.writerow(
                {
                    "native_linear_index": linear_index,
                    **coords,
                    "value_present": str(value_present).lower(),
                    "value_json": json.dumps(value, ensure_ascii=False, separators=(",", ":")) if value_present else "",
                    "value_is_null": str(value_present and value is None).lower(),
                    "status_present": str(status_present).lower(),
                    "status_json": json.dumps(status, ensure_ascii=False, separators=(",", ":")) if status_present else "",
                    "status_is_null": str(status_present and status is None).lower(),
                }
            )

    csv_bytes = csv_path.read_bytes()
    csv_sha = sha256_bytes(csv_bytes)
    source_native = {
        "schema_version": "1.0.0",
        "source_set_id": SOURCE_SET_ID,
        "dataset": DATASET,
        "native_asset": {
            "name": "tran_r_rago.json",
            "bytes": EXPECTED_BYTES,
            "sha256": EXPECTED_SHA256,
            "verified": True,
        },
        "evidence_class": "OBSERVED_PRIMARY_RAIL_GOODS",
        "jsonstat": {
            "version": raw.get("version"),
            "class": raw.get("class"),
            "label": raw.get("label"),
            "source": raw.get("source"),
            "updated": raw.get("updated"),
            "id": ids,
            "size": sizes,
            "dimension": dimensions,
            "value": raw.get("value"),
            "status": raw.get("status"),
            "value_encoding": value_encoding,
            "status_encoding": status_encoding,
            "native_cell_count": cell_count,
            "explicit_positions_count": len(explicit_positions),
        },
        "dimension_roles": {
            "c_load": "producer-native loading NUTS2 role",
            "c_unload": "producer-native unloading NUTS2 role",
            "geo": "producer-native reporting geography role",
            "time": "producer-native reference period",
            "unit": "producer-native unit",
            "freq": "producer-native frequency",
        },
        "missingness": {
            "explicit_value_null_rows": value_nulls,
            "explicit_status_null_rows": status_nulls,
            "rule": (
                "JSON-stat array nulls and sparse explicit keys are preserved exactly. "
                "Positions absent from both value and status are not materialized as observations; "
                "no missing or suppressed value is converted to numeric zero."
            ),
        },
        "semantic_guards": {
            "direction_inferred": False,
            "od_cells_synthesized": False,
            "mirror_reporters_averaged": False,
            "producer_reacquisition": False,
            "consumer_joins": False,
            "observed_vs_modelled_preserved": True,
            "rights_state_changed": False,
        },
        "outputs": {
            "csv_name": csv_path.name,
            "csv_bytes": len(csv_bytes),
            "csv_sha256": csv_sha,
        },
    }
    json_path = output_dir / "f148_tran_r_rago_source_native_ingress.json"
    json_path.write_text(
        json.dumps(source_native, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    json_bytes = json_path.read_bytes()
    receipt = {
        "schema_version": "1.0.0",
        "source_set_id": SOURCE_SET_ID,
        "package": "F148_EUROSTAT_TRAN_R_RAGO_EXTRACTION_INGRESS",
        "status": "PASS_NATIVE_BYTES_VERIFIED_AND_SOURCE_NATIVE_INGRESS_EMITTED",
        "native_asset_fingerprint": "54690c8fc00232401f07e3c331b1b0d3911b54d6ff494fdcdaa58ef908d40fda",
        "source_asset_verified": True,
        "native_cell_count": cell_count,
        "explicit_positions_count": len(explicit_positions),
        "dimensions": ids,
        "value_encoding": value_encoding,
        "status_encoding": status_encoding,
        "producer_native_roles_preserved": True,
        "status_flags_preserved": True,
        "missingness_preserved": True,
        "direction_inferred": False,
        "od_cells_synthesized": False,
        "mirror_reporters_averaged": False,
        "producer_reacquisition": False,
        "rights_state_changed": False,
        "outputs": [
            {"name": csv_path.name, "bytes": len(csv_bytes), "sha256": csv_sha},
            {"name": json_path.name, "bytes": len(json_bytes), "sha256": sha256_bytes(json_bytes)},
        ],
    }
    receipt_path = output_dir / "extraction-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.input, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
