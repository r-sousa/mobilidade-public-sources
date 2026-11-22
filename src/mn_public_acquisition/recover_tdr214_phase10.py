"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase10/"
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





import openpyxl,fitz
from collections import Counter,defaultdict
PARENT="statistics/assments/norte-centro-2026-11-22/".replace("assments","assessments")
def rr(phase):
    b,_=read_private(PARENT+phase+"/receipt.json");return json.loads(b)
def joinparts(parts):
    b=bytearray()
    for x in parts:
        a,_=read_private(x["path"]);assert sha(a)==x["sha256"];b.extend(a)
    return bytes(b)
def readcsv(p):
    b,bs=read_private(p);return list(csv.reader(io.StringIO(b.decode("utf-8-sig")))),bs
def writecsv(p,h,r):add_blob(p,csvbytes(h,r))
try:
    cw,_=readcsv(PARENT+"municipal-nuts-crosswalk-dgeg-2024.csv")
    lookup={r[0]:r for r in cw[1:]}
    p=PARENT+"phase5/raw/APA-emissions-1.xlsx";b,bs=read_private(p)
    assert sha(b)=="59780a107b9e123621c1bdad77fa258561524976a6da6a562b88e548421c5ae8"
    ws=openpyxl.load_workbook(io.BytesIO(b),read_only=True,data_only=True)["Emissões 2023"]
    it=ws.iter_rows(values_only=True)
    for i in range(6):next(it)
    names=next(it);units=next(it);headers=[(str(names[i] or "").replace("\n"," ").strip(),str(units[i] or "").strip()) for i in range(4,len(names))]
    assert units[0]=="CODE"
    native=[];agg=defaultdict(float);unmatched=Counter();codes=set();keys=set();duplicates=0;geos=Counter();negative=0;missing=0
    for row in it:
        if row[3]!=2023 and str(row[3])!="2023":continue
        code=str(row[0]).zfill(4);m=lookup.get(code)
        if not m:unmatched[(code,str(row[1]))]+=1;continue
        if m[7] not in ["Norte","Centro"]:continue
        codes.add(code);geos[m[7]]+=1
        sector=str(row[2])
        for i,(pol,unit) in enumerate(headers,4):
            if not pol or not unit:continue
            v=row[i];key=(code,sector,pol,unit)
            if key in keys:duplicates+=1
            keys.add(key)
            if isinstance(v,(int,float)):
                if v<0:negative+=1
                for level,geo in [("NUTS2",m[7]),("NUTS3",m[8])]:
                    agg[(level,geo,sector,pol,unit)]+=v
            else:missing+=1
            native.append([2023,code,row[1],m[7],m[8],sector,pol,unit,v])
    writecsv("emissions/APA-2023-norte-centro-municipal.csv",["year","municipal_code","municipality","nuts2","nuts3","gnfr","pollutant","unit","value"],native)
    writecsv("emissions/APA-2023-norte-centro-aggregates.csv",["year","geo_level","geography","gnfr","pollutant","unit","value"],[[2023,*k,v] for k,v in sorted(agg.items())])
    receipt("APA-emissions","normalize","PASS",rows=len(native),municipalities=len(codes),source_rows_by_region=dict(geos),headers=headers,duplicate_keys=duplicates,missing=missing,negative_values=negative,unmatched=[[*k,v] for k,v in unmatched.items()],transport_summary=[[*k,v] for k,v in agg.items() if k[0]=="NUTS2" and k[2] in ["F_RoadTransport","G_Shipping","H_Aviation","I_Offroad"]],guard="Spatial emissions inventory estimated using proxies; offroad includes non-rail sources; no modal allocation; no sum across pollutant units or source hierarchy")
except Exception as e:receipt("APA-emissions","normalize","ERROR",detail=str(e)[:300])
try:
    r=rr("phase5")
    for n,x in enumerate([x for x in r["requests"] if x["source_id"]=="ANAC" and x["stage"]=="download" and x["state"]=="PASS"],1):
        try:
            b=joinparts(x["parts"]);assert sha(b)==x["sha256"]
            doc=fitz.open(stream=b,filetype="pdf")
            t="\n".join(f"\n--- PAGE {i+1} ---\n"+p.get_text(sort=True) for i,p in enumerate(doc))
            out="air/ANAC-"+str(n)+".txt";add_blob(out,t.encode())
            pages=[i+1 for i,p in enumerate(doc) if any(q in p.get_text().lower() for q in ["bragança","vila real","viseu"])]
            receipt("ANAC","text_extract","PASS",url=x["url"],bytes=len(t.encode()),path=ROOT+out,pages=pages,source_sha256=x["sha256"])
        except Exception as e:receipt("ANAC","text_extract","ERROR",detail=str(e)[:180])
except Exception as e:receipt("ANAC","receipt","ERROR",detail=str(e)[:180])
try:
    p=PARENT+"phase4/energy/DGEG-PETROL-2.xlsx-pivotCacheDefinition1.csv";r,bs=readcsv(p)
    ks=Counter(tuple(a[1:]) for a in r[1:]);ex=Counter(tuple(a) for a in r[1:]);raw=defaultdict(float);unique=defaultdict(float)
    for a in r[1:]:raw[a[1]]+=float(a[0])
    for a in ex:unique[a[1]]+=float(a[0])
    p2=PARENT+"phase3/cells/DGEG-PETROL-2.xlsx-DGEG.csv";c,_=readcsv(p2)
    labels=[r for r in c[1:] if "total" in r[2].lower()];receipt("petroleum","duplicate_audit","PASS",rows=len(r)-1,repeated_dimensions=sum(v-1 for v in ks.values()),exact_repeated_rows=sum(v-1 for v in ex.values()),raw_totals=dict(raw),deduplicated_sensitivity=dict(unique),visible_totals_labels=labels[-15:])
except Exception as e:receipt("petroleum","audit","ERROR",detail=str(e)[:200])
store("receipt.json",{"status":"PRIVATE_STAGING_NOT_CANONICAL_ADMISSION","publication_authorized":False,"run_id":os.environ.get("GITHUB_RUN_ID"),"requests":RECEIPTS,"blobs":BLOBS})
for attempt in range(3):
    head=gh("git/ref/heads/"+BRANCH)["object"]["sha"];tree=gh("git/commits/"+head)["tree"]["sha"]
    entries=[{"path":ROOT+name,"mode":"100644","type":"blob","content":content} for name,content in OUT.items()]+[{"path":ROOT+name,"mode":"100644","type":"blob","sha":s} for name,s in BLOBS.items()]
    nt=gh("git/trees","POST",{"base_tree":tree,"tree":entries},write=True)["sha"]
    new=gh("git/commits","POST",{"message":"MN: normalize APA municipal emissions and extract ANAC using PyMuPDF","tree":nt,"parents":[head]},write=True)["sha"]
    try:
        gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_COMMIT",new,flush=True);break
    except urllib.error.HTTPError:
        if attempt==2:raise
        time.sleep(2)
