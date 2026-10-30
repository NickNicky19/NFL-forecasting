"""Independent aggregate and support checks of saved receiving-target vectors."""
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

VERSION = 'opportunity-four-target-saved-vector-qa-v1-20261029'
KEYS = ['season', 'week', 'game_id', 'player_id']
CONTEXT = ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc']
METHODS = ['TGT_CDF_BASE', 'TGT_ROLE_PRIOR', 'TGT_RECENT3_MEAN', 'TGT_RECENT8_MEAN']
LAWS = ['TGT_CDF_BASE', 'TGT_ROLE_PRIOR']
PRIMARY = ['RB', 'WR', 'TE']
CAPS = {'CPU_seconds': 30, 'wall_seconds': 60, 'RSS_bytes': 512*1024**2,
        'attempts': 1, 'metadata_bytes': 65536, 'models': 0, 'fits': 0,
        'HTTP': 0, 'CAS': 0, 'bootstrap_replicates': 500, 'seed': 1703}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


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
    assert json.loads(Path(args.go).read_bytes()) == {'state': 'GO', 'root': '/root',
        'scope': VERSION, 'plan_sha256': args.sha256, 'source_review': 'PASS'}
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
        raise Stop('finite target-vector QA exhausted')

    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGXCPU, stop)
    signal.setitimer(signal.ITIMER_REAL, 55)

    def deny(event, arguments):
        if (event.startswith('socket.') or event.startswith('pickle.') or
            event in ['subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn'] or
            (event == 'import' and arguments[0].split('.')[0] in ['joblib', 'sklearn'])):
            blocked.append(event)
            raise Stop('models, acquisition and children forbidden')

    sys.addaudithook(deny)

    def usage():
        return {'CPU_seconds': time.process_time()-cpu, 'wall_seconds': time.monotonic()-wall,
                'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                'model_deserializations': 0, 'fits': 0, 'HTTP': 0, 'CAS': 0, 'blocked_calls': blocked}

    def note(name, value):
        payload = encoded(value)
        assert sum(p.stat().st_size for p in native.parent.rglob('*') if p.is_file()) + len(payload) <= CAPS['metadata_bytes']
        with (native/name).open('xb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    note('CONSUMED.json', {'state': 'ONE_TARGET_QA_ATTEMPT_CONSUMED',
        'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'plan_sha256': args.sha256, 'resources': CAPS})
    try:
        for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
            os.environ[name] = '1'
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        freeze_body, grade_body = (auth(plan['inputs'][name]) for name in ['freeze', 'grade'])

        def saved(capsule, member, expected):
            assert member in ['FORECASTS.parquet', 'GRADED_ROWS.parquet', 'RESULT.json']
            with zipfile.ZipFile(io.BytesIO(capsule)) as archive:
                assert len(archive.namelist()) == len(set(archive.namelist()))
                payload = archive.read(member)
            assert {'bytes': len(payload), 'sha256': sha(payload)} == expected
            return payload

        frozen = pq.read_table(pa.BufferReader(saved(freeze_body, 'FORECASTS.parquet', plan['members']['frozen'])), use_threads=False).to_pandas()
        graded = pq.read_table(pa.BufferReader(saved(grade_body, 'GRADED_ROWS.parquet', plan['members']['graded'])), use_threads=False).to_pandas()
        result = json.loads(saved(grade_body, 'RESULT.json', plan['members']['result']))
        assert len(frozen) == len(graded) == 11996
        assert set(frozen.method) == set(graded.method) == set(METHODS)
        assert not frozen.duplicated(KEYS+['method', 'target']).any()
        assert not graded.duplicated(KEYS+['method', 'target']).any()
        assert frozen.target.eq('rec_tgt').all()
        assert 'actual' not in frozen and 'participation_state' not in frozen
        pd.testing.assert_frame_equal(graded[list(frozen)], frozen, check_exact=True)
        baseline = graded.loc[graded.method.eq('TGT_CDF_BASE')].reset_index(drop=True)
        assert len(baseline) == 2999 and baseline.game_id.nunique() == 93
        assert baseline.season.eq(2026).all() and baseline.week.between(1, 6).all()
        cutoff, kickoff = (pd.to_datetime(baseline[name], utc=True) for name in ['cutoff_utc', 'kickoff_utc'])
        assert cutoff.notna().all() and kickoff.notna().all() and (cutoff <= kickoff).all()
        labels = KEYS+CONTEXT+['actual', 'participation_state', 'outcome_state',
                  'label_source_present', 'label_missing_reason', 'source_position_differs_from_frozen_query']
        for method in METHODS:
            rows = graded.loc[graded.method.eq(method)].reset_index(drop=True)
            pd.testing.assert_frame_equal(rows[labels], baseline[labels], check_exact=True)
            assert np.isfinite(rows['mean']).all() and (rows['mean'] >= 0).all()
            if method in LAWS:
                assert np.isfinite(rows['median']).all()
                assert (rows['median'] >= 0).all() and (rows['median'] == np.floor(rows['median'])).all()
            else:
                assert rows['median'].isna().all()
                assert rows[['crps', 'log_score', 'cdf_actual', 'cdf_actual_below']].isna().all().all()
        finite = np.isfinite(pd.to_numeric(baseline.actual, errors='coerce'))
        assert not (finite & baseline.participation_state.ne('played')).any()
        truth = baseline.loc[finite, 'actual'].to_numpy(float)
        assert (truth >= 0).all() and (truth == np.floor(truth)).all()
        assert baseline.participation_state.isin(['played', 'DNP', 'unknown']).all()
        primary = graded.loc[graded.position.isin(PRIMARY)]
        primary_base = baseline.loc[baseline.position.isin(PRIMARY)]
        assert len(primary_base) == 2458
        eligible = primary_base.participation_state.eq('played') & np.isfinite(primary_base.actual)
        assert int(eligible.sum()) == 1855
        assert int(primary_base.participation_state.eq('unknown').sum()) == 603
        assert int((eligible & primary_base.actual.eq(0)).sum()) == 369
        laws_checked = 0
        for method in LAWS:
            rows = graded.loc[graded.method.eq(method)]
            supported = rows.participation_state.eq('played') & np.isfinite(rows.actual)
            rows = rows.loc[supported]
            assert rows[['crps', 'log_score', 'cdf_actual', 'cdf_actual_below']].notna().all().all()
            assert np.isfinite(rows.crps).all() and (rows.crps >= -1e-12).all()
            assert not np.isneginf(rows.log_score).any() and (rows.log_score >= -1e-12).all()
            low, high = rows.cdf_actual_below.to_numpy(float), rows.cdf_actual.to_numpy(float)
            assert np.isfinite(low).all() and np.isfinite(high).all()
            assert (low >= -1e-12).all() and (high <= 1+1e-12).all() and (low <= high+1e-12).all()
            assert np.allclose(high-low, np.exp(-rows.log_score.to_numpy(float)), rtol=1e-10, atol=1e-12)
            laws_checked += len(rows)

        def metric(rows, column, integer=False):
            truth = pd.to_numeric(rows.actual, errors='coerce')
            predicted = pd.to_numeric(rows[column], errors='coerce')
            played = rows.participation_state.eq('played')
            use = played & np.isfinite(truth) & np.isfinite(predicted)
            value = predicted[use].to_numpy(float)
            error = value-truth[use].to_numpy(float)
            absolute = np.abs(error)
            if integer:
                assert (value == np.floor(value)).all()
            enough, has_prediction = bool(len(error)), bool(np.isfinite(predicted).any())
            return {'planned': len(rows), 'scored': len(error), 'games': int(rows.loc[use, 'game_id'].nunique()),
                'weeks': int(rows.loc[use, 'week'].nunique()), 'players': int(rows.loc[use, 'player_id'].nunique()),
                'participation': {str(k): int(v) for k, v in rows.participation_state.value_counts(dropna=False).items()},
                'played_zero': int((use & truth.eq(0)).sum()), 'played_missing': int((played & ~np.isfinite(truth)).sum()),
                'fallbacks': int(rows.fallback.fillna('').ne('').sum()),
                'MAE': float(absolute.mean()) if enough else None, 'MSE': float(np.square(error).mean()) if enough else None,
                'RMSE': float(np.sqrt(np.square(error).mean())) if enough else None, 'bias': float(error.mean()) if enough else None,
                'p90_AE': float(np.quantile(absolute, .9)) if enough else None, 'p95_AE': float(np.quantile(absolute, .95)) if enough else None,
                'strict_error_lt1': float((absolute < 1).mean()) if enough else None,
                'inclusive_error_le1': float((absolute <= 1).mean()) if enough else None,
                'exact_count': float((error == 0).mean()) if enough and integer else None,
                'exact_count_reason': None if integer and has_prediction else ('OUTPUT_NOT_PRODUCED' if not has_prediction else 'MEAN_OR_POINT_NOT_ROUNDED_OR_REGISTERED_AS_INTEGER'),
                'no_score_reason': None if enough else ('OUTPUT_NOT_PRODUCED' if not has_prediction else 'NO_SUPPORTED_LABEL_AND_PREDICTION_OVERLAP')}

        def proper(rows):
            rows = rows.loc[rows.participation_state.eq('played') & rows.actual.notna()]
            assert len(rows) > 0
            impossible = int(np.isposinf(rows.log_score).sum())
            return {'CRPS': float(rows.crps.mean()),
                'log_loss': {'state': 'POSITIVE_INFINITY' if impossible else 'FINITE',
                    'value': None if impossible else float(rows.log_score.mean()),
                    'positive_infinite_rows': impossible, 'denominator': len(rows), 'impossible_events_retained': True},
                'calibration': 'NOT_ESTABLISHED; no authenticated target offering lines', 'conditional_on': 'played'}

        def summary(frame):
            return {method: {'mean': metric(rows, 'mean'), 'median': metric(rows, 'median', True),
                'proper': proper(rows) if method in LAWS else {'CRPS': None, 'log_loss': None, 'reason': 'POINT_ONLY_UNAUTHENTICATED_DISTRIBUTION'}}
                for method, rows in frame.groupby('method', sort=True)}

        field_checks = 0

        def compare(expected, actual):
            nonlocal field_checks
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
                assert np.isclose(expected, actual, rtol=1e-12, atol=1e-12)
                field_checks += 1
            else:
                assert expected == actual
                field_checks += 1

        primary_results = summary(primary)
        compare(primary_results, result['primary_results'])
        compare(summary(graded), result['all_role_operational_coverage'])
        compare({str(week): summary(rows) for week, rows in primary.groupby('week', sort=True)}, result['weekly'])
        first = primary.loc[primary.method.eq('TGT_CDF_BASE'), KEYS+['median', 'actual', 'participation_state']].rename(columns={'median': 'candidate'})
        second = primary.loc[primary.method.eq('TGT_RECENT8_MEAN'), KEYS+['mean']].rename(columns={'mean': 'control'})
        pair = first.merge(second, on=KEYS, validate='one_to_one')
        pair = pair.loc[pair.participation_state.eq('played') & np.isfinite(pair.actual) & np.isfinite(pair.candidate) & np.isfinite(pair.control)].copy()
        assert len(pair) == 1855
        pair['difference'] = (pair.candidate-pair.actual).abs() - (pair.control-pair.actual).abs()
        pair['n'] = 1
        for cluster, label in [('game_id', 'game'), ('week', 'week')]:
            totals = pair.groupby(cluster, sort=True)[['difference', 'n']].sum().to_numpy(float)
            count, interval = len(totals), None
            if count >= 8:
                draws = np.random.default_rng(1703).integers(count, size=(500, count))
                samples = totals[draws].sum(axis=1)
                interval = np.quantile(samples[:, 0]/samples[:, 1], [.025, .975]).tolist()
            candidate_loss = float((pair.candidate-pair.actual).abs().mean())
            control_loss = float((pair.control-pair.actual).abs().mean())
            expected = {'candidate': 'TGT_CDF_BASE', 'candidate_output': 'lower_count_median',
                'control': 'TGT_RECENT8_MEAN', 'control_output': 'unrounded_mean', 'score': 'MAE',
                'rows': len(pair), 'clusters': count, 'cluster': cluster,
                'candidate_loss': candidate_loss, 'control_loss': control_loss,
                'candidate_minus_control': float(pair.difference.mean()),
                'relative_improvement_percent': 100*(control_loss-candidate_loss)/control_loss if control_loss else None,
                'interval95': interval, 'minimum_clusters': 8, 'bootstrap_replicates': 500, 'seed': 1703,
                'scope': 'Point-display comparison; incompatible functionals remain honestly labeled, no probability claim'}
            compare(expected, result['paired_primary_vs_recent8'][label])
        assert result['new_fits'] == 1 and result['new_trees'] == 32
        assert result['new_forecast_rows'] == 11996 and result['unique_query_player_games'] == 2999
        assert result['new_genuine_pregame_capture'] == 0 and result['operational_admission_deployment'] is False
        assert result['probability_offer_EV_metrics']['value'] is None and result['website_comparison']['value'] is None
        assert result['target_label_qualification']['source_identity_admission']['unresolved_identity_row_count'] == 6
        observed = usage()
        assert observed['CPU_seconds'] < 29 and observed['wall_seconds'] < 59
        assert observed['RSS_bytes'] <= CAPS['RSS_bytes'] and not blocked
        note('RESULT.json', {'state': 'PASS_INDEPENDENT_TARGET_SAVED_VECTOR_QA', 'version': VERSION,
            'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'inputs_sha256': {name: ref['sha256'] for name, ref in plan['inputs'].items()},
            'method_rows': 11996, 'unique_query_player_games': 2999, 'primary_planned': 2458,
            'primary_supported': 1855, 'primary_unknown': 603, 'primary_played_zero': 369,
            'full_population_scored_law_rows_checked': laws_checked,
            'aggregate_result_fields_compared': field_checks,
            'primary_MAE': {method: {'mean': scores['mean']['MAE'], 'median': scores['median']['MAE']}
                            for method, scores in primary_results.items()},
            'checks': ['exact forecast-to-grade parity', 'all methods have identical keys/context/labels',
                'unknown never numeric zero', 'mean/median/point-only contracts',
                'count CDF/log-mass consistency', 'all overall/weekly point and proper aggregate scores',
                'game/week bootstrap seed1703/500 on same1855observations'],
            'usage': usage(), 'limitations': ['No new model deserialization/fit, source acquisition or forecast generation.',
                'Saved law score aggregation and CDF/log-mass consistency only; CRPS not regenerated from models.',
                'Same-host readback; not off-host restoration or official-credit historical-builder qualification.',
                'Exposed W1-6 reconstruction with original seven-day assumption; W7 gap retained.',
                'Six week clusters cannot support the declared minimum-eight-cluster week interval.',
                'No target website/market, probability calibration, EV, pregame, admission or deployment comparison.']})
    except BaseException as error:
        note('FAILED.json', {'state': 'INDEPENDENT_TARGET_VECTOR_QA_FAILED_RETAINED',
            'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'type': type(error).__name__, 'error': str(error), 'usage': usage(), 'automatic_retry': False})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    main()
