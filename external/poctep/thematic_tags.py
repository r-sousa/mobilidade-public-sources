#!/usr/bin/env python3
"""Curated thematic POCTEP views. Derived only from the official approved register.
Flags are NON-EXCLUSIVE; do not add subtotals together.
Energy core follows POCTEP OE 2.1/2.2 + P3; supplementary energy is reviewed by title.
Climate-plan flags identify direct plans/strategies or their operational tools,
not all climate-related projects. Source master: external/poctep/data/projects.csv.
"""
import csv,json
from pathlib import Path
from decimal import Decimal
ROOT=Path("external/poctep/data")
COMMUNITY={
"0052_COMENERG_1_E","0053_ALDEALIX_1_E","0081_CEL_RURAL_6_E",
"0184_ENERZAB_2_P","0198_TRANSCOM_EUROACE_4_E","0408_ENECORE_6_E"}
AUX_ENERGY={
"0091_AGERAR_PLUS_6_E","0093_AIHRE_6_E","0314_GREENER_5_E",
"0409_INERH2_6_E","0499_AIRES_4_E"}
CLIMATE_PLAN={
"0027_ADAPT_CLIMA_CENCYL_3_E","0031_RISC_PLUS_6_E",
"0177_EUROCIDADE_CT_ADAPT_1_P","0349_ACLIMA_URBAN_CENCYL_3_E",
"0476_ENE_RURAL_MUNICIPALITIES_2_E"}
CLIMATE_ENERGY_MODEL={"0186_FRONTEIRA_HUELLA_ZERO_2030_3_E",
"0582_FRONTEIRA_HUELLA_ZERO_2030_II_3_E"}
ALIASES={
"0052_COMENERG_1_E":"PV collective self-consumption; three local energy-community pilots",
"0053_ALDEALIX_1_E":"Biomass district heat and photovoltaics in rural energy communities",
"0081_CEL_RURAL_6_E":"Local rural energy-community pilots across POCTEP",
"0184_ENERZAB_2_P":"Renewable energy communities in Bragança and Zamora",
"0198_TRANSCOM_EUROACE_4_E":"Cross-border community energy advisory network and pilots",
"0408_ENECORE_6_E":"Shared rural energy pilots and energy-poverty action",
"0027_ADAPT_CLIMA_CENCYL_3_E":"City-level adaptation measures and resilience strategies",
"0031_RISC_PLUS_6_E":"Joint drought and cross-border river-basin planning",
"0177_EUROCIDADE_CT_ADAPT_1_P":"Joint climate adaptation strategy for Cerveira–Tomiño",
"0349_ACLIMA_URBAN_CENCYL_3_E":"Joint climate-action guidelines building on municipal climate plans",
"0476_ENE_RURAL_MUNICIPALITIES_2_E":"Local climate and energy plans for rural municipalities",
"0186_FRONTEIRA_HUELLA_ZERO_2030_3_E":"Integrated climate and energy model (phase I)",
"0582_FRONTEIRA_HUELLA_ZERO_2030_II_3_E":"Integrated climate and energy model (phase II)"}
def write(name,rows):
    path=ROOT/name
    cols=["project_code","project_title","cooperation_area","area_code","call_group",
          "priority","specific_objective","approved_erdf_eur","eligible_cost_eur_available",
          "energy_community","energy_core","energy_supplementary",
          "climate_adaptation","climate_plan_or_strategy","integrated_climate_energy_model",
          "classification_note"]
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        writer.writeheader()
        for x in rows:writer.writerow(x)
