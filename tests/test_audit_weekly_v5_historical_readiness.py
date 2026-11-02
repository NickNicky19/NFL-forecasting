"""Offline actual historical API metadata plus explicit synthetic native boundaries.

No real actor is rewritten. The current Parent/child, source files and Seal are
fictional fixtures. Actual407299 run/jobs/workflow/receipt bytes are retained.
No network, private Root, model, native admission, dispatch or publication.
"""
import base64
from copy import deepcopy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from nfl_lab import audit_weekly_controller_v1 as c
from nfl_lab import audit_weekly_controller_registration_v1 as registration
from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
from nfl_lab import audit_weekly_grade_history_v1 as history
from test_audit_weekly_controller_v1 import system,no_network,API,content,A,B,D

DATA=json.loads((Path(__file__).parent/'fixtures/audit_weekly_v5_historical_readiness_40729906573.json').read_text())
AT=c.utc('2099-10-31T13:38:00Z')


def ready():
    a=DATA['authority'];doc=json.loads(gzip.decompress(base64.b64decode(DATA['receipt_gzip_base64'])))
    return dict(source_sha=a['source_sha'],branch=a['branch'],run_id=a['run_id'],workflow_sha256=a['workflow_sha256'],
        jobs=deepcopy(doc['jobs']),receipt_sha256=a['receipt_sha256'],receipt_body_sha256=a['receipt_body_sha256'],
        receipt_bindings={k:doc[k] for k in c.RECEIPT_HASH_KEYS})


def root_for(source=B):
    binding=history._source_history_unwrap(DATA['source_history_binding'])
    binding['target_source_sha']=source
    return dict(schema_version='audit-weekly-hosted-v5-root-GO',source_sha=source,
        source_history_binding=history.source_history_envelope(binding),issued_at_utc='2099-10-31T13:36:20Z')


def install_actual_old(api,p):
    r=p['readiness'];identifier=r['run_id']
    api.data[c.run_url(identifier)]=deepcopy(DATA['run'])
    api.data[c.jobs_url(identifier)]=deepcopy(DATA['jobs'])
    api.data[c.contents_url(c.WORKFLOW,r['source_sha'])]=content(c.WORKFLOW,base64.b64decode(DATA['workflow_base64']))
    path=c.receipt_path(p)
    api.data[c.contents_url(path,'lab-state')]=content(path,base64.b64decode(DATA['receipt_gzip_base64']))


def actual_readiness(v5):
    p=dict(readiness=ready(),registered_at_utc='2099-10-31T13:00:00Z')
    if v5:p=c.historical_v5_registration(root_for(),p)
    api=API();install_actual_old(api,p)
    allowed=set(api.data)
    return p,api,c.Metadata(api,allowed,clock=lambda:AT)


def test_actual_407299_bot_metadata_reproduces_old_owner_rejection_and_v5_passes_without_rewrite():
    p,raw,api=actual_readiness(False);frozen=deepcopy(raw.data)
    with pytest.raises(c.ControllerError,match='ACTUAL_GHA_RUN_SOURCE_EVENT_ACTOR_STATUS'):
        c.readiness(api,p,before=AT)
    assert len(api.calls)==1 and raw.data==frozen
    p,raw,api=actual_readiness(True);frozen=deepcopy(raw.data)
    run,result=c.readiness(api,p,before=AT)
    assert run==DATA['run'] and run['actor']==run['triggering_actor']==c.BOT
    assert result['receipt_sha256']==DATA['authority']['receipt_sha256'] and len(api.calls)==4
    assert raw.data==frozen


