"""Execute the 25 September source disposition. No acquisition; private outputs only."""
from __future__ import annotations
import base64, copy, csv, datetime as dt, hashlib, io, json, os, tempfile, zipfile
from pathlib import Path
from urllib.parse import quote
import requests
from mn_public_acquisition.sinks import create_release, upload_or_verify

REPO = 'r-sousa/EU-transp-weekly'
BRANCH = 'mobilidade-norte-recovery-20260919'
ROOT = 'statistics/recovery-20260920/simple-runtime/'
AUTH = ROOT + 'decisions/20260925-user-source-disposition.json'
AUTH_REF = '8432432f63b648feb52e665ec39aecf18cdb0456'
QA = ROOT + 'outputs/W1B/G63R/G63R-QA-LEAD/20260924T2250PT-v3/01-f195-qa.json'
OUT = ROOT + 'outputs/ORCHESTRATOR/G63-FINAL-DISPOSITION-20260925/'
CONTROL = ROOT + 'orchestrator-status.json'
RUN = os.environ.get('GITHUB_RUN_ID', 'unknown')
EXECUTION = 'G63-FINAL-DISPOSITION-' + RUN
TOKEN = os.environ['MN_PRIVATE_SINK_TOKEN']
S = requests.Session()
S.headers.update({'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'MobilidadeNorte-ApprovedDisposition/1.0'})
API = 'https://api.github.com/repos/' + REPO

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def enc(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def blob_sha(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def api(method, suffix, **kwargs):
    r = S.request(method, API + suffix, timeout=120, **kwargs)
    if not r.ok:
        raise RuntimeError('GITHUB_' + method + '_HTTP_' + str(r.status_code))
    return r.json()

def head():
    return api('GET', '/git/ref/heads/' + quote(BRANCH, safe=''))['object']['sha']

def read(path, ref):
    o = api('GET', '/contents/' + quote(path, safe='/'), params={'ref': ref})
    if o.get('encoding') == 'base64' and o.get('content'):
        raw = base64.b64decode(o['content'])
    else:
        b = api('GET', '/git/blobs/' + o['sha'])
        raw = base64.b64decode(b['content'])
    if blob_sha(raw) != o['sha']:
        raise RuntimeError('READBACK_HASH_MISMATCH')
    return raw, o['sha']

def obj(path, ref):
    return json.loads(read(path, ref)[0])

def commit(changes, preconditions, message):
    # Only rebase over unrelated file additions; never overwrite a changed input.
    for _ in range(4):
        h = head()
        for p, expected in preconditions.items():
            if read(p, h)[1] != expected:
                raise RuntimeError('CONCURRENT_CANONICAL_CHANGE')
        tree = api('GET', '/git/commits/' + h)['tree']['sha']
        entries = [{'path': p, 'mode': '100644', 'type': 'blob', 'content': b.decode('utf-8')} for p, b in changes.items()]
        t = api('POST', '/git/trees', json={'base_tree': tree, 'tree': entries})['sha']
        c = api('POST', '/git/commits', json={'message': message, 'tree': t, 'parents': [h]})['sha']
        r = S.patch(API + '/git/refs/heads/' + quote(BRANCH, safe=''), json={'sha': c, 'force': False}, timeout=120)
        if r.ok:
            for p, b in changes.items():
                if read(p, c)[0] != b:
                    raise RuntimeError('COMMIT_READBACK_MISMATCH')
            return c
        if r.status_code not in (409, 422):
            raise RuntimeError('REF_UPDATE_HTTP_' + str(r.status_code))
    raise RuntimeError('CONCURRENT_BRANCH_BUSY')

def add_unique(items, value):
    if value not in items:
        items.append(value)

def run():
    auth = obj(AUTH, AUTH_REF)
    assert auth['source_decisions']['F195']['numeric_target'] == 87
    assert auth['execution']['plane'] == os.environ['GITHUB_REPOSITORY']
    assert auth['publication'] == 'NO_PUBLICATION_AUTHORISED_BY_THIS_OBJECT'
    start = head()
    ctrl_raw, ctrl_sha = read(CONTROL, start)
    ctrl = json.loads(ctrl_raw)
    assert ctrl['mission_generation'] == 63
    if ctrl.get('current_task'):
        raise RuntimeError('CANONICAL_WRITER_ALREADY_CLAIMED')
    fpath = 'statistics/source-sets/F195/manifest.json'
    f = obj(fpath, start)
    if f['runtime_overlay']['accepted_state']['accepted_statistical_record_count'] == 87:
        print('ALREADY_APPLIED_F195_87_NO_REPLAY')
        return
    assert f['runtime_overlay']['accepted_state']['accepted_statistical_record_count'] == 42
    # Claim the sole canonical writer before building the transaction.
    ctrl['current_task'] = {'task_id': 'G63-FINAL-SOURCE-DISPOSITION', 'execution_id': EXECUTION, 'owner': 'ORCHESTRATOR', 'started_at': now(), 'lease_expires_at': (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=45)).isoformat(), 'children': [{'repository': os.environ['GITHUB_REPOSITORY'], 'run_id': int(RUN)}]}
    claim = commit({CONTROL: enc(ctrl)}, {CONTROL: ctrl_sha}, 'Claim approved G63 final source disposition')
    owned = True
    try:
        snap = head()
        paths = [fpath, 'statistics/source-sets/index.json', 'statistics/catalogue-current.json', 'statistics/public-export/catalogue-metadata-current.json', ROOT + 'completeness-matrix.json', CONTROL]
        paths += ['statistics/source-sets/' + sid + '/manifest.json' for sid in ('F197','F198','F97','F100')]
        loaded = {p: read(p, snap) for p in paths}
        docs = {p: json.loads(v[0]) for p,v in loaded.items()}
        pre = {p: v[1] for p,v in loaded.items()}
        assert docs[CONTROL]['current_task']['execution_id'] == EXECUTION
        qa_raw, qa_sha = read(QA, snap)
        assert qa_sha == '20b49da17346d9a923d7c348fa904039fca5a602'
        qa = json.loads(qa_raw)
        assert qa['approved_delta']['statistical_observations'] == 45
        table_raw, table_sha = read(qa['evidence']['normalized_data'], snap)
        assert table_sha == 'f54eb99b0407733ca5ee3f15d92f401db8e126a5'
        source_raw, source_sha = read(qa['evidence']['source_utf8'], snap)
        rows = list(csv.DictReader(io.StringIO(table_raw.decode('utf-8'))))
        assert len(rows) == 48 and len({r['observation_key'] for r in rows}) == 48
        numeric = [r for r in rows if r['value_percent'] != '']
        markers = [r for r in rows if r['value_percent'] == '']
        assert len(numeric) == 45 and len(markers) == 3
        assert {r['observation_key'] for r in numeric} == set(qa['approved_numeric_keys'])
        assert {r['observation_key'] for r in markers} == {r['observation_key'] for r in qa['excluded_from_numeric_admission']}
        source_lines = source_raw.decode('utf-8-sig').splitlines()
        for r in rows:
            tokens = next(csv.reader([source_lines[int(r['source_line'])-1]], delimiter=';'))
            assert tokens[int(r['source_column_1based'])-1].strip() == r['raw_value']
            assert r['source_set_id'] == 'F195' and r['indicator'] == '0014450' and r['reference_year'] == '2024' and r['geography_code'] == 'PT'
            if r['value_percent']:
                assert float(r['value_percent']) == float(r['raw_value'].replace(',', '.'))
            else:
                assert r['raw_value'] == 'x x'
        f = docs[fpath]
        prior = copy.deepcopy(f['runtime_overlay']['accepted_state'])
        base_raw, base_sha = read(prior['data_package']['path'], snap)
        assert base_sha == prior['data_package']['blob'] and digest(base_raw) == prior['data_package']['sha256']
        old = [json.loads(line) for line in base_raw.splitlines() if line.strip()]
        assert len(old) == 42 and all(r['indicator_code'] != '0014450' for r in old)
        appended = []
        for r in numeric:
            appended.append({'schema_version':'1.0.0','source_set_id':'F195','product_key': f['identity']['product_key'], 'observation_key':r['observation_key'],'indicator_code':'0014450','reference_period':'2024','period_selector':'S7A2024','periodicity':'Sexenal','unit':'Percentagem (%)','power10':0,'decimal_precision':1,'geography_code':'PT','geography_label':'Portugal','geography_native_level':'COUNTRY','native_norte':False,'dimensions':{'sex':{'code':r['sex_code'],'label':r['sex_label']},'age':{'code':r['age_code'],'label':r['age_label']},'transport_use_frequency':{'code':r['frequency_code']}},'value':float(r['value_percent']),'value_raw':r['raw_value'],'source_missingness':'PRESENT_NUMERIC_VALUE','raw_source_observation':r,'source_csv_path':qa['evidence']['source_utf8'],'source_csv_sha256':digest(source_raw),'independent_qa':QA})
        combined = base_raw.rstrip(b'\n') + b'\n' + b''.join((json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode() for r in appended)
        assert len(combined.splitlines()) == 87
        data_path = 'statistics/source-sets/F195/data/public-current-87.jsonl'
        marker_path = 'statistics/source-sets/F195/data/0014450-2024-source-markers.json'
        receipt_path = OUT + 'transaction.json'
        current_state = 'COMPLETE_REGISTERED_PUBLIC_SCOPE_87_NUMERIC_3_SOURCE_MARKERS_CONTROLLED_SEPARATE'
        accepted = f['runtime_overlay']['accepted_state']
        accepted.update({'state':current_state,'accepted_statistical_record_count':87,'country_rows':60,'canonical_statistical_observation_delta':87,'public_scope_complete':True,'family_complete':False,'nonnumeric_source_marker_count':3,'data_package':{'path':data_path,'blob':blob_sha(combined),'sha256':digest(combined)},'previous_accepted_package':prior['data_package'],'incremental_admission_receipt':receipt_path})
        accepted['member_breakdown']['0014450/2024'] = 45
        f['source']['confirmed_period'] = 'Registered public members: 2024 and 2025. Indicator 0014450 is native 2024; controlled 2025 extension remains separate.'
        f['source']['acquisition_scope'] = 'Five registered public members preserved and normalized: 87 accepted numerical observations; 3 native nonnumerical markers retained separately. No controlled microdata.'
        f['preservation'].update({'audit_date':'2026-09-25','audit_status':current_state,'evidence_note':'Existing 42 plus independently approved 45 ingested exactly once. Earlier 12 are a subset of the 45. Original failed requests remain historical provenance.','next_action':'No repeated acquisition or unchanged normalization for the completed registered public scope.'})
        f['runtime_overlay']['semantics'] = f['source']['acquisition_scope'] + ' Native Norte rows remain 3; no national-to-Norte allocation.'
        dispatch = f['runtime_overlay'].get('g63_acquisition_dispatch',{})
        dispatch.update({'state':current_state,'members_acquired':5,'members_normalized':5,'blocked_member':None,'reopening_condition':'Only new separately authorised scope or verified source revision.'})
        f['runtime_overlay']['g63_acquisition_dispatch'] = dispatch
        f['runtime_overlay']['paths'].extend([QA, receipt_path])
        f['acquisition_packaging']['observation_admission'] = '87_NUMERICAL_OBSERVATIONS_ACCEPTED_FOR_REGISTERED_PUBLIC_SCOPE'
        # A reproducible private Release is preserved before canonical acceptance.
        with tempfile.TemporaryDirectory() as td:
            zp = Path(td)/'F195-public-87.zip'
            payloads = {'normalized-observations.jsonl':combined,'source-0014450-2024.csv':source_raw,'source-markers.json':enc(markers),'independent-qa.json':qa_raw,'accepted-42-original.jsonl':base_raw}
            with zipfile.ZipFile(zp,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for name, raw in sorted(payloads.items()):
                    info=zipfile.ZipInfo(name,date_time=(2026,9,25,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
            zh=digest(zp.read_bytes()); tag='mn-normalized-f195-87-'+zh[:16]
            rel=create_release(REPO,tag,TOKEN,target=snap,name='F195 — accepted registered public scope — 87 numerical observations',body='Private normalized package: existing 42 plus independently approved 45. Three nonnumerical source markers remain excluded. No public redistribution is authorised.')
            asset=upload_or_verify(REPO,rel,zp,zp.name,TOKEN,zh,zp.stat().st_size)
            private_release={'tag':tag,'url':rel['html_url'],'asset_id':asset['id'],'sha256':zh,'bytes':zp.stat().st_size,'readback':'PASS_SIZE_SHA256'}
        for field,value in [('release_tags',tag),('release_urls',rel['html_url']),('release_assets',asset['name'])]:
            add_unique(f['preservation'].setdefault(field,[]),value)
        freeze_sids=('F197','F198','F97','F100')
        for sid in freeze_sids:
            d=docs['statistics/source-sets/'+sid+'/manifest.json']
            d['current_user_disposition']={'decision_id':auth['decision_id'],'decision_path':AUTH,'state':'FROZEN_CURRENT_ACHIEVEMENTS','effective_at':now(),'further_acquisition':False,'further_scope_expansion':False,'numeric_admissions':'Existing independent approvals only; unapproved and disputed cells retain their current labels.','duplicate_work':False,'reopen_requires':'New explicit user instruction or critical integrity finding; no automatic further extraction.'}
            d.setdefault('runtime_overlay',{})['work_disposition']='FROZEN_BY_USER_20260925'
            d.setdefault('preservation',{})['next_action']='Retain current achievements and limits; no further acquisition or extraction for G63.'
        # The three live internal projections must agree before addition.
        ix=docs['statistics/source-sets/index.json']; cat=docs['statistics/catalogue-current.json']; mat=docs[ROOT+'completeness-matrix.json']
        assert ix['canonical_counts']['normalized_statistical_observations']==10825
        assert cat['canonical_counts']['normalized_statistical_observations']==10825
        assert mat['counting']['canonical_normalized_statistical_observations']==10825
        for d,key in [(ix,'g63_incremental_admission_breakdown'),(cat,'g63_breakdown')]:
            counts=d['canonical_counts'];assert counts[key]['F195']==42
            counts['normalized_statistical_observations']=10870
            counts['g63_incremental_admission_delta']['statistical_observations']=546
            counts[key]['F195']=87
            d['authority']['mission_generation']=63
            d['authority']['orchestrator_decision']='F195_87_APPLIED_AND_USER_FREEZES_RECORDED'
            d['authority']['w1b_qa']='PASS_INCREMENTAL_F195_45_NUMERIC_3_LINEAGE_MARKERS'
            d['authority']['w1a_integration']='EXECUTABLE_EXACT_ONCE_PLAN_WITH_SOURCE_KEY_TESTS'
        ix['g63_operational_states']['F195']=current_state
        for sid in freeze_sids:
            ix['g63_operational_states'][sid]='FROZEN_CURRENT_ACHIEVEMENTS'
        for d in (ix,cat):
            if 'guards' in d:
                d['guards']=[g for g in d['guards'] if not (('F195' in g and ('42' in g or 'zero rows' in g)) or 'G63 totals are 10825' in g)]
                d['guards'].append('F195 registered public scope: 87 numerical observations, 3 separate source markers. No double count of the earlier 12; no rights promotion.')
        cat['canonical_write_disposition']='F195_45_INCREMENT_APPLIED_546_G63_TOTAL_FREEZES_RECORDED_FINAL_OPEN'
        mat['counting']['canonical_normalized_statistical_observations']=10870
        mat['counting']['g63_cumulative_admitted_statistical_observations']=546
        mat['g63_admission_breakdown']['F195']=87
        mat['current_source_family_updates']['F195']={'state':current_state,'admitted_rows':87,'public_scope_complete':True,'native_nonnumeric_markers':3,'owner':'ORCHESTRATOR','receipt':receipt_path}
        for sid in freeze_sids:
            update=mat['current_source_family_updates'].setdefault(sid,{})
            update['state']='FROZEN_CURRENT_ACHIEVEMENTS';update['reopening_condition']='New explicit user instruction; frozen residuals are not G63 extraction prerequisites.';update['owner']='ORCHESTRATOR'
        mat['status']='G63_FINAL_INGESTIONS_ACTIVE_F195_87_APPLIED_FREEZES_RECORDED';mat['generated_at']=now()
        pub=docs['statistics/public-export/catalogue-metadata-current.json']
        pub['canonical_counts']['normalized_statistical_observations']=10870
        pub['canonical_counts']['normalized_spatial_features']=278
        pub['authority']={'mission_generation':63,'schema_version':'5.8.1','phase_stage':'G63_FINAL_INGESTIONS_METADATA_ONLY','catalogue_blob':blob_sha(enc(cat)),'index_blob':blob_sha(enc(ix))}
        pub['scope']={'ids':'F01-F203','source_set_count':203,'next_unallocated':'F204','source_set_ids':['F'+str(i).zfill(2) for i in range(1,204)]}
        pub['guards']=[g for g in pub.get('guards',[]) if g!='No F195.' and 'manifest-tree' not in g]
        pub['guards'].append('Metadata only. F195 source data and controlled records are not publicly published by this projection.')
        pub.get('metadata_resolution',{}).pop('manifest_tree_sha',None)
        pub['schema_version']='3.0.0-metadata-only-current'
        ctrl=docs[CONTROL]
        ctrl['current_task']=None
        ctrl['status']='G63_FINAL_INGESTIONS_F195_87_APPLIED_USER_FREEZES'
        ctrl['phase_stage']='FINAL_SOURCE_DECISIONS_BEFORE_G63_CLOSURE'
        ctrl['source_disposition_authority']=AUTH
        ctrl['final_source_decisions']={'completed_numeric_ingestion':{'F195':87},'frozen':list(freeze_sids),'remaining_ingestions':['F67','F169','F170','F176'],'F203':'INVALID_22_ROW_CANDIDATE_REMAINS_EXCLUDED'}
        # Update known aggregate fields in its canonical-state subtree only.
        def recalc(x):
            if isinstance(x,dict):
                for k,v in list(x.items()):
                    if k in ('statistical_observations','normalized_statistical_observations','canonical_normalized_statistical_observations') and v==10825:x[k]=10870
                    elif k in ('g63_delta','g63_cumulative_admitted_statistical_observations') and v==501:x[k]=546
                    elif k=='F195' and v==42:x[k]=87
                    else:recalc(v)
            elif isinstance(x,list):
                for v in x:recalc(v)
        recalc(ctrl.get('canonical_state',{}))
        ctrl['last_applied_transaction']=receipt_path
        receipt={'schema_version':'1.0.0','decision_id':auth['decision_id'],'execution_id':EXECUTION,'public_run_id':int(RUN),'public_code_commit':os.environ['GITHUB_SHA'],'before_snapshot':snap,'claim_commit':claim,'approved_qa':{'path':QA,'blob':qa_sha},'source_table_blob':table_sha,'source_csv_blob':source_sha,'data_path':data_path,'data_sha256':digest(combined),'numeric_rows':87,'prior_numeric_rows_preserved':42,'new_numeric_rows':45,'source_markers':3,'canonical_total_after':10870,'g63_delta_after':546,'source_sets':203,'spatial_features':278,'frozen_sources':list(freeze_sids),'private_release':private_release,'tests':{'source_cells_matched':48,'unique_new_numeric_keys':45,'prior42_hash_unchanged':True,'earlier12_not_added_again':True,'canonical_preconditions_agree':True},'status':'ATOMIC_TRANSACTION_DATA_AND_PROJECTIONS','closure':'G63_NOT_YET_CLOSED'}
        changes={p:enc(d) for p,d in docs.items()}
        changes.update({data_path:combined,marker_path:enc(markers),receipt_path:enc(receipt)})
        pre[QA]=qa_sha;pre[qa['evidence']['normalized_data']]=table_sha;pre[qa['evidence']['source_utf8']]=source_sha
        applied=commit(changes,pre,'Apply F195 42+45 exactly once; freeze user-selected source achievements')
        owned=False
        print(json.dumps({'status':'PASS_PRIVATE_RELEASE_AND_ATOMIC_CANONICAL_READBACK','commit':applied,'F195':87,'statistical_observations':10870,'frozen_sources':list(freeze_sids),'receipt':receipt_path}))
    finally:
        if owned:
            try:
                r,s=read(CONTROL,head());d=json.loads(r)
                if (d.get('current_task') or {}).get('execution_id')==EXECUTION:
                    d['current_task']=None;d['last_failed_execution']=EXECUTION
                    commit({CONTROL:enc(d)},{CONTROL:s},'Release failed final-disposition execution claim; retain prior canonical data')
            except Exception:
                print('CLAIM_RELEASE_NOT_CONFIRMED')

if __name__=='__main__':
    run()