def main():
    with (ROOT/"projects.csv").open(newline="",encoding="utf-8-sig") as f:
        original=list(csv.DictReader(f))
    if len(original)!=259:raise RuntimeError("Official 259-project baseline changed: review taxonomy before release.")
    ids={x["project_code"] for x in original}
    if any(x not in ids for x in COMMUNITY|AUX_ENERGY|CLIMATE_PLAN|CLIMATE_ENERGY_MODEL):
        raise RuntimeError("Curated thematic code missing from approved inventory.")
    data=[]
    for x in original:
        k=x["project_code"]
        y=dict(x)
        energy_core=x["priority"]=="P3" and x["specific_objective"] in ("2.1","2.2")
        y.update(energy_community=int(k in COMMUNITY),
                 energy_core=int(energy_core),
                 energy_supplementary=int(k in AUX_ENERGY),
                 climate_adaptation=int(x["priority"]=="P3" and x["specific_objective"]=="2.4"),
                 climate_plan_or_strategy=int(k in CLIMATE_PLAN),
                 integrated_climate_energy_model=int(k in CLIMATE_ENERGY_MODEL),
                 classification_note=ALIASES.get(k,""))
        data.append(y)
    views={
        "thematic_energy_projects.csv":lambda r:r["energy_core"] or r["energy_supplementary"],
        "thematic_energy_communities.csv":lambda r:r["energy_community"],
        "thematic_climate_adaptation.csv":lambda r:r["climate_adaptation"],
        "thematic_climate_plans.csv":lambda r:r["climate_plan_or_strategy"],
        "thematic_climate_energy_models.csv":lambda r:r["integrated_climate_energy_model"]}
    stats={}
    for filename,pred in views.items():
        group=[x for x in data if pred(x)]
        write(filename,group)
        stats[filename]={"projects":len(group),"erdf_eur":f"{sum(Decimal(x['approved_erdf_eur']) for x in group):.2f}"}
    write("thematic_all_flags.csv",data)
    (ROOT/"thematic_quality.json").write_text(json.dumps({
      "base_project_count":len(original),"view_stats":stats,"non_exclusive_flags":True,
      "energy_core_rule":"P3 + OE 2.1/2.2","energy_supplementary_codes":sorted(AUX_ENERGY),
      "community_codes":sorted(COMMUNITY),"climate_plan_codes":sorted(CLIMATE_PLAN),
      "notes":["Climate plans are a curated strict shortlist, not all projects with climate content.",
      "An official webpage may occasionally disagree with the Excel workbook on a project's priority; the register retains workbook values and flags such discrepancies for manual source verification.",
      "Funds are project-wide approved ERDF, not territory-specific expenditure.",
      "Prior programme calls 9 and 10 are not yet included."],
      "sources":["https://www.poctep.eu/en/operations-partners-list/"]
    },indent=2,ensure_ascii=False),encoding="utf-8")
    legend={
    "thematic_energy_projects.csv":"All 21 P3 OE2.1/2.2 energy projects plus 5 reviewed energy R&D/skills projects (26 total)",
    "thematic_energy_communities.csv":"6 directly focused on energy communities or energy-sharing pilots",
    "thematic_climate_adaptation.csv":"P3 OE2.4 climate adaptation, disaster risk and resilience (not the same as climate planning)",
    "thematic_climate_plans.csv":"5 reviewed projects with explicit planning, local strategies or municipal action guidelines",
    "thematic_climate_energy_models.csv":"2 integrated local climate-energy development models (Huella Zero I and II)",
    "thematic_all_flags.csv":"Master 259 operations with all overlapping flags"}
    text=["# POCTEP 2021–2027: energy and climate thematic register",
    "Based on the official approved operations and partners lists.",
    "## Derived extracts (overlapping categories; never sum them as distinct projects)",
    "| File | Scope | Projects | ERDF approved (EUR) |",
    "|---|---|---:|---:|"]
    for name,v in stats.items():
        text.append(f"| [{name}]({name}) | {legend[name]} | {v['projects']} | {v['erdf_eur']} |")
    text+=["","## Source and interpretation","- Parent inventory: [projects.csv](projects.csv), [partners.csv](partners.csv), and [quality.json](quality.json).",
    "- Territories are programme cooperation areas; partner-level NUTS mapping must be validated separately.",
    "- 'Energy communities' is a subset of energy projects. Climate plans, adaptation and energy may overlap.",
    "- Eligible project investment is not systematically available for calls 6–8. Use project ERDF unless checked separately.",
    "- Recomputed automatically when the source registry refreshes. Taxonomy code is versioned in the public repository." ]
    (ROOT/"THEMATIC_ENERGY_CLIMATE.md").write_text("\n".join(text)+"\n",encoding="utf-8")
    print("THEMATIC_QA",stats,flush=True)
if __name__=="__main__":main()
