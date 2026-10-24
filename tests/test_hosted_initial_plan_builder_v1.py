"""Invented restore/source/model metadata only; no model or provider calls."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime,timezone
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nfl_lab import hosted_initial_plan_builder_v1 as b,gha_private_checkpoint as cp,private_draft_store as core
from nfl_lab.hosted_fixed_build_v1 import allowed_periods
from tools import hosted_initial_plan_builder_v1 as cli

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,10,24,12,30,tzinfo=timezone.utc)
SOURCE='c'*40;RUN='123456789';WORKFLOW=core.REPO+'/.github/workflows/lab.yml@refs/heads/fictional'


class Clock(datetime):
    @classmethod
    def now(cls,tz=None):return NOW


def go():
    return dict(schema_version=b.VERSION+'-GO',state='ROOT_APPROVED_METADATA_BUILDER',authority_kind='ROOT_APPROVED_PROCEDURE',root_ledger_writer='/root',
        procedure_sha256='1'*64,source_sha=SOURCE,initial_registration_sha256=b.REGISTRATION_SHA,scope='STRICT18_INITIAL15Z_METADATA_PLAN_ONLY',
        approved_at_utc='2026-10-24T12:00:00Z',reviewer='/root/independent',independent_review_receipt_sha256='2'*64,
        root_ledger_event_sha256='3'*64,individual_generated_plan_human_review=False)


def fixture():
    registration=json.loads((ROOT/'config/weekly-initial-remaining-v1-registration.json').read_text())
    policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_text());names=cp.source_names(policy)
    config=dict(source_names=names,produce_job='genuine-hosted-fixed-build-v1',restore_job='genuine-hosted-fixed-build-restore-v1',_sha256='4'*64,
        _source_contract=dict(source_policy_sha256=cp.POLICY_SHA,feature_builder_sha256='5'*64,availability_rule='FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION'),
        _source_code_pins={'source.py':'6'*64},_numeric_code_pins={'numeric.py':'7'*64},_environment={'fictional':'1'},
        _allowed_periods={str(y):w for y,w in allowed_periods().items()},source_freshness_seconds=dict(schedule=86400,current_roster=86400,current_statistics=86400,players=604800))
    actual=json.loads((ROOT/'reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json').read_text());config['_runtime_binding']=actual['binding']
    root=Path('/tmp/fictional-restore-root');files=root/'private-checkpoint-restore/files';docs={};mapping={}
    def ref(path):return dict(path=str(path),bytes=100,sha256=core.sha(str(path).encode()))
    def mapped(logical):
        item=ref(files/logical);mapping['/fictional-original/'+logical]=item;return item
    source_refs={name:mapped('source-cache/raw/'+name) for name in names}
    receipt_refs={name:mapped('source-cache/raw/'+name+'.receipt.json') for name in names}
    slots=[];models=[]
    for target,family,method in cp.JOBS:
        prefix='models/'+target+'/'+family;original_model=mapped(prefix+'/trained.joblib');original_ref=mapped(prefix+'/future-inference.json')
        original_model=dict(original_model,path='/fictional-original/'+prefix+'/trained.joblib')
        support='bernoulli' if target=='anytime_td' else 'signed_integer' if target.endswith('_yd') else 'count'
        m=dict(schema_version='weekly-adaptive-release-v1-future-inference',artifact_kind='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY',dependencies=[],
            category=dict(target=target,support=support),family=family,method_id=method,source_contract=config['_source_contract'],code_pins=config['_numeric_code_pins'],
            environment=config['_environment'],training_cutoff_utc='2026-09-01T00:00:00+00:00',artifact_created_at='2026-10-24T11:59:00Z',
            fit_receipt=dict(training_source_capture_completed_at='2026-10-24T11:56:00Z',training_started_at='2026-10-24T11:57:00Z',training_completed_at='2026-10-24T11:58:00Z'),
            model=original_model,procedure_version=family+'-fictional',product={'count':'point_mean','signed_integer':'point_median','bernoulli':'binary_probability'}[support])
        docs[original_ref['path']]=m;relocated_ref=ref(root/'private-checkpoint-restore/relocated-models'/target/family/'future-inference.json')
        relocated_model=dict(original_model,path=str(root/'private-checkpoint-restore/relocated-models'/target/family/'trained.joblib'))
        docs[relocated_ref['path']]=dict(m,model=relocated_model,relocation=dict(schema_version=b.generic.MODEL_BOUNDARY,original_manifest=original_ref,
            original_model=original_model,relocated_model_path=relocated_model['path'],parameters_fixtures_code_source_unchanged=True,model_decodes=0))
        slots.append(dict(target=target,family=family,method_id=method,state='NEW_OPERATIONAL_ARTIFACT_EXPORTED',estimator_gate_calls=1,artifact=original_ref,fit_receipt=m['fit_receipt']))
        models.append(dict(target=target,family=family,method_id=method,manifest=relocated_ref,original_model_sha256=original_model['sha256']))
    producer=dict(execution_lane='github_actions',repository=core.REPO,run_id=RUN,run_attempt=1,source_sha=SOURCE,process_identity='a'*64,
        job_id=config['produce_job'],api_job_id=1,permission='write',workflow_ref=WORKFLOW)
    restorer=dict(producer,process_identity='b'*64,job_id=config['restore_job'],api_job_id=2)
    genuine_job=dict(execution_lane='github_actions',workflow_ref=WORKFLOW,workflow_sha=SOURCE,job_id=config['restore_job'],permission='write',event_name='workflow_dispatch',api_job_id=2,run_authenticated=True)
    client=SimpleNamespace(run_id=RUN,source_sha=SOURCE,binding=actual['binding'],process='b'*64,job=genuine_job,operation='restore',started_at='2026-10-24T12:29:00Z',calls=10,transferred=100)
    with patch.object(core,'datetime',Clock):
        proofs=[core.receipt(client,'restore',exact_readback=True,payload_sha256=d*64,bytes=100,separate_process=True,draft_before_after=True) for d in ('e','f')]
    source=dict(source_contract=config['_source_contract'],actual_execution_asof='2026-10-24T11:55:00Z',actual_source_and_feature_capture_completed_at='2026-10-24T11:56:00Z')
    build=dict(schema_version='GENUINE_HOSTED_FIXED_BUILD_V1',state='SOURCE_AND_TRAIN18_COMPLETE',fatal=None,source_sha=SOURCE,execution_lane='github_actions',
        genuine_job=dict(genuine_job,job_id=config['produce_job'],api_job_id=1),scoring=0,searches=0,forecasts_issued=0,source=source,training=dict(new_logical_fits_reserved=18,slots=slots))
    build_registration=dict(schema_version='genuine-hosted-fixed-build-registration-v1',approved=True,repository=core.REPO,source_sha=SOURCE,maximum_new_fits=18,
        scope='SOURCE_AND_TRAIN_FIXED18_ONLY',initial_registration=registration,initial_registration_sha256=b.REGISTRATION_SHA)
    source_manifest=dict(policy_sha256=cp.POLICY_SHA,code_sha256s=config['_source_code_pins'],allowed_periods=config['_allowed_periods'],source_receipts={},sources={})
    for name,url in names.items():
        receipt=dict(status='acquired',retrieved_utc='2026-10-24T11:55:00Z',sha256=source_refs[name]['sha256'],url=url)
        docs[receipt_refs[name]['path']]=receipt;source_manifest['source_receipts'][name]=receipt
        source_manifest['sources'][name]=dict(sha256=source_refs[name]['sha256'],receipt_sha256=receipt_refs[name]['sha256'],bytes=source_refs[name]['bytes'])
    for name,document in [('BUILD.json',build),('BUILD_REGISTRATION.json',build_registration),('SOURCE_READBACK.json',source),('source-manifest.json',source_manifest)]:
        docs[mapped('control/'+name)['path']]=document
    restored=dict(schema_version=cp.VERSION+'-restore',state='FULL_PRIVATE_CHECKPOINT_RESTORED',source_sha=SOURCE,run_id=RUN,procedure_sha256=config['_sha256'],
        index_sha256='e'*64,actual_completed_at=NOW.isoformat(),original_producer=producer,restorer=restorer,proofs=proofs,path_mapping=mapping,models=models,
        source_cache=str(files/'source-cache'),files=78,groups=1,model_decodes=0,scoring=0,old_model_hash_reproduction=False,selected_forecast_durability='NOT_CLAIMED')
    kwargs=dict(restore_ref=ref(root/'private-checkpoint-restore/RESTORE_FINISHED.json'),root=root,config=config,source_sha=SOURCE,run_id=RUN,
        workflow_ref=WORKFLOW,process_identity='d'*64,now=NOW,read=lambda ref:deepcopy(docs[ref['path']]),registration=registration)
    return restored,kwargs,docs


def validated(value):
    restored,kwargs,docs=value
    with patch.object(core,'datetime',Clock):return b.validate_restore(restored,**kwargs)


class MetadataBuilderChecks(unittest.TestCase):
    def test_GO_has_procedure_review_identity_and_no_fabricated_individual_human_review(self):
        approval=go();b.verify_go(approval,procedure_sha256='1'*64,source_sha=SOURCE,now=NOW)
        for field,value in [('individual_generated_plan_human_review',True),('state','PREPARED'),('source_sha','0'*40),('approved_at_utc','2026-10-24T14:00:00Z')]:
            changed=dict(approval,**{field:value})
            with self.subTest(field=field),self.assertRaises(ValueError):b.verify_go(changed,procedure_sha256='1'*64,source_sha=SOURCE,now=NOW)

    def test_complete_strict18_metadata_maps_original38_source_refs_and115_owned_inputs(self):
        result=validated(fixture())
        self.assertEqual(len(result['artifacts']),18);self.assertEqual(len(result['source_bindings']),38);self.assertEqual(len(result['owned_inputs']),115)
        self.assertTrue(result['source_cache'].endswith('/files/source-cache'));self.assertTrue(result['schedule']['path'].endswith('/source-cache/raw/schedules.csv'))

    def test_prior_API_identity_cannot_be_other_job_run_source_or_builder_process(self):
        for field in ('job','run','source','process'):
            value=fixture();restored,kwargs,_=value
            if field=='job':restored['restorer']['api_job_id']=99
            elif field=='run':kwargs['run_id']='999'
            elif field=='source':kwargs['source_sha']='0'*40
            else:kwargs['process_identity']='b'*64
            with self.subTest(field=field),self.assertRaises(Exception):validated(value)

    def test_missing_restore_proof_or_non_genuine_authentication_is_rejected(self):
        value=fixture();value[0]['proofs'].pop()
        with self.assertRaises(ValueError):validated(value)
        value=fixture();value[0]['proofs'][0]['job']['run_authenticated']=False
        with self.assertRaises(Exception):validated(value)

    def test_strict18_failure_no_partial_success_or_model_substitution(self):
        value=fixture();value[0]['models'].pop()
        with self.assertRaises(ValueError):validated(value)
        value=fixture();restored,kwargs,docs=value;docs[str(kwargs['root']/'private-checkpoint-restore/files/control/BUILD.json')]['training']['slots'][0]['state']='FAILED_FIT_RETAINED_NO_RETRY'
        with self.assertRaises(ValueError):validated(value)

    def test_changed_model_environment_source_code_or_relocation_rejected(self):
        for field in ('environment','source','model'):
            value=fixture();restored,kwargs,docs=value
            if field=='environment':kwargs['config']['_environment']={'fictional':'changed'}
            elif field=='source':kwargs['config']['_source_code_pins']={'changed.py':'0'*64}
            else:docs[restored['models'][0]['manifest']['path']]['model']['sha256']='0'*64
            with self.subTest(field=field),self.assertRaises(ValueError):validated(value)

    def test_capture_and_fit_must_follow_exact_initial_registration(self):
        value=fixture();restored,kwargs,docs=value
        docs[str(kwargs['root']/'private-checkpoint-restore/files/control/SOURCE_READBACK.json')]['actual_execution_asof']='2026-10-24T09:00:00Z'
        with self.assertRaises(ValueError):validated(value)
        value=fixture();restored,kwargs,docs=value
        docs[restored['models'][0]['manifest']['path']]['fit_receipt']['training_completed_at']='2026-10-24T10:00:00Z'
        with self.assertRaises(ValueError):validated(value)

    def test_exact14_schedule_metadata_derives_new15Z_slate_without_player_or_stat_values(self):
        header='season,week,game_type,game_id,gameday,gametime\n'
        body=header+'2026,7,REG,2026_07_NE_CHI,2026-10-22,20:15\n'
        body+=''.join('2026,7,REG,'+game+',2026-10-25,'+('09:30' if i==0 else '13:00')+'\n' for i,game in enumerate(b.initial.REMAINING))
        value=fixture();registration=value[1]['registration'];ref={'path':'fictional-registration','bytes':100,'sha256':'0'*64}
        slate=b.initial.prepare_initial_slate(b.schedule_metadata(body.encode()),registration,ref,now=NOW)
        self.assertEqual(len(slate['game_cutoffs']),13);self.assertEqual(slate['elapsed_games'],1)
        self.assertEqual(set(slate['game_cutoffs'].values()),{'2026-10-24T15:00:00Z'})
        with self.assertRaises(ValueError):b.initial.prepare_initial_slate(b.schedule_metadata(header.encode()),registration,ref,now=NOW)

    def test_catalog_only_actual18_new_manifest_versions_R0_explicitly_unavailable(self):
        result=validated(fixture());catalog=b.catalog_metadata(list(zip(result['artifacts'],result['records'])),registered_at=NOW.isoformat())
        self.assertEqual(len(catalog['categories']),11);self.assertEqual(sum(len(m['model_versions']) for m in catalog['methods'].values()),18)
        self.assertFalse(catalog['methods']['R0']['procedure_operational_eligible']);self.assertEqual(catalog['methods']['R0']['model_versions'],[])
        self.assertTrue(all(c['reference_id']=='R0' for c in catalog['categories'].values()))

    def test_preparation_CLI_does_not_read_files_env_credentials_or_execute(self):
        with patch.object(cli,'run',side_effect=AssertionError('execution forbidden')),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main([]),2)
        self.assertEqual(json.loads(output.getvalue())['state'],'INITIAL_PLAN_BUILDER_PREPARATION_ONLY_NO_IO')

    def test_reviewed_GO_supplies_procedure_SHA_without_workflow_hash_cycle(self):
        approval=go();summary=dict(state='STRICT18_INITIAL_METADATA_PLAN_GENERATED',plan_sha256='8'*64)
        with patch.dict(cli.os.environ,{'INITIAL_PLAN_BUILDER_GO_JSON':json.dumps(approval)},clear=True),\
                patch.object(cli.resource,'setrlimit'),patch.object(cli.signal,'alarm'),patch.object(cli.sys,'addaudithook'),\
                patch.object(cli,'run',return_value=summary) as run,redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--execute']),0)
        self.assertEqual(run.call_args.args[1],approval['procedure_sha256'])


if __name__=='__main__':unittest.main()
