"""Pinned private-only bridge for NV37–NV40 r2. No private rows in public logs."""
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
pins={"renderer":"75460b12a8b606debf27311820b104f5c5763f17","phase5":"964cbf553cd5eac3b05d83cc07a4725d9950c8be","phase24":"68e5ef1f843d39972b818919c7570526fad5c884","hubs":"7397728fe6045f9e2568b30d36e5575f9cf309a5","grid":"81ff487de1e18c4a2000f88f017277816ec331e9","facilities":"9ffcc08a8cdfd845918752ea5a27e622f80614e2"}
with tempfile.TemporaryDirectory() as tmp:
    td=pathlib.Path(tmp)
    (td/"render.py").write_bytes(file(ROOT+"build-nv37-nv40-r2.py",REF,pins["renderer"]))
    p5=json.loads(file(DATA+"phase5/receipt.json",SRCREF,pins["phase5"]))
    p24=json.loads(file(DATA+"phase24/receipt.json",SRCREF,pins["phase24"]))
    assert p24["blobs"]["F18-reachability-2km-cells.csv.gz"]==pins["grid"]
    source_hashes={}
    def parts(source,stage,name):
        item=next(x for x in p5["requests"] if x["source_id"]==source and x["stage"]==stage)
        def get(part):
            raw=file(part["path"],SRCREF);assert len(raw)==part["bytes"] and sha(raw)==part["sha256"];return raw
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            with (td/name).open("wb") as dst:
                for raw in pool.map(get,item["parts"]):dst.write(raw)
        with (td/name).open("rb") as f: digest=hashlib.file_digest(f,"sha256").hexdigest()
        if item.get("sha256"):assert digest==item["sha256"]
        source_hashes[name]=digest
    for a in [("CAOP2025","download","caop.geojson"),("road","territorial_clip","road.geojson"),("rail","territorial_clip","rail.geojson")]:parts(*a)
    for path,ref,pin,name in [(DATA+"phase24/F18-city-hubs.csv",SRCREF,pins["hubs"],"hubs.csv"),(DATA+"phase24/F18-reachability-2km-cells.csv.gz",SRCREF,pins["grid"],"grid.csv.gz"),(ROOT+"generated/NV04-facility-access-qa.json",REF,pins["facilities"],"facilities.json")]:
        raw=file(path,ref,pin);(td/name).write_bytes(raw);source_hashes[name]=sha(raw)
    out=td/"out"
    env={k:v for k,v in os.environ.items() if k in ("PATH","HOME","LANG","LC_ALL","SYSTEMROOT")};env["MPLCONFIGDIR"]=str(td/"mpl")
    proc=subprocess.run([sys.executable,str(td/"render.py"),str(td),str(out)],env=env,capture_output=True,timeout=420)
    if proc.returncode:
        err=proc.stderr.decode("utf-8",errors="replace")
        lines=re.findall(r'render\.py", line (\d+)',err);kinds=re.findall(r"^([A-Za-z][A-Za-z0-9_.]*(?:Error|Exception))(?::|$)",err,re.M)
        print("Renderer diagnostic: line",lines[-1] if lines else "unknown","exception",kinds[-1] if kinds else "unknown",flush=True)
        raise SystemExit(1)
    files=sorted(out.iterdir());assert len(files)==9
    receipt={"run_id":os.environ.get("GITHUB_RUN_ID"),"state":"PASS","publication_authorized":False,"input_blob_pins":pins,"source_sha256":source_hashes,"outputs":[{"path":"generated/"+p.name,"sha256":sha(p.read_bytes()),"bytes":p.stat().st_size} for p in files]}
    (out/"nv37-nv40-r2-render-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    entries=[]
    for p in out.iterdir():
        z=gh("git/blobs",{"content":base64.b64encode(p.read_bytes()).decode(),"encoding":"base64"},"POST",True)
        entries.append({"path":ROOT+"generated/"+p.name,"mode":"100644","type":"blob","sha":z["sha"]})
    for i in range(3):
        head=gh("git/ref/heads/"+REF)["object"]["sha"];tree=gh("git/commits/"+head)["tree"]["sha"]
        nt=gh("git/trees",{"base_tree":tree,"tree":entries},"POST",True)["sha"]
        c=gh("git/commits",{"message":"Render NV37–NV40 r2 with verified domestic GIS and F18","tree":nt,"parents":[head]},"POST",True)["sha"]
        try:gh("git/refs/heads/"+REF,{"sha":c,"force":False},"PATCH",True);break
        except Exception:
            if i==2:raise
            time.sleep(2)
    print("Private visual render committed:",len(entries),"objects.")
