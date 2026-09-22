#!/usr/bin/env python3
import base64, csv, hashlib, io, json, os, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

PRIVATE_REPO = "r-sousa/EU-transp-weekly"
PRIVATE_BRANCH = "mobilidade-norte-recovery-20260919"
GEN = 57
OUTROOT = "statistics/recovery-20260920/simple-runtime/outputs/W4C/20260922T2345PT-G57-F188-F192-EXACT-BYTE-INGRESS"
REQUEST = "extraction_requests/W4C-G57-F188-F192.json"
FPS = {
    "F188": "cccd1faf52e294662eee1bb6ab6c7470829eacc5134f0890fb4e571a42e84ab5",
    "F189": "f2b73d2dd7a9009985f352f30351aa0c7f1a04816a77beb1387c6c77393fd520",
    "F190": "4f00e4a0598c691ddd2789110f23064bc86b121db63d6b87c00275ab695d5a55",
    "F191": "7c8f8fa18c0d43ed9782b4f890e47a3ed1041c66af0acf192bfe70951941b046",
    "F192": "b2ce6590c2532905b4ce446c1a2ad10a3a06ca5984340e1227de73ddbb6fbf90",
}

def sha256(b):
    return hashlib.sha256(b).hexdigest()

def ghopen(url, token, accept="application/vnd.github+json", timeout=300):
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": accept,
        "User-Agent": "MobilidadeNorte-W4C-G57/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)

def ghjson(url, token):
    with ghopen(url, token) as r:
        return json.loads(r.read())

