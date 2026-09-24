#!/usr/bin/env python3
"""F68 current-task recovery using the pinned source-native spatial parser.
No producer reacquisition. All source bytes and outputs remain private.
"""
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time
from datetime import datetime, timezone
import requests
import extract_f68_preserved as old

TASK = 'F68-EXACT-PRESERVED-EXTRACTION'
BASE_SHA = 'c65a1a640592bb31f8cba14face424dea65862ea'
PART_SIZE = 320 * 1024 * 1024
RAW_PRESERVATION = None
TEAM = None
ORIGINAL_WORKER = None
PUT = old.put_private_content


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    obj, raw = old.get_private_content(path)
    return obj, json.loads(raw)


def guard():
    _, team = read_json(old.TEAM_PATH)
    binding = team.get('task_bindings', {}).get(TASK, {})
    if binding.get('owner') != 'W2C' or binding.get('mission_generation') != team['mission_generation']:
        raise old.Gate('CURRENT_EXPLICIT_F68_TASK_BINDING_REQUIRED')
    if binding.get('state') in ('CANCELLED', 'TRANSFERRED', 'COMPLETE'):
        raise old.Gate('F68_TASK_NOT_EXECUTABLE')
    if team['mission_generation'] != old.MISSION_GENERATION:
        raise old.Gate('CURRENT_GENERATION_CHANGED_EXPLICIT_REBIND_REQUIRED')
    return team


