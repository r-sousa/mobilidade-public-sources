"""Restricted runner for a visual catalogue: read preserved private source objects,
validate exact hashes, compute outputs, publish only to the private visual branch.
No tokens, private inputs, raw rows or results in public logs/artifacts.
"""
import base64, csv, hashlib, io, json, math, os, pathlib, tempfile, urllib.parse, urllib.request, time
from datetime import datetime, timezone
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree
from pyproj import Transformer
import fitz
REPO="r-sousa/EU-transp-weekly"
SRC_REF="mobilidade-norte-recovery-20260919"
DEST_REF="norte2040-tdr214-visual-catalogue"
ROOT="statistics/assessments/norte-centro-2026-11-22/"
DEST="statistics/assessments/norte2040-tdr214/visuals/"
READ=os.environ.get("MN_PRIVATE_READ_TOKEN") or os.environ.get("MN_PRIVATE_SINK_TOKEN")
WRITE=os.environ.get("MN_PRIVATE_SINK_TOKEN")
if not READ or not WRITE: raise SystemExit("Private read/sink credentials unavailable")
API="https://api.github.com/repos/"+REPO+"/"
class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        new=super().redirect_request(req,fp,code,msg,headers,newurl)
        if new and urllib.parse.urlparse(newurl).hostname!=urllib.parse.urlparse(req.full_url).hostname:
            new.remove_header("Authorization")
        return new
opener=urllib.request.build_opener(Redirect())
def gh(path,body=None,method="GET",write=False):
    h={"Authorization":"Bearer "+(WRITE if write else READ),"Accept":"application/vnd.github+json","User-Agent":"MN-Visual-Catalogue/1.0","X-GitHub-Api-Version":"2022-11-28"}
    if body is not None: h["Content-Type"]="application/json"
    req=urllib.request.Request(API+path,data=json.dumps(body).encode() if body is not None else None,headers=h,method=method)
    with opener.open(req,timeout=120) as response: return json.load(response)
def read(path,ref=SRC_REF):
    meta=gh("contents/"+urllib.parse.quote(path,safe="/")+"?ref="+urllib.parse.quote(ref,safe=""))
    blob=gh("git/blobs/"+meta["sha"])
    if blob.get("encoding")!="base64": raise ValueError("Unexpected blob encoding")
    raw=base64.b64decode(blob["content"],validate=False)
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=meta["sha"]: raise ValueError("Git blob mismatch")
    return raw,meta["sha"]
def sha(b): return hashlib.sha256(b).hexdigest()
def jbytes(d): return (json.dumps(d,ensure_ascii=False,indent=2)+"\n").encode()
def check(b,size,digest):
    if len(b)!=size or sha(b)!=digest: raise ValueError("Source content integrity mismatch")
def text(x): return str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
out={}; result={"state":"COMPLETE_ATTEMPT","run_id":os.environ.get("GITHUB_RUN_ID"),"publication_authorized":False,"source_ref":SRC_REF,"target_ref":DEST_REF,"steps":[]}
# Legal maps; original official pages preserved in private tree, never published to public runner artifacts.
try:
    receipt=json.loads(read(ROOT+"phase9/receipt.json")[0])
    for r in receipt["requests"]:
        if r.get("source_id")!="TENtec-legal" or r.get("stage")!="subset": continue
        raw,_=read(r["path"]);check(raw,r["bytes"],r["sha256"])
        doc=fitz.open(stream=raw,filetype="pdf")
        iberia="Iberia" in r["path"]
        offset=106 if iberia else 175
        assert len(doc)==(4 if iberia else 3)
        items=[]
        for i,page in enumerate(doc):
            png=page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False).tobytes("png")
            key=f"generated/NV03-legal-OJ-{offset+i:03}.png"
            out[key]=png;items.append({"path":key,"OJ_page":offset+i,"pixel_sha256":sha(png),"width":round(page.rect.width*1.7),"height":round(page.rect.height*1.7)})
        result["steps"].append({"id":"NV03-legal-map-pages","state":"PASS","source_path":r["path"],"source_sha256":r["sha256"],"pages":items,"guard":"Full native regulatory map pages as raster; no new spatial line classification, no cropping legend, no georeferencing. OJ page numbering follows phase9 producer's 1-based page-1 indexing."})
        doc.close()
except Exception as e:
    result["steps"].append({"id":"NV03-legal-map-pages","state":"ERROR","error_type":type(e).__name__})
# Validate AMT original page, preserve evidence (no public output).
try:
    rec=json.loads(read(ROOT+"phase26/receipt.json")[0])
    r=next(x for x in rec["requests"] if x.get("source_id")=="AMT-rail-2025" and x.get("stage")=="official_pdf")
    raw,_=read(r["parts"][0]["path"]);check(raw,r["bytes"],r["sha256"])
    doc=fitz.open(stream=raw,filetype="pdf");page=doc[8]
    png=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).tobytes("png")
    out["generated/F07-AMT-source-p09.png"]=png
    result["steps"].append({"id":"F07-source-page","state":"PASS","source_sha256":r["sha256"],"path":"generated/F07-AMT-source-p09.png","page":9,"image_sha256":sha(png)})
    doc.close()
