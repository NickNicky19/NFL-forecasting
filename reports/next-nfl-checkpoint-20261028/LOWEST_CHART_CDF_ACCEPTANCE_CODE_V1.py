"""Independent retained-law arithmetic acceptance. No fit/apply/predict/source acquisition."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,base64,csv,gzip,hashlib,importlib,importlib.metadata,io,json,math,os,pickle,resource,signal,sys,threading,time
VERSION='lowest-chart-cdf-independent-acceptance-v1'
ROOT=Path('/workspace/nfl-methods-integration/reports/next-nfl-checkpoint-20261028')
NAMES=['LEAF_CDF_CHART_MEDIAN_V1','LEAF_CDF_CHART_MEAN_V1','ROLE_LAW_CHART_MEDIAN_V1','ROLE_LAW_CHART_MEAN_V1','HGB_CHART_MEDIAN_V1','POSITION_CHART_MEDIAN_2024','GLOBAL_CHART_MEDIAN_2024','POSITION_CHART_MEAN_2024']
IDENTITY=['season','week','game_id','team','opponent','player_id','season_type']
CAPS={'CPU_seconds':45,'wall_seconds':60,'RSS_bytes':805306368,'model_loads':1,'fits':0,'forest_apply_predict_calls':0,'HTTP':0,'CAS_writes':0,'invocations':1,'maximum_input_bytes':4194304,'maximum_uncompressed_gzip_bytes_each':16777216,'maximum_empirical_support':5589,'maximum_lattice_grid_width':65536,'bootstrap_replicates':500,'seed':1703,'output_metadata_bytes':32768}
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def require(x,msg):
 if not x:raise ValueError(msg)
def auth(ref):
 p=Path(ref['path']);require(p.is_absolute()and p.resolve()==p and not p.is_symlink(),'canonical authenticated reference required');a=p.stat();b=p.read_bytes();z=p.stat()
 require((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns)and len(b)==ref['bytes']and sha(b)==ref['sha256'],'authenticated input changed');return b
def main():
 start=time.monotonic();cpu=time.process_time();p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--go',required=True);a=p.parse_args();raw=Path(a.plan).read_bytes();require(sha(raw)==a.sha256,'exact plan hash required');plan=json.loads(raw);go=json.loads(Path(a.go).read_bytes())
 require(plan['version']==VERSION and plan['resources']==CAPS and plan['state']=='ROOT_AND_REVIEWER_SEALED'and plan['review']=='PREEXEC_PASS'and plan['execution_authorized']is True and plan['root_registration']=={'registered_by':'/root','previous_managed_writer_closed':True},'separate root/reviewer sealed registration required')
 require(go=={'state':'GO','root':'/root','independent_review':'PASS','scope':'CHART_CDF_INDEPENDENT_READONLY_ACCEPTANCE','plan_sha256':a.sha256,'previous_managed_writer_closed':True},'exact root GO required')
 require(auth(plan['worker'])==Path(__file__).read_bytes(),'worker binding changed');require(sys.flags.dont_write_bytecode,'invoke -B')
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS']:os.environ[k]='1'
 os.environ['PYTHONDONTWRITEBYTECODE']='1'
 def deny(event,args):
  if event.startswith('socket.')or event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn'}:raise ValueError('offline child-free independent review required')
 sys.addaudithook(deny)
 progress={'model_loads':0,'forest_apply_predict_calls':0,'new_fits':0,'new_query_inference':0,'retained_law_rows':0,'scalar_checks':0};maxdiff=defaultdict(float)
 def usage():return{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
 def check():
  u=usage();require(u['CPU_seconds']<=45 and u['wall_seconds']<=60 and u['peak_RSS_bytes']<=CAPS['RSS_bytes'],'finite independent acceptance budget exceeded')
 consumed=ROOT/'LOWEST_CHART_CDF_ACCEPTANCE_CONSUMED_V1.json';result=ROOT/'LOWEST_CHART_CDF_ACCEPTANCE_RESULT_V1.json';failed=ROOT/'LOWEST_CHART_CDF_ACCEPTANCE_FAILED_V1.json';require(not any(p.exists()for p in [consumed,result,failed]),'one new independent invocation only; prior failures remain consumed')
 written=0
 def write(path,x):
  nonlocal written
  b=encoded(x);require(written+len(b)<=CAPS['output_metadata_bytes'],'review metadata cap');written+=len(b)
  with path.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 write(consumed,{'state':'INDEPENDENT_ACCEPTANCE_INVOCATION_CONSUMED_BEFORE_DATA_DECODE','plan_sha256':a.sha256,'maximum_model_loads':1,'new_fits':0,'new_query_inference':0,'automatic_retries':0})
 class Stop(BaseException):pass
 def stop(signum,frame):raise Stop('finite independent review interrupted; consumed attempt remains')
 resource.setrlimit(resource.RLIMIT_CPU,(45,46));signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGXCPU,stop);signal.signal(signal.SIGUSR1,stop);signal.setitimer(signal.ITIMER_REAL,max(.001,59-(time.monotonic()-start)));done=threading.Event()
 def watch():
  while not done.wait(.1):
   if usage()['peak_RSS_bytes']>CAPS['RSS_bytes']:os.kill(os.getpid(),signal.SIGUSR1);return
 threading.Thread(target=watch,daemon=True).start()
 try:
  bodies={k:auth(v)for k,v in plan['inputs'].items()};require(sum(map(len,bodies.values()))<=CAPS['maximum_input_bytes'],'bounded input bytes');require(all(importlib.metadata.version(k)==v for k,v in plan['environment'].items()),'declared environment changed')
  import numpy as np
  for ref in plan['model_class_sources'].values():auth(ref)
  sys.path.insert(0,plan['model_package_root']);engine=importlib.import_module('nfl_lab.cdf_engine');require(Path(engine.__file__).resolve()==Path(plan['model_class_sources']['cdf_engine']['path']),'exact trusted class origin required')
  def decode(name):
   if name in ['safe_aggregate','native_complete']:return json.loads(bodies[name])
   with gzip.GzipFile(fileobj=io.BytesIO(bodies[name]))as stream:b=stream.read(CAPS['maximum_uncompressed_gzip_bytes_each']+1)
   require(len(b)<=CAPS['maximum_uncompressed_gzip_bytes_each'],'bounded gzip expansion');return json.loads(b)
  freeze=decode('forecast');grade=decode('grade');summary=decode('safe_aggregate');native=decode('native_complete');oldfreeze=decode('original_HGB_forecast');oldgrade=decode('original_HGB_grade')
  require(freeze['version']=='next-checkpoint-chart-cdf-control-v1'and freeze['target']==grade['target']=='nick-chart-ppr-v1'and freeze['score_lattice_scale']==50,'exact new chart contract')
  require(grade['freeze_sha256']==sha(bodies['forecast'])and summary['freeze_capsule_sha256']==sha(bodies['forecast'])and summary['score_capsule_sha256']==sha(bodies['grade'])and native['capsule']['sha256']==sha(bodies['grade']),'freeze grade summary native bindings differ')
  require(freeze['plan_sha256']==grade['plan_sha256']==summary['plan_sha256']==native['plan_sha256']==plan['completed_study_plan_sha256'],'completed study identity differs')
  require(freeze['old_HGB_forecasts_sha256']==summary['old_HGB_forecasts_sha256']==sha(bodies['original_HGB_forecast'])and oldgrade['freeze_sha256']==sha(bodies['original_HGB_forecast']),'original HGB binding differs')
  modelbytes=base64.b64decode(freeze['fitted_model_pickle_base64'],validate=True);require(sha(modelbytes)==freeze['fitted_model_sha256']==summary['fitted_model_sha256']==plan['trusted_fitted_model_sha256'],'trusted fitted model differs')
  progress['model_loads']+=1;model=pickle.loads(modelbytes);require(type(model)is engine.LeafCDFModel and model.category['target']=='chart_lattice_002_v1'and len(model.forest.estimators_)==32,'trusted retained model schema differs')
  def forbidden(*args,**kwargs):progress['forest_apply_predict_calls']+=1;raise ValueError('new forest/model query forbidden')
  model.predict_batches=forbidden;model.forest.apply=model.forest.predict=forbidden
  for tree in model.forest.estimators_:tree.apply=tree.predict=forbidden
  # No model or engine distribution method is called below. Only retained fields.
  forecasts=freeze['forecasts'];rows=grade['rows'];require(len(forecasts)==len(rows)==2117,'complete2117 query required')
  def ident(r):return tuple(r['identity'][k]for k in IDENTITY)
  frozen={ident(r):r for r in forecasts};graded={ident(r):r for r in rows};old={ident(r):r for r in oldfreeze['forecasts']};oldg={ident(r):r for r in oldgrade['rows']};require(len(frozen)==len(graded)==len(old)==len(oldg)==2117 and set(frozen)==set(graded)==set(old)==set(oldg),'full distinct identities differ')
  require(len(freeze['prior_training_binding'])==5589 and all(r['season']==2024 for r in freeze['prior_training_binding']),'full prior training binding missing')
  def near(label,x,y,atol=1e-10,rtol=1e-12):
   progress['scalar_checks']+=1
   if x is None or y is None:require(x is y,label+' null differs');return
   if isinstance(x,str)or isinstance(y,str):require(x==y,label+' status differs');return
   dx=float(x);dy=float(y)
   if math.isinf(dx)or math.isinf(dy):require(dx==dy,label+' infinity differs');return
   require(math.isfinite(dx)and math.isfinite(dy),label+' invalid nonfinite');delta=abs(dx-dy);maxdiff[label.split('/')[0]]=max(maxdiff[label.split('/')[0]],delta);require(delta<=atol+rtol*max(abs(dx),abs(dy)),label+' numerical difference')
  def compare(label,x,y):
   if isinstance(x,dict):
    require(set(x)==set(y),label+' fields differ')
    for k in x:compare(label+'/'+k,x[k],y[k])
   elif isinstance(x,list):
    require(len(x)==len(y),label+' length differs')
    for i,(a,b)in enumerate(zip(x,y)):compare(label+'/'+str(i),a,b)
   elif isinstance(x,(float,int))and not isinstance(x,bool):near(label,x,y)
   else:require(x==y,label+' value differs')
  support=np.asarray(model.support,float);require(0<len(support)<=5589 and np.isfinite(support).all()and np.equal(support,np.rint(support)).all()and(np.diff(support)>0).all(),'signed integer support differs')
  leafmeta=freeze['query_leaf_ids'];require(leafmeta['dtype']=='int32'and leafmeta['shape']==[2117,32],'frozen leaf assignments differ');leaf=np.frombuffer(base64.b64decode(leafmeta['bytes_base64'],validate=True),dtype=np.int32).reshape(2117,32)
  weights=np.zeros((2117,len(support)))
  require(len(model.leaf_histograms)==32,'32 retained histograms needed')
  for j,hist in enumerate(model.leaf_histograms):
   require(hist.shape[1]==len(support)and leaf[:,j].min()>=0 and leaf[:,j].max()<hist.shape[0],'retained leaf shape/bounds differ');weights+=hist[leaf[:,j]].toarray()/32.
  require(np.isfinite(weights).all()and(weights>=0).all()and np.max(np.abs(weights.sum(axis=1)-1))<2e-12,'empirical histograms fail mass checks')
  prior_counts=sum(p.n for p in model.priors.values());require(prior_counts==model.global_prior.n==5589,'full prior role/global training counts differ')
  def prior_cdf(k,c,q):
   a=np.asarray(k,dtype=np.int64);out=np.empty(a.shape,float);left=a<c;out[left]=q**(c-a[left])/(1+q);out[~left]=1-q**(a[~left]-c+1)/(1+q);return out
  def make_cdf(w,c,q,b):
   cumulative=np.cumsum(w)
   def F(k):
    a=np.asarray(k,dtype=np.int64);ix=np.searchsorted(support,a,side='right')-1;emp=np.where(ix>=0,cumulative[np.maximum(ix,0)],0.);return(1-b)*emp+b*prior_cdf(a,c,q)
   return F
  def quantile(F,p,c):
   lo=min(int(support[0])-1,c-1,-1);hi=max(int(support[-1]),c,1)
   for _ in range(64):
    if float(F(lo))<p:break
    lo=2*lo-1
   else:raise ValueError('lower quantile bracket budget')
   for _ in range(64):
    if float(F(hi))>=p:break
    hi=2*hi+1
   else:raise ValueError('upper quantile bracket budget')
   while hi-lo>1:
    mid=(hi+lo)//2
    if float(F(mid))>=p:hi=mid
    else:lo=mid
   return hi
  def law_scores(w,c,q,b,y,F):
   # Exact discrete CDF identity plus both infinite geometric tails, no truncation.
   L=min(int(support[0]),c,y);H=max(int(support[-1]),c,y);require(H-L<=CAPS['maximum_lattice_grid_width'],'independent CDF-sum grid budget')
   grid=np.arange(L,H,dtype=np.int64);cdf=F(grid);finite=np.sum(np.where(grid<y,cdf*cdf,(1-cdf)*(1-cdf)))
   left=b*b*q**(2*(c-L+1))/((1+q)**2*(1-q*q));right=b*b*q**(2*(H-c+1))/((1+q)**2*(1-q*q));crps=(finite+left+right)/50
   empirical=float(w[support==y].sum());logprior=math.log1p(-q)-math.log1p(q)+abs(y-c)*math.log(q)
   l1=math.log1p(-b)+math.log(empirical)if b<1 and empirical>0 else-math.inf;l2=math.log(b)+logprior if b>0 else-math.inf;nll=-float(np.logaddexp(l1,l2));return float(crps),nll
  expected_scores={};scored=[];fallback_count=Counter();states=Counter();numeric=0
  for i,f in enumerate(forecasts):
   check();g=graded[ident(f)];h=old[ident(f)];hg=oldg[ident(f)];require(f['identity']['season']==2026 and 1<=f['identity']['week']<=6,'outside exposed evaluation scope')
   require(set(f['predictions'])==set(g['predictions'])==set(NAMES),'all8 products required');require(np.array_equal(np.asarray([f['predictions'][m]for m in NAMES],dtype='<f8').view('<u8'),np.asarray([g['predictions'][m]for m in NAMES],dtype='<f8').view('<u8')),'all frozen point bits must remain exact');compare('freeze_grade_predictions',f['predictions'],g['predictions']);compare('original_HGB_points',{k:f['predictions'][k]for k in h['predictions']},h['predictions'])
   for key in ['position','fallback','cutoff_utc','kickoff_utc','source_feature_max_utc']:require(f[key]==g[key]==h[key],'unchanged context/fallback differs')
   require(g['actual']==hg['actual']and g['outcome_state']==hg['outcome_state'],'original HGB actual/state differs');states[g['outcome_state']]+=1
   if f['fallback']:fallback_count[f['fallback']]+=1
   role=f['position'];prior=model.priors.get(role,model.global_prior);c,q=int(prior.center),float(prior.q);require(prior.support=='signed_integer'and 0<q<1,'signed geometric prior contract');w=weights[i]
   allscores={}
   for lawname,b in [('LEAF_CDF',1. if f['fallback']else.05),('ROLE_PRIOR',1.)]:
    F=make_cdf(w,c,q,b);med=quantile(F,.5,c)/50;mean=((1-b)*float(w@support)+b*c)/50;lower=quantile(F,.1,c)/50;upper=quantile(F,.9,c)/50
    pm=NAMES[0]if lawname=='LEAF_CDF'else NAMES[2];em=NAMES[1]if lawname=='LEAF_CDF'else NAMES[3]
    near('law_median',med,f['predictions'][pm]);near('law_mean',mean,f['predictions'][em]);near('law_p10',lower,f['distribution_intervals'][lawname]['p10']);near('law_p90',upper,f['distribution_intervals'][lawname]['p90'])
    require(f['distribution_intervals'][lawname]==g['distribution_intervals'][lawname],'frozen intervals changed')
    if g['actual']is not None:
     y=float(g['actual'])*50;require(math.isfinite(y)and abs(y-round(y))<1e-8,'chart actual lattice differs');v,nll=law_scores(w,c,q,b,int(round(y)),F);ref=g['distribution_scores'][lawname];near('independent_CRPS',v,ref['CRPS'],atol=2e-9);near('independent_logmass',nll,math.inf if ref['negative_log_mass']=='POSITIVE_INFINITY'else ref['negative_log_mass']);allscores[lawname]=(v,nll)
   expected_scores[ident(f)]=allscores;progress['retained_law_rows']+=1
   if g['actual']is not None:
    require(g['outcome_state']in ['played_score','played_zero'],'numeric outcome without participation');scored.append(g);numeric+=1
    for m in NAMES:near('signed_error',f['predictions'][m]-g['actual'],g['errors'][m])
   else:require(g['outcome_state']=='unknown_participation'and all(v is None for v in g['errors'].values()),'unknown outcome zero/error fabrication')
  require(numeric==1954 and states==Counter(played_score=1686,played_zero=268,unknown_participation=163),'exact1954 supported/163unknown population differs');require(len({r['identity']['game_id']for r in rows})==len({r['identity']['game_id']for r in scored})==93 and{r['identity']['week']for r in rows}==set(range(1,7)),'actual game/week coverage differs');require(dict(fallback_count)==freeze['fallbacks']==summary['query_coverage']['fallbacks'],'wholepopulation fallback counts differ')
  def metric(part,m):
   yy=np.array([r['actual']for r in part]);pp=np.array([r['predictions'][m]for r in part]);e=pp-yy;aa=np.abs(e)
   return{'n':len(e),'MAE':float(aa.mean()),'MSE':float(np.mean(e*e)),'RMSE':float(np.sqrt(np.mean(e*e))),'bias':float(e.mean()),'p90_absolute_error':float(np.quantile(aa,.9,method='linear')),'p95_absolute_error':float(np.quantile(aa,.95,method='linear')),'max_absolute_error':float(aa.max()),'error_strict_lt1':float(np.mean(aa<1)),'error_inclusive_le1':float(np.mean(aa<=1)),'error_strict_lt5':float(np.mean(aa<5)),'error_inclusive_le5':float(np.mean(aa<=5))}
  def allmetrics(part):return{m:metric(part,m)for m in NAMES}
  mm=allmetrics(scored);compare('all_point_metrics',mm,grade['metrics']);compare('safe_point_metrics',mm,summary['metrics'])
  for week in range(1,7):
   part=[r for r in rows if r['identity']['week']==week];good=[r for r in part if r['actual']is not None];want={'planned':len(part),'scored':len(good),'outcome_states':dict(Counter(r['outcome_state']for r in part)),'metrics':allmetrics(good)};compare('weekly',want,grade['weekly'][str(week)]);compare('safe_weekly',want,summary['weekly'][str(week)])
  for role in summary['role_metrics']:
   part=[r for r in scored if r['position']==role];compare('role_metrics',allmetrics(part),summary['role_metrics'][role]);compare('native_role_metrics',allmetrics(part),grade['role_metrics'][role])
  for name,state in [('model_only',False),('fallback_only',True)]:
   part=[r for r in rows if bool(r['fallback'])==state];good=[r for r in part if r['actual']is not None];want={'planned':len(part),'scored':len(good),'outcome_states':dict(Counter(r['outcome_state']for r in part)),'metrics':allmetrics(good)};compare('coverage_slices',want,grade['coverage_slices'][name]);compare('safe_coverage_slices',want,summary['coverage_slices'][name])
  for name in ['LEAF_CDF','ROLE_PRIOR']:
   vv=np.array([expected_scores[ident(r)][name][0]for r in scored]);nn=np.array([expected_scores[ident(r)][name][1]for r in scored]);lo=np.array([r['distribution_intervals'][name]['p10']for r in scored]);hi=np.array([r['distribution_intervals'][name]['p90']for r in scored]);yy=np.array([r['actual']for r in scored]);ninfinite=int(np.isposinf(nn).sum());want={'n':len(scored),'CRPS':float(vv.mean()),'negative_log_mass':{'state':'POSITIVE_INFINITY'if ninfinite else'FINITE','positive_infinite_rows':ninfinite,'value':None if ninfinite else float(nn.mean())},'interval80_coverage_inclusive':float(np.mean((yy>=lo)&(yy<=hi))),'interval80_mean_width':float(np.mean(hi-lo)),'interval80_score':float(np.mean(hi-lo+10*np.maximum(lo-yy,0)+10*np.maximum(yy-hi,0)))};compare('distribution_metrics',want,grade['distribution_metrics'][name]);compare('safe_distribution_metrics',want,summary['distribution_metrics'][name])
  def loss(r,m,k):return abs(r['predictions'][m]-r['actual'])if k=='MAE'else(r['predictions'][m]-r['actual'])**2 if k=='MSE'else expected_scores[ident(r)][m][0]
  require(len(grade['paired_contrasts'])==len(summary['paired_contrasts'])==5,'exact5 fixedcontrasts required')
  for ref in grade['paired_contrasts']:
   k=ref['loss'];candidate=ref['candidate'];control=ref['control'];delta=np.array([loss(r,candidate,k)-loss(r,control,k)for r in scored]);base=float(np.mean([loss(r,control,k)for r in scored]));mean=float(delta.mean());near('contrast_delta',mean,ref['mean_loss_difference']);near('contrast_gain',None if base==0 else-100*mean/base,ref['relative_improvement_percent']);require(ref['n']==1954,'contrast paired denominator')
   for field in ['game_id','week']:
    groups={}
    for r,v in zip(scored,delta):groups.setdefault(r['identity'][field],[]).append(v)
    sizes=np.array([len(v)for v in groups.values()]);sums=np.array([sum(v)for v in groups.values()]);n=len(groups);target=ref[field+'_interval'];require(target['clusters']==n,'bootstrap cluster denominator')
    if n<8:require(target['state']=='UNAVAILABLE_FEWER_THAN8CLUSTERS','week interval must remain unavailable');continue
    rng=np.random.Generator(np.random.PCG64(1703));bs=[]
    for _ in range(500):ix=rng.integers(0,n,n);bs.append(sums[ix].sum()/sizes[ix].sum())
    near('bootstrap_lower',float(np.quantile(bs,.025,method='linear')),target['lower']);near('bootstrap_upper',float(np.quantile(bs,.975,method='linear')),target['upper'])
  compare('safe_native_contrasts',grade['paired_contrasts'],summary['paired_contrasts'])
  text=grade['private_scorecard_csv_utf8'];require(sha(text.encode())==grade['private_scorecard_sha256']==summary['private_scorecard_sha256'],'private scorecard hash differs');reader=csv.DictReader(io.StringIO(text));csvcount=0
  csv_keys=['season','week','game_id','player_id','team','opponent'];lookup={tuple(str(r['identity'][k])for k in csv_keys):r for r in rows};seen=set()
  for z in reader:
   method=z['method'];key=tuple(z[k]for k in csv_keys);require(method in NAMES and key in lookup and(key,method)not in seen,'scorecard identity/method/duplicate');seen.add((key,method));r=lookup[key];require(float(z['prediction_chart_points'])==r['predictions'][method],'scorecard frozen prediction differs')
   require((z['actual_chart_points']==''and r['actual']is None)or(z['actual_chart_points']!=''and float(z['actual_chart_points'])==r['actual']),'scorecard actual differs');e=r['errors'][method];require((z['signed_error']==''and e is None)or(z['signed_error']!=''and float(z['signed_error'])==e),'scorecard signed error differs');require((z['absolute_error']==''and e is None)or(z['absolute_error']!=''and float(z['absolute_error'])==abs(e)),'scorecard absolute error differs')
   require(z['outcome_state']==r['outcome_state']and z['position']==r['position'],'scorecard state/position differs');require(z['fallback']==(r['fallback']if method in NAMES[:2]else''),'scorecard fallback differs');require(z['cutoff_utc']==(r['cutoff_utc']or'')and z['kickoff_utc']==(r['kickoff_utc']or''),'scorecard issue clocks differ');csvcount+=1
  require(csvcount==16936==grade['private_scorecard_rows']==summary['private_scorecard_rows'],'all2117x8 readable scorecard rows required')
  require(progress['model_loads']==1 and progress['forest_apply_predict_calls']==progress['new_fits']==progress['new_query_inference']==0,'read-only numerical verification contract violated');check()
  output={'version':VERSION,'state':'PASS','scope':'Independent arithmetic/law verification from exact frozen model fields,leaf assignments,points andgrades; not source-independent NFL truth','plan_sha256':a.sha256,'freeze_sha256':sha(bodies['forecast']),'grade_sha256':sha(bodies['grade']),'aggregate_sha256':sha(bodies['safe_aggregate']),'checks':progress,'complete_population':{'planned':2117,'scored':1954,'unknown':163,'games':93,'weeks':6,'point_values':16936,'distribution_law_rows':4234,'paired_contrasts':5,'bootstrap_replicates_each':500,'week_intervals':'unavailable6clusters'},'maximum_absolute_discrepancies':dict(maxdiff),'independent_law_method':'32 frozen leaf histograms;95%empirical+5%symmetric signed-geometric prior (100%registeredfallback); exactCDFbisection andintegerCDF-sumCRPSwithanalyticalinfinitegeometrictails;divideCRPS/50','metrics':mm,'distribution_metrics':summary['distribution_metrics'],'new_NFL_fits_query_inference_HTTP_CAS_writes':0,'actual_backend':'UNATTESTED','resources':usage(),'limitations':['No forest.apply/predict/newqueries and no retraining.','Retained source labels and membership not reauthenticated against independent NFL publisher.','One trusted pickle load; source/feature chronology remains original exposed7day reconstruction.','No independent confirmation, prospective accuracy, live readback or offhostrestoration claim.']}
  write(result,output);check();print(json.dumps({'state':'PASS','receipt':str(result),'bytes':result.stat().st_size,'sha256':sha(result.read_bytes()),'resources':usage(),'checks':progress}))
 except BaseException as error:
  signal.setitimer(signal.ITIMER_REAL,0)
  write(failed,{'version':VERSION,'state':'FAILED_REVIEW_ATTEMPT_PRESERVED','plan_sha256':a.sha256,'error_type':type(error).__name__,'error':str(error)[:300],'progress':progress,'resources':usage(),'automatic_retries':0,'new_NFL_fits_query_inference_HTTP_CAS_writes':0});raise
 finally:done.set();signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()
