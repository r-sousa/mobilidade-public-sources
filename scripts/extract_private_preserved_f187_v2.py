#!/usr/bin/env python3
import base64,csv,hashlib,json,os,pathlib,re,shutil,subprocess,unicodedata,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timezone
SRC='F187'; FP='43652d12e479f222ab932e5c7104c85cd8ca4b991f9a850d485b9f761d6125bd'; TAG='mn-src-f187-43652d12e479f222ab93'
PR='r-sousa/EU-transp-weekly'; BR='mobilidade-norte-recovery-20260919'; GEN=43; ORIGIN=42
PREC=f'statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F187/{FP}.json'
REQ=pathlib.Path(f'extraction_requests/F187-{FP}.json')
MONTHS={'jan':1,'janeiro':1,'fev':2,'fevereiro':2,'mar':3,'marco':3,'abr':4,'abril':4,'mai':5,'maio':5,'jun':6,'junho':6,'jul':7,'julho':7,'ago':8,'agosto':8,'set':9,'setembro':9,'out':10,'outubro':10,'nov':11,'novembro':11,'dez':12,'dezembro':12}

def n(v):
 s=str(v if v is not None else '').strip(); s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c)).lower(); return re.sub(r'\s+',' ',s)
def sh(b): return hashlib.sha256(b).hexdigest()
def cj(v): return json.dumps(v,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def ghopen(url,tok,accept='application/vnd.github+json',timeout=300):
 h={'Authorization':'Bearer '+tok,'Accept':accept,'User-Agent':'MobilidadeNorte-F187Extractor/2.0','X-GitHub-Api-Version':'2022-11-28'}; return urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=timeout)
def ghjson(url,tok):
 with ghopen(url,tok) as r:return json.loads(r.read())
def ptext(path,tok):
 q=urllib.parse.quote(path,safe='/'); o=ghjson(f'https://api.github.com/repos/{PR}/contents/{q}?ref={BR}',tok); return base64.b64decode(o['content']).decode()
def period(name):
 z=n(name); ym=re.search(r'(20\d{2})',z); y=int(ym.group(1)) if ym else None; qm=re.search(r'([1-4])(?:o|º)?[-_\s]*trimestre',z); q=int(qm.group(1)) if qm else None
 return {'reference_year':y,'reference_quarter':q,'edition_scope':('ANNUAL' if y and q is None and 'trimestre' not in z else (f'Q{q}' if q else 'UNRESOLVED'))}
def month(label):
 z=n(label)
 for k,v in MONTHS.items():
  if re.search(rf'(^|[^a-z]){re.escape(k)}([^a-z]|$)',z): return v
 return None
def role(label):
 z=n(label)
 if 'estrada' in z or 'autoestrad' in z or re.fullmatch(r'ae',z):return 'motorway'
 if 'concess' in z and len(z)<80:return 'concession'
 if 'sublanc' in z or 'sublan' in z:return 'sublanco'
 if re.search(r'(^|\W)tmdm(\W|$)',z):return 'tmdm'
 if re.search(r'(^|\W)tmda(\W|$)',z):return 'tmda'
 return None
def tcell(book,c):
 import xlrd
 if c.ctype==xlrd.XL_CELL_EMPTY:return {'type':'blank','value':''}
 if c.ctype==xlrd.XL_CELL_TEXT:return {'type':'text','value':str(c.value)}
 if c.ctype==xlrd.XL_CELL_NUMBER:return {'type':'number','value':c.value}
 if c.ctype==xlrd.XL_CELL_DATE:
  try:return {'type':'date','value':xlrd.xldate.xldate_as_datetime(c.value,book.datemode).isoformat(),'excel_serial':c.value}
  except Exception:return {'type':'date','value':c.value,'decode_error':True}
 if c.ctype==xlrd.XL_CELL_BOOLEAN:return {'type':'boolean','value':bool(c.value)}
 if c.ctype==xlrd.XL_CELL_ERROR:return {'type':'error','value':int(c.value)}
 return {'type':f'xlrd_{c.ctype}','value':c.value}
