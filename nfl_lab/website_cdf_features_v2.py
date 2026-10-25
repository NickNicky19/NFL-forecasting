"""Current-vintage prior-only query features from the training source family.

V1 is preserved.  This adapter reads 2026 statistics only through an explicit
season=2026/week<6 parquet filter, then uses the unchanged training feature
builder.  It never reads target outcomes, fits a model, or fetches data.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from nfl_lab import cdf_engine, data, features, website_cdf_features as v1

VERSION = "website-query-features-v2-normalized-prior-only-20261023"
ROOT = Path('/workspace/website-methods-research/resumed/website-cdf-20261023')
RAW = Path('/workspace/NFL-forecasting/data/raw')
PRIOR_CACHE = Path('/workspace/website-methods-research/category-work/anytime/private-grading-correction-1/processed/history.parquet')
PRIOR_SHA = '085319cb27144babee507d48a5f7f8e31ccd2a842e3e835f05bd61b6c9f0e853'
QUERY_V1_SHA = '07da36459d3361c06bb4bfd495a29afb3749dab3bff51f98cee0b7903a9a004b'
BASE_OPPORTUNITIES_SHA = '53635a814b34f46a128e1a8b5174f709f8fdb2e24f4e2103f20b007596cc8895'
RAW_PINS = {
    'stats_player_week_2026.parquet': '17c5e71586394a7786bba7f29e7606da83223f6defa2b76d7514895a36558cdd',
    'roster_weekly_2026.parquet': '951448fb9e22f11585f37593ce1e0bbcf2b0c01b13390559d2c9d773bb786c99',
    'snap_counts_2026.parquet': '715cad4c0619d89d400d3a57e79dd753bccc49d625a61cf7864bcd5038b3a4fa',
    'players.parquet': '35383262b6e2f41b6cf446eef319f9b501a9daa767dfa4d91e9ae2d88d635fe3',
    'schedules.csv': '6a7828f3aa5f0ba17cd365295489a09b861f4fa8eaa0f4c00c7c05ac652987e7',
}
ALIASES = {'LA':'LAR', 'STL':'LAR', 'SD':'LAC', 'OAK':'LV'}
KEYS = v1.KEYS
CONTEXT = ['position','team','opponent','kickoff_utc','cutoff_utc','outcome_available_utc']
PRIOR_FILTER = [('season','==',2026), ('week','<',6)]


def pin(path: Path, expected: str):
    if v1.sha(path) != expected:
        raise ValueError('pinned source changed: '+str(path))


def normalized_source_proof(prior: pd.DataFrame, raw_stats: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Verify explicit raw fields and all-position totals before source use."""
    for frame in (prior, raw_stats):
        if not (frame.season.eq(2026) & frame.week.between(1,5)).all():
            raise ValueError('2026 source outside strict prior filter')
    raw_stats = raw_stats.rename(columns={**data.STAT_MAP, 'passing_interceptions':'pass_int'}).copy()
    raw_stats['team'] = raw_stats.team.replace(ALIASES)
    if not raw_stats.season_type.eq('REG').all():
        raise ValueError('nonregular prior source')
    stats = list(data.STAT_MAP.values())
    keys = ['season','week','team','player_id']
    if raw_stats.duplicated(keys).any() or prior.duplicated(['game_id','player_id']).any():
        raise ValueError('duplicate prior source identity')
    observed = prior.loc[prior.stats_observed.eq(True), keys+stats]
    checked = observed.merge(raw_stats[keys+stats],on=keys,how='left',validate='one_to_one',suffixes=('_cache','_raw'),indicator=True)
    if not checked._merge.eq('both').all():
        raise ValueError('normalized observed row missing exact raw source')
    for field in stats:
        left,right=checked[field+'_cache'],checked[field+'_raw']
        if not (left.eq(right)|(left.isna()&right.isna())).all():
            raise ValueError('normalized/raw source mismatch: '+field)
    if 'game_id' in raw_stats:
        games=prior.loc[prior.stats_observed.eq(True),keys+['game_id']].merge(raw_stats[keys+['game_id']],on=keys,validate='one_to_one',suffixes=('_cache','_raw'))
        if not games.game_id_cache.eq(games.game_id_raw).all():
            raise ValueError('normalized/raw game identity mismatch')
    # Do this before filtering positions or identities: defensive players,
    # linemen, specialists and every other source position contribute.
    expected = raw_stats.groupby(['season','week','team'])[features.TEAM_STATS].sum(min_count=1).sort_index()
    fields = ['team_stat_'+c for c in features.TEAM_STATS]
    if prior.groupby(['game_id','team'])[fields].nunique().gt(1).any(axis=None):
        raise ValueError('inconsistent repeated full-team totals')
    found = prior.groupby(['season','week','team'])[fields].first().rename(columns={'team_stat_'+c:c for c in features.TEAM_STATS}).sort_index()
    if not expected.index.equals(found.index) or not np.allclose(expected,found,rtol=0,atol=0,equal_nan=True):
        raise ValueError('full-team totals differ from all-position raw source')
    proof = {'raw_prior_rows':len(raw_stats),'raw_positions':raw_stats.position.value_counts().to_dict(),
             'normalized_prior_rows':len(prior),'raw_observed_rows_verified':len(checked),
             'full_team_games_verified':len(found),'full_team_source':'all raw source positions before player-position or identity filtering',
             'explicit_zero_counts':{c:int(prior[c].eq(0).sum()) for c in stats},
             'participation':prior.participation_state.value_counts().to_dict(),
             'eligibility':'cached training adapter union of ACT/INA eligible rosters, observed statistics, positive snaps; all unknown and DNP rows retained'}
    team_trace = found.reset_index()
    team_trace['source_raw_stats_sha256'] = RAW_PINS['stats_player_week_2026.parquet']
    team_trace['source_normalized_cache_sha256'] = PRIOR_SHA
    return proof, team_trace


