"""Independent cached M/H arithmetic/selection QA; no fitting or law inference."""
from pathlib import Path
import gzip,hashlib,io,json,math,resource,signal,sys,time,zipfile
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]
POL=['FULL_BOARD','ABSTAIN_0_55','TOP_6','TOP_10','TOP_20','ALWAYS_OVER','ALWAYS_UNDER']
def enc(d):return json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def need(x,m):
 if not x:raise ValueError(m)
def execute(cfg,go):
 S=time.monotonic();C=time.process_time();need(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root' and go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('configuration_sha256')==sha(enc(cfg)),'exact QA GO required before cached outcomes')
 sys.path.insert(0,str(ROOT));import nfl_lab
 need(Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab','root binding')
 from tools import category_topfive_matched12_storage_v1 as st,category_topfive_matched12_offer_driver_v1 as rd
 from nfl_lab.owned_reference_batch import validate_owned_references
 import numpy as np,pandas as pd,pyarrow.parquet as pq
 plan=json.loads(rd.read_exact(cfg['source_configuration']));need(sha(enc(plan))==cfg['source_configuration_canonical_sha256'],'source configuration changed')
 refs=[cfg['package'],cfg['source_configuration'],plan['price_packet']]+[x['package'] for x in plan['law_inputs']];store,_=st.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=st.GO,readonly=True);unique={r['path']:r for r in refs};seen=set();audits=[]
 for owner in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]:
  b={r['path']:r['sha256'] for r in unique.values() if any(Path(r['path']).is_relative_to(Path(x)) for x in owner._roots)};need(not seen.intersection(b),'ambiguous owner')
  if b:got,a=validate_owned_references(owner,b);seen.update(got);audits.append({'references':len(got),'full_scans':a['full_scan_calls']})
 need(seen==set(unique),'all inputs require original owner')
 with zipfile.ZipFile(io.BytesIO(rd.read_exact(cfg['package']))) as z:
  manifest=json.loads(z.read('MEMBER_MANIFEST.json'));parts={}
  for name,m in manifest.items():
   b=z.read(name);need(len(b)==m['bytes'] and sha(b)==m['sha256'],'saved package member differs');parts[name]=b
 report=json.loads(gzip.decompress(parts['AGGREGATES.json.gz']));P=pq.read_table(io.BytesIO(parts['PROBABILITIES.parquet']),use_threads=False).to_pandas(use_threads=False);O=pq.read_table(io.BytesIO(parts['OPPORTUNITIES.parquet']),use_threads=False).to_pandas(use_threads=False);M=pq.read_table(io.BytesIO(parts['COMMON_MEMBERSHIP.parquet']),use_threads=False).to_pandas(use_threads=False);V=pq.read_table(io.BytesIO(parts['COMMON_SELECTIONS.parquet']),use_threads=False).to_pandas(use_threads=False)
 need(len(O)==3998 and not O.opportunity_key.duplicated().any() and not P.duplicated(['procedure_id','arm','opportunity_key']).any(),'primary/procedure uniqueness')
 def arrays_equal(a,b):return bool(np.allclose(np.asarray(a,float),np.asarray(b,float),rtol=1e-10,atol=1e-12,equal_nan=True))
 def direction(f):
  y=f.actual.to_numpy(float);part=f.participation_state.fillna('unknown').str.lower().to_numpy();e=np.full(len(f),np.nan)
  for i in np.flatnonzero((part=='played')&np.isfinite(y)):
   a,b=Decimal(str(y[i])),Decimal(str(f.iloc[i]['_line']));e[i]=1 if a>b else 0 if a<b else 2
  return e,part
 def masks(f,eligible):
  valid=np.asarray(eligible,bool);u=f.log_under.to_numpy(float);o=f.log_over.to_numpy(float);side=np.full(len(f),'unavailable',object);side[valid]='abstain';side[valid&(o>u)]='over';side[valid&(u>o)]='under';conf=np.exp(np.maximum(u,o));chosen=valid&np.isin(side,['over','under']);out={'FULL_BOARD':chosen,'ABSTAIN_0_55':chosen&(conf>=.55),'ALWAYS_OVER':valid,'ALWAYS_UNDER':valid}
  # Only keys and prediction confidences reach this ordering.
  rank=f[['target','week','game_id','player_id','opportunity_key']].copy();rank['confidence']=conf;rank['_row']=np.arange(len(f));rank=rank.loc[chosen].sort_values(['target','week','confidence','game_id','player_id','opportunity_key'],ascending=[True,True,False,True,True,True],kind='stable')
  for k in [6,10,20]:
   use=np.zeros(len(f),bool);use[rank.groupby(['target','week']).head(k)._row.to_numpy(int)]=True;out['TOP_'+str(k)]=use
  return side,out
 groups={k:g.copy() for k,g in P.groupby(['procedure_id','arm'],sort=False)};master=O.set_index('opportunity_key');probchecks=selectionchecks=0
 for key,g in groups.items():
  parent=master.loc[g.opportunity_key];need(arrays_equal(g.actual,parent.actual),'actual changed across candidates');need(g.participation_state.to_numpy().tolist()==parent.participation_state.to_numpy().tolist(),'participation changed');u,o=g.log_under.to_numpy(float),g.log_over.to_numpy(float);valid=g.prediction_eligible.to_numpy(bool);need(np.allclose(np.logaddexp(u[valid],o[valid]),0,atol=1e-10),'conditional logs incoherent')
  e,part=direction(g);known=np.isfinite(e);sc=valid&(part=='played')&known&(e!=2);b=np.full(len(g),np.nan);ll=b.copy();b[sc]=(np.exp(o[sc])-e[sc])**2;ll[sc]=-np.where(e[sc]==1,o[sc],u[sc]);need(arrays_equal(g.Brier,b) and arrays_equal(g.log_loss,ll),'binary scores differ/no infinity clipping')
  want=np.where(~valid,'NO_SUPPORTED_CONDITIONAL_PROBABILITY',np.where(part=='dnp','DNP',np.where(part!='played','UNKNOWN_PARTICIPATION',np.where(~known,'PLAYED_MISSING',np.where(e==2,'EXACT_LINE_PUSH','SCORED')))));need((want==g.score_state.to_numpy()).all(),'score-state mismatch');need(arrays_equal(g.event,e),'threshold direction mismatch');side,flags=masks(g,valid);need((side==g.side.to_numpy()).all(),'side mismatch')
  for p,v in flags.items():need(np.array_equal(v,g['select_'+p].to_numpy(bool)),'full prediction-only rank/abstention mismatch')
  probchecks+=len(g);selectionchecks+=len(g)*len(POL)
 # Recompute F/S conditioning from saved original law logs, not the score helper.
 rawchecks=0
 for spec in plan['law_inputs']:
  if spec['target'] not in set(O.target):continue
  with zipfile.ZipFile(io.BytesIO(rd.read_exact(spec['package']))) as z:f=pq.read_table(io.BytesIO(z.read('OFFER_PROBABILITY_SCORECARD.parquet')),use_threads=False).to_pandas(use_threads=False)
  f['_line']=f.line.map(lambda x:'0' if Decimal(str(x))==0 else format(Decimal(str(x)).normalize(),'f'));f['cutoff_utc']=pd.to_datetime(f.cutoff_utc,utc=True)
  join=['target','season','week','game_id','player_id','team','opponent','cutoff_utc','_line']
  for method in sorted(f.method.unique()):
   for src,arm in [('FOOTBALL','F_CONDITIONAL'),('SHRINK_0_5','S_CONDITIONAL')]:
    g=groups[(spec['cell_id']+'::'+method,arm)];j=g[join].merge(f.loc[f.method.eq(method)&f.arm.eq(src),join+['log_p_under','log_p_over']],on=join,how='left',validate='one_to_one');a,b=j.log_p_under.to_numpy(float),j.log_p_over.to_numpy(float);d=np.logaddexp(a,b);ok=np.isfinite(d)&~np.isnan(a)&~np.isnan(b);u=np.full(len(g),np.nan);o=u.copy();u[ok]=a[ok]-d[ok];o[ok]=b[ok]-d[ok];need(arrays_equal(g.log_under,u) and arrays_equal(g.log_over,o) and np.array_equal(g.prediction_eligible,ok),'original-law conditional normalization differs');rawchecks+=len(g)
 market=groups[('M_EXCLUDED_BOOK_Q_V1','M_EXCLUDED')].set_index('opportunity_key');same=groups[('M_OFFERING_BOOK_NONINDEPENDENT_Q_V1','M_SAMEBOOK')].set_index('opportunity_key')
 price=pq.read_table(io.BytesIO(rd.read_exact(plan['price_packet'])),use_threads=False).to_pandas(use_threads=False).set_index('opportunity_key')
 for source,g in [('market_q_over_given_decisive',market),('samebook_q_over_given_decisive',same)]:need(arrays_equal(np.exp(g.log_over),price.loc[g.index,source]),'source market q changed')
 for (procedure,arm),g in groups.items():
  if arm!='H_FIXED_HALF':continue
  F=groups[(procedure,'F_CONDITIONAL')].set_index('opportunity_key').loc[g.opportunity_key];q=market.loc[g.opportunity_key];u=np.logaddexp(F.log_under.to_numpy()-np.log(2),q.log_under.to_numpy()-np.log(2));o=np.logaddexp(F.log_over.to_numpy()-np.log(2),q.log_over.to_numpy()-np.log(2));need(arrays_equal(g.log_under,u) and arrays_equal(g.log_over,o),'fixed H formula differs')
 common_views={};commonchecks=0
 for (cid,arm),stored in V.groupby(['comparison_id','arm'],sort=False):
  source=groups[(cid,arm)] if arm not in ['M_EXCLUDED','M_SAMEBOOK'] else market.reset_index() if arm=='M_EXCLUDED' else same.reset_index();g=source.set_index('opportunity_key').loc[stored.opportunity_key].reset_index();membership=M.loc[M.comparison_id.eq(cid)].set_index('opportunity_key').loc[g.opportunity_key].common_prediction_eligible.to_numpy(bool);F=groups[(cid,'F_CONDITIONAL')].set_index('opportunity_key').loc[g.opportunity_key];mq=market.loc[g.opportunity_key];need(np.array_equal(membership,F.prediction_eligible.to_numpy(bool)&mq.prediction_eligible.to_numpy(bool)),'common pool used outcomes or wrong availability');valid=g.prediction_eligible.to_numpy(bool)&membership;side,flags=masks(g,valid);need(np.array_equal(stored.policy_eligible.to_numpy(bool),valid) and np.array_equal(stored.side.to_numpy(),side),'common side eligibility mismatch')
  for p,v in flags.items():need(np.array_equal(v,stored['select_'+p].to_numpy(bool)),'common ranks use post-outcome replacement')
  g['side']=side;g['policy_eligible']=valid
  for p,v in flags.items():g['select_'+p]=v
  common_views[cid,arm]=g;commonchecks+=len(g)
 def checkloss(values,claim):
  a=np.asarray(values,float);need(not np.isnan(a).any(),'undefined scores included');n=len(a);inf=int(np.isposinf(a).sum());need(claim['n']==n and claim['positive_infinite_rows']==inf,'loss denominator/infinity mismatch');want=None if inf or not n else float(a.mean());need(claim['value']==want if want is None else math.isclose(claim['value'],want,rel_tol=1e-10,abs_tol=1e-12),'loss mean differs')
 def checkprob(g,claim):
  s=g.loc[g.score_state.eq('SCORED')];need(claim['opportunities']==len(g) and claim['scored_decisive']==len(s),'probability sample mismatch');need(claim['states']==g.score_state.value_counts().to_dict(),'probability coverage states differ');checkloss(s.Brier,claim['Brier']);checkloss(s.log_loss,claim['log_loss'])
 def checkselection(g,p,claim):
  selected=g.loc[g['select_'+p]];side=np.full(len(selected),'over' if p=='ALWAYS_OVER' else 'under',object) if p.startswith('ALWAYS_') else selected.side.to_numpy();e=selected.event.to_numpy(float);part=selected.participation_state.to_numpy();r=np.where(part=='dnp','DNP',np.where(~np.isfinite(e),'UNRESOLVED',np.where(e==2,'PUSH',np.where((side=='over')==(e==1),'WIN','LOSS'))));need(claim['offered_pool']==len(g) and claim['selected']==len(selected),'selection pool mismatch')
  for s in ['over','under']:
   z=r[side==s];w=int((z=='WIN').sum());l=int((z=='LOSS').sum());c=claim[s];need(c['wins']==w and c['losses']==l and c['decided']==w+l,'own-side counts differ');need(c['hit_rate'] is None if not w+l else math.isclose(c['hit_rate'],w/(w+l),rel_tol=1e-12),'own-side hit rate is not wins/decided')
  need(claim['counts']=={str(k):int(v) for k,v in zip(*np.unique(r,return_counts=True))},'selected unresolved/push/DNP counts changed');checkprob(selected,claim['selected_probability_scores'])
 aggregatechecks=0
 for item in report['fullboard_method_summaries']:
  cid,arm,target=item['comparison_id'],item['arm'],item['target'];g=common_views[cid,arm] if item['scope']=='COMMON_F_M_H_PREDICTION_POOL' else groups[(cid,arm)] if arm not in ['M_EXCLUDED','M_SAMEBOOK'] else market.reset_index() if arm=='M_EXCLUDED' else same.reset_index();g=g.loc[g.target.eq(target)];checkprob(g.loc[g.policy_eligible] if item['scope'].startswith('COMMON') else g,item['probability'])
  for p in item['policies']:checkselection(g,p['policy'],p['metrics']);aggregatechecks+=1
  for w in item['weekly']:
   h=g.loc[g.week.eq(w['week'])];checkprob(h.loc[h.policy_eligible] if item['scope'].startswith('COMMON') else h,w['probability'])
   for p in w['policies']:checkselection(h,p['policy'],p['metrics']);aggregatechecks+=1
 line=O.loc[O.participation_state.eq('played')&O.actual.notna()].copy();need(report['line_as_point']['supported_outcomes']==len(line),'line heuristic denominator mismatch')
 for claim in report['line_as_point']['results']:
  g=line.loc[line.target.eq(claim['target'])];err=g._line.astype(float)-g.actual;ae=err.abs();want={'MAE':float(ae.mean()),'MSE':float((err**2).mean()),'RMSE':float(np.sqrt((err**2).mean())),'bias':float(err.mean()),'p90_absolute_error':float(ae.quantile(.9)),'p95_absolute_error':float(ae.quantile(.95))};need(claim['n']==len(g) and all(math.isclose(claim[k],v,rel_tol=1e-10,abs_tol=1e-12) for k,v in want.items()),'line heuristic error/tail projection differs')
 elapsed={'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};need(elapsed['CPU_seconds']<=80 and elapsed['wall_seconds']<=180,'QA runtime exceeded')
 return {'state':'PASS_INDEPENDENT_CACHED_CONDITIONAL_MARKET_QA','source_package_sha256':cfg['package']['sha256'],'probability_rows':probchecks,'original_law_conditional_rows':rawchecks,'selection_flags_checked':selectionchecks,'common_prediction_rows_checked':commonchecks,'cumulative_weekly_policy_records_checked':aggregatechecks,'fits_model_restorations_law_inference_HTTP':0,'bootstrap_intervals':'Existing score-source bootstrap not independently rerun; QA checks core scores/denominators/selection masks','actual':elapsed,'owned_reference_batches':audits}
