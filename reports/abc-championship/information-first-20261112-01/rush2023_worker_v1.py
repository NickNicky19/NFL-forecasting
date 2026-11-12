"""One root-authorized earlier-origin Backfield fit; retained evaluator/selector."""
from pathlib import Path
import ast, copy, hashlib, importlib.util, io, json, os, resource, signal, sys, time, traceback, zipfile

ROOT = Path('/workspace/nfl-methods-integration')
OUT = Path(__file__).resolve().parent
VERSION = 'A_BACKFIELD_CDF_ANNUAL_ORIGIN_2023_TOP6_v1'
KEY = ['season', 'week', 'game_id', 'player_id']
CAP = 15 * 1024**2
PEAK = 24 * 1024**2
META = 262144
ALL_META = 2 * META
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
    raw=(OUT/'RUSH2023_PROPOSAL_V1.json').read_bytes();proposal=json.loads(raw)
    go=json.loads((OUT/'RUSH2023_GO_V1.json').read_bytes())
    assert go['state']=='ROOT_AND_INDEPENDENT_GO'and go['root']=='/root'and go['owner']=='/root/rush_top6_extension'
    assert go['worker_sha256']==ref(Path(__file__))['sha256']and go['proposal_sha256']==sha(raw)and go['public_readback_verified']is True
    assert not(OUT/'RUSH2023_STARTED_V1.json').exists(),'one invocation; no automatic retry'
    assert sys.flags.dont_write_bytecode
    start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(240,241))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('root-sealed360second envelope')));signal.alarm(350)
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
    import importlib.metadata as md
    b=json.loads(auth(proposal['recipe']))
    env={k:md.version(k)for k in b['environment']};assert env==proposal['environment']==b['environment']
    pins=[ref(Path(__file__)),ref(OUT/'RUSH2023_GO_V1.json'),ref(OUT/'RUSH2023_PROPOSAL_V1.json')]
    for r in proposal['code_bindings']:auth(r);pins.append(r)
    cp=Path(proposal['C_code_directory'])
    source_refs=proposal['sources'];source_bytes={k:auth(v)for k,v in source_refs.items()}
    binding={'version':VERSION,'origin':'annual2023 extension of unchangedBackfield recipe; no2024/2026 parameters transferred','worker':pins[0],'code':pins[1:],'environment':env,'sources':source_refs,'training_filter':'2019..2022 REG; known availability<2023-09-01UTC','scope':'W1-9primary; all2023REGsecondary; actualweeks determined beforelabels','evidence_tier':proposal['evidence_tier'],'budget':proposal['budget']}
    note('RUSH2023_PREFIT_BINDINGS_V1.json',binding)
    note('RUSH2023_STARTED_V1.json',{'state':'ONE_INVOCATION_CONSUMED','UTC':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'binding_sha256':sha(enc(binding)),'fits':0})
    fits=0; writes=[]; third=None; fourth=None; destination=None
    def usage(): return {'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'fits':fits,'private_writes':writes,'HTTP':0,'retries':0}
    def check():
        u=usage();assert u['RSS_bytes']<=1073741824 and u['CPU_seconds']<235 and u['wall_seconds']<345,u
    try:
        import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq,joblib
        pa.set_cpu_count(1);pa.set_io_thread_count(1)
        sys.path.insert(0,str(ROOT));sys.path.insert(0,str(cp))
        from nfl_lab import cdf_engine as cdf,category_topfive_backfield_v1 as bf,data
        from nfl_lab.historical_market_comparison import pair_and_canonicalize,primary_offers
        import abc_championship_v2 as common
        loss=load(ROOT/'tools/category_topfive_matched12_law_scores_v1.py','rush_history_loss')
        aux=load(ROOT/'tools/category_topfive_matched12_aux_runner_v1.py','rush_history_aux')
        writer=load(ROOT/'tools/category_topfive_original_leans_private_freeze_v1_1.py','rush_history_writer')
        storage=load(ROOT/'tools/category_topfive_matched12_storage_v1.py','rush_history_storage')
        fourth,_=storage.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=storage.GO,readonly=True)
        third=writer.storage(ROOT);destination=third.live_root/'research'/'backfield-annual2023-top6-v1-20261112'
        assert not destination.exists()
        with third.transaction():
            fourth._refresh();fourth._require(PEAK+ALL_META);third._refresh();before=third._require(RESERVE+PEAK+ALL_META);third.register_root(destination)
        def put(name,body):
            check();assert sum(r['bytes']for r in writes)+len(body)+65536<=CAP
            assert sum(r['bytes']for r in writes)+2*len(body)+65536<=PEAK,'actual staging plus retained bytes exceed narrowed peak'
            r={'path':str(destination/name),'bytes':len(body),'sha256':sha(body)}
            writes.append(r) # charge a failed attempted write, too
            with third.transaction():
                fourth._refresh();fourth._require(PEAK+ALL_META);third._refresh();third._require(RESERVE+PEAK+ALL_META)
                third.write_bytes(destination/name,body);got=third.validate_reference(destination/name,r['sha256']);assert all(got[k]==r[k]for k in r)
                assert (destination/name).read_bytes()==body
                fourth._refresh();fourth._require(ALL_META);third._refresh();third._require(RESERVE+ALL_META)
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
        train=train.loc[train.season.lt(2023)&(pd.to_datetime(train.outcome_available_utc,utc=True)<pd.Timestamp('2023-09-01',tz='UTC'))].copy()
        assert len(train)==33955 and sorted(train.season.unique())==[2019,2020,2021,2022]
        cdf.assert_clock_contract(train)
        history=pd.read_parquet(io.BytesIO(source_bytes['history']))
        history=history.loc[history.season.le(2023)].copy()
        assert not history.duplicated(['game_id','player_id']).any() and history[['game_id','player_id','team','position']].notna().all(axis=None)
        assert history.player_id.str.fullmatch(r'00-\d{7}').all()
        for col in ['kickoff_utc','outcome_available_utc']:
            history[col]=pd.to_datetime(history[col],utc=True,errors='raise');assert history[col].notna().all()
        assert (history.outcome_available_utc-history.kickoff_utc).eq(pd.Timedelta(days=7)).all()
        for key in ['player_id','team']:
            ordered=history.sort_values([key,'outcome_available_utc','game_id','player_id'],kind='stable')
            assert not ordered.groupby(key).kickoff_utc.diff().dt.total_seconds().lt(0).any()
        with zipfile.ZipFile(io.BytesIO(source_bytes['normalized_offer_container']))as z:
            raw=z.read(proposal['normalized_offer_member']['member']);assert sha(raw)==proposal['normalized_offer_member']['sha256']and len(raw)==proposal['normalized_offer_member']['bytes']
            normalized=pd.read_parquet(io.BytesIO(raw))
        schedule=pd.read_csv(io.BytesIO(source_bytes['schedule']))
        reg=set(schedule.loc[schedule.season.eq(2023)&schedule.game_type.eq('REG'),'game_id'])
        assert len(reg)>0
        own=normalized.loc[normalized.season.eq(2023)&normalized.target.eq('rush_att')&normalized.game_id.isin(reg)].copy()
        canonical,offer_audit=pair_and_canonicalize(own,[68,69,79]);offers=primary_offers(canonical)
        assert len(offers)>0 and not offers.duplicated(KEY+['target']).any()and offers.week.between(1,18).all()
        # These fields are source-reference values, never the new forecast side/controls.
        source_renames={k:'source_'+k for k in ['side','M_point','M_probability']if k in offers}
        offers=offers.rename(columns=source_renames).copy()
        mainline_fields=[str(x)for x in normalized.columns if 'mainline'in str(x).lower()or'main_line'in str(x).lower()]
        mainline_status='MISSING_AUTHENTICATED_MAINLINE_FLAG;FIXED_REPRESENTATIVE_LINE_DIAGNOSTIC'if not mainline_fields else'FLAG_FIELDS_PRESENT_BUT_CONTRACT_NOT_AUTHENTICATED;REPRESENTATIVE_LINE_DIAGNOSTIC'
        # Exact source-week coverage is recorded before outcome-label decoding.
        coverage={'eligible':len(offers),'REG_games':len(reg),'offered_games':int(offers.game_id.nunique()),'actual_offer_weeks':sorted(map(int,offers.week.unique())),'requested_primary_weeks':list(range(1,10)),
          'by_week':[{'week':w,'eligible':int(offers.week.eq(w).sum()),'source_state':'OBSERVED_NAMED_BOOK_BOARD_TIME_UNVERIFIED'if offers.week.eq(w).any()else'MISSING_COMPATIBLE_ACTUAL_OFFER_BOARD;NOT_A_ZERO_SELECTION_WEEK'}for w in range(1,19)],'role_counts':offers.position.value_counts().to_dict(),'mainline_fields':mainline_fields,'mainline_status':mainline_status,'quote_clock':'UNVERIFIED_COLLECTOR_CLOCK_NOT_ORIGINAL_QUOTE_TIME','source_offer_audit':offer_audit}
        note('RUSH2023_OFFER_COVERAGE_BEFORE_LABELS_V1.json',coverage)
        with zipfile.ZipFile(io.BytesIO(source_bytes['retained_offer_forecast_container']))as z:
            raw=z.read('EVALUATION_FORECASTS.parquet');assert sha(raw)==proposal['saved_control_members']['EVALUATION_FORECASTS.parquet']['sha256']
            retained=pd.read_parquet(io.BytesIO(raw))
            raw=z.read('F_THRESHOLD_FORECASTS.parquet');assert sha(raw)==proposal['saved_control_members']['F_THRESHOLD_FORECASTS.parquet']['sha256']
            retained_law=pd.read_parquet(io.BytesIO(raw))
        retained=retained.loc[retained.season.eq(2023)&retained.target.eq('rush_att')].copy()
        retained_law=retained_law.loc[retained_law.season.eq(2023)&retained_law.target.eq('rush_att')].copy()
        control_key=KEY+['book_id','line','period','source_collection_naive']
        assert retained_law.F_model_year.eq(2023).all()and not retained_law.duplicated(control_key).any()and not retained.duplicated(control_key).any()
        for name,c in [('saved_F_law',retained_law),('saved_auxiliary',retained)]:
            match=offers[control_key].merge(c[control_key],on=control_key,how='left',validate='one_to_one',indicator=True)
            coverage[name+'_exact_horizon_available']=int(match._merge.eq('both').sum());coverage[name+'_unavailable']=int(match._merge.ne('both').sum())
        baseline_points=pd.read_parquet(io.BytesIO(source_bytes['baseline_points']))
        baseline_audit=json.loads(source_bytes['baseline_training_audit'])
        assert baseline_audit['training_rows']==len(train)and baseline_audit['numeric_features']==b['categories']['rush_att']['panels']['base']
        assert not baseline_points.duplicated(KEY).any()and baseline_points.season.eq(2023).all()and baseline_points.target.eq('rush_att').all()
        offers['offer_id']=np.arange(len(offers))
        query=pd.read_parquet(io.BytesIO(source_bytes['queries']))
        q=offers[KEY+['offer_id','team','opponent','position','kickoff_utc']].merge(query,on=KEY,how='left',suffixes=('_offer',''),validate='one_to_one',indicator=True)
        valid=q._merge.eq('both')
        for k in ['team','opponent','position','kickoff_utc']:valid&=q[k].eq(q[k+'_offer'])
        assert valid.any()
        coverage['compatible_query']=int(valid.sum());coverage['unavailable_query']=int((~valid).sum())
        q=q.loc[valid,list(query.columns)+['offer_id']].copy();q['participation_state']='unknown';q['outcome_available_utc']=pd.NaT
        assert 'rush_att'not in q and 'actual'not in q
        cdf.assert_clock_contract(q);q=bf.augment(q,history);cdf.assert_clock_contract(q)
        # One deterministic target/future-outcome mutation of this newly executing block.
        tiny=q.head(1).drop(columns=bf.COLUMNS+['backfield_feature_max_available_utc']).copy()
        altered=history.copy();altered.loc[altered.kickoff_utc.ge(tiny.cutoff_utc.iloc[0]),'rush_att']=999
        pd.testing.assert_frame_equal(bf.augment(tiny,history)[bf.COLUMNS],bf.augment(tiny,altered)[bf.COLUMNS],check_exact=True)
        category=copy.deepcopy(b['categories']['rush_att']);category['panels']['context']=category['panels']['base']+b['added_columns']['rush_att']
        assert cdf.TREE_PARAMETERS==b['tree_parameters'] and cdf.PRIOR_WEIGHT==.05
        # Check every named join overlap up front; only declared keys/context aliases coexist.
        label_fields={'actual','participation_state','outcome_state'}
        prediction_fields=set(KEY+['offer_id','position','cutoff_utc','feature_max_source_available_utc','mean','median','p_under','p_push','p_over','log_p_under','log_p_push','log_p_over','side','confidence','fallback'])
        control_fields={'F_over','F_under','F_push','F_probability','F_point','F_mean','F_fallback','F_model_year','FC_point','FC_probability','FS_probability','H_point','H_probability','M_point','M_probability'}
        assert not set(offers)&label_fields
        assert (set(offers)|label_fields)&(prediction_fields-{'position'})==set(KEY+['offer_id'])
        assert not((set(offers)|label_fields|prediction_fields)&control_fields)
        assert set(['BASE_CDF_mean','BASE_CDF_median','BASE_CDF_fallback']).isdisjoint(set(offers)|prediction_fields|control_fields)
        labels=pd.read_parquet(io.BytesIO(source_bytes['labels']))
        assert not labels.duplicated(KEY).any()
        rawstat=pd.read_parquet(io.BytesIO(source_bytes['explicit_stat_presence']),columns=['season','week','player_id','game_id','team','carries','season_type'])
        rawstat=rawstat.loc[rawstat.season_type.eq('REG')].copy();rawstat['team']=data._team(rawstat.team)
        assert not rawstat.duplicated(['season','week','player_id']).any()
        assert (set(labels)&set(rawstat))-{'season','week','player_id'}=={'game_id','team'}
        labelproof=labels.merge(rawstat,on=['season','week','player_id'],how='left',suffixes=('','_raw'),validate='one_to_one')
        known=labelproof.participation_state.eq('played')&labelproof.actual.notna()
        assert labelproof.loc[known,'carries'].notna().all()and labelproof.loc[known,'actual'].eq(labelproof.loc[known,'carries']).all()
        assert labelproof.loc[known,'game_id'].eq(labelproof.loc[known,'game_id_raw']).all()and labelproof.loc[known,'team'].eq(labelproof.loc[known,'team_raw']).all()
        presence_proof={'known_labels_with_explicit_raw_stat':int(known.sum()),'explicit_raw_zeros':int((known&labelproof.actual.eq(0)&labelproof.carries.eq(0)).sum()),'unsupported_zero_fills':0,'unknown_labels_retained':int((~known).sum()),'source_sha256':source_refs['explicit_stat_presence']['sha256']}
        note('RUSH2023_SOURCE_PREFIT_V1.json',{'coverage':coverage,'presence':presence_proof,'clock_and_identity':'known seven-day proxy; no duplicate/noncanonical IDs or publication/game-time reversal','join_schema_census':'PASS_ALL_DECLARED_OVERLAPS','label_scope':'source-presence validation only; labels never joined into training/query','baseline_expected_rows':baseline_audit['training_rows']})
        train_digest=sha(pd.util.hash_pandas_object(train,index=True).to_numpy().astype('<u8').tobytes())
        note('RUSH2023_FIT_START_V1.json',{'state':'ONE_FIT_ATTEMPT_CONSUMED','training_rows':len(train),'training_frame_values_sha256':train_digest,'category':category,'source_audit':{'history_rows':len(history),'unknown_clocks':0,'identity_or_order_failures':0,'policy':'seven-day reconstruction; not authenticated publication'},'query_rows':len(q),'offer_rows':len(offers),'usage':usage()})
        check();fits=1;model=cdf.LeafCDFModel.fit(train,category,'context');assert model.forest is not None
        # Returned parameters are durably retained before any target inference.
        s=io.BytesIO();joblib.dump(model,s,compress=3);model_bytes=s.getvalue()
        model_ref=put('MODEL.zip',cap({'model.joblib':model_bytes,'BINDING.json':enc({'version':VERSION,'training_frame_values_sha256':train_digest,'audit':model.audit,'model_member_sha256':sha(model_bytes),'binding_sha256':sha(enc(binding))})}))
        note('RUSH2023_MODEL_READBACK_V1.json',{'state':'RETURNED_MODEL_DURABLY_READ_BACK','reference':model_ref,'model_member_sha256':sha(model_bytes),'usage':usage()})
        assert model.design.names==category['panels']['context']
        baseline_parity={'first30_imputation':model.design.medians[:len(baseline_audit['numeric_medians'])]==baseline_audit['numeric_medians'],'role_priors':model.audit['role_priors']==baseline_audit['role_priors'],'global_prior':model.audit['global_prior']==baseline_audit['global_prior'],'training_rows':model.audit['training_rows']==baseline_audit['training_rows'],'supported_training_rows':model.audit['supported_played_training_rows']==baseline_audit['supported_played_training_rows']}
        assert all(baseline_parity.values()),'Own-baseline training/imputation mismatch; preserve returned model and stop without refitting'
        note('RUSH2023_BASELINE_PARITY_V1.json',baseline_parity)
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
        note('RUSH2023_INFERENCE_CHECKS_V1.json',{'state':'PASS_SCOPE_CHECKED','own_model_restoration':1,'fixture_rows':len(fixture),'single_batch_shuffled_max_tolerance':1e-12,'feature_order':'exact named sealed columns','future_target_outcome_backfield_mutation':'PASS_ONE_DETERMINISTIC_QUERY','new_additional_fits':0})
        del restored,restored_bytes
        # Law inference uses the original normalized-cumulative helper, not point inference.
        preds=[]
        for positions,law,fallback in model.predict_batches(q,batch_size=128):
            if law is None:continue
            sub=q.iloc[positions];off=offers.set_index('offer_id').loc[sub.offer_id]
            events=loss.threshold_probabilities(law,off.line.to_numpy());choice=loss.select_sides(events)
            for i,(_,r)in enumerate(sub.iterrows()):
                preds.append({**{k:r[k]for k in KEY},'offer_id':int(r.offer_id),'position':r.position,'cutoff_utc':r.cutoff_utc,'feature_max_source_available_utc':r.feature_max_source_available_utc,'mean':float(law.mean[i]),'median':float(law.quantile(.5)[i]),'p_under':float(events['probabilities'][i,0]),'p_push':float(events['probabilities'][i,1]),'p_over':float(events['probabilities'][i,2]),'log_p_under':float(events['log_probabilities'][i,0]),'log_p_push':float(events['log_probabilities'][i,1]),'log_p_over':float(events['log_probabilities'][i,2]),'side':str(choice['side'][i]),'confidence':float(choice['decisive_confidence'][i]),'fallback':str(fallback[i])})
        pred=pd.DataFrame(preds);assert len(pred)==len(q)and not pred.duplicated(KEY).any()
        frozen_ref=put('FORECASTS.zip',cap({'FORECASTS.parquet':parq(pred),'OFFERS.parquet':parq(offers),'QUERY_FEATURES.parquet':parq(q),'MANIFEST.json':enc({'version':VERSION,'model':model_ref,'code':pins,'source_refs':source_refs,'no_original_issuance':True,'quote_clock':'UNVERIFIED','timing':'seven-day reconstruction'})}))
        note('RUSH2023_FORECAST_FREEZE_V1.json',{'state':'EXACT_FORECAST_AND_OFFER_BYTES_FROZEN_BEFORE_LABEL_JOIN','reference':frozen_ref,'predicted':len(pred),'eligible':len(offers),'usage':usage()})
        # Source labels were validated before the fit; only now join them to frozen forecasts.
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
                row={'season':2023,'week':int(r['week']),'game_id':r['game_id'],'player_id':r['player_id'],'category':'rush_att','line':float(r['line']),'actual':float(y)if known else None,'appearance':appearance,'selected_side':side,'comparator':'STRICT_OVER_UNDER','status':'UNAVAILABLE_FORECAST'if side is None else'ABSTAIN'if side=='ABSTAIN'else'DNP'if appearance=='DNP'else'UNKNOWN_PARTICIPATION'if appearance!='PLAYED'else'MISSING_ACTUAL'if not known else'WIN'}
                row['status']=common.status(row);rr.append(row)
            return rr
        def summarize(f,sidecol='side',fallbackcol='fallback'):
            rows=common_rows(f,sidecol);s=common.summary(rows);s['fallback_selected']=int(f.loc[f[sidecol].isin(['over','under']),fallbackcol].fillna('').ne('').sum())if fallbackcol and fallbackcol in f else None
            s['fallback_provenance']='own retained reason'if fallbackcol else'NOT_ESTABLISHED_FOR_THIS_CONTROL;candidate mask contribution reported separately'
            s['role_counts']=f.position.value_counts().to_dict();s['supported_scored_weeks']=sorted({r['week']for r in rows if r['status']in['WIN','LOSS']});return s
        def interval(v,g):return aux._interval(v,g,{'minimum_clusters':2,'replicates':1000,'seed':20261030})
        # Exact saved strong controls retain their own source/model contracts.
        law_fields=['F_over','F_under','F_push','F_probability','F_point','F_mean','F_fallback','F_model_year']
        aux_fields=['FC_point','FC_probability','FS_probability','H_point','H_probability','M_point','M_probability']
        ctr=offers[control_key].merge(retained_law[control_key+law_fields],on=control_key,how='left',validate='one_to_one')
        ctr=ctr.merge(retained[control_key+aux_fields],on=control_key,how='left',validate='one_to_one')
        projected=ctr[KEY+law_fields+aux_fields]
        assert set(frame)&set(projected)==set(KEY)
        frame=frame.merge(projected,on=KEY,how='left',validate='one_to_one')
        context=['team','opponent','position','kickoff_utc','cutoff_utc']
        bp=baseline_points[KEY+context+['mean','median','fallback']].merge(query[KEY+context],on=KEY,how='left',suffixes=('_point','_query'),validate='one_to_one',indicator=True)
        admitted=bp._merge.eq('both')
        for name in context:admitted&=bp[name+'_point'].eq(bp[name+'_query'])
        bp=bp.loc[admitted,KEY+['mean','median','fallback']].rename(columns={'mean':'BASE_CDF_mean','median':'BASE_CDF_median','fallback':'BASE_CDF_fallback'})
        assert set(frame)&set(bp)==set(KEY)
        frame=frame.merge(bp,on=KEY,how='left',validate='one_to_one')
        controls={}
        for name,col in [('BASE_CDF_MEAN','BASE_CDF_mean'),('BASE_CDF_MEDIAN','BASE_CDF_median'),('F_SAVED_POINT','F_point'),('F_MEAN','F_mean'),('FC_SAVED_POINT','FC_point'),('H_SAVED_POINT','H_point'),('MARKET_POINT','M_point')]:
            controls[name]=[common.a.point_side(x,L).lower()if pd.notna(x)else'unavailable'for x,L in zip(frame[col],frame.line)]
        for name,col in [('F_PROBABILITY','F_probability'),('FC_PROBABILITY','FC_probability'),('FS_PROBABILITY','FS_probability'),('H_PROBABILITY','H_probability'),('MARKET_PROBABILITY','M_probability')]:
            controls[name]=['unavailable'if pd.isna(x)else'abstain'if x==.5 else'over'if x>.5 else'under'for x in frame[col]]
        controls['ALWAYS_OVER']=['over']*len(frame);controls['ALWAYS_UNDER']=['under']*len(frame)
        for name,v in controls.items():frame[name]=v
        records=[];pairs=[];metrics=[]
        for label,mask in [('2023_W1_9',frame.week.le(9)),('2023_FULL_REG',frame.week.le(18))]:
            g=frame.loc[mask].copy();top=selected(g)
            records.append({'period':label,'product':'BACKFIELD_CDF_P2_TOP6','summary':summarize(top),'eligible_board':len(g),'available_forecasts':int(g.side.ne('unavailable').sum()),'unavailable_forecasts':int(g.side.eq('unavailable').sum()),'selected_role_counts':top.position.value_counts().to_dict(),'selected_own_fallback':top.fallback.value_counts().to_dict(),'weekly':[{'week':int(w),'summary':summarize(top.loc[top.week.eq(w)]),'eligible':int(g.week.eq(w).sum()),'available':int((g.week.eq(w)&g.side.ne('unavailable')).sum())}for w in sorted(g.week.unique())]})
            records.append({'period':label,'product':'BACKFIELD_CDF_P2_FULL_BOARD','summary':summarize(g)})
            for role in sorted(g.position.unique()):records.append({'period':label,'product':'TOP6_SELECTED_ROLE_'+role,'summary':summarize(top.loc[top.position.eq(role)])})
            for name in controls:
                fallback_column='BASE_CDF_fallback'if name in ['BASE_CDF_MEAN','BASE_CDF_MEDIAN']else'F_fallback'if name in ['F_SAVED_POINT','F_MEAN','F_PROBABILITY']else None
                records.append({'period':label,'product':name+'_ON_CANDIDATE_TOP6','summary':summarize(top,name,fallback_column)})
                records.append({'period':label,'product':name+'_OWN_FULL_BOARD','summary':summarize(g,name,fallback_column)})
                a=common_rows(top);bb=common_rows(top,name);ix=[i for i in range(len(a))if a[i]['status']in['WIN','LOSS']and bb[i]['status']in['WIN','LOSS']]
                dif=np.asarray([int(a[i]['status']=='WIN')-int(bb[i]['status']=='WIN')for i in ix]);pairs.append({'period':label,'control':name,'common_selected_decided':len(ix),'candidate_wins':sum(a[i]['status']=='WIN'for i in ix),'control_wins':sum(bb[i]['status']=='WIN'for i in ix),'side_disagreements':sum(a[i]['selected_side']!=bb[i]['selected_side']for i in ix),'win_difference':int(dif.sum()),'paired_game':interval(dif,[a[i]['game_id']for i in ix]),'paired_week':interval(dif,[a[i]['week']for i in ix])})
            fprob=g.copy();fprob['side']=fprob['F_PROBABILITY'];fprob['confidence']=np.maximum(fprob.F_probability,1-fprob.F_probability);fprob['fallback']=fprob.F_fallback.fillna('UNAVAILABLE_RETAINED_CONTROL')
            records.append({'period':label,'product':'F_RETAINED_PROBABILITY_OWN_TOP6','summary':summarize(selected(fprob)),'eligible_board':len(g)})
            for mask_name,table in [('OFFERED_BOARD',g),('CANDIDATE_TOP6',top)]:
                good=table.participation_state.eq('played')&table.actual.notna()&table.actual.ge(0)&table.actual.mod(1).eq(0)
                nrec={'period':label,'mask':mask_name,'numeric':{}}
                for product in ['mean','median','BASE_CDF_mean','BASE_CDF_median','F_mean','F_point','FC_point','H_point','M_point']:
                    z=table.loc[good&table[product].notna()];error=z[product].to_numpy(float)-z.actual.to_numpy(float)
                    nrec['numeric'][product]={'scored':len(z),'MAE':float(np.abs(error).mean())if len(z)else None,'MSE':float(np.square(error).mean())if len(z)else None,'bias':float(error.mean())if len(z)else None}
                z=table.loc[good&table.p_over.notna()];logs=z[['log_p_under','log_p_push','log_p_over']].to_numpy(float)
                from decimal import Decimal
                events={'probabilities':z[['p_under','p_push','p_over']].to_numpy(float),'log_probabilities':logs,'line_ticks':np.asarray([Decimal(str(v))for v in z.line],dtype=object),'scale':1,'contract':None,'support':'count'}
                if len(z):
                    ps=loss.threshold_scores(events,z.actual.to_numpy(float));nrec['exact_law_probability']={'scored':len(z),'half_three_outcome_Brier':loss.loss_summary(ps['Brier']),'log_loss':loss.loss_summary(ps['log_loss']),'decisive_conditional_Brier':loss.loss_summary(ps['decisive_conditional_Brier'][ps['decisive_conditional_available']])}
                metrics.append(nrec)
        # Save complete versioned grades/masks, retaining unknown and unavailable rows.
        result={'version':VERSION,'state':'EXECUTED_ONE_ANNUAL_FIT_AND_FROZEN_REPLAY','model':model_ref,'forecasts':frozen_ref,'training_rows':len(train),'training_seasons':[2019,2020,2021,2022],'training_known_played_rows':model.audit['supported_played_training_rows'],'training_played_missing':model.audit['played_missing_outcome'],
          'records':records,'paired_controls':pairs,'numerical_and_probability_metrics':metrics,'raw_stat_presence_proof':presence_proof,'offer_coverage_before_labels':coverage,'own_baseline_training_parity':baseline_parity,'control_source':'F law from exact F_THRESHOLD_FORECASTS member; complete baseline typed points separately bound; no unavailable-control substitution','evidence_tier':proposal['evidence_tier'],'original_issued_forecasts':0,'new_original_NFL_games':0,'newly_evaluated_procedure_weeks':next(r['summary']['supported_scored_weeks']for r in records if r['period']=='2023_FULL_REG'and r['product']=='BACKFIELD_CDF_P2_TOP6'),'Top6_weekly_timing':'Future-in-week simultaneity not authenticated; retrospective diagnostic only','query_population':'Offer-derived universe with retained origin query feature intersection; no authenticated pregame roster claim','operational_decision':'SHADOW_RESEARCH_ONLY;NO_PRIMARY_PROMOTION_FROM_THIS_REPLAY','limitations':['One conditional historical season; original offered-role policy includes every qualified offered role','Mainline flag absent/unverified; quote times unverified; representative-line diagnostic, not mainline or original pregame issuance','No probabilities or full law inferred for point-only controls','Saved F/FC/FS/H/market controls retain distinct football/line/market-assistance contracts; no exact original website incumbent history claimed','Missing early-season boards remain missing, not zero-selection weeks; no borrowed duration'],'usage':usage()}
        grade_ref=put('GRADES.zip',cap({'ROWS.parquet':parq(frame),'RESULTS.json':enc(result),'SELECTED_MEMBERS.parquet':parq(selected(frame))}))
        result['grade_receipt']=grade_ref;result['usage']=usage()
        compressed_note('RUSH2023_HISTORICAL_RESULTS_V1.json.gz',result)
        note('RUSH2023_COMPLETE_V1.json',{'state':'COMPLETE_FIT_INFERENCE_FROZEN_GRADED_AND_LOCAL_READBACK','version':VERSION,'model':model_ref,'forecasts':frozen_ref,'grades':grade_ref,'usage':usage(),'no_primary_switch':True})
        signal.alarm(0);print(enc({'state':'COMPLETE','result':str(OUT/'RUSH2023_HISTORICAL_RESULTS_V1.json.gz'),'model':model_ref,'forecasts':frozen_ref,'grades':grade_ref,'usage':usage()}).decode(),flush=True)
    except BaseException as exc:
        failure={'state':'FAILED_PRESERVED_NO_RETRY','version':VERSION,'exception_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'usage':usage(),'returned_model_preserved':any(r['path'].endswith('MODEL.zip')for r in writes)}
        try:note('RUSH2023_FAILED_V1.json',failure)
        finally:signal.alarm(0)
        print(enc(failure).decode(),flush=True);raise

if __name__=='__main__':main()
