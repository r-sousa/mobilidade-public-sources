#!/usr/bin/env python3
"""G28 source-only overlays. Lines are G10 grid-centre research, not rail tracks."""
import argparse,hashlib,json,datetime
from pathlib import Path
import requests
from shapely.geometry import Point,shape
from shapely.ops import transform,unary_union
from pyproj import Transformer
PT="https://sigservices.icnf.pt/server/rest/services/Areas_classificadas/FeatureServer/0/query"
ES="https://geoserver.iepnb.es/geoserver/RN2000/ows"
TO3035=Transformer.from_crs(4326,3035,always_xy=True).transform
FROM3763=Transformer.from_crs(3763,3035,always_xy=True).transform
SITES=[("Vila Real",32588.50,181000),("Vila Real",29588.50,181000),("Vila Real",29888.50,181250),
       ("Bragança",114308.60,239000),("Bragança",114029.35,238890.38),
       ("Bragança",113000,237308.60),("Bragança",117218.20,238781.80)]
def fetch(url,parameters,limit):
    r=requests.get(url,params=parameters,timeout=80);r.raise_for_status()
    if len(r.content)>20000000:raise ValueError("official response too large")
    d=r.json()
    if d.get("type")!="FeatureCollection" or d.get("error") or not isinstance(d.get("features"),list):
        raise ValueError("official response is not complete GeoJSON")
    if len(d["features"])>=limit or d.get("exceededTransferLimit") or d.get("features_count",0)>limit:
        raise ValueError("official result potentially truncated")
    p=[]
    for f in d["features"]:
        g=shape(f["geometry"])
        if not g.is_valid:g=g.buffer(0)
        if not g.is_valid or g.geom_type not in ("Polygon","MultiPolygon"):
            raise ValueError("invalid official geometry")
        p.append((transform(TO3035,g),f.get("properties") or {}))
    return p,{"status":"VERIFIED","count":len(p),"sha256":hashlib.sha256(r.content).hexdigest(),"url":r.url}

def archived_miteco():
    """Official MITECO dated downloadable national SHP fallback if geoserver WFS 403.
    Read only features in mainland study envelope, never redistribute national ZIP.
    """
    import tempfile,zipfile
    import geopandas as gpd
    from shapely.geometry import box
    url=("https://www.miteco.gob.es/content/dam/miteco/es/biodiversidad/"
         "servicios/banco-datos-naturaleza/3-rn2000/rn2000-shp.zip")
    max_zip=175_000_000
    with tempfile.TemporaryDirectory(prefix="G28-MITECO-") as td:
        dst=Path(td)/"RN2000-source.zip"
        h=hashlib.sha256()
        size=0
        with requests.get(url,stream=True,timeout=(20,120),headers={"User-Agent":"Mobilidade-Norte-open-data-research/1.0"}) as r:
            r.raise_for_status()
            if int(r.headers.get("Content-Length") or 0)>max_zip:raise ValueError("MITECO national ZIP over bounded cap")
            with dst.open("wb") as f:
                for chunk in r.iter_content(1024*1024):
                    if not chunk:continue
                    size+=len(chunk)
                    if size>max_zip:raise ValueError("MITECO national ZIP exceeded cap")
                    h.update(chunk);f.write(chunk)
        if not zipfile.is_zipfile(dst):raise ValueError("not MITECO original ZIP")
        folder=Path(td)/"shapefiles";folder.mkdir()
        with zipfile.ZipFile(dst) as z:
            items=z.infolist()
            if not items or sum(x.file_size for x in items)>2_000_000_000:
                raise ValueError("unbounded decompressed national shapes")
            for x in items:
                p=Path(x.filename)
                if p.is_absolute() or ".." in p.parts:raise ValueError("MITECO ZIP invalid archive path")
            shps=[x.filename for x in items if x.filename.lower().endswith(".shp")]
            if not shps:raise ValueError("no MITECO shp in original archive")
            z.extractall(folder)
        clip=gpd.GeoSeries([box(-6.95,41,-5.52,42.12)],crs="EPSG:4326")
        observed=[]
        count=0
        for shp in shps:
            df=gpd.read_file(folder/shp,bbox=clip,engine="pyogrio")
            if df.crs is None:raise ValueError("MITECO original shp lacks declared CRS")
            df=df.to_crs(3035)
            for _,record in df.iterrows():
                geo=record.geometry
                if geo is None or geo.is_empty:continue
                if not geo.is_valid:geo=geo.buffer(0)
                if not geo.is_valid or geo.geom_type not in ("Polygon","MultiPolygon"):
                    raise ValueError("MITECO original shapefile geometry invalid")
                props={str(k):str(v) for k,v in record.items() if k!="geometry" and v is not None}
                observed.append((geo,props))
                count+=1
        if not count:raise ValueError("source produced zero Spanish polygons in known RN2000 corridor bbox")
        return observed,{"status":"VERIFIED","count":count,"sha256":h.hexdigest(),
                         "url":url,"original_zip_bytes":size,"original_shapefiles":shps,
                         "source_format":"official full national SHP clipped in runner, source ZIP not published",
                         "source_date_reference":"MITECO catalogue dated 2025-12-31; verify site-specific updates"}

