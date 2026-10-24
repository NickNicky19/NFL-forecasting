"""Opaque deterministic private bundles and relocation; never deserialize models."""
from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat

from . import private_draft_store as store

VERSION='weekly-owner-bootstrap-file-bundle-v1'
INFLATED=12<<20
GROUP_JSON=(8<<20)-(64<<10)  # Conservative fixed grouping; compression never expands the cap.
MAX_FILES=64
CHUNK=49152  # Multiple of3; concatenated base64 remains canonical.
FILE_KEYS={'logical_path','path','bytes','sha256','kind','origin','required'}


def require(value,code):
    if not value:raise store.StoreError(code)


def logical(value):
    require(isinstance(value,str) and 0<len(value)<=240 and '\\' not in value and ':' not in value,'LOGICAL_PATH')
    path=PurePosixPath(value)
    require(not path.is_absolute() and str(path)==value and all(p not in {'.','..',''} and not p.startswith('.') for p in path.parts),'LOGICAL_PATH')
    require(not any(p.lower() in {'.git','.env','credentials','ledger.jsonl','execution'} for p in path.parts),'FORBIDDEN_SCOPE')
    return value


def validate_files(files):
    require(isinstance(files,list) and 0<len(files)<=512,'FINITE_FILE_WHITELIST')
    names=set();paths=set()
    for item in files:
        require(set(item)==FILE_KEYS and type(item['bytes']) is int and 0<item['bytes']<=store.ASSET_CAP
            and store.HASH.fullmatch(item['sha256']) and type(item['required']) is bool
            and item['kind'] in {'model','model_manifest','forecast','completion','identity','feature','query','source_manifest','source_raw','projection','control'},'CLOSED_FILE_SCOPE')
        logical(item['logical_path']);path=store.parents_safe(item['path'])
        require(str(path)==item['path'] and item['logical_path'] not in names and item['path'] not in paths,'DUPLICATE_FILE_SCOPE')
        require(isinstance(item['origin'],dict) and set(item['origin'])=={'source_path','source_sha256','source_policy_sha256'}
            and item['origin']['source_path']==item['path'] and item['origin']['source_sha256']==item['sha256']
            and store.HASH.fullmatch(item['origin']['source_policy_sha256']),'ORIGINAL_ORIGIN_REQUIRED')
        names.add(item['logical_path']);paths.add(item['path'])
    return files


