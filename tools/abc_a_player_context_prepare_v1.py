"""Registered A-only retained-source/compact-inference pilot; no fits or collection."""
from __future__ import annotations
import copy,datetime,gzip,hashlib,io,json,os,resource,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'reports/abc-championship/player-context-matchup-01'
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def frame_ref(df):
    # Ordered dtype/null/value commitment; original retained rows remain the restore source.
    return {'rows':len(df),'columns':list(df),'dtypes':[str(t)for t in df.dtypes],
      'nulls':{k:int(v)for k,v in df.isna().sum().items()},
      'ordered_pandas_hash_sha256':sha(__import__('pandas').util.hash_pandas_object(df,index=True).values.tobytes())}
def run():
    start=time.monotonic();cpu=time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(300,310))
    for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
    import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq,joblib
    pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
    from tools import abc_a_dynamic_carry_wave_v1 as base
    from nfl_lab import abc_dynamic_carry_v1 as core,cdf_engine as cdf
    from tools import category_topfive_matched12_storage_v1 as st
    # All own-class modules imported before frozen storage attaches its package.
    store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO,readonly=True)
    b,c,g,fr,z,train,history,qq=base.inputs(pd)
    p=store.forward_root/'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/MODEL_2026_A1.joblib'
    ref={'path':str(p),'bytes':2316296,'sha256':'e48f750893984c4d4395d399075458c52be83ba02bbbbc0615866e378de4f659'}
    model=joblib.load(io.BytesIO(base.pin(ref)))
    assert isinstance(model,cdf.LeafCDFModel)and model.audit['fit_state']=='FITTED'
    print('AUTHENTICATED_OWN_MODEL_LOADED',flush=True)
    records=core.compile_history(history)
    augmented,aux,params=core.augment(train,records)
    mask=(augmented.season<2026)&(pd.to_datetime(augmented.outcome_available_utc,utc=True)<pd.Timestamp('2026-09-01',tz='UTC'))
    training=augmented.loc[mask].copy()
    y=cdf.numeric(training,'rush_att');good=(cdf.strings(training,'participation_state')=='played')&cdf.valid_support(y,'count')
    supported=training.loc[good];modeled=supported.loc[supported.position.isin(model.category['modeled_roles'])]
    cols=list(model.training_binding)
    pd.testing.assert_frame_equal(modeled[cols],model.training_binding,check_exact=True)
    pd.testing.assert_frame_equal(supported[list(model.prior_training_binding)],model.prior_training_binding,check_exact=True)
    ids=model.forest.apply(model.design.transform(modeled)).astype(np.int32)
    np.testing.assert_array_equal(ids,model.training_leaf_ids)
    q,_,_=core.augment(qq[2026],records)
    def predictions(m):
        r=[]
        for ix,law,fb in m.predict_batches(q):
            r.append((ix.copy(),law.support.copy(),law.weights.copy(),law.mean.copy(),law.quantile(.5).copy(),law.variance.copy(),fb.copy(),
                law.cdf(np.full(len(ix),9.)).copy(),law.cdf(np.full(len(ix),10.)).copy()))
        return r
    expected=predictions(model)
    compact=copy.copy(model)
    compact.training_binding=None;compact.prior_training_binding=None;compact.training_leaf_ids=None
    stream=io.BytesIO();joblib.dump(compact,stream,compress=3);body=stream.getvalue()
    restored=joblib.load(io.BytesIO(body))
    actual=predictions(restored)
    assert len(expected)==len(actual)
    for x,y in zip(expected,actual):
        for a,b_ in zip(x,y):np.testing.assert_array_equal(a,b_)
    report={'state':'PASS_IN_MEMORY_COMPACT_ROUNDTRIP_NO_NEW_FIT','assignment':'PLAYER-CONTEXT-MATCHUP-01',
      'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_model':{k:v for k,v in ref.items()if k!='path'},
      'compact_in_memory':{'bytes':len(body),'sha256':sha(body),'durable_restore':'NOT_YET_WRITTEN'},
      'exact_query_rows':len(q),'exact_modeling_rows':len(modeled),'training_binding':frame_ref(model.training_binding),
      'prior_training_binding':frame_ref(model.prior_training_binding),'training_leaf_ids':{'shape':list(ids.shape),'dtype':str(ids.dtype),'sha256':sha(ids.tobytes())},
      'derivation':{'training_source':{'bytes':fr['bytes'],'sha256':fr['sha256'],'member':'PREPARED_TRAIN.parquet'},
        'history_sources':[{k:v for k,v in x.items()if k!='path'}for x in c['history_sources']],
        'features':'Existing Backfield prepared training; exact abc_dynamic_carry_v1.augment; season<2026 and explicit availability<2026-09-01; original ordered supported/modeled masks; fitted design transform; fitted forest.apply; int32',
        'factorized_fields':['training_binding','prior_training_binding','training_leaf_ids'],
        'old_model_unchanged':True,'all_unique_learned_state_retained':True},
      'parity':['full law support/weights','mean','lower median','variance','fallback','integer and half-integer CDF boundaries'],
      'model_loads':{'original_authenticated':1,'compact_in_memory_roundtrip':1},'new_fits':0,'new_football_accuracy_observations':0,
      'code_sha256':{n:sha((ROOT/n).read_bytes())for n in ['nfl_lab/cdf_engine.py','nfl_lab/abc_dynamic_carry_v1.py','tools/abc_a_dynamic_carry_wave_v1.py']}}
    (OUT/'COMPACT_PREPARATION_V1.json').write_bytes(enc(report))
    print('PACKAGING_PARITY_PASS',len(body),len(q),flush=True)
    # The new source-group admission precedes this minimal semantic projection.
    d=base.doc('role-count-full-pbp2024-recovery-gate-network-v2.json');p24=Path(d['output'])/'FULL_PBP2024.parquet'
    r24={'path':str(p24),'bytes':d['asset']['expected_bytes'],'sha256':d['asset']['expected_sha256']}
    r26=base.doc('category-topfive-matched12-current-label-execute-v1.json.gz')['pbp']
    cols=['season','season_type','week','game_id','play_id','posteam','defteam','rusher_player_id','rush_attempt','rushing_yards',
      'run_location','run_gap','down','ydstogo','yardline_100','qb_kneel','qb_scramble','qb_spike','two_point_attempt','penalty',
      'play_type','first_down_rush','epa','success']
    reports=[]
    for season,ref_ in [(2024,r24),(2026,r26)]:
        raw=base.pin(ref_);df=pd.read_parquet(io.BytesIO(raw),columns=cols)
        assert df.season.eq(season).all()
        df=df.loc[df.season_type.eq('REG')&((df.week<=7)if season==2026 else True)].copy()
        attempts=df.loc[df.rush_attempt.eq(1)&df.two_point_attempt.eq(0)]
        ag=attempts.loc[attempts.rusher_player_id.notna()].groupby(['game_id','rusher_player_id']).size().rename('pbp_count')
        h=history.loc[history.season.eq(season)&((history.week<=7)if season==2026 else True)&history.participation_state.eq('played')]
        joined=h.merge(ag,left_on=['game_id','player_id'],right_index=True,how='left',validate='one_to_one')
        # Empty carries are zero only when the full source game and explicit official label qualify.
        has_game=joined.game_id.isin(df.game_id.unique());known=pd.to_numeric(joined.rush_att,errors='coerce').notna()&has_game
        got=joined.pbp_count.fillna(0);bad=known&got.ne(joined.rush_att)
        report_={'season':season,'raw_source':{k:v for k,v in ref_.items()if k!='path'},'actual_weeks':sorted(df.week.unique().tolist()),
          'REG_rows':len(df),'games':df.game_id.nunique(),'credited_attempt_rows':len(attempts),
          'null_rusher_attempts':int(attempts.rusher_player_id.isna().sum()),'field_nulls_on_attempts':{k:int(v)for k,v in attempts[cols].isna().sum().items()},
          'weekly_stat_reconciliation':{'supported_player_games':int(known.sum()),'matched':int((known&~bad).sum()),'mismatched':int(bad.sum()),
             'mismatch_deltas':{str(k):int(v)for k,v in (got-joined.rush_att).loc[bad].value_counts().items()}},
          'role_claim':'Official credited rush flags; all positions preserved before RB query restriction; location/gap descriptive, not called concept',
          'original_publication_clock':'UNKNOWN_CURRENT_VINTAGE','new_HTTP':0}
        reports.append(report_)
    result={'state':'SOURCE_PROJECTION_EXECUTED_RECONCILIATION_REQUIRES_REVIEW','sources':reports,
      'rights':'Existing retained approved source; new scoped context analysis; no raw public export',
      'blocked':['All-route/alignment denominators','Offensive-line availability and blocking concept','Front/box context','2025 full PBP binding','2026 Week8 complete PBP'],
      'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    (OUT/'SOURCE_QUALIFICATION_V1.json').write_bytes(enc(result))
    print(json.dumps(result),flush=True)
if __name__=='__main__':run()
