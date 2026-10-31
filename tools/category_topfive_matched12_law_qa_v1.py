"""Independent cached-law QA; no shared scoring code or fitting. Exact root GO first."""
import gzip,hashlib,importlib.util,io,json,math,os,resource,signal,sys,time,zipfile
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-independent-law-QA-v1'
KEY=['target','season','week','game_id','player_id','team','opponent','cutoff_utc']
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def read(r):
 p=Path(r['path']);a=p.stat();assert p.resolve()==p and not any(q.is_symlink() for q in [p,*p.parents]) and a.st_size==r['bytes'];b=p.read_bytes();z=p.stat();assert sha(b)==r['sha256'] and os.path.samestat(a,z) and (a.st_mtime_ns,a.st_ctime_ns)==(z.st_mtime_ns,z.st_ctime_ns);return b
def install(name,r):
 read(r);s=importlib.util.spec_from_file_location(name,r['path']);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def independent_crps(batch,y):
 """E|X-y|-.5E|X-X'|; explicit empirical pairs and closed-form prior moments."""
 import numpy as np
 s=np.asarray(batch.support,float);c=np.cumsum(batch.weights,axis=1);w=np.diff(c/c[:,-1:],axis=1,prepend=0.);prior=batch.prior;q=prior.q
 def absolute(t):
  t=np.asarray(t,float)
  if prior.support=='count':return np.where(t<0,q/(1-q)-t,t-q/(1-q)+2*q**(t+1)/(1-q))
  assert prior.support=='signed_integer';d=np.abs(t-prior.center);return d+2*q**(d+1)/(1-q*q)
 pp=2*q/(1-q*q) if prior.support=='count' else 4*q*(1+q+q*q)/((1-q)*(1+q)**3)
 a,b=batch.a,batch.b
 return a*np.sum(w*np.abs(s[None,:]-np.asarray(y)[:,None]),axis=1)+b*absolute(y)-.5*a*a*np.einsum('ij,jk,ik->i',w,np.abs(s[:,None]-s[None,:]),w)-a*b*(w@absolute(s))-.5*b*b*pp
def software_checks():
 import numpy as np
 from types import SimpleNamespace as N
 def law(s):return N(support=np.array([0.]),weights=np.ones((1,1)),prior=N(q=.5,support=s,center=0),a=0.,b=1.)
 assert np.allclose(independent_crps(law('count'),[0]),[1/3],rtol=0,atol=1e-14)
 assert np.allclose(independent_crps(law('signed_integer'),[0]),[8/27],rtol=0,atol=1e-14)
 return {'state':'PASS_FICTIONAL_ONLY','cases':2,'NFL_sources_models_outcomes':0}
