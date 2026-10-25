"""Fictional metadata only: no actual provider HTTP, raw NFL bytes, models or fits."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from nfl_lab import weekly_initial_continuation_v3 as cont,weekly_initial_remaining_v2 as old
from nfl_lab import initial_horizon as horizons,weekly_generic_producer as generic,weekly_inference_diagnostics_v1 as diag
from nfl_lab import hosted_initial_plan_builder_v1 as builder,private_draft_store as core,gha_private_checkpoint as cp
from nfl_lab.state import digest,utc
from tools import weekly_generic_future_producer as cli,weekly_continuation_source_cache_v3 as prep_cli
from tools import gha_private_checkpoint_v1 as checkpoint_cli

ROOT=Path(__file__).resolve().parents[1]
NOW=utc('2026-10-24T21:30:00Z')
SOURCE='c'*40


class Clock(datetime):
    @classmethod
    def now(cls,tz=None):return NOW


def registration():
    initial=json.loads((ROOT/'config/weekly-initial-remaining-v2-registration.json').read_text())
    parent=dict(run_id='40129209279',source_sha='a'*40,producer_job_id='genuine-hosted-fixed-build-v1',producer_api_job_id=120977111674,
        workflow_ref=core.REPO+'/.github/workflows/lab.yml@refs/heads/fictional-parent',checkpoint_procedure_sha256='4'*64,
        build_config_sha256='5'*64,initial_registration_sha256=cont.ORIGINAL_REGISTRATION_SHA,
        failed_inference_api_job_id=120977667174,failed_inference_forecast_counts=None)
    parent['handoff']=dict(schema_version=cp.VERSION+'-handoff',repository=core.REPO,procedure_sha256=parent['checkpoint_procedure_sha256'],
        source_sha=parent['source_sha'],run_id=parent['run_id'],runtime_binding={},index_descriptor=dict(entry=dict(writer_run_id=parent['run_id'],payload=dict(sha256='e'*64))))
    return dict(schema_version=cont.REGISTRATION,registration_id=cont.REGISTRATION_ID,state='ROOT_REGISTERED_ZERO_FIT_CONTINUATION',repository=core.REPO,
        registered_at_utc='2026-10-24T20:41:00Z',input_cutoff_utc=cont.CUTOFF,maximum_uses=1,maximum_new_fits=0,source_acquisitions=0,source_claims=0,
        scientific_qualification=False,initial_registration=initial,parent=parent)


def prepared():
    return dict(schema_version='weekly-continuation-source-cache-v3',state='OWNED_ORIGINAL_HISTORY_CACHE_PREPARED',
        continuation_origin_sha256=digest(registration()),source_sha=SOURCE,run_id='40000000006',source_contract={'source_policy_sha256':cp.POLICY_SHA},
        policy_sha256=cp.POLICY_SHA,allowed_periods={'2026':[1,2,3,4,5]},original_receipts_relabelled=False,
        original_source_bindings=[dict(path='/fictional/raw/body',bytes=3,sha256='f'*64)],parent_capture_completed_at='2026-10-24T20:00:00Z',
        asof_utc='2026-10-24T21:00:00Z',actual_completed_at='2026-10-24T21:01:00Z',HTTP=0,fits=0,query_rows=0,forecasts=0,scores=0)


def validate_prep(p):
    return cont.validate_prepared_history(p,origin_sha256=digest(registration()),source_sha=SOURCE,run_id='40000000006',
        source_contract=prepared()['source_contract'],source_bindings=prepared()['original_source_bindings'],allowed_periods=prepared()['allowed_periods'],now=NOW)


class ContinuationChecks(unittest.TestCase):
    def test_distinct_zero_fit_authority_preserves_consumed_source_and_unknown_counts(self):
        r=registration();cont.validate_registration(r,now=NOW)
        self.assertEqual(digest(r['initial_registration']),cont.ORIGINAL_REGISTRATION_SHA)
        for field,value in [('maximum_new_fits',1),('source_claims',1),('source_acquisitions',1),('maximum_uses',2),('scientific_qualification',True),
                ('registered_at_utc','2026-10-24T19:00:00Z'),('input_cutoff_utc','2026-10-25T01:00:00Z')]:
            bad=deepcopy(r);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):cont.validate_registration(bad,now=NOW)
        bad=deepcopy(r);bad['parent']['failed_inference_forecast_counts']=0
        with self.assertRaises(ValueError):cont.validate_registration(bad,now=NOW)
        with self.assertRaises(ValueError):cont.validate_registration(r,now=utc(cont.CUTOFF))

    def test_typed_origin_exact_handoff_and_no_mutable_authority_substitution(self):
        r=registration();origin=cont.origin(r,now=NOW);origin.check_handoff(r['parent']['handoff'])
        with self.assertRaises(ValueError):origin.check_handoff({})
        r['parent']['source_sha']='b'*40
        with self.assertRaises(ValueError):origin.verify_unchanged()

    def test_original_and_recovery_routes_do_not_implicitly_select_continuation(self):
        self.assertIs(horizons.resolve(),horizons.ORIGINAL);self.assertIs(horizons.resolve(True),horizons.RECOVERY)
        self.assertIs(horizons.resolve(continuation_v3=True).adapter(),cont)
        with self.assertRaises(ValueError):horizons.resolve(True,continuation_v3=True)

    def test_source_cache_receipt_requires_current_identity_exact_old_sources_and_actual_clocks(self):
        validate_prep(prepared())
        for key,value in [('source_sha','b'*40),('fits',1),('HTTP',1),('query_rows',1),('forecasts',1),
                ('asof_utc','2026-10-24T19:00:00Z'),('actual_completed_at','2026-10-24T22:00:00Z'),('original_receipts_relabelled',True)]:
            p=prepared();p[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_prep(p)
        p=prepared();p['original_source_bindings'][0]['sha256']='e'*64
        with self.assertRaises(ValueError):validate_prep(p)
        self.assertEqual(generic.LIMITS['new_bytes'],16<<20)
        self.assertEqual(prep_cli.BUDGETS['new_retained_bytes'],64<<20)

    def test_new_slate_journal_is_distinct_with_same13_future_game_cutoffs(self):
        from test_weekly_initial_remaining_v1 import schedule
        ref=dict(path='/fictional/continuation.json',bytes=100,sha256='f'*64)
        slate=cont.prepare_initial_slate(schedule(),registration(),ref,now=NOW)
        self.assertEqual(set(slate['game_cutoffs'].values()),{old.CUTOFF});self.assertEqual(len(slate['game_cutoffs']),13)
        self.assertEqual(slate['slate_id'],cont.REGISTRATION_ID)
        self.assertEqual(slate['slate_contract']['original_source_slate_contract']['schema_version'],old.VERSION)
        self.assertIsNone(slate['slate_contract']['prior_failed_inference_forecast_counts'])

    def test_diagnostics_expose_only_constant_codes_and_fingerprints(self):
        secret='FICTIONAL_PRIVATE_ROW_PATH_OR_TOKEN'
        d=diag.safe_failure(ValueError(secret));encoded=json.dumps(d)
        self.assertNotIn(secret,encoded);self.assertEqual(d['guard_code'],'UNLISTED_ERROR_CODE');self.assertEqual(len(d['message_fingerprint']),64)
        d=diag.safe_failure(RuntimeError('finite additional retained source/query allocation exhausted'))
        self.assertEqual(d['guard_code'],'STUDY_RETAINED_BYTES_EXHAUSTED')
        with redirect_stdout(io.StringIO()):diag.checkpoint('FEATURES')
        result=dict(fatal=dict(type='ValueError',reason=secret))
        result['safe_diagnostic']=diag.summary(result=result)
        with redirect_stdout(io.StringIO()):diag.checkpoint('TERMINAL')
        d=diag.summary(result=result);self.assertEqual(d['phase'],'FEATURES');self.assertIsNone(d['selected_rows'])
        self.assertNotIn(secret,json.dumps(d))
        with self.assertRaises(ValueError):diag.checkpoint(secret)

    def test_outer_cli_failure_retains_default_raising_and_safe_opt_in_summary(self):
        error=ValueError('FICTIONAL_PRIVATE_VALUE')
        with patch.object(cli,'_main',side_effect=error),self.assertRaises(ValueError):cli.main()
        with patch.object(cli,'_main',side_effect=error),patch.dict(cli.os.environ,{},clear=True),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(diagnostics=True),1)
        self.assertNotIn('FICTIONAL_PRIVATE_VALUE',output.getvalue())

    def test_prepare_and_restore_forbid_claim_or_source_execution_in_continuation(self):
        class NoEnv:
            def get(self,*a):raise AssertionError('no preparation environment read')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(prep_cli.main([]),2)
            self.assertEqual(checkpoint_cli.main(['claim','--continuation-v3'],environ=NoEnv()),2)
        with patch.object(checkpoint_cli.resource,'setrlimit'),patch.object(checkpoint_cli.signal,'alarm'),\
                patch.object(checkpoint_cli,'verified',side_effect=AssertionError('no claim allowed')),redirect_stdout(io.StringIO()):
            self.assertEqual(checkpoint_cli.main(['claim','--execute','--continuation-v3'],environ=NoEnv()),1)

    def test_cross_run_builder_authenticates_old_producer_and_current_restorer_separately(self):
        from test_hosted_initial_plan_builder_v1 import fixture
        restored,kwargs,docs=fixture();r=registration();origin=cont.origin(r,now=NOW);p=r['parent']
        def shift(value):
            if isinstance(value,dict):return {k:shift(v) for k,v in value.items()}
            if isinstance(value,list):return [shift(v) for v in value]
            if isinstance(value,str) and value.startswith('2026-10-24T'):return (utc(value)+timedelta(hours=8)).isoformat()
            return value
        docs=shift(docs);restored=shift(restored)
        current_run=kwargs['run_id'];current_source=kwargs['source_sha'];current_workflow=kwargs['workflow_ref']
        restored.update(schema_version=cp.VERSION+'-continuation-restore-v3',continuation_origin_sha256=origin.registration_sha256,
            parent_origin=p,original_procedure_sha256=p['checkpoint_procedure_sha256'],actual_completed_at=NOW.isoformat())
        restored['original_producer'].update(run_id=p['run_id'],source_sha=p['source_sha'],workflow_ref=p['workflow_ref'],api_job_id=p['producer_api_job_id'])
        for proof in restored['proofs']:proof['created_at_utc']=NOW.isoformat()
        build_path=str(kwargs['root']/'private-checkpoint-restore/files/control/BUILD.json')
        docs[build_path]['source_sha']=p['source_sha'];docs[build_path]['genuine_job']['api_job_id']=p['producer_api_job_id']
        build_registration=dict(schema_version=old.BUILD_REGISTRATION,registration_id=old.BUILD_REGISTRATION_ID,approved=True,repository=core.REPO,
            source_sha=p['source_sha'],config_sha256=p['build_config_sha256'],registered_at_utc='2026-10-24T19:52:00Z',input_cutoff_utc=old.CUTOFF,
            training_cutoff_utc='2026-09-01T00:00:00Z',scope='SOURCE_AND_TRAIN_FIXED18_ONLY',maximum_new_fits=18,old_artifact_reproduction=False,
            scientific_qualification=False,initial_registration=r['initial_registration'],initial_registration_sha256=cont.ORIGINAL_REGISTRATION_SHA)
        docs[str(kwargs['root']/'private-checkpoint-restore/files/control/BUILD_REGISTRATION.json')]=build_registration
        kwargs.update(now=NOW,registration=r['initial_registration'],recovery_v2=True,continuation=origin,read=lambda ref:deepcopy(docs[ref['path']]))
        kwargs['config']['_build_config_sha256']=p['build_config_sha256']
        with patch.object(core,'datetime',Clock):result=builder.validate_restore(restored,**kwargs)
        self.assertEqual(len(result['artifacts']),18)
        wrong=deepcopy(restored);wrong['restorer']['source_sha']=p['source_sha']
        with patch.object(core,'datetime',Clock),self.assertRaises(ValueError):builder.validate_restore(wrong,**kwargs)
        wrong=deepcopy(restored);wrong['original_producer']['run_id']=current_run
        with patch.object(core,'datetime',Clock),self.assertRaises(ValueError):builder.validate_restore(wrong,**kwargs)
        unchanged=dict(kwargs);unchanged.pop('continuation')
        with patch.object(core,'datetime',Clock),self.assertRaises(ValueError):builder.validate_restore(restored,**unchanged)

    def test_opaque_restore_retains_parent_bodies_but_emits_genuine_current_proofs(self):
        from test_gha_private_checkpoint import CheckpointTests
        from test_private_draft_store_v2 import Response
        from nfl_lab.operational_storage import OperationalStorage
        case=CheckpointTests();case.setUp()
        try:
            handoff=case.produce();original_producer=case.factory.clients[0]
            current_run='40099999999';current_source='c'*40
            fresh=case.base/'continuation';fresh.mkdir();storage=OperationalStorage(fresh/'cache',case.policy,state=fresh/'state');storage.register_root(fresh)
            journal=fresh/'journal';journal.mkdir(mode=0o700)
            workflow=core.REPO+'/.github/workflows/lab.yml@refs/heads/fictional-current'
            def transport(request,timeout):
                if '/actions/runs/' in request.full_url:
                    if '/jobs?' in request.full_url:return Response(dict(total_count=1,jobs=[dict(id=778,name=case.config['restore_job'],status='in_progress',run_id=int(current_run),head_sha=current_source)]))
                    return Response(dict(id=int(current_run),head_sha=current_source,event='workflow_dispatch',run_attempt=1,status='in_progress',path='.github/workflows/lab.yml',
                        repository=dict(full_name=core.REPO),head_repository=dict(full_name=core.REPO)))
                return case.server(request,timeout)
            class Factory:
                last=None
                def __call__(self,operation):
                    job=dict(execution_lane='github_actions',workflow_ref=workflow,workflow_sha=current_source,job_id=case.config['restore_job'],permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
                    client=core.Client('ghs_FICTIONAL',current_run,journal=journal,source_sha=current_source,transport=transport,process='5'*64,job=job,operation=operation)
                    client.authenticate_actions_job();client.bind(case.runtime);self.last=client;return client
            parent=dict(handoff=handoff,producer_api_job_id=777,workflow_ref=original_producer.job['workflow_ref'],run_id=handoff['run_id'])
            lower_level_authority=dict(parent=parent);origin=cont.ContinuationOrigin(lower_level_authority,digest(lower_level_authority))
            config=dict(case.config,_sha256='7'*64)
            result=cp.restore(handoff,Factory(),config=config,storage=storage,output=fresh/'out',producer_api_job_id=777,continuation=origin)
            self.assertEqual(result['run_id'],current_run);self.assertEqual(result['source_sha'],current_source)
            self.assertEqual(result['original_producer']['run_id'],handoff['run_id']);self.assertEqual(result['original_producer']['source_sha'],handoff['source_sha'])
            self.assertEqual((result['files'],len(result['models']),result['model_decodes']),(78,18,0))
            self.assertTrue(all(p['run_id']==current_run and p['source_sha']==current_source for p in result['proofs']))
        finally:case.tearDown()

    @patch('test_owner_private_bootstrap.datetime',Clock)
    @patch.object(core,'datetime',Clock)
    @patch('datetime.datetime',Clock)
    def test_global_metadata_consumption_rejects_same_registration_before_second_extraction(self):
        from test_gha_private_checkpoint import ClaimGuardChecks
        from test_private_draft_store_v2 import Response
        fixture=ClaimGuardChecks();fixture.setUp()
        try:
            authority=cont.origin(registration(),now=NOW);extractions=[]
            def client(run,process):
                job_id='genuine-hosted-fixed-build-restore-v1'
                def transport(request,timeout):
                    if '/actions/runs/' in request.full_url:
                        if '/jobs?' in request.full_url:return Response(dict(total_count=1,jobs=[dict(id=55,name=job_id,status='in_progress',run_id=int(run),head_sha=SOURCE)]))
                        return Response(dict(id=int(run),head_sha=SOURCE,event='workflow_dispatch',run_attempt=1,status='in_progress',path='.github/workflows/lab.yml',repository=dict(full_name=core.REPO),head_repository=dict(full_name=core.REPO)))
                    return fixture.server(request,timeout)
                job=dict(execution_lane='github_actions',workflow_ref=core.REPO+'/.github/workflows/lab.yml@refs/heads/fictional-current',workflow_sha=SOURCE,
                    job_id=job_id,permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
                c=core.Client('ghs_FICTIONAL',run,journal=fixture.journal,source_sha=SOURCE,transport=transport,process=process,job=job,operation='restore')
                c.authenticate_actions_job();c.bind(fixture.runtime);return c
            def begin(c):
                receipt=cont.consume_metadata_once(c,authority,fixture.q)
                extractions.append('fictional extraction would begin only now')
                return receipt
            first=client('40099999998','4'*64)
            with patch.object(cont,'validate_registration',wraps=cont.validate_registration):receipt=begin(first)
            cont.validate_metadata_consumption(receipt,authority=authority,current_run=first.run_id,current_source=SOURCE,current_api_job_id=55)
            with self.assertRaisesRegex(core.StoreError,'APPEND_ONLY_NAME_EXISTS'):begin(client('40099999999','5'*64))
            self.assertEqual(len(extractions),1)
            self.assertEqual(sum(call.method=='POST' for call in fixture.server.calls),1)
            self.assertEqual(receipt['source_claims'],0);self.assertEqual(receipt['fits'],0)
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
