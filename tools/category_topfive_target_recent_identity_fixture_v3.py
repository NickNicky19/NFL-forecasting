"""One fictional identity correction fixture; no NFL data or model access."""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import resource
import signal
import sys
import time

VERSION = 'target-recent-identity-fixture-v3-20261030'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--go', required=True)
    args = parser.parse_args()
    body = Path(args.plan).read_bytes()
    assert hashlib.sha256(body).hexdigest() == args.sha256
    plan = json.loads(body)
    assert plan['version'] == VERSION and plan['attempts'] == 1
    assert json.loads(Path(args.go).read_bytes()) == {'state': 'GO', 'root': '/root', 'scope': VERSION, 'plan_sha256': args.sha256}
    assert sys.flags.dont_write_bytecode
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    out = Path(plan['output'])
    assert not out.exists()
    out.mkdir(parents=True)
    start, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (2, 3))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('five second fictional fixture')))
    signal.alarm(5)
    def deny(event, unused):
        if event.startswith('socket.') or event in ['subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn', 'pickle.find_class']:
            raise RuntimeError('fictional fixture excludes network/children/models')
    sys.addaudithook(deny)
    result = {'version': VERSION, 'state': 'FAILED_RETAINED', 'NFL_rows_models_fits_forecasts_HTTP_CAS': 0, 'automatic_retry': False}
    (out / 'CONSUMED.json').write_text(json.dumps({'state': 'ONE_FICTIONAL_FIXTURE_CONSUMED', 'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'plan_sha256': args.sha256}) + '\n')
    try:
        for ref in plan['source_pins'].values():
            value = Path(ref['path']).read_bytes()
            assert len(value) == ref['bytes'] and hashlib.sha256(value).hexdigest() == ref['sha256']
        def load(ref, name):
            p = Path(ref['path'])
            b = p.read_bytes()
            assert len(b) == ref['bytes'] and hashlib.sha256(b).hexdigest() == ref['sha256']
            spec = importlib.util.spec_from_file_location(name, p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
        import numpy as np
        import pandas as pd
        old = load(plan['source_pins']['old_helper'], 'old_target_key_check')
        new = load(plan['source_pins']['new_helper'], 'new_target_key_check')
        q = pd.DataFrame({'season': np.array([2026, 2026], dtype=np.int32), 'week': np.array([1, 2], dtype=np.int32), 'game_id': ['FakeGameA', 'FakeGameB'], 'player_id': ['FakePlayer', 'FakePlayer']})
        a = q.copy()
        a['season'] = a.season.astype(np.int64)
        a['week'] = a.week.astype(np.int64)
        for w in [3, 8]:
            q['f_player_targets_n' + str(w)] = [1., 1.]
            q['f_player_targets_mean' + str(w)] = [2., 4.]
            a['n' + str(w)] = [1, 1]
            a['mean' + str(w)] = [2., 4.]
            a['unknown_slots' + str(w)] = [0, 0]
            a['DNP_slots' + str(w)] = [0, 0]
        try:
            old.parity_audit(q, a)
        except ValueError as error:
            assert str(error) == 'source parity query order changed'
        else:
            raise AssertionError('old dtype-only failure not reproduced on fiction')
        assert new.same_identity(q, a)
        assert all(v['mean_mismatches'] == v['count_mismatches'] == 0 for v in new.parity_audit(q, a).values())
        missing = a.copy(); missing.loc[0, 'player_id'] = None
        assert not new.same_identity(q, missing)
        assert not new.same_identity(q, a.iloc[::-1])
        changed = a.copy(); changed.loc[0, 'week'] = 9
        assert not new.same_identity(q, changed)
        changed = a.copy(); changed.loc[0, 'player_id'] = 'fakePlayer'
        assert not new.same_identity(q, changed)
        changed = a.copy(); changed.loc[0, 'player_id'] = 'FakePlayer '
        assert not new.same_identity(q, changed)
        duplicate = pd.concat([q.iloc[:1], q.iloc[:1]], ignore_index=True)
        assert not new.same_identity(duplicate, duplicate)
        changed = a.copy(); changed['season'] = changed.season.astype(float)
        assert not new.same_identity(q, changed)
        changed = a.copy(); changed.loc[0, 'season'] = None
        assert not new.same_identity(q, changed)
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= 128 * 1024 ** 2
        result.update(state='PASS_FICTIONAL_IDENTITY_CORRECTION', checks=10,
                      verified='Old dtype-only check fails on fictionalint32/int64; new exactorderedcanonicalkeysemanticspass andmissing/reorder/mutation/case/padding/dup/float/nonfinite reject',
                      limit='Fictional code mechanism, not independent actualNFL row equality or completed numeric sourceparity')
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        signal.alarm(0)
        result['terminal_at_UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['usage'] = {'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - start, 'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        with (out / 'RESULT.json').open('xb') as handle:
            handle.write((json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n').encode())
        print(json.dumps({'state': result['state'], 'usage': result['usage']}))


if __name__ == '__main__':
    main()
