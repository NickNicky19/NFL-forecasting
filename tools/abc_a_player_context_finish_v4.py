"""Resume saved A context vectors, fit only remaining partial-pool slot, C-score.

The relational scorecard serializer changes storage representation only. All
directions, statuses, summaries and probabilities use the bound existing scorer.
"""
from __future__ import annotations
import argparse,datetime,gzip,hashlib,io,json,lzma,os,resource,sys,time,traceback,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'reports/abc-championship/player-context-matchup-01/completion-v4'
STATE={'fits_attempted':0,'fits_returned':0,'artifacts':[],'forecasts':[],'phase':'START'}
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def note(n,x):
    with(OUT/n).open('xb')as f:f.write(enc(x));f.flush();os.fsync(f.fileno())
def freeze_archive(members):
    members=dict(members);members['MEMBER_MANIFEST.json']=enc({k:dict(bytes=len(v),sha256=sha(v))for k,v in members.items()})
    s=io.BytesIO()
    with zipfile.ZipFile(s,'w',zipfile.ZIP_DEFLATED)as z:
        for k,v in sorted(members.items()):z.writestr(k,v)
    return s.getvalue()
def compact_scorecard(members,bindings):
    """Exact relational factorization, including original field values/types."""
    numeric=json.loads(gzip.decompress(members['NUMERICAL_ROWS.json.gz']))
    offers=json.loads(gzip.decompress(members['OFFER_GRADE_ROWS.json.gz']))
    key=lambda r:(r['season'],r['week'],r['game_id'],r['player_id'])
    actuals={};nkeys=[];nindex={}
    for r in numeric:
        k=key(r);a={f:r.get(f)for f in ['actual','participation','outcome_state','outcome_version']}
        if k in actuals and actuals[k]!=a:raise ValueError('numerical labels differ across methods')
        if k not in nindex:nindex[k]=len(nkeys);nkeys.append(list(k));actuals[k]=a
    universe=[];uindex={};decisions={}
    shared=['game_id','player_id','season','week','category','line','actual','appearance','comparator',
      'source_stream','opportunity_key','source_sha256','source_quote_time','quote_timing_status']
    varying=['selected_side','status','point','fallback','unavailability_reason','p_under','p_push','p_over']
    for r in offers:
        k=r['opportunity_key'];u={f:r.get(f)for f in shared}
        if k not in uindex:uindex[k]=len(universe);universe.append(u)
        elif universe[uindex[k]]!=u:raise ValueError('offered event/label differs across methods')
        policy='P1_OTHER_POINT'if r['arm'].startswith(('P1_','P2_','P3_','R1_','R3_'))and r['policy']=='P1_MEAN'else r['policy']
        group=(r['arm'],policy)
        if group not in decisions:decisions[group]={'arm':group[0],'policy':group[1],'opportunities':[],**{f:[]for f in varying}}
        d=decisions[group];d['opportunities'].append(uindex[k])
        for f in varying:d[f].append(r.get(f))
    doc=dict(schema='A-PCM01-relational-scorecard-v1',numeric_keys=nkeys,
      numeric_actuals=[actuals[tuple(k)]for k in nkeys],numeric_forecasts='Exact immutable per-arm files bound below; all mean/median/fallback/clocks remain in those files',
      forecast_bindings=bindings,offer_universe=universe,decision_groups=list(decisions.values()),
      original_numeric_row_count=len(numeric),original_offer_row_count=len(offers),
      reconstruction='Zip offer universe by decision opportunity index, then varying arrays; numerical keys/actuals join exact arm forecast on season/week/game/player. No scorer/calculation changed.')
    raw=enc(doc);s=io.BytesIO()
    with zipfile.ZipFile(s,'w',zipfile.ZIP_LZMA)as z:
        z.writestr('RELATIONAL_SCORECARD.json',raw)
        z.writestr('MEMBER_MANIFEST.json',enc({'RELATIONAL_SCORECARD.json':dict(bytes=len(raw),sha256=sha(raw))}))
    return s.getvalue()
