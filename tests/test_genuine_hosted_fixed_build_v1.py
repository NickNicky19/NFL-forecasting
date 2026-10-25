"""Fictional source-budget, chronology and fit orchestration; no real fits/HTTP."""
from contextlib import nullcontext,redirect_stdout
from copy import deepcopy
from datetime import datetime,timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from nfl_lab import hosted_fixed_build_v1 as b
from tools.weekly_future_train import training_columns
from retained_source_fixture import retained_procedure

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fictional_hosted_fixed_driver',ROOT/'tools/genuine_hosted_fixed_build_v1.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)


def training_fixture():
    rows=[]
    for year in (2019,2020,2025,2026):
        for period in ('REG','POST'):
            kickoff=pd.Timestamp(f'{year}-09-01T17:00:00Z')
            row=dict(season=year,week=1,game_id=f'fictional-{year}-{period}',player_id='fictional-QB',position='QB',team='A',opponent='B',
                kickoff_utc=kickoff,cutoff_utc=kickoff,outcome_available_utc=kickoff+pd.Timedelta(days=7),
                feature_max_source_available_utc=pd.Timestamp('2018-01-01T00:00:00Z'),participation_state='played',f_player_games_prior=1.,rush_td=0.,rec_td=0.)
            row.update({name:(-2. if name.endswith('_yd') else 0.) for name in b.TARGETS});rows.append(row)
    frame=pd.DataFrame(rows);schedule=frame[['season','game_id']].copy();schedule['game_type']=['REG','POST']*4
    return frame,schedule


class Store:
    def __init__(self):self.documents=[]
    def atomic_json(self,path,value):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));self.documents.append((path,deepcopy(value)))


class FakeFuture:
    cdf=SimpleNamespace(KEYS=['season','week','game_id','player_id'])
    def __init__(self,fail=None,double=False):self.fail=fail;self.double=double;self.calls=[];self.exports=[]
    @staticmethod
    def now_utc():return datetime(2026,10,24,12,tzinfo=timezone.utc)
    def fit_future_model(self,train,category,family,**kwargs):
        key=(category['target'],family);self.calls.append((key,kwargs['expected_native_version']))
        if key==self.fail:raise ValueError('FICTIONAL_TARGET_SOURCE_ISSUE')
        kwargs['fit_gate']({'family':family,'target':category['target']})
        if self.double:kwargs['fit_gate']({'family':family})
        return SimpleNamespace(category=category)
    def export_trained_artifact(self,path,model,**kwargs):
        path=Path(path);path.mkdir(parents=True);self.exports.append(kwargs)
        manifest=dict(model={'bytes':100},fit_receipt={'training_started_at':self.now_utc().isoformat()})
        target=path/'future-inference.json';target.write_text(json.dumps(manifest))
        return dict(path=str(target),bytes=target.stat().st_size,sha256=d.sha(target.read_bytes()))


