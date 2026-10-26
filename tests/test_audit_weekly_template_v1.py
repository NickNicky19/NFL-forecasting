"""Invented metadata, real native byte codec, in-memory HTTP; no models."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from nfl_lab import audit_weekly_template_v1 as t, audit_weekly_controller_v1 as c
from nfl_lab import private_draft_store as s
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_weekly_template_v1 as cli
import test_audit_weekly_controller_v1 as cf
from test_audit_weekly_controller_v1 import system as controller_system
from test_private_draft_store_v2 import Server, Response
from test_owner_private_bootstrap import qualification, RUN as QRUN

ROOT=Path(__file__).resolve().parents[1]
RUN='40000000002'; SOURCE='b'*40
WRITER='audit-weekly-produce-v1'; READER='audit-weekly-restore-v1'


from test_audit_weekly_controller_bootstrap_v1 import fictional_runtime_metadata,dual_runtime_root


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *_:pytest.fail('REAL_NETWORK_FORBIDDEN'))


def document(x):
    pins=deepcopy(x.p['producer']['code_pins'])
    root={key:None for key in t.ROOT_KEYS}
    slots=[dict(target=a,family=b,method_id=d,procedure_version='1'*64,model_sha256='2'*64,
        manifest_sha256='3'*64,transport_manifest_sha256='4'*64) for a,b,d in t.JOBS]
    root.update(schema_version='audit-weekly-hosted-v2-root-GO',approved=False,repository=s.REPO,
        mode='audit-weekly-producer-v1',source_sha=SOURCE,code_pins=pins,single_writer_group='nfl-lab-single-writer',
        workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/research/current-producer',
        retained_registration=dict(schema_version='audit-count-retained-v1-registration',approved=True,
            maximum_new_fits=0,public_release=False,origin=dict(replay_catalog=dict(slots=slots))))
    return dict(schema_version=t.VERSION+'-static',source_sha=SOURCE,code_pins=pins,
        readiness=deepcopy(x.p['readiness']),root_template=root)


@pytest.fixture
def dual_document(tmp_path):
    from test_audit_weekly_controller_bootstrap_v1 import system,locator_system
    base=tmp_path/'dual-template-metadata';base.mkdir()
    x=locator_system.__wrapped__(system.__wrapped__(base))
    package=deepcopy(x.package)
    census=dict(schema_version='audit-private-rotation-v1-pending-census',complete=True,
        as_of_utc=package['qualification']['before_proof']['started_at_utc'],owner_evidence_sha256='a'*64,reservations=[])
    package['quota_reservation'].update(pending_records=0,pending_census_sha256=t.digest(census))
    value=deepcopy(x.prepared.document);old=value['root_template']
    old['qualified_runtime']=package;old['pending_census']=census
    anchor=dict(feed_sha256='1'*64,receipt_sha256='2'*64)
    value.update(schema_version=t.STATIC_V3,root_template=dual_runtime_root(old,package,census,anchor,original_root=old))
    return value


def test_v3_static_dual_runtime_selects_exact_old_anchor_and_unique_checkpoint(dual_document):
    value=dual_document;prepared=t.prepare(value);root=prepared.document['root_template'];old=root['prior_capture_qualified_runtime']
    original=s.canonical(old)
    assert t.capture_runtime(root,anchor=old['anchor'])==(old['qualified_runtime'],old['pending_census'])
    other=dict(feed_sha256='3'*64,receipt_sha256='4'*64)
    assert t.capture_runtime(root,anchor=other)==(root['qualified_runtime'],root['pending_census'])
    for package in (root['qualified_runtime'],old['qualified_runtime']):
        h=dict(runtime_binding_sha256=t.digest(package['binding']),qualified_package_sha256=t.digest(package))
        assert t.checkpoint_runtime(root,h,anchor=old['anchor'],checkpoint={'sha256':'5'*64})[0]==package
    assert s.canonical(old)==original and set(root)==t.ROOT_V3_KEYS
    assert t.decode_static(prepared.body,template_sha256=s.sha(prepared.plain),template_bytes=len(prepared.plain)).plain==prepared.plain


@pytest.mark.parametrize('damage',['extra','purpose','census','same_binding','old_hash','new_binding','no_checkpoint','anchor','no_root_hash'])
def test_v3_prior_namespace_cannot_be_supplied_by_unsealed_or_mixed_metadata(dual_document,damage):
    root=deepcopy(dual_document['root_template']);prior=root['prior_capture_qualified_runtime']
    h=dict(runtime_binding_sha256=t.digest(prior['qualified_runtime']['binding']),qualified_package_sha256=t.digest(prior['qualified_runtime']))
    anchor=deepcopy(prior['anchor']);checkpoint={'sha256':'6'*64}
    if damage=='extra':prior['url']='https://example.invalid/'
    elif damage=='purpose':prior['purpose']='APPEND'
    elif damage=='census':prior['pending_census']['owner_evidence_sha256']='0'*64
    elif damage=='same_binding':root['qualified_runtime']=deepcopy(prior['qualified_runtime'])
    elif damage=='old_hash':h['qualified_package_sha256']='0'*64
    elif damage=='new_binding':h['runtime_binding_sha256']=t.digest(root['qualified_runtime']['binding'])
    elif damage=='no_checkpoint':checkpoint=None
    elif damage=='anchor':anchor['receipt_sha256']='0'*64
    else:prior['root_static_sha256']=None
    with pytest.raises((t.TemplateError,c.ControllerError,s.StoreError)):
        t.checkpoint_runtime(root,h,anchor=anchor,checkpoint=checkpoint)


def test_v3_record_is_static_and_legacy_root_cannot_acquire_it(dual_document):
    value=deepcopy(dual_document);value['schema_version']=t.VERSION+'-static-v2'
    with pytest.raises(t.TemplateError):t.prepare(value)
    root=deepcopy(dual_document['root_template']);root['schema_version']='audit-weekly-hosted-v2-root-GO'
    with pytest.raises(t.TemplateError):t.capture_runtime(root)


class Service(Server):
    def __init__(self):
        super().__init__(); self.q=None; self.writer_done=None; self.reader_done=None; self.reader_started=None
        self.started=datetime.now(timezone.utc)-timedelta(seconds=1)
        self.redirect_payload=None; self.bad_digest=False

    def __call__(self,request,timeout):
        url=request.full_url; p=urlsplit(url)
        if p.hostname in s.probe.CDN_HOSTS and self.redirect_payload is not None:
            self.calls.append(request)
            assert request.get_header('Authorization') is None and request.get_header('Cookie') is None
            return Response(self.redirect_payload)
        if self.q is not None and url==s.API+'/actions/runs/'+QRUN:
            self.calls.append(request)
            return Response(dict(id=int(QRUN),head_sha=self.q['source_sha'],event='workflow_dispatch',run_attempt=1,
                status='completed',conclusion='success',path=c.WORKFLOW,repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO)))
        if self.q is not None and url==s.API+'/actions/runs/'+QRUN+'/jobs?per_page=100&page=1':
            self.calls.append(request)
            return Response(dict(total_count=3,jobs=[dict(id=p['job']['api_job_id'],name=p['job']['job_id'],
                run_id=int(QRUN),head_sha=p['source_sha'],status='completed',conclusion='success',
                started_at=p['started_at_utc'],completed_at=p['created_at_utc'])
                for p in (self.q['before_proof'],self.q['read_proof'],self.q)]))
        if url==s.API+'/actions/runs/'+RUN:
            self.calls.append(request)
            return Response(dict(id=int(RUN),head_sha=SOURCE,event='workflow_dispatch',run_attempt=1,
                status='completed' if self.reader_done else 'in_progress',conclusion='success' if self.reader_done else None,
                path=c.WORKFLOW,head_branch='research/current-producer',actor=dict(c.OWNER),
                repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO)))
        if url==s.API+'/actions/runs/'+RUN+'/jobs?per_page=100&page=1':
            self.calls.append(request)
            return Response(dict(total_count=2,jobs=[dict(id=n,name=name,run_id=int(RUN),head_sha=SOURCE,
                status='completed' if end else 'in_progress',conclusion='success' if end else None,
                started_at=(self.started if name==WRITER else self.reader_started or self.started).isoformat(),
                completed_at=end.isoformat() if end else None)
                for name,n,end in ((WRITER,777,self.writer_done),(READER,778,self.reader_done))]))
        if '/releases/assets/' in url and request.get_header('Accept')=='application/octet-stream':
            aid=int(p.path.rsplit('/',1)[-1]); asset=next(a for a in self.assets if a['id']==aid)
            if self.redirect_payload is not None and asset['name'].startswith('blob-'):
                self.calls.append(request)
                return Response(b'',302,{'Location':'https://objects.githubusercontent.com/fictional?signed=PRIVATE_NEVER_PRINT'})
        if self.bad_digest and '/releases/assets/' in url and request.get_header('Accept')!='application/octet-stream':
            self.calls.append(request)
            aid=int(p.path.rsplit('/',1)[-1]); value=self.metadata(next(a for a in self.assets if a['id']==aid))
            value['digest']='sha256:'+'0'*64; return Response(value)
        return super().__call__(request,timeout)


@pytest.fixture
def chain(controller_system,tmp_path):
    x=controller_system; server=Service()
    actual=datetime.now(timezone.utc)
    parent_at=(actual.astimezone(c.ZoneInfo('America/Chicago'))+timedelta(days=1)).replace(
        hour=8,minute=36,second=10,microsecond=0).astimezone(timezone.utc)
    # Keep the fictional API story portable across real CI dates. Readiness
    # predates native registration; the next fictional daily parent follows it.
    x.p['registered_at_utc']=(actual-timedelta(minutes=5)).isoformat()
    receipt=json.loads(x.original_receipt)
    receipt.update(policy_registered_at_utc=(actual-timedelta(minutes=120)).isoformat(),
        verified_at=(actual-timedelta(minutes=35)).isoformat(),created_at=(actual-timedelta(minutes=34)).isoformat())
    x.original_receipt=c.canonical(receipt);packed=gzip.compress(x.original_receipt,mtime=0)
    x.p['readiness'].update(receipt_sha256=c.sha(packed),receipt_body_sha256=c.sha(x.original_receipt))
    x.api.data[c.contents_url(c.receipt_path(x.p),'lab-state')]=cf.content(c.receipt_path(x.p),packed)
    for j,(start,end) in zip(x.api.data[c.jobs_url('200')]['jobs'],((60,50),(49,40),(39,30))):
        j.update(started_at=(actual-timedelta(minutes=start)).isoformat(),completed_at=(actual-timedelta(minutes=end)).isoformat())
    x.api.data[c.run_url('200')]['updated_at']=(actual-timedelta(minutes=29)).isoformat()
    x.reg=c.canonical(x.p);x.seal=c.sha(x.reg)
    journal=tmp_path/'native-journal'; journal.mkdir(mode=0o700)
    initial=s.Client('ghs_FICTIONAL',QRUN,journal=journal,source_sha='a'*40,transport=server,process='9'*64)
    binding=s.initialize(initial,'d'*32); q=qualification(binding); server.q=q
    package=dict(schema_version='audit-private-rotation-v1-qualified-runtime',binding=binding,qualification=q,
        runtime_reserved_bytes=32<<20,quota_reservation=dict(global_cap_bytes=512<<20,reserved_after_bytes=64<<20,new_runtime_id=binding['runtime_id']))
    storage=OperationalStorage(tmp_path/'cache',ROOT/'config/operational-source-policy-v2.json',state=tmp_path/'state')
    storage.register_root(tmp_path)
    def client(name,process,operation):
        job=dict(execution_lane='github_actions',workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/research/current-producer',
            workflow_sha=SOURCE,job_id=name,permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
        result=s.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,transport=server,process=process,job=job,operation=operation)
        result.bind(binding); return result
    prepared=t.prepare(document(x)); calls=[]
    def authority(request_sha):
        assert t.hashed(request_sha); calls.append(request_sha)
    handoff=t.append(prepared,client(WRITER,'4'*64,'append'),package,storage=storage,
        output=tmp_path/'append',root_go_sha256='e'*64,check_authority=authority)
    server.writer_done=datetime.now(timezone.utc)
    reader=client(READER,'5'*64,'restore'); server.reader_started=s.utc(reader.started_at)
    restored=t.restore(handoff,reader,package,storage=storage,output=tmp_path/'restore',
        root_go_sha256='e'*64,check_authority=authority)
    server.reader_done=datetime.now(timezone.utc)

    # Real typed verifier over fictional raw API, no private-key shortcut.
    x.api.data[c.run_url('100')].update(status='in_progress',conclusion=None)
    x.api.data[c.run_url('100')]['updated_at']=(parent_at-timedelta(seconds=5)).isoformat()
    x.api.data[c.jobs_url('100')]['jobs'][0].update(status='in_progress',conclusion=None,completed_at=None,
        started_at=(parent_at-timedelta(seconds=5)).isoformat())
    env=dict(x.env,GITHUB_RUN_ID='100',GITHUB_EVENT_NAME='schedule',GITHUB_SHA=cf.A,GITHUB_WORKFLOW_SHA=cf.A,
        GITHUB_WORKFLOW_REF=s.REPO+'/'+c.WORKFLOW+'@refs/heads/main',GITHUB_JOB='lab',
        GITHUB_ACTOR=c.OWNER['login'],GITHUB_ACTOR_ID=str(c.OWNER['id']))
    proof=c.verify_parent(x.reg,sealed_sha256=x.seal,env=env,
        event_bytes=c.canonical(dict(repository=dict(full_name=s.REPO),schedule=c.CADENCE['cron'])),
        source_root=x.parent_source,metadata_get=x.api,clock=lambda:parent_at,read_head=x.read_head)
    server.calls.clear()
    return SimpleNamespace(x=x,server=server,package=package,storage=storage,prepared=prepared,handoff=handoff,
        restored=restored,proof=proof,parent_at=parent_at,base=tmp_path,authority_calls=calls)


def parent_client(x,monkeypatch,*,auth=None):
    sealed=t.digest(x.restored['seal']); checks=[]
    def authenticate(value):
        assert value==sealed; checks.append(value)
        return auth() if auth is not None else x.proof
    journal=x.base/'parent-journal'; journal.mkdir(mode=0o700)
    monkeypatch.setattr(t,'now',lambda:x.parent_at)
    client=t.ParentGETClient('ghs_FICTIONAL',seal_sha256=sealed,registration_sha256=x.x.seal,
        parent_run_id='100',parent_job_id='lab',authenticate=authenticate,journal=journal,transport=x.server)
    return client,checks


def test_native_append_independent_restore_and_typed_schedule_get(chain,monkeypatch):
    x=chain; seal=x.restored['seal']; proof=x.restored['proof']
    assert proof['schema_version']=='weekly-private-proof-v2.1' and proof['exact_readback'] is proof['separate_process'] is True
    assert seal['writer']['process_identity']!=seal['reader']['process_identity']
    client,checks=parent_client(x,monkeypatch)
    result=t.recover_for_parent(seal,x.package,client,storage=x.storage,output=x.base/'current-parent')
    assert result['document']==x.prepared.document and result['created_at_utc']==x.parent_at.isoformat()
    assert all(result[k] is False for k in ('native_durability_qualified','execution_authority','forecast_authority','public_authority'))
    assert result['document']['root_template']['issued_at_utc'] is None
    assert len(checks)>=client.calls and client.calls<=40 and all(req.method=='GET' for req in x.server.calls)
    assert not any(key in seal for key in ('document','root_template','code_pins','path'))


@pytest.mark.parametrize('kind',['active','expired','credential_key','credential_value','forecast_body','encoded_secret','plain_cap'])
def test_static_metadata_rejects_execution_and_private_bodies(controller_system,kind):
    value=document(controller_system)
    if kind=='active': value['root_template']['approved']=True
    elif kind=='expired': value['root_template'].update(issued_at_utc='2000-01-01T00:00:00Z',expires_at_utc='2000-01-01T01:00:00Z')
    elif kind=='credential_key': value['root_template']['source_config']={'github_token':'PRIVATE_NEVER_PRINT'}
    elif kind=='credential_value': value['root_template']['source_config']={'description':'ghs_PRIVATE_NEVER_PRINT'}
    elif kind=='forecast_body': value['root_template']['source_config']={'forecast_value':1}
    elif kind=='encoded_secret': value['root_template']['publication_registration']={'policy_gzip_base64':base64.b64encode(gzip.compress(s.canonical({'password':'PRIVATE_NEVER_PRINT'}),mtime=0)).decode()}
    else: value['root_template']['source_config']={'metadata':'x'*(128<<10)}
    with pytest.raises(t.TemplateError): t.prepare(value)


def test_external_seal_and_live_typed_callback_are_required(chain,monkeypatch):
    client,checks=parent_client(chain,monkeypatch,auth=lambda:{'authenticated':True})
    with pytest.raises(t.TemplateError,match='LIVE_TYPED_PARENT_PROOF_REQUIRED'):
        t.recover_for_parent(chain.restored['seal'],chain.package,client,storage=chain.storage,output=chain.base/'flags')
    assert not chain.server.calls and checks
    client.seal_sha256='0'*64
    with pytest.raises(t.TemplateError,match='INDEPENDENTLY_TRUSTED_TEMPLATE_SEAL_REQUIRED'):
        t.recover_for_parent(chain.restored['seal'],chain.package,client,storage=chain.storage,output=chain.base/'self-digest')
    assert not chain.server.calls


def test_redirects_strip_authorization_and_authenticate_each_hop(chain,monkeypatch):
    blob=next(a for a in chain.server.assets if a['name'].startswith('blob-')); chain.server.redirect_payload=blob['body']
    client,checks=parent_client(chain,monkeypatch)
    t.recover_for_parent(chain.restored['seal'],chain.package,client,storage=chain.storage,output=chain.base/'redirect')
    redirects=[r for r in chain.server.calls if urlsplit(r.full_url).hostname in s.probe.CDN_HOSTS]
    assert redirects and len(checks)>=client.calls
    assert all(r.get_header('Authorization') is None and r.get_header('Cookie') is None for r in redirects)


@pytest.mark.parametrize('tamper',['server_digest','payload','manifest','same_reader'])
def test_original_entry_body_and_independence_tampering_blocks(chain,monkeypatch,tamper):
    seal=deepcopy(chain.restored['seal'])
    if tamper=='server_digest': chain.server.bad_digest=True
    elif tamper=='payload': next(a for a in chain.server.assets if a['name'].startswith('blob-'))['body']+=b'CORRUPT'
    elif tamper=='manifest': seal['descriptor']['manifest_sha256']='0'*64
    else: seal['reader']=deepcopy(seal['writer'])
    client,_=parent_client(chain,monkeypatch)
    with pytest.raises((t.TemplateError,s.StoreError)):
        t.recover_for_parent(seal,chain.package,client,storage=chain.storage,output=chain.base/'tampered')
    assert all(req.method=='GET' for req in chain.server.calls)


def test_prepare_cli_has_no_credentials_transport_or_execution_authority(controller_system,tmp_path,capsys):
    doc=document(controller_system); source=tmp_path/'static-input.json'; source.write_bytes(s.canonical(doc))
    target=tmp_path/'static-template.gz'
    assert cli.main(['prepare','--input',str(source),'--output',str(target)])==0
    status=json.loads(capsys.readouterr().out)
    assert status['native_durability_claimed'] is False and status['remote_calls']==0
    assert cli.main(['validate','--input',str(target),'--template-sha256',status['template_sha256'],
        '--template-bytes',str(status['template_bytes'])])==0
    assert 'PRIVATE_NEVER_PRINT' not in capsys.readouterr().out


def test_expired_live_parent_proof_stops_before_any_GET(chain,monkeypatch):
    client,_=parent_client(chain,monkeypatch)
    monkeypatch.setattr(t,'now',lambda:chain.parent_at+timedelta(seconds=181))
    with pytest.raises(t.TemplateError,match='FRESH_LIVE_PARENT_PROOF_REQUIRED'):
        t.recover_for_parent(chain.restored['seal'],chain.package,client,storage=chain.storage,output=chain.base/'stale')
    assert not chain.server.calls


def test_unknown_namespace_assets_count_before_template_body_GET(chain,monkeypatch):
    for n in range(4):chain.server.add('FICTIONAL_ORPHAN_'+str(n),b'fictional',size=s.ASSET_CAP)
    client,_=parent_client(chain,monkeypatch)
    with pytest.raises(s.StoreError,match='RUNTIME_BYTES_CAP'):
        t.recover_for_parent(chain.restored['seal'],chain.package,client,storage=chain.storage,output=chain.base/'full')
    assert not any(r.get_header('Accept')=='application/octet-stream' for r in chain.server.calls)


def test_parent_capability_rejects_mutations_and_other_namespace_even_if_allowlisted(chain,monkeypatch):
    client,_=parent_client(chain,monkeypatch)
    t.recover_for_parent(chain.restored['seal'],chain.package,client,storage=chain.storage,output=chain.base/'scoped')
    calls=len(chain.server.calls)
    current=s.API+'/releases/'+str(chain.package['binding']['release_id'])
    other=s.API+'/releases/999999999';client.allowed.add(other)
    for url,kwargs in ((current,dict(method='POST')), (current,dict(method='PATCH')), (current,dict(method='DELETE')), (other,{})):
        with pytest.raises(t.TemplateError):client.request(url,**kwargs)
    assert len(chain.server.calls)==calls


def test_bounded_inflation_and_unchanged_original_compressed_bytes(controller_system):
    prepared=t.prepare(document(controller_system))
    # Original packed bytes are hashed by native transport. A different zlib
    # compression level must not change the canonical plain metadata contract.
    packed=gzip.compress(prepared.plain,compresslevel=1,mtime=0)
    restored=t.decode_static(packed,template_sha256=s.sha(prepared.plain),template_bytes=len(prepared.plain))
    assert restored.body==packed and restored.plain==prepared.plain
    oversized=b'x'*(t.PLAIN_CAP+1)
    with pytest.raises(t.TemplateError):
        t.decode_static(gzip.compress(oversized,mtime=0),template_sha256=s.sha(oversized),template_bytes=len(oversized))


def test_retained_registration_transport_preserves_exact_original_bytes_and_metadata_guards(controller_system):
    import hashlib
    original=document(controller_system)
    reg=deepcopy(original['root_template']['retained_registration'])
    raw=json.dumps(reg,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    encoded=t.registration_envelope(reg)
    assert encoded['body_sha256']==hashlib.sha256(raw).hexdigest()
    assert encoded['body_bytes']==len(raw)
    assert gzip.decompress(base64.b64decode(encoded['gzip_base64'],validate=True))==raw
    assert t.retained_registration({'retained_registration':encoded})==reg
    assert t.retained_registration({'retained_registration':reg}) is reg
    changed=deepcopy(original);changed['root_template']['retained_registration']=encoded
    before=t.prepare(original);after=t.prepare(changed)
    assert hashlib.sha256(before.plain).hexdigest()!=hashlib.sha256(after.plain).hexdigest()  # New Root identity.
    assert t.retained_registration(json.loads(after.plain)['root_template'])==reg


@pytest.mark.parametrize('damage',['hash','size','base64','extra','inflation','private','duplicate'])
def test_retained_registration_transport_rejects_tampering_inflation_and_hidden_metadata(controller_system,damage):
    reg=deepcopy(document(controller_system)['root_template']['retained_registration'])
    encoded=t.registration_envelope(reg)
    if damage=='hash':encoded['body_sha256']='0'*64
    if damage=='size':encoded['body_bytes']+=1
    if damage=='base64':encoded['gzip_base64']='FICTIONAL!INVALID_BASE64'
    if damage=='extra':encoded['execution_authorized']=True
    if damage in {'inflation','private','duplicate'}:
        if damage=='inflation':raw=b'X'*(t.REGISTRATION_PLAIN_CAP+1)
        elif damage=='private':
            reg['api_key']='FICTIONAL_NEVER_PUBLIC';raw=s.canonical(reg)
        else:raw=b'{"schema_version":"audit-count-retained-v1-registration","schema_version":"duplicate"}'
        encoded.update(body_sha256=s.sha(raw),body_bytes=min(len(raw),t.REGISTRATION_PLAIN_CAP),
            gzip_base64=base64.b64encode(gzip.compress(raw,mtime=0)).decode())
    with pytest.raises(t.TemplateError):t.retained_registration({'retained_registration':encoded})
