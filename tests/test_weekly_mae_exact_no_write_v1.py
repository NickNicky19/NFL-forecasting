"""Exact public metadata; synthetic log/source/qualification HTTP boundaries.

The separate outside-checkout actual-data probe uses the retained complete log
and original Git blobs. This portable suite never includes a private job log or
Root, never calls a provider/network, and cannot mint native authority.
"""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from nfl_lab import weekly_mae_display_profile_v1 as p
from nfl_lab import audit_weekly_hosted_v1 as h,audit_weekly_template_v1 as t
from nfl_lab import audit_weekly_controller_v1 as c,private_draft_store as s
from nfl_lab.operational_storage import OperationalStorage
from test_audit_weekly_controller_v1 import no_network

DATA=json.loads((Path(__file__).parent/'fixtures/audit_weekly_no_write_41256899348.json').read_text())
BLOB='https://productionresultssa7.blob.core.windows.net/actions-results/fictional/job-logs.txt?sig=FICTIONAL'


class Response:
    def __init__(self,status,body=b'',headers=None):
        self.status=status;self.body=body;self.headers=headers or {}
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def read(self,n=-1):return self.body if n<0 else self.body[:n]


def fixture_runner(tmp_path,monkeypatch,*,actual=False):
    case=deepcopy(p._NO_WRITE_CASE)
    diagnostic=DATA['diagnostic']
    log=('2026-11-01T00:29:09.8401717Z '+json.dumps(diagnostic,sort_keys=True)+'\n'
        +'2026-11-01T00:29:13.6337877Z '+json.dumps(diagnostic,sort_keys=True)+'\n').encode()
    sources={name:('Fictional immutable source '+name).encode() for name in case['sources']}
    if not actual:
        case['canonical_log_sha256']=p.sha(p._nw_canonical_log(log))
        case['sources']={name:dict(bytes=len(body),sha256=p.sha(body)) for name,body in sources.items()}
        monkeypatch.setattr(p,'_NO_WRITE_CASE',case)  # explicit source/log fixture boundary
    run_url=s.API+'/actions/runs/'+case['run_id'];jobs_url=run_url+'/jobs?per_page=100&page=1'
    log_url=s.API+'/actions/jobs/'+str(case['job_api_id'])+'/logs'
    table={run_url:(200,c.canonical(DATA['run']),{}),jobs_url:(200,c.canonical(DATA['jobs']),{}),
        log_url:(302,b'',{'Location':BLOB}),BLOB:(200,log,{})}
    for name,body in sources.items():
        doc=dict(type='file',path=name,encoding='base64',size=len(body),sha=c.blob_sha(body),content=base64.b64encode(body).decode())
        table[s.API+'/contents/'+name+'?ref='+case['source_sha']]=(200,c.canonical(doc),{})
    calls=[];hooks={}
    def transport(req,timeout):
        assert req.get_method()=='GET' and req.data is None and 0<timeout<=20
        url=req.full_url;headers={k.lower():v for k,v in req.header_items()};calls.append((url,headers))
        assert url in table,'UNEXPECTED_ENDPOINT'
        if url.startswith('https://productionresultssa'):
            assert 'authorization' not in headers and 'cookie' not in headers
        else:assert headers['authorization']=='Bearer ghs_FICTIONAL'
        status,body,meta=table[url]
        if url in hooks:status,body,meta=hooks[url](status,body,meta)
        return Response(status,body,meta)
    journal=tmp_path/'journal';journal.mkdir(mode=0o700)
    job=dict(execution_lane='fictional_injected_transport',workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',
        workflow_sha='f'*40,job_id='audit-weekly-produce-v1',permission='write',event_name='workflow_dispatch',api_job_id=999,run_authenticated=True)
    class GetOnly(s.Client):
        def request(self,*args,method='GET',**kwargs):
            assert method=='GET' and kwargs.get('data') is None
            return super().request(*args,method=method,**kwargs)
    clients=[]
    def qualified_scope():
        # Native API/qualification boundary only. Real Client transfer, call,
        # URL, response and anonymous-log transport checks execute unchanged.
        client=GetOnly('ghs_FICTIONAL','99999999999',journal=journal,source_sha='f'*40,
            job=job,operation='metadata',transport=transport,clock=lambda:0,process='a'*64)
        client.calls=12;client.transferred=1000;clients.append(client);return client
    runner=h.Runner.__new__(h.Runner);runner.root=tmp_path/'owned';runner.journal=journal
    source=Path(h.__file__).resolve().parents[1]
    runner.storage=OperationalStorage(tmp_path/'cache',source/'config/operational-source-policy-v2.json',state=tmp_path/'state')
    runner.storage.register_root(runner.root)
    runner.go=dict(schema_version=t.ROOT_V5,source_sha='f'*40,issued_at_utc='2099-11-01T01:00:00Z',
        qualified_runtime=dict(binding=dict(origin_run_id=case['namespace_origin_run_id'])),
        effective_epoch=dict(schema_version=t.REGISTRATION_RECOVERY,pending_post_recovery=dict(
            schema_version=t.PENDING_RECOVERY,handoffs=[],pending_reservations=[])))
    runner.pending_metadata_client=qualified_scope;runner.pending_scope_authenticated=False
    row=deepcopy(DATA['run'])
    return SimpleNamespace(runner=runner,unknown=[row],table=table,calls=calls,hooks=hooks,clients=clients,
        log=log,sources=sources,run_url=run_url,jobs_url=jobs_url,log_url=log_url,scope=qualified_scope)


