"""One read-only arithmetic check of safe aggregate policy decisions."""
from pathlib import Path
import gzip,hashlib,json,math,resource,signal,sys,time
R=Path('/workspace/nfl-methods-integration/reports/next-nfl-checkpoint-20261028')
D=Path('/workspace/nfl-lowest-median-policy-v2-20261028/reports/next-nfl-median-policy-v2-20261028/COHORT_DECISIONS_GZIP_V2')
out=R/'NEXT_POINT_AGGREGATE_GZIP_INDEPENDENT_QA_V1.json';used=R/'NEXT_POINT_AGGREGATE_GZIP_QA_CONSUMED_V1.json'
assert not out.exists() and not used.exists();used.write_text('{"one_invocation_consumed":true,"automatic_retries":0}\n')
start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(12,13));resource.setrlimit(resource.RLIMIT_AS,(268435456,268435456))
def stop(*args):raise TimeoutError('finite aggregate QA limit')
signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,19)
def audit(event,args):
    if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.fork','os.forkpty','os.posix_spawn','os.posix_spawnp'}:raise ValueError('offline metadata QA')
sys.addaudithook(audit)
def sha(b):return hashlib.sha256(b).hexdigest()
def auth(ref):
    p=Path(ref['path']);assert p.is_absolute() and p.resolve()==p
    b=p.read_bytes();assert len(b)==ref['bytes'] and sha(b)==ref['sha256'];return b
n=0
def check(x):
    global n
    assert x;n+=1
