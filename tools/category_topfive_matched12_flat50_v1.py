"""Frozen numeric-threshold 50/50 control; cached laws only, no fit or bootstrap."""
from pathlib import Path
from decimal import Decimal
import argparse,gzip,hashlib,io,json,math,os,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-flat-decisive50-v1.1'
KEY=['target','season','week','game_id','player_id','team','opponent','cutoff_utc','offer_id']
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def exact(r):
 p=Path(r['path']);assert p.is_absolute() and p.resolve()==p and not any(x.is_symlink() for x in [p,*p.parents]);a=p.stat();b=p.read_bytes();z=p.stat();assert len(b)==r['bytes']==a.st_size<=16*1024**2 and sha(b)==r['sha256'] and (a.st_dev,a.st_ino,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_mtime_ns);return b
def loss(x):
 import numpy as np
 a=np.asarray(x,float);assert not np.isnan(a).any();p=int(np.isposinf(a).sum());n=int(np.isneginf(a).sum());state='UNAVAILABLE_NO_SCORED_ROWS' if not len(a) else 'UNDEFINED_MIXED_INFINITIES' if p and n else 'POSITIVE_INFINITY' if p else 'NEGATIVE_INFINITY' if n else 'FINITE'
 return {'n':len(a),'state':state,'value':float(a.mean()) if state=='FINITE' else None,'positive_infinite_rows':p,'negative_infinite_rows':n}
def difference(a,b):
 import numpy as np
 a=np.asarray(a,float);b=np.asarray(b,float);assert len(a)==len(b) and not np.isnan(a).any() and not np.isnan(b).any();both=np.isposinf(a)&np.isposinf(b)
 if both.any():return {'n':len(a),'state':'UNDEFINED_PAIRED_BOTH_POSITIVE_INFINITY','value':None,'both_positive_infinite_rows':int(both.sum()),'no_rows_dropped':True}
 with np.errstate(invalid='raise'):d=a-b
 return {**loss(d),'no_rows_dropped':True}
def flat_values(part,y,L):
 if str(part).lower()=='dnp':return 'DNP',None,None,None
 if part!='played':return 'UNKNOWN',None,None,None
 if y is None or math.isnan(float(y)):return 'PLAYED_MISSING',None,None,None
 assert math.isfinite(float(y));a,b=Decimal(str(y)),Decimal(str(L));assert b.is_finite();event=0 if a<b else 2 if a>b else 1
 return 'SCORED',event,.75 if event==1 else .25,math.inf if event==1 else math.log(2)
def summary(f):
 s=f.loc[f.control_state.eq('SCORED')];dec=s.loc[s.event_index.ne(1)]
 return {'opportunities':len(f),'scored':len(s),'games':int(s.game_id.nunique()),'weeks':sorted(map(int,s.week.unique())),'states':f.control_state.value_counts().to_dict(),'push_outcomes':int(s.event_index.eq(1).sum()),'half_three_outcome_Brier':loss(s.flat_Brier),'three_outcome_log_loss':loss(s.flat_log_loss),'decisive_only_binary_Brier':loss(dec.flat_Brier),'decisive_only_binary_log_loss':loss(dec.flat_log_loss),'selection':{'policy':'EXACT_PROBABILITY_TIE_ABSTAIN','abstain':len(f),'Over_decided':0,'Under_decided':0,'Over_hit_rate':None,'Under_hit_rate':None,'reason':'No selected side; 50/50 is a probability benchmark, not 0% accuracy.'}}
