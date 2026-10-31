"""Frozen exploratory conditional M/H comparison. No fits, HTTP, EV or live use.

The offered-board and prediction eligibility determine selections before any
outcome is used. Binary conditional loss excludes pushes; selected pushes,
DNP and unresolved outcomes remain in selection counts. Root GO required.
"""
from __future__ import annotations
import copy,gzip,hashlib,importlib.util,io,json,math,resource,signal,sys,time,zipfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-exploratory-conditional-market-score-v1'
NUMERIC=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd']
BASE=['target','season','week','game_id','player_id','team','opponent','cutoff_utc']
JOIN=BASE+['_line']
ARMS=['F_CONDITIONAL','S_CONDITIONAL','H_FIXED_HALF']
POLICIES=['FULL_BOARD','ABSTAIN_0_55','TOP_6','TOP_10','TOP_20','ALWAYS_OVER','ALWAYS_UNDER']
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,(Decimal,)):return str(v)
 if isinstance(v,float) and not math.isfinite(v):return {'state':'POSITIVE_INFINITY' if v==float('inf') else 'NEGATIVE_INFINITY' if v==-float('inf') else 'UNDEFINED_NAN'}
 return v
def enc(v):return json.dumps(clean(v),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def canonical(frame,linecol):
 import pandas as pd
 f=frame.copy();need(set(BASE+[linecol])<=set(f),'identity/line columns missing')
 def threshold(v):
  d=Decimal(str(v));need(d.is_finite(),'finite original line required');return '0' if d==0 else format(d.normalize(),'f')
 f['_line']=f[linecol].map(threshold)
 for v in f.cutoff_utc.dropna().unique():need(pd.Timestamp(v).tzinfo is not None,'unknown cutoff timezone')
 f['cutoff_utc']=pd.to_datetime(f.cutoff_utc,utc=True);need(f.cutoff_utc.notna().all(),'missing information cutoff')
 need(f.season.eq(2026).all() and f.week.between(1,7).all() and f.target.isin(NUMERIC).all(),'fixed numeric W1-7 scope only')
 return f

def conditional(log_under,log_over):
 import numpy as np
 u,o=np.asarray(log_under,float),np.asarray(log_over,float);need(u.shape==o.shape,'event log shape mismatch')
 need(not np.isposinf(u).any() and not np.isposinf(o).any() and not (u>1e-10).any() and not (o>1e-10).any(),'invalid event log probability')
 d=np.logaddexp(u,o);eligible=~np.isnan(u)&~np.isnan(o)&np.isfinite(d);need(not (d[eligible]>1e-10).any(),'incoherent decisive event mass')
 lu=np.full(u.shape,np.nan);lo=lu.copy();lu[eligible]=u[eligible]-d[eligible];lo[eligible]=o[eligible]-d[eligible]
 return lu,lo,eligible

def market_logs(q):
 import numpy as np
 q=np.asarray(q,float);ok=np.isfinite(q)&(q>=0)&(q<=1);lu=np.full(q.shape,np.nan);lo=lu.copy()
 with np.errstate(divide='ignore'):lu[ok]=np.log1p(-q[ok]);lo[ok]=np.log(q[ok])
 return lu,lo,ok

def mixture(fu,fo,mu,mo):
 import numpy as np
 ok=~np.isnan(fu)&~np.isnan(fo)&~np.isnan(mu)&~np.isnan(mo);u=np.full(np.shape(fu),np.nan);o=u.copy()
 u[ok]=np.logaddexp(fu[ok]-np.log(2),mu[ok]-np.log(2));o[ok]=np.logaddexp(fo[ok]-np.log(2),mo[ok]-np.log(2))
 return u,o,ok

def freeze_selections(frame,eligible=None):
 """Only identity and prediction columns are consulted; never actual/status."""
 import numpy as np
 need(not {'actual','participation_state','event','score_state','Brier','log_loss'}&set(frame),'outcome/status columns forbidden at selection freeze')
 f=frame.copy();valid=f.prediction_eligible.to_numpy(bool)
 if eligible is not None:valid &= np.asarray(eligible,bool)
 u,o=f.log_under.to_numpy(float),f.log_over.to_numpy(float);side=np.full(len(f),'unavailable',object);side[valid]='abstain';side[valid&(o>u)]='over';side[valid&(u>o)]='under'
 f['side']=side;confidence=np.full(len(f),np.nan);confidence[valid]=np.exp(np.maximum(u[valid],o[valid]));f['confidence']=confidence;f['policy_eligible']=valid
 selected=valid&np.isin(side,['over','under']);f['select_FULL_BOARD']=selected;f['select_ABSTAIN_0_55']=selected&(confidence>=.55)
 rank=f.loc[selected].sort_values(['target','week','confidence','game_id','player_id','opportunity_key'],ascending=[True,True,False,True,True,True],kind='stable')
 for k in [6,10,20]:f['select_TOP_'+str(k)]=False;f.loc[rank.groupby(['target','week'],sort=False).head(k).index,'select_TOP_'+str(k)]=True
 f['select_ALWAYS_OVER']=valid;f['select_ALWAYS_UNDER']=valid
 return f

def grade(frame):
 import numpy as np
 f=frame.copy();state=f.participation_state.fillna('unknown').str.lower();actual=f.actual.to_numpy(float);played=state.eq('played').to_numpy();known=played&np.isfinite(actual)
 event=np.full(len(f),np.nan)
 for i in np.flatnonzero(known):
  y,L=Decimal(str(actual[i])),Decimal(f.iloc[i]['_line']);need(y==y.to_integral_value(),'numeric official outcome off integer lattice');event[i]=1 if y>L else 0 if y<L else 2
 f['event']=event;ok=f.prediction_eligible.to_numpy(bool);decisive=known&(event!=2)&ok
 f['score_state']=np.where(~ok,'NO_SUPPORTED_CONDITIONAL_PROBABILITY',np.where(state.eq('dnp'),'DNP',np.where(~played,'UNKNOWN_PARTICIPATION',np.where(~np.isfinite(actual),'PLAYED_MISSING',np.where(event==2,'EXACT_LINE_PUSH','SCORED')))))
 f['p_over_given_decisive']=np.exp(f.log_over);f['Brier']=np.nan;f['log_loss']=np.nan
 f.loc[decisive,'Brier']=(f.p_over_given_decisive.to_numpy()[decisive]-event[decisive])**2
 f.loc[decisive,'log_loss']=-np.where(event[decisive]==1,f.log_over.to_numpy()[decisive],f.log_under.to_numpy()[decisive])
 f['venue_settlement']='UNQUALIFIED_NOT_INFERRED_FROM_STATISTICAL_DIRECTION';return f

def statistical_results(frame,side):
 import numpy as np
 side=np.asarray(side,object);event=frame.event.to_numpy(float);part=frame.participation_state.fillna('unknown').str.lower().to_numpy()
 return np.where(side=='unavailable','UNAVAILABLE',np.where(side=='abstain','ABSTAIN',np.where(part=='dnp','DNP',np.where(~np.isfinite(event),'UNRESOLVED',np.where(event==2,'PUSH',np.where((side=='over')==(event==1),'WIN','LOSS'))))))

def interval(x,groups,cfg,aux):
 import numpy as np
 x=np.asarray(x,float)
 if not np.isfinite(x).all():return {'state':'UNAVAILABLE_NONFINITE_LOSSES_RETAINED','rows':len(x)}
 return aux._interval(x,groups,cfg)

def probability_summary(frame,loss,aux,uncertainty):
 s=frame.loc[frame.score_state.eq('SCORED')];out={'opportunities':len(frame),'supported_predictions':int(frame.prediction_eligible.sum()),'scored_decisive':len(s),'games':int(s.game_id.nunique()),'weeks':sorted(map(int,s.week.unique())),'states':frame.score_state.value_counts().to_dict()}
 for metric in ['Brier','log_loss']:
  out[metric]=loss.loss_summary(s[metric].to_numpy(float));out[metric]['intervals']={c:interval(s[metric],s[c],uncertainty,aux) for c in ['game_id','week']}
 out['over_reliability']=[]
 for i in range(10):
  g=s.loc[s.p_over_given_decisive.ge(i/10)&(s.p_over_given_decisive.lt((i+1)/10) if i<9 else s.p_over_given_decisive.le(1))]
  out['over_reliability'].append({'bin':i,'n':len(g),'predicted':float(g.p_over_given_decisive.mean()) if len(g) else None,'observed_over':float(g.event.mean()) if len(g) else None})
 return out

def selection_summary(frame,policy,loss,aux,uncertainty):
 import numpy as np
 selected=frame.loc[frame['select_'+policy]];side=np.full(len(selected),'over' if policy=='ALWAYS_OVER' else 'under',object) if policy.startswith('ALWAYS_') else selected.side.to_numpy()
 results=statistical_results(selected,side);counts={str(k):int(v) for k,v in zip(*np.unique(results,return_counts=True))};w=counts.get('WIN',0);l=counts.get('LOSS',0)
 out={'offered_pool':len(frame),'prediction_eligible':int(frame.policy_eligible.sum()),'selected':len(selected),'coverage':len(selected)/len(frame) if len(frame) else None,'not_selected':len(frame)-len(selected),'counts':counts,'decided':w+l,'hit_rate':w/(w+l) if w+l else None,'exact_probability_ties':int((frame.side=='abstain').sum()),'independent_decided_games':int(selected.loc[np.isin(results,['WIN','LOSS']),'game_id'].nunique()),'independent_decided_weeks':int(selected.loc[np.isin(results,['WIN','LOSS']),'week'].nunique())}
 for s in ['over','under']:
  r=results[side==s];wins=int((r=='WIN').sum());miss=int((r=='LOSS').sum());out[s]={'wins':wins,'losses':miss,'decided':wins+miss,'hit_rate':wins/(wins+miss) if wins+miss else None,'all_statuses':{str(k):int(v) for k,v in zip(*np.unique(r,return_counts=True))}}
 decided=np.isin(results,['WIN','LOSS']);out['hit_rate_intervals']={c:interval((results[decided]=='WIN').astype(float),selected.loc[decided,c],uncertainty,aux) for c in ['game_id','week']}
 out['selected_probability_scores']=probability_summary(selected,loss,aux,uncertainty);out['venue_returns']=None;return out

def paired(a,b,loss,aux,uncertainty):
 j=a.merge(b,on='opportunity_key',validate='one_to_one',suffixes=('_candidate','_control'));sc=j.loc[j.score_state_candidate.eq('SCORED')&j.score_state_control.eq('SCORED')];out={'matched_prediction_rows':len(j),'matched_decisive':len(sc),'games':int(sc.game_id_candidate.nunique()),'weeks':int(sc.week_candidate.nunique())}
 for metric in ['Brier','log_loss']:
  x,y=sc[metric+'_candidate'].to_numpy(float),sc[metric+'_control'].to_numpy(float);out[metric]=loss.paired_summary(x,y);out[metric]['intervals']={c:interval(x-y,sc[c+'_candidate'],uncertainty,aux) if __import__('numpy').isfinite(x).all() and __import__('numpy').isfinite(y).all() else {'state':'UNAVAILABLE_NONFINITE_LOSSES_RETAINED'} for c in ['game_id','week']}
 decisive=j.loc[j.side_candidate.isin(['over','under'])&j.side_control.isin(['over','under'])&j.event_candidate.isin([0,1])&j.event_control.isin([0,1])]
 out['complete_decisions']={}
 for name,g in [('common_board',decisive),('disagreements',decisive.loc[decisive.side_candidate.ne(decisive.side_control)])]:
  x=((g.side_candidate=='over')==(g.event_candidate==1)).to_numpy(float);y=((g.side_control=='over')==(g.event_control==1)).to_numpy(float)
  out['complete_decisions'][name]={'rows':len(g),'candidate_correct':int(x.sum()),'control_correct':int(y.sum()),'difference':float((x-y).mean()) if len(g) else None,'intervals':{c:interval(x-y,g[c+'_candidate'],uncertainty,aux) for c in ['game_id','week']}}
 return out

def score(packet,law_frames,config,loss,aux):
 import numpy as np,pandas as pd
 packet=canonical(packet,'line_exact');need(not packet.duplicated(JOIN).any() and not packet.opportunity_key.duplicated().any(),'primary opportunity duplicate')
 need(len(packet)==3998,'frozen original primary board changed');facts=[];prepared=[]
 for spec,frame in law_frames:
  f=canonical(frame,'line');need(set(['actual','participation_state','method','arm','log_p_under','log_p_over','fallback'])<=set(f),'source probability scorecard incomplete')
  need(f.arm.isin(['FOOTBALL','SHRINK_0_5']).all(),'unsupported law arm');need(not f.duplicated(JOIN+['method','arm']).any(),'source method-arm duplicate')
  facts.append(f[JOIN+['actual','participation_state']]);prepared.append((spec,f))
 need(facts,'no successful numeric law records available')
 facts=pd.concat(facts,ignore_index=True);facts['participation_state']=facts.participation_state.fillna('unknown').str.lower();facts['_actual_token']=facts.actual.map(lambda x:'MISSING' if pd.isna(x) else str(Decimal(str(x)).normalize()))
 facts=facts.drop_duplicates(JOIN+['participation_state','_actual_token']);need(not facts.duplicated(JOIN).any(),'outcome version/participation conflict across laws')
 need(not (facts.actual.notna()&facts.participation_state.ne('played')).any(),'unknown/DNP actual is not zero')
 master=packet.merge(facts[JOIN+['actual','participation_state']],on=JOIN,how='left',validate='one_to_one');master['participation_state']=master.participation_state.fillna('unknown');basecols=JOIN+['opportunity_key','actual','participation_state']
 mlogs=market_logs(master.market_q_over_given_decisive);same=market_logs(master.samebook_q_over_given_decisive)
 def build(base,procedure,arm,logs):
  f=base[JOIN+['opportunity_key']].copy();f['procedure_id']=procedure;f['arm']=arm;f['log_under'],f['log_over'],f['prediction_eligible']=logs;f['fallback']='';f=freeze_selections(f);f['actual']=base.actual.to_numpy();f['participation_state']=base.participation_state.to_numpy();return grade(f)
 boards=[build(master,'M_EXCLUDED_BOOK_Q_V1','M_EXCLUDED',mlogs),build(master,'M_OFFERING_BOOK_NONINDEPENDENT_Q_V1','M_SAMEBOOK',same)];comparisons=[];members=[];common_decisions=[];source_coverage=[]
 for spec,source in prepared:
  for method in sorted(source.method.unique()):
   procedure=spec['cell_id']+'::'+method;target=spec['target'];base=master.loc[master.target.eq(target)].copy();needed=base[JOIN].copy();arms={}
   for src,arm in [('FOOTBALL','F_CONDITIONAL'),('SHRINK_0_5','S_CONDITIONAL')]:
    f=source.loc[source.method.eq(method)&source.arm.eq(src)];need(not f.duplicated(JOIN).any(),'source arm duplicates');j=needed.merge(f[JOIN+['log_p_under','log_p_over','fallback']],on=JOIN,how='left',validate='one_to_one')
    logs=conditional(j.log_p_under,j.log_p_over);arms[arm]=build(base,procedure,arm,logs);arms[arm]['fallback']=j.fallback.fillna('NO_MATCHED_FROZEN_LAW_RECORD').to_numpy()
   market=boards[0].loc[boards[0].target.eq(target)].copy();msame=boards[1].loc[boards[1].target.eq(target)].copy();f=arms['F_CONDITIONAL'];hlogs=mixture(f.log_under.to_numpy(),f.log_over.to_numpy(),market.log_under.to_numpy(),market.log_over.to_numpy());arms['H_FIXED_HALF']=build(base,procedure,'H_FIXED_HALF',hlogs)
   boards.extend(arms.values());common=f.prediction_eligible.to_numpy()&market.prediction_eligible.to_numpy();members.append(pd.DataFrame({'comparison_id':procedure,'opportunity_key':base.opportunity_key,'common_prediction_eligible':common}))
   for scope,mask in [('FULL_OPERATIONAL',None),('COMMON_F_M_H_PREDICTION_POOL',common)]:
    views={**arms,'M_EXCLUDED':market,'M_SAMEBOOK':msame}
    if mask is not None:
     changed={}
     for k,v in views.items():
      predictions=v.drop(columns=['actual','participation_state','event','score_state','Brier','log_loss'],errors='ignore');frozen=freeze_selections(predictions,mask);frozen['actual']=v.actual.to_numpy();frozen['participation_state']=v.participation_state.to_numpy();changed[k]=grade(frozen)
     views=changed
    # These masks and rankings were constructed without referencing outcomes.
    for arm,v in views.items():
     if mask is not None:
      g=v[['opportunity_key','side','policy_eligible']+['select_'+p for p in POLICIES]].copy();g['comparison_id']=procedure;g['arm']=arm;common_decisions.append(g)
     comparisons.append({'comparison_id':procedure,'target':target,'arm':arm,'scope':scope,'probability':probability_summary(v if mask is None else v.loc[v.policy_eligible],loss,aux,config['uncertainty']),'policies':[{'policy':p,'metrics':selection_summary(v,p,loss,aux,config['uncertainty'])} for p in POLICIES],'weekly':[{'week':int(w),'probability':probability_summary(v.loc[v.week.eq(w)&(v.policy_eligible if mask is not None else True)],loss,aux,config['uncertainty']),'policies':[{'policy':p,'metrics':selection_summary(v.loc[v.week.eq(w)],p,loss,aux,config['uncertainty'])} for p in POLICIES]} for w in sorted(v.week.unique())]})
   controls={**arms,'M_EXCLUDED':market,'M_SAMEBOOK':msame};pairs=[]
   for candidate,control in [('H_FIXED_HALF','F_CONDITIONAL'),('H_FIXED_HALF','M_EXCLUDED'),('M_EXCLUDED','F_CONDITIONAL'),('S_CONDITIONAL','F_CONDITIONAL'),('M_SAMEBOOK','M_EXCLUDED')]:
    a,b=controls[candidate],controls[control];eligible=a.prediction_eligible&b.prediction_eligible;pairs.append({'candidate':candidate,'control':control,'metrics':paired(a.loc[eligible],b.loc[eligible],loss,aux,config['uncertainty'])})
   source_coverage.append({'comparison_id':procedure,'target':target,'primary_board':len(base),'F_supported':int(f.prediction_eligible.sum()),'S_supported':int(arms['S_CONDITIONAL'].prediction_eligible.sum()),'M_supported':int(market.prediction_eligible.sum()),'common_F_M_H_before_outcomes':int(common.sum()),'pairwise':pairs})
 full=pd.concat(boards,ignore_index=True);line_rows=master.loc[master.participation_state.eq('played')&master.actual.notna()].copy();line_rows['line_point']=line_rows._line.astype(float);line_rows['signed_error']=line_rows.line_point-line_rows.actual;line_rows['absolute_error']=line_rows.signed_error.abs();line_summaries=[]
 for target,g in line_rows.groupby('target'):
  line_summaries.append({'target':target,'n':len(g),'MAE':float(g.absolute_error.mean()),'MSE':float((g.signed_error**2).mean()),'RMSE':float(np.sqrt((g.signed_error**2).mean())),'bias':float(g.signed_error.mean()),'p90_absolute_error':float(g.absolute_error.quantile(.9)),'p95_absolute_error':float(g.absolute_error.quantile(.95)),'intervals':{c:interval(g.absolute_error,g[c],config['uncertainty'],aux) for c in ['game_id','week']}})
 report={'version':VERSION,'state':'COMPLETED_EXPLORATORY_CONDITIONAL_PROBABILITY_COMPARISON','fullboard_method_summaries':comparisons,'matched_control_comparisons':source_coverage,'line_as_point':{'contract':'SINGLE_RECORDED_LINE_HEURISTIC_NOT_IDENTIFIED_MEAN_OR_MEDIAN','full_opportunities':len(master),'supported_outcomes':len(line_rows),'results':line_summaries},'probability_primary':'BINARY_BRIER_CONDITIONAL_ON_DECISIVE_SUPPORTED_STATISTICAL_OUTCOMES;NOT_THREE_OUTCOME_BRIER','selection':'Full source/prediction eligible board ranked before outcome grading; selected pushes/DNP/unknown retained; no replacement with settled rows.','uncertainty':config['uncertainty'],'evidence':'TIMING_UNVERIFIED_EXPOSED_HISTORICAL_RECONSTRUCTION; current-source outcome version fixed across arms','unsupported':{'chart_ppr':'NO_COMPATIBLE_ACTUAL_CHART_MARKET','rec_tgt':'TARGET_OFFER_UNAVAILABLE','anytime_td':'ONE_SIDED_NO_AUTHENTICATED_TWO_SIDED_REFERENCE'},'no_fits_HTTP_EV_profit_pregame_or_live_claim':True,'repeated_market_vectors':'M/Msame stored once; per-F comparison reuses identical vectors and is not independent evidence.'}
 return {'OPPORTUNITIES':master,'PROBABILITIES':full,'COMMON_MEMBERSHIP':pd.concat(members,ignore_index=True),'COMMON_SELECTIONS':pd.concat(common_decisions,ignore_index=True),'LINE_POINT_ERRORS':line_rows},report

def execute(config,go):
 """Root-reviewed actual scoring only; persist one complete private score ZIP."""
 start=time.monotonic();cpu=time.process_time()
 need(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root','root+independent GO required before any outcome')
 need(go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('configuration_sha256')==sha(enc(config)),'exact source/configuration binding')
 caps=config['resources'];need(caps['CPU_seconds']<=300,'unregistered score CPU expansion');need(config['uncertainty']=={'replicates':1000,'seed':20261030,'minimum_clusters':2},'registered uncertainty changed')
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('registered conditional market wall bound')));signal.alarm(caps['wall_seconds']);resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']+1))
 sys.addaudithook(lambda e,a:(_ for _ in ()).throw(RuntimeError('offline scoring only')) if e in {'socket.connect','socket.connect_ex','socket.getaddrinfo'} else None)
 sys.path.insert(0,str(ROOT));import nfl_lab
 need(Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab','root source package must bind before store')
 from tools import category_topfive_matched12_offer_driver_v1 as source,category_topfive_matched12_storage_v1 as storage
 from nfl_lab.owned_reference_batch import validate_owned_references
 for ref in config['source_pins'].values():source.read_exact(ref)
 def load(name,ref):
  s=importlib.util.spec_from_file_location(name,ref['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
 loss=load('conditional_market_loss',config['source_pins']['loss']);aux=load('conditional_market_interval',config['source_pins']['auxiliary'])
 import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 store,_=storage.open_store(ROOT,allocation_sha256=config['allocation_sha256'],root_go=storage.GO);out=store.forward_root/'research'/config['run_id']
 need(config['run_id'].startswith('matched12-exploratory-conditional-') and '/' not in config['run_id'] and not out.exists(),'fresh registered scoring namespace required');store.register_root(out);used=0
 def put(name,body):
  nonlocal used
  reserve=0 if name=='FAILURE.json' else 65536
  need(used+len(body)+reserve<=caps['private_bytes'],'complete conditional evidence allocation exhausted')
  store.write_bytes(out/name,body);used+=len(body);got=store.validate_reference(out/name,sha(body));return {k:got[k] for k in ['bytes','sha256']}
 put('STARTED.json',enc({'version':VERSION,'state':'STARTED_BEFORE_NEW_OUTCOME_JOIN','source_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'fits_HTTP':0}));put('CONFIGURATION.json',enc(config));stage='SOURCE_AUTHENTICATION'
 try:
  refs=[config['price_packet']]
  for s in config['law_inputs']:refs += [s[k] for k in ['package','source_report','evaluation_bindings']]
  unique={r['path']:r for r in refs};seen=set();audits=[]
  for owner in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]:
   items={r['path']:r['sha256'] for r in unique.values() if any(Path(r['path']).is_relative_to(Path(x)) for x in owner._roots)}
   need(not seen.intersection(items),'ambiguous managed owner')
   if items:
    got,a=validate_owned_references(owner,items);seen.update(got);audits.append({'references':len(got),'full_scans':a['full_scan_calls']})
  need(seen==set(unique),'every private input must authenticate original managed owner')
  stage='FROZEN_LAW_METADATA_ADMISSION';admitted=[];skipped=[]
  def document(ref):
   b=source.read_exact(ref);return json.loads(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b)
  for spec in config['law_inputs']:
   report=document(spec['source_report']);binding=document(spec['evaluation_bindings'])
   need(binding['labels_sha256']==config['labels_sha256'] and binding['offers_sha256']==config['prepared_offers_sha256'],'law evaluation outcome/offer version mismatch')
   cell=next(x for x in report['cells'] if x['cell_id']==spec['cell_id']);need(cell['state']=='SCORED_FROZEN_LAW','source law did not complete')
   need(all(cell['artifact'][k]==spec['package'][k] for k in ['bytes','sha256']),'law package terminal chain differs')
   with zipfile.ZipFile(io.BytesIO(source.read_exact(spec['package']))) as z:
    need(len(z.namelist())==len(set(z.namelist()))<=8,'ambiguous/oversized source law package');manifest=json.loads(z.read('MANIFEST.json'));need(manifest['spec']['cell_id']==spec['cell_id'] and manifest['spec']['target']==spec['target'],'source specification mismatch')
    need(manifest['law_helper_sha256']==config['source_pins']['loss']['sha256'],'law scorer source arithmetic differs')
    if spec['target'] not in NUMERIC:
     skipped.append({'cell_id':spec['cell_id'],'target':spec['target'],'reason':'NO_COMPATIBLE_NUMERIC_ACTUAL_MARKET'});continue
    need('OFFER_PROBABILITY_SCORECARD.parquet' in z.namelist(),'missing source offered probability scorecard')
    admitted.append((spec,z.read('OFFER_PROBABILITY_SCORECARD.parquet')))
  need(set(x['cell_id'] for x in config['law_inputs'])==set(config['expected_law_cell_ids']),'frozen requested cell inventory mismatch')
  stage='PACKET_AND_SOURCE_PROBABILITY_READ_AFTER_GO';packet=pq.read_table(io.BytesIO(source.read_exact(config['price_packet'])),use_threads=False).to_pandas(use_threads=False)
  need(len(packet)==3998 and packet.hybrid_q_weight.eq(.5).all() and packet.hybrid_football_weight.eq(.5).all(),'fixed packet population/weight changed')
  valid=packet.market_q_over_given_decisive.notna();need(packet.loc[valid,'reference_book_id'].ne(packet.loc[valid,'offering_book_id']).all(),'offering book entered independent reference')
  need(packet.authentic_pregame.eq(False).all() and packet.EV_or_return_supported.eq(False).all(),'unqualified source cannot become authentic or EV')
  frames=[];columns=BASE+['line','actual','participation_state','method','arm','log_p_under','log_p_over','fallback']
  for spec,b in admitted:
   f=pq.read_table(io.BytesIO(b),columns=columns,use_threads=False).to_pandas(use_threads=False);need(f.target.eq(spec['target']).all(),'cross-category law records');frames.append((spec,f))
  need(sum(len(f) for _,f in frames)<=caps['maximum_source_offer_records'],'bounded source record count exceeded')
  stage='OUTCOME_BLIND_SELECTION_AND_CONDITIONAL_SCORING';tables,report=score(packet,frames,config,loss,aux);report['source_cells_skipped']=skipped;report['source_failures_recorded_not_recreated']=config.get('source_failures',[])
  stage='COMPLETE_SCORE_PACKAGE_SERIALIZATION';entries={}
  for name,f in tables.items():
   b=io.BytesIO();pq.write_table(pa.Table.from_pandas(f,preserve_index=False,nthreads=1),b,compression='zstd');entries[name+'.parquet']=b.getvalue()
  report.update(actual={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},source_packet_sha256=config['price_packet']['sha256'],labels_sha256=config['labels_sha256'],source_law_packages=len(admitted),owned_reference_batches=audits,numerical_environment={'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pa.__version__})
  entries['AGGREGATES.json.gz']=gzip.compress(enc(report),mtime=0);entries['MEMBER_MANIFEST.json']=enc({k:{'bytes':len(v),'sha256':sha(v)} for k,v in entries.items()});b=io.BytesIO()
  with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_STORED) as z:
   for name,raw in entries.items():z.writestr(name,raw)
  package=put('SCORE_PACKAGE.zip',b.getvalue());stage='SAVED_PACKAGE_RESOURCE_AND_READBACK_ADMISSION'
  need(report['actual']['CPU_seconds']<=caps['CPU_seconds'] and report['actual']['wall_seconds']<=caps['wall_seconds'] and report['actual']['RSS_bytes']<=caps['RSS_bytes'],'resource envelope exceeded; saved output not admitted')
  receipt={'version':VERSION,'state':'COMPLETE_EXPLORATORY_STATISTICAL_COMPARISON_NOT_AUTHENTIC_MARKET_OR_RELEASE','package':package,'configuration_sha256':go['configuration_sha256'],'source_packet_sha256':config['price_packet']['sha256'],'new_fits_HTTP_live_writes':0,'actual':report['actual'],'offhost_restoration':'NOT_VERIFIED'};put('COMPLETE.json',enc(receipt));signal.alarm(0);return receipt,report
 except BaseException as e:
  failure={'version':VERSION,'state':'FAILED_CONDITIONAL_MARKET_COMPARISON_RETAINED','stage':stage,'error_type':type(e).__name__,'private_message':str(e),'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'fits_HTTP_live_writes':0};put('FAILURE.json',enc(failure));signal.alarm(0);raise
