#!/usr/bin/env python3
"""G33 all 30 G10+G30 six-urban-market city-to-source-grid research screen.

One original G11 method and same-time bounded OSRM demo query per urban market.
Road endpoint is nearest OSM car road to a RESEARCH GRID point, not a built station.
No railway stops, platform, passenger demand, public transport timetable or costs.
"""
from __future__ import annotations
import argparse,csv,datetime,hashlib,json,math,sys,time
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from pyproj import Transformer
from shapely.geometry import Point,LineString
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geo_rail_g11_urban_service import CITY,_read_osrm,OSRM_SNAP_MAX_M,stop_time_cost_bounds
from geo_rail_g32_unified_30_90_comparison import collect
TO_PT=Transformer.from_crs(4326,3763,always_xy=True)
TO_WGS=Transformer.from_crs(3763,4326,always_xy=True)
CITIES=tuple(CITY)
EXTRA=("Guimaraes","Amarante","Mirandela","Macedo_de_Cavaleiros")
MANDATORY=("Vila_Real","Braganca")
MODES={
 "EXP_VR_BR_only":MANDATORY,
 "REG_VR_BR_Amarante_Mirandela_Macedo":("Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca"),
 "REG_VR_BR_Guimaraes_Mirandela_Macedo":("Guimaraes","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca"),
 "REG_all_six":CITIES}
def validate(g10,g30,g30geo,g32):
    entries=collect(g10,g30,g30geo)
    if (g32.get("G10_count")!=27 or g32.get("G30_count")!=3
        or g32.get("total_rows")!=90 or len(g32.get("rows",[]))!=90
        or g32.get("PIC_status")!="UNRESOLVED_MUST_NOT_RANK_AS_LEGALLY_CLEARED"
        or not g32.get("canonical_portfolio_next_stages_all_27_G10_plus_3_G30")):
        raise ValueError("G33_original_G32_source_governance_contract")
    for speed in (160,200,250):
        rows=[v for v in g32["rows"] if v["scenario_speed_kmh"]==speed]
        if len(rows)!=30 or {x["option_id"] for x in rows}!=set(entries):
            raise ValueError("G33_30_options_for_each_speed_required")
    if len(CITIES)!=6 or set(MODES["EXP_VR_BR_only"])!=set(MANDATORY):
        raise ValueError("G33_compulsory_markets_not_preserved")
    if any(not set(MANDATORY).issubset(stop) for stop in MODES.values()):
        raise ValueError("G33_hypothetical_mode_omits_VR_or_BR")
    return entries
def build_refs(entries):
    out=[]
    for route_key,source in entries.items():
        line=LineString([TO_PT.transform(*xy) for xy in source["feat"]["geometry"]["coordinates"]])
        if line.geom_type!="LineString" or line.length<160000:
            raise ValueError("G33_source_lattice_not_a_corridor")
        for citykey,ref in CITY.items():
            city=Point(*TO_PT.transform(ref["lon"],ref["lat"]))
            station_chainage=line.project(city)
            target=line.interpolate(station_chainage)
            lon,lat=TO_WGS.transform(target.x,target.y)
            direct_km=city.distance(target)/1000
            if not math.isfinite(direct_km) or direct_km>200:
                raise ValueError("G33_implausible_urban_grid_distance")
            out.append({
              "option_id":route_key,"source_family":source["family"],
              "urban_market":ref["label"],"urban_key":citykey,"mandatory_market":ref["mandatory"],
              "urban_reference_WGS84":[ref["lon"],ref["lat"]],
              "nearest_2km_lattice_point_WGS84":[round(lon,7),round(lat,7)],
              "nearest_2km_grid_chainage_km_NOT_station":round(station_chainage/1000,3),
              "nearest_source_research_grid_direct_distance_km":round(direct_km,3),
              "grid_proximity_category":("<=3km" if direct_km<=3 else "3-8km" if direct_km<=8
                           else "8-20km" if direct_km<=20 else ">20km"),
              "road_drive_minutes_to_snapped_grid_road_not_station":None,
              "road_drive_km_to_snapped_grid_road_not_station":None,
              "source_city_road_snap_m":None,"target_road_snap_m":None,
              "road_status":"UNMEASURED_OSRM",
              "2021_population_with_real_network_catchment":None,
              "2021_population_gap":"NO_IDENTICAL_BRGI_AND_REAL_ISOCHRONE_FOR_ALL_30",
              "public_transport_travel_time":None,
              "public_transport_gap":"NUTS2_NORTE_NO_UNIFORM_VERIFIED_TIMETABLE",
              "actual_rail_stop_constructable":"UNKNOWN",
              "station_site_land_and_permit":"UNKNOWN",
              "no_railway_station_or_service_or_ridership_demonstrated":True})
    if len(out)!=180 or len({(v["option_id"],v["urban_key"]) for v in out})!=180:
        raise ValueError("G33_not_30_x_six_unique_comparators")
    return out
