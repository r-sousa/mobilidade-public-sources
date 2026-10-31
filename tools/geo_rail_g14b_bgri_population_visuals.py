#!/usr/bin/env python3
"""G14B plot actual original 2021 BGRI census populations around study points.

All plots/maps label Euclidean research buffers NOT isochrones, legally
serviced or validated railway stations. Associated city names do not imply
that the named urban centre is inside the referenced circle.
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
from shapely.ops import transform

FAMILIES=("P1-2-1","P2-2-1","P2-2-3")
CITIES=("Guimarães","Amarante","Vila Real","Mirandela","Macedo de Cavaleiros","Bragança")
def plot(src,union_chart,city_chart,geojson):
 d=json.loads(src.read_text())
 if len(d["all_54_city_research_geographic_buffer_census_cases"])!=54 or len(d["six_family_population_nonoverlapping_buffer_union_cases"])!=6:
  raise ValueError("G14_demographic_content_missing")
 cases=d["all_54_city_research_geographic_buffer_census_cases"]
 unions=d["six_family_population_nonoverlapping_buffer_union_cases"]
 qa=d["source_schema_validation"]
 if qa["record_count"]!=203264 or qa["srs"]!=3763:
  raise ValueError("G14_census_original_source_provenance_failed")
 values={x["research_corridor"]+"-"+str(x["union_geographic_radius_km"]):x["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"] for x in unions}
 vals10=[values[f+"-10"] for f in FAMILIES]
 vals20=[values[f+"-20"] for f in FAMILIES]
 pos=np.arange(len(FAMILIES))
 fig,ax=plt.subplots(figsize=(10,5.5),layout="constrained")
 width=.32
 bar1=ax.bar(pos-width/2,np.array(vals10)/1000,width,label="União de círculos 10 km")
 bar2=ax.bar(pos+width/2,np.array(vals20)/1000,width,label="União de círculos 20 km")
 for bars in (bar1,bar2):
  for bb in bars:ax.annotate(f"{bb.get_height():.0f}",(bb.get_x()+bb.get_width()/2,bb.get_height()),xytext=(0,3),textcoords="offset points",ha="center",fontsize=9)
 ax.set_xticks(pos,[s.removeprefix("P") for s in FAMILIES])
 ax.set_ylabel("Milhares de residentes (INE Censos 2021)")
 ax.set_title("População residente na união dos círculos geográficos dos 6 pontos por alternativa",loc="left",fontsize=13,fontweight="bold")
 ax.grid(axis="y",alpha=.18)
 ax.legend(loc="upper left")
 fig.text(.05,.015,"Áreas retas de 10/20km, não isócronas de acesso real nem passageiros. União evita dupla contagem de áreas sobrepostas.",fontsize=9)
 fig.savefig(union_chart,dpi=160,bbox_inches="tight")
 plt.close(fig)
 sel={(x["research_corridor"],x["urban_market"]):x for x in cases if x["research_geographic_radius_km"]==10}
 matrix=np.asarray([[sel[(f,c)]["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"] for c in CITIES] for f in FAMILIES])
 fig,ax=plt.subplots(figsize=(11.8,4.3),layout="constrained")
 ax.imshow(matrix,aspect="auto",cmap="viridis")
 ax.set_yticks(range(3),[f.removeprefix("P") for f in FAMILIES])
 ax.set_xticks(range(6),CITIES,rotation=21,ha="right")
 for i in range(3):
  for k in range(6):
   x=matrix[i,k]
   ax.text(k,i,f"{x/1000:.1f} mil",ha="center",va="center",fontsize=9,color="white" if x>70000 else "black")
 ax.set_title("População dentro de 10 km do ponto de estudo associado a cada cidade",loc="left",fontsize=13,fontweight="bold")
 ax.set_xlabel("O nome identifica o mercado urbano associado; não garante que o círculo inclua o centro da cidade.")
 fig.text(.08,.01,"INE 2021. Os pontos são apenas referências G13A de faixas de estudo, não estações ou acessos validados.",fontsize=9)
 fig.savefig(city_chart,dpi=160,bbox_inches="tight")
 plt.close(fig)
 to3763=Transformer.from_crs(4326,3763,always_xy=True)
 to4326=Transformer.from_crs(3763,4326,always_xy=True)
 features=[]
 for c in cases:
  if c["research_geographic_radius_km"] not in (10,20):continue
  x,y=to3763.transform(*c["chosen_original_G13A_research_lonlat"])
  circle=Point(x,y).buffer(c["research_geographic_radius_km"]*1000.,quad_segs=32)
  polygon=transform(to4326.transform,circle)
  features.append({"type":"Feature","geometry":mapping(polygon),
   "properties":{"study_corridor":c["research_corridor"],"associated_urban_market":c["urban_market"],
    "radius_km":c["research_geographic_radius_km"],
    "census_residents_2021_representative_subsection_method":c["centroid_or_interior_point_population_counts"]["N_INDIVIDUOS"],
    "census_residents_2021_area_weighted_sensitivity":c["area_weighted_uniform_within_subsection_population_estimates"]["N_INDIVIDUOS"],
    "geographic_buffer_is_NOT_a_road_travel_isochrone":True,
    "research_reference_is_NOT_a_rail_station":True,
    "centre_of_named_urban_market_may_be_outside_circle":True}})
 geojson.parent.mkdir(parents=True,exist_ok=True)
 geojson.write_text(json.dumps({"type":"FeatureCollection",
   "name":"G14 2021 census resident geographic envelopes around research points, NOT real stations","features":features},ensure_ascii=False)+"\n")
 print("G14B_VISUALS="+json.dumps({"circles":len(features),"union10":vals10,"union20":vals20,"cities_population10km":matrix.tolist()},ensure_ascii=False,separators=(',',':')))
def main():
 a=argparse.ArgumentParser()
 for n in ("input","unions","cities","geojson"):a.add_argument("--"+n,required=True,type=Path)
 q=a.parse_args();plot(q.input,q.unions,q.cities,q.geojson)
if __name__=="__main__":main()
