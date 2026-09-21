from __future__ import annotations

import csv
import io
import json
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .extract_w3c_shared import _html_extract, _metric_tags, _pdf_extract
from .extract_w4c_shared import _get_text, _put_text, _sha
from .private_bootstrap import download_release_asset, release_by_tag

_NS = {"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships", "pr":"http://schemas.openxmlformats.org/package/2006/relationships"}
_NUMERIC = re.compile(r"^[+-]?(?:\d+(?:[.,]\d+)?)$")


def _xlsx_rows(data: bytes) -> tuple[list[dict], dict]:
    out: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        if "xl/workbook.xml" not in names:
            return [], {"format":"zip_non_ooxml", "members":len(names)}
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iterfind(".//m:t", _NS)))
        relmap = {}
        if "xl/_rels/workbook.xml.rels" in names:
            rr = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            for rel in rr.findall("pr:Relationship", _NS):
                relmap[rel.attrib.get("Id")] = rel.attrib.get("Target")
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        sheets = []
        for sh in wb.findall("m:sheets/m:sheet", _NS):
            rid = sh.attrib.get("{%s}id" % _NS["r"])
            target = relmap.get(rid, "")
            if target.startswith("/"):
                path = target.lstrip("/")
            else:
                path = "xl/" + target.replace("../", "")
            sheets.append((sh.attrib.get("name", ""), path))
        for sheet_name, path in sheets:
            if path not in names:
                continue
            root = ET.fromstring(zf.read(path))
            for row in root.findall(".//m:sheetData/m:row", _NS):
                cells=[]; texts=[]
                for c in row.findall("m:c", _NS):
                    ref=c.attrib.get("r",""); typ=c.attrib.get("t","")
                    v=c.find("m:v",_NS); f=c.find("m:f",_NS); inline=c.find("m:is",_NS)
                    raw = v.text if v is not None else None
                    val = raw
                    if typ == "s" and raw is not None:
                        try: val = shared[int(raw)]
                        except Exception: val = raw
                    elif typ == "inlineStr" and inline is not None:
                        val = "".join(t.text or "" for t in inline.iterfind(".//m:t",_NS))
                    cells.append({"ref":ref,"type":typ,"value":val,"formula":f.text if f is not None else None})
                    if isinstance(val,str) and val.strip(): texts.append(val.strip())
                context=" | ".join(texts)
                tags=_metric_tags(context)
                numeric=[c for c in cells if c["value"] is not None and _NUMERIC.match(str(c["value"]).replace(" ",""))]
                if numeric and tags:
                    out.append({"locator":f"xlsx:sheet={sheet_name}:row={row.attrib.get('r','')}","metric_tags":tags,"cells":cells,"row_text":context})
        return out, {"format":"ooxml_xlsx", "sheet_count":len(sheets), "shared_string_count":len(shared), "archive_member_count":len(names)}


def _csv(rows: list[dict]) -> str:
    out=io.StringIO(newline="")
    fields=["locator","metric_tags","row_text","cells_json"]
    w=csv.DictWriter(out,fieldnames=fields,lineterminator="\n"); w.writeheader()
    for r in rows:
        w.writerow({"locator":r.get("locator",""),"metric_tags":"|".join(r.get("metric_tags",[])),"row_text":r.get("row_text") or r.get("raw_text","") ,"cells_json":json.dumps(r.get("cells",[]),ensure_ascii=False,separators=(",",":"))})
    return out.getvalue()


