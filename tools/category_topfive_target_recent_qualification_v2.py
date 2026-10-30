"""One bounded target-history source/parity qualification, with no forecasts.

Restricted paths arrive only through a sealed private CLI plan. Actual target-
game values, archived forecast rows and fitted models are not read by this run.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import resource
import signal
import sys
import time

VERSION = 'target-recent-history-qualification-v2-20261030'
CAPS = {'CPU_seconds': 60, 'wall_seconds': 90, 'RSS_bytes': 536870912,
        'attempts': 1, 'metadata_bytes': 65536, 'fits': 0, 'forecasts': 0,
        'model_loads': 0, 'HTTP': 0, 'CAS': 0}


def auth(ref):
    path = Path(ref['path'])
    assert path.is_absolute() and path.resolve() == path and not path.is_symlink()
    value = path.read_bytes()
    assert len(value) == ref['bytes'] and hashlib.sha256(value).hexdigest() == ref['sha256']
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
    assert json.loads(Path(args.go).read_bytes()) == {'state': 'GO', 'root': '/root', 'scope': VERSION, 'plan_sha256': args.sha256}
    assert sys.flags.dont_write_bytecode
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    out = Path(plan['output'])
    assert not out.exists()
    out.mkdir(parents=True)
    begun, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('90second source qualification')))
    signal.alarm(90)
    def deny(event, unused):
        if event.startswith('socket.') or event in ['subprocess.Popen', 'os.fork', 'os.system', 'os.posix_spawn', 'pickle.find_class']:
            raise RuntimeError('qualification excludes HTTP/children/models')
    sys.addaudithook(deny)
    result = {'version': VERSION, 'state': 'FAILED_RETAINED', 'fits_forecasts_models_HTTP_CAS': 0, 'automatic_retry': False}
    consumed = {'state': 'ONE_SOURCE_QUALIFICATION_ATTEMPT_CONSUMED', 'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'plan_sha256': args.sha256, 'original_allocations_refunded': False}
    (out / 'CONSUMED.json').write_text(json.dumps(consumed, sort_keys=True) + '\n')
    try:
        for ref in plan['source_pins'].values():
            auth(ref)
        for ref in plan['inputs'].values():
            auth(ref)
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.dataset as ds
        import pyarrow.parquet as pq
        for name, expected in plan['environment'].items():
            assert importlib.metadata.version(name) == expected
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        source = plan['source_pins']['helper']['path']
        spec = importlib.util.spec_from_file_location('target_recent_qualification_helper', source)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        columns = helper.KEYS + helper.CONTEXT + ['f_player_targets_mean3', 'f_player_targets_n3', 'f_player_targets_mean8', 'f_player_targets_n8']
        query = pq.read_table(plan['inputs']['query']['path'], columns=columns, use_threads=False).to_pandas()
        assert len(query) == 2999 and not query.duplicated(helper.KEYS).any()
        assert query.season.eq(2026).all() and query.week.between(1, 6).all()
        assert query.game_id.nunique() == 93 and query.position.isin(['RB', 'WR', 'TE']).sum() == 2458
        query['_query_order'] = np.arange(len(query))
        data = ds.dataset(plan['inputs']['history']['path'], format='parquet')
        scope = ((ds.field('season') >= 2019) & (ds.field('season') <= 2025)) | ((ds.field('season') == 2026) & (ds.field('week') >= 1) & (ds.field('week') <= 5))
        metadata_columns = helper.KEYS + ['kickoff_utc', 'outcome_available_utc', 'participation_state']
        metadata = data.to_table(columns=metadata_columns, filter=scope, use_threads=False).to_pandas()
        assert not metadata.duplicated(helper.KEYS).any() and not metadata[helper.KEYS].isna().any(axis=None)
        assert metadata.participation_state.isin(['played', 'DNP', 'unknown']).fillna(False).all()
        ko = pd.to_datetime(metadata.kickoff_utc, utc=True, errors='raise')
        av = pd.to_datetime(metadata.outcome_available_utc, utc=True, errors='raise')
        assert ko.notna().all() and not ((av.notna()) & (av <= ko)).any()
        # Explicit unknown availability remains unknown; never fabricate it.
        unknown_availability = int(av.isna().sum())
        numeric_columns = helper.KEYS + ['kickoff_utc', 'outcome_available_utc', 'participation_state', 'stats_observed', 'official_physical_event', 'rec_tgt']
        audits = []
        projected_row_incidences = 0
        for cutoff, batch in query.groupby('cutoff_utc', sort=True):
            limit = pd.Timestamp(cutoff)
            assert limit.tzinfo is not None
            predicate = scope & (ds.field('kickoff_utc') < limit.to_pydatetime()) & (ds.field('outcome_available_utc') < limit.to_pydatetime())
            prior = data.to_table(columns=numeric_columns, filter=predicate, use_threads=False).to_pandas()
            projected_row_incidences += len(prior)
            _, audit = helper.prepare_windows(batch, prior)
            audit['_query_order'] = batch['_query_order'].to_numpy()
            audits.append(audit)
        audit = pd.concat(audits, ignore_index=True).sort_values('_query_order').reset_index(drop=True)
        parity = helper.parity_audit(query, audit)
        failed = sum(x['mean_mismatches'] + x['count_mismatches'] for x in parity.values())
        result.update(source_contract='Prior qualified target history only; unknown/DNP slots consume positions; admit availability before kickoff chronology; no missing availability fill',
                      intended_scope='2026REGW1-7, supported frozen W1-6; W7 compatible source/query missing',
                      query_rows=len(query), primary_planned=2458, query_games=93,
                      source_identity_rows=len(metadata), unknown_availability_rows=unknown_availability,
                      numeric_projection_predicate='Each exact query cutoff separately: permitted source scope AND source kickoff<cutoff AND source outcome availability<cutoff',
                      cutoff_batches=int(query.cutoff_utc.nunique()), source_row_projection_incidences=projected_row_incidences,
                      source_mean_count_parity=parity,
                      audit_sha256=hashlib.sha256(audit.to_json(orient='records', date_format='iso', double_precision=15).encode()).hexdigest(),
                      target_game_values_used=False, archived_forecast_rows_read=0,
                      chronology='Availability admitted first; last3/8 roster-game slots by kickoff then game_id; qualified played finite integer values only inside slots',
                      historical_timing='Original fixed seven-day reconstruction assumption preserved; not authentic historical publication or pregame forecast')
        assert failed == 0, 'source mean/count parity mismatch; no same-information forecast admission'
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= CAPS['RSS_bytes']
        result['state'] = 'PASS_TARGET_RECENT_HISTORY_SOURCE_AND_MEAN_PARITY'
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        signal.alarm(0)
        result['terminal_at_UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['actual'] = {'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - begun, 'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        value = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        assert len(value) <= CAPS['metadata_bytes']
        with (out / 'RESULT.json').open('xb') as handle:
            handle.write(value)
        print(json.dumps({'state': result['state'], 'actual': result['actual']}))


if __name__ == '__main__':
    main()
