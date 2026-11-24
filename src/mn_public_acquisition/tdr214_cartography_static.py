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

import gzip, collections, math
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



# Direct verified static CartoBase ANE files. No third-party feature-query dependency.
import sqlite3,struct,unicodedata
from shapely import from_wkb
from shapely.geometry import box,mapping
from shapely.ops import transform
from pyproj import Transformer
PUBLIC="r-sousa/mobilidade-public-sources";TAG="mn-iberian-strategic-gis-20261124"
BASE="https://raw.githubusercontent.com/rOpenSpain/mapSpain/sianedata/dist/"
ATTR="Obra derivada de CartoBase ANE 2006-2024 CC-BY 4.0 ign.es; via mapSpain sianedata"
sources=[
("road","se89_3_vias_ctra_l_x.gpkg","d24bb8b8c206d5a04a8d7d02bbc944d22ae219e9",786432),
("rail","se89_3_vias_ffcc_l_x.gpkg","73e35493ae5567457f547a035415715d7df96c3c",348160),
("river","ee89_14_hidro_riol_l.gpkg","8c3256f6506d4aae4a85544459e68b9b27da9cb9",413696),
("urban","se89_3_urban_capimuni_p_x.gpkg","83179f05e1ccde349813eea2a298c68445713934",1552384)]
rec=json.loads(file(OUT+"acquisition-receipt.json",REF))
rec["previous_official_sources"]=rec.get("official_sources",{});rec["previous_acquisition_run_id"]=rec["run_id"];rec["run_id"]=os.environ["GITHUB_RUN_ID"];rec["state"]="STATIC_IN_PROGRESS";rec["official_sources"]={}
def norm(x):return "".join(c for c in unicodedata.normalize("NFKD",str(x).casefold()) if not unicodedata.combining(c))
def release(raw,name,td):
    p=td/name;p.write_bytes(raw)
    subprocess.run(["gh","release","upload",TAG,str(p),"--repo",PUBLIC,"--clobber"],check=True,stdout=subprocess.DEVNULL)
def geometry(raw):
    if raw is None:return None
    assert raw[:2]==b"GP"
    n={0:0,1:32,2:48,3:48,4:64}[(raw[3]>>1)&7]
    return from_wkb(raw[8+n:])
def read_gpkg(path):
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    t,col,epsg=db.execute("SELECT table_name,column_name,srs_id FROM gpkg_geometry_columns").fetchone()
    assert '"' not in t and '"' not in col
    trans=Transformer.from_crs(epsg,4326,always_xy=True)
    # preserve native code tables if present; never guess meaning of coded values
    tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    dicts={}
    for table in tables:
        if table.startswith(("gpkg_","rtree_","sqlite_")) or table==t or '"' in table:continue
        if any(v in norm(table) for v in ("tipo","estado","orden","ancho","numero","acceso")):
            rows=[dict(r) for r in db.execute('SELECT * FROM "'+table+'" LIMIT 1000')]
            dicts[table]=rows
    fs=[]
    for row in db.execute('SELECT * FROM "'+t+'"'):
        p=dict(row);g=geometry(p.pop(col))
        if g is None or g.is_empty:continue
        g=transform(trans.transform,g)
        p={k:v for k,v in p.items() if isinstance(v,(str,int,float,type(None)))}
        fs.append((p,g))
    db.close();return fs,dicts
def decoded(p,dicts,table,key):
    val=p.get(key)
    if val is None:return ""
    for t,rows in dicts.items():
        if table not in norm(t):continue
        for row in rows:
            matches=[k for k,v in row.items() if str(v)==str(val) and any(x in norm(k) for x in ("cod","id","valor"))]
            if matches:
                ds=[str(v) for k,v in row.items() if isinstance(v,str) and any(x in norm(k) for x in ("desc","denom","nombre"))]
                if ds:return ds[0]
    return str(val) if isinstance(val,str) and not val.isdigit() else ""
tiles=[("gal-west","GAL",box(-9.35,41.78,-7.85,43.15)),("gal-east","GAL",box(-7.85,41.78,-6.85,43.15)),("cyl-north","CYL",box(-6.85,41.35,-5.35,43.15)),("cyl-south","CYL",box(-7.10,40.10,-5.35,41.35))]
def save(name,fs,kind,region,source,td):
    if not fs:return
    raw=packed({"type":"FeatureCollection","features":fs});asset=name+".geojson.gz"
    m={"state":"PASS","asset":asset,"bytes":len(raw),"sha256":sha(raw),"count":len(fs),"kind":kind,"region":region,"attribution":ATTR,"source":source}
    rec["official_sources"][name]=m
    release(raw,asset,td);commit_files({asset:raw,"acquisition-receipt.json":dump(rec)},"Retain CartoBase ANE "+name)