def source_scan():
    ret={}
    tasks={"PT_ICNF":(PT,{"f":"geojson","where":"1=1","outFields":"*",
        "geometry":"-8.7,41.04,-5.55,42.15","geometryType":"esriGeometryEnvelope",
        "inSR":"4326","outSR":"4326","spatialRel":"esriSpatialRelIntersects",
        "resultRecordCount":"3000"},3000),
      "ES_MITECO":(ES,{"service":"WFS","version":"2.0.0","request":"GetFeature",
        "typeNames":"RN2000:rn2000","outputFormat":"application/json",
        "srsName":"EPSG:4326","bbox":"-6.95,41.00,-5.52,42.12,EPSG:4326","count":"2500"},2500)}
    for key,(url,params,max_n) in tasks.items():
        try:ret[key]=fetch(url,params,max_n)
        except Exception as e:ret[key]=([],{"status":"UNKNOWN_SOURCE","reason":f"{type(e).__name__}:{str(e)[:170]}"})
    if ret["ES_MITECO"][1]["status"]!="VERIFIED":
        wfs_error=ret["ES_MITECO"][1]["reason"]
        try:
            ret["ES_MITECO"]=archived_miteco()
            ret["ES_MITECO"][1]["previous_official_WFS_failure"]=wfs_error
        except Exception as e:
            ret["ES_MITECO"]=([],{"status":"UNKNOWN_SOURCE",
                "reason":"WFS:"+wfs_error+"; MITECO_ARCHIVE:"+type(e).__name__+":"+str(e)[:180]})
    return ret
def hit(geometry,source,buffer_m=250):
    geoms,receipt=source
    if receipt["status"]!="VERIFIED":return {"status":"UNKNOWN_SOURCE","line_overlap_km":None,"proximity_m":None}
    poly=[g for g,_ in geoms]
    if not poly:return {"status":"EMPTY_OBSERVED_NOT_LEGAL_CLEARANCE","line_overlap_km":0,"proximity_m":None}
    near=[(g,p) for g,p in geoms if g.intersects(geometry.buffer(buffer_m) if buffer_m>0 else geometry)]
    if near:
        u=unary_union([g for g,_ in near])
        overlap=round(geometry.intersection(u).length/1000,3) if geometry.geom_type=="LineString" else None
    else:overlap=0 if geometry.geom_type=="LineString" else None
    return {"status":"AVOIDANCE_PRIORITY" if near else "NO_GEOMETRIC_HIT_NOT_LEGAL_CLEARANCE",
            "line_overlap_km":overlap,"proximity_m":round(min(geometry.distance(g) for g in poly),1),
            "near_sites":[str(p.get("site_name") or p.get("site_code") or p.get("SITENAME")
                or p.get("SITECODE") or p.get("nombre") or "official_id_unread") for g,p in near][:30]}
