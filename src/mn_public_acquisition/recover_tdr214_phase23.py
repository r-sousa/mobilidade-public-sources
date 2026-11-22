"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase23/"
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
        new=gh("git/commits","POST",{"message":"MN: F187 interregional boundary sublink traffic panel","tree":nt,"parents":[head]},write=True)["sha"]
        try:
            gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_CHECKPOINT",new,flush=True);return
        except urllib.error.HTTPError:
            if attempt==4:raise
            time.sleep(2)




from collections import defaultdict
import calendar
cand,_=readcsv(PARENT+"phase22/supported-cross-region-sublink-candidates.csv")
wanted={(x[0],x[1]):"SUPPORTED_ENDPOINTS_OPPOSITE_NUTS2" for x in cand[1:]}
for label in ["Arada – Maceda","Maceda – Esmoriz","Esmoriz – Paramos","Paramos – Espinho Nascente"]:wanted[("A29",label)]="INTERFACE_CANDIDATE; actual crossing assignment unresolved"
allrows=[];sums=defaultdict(list);matched=set()
hdr=None
for year in [2024,2025,2026]:
    p=PARENT+f"phase19/F187-monthly-selected-{year}.csv";b,bs=read_private(p)
    reader=csv.DictReader(io.StringIO(b.decode("utf-8-sig")));hdr=reader.fieldnames
    for x in reader:
        k=(x["motorway"],x["sublanco"])
        if k not in wanted:continue
        year,month=map(int,x["month"].split("-"));v=float(x["native_value"])
        n=calendar.monthrange(year,month)[1]
        allrows.append([*[x[h] for h in hdr],wanted[k],bs]);matched.add(k)
        sums[(k,year,"H1" if month<=6 else "H2")].append((month,v,n))
        if year!=2026:sums[(k,year,"year")].append((month,v,n))
writecsv("F187-norte-centro-interface-monthly.csv",hdr+["geography_status","selected_panel_blob"],allrows)
rows=[]
for (k,y,period),vals in sorted(sums.items()):
    expected=12 if period=="year" else 6;months={x[0] for x in vals}
    rows.append([*k,y,period,len(months),sum(x[2] for x in vals),sum(x[1]*x[2] for x in vals)/sum(x[2] for x in vals),wanted[k],"COMPLETE" if len(months)==len(vals)==expected else "PARTIAL"])
writecsv("F187-norte-centro-interface-periods.csv",["road","sublanco","year","period","months","days","weighted_tmd","geography_status","coverage"],rows)
receipt("F187","boundary_join","PASS" if matched==set(wanted) else "PARTIAL",monthly_rows=len(allrows),matched=len(matched),missing=[list(k) for k in set(wanted)-matched],periods=rows,guard="A1/A24 supported node endpoints in opposing regions; A29 multiple RRN contacts and unresolved Paramos, no unique sublink crossing assignment; no summation across sequential sublinks or inference of passenger/freight OD")
commit("COMPLETE_ATTEMPT")
