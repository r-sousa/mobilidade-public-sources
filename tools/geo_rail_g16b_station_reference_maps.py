#!/usr/bin/env python3
"""G16B visual, real INE 2021 and G13A roads+surface site Pareto, not stations."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point,mapping
from pyproj import Transformer

FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
CITY=("Guimaraes","Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca")
LABELS=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
def make(inputfile,heat,geojson):
 data=json.loads(inputfile.read_text())
 if (data["source_sites_screened"]!=54 or len(data["market_by_family_pareto_reference_screen"])!=18
     or data["Fxx_accepted"] or data["Site_authorized"]):
  raise ValueError("G16_original_scope_and_54_sites_not_grounded")
 selected={(r["research_family"],r["urban_market"]):set(r["nondominated_reference_offsets_km"])
   for r in data["market_by_family_pareto_reference_screen"]}
 locations=data["all_54_source_research_station_reference_alternatives"]
 count=np.asarray([[len(selected[(f,c)]) for c in CITY] for f in FAMILIES],int)
 fig,ax=plt.subplots(figsize=(11.4,4.5),layout="constrained")
 im=ax.imshow(count,aspect="auto",cmap="viridis",vmin=1,vmax=3)
 ax.set_yticks(range(3),[x.removeprefix("P") for x in FAMILIES])
 ax.set_xticks(range(6),LABELS,rotation=22,ha="right")
 for i in range(3):
  for j in range(6):
   ax.text(j,i,f"{count[i,j]} de 3",ha="center",va="center",fontsize=10,fontweight="bold",color="white" if count[i,j]<3 else "black")
 ax.set_title("G16 — posições de estudo não dominadas por cidade e alternativa",loc="left",fontweight="bold",fontsize=13)
 ax.set_xlabel("Combina população INE 2021 até 5 km, tempos OSRM ao ponto rodoviário e pressão MDS local — não significa viabilidade de estação")
 fig.text(.09,.012,"A ausência de dados de transportes públicos no Norte não foi pontuada como ausência de serviço. Nenhum local de estação está aprovado.",fontsize=9)
 heat.parent.mkdir(parents=True,exist_ok=True);fig.savefig(heat,dpi=160,bbox_inches="tight");plt.close(fig)
 geo=[]
 for z in locations:
  offset=z["longitudinal_offset_km_from_nearest_grid_source_reference"]
  chosen=offset in selected[(z["research_family"],z["urban_market_key"])]
  geo.append({"type":"Feature","geometry":{"type":"Point","coordinates":z["WGS84_2km_research_grid_reference_NOT_station"]},
   "properties":{"family":z["research_family"],"urban_market_reference":z["urban_market_key"],"mandatory":z["mandatory_service_market"],
   "offset_along_source_grid_km":offset,"nondominated_Pareto_source_screen":chosen,
   "INE2021_5km_residents_circular_geography_NOT_true_station_isochrone":z["original_2021_residents_within_5km_geographic_buffer"],
   "INE2021_10km_residents_circular_geography_NOT_true_station_isochrone":z["original_2021_residents_within_10km_geographic_buffer"],
   "actual_OSRM_road_minutes_to_study_nonstation_reference":z["OSRM_2026_urban_market_to_research_road_reference_min"],
   "Copernicus_surface_DSM_25permille_1km_vertical_P90_m":z["DSM_25permille_1km_vertical_P90_surface_residual_m"],
   "not_a_real_station_or_approved_site":True,"PT_coverage_not_measured_not_assumed_zero":True}})
 geojson.parent.mkdir(parents=True,exist_ok=True)
 geojson.write_text(json.dumps({"type":"FeatureCollection",
   "name":"G16 54 actual georeferenced original 2km rail research reference locations, NOT stations","features":geo},ensure_ascii=False,separators=(',',':'))+"\n")
 print("G16B_VISUAL="+json.dumps({"reference_points":len(geo),
  "nondominated_source_positions":sum(f["properties"]["nondominated_Pareto_source_screen"] for f in geo),
  "site_positions_per_city":count.tolist()},separators=(',',':')))
def main():
 p=argparse.ArgumentParser()
 for n in ("source","heatmap","geojson"):p.add_argument("--"+n,required=True,type=Path)
 q=p.parse_args();make(q.source,q.heatmap,q.geojson)
if __name__=="__main__":main()
