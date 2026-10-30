"""One offline, fictional-only acceptance run under a prewritten source protocol."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import resource
import signal
import sys
import time
import unittest

BASE = Path(__file__).resolve().parents[1]
OUT = BASE/'reports/category-topfive-mae-release-priority-20261030/ordered-chart'
PROTOCOL = OUT/'CHART_TYPED_ADAPTER_PROTOCOL_V1.json'


def main():
    assert sys.flags.dont_write_bytecode
    protocol = json.loads(PROTOCOL.read_bytes())
    assert protocol['execution_authorized_by_root'] is True
    assert protocol['resources'] == {'CPU_seconds': 10, 'wall_seconds': 15,
        'RSS_bytes': 335544320, 'attempts': 1, 'NFL_model_deserializations': 0,
        'NFL_sources': 0, 'fits': 0, 'HTTP': 0, 'CAS': 0}
    for path, ref in protocol['sources'].items():
        body = (BASE/path).read_bytes()
        assert len(body) == ref['bytes'] and hashlib.sha256(body).hexdigest() == ref['sha256']
    result_path = OUT/'CHART_TYPED_ADAPTER_RESULT_V1.json'
    assert not result_path.exists() and not (OUT/'CHART_TYPED_ADAPTER_CONSUMED_V1.json').exists()
    cpu, wall = time.process_time(), time.monotonic()
    (OUT/'CHART_TYPED_ADAPTER_CONSUMED_V1.json').write_text(json.dumps({
        'state': 'ONE_FICTIONAL_SOFTWARE_ATTEMPT_CONSUMED',
        'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'protocol_sha256': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()})+'\n')
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('finite fictional allowance')))
    signal.alarm(14)
    blocked = []

    def audit(event, args):
        if event.startswith('socket.') or event.startswith('pickle.') or event in ['subprocess.Popen', 'os.system', 'os.fork', 'os.posix_spawn']:
            blocked.append(event)
            raise RuntimeError('offline fictional-only software check')
        if event == 'open' and isinstance(args[0], str) and args[0].startswith('/workspace/'):
            if Path(args[0]).suffix in ['.parquet', '.joblib', '.pickle', '.pkl', '.zip', '.gz', '.csv']:
                blocked.append('NFL_artifact_open')
                raise RuntimeError('no NFL data/model artifact access')
    sys.addaudithook(audit)
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    result = {'state': 'FAILED_RETAINED', 'new_NFL_models_fits_forecasts_HTTP_CAS': 0,
              'source_hashes': {k: v['sha256'] for k, v in protocol['sources'].items()}}
    try:
        sys.path.insert(0, str(BASE))
        import importlib.util
        spec = importlib.util.spec_from_file_location('chart_mae_fictional_checks', BASE/'tools/category_topfive_chart_mae_future_checks_v1.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with (OUT/'CHART_TYPED_ADAPTER_CHECKS_V1.log').open('w') as log:
            outcome = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
        result.update(cases=outcome.testsRun, failures=len(outcome.failures), errors=len(outcome.errors))
        assert outcome.wasSuccessful() and outcome.testsRun == 12 and not blocked
        usage = {'CPU_seconds': time.process_time()-cpu, 'wall_seconds': time.monotonic()-wall,
                 'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
        assert usage['CPU_seconds'] < 10 and usage['wall_seconds'] < 15 and usage['RSS_bytes'] <= 335544320
        result.update(state='PASS_TWELVE_FICTIONAL_CHART_TYPED_ADAPTER_CASES', actual=usage,
                      blocked_calls=blocked, genuine_pregame_capture=0, deployment=0,
                      admission='NOT_ADMITTED_CURRENT_SOURCE_RESTORATION_CAPTURE_OWNER_GATES_REMAIN')
    except BaseException as exc:
        result.update(error_type=type(exc).__name__, error=str(exc), blocked_calls=blocked)
        raise
    finally:
        signal.alarm(0)
        result.setdefault('actual', {'CPU_seconds': time.process_time()-cpu, 'wall_seconds': time.monotonic()-wall,
            'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})
        result['finished_at_UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result_path.write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
        print(json.dumps({'state': result['state'], 'actual': result['actual']}))


if __name__ == '__main__':
    main()