@pytest.mark.parametrize('damage',['actor_owner','actor_other','trigger_owner','trigger_missing','attempt','source','branch','event','failed','job_source','job_failed','receipt','workflow'])
def test_exact_v5_historical_api_run_receipt_and_original_three_job_controls_reject(damage):
    p,raw,api=actual_readiness(True);r=p['readiness'];run=raw.data[c.run_url(r['run_id'])]
    if damage=='actor_owner':run['actor']=deepcopy(c.OWNER)
    elif damage=='actor_other':run['actor']={'login':'other','id':7}
    elif damage=='trigger_owner':run['triggering_actor']=deepcopy(c.OWNER)
    elif damage=='trigger_missing':del run['triggering_actor']
    elif damage=='attempt':run['run_attempt']=2
    elif damage=='source':run['head_sha']='a'*40
    elif damage=='branch':run['head_branch']='main'
    elif damage=='event':run['event']='schedule'
    elif damage=='failed':run['conclusion']='failure'
    elif damage=='job_source':raw.data[c.jobs_url(r['run_id'])]['jobs'][0]['head_sha']='a'*40
    elif damage=='job_failed':next(j for j in raw.data[c.jobs_url(r['run_id'])]['jobs'] if j['id']==r['jobs']['consume']['api_job_id'])['conclusion']='failure'
    elif damage=='receipt':raw.data[c.contents_url(c.receipt_path(p),'lab-state')]=content(c.receipt_path(p),gzip.compress(b'{}',mtime=0))
    elif damage=='workflow':raw.data[c.contents_url(c.WORKFLOW,r['source_sha'])]=content(c.WORKFLOW,b'altered source')
    with pytest.raises(c.ControllerError):c.readiness(api,p,before=AT)


@pytest.mark.parametrize('field',['root_go_sha256','parent_run_id','parent_source_sha','parent_api_job_id','parent_context_sha256',
    'claim_id','claim_locator_sha256','controller_context_sha256','old_registration_sha256','native_control_asset_id',
    'parent_actor','root_static_sha256','source_history_binding_sha256','code_pins_sha256'])
def test_authority_is_exact_native_preimage_parent_and_claim_commitments_not_caller_flags(field):
    p,raw,api=actual_readiness(True)
    p['historical_readiness'][field]=0 if field not in p['historical_readiness'] or type(p['historical_readiness'][field]) is int else '0'*64
    with pytest.raises(c.ControllerError,match='CLOSED_V5_NATIVE_HISTORICAL_READINESS_AUTHORITY'):
        c.readiness(api,p,before=AT)
    assert not api.calls


@pytest.mark.parametrize('damage',['old_schema','other_root','other_source','other_run','other_receipt','caller_bool'])
def test_no_other_bot_or_old_root_schema_can_gain_this_closed_v5_route(damage):
    p,raw,api=actual_readiness(True)
    if damage=='old_schema':
        with pytest.raises(c.ControllerError,match='HISTORICAL_BOT_READINESS_REQUIRES_ROOT_V5'):
            c.historical_v5_registration(dict(root_for(),schema_version='audit-weekly-hosted-v4-root-GO'),p)
        return
    if damage=='caller_bool':p['historical_readiness']=True
    elif damage=='other_root':p['readiness']['receipt_bindings']['root_go_sha256']='0'*64
    elif damage=='other_source':p['readiness']['source_sha']='a'*40
    elif damage=='other_run':p['readiness']['run_id']='40729906574'
    else:p['readiness']['receipt_sha256']='0'*64
    with pytest.raises(c.ControllerError):c.readiness(api,p,before=AT)
    assert not api.calls


def shift(value):
    if isinstance(value,str):return value.replace('2026-10-25','2099-10-31')
    if isinstance(value,list):return [shift(v) for v in value]
    if isinstance(value,dict):return {k:shift(v) for k,v in value.items()}
    return value


@pytest.fixture
def v5(system):
    x=system;x.p=shift(x.p);x.go=shift(x.go);x.api.data=shift(x.api.data)
    x.p['readiness']=ready();x.go.update(root_for())
    x.p=c.historical_v5_registration(x.go,x.p);x.reg=c.canonical(x.p);x.seal=c.sha(x.reg)
    x.go['effective_epoch']['controller_context']['registration_sha256']=x.seal
    x.claim=shift(x.claim);x.claim['registration_sha256']=x.seal
    x.bind_root();x.claim['root_go_sha256']=c.sha(x.raw)
    x.api.data[c.contents_url(x.claim_path,D)]=content(x.claim_path,c.canonical(x.claim))
    x.api.data[c.API+'/commits/'+D]['files'][0]['sha']=c.blob_sha(c.canonical(x.claim))
    install_actual_old(x.api,x.p)
    return x


def test_current_child_and_genuine_current_parent_claim_still_run_within_original20_gets(v5):
    x=v5;proof=x.verify(clock=lambda:AT)
    assert proof.document['actor']==c.BOT and proof.document['parent_actor']==c.OWNER
    assert len(proof.document['metadata_GETs'])==20
    assert proof.document['readiness']['run_id']=='40729906573'