def put(path, data, message):
    # Only the worker overlay is upgraded. Evidence bytes remain unchanged so
    # the original parser's evidence SHA/size pointers remain valid.
    if path == old.WORKER_PATH:
        obj = json.loads(data)
        obj['schema_version'] = TEAM['schema_version']
        obj['mission_generation'] = old.MISSION_GENERATION
        obj['assignment_origin_generation'] = 54
        obj['task_id'] = TASK
        obj['assigned_task_id'] = TASK
        obj['previous_state'] = ORIGINAL_WORKER
        if 'window' in obj:
            obj['window']['mission'] = 'Current-generation exact preserved F68 extraction; origin G54.'
        if RAW_PRESERVATION:
            obj['durable_raw_preservation'] = RAW_PRESERVATION
        data = (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()
    for attempt in range(3):
        try:
            result = PUT(path, data, message.replace('G54', 'current F68'))
            _, actual = old.get_private_content(path)
            if actual != data:
                raise old.Gate('PRIVATE_WRITE_READBACK_MISMATCH:' + path)
            return result
        except old.Gate as exc:
            if '409' not in str(exc) or attempt == 2:
                raise
            time.sleep(attempt + 1)


def download_once(path, unused_alternate):
    url = f'https://api.github.com/repos/{old.PRIVATE_REPO}/actions/artifacts/{old.ARTIFACT_ID}/zip'
    h = hashlib.sha256()
    size = 0
    with requests.get(url, headers=old.gh_headers(old.READ_TOKEN), stream=True,
                      timeout=(30, 300)) as response:
        if response.status_code != 200:
            raise old.Gate(f'ARTIFACT_READ_HTTP_{response.status_code}')
        with open(path, 'wb') as target:
            for chunk in response.iter_content(8 * 1024 * 1024):
                if chunk:
                    target.write(chunk)
                    h.update(chunk)
                    size += len(chunk)
    if (size, h.hexdigest()) != (old.WRAPPER_BYTES, old.WRAPPER_SHA):
        raise old.Gate('PRESERVED_WRAPPER_IDENTITY_MISMATCH')
    return path, {'route': 'verified_current_credential_single_stream', 'bytes': size,
                  'sha256': h.hexdigest(), 'verified': True}


def release():
    url = f'https://api.github.com/repos/{old.PRIVATE_REPO}'
    repo = old.api_json('GET', url, old.WRITE_TOKEN)
    if repo.get('private') is not True:
        raise old.Gate('PRIVATE_DESTINATION_REQUIRED')
    r = requests.get(url + '/releases/tags/' + old.DESC_RELEASE_TAG,
                     headers=old.gh_headers(old.WRITE_TOKEN), timeout=60)
    if r.status_code == 200:
        return r.json()
    if r.status_code != 404:
        raise old.Gate(f'RELEASE_LOOKUP_HTTP_{r.status_code}')
    return old.api_json('POST', url + '/releases', old.WRITE_TOKEN, {
        'tag_name': old.DESC_RELEASE_TAG, 'target_commitish': old.PRIVATE_BRANCH,
        'name': 'F68 exact preserved COS2023v1-S2 and extraction descendants',
        'body': 'Private exact-byte preservation and source-native extraction. No public redistribution or observation admission.',
        'draft': False, 'prerelease': True})


def upload_verified(rel, path):
    size, sha = old.sha256_file(path)
    assets = old.api_json('GET', f'https://api.github.com/repos/{old.PRIVATE_REPO}/releases/{rel["id"]}/assets?per_page=100', old.WRITE_TOKEN)
    matches = [a for a in assets if a['name'] == path.name]
    if len(matches) > 1:
        raise old.Gate('DUPLICATE_RELEASE_ASSET_NAME')
    created = not matches
    if matches:
        asset = matches[0]
    else:
        with path.open('rb') as f:
            r = requests.post(rel['upload_url'].split('{')[0], params={'name': path.name},
                              headers={**old.gh_headers(old.WRITE_TOKEN), 'Content-Type': 'application/octet-stream',
                                       'Content-Length': str(size)}, data=f, timeout=(30, 900))
        if r.status_code not in (200, 201):
            raise old.Gate(f'PRIVATE_ASSET_UPLOAD_HTTP_{r.status_code}')
        asset = r.json()
    if asset.get('size') != size:
        raise old.Gate('PRIVATE_ASSET_SIZE_COLLISION')
    if asset.get('digest') and asset['digest'] != 'sha256:' + sha:
        raise old.Gate('PRIVATE_ASSET_DIGEST_COLLISION')
    h = hashlib.sha256()
    count = 0
    with requests.get(asset['url'], headers=old.gh_headers(old.READ_TOKEN, 'application/octet-stream'),
                      stream=True, timeout=(30, 300)) as r:
        if r.status_code != 200:
            raise old.Gate(f'PRIVATE_ASSET_READBACK_HTTP_{r.status_code}')
        for chunk in r.iter_content(8 * 1024 * 1024):
            if chunk:
                h.update(chunk)
                count += len(chunk)
    if (count, h.hexdigest()) != (size, sha):
        raise old.Gate('PRIVATE_ASSET_BYTE_READBACK_FAILED')
    return asset, created, {'name': path.name, 'bytes': size, 'sha256': sha,
                            'asset_id': asset['id'], 'readback': 'PASS'}


def preserve_and_upload(zip_path, zip_sha, zip_bytes):
    global RAW_PRESERVATION
    guard()
    rel = release()
    raw = zip_path.parent / old.RAW_MEMBER
    if old.sha256_file(raw) != (old.RAW_BYTES, old.RAW_SHA):
        raise old.Gate('RAW_PRESERVATION_INPUT_MISMATCH')
    parts = []
    n_parts = math.ceil(old.RAW_BYTES / PART_SIZE)
    with raw.open('rb') as source:
        for index in range(n_parts):
            part = zip_path.parent / f'{old.RAW_MEMBER}.part{index+1:03d}-of-{n_parts:03d}'
            part.write_bytes(source.read(PART_SIZE))
            _, _, receipt = upload_verified(rel, part)
            receipt['byte_offset'] = index * PART_SIZE
            parts.append(receipt)
            part.unlink()
        if source.read(1):
            raise old.Gate('RAW_SPLIT_NOT_EXHAUSTIVE')
    RAW_PRESERVATION = {'release_tag': rel['tag_name'], 'release_id': rel['id'],
                        'repository': old.PRIVATE_REPO, 'raw_name': old.RAW_MEMBER,
                        'raw_bytes': old.RAW_BYTES, 'raw_sha256': old.RAW_SHA,
                        'reassembly': 'Concatenate parts by ascending byte_offset; verify full size and SHA256 before use.',
                        'parts': parts, 'public_redistribution': False}
    manifest = zip_path.parent / 'F68-raw-reassembly-manifest.json'
    manifest.write_text(json.dumps(RAW_PRESERVATION, indent=2) + '\n')
    upload_verified(rel, manifest)
    put(old.OUT_BASE + '/raw-preservation.json', manifest.read_bytes(), 'F68: preserve exact private raw-byte reassembly manifest')
    if old.sha256_file(zip_path) != (zip_bytes, zip_sha):
        raise old.Gate('DESCENDANT_INPUT_IDENTITY_MISMATCH')
    asset, created, _ = upload_verified(rel, zip_path)
    return rel, asset, created


def main():
    global TEAM, ORIGINAL_WORKER
    source = Path(old.__file__).read_bytes()
    git_blob = hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest()
    if git_blob != BASE_SHA:
        raise old.Gate('LEGACY_SPATIAL_PARSER_CHANGED_REVIEW_REQUIRED')
    old.PUBLIC_TOKEN = ''
    if not old.READ_TOKEN or not old.WRITE_TOKEN:
        raise old.Gate('PRIVATE_READ_AND_SINK_CREDENTIAL_REQUIRED')
    _, TEAM = read_json(old.TEAM_PATH)
    old.MISSION_GENERATION = int(TEAM['mission_generation'])
    guard()
    worker_meta, worker = read_json(old.WORKER_PATH)
    if worker.get('current_task'):
        raise old.Gate('F68_WORKER_ALREADY_ACTIVE')
    if worker.get('assigned_task_id') != TASK:
        raise old.Gate('F68_WORKER_CURRENT_ASSIGNMENT_REQUIRED')
    if worker.get('status') == 'READY_NORMALIZATION_HANDOFF':
        print('F68 already complete; no unchanged execution.')
        return
    ORIGINAL_WORKER = {'git_blob_sha': worker_meta['sha'], 'mission_generation': worker.get('mission_generation'), 'last_output': worker.get('last_output')}
    meta = old.api_json('GET', f'https://api.github.com/repos/{old.PRIVATE_REPO}/actions/artifacts/{old.ARTIFACT_ID}', old.READ_TOKEN)
    if meta.get('expired') or meta.get('digest') != 'sha256:' + old.WRAPPER_SHA or meta.get('size_in_bytes') != old.WRAPPER_BYTES:
        raise old.Gate('ARTIFACT_METADATA_IDENTITY_MISMATCH')
    run = os.environ.get('GITHUB_RUN_ID', 'local-authorised')
    old.OUT_BASE = f'statistics/recovery-20260920/simple-runtime/outputs/W2C/G{old.MISSION_GENERATION}-F68-RESCUE-{run}'
    old.DESC_RELEASE_TAG = 'mn-f68-preserved-276ad30496322e95'
    request = json.loads(Path(old.REQUEST_PATH).read_text())
    request['mission_generation'] = old.MISSION_GENERATION
    old.REQUEST_PATH = str(Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'F68-current-request.json')
    Path(old.REQUEST_PATH).write_text(json.dumps(request))
    old.put_private_content = put
    old.current_team_guard = guard
    old.download_wrapper = download_once
    old.ensure_release_and_upload = preserve_and_upload
    worker.update({'schema_version': TEAM['schema_version'], 'mission_generation': old.MISSION_GENERATION,
                   'status': 'RUNNING_CURRENT_F68_RESCUE', 'current_task': {'task_id': TASK, 'run_id': run, 'started_at': now()}})
    put(old.WORKER_PATH, json.dumps(worker).encode(), 'F68: claim current exact-byte rescue')
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            old.main()
    except Exception as exc:
        receipt = {'task_id': TASK, 'status': 'BLOCKED_EXACT_RESCUE', 'at': now(),
                   'error': str(exc), 'producer_reacquisition': False, 'run_id': run}
        put(old.OUT_BASE + '/blocker.json', json.dumps(receipt).encode(), 'F68: persist current rescue blocker')
        _, failed = read_json(old.WORKER_PATH)
        failed.update({'status': 'BLOCKED_EXACT_RESCUE', 'current_task': None, 'last_output': old.OUT_BASE + '/blocker.json', 'blocker': receipt})
        put(old.WORKER_PATH, json.dumps(failed).encode(), 'F68: release task after exact blocker')
        raise
    print('PASS: exact F68 preservation, extraction and private byte readback; no public data publication.')


if __name__ == '__main__':
    main()
