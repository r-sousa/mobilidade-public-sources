#!/usr/bin/env python3
import base64
import csv
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests

PRIVATE_REPO=os.environ.get('PRIVATE_REPO','r-sousa/EU-transp-weekly')
PRIVATE_BRANCH=os.environ.get('PRIVATE_BRANCH','mobilidade-norte-recovery-20260919')
PUBLIC_REPO=os.environ.get('PUBLIC_REPO','r-sousa/mobilidade-public-sources')
PUBLIC_TOKEN=os.environ.get('PUBLIC_TOKEN','').strip()
READ_TOKEN=(os.environ.get('MN_PRIVATE_READ_TOKEN','').strip() or os.environ.get('PRIVATE_READ_TOKEN','').strip() or os.environ.get('MN_PRIVATE_SINK_TOKEN','').strip())
WRITE_TOKEN=(os.environ.get('MN_PRIVATE_SINK_TOKEN','').strip() or os.environ.get('PRIVATE_SINK_TOKEN','').strip())
SOURCE_ID='F68'
MISSION_GENERATION=54
RUN_ID=35415911461
ARTIFACT_ID=10576315158
ARTIFACT_NAME='mn26-dgt-cos-35415911461'
WRAPPER_BYTES=897711292
WRAPPER_SHA='9e3889f0999a7567a6442d1d44e309ae283efb7fdf0507ff4245657fb526df75'
RAW_MEMBER='F68-COS2023v1-S2-source.zip'
RAW_BYTES=898115957
RAW_SHA='276ad30496322e95a3a4cf5c8804cd203b841bb88827eca1f1ea8d0a9945aa07'
INNER_GPKG='COS2023v1-S2.gpkg'
INNER_BYTES=1559359488
EXPECTED_EPSG=3763
REQUEST_PATH=f'extraction_requests/F68-{RAW_SHA}.json'
PUBLIC_RESULT=f'extraction_results/F68-{RAW_SHA}-g54.json'
OUT_BASE='statistics/recovery-20260920/simple-runtime/outputs/W2C/20260922T1931PT-G54-F68-extraction-ingress'
CANONICAL_RECEIPT=f'statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F68/{RAW_SHA}-extraction.json'
WORKER_PATH='statistics/recovery-20260920/simple-runtime/worker-W2C.json'
TEAM_PATH='statistics/recovery-20260920/simple-runtime/team-missions.json'
DESC_RELEASE_TAG='mn-x-f68-276ad30496322e95a3a4-g54'
DESC_ASSET_NAME='F68-COS2023v1-S2-Norte-envelope.gpkg.zip'
USER_AGENT='MobilidadeNorte-F68Extractor/1.0'

class Gate(Exception):
    pass

def sha256_file(path, chunk=8*1024*1024):
    h=hashlib.sha256(); n=0
    with open(path,'rb') as fh:
        while True:
            b=fh.read(chunk)
            if not b: break
            n += len(b); h.update(b)
    return n,h.hexdigest()

def gh_headers(token, accept='application/vnd.github+json'):
    return {'Authorization':'Bearer '+token,'Accept':accept,'User-Agent':USER_AGENT,'X-GitHub-Api-Version':'2022-11-28'}

def api_json(method,url,token,body=None,timeout=180):
    r=requests.request(method,url,headers=gh_headers(token),json=body,timeout=timeout)
    if r.status_code >= 400:
        raise Gate(f'GITHUB_API_{method}_{r.status_code}:{url}:{r.text[:500]}')
    return r.json() if r.content else None

def get_private_content(path):
    url=f'https://api.github.com/repos/{PRIVATE_REPO}/contents/{urllib.parse.quote(path,safe="/")}?ref={urllib.parse.quote(PRIVATE_BRANCH)}'
    obj=api_json('GET',url,READ_TOKEN)
    return obj, base64.b64decode(obj['content'])

