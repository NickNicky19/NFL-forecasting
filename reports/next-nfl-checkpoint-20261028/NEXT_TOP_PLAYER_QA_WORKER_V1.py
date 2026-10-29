"""One finite independent QA of retained cohort rows and aggregate metrics."""
from pathlib import Path
import gzip,hashlib,io,json,math,os,resource,signal,sys,time,zipfile
ROOT=Path('/workspace/nfl-methods-integration')
PLAN=ROOT/'config/next-checkpoint-top-player-independent-qa-v1.json'
started=time.monotonic();cpu=time.process_time();plan_bytes=PLAN.read_bytes();plan=json.loads(plan_bytes)
assert plan['state']=='AUTHORIZED_READONLY_RECORDED_GRADE_QA' and plan['reviewer']=='/root/current_runtime_and_review'
assert plan['resources']=={'CAS':0,'CPU_seconds':60,'RSS_bytes':536870912,'fits':0,'invocations':1,'metadata_bytes':24576,'network':0,'new_outcomes':0,'new_predictions':0,'wall_seconds':90}
out=Path(plan['output']);consumed=out.with_name('NEXT_TOP_PLAYER_QA_CONSUMED_V1.json')
assert not out.exists() and not consumed.exists()
consumed.write_text(json.dumps({'state':'ONE_READONLY_QA_INVOCATION_CONSUMED','plan_sha256':hashlib.sha256(plan_bytes).hexdigest(),'automatic_retries':0})+'\n')
resource.setrlimit(resource.RLIMIT_CPU,(60,61))
def alarm(*args):raise TimeoutError('finite top-player QA limit')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,85)
def deny(event,args):
    if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.fork','os.forkpty','os.posix_spawn','os.posix_spawnp'}:raise ValueError('offline child-free QA')
sys.addaudithook(deny)
def sha(b):return hashlib.sha256(b).hexdigest()
def auth(ref):
    p=Path(ref['path']);assert p.is_absolute() and p.resolve()==p
    b=p.read_bytes();assert len(b)==ref['bytes'] and sha(b)==ref['sha256'];return b
checks=0
def verify(ok,why):
    global checks
    assert ok,why
    checks+=1
def eq(a,b):
    if a is None or b is None:return a is b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-9)
    return a==b
