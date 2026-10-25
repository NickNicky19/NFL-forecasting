"""Opaque invented forecasts and injected API; no child/HTTP/NFL/model work."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from retained_source_fixture import retained_procedure

from nfl_lab import selected_private_snapshot as x,private_draft_store as s,weekly_durable_acceptance as a
from nfl_lab.operational_storage import OperationalStorage
from tools import selected_private_snapshot_v1 as cli
from tools import export_weekly_public_feed_v1 as exporter,private_draft_store_v2 as context_cli
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from test_owner_private_bootstrap import qualification

ROOT=Path(__file__).resolve().parents[1]


class SnapshotChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_bytes());self.server=Server()
        journal=self.base/'init';journal.mkdir(mode=0o700);c=s.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,transport=self.server,process='e'*64);self.binding=s.initialize(c,'a'*32);self.q=qualification(self.binding);self.server.calls.clear()
        self.root=self.base/'producer';self.storage=self.store(self.root);self.output=self.root/'snapshot';self.output.mkdir();self.factory=self.factory_for(self.root,'producer','4'*64);self.first=self.factory('append')
        self.config=dict(_sha256='d'*64,_qualification=self.q,input_cutoff_utc=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),produce_job='producer',restore_job='restorer',producer_policy_sha256=None)
        self.inference=self.root/'initial-inference-v1';self.inference.mkdir();self.fixture()
    def tearDown(self):self.tmp.cleanup()
    def store(self,root):root.mkdir();storage=OperationalStorage(root/'cache',self.policy,state=root/'state');storage.register_root(root);return storage
    def factory_for(self,root,job_id,process):
        journal=root/('journal-'+job_id);journal.mkdir(mode=0o700);outer=self
        class Factory:
            last=None
            def __call__(self,operation):
                job=dict(execution_lane='github_actions',workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',workflow_sha=SOURCE,job_id=job_id,permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
                def transport(req,timeout):
                    if '/jobs?' in req.full_url:return Response(dict(total_count=1,jobs=[dict(id={'producer':77,'restorer':78,'exporter':79}[job_id],name=job_id,status='in_progress',run_id=int(RUN),head_sha=SOURCE)]))
                    return outer.server(req,timeout)
                c=s.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,transport=transport,process=process,job=job,operation=operation);c.authenticate_actions_job();c.bind(outer.binding);self.last=c;return c
        return Factory()
    def write(self,path,doc=None,body=None):
        self.storage.write_bytes(path,s.canonical(doc) if body is None else body);return x.ref(path)
    def fixture(self):
        stamp=datetime.now(timezone.utc)-timedelta(minutes=1);clock=stamp.isoformat();models=[]
        for n,(t,_,m) in enumerate(x.cp.JOBS):
            body=self.write(self.inference/'candidates'/t/(m+'.jsonl.gz'),body=gzip.compress(s.canonical(dict(FICTIONAL_ONLY=True,ordinal=n))+b'\n',mtime=0))
            persistence=dict(state='PERSISTED',binding=body,rows=1,persist_started_at=clock,completed_at=clock)
            self.write(Path(body['path']).with_suffix('.completion.json'),persistence)
            models.append(dict(target=t,method_id=m,persistence=persistence,failure=None))
        selected=self.write(self.inference/'selected.jsonl.gz',body=gzip.compress(b'{"FICTIONAL_SELECTED_ONLY":true}\n',mtime=0));completion=dict(state='PERSISTED',binding=selected,rows=1,persist_started_at=clock,completed_at=clock)
        refs={};refs['completion']=self.write(self.inference/'selected.jsonl.completion.json',completion);refs['decision']=self.write(self.inference/'DECISION.json',dict(FICTIONAL_CHOICE=True))
        refs['parent_capture']=self.write(self.inference/'CANDIDATES.json',dict(schema_version='weekly-generic-future-producer-v1-candidate-capture',state='GENERIC_CANDIDATE_FORECASTS_PERSISTED',models=models,actual_completed_at=clock))
        refs['bridge']=self.write(self.inference/'BRIDGE.json',dict(FICTIONAL_BRIDGE=True));refs['startup_policy']=self.write(self.inference/'POLICY.json',dict(FICTIONAL_POLICY=True));self.config['producer_policy_sha256']=refs['startup_policy']['sha256']
        refs['procedure_catalog']=self.write(self.inference/'CATALOG.json',dict(FICTIONAL_CATALOG=True));refs['selected_version_catalog']=self.write(self.inference/'VERSIONS.json',dict(current_values_used=False))
        refs['terminal']=self.write(self.inference/'FINISHED.json',dict(schema_version='weekly-generic-future-producer-v1',state='LOCAL_FUTURE_SLATE_CAPTURED',fatal=None,selected=completion,decision=refs['decision'],parent_capture=refs['parent_capture'],startup_policy=refs['startup_policy'],actual_completed_at=clock))
        self.write(self.inference/'CONSUMED.json',dict(schema_version='weekly-generic-future-producer-v1',at=(stamp-timedelta(minutes=1)).isoformat(),invocations=1,retries=0))
        self.write(self.inference/'EXPORT_INPUTS.json',dict(schema_version='weekly-generic-selected-handoff-v1',selected=selected,**refs))
    def collect(self):return x.collect(self.inference,self.storage,self.output,self.first,self.config)
    def append(self):
        selected,files,refs,producer,candidates=self.collect();return x.append_snapshot(selected,files,refs,producer,candidates,self.factory,self.q,self.storage,self.output,self.config,first=self.first)
    def chain(self):
        handoff=self.append();root3=self.base/'restorer';store3=self.store(root3);f3=self.factory_for(root3,'restorer','5'*64)
        r3=x.restore_snapshot(handoff,f3,store3,root3/'snapshot',self.config,producer_api_job_id=77);root4=self.base/'exporter';store4=self.store(root4);f4=self.factory_for(root4,'exporter','6'*64)
        r4=x.restore_snapshot(handoff,f4,store4,root4/'snapshot',self.config,producer_api_job_id=77,witness=r3['witness_descriptor'],witness_api_job_id=78)
        bundle={name:x.document(r4[name]) for name in ['terminal','completion','inference_consumed','producer_proof','durability']};bundle.update(terminal_body_sha256=r4['terminal']['sha256'],inference_consumed_body_sha256=r4['inference_consumed']['sha256'],inference_consumed_body_bytes=r4['inference_consumed']['bytes'])
        return r3,r4,bundle,store4,f4
    def test_all18_streams_and_job3_witness_survive_export_job_relocation(self):
        r3,r4,bundle,storage,f4=self.chain();self.assertEqual(r4['candidates_retained'],18);self.assertEqual(r4['candidate_rows'],18)
        self.assertNotEqual(r4['selected']['path'],bundle['completion']['binding']['path']);self.assertEqual(r4['selected']['sha256'],bundle['completion']['binding']['sha256'])
        self.assertEqual(bundle['durability']['restore_proof']['job']['job_id'],'restorer');a.facts(bundle,dict(producer_policy_sha256=self.config['producer_policy_sha256'],source_policy_sha256=x.cp.POLICY_SHA))
        accepted=dict(producer=bundle['producer_proof']['identity'],restorer=a.restored_identity(bundle['durability']['restore_proof']),exporter=x.cp.client_identity(f4.last))
        x.verify_relocation(x.document(r4['selected_relocation']),bundle,r4['selected'],storage,accepted,r4['selected_snapshot_index'])
    def test_missing_candidate_body_rejected_before_first_POST(self):
        selected,files,refs,p,c=self.collect();files.pop(0)
        with self.assertRaises(s.StoreError):x.append_snapshot(selected,files,refs,p,c,self.factory,self.q,self.storage,self.output,self.config,first=self.first)
        self.assertFalse(any(r.method=='POST' for r in self.server.calls))
    def test_all_runtime_unknown_bytes_count_before_forecast_POST(self):
        for n in range(4):self.server.add('unknown-'+str(n),size=(8<<20)-(200 if n==3 else 0))
        with self.assertRaises(s.StoreError):self.append()
        self.assertFalse(any(r.method=='POST' for r in self.server.calls))
    def test_wrong_job_rejected_before_private_capture(self):
        self.first.job['job_id']='not-registered'
        with self.assertRaisesRegex(s.StoreError,'PRODUCER_JOB'):self.collect()
    def test_index_rejects_wrong_actual_producer_API_job(self):
        h=self.append();root=self.base/'wrong-api';storage=self.store(root);factory=self.factory_for(root,'restorer','5'*64)
        with self.assertRaisesRegex(s.StoreError,'GENUINE_PACKAGER'):x.restore_snapshot(h,factory,storage,root/'snapshot',self.config,producer_api_job_id=999)
    def test_relocation_rejects_wrong_bytes_and_unowned_copy(self):
        _,r,b,storage,f4=self.chain();accepted=dict(producer=b['producer_proof']['identity'],restorer=a.restored_identity(b['durability']['restore_proof']),exporter=x.cp.client_identity(f4.last));rel=x.document(r['selected_relocation'])
        bad=deepcopy(rel);bad['restored_selected']['sha256']='0'*64
        with self.assertRaises(s.StoreError):x.verify_relocation(bad,b,r['selected'],storage,accepted,r['selected_snapshot_index'])
        copy=Path(r['selected']['path']).parents[1]/'unowned-copy';s.create_local(copy,x.read(r['selected']));unowned=x.ref(copy);bad=deepcopy(rel);bad['restored_selected']=unowned
        with self.assertRaises((ValueError,RuntimeError)):x.verify_relocation(bad,b,unowned,storage,accepted,r['selected_snapshot_index'])
    def test_unapproved_snapshot_procedure_fails_before_credentials(self):
        body=(ROOT/'config/selected-private-snapshot-v1.json').read_bytes()
        unapproved=json.loads(body);unapproved['state']='FICTIONAL_UNAPPROVED';rejected=s.canonical(unapproved)
        with patch.object(cli,'read',return_value=rejected),self.assertRaisesRegex(ValueError,'PROCEDURE_PENDING'):
            cli.verify_sources(cli.sha(rejected))
        with retained_procedure(cli,'config/selected-private-snapshot-v1.json'):
            self.assertEqual(cli.verify_sources(cli.CONFIG_SHA256)['state'],'ROOT_APPROVED_FOR_GENUINE_GHA')
        with self.assertRaisesRegex(ValueError,'SELECTED_SOURCE_PIN'):
            cli.verify_sources(cli.CONFIG_SHA256)
    def test_v2_honest_clock_negatives_and_v1_semantics_unchanged(self):
        _,_,b,_,_=self.chain();policy=dict(producer_policy_sha256=self.config['producer_policy_sha256'],source_policy_sha256=x.cp.POLICY_SHA)
        for change in ['future_terminal','backdated_packager','wrong_body']:
            bad=deepcopy(b)
            if change=='future_terminal':bad['terminal']['actual_completed_at']=(s.utc(bad['producer_proof']['started_at_utc'])+timedelta(seconds=1)).isoformat()
            elif change=='backdated_packager':bad['producer_proof']['started_at_utc']=(s.utc(bad['terminal']['actual_completed_at'])-timedelta(seconds=1)).isoformat()
            else:bad['producer_proof']['selected_sha256']='0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):a.facts(bad,policy)
        old=deepcopy(b);old['producer_proof']={k:v for k,v in old['producer_proof'].items() if k in a.PRODUCER};old['producer_proof'].update(schema_version='weekly-selected-producer-provenance-v1',started_at_utc=old['inference_consumed']['at']);a.facts(old,policy)


class ExportCounterCheck(unittest.TestCase):
    def test_actual_client_counter_survives_automatic_acceptance(self):
        procedure=dict(verifier_sha256=s.sha(Path(a.__file__).read_bytes()),source_sha=SOURCE,export_job='exporter')
        plan=dict(verifier_procedure_sha256=a.digest(procedure),acceptance_journal='/FICTIONAL',durability_acceptance_output='/FICTIONAL')
        fake=SimpleNamespace(calls=3,bind=lambda _:None);live=SimpleNamespace(record={})
        env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=s.REPO,GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1',GITHUB_SHA=SOURCE,GITHUB_JOB='exporter',STORE_PERMISSION='write',GITHUB_TOKEN='ghs_FICTIONAL',GITHUB_RUN_ID=RUN)
        with patch.object(exporter.acceptance,'verify_current_actions',return_value=live),patch.object(s,'Client',return_value=fake),patch.object(context_cli,'actions_context',return_value={}),patch.object(exporter,'persist_live_acceptance'),patch.dict('os.environ',env,clear=True):
            result=exporter.automatic_acceptance(plan,dict(durability=dict(runtime_binding={}),canary_acceptance={}),dict(durability_verifier_procedures=[procedure]),'2026-10-24T00:00:00Z')
        self.assertEqual(result.control_API_calls,3);self.assertEqual(result.record,{})


if __name__=='__main__':unittest.main()