@pytest.mark.parametrize('damage',['current_owner','parent_bot','claim_root','claim_parent','claim_source','claim_history','head_race'])
def test_v5_current_child_and_parent_source_and_original_once_claim_controls_remain_strict(v5,damage):
    x=v5
    if damage=='current_owner':x.env.update(GITHUB_ACTOR=c.OWNER['login'],GITHUB_ACTOR_ID=str(c.OWNER['id']))
    elif damage=='parent_bot':x.api.data[c.run_url('100')]['actor']=deepcopy(c.BOT)
    elif damage=='claim_history':x.api.data[c.claim_history(x.claim_path)]=[]
    elif damage=='head_race':x.api.data[c.head_url(x.p)]['object']['sha']='f'*40
    else:
        key={'claim_root':'root_go_sha256','claim_parent':'parent_run_id','claim_source':'producer_source_sha'}[damage]
        x.claim[key]='0'*64
        raw=c.canonical(x.claim);x.api.data[c.contents_url(x.claim_path,D)]=content(x.claim_path,raw)
        x.api.data[c.API+'/commits/'+D]['files'][0]['sha']=c.blob_sha(raw)
    with pytest.raises(c.ControllerError):x.verify(clock=lambda:AT)


def parent_environment(x):
    env=dict(GITHUB_ACTIONS='true',CI='true',GITHUB_REPOSITORY=c.REPO,GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_ID='100',
        GITHUB_EVENT_NAME='schedule',GITHUB_SHA=A,GITHUB_WORKFLOW_SHA=A,
        GITHUB_WORKFLOW_REF=c.REPO+'/'+c.WORKFLOW+'@refs/heads/main',GITHUB_JOB='lab',GITHUB_ACTOR=c.OWNER['login'],GITHUB_ACTOR_ID=str(c.OWNER['id']))
    x.api.data[c.run_url('100')].update(status='in_progress',conclusion=None,updated_at='2099-10-31T13:36:05Z')
    x.api.data[c.jobs_url('100')]['jobs'][0].update(status='in_progress',conclusion=None,completed_at=None)
    event=c.canonical(dict(repository=dict(full_name=c.REPO),schedule=x.p['cadence']['cron']))
    return env,event


def test_v5_parent_uses_same_closed_historical_route_and_preserves_actual_owner(v5):
    x=v5;env,event=parent_environment(x)
    proof=c.verify_parent(x.reg,sealed_sha256=x.seal,env=env,event_bytes=event,source_root=x.parent_source,
        metadata_get=x.api,clock=lambda:c.utc('2099-10-31T13:36:30Z'),read_head=x.read_head)
    assert proof.document['scheduled_parent']['actor']==c.OWNER and proof.document['next_action']==c.RETURN_RULE
    assert proof.document['readiness']['run_id']=='40729906573'


def test_native_registrar_readiness_derives_the_v5_variant_before_original_owner_actor_check(v5):
    x=v5;p=x.p;receipt=base64.b64decode(DATA['receipt_gzip_base64'])
    api=SimpleNamespace(allowed=set(),receipt_path=c.receipt_path(p))
    api.get=lambda url,cap=1<<20:c.decode(x.api(url,cap).body)
    live=SimpleNamespace(api=api,go=dict(x.go,effective_epoch=dict(previous_capture=dict(
        receipt_sha256=c.sha(receipt),feed_sha256=p['readiness']['receipt_bindings']['feed_sha256']))),run_id='999999')
    result=registration._readiness(live)
    assert result==p['readiness']
    live.go['schema_version']='audit-weekly-hosted-v4-root-GO'
    with pytest.raises(c.ControllerError,match='ACTUAL_GHA_RUN_SOURCE_EVENT_ACTOR_STATUS'):
        registration._readiness(live)


def test_old_registration_version_stays_owner_only_and_rejects_v5_extra_json(system):
    x=system
    assert c.registration(x.reg,sealed_sha256=x.seal,at=AT)==x.p
    changed=dict(x.p,historical_readiness=deepcopy(c.V5_HISTORICAL_AUTHORITY));raw=c.canonical(changed)
    with pytest.raises(c.ControllerError,match='CLOSED_SEALED_CONTROLLER_REGISTRATION'):
        c.registration(raw,sealed_sha256=c.sha(raw),at=AT)
    x.api.data[c.run_url('200')]['actor']=deepcopy(c.BOT)
    with pytest.raises(c.ControllerError,match='ACTUAL_GHA_RUN_SOURCE_EVENT_ACTOR_STATUS'):x.verify()


