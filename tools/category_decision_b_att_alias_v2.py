"""Scoped saved ATT identity coverage correction; no fit/inference/native writes.

Uses the original ATT worker's scientific functions and original C evaluator.
Only 2026 LA/LAR team tokens change at the B source-contract comparison.
Original 81-case summaries and pairs must reproduce before 6 extra cases score.
Importing this file does not read sources, models or a native namespace.
"""
from pathlib import Path
import argparse,collections,datetime,gzip,hashlib,importlib,importlib.util,io,json,math,os,platform,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='NFL-CATEGORY-DECISION-AND-RELEASE-01-B-ATT-ALIAS-v2'
PHASE='NOT_STARTED'
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def check(v,s):
 if not v:raise ValueError(s)
def pin(path,h,n=None):
 b=Path(path).read_bytes();check(sha(b)==h and(n is None or len(b)==n),'bound input differs: '+Path(path).name);return b
def module(name,path):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
def team(x):return 'LAR'if str(x)=='LA'else str(x)
def main(a):
 global PHASE
 start=time.monotonic();cpu=time.process_time();sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT))
 resource.setrlimit(resource.RLIMIT_CPU,(70,80));resource.setrlimit(resource.RLIMIT_AS,(2147483648,)*2)
 def exhausted(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('finite ATT alias supplement')
 signal.signal(signal.SIGXCPU,exhausted);signal.signal(signal.SIGALRM,exhausted);signal.alarm(580)
 def offline(event,_):
  if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline approved saved outputs only')
 sys.addaudithook(offline)
 PHASE='ROOT_GO';check(not a.output.exists(),'immutable result already exists');raw=pin(a.protocol,a.protocol_sha256);p=json.loads(raw)
 check(p['version']==VERSION and p['state']=='ROOT_REGISTERED_SCORING_GO','draft is not execution GO')
 check(p['resources']==dict(CPU_seconds=80,wall_seconds=600,RSS_bytes=2147483648,maximum_private_result_bytes=524288),'finite envelope differs')
 check(p['counts']==dict(new_fits=0,new_model_inference=0,new_source_collection=0,native_writes=0,production_writes=0),'scope differs')
 check(p['expected_old_available']==81 and p['expected_new_alias_cases']==6 and p['expected_full_offers']==87,'coverage registration differs')
 check(p['alias_policy']==dict(season=2026,team_map={'LA':'LAR'},LAC='UNCHANGED',other_identity_clocks='EXACT_UNCHANGED'),'alias policy differs')
 check(sys.executable=='/workspace/nfl-venv/bin/python','approved existing runtime required')
 for f,h in p['code_sha256'].items():pin(ROOT/f,h)
 check(p['code_sha256']['tools/category_decision_b_att_alias_v2.py']==sha(Path(__file__).read_bytes()),'executing code not pinned')
 for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='1'
 import numpy as np,pandas as pd,pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
 runtime=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__);check(runtime==p['runtime'],'runtime differs')
 old=module('category_decision_existing_ATT_math',ROOT/'tools/player_context_completion_qb_join_v1.py')
 old_result=json.loads(pin(ROOT/p['old_result']['path'],p['old_result']['sha256'],p['old_result']['bytes']))
 check(old_result['candidate_ids']==old.CANDIDATE_IDS and old_result['eligible_A_ATT_offers']==87,'old comparison differs')
 for f,h in p['common_code'].items():pin(a.c_cache/f,h)
 sys.path.insert(0,str(a.c_cache));common=importlib.import_module('abc_championship_v2')
 PHASE='PUBLIC_B_OUTPUTS';bf={};brefs=[]
 check(p['B_source_commit']==old.B_COMMIT and p['B_public_refs']==[dict(week=w,bytes=n,sha256=h)for w,n,h in old.B_REFS[:5]],'saved B version differs')
 for r in p['B_public_refs']:
  b=pin(a.b_cache/f"2026-W{r['week']:02}.json.gz",r['sha256'],r['bytes']);packet=json.loads(gzip.decompress(b))
  check(packet['season']==2026 and packet['week']==r['week'] and packet['original_issuance']is False,'B packet origin differs')
  rr=[q for q in packet['rows']if q['target']=='pass_att']
  for q in rr:
   check(q['procedure_id']==old.B_PROCEDURE and q['method']=='COMMON_EXPOSURE'and q['position']=='QB'and q['week']==r['week']and q['season']==2026 and q['original_issuance']is False,'B row procedure/role differs')
   check(old.finite(q['fit_cutoff'])and old.finite(q['feature_cutoff'])and q['fit_cutoff']<=q['feature_cutoff'],'B origin clock differs')
   check(q['latest_source_available']is None or q['latest_source_available']<q['feature_cutoff'],'B future history')
   check(all(old.finite(q[k])and q[k]>=0 for k in old.PRODUCTS),'B point invalid')
   check(q['law']['kind']=='gamma_poisson_count'and q['law']['mean']==q['mean']and old.finite(q['law']['shape'])and q['law']['shape']>0,'B output law differs')
   k=(2026,str(q['game_id']),str(q['player_id']));check(k not in bf,'B duplicate identity');bf[k]=q
  brefs.append(dict(r,ATT_saved_player_games=len(rr)))
 PHASE='EXISTING_READONLY_SOURCE_ATTACH'
 oldplan=json.loads(pin(ROOT/p['existing_attach_plan']['path'],p['existing_attach_plan']['sha256']))
 check(sha((ROOT/'nfl_lab/profile_freshness_a_storage_v1.py').read_bytes())==oldplan['code_sha256']['nfl_lab/profile_freshness_a_storage_v1.py'],'executing storage guard differs')
 attach=module('category_ATT_existing_readonly_attach',ROOT/'tools/next02_freshness_model_independent_v2.py');store=attach.readonly_store(oldplan)
 cfg=json.loads(gzip.decompress(pin(ROOT/p['source_configuration']['path'],p['source_configuration']['sha256'])))
 source_bytes={};check(p['source_owner_types']=={n:'outer'for n in p['source_objects']},'source owner differs')
 owners0=[('outer',store.outer),('complete_peer',store.outer.complete_peer),('prior_forward',store.outer.complete_peer.prior_forward),('legacy',store.outer.complete_peer.legacy)]
 with store.outer.transaction():
  for n,r in p['source_objects'].items():
   original=cfg[n];check({k:v for k,v in original.items()if k!='path'}==r,'source reference differs')
   path=Path(original['path']);check(path.resolve()==path and not path.is_symlink(),'canonical path required')
   owners=[(t,o)for t,o in owners0 if any(path.is_relative_to(rt)for rt in o._roots)];check(len(owners)==1 and owners[0][0]=='outer','unique original source owner required')
   owned=owners[0][1].validate_reference(path,r['sha256']);check(owned['bytes']==r['bytes'],'source size differs');source_bytes[n]=pin(path,r['sha256'],r['bytes'])
 PHASE='BOUND_ATT_BOARD_AND_OUTPUTS'
 with zipfile.ZipFile(io.BytesIO(source_bytes['frozen_bundle']))as z:
  b=z.read('FORECASTS.parquet');check(sha(b)==old.A_MEMBER,'forecast member differs');af=pd.read_parquet(io.BytesIO(b))
 with zipfile.ZipFile(io.BytesIO(source_bytes['offers']))as z:
  b=z.read(cfg['offers']['member']);check(sha(b)==cfg['offers']['member_sha256'],'offer member differs');offers=pd.read_parquet(io.BytesIO(b))
 with zipfile.ZipFile(io.BytesIO(source_bytes['qualified_labels']))as z:
  b=z.read(cfg['qualified_labels']['member']);check(sha(b)==cfg['qualified_labels']['member_sha256'],'outcome member differs');labels=pd.read_parquet(io.BytesIO(b))
 key=lambda q:(int(q['season']),str(q['game_id']),str(q['player_id']))
 af=af.loc[af.target.eq('pass_att')&af.season.eq(2026)&af.week.between(1,5)];check(not af.duplicated(['method','product','season','game_id','player_id']).any(),'A forecast duplicate')
 av={cid:{key(q):q for q in af.loc[af.method.eq(m)&af['product'].eq(prod)].to_dict('records')}for cid,(m,prod)in zip(old.A_IDS,old.A_PRODUCTS)}
 board=offers.loc[offers.target.eq('pass_att')&offers.season.eq(2026)&offers.week.between(1,5)].copy()
 check(len(board)==87 and set(board.source_stream)=={'ANNUAL_NAMED_NJ'}and not board.opportunity_key.duplicated().any()and not board.duplicated(['season','game_id','player_id']).any(),'exact annual board differs')
 ll=labels.loc[labels.target.eq('pass_att')&labels.season.eq(2026)&labels.week.between(1,5)];check(not ll.duplicated(['season','game_id','player_id']).any(),'label duplicate');lm={key(q):q for q in ll.to_dict('records')}
 def reason(q,o,producer,canonical=False):
  if q is None:return 'MISSING_'+producer+'_RETAINED_CANONICAL_QB_GAME'
  if str(q['position'])!=str(o['position']):return producer+'_POSITION_CONTRACT_MISMATCH'
  for f in ['team','opponent']:
   if f in o and (team(q[f])!=team(o[f])if canonical else str(q[f])!=str(o[f])):return producer+'_TEAM_OPPONENT_CONTRACT_MISMATCH'
  for f in ['kickoff_utc','cutoff_utc']:
   if f not in o or pd.isna(o[f]):return 'A_ORIGINAL_QUERY_CLOCK_MISSING'
   oq=pd.Timestamp(o[f]);fq=pd.Timestamp(q[f])if producer=='A'else pd.Timestamp(q['feature_cutoff'],unit='s',tz='UTC')
   if oq.tzinfo is None or fq.tzinfo is None or oq!=fq:return producer+'_EXACT_QUERY_'+f.upper()+'_MISMATCH'
  return None
 rows=[];strict=set();alias=[];members=[]
 for o in board.to_dict('records'):
  k=key(o);q=bf.get(k);lab=lm.get(k);check(o['position']=='QB'and old.finite(float(o['line'])),'ATT role/line invalid')
  rs=reason(q,o,'B',False);rn=reason(q,o,'B',True)
  if rs is None:strict.add(str(o['opportunity_key']))
  elif rn is None:
   check(rs=='B_TEAM_OPPONENT_CONTRACT_MISMATCH','nonalias qualification changed')
   check(any(str(q[f])!=str(o[f])and {str(q[f]),str(o[f])}=={'LA','LAR'}for f in ['team','opponent']),'unexpected team alias')
   alias.append(dict(case_sha256=sha(enc(str(o['opportunity_key']))),week=int(o['week']),old_reason=rs,new_state='IDENTITY_AND_CLOCK_QUALIFIED',tokens=sorted({str(q[f])for f in ['team','opponent']}|{str(o[f])for f in ['team','opponent']})))
  check(rn is None,'unresolved B identity/clock remains')
  appearance='PENDING'if lab and lab.get('outcome_state')=='pending'else'DNP'if lab and str(lab.get('participation_state')).lower()=='dnp'else'PLAYED'if lab and lab.get('participation_state')=='played'else'UNKNOWN'
  actual=lab.get('actual')if lab else None;actual=float(actual)if appearance=='PLAYED'and old.finite(actual)and actual>=0 and actual%1==0 else None
  if actual is not None:check(lab.get('label_reason')in ['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE']and bool(lab.get('participation_evidence')),'qualified metric presence absent')
  check(q['week']==int(o['week']),'game week differs')
  check(actual is None or not old.finite(q.get('actual'))or actual==q['actual'],'known outcome conflict')
  for cid in old.CANDIDATE_IDS:
   point=None;fallback=None;why=None
   if cid in old.A_IDS:
    aq=av[cid].get(k);why=reason(aq,o,'A',False)
    if why is None:
     point=float(aq['prediction'])if old.finite(aq['prediction'])else None;fallback=str(aq['fallback'])if not pd.isna(aq['fallback'])else None;why='A_RETAINED_POINT_UNAVAILABLE'if point is None else None
    side=old.point_side(point,o['line'])
   elif cid in old.B_IDS:point=q[old.PRODUCTS[old.B_IDS.index(cid)]];fallback=q['fallback'];side=old.point_side(point,o['line'])
   else:side=cid.removeprefix('ALWAYS_')
   row=dict(season=2026,week=int(o['week']),game_id=k[1],player_id=k[2],category='pass_att',line=float(o['line']),actual=actual,appearance=appearance,selected_side=side,point=point,candidate_id=cid,comparator='STRICT_OVER_UNDER',source_stream=str(o['source_stream']),opportunity_key=str(o['opportunity_key']),fallback=fallback,unavailability_reason=why,outer_outcome_state='KNOWN_ACTUAL'if actual is not None else'MISSING_ACTUAL'if appearance=='PLAYED'else appearance)
   row['status']=old.independent_status(row);check(common.status(row)==row['status'],'canonical and original independent grades differ');rows.append(row);members.append([cid,row['opportunity_key'],row['selected_side'],row['status'],point])
 check(len(strict)==81 and len(alias)==6 and old.mask([r for r in rows if r['candidate_id']==old.B_IDS[0]and r['opportunity_key']in strict])==p['old_shared81_mask_sha256'],'original81 mask or exact6 scope differs')
 full={str(o)for o in board.opportunity_key};check(sha(enc(sorted(full)))==p['full87_mask_sha256'],'full87 mask differs')
 def score(rr):
  errors=[r['point']-r['actual']for r in rr if r['point']is not None and r['actual']is not None]
  return dict(**common.summary(rr),actual_scored_weeks=sorted({r['week']for r in rr if r['status']in ['WIN','LOSS','PUSH']}),outer_outcomes=dict(collections.Counter(r['outer_outcome_state']for r in rr)),forecast_outcome_cross_counts=[dict(forecast_available=a,outcome_state=s,rows=n)for(a,s),n in sorted(collections.Counter((r['selected_side']is not None,r['outer_outcome_state'])for r in rr).items())],unavailable_reasons=dict(collections.Counter(r['unavailability_reason']for r in rr if r['unavailability_reason'])),fallback_outputs=sum(r['fallback']not in [None,'','none']for r in rr),numerical_same_offer_mask=dict(scored=len(errors),MAE=math.fsum(map(abs,errors))/len(errors)if errors else None,MSE=math.fsum(e*e for e in errors)/len(errors)if errors else None,bias=math.fsum(errors)/len(errors)if errors else None),eligible_mask_sha256=old.mask(rr),decided_mask_sha256=old.mask(rr,True))
 PHASE='ORIGINAL81_PARITY_BEFORE_EXPANSION';oldstats={};parity=0
 for cid in old.CANDIDATE_IDS:
  for w in ['ALL']+old.REQUESTED:
   rr=[r for r in rows if r['candidate_id']==cid and r['opportunity_key']in strict and(w=='ALL'or r['week']==w)];got=score(rr);oldstats[cid,w]=got
   for panel in ['ALL','ANNUAL_NAMED_NJ']:
    expected=next(s for s in old_result['scores']if s['view']=='SHARED_B_AVAILABLE'and s['source_panel']==panel and s['week_view']==w and s['candidate_id']==cid)
    for f,v in got.items():check(v==expected[f],'original81 summary parity differs: '+f)
    parity+=1
 oldpairs=[]
 for l,r in old.PAIRED_IDS:
  left=[q for q in rows if q['candidate_id']==l and q['opportunity_key']in strict];right=[q for q in rows if q['candidate_id']==r and q['opportunity_key']in strict];got=old.paired(left,right,np);expected=next(z for z in old_result['paired_controls']if z['view']=='SHARED_B_AVAILABLE'and z['left']==l and z['right']==r)
  for f,v in got.items():check(v==expected[f],'original81 paired parity differs: '+f)
  oldpairs.append(dict(view='ORIGINAL_STRICT_B81',left=l,right=r,**got))
 PHASE='APPEND_EXACT6_COVERAGE';summaries=[];pairs=[]
 for view,vm in [('FULL_A_BOARD_ALIAS_QUALIFIED87',full),('ORIGINAL_STRICT_B81',strict)]:
  for cid in old.CANDIDATE_IDS:
   for w in ['ALL']+old.REQUESTED:
    rr=[q for q in rows if q['candidate_id']==cid and q['opportunity_key']in vm and(w=='ALL'or q['week']==w)];s=oldstats[cid,w]if view=='ORIGINAL_STRICT_B81'else score(rr)
    for panel in ['ALL','ANNUAL_NAMED_NJ']:
     if view=='FULL_A_BOARD_ALIAS_QUALIFIED87'and cid not in old.B_IDS:
      expected=next(z for z in old_result['scores']if z['view']=='FULL_A_BOARD'and z['source_panel']==panel and z['week_view']==w and z['candidate_id']==cid)
      for f,v in s.items():check(v==expected[f],'unchanged full87 A/control parity differs: '+f)
     summaries.append(dict(category='pass_att',candidate_id=cid,view=view,source_panel=panel,week_view=w,**s))
  if view=='ORIGINAL_STRICT_B81':pairs.extend(oldpairs)
  else:
   vectors={cid:[q for q in rows if q['candidate_id']==cid]for cid in old.CANDIDATE_IDS}
   for l,r in old.PAIRED_IDS:pairs.append(dict(view=view,left=l,right=r,**old.paired(vectors[l],vectors[r],np)))
 result=dict(version=VERSION,state='COMPLETED_EXACT_ATT_ALIAS_COVERAGE_NO_MODEL_CHANGE',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),runtime=runtime,root_protocol_sha256=a.protocol_sha256,old_result=p['old_result'],B_source_commit=old.B_COMMIT,B_public_refs=brefs,source_objects=p['source_objects'],evidence_tier=p['evidence_tier'],candidate_ids=old.CANDIDATE_IDS,source_inventory=old_result['A_ATT_CMP_source_inventory_all_requested_weeks'],original81_summary_cells_reproduced=parity,original81_paired_cells_reproduced=len(oldpairs),unchanged_full87_A_control_summary_cells_reproduced=126,old81_mask_sha256=p['old_shared81_mask_sha256'],full87_mask_sha256=p['full87_mask_sha256'],newly_qualified_physical_cases=alias,newly_observed_games_weeks=0,newly_available_B_point_outputs=12,B_output_products_unchanged=2,summaries=summaries,paired=pairs,membership_sha256=sha(enc(sorted(members))),counts=p['counts'],resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),limitations='Only canonical team tokens changed; no learned forecast/information/decision-policy change. Coverage correction is not learned-skill gain. W1-5 timing-unverified actual offers only; no source-panel pooling/probability/Top Picks/primary admission. Original81 retained. Unprovided fit/source-clock/private parity remains unknown.')
 body=gzip.compress(enc(result),mtime=0);check(len(body)<=524288,'finite result cap exceeded')
 with a.output.open('xb')as f:f.write(body);f.flush();os.fsync(f.fileno())
 signal.alarm(0);print(json.dumps(dict(state=result['state'],bytes=len(body),sha256=sha(body),old81_summary_cells=parity,alias_cases=len(alias),resources=result['resources'],native_writes=0)))
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['protocol','output','b-cache','c-cache']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--protocol-sha256',required=True);a=p.parse_args();start=time.process_time()
 try:main(a)
 except BaseException as e:
  signal.alarm(0);out=dict(version=VERSION,state='FAILED_ATT_ALIAS_NO_AUTOMATIC_RETRY',phase=PHASE,error_type=type(e).__name__,error_sha256=sha(str(e).encode()),CPU_seconds=time.process_time()-start,new_fits=0,new_inference=0,native_writes=0)
  f=a.output.with_name('ATT_ALIAS_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
  with f.open('xb')as z:z.write(enc(out))
  print(json.dumps(out));raise SystemExit(1)from None
