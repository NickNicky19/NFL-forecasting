"""Registered A0/A1/A2 carry comparison; existing private CAS; no production I/O."""
from __future__ import annotations
import argparse,copy,datetime,gzip,hashlib,io,json,math,os,resource,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/abc-championship/predictive-improvement-01'
sys.path.insert(0,str(ROOT))
VERSION='ABC-PREDICTIVE-IMPROVEMENT-01-A-v1'
STATE={'phase':'NOT_STARTED','fit_attempts':0,'returned_fits':0,'model_refs':[],'forecasts':[]}
KEY=['season','week','game_id','player_id']
CTX=['team','opponent','position','kickoff_utc','cutoff_utc']
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def pin(ref):
    p=Path(ref['path']);b=p.read_bytes()
    if len(b)!=ref['bytes'] or sha(b)!=ref['sha256']:raise ValueError('source checksum mismatch: '+p.name)
    return b
def doc(name):
    p=ROOT/'config'/name;b=p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def parquet(frame):
    b=io.BytesIO();frame.to_parquet(b,index=False);return b.getvalue()
def archive(members):
    members=dict(members);members['MEMBER_MANIFEST.json']=enc({k:{'bytes':len(v),'sha256':sha(v)}for k,v in members.items()})
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED)as z:
        for k,v in sorted(members.items()):z.writestr(k,v)
    return b.getvalue()
def note(name,obj):
    p=OUT/name
    with p.open('xb')as f:f.write(enc(obj));f.flush();os.fsync(f.fileno())
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def event(kind,**fields):
    with (OUT/'RUN_STEP_EVENTS_V1.jsonl').open('ab')as f:
        f.write(enc({'UTC':now(),'event':kind,**fields}));f.flush();os.fsync(f.fileno())
def persist_model(store,destination,model,year,arm,joblib):
    stream=io.BytesIO();joblib.dump(model,stream,compress=3);body=stream.getvalue()
    STATE['pending_model_bytes']=body
    filename=f'MODEL_{year}_{arm}.joblib';path=destination/filename
    store.write_bytes(path,body);store.validate_reference(path,sha(body))
    ref={'object_id':filename,'sha256':sha(body),'bytes':len(body),'season':year,'arm':arm}
    STATE['model_refs'].append(ref);STATE.pop('pending_model_bytes',None)
    event('FIT_RETURNED_MODEL_SAVED_READBACK',**ref)

def sources():
    b=doc('category-topfive-backfield-v1.sealed.json')
    c=doc('category-topfive-matched12-inference-followup-v1.json.gz')
    g=doc('category-topfive-matched12-all-finalists-grade-v1.json.gz')
    fr=json.loads((Path(b['native_root'])/'COMPLETE.json').read_text())['freeze']
    return b,c,g,fr

def inputs(pd):
    from nfl_lab import category_topfive_backfield_v1 as bf
    b,c,g,fr=sources();raw=pin(fr);z=zipfile.ZipFile(io.BytesIO(raw))
    train=pd.read_parquet(io.BytesIO(z.read('PREPARED_TRAIN.parquet')))
    history=pd.concat([pd.read_parquet(io.BytesIO(pin(r)))for r in c['history_sources']],ignore_index=True)
    roster=history.set_index(['game_id','player_id']).roster_status.isin(['ACT','INA'])
    train['pregame_roster_qualified']=[bool(roster.get((r.game_id,r.player_id),False))for r in train.itertuples()]
    q26=pd.read_parquet(io.BytesIO(pin(c['features'])))
    q26=q26.loc[q26.position.eq('RB')].copy().reset_index(drop=True)
    base=pd.read_parquet(io.BytesIO(pin(b['inputs']['features'])))
    cols=KEY+CTX+['feature_max_source_available_utc','f_player_games_prior']+[x for x in base if x.startswith('f_')and x!='f_player_games_prior']
    q25=base.loc[base.season.eq(2025)&base.week.between(1,8)&base.roster_status.isin(['ACT','INA']),list(dict.fromkeys(cols))].copy()
    q25['participation_state']='unknown'
    q25=q25.loc[q25.position.eq('RB')].reset_index(drop=True)
    for q in [q25,q26]:
        q['pregame_roster_qualified']=True
        q['outcome_available_utc']=pd.NaT
        q['cutoff_utc']=pd.to_datetime(q.cutoff_utc,utc=True)
        q['kickoff_utc']=pd.to_datetime(q.kickoff_utc,utc=True)
        if not q.participation_state.eq('unknown').all():raise ValueError('query outcome leakage')
    q25=bf.augment(q25,history);q26=bf.augment(q26,history)
    return b,c,g,fr,z,train,history,{2025:q25,2026:q26}

