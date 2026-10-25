"""Real child processes/owned CAS, fictional status bytes and native boundaries.

Runner initialization/authentication is deliberately not exercised. Only native
archive/core append and client factory are injected; record_failure, codecs,
child control/status writes and failure-scope collection are production code.
An explicit local original-source path permits before/after method isolation.
No actual Actions authority, POST, model, source, forecast or outcome is used.
"""
import ast
import base64
from datetime import timedelta
import gzip
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import pytest

from nfl_lab import audit_weekly_hosted_v1 as hosted
from nfl_lab import operational_failure_v1 as failure
from nfl_lab import private_draft_store as store, gha_private_checkpoint as cp
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.owned_reference_batch import validate_owned_references

ROOT=Path(__file__).resolve().parents[1]
OUT_PREFIX=b"FICTIONAL child stdout prefix\x00\xff\x80"
ERR_PREFIX=b"FICTIONAL child stderr prefix\xfe\x00\x81"


def runner_type():
    original=os.environ.get('AUDIT_WEEKLY_CHILD_TEST_ORIGINAL_SOURCE')
    if not original:
        return hosted.Runner
    path=Path(original)
    tree=ast.parse(path.read_bytes(),filename=str(path))
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Runner')
    names={'child','preserve_failure','preserve_opaque_outputs','operation_go','failure_client'}
    methods=[n for n in node.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods}==names,'all original methods required; never skip failed assertions'
    isolated=ast.ClassDef(name='OriginalRunner',bases=[],keywords=[],body=methods,decorator_list=[])
    namespace=dict(vars(hosted))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[isolated],type_ignores=[])),str(path),'exec'),namespace)
    return namespace['OriginalRunner']


@pytest.fixture
def runner(tmp_path):
    r=object.__new__(runner_type());r.root=tmp_path/'fictional-attempt'
    r.storage=OperationalStorage(r.root/'cache',ROOT/'config/operational-source-policy-v2.json',state=r.root/'state')
    r.storage.register_root(r.root);r.phase='produce';r.child_number=0
    r.started=hosted.now_utc()-timedelta(seconds=2)
    r.env=dict(PATH=os.defpath,GITHUB_OUTPUT=str(tmp_path/'outputs'),AUDIT_WEEKLY_ORIGINAL_EXIT_CODE='1')
    Path(r.env['GITHUB_OUTPUT']).touch()
    runtime='b'*32;canary='e'*64
    binding=dict(schema_version='weekly-private-draft-binding-v2',repository=store.REPO,runtime_id=runtime,
        origin_run_id='49900000000',release_id=91,tag_name='weekly-private-runtime-v2-'+runtime,
        canary_asset_id=100,canary_name='canary-'+canary+'.txt',canary_sha256=canary,canary_bytes=117,
        browser_tag='weekly-private-runtime-v2-'+runtime,config_sha256=store.config_sha())
    store.checked_binding(binding)  # Closed fictional metadata, no platform authority.
    r.go=dict(qualified_runtime=dict(binding=binding,qualification={}),pending_census=dict(reservations=[]))
    r.go_sha='a'*64
    r.root_ref=hosted.write(r.storage,r.root/'OWNER_ROOT.json',dict(fictional_root=True,successful_forecast=False))
    r.identity=dict(execution_lane='github_actions',repository=store.REPO,run_id='49900000000',run_attempt=1,source_sha='c'*40,
        process_identity='d'*64,job_id=hosted.JOBS['produce'],api_job_id=777,permission='write',
        workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/fictional')
    r.job=dict(fictional_job=True)
    r.journal=r.storage.register_root(r.root/'journal')
    r.check=lambda:None  # Only the independently authorized child/control method is under test.
    return r


def append_boundary(r,monkeypatch,*,archive_success=False):
    observed=dict(archives=[],core=[],factory_calls=[])
    def archive_append(snapshot,factory,package,**kwargs):
        observed['archives'].append(snapshot)
        assert callable(factory) and package is r.go['qualified_runtime']
        assert kwargs['output']==r.root/'failure-archive-produce'
        assert kwargs['jobs']==hosted.JOBS and kwargs['root_go_sha256']==r.go_sha
        assert snapshot['census']['archive_state']=='FAILURE_EVIDENCE'
        assert snapshot['census']['successful_forecast'] is snapshot['census']['public_release'] is False
        assert snapshot['census']['raw_HTTP_corpus_archived'] is snapshot['census']['model_weights_reuploaded'] is False
        if not archive_success:
            raise store.StoreError('FICTIONAL_SECONDARY_APPEND_UNAVAILABLE')
        hosted.archive.validate_files(snapshot['files'])
        validate_owned_references(r.storage,{f['path']:f['sha256'] for f in snapshot['files']})
        paths={f['logical_path']:Path(f['path']) for f in snapshot['files']}
        assert hosted.archive.validate_capture(snapshot,paths.__getitem__,complete=False)['qualified_selected'] is False
        intent=hosted.archive.fresh(r.storage,kwargs['output'])
        hosted.write(r.storage,intent/'APPEND_INTENT.json',dict(fictional_native_boundary=True,archive_state='FAILURE_EVIDENCE'))
        raw=gzip.compress(b'FICTIONAL_FAILURE_INDEX',mtime=0)
        entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=cp.payload(raw),payload_asset_id=201,
            payload_name='blob-'+store.sha(raw)+'.bin',producer_process=r.identity['process_identity'],
            binding_sha256=hosted.digest(package['binding']),writer_run_id=r.identity['run_id'])
        descriptor=dict(entry=entry,manifest_asset_id=200,manifest_sha256=hosted.digest(entry),manifest_bytes=len(store.canonical(entry)))
        return dict(schema_version=hosted.archive.VERSION+'-handoff',repository=store.REPO,source_sha=r.identity['source_sha'],
            run_id=r.identity['run_id'],root_go_sha256=r.go_sha,producer=r.identity,runtime_binding=package['binding'],
            index_descriptor=descriptor,files_sha256=hosted.digest(snapshot['files']),archive_state='FAILURE_EVIDENCE',jobs=hosted.JOBS)
    def core_append(client,storage,output,**kwargs):
        request,bodies=failure.unpack((output/'FAILURE.json.gz').read_bytes())
        assert request['state']=='FAILED' and request['failure']['exit_code']==1
        assert kwargs['inputs']['payload_manifest']==store.canonical(failure.payload_manifest((output/'FAILURE.json.gz').read_bytes()))
        assert type(kwargs['authorization']) is bytes and store.sha(kwargs['authorization'])==kwargs['authorization_sha256']
        observed['core'].append((request,{item['label']:body for item,body in zip(request['attachments'],bodies)}))
        return dict(descriptor=dict(fictional_native_append=True))
    def factory(operation):
        observed['factory_calls'].append(operation);assert operation=='append';return object()
    monkeypatch.setattr(hosted.archive,'produce',archive_append)
    monkeypatch.setattr(failure,'append_failure',core_append)
    monkeypatch.setattr(r,'failure_client',factory)
    return observed


