"""Finite supervisor for the separately registered cached-row arithmetic review.

No source or model is read here. Root must seal the exact finished packet and
authorize one invocation. RSS is sampled, with an explicit safety margin.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import runpy
import selectors
import signal
import stat
import subprocess
import sys
import time

START = time.monotonic()
VERSION = "direct-booster-screen-postrun-review-v2-20261023"
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OMP_THREAD_LIMIT")
OUTPUT = Path("/workspace/website-methods-research/resumed/direct-booster-postrun-review-v2-20261023")
LIMITS = dict(worker_payload_bytes=3932160, supervisor_payload_bytes=131072,
    control_bytes_per_process=65536, pipe_bytes_per_stream=8192,
    RSS_poll_seconds=.01, RSS_stop_bytes=1040187392, RSS_limit_bytes=1073741824,
    worker_wall_seconds=170, worker_stop_seconds=173, combined_CPU_stop_seconds=174,
    supervisor_wall_seconds=179, external_wall_seconds=180)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "absolute canonical path required")
    require(not any(part.is_symlink() for part in [path, *path.parents]), "symlink forbidden")
    return path


def authenticate(binding, *, body=False):
    path = safe(binding["path"])
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size == binding["bytes"], "exact regular binding required")
    require(not body or before.st_size <= 1048576, "freeze too large")
    checksum, chunks = hashlib.sha256(), []
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            checksum.update(chunk)
            if body:
                chunks.append(chunk)
    after = path.stat()
    fields = ["st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"]
    require(all(getattr(before, field) == getattr(after, field) for field in fields) and checksum.hexdigest() == binding["sha256"], "frozen bytes changed")
    return b"".join(chunks) if body else None


def load(args):
    path = safe(args.freeze)
    body = authenticate(dict(path=str(path), sha256=args.sha256, bytes=path.stat().st_size), body=True)
    packet = json.loads(body)
    require(packet["state"] == "SEALED_REVIEW_READY" and packet["seal"]["integrator"] == "/root", "root sealed packet required")
    require(packet["seal"]["reporting_continuation_complete"] is True, "completed continuation required")
    require(packet["limits"] == LIMITS and Path(packet["guard"]["path"]) == Path(__file__).absolute(), "guard/limits changed")
    require(Path(packet["supervisor_output"]) == OUTPUT and Path(packet["review_output"]) == OUTPUT / "audit", "reserved review namespace required")
    for key in ["guard", "review_script", "python_binary", "timeout"]:
        authenticate(packet[key])
    for binding in packet["bindings"]:
        authenticate(binding)
    policy = json.loads(Path(packet["policy_path"]).read_text())
    require(policy["registration_id"] == VERSION, "wrong review policy")
    require(policy["budgets"] == dict(invocations=1, wall_seconds=180, CPU_seconds=180, RSS_bytes=1073741824, numerical_threads=2, fits_inference_source_acquisition_HTTP=0), "registered review budgets changed")
    environment = packet["environment"]
    require(sys.version == environment["python"] and str(Path(sys.executable).resolve()) == packet["python_binary"]["path"], "Python changed")
    require(all(importlib.metadata.version(name) == version for name, version in environment["packages"].items()), "dependency version changed")
    require(sys.dont_write_bytecode and all(os.environ.get(name) == "2" for name in THREADS), "two-thread -B environment required")
    if args.worker:
        require(os.getppid() == args.supervisor_pid, "worker parent changed")
    else:
        parent = Path(f"/proc/{os.getppid()}")
        expected = [packet["timeout"]["path"], "--signal=KILL", "180s", environment["executable"], "-B", packet["guard"]["path"], "--freeze", str(args.freeze), "--sha256", args.sha256]
        require(Path(os.readlink(parent / "exe")) == Path(packet["timeout"]["path"]) and (parent / "cmdline").read_bytes().rstrip(b"\0").split(b"\0") == [text.encode() for text in expected], "exact timeout180 invocation required")
    return packet


def storage_for(packet, *, worker):
    sys.path.insert(0, packet["code_root"])
    from nfl_lab.operational_storage import OperationalStorage
    original_write, original_control = OperationalStorage.write_bytes, OperationalStorage._atomic_plain
    charged = dict(payload=0, control=0)
    cap = LIMITS["worker_payload_bytes" if worker else "supervisor_payload_bytes"]
    scope = OUTPUT / "audit" if worker else OUTPUT
    def write(self, path, body, *, replace=False):
        destination = safe(path)
        require(scope in destination.parents and not replace, "own fresh reviewer scope required")
        body = bytes(body)
        require(charged["payload"] + len(body) <= cap, "review payload cap")
        charged["payload"] += len(body)
        return original_write(self, destination, body, replace=False)
    def control(self, path, body, *, replace=True):
        require(charged["control"] + len(body) <= LIMITS["control_bytes_per_process"], "review controls cap")
        charged["control"] += len(body)
        return original_control(self, path, body, replace=replace)
    OperationalStorage.write_bytes, OperationalStorage._atomic_plain = write, control
    config = json.loads(Path(packet["config_path"]).read_text())
    storage = OperationalStorage(config["cache"], json.loads(Path(config["source_policy"]["path"]).read_text()))
    return storage, charged


def deadline(*_):
    raise TimeoutError("whole review finalization reserve reached")


def deny(event, args):
    if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn"}:
        raise RuntimeError("review worker forbids network and process creation")


def worker(args):
    sys.addaudithook(deny)
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 170 - (time.monotonic() - START)))
    resource.setrlimit(resource.RLIMIT_CPU, (174, 174))
    packet = load(args)
    _, charged = storage_for(packet, worker=True)
    sys.argv = [packet["review_script"]["path"], "--freeze", str(args.freeze), "--sha256", args.sha256]
    runpy.run_path(packet["review_script"]["path"], run_name="__main__")
    load(args)
    print(json.dumps(dict(worker_guard="COMPLETED", charged_allocations=charged)), flush=True)
    return 0


def process_stat(pid):
    raw = Path(f"/proc/{pid}/stat").read_text()
    closing = raw.rfind(")")
    require(closing >= 0 and int(raw[:raw.find("(")].strip()) == pid, "process identity unavailable")
    fields = raw[closing + 2:].split()
    require(len(fields) >= 20, "incomplete process accounting")
    return fields


def process_binding(pid):
    fields = process_stat(pid)
    return dict(pid=pid, start_ticks=int(fields[19]))


def process_usage(binding):
    pid = binding["pid"]
    before = process_stat(pid)
    require(int(before[19]) == binding["start_ticks"], "required process PID reused")
    entries = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        name, _, value = line.partition(":")
        if name in {"Pid", "VmRSS"}:
            require(name not in entries, "duplicate process accounting field")
            entries[name] = value.split()
    require(entries.get("Pid") == [str(pid)] and "VmRSS" in entries and len(entries["VmRSS"]) == 2 and entries["VmRSS"][1] == "kB", "required process RSS unavailable")
    after = process_stat(pid)
    require(int(after[19]) == binding["start_ticks"], "required process changed during sample")
    rss = int(entries["VmRSS"][0]) * 1024
    require(rss > 0, "required live process RSS is not positive")
    return rss, (int(after[11]) + int(after[12])) / os.sysconf("SC_CLK_TCK")


def required_usage(required, child=None, child_binding=None):
    """Explicit known PIDs; required live RSS can never default to zero.

    Worker child-process creation is denied. This reviewed arithmetic helper
    creates no native subprocesses. Reaping races may conservatively overcount
    CPU, but never omit a live worker because discovery did not enumerate it.
    """
    require(len({item["pid"] for item in required}) == len(required), "duplicate required process binding")
    rss, cpu = 0, 0.
    for binding in required:
        current_rss, current_cpu = process_usage(binding)
        rss, cpu = rss + current_rss, cpu + current_cpu
    if child is not None and child.poll() is None:
        try:
            require(child_binding is not None, "live worker binding unavailable")
            current_rss, current_cpu = process_usage(child_binding)
            rss, cpu = rss + current_rss, cpu + current_cpu
        except (FileNotFoundError, ProcessLookupError, RuntimeError, ValueError):
            if child.poll() is None:
                raise
    used = resource.getrusage(resource.RUSAGE_CHILDREN)
    return rss, cpu + used.ru_utime + used.ru_stime


def supervisor(args):
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 179 - (time.monotonic() - START)))
    resource.setrlimit(resource.RLIMIT_CPU, (178, 178))
    packet = load(args)
    required = [process_binding(os.getppid()), process_binding(os.getpid())]
    required_usage(required)
    storage, charged = storage_for(packet, worker=False)
    with storage._locked():
        require(not OUTPUT.exists(), "review namespace consumed; no retries")
        storage.register_root(OUTPUT)
        storage.atomic_json(OUTPUT / "JOB_CONSUMED.json", dict(registration_id=VERSION, freeze_sha256=args.sha256, invocations=1, HTTP=0))
    parent_pid = os.getpid()
    def orphan_guard():
        require(ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) == 0, "PDEATHSIG unavailable")
        if os.getppid() != parent_pid:
            os.kill(os.getpid(), signal.SIGKILL)
    child, child_binding, stop, error = None, None, None, None
    peak, cpu_peak = 0, 0.
    logs, dropped = {"stdout": bytearray(), "stderr": bytearray()}, {"stdout": 0, "stderr": 0}
    selector = selectors.DefaultSelector()
    try:
        child = subprocess.Popen([sys.executable, "-B", __file__, "--freeze", str(args.freeze), "--sha256", args.sha256, "--worker", "--supervisor-pid", str(parent_pid)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ.copy(), preexec_fn=orphan_guard)
        if child.poll() is None:
            try:
                child_binding = process_binding(child.pid)
            except (FileNotFoundError, ProcessLookupError):
                if child.poll() is None:
                    raise
        for stream, label in [(child.stdout, "stdout"), (child.stderr, "stderr")]:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        while child.poll() is None or selector.get_map():
            rss, cpu = required_usage(required, child, child_binding)
            peak, cpu_peak = max(peak, rss), max(cpu_peak, cpu)
            if rss > LIMITS["RSS_stop_bytes"]:
                stop = stop or "COMBINED_RSS_MARGIN"
            elif cpu >= LIMITS["combined_CPU_stop_seconds"]:
                stop = stop or "COMBINED_CPU_RESERVE"
            elif time.monotonic() - START >= LIMITS["worker_stop_seconds"]:
                stop = stop or "WALL_FINALIZATION_RESERVE"
            if stop and child.poll() is None:
                child.kill()
            for key, _ in selector.select(.01):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                kept = min(len(chunk), LIMITS["pipe_bytes_per_stream"] - len(logs[key.data]))
                logs[key.data].extend(chunk[:kept])
                dropped[key.data] += len(chunk) - kept
        child.wait(timeout=1)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, reason="REVIEW_SUPERVISOR_FAILURE_NO_RETRY")
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=1)
        selector.close()
        if child is not None:
            for stream in [child.stdout, child.stderr]:
                if stream is not None and not stream.closed:
                    stream.close()
    try:
        load(args)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, reason="REVIEW_EXIT_BINDING_CHECK_FAILED")
    rss, cpu = required_usage(required)
    peak, cpu_peak = max(peak, rss), max(cpu_peak, cpu)
    elapsed = time.monotonic() - START
    if elapsed >= 179 or cpu >= 180 or peak > LIMITS["RSS_limit_bytes"]:
        stop = stop or "REVIEW_FINALIZATION_RESOURCE_LIMIT"
    returncode = child.returncode if child is not None else None
    receipt_path = OUTPUT / "audit/review-receipt.json"
    accepted_receipt = False
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        accepted_receipt = receipt["state"] == "PASS_FROZEN_CACHED_ROW_ARITHMETIC_ONLY" and receipt["freeze_sha256"] == args.sha256
    child_highwater = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    supervisor_highwater = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if max(child_highwater, supervisor_highwater) > LIMITS["RSS_limit_bytes"]:
        stop = stop or "CHILD_RSS_HIGHWATER_LIMIT"
    success = returncode == 0 and stop is None and error is None and accepted_receipt
    for label, body in logs.items():
        storage.write_bytes(OUTPUT / f"private/{label}.log", bytes(body))
    result = dict(registration_id=VERSION, state="COMPLETED" if success else "FAILED", child_returncode=returncode,
        stop_reason=stop, supervisor_error=error, review_receipt_accepted=accepted_receipt, freeze_sha256=args.sha256,
        wall_seconds_before_receipt_write=elapsed, combined_CPU_seconds_before_receipt_write=cpu,
        sampled_combined_RSS_peak_bytes=peak, RSS_poll_seconds=.01, RSS_transient_peaks_may_be_missed=True,
        child_individual_ru_maxrss_bytes=child_highwater,
        supervisor_individual_ru_maxrss_bytes=supervisor_highwater,
        sampled_processes="explicit timeout, supervisor, live worker; authenticated PID/startticks/status Pid and positive VmRSS; no discovery fallback",
        original_failed_run_preserved=True, fits_inference_law_HTTP=0, numerical_threads=2,
        pipe_bytes_dropped=dropped, charged_allocations_before_receipt=dict(charged),
        total_attempted_allocation_cap_bytes=4194304)
    storage.atomic_json(OUTPUT / "JOB_FINISHED.json", result)
    rss, cpu = required_usage(required)
    elapsed = time.monotonic() - START
    print(json.dumps(dict(state=result["state"], receipt=str(OUTPUT / "JOB_FINISHED.json"), receipt_sha256=hashlib.sha256((OUTPUT / "JOB_FINISHED.json").read_bytes()).hexdigest(), wall_seconds_after_receipt_write=elapsed, combined_CPU_seconds_after_receipt_write=cpu, sampled_combined_RSS_peak_bytes=max(peak, rss))), flush=True)
    signal.setitimer(signal.ITIMER_REAL, 0)
    return 0 if success and elapsed < 180 and cpu < 180 and rss <= LIMITS["RSS_limit_bytes"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--supervisor-pid", type=int)
    args = parser.parse_args()
    return worker(args) if args.worker else supervisor(args)


if __name__ == "__main__":
    raise SystemExit(main())
