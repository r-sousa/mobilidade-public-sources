"""NV41 targeted acquisition. Private sink; no private data in logs or public releases."""
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


import csv,io,gzip,math,itertools,unicodedata
from openpyxl import load_workbook
from mn_public_acquisition.ine_partitioned import _dimension_items,_dimensions,_period_labels,_resolve_label,_flatten
OUT=ROOT+"NV41/"
rec={"run_id":os.environ.get("GITHUB_RUN_ID"),"sources":{},"status":"IN_PROGRESS","publication_authorized":False}
files={}
def dump(obj):return (json.dumps(obj,ensure_ascii=False,indent=2,default=str)+"\n").encode()
def store(name,raw):files[name]=raw
def commit():
    files["acquisition-receipt.json"]=dump(rec)
    entries=[]
    for name,raw in files.items():
        assert len(raw)<25_000_000
        z=gh("git/blobs",{"content":base64.b64encode(raw).decode(),"encoding":"base64"},"POST",True)
        entries.append({"path":OUT+name,"mode":"100644","type":"blob","sha":z["sha"]})
    for i in range(4):
        head=gh("git/ref/heads/"+REF)["object"]["sha"];tree=gh("git/commits/"+head)["tree"]["sha"]
        nt=gh("git/trees",{"base_tree":tree,"tree":entries},"POST",True)["sha"]
        c=gh("git/commits",{"message":"NV41: preserved native evidence and reproducible outputs","tree":nt,"parents":[head]},"POST",True)["sha"]
        try:gh("git/refs/heads/"+REF,{"sha":c,"force":False},"PATCH",True);files.clear();return
        except Exception:
            if i==3:raise
            time.sleep(2)
def public(url,cap=20_000_000,timeout=45):
    req=urllib.request.Request(url,headers={"User-Agent":"MobilidadeNorte-NV41/1.0","Accept":"application/json"})
    with opener.open(req,timeout=timeout) as f:raw=f.read(cap+1)
    if len(raw)>cap:raise ValueError("response cap exceeded")
    return raw
def norm(v):return "".join(c for c in unicodedata.normalize("NFKD",str(v).casefold()) if not unicodedata.combining(c)).strip()
def err(name,e):rec["sources"][name]={"state":"ERROR","type":type(e).__name__,"detail":str(e)[:160]};print(name,type(e).__name__,flush=True)
reg=json.loads(file(OUT+"source-register.json",REF))
store("F88-original.csv",file(reg["f88"]["path"],SRCREF,reg["f88"]["blob"]))
rec["sources"]["F88"]={"state":"REUSED","blob":reg["f88"]["blob"],"guard":reg["f88"]["guard"]}
# F49 preserved private release; use API octet stream, no public reacquisition.
for a in reg["f49"]["assets"]:
    name="F49-"+str(a["year"])+"-"+a["window"]
    try:
        req=urllib.request.Request("https://api.github.com/repos/"+REPO+"/releases/assets/"+str(a["id"]),headers={"Authorization":"Bearer "+READ,"Accept":"application/octet-stream","User-Agent":"MobilidadeNorte-NV41/1.0"})
        with opener.open(req,timeout=45) as f:raw=f.read(a["bytes"]+1)
        assert len(raw)==a["bytes"] and sha(raw)==a["sha256"],"Preserved F49 asset mismatch"
        wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
        inv=[];native=[]
        for sh in wb:
            if sh.max_row*sh.max_column>1_000_000:raise ValueError("worksheet cap")
            cells=[]
            for i,row in enumerate(sh.iter_rows(values_only=True),1):
                vals=[[j,v] for j,v in enumerate(row,1) if v is not None]
                if vals:cells.append([i,vals])
            inv.append({"sheet":sh.title,"rows":sh.max_row,"columns":sh.max_column,"preview":cells[:12]})
            native.append({"sheet":sh.title,"cells":cells})
        store("native/"+name+"-inventory.json",dump(inv))
        store("native/"+name+"-cells.json.gz",gzip.compress(dump(native),mtime=0))
        rec["sources"][name]={"state":"REUSED","asset_id":a["id"],"sha256":sha(raw),"sheets":len(inv),"window":a["window"],"year":a["year"]}
        print(name,"verified",len(inv),flush=True)
    except Exception as e:err(name,e)