def auxiliary_files(attachments):
    records={};labels=[]
    for label,body in attachments.items():
        if not re.fullmatch(r'complete-auxiliary-controls(?:-[0-9]{2})?',label):continue
        assert len(body)<=failure.ATTACHMENT_CAP
        labels.append(label);document=cp.strict_json(body)
        assert document['schema_version']==hosted.VERSION+'-complete-auxiliary-controls'
        for record in document['files']:
            assert record['relative_path'] not in records,'no duplicate or silently overwritten original controls'
            raw=base64.b64decode(record['body_base64'],validate=True)
            assert base64.b64encode(raw).decode()==record['body_base64']
            assert len(raw)==record['bytes'] and store.sha(raw)==record['sha256']
            records[record['relative_path']]=raw
    assert 'complete-auxiliary-controls' in labels,'legacy first label must remain'
    return records,labels


@pytest.mark.parametrize('mode,code,state,reason',[
    ('sigterm',-15,'INVALID_CHILD_STATUS','WEEKLY_CHILD_STATUS_INVALID'),
    ('timeout',-9,'DEADLINE','WEEKLY_CHILD_DEADLINE'),
    ('malformed',0,'INVALID_CHILD_STATUS','WEEKLY_CHILD_STATUS_INVALID'),
    ('safe_nonzero',17,None,'FICTIONAL_SAFE_CHILD_FAILURE'),
])
def test_actual_child_preserves_exit_raw_stdio_and_core_codec(runner,tmp_path,monkeypatch,mode,code,state,reason):
    r=runner;marker=tmp_path/'controlled-child-started'
    safe=dict(state='FAILED_RETAINED',reason='FICTIONAL_SAFE_CHILD_FAILURE',successful_forecast=False)
    stdout=store.canonical(safe) if mode=='safe_nonzero' else OUT_PREFIX
    source='import os,signal,sys,time;from pathlib import Path;os.write(1,%r);os.write(2,%r);Path(sys.argv[1]).write_bytes(b"started");'% (stdout,ERR_PREFIX)
    source += {'sigterm':'os.kill(os.getpid(),signal.SIGTERM)', 'timeout':'time.sleep(30)',
        'malformed':'sys.exit(0)','safe_nonzero':'sys.exit(17)'}[mode]
    real_popen=subprocess.Popen;processes=[]
    def controlled(command,**kwargs):
        assert command[3].endswith('/tools/fictional_child.py') and command[4]=='infer'
        assert kwargs['start_new_session'] is True
        p=real_popen([sys.executable,'-I','-B','-c',source,str(marker)],**kwargs);processes.append(p)
        deadline=time.monotonic()+5
        while not marker.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        assert marker.exists(),'controlled child must flush both prefixes before timeout starts'
        return p
    monkeypatch.setattr(hosted.subprocess,'Popen',controlled)
    try:
        with pytest.raises(store.StoreError,match=reason):
            r.child('fictional_child','infer',dict(fictional_request=True),dict(fictional_authority=True),'FICTIONAL_AUTHORITY',.05 if mode=='timeout' else 5)
    finally:
        for process in processes:
            if process.poll() is None:os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=5)
    assert len(processes)==1 and processes[0].returncode==code
    prefix='phase-status/01-infer'
    status=hosted.read_owned(r.storage,cp.binding(r.root/(prefix+'.json')))
    assert status['exit_code']==code
    if state:
        assert status['state']==state
        assert status['stdout_sha256']==store.sha(stdout) and status['stderr_sha256']==store.sha(ERR_PREFIX)
    else:assert status['status']==safe
    expected={prefix+'.stdout':stdout,prefix+'.stderr':ERR_PREFIX}
    for name,body in expected.items():
        ref=cp.binding(r.root/name)
        validate_owned_references(r.storage,{ref['path']:ref['sha256']})
        assert Path(ref['path']).read_bytes()==body
    boundary=append_boundary(r,monkeypatch)
    result=r.preserve_failure()
    assert len(boundary['core'])==1
    request,attachments=boundary['core'][0]
    controls,labels=auxiliary_files(attachments)
    assert controls==expected and labels==['complete-auxiliary-controls']
    retained=[cp.strict_json(raw) for label,raw in attachments.items() if re.fullmatch('phase-[0-9]{2}',label)]
    assert retained==[status],'core envelope must preserve the original negative/zero status too'
    assert result['successful_forecast'] is result['public_release'] is False


