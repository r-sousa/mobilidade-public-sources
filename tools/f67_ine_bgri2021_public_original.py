#!/usr/bin/env python3
"""F67 public-source preservation: download EXACT INE BGRI21_CONT.zip.

Do not substitute local municipality BGRI subsets, grid rasters, mirrors,
Drive handoff or the private-sink object. Data are published only if all
original official bytes match the historical user-verified SHA256 and byte
length. This is a separate public archive release, NOT a change to F67
canonical/private data lifecycle or user-derived personal data.
"""
from __future__ import annotations
import argparse,hashlib,json,os,sqlite3,tempfile,time,urllib.error,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path

SOURCE="https://mapas.ine.pt/download/filesGPG/2021/BGRI21_CONT.zip"
LANDING="https://mapas.ine.pt/download/index2021.phtml"
META="https://mapas.ine.pt/download/metadados/bgri.html"
EXPECTED_NAME="BGRI21_CONT.gpkg"
EXPECTED_BYTES=246754080
EXPECTED_SHA256="3eb49fb9e262e9d6ccb4b493811b7e21e2bbb31b0afe1431851ddd459ad7f171"
CHUNK=2*1024*1024
MAX_SIZE=500*1024*1024
MAX_GPKG_UNCOMPRESSED=7*1024*1024*1024

def sha256(path):
 h=hashlib.sha256()
 with path.open("rb") as fh:
  for chunk in iter(lambda:fh.read(CHUNK),b""):h.update(chunk)
 return h.hexdigest()

def get_original(output,attempts=3):
 output.parent.mkdir(parents=True,exist_ok=True)
 errors=[]
 for attempt in range(1,attempts+1):
  try:
   request=urllib.request.Request(SOURCE,headers={
     "User-Agent":"MobilidadeNorte-F67-public-original-source-preservation/1.0",
     "Accept":"application/zip,application/octet-stream,*/*"})
   with urllib.request.urlopen(request,timeout=90) as src:
    ctype=src.headers.get("Content-Type","")
    length=src.headers.get("Content-Length")
    if length and int(length)>MAX_SIZE:raise ValueError("remote_file_size_exceeds_cap")
    if not src.url.startswith("https://mapas.ine.pt/"):
     raise ValueError("unexpected_non_ine_redirect_to_other_domain")
    h=hashlib.sha256();num=0
    part=output.with_suffix(output.suffix+".part")
    with part.open("wb") as target:
     while True:
      b=src.read(CHUNK)
      if not b:break
      target.write(b);h.update(b);num+=len(b)
      if num>MAX_SIZE:raise ValueError("download_exceeds_maximum_size")
    if num!=EXPECTED_BYTES:raise ValueError(f"INE_original_unexpected_bytes_{num}")
    if h.hexdigest()!=EXPECTED_SHA256:
     raise ValueError(f"INE_original_checksum_changed_{h.hexdigest()}")
    part.replace(output)
    return {"source_direct_url":SOURCE,"source_final_url":src.url,
      "http_content_type":ctype,"original_bytes":num,"original_sha256":h.hexdigest(),
      "download_attempt":attempt}
  except Exception as exc:
   errors.append({"attempt":attempt,"class":type(exc).__name__,
       "detail":str(exc)[:250]})
   try:output.with_suffix(output.suffix+".part").unlink(missing_ok=True)
   except Exception:pass
   if attempt<attempts:time.sleep(attempt*2)
 raise RuntimeError("NO_PUBLIC_RELEASE_source_original_unavailable_OR_not_exact_hash: "+json.dumps(errors))

