"""Sequential storage/source phases for one bounded context-only diagnosis.

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
VERSION = "raw-orphan-context-execution-v1"
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
LIMITS = {"worker_payload_bytes": 786432, "supervisor_payload_bytes": 65536,
          "bootstrap_payload_bytes": 65536, "control_bytes_per_process": 32768,
          "pipe_bytes_per_stream_per_phase": 8192,
          "RSS_poll_seconds": .01, "RSS_stop_bytes": 251658240,
          "worker_wall_seconds": 50, "bootstrap_wall_seconds": 20,
          "supervisor_worker_stop_seconds": 53,
          "combined_CPU_stop_seconds": 54, "supervisor_wall_seconds": 59}
BASE = Path("/workspace/website-methods-research/resumed")
OUTPUT = BASE / "raw-orphan-context-v1-20261023"
SUPERVISOR = BASE / "raw-orphan-context-v1-supervisor-20261023"


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
            or Path(freeze["runner"]["path"]) != Path(__file__).absolute()):
        raise ValueError("exact bound execution freeze required")
    for name in ("runner", "python_binary", "timeout", "source_policy"):
        authenticate(freeze[name])
    config = strict_json(authenticate(freeze["config"], body=True))
    expected_code = {str(Path(freeze["runner"]["path"]).parent.parent / name): digest
                     for name, digest in config["code_sha256"].items()}
    if ({x["path"]: x["sha256"] for x in freeze["code"]} != expected_code
            or len(freeze["code"]) != 4):
        raise ValueError("exact helper/storage/reference code bindings required")
    for binding in freeze["code"]:
        authenticate(binding)
    if (config["schema_version"] != "raw-orphan-context-v1"
            or config["state"] != "BOUND_READY" or config["output"] != str(OUTPUT)
            or config["cache"] != freeze["cache"]
            or config["source_policy"] != freeze["source_policy"]
            or config["environment"] != freeze["environment"]):
        raise ValueError("bound registration association mismatch")
    if (config["budgets"]["new_retained_bytes"] != 1048576
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
    if not (args.worker or args.bootstrap):
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


def storage_for(freeze, *, phase):
    """Add stricter per-job caps without editing the shared storage helper.

    Charge attempted serialized allocations before the original writer. Counting
    repeated/deduplicated bodies conservatively also covers abandoned CAS writes.
    Each process reserves 32KiB for registry/owner writes; no new control route.
    """
    root = str(Path(freeze["runner"]["path"]).parent.parent)
    sys.path.insert(0, root)
    from nfl_lab.operational_storage import OperationalStorage
    original_write, original_control = OperationalStorage.write_bytes, OperationalStorage._atomic_plain
    if phase not in {"worker", "bootstrap", "supervisor"}:
        raise ValueError("unknown sequential storage phase")
    ceiling = LIMITS[f"{phase}_payload_bytes"]
    scope = OUTPUT if phase == "worker" else SUPERVISOR
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
    storage, charged = storage_for(freeze, phase="worker")
    # Bootstrap has already exited. Its immutable consumption receipt prevents
    # a direct/unregistered source phase and is checked before any source read.
    consumed_path = no_symlinks(SUPERVISOR / "JOB_CONSUMED.json")
    consumed_body = consumed_path.read_bytes()
    consumption = strict_json(consumed_body)
    from nfl_lab.owned_reference_batch import validate_owned_references
    validate_owned_references(storage, {str(consumed_path): hashlib.sha256(consumed_body).hexdigest(),
        str(SUPERVISOR / "execution-freeze.json"): args.freeze_sha256})
    if (consumption.get("freeze_sha256") != args.freeze_sha256
            or consumption.get("config_sha256") != freeze["config"]["sha256"]
            or consumption.get("source_queries") != 0 or consumption.get("phase") != "STORAGE_BOOTSTRAP"):
        raise ValueError("completed zero-source bootstrap required")
    from nfl_lab.raw_orphan_context import run_prerequisite
    try:
        result = run_prerequisite(freeze["config"]["path"], freeze["config"]["sha256"])
        preflight(args)  # Reauthenticate versions/binary/config/code before success.
        print(json.dumps({"state": result["state"], "HTTP": 0, "charged_allocations": charged,
                          "wall_seconds_before_exit": time.monotonic() - START,
                          "CPU_seconds_before_exit": time.process_time()}, allow_nan=False), flush=True)
        return 0
    except BaseException as error:
        # Do not print a source exception message that could contain a raw value.
        print(json.dumps({"state": "FAILED", "error_type": type(error).__name__,
                          "reason": "STRUCTURAL_PREREQUISITE_FAILED_NO_RETRY", "HTTP": 0,
                          "zeros_applied": 0}, allow_nan=False), flush=True)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def bootstrap(args):
    """Sequential storage-only child: no source helper or Parquet decode."""
    sys.addaudithook(deny_external_effects)
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, LIMITS["bootstrap_wall_seconds"] - (time.monotonic() - START)))
    resource.setrlimit(resource.RLIMIT_CPU, (22, 22))
    freeze, _ = preflight(args)
    storage, charged = storage_for(freeze, phase="bootstrap")
    with storage._locked():
        if OUTPUT.exists() or SUPERVISOR.exists():
            raise ValueError("invocation namespace consumed; no retries")
        storage.register_root(SUPERVISOR)
        storage.atomic_json(SUPERVISOR / "JOB_CONSUMED.json", {
            "schema_version": VERSION, "freeze_sha256": args.freeze_sha256,
            "config_sha256": freeze["config"]["sha256"], "started_utc": utc(),
            "invocations": 1, "HTTP": 0, "source_queries": 0, "primitive_columns_read": 0,
            "automatic_retries": 0, "phase": "STORAGE_BOOTSTRAP"})
        storage.write_bytes(SUPERVISOR / "execution-freeze.json", Path(args.freeze).read_bytes())
    preflight(args)
    print(json.dumps({"state": "STORAGE_BOOTSTRAP_COMPLETE", "source_queries": 0,
                      "HTTP": 0, "charged_allocations": charged}, allow_nan=False), flush=True)
    signal.setitimer(signal.ITIMER_REAL, 0)
    return 0


def process_stat(pid):
    raw = Path(f"/proc/{pid}/stat").read_text()
    closing = raw.rfind(")")
    if closing < 0 or int(raw[:raw.find("(")].strip()) != pid:
        raise RuntimeError("process identity unavailable")
    fields = raw[closing + 2:].split()
    if len(fields) < 20:
        raise RuntimeError("incomplete process accounting")
    return fields


def process_binding(pid):
    fields = process_stat(pid)
    return {"pid": pid, "start_ticks": int(fields[19])}


def process_usage(binding):
    """A required known PID is never omitted because discovery is unavailable."""
    pid = binding["pid"]
    before = process_stat(pid)
    if int(before[19]) != binding["start_ticks"]:
        raise RuntimeError("required process PID reused")
    status = Path(f"/proc/{pid}/status").read_text()
    entries = {}
    for line in status.splitlines():
        name, _, value = line.partition(":")
        if name in {"Pid", "VmRSS"}:
            if name in entries:
                raise RuntimeError("duplicate process accounting field")
            entries[name] = value.split()
    if (entries.get("Pid") != [str(pid)] or "VmRSS" not in entries
            or len(entries["VmRSS"]) != 2 or entries["VmRSS"][1] != "kB"):
        raise RuntimeError("required process RSS unavailable")
    after = process_stat(pid)
    if int(after[19]) != binding["start_ticks"]:
        raise RuntimeError("required process changed during RSS sample")
    rss = int(entries["VmRSS"][0]) * 1024
    if rss <= 0:
        raise RuntimeError("required live process RSS is not positive")
    cpu = (int(after[11]) + int(after[12])) / os.sysconf("SC_CLK_TCK")
    return rss, cpu


def required_usage(required, child=None, child_binding=None):
    """Explicit timeout+supervisor+worker samples; no best-effort tree walk.

    Python child process creation is denied. The reviewed helper does not create
    native subprocesses. A live required PID/RSS failing authentication stops
    the job instead of silently returning the timeout process alone.
    """
    rss, cpu = 0, 0.
    if len({x["pid"] for x in required}) != len(required):
        raise RuntimeError("duplicate required process binding")
    for binding in required:
        current_rss, current_cpu = process_usage(binding)
        rss, cpu = rss + current_rss, cpu + current_cpu
    if child is not None and child.poll() is None:
        try:
            if child_binding is None:
                raise RuntimeError("live worker binding unavailable")
            current_rss, current_cpu = process_usage(child_binding)
            rss, cpu = rss + current_rss, cpu + current_cpu
        except (FileNotFoundError, ProcessLookupError, RuntimeError):
            # A genuine exit race is allowed only after waitpid/poll confirms
            # this exact worker exited. Other visibility errors fail closed.
            if child.poll() is None:
                raise
    used = resource.getrusage(resource.RUSAGE_CHILDREN)
    return rss, cpu + used.ru_utime + used.ru_stime


def require_light_supervisor():
    if any(name in sys.modules for name in ("pandas", "numpy", "pyarrow", "nfl_lab.operational_storage")):
        raise RuntimeError("heavy supervisor import before child phase")


def run_phase(args, phase, required):
    """Children run sequentially; cumulative CPU/wall reserves span both phases."""
    require_light_supervisor()
    parent_pid = os.getpid()

    def orphan_guard():
        if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise OSError("PDEATHSIG unavailable")
        if os.getppid() != parent_pid:
            os.kill(os.getpid(), signal.SIGKILL)

    child, child_binding, stop, error = None, None, None, None
    peak, cpu_peak, max_pipes = 0, 0., LIMITS["pipe_bytes_per_stream_per_phase"]
    logs = {"stdout": bytearray(), "stderr": bytearray()}
    dropped = {"stdout": 0, "stderr": 0}
    selector = selectors.DefaultSelector()
    try:
        child = subprocess.Popen([sys.executable, "-B", __file__, "--freeze", str(args.freeze),
            "--freeze-sha256", args.freeze_sha256, f"--{phase}", "--supervisor-pid", str(parent_pid)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=os.environ.copy(), preexec_fn=orphan_guard)
        if child.poll() is None:
            try:
                child_binding = process_binding(child.pid)
            except (FileNotFoundError, ProcessLookupError):
                if child.poll() is None:
                    raise
        for stream, label in ((child.stdout, "stdout"), (child.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        while child.poll() is None or selector.get_map():
            rss, cpu = required_usage(required, child, child_binding)
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
    # Do not start the source phase after a bootstrap whose known highwater or
    # cumulative resource use already violates the shared whole-job contract.
    rss, cpu = required_usage(required)
    peak, cpu_peak = max(peak, rss), max(cpu_peak, cpu)
    if rss > LIMITS["RSS_stop_bytes"]:
        stop = stop or "COMBINED_RSS_SAFETY_MARGIN"
    elif cpu >= LIMITS["combined_CPU_stop_seconds"]:
        stop = stop or "COMBINED_CPU_FINALIZATION_RESERVE"
    elif time.monotonic() - START >= LIMITS["supervisor_worker_stop_seconds"]:
        stop = stop or "WORKER_WALL_FINALIZATION_RESERVE"
    if max(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
           resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024 > 268435456:
        stop = stop or "KNOWN_INDIVIDUAL_RSS_EXCEEDS_COMBINED_LIMIT"
    return {"phase": phase, "returncode": returncode, "stop_reason": stop, "error": error,
            "combined_RSS_peak_sampled_bytes": peak, "combined_CPU_peak_accounted_seconds": cpu_peak,
            "pipe_bytes_dropped": dropped, "logs": logs}


def supervisor(args):
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 59 - (time.monotonic() - START)))
    resource.setrlimit(resource.RLIMIT_CPU, (58, 58))
    freeze, _ = preflight(args)
    require_light_supervisor()
    required = [process_binding(os.getppid()), process_binding(os.getpid())]
    required_usage(required)
    if OUTPUT.exists() or SUPERVISOR.exists():
        raise ValueError("invocation namespace consumed; no retries")
    phases = [run_phase(args, "bootstrap", required)]
    if phases[0]["returncode"] == 0 and phases[0]["stop_reason"] is None and phases[0]["error"] is None:
        phases.append(run_phase(args, "worker", required))
    # Both children have been killed/reaped or exited before pandas/storage can
    # enter this process. The original storage module and footer remain intact.
    require_light_supervisor()
    peak = max(x["combined_RSS_peak_sampled_bytes"] for x in phases)
    cpu_peak = max(x["combined_CPU_peak_accounted_seconds"] for x in phases)
    stop = next((x["stop_reason"] for x in phases if x["stop_reason"] is not None), None)
    error = next((x["error"] for x in phases if x["error"] is not None), None)
    try:
        preflight(args)
    except BaseException as exc:
        error = {"type": type(exc).__name__, "reason": "EXIT_BINDING_CHECK_FAILED"}
    storage, charged = storage_for(freeze, phase="supervisor")
    if not SUPERVISOR.exists():
        # A failed bootstrap still consumes this distinct version's namespace.
        # No source phase is started after bootstrap failure.
        storage.register_root(SUPERVISOR)
        storage.atomic_json(SUPERVISOR / "BOOTSTRAP_FAILURE_CONSUMED.json", {
            "freeze_sha256": args.freeze_sha256, "source_phase_started": False,
            "automatic_retries": 0, "HTTP": 0})
    rss, cpu = required_usage(required)
    peak, cpu_peak = max(peak, rss), max(cpu_peak, cpu)
    elapsed = time.monotonic() - START
    child_used = resource.getrusage(resource.RUSAGE_CHILDREN)
    supervisor_used = resource.getrusage(resource.RUSAGE_SELF)
    if elapsed >= 59 or cpu >= 60 or peak > 268435456:
        stop = stop or "FINALIZATION_RESOURCE_LIMIT"
    if max(child_used.ru_maxrss, supervisor_used.ru_maxrss) * 1024 > 268435456:
        stop = stop or "KNOWN_INDIVIDUAL_RSS_EXCEEDS_COMBINED_LIMIT"
    success = len(phases) == 2 and all(x["returncode"] == 0 for x in phases) and stop is None and error is None
    for item in phases:
        for label, value in item.pop("logs").items():
            storage.write_bytes(SUPERVISOR / f"private/{item['phase']}/{label}.log", bytes(value))
    receipt = {"schema_version": VERSION, "state": "STRUCTURAL_QUARANTINE_ONLY" if success else "FAILED",
        "freeze_sha256": args.freeze_sha256, "config_sha256": freeze["config"]["sha256"],
        "phases": phases, "stop_reason": stop, "supervisor_error": error,
        "heavy_imports_sequential": True, "source_phase_started": len(phases) == 2,
        "HTTP": 0, "automatic_retries": 0, "zeros_applied": 0,
        "combined_RSS_peak_sampled_bytes": peak, "RSS_poll_seconds": .01,
        "sampled_processes": "explicit pinned timeout, supervisor, live worker; no discovery fallback",
        "RSS_stop_bytes": LIMITS["RSS_stop_bytes"],
        "RSS_limit_bytes": 268435456, "RSS_transient_peaks_may_be_missed": True,
        "maximum_individual_child_ru_maxrss_bytes": child_used.ru_maxrss * 1024,
        "supervisor_individual_ru_maxrss_bytes": supervisor_used.ru_maxrss * 1024,
        "combined_CPU_seconds_before_receipt_write": cpu,
        "wall_seconds_before_receipt_write": elapsed,
        "external_timeout_seconds": 60, "worker_orphan_guard": "Linux PDEATHSIG SIGKILL",
        "network_process_guard": "Python audit hooks; reviewed local helper, not a hostile-code sandbox",
        "supervisor_charged_allocations_before_receipt": dict(charged),
        "job_allocation_ceiling_bytes": 1048576, "numerical_threads": 1, "finished_utc": utc()}
    storage.atomic_json(SUPERVISOR / "JOB_FINISHED.json", receipt)
    rss, cpu = required_usage(required)
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    mode.add_argument("--bootstrap", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--supervisor-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    return worker(args) if args.worker else bootstrap(args) if args.bootstrap else supervisor(args)


if __name__ == "__main__":
    raise SystemExit(main())