class NativeSealBoundary:
    """Explicit mock of already tested native sealing/readback, not a grant."""
    def __init__(self,x):
        self.registration_bytes=x.reg;self.registration_sha256=x.seal
        self.document=dict(owner_registration_completed_at='2099-10-31T13:00:01Z',owner_registration_run_id='50',
            static_public_policy_sha256='1'*64)
        self.template_descriptor=dict(template_sha256=c.sha(b'fictional sealed static derivative'),
            template_bytes=len(b'fictional sealed static derivative'))
        self.metadata=self
        self.x=x
    def verify(self):return self
    def __call__(self,url,cap):return self.x.api(url,cap)
    def get(self,url,cap=1<<20):return c.decode(self.x.api(url,cap).body)
    def budget(self):pass


def bind_current_claim(x):
    x.bind_root();x.claim['root_go_sha256']=c.sha(x.raw)
    raw=c.canonical(x.claim);x.api.data[c.contents_url(x.claim_path,D)]=content(x.claim_path,raw)
    x.api.data[c.API+'/commits/'+D]['files'][0]['sha']=c.blob_sha(raw)


def test_bootstrap_parent_wrapper_reaches_same_v5_historical_verification(v5,monkeypatch):
    x=v5;env,event=parent_environment(x);seal=NativeSealBoundary(x)
    monkeypatch.setattr(bootstrap,'load_seal',lambda *_a,**_k:seal)  # native Seal boundary only
    parent=bootstrap.authorize_parent(env,x.parent_source,metadata_get=x.api,event_bytes=event,
        clock=lambda:c.utc('2099-10-31T13:36:30Z'),read_head=x.read_head,registry_version=2)
    assert parent.proof.document['readiness']['run_id']=='40729906573'
    assert parent.proof.document['scheduled_parent']['actor']==c.OWNER


def test_bootstrap_child_wrapper_reaches_v5_and_preserves_current20_get_chain(v5,monkeypatch):
    x=v5;x.go['operation']='RECURRING_CAPTURE'
    x.go['effective_epoch'].update(schema_version='audit-weekly-recurring-v1-context',
        previous_capture=dict(receipt_sha256=x.p['readiness']['receipt_sha256'],
            feed_sha256=x.p['readiness']['receipt_bindings']['feed_sha256']))
    bind_current_claim(x);seal=NativeSealBoundary(x)
    monkeypatch.setattr(bootstrap,'load_seal',lambda *_a,**_k:seal)
    proof=bootstrap.authorize_child(x.env,x.child_source,x.raw,metadata_get=x.api,event_bytes=x.event,
        clock=lambda:AT,read_head=x.read_head,registry_version=2)
    assert proof.document['actor']==c.BOT and len(proof.document['metadata_GETs'])==20
    assert proof.document['readiness']['run_id']=='40729906573'


@pytest.mark.parametrize('wrong_current_actor',[False,True])
def test_bootstrap_manual_owner_wrapper_uses_v5_history_but_still_requires_current_owner(v5,monkeypatch,wrong_current_actor):
    from test_audit_weekly_controller_v1 import run
    x=v5;x.go['operation']='RECURRING_CAPTURE';x.go['publication_registration']={'policy_sha256':'1'*64}
    binding=history._source_history_unwrap(x.go['source_history_binding'])
    x.go['effective_epoch'].update(schema_version='audit-weekly-recurring-v1-context',controller_context=None,
        previous_capture={k:binding['predecessor'][k] for k in ('feed_sha256','receipt_sha256')},
        previous_checkpoint=dict(schema_version=history.LOCATOR_REF,**binding['predecessor']['locator']))
    bind_current_claim(x);x.env.update(GITHUB_ACTOR=c.OWNER['login'],GITHUB_ACTOR_ID=str(c.OWNER['id']))
    x.api.data[c.run_url('300')]=run('300',B,x.p['producer']['branch'],c.BOT if wrong_current_actor else c.OWNER,
        status='in_progress',updated='2099-10-31T13:37:05Z')  # wholly fictional current run
    seal=NativeSealBoundary(x)
    monkeypatch.setattr(bootstrap,'load_seal',lambda *_a,**_k:seal)
    # Explicit full-Root/static-template boundary mocks. The actual controller
    # source/env/current actor/old run/jobs/workflow/receipt checks execute.
    monkeypatch.setattr(history,'validate_source_history_binding',lambda root:history._source_history_unwrap(root['source_history_binding']))
    from nfl_lab import audit_weekly_template_v1 as template
    seen=[]
    def static(doc):
        seen.append(doc);assert doc['schema_version']==template.STATIC_V5
        return SimpleNamespace(plain=b'fictional sealed static derivative')
    monkeypatch.setattr(template,'prepare',static)
    historical_before=deepcopy(x.api.data[c.run_url('40729906573')])
    kwargs=dict(metadata_get=x.api,event_bytes=x.event,clock=lambda:AT,read_head=x.read_head,registry_version=2)
    if wrong_current_actor:
        with pytest.raises(c.ControllerError,match='ACTUAL_GHA_RUN_SOURCE_EVENT_ACTOR_STATUS'):
            bootstrap.authorize_owner(x.env,x.child_source,x.raw,**kwargs)
    else:
        proof=bootstrap.authorize_owner(x.env,x.child_source,x.raw,**kwargs)
        assert proof.document['actor']==c.OWNER and proof.document['scheduled_parent'] is None
        assert proof.document['prior_capture']['run_id']=='40729906573' and len(seen)==1
    assert x.api.data[c.run_url('40729906573')]==historical_before


