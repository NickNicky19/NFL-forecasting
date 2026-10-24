"""Explicit old-history cache preparation; zero NFL HTTP, fits or query values."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/weekly-continuation-source-cache-v3.json'
VERSION='weekly-continuation-source-cache-v3'
BUDGETS=dict(CPU_seconds=60,wall_seconds=90,RSS_bytes=1<<30,address_space_bytes=4<<30,new_retained_bytes=64<<20,
    global_bytes=512<<20,HTTP=0,fits=0,query_rows=0,forecasts=0,scores=0,invocations=1,retries=0)


def require(value,code):
    if not value:raise ValueError(code)
def sha(body):return hashlib.sha256(body).hexdigest()


def run(env,procedure_sha256,*,check=lambda:None):
    sys.path.insert(0,str(ROOT))
    from nfl_lab import private_draft_store as core,gha_private_checkpoint as cp,weekly_initial_continuation_v3 as cont
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab.owned_reference_batch import validate_owned_references
    from nfl_lab import operational_sources as source
    from nfl_lab.hosted_fixed_build_v1 import allowed_periods
    from tools.private_draft_store_v2 import actions_context
    from types import SimpleNamespace
    body=core.read_local(CONFIG,1<<20);require(sha(body)==procedure_sha256,'EXACT_SOURCE_CACHE_PREPARATION_PROCEDURE')
    config=cp.strict_json(body)
    require(config['schema_version']==VERSION+'-procedure' and config['state']=='ROOT_APPROVED_ZERO_HTTP_ZERO_FIT_SOURCE_CACHE_PREPARATION'
        and config['budgets']==BUDGETS,'EXPLICIT_SEPARATE_SOURCE_CACHE_BUDGET_REQUIRED')
    for name,expected in config['source_sha256'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and sha(core.read_local(ROOT/name,2<<20))==expected,'SOURCE_CACHE_CODE_OR_CONTROL_PIN')
    require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and env.get('GITHUB_RUN_ATTEMPT')=='1'
        and env.get('GITHUB_REPOSITORY')==core.REPO and env.get('GITHUB_JOB')=='genuine-hosted-fixed-build-restore-v1'
        and env.get('GITHUB_ACTOR')=='NickNicky19' and env.get('GITHUB_ACTOR_ID')=='208912933','GENUINE_CURRENT_RESTORE_JOB_REQUIRED')
    job=actions_context(env,'write');at=datetime.now(timezone.utc)
    registration=cp.strict_json(core.read_local(ROOT/cont.REGISTRATION_PATH,16384));origin=cont.origin(registration,now=at)
    root=core.parents_safe(Path(env['RUNNER_TEMP'])/('genuine-hosted-fixed-build-restore-v1-'+env['GITHUB_RUN_ID']))
    policy=source.load_source_policy(ROOT/'config/operational-source-policy-v2.json')
    require(policy['_policy_sha256']==cp.POLICY_SHA,'UNCHANGED_E7_SOURCE_CACHE_POLICY')
    storage=OperationalStorage(root/'cache',policy,state=root/'state');output=root/'source-cache-preparation-v3'
    restore_ref=cp.binding(root/'private-checkpoint-restore/RESTORE_FINISHED.json')
    validate_owned_references(storage,{restore_ref['path']:restore_ref['sha256']});restored=cp.strict_json(cp.read_ref(restore_ref))
    require(restored['schema_version']==cp.VERSION+'-continuation-restore-v3'
        and restored['state']=='FULL_PRIVATE_CHECKPOINT_RESTORED' and restored['source_sha']==env['GITHUB_SHA']
        and restored['run_id']==env['GITHUB_RUN_ID'] and restored['continuation_origin_sha256']==origin.registration_sha256
        and restored['parent_origin']==origin.parent and restored['index_sha256']==origin.parent['handoff']['index_descriptor']['entry']['payload']['sha256'],
        'EXACT_CURRENT_OWNED_CONTINUATION_RESTORE_REQUIRED')
    claim_ref=cp.binding(root/'private-checkpoint-restore/CONTINUATION_METADATA_CLAIM.json')
    validate_owned_references(storage,{claim_ref['path']:claim_ref['sha256']})
    cont.validate_metadata_consumption(cp.strict_json(cp.read_ref(claim_ref)),authority=origin,current_run=env['GITHUB_RUN_ID'],
        current_source=env['GITHUB_SHA'],current_api_job_id=restored['restorer']['api_job_id'])
    context=SimpleNamespace(run_id=env['GITHUB_RUN_ID'],source_sha=env['GITHUB_SHA'],process=core.process_identity(),
        binding=origin.parent['handoff']['runtime_binding'],job=job)
    require(len(restored['proofs'])==restored['groups']+1,'COMPLETE_CURRENT_RESTORE_PROOFS')
    for proof in restored['proofs']:
        core.check_proof(context,proof,'restore')
        require(proof['job']['job_id']==job['job_id'] and proof['job']['api_job_id']==restored['restorer']['api_job_id'],
            'EXACT_CURRENT_JOB_RESTORE_PROOF')
    mapped={Path(b['path']).relative_to(root/'private-checkpoint-restore/files').as_posix():b for b in restored['path_mapping'].values()}
    source_control=mapped['control/SOURCE_READBACK.json'];refs=[source_control]
    names=cp.source_names(policy)
    refs.extend(mapped['source-cache/raw/'+name+suffix] for name in names for suffix in ('','.receipt.json'))
    validate_owned_references(storage,{b['path']:b['sha256'] for b in refs})
    original=cp.strict_json(cp.read_ref(source_control));asof=at.isoformat()
    for name in names:
        receipt=cp.strict_json(cp.read_ref(mapped['source-cache/raw/'+name+'.receipt.json']))
        require(receipt['sha256']==mapped['source-cache/raw/'+name]['sha256'] and core.utc(receipt['retrieved_utc'])<=at,
            'ORIGINAL_SOURCE_RECEIPTS_MUST_PRECEDE_ACTUAL_PREPARATION_ASOF')
    class CacheStorage(OperationalStorage):
        anchor=None
        def _require(self,incoming):
            usage=super()._require(incoming)
            if self.anchor is not None:
                require(0<=usage['physical_bytes']-self.anchor and usage['physical_bytes']-self.anchor+incoming<=BUDGETS['new_retained_bytes'],
                    'SEPARATE_SOURCE_CACHE64MIB_BUDGET_EXHAUSTED')
            return usage
    store=CacheStorage(root/'cache',policy,state=root/'state')
    with store.transaction():
        require(not output.exists(),'SOURCE_CACHE_PREPARATION_ONCE_NO_RETRY')
        store.anchor=store.snapshot()['physical_bytes'];store.register_root(output)
        store.atomic_json(output/'CONSUMED.json',dict(schema_version=VERSION,continuation_origin_sha256=origin.registration_sha256,
            actual_started_at=asof,budgets=BUDGETS,baseline_physical_bytes=store.anchor,invocations=1,retries=0))
    check()
    manifest=source.acquire_operational_history(root/'cache',list(range(2019,2027)),policy,asof,
        source_cache=Path(restored['source_cache']),allowed_periods=allowed_periods(),storage=store,state=root/'state')
    check()
    manifest_ref=cp.binding(Path(manifest['namespace'])/'source-manifest.json')
    request=source._request(list(range(2019,2027)),policy,asof,allowed_periods())
    request_ref=cp.binding(root/'cache/operational-source-v2'/policy['_policy_sha256']/'requests'/(source._digest(request)+'.json'))
    from nfl_lab.weekly_source_read_batch import manifest_bindings
    bindings=manifest_bindings(manifest['namespace'],manifest,manifest_sha256=manifest_ref['sha256'],
        request_binding=request_ref['path'],request_binding_sha256=request_ref['sha256'])
    validate_owned_references(store,bindings)
    prepared=dict(schema_version=VERSION,state='OWNED_ORIGINAL_HISTORY_CACHE_PREPARED',procedure_sha256=procedure_sha256,
        source_sha=env['GITHUB_SHA'],run_id=env['GITHUB_RUN_ID'],continuation_origin_sha256=origin.registration_sha256,
        parent_source_capture=source_control,parent_capture_completed_at=original['actual_source_and_feature_capture_completed_at'],
        asof_utc=asof,actual_completed_at=datetime.now(timezone.utc).isoformat(),source_manifest=manifest_ref,request_binding=request_ref,
        namespace=manifest['namespace'],bindings=bindings,source_contract=original['source_contract'],original_source_bindings=refs[1:],
        allowed_periods={str(y):w for y,w in allowed_periods().items()},policy_sha256=cp.POLICY_SHA,
        baseline_physical_bytes=store.anchor,retained_physical_bytes_before_final_receipt=store.snapshot()['physical_bytes']-store.anchor,
        budgets=BUDGETS,HTTP=0,fits=0,query_rows=0,forecasts=0,scores=0,original_receipts_relabelled=False)
    store.atomic_json(output/'PREPARED.json',prepared)
    return cp.binding(output/'PREPARED.json')


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--procedure-sha256');args=parser.parse_args(argv)
    if not args.execute:print('{"state":"SOURCE_CACHE_PREPARATION_ONLY_NO_IO"}');return 2
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(60,60));resource.setrlimit(resource.RLIMIT_AS,(4<<30,4<<30))
        signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(90)
        def audit(event,unused):
            if event.startswith(('socket.','subprocess.')) or event in {'os.fork','os.forkpty','os.exec','os.system','os.posix_spawn','pickle.find_class'}:
                raise ValueError('SOURCE_CACHE_ZERO_HTTP_NO_CHILDREN_MODELS')
        sys.addaudithook(audit)
        text=ROOT/'config/weekly-continuation-source-cache-v3.json'
        config=json.loads(text.read_bytes())
        for name,value in config['numerical_environment'].items():require(os.environ.get(name)==value,'EXACT_SOURCE_CACHE_NUMERICAL_STARTUP')
        def check():require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<(1<<30)-33554432,'SOURCE_CACHE_RSS_STOP')
        def monitor():
            while True:
                time.sleep(.01)
                try:check()
                except BaseException:os.kill(os.getpid(),signal.SIGKILL)
        threading.Thread(target=monitor,daemon=True).start()
        ref=run(os.environ,args.procedure_sha256,check=check);check();print(json.dumps(dict(state='ORIGINAL_HISTORY_CACHE_PREPARED',receipt_sha256=ref['sha256'],HTTP=0,fits=0,forecasts=0),sort_keys=True));return 0
    except Exception as error:
        from nfl_lab.weekly_inference_diagnostics_v1 import safe_failure
        print(json.dumps(dict(state='SOURCE_CACHE_PREPARATION_FAILED_RETAINED',failure=safe_failure(error),HTTP=0,fits=0,forecasts=0),sort_keys=True));return 1


if __name__=='__main__':
    sys.path.insert(0,str(ROOT));raise SystemExit(main())