def construct_query(old: pd.DataFrame, prior: pd.DataFrame, queries: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Use canonical IDs internally and restore original Sleeper output keys."""
    if not old.season.between(2019,2025).all() or not (prior.season.eq(2026)&prior.week.between(1,5)).all():
        raise ValueError('feature source period violation')
    if not queries.season.eq(2026).all() or not queries.week.eq(6).all():
        raise ValueError('query period violation')
    sources = pd.concat([old,prior],ignore_index=True)
    sources['cutoff_utc'] = sources.kickoff_utc
    sources['fantasy_ppr'] = np.nan
    available = pd.to_datetime(sources.outcome_available_utc,utc=True)
    kickoff = pd.to_datetime(sources.kickoff_utc,utc=True)
    if not available.eq(kickoff+pd.Timedelta(days=7)).all():
        raise ValueError('source does not use fixed training seven-day lag')
    queries = queries.copy()
    queries['_output_player_id'] = queries.player_id
    queries['_query_row'] = np.arange(len(queries))
    queries['player_id'] = queries.canonical_player_id.fillna(queries.player_id)
    queries['participation_state'] = 'unknown'
    queries['is_home'] = queries.pop('f_is_home')
    for field in features.PLAYER_STATS + ['team_stat_'+c for c in features.TEAM_STATS]:
        queries[field] = np.nan
    # The caller's source read is filtered before this function.  A second
    # period assertion here makes passing a full cache fail before building.
    combined = pd.concat([sources,queries],ignore_index=True)
    result = features.build_features(combined)
    query = result.loc[result._query_row.notna()].sort_values('_query_row').copy()
    query['player_id'] = query._output_player_id
    output_cols = KEYS+CONTEXT+['canonical_player_id','participation_state','feature_max_source_available_utc']
    output_cols += [c for c in query if c.startswith('f_')]
    query = query[output_cols].reset_index(drop=True)
    traces=[]
    groups={pid:g.sort_values(['outcome_available_utc','kickoff_utc']) for pid,g in sources.groupby('player_id',sort=False)}
    for row in queries.to_dict('records'):
        eligible=groups.get(row['player_id'],sources.iloc[:0])
        eligible=eligible.loc[pd.to_datetime(eligible.outcome_available_utc,utc=True)<pd.Timestamp(row['cutoff_utc'])]
        history_fields=['season','week','game_id','team','opponent','kickoff_utc','outcome_available_utc','participation_state']
        traces.append({'player_id':row['_output_player_id'],'canonical_player_id':row['canonical_player_id'],
                       'prior_rows':len(eligible),'last3_source_rows':eligible.tail(3)[history_fields].to_json(orient='records',date_format='iso'),
                       'last8_source_rows':eligible.tail(8)[history_fields].to_json(orient='records',date_format='iso'),
                       'cutoff_utc':row['cutoff_utc'],'kickoff_utc':row['kickoff_utc'],
                       'source_old_cache_sha256':v1.HISTORICAL_FEATURES_SHA256,'source_2026_cache_sha256':PRIOR_SHA,
                       'identity_cohort_sha256':v1.IDENTITY_COHORT_SHA256})
    trace=pd.DataFrame(traces)
    if not np.array_equal(query.f_player_games_prior.to_numpy(),trace.prior_rows.to_numpy()):
        raise ValueError('feature player support differs from strict source trace')
    # build_features records wall time in attrs.  It is useful profiling
    # metadata, but cannot be part of a deterministic frozen parquet body.
    query.attrs.clear()
    return query,trace


def run() -> dict:
    pin(ROOT/'query-features.parquet',QUERY_V1_SHA)
    pin(ROOT/'opportunities.parquet',BASE_OPPORTUNITIES_SHA)
    pin(v1.HISTORICAL_FEATURES,v1.HISTORICAL_FEATURES_SHA256)
    pin(v1.IDENTITY_COHORT,v1.IDENTITY_COHORT_SHA256)
    pin(PRIOR_CACHE,PRIOR_SHA)
    receipts={}
    for name,expected in RAW_PINS.items():
        pin(RAW/name,expected)
        receipt=json.loads(Path(str(RAW/name)+'.receipt.json').read_text())
        if receipt['sha256']!=expected:
            raise ValueError('raw receipt hash mismatch')
        receipts[name]={'path':str(RAW/name),'sha256':expected,'receipt_sha256':v1.sha(Path(str(RAW/name)+'.receipt.json')),
                        'retrieved_utc':receipt.get('retrieved_utc'),'original_publication_utc':receipt.get('original_publication_utc'),
                        'vintage':receipt.get('vintage')}
    cols=KEYS+['team','opponent','position','kickoff_utc','outcome_available_utc','is_home','participation_state','roster_status','stats_observed']
    cols+=list(dict.fromkeys(features.PLAYER_STATS))+['team_stat_'+c for c in features.TEAM_STATS]
    old=pd.read_parquet(v1.HISTORICAL_FEATURES,columns=cols)
    # Target-week statistics are never materialized into this process.
    prior=pd.read_parquet(PRIOR_CACHE,columns=cols,filters=PRIOR_FILTER)
    raw_map={('passing_interceptions' if k=='interceptions' else k):v for k,v in data.STAT_MAP.items()}
    raw_cols=['season','week','game_id','team','player_id','position','season_type',*raw_map]
    raw_stats=pd.read_parquet(RAW/'stats_player_week_2026.parquet',columns=raw_cols,filters=PRIOR_FILTER)
    proof,team_trace=normalized_source_proof(prior,raw_stats)
    roster_cols=['season','week','team','gsis_id','position','status']
    roster=pd.read_parquet(RAW/'roster_weekly_2026.parquet',columns=roster_cols,filters=PRIOR_FILTER)
    roster=roster.loc[roster.position.isin(data.POSITIONS)&roster.status.isin(['ACT','INA'])].copy()
    roster['team']=roster.team.replace(ALIASES)
    roster=roster.rename(columns={'gsis_id':'player_id','status':'roster_status'}).dropna(subset=['player_id'])
    roster_keys=['season','week','team','player_id']
    roster=roster.drop_duplicates(roster_keys)
    membership=prior[roster_keys+['roster_status']].merge(roster[roster_keys+['roster_status']],on=roster_keys,how='left',validate='one_to_one',suffixes=('_cache','_raw'),indicator=True)
    if not membership._merge.eq('both').all() or not membership.roster_status_cache.eq(membership.roster_status_raw).all():
        raise ValueError('normalized eligibility/membership differs from exact raw ACT/INA roster')
    proof['raw_ACT_INA_roster_rows_verified']=len(membership)
    queries=pd.read_parquet(ROOT/'query-features.parquet',columns=KEYS+CONTEXT+['canonical_player_id','f_is_home','original_board_generated_at','calendar_generated_at'])
    cohort=pd.read_parquet(v1.IDENTITY_COHORT,columns=['player_id','canonical_player_id','identity_binding']).drop_duplicates()
    exact=cohort.loc[cohort.identity_binding.eq('exact_current_vintage_sleeper_gsis')]
    if exact.player_id.duplicated().any() or exact.canonical_player_id.duplicated().any():
        raise ValueError('ambiguous exact identity crosswalk')
    mapped=queries.merge(exact[['player_id','canonical_player_id']],on='player_id',how='left',validate='one_to_one',suffixes=('','_checked'))
    if not (mapped.canonical_player_id.eq(mapped.canonical_player_id_checked)|(mapped.canonical_player_id.isna()&mapped.canonical_player_id_checked.isna())).all():
        raise ValueError('query canonical identity changed')
    # Prior calendar validates actual teams/opponents/kickoffs independently of
    # target statistics.  Only identity schedule columns are read from CSV.
    calendar_path=Path('/workspace/website-methods-research/recovered/d46-teams.json')
    calendar_sha='e9a117d8ac49f75619c35ed2d6d96e16890c9e95f50a011224e015d0d42e3272'
    pin(calendar_path,calendar_sha)
    calendar=v1.document(calendar_path)
    schedule={(int(g['w']),team):(str(g['id']),pd.Timestamp(g['kickoff']),g['away'] if team==g['home'] else g['home'])
              for g in calendar['schedule'] for team in (g['home'],g['away'])}
    expected_team_games={(2026,w,team) for w,team in schedule if 1<=w<6}
    observed_team_games=set(team_trace[['season','week','team']].itertuples(index=False,name=None))
    if expected_team_games!=observed_team_games:
        raise ValueError('full prior calendar team-game closure incomplete')
    proof['calendar_team_game_closure_verified']=len(expected_team_games)
    for row in prior[['week','team','opponent','kickoff_utc']].drop_duplicates().to_dict('records'):
        _,kick,opponent=schedule[(int(row['week']),row['team'])]
        if kick!=pd.Timestamp(row['kickoff_utc']) or opponent!=row['opponent']:
            raise ValueError('prior normalized/calendar context mismatch')
    query,trace=construct_query(old,prior,queries)
    query['feature_max_assumed_history_available_utc']=query.feature_max_source_available_utc
    query['feature_max_source_available_utc']=[max([pd.Timestamp(board),pd.Timestamp(cal)]+([pd.Timestamp(history)] if pd.notna(history) else []))
        for board,cal,history in zip(queries.original_board_generated_at,queries.calendar_generated_at,query.feature_max_assumed_history_available_utc)]
    query['identity_binding']=np.where(query.canonical_player_id.notna(),'exact_current_vintage_sleeper_gsis','unlinked_cold_role_prior')
    query['feature_adapter_version']=VERSION
    query['evidence_lane']='current-vintage counterfactual reconstruction; postgame source downloads; no original forecast or publication claim'
    query['source_clock_semantics']='strict kickoff+7d reconstruction assumption plus original board/calendar generation; historical public revision clock unknown'
    query['history_season_floor']=2019
    query['history_unknown_slots_preserved']=True
    query['original_board_generated_at']=queries.original_board_generated_at
    query['calendar_generated_at']=queries.calendar_generated_at
    cdf_engine.assert_clock_contract(query)
    if len(query)!=396 or query.duplicated(KEYS).any():
        raise ValueError('original player population changed')
    unlinked=query.canonical_player_id.isna()
    if unlinked.sum()!=3 or not query.loc[unlinked,'f_player_games_prior'].eq(0).all():
        raise ValueError('fixed unlinked cold role prior policy changed')
    query.to_parquet(ROOT/'query-features-v2.parquet',index=False)
    trace.to_parquet(ROOT/'query-feature-provenance-v2.parquet',index=False)
    team_trace.to_parquet(ROOT/'team-feature-provenance-v2.parquet',index=False)
    sources=pd.concat([old,prior],ignore_index=True)
    source_trace=sources[KEYS+['team','opponent','kickoff_utc','outcome_available_utc','participation_state','roster_status','stats_observed']].copy()
    source_trace['source_cache_sha256']=np.where(source_trace.season.eq(2026),PRIOR_SHA,v1.HISTORICAL_FEATURES_SHA256)
    source_trace.to_parquet(ROOT/'history-feature-provenance-v2.parquet',index=False)
    report={'version':VERSION,'query_rows':len(query),'original_opportunities':2083,'fits':0,'target_outcomes_loaded':False,
            '2026_parquet_read_filters':PRIOR_FILTER,'2026_raw_columns_read':raw_cols,'2026_roster_columns_read':roster_cols,'historical_columns_read':cols,
            'prior2026_proof':proof,'old_history_rows':len(old),'old_history_seasons':sorted(old.season.unique().tolist()),
            'exact_identity_bindings':int((~unlinked).sum()),'unlinked_cold_role_prior_players':query.loc[unlinked,'player_id'].tolist(),
            'query_players_with_2026_source_rows':int(prior.loc[prior.player_id.isin(query.canonical_player_id.dropna())].player_id.nunique()),
            'raw_source_receipts':receipts,'prior_normalized_cache':{'path':str(PRIOR_CACHE),'sha256':PRIOR_SHA},
            'old_source_cache':{'path':str(v1.HISTORICAL_FEATURES),'sha256':v1.HISTORICAL_FEATURES_SHA256},
            'identity_only_cohort':{'path':str(v1.IDENTITY_COHORT),'sha256':v1.IDENTITY_COHORT_SHA256},
            'original_saved_calendar':{'path':str(calendar_path),'sha256':calendar_sha},
            'nonmissing_features':{c:int(query[c].notna().sum()) for c in query if c.startswith('f_')},
            'source_clock_policy':'fixed seven-day lag; actual postgame retrieval timestamps retained; no authenticated historic publication/revision claim',
            'participation_policy':'retain every cached ACT/INA/stat/snap source row including unknown/DNP; never select only positive games; no invented off-roster game slots',
            'full_team_policy':'all32teams retained, raw all-position totals verified before any player selection; all62752historical rows retained for league/team/opponent context',
            'PPR_state':'blocked; no generic points labels imported',
            'v1_snapshot':{'query_sha256':QUERY_V1_SHA,'opportunities_sha256':BASE_OPPORTUNITIES_SHA,'executed_as_model_trial':False},
            'loader_hashes':{str(Path(module.__file__)):v1.sha(Path(module.__file__)) for module in (data,features,cdf_engine,v1)},
            'adapter_sha256':v1.sha(Path(__file__)),
            'outputs':{name:v1.sha(ROOT/name) for name in ['query-features-v2.parquet','query-feature-provenance-v2.parquet','team-feature-provenance-v2.parquet','history-feature-provenance-v2.parquet']}}
    (ROOT/'feature-coverage-v2.json').write_text(json.dumps(report,indent=2)+'\n')
    pin(ROOT/'query-features.parquet',QUERY_V1_SHA)
    pin(ROOT/'opportunities.parquet',BASE_OPPORTUNITIES_SHA)
    print(json.dumps({k:report[k] for k in ['version','query_rows','exact_identity_bindings','outputs','fits','target_outcomes_loaded']}))
    return report


if __name__=='__main__':
    run()
