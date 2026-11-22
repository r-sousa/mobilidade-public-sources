"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase2/"
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


# Pull exact previously retained archive members before any retries. No skip based on just source ID.
for asset,n,expected,members in ARCH[1:]:
    try:
        with tempfile.TemporaryDirectory() as td:
            z=pathlib.Path(td)/"source.zip"
            h=hashlib.sha256(); size=0
            with gh("releases/assets/"+str(asset),binary=True) as src,z.open("wb") as dst:
                while True:
                    b=src.read(1024*1024)
                    if not b: break
                    dst.write(b);h.update(b);size+=len(b)
            if size!=n or h.hexdigest()!=expected: raise ValueError("archive identity mismatch")
            with zipfile.ZipFile(z) as za:
                for sid,name in members.items():
                    paths=[p for p in za.namelist() if pathlib.PurePosixPath(p).name==name]
                    if len(paths)!=1:
                        receipt(sid,"archive-"+str(asset),"MEMBER_NOT_UNIQUE",matches=len(paths));continue
                    b=za.read(paths[0]); obj=json.loads(b)
                    rows=ine_rows(obj,PORTUGAL_GEO if sid=="F101" else ["11","19"],["2024","2025"])
                    store(sid+"-archive-"+str(asset)+".json",{"asset_id":asset,"archive_sha256":expected,"member":paths[0],"member_sha256":sha(b),"rows":rows})
                    receipt(sid,"archive-"+str(asset),"PASS" if rows else "NO_TARGET_ROWS",rows=len(rows),numeric_rows=sum(bool(r["native"].get("valor")) for r in rows))
    except Exception as e: receipt("ARCHIVE","archive-"+str(asset),"ERROR",error_type=type(e).__name__,http_code=getattr(e,"code",None))
for sid,ds in [("F01","road_go_na_rl3g"),("F02","road_go_na_ru3g")]:
    euro(sid,ds,[("geo",N3+C3),("nst07","TOTAL"),("unit","THS_T"),("time",["2024","2025"])],"nuts3-all",lambda c:c.get("geo") in N3+C3)
    euro(sid,ds,[("geo",N3+C3),("unit","THS_T"),("time",["2024","2025"])],"nuts3-commodity",lambda c:c.get("geo") in N3+C3)
euro("F24","nama_10r_3gva",[("geo",N3+C3+R2),("nace_r2",["TOTAL","A","B-E","C","F","G-I","J","K","L","M-N","O-Q","R-U"]),("unit","CP_MEUR"),("time",["2022","2023","2024"])],"sector-2022-24",lambda c:c.get("geo") in N3+C3+R2)
euro("F148","tran_r_rago",[("time",["2024","2025"]),("c_load",R2+C2),("c_unload",R2+C2)],"current-2024-25",lambda c:c.get("c_load") in R2+C2 and c.get("c_unload") in R2+C2)
# Passenger, freight, infrastructure proxies; preserve native selection and coverage.
for sid,ds,params in [
 ("candidate-port","mar_go_aa", [("time",["2022","2023","2024","2025"])]),
 ("candidate-regional-rail","tran_r_rail", [("geo",R2),("time",["2022","2023","2024","2025"])]),
 ("candidate-road-network","tran_r_net", [("geo",R2),("time",["2022","2023","2024","2025"])]),
 ("candidate-rail-passenger","rail_pa_typepas", [("geo","PT"),("time",["2023","2024","2025"])]),
 ("candidate-rail-freight","rail_go_typeall", [("geo","PT"),("time",["2023","2024","2025"])])
]:
    if sid=="candidate-port": continue # unbounded EU port cube not acceptable
    euro(sid,ds,params,"latest",lambda c:True)
# Exact INE API queries, bounded attempts per indicator. Municipality code format is recovered via source metadata, not guessed.
for sid,code,yr,g in [("F75","0012347","2024",["19"]),("F75","0012347","2025",["11"]),("F101","0012348","2024",PORTUGAL_GEO),("F20","0012087","2025",PORTUGAL_GEO),("F21","0013838","2024",PORTUGAL_GEO),("F22","0013863","2024",PORTUGAL_GEO),("F23","0013872","2024",PORTUGAL_GEO)]:
    ine(sid,code,yr,g,"retry-"+yr)

# Public source files, preserved as exact bytes, private staging only.
from html.parser import HTMLParser
import re
class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            h=dict(attrs).get("href")
            if h: self.current=[h,""]
    def handle_data(self,d):
        if self.current: self.current[1]+=d
    def handle_endtag(self,tag):
        if tag=="a" and self.current:
            self.links.append(self.current);self.current=None
