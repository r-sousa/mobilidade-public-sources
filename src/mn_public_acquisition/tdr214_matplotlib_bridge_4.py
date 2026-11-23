"""Execute the pinned, reviewed private Matplotlib chart generator and save only to private branch."""
import os, json, hashlib, base64, urllib.request, urllib.parse, subprocess, tempfile, pathlib, sys, time
REPO="r-sousa/EU-transp-weekly"
REF="norte2040-tdr214-visual-catalogue"
ROOT="statistics/assessments/norte2040-tdr214/visuals/"
PINS={"nv34-nv36-inputs.json":"b162d84f365ecae4dfd6b8e70d04d20bad26f52c","build-nv34-nv36.py":"83e7a4ffca208a02d220038cc303b611d5ee2c1a"}
READ=os.environ.get("MN_PRIVATE_READ_TOKEN") or os.environ.get("MN_PRIVATE_SINK_TOKEN")
WRITE=os.environ.get("MN_PRIVATE_SINK_TOKEN")
if not READ or not WRITE: raise SystemExit("Private bridge tokens unavailable")
def gh(path,body=None,method="GET",write=False):
    h={"Authorization":"Bearer "+(WRITE if write else READ),"Accept":"application/vnd.github+json","User-Agent":"Norte2040-visual-render/1.0"}
    if body is not None: h["Content-Type"]="application/json"
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+"/"+path,data=json.dumps(body).encode() if body is not None else None,headers=h,method=method)
    with urllib.request.urlopen(req,timeout=90) as f:return json.load(f)
with tempfile.TemporaryDirectory() as td:
    td=pathlib.Path(td)
    for name,pin in PINS.items():
        blob=gh("git/blobs/"+pin);raw=base64.b64decode(blob["content"])
        assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==pin
        (td/name).write_bytes(raw)
    inputs=json.loads((td/"nv34-nv36-inputs.json").read_text(encoding="utf-8"))
    geo=td/"CAOP2025-municipios.geojson"
    with geo.open("wb") as dst:
        for part in inputs["geometry"]["parts"]:
            meta=gh("contents/"+urllib.parse.quote(part["path"],safe="/")+"?ref="+urllib.parse.quote(inputs["sources"]["geometry"]["ref"],safe=""))
            blob=gh("git/blobs/"+meta["sha"])
            raw=base64.b64decode(blob["content"])
            assert len(raw)==part["bytes"] and hashlib.sha256(raw).hexdigest()==part["sha256"]
            dst.write(raw)
    assert hashlib.sha256(geo.read_bytes()).hexdigest()==inputs["geometry"]["sha256"]
    out=td/"generated"
    # No bridge credentials passed to the renderer process.
    child_env={k:v for k,v in os.environ.items() if k in ("PATH","HOME","LANG","LC_ALL","SYSTEMROOT")}
    child_env["MPLCONFIGDIR"]=str(td/"mpl")
    subprocess.run([sys.executable,str(td/"build-nv34-nv36.py"),str(td/"nv34-nv36-inputs.json"),str(geo),str(out)],check=True,env=child_env,capture_output=True,timeout=90)
    files=list(out.iterdir());assert len(files)==7
    for name in ["candidate-NV34-pendular-geography","candidate-NV35-industrial-access-geography","candidate-NV36-scenario-investment-matrix"]:
        for ext in ["png","svg"]: assert (out/(name+"."+ext)).is_file()
    receipt={"run_id":os.environ.get("GITHUB_RUN_ID"),"state":"PASS","input_blob_pins":PINS,"publication_authorized":False,"outputs":[{"path":"generated/"+p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}
    (out/"nv34-nv36-render-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    entries=[]
    for p in out.iterdir():
        blob=gh("git/blobs",{"content":base64.b64encode(p.read_bytes()).decode(),"encoding":"base64"},"POST",True)
        entries.append({"path":ROOT+"generated/"+p.name,"mode":"100644","type":"blob","sha":blob["sha"]})
    for attempt in range(3):
        head=gh("git/ref/heads/"+REF)["object"]["sha"]
        tree=gh("git/commits/"+head)["tree"]["sha"]
        newtree=gh("git/trees",{"base_tree":tree,"tree":entries},"POST",True)["sha"]
        commit=gh("git/commits",{"message":"Render NV34–NV36, Matplotlib print-grade PNG + SVG and QA","tree":newtree,"parents":[head]},"POST",True)["sha"]
        try:
            gh("git/refs/heads/"+REF,{"sha":commit,"force":False},"PATCH",True);break
        except Exception:
            if attempt==2:raise
            time.sleep(2)
    print("Private visual render committed:",len(entries),"objects; no private rows emitted.")
