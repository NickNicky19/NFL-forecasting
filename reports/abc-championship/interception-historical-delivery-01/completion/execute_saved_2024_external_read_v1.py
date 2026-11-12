"""One root-authorized saved-output extension; no model loading, fitting or inference."""
from __future__ import annotations
import datetime, hashlib, importlib.util, io, json, math, os, resource, signal, sys, time, zipfile
from collections import Counter
from pathlib import Path

ROOT = Path('/workspace/nfl-methods-integration')
TASK = ROOT/'reports/abc-championship/interception-historical-delivery-01'
HERE = TASK/'completion'
PRIVATE_BASE = Path('/workspace/website-methods-research/resumed')
VERSION = 'A-SAVED-2024-COMPLETION-EXTENSION-v1'
START = time.monotonic(); CPU = time.process_time()
sys.dont_write_bytecode = True
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[name] = '1'
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(HERE/'C_code'))

def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(raw): return hashlib.sha256(raw).hexdigest()
def require(value, message):
    if not value: raise ValueError(message)
def ref(path, expected=None):
    path=Path(path); raw=path.read_bytes(); h=digest(raw)
    require(expected is None or h==expected,'Immutable source hash changed: '+path.name)
    return dict(path=str(path),bytes=len(raw),sha256=h)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def metadata_bytes(): return sum(p.stat().st_size for p in TASK.rglob('*') if p.is_file())
def norm(value): return {'LA':'LAR'}.get(str(value),str(value))
def table_bytes(frame):
    b=io.BytesIO();frame.to_parquet(b,index=False,compression='zstd');return b.getvalue()
def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if hasattr(value,'item'):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value