class HostedFixedBuildChecks(unittest.TestCase):
    def setUp(self):self.config=json.loads((ROOT/'config/genuine-hosted-fixed-build-v1.json').read_text())

    def test_exact18_fixed_recipes_no_search_or_2026_training(self):
        jobs=b.jobs();self.assertEqual(len(jobs),18);self.assertEqual(jobs,self.config['jobs'])
        self.assertEqual([sum(j['family']==f for j in jobs) for f in ('leaf_cdf_base','count_A','catboost_medium')],[11,2,5])
        self.assertEqual(b.allowed_periods()[2026],[1,2,3,4,5]);self.assertNotIn('fantasy_ppr',{j['target'] for j in jobs})

    def test_REG_identity_earlier_seasons_signed_zero_unknown_and_primitive_TD_preserved(self):
        frame,schedule=training_fixture();frame.loc[frame.season.eq(2020),'participation_state']='unknown'
        selected=b.training_rows(frame,schedule)
        self.assertEqual(selected.season.tolist(),[2019,2020,2025]);self.assertTrue(selected.pass_yd.eq(-2).all());self.assertTrue(selected.pass_att.eq(0).all())
        self.assertIn('unknown',selected.participation_state.tolist())
        categories={t:dict(panels={'base':['f_player_games_prior']}) for t in b.TARGETS}
        columns=training_columns(categories,['season','week','game_id','player_id','position','team','opponent','kickoff_utc','cutoff_utc'])
        self.assertTrue({'rush_td','rec_td'}<=set(columns));self.assertTrue({'rush_td','rec_td'}<=set(selected))
        with self.assertRaises(ValueError):b.training_rows(frame,pd.concat([schedule,schedule]))

    def test_source19_URLs_attempts_charged_before_transport_and_no_credential_lookup(self):
        urls={f'fixture{i}':f'https://raw.githubusercontent.com/fictional/source{i}' for i in range(19)};records=[]
        budget=b.SourceBudget(urls,record=lambda i,r:records.append((i,r)),clock=lambda:0.)
        def request(session,method,url,**kwargs):
            self.assertEqual(len(records),budget.attempts);self.assertTrue(callable(kwargs['auth']));return 'fictional'
        for _ in range(60):self.assertEqual(budget.request(request,None,'GET',urls['fixture0']), 'fictional')
        self.assertEqual(len(records),60)
        with self.assertRaises(b.BuildStop):budget.request(request,None,'GET',urls['fixture0'])
        self.assertNotIn('https://',json.dumps(records));self.assertNotIn('token',json.dumps(records).lower())

    def test_source_foreign_URL_method_auth_headers_redirect_and_phase_forbidden(self):
        urls={f'f{i}':f'https://raw.githubusercontent.com/fictional/{i}' for i in range(19)};budget=b.SourceBudget(urls,record=lambda *a:None,clock=lambda:0.)
        for method,url,kwargs in [('POST',urls['f0'],{}),('GET','https://paid.invalid/nfl',{}),('GET',urls['f0'],{'auth':'forbidden'})]:
            with self.assertRaises(b.BuildStop):budget.request(lambda *a,**k:None,None,method,url,**kwargs)
        for url,headers in [('https://evil.invalid/file',{}),(urls['f0'],{'Authorization':'secret'}),(urls['f0'],{'Cookie':'secret'})]:
            with self.assertRaises(b.BuildStop):budget.send(lambda *a,**k:None,None,SimpleNamespace(url=url,method='GET',headers=headers))
        seen=[]
        def send(*args,**kwargs):seen.append(getattr(budget.local,'transport',False));return 1
        self.assertEqual(budget.send(send,None,SimpleNamespace(url=urls['f0'],method='GET',headers={})),1)
        self.assertEqual(seen,[True]);self.assertFalse(budget.local.transport)
        budget.phase=False
        with self.assertRaises(b.BuildStop):budget.request(lambda *a:None,None,'GET',urls['f0'])

    def test_native_deadline_requires_whole_packet_timer_and_restores_remaining_budget(self):
        with patch.object(b.signal,'getitimer',return_value=(0.,0.)),self.assertRaises(b.BuildStop):
            with b.hard_deadline(60):self.fail('missing whole timer admitted')
        with patch.object(b.signal,'getitimer',side_effect=[(100.,0.),(0.,0.)]),patch.object(b.signal,'getsignal',return_value='original'),\
                patch.object(b.signal,'signal') as handlers,patch.object(b.signal,'setitimer') as timers,patch.object(b.time,'monotonic',side_effect=[10.,12.]):
            with b.hard_deadline(60):pass
        self.assertEqual(timers.call_args_list[0].args,(b.signal.ITIMER_REAL,60))
        self.assertEqual(timers.call_args_list[-1].args,(b.signal.ITIMER_REAL,98.))
        self.assertEqual(handlers.call_args_list[0].args,(b.signal.SIGALRM,b.signal.SIG_DFL))

    def train(self,folder,backend,check=lambda:None,report=None):
        frame,schedule=training_fixture();train=b.training_rows(frame,schedule)
        categories={t:dict(target=t,modeled_roles=['QB']) for t in b.TARGETS};store=Store()
        result=b.train18(train,categories,future=backend,storage=store,output=folder,source_contract=self.config['source_contract'],
            source_bindings=[{'path':'fictional','sha256':'a'*64}],source_completed_at='2026-10-24T11:00:00Z',check=check,deadline=lambda seconds:nullcontext(),report=report)
        return result,store

    def test18_reservations_before_fitter_and_exact_future_export_not_old_model_reuse(self):
        backend=FakeFuture()
        with tempfile.TemporaryDirectory() as tmp:result,store=self.train(tmp,backend)
        self.assertEqual(result['new_logical_fits_reserved'],18);self.assertEqual(len(backend.calls),18);self.assertEqual(len(backend.exports),18)
        self.assertTrue(all(r['state']=='NEW_OPERATIONAL_ARTIFACT_EXPORTED' for r in result['slots']))
        self.assertEqual([version for (target,family),version in backend.calls if family=='catboost_medium'],['1.2.10']*5)
        self.assertFalse(result['old_model_hash_reproduction_claim']);self.assertEqual(result['scores'],0)
        self.assertEqual(len([p for p,v in store.documents if p.parent.name=='fit-reservations']),18)
        self.assertTrue(all(len(call['replay_fixture'])<=4 for call in backend.exports))

    def test_one_Cat_failure_retained_others_complete_no_substitute_or_retry(self):
        backend=FakeFuture(fail=('anytime_td','catboost_medium'))
        with tempfile.TemporaryDirectory() as tmp:result,_=self.train(tmp,backend)
        self.assertEqual(len(result['slots']),18);self.assertEqual(len(backend.calls),18);self.assertEqual(len(backend.exports),17)
        failed=[r for r in result['slots'] if r['state']=='FAILED_FIT_RETAINED_NO_RETRY'];self.assertEqual(len(failed),1)
        self.assertNotIn('artifact',failed[0]);self.assertEqual(failed[0]['target'],'anytime_td')

    def test_global_stop_keeps18_statuses_and_consumed_prefix_without_extra_fits(self):
        report=b.initial_training_report();calls=[]
        def stop():
            calls.append(1)
            if len(calls)==3:raise b.BuildStop('FICTIONAL_GLOBAL_BUDGET')
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(b.BuildStop):self.train(tmp,FakeFuture(),check=stop,report=report)
        self.assertEqual(len(report['slots']),18);self.assertEqual(report['new_logical_fits_reserved'],1)
        self.assertEqual(sum(r['state']=='NOT_ATTEMPTED' for r in report['slots']),17)
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(b.BuildStop):self.train(tmp,FakeFuture(double=True))

    def test_actual_initial_registration_before_inputs_and_new15Z_not_old12Z(self):
        config=self.config;initial=json.loads((ROOT/'config/weekly-initial-remaining-v1-registration.json').read_text())
        registration=json.loads((ROOT/'config/genuine-hosted-fixed-build-registration-starter-v1.json').read_text())
        registration.update(approved=True,source_sha='c'*40,registered_at_utc='2026-10-24T11:55:00Z',initial_registration=initial,initial_registration_sha256=d.sha(d.canonical(initial)))
        with tempfile.TemporaryDirectory() as tmp:
            event=Path(tmp)/'event.json';text=d.canonical(registration).decode()
            env=dict(GITHUB_ACTIONS='true',CI='true',RUNNER_ENVIRONMENT='github-hosted',GITHUB_REPOSITORY=d.REPO,GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1',
                GITHUB_JOB=d.MODE,BUILD_MODE=d.MODE,STORE_PERMISSION='write',GITHUB_ACTOR='NickNicky19',GITHUB_ACTOR_ID='208912933',GITHUB_RUN_ID='40000000005',GITHUB_SHA='c'*40,
                GITHUB_WORKFLOW_SHA='c'*40,GITHUB_WORKSPACE=str(ROOT),GITHUB_REF='refs/heads/fixture',GITHUB_WORKFLOW_REF=d.REPO+'/.github/workflows/lab.yml@refs/heads/fixture',
                GITHUB_EVENT_PATH=str(event),BUILD_REGISTRATION_JSON=text,BUILD_REGISTRATION_SHA256=d.sha(text.encode()),**config['numerical_environment'])
            event.write_text(json.dumps(dict(inputs={'mode':d.MODE,'build_registration_json':text,'build_registration_sha256':env['BUILD_REGISTRATION_SHA256']},repository={'full_name':d.REPO},ref='fixture')))
            original=d.read
            with patch.object(d,'read',side_effect=lambda p,c:('c'*40+'\n').encode() if Path(p)==ROOT/'.git/HEAD' else original(p,c)),patch.object(d,'now',return_value=datetime(2026,10,24,12,tzinfo=timezone.utc)):
                self.assertEqual(d.preflight(env,config)['maximum_new_fits'],18)
                registration['initial_registration']['registered_at_utc']='2026-10-24T11:00:00Z'
                registration['initial_registration_sha256']=d.sha(d.canonical(registration['initial_registration']))
                text=d.canonical(registration).decode()
                with self.assertRaises(Exception):d.preflight(dict(env,BUILD_REGISTRATION_JSON=text,BUILD_REGISTRATION_SHA256=d.sha(text.encode())),config)
                registration['initial_registration']['registered_at_utc']=None;text=d.canonical(registration).decode()
                with self.assertRaises(Exception):d.preflight(dict(env,BUILD_REGISTRATION_JSON=text,BUILD_REGISTRATION_SHA256=d.sha(text.encode())),config)

    def test_memory_and_storage_errors_stop_packet_without_more_fits(self):
        from nfl_lab.operational_storage import StorageQuotaError, StorageIntegrityError
        for error in (MemoryError, StorageQuotaError, StorageIntegrityError):
            with self.subTest(error=error.__name__):
                class ResourceFailure(FakeFuture):
                    def fit_future_model(self,train,category,family,**kwargs):
                        self.calls.append((category['target'],family))
                        kwargs['fit_gate']({'family':family,'target':category['target']})
                        raise error('FICTIONAL_GLOBAL_RESOURCE_FAILURE')
                backend=ResourceFailure();report=b.initial_training_report()
                with tempfile.TemporaryDirectory() as tmp,self.assertRaises(b.BuildStop):
                    self.train(tmp,backend,report=report)
                self.assertEqual(len(backend.calls),1)
                self.assertEqual(report['new_logical_fits_reserved'],1)
                self.assertEqual(report['slots'][0]['state'],'GLOBAL_RESOURCE_OR_STORAGE_STOP_RETAINED')
                self.assertEqual(sum(r['state']=='NOT_ATTEMPTED' for r in report['slots']),17)

    def test_source_claim_is_exact_same_job_and_cannot_reuse_a_consumed_build(self):
        initial=json.loads((ROOT/'config/weekly-initial-remaining-v1-registration.json').read_text())
        registration=dict(initial_registration=initial,registered_at_utc='2026-10-24T12:00:00Z')
        initial_body=d.canonical(initial);procedure=b'fictional-reviewed-procedure'
        receipt=dict(schema_version='weekly-gha-private-checkpoint-v1-source-claim',state='ONE_TIME_SOURCE_CLAIMED',repository=d.REPO,
            run_id='40000000005',source_sha='c'*40,job_id=d.MODE,api_job_id=123,process_identity='a'*64,
            registration_sha256=d.sha(initial_body),registration_bytes=len(initial_body),asset_id=456,
            asset_name='manifest-'+d.sha(initial_body)+'.json',binding_sha256='763d08e2d576434b3722ad942da9f807645f6ffa39d0650616fae80a11d1fa11',
            procedure_sha256=d.sha(procedure),claimed_at='2026-10-24T12:01:00Z')
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);physical=directory/'private-checkpoint-claim/CLAIM_RECEIPT.json';physical.parent.mkdir()
            def setup(value):
                text=d.canonical(value).decode();physical.write_bytes(text.encode())
                return dict(GITHUB_RUN_ID='40000000005',GITHUB_SHA='c'*40,BUILD_CLAIM_RECEIPT_JSON=text,BUILD_CLAIM_RECEIPT_SHA256=d.sha(text.encode()))
            original=d.read;job=dict(job_id=d.MODE,api_job_id=123,run_authenticated=True)
            with patch.object(d,'read',side_effect=lambda p,c:procedure if Path(p)==ROOT/'config/gha-private-checkpoint-v1.json' else original(p,c)),\
                    patch.object(d,'now',return_value=datetime(2026,10,24,12,2,tzinfo=timezone.utc)):
                env=setup(receipt)
                self.assertEqual(d.verify_source_claim(env,self.config,registration,directory,job=job,process='b'*64),receipt)
                for name,value in [('source_sha','d'*40),('api_job_id',124),('asset_name','manifest-'+'e'*64+'.json'),
                    ('procedure_sha256','e'*64),('claimed_at','2026-10-24T12:03:00Z')]:
                    changed=dict(receipt,**{name:value})
                    with self.subTest(field=name),self.assertRaises(d.GuardStop):
                        d.verify_source_claim(setup(changed),self.config,registration,directory,job=job,process='b'*64)
                env=setup(receipt)
                with self.assertRaises(d.GuardStop):d.verify_source_claim(env,self.config,registration,directory,job=job,process='a'*64)
                physical.write_bytes(b'{}')
                with self.assertRaises(d.GuardStop):d.verify_source_claim(env,self.config,registration,directory)
                env=setup(receipt);(directory/'CONSUMED.json').write_bytes(b'{}')
                with self.assertRaises(d.GuardStop):d.verify_source_claim(env,self.config,registration,directory)

    def test_noop_source_pins_and_same_workflow_single_writer_only(self):
        with redirect_stdout(io.StringIO()) as output:self.assertEqual(d.main([]),2)
        self.assertEqual(json.loads(output.getvalue())['state'],'HOSTED_FIXED_BUILD_PREPARATION_ONLY_NO_IO')
        with retained_procedure(d,'config/genuine-hosted-fixed-build-v1.json'):
            self.assertEqual(d.verify_sources()['maximum_new_fits'],18)
        with self.assertRaisesRegex(d.GuardStop,'BUILD_SOURCE_CHANGED'):
            d.verify_sources()
        workflow=(ROOT/'.github/workflows/lab.yml').read_text();job=workflow.split('  genuine-hosted-fixed-build-v1:\n',1)[1]
        self.assertIn('group: nfl-lab-single-writer',workflow);self.assertEqual(workflow.count("cron: '36 13,14 * * *'"),1)
        self.assertIn('requirements-hosted-fixed-build-v1.lock',job);self.assertNotIn('upload-artifact',job)
        self.assertLess(job.index('id: source-claim'),job.index('tools/genuine_hosted_fixed_build_v1.py --execute'))
        self.assertGreater(job.index('id: private-checkpoint'),job.index('tools/genuine_hosted_fixed_build_v1.py --execute'))
        self.assertIn('BUILD_CLAIM_RECEIPT_JSON: ${{ steps.source-claim.outputs.claim_receipt_json }}',job)
        self.assertIn('genuine-hosted-fixed-build-restore-v1:',job)
        self.assertIn('needs: genuine-hosted-fixed-build-v1',job)
        self.assertIn('checkpoint_handoff_json: ${{ steps.private-checkpoint.outputs.handoff_json }}',job)
        self.assertIn("inputs.mode != 'genuine-hosted-fixed-build-v1'",workflow)


if __name__=='__main__':unittest.main()
