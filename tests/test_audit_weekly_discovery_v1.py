"""Fictional API/qualified namespace and old native archive, never real HTTP.

Native descriptors/proofs come from the existing injected archive fixture.
Discovery requests are isolated from fixture setup POSTs and never fetch an
archive group, forecast, model, raw-provider body or outcome.
"""
from copy import copy, deepcopy
from datetime import datetime, timedelta, timezone
import gzip
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_discovery_v1 as d, audit_weekly_archive_v1 as a
from nfl_lab import audit_weekly_retained_v1 as retained, private_draft_store as s, gha_private_checkpoint as cp
from tools import audit_weekly_discovery_v1 as cli
from test_audit_weekly_archive_v1 import capture, produce, ROOT, ROLES
from test_audit_weekly_retained_v1 import History, full_r0, CURRENT_RUN, CURRENT_SOURCE, CURRENT_JOB, WORKFLOW
from test_private_draft_store_v2 import Response, RUN, SOURCE


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    p=capture.__wrapped__(tmp_path_factory.mktemp('fictional-discovery-original'))
    history=History(p);r0,r0_completion=full_r0(p)
    snapshot=a.collect(p.root,p.context,storage=p.storage,output=p.base/'collection',r0=r0)
    # The older assembly collector predates the parent's strict completion
    # closure. Preserve the fixture's real original completion bytes; never
    # fabricate a missing receipt or weaken the discovery census.
    if 'r0/control_completion.json' not in {f['logical_path'] for f in snapshot['files']}:
        item=cp.file_item(r0_completion,'r0/control_completion.json','control')
        snapshot['files'].append(item);snapshot['census']['physical_origins'][item['logical_path']]=r0_completion
    policy=p.put('context/discovery-public-policy.json',dict(fictional_prevalue_policy=True))
    name='context/public_policy.json';snapshot['files'].append(cp.file_item(policy,name,'control'))
    snapshot['files'].sort(key=lambda f:f['logical_path']);snapshot['census']['physical_origins'][name]=policy
    snapshot['census']['logical_files']=len(snapshot['files']);snapshot['census']['logical_bytes']=sum(f['bytes'] for f in snapshot['files'])
    snapshot['census']['context_roles'].append('public_policy');snapshot['census']['context_roles'].sort()
    history.begin('produce');handoff,_,_=produce(p,history.old,snapshot=snapshot);history.end()
    history.begin('restore')
    a.restore(handoff,history.old.factory(p.base/'old-reader-journal','restore'),history.old.package,
        storage=p.storage,output=p.base/'old-reader',root_go_sha256='d'*64,pending_census=history.old.census)
    history.end();reader=cp.strict_json((p.base/'old-reader/READER_HANDOFF.json').read_bytes())
    history.begin('consume');verified=datetime.now(timezone.utc)
    # Only fictional source controls/forecasts exist in this setup fixture.
    a.consume(reader,history.old.factory(p.base/'old-export-journal','consume'),history.old.package,
        storage=p.storage,output=p.base/'old-export',root_go_sha256='d'*64,pending_census=history.old.census)
    created=datetime.now(timezone.utc);history.end();history.finished=True
    files={f['logical_path']:f for f in snapshot['files']}
    receipt=dict(schema_version=d.delivery.VERSION+'-public-receipt',source_sha=SOURCE,run_id=RUN,root_go_sha256='d'*64,
        policy_sha256=policy['sha256'],policy_registered_at_utc=(p.stamp-timedelta(seconds=120)).isoformat(),
        workflow_sha256=s.sha(history.codes['.github/workflows/lab.yml']),recipe_registration_sha256='1'*64,
        rights_authority_sha256='2'*64,r0_identity_sha256='3'*64,origin_choice_sha256='4'*64,
        feed_sha256='5'*64,feed_bytes=100,rows=1,categories=['pass_att'],
        jobs={role:dict(job_id=job,api_job_id=777+i) for i,(role,job) in enumerate(ROLES.items())},
        created_at=created.isoformat(),verified_at=verified.isoformat(),fits=0,raw_or_models_public=False,
        archive_index_sha256=handoff['index_descriptor']['entry']['payload']['sha256'],archive_files_sha256=handoff['files_sha256'],
        reader_witness_sha256=reader['witness_descriptor']['entry']['payload']['sha256'],
        epoch_sha256=files['context/epoch.json']['sha256'],choice_sha256=files['prepared/choice.json']['sha256'])
    assert len(receipt)==25
    return SimpleNamespace(p=p,history=history,reader=reader,receipt=receipt)


