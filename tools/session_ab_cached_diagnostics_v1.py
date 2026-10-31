"""Session A cached diagnostics for the separately registered A/B comparison.

No fitting, model inference, external recovery, source acquisition or production
writes. B row-level records are not presumed accessible. Existing scores remain
intact. The caller pins source/configuration and supplies a reviewed GO.
"""
from pathlib import Path
from decimal import Decimal
import argparse,gzip,hashlib,io,json,math,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='session-a-b-cached-A-diagnostics-v1'
KEY=['target','season','week','game_id','player_id','team','opponent','cutoff_utc']
COUNT={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec'}
def enc(x):
 def scalar(v):
  if hasattr(v,'item'):return v.item()
  raise TypeError(type(v).__name__)
 return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,default=scalar).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def exact(r):
 p=Path(r['path']);assert p.is_absolute() and p.resolve()==p and not any(q.is_symlink() for q in [p,*p.parents]);a=p.stat();b=p.read_bytes();z=p.stat();assert len(b)==r['bytes']<=16*1024**2 and sha(b)==r['sha256'] and (a.st_dev,a.st_ino,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_mtime_ns);return b
def finite_score(v):
 import numpy as np
 a=np.asarray(v,float);assert not np.isnan(a).any();p=int(np.isposinf(a).sum());n=int(np.isneginf(a).sum());state='UNAVAILABLE' if not len(a) else 'UNDEFINED_MIXED_INFINITIES' if p and n else 'POSITIVE_INFINITY' if p else 'NEGATIVE_INFINITY' if n else 'FINITE'
 return {'n':len(a),'state':state,'value':float(a.mean()) if state=='FINITE' else None,'positive_infinite_rows':p,'negative_infinite_rows':n}
def point_side(f,L):
 if f is None or not math.isfinite(float(f)):return 'UNAVAILABLE'
 a,b=Decimal(str(f)),Decimal(str(L));assert b.is_finite();return 'over' if a>b else 'under' if a<b else 'abstain'
def grade(side,y,L,participation):
 if side=='UNAVAILABLE':return 'UNAVAILABLE'
 if side=='abstain':return 'ABSTAIN'
 if str(participation).lower()=='dnp':return 'DNP'
 if participation!='played':return 'UNKNOWN'
 if y is None or not math.isfinite(float(y)):return 'PLAYED_MISSING'
 a,b=Decimal(str(y)),Decimal(str(L))
 return 'PUSH' if a==b else 'WIN' if (a>b if side=='over' else a<b) else 'LOSS'
def side_summary(f,sidefield,resultfield):
 out={'opportunities':len(f),'games':int(f.game_id.nunique()),'weeks':sorted(map(int,f.week.unique())),'state_counts':f[resultfield].value_counts().to_dict(),'fallback_rows':int(f.fallback.fillna('').astype(str).ne('').sum()) if 'fallback' in f else None,'sides':{}}
 for side in ['over','under']:
  g=f.loc[f[sidefield].eq(side)];c=g[resultfield].value_counts().to_dict();w=int(c.get('WIN',0));l=int(c.get('LOSS',0));out['sides'][side]={'selected':len(g),'wins':w,'losses':l,'decided':w+l,'hit_rate':w/(w+l) if w+l else None,'other_states':{k:int(v) for k,v in c.items() if k not in ['WIN','LOSS']}}
 w=sum(x['wins'] for x in out['sides'].values());l=sum(x['losses'] for x in out['sides'].values());out['combined']={'wins':w,'losses':l,'decided':w+l,'hit_rate':w/(w+l) if w+l else None};return out
def paired(f,a,b,seed=20261031):
 import numpy as np
 assert len(f) and np.isfinite(f[[a,b]].to_numpy(float)).all();d=f[a].to_numpy(float)-f[b].to_numpy(float);v={'n':len(f),'candidate':a,'control':b,'candidate_loss':float(f[a].mean()),'control_loss':float(f[b].mean()),'candidate_minus_control':float(d.mean()),'intervals':{}}
 for group in ['game_id','week']:
  g=f[[group]].copy();g['d']=d;c=g.groupby(group).d.agg(['sum','count']);rng=np.random.default_rng(seed);n=len(c)
  if n<2:ci=None
  else:
   ix=rng.integers(0,n,size=(500,n));values=c['sum'].to_numpy()[ix].sum(1)/c['count'].to_numpy()[ix].sum(1);ci=list(map(float,np.quantile(values,[.025,.975])))
  v['intervals'][group]={'clusters':n,'replicates':500 if n>=2 else 0,'interval95':ci}
 v['interpretation']='Nominal exposed-development cluster sensitivity, not selection-adjusted qualification.';return v
