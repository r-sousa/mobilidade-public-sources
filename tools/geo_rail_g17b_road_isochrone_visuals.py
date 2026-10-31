#!/usr/bin/env python3
"""G17B visualize observed Valhalla road isochrones (not bus/PT/station times)."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer

FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
CITIES=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
SPEEDS=(15,30,45)
def execute(src,geo,bar,heat,mapfile):
 r=json.loads(src.read_text());f=json.loads(geo.read_text())
 x=r["9_original_2021_road_catchment_union_aggregates"]
 z=r["54_source_city_minutes_cases"]
 if len(x)!=9 or len(z)!=54 or len(f["features"])!=63:
  raise ValueError("G17B_expected_source_2021_and_Valhalla_shapes_missing")
 union={(j["research_family"],j["reverse_road_travel_time_minutes"]):j for j in x}
 site={(j["research_family"],j["urban_market_reference"],j["reverse_road_travel_time_minutes"]):j for j in z}
 vals=np.array([[union[f,t]["total_2021_residents_in_nonoverlapping_road_isochrone_union"] for t in SPEEDS] for f in FAMILIES])
 fig,ax=plt.subplots(figsize=(10.7,6.0),layout="constrained")
 for i,t in enumerate(SPEEDS):
  bars=ax.bar(np.arange(3)+(i-1)*.26,vals[:,i]/1000,width=.24,label=f"{t} minutos")
  for p in bars:
   ax.annotate(f"{p.get_height():.0f}",(p.get_x()+p.get_width()/2,p.get_height()),
    xytext=(0,3),textcoords="offset points",ha="center",fontsize=9)
 ax.set_xticks(np.arange(3),[x.removeprefix("P") for x in FAMILIES])
 ax.set_ylabel("Milhares de residentes — INE Censos 2021")
 ax.set_title("População residente nas isócronas rodoviárias de chegada ao ponto de estudo",loc="left",fontsize=13,fontweight="bold")
 ax.grid(axis="y",alpha=.15)
 ax.legend()
 fig.text(.08,.01,"União de 6 pontos/alternativa, sem dupla contagem. Rede OSM/Valhalla; não estações, GTFS, congestionamento ou passageiros ferroviários.",fontsize=9)
 bar.parent.mkdir(parents=True,exist_ok=True)
 fig.savefig(bar,dpi=160,bbox_inches="tight");plt.close(fig)
 matrix=np.array([[site[f,city,15]["2021_INE_census_residents_representative_point"] for city in CITIES] for f in FAMILIES])
 fig,ax=plt.subplots(figsize=(11.5,4.6),layout="constrained")
 im=ax.imshow(matrix,aspect="auto",cmap="viridis")
 ax.set_yticks(range(3),[f.removeprefix("P") for f in FAMILIES])
 ax.set_xticks(range(6),CITIES,rotation=22,ha="right")
 for i in range(3):
  for k in range(6):
   p=matrix[i,k]
   ax.text(k,i,f"{p/1000:.1f} mil",ha="center",va="center",
    color="white" if p>matrix.max()*.5 else "black",fontsize=9)
 ax.set_title("Residentes nas isócronas de 15 min por ponto rodoviário de investigação",loc="left",fontsize=13,fontweight="bold")
 ax.set_xlabel("Cidade = mercado urbano associado, não valida estação. Chegada de automóvel sem tráfego em tempo real.")
 fig.text(.07,.01,"INE 2021 e Valhalla/OSM. Não equivale a emprego, procura ferroviária ou disponibilidade de transporte público.",fontsize=9)
 fig.savefig(heat,dpi=160,bbox_inches="tight");plt.close(fig)
 # Comparative geography map uses actual returned Valhalla iso boundaries.
 tr=Transformer.from_crs(4326,3763,always_xy=True)
 features={(j["properties"]["study_family"],j["properties"].get("reverse_automobile_isochrone_arrival_minutes")):j
   for j in f["features"] if j["properties"].get("layer")=="union_6_study_reference_reverse_isochrones"}
 if len(features)!=9:raise ValueError("G17B_nine_georeferenced_real_road_area_union_shapes_missing")
 fig,axes=plt.subplots(1,3,figsize=(15.5,6.1),sharex=True,sharey=True,layout="constrained")
 palette={15:"#1b9761",30:"#2478b2",45:"#ae6c44"}
 allbounds=[]
 for ax,family in zip(axes,FAMILIES):
  for t in reversed(SPEEDS):
   shp=transform(tr.transform,shape(features[family,t]["geometry"]))
   allbounds.append(shp.bounds)
   for polygon in (list(shp.geoms) if hasattr(shp,"geoms") else [shp]):
    x,y=polygon.exterior.xy
    ax.fill(np.array(x)/1000,np.array(y)/1000,color=palette[t],alpha=.17,linewidth=.5)
    ax.plot(np.array(x)/1000,np.array(y)/1000,color=palette[t],linewidth=.7,alpha=.8)
  ax.set_title("Família "+family.removeprefix("P"),fontsize=11,fontweight="bold")
  ax.set_xlabel("ETRS89 / PT-TM06 Este (km)",fontsize=9)
  ax.grid(alpha=.17)
 axes[0].set_ylabel("ETRS89 / PT-TM06 Norte (km)",fontsize=9)
 for ax in axes:ax.set_aspect("equal",adjustable="box")
 fig.suptitle("Cobertura real por rede rodoviária em 15/30/45 minutos — seis pontos de investigação",fontsize=14)
 from matplotlib.patches import Patch
 fig.legend(handles=[Patch(facecolor=palette[t],alpha=.5,label=f"{t}min") for t in SPEEDS],
    loc="lower center",ncol=3,bbox_to_anchor=(.5,-.01))
 fig.savefig(mapfile,dpi=170,bbox_inches="tight")
 plt.close(fig)
 print("G17B_VISUAL_SOURCE="+json.dumps({"bars":"3 families ×3 real driving contours",
  "cells":18,"union_shapes":len(features),"percent_real_source":100},ensure_ascii=False))
def main():
 a=argparse.ArgumentParser()
 for n in ("source","geojson","bars","heatmap","map"):a.add_argument("--"+n,type=Path,required=True)
 q=a.parse_args();execute(q.source,q.geojson,q.bars,q.heatmap,q.map)
if __name__=="__main__":main()
