from __future__ import annotations
import csv, io, json, re, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path
from .extract_w3c_shared import _html_extract, _pdf_extract, _metric_tags
from .extract_w3c_f166 import _xlsx_rows
from .extract_w4c_shared import _get_text, _put_text, _sha
from .private_bootstrap import download_release_asset, release_by_tag

_NUM=re.compile(r"[+-]?\d[\d\s.,]*")

def _text_rows(text:str, member:str):
    rows=[]
    for i,line in enumerate(text.splitlines(),1):
        s=" ".join(line.split())
        tags=_metric_tags(s)
        nums=_NUM.findall(s)
        if tags and nums:
            rows.append({"locator":f"{member}:line={i}","metric_tags":tags,"raw_text":s,"numeric_tokens":nums})
    return rows

def _csv(rows):
    out=io.StringIO(newline=""); fields=["member","locator","metric_tags","raw_text","row_json"]
    w=csv.DictWriter(out,fieldnames=fields,lineterminator="\n"); w.writeheader()
    for r in rows:
        w.writerow({"member":r.get("member",""),"locator":r.get("locator",""),"metric_tags":"|".join(r.get("metric_tags",[])),"raw_text":r.get("raw_text") or r.get("row_text","") ,"row_json":json.dumps(r,ensure_ascii=False,separators=(",",":"))})
    return out.getvalue()

