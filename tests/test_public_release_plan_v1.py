"""Fictional metadata only: no actual HTTP, token, NFL value or model work."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import public_release_plan_v1 as b,private_draft_store as s,weekly_durable_acceptance as a,gha_private_checkpoint as cp
from nfl_lab.operational_storage import OperationalStorage
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from test_owner_private_bootstrap import qualification
from tools import hosted_public_release_plan_v1 as cli

ROOT=Path(__file__).resolve().parents[1]


class ReleasePlanChecks(unittest.TestCase):
    def setUp(self):
        class FictionalWindowClock(datetime):
            @classmethod
            def now(cls,tz=None):return datetime(2026,10,24,14,tzinfo=timezone.utc)
        for target in ('test_owner_private_bootstrap.datetime','nfl_lab.private_draft_store.datetime'):
            clock=patch(target,FictionalWindowClock);clock.start();self.addCleanup(clock.stop)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.policy_source=json.loads((ROOT/'config/operational-source-policy-v2.json').read_bytes());self.storage=OperationalStorage(self.root/'cache',self.policy_source,state=self.root/'state');self.storage.register_root(self.root)
        # Fictional historical clock; this never extends live one-use authority.
        self.stamp=datetime(2026,10,24,14,tzinfo=timezone.utc);stamp=lambda seconds:(self.stamp+timedelta(seconds=seconds)).isoformat();self.at=stamp(0)
        journal=self.root/'journal';journal.mkdir(mode=0o700);server=Server();client=s.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,transport=server,process='e'*64);runtime=s.initialize(client,'b'*32);q=qualification(runtime)
        workflow=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional';identity=lambda role,n:dict(execution_lane='github_actions',repository=s.REPO,run_id=RUN,run_attempt=1,source_sha=SOURCE,process_identity=str(n)*64,job_id=role,api_job_id=n,permission='write',workflow_ref=workflow)
        producer=identity('genuine-hosted-fixed-build-restore-v1',4);restorer=identity('genuine-hosted-selected-restore-v1',5);physical=identity('genuine-hosted-selected-export-v1',6)
        self.context=dict(source_sha=SOURCE,run_id=RUN,process_identity='7'*64,season=2026,week=7,job=dict(execution_lane='github_actions',workflow_ref=workflow,workflow_sha=SOURCE,job_id=physical['job_id'],permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False))
        selected=self.write('selected.gz',body=gzip.compress(b'{"FICTIONAL_ONLY":true}\n',mtime=0));original=dict(selected,path='/FICTIONAL_ORIGINAL/selected.gz');completion=dict(state='PERSISTED',binding=original)
        consumed_ref=self.write('CONSUMED.json',dict(schema_version='weekly-generic-future-producer-v1',at=stamp(-180),invocations=1,retries=0))
        policy=deepcopy(json.loads((ROOT/'config/weekly-derived-selected-policy-v2.json').read_bytes()));policy['state']='ROOT_REGISTERED';policy['publication_authority'].update(state='ROOT_REGISTERED',source_sha=SOURCE,source_branch='fictional')
        for entries in policy['procedures'].values():
            for entry in entries:entry['procedure_version']='b'*64
        catalog=dict(schema_version=b.feed.CATALOG_V2,rows=[dict(category=t,method_id=e['method_id'],procedure_version=e['procedure_version'],model_version='a'*64) for t,entries in policy['procedures'].items() for e in entries],current_values_used=False,public_policy_registration='REQUIRED_SEPARATELY; not automatic approval')
        cat_ref=self.write('CATALOG.json',catalog)
        terminal=dict(selected=completion,actual_completed_at=stamp(-120),selected_version_catalog=cat_ref)
        terminal_ref=self.write('TERMINAL.json',terminal)
        proof=dict(schema_version='weekly-selected-packager-provenance-v2',identity=producer,terminal_sha256=terminal_ref['sha256'],selected_sha256=selected['sha256'],bytes=selected['bytes'],producer_policy_sha256=policy['producer_policy_sha256'],source_policy_sha256=cp.POLICY_SHA,started_at_utc=stamp(-90),created_at_utc=stamp(-80),inference_consumed_ref=consumed_ref,inference_consumed_at=stamp(-180))
        def restore(ident,start,end):
            job=dict(execution_lane='github_actions',workflow_ref=workflow,workflow_sha=SOURCE,job_id=ident['job_id'],permission='write',event_name='workflow_dispatch',api_job_id=ident['api_job_id'],run_authenticated=True)
            return dict(schema_version='weekly-private-proof-v2.1',phase='restore',operation='restore',repository=s.REPO,run_id=RUN,run_attempt=1,started_at_utc=stamp(start),created_at_utc=stamp(end),source_sha=SOURCE,binding_sha256=a.digest(runtime),config_sha256=s.config_sha(),process_identity=ident['process_identity'],job=job,HTTP_calls=10,transfer_bytes=1000,exact_readback=True,payload_sha256=selected['sha256'],bytes=selected['bytes'],separate_process=True,draft_before_after=True)
        r3=restore(restorer,-70,-60);r4=restore(physical,-40,-30);durable=dict(runtime_binding=runtime,qualification_proof=q,restore_proof=r3)
        canary=dict(schema_version='weekly-canary-platform-acceptance-v1',authority_kind='ROOT_VERIFIED',state='COMPLETED_SUCCESS_VERIFIED',qualified_proof_sha256=a.digest(q),runtime_binding_sha256=a.digest(runtime),run_id=q['run_id'],run_attempt=1,source_sha=q['source_sha'],workflow_sha256='a'*64,verified_at=stamp(-600),jobs=[dict(job_id=p['job']['job_id'],api_job_id=p['job']['api_job_id'],permission=p['job']['permission'],run_status='completed',run_conclusion='success',status='completed',conclusion='success') for p in [q['before_proof'],q['read_proof'],q]])
        policy['root_verified_canary_acceptances']=[a.digest(canary)]
        board_body=s.canonical(dict(season=2026,week=7,games=[],players=[]));self.board_body=board_body
        rights=dict(schema_version='weekly-selected-derived-rights-authority-v1',state='ROOT_REGISTERED',authority_kind='ROOT_APPROVED_DERIVED_PUBLICATION',source_policy_sha256=cp.POLICY_SHA,scope='SELECTED_DERIVED_ONLY',public_fields=policy['public_fields'],source_review_sha256='c'*64,basis='FICTIONAL derived-only authority, no upstream blanket grant',upstream_blanket_grant=False,public_raw_or_model_weights=False,human_approval=False)
        r0=dict(schema_version='weekly-actual-r0-freeze-v1',state='ACTUAL_FIRST_RELEASE_R0_FROZEN',engine_sha256=policy['engine_sha256'],visible_board_sha256=s.sha(board_body),frozen_at=stamp(-600),extra_provenance='FICTIONAL_PRESERVED')
        policy['rights_authorities']=[a.digest(rights)];policy['r0_identities']=[a.digest(r0)]
        policy['durability_verifier_procedures']=[dict(schema_version='weekly-durable-verifier-procedure-v1',source_sha=SOURCE,verifier_sha256=s.sha(Path(a.__file__).read_bytes()),workflow_sha256='a'*64,producer_job=producer['job_id'],restorer_job=restorer['job_id'],export_job=physical['job_id'],permissions={r:dict(contents='write',actions='read') for r in ['producer','restorer','export']})]
        self.go=dict(schema_version=b.VERSION+'-GO',state='ROOT_APPROVED_DERIVED_PUBLICATION',authority_kind='ROOT_APPROVED_PROCEDURE',repository=s.REPO,source_sha=SOURCE,procedure_sha256='d'*64,review_sha256='c'*64,root_ledger_sha256='e'*64,registered_at_utc=stamp(-300),input_cutoff_utc='2026-10-24T15:00:00Z',policy=policy,rights_authority=rights,r0=r0,canary_acceptance=canary,board=dict(url='https://raw.githubusercontent.com/NickNicky19/nicks-expert-nfl-picks/'+'f'*40+'/output/data/week.json',sha256=s.sha(board_body),bytes=len(board_body),captured_at=stamp(-600)))
        self.inputs=dict(schema_version='weekly-selected-private-snapshot-v1-restored-inputs',candidates_retained=18,public_export_authorized=False,selected=selected,producer_proof=self.write('PACKAGER.json',proof),terminal=terminal_ref,completion=self.write('COMPLETION.json',completion),decision=self.write('DECISION.json',{}),parent_capture=self.write('PARENT.json',{}),bridge=self.write('BRIDGE.json',{}),startup_policy=self.write('STARTUP.json',{}),procedure_catalog=self.write('PROCEDURE.json',{}),selected_version_catalog=cat_ref,inference_consumed=consumed_ref,durability=self.write('DURABILITY.json',durable),selected_relocation=self.write('RELOCATION.json',dict(physical_restore_proof=r4,restored_selected=selected,original_selected=original)),selected_snapshot_index=self.write('INDEX.gz',body=gzip.compress(b'{}',mtime=0)))
        build=dict(schema_version='genuine-hosted-fixed-build-registration-v1',approved=True,repository=s.REPO,source_sha=SOURCE,scope='SOURCE_AND_TRAIN_FIXED18_ONLY',maximum_new_fits=18,registered_at_utc=stamp(-240),initial_registration=dict(season=2026,week=7))
        self.text=s.canonical(self.go).decode();self.go_sha=s.sha(self.text.encode());text=s.canonical(build).decode();self.event=dict(repository=dict(full_name=s.REPO),inputs=dict(mode='genuine-hosted-fixed-build-v1',public_release_go_json=self.text,public_release_go_sha256=self.go_sha,build_registration_json=text,build_registration_sha256=s.sha(text.encode())))
    def tearDown(self):self.tmp.cleanup()
    def write(self,name,doc=None,body=None):
        p=self.root/name;self.storage.write_bytes(p,s.canonical(doc) if body is None else body);return cp.binding(p)
    def validate(self,go=None,event=None):return b.validate_go(go or self.go,procedure_sha256='d'*64,source_sha=SOURCE,event=event or self.event,go_text=self.text,go_sha=self.go_sha,at=self.at)
    def test_exact_existing_exporter_inputs_and_unchanged_R0(self):
        self.validate();getter=b.BoardGET(lambda *_:Response(self.board_body));ref=b.build_plan(self.inputs,go=self.go,storage=self.storage,root=self.root,output=self.root/'out',context=self.context,source_policy_ref=cp.binding(ROOT/'config/operational-source-policy-v2.json'),board_get=getter,at=self.at)
        plan=cp.strict_json(cp.read_ref(ref));self.assertEqual(plan['schema_version'],'weekly-public-feed-export-plan-v1');self.assertEqual(getter.calls,1);self.assertEqual(plan['selected'],self.inputs['selected']);self.assertEqual(plan['durability_authority'],'ROOT_APPROVED_PROCEDURE_VERIFIED')
        self.assertEqual(cp.strict_json(cp.read_ref(plan['r0'])),self.go['r0']);self.assertEqual(cp.strict_json(cp.read_ref(plan['rights']))['selected_sha256'],self.inputs['selected']['sha256']);self.assertIn('selected_version_catalog',plan)
    def test_bad_source_or_GO_after_source_registration_rejected(self):
        bad=deepcopy(self.go);bad['source_sha']='0'*40
        with self.assertRaises(s.StoreError):self.validate(go=bad)
        event=deepcopy(self.event);build=json.loads(event['inputs']['build_registration_json']);build['registered_at_utc']=(self.stamp-timedelta(minutes=10)).isoformat();text=s.canonical(build).decode();event['inputs'].update(build_registration_json=text,build_registration_sha256=s.sha(text.encode()))
        with self.assertRaisesRegex(s.StoreError,'BEFORE_SOURCE'):self.validate(event=event)
    def test_unpinned_live_URL_and_corrupt_body_stop_before_decode(self):
        for url in ['https://example.invalid/week.json',self.go['board']['url'].replace('f'*40,'main')]:
            with self.assertRaises(s.StoreError):b.archive_url(url)
        getter=b.BoardGET(lambda *_:Response(b'not-json-corrupt'))
        with self.assertRaisesRegex(s.StoreError,'EXACT_BYTES'):getter(self.go['board'])
        with self.assertRaisesRegex(s.StoreError,'NO_RETRY'):getter(self.go['board'])
    def test_unsafe_rights_scope_rejected(self):
        go=deepcopy(self.go);go['rights_authority']['upstream_blanket_grant']=True
        text=s.canonical(go).decode();event=deepcopy(self.event);event['inputs'].update(public_release_go_json=text,public_release_go_sha256=s.sha(text.encode()))
        with self.assertRaisesRegex(s.StoreError,'RIGHTS_AUTHORITY'):b.validate_go(go,procedure_sha256='d'*64,source_sha=SOURCE,event=event,go_text=text,go_sha=s.sha(text.encode()),at=self.at)
    def test_preparation_reads_no_environment_or_network(self):
        class NoEnv:
            def get(self,*a):raise AssertionError('context/credential read')
        self.assertEqual(cli.main([],environ=NoEnv(),transport=lambda *_:(_ for _ in ()).throw(AssertionError('GET'))),2)


if __name__=='__main__':unittest.main()
