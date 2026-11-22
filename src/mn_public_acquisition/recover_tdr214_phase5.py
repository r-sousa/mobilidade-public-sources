"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase5/"
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
import math
PARENT="statistics/assessments/norte-centro-2026-11-22/"
P4=PARENT+"phase4/"
def readcsv(p):
    b,s=read_private(p);return list(csv.reader(io.StringIO(b.decode("utf-8-sig")))),s
def savecsv(path,headers,rows):
    add_blob(path,csvbytes(headers,rows))
def getbytes(url,cap=100_000_000):
    with OPENER.open(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"}),timeout=120) as r:
        b=r.read(cap+1)
    if len(b)>cap:raise ValueError("response exceeds cap")
    return b
# Source-native records, national totals control, and NUTS II/III + municipality aggregates.
cw,_=readcsv(PARENT+"municipal-nuts-crosswalk-dgeg-2024.csv")
import unicodedata
def norm(s):return "".join(c for c in unicodedata.normalize("NFKD",s.lower()) if not unicodedata.combining(c)).strip().replace(" ","").replace("-","")
lookup={(norm(r[1]),norm(r[7]),norm(r[8])):r[0] for r in cw[1:]}
for name,kind,unit,expect in [("DGEG-ECA-2024.xlsx","electricity","kWh",32551),("DGEG-PETROL-2.xlsx","petroleum","t",11327),("F170-1.xlsx","gas","10^3 Nm3",4606)]:
    try:
        p=P4+"energy/"+name+"-pivotCacheDefinition1.csv";rr,src=readcsv(p);rows=rr[1:];assert len(rows)==expect
        facts=[];ag=defaultdict(float);geos=defaultdict(set);keys=set();missing=0;conflicts=0;unmatched=Counter();totals=defaultdict(float)
        for r in rows:
            if kind=="electricity": product,val,activity,mun,dist,n1,old,n2,n3=r
            elif kind=="petroleum": val,product,activity,mun,dist,n1,old,n2,n3=r
            else:val,activity,mun,dist,n1,old,n2,n3=r;product="Gás natural"
            code=lookup.get((norm(mun),norm(n2),norm(n3)),"")
            if not code:unmatched[(mun,n2,n3)]+=1
            key=(product,activity,mun,dist,n1,n2,n3)
            if key in keys:conflicts+=1
            keys.add(key)
            if val=="":missing+=1;v=None
            else:v=float(val)
            if v is not None:
                totals[product]+=v
                for level,geo in [("PT","Portugal"),("NUTS2",n2),("NUTS3",n3)]:
                    ag[(level,geo,product,activity)]+=v
                    ag[(level,geo,product,"__all_activities__")]+=v
                if code:ag[("municipality",code,product,activity)]+=v;ag[("municipality",code,product,"__all_activities__")]+=v
            if n2 in ["Norte","Centro"]:
                geos[n2].add(mun);facts.append([2024,kind,product,activity,code,mun,n2,n3,unit,val])
        savecsv("energy/"+kind+"-municipal-facts.csv",["year","energy","product_or_voltage","activity","municipal_code","municipality","nuts2","nuts3","unit","value"],facts)
        savecsv("energy/"+kind+"-aggregates.csv",["year","energy","geo_level","geo","product_or_voltage","activity","unit","value"],[[2024,kind,*k,unit,v] for k,v in sorted(ag.items())])
        summary=[{"geo":k[1],"product":k[2],"value":v} for k,v in ag.items() if k[0]=="NUTS2" and k[1] in ["Norte","Centro"] and k[3]=="__all_activities__"]
        receipt(kind,"normalized","PASS",source_blob=src,rows=len(rows),selected=len(facts),unique=len(keys),duplicate_keys=conflicts,missing=missing,unmatched=[list(k)+[v] for k,v in unmatched.items()],municipalities={k:len(v) for k,v in geos.items()},national_by_product=dict(totals),region_by_product=summary,aggregate_rows=len(ag),unit=unit)
    except Exception as e:receipt(kind,"normalized","ERROR",error_type=type(e).__name__,detail=str(e)[:220])
# Acquire and preserve current operating rail network, and CAOP municipality polygons.
import geopandas as gpd
import pandas as pd
from shapely import make_valid
from shapely.geometry import shape
def preserve_bytes(path,b):
    if len(b)<=8_000_000:add_blob(path,b);return [{"path":ROOT+path,"bytes":len(b),"sha256":sha(b)}]
    parts=[]
    for i in range(0,len(b),8_000_000):
        p=path+".part"+str(i//8_000_000+1).zfill(3);a=b[i:i+8_000_000];add_blob(p,a);parts.append({"path":ROOT+p,"bytes":len(a),"sha256":sha(a)})
    return parts
def unzip_shp(b,td):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        out=pathlib.Path(td); paths=[x for x in z.namelist() if x.lower().endswith(".shp")]
        if not paths:raise ValueError("no shp")
        for x in z.infolist():
            if x.is_dir():continue
            target=out/pathlib.PurePosixPath(x.filename).name;target.write_bytes(z.read(x))
    return [(p,gpd.read_file(out/pathlib.PurePosixPath(p).name)) for p in paths]
with tempfile.TemporaryDirectory() as td:
    root=pathlib.Path(td); networks=[]
    try:
        b,src=read_private(P4+"raw/PT-RRN-6b646bf4-f569-405d-a3b7-bb6ff1a6c95a.zip")
        assert sha(b)=="ff08f8374309f29d50dcc50b0341f48867abb6b8c2fd11793b2de65a8ecaa4a6"
        (root/"road").mkdir()
        for p,g in unzip_shp(b,root/"road"):
            receipt("PT-RRN","inspect","PASS",layer=p,rows=len(g),crs=str(g.crs),fields=list(g.columns),sample=g.drop(columns=g.geometry.name).head(3).fillna("").astype(str).to_dict("records"))
            if g.crs and g.geom_type.isin(["LineString","MultiLineString"]).any():networks.append(("road",p,g))
    except Exception as e:receipt("PT-RRN","inspect","ERROR",detail=str(e)[:220])
    try:
        url="https://dados.gov.pt/s/resources/rede-ferroviaria-nacional/20260415-171819/rede-ferroviaria.zip";b=getbytes(url,25_000_000);add_blob("raw/PT-RFN.zip",b);(root/"rail").mkdir()
        receipt("PT-RFN","download","PASS",url=url,bytes=len(b),sha256=sha(b))
        for p,g in unzip_shp(b,root/"rail"):
            receipt("PT-RFN","inspect","PASS",layer=p,rows=len(g),crs=str(g.crs),fields=list(g.columns))
            if g.crs and g.geom_type.isin(["LineString","MultiLineString"]).any():networks.append(("rail",p,g))
    except Exception as e:receipt("PT-RFN","download_or_inspect","ERROR",detail=str(e)[:220])
    mun=None
    try:
        url="https://ogcapi.dgterritorio.gov.pt/collections/municipios/items?f=json&limit=50"
        features=[];visited=set()
        while url and url not in visited and len(visited)<20:
            visited.add(url);b=getbytes(url,60_000_000);j=json.loads(b);features.extend(j["features"])
            url=next((urllib.parse.urljoin(url,l["href"]) for l in j.get("links",[]) if l.get("rel")=="next"),None)
        if len(features)!=278:raise ValueError("municipality count "+str(len(features)))
        raw=json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False).encode();parts=preserve_bytes("geo/CAOP2025-municipios.geojson",raw)
        mun=gpd.GeoDataFrame.from_features(features,crs=4326).to_crs(3763)
        mun=mun[mun["nuts2"].isin(["Norte","Centro"])][["dtmn","municipio","nuts2","nuts3_cod","nuts3","geometry"]].copy()
        assert len(mun)==163 and mun["dtmn"].nunique()==163
        mun["geometry"]=mun.geometry.make_valid()
        receipt("CAOP2025","download","PASS",national=278,target=163,parts=parts,sha256=sha(raw),fields=list(mun.columns))
    except Exception as e:receipt("CAOP2025","download","ERROR",detail=str(e)[:220])
    # Reassemble verified APA archive and inspect all vector layers.
    flood=[]
    try:
        raw,_=read_private(P4+"receipt.json");r=json.loads(raw);rec=next(x for x in r["requests"] if x["source_id"]=="APA-FLOOD" and x["state"]=="PRESERVED_CHUNKS")
        zpath=root/"flood.zip";h=hashlib.sha256()
        with zpath.open("wb") as f:
            for p in rec["parts"]:
                b,_=read_private(p["path"]);assert sha(b)==p["sha256"];h.update(b);f.write(b)
        assert h.hexdigest()==rec["sha256"] and zpath.stat().st_size==rec["bytes"]
        with zipfile.ZipFile(zpath) as z:
            gp=root/"flood.gpkg"
            with z.open("PGRI2C_PerigoIGT.gpkg") as src,gp.open("wb") as dst:
                import shutil;shutil.copyfileobj(src,dst)
        for layer,geomtype in gpd.list_layers(gp).itertuples(index=False,name=None):
            g=gpd.read_file(gp,layer=layer)
            receipt("APA-FLOOD","inspect","PASS",layer=layer,geometry_type=geomtype,rows=len(g),crs=str(g.crs),fields=list(g.columns),sample=g.drop(columns=g.geometry.name).head(2).fillna("").astype(str).to_dict("records"))
            if g.crs and g.geom_type.isin(["Polygon","MultiPolygon"]).any():flood.append((layer,g.to_crs(3763)))
    except Exception as e:receipt("APA-FLOOD","inspect","ERROR",detail=str(e)[:220])
    if mun is not None:
        for mode,layer,g in networks:
            try:
                g=g.to_crs(3763).reset_index(drop=True);g["source_id"]=g.index.astype(str);g["geometry"]=g.geometry.make_valid()
                # Retain source schema; do not infer TEN-T classes or operating state from route names.
                target=gpd.overlay(g,mun,how="intersection",keep_geom_type=True)
                target["length_km"]=target.length/1000
                summary=target.groupby(["nuts2","nuts3_cod","nuts3"],dropna=False)["length_km"].sum().reset_index()
                savecsv("geo/"+mode+"-nuts3-length.csv",list(summary.columns),summary.itertuples(index=False,name=None))
                raw=target.to_crs(4326).to_json(drop_id=True).encode();parts=preserve_bytes("geo/"+mode+"-norte-centro.geojson",raw)
                receipt(mode,"territorial_clip","PASS",layer=layer,features=len(target),length_by_region=summary.groupby("nuts2")["length_km"].sum().to_dict(),parts=parts,guard="source geometrical length; includes native classifications, not unique route-km or capacity")
                for fl,fg in flood:
                    try:
                        fg=fg[fg.geometry.notna() & ~fg.geometry.is_empty].copy();fg["geometry"]=fg.geometry.make_valid()
                        # Union each source layer: overlapping hazard polygons counted once within that layer.
                        haz=fg.geometry.union_all();lens=target.geometry.intersection(haz).length/1000
                        vals=target[["source_id","nuts2","nuts3_cod","nuts3","length_km"]].copy();vals["exposed_km"]=lens
                        summary=vals.groupby(["nuts2","nuts3_cod","nuts3"],dropna=False)[["length_km","exposed_km"]].sum().reset_index()
                        safe=re.sub(r"[^a-zA-Z0-9_-]","_",fl);savecsv("geo/"+mode+"-flood-"+safe+".csv",list(summary.columns),summary.itertuples(index=False,name=None))
                        receipt(mode,"flood_intersection","PASS",source_layer=fl,summary=summary.groupby("nuts2")[["length_km","exposed_km"]].sum().reset_index().to_dict("records"),guard="geometric exposure only; no vulnerability, probability or expected losses inferred; source layers not additive")
                    except Exception as e:receipt(mode,"flood_intersection","ERROR",source_layer=fl,detail=str(e)[:220])
            except Exception as e:receipt(mode,"territorial_clip","ERROR",detail=str(e)[:220])
# Targeted producer series. Preserve both exact result and error payload.
for sid,code in [("rail-electrification","0014169")]:
    for y in ["2024","2025"]:
        try:
            url="https://www.ine.pt/ine/json_indicador/pindica.jsp?"+urllib.parse.urlencode({"op":2,"varcd":code,"lang":"PT","Dim1":"S7A"+y})
            b,j=get_public(url);add_blob("ine/"+sid+"-"+y+".json",b)
            rr=[r for block in j if isinstance(block,dict) for year,rows in block.get("Dados",{}).items() for r in rows if year==y]
            receipt(sid,y,"PASS" if rr else "ERROR_BODY",rows=len(rr),sample=rr[:5],url=url)
        except Exception as e:receipt(sid,y,"ERROR",detail=str(e)[:220])
# APA and alternate accessible links: direct producer landing page with normal UA; archive link discovered from actual HTML only.
from html.parser import HTMLParser
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.a=None
    def handle_starttag(self,t,attrs):
        if t=="a" and dict(attrs).get("href"):self.a=[dict(attrs)["href"],""]
    def handle_data(self,d):
        if self.a:self.a[1]+=d
    def handle_endtag(self,t):
        if t=="a" and self.a:self.links.append(self.a);self.a=None
for page,prefix,pattern in [
("https://apambiente.pt/clima/distribuicao-espacial-de-emissoes-nacionais-0","APA-emissions",r"2023.*xlsx|xlsx.*2023|2023.*excel|excel.*2023"),
("https://www.anac.pt/vPT/Generico/PublicacoesINAC/newslettersdetrafego/Paginas/NewslettersdeTrafego.aspx","ANAC",r"(setembro|agosto|julho|junho)\s*2026"),
("https://www.imt-ip.pt/biblioteca/reportorio-geral/estatisticas-repertorio-geral/relatorios-setoriais-imt/","IMT",r"2026.*\.(xlsx|pdf)|2025.*\.xlsx")
]:
    try:
        raw=getbytes(page,4_000_000);p=Links();p.feed(raw.decode("utf-8","replace"));found=[]
        for u,lab in p.links:
            u=urllib.parse.urljoin(page,u)
            if re.search(pattern,u+" "+lab,re.I) and urllib.parse.urlparse(u).scheme=="https" and u not in found:found.append(u)
        receipt(prefix,"discover","LINKS_FOUND" if found else "NO_FILE_LINKS",links=found)
        for i,u in enumerate(found[:8]):
            try:
                b=getbytes(u,30_000_000)
                ext=".pdf" if b.startswith(b"%PDF") else ".xlsx" if b.startswith(bytes.fromhex("504b0304")) else ".unknown"
                if ext==".unknown":raise ValueError("not recognised file")
                path="raw/"+prefix+"-"+str(i+1)+ext;parts=preserve_bytes(path,b)
                receipt(prefix,"download","PASS",url=u,bytes=len(b),sha256=sha(b),parts=parts)
            except Exception as e:receipt(prefix,"download","ERROR",url=u,detail=str(e)[:160])
    except Exception as e:receipt(prefix,"discover","ERROR",detail=str(e)[:180])
store("receipt.json",{"status":"PRIVATE_STAGING_NOT_CANONICAL_ADMISSION","publication_authorized":False,"run_id":os.environ.get("GITHUB_RUN_ID"),"requests":RECEIPTS,"blobs":BLOBS})
for attempt in range(3):
    head=gh("git/ref/heads/"+BRANCH)["object"]["sha"]; tree=gh("git/commits/"+head)["tree"]["sha"]
    entries=[{"path":ROOT+name,"mode":"100644","type":"blob","content":content} for name,content in OUT.items()]
    entries += [{"path":ROOT+name,"mode":"100644","type":"blob","sha":s} for name,s in BLOBS.items()]
    nt=gh("git/trees","POST",{"base_tree":tree,"tree":entries},write=True)["sha"]
    new=gh("git/commits","POST",{"message":"MN: phase5 regional energy normalization and official network flood overlays","tree":nt,"parents":[head]},write=True)["sha"]
    try:
        gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_COMMIT",new,"FILES",len(entries),flush=True);break
    except urllib.error.HTTPError:
        if attempt==2:raise
        time.sleep(2)
