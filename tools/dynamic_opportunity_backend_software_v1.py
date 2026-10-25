"""One bounded six-method fictional consumer packet; no NFL execution."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import unittest

VERSION = 'dynamic-opportunity-backend-software-v1-20261023'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', required=True)
    parser.add_argument('--freeze-sha256', required=True)
    args = parser.parse_args()
    if sha(args.freeze) != args.freeze_sha256:
        raise RuntimeError('exact consumer software freeze required')
    freeze = json.loads(Path(args.freeze).read_text())
    root = Path(__file__).resolve().parents[1]
    if freeze['schema_version'] != VERSION or freeze['root'] != str(root):
        raise RuntimeError('exact software root/version required')
    required = {str(p) for p in (root/'nfl_lab').glob('*.py')}
    required |= {str(root/p) for p in ('tests/test_dynamic_opportunity_backend_contracts.py',
        'tools/dynamic_opportunity_backend_software_v1.py', 'tools/offline_report_imports_v1.py',
        'tools/direct_booster_frozen_report.py')}
    if set(freeze['bindings']) != required:
        raise RuntimeError('all imported lab modules and exact new packet required')
    for path, ref in freeze['bindings'].items():
        item = Path(path)
        if (str(item) != ref['path'] or item.resolve() != item or any(p.is_symlink() for p in (item, *item.parents))
                or item.stat().st_size != ref['bytes'] or sha(item) != ref['sha256']):
            raise RuntimeError('consumer software binding changed')
    env = freeze['interpreter']
    if (sys.executable != env['executable'] or sys.version != env['version'] or not sys.dont_write_bytecode
            or str(Path(sys.executable).resolve()) != env['binary'] or sha(env['binary']) != env['sha256']):
        raise RuntimeError('exact original Python -B required')
    caps = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
            'VECLIB_MAXIMUM_THREADS', 'OMP_THREAD_LIMIT', 'ARROW_IO_THREADS')
    if any(os.environ.get(name) != '2' for name in caps):
        raise RuntimeError('all numerical thread caps2 required')
    limits = dict(invocations=1, methods=6, wall_seconds=120, CPU_seconds=120,
                  RSS_bytes=536870912, threads=2, children=0, old_suite_NFL_source_model_HTTP_CAS=0, retries=0)
    if freeze['limits'] != limits:
        raise RuntimeError('fixed six-method software budget required')
    output = Path(freeze['output'])
    output.mkdir(exist_ok=False)
    (output/'CONSUMED.json').write_text('{"invocations":1,"retries":0}\n')
    start, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    counts = dict(denied_effects=0, lines=0, resource_checks=0)
    result = None
    exception = None
    log = io.StringIO()

    def budget():
        counts['resource_checks'] += 1
        if (time.monotonic()-start >= 118 or time.process_time()-cpu >= 118
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 > limits['RSS_bytes']):
            raise RuntimeError('consumer software resource allowance consumed')

    def trace(frame, event, value):
        if event == 'line':
            counts['lines'] += 1
            if counts['lines'] % 200 == 0:
                budget()
        return trace

    def audit(event, values):
        denied = event.startswith(('socket.', 'subprocess.')) or event in {
            'os.system', 'os.fork', 'os.forkpty', 'os.exec', 'os.posix_spawn', 'pty.spawn'}
        if event == 'open' and values and isinstance(values[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(values[0])
            denied |= '/workspace/website-methods-research/' in name or name.endswith(('.parquet', '.csv', '.joblib', '.pkl', '.pickle'))
        if denied:
            counts['denied_effects'] += 1
            raise RuntimeError('consumer software forbids source/model/network/process effects')

    def timeout(signum, frame):
        raise TimeoutError('bounded consumer software wall allowance consumed')

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 119)
    sys.addaudithook(audit)
    sys.settrace(trace)
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root/'tools'))
    try:
        import pyarrow as pa
        pa.set_cpu_count(2)
        pa.set_io_thread_count(2)
        module_spec = importlib.util.spec_from_file_location('new_dynamic_consumers', root/'tests/test_dynamic_opportunity_backend_contracts.py')
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        if suite.countTestCases() != 6:
            raise RuntimeError('exactly six new consumer methods required')
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        budget()
    except BaseException as error:
        exception = dict(type=type(error).__name__, message=str(error))
    finally:
        sys.settrace(None)
        signal.setitimer(signal.ITIMER_REAL, 0)
        wall, used = time.monotonic()-start, time.process_time()-cpu
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        passed = (result is not None and result.testsRun == 6 and result.wasSuccessful() and not result.skipped
            and exception is None and counts['denied_effects'] == 0 and wall < 120 and used < 120 and peak <= limits['RSS_bytes'])
        receipt = dict(schema_version=VERSION, state='PASS' if passed else 'FAILED',
            tests_run=result.testsRun if result else None, failures=len(result.failures) if result else None,
            errors=len(result.errors) if result else None, skips=len(result.skipped) if result else None,
            wall_seconds_before_receipt_write=wall, CPU_seconds_before_receipt_write=used,
            process_highwater_bytes=peak, limits=limits, counts=counts, exception=exception, log=log.getvalue(),
            resource_scope='Single process highwater and traced checks; resource interval ends before receipt write; not continuous RSS certification',
            freeze_sha256=args.freeze_sha256, NFL_predictive_validation=False, actual_backend_effort='UNATTESTED')
        body = (json.dumps(receipt, sort_keys=True, indent=2)+'\n').encode()
        if len(body) > 1048576:
            raise RuntimeError('bounded consumer receipt too large')
        (output/'FINISHED.json').write_bytes(body)
        print(json.dumps({k: receipt[k] for k in ('state', 'tests_run', 'failures', 'errors', 'skips',
            'wall_seconds_before_receipt_write', 'CPU_seconds_before_receipt_write', 'process_highwater_bytes', 'exception')}))
        print('receipt_sha256', hashlib.sha256(body).hexdigest())
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
