"""Fictional opaque bytes only; no real model, owner token or GitHub request."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
import copy,json,tempfile,unittest
from unittest.mock import patch
from nfl_lab import count_a_native_extension_v1 as m
from nfl_lab import private_draft_store as private,owner_private_bootstrap as owner,owner_bootstrap_bundle as bundle
from nfl_lab.operational_storage import OperationalStorage
from tests.test_count_a_native_extension_v1 import fixture
ROOT=Path(__file__).resolve().parents[1]

class Materialization(unittest.TestCase):
 def setup_packet(self,tmp):
  base=Path(tmp);now=datetime.now(timezone.utc);root=fixture();root.update(source_sha='a'*40,jobs={'produce':'audit-weekly-produce-v1'},workflow_ref=private.REPO+'/.github/workflows/lab.yml@refs/heads/review',issued_at_utc=(now-timedelta(minutes=1)).isoformat(),expires_at_utc=(now+timedelta(minutes=20)).isoformat())
  r=root[m.FIELD];r['owner_restore']=dict(schema_version=m.VERSION+'-owner-restore',descriptor={'fixture':'SAFE_ID_METADATA_ONLY'},root_manifest_sha256='c'*64,owner_authorization_comment_id=12,maximum_materialization_bytes=1<<20,helper_pins={n:m.sha((ROOT/n).read_bytes())for n in m.OWNER_HELPERS})
  values={'capsule':b'C'*399037,'producer_proof':b'P'*26032,'fit_start':b'F'*300};files=[]
  for k,b in values.items():
   p=base/('original-'+k);p.write_bytes(b);r[k]=dict(path=str(p),bytes=len(b),sha256=m.sha(b));files.append(dict(logical_path=m.ORIGINALS[k],path=str(p),bytes=len(b),sha256=m.sha(b),kind='model'if k=='capsule'else'completion',origin=dict(source_path=str(p),source_sha256=m.sha(b),source_policy_sha256='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441'),required=True))
  body,inflated=bundle.encode(files);record=dict(files=files,bytes=len(body),sha256=m.sha(body),inflated_bytes=inflated)
  policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_text());storage=OperationalStorage(base/'cache',policy,state=base/'state');storage.register_root(base/'native')
  journal=base/'journal';journal.mkdir(mode=0o700);job=dict(execution_lane='github_actions',workflow_ref=root['workflow_ref'],workflow_sha=root['source_sha'],job_id=root['jobs']['produce'],permission='write',event_name='workflow_dispatch',api_job_id=123,run_authenticated=True)
  client=private.Client('ghs_FICTIONAL','12345',journal=journal,source_sha=root['source_sha'],job=job,transport=lambda *a,**k:(_ for _ in()).throw(AssertionError('NO_NETWORK_FIXTURE')))
  proof=dict(restore_run_id=client.run_id,execution_lane='github_actions',exact_remote_readback=True,separate_process=True,model_decodes=0,root_manifest_sha256='c'*64,owner_authorization_comment_id=12,origin_execution_lane='OWNER_BOOTSTRAP',origin_writer_run_id=None)
  return root,storage,client,body,record,proof,base/'native'/'count-a-originals'
 def test_opaque_originals_restore_and_resolve_without_root_rewrite(self):
  with tempfile.TemporaryDirectory()as tmp:
   root,storage,client,body,record,proof,dest=self.setup_packet(tmp);before=m.canonical(root)
   with patch.object(m,'CAPSULE',root[m.FIELD]['capsule']['sha256']),patch.object(m,'PROOF',root[m.FIELD]['producer_proof']['sha256']),patch.object(owner,'restore_owner_bundle',return_value=(body,record,proof))as restore:
    ref=m.materialize_owner_originals(root,ROOT,client,storage,dest);restore.assert_called_once()
    self.assertEqual(m.canonical(root),before);authority=dict(source_sha=client.source_sha,run_id=client.run_id,job_id=client.job['job_id'],api_job_id=123,workflow_ref=client.job['workflow_ref']);native=SimpleNamespace(root=root,source_root=ROOT,root_sha256=m.sha(before),authority=authority,verify=lambda:None)
    refs=m.resolved_originals(storage,ref,native);self.assertEqual(set(refs),set(m.ORIGINALS))
    for k,r in refs.items():self.assertEqual(Path(r['path']).read_bytes(),{'capsule':b'C'*399037,'producer_proof':b'P'*26032,'fit_start':b'F'*300}[k]);self.assertNotEqual(r['path'],root[m.FIELD][k]['path'])
    with self.assertRaisesRegex(ValueError,'COUNT_A_FRESH_OWNER_RESTORE_NO_RETRY'):m.materialize_owner_originals(root,ROOT,client,storage,dest)
    native.authority['run_id']='99999'
    with self.assertRaisesRegex(ValueError,'COUNT_A_CURRENT_JOB_MATERIALIZATION'):m.resolved_originals(storage,ref,native)
 def test_too_small_materialization_budget_fails_before_private_get(self):
  with tempfile.TemporaryDirectory()as tmp:
   root,storage,client,body,record,proof,dest=self.setup_packet(tmp);root[m.FIELD]['owner_restore']['maximum_materialization_bytes']=sum(root[m.FIELD][k]['bytes']for k in m.ORIGINALS)
   with patch.object(m,'CAPSULE',root[m.FIELD]['capsule']['sha256']),patch.object(m,'PROOF',root[m.FIELD]['producer_proof']['sha256']),patch.object(owner,'restore_owner_bundle')as restore:
    with self.assertRaisesRegex(ValueError,'COUNT_A_MATERIALIZATION_RESERVATION_TOO_SMALL'):m.materialize_owner_originals(root,ROOT,client,storage,dest)
    restore.assert_not_called();self.assertFalse(dest.exists())
 def test_rejects_extra_original_before_extraction(self):
  with tempfile.TemporaryDirectory()as tmp:
   root,storage,client,body,record,proof,dest=self.setup_packet(tmp);record['files'].append(copy.deepcopy(record['files'][0]))
   with patch.object(m,'CAPSULE',root[m.FIELD]['capsule']['sha256']),patch.object(m,'PROOF',root[m.FIELD]['producer_proof']['sha256']),patch.object(owner,'restore_owner_bundle',return_value=(body,record,proof)):
    with self.assertRaisesRegex(ValueError,'COUNT_A_THREE_ORIGINALS_ONLY'):m.materialize_owner_originals(root,ROOT,client,storage,dest)
   self.assertFalse(dest.exists())
 def test_rejects_wrong_current_source_before_private_get(self):
  with tempfile.TemporaryDirectory()as tmp:
   root,storage,client,body,record,proof,dest=self.setup_packet(tmp);client.source_sha='b'*40
   with patch.object(m,'CAPSULE',root[m.FIELD]['capsule']['sha256']),patch.object(m,'PROOF',root[m.FIELD]['producer_proof']['sha256']),patch.object(owner,'restore_owner_bundle')as restore:
    with self.assertRaisesRegex(ValueError,'COUNT_A_GENUINE_PARENT_RESTORE_CLIENT'):m.materialize_owner_originals(root,ROOT,client,storage,dest)
    restore.assert_not_called()
 def test_rejects_changed_registered_owner_helper(self):
  root=fixture();r=root[m.FIELD];r['owner_restore']=dict(schema_version=m.VERSION+'-owner-restore',descriptor={},root_manifest_sha256='c'*64,owner_authorization_comment_id=12,maximum_materialization_bytes=1<<20,helper_pins={n:m.sha((ROOT/n).read_bytes())for n in m.OWNER_HELPERS});r['owner_restore']['helper_pins'][m.OWNER_HELPERS[0]]='0'*64
  with self.assertRaisesRegex(ValueError,'COUNT_A_OWNER_SOURCE_BYTES'):m.validate_metadata(root,ROOT)
 def test_no_owner_descriptor_keeps_original_refs_without_private_get(self):
  root=fixture();native=SimpleNamespace(root=root,source_root=ROOT,verify=lambda:(_ for _ in()).throw(AssertionError('NO_NEW_LEGACY_IO')))
  self.assertEqual(m.resolved_originals(None,None,native),{k:root[m.FIELD][k]for k in m.ORIGINALS})
  with self.assertRaisesRegex(ValueError,'COUNT_A_NO_UNREGISTERED_MATERIALIZATION'):m.resolved_originals(None,{'unregistered':'receipt'},native)
 def test_offline_inference_remains_offline_and_catalog_remains18(self):
  runtime=(ROOT/'tools/audit_weekly_runtime_v1.py').read_text();self.assertIn('OFFLINE_INFERENCE_NO_HTTP_OR_CHILDREN',runtime);hosted=(ROOT/'nfl_lab/audit_weekly_hosted_v1.py').read_text();self.assertLess(hosted.index('request["count_a_materialization"]=materialize_owner_originals'),hosted.index('for phase in ("prepare","acquire","infer")'))
  self.assertIn('== len(aliases["models"]) == 18',(ROOT/'nfl_lab/audit_weekly_runtime_v1.py').read_text())

if __name__=='__main__':unittest.main()
