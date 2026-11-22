"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase13/"
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
        new=gh("git/commits","POST",{"message":"MN: dependent F20 and municipal completion QA checkpoint","tree":nt,"parents":[head]},write=True)["sha"]
        try:
            gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_CHECKPOINT",new,flush=True);return
        except urllib.error.HTTPError:
            if attempt==4:raise
            time.sleep(2)
# Consume only confirmed files from the upstream checkpoint; no guessed observations.
try:
    upstream=readj(PARENT+"phase12/receipt.json")
    total=[];byperiod=defaultdict(dict);geoval=defaultdict(dict)
    for x in upstream["requests"]:
        if x["source_id"]!="F20" or x["state"]!="PASS":continue
        label=x["stage"];m=re.fullmatch(r"F20-(\d{6})-(regional|municipal-total)",label)
        if not m:continue
        ym,scope=m.groups();name="phase12/normalized/"+label+".csv";p=PARENT+name
        rows,blob=readcsv(p);assert len(rows)-1==x["rows"]
        for a in rows[1:]:
            month,native,geo,name,trade,trade_label,nc2,nc2_label,value,flag=a
            if nc2!="T" or trade!="T" or value=="":continue
            if scope=="regional" and geo in ["11","19"]:
                v=int(value);total.append([month,geo,name,v,flag,p,blob]);byperiod[month][geo]=v
            if scope=="municipal-total":geoval[month][geo]=int(value)
    checks=[]
    for month,rs in sorted(byperiod.items()):
        for geo,v in rs.items():
            a=[x for g,x in geoval.get(month,{}).items() if g.startswith(geo)];expected=86 if geo=="11" else 77
            checks.append([month,geo,v,sum(a) if a else "",len(a),expected,sum(a)-v if len(a)==expected else "","COMPLETE_MATCH" if len(a)==expected and sum(a)==v else "INCOMPLETE_OR_DIFFERENT"])
    writecsv("F20-regional-monthly-totals.csv",["month","NUTS2","geography","export_eur","flag","source_path","source_blob_sha"],total)
    writecsv("F20-municipal-reconciliation.csv",["month","region","official_eur","municipal_sum_eur","numeric_municipalities","expected_municipalities","difference_eur","qa"],checks)
    years=[]
    for geo in ["11","19"]:
        for year in range(2022,2027):
            months=[f"{year}-{m:02}" for m in range(1,10)]
            vs=[byperiod.get(m,{}).get(geo) for m in months]
            if all(v is not None for v in vs):years.append([geo,year,"Jan-Sep",sum(vs)])
    writecsv("F20-jan-sep-panel.csv",["region","year","period","export_eur"],years)
    receipt("F20","dependent_QA","PASS" if total else "NO_VALIDATED_TOTALS",upstream_status=upstream.get("status"),months=len(byperiod),regional_totals=len(total),controls=len(checks),complete_matches=sum(x[-1]=="COMPLETE_MATCH" for x in checks),ytd=years,guard="Complete matched periods only; 2026 preliminary; operator location, no transport OD")
