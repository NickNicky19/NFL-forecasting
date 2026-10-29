"""Pure 2025 original-fold reconstruction adapter, technical V2.

Only semantic substitutions in the two original functions: remove acquisition-
heavy relative data import and replace data.TARGETS by its authenticated literal
12-target tuple. Projection, sort, index, filters and clocks remain unchanged.
No NFL data, network, model, fitting or scoring occurs at import.
"""
NEW_YEARS, CACHED_YEARS = ((2020, 2021, 2025), (2022, 2023, 2024))
PERIODS = {year: list(range(1, 18 if year == 2020 else 19)) for year in range(2020, 2026)}
PERIODS[2026] = list(range(1, 7))
KEYS = ['season', 'week', 'game_id', 'player_id']
META = KEYS + ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc', 'outcome_available_utc', 'feature_max_source_available_utc', 'is_home']

TARGETS = ('pass_yd', 'pass_td', 'pass_cmp', 'pass_att', 'pass_int', 'rush_yd', 'rush_att', 'rec', 'rec_yd', 'rush_rec_yd', 'fantasy_ppr', 'anytime_td')

def read_partition(path, year, lane, schedule, *, score_allowed=False):
    """Project before semantic decoding; no unregistered period/POST can enter."""
    import pyarrow.dataset as ds
    if year not in (*NEW_YEARS, 2026) or lane not in {'train', 'query', 'labels'}:
        raise ValueError('registered annual partition/lane required')
    if lane == 'train' and year not in NEW_YEARS:
        raise ValueError('2026models are reuse-only')
    if lane == 'labels' and (not score_allowed):
        raise ValueError('target scoring requires the completed global forecast freeze')
    dataset = ds.dataset(path, format='parquet')
    names = dataset.schema.names
    metadata = [name for name in META if name in names]
    features = [name for name in names if name.startswith('f_')]
    labels = [name for name in (*TARGETS, 'rush_td', 'rec_td', 'participation_state', 'official_physical_event', 'participation_evidence', 'source_policy', 'stats_observed') if name in names]
    columns = metadata + (features if lane != 'labels' else []) + (labels if lane != 'query' else [])
    selected = schedule.loc[schedule.game_type.eq('REG') & (schedule.season.between(2019, year - 1) if lane == 'train' else schedule.season.eq(year))]
    if lane != 'train':
        selected = selected.loc[selected.week.isin(PERIODS[year])]
    allowed = selected.game_id.tolist()
    predicate = ds.field('game_id').isin(allowed)
    predicate &= (ds.field('season') >= 2019) & (ds.field('season') < year) if lane == 'train' else ds.field('season') == year
    if year == 2026:
        predicate &= ds.field('week').isin([1, 2, 3, 4, 5])
    for period in ('season_type', 'game_type'):
        if period in names:
            predicate &= ds.field(period) == 'REG'
    frame = dataset.to_table(columns=list(dict.fromkeys(columns)), filter=predicate).to_pandas()
    if frame.empty or frame[KEYS].isna().any(axis=None) or frame.duplicated(KEYS).any() or (not frame.game_id.isin(allowed).all()):
        raise ValueError('missing/duplicate/out-of-scope source partition')
    if lane == 'query':
        if set(TARGETS) & set(frame):
            raise AssertionError('query projection included target values')
        frame['participation_state'] = 'unknown'
    return frame.sort_values(['kickoff_utc', 'game_id', 'player_id'], kind='stable').reset_index(drop=True)

def fold(path, year, schedule):
    import pandas as pd
    from .cdf_engine import assert_clock_contract
    query = read_partition(path, year, 'query', schedule)
    train = read_partition(path, year, 'train', schedule)
    cutoff = pd.to_datetime(query.cutoff_utc, utc=True).min()
    keep = pd.to_datetime(train.outcome_available_utc, utc=True).lt(cutoff) & pd.to_datetime(train.kickoff_utc, utc=True).lt(cutoff)
    train = train.loc[keep].copy()
    assert_clock_contract(train)
    assert_clock_contract(query)
    if train.empty:
        raise ValueError('annual training warmup unavailable')
    return (train, query, cutoff.isoformat())
