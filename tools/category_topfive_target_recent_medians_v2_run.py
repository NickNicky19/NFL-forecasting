"""One portable zero-fit target-median comparison with immutable forecasts.

Private bindings arrive only through CLI plan. Earlier-history target medians
are new point procedures; existing CDF/recent8 forecasts are reused unchanged.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import resource
import signal
import sys
import time
import zipfile

VERSION = 'opportunity-four-target-recent-medians-v2-20261030'
MIB = 1024 ** 2
CAPS = {'CPU_seconds': 120, 'wall_seconds': 180, 'RSS_bytes': 512 * MIB,
        'fits': 0, 'model_loads': 0, 'HTTP': 0, 'automatic_retries': 0,
        'managed_write_attempts': 3, 'retained_private_bytes': 16 * MIB,
        'peak_private_bytes': 32 * MIB, 'native_metadata_bytes': 64 * 1024,
        'public_aggregate_bytes': 128 * 1024, 'bootstrap_replicates': 500, 'seed': 1703}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def auth(ref):
    p = Path(ref['path'])
    assert p.is_absolute() and p.resolve() == p and not p.is_symlink()
    value = p.read_bytes()
    assert len(value) == ref['bytes'] and hashlib.sha256(value).hexdigest() == ref['sha256']
    return value


def module(ref, name):
    auth(ref)
    spec = importlib.util.spec_from_file_location(name, ref['path'])
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--go', required=True)
    args = parser.parse_args()
    body = Path(args.plan).read_bytes()
    assert hashlib.sha256(body).hexdigest() == args.sha256
    plan = json.loads(body)
    assert plan['version'] == VERSION and plan['resources'] == CAPS
    assert plan['state'] == 'ROOT_AND_REVIEWER_SEALED' and plan['execution_authorized'] is True
    assert json.loads(Path(args.go).read_bytes()) == {'state': 'GO', 'root': '/root', 'independent_review': 'PASS', 'scope': VERSION, 'plan_sha256': args.sha256, 'previous_managed_writer_closed': True}
    protocol = plan['public_protocol']
    assert protocol['experiment_id'] == 'e:' + VERSION and protocol['run_id'] == 'r:' + VERSION
    assert protocol['remote_readback'] == 'PASS' and len(protocol['commit']) == 40 and all(c in '0123456789abcdef' for c in protocol['commit'])
    assert sys.flags.dont_write_bytecode
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    for ref in plan['source_pins'].values():
        auth(ref)
    inputs = {name: auth(ref) for name, ref in plan['inputs'].items()}
    proof = json.loads(inputs['publication_proof'])
    assert proof['state'] == 'PUBLICATION_COMPLETE' and proof['remote_readback'] == 'PASS'
    assert proof['experiment_id'] == 'e:' + VERSION and proof['run_id'] == 'r:' + VERSION
    assert proof['protocol_commit'] == protocol['commit']
    assert proof['worker_sha256'] == plan['source_pins']['worker']['sha256'] and proof['helper_sha256'] == plan['source_pins']['helper']['sha256']
    qualification = json.loads(inputs['qualification'])
    assert qualification['version'] == 'target-recent-history-qualification-v3-20261030'
    assert qualification['state'] == 'PASS_TARGET_RECENT_HISTORY_SOURCE_AND_MEAN_PARITY'
    assert all(x['mean_mismatches'] == x['count_mismatches'] == 0 for x in qualification['source_mean_count_parity'].values())
    native = Path(plan['native_root'])
    assert not native.exists()
    native.mkdir(parents=True)
    begun, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
    class Stop(BaseException):
        pass
    def expired(*unused):
        raise Stop('finite zero-fit target-median allocation consumed')
    signal.signal(signal.SIGALRM, expired)
    signal.signal(signal.SIGXCPU, expired)
    signal.setitimer(signal.ITIMER_REAL, 175)
    blocked = []
    def deny(event, unused):
        if event.startswith('socket.') or event in ['subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn', 'pickle.find_class']:
            blocked.append(event)
            raise Stop('offline child-free zero-model experiment')
    sys.addaudithook(deny)
    writes = []
    new_rows_count = 0
    store = None
    def usage():
        return {'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - begun,
                'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                'fits': 0, 'model_deserializations': 0, 'new_forecast_rows': new_rows_count,
                'CAS_attempts': len(writes), 'HTTP': 0, 'blocked_calls': blocked}
    def note(name, value):
        data = encoded(value)
        assert sum(p.stat().st_size for p in native.iterdir()) + len(data) <= CAPS['native_metadata_bytes']
        with (native / name).open('xb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    def check(retention_only=False):
        u = usage()
        assert u['CPU_seconds'] < (119 if retention_only else 116) and u['wall_seconds'] < (179 if retention_only else 175) and u['RSS_bytes'] <= CAPS['RSS_bytes'] and (not blocked or retention_only)
    note('CONSUMED.json', {'state': 'ONE_ZERO_FIT_TARGET_MEDIAN_ATTEMPT_CONSUMED', 'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'plan_sha256': args.sha256, 'protocol': protocol, 'resources': CAPS, 'original_allocations_refunded': False})
    try:
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.dataset as ds
        import pyarrow.parquet as pq
        for name, expected in plan['environment'].items():
            assert importlib.metadata.version(name) == expected
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        helper = module(plan['source_pins']['helper'], 'target_recent_median_helper')
        product = module(plan['source_pins']['product_metrics'], 'target_recent_point_metrics')
        sp = plan['storage']
        original_store = module(sp['original_helper'], 'target_recent_original_store')
        metadata = module(sp['helper'], 'target_recent_prior_metadata')
        base = original_store.load_frozen(sp['forward_implementation']['path'], sp['legacy_library_root'])
        prior = metadata.build_storage_class(original_store.build_storage_class(base), json.loads(auth(sp['prior_metadata_descriptor'])))
        extension = module(sp['forward_metadata_helper'], 'target_recent_new_metadata')
        cls = extension.build_storage_class(prior, json.loads(auth(sp['metadata_descriptor'])))
        store = cls(sp['legacy_cache'], json.loads(auth(sp['market_policy'])), json.loads(auth(sp['legacy_policy'])), json.loads(auth(sp['prior_policy'])))
        output = Path(plan['output'])
        assert output == store.live_root / 'research' / VERSION and not output.exists()
        store.register_root(output)
        with store.transaction():
            store._refresh()
            store._require(CAPS['peak_private_bytes'])
        def save(name, members, retention_only=False):
            check(retention_only)
            assert len(writes) < 3
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
                for key, value in sorted(members.items()):
                    archive.writestr(key, value)
            value = stream.getvalue()
            retained = sum(ref['bytes'] for ref in writes)
            assert len(value) <= 12 * MIB and retained + len(value) + 65536 <= 16 * MIB and retained + 2 * len(value) + 65536 <= 32 * MIB
            ref = {'path': str(output / name), 'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
            writes.append(ref)
            store.write_bytes(output / name, value)
            observed = store.validate_reference(output / name)
            assert all(observed[k] == ref[k] for k in ['path', 'bytes', 'sha256'])
            assert (output / name).read_bytes() == value
            with zipfile.ZipFile(output / name) as archive:
                assert set(archive.namelist()) == set(members) and all(archive.read(k) == v for k, v in members.items())
            note(name.replace('.zip', '_READBACK.json'), {'state': 'EXACT_CAPSULE_AND_MEMBER_READBACK_PASS', 'reference': ref, 'members': {k: {'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()} for k, v in members.items()}, 'usage': usage()})
            return ref
        def parquet(frame):
            f = frame.copy()
            f.attrs.clear()
            stream = pa.BufferOutputStream()
            pq.write_table(pa.Table.from_pandas(f, preserve_index=False), stream, compression='zstd')
            return stream.getvalue().to_pybytes()
        save('ATTEMPT_CONSUMED.zip', {'CONSUMED.json': encoded({'fits': 0, 'new_median_procedures': 2, 'plan_sha256': args.sha256, 'protocol': protocol})})
        columns = helper.KEYS + helper.CONTEXT + ['f_player_targets_mean3', 'f_player_targets_n3', 'f_player_targets_mean8', 'f_player_targets_n8']
        query = pq.read_table(pa.BufferReader(inputs['query']), columns=columns, use_threads=False).to_pandas()
        assert len(query) == 2999 and not query.duplicated(helper.KEYS).any()
        with zipfile.ZipFile(io.BytesIO(inputs['original_freeze'])) as archive:
            original = pq.read_table(pa.BufferReader(archive.read('FORECASTS.parquet')), use_threads=False).to_pandas()
            original_query = pq.read_table(pa.BufferReader(archive.read('PREPARED_QUERY.parquet')), columns=columns, use_threads=False).to_pandas()
        pd.testing.assert_frame_equal(query, original_query, check_exact=True)
        assert not any(c in original for c in ['actual', 'participation_state', 'outcome_state'])
        control = original.loc[original.method.isin(['TGT_CDF_BASE', 'TGT_RECENT8_MEAN'])].copy().reset_index(drop=True)
        assert len(control) == 5998 and not control.duplicated(helper.KEYS + ['method']).any()
        cdf = control.loc[control.method.eq('TGT_CDF_BASE')].reset_index(drop=True)
        pd.testing.assert_frame_equal(query[helper.KEYS + helper.CONTEXT], cdf[helper.KEYS + helper.CONTEXT], check_exact=True)
        data = ds.dataset(plan['inputs']['history']['path'], format='parquet')
        scope = ((ds.field('season') >= 2019) & (ds.field('season') <= 2025)) | ((ds.field('season') == 2026) & (ds.field('week') >= 1) & (ds.field('week') <= 5))
        query['_query_order'] = np.arange(len(query))
        projected = helper.KEYS + ['kickoff_utc', 'outcome_available_utc', 'participation_state', 'stats_observed', 'official_physical_event', 'rec_tgt']
        forecasts, source_audits = [], []
        for cutoff, batch in query.groupby('cutoff_utc', sort=True):
            limit = pd.Timestamp(cutoff)
            # Identity-only projection: the helper looks up only these exact
            # batch players. Retain every query and verify the whole source
            # audit digest against the prior full-source qualification.
            predicate = scope & (ds.field('kickoff_utc') < limit.to_pydatetime()) & (ds.field('outcome_available_utc') < limit.to_pydatetime()) & ds.field('player_id').isin(batch.player_id.unique().tolist())
            history = data.to_table(columns=projected, filter=predicate, use_threads=False).to_pandas()
            windows, audit = helper.prepare_windows(batch, history)
            audit['_query_order'] = batch['_query_order'].to_numpy()
            source_audits.append(audit)
            fallback = cdf.iloc[batch['_query_order'].to_numpy()].reset_index(drop=True)
            for window in helper.WINDOWS:
                rows = helper.forecast_rows(batch, windows, fallback, window)
                rows['_query_order'] = batch['_query_order'].to_numpy()
                forecasts.append(rows)
        audit = pd.concat(source_audits, ignore_index=True).sort_values('_query_order').reset_index(drop=True)
        parity = helper.parity_audit(query, audit)
        assert all(x['mean_mismatches'] == x['count_mismatches'] == 0 for x in parity.values())
        assert hashlib.sha256(audit.to_json(orient='records', date_format='iso', double_precision=15).encode()).hexdigest() == qualification['audit_sha256']
        new = pd.concat(forecasts, ignore_index=True).sort_values(['method', '_query_order']).drop(columns='_query_order').reset_index(drop=True)
        new_rows_count = len(new)
        assert len(new) == 5998 and not new.duplicated(helper.KEYS + ['method']).any()
        frozen = pd.concat([control, new], ignore_index=True)
        assert len(frozen) == 11996 and not frozen.duplicated(helper.KEYS + ['method']).any()
        assert frozen.loc[frozen.method.isin(helper.METHODS.values()), 'mean'].isna().all()
        freeze = save('FORECASTS_FROZEN.zip', {'NEW_FORECASTS.parquet': parquet(new), 'CONTROL_FORECASTS.parquet': parquet(control), 'PREPARED_QUERY.parquet': parquet(query.drop(columns='_query_order')), 'SOURCE_WINDOW_AUDIT.parquet': parquet(audit), 'PLAN.json': body})
        # No target-game actual is projected before the exact global freeze.
        frozen_columns = list(frozen.columns)
        with zipfile.ZipFile(io.BytesIO(inputs['original_grade'])) as archive:
            original_grade = pq.read_table(pa.BufferReader(archive.read('GRADED_ROWS.parquet')), use_threads=False).to_pandas()
        label_columns = helper.KEYS + ['actual', 'participation_state', 'outcome_state', 'label_source_present', 'label_missing_reason', 'source_position_differs_from_frozen_query']
        labels = original_grade.loc[original_grade.method.eq('TGT_CDF_BASE'), label_columns].reset_index(drop=True)
        assert len(labels) == 2999 and not labels.duplicated(helper.KEYS).any()
        graded = frozen.merge(labels, on=helper.KEYS, how='left', validate='many_to_one')
        pd.testing.assert_frame_equal(graded[frozen_columns], frozen, check_exact=True)
        assert graded.participation_state.isin(['played', 'DNP', 'unknown']).fillna(False).all()
        def summaries(frame):
            return {str(method): {'mean': product.metric(rows, 'mean'), 'median': product.metric(rows, 'median', integer_point=True)} for method, rows in frame.groupby('method', sort=True)}
        primary = graded.loc[graded.position.isin(['RB', 'WR', 'TE'])]
        summary = summaries(primary)
        assert summary['TGT_CDF_BASE']['median']['planned'] == 2458 and summary['TGT_CDF_BASE']['median']['scored'] == 1855
        assert summary['TGT_CDF_BASE']['median']['played_zero'] == 369
        assert summary['TGT_CDF_BASE']['median']['MAE'] == 1.692722371967655
        assert summary['TGT_RECENT8_MEAN']['mean']['MAE'] == 1.7612667604551633
        pairs = {method: {control_id: {cluster: helper.paired_medians(primary, method, control_id, column, cluster) for cluster in ['game_id', 'week']} for control_id, column in [('TGT_CDF_BASE', 'median'), ('TGT_RECENT8_MEAN', 'mean')]} for method in helper.METHODS.values()}
        result = {'version': VERSION, 'state': 'NEW_TARGET_RECENT_MEDIAN_COMPARISON_COMPLETE', 'product': 'rec_tgt_nflverse_weekly_v1', 'public_protocol': protocol,
                  'new_fits': 0, 'model_deserializations': 0, 'new_forecast_rows': 5998, 'reused_control_forecast_rows': 5998, 'unique_query_player_games': 2999,
                  'scope': {'season': 2026, 'intended_weeks': list(range(1, 8)), 'supported_weeks': list(range(1, 7)), 'games': 93, 'primary_planned': 2458, 'primary_supported': 1855, 'primary_unknown': 603, 'played_zero': 369, 'week7': 'MISSING_COMPATIBLE_QUERY_AND_TARGET_LABEL_SOURCE'},
                  'history': 'Earlier per-cutoff eligible2019-2025 and earlier2026W1-5 source records; old seven-day reconstruction unchanged; not current-season-only information or weekly fitted-history comparison',
                  'primary': 'Recent8 lower empirical count median with frozen CDF lower-median fallback vs unchanged CDF lower median MAE; recent3 and recent8mean comparisons secondary',
                  'source_mean_count_parity': parity, 'source_audit_sha256': qualification['audit_sha256'], 'primary_results': summary, 'paired_comparisons': pairs,
                  'weekly': {str(week): summaries(rows) for week, rows in primary.groupby('week', sort=True)}, 'all_role_coverage': summaries(graded),
                  'point_contract': 'New true lower empirical medians of qualified prior target values inside last3/8 roster-game slots; not median of means and no future count distribution asserted. No additional tree fits.',
                  'fallback': 'If no qualified finite target inside fixed slots, retain original CDF actual lower count median; if unavailable, abstain; do not zero-fill',
                  'probability_offer_EV': {'value': None, 'reason': 'POINT_ONLY_NEW_PROCEDURES_NO_AUTHENTICATED_TARGET_OFFERS_PRICE_OR_FROZEN_SELECTIONS'},
                  'website': {'value': None, 'reason': 'NO_INCUMBENT_WEBSITE_TARGET_FORECAST'}, 'pregame_capture': 0, 'operational_admission_deployment': False,
                  'limitations': ['EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION', 'Original historical builder and nullified/two-point target-credit exceptions unverified', 'W7 gap', 'Six week clusters below minimum8 for interval', 'Same-host issuing-process readback, not independent/off-host restoration', 'Mean and median are related family outputs, not independent evidence'],
                  'forecast_values_unchanged_during_grade': True, 'usage_before_grade': usage()}
        grade = save('GRADE_COMPLETE.zip', {'RESULT.json': encoded(result), 'GRADED_ROWS.parquet': parquet(graded), 'SOURCE_BINDINGS.json': encoded(plan['inputs'])})
        check()
        note('COMPLETE.json', {'state': result['state'], 'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'freeze': freeze, 'grade': grade, 'usage': usage(), 'managed_writer': 'CLOSED'})
        public = {**result, 'freeze': freeze, 'grade': grade, 'usage': usage()}
        destination = Path(plan['private_result_metadata'])
        assert not destination.exists()
        value = encoded(public)
        assert len(value) <= CAPS['public_aggregate_bytes']
        destination.write_bytes(value)
        print(json.dumps({'state': result['state'], 'primary_results': {m: {'median_MAE': s['median']['MAE'], 'mean_MAE': s['mean']['MAE']} for m, s in summary.items()}, 'usage': usage(), 'freeze': freeze, 'grade': grade}))
    except BaseException as error:
        record = {'state': 'TARGET_RECENT_MEDIAN_FAILURE_PRESERVED', 'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'type': type(error).__name__, 'error': str(error), 'usage': usage(), 'automatic_retry': False}
        note('FAILED.json', record)
        if store is not None and len(writes) < 3 and 'save' in locals():
            try:
                partial = {'FAILED.json': encoded(record)}
                if 'freeze' in locals():
                    partial['FROZEN_FORECAST_REFERENCE.json'] = encoded(freeze)
                    if 'graded' in locals():
                        partial['PARTIAL_GRADED_ROWS.parquet'] = parquet(graded)
                    if 'result' in locals():
                        partial['PARTIAL_RESULT.json'] = encoded(result)
                else:
                    if 'new' in locals():
                        partial['PARTIAL_NEW_FORECASTS.parquet'] = parquet(new)
                    elif 'forecasts' in locals() and forecasts:
                        partial['PARTIAL_COMPLETED_POINT_BATCHES.parquet'] = parquet(pd.concat(forecasts, ignore_index=True))
                    if 'source_audits' in locals() and source_audits:
                        partial['PARTIAL_COMPLETED_SOURCE_AUDITS.parquet'] = parquet(pd.concat(source_audits, ignore_index=True))
                    if 'rows' in locals():
                        partial['LAST_COMPLETED_POINT_BATCH.parquet'] = parquet(rows)
                    if 'batch' in locals():
                        partial['ACTIVE_QUERY_BATCH.parquet'] = parquet(batch)
                    if 'audit' in locals():
                        partial['LAST_SOURCE_AUDIT.parquet'] = parquet(audit)
                    if 'history' in locals():
                        partial['ACTIVE_ELIGIBLE_SOURCE_HISTORY.parquet'] = parquet(history)
                save('FAILED.zip', partial, retention_only=True)
            except BaseException as retention:
                note('FAILURE_RETENTION.json', {'type': type(retention).__name__, 'error': str(retention)})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    main()
