"""Explicit same-job append, fresh restore and export-job consume; no scheduler."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/selected-private-snapshot-v1.json'
CONFIG_SHA256='f908af1a4130705dc53e368acda96a658f8166035c693e353e08679a022cbef8'


def require(v,code):
    if not v:raise ValueError(code)
def sha(body):return hashlib.sha256(body).hexdigest()
def read(path,cap):
    path=Path(path);require(path.is_file() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents) and path.stat().st_size<=cap,'SELECTED_CONTROL_BOUND')
    body=path.read_bytes();require(len(body)<=cap,'SELECTED_CONTROL_BOUND');return body
def verify_sources(expected,*,recovery_v2=False):
    sys.path.insert(0,str(ROOT))
    from nfl_lab.initial_horizon import resolve
    route=resolve(recovery_v2)
    path=ROOT/'config/selected-private-snapshot-v2.json' if recovery_v2 else CONFIG
    body=read(path,1<<20);require(sha(body)==expected,'SELECTED_PROCEDURE_PIN');c=json.loads(body)
    require(c['schema_version']=='weekly-selected-private-snapshot-procedure-v'+str(route.version) and c['state']=='ROOT_APPROVED_FOR_GENUINE_GHA'
        and c['authority_kind']=='ROOT_APPROVED_PROCEDURE' and c['input_cutoff_utc']==route.cutoff,'SELECTED_PROCEDURE_PENDING')
    for path,value in c['source_sha256'].items():
        require(not Path(path).is_absolute() and '..' not in Path(path).parts and sha(read(ROOT/path,2<<20))==value,'SELECTED_SOURCE_PIN')
    c['_sha256']=expected;return c


def main(argv=None,*,environ=None,transport=None):
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['produce','restore','consume']);p.add_argument('--execute',action='store_true');p.add_argument('--config-sha256',default=CONFIG_SHA256)
    p.add_argument('--recovery-v2',action='store_true');args=p.parse_args(argv)
    if not args.execute:print('{"state":"SELECTED_SNAPSHOT_PREPARATION_ONLY"}');return 2
    clients=[]
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20));signal.alarm(180)
        c=verify_sources(args.config_sha256,recovery_v2=args.recovery_v2);env=os.environ if environ is None else environ
        sys.path.insert(0,str(ROOT))
        from nfl_lab import selected_private_snapshot as snap,private_draft_store as s,gha_private_checkpoint as cp
        from nfl_lab.operational_storage import OperationalStorage
        from tools.private_draft_store_v2 import actions_context
        require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==s.REPO and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
            and env.get('GITHUB_RUN_ATTEMPT')=='1' and env.get('STORE_PERMISSION')=='write' and env.get('SELECTED_SNAPSHOT_MODE')==c['mode']
            and env.get('GITHUB_JOB')==c[args.phase+'_job'],'GENUINE_SELECTED_JOB_REQUIRED')
        job=actions_context(env,'write');run=env['GITHUB_RUN_ID'];source=env['GITHUB_SHA']
        actual=json.loads(read(ROOT/c['canary_report'],256<<10));binding=actual['binding'];q=actual['qualification']
        require(s.sha(s.canonical(binding))==c['binding_sha256'] and s.sha(s.canonical(q))==c['qualification_sha256'],'EXACT_OLD_RUNTIME_QUALIFICATION');c['_qualification']=q
        base=Path(env['RUNNER_TEMP'])/(c['produce_root_prefix']+'-'+run) if args.phase=='produce' else Path(env['RUNNER_TEMP'])/(c[args.phase+'_job']+'-'+run)
        if args.phase!='produce':require(not base.exists(),'FRESH_SELECTED_JOB_ROOT');base.mkdir(mode=0o700)
        else:require(base.is_dir(),'EXISTING_INFERENCE_ROOT_REQUIRED')
        policy=json.loads(read(ROOT/'config/operational-source-policy-v2.json',1<<20));storage=OperationalStorage(base/'cache',policy,state=base/'state');storage.register_root(base)
        output=base/('selected-private-'+args.phase);output.mkdir(mode=0o700);journal=output/'journal';journal.mkdir(mode=0o700)
        with storage.transaction():storage._require(sum(len(s.canonical(x)) for x in c['external_pending_reservations']));cp.seed_pending(journal,c['external_pending_reservations'])
        class Client(s.Client):
            def reserve(self,key,body,*,name=None):
                record=cp.reservation_metadata(key,body,name)
                with storage.transaction():storage._require(len(s.canonical(record)));super().reserve(key,body,name=name)
                print('SELECTED_SAFE_POST_INTENT_JSON='+s.canonical(record).decode(),flush=True)
        class Factory:
            last=None
            def __call__(self,operation):
                require(len(clients)<11,'ELEVEN_NATIVE_OPERATIONS_MAX')
                client=Client(env.get('GITHUB_TOKEN'),run,journal=journal,source_sha=source,job=job,transport=transport,operation=operation);clients.append(client);self.last=client
                client.authenticate_actions_job();client.bind(binding);return client
        factory=Factory()
        if args.phase=='produce':
            first=factory('append');selected,files,refs,producer,candidates=snap.collect(base/('initial-inference-v2' if args.recovery_v2 else 'initial-inference-v1'),storage,output,first,c)
            result=snap.append_snapshot(selected,files,refs,producer,candidates,factory,q,storage,output,c,first=first)
        else:
            text=env.get('SELECTED_SNAPSHOT_HANDOFF_JSON','');require(len(text.encode())<=32768 and sha(text.encode())==env.get('SELECTED_SNAPSHOT_HANDOFF_SHA256'),'EXACT_SELECTED_HANDOFF')
            result=snap.cp.strict_json(text);keys={'schema_version','runtime_binding','source_sha','run_id','procedure_sha256','index_descriptor'}
            require(set(result)==keys|({'witness_descriptor'} if args.phase=='consume' else set()) and result['schema_version']==snap.VERSION+'-handoff'
                and result['runtime_binding']==binding and result['source_sha']==source and result['run_id']==run and result['procedure_sha256']==c['_sha256'],'REGISTERED_CURRENT_SELECTED_HANDOFF')
            witness=result.pop('witness_descriptor',None)
            # Authenticate exact successful predecessor before reading payloads.
            first=factory('restore');jobs=first.json(first.allow(first.path('/actions/runs/'+run+'/jobs?per_page=100&page=1')))
            predecessor=c['produce_job' if args.phase=='restore' else 'restore_job'];matches=[j for j in jobs.get('jobs',[]) if j.get('name')==predecessor and j.get('head_sha')==source and j.get('run_id')==int(run)]
            require(jobs.get('total_count')==len(jobs.get('jobs',[])) and len(jobs['jobs'])<=100 and len(matches)==1 and matches[0].get('status')=='completed' and matches[0].get('conclusion')=='success','SUCCESSFUL_SELECTED_PREDECESSOR_REQUIRED')
            producers=[j for j in jobs['jobs'] if j.get('name')==c['produce_job'] and j.get('head_sha')==source and j.get('run_id')==int(run)]
            require(len(producers)==1 and producers[0].get('status')=='completed' and producers[0].get('conclusion')=='success','EXACT_ACTUAL_PRODUCER_JOB')
            original=factory.__call__;used=False
            class Restores:
                last=first
                def __call__(self,operation):
                    nonlocal used
                    if not used:used=True;return first
                    self.last=original(operation);return self.last
            restored=snap.restore_snapshot(result,Restores(),storage,output,c,producer_api_job_id=producers[0]['id'],witness=witness,witness_api_job_id=matches[0]['id'] if args.phase=='consume' else None)
            if args.phase=='restore':result['witness_descriptor']=restored['witness_descriptor']
            else:result=dict(state='PRIVATE_EXPORT_INPUTS_RESTORED',input_sha256=sha(read(output/'EXPORT_INPUTS_RELOCATED.json',1<<20)),candidates_retained=18,public_export_authorized=False)
        require(sum(x.calls for x in clients)<=440,'SELECTED_NATIVE_HTTP_CAP')
        text=s.canonical(result).decode();print('SELECTED_SAFE_RESULT_JSON='+text)
        if args.phase!='consume' and env.get('GITHUB_OUTPUT'):
            with open(env['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:stream.write('handoff_json='+text+'\nhandoff_sha256='+sha(text.encode())+'\n')
        return 0
    except Exception as error:
        reason=getattr(error,'code',str(error));reason=reason if isinstance(reason,str) and re.fullmatch('[A-Z0-9_]{1,90}',reason) else 'SELECTED_SNAPSHOT_FAILED_RETAINED'
        print(json.dumps(dict(state='SELECTED_SNAPSHOT_FAILED_RETAINED',reason=reason,HTTP_calls=sum(x.calls for x in clients),public_export_authorized=False)));return 1


if __name__=='__main__':raise SystemExit(main())