# Separate current-Owner protocol controls. The public receipt is exact; API,
# current Root/Seal/job boundaries below are synthetic, never native admission.
CURRENT_OWNER_PUBLIC_RECEIPT_GZIP_BASE64 = 'H4sIAAAAAAACA31V247bOAz9l7xup5BIXah8x74tFoZIURNvM3FgOzMdFP33pTPpZLZoNzACWqaOyMND6tuuznIYn3Xo41GXYTlUiGm337VeOjZWTiV6cC1S5wLcxVOhXhWUWkLHPrUesi8hNiQXJNYmkTnvPr0jj6emX+/IzKmWSLGJawnEMWYXXIIOTp1QaMBOpLncELk06r3XHAMlL029Q0OWuurjNI+67PZ/7erpdR2fdFibfTrXZRnquv4w5en8wxxP76t319fNmlXe/m+vl+Vww7ia//1g1t8WwmEaRe9Zhc7BUqGakjTvyWVS6YKxEANJ0RJBKEPKDJwoWy6QE3ifE2KgumU1q+XV7GTDAwfpwfsHB38C7O1B+FwCEMIfzu2dM389T3K4R6A5JnHYvTbfSFOLzZXYKEDpxKGUTI4iSnRcexSQBEBdpIQeUlQ1xK52PL+uG68eKUV/W3s/xNx7DRwxBaRAW9UDoDZHJSEYeDC/ngQYcnDBqkeS+qYM++lVFn1cDd592v0zsRnfdjKdlsuTbmY9j4MtD2OzACBGshgA0V+dr6u7emnj+vCi+uX4+qBfz9O8Pjz73Xer5zy1i/waxxSWIbjf4dy23oBmXdZp/jVQxkLB4e+AbluvQIZkGn0cT8PPYqlJuVXCDOoaRMg1CcVMCasWbIVc9GrdRaBGrw8VfS/I0Lo3VpPfxDsdR3k1aT6Oy6rzVTbDZZWfpOP3Ie4dfXalhBLfpXPb/R4Qhp5TyqkKQyyuIlEIiW0PWWHFQ3HOshfPFlD0pt/KGJg9eWcq4a03nNGhp3VcP+BW8NbK4GtDk2I1oWeJ6ihUa4oUTS4VY66++OCLSGi1iKIXb5LFlLZQ5/oyTPPwNDU9LsP5whb5bt/rcdGtUrXpPLyM60mXD9ML2Ueh2qBYfGJDhDumkqFWh6Sle2Hn0VkL5oqMiKkFHxJQaSVpD2/TYDzrjeC5ruN0uuP3yDls2RcMCkkMomafqeTeuNuUak17BA99s8g116qgy7F046vAhj8+HlYbVZf1YCr5SJoa5zF2ZBspoSS/ta0Xclh9Zkslml/H0syjiSUWQjQui71IKC6VDXya1uFx+oDJXF0ORgVaytqdTdUYitHnAiqbrCSxFZKrUUDNA0hELduZkoWuAU8v21gIuM3B05v2g4+IlrZFaB6LHPSpDs86L8bWz61h9bPbYH613nh4K6N1i+h43ubsMl3mtw7Z7p5q100LsdjVw41z1k4RmKSSDQQLnR2LXtVhgGMf/29oGncZ78p/meYv/Ti93KkBhYLFMZtIJEgtxW+kt1J9r3YPlaB2QVkXRBJnesKeILHddpWiqSnsvv8L/SuTdkUHAAA='


