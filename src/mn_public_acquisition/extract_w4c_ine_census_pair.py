from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import io
import json
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .private_bootstrap import download_release_asset, release_by_tag

API = "https://api.github.com"
UA = "MobilidadeNorte-W4C-INE-CensusPair/2.0"
MAX_PART_BYTES = 6_000_000


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_text(repo: str, branch: str, path: str, token: str) -> tuple[str, str]:
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}"
    r = requests.get(url, params={"ref": branch}, headers=_headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(f"PRIVATE_CONTENT_READ_FAILED:{path}:{r.status_code}:{r.text[:300]}")
    obj = r.json()
    return base64.b64decode(obj["content"]).decode("utf-8"), obj["sha"]


def _put_text(repo: str, branch: str, path: str, text: str, token: str, *, message: str, immutable: bool = True) -> dict[str, Any]:
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}"
    g = requests.get(url, params={"ref": branch}, headers=_headers(token), timeout=120)
    if g.status_code == 200:
        obj = g.json()
        existing = base64.b64decode(obj["content"]).decode("utf-8")
        if existing == text:
            return {"path": path, "status": "IDENTICAL_ALREADY_PRESENT", "sha": obj["sha"]}
        if immutable:
            raise RuntimeError(f"IMMUTABLE_PRIVATE_OUTPUT_CONFLICT:{path}")
        current_sha = obj["sha"]
    elif g.status_code == 404:
        current_sha = None
    else:
        raise RuntimeError(f"PRIVATE_CONTENT_LOOKUP_FAILED:{path}:{g.status_code}:{g.text[:300]}")
    body: dict[str, Any] = {
        "message": message,
        "branch": branch,
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }
    if current_sha:
        body["sha"] = current_sha
    r = requests.put(url, headers={**_headers(token), "Content-Type": "application/json"}, json=body, timeout=240)
    if not r.ok:
        raise RuntimeError(f"PRIVATE_CONTENT_WRITE_FAILED:{path}:{r.status_code}:{r.text[:300]}")
    obj = r.json()
    return {"path": path, "status": "WRITTEN", "commit": obj["commit"]["sha"], "sha": obj["content"]["sha"]}


def _scalarish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _is_observation_dict(item: dict[str, Any]) -> bool:
    keys = {str(k).casefold() for k in item}
    markers = {
        "geocod", "geodsg", "valor", "valor_numerico", "valornumerico", "sinal_conv",
        "dim_3", "dim_3_t", "dim_4", "dim_4_t", "dim_5", "dim_5_t", "dim_6", "dim_6_t",
    }
    if keys & markers:
        return True
    complex_values = sum(isinstance(v, (dict, list)) for v in item.values())
    return complex_values == 0


def _walk_rows(node: Any, path: list[str], out: list[dict[str, Any]]) -> None:
    """Find producer-native observation dictionaries without interpreting their dimensions."""
    if isinstance(node, list):
        for idx, item in enumerate(node):
            if isinstance(item, dict) and _is_observation_dict(item):
                out.append({"context_path": list(path), "source_row": item})
            else:
                _walk_rows(item, path + [str(idx)], out)
        return
    if isinstance(node, dict):
        if _is_observation_dict(node):
            out.append({"context_path": list(path), "source_row": node})
            return
        for key, value in node.items():
            _walk_rows(value, path + [str(key)], out)
        return
    out.append({"context_path": list(path), "source_row": {"value": node}})


def _unwrap_response(raw_json: Any) -> tuple[Any, dict[str, Any], str | None]:
    if isinstance(raw_json, dict):
        for key in ("Data", "data", "DATA"):
            value = raw_json.get(key)
            if isinstance(value, (list, dict)):
                meta = {k: v for k, v in raw_json.items() if k != key}
                return value, meta, key
    return raw_json, {}, None


