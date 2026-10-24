"""One root-sealed current inference/capture; no fits, scoring or acquisition."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time
import traceback
import threading


class CaptureResourceStop(BaseException):
    pass



def interpreter_invocation_identity(invocation):
    """Only the interpreter has this explicit, fully bound symlink contract."""
    path=Path(invocation)
    if not path.is_absolute() or str(path)!=os.path.abspath(path) or any(p.is_symlink() for p in path.parents):
        raise ValueError('canonical interpreter invocation and nonsymlink parents required')
    chain=[];seen=set()
    while path.is_symlink():
        if str(path) in seen or len(chain)>=8:raise ValueError('invalid interpreter link chain')
        seen.add(str(path));info=path.lstat();target=os.readlink(path)
        chain.append(dict(path=str(path),readlink=target,device=info.st_dev,inode=info.st_ino,mode=info.st_mode,
            bytes=info.st_size,mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns))
        path=Path(target) if os.path.isabs(target) else Path(os.path.abspath(path.parent/target))
    resolved=path.resolve(strict=True)
    if path!=resolved or any(p.is_symlink() for p in resolved.parents) or not stat.S_ISREG(resolved.lstat().st_mode):
        raise ValueError('canonical resolved regular interpreter target required')
    return dict(path=invocation,symlink_chain=chain,resolved_path=str(resolved))


def validate_interpreter_binding(plan,*,actual_executable=None):
    from tools.weekly_current_query import pin
    # Unchanged strict source pin accepts ONLY the canonical nonsymlink target.
    pin(plan['interpreter'])
    expected=plan['interpreter_invocation']
    actual=sys.executable if actual_executable is None else actual_executable
    if actual!=expected['path'] or interpreter_invocation_identity(actual)!=expected:
        raise ValueError('exact venv invocation or interpreter link identity changed')
    if expected['resolved_path']!=plan['interpreter']['path']:
        raise ValueError('interpreter link resolves to an unregistered target')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True,type=Path);parser.add_argument('--plan-sha256',required=True)
    args=parser.parse_args();body=args.plan.read_bytes()
    if hashlib.sha256(body).hexdigest()!=args.plan_sha256:raise ValueError('exact frozen inference plan required')
    plan=json.loads(body)
    if plan['schema_version']!='weekly-current-inference-capture-v1' or plan['state']!='FROZEN_ROOT_REVIEWER_SEALED' or plan['review'].get('status')!='PREEXEC_PASS' or plan['review'].get('integrator')!='/root':
        raise ValueError('preparation is not current inference execution authority')
    caps=plan['budgets']
    if not(0<caps['CPU_seconds']<=180 and 0<caps['wall_seconds']<=180 and caps['RSS_bytes']==1073741824 and caps['address_space_bytes']==4294967296 and caps['RSS_monitor_threads']==1
        and caps['model_restores']==18 and caps['max_prediction_rows']==18000 and caps['max_query_rows']==1000
        and caps['fits']==caps['scores']==caps['HTTP']==caps['children']==caps['automatic_retries']==0
        and caps['invocations']==1 and caps['new_output_bytes']<=8388608 and caps['cumulative_current_track_bytes']==33554432):
        raise ValueError('finite18model/no-fit/no-score/no-HTTP inference caps required')
    if plan['cutoff_utc']!='2026-10-24T12:00:00Z' or plan['retention_physical_anchor']!=464099131 or plan['slate_id']!='2026-REG-W07-remaining-initial-v1':
        raise ValueError('fixed current input cutoff and existing conservative root anchor required')
    for name,value in plan['numerical_environment'].items():
        if os.environ.get(name)!=value:raise ValueError('numerical/allocator environment must be set before interpreter start')
    resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']))
    resource.setrlimit(resource.RLIMIT_AS,(caps['address_space_bytes'],caps['address_space_bytes']))
    def expire(*unused):raise CaptureResourceStop('fixed current-inference wall ceiling')
    signal.signal(signal.SIGALRM,expire);signal.setitimer(signal.ITIMER_REAL,caps['wall_seconds'])
    def audit(event,unused):
        if event.startswith(('socket.','subprocess.')) or event in {'os.fork','os.forkpty','os.system','os.exec','os.posix_spawn'}:
            raise RuntimeError('current inference cannot acquire or create child processes')
    sys.addaudithook(audit)
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));started=time.monotonic();cpu=time.process_time()
    # Metadata checks precede pandas, model objects, or shared feature decoding.
    from tools.weekly_current_query import pin,study_storage_class
    for name,value in plan['code_pins'].items():pin(dict(path=str(root/name),sha256=value))
    for name in ('source_policy','model_metadata','inherited_environment_attestation','environment_preflight','interpreter','libc','rss_sampler','startup_policy'):
        pin(plan[name])
    validate_interpreter_binding(plan)
    sampler_spec=importlib.util.spec_from_file_location('inference_existing_pid_sampler',plan['rss_sampler']['path'])
    sampler=importlib.util.module_from_spec(sampler_spec);sampler_spec.loader.exec_module(sampler)
    process=sampler.process_binding(os.getpid());memory=dict(samples=0,sampled_peak_bytes=0,highwater_bytes=0)
    stop=threading.Event()
    def sample_memory():
        rss,_=sampler.required_usage([process]);highwater=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        memory['samples']+=1;memory['sampled_peak_bytes']=max(memory['sampled_peak_bytes'],rss);memory['highwater_bytes']=max(memory['highwater_bytes'],highwater)
        if max(rss,highwater)>=caps['RSS_bytes']-33554432:raise MemoryError('unchanged1GiB physical RSS stop margin')
    def watch():
        while not stop.wait(.01):
            try:sample_memory()
            except BaseException:
                os.write(2,b'{"state":"INFERENCE_RSS_OR_ACCOUNTING_STOP","private_values":false}\n');os.kill(os.getpid(),signal.SIGKILL)
    sample_memory();watcher=threading.Thread(target=watch,name='inference-existing-rss-sampler',daemon=True);watcher.start()
    from nfl_lab import weekly_current_inference as current,weekly_future_inference as future
    if not current.utc(plan['registered_at'])<=current.utc(plan['weekly_decision_cutoff_utc'])<=future.now_utc()<current.utc(plan['cutoff_utc']):
        raise ValueError('actual registration/startupchoice must precede actual issuance; no future12Zdecision fiction')
    startup=current.read_metadata(plan['startup_policy'])
    registered=current.validate_startup_policy(startup,plan['weekly_decision_cutoff_utc'],future.now_utc())
    if plan['registered_at']!=registered:raise ValueError('actual policy registration clock must be preserved')
    records=[]
    for slot in plan['models']:
        m=current.read_metadata(slot['artifact']);records.append(dict(binding=slot['artifact'],manifest=m,eligible_roles=slot['eligible_roles']))
    current.validate_manifests(records,plan['source_contract'])
    if len({current.digest(dict(features=r['manifest']['features'],roles=r['eligible_roles'])) for r in records})>7:
        raise ValueError('finite seven shared-projection contracts required')
    if any(r['manifest']['code_pins']!=future.code_pins() or r['manifest']['environment']!=future.environment() for r in records):
        raise ValueError('authentic trained code/environment changed')
    query_result=current.read_metadata(plan['query_result']);terminal=current.read_metadata(plan['query_terminal'])
    if query_result['state']!='CURRENT_QUERY_CAPTURED_NOT_ISSUED' or terminal['state']!='CURRENT_QUERY_CAPTURED_NOT_ISSUED' or query_result['source_contract']!=plan['source_contract']:
        raise ValueError('successful real current-query source capture required')
    if query_result['feature_binding']!=plan['shared_features'] or query_result['capture_binding']!=plan['feature_capture']:
        raise ValueError('root-sealed same shared source snapshot required')
    if query_result.get('preserved_queries')!=plan['queries']:raise ValueError('feature-only V3 must reuse exact V2 queries')
    population=current.read_metadata(plan['population']);readback=current.read_metadata(plan['source_readback'])
    if query_result['coverage']!=population or any(population.get(k)!=v for k,v in dict(retained_weekly_skill_rows=708,offered_rows=610,quarantined_rows=54,no_remaining_game_rows=44,remaining_games=13,elapsed_games=1).items()):
        raise ValueError('all708population states and initial13game remaining slate required')
    if not current.utc(readback['actual_execution_asof'])<=current.utc(readback['actual_readback_completed_at'])<current.utc(plan['cutoff_utc']):raise ValueError('genuine original source readback clocks required')
    capture=current.read_metadata(plan['feature_capture'])
    import pandas as pd
    import pyarrow as pa
    import threadpoolctl
    pa.set_cpu_count(2);pa.set_io_thread_count(2);pa.set_memory_pool(pa.system_memory_pool())
    from nfl_lab.operational_sources import load_source_policy
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab.owned_reference_batch import validate_owned_references
    policy=load_source_policy(plan['source_policy']['path'])
    storage=study_storage_class(OperationalStorage)(plan['cache'],policy,state=plan['state_root'],
        study_anchor=plan['retention_physical_anchor'],study_bytes=caps['cumulative_current_track_bytes'])
    with storage.transaction():
        usage=storage.snapshot()['physical_bytes']
        if usage<plan['retention_physical_anchor']:raise ValueError('old failed/concurrent retained bytes disappeared')
        OperationalStorage._require(storage,caps['cumulative_current_track_bytes']-(usage-plan['retention_physical_anchor']))
        output=storage.register_root(plan['output_root'])
        sink=current.BoundedOutput(storage,output,caps['new_output_bytes'])
        if (output/'CONSUMED.json').exists():raise ValueError('one current inference invocation already consumed')
        sink.atomic_json(output/'CONSUMED.json',dict(invocations=1,retries=0,plan_sha256=args.plan_sha256,
            started_at=future.now_utc().isoformat(),fits=0,scores=0,correction_fit_reservations_consumed=0))
    input_refs=[plan[k] for k in ('query_result','query_terminal','queries','shared_features','feature_capture','schedule','query_quarantine','query_no_remaining','population','source_readback','source_parent_terminal')]
    input_refs+=plan['training_receipts']+plan['restore_receipts']+capture['source_bindings']
    unique={b['path']:b for b in input_refs}
    fatal=None;capture_result=None;models_prepared=False;session=None
    def progress():
        if future.now_utc()>=current.utc(plan['cutoff_utc']):raise TimeoutError('actual issuance/persistence cutoff elapsed')
        sample_memory()
        used=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
        if used+262144>caps['new_output_bytes']:raise RuntimeError('new inference namespace byte ceiling; preserve partials')
    spec=importlib.util.spec_from_file_location('current_inference_existing_thread_resolver',root/'tools/ngboost_law_software_v1.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    try:
        validate_owned_references(storage,{b['path']:b['sha256'] for b in unique.values()})
        if len(plan['training_receipts'])!=2 or len(plan['restore_receipts'])!=2:raise ValueError('exact V3/V4 training and restore provenance required')
        declared_all=set()
        for index,(terminal_ref,restore_ref) in enumerate(zip(plan['training_receipts'],plan['restore_receipts'])):
            train=current.read_metadata(terminal_ref);restored=current.read_metadata(restore_ref)
            if restored['state']!='FRESH_PROCESS_REPLAY_PASS' or restored['training_receipt_sha256']!=terminal_ref['sha256']:
                raise ValueError('authentic17+1 fresh-process restoration receipts required')
            declared={s['artifact']['sha256'] for s in train['slots'] if s['state']=='FUTURE_ARTIFACT_EXPORTED'}
            if len(declared)!=(17 if index==0 else 1) or restored['artifacts']!=len(declared):raise ValueError('exact17+1 successful exported/restore slots required')
            declared_all.update(declared)
        if declared_all!={r['binding']['sha256'] for r in records}:raise ValueError('registered18 must equal exact17+1 genuine trained slots')
        progress()
        import pyarrow.parquet as pq
        columns=pq.ParquetFile(plan['shared_features']['path']).schema_arrow.names
        if not all(n in future.IDENTITY+['feature_max_source_available_utc'] or n.startswith('f_') for n in columns):
            raise ValueError('sealed shared snapshot may contain only identity/sourceclock/feature columns, no labels')
        features=pd.read_parquet(plan['shared_features']['path'],columns=columns)
        queries=pd.read_parquet(plan['queries']['path'],columns=current.BRIDGE_COLUMNS)
        current.validate_shared_snapshot(features,queries,capture,feature_binding=plan['shared_features'],source_contract=plan['source_contract'])
        if len(queries)!=610 or queries.game_id.nunique()!=13:raise ValueError('exact original610future offers/13remaining games required')
        schedule=pd.read_csv(plan['schedule']['path'],usecols=current.SCHEDULE_COLUMNS)
        bridge=current.exact_bridge(queries,schedule,schedule_binding=plan['schedule'],query_binding=plan['queries'])
        bridge_doc=dict(schema_version=current.VERSION+'-identity-bridge',queries=plan['queries'],schedule=plan['schedule'],
            identities=list(bridge.values()),visible_board_match='NOT_YET_CHECKED',name_matching=False)
        sink.atomic_json(output/'IDENTITY_BRIDGE.json',bridge_doc)
        catalog=current.procedure_catalog(records,registered_at=plan['registered_at'],query_result_binding=plan['query_result'],source_contract=plan['source_contract'])
        sink.atomic_json(output/'PROCEDURE_CATALOG.json',catalog)
        with guard.process_free_threads(threadpoolctl,plan['libc']),threadpoolctl.threadpool_limits(limits=2):
            session=future.FutureInferenceSession.from_storage(storage)
            session.prepare([r['binding'] for r in records]);models_prepared=True
            session._verify(list(unique.values()))
            projections,keys=current.projection_receipts(records,features,capture,plan['feature_capture'],storage=sink,output=output)
            session._verify([v['binding'] for v in projections.values()])
            progress()
            capture_result=current.capture_registered(session,records,features,bridge,projections,keys,storage=sink,output=output,
                context=dict(cutoff_utc=plan['cutoff_utc'],weekly_decision_cutoff_utc=plan['weekly_decision_cutoff_utc'],
                    slate_id=plan['slate_id'],source_contract=plan['source_contract'],evidence_lane='original_pregame',
                    reference_stream='candidate',query_source_sha256=plan['shared_features']['sha256'],
                    startup_policy_sha256=plan['startup_policy']['sha256'],startup_policy_registered_at=registered),
                max_rows=caps['max_prediction_rows'],max_bytes=caps['new_output_bytes'],batch_size=128,progress=progress)
            session.close();session=None
        progress()
        output_refs=[entry['persistence']['binding'] for entry in capture_result['models']]
        output_refs += [future.binding(Path(b['path']).with_suffix('.completion.json')) for b in output_refs]
        validate_owned_references(storage,{b['path']:b['sha256'] for b in output_refs})
        sink.atomic_json(output/'LOCAL_READBACK.json',dict(state='SAME_PROCESS_OWNED_IMMUTABLE_READBACK',
            at=future.now_utc().isoformat(),body_and_receipt_refs=output_refs,
            remote_durability='NOT_ESTABLISHED',fresh_process_restore='PENDING_SEPARATE_READBACK'))
    except BaseException as error:
        fatal=dict(type=type(error).__name__,message=str(error)[:500],traceback=traceback.format_exc()[-5000:])
    finally:
        if session is not None:
            try:session.close()
            except BaseException as error:
                if fatal is None:fatal=dict(type=type(error).__name__,message=str(error)[:500])
                else:fatal['close_error']=dict(type=type(error).__name__,message=str(error)[:500])
    status='FAILED_RETAINED' if fatal or capture_result and any(m['failure'] for m in capture_result['models']) else 'CURRENT_CANDIDATE_FORECASTS_LOCAL_READBACK'
    result=dict(schema_version=current.VERSION,state=status,plan_sha256=args.plan_sha256,fatal=fatal,capture=capture_result,
        models_restored_once=18 if models_prepared else None,source_result=plan['query_result'],shared_features=plan['shared_features'],
        original_feature_capture=plan['feature_capture'],input_cutoff_utc=plan['cutoff_utc'],startup_policy=plan['startup_policy'],
        startup_policy_registered_at=registered,weekly_decision_cutoff_utc=plan['weekly_decision_cutoff_utc'],
        actual_completed_at=future.now_utc().isoformat(),slate_kind='INITIAL_REMAINING_W7',historical_feature_availability_uncertain=True,
        historical_feature_availability_rule=plan['source_contract']['availability_rule'],upstream_publication='NOT_INFERRED',HTTP=0,fits=0,scores=0,scientific_qualification=False,
        remote_durability='NOT_ESTABLISHED',website_published=False,policy_selection='SEPARATE_FROZEN_PROCEDURE_DECISION_REQUIRED',
        CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,
        RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        physical_bytes_above_existing_root_anchor=storage.snapshot()['physical_bytes']-plan['retention_physical_anchor'])
    stop.set();watcher.join(timeout=.5)
    if watcher.is_alive():raise RuntimeError('required RSS sampler did not stop')
    sample_memory();result['memory_sampling']=memory
    sink.atomic_json(output/'FINISHED.json',result);signal.setitimer(signal.ITIMER_REAL,0)
    print(json.dumps({k:result[k] for k in ('state','CPU_seconds','wall_seconds','HTTP','fits','scores')}))
    return 1 if status=='FAILED_RETAINED' else 0


if __name__=='__main__':raise SystemExit(main())
