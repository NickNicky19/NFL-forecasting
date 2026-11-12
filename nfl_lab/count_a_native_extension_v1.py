"""Optional retained Count A shadow component of the existing weekly producer.

No import loads a model, source, credential or native namespace. The existing
producer owns the live Root/API proof, owned references, source and sink. This
component never adds a nineteenth generic slot, selects picks or publishes.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib,io,json,math,re,zipfile

VERSION='count-a-native-shadow-v1'
FIELD='count_a_mean_shadow'
PRODUCT='pass_td__COUNT_A_MEAN'
PROCEDURE='f8607aa99a94c7c1c9ab5c89599e07eba9b15527749b092b225f368032881e83'
PARENT='9c48aab650f35a60631fd5d6af2cef4b8c513416fe0f9b2c61591d7f8af4b85f'
MODEL='4d277e3e3986d712a86d9a55019e35f2e5b5c58d6f4f411af0a0abc65da1b62d'
CAPSULE='5f55367c9f3389dbbe713b1aa95e691e77602cde99bf8e5ff657554a2d5a6a36'
PROOF='9071f4fd5f81fb7e0514e9f1ac47a93d207fc5b27cda3d8aa7f7ea16d320b45e'
ADAPTER='a3b44ee5c7937e830d0c2693d3fa55b0fed52c9cba51ae5058c04b2e7075b527'
CORRECTOR='aa7c002506b57d7c1ca643f4236e5fb8b5132bebb00ad86720ee11221b6d9fb6'
MEMBERS={
 'CELL_COMPLETE.json':(859,'8612a6157d4de635677301fe7128a6314471efa33956976fefd5baf6311407ee'),
 'FIXTURE_EXPECTED.parquet':(15916,'f9d83fdbb9d8b8d16ef89a9c537ad3fa97c14320573dc6a2782637d07d025c9e'),
 'FIXTURE_FEATURES.parquet':(46058,'cac7a18d0a679441d10418381b67290438957ef721425e5f4a318abdda0e0216'),
 'FORECASTS.parquet':(26771,'8d801a6b276a8ba800311a72abba6e13e1f051db9d3959bab596495913fe7a39'),
 'MODEL.joblib':(298952,MODEL),
 'MODEL_AUDIT.json':(8898,'a7679510ccae33d4f915f6bd70988090d279818bbf2934dc6f25654248cd0dc1')}
HELPERS=('nfl_lab/count_a_native_extension_v1.py','nfl_lab/count_a_mean_export_adapter_v1.py','tools/modern_count_a_mean_v3.py')
KEYS={'schema_version','product','procedure_version','capsule','producer_proof','fit_start','helper_pins','source_contract_sha256','source_config_sha256','maximum_query_rows','maximum_new_bytes','public_release','ranking_policy_change','publication'}
FILES={'count-a-mean-shadow/CAPTURE.json','count-a-mean-shadow/ROWS.jsonl'}
ROW_FIELDS=('season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc','expected_mean','selection_point','fallback_reason','value_origin','prediction_functional','procedure_version','model_sha256','issued_at_UTC','expiry_UTC','probability','EV')

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def acceptance_sha(record):return sha(json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
def require(ok,why):
 if not ok:raise ValueError(why)
def instant(x):
 d=datetime.fromisoformat(str(x).replace('Z','+00:00'));require(d.tzinfo is not None,'COUNT_A_AWARE_CLOCK_REQUIRED');return d.astimezone(timezone.utc)
def strict(body):
 def unique(pairs):
  out={}
  for k,v in pairs:require(k not in out,'COUNT_A_DUPLICATE_JSON_KEY');out[k]=v
  return out
 return json.loads(body,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(ValueError('COUNT_A_NONFINITE_JSON')))
def reference(r,n,h):return type(r)is dict and set(r)=={'path','bytes','sha256'}and type(r['path'])is str and r['bytes']==n and r['sha256']==h
def validate_metadata(root,source_root):
 """An optional closed Root field, covered by the original complete Root hash."""
 if FIELD not in root:return None
 r=root[FIELD];require(type(r)is dict and set(r)==KEYS,'COUNT_A_CLOSED_EXTENSION')
 require(r['schema_version']==VERSION and r['product']==PRODUCT and r['procedure_version']==PROCEDURE,'COUNT_A_EXACT_PRODUCT')
 require(reference(r['capsule'],399037,CAPSULE)and reference(r['producer_proof'],26032,PROOF),'COUNT_A_EXACT_ORIGINAL_OWNED_ARTIFACT_REFS')
 f=r['fit_start'];require(type(f)is dict and set(f)=={'path','bytes','sha256'}and type(f['bytes'])is int and 0<f['bytes']<=65536 and re.fullmatch('[a-f0-9]{64}',str(f['sha256'])),'COUNT_A_BOUND_FIT_START_REQUIRED')
 require(r['maximum_query_rows']==1000 and r['maximum_new_bytes']==(2<<20)and type(r['public_release'])is bool and r['ranking_policy_change']is False,'COUNT_A_SHADOW_ONLY_FIXED_LIMITS')
 require(re.fullmatch('[a-f0-9]{64}',str(r['source_contract_sha256']))is not None,'COUNT_A_BOUND_SOURCE_CONTRACT')
 require(r['source_config_sha256']==sha(canonical(root['source_config'])),'COUNT_A_SAME_SOURCE_CONFIG')
 require(type(r['helper_pins'])is dict and set(r['helper_pins'])==set(HELPERS),'COUNT_A_CLOSED_HELPER_CENSUS')
 for f in HELPERS:
  p=Path(source_root)/f;require(p.is_file()and not p.is_symlink()and p.resolve().is_relative_to(Path(source_root).resolve())and p.stat().st_size<=65536 and sha(p.read_bytes())==r['helper_pins'][f],'COUNT_A_EXACT_HELPER_BYTES')
 require(r['helper_pins'][HELPERS[1]]==ADAPTER and r['helper_pins'][HELPERS[2]]==CORRECTOR,'COUNT_A_UNCHANGED_ADAPTER_CORRECTOR')
 publication(r,root)
 return r
def publication(r,root):
 g=r['publication']
 if not r['public_release']:
  require(g is None,'COUNT_A_NO_IMPLICIT_PUBLICATION');return None
 require(type(g)is dict and set(g)=={'schema_version','authority_kind','scope','source_policy_sha256','source_review_sha256','public_fields','public_prefix','raw_or_weights_public','primary_activation','ranking_change'}and g['schema_version']==VERSION+'-publication'and g['authority_kind']=='ROOT_APPROVED_DERIVED_PUBLICATION'and g['scope']=='DERIVED_QB_MEAN_SHADOW_ONLY'and g['source_policy_sha256']=='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441'and re.fullmatch('[a-f0-9]{64}',str(g['source_review_sha256']))and g['public_fields']==list(ROW_FIELDS)and g['public_prefix']=='public/count-a-mean-shadow-v1/'and g['raw_or_weights_public']is g['primary_activation']is g['ranking_change']is False and root.get('publication')is True,'COUNT_A_EXACT_REGISTERED_DERIVED_SHADOW_GRANT')
 return g
def authenticate_capsule(body):
 """Bound all members before any trusted deserialization; never extract paths."""
 require(type(body)is bytes and len(body)==399037 and sha(body)==CAPSULE,'COUNT_A_CAPSULE_BYTES')
 with zipfile.ZipFile(io.BytesIO(body))as z:
  infos=z.infolist();names=[x.filename for x in infos]
  require(len(names)==len(set(names))==7 and set(names)==set(MEMBERS)|{'MEMBER_MANIFEST.json'},'COUNT_A_CLOSED_ZIP_MEMBERS')
  require(sum(x.file_size for x in infos)<=512<<10 and all(not x.is_dir()and not x.flag_bits&1 and x.compress_type in {zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED}and (x.external_attr>>16)&0o170000!=0o120000 for x in infos),'COUNT_A_BOUNDED_ZIP_ONLY')
  out={x.filename:z.read(x)for x in infos}
 mm=strict(out['MEMBER_MANIFEST.json'])['members'];require(set(mm)==set(MEMBERS),'COUNT_A_MEMBER_MANIFEST_CENSUS')
 for n,(size,h)in MEMBERS.items():require(len(out[n])==size and sha(out[n])==h and mm[n]['bytes']==size and mm[n]['sha256']==h,'COUNT_A_MEMBER_BYTES')
 return out
def authenticate_fit(proof_body,fit_body,registration,audit):
 require(len(proof_body)==26032 and sha(proof_body)==PROOF,'COUNT_A_ORIGINAL_PRODUCER_PROOF')
 proof=strict(proof_body);fit=strict(fit_body);ref=registration['fit_start'];record=proof['artifacts']['pass_td__COUNT_A_MEAN/FIT_START.json']
 require(len(fit_body)==ref['bytes']==record['bytes']and sha(fit_body)==ref['sha256']==record['sha256'],'COUNT_A_ORIGINAL_FIT_START')
 recipe=fit['recipe'];require(sha(canonical(recipe)+b'\n')==PARENT==audit['recipe_sha256'],'COUNT_A_ORIGINAL_RECIPE')
 require(recipe['training_cutoff_utc']=='2026-09-01T00:00:00Z'and recipe['source_pins']['mean_corrector']['sha256']==CORRECTOR,'COUNT_A_ORIGINAL_TRAINING_CLOCK_CORRECTOR')
 return recipe
def allowed_runtime_name(name):return name in FILES
def projection(rows):
 """Typed derived shadow rows only; not an authority to publish or activate."""
 out=[]
 for r in rows:
  require(set(r)==set(ROW_FIELDS)and r['position']=='QB'and r['procedure_version']==PROCEDURE and r['model_sha256']==MODEL and r['probability']is r['EV']is None,'COUNT_A_TYPED_SHADOW_ROWS')
  require(r['expected_mean']==r['selection_point']and(r['expected_mean']is None or(type(r['expected_mean'])in[int,float]and math.isfinite(r['expected_mean'])and r['expected_mean']>=0)),'COUNT_A_FINITE_MEAN_OR_NULL')
  require(instant(r['issued_at_UTC'])<instant(r['cutoff_utc'])<=instant(r['kickoff_utc'])and instant(r['issued_at_UTC'])<instant(r['expiry_UTC'])<=instant(r['cutoff_utc']),'COUNT_A_REAL_ISSUE_EXPIRY_HORIZON')
  out.append({k:r[k]for k in ROW_FIELDS})
 return dict(schema_version=VERSION+'-derived',state='SHADOW_NOT_PRIMARY_NOT_PICKS',product=PRODUCT,rows=out,probability=None,EV=None,public_export_authorized=False)

class BoundShadow:
 def __init__(self,backend,native):
  from .weekly_mae_display_runtime_v1 import NativeContext
  require(type(native)is NativeContext,'COUNT_A_REAL_NATIVE_CONTEXT_REQUIRED');native.verify()
  self.backend,self.native=backend,native;self.registration=validate_metadata(native.root,native.source_root)
  require(self.registration is not None and backend.config==native.root['source_config']and sha(canonical(backend.contract))==self.registration['source_contract_sha256'],'COUNT_A_CURRENT_ROOT_SOURCE_REQUIRED')
 def capture(self,features,capture,capture_ref,source,sink,output):
  """Called only after original18 capture and its existing source/API guards."""
  from . import audit_weekly_runtime_v1 as runtime
  self.native.verify();self.backend.check();r=self.registration
  require(validate_metadata(self.native.root,self.native.source_root)==r,'COUNT_A_LIVE_HELPER_BINDINGS_CHANGED')
  from .count_a_mean_export_adapter_v1 import predict_verified_mean
  from tools.modern_count_a_mean_v3 import correct_fallbacks
  require(capture['source_contract']==self.backend.contract and instant(capture['feature_persist_completed_at'])<=self.backend.clock(),'COUNT_A_FEATURE_CAPTURE_REQUIRED')
  require(source['state']=='FRESH_E7_SOURCE_PREPARED'and source['manifest']['request']['allowed_periods']==self.backend.config['allowed_periods'],'COUNT_A_QUALIFIED_CURRENT_SOURCE_REQUIRED')
  members=authenticate_capsule(runtime.read_owned(self.backend.storage,r['capsule'],399037,raw=True));audit=strict(members['MODEL_AUDIT.json'])
  recipe=authenticate_fit(runtime.read_owned(self.backend.storage,r['producer_proof'],26032,raw=True),runtime.read_owned(self.backend.storage,r['fit_start'],65536,raw=True),r,audit)
  import joblib,numpy as np,pandas as pd,pyarrow,scipy,sklearn
  from .role_boosting import RoleCountBoostingModel
  versions=dict(joblib=joblib.__version__,numpy=np.__version__,pandas=pd.__version__,pyarrow=pyarrow.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__)
  require(all(audit['environment'][k]==v for k,v in versions.items()),'COUNT_A_EXACT_RESTORATION_ENVIRONMENT')
  model=joblib.load(io.BytesIO(members['MODEL.joblib']))
  require(type(model)is RoleCountBoostingModel and model.variant=='A'and model.category==audit['category']and model.category['target']=='pass_td'and model.category['support']=='count','COUNT_A_TRUSTED_TYPE_CATEGORY')
  for b in [model.training_binding,model.prior_training_binding]:
   require(b is not None,'COUNT_A_ORIGINAL_TRAINING_BINDING');clocks=pd.to_datetime(b.outcome_available_utc,utc=True,errors='coerce');require(clocks.notna().all()and(clocks<pd.Timestamp(recipe['training_cutoff_utc'])).all(),'COUNT_A_EARLIER_TRAINING_LABELS')
  frame=features.loc[features.position.eq('QB')].copy();require(0<len(frame)<=r['maximum_query_rows'],'COUNT_A_COMPLETE_QB_QUERY_POPULATION')
  typed=predict_verified_mean(model,frame,mean_corrector=correct_fallbacks,binding=dict(model_sha256=MODEL,parent_procedure_version=PARENT,training_cutoff_utc=recipe['training_cutoff_utc']))
  issued=self.backend.clock();rows=[]
  for x in typed.to_dict('records'):
   row={k:x.get(k)for k in ROW_FIELDS};row.update(issued_at_UTC=issued.isoformat(),expiry_UTC=str(x['cutoff_utc']))
   for k in ['kickoff_utc','cutoff_utc']:row[k]=str(row[k])
   for k in ['expected_mean','selection_point']:row[k]=float(row[k])if np.isfinite(row[k])else None
   rows.append(row)
  derived=projection(rows);body=b''.join(canonical(x)+b'\n'for x in derived['rows']);require(len(body)<=r['maximum_new_bytes'],'COUNT_A_EXTRA_BYTE_CAP')
  folder=Path(output)/'count-a-mean-shadow';sink.write_bytes(folder/'ROWS.jsonl',body)
  from .weekly_future_inference import binding as file_binding
  require(runtime.read_owned(self.backend.storage,file_binding(folder/'ROWS.jsonl'),2<<20,raw=True)==body,'COUNT_A_LOCAL_PERSISTENCE_READBACK')
  persisted=self.backend.clock();require(all(persisted<instant(x['cutoff_utc'])for x in rows),'COUNT_A_PERSISTENCE_BEFORE_CUTOFF')
  receipt=dict(schema_version=VERSION+'-capture',state='PRIVATE_SHADOW_CAPTURE_REQUIRES_NATIVE_RESTORE',rows=len(rows),row_sha256=sha(body),model_sha256=MODEL,procedure_version=PROCEDURE,capsule_sha256=CAPSULE,feature_capture=capture_ref,source_config_sha256=r['source_config_sha256'],root_go_sha256=self.native.root_sha256,actual_issued_at_UTC=issued.isoformat(),actual_local_rows_persisted_at_UTC=persisted.isoformat(),public_export_authorized=False,primary_activation=False,ranking_policy_change=False)
  sink.write_bytes(folder/'CAPTURE.json',canonical(receipt));self.native.verify();return receipt


def validate_archive(snapshot,path,root,*,complete):
 names={f["logical_path"]for f in snapshot["files"]};expected={"runtime/"+n for n in FILES};found={n for n in names if n.startswith("runtime/count-a-mean-shadow/")}
 if FIELD not in root:
  require(not found,"COUNT_A_ARCHIVE_WITHOUT_ROOT_BINDING");return None
 require(found<=expected and(not complete or found==expected),"COUNT_A_COMPLETE_CLOSED_ARCHIVE")
 if found!=expected:return dict(state="FAILED_OR_PARTIAL_SHADOW_RETAINED",public_export_authorized=False)
 body=Path(path("runtime/count-a-mean-shadow/ROWS.jsonl")).read_bytes();require(len(body)<=root[FIELD]["maximum_new_bytes"],"COUNT_A_ARCHIVE_CAP")
 cap=Path(path("runtime/count-a-mean-shadow/CAPTURE.json"));require(cap.stat().st_size<=65536,"COUNT_A_RECEIPT_CAP");doc=strict(cap.read_bytes())
 require(doc["schema_version"]==VERSION+"-capture"and doc["root_go_sha256"]==sha(canonical(root))and doc["row_sha256"]==sha(body)and doc["model_sha256"]==MODEL and doc["procedure_version"]==PROCEDURE and doc["capsule_sha256"]==CAPSULE,"COUNT_A_CAPTURE_ROOT_AND_BODY")
 rows=[strict(x)for x in body.splitlines()];require(len(rows)==doc["rows"]<=1000,"COUNT_A_COMPLETE_ROWS");projection(rows)
 return dict(state="PRIVATE_TYPED_SHADOW_VERIFIED",rows=len(rows),public_export_authorized=False,primary_activation=False)


def count_a_shadow_projection(live,root,*,at):
 """Derive shadow rows only from the genuine accepted owned archive aliases."""
 from .audit_weekly_public_v1 import LiveAcceptance
 from . import audit_weekly_archive_v1 as archive
 require(type(live)is LiveAcceptance,"COUNT_A_IN_MEMORY_LIVE_ACCEPTANCE");live.verify()
 require(FIELD in root,"COUNT_A_REGISTERED_DURABLE_OWNER_ROOT")
 aliases=live.inputs["aliases"];storage=live.inputs["storage"]
 def path(name):
  require(name in aliases,"COUNT_A_SEALED_ALIAS_REQUIRED")
  ref=aliases[name];archive.read_owned(storage,ref,2<<20,raw=True);return ref["path"]
 snapshot=dict(files=[dict(logical_path=n)for n in aliases])
 # LiveAcceptance seals the owned alias inventory; CAPTURE binds this exact Root.
 validate_archive(snapshot,path,root,complete=True)
 body=archive.read_owned(storage,aliases["runtime/count-a-mean-shadow/ROWS.jsonl"],2<<20,raw=True)
 result=projection([strict(line)for line in body.splitlines()])
 result.update(native_acceptance_sha256=acceptance_sha(live.record),durable_root_go_sha256=sha(canonical(root)),verified_at=at,public_export_authorized=False)
 return result


def public_pair(document,live_record,root,created):
 """Pure formatting after in-memory native acceptance; no local/public write."""
 import gzip
 grant=publication(root[FIELD],root);require(grant is not None,'COUNT_A_PUBLICATION_NOT_REGISTERED')
 checked=projection(document['rows']);rows=checked['rows'];require(rows and len(rows)<=1000,'COUNT_A_NONEMPTY_PUBLIC_ROWS')
 root_sha=sha(canonical(root))
 seasons={x['season']for x in rows};weeks={x['week']for x in rows};require(len(seasons)==len(weeks)==1,'COUNT_A_ONE_PERIOD')
 require(instant(created)>=max(instant(x['issued_at_UTC'])for x in rows)and instant(created)>=instant(live_record['accepted_at']),'COUNT_A_EXPORT_AFTER_ORIGINAL_ISSUE_AND_NATIVE_ACCEPTANCE')
 doc=dict(checked,participation_conditioning='CONDITIONAL_ON_QUALIFIED_PLAYED_HISTORY; source role/participation uncertainty and prior/incumbent fallback remain explicit; no unconditional participation probability',created_at=created,current_use_status='EXPIRED_OR_PARTIALLY_EXPIRED'if any(instant(x['expiry_UTC'])<=instant(created)for x in rows)else'CURRENT_SHADOW_FORECAST_ONLY',is_current_recommendation=False,source_policy_sha256=grant['source_policy_sha256'],root_go_sha256=root_sha,model_sha256=MODEL,procedure_version=PROCEDURE,native_acceptance_sha256=acceptance_sha(live_record))
 body=canonical(doc);h=sha(body);stamp=instant(created).strftime('%Y%m%dT%H%M%S.%fZ');prefix=grant['public_prefix']+f"{next(iter(seasons))}-W{next(iter(weeks)):02d}/"
 receipt=dict(schema_version=VERSION+'-publication-receipt',feed_sha256=h,feed_bytes=len(body),rows=len(rows),root_go_sha256=root_sha,native_acceptance_sha256=doc['native_acceptance_sha256'],publication_grant_sha256=sha(canonical(grant)),created_at=created,model_sha256=MODEL,procedure_version=PROCEDURE,primary_activation=False,ranking_change=False,raw_or_weights_public=False)
 return {prefix+stamp+'--'+h+'.json':body,prefix+h+'.json.gz':gzip.compress(canonical(receipt),mtime=0)}
def validate_public_files(state,files,live,root,source_policy_sha256):
 """Called by existing state publisher; serialized flags cannot replace live."""
 from .audit_weekly_public_v1 import LiveAcceptance
 require(type(live)is LiveAcceptance,'COUNT_A_IN_MEMORY_LIVE_ACCEPTANCE');live.verify();grant=publication(root[FIELD],root)
 require(grant is not None and grant['source_policy_sha256']==source_policy_sha256 and len(files)==2,'COUNT_A_EXACT_PUBLIC_PAIR')
 refs=[n for n in files if n.endswith('.json')];require(len(refs)==1,'COUNT_A_ONE_PUBLIC_FEED');body=Path(state,refs[0]).read_bytes();require(len(body)<=2<<20 and sha(body)==files[refs[0]],'COUNT_A_PUBLIC_FEED_BYTES');doc=strict(body)
 require(instant(doc['created_at'])<=datetime.now(timezone.utc),'COUNT_A_NO_FUTURE_EXPORT_CLOCK')
 durable=count_a_shadow_projection(live,root,at=doc['created_at'])
 expected=public_pair(durable,live.record,root,doc['created_at']);require(set(expected)==set(files)and all(sha(v)==files[n]and Path(state,n).read_bytes()==v for n,v in expected.items()),'COUNT_A_EXACT_REVIEWED_PUBLIC_BYTES')
 return files