def current_owner_root():
    """New synthetic Root metadata over actual current/DAD source bytes."""
    import subprocess
    from nfl_lab import audit_weekly_hosted_v1 as hosted,weekly_mae_display_profile_v1 as profile
    from nfl_lab import private_draft_store as store
    source_root=Path(__file__).resolve().parents[1];a=c.V5_CURRENT_OWNER_AUTHORITY
    pins=hosted.pins();old={n:store.sha(subprocess.check_output(
        ['git','--no-lazy-fetch','show',a['source_sha']+':'+n],cwd=source_root)) for n in pins}
    assert store.sha(store.canonical(old))==a['code_pins_sha256']
    body=history._source_history_unwrap(DATA['source_history_binding'])
    body.update(target_source_sha=B,target_policy_sha256='0'*64,predecessor_root_schema=history.ROOT_V5,
        predecessor_source_history_sha256=a['source_history_binding_sha256'],
        pin_overrides={n:h for n,h in old.items() if h!=pins[n]})
    body['predecessor'].update({n:a[n] for n in ('source_sha','run_id','workflow_sha256','receipt_sha256',
        'root_go_sha256','root_static_sha256','code_pins_sha256')})
    body['predecessor'].update({n:a['receipt_bindings'][n] for n in ('feed_sha256','policy_sha256',
        'recipe_registration_sha256','epoch_sha256','choice_sha256')})
    body['predecessor']['locator']['path']='20261102T222307.000000Z--'+a['run_id']+'--'+'0'*64+'.json.gz'
    root={n:None for n in history._SOURCE_ROOT_V3_KEYS}
    helpers=profile.pins(source_root);raw=(source_root/profile.REGISTRATION_PATH).read_bytes()
    root.update(schema_version=history.ROOT_V5,source_sha=B,code_pins=pins,
        publication_registration=dict(policy_sha256='0'*64),source_history_binding=history.source_history_envelope(body),
        mae_helper_pins=helpers,mae_registration=dict(path=profile.REGISTRATION_PATH,bytes=len(raw),sha256=store.sha(raw)),
        operation='RECURRING_CAPTURE',effective_epoch=dict(schema_version=history.CONTEXT_V5,controller_context=None,
            previous_capture={n:a['receipt_bindings'][n] if n=='feed_sha256' else a[n] for n in ('feed_sha256','receipt_sha256')},
            previous_checkpoint=dict(schema_version=history.LOCATOR_REF,**body['predecessor']['locator'])))
    # These are source/history metadata checks, not complete hosted Root admission.
    history.validate_source_history_binding(root)
    return root


def current_owner_protocol():
    """Exact public receipt; synthetic current API wrappers, no real IO."""
    a=c.V5_CURRENT_OWNER_AUTHORITY;packed=base64.b64decode(CURRENT_OWNER_PUBLIC_RECEIPT_GZIP_BASE64)
    raw=gzip.decompress(packed);doc=c.decode(raw)
    assert c.sha(packed)==a['receipt_sha256'] and c.sha(raw)==a['receipt_body_sha256']
    r={n:deepcopy(a[n]) for n in ('source_sha','branch','run_id','workflow_sha256','jobs',
        'receipt_sha256','receipt_body_sha256','receipt_bindings')}
    root=current_owner_root();p=c.historical_v5_registration(root,dict(readiness=r,registered_at_utc='2099-10-31T13:00:00Z'))
    api=API();run=deepcopy(DATA['run']);run.update(id=int(a['run_id']),head_sha=a['source_sha'],
        head_branch=a['branch'],actor=deepcopy(c.OWNER),triggering_actor=deepcopy(c.OWNER))
    jobs=deepcopy(DATA['jobs']);refs=a['jobs']
    for role,ref in refs.items():
        old=DATA['authority']['jobs'][role]['api_job_id'];j=next(j for j in jobs['jobs'] if j['id']==old)
        j.update(id=ref['api_job_id'],run_id=int(a['run_id']),head_sha=a['source_sha'],name=ref['job_id'],
            started_at={'produce':'2026-11-02T22:02:53Z','restore':'2026-11-02T22:16:45Z','consume':'2026-11-02T22:19:15Z'}[role],
            completed_at={'produce':'2026-11-02T22:16:45Z','restore':'2026-11-02T22:19:14Z','consume':'2026-11-02T22:23:07Z'}[role])
    # The fictional workflow body is replaced with exact pinned public bytes.
    import subprocess
    workflow=subprocess.check_output(['git','--no-lazy-fetch','show',a['source_sha']+':'+c.WORKFLOW],cwd=Path(__file__).resolve().parents[1])
    assert c.sha(workflow)==a['workflow_sha256']
    api.data.update({c.run_url(a['run_id']):run,c.jobs_url(a['run_id']):jobs,
        c.contents_url(c.WORKFLOW,a['source_sha']):content(c.WORKFLOW,workflow),
        c.contents_url(c.receipt_path(p),'lab-state'):content(c.receipt_path(p),packed)})
    return root,p,doc,api