except Exception as e:
    result["steps"].append({"id":"F07-source-page","state":"ERROR","error_type":type(e).__name__})
# Actual route model, exact graph schema documented in phase24 producer.
try:
    receipt=json.loads(read(ROOT+"phase24/receipt.json")[0])
    model=next(r for r in receipt["requests"] if r.get("stage")=="road_access_model")
    meta=model["graph"]
    assert len(meta["parts"])==15
    with tempfile.TemporaryDirectory() as td:
        path=pathlib.Path(td)/"graph.npz"; hash_all=hashlib.sha256(); n=0
        with path.open("wb") as dst:
            for p in meta["parts"]:
                b,_=read(p["path"]);check(b,p["bytes"],p["sha256"])
                dst.write(b);hash_all.update(b);n+=len(b)
        assert n==meta["bytes"] and hash_all.hexdigest()==meta["sha256"]
        with np.load(path,allow_pickle=False) as z:
            expected={"indptr","indices","seconds","osm_node_ids","longitude","latitude"}
            assert set(z.files)==expected
            indptr=z["indptr"];indices=z["indices"];seconds=z["seconds"]
            lon=z["longitude"];lat=z["latitude"]; nodeids=z["osm_node_ids"]
        N=model["nodes"]; E=model["directed_arcs"]
        assert len(lon)==len(lat)==len(nodeids)==N and len(indptr)==N+1 and len(indices)==len(seconds)==E and indptr[-1]==E
        assert np.isfinite(seconds).all() and (seconds>=0).all() and (indices>=0).all() and (indices<N).all()
        G=csr_matrix((seconds,indices,indptr),shape=(N,N)); rev=G.T.tocsr()
        count,comp=connected_components(G,directed=True,connection="weak");sizes=np.bincount(comp);big=int(sizes.argmax()); idx=np.flatnonzero(comp==big)
        assert int(sizes[big])==model["largest_component_nodes"]
        trans=Transformer.from_crs(4326,3763,always_xy=True)
        xx,yy=trans.transform(lon,lat);tree=cKDTree(np.column_stack((xx[idx],yy[idx])))
        hubs=list(csv.DictReader(io.StringIO(read(ROOT+"phase24/F18-city-hubs.csv")[0].decode("utf-8"))))
        assert len(hubs)==20
        hubids=np.array([int(h["graph_index"]) for h in hubs],dtype=np.int32)
        assert all(int(nodeids[j])==int(h["snap_osm_node"]) for j,h in zip(hubids,hubs))
        base=np.array(dijkstra(G,directed=True,indices=int(hubids[0]),limit=180*60))
        check_porto_braga=float(base[hubids[1]]/60)
        assert abs(check_porto_braga-35.38613532440116)<0.01
        del base
        candidates=[
          {"id":"TFML","name":"TFM Leixões","lat":41.189877,"lon":-8.681855,"source":"https://tfm.apdl.pt/","precision":"official facility point; gate not verified"},
          {"id":"TFMG","name":"TFM Guarda","lat":40+33/60+8/3600,"lon":-(7+14/60+19.3/3600),"source":"https://tfm.apdl.pt/","precision":"official facility point; gate not verified"},
          {"id":"VCT","name":"Cais comercial de Viana","lat":41+41/60+13.77/3600,"lon":-(8+49/60+38.27/3600),"source":"https://www.amn.pt/DGAM/Capitanias/VianaCastelo/Documents/Plano%20Salvamento%20Mar%C3%ADtimo%20de%20Viana%20do%20Castelo_v20260309_signed.pdf","precision":"official quay reference PH, access from Avenida do Cabedelo; gate not verified"}
        ]
        routes=[]; snapped=[]
        for c in candidates:
            x,y=trans.transform(c["lon"],c["lat"]);dist,j=tree.query([x,y]);node=int(idx[j]);dist=float(dist)
            c.update(snap_distance_m=dist,graph_index=node,snap_lon=float(lon[node]),snap_lat=float(lat[node]),osm_node_id=int(nodeids[node]))
            if dist>300:
                c["state"]="SNAP_OVER_300M_EXCLUDED";snapped.append(c);continue
            c["state"]="INDICATIVE_FACILITY_POINT_SNAPPED";snapped.append(c)
            for direction,M in [("facility_to_hub",G),("hub_to_facility",rev)]:
                dt=dijkstra(M,directed=True,indices=node,limit=180*60)
                assert dt[node]==0
                for h,j in zip(hubs,hubids):
                    v=float(dt[j])
                    routes.append({"facility":c["id"],"hub":h["name"],"direction":direction,"minutes":v/60 if math.isfinite(v) else None,"state":"FINITE_WITHIN_180_MIN" if math.isfinite(v) else "OVER_180_OR_UNREACHABLE","snap_distance_m":dist})
                del dt
        assert len(routes)==40*sum(x["state"].startswith("INDICATIVE") for x in snapped)
        rows=[r for r in routes if r["direction"]=="hub_to_facility"]; ids=[c["id"] for c in snapped if c["state"].startswith("INDICATIVE")]
        header=["facility","hub","direction","minutes","state","snap_distance_m"];s=io.StringIO(newline="");w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(routes)
        out["generated/NV04-facility-access.csv"]=s.getvalue().encode()
        out["generated/NV04-facility-access-qa.json"]=jbytes({"graph_sha256":meta["sha256"],"graph_nodes":N,"graph_arcs":E,"baseline_porto_braga_min":check_porto_braga,"source":ROOT+"phase24/F18-city-hubs.csv","facilities":snapped,"route_count":len(routes),"finite_count":sum(r["minutes"] is not None for r in routes),"guard":"Passenger-car F18 free-flow; road-referenced facility points, not gate-to-gate or HGV. No congestion, tolls, closure, time-of-day or turn restrictions. Null not zero; >180 or unreachable. Snap distance not added to route."})
        # Static matrix preserving the primary model and explicit excluded facilities.
        def tx(x,y,s,size=14,fill="#173e50",anchor="start"):
            return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}">{text(s)}</text>'
        if ids:
            body="";left=230;cw=260
            for j,fid in enumerate(ids):
                name=next(c["name"] for c in snapped if c["id"]==fid);body+=tx(left+j*cw+cw/2,90,name,14,anchor="middle")
            for i,h in enumerate(hubs):
                y=100+i*26;body+=tx(left-8,y+17,h["name"],13,anchor="end")
                for j,fid in enumerate(ids):
                    r=next(r for r in rows if r["hub"]==h["name"] and r["facility"]==fid);v=r["minutes"];p=0 if v is None else v/180
                    color="#e9e9e9" if v is None else f'rgb({int(233-200*p)},{int(244-118*p)},{int(243-113*p)})'
                    body+=f'<rect x="{left+j*cw}" y="{y}" width="{cw-3}" height="24" fill="{color}"/>'+tx(left+j*cw+cw/2,y+17,"—" if v is None else str(round(v)),13,"white" if p>.65 else "#173e50","middle")
            width=1120;height=715
            svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial,sans-serif">'+tx(24,32,"Acessibilidade rodoviária indicativa a interfaces logísticas",22)+tx(24,55,"Centros urbanos → pontos de referência das instalações · minutos modelados · F18",13)+body+tx(24,654,"Fonte: Mobilidade Norte F18, OSM/Geofabrik 01-11-2026; coordenadas oficiais APDL e AMN.",12)+tx(24,673,"Automóvel em condições livres; não HGV, não portaria a portaria. — superior a 180 min ou sem percurso válido.",12)+tx(24,692,"Valongo, Lousado e carga aérea sem coordenada de acesso validada; excluídos. Pontos com snap >300 m omitidos.",12)+"</g></svg>\n"
            out["generated/candidate-NV04-facility-access.svg"]=svg.encode()
        result["steps"].append({"id":"NV04-F18-routing","state":"PASS" if ids else "NO_VALID_SNAPS","route_count":len(routes),"valid_facility_count":len(ids),"graph_sha256":meta["sha256"],"guards":"Only public facility reference points; passenger car, not HGV; first/last-mile unsnapped portion not modelled."})
