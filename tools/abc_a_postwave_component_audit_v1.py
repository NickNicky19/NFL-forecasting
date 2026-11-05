"""Common-case accounting of retained carry forecasts; never a live predictor.

Actual-volume/share substitutions are explicitly POSTGAME_DIAGNOSTIC_ONLY.
No model deserialization, fitting, new football acquisition or pick alteration.
"""
from __future__ import annotations
import collections
import csv
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'reports/abc-championship/post-wave-5w-v1'


def main():
    begin = time.monotonic()
    cpu = time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (90, 91))
    resource.setrlimit(resource.RLIMIT_AS, (1610612736, 1610612736))
    signal.alarm(120)
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    from tools import abc_a_dynamic_carry_wave_v1 as base
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    store, _ = open_store(ROOT, allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO)
    destination = store.forward_root / 'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
    receipt = json.loads((ROOT / 'reports/abc-championship/predictive-improvement-01/completion-v3/SCORING_RECEIPT_V1.json').read_bytes())
    path = destination / 'GRADED_SCORECARD_V1.zip'
    store.validate_reference(path, receipt['sha256'])
    with zipfile.ZipFile(path) as z:
        numeric = json.loads(gzip.decompress(z.read('NUMERICAL_ROWS.json.gz')))
    _, source, _, _ = base.sources()
    columns = ['season', 'week', 'game_id', 'player_id', 'team', 'position', 'participation_state', 'rush_att', 'team_stat_rush_att']
    histories = []
    source_refs = []
    for ref in source['history_sources']:
        data = base.pin(ref)
        histories.append(pd.read_parquet(io.BytesIO(data), columns=columns))
        source_refs.append({'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    history = pd.concat(histories, ignore_index=True)
    if history.duplicated(['game_id', 'player_id']).any():
        raise ValueError('duplicate source player/game')
    totals = {}
    source_actual = {}
    for (year, game, team), frame in history.groupby(['season', 'game_id', 'team'], sort=False):
        values = pd.to_numeric(frame.team_stat_rush_att, errors='coerce').dropna().unique()
        if len(values) != 1 or not np.isfinite(values[0]) or values[0] < 0 or values[0] % 1:
            raise ValueError('incomplete/inconsistent all-position team total')
        totals[int(year), str(game), str(team)] = float(values[0])
        for row in frame.itertuples():
            if row.participation_state == 'played' and pd.notna(row.rush_att):
                source_actual[int(year), str(game), str(row.player_id)] = float(row.rush_att)
    groups = collections.defaultdict(list)
    for row in numeric:
        if row['arm'] in ['A2_DYNAMIC_ALLOCATION', 'S0_RECENCY_ALLOCATION']:
            groups[row['season'], row['game_id'], row['team'], row['arm']].append(row)
    component_rows = []
    group_rows = []
    coherence = {'groups': 0, 'max_share_error': 0., 'max_mean_conservation_error': 0.,
                 'max_saved_mean_error': 0., 'source_label_conflicts': 0}
    for (year, game, team, arm), rows in groups.items():
        if len({r['player_id'] for r in rows}) != len(rows):
            raise ValueError('duplicate allocation player')
        laws = [r['law'] for r in rows]
        if len({(x['shape'], x['rate'], x['other_probability']) for x in laws}) != 1:
            raise ValueError('inconsistent joint group')
        mu = laws[0]['shape'] / laws[0]['rate']
        psum = sum(x['allocation_share'] for x in laws)
        other = laws[0]['other_probability']
        share_error = abs(psum + other - 1)
        mean_error = abs(sum(r['mean'] for r in rows) + mu*other - mu)
        saved_error = max(abs(r['mean'] - mu*r['law']['allocation_share']) for r in rows)
        if share_error > 1e-10 or mean_error > 1e-8 or saved_error > 1e-8:
            raise ValueError('retained allocation does not conserve its full predicted total')
        coherence['groups'] += 1
        coherence['max_share_error'] = max(coherence['max_share_error'], share_error)
        coherence['max_mean_conservation_error'] = max(coherence['max_mean_conservation_error'], mean_error)
        coherence['max_saved_mean_error'] = max(coherence['max_saved_mean_error'], saved_error)
        total = totals.get((year, game, team))
        scored = [r for r in rows if r['actual'] is not None]
        missing = [r for r in rows if r['actual'] is None]
        conflicts = [r for r in scored if (year, game, r['player_id']) in source_actual and source_actual[year, game, r['player_id']] != r['actual']]
        coherence['source_label_conflicts'] += len(conflicts)
        actual_sum = sum(r['actual'] for r in scored)
        if total is not None and actual_sum > total:
            raise ValueError('scored player credits exceed qualified team total')
        raw_key = 'recency_share' if arm == 'S0_RECENCY_ALLOCATION' else 'raw_share'
        raw_sum = sum(r['law'][raw_key] for r in rows)
        denominator = raw_sum + laws[0]['other_weight']
        if max(abs(r['law']['allocation_share'] - r['law'][raw_key]/denominator) for r in rows) > 1e-10:
            raise ValueError('saved normalization cannot be reconstructed')
        group_rows.append({'season': year, 'week': rows[0]['week'], 'game_id': game, 'team': team, 'arm': arm,
            'forecast_roster_RB': len(rows), 'scored_RB': len(scored), 'unknown_RB': len(missing),
            'forecast_team_mean': mu, 'actual_team_total': total, 'raw_RB_share_sum': raw_sum,
            'raw_other_weight': laws[0]['other_weight'], 'normalization_denominator': denominator,
            'other_probability': other, 'scored_player_probability': sum(r['law']['allocation_share'] for r in scored),
            'unknown_player_probability': sum(r['law']['allocation_share'] for r in missing),
            'known_RB_actual_sum': actual_sum,
            'actual_residual_other_or_unresolved': total-actual_sum if total is not None else None,
            'source_label_conflicts': len(conflicts)})
        for r in scored:
            p = r['law']['allocation_share']
            reason = 'TEAM_TOTAL_UNAVAILABLE' if total is None else 'ZERO_TEAM_TOTAL_RATIO_UNDEFINED' if total == 0 else 'SOURCE_LABEL_CONFLICT' if conflicts else None
            row = {'season': year, 'week': r['week'], 'game_id': game, 'player_id': r['player_id'], 'team': team,
                'arm': arm, 'actual': r['actual'], 'forecast_mean': r['mean'], 'forecast_team_mean': mu,
                'actual_team_total': total, 'allocation_share': p, 'raw_share': r['law'][raw_key],
                'other_probability': other, 'normalization_denominator': denominator,
                'fallback': r['fallback'], 'participation': r['participation'], 'outcome_version': r['outcome_version'],
                'common_component_missing_reason': reason, 'point_error': r['mean']-r['actual']}
            if reason is None:
                actual_share = r['actual']/total
                volume = (mu-total)*p
                allocation = total*(p-actual_share)
                if abs(row['point_error']-volume-allocation) > 1e-9:
                    raise ValueError('component identity failed')
                row.update(actual_share=actual_share, share_error=p-actual_share,
                    volume_error_contribution=volume, allocation_error_contribution=allocation,
                    POSTGAME_actual_volume_point=total*p, POSTGAME_actual_share_point=mu*actual_share)
            component_rows.append(row)
    def metrics(values):
        if not values:
            return {'n': 0, 'MAE': None, 'RMSE': None, 'bias': None, 'reason': 'No qualified matching rows'}
        a = np.asarray(values, float)
        return {'n': len(a), 'MAE': float(np.abs(a).mean()), 'RMSE': float(np.sqrt((a*a).mean())), 'bias': float(a.mean())}
    summaries = []
    for year in [2025, 2026]:
        for arm in ['A2_DYNAMIC_ALLOCATION', 'S0_RECENCY_ALLOCATION']:
            allrows = [r for r in component_rows if r['season'] == year and r['arm'] == arm]
            for weeks in [sorted({r['week'] for r in allrows}), *[[w] for w in sorted({r['week'] for r in allrows})]]:
                rr = [r for r in allrows if r['week'] in weeks]
                common = [r for r in rr if r['common_component_missing_reason'] is None]
                keys = {(r['season'], r['game_id'], r['team']) for r in common}
                gr = [r for r in group_rows if (r['season'], r['game_id'], r['team']) in keys and r['arm'] == arm]
                summaries.append({'season': year, 'weeks': weeks, 'arm': arm,
                    'original_scored_player_metrics': metrics([r['point_error'] for r in rr]),
                    'common_player_metrics': metrics([r['point_error'] for r in common]),
                    'common_team_metrics_unique_team_games': metrics([r['forecast_team_mean']-r['actual_team_total'] for r in gr]),
                    'common_team_games': len(gr), 'games': len({r['game_id'] for r in common}),
                    'volume_contribution_bias': float(np.mean([r['volume_error_contribution'] for r in common])) if common else None,
                    'allocation_contribution_bias': float(np.mean([r['allocation_error_contribution'] for r in common])) if common else None,
                    'predicted_share_mean': float(np.mean([r['allocation_share'] for r in common])) if common else None,
                    'actual_share_mean': float(np.mean([r['actual_share'] for r in common])) if common else None,
                    'raw_share_mean': float(np.mean([r['raw_share'] for r in common])) if common else None,
                    'normalization_denominator_mean': float(np.mean([r['normalization_denominator'] for r in gr])) if gr else None,
                    'other_probability_mean': float(np.mean([r['other_probability'] for r in gr])) if gr else None,
                    'forecast_mass_to_unknown_RB_mean': float(np.mean([r['unknown_player_probability'] for r in gr])) if gr else None,
                    'fallback_common_player_metrics': metrics([r['point_error'] for r in common if r['fallback']]),
                    'nonfallback_common_player_metrics': metrics([r['point_error'] for r in common if not r['fallback']]),
                    'POSTGAME_DIAGNOSTIC_actual_volume': metrics([r['POSTGAME_actual_volume_point']-r['actual'] for r in common]),
                    'POSTGAME_DIAGNOSTIC_actual_share': metrics([r['POSTGAME_actual_share_point']-r['actual'] for r in common]),
                    'excluded_component_rows': dict(collections.Counter(r['common_component_missing_reason'] for r in rr if r['common_component_missing_reason']))})
    # Restricted row bytes stay in the same approved managed store.
    package = {'component_rows': component_rows, 'full_forecast_roster_team_groups': group_rows,
               'scope': 'POSTGAME_DIAGNOSTIC_ONLY_NOT_DEPLOYABLE_NOT_NEW_FORECASTS'}
    raw = gzip.compress((json.dumps(package, separators=(',', ':'), allow_nan=False)+'\n').encode(), mtime=0)
    if len(raw) > 1048576:
        raise ValueError('registered component archive size exceeded')
    target = destination / 'POST_WAVE_COMPONENT_DIAG_V1.json.gz'
    if target.exists():
        raise ValueError('immutable diagnostic already retained; do not rerun unchanged')
    store.write_bytes(target, raw)
    store.validate_reference(target, hashlib.sha256(raw).hexdigest())
    usage = store.verify_retained_checkpoint()
    result = {'id': 'A-ALLOC-COMMON-CASE-DIAG-v1', 'state': 'COMPLETED_ZERO_FIT_POSTGAME_DIAGNOSIS',
        'asof_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'original_predictions_changed': False,
        'source_numeric_archive_sha256': receipt['sha256'], 'team_label_source_hashes': source_refs,
        'retained_rows': len(component_rows), 'joint_roster_groups': len(group_rows), 'coherence': coherence,
        'summaries': summaries, 'private_evidence': {'logical_id': 'A-POST-WAVE-COMPONENT-DIAG-V1', 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(), 'readback': 'PASS_OWNER_LOCAL', 'offhost': 'NOT_VERIFIED'},
        'causal_limits': ['Accounting decomposition and postgame substitutions identify error components, not a causal mechanism or achievable future accuracy.',
            'Other/unresolved and unscored roster mass are not verified DNP or zero production.',
            'Seven-day football availability is the original reconstruction assumption; quote timing and provider historical vintages remain unverified.',
            'No architecture, injury penalty, correction offset, selection rule or forecast has been changed.'],
        'CPU_seconds': time.process_time()-cpu, 'wall_seconds': time.monotonic()-begin,
        'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024, 'new_fits_inference': 0,
        'retained_headroom_bytes': usage['wave_retained_limit_bytes']-usage['new_peer_physical_bytes']}
    (OUT / 'ALLOCATION_COMPONENT_RESULTS_V1.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'state': result['state'], 'private_evidence': result['private_evidence'],
        'CPU_seconds': result['CPU_seconds'], 'summaries': [r for r in summaries if len(r['weeks']) > 1]}))


if __name__ == '__main__':
    main()