def test_current_owner_successor_uses_exact_dad_receipt_actor_and_four_fresh_API_reads():
    root,p,value,raw=current_owner_protocol();before=deepcopy(raw.data)
    api=c.Metadata(raw,set(raw.data),clock=lambda:AT)
    run,ready=c.readiness(api,p,before=AT)
    assert p['schema_version']==c.REGISTRATION_V5_OWNER and run['actor']==run['triggering_actor']==c.OWNER
    assert ready['run_id']=='41533789085' and len(api.calls)==4 and raw.data==before
    assert c.v5_history_authority(root)==c.V5_CURRENT_OWNER_AUTHORITY
    assert c.V5_HISTORICAL_AUTHORITY==DATA['authority']


@pytest.mark.parametrize('damage',['actor_bot','trigger_bot','trigger_missing','attempt','source','branch','event',
    'failed','job_source','job_failed','receipt','workflow','authority','unknown_schema','wrong_root','wrong_preimage'])
def test_current_owner_route_rejects_wrong_run_receipt_source_root_and_caller_authority(damage):
    root,p,value,raw=current_owner_protocol();a=c.V5_CURRENT_OWNER_AUTHORITY
    run=raw.data[c.run_url(a['run_id'])]
    if damage=='actor_bot':run['actor']=deepcopy(c.BOT)
    elif damage=='trigger_bot':run['triggering_actor']=deepcopy(c.BOT)
    elif damage=='trigger_missing':del run['triggering_actor']
    elif damage=='attempt':run['run_attempt']=2
    elif damage=='source':run['head_sha']='a'*40
    elif damage=='branch':run['head_branch']='main'
    elif damage=='event':run['event']='schedule'
    elif damage=='failed':run['conclusion']='failure'
    elif damage=='job_source':raw.data[c.jobs_url(a['run_id'])]['jobs'][0]['head_sha']='a'*40
    elif damage=='job_failed':next(j for j in raw.data[c.jobs_url(a['run_id'])]['jobs'] if j['id']==a['jobs']['consume']['api_job_id'])['conclusion']='failure'
    elif damage=='receipt':raw.data[c.contents_url(c.receipt_path(p),'lab-state')]=content(c.receipt_path(p),gzip.compress(b'{}',mtime=0))
    elif damage=='workflow':raw.data[c.contents_url(c.WORKFLOW,a['source_sha'])]=content(c.WORKFLOW,b'changed')
    elif damage=='authority':p['current_owner_readiness']['root_go_sha256']='0'*64
    elif damage=='unknown_schema':p['schema_version']='unrecognized-current-owner'
    else:
        binding=history._source_history_unwrap(root['source_history_binding'])
        if damage=='wrong_root':binding['predecessor']['root_go_sha256']='0'*64
        else:binding['predecessor_source_history_sha256']='0'*64
        root['source_history_binding']=history.source_history_envelope(binding)
        with pytest.raises(c.ControllerError):c.v5_history_authority(root)
        return
    api=c.Metadata(raw,set(raw.data),clock=lambda:AT)
    if damage=='unknown_schema':
        with pytest.raises(c.ControllerError):c._current_owner_v5(p)
    else:
        with pytest.raises(c.ControllerError):c.readiness(api,p,before=AT)