def run(digest):
    start=time.monotonic();cpu=time.process_time();rawplan=(OUT/'PROTOCOL_V4.json').read_bytes();assert sha(rawplan)==digest
    plan=json.loads(rawplan)
    for p,d in plan['code_sha256'].items():assert sha((ROOT/p).read_bytes())==d
    assert json.loads((OUT/'PUBLICATION_V4.json').read_text())['state']=='PUBLICATION_COMPLETE'
    resource.setrlimit(resource.RLIMIT_CPU,(500,600));resource.setrlimit(resource.RLIMIT_AS,(3221225472,)*2)
    for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
    import numpy as np,pandas as pd,joblib,pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
    from nfl_lab import abc_dynamic_carry_v1 as dynamic,cdf_engine as cdf,abc_player_rushing_context_v1 as ctx
    from tools import abc_a_dynamic_carry_wave_v1 as base,category_topfive_matched12_storage_v1 as storage
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.linear_model import Ridge
    from scipy import sparse
    store,_=storage.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=storage.GO)
    dest=store.forward_root/'research/PLAYER-CONTEXT-MATCHUP-01-A-completion-v4'
    assert not dest.exists();store.register_root(dest);STATE.update(store=store,dest=dest)
    with store.transaction():store._refresh();store._require(plan['resources']['private_peak_bytes'])
    def persist(n,b):
        if sum(r['bytes']for r in STATE['artifacts'])+len(b)>plan['resources']['private_peak_bytes']:raise ValueError('completion190000byte envelope')
        store.write_bytes(dest/n,b);store.validate_reference(dest/n,sha(b));r=dict(id=n,bytes=len(b),sha256=sha(b));STATE['artifacts'].append(r);return r
    note('START_V4.json',dict(UTC=now(),protocol_sha256=digest,new_fit_budget=1,already_returned_preserved_fits=4))
    old=store.forward_root/'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
    root3=store.forward_root/'research/PLAYER-CONTEXT-MATCHUP-01-A-runtime-v3'
    refs=plan['retained_v3_forecasts'];forecasts=STATE['forecasts'];bindings={}
    for ref in refs:
        r=json.loads(lzma.decompress(base.pin({'path':str(root3/ref['id']),**{k:ref[k]for k in ['bytes','sha256']}})))
        forecasts+=r;bindings[r[0]['arm']]=dict(container='RetainedV3',**ref)
    partials=base.pin({'path':str(old/'FAILED_PARTIALS_V2.zip'),'bytes':4829248,'sha256':'91121673a47289098f764978fec2cba74b2d156299a1223ea21ce307da5bc208'})
    with zipfile.ZipFile(io.BytesIO(partials))as z:cached=json.loads(gzip.decompress(z.read('FORECAST_PARTIALS.json.gz')))
    for original,arm in [('A1_BACKFIELD_CDF_ROLE_INPUTS','E0_A1_UNCHANGED'),('A0_BACKFIELD_CDF','S_DIRECT_BACKFIELD_UNCHANGED')]:
        forecasts.extend(dict(r,arm=arm)for r in cached if r['season']==2026 and r['arm']==original)
        bindings[arm]=dict(container_sha256='91121673a47289098f764978fec2cba74b2d156299a1223ea21ce307da5bc208',member='FORECAST_PARTIALS.json.gz',original_arm=original,season=2026)
    a3=json.loads((ROOT/'reports/abc-championship/post-wave-5w-v1/A3_FORECAST_FREEZE_V1.json').read_bytes())
    a3data=json.loads(gzip.decompress(base.pin({'path':str(old/'POST_WAVE_A3_FORECASTS_V1.json.gz'),'bytes':a3['bytes'],'sha256':a3['sha256']})))
    forecasts.extend(dict(r,arm='S_STRUCTURED_A3_UNCHANGED',law={'kind':'finite_allocation',**r['law']})for r in a3data['forecasts']if r['season']==2026)
    bindings['S_STRUCTURED_A3_UNCHANGED']=dict(container_sha256=a3['sha256'],original_arm='A3_CONDITIONAL_PLAYED_EXPOSURE',season=2026)
    b,c,g,fr,z,train,history,qq=base.inputs(pd)
    records=dynamic.compile_history(history);train,_,_=dynamic.augment(train,records);q,_,_=dynamic.augment(qq[2026],records)
    featref=plan['retained_context_features'];fb=base.pin({'path':str(store.forward_root/'research/PLAYER-CONTEXT-MATCHUP-01-A-v1/CONTEXT_FEATURES.parquet'),**featref})
    features=pd.read_parquet(io.BytesIO(fb));assert not features.duplicated(base.KEY).any()
    for name,frame in [('train',train),('query',q)]:
        merged=frame.merge(features,on=base.KEY,how='left',sort=False,validate='one_to_one',indicator=True)
        assert merged['_merge'].eq('both').all();merged.drop(columns='_merge',inplace=True)
        if name=='train':train=merged
        else:q=merged
    mask=(train.season<2026)&(pd.to_datetime(train.outcome_available_utc,utc=True)<pd.Timestamp('2026-09-01',tz='UTC'))
    tr=train.loc[mask];modeled=tr.loc[tr.position.eq('RB')&tr.participation_state.eq('played')&cdf.valid_support(cdf.numeric(tr,'rush_att'),'count')]
    mref=plan['retained_P1_model'];p1=joblib.load(io.BytesIO(base.pin({'path':str(root3/mref['id']),**{k:mref[k]for k in ['bytes','sha256']}})))
    assert p1['point_contract']=='nonnegative regression point; probability/median unsupported'
    design,scale=p1['design'],p1['scale']
    y=cdf.numeric(modeled,'rush_att');x=scale.transform(design.transform(modeled));xq=scale.transform(design.transform(q))
    oldp1={tuple(r[k]for k in base.KEY):r for r in forecasts if r['arm']=='P1_POOLED_RIDGE'}
    restored=np.maximum(0.,p1['model'].predict(xq))
    np.testing.assert_allclose(restored,np.array([oldp1[tuple(row)]["mean"]for row in q[base.KEY].itertuples(index=False,name=None)]),rtol=0,atol=1e-12)
    for i,row in enumerate(q.itertuples()):q.loc[i,'feature_max_source_available_utc']=pd.Timestamp(oldp1[(int(row.season),int(row.week),str(row.game_id),str(row.player_id))]['source_information_max_UTC'])
    assert sum(r['bytes']for r in STATE['artifacts'])+130000<=plan['resources']['private_peak_bytes']
    onehot=OneHotEncoder(handle_unknown='ignore',sparse_output=True,dtype=np.float64)
    xx=sparse.hstack([sparse.csr_matrix(x),onehot.fit_transform(modeled[['player_id','team','opponent']].astype(str))]).tocsr()
    xq=sparse.hstack([sparse.csr_matrix(xq),onehot.transform(q[['player_id','team','opponent']].astype(str))]).tocsr()
    STATE.update(phase='FIT_P2',fits_attempted=1)
    note('FIT_ATTEMPT_V4.json',dict(UTC=now(),slot=5,cumulative_previous_fits=4,arm='P2_PARTIAL_PLAYER_TEAM_RIDGE'))
    model=Ridge(alpha=32.,solver='lsqr',tol=1e-8,max_iter=2000).fit(xx,y);STATE['fits_returned']=1
    obj=dict(design=design,scale=scale,onehot=onehot,model=model,point_contract='nonnegative regression point; probability/median unsupported');STATE['pending_object']=obj
    s=io.BytesIO();joblib.dump(obj,s,compress=('xz',3));STATE['pending_model']=s.getvalue();modelref=persist('MODEL_P2.joblib',s.getvalue());STATE.pop('pending_model');STATE.pop('pending_object')
    points=np.maximum(0.,model.predict(xq));generated=[]
    for i,r in enumerate(q.itertuples()):
        row={k:int(getattr(r,k))if k in ['season','week']else str(getattr(r,k))for k in base.KEY+base.CTX}
        row.update(arm='P2_PARTIAL_PLAYER_TEAM_RIDGE',mean=float(points[i]),median=None,law=None,fallback=None,point_type='REGRESSION_POINT_NOT_A_DISTRIBUTION_EXPECTATION',generation_UTC=now(),original_issued_UTC=None,source_information_max_UTC=str(r.feature_max_source_available_utc));generated.append(row)
    ref=persist('FORECAST_P2.json.xz',lzma.compress(enc(generated),preset=3));bindings['P2_PARTIAL_PLAYER_TEAM_RIDGE']=ref;forecasts+=generated
    played=history.loc[history.participation_state.eq('played')&cdf.valid_support(cdf.numeric(history,'rush_att'),'count')]
    players={str(k):v for k,v in played.groupby('player_id')};generated=[]
    for r in q.itertuples():
        h=players.get(str(r.player_id),played.iloc[:0]);cut=pd.to_datetime(r.cutoff_utc,utc=True)
        h=h.loc[pd.to_datetime(h.outcome_available_utc,utc=True).notna()&(pd.to_datetime(h.outcome_available_utc,utc=True)<cut)].sort_values(['kickoff_utc','game_id'],kind='stable').tail(8)
        row={k:int(getattr(r,k))if k in ['season','week']else str(getattr(r,k))for k in base.KEY+base.CTX}
        row.update(arm='P3_PLAYER_ONLY_8_WITH_P1_FALLBACK',mean=float(h.rush_att.mean())if len(h)==8 else oldp1[tuple(row[k]for k in base.KEY)]['mean'],median=None,law=None,fallback=None if len(h)==8 else'FEWER_THAN_8_SUPPORTED_PRIOR_APPEARANCES_P1_FALLBACK',player_only_support=len(h),generation_UTC=now(),original_issued_UTC=None,source_information_max_UTC=str(r.feature_max_source_available_utc));generated.append(row)
    ref=persist('FORECAST_P3.json.xz',lzma.compress(enc(generated),preset=3));bindings['P3_PLAYER_ONLY_8_WITH_P1_FALLBACK']=ref;forecasts+=generated
    manifest=persist('FORECAST_BINDINGS.json',enc(bindings));note('FORECAST_FREEZE_V4.json',dict(state='ALL_NEW_AND_REUSED_VECTORS_READBACK_BEFORE_GRADING',UTC=now(),rows=len(forecasts),new_fit_rows=1244,new_player_only_rule_rows=1244,reused_saved_forecasts=len(forecasts)-2488,source_bindings=manifest))
    base.OUT=OUT;original_note=base.note
    def typed_note(n,doc):
        for r in doc.get('scores',[]):
            if r.get('arm','').startswith(('P1_','P2_','P3_','R1_','R3_')):
                if r.get('product')=='mean':r['product']='other_point'
                if r.get('policy')=='P1_MEAN':r['policy']='P1_OTHER_POINT'
        original_note(n,doc)
    base.note=typed_note;base.archive=lambda members:compact_scorecard(members,bindings)
    class ScoreStore:
        def write_bytes(self,p,b):persist(Path(p).name,b)
        def __getattr__(self,n):return getattr(store,n)
    base.score(forecasts,ScoreStore(),dest,plan,np,pd)
    usage=store.verify_retained_checkpoint()
    note('EXECUTION_RECEIPT_V4.json',dict(state='COMPLETE_SCORING_SAVED_READBACK',new_fits=1,cumulative_new_fits=5,reused_returned_CDF_fits=1,
      expected_queries=1244,forecast_rows=len(forecasts),new_forecasts_this_resume=2488,model=modelref,private_artifacts=STATE['artifacts'],
      CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
      wave_retained_headroom_bytes=usage['wave_retained_headroom_bytes'],C_admission='NOT_OBSERVED',website_changed=False,new_pregame_captures=0))
    print(json.dumps({'state':'COMPLETE','fits_this_resume':1,'fits_cumulative':5,'forecast_rows':len(forecasts),'private_bytes_this_resume':sum(r['bytes']for r in STATE['artifacts'])}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--protocol-sha256',required=True);a=p.parse_args()
    try:run(a.protocol_sha256)
    except BaseException as e:
        failure={k:v for k,v in STATE.items()if k not in ['store','dest','forecasts','pending_model','pending_object']};failure.update(state='FAILED',error_type=type(e).__name__,UTC=now())
        try:
            m={'FAILURE.json':enc(failure),'TRACEBACK.txt':traceback.format_exc().encode()}
            if STATE.get('pending_model'):m['PENDING_MODEL.joblib']=STATE['pending_model']
            elif STATE.get('pending_object'):
                import joblib
                stream=io.BytesIO();joblib.dump(STATE['pending_object'],stream,compress=3);m['PENDING_MODEL.joblib']=stream.getvalue()
            b=freeze_archive(m)
            if sum(r['bytes']for r in STATE['artifacts'])+len(b)>190000:raise ValueError('preserve original completion budget')
            if STATE.get('store'):
                z=STATE['dest']/'FAILED_V4.zip';STATE['store'].write_bytes(z,b);STATE['store'].validate_reference(z,sha(b));failure['private_failure']=dict(bytes=len(b),sha256=sha(b))
        except BaseException as re:failure['retention_error_type']=type(re).__name__
        note('FAILURE_V4.json',failure);raise