RAW={}
def fetch_bytes(url,limit=24_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte/1.0"})
    with OPENER.open(req,timeout=40) as r:
        b=r.read(limit+1); typ=r.headers.get("Content-Type","");final=r.geturl()
    if len(b)>limit: raise ValueError("source exceeds size cap")
    return b,typ,final
def preserve(sid,url,label):
    try:
        b,typ,final=fetch_bytes(url)
        ext=pathlib.PurePosixPath(urllib.parse.urlparse(final).path).suffix.lower()
        if b.startswith(b"PK\x03\x04"): ext=ext if ext in [".xlsx",".zip",".gpkg"] else ".zip"
        elif b.startswith(b"%PDF"): ext=".pdf"
        elif b[:8]==bytes.fromhex("d0cf11e0a1b11ae1"): ext=".xls"
        elif ext in [".csv",".json",".geojson"] and "html" not in typ.lower(): pass
        else: raise ValueError("not recognized data file")
        name=re.sub(r"[^a-zA-Z0-9_.-]","_",sid+"-"+label)+ext
        RAW[name]=b
        details={"url":url,"final_url":final,"sha256":sha(b),"bytes":len(b),"mime":typ,"path":ROOT+"raw/"+name}
        if ext==".xlsx":
            with zipfile.ZipFile(__import__("io").BytesIO(b)) as z:
                import xml.etree.ElementTree as ET
                root=ET.fromstring(z.read("xl/workbook.xml"))
                details["sheets"]=[x.attrib.get("name") for x in root.iter() if x.tag.endswith("}sheet")]
        receipt(sid,label,"PRESERVED_BYTES",**details)
    except Exception as e: receipt(sid,label,"ERROR",url=url,error_type=type(e).__name__,http_code=getattr(e,"code",None))
def discover(sid,page,pattern,maxfiles):
    try:
        b,typ,final=fetch_bytes(page,4_000_000); parser=Links();parser.feed(b.decode("utf-8","replace"))
        found=[]
        for href,label in parser.links:
            url=urllib.parse.urljoin(final,href)
            if urllib.parse.urlparse(url).scheme!="https": continue
            if re.search(pattern,url+" "+label,re.I) and re.search(r"\.(xlsx?|csv|zip|gpkg|pdf)(?:$|[?#])",url,re.I) and url not in [x[0] for x in found]:
                found.append((url,label.strip()))
        store(sid+"-discovered.json",{"page":page,"links":found})
        receipt(sid,"discover","LINKS_FOUND" if found else "NO_FILE_LINKS",page=page,links=len(found),attempted=min(len(found),maxfiles))
        for i,(u,l) in enumerate(found[:maxfiles]): preserve(sid,u,str(i+1))
    except Exception as e: receipt(sid,"discover","ERROR",page=page,error_type=type(e).__name__,http_code=getattr(e,"code",None))
preserve("DGEG-ECA","https://www.dgeg.gov.pt/media/iqxczkj0/dgeg-eca-2024.xlsx","2024")
preserve("F169","https://www.dgeg.gov.pt/media/yevbnrq5/dgeg-ben-2024.xlsx","2024-revised")
for sid,page,pat,n in [
 ("F169","https://www.dgeg.gov.pt/pt/estatistica/energia/balancos-energeticos/balancos-energeticos-nacionais/",r"2025",2),
 ("DGEG-PETROL","https://www.dgeg.gov.pt/pt/estatistica/energia/petroleo-e-derivados/vendas-anuais/",r"2024|2025",4),
 ("F170","https://www.dgeg.gov.pt/pt/estatistica/energia/gas-natural/consumos/",r"2024|2025",4),
 ("IMT","https://www.imt-ip.pt/biblioteca/reportorio-geral/estatisticas-repertorio-geral/relatorios-setoriais-imt/",r"2025|2026",12),
 ("F09","https://leixoes.apdl.pt/estatisticas/boletim-estatistico/boletim-estatistico/",r"2025|2026",8),
 ("F150","https://leixoes.apdl.pt/estatisticas/carga/movimento-de-mercadorias-anual/",r"2025|2026",4),
 ("F152","https://viana.apdl.pt/estatisticas/carga/movimento-de-mercadorias-anual/",r"2025|2026",4),
 ("APA-FLOOD","https://sniamb.apambiente.pt/content/diretiva60ce2007-2%25C2%25BA-ciclo?language=pt-pt",r"shp|shapefile|inund",4),
 ("TENtec","https://transport.ec.europa.eu/transport-themes/infrastructure-and-investment/trans-european-transport-network-ten-t/tentec-information-system-and-ten-t-map-library_en",r"2024|gis|shapefile|geodata",4)
]:
    discover(sid,page,pat,n)
# Stage data and raw files on private branch, never public. Individual blobs prevent large single tree payloads.
for name,b in RAW.items():
    item=gh("git/blobs","POST",{"content":base64.b64encode(b).decode(),"encoding":"base64"},write=True)
    RAW[name]=item["sha"]
store("receipt.json",{"status":"INTERNAL_ACQUISITION_NOT_CANONICAL_ADMISSION","publication_authorized":False,"run_id":os.environ.get("GITHUB_RUN_ID"),"requests":RECEIPTS,"raw_files":RAW,"json_files":sorted(OUT)})
for attempt in range(3):
    head=gh("git/ref/heads/"+BRANCH)["object"]["sha"];tree=gh("git/commits/"+head)["tree"]["sha"]
    entries=[{"path":ROOT+name,"mode":"100644","type":"blob","content":content} for name,content in OUT.items()]
    entries += [{"path":ROOT+"raw/"+name,"mode":"100644","type":"blob","sha":s} for name,s in RAW.items()]
    nt=gh("git/trees","POST",{"base_tree":tree,"tree":entries},write=True)["sha"]
    new=gh("git/commits","POST",{"message":"MN: TdR 2.1.4 residual source acquisition phase 2","tree":nt,"parents":[head]},write=True)["sha"]
    try:
        gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True)
        print("PRIVATE_COMMIT",new,"FILES",len(entries),flush=True);break
    except urllib.error.HTTPError:
        if attempt==2:raise
        time.sleep(2)
