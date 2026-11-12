#!/usr/bin/env python3
"""Normalize POCTEP official partner records without double-counting project totals.
Run after poctep_inventory.py. Uses only the source files downloaded by that step.
"""
import csv, json, re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path("external/poctep/data")
SOURCE = ROOT / "source"
EXPECT = {"calls_1_5":144, "call_6":94, "call_7":6, "call_8":15}
FILES = {k:SOURCE/(k+"_sheet1.csv") for k in EXPECT}
CODE = re.compile(r"^\d{3,5}_[A-Za-z0-9_-]+_[1-8]_[A-Za-z]$")
REGIONS = {"1":"Galiza / Norte de Portugal",
           "2":"Norte de Portugal / Castilla y León",
           "3":"Centro de Portugal / Castilla y León",
           "4":"Centro / Alentejo / Extremadura",
           "5":"Alentejo / Algarve / Andalucía",
           "6":"Plurirregional"}
PRIORITY = {"P1":"Empresas, digitalização e I&D",
            "P2":"Recursos endógenos",
            "P3":"Transição ecológica",
            "P4":"Biodiversidade",
            "P5":"Desafio demográfico",
            "P6":"Desenvolvimento territorial integrado",
            "P7":"Governação e cooperação"}
SCHEMA = {
  "calls_1_5": dict(code=2, title=3, area=5, start=6, end=7, country=8, beneficiary=9, role=10,
                   op=11, priority=12, oe=13, scope=14, cost=15, rate=16, erdf=17, call=0),
  "call_6": dict(code=0, title=1, area=2, priority=3, oe=4, op=5, role=6, beneficiary=7, erdf=8),
  "call_7": dict(code=0, title=1, area=2, priority=3, oe=4, op=5, role=6, beneficiary=7, erdf=8),
  "call_8": dict(code=0, title=1, area=2, priority=3, oe=4, op=5, role=6, beneficiary=7, erdf=9, nature=8)
}

def get(row, schema, name):
    i = schema.get(name)
    return str(row[i]).strip() if i is not None and i < len(row) else ""

