"""Complete per-origin query matrix check without turning queries into history.

Reuses V6's proven training and unchanged nonplayer/guard components. Rebuilds
every player window from the authenticated history alone, using the fixed code.
No model, fit, forecast, grader, selector or new information policy.
"""
from pathlib import Path
import datetime
import gzip
import hashlib
import importlib.util
import io
import json
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/audit-remediation-20261105'
KEY = ['season', 'week', 'game_id', 'player_id']


def main():
    start = time.monotonic()
    cpu = time.process_time()
    resource.setrlimit(resource.RLIMIT_AS, (1610612736, 1610612736))
    resource.setrlimit(resource.RLIMIT_CPU, (110, 120))
    signal.alarm(175)
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import nfl_lab
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    pa.set_memory_pool(pa.system_memory_pool())
    previous_bytes = (OUT / 'HISTORY_IMPACT_RECEIPT_V6.json').read_bytes()
    previous_sha = hashlib.sha256(previous_bytes).hexdigest()
    if previous_sha != '8dfc96149eac5900b3e7cdfb3df30b857483c293a2c6f7c48468cadf0612b0ed':
        raise ValueError('reviewed component proof differs')
    previous = json.loads(previous_bytes)
    training, panel = previous['panels']
    if not all(training[k]['exact_finite_and_missing_equivalence'] for k in
            ['original_rebuild', 'repair_effect', 'fit_scope_original_rebuild', 'fit_scope_repair_effect']):
        raise ValueError('training matrix compatibility not proven')
    changed = {x['feature'] for k in ['original_rebuild', 'repair_effect']
        for x in panel[k]['changed_columns']}
    if any(not name.startswith('f_player_') for name in changed):
        raise ValueError('nonplayer source context mismatch requires separate reconstruction')
    if training['missing_expected_feature_columns'] or panel['missing_expected_feature_columns']:
        raise ValueError('incomplete prior input component proof')
    if any(not panel[k]['complete'] or panel[k]['changed_rows'] for k in
            ['stored_vs_original_guard_clock', 'original_vs_repaired_guard_clock']):
        raise ValueError('query source guard clock context differs')
    path = ROOT.parent / 'nfl-audit-remediation-a/nfl_lab/features.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != previous['new_feature_sha256']:
        raise ValueError('reviewed fixed feature source differs')
    spec = importlib.util.spec_from_file_location('audit_origin_features', path)
    fixed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixed)
    store, _ = open_store(ROOT, allocation_sha256=
        'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO)

    def owned(ref):
        p = Path(ref['path'])
        owners = [s for s in (store, store.complete_peer, store.complete_peer.prior_forward,
            store.complete_peer.legacy) if any(p.is_relative_to(r) for r in s._roots)]
        if len(owners) != 1:
            raise ValueError('unique source owner required')
        got = owners[0].validate_reference(p, ref['sha256'])
        if got['bytes'] != ref['bytes']:
            raise ValueError('source size differs')
        return p.read_bytes()

    plan = json.loads(gzip.decompress((ROOT /
        'config/category-topfive-matched12-inference-followup-v1.json.gz').read_bytes()))
    training_config = json.loads((ROOT / 'config/weekly-future-training-v3.json').read_bytes())
    if (plan['features']['sha256'] != previous['query_input']['sha256']
            or training_config['features']['sha256'] != previous['training_input']['sha256']):
        raise ValueError('retained training/query bindings differ from component proof')
    query = pd.read_parquet(io.BytesIO(owned(plan['features'])))
    history = pd.concat([pd.read_parquet(io.BytesIO(owned(r))) for r in plan['history_sources']], ignore_index=True)
    history = history.loc[history.roster_status.isin(['ACT', 'INA'])].copy()
    if history.duplicated(['game_id', 'player_id']).any() or query.duplicated(KEY).any():
        raise ValueError('source/query identity versions unresolved')
    for name in ['outcome_available_utc', 'kickoff_utc']:
        history[name] = pd.to_datetime(history[name], utc=True)
    history = history.loc[history.outcome_available_utc.notna()].copy()
    history['known_play'] = np.where(history.participation_state.eq('played'), 1.,
        np.where(history.participation_state.eq('DNP'), 0., np.nan))
    for name in fixed.PLAYER_STATS:
        if name not in history:
            history[name] = np.nan
    player = fixed._lookup_windows(history, query, 'player_id', fixed.PLAYER_STATS + ['known_play'])
    values = {}
    for stat in fixed.PLAYER_STATS:
        for window in [3, 8]:
            values[f'f_player_{stat}_mean{window}'] = player[(stat, window, 'mean')]
            values[f'f_player_{stat}_n{window}'] = player[(stat, window, 'n')]
    for window in [3, 8]:
        values[f'f_player_targets_mean{window}'] = player[('rec_tgt', window, 'mean')]
        values[f'f_player_targets_n{window}'] = player[('rec_tgt', window, 'n')]
    values['f_player_games_prior'] = player['games']
    values['f_player_play_rate8'] = np.full(len(query), np.nan)  # Exact original operational wrapper.
    values['f_player_known_participation_n8'] = player[('known_play', 8, 'n')]
    for label, numerator, denominator in [('pass_ypa3', 'pass_yd', 'pass_att'),
            ('comp_rate3', 'pass_cmp', 'pass_att'), ('rush_ypa3', 'rush_yd', 'rush_att'),
            ('rec_ypt3', 'rec_yd', 'rec_tgt'), ('rec_catch_rate3', 'rec', 'rec_tgt')]:
        valid = history[[numerator, denominator]].notna().all(axis=1)
        pair = history[['player_id', 'kickoff_utc', 'outcome_available_utc', numerator, denominator]].copy()
        pair.loc[~valid, [numerator, denominator]] = np.nan
        pool = fixed._lookup_windows(pair, query, 'player_id', [numerator, denominator], (3,))
        values['f_player_' + label] = fixed._ratio(pool[(numerator, 3, 'sum')], pool[(denominator, 3, 'sum')])
    expected = [name for name in query if name.startswith('f_player_')]
    if set(expected) - set(values):
        raise ValueError('expected player feature missing from exact reconstruction')
    changed_rows = np.zeros(len(query), bool)
    differences = []
    for name in expected:
        left = pd.to_numeric(query[name], errors='raise').to_numpy(float)
        right = values[name]
        same = (left == right) | (np.isnan(left) & np.isnan(right))
        changed_rows |= ~same
        if (~same).any():
            differences.append({'feature': name, 'changed_rows': int((~same).sum())})
    result = {'id': 'A-AUDIT-PER-ORIGIN-QUERY-MATRIX-v1',
        'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'state': 'EXACT_RETAINED_TRAINING_QUERY_INPUT_AND_GUARD_EQUIVALENCE' if not changed_rows.any() else 'SAVED_VERSUS_RECONSTRUCTION_QUERY_DIFFERENCES_REQUIRE_CONTEXT_REVIEW',
        'query_rows': len(query), 'player_columns_rebuilt': len(expected),
        'changed_rows': int(changed_rows.sum()), 'changed_columns': differences,
        'nonplayer_and_guard_evidence': 'V6 full-builder old/stored and old/repaired comparisons, no differences outside player fields and source-guard clocks.',
        'training_evidence': 'V6 exact97columns on62388source rows and59842earlierfit rows, original/current/repaired parity, samefitguardclocks.',
        'scope_repair': 'Queries are targets only, never appended as historical observations at another origin. V6unmatchedquerycontext is a harness limitation, not measured contamination of savedNFLforecasts.',
        'source_sha256': previous['new_feature_sha256'],
        'query_feature_sha256': plan['features']['sha256'],
        'previous_component_proof_sha256': previous_sha,
        'source_availability_policy': 'Original declaredseven-dayproxy, not authenticated historical observation clocks. No <to<=change.',
        'by_week': [{'season': int(y), 'week': int(w), 'rows': len(index),
            'changed_rows': int(changed_rows[np.asarray(index)].sum())}
            for (y, w), index in query.groupby(['season', 'week']).indices.items()],
        'new_model_loads_fits_predictions_grades': 0,
        'current_native_Root_and_consumer': 'NOT_VERIFIED; exactcurrent-source/profile/issuedRoot/capture/consumer remain existingowner actions.',
        'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - start}
    if changed_rows.any():
        altered = query.copy()
        for name in expected:
            altered[name] = values[name]
        stream = io.BytesIO()
        altered.to_parquet(stream, index=False)
        body = stream.getvalue()
        if len(body) > 524288:
            raise ValueError('registered corrected query retention cap exceeded')
        dest = store.forward_root / 'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/AUDIT_FIXED_QUERY_MATRIX_V1.parquet'
        store.write_bytes(dest, body)
        ref = store.validate_reference(dest, hashlib.sha256(body).hexdigest())
        result['private_evidence'] = {k: ref[k] for k in ['bytes', 'sha256']}
        result['private_evidence']['readback'] = 'PASS_OWNER_LOCAL;OFFHOST_UNVERIFIED'
    store.verify_retained_checkpoint()
    with (OUT / 'PER_ORIGIN_QUERY_MATRIX_RECEIPT_V1.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))
    signal.alarm(0)


if __name__ == '__main__':
    main()