def test_normal_archive_failure_gets_distinct_failure_only_append_and_batched_raw_controls(runner,monkeypatch):
    r=runner;normal=r.storage.register_root(r.root/'archive-produce')
    old={}
    for name in ('CONSUMED.json','ADMISSION.json','HANDOFF.json'):
        path=normal/'transport'/name
        r.storage.write_bytes(path,store.canonical(dict(fictional_failed_normal_archive=name)))
        old[path.relative_to(normal).as_posix()]=path.read_bytes()
    raw=b'FICTIONAL unresolved original archive POST'
    pending=cp.reservation_metadata('asset:blob-'+store.sha(raw)+'.bin',raw,'blob-'+store.sha(raw)+'.bin')
    path=normal/'journal'/'original.reservation.json';r.storage.write_bytes(path,store.canonical(pending))
    old[path.relative_to(normal).as_posix()]=path.read_bytes()
    expected={}
    for n in range(8):
        for stream in ('stdout','stderr'):
            name=f'phase-status/{20+n:02}-fictional.{stream}'
            body=(bytes([255-n])+b'\x00\x80FICTIONAL_STDIO')*4096
            body=body[:64<<10];r.storage.write_bytes(r.root/name,body);expected[name]=body
    hosted.write(r.storage,r.root/'phase-status/PARENT_FAILED.json',dict(state='FAILED_RETAINED',successful_forecast=False))
    partial=b'FICTIONAL_INCOMPLETE_PRIVATE_BYTES\x00\xff'
    r.storage.write_bytes(r.root/'runtime/selected.jsonl.gz',partial)
    boundary=append_boundary(r,monkeypatch,archive_success=True)
    result=r.preserve_failure()
    assert result['partial_forecast_archive_state']=='FAILURE_EVIDENCE'
    assert result['successful_forecast'] is result['public_release'] is False
    assert len(boundary['archives'])==len(boundary['core'])==1 and boundary['factory_calls']==['append']
    snapshot=boundary['archives'][0];files={f['logical_path']:Path(f['path']).read_bytes() for f in snapshot['files']}
    for name,body in old.items():
        logical='failed/original-archive/'+name.removeprefix('transport/')
        assert files[logical]==body
        assert (normal/name).read_bytes()==body
    assert files['failed/runtime/selected.jsonl.gz']==partial
    seeded=r.journal/(store.sha(pending['key'].encode())+'.reservation.json')
    assert seeded.read_bytes()==store.canonical(pending),'unchanged seed_pending must charge unresolved original POST'
    controls,labels=auxiliary_files(boundary['core'][0][1])
    assert controls==expected and labels==['complete-auxiliary-controls','complete-auxiliary-controls-01']
    assert (r.root/'failure-archive-produce/APPEND_INTENT.json').is_file()
    intent=(r.root/'failure-archive-produce/APPEND_INTENT.json').read_bytes()
    package=(r.root/'failure-evidence/FAILURE.json.gz').read_bytes()
    with pytest.raises(store.StoreError,match='FAILED_ATTEMPT_PRESERVATION_ALREADY_CONSUMED'):
        r.preserve_failure()
    assert len(boundary['archives'])==len(boundary['core'])==1,'neither original nor new failure intent may retry'
    assert (r.root/'failure-archive-produce/APPEND_INTENT.json').read_bytes()==intent
    assert (r.root/'failure-evidence/FAILURE.json.gz').read_bytes()==package
    assert all((normal/name).read_bytes()==body for name,body in old.items())