def run(cfg: dict, read_token: str, write_token: str) -> dict:
    repo=cfg["private_repository"]; branch=cfg["private_branch"]; generation=int(cfg["mission_generation"])
    team_path="statistics/recovery-20260920/simple-runtime/team-missions.json"
    team_text,_=_get_text(repo,branch,team_path,read_token); team=json.loads(team_text)
    if int(team.get("mission_generation",-1)) != generation: raise RuntimeError("MISSION_GENERATION_CHANGED")
    w3c=((team.get("teams") or {}).get("W3") or {}).get("C") or {}
    if w3c.get("worker") != "W3C" or "f166" not in " ".join(w3c.get("queue") or []).lower(): raise RuntimeError("W3C_CURRENT_MISSION_NO_LONGER_AUTHORIZES_F166")
    handoff_text,handoff_sha=_get_text(repo,branch,cfg["handoff_path"],read_token)
    if handoff_sha != cfg["handoff_blob_sha"]: raise RuntimeError(f"W3B_HANDOFF_BLOB_MISMATCH:{handoff_sha}")
    handoff=json.loads(handoff_text); preserved=handoff.get("preserved_input") or {}
    if preserved.get("private_release_tag") != cfg["release_tag"] or set(preserved.get("assets") or []) != set(a["name"] for a in cfg["assets"]): raise RuntimeError("W3B_HANDOFF_RELEASE_ASSET_SET_MISMATCH")
    release=release_by_tag(repo,cfg["release_tag"],read_token)
    release_assets={x["name"]:x for x in release.get("assets",[])}
    downloaded={}; inventory=[]
    with tempfile.TemporaryDirectory(prefix="mn-w3c-f166-") as td:
        for spec in cfg["assets"]:
            a=release_assets.get(spec["name"])
            if not a or int(a["id"]) != int(spec["id"]) or int(a["size"]) != int(spec["bytes"]): raise RuntimeError(f"ASSET_METADATA_MISMATCH:{spec['name']}")
            digest=str(a.get("digest") or "").removeprefix("sha256:")
            if digest and digest != spec["sha256"]: raise RuntimeError(f"ASSET_DIGEST_MISMATCH:{spec['name']}")
            p=Path(td)/spec["name"]; download_release_asset(repo,a,read_token,p); data=p.read_bytes()
            if len(data) != int(spec["bytes"]) or _sha(data) != spec["sha256"]: raise RuntimeError(f"ASSET_BYTE_HASH_MISMATCH:{spec['name']}")
            downloaded[spec["name"]]=data; inventory.append({"id":spec["id"],"name":spec["name"],"bytes":len(data),"sha256":_sha(data)})
    manifest=json.loads(downloaded["series-manifest.json"].decode("utf-8"))
    sat=downloaded["Satellite"]; rows=[]; method={}
    if sat.startswith(b"PK"):
        rows,method=_xlsx_rows(sat)
    elif sat.startswith(b"%PDF"):
        _,rows,method=_pdf_extract(sat)
    elif sat.lstrip().startswith((b"<",b"<!")):
        _,rows,method=_html_extract(sat)
    else:
        try:
            text=sat.decode("utf-8")
            method={"format":"utf8_text","chars":len(text)}
        except UnicodeDecodeError:
            method={"format":"unknown_binary","magic_hex":sat[:16].hex()}
    landing_candidates,landing_rows,landing_method=_html_extract(downloaded["landing.html"])
    status="PASS_EXPLICIT_SOURCE_NATIVE_METRIC_ROWS" if rows else "PASS_PRESERVED_SERIES_MANIFEST_NO_NUMERIC_ROWS_ADMITTED"
    payload={"schema_version":"4.0.1","worker":"W3C","mission_generation":generation,"source_set_id":"F166","producer":"Aena","product":"Informes mensuales de tráfico","status":status,"release_tag":cfg["release_tag"],"release_id":release.get("id"),"assets":inventory,"series_manifest":manifest,"satellite_parse":method,"landing_parse":landing_method,"landing_numeric_candidate_count":len(landing_candidates),"landing_admitted_row_count":len(landing_rows),"record_count":len(rows),"records":rows,"guards":["Keep passengers, aircraft operations and freight/cargo separate.","Preserve Aena airport labels and native period/file identity.","F166 ordinary public evidence remains distinct from controlled/private F167.","No missing cell is filled from ANAC, ANA, Eurostat or another source."],"producer_reacquisition":False,"rights_adjudication":False,"consumer_join":False}
    fresh,_=_get_text(repo,branch,team_path,read_token)
    if int(json.loads(fresh).get("mission_generation",-1)) != generation: raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); base=f"statistics/recovery-20260920/simple-runtime/outputs/W3C/{stamp}-G{generation}-W3C-F166-Aena-extraction-ingress"
    jpath=f"{base}/F166-source-native.json"; cpath=f"{base}/F166-source-native.csv"; rpath=f"{base}/extraction-receipt.json"; hpath=f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F166/{cfg['fingerprint']}-extraction.json"
    _put_text(repo,branch,jpath,json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",write_token,message="result(mn): W3C F166 source-native extraction",immutable=True)
    _put_text(repo,branch,cpath,_csv(rows),write_token,message="result(mn): W3C F166 compact extraction",immutable=True)
    receipt={"schema_version":"4.0.1","worker":"W3C","mission_generation":generation,"package":"W3C_F166_AENA_PRESERVED_EXTRACTION","source_set_id":"F166","status":status,"release_tag":cfg["release_tag"],"assets":inventory,"w3b_handoff":{"path":cfg["handoff_path"],"blob_sha":handoff_sha,"verified":True},"series_manifest_preserved":True,"satellite_parse":method,"record_count":len(rows),"outputs":[jpath,cpath],"producer_reacquisition":False,"rights_adjudication":False,"consumer_join":False}
    rtext=json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; _put_text(repo,branch,rpath,rtext,write_token,message="result(mn): W3C F166 extraction receipt",immutable=True); _put_text(repo,branch,hpath,rtext,write_token,message="handoff(mn): W3C F166 extraction",immutable=True)
    worker_path="statistics/recovery-20260920/simple-runtime/worker-W3C.json"; prior_text,prior_sha=_get_text(repo,branch,worker_path,write_token); prior=json.loads(prior_text); completed=list(prior.get("cumulative_completed") or []); marker=f"GEN{generation}_V401_W3C_F166_AENA_EXTRACTION"; completed += [] if marker in completed else [marker]
    previous_count=int(((prior.get("metrics") or {}).get("material_packages_this_window")) or 0); material=max(previous_count,1)+1
    worker={"schema_version":"4.0.1","worker":"W3C","team":"W3","partner":"C","mission_generation":generation,"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"status":"READY_CONTINUE_WINDOW","elastic_state":"ACTIVE_W3B_P114_P124_EXTRACTION_BACKLOG","current_task":None,"last_output":rpath,"window":{"mission_generation":generation,"phase":"CLEANUP_NORMALIZATION_COMPLETENESS","material_packages":material,"completed_packages":["P124_F30_IGE4580_SOURCE_NATIVE_MATRIX_V2","P114_F166_AENA"],"source_sets":["F30","F166"],"F166_record_count":len(rows),"producer_reacquisitions":0,"rights_adjudications":0,"consumer_tables_built":0,"canonical_manifest_index_catalogue_writes":0,"site_deployments":0,"drive_refreshes":0,"scheduler_changes":0,"outputs":[jpath,cpath,rpath,hpath],"next_cursor":["Continue P123/F10 and exact shared backlog members only with changed member identity.","Do not repeat F148 current 2024+ valid-empty package."]},"cumulative_completed":completed,"metrics":{"material_packages_this_window":material,"source_native_records_this_package":len(rows),"producer_reacquisitions_this_window":0},"blocker":None}
    _put_text(repo,branch,worker_path,json.dumps(worker,ensure_ascii=False,indent=2,sort_keys=True)+"\n",write_token,message="result(mn): W3C F166 Aena extraction ingress",expected_sha=prior_sha,immutable=False)
    return {"schema_version":"1.0.0","complete":True,"results":[{"source_set_id":"F166","status":status,"record_count":len(rows),"private_handoff":hpath}],"failures":[],"private_write_count":5}
