"""Official-weekly provider target labels with existing physical-event evidence.

This is a new exact source join, not a zero imputation or participation model.
The caller projects only approved2026REG source rows before calling.
"""
import numpy as np
import pandas as pd

VERSION='rec-tgt-raw-weekly-label-join-v2'
KEYS=['season','week','game_id','player_id']
ALIASES={'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'}


def qualify(raw,query,schedule,*,count_fields,yard_fields):
    if raw.duplicated(KEYS).any() or query.duplicated(KEYS).any():
        raise ValueError('unique canonical source/query player-games required')
    if raw[KEYS+['team']].isna().any(axis=None) or query[KEYS+['team','opponent','position']].isna().any(axis=None):
        raise ValueError('complete canonical identity required')
    if not raw.season.eq(2026).all() or not raw.week.between(1,7).all() or not raw.season_type.eq('REG').all():
        raise ValueError('only declared2026REGW1–7 raw rows may enter')
    cal=schedule.loc[schedule.season.eq(2026)&schedule.week.between(1,7)&schedule.game_type.eq('REG')].copy()
    if cal.game_id.duplicated().any():
        raise ValueError('unique schedule game IDs required')
    if not raw.game_id.isin(cal.game_id).all() or not query.game_id.isin(cal.game_id).all():
        raise ValueError('schedule-authenticatedREGgame identity required')
    for frame in [raw,query]:
        check=frame[['season','week','game_id','team']].merge(cal[['season','week','game_id','home_team','away_team']],on=['season','week','game_id'],how='left',validate='many_to_one')
        team=check.team.replace(ALIASES)
        if not (team.eq(check.home_team.replace(ALIASES))|team.eq(check.away_team.replace(ALIASES))).all():
            raise ValueError('team/game/week mismatch')
    r=raw.copy()
    r['team']=r.team.replace(ALIASES)
    r['opponent_team']=r.opponent_team.replace(ALIASES)
    raw_target=pd.to_numeric(r.targets,errors='coerce')
    if (r.targets.notna()&~np.isfinite(raw_target)).any() or (raw_target.notna()&((raw_target<0)|(raw_target%1!=0))).any():
        raise ValueError('invalid raw target count; never silently drop or clip')
    count_names=[name for name in count_fields if name in r]
    yard_names=[name for name in yard_fields if name in r]
    if not count_names or not yard_names or 'targets' not in count_names:
        raise ValueError('original physical-action source schema required')
    # Same numerical predicate as permitted_source_features.physical_event_evidence.
    # Count values are appearance evidence only, not additional forecast targets.
    counts=r[count_names].apply(pd.to_numeric,errors='coerce')
    yards=r[yard_names].apply(pd.to_numeric,errors='coerce')
    physical=((counts.gt(0)&np.isfinite(counts)).any(axis=1)|(yards.ne(0)&np.isfinite(yards)).any(axis=1))
    r['_raw_target']=raw_target
    r['_physical']=physical
    retained=r[KEYS+['team','opponent_team','position','_raw_target','_physical']].rename(columns={'team':'_source_team','opponent_team':'_source_opponent','position':'_source_position'})
    labels=query[KEYS+['team','opponent','position','kickoff_utc','cutoff_utc']].merge(retained,on=KEYS,how='left',validate='one_to_one',indicator=True)
    present=labels._merge.eq('both')
    for own,other in [('team','_source_team'),('opponent','_source_opponent')]:
        known=present&labels[other].notna()
        if not labels.loc[known,own].replace(ALIASES).eq(labels.loc[known,other]).all():
            raise ValueError('exact source/query team or opponent mismatch')
    position_difference=present&labels._source_position.notna()&labels._source_position.ne(labels.position)
    # The cohort uses frozen query positions. Postgame source metadata cannot
    # retrospectively change which players enter the evaluation.
    played=present&labels._physical.eq(True).fillna(False)
    numeric=np.isfinite(pd.to_numeric(labels._raw_target,errors='coerce'))
    labels['stats_observed']=present
    labels['official_physical_event']=played
    labels['participation_state']=np.where(played,'played','unknown')
    labels['actual']=labels._raw_target.where(played,np.nan)
    labels['label_source_present']=present
    labels['source_position_differs_from_frozen_query']=position_difference
    labels['outcome_state']=np.where(~present,'missing_label_source',np.where(~played,'unknown_participation',np.where(~numeric,'played_missing_target',np.where(labels.actual.eq(0),'played_zero','played_nonzero'))))
    labels['label_missing_reason']=np.where(~present,'OFFICIAL_WEEKLY_PLAYER_GAME_ROW_ABSENT',np.where(~played,'NO_POSITIVE_OFFICIAL_PHYSICAL_EVIDENCE',np.where(~numeric,'TARGET_STATISTIC_MISSING','')))
    audit={'source_stat_row_count':len(raw),'query_rows':len(query),'source_rows_joined':int(present.sum()),'missing_source_rows':int((~present).sum()),'source_position_differences_retained':int(position_difference.sum()),'raw_zero_without_played_evidence_quarantined':int((present&~played&labels._raw_target.eq(0)).sum()),'raw_nonmissing_unknown_target_quarantined':int((present&~played&numeric).sum()),'count_fields_used':count_names,'signed_fields_used':yard_names,'raw_primary_rows_outside_fixed_query':int(raw.loc[raw.position.isin(['RB','WR','TE'])].merge(query[KEYS],on=KEYS,how='left',indicator=True)._merge.eq('left_only').sum()),'outcome_states':{str(k):int(v) for k,v in labels.outcome_state.value_counts(dropna=False).items()}}
    labels=labels.drop(columns=['_source_team','_source_opponent','_source_position','_raw_target','_physical','_merge'])
    return labels,audit


