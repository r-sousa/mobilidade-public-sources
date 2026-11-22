"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase4/"
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

# Decode pivot cache records. Keep each cache as a native table and check index decoding.
for name in ["DGEG-ECA-2024.xlsx","DGEG-PETROL-2.xlsx","F170-1.xlsx"]:
    try:
        path=BASE+"raw/"+name;raw,blob=read_private(path)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=z.namelist()
            defs=[p for p in names if re.fullmatch(r"xl/pivotCache/pivotCacheDefinition\d+\.xml",p)]
            recs=[p for p in names if re.fullmatch(r"xl/pivotCache/pivotCacheRecords\d+\.xml",p)]
            receipt(name,"cache_inventory","PASS",definitions=defs,records=recs,model=[p for p in names if p.startswith("xl/model/")])
            for p in defs:
                root=ET.fromstring(z.read(p));ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                fields=root.findall("m:cacheFields/m:cacheField",ns)
                cols=[f.attrib["name"] for f in fields]
                shared=[]
                for f in fields:
                    s=f.find("m:sharedItems",ns);shared.append(list(s) if s is not None else [])
                relpath="xl/pivotCache/_rels/"+p.rsplit("/",1)[1]+".rels"
                record=None
                if relpath in names:
                    for rel in ET.fromstring(z.read(relpath)):
                        if rel.attrib.get("Type","").endswith("/pivotCacheRecords"):
                            target=rel.attrib["Target"];record=target.lstrip("/") if target.startswith("/") else "xl/pivotCache/"+target
                if not record or record not in names:
                    receipt(name,p,"MISSING_CACHE_RECORDS",fields=cols);continue
                rr=ET.fromstring(z.read(record))
                def decode(e,i):
                    kind=e.tag.rsplit("}",1)[-1];v=e.attrib.get("v","")
                    if kind=="x":
                        return decode(shared[i][int(v)],i)
                    if kind=="m": return ""
                    return v
                rows=[]
                for recordrow in rr:
                    if len(recordrow)!=len(cols):raise ValueError("pivot record width mismatch")
                    rows.append([decode(e,i) for i,e in enumerate(recordrow)])
                if int(rr.attrib.get("count",len(rows)))!=len(rows):raise ValueError("pivot record count mismatch")
                result="energy/"+name+"-"+p.rsplit("/",1)[1].replace(".xml",".csv")
                add_blob(result,csvbytes(cols,rows))
                receipt(name,p,"PASS",rows=len(rows),fields=cols,sample=rows[:3],path=ROOT+result,source_sha256=sha(raw),source_blob=blob)
    except Exception as e:receipt(name,"cache_decode","ERROR",error_type=type(e).__name__,detail=str(e)[:180])
# Reuse municipality dimension and fetch municipal enterprise indicators by exact prefix.
# Municipal geography codes from the producer's DGEG table are administrative DICOFRE, not INE geocod.
# Obtain INE native data without guessing the municipality classification or filtering invalid codes.
for sid,code,period in [("F20","0012087","2025"),("candidate-electricity","0014156","2024")]:
    for mode in ["metadata","year"]:
        params={"op":1 if mode=="metadata" else 2,"varcd":code,"lang":"PT"}
        if mode=="year":params["Dim1"]="S7A"+period
        url="https://www.ine.pt/ine/json_indicador/pindica.jsp?"+urllib.parse.urlencode(params)
        try:
            raw,obj=get_public(url);add_blob("ine/"+sid+"-"+mode+".json",raw)
            receipt(sid,mode,"PRESERVED_RESPONSE",bytes=len(raw),sha256=sha(raw),sample=str(obj)[:350])
        except Exception as e:receipt(sid,mode,"ERROR",error_type=type(e).__name__,detail=str(e)[:160])
# Query remaining Spanish TEN-T roads/rail at small page size and ESRI JSON (not GeoJSON if unsupported).
server="https://mapas.fomento.gob.es/arcgis/rest/services/Hermes/NEW_RED_TRANSEUROPEA_DE_TRANSPORTE__TEN_T_2024/MapServer"
scope="-10,39,-2,44"
for lid in [5,23,32,33,34]:
    try:
        _,meta=get_public(server+"/"+str(lid)+"?f=json")
        args={"where":"1=1","geometry":scope,"geometryType":"esriGeometryEnvelope","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outSR":"4326"}
        url=server+"/"+str(lid)+"/query?"
        _,ids=get_public(url+urllib.parse.urlencode({**args,"returnIdsOnly":"true","f":"json"}))
        keys=ids.get("objectIds")
        if keys is None:raise ValueError(str(ids)[:160])
        keys=sorted(keys);parts=[]
        for i in range(0,len(keys),50):
            batch=keys[i:i+50]
            raw,j=get_public(url+urllib.parse.urlencode({"objectIds":",".join(map(str,batch)),"outFields":"*","returnGeometry":"true","outSR":"4326","f":"json"}))
            fs=j.get("features")
            if fs is None or len(fs)!=len(batch):raise ValueError("feature batch count mismatch")
            parts.extend(fs)
        p="geo/ES-TENtec-layer-"+str(lid)+".json"
        add_blob(p,json.dumps({"metadata":meta,"spatialReference":{"wkid":4326},"features":parts},ensure_ascii=False).encode())
        receipt("TENtec-ES",str(lid),"PASS",name=meta.get("name"),parent=meta.get("parentLayer"),features=len(parts),path=ROOT+p)
    except Exception as e:receipt("TENtec-ES",str(lid),"ERROR",error_type=type(e).__name__,detail=str(e)[:180])
