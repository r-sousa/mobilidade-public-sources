"""NV41 targeted acquisition. Private sink; no private data in logs or public releases."""
import os,json,hashlib,base64,urllib.request,urllib.parse,subprocess,tempfile,pathlib,sys,time,re,concurrent.futures
REPO="r-sousa/EU-transp-weekly"
REF="norte2040-tdr214-visual-catalogue"
SRCREF="mobilidade-norte-recovery-20260919"
ROOT="statistics/assessments/norte2040-tdr214/visuals/"
DATA="statistics/assessments/norte-centro-2026-11-22/"
READ=os.environ.get("MN_PRIVATE_READ_TOKEN") or os.environ.get("MN_PRIVATE_SINK_TOKEN")
WRITE=os.environ.get("MN_PRIVATE_SINK_TOKEN")
if not READ or not WRITE:raise SystemExit("Private bridge tokens unavailable")
class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        nxt=super().redirect_request(req,fp,code,msg,headers,newurl)
        if nxt and urllib.parse.urlparse(newurl).hostname!=urllib.parse.urlparse(req.full_url).hostname:nxt.remove_header("Authorization")
        return nxt
opener=urllib.request.build_opener(SafeRedirect())
def gh(path,body=None,method="GET",write=False):
    h={"Authorization":"Bearer "+(WRITE if write else READ),"Accept":"application/vnd.github+json","User-Agent":"Norte2040-visual-render/1.0"}
    if body is not None:h["Content-Type"]="application/json"
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+"/"+path,data=json.dumps(body).encode() if body is not None else None,headers=h,method=method)
    for n in range(3):
        try:
            with opener.open(req,timeout=120) as f:return json.load(f)
        except Exception:
            if write or n==2:raise
            time.sleep(2**n)
def blob(pin):
    z=gh("git/blobs/"+pin);b=base64.b64decode(z["content"])
    assert hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()==pin
    return b
def file(path,ref,pin=None):
    m=gh("contents/"+urllib.parse.quote(path,safe="/")+"?ref="+urllib.parse.quote(ref,safe=""))
    if pin:assert m["sha"]==pin
    return blob(m["sha"])
def sha(raw):return hashlib.sha256(raw).hexdigest()


import csv,io,gzip,math,itertools,unicodedata
from openpyxl import load_workbook
from mn_public_acquisition.ine_partitioned import _dimension_items,_dimensions,_period_labels,_resolve_label,_flatten
OUT=ROOT+"NV41/"
rec={"run_id":os.environ.get("GITHUB_RUN_ID"),"sources":{},"status":"IN_PROGRESS","publication_authorized":False}
files={}
def dump(obj):return (json.dumps(obj,ensure_ascii=False,indent=2,default=str)+"\n").encode()
def store(name,raw):files[name]=raw
def commit():
    files["acquisition-receipt.json"]=dump(rec)
    entries=[]
    for name,raw in files.items():
        assert len(raw)<25_000_000
        z=gh("git/blobs",{"content":base64.b64encode(raw).decode(),"encoding":"base64"},"POST",True)
        entries.append({"path":OUT+name,"mode":"100644","type":"blob","sha":z["sha"]})
    for i in range(4):
        head=gh("git/ref/heads/"+REF)["object"]["sha"];tree=gh("git/commits/"+head)["tree"]["sha"]
        nt=gh("git/trees",{"base_tree":tree,"tree":entries},"POST",True)["sha"]
        c=gh("git/commits",{"message":"NV41: preserved native evidence and reproducible outputs","tree":nt,"parents":[head]},"POST",True)["sha"]
        try:gh("git/refs/heads/"+REF,{"sha":c,"force":False},"PATCH",True);files.clear();return
        except Exception:
            if i==3:raise
            time.sleep(2)
def public(url,cap=20_000_000,timeout=45):
    req=urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte-NV41/1.0","Accept":"application/json"})
    with opener.open(req,timeout=timeout) as f:raw=f.read(cap+1)
    if len(raw)>cap:raise ValueError("response cap exceeded")
    return raw
def norm(v):return "".join(c for c in unicodedata.normalize("NFKD",str(v).casefold()) if not unicodedata.combining(c)).strip()
def err(name,e):rec["sources"][name]={"state":"ERROR","type":type(e).__name__,"detail":str(e)[:160]};print(name,type(e).__name__,flush=True)

# Focused recovery: exact series only, no reacquisition of F49 assets.
def query_one(code,years):
    murl="https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?"+urllib.parse.urlencode({"varcd":code,"lang":"PT"})
    raw=public(murl,timeout=25);meta=json.loads(raw)
    store("supplement/INE-"+code+"-metadata.json",raw)
    dims=_dimensions(meta)
    d={k:{c:str(v.get("categ_dsg") or v.get("Designacao") or v.get("Descricao") or v.get("label") or "") for c,v in _dimension_items(meta,int(k[3:])).items()} for k in dims}
    g=_resolve_label(meta,2,"Norte")
    periods={k:v for k,v in _period_labels(meta).items() if str(v) in years}
    rows=[];q=[]
    for k,y in periods.items():
        params={"op":"2","varcd":code,"lang":"PT","Dim1":k,"Dim2":g}
        url="https://www.ine.pt/ine/json_indicador/pindica.jsp?"+urllib.parse.urlencode(params)
        for attempt in range(3):
            try:
                raw=public(url,timeout=25);rr=_flatten(json.loads(raw));assert rr
                rows.extend(rr);store("supplement/INE-"+code+"-"+y+".json",raw);q.append({"year":y,"rows":len(rr),"sha256":sha(raw)});break
            except Exception as e:
                if attempt==2:q.append({"year":y,"error":type(e).__name__})
                time.sleep(1)
    return {"rows":rows,"dimensions":{k:v for k,v in d.items() if k!="Dim2"},"geocodes":{"Norte":g},"periods":periods,"queries":q,"metadata_url":murl}
for c,y in [("0008640",{"2019","2020","2021","2022","2023"}),("0012775",{"2022"}),("0012774",{"2022","2024"})]:
    try:
        z=query_one(c,y);store("supplement/INE-"+c+"-rows.json",dump(z));rec["sources"]["INE-"+c]={"state":"PASS" if z["rows"] else "EMPTY","queries":z["queries"],"rows":len(z["rows"])}
    except Exception as e:err("INE-"+c,e)
# Separate receipt from original full acquisition.
store("supplement/receipt.json",dump(rec))
# preserve original receipt, don't overwrite it with supplement metadata
old=file(OUT+"acquisition-receipt.json",REF)
rec=json.loads(old);rec["supplement_run"]=os.environ.get("GITHUB_RUN_ID");commit()