def case(original,tmp_path,*,stress=False):
    p=original.p;history=copy(original.history);history.calls=[];history.codes=dict(original.history.codes);history.jobs_bad={}
    history.old=copy(original.history.old);history.old.server=copy(original.history.old.server)
    server=history.old.server;server.calls=[];server.assets=deepcopy(original.history.old.server.assets)
    if stress:
        # Exact 128 assets, including unrelated valid native manifests and
        # private payloads that discovery must never GET or decode.
        while len(server.assets)+2 <= 128:
            body=b'FICTIONAL_PRIVATE_BODY_NEVER_FETCH:'+str(len(server.assets)).encode()
            asset=server.add('blob-'+s.sha(body)+'.bin',body)
            entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=cp.payload(body),payload_asset_id=asset['id'],
                payload_name=asset['name'],producer_process='7'*64,binding_sha256=s.sha(s.canonical(history.old.binding)),writer_run_id='40000000123')
            raw=s.canonical(entry);server.add('manifest-'+s.sha(raw)+'.json',raw)
        if len(server.assets)<128:server.add('unrelated-private-weight.joblib',b'FICTIONAL_MODEL_NEVER_DECODE')
        assert len(server.assets)==128
    value=deepcopy(original.receipt);clients=[];auth=[]
    root=tmp_path/'current';p.storage.register_root(root);journal=p.storage.register_root(root/'journal')
    def transport(request,timeout):
        if request.full_url.startswith('https://objects.githubusercontent.com/fictional-discovery/'):
            history.calls.append(request)
            assert request.get_header('Authorization') is None
            aid=int(request.full_url.rsplit('/',1)[-1]);return Response(next(a['body'] for a in server.assets if a['id']==aid))
        if stress and '/releases/assets/' in request.full_url and request.get_header('Accept')=='application/octet-stream':
            aid=int(request.full_url.rsplit('/',1)[-1]);asset=next(a for a in server.assets if a['id']==aid)
            if asset['name'].startswith('manifest-'):
                history.calls.append(request)
                return Response(status=302,headers={'Location':'https://objects.githubusercontent.com/fictional-discovery/'+str(aid)})
        return history.transport(request,timeout)
    def factory(operation):
        assert operation=='restore'
        job=dict(execution_lane='github_actions',workflow_ref=WORKFLOW,workflow_sha=CURRENT_SOURCE,job_id=CURRENT_JOB,
            permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
        client=retained.ReadClient('ghs_FICTIONAL',CURRENT_RUN,journal=journal,source_sha=CURRENT_SOURCE,job=job,
            process='8'*64,operation='restore',transport=transport,extra_routes=d.routes(value,history.old.package))
        client.bind(history.old.binding);clients.append(client);return client
    def authenticate(client,scope):
        auth.append(scope)
        return (client.job['run_authenticated'] is True and scope['current']['run_id']==CURRENT_RUN
            and scope['current_root_go_sha256']=='f'*64 and scope['qualified_runtime_sha256']==s.sha(s.canonical(history.old.package)))
    return SimpleNamespace(p=p,history=history,server=server,value=value,clients=clients,auth=auth,factory=factory,
        authenticate=authenticate,output=root/'discovered',journal=journal,pending=[],
        pins={name:s.sha(body) for name,body in history.codes.items()})


def execute(c):
    body=s.canonical(c.value)
    return d.discover(body,s.sha(body),c.history.old.package,c.factory,storage=c.p.storage,output=c.output,
        historical_source_sha256=c.pins,pending_census=c.history.old.census,pending_reservations=c.pending,
        current_root_go_sha256='f'*64,authenticate=c.authenticate)


def payload_gets(c):
    result=set()
    for request in c.history.calls:
        if '/releases/assets/' in request.full_url and request.get_header('Accept')=='application/octet-stream':
            result.add(int(request.full_url.rsplit('/',1)[-1]))
    return result


def test_exact_original_handoff_from_128_asset_namespace_only_metadata_GETs(original,tmp_path):
    c=case(original,tmp_path,stress=True);result=execute(c);result.verify();doc=result.document
    assert doc['state']=='DERIVED_FROM_ORIGINAL_METADATA'
    assert doc['reader_handoff']==original.reader
    assert doc['original_receipt']==original.receipt
    assert 1<len(c.clients)<=6 and all(client.calls<=40 for client in c.clients)
    assert doc['HTTP_calls']==len(c.history.calls)<=200
    assert doc['inventory_assets']==128 and len(doc['metadata_get_proofs'])==2
    assert doc['capture_body_restored'] is doc['capture_durability_established'] is doc['public_authority'] is False
    assert all(r.method=='GET' and r.data is None for r in c.history.calls)
    allowed={a['id'] for a in c.server.assets if a['name'].startswith('manifest-')} | {
        original.reader['archive']['index_descriptor']['entry']['payload_asset_id'],
        original.reader['witness_descriptor']['entry']['payload_asset_id'],c.history.old.binding['canary_asset_id']}
    assert payload_gets(c)<=allowed
    assert cp.read_ref(result.binding)==s.canonical(doc)
    c.p.storage.validate_reference(result.binding['path'],result.binding['sha256'])
    p=retained.prepare_request(ROOT,doc['reader_handoff'],c.history.old.package,exporter_api_job_id=doc['exporter_api_job_id'],
        historical_source_sha256=doc['historical_source_sha256'],cache=c.p.base/'cache',state_root=c.p.base/'state',
        output=tmp_path/'later-restore',pending_census=c.history.old.census)
    assert p['approved'] is False and p['reader_handoff']==original.reader
    assert doc['metadata_get_proofs'][0]['run_id']==CURRENT_RUN and doc['reader_handoff']['restorer']['run_id']==RUN


def test_ambiguous_unavailable_pending_and_failure_capture_never_choose_latest(original,tmp_path):
    for failure in ('duplicate','unavailable','pending','failure_archive'):
        c=case(original,tmp_path/failure);descriptor=deepcopy(original.reader['archive']['index_descriptor'])
        if failure=='duplicate':
            entry=deepcopy(descriptor['entry']);entry['producer_process']='9'*64
            raw=s.canonical(entry);c.server.add('manifest-'+s.sha(raw)+'.json',raw)
            expected='UNIQUE_INDEX_AND_WITNESS'
        elif failure=='unavailable':
            c.value['archive_index_sha256']='0'*64;expected='UNIQUE_INDEX_AND_WITNESS'
        elif failure=='pending':
            c.pending=[dict(schema_version='weekly-private-POST-reservation-v2',key='asset:blob-'+'0'*64+'.bin',
                bytes=123,sha256='0'*64,name='blob-'+'0'*64+'.bin')]
            expected='UNRESOLVED_PENDING'
        else:
            asset=next(a for a in c.server.assets if a['id']==descriptor['entry']['payload_asset_id'])
            index=a.unpack(asset['body'],a.INDEX_PLAIN_CAP);index['archive_state']='FAILURE_EVIDENCE';index['census']['archive_state']='FAILURE_EVIDENCE'
            body=gzip.compress(s.canonical(index),mtime=0);asset.update(body=body,name='blob-'+s.sha(body)+'.bin',size=len(body),digest='sha256:'+s.sha(body))
            entry=descriptor['entry'];entry.update(payload=cp.payload(body),payload_name=asset['name'])
            raw=s.canonical(entry);manifest=next(a for a in c.server.assets if a['id']==descriptor['manifest_asset_id'])
            manifest.update(body=raw,name='manifest-'+s.sha(raw)+'.json',size=len(raw),digest='sha256:'+s.sha(raw))
            c.value['archive_index_sha256']=s.sha(body);expected='EXACT_ORIGINAL_ARCHIVE_INDEX'
        with pytest.raises(s.StoreError,match=expected):execute(c)
        assert all(r.method=='GET' for r in c.history.calls)
        assert not (c.output/'DISCOVERED.json').exists()


def test_real_API_and_code_checks_not_saved_flags_or_corrupt_server_bytes(original,tmp_path):
    for failure in ('server_bytes','old_failed_exporter','old_source','current_source','saved_authority'):
        c=case(original,tmp_path/failure)
        if failure=='server_bytes':
            asset=next(a for a in c.server.assets if a['name'].startswith('manifest-'));asset['body']+=b'CORRUPT'
            expected='EXACT_SERVER_METADATA'
        elif failure=='old_failed_exporter':c.history.jobs_bad['consume']=dict(conclusion='failure');expected='COMPLETED_SUCCESSFUL_ORIGINAL'
        elif failure=='old_source':c.history.contents_bad='nfl_lab/audit_weekly_archive_v1.py';expected='EXACT_ORIGINAL_DISCOVERY_SOURCE'
        elif failure=='current_source':c.history.current_bad=True;expected='ACTIONS_API_IDENTITY'
        else:c.authenticate=dict(actual_actions_api_authenticated=True);expected='LIVE_PARENT_CLIENT_FACTORY'
        with pytest.raises(s.StoreError,match=expected):execute(c)
        assert not (c.output/'DISCOVERED.json').exists()
        if failure=='saved_authority':assert c.history.calls==[]


def test_closed_new_receipt_and_entry_size_bound_without_payload_decode(original,tmp_path,capsys):
    c=case(original,tmp_path/'old-receipt');del c.value['reader_witness_sha256']
    with pytest.raises(s.StoreError,match='NEW_CLOSED_CANONICAL'):execute(c)
    assert c.history.calls==[]
    c=case(original,tmp_path/'oversized-entry')
    entry=next(a for a in c.server.assets if a['name'].startswith('manifest-'));entry['size']=cp.ENTRY_CAP+1
    with pytest.raises(s.StoreError,match='BOUNDED_SERVER_ASSET_DIGEST'):execute(c)
    assert entry['id'] not in payload_gets(c)
    assert cli.main(['discover','--execute'])==2
    assert 'LIVE_PARENT_FACTORY' in capsys.readouterr().out
