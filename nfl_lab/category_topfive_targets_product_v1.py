"""Pure receiving-target product helpers for one declared frozen-history pilot.

No fitting, acquisition, deserialization or scoring occurs on import. Existing
mean features remain means; no target label is inferred from a reception line.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

VERSION = 'rec-tgt-provider-product-v1'
TARGET = 'rec_tgt'
KEYS = ['season', 'week', 'game_id', 'player_id']
CONTEXT = ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc']
PRIMARY_ROLES = ['RB', 'WR', 'TE']
METHODS = ['TGT_CDF_BASE', 'TGT_ROLE_PRIOR', 'TGT_RECENT3_MEAN', 'TGT_RECENT8_MEAN']


def attach_training_targets(original, labels):
    if original.duplicated(KEYS).any() or labels.duplicated(KEYS).any():
        raise ValueError('unique training identities required')
    if TARGET in original:
        raise ValueError('original base view unexpectedly contains new target')
    out = original.copy()
    keys = original[KEYS].copy()
    labels = labels.rename(columns={TARGET:'_new_target', 'team':'_target_team', 'position':'_target_position', 'participation_state':'_target_state'})
    merged = keys.merge(labels[KEYS+['_new_target','_target_team','_target_position','_target_state']], on=KEYS, how='left', validate='one_to_one')
    for original_name,new_name in [('team','_target_team'),('position','_target_position'),('participation_state','_target_state')]:
        if not original[original_name].astype(str).reset_index(drop=True).equals(merged[new_name].astype(str).reset_index(drop=True)):
            raise ValueError('training target identity/participation differs')
    values = pd.to_numeric(merged['_new_target'], errors='coerce').to_numpy(float)
    played = original.participation_state.eq('played').to_numpy()
    valid = np.isfinite(values)
    if ((valid & played) & ((values<0)|(values!=np.floor(values)))).any():
        raise ValueError('invalid finite count cannot be dropped')
    if (valid & ~played).any():
        raise ValueError('unqualified target numeric value cannot train')
    out[TARGET] = values
    return out


def recent_mean_rows(model, query, window):
    if window not in (3,8):
        raise ValueError('two declared recent windows only')
    result = query[KEYS+CONTEXT].copy()
    result['target'] = TARGET
    result['method'] = 'TGT_RECENT'+str(window)+'_MEAN'
    result['distribution'] = 'NONE_POINT_ONLY'
    result['point_semantics'] = 'recent_valid_target_mean_with_training_position_mean_fallback'
    result['conditional_on'] = 'played'
    result['mean'] = np.nan
    result['median'] = np.nan
    result['fallback'] = ''
    # Use the unchanged reception-CDF panel's explicitly documented aliases.
    # features.py assigns targets_* from the same rec_tgt rolling statistics.
    values = pd.to_numeric(query['f_player_targets_mean'+str(window)], errors='coerce').to_numpy(float)
    counts = pd.to_numeric(query['f_player_targets_n'+str(window)], errors='coerce').to_numpy(float)
    for i,role in enumerate(query.position.astype(str)):
        prior = model.priors.get(role, model.global_prior)
        if prior is None:
            result.iloc[i,result.columns.get_loc('fallback')] = 'no_supported_training_prior_abstain'
            continue
        if np.isfinite(values[i]) and values[i]>=0 and np.isfinite(counts[i]) and counts[i]>0:
            result.iloc[i,result.columns.get_loc('mean')] = values[i]
        else:
            result.iloc[i,result.columns.get_loc('mean')] = prior.mean
            result.iloc[i,result.columns.get_loc('fallback')] = 'missing_recent_targets_training_position_mean'
    return result


def metric(frame, column, *, integer_point=False):
    y = pd.to_numeric(frame.actual, errors='coerce')
    predicted = pd.to_numeric(frame[column], errors='coerce')
    played = frame.participation_state.eq('played')
    finite = np.isfinite(y)
    if (played & finite & ((y<0)|(y%1!=0))).any():
        raise ValueError('unsupported finite count')
    use = played & finite & np.isfinite(predicted)
    error = (predicted[use]-y[use]).to_numpy(float)
    absolute = np.abs(error)
    if integer_point and not np.equal(predicted[use], np.floor(predicted[use])).all():
        raise ValueError('declared lower count median is not integer')
    enough = bool(len(error))
    has_prediction = bool(np.isfinite(predicted).any())
    return {'planned':len(frame),'scored':len(error),'games':int(frame.loc[use,'game_id'].nunique()),'weeks':int(frame.loc[use,'week'].nunique()),'players':int(frame.loc[use,'player_id'].nunique()),'participation':{str(k):int(v) for k,v in frame.participation_state.value_counts(dropna=False).items()},'played_zero':int((use&y.eq(0)).sum()),'played_missing':int((played&~finite).sum()),'fallbacks':int(frame.fallback.fillna('').ne('').sum()),'MAE':float(absolute.mean()) if enough else None,'MSE':float((error**2).mean()) if enough else None,'RMSE':float(np.sqrt((error**2).mean())) if enough else None,'bias':float(error.mean()) if enough else None,'p90_AE':float(np.quantile(absolute,.9)) if enough else None,'p95_AE':float(np.quantile(absolute,.95)) if enough else None,'strict_error_lt1':float((absolute<1).mean()) if enough else None,'inclusive_error_le1':float((absolute<=1).mean()) if enough else None,'exact_count':float((error==0).mean()) if enough and integer_point else None,'exact_count_reason':None if integer_point and has_prediction else ('OUTPUT_NOT_PRODUCED' if not has_prediction else 'MEAN_OR_POINT_NOT_ROUNDED_OR_REGISTERED_AS_INTEGER'),'no_score_reason':None if enough else ('OUTPUT_NOT_PRODUCED' if not has_prediction else 'NO_SUPPORTED_LABEL_AND_PREDICTION_OVERLAP')}


def paired(frame, control, *, cluster):
    if cluster not in ('game_id','week'):
        raise ValueError('registered clusters only')
    candidate = frame.loc[frame.method.eq('TGT_CDF_BASE'),KEYS+['median','actual','participation_state']].rename(columns={'median':'candidate'})
    comparator = frame.loc[frame.method.eq(control),KEYS+['mean']].rename(columns={'mean':'control'})
    rows = candidate.merge(comparator,on=KEYS,validate='one_to_one')
    good = rows.participation_state.eq('played')&np.isfinite(rows.actual)&np.isfinite(rows.candidate)&np.isfinite(rows.control)
    rows = rows.loc[good].copy()
    rows['difference']=(rows.candidate-rows.actual).abs()-(rows.control-rows.actual).abs()
    rows['n']=1
    summed=rows.groupby(cluster,sort=True)[['difference','n']].sum().to_numpy(float)
    n=len(summed);interval=None
    if n>=8:
        index=np.random.default_rng(1703).integers(n,size=(500,n))
        sums=summed[index].sum(axis=1)
        interval=np.quantile(sums[:,0]/sums[:,1],[.025,.975]).tolist()
    candidate_loss=float((rows.candidate-rows.actual).abs().mean()) if len(rows) else None
    control_loss=float((rows.control-rows.actual).abs().mean()) if len(rows) else None
    return {'candidate':'TGT_CDF_BASE','candidate_output':'lower_count_median','control':control,'control_output':'unrounded_mean','score':'MAE','rows':len(rows),'clusters':n,'cluster':cluster,'candidate_loss':candidate_loss,'control_loss':control_loss,'candidate_minus_control':float(rows.difference.mean()) if len(rows) else None,'relative_improvement_percent':100*(control_loss-candidate_loss)/control_loss if control_loss else None,'interval95':interval,'minimum_clusters':8,'bootstrap_replicates':500,'seed':1703,'scope':'Point-display comparison; incompatible functionals remain honestly labeled, no probability claim'}


def proper(frame):
    rows=frame.loc[frame.participation_state.eq('played')&frame.actual.notna()]
    if not len(rows):
        return {'CRPS':None,'log_loss':None,'reason':'NO_SUPPORTED_LABELS'}
    if rows.crps.isna().any() or rows.log_score.isna().any() or np.isneginf(rows.log_score).any():
        raise ValueError('all eligible proper-score rows required')
    impossible=int(np.isposinf(rows.log_score).sum())
    return {'CRPS':float(rows.crps.mean()),'log_loss':{'state':'POSITIVE_INFINITY' if impossible else 'FINITE','value':None if impossible else float(rows.log_score.mean()),'positive_infinite_rows':impossible,'denominator':len(rows),'impossible_events_retained':True},'calibration':'NOT_ESTABLISHED; no authenticated target offering lines','conditional_on':'played'}


def check_fictional():
    original=pd.DataFrame([dict(season=2025,week=1,game_id='a',player_id='p',team='T',position='WR',participation_state='played',base=3)])
    labels=original[KEYS+['team','position','participation_state']].copy();labels[TARGET]=0
    joined=attach_training_targets(original,labels)
    assert joined[TARGET].iloc[0]==0 and joined.base.iloc[0]==3
    bad=labels.copy();bad[TARGET]=-1
    try:attach_training_targets(original,bad)
    except ValueError:pass
    else:raise AssertionError('negative target admitted')
    changed=labels.copy();changed.team='OTHER'
    try:attach_training_targets(original,changed)
    except ValueError:pass
    else:raise AssertionError('target identity drift admitted')
    frame=pd.DataFrame([dict(season=2026,week=1,game_id='a',player_id='p',actual=0,participation_state='played',fallback='',mean=.5,median=0)])
    mean=metric(frame,'mean');median=metric(frame,'median',integer_point=True)
    assert mean['MAE']==.5 and mean['exact_count'] is None and median['exact_count']==1
    class Prior:
        mean=2.5
    class Model:
        priors={'WR':Prior()}
        global_prior=Prior()
    q=pd.DataFrame([dict(season=2026,week=1,game_id='q',player_id='p',team='T',opponent='O',position='WR',kickoff_utc='2026-09-10T00:20:00Z',cutoff_utc='2026-09-09T22:50:00Z',f_player_targets_mean3=4.,f_player_targets_n3=2.,f_player_targets_mean8=np.nan,f_player_targets_n8=0.)])
    recent3=recent_mean_rows(Model(),q,3)
    recent8=recent_mean_rows(Model(),q,8)
    assert recent3['mean'].iloc[0]==4. and recent3.fallback.iloc[0]==''
    assert recent8['mean'].iloc[0]==2.5 and recent8.fallback.iloc[0]=='missing_recent_targets_training_position_mean'
    q['rec_tgt']=999
    assert recent_mean_rows(Model(),q,3)['mean'].iloc[0]==4.
    return {'state':'PASS','fictional_checks':8,'NFL_rows':0}