commit()
# Eurostat one coherent API release. Native categories and flags preserved.
def jsonstat(obj):
    ids=obj["id"];dims=obj["dimension"];sizes=obj["size"]
    cats=[]
    for k in ids:
        c=dims[k]["category"];ix=c["index"]
        keys=sorted(ix,key=ix.get) if isinstance(ix,dict) else ix
        cats.append(keys)
    vals=obj.get("value",{});flags=obj.get("status",{})
    rows=[]
    for i,v in (enumerate(vals) if isinstance(vals,list) else ((int(i),v) for i,v in vals.items())):
        if v is None:continue
        pos=i;coords=[]
        for n in sizes[::-1]:coords.append(pos%n);pos//=n
        row={k:cats[j][c] for j,(k,c) in enumerate(zip(ids,coords[::-1]))}
        row["value"]=v;row["flag"]=flags.get(str(i),"") if isinstance(flags,dict) else (flags[i] if i<len(flags) else "")
        rows.append(row)
    return rows
geos=["PT11","PT","EU27_2020","PT111","PT112","PT119","PT11A","PT11B","PT11C","PT11D","PT11E"]
def euro(ds,params):
    url="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"+ds+"?"+urllib.parse.urlencode([("lang","EN")]+params,doseq=True)
    raw=public(url);obj=json.loads(raw);rows=jsonstat(obj)
    store("native/"+ds+".json",raw)
    rec["sources"][ds]={"state":"PASS","url":url,"sha256":sha(raw),"rows":len(rows),"dimensions":{k:obj["dimension"][k]["category"].get("label",{}) for k in obj["id"]}}
    return obj,rows
compar=[];eurocounts=[]
try:
    obj,rows=euro("tran_r_acci",[("geo",g) for g in geos[:3]]+[("sinceTimePeriod","2019"),("untilTimePeriod","2025")])
    pops,pr=euro("demo_pjan",[("geo",g) for g in geos]+[("age","TOTAL"),("sex","T"),("unit","NR"),("sinceTimePeriod","2019"),("untilTimePeriod","2025")])
    pop={(r["geo"],r["time"]):r for r in pr}
    def label(k,v):return obj["dimension"][k]["category"].get("label",{}).get(v,v)
    for r in rows:
        y=int(r["time"])
        if not 2019<=y<=2025:continue
        descriptors=[norm(label(k,r[k])) for k in obj["id"] if k not in ("geo","time","unit","freq")]
        # Accept explicit fatalities category only; no guessing native victim codes.
        if not any(re.search(r"fatalit|persons killed|people killed|killed persons|deaths|killed",v) for v in descriptors):continue
        if any(re.search(r"injur|accident[s]? with|casualties",v) and not re.search(r"fatalit|killed|deaths",v) for v in descriptors):continue
        unit=norm(label("unit",r["unit"])) if "unit" in r else ""
        if r.get("unit")=="NR" or unit in ("number","number of persons"):
            p=pop.get((r["geo"],r["time"]))
            if p and p["value"]>0:
                compar.append({"geo":r["geo"],"year":y,"rate":r["value"]*1e6/p["value"],"fatalities":r["value"],"population":p["value"],"flag":r["flag"],"population_flag":p["flag"],"source":"tran_r_acci / demo_pjan","native":r})
                eurocounts.append(r)
        elif "million" in unit and ("inhabitant" in unit or "person" in unit):
            compar.append({"geo":r["geo"],"year":y,"rate":r["value"],"flag":r["flag"],"source":"tran_r_acci native rate","native":r})
    # do not choose among conflicting dimension combinations or mix native/calculated rates
    by={}
    for r in compar:
        key=(r["geo"],r["year"])
        if key in by and abs(by[key]["rate"]-r["rate"])>0.6:raise ValueError("multiple conflicting fatality series")
        if key not in by or "fatalities" in r:by[key]=r
    compar=list(by.values())
    store("comparative-series.json",dump(compar))
