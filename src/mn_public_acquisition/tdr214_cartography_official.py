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


# Official Spanish networks: bounded ArcGIS queries, native fields, no OSM relabelling.
PUBLIC="r-sousa/mobilidade-public-sources"
TAG="mn-iberian-strategic-gis-20261124"
ROAD="https://services1.arcgis.com/nCKYwcSONQTkPA4K/ArcGIS/rest/services/Red_de_carreteras_en_Espa%C3%B1a/FeatureServer/0"
RAIL="https://services1.arcgis.com/nCKYwcSONQTkPA4K/ArcGIS/rest/services/RedFerrocarrilesIGN/FeatureServer/2"
HYDRO="https://sniambgeoogc.apambiente.pt/getogc/rest/services/SNIAmb/RdHidrografica_GeoCodificada/MapServer/0"
ATTR="Instituto Geográfico Nacional de España, IGR-RT; https://www.ign.es/web/politica-datos (CC BY 4.0 compatible)"
roadfields="OBJECTID,id_tramo,codigo,dgc_via,clased,tipo_viald,tipo_tramd,orden,ordend,estadofisd,ncarriles,calzadad,titulard,nombre,fuente_td"
railfields="OBJECTID,id_tramo,codigo,nombre,tipo_lined,tipo_tramd,ancho_viad,electrifid,estadofisd,n_viasD,n_via,red_tentd,uso_ppald,fuente_ld"
where_road="(orden = 'P' OR ordend LIKE 'Principal%' OR tipo_viald LIKE '%Autopista%' OR tipo_viald LIKE '%Autovía%' OR dgc_via LIKE 'A-%' OR dgc_via LIKE 'AP-%' OR dgc_via LIKE 'N-%' OR codigo LIKE 'A-%' OR codigo LIKE 'AP-%' OR codigo LIKE 'N-%')"
tiles=[("gal-west","GAL",[-9.30,41.78,-7.85,43.05]),("gal-east","GAL",[-7.85,41.78,-6.85,43.05]),("cyl-north","CYL",[-6.85,41.35,-5.50,43.05]),("cyl-south","CYL",[-7.10,40.15,-5.50,41.35])]
run=os.environ.get("GITHUB_RUN_ID","local")
rec=json.loads(file(OUT+"acquisition-receipt.json",REF))
rec["previous_acquisition_run_id"]=rec["run_id"]
rec["run_id"]=run;rec["state"]="OFFICIAL_IN_PROGRESS";rec["official_sources"]={}
def query(url,params,cap=18_000_000,timeout=35):
    u=url+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(u,headers={"User-Agent":"MobilidadeNorte-IGR/1.0","Accept":"application/json"})
    with opener.open(req,timeout=timeout) as f:raw=f.read(cap+1)
    if len(raw)>cap:raise ValueError("response cap")
    obj=json.loads(raw)
    if "error" in obj:raise RuntimeError("ArcGIS "+str(obj["error"].get("code"))+" "+str(obj["error"].get("message"))[:150])
    return obj
def acquire(layer,where,bbox,fields,cap=18000):
    env={"where":where,"geometry":",".join(map(str,bbox)),"geometryType":"esriGeometryEnvelope","inSR":4326,"spatialRel":"esriSpatialRelIntersects"}
    ids=query(layer+"/query",{**env,"returnIdsOnly":"true","f":"json"}).get("objectIds")
    if not ids:raise ValueError("no object IDs")
    ids=sorted(set(ids))
    if len(ids)>cap:raise ValueError("ID cap exceeded: "+str(len(ids)))
    fs=[]
    for k in range(0,len(ids),600):
        wanted=ids[k:k+600]
        j=query(layer+"/query",{"objectIds":",".join(map(str,wanted)),"outFields":fields,"returnGeometry":"true","outSR":4326,"returnZ":"false","returnM":"false","geometryPrecision":5,"maxAllowableOffset":0.0003,"f":"geojson"})
        if j.get("exceededTransferLimit"):raise ValueError("truncated")
        batch=j.get("features",[])
        actual={int(f["properties"].get("OBJECTID",f["properties"].get("objectid",f.get("id")))) for f in batch}
        if actual!=set(wanted):raise ValueError("object ID mismatch")
        fs.extend(batch)
    if not fs or any(not f.get("geometry") or f["geometry"]["type"] not in ("LineString","MultiLineString") for f in fs):raise ValueError("invalid line geometry")
    return fs,{"where":where,"bbox":bbox,"requested_ids":len(ids),"returned":len(fs),"geometry_precision":5,"maxAllowableOffset_deg":0.0003}
