"""Finite A saved-point comparison; existing C evaluator, no fits or new forecasts.

A root GO, exact source bindings and private-store admission are required before
NFL payloads are read. Source-only import never opens a native namespace. Root
alone retains the aggregate result through the existing allocation after review.
"""
from pathlib import Path
import argparse,collections,datetime,gzip,hashlib,importlib,importlib.util,io,json,math,os,platform,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='NFL-CATEGORY-DECISION-AND-RELEASE-01-A-SAVED-POINT-PAIRS-v1'
CATEGORIES=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd']
COUNT={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec'}
KEY=['target','season','week','game_id','player_id']
PHASE='NOT_STARTED'
def enc(v):return(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def check(v,s):
 if not v:raise ValueError(s)
def pin(path,digest,size=None):
 b=Path(path).read_bytes();check(sha(b)==digest and(size is None or len(b)==size),'bound bytes differ: '+Path(path).name);return b
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def finite(x):return type(x)in[int,float]and math.isfinite(x)
def identity(r):return tuple(str(r[k])if k not in ['season','week']else int(r[k])for k in KEY)
def main(a):
 global PHASE
 start=time.monotonic();cpu=time.process_time();sys.dont_write_bytecode=True;PHASE='ROOT_REGISTRATION'
 check(not a.output.exists(),'immutable output already exists');raw=pin(a.protocol,a.protocol_sha256);p=json.loads(raw)
 check(p['version']==VERSION and p['state']=='ROOT_REGISTERED_SCORING_GO','draft is not execution authority')
 check(p['counts']==dict(new_fits=0,new_model_inference=0,new_source_collection=0,native_writes=0,production_writes=0),'scope differs')
 check(p['resources']==dict(CPU_seconds=200,wall_seconds=900,RSS_bytes=2147483648,maximum_private_result_bytes=1048576),'finite envelope differs')
 for f,h in p['code_sha256'].items():pin(ROOT/f,h)
 check(p['code_sha256']['tools/category_decision_a_saved_point_pairs_v1.py']==sha(Path(__file__).read_bytes()),'executing code not bound')
 resource.setrlimit(resource.RLIMIT_CPU,(185,200));resource.setrlimit(resource.RLIMIT_AS,(2147483648,)*2)
 def exhausted(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('finite saved-point package exhausted')
 signal.signal(signal.SIGXCPU,exhausted);signal.signal(signal.SIGALRM,exhausted);signal.alarm(880)
 def offline(event,_):
  if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline approved retained inputs only')
 sys.addaudithook(offline)
 for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='1'
 import numpy as np,pandas as pd,pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
 runtime=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__);check(runtime==p['runtime'],'runtime differs')
 for f,h in p['common_code'].items():pin(a.c_cache/f,h)
 sys.path.insert(0,str(a.c_cache));common=importlib.import_module('abc_championship_v2')
 helper=module('category_decision_existing_math',ROOT/'tools/timing_confirm_b_completion_join_v1.py')
 oldplan=json.loads(pin(ROOT/p['existing_attach_plan']['path'],p['existing_attach_plan']['sha256']))
 check(sha((ROOT/'nfl_lab/profile_freshness_a_storage_v1.py').read_bytes())==oldplan['code_sha256']['nfl_lab/profile_freshness_a_storage_v1.py'],'existing executing guard differs')
 PHASE='EXISTING_READONLY_NAMESPACE_ATTACH'
 attach=module('category_decision_readonly_attach',ROOT/'tools/next02_freshness_model_independent_v2.py');store=attach.readonly_store(oldplan)
 config=json.loads(gzip.decompress(pin(ROOT/p['source_configuration']['path'],p['source_configuration']['sha256'])))
 # The path stays protected inside the original owner configuration; never export
 # it. Existing-owner transaction and registered hashes admit exactly three ZIPs.
 source_bytes={}
 with store.outer.transaction():
  for name,ref in p['source_objects'].items():
   original=config[name];check({k:v for k,v in original.items()if k!='path'}==ref,'source binding differs')
   path=Path(original['path']);check(path.is_relative_to(store.prior.forward_root)and path.resolve()==path and not path.is_symlink(),'source outside approved owner root')
   source_bytes[name]=pin(path,ref['sha256'],ref['bytes'])
 PHASE='IMMUTABLE_SAVED_POINTS_OFFERS_AND_QUALIFIED_OUTCOMES'
 with zipfile.ZipFile(io.BytesIO(source_bytes['frozen_bundle']))as z:
  b=z.read('FORECASTS.parquet');check(sha(b)==p['member_sha256']['FORECASTS.parquet'],'forecast member differs');forecasts=pd.read_parquet(io.BytesIO(b))
  b=z.read('EXPECTED_POPULATION.parquet');check(sha(b)==p['member_sha256']['EXPECTED_POPULATION.parquet'],'query universe differs');expected=pd.read_parquet(io.BytesIO(b))
 with zipfile.ZipFile(io.BytesIO(source_bytes['offers']))as z:
  b=z.read(config['offers']['member']);check(sha(b)==config['offers']['member_sha256'],'offer member differs');offers=pd.read_parquet(io.BytesIO(b))
 with zipfile.ZipFile(io.BytesIO(source_bytes['qualified_labels']))as z:
  b=z.read(config['qualified_labels']['member']);check(sha(b)==config['qualified_labels']['member_sha256'],'outcome member differs');labels=pd.read_parquet(io.BytesIO(b))
 for df in [forecasts,expected,offers,labels]:check(set(KEY)<=set(df),'source identity columns absent')
 # Only the registered ten-category annual cells participate in this replay.
 # Unused chart/event products and later diagnostics do not gate these cells.
 forecasts=forecasts.loc[forecasts.target.isin(CATEGORIES)&forecasts.season.eq(2026)&forecasts.week.between(1,5)].copy()
 expected=expected.loc[expected.target.isin(CATEGORIES)&expected.season.eq(2026)&expected.week.between(1,5)].copy()
 labels=labels.loc[labels.target.isin(CATEGORIES)&labels.season.eq(2026)&labels.week.between(1,5)].copy()
 check(not expected.duplicated(KEY).any()and not labels.duplicated(KEY).any(),'query or outcome keys duplicated')
 check(not forecasts.duplicated(KEY+['method','product']).any(),'saved forecast keys duplicated')
 source_inventory=[]
 for cat in CATEGORIES:
  for week in range(1,9):
   s=offers.loc[offers.target.eq(cat)&offers.season.eq(2026)&offers.week.eq(week)]
   source_inventory.append(dict(category=cat,week=week,offers=len(s),games=int(s.game_id.nunique()),source_panels=dict(collections.Counter(map(str,s.source_stream)))))
 board=offers.loc[offers.target.isin(CATEGORIES)&offers.season.eq(2026)&offers.week.between(1,5)&offers.source_stream.eq('ANNUAL_NAMED_NJ')].copy()
 check(not board.duplicated(KEY).any()and not board.opportunity_key.duplicated().any(),'primary offered opportunity keys duplicated')
 check(len(board)>0,'registered annual actual-line panel absent')
 universe={identity(r)for r in expected.to_dict('records')};lm={identity(r):r for r in labels.to_dict('records')}
 wanted={(t['category'],t['method'],t['output'])for t in p['point_products']}
 ff=forecasts.loc[forecasts.target.isin(CATEGORIES)&forecasts.season.eq(2026)&forecasts.week.between(1,5)]
 lookup={(r['target'],r['method'],r['product'],identity(r)):r for r in ff.to_dict('records')if(r['target'],r['method'],r['product'])in wanted}
 check(len(wanted)==79 and len(p['point_products'])==79,'finite original full-point roster differs')
 products=collections.defaultdict(list)
 for t in p['point_products']:products[t['category']].append(t)
 vectors={};provenance={};membership=[];alias_counts=collections.Counter();presence=collections.Counter();version_checks=collections.Counter()
 def norm(x):return {'LA':'LAR'}.get(str(x),str(x))
 for cat in CATEGORIES:
  catboard=board.loc[board.target.eq(cat)].to_dict('records');ids=[t['candidate_id']for t in products[cat]]+['ALWAYS_OVER','ALWAYS_UNDER'];vectors[cat]={cid:[]for cid in ids}
  for o in catboard:
   key=identity(o);check(finite(float(o['line'])),'nonfinite actual offered line');lab=lm.get(key);st=lab.get('participation_state')if lab else None
   appearance='PENDING'if lab and lab.get('outcome_state')=='pending'else'DNP'if str(st).lower()=='dnp'else'PLAYED'if st=='played'else'UNKNOWN'
   actual=lab.get('actual')if lab else None;actual=float(actual)if finite(actual)and appearance=='PLAYED'else None
   if actual is not None:
    check(actual==math.floor(actual)and(cat not in COUNT or actual>=0),'qualified target support differs')
    allowed=['EXPLICIT_BOTH_SIGNED_COMPONENTS']if cat=='rush_rec_yd'else['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE']
    check(lab.get('label_reason')in allowed and bool(lab.get('participation_evidence')),'metric/component presence not qualified')
    presence[(cat,str(lab.get('label_reason')))]+=1
   for t in products[cat]+[dict(candidate_id='ALWAYS_OVER'),dict(candidate_id='ALWAYS_UNDER')]:
    cid=t['candidate_id'];point=None;fallback=None;reason=None;f=None
    if cid.startswith('ALWAYS_'):side=cid.removeprefix('ALWAYS_')
    else:
     f=lookup.get((cat,t['method'],t['output'],key));reason='MISSING_SAVED_POINT'if f is None else None
     if f is not None:
      check(str(f['output_procedure_version'])==t['procedure_version'],'exact saved product version differs')
      version_checks[cid]+=1
      if f['position']!=o['position']:reason='ROLE_CONTRACT_MISMATCH'
      elif any(norm(f[c])!=norm(o[c])for c in ['team','opponent']):reason='TEAM_OPPONENT_CONTRACT_MISMATCH'
      elif any(pd.isna(f.get(c))or pd.isna(o.get(c))or pd.Timestamp(f[c])!=pd.Timestamp(o[c])for c in ['kickoff_utc','cutoff_utc']):reason='CLOCK_CONTRACT_MISMATCH'
      elif not finite(f.get('prediction')):reason='NONFINITE_OR_MISSING_POINT'
      else:
       point=float(f['prediction']);fallback=None if pd.isna(f.get('fallback'))else str(f['fallback'])
       if any(str(f[c])!=str(o[c])for c in ['team','opponent']):alias_counts[cid]+=1
     side=helper.point_side(point,float(o['line']))
    row=dict(season=2026,week=int(o['week']),game_id=str(o['game_id']),player_id=str(o['player_id']),category=cat,comparator='STRICT_OVER_UNDER',line=float(o['line']),actual=actual,appearance=appearance,point=point,selected_side=side,opportunity_key=str(o['opportunity_key']),source_stream=str(o['source_stream']),candidate_id=cid,fallback=fallback,unavailability_reason=reason,original_query_universe=key in universe)
    row['status']=helper.grade(row);check(common.status(row)==row['status'],'existing independent and common grades disagree');vectors[cat][cid].append(row)
    membership.append([cat,cid,row['opportunity_key'],point,side,row['status'],key in universe])
  for t in products[cat]:
   s=ff.loc[ff.target.eq(cat)&ff.method.eq(t['method'])&ff['product'].eq(t['output'])];cols=[c for c in ['output_procedure_version','source_forecast_sha256','source_forecast_member_sha256','source_information_policy','source_issue_time_UTC']if c in s]
   provenance[t['candidate_id']]=[{k:None if pd.isna(v)else str(v)for k,v in z.items()}for z in s[cols].drop_duplicates().to_dict('records')]
 PHASE='COMMON_SCORING_AND_BOUNDED_MATCHED_COMPARISONS'
 summaries=[];pairs=[];parity=[]
 oracle={t['candidate_id']:t for t in p['point_products']}
 for cat in CATEGORIES:
  vv=vectors[cat]
  for view in ['FULL_ELIGIBLE_ANNUAL_BOARD','ORIGINAL_QUERY_INTERSECTION']:
   sub={cid:[r for r in rs if view=='FULL_ELIGIBLE_ANNUAL_BOARD'or r['original_query_universe']]for cid,rs in vv.items()}
   for cid,rs in sub.items():
    for week in ['ALL']+list(range(1,9)):
     rr=[r for r in rs if week=='ALL'or r['week']==week]
     summary=dict(category=cat,candidate_id=cid,view=view,source_panel='ANNUAL_NAMED_NJ',week_view=week,requested_weeks=list(range(1,9)),actual_scored_weeks=sorted({r['week']for r in rr if r['status']in ['WIN','LOSS','PUSH']}),**common.summary(rr),numerical=helper.numerical(rr),fallback_states=dict(collections.Counter(str(r['fallback'])for r in rr)),unavailable_reasons=dict(collections.Counter(r['unavailability_reason']for r in rr if r['unavailability_reason'])),eligible_mask_sha256=helper.mask(rr),decided_mask_sha256=helper.mask(rr,True),evidence_tier=p['evidence_tier'])
     summaries.append(summary)
     if view=='ORIGINAL_QUERY_INTERSECTION'and(week=='ALL'or week in range(1,6))and cid in oracle:
      expected_record=oracle[cid]['annual_aggregate_oracle']if week=='ALL'else oracle[cid]['weekly_aggregate_oracle'][str(week)]
      actual_record={s:{k:summary[s][k]or 0 for k in ['wins','losses','decided']}for s in ['OVER','UNDER','COMBINED']}
      parity.append(dict(category=cat,candidate_id=cid,week_view=week,expected=expected_record,actual=actual_record,match=expected_record==actual_record))
   for left,right in p['paired_candidate_ids'][cat]:pairs.append(dict(category=cat,view=view,source_panel='ANNUAL_NAMED_NJ',left=left,right=right,**helper.paired(sub[left],sub[right],np)))
 check(all(v['match']for v in parity)and len(parity)==79*6,'original annual or weekly aggregate parity failed; scoped diagnosis required')
 PHASE='IMMUTABLE_AGGREGATE_RESULT'
 result=dict(version=VERSION,state='COMPLETED_A_SAVED_POINT_ANNUAL_COMMON_COMPARISONS',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_protocol_sha256=a.protocol_sha256,source_objects=p['source_objects'],source_member_sha256=p['member_sha256'],original_point_products=p['point_products'],source_inventory=source_inventory,source_catalog_provenance=provenance,canonical_alias_rows=dict(alias_counts),version_checks=dict(version_checks),qualified_presence_counts=[dict(category=k[0],reason=k[1],rows=v)for k,v in sorted(presence.items())],summary_cells=len(summaries),paired_cells=len(pairs),summaries=summaries,paired=pairs,aggregate_parity=parity,membership_sha256=sha(enc(sorted(membership))),runtime=runtime,counts=p['counts'],original_query_universe_scope='Pre-outcome EXPECTED_POPULATION member; FULL_ELIGIBLE preserves offers outside query universe as unavailable rather than shrinking every contender.',limitations=p['limitations'],resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
 body=gzip.compress(enc(result),mtime=0);check(len(body)<=p['resources']['maximum_private_result_bytes'],'finite aggregate retention reservation exceeded')
 with a.output.open('xb')as f:f.write(body);f.flush();os.fsync(f.fileno())
 signal.alarm(0);print(json.dumps(dict(state=result['state'],bytes=len(body),sha256=sha(body),summary_cells=len(summaries),paired_cells=len(pairs),resources=result['resources'],native_writes=0)))
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['protocol','c-cache','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--protocol-sha256',required=True);a=p.parse_args()
 try:main(a)
 except BaseException as e:
  signal.alarm(0);failure=dict(version=VERSION,state='FAILED_SAVED_POINT_PACKAGE_NO_AUTOMATIC_RETRY',phase=PHASE,error_type=type(e).__name__,error_sha256=sha(str(e).encode()),CPU_seconds=time.process_time(),new_fits=0,new_model_inference=0,native_writes=0)
  with a.output.with_name('A_POINT_PAIR_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json').open('xb')as f:f.write(enc(failure))
  print(json.dumps(failure));raise
