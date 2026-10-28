"""Prepare one new owner registration continuing the retained capture 28.

GET and local metadata only. No dispatch, private payload download, fit or
forecast/outcome body is read. --help does not import repository modules.
"""
import argparse
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE=Path('/workspace/nfl-system-audit/continuation')
PRIVATE=BASE/'private'
GH='/workspace/nfl-system-audit/bin/gh'
REPO='NickNicky19/NFL-forecasting'
OLD_SOURCE='5278c1a46987e1676a39c9aff500d820d417a733'
OLD_ROOT='1c09b8e5c14aae5d50e3763b95c61f1ea24b57836eac9ef39eecf430d6359f2d'
OLD_FEED='a71202ff804378d9b2343fc502e06ed82d829e53d7dfc57d9459d620abbfc01a'
OLD_RECEIPT='127f8eb72c73fbe9c89dfd3ac5e6e345acb0c449aa78fe4625a9e2a6f74c62b4'
OLD_LOCATOR='638f388a85e83d143c5ee74bb2a88e24d8f66423dca4c6ece6b24ae7a43c6603'
def require(value,code):
    if not value:raise ValueError(code)
def cmd(*args):return subprocess.check_output(args)
def api(path):return json.loads(cmd(GH,'api','--method','GET','repos/'+REPO+'/'+path))
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=int,required=True)
    parser.add_argument('--parent-source',required=True)
    parser.add_argument('--producer-source',required=True)
    parser.add_argument('--parent-ci-run',type=int,required=True)
    parser.add_argument('--producer-ci-run',type=int,required=True)
    parser.add_argument('--qualified-runtime',type=Path)
    parser.add_argument('--pending-census',type=Path)
    args=parser.parse_args()
    require(args.attempt>28,'NEW_REGISTRATION_ONLY_NOT_OLD_ISSUE_RETRY')
    require((args.qualified_runtime is None)==(args.pending_census is None),'EXACT_QUALIFIED_RUNTIME_AND_ORIGINAL_CENSUS_PAIR')
    require(all(re.fullmatch('[a-f0-9]{40}',x) for x in (args.parent_source,args.producer_source)), 'LITERAL_CURRENT_SOURCES')
    source=Path.cwd().resolve();sys.path.insert(0,str(source))
    from nfl_lab import audit_weekly_hosted_v1 as hosted,audit_weekly_controller_registration_v1 as registration
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap,audit_weekly_template_v1 as template
    from nfl_lab import audit_weekly_grade_history_v1 as history,audit_weekly_public_v1 as public,private_draft_store as store
    require(cmd('git','rev-parse','HEAD').decode().strip()==args.producer_source and not cmd('git','status','--porcelain'),'CLEAN_CURRENT_PRODUCER_CHECKOUT')
    owner=json.loads(cmd(GH,'api','user'));require((owner['login'],owner['id'])==('NickNicky19',208912933),'EXISTING_OWNER_ONLY')
    for branch,sha in (('main',args.parent_source),('research/weekly-storage-probe-v1',args.producer_source)):
        require(api('branches/'+branch)['commit']['sha']==sha,'CURRENT_SOURCE_HEAD_CHANGED')
    for run_id,sha in ((args.parent_ci_run,args.parent_source),(args.producer_ci_run,args.producer_source)):
        run=api('actions/runs/'+str(run_id))
        require((run['status'],run['conclusion'],run['path'])==('completed','success','.github/workflows/audit-source-checks.yml'),'COMPLETED_CURRENT_SOURCE_CI_REQUIRED')
        require(api('git/commits/'+run['head_sha'])['tree']['sha']==api('git/commits/'+sha)['tree']['sha'],'EXACT_TESTED_SOURCE_TREE_REQUIRED')
    raw=(PRIVATE/'weekly-go-28.json').read_bytes();old=json.loads(raw)
    require(store.sha(raw)==OLD_ROOT and raw==store.canonical(old) and old['source_sha']==OLD_SOURCE,'UNALTERED_ORIGINAL_CAPTURE28_ROOT')
    packed=(PRIVATE/'consumer27-actual28-fresh-board/public-network-4.bin').read_bytes()
    require(store.sha(packed)==OLD_RECEIPT,'ORIGINAL_CAPTURE28_PUBLIC_RECEIPT_BYTES')
    receipt=json.loads(gzip.decompress(packed));require(receipt['feed_sha256']==OLD_FEED and receipt['root_go_sha256']==OLD_ROOT,'ORIGINAL_CAPTURE28_RECEIPT_BINDINGS')
    prior_run=api('actions/runs/40611698210');require(prior_run['head_sha']==OLD_SOURCE and prior_run['status']=='completed' and prior_run['conclusion']=='success','ACTUAL_COMPLETED_PREDECESSOR')
    jobs=api('actions/runs/40611698210/jobs?per_page=100')['jobs']
    for ref in receipt['jobs'].values():
        matched=[j for j in jobs if j['id']==ref['api_job_id']]
        require(len(matched)==1 and matched[0]['name']==ref['job_id'] and matched[0]['conclusion']=='success' and matched[0]['head_sha']==OLD_SOURCE,'THREE_ORIGINAL_SUCCESSFUL_PREDECESSOR_JOBS')
    state_head=api('branches/lab-state')['commit']['sha']
    entries=api('contents/'+history.LOCATOR_ROOT+'?ref='+state_head);name=history.latest_locator(entries)
    content=api('contents/'+history.LOCATOR_ROOT+'/'+name+'?ref='+state_head)
    locator_raw=base64.b64decode(content['content'],validate=False)
    require(store.sha(locator_raw)==OLD_LOCATOR,'NEWER_OR_CHANGED_HISTORY_REQUIRES_RECONCILIATION')
    locator=history.metadata_document(locator_raw)
    require(locator['cohort']['run_id']=='40611698210' and locator['anchor']==dict(feed_sha256=OLD_FEED,receipt_sha256=OLD_RECEIPT),'CAPTURE28_REMAINS_THE_OPERATIONAL_PREDECESSOR')
    for path,sha in old['code_pins'].items():
        require(store.sha(cmd('git','show',OLD_SOURCE+':'+path))==sha,'ORIGINAL_PREDECESSOR_COMMIT_BLOB_CHANGED')
    parent_pins={path:store.sha(cmd('git','show',args.parent_source+':'+path)) for path in sorted(bootstrap.PARENT_EXECUTABLE_PINS)}
    pins=hosted.pins();require(set(pins)==set(old['code_pins']) and len(pins)<=128,'EXACT_ORIGINAL_PIN_INVENTORY_NO_REMOVALS')
    require(all(parent_pins[path]==pins[path] for path in bootstrap.SHARED_EXECUTABLE_PINS),'IDENTICAL_SHARED_RUNTIME_BYTES')
    issued=datetime.now(timezone.utc)
    previous_policy_raw=gzip.decompress(base64.b64decode(old['publication_registration']['policy_gzip_base64'],validate=True))
    require(store.sha(previous_policy_raw)==old['publication_registration']['policy_sha256'],'ORIGINAL_SOURCE_POLICY_BYTES')
    previous_policy=json.loads(previous_policy_raw)
    require(previous_policy_raw==store.canonical(previous_policy),'CANONICAL_ORIGINAL_SOURCE_POLICY')
    policy=public.policy_template()
    policy.update(state='ROOT_REGISTERED',source_sha=args.producer_source,source_branch='research/weekly-storage-probe-v1',
        workflow_sha256=pins['.github/workflows/lab.yml'],registered_at_utc=issued.isoformat(),jobs=deepcopy(hosted.JOBS),
        **{k:deepcopy(previous_policy[k]) for k in ('origin_choice_sha256','public_roles','rights_authorities','r0_identities','engine_sha256','website_code_sha256','approved_candidates')})
    policy['producer_policy_sha256']=public.recipe_commitment(policy)
    policy['publication_authority'].update(state='ROOT_REGISTERED',source_sha=args.producer_source,source_branch=policy['source_branch'],
        export_job=hosted.JOBS['consume'],recipe_registration_sha256=policy['producer_policy_sha256'])
    policy_raw=store.canonical(policy)
    binding=dict(schema_version='audit-weekly-source-history-binding-v1',target_source_sha=args.producer_source,target_policy_sha256=store.sha(policy_raw),
        runtime_transition='PRESERVE' if args.qualified_runtime is None else 'DUAL_RUNTIME_ROTATE',
        predecessor={**{k:receipt[k] for k in ('source_sha','workflow_sha256','policy_sha256','recipe_registration_sha256','run_id','feed_sha256','root_go_sha256','epoch_sha256','choice_sha256')},
            'receipt_sha256':OLD_RECEIPT,'root_static_sha256':template.static_root_sha256(old),'code_pins_sha256':store.sha(store.canonical(old['code_pins'])),
            'locator':dict(path=name,sha256=OLD_LOCATOR)},
        pin_overrides={path:old['code_pins'][path] for path in pins if pins[path]!=old['code_pins'][path]})
    root=deepcopy(old)
    root.update(schema_version=template.ROOT_V4,operation='CONTROLLER_REGISTRATION',source_sha=args.producer_source,code_pins=pins,
        issued_at_utc=issued.isoformat(),expires_at_utc=(issued+timedelta(hours=1)).isoformat(),source_history_binding=history.source_history_envelope(binding))
    if args.qualified_runtime is not None:
        # Preserve both original qualified documents. Existing dual-runtime
        # authentication controls selection and the current namespace budget.
        root['qualified_runtime']=json.loads(args.qualified_runtime.read_bytes())
        root['pending_census']=json.loads(args.pending_census.read_bytes())
        root['prior_capture_qualified_runtime']=dict(schema_version=template.PRIOR_RUNTIME,purpose='PRIOR_CAPTURE_QUALIFIED_RUNTIME',
            anchor=dict(feed_sha256=OLD_FEED,receipt_sha256=OLD_RECEIPT),qualified_runtime=deepcopy(old['qualified_runtime']),
            pending_census=deepcopy(old['pending_census']),root_static_sha256=template.static_root_sha256(old))
        template.prior_runtime(root,before=issued.isoformat())
    root['publication_registration'].update(policy_gzip_base64=base64.b64encode(gzip.compress(policy_raw,mtime=0)).decode(),policy_sha256=store.sha(policy_raw))
    pending_current=history.continued_pending_recovery(root,old)
    root['effective_epoch']=dict(schema_version=registration.RECOVERY_CONTEXT_SCHEMA,parent_source_sha=args.parent_source,parent_code_pins=parent_pins,
        previous_capture=dict(feed_sha256='214b3983f6fc6cbf2907afa1ef4ae0bd002179fdf99c78b9bc739b1f8431dd4c',receipt_sha256='ab065477019becb3546da50169341b4d884dd9d9976cb4ce3e32ed7bbb9abec0'),
        history_protocol=history.LOCATOR_VERSION,pending_post_recovery=template.pending_recovery_envelope(pending_current))
    static_root=deepcopy(root);static_root['approved']=False
    for field in ('effective_epoch','issued_at_utc','expires_at_utc','operation'):static_root[field]=None
    history.source_history_scope(static_root,receipt,locator=locator,locator_sha256=OLD_LOCATOR)
    hosted.validate_root(root,now=issued);registration._source_specs(root)
    encoded=store.canonical(root);dispatch=store.canonical(dict(ref='research/weekly-storage-probe-v1',inputs=dict(mode=hosted.MODE,
        inference_builder_go_json=encoded.decode(),inference_builder_go_sha256=store.sha(encoded))))
    require(len(encoded)<=60<<10 and len(dispatch)<=65535,'UNCHANGED_ROOT_AND_ACTIONS_CAPS')
    require(not cmd('git','status','--porcelain') and hosted.pins()==pins,'SOURCE_CHANGED_DURING_PREPARATION')
    for name,body in ((f'weekly-go-{args.attempt}.json',encoded),(f'weekly-dispatch-{args.attempt}.json',dispatch),(f'weekly-public-policy-{args.attempt}.json',policy_raw)):
        with (PRIVATE/name).open('xb') as stream:stream.write(body)
    print(json.dumps(dict(state='SOURCE_HISTORY_REGISTRATION_PREPARED_NO_POST',source_sha=args.producer_source,parent_source_sha=args.parent_source,
        root_go_sha256=store.sha(encoded),root_bytes=len(encoded),dispatch_bytes=len(dispatch),predecessor_run=40611698210,
        predecessor_feed_sha256=OLD_FEED,old_root_or_receipt_modified=False,old_first_or_recovery_claim_reused=False,
        new_fits=0,private_payload_GETs=0,remote_writes=0,issued_at_utc=issued.isoformat())))

if __name__=='__main__':
    os.umask(0o077)
    try:main()
    except Exception as error:
        code=str(error) if type(error) is ValueError and re.fullmatch('[A-Z][A-Z0-9_]{0,100}',str(error)) else 'SOURCE_OR_METADATA_PREPARATION_REJECTED'
        print(json.dumps(dict(state='PREPARATION_REJECTED_NO_POST',reason=code,remote_writes=0,new_fits=0)),file=sys.stderr)
        raise SystemExit(2)
