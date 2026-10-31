#!/usr/bin/env python3
"""C1 actual bare-earth DTM acquisition, 2 separate candidate N-122 research panels.

Mandatory service territories for overall mission: Vila Real + Bragança.
NO Sanabria. Neither Spanish site is a compelled railway via-point.
Each source panel = 8×6 km from 12 independently requested IGN/CNIG WCS
Elevacion25830_5 2×2km GeoTIFF responses. Keep native WCS-response bytes
and a joined losslessly compressed 5m mosaic per site; preserve SHA256.
No interpolation, no source pixels fabricated, no vertical claim.
"""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import numpy as np

SERVICE="https://servicios.idee.es/wcs-inspire/mdt"
COVERAGE="Elevacion25830_5"
RES=5
BLOCK=2000
SITE_BOXES={
    "Alcanices":[218000,4619000,226000,4625000],
    "Muelas_del_Pan":[248000,4597000,256000,4603000],
}
SITE_WGS84_REFERENCE={
    "Alcanices":[-6.346470,41.699400],
    "Muelas_del_Pan":[-5.970320,41.520980],
}
MAX_SOURCE_RESPONSE_BYTES=2_000_000
MAX_ALL_RESPONSE_BYTES=50_000_000
DERIVED_NODATA=-32768
REQUIRED_NOTICE="Instituto Geografico Nacional (IGN) / Centro Nacional de Informacion Geografica (CNIG), Spain. CC BY 4.0 attribution required."
LICENCE="https://datos.gob.es/es/catalogo/e0dat0002-wcs-de-modelos-digitales-del-terreno-de-espana1"

def site_blocks(site):
    if site not in SITE_BOXES:raise ValueError("unapproved study panel")
    west,south,east,north=SITE_BOXES[site]
    if (east-west,north-south)!=(8000,6000):raise ValueError("site panel not 8kmx6km")
    return [(r,c,[west+2000*c,south+2000*r,west+2000*(c+1),south+2000*(r+1)])
             for r in range(3) for c in range(4)]

def url_for(bbox):
    if not (isinstance(bbox,list) and len(bbox)==4 and all(type(x)==int for x in bbox)
        and (bbox[2]-bbox[0],bbox[3]-bbox[1])==(2000,2000)
        and 150000<=bbox[0]<bbox[2]<=350000 and 4550000<=bbox[1]<bbox[3]<=4700000):
        raise ValueError("WCS request not in approved bounded 2km grid")
    q=[("service","WCS"),("request","GetCoverage"),("version","2.0.1"),
       ("coverageId",COVERAGE),("format","image/tiff"),
       ("subset",f"x({bbox[0]},{bbox[2]})"),("subset",f"y({bbox[1]},{bbox[3]})")]
    return SERVICE+"?"+urlencode(q)

def inspect_source(path,bbox):
    import rasterio
    with rasterio.open(path) as ds:
        if (ds.driver!="GTiff" or ds.crs is None or ds.crs.to_epsg()!=25830
            or ds.count!=1 or (ds.width,ds.height)!=(400,400)
            or any(abs(a-b)>0.001 for a,b in zip(ds.bounds,bbox))
            or any(abs(v-RES)>0.001 for v in ds.res)):
            raise ValueError("wrong_source_WCS_GeoTIFF_shape_or_CRS")
        vals=ds.read(1,masked=True)
        if vals.count()!=vals.size:
            raise ValueError("source_WCS_contains_NoData")
        z=vals.compressed()
        if not np.isfinite(z).all() or z.min()<-500 or z.max()>4000:
            raise ValueError("source_WCS_elevation_values_unexpected")
        return {"bbox_epsg25830":bbox,"valid_pixels":int(vals.count()),
                "nodata_pixels":0,"dtype":ds.dtypes[0],
                "min_terrain_m":float(z.min()),"max_terrain_m":float(z.max()),
                "vertical_CRS_encoded_in_GeoTIFF":("VERTCRS[" in ds.crs.to_wkt() or "VERT_CS[" in ds.crs.to_wkt())}

def download_response(site,row,col,bbox,folder):
    name=f"{site}-r{row}-c{col}-IGN-CNIG-MDT5m-WCS-response.tif"
    dest=folder/name
    src=url_for(bbox)
    sha=hashlib.sha256();count=0
    with urlopen(Request(src,headers={"User-Agent":"MN-GEO-RAIL-001-C1-5m-ground/1"}),timeout=50) as response, dest.open("wb") as out:
        if response.status!=200:
            raise ValueError("official_WCS_did_not_return_200")
        while True:
            part=response.read(256*1024)
            if not part:break
            count+=len(part)
            if count>MAX_SOURCE_RESPONSE_BYTES:raise ValueError("bounded_WCS_response_too_large")
            sha.update(part);out.write(part)
    if count<1000:raise ValueError("source_WCS_5m_empty")
    raster=inspect_source(dest,bbox)
    return {"site":site,"row":row,"col":col,"bbox_epsg25830":bbox,
        "file":name,"source_response_url":src,
        "bytes":count,"sha256":sha.hexdigest(),"raster":raster,
        "source_type":"actual GetCoverage 5m GeoTIFF response NOT original CNIG repository 5m archive tile"}

