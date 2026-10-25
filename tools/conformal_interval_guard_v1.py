"""Existing explicit-PID guard structure for one cached interval worker.

One scientific process, no worker children. The stdlib supervisor reuses the
reviewed exact-PID/start-ticks/Z-X sampler and imports owned storage only after
the worker has exited, avoiding duplicate heavy dependency residency.
"""
import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import time

START = time.monotonic()
CPU_START = time.process_time()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from direct_booster_frozen_report_run import arm_parent_death, pin, sha

CAPS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
    'VECLIB_MAXIMUM_THREADS', 'OMP_THREAD_LIMIT', 'ARROW_IO_THREADS')
TARGETS = ('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd')


def load(args, *, environment=False):
    if sha(args.freeze) != args.freeze_sha256:
        raise ValueError('exact compact interval execution freeze required')
    packet = json.loads(Path(args.freeze).read_text())
    if packet['state'] != 'SEALED_ROOT_AND_REVIEWER' or packet['seal']['integrator'] != '/root' or not packet['seal']['reviewer'].startswith('/root/'):
        raise ValueError('root and separate reviewer interval seal required')
    if packet['preexec_review'] != 'PASS' or packet['code_root'] != str(ROOT):
        raise ValueError('exact reviewed interval code root required')
    for ref in packet['bindings']:
        pin(ref)
    for key in ('python_binary', 'external_timeout', 'parent_environment'):
        pin(packet[key])
    if not sys.dont_write_bytecode or any(os.environ.get(name) != '2' for name in CAPS):
        raise ValueError('Python-B and seven numerical caps2 required')
    spec = packet['execution_metadata']
    policy = json.loads(Path(packet['policy']['path']).read_text())
    if (policy['registration_id'] != spec['registration_id'] or tuple(policy['targets']) != TARGETS
        or policy['alpha'] != .2 or policy['blocks'] != [dict(calibration=2022,evaluation=2023),dict(calibration=2023,evaluation=2024)]
        or policy['budgets'] != dict(invocations=1,wall_seconds=300,CPU_seconds=300,RSS_bytes=536870912,
            numerical_thread_caps=2,new_retained_bytes=16777216,shared_retention_bytes=536870912,radii=20,
            new_base_fits=0,new_base_predictions=0,HTTP=0,retries=0,semantic_projection_row_cap=600000)):
        raise ValueError('fixed original interval protocol/budget changed')
    if spec['state'] != 'ROOT_REGISTERED_SEALED' or packet['limits'] != dict(wall_seconds=300, CPU_seconds=300,
        combined_RSS_bytes=536870912, numerical_threads=2, new_retained_bytes=16777216,
        shared_retention_bytes=536870912, workers=1, worker_children=0, HTTP=0, base_fits_predictions_models_sources=0, retries=0):
        raise ValueError('exact twenty-radius interval resource contract required')
    if environment:
        parent = json.loads(Path(packet['parent_environment']['path']).read_text())
        env = parent['environment']
        if sys.executable != env['executable'] or sys.version != env['python'] or not env['file_bindings']:
            raise ValueError('original DIRECT Python and complete environment required')
        if str(Path(sys.executable).resolve()) != packet['python_binary']['path']:
            raise ValueError('original Python binary differs')
        for ref in env['file_bindings']:
            pin(ref)
        if sha(env['inventory_path']) != env['inventory_sha256']:
            raise ValueError('original environment inventory differs')
        for name, version in env['packages'].items():
            if importlib.metadata.version(name) != version:
                raise ValueError('original package version differs')
    return packet, spec