def test_all_original_archive_intents_and_pending_survive_fresh_failure_append_without_resume(runner,monkeypatch):
    r=runner;normal=r.storage.register_root(r.root/'archive-produce');old={}
    names=['CONSUMED.json','ADMISSION.json','HANDOFF.json','APPEND_FAILED.json','APPENDED.json']
    names += [f'APPEND_INTENT_{n}.json' for n in range(9)]
    for n,name in enumerate(names):
        # Deliberately noncanonical originals, including an interrupted binary
        # tail. Failure evidence must preserve bytes, not parse or repair JSON.
        body=(b'{ "fictional_original_control" : '+str(n).encode()+b' }\n')
        if name=='APPEND_FAILED.json':body+=b'\x00\xff\x80'
        path=normal/'transport'/name;r.storage.write_bytes(path,body)
        old[path.relative_to(normal).as_posix()]=(body,path.stat().st_dev,path.stat().st_ino)
    pending=[]
    for n,kind in enumerate(('blob','manifest','blob')):
        raw=b'FICTIONAL ambiguous original POST\x00'+bytes([n])* (127+n)
        name=kind+'-'+store.sha(raw)+('.bin' if kind=='blob' else '.json')
        record=cp.reservation_metadata('asset:'+name,raw,name);pending.append(record)
        path=normal/'journal'/str(n)/'original.reservation.json'
        r.storage.write_bytes(path,store.canonical(record))
        old[path.relative_to(normal).as_posix()]=(path.read_bytes(),path.stat().st_dev,path.stat().st_ino)
    boundary=append_boundary(r,monkeypatch,archive_success=True)
    append=hosted.archive.produce;charges=[]
    def charged_before_native_append(snapshot,factory,package,**kwargs):
        # Real inventory accounting against an empty fictional remote listing.
        # Its transport seam grants no native authentication/durability claim.
        class Inventory:
            binding=r.go['qualified_runtime']['binding']
            journal=r.journal
            path=store.Client.path
            def allow(self,url):return url
            def json(self,url):
                assert url==self.path('/releases/91/assets?per_page=100&page=1')
                return []
        inventory=Inventory();assets,total=store.Client.inventory(inventory)
        assert assets==[] and total==sum(record['bytes'] for record in pending)
        assert inventory.inventory_slots==len(pending)
        for record in pending:
            path=r.journal/(store.sha(record['key'].encode())+'.reservation.json')
            assert path.read_bytes()==store.canonical(record)
        charges.append((total,inventory.inventory_slots))
        return append(snapshot,factory,package,**kwargs)
    monkeypatch.setattr(hosted.archive,'produce',charged_before_native_append)
    result=r.preserve_failure()
    assert result['partial_forecast_archive_state']=='FAILURE_EVIDENCE'
    assert result['successful_forecast'] is result['public_release'] is False
    assert len(charges)==len(boundary['archives'])==len(boundary['core'])==1
    files={f['logical_path']:f for f in boundary['archives'][0]['files']}
    original_controls={name for name in files if name.startswith('failed/original-archive/')}
    expected={'failed/original-archive/'+name.removeprefix('transport/') for name in old}
    assert original_controls==expected,'no original intent, status or journal may be silently omitted'
    for name,(body,device,inode) in old.items():
        original=normal/name;logical='failed/original-archive/'+name.removeprefix('transport/')
        assert Path(files[logical]['path']).read_bytes()==body
        assert (files[logical]['bytes'],files[logical]['sha256'])==(len(body),store.sha(body))
        assert original.read_bytes()==body and (original.stat().st_dev,original.stat().st_ino)==(device,inode)
    intent=r.root/'failure-archive-produce/APPEND_INTENT.json'
    assert intent.is_file() and not (normal/'APPEND_INTENT.json').exists()
    before=intent.read_bytes()
    with pytest.raises(store.StoreError,match='FAILED_ATTEMPT_PRESERVATION_ALREADY_CONSUMED'):
        r.preserve_failure()
    assert len(charges)==len(boundary['archives'])==len(boundary['core'])==1
    assert intent.read_bytes()==before
    assert all((normal/name).read_bytes()==body for name,(body,_,_) in old.items())
