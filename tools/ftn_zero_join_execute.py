"""One local FTN candidate-zero audit with an external 60-second deadline.

This wrapper does not grant execution authority. The integrator must separately
authorize the exact reviewed freeze. It never applies zeros or scores forecasts.
RSS is sampled, not an asserted continuous or kernel-enforced memory maximum.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time

START = time.monotonic()
VERSION = "ftn-explicit-zero-join-execution-v1"
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
LIMITS = {"worker_payload_bytes": 3932160, "supervisor_payload_bytes": 131072,
          "control_bytes_per_process": 65536, "pipe_bytes_per_stream": 8192,
          "RSS_poll_seconds": .01, "RSS_stop_bytes": 251658240,
          "worker_wall_seconds": 50, "supervisor_worker_stop_seconds": 53,
          "combined_CPU_stop_seconds": 54, "supervisor_wall_seconds": 59}
CONFIG_SHA = "fb1a4e2c745592fa2d9180f70c758ed90d20417743263b2c021cc118679ba99d"
BASE = Path("/workspace/website-methods-research/resumed")
OUTPUT = BASE / "ftn-explicit-zero-join-v1-20261023"
SUPERVISOR = BASE / "ftn-explicit-zero-join-v1-supervisor-20261023"


def utc():
    return datetime.now(timezone.utc).isoformat()


def no_symlinks(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("canonical absolute path required")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("symlink forbidden")
    return path


def authenticate(binding, *, body=False):
    if set(binding) != {"path", "sha256", "bytes"}:
        raise ValueError("exact file binding required")
    path = no_symlinks(binding["path"])
    before = path.stat()
    if (not stat.S_ISREG(before.st_mode) or type(binding["bytes"]) is not int
            or before.st_size != binding["bytes"] or before.st_size > 67108864
            or (body and before.st_size > 1048576)):
        raise ValueError("bounded regular frozen file required")
    sha, chunks = hashlib.sha256(), []
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            sha.update(chunk)
            if body:
                chunks.append(chunk)
    after = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if (tuple(getattr(before, x) for x in fields) != tuple(getattr(after, x) for x in fields)
            or sha.hexdigest() != binding["sha256"]):
        raise ValueError("frozen file changed")
    return b"".join(chunks) if body else None


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


def preflight(args):
    path = no_symlinks(args.freeze)
    freeze = strict_json(authenticate({"path": str(path), "sha256": args.freeze_sha256,
                                     "bytes": path.stat().st_size}, body=True))
    if (set(freeze) != {"schema_version", "state", "runner", "config", "code", "environment",
                       "python_binary", "timeout", "limits", "supervisor", "cache", "source_policy"}
            or freeze["schema_version"] != VERSION or freeze["state"] != "BOUND_READY"
            or freeze["limits"] != LIMITS or freeze["supervisor"] != str(SUPERVISOR)
            or freeze["config"]["sha256"] != CONFIG_SHA
            or Path(freeze["runner"]["path"]) != Path(__file__).absolute()):
        raise ValueError("exact bound execution freeze required")
    for name in ("runner", "python_binary", "timeout", "source_policy"):
        authenticate(freeze[name])
    config = strict_json(authenticate(freeze["config"], body=True))
    expected_code = {str(Path(freeze["runner"]["path"]).parent.parent / name): digest
                     for name, digest in config["code_sha256"].items()}
    if ({x["path"]: x["sha256"] for x in freeze["code"]} != expected_code
            or len(freeze["code"]) != 3):
        raise ValueError("exact helper/storage/reference code bindings required")
    for binding in freeze["code"]:
        authenticate(binding)
    if (config["state"] != "BOUND_READY" or config["output"] != str(OUTPUT)
            or config["cache"] != freeze["cache"]
            or config["source_policy"] != freeze["source_policy"]
            or config["environment"] != freeze["environment"]):
        raise ValueError("bound registration association mismatch")
    if (config["budgets"]["new_retained_bytes"] != 4194304
            or config["budgets"]["wall_seconds"] != 60
            or config["budgets"]["CPU_seconds"] != 60
            or config["budgets"]["combined_RSS_bytes"] != 268435456
            or config["budgets"]["HTTP"] != 0):
        raise ValueError("unchanged finite job budget required")
    env = freeze["environment"]
    if (sys.version != env["python"]
            or Path(sys.executable).resolve() != Path(env["executable"]).resolve()
            or Path(sys.executable).resolve() != Path(freeze["python_binary"]["path"])
            or set(env["packages"]) != {"numpy", "pandas", "pyarrow"}
            or any(os.environ.get(name) != "1" for name in THREADS)
            or not sys.dont_write_bytecode):
        raise ValueError("frozen Python -B and one-thread environment required")
    for name, version in env["packages"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError("dependency version changed")
    for target in (OUTPUT, SUPERVISOR):
        no_symlinks(target)
    if not args.worker:
        timeout_argv = [freeze["timeout"]["path"], "--signal=KILL", "60s", env["executable"], "-B",
                        freeze["runner"]["path"], "--freeze", str(args.freeze),
                        "--freeze-sha256", args.freeze_sha256]
        parent = Path(f"/proc/{os.getppid()}")
        if (Path(os.readlink(parent / "exe")) != Path(freeze["timeout"]["path"])
                or (parent / "cmdline").read_bytes().rstrip(b"\0").split(b"\0") !=
                   [x.encode() for x in timeout_argv]):
            raise ValueError("exact pinned external timeout 60s invocation required")
    elif os.getppid() != args.supervisor_pid:
        raise ValueError("worker parent identity changed")
    return freeze, config


def storage_for(freeze, *, worker):
    """Add stricter per-job caps without editing the shared storage helper.

    Charge attempted serialized allocations before the original writer. Counting
    repeated/deduplicated bodies conservatively also covers abandoned CAS writes.
    Each process reserves 64KiB for registry/owner writes; no new control route.
    """
    root = str(Path(freeze["runner"]["path"]).parent.parent)
    sys.path.insert(0, root)
    from nfl_lab.operational_storage import OperationalStorage
    original_write, original_control = OperationalStorage.write_bytes, OperationalStorage._atomic_plain
    ceiling = LIMITS["worker_payload_bytes" if worker else "supervisor_payload_bytes"]
    scope = OUTPUT if worker else SUPERVISOR
    charged = {"payload": 0, "control": 0}

    def write(self, path, body, *, replace=False):
        destination = no_symlinks(path)
        if destination == scope or scope not in destination.parents or replace:
            raise ValueError("fresh wrapper-owned output path required")
        serialized = bytes(body)
        if charged["payload"] + len(serialized) > ceiling:
            raise ValueError("job payload allocation cap")
        charged["payload"] += len(serialized)
        return original_write(self, destination, serialized, replace=False)

    def control(self, path, body, *, replace=True):
        if charged["control"] + len(body) > LIMITS["control_bytes_per_process"]:
            raise ValueError("job control allocation cap")
        charged["control"] += len(body)
        return original_control(self, path, body, replace=replace)

    OperationalStorage.write_bytes, OperationalStorage._atomic_plain = write, control
    policy = strict_json(authenticate(freeze["source_policy"], body=True))
    return OperationalStorage(freeze["cache"], policy), charged


def deny_external_effects(event, args):
    if (event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.fork",
            "os.forkpty", "os.posix_spawn", "pty.spawn"}):
        raise RuntimeError("network and child-process creation denied for source worker")


def deadline(signum, frame):
    raise TimeoutError("whole-job finalization reserve reached")


def worker(args):
    sys.addaudithook(deny_external_effects)
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, LIMITS["worker_wall_seconds"] - (time.monotonic() - START)))
    resource.setrlimit(resource.RLIMIT_CPU, (55, 55))
    freeze, _ = preflight(args)
    _, charged = storage_for(freeze, worker=True)
    from nfl_lab.ftn_zero_join import run_join
    try:
        result = run_join(freeze["config"]["path"], freeze["config"]["sha256"])
        preflight(args)  # Reauthenticate versions/binary/config/code before success.
        print(json.dumps({"state": result["state"], "HTTP": 0, "charged_allocations": charged,
                          "wall_seconds_before_exit": time.monotonic() - START,
                          "CPU_seconds_before_exit": time.process_time()}, allow_nan=False), flush=True)
        return 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def tree_usage(pid):
    todo, seen, rss, cpu = [pid], set(), 0, 0.
    ticks = os.sysconf("SC_CLK_TCK")
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            status = Path(f"/proc/{current}/status").read_text()
            rss += next((int(x.split()[1]) * 1024 for x in status.splitlines() if x.startswith("VmRSS:")), 0)
            raw = Path(f"/proc/{current}/stat").read_text()
            fields = raw[raw.rfind(")") + 2:].split()
            cpu += (int(fields[11]) + int(fields[12])) / ticks
            for task in Path(f"/proc/{current}/task").iterdir():
                todo.extend(int(x) for x in (task / "children").read_text().split())
        except (FileNotFoundError, ProcessLookupError):
            pass
    used = resource.getrusage(resource.RUSAGE_CHILDREN)
    return rss, cpu + used.ru_utime + used.ru_stime


def supervisor(args):
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 59 - (time.monotonic() - START)))
    resource.setrlimit(resource.RLIMIT_CPU, (58, 58))
    freeze, _ = preflight(args)
    storage, charged = storage_for(freeze, worker=False)
    with storage._locked():
        if OUTPUT.exists() or SUPERVISOR.exists():
            raise ValueError("invocation namespace consumed; no retries")
        storage.register_root(SUPERVISOR)
        storage.atomic_json(SUPERVISOR / "JOB_CONSUMED.json", {
            "schema_version": VERSION, "freeze_sha256": args.freeze_sha256,
            "config_sha256": CONFIG_SHA, "started_utc": utc(), "invocations": 1, "HTTP": 0,
            "external_wall_seconds": 60, "automatic_retries": 0})
        storage.write_bytes(SUPERVISOR / "execution-freeze.json", Path(args.freeze).read_bytes())
    parent_pid = os.getpid()

    def orphan_guard():
        if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise OSError("PDEATHSIG unavailable")
        if os.getppid() != parent_pid:
            os.kill(os.getpid(), signal.SIGKILL)

    child, stop, error = None, None, None
    peak, cpu_peak, max_pipes = 0, 0., LIMITS["pipe_bytes_per_stream"]
    logs = {"stdout": bytearray(), "stderr": bytearray()}
    dropped = {"stdout": 0, "stderr": 0}
    selector = selectors.DefaultSelector()
    try:
        child = subprocess.Popen([sys.executable, "-B", __file__, "--freeze", str(args.freeze),
            "--freeze-sha256", args.freeze_sha256, "--worker", "--supervisor-pid", str(parent_pid)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=os.environ.copy(), preexec_fn=orphan_guard)
        for stream, label in ((child.stdout, "stdout"), (child.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        while child.poll() is None or selector.get_map():
            # Include the pinned external timeout process as well as Python and
            # every live descendant. Reaped worker CPU is added by tree_usage.
            rss, cpu = tree_usage(os.getppid())
            peak, cpu_peak = max(peak, rss), max(cpu_peak, cpu)
            if rss > LIMITS["RSS_stop_bytes"]:
                stop = stop or "COMBINED_RSS_SAFETY_MARGIN"
            elif cpu >= LIMITS["combined_CPU_stop_seconds"]:
                stop = stop or "COMBINED_CPU_FINALIZATION_RESERVE"
            elif time.monotonic() - START >= LIMITS["supervisor_worker_stop_seconds"]:
                stop = stop or "WORKER_WALL_FINALIZATION_RESERVE"
            if stop and child.poll() is None:
                child.kill()
            for key, _ in selector.select(LIMITS["RSS_poll_seconds"]):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                kept = min(len(chunk), max_pipes - len(logs[key.data]))
                logs[key.data].extend(chunk[:kept])
                dropped[key.data] += len(chunk) - kept
        child.wait(timeout=1)
    except BaseException as exc:
        error = {"type": type(exc).__name__, "reason": "SUPERVISOR_FAILURE_NO_RETRY"}
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=1)
        selector.close()
        if child is not None:
            for stream in (child.stdout, child.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
    returncode = child.returncode if child is not None else None
    try:
        preflight(args)
    except BaseException as exc:
        error = {"type": type(exc).__name__, "reason": "EXIT_BINDING_CHECK_FAILED"}
    rss, cpu = tree_usage(os.getppid())
    peak, cpu_peak = max(peak, rss), max(cpu_peak, cpu)
    elapsed = time.monotonic() - START
    if elapsed >= 59 or cpu >= 60 or peak > 268435456:
        stop = stop or "FINALIZATION_RESOURCE_LIMIT"
    success = returncode == 0 and stop is None and error is None
    for label, value in logs.items():
        storage.write_bytes(SUPERVISOR / f"private/{label}.log", bytes(value))
    child_used = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {"schema_version": VERSION, "state": "CANDIDATE_AUDIT_ONLY" if success else "FAILED",
        "freeze_sha256": args.freeze_sha256, "config_sha256": CONFIG_SHA,
        "child_returncode": returncode, "stop_reason": stop, "supervisor_error": error,
        "HTTP": 0, "automatic_retries": 0, "zeros_applied": 0,
        "combined_RSS_peak_sampled_bytes": peak, "RSS_poll_seconds": .01,
        "sampled_process_tree_root": "pinned external timeout parent",
        "RSS_stop_bytes": LIMITS["RSS_stop_bytes"],
        "RSS_limit_bytes": 268435456, "RSS_transient_peaks_may_be_missed": True,
        "child_individual_ru_maxrss_bytes": child_used.ru_maxrss * 1024,
        "combined_CPU_seconds_before_receipt_write": cpu,
        "wall_seconds_before_receipt_write": elapsed,
        "external_timeout_seconds": 60, "worker_orphan_guard": "Linux PDEATHSIG SIGKILL",
        "network_process_guard": "Python audit hooks; reviewed local helper, not a hostile-code sandbox",
        "pipe_bytes_dropped": dropped, "supervisor_charged_allocations_before_receipt": dict(charged),
        "job_allocation_ceiling_bytes": 4194304, "numerical_threads": 1, "finished_utc": utc()}
    storage.atomic_json(SUPERVISOR / "JOB_FINISHED.json", receipt)
    rss, cpu = tree_usage(os.getppid())
    observed_wall = time.monotonic() - START
    print(json.dumps({"state": receipt["state"], "receipt": str(SUPERVISOR / "JOB_FINISHED.json"),
        "receipt_sha256": hashlib.sha256((SUPERVISOR / "JOB_FINISHED.json").read_bytes()).hexdigest(),
        "tool_wall_seconds_after_receipt_write": observed_wall,
        "tool_combined_CPU_seconds_after_receipt_write": cpu,
        "combined_RSS_peak_sampled_bytes": max(peak, rss), "HTTP": 0, "zeros_applied": 0}, allow_nan=False), flush=True)
    signal.setitimer(signal.ITIMER_REAL, 0)
    return 0 if success and observed_wall < 60 and cpu < 60 and rss <= 268435456 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--freeze-sha256", required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--supervisor-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    return worker(args) if args.worker else supervisor(args)


if __name__ == "__main__":
    raise SystemExit(main())
