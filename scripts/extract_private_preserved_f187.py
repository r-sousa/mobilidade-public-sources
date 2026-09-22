#!/usr/bin/env python3
import base64
import csv
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SOURCE_SET_ID="F187"
FINGERPRINT="43652d12e479f222ab932e5c7104c85cd8ca4b991f9a850d485b9f761d6125bd"
RELEASE_TAG="mn-src-f187-43652d12e479f222ab93"
PRIVATE_REPO="r-sousa/EU-transp-weekly"
PRIVATE_BRANCH="mobilidade-norte-recovery-20260919"
PRIVATE_RECEIPT=f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F187/{FINGERPRINT}.json"
REQUEST=pathlib.Path(f"extraction_requests/F187-{FINGERPRINT}.json")
WAKE_GENERATION=43
ASSIGNMENT_ORIGIN_GENERATION=42
MONTHS={"janeiro":1,"jan":1,"fevereiro":2,"fev":2,"marco":3,"mar":3,"abril":4,"abr":4,"maio":5,"mai":5,"junho":6,"jun":6,"julho":7,"jul":7,"agosto":8,"ago":8,"setembro":9,"set":9,"outubro":10,"out":10,"novembro":11,"nov":11,"dezembro":12,"dez":12}


def norm(v):
    s=str(v if v is not None else "").strip()
    s="".join(c for c in unicodedata.normalize("NFKD",s) if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+"," ",s)

def sha(b): return hashlib.sha256(b).hexdigest()
def cj(v): return json.dumps(v,ensure_ascii=False,separators=(",",":"),sort_keys=True)

def gh_open(url,token,accept="application/vnd.github+json",timeout=240):
    h={"Authorization":"Bearer "+token,"Accept":accept,"User-Agent":"MobilidadeNorte-F187Extractor/1.1","X-GitHub-Api-Version":"2022-11-28"}
    return urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=timeout)

def gh_json(url,token):
    with gh_open(url,token) as r: return json.loads(r.read())

