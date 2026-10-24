"""Root-reviewed metadata plan generation; no credentials, HTTP or ML imports."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime,timezone
from importlib import metadata
import json
import os
from pathlib import Path
import resource
import re
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/hosted-initial-plan-builder-v1.json'


def require(value,code):
    if not value:raise ValueError(code)


def run(env,procedure_sha256,*,recovery_v2=False):
    sys.path.insert(0,str(ROOT))
    from nfl_lab import hosted_initial_plan_builder_v1 as b
    from nfl_lab.initial_horizon import resolve
    route=resolve(recovery_v2);initial=route.adapter();version=route.builder_version
    from nfl_lab import gha_private_checkpoint as cp,private_draft_store as core
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab.owned_reference_batch import validate_owned_references
    from nfl_lab.hosted_fixed_build_v1 import allowed_periods
    from tools.private_draft_store_v2 import actions_context
    from tools.weekly_current_inference_capture import interpreter_invocation_identity,validate_interpreter_binding
    now=datetime.now(timezone.utc)
    def pin(path,cap=2<<20):
        path=core.parents_safe(path);body=core.read_local(path,cap)
        return dict(path=str(path),bytes=len(body),sha256=core.sha(body))
    def public(name,cap=2<<20):return cp.strict_json(cp.read_ref(pin(ROOT/name,cap),cap))
    config_path=ROOT/route.builder_config_path if recovery_v2 else CONFIG
    procedure_ref=pin(config_path);require(procedure_ref['sha256']==procedure_sha256,'EXACT_REVIEWED_BUILDER_PROCEDURE_SHA')
    config=public(config_path.relative_to(ROOT));require(config['schema_version']==version+'-procedure'
        and config['state']=='ROOT_APPROVED_METADATA_BUILDER' and config['budgets']==dict(CPU_seconds=20,wall_seconds=30,address_space_bytes=512<<20,
            HTTP=0,children=0,fits=0,scores=0,model_decodes=0,generated_plans=1,retries=0,metadata_bytes=1<<20),'APPROVED_METADATA_ONLY_PROCEDURE_REQUIRED')
    for name,expected in config['source_sha256'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and pin(ROOT/name)['sha256']==expected,'BUILDER_SOURCE_PIN_CHANGED')
    require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==core.REPO and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
        and env.get('GITHUB_RUN_ATTEMPT')=='1' and env.get('GITHUB_JOB')=='genuine-hosted-fixed-build-restore-v1'
        and env.get('STORE_PERMISSION')=='write'
        and env.get('GITHUB_ACTOR')=='NickNicky19' and env.get('GITHUB_ACTOR_ID')=='208912933','ACTUAL_SAME_RESTORE_JOB_CONTEXT_REQUIRED')
    job=actions_context(env,'write')  # Checkout identity only; no token discovery/API.
    for name,value in config['numerical_environment'].items():require(env.get(name)==value,'EXACT_INFERENCE_NUMERICAL_STARTUP')
    text=env.get('INITIAL_PLAN_BUILDER_GO_JSON','');go_sha=env.get('INITIAL_PLAN_BUILDER_GO_SHA256','')
    require(len(text.encode())<=16384 and core.sha(text.encode())==go_sha,'EXACT_BUILDER_GO_BODY_HASH')
    go=cp.strict_json(text);require(core.canonical(go).decode()==text,'CANONICAL_BUILDER_GO_REQUIRED')
    registration_ref=pin(ROOT/route.registration_path);registration=public(route.registration_path)
    registration_sha=core.sha(core.canonical(registration))
    if not recovery_v2:require(registration_sha==b.REGISTRATION_SHA,'ACTUAL_UNCHANGED_INITIAL_REGISTRATION')
    initial.validate_registration(registration,now=now)
    b.verify_go(go,procedure_sha256=procedure_sha256,source_sha=env['GITHUB_SHA'],now=now,
        recovery_v2=recovery_v2,registration_sha256=registration_sha)
    event=cp.strict_json(core.read_local(env['GITHUB_EVENT_PATH'],256<<10))
    require(event.get('inputs',{}).get('mode')=='genuine-hosted-fixed-build-v1'
        and event['inputs'].get('inference_builder_go_json')==text and event['inputs'].get('inference_builder_go_sha256')==go_sha
        and event.get('repository',{}).get('full_name')==core.REPO,'EXACT_OWNER_DISPATCH_BUILDER_APPROVAL_REQUIRED')
    checkpoint=public(route.checkpoint_config_path);checkpoint['_sha256']=pin(ROOT/route.checkpoint_config_path)['sha256']
    require(checkpoint['state']=='ROOT_APPROVED_FOR_GENUINE_GHA','REVIEWED_CHECKPOINT_PROCEDURE_REQUIRED')
    actual=public(checkpoint['canary_report']);checkpoint['_runtime_binding']=actual['binding']
    require(core.sha(core.canonical(actual['binding']))==checkpoint['binding_sha256']
        and core.sha(core.canonical(actual['qualification']))==checkpoint['qualification_sha256'],'EXACT_QUALIFIED_RUNTIME_METADATA')
    build_config=public(route.build_config_path);checkpoint['_source_contract']=build_config['source_contract']
    if recovery_v2:
        checkpoint['_build_config_sha256']=pin(ROOT/route.build_config_path)['sha256']
        require(build_config['initial_registration_canonical_sha256']==checkpoint['initial_registration_canonical_sha256']==registration_sha,
            'SAME_REGISTERED_RECOVERY_BUILD_AND_CHECKPOINT_REQUIRED')
    checkpoint['_environment']={n:metadata.version(n) for n in build_config['environment_versions']}
    require(checkpoint['_environment']==build_config['environment_versions'],'ACTUAL_FULL_FIXED18_RUNTIME_REQUIRED')
    def code_fields(relative):
        tree=ast.parse(core.read_local(ROOT/'nfl_lab'/relative,2<<20))
        values=[ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='CODE_FILES' for t in node.targets)]
        require(len(values)==1 and all(isinstance(n,str) and Path(n).name==n for n in values[0]),'EXACT_SOURCE_CODE_FILE_TUPLE')
        return {n:pin(ROOT/'nfl_lab'/n)['sha256'] for n in values[0]}
    checkpoint['_numeric_code_pins']=code_fields('weekly_future_inference.py')
    checkpoint['_source_code_pins']=code_fields('operational_sources.py')
    checkpoint['_allowed_periods']={str(y):weeks for y,weeks in allowed_periods().items()}
    checkpoint['source_freshness_seconds']=config['source_freshness_seconds']
    root=core.parents_safe(Path(env['RUNNER_TEMP'])/('genuine-hosted-fixed-build-restore-v1-'+env['GITHUB_RUN_ID']))
    require(root.is_dir() and (root/'cache/operational-storage-v2/registry.json').is_file(),'EXISTING_RESTORE_OWNED_QUOTA_REQUIRED')
    policy=public('config/operational-source-policy-v2.json');require(pin(ROOT/'config/operational-source-policy-v2.json')['sha256']==cp.POLICY_SHA,'UNCHANGED_E7_POLICY')
    storage=OperationalStorage(root/'cache',policy,state=root/'state')
    restore_ref=pin(root/'private-checkpoint-restore/RESTORE_FINISHED.json');validate_owned_references(storage,{restore_ref['path']:restore_ref['sha256']})
    restored=cp.strict_json(cp.read_ref(restore_ref));pre_refs=[b.basic(r) for r in restored['path_mapping'].values()]
    pre_refs.extend(b.basic(m['manifest']) for m in restored['models'])
    require(len(pre_refs)==96,'FIXED78_PLUS18_MANIFEST_METADATA_SCOPE')
    validate_owned_references(storage,{r['path']:r['sha256'] for r in pre_refs})
    approved={r['path']:r for r in pre_refs}
    def read_owned(ref):
        require(b.basic(ref)==approved.get(ref['path']) and Path(ref['path']).name.endswith('.json'),'CLOSED_OWNED_METADATA_READ_ONLY')
        return cp.strict_json(cp.read_ref(b.basic(ref),1<<20))
    process=core.process_identity()
    validated=b.validate_restore(restored,restore_ref=restore_ref,root=root,config=checkpoint,source_sha=env['GITHUB_SHA'],run_id=env['GITHUB_RUN_ID'],
        workflow_ref=job['workflow_ref'],process_identity=process,now=now,read=read_owned,registration=registration,recovery_v2=recovery_v2)
    validate_owned_references(storage,{r['path']:r['sha256'] for r in validated['owned_inputs']})
    slate=initial.prepare_initial_slate(b.schedule_metadata(cp.read_ref(validated['schedule'])),registration,registration_ref,now=now)
    invocation=interpreter_invocation_identity(sys.executable);interpreter=pin(invocation['resolved_path'],64<<20)
    libc=Path('/usr/lib/x86_64-linux-gnu/libc.so.6').resolve(strict=True);libc_ref=pin(libc,8<<20)
    catalog=b.catalog_metadata(list(zip(validated['artifacts'],validated['records'])),registered_at=restored['actual_completed_at'])
    startup_ref=pin(ROOT/'config/weekly-provisional-live-policy-v1.json');require(startup_ref['sha256']==registration['startup_policy_sha256'],'UNCHANGED_STARTUP_POLICY')
    output=root/('initial-plan-builder-v'+str(route.version));inference_output=root/('initial-inference-v'+str(route.version))
    with storage.transaction():
        require(not output.exists() and not inference_output.exists(),'ONE_METADATA_GENERATION_NO_RETRY')
        anchor=storage.snapshot()['physical_bytes'];storage._require(b.generic.LIMITS['new_bytes'])
        storage.register_root(output)
        storage.write_bytes(output/'BUILDER_GO.json',text.encode());go_ref=pin(output/'BUILDER_GO.json')
        storage.atomic_json(output/'CATALOG.json',catalog);catalog_ref=pin(output/'CATALOG.json')
        authority=dict(schema_version=version,authority_kind='ROOT_APPROVED_METADATA_BUILDER',procedure=procedure_ref,root_GO=go_ref,
            root_GO_sha256=go_sha,independent_review_receipt_sha256=go['independent_review_receipt_sha256'],individual_generated_plan_human_review=False,
            actual_generated_at_utc=now.isoformat(),source_sha=env['GITHUB_SHA'],run_id=env['GITHUB_RUN_ID'],process_identity=process,
            original_restore=restore_ref,original_build=validated['build'],API_authenticated_same_job_predecessor=restored['restorer'],
            current_process_API_authentication='NOT_ATTEMPTED_METADATA_ONLY',model_decodes=0,HTTP=0,fits=0,scores=0)
        plan=dict(schema_version=b.generic.VERSION,state='FROZEN_ROOT_REVIEWER_SEALED',execution_authorized=True,budgets=dict(b.generic.LIMITS),HTTP=0,
            review=dict(status='PREEXEC_PASS',integrator='/root',reviewer=go['reviewer'],authority_kind='ROOT_APPROVED_METADATA_BUILDER',
                reviewed_procedure_sha256=procedure_sha256,independent_review_receipt_sha256=go['independent_review_receipt_sha256'],generated_plan_individually_reviewed=False),
            generation_authority=authority,model_boundary=b.generic.MODEL_BOUNDARY,export_boundary=b.generic.EXPORT_BOUNDARY,
            source_mode='ADOPT_VERIFIED_CACHE',source_policy=pin(ROOT/'config/operational-source-policy-v2.json'),source_contract=checkpoint['_source_contract'],
            source_cache=validated['source_cache'],source_bindings=validated['source_bindings'],source_freshness_seconds=config['source_freshness_seconds'],
            cache=str(root/'cache'),state_root=str(root/'state'),output_root=str(inference_output),retention_physical_anchor=anchor,
            history_seasons=list(range(2019,2027)),allowed_periods=checkpoint['_allowed_periods'],schedule=validated['schedule'],roster=validated['roster'],
            artifacts=validated['artifacts'],selector_catalog=catalog_ref,startup_policy=startup_ref,slate=slate,
            initial_adapter=dict(schema_version=initial.VERSION,registration=registration_ref),history_bundle=None,previous_choices=None,frozen_weekly_choice=None,reference_forecasts=None,
            owned_inputs=[*validated['owned_inputs'],catalog_ref,go_ref],code_pins=dict(config['source_sha256'],**{str(config_path.relative_to(ROOT)):procedure_sha256}),
            interpreter=interpreter,interpreter_invocation=invocation,libc=libc_ref,rss_sampler=pin(ROOT/'tools/review_direct_booster_screen_guard_v4.py'),numerical_environment=config['numerical_environment'])
        b.generic.validate_plan(plan,now=now);initial.validate_plan(plan,now=now);validate_interpreter_binding(plan)
        encoded=core.canonical(plan);require(len(encoded)+len(core.canonical(catalog))+len(text.encode())<1<<20,'FINITE_METADATA_PLAN_BYTES')
        storage.write_bytes(output/'PLAN.json',encoded);plan_ref=pin(output/'PLAN.json')
        storage.atomic_json(output/'PLAN_GENERATED.json',dict(schema_version=version,state='STRICT18_INITIAL_METADATA_PLAN_GENERATED',plan=plan_ref,
            catalog=catalog_ref,generation_authority=authority,actual_metadata_persist_completed_at=datetime.now(timezone.utc).isoformat(),model_decodes=0,HTTP=0,fits=0,scores=0))
    return dict(state='STRICT18_INITIAL_METADATA_PLAN_GENERATED',plan_sha256=plan_ref['sha256'],catalog_sha256=catalog_ref['sha256'],source_sha=env['GITHUB_SHA'],models=18,HTTP=0,fits=0,scores=0,model_decodes=0)


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--procedure-sha256')
    parser.add_argument('--recovery-v2',action='store_true');args=parser.parse_args(argv)
    if not args.execute:print('{"state":"INITIAL_PLAN_BUILDER_PREPARATION_ONLY_NO_IO"}');return 2
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(20,20));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20));signal.alarm(30)
        def audit(event,unused):
            if event.startswith(('socket.','subprocess.')) or event in {'os.fork','os.forkpty','os.exec','os.system','os.posix_spawn','pickle.find_class'}:raise ValueError('METADATA_ONLY_NO_NETWORK_CHILDREN_MODEL_DECODE')
        sys.addaudithook(audit)
        expected=args.procedure_sha256 or json.loads(os.environ.get('INITIAL_PLAN_BUILDER_GO_JSON','{}')).get('procedure_sha256')
        result=run(os.environ,expected,recovery_v2=args.recovery_v2);print(json.dumps(result,sort_keys=True))
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as stream:stream.write('plan_sha256='+result['plan_sha256']+'\n')
        return 0
    except Exception as error:
        reason=getattr(error,'code',str(error));reason=reason if re.fullmatch('[A-Z0-9_]{1,100}',reason) else 'METADATA_BUILDER_FAILED'
        print(json.dumps(dict(state='INITIAL_PLAN_BUILDER_FAILED_RETAINED',reason=reason,HTTP=0,fits=0,scores=0,model_decodes=0),sort_keys=True));return 1


if __name__=='__main__':raise SystemExit(main())
