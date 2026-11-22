"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/acquisition/"
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
CACHE={}
for asset,n,expected,members in ARCH:
    wanted={sid:name for sid,name in members.items() if sid not in CACHE}
    if not wanted: continue
    try:
        with tempfile.TemporaryDirectory() as td:
            z=pathlib.Path(td)/"source.zip"
            h=hashlib.sha256(); size=0
            with gh("releases/assets/"+str(asset),binary=True) as src,z.open("wb") as dst:
                while True:
                    b=src.read(1024*1024)
                    if not b: break
                    dst.write(b); h.update(b); size+=len(b)
                    if size>n: raise ValueError("archive size exceeds pinned size")
            if size!=n or h.hexdigest()!=expected: raise ValueError("archive identity mismatch")
            with zipfile.ZipFile(z) as za:
                for sid,name in wanted.items():
                    paths=[p for p in za.namelist() if pathlib.PurePosixPath(p).name==name]
                    if len(paths)!=1:
                        receipt(sid,"archive","MEMBER_NOT_UNIQUE",asset_id=asset,member_matches=len(paths));continue
                    b=za.read(paths[0])
                    obj=json.loads(b)
                    role="c_load" if sid=="F140" else "c_unload"
                    rows=jsonstat(obj,road_pred(role)) if sid in ["F140","F141"] else ine_rows(obj,PORTUGAL_GEO if sid=="F101" else ["19"],["2024","2025"])
                    CACHE[sid]=rows
                    store(sid+"-preserved-selection.json",{"asset_id":asset,"archive_sha256":expected,"member":paths[0],"member_sha256":sha(b),"source_metadata":{k:obj.get(k) for k in ["id","size","updated","label"]} if isinstance(obj,dict) else None,"rows":rows})
                    receipt(sid,"archive","PRESERVED_SELECTION",asset_id=asset,rows=len(rows),numeric_rows=sum(r.get("value") is not None for r in rows) if sid in ["F140","F141"] else sum(bool(r["native"].get("valor")) for r in rows))
    except Exception as e:
        receipt("ARCHIVE","read","ERROR",asset_id=asset,error_type=type(e).__name__)
# Producer calls are sequential; do not send private credentials to any producer.
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

# Road freight: current Centro and legacy code kept distinct; 2025 refresh for all 4 regions.
for sid,ds,role in [("F140","road_go_ta_rl","c_load"),("F141","road_go_ta_ru","c_unload")]:
    old=CACHE.get(sid,[])
    for yr,regions in [("2024",C2),("2025",list(dict.fromkeys(R2+C2)))]:
        # Missing scope only; preserve flags, no fill for absent values.
        missing=[g for g in regions if not any(r["coord"].get(role)==g and r["coord"].get("time")==yr and r["coord"].get("geo")=="EU27_2020" and r["coord"].get("unit")=="THS_T" and r["value"] is not None for r in old)]
        if missing:
            euro(sid,ds,[(role,missing),("unit",UNITS),("geo",REPORTERS),("time",yr)],"gap-"+yr,road_pred(role))
        else: receipt(sid,"gap-"+yr,"PRESERVED_COVERAGE")
# NUTS III physical marginals: current-year codes only. 2019–23 cannot be spliced to changes of NUTS.
for sid,ds in [("F01","road_go_na_rl3g"),("F02","road_go_na_ru3g")]:
    euro(sid,ds,[("geo",C3),("nst07","TOTAL"),("unit","THS_T"),("time",["2024","2025"])],"centro-nuts3",lambda c:c.get("geo") in C3 and c.get("time") in ["2024","2025"])
# Historical rail OD directed records, not the current valid-empty edition.
for yr in ["2015","2020"]:
    euro("F148","tran_r_rago",[("time",yr),("c_load",["PT11"]+C2),("c_unload",["PT11"]+C2)],"historical-"+yr,lambda c:c.get("c_load") in ["PT11"]+C2 and c.get("c_unload") in ["PT11"]+C2)
# Trade: restore archive before API; use exact current NUTS codes.
for sid,code in [("F75","0012347"),("F101","0012348")]:
    for yr in ["2024","2025"]:
        targets=["19"] if sid=="F75" else PORTUGAL_GEO
        got={r["native"].get("geocod") for r in CACHE.get(sid,[]) if r["period"]==yr and r["native"].get("valor") is not None}
        missing=[g for g in targets if g not in got]
        if missing: ine(sid,code,yr,missing,"gap-"+yr)
        else: receipt(sid,"gap-"+yr,"PRESERVED_COVERAGE")
# Regional economic structure (reuse F24 concept; no invented H-only values).
euro("F24","nama_10r_3gva",[("geo",N3+C3),("nace_r2",["TOTAL","B-E","C"]),("unit","CP_MEUR"),("time","2024")],"regional-gva-2024",lambda c:c.get("geo") in N3+C3)
# Statistical harmonization supplements, not admitted as canonical source sets.
euro("candidate-population","demo_r_pjanaggr3",[("geo",N3+C3),("sex","T"),("age","TOTAL"),("unit","NR"),("time",["2024","2025"])],"nuts3",lambda c:c.get("geo") in N3+C3)
store("receipt.json",{"schema_version":"1.0","created":datetime.now(timezone.utc).isoformat(),"status":"INTERNAL_ACQUISITION_RECEIPT_NOT_CANONICAL_ADMISSION","source_ids_preserved":True,"publication_authorized":False,"no_credentials_in_output":True,"workflow_run_id":os.environ.get("GITHUB_RUN_ID"),"requests":RECEIPTS,"files":sorted(OUT),"unresolved":["No road NUTS2 OD inferred from marginals","No current 2024+ rail OD inferred from F148","No conversion of PT16 into PT19","No PReMMIA bilateral values inferred from regional totals"]})
# Atomic private git commit, optimistic branch lease; no publication or canonical changes.
for attempt in range(3):
    head=gh("git/ref/heads/"+BRANCH)["object"]["sha"]
    tree=gh("git/commits/"+head)["tree"]["sha"]
    entries=[{"path":ROOT+name,"mode":"100644","type":"blob","content":content} for name,content in OUT.items()]
    nt=gh("git/trees","POST",{"base_tree":tree,"tree":entries},write=True)["sha"]
    new=gh("git/commits","POST",{"message":"MN: Norte-Centro preserved-first targeted acquisition results","tree":nt,"parents":[head]},write=True)["sha"]
    try:
        gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True)
        print("PRIVATE_COMMIT",new,"FILES",len(OUT),flush=True); break
    except urllib.error.HTTPError:
        if attempt==2: raise
        time.sleep(2)
