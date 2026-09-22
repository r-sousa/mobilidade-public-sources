from __future__ import annotations

import hashlib
import json
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .extract_w4c_archive_inventory import _get_text, _member_text, _put_text
from .private_bootstrap import download_release_asset, release_by_tag


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _candidate_map(zf: zipfile.ZipFile, inventory: list[dict], members: dict) -> dict[str, dict]:
    searchable: dict[str, str] = {}
    for row in inventory:
        path = row["internal_path"]
        if row["is_dir"]:
            continue
        suffix = Path(path).suffix.lower()
        folded = _fold(path)
        if suffix in {".html", ".htm", ".txt", ".csv", ".json", ".xml", ".md", ".pdf"} and row["uncompressed_size"] <= 80_000_000:
            try:
                folded += " " + _fold(_member_text(path, zf.read(path)))
            except Exception:
                pass
        searchable[path] = folded

    out: dict[str, dict] = {}
    for fid, spec in members.items():
        producer_tokens = [_fold(x) for x in spec.get("producer_tokens", [])]
        product_tokens = [_fold(x) for x in spec.get("product_tokens", [])]
        geo_tokens = [_fold(x) for x in spec.get("geography_tokens", [])]
        expected_ext = str(spec.get("expected_extension") or "").lower()
        rows = []
        for path, folded in searchable.items():
            literal_id = fid.casefold() in folded
            pm = sorted({t for t in producer_tokens if t and t in folded})
            qm = sorted({t for t in product_tokens if t and t in folded})
            gm = sorted({t for t in geo_tokens if t and t in folded})
            ext_match = bool(expected_ext and path.lower().endswith(expected_ext))
            score = (200 if literal_id else 0) + 20 * len(pm) + 10 * len(qm) + 5 * len(gm) + (3 if ext_match else 0)
            if score:
                rows.append({
                    "internal_path": path,
                    "score": score,
                    "literal_source_id_match": literal_id,
                    "producer_matches": pm,
                    "product_matches": qm,
                    "geography_matches": gm,
                    "extension_match": ext_match,
                })
        rows.sort(key=lambda x: (-x["score"], x["internal_path"]))
        literals = [r for r in rows if r["literal_source_id_match"]]
        if len(literals) == 1:
            chosen = literals[0]
            status = "MAPPED_UNIQUE_DEFENSIBLE"
            basis = "unique archive-internal literal source-set identity"
        elif len(literals) > 1:
            out[fid] = {"status": "AMBIGUOUS_ARCHIVE_MEMBER_IDENTITY", "candidate_members": literals[:25]}
            continue
        elif not rows:
            out[fid] = {"status": "PRESERVED_ARCHIVE_MEMBER_ABSENT", "candidate_members": []}
            continue
        else:
            top = rows[0]
            second = rows[1]["score"] if len(rows) > 1 else -1
            groups = sum(bool(top[k]) for k in ("producer_matches", "product_matches", "geography_matches"))
            if top["score"] >= 43 and groups >= 2 and top["producer_matches"] and top["product_matches"] and top["score"] >= second + 15:
                chosen = top
                status = "MAPPED_UNIQUE_DEFENSIBLE"
                basis = "unique high-margin preserved producer/product/geography identity"
            else:
                out[fid] = {"status": "AMBIGUOUS_ARCHIVE_MEMBER_IDENTITY", "candidate_members": rows[:25]}
                continue
        member = zf.read(chosen["internal_path"])
        out[fid] = {
            "status": status,
            "member": chosen["internal_path"],
            "basis": basis,
            "member_bytes": len(member),
            "member_sha256": hashlib.sha256(member).hexdigest(),
            "candidate_members": rows[:25],
        }
    return out


