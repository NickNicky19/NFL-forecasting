"""Separately sealed opaque freeze/owner-upload/GHA-restore/relocation operations.

Help/preparation does no input, credential or network I/O. No operation creates,
edits or publishes a release, writes an owner comment, retries a POST or fits.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_lab import private_draft_store as core,owner_bootstrap_bundle as bundle,owner_private_bootstrap as owner

PHASES=('freeze','upload','restore','relocate')
INPUTS={'freeze':{'binding','qualification','rights'},'upload':{'manifest'},'restore':{'descriptor'},'relocate':{'relocation_pairs'}}
GO_KEYS={'schema_version','approved','phase','repository','plan_sha256','source_sha','code_pins_sha256','input_sha256',
    'root_manifest_sha256','comment_id','bundle_index','output_root','local_cache','local_state','single_writer_group'}


def load(path,maximum=1<<20):
    return json.loads(core.read_local(path,maximum))


def checkout_head(root):
    """Read only HEAD/ref metadata; never discover credentials or spawn git."""
    git=Path(root)/'.git'
    if git.is_file():
        text=core.read_local(git,4096).decode().strip()
        if not text.startswith('gitdir: '):raise core.StoreError('CHECKOUT_SOURCE_IDENTITY')
        git=Path(text[8:]);git=git if git.is_absolute() else Path(root)/git
    common=git
    if (git/'commondir').exists():
        target=core.read_local(git/'commondir',4096).decode().strip();common=Path(os.path.abspath(git/target))
    head=core.read_local(git/'HEAD',4096).decode().strip()
    if core.re.fullmatch(r'[a-f0-9]{40}',head):return head
    if not core.re.fullmatch(r'ref: refs/heads/[A-Za-z0-9_./-]+',head):raise core.StoreError('CHECKOUT_SOURCE_IDENTITY')
    ref=head[5:]
    if '..' in Path(ref).parts:raise core.StoreError('CHECKOUT_SOURCE_IDENTITY')
    if (common/ref).exists():return core.read_local(common/ref,4096).decode().strip()
    for line in core.read_local(common/'packed-refs',2<<20).decode().splitlines():
        if line.endswith(' '+ref) and core.re.fullmatch(r'[a-f0-9]{40}',line[:40]):return line[:40]
    raise core.StoreError('CHECKOUT_SOURCE_IDENTITY')


def store_for(plan,go):
    from nfl_lab.operational_storage import OperationalStorage
    # Local private paths are provenance only; hosted checkout supplies identical policy bytes.
    policy_path=Path(__file__).resolve().parents[1]/'config/operational-source-policy-v2.json'
    raw=core.read_local(policy_path,16384);policy=json.loads(raw)
    if core.sha(raw)!=plan['source_policy']['sha256']:raise core.StoreError('SOURCE_POLICY_HASH')
    storage=OperationalStorage(go['local_cache'],policy,state=go['local_state'])
    with storage.transaction():
        storage._require(1<<20)
        root=storage.register_root(go['output_root'])
    return storage,root


def main(argv=None,*,environ=None,transport=None):
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=PHASES);parser.add_argument('--execute',action='store_true')
    for name in ('plan','plan-sha256','go','go-sha256','binding','qualification','rights','manifest','descriptor','relocation-pairs'):
        parser.add_argument('--'+name)
    args=parser.parse_args(argv)
    if not args.execute:
        print(json.dumps(dict(state='PREPARATION_ONLY_NO_IO',execution_lane='UNSTARTED',private_durability_qualified=False)));return 2
    client=None
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
        signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(180)
        plan_body=core.read_local(args.plan,1<<20);go_body=core.read_local(args.go,256<<10)
        if core.sha(plan_body)!=args.plan_sha256 or core.sha(go_body)!=args.go_sha256:raise core.StoreError('EXACT_PLAN_AND_GO_HASH')
        plan=json.loads(plan_body);go=json.loads(go_body)
        if (set(go)!=GO_KEYS or go['schema_version']!='weekly-owner-bootstrap-GO-v1' or go['approved'] is not True or go['phase']!=args.phase
            or go['repository']!=core.REPO or go['plan_sha256']!=args.plan_sha256 or go['single_writer_group']!='nfl-lab-single-writer'
            or go['code_pins_sha256']!=core.sha(core.canonical(plan['code_pins'])) or set(go['input_sha256'])!=INPUTS[args.phase]
            or not owner.store_hashes(go['input_sha256']) or not core.re.fullmatch(r'[a-f0-9]{40}',go['source_sha'])):
            raise core.StoreError('SEPARATE_EXACT_OPERATION_GO_REQUIRED')
        if plan['schema_version']!='weekly-owner-private-bootstrap-plan-v1' or plan['source_policy']['sha256']!='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441':
            raise core.StoreError('BOOTSTRAP_PLAN_SCHEMA')
        for name,value in plan['numerical_environment'].items():
            if os.environ.get(name)!=value:raise core.StoreError('TWO_THREAD_ALLOCATOR_STARTUP_REQUIRED')
        root=Path(__file__).resolve().parents[1]
        if checkout_head(root)!=go['source_sha']:raise core.StoreError('ACTUAL_CHECKOUT_HEAD_REQUIRED')
        for name,expected in plan['code_pins'].items():
            bundle.logical(name)
            if core.sha(core.read_local(root/name,2<<20))!=expected:raise core.StoreError('BOOTSTRAP_CODE_CHANGED')
        inputs={}
        for name in INPUTS[args.phase]:
            body=core.read_local(getattr(args,name),1<<20)
            if core.sha(body)!=go['input_sha256'][name]:raise core.StoreError('EXACT_PHASE_INPUT_HASH')
            inputs[name]=json.loads(body)
        # Explicitly bound output roots; nothing may inherit an old /workspace path on GHA.
        for field in ('output_root','local_cache','local_state'):core.parents_safe(go[field])
        if args.phase in {'freeze','upload'} and (go['local_cache']!=plan['cache'] or go['local_state']!=plan['state_root']):
            raise core.StoreError('ORIGINAL_OWNER_STORE_REQUIRED')
        storage,output=store_for(plan,go)
        operation_key=args.phase+('-'+str(go['bundle_index']) if args.phase in {'upload','restore'} else '')
        consumed=output/(operation_key+'-CONSUMED.json')
        if consumed.exists():raise core.StoreError('ONE_OPERATION_NO_RETRY')
        storage.write_bytes(consumed,core.canonical(dict(phase=args.phase,GO_sha256=args.go_sha256,source_sha=go['source_sha'],model_decodes=0)))
        from nfl_lab.owned_reference_batch import validate_owned_references
        if args.phase in {'freeze','upload'}:
            bundle.validate_files(plan['files'])
            validate_owned_references(storage,{f['path']:f['sha256'] for f in plan['files']})
        if args.phase=='freeze':
            if go['comment_id'] is not None or go['bundle_index'] is not None or go['root_manifest_sha256'] is not None:
                raise core.StoreError('FREEZE_PRECEDES_COMMENT')
            def deny(event,unused):
                if event.startswith(('socket.','subprocess.')) or event in {'os.fork','os.exec','os.system','os.posix_spawn'}:raise core.StoreError('FREEZE_NO_HTTP_OR_CHILDREN')
            sys.addaudithook(deny)
            result=bundle.freeze(plan['files'],binding=inputs['binding'],qualification=inputs['qualification'],rights=inputs['rights'],source_sha=go['source_sha'],code_pins=plan['code_pins'])
            owner.validate_root(result);storage.write_bytes(output/'ROOT_MANIFEST.json',core.canonical(result))
            storage.write_bytes(output/'OWNER_COMMENT_EXACT_BODY.txt',owner.authorization_body(result).encode())
        elif args.phase=='upload':
            manifest=owner.validate_root(inputs['manifest'])
            if (core.sha(core.canonical(manifest))!=go['root_manifest_sha256'] or manifest['source_sha']!=go['source_sha']
                or manifest['source_code_pins']!=plan['code_pins']):raise core.StoreError('FROZEN_ROOT_CHANGED')
            index=go['bundle_index'];core.positive(go['comment_id'])
            if type(index) is not int or not 0<=index<len(manifest['bundles']):raise core.StoreError('FROZEN_BUNDLE_INDEX')
            record=manifest['bundles'][index]
            # No path can enter via a substituted root manifest outside the owned whitelist.
            approved={f['logical_path']:f for f in plan['files']}
            if any(approved.get(f['logical_path'])!=f for p in manifest['bundles'] for f in p['files']):raise core.StoreError('OWNED_WHITELIST_CHANGED')
            body,inflated=bundle.encode(record['files'])
            if (len(body),core.sha(body),inflated)!=(record['bytes'],record['sha256'],record['inflated_bytes']):raise core.StoreError('EXACT_REGENERATION_REQUIRED')
            journal=output/'owner-POST-journal'
            # Root passes the SAME registered output root for distinct bundle invocations.
            if not journal.exists():journal.mkdir(mode=0o700)
            env=os.environ if environ is None else environ
            client=owner.OwnerBootstrapClient(env.get('GH_TOKEN'),journal=journal,source_sha=go['source_sha'],transport=transport,reservation_storage=storage)
            result=owner.upload_one(client,manifest,index,go['comment_id'],body)
            storage.write_bytes(output/('OWNER_DESCRIPTOR_'+str(index)+'.json'),core.canonical(result))
        elif args.phase=='restore':
            from tools.private_draft_store_v2 import actions_context
            env=os.environ if environ is None else environ
            if (env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_REPOSITORY')!=core.REPO or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch'
                or env.get('GITHUB_RUN_ATTEMPT')!='1' or env.get('GITHUB_SHA')!=go['source_sha'] or env.get('STORE_PERMISSION')!='write'):
                raise core.StoreError('GENUINE_GHA_RESTORE_CONTEXT')
            job=actions_context(env,'write');journal=output/'restore-journal';journal.mkdir(mode=0o700)
            client=core.Client(env.get('GITHUB_TOKEN'),env.get('GITHUB_RUN_ID'),journal=journal,source_sha=go['source_sha'],job=job,transport=transport,operation='restore')
            body,record,result=owner.restore_owner_bundle(client,inputs['descriptor'],expected_root_sha256=go['root_manifest_sha256'],expected_comment_id=go['comment_id'])
            result['extraction']=bundle.extract_owned(body,record,storage,output/'files')
        else:
            pairs=inputs['relocation_pairs']
            if not isinstance(pairs,list) or not 1<=len(pairs)<=18:raise core.StoreError('MAX18_RELOCATIONS')
            result=dict(schema_version='weekly-owner-bootstrap-relocations-v1',artifacts=[],model_decodes=0)
            for index,pair in enumerate(pairs):
                if set(pair)!={'original_manifest','model'}:raise core.StoreError('CLOSED_RELOCATION_PAIR')
                result['artifacts'].append(bundle.relocate_future_manifest(pair['original_manifest'],pair['model'],output/('relocated-'+str(index)),storage))
        storage.write_bytes(output/(operation_key+'-FINISHED.json'),core.canonical(dict(state='COMPLETE',phase=args.phase,result=result,
            execution_lane='OWNER_BOOTSTRAP' if args.phase=='upload' else 'github_actions' if args.phase=='restore' else 'LOCAL_OPAQUE_ENGINEERING',
            model_decodes=0,fits=0,public_payload_export=False,private_durability_qualified=False)))
        print(json.dumps(dict(state='COMPLETE',phase=args.phase,receipt_sha256=core.sha(core.canonical(result)),HTTP_calls=client.calls if client else 0,
            transfer_bytes=client.transferred if client else 0,model_decodes=0,private_durability_qualified=False)));return 0
    except Exception as error:
        print(json.dumps(dict(state='FAILED_RETAINED',reason=error.code if isinstance(error,core.StoreError) else 'BOOTSTRAP_FAILED',
            HTTP_calls=client.calls if client else 0,private_durability_qualified=False)));return 1


if __name__=='__main__':raise SystemExit(main())
