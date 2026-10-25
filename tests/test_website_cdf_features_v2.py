"""Fictional source/identity/window checks; no model fits or real outcomes."""
import numpy as np
import pandas as pd
import pytest

from nfl_lab import data, features
from nfl_lab.website_cdf_features_v2 import construct_query, normalized_source_proof


def row(season, week, kickoff, value, *, player='00-0000001', team='A', state='played'):
    kickoff=pd.Timestamp(kickoff)
    result={'season':season,'week':week,'game_id':f'{season}-g{week}-{team}','player_id':player,
            'position':'QB','team':team,'opponent':'B','kickoff_utc':kickoff,
            'outcome_available_utc':kickoff+pd.Timedelta(days=7),'participation_state':state,
            'is_home':1,'roster_status':'INA' if state=='DNP' else 'ACT','stats_observed':state=='played'}
    result.update({name:np.nan for name in features.PLAYER_STATS})
    result.update({'team_stat_'+name:40. for name in features.TEAM_STATS})
    result['rush_yd']=value
    return result


def fixture():
    old=pd.DataFrame([row(2025,17,'2025-12-28T17:00Z',100)])
    prior=pd.DataFrame([row(2026,w,date,value,state=state) for w,date,value,state in [
        (1,'2026-09-13T17:00Z',0,'played'),(2,'2026-09-20T17:00Z',np.nan,'unknown'),
        (3,'2026-09-27T17:00Z',np.nan,'DNP'),(4,'2026-10-04T17:00Z',-3,'played'),
        (5,'2026-10-11T17:00Z',999,'played')]])
    query=pd.DataFrame([{'season':2026,'week':6,'game_id':'original-espn-6','player_id':'sleeper:1',
            'canonical_player_id':'00-0000001','position':'QB','team':'A','opponent':'B',
            'kickoff_utc':pd.Timestamp('2026-10-18T17:00Z'),'cutoff_utc':pd.Timestamp('2026-10-18T10:48:59Z'),
            'outcome_available_utc':pd.Timestamp('2026-10-25T17:00Z'),'f_is_home':1}])
    return old,prior,query


def test_exact_mapping_preserves_zero_unknown_dnp_and_seven_day_windows():
    query,trace=construct_query(*fixture())
    result=query.iloc[0]
    assert result.player_id=='sleeper:1'
    assert result.f_player_games_prior==5
    assert result.f_player_rush_yd_mean3==-3
    assert result.f_player_rush_yd_n3==1
    assert result.f_player_rush_yd_mean8==pytest.approx(97/3)
    assert result.f_player_rush_yd_n8==3
    assert result.f_player_play_rate8==.75
    assert result.f_player_known_participation_n8==4
    assert '2026-g5-A' not in trace.iloc[0].last8_source_rows


def test_current_team_and_output_identity_remain_original_across_trade_history():
    old,prior,queries=fixture()
    prior.loc[prior.week.eq(1),'team']='C'
    result,_=construct_query(old,prior,queries)
    assert result.iloc[0].team=='A'
    assert result.iloc[0].opponent=='B'
    assert result.iloc[0].player_id=='sleeper:1'
    assert result.iloc[0].f_player_games_prior==5
    assert result.iloc[0].f_is_home==1


def test_unlinked_identity_is_cold_and_target_week_source_rejected_before_builder():
    old,prior,queries=fixture()
    queries['canonical_player_id']=None
    result,_=construct_query(old,prior,queries)
    assert result.iloc[0].f_player_games_prior==0
    assert np.isnan(result.iloc[0].f_player_rush_yd_mean3)
    prior.loc[prior.index[-1],'week']=6
    with pytest.raises(ValueError,match='source period'):
        construct_query(old,prior,queries)


def test_full_team_proof_requires_raw_all_position_totals():
    prior=pd.DataFrame([row(2026,1,'2026-09-13T17:00Z',5)])
    for field in data.STAT_MAP.values():
        prior[field]=0.
    prior['rush_yd']=5.
    raw=[]
    for pid,position,yards in [('00-0000001','QB',5),('00-0000002','OL',2)]:
        item={'season':2026,'week':1,'team':'A','player_id':pid,'position':position,'season_type':'REG'}
        item.update({('passing_interceptions' if key=='interceptions' else key):0 for key in data.STAT_MAP})
        item['rushing_yards']=yards
        raw.append(item)
    for field in features.TEAM_STATS:
        prior['team_stat_'+field]=7. if field=='rush_yd' else 0.
    proof,_=normalized_source_proof(prior,pd.DataFrame(raw))
    assert proof['raw_positions']=={'QB':1,'OL':1}
    with pytest.raises(ValueError,match='full-team totals differ'):
        normalized_source_proof(prior,pd.DataFrame(raw[:1]))