def put_private_content(path,data,message):
    url=f'https://api.github.com/repos/{PRIVATE_REPO}/contents/{urllib.parse.quote(path,safe="/")}'
    existing=None
    r=requests.get(url,headers=gh_headers(WRITE_TOKEN),params={'ref':PRIVATE_BRANCH},timeout=180)
    if r.status_code==200:
        existing=r.json()
        old=base64.b64decode(existing['content'])
        if old==data:
            return {'unchanged':True,'sha':existing['sha']}
    elif r.status_code!=404:
        raise Gate(f'PRIVATE_CONTENT_GET_{r.status_code}:{path}:{r.text[:500]}')
    body={'message':message,'branch':PRIVATE_BRANCH,'content':base64.b64encode(data).decode('ascii')}
    if existing: body['sha']=existing['sha']
    rr=requests.put(url,headers=gh_headers(WRITE_TOKEN),json=body,timeout=300)
    if rr.status_code not in (200,201):
        raise Gate(f'PRIVATE_CONTENT_PUT_{rr.status_code}:{path}:{rr.text[:500]}')
    return rr.json()

def put_public_content(path,data,message):
    if not PUBLIC_TOKEN: return None
    url=f'https://api.github.com/repos/{PUBLIC_REPO}/contents/{urllib.parse.quote(path,safe="/")}'
    r=requests.get(url,headers=gh_headers(PUBLIC_TOKEN),params={'ref':'main'},timeout=120)
    existing=r.json() if r.status_code==200 else None
    if r.status_code not in (200,404):
        raise Gate(f'PUBLIC_CONTENT_GET_{r.status_code}:{path}:{r.text[:500]}')
    if existing and base64.b64decode(existing['content'])==data:
        return {'unchanged':True,'sha':existing['sha']}
    body={'message':message,'branch':'main','content':base64.b64encode(data).decode('ascii')}
    if existing: body['sha']=existing['sha']
    rr=requests.put(url,headers=gh_headers(PUBLIC_TOKEN),json=body,timeout=180)
    if rr.status_code not in (200,201):
        raise Gate(f'PUBLIC_CONTENT_PUT_{rr.status_code}:{path}:{rr.text[:500]}')
    return rr.json()

def current_team_guard():
    if not READ_TOKEN:
        raise Gate('MN_PRIVATE_READ_CREDENTIAL_MISSING')
    _,raw=get_private_content(TEAM_PATH)
    team=json.loads(raw.decode('utf-8'))
    if int(team.get('mission_generation',-1))!=MISSION_GENERATION:
        raise Gate(f'MISSION_GENERATION_CHANGED:{team.get("mission_generation")}')
    w2c=((team.get('teams') or {}).get('W2') or {}).get('C') or {}
    mission=str(w2c.get('mission',''))
    if 'F68' not in mission or 'deterministic extraction' not in mission.lower():
        raise Gate('W2C_F68_MISSION_NOT_CURRENT')
    if 'F68_EXACT_PRESERVED_EXTRACTION' not in str(w2c.get('elastic_state','')):
        raise Gate(f'W2C_ELASTIC_STATE_NOT_F68:{w2c.get("elastic_state")}')
    return team

def download_wrapper(primary_path, alt_path):
    url=f'https://api.github.com/repos/{PRIVATE_REPO}/actions/artifacts/{ARTIFACT_ID}/zip'
    # Primary preserved-object recovery attempt: streaming authenticated REST download.
    try:
        with requests.get(url,headers=gh_headers(READ_TOKEN,'application/vnd.github+json'),stream=True,allow_redirects=True,timeout=(30,300)) as r:
            if r.status_code >= 400:
                raise Gate(f'PRIMARY_ACTIONS_ARTIFACT_HTTP_{r.status_code}:{r.text[:300]}')
            h=hashlib.sha256(); n=0
            with open(primary_path,'wb') as fh:
                for chunk in r.iter_content(8*1024*1024):
                    if chunk:
                        fh.write(chunk); h.update(chunk); n+=len(chunk)
        if n==WRAPPER_BYTES and h.hexdigest()==WRAPPER_SHA:
            return primary_path, {'route':'authenticated_rest_stream','bytes':n,'sha256':h.hexdigest(),'verified':True}
        raise Gate(f'PRIMARY_WRAPPER_IDENTITY_MISMATCH:bytes={n}:sha256={h.hexdigest()}')
    except Exception as e:
        primary_error=str(e)
    # Exactly one alternate preserved-object recovery attempt: curl on the same immutable artifact endpoint.
    env=os.environ.copy()
    cmd=['curl','--fail','--silent','--show-error','--location','--header',f'Authorization: Bearer {READ_TOKEN}','--header','Accept: application/vnd.github+json','--header','X-GitHub-Api-Version: 2022-11-28','--output',str(alt_path),url]
    p=subprocess.run(cmd,env=env,text=True,capture_output=True)
    if p.returncode!=0:
        raise Gate(f'PRESERVED_OBJECT_RECOVERY_EXHAUSTED:primary={primary_error};alternate_curl={p.stderr[-800:]}')
    n,sha=sha256_file(alt_path)
    if n!=WRAPPER_BYTES or sha!=WRAPPER_SHA:
        raise Gate(f'ALTERNATE_WRAPPER_IDENTITY_MISMATCH:primary={primary_error};bytes={n};sha256={sha}')
    return alt_path, {'route':'alternate_curl_same_immutable_artifact','bytes':n,'sha256':sha,'verified':True,'primary_error':primary_error}