def test_exact_case_fresh_full_metadata_and_anonymous_log_is_only_admission(tmp_path,monkeypatch):
    x=fixture_runner(tmp_path,monkeypatch)
    assert p.no_write_failures(x.runner,x.unknown)==[]
    assert len(x.calls)==9 and x.clients[0].calls==21<=s.MAX_CALLS==40
    ref=x.runner.no_write_receipts[0];proof=h.read_owned(x.runner.storage,ref)
    assert proof['subject_run_id']=='41256899348' and proof['private_POSTs']==0
    assert proof['raw_log_sha256']==p.sha(x.log) and proof['canonical_log_sha256']==p.sha(p._nw_canonical_log(x.log))
    assert proof['proof_bytes']==x.clients[0].transferred-1000
    assert len(proof['metadata'][x.run_url])==len(proof['metadata'][x.jobs_url])==2
    assert not any('sig=' in key for key in proof['metadata'])


@pytest.mark.parametrize('damage',['actor','trigger','attempt','source','branch','event','run_pending','run_success',
    'job_missing','job_extra','step_added','preserve_success','other_job_success','source_bytes','source_blob_sha',
    'log_record_added','log_record_omitted','log_utf8','log_bare_cr','metadata_race','jobs_race','namespace','late_root'])
def test_changed_subject_source_complete_job_graph_logs_or_clock_never_admit(tmp_path,monkeypatch,damage):
    x=fixture_runner(tmp_path,monkeypatch)
    run=json.loads(x.table[x.run_url][1]);jobs=json.loads(x.table[x.jobs_url][1]);active=next(j for j in jobs['jobs'] if j['id']==124701874519)
    if damage=='actor':run['actor']=deepcopy(c.BOT)
    elif damage=='trigger':run['triggering_actor']=deepcopy(c.BOT)
    elif damage=='attempt':run['run_attempt']=2
    elif damage=='source':run['head_sha']='a'*40
    elif damage=='branch':run['head_branch']='main'
    elif damage=='event':run['event']='schedule'
    elif damage=='run_pending':run['status']='in_progress'
    elif damage=='run_success':run['conclusion']='success'
    elif damage=='job_missing':jobs['jobs'].pop();jobs['total_count']-=1
    elif damage=='job_extra':jobs['jobs'].append(deepcopy(active));jobs['total_count']+=1
    elif damage=='step_added':active['steps'].append(dict(number=99,name='Private POST',status='completed',conclusion='success'))
    elif damage=='preserve_success':next(s for s in active['steps'] if s['number']==8)['conclusion']='success'
    elif damage=='other_job_success':next(j for j in jobs['jobs'] if j['id']!=active['id'])['conclusion']='success'
    elif damage.startswith('source_'):
        url=next(u for u in x.table if '/contents/' in u);doc=json.loads(x.table[url][1])
        if damage=='source_bytes':doc['content']=base64.b64encode(b'altered').decode()
        else:doc['sha']='0'*40
        x.table[url]=(200,c.canonical(doc),{})
    elif damage=='log_record_added':x.table[BLOB]=(200,x.log+b'nonwhitespace extra record\n',{})
    elif damage=='log_record_omitted':x.table[BLOB]=(200,x.log.splitlines(keepends=True)[0],{})
    elif damage=='log_utf8':x.table[BLOB]=(200,b'\xff'+x.log,{})
    elif damage=='log_bare_cr':x.table[BLOB]=(200,x.log.replace(b'Z ',b'Z\r',1),{})
    elif damage=='metadata_race':
        count=[0]
        def race(status,body,headers):
            count[0]+=1
            if count[0]>1:
                v=json.loads(body);v['updated_at']='2099-01-01T00:00:00Z';body=c.canonical(v)
            return status,body,headers
        x.hooks[x.run_url]=race
    elif damage=='jobs_race':
        count=[0]
        def race(status,body,headers):
            count[0]+=1
            if count[0]>1:
                v=json.loads(body);v['jobs'][0]['name']='changed';body=c.canonical(v)
            return status,body,headers
        x.hooks[x.jobs_url]=race
    elif damage=='namespace':x.runner.go['qualified_runtime']['binding']['origin_run_id']='1'
    elif damage=='late_root':x.runner.go['issued_at_utc']='2026-11-01T00:28:00Z'
    x.table[x.run_url]=(200,c.canonical(run),{});x.table[x.jobs_url]=(200,c.canonical(jobs),{})
    with pytest.raises((s.StoreError,c.ControllerError)):p.no_write_failures(x.runner,x.unknown)
    assert not list((x.runner.root/'metadata').glob('NO_WRITE_*.json'))


