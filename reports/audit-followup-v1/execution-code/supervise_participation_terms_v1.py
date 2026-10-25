"""One guarded terms-only capture; no game data or predictive evaluation."""
import hashlib, json, os, resource, selectors, signal, subprocess, sys, time
from pathlib import Path
BEGIN = time.monotonic()
resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
os.umask(0o077)
ROOT = Path(__file__).resolve().parent
CODE = Path('/workspace/nfl-methods-integration')
sys.path.insert(0, str(CODE))

def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def usage(pgid):
    rss, cpu = 0, 0.0
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():
            continue
        try:
            values = (item / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(values[2]) == pgid:
                rss += int(values[21]) * os.sysconf('SC_PAGE_SIZE')
                cpu += sum(int(values[k]) for k in (11, 12, 13, 14)) / os.sysconf('SC_CLK_TCK')
        except (OSError, ValueError, IndexError):
            pass
    own = resource.getrusage(resource.RUSAGE_SELF)
    values = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    rss += int(values[21]) * os.sysconf('SC_PAGE_SIZE')
    cpu += own.ru_utime + own.ru_stime
    return rss, cpu

freeze_path = ROOT / 'TERMS_EXECUTION_FREEZE_V1A.json'
freeze = json.loads(freeze_path.read_text())
for item in freeze['bindings']:
    if sha(item['path']) != item['sha256']:
        raise ValueError('frozen binding changed: ' + item['path'])
if str(Path(sys.executable).resolve()) != freeze['environment']['resolved_executable'] or sys.version != freeze['environment']['python']:
    raise ValueError('frozen interpreter changed')
if Path(freeze['capture_output']).exists():
    raise FileExistsError('capture already consumed; no retry')
consumed = ROOT / 'SUPERVISOR_CONSUMED.json'
from nfl_lab.operational_storage import OperationalStorage
policy = json.loads(Path(freeze['source_policy_path']).read_text())
storage = OperationalStorage(freeze['cache'], policy)
storage.atomic_json(consumed, {'freeze_sha256': sha(freeze_path), 'invocations': 1}, replace=False)
if time.monotonic() - BEGIN >= 54 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > 536870912:
    raise RuntimeError('preflight consumed resource reserve; invocation stays consumed')
env = dict(os.environ, PYTHONPATH=str(CODE), PYTHONDONTWRITEBYTECODE='1',
    OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
remaining = 54 - (time.monotonic() - BEGIN)
if remaining <= 0:
    raise RuntimeError('no child wall budget remains; invocation stays consumed')
# An isolated child needs its own timer: killing the outer supervisor's session
# cannot reach this new session. GNU timeout without --foreground kills this
# complete child process group even if its supervising Python parent dies.
command = ['/usr/bin/timeout', '--signal=KILL', f'{remaining:.3f}s',
    sys.executable, '-B', '-m', 'nfl_lab.participation_qualification_probe',
    '--config', freeze['config_path'], '--config-sha256', freeze['config_sha256']]
p = subprocess.Popen(command, cwd=CODE, env=env, stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, start_new_session=True)
selector = selectors.DefaultSelector()
selector.register(p.stdout, selectors.EVENT_READ)
reason, peak, logged = None, 0, bytearray()
while p.poll() is None:
    for key, _ in selector.select(timeout=0):
        body = os.read(key.fileobj.fileno(), 65536)
        if body:
            if len(logged) + len(body) > 1048576:
                reason = 'STDOUT_LIMIT'
                break
            logged.extend(body)
        else:
            selector.unregister(key.fileobj)
    rss, cpu = usage(p.pid)
    peak = max(peak, rss)
    if time.monotonic() - BEGIN >= 54:
        reason = reason or 'WALL_FINALIZATION_RESERVE'
    if cpu >= 54:
        reason = reason or 'CPU_FINALIZATION_RESERVE'
    if rss > 536870912:
        reason = reason or 'COMBINED_RSS_LIMIT'
    if reason:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        break
    time.sleep(.05)
while True:
    body = p.stdout.read(65536)
    if not body:
        break
    if len(logged) + len(body) > 1048576:
        reason = reason or 'STDOUT_LIMIT'
        break
    logged.extend(body)
p.stdout.close()
selector.close()
# Capture preflight/imports, HTTP and quota work ran inside the guarded child;
# supervisor startup itself is within timeout60 and the CPU limit. Only
# immutable logging remains, with six seconds reserved inside the outer
# timeout60 guard. The CLI itself also has the registered resource checks.
storage.write_bytes(ROOT / 'supervisor-stdout.log', bytes(logged), replace=False)
own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
wall = time.monotonic() - BEGIN
cpu = own.ru_utime + own.ru_stime + child.ru_utime + child.ru_stime
if wall > 60 or cpu > 60:
    reason = reason or 'FINAL_RESOURCE_LIMIT'
receipt = {'state': 'COMPLETED' if p.returncode == 0 and reason is None else 'FAILED',
    'returncode': p.returncode, 'limit_reason': reason, 'wall_seconds': wall,
    'wall_scope': 'supervisor-observed; external timeout60 enforces launcher-inclusive hard ceiling',
    'CPU_seconds': cpu, 'peak_combined_RSS_bytes': peak, 'threads': 1,
    'automatic_retries': 0, 'scope': 'terms documentation only; zero game/PDF/player/model/score extraction',
    'storage': storage.snapshot()}
storage.atomic_json(ROOT / 'supervisor-completion.json', receipt, replace=False)
print(json.dumps(receipt, allow_nan=False))
sys.exit(0 if receipt['state'] == 'COMPLETED' else 1)