except Exception as e:err("Eurostat_comparison",e);compar=[]
commit()
# INE: exact metadata code dictionary, choose published named geography members.
nuts=["Norte","Alto Minho","Cávado","Ave","Área Metropolitana do Porto","Alto Tâmega e Barroso","Tâmega e Sousa","Douro","Terras de Trás-os-Montes","Portugal"]
def memberlabel(item):return str(item.get("categ_dsg") or item.get("Designacao") or item.get("Descricao") or item.get("label") or "")
ine_rows={}
for code in ("0012775","0012774"):
    try:
        murl="https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?"+urllib.parse.urlencode({"varcd":code,"lang":"PT"})
        raw=public(murl);meta=json.loads(raw);dims=_dimensions(meta)
        store("native/INE-"+code+"-metadata.json",raw)
        dicts={k:{c:memberlabel(v) for c,v in _dimension_items(meta,int(k[3:])).items()} for k in dims}
        store("native/INE-"+code+"-dictionary.json",dump(dicts))
        geocodes={}
        for n in nuts:
            try:geocodes[n]=_resolve_label(meta,2,n)
            except Exception:pass
        assert "Norte" in geocodes and len(geocodes)>=9,"NUTS members absent"
        periods={k:v for k,v in _period_labels(meta).items() if re.fullmatch(r"20(19|2[0-5])",v)}
        assert periods,"no target years"
        rows=[];queries=[]
        # Only requested year/geography. All categories of other dimensions native.
        for k,y in periods.items():
            params={"op":"2","varcd":code,"lang":"PT","Dim1":k,"Dim2":",".join(geocodes.values())}
            url="https://www.ine.pt/ine/json_indicador/pindica.jsp?"+urllib.parse.urlencode(params)
            try:
                raw=public(url);body=json.loads(raw);rr=_flatten(body)
                assert len(rr)<=40000
                store("native/INE-"+code+"-"+y+".json",raw)
                rows.extend(rr);queries.append({"year":y,"url":url,"sha256":sha(raw),"rows":len(rr)})
            except Exception as e:queries.append({"year":y,"state":"ERROR","type":type(e).__name__})
            time.sleep(2)
        store("INE-"+code+"-rows.json",dump({"rows":rows,"dimensions":dicts,"geocodes":geocodes,"periods":periods}))
        rec["sources"]["INE-"+code]={"state":"PASS" if rows else "EMPTY","metadata_url":murl,"metadata_sha256":sha(raw) if not queries else None,"geocodes":geocodes,"queries":queries,"rows":len(rows),"guard":"Source-native; window unspecified until explicit definition checked; accidents != victims"}
    except Exception as e:err("INE-"+code,e)
    commit()
rec["status"]="ACQUISITION_COMPLETE_WITH_GATES"
commit()
# Rendering separate from acquisition. Use pinned evidence register + native observations via isolated local files.
with tempfile.TemporaryDirectory() as t:
    td=pathlib.Path(t)
    for name in ("source-register.json","F88-original.csv","comparative-series.json","INE-0012775-rows.json","INE-0012774-rows.json","acquisition-receipt.json"):
        try:(td/name).write_bytes(file(OUT+name,REF))
        except Exception:pass
    (td/"render.py").write_bytes(file(OUT+"render.py",REF))
    out=td/"out";out.mkdir()
    env={k:v for k,v in os.environ.items() if k in ("PATH","HOME","LANG","LC_ALL","SYSTEMROOT")};env["MPLCONFIGDIR"]=str(td/"mpl")
    p=subprocess.run([sys.executable,str(td/"render.py"),str(td),str(out)],env=env,capture_output=True,timeout=180)
    if p.returncode:
        e=p.stderr.decode(errors="replace");print("Render diagnostic:",re.findall(r'render\.py", line (\d+)',e)[-1:],"failure",flush=True);raise SystemExit(1)
    for f in out.iterdir():store("render/"+f.name,f.read_bytes())
    rec["status"]="RENDERED_WITH_GATES";rec["render_outputs"]=[{"path":k,"sha256":sha(v),"bytes":len(v)} for k,v in files.items()]
    commit()
