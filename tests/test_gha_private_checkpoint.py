"""Fictional in-memory API + opaque invented files only; no NFL/HTTP/ML."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import base64
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone,timedelta
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import gha_private_checkpoint as cp,private_draft_store as s
from nfl_lab.operational_storage import OperationalStorage
from tools import gha_private_checkpoint_v1 as cli
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from test_owner_private_bootstrap import qualification
from retained_source_fixture import retained_procedure, workflow_job

ROOT=Path(__file__).resolve().parents[1]


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'build';self.root.mkdir()
        self.policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_bytes());self.policy['_path']=str(ROOT/'config/operational-source-policy-v2.json')
        self.storage=OperationalStorage(self.root/'cache',self.policy,state=self.root/'state');self.storage.register_root(self.root)
        self.journal=self.root/'journal';self.journal.mkdir(mode=0o700);self.server=Server()
        init=s.Client('ghs_FICTIONAL',RUN,journal=self.journal,source_sha=SOURCE,transport=self.server,process='e'*64)
        self.runtime=s.initialize(init,'c'*32);self.q=qualification(self.runtime);self.server.calls.clear()
        self.config=json.loads((ROOT/'config/gha-private-checkpoint-v1.json').read_bytes())
        self.config.update(source_names=cp.source_names(self.policy),external_pending_reservations=[])
        self.factory=self.factory_for(self.journal,self.config['produce_job'],'4'*64)
        first=self.factory('append');self.job=first.job
        self.make_build();self.output=self.root/'checkpoint';self.output.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def factory_for(self,journal,label,process):
        outer=self
        class Factory:
            last=None
            def __init__(self):self.clients=[]
            def __call__(self,operation):
                if len(self.clients)>=9:raise AssertionError('finite client cap')
                job=dict(execution_lane='github_actions',workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',workflow_sha=SOURCE,job_id=label,permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
                def transport(req,timeout):
                    if '/jobs?per_page=100&page=1' in req.full_url:return Response(dict(total_count=1,jobs=[dict(id=777 if process=='4'*64 else 778,name=label,status='in_progress',run_id=int(RUN),head_sha=SOURCE)]))
                    return outer.server(req,timeout)
                c=s.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,transport=transport,process=process,job=job,operation=operation);c.authenticate_actions_job();c.bind(outer.runtime)
                self.clients.append(c);self.last=c;return c
        return Factory()
    def write(self,name,body):
        self.storage.write_bytes(self.root/name,body);return cp.binding(self.root/name)
    def make_build(self):
        slots=[]
        for t,family,method in cp.JOBS:
            prefix='models/'+t+'/'+family;model=self.write(prefix+'/trained.joblib',('FICTIONAL_OPAQUE_NOT_A_MODEL '+prefix).encode())
            manifest=dict(schema_version='weekly-adaptive-release-v1-future-inference',artifact_kind='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY',family=family,method_id=method,source_contract=dict(source_policy_sha256=cp.POLICY_SHA),dependencies=[],model=model)
            ref=self.write(prefix+'/future-inference.json',s.canonical(manifest));slots.append(dict(target=t,family=family,method_id=method,state='NEW_OPERATIONAL_ARTIFACT_EXPORTED',estimator_gate_calls=1,artifact=ref))
        raw=self.root/'cache/operational-source-v2'/cp.POLICY_SHA/'daily/2026-10-24';refs=[]
        for name,url in cp.source_names(self.policy).items():
            r=self.write(str((raw/'raw'/name).relative_to(self.root)),('FICTIONAL_OPAQUE_SOURCE '+name).encode());refs.append(r)
            refs.append(self.write(str((raw/'raw'/(name+'.receipt.json')).relative_to(self.root)),s.canonical(dict(status='acquired',sha256=r['sha256'],url=url,retrieved_utc='2026-10-24T01:00:00Z'))))
        source=dict(schema_version='genuine-hosted-source-readback-v1',actual_execution_asof='2026-10-24T01:00:00Z',original_source_cache=str(raw),original_raw_body_receipt_bindings=refs,manifest=self.write('source-manifest.json',b'{"FICTIONAL_SOURCE_MANIFEST":true}'))
        self.write('SOURCE_READBACK.json',s.canonical(source));self.write('BUILD_REGISTRATION.json',s.canonical(dict(schema_version='genuine-hosted-fixed-build-registration-v1',approved=True,repository=s.REPO,source_sha=SOURCE,maximum_new_fits=18,scope='SOURCE_AND_TRAIN_FIXED18_ONLY')))
        build=dict(schema_version='GENUINE_HOSTED_FIXED_BUILD_V1',state='SOURCE_AND_TRAIN18_COMPLETE',fatal=None,source_sha=SOURCE,execution_lane='github_actions',genuine_job=self.job,
            private_remote_persistence='NOT_YET_PERFORMED',scoring=0,searches=0,forecasts_issued=0,source=source,training=dict(slots=slots,new_logical_fits_reserved=18))
        self.write('FINISHED.json',s.canonical(build))
    def collect(self):return cp.collect(self.root,self.storage,self.policy,source_sha=SOURCE,job=self.job)
    def produce(self):
        files,pairs,build=self.collect()
        # setUp's authentication client is the same first per-operation client.
        return cp.produce(files,pairs,build,self.factory,self.q,procedure_sha256='d'*64,source_sha=SOURCE,run_id=RUN,output=self.output,storage=self.storage,pending=[],first=self.factory.clients[0])
    def restore(self,handoff,*,process='5'*64):
        root=self.base/'fresh';root.mkdir();storage=OperationalStorage(root/'cache',self.policy,state=root/'state');storage.register_root(root);journal=root/'journal';journal.mkdir(mode=0o700)
        factory=self.factory_for(journal,self.config['restore_job'],process)
        return cp.restore(handoff,factory,config=self.config,storage=storage,output=root/'out',producer_api_job_id=777)
    def test_complete78_files_exact19_sources_and18_models(self):
        files,pairs,_=self.collect();self.assertEqual(len(files),78);self.assertEqual(len(pairs),18)
        self.assertEqual(sum(i['kind']=='source_raw' for i in files),19);self.assertTrue(all(i['required'] for i in files))
        self.assertNotIn('training-features.parquet',{Path(i['path']).name for i in files})
    def test_append_fresh_restore_and_new_manifest_relocation(self):
        handoff=self.produce();doc=self.restore(handoff);self.assertEqual(doc['files'],78);self.assertEqual(len(doc['models']),18);self.assertEqual(doc['model_decodes'],0)
        self.assertEqual(doc['selected_forecast_durability'],'NOT_CLAIMED');self.assertTrue(all(p['separate_process'] for p in doc['proofs']))
        for m in doc['models']:
            relocated=json.loads(s.read_local(m['manifest']['path'],256<<10));self.assertEqual(relocated['model']['sha256'],m['original_model_sha256']);self.assertFalse(m['manifest']['old_path_hash_reproduced'])
        raw=Path(doc['source_cache'])/'raw';self.assertEqual(len(list(raw.iterdir())),38)
        self.assertEqual(len(self.factory.clients),len(doc['proofs']));self.assertTrue(all(c.calls<=40 for c in self.factory.clients))
    def test_safe_handoff_has_no_paths_urls_private_index_or_body(self):
        handoff=self.produce();body=s.canonical(handoff)
        for marker in [b'/tmp/',b'/home/',b'https://',b'files',b'FICTIONAL_OPAQUE',b'models/']:self.assertNotIn(marker,body)
        self.assertEqual(handoff['index_descriptor']['entry']['payload']['payload_kind'],'runtime_manifest')
        self.assertGreater(len(list(self.output.glob('NATIVE_APPEND_GO-*.json'))),1)
    def test_all_groups_hash_before_any_POST(self):
        files,pairs,build=self.collect();files[-1]['sha256']='0'*64;files[-1]['origin']['source_sha256']='0'*64
        with self.assertRaises(s.StoreError):cp.produce(files,pairs,build,self.factory,self.q,procedure_sha256='d'*64,source_sha=SOURCE,run_id=RUN,output=self.output,storage=self.storage,pending=[],first=self.factory.clients[0])
        self.assertFalse(any(r.method=='POST' for r in self.server.calls))
    def test_unknown_asset_bytes_stop_before_any_POST(self):
        for i in range(4):self.server.add('unknown-'+str(i),size=(8<<20)-(100 if i==3 else 0))
        with self.assertRaises(s.StoreError):self.produce()
        self.assertFalse(any(r.method=='POST' for r in self.server.calls))
    def test_external_pending_bytes_and_slot_charged_without_POST(self):
        q=self.config['external_pending_reservations']=json.loads((ROOT/'config/gha-private-checkpoint-v1.json').read_bytes())['external_pending_reservations']
        cp.seed_pending(self.journal,q);c=self.factory.clients[0];_,total=c.inventory();self.assertEqual(total,117+80745);self.assertEqual(c.inventory_slots,2)
        cp.seed_pending(self.journal,q);_,again=c.inventory();self.assertEqual(again,total);self.assertFalse(any(r.method=='POST' for r in self.server.calls))
    def test_ambiguous_POST_is_not_retried_or_claimed_complete(self):
        self.server.ambiguous=True
        with self.assertRaises(s.StoreError):self.produce()
        self.assertEqual(sum(r.method=='POST' for r in self.server.calls),1);self.assertFalse((self.output/'PRODUCER_FINISHED.json').exists())
        self.assertTrue(list(self.journal.glob('*.reservation.json')))
    def test_same_process_restore_and_corrupt_payload_fail(self):
        handoff=self.produce()
        with self.assertRaises(s.StoreError):self.restore(handoff,process='4'*64)
    def test_corrupt_remote_index_stops_before_extraction(self):
        handoff=self.produce();asset_id=handoff['index_descriptor']['entry']['payload_asset_id']
        next(a for a in self.server.assets if a['id']==asset_id)['body']+=b'CORRUPT'
        with self.assertRaises(s.StoreError):self.restore(handoff)
        self.assertFalse((self.base/'fresh/out/files').exists());self.assertEqual(len(self.collect()[0]),78)
    def test_actual_fresh_Python_restores_fictional_opaque_snapshot(self):
        handoff=self.produce();fixture=self.base/'fictional-service.json';data=dict(handoff=handoff,config=self.config,policy=self.policy,tag=self.server.tag,
            assets=[dict(a,body=base64.b64encode(a['body']).decode()) for a in self.server.assets])
        fixture.write_bytes(s.canonical(data))
        program='''import base64,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,str(Path(sys.argv[1])/'tests'))
from test_gha_private_checkpoint import CheckpointTests,Server
from nfl_lab import gha_private_checkpoint as cp,private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
d=json.loads(Path(sys.argv[2]).read_bytes());t=CheckpointTests();t.server=Server();t.server.tag=d['tag'];t.server.assets=[dict(a,body=base64.b64decode(a['body'])) for a in d['assets']];t.runtime=d['handoff']['runtime_binding']
root=Path(sys.argv[3]);root.mkdir();storage=OperationalStorage(root/'cache',d['policy'],state=root/'state');storage.register_root(root);journal=root/'journal';journal.mkdir(mode=0o700)
factory=t.factory_for(journal,d['config']['restore_job'],store.process_identity());result=cp.restore(d['handoff'],factory,config=d['config'],storage=storage,output=root/'out',producer_api_job_id=777)
print(json.dumps(dict(state=result['state'],files=result['files'],models=len(result['models']),model_decodes=result['model_decodes'])))
'''
        result=subprocess.run([sys.executable,'-I','-B','-c',program,str(ROOT),str(fixture),str(self.base/'fresh-Python')],check=True,capture_output=True,text=True,timeout=30)
        observed=json.loads(result.stdout);self.assertEqual(observed['files'],78);self.assertEqual(observed['models'],18);self.assertEqual(observed['model_decodes'],0)
    def test_core_descriptor_rejects_owner_origin_unknown_fields_and_oversize(self):
        handoff=self.produce();descriptor=handoff['index_descriptor']
        for update in [dict(writer_origin='OWNER_BOOTSTRAP'),dict(payload_name='https://forbidden.invalid')]:
            d=deepcopy(descriptor);d['entry'].update(update)
            with self.assertRaises(s.StoreError):cp.descriptor_meta(d,cp.INDEX_CAP)
        d=deepcopy(descriptor);d['entry']['payload']['bytes']=cp.INDEX_CAP+1
        with self.assertRaises(s.StoreError):cp.descriptor_meta(d,cp.INDEX_CAP)
    def test_missing_source_or_failed_slot_never_becomes_partial_snapshot(self):
        with patch.object(cp,'strict_json',side_effect=[dict(schema_version='GENUINE_HOSTED_FIXED_BUILD_V1',state='BUILD_PARTIAL_OR_FAILED_RETAINED')]):
            with self.assertRaises(s.StoreError):self.collect()
        files,_,_=self.collect();self.assertEqual(len(files),78)
    def test_preparation_and_unapproved_procedure_read_no_credentials(self):
        class NoEnvironment:
            def get(self,*a):raise AssertionError('credentials read')
        with redirect_stdout(io.StringIO()):self.assertEqual(cli.main(['produce'],environ=NoEnvironment()),2)
        body=(ROOT/'config/gha-private-checkpoint-v1.json').read_bytes()
        # Preserve the negative gate after root seals the real procedure.
        unapproved=json.loads(body);unapproved['state']='FICTIONAL_UNAPPROVED'
        rejected=s.canonical(unapproved)
        with patch.object(cli,'read',return_value=rejected),self.assertRaisesRegex(ValueError,'NOT_APPROVED'):
            cli.verified(cli.sha(rejected))
        with retained_procedure(cli,'config/gha-private-checkpoint-v1.json'):
            self.assertEqual(cli.verified(cli.REGISTERED_CONFIG_SHA256)['state'],'ROOT_APPROVED_FOR_GENUINE_GHA')
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_SOURCE_PIN'):
            cli.verified(cli.REGISTERED_CONFIG_SHA256)
    def test_workflow_snippet_preserves_existing_mode_and_safe_boundaries(self):
        text=workflow_job((ROOT/'.github/workflows/lab.yml').read_text(),'genuine-hosted-fixed-build-restore-v1')
        self.assertIn('needs: genuine-hosted-fixed-build-v1',text);self.assertIn('persist-credentials: false',text)
        self.assertIn('ref: ${{ github.sha }}',text);self.assertIn('contents: write',text);self.assertIn('actions: read',text)
        self.assertNotIn('cron:',text);self.assertNotIn('uses: actions/upload-artifact',text);self.assertNotIn('ghp_',text)
        self.assertIn('timeout --signal=KILL 190s',text)


class ReservationMetadataCheck(unittest.TestCase):
    def test_safe_pretransport_intent_is_exact_and_has_no_body(self):
        body=b'FICTIONAL_NEVER_PRINT_THIS_PAYLOAD';name='blob-'+s.sha(body)+'.bin';q=cp.reservation_metadata('asset:'+name,body,name)
        self.assertEqual(q['bytes'],len(body));self.assertNotIn(body,s.canonical(q))
        self.assertEqual(set(q),{'schema_version','key','bytes','sha256','name'})
        with self.assertRaises(s.StoreError):cp.reservation_metadata('https://forbidden.invalid',body,name)
    def test_restore_bootstrap_is_exact_original_six_pin_subset(self):
        pins=(ROOT/'requirements-gha-private-checkpoint-v1.lock').read_text().splitlines();original=(ROOT/'requirements.lock').read_text().splitlines()
        self.assertEqual(len(pins),6);self.assertTrue(set(pins)<=set(original));self.assertFalse(any('sklearn' in p or 'catboost' in p for p in pins))


class ClaimGuardChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.journal=Path(self.temp.name);self.server=Server()
        initial=s.Client('ghs_FICTIONAL',RUN,journal=self.journal,source_sha=SOURCE,transport=self.server,process='e'*64)
        self.runtime=s.initialize(initial,'b'*32);self.q=qualification(self.runtime);self.server.calls.clear()
        stamp=datetime.now(timezone.utc);self.body=s.canonical(dict(schema_version='weekly-initial-remaining-v1-registration',state='FROZEN_ROOT_REGISTERED',slate_kind='INITIAL_REMAINING_ONE_TIME',maximum_uses=1,
            registered_at_utc=(stamp-timedelta(minutes=1)).isoformat(),input_cutoff_utc=(stamp+timedelta(hours=1)).isoformat()))
    def tearDown(self):self.temp.cleanup()
    def client(self,run_id=RUN,process='4'*64):
        job=dict(execution_lane='github_actions',workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',workflow_sha=SOURCE,job_id='store_create',permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
        def transport(req,timeout):
            if '/actions/runs/' in req.full_url:
                if '/jobs?' in req.full_url:return Response(dict(total_count=1,jobs=[dict(id=55,name='store_create',status='in_progress',run_id=int(run_id),head_sha=SOURCE)]))
                return Response(dict(id=int(run_id),head_sha=SOURCE,event='workflow_dispatch',run_attempt=1,status='in_progress',path='.github/workflows/lab.yml',repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO)))
            return self.server(req,timeout)
        c=s.Client('ghs_FICTIONAL',run_id,journal=self.journal,source_sha=SOURCE,transport=transport,process=process,job=job,operation='claim');c.authenticate_actions_job();c.bind(self.runtime);return c
    def claim(self,c):return cp.claim_once(c,self.body,self.q,expected_sha256=s.sha(self.body),procedure_sha256='d'*64)
    def test_exact_claim_full_readback_and_safe_receipt(self):
        receipt=self.claim(self.client());self.assertEqual(receipt['state'],'ONE_TIME_SOURCE_CLAIMED');self.assertEqual(receipt['registration_sha256'],s.sha(self.body))
        self.assertEqual(receipt['asset_name'],'manifest-'+s.sha(self.body)+'.json');self.assertNotIn('slate_kind',receipt)
        self.assertEqual(sum(r.method=='POST' for r in self.server.calls),1)
    def test_second_dispatch_same_initial_registration_rejected_before_POST(self):
        self.claim(self.client())
        with self.assertRaisesRegex(s.StoreError,'APPEND_ONLY_NAME_EXISTS'):self.claim(self.client('40099999991','5'*64))
        self.assertEqual(sum(r.method=='POST' for r in self.server.calls),1)
    def test_ambiguous_claim_is_retained_and_not_automatically_retried(self):
        self.server.ambiguous=True
        with self.assertRaises(s.StoreError):self.claim(self.client())
        self.assertTrue(list(self.journal.glob('*.reservation.json')))
        with self.assertRaises(s.StoreError):self.claim(self.client('40099999992','5'*64))
        self.assertEqual(sum(r.method=='POST' for r in self.server.calls),1)
    def test_unregistered_body_rejected_before_any_POST(self):
        doc=json.loads(self.body);doc['state']='PREPARED_NOT_REGISTERED';self.body=s.canonical(doc)
        with self.assertRaises(s.StoreError):self.claim(self.client())
        self.assertFalse(any(r.method=='POST' for r in self.server.calls))


if __name__=='__main__':unittest.main()
