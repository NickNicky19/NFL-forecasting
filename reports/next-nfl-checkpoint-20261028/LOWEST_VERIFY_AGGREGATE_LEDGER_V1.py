"""Structural/source-pointer checks only; no raw NFL inputs or models."""
from pathlib import Path
from collections import Counter
import hashlib,json,gzip,math
O=Path('/workspace/nfl-methods-integration/reports/next-nfl-checkpoint-20261028')
p=O/'LOWEST_ALL_METHOD_LEDGER_V1.json';b=p.read_bytes();x=json.loads(b);d=x['label_dictionaries'];docs={};source_checks=[]
for sid,ref in x['sources'].items():
 path=Path(ref['path']);v=path.read_bytes();status='EXACT_CURRENT_BYTES'
 if hashlib.sha256(v).hexdigest()!=ref['sha256']:
  assert hashlib.sha256(v[:ref['bytes']]).hexdigest()==ref['sha256']and path.name=='ledger.jsonl'
  v=v[:ref['bytes']];status='EXACT_RECORDED_APPEND_ONLY_LEDGER_PREFIX'
 assert len(v)==ref['bytes']
 source_checks.append({'source':sid,'state':status})
 if path.suffix=='.gz':docs[sid]=json.loads(gzip.decompress(v))
 elif path.suffix=='.json':docs[sid]=json.loads(v)
 else:docs[sid]=v.decode()
def point(sid,tokens):
 ptr='/'.join(d['pointer_tokens'][k]for k in d['pointer'][tokens]);a=docs[sid]
 if ptr.startswith('/line/'):
  line=int(ptr.rsplit('/',1)[1]);assert 1<=line<=len(a.splitlines());return ptr
 assert ptr.startswith('/')
 for k in ptr[1:].split('/'):
  k=k.replace('~1','/').replace('~0','~')
  a=a[int(k)]if isinstance(a,list)else a[k]
 return ptr
counts=Counter();pointer_checks=0;infinities=0
for i,r in enumerate(x['records']):
 assert len(r)==10
 panel,target,method,product,period=[d[key][r[j]]for j,key in enumerate(['panel','target','method','product','period'])]
 scores={x['score_keys'][k]:v for k,v in x['score_records'][r[5]]}
 cov={x['coverage_keys'][k]:v for k,v in x['coverage_records'][r[6]]}
 sid=d['source'][r[7]];point(sid,r[8]);pointer_checks+=1
 for v in scores.values():
  if isinstance(v,float):assert math.isfinite(v)
  if v=='POSITIVE_INFINITY':infinities+=1
 counts[target]+=1
for r in x['rankings']:
 ranking=d['ranking'][r[3]];metric={'A_numeric_MAE':'MAE','B_valid_mean_MSE':'MSE','C_full_law_CRPS':'CRPS','C_valid_median_MAE':'MAE','D_event_Brier':'Brier'}[ranking]
 for i in r[9]:
  source=x['records'][i];scores={x['score_keys'][k]:v for k,v in x['score_records'][source[5]]}
  assert scores[metric]==r[8]
assert len(b)<=1048576 and x['executed_now']['new_fits']==x['executed_now']['new_forecasts']==x['executed_now']['new_NFL_scoring_runs']==0
assert x['metadata_census']['private_attempt_census_complete']is False
out={'version':'lowest-all-method-aggregate-structural-acceptance-v1','state':'PASS','scope':'same-agent independent decoder/sourcepointer structural checks only; not NFL accuracy reproduction/private-data audit','ledger_bytes':len(b),'ledger_sha256':hashlib.sha256(b).hexdigest(),'source_checks':source_checks,'source_pointer_checks':pointer_checks,'target_record_counts':dict(counts),'ranked_leader_value_checks':sum(len(r[9])for r in x['rankings']),'records':len(x['records']),'new_NFL_fits_predictions_outcome_scoring_model_loads_HTTP':0,'original17_artifact_hash_checks_all_pass':all(v.get('byte_hash_matches')for v in x['metadata_census']['dated_private_entries']),'limitations':'Source-declared cohort comparability was not reverified from private player keys. Null logloss with positive-infinity count stays unavailable/infinite rather than finite. Canonicalledger uses exact recorded prefix if legitimately appended.'}
q=O/'LOWEST_AGGREGATE_ACCEPTANCE_V1.json';q.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in ['source_checks','target_record_counts']},sort_keys=True))
