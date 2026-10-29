"""One authorized read-only QA of retained diagnostic rows; no new sources."""
from pathlib import Path
import hashlib, io, json, math, os, resource, signal, sys, time, zipfile

ROOT=Path('/workspace/nfl-methods-integration')
PLAN=ROOT/'config/next-checkpoint-actual-volume-qa-v1.json'
start=time.monotonic();cpu=time.process_time()
plan_body=PLAN.read_bytes();plan=json.loads(plan_body)
assert plan['state']=='AUTHORIZED_READONLY_RECORDED_GRADE_QA'
assert plan['reviewer']=='/root/current_runtime_and_review'
assert plan['resources']=={'CAS':0,'CPU_seconds':20,'RSS_bytes':268435456,'fits':0,'invocations':1,'metadata_bytes':16384,'network':0,'new_outcomes':0,'new_predictions':0,'wall_seconds':30}
out=Path(plan['output']);consumed=out.with_name('NEXT_ACTUAL_VOLUME_QA_CONSUMED_V1.json')
assert not out.exists() and not consumed.exists()
consumed.write_text(json.dumps({'state':'ONE_READONLY_QA_INVOCATION_CONSUMED','plan_sha256':hashlib.sha256(plan_body).hexdigest(),'automatic_retries':0})+'\n')
resource.setrlimit(resource.RLIMIT_CPU,(20,21))
def alarm(*args):raise TimeoutError('read-only QA resource limit')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,28)
def audit(event,args):
    if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.fork','os.forkpty','os.posix_spawn','os.posix_spawnp'}:raise ValueError('offline child-free QA')
sys.addaudithook(audit)
def digest(b):return hashlib.sha256(b).hexdigest()
def auth(path,sha,size=None):
    p=Path(path);assert p.is_absolute() and p.resolve()==p
    b=p.read_bytes();assert digest(b)==sha and (size is None or len(b)==size)
    return b
checks=0
def check(condition,message):
    global checks
    assert condition,message
    checks+=1
