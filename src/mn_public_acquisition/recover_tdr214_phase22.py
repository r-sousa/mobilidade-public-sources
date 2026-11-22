"""Bounded, preserved-first Norte/Centro acquisition; outputs private only."""
import base64, hashlib, json, os, pathlib, tempfile, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from itertools import product

PRIVATE = "r-sousa/EU-transp-weekly"
BRANCH = "mobilidade-norte-recovery-20260919"
ROOT = "statistics/assessments/norte-centro-2026-11-22/phase22/"
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
        new=gh("git/commits","POST",{"message":"MN: Norte-Centro official network boundary intersections","tree":nt,"parents":[head]},write=True)["sha"]
        try:
            gh("git/refs/heads/"+BRANCH,"PATCH",{"sha":new,"force":False},write=True);print("PRIVATE_CHECKPOINT",new,flush=True);return
        except urllib.error.HTTPError:
            if attempt==4:raise
            time.sleep(2)




import geopandas as gpd
from shapely.geometry import Point, shape, mapping
from shapely.ops import unary_union
from collections import Counter
def load_pieces(r):
    out=bytearray()
    for x in r["parts"]:
        b,_=read_private(x["path"]);assert sha(b)==x["sha256"];out.extend(b)
    assert sha(out)==r["sha256"]
    return bytes(out)
def points(g):
    if g.is_empty:return []
    if g.geom_type=="Point":return [g]
    if g.geom_type in ["MultiPoint","GeometryCollection"]:return [p for v in g.geoms for p in points(v)]
    return []
def intersect_lines(g):
    if g.is_empty:return []
    if g.geom_type in ("LineString","MultiLineString"):return [g]
    if g.geom_type=="GeometryCollection":return [p for v in g.geoms for p in intersect_lines(v)]
    return []