def gpkg_header_scan(conn,layer,geom_col,srs_id):
    total=0; invalid=0; srs_mismatch=0; empty=0; envelope_types={}; geom_bytes=0
    q=f'SELECT "{geom_col.replace(chr(34),chr(34)*2)}" FROM "{layer.replace(chr(34),chr(34)*2)}"'
    for (blob,) in conn.execute(q):
        total += 1
        if blob is None:
            invalid += 1; continue
        b=bytes(blob); geom_bytes += len(b)
        if len(b)<8 or b[0:2]!=b'GP' or b[2]!=0:
            invalid += 1; continue
        flags=b[3]; little=bool(flags & 1); env_type=(flags >> 1) & 0b111; envelope_types[str(env_type)]=envelope_types.get(str(env_type),0)+1
        if flags & 0b10000: empty += 1
        fmt='<i' if little else '>i'
        got_srs=struct.unpack(fmt,b[4:8])[0]
        if got_srs!=srs_id: srs_mismatch+=1
    return {'geometry_headers_checked':total,'invalid_geometry_headers':invalid,'geometry_header_srs_mismatch':srs_mismatch,'empty_geometry_flag_count':empty,'envelope_type_counts':envelope_types,'geometry_blob_bytes_total':geom_bytes,'pass':invalid==0 and srs_mismatch==0}

def projection_bbox_from_request(req):
    bbox=req['norte_selection']['wgs84_bbox']
    minlon,minlat,maxlon,maxlat=map(float,bbox)
    points='\n'.join(f'{x} {y}' for x,y in [(minlon,minlat),(minlon,maxlat),(maxlon,minlat),(maxlon,maxlat)])+'\n'
    p=subprocess.run(['gdaltransform','-s_srs','EPSG:4326','-t_srs','EPSG:3763'],input=points,text=True,capture_output=True)
    if p.returncode!=0: raise Gate(f'GDALTRANSFORM_FAILED:{p.stderr[-800:]}')
    xy=[]
    for line in p.stdout.strip().splitlines():
        parts=line.split()
        if len(parts)<2: continue
        xy.append((float(parts[0]),float(parts[1])))
    if len(xy)!=4: raise Gate(f'GDALTRANSFORM_OUTPUT_INVALID:{p.stdout}')
    return [min(x for x,y in xy),min(y for x,y in xy),max(x for x,y in xy),max(y for x,y in xy)],xy

def ensure_release_and_upload(zip_path,zip_sha,zip_bytes):
    # Reuse an existing deterministic descendant release only if the target asset matches exactly.
    tag_url=f'https://api.github.com/repos/{PRIVATE_REPO}/releases/tags/{DESC_RELEASE_TAG}'
    r=requests.get(tag_url,headers=gh_headers(WRITE_TOKEN),timeout=120)
    if r.status_code==200:
        release=r.json()
    elif r.status_code==404:
        body={'tag_name':DESC_RELEASE_TAG,'target_commitish':PRIVATE_BRANCH,'name':'MN F68 G54 deterministic extraction descendant','body':'Private deterministic descendant of exact preserved F68 bytes; no rights/publication adjudication.','draft':False,'prerelease':True}
        release=api_json('POST',f'https://api.github.com/repos/{PRIVATE_REPO}/releases',WRITE_TOKEN,body)
    else:
        raise Gate(f'PRIVATE_DESC_RELEASE_LOOKUP_{r.status_code}:{r.text[:500]}')
    assets=release.get('assets') or []
    for a in assets:
        if a.get('name')==DESC_ASSET_NAME:
            # GitHub release metadata has size but no digest on older endpoints. Download only if small enough is false; rely on deterministic receipt if pre-existing exact size.
            if int(a.get('size',-1))==zip_bytes:
                return release,a,False
            raise Gate(f'DESC_RELEASE_ASSET_NAME_COLLISION:size={a.get("size")} expected={zip_bytes}')
    upload_url=release['upload_url'].split('{',1)[0]+'?name='+urllib.parse.quote(DESC_ASSET_NAME)
    with open(zip_path,'rb') as fh:
        rr=requests.post(upload_url,headers={**gh_headers(WRITE_TOKEN,'application/vnd.github+json'),'Content-Type':'application/zip','Content-Length':str(zip_bytes)},data=fh,timeout=(30,900))
    if rr.status_code not in (200,201):
        raise Gate(f'DESC_RELEASE_UPLOAD_{rr.status_code}:{rr.text[:500]}')
    asset=rr.json()
    if int(asset.get('size',-1))!=zip_bytes:
        raise Gate(f'DESC_RELEASE_UPLOAD_SIZE_MISMATCH:{asset.get("size")}:{zip_bytes}')
    return release,asset,True

