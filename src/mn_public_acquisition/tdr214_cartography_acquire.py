"""Private sink for new NV37–NV40. Public source extraction, no private rows in logs."""
import os,json,hashlib,base64,urllib.request,urllib.parse,subprocess,tempfile,pathlib,sys,time,re,concurrent.futures
REPO="r-sousa/EU-transp-weekly"
REF="norte2040-tdr214-visual-catalogue"
SRCREF="mobilidade-norte-recovery-20260919"
ROOT="statistics/assessments/norte2040-tdr214/visuals/"
DATA="statistics/assessments/norte-centro-2026-11-22/"
READ=os.environ.get("MN_PRIVATE_READ_TOKEN") or os.environ.get("MN_PRIVATE_SINK_TOKEN")
WRITE=os.environ.get("MN_PRIVATE_SINK_TOKEN")
if not READ or not WRITE:raise SystemExit("Private bridge tokens unavailable")
class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        nxt=super().redirect_request(req,fp,code,msg,headers,newurl)
        if nxt and urllib.parse.urlparse(newurl).hostname!=urllib.parse.urlparse(req.full_url).hostname:nxt.remove_header("Authorization")
        return nxt
opener=urllib.request.build_opener(SafeRedirect())
def gh(path,body=None,method="GET",write=False):
    h={"Authorization":"Bearer "+(WRITE if write else READ),"Accept":"application/vnd.github+json","User-Agent":"Norte2040-visual-render/1.0"}
    if body is not None:h["Content-Type"]="application/json"
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+"/"+path,data=json.dumps(body).encode() if body is not None else None,headers=h,method=method)
    for n in range(3):
        try:
            with opener.open(req,timeout=120) as f:return json.load(f)
        except Exception:
            if write or n==2:raise
            time.sleep(2**n)
def blob(pin):
    z=gh("git/blobs/"+pin);b=base64.b64decode(z["content"])
    assert hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()==pin
    return b
def file(path,ref,pin=None):
    m=gh("contents/"+urllib.parse.quote(path,safe="/")+"?ref="+urllib.parse.quote(ref,safe=""))
    if pin:assert m["sha"]==pin
    return blob(m["sha"])
def sha(raw):return hashlib.sha256(raw).hexdigest()

import gzip, shutil, collections, math, csv
import osmium
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import transform
from pyproj import Transformer
OUT=ROOT+"cartography/rebuild/"
def commit_files(files,label):
    entries=[]
    for name,raw in files.items():
        assert len(raw)<50_000_000
        z=gh("git/blobs",{"content":base64.b64encode(raw).decode(),"encoding":"base64"},"POST",True)
        entries.append({"path":OUT+name,"mode":"100644","type":"blob","sha":z["sha"]})
    for i in range(3):
        head=gh("git/ref/heads/"+REF)["object"]["sha"];tree=gh("git/commits/"+head)["tree"]["sha"]
        nt=gh("git/trees",{"base_tree":tree,"tree":entries},"POST",True)["sha"]
        c=gh("git/commits",{"message":label,"tree":nt,"parents":[head]},"POST",True)["sha"]
        try:gh("git/refs/heads/"+REF,{"sha":c,"force":False},"PATCH",True);return
        except Exception:
            if i==2:raise
            time.sleep(2)
def dump(j):return (json.dumps(j,ensure_ascii=False,indent=2)+"\n").encode()
def packed(j):return gzip.compress(json.dumps(j,ensure_ascii=False,separators=(",",":")).encode(),mtime=0)
cfgraw=file(ROOT+"cartography/rebuild-inputs.json",REF)
cfg=json.loads(cfgraw)
bounds=cfg["bbox_wgs84"]; bb=box(*bounds)
allowed={"motorway","trunk","primary","motorway_link","trunk_link","primary_link"}
keys={"name","name:pt","name:es","ref","int_ref","highway","railway","electrified","voltage","frequency","gauge","usage","service","tracks","maxspeed","lanes","oneway","access","hgv","maxheight","maxweight","maxwidth","maxlength","maxaxleload","junction","waterway","aeroway","harbour","industrial","landuse","barrier","iata","icao","operator","construction","proposed","disused","freight","cargo","place","population"}
def fields(o):return {t.k:t.v for t in o.tags if t.k in keys}
def point_kind(t):
    if t.get("aeroway") in ("aerodrome","terminal"):return "airport"
    if t.get("harbour") in ("yes","port","commercial") or t.get("industrial") in ("port","logistics"):return "facility"
    if t.get("railway") in ("freight_terminal","yard","station") and t.get("name"):return "rail_node"
    if t.get("barrier") in ("gate","lift_gate") and t.get("name"):return "gate"
    if t.get("place") in ("city","town") and t.get("name"):return "urban"
    if t.get("name") and any(k in t["name"].casefold() for k in ("portaria principal","terminal de carga","porto de leixões","porto de viana","terminal de lousado","terminal norte","plataforma logística")):return "named_reference"
    return None
def inbbox(x,y):return bounds[0]<=x<=bounds[2] and bounds[1]<=y<=bounds[3]
def feature(typ,oid,kind,t,g,region,node_ids=None):
    p={"osm_type":typ,"osm_id":int(oid),"region":region,"kind":kind,**t}
    if node_ids is not None:p["node_ids"]=node_ids
    return {"type":"Feature","properties":p,"geometry":mapping(g)}