def route_road(rows,enabled=True):
    receipts=[]
    if not enabled:
        return [{"city":k,"status":"NOT_QUERIED_IN_TEST_MODE","points":0} for k in CITIES]
    for i,key in enumerate(CITIES):
        case=[z for z in rows if z["urban_key"]==key]
        bypoint=defaultdict(list)
        for rec in case:bypoint[tuple(rec["nearest_2km_lattice_point_WGS84"])].append(rec)
        pts=list(bypoint)
        if not 1<=len(pts)<=30:raise ValueError("G33_more_than_30_OSRM_destinations_per_city")
        if i:time.sleep(1.5)
        try:
            answer=_read_osrm(key,pts)
            if len(answer["destinations"])!=len(pts):
                raise ValueError("OSRM_destinations_count_mismatch")
            originvalid=answer["waypoint_source_snap_m"]<=OSRM_SNAP_MAX_M
            for dest,access in zip(pts,answer["destinations"]):
                good=(originvalid and access["snap_distance_m"]<=OSRM_SNAP_MAX_M
                      and access["network_duration_minutes"] is not None
                      and access["network_distance_km"] is not None)
                for row in bypoint[dest]:
                    row["source_city_road_snap_m"]=round(answer["waypoint_source_snap_m"],1)
                    row["target_road_snap_m"]=round(access["snap_distance_m"],1)
                    row["road_status"]="OBSERVED_OSRM_TO_SNAP_NOT_STATION" if good else "OSRM_SNAP_OR_ROUTING_INVALID"
                    if good:
                        row["road_drive_minutes_to_snapped_grid_road_not_station"]=access["network_duration_minutes"]
                        row["road_drive_km_to_snapped_grid_road_not_station"]=access["network_distance_km"]
            receipts.append({"urban_key":key,"status":"SOURCE_NETWORK_OBSERVED_NOT_STATION",
                "source_response_sha256":answer["response_SHA256"],
                "utc":answer["observed_utc"],"city_origin_road_snap_m":answer["waypoint_source_snap_m"],
                "unique_destinations":len(pts),
                "qualified_rows":sum(r["road_drive_minutes_to_snapped_grid_road_not_station"] is not None for r in case),
                "provider":"OSRM OSM public demo, car routing without live traffic"})
        except Exception as exc:
            for row in case:row["road_status"]="OSRM_SOURCE_FAILED_NO_IMPUTATION"
            receipts.append({"urban_key":key,"status":"UNAVAILABLE_NOT_ZERO","error_type":type(exc).__name__,
                             "unique_destinations":len(pts),"qualified_rows":0})
    return receipts
