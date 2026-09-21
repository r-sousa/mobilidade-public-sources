from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import re
import tempfile
import unicodedata
import urllib.parse
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests
from pypdf import PdfReader

from .private_bootstrap import download_release_asset, release_by_tag

API = "https://api.github.com"
UA = "MobilidadeNorte-W4CArchiveInventory/1.0"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": UA, "X-GitHub-Api-Version": "2022-11-28"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _get_text(repo: str, branch: str, path: str, token: str) -> tuple[str, str]:
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}"
    r = requests.get(url, params={"ref": branch}, headers=_headers(token), timeout=120)
    if not r.ok:
        raise RuntimeError(f"PRIVATE_CONTENT_READ_FAILED:{path}:{r.status_code}:{r.text[:300]}")
    obj = r.json()
    return base64.b64decode(obj["content"]).decode("utf-8"), obj["sha"]


def _put_text(repo: str, branch: str, path: str, text: str, token: str, *, message: str, immutable: bool = True) -> dict:
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
    body = {"message": message, "branch": branch, "content": base64.b64encode(text.encode("utf-8")).decode("ascii")}
    if current_sha:
        body["sha"] = current_sha
    r = requests.put(url, headers={**_headers(token), "Content-Type": "application/json"}, json=body, timeout=120)
    if not r.ok:
        raise RuntimeError(f"PRIVATE_CONTENT_WRITE_FAILED:{path}:{r.status_code}:{r.text[:300]}")
    obj = r.json()
    return {"path": path, "status": "WRITTEN", "commit": obj["commit"]["sha"], "sha": obj["content"]["sha"]}


def _member_text(path: str, data: bytes) -> str:
    p = path.lower()
    if p.endswith((".html", ".htm", ".txt", ".csv", ".json", ".xml", ".md")):
        raw = data.decode("utf-8", errors="replace")
        if p.endswith((".html", ".htm")):
            raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        return " ".join(raw.split())[:800000]
    if p.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(data), strict=False)
            chunks = []
            for page in reader.pages[:20]:
                chunks.append(page.extract_text() or "")
            return " ".join(" ".join(chunks).split())[:800000]
        except Exception:
            return ""
    return ""

PROFILES = {
    "F169": {
        "producer_tokens": ["dgeg", "direcao geral de energia", "direção geral de energia"],
        "identity_tokens": ["balanco energetico", "balanço energetico", "balanço energético", "consumo de energia", "portugal"],
        "scope_tokens": ["transport", "transporte", "transportes", "mobilidade"],
        "geo_tokens": ["portugal", "nacional"],
    },
    "F170": {
        "producer_tokens": ["dgeg", "direcao geral de energia", "direção geral de energia"],
        "identity_tokens": ["municipio", "município", "concelho", "consumo", "energia"],
        "scope_tokens": ["transport", "transporte", "transportes", "mobilidade"],
        "geo_tokens": ["municipio", "município", "concelho"],
    },
    "F176": {
        "producer_tokens": ["inega", "instituto energetico de galicia", "instituto energético de galicia"],
        "identity_tokens": ["galicia", "galiza", "balance energetico", "balance energético", "enerxia", "energía"],
        "scope_tokens": ["transport", "transporte", "transportes"],
        "geo_tokens": ["galicia", "galiza"],
    },
    "F179": {
        "producer_tokens": ["cores", "corporacion de reservas", "corporación de reservas"],
        "identity_tokens": ["carburante", "hidrocarburo", "gasoleo", "gasóleo", "gasolina", "automocion", "automoción"],
        "scope_tokens": ["automocion", "automoción", "carretera", "road transport", "transporte por carretera"],
        "geo_tokens": ["espana", "españa", "provincia"],
    },
}


def _candidate_scores(zf: zipfile.ZipFile, inventory: list[dict]) -> dict[str, list[dict]]:
    texts: dict[str, str] = {}
    for row in inventory:
        path = row["internal_path"]
        if row["is_dir"] or row["uncompressed_size"] > 25_000_000:
            continue
        if not path.lower().endswith((".html", ".htm", ".txt", ".csv", ".json", ".xml", ".md", ".pdf")):
            continue
        try:
            data = zf.read(path)
        except Exception:
            continue
        text = _member_text(path, data)
        if text:
            texts[path] = _fold(path + " " + text)
    out: dict[str, list[dict]] = {}
    for fid, profile in PROFILES.items():
        rows = []
        for path, folded in texts.items():
            exact_id = 1 if fid.casefold() in folded else 0
            producer = sorted({t for t in profile["producer_tokens"] if _fold(t) in folded})
            identity = sorted({t for t in profile["identity_tokens"] if _fold(t) in folded})
            scope = sorted({t for t in profile["scope_tokens"] if _fold(t) in folded})
            geo = sorted({t for t in profile["geo_tokens"] if _fold(t) in folded})
            score = exact_id * 100 + len(producer) * 12 + len(identity) * 5 + len(scope) * 8 + len(geo) * 4
            if score > 0:
                rows.append({"internal_path": path, "score": score, "literal_source_id_match": bool(exact_id), "producer_matches": producer, "identity_matches": identity, "scope_matches": scope, "geography_matches": geo})
        rows.sort(key=lambda x: (-x["score"], x["internal_path"]))
        out[fid] = rows[:25]
    return out


