#!/usr/bin/env python3
"""G11 plot six-city service envelope and actual OSRM-probed road proxy data."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm,ListedColormap

CITIES=("Guimaraes","Amarante","Vila_Real","Mirandela","Macedo_de_Cavaleiros","Braganca")
LABELS=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
def render(src,out_heat,out_access):
 j=json.loads(src.read_text())
 assert j["city_route_pairs"]==162 and len(j["all_162_source_route_city_pairs"])==162
 all_rows=j["all_162_source_route_city_pairs"]
 routes=sorted(set(r["combination_id"] for r in all_rows))
 assert len(routes)==27
 lookup={(r["combination_id"],r["city_key"]):r for r in all_rows}
 data=np.asarray([[lookup[(route,c)]["minimum_straight_distance_urban_reference_to_source_lattice_km"]
                    for c in CITIES] for route in routes])
 fig,ax=plt.subplots(figsize=(12.4,9),layout="constrained")
 col=ListedColormap(["#c5e9db","#d6e8f7","#fde2b8","#f8c5c5"])
 bounds=[0,3,8,20,1000]
 im=ax.imshow(data,aspect="auto",cmap=col,norm=BoundaryNorm(bounds,col.N))
 ax.set_xticks(np.arange(len(CITIES)),LABELS,rotation=28,ha="right",fontsize=10)
 ax.set_yticks(range(len(routes)),routes,fontsize=8)
 for i in range(len(routes)):
  for k in range(len(CITIES)):
   ax.text(k,i,f"{data[i,k]:.1f}",ha="center",va="center",fontsize=7.6,color="#16202a")
 ax.set_title("Serviço territorial potencial · 27 alternativas × 6 cidades",fontsize=15,loc="left",fontweight="bold")
 ax.set_xlabel("Afastamento direto da referência urbana à trajetória de grelha (km) · NÃO acesso rodoviário nem estação")
 fig.text(.09,.013,"Cor verde: ≤3 km | azul: 3–8 km | âmbar: 8–20 km | vermelho: >20 km. Apenas referência geográfica; VR e Bragança são nós obrigatórios.",fontsize=9)
 out_heat.parent.mkdir(parents=True,exist_ok=True)
 fig.savefig(out_heat,bbox_inches="tight",dpi=150)
 plt.close(fig)
 chosen=["P1-1-1","P1-2-1","P2-2-1","P2-2-3","P1-3-1","P3-1-3"]
 road=np.array([[lookup[(r,c)]["road_routing_network_minutes_to_research_point"]
                 if lookup[(r,c)]["road_routing_network_minutes_to_research_point"] is not None
                 else np.nan for c in CITIES] for r in chosen],dtype=float)
 fig,ax=plt.subplots(figsize=(12.4,5.5),layout="constrained")
 col2=ListedColormap(["#b7dfd3","#c3d7e9","#f4dec0","#efa7a7"])
 normal=np.where(np.isnan(road),-1,road)
 ax.imshow(np.ma.masked_invalid(road),cmap="viridis",aspect="auto",vmin=0,vmax=max(35,float(np.nanmax(road))) if np.isfinite(road).any() else 40)
 ax.set_xticks(np.arange(len(CITIES)),LABELS,rotation=23,ha="right")
 ax.set_yticks(np.arange(len(chosen)),chosen)
 for i in range(len(chosen)):
  for k in range(len(CITIES)):
   value=road[i,k]
   ax.text(k,i,f"{value:.1f} min" if np.isfinite(value) else "N/D",ha="center",va="center",fontsize=9,
           color="white" if np.isfinite(value) else "#a23e31")
 ax.set_title("Roteamento OSRM · referência urbana → ponto de estrada próximo da faixa",loc="left",fontweight="bold",fontsize=13)
 ax.set_xlabel("NÃO são tempos de acesso a estações; pontos de estrada ajustados ao modelo OSM (limite de 600 m), sujeitas a validação local")
 fig.text(.1,.012,"N/D = API indisponível, percurso impossível, ou referência afastada da estrada >600 m. Os pontos não comprovam implantação de estações.",fontsize=9)
 fig.savefig(out_access,bbox_inches="tight",dpi=150)
 plt.close(fig)
 print("G11_PLOTS="+json.dumps({"heat":str(out_heat),"access":str(out_access),"routed_nonmissing":int(np.isfinite(road).sum())}))

def main():
 a=argparse.ArgumentParser()
 a.add_argument("--report",type=Path,required=True)
 a.add_argument("--heatmap",type=Path,required=True)
 a.add_argument("--roadmap",type=Path,required=True)
 q=a.parse_args()
 render(q.report,q.heatmap,q.roadmap)
if __name__=="__main__":main()