def cached_count_a(g,queries,pd):
    with zipfile.ZipFile(io.BytesIO(pin(g['frozen_bundle'])))as control_zip:
        controls=pd.read_parquet(io.BytesIO(control_zip.read('FORECASTS.parquet')))
    controls=controls.loc[controls.target.eq('rush_att')&controls.method.eq('COUNT_A_MEAN')&controls.position.eq('RB')].copy()
    if controls.empty or controls.duplicated(KEY).any():raise ValueError('empty/ambiguous saved Count A product')
    planned=set(map(tuple,queries[2026][KEY].to_numpy()));got=set(map(tuple,controls[KEY].to_numpy()))
    if planned!=got:raise ValueError('saved Count A outer-population mismatch')
    return controls

def cdf_forecasts(model,q,arm,np):
    rows=[];law_check=0
    for ix,law,reasons in model.predict_batches(q,batch_size=128):
        if law is None:raise ValueError('strong CDF has no law')
        means=law.mean;medians=law.quantile(.5)
        for j,pos in enumerate(ix):
            r={k:(int(q.loc[pos,k])if k in ['season','week']else str(q.loc[pos,k]))for k in KEY+CTX}
            r.update(arm=arm,mean=float(means[j]),median=float(medians[j]),fallback=str(reasons[j])or None,
                generation_UTC=now(),original_issued_UTC=None,source_information_max_UTC=str(q.loc[pos,'feature_max_source_available_utc']),
                law={'kind':'leaf_cdf','support':law.support.tolist(),'weights':law.weights[j].tolist(),
                     'prior':vars(law.prior),'prior_weight':law.b})
            rows.append(r);law_check+=1
    if len(rows)!=len(q):raise ValueError('incomplete law inference')
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--protocol-sha256',required=True);ap.add_argument('--mode',choices=['preflight','run','score'],required=True);a=ap.parse_args()
    protocol=(OUT/'PROTOCOL_V1.json').read_bytes();assert sha(protocol)==a.protocol_sha256
    plan=json.loads(protocol);assert plan['assignment_id']=='ABC-PREDICTIVE-IMPROVEMENT-01'
    for r in plan['code_bindings']:
        assert sha((ROOT/r['path']).read_bytes())==r['sha256']
    for path,r in plan.get('source_bindings',{}).items():
        raw=(ROOT/path).read_bytes();assert len(raw)==r['bytes']and sha(raw)==r['sha256']
    if 'environment'in plan:
        import importlib.metadata
        for package,version in plan['environment'].items():assert importlib.metadata.version(package)==version
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
    import numpy as np,pandas as pd,joblib
    from nfl_lab import abc_dynamic_carry_v1 as core,cdf_engine as cdf
    from tools import category_topfive_matched12_storage_v1 as st
    start=time.monotonic();cpu=time.process_time();STATE.update(start_wall=start,start_CPU=cpu,phase=a.mode,mode=a.mode)
    resource.setrlimit(resource.RLIMIT_CPU,(1700,1800))
    resource.setrlimit(resource.RLIMIT_AS,(plan['resources']['RSS_bytes'],)*2)
    import signal
    def exhausted(*_):raise TimeoutError('registered resource envelope; final100seconds reserved for failure retention')
    signal.signal(signal.SIGXCPU,exhausted);signal.signal(signal.SIGALRM,exhausted);signal.signal(signal.SIGTERM,exhausted)
    signal.alarm(2300)
    if a.mode=='preflight':
        b,c,g,fr,z,train,h,qq=inputs(pd);records=core.compile_history(h)
        sample=qq[2026].iloc[:100].copy();t=time.monotonic();features,aux,params=core.augment(sample,records)
        synthetic=core.allocation_law({'shape':100.,'rate':4.,'allocation_share':.25,'allocation_kappa':30.})
        result={'version':VERSION,'state':'SOURCE_AND_RUNTIME_QUALIFIED_NO_PREDICTIVE_FIT',
            'inputs':{key:{'sha256':ref['sha256'],'bytes':ref['bytes']}for key,ref in {'backfield_capsule':fr,'history':c['history_sources'][0],'week6_history':c['history_sources'][1],'query_features':c['features']}.items()},
            'planned':{str(y):{'player_games':len(q),'games':q.game_id.nunique(),'weeks':sorted(q.week.unique().tolist())}for y,q in qq.items()},
            'history_rows':len(h),'history_team_games':len(records),'team_other_residual_games':sum(r.unresolved>0 for r in records),'team_other_residual_carries':sum(r.unresolved for r in records),
            'sample_feature_rows':len(sample),'NFL_forecast_vectors_generated':0,'sample_wall_seconds':time.monotonic()-t,
            'synthetic_exact_law_tail_bound':synthetic['omitted_mass_bound'],
            'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,
            'fits':0,'accuracy_scores':0,'evidence':'CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION',
            'limits':['Provider total is summed over all stat positions before skill-position filtering, not an independent official team-box certification. Residual is explicit other/unresolved.','No designed-run/scramble/kneel separation in this source. No qualified injury/limited/replacement probabilities.','2025 evaluation uses weekly ACT/INA roster members; original broader training still includes valid stat participants. Pregame roster publication clocks are unverified.']}
        note('SOURCE_QUALIFICATION_V1.json',result);print(json.dumps(result));return
    store,_=st.open_store(ROOT,allocation_sha256=plan['storage']['allocation_sha256'],root_go=st.GO)
    destination=store.forward_root/'research'/VERSION
    STATE.update(store=store,destination=destination)
    if a.mode=='run':
        publication=json.loads((OUT/'PREEXEC_PUBLICATION_READBACK_V1.json').read_text())
        if publication['state']!='PUBLICATION_COMPLETE':raise ValueError('preexec public readback required')
        execution_source_commit=publication['commit']
        assert not destination.exists()
        store.register_root(destination)
        with store.transaction():store._refresh();store._require(plan['resources']['private_peak_bytes'])
        note('START_V1.json',{'run_id':VERSION,'state':'RUNNING','started_UTC':now(),'protocol_sha256':sha(protocol),'new_forest_fit_budget':3,'new_source_HTTP':0})
        b,c,g,fr,z,train,history,queries=inputs(pd)
        controls=cached_count_a(g,queries,pd)
        event('SAVED_COUNT_A_CONTROL_QUALIFIED_BEFORE_FITS',rows=len(controls),source_sha256=g['frozen_bundle']['sha256'])
        records=core.compile_history(history);ttrain,training_aux,params=core.augment(train,records)
        forecasts=STATE['forecasts'];members={'PROTOCOL.json':protocol,'TRAINING_DYNAMIC_FEATURES.parquet':parquet(ttrain[KEY+['feature_max_source_available_utc']+core.FEATURES]),'ANNUAL_FILTER_PARAMETERS.json':enc(params)}
        fit_count=0;audits={};coherence=[];prepared={};numerical=[]
        original=joblib.load(io.BytesIO(z.read('MODELS/rush_att_BACKFIELD.joblib')))
        assert isinstance(original,cdf.LeafCDFModel) and original.audit['fit_state']=='FITTED'
        category=copy.deepcopy(original.category)
        for year,q in queries.items():
            source_q=q.copy();q,aux,par=core.augment(q,records)
            # A0 original inputs are unchanged; A1 appends only the registered group.
            for name in source_q:
                if name!='feature_max_source_available_utc' and not q[name].equals(source_q[name]):raise ValueError('changed control input')
            mask=(ttrain.season<year)&(pd.to_datetime(ttrain.outcome_available_utc,utc=True)<pd.Timestamp(f'{year}-09-01',tz='UTC'))
            training=ttrain.loc[mask].copy()
            if year==2026:base_model=original
            else:
                fit_count+=1;assert fit_count<=3;STATE.update(phase=f'fit_{year}_A0',fit_attempts=fit_count)
                event('FIT_ATTEMPT_CONSUMED',fit_slot=fit_count,season=year,arm='A0')
                base_model=cdf.LeafCDFModel.fit(training,category,'context')
                STATE['returned_fits']+=1
                event('FIT_RETURNED_BEFORE_PERSISTENCE',fit_slot=fit_count,season=year,arm='A0')
                persist_model(store,destination,base_model,year,'A0',joblib)
            forecasts+=cdf_forecasts(base_model,source_q,'A0_BACKFIELD_CDF',np)
            expanded=copy.deepcopy(category);expanded['panels']['context']=list(category['panels']['context'])+core.FEATURES
            fit_count+=1;assert fit_count<=3
            STATE.update(phase=f'fit_{year}_A1',fit_attempts=fit_count)
            event('FIT_ATTEMPT_CONSUMED',fit_slot=fit_count,season=year,arm='A1')
            learned=cdf.LeafCDFModel.fit(training,expanded,'context')
            STATE['returned_fits']+=1
            event('FIT_RETURNED_BEFORE_PERSISTENCE',fit_slot=fit_count,season=year,arm='A1')
            persist_model(store,destination,learned,year,'A1',joblib)
            if learned.audit['role_priors']!=base_model.audit['role_priors']:raise ValueError('changed training targets or priors')
            if learned.design.medians[:len(base_model.design.medians)]!=base_model.design.medians:raise ValueError('changed old imputation')
            forecasts+=cdf_forecasts(learned,q,'A1_BACKFIELD_CDF_ROLE_INPUTS',np)
            audits[str(year)]={'A0':base_model.audit,'A1':learned.audit,'training_seasons':sorted(training.season.unique().tolist()),'training_rows':len(training),'training_label_max_UTC':str(pd.to_datetime(training.outcome_available_utc,utc=True).max()),'fit_cutoff_UTC':f'{year}-09-01T00:00:00+00:00'}
            for recency in [False,True]:
                allocations,check=core.finite_allocations(q,aux,recency=recency)
                for r in check:r.update(season=year,arm='S0_RECENCY_ALLOCATION'if recency else'A2_DYNAMIC_ALLOCATION')
                coherence+=check
                for pos,parameters in allocations.items():
                    law=core.allocation_law(parameters)
                    row={k:(int(q.loc[pos,k])if k in ['season','week']else str(q.loc[pos,k]))for k in KEY+CTX}
                    row.update(arm='S0_RECENCY_ALLOCATION'if recency else'A2_DYNAMIC_ALLOCATION',mean=law['mean'],median=law['median'],
                        generation_UTC=now(),original_issued_UTC=None,source_information_max_UTC=str(q.loc[pos,'feature_max_source_available_utc']),
                        fallback='NO_QUALIFIED_PLAYER_HISTORY_ROLE_PRIOR'if not parameters['known_player_games']else None,
                        law={'kind':'finite_allocation',**parameters,'pmf':law['pmf'].tolist(),'omitted_mass_bound':law['omitted_mass_bound']})
                    forecasts.append(row)
            # Deterministic quadrature precision; no score-guided seed/draw search.
            numerical.append({'season':year,'actual_query_states':par[year]['numerical_observed'],'actual_training_states':params[year-1].get('numerical_observed')if year-1 in params else None,'rule':'41then81/161/321until both moments differ<=1e-6; every actual state checked','PASS':True})
            prepared[str(year)]=q
        if fit_count!=3:raise ValueError('registered3forestfits')
        # Re-inference of the unchanged 2026 control must match its retained points.
        fixed=next(x for x in doc('category-topfive-matched12-all-finalists-freeze-v1_2.json.gz')['extra_entries']if x.get('method')=='BACKFIELD_CDF')
        old=pd.read_parquet(io.BytesIO(pin(fixed['forecast'])));cur=pd.DataFrame([r for r in forecasts if r['season']==2026 and r['arm']=='A0_BACKFIELD_CDF'])
        match=old.merge(cur,on=KEY,suffixes=('_old','_new'),validate='one_to_one')
        if len(match)!=len(queries[2026]):raise ValueError('A0 old control coverage mismatch')
        for p in ['mean','median']:
            if not np.array_equal(match[p+'_old'].to_numpy(float),match[p+'_new'].to_numpy(float)):raise ValueError('A0 unchanged point replay mismatch')
        # Existing structured Count A mean is a point-only control, not a law
        # manufactured from a count-fitting objective. Reuse saved values.
        for rr in controls.to_dict('records'):
            row={k:int(rr[k])if k in ['season','week']else str(rr[k])for k in KEY+CTX}
            value=float(rr['prediction'])if pd.notna(rr['prediction'])else None
            row.update(arm='STORED_COUNT_A_MEAN_CONTROL',mean=value,median=None,law=None,
                fallback=str(rr['fallback'])if pd.notna(rr.get('fallback'))else None,generation_UTC=str(rr['source_issue_time_UTC'])if pd.notna(rr.get('source_issue_time_UTC'))else None,original_issued_UTC=None,
                source_information_policy=rr.get('source_information_policy'),source_forecast_sha256=rr.get('source_forecast_sha256'),
                source_information_max_UTC=None,output_procedure_version=rr['output_procedure_version'])
            forecasts.append(row)
        members.update({'FORECASTS.json.gz':gzip.compress(enc(forecasts),mtime=0),'MODEL_REFERENCES.json':enc(STATE['model_refs']),'MODEL_AUDITS.json':enc(audits),'COHERENCE.json':enc(coherence),'NUMERICAL_PRECISION.json':enc(numerical),**{f'QUERIES_{year}.parquet':parquet(q)for year,q in prepared.items()}})
        body=archive(members)
        if len(body)+sum(r['bytes']for r in STATE['model_refs'])>plan['resources']['private_retained_bytes']-1048576:raise ValueError('forecast package exceeds reserved retained envelope')
        target=destination/'FROZEN_FORECASTS_MODELS_V1.zip';store.write_bytes(target,body);store.validate_reference(target,sha(body));store.verify_retained_checkpoint()
        receipt={'run_id':VERSION,'state':'FITTED_FORECASTED_SAVED_READBACK_NOT_SCORED','artifact_id':'A-DYNAMIC-CARRY-FROZEN-V1','sha256':sha(body),'bytes':len(body),'model_objects':STATE['model_refs'],'forecast_rows':len(forecasts),'fits':fit_count,'trees':fit_count*32,'CDF_2026_restorations':1,'A0_exact_saved_point_replay_rows':len(match),'generated_UTC':now(),'persisted_UTC':now(),'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'offhost_restore':'NOT_VERIFIED','producer_source_commit':execution_source_commit,'new_pregame_issuances':0,'evidence':'CURRENT_VINTAGE_CHRONOLOGICAL_RECONSTRUCTION'}
        note('FORECAST_FREEZE_RECEIPT_V1.json',receipt);print(json.dumps(receipt));return
    receipt=json.loads((OUT/'FORECAST_FREEZE_RECEIPT_V1.json').read_text())
    path=destination/'FROZEN_FORECASTS_MODELS_V1.zip';store.validate_reference(path,receipt['sha256']);data=path.read_bytes()
    z=zipfile.ZipFile(io.BytesIO(data));forecasts=json.loads(gzip.decompress(z.read('FORECASTS.json.gz')))
    score(forecasts,store,destination,plan,np,pd)

def score(forecasts,store,destination,plan,np,pd):
    from nfl_lab import abc_dynamic_carry_v1 as core,cdf_engine as cdf
    cache=Path(os.environ.get('ABC_C_CODE_CACHE','/tmp/abc-improvement-01/C/src'))
    for ref in plan['C_bound_code']:
        if sha((cache/Path(ref['path']).name).read_bytes())!=ref['sha256']:raise ValueError('pinned C evaluator dependency changed')
    sys.path.insert(0,str(cache));import abc_championship_v2 as common
    import collections
    b,c,g,fr=sources()
    # Labels are projected only after immutable forecast readback.
    with zipfile.ZipFile(io.BytesIO(pin(g['qualified_labels'])))as z:labels=pd.read_parquet(io.BytesIO(z.read(g['qualified_labels']['member'])))
    history=pd.read_parquet(io.BytesIO(pin(b['inputs']['history'])))
    label={(int(r.season),str(r.game_id),str(r.player_id)):r for r in labels.loc[labels.target.eq('rush_att')].itertuples()}
    for r in history.loc[history.season.eq(2025)&history.week.between(1,8)&history.position.eq('RB')].itertuples():label[(2025,str(r.game_id),str(r.player_id))]=r
    def outcome(season,game,player):
        l=label.get((season,game,player))
        if l is None:return None,'UNKNOWN','MISSING_OUTCOME_RECORD'
        state=l.participation_state
        value=getattr(l,'actual',getattr(l,'rush_att',None))
        pending=getattr(l,'outcome_state',None)=='pending'
        appearance='PENDING'if pending else'DNP'if state=='DNP'else'PLAYED'if state=='played'else'UNKNOWN'
        valid=appearance=='PLAYED'and value is not None and np.isfinite(value)and value>=0 and value%1==0
        return float(value)if valid else None,appearance,getattr(l,'outcome_state','supported_played'if valid else'played_missing'if appearance=='PLAYED'else appearance)
    numeric=[];numeric_rows=[];by=collections.defaultdict(list)
    for r in forecasts:
        y,appearance,outcome_state=outcome(r['season'],r['game_id'],r['player_id'])
        r=dict(r,actual=y,participation=appearance,outcome_state=outcome_state,outcome_version=g['qualified_labels']['sha256']if r['season']==2026 else b['inputs']['history']['sha256'])
        numeric_rows.append(r);by[(r['season'],r['arm'])].append(r)
    for (year,arm),rs in sorted(by.items()):
        for week in ['ALL']+sorted({r['week']for r in rs}):
            s=[r for r in rs if week=='ALL'or r['week']==week];good=[r for r in s if r['actual']is not None]
            for product in ['mean','median']:
                scored=[r for r in good if r.get(product)is not None]
                e=np.array([r[product]-r['actual']for r in scored]);ae=np.abs(e)
                numeric.append({'season':year,'week':week,'actual_weeks':sorted({r['week']for r in s}),'arm':arm,'product':product,'expected':len(s),'scored':len(scored),'unknown_or_missing':len(s)-len(good),'unsupported_product_rows':sum(r.get(product)is None for r in s),'null_score_reason':None if len(e)else'NO_SUPPORTED_POINT_PRODUCT_ON_KNOWN_OUTCOMES','outcome_states':dict(collections.Counter(r['outcome_state']for r in s)),'games':len({r['game_id']for r in scored}),'MAE':float(ae.mean())if len(e)else None,'MSE':float((e*e).mean())if len(e)else None,'RMSE':float(np.sqrt((e*e).mean()))if len(e)else None,'bias':float(e.mean())if len(e)else None,'p95_absolute_error':float(np.quantile(ae,.95))if len(e)else None,'strict_lt1':int((ae<1).sum()),'inclusive_le1':int((ae<=1).sum()),'exact_unrounded':int((ae==0).sum()),'fractional_mean_not_rounded':True})
    with zipfile.ZipFile(io.BytesIO(pin(g['offers'])))as z:offers=pd.read_parquet(io.BytesIO(z.read(g['offers']['member'])))
    # Public frozen offering policy owns eligibility; no offer choice by outcome.
    excluded_roles=offers.loc[offers.target.eq('rush_att')&~offers.position.eq('RB')].position.value_counts().to_dict()
    offers=offers.loc[offers.target.eq('rush_att')&offers.position.eq('RB')].copy()
    if offers.duplicated(['season','game_id','player_id']).any():raise ValueError('duplicate primary opportunity')
    offer_rows=offers.to_dict('records');fmap={(r['season'],r['game_id'],r['player_id'],r['arm']):r for r in numeric_rows}
    arms=sorted({r['arm']for r in forecasts});rows=[];laws={};consistency=[]
    for o in offer_rows:
        for arm in arms+['ALWAYS_OVER','ALWAYS_UNDER']:
            f=fmap.get((int(o['season']),str(o['game_id']),str(o['player_id']),arm));line=float(o['line'])
            if f and f['law']is not None:
                law=f['law']
                if law['kind']=='leaf_cdf':
                    prior=cdf.SupportPrior(**law['prior']);batch=cdf.MixtureBatch(np.array(law['support']),np.array([law['weights']]),prior,prior_weight=law['prior_weight'])
                    pu=float(batch.cdf([math.ceil(line)-1])[0]);po=float(1-batch.cdf([math.floor(line)])[0]);ps=dict(p_under=pu,p_over=po,p_push=max(0.,1-pu-po))
                else:ps=core.event_probabilities(np.array(law['pmf']),line)
                if abs(sum(ps.values())-1)>1e-10 or min(ps.values())<0:raise ValueError('exact event mass')
                probside='ABSTAIN'if abs(ps['p_over']-ps['p_under'])<=1e-12 else'OVER'if ps['p_over']>ps['p_under']else'UNDER'
                if line%1==.5:
                    medside=common.a.point_side(f['median'],line)
                    consistency.append({'arm':arm,'same_law_direction_equal':medside==probside or probside=='ABSTAIN','probability_tie':probside=='ABSTAIN'})
                    if medside!=probside and probside!='ABSTAIN':raise ValueError('same-law median direction inconsistency')
            else:ps={k:None for k in ['p_under','p_push','p_over']};probside=None
            policies=['CONSTANT']if arm.startswith('ALWAYS_')else['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW','P2_EXACT_LAW_CONF55']
            for policy in policies:
                side=arm.removeprefix('ALWAYS_')if policy=='CONSTANT'else common.a.point_side(f[policy.removeprefix('P1_').lower()],line)if f and policy.startswith('P1_')else probside
                if side=='UNAVAILABLE':side=None
                if policy=='P2_EXACT_LAW_CONF55'and ps['p_under']is not None and ps['p_over']is not None and max(ps['p_under'],ps['p_over'])<.55:side='ABSTAIN'
                y,appearance,outcome_state=outcome(int(o['season']),str(o['game_id']),str(o['player_id']))
                state='UNAVAILABLE_FORECAST'if side is None else'ABSTAIN'if side=='ABSTAIN'else'DNP'if appearance=='DNP'else'PENDING'if appearance=='PENDING'else'UNKNOWN_PARTICIPATION'if appearance!='PLAYED'else'MISSING_ACTUAL'if y is None else'WIN'
                row={'game_id':str(o['game_id']),'player_id':str(o['player_id']),'season':int(o['season']),'week':int(o['week']),'category':'rush_att','line':line,'actual':y,'appearance':appearance,'selected_side':side,'status':state,'comparator':'STRICT_OVER_UNDER','arm':arm,'policy':policy,'point':f.get(policy.removeprefix('P1_').lower())if f and policy.startswith('P1_')else None,'fallback':f['fallback']if f else None,'unavailability_reason':'POINT_ONLY_CONTROL_HAS_NO_LAW'if f and f['law']is None and policy.startswith('P2')else'UNSUPPORTED_POINT_PRODUCT'if f and policy.startswith('P1')and f.get(policy.removeprefix('P1_').lower())is None else None,'source_stream':o['source_stream'],'opportunity_key':o['opportunity_key'],'source_sha256':o['source_sha256'],'source_quote_time':str(o['source_quote_time']),'quote_timing_status':o['quote_timing_status'],**ps}
                row['status']=common.status(row);rows.append(row)
    groups=collections.defaultdict(list)
    for r in rows:
        for week in ['ALL',r['week']]:groups[(r['arm'],r['policy'],week)].append(r)
    result=[];proper=[]
    for (arm,policy,week),rs in sorted(groups.items(),key=lambda v:str(v[0])):
        decided=[r for r in rs if r['status']in['WIN','LOSS']];pr=[r for r in decided if r['p_over']is not None and r['line']%1==.5]
        brier=float(np.mean([(r['p_over']-int(r['actual']>r['line']))**2 for r in pr]))if pr else None
        logloss=float(np.mean([-math.log(r['p_over']if r['actual']>r['line']else r['p_under'])for r in pr]))if pr else None
        result.append({'season':2026,'arm':arm,'policy':policy,'week':week,**common.summary(rs),'selected_binary_Brier_half_integer':brier,'selected_binary_logloss_half_integer':logloss,'selected_probability_scored':len(pr),'probability_missing_reason':None if pr else'NO_SUPPORTED_LAW_OR_HALF_INTEGER_DECIDED_EVENTS','evidence_tier':'CURRENT_VINTAGE_RECORDED_THRESHOLD_DIAGNOSTIC_QUOTE_AND_BOOK_SEMANTICS_UNVERIFIED'})
        if policy=='P2_EXACT_LAW':
            full=[r for r in rs if r['appearance']=='PLAYED'and r['actual']is not None and r['p_over']is not None and r['line']%1==.5]
            probs=np.array([r['p_over']for r in full]);events=np.array([int(r['actual']>r['line'])for r in full]);reliability=[]
            for lo in [0.,.2,.4,.6,.8]:
                mask=(probs>=lo)&(probs<lo+.2 if lo<.8 else probs<=1)
                reliability.append({'low':lo,'high':lo+.2,'n':int(mask.sum()),'predicted':float(probs[mask].mean())if mask.any()else None,'observed':float(events[mask].mean())if mask.any()else None})
            proper.append({'arm':arm,'week':week,'scored':len(full),'includes_probability_ties_and_policy_abstentions':True,'Brier':float(np.mean((probs-events)**2))if len(full)else None,'neutral_Brier':.25 if len(full)else None,'logloss':float(np.mean([-math.log(r['p_over']if r['actual']>r['line']else r['p_under'])for r in full]))if full else None,'reliability':reliability})
    body=archive({'NUMERICAL_ROWS.json.gz':gzip.compress(enc(numeric_rows),mtime=0),'OFFER_GRADE_ROWS.json.gz':gzip.compress(enc(rows),mtime=0)})
    target=destination/'GRADED_SCORECARD_V1.zip';store.write_bytes(target,body);store.validate_reference(target,sha(body));usage=store.verify_retained_checkpoint()
    note('NUMERICAL_RESULTS_V1.json',{'scores':numeric,'mean_and_median_are_products_not_independent_methods':True,'2025_over_under':'NO_QUALIFIED_2025_OFFER_PANEL_THIS_WAVE'})
    note('ACTUAL_LINE_RESULTS_V1.json',{'C_protocol':plan['C_protocol'],'C_scorer_sha256':plan['C_scorer_sha256'],'scores':result,'full_board_probability_scores':proper,'excluded_nonRB_offers':excluded_roles,'same_law_median_checks':{'rows':len(consistency),'passed':sum(r['same_law_direction_equal']for r in consistency),'ties':sum(r['probability_tie']for r in consistency)},'limits':['Reconstructed decisions, not originally issued selections.','Prepared full-board thresholds retain original timing/source qualification limits; venue prices/settlement unsupported.','Current2026 only here; no fabricated2025 historical odds.','New candidate roster not automatically admitted by C or production.']})
    note('SCORING_RECEIPT_V1.json',{'state':'SCORED_SAVED_READBACK','artifact_id':'A-DYNAMIC-CARRY-SCORECARD-V1','sha256':sha(body),'bytes':len(body),'score_rows':len(rows),'numeric_prediction_rows':len(numeric_rows),'method_week_output_policy_cells':len(numeric)+len(result),'new_fits':0,'scored_UTC':now(),'wave_retained_headroom_bytes':usage['wave_retained_headroom_bytes'],'offhost_restore':'NOT_VERIFIED'})
    print(json.dumps({'numeric_cells':len(numeric),'selection_cells':len(result),'grade_rows':len(rows),'private_bytes':len(body)}))

if __name__=='__main__':
    try:main()
    except BaseException as error:
        # Never recycle fit slots or discard returned models after later failures.
        import traceback,signal
        # Keep the registered hard cap; avoid repeated soft signals consuming
        # the separately reserved failure-finalization interval.
        soft,hard=resource.getrlimit(resource.RLIMIT_CPU)
        if hard==1800:resource.setrlimit(resource.RLIMIT_CPU,(hard,hard))
        signal.signal(signal.SIGXCPU,signal.SIG_IGN)
        if 'start_wall'in STATE:signal.alarm(max(1,min(100,int(2400-(time.monotonic()-STATE['start_wall'])))))
        failure={'run_id':VERSION,'state':'FAILED','phase':STATE['phase'],'error_type':type(error).__name__,'fit_attempts_consumed':STATE['fit_attempts'],'returned_fit_count':STATE['returned_fits'],'returned_models':STATE['model_refs'],'forecast_rows_so_far':len(STATE['forecasts']),'finished_UTC':now(),'automatic_retry':False,'earlier_allocations_refunded':False,'public_reason':'See exact source-bound failure witness in approved private store; no scores claimed.'}
        if 'start_wall'in STATE:failure.update(CPU_seconds=time.process_time()-STATE['start_CPU'],wall_seconds=time.monotonic()-STATE['start_wall'],RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        if STATE.get('store') and STATE['destination'].exists():
            try:
                failed_members={'FAILURE.json':enc(failure),'TRACEBACK.txt':traceback.format_exc().encode(),'FORECAST_PARTIALS.json.gz':gzip.compress(enc(STATE['forecasts']),mtime=0)}
                if STATE.get('pending_model_bytes'):failed_members['RETURNED_MODEL_WRITE_FAILED.joblib']=STATE['pending_model_bytes']
                payload=archive(failed_members)
                path=STATE['destination']/'FAILED_PARTIALS_V1.zip';STATE['store'].write_bytes(path,payload);STATE['store'].validate_reference(path,sha(payload));failure['private_failure']={'sha256':sha(payload),'bytes':len(payload),'readback':'PASS'}
            except BaseException as retention_error:failure['failure_retention_error_type']=type(retention_error).__name__
        name='PREFLIGHT_FAILURE_V1.json'if STATE.get('mode')=='preflight'else'EXECUTION_FAILURE_V1.json'
        if not (OUT/name).exists():note(name,failure)
        raise
