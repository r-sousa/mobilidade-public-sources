#!/usr/bin/env python3
"""G15B transparent 2021 resident 4km road-sampling quality charts.

Every bar has known routed sample share and unknown complement. No assigned
bus/PT scores, no automatic classification of unknown as unreachable, no
train station or road-network isochrone claims.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer
from shapely.geometry import Point,mapping

F=("P1-2-1","P2-2-1","P2-2-3")
C=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")

def charts(src,coverage,access,geo):
 report=json.loads(src.read_text())
 if report["Fxx_accepted"] or report["Site_authorized"] or len(report["all_18_family_city_population_road_research_screen"])!=18:
  raise ValueError("G15_original_source_scope_not_valid")
 lookup={(r["research_family"],r["associated_urban_market"]):r for r in report["all_18_family_city_population_road_research_screen"]}
 share=np.asarray([[lookup[(f,c)]["road_sample_classification"]["fraction_of_2021_population_sampled_and_routed"] for c in C] for f in F])
 matrix15=np.asarray([[lookup[(f,c)]["road_sample_classification"]["conservative_nonstation_sampled_road_coverage_by_time_minutes"]["15"]["qualifying_population_2021_from_road_samplings"] for c in C] for f in F],float)
 matrix30=np.asarray([[lookup[(f,c)]["road_sample_classification"]["conservative_nonstation_sampled_road_coverage_by_time_minutes"]["30"]["qualifying_population_2021_from_road_samplings"] for c in C] for f in F],float)
 fig,ax=plt.subplots(figsize=(11.3,4.6),layout="constrained")
 im=ax.imshow(share*100,aspect="auto",vmin=0,vmax=100,cmap="viridis")
 ax.set_xticks(range(6),C,rotation=18,ha="right")
 ax.set_yticks(range(3),[f.removeprefix("P") for f in F])
 for i in range(3):
  for j in range(6):ax.text(j,i,f"{share[i,j]*100:.0f}%",ha="center",va="center",fontweight="bold",fontsize=10,color="white" if share[i,j]<.7 else "#132b39")
 fig.colorbar(im,ax=ax,label="Parte da população INE 2021 com amostra rodoviária classificável (%)",shrink=.82)
 ax.set_title("G15 — fiabilidade da amostragem rodoviária, não cobertura de transporte",loc="left",fontsize=13,fontweight="bold")
 ax.set_xlabel("Diferença até 100% = células sem classificação, NÃO população sem acesso ou sem transporte público.",fontsize=9)
 coverage.parent.mkdir(parents=True,exist_ok=True)
 fig.savefig(coverage,dpi=160,bbox_inches="tight");plt.close(fig)
 fig,axs=plt.subplots(figsize=(12,5.3),layout="constrained")
 im=axs.imshow(matrix30/1000,aspect="auto",cmap="viridis")
 axs.set_xticks(range(6),C,rotation=18,ha="right")
 axs.set_yticks(range(3),[f.removeprefix("P") for f in F])
 for i in range(3):
  for j in range(6):
   axs.text(j,i,f"{matrix15[i,j]/1000:.1f} / {matrix30[i,j]/1000:.1f}",ha="center",va="center",fontsize=8.5,color="white" if matrix30[i,j]<90000 else "#142439")
 fig.colorbar(im,ax=axs,shrink=.8,label="Milhares de residentes classificados em 30min da amostra")
 axs.set_title("G15 — residentes 2021 em células classificadas até 15 / 30min (milhares)",loc="left",fontsize=13,fontweight="bold")
 axs.set_xlabel("Os tempos são OSRM 2026 para pontos próximos das faixas, NÃO estações. Áreas limitadas a raio retilíneo 30km.")
 fig.savefig(access,dpi=160,bbox_inches="tight");plt.close(fig)
 t=Transformer.from_crs(4326,3763,always_xy=True)
 inverse=Transformer.from_crs(3763,4326,always_xy=True)
 features=[]
 for row in report["all_18_family_city_population_road_research_screen"]:
  for cell in row["original_sampled_population_cells"]:
   lon,lat=cell["source_representative_populated_subsection_reference_lonlat"]
   features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
    "properties":{"source_research_family":row["research_family"],"associated_market":row["associated_urban_market"],
       "population_2021_grid_cell":cell["INE_2021_census_residents_in_sampled_cell"],
       "road_OSRM_2026_minutes_to_road_snap_not_station":cell["router_2026_network_duration_minutes"],
       "sample_snap_valid":cell["road_snapping_accepted"],
       "unrouted_or_unqueried_is_UNKNOWN_not_no_access":cell["router_2026_network_duration_minutes"] is None,
       "4km_population_cell_representative_point_NOT_exact_population_location":True}})
 geo.parent.mkdir(parents=True,exist_ok=True)
 geo.write_text(json.dumps({"type":"FeatureCollection",
   "name":"G15 sampled 4km INE census cells and observed OSRM network route to NON-station study points","features":features},ensure_ascii=False,separators=(',',':'))+"\n")
 print("G15B_SOURCE_CHARTS="+json.dumps({"features":len(features),
  "known_pop_reliability_per_family_market_percent":(share*100).round(1).tolist(),
  "15_min_population_source_samples":matrix15.astype(int).tolist(),
  "30_min_population_source_samples":matrix30.astype(int).tolist()},separators=(',',':')))
def main():
 a=argparse.ArgumentParser()
 for k in ("json","coverage","minutes","geojson"):a.add_argument("--"+k,required=True,type=Path)
 p=a.parse_args();charts(p.json,p.coverage,p.minutes,p.geojson)
if __name__=="__main__":main()