def _resolve(candidates: dict[str, list[dict]]) -> dict[str, dict]:
    result = {}
    for fid, rows in candidates.items():
        if not rows:
            result[fid] = {"status": "PRESERVED_ARCHIVE_MEMBER_ABSENT", "candidate_members": []}
            continue
        top = rows[0]
        literal = [r for r in rows if r["literal_source_id_match"]]
        if len(literal) == 1:
            result[fid] = {"status": "MAPPED_UNIQUE_DEFENSIBLE", "member": literal[0]["internal_path"], "basis": "unique archive-internal literal source-set identity", "candidate_members": rows}
            continue
        if len(literal) > 1:
            result[fid] = {"status": "AMBIGUOUS_ARCHIVE_MEMBER_IDENTITY", "candidate_members": literal}
            continue
        second_score = rows[1]["score"] if len(rows) > 1 else -1
        evidence_groups = sum(bool(top[k]) for k in ("producer_matches", "identity_matches", "scope_matches", "geography_matches"))
        if top["score"] >= 25 and evidence_groups >= 3 and top["score"] >= second_score + 12:
            result[fid] = {"status": "MAPPED_UNIQUE_DEFENSIBLE", "member": top["internal_path"], "basis": "unique high-margin preserved producer/product/geography/scope identity", "candidate_members": rows}
        else:
            result[fid] = {"status": "AMBIGUOUS_ARCHIVE_MEMBER_IDENTITY", "candidate_members": rows}
    return result

_NUMERIC = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:[,.]\d+)?(?:\s*%)?(?!\w)")
_UNIT = re.compile(r"\b(?:tep|ktep|mtep|twh|gwh|mwh|kwh|tj|gj|mj|m3|m³|nm3|nm³|kt|toneladas?|tonnes?|litros?|litres?|kg|%)\b", re.I)


def _extract_rows(fid: str, path: str, data: bytes) -> tuple[list[dict], str]:
    text = _member_text(path, data)
    lines = [" ".join(x.split()) for x in text.splitlines() if " ".join(x.split())]
    if len(lines) < 2:
        lines = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    admitted = []
    for i, raw in enumerate(lines, 1):
        f = _fold(raw)
        ok = False
        if fid in {"F169", "F170"}:
            ok = any(x in f for x in ("transport", "transporte", "transportes", "mobilidade"))
            if fid == "F170":
                ok = ok and any(x in f for x in ("municip", "concelho"))
        elif fid == "F176":
            ok = ("galicia" in f or "galiza" in f) and any(x in f for x in ("transport", "transporte"))
        elif fid == "F179":
            ok = any(x in f for x in ("automocion", "carretera", "road transport", "transporte por carretera"))
        if ok and _NUMERIC.search(raw):
            admitted.append({"locator": {"line": i}, "raw_text": raw, "numeric_tokens": _NUMERIC.findall(raw), "unit_tokens": _UNIT.findall(raw)})
    return admitted, "conservative_explicit_label_text_filter_v1"


def _csv_text(rows: list[dict]) -> str:
    s = io.StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=["line", "raw_text", "numeric_tokens_json", "unit_tokens_json"], lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({"line": r["locator"]["line"], "raw_text": r["raw_text"], "numeric_tokens_json": json.dumps(r["numeric_tokens"], ensure_ascii=False), "unit_tokens_json": json.dumps(r["unit_tokens"], ensure_ascii=False)})
    return s.getvalue()


