"""One root-authorized earlier-origin Backfield fit; retained evaluator/selector."""
from pathlib import Path
import ast, copy, hashlib, importlib.util, io, json, os, resource, signal, sys, time, traceback, zipfile

ROOT = Path('/workspace/nfl-methods-integration')
OUT = Path(__file__).resolve().parent
VERSION = 'A_BACKFIELD_CDF_ANNUAL_ORIGIN_2024_TOP6_v1'
KEY = ['season', 'week', 'game_id', 'player_id']
CAP = 15 * 1024**2
PEAK = 28 * 1024**2
META = 262144
RESERVE = 80 * 1024**2

def sha(b): return hashlib.sha256(b).hexdigest()
def clean(x):
    import numpy as np
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if isinstance(x, np.generic): return clean(x.item())
    if isinstance(x, float) and not __import__('math').isfinite(x): return None
    return x
def enc(x): return (json.dumps(clean(x), sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
def ref(p):
    p=Path(p); b=p.read_bytes(); return {'path':str(p), 'bytes':len(b), 'sha256':sha(b)}
def auth(r):
    p=Path(r['path']); b=p.read_bytes()
    assert p.resolve()==p and not p.is_symlink() and len(b)==r['bytes'] and sha(b)==r['sha256'], r['path']
    return b
def load(p, name):
    spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); sys.modules[name]=m;spec.loader.exec_module(m);return m
def note(name, value):
    b=enc(value); assert sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())+len(b)<=META, 'shared task metadata cap'
    with (OUT/name).open('xb') as f: f.write(b); f.flush();os.fsync(f.fileno())
def compressed_note(name,value):
    import gzip
    b=gzip.compress(enc(value),mtime=0);assert sum(p.stat().st_size for p in OUT.rglob('*')if p.is_file())+len(b)<=META
    with (OUT/name).open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
