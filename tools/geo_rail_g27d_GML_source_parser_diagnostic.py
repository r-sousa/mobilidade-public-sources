#!/usr/bin/env python3
"""G27D DGT GeoMedia GML original local structure non-sensitive diagnosis.
Single WFS 1.1.0 GetFeature for REN, RAN, CRUS, max 1. Print no full source
geometry. To derive robust geometries, identify correct GML 3.1 coordinates.
"""
import json,urllib.parse,urllib.request,xml.etree.ElementTree as ET,hashlib,tempfile
from pathlib import Path
import pyogrio
SOURCES={
 "REN":"https://servicos.dgterritorio.pt/SDISNITWFSSRUP_REN_NORTE/WFService.aspx",
 "RAN":"https://servicos.dgterritorio.pt/SDISNITWFSSRUP_RAN_PT1/WFService.aspx",
 "CRUS":"https://servicos.dgterritorio.pt/SDISNITWFSCRUS/WFService.aspx"}
NAMES={"REN":"gmgml:REN_Norte","RAN":"gmgml:RAN","CRUS":"gmgml:CRUS"}
def local(s):return str(s).rsplit("}",1)[-1]
for name,endpoint in SOURCES.items():
 qs={"service":"WFS","version":"1.1.0","request":"GetFeature","typeName":NAMES[name],
    "bbox":"32188.5,180600,32988.5,181400,EPSG:3763","maxFeatures":1}
 url=endpoint+"?"+urllib.parse.urlencode(qs)
 try:
  with urllib.request.urlopen(url,timeout=45) as resp:body=resp.read(2500000)
  root=ET.fromstring(body)
  ntypes={};pos=[];srs=[]
  for x in root.iter():
   ntypes[local(x.tag)]=ntypes.get(local(x.tag),0)+1
   if local(x.tag) in ("posList","coordinates","pos") and len(pos)<4:
    pos.append({"tag":local(x.tag),"text_first_80":(x.text or "")[:80].strip(),
      "srsDimension":x.attrib.get("srsDimension"),"dimension":x.attrib.get("dimension")})
   if x.attrib.get("srsName") and x.attrib.get("srsName") not in srs:srs.append(x.attrib.get("srsName"))
  print("SOURCE_GML_STRUCT="+json.dumps({"topic":name,"bytes":len(body),"SHA256":hashlib.sha256(body).hexdigest(),
    "root":local(root.tag),"numberOfFeatures":root.attrib.get("numberOfFeatures"),
    "nodes":sorted(ntypes.items(),key=lambda z:-z[1])[:25],"geometry_srs":srs[:6],"coords":pos},ensure_ascii=False))
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"original.gml";path.write_bytes(body)
   for opts in ({},{"DOWNLOAD_SCHEMA":"NO"}):
    try:
     inf=pyogrio.read_info(path,**({"dataset_options":opts} if opts else {}))
     g=pyogrio.read_dataframe(path,**({"dataset_options":opts} if opts else {}))
     print("GDAL_GML_READER="+json.dumps({"topic":name,"opts":opts,"layers":str(inf.get("layer_name")),"rows":len(g),"crs":str(g.crs),
       "columns":list(g.columns)},ensure_ascii=False))
    except Exception as e:
     print("GDAL_GML_ERROR="+json.dumps({"topic":name,"opts":opts,"type":type(e).__name__,"short":str(e)[:260]},ensure_ascii=False))
 except Exception as e:
  print("SOURCE_FETCH_OR_XML_ERROR="+json.dumps({"topic":name,"type":type(e).__name__,"short":str(e)[:200]}))