def execute(cfg,go):
 assert go['state']=='ROOT_GO_INDEPENDENT_LAW_QA' and go['registered_by']=='/root' and go['worker_sha256']==sha(Path(__file__).read_bytes()) and go['config_sha256']==sha(enc(cfg))
 start=time.monotonic();cpu=time.process_time();caps=cfg['resources'];resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(caps['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('law QA wall cap')));signal.alarm(caps['wall_seconds'])
 sys.addaudithook(lambda e,a:(_ for _ in ()).throw(RuntimeError('offline QA')) if e in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None);sys.path.insert(0,str(ROOT))
 import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq,joblib
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 plan=json.loads(gzip.decompress(read(cfg['law_plan'])))
 for r in plan['source_pins'].values():read(r)
 from tools import category_topfive_matched12_storage_v1 as storage
 from nfl_lab.owned_reference_batch import validate_owned_references
 from nfl_lab import cdf_engine
 store,_=storage.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=storage.GO,readonly=True)
 refs=[cfg['aggregates']]
 chosen=[s for s in plan['specs'] if s['cell_id'] in cfg['direct_model_cells']];assert len(chosen)==len(cfg['direct_model_cells'])<=4
 for s in chosen:refs += [s['artifact'],s['features']]
 unique={r['path']:r for r in refs};seen=set();audits=[]
 def authenticate():
  seen.clear();result=[]
  for owner in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]:
   items={r['path']:r['sha256'] for r in unique.values() if any(Path(r['path']).is_relative_to(Path(p)) for p in owner._roots)}
   assert not seen.intersection(items)
   if items:
    got,a=validate_owned_references(owner,items);assert all(got[p]['bytes']==unique[p]['bytes'] for p in got);seen.update(got);result.append({'references':len(got),'full_scans':a['full_scan_calls']})
  assert seen==set(unique);return result
 audits.append(authenticate());report=json.loads(gzip.decompress(read(cfg['aggregates'])));assert len(report['cells'])==24
 run=Path(plan['specs'][0]['features']['path']).parent.parent/plan['run_id'];packages=[{'cell_id':c['cell_id'],'artifact':{'path':str(run/c['cell_id']/'SCORE_PACKAGE.zip'),**c['artifact']}} for c in report['cells']]
 assert {c['cell_id'] for c in packages}=={s['cell_id'] for s in plan['specs']}
 unique.update({c['artifact']['path']:c['artifact'] for c in packages});audits.append(authenticate())
 numeric=[];events=[];cache={};checked=0;cells={s['cell_id']:s for s in plan['specs']}
 for c in packages:
  cid=c['cell_id'];spec=cells[cid];r=next(x for x in report['cells'] if x['cell_id']==cid);assert r['state']=='SCORED_FROZEN_LAW' and all(r['artifact'][k]==c['artifact'][k] for k in ['bytes','sha256'])
  with zipfile.ZipFile(io.BytesIO(read(c['artifact']))) as z:
   assert len(z.namelist())==len(set(z.namelist()));m=json.loads(z.read('MANIFEST.json'));assert m['spec']==spec and m['law_helper_sha256']==plan['source_pins']['loss']['sha256']
   n=pq.read_table(io.BytesIO(z.read('DISTRIBUTION_SCORECARD.parquet')),use_threads=False).to_pandas(use_threads=False);cache[cid]=n
   assert not any(str(k).startswith('f_') for k in n) and set(n.method)==set(spec['methods']) and n.target.eq(spec['target']).all()
   assert not n.duplicated(KEY+['method']).any() and n.primary_role.eq(n.position.isin(spec['primary_roles'])).all()
   for method,v in n.groupby('method'):assert len(v)==spec['expected_query_rows']
   good=n.score_state.eq('SCORED');assert n.loc[good,'participation_state'].eq('played').all() and np.isfinite(n.loc[good,'actual']).all()
   lattice=n.loc[good,'actual'].to_numpy(float)*spec['scale'];assert np.all(np.abs(lattice-np.rint(lattice))<=1e-8)
   assert not n.loc[good,['CRPS','negative_log_pmf']].isna().any().any() and (n.loc[good,'CRPS']>=-1e-9).all() and (n.loc[good,'negative_log_pmf']>=-1e-10).all()
   numeric.append(n)
   if 'OFFER_PROBABILITY_SCORECARD.parquet' not in z.namelist():continue
   f=pq.read_table(io.BytesIO(z.read('OFFER_PROBABILITY_SCORECARD.parquet')),use_threads=False).to_pandas(use_threads=False);assert not f.duplicated(KEY+['method','arm','offer_id']).any()
   p=f[['p_under','p_push','p_over']].to_numpy(float);logs=f[['log_p_under','log_p_push','log_p_over']].to_numpy(float);valid=np.isfinite(p).all(1);assert np.array_equal(valid,~np.isnan(logs).any(1)) and np.isnan(p[~valid]).all()
   assert np.all(p[valid]>=0) and np.all(p[valid]<=1+1e-10) and np.allclose(p[valid].sum(1),1,atol=1e-10,rtol=0) and np.allclose(np.exp(logs[valid]),p[valid],rtol=1e-12,atol=1e-14)
   at=np.flatnonzero(f.score_state.eq('SCORED'));y=[]
   for i in at:
    value=D(str(f.iloc[i].actual))*spec['scale'];nearest=value.to_integral_value();assert abs(value-nearest)<=D('0.00000001');L=D(str(f.iloc[i].line))*spec['scale'];y.append(0 if nearest<L else 2 if nearest>L else 1)
   y=np.asarray(y,int);assert np.array_equal(f.iloc[at].event_index.to_numpy(),y)
   assert np.allclose(f.iloc[at].Brier,.5*np.sum((p[at]-np.eye(3)[y])**2,axis=1),rtol=1e-12,atol=1e-14)
   assert np.allclose(f.iloc[at].log_loss,-logs[at,y],rtol=1e-12,atol=1e-12,equal_nan=False)
   u,o=logs[:,0],logs[:,2];d=np.logaddexp(u,o);conf=np.full(len(f),np.nan);alive=np.isfinite(d);conf[alive]=np.exp(np.maximum(u[alive],o[alive])-d[alive]);side=np.full(len(f),'unavailable',object);side[valid]='abstain';side[alive&(o>u)]='over';side[alive&(u>o)]='under'
   side55=side.copy();side55[alive&(conf<.55)]='abstain';assert np.array_equal(f.side,side) and np.array_equal(f.side55,side55) and np.allclose(f.confidence,conf,equal_nan=True,rtol=1e-12,atol=1e-14)
   for sf,rf in [('side','result'),('side55','result55')]:
    expected=[]
    for row in f.to_dict('records'):
     s=row[sf];state=row['participation_state'];v=row['actual'];L=D(str(row['line']));v=D(str(v)) if math.isfinite(v) else None
     expected.append('ABSTAIN' if s=='abstain' else 'UNRESOLVED' if s=='unavailable' else 'DNP' if state in ['DNP','dnp'] else 'UNRESOLVED' if state!='played' or v is None else 'PUSH' if v==L else 'WIN' if (v>L if s=='over' else v<L) else 'LOSS')
    assert np.array_equal(f[rf],expected)
   events.append(f);checked+=len(f)
 num=pd.concat(numeric,ignore_index=True);event=pd.concat(events,ignore_index=True)
 def loss(x,r):
  x=np.asarray(x,float);assert not np.isnan(x).any();inf=int(np.isposinf(x).sum());state='UNAVAILABLE' if not len(x) else 'POSITIVE_INFINITY' if inf else 'FINITE';assert r['n']==len(x) and r['state']==state and r['positive_infinite_rows']==inf
  assert r['value'] is None if state!='FINITE' else math.isclose(float(x.mean()),r['value'],rel_tol=1e-12,abs_tol=1e-10)
 for r in report['distribution_scores']:
  f=num.loc[num.target.eq(r['target'])&num.method.eq(r['method'])]
  for name,v in [('primary_roles',f.loc[f.primary_role]),('all_attempts_secondary',f)]:
   s=v.loc[v.score_state.eq('SCORED')];a=r[name];assert a['planned']==len(v) and a['scored']==len(s) and a['states']==v.score_state.value_counts().to_dict();loss(s.CRPS,a['CRPS']);loss(s.negative_log_pmf,a['negative_log_pmf'])
 for r in report['probability_scores']:
  f=event.loc[event.target.eq(r['target'])&event.method.eq(r['method'])&event.arm.eq(r['arm'])];s=f.loc[f.score_state.eq('SCORED')];a=r['metrics'];assert a['planned']==len(f) and a['scored']==len(s);loss(s.Brier,a['Brier']);loss(s.log_loss,a['log_loss'])
 for r in report['selection_policies']:
  f=event.loc[event.target.eq(r['target'])&event.method.eq(r['method'])&event.arm.eq(r['arm'])].copy();policy=r['policy']
  if policy=='ABSTAIN_CONFIDENCE_0_55':f['side']=f.side55;f['result']=f.result55
  elif policy.startswith('TOP_'):k=int(policy.split('_')[1]);f=f.loc[f.side.isin(['over','under'])].sort_values(['week','confidence','game_id','player_id'],ascending=[True,False,True,True],kind='stable').groupby('week').head(k)
  elif policy.startswith('ALWAYS_'):
   f['side']=policy[7:].lower();f['result']=np.where(f.participation_state.isin(['DNP','dnp']),'DNP',np.where(f.event_index.isna(),'UNRESOLVED',np.where(f.event_index.eq(1),'PUSH',np.where(f.event_index.eq(2 if policy=='ALWAYS_OVER' else 0),'WIN','LOSS'))))
  else:assert policy=='FULL_BOARD'
  a=r['metrics'];assert a['opportunities']==len(f)
  decided=f.loc[f.result.isin(['WIN','LOSS'])]
  for c in ['game_id','week']:assert a['hit_rate_intervals'][c]['clusters']==decided[c].nunique()
  for side in ['over','under']:
   v=f.loc[f.side.eq(side)];c=v.result.value_counts();w=int(c.get('WIN',0));l=int(c.get('LOSS',0));b=a[side];assert (b['wins'],b['losses'],b['decided'])==(w,l,w+l) and b['hit_rate']==(w/(w+l) if w+l else None)
   for k,j in [('push','PUSH'),('DNP','DNP'),('unresolved','UNRESOLVED')]:assert b[k]==int(c.get(j,0))
 direct=[];rows=0
 if chosen:
  install('nfl_lab.threshold_cdf',plan['source_pins']['threshold']);install('nfl_lab.distribution_split_cdf',plan['source_pins']['response'])
 for spec in chosen:
  blob=read(spec['artifact'])
  if spec['kind']=='future':model=joblib.load(io.BytesIO(blob))['model']
  else:
   assert spec['kind']=='fixed_cell'
   with zipfile.ZipFile(io.BytesIO(blob)) as z:b=z.read(spec['member'])
   assert sha(b)==spec['inner_sha256'];model=joblib.load(io.BytesIO(b))
  q=pq.read_table(io.BytesIO(read(spec['features'])),use_threads=False).to_pandas(use_threads=False);q=q.loc[q.position.isin(spec['primary_roles'])].sort_values(['season','week','game_id','player_id'],kind='stable').head(4).copy().reset_index(drop=True);rows+=len(q);assert rows<=16
  cached=cache[spec['cell_id']];cached=cached.loc[cached.method.eq(spec['methods'][0])];expected=q[['season','week','game_id','player_id']].merge(cached,on=['season','week','game_id','player_id'],validate='one_to_one');n=0
  for ix,batch,why in model.predict_batches(q,batch_size=4):
   if batch is None:continue
   good=expected.iloc[ix].score_state.eq('SCORED').to_numpy();at=np.flatnonzero(good)
   if not len(at):continue
   import copy
   b=copy.copy(batch);b.weights=batch.weights[at];y=expected.iloc[ix[at]].actual.to_numpy(float)*spec['scale'];y=np.rint(y);v=independent_crps(b,y)/spec['scale'];assert np.allclose(v,expected.iloc[ix[at]].CRPS,rtol=1e-9,atol=1e-8);n+=len(at)
  direct.append({'cell_id':spec['cell_id'],'query_rows':len(q),'supported_CRPS_rows':n,'policy':'FIRST4_CANONICAL_PRIMARY_ROLE_QUERIES_OUTCOME_BLIND; no replacement when outcomes missing'})
 audits.append(authenticate());rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024;assert rss<=caps['RSS_bytes'];signal.alarm(0)
 return {'version':VERSION,'state':'PASS_INDEPENDENT_CACHED_LAW_QA','cells':len(packages),'distribution_rows':len(num),'event_rows_checked':checked,'selection_policy_records':len(report['selection_policies']),'direct_CRPS_samples':direct,'new_model_restorations':len(chosen),'new_query_rows':rows,'scope':'All cached proper-score/event/selection arithmetic checked; CRPS full vectors reaggregated, only16outcome-blind queries independently re-inferred. Not full independent law reproduction.','owned_reference_batches':audits,'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':rss},'fits_HTTP_new_source_acquisition_production':0}