def combine_site(site,folder,blocks):
    import rasterio
    from rasterio.transform import from_origin
    west,south,east,north=SITE_BOXES[site]
    height=(north-south)//RES
    width=(east-west)//RES
    result=np.full((height,width),DERIVED_NODATA,dtype="int16")
    for info in blocks:
        with rasterio.open(folder/info["file"]) as ds:
            values=ds.read(1,masked=True)
            if values.count()!=values.size:raise ValueError("masked source unexpectedly")
            row=info["row"];col=info["col"]
            # Source rows run north->south; row index counts from south->north.
            y=(2-row)*400
            x=col*400
            values=values.data
            if values.dtype!=np.int16:
                raise ValueError("actual WCS response not int16; revise derivation intentionally")
            result[y:y+400,x:x+400]=values
    if int(np.count_nonzero(result==DERIVED_NODATA))!=0:raise ValueError("site panel has pixel gaps")
    mosaic=folder/f"{site}-IGN-CNIG-5m-ground-8x6km-MOSAIC.tif"
    with rasterio.open(mosaic,"w",driver="GTiff",width=width,height=height,count=1,
      dtype="int16",crs="EPSG:25830",transform=from_origin(west,north,RES,RES),
      nodata=DERIVED_NODATA,tiled=True,blockxsize=400,blockysize=400,
      compress="DEFLATE",predictor=2,zlevel=6) as dst:
        dst.write(result,1)
        dst.update_tags(PRODUCER=REQUIRED_NOTICE,
            ORIGINAL_SOURCE="12 individual IGN/CNIG WCS MDT5m GeoTIFF response files",
            ORIGINAL_PRODUCT_CLASS="Digital terrain model (DTM), not DSM",
            PREACCEPTANCE="NOT a railway alignment; no datum control or geodetic correction")
    re=inspect_joined(site,mosaic,blocks,folder)
    return {"file":mosaic.name,"sha256":hashlib.sha256(mosaic.read_bytes()).hexdigest(),
            "bytes":mosaic.stat().st_size,"QA":re}

def inspect_joined(site,path,blocks,folder):
    import rasterio
    west,south,east,north=SITE_BOXES[site]
    with rasterio.open(path) as ds:
        if (ds.crs is None or ds.crs.to_epsg()!=25830 or ds.driver!="GTiff"
            or ds.count!=1 or (ds.width,ds.height)!=(1600,1200)
            or any(abs(a-b)>0.001 for a,b in zip(ds.bounds,(west,south,east,north)))):
            raise ValueError("wrong_48km2_joined_5m_GeoTIFF")
        raw=ds.read(1,masked=True)
        if raw.count()!=1_920_000:raise ValueError("joined_WCS_contains_nodata")
        z=raw.data
        for b in blocks:
            y=(2-b["row"])*400
            x=b["col"]*400
            with rasterio.open(folder/b["file"]) as check:
                original=check.read(1)
            if not np.array_equal(z[y:y+400,x:x+400],original):
                raise ValueError("source_WCS_pixels_changed_in_derived_mosaic")
        meridians=[]
        for x in (400,800,1200):
            valid=int(np.count_nonzero(z[:,x-1]!=DERIVED_NODATA & (z[:,x]!=DERIVED_NODATA))) if False else int((np.logical_and(z[:,x-1]!=DERIVED_NODATA,z[:,x]!=DERIVED_NODATA)).sum())
            if valid!=1200:raise ValueError("missing_WCS_vertical_source_seam")
            meridians.append({"boundary_col":x,"valid_neighbor_pairs":valid})
        parallels=[]
        for y in (400,800):
            valid=int((np.logical_and(z[y-1,:]!=DERIVED_NODATA,z[y,:]!=DERIVED_NODATA)).sum())
            if valid!=1600:raise ValueError("missing_WCS_horizontal_source_seam")
            parallels.append({"boundary_row":y,"valid_neighbor_pairs":valid})
        return {"real_valid_ground_cells":int(raw.count()),"NoData":0,
          "bbox_epsg25830":[west,south,east,north],
          "grid_px":[1600,1200],"nominal_pixel_m":5,
          "source_5m_blocks_verified_byte_for_byte_in_derived_GeoTIFF":len(blocks),
          "vertical_tile_meridian_seams":meridians,
          "horizontal_tile_parallel_seams":parallels,
          "range_ground_height_m":[int(z.min()),int(z.max())],
          "vertical_datum_independent_control":False,
          "station_candidate_or_rail_alignment_validated":False}

