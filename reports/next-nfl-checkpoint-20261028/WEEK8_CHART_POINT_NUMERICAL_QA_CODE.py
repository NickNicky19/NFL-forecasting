"""Independent chart cached-prediction/label arithmetic acceptance; no model load."""
from pathlib import Path
import argparse
import base64
import collections
import csv
import datetime
import gc
import gzip
import hashlib
import io
import json
import math
import os
import resource
import signal
import sys
import time

METHODS=['HGB_CHART_MEDIAN_V1','POSITION_CHART_MEDIAN_2024','GLOBAL_CHART_MEDIAN_2024','POSITION_CHART_MEAN_2024']
checks=0

def sha(b):return hashlib.sha256(b).hexdigest()
def req(ok,msg):
    global checks
    checks+=1
    if not ok:raise ValueError(msg)
def encoded(x):return (json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
def key(r):return tuple(r['identity'][k] for k in ('season','week','game_id','team','opponent','player_id','season_type'))
def read(ref,compressed=False):
    p=Path(ref['path']);req(p.is_absolute() and p.resolve()==p,'canonical immutable input')
    before=p.stat();body=p.read_bytes();after=p.stat()
    req(len(body)==ref['bytes'] and sha(body)==ref['sha256'],'exact input hash/bytes')
    req((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'stable input stamp')
    if compressed:
        req(len(body)<=plan['resources']['maximum_compressed_bytes_per_capsule'],'compressed cap')
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as f:body=f.read(plan['resources']['maximum_expanded_bytes_per_capsule']+1)
        req(len(body)<=plan['resources']['maximum_expanded_bytes_per_capsule'],'expanded cap')
    return json.loads(body)

def compare(a,b,name):
    if isinstance(a,dict):
        req(set(a)==set(b),'mapping fields:'+name)
        for k in a:compare(a[k],b[k],name+'/'+str(k))
    elif isinstance(a,list):
        req(len(a)==len(b),'list length:'+name)
        for i,(x,y) in enumerate(zip(a,b)):compare(x,y,name+'/'+str(i))
    elif isinstance(a,(int,float)) and not isinstance(a,bool):req(isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-9),'numeric:'+name)
    else:req(a==b,'value:'+name)

def metrics(rows,method):
    y=np.asarray([r['actual'] for r in rows],float);p=np.asarray([r['predictions'][method] for r in rows],float);e=p-y;a=np.abs(e)
    return {'n':len(e),'MAE':float(a.mean()),'MSE':float(np.mean(e*e)),'RMSE':float(np.sqrt(np.mean(e*e))),'bias':float(e.mean()),'p90_absolute_error':float(np.quantile(a,.9,method='linear')),'p95_absolute_error':float(np.quantile(a,.95,method='linear')),'max_absolute_error':float(a.max()),'error_strict_lt1':float(np.mean(a<1)),'error_inclusive_le1':float(np.mean(a<=1)),'error_strict_lt5':float(np.mean(a<5)),'error_inclusive_le5':float(np.mean(a<=5))}
def allmetrics(rows):return {m:metrics(rows,m) for m in METHODS}
def pair(rows,control):
    delta=np.asarray([abs(r['predictions'][METHODS[0]]-r['actual'])-abs(r['predictions'][control]-r['actual']) for r in rows])
    error=float(delta.mean());baseline=float(np.mean([abs(r['predictions'][control]-r['actual']) for r in rows]))
    out={'candidate':METHODS[0],'control':control,'primary':'MAE','n':len(rows),'mean_loss_difference':error,'relative_improvement_percent':-100*error/baseline if baseline else None}
    for name in ['game_id','week']:
        groups={}
        for row,d in zip(rows,delta):groups.setdefault(row['identity'][name],[]).append(d)
        count=len(groups)
        if count<8:out[name+'_interval']={'state':'UNAVAILABLE_FEWER_THAN8CLUSTERS','clusters':count};continue
        vals=list(groups.values());sums=np.array([sum(v) for v in vals]);sizes=np.array([len(v) for v in vals]);rng=np.random.default_rng(1703);samples=[]
        for unused in range(500):
            drawn=rng.integers(0,count,count);samples.append(sums[drawn].sum()/sizes[drawn].sum())
        out[name+'_interval']={'state':'NOMINAL_EXPOSED_DEVELOPMENT_DIAGNOSTIC','clusters':count,'confidence':.95,'replicates':500,'seed':1703,'lower':float(np.quantile(samples,.025)),'upper':float(np.quantile(samples,.975))}
    return out

parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--go',required=True);args=parser.parse_args()
raw=Path(args.plan).read_bytes();req(sha(raw)==args.sha256,'exact review plan');plan=json.loads(raw);go=json.loads(Path(args.go).read_bytes());req(go['state']=='GO' and go['root']=='/root' and go['plan_sha256']==args.sha256,'explicit root GO before row decode');req(sha(Path(__file__).read_bytes())==plan['checker_sha256'],'exact checker')
req(plan['resources']=={'CPU_seconds':15,'wall_seconds':30,'RSS_bytes':268435456,'invocations':1,'maximum_compressed_bytes_per_capsule':2097152,'maximum_expanded_bytes_per_capsule':33554432,'maximum_metadata_output_bytes':65536,'fits':0,'model_loads':0,'inference':0,'original_NFL_table_decodes':0,'HTTP':0,'CAS_writes':0,'automatic_retries':0},'finite cached QA caps')
start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(15,16));signal.signal(signal.SIGALRM,lambda *unused:os._exit(124));signal.setitimer(signal.ITIMER_REAL,29)
def deny(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.fork','os.posix_spawn'):raise ValueError('cached QA offline child-free scope')
sys.addaudithook(deny);output=Path(plan['output']);failure=Path(plan['failure_output']);req(not output.exists() and not failure.exists(),'one fresh invocation')
try:
    labels=read(plan['inputs']['qualified_chart_labels'],True)
    req(labels['target']=='nick-chart-ppr-v1' and len(labels['labels'])==14160,'qualified complete source label capsule')
    labelmap={key(r):(r['value'],r['state']) for r in labels['labels'] if r['identity']['season']==2026};req(len(labelmap)==2117,'full2026 label panel');del labels;gc.collect()
    freeze=read(plan['inputs']['forecasts'],True);grade=read(plan['inputs']['grades'],True);summary=read(plan['inputs']['safe_aggregate']);complete=read(plan['inputs']['completion']);science=read(plan['inputs']['scientific_plan'])
    import numpy as np
    req(freeze['target']==grade['target']==summary['target']=='nick-chart-ppr-v1','same chart contract')
    req(freeze['plan_sha256']==grade['plan_sha256']==summary['plan_sha256']==plan['inputs']['scientific_plan']['sha256'],'same exact scientific plan')
    req(grade['freeze_sha256']==summary['freeze_capsule_sha256']==plan['inputs']['forecasts']['sha256'],'original immutable forecast freeze')
    req(summary['score_capsule_sha256']==plan['inputs']['grades']['sha256'],'grade body source')
    req(complete['actual_work']['completed_fits']==1 and complete['actual_work']['fit_attempts']==1,'existing one actual model fit')
    req(complete['actual_work']['durably_frozen_forecast_rows']==2117 and complete['actual_work']['completed_scoring_runs']==1,'existing full freeze and score')
    req(freeze['functional_contracts']=={METHODS[0]:'MAE_objective_point_no_distribution',METHODS[1]:'empirical_position_median',METHODS[2]:'empirical_global_median',METHODS[3]:'position_conditional_mean_control'},'truthful separate point products')
    req(sha(base64.b64decode(freeze['fitted_model_pickle_base64'],validate=True))==freeze['fitted_model_sha256']==summary['model_sha256'],'fitted byte integrity only; never unpickle')
    compare(freeze['features'],science['features'],'fixed features');compare(freeze['fitted_iterations'],150,'fixed150 iterations')
    req(freeze['training']['planned']==5935 and freeze['training']['supported_numeric']==5589,'training coverage/missingness preserved')
    raw_rows=freeze['forecasts'];rows=grade['rows'];req(len(raw_rows)==len(rows)==2117,'complete2117 player-games')
    before={key(r):r for r in raw_rows};after={key(r):r for r in rows};req(len(before)==len(after)==2117 and set(before)==set(after)==set(labelmap),'unique complete canonical identities')
    fallbacks=collections.Counter();states=collections.Counter()
    for k,r in after.items():
        original=before[k];projected={n:v for n,v in r.items() if n not in ['actual','errors','outcome_state']};req(projected==original,'forecast+timing+fallback exactly unchanged from freeze')
        req(set(r['predictions'])==set(METHODS) and all(type(v) in (int,float) and math.isfinite(v) for v in r['predictions'].values()),'four finite point values')
        actual,state=labelmap[k];req(r['outcome_state']==state and r['actual']==actual,'qualified2026actual+participation unchanged')
        states[state]+=1
        if r['fallback']:fallbacks[r['fallback']]+=1
        if actual is None:
            req(state=='unknown_participation' and all(e is None for e in r['errors'].values()),'unknown labels retain null errors')
        else:
            req(state in ('played_score','played_zero') and math.isfinite(actual),'supported played actual')
            for m in METHODS:compare(r['errors'][m],r['predictions'][m]-actual,'signed row error')
    scored=[r for r in rows if r['actual'] is not None];req(len(scored)==1954 and states['unknown_participation']==163,'same scored/fullpopulation')
    req(len({r['identity']['game_id'] for r in rows})==len({r['identity']['game_id'] for r in scored})==93 and {r['identity']['week'] for r in rows}==set(range(1,7)),'93games6weeks')
    compare(dict(fallbacks),freeze['fallbacks'],'fallback counts');compare(dict(fallbacks),summary['query_coverage']['fallbacks'],'summary fallback counts')
    compare(len([r for r in rows if r['fallback']]),85,'85 fallbacks');compare(len([r for r in rows if not r['fallback']]),2032,'2032 model points')
    computed=allmetrics(scored);compare(computed,grade['metrics'],'all4 cached primary+secondary metrics');compare(computed,summary['metrics'],'safe summary metrics')
    weekly={}
    for w in range(1,7):
        part=[r for r in rows if r['identity']['week']==w];good=[r for r in part if r['actual'] is not None]
        weekly[str(w)]={'planned':len(part),'scored':len(good),'outcome_states':dict(collections.Counter(r['outcome_state'] for r in part)),'metrics':allmetrics(good) if good else {}}
    compare(weekly,grade['weekly'],'all weekly cells');compare(weekly,summary['weekly'],'safe weekly cells')
    roles={}
    for role in ['QB','RB','FB','WR','TE']:
        part=[r for r in scored if r['position']==role]
        if part:roles[role]=allmetrics(part)
    compare(roles,grade['role_metrics'],'role metrics');compare(roles,summary['role_metrics'],'safe role metrics')
    slices={}
    for name,fallback in [('model_only',False),('fallback_only',True)]:
        part=[r for r in rows if bool(r['fallback'])==fallback];good=[r for r in part if r['actual'] is not None]
        slices[name]={'planned':len(part),'scored':len(good),'outcome_states':dict(collections.Counter(r['outcome_state'] for r in part)),'metrics':allmetrics(good) if good else {}}
    compare(slices,grade['coverage_slices'],'model/fallback-only errors+coverage');compare(slices,summary['coverage_slices'],'safe model/fallback-only cells')
    pairs=[pair(scored,m) for m in METHODS[1:3]];compare(pairs,grade['paired_contrasts'],'independent500game/6weekNAloss intervals');compare(pairs,summary['paired_contrasts'],'safe paired intervals')
    text=grade['private_scorecard_csv_utf8'];req(sha(text.encode())==grade['private_scorecard_sha256']==summary['private_scorecard_sha256'],'scorecard text exact hash')
    csv_rows=list(csv.DictReader(io.StringIO(text)));req(len(csv_rows)==8468==grade['private_scorecard_rows']==summary['private_scorecard_rows'],'full8468 readable scorecard')
    seen=set()
    for r in csv_rows:
        k=(int(r['season']),int(r['week']),r['game_id'],r['team'],r['opponent'],r['player_id'],'REG');m=r['method'];req((k,m) not in seen,'unique CSV opportunity/method');seen.add((k,m));source=after[k]
        compare(float(r['prediction']),source['predictions'][m],'CSV prediction');req(r['position']==source['position'] and r['outcome_state']==source['outcome_state'],'CSV role/participation')
        if source['actual'] is None:req(r['actual_chart_points']==r['signed_error']==r['absolute_error']=='','CSV unknown remains blank')
        else:
            compare(float(r['actual_chart_points']),source['actual'],'CSV actual');compare(float(r['signed_error']),source['errors'][m],'CSV signed error');compare(float(r['absolute_error']),abs(source['errors'][m]),'CSV absolute error')
        req(r['cutoff_utc']==(source['cutoff_utc'] or '') and r['kickoff_utc']==(source['kickoff_utc'] or ''),'CSV forecast cutoff/kickoff provenance')
    req(summary['new_live_use'] is False and summary['prospective'] is False and summary['distribution_or_prop_probabilities']=='UNAVAILABLE_POINT_ONLY','no website/prospective/distribution claim')
    use={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};req(use['CPU_seconds']<=15 and use['wall_seconds']<=30 and use['RSS_bytes']<=268435456,'finite acceptance budget')
    result={'schema_version':'week8-chart-point-independent-numerical-acceptance-v1','state':'PASS_ORIGINAL_CACHED_FORECASTS_LABELS_AND_ERROR_ARITHMETIC','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':args.sha256,'checker_sha256':sha(Path(__file__).read_bytes()),'checks':checks,'unique_planned_player_games':2117,'known_numeric_outcomes':1954,'unknown_participation':163,'games':93,'weeks':6,'method_forecast_values':8468,'private_readable_scorecard_rows':8468,'model_points':2032,'fallback_points':85,'metrics':computed,'paired':pairs,'resources':use,'new_fits_model_loads_inference_original_NFL_table_decodes_HTTP_CAS':0,'new_football_observations':0,'model_replay':False,'new_live_use':False,'scientific_qualification':False,'interpretation':'OnefixedHGBMAEpoint vsconstantposition/global chart controls; noauthenticwebsitechartcomparison,distributionorprobabilityclaim. Source-label reconstruction remains exposed development.'}
    body=encoded(result);req(len(body)<=65536,'safe QA metadata cap');output.write_bytes(body);print(json.dumps({'path':str(output),'bytes':len(body),'sha256':sha(body),'state':result['state'],'resources':use}))
except BaseException as error:
    failure.write_bytes(encoded({'schema_version':'week8-chart-point-independent-numerical-acceptance-v1','state':'FAILED_ACCEPTANCE_PRESERVED_NO_RETRY','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'error':str(error),'type':type(error).__name__,'plan_sha256':args.sha256,'checker_sha256':sha(Path(__file__).read_bytes()),'checks_before_failure':checks,'resources':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'new_fits_models_inference_HTTP_CAS_original_NFL_tables':0}));raise
finally:signal.setitimer(signal.ITIMER_REAL,0)
