"""Bounded target-label qualification, without fitting or predicting.

All restricted paths and identities come from the separately approved plan.
Only aggregates leave the process; this script never writes player rows.
"""
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

VERSION = 'rec-tgt-provider-label-qualification-v1-20261029'
KEYS = ['season', 'week', 'game_id', 'player_id']


def digest(body):
    return hashlib.sha256(body).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--go', required=True)
    args = parser.parse_args()
    body = Path(args.plan).read_bytes()
    assert digest(body) == args.sha256
    plan = json.loads(body)
    assert plan['version'] == VERSION and plan['resources']['attempts'] == 1
    assert json.loads(Path(args.go).read_bytes()) == {'state': 'GO', 'root': '/root', 'scope': VERSION, 'plan_sha256': args.sha256}
    output = Path(plan['output'])
    assert not output.exists()
    output.mkdir(parents=True)
    start, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('90second qualification')))
    signal.alarm(90)
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    def deny(event, unused):
        if event.startswith('socket.') or event in ['subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn', 'pickle.find_class']:
            raise RuntimeError('offline qualification without models or child processes')
    sys.addaudithook(deny)
    result = {'version': VERSION, 'state': 'FAILED_RETAINED', 'model_loads_fits_forecasts_HTTP_CAS': 0}
    (output/'CONSUMED.json').write_text(json.dumps({'state': 'ONE_QUALIFICATION_ATTEMPT_CONSUMED', 'plan_sha256': args.sha256, 'automatic_retry': False}, sort_keys=True)+'\n')
    try:
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pyarrow.dataset as ds
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        def auth(ref):
            content = Path(ref['path']).read_bytes()
            assert len(content) == ref['bytes'] and digest(content) == ref['sha256']
            return content
        for ref in plan['source_pins'].values():
            auth(ref)
        inputs = {name: auth(ref) for name, ref in plan['inputs'].items()}
        schedule = pd.read_csv(io.BytesIO(inputs['schedule']), usecols=['season', 'week', 'game_id', 'game_type'])
        assert not schedule.game_id.duplicated().any()
        regular = schedule.loc[schedule.game_type.eq('REG')]
        allowed = set(regular.game_id.astype(str))
        columns = KEYS+['team', 'opponent', 'position', 'kickoff_utc', 'outcome_available_utc', 'participation_state', 'official_physical_event', 'stats_observed', 'rec_tgt']
        data = ds.dataset(plan['inputs']['accepted_features']['path'], format='parquet')
        cutoff = pd.Timestamp(plan['training_cutoff_utc'])
        train = data.to_table(columns=columns, filter=(ds.field('season')>=2022)&(ds.field('season')<=2025)&ds.field('game_id').isin(list(allowed))&(ds.field('outcome_available_utc')<cutoff.to_pydatetime())&(ds.field('kickoff_utc')<cutoff.to_pydatetime()), use_threads=False).to_pandas()
        query = pq.read_table(pa.BufferReader(inputs['query']), columns=columns+['cutoff_utc'], use_threads=False).to_pandas()
        assert not train.duplicated(KEYS).any() and not query.duplicated(KEYS).any()
        assert len(query) == 2999 and query.season.eq(2026).all() and query.week.between(1, 7).all() and query.game_id.astype(str).isin(allowed).all()
        def summarize(frame):
            assert frame.participation_state.isin(['played','DNP','unknown']).fillna(False).all(), 'participation state must be explicit'
            y = pd.to_numeric(frame.rec_tgt, errors='coerce')
            played = frame.participation_state.eq('played')
            finite = np.isfinite(y)
            invalid = played & finite & ((y<0)|(y%1!=0))
            assert not invalid.any(), 'invalid finite count cannot be silently dropped'
            supported = played & finite
            assert frame.loc[supported, 'stats_observed'].eq(True).fillna(False).all(), 'label without observed-stat source'
            assert frame.loc[supported, 'official_physical_event'].eq(True).fillna(False).all(), 'playing not independently qualified'
            zero = supported & y.eq(0)
            return {'planned': len(frame), 'supported': int(supported.sum()), 'players': int(frame.loc[supported, 'player_id'].nunique()), 'games': int(frame.loc[supported, 'game_id'].nunique()), 'weeks': int(frame.loc[supported, 'week'].nunique()), 'participation': {str(k): int(v) for k,v in frame.participation_state.value_counts(dropna=False).items()}, 'played_zero': int(zero.sum()), 'played_missing': int((played & ~finite).sum()), 'unknown_numeric_quarantined': int((~played & finite).sum()), 'all_recorded_zeros_have_physical_event_and_observed_stat': bool(frame.loc[zero, 'official_physical_event'].eq(True).fillna(False).all() and frame.loc[zero, 'stats_observed'].eq(True).fillna(False).all())}
        periods = {}
        for season, group in train.groupby('season', sort=True):
            relevant = group.loc[group.position.isin(['RB', 'WR', 'TE'])]
            periods[str(season)] = {'all_role': summarize(group), 'primary_RB_WR_TE': summarize(relevant)}
        weekly = {}
        for week in range(1, 8):
            group = query.loc[query.week.eq(week)]
            expected_games = regular.loc[regular.season.eq(2026)&regular.week.eq(week), 'game_id'].astype(str)
            weekly[str(week)] = {'all_role': summarize(group), 'primary_RB_WR_TE': summarize(group.loc[group.position.isin(['RB','WR','TE'])]), 'scheduled_REG_games': len(expected_games), 'query_games': int(group.game_id.nunique()), 'missing_game_ids_count': int((~expected_games.isin(group.game_id.astype(str))).sum()), 'state': 'SUPPORTED_QUERY_SOURCE' if len(group) else 'MISSING_COMPATIBLE_QUERY_AND_TARGET_LABEL_SOURCE'}
        result.update(state='PROVIDER_REPORTED_TARGET_LABEL_QUALIFICATION_COMPLETE', product='rec_tgt_nflverse_weekly_v1', outcome_definition='Provider-reported weekly targets mapped unchanged to rec_tgt; independently qualified played rows with finite nonnegative integer statistic', event_credit_rules={'overtime': 'NOT_INDEPENDENTLY_VERIFIED_FROM_RETAINED_AGGREGATION_SOURCE', 'nullified_plays': 'NOT_INDEPENDENTLY_VERIFIED_FROM_RETAINED_AGGREGATION_SOURCE', 'two_point_exclusion': 'NOT_INDEPENDENTLY_VERIFIED_FROM_RETAINED_AGGREGATION_SOURCE'}, operational_target_contract='BLOCKED_EXACT_CREDIT_EXCEPTIONS_AND_CURRENT_SOURCE_ADMISSION', intended_evaluation={'season':2026,'weeks':list(range(1,8)),'scope':'REG; unsupported week remains explicit, no hindsight exclusion'}, training={'seasons':[2022,2023,2024,2025], 'cutoff_utc':plan['training_cutoff_utc'], 'periods':periods, 'feature_memory':'Existing feature representation retains earlier2019-2021 history where present; not strict current-season information'}, evaluation={'all_role':summarize(query),'primary_RB_WR_TE':summarize(query.loc[query.position.isin(['RB','WR','TE'])]),'weekly':weekly}, source_clocks='Original assumed kickoff+7day historical reconstruction; not verified publication clocks', target_website_reference='NOT_AVAILABLE', authentic_target_offer_contract='NOT_AVAILABLE', predictive_experiment_complete=False)
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 <= plan['resources']['RSS_bytes']
    except BaseException as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        signal.alarm(0)
        result['actual']={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
        encoded=(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        assert len(encoded)<=65536
        with (output/'RESULT.json').open('xb') as handle:
            handle.write(encoded)
        print(json.dumps({'state':result['state'],'actual':result['actual']}))


if __name__=='__main__':
    main()