@pytest.mark.parametrize('url',['http://productionresultssa7.blob.core.windows.net/actions-results/fixture/job-logs.txt?sig=x',
    'https://attacker.example/actions-results/job-logs.txt?sig=x',
    'https://user@productionresultssa7.blob.core.windows.net/actions-results/job-logs.txt?sig=x',
    'https://productionresultssa7.blob.core.windows.net:443/actions-results/job-logs.txt?sig=x',
    'https://productionresultssa7.blob.core.windows.net/actions-results/job-logs.txt?sig=x#secret',
    'https://productionresultssa7.blob.core.windows.net/other/job-logs.txt?sig=x',
    'https://productionresultssa7.blob.core.windows.net/actions-results/job-logs.txt'])
def test_signed_redirect_scope_fails_before_anonymous_request(tmp_path,monkeypatch,url):
    x=fixture_runner(tmp_path,monkeypatch);x.table[x.log_url]=(302,b'',{'Location':url})
    with pytest.raises(s.StoreError,match='NO_WRITE_LOG_REDIRECT_SCOPE'):p.no_write_failures(x.runner,x.unknown)
    assert not any(u==url for u,_ in x.calls)


@pytest.mark.parametrize('damage',['second_redirect','status','length','body','calls','transfer','eight_scopes'])
def test_all_existing_call_transfer_and_log_bounds_remain_closed(tmp_path,monkeypatch,damage):
    x=fixture_runner(tmp_path,monkeypatch)
    if damage=='second_redirect':x.table[BLOB]=(302,b'',{'Location':'https://attacker.example/'})
    elif damage=='status':x.table[BLOB]=(403,b'denied',{})
    elif damage=='length':x.table[BLOB]=(200,x.log,{'Content-Length':str((128<<10)+1)})
    elif damage=='body':x.table[BLOB]=(200,b'x'*((128<<10)+1),{})
    elif damage=='eight_scopes':
        def closed():raise s.StoreError('EIGHT_PENDING_FAILURE_METADATA_CLIENTS')
        x.runner.pending_metadata_client=closed
    else:
        original=x.scope
        def bounded():
            client=original()
            if damage=='calls':client.calls=39
            else:client.transferred=s.TRANSFER_CAP-1
            return client
        x.runner.pending_metadata_client=bounded
    with pytest.raises(s.StoreError):p.no_write_failures(x.runner,x.unknown)
    assert not list((x.runner.root/'metadata').glob('NO_WRITE_*.json'))


@pytest.mark.parametrize('variant',[b'\xef\xbb\xbf',b'CRLF',b'EXTRA_LF',b'BLANK_TAIL'])
def test_only_explicit_lossless_log_canonicalization_is_allowed(tmp_path,monkeypatch,variant):
    x=fixture_runner(tmp_path,monkeypatch)
    raw=(variant+x.log) if variant==b'\xef\xbb\xbf' else x.log.replace(b'\n',b'\r\n') if variant==b'CRLF' else x.log+b'\n\n' if variant==b'EXTRA_LF' else x.log+b' \t\n\n'
    x.table[BLOB]=(200,raw,{})
    assert p.no_write_failures(x.runner,x.unknown)==[]
    proof=h.read_owned(x.runner.storage,x.runner.no_write_receipts[0])
    assert proof['raw_log_sha256']==p.sha(raw) and proof['canonical_log_sha256']==p.sha(p._nw_canonical_log(x.log))


def test_local_success_receipt_cannot_replace_fresh_metadata_verification(tmp_path,monkeypatch):
    x=fixture_runner(tmp_path,monkeypatch);assert p.no_write_failures(x.runner,x.unknown)==[]
    old=x.runner.no_write_receipts[0];run=json.loads(x.table[x.run_url][1]);run['actor']=deepcopy(c.BOT)
    x.table[x.run_url]=(200,c.canonical(run),{});count=len(x.calls)
    with pytest.raises(s.StoreError):p.no_write_failures(x.runner,x.unknown)
    assert len(x.calls)>count and h.read_owned(x.runner.storage,old)['private_POSTs']==0