def run(folder):
    folder.mkdir(parents=True,exist_ok=True)
    doc={"mission":"MN-GEO-RAIL-001","stage":"C1_two_N122_reference_zones_real_IGN_CNIG_DTM5m",
       "observed_utc":datetime.now(timezone.utc).isoformat(),
       "mandatory_PT_nodes":["Vila Real","Bragança"],
       "service_requirement":"both cities obligatory but railway stations may be peripheral",
       "route_not_selected":True,"Sanabria_excluded_from_active_acquisition":True,
       "road_reference_only":"A4/IP4 then Spanish N-122, NOT a railway alignment",
       "producer":"Instituto Geográfico Nacional (IGN)/Centro Nacional de Información Geográfica (CNIG), Spain",
       "licence":"CC BY 4.0 with IGN/CNIG attribution","licence_source":LICENCE,
       "original_producer_tile_archive_rehosted":False,
       "source_is_actual_WCS_response_not_archived_producer_COG":True,
       "sample_regions_are_disjoint":True,
       "territorial_extent_total_km2":96,
       "terrain_5m_valid_cells_total":0,"real_WCS_response_assets":0,
       "national_vertical_datum_control_independently_verified":False,
       "crossborder_PT_ES_geodetic_validation":False,
       "Fxx_accepted":False,"Site_authorized":False,
       "results":[]}
    total=0
    for site in SITE_BOXES:
        records=[]
        for row,col,bbox in site_blocks(site):
            r=download_response(site,row,col,bbox,folder)
            total+=r["bytes"]
            if total>MAX_ALL_RESPONSE_BYTES:raise ValueError("total_WCS_bytes_over_budget")
            records.append(r)
        joined=combine_site(site,folder,records)
        doc["results"].append({"site":site,"reference_point_wgs84":SITE_WGS84_REFERENCE[site],
            "target_bbox_epsg25830":SITE_BOXES[site],
            "source_original_WCS_responses":records,"joined_5m_ground_panel":joined})
        doc["terrain_5m_valid_cells_total"]+=joined["QA"]["real_valid_ground_cells"]
        doc["real_WCS_response_assets"]+=len(records)
    doc["original_WCS_bytes_acquired"]=total
    (folder/"C1-IGN-CNIG-5m-N122-reference-source-QA.json").write_text(json.dumps(doc,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    return doc

def verify(folder):
    j=json.loads((folder/"C1-IGN-CNIG-5m-N122-reference-source-QA.json").read_text())
    if (j["Fxx_accepted"] or j["Site_authorized"] or
        not j["Sanabria_excluded_from_active_acquisition"] or
        j["mandatory_PT_nodes"]!=["Vila Real","Bragança"] or
        j["terrain_5m_valid_cells_total"]!=3_840_000 or
        j["real_WCS_response_assets"]!=24):
        raise ValueError("invalid_declared_acquisition_receipt")
    if set(x["site"] for x in j["results"])!=set(SITE_BOXES):
        raise ValueError("missing_source_regions")
    total=0
    for region in j["results"]:
        site=region["site"]
        blocks=region["source_original_WCS_responses"]
        if len(blocks)!=12 or {tuple(x["bbox_epsg25830"]) for x in blocks}!={tuple(x[2]) for x in site_blocks(site)}:
            raise ValueError("missing_original_source_12_block_grid")
        for b in blocks:
            p=folder/b["file"]
            if (p.stat().st_size!=b["bytes"] or p.stat().st_size>MAX_SOURCE_RESPONSE_BYTES
                 or hashlib.sha256(p.read_bytes()).hexdigest()!=b["sha256"]
                 or inspect_source(p,b["bbox_epsg25830"])!=b["raster"]):
                raise ValueError("source_WCS_original_response_changed")
            total+=b["bytes"]
        joined=region["joined_5m_ground_panel"]
        f=folder/joined["file"]
        if (f.stat().st_size!=joined["bytes"]
            or hashlib.sha256(f.read_bytes()).hexdigest()!=joined["sha256"]
            or inspect_joined(site,f,blocks,folder)!=joined["QA"]):
            raise ValueError("source_reconstructed_5m_mosaic_QA_mismatch")
    if total!=j["original_WCS_bytes_acquired"]:raise ValueError("source_bytes_accounting_disagree")
    return j

def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--acquire",type=Path)
    g.add_argument("--verify",type=Path)
    opt=p.parse_args()
    doc=run(opt.acquire) if opt.acquire else verify(opt.verify)
    print(json.dumps({"status":"SOURCE_WCS_5M_GROUND_PIXEL_QA_SUCCESS",
      "sites":[r["site"] for r in doc["results"]],
      "terrain_pixels":doc["terrain_5m_valid_cells_total"],
      "source_assets":doc["real_WCS_response_assets"],
      "area_km2":doc["territorial_extent_total_km2"],
      "original_response_bytes":doc["original_WCS_bytes_acquired"]},sort_keys=True))
if __name__=="__main__":main()
