#!/usr/bin/env python3
"""G12C graphical service and surface-pressure *source* decision comparison.

Generates transparent image heatmap and quantitative scatter, using only G12B
audited source evidence. No financial costs, approved station locations, rail
travel times, demand or land information is invented.
"""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAMES=("Guimaraes","Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca")
LABELS=("Guimarães","Amarante","Vila Real*","Mirandela","Macedo de Cavaleiros","Bragança*")
def plot(src,road,pressure):
 x=json.loads(src.read_text())
 rows=x["per_alternative_source_comparison"]
 if len(rows)!=6:raise ValueError("G12B_wrong_6_source_options")
 labels=[r["research_combination"].removeprefix("P") for r in rows]
 data=np.asarray([[r["road_to_study_road_snap_from_urban_centre_minutes"][k]
     if r["road_to_study_road_snap_from_urban_centre_minutes"][k] is not None else float("nan")
         for k in NAMES] for r in rows],dtype=float)
 fig,ax=plt.subplots(figsize=(11,4.9),layout="constrained")
 masked=np.ma.masked_invalid(data)
 im=ax.imshow(masked,aspect="auto",vmin=0,vmax=46,cmap="viridis_r")
 ax.set_xticks(range(6),LABELS,rotation=17,ha="right")
 ax.set_yticks(range(6),labels)
 for i in range(6):
  for k in range(6):
   a=data[i,k]
   ax.text(k,i,f"{a:.1f}" if np.isfinite(a) else "N/D",
    ha="center",va="center",fontsize=9,color="black" if a>25 or not np.isfinite(a) else "white")
 fig.colorbar(im,ax=ax,label="Minutos automóvel à via de proximidade (não à estação)",shrink=.77)
 ax.set_title("G12 — seis famílias: acessibilidade rodoviária exploratória",loc="left",fontweight="bold")
 fig.text(.06,.005,"* Nó obrigatório. Não são estações viáveis; os destinos são road-snaps OSRM próximos dos eixos de grelha.",fontsize=9)
 road.parent.mkdir(parents=True,exist_ok=True)
 fig.savefig(road,dpi=160,bbox_inches="tight")
 plt.close(fig)
 fig,ax=plt.subplots(figsize=(10.5,6.3),layout="constrained")
 for r in rows:
  name=r["research_combination"].removeprefix("P")
  x0=r["G10_200kmh_length_index_km_NOT_railway"]
  y0=100*r["G10_200kmh_25permille_DSM_fraction_residual_gt25m_NOT_cost"]
  keep=r["research_combination"] in x["provisional_3_family_anchors_NOT_final_selection"]
  col="#2475af" if r["research_combination"].split("-")[0]=="P1" else "#15916d" if r["research_combination"].split("-")[0]=="P2" else "#b46c3e"
  ax.scatter(x0,y0,color=col,s=150 if keep else 70,marker="o",alpha=.85,
             edgecolors="black" if keep else "none",linewidths=1.5)
  ax.annotate(name,(x0,y0),xytext=(6,7),textcoords="offset points",fontsize=10,
    fontweight="bold" if keep else "normal")
 ax.set_title("G12 — distância de estudo versus pressão topográfica de superfície",
   loc="left",fontweight="bold")
 ax.set_xlabel("Comprimento da grelha suavizada a 200 km/h (km) · NÃO extensão ferroviária")
 ax.set_ylabel("Desvio do perfil MDS >25m (%) · NÃO CAPEX")
 ax.grid(alpha=.2)
 fig.text(.075,.015,"Pontos contornados: famílias retidas por diversidade espacial e serviço. Não significa ótimo técnico nem económico.",fontsize=9)
 pressure.parent.mkdir(parents=True,exist_ok=True)
 fig.savefig(pressure,dpi=160,bbox_inches="tight")
 plt.close(fig)
 print("G12C_GRAPHICS="+json.dumps({"routes":len(rows),"cities":len(NAMES),
  "road_valid":int(np.isfinite(data).sum()),"road_png":road.name,"terrain_png":pressure.name}))
def main():
 a=argparse.ArgumentParser()
 for n in ("report","road","terrain"):a.add_argument("--"+n,type=Path,required=True)
 p=a.parse_args();plot(p.report,p.road,p.terrain)
if __name__=="__main__":main()