def summarize(frame):
    if not frame.participation_state.isin(['played','DNP','unknown']).fillna(False).all():
        raise ValueError('explicit valid participation state required')
    actual=pd.to_numeric(frame.actual,errors='coerce')
    played=frame.participation_state.eq('played')
    supported=played&np.isfinite(actual)
    if (supported&((actual<0)|(actual%1!=0))).any():
        raise ValueError('invalid finite target count')
    zero=supported&actual.eq(0)
    if not frame.loc[supported,'stats_observed'].eq(True).fillna(False).all() or not frame.loc[supported,'official_physical_event'].eq(True).fillna(False).all():
        raise ValueError('unqualified source/participation cannot produce a target label')
    return {'planned':len(frame),'supported':int(supported.sum()),'games':int(frame.loc[supported,'game_id'].nunique()),'weeks':int(frame.loc[supported,'week'].nunique()),'players':int(frame.loc[supported,'player_id'].nunique()),'participation':{str(k):int(v) for k,v in frame.participation_state.value_counts(dropna=False).items()},'played_zero':int(zero.sum()),'played_missing':int((played&~np.isfinite(actual)).sum()),'source_missing':int(frame.label_source_present.eq(False).sum()),'source_position_differences_retained':int(frame.source_position_differs_from_frozen_query.eq(True).sum()),'outcome_states':{str(k):int(v) for k,v in frame.outcome_state.value_counts(dropna=False).items()},'source_and_physical_zero_evidence':True}


def check_fictional():
    raw=pd.DataFrame([dict(season=2026,week=1,game_id='g',player_id='p',team='T',opponent_team='O',position='TE',season_type='REG',targets=0,carries=1,receiving_yards=0),dict(season=2026,week=1,game_id='g',player_id='u',team='T',opponent_team='O',position='WR',season_type='REG',targets=0,carries=0,receiving_yards=0)])
    q=pd.DataFrame([dict(season=2026,week=1,game_id='g',player_id=p,team='T',opponent='O',position='WR',kickoff_utc='2026-09-10T00:20:00Z',cutoff_utc='2026-09-09T22:50:00Z') for p in ['p','u','missing']])
    cal=pd.DataFrame([dict(season=2026,week=1,game_id='g',home_team='T',away_team='O',game_type='REG')])
    labels,audit=qualify(raw,q,cal,count_fields=['targets','carries'],yard_fields=['receiving_yards'])
    assert labels.actual.iloc[0]==0 and labels.participation_state.iloc[0]=='played'
    assert np.isnan(labels.actual.iloc[1]) and labels.participation_state.iloc[1]=='unknown'
    assert labels.outcome_state.iloc[2]=='missing_label_source' and np.isnan(labels.actual.iloc[2])
    assert labels.position.iloc[0]=='WR' and audit['source_position_differences_retained']==1
    bad=raw.copy();bad.loc[0,'targets']=-1
    try:qualify(bad,q,cal,count_fields=['targets','carries'],yard_fields=['receiving_yards'])
    except ValueError:pass
    else:raise AssertionError('negative targets admitted')
    bad=raw.copy();bad.loc[0,'team']='OTHER'
    try:qualify(bad,q,cal,count_fields=['targets','carries'],yard_fields=['receiving_yards'])
    except ValueError:pass
    else:raise AssertionError('wrong source team admitted')
    assert summarize(labels)['supported']==1 and summarize(labels)['played_zero']==1
    return {'state':'PASS','fictional_checks':7,'NFL_rows':0}
