"""Independent cached 2025 aggregation checks; no law inference or bootstrap."""
import gzip,hashlib,io,json,math,sys,time,resource,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def enc(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def exact(r):
 p=Path(r['path']);a=p.stat();assert p.is_absolute() and p.resolve()==p and not any(x.is_symlink() for x in [p,*p.parents]);b=p.read_bytes();z=p.stat();assert len(b)==r['bytes']==a.st_size<=16*1024**2 and sha(b)==r['sha256'] and (a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_ino,z.st_size,z.st_mtime_ns);return b
def execute(cfg,go):
 S=time.monotonic();C=time.process_time();assert go['state']=='ROOT_AND_INDEPENDENT_GO' and go['registered_by']=='/root' and go['worker_sha256']==sha(Path(__file__).read_bytes()) and go['configuration_sha256']==sha(enc(cfg))
 sys.path.insert(0,str(ROOT));import nfl_lab
 from tools import category_topfive_matched12_storage_v1 as st
 from nfl_lab.owned_reference_batch import validate_owned_references
 import numpy as np,pandas as pd,pyarrow.parquet as pq
 original=json.loads(exact(cfg['configuration']));assert sha(enc(original))==cfg['original_configuration_sha256'];store,_=st.open_store(ROOT,allocation_sha256=original['allocation_sha256'],root_go=st.GO,readonly=True);_,audit=validate_owned_references(store,{cfg[k]['path']:cfg[k]['sha256'] for k in ['configuration','results','terminal']})
 terminal=json.loads(exact(cfg['terminal']));assert terminal['state']=='COMPLETE_OWNED_NEW_2025_PROPER_SCORE_COMPARISON' and terminal['source_sha256']==cfg['original_worker_sha256'] and terminal['configuration_sha256']==cfg['original_configuration_sha256'] and terminal['result']=={k:cfg['results'][k] for k in ['bytes','sha256']}
 with zipfile.ZipFile(io.BytesIO(exact(cfg['results']))) as z:
  manifest=json.loads(z.read('MEMBER_MANIFEST.json'));assert manifest==terminal['members'];parts={}
  for k,m in manifest.items():
   b=z.read(k);assert len(b)==m['bytes'] and sha(b)==m['sha256'];parts[k]=b
 a=json.loads(gzip.decompress(parts['AGGREGATES.json.gz']));f=pq.read_table(io.BytesIO(parts['ALL_ORIGINAL_CONTEXT_LAW_SCORECARD.parquet']),use_threads=False).to_pandas(use_threads=False);K=['season','week','game_id','player_id'];assert len(f)==34804 and f.season.eq(2025).all() and f.week.between(1,18).all() and not f.duplicated(['target','comparison_method']+K).any();assert set(f.target)=={'rush_att','rec'}
 def eq(a,b):return a is b if a is None or b is None else math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-12)
 def loss(x,c):
  x=np.asarray(x,float);assert not np.isnan(x).any() and not np.isneginf(x).any();n=int(np.isposinf(x).sum());assert c['n']==len(x) and c['positive_infinite_rows']==n and c['state']==('UNAVAILABLE' if not len(x) else 'POSITIVE_INFINITY' if n else 'FINITE') and eq(c['value'],None if n or not len(x) else float(x.mean()))
 checks=weeks=pairs=0
 for r in a['results']:
  t=r['target'];g=f.loc[f.target.eq(t)];assert g.is_primary_evaluation_row.eq(g.position.isin(original['primary_roles'][t])).all();b=g.loc[g.comparison_method.eq('BASE_CDF_CACHED')].sort_values(K).reset_index(drop=True);c=g.loc[g.comparison_method.eq('ORDERED_CDF')].sort_values(K).reset_index(drop=True);assert len(b)==len(c)==8701 and b[K].equals(c[K]) and b.participation_state.equals(c.participation_state) and np.array_equal(b.actual,c.actual,equal_nan=True);p=b.is_primary_evaluation_row;good=b.participation_state.eq('played')&np.isfinite(b.actual);m=p&good;v=r['population'];assert not (b.participation_state.ne('played')&b.actual.notna()).any();assert int(m.sum())==original['expected'][t]['supported'] and int(good.sum())==original['expected_all_roles'][t]['supported'];assert v['planned']==int(p.sum()) and v['supported']==int(m.sum()) and v['states']==b.loc[p,'participation_state'].value_counts().to_dict() and v['played_missing']==int((p&b.participation_state.eq('played')&b.actual.isna()).sum()) and v['played_zero']==int((m&b.actual.eq(0)).sum());assert v['games']==b.loc[p,'game_id'].nunique() and v['weeks']==b.loc[p,'week'].nunique()
  for name,x in [('BASE',b),('ORDERED',c)]:assert v[name+'_fallback_planned']==int(x.loc[p,'fallback'].fillna('').ne('').sum())
  for field,label in [('crps','CRPS'),('log_score','NLL')]:
   x,y=c.loc[m,field].to_numpy(float),b.loc[m,field].to_numpy(float);r0=r['ORDERED_minus_BASE_'+label];q=r0['paired'];loss(x,q['candidate']);loss(y,q['control']);assert q['paired_rows']==len(x) and q['no_rows_dropped'];xi,yi=np.isposinf(x).any(),np.isposinf(y).any();state='UNDEFINED_BOTH_MEANS_INFINITE' if xi and yi else 'POSITIVE_INFINITY' if xi else 'NEGATIVE_INFINITY' if yi else 'FINITE';assert q['candidate_minus_control']['state']==state and eq(q['candidate_minus_control']['value'],None if xi or yi else float((x-y).mean()));assert eq(r0['improvement_percent'],None if xi or yi or not y.mean() else 100*(float(y.mean())-float(x.mean()))/float(y.mean()));pairs+=1
   if not xi and not yi:
    for k,z in r0['intervals'].items():assert z['clusters']==b.loc[m,k].astype(str).nunique() and z['replicates']==1000 and z['seed']==original['uncertainty']['seed'] and z['two_target_Bonferroni_lower']<=z['lower']<=z['upper']<=z['two_target_Bonferroni_upper']
   for w in r['weekly']:
    take=m&b.week.eq(w['week']);assert w['planned']==int((p&b.week.eq(w['week'])).sum()) and w['supported']==int(take.sum());loss(c.loc[take,field],w['ORDERED_'+label]);loss(b.loc[take,field],w['BASE_'+label]);weeks+=1
  checks+=1
 return {'state':'PASS_INDEPENDENT_CACHED_2025_PROPER_QA','source_result_sha256':cfg['results']['sha256'],'categories':checks,'weekly_metric_pairs':weeks,'paired_metrics':pairs,'all_context_output_rows':len(f),'primary_supported':6861,'fits_restorations_inference_bootstrap_HTTP_private_writes':0,'owned_reference_batch':{'references':3,'full_scans':audit['full_scan_calls']},'intervals':'Cluster metadata/order checked; endpoints not independently resimulated','actual':{'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}
