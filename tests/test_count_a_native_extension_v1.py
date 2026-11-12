"""Synthetic software fixtures only: no NFL capsule/model/source/native namespace."""
from pathlib import Path
import ast,copy,importlib.util,json,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('counta_extension_under_review',ROOT/'nfl_lab/count_a_native_extension_v1.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def fixture():
 r=dict(schema_version=m.VERSION,product=m.PRODUCT,procedure_version=m.PROCEDURE,capsule=dict(path='/synthetic-owned/capsule',bytes=399037,sha256=m.CAPSULE),producer_proof=dict(path='/synthetic-owned/proof',bytes=26032,sha256=m.PROOF),fit_start=dict(path='/synthetic-owned/fit',bytes=300,sha256='1'*64),helper_pins={n:m.sha((ROOT/n).read_bytes())for n in m.HELPERS},source_contract_sha256='2'*64,source_config_sha256=m.sha(m.canonical({'purpose':'CURRENT_OPERATIONAL_INFERENCE'})),maximum_query_rows=1000,maximum_new_bytes=2<<20,public_release=False,ranking_policy_change=False,publication=None)
 return dict(schema_version='audit-weekly-hosted-v5-root-GO',approved=True,issued_at_utc='2026-11-12T00:00:00Z',expires_at_utc='2026-11-12T01:00:00Z',source_config={'purpose':'CURRENT_OPERATIONAL_INFERENCE'},code_pins={f'legacy_{i:03}':'3'*64 for i in range(128)},count_a_mean_shadow=r)
def typed(value=1.5):
 r={k:None for k in m.ROW_FIELDS};r.update(season=2026,week=10,game_id='SYNTHETIC_EVENT',player_id='SYNTHETIC_QB',team='AAA',opponent='BBB',position='QB',kickoff_utc='2026-11-13T01:15:00Z',cutoff_utc='2026-11-12T23:45:00Z',expected_mean=value,selection_point=value,fallback_reason='',value_origin='LEARNED_POISSON_OBJECTIVE_MEAN',prediction_functional='MEAN_OBJECTIVE_POINT',procedure_version=m.PROCEDURE,model_sha256=m.MODEL,issued_at_UTC='2026-11-12T22:00:00Z',expiry_UTC='2026-11-12T23:45:00Z')
 return r

class Component(unittest.TestCase):
 def test_complete_metadata_and_real_issuance_fields_fit_wire(self):
  r=fixture();t=ast.parse((ROOT/'nfl_lab/audit_weekly_template_v1.py').read_text());env={'require':m.require}
  for n in t.body:
   if isinstance(n,ast.Assign)and any(isinstance(x,ast.Name)and x.id in ['ROOT_KEYS','ROOT_V3','ROOT_V3_KEYS','ROOT_V4','ROOT_V4_KEYS','ROOT_V5','ROOT_V5_KEYS']for x in n.targets):exec(compile(ast.Module(body=[n],type_ignores=[]),'bound-template','exec'),env)
  r={k:r.get(k,'SYNTHETIC_UNAUTHENTICATED_METADATA')for k in env['ROOT_V5_KEYS']|{m.FIELD}};self.assertEqual(m.validate_metadata(r,ROOT),r[m.FIELD]);body=m.canonical(r);self.assertLessEqual(len(body),61440);self.assertEqual(len(r['code_pins']),128);self.assertIn(b'issued_at_utc',body);self.assertIn(b'expires_at_utc',body)
 def test_root_canonical_unicode_uses_existing_private_protocol(self):
  r=fixture();r['owner_note']='é';body=json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode();self.assertEqual(m.canonical(r),body);self.assertIn(b'\\u00e9',body)
 def test_registered_public_shadow_pair_and_expiry(self):
  r=fixture();r['publication']=True;reg=r[m.FIELD];reg['public_release']=True;reg['publication']=dict(schema_version=m.VERSION+'-publication',authority_kind='ROOT_APPROVED_DERIVED_PUBLICATION',scope='DERIVED_QB_MEAN_SHADOW_ONLY',source_policy_sha256='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441',source_review_sha256='4'*64,public_fields=list(m.ROW_FIELDS),public_prefix='public/count-a-mean-shadow-v1/',raw_or_weights_public=False,primary_activation=False,ranking_change=False)
  self.assertEqual(m.validate_metadata(r,ROOT),reg);live=dict(root_go_sha256=m.sha(m.canonical(r)),accepted_at='2026-11-12T22:01:00Z');d=m.projection([typed()]);pair=m.public_pair(d,live,r,'2026-11-12T22:02:00Z');self.assertEqual(len(pair),2);doc=m.strict(next(v for k,v in pair.items()if k.endswith('.json')));self.assertEqual(doc['rows'][0]['issued_at_UTC'],typed()['issued_at_UTC']);self.assertEqual(doc['current_use_status'],'CURRENT_SHADOW_FORECAST_ONLY')
  late=m.public_pair(d,live,r,'2026-11-14T00:00:00Z');self.assertEqual(m.strict(next(v for k,v in late.items()if k.endswith('.json')))['current_use_status'],'EXPIRED_OR_PARTIALLY_EXPIRED')
  self.assertFalse(doc['is_current_recommendation']);reg['publication']['primary_activation']=True
  with self.assertRaises(ValueError):m.public_pair(d,live,r,'2026-11-12T22:02:00Z')
 def test_actual_public_entrypoint_rejects_rehashed_changed_mean(self):
  import types,sys,datetime
  r=fixture();r['publication']=True;reg=r[m.FIELD];reg['public_release']=True;reg['publication']=dict(schema_version=m.VERSION+'-publication',authority_kind='ROOT_APPROVED_DERIVED_PUBLICATION',scope='DERIVED_QB_MEAN_SHADOW_ONLY',source_policy_sha256='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441',source_review_sha256='4'*64,public_fields=list(m.ROW_FIELDS),public_prefix='public/count-a-mean-shadow-v1/',raw_or_weights_public=False,primary_activation=False,ranking_change=False)
  now=datetime.datetime.now(datetime.timezone.utc);row=typed();row.update(issued_at_UTC=(now-datetime.timedelta(minutes=10)).isoformat(),cutoff_utc=(now+datetime.timedelta(minutes=50)).isoformat(),expiry_UTC=(now+datetime.timedelta(minutes=50)).isoformat(),kickoff_utc=(now+datetime.timedelta(minutes=90)).isoformat())
  class Live:
   def verify(self):return True
  live=Live();live.record=dict(root_go_sha256=m.sha(m.canonical(r)),accepted_at=(now-datetime.timedelta(minutes=1)).isoformat());created=(now-datetime.timedelta(seconds=1)).isoformat()
  with tempfile.TemporaryDirectory()as tmp:
   base=Path(tmp);body=m.canonical(row)+b'\n';(base/'ROWS.jsonl').write_bytes(body);cap=dict(schema_version=m.VERSION+'-capture',root_go_sha256=live.record['root_go_sha256'],row_sha256=m.sha(body),model_sha256=m.MODEL,procedure_version=m.PROCEDURE,capsule_sha256=m.CAPSULE,rows=1);(base/'CAPTURE.json').write_bytes(m.canonical(cap));aliases={f'runtime/count-a-mean-shadow/{n}':dict(path=str(base/n),bytes=(base/n).stat().st_size,sha256=m.sha((base/n).read_bytes()))for n in ['ROWS.jsonl','CAPTURE.json']};live.inputs=dict(aliases=aliases,storage=None)
   def owned(storage,ref,cap,raw=False):
    b=Path(ref['path']).read_bytes();self.assertLessEqual(len(b),cap);self.assertEqual(m.sha(b),ref['sha256']);return b if raw else m.strict(b)
   env=dict(require=m.require,LiveAcceptance=Live,feed=types.SimpleNamespace(digest=lambda x:m.sha(m.canonical(x))),archive=types.SimpleNamespace(read_owned=owned))
   node=next(x for x in ast.parse((ROOT/'nfl_lab/audit_weekly_public_v1.py').read_text()).body if isinstance(x,ast.FunctionDef)and x.name=='count_a_shadow_projection');exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-source-entrypoint','exec'),env)
   pub=types.ModuleType('nfl_lab.audit_weekly_public_v1');pub.LiveAcceptance=Live;pub.count_a_shadow_projection=env['count_a_shadow_projection'];pkg=types.ModuleType('nfl_lab');pkg.__path__=[];names={'nfl_lab':pkg,'nfl_lab.audit_weekly_public_v1':pub,'nfl_lab.count_a_native_extension_v1':m};old={k:sys.modules.get(k)for k in names};package=m.__package__;original_spec=m.__spec__;sys.modules.update(names);m.__package__='nfl_lab';m.__spec__=importlib.util.spec_from_loader('nfl_lab.count_a_native_extension_v1',loader=None);env['__package__']='nfl_lab'
   try:
    document=pub.count_a_shadow_projection(live,r,at=created);pair=m.public_pair(document,live.record,r,created)
    def stage(pp):
     for n,b in pp.items():(base/n).parent.mkdir(parents=True,exist_ok=True);(base/n).write_bytes(b)
     return {n:m.sha(b)for n,b in pp.items()}
    files=stage(pair);self.assertEqual(m.validate_public_files(base,files,live,r,reg['publication']['source_policy_sha256']),files)
    changed=copy.deepcopy(document);changed['rows'][0]['expected_mean']=changed['rows'][0]['selection_point']=99.;bad=stage(m.public_pair(changed,live.record,r,created))
    with self.assertRaises(ValueError):m.validate_public_files(base,bad,live,r,reg['publication']['source_policy_sha256'])
   finally:
    m.__package__=package;m.__spec__=original_spec
    for k,v in old.items():
     if v is None:sys.modules.pop(k,None)
     else:sys.modules[k]=v
 def test_existing_delivery_and_publisher_reachability(self):
  src=(ROOT/'nfl_lab/audit_weekly_delivery_v1.py').read_text();self.assertIn('public.count_a_shadow_projection(live,display_profile.root',src);self.assertIn('count_a_shadow_context=(live,display_profile.root)',src)
  src=(ROOT/'tools/persist_state.py').read_text();self.assertIn('validate_public_files(state,files,*count_a_shadow_context',src)
 def test_all_source_override_parsers_include_only_named_path(self):
  src=(ROOT/'nfl_lab/audit_weekly_grade_history_v1.py').read_text();body=src[src.index('def _source_history_body'):src.index('def source_history_envelope')];self.assertIn('nfl_lab/audit_weekly_public_v1.py',body)
 def test_absent_extension_preserves_legacy(self):self.assertIsNone(m.validate_metadata({},ROOT))
 def test_tampered_registration_fields(self):
  for field,value in [('product','wrong'),('procedure_version','0'*64),('maximum_query_rows',1001),('public_release',True),('ranking_policy_change',True),('source_config_sha256','0'*64)]:
   with self.subTest(field=field):
    r=fixture();r[m.FIELD][field]=value
    with self.assertRaises(ValueError):m.validate_metadata(r,ROOT)
 def test_unknown_root_extension_field(self):
  r=fixture();r[m.FIELD]['skip_source_guard']=True
  with self.assertRaises(ValueError):m.validate_metadata(r,ROOT)
 def test_wrong_capsule_or_proof(self):
  for key in ['capsule','producer_proof']:
   r=fixture();r[m.FIELD][key]['sha256']='0'*64
   with self.assertRaises(ValueError):m.validate_metadata(r,ROOT)
 def test_wrong_helper(self):
  r=fixture();r[m.FIELD]['helper_pins'][m.HELPERS[2]]='0'*64
  with self.assertRaises(ValueError):m.validate_metadata(r,ROOT)
 def test_no_untrusted_model_load(self):
  with self.assertRaises(ValueError):m.authenticate_capsule(b'not a trusted zip or pickle')
 def test_duplicate_json_and_nonfinite(self):
  for b in [b'{"a":1,"a":2}',b'{"a":NaN}']:
   with self.assertRaises(ValueError):m.strict(b)
 def test_valid_derived_mean_and_null(self):
  rows=[typed(),typed(None)];x=m.projection(rows);self.assertEqual(len(x['rows']),2);self.assertIsNone(x['rows'][1]['expected_mean']);self.assertFalse(x['public_export_authorized']);self.assertIsNone(x['probability'])
 def test_projection_tampering(self):
  for field,value in [('position','RB'),('probability',.9),('expected_mean',float('inf')),('selection_point',3),('issued_at_UTC','2026-11-13T00:01:00Z'),('expiry_UTC','2026-11-13T00:01:00Z')]:
   with self.subTest(field=field):
    r=typed();r[field]=value
    with self.assertRaises(ValueError):m.projection([r])
 def test_closed_archive_roundtrip_and_tamper(self):
  r=fixture();rows=[typed(),typed(None)];body=b''.join(m.canonical(x)+b'\n'for x in rows);cap=dict(schema_version=m.VERSION+'-capture',root_go_sha256=m.sha(m.canonical(r)),row_sha256=m.sha(body),model_sha256=m.MODEL,procedure_version=m.PROCEDURE,capsule_sha256=m.CAPSULE,rows=2)
  with tempfile.TemporaryDirectory()as tmp:
   p=Path(tmp);(p/'ROWS.jsonl').write_bytes(body);(p/'CAPTURE.json').write_bytes(m.canonical(cap));snapshot=dict(files=[dict(logical_path='runtime/'+x)for x in m.FILES]);lookup=lambda n:p/Path(n).name
   self.assertEqual(m.validate_archive(snapshot,lookup,r,complete=True)['rows'],2)
   (p/'ROWS.jsonl').write_bytes(body+b'{}\n')
   with self.assertRaises(ValueError):m.validate_archive(snapshot,lookup,r,complete=True)
 def test_no_unregistered_or_incomplete_archive(self):
  ss=dict(files=[dict(logical_path='runtime/count-a-mean-shadow/ROWS.jsonl')])
  with self.assertRaises(ValueError):m.validate_archive(ss,None,{},complete=True)
  with self.assertRaises(ValueError):m.validate_archive(ss,None,fixture(),complete=True)
 def test_root_parser_existing_code_and_unchanged18(self):
  tree=ast.parse((ROOT/'nfl_lab/audit_weekly_template_v1.py').read_text());env={'require':m.require}
  for n in tree.body:
   if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id in ['ROOT_KEYS','ROOT_V3','ROOT_V3_KEYS','ROOT_V4','ROOT_V4_KEYS','ROOT_V5','ROOT_V5_KEYS']for t in n.targets):exec(compile(ast.Module(body=[n],type_ignores=[]),'bound-template','exec'),env)
  fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='root_keys');exec(compile(ast.Module(body=[fn],type_ignores=[]),'bound-template','exec'),env)
  old={'schema_version':env['ROOT_V5']};self.assertEqual(env['root_keys'](old),env['ROOT_V5_KEYS']);new=fixture();self.assertEqual(env['root_keys'](new),env['ROOT_V5_KEYS']|{m.FIELD})
  src=(ROOT/'nfl_lab/audit_weekly_runtime_v1.py').read_text();self.assertIn('== len(aliases["models"]) == 18',src);self.assertIn('self._count_a_shadow.capture(features, capture, cref, source, sink, output)',src)
 def test_legacy_profile_keeps_original_change_set(self):
  src=(ROOT/'nfl_lab/weekly_mae_display_profile_v1.py').read_text();self.assertIn('if "count_a_mean_shadow" in root else CHANGED_LEGACY_PATHS',src);self.assertIn('len(root["code_pins"]) == 128',src)

if __name__=='__main__':unittest.main()