def amount(s):
    if not s or str(s).strip() in ("-", "–", "n/a", "N/A"): return None
    s = str(s).strip().replace("\u00a0", "").replace("€", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        p = s.split(",")
        s = s.replace(",", ".") if len(p[-1]) in (1,2) else s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def string_amount(v):
    return f"{v:.2f}" if v is not None else ""

def read_file(path):
    with path.open("r", encoding="utf-8-sig", newline="") as h:
        return list(csv.reader(h))

def write_csv(path, header, data):
    with path.open("w", encoding="utf-8-sig", newline="") as h:
        w=csv.writer(h); w.writerow(header); w.writerows(data)

def clean_oe(raw):
    try:
        x=float(raw)
        if 0 <= x < 10: return f"{x:.1f}"
    except (ValueError, TypeError): pass
    return raw

def choose(old, new):
    return old or new or ""

def main():
    quality=json.loads((ROOT/"quality.json").read_text(encoding="utf-8"))
    projects={}
    partners=[]
    diagnostics=[]
    for source, path in FILES.items():
        rows=read_file(path)
        s=SCHEMA[source]
        last_code=""
        local=set()
        rejected=[]
        for i,row in enumerate(rows[1:], start=2):
            val=get(row,s,"code")
            if val.lower().startswith("total ") or val.upper().startswith("TOTAL"):
                last_code=""
                continue
            code=val.upper() if CODE.fullmatch(val) else ""
            if code: last_code=code
            if not code: code=last_code
            ben=get(row,s,"beneficiary")
            role=get(row,s,"role").upper()
            if not code or not CODE.fullmatch(code) or not ben or (source != "calls_1_5" and role not in ("BP","BE","SO")):
                if val and not CODE.fullmatch(val) and not val.lower().startswith("total "):
                    rejected.append((i,val[:100],role,ben[:60]))
                continue
            local.add(code)
            p=projects.setdefault(code,dict(project_code=code,call_group=source,
                          call_number="",title="",area_code="",area="",priority="",priority_label="",
                          oe="",op="",start="",end="",partner_count=0,erdf=Decimal(0),
                          erdf_rows=0,cost=Decimal(0),cost_rows=0,source_count=0))
            if p["call_group"] != source:
                diagnostics.append("Duplicated project code across calls: "+code)
            p["title"]=choose(p["title"],get(row,s,"title"))
            area_raw=get(row,s,"area")
            ar=re.match(r"^\s*([1-6])\b",area_raw)
            area=ar.group(1) if ar else ""
            if not area:
                tail=re.search(r"_([1-6])_[A-Za-z]$",code)
                area=tail.group(1) if tail else ""
            p["area_code"]=choose(p["area_code"],area)
            p["area"]=REGIONS.get(p["area_code"],area_raw)
            pr=get(row,s,"priority").upper().replace(" ","")
            if pr in PRIORITY:
                p["priority"]=choose(p["priority"],pr)
            elif pr.isdigit() and pr in "1234567":
                p["priority"]=choose(p["priority"],"P"+pr)
            p["priority_label"]=PRIORITY.get(p["priority"],"")
            p["oe"]=choose(p["oe"],clean_oe(get(row,s,"oe")))
            p["op"]=choose(p["op"],get(row,s,"op"))
            p["start"]=choose(p["start"],get(row,s,"start"))
            p["end"]=choose(p["end"],get(row,s,"end"))
            p["call_number"]=choose(p["call_number"],get(row,s,"call"))
            erdf=amount(get(row,s,"erdf")); cost=amount(get(row,s,"cost"))
            if erdf is not None:
                p["erdf"]+=erdf; p["erdf_rows"]+=1
            if cost is not None:
                p["cost"]+=cost; p["cost_rows"]+=1
            p["source_count"]+=1
            partners.append([code, source, get(row,s,"beneficiary"),role,
                             get(row,s,"country"), get(row,s,"nature"),
                             string_amount(erdf),string_amount(cost),get(row,s,"rate"),
                             p["area_code"],p["priority"],i])
        diagnostics.append({"source":source,"role_examples":sorted({get(r,s,"role") for r in rows[1:100] if get(r,s,"role")})[:15], "strict_projects":len(local),"expected":EXPECT[source],
                            "strict_partner_rows":sum(x[1]==source for x in partners),
                            "rejected_nonempty_code_examples":rejected[:8]})
    ph=["project_code","call_group","call_number","project_title","area_code","cooperation_area",
        "priority","priority_description","specific_objective","political_objective",
        "start_date","end_date","partner_rows","approved_erdf_eur",
        "eligible_cost_eur_available","erdf_rows","eligible_cost_rows","source_rows"]
    output=[]
    for p in sorted(projects.values(),key=lambda x:x["project_code"]):
        output.append([p["project_code"],p["call_group"],p["call_number"],p["title"],
                       p["area_code"],p["area"],p["priority"],p["priority_label"],
                       p["oe"],p["op"],p["start"],p["end"],p["source_count"],
                       string_amount(p["erdf"]) if p["erdf_rows"] else "",
                       string_amount(p["cost"]) if p["cost_rows"] else "",
                       p["erdf_rows"],p["cost_rows"],p["source_count"]])
    write_csv(ROOT/"projects.csv",ph,output)
    write_csv(ROOT/"partners.csv",
              ["project_code","call_group","partner_name","partner_role","country_source",
               "partner_nature","partner_approved_erdf_eur","partner_eligible_cost_eur",
               "cofinancing_rate_source","area_code","priority","source_row"],
              partners)
    def group(keys):
        d=defaultdict(list)
        for p in projects.values():
            d[tuple(p[k] for k in keys)].append(p)
        header=keys+["projects","approved_erdf_eur","projects_with_erdf",
                     "eligible_cost_eur_recorded","projects_with_eligible_cost"]
        out=[]
        for k,v in sorted(d.items()):
            erdf=sum((x["erdf"] for x in v if x["erdf_rows"]),Decimal(0))
            cost=sum((x["cost"] for x in v if x["cost_rows"]),Decimal(0))
            out.append(list(k)+[len(v),string_amount(erdf),
                         sum(bool(x["erdf_rows"]) for x in v),
                         string_amount(cost) if any(x["cost_rows"] for x in v) else "",
                         sum(bool(x["cost_rows"]) for x in v)])
        return header,out
    for name,fields in [("by_call",["call_group"]),("by_area",["area_code","area"]),
                        ("by_priority",["priority","priority_label"]),
                        ("by_area_priority",["area_code","priority"])]:
        h,d=group(fields)
        write_csv(ROOT/("summary_"+name+".csv"),h,d)
    actual={s:sum(p["call_group"]==s for p in projects.values()) for s in EXPECT}
    total_erdf=sum((p["erdf"] for p in projects.values() if p["erdf_rows"]),Decimal(0))
    known_cost=sum((p["cost"] for p in projects.values() if p["cost_rows"]),Decimal(0))
    partner_erdf_missing=sum(p["erdf_rows"]==0 for p in projects.values())
    match=actual==EXPECT
    status="validated_project_identifiers" if match else "review_required"
    quality.update({"normalized_at_utc":datetime.now(timezone.utc).isoformat(),
                    "strict_unique_projects":len(projects),
                    "strict_by_call":actual,
                    "strict_match_official_by_call":match,
                    "strict_partner_records":len(partners),
                    "total_approved_erdf_eur_from_partner_records":string_amount(total_erdf),
                    "available_eligible_cost_eur_only_sources_with_explicit_field":string_amount(known_cost),
                    "projects_missing_erdf":partner_erdf_missing,
                    "normalised_register_status":status,
                    "normalisation_diagnostics":diagnostics,
                    "financial_caution":"ERDF is summed only once per beneficiary row. Eligible total cost is published in the first five call workbook but not in the 6th-8th call workbooks. Do not infer missing investment by dividing ERDF by a maximum cofinancing rate; partial eligible-cost totals cannot describe the entire programme."})
    (ROOT/"quality.json").write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding="utf-8")
    def table(path):
        rows=read_file(path)
        return "\n".join("| "+" | ".join(r)+" |" for r in rows[:25])
    summary=f"""# POCTEP 2021–2027 — approved operations and beneficiaries

Updated from official source {quality['normalized_at_utc']}.

## Coverage and validity

- Official published approved operations: **259** (calls 1–8).
- Operations with distinct identifiers in the source workbooks: **{len(projects)}**.
- Partner/beneficiary records extracted: **{len(partners)}**.
- Source counts: {actual}. Official reference counts: {EXPECT}.
- Verification: **{status}**.
- ERDF summed across beneficiary records: **€{total_erdf:,.2f}** (subject to source revisions and data QA).
- Total eligible expenditure explicitly reported in source subset: **€{known_cost:,.2f}** (NOT the full programme investment).

## By cooperation area

{table(ROOT/'summary_by_area.csv')}

## By thematic priority

{table(ROOT/'summary_by_priority.csv')}

## Methodological limits

- The values of €475 million total investment and €356 million ERDF on the POCTEP homepage are PROGRAMME ALLOCATIONS, not approved-project totals.
- The source for calls 6–8 reports beneficiary ERDF but does not include the beneficiary total eligible cost. Any whole-programme investment estimate requires an additional official financial source.
- Cooperation area is a project-level category. Cross-border projects and pluriregional projects cannot be apportioned to NUTS3 regions without independently verified beneficiary/territorial investment allocations.
- Partner rows with role SO (without funding) remain included; their published ERDF of zero is preserved.
- Files are snapshots of published operations, not evidence of actual disbursements or completed expenditure.

## Traceability

- Source catalogue: https://www.poctep.eu/en/operations-partners-list/
- Original download URLs, SHA-256 and source sheet schemas: \`discovery.json\` and \`quality.json\`.
- Projects: \`projects.csv\`; partner allocations: \`partners.csv\`.
- The historical official workbooks are flattened without suppressing their source data under \`source/\`.
"""
    (ROOT/"SUMMARY.md").write_text(summary,encoding="utf-8")
    print("NORMALIZED_QA", json.dumps({"projects":len(projects),"by_call":actual,"match":match,
                                    "partners":len(partners),"ERDF_eur":str(total_erdf),
                                    "cost_subset_eur":str(known_cost)}),flush=True)
if __name__=="__main__":
    main()