def run(cfg: dict, read_token: str, write_token: str) -> dict:
    private_repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    release_tag = cfg["release_tag"]
    asset_cfg = cfg["asset"]
    team_text, _ = _get_text(private_repo, branch, "statistics/recovery-20260920/simple-runtime/team-missions.json", read_token)
    team = json.loads(team_text)
    if int(team.get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED")
    release = release_by_tag(private_repo, release_tag, read_token)
    asset = next((x for x in release.get("assets", []) if int(x["id"]) == int(asset_cfg["id"])), None)
    if not asset:
        raise RuntimeError("PINNED_RELEASE_ASSET_ID_NOT_FOUND")
    if asset["name"] != asset_cfg["name"] or int(asset["size"]) != int(asset_cfg["bytes"]):
        raise RuntimeError("PINNED_RELEASE_ASSET_METADATA_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="mn-w4c-inventory-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(private_repo, asset, read_token, local)
        data = local.read_bytes()
    actual_sha = _sha(data)
    if len(data) != int(asset_cfg["bytes"]) or actual_sha != asset_cfg["sha256"]:
        raise RuntimeError(f"ARCHIVE_VERIFICATION_FAILED:{len(data)}:{actual_sha}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W4C/{stamp}-G39-W4C-archive-inventory-first"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        inventory = [{"internal_path": zi.filename, "uncompressed_size": zi.file_size, "compressed_size": zi.compress_size, "crc32": f"{zi.CRC:08x}", "is_dir": zi.is_dir()} for zi in zf.infolist()]
        candidates = _candidate_scores(zf, inventory)
        member_map = _resolve(candidates)
        extraction = {}
        for fid, mapping in member_map.items():
            if mapping["status"] != "MAPPED_UNIQUE_DEFENSIBLE":
                extraction[fid] = {"status": mapping["status"], "admitted_row_count": 0}
                continue
            path = mapping["member"]
            member = zf.read(path)
            rows, method = _extract_rows(fid, path, member)
            state = "PASS_EXPLICIT_MOBILITY_ROWS" if rows else "PASS_VALID_EMPTY_EXPLICIT_MOBILITY_SCOPE"
            payload = {"schema_version": "4.0.1", "worker": "W4C", "mission_generation": generation, "source_set_id": fid, "status": state, "archive": {"release_tag": release_tag, "asset_id": asset_cfg["id"], "bytes": len(data), "sha256": actual_sha}, "member": {"internal_path": path, "bytes": len(member), "sha256": _sha(member)}, "extraction_method": method, "admitted_row_count": len(rows), "admitted_rows": rows, "guards": cfg["guards"][fid], "producer_reacquisition": False, "rights_adjudication": False}
            jpath = f"{out_base}/{fid}/{fid.lower()}-source-native.json"
            cpath = f"{out_base}/{fid}/{fid.lower()}-source-native.csv"
            _put_text(private_repo, branch, jpath, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message=f"W4C {fid}: archive-inventory-first extraction")
            _put_text(private_repo, branch, cpath, _csv_text(rows), write_token, message=f"W4C {fid}: source-native rows")
            handoff = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/{fid}/{actual_sha[:24]}-archive-extraction.json"
            handoff_payload = {"schema_version": "4.0.1", "source_set_id": fid, "status": state, "mission_generation": generation, "source_identity_unchanged": True, "archive_sha256": actual_sha, "member_path": path, "member_sha256": _sha(member), "member_bytes": len(member), "admitted_row_count": len(rows), "outputs": [jpath, cpath], "producer_reacquisition": False}
            _put_text(private_repo, branch, handoff, json.dumps(handoff_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message=f"W4C {fid}: extraction handoff")
            extraction[fid] = {"status": state, "member_path": path, "member_bytes": len(member), "member_sha256": _sha(member), "admitted_row_count": len(rows), "json": jpath, "csv": cpath, "handoff": handoff}
    inventory_payload = {"schema_version": "4.0.1", "worker": "W4C", "mission_generation": generation, "archive": {"release_tag": release_tag, "asset_id": asset_cfg["id"], "name": asset_cfg["name"], "bytes": len(data), "sha256": actual_sha, "verified_once_before_inspection": True}, "member_count": len(inventory), "members": inventory}
    map_payload = {"schema_version": "4.0.1", "worker": "W4C", "mission_generation": generation, "mode": "ARCHIVE_INVENTORY_FIRST", "mapping": member_map, "invalidated_routes_not_retried": ["EXACT_LOGICAL_MEMBER_PATH", "UNIQUE_PREFIXED_SUFFIX_MATCH_FOR_PINNED_LOGICAL_PATH"]}
    receipt_payload = {"schema_version": "4.0.1", "worker": "W4C", "mission_generation": generation, "archive_verification": "PASS", "archive_sha256": actual_sha, "inventory_member_count": len(inventory), "mapping_status": {k:v["status"] for k,v in member_map.items()}, "extraction": extraction, "producer_requests_made": 0, "rights_state_changed": False, "complete": True}
    ipath = f"{out_base}/f169-f170-f176-f179-archive-inventory.json"
    mpath = f"{out_base}/f169-f170-f176-f179-member-map.json"
    rpath = f"{out_base}/f169-f170-f176-f179-extraction-receipt.json"
    _put_text(private_repo, branch, ipath, json.dumps(inventory_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message="W4C: complete archive central-directory inventory")
    _put_text(private_repo, branch, mpath, json.dumps(map_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message="W4C: archive member identity map")
    _put_text(private_repo, branch, rpath, json.dumps(receipt_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message="W4C: archive inventory extraction receipt")
    return {"schema_version":"4.0.1","complete":True,"out_base":out_base,"inventory_path":ipath,"member_map_path":mpath,"receipt_path":rpath,"inventory_member_count":len(inventory),"mapping_status":receipt_payload["mapping_status"],"extraction":extraction}
