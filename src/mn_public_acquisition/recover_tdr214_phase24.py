"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase24/"
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




import gzip,math
import numpy as np
import osmium
from array import array
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra,connected_components
from scipy.spatial import cKDTree
from pyproj import Transformer
from collections import Counter,defaultdict
URL="https://download.geofabrik.de/europe/portugal-261101.osm.pbf"
BBOX="-9.8,38.9,-6.0,42.3"
SPEEDS={"motorway":110,"motorway_link":45,"trunk":90,"trunk_link":45,"primary":75,"primary_link":40,"secondary":65,"secondary_link":35,"tertiary":50,"tertiary_link":30,"unclassified":35,"residential":30,"living_street":15,"service":20}
CITIES=["Porto","Braga","Guimarães","Viana do Castelo","Vila Real","Bragança","Chaves","Mirandela","Peso da Régua","Lamego","Aveiro","Coimbra","Leiria","Viseu","Guarda","Castelo Branco","Figueira da Foz","Covilhã","Vila Nova de Famalicão","Penafiel"]
def parts(name,p):
    out=[];hh=hashlib.sha256()
    with p.open("rb") as f:
        i=0
        while True:
            b=f.read(8_000_000)
            if not b:break
            i+=1;hh.update(b);part=f"{name}.part{i:03}";add_blob(part,b);out.append({"path":ROOT+part,"bytes":len(b),"sha256":sha(b)})
    return {"sha256":hh.hexdigest(),"bytes":p.stat().st_size,"parts":out}