def fixtures():
 tests=[]
 for side in ['over','under']:
  for y in range(4):tests.append((f'passTD_{side}_1.5_y{y}',grade(side,y,'1.5','played')==('WIN' if (y>=2 if side=='over' else y<=1) else 'LOSS')))
 for L,y0,y1 in [('4.5',4,5),('19.5',19,20)]:
  for side in ['over','under']:
   tests.append((f'count_{side}_{L}',grade(side,y0,L,'played')==('LOSS' if side=='over' else 'WIN') and grade(side,y1,L,'played')==('WIN' if side=='over' else 'LOSS')))
 tests += [('integer_push',grade('over',5,5,'played')=='PUSH'),('fractional_mean_unrounded',point_side(1.88,1.5)=='over'),('point_tie_abstain',point_side(4.5,4.5)=='abstain'),('signed_yards',grade('under',-3,-.5,'played')=='WIN'),('fractional_chart',grade('over',10.04,10.02,'played')=='WIN'),('DNP_not_zero',grade('under',None,4.5,'DNP')=='DNP'),('unknown_not_zero',grade('under',None,4.5,'unknown')=='UNKNOWN'),('played_missing',grade('under',None,4.5,'played')=='PLAYED_MISSING'),('supported_zero',grade('under',0,.5,'played')=='WIN'),('missing_forecast',point_side(None,.5)=='UNAVAILABLE')]
 assert all(v for _,v in tests);return {'state':'PASS_FICTIONAL_THRESHOLD_FIXTURES','checks':[n for n,_ in tests],'NFL_observations':0}