def execute(cfg,go):
 S=time.monotonic();C=time.process_time();assert go['state']=='ROOT_AND_INDEPENDENT_GO' and go['registered_by']=='/root' and go['worker_sha256']==sha(Path(__file__).read_bytes()) and go['configuration_sha256']==sha(enc(cfg));assert cfg['version']==VERSION and cfg['resources']=={'CPU_seconds':180,'wall_seconds':420,'RSS_bytes':536870912,'AS_bytes':4294967296,'private_bytes':1048576};assert cfg['labels_member_sha256']=='65cb09b5b4644ec263884b974b3fbbd83b235012408bdd46b432944ce7582883'
 original=json.loads(gzip.decompress(exact(cfg['original_law_plan'])));assert sha(enc(original)+b'\n')==cfg['original_law_plan_canonical_sha256'];assert original['labels']['sha256']==cfg['labels_package_sha256'] and original['labels']['member']=='QUALIFIED_LABELS.parquet' and original['labels']['member_sha256']==cfg['labels_member_sha256'];assert original['offers']['sha256']==cfg['offers_package_sha256'] and original['offers']['member_sha256']==cfg['offers_member_sha256']
 sys.path.insert(0,str(ROOT));import nfl_lab
 assert Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab'
 from tools import category_topfive_matched12_storage_v1 as st
 from nfl_lab.owned_reference_batch import validate_owned_references
 import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 assert sha(Path(st.__file__).read_bytes())==cfg['storage_helper_sha256']
 store,_=st.open_store(ROOT,allocation_sha256=cfg['allocation_sha256'],root_go=st.GO);out=store.forward_root/'research'/cfg['run_id'];assert cfg['run_id'].startswith('matched12-flat50-') and '/' not in cfg['run_id'] and not out.exists();store.register_root(out);used=0
 def put(name,b):
  nonlocal used
  assert used+len(b)+(0 if name=='FAILURE.json' else 32768)<=cfg['resources']['private_bytes'];store.write_bytes(out/name,b);r=store.validate_reference(out/name,sha(b));used+=len(b);return {k:r[k] for k in ['bytes','sha256']}
 put('STARTED.json',enc({'version':VERSION,'state':'STARTED_BEFORE_CACHED_OUTCOME_READ','source_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256']}));stage='OWNERSHIP'
 try:
  # Exactly one grouped original-owner input batch; no model/source-feed reads.
  refs={c['package']['path']:c['package']['sha256'] for c in cfg['cells']};assert len(refs)==24
  for key in ['source_terminal','evaluation_bindings','source_started']:refs[cfg[key]['path']]=cfg[key]['sha256']
  assert len(refs)==27;_,audit=validate_owned_references(store,refs);parts=[];skipped=[]
  started=json.loads(exact(cfg['source_started']));assert started['state']=='STARTED_BEFORE_LABEL_READ' and started['plan_sha256']==cfg['original_law_plan_canonical_sha256'];terminal=json.loads(gzip.decompress(exact(cfg['source_terminal'])));binding=json.loads(exact(cfg['evaluation_bindings']));assert terminal['state']=='COMPLETED_FROZEN_LAW_COMPARISON';assert binding['labels_sha256']==cfg['labels_package_sha256'] and binding['offers_sha256']==cfg['offers_package_sha256'] and binding['specs']==original['specs'];specs={s['cell_id']:s for s in binding['specs']};completed={s['cell_id']:s for s in terminal['cells']};assert len(specs)==len(completed)==24 and set(specs)==set(completed)=={c['cell_id'] for c in cfg['cells']}
  stage='CACHED_LAW_SCORECARD_READ_AFTER_GO'
  for cell in cfg['cells']:
   with zipfile.ZipFile(io.BytesIO(exact(cell['package']))) as z:
    m=json.loads(z.read('MANIFEST.json'));assert m['spec']==specs[cell['cell_id']] and m['spec']['target']==cell['target'] and m['law_helper_sha256']==cfg['law_helper_sha256'];c=completed[cell['cell_id']];assert c['state']=='SCORED_FROZEN_LAW' and c['artifact']=={k:cell['package'][k] for k in ['bytes','sha256']}
    if cell['target']=='chart_ppr':skipped.append({'cell_id':cell['cell_id'],'reason':'NO_ACTUAL_CHART_OFFER'});continue
    assert cell['target'] not in ['anytime_td','rec_tgt'];f=pq.read_table(io.BytesIO(z.read('OFFER_PROBABILITY_SCORECARD.parquet')),columns=KEY+['line','actual','participation_state','position','primary_role','method','arm','score_state','Brier','log_loss'],use_threads=False).to_pandas(use_threads=False);assert f.target.eq(cell['target']).all() and f.primary_role.eq(f.position.isin(m['spec']['primary_roles'])).all();f['source_cell_id']=cell['cell_id'];parts.append(f)
  allrows=pd.concat(parts,ignore_index=True);assert set(allrows.arm)=={'FOOTBALL','SHRINK_0_5'} and not allrows.duplicated(KEY+['method','arm']).any();allrows['cutoff_utc']=pd.to_datetime(allrows.cutoff_utc,utc=True);allrows['_line']=allrows.line.map(lambda x:format(Decimal(str(x)).normalize(),'f'));base=allrows[KEY+['_line','actual','participation_state','primary_role']].drop_duplicates();assert not base.duplicated(KEY).any(),'incompatible actual/line/participation/role across methods';base=base.sort_values(KEY,kind='stable').reset_index(drop=True);assert len(base)<=3998
  known=base.participation_state.eq('played')&base.actual.notna();assert np.isfinite(base.loc[known,'actual'].to_numpy(float)).all();assert not (base.actual.notna()&~base.participation_state.eq('played')).any();v=[flat_values(p,y,L) for p,y,L in base[['participation_state','actual','_line']].to_numpy()];base[['control_state','event_index','flat_Brier','flat_log_loss']]=pd.DataFrame(v,index=base.index);base['p_under']=.5;base['p_push']=0.;base['p_over']=.5;base['side']='abstain'
  pairs=[]
  for (target,method,arm),f in allrows.groupby(['target','method','arm'],sort=True):
   j=f.merge(base[KEY+['control_state','flat_Brier','flat_log_loss','event_index']],on=KEY,how='left',validate='one_to_one');assert j.control_state.notna().all()
   for scope,pop in [('PRIMARY_ROLES',j.loc[j.primary_role]),('ALL_OFFERED_ROLES_SECONDARY',j)]:
    for week in [None]+sorted(map(int,pop.week.unique())):
     g=pop if week is None else pop.loc[pop.week.eq(week)];s=g.loc[g.score_state.eq('SCORED')];assert s.control_state.eq('SCORED').all() and not s[['Brier','log_loss']].isna().any().any()
     pairs.append({'target':target,'method':method,'arm':arm,'scope':scope,'week':week,'source_opportunities':len(g),'source_states':g.score_state.value_counts().to_dict(),'matched_scored':len(s),'games':int(s.game_id.nunique()),'week_clusters':int(s.week.nunique()),'push_outcomes':int(s.event_index.eq(1).sum()),'half_three_outcome_Brier':{'flat':loss(s.flat_Brier),'source':loss(s.Brier),'flat_minus_source':difference(s.flat_Brier,s.Brier)},'three_outcome_log_loss':{'flat':loss(s.flat_log_loss),'source':loss(s.log_loss),'flat_minus_source':difference(s.flat_log_loss,s.log_loss)}})
  categories=[]
  for scope,pop in [('PRIMARY_ROLES',base.loc[base.primary_role]),('ALL_OFFERED_ROLES_SECONDARY',base)]:
   categories += [{'target':str(t),'scope':scope,'all_weeks':summary(f),'weekly':[{'week':int(w),'metrics':summary(g)} for w,g in f.groupby('week',sort=True)]} for t,f in pop.groupby('target',sort=True)]
  report={'version':VERSION,'state':'CACHED_FLAT50_CONTROL_SCORED','primary':'HALF_THREE_OUTCOME_BRIER','formula':'Under=.5,Push=0,Over=.5; Brier=.25 decisive/.75 exact-line; logloss=log(2) decisive/+infinity exact-line','conditioning':'Played statistical event; venue settlement unqualified.','catalog':'Probability-only numeric-threshold control, not a full statistic CDF or anytime-TD control.','board_scope':'Exact frozen law primary-offer board; primary-role headline per frozen spec, all-offered-role secondary distinct.','primary_role_counts':{str(k):int(v) for k,v in base.primary_role.value_counts().items()},'categories':categories,'matched_method_arms':pairs,'skipped':skipped,'unique_primary_opportunities':int(base.primary_role.sum()),'unique_all_offered_opportunities':len(base),'source_offer_output_rows':len(allrows),'owned_input_batch':{'references':len(refs),'full_scans':audit['full_scan_calls'],'scope':'Original managed owner authenticated once; full audit private only'},'no_new_fits_inference_bootstrap_HTTP':True,'uncertainty':'No new bootstrap; simple matched means/differences only. Original law CIs remain separate.','evidence':'EXPOSED_CURRENT_VINTAGE_TIMING_UNVERIFIED_2026_REG_W1_7'}
  b=io.BytesIO();pq.write_table(pa.Table.from_pandas(base,preserve_index=False,nthreads=1),b,compression='zstd');entries={'FLAT_PROBABILITIES_AND_OUTCOMES.parquet':b.getvalue(),'OWNED_INPUT_AUDIT_PRIVATE.json':enc(audit),'AGGREGATES.json.gz':gzip.compress(enc(report),mtime=0)};entries['MANIFEST.json']=enc({k:{'bytes':len(v),'sha256':sha(v)} for k,v in entries.items()});b=io.BytesIO()
  with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for name,raw in entries.items():z.writestr(name,raw)
  stage='PERSISTENCE';package=put('SCORE_PACKAGE.zip',b.getvalue());actual={'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};assert actual['CPU_seconds']<=180 and actual['wall_seconds']<=420 and actual['RSS_bytes']<=536870912
  receipt={'version':VERSION,'state':'COMPLETE_FLAT50_CONTROL_REQUIRES_NO_LATER_FAILURE','package':package,'actual_before_terminal_write':actual,'configuration_sha256':go['configuration_sha256'],'unique_primary_opportunities':int(base.primary_role.sum()),'unique_all_offered_opportunities':len(base),'source_offer_output_rows':len(allrows),'new_fits_inference_bootstrap_HTTP':0};terminal=put('COMPLETE.json',enc(receipt));actual={'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};assert actual['CPU_seconds']<=180 and actual['wall_seconds']<=420 and actual['RSS_bytes']<=536870912;return {**receipt,'state':'COMPLETE_FLAT50_CONTROL','actual':actual,'terminal':terminal,'later_failure_overrides_completion':True}
 except BaseException as e:
  put('FAILURE.json',enc({'version':VERSION,'state':'FAILED_RETAINED','stage':stage,'private_error':str(e),'error_type':type(e).__name__,'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S}));raise
def main():
 a=argparse.ArgumentParser();a.add_argument('--plan',required=True,type=Path);a.add_argument('--go',required=True,type=Path);v=a.parse_args();cfg=json.loads(gzip.decompress(v.plan.read_bytes()));go=json.loads(v.go.read_bytes());cap=cfg['resources'];resource.setrlimit(resource.RLIMIT_CPU,(cap['CPU_seconds'],cap['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(cap['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('flat50wall')));signal.alarm(cap['wall_seconds']);sys.addaudithook(lambda e,a:(_ for _ in ()).throw(RuntimeError('offline cached scorer')) if e in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None);print(enc(execute(cfg,go)).decode());signal.alarm(0)
if __name__=='__main__':main()
