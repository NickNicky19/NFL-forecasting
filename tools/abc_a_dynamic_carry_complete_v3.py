"""Zero-fit admission/scoring of exact retained V2 forecasts after bundle refusal.

Never changes failed run state. Full law bytes stay in the original immutable
failure member; scorecards reference them and retain scalar parameters instead
of copying every PMF a second time. All storage guards remain active.
"""
from __future__ import annotations
import collections,gzip,hashlib,io,json,math,os,resource,sys,time,zipfile
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','ARROW_IO_THREADS']:os.environ[k]='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import abc_a_dynamic_carry_wave_v1 as base
OUT=ROOT/'reports/abc-championship/predictive-improvement-01'
V2=OUT/'runtime-v2';V3=OUT/'completion-v3';RUN='ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
def main():
    begin=time.monotonic();cpu=time.process_time()
    import numpy as np,pandas as pd,pyarrow as pa
    from nfl_lab import cdf_engine as cdf
    from tools import category_topfive_matched12_storage_v1 as st
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    resource.setrlimit(resource.RLIMIT_CPU,(280,300));resource.setrlimit(resource.RLIMIT_AS,(1610612736,)*2)
    import signal
    def exhausted(*_):raise TimeoutError('finite zero-fit completion envelope')
    signal.signal(signal.SIGXCPU,exhausted);signal.signal(signal.SIGALRM,exhausted);signal.alarm(400)
    plan=json.loads((OUT/'COMPLETION_REGISTRATION_V3.json').read_text())
    for ref in plan['code_bindings']:
        if base.sha((ROOT/ref['path']).read_bytes())!=ref['sha256']:raise ValueError('completion source binding')
    for ref in plan['metadata_bindings']:
        raw=(ROOT/ref['path']).read_bytes()
        if len(raw)!=ref['bytes']or base.sha(raw)!=ref['sha256']:raise ValueError('completion metadata binding')
    if len(sys.argv)!=2 or sys.argv[1]!=base.sha((OUT/'COMPLETION_REGISTRATION_V3.json').read_bytes()):raise ValueError('exact completion protocol required')
    store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
    destination=store.forward_root/'research'/RUN
    with store.transaction():store._refresh();usage=store._require(plan['resources']['peak_new_bytes'])
    census=json.loads((OUT/'COMPLETION_CONTENT_CENSUS_V3.json').read_text())
    path=destination/'FAILED_PARTIALS_V2.zip';store.validate_reference(path,census['source_sha256'])
    with zipfile.ZipFile(path)as z:member=z.read(census['member'])
    if base.sha(member)!=census['member_sha256']:raise ValueError('forecast member changed')
    forecasts=json.loads(gzip.decompress(member));seen=set();by=collections.defaultdict(list);coherence=collections.defaultdict(list);max_tail=0.;max_mass_error=0.;max_mean_error=0.
    for r in forecasts:
        key=tuple(r[k]for k in ['season','game_id','player_id','arm'])
        if key in seen:raise ValueError('duplicate forecast identity')
        seen.add(key);by[(r['season'],r['arm'])].append(r)
        cutoff=pd.Timestamp(r['cutoff_utc']);kickoff=pd.Timestamp(r['kickoff_utc'])
        if cutoff.tzinfo is None or cutoff>kickoff:raise ValueError('cutoff contract')
        clock=r.get('source_information_max_UTC')
        if clock not in [None,'NaT']and pd.Timestamp(clock)>=cutoff:raise ValueError('future information clock')
        if r.get('mean')is not None and not math.isfinite(r['mean']):raise ValueError('nonfinite point')
        law=r['law']
        if law is None:
            if r['arm']!='STORED_COUNT_A_MEAN_CONTROL'or r['median']is not None:raise ValueError('unsupported law attribution')
            continue
        if law['kind']=='leaf_cdf':
            prior=cdf.SupportPrior(**law['prior']);batch=cdf.MixtureBatch(np.array(law['support']),np.array([law['weights']]),prior,prior_weight=law['prior_weight'])
            if abs(float(batch.mean[0])-r['mean'])>1e-10 or float(batch.quantile(.5)[0])!=r['median']:raise ValueError('CDF saved product mismatch')
        else:
            mass=np.array(law['pmf']);error=abs(float(mass.sum())-1);max_mass_error=max(max_mass_error,error)
            mean_error=abs(float(np.arange(len(mass))@mass)-r['mean']);max_mean_error=max(max_mean_error,mean_error)
            if error>1e-10 or mean_error>1e-7 or (mass<0).any()or not np.isfinite(mass).all():raise ValueError('finite allocation law invalid')
            if int(np.searchsorted(np.cumsum(mass),.5))!=r['median']:raise ValueError('allocation median inconsistent')
            if law['omitted_mass_bound']>1.01e-12:raise ValueError('tail exceeds registered bound')
            max_tail=max(max_tail,law['omitted_mass_bound']);coherence[(r['season'],r['game_id'],r['team'],r['arm'])].append(r)
    for key,rs in coherence.items():
        laws=[r['law']for r in rs]
        if len({r['cutoff_utc']for r in rs})!=1 or len({(x['shape'],x['rate'],x['allocation_kappa'])for x in laws})!=1:raise ValueError('mixed joint law')
        if len({x['other_probability']for x in laws})!=1:raise ValueError('mixed other bucket')
        if abs(sum(x['allocation_share']for x in laws)+laws[0]['other_probability']-1)>1e-12:raise ValueError('missing finite other bucket')
    b,c,g,fr=base.sources()
    f26=pd.read_parquet(io.BytesIO(base.pin(c['features'])),columns=base.KEY+base.CTX)
    f26=f26.loc[f26.position.eq('RB')]
    f25=pd.read_parquet(io.BytesIO(base.pin(b['inputs']['features'])),columns=list(dict.fromkeys(base.KEY+base.CTX+['roster_status'])))
    f25=f25.loc[f25.season.eq(2025)&f25.week.between(1,8)&f25.position.eq('RB')&f25.roster_status.isin(['ACT','INA'])]
    for (year,arm),rs in by.items():
        q=f25 if year==2025 else f26
        wanted={tuple(str(v)for v in r)for r in q[base.KEY+base.CTX].to_numpy()};got={tuple(str(r[k])for k in base.KEY+base.CTX)for r in rs}
        if wanted!=got:raise ValueError('outer population/context mismatch')
    expected={(year,arm)for year in [2025,2026]for arm in ['A0_BACKFIELD_CDF','A1_BACKFIELD_CDF_ROLE_INPUTS','A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION']}|{(2026,'STORED_COUNT_A_MEAN_CONTROL')}
    if len(forecasts)!=9912 or set(by)!=expected:raise ValueError('missing expected method/year blocks')
    # Fresh-process readback of both newly returned models; cached rows suffice
    # for this scoring step, so no model deserialization is needed.
    models=[]
    events=[json.loads(line)for line in(V2/'RUN_STEP_EVENTS_V1.jsonl').read_text().splitlines()]
    for event in events:
        if event['event']!='FIT_RETURNED_MODEL_SAVED_READBACK':continue
        store.validate_reference(destination/event['object_id'],event['sha256']);models.append({k:event[k]for k in ['object_id','sha256','bytes','season','arm']})
    if len(models)!=2:raise ValueError('new model readback scope')
    admission={'state':'ADMITTED_FOR_OWNER_LOCAL_RESEARCH_SCORING_NOT_PRODUCTION','rows':len(forecasts),'blocks':{f'{y}|{a}':len(rs)for(y,a),rs in sorted(by.items())},'source_artifact_sha256':census['source_sha256'],'source_member_sha256':census['member_sha256'],'models_fresh_process_readback':models,'joint_groups_checked':len(coherence),'max_mass_error':max_mass_error,'max_mean_error':max_mean_error,'max_tail_bound':max_tail,'new_fits_inference':0,'parent_run_states':'FAILED_PRESERVED; content admission does not mark parent run completed.','CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin}
    V3.mkdir(exist_ok=True);(V3/'CONTENT_ADMISSION_V3.json').write_bytes(base.enc(admission))
    # All calculations still consume the complete original laws. Only the
    # subsequent scorecard serialization factors the already-retained arrays.
    original_archive=base.archive
    def factored(members):
        if 'NUMERICAL_ROWS.json.gz'in members:
            rows=json.loads(gzip.decompress(members['NUMERICAL_ROWS.json.gz']))
            for r in rows:
                if r['law']is not None:r['law']={k:v for k,v in r['law'].items()if k not in ['pmf','weights','support']}
                r['full_law_reference']={'artifact_sha256':census['source_sha256'],'member':census['member'],'member_sha256':census['member_sha256'],'key':{k:r[k]for k in ['season','game_id','player_id','arm']}}
            members={**members,'NUMERICAL_ROWS.json.gz':gzip.compress(base.enc(rows),mtime=0),'ORIGINAL_LAW_REFERENCE.json':base.enc(census)}
        return original_archive(members)
    base.archive=factored;base.OUT=V3
    (V3/'START_SCORING_V3.json').write_bytes(base.enc({'state':'SCORING','source_rows':len(forecasts),'new_fits':0,'source_member_sha256':census['member_sha256'],'UTC':base.now()}))
    base.score(forecasts,store,destination,json.loads((V2/'PROTOCOL_V1.json').read_text()),np,pd)
    (V3/'COMPLETION_COUNTERS_V3.json').write_bytes(base.enc({'state':'COMPLETED_OWNER_LOCAL_SCORING','CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'new_fits':0,'new_inference':0,'preserved_parent_fit_attempts':4,'failed_fit_attempts':1,'successfully_returned_forests_cumulative':3,'new_NFL_outcomes_created':0}))

if __name__=='__main__':
    try:main()
    except BaseException as e:
        import signal
        soft,hard=resource.getrlimit(resource.RLIMIT_CPU)
        if hard==300:resource.setrlimit(resource.RLIMIT_CPU,(hard,hard))
        signal.signal(signal.SIGXCPU,signal.SIG_IGN)
        V3.mkdir(exist_ok=True);(V3/'COMPLETION_FAILURE_V3.json').write_bytes(base.enc({'state':'FAILED','error_type':type(e).__name__,'new_fits':0,'new_inference':0,'parents_unchanged':True,'UTC':base.now()}));raise
