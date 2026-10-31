#!/usr/bin/env python3
"""B1 source-backed original DGT 2m 2×2 km grids for two mandatory cities.

Read ONLY five previously verified anonymous producer STAC query receipts.
Generate balanced competing 2×2 original-tile groups in peripheries of
MANDATORY Vila Real and Bragança, independently of station-centre assumptions.
Metadata tile groups are NOT native data, highway access nor route geometry.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re
from pathlib import Path
from collections import defaultdict

SOURCE_SPECS=(
("E01-E06","pt-dgt-mdt-sector-footprints.json",12),
("G07","pt-dgt-vilareal-mirandela-anonymous-strip.json",20),
("G08","pt-dgt-porto-vilareal-anonymous-strip.json",32),
("G09","pt-dgt-macedo-braganca-anonymous-strip.json",48),
("G10","pt-dgt-g10-g08-g07-interface-anonymous-strip.json",4),
)
SITES={"Vila Real":(-7.744,41.3006),"Bragança":(-6.7576,41.806)}
REGEX=re.compile(r"^MDT-2m-(\d{3})(\d{3})-(\d{2})-(\d{4})$")
def inventory(source):
    d=Path(source)
    by_key={}
    proofs=[]
    for label,name,expected in SOURCE_SPECS:
        raw=(d/name).read_bytes()
        root=json.loads(raw)
        rows=root.get("requests") if label=="E01-E06" else root.get("responses")
        if not isinstance(rows,list) or len(rows)!=expected:raise ValueError("incomplete_source_STAC_queries_"+label)
        for q in rows:
            if q.get("collection")!="MDT-2m":continue
            for f in q.get("footprints",[]):
                z=f.get("tile_id")
                p=REGEX.fullmatch(str(z))
                if not p:raise ValueError("unexpected_DGT_2m_tile_identifier")
                c,r=int(p.group(1)),int(p.group(2))
                b=f.get("bbox_wgs84")
                if not isinstance(b,list) or len(b)!=4:raise ValueError("missing_geometry_bbox")
                current=by_key.get((c,r))
                proposal={"id":z,"bbox":b,"col":c,"row":r,"edition_month":int(p.group(3)),
                          "edition_year":int(p.group(4)),"source":label}
                # prefer latest producer edition of EXACT native grid coordinate
                if current is None or (proposal["edition_year"],proposal["edition_month"])>(current["edition_year"],current["edition_month"]):
                    by_key[(c,r)]=proposal
        proofs.append({"label":label,"filename":name,"sha256":hashlib.sha256(raw).hexdigest(),
                       "query_count":expected})
    if len(proofs)!=5:raise ValueError("incomplete_metadata_sources")
    return by_key,proofs

def shortlist(by_key):
    groups=[]
    for city,(lon,lat) in SITES.items():
        for (col,row),v in by_key.items():
            tiles=[by_key.get((col+dc,row+dr)) for dr in (0,1) for dc in (0,1)]
            if any(z is None for z in tiles):continue
            xmin=min(x["bbox"][0] for x in tiles);xmax=max(x["bbox"][2] for x in tiles)
            ymin=min(x["bbox"][1] for x in tiles);ymax=max(x["bbox"][3] for x in tiles)
            cx,cy=(xmin+xmax)/2,(ymin+ymax)/2
            dx=(cx-lon)*111.195*math.cos(math.radians(lat));dy=(cy-lat)*111.195
            distance=math.hypot(dx,dy)
            if not 3<=distance<=13:continue
            direction=("E" if dx>0 else "W") if abs(dx)>abs(dy) else ("N" if dy>0 else "S")
            groups.append({"city":city,"quadrant":direction,"source_grid_2by2_km_epsg3763":
                [(col-200)*1000,(row-301)*1000,(col-198)*1000,(row-299)*1000],
                "source_2m_native_tile_ids":[z["id"] for z in tiles],
                "producer_STAC_bbox_proxy_wgs84":[xmin,ymin,xmax,ymax],
                "straight_line_distance_to_city_centre_km":round(distance,2),
                "source_pixels_currently_acquired_for_this_group":False,
                "road_network_station_access_distance_measured":False,
                "MDS_terrain_derived_railway_gradient_measured":False,
                "is_candidate_station":False,
                "is_railway_alignment":False})
    selected=[]
    for city in SITES:
        used=set()
        for direction in ("W","E","N","S"):
            pool=sorted((z for z in groups if z["city"]==city and z["quadrant"]==direction),
                  key=lambda z:abs(z["straight_line_distance_to_city_centre_km"]-7))
            for row in pool:
                ids=set(row["source_2m_native_tile_ids"])
                if not(ids&used):
                    selected.append(row);used.update(ids);break
    return selected,groups

def run(d):
    by_key,proofs=inventory(d)
    review,allgroups=shortlist(by_key)
    out={"mission":"MN-GEO-RAIL-001","stage":"B1_mandatory_city_DGT_official_source_candidate_2x2km_groups",
        "country":"Portugal","mandatory_service_cities":list(SITES),
        "stations_in_city_centres_required":False,
        "Sanabria_excluded":True,
        "producer":"Direção-Geral do Território, original public metadata STAC",
        "screened_source_receipts":proofs,
        "candidate_product_grids_from_official_metadata":len(by_key),
        "possible_2by2km_groups_near_mandatory_cities":len(allgroups),
        "review_only_source_tile_groups":review,
        "review_groups_count":len(review),
        "review_groups_by_city":{city:len([r for r in review if r["city"]==city]) for city in SITES},
        "no_current_original_DGT_raster_bytes_downloaded":True,
        "no_road_network_geometry_used_to_finalize_station_sites":True,
        "use_real_road_geometry_and_terrain_before_protected_DGT_acquisition":True,
        "register_for_manual_only_protected_main_environment_dgt_cdd":True,
        "Fxx_accepted":False,"Site_authorized":False}
    return out
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reports",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    z=run(a.reports)
    if any(not z["review_groups_by_city"][s] for s in SITES):
        raise ValueError("one_mandatory_city_has_no_reviewed_2by2_candidate_grids")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(z,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    print(json.dumps({"status":"DGT_TWO_MANDATORY_CITIES_REVIEWED_TILE_GROUPS",
        "group_count":z["review_groups_count"],
        "city_groups":z["review_groups_by_city"],
        "metadata_grids_count":z["candidate_product_grids_from_official_metadata"]}))
if __name__=="__main__":main()