def test_direct_raw200_log_still_checks_complete_content_and_counts_bytes(tmp_path,monkeypatch):
    x=fixture_runner(tmp_path,monkeypatch);x.table[x.log_url]=(200,x.log,{})
    assert p.no_write_failures(x.runner,x.unknown)==[] and len(x.calls)==8
    assert x.clients[0].calls==20 and not any(u==BLOB for u,_ in x.calls)


def test_anonymous_log_hop_elapsed_time_remains_inside_same_scope(tmp_path,monkeypatch):
    x=fixture_runner(tmp_path,monkeypatch);original=x.scope;elapsed=[0]
    def scoped():
        client=original();client.clock=lambda:elapsed[0];return client
    x.runner.pending_metadata_client=scoped
    def delayed(status,body,headers):elapsed[0]=181;return status,body,headers
    x.hooks[BLOB]=delayed
    with pytest.raises(s.StoreError,match='NO_WRITE_LOG_RESPONSE_OR_TRANSFER_CAP'):
        p.no_write_failures(x.runner,x.unknown)
    assert not list((x.runner.root/'metadata').glob('NO_WRITE_*.json'))


def test_duplicate_metadata_key_is_not_a_json_pass(tmp_path,monkeypatch):
    x=fixture_runner(tmp_path,monkeypatch)
    x.table[x.run_url]=(200,b'{"id":41256899348,"id":41256899348}',{})
    with pytest.raises(s.StoreError,match='NO_WRITE_STRICT_METADATA_JSON'):
        p.no_write_failures(x.runner,x.unknown)


@pytest.mark.parametrize('old_or_other',['V4','other','mixed'])
def test_unknown_failures_and_all_old_root_versions_remain_unknown(tmp_path,monkeypatch,old_or_other):
    x=fixture_runner(tmp_path,monkeypatch);rows=deepcopy(x.unknown)
    if old_or_other=='V4':x.runner.go['schema_version']=t.ROOT_V4
    elif old_or_other=='other':rows[0]['id']+=1
    else:rows.append(dict(rows[0],id=rows[0]['id']+1))
    assert p.no_write_failures(x.runner,rows)==rows and not x.calls


@pytest.mark.parametrize('case',['exact','other','V4'])
def test_actual_pending_census_hook_keeps_unknown_rule_and_seed_order(tmp_path,monkeypatch,case):
    x=fixture_runner(tmp_path,monkeypatch);r=x.runner
    origin=int(r.go['qualified_runtime']['binding']['origin_run_id'])
    member=deepcopy(x.unknown[0])
    if case=='other':member['id']+=1
    if case=='V4':r.go['schema_version']=t.ROOT_V4
    members=[member,dict(id=origin,status='completed',conclusion='success')]
    class Census:
        def inventory(self):return [],{}
        def allow(self,url):return url
        def json(self,url):return dict(total_count=2,workflow_runs=deepcopy(members))
    r.client=Census()
    if case=='exact':
        r.authenticate_pending_posts();assert r.pending_scope_authenticated and r.no_write_receipts
    else:
        with pytest.raises(s.StoreError,match='UNRECOVERED_PRIOR_FAILED_DISPATCH_NO_WRITE'):r.authenticate_pending_posts()
        assert not r.pending_scope_authenticated
    assert not list(r.journal.glob('*.reservation.json'))


def test_profile_cold_import_has_no_model_hosted_or_network_side_effect():
    import subprocess,sys
    source=Path(p.__file__).resolve().parents[1]
    script='''import importlib.abc,sys,socket
sys.path.insert(0,sys.argv[1])
class Deny(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'numpy','pandas','pyarrow','joblib','scipy','sklearn'} or fullname=='nfl_lab.audit_weekly_hosted_v1':
   raise AssertionError('DEFERRED_DEPENDENCY_IMPORTED:'+fullname)
sys.meta_path.insert(0,Deny())
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError('NETWORK_ON_IMPORT'))
from nfl_lab import weekly_mae_display_profile_v1
assert weekly_mae_display_profile_v1._NO_WRITE_CASE['run_id']=='41256899348'
print('PURE_METADATA_IMPORT_OK')
'''
    result=subprocess.run([sys.executable,'-I','-B','-c',script,str(source)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='PURE_METADATA_IMPORT_OK'


def test_existing_hosted_source_cap_and_request_caps_are_not_raised():
    assert Path(h.__file__).stat().st_size<=128<<10
    assert (s.MAX_CALLS,s.TRANSFER_CAP,s.META_CAP)==(40,40<<20,256<<10)