def combine_all(entries,g32,rows):
    pair={(v["option_id"],v["urban_key"]):v for v in rows}
    wide=[];modes=[]
    for option in entries:
        market={city:pair[option,city] for city in CITIES}
        metrics={city:{
          "distance_grid_km_not_station":market[city]["nearest_source_research_grid_direct_distance_km"],
          "road_drive_min_to_road_near_grid_NOT_station":market[city]["road_drive_minutes_to_snapped_grid_road_not_station"],
          "road_status":market[city]["road_status"],
          "station_site_is_not_assessed":True} for city in CITIES}
        # Do not add city accessible population (duplicate and not station).
        for speed in (160,200,250):
            old=next(v for v in g32["rows"] if v["option_id"]==option and v["scenario_speed_kmh"]==speed)
            wide.append({**old,"six_urban_market_research_access_proxies":metrics,
              "mandatory_VR_BR_both_within_8km_source_line":all(
                 market[k]["nearest_source_research_grid_direct_distance_km"]<=8 for k in MANDATORY),
              "optional_markets_within_8km_grid_geometry_not_stop":sum(
                 market[k]["nearest_source_research_grid_direct_distance_km"]<=8 for k in EXTRA),
              "mandatory_both_OSRM_road_targets_valid":all(
                 market[k]["road_drive_minutes_to_snapped_grid_road_not_station"] is not None for k in MANDATORY),
              "full_30_population_road_isochrone_UNAVAILABLE":True,
              "not_approved_stations_or_train_rail_speeds":True})
            for pattern,stops in MODES.items():
                bounds=stop_time_cost_bounds(speed)
                n=len(stops)-2
                modes.append({"option_id":option,"speed_scenario_kmh":speed,
                   "hypothetical_stopping_pattern":pattern,"hypothetical_urban_stops":list(stops),
                   "additional_stops_beyond_obligatory":n,
                   "incremental_stop_motion_plus_dwell_only_min_lower":round(n*bounds["lower_minutes"],2),
                   "incremental_stop_motion_plus_dwell_only_min_upper":round(n*bounds["upper_minutes"],2),
                   "number_of_stop_market_references_within_8km_source_grid":sum(
                       market[k]["nearest_source_research_grid_direct_distance_km"]<=8 for k in stops),
                   "stops_not_confirmed_geometry_and_platform":True,
                   "infrastructure_or_feeder_or_change_of_rail_route_may_be_required":True,
                   "rail_train_running_time_or_demand_estimated":False})
    if len(wide)!=90 or len(modes)!=360:raise ValueError("G33_full_portfolio_service_patterns_incomplete")
    return wide,modes
def figure(rows,which,path):
    by={(r["option_id"],r["urban_key"]):r for r in rows}
    ids=sorted({r["option_id"] for r in rows},key=lambda x:(x.startswith("G30"),x))
    grid=np.full((30,6),np.nan)
    for i,opt in enumerate(ids):
        for j,key in enumerate(CITIES):
            r=by[opt,key]
            val=(r["nearest_source_research_grid_direct_distance_km"] if which=="geographic"
                 else r["road_drive_minutes_to_snapped_grid_road_not_station"])
            if val is not None:grid[i,j]=val
    fig,ax=plt.subplots(figsize=(11.4,13.5),layout="constrained")
    maxv=20 if which=="geographic" else 50
    # Missing values transparent/grey, not zero. Values above vMax saturate, not clip raw matrix.
    cmap=plt.get_cmap("YlOrRd").copy();cmap.set_bad("#dadde1")
    image=ax.imshow(grid,cmap=cmap,vmin=0,vmax=maxv,aspect="auto")
    ax.set_xticks(range(6),[CITY[k]["label"] for k in CITIES],rotation=32,ha="right",fontsize=9)
    ax.set_yticks(range(30),ids,fontsize=8)
    ax.axhline(26.5,c="#1f334c",lw=2)
    for i in range(30):
        for j in range(6):
            val=grid[i,j]
            if not np.isfinite(val):t="N/D"
            else:t=f"{val:.1f}"
            ax.text(j,i,t,ha="center",va="center",fontsize=6.7,
                color="white" if np.isfinite(val) and val>maxv*.68 else "#192b38")
    fig.colorbar(image,ax=ax,shrink=.58,label=("km em linha reta até à malha exploratória (não à estação)"
                                      if which=="geographic" else
                                     "minutos automóvel até à estrada próxima da malha (não estação)"))
    ax.set_title("G33 · 27 G10 + 3 G30 · "+("distância geográfica" if which=="geographic" else "OSRM rodoviário"),
                 loc="left",fontsize=12)
    fig.savefig(path,dpi=160,bbox_inches="tight");plt.close(fig)