def worker(args):
    arm_parent_death(args.parent_pid)
    resource.setrlimit(resource.RLIMIT_CPU, (298, 298))
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError('interval worker wall allowance')))
    signal.setitimer(signal.ITIMER_REAL, max(.01, 297-(time.monotonic()-START)))
    denied = [0]
    metadata_hash_phase = [False]
    allowed_parquet = set()
    def audit(event, values):
        forbidden = event.startswith(('socket.', 'subprocess.')) or event in {
            'os.system', 'os.fork', 'os.forkpty', 'os.exec', 'os.posix_spawn', 'pty.spawn'}
        if event == 'open' and values and isinstance(values[0], (str, bytes, os.PathLike)):
            path = os.fsdecode(values[0])
            if not metadata_hash_phase[0]:
                forbidden |= path.endswith(('.joblib', '.pkl', '.pickle', '.csv'))
                if path.endswith('.parquet'):
                    forbidden |= path not in allowed_parquet
        if forbidden:
            denied[0] += 1
            raise RuntimeError('interval worker forbids network, child, raw CSV and model artifacts')
    sys.addaudithook(audit)
    def verified_load():
        # Complete installed package inventories can include their fictional
        # CSV/pickle fixtures. The unchanged pin() only hashes them here; no
        # parser/unpickler/model/science route is entered in this narrow phase.
        metadata_hash_phase[0] = True
        try:
            return load(args, environment=True)
        finally:
            metadata_hash_phase[0] = False
    packet, spec = verified_load()
    allowed_parquet.update(ref['path'] for ref in spec['queries'].values())
    allowed_parquet.update(ref['path'] for group in spec['cdf'].values() for ref in group.values())
    allowed_parquet.update(str(Path(spec['output'])/'private'/'intervals'/str(year)/(target+'.parquet'))
        for year in (2023,2024) for target in TARGETS)
    allowed_parquet.update(str(Path(spec['output'])/'private'/'subgroups'/(target+'.parquet')) for target in TARGETS)
    sys.path.insert(0, str(ROOT))
    from offline_report_imports_v1 import offline_dependency_imports
    with offline_dependency_imports():
        from nfl_lab import conformal_interval_campaign as campaign
        from direct_booster_frozen_report import no_science
        from direct_xgboost_binary_recovery import process_free_threads
        from threadpoolctl import threadpool_limits
        from contextlib import ExitStack
        from unittest.mock import patch
        from nfl_lab.cdf_engine import LeafCDFModel
    def guard():
        used = resource.getrusage(resource.RUSAGE_SELF)
        if (time.monotonic()-START >= 280 or time.process_time()-CPU_START >= 280
            or used.ru_maxrss*1024 >= 503316480 or denied[0]):
            raise RuntimeError('interval worker resource/side-effect safety stop')
    def forbidden(*a, **k):
        raise AssertionError('interval experiment cannot fit/infer a base CDF')
    with process_free_threads(packet['libc']), threadpool_limits(limits=2), no_science(), ExitStack() as stack:
        for name in ('fit', 'predict_batches'):
            stack.enter_context(patch.object(LeafCDFModel, name, forbidden))
        campaign.run(spec, guard=guard, final_verify=verified_load)
    guard()
    print(json.dumps(dict(state='INTERVAL_REPORT_COMPLETE', radii=20, denied_effects=denied[0],
        new_base_fits_predictions_models_source_HTTP=0)), flush=True)


