"""Independent saved-point QA; no model, source-feature or fitting operations."""
from pathlib import Path
import argparse
import datetime
import hashlib
import io
import json
import os
import resource
import signal
import sys
import time
import zipfile

VERSION = 'opportunity-four-history-saved-vector-qa-v2-20261029'
KEYS = ['season', 'week', 'game_id', 'player_id']
CONTEXT = ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc']
METHODS = [
    'BASE_CDF_CACHED', 'CDF_H1_CURRENT_SEASON_TRAINING',
    'CDF_H2_PRIOR_PLUS_CURRENT_TRAINING', 'CDF_H3_TIME_WEIGHTED_TRAINING',
    'CDF_H4_HISTORICAL_RELATION_CURRENT_STATE', 'CDF_H4_PLUS_TIMESTAMPED_DEPTH',
]
CAPS = {'CPU_seconds': 30, 'wall_seconds': 60, 'RSS_bytes': 512*1024**2,
        'attempts': 1, 'metadata_bytes': 65536, 'models': 0, 'fits': 0,
        'HTTP': 0, 'CAS': 0, 'bootstrap_replicates': 500, 'seed': 1703}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       allow_nan=False)+'\n').encode()


def auth(ref):
    path = Path(ref['path'])
    assert path.is_absolute() and path.resolve() == path and not path.is_symlink()
    body = path.read_bytes()
    assert len(body) == ref['bytes'] and sha(body) == ref['sha256']
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--go', required=True)
    args = parser.parse_args()
    body = Path(args.plan).read_bytes()
    assert sha(body) == args.sha256
    plan = json.loads(body)
    assert plan['version'] == VERSION and plan['state'] == 'ROOT_REVIEWED_AND_SEALED'
    assert plan['execution_authorized'] is True and plan['resources'] == CAPS
    assert json.loads(Path(args.go).read_bytes()) == {
        'state': 'GO', 'root': '/root', 'scope': VERSION,
        'plan_sha256': args.sha256, 'source_review': 'PASS'}
    assert sha(Path(__file__).read_bytes()) == plan['worker_sha256']
    assert sys.flags.dont_write_bytecode
    native = Path(plan['native_root'])
    assert not native.exists()
    native.mkdir()
    cpu, wall = time.process_time(), time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    blocked = []

    class Stop(BaseException):
        pass

    def stop(*unused):
        raise Stop('one finite independent saved-vector QA exhausted')

    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGXCPU, stop)
    signal.setitimer(signal.ITIMER_REAL, 55)

    def deny(event, arguments):
        if (event.startswith('socket.') or event.startswith('pickle.') or
            event in ['subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn'] or
            (event == 'import' and arguments[0].split('.')[0] in ['joblib', 'sklearn'])):
            blocked.append(event)
            raise Stop('QA forbids models, pickle, acquisition and subprocesses')

    sys.addaudithook(deny)

    def usage():
        return {'CPU_seconds': time.process_time()-cpu,
                'wall_seconds': time.monotonic()-wall,
                'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                'model_deserializations': 0, 'fits': 0, 'HTTP': 0, 'CAS': 0,
                'blocked_calls': blocked}

    def note(name, value):
        payload = encoded(value)
        assert sum(p.stat().st_size for p in native.parent.rglob('*') if p.is_file()) + len(payload) <= CAPS['metadata_bytes']
        with (native/name).open('xb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    note('CONSUMED.json', {'state': 'ONE_QA_ATTEMPT_CONSUMED',
         'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'plan_sha256': args.sha256, 'resources': CAPS,
         'no_original_study_budget_refund': True})
    try:
        for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
            os.environ[name] = '1'
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)

        def frame(capsule, member, expected=None, columns=None):
            with zipfile.ZipFile(io.BytesIO(capsule)) as archive:
                assert len(archive.namelist()) == len(set(archive.namelist()))
                # Only saved vectors are permitted: never open model members.
                assert member in ['FORECASTS.parquet', 'GRADED_ROWS.parquet', 'QUERY.parquet']
                if member == 'QUERY.parquet':
                    assert columns == KEYS+['kickoff_utc', 'cutoff_utc', 'feature_max_source_available_utc']
                data = archive.read(member)
            if expected is not None:
                assert {'bytes': len(data), 'sha256': sha(data)} == expected
            return pq.read_table(pa.BufferReader(data), columns=columns, use_threads=False).to_pandas()

        frozen_body = auth(plan['inputs']['freeze'])
        grade_body = auth(plan['inputs']['grade'])
        old_body = auth(plan['inputs']['original_freeze'])
        with zipfile.ZipFile(io.BytesIO(grade_body)) as archive:
            saved_result = json.loads(archive.read('RESULT.json'))
            assert sha(archive.read('RESULT.json')) == plan['grade_result_sha256']
        frozen = frame(frozen_body, 'FORECASTS.parquet', plan['members']['frozen'])
        graded = frame(grade_body, 'GRADED_ROWS.parquet', plan['members']['graded'])
        original = frame(old_body, 'FORECASTS.parquet')
        assert len(frozen) == len(graded) == 3090 and len(original) == 2575
        assert set(frozen.method) == set(graded.method) == set(METHODS)
        assert not frozen.duplicated(KEYS+['method']).any()
        assert not graded.duplicated(KEYS+['method']).any()
        assert not original.duplicated(KEYS+['method']).any()
        assert 'actual' not in frozen and 'participation_state' not in frozen
        pd.testing.assert_frame_equal(graded[list(frozen)], frozen, check_exact=True)
        assert frozen.position.eq('QB').all() and frozen.season.eq(2026).all()
        assert frozen.week.between(1, 6).all()
        cutoff = pd.to_datetime(frozen.cutoff_utc, utc=True)
        kickoff = pd.to_datetime(frozen.kickoff_utc, utc=True)
        assert cutoff.notna().all() and kickoff.notna().all() and (cutoff <= kickoff).all()
        clock_columns = KEYS+['kickoff_utc', 'cutoff_utc', 'feature_max_source_available_utc']
        query_clock = frame(frozen_body, 'QUERY.parquet', plan['members']['query_clock'], columns=clock_columns)
        assert len(query_clock) == 515 and not query_clock.duplicated(KEYS).any()
        query_cutoff = pd.to_datetime(query_clock.cutoff_utc, utc=True)
        source_clock = pd.to_datetime(query_clock.feature_max_source_available_utc, utc=True)
        assert (source_clock.isna() | (source_clock < query_cutoff)).all()
        known_source_clock_count = int(source_clock.notna().sum())
        cutoff_equal_kickoff_unique = int((query_cutoff == pd.to_datetime(query_clock.kickoff_utc, utc=True)).sum())
        assert np.isfinite(frozen[['mean', 'median']].to_numpy(float)).all()
        assert (frozen[['mean', 'median']].to_numpy(float) >= 0).all()
        assert (frozen['median'] == np.floor(frozen['median'])).all()
        base = graded.loc[graded.method.eq('BASE_CDF_CACHED')].copy()
        keys = base[KEYS].reset_index(drop=True)
        assert len(keys) == 515 and base.game_id.nunique() == 93
        pd.testing.assert_frame_equal(base[KEYS+['kickoff_utc', 'cutoff_utc']].reset_index(drop=True), query_clock[KEYS+['kickoff_utc', 'cutoff_utc']].reset_index(drop=True), check_exact=True)
        assert base.participation_state.value_counts().to_dict() == {'unknown': 304, 'played': 211}
        assert base.loc[base.participation_state.eq('unknown'), 'actual'].isna().all()
        supported = base.participation_state.eq('played')
        y = base.loc[supported, 'actual'].to_numpy(float)
        assert len(y) == 211 and np.isfinite(y).all() and (y >= 0).all()
        assert (y == np.floor(y)).all() and int((y == 0).sum()) == 6
        for method in METHODS:
            rows = graded.loc[graded.method.eq(method)].reset_index(drop=True)
            pd.testing.assert_frame_equal(rows[KEYS], keys, check_exact=True)
            pd.testing.assert_frame_equal(rows[CONTEXT+['actual', 'participation_state']],
                                          base[CONTEXT+['actual', 'participation_state']].reset_index(drop=True),
                                          check_exact=True)
        old_join = frozen.loc[frozen.method.ne('BASE_CDF_CACHED')].merge(
            original[KEYS+['method', 'point', 'fallback']], on=KEYS+['method'],
            suffixes=('', '_original'), validate='one_to_one')
        assert len(old_join) == 2575
        assert np.array_equal(old_join['mean'].to_numpy(np.float64).view(np.uint64),
                              old_join['point'].to_numpy(np.float64).view(np.uint64))
        assert old_join.fallback.fillna('').equals(old_join.fallback_original.fillna(''))

        def metric(rows, functional):
            use = rows.participation_state.eq('played') & rows.actual.notna() & rows[functional].notna()
            truth = rows.loc[use, 'actual'].to_numpy(float)
            value = rows.loc[use, functional].to_numpy(float)
            error = value-truth
            absolute = np.abs(error)
            integer = bool((value == np.floor(value)).all())
            return {'planned': len(rows), 'scored': len(truth),
                    'unknown': int(rows.participation_state.eq('unknown').sum()),
                    'played_zero': int((truth == 0).sum()),
                    'fallbacks': int(rows.fallback.fillna('').ne('').sum()),
                    'scored_fallbacks': int((use & rows.fallback.fillna('').ne('')).sum()),
                    'games': int(rows.loc[use, 'game_id'].nunique()),
                    'weeks': int(rows.loc[use, 'week'].nunique()),
                    'MAE': float(absolute.mean()), 'MSE': float(np.square(error).mean()),
                    'RMSE': float(np.sqrt(np.square(error).mean())),
                    'bias': float(error.mean()), 'p90_AE': float(np.quantile(absolute, .9)),
                    'p95_AE': float(np.quantile(absolute, .95)),
                    'strict_error_lt1': float((absolute < 1).mean()),
                    'inclusive_error_le1': float((absolute <= 1).mean()),
                    'exact_integer_match': float((value == truth).mean()) if integer else None,
                    'exact_integer_match_reason': None if integer else 'fractional_mean_without_registered_discrete_rounding_rule',
                    'rounding': 'none'}

        result_checks = 0

        def compare(expected, actual):
            nonlocal result_checks
            if isinstance(expected, dict):
                assert isinstance(actual, dict) and set(expected) == set(actual)
                for key in expected:
                    compare(expected[key], actual[key])
            elif isinstance(expected, list):
                assert isinstance(actual, list) and len(expected) == len(actual)
                for first, second in zip(expected, actual):
                    compare(first, second)
            elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
                assert isinstance(actual, (int, float)) and not isinstance(actual, bool)
                # Reporting float arithmetic only; prediction parity above is exact.
                assert np.isclose(expected, actual, rtol=1e-12, atol=1e-12)
                result_checks += 1
            else:
                assert expected == actual
                result_checks += 1

        metrics = {method: {functional: metric(rows, functional) for functional in ['mean', 'median']}
                   for method, rows in graded.groupby('method', sort=True)}
        compare(metrics, saved_result['metrics'])
        weekly = {str(week): {method: {functional: metric(rows, functional) for functional in ['mean', 'median']}
                             for method, rows in part.groupby('method', sort=True)}
                  for week, part in graded.groupby('week', sort=True)}
        compare(weekly, saved_result['weekly'])
        paired = []
        for method in METHODS:
            if method == 'BASE_CDF_CACHED':
                continue
            for functional in ['mean', 'median']:
                pivot = graded.pivot(index=KEYS, columns='method', values=functional)
                actual = base.set_index(KEYS).actual
                rows = ((pivot[method]-actual).abs() - (pivot['BASE_CDF_CACHED']-actual).abs()).dropna().reset_index(name='delta')
                rows['n'] = 1
                intervals = {}
                for cluster in ['game_id', 'week']:
                    totals = rows.groupby(cluster, sort=True)[['delta', 'n']].sum().to_numpy(float)
                    n = len(totals)
                    interval = None
                    if n >= 8:
                        draws = np.random.default_rng(1703).integers(n, size=(500, n))
                        samples = totals[draws].sum(axis=1)
                        interval = np.quantile(samples[:, 0]/samples[:, 1], [.025, .975]).tolist()
                    intervals[cluster] = {'clusters': n, 'nominal95_interval': interval,
                                          'reason': None if interval is not None else 'fewer_than8clusters'}
                paired.append({'method': method, 'functional': functional, 'comparator': 'BASE_CDF_CACHED',
                               'paired_rows': len(rows), 'candidate_minus_control_MAE': float(rows.delta.mean()),
                               'relative_improvement_percent': 100*(metrics['BASE_CDF_CACHED'][functional]['MAE']-metrics[method][functional]['MAE'])/metrics['BASE_CDF_CACHED'][functional]['MAE'],
                               'intervals': intervals,
                               'multiplicity': 'nominal descriptive10productcontrasts; selectedminimum notscientificqualification'})
        lookup = {(row['method'], row['functional']): row for row in saved_result['paired']}
        assert len(lookup) == 10
        for row in paired:
            compare(row, lookup[(row['method'], row['functional'])])
        h4 = graded.loc[graded.method.eq('CDF_H4_HISTORICAL_RELATION_CURRENT_STATE')].reset_index(drop=True)
        base_reset = base.reset_index(drop=True)
        equality = {functional: bool(np.array_equal(h4[functional].to_numpy(np.float64).view(np.uint64),
                                                    base_reset[functional].to_numpy(np.float64).view(np.uint64)))
                    for functional in ['mean', 'median']}
        equality['fallbacks'] = bool(h4.fallback.fillna('').equals(base_reset.fallback.fillna('')))
        equality['all_recorded_functionals_and_fallbacks'] = all(equality.values())
        fallback_pivot = graded.assign(learned=graded.fallback.fillna('').eq('')).pivot(
            index=KEYS, columns='method', values='learned')
        learned_keys = fallback_pivot.index[fallback_pivot.all(axis=1)]
        learned = graded.set_index(KEYS).loc[learned_keys].reset_index()
        overlap = {'definition': 'All six procedures have empty original fallback flags on the same player-game; no outcome-based filtering.',
                   'planned_unique': len(learned_keys),
                   'scored_unique': int(learned.loc[learned.method.eq('BASE_CDF_CACHED'), 'participation_state'].eq('played').sum()),
                   'methods': {method: {functional: metric(rows, functional) for functional in ['mean', 'median']}
                               for method, rows in learned.groupby('method', sort=True)}}
        assert saved_result['new_fits'] == 0 and saved_result['new_median_forecast_rows'] == 2575
        assert saved_result['replayed_original_mean_rows'] == 2575 and saved_result['cached_base_rows'] == 515
        assert saved_result['new_pregame_capture_admission_deployment'] == 0
        assert saved_result['proper_probabilities_and_OverUnder_EV'] is None
        observed = usage()
        assert observed['CPU_seconds'] < 29 and observed['wall_seconds'] < 59
        assert observed['RSS_bytes'] <= CAPS['RSS_bytes'] and not blocked
        note('RESULT.json', {'state': 'PASS_INDEPENDENT_SAVED_VECTOR_QA', 'version': VERSION,
             'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'inputs_sha256': {name: ref['sha256'] for name, ref in plan['inputs'].items()},
             'rows': 3090, 'unique_player_games': 515, 'supported': 211, 'unknown': 304,
             'played_zero': 6, 'original_mean_and_fallback_parity_rows': 2575,
             'clock_diagnostics': {'cutoff_equal_kickoff_unique': cutoff_equal_kickoff_unique, 'known_source_clocks': known_source_clock_count, 'unknown_source_clocks': 515-known_source_clock_count, 'rule': 'Original kickoff-left-limit permits cutoff equality; known feature clocks strictly earlier. No numeric source features decoded.'},
             'prior_QA_v1': 'FAILED_RETAINED: reviewer imposed stricter cutoff<kickoff; no median result invalidation absent an actual defect.',
             'aggregate_result_fields_compared': result_checks,
             'checks': ['exact forecast-to-grade parity', 'identical method keys/context/labels',
                        'unrounded means and integer medians', 'no unknown zeros',
                        'overall and per-week metrics', 'all ten game/week-aware paired contrasts'],
             'H4_vs_BASE_bit_equality': equality, 'common_learned_output_overlap': overlap,
             'usage': usage(),
             'limitations': ['No model deserialization/refit or new forecasts.',
                 'Same-host saved-vector readback; not off-host private restoration.',
                 'Exposed W1-6 reconstructed labels/timing; no W7 or genuine pregame/site gain.',
                 'Nominal intervals; only six week clusters, so week uncertainty unavailable.',
                 'No probability, offered-line, market, EV, admission or deployment evidence.']})
    except BaseException as error:
        note('FAILED.json', {'state': 'INDEPENDENT_SAVED_VECTOR_QA_FAILED_RETAINED',
             'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'type': type(error).__name__, 'error': str(error), 'usage': usage(),
             'automatic_retry': False})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    main()