def run(cfg: dict, read_token: str, write_token: str) -> dict:
    repo = cfg["private_repository"]
    branch = cfg["private_branch"]
    generation = int(cfg["mission_generation"])
    tag = cfg["release_tag"]
    asset_cfg = cfg["asset"]
    members = cfg["members"]
    team_path = "statistics/recovery-20260920/simple-runtime/team-missions.json"

    team_text, _ = _get_text(repo, branch, team_path, read_token)
    team = json.loads(team_text)
    if int(team.get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED")
    w3c = ((team.get("teams") or {}).get("W3") or {}).get("C") or {}
    queue_text = " ".join(w3c.get("queue") or []).casefold()
    if w3c.get("worker") != "W3C" or not all(fid.casefold() in queue_text for fid in members):
        raise RuntimeError("W3C_CURRENT_MISSION_NO_LONGER_AUTHORIZES_SHARED_ARCHIVE_FAMILY")

    release = release_by_tag(repo, tag, read_token)
    asset = next((x for x in release.get("assets", []) if int(x["id"]) == int(asset_cfg["id"])), None)
    if not asset:
        raise RuntimeError("PINNED_RELEASE_ASSET_ID_NOT_FOUND")
    if asset["name"] != asset_cfg["name"] or int(asset["size"]) != int(asset_cfg["bytes"]):
        raise RuntimeError("PINNED_RELEASE_ASSET_METADATA_MISMATCH")
    digest = str(asset.get("digest") or "").removeprefix("sha256:")
    if digest and digest != asset_cfg["sha256"]:
        raise RuntimeError("PINNED_RELEASE_ASSET_DIGEST_METADATA_MISMATCH")

    with tempfile.TemporaryDirectory(prefix="mn-w3c-inventory-") as td:
        local = Path(td) / asset_cfg["name"]
        download_release_asset(repo, asset, read_token, local)
        if local.stat().st_size != int(asset_cfg["bytes"]):
            raise RuntimeError(f"ARCHIVE_SIZE_MISMATCH:{local.stat().st_size}")
        archive_sha = _file_sha256(local)
        if archive_sha != asset_cfg["sha256"]:
            raise RuntimeError(f"ARCHIVE_SHA_MISMATCH:{archive_sha}")
        with zipfile.ZipFile(local) as zf:
            inventory = [{
                "internal_path": zi.filename,
                "uncompressed_size": zi.file_size,
                "compressed_size": zi.compress_size,
                "crc32": f"{zi.CRC:08x}",
                "is_dir": zi.is_dir(),
            } for zi in zf.infolist()]
            member_map = _candidate_map(zf, inventory, members)

    fresh_team_text, _ = _get_text(repo, branch, team_path, read_token)
    if int(json.loads(fresh_team_text).get("mission_generation", -1)) != generation:
        raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = f"statistics/recovery-20260920/simple-runtime/outputs/W3C/{stamp}-G{generation}-shared-archive-inventory-first"
    inventory_path = f"{out_base}/archive-inventory.json"
    map_path = f"{out_base}/member-map.json"
    receipt_path = f"{out_base}/receipt.json"
    canonical_receipt = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/W3C/shared-archive-{asset_cfg['sha256']}-inventory.json"

    inv_obj = {
        "schema_version": "4.0.3",
        "worker": "W3C",
        "mission_generation": generation,
        "release_tag": tag,
        "archive": {"asset_id": asset_cfg["id"], "name": asset_cfg["name"], "bytes": asset_cfg["bytes"], "sha256": archive_sha, "verified": True},
        "member_count": len(inventory),
        "members": inventory,
    }
    map_obj = {
        "schema_version": "4.0.3",
        "worker": "W3C",
        "mission_generation": generation,
        "method": "ARCHIVE_INVENTORY_FIRST_THEN_PRESERVED_IDENTITY_SCORING",
        "release_tag": tag,
        "archive_sha256": archive_sha,
        "mappings": member_map,
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "numeric_rows_admitted": 0,
    }
    statuses = {fid: row["status"] for fid, row in member_map.items()}
    receipt = {
        "schema_version": "4.0.3",
        "worker": "W3C",
        "mission_generation": generation,
        "package": "W3C_SHARED_ARCHIVE_INVENTORY_FIRST",
        "status": "PASS_ARCHIVE_INVENTORY_AND_MEMBER_MAP",
        "archive": inv_obj["archive"],
        "source_set_ids": list(members),
        "member_statuses": statuses,
        "mapped_unique": sorted(fid for fid, state in statuses.items() if state == "MAPPED_UNIQUE_DEFENSIBLE"),
        "ambiguous": sorted(fid for fid, state in statuses.items() if state == "AMBIGUOUS_ARCHIVE_MEMBER_IDENTITY"),
        "absent_from_preserved_archive": sorted(fid for fid, state in statuses.items() if state == "PRESERVED_ARCHIVE_MEMBER_ABSENT"),
        "producer_reacquisition": False,
        "rights_adjudication": False,
        "numeric_rows_admitted": 0,
        "outputs": [inventory_path, map_path, receipt_path],
        "next_rule": "Only MAPPED_UNIQUE_DEFENSIBLE members may proceed to source-native parsing. Ambiguous/absent preserved members are bounded archive-identity results, not producer/source absence and do not authorize reacquisition.",
    }
    for path, obj, msg in [
        (inventory_path, inv_obj, "result(mn): W3C shared archive central-directory inventory"),
        (map_path, map_obj, "result(mn): W3C shared archive identity map"),
        (receipt_path, receipt, "result(mn): W3C shared archive inventory-first receipt"),
        (canonical_receipt, receipt, "handoff(mn): W3C shared archive inventory-first receipt"),
    ]:
        _put_text(repo, branch, path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", write_token, message=msg, immutable=True)

    return {
        "schema_version": "1.0.0",
        "complete": True,
        "private_repository": repo,
        "release_tag": tag,
        "archive_sha256": archive_sha,
        "member_count": len(inventory),
        "member_statuses": statuses,
        "private_receipt": canonical_receipt,
        "producer_reacquisition": False,
    }
