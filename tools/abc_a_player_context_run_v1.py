"""Finite A-owned context continuation; original C scorer and private A store."""
from __future__ import annotations
import argparse,copy,datetime,gzip,hashlib,io,json,os,resource,sys,time,traceback,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'reports/abc-championship/player-context-matchup-01'
STATE={'phase':'START','fits_attempted':0,'fits_returned':0,'artifacts':[],'forecasts':[]}
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def note(name,obj):
    p=OUT/name
    with p.open('xb')as f:f.write(enc(obj));f.flush();os.fsync(f.fileno())
def event(kind,**kwargs):
    with(OUT/'RUN_EVENTS_V1.jsonl').open('ab')as f:f.write(enc(dict(UTC=now(),kind=kind,**kwargs)));f.flush();os.fsync(f.fileno())
def setup():
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='1'
    import numpy as np,pandas as pd,pyarrow as pa,joblib
    pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
    from nfl_lab import abc_player_rushing_context_v1 as context,abc_dynamic_carry_v1 as dynamic,cdf_engine as cdf
    from tools import abc_a_dynamic_carry_wave_v1 as base,category_topfive_matched12_storage_v1 as storage
    return np,pd,joblib,context,dynamic,cdf,base,storage
def sources(base,pd):
    d=base.doc('role-count-full-pbp2024-recovery-gate-network-v2.json')
    r24={'path':str(Path(d['output'])/'FULL_PBP2024.parquet'),'bytes':d['asset']['expected_bytes'],'sha256':d['asset']['expected_sha256']}
    r26=base.doc('category-topfive-matched12-current-label-execute-v1.json.gz')['pbp']
    from nfl_lab import abc_player_rushing_context_v1 as context
    frames=[]
    for year,ref in [(2024,r24),(2026,r26)]:
        df=pd.read_parquet(io.BytesIO(base.pin(ref)),columns=context.COLS)
        df=df.loc[df.season_type.eq('REG')&((df.week<=7)if year==2026 else True)].copy()
        frames.append(df)
    return frames
def inputs():
    np,pd,joblib,context,dynamic,cdf,base,storage=setup()
    b,c,g,fr,z,train,history,qq=base.inputs(pd)
    records=dynamic.compile_history(history)
    train,_,_=dynamic.augment(train,records);q,_,_=dynamic.augment(qq[2026],records)
    ctx=context.Context(sources(base,pd),history)
    return (np,pd,joblib,context,dynamic,cdf,base,storage),(b,c,g,fr,z,train,history,q,ctx)
def choose_window():
    resource.setrlimit(resource.RLIMIT_CPU,(180,190))
    start=time.monotonic();libs,data=inputs();np,pd,_,context,*_=libs;ctx=data[-1]
    # Component-only earlier validation. Actual context is a label, never a query feature.
    rows=[]
    for player,rs in ctx.players.items():
        for r in rs:
            if r['season']!=2024 or not 5<=r['week']<=8 or r['role']!='RB' or not r['attempts']:continue
            cut=r['kickoff']-pd.Timedelta(hours=1)
            if not context.eligible(rs,cut,1):continue
            for w in [4,8,16]:
                f,_=ctx.features(player,r['team'],r['opponent'],cut,w)
                ix=[i for i,(group,value)in enumerate(context.LABELS)if group=='location']
                p=np.array([f[context.OWN[i]]for i in ix]);counts=r['mix'][ix]
                rows.append(dict(window=w,week=r['week'],game=r['game'],n=int(counts.sum()),nll=float(-np.dot(counts,np.log(p)))))
    scores=[]
    for w in [4,8,16]:
        rr=[r for r in rows if r['window']==w]
        scores.append(dict(window=w,player_games=len(rr),games=len({r['game']for r in rr}),carries=sum(r['n']for r in rr),
          nll_per_carry=sum(r['nll']for r in rr)/sum(r['n']for r in rr)if rr else None))
    rank={8:0,4:1,16:2}
    best=min(scores,key=lambda r:(round(r['nll_per_carry'],12)if r['nll_per_carry']is not None else float('inf'),rank[r['window']]))['window']
    note('EARLIER_COMPONENT_WINDOW_V1.json',dict(state='EARLIER_COMPONENT_VALIDATION_EXECUTED',selected_window=best,
       period='2024 W5-8 conditional on supported carries and at least one eligible context appearance',scores=scores,
       tie_rule='equal to 12decimal NLL:8 then4 then16',new_final_stat_fits=0,prop_accuracy_cells=0,
       evidence='CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION_EXPOSED_DEVELOPMENT',wall_seconds=time.monotonic()-start))
    print(json.dumps({'selected_window':best,'scores':scores}),flush=True)