def run(g10,sources):
    assert g10["type"]=="FeatureCollection" and len(g10["features"])==27
    rows=[]
    for feat in g10["features"]:
        assert feat["properties"].get("this_is_not_an_approved_or_proposed_railway_alignment") is True
        geo=shape(feat["geometry"])
        assert geo.geom_type=="LineString"
        geom=transform(TO3035,geo)
        rows.append({"id":feat["properties"]["id"],"PT":hit(geom,sources["PT_ICNF"]),
                     "ES":hit(geom,sources["ES_MITECO"]),"PIC":"UNKNOWN_NOT_DEFINED",
                     "not_a_rail_alignment":True,"legal_clearance":False})
    assert len({r["id"] for r in rows})==27
    site_rows=[]
    for city,x,y in SITES:
        circle=transform(FROM3763,Point(x,y)).buffer(400)
        site_rows.append({"city":city,"EPSG3763":[x,y],"PT":hit(circle,sources["PT_ICNF"],0),
                          "PIC":"UNKNOWN_NOT_DEFINED","station_permitted":None})
    return rows,site_rows
def main():
    a=argparse.ArgumentParser()
    for k in ("g10","out","md"):a.add_argument("--"+k,type=Path,required=True)
    v=a.parse_args();b=v.g10.read_bytes();s=source_scan();rows,sites=run(json.loads(b),s)
    doc={"mission":"MN-GEO-RAIL-001","stage":"G28 environmental first-pass STRONG restriction",
         "UTC":datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "G10_source_sha256":hashlib.sha256(b).hexdigest(),
         "source_receipts":{k:v[1] for k,v in s.items()},
         "corridor_grid_research_27":rows,"city_research_circles_7":sites,
         "PIC":"UNKNOWN_NOT_DEFINED_OFFICIAL_SPATIAL_SOURCE_REQUIRED",
         "site_specific_Natura2000_management_objectives":"NOT_YET_REVIEWED",
         "legal_or_environmental_authorization":False,
         "not_real_rail_alignments":True,"no_DGT_download":True,"no_Fxx_or_Site":True,
         "Vila_Real_Braganca_mandatory":True,"Sanabria_excluded":True}
    v.out.parent.mkdir(parents=True,exist_ok=True)
    v.out.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n")
    lines=["# G28 — Natura 2000 PT/ES e PIC, triagem ambiental inicial","",
       "As 27 linhas G10 são cadeias de quadrículas de investigação, não traçados ferroviários. Interseções e proximidades são indícios para priorizar evitamento, não AIA/licenças.",
       "","| Fonte | Resposta primária | Geometrias |","|---|---|---:|"]
    for k,q in s.items():lines.append(f"| {k} | {q[1]['status']} | {q[1].get('count','indeterminado')} |")
    lines+=["","**PIC continua por definir e localizar.** A ausência de geometria nunca prova a inexistência de restrições. Não aprovar shortlist ambiental ou novas aquisições de MDT com base apenas nesta fase.","",
            "| Opção G10 | ICNF | MITECO | PIC |","|---|---|---|---|"]
    for z in rows:lines.append(f"| {z['id']} | {z['PT']['status']} | {z['ES']['status']} | pendente |")
    lines+=["","Confrontar polígonos com áreas contínuas de projeto, valores de conservação e efeitos indirectos/cumulativos. Sem Fxx/Site, custos de obra, tempos de comboio ou declaração de viabilidade."]
    v.md.write_text("\n".join(lines)+"\n")
    print(json.dumps({"G10":len(rows),"areas_cidades":len(sites),"source_status":doc["source_receipts"],"PIC":doc["PIC"]},ensure_ascii=False))
if __name__=="__main__":main()