r=readj(PARENT+"phase5/receipt.json")
caop=next(x for x in r["requests"] if x["source_id"]=="CAOP2025" and x["stage"]=="download" and x["state"]=="PASS")
mun=gpd.GeoDataFrame.from_features(json.loads(load_pieces(caop))["features"],crs="EPSG:4326").to_crs(3763)
assert len(mun)==278
n=mun[mun.nuts2=="Norte"];c=mun[mun.nuts2=="Centro"];assert len(n)==86 and len(c)==77
pn=unary_union(n.geometry);pc=unary_union(c.geometry);shared=pn.boundary.intersection(pc.boundary)
assert shared.length>10000
b,_=read_private(PARENT+"phase4/raw/PT-RRN-6b646bf4-f569-405d-a3b7-bb6ff1a6c95a.zip");assert sha(b)=="ff08f8374309f29d50dcc50b0341f48867abb6b8c2fd11793b2de65a8ecaa4a6"
rb,_=read_private(PARENT+"phase5/raw/PT-RFN.zip");assert sha(rb)=="6065ac244973d192ae705008fe0a6c4fc595b49d74c9f30369fadd22ebef7e19"
with tempfile.TemporaryDirectory() as td:
    a=pathlib.Path(td)/"rrn.zip";a.write_bytes(b);f=pathlib.Path(td)/"rfn.zip";f.write_bytes(rb)
    rr=gpd.read_file(a).to_crs(3763);rf=gpd.read_file(f).to_crs(3763)
    assert len(rr)==4077 and len(rf)==59
    cross=[];overlap=[];features=[]
    for mode,df,filter_col,filter_val,name_col in [("road",rr,"estado","Construído","roadnumber"),("rail",rf,"exploracao","Com Exploração","designacao")]:
        for idx,x in df[df[filter_col]==filter_val].iterrows():
            geom=x.geometry
            if not geom.intersects(shared):continue
            z=geom.intersection(shared)
            # Boundary overlaps kept separate from crossing candidates.
            for l in intersect_lines(z):overlap.append([mode,idx,x[name_col],l.length])
            for p in points(z):
                # A boundary contact is not necessarily a crossing; require line interior in both regions locally.
                local=geom.intersection(p.buffer(100))
                ln=local.intersection(pn).length;lc=local.intersection(pc).length
                valid=ln>1 and lc>1
                aliases="|".join(str(x.get(q,"") or "") for q in ["road1","road2","road3","road4"]) if mode=="road" else ""
                cross.append([mode,idx,x[name_col],x.get("categoria",""),aliases,p.x,p.y,ln,lc,valid])
                features.append({"type":"Feature","geometry":mapping(p),"properties":{"mode":mode,"source_index":int(idx),"native_name":str(x[name_col]),"category":str(x.get("categoria","")),"crosses_both_regions_local":bool(valid)}})
    hdr=["mode","source_index","native_name","category","aliases","x_pt_tm06","y_pt_tm06","north_local_m","center_local_m","both_sides"]
    writecsv("boundary-intersections-native.csv",hdr,cross);writecsv("boundary-overlaps-native.csv",["mode","source_index","name","boundary_overlap_m"],overlap)
    valid=[x for x in cross if x[-1]]
    # Cluster only same native designation, within 50 m. Counts remain geometric, not infrastructure capacity.
    clusters=[]
    for x in sorted(valid,key=lambda x:(x[0],str(x[2]),x[5],x[6])):
        m=next((g for g in clusters if g[0]==x[0] and g[1]==x[2] and Point(g[2],g[3]).distance(Point(x[5],x[6]))<=50),None)
        if m:m[4]+=1
        else:clusters.append([x[0],x[2],x[5],x[6],1,x[3],x[4]])
    geo=gpd.GeoDataFrame(clusters,columns=["mode","native_name","x","y","native_contacts","category","aliases"],geometry=[Point(g[2],g[3]) for g in clusters],crs=3763).to_crs(4326)
    add_blob("boundary-crossing-candidates.geojson",geo.to_json(drop_id=True).encode())
    # Locate earlier OSM/RRN junction centres using official municipal polygons, preserving uncertain statuses.
    nodes,_=readcsv(PARENT+"motorway-nodes-v6-norte-centro-boundary-candidates.csv")
    rows=[]
    for a in nodes[1:]:
        rid,road,name,status,lon,lat,seq,hh=a
        if not lon or not lat:rows.append([*a,"","","",None]);continue
        p=gpd.GeoSeries([Point(float(lon),float(lat))],crs=4326).to_crs(3763).iloc[0]
        z=mun[mun.geometry.covers(p)]
        rows.append([*a,"|".join(z.dtmn.astype(str)),"|".join(z.municipio.astype(str)),"|".join(z.nuts2.astype(str)),p.distance(shared)])
    writecsv("boundary-junctions-municipal-locations.csv",nodes[0]+["dtmn","municipality","nuts2","distance_boundary_m"],rows)
    # Candidate exact source sublinks with supported endpoints in opposing regions.
    by=defaultdict(list)
    for a in rows:by[a[1]].append(a)
    pairs=[]
    for road,ls in by.items():
        ls.sort(key=lambda a:int(a[6]))
        for a,b in zip(ls,ls[1:]):
            if int(b[6])-int(a[6])!=1:continue
            if {a[10],b[10]}!={"Norte","Centro"}:continue
            if not(a[3].endswith("SUPPORTED") and b[3].endswith("SUPPORTED")):continue
            pairs.append([road,a[2]+" – "+b[2],a[0],b[0],a[9],b[9],a[10],b[10]])
    writecsv("supported-cross-region-sublink-candidates.csv",["road","native_sublink_candidate","node_a_id","node_b_id","municipality_a","municipality_b","region_a","region_b"],pairs)
    receipt("RRN-RFN-CAOP","boundary_intersections","PASS",shared_boundary_km=shared.length/1000,native_contacts=len(cross),valid_local_contacts=len(valid),clustered_count=len(clusters),by_mode=dict(Counter(x[0] for x in clusters)),motorway_candidates=[x for x in clusters if x[0]=="road" and x[5]=="Auto-estrada"],rail_candidates=[x for x in clusters if x[0]=="rail"],boundary_overlaps=len(overlap),junction_candidates=len(rows),supported_sublinks=pairs,guard="Geometric crossings of current official RRN/RFN and administrative boundary. Not traffic OD, complete all roads inventory, or unique junction certification. Cluster same road name only. Sublink candidates require exact native label verification.")
commit("COMPLETE_ATTEMPT")