try:
    import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    blobs={k:auth(v) for k,v in plan['inputs'].items()}
    native=json.loads(blobs['complete']);safe=json.loads(gzip.decompress(blobs['safe']))
    verify(native['state']==safe['state']=='TOP_PLAYER_CACHED_COMPARISONS_COMPLETE' and native['managed_writer']=='CLOSED','completion state')
    verify(native['safe_output']['sha256']==sha(blobs['safe']) and native['safe_output']['uncompressed_sha256']==sha(gzip.decompress(blobs['safe'])),'safe readback')
    verify(native['grade']==safe['grade'] and native['membership_freeze']==safe['membership_freeze'],'native/source linkage')
    verify(safe['grade']['sha256']==sha(blobs['grade']) and safe['membership_freeze']['sha256']==sha(blobs['freeze']),'private capsule refs')
    with zipfile.ZipFile(io.BytesIO(blobs['freeze'])) as z:
        verify(set(z.namelist())=={'MEMBERSHIPS.parquet','MANIFEST.json'},'freeze members')
        members=pq.read_table(pa.BufferReader(z.read('MEMBERSHIPS.parquet')),use_threads=False).to_pandas();manifest=json.loads(z.read('MANIFEST.json'))
    with zipfile.ZipFile(io.BytesIO(blobs['grade'])) as z:
        verify(set(z.namelist())=={'RESULT.json','COMPARISON_ROWS.parquet','SOURCE_VERSIONS.json'},'grade members')
        result=json.loads(z.read('RESULT.json'));rows=pq.read_table(pa.BufferReader(z.read('COMPARISON_ROWS.parquet')),use_threads=False).to_pandas();sources=json.loads(z.read('SOURCE_VERSIONS.json'))
    verify(manifest['state']=='ALL12_COMMON_WEEKLY_MEMBERSHIPS_FROZEN_BEFORE_EVALUATION_LABELS' and manifest['target_evaluation_labels_decoded']==manifest['fits']==manifest['model_loads']==0,'prelabel freeze contract')
    verify(manifest['plan_sha256']==result['plan_sha256'] and sources['inputs']==manifest['input_bindings'] and sources['membership_freeze']==safe['membership_freeze'],'source versions')
    verify(result['records']==safe['records'] and result['paired']==safe['paired'] and result['diagnostics']==safe['diagnostics'],'all aggregate cells retained')
    verify(safe['new_predictive_fits']==safe['new_model_inference']==result['new_prospective_forecasts']==0 and result['specialized_training_tested'] is False and result['live_selection_or_release'] is False,'scope claims')
    KEY=['season','week','game_id','player_id','team','opponent'];ID=['target',*KEY]
    verify(len(members)==15860 and members.target.nunique()==12 and not members.duplicated(ID).any(),'full frozen membership')
    verify(not rows.duplicated(['target','method',*KEY]).any(),'unique method opportunities')
    verify(members.season.eq(2026).all() and members.week.between(1,6).all(),'period')
    expected={'pass_yd':515,'pass_td':515,'pass_cmp':515,'pass_att':515,'pass_int':515,'rush_yd':668,'rush_att':668,'rec':2458,'rec_yd':2458,'rush_rec_yd':2458,'anytime_td':2458,'chart_ppr':2117}
    verify(members.groupby('target').size().to_dict()==expected,'category primary membership counts')
    verify(not {'actual','prediction','signed_error','participation_state'}&set(members.columns),'target labels or predictions in membership freeze')
    joined=rows.merge(members,on=ID,how='left',validate='many_to_one',suffixes=('','_frozen'),indicator=True)
    verify(joined['_merge'].eq('both').all(),'rows missing frozen membership')
    for col in members.columns:
        if col in ID:continue
        a=joined[col];b=joined[col+'_frozen']
        verify((a.eq(b)|(a.isna()&b.isna())).all(),'changed frozen column:'+col)
    for target,t in rows.groupby('target'):
        for method,f in t.groupby('method'):
            verify(len(f)==expected[target] and f['product'].nunique()==1,'method omitted original population')
        v=t.groupby(KEY,dropna=False)[['actual','participation_state']].nunique(dropna=False)
        verify(v.eq(1).all().all(),'methods have different outcomes or supported populations')
    known=members['rank'].notna();score=pd.to_numeric(members.rank_score,errors='coerce')
    verify(np.array_equal(known,np.isfinite(score)),'rank missingness')
    verify(members.rank_history_slots.between(0,8).all() and members.rank_known_slots.le(members.rank_history_slots).all(),'prior slot bounds')
    deadlines=pd.to_datetime(members.rank_deadline,utc=True);calendar=pd.to_datetime(members.calendar_kickoff,utc=True)
    prior_time=pd.to_datetime(members.rank_max_available,utc=True,errors='coerce');last_game=pd.to_datetime(members.rank_last_game,utc=True,errors='coerce')
    verify(prior_time.loc[known].notna().all() and last_game.loc[known].notna().all(),'ranked rows lack source clocks')
    verify(deadlines.notna().all() and deadlines.lt(calendar).all(),'ranking not before target games')
    verify((prior_time.isna()|prior_time.lt(deadlines)).all() and (last_game.isna()|last_game.lt(deadlines)).all(),'rank source chronology')
    for k,g in members.groupby(['target','position','week'],sort=True):
        u=g[['player_id','rank_score','rank']].drop_duplicates();verify(not u.player_id.duplicated().any(),'different player rank within week')
        ranked=u.loc[u['rank'].notna()].sort_values(['rank_score','player_id'],ascending=[False,True])
        verify(np.array_equal(ranked['rank'].to_numpy(float),np.arange(1,len(ranked)+1,dtype=float)),'ranking/tie rule')
        for n in [10,15,20]:verify(ranked.loc[ranked['rank'].le(n),'player_id'].nunique()<=n,'TopN includes too many unique players')
    verify(np.isfinite(rows.prediction.to_numpy(float)).all(),'nonfinite point')
    numeric=pd.to_numeric(rows.actual,errors='coerce');verify(not np.isinf(numeric).any(),'infinite outcome')
    good=rows.participation_state.eq('played')&np.isfinite(numeric)
    verify(rows.loc[~rows.participation_state.eq('played'),'actual'].isna().all(),'nonplayed numeric outcome')
    for col in ['source_label_input','source_forecast_input']:
        keys=set(str(x) for x in rows[col].unique())
        verify(all(all(k in sources['inputs'] for k in key.split('+')) for key in keys),'row source keys unresolved')
    error=rows.prediction.to_numpy()-numeric.to_numpy();verify(np.allclose(rows.loc[good,'signed_error'],error[good],rtol=0,atol=1e-12),'saved signed errors')
    verify(np.allclose(rows.loc[good,'absolute_error'],abs(error[good]),rtol=0,atol=1e-12),'saved absolute errors')
    counts=rows.target.isin(['pass_td','pass_cmp','pass_att','pass_int','rush_att','rec'])&good
    verify((numeric[counts]>=0).all() and np.equal(numeric[counts],np.floor(numeric[counts])).all(),'count support')
    cache={}
    for (target,method),f in rows.groupby(['target','method'],sort=False):
        cache[(target,method,'ALL_ORIGINAL_PRIMARY_ROLES')]=f
        for position,t in f.groupby('position',sort=False):cache[(target,method,position)]=t
    def groupmask(f,group):
        rank=f['rank'];finite=rank.notna()
        return {'full':np.ones(len(f),bool),'top10':finite&rank.le(10),'top15':finite&rank.le(15),'top20':finite&rank.le(20),'rank1_10':finite&rank.le(10),'rank11_15':finite&rank.gt(10)&rank.le(15),'rank16_20':finite&rank.gt(15)&rank.le(20),'remainder':~finite|rank.gt(20),'unranked':~finite}[group]
    def select(target,method,position,group,period):
        f=cache[(target,method,position)];mask=groupmask(f,group)
        if period!='2026_W1_6':mask=mask&f.week.eq(int(period.split('_W')[1]))
        return f.loc[mask]
    def metric(f,target):
        y=pd.to_numeric(f.actual,errors='coerce').to_numpy(float);p=f.prediction.to_numpy(float);ok=f.participation_state.eq('played').to_numpy()&np.isfinite(y)&np.isfinite(p)
        e=p[ok]-y[ok];a=abs(e);fallback=f.fallback.fillna('').ne('').to_numpy();tol=1 if target in ['pass_td','pass_cmp','pass_att','pass_int','rush_att','rec','chart_ppr'] else 10
        d={'planned':len(f),'scored':int(ok.sum()),'players':f.loc[ok,'player_id'].nunique(),'games':f.loc[ok,'game_id'].nunique(),'weeks':f.loc[ok,'week'].nunique(),'outcome_states':{str(k):int(v) for k,v in f.participation_state.value_counts(dropna=False).items()},'played_missing':int((f.participation_state.eq('played').to_numpy()&~np.isfinite(y)).sum()),'played_zero':int((ok&(y==0)).sum()),'fallback_planned':int(fallback.sum()),'fallback_scored':int((ok&fallback).sum()),'rank_unavailable_planned':int(f['rank'].isna().sum()),'original_forecast_clock_unknown':int(f.forecast_clock_state.eq('original_clock_unknown').sum()),'absolute_error_sum':float(a.sum()),'tolerance':None if target=='anytime_td' else tol}
        for k,v in [('MAE',a.mean() if len(a) else None),('MSE',(e*e).mean() if len(e) else None),('RMSE',np.sqrt((e*e).mean()) if len(e) else None),('bias',e.mean() if len(e) else None),('p90_AE',np.quantile(a,.9) if len(a) else None),('p95_AE',np.quantile(a,.95) if len(a) else None),('strict_within',(a<tol).mean() if len(a) and target!='anytime_td' else None),('inclusive_within',(a<=tol).mean() if len(a) and target!='anytime_td' else None)]:d[k]=v
        return d,ok,p,y
    metric_cells=0;probability_cells=0
    for record in safe['records']:
        target=record['target'];f=select(target,record['method'],record['position'],record['group'],record['period']);m=record['metrics'];values,ok,p,y=metric(f,target)
        for k,v in values.items():verify(eq(v,m[k]),'aggregate metric:'+target+'/'+k)
        verify(record['product']==cache[(target,record['method'],record['position'])]['product'].iloc[0],'original product changed')
        verify(m['actual_prop_offered_population']=='UNAVAILABLE_NOT_GENERIC_QUERY_POOL' and m['authentic_offer_side_or_close_and_correct']=='UNAVAILABLE_NO_MATCHED_AUTHENTIC_LINES','fabricated offer diagnostics')
        if 'share_of_full_position_absolute_error' in m:
            total=cache[(target,record['method'],record['position'])];base=metric(total,target)[0]['absolute_error_sum'];verify(eq(m['share_of_full_position_absolute_error'],None if base==0 else values['absolute_error_sum']/base),'error contribution')
        if target=='anytime_td':
            pp=p[ok];yy=y[ok];verify(((pp>=0)&(pp<=1)).all() and np.isin(yy,[0,1]).all(),'binary probability contract')
            with np.errstate(divide='ignore'):loss=np.where(yy==1,-np.log(pp),-np.log1p(-pp))
            inf=int(np.isposinf(loss).sum());q=m['probability_scores'];verify(eq(q['Brier'],values['MSE']),'Brier')
            verify(q['log_loss']['state']==('POSITIVE_INFINITY' if inf else 'FINITE' if len(loss) else 'UNAVAILABLE') and q['log_loss']['positive_infinite_rows']==inf,'infinite loss population')
            verify(eq(q['log_loss']['value'],None if inf or not len(loss) else loss.mean()),'log loss')
            for i,b in enumerate(q['reliability']):
                mask=(pp>=i/10)&((pp<(i+1)/10) if i<9 else (pp<=1))
                verify(b['n']==int(mask.sum()) and eq(b['mean_probability'],pp[mask].mean() if mask.any() else None) and eq(b['event_rate'],yy[mask].mean() if mask.any() else None),'fixed reliability bin')
            probability_cells+=1
        else:verify(m['probability_scores'] is None,'point-only probability claim')
        metric_cells+=1
    partitions=0
    for (target,method,position),f in cache.items():
        if position=='ALL_ORIGINAL_PRIMARY_ROLES':continue
        a=sum(np.asarray(groupmask(f,g),int) for g in ['rank1_10','rank11_15','rank16_20','remainder'])
        verify(np.equal(a,1).all(),'disjoint bands omit or double count rows')
        verify((~np.asarray(groupmask(f,'unranked'))|np.asarray(groupmask(f,'remainder'))).all(),'unranked not subset of remainder')
        verify((~np.asarray(groupmask(f,'top10'))|np.asarray(groupmask(f,'top15'))).all() and (~np.asarray(groupmask(f,'top15'))|np.asarray(groupmask(f,'top20'))).all(),'nested top cohorts')
        partitions+=1
    pairs=0
    for c in safe['paired']:
        f=select(c['target'],c['candidate'],c['position'],c['group'],'2026_W1_6').sort_values(KEY)
        b=select(c['target'],c['control'],c['position'],c['group'],'2026_W1_6').sort_values(KEY)
        verify(f[KEY].reset_index(drop=True).equals(b[KEY].reset_index(drop=True)),'paired key populations')
        y=pd.to_numeric(f.actual,errors='coerce').to_numpy(float);ok=f.participation_state.eq('played').to_numpy()&np.isfinite(y)
        ec=f.prediction.to_numpy()[ok]-y[ok];eb=b.prediction.to_numpy()[ok]-y[ok]
        lc=abs(ec) if c['loss']=='MAE' else ec*ec;lb=abs(eb) if c['loss']=='MAE' else eb*eb;delta=lc-lb
        verify(c['paired_rows']==int(ok.sum()) and eq(c['candidate_loss'],lc.mean() if len(lc) else None) and eq(c['control_loss'],lb.mean() if len(lb) else None) and eq(c['candidate_minus_control'],delta.mean() if len(delta) else None),'paired losses')
        verify(eq(c['improvement_percent'],100*(lb.mean()-lc.mean())/lb.mean() if len(lb) and lb.mean()!=0 else None),'paired percent')
        t=f.loc[ok].copy();t['delta_qa']=delta
        for cluster in ['game_id','week']:
            g=t.groupby(cluster,sort=True).delta_qa.agg(['sum','size']).to_numpy(float);k=len(g);claim=c['intervals'][cluster]
            verify(claim['clusters']==k,'paired clusters')
            if k<8:verify(claim['interval'] is None,'insufficient clusters')
            else:
                idx=np.random.default_rng(1703).integers(k,size=(500,k));s=g[idx].sum(axis=1);ci=np.quantile(s[:,0]/s[:,1],[.025,.975]);verify(np.allclose(ci,claim['interval'],rtol=0,atol=1e-9),'paired bootstrap')
        pairs+=1
    primary=[r for r in safe['records'] if r['position']=='ALL_ORIGINAL_PRIMARY_ROLES' and r['group']=='full' and r['period']=='2026_W1_6']
    summary=[]
    for target in expected:
        cells=[x for x in primary if x['target']==target];verify(cells and len({x['metrics']['scored'] for x in cells})==1,'common primary support')
        best=min(cells,key=lambda x:(x['metrics']['probability_scores']['Brier'] if target=='anytime_td' else x['metrics']['MAE'],x['method']))
        summary.append({'target':target,'planned':expected[target],'supported':best['metrics']['scored'],'lowest_observed_full_pool_method':best['method'],'primary':'Brier' if target=='anytime_td' else 'MAE','loss':best['metrics']['probability_scores']['Brier'] if target=='anytime_td' else best['metrics']['MAE']})
    used=time.process_time()-cpu;elapsed=time.monotonic()-started;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    verify(used<=60 and elapsed<=90 and rss<=536870912,'resource cap')
    receipt={'state':'PASS','version':'top-player-independent-qa-v1','reviewer':'/root/current_runtime_and_review','actual_backend':'UNATTESTED','plan_sha256':sha(plan_bytes),'worker_sha256':sha(Path(__file__).read_bytes()),'source_safe_aggregate_sha256':sha(blobs['safe']),'grade_sha256':sha(blobs['grade']),'membership_freeze_sha256':sha(blobs['freeze']),'checks':checks,'membership_rows':len(members),'method_point_rows':len(rows),'unique_target_player_game_opportunities':rows.drop_duplicates(ID).shape[0],'unique_player_game_opportunities':rows.drop_duplicates(KEY).shape[0],'metric_records':metric_cells,'probability_records':probability_cells,'paired_records':pairs,'disjoint_partition_checks':partitions,'summary':summary,'CPU_seconds':used,'wall_seconds':elapsed,'RSS_bytes':rss,'new_fits_models_predictions_outcomes_CAS_network':0,'evidence':'Retained exposed2026W1-6 historical-left-limit rows. No genuine new captures, special training, current website win or prop/price/ranking-return claim. Unranked is a subset of remainder.'}
except BaseException as error:
    receipt={'state':'FAIL','version':'top-player-independent-qa-v1','type':type(error).__name__,'message':str(error)[:1000],'checks_completed':checks,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'automatic_retries':0}
finally:signal.setitimer(signal.ITIMER_REAL,0)
body=(json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();assert len(body)+Path(__file__).stat().st_size+len(plan_bytes)+consumed.stat().st_size<=24576
with out.open('xb') as stream:stream.write(body)
print(json.dumps(receipt))
if receipt['state']!='PASS':sys.exit(1)