def _indicator_items(core: Any) -> list[Any]:
    if isinstance(core, list):
        return core
    if isinstance(core, dict):
        if any(str(k).casefold() == "dados" for k in core):
            return [core]
        vals = list(core.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return vals
        return [core]
    return [core]


def _extract_payload(raw_json: Any) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    core, response_meta, wrapper_key = _unwrap_response(raw_json)
    indicators = _indicator_items(core)
    metadata: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for i, item in enumerate(indicators):
        if not isinstance(item, dict):
            metadata.append({"indicator_index": i, "top_level_value": item})
            continue
        data_key = next((k for k in item if str(k).casefold() == "dados"), None)
        meta = {k: v for k, v in item.items() if k != data_key}
        meta["indicator_index"] = i
        metadata.append(meta)
        local: list[dict[str, Any]] = []
        if data_key is None:
            _walk_rows(item, [], local)
        else:
            _walk_rows(item[data_key], [], local)
        for row in local:
            row["indicator_index"] = i
            rows.append(row)
    response_info = {
        "wrapper_key": wrapper_key,
        "response_metadata": response_meta,
        "core_type": type(core).__name__,
    }
    return response_info, metadata, rows


def _field_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys: set[str] = set()
    nonnull: dict[str, int] = {}
    samples: dict[str, list[str]] = {}
    for rec in rows:
        row = rec.get("source_row") or {}
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            ks = str(k)
            keys.add(ks)
            if v not in (None, ""):
                nonnull[ks] = nonnull.get(ks, 0) + 1
                if len(samples.setdefault(ks, [])) < 5:
                    sv = _scalarish(v)
                    if sv not in samples[ks]:
                        samples[ks].append(sv[:240])
    return {
        "field_count": len(keys),
        "fields": sorted(keys),
        "nonnull_counts": {k: nonnull.get(k, 0) for k in sorted(keys)},
        "samples": {k: samples.get(k, []) for k in sorted(keys)},
    }


def _split_records(rows: list[dict[str, Any]], target_bytes: int = MAX_PART_BYTES) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    size = 2
    for row in rows:
        estimate = len(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")) + 2
        if current and size + estimate > target_bytes:
            chunks.append(current)
            current = []
            size = 2
        current.append(row)
        size += estimate
    if current:
        chunks.append(current)
    return chunks


def _csv_text(source_set_id: str, metadata: list[dict[str, Any]], rows: list[dict[str, Any]]) -> str:
    row_fields = sorted({str(k) for rec in rows for k in ((rec.get("source_row") or {}).keys() if isinstance(rec.get("source_row"), dict) else [])})
    meta_by_idx = {int(m.get("indicator_index", i)): m for i, m in enumerate(metadata)}
    meta_keys = []
    for preferred in ("IndicadorCod", "IndicadorDsg", "DataExtracao", "DataUltimoAtualizacao", "UltimoPref"):
        if any(preferred in m for m in metadata):
            meta_keys.append(preferred)
    cols = ["source_set_id", "indicator_index", "context_path_json"] + [f"meta__{k}" for k in meta_keys] + row_fields
    s = io.StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for rec in rows:
        idx = int(rec.get("indicator_index", 0))
        source_row = rec.get("source_row") if isinstance(rec.get("source_row"), dict) else {"value": rec.get("source_row")}
        out: dict[str, Any] = {
            "source_set_id": source_set_id,
            "indicator_index": idx,
            "context_path_json": json.dumps(rec.get("context_path") or [], ensure_ascii=False, separators=(",", ":")),
        }
        meta = meta_by_idx.get(idx, {})
        for k in meta_keys:
            out[f"meta__{k}"] = _scalarish(meta.get(k))
        for k in row_fields:
            out[k] = _scalarish(source_row.get(k))
        w.writerow(out)
    return s.getvalue()


def _write_parts(private_repo: str, branch: str, sid: str, out_base: str, metadata: list[dict[str, Any]], rows: list[dict[str, Any]], write_token: str, generation: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    json_parts: list[dict[str, Any]] = []
    csv_parts: list[dict[str, Any]] = []
    chunks = _split_records(rows)
    for i, chunk in enumerate(chunks, 1):
        jtext = json.dumps(chunk, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
        ctext = _csv_text(sid, metadata, chunk)
        jpath = f"{out_base}/{sid}/{sid.lower()}-source-native-part-{i:04d}.json"
        cpath = f"{out_base}/{sid}/{sid.lower()}-source-native-part-{i:04d}.csv"
        _put_text(private_repo, branch, jpath, jtext, write_token, message=f"W4C G{generation} {sid}: source-native JSON part {i}")
        _put_text(private_repo, branch, cpath, ctext, write_token, message=f"W4C G{generation} {sid}: source-native CSV part {i}")
        json_parts.append({"path": jpath, "sha256": _sha(jtext.encode('utf-8')), "bytes": len(jtext.encode('utf-8')), "rows": len(chunk)})
        csv_parts.append({"path": cpath, "sha256": _sha(ctext.encode('utf-8')), "bytes": len(ctext.encode('utf-8')), "rows": len(chunk)})
    return json_parts, csv_parts


def run(cfg: dict[str, Any], read_token: str, write_token: str) -> dict[str, Any]:
    private_repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    release_tag = cfg["release_tag"]
    execution_attempt = int(cfg.get("execution_attempt", 2))

    team_text, team_sha = _get_text(private_repo, branch, "statistics/recovery-20260920/simple-runtime/team-missions.json", read_token)
    team = json.loads(team_text)
    if int(team.get("mission_generation", -1)) != generation:
        raise RuntimeError(f"MISSION_GENERATION_CHANGED:{team.get('mission_generation')}!=G{generation}")
    current_w4c = (((team.get("teams") or {}).get("W4") or {}).get("C") or {})
    if "F25" not in json.dumps(current_w4c, ensure_ascii=False) or "F26" not in json.dumps(current_w4c, ensure_ascii=False):
        raise RuntimeError("CURRENT_W4C_MISSION_DOES_NOT_ASSIGN_F25_F26")

    release = release_by_tag(private_repo, release_tag, read_token)
    assets_by_id = {int(x["id"]): x for x in release.get("assets", [])}
    verified: dict[str, dict[str, Any]] = {}
    payloads: dict[str, tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], bytes, bytes]] = {}

    # Verify all exact preserved bytes before parsing either source.
    with tempfile.TemporaryDirectory(prefix="mn-w4c-f25-f26-") as td:
        tdir = Path(td)
        compressed: dict[str, bytes] = {}
        for sid in ("F25", "F26"):
            acfg = cfg["assets"][sid]
            asset = assets_by_id.get(int(acfg["id"]))
            if not asset:
                raise RuntimeError(f"{sid}:PINNED_RELEASE_ASSET_ID_NOT_FOUND")
            if asset.get("name") != acfg["name"] or int(asset.get("size", -1)) != int(acfg["bytes"]):
                raise RuntimeError(f"{sid}:PINNED_RELEASE_ASSET_METADATA_MISMATCH")
            local = tdir / acfg["name"]
            download_release_asset(private_repo, asset, read_token, local)
            comp = local.read_bytes()
            digest = _sha(comp)
            if len(comp) != int(acfg["bytes"]) or digest != acfg["sha256"]:
                raise RuntimeError(f"{sid}:ASSET_VERIFICATION_FAILED:{len(comp)}:{digest}")
            verified[sid] = {"asset_id": int(asset["id"]), "name": asset["name"], "bytes": len(comp), "sha256": digest}
            compressed[sid] = comp

        for sid in ("F25", "F26"):
            comp = compressed[sid]
            try:
                raw = gzip.decompress(comp)
            except Exception as exc:
                raise RuntimeError(f"{sid}:GZIP_DECOMPRESSION_FAILED:{exc}") from exc
            try:
                obj = json.loads(raw.decode("utf-8-sig"))
            except Exception as exc:
                raise RuntimeError(f"{sid}:JSON_PARSE_FAILED:{exc}") from exc
            response_info, metadata, rows = _extract_payload(obj)
            if not rows:
                raise RuntimeError(f"{sid}:NO_SOURCE_NATIVE_ROWS_EXTRACTED")
            payloads[sid] = (response_info, metadata, rows, comp, raw)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W4C/{stamp}-G{generation}-F25-F26-INE-EXTRACTION-V2"
    results: dict[str, Any] = {}

    for sid in ("F25", "F26"):
        response_info, metadata, rows, comp, raw = payloads[sid]
        inv = _field_inventory(rows)
        guard = cfg["semantic_guards"][sid]
        json_parts, csv_parts = _write_parts(private_repo, branch, sid, out_base, metadata, rows, write_token, generation)
        summary_path = f"{out_base}/{sid}/{sid.lower()}-source-native-summary.json"
        summary = {
            "schema_version": "4.1.0",
            "worker": "W4C",
            "mission_generation": generation,
            "execution_attempt": execution_attempt,
            "source_set_id": sid,
            "status": "PASS_SOURCE_NATIVE_EXTRACTION_INGRESS",
            "semantic_owner_after_return": "W4B",
            "source_identity": {
                "private_release": release_tag,
                **verified[sid],
                "gzip_decompressed_bytes": len(raw),
                "gzip_decompressed_sha256": _sha(raw),
                "verified_before_parse": True,
            },
            "response_structure": response_info,
            "indicator_metadata": metadata,
            "producer_payload_shape": {"indicator_objects": len(metadata), "source_native_rows": len(rows), "field_inventory": inv},
            "json_parts": json_parts,
            "csv_parts": csv_parts,
            "guards": guard,
            "interpretation_performed": False,
            "producer_reacquisition": False,
            "rights_adjudication": False,
            "consumer_interpretation": False,
        }
        summary_text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        _put_text(private_repo, branch, summary_path, summary_text, write_token, message=f"W4C G{generation} {sid}: corrected source-native extraction summary")
        receipt_path = f"{out_base}/{sid}/{sid.lower()}-extraction-receipt.json"
        receipt = {
            "schema_version": "4.1.0",
            "worker": "W4C",
            "mission_generation": generation,
            "execution_attempt": execution_attempt,
            "source_set_id": sid,
            "status": "PASS_SOURCE_NATIVE_EXTRACTION_INGRESS",
            "asset": verified[sid],
            "gzip_decompressed_bytes": len(raw),
            "gzip_decompressed_sha256": _sha(raw),
            "source_native_row_count": len(rows),
            "field_count": inv["field_count"],
            "summary": {"path": summary_path, "sha256": _sha(summary_text.encode('utf-8')), "bytes": len(summary_text.encode('utf-8'))},
            "json_parts": json_parts,
            "csv_parts": csv_parts,
            "semantic_owner_after_return": "W4B",
            "state_after_ingress": "ACQUIRED_NOT_NORMALIZED",
            "producer_reacquisition": False,
            "rights_adjudication": False,
            "consumer_built": False,
            "complete": True,
        }
        receipt_text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        receipt_hash = _sha(receipt_text.encode("utf-8"))
        _put_text(private_repo, branch, receipt_path, receipt_text, write_token, message=f"W4C G{generation} {sid}: corrected extraction receipt")
        handoff_path = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/{sid}/{verified[sid]['sha256'][:24]}-g{generation}-v2-extraction.json"
        handoff = {
            **receipt,
            "handoff_type": "DETERMINISTIC_EXTRACTION_INGRESS_TO_W4B",
            "private_extraction_receipt": receipt_path,
            "private_extraction_receipt_sha256": receipt_hash,
            "binding_team_missions_blob_sha": team_sha,
            "corrects_prior_attempt": cfg.get("corrects_prior_attempt"),
            "changed_method_reason": cfg.get("changed_method_reason"),
        }
        _put_text(private_repo, branch, handoff_path, json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message=f"W4C G{generation} {sid}: corrected extraction handoff to W4B")
        results[sid] = {
            "status": receipt["status"],
            "source_native_row_count": len(rows),
            "summary": summary_path,
            "receipt": receipt_path,
            "receipt_sha256": receipt_hash,
            "handoff": handoff_path,
            "json_parts": json_parts,
            "csv_parts": csv_parts,
        }

    family = {
        "schema_version": "4.1.0",
        "worker": "W4C",
        "mission_generation": generation,
        "execution_attempt": execution_attempt,
        "operation": "DETERMINISTIC_PRIVATE_PRESERVED_INE_CENSUS_PAIR_EXTRACTION",
        "release_tag": release_tag,
        "assets_verified_before_parse": True,
        "results": results,
        "semantic_owner_after_return": "W4B",
        "producer_requests_made": 0,
        "rights_state_changed": False,
        "consumer_tables_built": False,
        "corrects_prior_attempt": cfg.get("corrects_prior_attempt"),
        "changed_method_reason": cfg.get("changed_method_reason"),
        "complete": True,
    }
    family_path = f"{out_base}/f25-f26-family-extraction-receipt.json"
    _put_text(private_repo, branch, family_path, json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message=f"W4C G{generation}: corrected F25/F26 family extraction receipt")
    return {"complete": True, "out_base": out_base, "family_receipt": family_path, "results": results}