def release(raw,name,td):
    p=td/name;p.write_bytes(raw)
    # Existing release contains ODbL OSM data; each IGN file has a separate attribution manifest.
    subprocess.run(["gh","release","upload",TAG,str(p),"--repo",PUBLIC,"--clobber"],check=True,stdout=subprocess.DEVNULL)
def store(name,features,m,td,public=True):
    raw=packed({"type":"FeatureCollection","features":features})
    m.update(state="PASS",count=len(features),sha256=sha(raw),bytes=len(raw),asset=name+".geojson.gz")
    if public:release(raw,m["asset"],td)
    rec["official_sources"][name]=m
    commit_files({m["asset"]:raw,"acquisition-receipt.json":dump(rec)},"Retain verified official source "+name)
def attempt(name,layer,where,bbox,fields,td,kind,region):
    try:
        fs,m=acquire(layer,where,bbox,fields)
        m.update(url=layer,kind=kind,region=region,attribution=ATTR)
        # Preserve native attributes; renderer assigns only grounded classes.
        for f in fs:f["properties"].update(source="IGN IGR-RT",source_region=region,source_kind=kind)
        m["native_values"]={key:dict(collections.Counter(str(f["properties"].get(key)) for f in fs)) for key in (("ordend","tipo_viald","estadofisd") if kind=="road" else ("estadofisd","electrifid","ancho_viad","tipo_lined"))}
        store(name,fs,m,td)
        print(name,"PASS",len(fs),flush=True)
    except Exception as e:
        rec["official_sources"][name]={"state":"ERROR","url":layer,"bbox":bbox,"error_type":type(e).__name__,"detail":str(e)[:180]}
        print(name,"ERROR",type(e).__name__,str(e)[:180],flush=True)
        commit_files({"acquisition-receipt.json":dump(rec)},"Record official source diagnostic "+name)
with tempfile.TemporaryDirectory() as t:
    td=pathlib.Path(t)
    # Rail is small and a priority; acquire first and independently of roads.
    for name,region,bbox in tiles:
        attempt("ign-rail-"+name,RAIL,"1=1",bbox,railfields,td,"rail",region)
    for name,region,bbox in tiles:
        attempt("ign-road-"+name,ROAD,where_road,bbox,roadfields,td,"road",region)
    # APA: discover real field names before issuing a named river query; no invented hydro line.
    try:
        meta=query(HYDRO,{"f":"json"})
        fields={f["name"].lower():f["name"] for f in meta.get("fields",[])}
        namefield=next((fields[x] for x in ("name","nome","geographicalname","designacao") if x in fields),None)
        if not namefield:raise ValueError("No name field in APA layer; cannot isolate Douro safely")
        oid=meta.get("objectIdField") or fields.get("objectid","objectid")
        fs,m=acquire(HYDRO,f"UPPER({namefield}) LIKE '%DOURO%'",[-8.80,40.93,-6.15,41.29],oid+","+namefield)
        m.update(url=HYDRO,kind="river",region="PT",attribution="Agência Portuguesa do Ambiente; Rede hidrográfica geocodificada; public redistribution license not independently confirmed")
        store("apa-douro",fs,m,td,public=False)
    except Exception as e:
        rec["official_sources"]["apa-douro"]={"state":"ERROR","url":HYDRO,"error_type":type(e).__name__,"detail":str(e)[:180]}
        print("apa-douro",type(e).__name__,str(e)[:180],flush=True)
    rec["state"]="OFFICIAL_PASS" if all(v["state"]=="PASS" for v in rec["official_sources"].values()) else "OFFICIAL_PARTIAL"
    pub={"source":"IGN IGR-RT","attribution":ATTR,"run_id":run,"sources":{k:v for k,v in rec["official_sources"].items() if k.startswith("ign-")}}
    if any(v["state"]=="PASS" for v in pub["sources"].values()):release(dump(pub),"ign-source-receipt.json",td)
    commit_files({"acquisition-receipt.json":dump(rec)},"Record official-source acquisition result; retain previous OSM and GISCO")
