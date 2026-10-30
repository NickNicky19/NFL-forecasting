"""True prior-game target medians; no source access or execution on import.

Availability is admitted before game chronology. Missing, unknown and DNP slots
consume window positions; they never become zero targets. A recent-game mean
feature is never treated as the observations needed to calculate a median.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

VERSION = 'rec-tgt-recent-controls-v2-20261030'
KEYS = ['season', 'week', 'game_id', 'player_id']
CONTEXT = ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc']
WINDOWS = (3, 8)
METHODS = {3: 'TGT_RECENT3_LOWER_MEDIAN_CDF_FALLBACK',
           8: 'TGT_RECENT8_LOWER_MEDIAN_CDF_FALLBACK'}


def prepare_windows(query, history):
    """Inspect one identical-cutoff batch, with caller-filtered old values.

    Return each original query's valid target observations inside its last3/8
    roster-game slots plus source-parity metadata. No forecast is formed here.
    """
    q = query.copy().reset_index(drop=True)
    if q[KEYS + CONTEXT].isna().any(axis=None) or q.duplicated(KEYS).any():
        raise ValueError('complete unique query identities/context required')
    cutoffs = pd.to_datetime(q.cutoff_utc, utc=True, errors='raise')
    if cutoffs.nunique() != 1 or cutoffs.isna().any():
        raise ValueError('one explicit cutoff batch required')
    kickoffs = pd.to_datetime(q.kickoff_utc, utc=True, errors='raise')
    if kickoffs.isna().any() or (cutoffs > kickoffs).any():
        raise ValueError('forecast cutoff must not follow target kickoff')
    cutoff = cutoffs.iloc[0]
    h = history.copy()
    if h[KEYS].isna().any(axis=None) or h.duplicated(KEYS).any():
        raise ValueError('complete unique source identities required')
    if not h.participation_state.isin(['played', 'DNP', 'unknown']).fillna(False).all():
        raise ValueError('explicit valid source participation required')
    for name in ['kickoff_utc', 'outcome_available_utc']:
        h[name] = pd.to_datetime(h[name], utc=True, errors='raise')
        if h[name].isna().any() or not (h[name] < cutoff).all():
            raise ValueError('source values must already satisfy strictly earlier clock')
    if not (h.outcome_available_utc > h.kickoff_utc).all():
        raise ValueError('qualified source availability must follow its own game')
    values = pd.to_numeric(h.rec_tgt, errors='coerce')
    finite = np.isfinite(values)
    if (h.rec_tgt.notna() & ~finite).any() or (finite & ((values < 0) | (values % 1 != 0))).any():
        raise ValueError('invalid target values cannot be dropped or clipped')
    qualified = (h.participation_state.eq('played') & h.stats_observed.eq(True).fillna(False)
                 & h.official_physical_event.eq(True).fillna(False))
    if (finite & ~qualified).any():
        raise ValueError('unqualified finite target value cannot enter history')
    h['_target'] = values
    groups = {str(k): g.sort_values(['kickoff_utc', 'game_id'], kind='stable')
              for k, g in h.groupby('player_id', sort=False)}
    windows = {w: [] for w in WINDOWS}
    audit = []
    for _, row in q.iterrows():
        old = groups.get(str(row.player_id))
        entry = {**{k: row[k] for k in KEYS}, 'prior_slots': 0,
                 'maximum_used_availability_utc': None}
        for w in WINDOWS:
            chosen = old.iloc[-w:] if old is not None else h.iloc[:0]
            if chosen.game_id.eq(row.game_id).any():
                raise ValueError('target game present in its prior window')
            valid = chosen.loc[chosen.participation_state.eq('played') & chosen._target.notna(), '_target']
            v = valid.to_numpy(float)
            windows[w].append(v)
            entry['n' + str(w)] = len(v)
            entry['mean' + str(w)] = float(v.mean()) if len(v) else np.nan
            entry['slot_count' + str(w)] = len(chosen)
            entry['unknown_slots' + str(w)] = int(chosen.participation_state.eq('unknown').sum())
            entry['DNP_slots' + str(w)] = int(chosen.participation_state.eq('DNP').sum())
        if old is not None and len(old):
            entry['prior_slots'] = len(old)
            entry['maximum_used_availability_utc'] = old.iloc[-8:].outcome_available_utc.max().isoformat()
        audit.append(entry)
    return windows, pd.DataFrame(audit)


def parity_audit(query, audit, tolerance=1e-10):
    if not query[KEYS].reset_index(drop=True).equals(audit[KEYS].reset_index(drop=True)):
        raise ValueError('source parity query order changed')
    result = {}
    for w in WINDOWS:
        source_count = audit['n' + str(w)].to_numpy(float)
        cached_count = pd.to_numeric(query['f_player_targets_n' + str(w)], errors='coerce').to_numpy(float)
        count_equal = np.isfinite(cached_count) & (source_count == cached_count)
        source_mean = audit['mean' + str(w)].to_numpy(float)
        cached_mean = pd.to_numeric(query['f_player_targets_mean' + str(w)], errors='coerce').to_numpy(float)
        both = np.isfinite(source_mean) & np.isfinite(cached_mean)
        mean_equal = ((np.isnan(source_mean) & np.isnan(cached_mean)) |
                      (both & (np.abs(source_mean - cached_mean) <= tolerance)))
        result[str(w)] = {'query_rows': len(query), 'count_mismatches': int((~count_equal).sum()),
                          'mean_mismatches': int((~mean_equal).sum()),
                          'maximum_finite_mean_difference': float(np.abs(source_mean[both] - cached_mean[both]).max()) if both.any() else None,
                          'mean_tolerance': tolerance, 'zero_valid_value_windows': int((source_count == 0).sum()),
                          'unknown_slots': int(audit['unknown_slots' + str(w)].sum()),
                          'DNP_slots': int(audit['DNP_slots' + str(w)].sum())}
    return result


def forecast_rows(query, windows, frozen_cdf, window):
    """Point-only lower empirical median, with a truthful CDF-median fallback."""
    if window not in WINDOWS:
        raise ValueError('only two declared fixed windows')
    if not query[KEYS].reset_index(drop=True).equals(frozen_cdf[KEYS].reset_index(drop=True)):
        raise ValueError('exact original CDF key order required for fallback')
    result = query[KEYS + CONTEXT].copy().reset_index(drop=True)
    result['target'] = 'rec_tgt'
    result['method'] = METHODS[window]
    result['conditional_on'] = 'played'
    result['distribution'] = 'NONE_POINT_ONLY'
    result['point_semantics'] = 'lower_empirical_median_of_valid_targets_in_last_roster_game_slots_CDF_lower_median_fallback'
    result['mean'] = np.nan
    result['median'] = np.nan
    result['fallback'] = ''
    for i, v in enumerate(windows[window]):
        if len(v):
            result.loc[i, 'median'] = np.sort(v)[(len(v) - 1) // 2]
        else:
            value = pd.to_numeric(pd.Series([frozen_cdf.iloc[i]['median']]), errors='coerce').iloc[0]
            if np.isfinite(value) and value >= 0 and value % 1 == 0:
                result.loc[i, 'median'] = value
                result.loc[i, 'fallback'] = 'NO_QUALIFIED_RECENT_TARGETS_FROZEN_CDF_LOWER_MEDIAN'
            else:
                result.loc[i, 'fallback'] = 'NO_RECENT_TARGETS_OR_VALID_FROZEN_CDF_MEDIAN_ABSTAIN'
    return result


def paired_medians(frame, candidate, control='TGT_CDF_BASE', control_column='median', cluster='game_id'):
    if cluster not in ('game_id', 'week') or control_column not in ('median', 'mean'):
        raise ValueError('registered comparison only')
    a = frame.loc[frame.method.eq(candidate), KEYS + ['median', 'actual', 'participation_state']].rename(columns={'median': 'candidate'})
    b = frame.loc[frame.method.eq(control), KEYS + [control_column]].rename(columns={control_column: 'control'})
    rows = a.merge(b, on=KEYS, validate='one_to_one')
    valid = rows.participation_state.eq('played') & np.isfinite(rows.actual) & np.isfinite(rows.candidate) & np.isfinite(rows.control)
    rows = rows.loc[valid].copy()
    rows['difference'] = np.abs(rows.candidate - rows.actual) - np.abs(rows.control - rows.actual)
    rows['n'] = 1
    grouped = rows.groupby(cluster, sort=True)[['difference', 'n']].sum().to_numpy(float)
    interval = None
    if len(grouped) >= 8:
        index = np.random.default_rng(1703).integers(len(grouped), size=(500, len(grouped)))
        samples = grouped[index].sum(axis=1)
        interval = np.quantile(samples[:, 0] / samples[:, 1], [.025, .975]).tolist()
    loss_a = float(np.abs(rows.candidate - rows.actual).mean()) if len(rows) else None
    loss_b = float(np.abs(rows.control - rows.actual).mean()) if len(rows) else None
    return {'candidate': candidate, 'candidate_output': 'lower_empirical_count_median', 'control': control,
            'control_output': control_column, 'score': 'MAE', 'rows': len(rows), 'cluster': cluster,
            'clusters': len(grouped), 'candidate_loss': loss_a, 'control_loss': loss_b,
            'candidate_minus_control': float(rows.difference.mean()) if len(rows) else None,
            'relative_improvement_percent': 100 * (loss_b - loss_a) / loss_b if loss_b else None,
            'interval95': interval, 'minimum_clusters': 8, 'bootstrap_replicates': 500, 'seed': 1703}
