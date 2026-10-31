#!/usr/bin/env python3
"""B1 road/reief acquisition survey for mandatory Vila Real and Bragança.

Real OSM road geometries incl. motorway/links/primary/secondary are acquired,
then road *Euclidean proximity* and real GLO30 DSM relief are measured for
2km grid research sectors around both mandatory service territories.

Close to motorway does NOT establish station accessibility by road network;
A4/IP4 is reference, not a railway alignment. NO Sanabria. No scoring of
railway grade, tunnel length, track radius or station construction feasibility.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from datetime import datetime,timezone

CITY={
    "Vila_Real":{"centre_wgs84":[-7.744,41.3006],"osm_bbox":[41.17,-7.93,41.45,-7.52]},
    "Braganca":{"centre_wgs84":[-6.7576,41.8060],"osm_bbox":[41.67,-6.96,41.94,-6.52]},
}
SOURCE_ORIGINS=("https://overpass.kumi.systems/api/interpreter",
                "https://overpass-api.de/api/interpreter")
ROAD_CLASSES=("motorway","motorway_link","trunk","trunk_link","primary","primary_link","secondary","secondary_link")
ROAD_CLASSES_RE="motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link"
MAX_SOURCE_BYTES_PER_CITY=20_000_000
DSM_SHA256="a708b502b2eb86236c70f2d74322e9d8e2ea1417eb24094d0e43536845407bd9"
ROAD_GEO="B1-PT-A4-IP4-mandatory-city-road-reference-OSM.geojson"
CANDIDATE="B1-PT-VilaReal-Braganca-2km-sector-priorities.json"

def _overpass_query(city):
    if city not in CITY:raise ValueError("unknown_mandatory_city")
    south,west,north,east=CITY[city]["osm_bbox"]
    return (f'[out:json][timeout:85];way["highway"~"^({ROAD_CLASSES_RE})$"]'
            f'({south},{west},{north},{east});out tags geom;')

def fetch(city):
    q=_overpass_query(city).encode()
    err_types=[]
    for endpoint in SOURCE_ORIGINS:
        try:
            req=Request(endpoint,data=urlencode({"data":q.decode()}).encode(),
                headers={"Content-Type":"application/x-www-form-urlencoded",
                         "User-Agent":"MobilidadeNorte-MN-GEO-RAIL-B1/1.0"},method="POST")
            with urlopen(req,timeout=100) as response:
                if response.status!=200:raise ValueError("overpass_non200")
                raw=response.read(MAX_SOURCE_BYTES_PER_CITY+1)
            if len(raw)>MAX_SOURCE_BYTES_PER_CITY:raise ValueError("road_source_over_byte_budget")
            d=json.loads(raw)
            items=d.get("elements")
            if not isinstance(items,list) or not 40<=len(items)<=8000:
                raise ValueError("unexpected_OSM_road_segments_count")
            return endpoint,hashlib.sha256(raw).hexdigest(),len(raw),items
        except Exception as e:
            err_types.append(type(e).__name__)
    raise RuntimeError("both_bounded_OSM_road_sources_unavailable:"+",".join(err_types))

def _lines(city,records):
    geo=[]
    for x in records:
        if not isinstance(x,dict) or x.get("type")!="way":
            continue
        tags=x.get("tags") or {}
        klass=tags.get("highway")
        if klass not in ROAD_CLASSES:continue
        coords=[(p["lon"],p["lat"]) for p in x.get("geometry",[]) if isinstance(p,dict) and "lon" in p and "lat" in p]
        if len(coords)<2 or len(coords)>5000:continue
        geo.append({"type":"Feature","geometry":{"type":"LineString","coordinates":[list(c) for c in coords]},
                    "properties":{"city_scope":city,"OSM_way_id":int(x["id"]),"highway":klass,
                                  "ref":str(tags.get("ref",""))[:70],
                                  "name":str(tags.get("name",""))[:140]}})
    if len(geo)<20:raise ValueError("insufficient_georeferenced_road_ways")
    return geo

def sample_DSM(dsm,poly):
    import numpy as np
    from rasterio.windows import from_bounds
    from rasterio.windows import Window
    x0,y0,x1,y1=poly
    win=from_bounds(x0,y0,x1,y1,transform=dsm.transform)
    window=Window(col_off=max(0,math.floor(win.col_off)),
                  row_off=max(0,math.floor(win.row_off)),
                  width=max(1,math.ceil(win.width)+1),
                  height=max(1,math.ceil(win.height)+1))
    d=dsm.read(1,window=window,masked=True).compressed()
    if d.size<100:return None
    return {"robust_surface_relief_P95_minus_P05_m":float(np.percentile(d,95)-np.percentile(d,5)),
            "surface_min_m":float(d.min()),"surface_max_m":float(d.max()),"sampled_actual_DSM_cells":int(d.size)}

def candidate_sectors(city,roads,dsm):
    import pyproj
    from shapely.geometry import LineString,Point
    from shapely.ops import transform
    import numpy as np
    from pyproj import Transformer
    xform=Transformer.from_crs(4326,3763,always_xy=True)
    inverse=Transformer.from_crs(3763,4326,always_xy=True)
    lon,lat=CITY[city]["centre_wgs84"]
    cx,cy=xform.transform(lon,lat)
    segs=[]
    for f in roads:
        if f["properties"]["city_scope"]!=city:continue
        line=LineString(f["geometry"]["coordinates"])
        if line.length==0:continue
        xy=transform(xform.transform,line)
        segs.append((xy,f["properties"]["highway"],f["properties"].get("ref","")))
    primary=[l for l,k,ref in segs if k in ("primary","primary_link","secondary","secondary_link")]
    major=[l for l,k,ref in segs if k in ("motorway","motorway_link","trunk","trunk_link")]
    if not primary or not major:raise ValueError("required local road classes missing")
    cells=[]
    xmin=math.floor((cx-12000)/2000)*2000
    ymin=math.floor((cy-12000)/2000)*2000
    for x in range(int(xmin),int(cx+12000),2000):
        for y in range(int(ymin),int(cy+12000),2000):
            mid=Point(x+1000,y+1000)
            distance_city_km=mid.distance(Point(cx,cy))/1000
            if distance_city_km<2 or distance_city_km>12:continue
            # actual WGS84 polygon envelope for sampling, not a track path
            corners=[inverse.transform(xx,yy) for xx,yy in ((x,y),(x+2000,y),(x+2000,y+2000),(x,y+2000))]
            bbox=[min(z[0] for z in corners),min(z[1] for z in corners),
                  max(z[0] for z in corners),max(z[1] for z in corners)]
            dsm_q=sample_DSM(dsm,bbox)
            if not dsm_q:continue
            local_dist=min(mid.distance(r) for r in primary)
            highway_dist=min(mid.distance(r) for r in major)
            # discovery class only: proximity is NOT road drive-time, junction or network reachability
            interest=(local_dist<=1200 and highway_dist<=4000)
            cells.append({
                "id":f"{city}_E{x}_N{y}","city":city,"sector_EPSG3763":[x,y,x+2000,y+2000],
                "sector_WGS84_bbox_proxy":bbox,
                "city_straightline_distance_km":round(distance_city_km,2),
                "minimum_Euclidean_distance_to_mapped_local_major_road_m":round(local_dist),
                "minimum_Euclidean_distance_to_motorway_or_trunk_m":round(highway_dist),
                "road_connected_station_access_proven":False,
                "station_location_assigned":False,
                "inside_peripheral_road_proximity_discovery_threshold":bool(interest),
                "DSM_is_surface_not_terrestrial_DTM":True,
                "DSM_terrain_metric_cannot_predict_railway_grade":True,
                "DSM":dsm_q})
    return cells

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verified-dsm",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    import rasterio
    if hashlib.sha256(a.verified_dsm.read_bytes()).hexdigest()!=DSM_SHA256:
        raise ValueError("incorrect_or_superseded_GLO30_DSM_revision")
    sources=[];ways=[]
    for city in CITY:
        endpoint,sha,n,entries=fetch(city)
        extracted=_lines(city,entries)
        ways.extend(extracted)
        sources.append({"city":city,"OSM_date_of_observation_utc":datetime.now(timezone.utc).isoformat(),
                        "api_endpoint":endpoint,"OSM_response_SHA256":sha,"bytes":n,
                        "road_ways_with_geometry":len(extracted),"bbox_wgs84":CITY[city]["osm_bbox"]})
    a.output.mkdir(parents=True,exist_ok=True)
    geo={"type":"FeatureCollection","metadata":{
        "source":"OpenStreetMap contributors through bounded Overpass, ODbL",
        "licence_url":"https://www.openstreetmap.org/copyright",
        "not_official_transport_road_inventory":True,
        "road_geometry_is_not_rail_alignment":True,
        "OSM_source_response_sha256_by_city":sources},"features":ways}
    (a.output/ROAD_GEO).write_text(json.dumps(geo,separators=(",",":"),ensure_ascii=False)+"\n")
    with rasterio.open(a.verified_dsm) as ds:
        if ds.crs is None or ds.crs.to_epsg()!=4326 or ds.count!=1:
            raise ValueError("incorrect_base_DSM")
        sectors=[]
        for city in CITY: sectors.extend(candidate_sectors(city,ways,ds))
    result={"mission":"MN-GEO-RAIL-001","stage":"B1_real_road_network_plus_30m_DSM_2km_peripheral_research_sectors",
        "mandatory_service_areas":["Vila Real","Bragança"],
        "no_center_station_required":True,"Sanabria_excluded":True,
        "producer_road":"OpenStreetMap contributors; third-party road network reference, ODbL",
        "official_road_reference":"A4/IP4 (IP); Spain N-122 official, not rail alignment",
        "road_geometry_receipt":ROAD_GEO,"sources":sources,
        "road_ways_total":len(ways),"base_DSM_original_release_SHA256":DSM_SHA256,
        "street_network_accessibility_time_verified":False,
        "motorway_direct_access_to_stations_verified":False,
        "bare_earth_vertical_terrain_accuracy_verified":False,
        "railway_station_siting_approved":False,
        "DGT_2m_source_rasters_newly_downloaded":0,
        "Fxx_accepted":False,"site_authorized":False,
        "research_sectors":sectors,
        "sectors_total":len(sectors),
        "road_proximity_screen_count":sum(x["inside_peripheral_road_proximity_discovery_threshold"] for x in sectors),
        "road_proximity_screen_by_city":{city:sum(x["city"]==city and x["inside_peripheral_road_proximity_discovery_threshold"] for x in sectors) for city in CITY}}
    if result["road_proximity_screen_count"]<4 or any(n<2 for n in result["road_proximity_screen_by_city"].values()):
        raise ValueError("road_proximity_review_has_insufficient_candidates")
    (a.output/CANDIDATE).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"status":"B1_SECONDARY_ROAD_GEOMETRY_AND_DSM_RESEARCH_SECTORS_CREATED",
      "roads":len(ways),"sectors_total":len(sectors),
      "screened":result["road_proximity_screen_by_city"],
      "mandatory_nodes":["Vila Real","Bragança"]}))
if __name__=="__main__":main()
