"""New NV37–NV40 render: pinned private inputs, isolated renderer and private sink."""
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

pins={"renderer":"fcafec186c2a5050ef181cf151270273f928436e","config":"0fdc527a637c4021e07c5a3ec9c97e1b61fd63ff","phase5":"964cbf553cd5eac3b05d83cc07a4725d9950c8be","phase24":"68e5ef1f843d39972b818919c7570526fad5c884","hubs":"7397728fe6045f9e2568b30d36e5575f9cf309a5","facilities":"9ffcc08a8cdfd845918752ea5a27e622f80614e2","legal":"dc0d5dd75580c37367f33a76d5ba569df81a5abd"}
SRC=ROOT+"cartography/rebuild/"
OUT=SRC+"render/"
with tempfile.TemporaryDirectory() as tmp:
    td=pathlib.Path(tmp);source_hashes={}
    def save(name,raw):
        (td/name).write_bytes(raw);source_hashes[name]=sha(raw)
    save("render.py",file(ROOT+"cartography/build-NV37-NV40.py",REF,pins["renderer"]))
    save("config.json",file(ROOT+"cartography/rebuild-inputs.json",REF,pins["config"]))
    p5=json.loads(file(DATA+"phase5/receipt.json",SRCREF,pins["phase5"]))
    p24=json.loads(file(DATA+"phase24/receipt.json",SRCREF,pins["phase24"]))
    def parts(meta,name,ref=SRCREF,prefix=""):
        def get(p):
            raw=file(prefix+p.get("path",p.get("name")),ref);assert len(raw)==p["bytes"] and sha(raw)==p["sha256"];return raw
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            with (td/name).open("wb") as dst:
                for raw in pool.map(get,meta["parts"]):dst.write(raw)
        with (td/name).open("rb") as f: digest=hashlib.file_digest(f,"sha256").hexdigest()
        expected=meta.get("sha256",meta.get("derived_sha256"))
        if expected:assert digest==expected
        source_hashes[name]=digest
    for source,stage,name in [("CAOP2025","download","caop.geojson"),("road","territorial_clip","road.geojson"),("rail","territorial_clip","rail.geojson")]:
        item=next(x for x in p5["requests"] if x["source_id"]==source and x["stage"]==stage);parts(item,name)
    graph=next(x for x in p24["requests"] if x["stage"]=="road_access_model")["graph"];parts(graph,"graph.npz")
    for path,ref,pin,name in [(DATA+"phase24/F18-city-hubs.csv",SRCREF,pins["hubs"],"hubs.csv"),(ROOT+"generated/NV04-facility-access-qa.json",REF,pins["facilities"],"facilities.json"),(DATA+"phase25/TEN-T-2024-Annex-II-PT-node-register.csv",SRCREF,pins["legal"],"legal.csv")]:save(name,file(path,ref,pin))
    # Acquisition receipt is required; only checked source parts are accepted, partial result clearly marked.
    recraw=file(SRC+"acquisition-receipt.json",REF);rec=json.loads(recraw);save("acquisition-receipt.json",recraw)
    for r in ("PT","GAL","CYL"):
        m=rec["sources"].get(r,{})
        if m.get("state")=="PASS":parts(m,"osm-"+r+".geojson.gz",REF,SRC)
    m=rec["sources"].get("gisco",{})
    if m.get("state")=="PASS":
        raw=file(SRC+"gisco.gz",REF);assert sha(raw)==m["derived_sha256"];save("gisco.geojson.gz",raw)
    for name,m in rec.get("official_sources",{}).items():
        if m.get("state")!="PASS":continue
        assert re.fullmatch(r"(?:ign-(?:road|rail)-(?:gal-west|gal-east|cyl-north|cyl-south)|apa-douro|siane-urban)",name)
        raw=file(SRC+m["asset"],REF);assert len(raw)==m["bytes"] and sha(raw)==m["sha256"];save(m["asset"],raw)
    # Small native CartoBase code lists, pinned to upstream Git blobs.
    import struct
    dictpins={"EstadoFisico":"db27fefe5fdf8daf90a7de83879249f8319b9443","TipoCarretera":"cb6a484b694e5c73ffc7e7bffe7cccf1abdaead1","TipoFFCC":"b16cbe39c7f17cc9d25ac0aae1fd3e3d07fa601c","BooleanSymbolValue":"dba2807ad585da7c4025afab3e8f3b034858aae8","AnchoVia":"fda04ec4c02ac0a95dffd6cb12448ef021eabcdf","NumeroVias":"d7050186d077830b6e57c30fe297afa434031ae0","Orden":"e43c0ebd80b92dd6ffc090a25eef8478ce85e8f7"}
    dd={};diag={}
    for name,pin in dictpins.items():
        try:
            fname="lve_"+name+".dbf";url="https://raw.githubusercontent.com/rOpenSpain/mapSpain/main/data-raw/listas_de_valores_enumerados/"+fname
            with opener.open(url,timeout=15) as f:raw=f.read(100001)
            assert len(raw)<100001 and hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==pin
            n,h,rl=struct.unpack_from("<IHH",raw,4);fields=[]
            for i in range(32,h-1,32):
                if raw[i]==13:break
                fields.append((raw[i:i+11].split(b"\0")[0].decode("ascii").lower(),raw[i+16]))
            rows=[]
            for j in range(n):
                off=h+j*rl
                if raw[off:off+1]==b"*":continue
                off+=1;row={}
                for key,l in fields:
                    row[key]=raw[off:off+l].decode("utf-8",errors="replace").strip();off+=l
                rows.append(row)
            assert rows and all("descrip" in row for row in rows)
            key=next(k for k in rows[0] if k!="descrip" and k in ("valor","codigo","cod","id","value"))
            dd[name]={row[key]:row["descrip"] for row in rows};diag[name]={"pin":pin,"sha256":sha(raw),"fields":fields,"url":url}
            save(fname,raw)
            if os.environ.get("GH_TOKEN"):
                subprocess.run(["gh","release","upload","mn-iberian-strategic-gis-20261124",str(td/fname),"--repo","r-sousa/mobilidade-public-sources","--clobber"],check=True,stdout=subprocess.DEVNULL)
        except Exception as e:diag[name]={"error":type(e).__name__,"detail":str(e)[:120]}
    save("cartobase-dictionaries.json",json.dumps({"tables":dd,"metadata":diag},ensure_ascii=False).encode())
    out=td/"render"
    env={k:v for k,v in os.environ.items() if k in ("PATH","HOME","LANG","LC_ALL","SYSTEMROOT")};env["MPLCONFIGDIR"]=str(td/"mpl")
    proc=subprocess.run([sys.executable,str(td/"render.py"),str(td),str(out)],env=env,capture_output=True,timeout=900)
    if proc.returncode:
        err=proc.stderr.decode("utf-8",errors="replace")
        loc=re.findall(r'render\.py", line (\d+)',err);kind=re.findall(r"^([A-Za-z][A-Za-z0-9_.]*(?:Error|Exception))(?::|$)",err,re.M)
        print("Renderer diagnostic:",loc[-1] if loc else "unknown",kind[-1] if kind else "unknown",flush=True);raise SystemExit(1)
    files=sorted(out.iterdir());qa=json.loads((out/"QA.json").read_text())
    receipt={"run_id":os.environ.get("GITHUB_RUN_ID"),"state":"RENDERED_WITH_GAPS" if qa["gaps"] else "PASS","publication_authorized":False,"input_blob_pins":pins,"source_sha256":source_hashes,"acquisition_run_id":rec.get("run_id"),"outputs":[{"path":"cartography/rebuild/render/"+p.name,"sha256":sha(p.read_bytes()),"bytes":p.stat().st_size} for p in files]}
    (out/"render-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    entries=[]
    for p in out.iterdir():
        raw=p.read_bytes();assert len(raw)<50_000_000
        z=gh("git/blobs",{"content":base64.b64encode(raw).decode(),"encoding":"base64"},"POST",True)
        entries.append({"path":OUT+p.name,"mode":"100644","type":"blob","sha":z["sha"]})
    for i in range(3):
        head=gh("git/ref/heads/"+REF)["object"]["sha"];tree=gh("git/commits/"+head)["tree"]["sha"]
        nt=gh("git/trees",{"base_tree":tree,"tree":entries},"POST",True)["sha"]
        c=gh("git/commits",{"message":"Render fresh NV37–NV40 using acquired Iberian geometry and verified F18 network","tree":nt,"parents":[head]},"POST",True)["sha"]
        try:gh("git/refs/heads/"+REF,{"sha":c,"force":False},"PATCH",True);break
        except Exception:
            if i==2:raise
            time.sleep(2)
    print("Private new GIS outputs committed:",len(entries),"objects; state",receipt["state"])