def run(plan_sha):
    start=time.monotonic();cpu=time.process_time();STATE.update(start=start,cpu=cpu)
    planraw=(OUT/'FIT_PROTOCOL_V1.json').read_bytes();assert sha(planraw)==plan_sha
    plan=json.loads(planraw)
    for name,digest in plan['code_sha256'].items():assert sha((ROOT/name).read_bytes())==digest
    assert json.loads((OUT/'FIT_PUBLICATION_V1.json').read_text())['state']=='PUBLICATION_COMPLETE'
    resource.setrlimit(resource.RLIMIT_CPU,(1200,1300))
    resource.setrlimit(resource.RLIMIT_AS,(plan['resources']['RSS_bytes'],)*2)
    import signal
    signal.signal(signal.SIGXCPU,lambda *_:(_ for _ in()).throw(TimeoutError('fit CPU budget')))
    libs,data=inputs();np,pd,joblib,context,dynamic,cdf,base,storage=libs
    b,c,g,fr,z,train,history,q,ctx=data
    window=json.loads((OUT/'EARLIER_COMPONENT_WINDOW_V1.json').read_text())['selected_window']
    store,_=storage.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=storage.GO)
    dest=store.forward_root/'research/PLAYER-CONTEXT-MATCHUP-01-A-v1'
    assert not dest.exists();store.register_root(dest);STATE.update(store=store,destination=dest)
    with store.transaction():store._refresh();store._require(plan['resources']['private_peak_bytes'])
    event('START',protocol_sha256=plan_sha,new_fit_budget=5,source_HTTP=0,private_peak_bytes=plan['resources']['private_peak_bytes'])
    oldroot=store.forward_root/'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
    raw=base.pin({'path':str(oldroot/'MODEL_2026_A1.joblib'),'bytes':2316296,'sha256':'e48f750893984c4d4395d399075458c52be83ba02bbbbc0615866e378de4f659'})
    e0=joblib.load(io.BytesIO(raw));category=copy.deepcopy(e0.category)
    def persist(name,body):
        if sum(r['bytes']for r in STATE['artifacts'])+len(body)>plan['resources']['private_peak_bytes']:
            raise ValueError('registered package private-byte ceiling; inherited cap unchanged')
        store.write_bytes(dest/name,body);store.validate_reference(dest/name,sha(body))
        ref=dict(id=name,bytes=len(body),sha256=sha(body));STATE['artifacts'].append(ref);return ref
    def compact(m,name):
        # Retain the returned unique inference state BEFORE optional audit/parity checks.
        cp=copy.copy(m)
        for k in ['training_binding','prior_training_binding','training_leaf_ids']:setattr(cp,k,None)
        s=io.BytesIO();joblib.dump(cp,s,compress=3);body=s.getvalue();STATE['pending_model_bytes']=body
        binding={k:None for k in ['training_binding','prior_training_binding','training_leaf_ids']}
        from tools.abc_a_player_context_prepare_v1 import frame_ref
        derivation=dict(training=frame_ref(m.training_binding),prior_training=frame_ref(m.prior_training_binding),
          leaf_ids_sha256=sha(m.training_leaf_ids.tobytes()),leaf_ids_shape=list(m.training_leaf_ids.shape),
          recipe='Exact saved source/member+augmented-feature table; same ordered supported/modeled filter; fitted design transform and forest.apply.astype(int32)',
          source_hashes={'frozen_prepared':fr['sha256'],'context_features':'CONTEXT_FEATURES.parquet in private capsule'})
        ref=persist(name,body);rr=joblib.load(io.BytesIO((dest/name).read_bytes()))
        for (i,a,fa),(j,bb,fb)in zip(m.predict_batches(q),rr.predict_batches(q)):
            for x,y in [(i,j),(a.support,bb.support),(a.weights,bb.weights),(a.mean,bb.mean),(a.quantile(.5),bb.quantile(.5)),(a.variance,bb.variance),(fa,fb)]:np.testing.assert_array_equal(x,y)
        STATE.pop('pending_model_bytes',None);STATE.pop('pending_model_object',None)
        return dict(**ref,bindings=derivation,local_durable_restore_parity=True)
    # Keep output-preserving compact control as a recoverable inference-adapter proof.
    modelrefs={'E0':compact(e0,'MODEL_E0_COMPACT.joblib')}
    oldcaps=base.pin({'path':str(oldroot/'FAILED_PARTIALS_V2.zip'),'bytes':4829248,'sha256':'91121673a47289098f764978fec2cba74b2d156299a1223ea21ce307da5bc208'})
    with zipfile.ZipFile(io.BytesIO(oldcaps))as zz:
        cached=json.loads(gzip.decompress(zz.read('FORECAST_PARTIALS.json.gz')))
    control=[dict(r,arm='E0_A1_UNCHANGED')for r in cached if r['season']==2026 and r['arm']=='A1_BACKFIELD_CDF_ROLE_INPUTS']
    assert len(control)==len(q)==1244
    STATE['forecasts'].extend(control)
    direct=[dict(r,arm='S_DIRECT_BACKFIELD_UNCHANGED')for r in cached if r['season']==2026 and r['arm']=='A0_BACKFIELD_CDF']
    assert len(direct)==1244;STATE['forecasts'].extend(direct)
    a3ref=json.loads((ROOT/'reports/abc-championship/post-wave-5w-v1/A3_FORECAST_FREEZE_V1.json').read_bytes())
    a3raw=base.pin({'path':str(oldroot/'POST_WAVE_A3_FORECASTS_V1.json.gz'),'bytes':a3ref['bytes'],'sha256':a3ref['sha256']})
    structured=[dict(r,arm='S_STRUCTURED_A3_UNCHANGED',law={'kind':'finite_allocation',**r['law']})for r in json.loads(gzip.decompress(a3raw))['forecasts']if r['season']==2026]
    assert len(structured)==1244;STATE['forecasts'].extend(structured)
    source_q=q.copy()
    train=ctx.augment(train,window);q=ctx.augment(q,window)
    cdf.assert_clock_contract(train);cdf.assert_clock_contract(q)
    altered=source_q.iloc[:32].copy();altered['rush_att']=9999.;altered['actual_targets']=7777.;altered['realized_team_carries']=8888.
    probe=ctx.augment(altered,window)
    pd.testing.assert_frame_equal(q.iloc[:32][context.OWN+context.DEF+context.INTER],probe[context.OWN+context.DEF+context.INTER],check_exact=True)
    for group in context.GROUPS:
        fields=[context.OWN[i]for i,(k,v)in enumerate(context.LABELS)if k==group]
        np.testing.assert_allclose(q[fields].sum(axis=1).to_numpy(),np.ones(len(q)),rtol=0,atol=1e-12)
    note('FEATURE_ADMISSION_V1.json',dict(state='PASS_BEFORE_FITS',query_rows=len(q),target_outcome_mutations_ignored=32,
      context_source_games=len(ctx.source_games),withheld_future_source_games=len(ctx.withheld_future_source_games),
      context_clock_policy='Explicit earlier history only; W7 future target PBP not treated as admitted past; no unknown clock fill',
      query_context_supported=int(q.f_pcm_games.gt(0).sum()),query_context_missing=int(q.f_pcm_games.eq(0).sum()),
      query_context_age_days={'median':float(q.f_pcm_age_days.median()),'maximum':float(q.f_pcm_age_days.max())},
      context_mixtures_conserved=True,source_team_other_bucket='All positions preserved; team total minus retained player is other. Direct marginal CDF does not claim joint player-allocation conservation.'))
    mask=(train.season<2026)&(pd.to_datetime(train.outcome_available_utc,utc=True)<pd.Timestamp('2026-09-01',tz='UTC'))
    tr=train.loc[mask].copy()
    features=base.parquet(pd.concat([train[base.KEY+context.OWN+context.DEF+context.INTER],q[base.KEY+context.OWN+context.DEF+context.INTER]],ignore_index=True))
    feature_ref=persist('CONTEXT_FEATURES.parquet',features)
    for arm,names in [('E1_OWN_CONTEXT',context.OWN),('E2_OPP_MAIN',context.OWN+context.DEF),('E3_CONTEXT_INTERACTION',context.OWN+context.DEF+context.INTER)]:
        if sum(r['bytes']for r in STATE['artifacts'])+1450000>plan['resources']['private_peak_bytes']:
            raise ValueError('before-fit model750000 plus failure700000 reservation unavailable')
        cat=copy.deepcopy(category);cat['panels']['context']+=names
        STATE['phase']='FIT_'+arm;STATE['fits_attempted']+=1;event('FIT_ATTEMPT',arm=arm,slot=STATE['fits_attempted'])
        m=cdf.LeafCDFModel.fit(tr,cat,'context');STATE['fits_returned']+=1
        STATE['pending_model_object']=m
        modelrefs[arm]=compact(m,'MODEL_'+arm+'.joblib')
        assert m.audit['role_priors']==e0.audit['role_priors']
        STATE['forecasts'].extend(base.cdf_forecasts(m,q,arm,np))
        event('FIT_INFERENCE_SAVED',arm=arm,forecast_rows=len(q),model=modelrefs[arm]['sha256'])
    # Same-context pooled/partially-pooled contrast. No invented outcome law.
    from sklearn.preprocessing import StandardScaler,OneHotEncoder
    from sklearn.linear_model import Ridge
    from scipy import sparse
    names=category['panels']['context']+context.OWN+context.DEF
    modeled=tr.loc[tr.position.eq('RB')&tr.participation_state.eq('played')&cdf.valid_support(cdf.numeric(tr,'rush_att'),'count')]
    design=cdf.FixedDesign.fit(modeled,names);scale=StandardScaler().fit(design.transform(modeled))
    x=scale.transform(design.transform(modeled));xq=scale.transform(design.transform(q));y=cdf.numeric(modeled,'rush_att')
    vectors={}
    for arm in ['P1_POOLED_RIDGE','P2_PARTIAL_PLAYER_TEAM_RIDGE']:
        if sum(r['bytes']for r in STATE['artifacts'])+950000>plan['resources']['private_peak_bytes']:
            raise ValueError('before-fit linear250000 plus failure700000 reservation unavailable')
        STATE['phase']='FIT_'+arm;STATE['fits_attempted']+=1;event('FIT_ATTEMPT',arm=arm,slot=STATE['fits_attempted'])
        xx,qq_=x,xq;onehot=None
        if arm.startswith('P2'):
            onehot=OneHotEncoder(handle_unknown='ignore',sparse_output=True,dtype=np.float64)
            xx=sparse.hstack([sparse.csr_matrix(x),onehot.fit_transform(modeled[['player_id','team','opponent']].astype(str))]).tocsr()
            qq_=sparse.hstack([sparse.csr_matrix(xq),onehot.transform(q[['player_id','team','opponent']].astype(str))]).tocsr()
        m=Ridge(alpha=32.,solver='lsqr',tol=1e-8,max_iter=2000).fit(xx,y);STATE['fits_returned']+=1
        STATE['pending_model_object']=dict(design=design,scale=scale,onehot=onehot,model=m,point_contract='nonnegative regression point; probability/median unsupported')
        s=io.BytesIO();joblib.dump(STATE['pending_model_object'],s,compress=3);STATE['pending_model_bytes']=s.getvalue()
        modelrefs[arm]=persist('MODEL_'+arm+'.joblib',s.getvalue())
        STATE.pop('pending_model_bytes',None);STATE.pop('pending_model_object',None)
        pred=np.maximum(0.,m.predict(qq_));vectors[arm]=pred
        for j,r in enumerate(q.itertuples()):
            row={k:int(getattr(r,k))if k in ['season','week']else str(getattr(r,k))for k in base.KEY+base.CTX}
            row.update(arm=arm,mean=float(pred[j]),median=None,law=None,fallback=None,point_type='REGRESSION_POINT_NOT_A_DISTRIBUTION_EXPECTATION',
              generation_UTC=now(),original_issued_UTC=None,source_information_max_UTC=str(r.feature_max_source_available_utc))
            STATE['forecasts'].append(row)
    # Genuine no-pooling comparator on predeclared supported players; full-system fallback explicit.
    hh=history.loc[history.participation_state.eq('played')&cdf.valid_support(cdf.numeric(history,'rush_att'),'count')]
    byplayer={str(k):v for k,v in hh.groupby('player_id')}
    for j,r in enumerate(q.itertuples()):
        old=byplayer.get(str(r.player_id),hh.iloc[:0]);cut=pd.to_datetime(r.cutoff_utc,utc=True)
        old=old.loc[pd.to_datetime(old.outcome_available_utc,utc=True).notna()&(pd.to_datetime(old.outcome_available_utc,utc=True)<cut)]
        old=old.sort_values(['kickoff_utc','game_id'],kind='stable').tail(8)
        point=float(old.rush_att.mean())if len(old)==8 else float(vectors['P1_POOLED_RIDGE'][j])
        row={k:int(getattr(r,k))if k in ['season','week']else str(getattr(r,k))for k in base.KEY+base.CTX}
        row.update(arm='P3_PLAYER_ONLY_8_WITH_P1_FALLBACK',mean=point,median=None,law=None,
          fallback=None if len(old)==8 else'FEWER_THAN_8_SUPPORTED_PRIOR_APPEARANCES_P1_FALLBACK',player_only_support=len(old),
          generation_UTC=now(),original_issued_UTC=None,source_information_max_UTC=str(r.feature_max_source_available_utc))
        STATE['forecasts'].append(row)
    assert STATE['fits_attempted']==STATE['fits_returned']==5
    forecasts=STATE['forecasts'];body=base.archive({'FORECASTS.json.gz':gzip.compress(enc([r for r in forecasts if not r['arm'].startswith(('E0_','S_'))]),mtime=0),
      'REUSED_FORECAST_BINDINGS.json':enc({'original_capsule_sha256':'91121673a47289098f764978fec2cba74b2d156299a1223ea21ce307da5bc208',
        'original_member':'FORECAST_PARTIALS.json.gz','A3_original_sha256':a3ref['sha256'],'copied_control_rows':3732,
        'mapping':{'A1_BACKFIELD_CDF_ROLE_INPUTS':'E0_A1_UNCHANGED','A0_BACKFIELD_CDF':'S_DIRECT_BACKFIELD_UNCHANGED','A3_CONDITIONAL_PLAYED_EXPOSURE':'S_STRUCTURED_A3_UNCHANGED'},
        'A3_law_adapter':'Only add kind=finite_allocation for existing common scorer; probabilities/PMF/points unchanged'}),
      'MODEL_BINDINGS.json':enc(modelrefs),
      'PROTOCOL.json':planraw,'COMPONENT_WINDOW.json':(OUT/'EARLIER_COMPONENT_WINDOW_V1.json').read_bytes()})
    forecast_ref=persist('FORECAST_CAPSULE_V1.zip',body)
    STATE['forecasts_durable']=True
    event('IMMUTABLE_FORECASTS_READBACK_BEFORE_GRADING',artifact=forecast_ref,rows=len(forecasts))
    # Reuse the existing C-bound grader. Factor repeated laws out of the scorecard only.
    base.OUT=OUT
    original_archive=base.archive
    def score_archive(members):
        for name in ['NUMERICAL_ROWS.json.gz']:
            if name in members:
                rr=json.loads(gzip.decompress(members[name]))
                for row in rr:
                    row.pop('law',None);row['law_reference']=forecast_ref['sha256']
                members[name]=gzip.compress(enc(rr),mtime=0)
        if 'OFFER_GRADE_ROWS.json.gz'in members:
            rr=json.loads(gzip.decompress(members['OFFER_GRADE_ROWS.json.gz']))
            for row in rr:
                if row['arm'].startswith(('P1_','P2_','P3_'))and row['policy']=='P1_MEAN':row['policy']='P1_OTHER_POINT'
            members['OFFER_GRADE_ROWS.json.gz']=gzip.compress(enc(rr),mtime=0)
        return original_archive(members)
    base.archive=score_archive
    original_note=base.note
    def typed_note(name,obj):
        for row in obj.get('scores',[]):
            if row.get('arm','').startswith(('P1_','P2_','P3_')):
                row['point_contract']='REGRESSION_OR_PLAYER_HISTORY_POINT; NO_PREDICTIVE_LAW_OR_EXPECTATION_CLAIM'
                if row.get('product')=='mean':row['product']='other_point'
                if row.get('policy')=='P1_MEAN':row['policy']='P1_OTHER_POINT'
        original_note(name,obj)
    base.note=typed_note
    # Existing scorer's write goes through the same smaller package envelope.
    class BoundedScoreStore:
        def write_bytes(self,path,body):
            if sum(r['bytes']for r in STATE['artifacts'])+len(body)>plan['resources']['private_peak_bytes']:
                raise ValueError('scorecard exceeds registered package envelope')
            store.write_bytes(path,body)
            STATE['artifacts'].append(dict(id=Path(path).name,bytes=len(body),sha256=sha(body)))
        def __getattr__(self,name):return getattr(store,name)
    base.score(forecasts,BoundedScoreStore(),dest,plan,np,pd)
    usage=store.verify_retained_checkpoint()
    result=dict(state='EXECUTED_SAVED_READBACK',fits_attempted=5,fits_returned=5,forecast_rows=len(forecasts),
      forecasts=forecast_ref,model_refs=modelrefs,context_features=feature_ref,actual_weeks=sorted(q.week.unique().tolist()),
      CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
      private_artifacts=STATE['artifacts'],remaining_wave_bytes=usage['wave_retained_headroom_bytes'],new_current_queries=0,
      original_game_issuance='NONE_HISTORICAL_RECONSTRUCTION',C_admission='NOT_OBSERVED',production_changed=False)
    note('EXECUTION_RECEIPT_V1.json',result);event('COMPLETE',fits=5,forecast_rows=len(forecasts));print(json.dumps(result),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['choose-window','run'],required=True);ap.add_argument('--protocol-sha256');a=ap.parse_args()
    try:
        if a.mode=='choose-window':choose_window()
        else:run(a.protocol_sha256)
    except BaseException as e:
        fail={k:v for k,v in STATE.items()if k not in ['store','destination','forecasts','start','cpu','pending_model_bytes','pending_model_object']}
        fail.update(state='FAILED_NO_AUTOMATIC_RETRY',error_type=type(e).__name__,UTC=now(),forecast_rows=len(STATE['forecasts']))
        if STATE.get('store')and STATE.get('destination'):
            try:
                members={'FAILURE.json':enc(fail),'TRACEBACK.txt':traceback.format_exc().encode(),
                  'FORECAST_PARTIALS.json.gz':gzip.compress(enc([]if STATE.get('forecasts_durable')else[r for r in STATE['forecasts']if not r['arm'].startswith(('E0_','S_'))]),mtime=0)}
                if STATE.get('pending_model_bytes'):members['RETURNED_PENDING_MODEL.joblib']=STATE['pending_model_bytes']
                elif STATE.get('pending_model_object')is not None:
                    import joblib
                    obj=copy.copy(STATE['pending_model_object'])
                    if not isinstance(obj,dict):
                        for k in ['training_binding','prior_training_binding','training_leaf_ids']:setattr(obj,k,None)
                    ss=io.BytesIO();joblib.dump(obj,ss,compress=3);members['RETURNED_PENDING_MODEL.joblib']=ss.getvalue()
                from tools.abc_a_dynamic_carry_wave_v1 import archive
                payload=archive(members);p=STATE['destination']/'FAILED_PARTIALS_V1.zip'
                if sum(r['bytes']for r in STATE['artifacts'])+len(payload)>3500000:raise ValueError('failure reserve exhausted; preserve exact allocation dependency')
                STATE['store'].write_bytes(p,payload);STATE['store'].validate_reference(p,sha(payload))
                fail['private_failure']={'bytes':len(payload),'sha256':sha(payload)}
            except BaseException as retention_error:
                fail['failure_retention_error_type']=type(retention_error).__name__
        seq=1
        while (OUT/('FAILURE_'+a.mode.replace('-','_')+'_V'+str(seq)+'.json')).exists():seq+=1
        note('FAILURE_'+a.mode.replace('-','_')+'_V'+str(seq)+'.json',fail)
        raise
