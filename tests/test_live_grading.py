from pathlib import Path

import pytest

from nfl_lab.live import grade_saved
from nfl_lab.state import records,resolved_outcomes,save


def fixture(tmp_path,monkeypatch,primary=None,supplement=0,*,final=True,context_error=False):
    state=tmp_path/'state'
    row=dict(player_id='sleeper:1',sleeper_id='1',game_id='espn:1',target='rec',season=2026,week=6,
             team='A',opponent='B',kickoff_utc='2026-10-18T17:00:00Z')
    save(state,'forecasts',{'rows':[row]})
    receipt={'sha256':'a'*64,'retrieved_utc':'2026-10-22T12:00:00Z'}
    board={'season':{'type':2,'year':2026},'week':{'number':6},'events':[{
        'id':'1','date':row['kickoff_utc'],'competitions':[{'competitors':[
            {'homeAway':'home','team':{'abbreviation':'A'}},
            {'homeAway':'away','team':{'abbreviation':'B'}}],
            'status':{'type':{'completed':final,'name':'STATUS_FINAL' if final else 'STATUS_IN_PROGRESS'}}}]}]}
    def fetch(cache,name,url):
        if name.startswith('grade-schedule'):return board,receipt
        stats={'gp':1}
        if primary is not None:stats['rec']=primary
        return {'1':{'stats':stats,'team':'A','season':2026,'week':6}},receipt
    monkeypatch.setattr('nfl_lab.live.fetch',fetch)
    calls=[]
    def load(cache,seasons):
        calls.append(seasons)
        if context_error:raise ValueError('injected cached integrity error')
        return {'fixture':True,'receipts':{'players':{'sha256':'c'*64}}}
    def candidate(context,forecast,game,status_receipt):
        assert game['final'] is True and game['season']==2026 and game['week']==6
        assert forecast['player_id']=='sleeper:1'
        if forecast.get('identity_binding')=='conflicting_identity_cold_start':
            return {'supplement_status':'unsupported','gap_reason':'conflicting_frozen_provider_identity'}
        return {**{k:forecast[k] for k in ['player_id','game_id','target']},
                'actual':supplement,'participation_state':'played','source':'nflverse-cached-player-stats',
                'source_timestamp':None,'source_sha256':'b'*64,'observed_at':receipt['retrieved_utc'],
                'supplement_status':'supported','gap_reason':None}
    monkeypatch.setattr('nfl_lab.grading_sources.load_cached_grading_context',load)
    monkeypatch.setattr('nfl_lab.grading_sources.cached_nflverse_outcome',candidate)
    return state,calls


def test_cached_known_zero_supplements_sparse_missing_without_replacing_receipt(tmp_path,monkeypatch):
    state,calls=fixture(tmp_path,monkeypatch)
    result=grade_saved(state,tmp_path/'data',{})
    assert result['nflverse_supported']==1 and result['appended']==2
    assert calls==[[2026]]
    assert resolved_outcomes(state)[('sleeper:1','espn:1','rec')]=={'state':'played','actual':0}
    assert {r['source'] for r in records(state,'outcomes')}=={'sleeper-stats-nfl','nflverse-cached-player-stats'}


def test_cross_source_disagreement_remains_quarantined(tmp_path,monkeypatch):
    state,_=fixture(tmp_path,monkeypatch,primary=2,supplement=3)
    result=grade_saved(state,tmp_path/'data',{})
    assert result['pending_outcomes']==1 and result['outcome_coverage']['conflicts']==1
    assert resolved_outcomes(state)[('sleeper:1','espn:1','rec')]['state']=='unresolved_numeric_conflict'


def test_missing_cached_supplement_keeps_primary_and_limit(tmp_path,monkeypatch):
    state,_=fixture(tmp_path,monkeypatch,primary=2,context_error=True)
    result=grade_saved(state,tmp_path/'data',{})
    assert 'integrity error' in result['nflverse_limit']
    assert resolved_outcomes(state)[('sleeper:1','espn:1','rec')]['actual']==2


def test_no_completed_game_does_not_load_or_grade_cached_history(tmp_path,monkeypatch):
    state,calls=fixture(tmp_path,monkeypatch,final=False)
    result=grade_saved(state,tmp_path/'data',{})
    assert result['opportunities_checked']==0 and result['appended']==0 and calls==[]


def test_earlier_conflict_marker_survives_later_frozen_binding(tmp_path,monkeypatch):
    state,_=fixture(tmp_path,monkeypatch,primary=2)
    row=next(records(state,'forecasts'))['rows'][0]
    save(state,'forecasts',{'rows':[{**row,'identity_binding':'conflicting_identity_cold_start'}]})
    save(state,'forecasts',{'rows':[{**row,'identity_binding':'frozen_first_sleeper_binding'}]})
    grade_saved(state,tmp_path/'data',{})
    assert resolved_outcomes(state)[('sleeper:1','espn:1','rec')]['state']=='unresolved_identity_conflict'


def test_known_identity_conflict_stays_quarantined_when_optional_cache_fails(tmp_path,monkeypatch):
    state,_=fixture(tmp_path,monkeypatch,primary=2,context_error=True)
    row=next(records(state,'forecasts'))['rows'][0]
    save(state,'forecasts',{'rows':[{**row,'identity_binding':'conflicting_identity_cold_start'}]})
    result=grade_saved(state,tmp_path/'data',{})
    assert result['outcome_coverage']['conflicts']==1 and result['pending_outcomes']==1
    assert resolved_outcomes(state)[('sleeper:1','espn:1','rec')]['state']=='unresolved_identity_conflict'
