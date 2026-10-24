"""Job4 metadata release plan; one pinned archived GET, no token discovery."""
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
CONFIG=ROOT/'config/hosted-public-release-plan-v1.json'


def require(v,code):
    if not v:raise ValueError(code)
def read(path,cap):
    path=Path(path);require(path.is_file() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents) and path.stat().st_size<=cap,'BUILDER_SOURCE_BOUND')
    body=path.read_bytes();require(len(body)<=cap,'BUILDER_SOURCE_BOUND');return body
def sha(body):return hashlib.sha256(body).hexdigest()


def run(env,procedure_sha256,*,transport=None):
    # Source/procedure identity is checked before importing shared CAS hooks or
    # reading private inputs. No credential is requested by this builder.
    body=read(CONFIG,1<<20);require(sha(body)==procedure_sha256,'EXACT_PUBLIC_PLAN_PROCEDURE');config=json.loads(body)
    require(config['schema_version']=='weekly-hosted-public-release-plan-procedure-v1' and config['state']=='ROOT_APPROVED_METADATA_BUILDER'
        and config['budgets']==dict(CPU_seconds=15,wall_seconds=30,address_space_bytes=512<<20,archived_board_GETs=1,board_bytes=4<<20,retries=0,children=0,model_decodes=0),'PUBLIC_PLAN_PROCEDURE_PENDING')
    for name,expected in config['source_sha256'].items():require(not Path(name).is_absolute() and '..' not in Path(name).parts and sha(read(ROOT/name,2<<20))==expected,'PUBLIC_PLAN_SOURCE_PIN')
    sys.path.insert(0,str(ROOT))
    from nfl_lab import public_release_plan_v1 as b,private_draft_store as s,gha_private_checkpoint as cp
    from nfl_lab.operational_storage import OperationalStorage
    from tools.private_draft_store_v2 import actions_context
    require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==s.REPO and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and env.get('GITHUB_RUN_ATTEMPT')=='1'
        and env.get('GITHUB_JOB')=='genuine-hosted-selected-export-v1' and env.get('STORE_PERMISSION')=='write' and env.get('GITHUB_ACTOR')=='NickNicky19' and env.get('GITHUB_ACTOR_ID')=='208912933'
        and re.fullmatch('[1-9][0-9]{0,19}',env.get('GITHUB_RUN_ID','')),'ACTUAL_PUBLIC_EXPORT_JOB_REQUIRED')
    job=actions_context(env,'write')  # Checkout identity only; inherited proof below supplies prior API auth.
    text=env.get('PUBLIC_RELEASE_GO_JSON','');go_sha=env.get('PUBLIC_RELEASE_GO_SHA256','');require(len(text.encode())<=48<<10,'PUBLIC_GO_BOUND')
    go=cp.strict_json(text);event=cp.strict_json(read(env['GITHUB_EVENT_PATH'],256<<10));at=b.now()
    registration=b.validate_go(go,procedure_sha256=procedure_sha256,source_sha=env['GITHUB_SHA'],event=event,go_text=text,go_sha=go_sha,at=at)
    require(go['policy']['publication_authority']['source_branch']==env['GITHUB_REF'].removeprefix('refs/heads/'),'EXACT_REGISTERED_SOURCE_BRANCH')
    source_path=ROOT/'config/operational-source-policy-v2.json';raw=read(source_path,1<<20);require(sha(raw)==cp.POLICY_SHA,'EXACT_E7_POLICY_BYTES');policy=cp.strict_json(raw)
    root=s.parents_safe(Path(env['RUNNER_TEMP'])/('genuine-hosted-selected-export-v1-'+env['GITHUB_RUN_ID']));require(root.is_dir(),'EXISTING_JOB4_CACHE_REQUIRED')
    storage=OperationalStorage(root/'cache',policy,state=root/'state');storage.register_root(root)
    handoff_ref=cp.binding(root/'selected-private-consume/EXPORT_INPUTS_RELOCATED.json')
    from nfl_lab.owned_reference_batch import validate_owned_references
    validate_owned_references(storage,{handoff_ref['path']:handoff_ref['sha256']});inputs=cp.strict_json(cp.read_ref(handoff_ref,1<<20))
    source_ref=dict(path=str(source_path),bytes=len(raw),sha256=sha(raw));getter=b.BoardGET(transport)
    context=dict(source_sha=env['GITHUB_SHA'],run_id=env['GITHUB_RUN_ID'],job=job,process_identity=s.process_identity(),season=registration['initial_registration']['season'],week=registration['initial_registration']['week'])
    ref=b.build_plan(inputs,go=go,storage=storage,root=root,output=root/'public-release-plan-v1',context=context,source_policy_ref=source_ref,board_get=getter,at=at)
    return ref['sha256']


def main(argv=None,*,environ=None,transport=None):
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--procedure-sha256');args=p.parse_args(argv)
    if not args.execute:print('{"state":"PUBLIC_RELEASE_PLAN_PREPARATION_ONLY"}');return 2
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(15,15));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20));signal.alarm(30)
        env=os.environ if environ is None else environ
        expected=args.procedure_sha256 or json.loads(env.get('PUBLIC_RELEASE_GO_JSON','{}')).get('procedure_sha256')
        result=run(env,expected,transport=transport);print('PUBLIC_RELEASE_PLAN_SHA256='+result)
        if env.get('GITHUB_OUTPUT'):
            with open(env['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:stream.write('plan_sha256='+result+'\n')
        return 0
    except Exception as error:
        reason=getattr(error,'code',str(error));reason=reason if isinstance(reason,str) and re.fullmatch('[A-Z0-9_]{1,90}',reason) else 'PUBLIC_RELEASE_PLAN_FAILED_RETAINED'
        print(json.dumps(dict(state='PUBLIC_RELEASE_PLAN_FAILED_RETAINED',reason=reason,public_export_authorized=False)));return 1


if __name__=='__main__':raise SystemExit(main())