def writecsv(p,fields,rows):
 with p.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n',extrasaction='ignore');w.writeheader();w.writerows(rows)
def stem(name):return re.sub(r'[^A-Za-z0-9._-]+','_',pathlib.Path(name).stem)[:180]
def roadlike(v):
 z=n(v).replace(' ',''); return bool(re.match(r'^(a\d+[a-z]?|ip\d+|ic\d+|en\d+|er\d+)$',z))
def label_rows(prows,data_start):
 cand=[]
 for r in range(max(0,data_start-5),data_start):
  if any(str(x).strip() for x in prows[r]): cand.append(r)
 return cand[-3:]
def main():
 rq=json.loads(REQ.read_text());
 if rq.get('source_set_id')!=SRC or rq.get('native_asset_fingerprint')!=FP or rq.get('release_tag')!=TAG or int(rq.get('wake_mission_generation',-1))!=GEN:raise SystemExit('REQUEST_IDENTITY_MISMATCH')
 rt=(os.getenv('MN_PRIVATE_SINK_TOKEN') or os.getenv('MN_PRIVATE_READ_TOKEN') or '').strip(); wt=(os.getenv('MN_PRIVATE_SINK_TOKEN') or '').strip()
 if not rt:raise SystemExit('MN_PRIVATE_READ_CREDENTIAL_MISSING')
 if not wt:raise SystemExit('MN_PRIVATE_WRITE_CREDENTIAL_MISSING')
 rec=json.loads(ptext(PREC,rt)); assets=rec.get('assets') or []; by={a['name']:a for a in assets}; xls=[a for a in assets if a['name'].lower().endswith('.xls')]
 if rec.get('native_asset_fingerprint')!=FP or len(xls)!=51 or not {'landing.html','series-manifest.json'}.issubset(by):raise SystemExit('PRIVATE_RECEIPT_CONTRACT_MISMATCH')
 rel=ghjson(f'https://api.github.com/repos/{PR}/releases/tags/{TAG}',rt); ra={a['name']:a for a in rel.get('assets',[])}
 if set(by)-set(ra):raise SystemExit('PRIVATE_RELEASE_ASSETS_MISSING')
 verified={}
 for name,a in by.items():
  m=ra[name]
  if int(m.get('size',-1))!=int(a['bytes']):raise SystemExit('RELEASE_SIZE_MISMATCH:'+name)
  try:
   with ghopen(f'https://api.github.com/repos/{PR}/releases/assets/{int(m["id"])}',rt,'application/octet-stream') as r:b=r.read()
  except urllib.error.HTTPError as e:raise SystemExit(f'PRIVATE_ASSET_READ_FAILED:{name}:HTTP_{e.code}')
  if len(b)!=int(a['bytes']) or sh(b)!=a['sha256']:raise SystemExit('ASSET_VERIFICATION_FAILED:'+name)
  verified[name]={'data':b,'asset_id':int(m['id']),'bytes':len(b),'sha256':sh(b),'role':a.get('role'),'format':a.get('format'),'source_url':a.get('source_url')}
 print(cj({'gate':'ALL_53_ASSETS_VERIFIED_BEFORE_PARSE','xls':len(xls)}),flush=True)
 import xlrd
 manifest=json.loads(verified['series-manifest.json']['data'].decode()); now=datetime.now(timezone.utc); stamp=now.strftime('%Y%m%dT%H%M%SZ'); tmp=pathlib.Path(os.getenv('RUNNER_TEMP','/tmp'))/('f187v2-'+stamp); out=tmp/'out'; rowsdir=out/'row_shards'; metadir=out/'per_file_metadata'; rowsdir.mkdir(parents=True);metadir.mkdir()
 wbinv=[]; shinv=[]; shardinv=[]; schemas={}; totalrows=0; totalvals=0; omitted_before=0; data_sheets=0; metadata_sheets=0
 rowfields=['source_file','source_file_sha256','source_file_bytes','reference_year','reference_quarter','edition_scope','sheet_index_1based','sheet_name','source_row_1based','schema_signature_sha256','motorway','concession','sublanco','tmdm','tmda','measure_tokens_json','source_month_fields_json','blank_source_columns_1based_json','source_fields_json']
 for a in sorted(xls,key=lambda z:z['name']):
  name=a['name']; b=verified[name]['data']; pe=period(name); book=xlrd.open_workbook(file_contents=b,on_demand=True); filerows=[]; fm={'source_file':name,'bytes':len(b),'sha256':sh(b),**pe,'sheet_count':book.nsheets,'sheets':[]}; workbook_tokens=set()
  for si in range(book.nsheets):
   ws=book.sheet_by_index(si); typed=[]; plain=[]
   for r in range(ws.nrows):
    tr=[tcell(book,ws.cell(r,c)) for c in range(ws.ncols)]; typed.append(tr);plain.append([x['value'] for x in tr])
   ds=None
   for r in range(min(ws.nrows,40)):
    c0=plain[r][0] if ws.ncols>0 else ''; c1=plain[r][1] if ws.ncols>1 else ''
    if roadlike(c0) and str(c1).strip() and 'sublan' not in n(c1):ds=r;break
   alltext=' | '.join(str(v) for rr in plain for v in rr if isinstance(v,str) and v.strip())
   tokens=[]
   if re.search(r'(^|\W)tmdm(\W|$)',n(alltext)):tokens.append('TMDM')
   if re.search(r'(^|\W)tmda(\W|$)',n(alltext)):tokens.append('TMDA')
   workbook_tokens.update(tokens)
   rev=[];units=[];notes=[]
   for r in range(ws.nrows):
    for c in range(ws.ncols):
     v=plain[r][c]
     if not isinstance(v,str) or not v.strip():continue
     z=n(v)
     if any(k in z for k in ['provisor','provis','revisto','revis','definitiv']):rev.append({'row':r+1,'col':c+1,'text':v})
     if any(k in z for k in ['veiculo','veiculos','veic/dia','veiculos/dia','quilomet',' km','%']):units.append({'row':r+1,'col':c+1,'text':v})
     if any(k in z for k in ['nota','fonte','observ']):notes.append({'row':r+1,'col':c+1,'text':v})
   if ds is None:
    metadata_sheets+=1; labels=[]; cmap={}; mmap={}; sig=sh(cj({'sheet_name':ws.name,'metadata_only':True,'nrows':ws.nrows,'ncols':ws.ncols}).encode());schemas[sig]=schemas.get(sig,0)+1; extracted=0; nonblank=0; hr=[]
   else:
    data_sheets+=1; hr=label_rows(plain,ds);labels=[];cmap={};mmap={};cy=None
    for c in range(ws.ncols):
     parts=[]
     for rr in hr:
      v=plain[rr][c]
      if str(v).strip():parts.append(str(v).strip())
     label=' | '.join(dict.fromkeys(parts)) if parts else f'col_{c+1:03d}';labels.append(label);rr=role(label)
     if rr and rr not in cmap:cmap[rr]=c
     ym=re.search(r'(20\d{2})',label)
     if ym:cy=int(ym.group(1))
     mo=month(label)
     if mo:mmap[c]={'month':mo,'year':cy}
    sigobj={'sheet_name':ws.name,'data_start_row_1based':ds+1,'header_rows_1based':[r+1 for r in hr],'column_labels':labels,'core_column_map_1based':{k:v+1 for k,v in cmap.items()},'month_column_map_1based':{str(k+1):v for k,v in mmap.items()}};sig=sh(cj(sigobj).encode());schemas[sig]=schemas.get(sig,0)+1;extracted=0;nonblank=0
    for r in range(ds,ws.nrows):
     tr=typed[r]
     if not any(x['type']!='blank' for x in tr):continue
     vals=[x['value'] for x in tr];fields=[];blanks=[];months={}
     for c,tc in enumerate(tr):
      fields.append({'source_column_1based':c+1,'source_label':labels[c],'cell':tc})
      if tc['type']=='blank':blanks.append(c+1)
      else:
       nonblank+=1
       if c in mmap:months[str(c+1)]={'reference_year':mmap[c]['year'],'reference_month':mmap[c]['month'],'source_label':labels[c],'cell':tc}
     core={k:vals[c] for k,c in cmap.items()}
     filerows.append({'source_file':name,'source_file_sha256':sh(b),'source_file_bytes':len(b),**pe,'sheet_index_1based':si+1,'sheet_name':ws.name,'source_row_1based':r+1,'schema_signature_sha256':sig,'motorway':core.get('motorway'),'concession':core.get('concession'),'sublanco':core.get('sublanco'),'tmdm':core.get('tmdm'),'tmda':core.get('tmda'),'measure_tokens_json':cj(tokens),'source_month_fields_json':cj(months),'blank_source_columns_1based_json':cj(blanks),'source_fields_json':cj(fields)});extracted+=1
    totalrows+=extracted;totalvals+=nonblank
   nonempty=sum(1 for rr in typed for x in rr if x['type']!='blank')
   sm={'source_file':name,'sheet_index_1based':si+1,'sheet_name':ws.name,'nrows':ws.nrows,'ncols':ws.ncols,'data_sheet':ds is not None,'data_start_row_1based':None if ds is None else ds+1,'header_rows_1based':[] if ds is None else [r+1 for r in hr],'column_labels':labels,'core_column_map_1based':{k:v+1 for k,v in cmap.items()},'month_column_map_1based':{str(k+1):v for k,v in mmap.items()},'schema_signature_sha256':sig,'measure_tokens':tokens,'revision_markers':rev[:100],'unit_hints':units[:100],'notes':notes[:100],'extracted_nonempty_rows':extracted,'published_nonblank_values':nonblank,'nonempty_cells':nonempty};fm['sheets'].append(sm);shinv.append({'source_file':name,'reference_year':pe['reference_year'],'reference_quarter':pe['reference_quarter'],'edition_scope':pe['edition_scope'],'sheet_index_1based':si+1,'sheet_name':ws.name,'data_sheet':ds is not None,'data_start_row_1based':'' if ds is None else ds+1,'header_rows_1based_json':cj(sm['header_rows_1based']),'column_labels_json':cj(labels),'core_column_map_1based_json':cj(sm['core_column_map_1based']),'month_column_map_1based_json':cj(sm['month_column_map_1based']),'schema_signature_sha256':sig,'measure_tokens_json':cj(tokens),'revision_markers_json':cj(sm['revision_markers']),'unit_hints_json':cj(sm['unit_hints']),'notes_json':cj(sm['notes']),'extracted_nonempty_rows':extracted,'published_nonblank_values':nonblank,'nonempty_cells':nonempty})
  book.release_resources();sp=stem(name);rp=rowsdir/(sp+'-rows.csv');writecsv(rp,rowfields,filerows);rb=rp.read_bytes();mp=metadir/(sp+'-metadata.json');fm['measure_tokens']=sorted(workbook_tokens);mp.write_text(json.dumps(fm,ensure_ascii=False,indent=2,sort_keys=True)+'\n');mb=mp.read_bytes();shardinv.append({'source_file':name,'row_shard':str(rp.relative_to(out)),'row_count':len(filerows),'row_shard_bytes':len(rb),'row_shard_sha256':sh(rb),'metadata_file':str(mp.relative_to(out)),'metadata_bytes':len(mb),'metadata_sha256':sh(mb)});wbinv.append({'source_file':name,'bytes':len(b),'sha256':sh(b),**pe,'sheet_count':fm['sheet_count'],'source_url':a.get('source_url'),'measure_tokens_json':cj(sorted(workbook_tokens)),'extracted_rows':len(filerows),'row_shard':str(rp.relative_to(out))})
 wb=out/'f187_workbook_inventory_corrected.csv';writecsv(wb,['source_file','bytes','sha256','reference_year','reference_quarter','edition_scope','sheet_count','source_url','measure_tokens_json','extracted_rows','row_shard'],wbinv)
 si=out/'f187_sheet_inventory_corrected.csv';writecsv(si,['source_file','reference_year','reference_quarter','edition_scope','sheet_index_1based','sheet_name','data_sheet','data_start_row_1based','header_rows_1based_json','column_labels_json','core_column_map_1based_json','month_column_map_1based_json','schema_signature_sha256','measure_tokens_json','revision_markers_json','unit_hints_json','notes_json','extracted_nonempty_rows','published_nonblank_values','nonempty_cells'],shinv)
 sm=out/'f187_row_shards_manifest_corrected.json';sm.write_text(json.dumps(shardinv,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
 vmeta=[{'name':name,**{k:v for k,v in x.items() if k!='data'}} for name,x in verified.items()]
 ingress={'schema_version':'4.0.7','worker':'W2C','mission_generation':GEN,'assignment_origin_generation':ORIGIN,'package':'F187_IMT_XLS_EXTRACTION_METADATA_CORRECTION_V2','source_set_id':SRC,'native_asset_fingerprint':FP,'private_release_tag':TAG,'all_assets_verified_before_parse':True,'verified_asset_count':len(vmeta),'verified_assets':vmeta,'series_manifest':manifest,'workbook_count':len(wbinv),'sheet_count':len(shinv),'data_sheet_count':data_sheets,'metadata_sheet_count':metadata_sheets,'source_native_nonempty_rows':totalrows,'published_nonblank_values':totalvals,'schema_signature_count':len(schemas),'corrections':['Quarter parser now recognizes filename forms such as 1o-Trimestre and 1o-Trimestre with hyphen separators.','Data-sheet boundary is detected from first source road/subsection row; header labels use only preceding header rows, never first data values.','Estrada is retained as source-native motorway/road identity; Notes sheets are metadata-only and cannot create false concession mappings.','Month fields carry explicit source header year/month when available; edition harmonization remains forbidden.'],'source_rows_or_values_modified_by_correction':False,'source_asset_identity_changed':False,'producer_reacquisition':False,'editions_harmonized':False,'annual_quarterly_reconciled':False,'f05_joined':False,'rights_adjudication':False,'consumer_joins':False}
 ip=out/'f187_source_native_ingress_corrected.json';ip.write_text(json.dumps(ingress,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
 outs=[wb,si,sm,ip]+sorted(rowsdir.glob('*.csv'))+sorted(metadir.glob('*.json'));om=[]
 for p in outs:b=p.read_bytes();om.append({'relative_path':str(p.relative_to(out)),'bytes':len(b),'sha256':sh(b)})
 largest=max(om,key=lambda z:z['bytes']);print(cj({'gate':'CORRECTED_EXTRACTION_BUILT','rows':totalrows,'sheets':len(shinv),'largest_output':largest,'schemas':len(schemas)}),flush=True)
 if largest['bytes']>50_000_000:raise SystemExit('OUTPUT_SHARD_TOO_LARGE')
 outbase=f'statistics/recovery-20260920/simple-runtime/outputs/W2C/{stamp}-G43-F187-extraction-correction';handoff=f'statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F187/{FP}-extraction-correction.json'
 cr={'schema_version':'4.0.7','worker':'W2C','mission_generation':GEN,'assignment_origin_generation':ORIGIN,'package':'F187_IMT_XLS_EXTRACTION_METADATA_CORRECTION_V2','source_set_id':SRC,'native_asset_fingerprint':FP,'private_release_tag':TAG,'status':'PASS_APPEND_ONLY_EXTRACTION_CORRECTION_READY_NORMALIZATION_HANDOFF','supersedes_for_normalization':'statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/F187/'+FP+'-extraction.json','historical_extraction_mutated':False,'all_53_assets_reverified_before_parse':True,'verified_xls_workbooks':51,'source_native_rows':totalrows,'published_nonblank_values':totalvals,'sheet_count':len(shinv),'data_sheet_count':data_sheets,'schema_signature_count':len(schemas),'source_asset_identity_changed':False,'source_values_changed':False,'producer_reacquisition':False,'editions_harmonized':False,'annual_quarterly_reconciled':False,'f05_joined':False,'consumer_joins':False,'rights_adjudication':False,'outputs':[{'path':outbase+'/'+x['relative_path'],'bytes':x['bytes'],'sha256':x['sha256']} for x in om],'next_owner':'W2B','next_state':'READY_NORMALIZATION_HANDOFF','canonical_correction_receipt_path':handoff}
 ep=out/'extraction-correction-receipt.json';ep.write_text(json.dumps(cr,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
 team=json.loads(ptext('statistics/recovery-20260920/simple-runtime/team-missions.json',rt));wc=(((team.get('teams') or {}).get('W2') or {}).get('C') or {});bind=cj(wc)
 if SRC not in bind or FP not in bind:raise SystemExit('CURRENT_W2C_ASSIGNMENT_CHANGED')
 clone=tmp/'private';env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0';url=f'https://x-access-token:{wt}@github.com/{PR}.git';subprocess.run(['git','clone','--depth','1','--branch',BR,url,str(clone)],check=True,env=env,stdout=subprocess.DEVNULL)
 dst=clone/outbase;dst.mkdir(parents=True,exist_ok=True)
 for p in outs+[ep]:q=dst/p.relative_to(out);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
 hp=clone/handoff;hp.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ep,hp)
 wp=clone/'statistics/recovery-20260920/simple-runtime/worker-W2C.json';worker={'schema_version':'4.0.7','worker':'W2C','team':'W2','partner':'C','mission_generation':GEN,'assignment_origin_generation':ORIGIN,'updated_at':now.isoformat().replace('+00:00','Z'),'status':'READY_NORMALIZATION_HANDOFF','elastic_state':'STANDBY_EXTRACTION_INGRESS','current_task':None,'last_output':outbase+'/extraction-correction-receipt.json','window':{'mission':'F187 exact-fingerprint deterministic extraction plus append-only metadata correction; no producer reacquisition.','material_packages':2,'source_id':SRC,'native_asset_fingerprint':FP,'result':'PASS_F187_CORRECTED_SOURCE_NATIVE_XLS_EXTRACTION_INGRESS','all_assets_reverified_before_parse':True,'xls_workbook_count':51,'sheet_count':len(shinv),'source_native_nonempty_rows':totalrows,'published_nonblank_values':totalvals,'schema_signature_count':len(schemas),'producer_requests_sent':0,'producer_reacquisitions':0,'consumer_joins':0,'rights_adjudications':0,'f05_joined':False,'editions_harmonized':False,'authoritative_normalization_handoff':handoff,'historical_extraction_receipt_preserved':True,'next_cursor':['W2B must use the extraction-correction receipt as authoritative normalization ingress.','Preserve edition/file, sheet/table, period, road/subsection identity, source labels/unit hints/revision markers and missingness; reconcile annual/quarterly explicitly.','Do not join F05 inside W2B normalization.']},'blocker':None};wp.write_text(json.dumps(worker,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
 subprocess.run(['git','-C',str(clone),'config','user.name','mobilidade-public-sources[bot]'],check=True);subprocess.run(['git','-C',str(clone),'config','user.email','actions@users.noreply.github.com'],check=True);subprocess.run(['git','-C',str(clone),'add','--',outbase,handoff,'statistics/recovery-20260920/simple-runtime/worker-W2C.json'],check=True);subprocess.run(['git','-C',str(clone),'commit','-m','result(mn): correct W2C F187 extraction metadata'],check=True,stdout=subprocess.DEVNULL)
 for i in range(4):
  p=subprocess.run(['git','-C',str(clone),'push','origin',BR],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  if p.returncode==0:break
  subprocess.run(['git','-C',str(clone),'pull','--rebase','origin',BR],check=True,env=env,stdout=subprocess.DEVNULL)
 else:raise SystemExit('PRIVATE_CORRECTION_PUSH_FAILED')
 print(cj({'status':'PASS_CORRECTED','handoff':handoff,'rows':totalrows,'sheets':len(shinv),'data_sheets':data_sheets,'schemas':len(schemas)}),flush=True)
if __name__=='__main__':main()