def execute(g10,g30,g30geo,g32,source_bytes,report,citycsv,widejson,patternsjson,md,geopng,roadpng,network=True):
    entries=validate(g10,g30,g30geo,g32)
    rows=build_refs(entries)
    receipts=route_road(rows,enabled=network)
    wide,modes=combine_all(entries,g32,rows)
    populations_benchmark={k:None for k in entries}
    out={"mission":"MN-GEO-RAIL-001","stage":"G33_27_G10_plus_3_G30_six_city_equitable_service_road_snap",
         "portfolio_30_in_all_future_assessments":True,
         "source_G32_sha256":hashlib.sha256(source_bytes).hexdigest(),
         "source_30_research_routes":30,"urban_markets_six":list(CITIES),
         "G10":27,"G30":3,"six_city_combinations":len(rows),
         "speed_sensitive_scenario_rows":len(wide),"hypothetical_stopping_patterns":len(modes),
         "source_road_snap_rule_max_m":OSRM_SNAP_MAX_M,
         "road_network_source_receipts":receipts,
         "OSRM_source_actual_queries_max":6 if network else 0,
         "road_only_to_snap_not_real_station":True,
         "population_BRGI2021_available_only_historically_for_three_G14_G17_families_not_uniform_30":True,
         "no_population_or_actual_rail_demand_extrapolation_from_three_to_30":True,
         "NUTS2_Norte_PT_timetable_comparison_not_available_no_imputation":True,
         "new_DGT_tiles":0,"PIC_UNRESOLVED":True,"no_Fxx_or_site":True,
         "six_city_all_180_records":rows}
    report.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    widejson.write_text(json.dumps({"mission":"MN-GEO-RAIL-001","G32_source_sha256":out["source_G32_sha256"],
        "comparable_study_routes":30,"speed_rows":90,"G10":27,"G30":3,
        "no_real_station_or_actual_rail_time":True,"rows":wide},ensure_ascii=False,indent=2)+"\n")
    patternsjson.write_text(json.dumps({"mission":"MN-GEO-RAIL-001",
        "four_hypothetical_stop_patterns":list(MODES),"route_count":30,"scenario_rows":360,
        "2021_resident_market_population_not_uniformly_available_for_all_30":True,
        "not_a_service_timetable":True,"rows":modes},ensure_ascii=False,indent=2)+"\n")
    with citycsv.open("w",newline="",encoding="utf-8-sig") as f:
        cols=("option_id","source_family","urban_market","mandatory_market",
              "nearest_source_research_grid_direct_distance_km",
              "road_drive_minutes_to_snapped_grid_road_not_station",
              "road_drive_km_to_snapped_grid_road_not_station",
              "source_city_road_snap_m","target_road_snap_m","road_status",
              "grid_proximity_category","2021_population_with_real_network_catchment")
        w=csv.DictWriter(f,fieldnames=cols,delimiter=";")
        w.writeheader();w.writerows({k:r.get(k) for k in cols} for r in rows)
    figure(rows,"geographic",geopng)
    figure(rows,"road",roadpng)
    by={(r["option_id"],r["urban_key"]):r for r in rows}
    names=sorted(entries,key=lambda x:(x.startswith("G30"),x))
    mdlines=["# G33 — Qualidade de acesso às seis cidades nos 30 corredores (27 G10 + 3 G30)",
       "","**Mesma cartografia e método para todos os 30**, medido de novo a partir das geometrias oficiais de investigação preservadas. Este exercício é aproximação geográfica e rodoviária a um ponto da grelha, **não** localiza uma estação. Não implica que o comboio pare em cada cidade.",
       "","A medição rodoviária OSRM é feita na mesma execução para todas as 30 variantes, por até seis consultas à rede de referência OSM, sem inventar resultados quando uma chamada ou ajuste à estrada falhe.",
       "","## Tabela integral — distâncias euclidianas da referência urbana à linha de grelha (km)",
       "","| Corredor | Guimarães | Amarante | Vila Real* | Mirandela | Macedo de Cavaleiros | Bragança* |",
       "|---|---:|---:|---:|---:|---:|---:|"]
    for k in names:
        mdlines.append("| "+k+" | "+" | ".join(str(by[k,c]["nearest_source_research_grid_direct_distance_km"]) for c in CITIES)+" |")
    mdlines+=["","## Tabela integral — automóvel OSRM até à estrada ajustada ao ponto mais próximo da malha (minutos)",
      "","| Corredor | Guimarães | Amarante | Vila Real* | Mirandela | Macedo de Cavaleiros | Bragança* |",
      "|---|---:|---:|---:|---:|---:|---:|"]
    for k in names:
        mdlines.append("| "+k+" | "+" | ".join(
          str(by[k,c]["road_drive_minutes_to_snapped_grid_road_not_station"])
          if by[k,c]["road_drive_minutes_to_snapped_grid_road_not_station"] is not None else "N/D" for c in CITIES)+" |")
    mdlines+=["","*Vila Real e Bragança obrigatórias; Sanábria excluída. Qualidade efetiva do serviço, plataforma, capacidade e ligação funcional não estão demonstradas. Guimarães já tem ferrovia existente, pelo que a interligação merece estudo próprio; a passagem próxima da malha não garante estação/paragem nem melhoria de serviço.*",
       "","## Cobertura dos dados externos de estrada",
       "","| Cidade | Destinos distintos numa consulta | Referências G10+G30 com rota+snap validado (máx. 30) | Fonte |",
       "|---|---:|---:|---|"]
    for q in receipts:
        mdlines.append(f"| {CITY[q['urban_key']]['label']} | {q['unique_destinations'] if 'unique_destinations' in q else '—'} | {q.get('qualified_rows',0)} | {q['status']} |")
    mdlines+=["","## Quatro padrões hipotéticos de exploração, aplicados igualmente aos 30 corredores e três velocidades",
       "","Expresso VR–Bragança; regional com Amarante/Mirandela/Macedo; regional com Guimarães/Mirandela/Macedo; regional com os seis mercados. Os intervalos adicionais estimam só desaceleração, aceleração e paragem de uma operação idealizada, sem marcha ferroviária ou cotas de estação; não são tempo porta-a-porta nem promessa de paragens.",
       "","**Demografia:** G14/G17/G18 já produziram BGRI2021 e isócronas rodoviárias para **três famílias antigas**, com referências de posição diferentes. Não se extrapola uma contagem 2021 ou acessibilidade em automóvel a todas as 30 variantes; estes campos permanecem **N/D** até fazer 30 avaliações comparáveis sobre a mesma fonte BGRI.",
       "","**Transporte público:** sem cobertura sistemática verificável GTFS/horários para toda a NUTS2 Norte, não imputar ausência de serviço, frequência zero ou tempos inventados.",
       "","**Ambiente e custos:** G32 manteve sobreposição Natura 2000 e relevo MDS para os 90 cenários; G33 conserva esses indicadores no ficheiro combinado sem os substituir. PIC mantém-se restrição maior sem delimitação oficial. Nenhum dos indicadores mede impacte ecológico de túneis, preço, procura, relevância do serviço ou viabilidade ferroviária.",
       "","Próximo portão: unir subsecções BGRI2021 aos **30 conjuntos** de áreas efetivamente alcançáveis por estrada (sem dupla contagem), antes de eventual shortlist 3–6; posteriormente, só estações com geometria, cotas e acesso legal poderão produzir tempos reais de serviço.",
       "","Sem novas quadrículas DGT, sem Fxx/Site.",""]
    md.write_text("\n".join(mdlines))
    print("G33_RESULT",json.dumps({"city_cases":len(rows),"wide_90":len(wide),"stop_360":len(modes),
        "network_receipts":receipts,"valid_road_pairs":sum(r["road_drive_minutes_to_snapped_grid_road_not_station"] is not None for r in rows),
        "geographic_near8_by_market":{c:sum(r["urban_key"]==c and r["nearest_source_research_grid_direct_distance_km"]<=8 for r in rows) for c in CITIES}},ensure_ascii=False,default=str),flush=True)
def main():
    p=argparse.ArgumentParser()
    for key in ("g10","g30","g30geo","g32","json","csv","combined","patterns","markdown","geoplot","roadplot"):
        p.add_argument("--"+key,required=True,type=Path)
    p.add_argument("--no-network",action="store_true")
    a=p.parse_args()
    b=a.g32.read_bytes()
    execute(json.loads(a.g10.read_text()),json.loads(a.g30.read_text()),
        json.loads(a.g30geo.read_text()),json.loads(b),b,
        a.json,a.csv,a.combined,a.patterns,a.markdown,a.geoplot,a.roadplot,network=not a.no_network)
if __name__=="__main__":main()