def main():
    go=json.loads((OUT/'RUSH_HISTORICAL_GO_V1.json').read_bytes())
    assert go['state']=='GO' and go['root']=='/root' and go['owner']=='/root/rush_top6_extension'
    assert not (OUT/'RUSH_STARTED_V1.json').exists(), 'one invocation; consumed attempts cannot retry'
    assert sys.flags.dont_write_bytecode
    start=time.monotonic(); cpu=time.process_time(); resource.setrlimit(resource.RLIMIT_CPU,(240,241))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('root-sealed 360second wall envelope')));signal.alarm(350)
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
    import importlib.metadata as md
    b=json.loads((ROOT/'config/category-topfive-backfield-v1.sealed.json').read_bytes())
    env={k:md.version(k) for k in b['environment']}; assert env==b['environment']
    pins=[ref(Path(__file__)),ref(OUT/'RUSH_HISTORICAL_GO_V1.json'),ref(ROOT/'config/category-topfive-backfield-v1.sealed.json')]
    for p,digest in [
      (ROOT/'nfl_lab/cdf_engine.py','6a963111f4173a88affe90ca1ce17532cd5eb690a1f28b284e9fa4145eecb214'),
      (ROOT/'nfl_lab/category_topfive_backfield_v1.py','d1573acc289d0851b3b9bb55f568f373f328c497af35af910ac6e224003d3fd7'),
      (ROOT/'tools/category_topfive_matched12_law_scores_v1.py','2a4754b286a81c44a34d389110624de2a5ccbbf155fd4eb6bcb27bda704d2e21'),
      (ROOT/'tools/category_topfive_matched12_law_outer_v1.py','f761c909b34cff9e44edf967ca40c8d6be0e1bf37caf938d6333dc81ba2fffa7'),
      (ROOT/'tools/category_topfive_matched12_aux_runner_v1.py','9e3e060e098acdcac67607a0a0bc0b23c4fa84ecd8716169eca3cff5c2fee8e9'),
      (ROOT/'nfl_lab/data.py','38c6fdc45d0a9d86f2a11fc334f77099d918819672ac745563e7248093ba625f'),
      (ROOT/'tools/category_topfive_original_leans_private_freeze_v1_1.py','428ba78c67100a730dc7b0f2d93fca8248b7bfb8e83c85b1835c7421144f685b')]:
        r=ref(p);assert r['sha256']==digest;pins.append(r)
    cp=OUT/'completion/C_code'
    c_protocol=json.loads((ROOT/'reports/abc-championship/predictive-improvement-01/runtime-v2/PROTOCOL_V1.json').read_bytes())
    technical=json.loads((OUT/'RUSH_TECHNICAL_PIN_GO_V1.json').read_bytes())
    assert technical['state']=='GO_TECHNICAL_PIN_CONTINUATION'and technical['root']=='/root'and technical['owner']=='/root/rush_top6_extension'
    assert technical['correction']['adopted_sha256']=='ba3cd2d5c33eb05f3c07e8f2674f6d51b51694c8fd722f8eaba5db089907997f'
    pins.append(ref(OUT/'RUSH_TECHNICAL_PIN_GO_V1.json'))
    for r in c_protocol['C_bound_code']:
        expected=technical['correction']['adopted_sha256']if Path(r['path']).name=='selection.py'else r['sha256']
        got=ref(cp/Path(r['path']).name);assert got['sha256']==expected;pins.append(got)
    hplan=json.loads((ROOT/'config/historical-market-comparison-no2025-technical-v3.sealed.json').read_bytes())
    source_refs={'history':b['inputs']['history'],'queries':hplan['historical_queries']['2024'],'labels':hplan['historical_label_inputs']['2024']['rush_att'],
      'backfield_training_container':ref(Path(b['output'])/'FORECASTS_MODELS.zip'),
      'retained_offer_forecast_container':ref(Path(hplan['output'])/'FORECASTS_FROZEN.zip')}
    raw_stats=Path(b['inputs']['history']['path']).parent.parent/'sources/stats_player_week_2024.parquet'
    source_refs['explicit_2024_stat_presence']=ref(raw_stats)
    assert source_refs['explicit_2024_stat_presence']['sha256']=='847569d194ca3d96b5efcf91e6eac5e18780fc47568a713fd545a82d29d155c1'
    pins.append(ref(ROOT/'reports/abc-championship/audit-remediation-20261105/HISTORY_IMPACT_SCOPE_CORRECTION_V7.json'))
    assert source_refs['backfield_training_container']['sha256']=='1d16502dfa02c32d2d32446a9866f277bfd7ff78a78b82c4326af1718a720854'
    # Authenticate every source before the one fit; no existing model is loaded.
    source_bytes={k:auth(v) for k,v in source_refs.items()}
    binding={'version':VERSION,'origin':'annual2024; exact separate extension, not literal fixed2026 artifact','root_GO_sha256':pins[1]['sha256'],'worker':pins[0],
      'code':pins[2:],'environment':env,'sources':source_refs,'training_filter':'season<2024; known outcome_available<2024-09-01UTC; original REG rows',
      'scope':'W1-8 primary; W1-18 REG secondary; all original offered roles;7day current-vintage reconstruction; quote clocks unverified',
      'fit_budget':1,'CPU_seconds':240,'wall_seconds':360,'RSS_bytes':1073741824,'private_retained_bytes':CAP,'private_peak_bytes':PEAK,'HTTP':0,'retries':0}
    note('RUSH_PREFIT_BINDINGS_V1.json',binding)
    note('RUSH_STARTED_V1.json',{'state':'ONE_INVOCATION_CONSUMED','UTC':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'binding_sha256':sha(enc(binding)),'fits':0})
    fits=0; writes=[]; third=None; fourth=None; destination=None
    def usage(): return {'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'fits':fits,'private_writes':writes,'HTTP':0,'retries':0}
    def check():
        u=usage();assert u['RSS_bytes']<=1073741824 and u['CPU_seconds']<235 and u['wall_seconds']<345,u
    try:
        import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq,joblib
        pa.set_cpu_count(1);pa.set_io_thread_count(1)
        sys.path.insert(0,str(ROOT));sys.path.insert(0,str(cp))
        from nfl_lab import cdf_engine as cdf,category_topfive_backfield_v1 as bf,data
        import abc_championship_v2 as common
        loss=load(ROOT/'tools/category_topfive_matched12_law_scores_v1.py','rush_history_loss')
        aux=load(ROOT/'tools/category_topfive_matched12_aux_runner_v1.py','rush_history_aux')
        writer=load(ROOT/'tools/category_topfive_original_leans_private_freeze_v1_1.py','rush_history_writer')
        storage=load(ROOT/'tools/category_topfive_matched12_storage_v1.py','rush_history_storage')
        fourth,_=storage.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=storage.GO,readonly=True)
        third=writer.storage(ROOT);destination=third.live_root/'research'/'backfield-annual2024-top6-v1-20261112'
        assert not destination.exists()
        with third.transaction():
            fourth._refresh();fourth._require(PEAK+META);third._refresh();before=third._require(RESERVE+PEAK+META);third.register_root(destination)
        def put(name,body):
            check();assert sum(r['bytes']for r in writes)+len(body)+65536<=CAP
            r={'path':str(destination/name),'bytes':len(body),'sha256':sha(body)}
            writes.append(r) # charge a failed attempted write, too
            with third.transaction():
                fourth._refresh();fourth._require(PEAK+META);third._refresh();third._require(RESERVE+PEAK+META)
                third.write_bytes(destination/name,body);got=third.validate_reference(destination/name,r['sha256']);assert all(got[k]==r[k]for k in r)
                assert (destination/name).read_bytes()==body
                fourth._refresh();fourth._require(META);third._refresh();third._require(RESERVE+META)
            return r
        def parq(f):
            f=f.copy();f.attrs.clear();s=io.BytesIO();f.to_parquet(s,index=False,compression='zstd');return s.getvalue()
        def cap(members):
            s=io.BytesIO()
            with zipfile.ZipFile(s,'w',compression=zipfile.ZIP_STORED)as z:
                for n,raw in sorted(members.items()):z.writestr(n,raw)
            return s.getvalue()
        with zipfile.ZipFile(io.BytesIO(source_bytes['backfield_training_container']))as z:
            train_bytes=z.read('PREPARED_TRAIN.parquet');assert sha(train_bytes)=='37e77dc416b05aacf8184f9501f404e5744fac71953c5be370871242e623ba6f'
            train=pd.read_parquet(io.BytesIO(train_bytes))
        train=train.loc[train.season.lt(2024)&(pd.to_datetime(train.outcome_available_utc,utc=True)<pd.Timestamp('2024-09-01',tz='UTC'))].copy()
        assert len(train)==42561 and sorted(train.season.unique())==[2019,2020,2021,2022,2023]
        cdf.assert_clock_contract(train)
        history=pd.read_parquet(io.BytesIO(source_bytes['history']))
        history=history.loc[history.season.le(2024)].copy()
        assert not history.duplicated(['game_id','player_id']).any() and history[['game_id','player_id','team','position']].notna().all(axis=None)
        assert history.player_id.str.fullmatch(r'00-\d{7}').all()
        for col in ['kickoff_utc','outcome_available_utc']:
            history[col]=pd.to_datetime(history[col],utc=True,errors='raise');assert history[col].notna().all()
        assert (history.outcome_available_utc-history.kickoff_utc).eq(pd.Timedelta(days=7)).all()
        for key in ['player_id','team']:
            ordered=history.sort_values([key,'outcome_available_utc','game_id','player_id'],kind='stable')
            assert not ordered.groupby(key).kickoff_utc.diff().dt.total_seconds().lt(0).any()
        with zipfile.ZipFile(io.BytesIO(source_bytes['retained_offer_forecast_container']))as z:
            offers=pd.read_parquet(io.BytesIO(z.read('ALL_CANONICAL_OFFERED_POOL.parquet')))
            retained=pd.read_parquet(io.BytesIO(z.read('EVALUATION_FORECASTS.parquet')))
        offers=offers.loc[offers.season.eq(2024)&offers.week.between(1,18)&offers.target.eq('rush_att')].copy()
        offers['_book_priority']=offers.book_id.map({68:0,69:1,79:2});assert offers._book_priority.notna().all()
        offers=offers.sort_values('_book_priority',kind='stable').drop_duplicates(KEY+['target']).reset_index(drop=True)
        assert len(offers)==1140 and int(offers.week.le(8).sum())==529
        offers['offer_id']=np.arange(len(offers))
        query=pd.read_parquet(io.BytesIO(source_bytes['queries']))
        q=offers[KEY+['offer_id','team','opponent','position','kickoff_utc']].merge(query,on=KEY,how='left',suffixes=('_offer',''),validate='one_to_one',indicator=True)
        valid=q._merge.eq('both')
        for k in ['team','opponent','position','kickoff_utc']:valid&=q[k].eq(q[k+'_offer'])
        assert int(valid.sum())==1139 and valid.loc[q.week.le(8)].all()
        q=q.loc[valid,list(query.columns)+['offer_id']].copy();q['participation_state']='unknown';q['outcome_available_utc']=pd.NaT
        assert 'rush_att'not in q and 'actual'not in q
        cdf.assert_clock_contract(q);q=bf.augment(q,history);cdf.assert_clock_contract(q)
        # One deterministic target/future-outcome mutation of this newly executing block.
        tiny=q.head(1).drop(columns=bf.COLUMNS+['backfield_feature_max_available_utc']).copy()
        altered=history.copy();altered.loc[altered.kickoff_utc.ge(tiny.cutoff_utc.iloc[0]),'rush_att']=999
        pd.testing.assert_frame_equal(bf.augment(tiny,history)[bf.COLUMNS],bf.augment(tiny,altered)[bf.COLUMNS],check_exact=True)
        category=copy.deepcopy(b['categories']['rush_att']);category['panels']['context']=category['panels']['base']+b['added_columns']['rush_att']
        assert cdf.TREE_PARAMETERS==b['tree_parameters'] and cdf.PRIOR_WEIGHT==.05
        train_digest=sha(pd.util.hash_pandas_object(train,index=True).to_numpy().astype('<u8').tobytes())
        note('RUSH_FIT_START_V1.json',{'state':'ONE_FIT_ATTEMPT_CONSUMED','training_rows':len(train),'training_frame_values_sha256':train_digest,'category':category,'source_audit':{'history_rows':len(history),'unknown_clocks':0,'identity_or_order_failures':0,'policy':'seven-day reconstruction; not authenticated publication'},'query_rows':len(q),'offer_rows':len(offers),'usage':usage()})
        check();fits=1;model=cdf.LeafCDFModel.fit(train,category,'context');assert model.forest is not None
        # Returned parameters are durably retained before any target inference.
        s=io.BytesIO();joblib.dump(model,s,compress=3);model_bytes=s.getvalue()
        model_ref=put('MODEL.zip',cap({'model.joblib':model_bytes,'BINDING.json':enc({'version':VERSION,'training_frame_values_sha256':train_digest,'audit':model.audit,'model_member_sha256':sha(model_bytes),'binding_sha256':sha(enc(binding))})}))
        note('RUSH_MODEL_READBACK_V1.json',{'state':'RETURNED_MODEL_DURABLY_READ_BACK','reference':model_ref,'model_member_sha256':sha(model_bytes),'usage':usage()})
        assert model.design.names==category['panels']['context']
        with zipfile.ZipFile(io.BytesIO(auth(model_ref)))as z:restored_bytes=z.read('model.joblib')
        assert sha(restored_bytes)==sha(model_bytes)
        restored=joblib.load(io.BytesIO(restored_bytes)) # our just-produced, hash-bound trusted model only
        def fixture_predictions(m,sample):
            values=[]
            for at,law,reason in m.predict_batches(sample,batch_size=2):
                assert law is not None
                part=sample.iloc[at];L=offers.set_index('offer_id').loc[part.offer_id].line.to_numpy()
                event=loss.threshold_probabilities(law,L)
                for j,oid in enumerate(part.offer_id):values.append([int(oid),float(law.mean[j]),*event['probabilities'][j].tolist()])
            return np.asarray(sorted(values,key=lambda r:r[0]))
        fixture=q.head(3).copy();expected=fixture_predictions(model,fixture)
        np.testing.assert_allclose(fixture_predictions(restored,fixture.iloc[::-1]),expected,atol=1e-12,rtol=0)
        singles=np.concatenate([fixture_predictions(restored,fixture.iloc[[i]])for i in range(len(fixture))]);singles=singles[np.argsort(singles[:,0])]
        np.testing.assert_allclose(singles,expected,atol=1e-12,rtol=0)
        note('RUSH_INFERENCE_CHECKS_V1.json',{'state':'PASS_SCOPE_CHECKED','own_model_restoration':1,'fixture_rows':len(fixture),'single_batch_shuffled_max_tolerance':1e-12,'feature_order':'exact named sealed columns','future_target_outcome_backfield_mutation':'PASS_ONE_DETERMINISTIC_QUERY','new_additional_fits':0})
        del restored,restored_bytes
        # Law inference uses the original normalized-cumulative helper, not point inference.
        preds=[]
        for positions,law,fallback in model.predict_batches(q,batch_size=128):
            if law is None:continue
            sub=q.iloc[positions];off=offers.set_index('offer_id').loc[sub.offer_id]
            events=loss.threshold_probabilities(law,off.line.to_numpy());choice=loss.select_sides(events)
            for i,(_,r)in enumerate(sub.iterrows()):
                preds.append({**{k:r[k]for k in KEY},'offer_id':int(r.offer_id),'position':r.position,'cutoff_utc':r.cutoff_utc,'feature_max_source_available_utc':r.feature_max_source_available_utc,'mean':float(law.mean[i]),'median':float(law.quantile(.5)[i]),'p_under':float(events['probabilities'][i,0]),'p_push':float(events['probabilities'][i,1]),'p_over':float(events['probabilities'][i,2]),'log_p_under':float(events['log_probabilities'][i,0]),'log_p_push':float(events['log_probabilities'][i,1]),'log_p_over':float(events['log_probabilities'][i,2]),'side':str(choice['side'][i]),'confidence':float(choice['decisive_confidence'][i]),'fallback':str(fallback[i])})
        pred=pd.DataFrame(preds);assert len(pred)==1139 and not pred.duplicated(KEY).any()
        frozen_ref=put('FORECASTS.zip',cap({'FORECASTS.parquet':parq(pred),'OFFERS.parquet':parq(offers),'QUERY_FEATURES.parquet':parq(q),'MANIFEST.json':enc({'version':VERSION,'model':model_ref,'code':pins,'source_refs':source_refs,'no_original_issuance':True,'quote_clock':'UNVERIFIED','timing':'seven-day reconstruction'})}))
        note('RUSH_FORECAST_FREEZE_V1.json',{'state':'EXACT_FORECAST_AND_OFFER_BYTES_FROZEN_BEFORE_LABEL_JOIN','reference':frozen_ref,'predicted':len(pred),'eligible':len(offers),'usage':usage()})
        labels=pd.read_parquet(io.BytesIO(source_bytes['labels']))
        assert not labels.duplicated(KEY).any()
        rawstat=pd.read_parquet(io.BytesIO(source_bytes['explicit_2024_stat_presence']),columns=['season','week','player_id','game_id','team','carries','season_type'])
        rawstat=rawstat.loc[rawstat.season_type.eq('REG')].copy();rawstat['team']=data._team(rawstat.team)
        assert not rawstat.duplicated(['season','week','player_id']).any()
        labelproof=labels.merge(rawstat,on=['season','week','player_id'],how='left',suffixes=('','_raw'),validate='one_to_one')
        known=labelproof.participation_state.eq('played')&labelproof.actual.notna()
        assert labelproof.loc[known,'carries'].notna().all()
        assert labelproof.loc[known,'actual'].eq(labelproof.loc[known,'carries']).all()
        assert labelproof.loc[known,'game_id'].eq(labelproof.loc[known,'game_id_raw']).all()
        assert labelproof.loc[known,'team'].eq(labelproof.loc[known,'team_raw']).all()
        presence_proof={'known_labels_with_explicit_raw_stat':int(known.sum()),'explicit_raw_zeros':int((known&labelproof.actual.eq(0)&labelproof.carries.eq(0)).sum()),'unsupported_zero_fills':0,'unknown_labels_retained':int((~known).sum()),'team_alias':'pinned data._team; LA->LAR; no fuzzy/player alias','source_sha256':source_refs['explicit_2024_stat_presence']['sha256']}
        panel=offers.merge(labels[KEY+['actual','participation_state','outcome_state']],on=KEY,how='left',validate='one_to_one')
        frame=panel.merge(pred.drop(columns=['position']),on=KEY+['offer_id'],how='left',validate='one_to_one')
        frame['side']=frame.side.fillna('unavailable');frame['fallback']=frame.fallback.fillna('UNAVAILABLE_QUERY_CONTEXT')
        # Extract exactly the original two Top-k statements from the pinned selector AST.
        tree=ast.parse((ROOT/'tools/category_topfive_matched12_law_outer_v1.py').read_text());fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name=='selectors')
        outerloop=next(x for x in fn.body if isinstance(x,ast.For));kloop=next(x for x in outerloop.body if isinstance(x,ast.For)and isinstance(x.target,ast.Name)and x.target.id=='k')
        assert isinstance(kloop.body[0],ast.Assign)and isinstance(kloop.body[1],ast.Assign)
        select_code=compile(ast.Module(body=kloop.body[:2],type_ignores=[]),'<pinned exact selector statements>','exec')
        def selected(g):
            ns={'g':g,'k':6,'views':{}};exec(select_code,ns);return ns['views']['TOP_6_PER_CATEGORY_WEEK']
        def common_rows(f,sidecol='side'):
            rr=[]
            for r in f.to_dict('records'):
                y=r.get('actual');state=r.get('participation_state');known=state=='played'and y is not None and np.isfinite(y)and y>=0 and y%1==0
                side=r.get(sidecol);side=None if side is None or pd.isna(side)or side=='unavailable'else str(side).upper()
                appearance='PLAYED'if state=='played'else'DNP'if state in['DNP','dnp']else'UNKNOWN'
                row={'season':2024,'week':int(r['week']),'game_id':r['game_id'],'player_id':r['player_id'],'category':'rush_att','line':float(r['line']),'actual':float(y)if known else None,'appearance':appearance,'selected_side':side,'comparator':'STRICT_OVER_UNDER','status':'UNAVAILABLE_FORECAST'if side is None else'ABSTAIN'if side=='ABSTAIN'else'DNP'if appearance=='DNP'else'UNKNOWN_PARTICIPATION'if appearance!='PLAYED'else'MISSING_ACTUAL'if not known else'WIN'}
                row['status']=common.status(row);rr.append(row)
            return rr
        def summarize(f,sidecol='side',fallbackcol='fallback'):
            rows=common_rows(f,sidecol);s=common.summary(rows);s['fallback_selected']=int(f.loc[f[sidecol].isin(['over','under']),fallbackcol].fillna('').ne('').sum())if fallbackcol and fallbackcol in f else None
            s['fallback_provenance']='own retained reason'if fallbackcol else'NOT_ESTABLISHED_FOR_THIS_CONTROL;candidate mask contribution reported separately'
            s['role_counts']=f.position.value_counts().to_dict();s['supported_scored_weeks']=sorted({r['week']for r in rows if r['status']in['WIN','LOSS']});return s
        def interval(v,g):return aux._interval(v,g,{'minimum_clusters':2,'replicates':1000,'seed':20261030})
        # Exact saved strong controls retain their own source/model contracts.
        retained=retained.loc[retained.season.eq(2024)&retained.target.eq('rush_att')]
        control_columns=['book_id','line','F_over','F_under','F_push','F_probability','F_point','F_mean','F_fallback','F_model_year','FC_point','FC_probability','FS_probability','H_point','H_probability','M_point','M_probability']
        ctr=offers[KEY+['book_id','line']].merge(retained[KEY+control_columns],on=KEY+['book_id','line'],how='left',validate='one_to_one')
        frame=frame.merge(ctr.drop(columns=['book_id','line']),on=KEY,how='left',validate='one_to_one')
        controls={}
        for name,col in [('F_SAVED_POINT','F_point'),('F_MEAN','F_mean'),('FC_SAVED_POINT','FC_point'),('H_SAVED_POINT','H_point'),('MARKET_POINT','M_point')]:
            controls[name]=[common.a.point_side(x,L).lower()if pd.notna(x)else'unavailable'for x,L in zip(frame[col],frame.line)]
        for name,col in [('F_PROBABILITY','F_probability'),('FC_PROBABILITY','FC_probability'),('FS_PROBABILITY','FS_probability'),('H_PROBABILITY','H_probability'),('MARKET_PROBABILITY','M_probability')]:
            controls[name]=['unavailable'if pd.isna(x)else'abstain'if x==.5 else'over'if x>.5 else'under'for x in frame[col]]
        controls['ALWAYS_OVER']=['over']*len(frame);controls['ALWAYS_UNDER']=['under']*len(frame)
        for name,v in controls.items():frame[name]=v
        records=[];pairs=[];metrics=[]
        for label,mask in [('2024_W1_8',frame.week.le(8)),('2024_FULL_REG',frame.week.le(18))]:
            g=frame.loc[mask].copy();top=selected(g)
            records.append({'period':label,'product':'BACKFIELD_CDF_P2_TOP6','summary':summarize(top),'eligible_board':len(g),'available_forecasts':int(g.side.ne('unavailable').sum()),'unavailable_forecasts':int(g.side.eq('unavailable').sum()),'selected_role_counts':top.position.value_counts().to_dict(),'selected_own_fallback':top.fallback.value_counts().to_dict(),'weekly':[{'week':int(w),'summary':summarize(top.loc[top.week.eq(w)]),'eligible':int(g.week.eq(w).sum()),'available':int((g.week.eq(w)&g.side.ne('unavailable')).sum())}for w in sorted(g.week.unique())]})
            records.append({'period':label,'product':'BACKFIELD_CDF_P2_FULL_BOARD','summary':summarize(g)})
            for role in sorted(g.position.unique()):records.append({'period':label,'product':'TOP6_SELECTED_ROLE_'+role,'summary':summarize(top.loc[top.position.eq(role)])})
            for name in controls:
                records.append({'period':label,'product':name+'_ON_CANDIDATE_TOP6','summary':summarize(top,name,'F_fallback'if name in ['F_SAVED_POINT','F_MEAN','F_PROBABILITY']else None)})
                a=common_rows(top);bb=common_rows(top,name);ix=[i for i in range(len(a))if a[i]['status']in['WIN','LOSS']and bb[i]['status']in['WIN','LOSS']]
                dif=np.asarray([int(a[i]['status']=='WIN')-int(bb[i]['status']=='WIN')for i in ix]);pairs.append({'period':label,'control':name,'common_selected_decided':len(ix),'candidate_wins':sum(a[i]['status']=='WIN'for i in ix),'control_wins':sum(bb[i]['status']=='WIN'for i in ix),'side_disagreements':sum(a[i]['selected_side']!=bb[i]['selected_side']for i in ix),'win_difference':int(dif.sum()),'paired_game':interval(dif,[a[i]['game_id']for i in ix]),'paired_week':interval(dif,[a[i]['week']for i in ix])})
            fprob=g.copy();fprob['side']=fprob['F_PROBABILITY'];fprob['confidence']=np.maximum(fprob.F_probability,1-fprob.F_probability);fprob['fallback']=fprob.F_fallback.fillna('UNAVAILABLE_RETAINED_CONTROL')
            records.append({'period':label,'product':'F_RETAINED_PROBABILITY_OWN_TOP6','summary':summarize(selected(fprob)),'eligible_board':len(g)})
            for mask_name,table in [('OFFERED_BOARD',g),('CANDIDATE_TOP6',top)]:
                good=table.participation_state.eq('played')&table.actual.notna()&table.actual.ge(0)&table.actual.mod(1).eq(0)
                nrec={'period':label,'mask':mask_name,'numeric':{}}
                for product in ['mean','median','F_mean','F_point','FC_point','H_point','M_point']:
                    z=table.loc[good&table[product].notna()];error=z[product].to_numpy(float)-z.actual.to_numpy(float)
                    nrec['numeric'][product]={'scored':len(z),'MAE':float(np.abs(error).mean())if len(z)else None,'MSE':float(np.square(error).mean())if len(z)else None,'bias':float(error.mean())if len(z)else None}
                z=table.loc[good&table.p_over.notna()];logs=z[['log_p_under','log_p_push','log_p_over']].to_numpy(float)
                from decimal import Decimal
                events={'probabilities':z[['p_under','p_push','p_over']].to_numpy(float),'log_probabilities':logs,'line_ticks':np.asarray([Decimal(str(v))for v in z.line],dtype=object),'scale':1,'contract':None,'support':'count'}
                if len(z):
                    ps=loss.threshold_scores(events,z.actual.to_numpy(float));nrec['exact_law_probability']={'scored':len(z),'half_three_outcome_Brier':loss.loss_summary(ps['Brier']),'log_loss':loss.loss_summary(ps['log_loss']),'decisive_conditional_Brier':loss.loss_summary(ps['decisive_conditional_Brier'][ps['decisive_conditional_available']])}
                metrics.append(nrec)
        # Save complete versioned grades/masks, retaining unknown and unavailable rows.
        result={'version':VERSION,'state':'EXECUTED_ONE_ANNUAL_FIT_AND_FROZEN_REPLAY','model':model_ref,'forecasts':frozen_ref,'training_rows':len(train),'training_seasons':[2019,2020,2021,2022,2023],'training_known_played_rows':model.audit['supported_played_training_rows'],'training_played_missing':model.audit['played_missing_outcome'],
          'records':records,'paired_controls':pairs,'numerical_and_probability_metrics':metrics,'raw_stat_presence_proof':presence_proof,'evidence_tier':'EXPOSED_CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION_ACTUAL_LINES_QUOTE_TIME_UNVERIFIED','original_issued_forecasts':0,'new_original_NFL_games':0,'newly_evaluated_procedure_weeks':list(range(1,19)),'Top6_weekly_timing':'Future-in-week simultaneity not authenticated; retrospective diagnostic only','query_population':'Offer-derived universe with retained origin query feature intersection; no authenticated pregame roster claim','operational_decision':'SHADOW_RESEARCH_ONLY;NO_PRIMARY_PROMOTION_FROM_THIS_REPLAY','limitations':['One conditional historical season; original offered-role policy includes QB and RB','No probabilities or full law inferred for point-only controls','Saved F/FC/FS/H/market controls retain distinct football/line/market-assistance contracts; no exact original website incumbent history claimed','2025 origin A0 evidence not relabeled as2024 or given invented offers'],'usage':usage()}
        grade_ref=put('GRADES.zip',cap({'ROWS.parquet':parq(frame),'RESULTS.json':enc(result),'SELECTED_MEMBERS.parquet':parq(selected(frame))}))
        result['grade_receipt']=grade_ref;result['usage']=usage()
        compressed_note('RUSH_HISTORICAL_RESULTS_V1.json.gz',result)
        note('RUSH_COMPLETE_V1.json',{'state':'COMPLETE_FIT_INFERENCE_FROZEN_GRADED_AND_LOCAL_READBACK','version':VERSION,'model':model_ref,'forecasts':frozen_ref,'grades':grade_ref,'usage':usage(),'no_primary_switch':True})
        signal.alarm(0);print(enc({'state':'COMPLETE','result':str(OUT/'RUSH_HISTORICAL_RESULTS_V1.json.gz'),'model':model_ref,'forecasts':frozen_ref,'grades':grade_ref,'usage':usage()}).decode(),flush=True)
    except BaseException as exc:
        failure={'state':'FAILED_PRESERVED_NO_RETRY','version':VERSION,'exception_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'usage':usage(),'returned_model_preserved':any(r['path'].endswith('MODEL.zip')for r in writes)}
        try:note('RUSH_FAILED_V1.json',failure)
        finally:signal.alarm(0)
        print(enc(failure).decode(),flush=True);raise

if __name__=='__main__':main()
