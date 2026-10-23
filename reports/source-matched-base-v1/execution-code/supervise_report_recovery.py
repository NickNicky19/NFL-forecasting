"""Frozen report recovery supervisor; no fitting or acquisition."""
import hashlib, importlib.metadata, json, os, resource, selectors, signal, subprocess, sys, time
from pathlib import Path
BEGIN = time.monotonic()
BEFORE = resource.getrusage(resource.RUSAGE_SELF)
ROOT = Path(__file__).resolve().parent
CODE = Path('/workspace/nfl-methods-integration')
os.umask(0o077)
sys.path.insert(0, str(CODE))
def proc_usage(pid):
    # Live children contribute own CPU; reaped descendants roll into parent cutime/cstime.
    rss, cpu = 0, 0.0
    ticks = os.sysconf('SC_CLK_TCK')
    pages = os.sysconf('SC_PAGE_SIZE')
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            values = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(values[2]) != pid:
                continue
            cpu += sum(int(values[index]) for index in (11, 12, 13, 14)) / ticks
            rss += int(values[21]) * pages
        except (OSError, ValueError, IndexError):
            continue
    return rss, cpu
from nfl_lab.operational_sources import load_source_policy
from nfl_lab.operational_storage import OperationalStorage

def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

freeze_path = ROOT / 'RECOVERY_EXECUTION_FREEZE.json'
freeze = json.loads(freeze_path.read_text())
for item in freeze['bindings']:
    if sha(item['path']) != item['sha256']:
        raise ValueError('frozen binding changed: ' + item['path'])
if str(Path(sys.executable).resolve()) != str(Path(freeze['environment']['executable']).resolve()):
    raise ValueError('wrong dependency interpreter')
if sys.version != freeze['environment']['python']:
    raise ValueError('Python version changed')
for name, version in freeze['environment']['packages'].items():
    if importlib.metadata.version(name) != version:
        raise ValueError('dependency version changed: ' + name)
# Capability imports before consuming the one actual invocation; no input decoding.
from nfl_lab.source_matched_report_recovery import run_recovery
plan_path = Path(freeze['plan_path'])
plan = json.loads(plan_path.read_text())
parent_plan = json.loads(Path(plan['parent_config']['path']).read_text())
storage = OperationalStorage(Path(parent_plan['cache']),
    load_source_policy(parent_plan['source_policy']['path']), state=None)
storage.register_root(ROOT)
if (ROOT / 'recovery-supervisor-consumed.json').exists():
    raise FileExistsError('one invocation already consumed')
storage.atomic_json(ROOT / 'recovery-supervisor-consumed.json',
    {'invocations': 1, 'freeze_sha256': sha(freeze_path)}, replace=False)
env = dict(os.environ, PYTHONPATH=str(CODE), PYTHONDONTWRITEBYTECODE='1',
           OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2')
cmd = [sys.executable, '-B', str(ROOT / 'run_report_recovery.py')]
reason = None
peak = 0
logged = bytearray()
p = subprocess.Popen(cmd, cwd=CODE, env=env, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, start_new_session=True)
selector = selectors.DefaultSelector()
selector.register(p.stdout, selectors.EVENT_READ)
while p.poll() is None:
    for key, _ in selector.select(timeout=0):
        body = os.read(key.fileobj.fileno(), 65536)
        if body:
            if len(logged) + len(body) > 1048576:
                reason = 'SUPERVISOR_STDOUT_LIMIT'
                break
            logged.extend(body)
        else:
            selector.unregister(key.fileobj)
    if (ROOT / 'estimator-cpu-guard.json').exists():
        reason = reason or 'FORBIDDEN_NEW_ESTIMATOR_GUARD'
    rss, cpu = proc_usage(p.pid)
    own = resource.getrusage(resource.RUSAGE_SELF)
    values = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    rss += int(values[21]) * os.sysconf('SC_PAGE_SIZE')
    peak = max(peak, rss)
    cpu += own.ru_utime + own.ru_stime - BEFORE.ru_utime - BEFORE.ru_stime
    if time.monotonic() - BEGIN >= 598:
        reason = reason or 'WALL_LIMIT'
    elif cpu >= 898:
        reason = reason or 'CPU_LIMIT'
    elif rss > 2147483648:
        reason = reason or 'COMBINED_RSS_LIMIT'
    if reason:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        break
    time.sleep(.1)
while True:
    body = p.stdout.read(65536)
    if not body:
        break
    if len(logged) + len(body) > 1048576:
        reason = reason or 'SUPERVISOR_STDOUT_LIMIT'
        break
    logged.extend(body)
p.stdout.close()
selector.close()
storage.write_bytes(ROOT / 'recovery-supervisor-stdout.log', bytes(logged), replace=False)
own = resource.getrusage(resource.RUSAGE_SELF)
child = resource.getrusage(resource.RUSAGE_CHILDREN)
wall = time.monotonic() - BEGIN
cpu = own.ru_utime + own.ru_stime - BEFORE.ru_utime - BEFORE.ru_stime + child.ru_utime + child.ru_stime
if wall > 600:
    reason = reason or 'FINAL_WALL_LIMIT'
if cpu > 900:
    reason = reason or 'FINAL_CPU_LIMIT'
receipt = {'state': 'COMPLETED' if p.returncode == 0 and reason is None else 'FAILED',
           'returncode': p.returncode, 'limit_reason': reason,
           'wall_seconds': wall, 'CPU_seconds': cpu, 'peak_combined_RSS_bytes': peak,
           'threads': 2, 'storage': storage.snapshot(),
           'new_HTTP_official_forecasts_confirmation': 0}
storage.atomic_json(ROOT / 'recovery-supervisor-completion.json', receipt, replace=False)
print(json.dumps(receipt))
sys.exit(0 if receipt['state'] == 'COMPLETED' else 1)