def inspect_archive(path):
 if path.stat().st_size!=EXPECTED_BYTES or sha256(path)!=EXPECTED_SHA256:
  raise ValueError("original_SHA256_size_mismatch")
 if not zipfile.is_zipfile(path):raise ValueError("not_zip_archive")
 with zipfile.ZipFile(path) as zipped:
  members=[v for v in zipped.infolist() if not v.is_dir()]
  gpkg=[m for m in members if Path(m.filename).name==EXPECTED_NAME]
  if len(gpkg)!=1:raise ValueError("original_member_count_not_one")
  if gpkg[0].file_size>MAX_GPKG_UNCOMPRESSED:raise ValueError("uncompressed_gpkg_exceeds_cap")
  if any(m.flag_bits & 0x1 for m in members):raise ValueError("encrypted_archive_not_supported")
  corrupt=zipped.testzip()
  if corrupt:raise ValueError("ZIP_CRC_corrupt_"+corrupt[:60])
  members_report=[{"name":m.filename,"uncompressed_bytes":m.file_size,
   "compressed_bytes":m.compress_size,"CRC32":f"{m.CRC:08x}"} for m in members]
  with tempfile.TemporaryDirectory(prefix="f67-native-gpkg-") as temp:
   gpkg_path=Path(temp)/EXPECTED_NAME
   with zipped.open(gpkg[0]) as src,gpkg_path.open("wb") as target:
    while True:
     b=src.read(CHUNK)
     if not b:break
     target.write(b)
   conn=sqlite3.connect(f"file:{gpkg_path}?mode=ro",uri=True,timeout=20)
   try:
    rows=conn.execute("SELECT table_name,data_type,srs_id FROM gpkg_contents").fetchall()
    geometries=conn.execute("SELECT table_name,column_name,geometry_type_name,srs_id FROM gpkg_geometry_columns").fetchall()
    layers=[]
    for table,kind,srs in rows:
     q='"'+str(table).replace('"','""')+'"'
     columns=[x[1] for x in conn.execute("PRAGMA table_info("+q+")").fetchall()]
     # COUNT can require full scans on huge geopackage; do only if <=1GB extracted
     count=conn.execute("SELECT count(*) FROM "+q).fetchone()[0] if gpkg_path.stat().st_size < 1_000_000_000 else None
     layers.append({"name":table,"content_kind":kind,"srs_id":srs,
       "row_count_exact_if_below_1GB":count,
       "original_field_names":columns[:160]})
    integrity=conn.execute("PRAGMA quick_check").fetchone()[0]
    if integrity!="ok":raise ValueError("GPKG_SQLite_quick_check_failed_"+str(integrity))
    if not any(k=="features" for _,k,_ in rows):
     raise ValueError("missing_geographic_geopackage_features_layer")
   finally:conn.close()
 return {"zip_members":members_report,"gpkg_sqlite_quick_check":"ok",
    "gpkg_geographic_layers":geometries,"gpkg_contents":layers,
    "gpkg_extracted_size_bytes":gpkg_path.stat().st_size if False else gpkg[0].file_size,
    "expected_original_member":EXPECTED_NAME}

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--zip",required=True,type=Path)
 p.add_argument("--receipt",required=True,type=Path)
 p.add_argument("--markdown",required=True,type=Path)
 p.add_argument("--dry-local",action="store_true")
 a=p.parse_args()
 origin={"source":"INE Instituto Nacional de Estatística","year":2021,
   "source_set_id":"F67","producer_landing_url":LANDING,
   "official_archive_url":SOURCE,"producer_metadata_url":META,
   "producer_license_metadata":"BGRI metadata: noLimitations; noConditionsApply; Acesso e uso sem condições",
   "exact_historical_original_bytes":EXPECTED_BYTES,
   "exact_historical_original_SHA256":EXPECTED_SHA256,
   "previous_PRIVATE_sink_receipt_SHA_provenance":"receipts/F67/03b729e73f0adf411f893c50cac6883878629b6b8ab0d66338fdf9ebcf096738.json",
   "reproduction_note":"new independent exact producer acquisition, not Google Drive or third party",
   "private_canonical_Fxx_state_unchanged":True,
   "public_original_release_is_explicitly_requested_by_user":True}
 transfer={"original_bytes":EXPECTED_BYTES,"original_sha256":EXPECTED_SHA256,"download_attempt":0} if a.dry_local else get_original(a.zip)
 qa=inspect_archive(a.zip)
 receipt={**origin,**transfer,**qa,"acquisition_utc":datetime.now(timezone.utc).isoformat(),
   "release_gate":"approved_if_original_SHA_size_ZIP_CRC_and_SQLite_pass"}
 a.receipt.parent.mkdir(parents=True,exist_ok=True)
 a.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
 a.markdown.parent.mkdir(parents=True,exist_ok=True)
 a.markdown.write_text("# F67 — arquivo original INE BGRI2021 Continente\n\n"+
   "Ficheiro binário original obtido diretamente do produtor, sem alterações: `BGRI21_CONT.zip`.\n\n"+
   f"**SHA-256:** `{EXPECTED_SHA256}`; **bytes:** {EXPECTED_BYTES:,}.\n\n"+
   f"**Origem oficial:** {SOURCE}  \n**Entrada INE:** {LANDING}  \n**Metadados e direitos:** {META}\n\n"+
   "O INE indica acesso público e uso sem condições no registo de metadados BGRI. A fonte original foi mantida intacta; a redistribuição é um arquivo adicional solicitado pelo utilizador, sem alterar o circuito canónico privado F67. Cite sempre INE, Censos 2021 e os metadados originais.\n\n"+
   "Contém informação estatística e geográfica de subsecção censitária de 2021. **Não contém, por si, emprego por estabelecimento, fluxos origem-destino, procura de comboio nem localização de estações.** Requer validação das colunas e dos métodos de proteção da confidencialidade.\n\n"+
   "## QA verificado\n\n"+
   f"- ZIP CRC: passou; GeoPackage SQLite: {qa['gpkg_sqlite_quick_check']}; número de camadas: {len(qa['gpkg_contents'])}\n"+
   "- Nome e integridade do arquivo original validados por SHA-256 e comprimento contra a cópia F67 histórica de setembro de 2026.\n")
 print("F67_PUBLIC_ORIGINAL_VERIFIED="+json.dumps({"sha256":EXPECTED_SHA256,
   "bytes":EXPECTED_BYTES,"layers":[{"name":x["name"],"rows":x["row_count_exact_if_below_1GB"],
    "fields":x["original_field_names"][:12]} for x in qa["gpkg_contents"]],
   "metadata_license":origin["producer_license_metadata"]},ensure_ascii=False,separators=(',',':')))
if __name__=="__main__":main()
