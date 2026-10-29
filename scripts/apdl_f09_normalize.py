#!/usr/bin/env python3
"""APDL F09: deterministic source-native normalisation. No external I/O."""
import csv, hashlib, json, sys, unicodedata, zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET
M="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R="{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
P="{http://schemas.openxmlformats.org/package/2006/relationships}"
RELEASE="mn-src-f09-a8e694da3696db4b91eb"
FILES=[
 ("nature-2025.xlsx","nature","annual_2025",2025,2024,"2025-01/12","2024-01/12","c84e1b0d3d5e2abc064552cc647e8796ae0087b527f6d550ce19af6e30addfc5"),
 ("od-2025.xlsx","geography","annual_2025",2025,2024,"2025-01/12","2024-01/12","5d8774f86348dd56fac5992691154c9346a14b7498c05c8f2203b2dbe276922e"),
 ("nature-2026sep.xlsx","nature","sept_2026",2026,2025,"2026-01/09","2025-01/09","fc2ffdb67e8a260bfb754dacfcbd4b25048b55db88ce3fd5d05dcba9ea520ff1"),
 ("od-2026sep.xlsx","geography","sept_2026",2026,2025,"2026-01/09","2025-01/09","1229cfa886772fcdc4fe2a2bbe0747cb67b06f7f179d2c22297837ae6e927862")]
COLS=("carga","descarga","total")
FIELDS=["source_set_id","producer","edition","source_release","source_asset","source_sha256",
 "source_sheet","source_row","source_cell","source_label","source_row_role",
 "cargo_group","cargo_nature","od_zone","od_class","od_scope","reference_year",
 "period","edition_position","operation","unit","value","status"]

def simple(s):
 return "".join(c for c in unicodedata.normalize("NFKD",str(s).upper()) if not unicodedata.combining(c)).strip()

def numeric(s):
 try: return Decimal(s.strip()) if s and s.strip() not in ("-"," - ","#DIV/0!") else None
 except InvalidOperation: return None

def read_xlsx(path):
 with zipfile.ZipFile(path) as z:
  bad=z.testzip()
  if bad: raise ValueError("Corrupt XLSX member: "+bad)
  st=[]
  if "xl/sharedStrings.xml" in z.namelist():
   root=ET.fromstring(z.read("xl/sharedStrings.xml"))
   st=["".join(t.text or "" for t in el.iter(M+"t")) for el in root.findall(M+"si")]
  w=ET.fromstring(z.read("xl/workbook.xml"))
  sheets=w.find(M+"sheets").findall(M+"sheet")
  if len(sheets)!=1: raise ValueError("Unexpected number of source sheets")
  rel=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
  relmap={x.attrib["Id"]:x.attrib["Target"] for x in rel.findall(P+"Relationship")}
  target=relmap[sheets[0].attrib[R+"id"]]
  target=target.lstrip("/") if target.startswith("/") else "xl/"+target
  root=ET.fromstring(z.read(target.replace("xl/xl/","xl/")))
  cells={}
  for row in root.findall(".//"+M+"sheetData/"+M+"row"):
   for c in row.findall(M+"c"):
    x=c.find(M+"v")
    if x is not None:
     val=st[int(x.text)] if c.attrib.get("t")=="s" else x.text
    else:
     inline=c.find(M+"is")
     val="".join(t.text or "" for t in inline.iter(M+"t")) if inline is not None else None
    if val is not None:cells[c.attrib["r"]]=str(val)
  return sheets[0].attrib["name"],cells

def normalise(config, folder):
 name,family,edition,year,comparison,period,comparison_period,sha=config
 path=folder/name
 raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=sha: raise ValueError("Source SHA mismatch for "+name)
 sheet,c=read_xlsx(path)
 first=11 if family=="nature" else 8
 last=91 if family=="nature" else 29
 marker=simple(c.get("A"+str(last),""))
 if "TOTAL" not in marker: raise ValueError("Missing producer TOTAL line")
 zone=""; group=""; records=[]; totals={}; differences=[]
 for row in range(first,last+1):
  rawlabel=c.get("A"+str(row),"").strip()
  if not rawlabel:continue
  lbl=simple(rawlabel)
  role="detail"; nature=rawlabel; odclass=""; odscope=""
  if family=="nature":
   if lbl=="TOTAL":role="overall_total";nature=""
   elif lbl=="CARGA GERAL":role="cargo_group_total";group="CARGA GERAL";nature=""
   elif lbl in ("FRACIONADA","CONTENTORIZADA","CARGA CONTENTORIZADA","CONTENTORES","RO-RO","RO RO","GRANEIS SOLIDOS","GRANEL SOLIDO","GRANEIS LIQUIDOS","GRANEL LIQUIDO"):
    role="cargo_category_total";group=rawlabel;nature=""
  else:
   nature=""
   idx=(row-8)%7
   if row==29:role="overall_total";odscope="all_zones";odclass=""
   elif idx==0:role="zone_total";zone=rawlabel;odscope="APDL_zone";odclass=""
   elif idx==1:role="zone_group_total";odclass=rawlabel;odscope="APDL_zone"
   else:role="zone_cargo_type";odclass=rawlabel;odscope="APDL_zone"
  for position,period_year,period_name,base in (
   ("current",year,period,("E","F","G")),
   ("edition_comparison",comparison,comparison_period,("B","C","D"))):
   triple=[numeric(c.get(letter+str(row),"")) for letter in base]
   if triple[0] is not None and triple[1] is not None and triple[2] is not None:
    difference=triple[0]+triple[1]-triple[2]
    if abs(difference)>Decimal("0.01"):
     differences.append({"sheet":sheet,"row":row,"label":rawlabel,"year":period_year,
       "period":period_name,"difference_t":str(difference),"position":position})
   for operation,letter,val in zip(COLS,base,triple):
    if val is None:continue
    entry=dict(source_set_id="F09",producer="APDL",edition=edition,
     source_release=RELEASE,source_asset=name,source_sha256=sha,source_sheet=sheet,
     source_row=row,source_cell=letter+str(row),source_label=rawlabel,
     source_row_role=role,cargo_group=group if family=="nature" else "",
     cargo_nature=nature,od_zone=zone if family=="geography" and row!=29 else "",
     od_class=odclass,od_scope=odscope,reference_year=period_year,
     period=period_name,edition_position=position,operation=operation,unit="t",
     value=str(val),status="producer_value")
    records.append(entry)
    if role=="overall_total":totals[position+":"+operation]=str(val)
 dest=folder/(f"F09-{family}-{edition}.csv")
 with dest.open("w",newline="",encoding="utf-8") as fout:
  w=csv.DictWriter(fout,fieldnames=FIELDS);w.writeheader();w.writerows(records)
 return {"file":dest.name,"source":name,"source_sha256":sha,"period":period,
   "family":family,"edition":edition,"rows":len(records),"overall_totals_t":totals,
   "row_balance_exceptions":differences,"bytes":dest.stat().st_size,
   "csv_sha256":hashlib.sha256(dest.read_bytes()).hexdigest()}

def main():
 folder=Path(sys.argv[1]) if len(sys.argv)>1 else Path(".")
 outputs=[normalise(cfg,folder) for cfg in FILES]
 bykey={(r["family"],r["edition"]):r for r in outputs}
 qa=[]
 for edition in ("annual_2025","sept_2026"):
  x=bykey[("nature",edition)]["overall_totals_t"]
  y=bykey[("geography",edition)]["overall_totals_t"]
  for position in ("current","edition_comparison"):
   delta=Decimal(x[position+":total"])-Decimal(y[position+":total"])
   qa.append({"edition":edition,"position":position,"nature_minus_geography_t":str(delta),
    "same_total":delta==0})
 if Decimal(bykey[("nature","annual_2025")]["overall_totals_t"]["current:total"])!=Decimal("13990733.143"):
  raise ValueError("2025 source total differs from F09 validated general-movement baseline")
 if Decimal(bykey[("geography","annual_2025")]["overall_totals_t"]["current:total"])!=Decimal("13990733.143"):
  raise ValueError("2025 geographical source total differs from F09 baseline")
 status="NORMALIZED_WITH_SOURCE_DISCREPANCIES_PENDING_INDEPENDENT_QA"
 manifest={"schema_version":"1.0.0","source_set_id":"F09",
   "publication":"PRIVATE_INTERNAL_ONLY","canonical_admission":"PENDING_W3A_AND_W1B",
   "status":status,"release":RELEASE,
   "reader_guidance":"Read only edition_position=current to avoid double-counting comparison columns. Filter by period/year. Do not sum subtotals and leaf rows. Maritime/declared APDL zones are not final economic markets or terrestrial hinterland.",
   "datasets":outputs,"cross_book_qa":qa,
   "methodology":["Source native units t; no tonne-thousands scaling.","Original producer cells, labels, editions and SHA-256 preserved.","All numeric cells B:G as source views, with current and comparison periods distinct.","H:J percentage variation excluded as derived displayed ratio, not an observation.","Zeros preserved; -, blank and spreadsheet errors not interpreted as zero.","No NUTS III, commercial final market or origin/destination port inferred."],
   "known_limitations":["2026 September totals differ between native tables and rowwise arithmetic. Preserved as reported.","2024 comparison values in 2025 editions differ from earlier general movement source; retain all edition identities.","2026 native label N/A and row order changes prohibit positional mapping to 2025 cargo names.","Cross-producer AMT F08 cargo totals differ from APDL F09 and require a separate reconciliation."]}
 (folder/"F09-normalized-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"status":status,"products":len(outputs),"rows":sum(x["rows"] for x in outputs),
   "exceptions":sum(len(x["row_balance_exceptions"]) for x in outputs),"cross_book_qa":qa},ensure_ascii=False))
if __name__=="__main__":main()
