"""Existing hosted build job checkpoint and fresh-job restore. No scheduler."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/gha-private-checkpoint-v1.json'
REGISTERED_CONFIG_SHA256='f4fe90f2bde17b97198b9a4f36f84ca7941c8fb4a17e2584db6c49598291cdb6'


def require(v,code):
    if not v:raise ValueError(code)
def sha(body):return hashlib.sha256(body).hexdigest()
def read(path,cap):
    path=Path(path);require(not path.is_symlink() and not any(p.is_symlink() for p in path.parents) and path.is_file() and path.stat().st_size<=cap,'CHECKPOINT_SOURCE_BOUND')
    body=path.read_bytes();require(len(body)<=cap,'CHECKPOINT_SOURCE_BOUND');return body


def verified(config_sha,*,recovery_v2=False,continuation_v3=False):
    sys.path.insert(0,str(ROOT))
    from nfl_lab.initial_horizon import resolve
    route=resolve(recovery_v2,continuation_v3=continuation_v3)
    body=read(ROOT/route.checkpoint_config_path if recovery_v2 or continuation_v3 else CONFIG,1<<20);require(sha(body)==config_sha,'CHECKPOINT_CONFIG_PIN');config=json.loads(body)
    require(config['schema_version']=='weekly-gha-private-checkpoint-procedure-v'+str(route.version) and config['authority_kind']=='ROOT_APPROVED_PROCEDURE'
        and config['state']=='ROOT_APPROVED_FOR_GENUINE_GHA' and config['source_policy_sha256']=='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441'
        and config['maximum_groups']==8 and config['maximum_files_per_group']==64 and config['runtime_cap_bytes']==32<<20
        and config['global_private_cap_bytes']==512<<20 and config['automatic_retries']==0,'CHECKPOINT_PROCEDURE_NOT_APPROVED')
    require({'nfl_lab/hosted_fixed_build_v1.py','tools/genuine_hosted_fixed_build_v1.py',route.build_config_path}<=set(config['source_sha256']),'REGISTERED_FIXED_BUILD_SOURCE_PINS_REQUIRED')
    expected='9fdae2c34732602c81155e7b6db0488043886ca45259f8c3560aa6787125ca72'
    if recovery_v2 or continuation_v3:
        from datetime import datetime,timezone
        registration=json.loads(read(ROOT/route.registration_path,16384));route.adapter().validate_registration(registration,now=datetime.now(timezone.utc))
        expected=sha(json.dumps(registration,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
        require(route.registration_path in config['source_sha256'],'REGISTERED_RECOVERY_REGISTRATION_PIN_REQUIRED')
    require(config['initial_registration_path']==route.registration_path
        and config['initial_registration_canonical_sha256']==expected
        and (continuation_v3 or config['claim_job']==config['produce_job']),'EXACT_ONCE_ONLY_CLAIM_SCOPE')
    for name,expected in config['source_sha256'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and sha(read(ROOT/name,2<<20))==expected,'CHECKPOINT_SOURCE_PIN')
    return config


def recovery_claim_preflight(env):
    """Admit the actual A build before consuming the new remote one-use claim."""
    sys.path.insert(0,str(ROOT))
    from tools import genuine_hosted_fixed_build_v1 as build
    text=env.get('BUILD_REGISTRATION_JSON','')
    require(0<len(text.encode())<=16384,'RECOVERY_BUILD_REGISTRATION_BEFORE_CLAIM')
    registration=json.loads(text);expected=registration.get('config_sha256')
    require(type(expected) is str and re.fullmatch('[a-f0-9]{64}',expected),'RECOVERY_BUILD_CONFIG_BEFORE_CLAIM')
    config=build.verify_sources(recovery_v2=True,config_sha256=expected)
    return build.preflight(env,config,recovery_v2=True)


def main(argv=None,*,environ=None,transport=None):
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['claim','produce','restore']);p.add_argument('--execute',action='store_true');p.add_argument('--config-sha256',default=REGISTERED_CONFIG_SHA256)
    p.add_argument('--recovery-v2',action='store_true');p.add_argument('--continuation-v3',action='store_true');args=p.parse_args(argv)
    if not args.execute:print('{"state":"CHECKPOINT_PREPARATION_ONLY_NO_IO"}');return 2
    factory=None
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20));signal.alarm(180)
        require(not args.continuation_v3 or args.phase=='restore','CONTINUATION_RESTORE_ONLY_NO_SOURCE_OR_CLAIM')
        config=verified(args.config_sha256,recovery_v2=args.recovery_v2,continuation_v3=args.continuation_v3);env=os.environ if environ is None else environ
        sys.path.insert(0,str(ROOT))
        from nfl_lab import gha_private_checkpoint as cp,private_draft_store as store
        from nfl_lab.operational_storage import OperationalStorage
        from tools.private_draft_store_v2 import actions_context
        continuation=None
        if args.continuation_v3:
            from datetime import datetime,timezone
            from nfl_lab.weekly_initial_continuation_v3 import origin,MODE,REGISTRATION_PATH
            registration=cp.strict_json(read(ROOT/REGISTRATION_PATH,16384));text=store.canonical(registration).decode()
            event=cp.strict_json(read(env['GITHUB_EVENT_PATH'],256<<10))
            require(event.get('repository',{}).get('full_name')==store.REPO and event.get('inputs',{}).get('mode')==MODE
                and event['inputs'].get('bootstrap_locators_json')==text
                and event['inputs'].get('bootstrap_locators_sha256')==sha(text.encode()),'EXACT_CONTINUATION_OWNER_DISPATCH')
            continuation=origin(registration,now=datetime.now(timezone.utc));config['_sha256']=args.config_sha256
            require(env.get('GITHUB_ACTOR')=='NickNicky19' and env.get('GITHUB_ACTOR_ID')=='208912933','EXACT_CONTINUATION_OWNER_ACTOR')
        require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==store.REPO and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
            and env.get('GITHUB_RUN_ATTEMPT')=='1' and env.get('STORE_PERMISSION')=='write' and env.get('CHECKPOINT_MODE')==config['build_mode']
            and env.get('GITHUB_JOB')==config[args.phase+'_job'],'GENUINE_CHECKPOINT_JOB_CONTEXT')
        if args.recovery_v2 and args.phase=='claim':recovery_claim_preflight(env)
        job=actions_context(env,'write');run_id=env['GITHUB_RUN_ID'];source_sha=env['GITHUB_SHA']
        require(re.fullmatch('[1-9][0-9]{0,19}',run_id),'EXACT_RUN_ID')
        actual=json.loads(read(ROOT/config['canary_report'],256<<10));runtime=actual['binding'];qualification=actual['qualification']
        require(cp.store.sha(cp.store.canonical(runtime))==config['binding_sha256'] and cp.store.sha(cp.store.canonical(qualification))==config['qualification_sha256']
            and actual['source_sha']==config['canary_source_sha'] and qualification['source_sha']==config['canary_source_sha'],'EXACT_OLD_QUALIFIED_RUNTIME')
        policy=json.loads(read(ROOT/'config/operational-source-policy-v2.json',1<<20));policy['_path']=str(ROOT/'config/operational-source-policy-v2.json')
        require(cp.source_names(policy)==config['source_names'],'EXACT19_SOURCE_WHITELIST')
        root=store.parents_safe(Path(env['RUNNER_TEMP'])/(config['build_mode']+'-'+run_id)) if args.phase in {'claim','produce'} else store.parents_safe(Path(env['RUNNER_TEMP'])/('genuine-hosted-fixed-build-restore-v1-'+run_id))
        if args.phase in {'claim','restore'}:require(not root.exists(),'FRESH_CHECKPOINT_PHASE_ROOT');root.mkdir(mode=0o700)
        else:require(root.is_dir(),'CLAIMED_BUILD_ROOT_REQUIRED')
        storage=OperationalStorage(root/'cache',policy,state=root/'state');storage.register_root(root)
        output=root/('private-checkpoint-'+args.phase);output.mkdir(mode=0o700);journal=output/'journal';journal.mkdir(mode=0o700)
        with storage.transaction():
            storage._require(sum(len(store.canonical(q)) for q in config['external_pending_reservations']));cp.seed_pending(journal,config['external_pending_reservations'])
        class GhaClient(store.Client):
            def allow(self,url):
                if continuation is not None and url in {self.path('/actions/runs/'+continuation.parent['run_id']),
                        self.path('/actions/runs/'+continuation.parent['run_id']+'/jobs?per_page=100&page=1')}:
                    self.allowed.add(url);return url
                return super().allow(url)
            def reserve(self,key,body,*,name=None):
                safe=cp.reservation_metadata(key,body,name)
                super().reserve(key,body,name=name)
                # Safe intent survives runner loss; it is emitted BEFORE transport.
                print('CHECKPOINT_SAFE_POST_RESERVATION_JSON='+store.canonical(safe).decode(),flush=True)
        class Factory:
            calls=0;last=None;clients=[]
            def __call__(self,operation):
                require(len(self.clients)<9,'NINE_CORE_OPERATIONS_MAX')
                c=GhaClient(env.get('GITHUB_TOKEN'),run_id,journal=journal,source_sha=source_sha,job=job,transport=transport,operation=operation)
                self.last=c;self.clients.append(c)  # Failed authentication HTTP remains charged.
                c.authenticate_actions_job();c.bind(runtime);return c
        factory=Factory()
        if args.phase=='claim':
            client=factory('claim');registration=cp.strict_json(read(ROOT/config['initial_registration_path'],16384));body=store.canonical(registration)
            native=dict(schema_version=cp.VERSION+'-native-claim-GO',authority_kind='ROOT_APPROVED_PROCEDURE',human_approval=False,procedure_sha256=args.config_sha256,
                registration_sha256=config['initial_registration_canonical_sha256'],repository=store.REPO,run_id=run_id,source_sha=source_sha,job=client.job,binding_sha256=config['binding_sha256'],operation='claim_once')
            storage.write_bytes(output/'NATIVE_CLAIM_GO.json',store.canonical(native))
            result=cp.claim_once(client,body,qualification,expected_sha256=config['initial_registration_canonical_sha256'],procedure_sha256=args.config_sha256,recovery_v2=args.recovery_v2)
            text=store.canonical(result).decode();storage.write_bytes(output/'CLAIM_RECEIPT.json',text.encode())
            print('CHECKPOINT_SAFE_CLAIM_RECEIPT_JSON='+text);print('CHECKPOINT_SAFE_CLAIM_RECEIPT_SHA256='+sha(text.encode()))
            if env.get('GITHUB_OUTPUT'):
                with open(env['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:stream.write('claim_receipt_json='+text+'\nclaim_receipt_sha256='+sha(text.encode())+'\n')
        elif args.phase=='produce':
            first=factory('append')  # Real API job authentication before private metadata/body reads.
            files,pairs,build_ref=cp.collect(root,storage,policy,source_sha=source_sha,job=first.job,recovery_v2=args.recovery_v2)
            result=cp.produce(files,pairs,build_ref,factory,qualification,procedure_sha256=args.config_sha256,source_sha=source_sha,run_id=run_id,output=output,storage=storage,pending=config['external_pending_reservations'],first=first)
            text=store.canonical(result).decode();print('CHECKPOINT_SAFE_HANDOFF_JSON='+text);print('CHECKPOINT_SAFE_HANDOFF_SHA256='+sha(text.encode()))
            if env.get('GITHUB_OUTPUT'):
                with open(env['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:stream.write('handoff_json='+text+'\nhandoff_sha256='+sha(text.encode())+'\n')
        else:
            text=store.canonical(continuation.parent['handoff']).decode() if continuation is not None else env.get('CHECKPOINT_HANDOFF_JSON','')
            require(len(text.encode())<=16384 and (continuation is not None or sha(text.encode())==env.get('CHECKPOINT_HANDOFF_SHA256')),'EXACT_SAFE_HANDOFF_HASH')
            handoff=cp.strict_json(text);require(set(handoff)=={'schema_version','repository','procedure_sha256','source_sha','run_id','runtime_binding','index_descriptor'}
                and handoff['schema_version']==cp.VERSION+'-handoff' and handoff['repository']==store.REPO
                and handoff['procedure_sha256']==(continuation.parent['checkpoint_procedure_sha256'] if continuation is not None else args.config_sha256)
                and handoff['source_sha']==(continuation.parent['source_sha'] if continuation is not None else source_sha)
                and handoff['run_id']==(continuation.parent['run_id'] if continuation is not None else run_id)
                and handoff['runtime_binding']==runtime,'EXACT_CURRENT_RUN_HANDOFF')
            # Authenticate this job and the completed real producer before restore.
            first=factory('restore');parent_run=continuation.parent['run_id'] if continuation is not None else run_id
            parent_source=continuation.parent['source_sha'] if continuation is not None else source_sha
            if continuation is not None:
                parent_run_metadata=first.json(first.allow(first.path('/actions/runs/'+parent_run)))
                require(parent_run_metadata.get('id')==int(parent_run) and parent_run_metadata.get('head_sha')==parent_source
                    and parent_run_metadata.get('run_attempt')==1 and parent_run_metadata.get('status')=='completed'
                    and parent_run_metadata.get('conclusion')=='failure' and parent_run_metadata.get('event')=='workflow_dispatch'
                    and parent_run_metadata.get('path')=='.github/workflows/lab.yml'
                    and parent_run_metadata.get('repository',{}).get('full_name')==store.REPO,'EXACT_COMPLETED_PARENT_RUN_REQUIRED')
            jobs=first.json(first.allow(first.path('/actions/runs/'+parent_run+'/jobs?per_page=100&page=1')))
            require(type(jobs.get('jobs')) is list and jobs.get('total_count')==len(jobs['jobs']) and len(jobs['jobs'])<=100,'COMPLETE_PREDECESSOR_JOB_LIST')
            matches=[j for j in jobs['jobs'] if j.get('name')==config['produce_job'] and j.get('head_sha')==parent_source and j.get('run_id')==int(parent_run)]
            require(len(matches)==1 and matches[0].get('status')=='completed' and matches[0].get('conclusion')=='success','SUCCESSFUL_REAL_PRODUCER_REQUIRED')
            if continuation is not None:
                require(matches[0].get('id')==continuation.parent['producer_api_job_id']
                    and store.utc(matches[0]['completed_at'])<=store.utc(continuation.registration['registered_at_utc'])
                    and run_id!=parent_run,'ACTUAL_REGISTERED_PARENT_SOURCE_COMPLETED_BEFORE_CONTINUATION')
                from nfl_lab.weekly_initial_continuation_v3 import consume_metadata_once
                consumed=consume_metadata_once(first,continuation,qualification)
                storage.atomic_json(output/'CONTINUATION_METADATA_CLAIM.json',consumed)
                print(json.dumps(dict(state='ONE_TIME_CONTINUATION_METADATA_CONSUMED',registration_sha256=continuation.registration_sha256,
                    asset_id=consumed['asset_id'],continuation_metadata_claims=1,source_claims=0,fits=0),sort_keys=True),flush=True)
            else:
                own=[j for j in jobs['jobs'] if j.get('id')==first.job['api_job_id']]
                require(len(own)==1 and store.utc(matches[0]['completed_at'])<=store.utc(own[0]['started_at']),'ACTUAL_PRODUCER_BEFORE_RESTORE_JOB')
            # First authenticated client is consumed by the index restore.
            original=factory.__call__;used=False
            class RestoreFactory:
                last=first
                def __call__(self,operation):
                    nonlocal used
                    if not used:used=True;return first
                    self.last=original(operation);return self.last
            result=cp.restore(handoff,RestoreFactory(),config=config,storage=storage,output=output,producer_api_job_id=matches[0]['id'],continuation=continuation)
            print(json.dumps(dict(state=result['state'],index_sha256=result['index_sha256'],files=result['files'],groups=result['groups'],model_decodes=0,selected_forecast_durability='NOT_CLAIMED'),sort_keys=True))
        require(sum(c.calls for c in factory.clients)<=(40 if args.phase=='claim' else 360),'CHECKPOINT_HTTP_CAP')
        return 0
    except Exception as error:
        reason=getattr(error,'code',str(error));reason=reason if re.fullmatch('[A-Z0-9_]{1,90}',reason) else 'CHECKPOINT_FAILED_RETAINED'
        pending=[]
        if factory:
            try:
                for path in sorted(journal.glob('*.reservation.json')):
                    require(len(pending)<128,'PENDING_SUMMARY_CAP');q=json.loads(read(path,16384))
                    require(set(q)=={'schema_version','key','bytes','sha256','name'} and re.fullmatch(r'(blob-[a-f0-9]{64}\.bin|manifest-[a-f0-9]{64}\.json)',q['name']),'SAFE_RESERVATION_METADATA_ONLY');pending.append(q)
            except Exception:pending=None
        print(json.dumps(dict(state='CHECKPOINT_FAILED_RETAINED',reason=reason,HTTP_calls=sum(c.calls for c in factory.clients) if factory else 0,pending_reservations=pending,model_decodes=0,public_payload_bytes=0),sort_keys=True));return 1


if __name__=='__main__':raise SystemExit(main())
