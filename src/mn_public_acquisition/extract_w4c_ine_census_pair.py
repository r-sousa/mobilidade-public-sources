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
UA = "MobilidadeNorte-W4C-INE-CensusPair/1.0"


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


def _walk_rows(node: Any, path: list[str], out: list[dict[str, Any]]) -> None:
    """Conservatively preserve producer rows under Dados without semantic reshaping."""
    if isinstance(node, list):
        for idx, item in enumerate(node):
            if isinstance(item, dict):
                out.append({"context_path": list(path), "source_row": item})
            else:
                out.append({"context_path": list(path) + [str(idx)], "source_row": {"value": item}})
        return
    if isinstance(node, dict):
        # Most INE payloads use period keys -> list[dict]. Recurse until a row-bearing list is found.
        for key, value in node.items():
            _walk_rows(value, path + [str(key)], out)
        return
    out.append({"context_path": list(path), "source_row": {"value": node}})


def _extract_payload(raw_json: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indicators = raw_json if isinstance(raw_json, list) else [raw_json]
    metadata: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for i, item in enumerate(indicators):
        if not isinstance(item, dict):
            metadata.append({"indicator_index": i, "top_level_value": item})
            continue
        data_key = "Dados" if "Dados" in item else ("dados" if "dados" in item else None)
        meta = {k: v for k, v in item.items() if k != data_key}
        meta["indicator_index"] = i
        metadata.append(meta)
        if data_key is None:
            # Fail closed to a single preserved object row rather than inventing an observation grain.
            rows.append({"indicator_index": i, "context_path": [], "source_row": item})
            continue
        local: list[dict[str, Any]] = []
        _walk_rows(item[data_key], [], local)
        for row in local:
            row["indicator_index"] = i
            rows.append(row)
    return metadata, rows


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


def _csv_text(source_set_id: str, metadata: list[dict[str, Any]], rows: list[dict[str, Any]]) -> str:
    row_fields = sorted({str(k) for rec in rows for k in ((rec.get("source_row") or {}).keys() if isinstance(rec.get("source_row"), dict) else [])})
    meta_by_idx = {int(m.get("indicator_index", i)): m for i, m in enumerate(metadata)}
    meta_keys = []
    for preferred in ("IndicadorCod", "IndicadorDsg", "DataExtracao", "DataUltimoAtualizacao", "UltimoPref"):
        if any(preferred in m for m in metadata):
            meta_keys.append(preferred)
    cols = ["source_set_id", "indicator_index", "context_path_json"] + [f"meta__{k}" for k in meta_keys] + row_fields + ["source_row_json"]
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
            "source_row_json": json.dumps(source_row, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        }
        meta = meta_by_idx.get(idx, {})
        for k in meta_keys:
            out[f"meta__{k}"] = _scalarish(meta.get(k))
        for k in row_fields:
            out[k] = _scalarish(source_row.get(k))
        w.writerow(out)
    return s.getvalue()


def run(cfg: dict[str, Any], read_token: str, write_token: str) -> dict[str, Any]:
    private_repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    release_tag = cfg["release_tag"]

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
    payloads: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]], bytes, bytes]] = {}

    # Verify every assigned asset before any parse.
    with tempfile.TemporaryDirectory(prefix="mn-w4c-f25-f26-") as td:
        tdir = Path(td)
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
            payloads[sid] = ([], [], comp, b"")

        for sid in ("F25", "F26"):
            comp = payloads[sid][2]
            try:
                raw = gzip.decompress(comp)
            except Exception as exc:
                raise RuntimeError(f"{sid}:GZIP_DECOMPRESSION_FAILED:{exc}") from exc
            try:
                obj = json.loads(raw.decode("utf-8-sig"))
            except Exception as exc:
                raise RuntimeError(f"{sid}:JSON_PARSE_FAILED:{exc}") from exc
            metadata, rows = _extract_payload(obj)
            if not rows:
                raise RuntimeError(f"{sid}:NO_SOURCE_NATIVE_ROWS_EXTRACTED")
            payloads[sid] = (metadata, rows, comp, raw)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W4C/{stamp}-G{generation}-F25-F26-INE-EXTRACTION"
    results: dict[str, Any] = {}

    for sid in ("F25", "F26"):
        metadata, rows, comp, raw = payloads[sid]
        inv = _field_inventory(rows)
        guard = cfg["semantic_guards"][sid]
        payload = {
            "schema_version": "4.1.0",
            "worker": "W4C",
            "mission_generation": generation,
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
            "producer_payload_shape": {
                "top_level_type": type(json.loads(raw.decode('utf-8-sig'))).__name__,
                "indicator_objects": len(metadata),
                "source_native_rows": len(rows),
                "field_inventory": inv,
            },
            "indicator_metadata": metadata,
            "source_native_rows": rows,
            "guards": guard,
            "interpretation_performed": False,
            "producer_reacquisition": False,
            "rights_adjudication": False,
            "consumer_interpretation": False,
        }
        json_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
        csv_text = _csv_text(sid, metadata, rows)
        json_path = f"{out_base}/{sid}/{sid.lower()}-source-native.json"
        csv_path = f"{out_base}/{sid}/{sid.lower()}-source-native.csv"
        receipt_path = f"{out_base}/{sid}/{sid.lower()}-extraction-receipt.json"
        handoff_path = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/{sid}/{verified[sid]['sha256'][:24]}-g{generation}-extraction.json"
        json_hash = _sha(json_text.encode("utf-8"))
        csv_hash = _sha(csv_text.encode("utf-8"))
        receipt = {
            "schema_version": "4.1.0",
            "worker": "W4C",
            "mission_generation": generation,
            "source_set_id": sid,
            "status": "PASS_SOURCE_NATIVE_EXTRACTION_INGRESS",
            "asset": verified[sid],
            "gzip_decompressed_bytes": len(raw),
            "gzip_decompressed_sha256": _sha(raw),
            "source_native_row_count": len(rows),
            "field_count": inv["field_count"],
            "outputs": {
                "json": {"path": json_path, "sha256": json_hash, "bytes": len(json_text.encode('utf-8'))},
                "csv": {"path": csv_path, "sha256": csv_hash, "bytes": len(csv_text.encode('utf-8'))},
            },
            "semantic_owner_after_return": "W4B",
            "state_after_ingress": "ACQUIRED_NOT_NORMALIZED",
            "producer_reacquisition": False,
            "rights_adjudication": False,
            "consumer_built": False,
            "complete": True,
        }
        receipt_text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        receipt_hash = _sha(receipt_text.encode("utf-8"))
        handoff = {
            **receipt,
            "handoff_type": "DETERMINISTIC_EXTRACTION_INGRESS_TO_W4B",
            "private_extraction_receipt": receipt_path,
            "private_extraction_receipt_sha256": receipt_hash,
            "binding_team_missions_blob_sha": team_sha,
        }
        _put_text(private_repo, branch, json_path, json_text, write_token, message=f"W4C G{generation} {sid}: source-native INE extraction")
        _put_text(private_repo, branch, csv_path, csv_text, write_token, message=f"W4C G{generation} {sid}: source-native INE CSV")
        _put_text(private_repo, branch, receipt_path, receipt_text, write_token, message=f"W4C G{generation} {sid}: extraction receipt")
        _put_text(private_repo, branch, handoff_path, json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message=f"W4C G{generation} {sid}: extraction handoff to W4B")
        results[sid] = {
            "status": receipt["status"],
            "source_native_row_count": len(rows),
            "json": json_path,
            "json_sha256": json_hash,
            "csv": csv_path,
            "csv_sha256": csv_hash,
            "receipt": receipt_path,
            "receipt_sha256": receipt_hash,
            "handoff": handoff_path,
        }

    family = {
        "schema_version": "4.1.0",
        "worker": "W4C",
        "mission_generation": generation,
        "operation": "DETERMINISTIC_PRIVATE_PRESERVED_INE_CENSUS_PAIR_EXTRACTION",
        "release_tag": release_tag,
        "assets_verified_before_parse": True,
        "results": results,
        "semantic_owner_after_return": "W4B",
        "producer_requests_made": 0,
        "rights_state_changed": False,
        "consumer_tables_built": False,
        "complete": True,
    }
    family_path = f"{out_base}/f25-f26-family-extraction-receipt.json"
    _put_text(private_repo, branch, family_path, json.dumps(family, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message=f"W4C G{generation}: F25/F26 family extraction receipt")
    return {"complete": True, "out_base": out_base, "family_receipt": family_path, "results": results}