def inflated_size(files):
    # Same canonical byte order as encode(); base64 length uses only metadata.
    total=len(b'{"files":[],"schema_version":"'+VERSION.encode()+b'"}')
    for index,item in enumerate(files):
        header=dict(bytes=item['bytes'],content_b64='',origin=item['origin'],path=item['logical_path'],sha256=item['sha256'])
        total+=len(store.canonical(header))+4*((item['bytes']+2)//3)+(1 if index else 0)
    return total


def groups(files):
    validate_files(files);result=[];current=[]
    for item in sorted(files,key=lambda x:(not x['required'],x['logical_path'])):
        require(inflated_size([item])<=GROUP_JSON,'SINGLE_FILE_BUNDLE_CAP')
        if current and (len(current)==MAX_FILES or inflated_size(current+[item])>GROUP_JSON):result.append(current);current=[]
        current.append(item)
    if current:result.append(current)
    require(len(result)<=16,'FINITE_BUNDLE_COUNT')
    return result


class CappedBuffer(io.BytesIO):
    def write(self,body):
        require(self.tell()+len(body)<=store.ASSET_CAP,'COMPRESSED_BUNDLE_CAP')
        return super().write(body)


def encode(files):
    """At most one8MiB compressed buffer plus64KiB streaming working blocks."""
    validate_files(files);require(len(files)<=MAX_FILES and inflated_size(files)<=INFLATED,'INFLATED_BUNDLE_CAP')
    output=CappedBuffer();written=0
    with gzip.GzipFile(fileobj=output,mode='wb',filename='',mtime=0,compresslevel=9) as zipped:
        def write(body):
            nonlocal written
            require(written+len(body)<=INFLATED,'INFLATED_BUNDLE_CAP');written+=len(body);zipped.write(body)
        write(b'{"files":[')
        for index,item in enumerate(files):
            if index:write(b',')
            write(b'{"bytes":'+str(item['bytes']).encode()+b',"content_b64":"')
            parent,name=store.parent_fd(item['path'])
            try:fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
            finally:os.close(parent)
            try:
                before=os.fstat(fd);require(stat.S_ISREG(before.st_mode) and before.st_size==item['bytes'],'OPAQUE_FILE_SIZE')
                count=0;digest=hashlib.sha256();carry=b''
                while True:
                    chunk=os.read(fd,CHUNK)
                    if not chunk:break
                    count+=len(chunk);require(count<=item['bytes'],'OPAQUE_FILE_SIZE');digest.update(chunk)
                    pending=carry+chunk;whole=(len(pending)//3)*3
                    if whole:write(base64.b64encode(pending[:whole]))
                    carry=pending[whole:]
                if carry:write(base64.b64encode(carry))
                after=os.fstat(fd)
                stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mode,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
                require(count==item['bytes'] and digest.hexdigest()==item['sha256'] and stamp(after)==stamp(before),'OPAQUE_FILE_HASH_OR_CHANGE')
            finally:os.close(fd)
            write(b'","origin":'+store.canonical(item['origin'])+b',"path":'+store.canonical(item['logical_path'])+b',"sha256":'+store.canonical(item['sha256'])+b'}')
        write(b'],"schema_version":'+store.canonical(VERSION)+b'}')
    require(written==inflated_size(files),'ENCODER_SIZE_CONTRACT')
    return output.getvalue(),written


def freeze(files,*,binding,qualification,rights,source_sha,code_pins):
    """Invoke only after packaging GO; returns metadata, never retains bundles."""
    validate_files(files)
    require(rights.get('schema_version')=='weekly-owner-bootstrap-rights-review-v1' and rights.get('approved') is True
        and rights.get('basis')=='OWNER_DELEGATED_OCT24_PRIVATE_ONLY' and rights.get('human_review_claim') is False,
        'EXPLICIT_PRIVATE_RIGHTS_REVIEW_REQUIRED')
    allowed=set(rights['approved_logical_paths']);require(allowed<=set(i['logical_path'] for i in files),'RIGHTS_SCOPE')
    required=[i for i in files if i['required']];optional=[i for i in files if not i['required']]
    require(all(i['logical_path'] in allowed for i in required),'REQUIRED_RIGHTS_MISSING')
    payloads=[];pending=[];total=binding['canary_bytes'];index=0
    optional_fit=[]
    for item in optional:
        if item['logical_path'] in allowed:
            if inflated_size([item])<=GROUP_JSON:optional_fit.append(item)
            else:pending.append(dict(logical_path=item['logical_path'],reason='RAW_ARCHIVE_PENDING_SINGLE_FILE_CAP'))
    # Required groups precede optional raw archival groups; no mixed required/raw group.
    for cohort in (required,optional_fit):
        for members in groups(cohort) if cohort else []:
            body,inflated=encode(members);record=dict(index=index,bytes=len(body),sha256=store.sha(body),inflated_bytes=inflated,files=members)
            if total+len(body)+262144>store.TOTAL_CAP:
                require(not members[0]['required'],'REQUIRED_REMOTE_CAP')
                pending.extend(dict(logical_path=i['logical_path'],reason='RAW_ARCHIVE_PENDING_REMOTE_CAP') for i in members)
            else:payloads.append(record);total+=len(body);index+=1
            del body
    pending.extend(dict(logical_path=i['logical_path'],reason='RAW_ARCHIVE_PENDING_RIGHTS_REVIEW') for i in optional if i['logical_path'] not in allowed)
    require(payloads and len(payloads)<=8 and 1+2*len(payloads)<=store.MAX_ASSETS,'BOOTSTRAP_REMOTE_SCOPE_CAP')
    return dict(schema_version='weekly-owner-bootstrap-root-manifest-v1',repository=store.REPO,source_sha=source_sha,
        source_code_pins=code_pins,release_binding=binding,qualification=qualification,rights_review=rights,
        source_policy_sha256=files[0]['origin']['source_policy_sha256'],bundles=payloads,pending_raw_archive=pending,
        total_payload_bytes=sum(p['bytes'] for p in payloads),remote_metadata_reserve_bytes=262144,
        public_export=False,scope_encoding='OPAQUE_ONLY_NO_MODELS_OR_TARGETS_DECODED')


def verify_bundle(body,record):
    require(len(body)==record['bytes']<=store.ASSET_CAP and store.sha(body)==record['sha256'],'BUNDLE_HASH')
    plain=bytearray()
    with gzip.GzipFile(fileobj=io.BytesIO(body),mode='rb') as stream:
        while True:
            chunk=stream.read(min(65536,INFLATED-len(plain)+1))
            if not chunk:break
            require(len(plain)+len(chunk)<=INFLATED,'INFLATED_BUNDLE_CAP');plain.extend(chunk)
    require(len(plain)==record['inflated_bytes']<=INFLATED,'INFLATED_BUNDLE_CAP')
    try:document=json.loads(plain)
    except (ValueError,UnicodeError):raise store.StoreError('BUNDLE_JSON') from None
    require(set(document)=={'schema_version','files'} and document['schema_version']==VERSION
        and len(document['files'])==len(record['files'])<=MAX_FILES,'CLOSED_BUNDLE')
    expected={i['logical_path']:i for i in record['files']};seen=set();result=[]
    for file in document['files']:
        require(set(file)=={'path','bytes','sha256','origin','content_b64'},'CLOSED_BUNDLE_FILE');name=logical(file['path'])
        require(name in expected and name not in seen,'BUNDLE_FILE_SCOPE');seen.add(name);original=expected[name]
        require((file['bytes'],file['sha256'],file['origin'])==(original['bytes'],original['sha256'],original['origin']),'BUNDLE_FILE_ORIGIN')
        try:value=base64.b64decode(file['content_b64'],validate=True)
        except (ValueError,TypeError):raise store.StoreError('BUNDLE_BASE64') from None
        require(len(value)==file['bytes'] and store.sha(value)==file['sha256'],'BUNDLE_FILE_HASH');result.append((name,value))
    return result


def extract_owned(body,record,storage,destination):
    """Closed verified extraction through original owned CAS; no raw os archive."""
    files=verify_bundle(body,record);destination=store.parents_safe(destination)
    with storage.transaction():
        for name,_ in files:
            target=store.parents_safe(destination/name);require(not target.exists(),'EXTRACTION_EXISTS')
        storage._require(sum(len(value) for _,value in files))
        for name,value in files:storage.write_bytes(destination/name,value)
    return dict(files=len(files),bytes=sum(len(value) for _,value in files),model_decodes=0)


def relocate_future_manifest(original_ref,model_ref,destination,storage):
    """Preserve original JSON/hash and opaque weights; issue a NEW path-bound manifest."""
    raw=store.read_local(original_ref['path'],256<<10)
    require(store.sha(raw)==original_ref['sha256'] and len(raw)==original_ref['bytes'],'ORIGINAL_MANIFEST_HASH')
    original=json.loads(raw);require(original['schema_version']=='weekly-adaptive-release-v1-future-inference'
        and original['artifact_kind']=='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY' and not original['dependencies'],'STANDALONE_FUTURE_MANIFEST_ONLY')
    require((model_ref['sha256'],model_ref['bytes'])==(original['model']['sha256'],original['model']['bytes']),'UNCHANGED_MODEL_REQUIRED')
    from .owned_reference_batch import validate_owned_references
    validate_owned_references(storage,{model_ref['path']:model_ref['sha256'],original_ref['path']:original_ref['sha256']})
    destination=store.parents_safe(destination);model_path=destination/'trained.joblib';manifest_path=destination/'future-inference.json'
    with storage.transaction():
        require(not destination.exists(),'RELOCATION_FRESH_ROOT')
        storage._require(model_ref['bytes']+len(raw)+262144)
        storage.import_file(model_ref['path'],model_path,expected_sha256=model_ref['sha256'])
        storage.write_bytes(destination/'original-future-inference.json',raw)
        relocated=dict(original,model=dict(path=str(model_path),bytes=model_ref['bytes'],sha256=model_ref['sha256']),
            relocation=dict(schema_version='weekly-owner-bootstrap-future-relocation-v1',original_manifest=original_ref,
                original_model=original['model'],relocated_model_path=str(model_path),parameters_fixtures_code_source_unchanged=True,model_decodes=0))
        encoded=store.canonical(relocated);storage.write_bytes(manifest_path,encoded)
    return dict(path=str(manifest_path),bytes=len(encoded),sha256=store.sha(encoded),original_manifest_sha256=original_ref['sha256'],old_path_hash_reproduced=False)
