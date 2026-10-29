"""Prepared trusted-artifact inference contract for the separate chart target.

This module is not wired into the website. A caller must admit its model/source
manifest, trusted pickle hash, current identity bridge and actual pregame clocks.
"""
from __future__ import annotations
import hashlib
import pickle
import numpy as np
import pandas as pd
from . import cdf_engine as engine

VERSION='nick-chart-ppr-leaf-cdf-future-contract-v1'
TARGET='nick-chart-ppr-v1'
SCALE=50
ROLES=['QB','RB','FB','WR','TE']
STATS=['pass_yd','pass_td','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_td','rec_td','rec_tgt']
FEATURES=[f'f_player_{s}_mean{w}'for s in STATS for w in (3,8)]+[
 'f_player_games_prior','f_player_play_rate8','f_player_known_participation_n8','f_player_pass_ypa3',
 'f_player_comp_rate3','f_player_rush_ypa3','f_player_rec_ypt3','f_player_rec_catch_rate3','f_rest_days','f_is_home']
IDENTITY=['season','week','game_id','team','opponent','player_id','position']
CLOCKS=['cutoff_utc','kickoff_utc','feature_max_source_available_utc']


def load_reviewed_model(body:bytes, *, expected_sha256:str):
    """The expected hash must come from the approved manifest, not untrusted input."""
    if not isinstance(body,bytes)or len(expected_sha256)!=64 or hashlib.sha256(body).hexdigest()!=expected_sha256:
        raise ValueError('trusted reviewed model identity required before pickle loading')
    model=pickle.loads(body)
    if (not isinstance(model,engine.LeafCDFModel)or model.category['target']!='chart_lattice_002_v1'
        or model.category['support']!='signed_integer'or model.category['panels']['base']!=FEATURES
        or model.category['modeled_roles']!=ROLES or model.forest is None
        or len(model.forest.estimators_)!=32 or model.global_prior is None):
        raise ValueError('exact chart-CDF artifact/schema required')
    return model


def _clock(value, *, allow_missing=False):
    if pd.isna(value):
        if allow_missing:return None
        raise ValueError('unknown required pregame clock')
    stamp=pd.Timestamp(value)
    if stamp.tzinfo is None:raise ValueError('timezone-aware input clocks required')
    return stamp.tz_convert('UTC')


def predict_reviewed(model, queries:pd.DataFrame, *, source_policy_sha256:str, expected_source_policy_sha256:str):
    """Emit exact-law means/medians with explicit prior fallback; no outcomes read.

    A source hash authenticates an approved contract, not actual publication
    truth. Upstream caller must separately verify source vintages/persistence.
    """
    if source_policy_sha256!=expected_source_policy_sha256 or len(source_policy_sha256)!=64:
        raise ValueError('approved current-input source binding required')
    if not 0<len(queries)<=4096 or set(IDENTITY+CLOCKS)-set(queries):
        raise ValueError('bounded complete query identity/cutoff schema required')
    frame=queries.copy().reset_index(drop=True)
    if frame[IDENTITY].isna().any(axis=None)or frame.duplicated(['season','week','game_id','player_id']).any():
        raise ValueError('unique canonical player-game identities required')
    if not frame.position.isin(ROLES).all():raise ValueError('only registered offensive positions admitted')
    for name in ['actual','outcome','chart_lattice_002_v1','nick-chart-ppr-v1']:
        if name in frame and frame[name].notna().any():raise ValueError('target-game outcome cannot enter query')
    for name in FEATURES:
        if name not in frame:frame[name]=np.nan
        frame[name]=pd.to_numeric(frame[name],errors='coerce')
    reasons=[]
    for row in frame.to_dict('records'):
        cutoff=_clock(row['cutoff_utc']);kickoff=_clock(row['kickoff_utc']);source=_clock(row['feature_max_source_available_utc'],allow_missing=True)
        if cutoff>kickoff or source is not None and source>=cutoff:raise ValueError('future/equal-source or late cutoff invalid')
        history=row['f_player_games_prior'];reason=''
        if row.get('feature_query_available')is False:reason='missing_feature_query_position_prior'
        elif source is None:reason='unknown_feature_clock_position_prior'
        elif not np.isfinite(history)or history<=0:reason='cold_or_unknown_history_position_prior'
        if row['position']not in model.priors:reason='unseen_role_global_prior'
        reasons.append(reason)
    result=[]
    for i,row in frame.iterrows():
        result.append({'identity':{k:row[k]for k in IDENTITY},'target':TARGET,'contract':VERSION,
            'conditional_on':'played','source_policy_sha256':source_policy_sha256,'fallback':reasons[i],
            'cutoff_utc':str(row['cutoff_utc']),'kickoff_utc':str(row['kickoff_utc']),
            'feature_max_source_available_utc':None if pd.isna(row['feature_max_source_available_utc'])else str(row['feature_max_source_available_utc'])})
    for prior_only in [False,True]:
        indices=np.array([i for i,r in enumerate(reasons)if bool(r)==prior_only],dtype=int)
        if not len(indices):continue
        subset=frame.iloc[indices].reset_index(drop=True)
        for positions,law,_ in model.predict_batches(subset,batch_size=128,prior_only=prior_only):
            if law is None:raise ValueError('no supported chart prior; caller must abstain')
            means,medians=law.mean/SCALE,law.quantile(.5)/SCALE
            low,high=law.quantile(.1)/SCALE,law.quantile(.9)/SCALE
            for j,pos in enumerate(positions):
                out=result[int(indices[pos])];out.update(mean=float(means[j]),median=float(medians[j]),p10=float(low[j]),p90=float(high[j]),
                    support='signed0.02chartpointlattice',probability_law='empiricalleafplusfullsupportroleprior'if not prior_only else 'fullsupportroleprior')
    return result