def private_get_bytes(path, token):
    q = urllib.parse.quote(path, safe="/")
    obj = ghjson(f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{q}?ref={PRIVATE_BRANCH}", token)
    return base64.b64decode(obj["content"]), obj.get("sha")

def private_put_bytes(path, data, token, message):
    q = urllib.parse.quote(path, safe="/")
    url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{q}"
    payload = {
        "message": message,
        "content": base64.b64encode(data).decode("ascii"),
        "branch": PRIVATE_BRANCH,
    }
    try:
        current = ghjson(url + "?ref=" + PRIVATE_BRANCH, token)
        payload["sha"] = current["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="PUT", headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "MobilidadeNorte-W4C-G57/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())

def private_put_json(path, obj, token, message):
    data = (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    private_put_bytes(path, data, token, message)
    return {"path": path, "bytes": len(data), "sha256": sha256(data)}

def deterministic_counts(name, data):
    lower = name.lower()
    out = {"bytes": len(data), "sha256": sha256(data)}
    if lower.endswith(".csv"):
        text = data.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
        out.update({"kind": "csv", "rows_including_header": len(rows), "data_rows": max(0, len(rows)-1), "columns_max": max([len(r) for r in rows] or [0])})
    elif lower.endswith(".json"):
        obj = json.loads(data.decode("utf-8-sig"))
        out["kind"] = "json"
        if isinstance(obj, dict):
            out["top_level_keys"] = sorted(obj.keys())
            if isinstance(obj.get("value"), list):
                out["value_slots"] = len(obj["value"])
            elif isinstance(obj.get("value"), dict):
                out["value_slots"] = len(obj["value"])
            if isinstance(obj.get("status"), list):
                out["status_slots"] = len(obj["status"])
            elif isinstance(obj.get("status"), dict):
                out["status_slots"] = len(obj["status"])
            if isinstance(obj.get("id"), list):
                out["dimension_ids"] = obj["id"]
            if isinstance(obj.get("size"), list):
                out["dimension_sizes"] = obj["size"]
            charts = obj.get("charts")
            if isinstance(charts, list):
                out["chart_count"] = len(charts)
            elif isinstance(obj, list):
                out["object_count"] = len(obj)
        elif isinstance(obj, list):
            out.update({"kind": "json", "object_count": len(obj)})
    elif lower.endswith(".html") or lower.endswith(".htm"):
        out.update({"kind": "html", "utf8_chars": len(data.decode("utf-8"))})
    else:
        out["kind"] = "opaque"
    return out

def verify_and_extract(source_set_id, fp, read_token, write_token):
    receipt_path = f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/{source_set_id}/{fp}.json"
    raw_receipt, receipt_blob_sha = private_get_bytes(receipt_path, read_token)
    receipt = json.loads(raw_receipt.decode("utf-8"))
    if receipt.get("source_set_id") != source_set_id or receipt.get("native_asset_fingerprint") != fp:
        raise RuntimeError("RECEIPT_IDENTITY_MISMATCH")
    disp = receipt.get("disposition") or {}
    tag = disp.get("release_tag")
    if not tag or disp.get("repository") != PRIVATE_REPO:
        raise RuntimeError("RECEIPT_RELEASE_IDENTITY_MISSING")
    release = ghjson(f"https://api.github.com/repos/{PRIVATE_REPO}/releases/tags/{urllib.parse.quote(tag, safe='')}", read_token)
    rel_assets = {a["name"]: a for a in release.get("assets", [])}
    disp_assets = {a["name"]: a for a in disp.get("assets", [])}
    receipt_assets = receipt.get("assets") or []
    if not receipt_assets:
        raise RuntimeError("RECEIPT_HAS_NO_ASSETS")
    verified = []
    descendants = []
    for expected in receipt_assets:
        name = expected["name"]
        if name not in rel_assets or name not in disp_assets:
            raise RuntimeError("RELEASE_ASSET_MISSING:" + name)
        meta = rel_assets[name]
        pinned = disp_assets[name]
        if int(meta.get("id", -1)) != int(pinned.get("id", -2)):
            raise RuntimeError("RELEASE_ASSET_ID_MISMATCH:" + name)
        if int(meta.get("size", -1)) != int(expected["bytes"]) or int(pinned.get("bytes", -1)) != int(expected["bytes"]):
            raise RuntimeError("RELEASE_ASSET_SIZE_METADATA_MISMATCH:" + name)
        with ghopen(f"https://api.github.com/repos/{PRIVATE_REPO}/releases/assets/{int(meta['id'])}", read_token, "application/octet-stream") as r:
            data = r.read()
        got = sha256(data)
        if len(data) != int(expected["bytes"]):
            raise RuntimeError("BYTE_COUNT_FAIL:" + name)
        if got != expected["sha256"] or got != pinned.get("sha256"):
            raise RuntimeError("SHA256_FAIL:" + name)
        dest = f"{OUTROOT}/{source_set_id}/source-native/{name}"
        private_put_bytes(dest, data, write_token, f"W4C G57 {source_set_id}: persist exact verified source-native descendant {name}")
        count_meta = deterministic_counts(name, data)
        verified.append({
            "name": name,
            "release_asset_id": int(meta["id"]),
            "role": expected.get("role"),
            "format": expected.get("format"),
            "source_url": expected.get("source_url"),
            "expected_bytes": int(expected["bytes"]),
            "observed_bytes": len(data),
            "expected_sha256": expected["sha256"],
            "observed_sha256": got,
            "byte_count_check": "PASS",
            "sha256_check": "PASS",
        })
        descendants.append({"path": dest, **count_meta})
    package = {
        "schema_version": "1.0.0",
        "mission_generation": GEN,
        "worker": "W4C",
        "source_set_id": source_set_id,
        "status": "EXTRACTION_INGRESS_COMPLETE",
        "semantic_normalization_performed": False,
        "producer_reacquisition_performed": False,
        "receipt_path": receipt_path,
        "receipt_native_asset_fingerprint": fp,
        "receipt_file_bytes": len(raw_receipt),
        "receipt_file_sha256": sha256(raw_receipt),
        "receipt_blob_sha": receipt_blob_sha,
        "release_repository": PRIVATE_REPO,
        "release_tag": tag,
        "release_id": release.get("id"),
        "extraction_method": "PUBLIC_GITHUB_HOSTED_RUNNER_PRIVATE_RELEASE_API_OCTET_STREAM_WITH_MN_PRIVATE_READ_TOKEN",
        "verification_rule": "release asset id + byte count + SHA256 verified against exact private acquisition receipt before descendant persistence",
        "verified_assets": verified,
        "source_native_descendants": descendants,
        "interpretation": "NONE_SOURCE_NATIVE_ONLY",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "blocker": None,
    }
    ppath = f"{OUTROOT}/{source_set_id}/extraction-package.json"
    meta = private_put_json(ppath, package, write_token, f"W4C G57 {source_set_id}: extraction package")
    return {"source_set_id": source_set_id, "status": package["status"], "package_path": ppath, "package_sha256": meta["sha256"], "descendants": descendants}

def main():
    read_token = (os.getenv("MN_PRIVATE_READ_TOKEN") or "").strip()
    write_token = (os.getenv("MN_PRIVATE_SINK_TOKEN") or "").strip()
    if not read_token or not write_token:
        raise SystemExit("PRIVATE_RELEASE_BYTE_ROUTE_UNAVAILABLE:CREDENTIAL_MISSING")
    req = json.load(open(REQUEST, encoding="utf-8"))
    if req.get("mission_generation") != GEN or req.get("source_sets") != list(FPS.keys()) or req.get("fingerprints") != FPS:
        raise SystemExit("REQUEST_CONTRACT_MISMATCH")
    results = []
    common_blocker = None
    for sid, fp in FPS.items():
        try:
            results.append(verify_and_extract(sid, fp, read_token, write_token))
        except Exception as e:
            blocker = f"{type(e).__name__}:{e}"
            fail = {
                "schema_version": "1.0.0", "mission_generation": GEN, "worker": "W4C",
                "source_set_id": sid, "status": "EXTRACTION_INGRESS_BLOCKED",
                "receipt_path": f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/{sid}/{fp}.json",
                "receipt_native_asset_fingerprint": fp, "blocker": blocker,
                "semantic_normalization_performed": False, "producer_reacquisition_performed": False,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            ppath = f"{OUTROOT}/{sid}/extraction-package.json"
            meta = private_put_json(ppath, fail, write_token, f"W4C G57 {sid}: extraction blocker package")
            results.append({"source_set_id": sid, "status": fail["status"], "package_path": ppath, "package_sha256": meta["sha256"], "blocker": blocker})
            if "PRIVATE_RELEASE_BYTE_ROUTE_UNAVAILABLE" in blocker or "HTTP Error 403" in blocker or "HTTP Error 404" in blocker:
                common_blocker = common_blocker or blocker
    handoff = {
        "schema_version": "1.0.0", "mission_generation": GEN, "from_worker": "W4C", "to_worker": "W4A",
        "scope": ["F188", "F189", "F190", "F191", "F192"],
        "ownership_boundary": "W4A semantic normalization only; W4C extraction ends here",
        "results": results,
        "all_five_extraction_ingress_complete": all(r.get("status") == "EXTRACTION_INGRESS_COMPLETE" for r in results),
        "common_blocker": common_blocker,
        "producer_reacquisition_performed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    private_put_json(f"{OUTROOT}/06-w4c-to-w4a-handoff.json", handoff, write_token, "W4C G57: F188-F192 exact-byte ingress handoff to W4A")
    print(json.dumps(handoff, ensure_ascii=False, sort_keys=True))
    if not handoff["all_five_extraction_ingress_complete"]:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