def close(a,b):return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
def product(r):return 'point_median' if r['product'] in ['median','median_objective_point'] else 'point_mean'
try:
    b=(D/'DECISIONS.json.gz').read_bytes();check(len(b)==9103 and sha(b)=='58cba3d0c1442ec40b2ec5eb19428b418992f99a6f2c410e5f4f78ffda37dd31')
    raw=gzip.decompress(b);check(len(raw)==78998 and sha(raw)=='bfda33b741ac937104164fb0cd7075548c1d01db5cc3cb42f1c110bce4b7447c')
    data=json.loads(raw);done=json.loads((D/'COMPLETE.json').read_bytes());consumed=json.loads((D/'CONSUMED.json').read_bytes())
    seal='520c24305f2951bbd6656a447d43aba228d452840d82c75bbe974600ced3f11e'
    check(done['state']=='SAFE_AGGREGATE_GZIP_V2_COMPLETE' and done['plan_sha256']==consumed['plan_sha256']==data['plan_sha256']==seal)
    check(done['decision_file']=={'name':'DECISIONS.json.gz','bytes':len(b),'sha256':sha(b),'uncompressed_bytes':len(raw),'uncompressed_sha256':sha(raw)})
    check(done['readback']=='BYTE_IDENTICAL' and done['policy_or_input_changes'] is False and done['prior_V1_failure_preserved'] is True)
    cohort=json.loads(gzip.decompress(auth(data['source_safe_aggregate'])))
    check(data['source_safe_aggregate']['sha256']=='2e2b7f87f7b5470a1421d4e4778da05f3ddc40c453dd5cc2eb68cdb4f25e7f04')
    qa=json.loads(auth(data['independent_source_QA']));check(qa['state']=='PASS' and qa['source_safe_aggregate_sha256']==data['source_safe_aggregate']['sha256'])
    records=[r for r in cohort['records'] if r['position']=='ALL_ORIGINAL_PRIMARY_ROLES' and r['group']=='full' and r['period']=='2026_W1_6']
    check(len(data['decisions'])==11 and data['live_activation'] is False and data['full_population_only'] and data['subgroups_not_used_to_choose_global_model'])
    heads=[];targets=[]
    for d in data['decisions']:
        t='chart_ppr' if d['target']=='nick-chart-ppr-v1' else d['target'];targets.append(t)
        cells=[r for r in records if r['target']==t];check(bool(cells))
        current=d['actual_prior_display']
        def winner(rows):
            v=min(r['metrics']['MAE'] for r in rows);tied=[r for r in rows if r['metrics']['MAE']==v]
            old=[r for r in tied if r['method']==current['method_id'] and product(r)==current['product']]
            return old[0] if old else min(tied,key=lambda r:r['method'])
        lead=winner(cells);med=winner([r for r in cells if product(r)=='point_median'])
        means=[r for r in cells if product(r)=='point_mean'];mean=min(means,key=lambda r:(r['metrics']['MSE'],r['method']))
        check(d['research_leader']==lead['method'] and close(d['research_leader_MAE_2026'],lead['metrics']['MAE']))
        check(d['research_leader_original_product']==product(lead) and d['strict_median_MAE_leader']==med['method'] and d['separate_valid_mean_MSE_leader']==mean['method'])
        check(d['product']=='stat_point_mae_v2' and d['primary']=='MAE' and d['scoring_target']==d['target'])
        check(d['operational_candidate'] is None and d['unchanged_fallback_contract']==current and d['live_activation'] is False and d['scientific_qualification'] is False and d['old_P2_and_v1_unchanged'] is True)
        check(set(d['readiness_reasons'])=={r['method'] for r in cells})
        for r in cells:
            check(set(d['readiness_reasons'][r['method']])=={'operational_pending:'+x for x in ['future_inference','source_and_artifact_bindings','durable_capture_restore','consumer_contract','fallback_rollback','retained_owner_admission']})
            diag=d['diagnostics_reported_without_automatic_veto'][r['method']]
            for key in ['MSE','RMSE','bias','p90_AE','p95_AE']:check(close(diag[key+'_2026'] if key in ['MSE','RMSE'] else diag[key],r['metrics'][key]))
            check(d['coverage']=={'offered_rows':r['metrics']['planned'],'scored_rows':r['metrics']['scored'],'games':r['metrics']['games'],'weeks':r['metrics']['weeks']})
        if t in ['rush_att','rec']:check(current['method_id']=='LIVE_SELECTED_COUNT_A_DECLARED_MEAN' and current['fallback_recipe_equivalence_to_lab_corrected_mean']=='UNVERIFIED_NOT_INFERRED_FROM_ALIAS')
        heads.append({'target':t,'MAE_leader':lead['method'],'MAE':lead['metrics']['MAE'],'mean_MSE_leader':mean['method'],'retained':True})
    check(set(targets)=={r['target'] for r in records if r['target']!='anytime_td'})
    p=data['anytime_probability_stream'];check(p['state']=='NOT_CHANGED_BY_NUMERIC_POINT_POLICY' and p['current_method']=='TD_EQUAL_CDF_CAT' and p['source_records']==[r for r in records if r['target']=='anytime_td'])
    for name,h in [('CONSUMED.json','f0f65e1278393cfe60dd93de909dedf12f5ae602b89f607edff48acf81def837'),('FAILED.json','c4fd15ba013f8238648571d1f382daba76e401b398f959b3c05f4e0f78177d2c')]:check(sha((D.parent/'COHORT_DECISIONS_V1'/name).read_bytes())==h)
    elapsed=time.monotonic()-start;seconds=time.process_time()-cpu;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024;check(elapsed<=20 and seconds<=12 and rss<=268435456)
    result={'state':'PASS','version':'point-aggregate-gzip-v2-independent-qa-v1','checks':n,'decision_sha256':sha(b),'decoded_sha256':sha(raw),'decisions':heads,'all11_retained':True,'ATD_unchanged':True,'V1_failure_preserved':True,'CPU_seconds':seconds,'wall_seconds':elapsed,'RSS_bytes':rss,'new_NFL_fits_models_outcomes_predictions_scoring_CAS_network':0,'actual_backend':'UNATTESTED','budget_scope':'Separate8KiBsource+8KiBreceipts allocation inside unchanged16MiB sharedmetadata cap; prior1086Bstaticreview included; no budget refund'}
except BaseException as e:result={'state':'FAIL','type':type(e).__name__,'message':str(e)[:300],'checks':n,'automatic_retries':0}
finally:signal.setitimer(signal.ITIMER_REAL,0)
body=(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode();assert len(body)<=8192
with out.open('xb') as f:f.write(body)
print(body.decode())
if result['state']!='PASS':sys.exit(1)
