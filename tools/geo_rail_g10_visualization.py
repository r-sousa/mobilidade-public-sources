#!/usr/bin/env python3
"""Source-coordinate geographic and multi-criteria visualizations for G10.

All maps are plots of actual G3/G5 2km research sector centre paths in
PT-TM06, NOT illustrative invented rail tracks. No road accessibility
or CAPEX values are inferred from the surface DSM.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pyproj import Transformer
from shapely.geometry import LineString,mapping
from shapely.ops import transform
from geo_rail_g10_27_macro_portfolio import compose,G3_SHA,G5_SHA

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def make(g3path,g5path,portfolio_path,geojson_path,map_path,scatter_path):
 if sha(g3path)!=G3_SHA or sha(g5path)!=G5_SHA:
  raise ValueError("G10_source_city_terrain_G5_SHA_fail")
 g3=json.loads(g3path.read_text());g5=json.loads(g5path.read_text())
 j=json.loads(portfolio_path.read_text())
 if j["total_combinations"]!=27 or len(j["scenario_rows"])!=81:
  raise ValueError("G10_source_27x3_visual_contract_fail")
 sources=compose(g3,g5)
 coords=Transformer.from_crs(3763,4326,always_xy=True)
 features=[]
 for id,modules,p in sources:
  ls=LineString([(x+1000,y+1000) for x,y in p])
  features.append({"type":"Feature","geometry":mapping(transform(coords.transform,ls)),
    "properties":{"id":id,"P1":modules[0],"P3":modules[1],"P5":modules[2],
      "coordinate_source":"real_G5_G3_2km_PT_TM06_research_grid_sector_centres",
      "this_is_not_an_approved_or_proposed_railway_alignment":True}})
 geojson_path.parent.mkdir(parents=True,exist_ok=True)
 geojson_path.write_text(json.dumps({"type":"FeatureCollection","name":"G10 27 true source research routes; NOT rail alignments",
    "features":features},ensure_ascii=False,indent=2)+"\n")
 fig,ax=plt.subplots(figsize=(12,7),layout="constrained")
 fig.patch.set_facecolor("white")
 names={ "P2-2-1":("#09764e",2.9,"2–2–1 · menor pressão DSM"),
         "P1-2-1":("#1d61b4",2.8,"1–2–1 · mais direta"),
         "P1-1-1":("#bf6534",1.3,"1–1–1 · referência G6")}
 for id,modules,p in sources:
  if id in names:continue
  x=[q[0]/1000 for q in p];y=[q[1]/1000 for q in p]
  ax.plot(x,y,color="#a0adba",alpha=.22,linewidth=.9)
 for id,modules,p in sources:
  if id not in names:continue
  col,w,label=names[id]
  x=[q[0]/1000 for q in p];y=[q[1]/1000 for q in p]
  ax.plot(x,y,color=col,linewidth=w,alpha=.96,label=label,zorder=5)
 city=[("AFSC · referência",-8.678056,41.235556),("Vila Real · área",-7.744,41.3006),
       ("Bragança · área",-6.7576,41.8060),("Zamora · referência",-5.746992,41.50378)]
 # Grounded to official AIP AFSC and already used research city reference coordinates.
 west=Transformer.from_crs(4326,3763,always_xy=True)
 for name,lon,lat in city:
  x,y=west.transform(lon,lat);x/=1000;y/=1000
  ax.scatter([x],[y],color="#132b41",s=35,zorder=7)
  ax.annotate(name,(x,y),xytext=(6,6),textcoords="offset points",fontsize=9,color="#102f4b",
   bbox=dict(facecolor="white",alpha=.78,edgecolor="none",pad=1.5))
 ax.set_title("27 combinações de corredores geográficos de estudo · coordenadas de origem",loc="left",
  fontsize=14,fontweight="bold")
 ax.set_xlabel("PT-TM06 / ETRS89 · coordenada Este (km)")
 ax.set_ylabel("PT-TM06 / ETRS89 · coordenada Norte (km)")
 ax.set_aspect("equal",adjustable="datalim")
 ax.grid(alpha=.14)
 ax.legend(loc="lower right",framealpha=.92,fontsize=9)
 fig.text(.08,.01,"Cada linha une centros das quadrículas G3/G5 de 2 km. NÃO é traçado ferroviário, nem delimitação do corredor de obra.",fontsize=9)
 fig.savefig(map_path,dpi=160,bbox_inches="tight")
 plt.close(fig)

 v=[z for z in j["scenario_rows"] if z["speed_scenario_kmh"]==200 and z["horizontal_radius_research_screen_pass"]]
 pareto=set(j["Pareto_exploratory_study_front_by_speed_and_traffic_case"]["200"]["passenger25"])
 fig,ax=plt.subplots(figsize=(11,7),layout="constrained")
 fig.patch.set_facecolor("white")
 palette={1:"#246bc0",2:"#15936a",3:"#ba7845"}
 for option in (1,2,3):
  subset=[z for z in v if z["module_options"]["P3"]==option]
  x=[z["hypothetical_length_divided_by_speed_minutes_NOT_train_travel_time"] for z in subset]
  y=[100*z["passenger25_DSM_fraction_gt25m"] for z in subset]
  ax.scatter(x,y,s=[110 if z["combination_id"] in pareto else 42 for z in subset],
    c=palette[option],alpha=.7,label=f"P3 · variante {option}",
    edgecolors=["#111" if z["combination_id"] in pareto else "none" for z in subset])
 for id in ("P2-2-1","P1-2-1","P1-1-1","P2-2-2"):
  q=next(z for z in v if z["combination_id"]==id)
  ax.annotate(id.replace("P",""),(q["hypothetical_length_divided_by_speed_minutes_NOT_train_travel_time"],
    100*q["passenger25_DSM_fraction_gt25m"]),xytext=(5,8),textcoords="offset points",
    fontsize=10,fontweight="bold")
 ax.set_title("27 alternativas · confronto exploratório a 200 km/h e 25‰",loc="left",
   fontsize=15,fontweight="bold")
 ax.set_xlabel("ÍNDICE tempo geométrico: distância da grelha suavizada ÷ 200 km/h (min) · NÃO tempo real")
 ax.set_ylabel("Pressão topográfica: amostras com desvio vertical MDS >25 m (%) · NÃO custo")
 ax.grid(alpha=.2)
 ax.legend(loc="upper right",fontsize=9)
 fig.text(.07,.015,
   "Custo de construção (€): N/D       Intermodalidade por rede rodoviária: N/D       Serviço das cidades: obrigação topológica, estação por validar.",
   fontsize=9,color="#4e5360")
 fig.savefig(scatter_path,dpi=160,bbox_inches="tight")
 plt.close(fig)

 concise=[{"id":z["combination_id"],"speed":z["speed_scenario_kmh"],
     "tm":z.get("hypothetical_length_divided_by_speed_minutes_NOT_train_travel_time"),
     "km":z.get("smoothed_research_grid_length_km_not_rail_track"),
     "pressure":z.get("passenger25_DSM_fraction_gt25m"),
     "p90":z.get("passenger25_DSM_p90_m"),"r":z["horizontal_radius_research_screen_pass"],
     "p3":z["module_options"]["P3"],
     "pareto":z["combination_id"] in j["Pareto_exploratory_study_front_by_speed_and_traffic_case"][str(z["speed_scenario_kmh"])]["passenger25"]}
     for z in j["scenario_rows"]]
 print("G10_VISUAL_MATRIX="+json.dumps(concise,separators=(',',':')))
 print("G10_REAL_SOURCE_GEOGRAPHIC_GRAPH="+json.dumps({"features":len(features),
   "map_png":map_path.name,"comparison_png":scatter_path.name,"pareto200":sorted(pareto)}))

def main():
 a=argparse.ArgumentParser()
 for name in ("g3","g5","portfolio","geojson","map","scatter"):
  a.add_argument("--"+name,type=Path,required=True)
 q=a.parse_args()
 make(q.g3,q.g5,q.portfolio,q.geojson,q.map,q.scatter)
if __name__=="__main__":main()