def private_text(path,token):
    q=urllib.parse.quote(path,safe="/")
    obj=gh_json(f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{q}?ref={PRIVATE_BRANCH}",token)
    return base64.b64decode(obj["content"]).decode("utf-8")

def period(name):
    n=norm(name); y=re.search(r"(20\d{2})",n); year=int(y.group(1)) if y else None
    q=None
    m=re.search(r"([1-4])(?:o|º)?\s*trimestre",n)
    if m: q=int(m.group(1))
    return {"reference_year":year,"reference_quarter":q,"edition_scope":("ANNUAL" if year and q is None and "trimestre" not in n else (f"Q{q}" if q else "UNRESOLVED"))}

def month_for(label):
    n=norm(label)
    for k,v in MONTHS.items():
        if re.search(rf"(^|[^a-z]){re.escape(k)}([^a-z]|$)",n): return v
    return None

def hscore(vals):
    t=" | ".join(norm(x) for x in vals if str(x).strip())
    score=0
    for tok,pts in [("autoestrad",5),("concess",5),("sublanc",6),("sublan",6),("tmdm",7),("tmda",7),("trafego",4),("circul",3),("veicul",2),("portagem",2),("extens",2),("km",1)]:
        if tok in t: score+=pts
    return score+min(sum(1 for x in vals if str(x).strip()),10)*0.15

def core_role(label):
    n=norm(label)
    if "autoestrad" in n or re.search(r"(^|\W)ae(\W|$)",n): return "motorway"
    if "concess" in n: return "concession"
    if "sublanc" in n or "sublan" in n: return "sublanco"
    if "tmdm" in n: return "tmdm"
    if "tmda" in n: return "tmda"
    return None

def typed(book,cell):
    import xlrd
    if cell.ctype==xlrd.XL_CELL_EMPTY: return {"type":"blank","value":""}
    if cell.ctype==xlrd.XL_CELL_TEXT: return {"type":"text","value":str(cell.value)}
    if cell.ctype==xlrd.XL_CELL_NUMBER: return {"type":"number","value":cell.value}
    if cell.ctype==xlrd.XL_CELL_DATE:
        try: return {"type":"date","value":xlrd.xldate.xldate_as_datetime(cell.value,book.datemode).isoformat(),"excel_serial":cell.value}
        except Exception: return {"type":"date","value":cell.value,"decode_error":True}
    if cell.ctype==xlrd.XL_CELL_BOOLEAN: return {"type":"boolean","value":bool(cell.value)}
    if cell.ctype==xlrd.XL_CELL_ERROR: return {"type":"error","value":int(cell.value)}
    return {"type":f"xlrd_{cell.ctype}","value":cell.value}

def csv_write(path,fields,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n",extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def safe_stem(name):
    return re.sub(r"[^A-Za-z0-9._-]+","_",pathlib.Path(name).stem)[:180]


def main():
    if not REQUEST.exists(): raise SystemExit("EXTRACTION_REQUEST_MISSING")
    rq=json.loads(REQUEST.read_text(encoding="utf-8"))
    if rq.get("source_set_id")!=SOURCE_SET_ID or rq.get("native_asset_fingerprint")!=FINGERPRINT or rq.get("release_tag")!=RELEASE_TAG: raise SystemExit("REQUEST_IDENTITY_MISMATCH")
    if int(rq.get("wake_mission_generation",-1))!=WAKE_GENERATION: raise SystemExit("REQUEST_WAKE_GENERATION_MISMATCH")
    read=(os.environ.get("MN_PRIVATE_SINK_TOKEN") or os.environ.get("MN_PRIVATE_READ_TOKEN") or "").strip(); write=(os.environ.get("MN_PRIVATE_SINK_TOKEN") or "").strip()
    if not read: raise SystemExit("MN_PRIVATE_READ_CREDENTIAL_MISSING")
    if not write: raise SystemExit("MN_PRIVATE_WRITE_CREDENTIAL_MISSING")

    receipt=json.loads(private_text(PRIVATE_RECEIPT,read))
    if receipt.get("native_asset_fingerprint")!=FINGERPRINT: raise SystemExit("PRIVATE_RECEIPT_FINGERPRINT_MISMATCH")
    expected=receipt.get("assets") or []; byname={a["name"]:a for a in expected}
    xls=[a for a in expected if a["name"].lower().endswith(".xls")]
    if len(xls)!=51: raise SystemExit(f"PRIVATE_RECEIPT_XLS_COUNT_MISMATCH:{len(xls)}")
    if not {"landing.html","series-manifest.json"}.issubset(byname): raise SystemExit("SUPPORT_ASSET_MISSING")
    rel=gh_json(f"https://api.github.com/repos/{PRIVATE_REPO}/releases/tags/{RELEASE_TAG}",read); rassets={a["name"]:a for a in rel.get("assets",[])}
    missing=sorted(set(byname)-set(rassets))
    if missing: raise SystemExit("PRIVATE_RELEASE_ASSETS_MISSING:"+",".join(missing))

    # Contract: verify every receipt asset against exact byte count and SHA-256 before parsing any asset.
    verified={}
    for name,exp in byname.items():
        meta=rassets[name]
        if int(meta.get("size",-1))!=int(exp.get("bytes",-2)): raise SystemExit(f"RELEASE_METADATA_SIZE_MISMATCH:{name}")
        aid=int(meta["id"])
        try:
            with gh_open(f"https://api.github.com/repos/{PRIVATE_REPO}/releases/assets/{aid}",read,"application/octet-stream",300) as r: data=r.read()
        except urllib.error.HTTPError as e: raise SystemExit(f"PRIVATE_ASSET_READ_FAILED:{name}:HTTP_{e.code}")
        if len(data)!=int(exp["bytes"]) or sha(data)!=exp["sha256"]: raise SystemExit(f"ASSET_VERIFICATION_FAILED:{name}:{len(data)}:{sha(data)}")
        verified[name]={"data":data,"asset_id":aid,"bytes":len(data),"sha256":sha(data),"role":exp.get("role"),"format":exp.get("format"),"source_url":exp.get("source_url")}
    print(cj({"gate":"ALL_ASSETS_VERIFIED_BEFORE_PARSE","asset_count":len(verified),"xls_count":len(xls)}),flush=True)

    import xlrd
    manifest=json.loads(verified["series-manifest.json"]["data"].decode("utf-8"))
    now=datetime.now(timezone.utc); stamp=now.strftime("%Y%m%dT%H%M%SZ")
    temp=pathlib.Path(os.environ.get("RUNNER_TEMP","/tmp"))/f"f187-{stamp}"; out=temp/"out"; shards=out/"row_shards"; meta_dir=out/"per_file_metadata"
    shards.mkdir(parents=True,exist_ok=True); meta_dir.mkdir(parents=True,exist_ok=True)
    wb_inv=[]; sheet_inv=[]; shard_meta=[]; schemas={}; total_rows=0; total_nonempty=0; total_nonblank_values=0
    row_fields=["source_file","source_file_sha256","source_file_bytes","reference_year","reference_quarter","edition_scope","sheet_index_1based","sheet_name","source_row_1based","schema_signature_sha256","motorway","concession","sublanco","tmdm","tmda","source_month_fields_json","row_measure_labels_json","blank_source_columns_1based_json","source_fields_json"]

    for exp in sorted(xls,key=lambda a:a["name"]):
        name=exp["name"]; data=verified[name]["data"]; per=period(name); book=xlrd.open_workbook(file_contents=data,on_demand=True)
        file_rows=[]; fm={"source_file":name,"bytes":len(data),"sha256":sha(data),**per,"sheet_count":book.nsheets,"sheets":[]}
        for si in range(book.nsheets):
            sh=book.sheet_by_index(si); trows=[]; prows=[]
            for r in range(sh.nrows):
                tr=[typed(book,sh.cell(r,c)) for c in range(sh.ncols)]; trows.append(tr); prows.append([x["value"] for x in tr])
            scores=sorted(((hscore(prows[r]),r) for r in range(min(sh.nrows,80))),reverse=True)
            best,hr=scores[0] if scores else (0,0); hs=max(0,hr-2); he=min(sh.nrows-1,hr+1) if sh.nrows else 0
            labels=[]; cmap={}; months={}
            for c in range(sh.ncols):
                parts=[]
                for rr in range(hs,he+1):
                    v=prows[rr][c]
                    if str(v).strip(): parts.append(str(v).strip())
                label=" | ".join(dict.fromkeys(parts)) if parts else f"col_{c+1:03d}"; labels.append(label)
                role=core_role(label)
                if role and role not in cmap: cmap[role]=c
                m=month_for(label)
                if m is not None: months[c]=m
            sig_obj={"sheet_name":sh.name,"ncols":sh.ncols,"header_window_rows_1based":[hs+1,he+1] if sh.nrows else [],"column_labels":labels,"core_column_map_1based":{k:v+1 for k,v in cmap.items()},"month_column_map_1based":{str(k+1):v for k,v in months.items()}}
            ss=sha(cj(sig_obj).encode()); schemas[ss]=schemas.get(ss,0)+1
            rev=[]; units=[]; notes=[]
            for r in range(sh.nrows):
                for c in range(sh.ncols):
                    v=prows[r][c]
                    if not isinstance(v,str) or not v.strip(): continue
                    n=norm(v)
                    if any(x in n for x in ["provisor","provis","revisto","revis","definitiv"]): rev.append({"row":r+1,"col":c+1,"text":v})
                    if any(x in n for x in ["veiculo","veiculos","veic/dia","veiculos/dia","quilomet"," km","percentagem"]): units.append({"row":r+1,"col":c+1,"text":v})
                    if any(x in n for x in ["nota","fonte","observ"]): notes.append({"row":r+1,"col":c+1,"text":v})
            nonempty=sum(1 for rr in trows for x in rr if x["type"]!="blank"); total_nonempty+=nonempty; file_count=0; nonblank_values=0
            for r in range(min(sh.nrows,he+1),sh.nrows):
                tr=trows[r]
                if not any(x["type"]!="blank" for x in tr): continue
                vals=[x["value"] for x in tr]; fields=[]; blanks=[]; month_fields={}
                for c,tc in enumerate(tr):
                    fields.append({"source_column_1based":c+1,"source_label":labels[c],"cell":tc})
                    if tc["type"]=="blank": blanks.append(c+1)
                    else:
                        nonblank_values+=1
                        if c in months: month_fields[str(months[c])] = {"source_label":labels[c],"cell":tc}
                core={k:vals[c] for k,c in cmap.items()}
                measure_labels=[v for v in vals if isinstance(v,str) and ("tmdm" in norm(v) or "tmda" in norm(v))]
                file_rows.append({"source_file":name,"source_file_sha256":sha(data),"source_file_bytes":len(data),**per,"sheet_index_1based":si+1,"sheet_name":sh.name,"source_row_1based":r+1,"schema_signature_sha256":ss,"motorway":core.get("motorway"),"concession":core.get("concession"),"sublanco":core.get("sublanco"),"tmdm":core.get("tmdm"),"tmda":core.get("tmda"),"source_month_fields_json":cj(month_fields),"row_measure_labels_json":cj(measure_labels),"blank_source_columns_1based_json":cj(blanks),"source_fields_json":cj(fields)})
                file_count+=1
            total_rows+=file_count; total_nonblank_values+=nonblank_values
            sm={"source_file":name,"sheet_index_1based":si+1,"sheet_name":sh.name,"nrows":sh.nrows,"ncols":sh.ncols,"nonempty_cells":nonempty,"header_score":best,"header_window_rows_1based":[hs+1,he+1] if sh.nrows else [],"column_labels":labels,"core_column_map_1based":{k:v+1 for k,v in cmap.items()},"month_column_map_1based":{str(k+1):v for k,v in months.items()},"schema_signature_sha256":ss,"revision_markers":rev[:100],"unit_hints":units[:100],"notes":notes[:100],"extracted_nonempty_rows":file_count,"published_nonblank_values":nonblank_values}
            fm["sheets"].append(sm); sheet_inv.append({"source_file":name,"reference_year":per["reference_year"],"reference_quarter":per["reference_quarter"],"edition_scope":per["edition_scope"],"sheet_index_1based":si+1,"sheet_name":sh.name,"nrows":sh.nrows,"ncols":sh.ncols,"nonempty_cells":nonempty,"header_score":best,"header_window_rows_1based_json":cj(sm["header_window_rows_1based"]),"column_labels_json":cj(labels),"core_column_map_1based_json":cj(sm["core_column_map_1based"]),"month_column_map_1based_json":cj(sm["month_column_map_1based"]),"schema_signature_sha256":ss,"revision_markers_json":cj(sm["revision_markers"]),"unit_hints_json":cj(sm["unit_hints"]),"notes_json":cj(sm["notes"]),"extracted_nonempty_rows":file_count,"published_nonblank_values":nonblank_values})
        book.release_resources()
        stem=safe_stem(name); rp=shards/(stem+"-rows.csv"); csv_write(rp,row_fields,file_rows); rb=rp.read_bytes()
        mp=meta_dir/(stem+"-metadata.json"); mp.write_text(json.dumps(fm,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); mb=mp.read_bytes()
        shard_meta.append({"source_file":name,"row_shard":str(rp.relative_to(out)),"row_count":len(file_rows),"row_shard_bytes":len(rb),"row_shard_sha256":sha(rb),"metadata_file":str(mp.relative_to(out)),"metadata_bytes":len(mb),"metadata_sha256":sha(mb)})
        wb_inv.append({"source_file":name,"bytes":len(data),"sha256":sha(data),**per,"sheet_count":fm["sheet_count"],"source_url":exp.get("source_url"),"extracted_rows":len(file_rows),"row_shard":str(rp.relative_to(out))})

    wb=out/"f187_workbook_inventory.csv"; csv_write(wb,["source_file","bytes","sha256","reference_year","reference_quarter","edition_scope","sheet_count","source_url","extracted_rows","row_shard"],wb_inv)
    si=out/"f187_sheet_inventory.csv"; csv_write(si,["source_file","reference_year","reference_quarter","edition_scope","sheet_index_1based","sheet_name","nrows","ncols","nonempty_cells","header_score","header_window_rows_1based_json","column_labels_json","core_column_map_1based_json","month_column_map_1based_json","schema_signature_sha256","revision_markers_json","unit_hints_json","notes_json","extracted_nonempty_rows","published_nonblank_values"],sheet_inv)
    smp=out/"f187_row_shards_manifest.json"; smp.write_text(json.dumps(shard_meta,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    verified_meta=[{"name":n,**{k:v for k,v in x.items() if k!="data"}} for n,x in verified.items()]
    ingress={"schema_version":"4.0.7","worker":"W2C","wake_mission_generation":WAKE_GENERATION,"assignment_origin_generation":ASSIGNMENT_ORIGIN_GENERATION,"package":"F187_IMT_MOTORWAY_TRAFFIC_XLS_DETERMINISTIC_EXTRACTION_INGRESS","source_set_id":SOURCE_SET_ID,"native_asset_fingerprint":FINGERPRINT,"private_release_tag":RELEASE_TAG,"private_receipt":PRIVATE_RECEIPT,"verification":{"all_receipt_assets_verified_before_any_parse":True,"asset_count":len(verified_meta),"xls_workbook_count":len(xls),"assets":verified_meta},"source_family":{"series_manifest":manifest,"workbook_count":len(wb_inv),"sheet_count":len(sheet_inv),"source_native_nonempty_rows":total_rows,"source_native_nonempty_cells":total_nonempty,"published_nonblank_values":total_nonblank_values,"schema_signature_count":len(schemas),"schema_signature_occurrences":schemas,"row_shards":shard_meta},"semantic_contract":{"evidence_class":"OBSERVED_TRAFFIC_SOURCE","source_native_only":True,"edition_file_preserved":True,"sheet_table_identity_preserved":True,"motorway_concession_sublanco_only_when_source_header_detection_supports":True,"reference_year_quarter_from_source_filename_only":True,"month_values_preserved_only_for_unambiguous_source_month_labels":True,"tmdm_tmda_only_when_exact_source_header_token_supports":True,"other_published_fields_preserved_verbatim_in_source_fields_json":True,"revision_provisional_text_preserved_as_source_markers":True,"source_unit_hints_preserved_verbatim":True,"blanks_missingness_preserved":True,"schema_drift_preserved_by_sheet_signature":True,"editions_harmonized":False,"annual_quarterly_reconciled":False,"f05_joined":False,"crosswalks_invented":False,"producer_reacquisition":False,"rights_adjudication":False},"limitations":["XLS formula source text is not exposed by xlrd; calculated cell values/types are extracted while exact verified XLS remains canonical.","Header/core-field detection is extraction aid only; W2B owns semantic normalization and cross-edition reconciliation."]}
    ip=out/"f187_source_native_ingress.json"; ip.write_text(json.dumps(ingress,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    outs=[wb,si,smp,ip]+sorted(shards.glob("*.csv"))+sorted(meta_dir.glob("*.json")); om=[]
    for p in outs:
        b=p.read_bytes(); om.append({"relative_path":str(p.relative_to(out)),"bytes":len(b),"sha256":sha(b)})
    largest=max(om,key=lambda x:x["bytes"])
    print(cj({"gate":"EXTRACTION_BUILT","rows":total_rows,"sheets":len(sheet_inv),"schemas":len(schemas),"largest_output":largest,"total_output_bytes":sum(x["bytes"] for x in om)}),flush=True)
    if largest["bytes"]>50_000_000: raise SystemExit(f"OUTPUT_SHARD_TOO_LARGE:{largest['relative_path']}:{largest['bytes']}")

    outbase=f"statistics/recovery-20260920/simple-runtime/outputs/W2C/{stamp}-G43-F187-extraction-ingress"; handoff=f"statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F187/{FINGERPRINT}-extraction.json"
    er={"schema_version":"4.0.7","worker":"W2C","wake_mission_generation":WAKE_GENERATION,"assignment_origin_generation":ASSIGNMENT_ORIGIN_GENERATION,"package":"F187_IMT_MOTORWAY_TRAFFIC_XLS_DETERMINISTIC_EXTRACTION_INGRESS","source_set_id":SOURCE_SET_ID,"native_asset_fingerprint":FINGERPRINT,"private_release_tag":RELEASE_TAG,"status":"PASS_PRIVATE_PRESERVED_ASSET_SET_VERIFIED_BEFORE_PARSE_AND_SOURCE_NATIVE_XLS_INGRESS_EMITTED","asset_set_verified_before_parse":True,"verified_asset_count":len(verified_meta),"verified_xls_workbook_count":len(xls),"source_native_nonempty_rows":total_rows,"published_nonblank_values":total_nonblank_values,"sheet_count":len(sheet_inv),"schema_signature_count":len(schemas),"observed_traffic_source":True,"editions_harmonized":False,"annual_quarterly_reconciled":False,"f05_joined":False,"producer_reacquisition":False,"consumer_joins":False,"rights_adjudication":False,"outputs":[{"path":outbase+"/"+x["relative_path"],"bytes":x["bytes"],"sha256":x["sha256"]} for x in om],"canonical_extraction_receipt_path":handoff,"next_owner":"W2B","next_state":"READY_NORMALIZATION_HANDOFF"}
    ep=out/"extraction-receipt.json"; ep.write_text(json.dumps(er,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    team=json.loads(private_text("statistics/recovery-20260920/simple-runtime/team-missions.json",read)); c=(((team.get("teams") or {}).get("W2") or {}).get("C") or {}); binding=cj(c)
    if SOURCE_SET_ID not in binding or FINGERPRINT not in binding: raise SystemExit("CURRENT_W2C_ASSIGNMENT_NO_LONGER_CONTAINS_EXACT_F187_FINGERPRINT")
    current_gen=int(team.get("mission_generation",-1))
    clone=temp/"private"; env=os.environ.copy(); env["GIT_TERMINAL_PROMPT"]="0"; url=f"https://x-access-token:{write}@github.com/{PRIVATE_REPO}.git"
    subprocess.run(["git","clone","--depth","1","--branch",PRIVATE_BRANCH,url,str(clone)],check=True,env=env,stdout=subprocess.DEVNULL)
    c2=(((json.loads((clone/"statistics/recovery-20260920/simple-runtime/team-missions.json").read_text(encoding="utf-8")).get("teams") or {}).get("W2") or {}).get("C") or {})
    if SOURCE_SET_ID not in cj(c2) or FINGERPRINT not in cj(c2): raise SystemExit("W2C_ASSIGNMENT_CHANGED_AFTER_CLONE")
    dst=clone/outbase; dst.mkdir(parents=True,exist_ok=True)
    for p in outs+[ep]:
        q=dst/p.relative_to(out); q.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,q)
    hp=clone/handoff; hp.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ep,hp)
    wp=clone/"statistics/recovery-20260920/simple-runtime/worker-W2C.json"
    worker={"schema_version":"4.0.7","worker":"W2C","team":"W2","partner":"C","mission_generation":WAKE_GENERATION,"assignment_origin_generation":ASSIGNMENT_ORIGIN_GENERATION,"team_mission_generation_observed_before_private_write":current_gen,"updated_at":now.isoformat().replace("+00:00","Z"),"status":"READY_NORMALIZATION_HANDOFF","elastic_state":"STANDBY_EXTRACTION_INGRESS","current_task":None,"last_output":outbase+"/extraction-receipt.json","window":{"mission":"Exact fingerprint-pinned F187 IMT motorway-traffic XLS deterministic extraction ingress; no producer reacquisition.","material_packages":1,"source_id":SOURCE_SET_ID,"native_asset_fingerprint":FINGERPRINT,"private_release_tag":RELEASE_TAG,"all_assets_verified_before_parse":True,"verified_asset_count":len(verified_meta),"xls_workbook_count":len(xls),"sheet_count":len(sheet_inv),"source_native_nonempty_rows":total_rows,"published_nonblank_values":total_nonblank_values,"schema_signature_count":len(schemas),"result":"PASS_F187_SOURCE_NATIVE_XLS_EXTRACTION_INGRESS","producer_requests_sent":0,"producer_reacquisitions":0,"consumer_joins":0,"rights_adjudications":0,"f05_joined":False,"editions_harmonized":False,"outputs":[outbase+"/"+x["relative_path"] for x in om]+[outbase+"/extraction-receipt.json",handoff],"canonical_extraction_receipt":handoff,"next_cursor":["W2B: consume exact extraction receipt and normalize source-native traffic rows preserving edition/file, sheet/table, period, motorway/concession/sublanco, labels/units, revision markers, blanks and schema signatures.","Reconcile annual versus quarterly editions explicitly in W2B; do not silently replace revisions.","Do not join F05 in W2C."]},"blocker":None}
    wp.write_text(json.dumps(worker,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    subprocess.run(["git","-C",str(clone),"config","user.name","mobilidade-public-sources[bot]"],check=True); subprocess.run(["git","-C",str(clone),"config","user.email","actions@users.noreply.github.com"],check=True)
    paths=[outbase,handoff,"statistics/recovery-20260920/simple-runtime/worker-W2C.json"]; subprocess.run(["git","-C",str(clone),"add","--"]+paths,check=True); subprocess.run(["git","-C",str(clone),"commit","-m","result(mn): W2C F187 source-native XLS extraction ingress"],check=True,stdout=subprocess.DEVNULL)
    pushed=False
    for i in range(4):
        p=subprocess.run(["git","-C",str(clone),"push","origin",PRIVATE_BRANCH],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if p.returncode==0: pushed=True; break
        print(cj({"push_attempt":i+1,"stderr_tail":p.stderr[-2000:]}),flush=True)
        subprocess.run(["git","-C",str(clone),"pull","--rebase","origin",PRIVATE_BRANCH],check=True,env=env,stdout=subprocess.DEVNULL)
    if not pushed: raise SystemExit("PRIVATE_HANDOFF_PUSH_FAILED_AFTER_REBASE")
    print(cj({"status":"PASS","source_set_id":SOURCE_SET_ID,"fingerprint":FINGERPRINT,"output_base":outbase,"verified_assets":len(verified_meta),"xls_workbooks":len(xls),"sheets":len(sheet_inv),"source_native_rows":total_rows,"published_nonblank_values":total_nonblank_values,"schema_signatures":len(schemas),"handoff":handoff}),flush=True)

if __name__=="__main__": main()
