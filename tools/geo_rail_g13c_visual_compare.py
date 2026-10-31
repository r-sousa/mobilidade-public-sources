#!/usr/bin/env python3
"""G13C non-fiction source-only charts for three geographic families.

Charts from published G10 and G12B, and actual G13A 108 surface profiles.
Neither road reference snap nor DSM surface is a verified rail station or
economic EUR estimate.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CITIES=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
def source_matrix(j):
 selection={ (x["research_combination"],x["urban_market"]):x for x in j["non_dominated_reference_site_screens_per_market"] }
 if len(selection)!=36:raise ValueError("G13A_missing_36_market_corridor_source_cases")
 roads=np.full((3,6),np.nan);surface=roads.copy()
 for i,r in enumerate(FAMILIES):
  for k,c in enumerate(CITIES):
   spots=selection[(r,c)]["non_dominated_road_time_vs_DSM_terrain_reference_points"]
   if not spots:continue
   roads[i,k]=min(x["real_road_time_to_nearest_grid_road_snap_min"] for x in spots)
   surface[i,k]=min(x["L1_25permille_p90_vertical_surface_residual_m"] for x in spots)
 return roads,surface

def plot(report,roadpath,terrainpath):
 j=json.loads(report.read_text())
 assert j["site_counts"]["original_research_points"]==108
 roads,surface=source_matrix(j)
 for data,path,vmax,title,text in [
  (roads,roadpath,36.,"Tempos rodoviários aos pontos de investigação por família (min)","Menor tempo OSRM até via próxima da grelha; NÃO é uma estação."),
  (surface,terrainpath,65.,"Pressão do relevo superficial junto dos interfaces (m)","P90 do desvio MDS num perfil matemático a 25‰; NÃO é custo em euros.")]:
  fig,ax=plt.subplots(figsize=(11.3,4.7),layout="constrained")
  im=ax.imshow(np.ma.masked_invalid(data),aspect="auto",vmin=0,vmax=vmax,cmap="viridis_r")
  ax.set_yticks(range(3),[x.removeprefix("P") for x in FAMILIES],fontsize=11)
  ax.set_xticks(range(6),CITIES,rotation=19,ha="right")
  for i in range(3):
   for k in range(6):
    value=data[i,k]
    label=f"{value:.1f}" if np.isfinite(value) else "N/D"
    ax.text(k,i,label,ha="center",va="center",color="white" if value<.58*vmax else "#151923",
     fontsize=10,fontweight="bold")
  ax.set_title(title,loc="left",fontweight="bold",fontsize=13)
  ax.set_xlabel(text,fontsize=9)
  fig.colorbar(im,ax=ax,shrink=.80,label="Minutos" if data is roads else "Metros de MDS")
  fig.text(.08,.005,"* Vila Real e Bragança são mercados obrigatórios. Sanábria excluída. Todas as localizações são referências de estudo, não estações validadas.",fontsize=8)
  path.parent.mkdir(parents=True,exist_ok=True)
  fig.savefig(path,dpi=160,bbox_inches="tight")
  plt.close(fig)
 print("G13C_PLOTS="+json.dumps({"families":len(FAMILIES),"urban_markets":len(CITIES),
  "observed_road_reference_points":int(np.isfinite(roads).sum()),
  "observed_source_surface_terrain_profiles":int(np.isfinite(surface).sum())},separators=(',',':')))
def main():
 a=argparse.ArgumentParser()
 for k in ("report","road","terrain"):a.add_argument("--"+k,required=True,type=Path)
 p=a.parse_args();plot(p.report,p.road,p.terrain)
if __name__=="__main__":main()
