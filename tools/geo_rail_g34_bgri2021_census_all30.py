#!/usr/bin/env python3
"""G34 genuine original INE 2021 BGRI resident geography for ALL 30 G10+G30.

5/10 km geographic sensitivity circles of G33 closest GRID study points.
NOT road or public transport isochrones, stations, current population, demand.
Union 10km avoids multiple counts along a single corridor; no station constructability.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sqlite3,tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point
from shapely.ops import unary_union
from pyproj import Transformer
from geo_rail_g14_bgri2021_station_population import F67_SHA,F67_BYTES,unpack_exact,native_qa,catchment
TO_PT=Transformer.from_crs(4326,3763,always_xy=True)
CITY=("Guimaraes","Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca")
RADII=(5000,10000)
def validate(j):
    rows=j.get("six_city_all_180_records",[])
    if not (j.get("mission")=="MN-GEO-RAIL-001" and j.get("G10")==27 and j.get("G30")==3
            and len(rows)==180 and len(j.get("road_network_source_receipts",[]))==6
            and j.get("PIC_UNRESOLVED") and j.get("new_DGT_tiles")==0
            and j.get("no_Fxx_or_site")):
        raise ValueError("G34_G33_original_30x6_road_and_PIC_scope_required")
    ids={r["option_id"] for r in rows}
    if len(ids)!=30 or len([k for k in ids if k.startswith("G30-")])!=3:
        raise ValueError("G34_G33_options_not_30")
    if len({(r["option_id"],r["urban_key"]) for r in rows})!=180:
        raise ValueError("G34_G33_unrepeated_six_cities")
    if any({r["urban_key"] for r in rows if r["option_id"]==k}!=set(CITY) for k in ids):
        raise ValueError("G34_six_city_missing")
    if any(r["2021_population_with_real_network_catchment"] is not None for r in rows):
        raise ValueError("G34_old_census_not_uniform_must_stay_null")
    return rows
def source_census_record(d):
    return {"residents_2021_representative_subsection":d["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
            "residents_2021_area_weighted_uniform_subsection_sensitivity":d["area_weighted_uniform_within_subsection_population_estimates"]["N_INDIVIDUOS"],
            "residents_2021_65plus_representative_subsection":d["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS_65_OU_MAIS"],
            "intersected_original_subsections":d["original_subsections_intersecting_area"],
            "missing_census_field_observations_not_imputed":d["missing_census_field_observations"],
            "source_geometry_invalid_skipped":d["invalid_original_geometries_skipped"]}
def exercise(src,archive,jpath,csvpath,mdpath,heatpath,barpath):
    rows=validate(src)
    known={}
    for row in rows:
        key=tuple(row["nearest_2km_lattice_point_WGS84"])
        if len(key)!=2 or any(not math.isfinite(v) for v in key):
            raise ValueError("G34_G33_points_invalid")
        known.setdefault(key,[]).append(row)
    projected={point:Point(*TO_PT.transform(*point)) for point in known}
    n=0
    output=[];unions=[]
    with tempfile.TemporaryDirectory(prefix="MN-G34-BGRI2021-") as tmp:
        native=unpack_exact(archive,Path(tmp))
        db=sqlite3.connect(f"file:{native}?mode=ro",uri=True,timeout=45)
        try:
            qa=native_qa(db)
            census={}
            for point,origin in projected.items():
                for rad in RADII:
                    original=catchment(db,origin.buffer(rad,quad_segs=24),qa["rtree"])
                    census[(point,rad)]=source_census_record(original)
                n+=1
                print("G34 census unique research reference",n,"/",len(projected),flush=True)
            per_option=defaultdict(dict)
            for row in rows:
                key=tuple(row["nearest_2km_lattice_point_WGS84"])
                result={"option_id":row["option_id"],"source_family":row["source_family"],
                  "urban_key":row["urban_key"],"urban_market":row["urban_market"],
                  "mandatory_urban_market":row["mandatory_market"],
                  "study_grid_reference_point_WGS84":list(key),
                  "urban_reference_to_grid_straight_km_not_station":row["nearest_source_research_grid_direct_distance_km"],
                  "same_run_OSRM_drive_min_to_road_snapped_grid_not_station":row["road_drive_minutes_to_snapped_grid_road_not_station"],
                  "same_run_OSRM_status":row["road_status"],
                  "2021_residents_not_rail_passenger_demand":True,
                  "circular_radius_is_geographic_NOT_road_isochrone":True,
                  "source_original_INE_BRGI2021_correct_year":2021,
                  "not_a_station_or_catchment_to_approved_station":True,
                  "geographic_circle_5km":census[(key,5000)],
                  "geographic_circle_10km":census[(key,10000)]}
                output.append(result)
                per_option[row["option_id"]][row["urban_key"]]=projected[key]
            if len(output)!=180:raise ValueError("G34_180_census_market_cases_missing")
            for k,ptby in sorted(per_option.items()):
                if set(ptby)!=set(CITY):raise ValueError("G34_6_reference_points_missing")
                unique=sorted({(round(pt.x,3),round(pt.y,3)) for pt in ptby.values()})
                # Geometries for each city union; sum over each buffer is WRONG
                # when overlapping. Use exact polygon union plus census one time.
                circle=unary_union([Point(x,y).buffer(10000,quad_segs=24) for x,y in unique])
                actual=catchment(db,circle,qa["rtree"])
                unions.append({"option_id":k,"source_family":"G30" if k.startswith("G30-") else "G10",
                    "city_market_reference_points":len(ptby),"unique_geographic_points":len(unique),
                    "union_radius_geographic_km":10,
                    "2021_residents_in_unduplicated_union_of_six_10km_study_circles":source_census_record(actual),
                    "not_all_residents_access_rail_or_road_or_station":True})
                print("G34 union market research",len(unions),"/30",k,flush=True)
        finally:db.close()
    if len(unions)!=30:raise ValueError("G34_30_exact_overlap_free_unions_required")
    doc={"mission":"MN-GEO-RAIL-001",
      "stage":"G34_all30_2021_official_INE_BRGI2021_station_grid_geographic_population",
      "source_G33_sha256":hashlib.sha256(json.dumps(src,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
      "native_original_INE_2021_F67_zip_sha256":F67_SHA,
      "native_original_INE_2021_original_zip_bytes":F67_BYTES,
      "original_gpkg_qa":qa,
      "city_points_unique":len(projected),
      "original_census_spatial_queries_unique_points_radius":len(projected)*len(RADII),
      "original_census_unduplicated_corridor_service_envelopes":30,
      "all30_same_method":True,"G10_count":27,"G30_count":3,
      "30_times_six_city_study_geographic_census_cases":len(output),
      "5_and_10km_geographic_circles_NOT_true_road_public_transport_station_isochrones":True,
      "not_station_rail_ridership_mobility_poverty_or_2026_population":True,
      "mandatory_Vila_Real_and_Braganca_reference_fixed_across_30_by_G10_grid":True,
      "2021_population_not_2026_actual":True,"no_new_INE_original_producer_acquisition":True,
      "new_DGT_tiles":0,"PIC_UNRESOLVED":True,
      "no_Fxx_or_site":True,
      "market_cases":output,"corridor_six_city_radius10km_unions_no_overlap_duplication":unions}
    jpath.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n")
    with csvpath.open("w",newline="",encoding="utf-8-sig") as f:
        cols=("option_id","source_family","urban_market","mandatory_urban_market",
              "urban_reference_to_grid_straight_km_not_station",
              "same_run_OSRM_drive_min_to_road_snapped_grid_not_station",
              "population_2021_5km_representative",
              "population_2021_10km_representative",
              "population_2021_10km_area_weighted",
              "age65_2021_10km_representative")
        w=csv.DictWriter(f,fieldnames=cols,delimiter=";")
        w.writeheader()
        for r in output:
            w.writerow({"option_id":r["option_id"],"source_family":r["source_family"],
                "urban_market":r["urban_market"],"mandatory_urban_market":r["mandatory_urban_market"],
                "urban_reference_to_grid_straight_km_not_station":r["urban_reference_to_grid_straight_km_not_station"],
                "same_run_OSRM_drive_min_to_road_snapped_grid_not_station":r["same_run_OSRM_drive_min_to_road_snapped_grid_not_station"],
                "population_2021_5km_representative":r["geographic_circle_5km"]["residents_2021_representative_subsection"],
                "population_2021_10km_representative":r["geographic_circle_10km"]["residents_2021_representative_subsection"],
                "population_2021_10km_area_weighted":r["geographic_circle_10km"]["residents_2021_area_weighted_uniform_subsection_sensitivity"],
                "age65_2021_10km_representative":r["geographic_circle_10km"]["residents_2021_65plus_representative_subsection"]})
    items=sorted({r["option_id"] for r in output},key=lambda x:(x.startswith("G30-"),x))
    arr=np.zeros((30,6),float)
    look={(r["option_id"],r["urban_key"]):r for r in output}
    for i,opt in enumerate(items):
        for j,city in enumerate(CITY):
            arr[i,j]=look[opt,city]["geographic_circle_10km"]["residents_2021_representative_subsection"]
    fig,ax=plt.subplots(figsize=(11.7,14.0),layout="constrained")
    image=ax.imshow(arr,cmap="viridis",aspect="auto")
    ax.set_xticks(range(6),["Guimarães","Amarante","Vila Real*","Mirandela","Macedo de Cavaleiros","Bragança*"],
                  rotation=28,ha="right",fontsize=8)
    ax.set_yticks(range(30),items,fontsize=8)
    ax.axhline(26.5,color="white",lw=2)
    ax.set_title("G34 · INE Censos 2021: residentes em raio geográfico de 10 km da malha (não isócrona nem estação)",loc="left",fontsize=11)
    fig.colorbar(image,ax=ax,label="Residentes 2021 por subsecção representativa (geográfico, não procura)")
    fig.savefig(heatpath,dpi=155,bbox_inches="tight");plt.close(fig)
    unions_by={x["option_id"]:x["2021_residents_in_unduplicated_union_of_six_10km_study_circles"]["residents_2021_representative_subsection"] for x in unions}
    fig,ax=plt.subplots(figsize=(12.,10.),layout="constrained")
    ys=np.arange(len(items))
    bars=[unions_by[k] for k in items]
    ax.barh(ys,bars,color=["#728aa3" if not k.startswith("G30-") else "#cb814e" for k in items])
    ax.set_yticks(ys,items,fontsize=8);ax.invert_yaxis()
    ax.set_xlabel("Residentes 2021 na união de seis círculos geográficos de 10km, sem dupla contagem\nNÃO é procura, tempo de acesso nem área efetiva de estação")
    ax.set_title("G34 · Mercado geográfico demográfico de estudo — 30 alternativas comparáveis",loc="left")
    ax.grid(axis="x",alpha=.17)
    fig.savefig(barpath,dpi=155,bbox_inches="tight");plt.close(fig)
    lines=["# G34 — Comparação INE BGRI2021 de TODAS as 30 alternativas, sem imputação",
       "","Censos **2021**, geometria de subsecção INE BGRI21_CONT original F67 (203264 registos), reutilizada a partir da release já preservada no GitHub e validada por SHA256. Inclui três variantes G30 e 27 alternativas G10, seis cidades por alternativa, círculos geográficos de 5 e 10 km em volta de **pontos de grelha**, não estações.",
       "","As medições representam **residentes historicamente localizados** em círculos de distância em linha reta; não implicam tempos de automóvel, transporte público, qualidade da via, utilização de comboio ou localização viável de uma estação. Não são estimativas de população para 2026.",
       "","## Quadro integral de residentes de 2021 no círculo geográfico de 10 km (subsecção representativa)",
       "","| Alternativa | Guimarães | Amarante | Vila Real* | Mirandela | Macedo | Bragança* | União sem duplicar seis círculos |",
       "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for option in items:
        v=[str(look[option,c]["geographic_circle_10km"]["residents_2021_representative_subsection"]) for c in CITY]
        lines.append("| "+option+" | "+" | ".join(v)+" | "+str(unions_by[option])+" |")
    lines+=["","*Vila Real e Bragança são obrigatórias, mas o ponto exploratório da malha é partilhado entre os 30 corredores. Assim, o indicador demográfico nessas duas cidades é igual por construção, e não demonstra equivalência entre alternativas de estação.*",
      "","A coluna de **união** foi calculada a partir de polígonos da união dos seis círculos por alternativa, confrontados uma única vez com as geometrias originais INE, evitando somar subsecções sobrepostas.",
      "","As contagens de população em subsecções parcialmente cruzadas também têm estimativa ponderada por área como sensibilidade, que assume distribuição residencial homogénea e não deve ser tomada como contagem censitária observada por fração.",
      "","## Lacunas para avaliação efetiva do serviço ferroviário",
      "1. Validar e diversificar localizações de estação e engenharia 3D, em especial nos dois nós obrigatórios, sem forçar localização central.",
      "2. Gerar isócronas rodoviárias e de transporte público **comparáveis a partir das futuras estações**, com frequências e conectividade, em vez de círculos geográficos.",
      "3. Calibrar eventual procura com pares OD, motivos de deslocação, rendimento e concorrência intermodal; não converter diretamente população em passageiros.",
      "4. Integrar a carteira completa G32 com custos, travessia Marão/Alvão e outras áreas Natura, PIC e engenharia 160/200/250; não antecipar shortlist com pesos arbitrários.",
      "","**Sem nova aquisição externa INE, DGT ou MITECO. Sem Fxx/Site.**"]
    mdpath.write_text("\n".join(lines)+"\n")
    print("G34_RESULT",json.dumps({"unique_points":len(projected),"source_F67_SHA":F67_SHA,
      "city_cases":len(output),"union_cases":len(unions),
      "union_range_residents_2021":[min(bars),max(bars)],
      "g30_union_residents_2021":{k:unions_by[k] for k in items if k.startswith("G30-")},
      "missing_census_fields":sum(x["geographic_circle_10km"]["missing_census_field_observations_not_imputed"] for x in output)},ensure_ascii=False))
def main():
    a=argparse.ArgumentParser()
    for k in ("g33","f67","json","csv","markdown","heatmap","bars"):
        a.add_argument("--"+k,required=True,type=Path)
    p=a.parse_args()
    exercise(json.loads(p.g33.read_text()),p.f67,p.json,p.csv,p.markdown,p.heatmap,p.bars)
if __name__=="__main__":main()