class Extract(osmium.SimpleHandler):
    def __init__(self,region):super().__init__();self.region=region;self.rows=[];self.skipped=0
    def node(self,n):
        t=fields(n);kind=point_kind(t)
        if kind and n.location.valid() and inbbox(n.location.lon,n.location.lat):
            self.rows.append(feature("node",n.id,kind,t,Point(n.location.lon,n.location.lat),self.region))
    def way(self,w):
        t=fields(w);k=None
        if t.get("highway") in allowed:k="road"
        elif t.get("railway")=="rail":k="rail"
        elif t.get("waterway")=="river" and re.search(r"\b(douro|duero)\b",str(t.get("name","")),re.I):k="river"
        else:k=point_kind(t)
        if not k:return
        try:
            coords=[(n.lon,n.lat) for n in w.nodes];ids=[int(n.ref) for n in w.nodes]
        except Exception:self.skipped+=1;return
        if len(coords)<2:return
        g=LineString(coords)
        if not g.intersects(bb):return
        if k in ("road","rail","river"):
            self.rows.append(feature("way",w.id,k,t,g,self.region,ids))
        else:
            self.rows.append(feature("way",w.id,k,t,g.representative_point(),self.region))
def download(url,dst,cap=700_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":"Norte2040-research/1.0"})
    h=hashlib.sha256();m=hashlib.md5();n=0
    with opener.open(req,timeout=120) as f,dst.open("wb") as out:
        meta={"url":url,"final_url":f.url,"last_modified":f.headers.get("Last-Modified"),"etag":f.headers.get("ETag")}
        while True:
            data=f.read(1024*1024)
            if not data:break
            n+=len(data)
            if n>cap:raise ValueError("download size limit")
            h.update(data);m.update(data);out.write(data)
    if not n:raise ValueError("empty response")
    meta.update(bytes=n,sha256=h.hexdigest(),md5=m.hexdigest())
    return meta
def acquire(region,url,td):
    path=td/(region+".osm.pbf")
    meta=download(url,path)
    try:
        mdurl=url+".md5"
        with opener.open(mdurl,timeout=30) as f: remote=f.read(256).decode().split()[0].lower()
        if re.fullmatch("[a-f0-9]{32}",remote):
            meta["md5_remote"]=remote;meta["md5_match"]=remote==meta["md5"]
            if not meta["md5_match"]:raise ValueError("source MD5 mismatch")
    except ValueError:raise
    except Exception:meta["md5_match"]=None
    try:
        reader=osmium.io.Reader(str(path));header=reader.header();meta["replication_timestamp"]=header.get("osmosis_replication_timestamp");reader.close()
    except Exception:pass
    handler=Extract(region);handler.apply_file(str(path),locations=True,idx="flex_mem")
    counts=collections.Counter(f["properties"]["kind"] for f in handler.rows)
    assert counts["road"]>100 and counts["rail"]>10
    obj={"type":"FeatureCollection","features":handler.rows}
    raw=packed(obj);meta.update(state="PASS",counts=dict(counts),skipped_invalid_way_locations=handler.skipped,derived_sha256=sha(raw),derived_bytes=len(raw),license="ODbL 1.0; © OpenStreetMap contributors; Geofabrik",guard="native tags and actual way geometries; not official RTE-T, physical operating status or HGV verification")
    path.unlink()
    return raw,meta
with tempfile.TemporaryDirectory() as t:
    td=pathlib.Path(t)
    rec={"run_id":os.environ.get("GITHUB_RUN_ID"),"state":"COMPLETE_ATTEMPT","publication_authorized":False,"config_sha256":sha(cfgraw),"sources":{}}
    for region,url in cfg["data_sources"]["geofabrik"].items():
        try:
            raw,meta=acquire(region,url,td);rec["sources"][region]=meta
            # Preserve filtered native objects in separately hashed chunks, so reruns never need new downloads.
            pieces={f"osm-{region}.geojson.gz.part{i//8_000_000+1:03}":raw[i:i+8_000_000] for i in range(0,len(raw),8_000_000)}
            meta["parts"]=[{"name":name,"bytes":len(b),"sha256":sha(b)} for name,b in pieces.items()]
            commit_files({**pieces,"acquisition-receipt.json":dump(rec)},"Acquire bounded OSM geometry and tags for "+region+" (private)")
        except Exception as e:
            rec["sources"][region]={"state":"ERROR","error_type":type(e).__name__,"http_code":getattr(e,"code",None),"url":url}
        print("Geometry",region,rec["sources"][region]["state"],flush=True)
    for name in ("gisco","ign_wfs"):
        url=cfg["data_sources"][name]
        try:
            path=td/name;meta=download(url,path,cap=50_000_000);raw=path.read_bytes()
            if name=="gisco":
                z=json.loads(raw);selected=[f for f in z["features"] if str(f["properties"].get("NUTS_ID","")) in ("ES11","ES41","PT11","PT19")];assert len(selected)==4
                derived=packed({"type":"FeatureCollection","features":selected})
            else:
                import xml.etree.ElementTree as ET
                z=ET.fromstring(raw);assert "Capabilities" in z.tag
                derived=gzip.compress(raw,mtime=0)
                meta["feature_types"]=[e.text for e in z.findall(".//{*}FeatureType/{*}Name") if e.text]
            meta.update(state="PASS",derived_sha256=sha(derived),derived_bytes=len(derived))
            rec["sources"][name]=meta;commit_files({name+".gz":derived,"acquisition-receipt.json":dump(rec)},"Preserve "+name+" source metadata/geometry")
        except Exception as e:rec["sources"][name]={"state":"ERROR","error_type":type(e).__name__,"http_code":getattr(e,"code",None),"url":url}
    rec["state"]="PASS_OSM_BASE" if all(rec["sources"].get(k,{}).get("state")=="PASS" for k in ("PT","GAL","CYL")) else "PARTIAL"
    commit_files({"acquisition-receipt.json":dump(rec)},"Record new NV37–NV40 external geometry acquisition receipt")