def close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-11,abs_tol=1e-10)
try:
    import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    public_bytes=auth(plan['inputs']['public'],plan['inputs']['public_sha256']);public=json.loads(public_bytes)
    check(public['state']=='POSTGAME_DIAGNOSTIC_COMPLETE_NOT_FORECAST','wrong state')
    check(public['new_predictive_fits']==public['new_pregame_forecasts']==0 and public['uses_actual_target_game_volume'] is True,'forecast claim changed')
    fb=auth(public['freeze']['path'],plan['inputs']['freeze_sha256'],public['freeze']['bytes'])
    gb=auth(public['grade']['path'],plan['inputs']['grade_sha256'],public['grade']['bytes'])
    with zipfile.ZipFile(io.BytesIO(fb)) as z:
        check(set(z.namelist())=={'CONTROLS_AND_PRIORS.parquet','CONTRACT.json'},'freeze members')
        frozen=pq.read_table(pa.BufferReader(z.read('CONTROLS_AND_PRIORS.parquet')),use_threads=False).to_pandas()
        contract=json.loads(z.read('CONTRACT.json'))
    with zipfile.ZipFile(io.BytesIO(gb)) as z:
        check(set(z.namelist())=={'RESULT.json','DIAGNOSTIC_ROWS.parquet'},'grade members')
        result=json.loads(z.read('RESULT.json'));rows=pq.read_table(pa.BufferReader(z.read('DIAGNOSTIC_ROWS.parquet')),use_threads=False).to_pandas()
    check(result=={k:v for k,v in public.items() if k not in {'grade','final_usage'}},'inner/public result mismatch')
    keys=['target','season','week','game_id','player_id']
    check(len(frozen)==len(rows)==1183 and not frozen.duplicated(keys).any() and not rows.duplicated(keys).any(),'population')
    check(not {'actual','actual_volume','diagnostic_point','participation_state'}&set(frozen),'target labels in freeze')
    f=frozen.sort_values(keys).reset_index(drop=True);r=rows.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(f,r[f.columns],check_dtype=False,check_exact=True);checks+=1
    check(r.cutoff_utc.eq(r.kickoff_utc).all(),'historical clock changed')
    known=pd.to_datetime(r.feature_max_source_available_utc,utc=True,errors='coerce')
    prior=known.notna()&known.lt(r.cutoff_utc)&r.prior_slot_numeric_count.gt(0)&np.isfinite(r.fixed_prior_rate)&np.isfinite(r.pregame_lag_volume_point)&r.pregame_lag_volume_point.ge(0)
    check(np.array_equal(prior,r.prior_rate_admitted),'prior admission')
    pre=np.where(prior,r.fixed_prior_rate*r.pregame_lag_volume_point,r.control_point)
    check(np.allclose(pre,r.same_rate_pregame_point,rtol=0,atol=1e-12),'same-rate formula')
    good=r.participation_state.eq('played')&np.isfinite(r.actual)
    vol=np.isfinite(r.actual_volume)&r.actual_volume.ge(0)&r.actual_volume.eq(np.floor(r.actual_volume))
    use=good&prior&vol
    oracle=np.where(use,r.actual_volume*r.fixed_prior_rate,pre)
    check(np.array_equal(use,r.diagnostic_applied) and np.allclose(oracle,r.diagnostic_point,rtol=0,atol=1e-12),'actual-volume formula or fallback')
    check(int(good.sum())==737 and r.loc[~r.participation_state.eq('played'),'actual'].isna().all(),'outcome population')
    reason=np.select([~good,~prior,~vol],['target_unresolved_no_score','prior_not_admitted_keep_CDF','volume_unresolved_keep_same_rate_point'],default='')
    check(np.array_equal(reason,r.diagnostic_fallback_reason),'fallback reasons')
    def metric(t,col):
        supported=t.participation_state.eq('played')&np.isfinite(t.actual);s=t.loc[supported]
        e=s[col].to_numpy(float)-s.actual.to_numpy(float);a=abs(e)
        return {'planned':len(t),'scored':len(s),'games':s.game_id.nunique(),'weeks':s.week.nunique(),'players':s.player_id.nunique(),'unknown':t.participation_state.eq('unknown').sum(),'played_missing':(t.participation_state.eq('played')&t.actual.isna()).sum(),'MAE':a.mean(),'MSE':(e*e).mean(),'RMSE':np.sqrt((e*e).mean()),'bias':e.mean(),'p95_absolute_error':np.quantile(a,.95),'error_lt10':(a<10).mean(),'error_le10':(a<=10).mean()}
    def metric_check(t,col,m):
        actual=metric(t,col)
        check(set(actual)==set(m),'metric schema')
        for k,v in actual.items():check(close(v,m[k]),'metric:'+k)
    def paired_check(t,col,cluster,m):
        s=t.loc[t.participation_state.eq('played')&np.isfinite(t.actual)].copy()
        s['diff']=abs(s.diagnostic_point-s.actual)-abs(s[col]-s.actual)
        grouped=s.groupby(cluster,sort=True)['diff'].agg(['sum','size']).to_numpy(float);n=len(grouped)
        check(n==m['clusters'] and len(s)==m['paired_rows'] and close(s['diff'].mean(),m['delta_diagnostic_minus_control']),'paired difference')
        if n<8:check(m['nominal95_interval'] is None,'small-cluster interval')
        else:
            ix=np.random.default_rng(1703).integers(0,n,size=(500,n));v=grouped[ix].sum(axis=1);ci=np.quantile(v[:,0]/v[:,1],[.025,.975])
            check(np.allclose(ci,m['nominal95_interval'],rtol=0,atol=1e-10),'bootstrap interval')
    summary=[]
    for item in public['results']:
        t=r.loc[r.target.eq(item['target'])]
        check(len(t)==(515 if item['target']=='pass_yd' else 668),'target population')
        for col,name in [('control_point','control_metrics'),('same_rate_pregame_point','same_rate_pregame_recipe_metrics'),('diagnostic_point','postgame_actual_volume_diagnostic_metrics')]:metric_check(t,col,item[name])
        for w,g in t.groupby('week'):
            for col,name in [('control_point','control'),('same_rate_pregame_point','same_rate_pregame_recipe'),('diagnostic_point','diagnostic')]:metric_check(g,col,item['weekly'][str(w)][name])
        for col,prefix in [('control_point',''),('same_rate_pregame_point','same_rate_')]:
            paired_check(t,col,'game_id',item[prefix+'game_interval']);paired_check(t,col,'week',item[prefix+'week_interval'])
        c=item['control_metrics']['MAE'];p=item['same_rate_pregame_recipe_metrics']['MAE'];d=item['postgame_actual_volume_diagnostic_metrics']['MAE']
        check(close(100*(c-d)/c,item['signed_MAE_improvement_percent']) and close(100*(p-d)/p,item['actual_volume_vs_same_rate_pregame_percent']),'relative diagnostic gain')
        check(item['diagnostic_fallback_reasons']=={str(k):int(v) for k,v in t.diagnostic_fallback_reason.value_counts().items()},'reason totals')
        check(item['actual_volume_used_scored']==int(t.diagnostic_applied.sum()) and item['actual_volume_not_used']==int((~t.diagnostic_applied).sum()),'application totals')
        for name,mask in [('diagnostic_applied',t.diagnostic_applied),('diagnostic_not_applied',~t.diagnostic_applied),('supported_zero_exposure',t.actual_volume.eq(0))]:
            sub=t.loc[mask]
            for col,m in [('control_point','control'),('diagnostic_point','diagnostic')]:metric_check(sub,col,item['strata'][name][m])
        summary.append({'target':item['target'],'planned':len(t),'scored':int((t.participation_state.eq('played')&t.actual.notna()).sum()),'CDF_MAE':c,'lagged_volume_MAE':p,'postgame_actual_volume_MAE':d,'genuine_new_forecasts':0})
    failure=ROOT/'reports/next-nfl-checkpoint-20261028/NEXT_ACTUAL_VOLUME_NATIVE_V1/FAILURE.json'
    check(failure.exists(),'V1 failure not retained')
    elapsed=time.monotonic()-start;used=time.process_time()-cpu;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    check(elapsed<=30 and used<=20 and rss<=268435456,'resource budget')
    receipt={'state':'PASS','version':'actual-volume-independent-qa-v1','reviewer':'/root/current_runtime_and_review','actual_backend':'UNATTESTED','plan_sha256':digest(plan_body),'worker_sha256':digest(Path(__file__).read_bytes()),'public_sha256':digest(public_bytes),'freeze_sha256':digest(fb),'grade_sha256':digest(gb),'checks':checks,'rows':len(r),'supported_rows':int(good.sum()),'summary':summary,'CPU_seconds':used,'wall_seconds':elapsed,'RSS_bytes':rss,'new_fits_models_predictions_outcomes_CAS_network':0,'interpretation':'Read-only validation of POSTGAME actual-volume diagnostics. These are not achievable pregame gains, forecast replacements or an error floor. V1 failure preserved.'}
except BaseException as error:
    receipt={'state':'FAIL','version':'actual-volume-independent-qa-v1','type':type(error).__name__,'message':str(error)[:1000],'checks_completed':checks,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'automatic_retries':0}
finally:signal.setitimer(signal.ITIMER_REAL,0)
body=(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();assert len(body)<=16384
with out.open('xb') as stream:stream.write(body)
print(json.dumps(receipt))
if receipt['state']!='PASS':sys.exit(1)