def supervisor(args):
    def deny_network(event, values):
        if event.startswith('socket.'):
            raise RuntimeError('interval supervisor network forbidden')
    sys.addaudithook(deny_network)
    packet, spec = load(args)
    # Import only the unchanged stdlib sampler, never its registration/run path.
    binding = packet['sampler']
    pin(binding)
    module_spec = importlib.util.spec_from_file_location('existing_interval_pid_sampler', binding['path'])
    sampler = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(sampler)
    parent = Path('/proc')/str(os.getppid())
    expected = [packet['external_timeout']['path'], '--signal=KILL', '300s', sys.executable, '-B', str(Path(__file__).resolve()),
        '--freeze', args.freeze, '--freeze-sha256', args.freeze_sha256]
    actual = [x.decode() for x in (parent/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')]
    if (parent/'exe').resolve() != Path(packet['external_timeout']['path']) or actual != expected:
        raise ValueError('exact pinned GNU timeout300 parent required')
    output = Path(spec['output'])
    if (output/'CONSUMED.json').exists() or (output/'SUPERVISOR_TERMINAL.json').exists():
        raise RuntimeError('single interval job already consumed')
    required = [sampler.process_binding(os.getppid()), sampler.process_binding(os.getpid())]
    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--freeze', args.freeze,
        '--freeze-sha256', args.freeze_sha256, '--worker', '--parent-pid', str(os.getpid())],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ.copy())
    try:
        child_binding = sampler.process_binding(child.pid)
    except (FileNotFoundError, ProcessLookupError):
        if child.poll() is None:
            child.kill(); child.wait(timeout=3)
            raise RuntimeError('live worker binding unavailable')
        child_binding = None
    selector = selectors.DefaultSelector()
    for stream in (child.stdout, child.stderr):
        selector.register(stream, selectors.EVENT_READ)
    logs = bytearray(); peak = cpu_peak = 0; reason = None
    try:
        while child.poll() is None or selector.get_map():
            for key, _ in selector.select(timeout=.01):
                body = os.read(key.fileobj.fileno(), 8192)
                if body:
                    logs.extend(body)
                else:
                    selector.unregister(key.fileobj)
            rss, cpu = sampler.required_usage(required, child, child_binding)
            peak, cpu_peak = max(peak, rss), max(cpu_peak, cpu)
            if time.monotonic()-START >= 290: reason = 'WALL_SAFETY_STOP'
            elif cpu >= 290: reason = 'CPU_SAFETY_STOP'
            elif rss >= 503316480: reason = 'RSS_SAFETY_STOP'
            elif len(logs) > 65536: reason = 'LOG_CAP'
            if reason:
                break
    except BaseException as error:
        reason = 'SAMPLER_FAILURE_'+type(error).__name__
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
        selector.close(); child.stdout.close(); child.stderr.close()
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    # Storage imports occur after reaping; the original writer/accounting remain.
    from offline_report_imports_v1 import offline_dependency_imports
    with offline_dependency_imports():
        sys.path.insert(0, str(ROOT))
        from direct_xgboost_binary_recovery import storage
    store, output = storage(spec)
    rss, cpu = sampler.required_usage(required)
    # required_usage already adds reaped-child CPU. Explicitly retain the
    # independently known self+children floor as well; peaks are nonconcurrent.
    final_cpu = max(cpu, time.process_time()+children.ru_utime+children.ru_stime)
    supervisor_highwater = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    peak, cpu_peak = max(peak, rss), max(cpu_peak, final_cpu)
    if max(children.ru_maxrss*1024, supervisor_highwater, peak) >= 536870912 or cpu_peak >= 300 or time.monotonic()-START >= 300:
        reason = reason or 'FINAL_RESOURCE_LIMIT'
    receipt = dict(state='COMPLETE' if child.returncode == 0 and reason is None and (output/'report.json').exists() else 'FAILED',
        returncode=child.returncode, limit_reason=reason, wall_seconds_before_receipt_write=time.monotonic()-START,
        CPU_seconds_before_receipt_write=cpu_peak, peak_sampled_combined_RSS_bytes=peak,
        child_ru_maxrss_bytes=children.ru_maxrss*1024, threads=2, worker_children=0,
        supervisor_ru_maxrss_bytes=supervisor_highwater,
        RSS_scope='unchanged exact-PID/Z-X-aware sampler incl timeout+supervisor+worker, individual child highwater crosscheck; brief peaks may escape sampling',
        retention=store.report_retention(), original_points_laws_sources_unchanged=True)
    store.write_bytes(output/'supervisor.log', bytes(logs[:65536]), replace=False)
    store.atomic_json(output/'SUPERVISOR_TERMINAL.json', receipt, replace=False)
    print(json.dumps(receipt), flush=True)
    if receipt['state'] != 'COMPLETE':
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', required=True); parser.add_argument('--freeze-sha256', required=True)
    parser.add_argument('--worker', action='store_true'); parser.add_argument('--parent-pid', type=int)
    args = parser.parse_args()
    if args.worker:
        worker(args)
    else:
        supervisor(args)


if __name__ == '__main__':
    main()
