"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase27/"
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
        new=gh("git/commits","POST",{"message":"MN: F18 dated source road subset and network accessibility pilot","tree":nt,"parents":[head]},write=True)["sha"]
        try:
            gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_CHECKPOINT",new,flush=True);return
        except urllib.error.HTTPError:
            if attempt==4:raise
            time.sleep(2)




# Cartographic refinement; original data are reused, no changes to canonical registry.
import gzip, math, concurrent.futures
import numpy as np
import pandas as pd
import geopandas as gp
from shapely.geometry import box, LineString, Point
from shapely.ops import unary_union
from pyproj import Transformer
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap
BASE="statistics/assessments/norte-centro-2026-11-22/"
def readp(n):return read_private(BASE+n)[0]
def rdjson(n):return json.loads(readp(n))
def readparts(meta):
    def get(x):
        b=read_private(x["path"])[0]
        assert len(b)==x["bytes"] and sha(b)==x["sha256"]
        return b
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:return b"".join(pool.map(get,meta))
def public(url,timeout=60,post=None):
    req=urllib.request.Request(url,data=post,headers={"User-Agent":"NORTE2040-research/1.0", "Accept":"application/json"})
    with OPENER.open(req,timeout=timeout) as r:return json.load(r)
# External OD matrix, one consistent routing model, no concatenated domestic times.
orig=[("Leixões",-8.705,41.185),("Lousado",-8.535,41.350),("Viana do Castelo",-8.817,41.686),("Vila Real",-7.744,41.295),("Bragança",-6.758,41.806)]
dest=[("Aveiro / Cacia",-8.629,40.682),("Vigo",-8.721,42.240),("Zamora",-5.743,41.503),("Valladolid",-4.724,41.652),("Madrid",-3.704,40.418),("Irun / Biriatou",-1.750,43.335),("Vilar Formoso",-6.832,40.608)]
pts=orig+dest; coords=";".join(f"{x},{y}" for _,x,y in pts)
osrmurl=None; osrm=None
for host,path in [("routing.openstreetmap.de","routed-car/table/v1/driving/"),("router.project-osrm.org","table/v1/driving/")]:
    try:
        u="https://"+host+"/"+path+coords+"?sources="+";".join(map(str,range(len(orig))))+"&destinations="+";".join(map(str,range(len(orig),len(pts))))+"&annotations=duration,distance"
        a=public(u,45)
        if a.get("code")!="Ok":raise ValueError(str(a)[:200])
        osrm=a;osrmurl=u;break
    except Exception as e:receipt("OSRM","external_matrix","ERROR",host=host,detail=str(e)[:150])
if osrm:
    store("external-matrix-raw.json",{"url":osrmurl,"origins":orig,"destinations":dest,"response":osrm,"guard":"Car routing estimate, no HGV or traffic/delay guarantee; coordinate anchors, not terminal gates."})
    rows=[[a[0],b[0],round(osrm["durations"][i][j]/60) if osrm["durations"][i][j] is not None else "",round(osrm["distances"][i][j]/1000) if osrm.get("distances") and osrm["distances"][i][j] is not None else ""] for i,a in enumerate(orig) for j,b in enumerate(dest)]
    writecsv("external-matrix.csv",["origin","destination","minutes","distance_km"],rows)
    receipt("OSRM","external_matrix","PASS",url=osrmurl,rows=len(rows))
    commit("MATRIX_CHECKPOINT")
# Reuse national official geometries; territory and detailed grid.
p5=rdjson("phase5/receipt.json")
def request(s,t):return next(x for x in p5["requests"] if x["source_id"]==s and x["stage"]==t)
def gfrom(b):return gp.GeoDataFrame.from_features(json.loads(b)["features"],crs=4326).to_crs(3763)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    f1=pool.submit(readparts,request("CAOP2025","download")["parts"])
    f2=pool.submit(readparts,request("road","territorial_clip")["parts"])
    f3=pool.submit(readparts,request("rail","territorial_clip")["parts"])
    mun=gfrom(f1.result());road=gfrom(f2.result());rail=gfrom(f3.result())