def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def main():
    start=datetime.now(timezone.utc)
    request=json.loads(pathlib.Path(REQUEST_PATH).read_text(encoding='utf-8'))
    if request.get('source_set_id')!=SOURCE_ID or int(request.get('mission_generation',-1))!=MISSION_GENERATION or int(request.get('artifact_id',-1))!=ARTIFACT_ID or request.get('raw_member_sha256')!=RAW_SHA:
        raise Gate('REQUEST_IDENTITY_MISMATCH')
    if not WRITE_TOKEN:
        raise Gate('MN_PRIVATE_SINK_CREDENTIAL_MISSING')
    team=current_team_guard()
    tmp=pathlib.Path(os.environ.get('RUNNER_TEMP','/tmp'))/'f68-g54'
    shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True)
    out_dir=tmp/'out'; out_dir.mkdir()
    outer1=tmp/'artifact-primary.zip'; outer2=tmp/'artifact-alternate.zip'
    wrapper_path,wrapper_route=download_wrapper(outer1,outer2)

    import zipfile
    with zipfile.ZipFile(wrapper_path,'r') as z:
        names=z.namelist()
        exact=[n for n in names if pathlib.PurePosixPath(n).name==RAW_MEMBER]
        if len(exact)!=1: raise Gate(f'RAW_MEMBER_NOT_UNIQUE:{exact[:10]}')
        info=z.getinfo(exact[0])
        raw_path=tmp/RAW_MEMBER
        h=hashlib.sha256(); n=0
        with z.open(info,'r') as src, raw_path.open('wb') as dst:
            while True:
                b=src.read(8*1024*1024)
                if not b: break
                dst.write(b); h.update(b); n+=len(b)
        raw_sha=h.hexdigest()
    if n!=RAW_BYTES or raw_sha!=RAW_SHA:
        raise Gate(f'RAW_MEMBER_IDENTITY_MISMATCH:bytes={n}:sha256={raw_sha}')

    with zipfile.ZipFile(raw_path,'r') as z:
        exact=[n for n in z.namelist() if pathlib.PurePosixPath(n).name==INNER_GPKG]
        if len(exact)!=1: raise Gate(f'INNER_GPKG_NOT_UNIQUE:{exact[:10]}')
        info=z.getinfo(exact[0])
        if info.file_size!=INNER_BYTES: raise Gate(f'INNER_GPKG_EXPECTED_SIZE_MISMATCH:{info.file_size}')
        gpkg=tmp/INNER_GPKG
        with z.open(info,'r') as src, gpkg.open('wb') as dst:
            shutil.copyfileobj(src,dst,length=8*1024*1024)
    gpkg_bytes,gpkg_sha=sha256_file(gpkg)
    if gpkg_bytes!=INNER_BYTES: raise Gate(f'INNER_GPKG_EXTRACTED_SIZE_MISMATCH:{gpkg_bytes}')

    conn=sqlite3.connect(f'file:{gpkg}?mode=ro',uri=True)
    quick=conn.execute('PRAGMA quick_check').fetchone()[0]
    if quick!='ok': raise Gate(f'SQLITE_QUICK_CHECK_FAILED:{quick}')
    layers=[r[0] for r in conn.execute("SELECT table_name FROM gpkg_contents WHERE data_type='features'")]
    if len(layers)!=1: raise Gate(f'EXPECTED_ONE_FEATURE_LAYER:{layers}')
    layer=layers[0]
    gcols=conn.execute('SELECT column_name,geometry_type_name,srs_id,z,m FROM gpkg_geometry_columns WHERE table_name=?',(layer,)).fetchall()
    if len(gcols)!=1: raise Gate(f'EXPECTED_ONE_GEOMETRY_COLUMN:{gcols}')
    geom_col,geom_type,srs_id,zflag,mflag=gcols[0]
    if int(srs_id)!=EXPECTED_EPSG: raise Gate(f'CRS_MISMATCH:{srs_id}')
    cols=conn.execute(f'PRAGMA table_info("{layer.replace(chr(34),chr(34)*2)}")').fetchall()
    col_names=[r[1] for r in cols]
    pk_cols=[r[1] for r in cols if int(r[5])>0]
    if not pk_cols: raise Gate('NO_PRIMARY_KEY_COLUMN')
    pk=pk_cols[0]
    qlayer='"'+layer.replace('"','""')+'"'; qgeom='"'+geom_col.replace('"','""')+'"'; qpk='"'+pk.replace('"','""')+'"'
    feature_count=int(conn.execute(f'SELECT COUNT(*) FROM {qlayer}').fetchone()[0])
    null_geoms=int(conn.execute(f'SELECT COUNT(*) FROM {qlayer} WHERE {qgeom} IS NULL').fetchone()[0])
    if null_geoms!=0: raise Gate(f'NULL_GEOMETRIES_FOUND:{null_geoms}')
    header_qa=gpkg_header_scan(conn,layer,geom_col,int(srs_id))
    if not header_qa['pass'] or header_qa['geometry_headers_checked']!=feature_count:
        raise Gate(f'GEOMETRY_HEADER_QA_FAILED:{header_qa}')
    srs_row=conn.execute('SELECT srs_name,srs_id,organization,organization_coordsys_id,definition,description FROM gpkg_spatial_ref_sys WHERE srs_id=?',(int(srs_id),)).fetchone()
    rtree_name=f'rtree_{layer}_{geom_col}'
    rtree_present=conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(rtree_name,)).fetchone()[0]==1

    projected_bbox,projected_corners=projection_bbox_from_request(request)
    xmin,ymin,xmax,ymax=projected_bbox
    subset=tmp/'F68-COS2023v1-S2-Norte-envelope.gpkg'
    cmd=['ogr2ogr','-f','GPKG',str(subset),str(gpkg),layer,'-spat',str(xmin),str(ymin),str(xmax),str(ymax),'-spat_srs','EPSG:3763','-preserve_fid','-nln',layer,'-lco','SPATIAL_INDEX=YES']
    p=subprocess.run(cmd,text=True,capture_output=True)
    if p.returncode!=0: raise Gate(f'OGR2OGR_NORTE_ENVELOPE_FAILED:{p.stderr[-2000:]}')
    sub=sqlite3.connect(subset)
    sub_quick=sub.execute('PRAGMA quick_check').fetchone()[0]
    if sub_quick!='ok': raise Gate(f'SUBSET_QUICK_CHECK_FAILED:{sub_quick}')
    sub_layers=[r[0] for r in sub.execute("SELECT table_name FROM gpkg_contents WHERE data_type='features'")]
    if sub_layers!=[layer]: raise Gate(f'SUBSET_LAYER_MISMATCH:{sub_layers}:{layer}')
    sub_gcol=sub.execute('SELECT column_name,srs_id FROM gpkg_geometry_columns WHERE table_name=?',(layer,)).fetchone()
    if not sub_gcol or int(sub_gcol[1])!=EXPECTED_EPSG: raise Gate(f'SUBSET_CRS_MISMATCH:{sub_gcol}')
    sub_count=int(sub.execute(f'SELECT COUNT(*) FROM {qlayer}').fetchone()[0])
    sub_null=int(sub.execute(f'SELECT COUNT(*) FROM {qlayer} WHERE {qgeom} IS NULL').fetchone()[0])
    sub_distinct=int(sub.execute(f'SELECT COUNT(DISTINCT {qpk}) FROM {qlayer}').fetchone()[0])
    if sub_null!=0 or sub_distinct!=sub_count: raise Gate(f'SUBSET_KEY_OR_GEOM_QA_FAILED:count={sub_count}:distinct={sub_distinct}:null={sub_null}')
    # Verify all non-geometry attributes and preserved feature ids are exact source values.
    attrs=[c for c in col_names if c!=geom_col]
    proj=','.join('"'+c.replace('"','""')+'"' for c in attrs)
    sub.execute('ATTACH DATABASE ? AS src',(str(gpkg),))
    diff=int(sub.execute(f'SELECT COUNT(*) FROM (SELECT {proj} FROM main.{qlayer} EXCEPT SELECT {proj} FROM src.{qlayer})').fetchone()[0])
    if diff!=0: raise Gate(f'SUBSET_ATTRIBUTE_OR_FID_MISMATCH_ROWS:{diff}')
    sub.close(); conn.close()

    subset_bytes,subset_sha=sha256_file(subset)
    zip_path=tmp/DESC_ASSET_NAME
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        z.write(subset,arcname=subset.name)
    zip_bytes,zip_sha=sha256_file(zip_path)

    layer_inventory={
      'schema_version':'1.0.0','source_set_id':SOURCE_ID,'mission_generation':MISSION_GENERATION,
      'source_identity':{'run_id':RUN_ID,'artifact_id':ARTIFACT_ID,'artifact_name':ARTIFACT_NAME,'wrapper_bytes':WRAPPER_BYTES,'wrapper_sha256':WRAPPER_SHA,'raw_member':RAW_MEMBER,'raw_member_bytes':RAW_BYTES,'raw_member_sha256':RAW_SHA,'inner_gpkg':INNER_GPKG,'inner_gpkg_bytes':INNER_BYTES,'inner_gpkg_sha256':gpkg_sha},
      'layer':{'name':layer,'feature_count':feature_count,'geometry_column':geom_col,'geometry_type_name':geom_type,'srs_id':int(srs_id),'z':zflag,'m':mflag,'primary_key':pk,'columns':col_names,'sqlite_quick_check':quick,'rtree_present':rtree_present,'srs_row':srs_row},
      'geometry_qa':header_qa | {'null_geometries':null_geoms},
      'producer_reacquisition':False,'rights_adjudicated':False
    }
    attribute_rows=[]
    for cid,name,ctype,notnull,dflt,pkflag in cols:
        attribute_rows.append({'ordinal':cid,'name':name,'sqlite_type':ctype,'not_null':bool(notnull),'default':dflt,'primary_key_position':pkflag,'role':'geometry' if name==geom_col else ('feature_id' if name==pk else 'source_attribute')})
    boundary={
      'schema_version':'1.0.0','source_set_id':SOURCE_ID,'mission_generation':MISSION_GENERATION,
      'selection_name':request['norte_selection']['name'],'selection_semantics':request['norte_selection']['semantics'],
      'wgs84_bbox':request['norte_selection']['wgs84_bbox'],'epsg3763_bbox':[xmin,ymin,xmax,ymax],'projected_corner_coordinates':projected_corners,
      'selection_operation':'ogr2ogr -spat feature-intersection selection only; source geometries are not clipped, simplified or transformed; output remains EPSG:3763',
      'administrative_membership_claimed':False,'consumer_join':False,
      'subset':{'feature_count':sub_count,'feature_ids_distinct':sub_distinct,'null_geometries':sub_null,'sqlite_quick_check':sub_quick,'attributes_exact_against_source':diff==0,'gpkg_bytes':subset_bytes,'gpkg_sha256':subset_sha,'zip_bytes':zip_bytes,'zip_sha256':zip_sha}
    }
    write_json(out_dir/'layer-schema-inventory.json',layer_inventory)
    with (out_dir/'attribute-dictionary.csv').open('w',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(attribute_rows[0].keys()),lineterminator='\n'); w.writeheader(); w.writerows(attribute_rows)
    write_json(out_dir/'geometry-qa.json',{'source_set_id':SOURCE_ID,'mission_generation':MISSION_GENERATION,'source_feature_count':feature_count,'source_geometry_qa':header_qa,'source_null_geometries':null_geoms,'subset_feature_count':sub_count,'subset_null_geometries':sub_null,'subset_feature_ids_distinct':sub_distinct,'subset_sqlite_quick_check':sub_quick,'result':'PASS'})
    write_json(out_dir/'norte-envelope-manifest.json',boundary)

    release,asset,uploaded=ensure_release_and_upload(zip_path,zip_sha,zip_bytes)
    asset_locator={'release_tag':DESC_RELEASE_TAG,'release_id':release['id'],'asset_id':asset['id'],'asset_name':asset['name'],'asset_bytes':int(asset['size']),'asset_api_url':asset['url'],'asset_browser_download_url':asset['browser_download_url'],'expected_sha256':zip_sha,'newly_uploaded':uploaded,'private_repository':PRIVATE_REPO}

    # Re-check authoritative generation immediately before private receipt/state writes.
    team2=current_team_guard()
    outputs=[]
    for fn in ['layer-schema-inventory.json','attribute-dictionary.csv','geometry-qa.json','norte-envelope-manifest.json']:
        pth=out_dir/fn; b=pth.read_bytes(); outputs.append({'path':OUT_BASE+'/'+fn,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    handoff={
      'schema_version':'4.9.0','worker':'W2C','mission_generation':MISSION_GENERATION,'package':'F68_EXACT_PRESERVED_ARTIFACT_DETERMINISTIC_EXTRACTION','source_set_id':SOURCE_ID,'status':'PASS_READY_W2B_NORMALIZATION_HANDOFF',
      'collision_scope':'W2C extraction only; W2B semantic normalization and W1C consumer integration remain separate',
      'preserved_source_verification':{'wrapper':wrapper_route,'raw_member':{'name':RAW_MEMBER,'bytes':RAW_BYTES,'sha256':RAW_SHA,'verified':True},'inner_gpkg':{'name':INNER_GPKG,'bytes':gpkg_bytes,'sha256':gpkg_sha,'verified_uncompressed_size':gpkg_bytes==INNER_BYTES}},
      'source_validation':{'sqlite_quick_check':quick,'feature_layer_count':1,'layer':layer,'feature_count':feature_count,'crs':'EPSG:3763','geometry_header_pass':header_qa['pass'],'geometry_headers_checked':header_qa['geometry_headers_checked'],'null_geometries':null_geoms},
      'norte_extraction':{'selection':boundary,'private_descendant_asset':asset_locator},
      'metadata_outputs':outputs,
      'canonical_extraction_receipt_path':CANONICAL_RECEIPT,
      'guards':{'producer_reacquisition':False,'consumer_joins':False,'rights_adjudication':False,'canonical_source_set_writes':False,'catalogue_writes':False,'site_or_drive_work':False,'scheduler_changes':False,'f65_f67_join':False},
      'w2b_handoff':'Consume the exact descendant asset and metadata only for source-native semantic normalization. The conservative extraction envelope is not an administrative/NUTS membership adjudication. Preserve F68 source identity, feature ids, source attributes and EPSG:3763 lineage; do not infer consumer categories here.'
    }
    receipt_path=out_dir/'extraction-receipt.json'; write_json(receipt_path,handoff)
    handoff_bytes=receipt_path.read_bytes(); outputs.append({'path':OUT_BASE+'/extraction-receipt.json','bytes':len(handoff_bytes),'sha256':hashlib.sha256(handoff_bytes).hexdigest()})
    w2b_path=out_dir/'w2b-handoff.json'; write_json(w2b_path,{'schema_version':'1.0.0','source_set_id':SOURCE_ID,'mission_generation':MISSION_GENERATION,'status':'READY_NORMALIZATION_HANDOFF','canonical_extraction_receipt_path':CANONICAL_RECEIPT,'private_descendant_asset':asset_locator,'source_feature_count':feature_count,'selected_feature_count':sub_count,'selection_semantics':boundary['selection_semantics'],'do_not_consumerize':True})
    wb=w2b_path.read_bytes(); outputs.append({'path':OUT_BASE+'/w2b-handoff.json','bytes':len(wb),'sha256':hashlib.sha256(wb).hexdigest()})

    for fn in ['layer-schema-inventory.json','attribute-dictionary.csv','geometry-qa.json','norte-envelope-manifest.json','extraction-receipt.json','w2b-handoff.json']:
        put_private_content(OUT_BASE+'/'+fn,(out_dir/fn).read_bytes(),f'result(mn): W2C G54 F68 {fn}')
    put_private_content(CANONICAL_RECEIPT,handoff_bytes,'receipt(mn): F68 G54 deterministic extraction handoff')

    worker={
      'schema_version':'4.9.0','worker':'W2C','team':'W2','partner':'C','mission_generation':MISSION_GENERATION,'assignment_origin_generation':MISSION_GENERATION,
      'updated_at':datetime.now(timezone.utc).isoformat(),'status':'READY_NORMALIZATION_HANDOFF','current_task':None,'elastic_state':'READY_NORMALIZATION_HANDOFF','last_output':OUT_BASE+'/extraction-receipt.json','blocker':None,
      'window':{'mission':'Generation-54 sole deterministic extraction owner for exact preserved F68 COS2023v1-S2 artifact.','material_packages':1,'source_id':SOURCE_ID,'result':'PASS_F68_EXACT_PRESERVED_EXTRACTION','producer_requests_sent':0,'producer_reacquisitions':0,'wrapper_verified':True,'raw_member_verified':True,'inner_gpkg_bytes':gpkg_bytes,'source_feature_count':feature_count,'source_null_geometries':null_geoms,'geometry_header_pass':header_qa['pass'],'selected_feature_count':sub_count,'selection_semantics':boundary['selection_semantics'],'private_descendant_release':DESC_RELEASE_TAG,'private_descendant_asset_id':asset['id'],'canonical_extraction_receipt':CANONICAL_RECEIPT,'consumer_joins':0,'rights_adjudications':0,'canonical_writes':0,'next_cursor':'W2B may normalize the exact F68 descendant only after orchestrator assignment; W2C must not consumerize.'}
    }
    put_private_content(WORKER_PATH,(json.dumps(worker,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8'),'state(mn): W2C G54 F68 extraction handoff ready')

    public_result={'schema_version':'1.0.0','source_set_id':SOURCE_ID,'mission_generation':MISSION_GENERATION,'status':'PASS','artifact_id':ARTIFACT_ID,'wrapper_sha256':WRAPPER_SHA,'raw_member_sha256':RAW_SHA,'source_feature_count':feature_count,'selected_feature_count':sub_count,'private_descendant_release_tag':DESC_RELEASE_TAG,'private_descendant_asset_id':asset['id'],'canonical_private_receipt':CANONICAL_RECEIPT,'producer_reacquisition':False,'completed_at':datetime.now(timezone.utc).isoformat()}
    put_public_content(PUBLIC_RESULT,(json.dumps(public_result,indent=2,sort_keys=True)+'\n').encode('utf-8'),'receipt(mn): F68 G54 extraction PASS')
    print(json.dumps(public_result,indent=2,sort_keys=True))

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        msg=f'{type(exc).__name__}:{exc}'
        blocker={'schema_version':'1.0.0','source_set_id':SOURCE_ID,'mission_generation':MISSION_GENERATION,'status':'BLOCKED','blocker':msg,'artifact_id':ARTIFACT_ID,'wrapper_sha256':WRAPPER_SHA,'raw_member_sha256':RAW_SHA,'producer_reacquisition':False,'alternate_preserved_attempt_limit_respected':True,'at':datetime.now(timezone.utc).isoformat()}
        try:
            b=(json.dumps(blocker,indent=2,sort_keys=True)+'\n').encode('utf-8')
            put_public_content(PUBLIC_RESULT,b,'receipt(mn): F68 G54 extraction blocker')
            if WRITE_TOKEN:
                put_private_content(OUT_BASE+'/blocker.json',b,'blocker(mn): W2C G54 F68 extraction')
                put_private_content(CANONICAL_RECEIPT,b,'blocker(mn): F68 G54 exact extraction handoff')
                worker={'schema_version':'4.9.0','worker':'W2C','team':'W2','partner':'C','mission_generation':MISSION_GENERATION,'assignment_origin_generation':MISSION_GENERATION,'updated_at':datetime.now(timezone.utc).isoformat(),'status':'EXECUTION_SURFACE_BLOCKED','current_task':None,'elastic_state':'READY_CHANGED_ONLY','last_output':OUT_BASE+'/blocker.json','blocker':{'type':'F68_EXACT_PRESERVED_EXTRACTION_BLOCKER','detail':msg,'artifact_id':ARTIFACT_ID,'expires_at':'2026-10-19T02:32:18Z','producer_reacquisition':False,'resume_trigger':'verified byte-capable preserved-object route with exact wrapper and raw-member identities'}}
                put_private_content(WORKER_PATH,(json.dumps(worker,indent=2,sort_keys=True)+'\n').encode('utf-8'),'state(mn): W2C G54 F68 extraction blocked')
        except Exception as persist_exc:
            print('BLOCKER_PERSIST_FAILURE',repr(persist_exc),file=sys.stderr)
        print(msg,file=sys.stderr)
        sys.exit(2)