with tempfile.TemporaryDirectory() as t:
    td=pathlib.Path(t)
    for kind,name,pin,size in sources:
        try:
            with opener.open(BASE+name,timeout=35) as f:raw=f.read(size+1)
            assert len(raw)==size and hashlib.sha1(b"blob "+str(size).encode()+b"\0"+raw).hexdigest()==pin
            p=td/name;p.write_bytes(raw);data,dicts=read_gpkg(p);release(raw,name,td)
            meta={"name":name,"url":BASE+name,"git_blob":pin,"sha256":sha(raw),"bytes":size,"attribution":ATTR,"native_fields":list(data[0][0]),"dictionaries":dicts}
            rec.setdefault("static_metadata",{})[kind]=meta
            print(kind,"verified",len(data),flush=True)
            if kind in ("road","rail"):
                for tile,region,b in tiles:
                    fs=[]
                    for i,(p,g) in enumerate(data):
                        if not g.intersects(b):continue
                        g=g.intersection(b)
                        if g.is_empty or g.geom_type not in ("LineString","MultiLineString"):continue
                        status=decoded(p,dicts,"estadofisico","estado_fis")
                        typ=decoded(p,dicts,"tipocarretera","t_ctra") if kind=="road" else decoded(p,dicts,"tipoffcc","t_ffcc")
                        ref=str(p.get("rotulo") or p.get("nombre") or "")
                        # reference-based classification only if native descriptions not decoded
                        if kind=="road" and not typ:typ="Autovía/autopista (referencia)" if re.match(r"^AP?-\d",ref,re.I) else "Rede principal (CartoBase)"
                        attrs={**p,"OBJECTID":i,"source_kind":kind,"source_region":region,"source":"CartoBase ANE","estadofisd":status,"tipo_viald":typ,"tipo_lined":typ,"electrifid":"","native_status_unverified":not bool(status)}
                        fs.append({"type":"Feature","properties":attrs,"geometry":mapping(g)})
                    save("ign-"+kind+"-"+tile,fs,kind,region,name,td)
            elif kind=="river":
                fs=[]
                for i,(p,g) in enumerate(data):
                    if not any(re.search(r"\b(douro|duero)\b",norm(v)) for v in p.values() if isinstance(v,str)):continue
                    g=g.intersection(box(-8.80,40.93,-6.15,41.29))
                    if not g.is_empty and g.geom_type in ("LineString","MultiLineString"):fs.append({"type":"Feature","properties":p,"geometry":mapping(g)})
                save("apa-douro",fs,"river","PT",name,td)
            elif kind=="urban":
                fs=[]
                for p,g in data:
                    if g.geom_type!="Point" or not box(-9.35,40.1,-5.35,43.15).covers(g):continue
                    for name0 in ("Vigo","Ourense","Verín","Zamora","Salamanca","Barcelos"):
                        if any(norm(v)==norm(name0) for v in p.values() if isinstance(v,str)):
                            fs.append({"type":"Feature","properties":{**p,"name":name0,"kind":"urban"},"geometry":mapping(g)});break
                save("siane-urban",fs,"urban","ES",name,td)
            commit_files({"acquisition-receipt.json":dump(rec)},"Record verified CartoBase metadata "+kind)
        except Exception as e:
            rec.setdefault("static_errors",{})[kind]={"type":type(e).__name__,"detail":str(e)[:180]};print(kind,type(e).__name__,str(e)[:180],flush=True)
    rec["state"]="STATIC_PARTIAL" if rec.get("static_errors") or len(rec["official_sources"])<10 else "STATIC_PASS"
    pub={"attribution":ATTR,"sources":rec.get("static_metadata",{}),"extractions":rec["official_sources"],"errors":rec.get("static_errors",{})}
    if rec.get("static_metadata"):release(dump(pub),"cartobase-ane-source-receipt.json",td)
    commit_files({"acquisition-receipt.json":dump(rec)},"Record direct static CartoBase acquisition outcome")