n=mun[mun.nuts2=="Norte"].copy();c=mun[mun.nuts2=="Centro"].copy();assert len(n)>50
n["geometry"]=n.geometry.make_valid();c["geometry"]=c.geometry.make_valid()
N=n.geometry.union_all();C=c.geometry.union_all()
# Spain actual OSM main roads / operating rail, bounded query.
spanish={"road":[],"rail":[],"river":[]}
query='[out:json][timeout:40];(way["highway"~"^(motorway|trunk)$"](40.2,-9.5,43.9,-4.2);way["highway"="primary"]["ref"~"^(N-122|N-525|N-532|N-120|N-550)"](40.2,-9.5,43.9,-4.2);way["railway"="rail"](40.2,-9.5,43.9,-4.2);way["waterway"="river"]["name"~"Douro|Duero"](40.8,-8.9,42,-6.6););out geom;'
for host in ["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]:
    try:
        o=public(host,70,urllib.parse.urlencode({"data":query}).encode())
        for el in o.get("elements",[]):
            geom=el.get("geometry",[]);tag=el.get("tags",{})
            if len(geom)<2:continue
            way=LineString([(a["lon"],a["lat"]) for a in geom])
            typ="rail" if tag.get("railway")=="rail" else "river" if tag.get("waterway") else "road"
            spanish[typ].append({"geometry":way,"ref":tag.get("ref",""),"kind":tag.get("highway",""),"usage":tag.get("usage","")})
        receipt("OSM","external_geometries","PASS",url=host,counts={k:len(v) for k,v in spanish.items()});break
    except Exception as e:receipt("OSM","external_geometries","ERROR",url=host,detail=str(e)[:150])
# Build local map geometry and normalized simplified paths for compact document integration.
tr=Transformer.from_crs(4326,3763,always_xy=True)
def xy(lon,lat):return tr.transform(lon,lat)
def lines(g):
    if g.is_empty:return []
    if g.geom_type=="LineString":return [list(g.coords)]
    if hasattr(g,"geoms"):return [a for p in g.geoms for a in lines(p)]
    return []
def polygons(g):
    if g.is_empty:return []
    if g.geom_type=="Polygon":return [list(g.exterior.coords)]
    if hasattr(g,"geoms"):return [a for p in g.geoms for a in polygons(p)]
    return []
# Use a fixed frame showing Galicia, adjacent Castile and central Portugal.
window=box(*[xy(-9.25,40.15)[0],xy(-9.25,40.15)[1],xy(-5.25,43.05)[0],xy(-5.25,43.05)[1]])
# Native Portuguese categories and route identifiers; use both fields, no conflation of road class with TEN-T.
def classroad(row):
    cat=str(row.get("categoria","")).upper()
    refs=" ".join(str(row.get(k,"")) for k in ["roadnumber","road1","road2","road3","road4"])
    if "AUTO" in cat or re.search(r"\bA\s*\d+",refs):return "A"
    if re.search(r"\bIP\s*\d+",refs) or cat.startswith("IP") or "PRINCIPAL" in cat:return "IP"
    if re.search(r"\bIC\s*\d+",refs) or cat.startswith("IC") or "COMPLEMENTAR" in cat:return "IC"
    return ""
road["cls"]=road.apply(classroad,axis=1)
receipt("RRN","selected_classes","PASS",counts=road.cls.value_counts().to_dict(),native=road.categoria.astype(str).value_counts().head(20).to_dict())
roadlayers={}
for k in ["A","IP","IC"]:
    gg=road[road.cls==k].geometry
    roadlayers[k]=gg.union_all().intersection(window)
railop=rail[rail.exploracao.astype(str).str.match(r"(?i)^com explora")].geometry.union_all().intersection(window)
railother=rail[~rail.exploracao.astype(str).str.match(r"(?i)^com explora")].geometry.union_all().intersection(window)
ex={}
for k,v in spanish.items():
    if v:
        z=gp.GeoDataFrame(v,crs=4326).to_crs(3763)
        ex[k]=z.geometry.union_all().difference(N.union(C).buffer(100)).intersection(window) if k!="river" else z.geometry.union_all().intersection(window)
    else:ex[k]=LineString()
# Source data grid: incoming access to Porto, Famalicao, Braga, Viana and other selected urban hubs; not actual term gate.
grid=pd.read_csv(io.BytesIO(gzip.decompress(readp("phase24/F18-reachability-2km-cells.csv.gz"))))
sel=grid[(grid.direction=="inbound")&grid.hub.isin(["Porto","Viana do Castelo","Vila Nova de Famalicão","Braga","Vila Real","Bragança","Chaves","Mirandela","Penafiel"])]
gcols=["grid_x_2km_EPSG3763","grid_y_2km_EPSG3763"]
mn=sel.groupby(gcols).minimum_vertex_model_minutes.min().reset_index()
# All candidate urban nodes are already modeled; map selected core logistics-adjacent cities only, distinct from terminal access.
sel=grid[(grid.direction=="inbound")&grid.hub.isin(["Porto","Viana do Castelo","Vila Nova de Famalicão","Braga"])]
mn=sel.groupby(gcols).minimum_vertex_model_minutes.min().reset_index()
# Per-cell geometry clip to North; cell minimum denotes road vertices, not every resident.
cells=gp.GeoDataFrame(mn,geometry=[box(x*2000,y*2000,(x+1)*2000,(y+1)*2000) for x,y in mn[gcols].itertuples(index=False,name=None)],crs=3763)
cells=cells[cells.intersects(N)].copy();cells["geometry"]=cells.geometry.intersection(N)
cells["band"]=pd.cut(cells.minimum_vertex_model_minutes,[-.001,30,60,90],labels=["0–30","30–60","60–90"])
fig,ax=plt.subplots(figsize=(9,6.2));gp.GeoSeries([N],crs=3763).plot(ax=ax,color="#d8dce0",edgecolor="#56626b",linewidth=.45)
for k,col in zip(["0–30","30–60","60–90"],["#156f74","#78b5ad","#d7e8b8"]):
    cells[cells.band==k].plot(ax=ax,color=col,linewidth=0)
n.boundary.plot(ax=ax,color="#ffffff",linewidth=.21)
for label,lon,lat in [("Porto",-8.6103,41.1502),("Viana do Castelo",-8.8283,41.6935),("Famalicão",-8.5188,41.4065),("Braga",-8.428,41.5511)]:
    x,y=xy(lon,lat);ax.scatter(x,y,s=14,c="#172e43",zorder=5);ax.annotate(label,(x,y),xytext=(3,4),textcoords="offset points",fontsize=7)
ax.set_axis_off();ax.set_title("Acessibilidade rodoviária a quatro centros de atividade logística",fontsize=13,fontweight="bold")
ax.legend(handles=[Patch(facecolor=c,label=k+" min") for k,c in zip(["0–30","30–60","60–90"],["#156f74","#78b5ad","#d7e8b8"])]+[Patch(facecolor="#d8dce0",label="Sem registo ≤90 min")],loc="lower right",fontsize=8,frameon=False)
fig.text(.06,.025,"Proposta para validação • OSM/Geofabrik, rede 01.11.2026; CAOP 2025. Grelha de 2 km; mínimo de tempo até vértice de rede.\nAutomóvel, circulação livre. Centros urbanos como aproximação à área logística; não são acessos a terminais. Sem restrições HGV.",fontsize=7)
fig.savefig("/tmp/access.png",dpi=180,bbox_inches="tight");plt.close(fig);add_blob("accessibility-proposal.png",open("/tmp/access.png","rb").read())
# Maps with official Portuguese geometry. External coverage and Douro use actual lines when obtained.
nodes=[("Leixões",-8.705,41.185,"port","core"),("AFSC",-8.681,41.242,"air","core"),("Valongo",-8.498,41.189,"terminal","core"),("V. N. Gaia",-8.618,41.121,"terminal","core"),("Lousado",-8.535,41.350,"terminal","global"),("Vila Real",-7.720,41.274,"air","global"),("Bragança",-6.707,41.857,"air","global"),("Aveiro",-8.743,40.648,"port","global"),("Cacia",-8.629,40.682,"terminal","global"),("Pampilhosa",-8.432,40.334,"terminal","core"),("Alfarelos",-8.661,40.133,"terminal","core"),("Guarda",-7.230,40.553,"terminal","global")]
def basemap(ax):
    gp.GeoSeries([C.intersection(window),N.intersection(window)],crs=3763).plot(ax=ax,color=["#f0f1f1","#e5efec"],edgecolor="#8d9a9d",linewidth=.5)
    n.dissolve(by="nuts3").boundary.plot(ax=ax,color="#c3cfce",linewidth=.4)
    for label,lon,lat in [("GALIZA",-8.2,42.78),("CASTELA E LEÃO",-6.2,42.4),("CENTRO",-7.6,40.4),("NORTE",-7.5,41.35)]:
        x,y=xy(lon,lat);ax.text(x,y,label,fontsize=9,color="#65767b",ha="center",weight="bold",alpha=.9)
    ax.set_xlim(window.bounds[0],window.bounds[2]);ax.set_ylim(window.bounds[1],window.bounds[3]);ax.set_aspect("equal");ax.axis("off")
def plotline(ax,g,color,lw,ls="-",z=3):
    if not g.is_empty:ax.add_collection(LineCollection(lines(g),colors=color,linewidths=lw,linestyles=ls,zorder=z))
def pointnodes(ax):
    for name,lon,lat,kind,cls in nodes:
        x,y=xy(lon,lat)
        if not window.covers(Point(x,y)):continue
        mk={"port":"s","air":"^","terminal":"o"}[kind]
        ax.scatter(x,y,marker=mk,s=25,facecolor="#173f55" if cls=="core" else "white",edgecolor="#173f55",linewidth=.8,zorder=7)
        ax.annotate(name,(x,y),xytext=(4,3),textcoords="offset points",fontsize=6.5,zorder=8)
def draw(mode):
    fig,ax=plt.subplots(figsize=(10,7.2));basemap(ax)
    hs=[]
    if mode in ["road","summary"]:
        for k,col,lw in [("IC","#aeb9b9",.7),("IP","#bb7a32",1.0),("A","#326a80",1.2)]:
            plotline(ax,roadlayers[k],col,lw);hs.append(Line2D([0],[0],color=col,lw=2,label={"A":"Autoestradas","IP":"IP (não autoestrada)","IC":"IC (não autoestrada)"}[k]))
        plotline(ax,ex["road"],"#829caa",.7);hs.append(Line2D([0],[0],color="#829caa",label="Rede principal Espanha (OSM)" if spanish["road"] else "Espanha: sem geometria recuperada"))
    if mode in ["rail","summary"]:
        plotline(ax,railop,"#a74c47",1.5);plotline(ax,railother,"#aa9b95",.9,"--");plotline(ax,ex["rail"],"#a74c47",.65)
        hs.extend([Line2D([0],[0],color="#a74c47",label="Ferrovia em exploração (PT); rede OSM (ES)"),Line2D([0],[0],color="#aa9b95",ls="--",label="Outros segmentos RFN (PT)")])
    if mode=="summary":
        # Official Douro VND route approximation only where OSM river obtained; not all river is navigable.
        if spanish["river"]:
            a=ex["river"].intersection(box(xy(-8.75,40.95)[0],xy(-8.75,40.95)[1],xy(-6.68,41.55)[0],xy(-6.68,41.55)[1]))
            plotline(ax,a,"#1b92b1",2);hs.append(Line2D([0],[0],color="#1b92b1",label="Rio Douro (referência à VND)"))
        pointnodes(ax);hs.extend([Line2D([0],[0],marker=m,color="none",markeredgecolor="#173f55",markerfacecolor="#173f55",label=l) for m,l in [("s","Porto marítimo"),("^","Aeroporto / aeródromo"),("o","Terminal ferroviário-rodoviário")]])
    for name,lon,lat in [("Vigo",-8.721,42.240),("Ourense",-7.864,42.34),("Verín",-7.44,41.94),("Zamora",-5.743,41.503),("Viseu",-7.914,40.657),("Coimbra",-8.429,40.211),("Guarda",-7.266,40.538),("Braga",-8.428,41.551),("Porto",-8.61,41.15),("Bragança",-6.759,41.807),("Chaves",-7.472,41.74),("Vila Real",-7.746,41.298)]:
        x,y=xy(lon,lat)
        if window.covers(Point(x,y)):ax.scatter(x,y,s=6,c="#37474f",zorder=5);ax.annotate(name,(x,y),xytext=(3,-7),textcoords="offset points",fontsize=7,zorder=6)
    ax.set_title({"road":"Rede rodoviária estruturante","rail":"Rede ferroviária e continuidade ibérica","summary":"Redes e nós estratégicos — proposta de síntese"}[mode],fontsize=14,weight="bold")
    ax.legend(handles=hs,loc="lower left",fontsize=7,frameon=True,ncol=2 if mode=="summary" else 1)
    fig.text(.05,.025,"Fontes: DGT, CAOP 2025; rede rodoviária e ferroviária nacionais (dados.gov.pt); OSM (Espanha, quando disponível).\nNós selecionados: Regulamento (UE) 2024/1679, anexo II, localização indicativa. Fora de Portugal: sem classificação RTE-T.",fontsize=7)
    fig.savefig("/tmp/"+mode+".png",dpi=180,bbox_inches="tight");plt.close(fig);add_blob(mode+"-map.png",open("/tmp/"+mode+".png","rb").read())
for mode in ["road","rail","summary"]:draw(mode)
receipt("mapping","products","PASS",grid_cells=len(cells),spanish={k:len(v) for k,v in spanish.items()},guard="Draft for review; no official legal line classification; road classes prioritized A > IP > IC; selected nodes indicative.")
commit("COMPLETE_ATTEMPT")
