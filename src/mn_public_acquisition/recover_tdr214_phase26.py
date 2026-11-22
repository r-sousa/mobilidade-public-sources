"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase26/"
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
        new=gh("git/commits","POST",{"message":"MN: TdR 2.1.4 2025 transport update and residual monthly trade","tree":nt,"parents":[head]},write=True)["sha"]
        try:
            gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_CHECKPOINT",new,flush=True);return
        except urllib.error.HTTPError:
            if attempt==4:raise
            time.sleep(2)

# Independently checkpoint each source, never silently merge revisions.
from bs4 import BeautifulSoup
import openpyxl, fitz, gzip
from urllib.parse import urljoin, urlparse
MAX=65_000_000
def rawget(url,cap=MAX):
    with OPENER.open(urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte/1.0","Accept":"*/*"}),timeout=60) as rr:
        b=rr.read(cap+1);final=rr.geturl();typ=rr.headers.get("Content-Type","")
    if len(b)>cap:raise ValueError("bounded source response")
    return b,final,typ
def keep(stem,b):
    ps=[]
    for i in range(0,len(b),8_000_000):
        p=stem if len(b)<=8_000_000 else stem+f".part{1+i//8_000_000:03}"
        piece=b[i:i+8_000_000];add_blob(p,piece);ps.append({"path":ROOT+p,"bytes":len(piece),"sha256":sha(piece)})
    return ps
def links(url,b):
    soup=BeautifulSoup(b,"html.parser")
    return [(urljoin(url,a.get("href","")),a.get_text(" ",strip=True),a.get("title","")) for a in soup.select("a[href]") if a.get("href") and not a["href"].startswith(("javascript:","#","mailto:"))]
def extract_file(sid,url,stem):
    b,final,typ=rawget(url)
    # Treat true XLSX, PDF, ZIP separately. Preserve original bytes before deriving.
    if b.startswith(b"%PDF"):
        ps=keep("raw/"+stem+".pdf",b);doc=fitz.open(stream=b,filetype="pdf");pages=[{"page":i+1,"text":p.get_text(sort=True)} for i,p in enumerate(doc)]
        textb=json.dumps(pages,ensure_ascii=False).encode();keep("extracted/"+stem+"-pages.json",textb)
        receipt(sid,"official_pdf","PASS",url=url,final_url=final,bytes=len(b),sha256=sha(b),parts=ps,pages=len(pages),text_chars=sum(len(p["text"]) for p in pages))
        return True
    if b.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(b)) as z:names=z.namelist()
        ps=keep("raw/"+stem+(".xlsx" if "xl/workbook.xml" in names else ".zip"),b)
        if "xl/workbook.xml" in names:
            source_xlsx(stem,b,final,sha(b))
            receipt(sid,"official_xlsx","PASS",url=url,final_url=final,bytes=len(b),sha256=sha(b),parts=ps)
        else:
            receipt(sid,"official_zip","PASS",url=url,final_url=final,bytes=len(b),sha256=sha(b),parts=ps,members=names[:200])
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                for i,n in enumerate(names):
                    if n.lower().endswith(".xlsx") and z.getinfo(n).file_size<=MAX:
                        w=z.read(n);source_xlsx(stem+f"-member{i}",w,final+"#"+n,sha(w))
        return True
    receipt(sid,"file_not_binary","NON_FILE",url=url,final_url=final,mime=typ,bytes=len(b))
    return False
# AMT direct source page, explicitly select 2025 release only.
sid="AMT-rail-2025"
try:
    u="https://observatorio.amt-autoridade.pt/publicacao/analise-estatistica-transporte-ferroviario-em-portugal";b,f,t=rawget(u,4_000_000);keep("raw/AMT-rail-listing.html",b)
    ls=[x for x in links(f,b) if "2025" in " ".join(x[1:]) and re.search(r"ferrovi|análise|analise", " ".join(x[1:]),re.I)]
    receipt(sid,"discover","PASS" if ls else "NO_2025_LINK",url=f,links=ls)
    for i,a in enumerate(ls[:4]):
        try:extract_file(sid,a[0],f"AMT-rail-2025-{i}")
        except Exception as e:receipt(sid,"download","ERROR",url=a[0],detail=str(e)[:160])
except Exception as e:receipt(sid,"discover","ERROR",detail=str(e)[:200])
commit("AMT_CHECKPOINT")
# Follow actual official INE links from the current INE pages or linked references.
sid="INE-transport-2025"
seeds=["https://www.ine.pt/xportal/xmain?tema_=&xpgid=ine_tema&xpid=INE","https://webinq.ine.pt/home.aspx","https://rea.apambiente.pt/node/106","https://simula.pt/noticias/transportes-passageiros-2025/"]
seen=set();queue=[];files=[];k=0
def official(u):return (urlparse(u).hostname or "").lower().split(".")[-2:]==["ine","pt"]
for i,u in enumerate(seeds):
    try:
        b,f,t=rawget(u,5_000_000);keep(f"raw/INE-discovery-seed-{i}.html",b)
        ll=links(f,b)
        # Look for exact release phrase or exact title in nearby parent, not arbitrary older releases.
        soup=BeautifulSoup(b,"html.parser")
        for a in soup.select("a[href]"):
            un=urljoin(f,a["href"]);label=a.get_text(" ",strip=True)+" "+a.get("title","")
            if not official(un):continue
            parent=a.parent.get_text(" ",strip=True) if a.parent else ""
            if re.search(r"estatísticas dos transportes e comunicações.{0,20}2025|transporte de passageiros aumentou na generalidade",label+" "+parent,re.I):
                queue.append(un)
        receipt(sid,"seed","PASS",url=f,matching_links=list(dict.fromkeys(queue))[:25])
    except Exception as e:receipt(sid,"seed","ERROR",url=u,detail=str(e)[:160])
while queue and k<12:
    u=queue.pop(0)
    if u in seen or not official(u):continue
    seen.add(u);k+=1
    try:
        b,f,t=rawget(u)
        if b.startswith((b"%PDF",b"PK")):
            # Avoid a second source download; use the bytes already obtained.
            stem=f"INE-transport-2025-{k}"
            if b.startswith(b"%PDF"):
                ps=keep("raw/"+stem+".pdf",b);doc=fitz.open(stream=b,filetype="pdf");p=[{"page":i+1,"text":x.get_text(sort=True)} for i,x in enumerate(doc)];keep("extracted/"+stem+"-pages.json",json.dumps(p,ensure_ascii=False).encode())
                receipt(sid,"candidate_pdf","PASS",url=u,final_url=f,sha256=sha(b),bytes=len(b),parts=ps,pages=len(p),title_validation=bool(re.search(r"Transportes e Comunicações",p[0]["text"] if p else "",re.I)))
            else:
                ps=keep("raw/"+stem+".zip",b)
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    names=z.namelist()
                    if "xl/workbook.xml" in names:source_xlsx(stem,b,f,sha(b))
                    else:
                        for j,n in enumerate(names):
                            if n.lower().endswith(".xlsx") and z.getinfo(n).file_size<=MAX:
                                w=z.read(n);source_xlsx(stem+f"-member{j}",w,f+"#"+n,sha(w))
                receipt(sid,"candidate_workbook_zip","PASS",url=u,final_url=f,sha256=sha(b),parts=ps,members=names[:100],guard="Validate release title and year before admission")
            continue
        keep(f"raw/INE-detail-{k}.html",b)
        ll=links(f,b)
        for un,label,title in ll:
            if official(un) and re.search(r"Publicação|quadros|excel|xlsx|zip|pdf|download",label+" "+title+" "+un,re.I) and (re.search(r"publicacoes|download|publ|file|anexo|pdf|xlsx|zip",un,re.I)):
                queue.append(un)
        receipt(sid,"detail","PASS",url=f,candidate_links=queue[:30])
    except Exception as e:receipt(sid,"detail","ERROR",url=u,detail=str(e)[:160])
commit("INE_PUBLICATION_CHECKPOINT")
# F20 totals for the single still-missing September 2026 vintage, no re-fetch Aug totals.
try:
    u,b,j,rs=query("0012087",{"Dim1":"S3A202609","Dim2":"11,19","Dim3":"T","Dim4":"T"})
    keep("raw/F20-202609-nuts2.json",b)
    good=[x for y,x in rs if x.get("geocod") in {"11","19"} and x.get("dim_3")=="T" and x.get("dim_4")=="T" and x.get("valor") not in (None,"")]
    assert len({x["geocod"] for x in good})==len(good)
    writecsv("F20-202609-nuts2-totals.csv",["month","geo","eur","flag"],[["2026-09",x["geocod"],x["valor"],x.get("sinal_conv","")] for x in good])
    receipt("F20","September-2026-totals","PASS" if len(good)==2 else "PARTIAL",url=u,rows=len(good),data=good)
except Exception as e:receipt("F20","September-2026-totals","ERROR",detail=str(e)[:160])
commit("COMPLETE_ATTEMPT")