# Download official Portuguese network package via dados.gov.pt CKAN/udata API, with exact resource metadata.
try:
    url="https://dados.gov.pt/api/1/datasets/rede-rodoviaria-nacional/"
    raw,obj=get_public(url);add_blob("geo/PT-RRN-metadata.json",raw)
    for r in obj.get("resources",[]):
        u=r.get("url",""); title=r.get("title","")
        if not u.startswith("https://"):continue
        if r.get("format","").lower() not in ["zip","shp","shapefile","gpkg"] and not re.search(r"\.zip(?:$|\?)",u,re.I):continue
        try:
            with OPENER.open(urllib.request.Request(u,headers={"User-Agent":"MobilidadeNorte/1.0"}),timeout=90) as h: b=h.read(75_000_001)
            if len(b)>75_000_000 or not b.startswith(bytes.fromhex("504b0304")):raise ValueError("not a bounded ZIP")
            p="raw/PT-RRN-"+str(r.get("id","resource"))+".zip";add_blob(p,b)
            receipt("PT-RRN","download","PRESERVED_BYTES",title=title,url=u,bytes=len(b),sha256=sha(b),path=ROOT+p)
        except Exception as e:receipt("PT-RRN","download","ERROR",url=u,error_type=type(e).__name__,detail=str(e)[:160])
except Exception as e:receipt("PT-RRN","metadata","ERROR",error_type=type(e).__name__,detail=str(e)[:180])
# The APA archive exceeded 40 MB. Preserve chunks with exact full hash, not an arbitrary truncation.
try:
    url="https://sniambgeoviewer.apambiente.pt/Geodocs/gpkgzips/PGRI2C_PerigoIGT_gpkg.zip";h=hashlib.sha256();parts=[];size=0
    with tempfile.TemporaryDirectory() as td:
        f=pathlib.Path(td)/"apa.zip"
        with OPENER.open(urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte/1.0"}),timeout=120) as src,f.open("wb") as dst:
            while True:
                b=src.read(1024*1024)
                if not b:break
                size+=len(b)
                if size>250_000_000:raise ValueError("250 MB archive cap")
                h.update(b);dst.write(b)
        with zipfile.ZipFile(f) as z: members=[{"name":i.filename,"bytes":i.file_size,"crc":i.CRC} for i in z.infolist()]
        with f.open("rb") as src:
            i=0
            while True:
                b=src.read(8_000_000)
                if not b:break
                i+=1;p=f"raw/APA-PGRI2C.zip.part{i:03d}";add_blob(p,b);parts.append({"path":ROOT+p,"bytes":len(b),"sha256":sha(b)})
        receipt("APA-FLOOD","download","PRESERVED_CHUNKS",url=url,bytes=size,sha256=h.hexdigest(),parts=parts,members=members)
except Exception as e:receipt("APA-FLOOD","download","ERROR",error_type=type(e).__name__,detail=str(e)[:180])
store("receipt.json",{"status":"PRIVATE_STAGING_NOT_CANONICAL_ADMISSION","publication_authorized":False,"run_id":os.environ.get("GITHUB_RUN_ID"),"requests":RECEIPTS,"blobs":BLOBS})
for attempt in range(3):
    head=gh("git/ref/heads/"+BRANCH)["object"]["sha"]; tree=gh("git/commits/"+head)["tree"]["sha"]
    entries=[{"path":ROOT+name,"mode":"100644","type":"blob","content":content} for name,content in OUT.items()]
    entries += [{"path":ROOT+name,"mode":"100644","type":"blob","sha":s} for name,s in BLOBS.items()]
    nt=gh("git/trees","POST",{"base_tree":tree,"tree":entries},write=True)["sha"]
    new=gh("git/commits","POST",{"message":"MN: phase 4 municipal energy pivot caches and targeted geographic recovery","tree":nt,"parents":[head]},write=True)["sha"]
    try:
        gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_COMMIT",new,"FILES",len(entries),flush=True);break
    except urllib.error.HTTPError:
        if attempt==2:raise
        time.sleep(2)