except Exception as e:receipt("F20","dependent_QA","ERROR",detail=str(e)[:200])
commit("UPSTREAM_QA_CHECKPOINT")
# Actual INE geography and annual period codes acquired in previous phases.
obj=readj(PARENT+"phase4/ine/candidate-electricity-year.json")
mun=sorted({r["geocod"] for r in obj[0]["Dados"]["2024"] if len(r["geocod"])==7 and r["geocod"].startswith(("11","19"))})
assert len(mun)==163
for sid,code,orig in [("F22","0013863","phase7/ine/F22-municipal-normalized.csv"),("establishment-turnover","0012932","phase7/ine/candidate-establishment-turnover-municipal-normalized.csv")]:
    try:
        raw,blob=readcsv(PARENT+orig);rows={tuple(a[:2])+ (a[3],):a for a in raw[1:]}
        if sid=="F22":todo=[g for g in mun if ("2024",g,"T") not in rows];filters={"Dim3":"T"}
        else:todo=[g for g in mun if not any(k[1]==g for k in rows)];filters={}
        for i in range(0,len(todo),20 if sid=="F22" else 10):
            gs=todo[i:i+(20 if sid=="F22" else 10)]
            try:
                u,b,j,rs=query(code,{"Dim1":"S7A2024","Dim2":",".join(gs),**filters})
                p="raw/"+sid+"-retry-"+str(i).zfill(3)+".json";add_blob(p,b)
                for y,r in rs:
                    k=(str(y),r["geocod"],r["dim_3"])
                    v=[str(y),r["geocod"],r.get("geodsg",""),r["dim_3"],r.get("dim_3_t",""),r.get("valor",""),r.get("sinal_conv",""),ROOT+p]
                    if k in rows and rows[k][5:7]!=v[5:7]:raise ValueError("conflicting native key")
                    rows[k]=v
                receipt(sid,"retry","PASS" if rs else "ERROR_BODY",rows=len(rs),requested=len(gs),url=u,detail=str(j)[:220] if not rs else None)
            except Exception as e:receipt(sid,"retry","ERROR",detail=str(e)[:160])
        p="ine/"+sid+"-municipal-completed.csv";writecsv(p,raw[0],rows.values())
        receipt(sid,"reconciled","PASS",rows=len(rows),numeric=sum(bool(x[5]) for x in rows.values()),municipalities=len({k[1] for k in rows}),total_cells=sum(k[2]=="T" for k in rows),missing_geos=sorted(set(mun)-{k[1] for k in rows}),path=ROOT+p)
    except Exception as e:receipt(sid,"reconcile","ERROR",detail=str(e)[:200])
commit("MUNICIPAL_QA_CHECKPOINT")
try:
    code="0014449";u="https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd="+code+"&lang=PT"
    b,j=get_public(u);add_blob("raw/0014449-metadata.json",b);m=j[0]
    cats=[x for c in m["Dimensoes"]["Categoria_Dim"] for a in c.values() for x in a]
    ps=sorted([x for x in cats if x["dim_num"]=="1"],key=lambda x:x["categ_ord"],reverse=True)
    gs=sorted({x["cat_id"] for x in cats if x["dim_num"]=="2" and x["cat_id"] in mun})
    p=next((x for x in ps if x["categ_ord"].startswith("2024")),ps[0] if ps else None)
    receipt("0014449","metadata","PASS",title=m.get("IndicadorNome"),periods=[(x["cat_id"],x["categ_dsg"]) for x in ps],target=p,municipality_codes=len(gs))
    if p and gs:
        # Metadata governs year; do not relabel a non-2024 release as 2024.
        rows={}
        for i in range(0,len(gs),15):
            try:
                u,b,j,rs=query(code,{"Dim1":p["cat_id"],"Dim2":",".join(gs[i:i+15])});raw="raw/0014449-"+str(i).zfill(3)+".json";add_blob(raw,b)
                for y,r in rs:rows[(str(y),r["geocod"],r.get("dim_3",""))]=[str(y),r["geocod"],r.get("geodsg",""),r.get("dim_3",""),r.get("dim_3_t",""),r.get("valor",""),r.get("sinal_conv",""),ROOT+raw]
                receipt(code,"batch","PASS" if rs else "ERROR_BODY",rows=len(rs),url=u,detail=str(j)[:200] if not rs else None)
            except Exception as e:receipt(code,"batch","ERROR",detail=str(e)[:140])
        if rows:
            path="ine/0014449-municipal-enterprises.csv";writecsv(path,["year","geocod","municipality","cae","cae_label","value","flag","source_path"],rows.values())
            receipt(code,"normalized","PASS",rows=len(rows),numeric=sum(bool(x[5]) for x in rows.values()),municipalities=len({k[1] for k in rows}),years=sorted({k[0] for k in rows}),path=ROOT+path)
except Exception as e:receipt("0014449","metadata_or_extract","ERROR",detail=str(e)[:200])
commit("COMPLETE_ATTEMPT")