def run(cfg, read_token, write_token):
    repo=cfg["private_repository"]; branch=cfg["private_branch"]; generation=int(cfg["mission_generation"]); team_path="statistics/recovery-20260920/simple-runtime/team-missions.json"
    team_text,_=_get_text(repo,branch,team_path,read_token); team=json.loads(team_text)
    if int(team.get("mission_generation",-1))!=generation: raise RuntimeError("MISSION_GENERATION_CHANGED")
    w3c=((team.get("teams") or {}).get("W3") or {}).get("C") or {}; q=" ".join(w3c.get("queue") or []).lower()
    if w3c.get("worker")!="W3C" or "f10" not in q: raise RuntimeError("W3C_CURRENT_MISSION_NO_LONGER_AUTHORIZES_F10")
    handoff_text,handoff_sha=_get_text(repo,branch,cfg["handoff_path"],read_token)
    if handoff_sha!=cfg["handoff_blob_sha"]: raise RuntimeError(f"W3B_HANDOFF_BLOB_MISMATCH:{handoff_sha}")
    handoff=json.loads(handoff_text); preserved=handoff.get("preserved_input") or {}
    if preserved.get("release_tag")!=cfg["release_tag"] or preserved.get("asset")!=cfg["asset"]["name"]: raise RuntimeError("W3B_HANDOFF_RELEASE_ASSET_MISMATCH")
    release=release_by_tag(repo,cfg["release_tag"],read_token); a=next((x for x in release.get("assets",[]) if int(x["id"])==int(cfg["asset"]["id"])),None)
    if not a or a["name"]!=cfg["asset"]["name"] or int(a["size"])!=int(cfg["asset"]["bytes"]): raise RuntimeError("PINNED_RELEASE_ASSET_METADATA_MISMATCH")
    digest=str(a.get("digest") or "").removeprefix("sha256:")
    if digest and digest!=cfg["asset"]["sha256"]: raise RuntimeError("PINNED_RELEASE_ASSET_DIGEST_MISMATCH")
    inventory=[]; rows=[]; methods={}
    with tempfile.TemporaryDirectory(prefix="mn-w3c-f10-") as td:
        p=Path(td)/a["name"]; download_release_asset(repo,a,read_token,p); data=p.read_bytes()
        if len(data)!=int(cfg["asset"]["bytes"]) or _sha(data)!=cfg["asset"]["sha256"]: raise RuntimeError("PINNED_RELEASE_ASSET_BYTE_HASH_MISMATCH")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir(): continue
                name=info.filename; member=zf.read(name); entry={"name":name,"bytes":len(member),"sha256":_sha(member)}; inventory.append(entry)
                low=name.lower(); admitted=[]; method={"format":"unsupported_or_inventory_only"}
                try:
                    if low.endswith(".pdf"):
                        _,admitted,method=_pdf_extract(member)
                    elif low.endswith((".html",".htm")):
                        _,admitted,method=_html_extract(member)
                    elif low.endswith(".xlsx") or member.startswith(b"PK"):
                        admitted,method=_xlsx_rows(member)
                    elif low.endswith((".txt",".csv",".json",".md")):
                        text=member.decode("utf-8",errors="replace"); admitted=_text_rows(text,name); method={"format":"utf8_text","chars":len(text)}
                except Exception as exc:
                    method={"format":"parse_error","error":str(exc)}; admitted=[]
                methods[name]=method
                for r in admitted:
                    rr=dict(r); rr["member"]=name; rr["member_sha256"]=entry["sha256"]; rows.append(rr)
    status="PASS_EXPLICIT_SOURCE_NATIVE_METRIC_CANDIDATES" if rows else "PASS_ARCHIVE_INVENTORY_NO_EXPLICIT_NUMERIC_METRIC_ROWS_ADMITTED"
    payload={"schema_version":"4.0.1","worker":"W3C","mission_generation":generation,"source_set_id":"F10","producer":"ANAC","product":"anuarios","status":status,"release_tag":cfg["release_tag"],"release_id":release.get("id"),"archive":{"asset_id":a["id"],"name":a["name"],"bytes":len(data),"sha256":_sha(data)},"archive_inventory":inventory,"member_parse_methods":methods,"record_count":len(rows),"records":rows,"guards":["Numeric table candidates only; page text existence alone is not an accepted statistical observation.","Preserve archive member, edition/file/page locator, metric definition, units, flags and missingness.","Do not collapse revisions across annual editions.","Keep passengers, movements and freight/cargo separate.","No producer reacquisition and no cross-source fill."],"producer_reacquisition":False,"rights_adjudication":False,"consumer_join":False}
    fresh,_=_get_text(repo,branch,team_path,read_token)
    if int(json.loads(fresh).get("mission_generation",-1))!=generation: raise RuntimeError("MISSION_GENERATION_CHANGED_BEFORE_PRIVATE_WRITE")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); base=f"statistics/recovery-20260920/simple-runtime/outputs/W3C/{stamp}-G{generation}-W3C-F10-ANAC-annual-extraction-ingress"
    jpath=f"{base}/F10-source-native.json"; cpath=f"{base}/F10-source-native.csv"; rpath=f"{base}/extraction-receipt.json"; hpath=f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F10/{cfg['fingerprint']}-extraction.json"
    _put_text(repo,branch,jpath,json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",write_token,message="result(mn): W3C F10 archive extraction",immutable=True)
    _put_text(repo,branch,cpath,_csv(rows),write_token,message="result(mn): W3C F10 compact extraction",immutable=True)
    receipt={"schema_version":"4.0.1","worker":"W3C","mission_generation":generation,"package":"W3C_F10_ANAC_PRESERVED_ARCHIVE_EXTRACTION","source_set_id":"F10","status":status,"release_tag":cfg["release_tag"],"archive":{"asset_id":a["id"],"name":a["name"],"bytes":len(data),"sha256":_sha(data),"members":len(inventory)},"w3b_handoff":{"path":cfg["handoff_path"],"blob_sha":handoff_sha,"verified":True},"record_count":len(rows),"outputs":[jpath,cpath],"producer_reacquisition":False,"rights_adjudication":False,"consumer_join":False}
    rtext=json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; _put_text(repo,branch,rpath,rtext,write_token,message="result(mn): W3C F10 extraction receipt",immutable=True); _put_text(repo,branch,hpath,rtext,write_token,message="handoff(mn): W3C F10 extraction",immutable=True)
    worker_path="statistics/recovery-20260920/simple-runtime/worker-W3C.json"; prior_text,prior_sha=_get_text(repo,branch,worker_path,write_token); prior=json.loads(prior_text); completed=list(prior.get("cumulative_completed") or []); marker=f"GEN{generation}_V401_W3C_F10_ANAC_ARCHIVE_EXTRACTION"; completed += [] if marker in completed else [marker]
    previous=int(((prior.get("metrics") or {}).get("material_packages_this_window")) or 0); material=previous+1
    worker={"schema_version":"4.0.1","worker":"W3C","team":"W3","partner":"C","mission_generation":generation,"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"status":"READY_CONTINUE_WINDOW","elastic_state":"ACTIVE_W3B_P114_P124_EXTRACTION_BACKLOG","current_task":None,"last_output":rpath,"window":{"mission_generation":generation,"phase":"CLEANUP_NORMALIZATION_COMPLETENESS","material_packages":material,"completed_packages":["P123_F10_ANAC_ARCHIVE"],"source_sets":["F10"],"F10_record_count":len(rows),"archive_member_count":len(inventory),"producer_reacquisitions":0,"rights_adjudications":0,"consumer_tables_built":0,"canonical_manifest_index_catalogue_writes":0,"site_deployments":0,"drive_refreshes":0,"scheduler_changes":0,"outputs":[jpath,cpath,rpath,hpath],"next_cursor":["Continue P114/F166 or changed shared-member identities if still current and non-overlapping.","Do not repeat F148 current 2024+ valid-empty package."]},"cumulative_completed":completed,"metrics":{"material_packages_this_window":material,"source_native_records_this_package":len(rows),"producer_reacquisitions_this_window":0},"blocker":None}
    _put_text(repo,branch,worker_path,json.dumps(worker,ensure_ascii=False,indent=2,sort_keys=True)+"\n",write_token,message="result(mn): W3C F10 archive extraction ingress",expected_sha=prior_sha,immutable=False)
    return {"schema_version":"1.0.0","complete":True,"results":[{"source_set_id":"F10","status":status,"record_count":len(rows),"archive_members":len(inventory),"private_handoff":hpath}],"failures":[],"private_write_count":5}
