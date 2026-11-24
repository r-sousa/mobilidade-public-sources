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

# Only bounded missing public features. No new regional PBF, no re-acquisition of PT national roads or RFN.
PUBLIC="r-sousa/mobilidade-public-sources"
TAG="mn-iberian-strategic-gis-20261124"
ENDPOINTS=["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]
run=os.environ.get("GITHUB_RUN_ID","local")
rec={"run_id":run,"state":"SELECTIVE_IN_PROGRESS","sources":{},"public_release":"https://github.com/"+PUBLIC+"/releases/tag/"+TAG,"publication_authorized":False,"guard":"Public source assets only; private inputs, derived maps and model never published."}
def release(raw,name,td):
    path=td/name;path.write_bytes(raw)
    args=["gh","release","view",TAG,"--repo",PUBLIC]
    if subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        subprocess.run(["gh","release","create",TAG,"--repo",PUBLIC,"--target",os.environ["GITHUB_SHA"],"--title","Mobilidade Norte — bounded Iberian strategic GIS","--notes","OpenStreetMap data © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright). Bounded source extracts only; no private inputs. See acquisition receipts for exact queries, dates and checksums."],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(["gh","release","upload",TAG,str(path),"--repo",PUBLIC,"--clobber"],check=True,stdout=subprocess.DEVNULL)
def valid_response(raw):
    j=json.loads(raw)
    if j.get("remark") or not isinstance(j.get("elements"),list):raise ValueError("Incomplete Overpass response")
    return j
def query(selectors,b):
    bbox=",".join(map(str,b))
    return "[out:json][timeout:30][maxsize:67108864];("+''.join(s+"("+bbox+");" for s in selectors)+");out geom;"
def fetch(q):
    for url in ENDPOINTS:
        try:
            req=urllib.request.Request(url,data=urllib.parse.urlencode({"data":q}).encode(),headers={"User-Agent":"MobilidadeNorte-strategic-GIS/1.0","Accept":"application/json"})
            with opener.open(req,timeout=45) as f:raw=f.read(16_000_001)
            if len(raw)>16_000_000:raise ValueError("Bound exceeded")
            obj=valid_response(raw)
            return raw,obj,url
        except Exception as e:last=type(e).__name__
    raise RuntimeError(last)
roads=['way["highway"~"^(motorway|trunk|primary)$"]']
rails=['way["railway"="rail"]["service"!~"^(yard|siding|spur)$"]']
# 4 bounded strategic Spain tiles: southern Galicia and western Castilla y León toward Zamora/Salamanca.
# PT queries are only technical rail tags, selected named facilities/urban nodes, river and narrow crossing windows.
tasks=[
("gal-west","GAL",roads+rails,(41.78,-8.95,42.85,-7.85)),
("gal-east","GAL",roads+rails,(41.78,-7.85,42.85,-6.85)),
("cyl-northwest","CYL",roads+rails,(41.35,-6.85,42.85,-5.60)),
("cyl-southwest","CYL",roads+rails,(40.45,-7.05,41.35,-5.60)),
("pt-rail-tags","PT",['way["railway"="rail"]["electrified"]'],(40.3,-8.95,42.18,-6.18)),
("pt-douro","PT",['way["waterway"="river"]["name"~"Douro|Duero",i]'],(40.93,-8.80,41.29,-6.15)),
("pt-facilities-west","PT",['nwr["aeroway"="aerodrome"]','nwr["aeroway"="terminal"]["name"~"carga|cargo",i]','nwr["name"~"porto de leixões|porto de leixoes|portaria principal|portaria única|terminal.*lousado|terminal.*valongo|terminal norte|terminal.*gaia|terminal.*devesas|plataforma logística",i]','node["place"~"^(city|town)$"]["name"~"^Barcelos$"]'],(40.97,-8.85,41.75,-8.25)),
("pt-facilities-east","PT",['nwr["aeroway"="aerodrome"]'],(41.10,-7.90,41.90,-6.45)),
("border-valenca","PT",roads,(41.99,-8.72,42.08,-8.58)),
("border-verin","PT",roads,(41.76,-7.48,41.86,-7.36)),
("border-quintanilha","PT",roads,(41.70,-6.64,41.82,-6.48)),
("es-cities","GAL",['node["place"~"^(city|town)$"]["name"~"^(Vigo|Ourense|Verín|Zamora|Salamanca)$"]'],(40.45,-9.0,42.85,-5.55)),
]
keys={"name","name:pt","name:es","ref","int_ref","highway","railway","electrified","voltage","frequency","gauge","usage","service","tracks","maxspeed","lanes","oneway","access","hgv","maxheight","maxweight","maxwidth","maxlength","maxaxleload","junction","waterway","aeroway","harbour","industrial","landuse","barrier","iata","icao","operator","construction","proposed","disused","freight","cargo","place","population"}
def feature(el,region):
    t={k:v for k,v in el.get("tags",{}).items() if k in keys}
    k=("road" if t.get("highway") in ("motorway","trunk","primary") else "rail" if t.get("railway")=="rail" else "river" if t.get("waterway")=="river" else "airport" if t.get("aeroway") in ("aerodrome","terminal") else "urban" if t.get("place") in ("city","town") else "named_reference")
    xy=[[g["lon"],g["lat"]] for g in el.get("geometry",[]) if "lon" in g and "lat" in g]
    if k in ("road","rail","river"):
        if el["type"]!="way" or len(xy)<2 or len(xy)!=len(el.get("nodes",[])):return None
        geom={"type":"LineString","coordinates":xy}
    else:
        if "lon" in el:point=[el["lon"],el["lat"]]
        elif xy:point=[sum(a[0] for a in xy)/len(xy),sum(a[1] for a in xy)/len(xy)]
        else:return None
        geom={"type":"Point","coordinates":point}
    p={"osm_type":el["type"],"osm_id":el["id"],"region":region,"kind":k,**t}
    if k in ("road","rail","river"):p["node_ids"]=el["nodes"]
    return {"type":"Feature","properties":p,"geometry":geom}
def read_old():
    try:return json.loads(file(OUT+"acquisition-receipt.json",REF))
    except Exception:return {}
def public_old(old,td):
    for region in ("PT","GAL","CYL"):
        m=old.get("sources",{}).get(region,{})
        # Strict source allowlist: verified public Geofabrik extracts only, no private inputs.
        if m.get("state")!="PASS" or not str(m.get("url","")).startswith("https://download.geofabrik.de/europe/"):continue
        try:
            chunks=[file(OUT+p["name"],REF) for p in m["parts"]]
            assert all(sha(b)==p["sha256"] and len(b)==p["bytes"] for b,p in zip(chunks,m["parts"]))
            raw=b"".join(chunks);assert sha(raw)==m["derived_sha256"]
            release(raw,"previous-geofabrik-"+region+".geojson.gz",td)
            print("Preserved earlier public source",region,flush=True)
        except Exception as e:print("Earlier source preservation issue",region,type(e).__name__,flush=True)
with tempfile.TemporaryDirectory() as tmp:
    td=pathlib.Path(tmp)
    public_old(read_old(),td)
    commit_files({"acquisition-receipt.json":dump(rec)},"Record selective GIS acquisition start")
    rows={r:{} for r in ("PT","GAL","CYL")}
    byregion=collections.defaultdict(list)
    for name,region,selectors,bbox in tasks:
        q=query(selectors,bbox)
        try:
            raw,j,url=fetch(q)
            f=[v for e in j["elements"] if (v:=feature(e,region)) is not None]
            if not f:raise ValueError("No matching source features")
            gz=gzip.compress(raw,mtime=0);asset=name+".overpass.json.gz"
            # Publish immediately; preserve provenance without public private-data leakage.
            release(gz,asset,td)
            m={"state":"PASS","url":url,"query":q,"bbox":bbox,"asset":asset,"source_sha256":sha(raw),"asset_sha256":sha(gz),"count":len(f),"timestamp_osm_base":j.get("osm3s",{}).get("timestamp_osm_base"),"license":"ODbL 1.0; © OpenStreetMap contributors"}
            for v in f:
                p=v["properties"];rows[region][(p["osm_type"],p["osm_id"])]=v
        except Exception as e:m={"state":"ERROR","query":q,"bbox":bbox,"error_type":type(e).__name__}
        byregion[region].append(m);rec["sources"][name]=m
        # Make partial results inspectable without waiting for the entire run.
        print(name,m["state"],flush=True)
        rr=rows[region]
        if rr:
            raw=packed({"type":"FeatureCollection","features":list(rr.values())})
            part=f"osm-{region}.geojson.gz.part001"
            meta={"state":"PASS","coverage":"PARTIAL_BOUNDED_QUERIES","tasks":byregion[region],"derived_sha256":sha(raw),"parts":[{"name":part,"sha256":sha(raw),"bytes":len(raw)}],"count":len(rr)}
            rec["sources"][region]=meta
            commit_files({part:raw,"acquisition-receipt.json":dump(rec)},"Preserve selective strategic geometry "+name)
        else:commit_files({"acquisition-receipt.json":dump(rec)},"Record unavailable query "+name)
        time.sleep(1)
    # Context boundaries, only if not already available; low-resolution regional GISCO.
    try:
        url="https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326.geojson"
        with opener.open(url,timeout=35) as f:raw=f.read(12_000_001)
        assert len(raw)<=12_000_000
        j=json.loads(raw);selected=[f for f in j["features"] if f["properties"].get("NUTS_ID") in ("ES11","ES41","PT11","PT19")];assert len(selected)==4
        derived=packed({"type":"FeatureCollection","features":selected})
        rec["sources"]["gisco"]={"state":"PASS","url":url,"derived_sha256":sha(derived)}
        commit_files({"gisco.gz":derived,"acquisition-receipt.json":dump(rec)},"Preserve bounded GISCO context")
    except Exception as e:rec["sources"]["gisco"]={"state":"ERROR","error_type":type(e).__name__}
    rec["state"]="SELECTIVE_PASS" if all(rec["sources"].get(n,{}).get("state")=="PASS" for n,*_ in tasks) else "SELECTIVE_PARTIAL"
    # Public receipt limited to the public-source metadata; no internal paths, model, or private credentials.
    publicmeta={k:v for k,v in rec["sources"].items() if k in {n for n,*_ in tasks}}
    if any(v.get("state")=="PASS" for v in publicmeta.values()):release(dump({"sources":publicmeta,"state":rec["state"]}),"source-receipt.json",td)
    commit_files({"acquisition-receipt.json":dump(rec)},"Record final selective acquisition receipt")
