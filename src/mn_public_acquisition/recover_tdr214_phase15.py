"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase15/"
READ = os.environ.get("MN_PRIVATE_READ_TOKEN") or os.environ.get("MN_PRIVATE_SINK_TOKEN")
WRITE = os.environ.get("MN_PRIVATE_SINK_TOKEN")
if not READ or not WRITE:
    raise SystemExit("MN_PRIVATE_READ_AND_SINK_TOKEN_REQUIRED")
C3 = ["PT191","PT192","PT193","PT194","PT195","PT196"]
N3 = ["PT111","PT112","PT119","PT11A","PT11B","PT11C","PT11D","PT11E"]
C2 = ["PT19","PT16"]
R2 = ["PT11","PT19","ES11","ES41"]
UNITS = ["THS_T","MIO_TKM","THS_JRNY"]
REPORTERS = ["EU27_2020","PT","ES"]
PORTUGAL_GEO = ["11","19"] + [g[2:] for g in N3+C3]
OUT = {}
RECEIPTS = []
ARCH = [
  (565876530,477522937,"60d6e818aa81c1e710a6b41953e68fee6f50abe494e7363f8f175f7b8e568084",{
   "F140":"F140_Eurostat_road_go_ta_rl_2024.json","F141":"F141_Eurostat_road_go_ta_ru_2024.json"}),
  (565354564,30084213,"7716fc40fda89acc2a8a91bcfbde12ba6b890d185f928674ce69ea160360a724",{
   "F75":"0012347_data.json","F101":"0012348_data.json"}),
  (565428232,44717128,"cbc55316dded629a72a88b861d5f2a09d8a5bb078adc0345d4423b86e6dee168",{
   "F75":"0012347_data.json","F101":"0012348_data.json"})
]

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        nxt = super().redirect_request(req,fp,code,msg,headers,newurl)
        if nxt and urllib.parse.urlparse(newurl).hostname != urllib.parse.urlparse(req.full_url).hostname:
            nxt.remove_header("Authorization")
        return nxt
OPENER = urllib.request.build_opener(SafeRedirect())
def sha(b): return hashlib.sha256(b).hexdigest()
def gh(path, method="GET", body=None, write=False, binary=False):
    h={"Authorization":"Bearer "+(WRITE if write else READ),"Accept":"application/octet-stream" if binary else "application/vnd.github+json","User-Agent":"MobilidadeNorte-NorteCentro/1.0","X-GitHub-Api-Version":"2022-11-28"}
    data=None
    if body is not None: h["Content-Type"]="application/json"; data=json.dumps(body).encode()
    req=urllib.request.Request("https://api.github.com/repos/"+PRIVATE+"/"+path,data=data,headers=h,method=method)
    if binary: return OPENER.open(req,timeout=180)
    with OPENER.open(req,timeout=120) as resp: return json.load(resp)