def execute(c,go):
 begin=time.process_time();start=time.monotonic();assert go['state']=='ROOT_AND_INDEPENDENT_GO' and go['source_sha256']==sha(Path(__file__).read_bytes()) and go['configuration_sha256']==sha(enc(c));assert c['version']==VERSION and c['B_private_rows_available'] is False
 import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1);sys.path.insert(0,str(ROOT));import nfl_lab
 from tools import category_topfive_matched12_storage_v1 as st
 from nfl_lab.owned_reference_batch import validate_owned_references
 assert sha(Path(st.__file__).read_bytes())==c['storage_helper_sha256'];store,_=st.open_store(ROOT,allocation_sha256=c['allocation_sha256'],root_go=st.GO);out=store.forward_root/'research'/c['run_id'];assert c['run_id'].startswith('session-a-b-A-diagnostic-') and '/' not in c['run_id'] and not out.exists();store.register_root(out);used=0
 def put(name,b):
  nonlocal used
  assert used+len(b)+(0 if name=='FAILURE.json' else 65536)<=c['resources']['private_bytes'];store.write_bytes(out/name,b);r=store.validate_reference(out/name,sha(b));used+=len(b);return {k:r[k] for k in ['bytes','sha256']}
 put('STARTED.json',enc({'version':VERSION,'state':'BEFORE_CACHED_VECTOR_READ','source_sha256':go['source_sha256'],'configuration_sha256':go['configuration_sha256'],'B_private_rows':0,'new_fits_inference':0}));stage='AUTHENTICATE_INPUTS'
 try:
  refs={r['path']:r['sha256'] for r in [c['source_zip'],c['source_terminal'],c['law_source_started'],c['law_source_terminal'],c['law_evaluation_bindings']]+[x['package'] for x in c['law_cells']]};_,audit=validate_owned_references(store,refs)
  terminal=json.loads(exact(c['source_terminal']));assert terminal['result']=={k:c['source_zip'][k] for k in ['bytes','sha256']}
  with zipfile.ZipFile(io.BytesIO(exact(c['source_zip']))) as z:
   m=json.loads(z.read('MEMBER_MANIFEST.json'));cache={}
   for n in ['AGGREGATES.json.gz','ALL_POINTS.parquet','DIRECTIONS.parquet']:
    b=z.read(n);assert m[n]==terminal['members'][n] and len(b)==m[n]['bytes'] and sha(b)==m[n]['sha256'];cache[n]=b
  ag=json.loads(gzip.decompress(cache['AGGREGATES.json.gz']));assert ag['state']=='COMPLETED_NORMALIZED_FINALIST_COMPARISON' and ag['scope']['weeks']==list(range(1,8)) and ag['scope']['outcome_version']==c['outcome_version']
  def read_table(b,want=None):
   pf=pq.ParquetFile(io.BytesIO(b));cols=pf.schema_arrow.names;f=pf.read(columns=[n for n in want if n in cols] if want else None,use_threads=False).to_pandas(use_threads=False)
   if 'cutoff_utc' in f:f['cutoff_utc']=pd.to_datetime(f.cutoff_utc,utc=True)
   return f
  stage='SAVED_POINT_SIDE_READ';cols=KEY+['position','method','product','prediction','actual','participation_state','fallback','procedure_version','output_procedure_version','source_forecast_sha256','source_forecast_member_sha256'];points=read_table(cache['ALL_POINTS.parquet'],cols);assert not points.duplicated(KEY+['method','product']).any()
  sides=read_table(cache['DIRECTIONS.parquet'],cols+['offer_id','line','selected_side','statistical_result']);sides=sides.loc[sides.line.notna()].copy();assert not sides.duplicated(KEY+['method','product']).any();assert sides.season.eq(2026).all() and sides.week.between(1,7).all()
  own=[]
  for (t,m,p),f in sides.groupby(['target','method','product'],sort=True):
   ss=[point_side(x,L) for x,L in f[['prediction','line']].to_numpy()];assert (f.selected_side.to_numpy()==np.asarray(['UNRESOLVED' if x=='UNAVAILABLE' else x for x in ss])).all();gg=[grade(s,y,L,part) for s,y,L,part in zip(ss,f.actual,f.line,f.participation_state)]
   # Existing scorer uses UNRESOLVED for unknown/missing; preserve that record,
   # while the new diagnostic keeps the distinct reasons under fresh columns.
   old=np.asarray(gg,object);old[np.isin(old,['UNKNOWN','PLAYED_MISSING','UNAVAILABLE'])]='UNRESOLVED';assert np.array_equal(old,f.statistical_result.to_numpy())
   f=f.copy();f['diagnostic_result']=gg
   for label,g in [('W1_7',f),('W5_7_CALENDAR_SLICE_NOT_B_MATCHED',f.loc[f.week.ge(5)])]:own.append({'target':t,'method':m,'product':p,'scope':label,'metrics':side_summary(g,'selected_side','diagnostic_result')})
  role=[]
  for (t,m,p),f in points.loc[points.target.isin(['rush_att','rush_yd'])].groupby(['target','method','product'],sort=True):
   for label,positions in [('RB_ONLY',['RB']),('QB_ONLY',['QB']),('QB_RB',['QB','RB'])]:
    g=f.loc[f.position.isin(positions)];s=g.loc[g.participation_state.eq('played')&np.isfinite(g.prediction)&np.isfinite(g.actual)];e=s.prediction-s.actual
    role.append({'target':t,'method':m,'product':p,'role_scope':label,'planned':len(g),'scored':len(s),'games':int(s.game_id.nunique()),'weeks':sorted(map(int,s.week.unique())),'unknown_participation':int((~g.participation_state.isin(['played','dnp','DNP'])).sum()),'MAE':float(abs(e).mean()) if len(s) else None,'MSE':float((e**2).mean()) if len(s) else None,'RMSE':float(np.sqrt((e**2).mean())) if len(s) else None,'bias':float(e.mean()) if len(s) else None,'fallback_scored':int(s.fallback.fillna('').astype(str).ne('').sum())})
  started=json.loads(exact(c['law_source_started']));lt=json.loads(gzip.decompress(exact(c['law_source_terminal'])));binding=json.loads(exact(c['law_evaluation_bindings']));assert started['state']=='STARTED_BEFORE_LABEL_READ' and lt['state']=='COMPLETED_FROZEN_LAW_COMPARISON';assert binding['labels_sha256']==c['labels_package_sha256'] and binding['offers_sha256']==c['offers_package_sha256'] and sha(enc(binding['specs']))==c['law_specs_sha256'];specs={s['cell_id']:s for s in binding['specs']};completed={s['cell_id']:s for s in lt['cells']};assert set(specs)=={x['cell_id'] for x in c['law_cells']};consistency=[];probability=[];privatechecks=[];binding_exclusions=[]
  for cell in c['law_cells']:
   if cell['target']=='chart_ppr':continue
   stage='CACHED_LAW_COMPARE_'+cell['cell_id']
   with zipfile.ZipFile(io.BytesIO(exact(cell['package']))) as z:
    doc=json.loads(z.read('MANIFEST.json'));assert doc['spec']==specs[cell['cell_id']] and doc['law_helper_sha256']==c['law_helper_sha256'];assert completed[cell['cell_id']]['artifact']=={k:cell['package'][k] for k in ['bytes','sha256']};f=read_table(z.read('OFFER_PROBABILITY_SCORECARD.parquet'),KEY+['offer_id','line','position','method','arm','actual','participation_state','fallback','p_under','p_push','p_over','log_p_under','log_p_push','log_p_over','side','result','Brier','log_loss','score_state'])
   spec=doc['spec'];f=f.loc[f.arm.eq('FOOTBALL')].copy();f['raw_probability_side']='UNAVAILABLE';known=f[['log_p_under','log_p_over']].notna().all(axis=1);f.loc[known,'raw_probability_side']=np.where(f.loc[known,'log_p_over']>f.loc[known,'log_p_under'],'over',np.where(f.loc[known,'log_p_under']>f.loc[known,'log_p_over'],'under','abstain'));assert f.loc[known,'side'].equals(f.loc[known,'raw_probability_side'])
   for method,g in f.groupby('method',sort=True):
    target=cell['target'];cat=ag['catalog'][target][method];assert not g.duplicated(KEY).any();model_same=cat.get('model_sha256')==spec.get('inner_sha256') and cat.get('model_sha256') is not None
    for label,v in [('W1_7',g),('W5_7_CALENDAR_SLICE_NOT_B_MATCHED',g.loc[g.week.ge(5)])]:
     s=v.loc[v.score_state.eq('SCORED')];assert not s[['Brier','log_loss']].isna().any().any();decisive_mass=s.p_over+s.p_under;q=s.p_over/decisive_mass.where(decisive_mass.gt(0));event=(s.actual>s.line).astype(float);push=s.actual.eq(s.line);dec=s.loc[~push]
     probability.append({'target':target,'method':method,'scope':label,'opportunities':len(v),'scored':len(s),'games':int(s.game_id.nunique()),'weeks':sorted(map(int,s.week.unique())),'half_three_outcome_Brier':finite_score(s.Brier),'neutral_half_three_outcome_Brier':finite_score(np.where(push,.75,.25)),'log_loss':finite_score(s.log_loss),'decisive_binary_Brier':finite_score((q.loc[~push&decisive_mass.gt(0)]-event.loc[~push&decisive_mass.gt(0)])**2),'conditional_probability_unavailable_nonpush':int((~push&~decisive_mass.gt(0)).sum()),'probability_selection':side_summary(v,'side','result'),'max_probability_sum_error':float(abs(v[['p_under','p_push','p_over']].sum(axis=1)-1).max()) if len(v) else None})
    if target not in COUNT:continue
    half=g.line.map(lambda L:abs(Decimal(str(L))%1)==Decimal('.5'));v=g.loc[half].copy();p=points.loc[points.target.eq(target)&points.method.eq(method)&points['product'].eq('median')];j=v.merge(p[KEY+['prediction','output_procedure_version','source_forecast_sha256','source_forecast_member_sha256','actual','participation_state']].rename(columns={'actual':'actual_point','participation_state':'participation_state_point'}),on=KEY,how='left',validate='one_to_one');assert np.array_equal(j.actual.to_numpy(float),j.actual_point.to_numpy(float),equal_nan=True) and j.participation_state.equals(j.participation_state_point),'saved point/law outcomes or participation conflict';expected_version=cat.get('product_procedure_versions',{}).get('median',cat['procedure_version']);assert j.loc[j.prediction.notna(),'output_procedure_version'].eq(expected_version).all();j['point_side']=[point_side(x,L) for x,L in j[['prediction','line']].to_numpy()];j['exact_tie']=j.log_p_over.eq(j.log_p_under);j['rounded_p_tie_not_log_tie']=j.p_over.eq(j.p_under)&~j.exact_tie;j['near_tie_nonexact']=(j.p_over-j.p_under).abs().le(1e-12)&~j.exact_tie;j['point_missing']=~np.isfinite(j.prediction);expected_forecast=spec['forecast']['sha256'];expected_member=spec['forecast'].get('member_sha256');j['source_forecast_matches']=j.source_forecast_sha256.eq(expected_forecast);j['source_member_matches']=j.source_forecast_member_sha256.isna() if expected_member is None else j.source_forecast_member_sha256.eq(expected_member);j['same_query_features']=spec.get('features',{}).get('sha256')==c['feature_sha256'];j['same_law_lineage']=j.source_forecast_matches&j.source_member_matches&j.same_query_features&model_same;j['law_probability_unavailable']=j.raw_probability_side.eq('UNAVAILABLE')|~np.isfinite(j[['p_under','p_push','p_over']]).all(axis=1)|j[['p_under','p_push','p_over']].sum(axis=1).sub(1).abs().gt(1e-10);j['mismatch']=j.point_side.ne(j.raw_probability_side)&~j.exact_tie&~j.point_missing&~j.law_probability_unavailable;j['strict_mismatch']=j.mismatch&~j.near_tie_nonexact
    rec={'target':target,'method':method,'cell_id':cell['cell_id'],'same_saved_model_hash':model_same,'saved_point_output_version':cat.get('product_procedure_versions',{}).get('median',cat['procedure_version']),'same_model_hash':cat.get('model_sha256'),'law_model_hash':spec.get('inner_sha256'),'point_line_opportunities':len(j),'missing_point':int(j.point_missing.sum()),'exact_50_50_ties':int(j.exact_tie.sum()),'near_50_50_nonexact_sensitivity':int(j.near_tie_nonexact.sum()),'all_nonexact_mismatches':int(j.mismatch.sum()),'strict_mismatches':int(j.strict_mismatch.sum()),'authenticated_same_law_rows':int(j.same_law_lineage.sum()),'same_law_comparable_valid_point_probability_rows':int((j.same_law_lineage&~j.point_missing&~j.law_probability_unavailable).sum()),'authenticated_same_law_strict_mismatches':int((j.same_law_lineage&j.strict_mismatch).sum()),'point_law_actual_participation_exact':True,'forecast_lineage_mismatches':int((~j.source_forecast_matches|~j.source_member_matches).sum()),'same_query_features':bool(j.same_query_features.all()),'probability_unavailable':int(j.law_probability_unavailable.sum()),'rounded_probability_ties_not_log_ties':int(j.rounded_p_tie_not_log_tie.sum()),'half_integer_push_mass_nonzero':int(j.p_push.ne(0).sum()),'matching_scope':'Same frozen parameter/query-contract bindings; cached original point and replayed law outputs. No new inference or claim of authentic pregame clocks.'};consistency.append(rec);j['model_binding_same']=model_same;j['source_cell_id']=cell['cell_id'];privatechecks.append(j)
    if not model_same or not j.same_law_lineage.all():binding_exclusions.append({'target':target,'method':method,'cell_id':cell['cell_id'],'reason':'IDENTICAL_MODEL_NOT_AUTHENTICATED;notcountedasame-lawfailure'})
  stage='CARRY_MEAN_MEDIAN_DIAGNOSTIC';carry=sides.loc[sides.target.eq('rush_att')&sides.method.eq('BACKFIELD_CDF')&sides['product'].isin(['mean','median'])].copy();a=carry.loc[carry['product'].eq('mean')];b=carry.loc[carry['product'].eq('median')];j=a.merge(b,on=KEY,validate='one_to_one',suffixes=('_mean','_median'));assert len(j)==len(a)==len(b) and j.line_mean.equals(j.line_median);assert np.array_equal(j.actual_mean.to_numpy(),j.actual_median.to_numpy(),equal_nan=True);j['directions_disagree']=j.selected_side_mean.ne(j.selected_side_median);sc=j.loc[j.statistical_result_mean.isin(['WIN','LOSS'])&j.statistical_result_median.isin(['WIN','LOSS'])].copy();sc['mean_correct']=sc.statistical_result_mean.eq('WIN').astype(float);sc['median_correct']=sc.statistical_result_median.eq('WIN').astype(float);sc['mean_AE']=(sc.prediction_mean-sc.actual_mean).abs();sc['median_AE']=(sc.prediction_median-sc.actual_mean).abs()
  carryreport={'offered_planned':len(j),'both_decisive':len(sc),'disagreements':int(sc.directions_disagree.sum()),'mean_wins_median_loses':int((sc.mean_correct.eq(1)&sc.median_correct.eq(0)).sum()),'median_wins_mean_loses':int((sc.mean_correct.eq(0)&sc.median_correct.eq(1)).sum()),'mean_correct':int(sc.mean_correct.sum()),'median_correct':int(sc.median_correct.sum()),'mean_minus_median_decision_correct':paired(sc,'mean_correct','median_correct'),'median_minus_mean_AE_on_same_offered_rows':paired(sc,'median_AE','mean_AE'),'interpretation':'Observed error and threshold decisions are different objectives; no retrospective mean/median router proposed.'}
  report={'version':VERSION,'state':'COMPLETE_A_CACHED_DIAGNOSTICS_B_PAIRED_JOIN_BLOCKED','new_fits_model_inference_forecasts':0,'B_rows_joined':0,'B_join_dependency':'B frozen canonical row-level forecast/outcome/offer/probability export; public aggregates do not prove identity overlap.','A_source_result_sha256':c['source_zip']['sha256'],'A_outcome_version':c['outcome_version'],'A_own_point_directions':own,'A_rushing_role_views':role,'A_law_point_consistency':consistency,'A_law_binding_exclusions':binding_exclusions,'A_probability_controls_and_W5_7_slice':probability,'A_carry_mean_median':carryreport,'main_score_versions_preserved':True,'evidence':'EXPOSED_CURRENT_VINTAGE_TIMING_UNVERIFIED_RECONSTRUCTION;calendarW5_7isnotBmatched','private_input_authentication':{'references':len(refs),'full_scans':audit['full_scan_calls']},'original_numeric_MAE_roles':'QBpassing,RBrushing,RBWRTEreceiving,all5chart;newQB_RBviewsseparate','selection_limitations':'Own-side maxima concern different subsets; no adaptiveposthocsplice;push/void/unknownandunavailabledistinct; noROI.'}
  def parquet(v):
   buf=io.BytesIO();pq.write_table(pa.Table.from_pandas(v,preserve_index=False,nthreads=1),buf,compression='zstd');return buf.getvalue()
  entries={'AGGREGATES.json.gz':gzip.compress(enc(report),mtime=0),'CARRY_MEAN_MEDIAN_PRIVATE.parquet':parquet(j),'SAME_MODEL_MEDIAN_PROBABILITY_PRIVATE.parquet':parquet(pd.concat(privatechecks,ignore_index=True)),'OWNED_INPUT_AUDIT_PRIVATE.json':enc(audit),'CONFIGURATION_PRIVATE.json.gz':gzip.compress(enc(c),mtime=0)};entries['MANIFEST.json']=enc({k:{'bytes':len(v),'sha256':sha(v)} for k,v in entries.items()});buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for n,b in entries.items():z.writestr(n,b)
  result=put('RESULTS.zip',buf.getvalue());actual={'CPU_seconds':time.process_time()-begin,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};assert actual['CPU_seconds']<=c['resources']['CPU_seconds'] and actual['RSS_bytes']<=c['resources']['RSS_bytes'];terminal=put('COMPLETE.json',enc({'state':'COMPLETE_A_DIAGNOSTICS_NO_B_PAIRING_CLAIM','version':VERSION,'result':result,'actual_before_terminal':actual,'source_sha256':go['source_sha256'],'configuration_sha256':go['configuration_sha256'],'new_fits_inference':0}));actual={'CPU_seconds':time.process_time()-begin,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};assert actual['CPU_seconds']<=c['resources']['CPU_seconds'] and actual['wall_seconds']<=c['resources']['wall_seconds'] and actual['RSS_bytes']<=c['resources']['RSS_bytes'];return {'state':'COMPLETE_REQUIRES_NO_LATER_FAILURE','version':VERSION,'result':result,'terminal':terminal,'actual':actual,'new_fits_inference_B_pairs':0}
 except BaseException as e:
  put('FAILURE.json',enc({'state':'FAILED_PRESERVED','stage':stage,'type':type(e).__name__,'private_error':str(e),'CPU_seconds':time.process_time()-begin}));raise
def main():
 a=argparse.ArgumentParser();a.add_argument('--plan',type=Path);a.add_argument('--go',type=Path);a.add_argument('--fixtures',action='store_true');v=a.parse_args()
 if v.fixtures:print(enc(fixtures()).decode());return
 c=json.loads(gzip.decompress(v.plan.read_bytes()));go=json.loads(v.go.read_bytes());cap=c['resources'];resource.setrlimit(resource.RLIMIT_CPU,(cap['CPU_seconds'],cap['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(cap['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('A/Bcachedwall')));signal.alarm(cap['wall_seconds']);sys.addaudithook(lambda e,a:(_ for _ in ()).throw(RuntimeError('offline cachedcomparison')) if e in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None);print(enc(execute(c,go)).decode());signal.alarm(0)
if __name__=='__main__':main()
