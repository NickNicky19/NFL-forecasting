"""Genuine manual hosted SOURCE+TRAIN18 only; preparation performs no I/O."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
from importlib import metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import signal
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/genuine-hosted-fixed-build-v1.json'
CONFIG_SHA256='ab0fcff5adb3f17e68561554a804b4d73ee57eb461bb7a9ad8e3b34a14b12e1f'
MODE='genuine-hosted-fixed-build-v1'
REPO='NickNicky19/NFL-forecasting'


class GuardStop(Exception):pass
def require(value,code):
    if not value:raise GuardStop(code)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(body):return hashlib.sha256(body).hexdigest()
def utc(value):
    result=datetime.fromisoformat(str(value).replace('Z','+00:00'));require(result.tzinfo is not None,'EXPLICIT_UTC_CLOCK_REQUIRED')
    return result.astimezone(timezone.utc)
def now():return datetime.now(timezone.utc)


def read(path,cap):
    p=Path(path);require(not p.is_symlink() and not any(v.is_symlink() for v in p.parents) and p.is_file() and p.stat().st_size<=cap,'BOUND_SOURCE_OR_CONTROL')
    body=p.read_bytes();require(len(body)<=cap,'BOUND_SOURCE_OR_CONTROL');return body


def verify_sources():
    body=read(CONFIG,1<<20);require(sha(body)==CONFIG_SHA256,'BUILD_CONFIG_HASH');config=json.loads(body)
    require(config['schema_version']=='genuine-hosted-fixed-build-plan-v1' and config['mode']==MODE and config['maximum_new_fits']==18,'FIXED_BUILD_SCOPE')
    for name,expected in config['source_sha256'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and sha(read(ROOT/name,2<<20))==expected,'BUILD_SOURCE_CHANGED')
    return config


def preflight(env,config):
    require(env.get('GITHUB_ACTIONS')=='true' and env.get('CI')=='true' and env.get('RUNNER_ENVIRONMENT')=='github-hosted'
        and env.get('GITHUB_REPOSITORY')==REPO and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and env.get('GITHUB_RUN_ATTEMPT')=='1'
        and env.get('GITHUB_JOB')==MODE and env.get('BUILD_MODE')==MODE and env.get('STORE_PERMISSION')=='write'
        and env.get('GITHUB_ACTOR')=='NickNicky19' and env.get('GITHUB_ACTOR_ID')=='208912933'
        and re.fullmatch(r'[1-9][0-9]{0,19}',env.get('GITHUB_RUN_ID','')) and re.fullmatch(r'[a-f0-9]{40}',env.get('GITHUB_SHA',''))
        and env.get('GITHUB_WORKFLOW_SHA')==env.get('GITHUB_SHA') and env.get('GITHUB_WORKSPACE')==str(ROOT)
        and read(ROOT/'.git/HEAD',4096).decode().strip()==env['GITHUB_SHA']
        and env.get('GITHUB_WORKFLOW_REF')==REPO+'/.github/workflows/lab.yml@'+env.get('GITHUB_REF',''),'GENUINE_BUILD_CONTEXT')
    for key,value in config['numerical_environment'].items():require(env.get(key)==value,'TWO_THREAD_ALLOCATOR_STARTUP')
    text=env.get('BUILD_REGISTRATION_JSON','');expected=env.get('BUILD_REGISTRATION_SHA256','')
    require(len(text.encode())<=16384 and re.fullmatch(r'[a-f0-9]{64}',expected) and sha(text.encode())==expected,'EXACT_BUILD_REGISTRATION_HASH')
    registration=json.loads(text)
    keys={'schema_version','registration_id','approved','repository','source_sha','config_sha256','registered_at_utc','input_cutoff_utc',
        'training_cutoff_utc','scope','maximum_new_fits','old_artifact_reproduction','scientific_qualification','initial_registration','initial_registration_sha256'}
    require(set(registration)==keys and canonical(registration).decode()==text and registration['schema_version']=='genuine-hosted-fixed-build-registration-v1'
        and registration['registration_id']=='initial-remaining-2026W7-new15Z-operational-build-v1' and registration['approved'] is True
        and registration['repository']==REPO and registration['source_sha']==env['GITHUB_SHA'] and registration['config_sha256']==CONFIG_SHA256
        and registration['input_cutoff_utc']=='2026-10-24T15:00:00Z' and registration['training_cutoff_utc']=='2026-09-01T00:00:00Z'
        and registration['scope']=='SOURCE_AND_TRAIN_FIXED18_ONLY' and type(registration['maximum_new_fits']) is int and registration['maximum_new_fits']==18
        and registration['old_artifact_reproduction'] is False and registration['scientific_qualification'] is False
        and utc(registration['registered_at_utc'])<=now()<utc(registration['input_cutoff_utc']),'REGISTER_NEW_OPERATIONAL_BUILD_BEFORE_INPUTS')
    sys.path.insert(0,str(ROOT))
    from nfl_lab.weekly_initial_remaining_v1 import validate_registration
    initial=registration['initial_registration'];validate_registration(initial,now=now())
    registered=json.loads(read(ROOT/'config/weekly-initial-remaining-v1-registration.json',16384))
    require(initial==registered
        and sha(canonical(initial))==config['initial_registration_canonical_sha256']
        ==registration['initial_registration_sha256']
        and utc(initial['registered_at_utc'])<=utc(registration['registered_at_utc']),'EXACT_INITIAL_REGISTRATION_BEFORE_BUILD_INPUTS')
    event=json.loads(read(env['GITHUB_EVENT_PATH'],256<<10))
    require(event.get('inputs',{}).get('mode')==MODE and event.get('inputs',{}).get('build_registration_json')==text
        and event.get('inputs',{}).get('build_registration_sha256')==expected and event.get('repository',{}).get('full_name')==REPO
        and event.get('ref') in {env['GITHUB_REF'],env['GITHUB_REF'].removeprefix('refs/heads/')},'EXACT_BUILD_DISPATCH')
    for name,version in config['environment_versions'].items():require(metadata.version(name)==version,'EXACT_HOSTED_MODEL_DEPENDENCIES')
    return registration


def imported(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def verify_source_claim(env,config,registration,directory,*,job=None,process=None):
    """Bind the preceding genuine step's one-time remote claim before source I/O."""
    keys={'schema_version','state','repository','run_id','source_sha','job_id','api_job_id','process_identity',
        'registration_sha256','registration_bytes','asset_id','asset_name','binding_sha256','procedure_sha256','claimed_at'}
    text=env.get('BUILD_CLAIM_RECEIPT_JSON','');expected=env.get('BUILD_CLAIM_RECEIPT_SHA256','')
    require(0<len(text.encode())<=16384 and re.fullmatch('[a-f0-9]{64}',expected) and sha(text.encode())==expected,'EXACT_SOURCE_CLAIM_RECEIPT')
    receipt=json.loads(text);physical=read(Path(directory)/'private-checkpoint-claim/CLAIM_RECEIPT.json',16384)
    initial=canonical(registration['initial_registration']);digest=sha(initial)
    require(canonical(receipt).decode()==text and physical==text.encode() and set(receipt)==keys
        and receipt['schema_version']=='weekly-gha-private-checkpoint-v1-source-claim' and receipt['state']=='ONE_TIME_SOURCE_CLAIMED'
        and receipt['repository']==REPO and receipt['run_id']==env['GITHUB_RUN_ID'] and receipt['source_sha']==env['GITHUB_SHA']
        and receipt['job_id']==MODE and type(receipt['api_job_id']) is int and receipt['api_job_id']>0
        and type(receipt['asset_id']) is int and receipt['asset_id']>0 and re.fullmatch('[a-f0-9]{64}',receipt['process_identity'])
        and receipt['registration_sha256']==digest==config['initial_registration_canonical_sha256']
        and type(receipt['registration_bytes']) is int and receipt['registration_bytes']==len(initial)
        and receipt['asset_name']=='manifest-'+digest+'.json'
        and receipt['binding_sha256']=='763d08e2d576434b3722ad942da9f807645f6ffa39d0650616fae80a11d1fa11'
        and receipt['procedure_sha256']==sha(read(ROOT/'config/gha-private-checkpoint-v1.json',1<<20))
        and utc(registration['registered_at_utc'])<=utc(receipt['claimed_at'])<=now(),'AUTHENTIC_ONE_TIME_SOURCE_CLAIM_REQUIRED')
    allowed={'cache','state','private-checkpoint-claim','.operational-storage-owner','API-journal'}
    require(Path(directory).is_dir() and {p.name for p in Path(directory).iterdir()}<=allowed,'SOURCE_BUILD_ALREADY_CONSUMED_OR_DIRTY')
    if job is not None:
        require(job['run_authenticated'] is True and receipt['job_id']==job['job_id'] and receipt['api_job_id']==job['api_job_id']
            and receipt['process_identity']!=process,'SOURCE_CLAIM_GENUINE_CURRENT_JOB')
    return receipt