def store(name,obj): OUT[name]=(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
def receipt(sid,stage,state,**kw):
    RECEIPTS.append({"source_id":sid,"stage":stage,"state":state,**kw})
    print(sid,stage,state,kw.get("numeric_rows",kw.get("rows","")),flush=True)
def jsonstat(obj, predicate):
    ids=obj.get("id",[]); sizes=obj.get("size",[])
    if len(ids)!=len(sizes) or not ids: raise ValueError("not JSON-stat")
    if not all(sizes): return []
    labels=[]
    for d,size in zip(ids,sizes):
        index=obj["dimension"][d]["category"]["index"]
        inv=index if isinstance(index,list) else sorted(index,key=index.get)
        if len(inv)!=size: raise ValueError("dimension size mismatch")
        labels.append(inv)
    values=obj.get("value",{}); statuses=obj.get("status",{})
    if isinstance(values,list): values={str(i):v for i,v in enumerate(values) if v is not None}
    if isinstance(statuses,list): statuses={str(i):v for i,v in enumerate(statuses) if v}
    ret=[]
    for k in set(values)|set(statuses):
        ix=int(k); coords=[]
        for size, inv in zip(reversed(sizes),reversed(labels)):
            ix,r=divmod(ix,size); coords.append(inv[r])
        if ix: raise ValueError("native offset outside cube")
        c=dict(zip(ids,reversed(coords)))
        if predicate(c): ret.append({"coord":c,"value":values.get(k),"status":statuses.get(k)})
    return sorted(ret,key=lambda r:tuple(r["coord"][k] for k in ids))

def ine_rows(obj,geos,years):
    if isinstance(obj,dict):
        obj=obj.get("source_body",obj.get("data",[obj]))
    if not isinstance(obj,list): raise ValueError("INE body not list")
    ret=[]
    for block in obj:
        if not isinstance(block,dict) or "Dados" not in block: continue
        for yr,rr in block["Dados"].items():
            if str(yr) not in years or not isinstance(rr,list): continue
            for r in rr:
                if r.get("geocod") in geos:
                    ret.append({"period":str(yr),"native":r})
    return ret
def road_pred(role):
    return lambda c: (c.get(role) in C2 or (c.get("time")=="2025" and c.get(role) in R2)) and c.get("time") in ["2024","2025"] and c.get("unit") in UNITS and c.get("geo") in REPORTERS
def get_public(url):
    for attempt in range(3):
        try:
            with OPENER.open(urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte/1.0","Accept":"application/json"}),timeout=45) as r:
                raw=r.read(8_000_001)
            if len(raw)>8_000_000: raise ValueError("bounded source response exceeded cap")
            return raw,json.loads(raw)
        except (urllib.error.URLError,TimeoutError):
            if attempt==2: raise
            time.sleep(2**attempt)
def euro(sid,dataset,params,label,pred):
    url="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"+dataset+"?"+urllib.parse.urlencode([("lang","EN")]+params,doseq=True)
    try:
        raw,obj=get_public(url)
        rows=jsonstat(obj,pred)
        num=sum(r["value"] is not None for r in rows)
        store(sid+"-"+label+".json",{"source_id":sid,"url":url,"sha256":sha(raw),"source_body":obj,"rows":rows,"numeric_rows":num,"semantic_guard":"native dimension roles and flags retained; absent is not zero"})
        receipt(sid,label,"PASS" if num else "VALID_EMPTY_OR_FLAG_ONLY",rows=len(rows),numeric_rows=num)
        return rows
    except Exception as e:
        receipt(sid,label,"ERROR",error_type=type(e).__name__,http_code=getattr(e,"code",None)); return []
def ine(sid,code,yr,geos,label):
    url="https://www.ine.pt/ine/json_indicador/pindica.jsp?"+urllib.parse.urlencode({"op":2,"varcd":code,"lang":"PT","Dim1":"S7A"+yr,"Dim2":",".join(geos)})
    try:
        raw,obj=get_public(url)
        rows=ine_rows(obj,geos,[yr])
        num=sum(bool(r["native"].get("valor")) for r in rows)
        store(sid+"-"+label+".json",{"source_id":sid,"url":url,"sha256":sha(raw),"source_body":obj,"rows":rows,"numeric_rows":num,"semantic_guard":"operator geography; mixed hierarchy non-additive; not physical OD"})
        receipt(sid,label,"PASS" if num else "EMPTY_OR_ERROR_BODY",rows=len(rows),numeric_rows=num)
    except Exception as e:
        receipt(sid,label,"ERROR",error_type=type(e).__name__,http_code=getattr(e,"code",None))



import csv, io, re, subprocess, xml.etree.ElementTree as ET
BASE="statistics/assessments/norte-centro-2026-11-22/phase2/"
BLOBS={}
def read_private(path):
    meta=gh("contents/"+urllib.parse.quote(path)+"?ref="+BRANCH)
    blob=gh("git/blobs/"+meta["sha"])
    raw=base64.b64decode(blob["content"])
    return raw,meta["sha"]
def add_blob(path,raw):
    BLOBS[path]=gh("git/blobs","POST",{"content":base64.b64encode(raw).decode(),"encoding":"base64"},write=True)["sha"]
def csvbytes(headers,rows):
    f=io.StringIO(newline=""); w=csv.writer(f);w.writerow(headers);w.writerows(rows);return f.getvalue().encode("utf-8")
def source_xlsx(name,raw,source_path,source_sha):
    ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    counts=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        shared=[]
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si",ns):
                shared.append("".join(t.text or "" for t in si.findall(".//m:t",ns)))
        rels={r.attrib["Id"]:r.attrib["Target"] for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        for sheet in ET.fromstring(z.read("xl/workbook.xml")).findall(".//m:sheet",ns):
            label=sheet.attrib["name"]
            target=rels[sheet.attrib["{"+ns["r"]+"}id"]]
            target=target.lstrip("/") if target.startswith("/") else "xl/"+target
            root=ET.fromstring(z.read(target)); cells=[]
            for cell in root.findall(".//m:sheetData/m:row/m:c",ns):
                v=cell.find("m:v",ns); formula=cell.find("m:f",ns); kind=cell.attrib.get("t","n")
                value=v.text if v is not None else None
                if kind=="s" and value is not None: value=shared[int(value)]
                elif kind=="inlineStr": value="".join(t.text or "" for t in cell.findall(".//m:t",ns))
                if value is not None or formula is not None:
                    cells.append([cell.attrib["r"],kind,value,formula.text if formula is not None else "",cell.attrib.get("s","")])
            path="cells/"+re.sub(r"[^a-zA-Z0-9_.-]","_",name+"-"+label)+".csv"
            add_blob(path,csvbytes(["cell","native_type","native_value","formula","style_id"],cells))
            counts.append({"sheet":label,"cells":len(cells),"path":ROOT+path,"header_sample":cells[:35]})
    receipt(name,"extract_workbook_cells","PASS",source=source_path,source_blob=source_sha,source_sha256=sha(raw),sheets=counts)







from collections import defaultdict,Counter
import concurrent.futures
PARENT="statistics/assessments/norte-centro-2026-11-22/"
def readcsv(path):
    b,s=read_private(path);return list(csv.reader(io.StringIO(b.decode("utf-8-sig")))),s
def readj(path):
    b,s=read_private(path);return json.loads(b)
def writecsv(p,h,rows):add_blob(p,csvbytes(h,rows))
def query(code,params):
    u="https://www.ine.pt/ine/json_indicador/pindica.jsp?"+urllib.parse.urlencode({"op":2,"varcd":code,"lang":"PT",**params})
    b,j=get_public(u);rs=[(y,r) for block in j if isinstance(block,dict) for y,rr in block.get("Dados",{}).items() for r in rr]
    return u,b,j,rs
def commit(label):
    store("receipt.json",{"status":label,"publication_authorized":False,"run_id":os.environ.get("GITHUB_RUN_ID"),"requests":RECEIPTS,"blobs":BLOBS})
    for attempt in range(5):
        head=gh("git/ref/heads/"+BRANCH)["object"]["sha"];tree=gh("git/commits/"+head)["tree"]["sha"]
        entries=[{"path":ROOT+n,"mode":"100644","type":"blob","content":c} for n,c in OUT.items()]+[{"path":ROOT+n,"mode":"100644","type":"blob","sha":s} for n,s in BLOBS.items()]
        nt=gh("git/trees","POST",{"base_tree":tree,"tree":entries},write=True)["sha"]
        new=gh("git/commits","POST",{"message":"MN: F20 cache reconciliation and residual totals","tree":nt,"parents":[head]},write=True)["sha"]
        try:
            gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_CHECKPOINT",new,flush=True);return
        except urllib.error.HTTPError:
            if attempt==4:raise
            time.sleep(2)

import gzip
from decimal import Decimal
# Replay the validated archive; no extra download of its source.
r=readj(PARENT+"phase14/receipt.json")
assert any(x["stage"]=="release_normalize" and x["state"]=="PASS" for x in r["requests"])
tot,_=readcsv(PARENT+"phase14/F20-monthly-nuts2-totals.csv")
b,_=read_private(PARENT+"phase14/F20-monthly-municipal-totals.csv.gz")
munrows=list(csv.DictReader(io.StringIO(gzip.decompress(b).decode())))
a=defaultdict(list)
for x in munrows:a[(x["month"],x["geo"][:2])].append(Decimal(x["eur"]))
checks=[];monthly=defaultdict(dict)
for x in [dict(zip(tot[0],row)) for row in tot[1:]]:
    k=(x["month"],x["geo"]);vals=a[k];ex=86 if x["geo"]=="11" else 77;v=Decimal(x["eur"]);d=sum(vals)-v;monthly[x["geo"]][x["month"]]=v
    checks.append([*k,v,len(vals),ex,sum(vals),d,"MATCH" if len(vals)==ex and d==0 else "DIFFERENCE"])
writecsv("F20-cache-municipal-reconciliation.csv",["month","geo","official_eur","municipal_count","expected_count","municipal_sum_eur","difference_eur","state"],checks)
ytd=[]
for g,months in monthly.items():
    for yr in range(2022,2027):
        vals=[months.get(f"{yr}-{m:02}") for m in range(1,8)]
        if all(v is not None for v in vals):ytd.append([g,yr,"Jan-Jul",str(sum(vals))])
writecsv("F20-jan-jul-panel.csv",["geo","year","period","eur"],ytd)
receipt("F20","archive_reconciliation","PASS",comparisons=len(checks),exact_matches=sum(x[-1]=="MATCH" for x in checks),max_abs_difference_eur=str(max(abs(x[-2]) for x in checks)),ytd=ytd,guard="Archived September 2026 producer vintage; do not join revisions silently.")
commit("ARCHIVE_QA_COMPLETE")
# Correct the actual INE CAE total code (TOT), not T.
raw,_=readcsv(PARENT+"phase7/ine/F22-municipal-normalized.csv")
rows={(x[0],x[1],x[3]):x for x in raw[1:]}
gs=sorted({x[1] for x in raw[1:]});todo=[g for g in gs if ("2024",g,"TOT") not in rows]
for i in range(0,len(todo),40):
    part=todo[i:i+40]
    try:
        u,b,j,rs=query("0013863",{"Dim1":"S7A2024","Dim2":",".join(part),"Dim3":"TOT"})
        p=f"raw/F22-total-{i:03}.json";add_blob(p,b)
        assert all(k["dim_3"]=="TOT" and k["geocod"] in part for y,k in rs)
        for y,k in rs:rows[(str(y),k["geocod"],"TOT")]=[str(y),k["geocod"],k.get("geodsg",""),"TOT",k.get("dim_3_t",""),k.get("valor",""),k.get("sinal_conv",""),ROOT+p]
        receipt("F22","TOT_batch","PASS" if rs else "ERROR_BODY",rows=len(rs),requested=len(part),url=u)
    except Exception as e:receipt("F22","TOT_batch","ERROR",detail=str(e)[:200])
writecsv("F22-municipal-completed.csv",raw[0],rows.values())
tt=[x for k,x in rows.items() if k[2]=="TOT"]
receipt("F22","actual_total_reconciliation","PASS" if len(tt)==163 else "PARTIAL",rows=len(rows),numeric=sum(bool(x[5]) for x in rows.values()),municipalities=len(gs),total_cells=len(tt),total_numeric=sum(bool(x[5]) for x in tt))
turn,_=readcsv(PARENT+"phase13/ine/establishment-turnover-municipal-completed.csv")
tt=[x for x in turn[1:] if x[3]=="TOT"]
receipt("0012932","actual_total_reconciliation","PASS" if len(tt)==163 else "PARTIAL",rows=len(turn)-1,total_cells=len(tt),total_numeric=sum(bool(x[5]) for x in tt),municipalities=len({x[1] for x in turn[1:]}))
commit("MUNICIPAL_QA_COMPLETE")
# Only the two new months, targeted totals first, parallel independent calls.
def recent(m):
    u="https://www.ine.pt/ine/json_indicador/pindica.jsp?"+urllib.parse.urlencode({"op":2,"varcd":"0012087","lang":"PT","Dim1":"S3A2026"+m,"Dim2":"11,19","Dim3":"T","Dim4":"T"})
    try:
        with OPENER.open(urllib.request.Request(u,headers={"User-Agent":"MobilidadeNorte/1.0","Accept":"application/json"}),timeout=25) as rr:b=rr.read(1_000_000)
        j=json.loads(b);rs=[(y,k) for block in j if isinstance(block,dict) for y,v in block.get("Dados",{}).items() for k in v]
        return m,u,b,rs,None
    except Exception as e:return m,u,b"",[],str(e)[:200]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for m,u,b,rs,err in pool.map(recent,["08","09"]):
        if b:add_blob(f"raw/F20-2026{m}-nuts2.json",b)
        good=[k for y,k in rs if k.get("geocod") in {"11","19"} and k.get("dim_3")=="T" and k.get("dim_4")=="T" and k.get("valor") not in (None,"")]
        if len(good)==2:writecsv(f"F20-2026{m}-nuts2-totals.csv",["month","geo","eur","flag"],[["2026-"+m,k["geocod"],k["valor"],k.get("sinal_conv","")] for k in good])
        receipt("F20","new-month-2026-"+m,"PASS" if len(good)==2 else "ERROR_OR_PARTIAL",rows=len(good),data=good,detail=err,url=u)
commit("COMPLETE_ATTEMPT")