def cmd(args):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=600).stdout
with tempfile.TemporaryDirectory() as td:
    d=pathlib.Path(td);p=d/"source.osm.pbf";md5url=URL+".md5"
    # Reuse the exact checksum-verified private checkpoint from the prior run.
    # No source download or duplicate blob writes when the preserved parts validate.
    p3=d/"roads.osm.pbf"
    try:
        prior=readj(ROOT+"receipt.json")
        native=next(r for r in prior["requests"] if r["source_id"]=="F18" and r["stage"]=="source_subset" and r["state"]=="PASS")
        assert native["source_url"]==URL and native["bbox"]==BBOX
        raw=native["filtered"]; hh=hashlib.sha256(); total=0
        with p3.open("wb") as f:
            for part in raw["parts"]:
                b,blob=read_private(part["path"])
                assert len(b)==part["bytes"] and sha(b)==part["sha256"]
                f.write(b);hh.update(b);total+=len(b)
        assert total==raw["bytes"] and hh.hexdigest()==raw["sha256"]
        RECEIPTS.append(native)
        receipt("F18","reuse_checkpoint","PASS",bytes=total,sha256=hh.hexdigest(),parts=len(raw["parts"]))
    except Exception as e:
        receipt("F18","reuse_checkpoint","ERROR",error_type=type(e).__name__,detail=str(e)[:200])
        raise RuntimeError("Preserved source checkpoint must be recovered before further processing") from e
    nodes={};nodeids=array("q");lon=array("d");lat=array("d");src=array("I");dst=array("I");sec=array("f");wayids=array("q");meters=array("f");ways=Counter();seenplaces=[];excluded=Counter();speedflags=Counter();barriers=set()
    def tag_allowed(t):
        a=t.get("motorcar",t.get("motor_vehicle",t.get("vehicle",t.get("access",""))))
        return a not in ("no","private","agricultural","forestry")
    def ix(nd):
        k=nd.ref
        if k not in nodes:
            nodes[k]=len(nodeids);nodeids.append(k);lon.append(nd.location.lon);lat.append(nd.location.lat)
        return nodes[k]
    def speed_tag(s):
        if not s:return None
        s=s.strip().lower()
        if s.endswith(" mph"):
            try:return float(s[:-4])*1.609344
            except:return None
        try:
            v=float(s)
            return v if 5<=v<=150 else None
        except:return None
    def dist(a,b):
        x=(b.location.lon-a.location.lon)*111195*math.cos(math.radians((a.location.lat+b.location.lat)/2))
        y=(b.location.lat-a.location.lat)*111195
        return math.hypot(x,y)
    class Handler(osmium.SimpleHandler):
        def node(self,n):
            if n.tags.get("place") in ("city","town","village") and n.tags.get("name") in CITIES and n.location.valid():
                seenplaces.append([n.tags.get("name"),n.id,n.tags.get("place"),n.location.lon,n.location.lat,n.tags.get("population","")])
            if n.tags.get("barrier") and not tag_allowed(n.tags):barriers.add(n.id)
        def way(self,w):
            t=w.tags;h=t.get("highway")
            if h not in SPEEDS:return
            if not tag_allowed(t):excluded["access"]+=1;return
            if h=="service" and t.get("service") in ("parking_aisle","driveway","drive-through"):excluded["service_subclass"]+=1;return
            if t.get("area")=="yes":excluded["area"]+=1;return
            o=t.get("oneway:motorcar",t.get("oneway",""))
            if o=="-1":forward,back=False,True
            elif o in ("yes","1","true") or (o not in ("no","0","false") and (h=="motorway" or t.get("junction") in ("roundabout","circular"))):forward,back=True,False
            else:forward,back=True,True
            base=SPEEDS[h];general=speed_tag(t.get("maxspeed",""))
            if general:speedflags["explicit_general"]+=1
            else:speedflags["assumed_class"]+=1
            sf=min(base,speed_tag(t.get("maxspeed:forward","")) or general or base);sb=min(base,speed_tag(t.get("maxspeed:backward","")) or general or base)
            ways[h]+=1
            wn=list(w.nodes)
            for a,b in zip(wn,wn[1:]):
                if not a.location.valid() or not b.location.valid():excluded["missing_location"]+=1;continue
                if a.ref==b.ref:continue
                if a.ref in barriers or b.ref in barriers:excluded["explicit_restricted_barrier_arc"]+=1;continue
                length=dist(a,b)
                if length<.001:continue
                i,j=ix(a),ix(b)
                if forward:src.append(i);dst.append(j);sec.append(length*3.6/sf);wayids.append(w.id);meters.append(length)
                if back:src.append(j);dst.append(i);sec.append(length*3.6/sb);wayids.append(w.id);meters.append(length)
    Handler().apply_file(str(p3),locations=True,idx="flex_mem")
    assert len(nodes)>10000 and len(src)>10000
    # Same OSM node connectivity only; choose cheapest edge for duplicate ordered node pairs.
    u=np.frombuffer(src,dtype=np.uint32);v=np.frombuffer(dst,dtype=np.uint32);w=np.frombuffer(sec,dtype=np.float32)
    order=np.lexsort((w,v,u));u0=u[order];v0=v[order]
    keep=np.ones(len(order),dtype=bool);keep[1:]=(u0[1:]!=u0[:-1])|(v0[1:]!=v0[:-1])
    order=order[keep];N=len(nodes)
    G=csr_matrix((w[order],(u[order],v[order])),shape=(N,N),dtype=np.float32)
    del nodes
    count,comp=connected_components(G,directed=True,connection="weak");sizes=np.bincount(comp);largest=int(sizes.argmax())
    trans=Transformer.from_crs(4326,3763,always_xy=True)
    xx,yy=trans.transform(np.frombuffer(lon,dtype=np.float64),np.frombuffer(lat,dtype=np.float64));xy=np.column_stack([xx,yy]);idx=np.flatnonzero(comp==largest)
    tree=cKDTree(xy[idx]);hubs=[]
    for name in CITIES:
        choices=[x for x in seenplaces if x[0]==name]
        if not choices:continue
        best=[x for x in choices if x[2]=="city"] or [x for x in choices if x[2]=="town"] or choices
        if len(best)!=1:continue
        a=best[0];x,y=trans.transform(a[3],a[4]);distance,j=tree.query([x,y]);i=int(idx[j])
        if distance>1000:continue
        hubs.append([*a,i,float(distance),int(nodeids[i])])
    writecsv("F18-city-hubs.csv",["name","osm_place_node","place_class","longitude","latitude","native_population","graph_index","snap_distance_m","snap_osm_node"],hubs)
    writecsv("F18-city-place-candidates.csv",["name","osm_place_node","place_class","longitude","latitude","native_population"],seenplaces)
    graph=d/"F18-road-directed-graph.npz"
    np.savez_compressed(graph,indptr=G.indptr,indices=G.indices,seconds=G.data,osm_node_ids=np.frombuffer(nodeids,dtype=np.int64),longitude=np.frombuffer(lon,dtype=np.float64),latitude=np.frombuffer(lat,dtype=np.float64))
    graphmeta=parts("graph/F18-road-directed-graph.npz",graph)
    output=[];reach=[]
    # Cell observation = minimum directed network travel time to any modeled road vertex in a 2 km cell.
    gx=np.floor(np.asarray(xx)/2000).astype(np.int32);gy=np.floor(np.asarray(yy)/2000).astype(np.int32)
    keys=np.stack([gx,gy],axis=1);cells,cellidx=np.unique(keys,axis=0,return_inverse=True)
    cellids=cellidx.reshape(-1);gt=G.T.tocsr()
    for hub in hubs:
        for direction,mat in [("outbound",G),("inbound",gt)]:
            ds=dijkstra(mat,directed=True,indices=hub[6],limit=180*60)
            assert ds[hub[6]]==0
            if direction=="outbound":
                for b in hubs:
                    t=float(ds[b[6]])
                    output.append([hub[0],b[0],t/60 if math.isfinite(t) else "", "FINITE_WITHIN_180_MIN" if math.isfinite(t) else "OVER_180_OR_UNREACHABLE"])
            minimum=np.full(len(cells),np.inf);np.minimum.at(minimum,cellids,ds)
            for k in np.flatnonzero(minimum<=90*60):
                reach.append([hub[0],direction,int(cells[k,0]),int(cells[k,1]),float(minimum[k]/60),30 if minimum[k]<=1800 else 60 if minimum[k]<=3600 else 90])
    writecsv("F18-road-hub-travel-times.csv",["origin","destination","model_minutes","state"],output)
    add_blob("F18-reachability-2km-cells.csv.gz",gzip.compress(csvbytes(["hub","direction","grid_x_2km_EPSG3763","grid_y_2km_EPSG3763","minimum_vertex_model_minutes","threshold_min"],reach),mtime=0))
    receipt("F18","road_access_model","PASS",nodes=N,directed_arcs=int(G.nnz),native_arcs=len(src),weak_components=int(count),largest_component_nodes=int(sizes[largest]),ways=dict(ways),excluded=dict(excluded),speed_provenance=dict(speedflags),hubs=[x[0] for x in hubs],snap_max_m=max([x[7] for x in hubs],default=None),matrix_rows=len(output),grid_rows=len(reach),graph=graphmeta,defaults_kmh=SPEEDS,guards=["Passenger car free-flow indicative times, not real traffic or HGV routing","No turn-restriction, traffic signal, gradient, toll, closure or border crossing delay modelling","Native OSM shared node topology, direction and explicit access restrictions; maxspeed used as cap","2km cell minimum at network vertices is not full continuous isochrone or population coverage","Bounds cut routes leaving region; all matrix values >180 min or disconnected remain absent"])
    commit("COMPLETE_ATTEMPT")