def run_build(env,config,registration):
    sys.path.insert(0,str(ROOT))
    from nfl_lab import hosted_fixed_build_v1 as build,private_draft_store as private
    started=time.monotonic();cpu=time.process_time();deadline=utc(registration['input_cutoff_utc'])
    sampler=imported(ROOT/'tools/review_direct_booster_screen_guard_v4.py','hosted_build_existing_pid_sampler')
    binding=sampler.process_binding(os.getpid());stop=threading.Event();memory=dict(samples=0,sampled_peak_bytes=0,highwater_bytes=0)
    def sample():
        rss,_=sampler.required_usage([binding]);peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        memory['samples']+=1;memory['sampled_peak_bytes']=max(memory['sampled_peak_bytes'],rss);memory['highwater_bytes']=max(memory['highwater_bytes'],peak)
        if max(rss,peak)>=1073741824-33554432:raise build.BuildStop('BUILD_PHYSICAL_RSS')
    def monitor():
        while not stop.wait(.01):
            try:sample()
            except BaseException:
                os.write(2,b'{"state":"HOSTED_BUILD_RSS_OR_ACCOUNTING_STOP"}\n');os.kill(os.getpid(),signal.SIGKILL)
    sample();watcher=threading.Thread(target=monitor,daemon=True,name='hosted-build-existing-rss-monitor');watcher.start()
    import pandas as pd
    import pyarrow as pa
    import requests
    import threadpoolctl
    pa.set_cpu_count(2);pa.set_io_thread_count(2);pa.set_memory_pool(pa.system_memory_pool())
    from nfl_lab import operational_sources as source,weekly_future_inference as future
    from nfl_lab.operational_storage import OperationalStorage
    from tools.private_draft_store_v2 import actions_context
    from tools.weekly_future_train import category_contracts,training_columns
    policy=source.load_source_policy(ROOT/'config/operational-source-policy-v2.json')
    directory=private.parents_safe(Path(env['RUNNER_TEMP'])/(MODE+'-'+env['GITHUB_RUN_ID']))
    verify_source_claim(env,config,registration,directory)
    class BuildStorage(OperationalStorage):
        model_anchor=None
        def _require(self,incoming):
            usage=super()._require(incoming)
            if self.model_anchor is not None and usage['physical_bytes']-self.model_anchor+incoming>12<<20:raise build.BuildStop('MODEL_PHASE_RETAINED12MIB_CAP')
            return usage
    storage=BuildStorage(directory/'cache',policy,state=directory/'state');storage.register_root(directory)
    journal=directory/'API-journal';journal.mkdir(mode=0o700)
    client=private.Client(env.get('GITHUB_TOKEN'),env['GITHUB_RUN_ID'],journal=journal,source_sha=env['GITHUB_SHA'],job=actions_context(env,'write'),operation=MODE)
    client.authenticate_actions_job()  # Genuine current run/job before any NFL source request.
    claim=verify_source_claim(env,config,registration,directory,job=client.job,process=client.process)
    storage.atomic_json(directory/'BUILD_REGISTRATION.json',registration)
    storage.atomic_json(directory/'CONSUMED.json',dict(source_invocations=1,new_logical_fit_budget=18,automatic_retries=0,source_sha=env['GITHUB_SHA'],source_claim_receipt_sha256=sha(canonical(claim))))
    trained=build.initial_training_report();storage.atomic_json(directory/'TRAIN18_REGISTERED_SLOTS.json',trained)
    names=source._names(list(range(2019,2027)))
    budget=build.SourceBudget({name:item['url'] for name,item in names.items()},record=lambda i,r:storage.atomic_json(directory/f'source-attempts/{i:02}.json',r))
    def audit(event,unused):
        if event in {'subprocess.Popen','os.fork','os.forkpty','os.exec','os.system','os.posix_spawn'}:raise build.BuildStop('BUILD_CHILDREN_FORBIDDEN')
        if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'} and not getattr(budget.local,'transport',False):raise build.BuildStop('NETWORK_OUTSIDE_OFFICIAL_SOURCE_TRANSPORT')
    sys.addaudithook(audit)
    def check():
        sample()
        if time.process_time()-cpu>=580 or time.monotonic()-started>=1180 or now()>=deadline:raise build.BuildStop('BUILD_BUDGET_OR15Z_CUTOFF')
    libc_path=Path('/usr/lib/x86_64-linux-gnu/libc.so.6').resolve(strict=True)
    libc=dict(path=str(libc_path),bytes=libc_path.stat().st_size,sha256=sha(read(libc_path,8<<20)))
    guard=imported(ROOT/'tools/ngboost_law_software_v1.py','hosted_build_existing_process_free_threads')
    phase='SOURCE';fatal=None;source_receipt=None;source_asof=now().isoformat()
    try:
        with guard.process_free_threads(threadpoolctl,libc),threadpoolctl.threadpool_limits(limits=2):
            with build.hard_deadline(300),budget.install(requests):
                check();manifest=source.acquire_operational_history(directory/'cache',list(range(2019,2027)),policy,source_asof,
                    source_cache=None,allowed_periods=build.allowed_periods(),state=directory/'state',storage=storage)
                history=source.load_operational_history(directory/'cache',list(range(2019,2027)),policy,source_asof,allowed_periods=build.allowed_periods())
                check();features=source.build_operational_features(history,policy=policy)
                schedule=pd.read_csv(Path(manifest['namespace'])/'raw/schedules.csv',usecols=['season','game_id','game_type'])
                categories=category_contracts(json.loads(read(ROOT/'reports/all12-leaf-cdf-v1/method-config.json',1<<20)))
                train=build.training_rows(features,schedule).loc[:,training_columns(categories,future.IDENTITY)].copy()
                del features,history
                train.attrs.clear();feature_path=directory/'training-features.parquet';storage.write_dataframe(train,feature_path,index=False,compression='zstd')
                feature_ref=future.binding(feature_path);manifest_ref=future.binding(Path(manifest['namespace'])/'source-manifest.json')
                captured=now().isoformat();raw=directory/'cache/operational-source-v2'/policy['_policy_sha256']/'daily'/source_asof[:10]
                raw_refs=[]
                for name in names:
                    raw_refs.extend([future.binding(raw/'raw'/name),future.binding(raw/'raw'/(name+'.receipt.json'))])
                source_receipt=dict(schema_version='genuine-hosted-source-readback-v1',actual_execution_asof=source_asof,actual_source_and_feature_capture_completed_at=captured,
                    manifest=manifest_ref,namespace=manifest['namespace'],original_source_cache=str(raw),original_raw_body_receipt_bindings=raw_refs,
                    training_features=feature_ref,training_rows=len(train),training_seasons=sorted(map(int,train.season.unique())),
                    source_contract=config['source_contract'],allowed_periods=build.allowed_periods(),source_attempts=budget.attempts,source_roundtrips=budget.roundtrips,
                    HTTP='ORIGINAL_DOWNLOADER_ONLY_19_OFFICIAL_URLS',upstream_publication='NOT_INFERRED',old_artifact_reproduction=False)
                storage.atomic_json(directory/'SOURCE_READBACK.json',source_receipt)
            phase='TRAIN18';storage.model_anchor=storage.snapshot()['physical_bytes']
            trained=build.train18(train,categories,future=future,storage=storage,output=directory,source_contract=config['source_contract'],
                source_bindings=[feature_ref,manifest_ref,future.binding(directory/'BUILD_REGISTRATION.json')],source_completed_at=captured,check=check,
                progress=lambda row:print(json.dumps(row,sort_keys=True),flush=True),report=trained)
            check()
    except BaseException as error:
        fatal=dict(phase=phase,error_type=type(error).__name__,code=error.args[0] if isinstance(error,build.BuildStop) and error.args else 'BUILD_PHASE_FAILED')
    finally:
        storage.model_anchor=None;stop.set();watcher.join(timeout=.5)
    state='SOURCE_AND_TRAIN18_COMPLETE' if fatal is None and trained and all(s['state']=='NEW_OPERATIONAL_ARTIFACT_EXPORTED' for s in trained['slots']) else 'BUILD_PARTIAL_OR_FAILED_RETAINED'
    result=dict(schema_version=build.VERSION,state=state,phase=phase,fatal=fatal,source=source_receipt,training=trained,actual_completed_at_utc=now().isoformat(),
        source_sha=env['GITHUB_SHA'],registration=registration,execution_lane='github_actions',genuine_job=client.job,control_API_calls=client.calls,
        source_attempts=budget.attempts,source_roundtrips=budget.roundtrips,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,
        memory_sampling=memory,runtime_libc=libc,environment=future.environment(),new_operational_model_build=True,old_model_reproduction=False,
        scoring=0,searches=0,forecasts_issued=0,private_remote_persistence='NOT_YET_PERFORMED',model_restore_bit_acceptance='PENDING',scientific_qualification=False)
    storage.atomic_json(directory/'FINISHED.json',result)
    return dict(state=state,receipt_sha256=sha(read(directory/'FINISHED.json',2<<20)),new_fits_reserved=trained['new_logical_fits_reserved'] if trained else None,
        model_artifacts=sum(s['state']=='NEW_OPERATIONAL_ARTIFACT_EXPORTED' for s in trained['slots']) if trained else 0,
        source_attempts=budget.attempts,source_roundtrips=budget.roundtrips,scores=0,forecasts_issued=0,private_durability_qualified=False)


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args(argv)
    if not args.execute:print('{"state":"HOSTED_FIXED_BUILD_PREPARATION_ONLY_NO_IO"}');return 2
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(600,600));resource.setrlimit(resource.RLIMIT_AS,(4294967296,4294967296))
        def expired(*unused):raise GuardStop('WHOLE_BUILD_WALL')
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,1200)
        config=verify_sources();registration=preflight(os.environ,config)
        result=run_build(os.environ,config,registration);print(json.dumps(result,sort_keys=True));return 0 if result['state']=='SOURCE_AND_TRAIN18_COMPLETE' else 1
    except BaseException:
        print('{"state":"HOSTED_FIXED_BUILD_FAILED_RETAINED","scores":0,"forecasts_issued":0,"private_durability_qualified":false}');return 1


if __name__=='__main__':raise SystemExit(main())