def run():
    preserve_v1=HERE/'execute_saved_2024_v1.py'
    go=json.loads((TASK/'COMPLETION_SCORING_GO_V1.json').read_text())
    require(go['state']=='GO' and go['publication']=='50887abadc05fea87c1eda3b6da5fe2c25585942','Published root execution GO required')
    continuation=json.loads((TASK/'COMPLETION_ORIGINAL_EXTERNAL_READ_GO_V1.json').read_text()); require(continuation['state']=='GO_BOUNDED_ORIGINAL_EXTERNAL_READ','Exact original external read GO required')
    require((HERE/'FAILED_2024_TECHNICAL_V1.json').is_file(),'Second predecode failure must remain retained')
    require((HERE/'FAILED_2024_V1.json').is_file(),'Original failure must remain retained')
    require(digest(preserve_v1.read_bytes())=='9732a95e509cdc315b27914199e43aa6d9cc096d5281983211196b94d1e91ae6','Original failed worker bytes changed')
    bounds=dict(continuation['remaining_original_budget']); bounds.update(private_retained_bytes=1048576,private_peak_bytes=4194304); bounds['public_task_metadata_bytes']=bounds.pop('public_task_metadata_shared_bytes');resource.setrlimit(resource.RLIMIT_CPU,(bounds['CPU_seconds'],bounds['CPU_seconds']))
    resource.setrlimit(resource.RLIMIT_AS,(bounds['RSS_bytes'],bounds['RSS_bytes']))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Finite completion extension wall budget')))
    signal.alarm(bounds['wall_seconds'])
    require(metadata_bytes()<bounds['public_task_metadata_bytes'],'Task metadata cap before execution')
    require(not (HERE/'EXECUTED_2024_V1.json').exists(),'Immutable execution already exists')
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    from tools import category_topfive_matched12_storage_v1 as storage4
    from tools import category_topfive_original_leans_private_freeze_v1_1 as storage3
    from tools import next02_b_completion_join_v2 as accepted
    from tools.category_topfive_matched12_replay_v1_2 import owner_validate
    from nfl_lab.historical_market_comparison import pair_and_canonicalize, primary_offers
    import abc_championship_v2 as common
    import actual_accuracy_v6
    bindings={}
    for filename,h in {
        'abc_championship_v2.py':'2ba450f91bb5fac869ce3adde031099390ec70408a91204653869032b49b2bce',
        'actual_accuracy_v6.py':'92260304be31b0fbee42faa3ab78616f77c3791bd2613edb9d322f9bbf29aa2a',
        'selection.py':'ba3cd2d5c33eb05f3c07e8f2674f6d51b51694c8fd722f8eaba5db089907997f',
        'contracts_v2.py':'9321d35ba5c7d7af59684784cbf92322849e968097ab7c01a2990493d061a77a',
        'offer_validator_v2.py':'a24a51491c061d7825a31a98fdfdf57358a666dd9b850e0f1b117cc776b0ac51',
    }.items():bindings['C_'+filename]=ref(HERE/'C_code'/filename,h)
    for file in ['tools/next02_b_completion_join_v2.py','nfl_lab/historical_market_comparison.py','tools/category_topfive_original_leans_private_freeze_v1_1.py','tools/category_topfive_matched12_storage_v1.py']:
        bindings[file]=ref(ROOT/file)
    bindings['root_GO']=ref(TASK/'COMPLETION_SCORING_GO_V1.json')
    bindings['technical_GO']=ref(TASK/'COMPLETION_TECHNICAL_CONTINUATION_GO_V1.json')
    bindings['external_read_GO']=ref(TASK/'COMPLETION_ORIGINAL_EXTERNAL_READ_GO_V1.json')
    bindings['adapter_v1_preserved']=ref(preserve_v1)
    bindings['adapter_executed']=ref(Path(__file__))
    bindings['owner_validate']=ref(ROOT/'tools/category_topfive_matched12_replay_v1_2.py')
    prepared=storage4.prepare(ROOT)
    fourth,_=storage4.open_store(ROOT,allocation_sha256=prepared['allocation_sha256'],root_go=storage4.GO,readonly=True)
    # The fourth peer remains read-only. Third writer uses its existing factory.
    with fourth.transaction():
        fourth._refresh(); before4=fourth._require(bounds['private_peak_bytes']+bounds['public_task_metadata_bytes'])
        third=storage3.storage(ROOT)
        third._refresh(); before3=third._require(bounds['private_peak_bytes']+bounds['public_task_metadata_bytes'])
    source_refs={
        'CATBOOST':(PRIVATE_BASE/'direct-booster-screen-v1-20261023/private/cells/2024/pass_cmp/direct_catboost_medium/forecast-frozen.parquet','fd066fae399b5aa061b311585497090b757412017f00100efd53f3993b9e34f7'),
        'HGB':(PRIVATE_BASE/'median-boosting-20261023/RUN_01/trials/pass_cmp/base/2024/candidate-frozen.parquet','162042f21afe78098a0044ca7f2b5cffce6ac7fbf857c4f3754578d72c1fab9d'),
        'CDF':(PRIVATE_BASE/'source-matched-report-recovery-v1-20261023/private/scored/2024/pass_cmp/leaf_cdf/rows.parquet','98c3959ea08a7c55928e48857732a17605dc18adda392f9229d3d9619810da3b'),
        'COUNT_A_LEGACY':(PRIVATE_BASE/'source-matched-base-v1-20261023/private/cells/2024/pass_cmp/count_A/forecast-frozen.parquet','6c2e80ec119f9913c1b048f9511b2f7d887d04555ac537bcebb25d0bb820b18d'),
        'HGB_ROLE_PRIOR':(PRIVATE_BASE/'median-boosting-20261023/RUN_01/trials/pass_cmp/base/2024/role-prior-frozen.parquet','49cc4095110abf2ca52444a8578f4886d71bafe9c504d4a338033e36ad59405c'),
        'offers_container':(PRIVATE_BASE/'historical-market-forward-v1-20261028/cache/processed/operational-source-v3/historical-market-no2025-v1/source-normalization-v3.zip','0521c422c36173d5190ca3fe0c296d4543673b7ca210c4daf5cd499292a6907a'),
        'HGB_model':(PRIVATE_BASE/'median-boosting-20261023/RUN_01/trials/pass_cmp/base/2024/model/model.joblib','a425360d5110530f61992bf1523ba635c2e522bb11d99e4190e3ef2bf10f3900'),
        'HGB_manifest':(PRIVATE_BASE/'median-boosting-20261023/RUN_01/trials/pass_cmp/base/2024/model/manifest.json','c46d371696da0a8c124defeebb4cf5cdbc3c856cd057e556b2dfa4e0100e63f6'),
        'CAT_model':(PRIVATE_BASE/'direct-booster-screen-v1-20261023/private/cells/2024/pass_cmp/direct_catboost_medium/model.joblib','581e37d8cafc6f78e970650d4cca02434d95773f3c1219b7fe257dd22353f41e'),
        'CAT_freeze':(PRIVATE_BASE/'direct-booster-screen-v1-20261023/forecast-freeze.json','24d62b47e17fe936407d2cd7dc7d8d2f2a86244a3487211132d4df7c8798ca4f'),
        'HGB_training':(PRIVATE_BASE/'median-boosting-20261023/permitted-source/features.parquet','e4f325e577f40839f7029a3a65010a9517a067432247736ea3b220f67262adfc'),
    }
    # All inputs are existing owner-local immutable references; no model bytes loaded.
    external_keys={'HGB','HGB_ROLE_PRIOR','HGB_model','HGB_manifest','HGB_training'}
    external_stamps={}
    for name,(path,h) in source_refs.items():
        bindings[name]=ref(path,h)
        if name in external_keys:
            require(path.resolve()==path and not any(q.is_symlink() for q in (path,*path.parents)),'External original path must be canonical and nonsymlink')
            st=path.stat();external_stamps[name]=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
        else:owner_validate(fourth,bindings[name])
    require(sum(bindings[k]['bytes'] for k in external_keys)==5514422,'Exact external original byte envelope')
    original_root=PRIVATE_BASE/'median-boosting-20261023'
    bindings['HGB_original_registry']=ref(original_root/'SEALED_REGISTRY.json','49ea230f4a54e523faed757f77239c17e1829c7ed7350d8b44f2025c425a9256')
    bindings['HGB_original_source_rights']=ref(original_root/'APPROVED_SOURCE_CONTRACT.json','ef3083a77e0ac864e96de2af85faddc1e1d509129f202969e52e66f4554cc5f5')
    original_registry=json.loads((original_root/'SEALED_REGISTRY.json').read_text());rights=json.loads((original_root/'APPROVED_SOURCE_CONTRACT.json').read_text());old_policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_text())
    require(original_registry['source_contract']['sha256']==bindings['HGB_original_source_rights']['sha256'] and original_registry['inputs']['training_features']['sha256']==bindings['HGB_training']['sha256'],'Original source rights binding mismatch')
    require(rights['state']=='APPROVED_FREE_TRAINING_AND_INFERENCE' and 'immutable' in old_policy['storage']['legacy'],'Original external read authority not established')
    external_admission=dict(state='ADMITTED_READONLY_ORIGINALS_BEFORE_DECODE',sources={k:bindings[k] for k in sorted(external_keys)},existing_external_bytes=5514422,rights=bindings['HGB_original_source_rights'],original_registration=bindings['HGB_original_registry'],authority=old_policy['storage']['legacy'],old_policy=ref(ROOT/'config/operational-source-policy-v2.json'),model_hash_only=True,model_deserialized=False,managed_restore=False,no_copy=True)
    with (HERE/'EXTERNAL_ORIGINAL_ADMISSION_V1.json').open('xb') as f:f.write(encoded(external_admission));f.flush();os.fsync(f.fileno())
    raw_stat=next((PRIVATE_BASE/'operational-storage-v2-20261023/cache/operational-source-v2').glob('*/20261023T112749536081Z/*/sources/stats_player_week_2024.parquet'))
    bindings['raw_stats']=ref(raw_stat,'847569d194ca3d96b5efcf91e6eac5e18780fc47568a713fd545a82d29d155c1');owner_validate(fourth,bindings['raw_stats'])
    schedule=raw_stat.parent/'schedules.csv';bindings['schedule']=ref(schedule,'6a7828f3aa5f0ba17cd365295489a09b861f4fa8eaa0f4c00c7c05ac652987e7');owner_validate(fourth,bindings['schedule'])
    sch=pd.read_csv(schedule);sch=sch.loc[sch.season.eq(2024)&sch.game_type.eq('REG')].copy()
    require(not sch.game_id.duplicated().any(),'Schedule event ambiguity');reg=set(sch.game_id.astype(str))
    require(len(sch)==272,'2024 REG event census changed')
    frames={k:pd.read_parquet(path) for k,(path,h) in source_refs.items() if k in ['CATBOOST','HGB','CDF','COUNT_A_LEGACY','HGB_ROLE_PRIOR']}
    for name,f in frames.items():
        require(not f.duplicated(['game_id','player_id']).any(),'Saved forecast identity duplication: '+name)
        require(f.season.eq(2024).all(),'Wrong forecast season')
        require(f.target.eq('pass_cmp').all(),'Wrong forecast target')
    htrain=pd.read_parquet(source_refs['HGB_training'][0],columns=['player_id','game_id','season','kickoff_utc','cutoff_utc','outcome_available_utc','feature_max_source_available_utc','f_player_games_prior'])
    for c in ['kickoff_utc','cutoff_utc','outcome_available_utc','feature_max_source_available_utc']:htrain[c]=pd.to_datetime(htrain[c],utc=True)
    clock=dict(rows=len(htrain),duplicate_player_game=int(htrain.duplicated(['game_id','player_id']).sum()),explicit_unknown_outcome_clock=int(htrain.outcome_available_utc.isna().sum()),non_fixed_seven_day=int((htrain.outcome_available_utc!=htrain.kickoff_utc+pd.Timedelta(days=7)).sum()),warm_missing_feature_clock=int((htrain.f_player_games_prior.gt(0)&htrain.feature_max_source_available_utc.isna()).sum()),feature_at_or_after_cutoff=int((htrain.feature_max_source_available_utc>=htrain.cutoff_utc).sum()))
    require(all(clock[k]==0 for k in clock if k!='rows'),'Old source chronology requires correction, stop original-version join')
    labels=frames['CDF'][['game_id','player_id','position','actual','participation_state','outcome_state']]
    raw=pd.read_parquet(raw_stat,columns=['player_id','game_id','season_type','team','completions','attempts'])
    raw=raw.loc[raw.season_type.eq('REG')].copy();require(not raw.duplicated(['game_id','player_id']).any(),'Raw stat identity duplication')
    lab=labels.merge(raw,on=['game_id','player_id'],how='left',validate='1:1')
    q=lab.loc[lab.position.eq('QB')];present=q.actual.notna()
    presence=dict(QB_rows=len(q),supported_labels=int(present.sum()),raw_reported_labels=int(q.completions.notna().sum()),label_disagreement=int((present&(~q.actual.eq(q.completions))).sum()),explicit_zero=int((q.actual.eq(0)&q.completions.eq(0)).sum()),unsupported_zero=int((q.actual.eq(0)&q.completions.isna()).sum()),unknown=int(q.participation_state.eq('unknown').sum()),completions_above_attempts=int((q.completions>q.attempts).sum()))
    require(presence['label_disagreement']==presence['unsupported_zero']==presence['completions_above_attempts']==0,'Outcome source discrepancy; no scoring')
    lm={(str(r.game_id),str(r.player_id)):r for r in lab.itertuples()}
    with zipfile.ZipFile(source_refs['offers_container'][0]) as archive:offer_body=archive.read('offers_2024.parquet')
    require(digest(offer_body)=='2d8a3ba8512d4a830ab2d00962955b9bab2cb4ebbd241cd4781556c3605cb30a','Offer member changed')
    bindings['offer_member']=dict(member='offers_2024.parquet',bytes=len(offer_body),sha256=digest(offer_body))
    offers=pd.read_parquet(io.BytesIO(offer_body));offers=offers.loc[offers.target.eq('pass_cmp')&offers.position.eq('QB')&offers.game_id.isin(reg)].copy()
    canonical,_=pair_and_canonicalize(offers,[68,69,79])
    board=primary_offers(canonical)
    require(not board.duplicated(['season','game_id','player_id','target']).any(),'Primary offer duplication')
    require(board.week.between(1,18).all() and board.game_id.isin(reg).all(),'NonREG offer entered')
    require(not board.empty,'No supported named-book completion offers')
    ids=['CATBOOST_MEDIUM_ORIGINAL_2024::point','HGB_MAE_DIRECT_ORIGINAL_2024_BASE::point','CDF_ORIGINAL_2024::mean','CDF_ORIGINAL_2024::median','COUNT_A_ORIGINAL_2024::legacy_point','HGB_ORIGINAL_2024::role_prior','ALWAYS_OVER','ALWAYS_UNDER']
    arms={ids[0]:('CATBOOST','point'),ids[1]:('HGB','point'),ids[2]:('CDF','mean'),ids[3]:('CDF','median'),ids[4]:('COUNT_A_LEGACY','point'),ids[5]:('HGB_ROLE_PRIOR','point')}
    lookups={name:{(str(r['game_id']),str(r['player_id'])):r for r in f.to_dict('records')} for name,f in frames.items()}
    rows={name:[] for name in ids};unavailable=Counter();variation={};raw_team_mismatch=set()
    for name,f in frames.items():
        ff=f.loc[f.position.eq('QB')&f.game_id.isin(reg)]
        variation[name]=dict(QB_REG_rows=len(ff),point_distinct=int(ff.point.nunique()),point_zero=int(ff.point.eq(0).sum()),fallback_states=dict(Counter(str(v) for v in ff.fallback)),all_original_actuals_missing=bool(ff.actual.isna().all()) if name!='CDF' else None)
    for o in board.to_dict('records'):
        key=(str(o['game_id']),str(o['player_id']));label=lm.get(key)
        appearance='UNKNOWN' if label is None else 'PLAYED' if label.participation_state=='played' else 'DNP' if str(label.participation_state).lower()=='dnp' else 'UNKNOWN'
        actual=None
        if label is not None and appearance=='PLAYED' and pd.notna(label.actual) and pd.notna(label.completions):
            require(float(label.actual)==float(label.completions),'Unsupported label mismatch')
            actual=float(label.completions);require(math.isfinite(actual) and actual>=0 and actual==int(actual),'Invalid completion outcome')
            if norm(label.team)!=norm(o['team']):
                raw_team_mismatch.add(key); actual=None
        oid=digest(encoded([2024,int(o['week']),*key,'pass_cmp',int(o['book_id']),str(o['line']),str(o['source_collection_naive']),int(o['source_row_number'])]))
        for cid in ids:
            point=None;fallback=None;reason=None;side=None;fore=None
            if cid in arms:
                name,column=arms[cid];fore=lookups[name].get(key)
                reason='NO_SAVED_FORECAST' if fore is None else None
                if fore is not None:
                    if fore['position']!='QB':reason='ROLE_MISMATCH'
                    elif any(norm(fore[k])!=norm(o[k]) for k in ['team','opponent']):reason='HISTORICAL_TEAM_OR_OPPONENT_MISMATCH'
                    elif pd.Timestamp(fore['kickoff_utc'])!=pd.Timestamp(o['kickoff_utc']):reason='EVENT_CLOCK_MISMATCH'
                    elif pd.Timestamp(fore['cutoff_utc'])>pd.Timestamp(o['kickoff_utc']):reason='FORECAST_FEATURE_CUTOFF_AFTER_KICKOFF'
                    elif pd.isna(fore[column]) or not math.isfinite(float(fore[column])):reason='NONFINITE_POINT'
                    if reason is None:point=float(fore[column]);fallback=str(fore['fallback'])
                side=accepted.point_side(point,o['line'])
            else:side=cid.removeprefix('ALWAYS_');fallback='CONSTANT_CONTROL'
            r=dict(candidate_id=cid,season=2024,week=int(o['week']),game_id=key[0],player_id=key[1],team=norm(o['team']),opponent=norm(o['opponent']),position='QB',category='pass_cmp',comparator='STRICT_OVER_UNDER',line=float(o['line']),actual=actual,appearance=appearance,point=point,selected_side=side,opportunity_key=oid,fallback=fallback,unavailability_reason=reason,book_id=int(o['book_id']),source_row_number=int(o['source_row_number']),source_collection_naive=str(o['source_collection_naive']),forecast_cutoff_utc=None if fore is None else str(fore['cutoff_utc']),forecast_kickoff_utc=str(o['kickoff_utc']),source_sha256=str(o['source_sha256']),quote_timing='UNVERIFIED',status=None)
            r['status']=accepted.grade(r);require(common.status(r)==r['status'],'Accepted A and canonical C grade mismatch')
            rows[cid].append(r)
            if reason:unavailable[cid+'::'+reason]+=1
    presence['offered_raw_historical_team_mismatches']=len(raw_team_mismatch)
    # Deterministic existing-scorer boundary fixtures; separate from NFL records.
    for actual,appearance,side,expected in [(0.,'PLAYED','UNDER','WIN'),(None,'PLAYED','UNDER','MISSING_ACTUAL'),(0.,'UNKNOWN','UNDER','UNKNOWN_PARTICIPATION'),(1.,'PLAYED','OVER','WIN'),(.5,'PLAYED','OVER','PUSH')]:
        fixture=dict(selected_side=side,actual=actual,appearance=appearance,line=.5,comparator='STRICT_OVER_UNDER',status=expected)
        require(accepted.grade(fixture)==common.status(fixture)==expected,'Existing-scorer fixture mismatch')
    summaries=[];pairs=[]
    pair_ids=[(ids[0],other) for other in ids[1:]]+[(ids[1],other) for other in ids[2:]]
    for panel,allowed in [('ALL_2024_REG',set(range(1,19))),('2024_W1_W8',set(range(1,9)))]:
        rr={cid:[r for r in rs if r['week'] in allowed] for cid,rs in rows.items()}
        for cid,rs in rr.items():
            for week in ['ALL']+sorted(allowed):
                ww=[r for r in rs if week=='ALL' or r['week']==week]
                summaries.append(dict(panel=panel,candidate_id=cid,week_view=week,**common.summary(ww),numerical=accepted.numerical(ww),fallback_states=dict(Counter(str(r['fallback']) for r in ww)),unknown=sum(r['appearance']=='UNKNOWN' for r in ww),learned=sum(r['fallback']=='' for r in ww),selected_learned=sum(r['fallback']=='' and r['selected_side'] in ['OVER','UNDER'] for r in ww),scored_weeks=sorted({r['week'] for r in ww if r['status'] in ['WIN','LOSS','PUSH']}),eligible_mask_sha256=accepted.mask(ww),decided_mask_sha256=accepted.mask(ww,True)))
        for left,right in pair_ids:pairs.append(dict(panel=panel,left=left,right=right,**accepted.paired(rr[left],rr[right],np)))
    # A fixed common-availability mask supplements, never replaces, full-board results.
    common_ids=set(r['opportunity_key'] for r in rows[ids[0]])
    for cid in ids[:6]:common_ids&={r['opportunity_key'] for r in rows[cid] if r['selected_side'] is not None}
    common_summary=[dict(candidate_id=cid,**common.summary([r for r in rs if r['opportunity_key'] in common_ids]),numerical=accepted.numerical([r for r in rs if r['opportunity_key'] in common_ids])) for cid,rs in rows.items()]
    for name in external_keys:
        path,h=source_refs[name]; st=path.stat();require((st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==external_stamps[name] and digest(path.read_bytes())==h,'External original changed after read')
    safe_bindings={k:{kk:vv for kk,vv in v.items() if kk!='path'} for k,v in bindings.items()}
    summary=dict(id=VERSION,state='EXECUTED_ORIGINAL_VERSION_2024_SAVED_OUTPUT_DIAGNOSTIC',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_bindings=safe_bindings,procedure_bindings=dict(CATBOOST=dict(training_seasons=list(range(2019,2024)),REG=True,model_sha256=bindings['CAT_model']['sha256'],output='conditional_mean_objective_point',recipe='mediumPoisson128_depth5_seed1753'),HGB=dict(training_seasons=list(range(2019,2024)),original_allphase=True,model_sha256=bindings['HGB_model']['sha256'],manifest_sha256=bindings['HGB_manifest']['sha256'],output='MAE_objective_point_heuristic',recipe='absolute_error150_depth3_seed1702')),admission=dict(clock=clock,presence=presence,forecast_variation=variation,C_WIN_LOSS_PUSH_recalculation_parity=True,unknown_states_from_existing_A_grade=True),offer_policy='Unchanged historical_market_comparison.pair_and_canonicalize([68,69,79]) then primary_offers; earliest collector snapshot perbook andfixed bookpriority; source clocks naive/unverified',direction_policy='Unrounded savedpoint strictly above/below original exactline; equality abstains; each method ownside',population='2024REG historicalstat/roster-conditioned QBquery rows; not authenticated pregameroster; full namedbookboard retained with unavailable/unknowns',evidence_tier='EXPOSED_CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION;ACTUAL_NAMED_BOOK_LINES_QUOTE_TIME_UNVERIFIED;NO_ORIGINAL_ISSUANCE',original_source_limit='2024HGB e4f325 permittedsource allphase training differs from accepted2026REG375dc79; no source-equivalence or model-fit parity claimed. No fit/inference/model loading in this run.',counts=dict(eligible=len(board),games=int(board.game_id.nunique()),weeks=sorted(map(int,board.week.unique())),common_available=len(common_ids),new_fits=0,new_inference=0,source_acquisition=0),summaries=summaries,paired=pairs,common_available_summaries=common_summary,unavailable_reasons=dict(unavailable),external_original_scope=dict(existing_bytes=5514422,managed_restore=False,read_only=True,before_after_hash_and_stamp_match=True,authorization_registry_sha256=bindings['HGB_original_registry']['sha256'],rights_sha256=bindings['HGB_original_source_rights']['sha256']),probability='N/A: no probabilities inferred from points; CDF mean/median used only as typed numerical controls',exact_incumbent='UNAVAILABLE_ON_THIS_HISTORICAL_BOARD; no replacement-superiority claim',earlier_prevalence='NOT_RETAINED_ON_THIS_EXACT_OFFER_MASK; not reconstructed from exposed outcomes',decision='SHADOW_DIAGNOSTIC_ONLY; no primary release or prospective claim',resources=dict(CPU_seconds=time.process_time()-CPU,wall_seconds=time.monotonic()-START,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    joint=pd.DataFrame([r for rs in rows.values() for r in rs])
    members={'JOINT_ROWS.parquet':table_bytes(joint),'SCOPES_AND_AGGREGATES.json':encoded(clean(summary)),'SOURCE_AND_POLICY_BINDINGS.json':encoded(dict(bindings=bindings,unchanged_procedures=arms,root_GO=go))}
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,body in sorted(members.items()):archive.writestr(name,body)
    body=buffer.getvalue();require(2*len(body)+65536<=bounds['private_retained_bytes'],'Complete physical retained-byte envelope')
    require(metadata_bytes()+65536<bounds['public_task_metadata_bytes'],'Leave bounded task metadata for public report')
    target=third.live_root/'research'/'interception-historical-delivery-01-completion-2024-v1'/'RESULTS.zip'
    require(not target.parent.exists(),'Fresh unique output namespace required')
    with fourth.transaction():
        fourth._refresh();prior=fourth._require(bounds['private_peak_bytes']+bounds['public_task_metadata_bytes'])
        with third.transaction():
            third._refresh();third._require(bounds['private_peak_bytes']+bounds['public_task_metadata_bytes'])
            third.register_root(target.parent);third.write_bytes(target,body);third.validate_reference(target,digest(body))
        fourth._refresh();after4=fourth._require(bounds['public_task_metadata_bytes'])
        third._refresh();after3=third._require(bounds['public_task_metadata_bytes'])
        require(after3['market_accounted_bytes']-before3['market_accounted_bytes']<=bounds['private_retained_bytes'],'Actual private growth exceeded envelope')
    with zipfile.ZipFile(target) as archive:
        require(set(archive.namelist())==set(members),'Readback member set')
        for name,b in members.items():require(archive.read(name)==b,'Complete private readback differs')
    receipt=dict(id=VERSION,state=summary['state'],UTC=summary['UTC'],artifact=dict(path=str(target),bytes=len(body),sha256=digest(body)),members={k:dict(bytes=len(v),sha256=digest(v)) for k,v in members.items()},source_bindings=safe_bindings,procedure_bindings=summary['procedure_bindings'],admission=summary['admission'],counts=summary['counts'],summaries=summaries,paired=pairs,common_available_summaries=common_summary,evidence_tier=summary['evidence_tier'],decision=summary['decision'],external_original_scope=summary['external_original_scope'],limits=dict(original_source=summary['original_source_limit'],population=summary['population'],incumbent=summary['exact_incumbent'],prevalence=summary['earlier_prevalence']),storage=dict(factory='category_topfive_original_leans_private_freeze_v1_1.storage unchanged',fourth_readonly=True,permanent_lock_unchanged=True,market_before=before3['market_accounted_bytes'],market_after=after3['market_accounted_bytes'],market_limit=after3['market_limit_bytes'],complete_before=before4['matched12_complete_accounted_bytes'],complete_after=after4['matched12_complete_accounted_bytes'],complete_limit=after4['matched12_complete_limit_bytes'],private_physical_growth=after3['market_accounted_bytes']-before3['market_accounted_bytes'],explicit_task_metadata_reservation=bounds['public_task_metadata_bytes']),resources=dict(CPU_seconds=time.process_time()-CPU,wall_seconds=time.monotonic()-START,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),counters=dict(fits=0,inference=0,model_loads=0,new_HTTP_source_acquisition=0,raw_rows_published=0,production_changes=0))
    receipt['artifact'].pop('path',None)
    full_public=__import__('gzip').compress(encoded(clean(receipt)),mtime=0)
    def brief(x,weekly=False):
        z={k:x[k] for k in ['panel','candidate_id','week_view','eligible','unavailable','unknown','learned','OVER','UNDER','COMBINED']}
        if not weekly:z.update(numerical=x['numerical'],fallback_states=x['fallback_states'],scored_weeks=x['scored_weeks'])
        return z
    compact={k:v for k,v in receipt.items() if k not in ['summaries','paired','common_available_summaries']}
    compact['summaries']=[brief(x) for x in summaries if x['week_view']=='ALL']
    compact['weekly_columns']=['week','procedure_index_in_primary_ids','eligible','unavailable','unknown','learned','Over_W','Over_L','Under_W','Under_L','Combined_W','Combined_L']
    compact['primary_ids']=ids[:2]
    compact['weekly_primary']=[[x['week_view'],ids.index(x['candidate_id']),x['eligible'],x['unavailable'],x['unknown'],x['learned'],x['OVER']['wins'],x['OVER']['losses'],x['UNDER']['wins'],x['UNDER']['losses'],x['COMBINED']['wins'],x['COMBINED']['losses']] for x in summaries if x['week_view']!='ALL' and x['panel']=='ALL_2024_REG' and x['candidate_id'] in ids[:2]]
    compact['primary_paired']=[x for x in pairs if x['left']==ids[0] and x['right']==ids[1]]
    compact['full_aggregate_receipt']=dict(file='FULL_AGGREGATES_2024_V1.json.gz',bytes=len(full_public),sha256=digest(full_public))
    public=encoded(clean(compact));require(metadata_bytes()+len(public)+len(full_public)+12288<=bounds['public_task_metadata_bytes'],'Task metadata cap with final root reserve before public receipt')
    with (HERE/'FULL_AGGREGATES_2024_V1.json.gz').open('xb') as f:f.write(full_public);f.flush();os.fsync(f.fileno())
    with (HERE/'EXECUTED_2024_V1.json').open('xb') as f:f.write(public);f.flush();os.fsync(f.fileno())
    signal.alarm(0)
    print(json.dumps(dict(state=receipt['state'],eligible=len(board),games=receipt['counts']['games'],weeks=receipt['counts']['weeks'],artifact_sha256=digest(body),private_bytes=len(body),public_metadata_bytes=metadata_bytes(),resources=receipt['resources'])))

if __name__=='__main__':
    try:run()
    except BaseException as e:
        failure=dict(state='FAILED_PRESERVED_ATTEMPT_NO_AUTOMATIC_RETRY',error=type(e).__name__,message=str(e),CPU_seconds=time.process_time()-CPU,wall_seconds=time.monotonic()-START)
        p=HERE/'FAILED_2024_EXTERNAL_READ_V1.json'
        if not p.exists() and metadata_bytes()+len(encoded(failure))<262144:p.write_bytes(encoded(failure))
        print(json.dumps(failure));raise
