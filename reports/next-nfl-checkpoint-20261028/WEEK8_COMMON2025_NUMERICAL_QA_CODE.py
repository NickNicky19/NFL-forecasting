"""Independent cached-row acceptance; no fitting, model loading or NFL acquisition."""
from pathlib import Path
import argparse
import collections
import datetime
import hashlib
import io
import json
import math
import os
import resource
import signal
import sys
import time
import zipfile

KEYS=['season','week','game_id','player_id']
CONTEXT=['team','opponent','position','kickoff_utc','cutoff_utc']
METHODS=['CDF_H1_CURRENT_SEASON_TRAINING','CDF_H2_PRIOR_PLUS_CURRENT_TRAINING','CDF_H3_TIME_WEIGHTED_FIXED365_TRAINING','CDF_H4_HISTORICAL_RELATION_CURRENT_STATE','FROZEN_CDF_MEAN']
POLICY_IDS=['CURRENT_ONLY','PRIOR_PLUS_CURRENT','TIME_WEIGHTED','HISTORICAL_RELATION_CURRENT_STATE']
checks=0

def sha(b):return hashlib.sha256(b).hexdigest()
def req(ok,msg):
    global checks
    checks+=1
    if not ok:raise ValueError(msg)
def encoded(x):return (json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
def authenticate(ref):
    p=Path(ref['path']);req(p.is_absolute() and p.resolve()==p,'canonical private/input path')
    before=p.stat();h=hashlib.sha256();size=0
    with p.open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):size+=len(b);h.update(b)
    after=p.stat();req(size==ref['bytes'] and h.hexdigest()==ref['sha256'],'source byte/hash identity')
    req((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'stable input source stamp')
    return p

def jsonref(ref):return json.loads(authenticate(ref).read_bytes())
def close(a,b,label):
    if isinstance(a,float) or isinstance(b,float):req(math.isclose(float(a),float(b),rel_tol=1e-11,abs_tol=1e-9),label)
    else:req(a==b,label)

def metrics(frame):
    y=frame.actual.to_numpy(float);p=frame.point.to_numpy(float)
    good=frame.participation_state.eq('played').to_numpy() & np.isfinite(y) & (y>=0) & (y==np.floor(y))
    delta=p[good]-y[good];a=np.abs(delta)
    return {'offered':len(frame),'scored':int(good.sum()),'games':int(frame.loc[good].game_id.nunique()),'weeks':int(frame.loc[good].week.nunique()),'played_zero':int((good & (y==0)).sum()),'participation':frame.participation_state.value_counts(dropna=False).to_dict(),'played_missing':int((frame.participation_state.eq('played').to_numpy() & ~np.isfinite(y)).sum()),'played_invalid':int((frame.participation_state.eq('played').to_numpy() & np.isfinite(y) & ~good).sum()),'fallback_offered':int(frame.fallback.ne('').sum()),'fallback_scored':int((good & frame.fallback.ne('').to_numpy()).sum()),'MAE':float(a.mean()),'MSE':float(np.mean(delta**2)),'RMSE':float(np.sqrt(np.mean(delta**2))),'bias':float(delta.mean()),'p90_abs':float(np.quantile(a,.9,method='linear')),'p95_abs':float(np.quantile(a,.95,method='linear')),'maximum_abs':float(a.max()),'error_lt1':float((a<1).mean()),'error_le1':float((a<=1).mean())}

def compare_metrics(actual,expected,label):
    req(set(actual)==set(expected),label+' fields')
    for k,v in actual.items():close(v,expected[k],label+'/'+k)

def boot(frame,cluster):
    keys=['season','week'] if cluster=='week' else ['season','game_id']
    grouped=frame.groupby(keys,sort=True).delta.agg(['sum','count'])
    count=len(grouped);out={'clusters':count,'paired_rows':len(frame)}
    if count<8:out.update(state='N/A',interval=None);return out
    rng=np.random.Generator(np.random.PCG64(1703));draw=rng.integers(0,count,size=(500,count))
    values=grouped['sum'].to_numpy()[draw].sum(axis=1)/grouped['count'].to_numpy()[draw].sum(axis=1)
    out.update(state='DESCRIPTIVE',interval=np.quantile(values,[.025,.975],method='linear').tolist());return out

parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--go',required=True);args=parser.parse_args()
raw=Path(args.plan).read_bytes();req(sha(raw)==args.sha256,'exact QA plan');plan=json.loads(raw)
go=json.loads(Path(args.go).read_bytes());req(go['root']=='/root' and go['state']=='GO' and go['plan_sha256']==args.sha256,'root GO before cached score rows')
req(sha(Path(__file__).read_bytes())==plan['checker_sha256'],'exact independent checker code')
req(plan['resources']=={'CPU_seconds':30,'wall_seconds':60,'RSS_bytes':536870912,'invocations':1,'maximum_forecast_capsule_bytes':50331648,'maximum_score_capsule_bytes':4194304,'maximum_metadata_output_bytes':65536,'fits':0,'model_loads':0,'inference':0,'original_NFL_table_decodes':0,'HTTP':0,'CAS_writes':0,'automatic_retries':0},'finite QA caps')
start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(30,31));signal.signal(signal.SIGALRM,lambda *unused:os._exit(124));signal.setitimer(signal.ITIMER_REAL,59)
def deny(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.fork','os.posix_spawn','os.system'):raise ValueError('read-only offline cached QA requires no network/child')
sys.addaudithook(deny)
output=Path(plan['output']);failure=Path(plan['failure_output']);req(not output.exists() and not failure.exists(),'one fresh QA invocation')
try:
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    science=jsonref(plan['inputs']['scientific_plan']);freeze_receipt=jsonref(plan['inputs']['freeze_readback']);score_receipt=jsonref(plan['inputs']['score_readback']);completion=jsonref(plan['inputs']['completion'])
    req(completion['state']=='NEW2025_COMMON_LEARNER_FOUR_HISTORY_COMPARISON_COMPLETE','actual completed comparison')
    req(completion['resources']['returned_forest_fits']==completion['resources']['actual_forest_fit_entries']==52,'52 actual returned forests')
    req(completion['resources']['tree_estimators']==1664,'1664 actual tree estimators')
    req(science['scope']['evaluation_season']==2025 and science['scope']['weeks']==list(range(1,19)),'full2025REG18week science')
    req(len(science['fold_opportunities'])==55,'all55 new fixed slots')
    archive_members={}
    for name,receipt,cap in [('forecasts',freeze_receipt,50331648),('scores',score_receipt,4194304)]:
        ref=plan['inputs'][name];req(ref['bytes']<=cap,'archive cap')
        req(receipt['binding']==ref,'native original archive binding')
        with zipfile.ZipFile(authenticate(ref)) as z:
            req(len(z.namelist())==len(set(z.namelist())),'unique archive names')
            req(set(z.namelist())==set(receipt['members']),'complete native file map')
            for path,meta in receipt['members'].items():
                h=hashlib.sha256();n=0
                with z.open(path) as f:
                    for chunk in iter(lambda:f.read(65536),b''):n+=len(chunk);h.update(chunk)
                req(n==meta['bytes'] and h.hexdigest()==meta['sha256'],'member integrity:'+path)
            if name=='forecasts':
                manifest=json.loads(z.read('MANIFEST.json'))
                req(manifest['complete_outer_label_decodes']==0 and manifest['forecast_rows']==5436 and manifest['offered_unique_rows']==1359,'complete freeze before outer labels')
                req(manifest['plan_sha256']==plan['inputs']['scientific_plan']['sha256'],'frozen scientific plan hash')
                req(manifest['opportunities_consumed']==55 and len(manifest['fit_audits'])==55,'complete55 fit opportunity census')
                req({r['slot']['id'] for r in manifest['fit_audits']}=={r['id'] for r in science['fold_opportunities']},'exact declared slots')
                for a in manifest['fit_audits']:
                    slot=a['slot']['id'];audit=json.loads(z.read(slot+'/FIT_AUDIT.json'))
                    req(a==audit,'manifest fit audit identity')
                    req(a['model_sha256']==receipt['members'][slot+'/MODEL.joblib']['sha256'],'retained model bytes hash; never loaded')
                    req(a['training_sha256']==receipt['members'][slot+'/TRAINING_BINDING.parquet']['sha256'],'retained training hash')
                    maximum=a['maximum_training_label_available_utc']
                    if maximum is not None:req(pd.Timestamp(maximum)<pd.Timestamp(a['cutoff_utc']),'training labels earlier than fold cutoff')
                forecasts=pq.read_table(io.BytesIO(z.read('FORECASTS.parquet')),use_threads=False).to_pandas()
            else:
                report=json.loads(z.read('REPORT.json'))
                scored=pq.read_table(io.BytesIO(z.read('SCORED_ROWS.parquet')),use_threads=False).to_pandas()
                csv_rows=pd.read_csv(io.BytesIO(z.read('SCORED_ROWS.csv')))
            archive_members[name]=len(z.namelist())
    req(report['forecast_freeze']==plan['inputs']['forecasts'] and report['plan_sha256']==plan['inputs']['scientific_plan']['sha256'],'report original forecast/plan binding')
    req(len(forecasts)==5436 and len(scored)==6795 and len(csv_rows)==6795,'5436 forecasts/6795 graded+readable rows')
    req(set(forecasts.method)==set(METHODS[:4]) and set(scored.method)==set(METHODS),'four candidates+one control')
    req(not forecasts.duplicated(KEYS+['method']).any() and not scored.duplicated(KEYS+['method']).any(),'one outcome per method/player-game')
    sort=KEYS+CONTEXT
    arms={m:scored.loc[scored.method.eq(m)].sort_values(sort,kind='stable').reset_index(drop=True) for m in METHODS}
    reference=arms[METHODS[-1]]
    for m,f in arms.items():
        req(len(f)==1359 and f[sort].equals(reference[sort]),'same full1359 context:'+m)
        req(np.isfinite(f.point.to_numpy(float)).all(),'complete finite issued points')
        req(f.actual.equals(reference.actual) and f.participation_state.equals(reference.participation_state),'same outcome+participation for each arm')
        req(set(f.participation_state)<=set(['played','unknown','DNP']),'distinct participation states')
        req(f.loc[~f.participation_state.eq('played'),'actual'].isna().all(),'unknown/DNP never fabricated numeric outcome')
        if m in METHODS[:4]:
            original=forecasts.loc[forecasts.method.eq(m)].sort_values(sort,kind='stable').reset_index(drop=True)
            req(original[sort].equals(f[sort]) and original.point.equals(f.point) and original.fallback.equals(f.fallback),'graded forecasts identical to original freeze:'+m)
    summaries={m:metrics(f) for m,f in arms.items()}
    for m,s in summaries.items():compare_metrics(s,report['summaries'][m],m)
    expected={(m,METHODS[-1]) for m in METHODS[:4]}|{(m,METHODS[3]) for m in METHODS[:3]}
    req(len(report['paired'])==7 and {(p['candidate'],p['comparator']) for p in report['paired']}==expected,'seven prespecified paired contrasts')
    paired=[]
    for pair in report['paired']:
        m,c=pair['candidate'],pair['comparator'];a,b=arms[m],arms[c]
        y=a.actual.to_numpy(float);good=a.participation_state.eq('played').to_numpy()&np.isfinite(y)&(y>=0)&(y==np.floor(y))
        delta=(a.point.to_numpy(float)-y)**2-(b.point.to_numpy(float)-y)**2
        close(int(good.sum()),pair['n'],'paired row count');close(float(delta[good].mean()),pair['MSE_delta_candidate_minus_control'],'paired MSE difference')
        close(100*(summaries[c]['MSE']-summaries[m]['MSE'])/summaries[c]['MSE'],pair['relative_improvement_percent'],'paired relative improvement')
        warm=good&a.modeled_training_rows.ge(60).to_numpy();close(int(warm.sum()),pair['adequately_trained_n'],'adequate training count')
        if warm.any():close(float(delta[warm].mean()),pair['adequately_trained_delta_MSE'],'adequate training MSE difference')
        for weekly in pair['weekly']:
            w=weekly['week'];mask=good&a.week.eq(w).to_numpy();close(int(mask.sum()),weekly['n'],'weekly paired population');close(float(delta[mask].mean()),weekly['MSE_delta'],'weekly paired MSE delta')
        q=a.loc[good,KEYS].copy();q['delta']=delta[good]
        intervals={}
        for x in pair['intervals']:
            current=boot(q,x['cluster']);close(current['clusters'],x['clusters'],'bootstrap clusters');close(current['paired_rows'],x['paired_rows'],'bootstrap rows');req(current['state']==x['state'],'bootstrap state')
            if current['interval'] is not None:
                for u,v in zip(current['interval'],x['interval']):close(u,v,'independent paired percentile interval')
            intervals[x['cluster']]=current
        paired.append({'candidate':m,'control':c,'MSE_delta':float(delta[good].mean()),'intervals':intervals})
    readable=csv_rows.sort_values(KEYS+CONTEXT+['method'],kind='stable').reset_index(drop=True)
    native=scored.sort_values(KEYS+CONTEXT+['method'],kind='stable').reset_index(drop=True)
    req(readable[KEYS+['method']].astype(str).equals(native[KEYS+['method']].astype(str)),'CSV original identity/order')
    req(np.allclose(readable.prediction_mean_attempts,native.point,rtol=1e-12,atol=1e-12,equal_nan=True),'CSV prediction values')
    req(np.allclose(readable.actual_attempts,native.actual,rtol=1e-12,atol=1e-12,equal_nan=True),'CSV actual values')
    unknown=~native.participation_state.eq('played')
    req(readable.loc[unknown,'absolute_error_attempts'].isna().all(),'CSV unsupported outcomes not graded as zero')
    req(Path(plan['inputs']['forecasts']['path']).stat().st_size==plan['inputs']['forecasts']['bytes'],'original freeze retained')
    use={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    req(use['CPU_seconds']<=30 and use['wall_seconds']<=60 and use['RSS_bytes']<=536870912,'bounded acceptance runtime')
    result={'schema_version':'week8-common2025-independent-numerical-acceptance-v1','state':'PASS_CACHED_ROWS_AND_PAIRED_ARITHMETIC','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':args.sha256,'checker_sha256':sha(Path(__file__).read_bytes()),'checks':checks,'archive_members_verified':archive_members,'forecasts_checked':5436,'scored_method_rows_checked':6795,'unique_player_games':1359,'candidate_procedures':4,'control_procedures':1,'fit_opportunity_audits_checked':55,'actual_returned_fits_existing':52,'trees_existing':1664,'summaries':summaries,'paired':paired,'resources':use,'new_fits_model_loads_inference_HTTP_CAS_original_NFL_table_decodes':0,'new_football_observations':0,'replayed_models':False,'scientific_qualification':False,'new_live_use':False}
    body=encoded(result);req(len(body)<=65536,'safe acceptance metadata cap');output.write_bytes(body);print(json.dumps({'path':str(output),'bytes':len(body),'sha256':sha(body),'state':result['state'],'resources':use}))
except BaseException as e:
    body=encoded({'schema_version':'week8-common2025-independent-numerical-acceptance-v1','state':'FAILED_ACCEPTANCE_PRESERVED_NO_RETRY','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':args.sha256,'checker_sha256':sha(Path(__file__).read_bytes()),'error':str(e),'type':type(e).__name__,'checks_before_failure':checks,'resources':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'new_fits_model_loads_inference_HTTP_CAS_original_NFL_table_decodes':0})
    failure.write_bytes(body);raise
finally:signal.setitimer(signal.ITIMER_REAL,0)