except Exception as e:
    result["steps"].append({"id":"NV04-F18-routing","state":"ERROR","error_type":type(e).__name__})
# Commit outputs to the isolated private branch only; no public upload/logging of rows.
result["files"]=[{"path":k,"sha256":sha(b),"bytes":len(b)} for k,b in sorted(out.items())]
out["generated/visual-bridge-receipt.json"]=jbytes(result)
entries=[]
for name,raw in sorted(out.items()):
    blob=gh("git/blobs",{"encoding":"base64","content":base64.b64encode(raw).decode()},"POST",True)
    entries.append({"path":DEST+name,"mode":"100644","type":"blob","sha":blob["sha"]})
# Optimistic non-force commit to preserve concurrent catalogue edits.
for attempt in range(3):
    head=gh("git/ref/heads/"+DEST_REF)["object"]["sha"]
    tree=gh("git/commits/"+head)["tree"]["sha"]
    nt=gh("git/trees",{"base_tree":tree,"tree":entries},"POST",True)["sha"]
    commit=gh("git/commits",{"message":"TdR214 visual bridge: validated F18 and legal-map evidence","tree":nt,"parents":[head]},"POST",True)["sha"]
    try:
        gh("git/refs/heads/"+DEST_REF,{"sha":commit,"force":False},"PATCH",True)
        print("Private output committed; steps:",[(r["id"],r["state"]) for r in result["steps"]],flush=True); break
    except Exception:
        if attempt==2: raise
        time.sleep(2)
