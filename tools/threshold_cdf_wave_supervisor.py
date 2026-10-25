"""One bounded, offline threshold-CDF worker and an exclusive durable receipt.

Production CLI has no synthetic-mode or resource override. Source and input
hashes are verified before launching the exact manifest-bound interpreter and
runner. CPU includes this monitor, the worker and observed descendants. RSS is
sampled simultaneously; wait4 rusage cross-checks peaks missed between polls.
Only Linux process directories are enumerated, so native threads are allowed.
"""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

VERSION = "threshold-cdf-wave-supervisor-v2-20261025"
START_WALL = time.monotonic()
RECEIPT_RESERVE = 65536
PAYLOAD_TERMINAL_RESERVE = 262144
INTERPRETER = "/workspace/nfl-direct-boosters-venv/bin/python"
REGISTRATION_ID = "distribution-cdf-after-audit-v2-20261025"
TICKS = os.sysconf("SC_CLK_TCK")
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def binding(value, *, interpreter=False):
    path = Path(value["path"])
    if not path.is_absolute() or not path.is_file():
        raise ValueError("binding must be an absolute regular file")
    if interpreter:
        if str(path) != INTERPRETER or value.get("resolved_path") != str(path.resolve()):
            raise ValueError("unqualified interpreter resolution")
    elif path.is_symlink():
        raise ValueError("symlink binding forbidden")
    if sha(path) != value["sha256"]:
        raise ValueError("binding SHA256 mismatch")
    return path


@dataclass(frozen=True)
class Limits:
    cpu: float = 1200.
    wall: float = 1500.
    rss: int = 4294967296
    retained: int = 201326592
    soft_reserve: float = 50.
    grace: float = 5.
    poll: float = .05
    address_space: int = 8589934592


def verify(manifest_path, supplied_sha):
    path = Path(manifest_path)
    if path.is_symlink() or not path.is_file() or sha(path) != supplied_sha:
        raise ValueError("execution manifest SHA256 mismatch")
    manifest = json.loads(path.read_text())
    registration = json.loads(binding(manifest["registration"]).read_text())
    if registration["registration_id"] != REGISTRATION_ID:
        raise ValueError("wrong registration")
    expected = {"maximum_CPU_seconds": 1200, "maximum_wall_seconds": 1500,
                "finalization_reserve_seconds": 45, "maximum_RSS_bytes": 4294967296,
                "maximum_address_space_bytes": 8589934592, "threads": 2,
                "maximum_new_retained_bytes": 201326592, "HTTP": 0, "GPU": 0}
    if any(registration["resources"].get(key) != value for key, value in expected.items()):
        raise ValueError("changed prespecified resource limits")
    for group in (manifest["inputs"], manifest["code"]):
        for value in group.values():
            binding(value)
    worker = manifest["worker"]
    interpreter = binding(worker["interpreter"], interpreter=True)
    script = binding(worker["script"])
    cwd = Path(worker["cwd"])
    if not cwd.is_absolute() or not cwd.is_dir() or cwd.resolve() != cwd:
        raise ValueError("worker cwd must be an explicit resolved directory")
    if script != cwd / "tools" / "run_threshold_cdf_after_audit.py":
        raise ValueError("unexpected worker script")
    code_paths = {str(Path(value["path"])) for value in manifest["code"].values()}
    if str(script) not in code_paths or str(Path(__file__).resolve()) not in code_paths:
        raise ValueError("worker and supervisor sources must both be frozen")
    output = Path(manifest["output"])
    if not output.is_absolute() or output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("worker requires a new absolute output directory")
    resources = registration["resources"]
    limits = Limits(cpu=resources["maximum_CPU_seconds"], wall=resources["maximum_wall_seconds"],
                    rss=resources["maximum_RSS_bytes"], retained=resources["maximum_new_retained_bytes"],
                    address_space=resources["maximum_address_space_bytes"])
    return manifest, [str(interpreter), str(script), str(path.resolve()), supplied_sha], cwd, output, limits


def proc(pid):
    values = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "state": values[0], "ppid": int(values[1]), "pgrp": int(values[2]),
            "start_ticks": int(values[19]), "rss": int(values[21]) * PAGE_SIZE,
            "cpu": sum(int(values[i]) for i in (11, 12, 13, 14)) / TICKS}


def require_isolated_monitor():
    """Refuse shared process ownership before creating or changing anything."""
    if len(list(Path("/proc/self/task").iterdir())) != 1:
        raise RuntimeError("supervisor requires a single-threaded isolated monitor")
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            child = proc(int(directory.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        if child["ppid"] == os.getpid():
            raise RuntimeError("supervisor refuses preexisting direct children")


def snapshot(worker_pid, worker_start, known):
    """Read the known worker explicitly, then its process tree and group."""
    entries = {}
    try:
        worker = proc(worker_pid)
        if worker["start_ticks"] != worker_start:
            raise RuntimeError("known worker PID identity changed")
        entries[worker_pid] = worker
    except FileNotFoundError:
        worker = None
    all_entries = {}
    for directory in Path("/proc").iterdir():
        if directory.name.isdigit() and int(directory.name) != worker_pid:
            try:
                item = proc(int(directory.name))
                all_entries[item["pid"]] = item
            except (FileNotFoundError, ProcessLookupError):
                continue
    selected = {worker_pid}
    while True:
        added = {pid for pid, item in all_entries.items()
                 if item["ppid"] in selected or item["pgrp"] == worker_pid or item["ppid"] == os.getpid()
                 or known.get(pid) == item["start_ticks"]}
        if added <= selected:
            break
        selected.update(added)
    entries.update({pid: all_entries[pid] for pid in selected if pid in all_entries})
    known.update({pid: item["start_ticks"] for pid, item in entries.items()})
    return entries


def signal_owned(worker_pid, known, signum):
    entries = []
    for pid, start_ticks in known.items():
        try:
            item = proc(pid)
            if item["start_ticks"] == start_ticks and item["state"] != "Z":
                entries.append(item)
        except (FileNotFoundError, ProcessLookupError):
            continue
    if any(item["pgrp"] == worker_pid for item in entries):
        try:
            os.killpg(worker_pid, signum)
        except ProcessLookupError:
            pass
    for item in entries:
        if item["pgrp"] != worker_pid:
            try:
                os.kill(item["pid"], signum)
            except ProcessLookupError:
                pass


def retained_bytes(output):
    total = 0
    if output.exists():
        for parent, dirs, files in os.walk(output, followlinks=False):
            for name in dirs + files:
                path = Path(parent, name)
                if path.is_symlink():
                    raise RuntimeError("payload symlink forbidden")
            total += sum(Path(parent, name).stat().st_size for name in files)
    return total


def _linux_child_setup(parent, limits):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent:
        os._exit(125)
    resource.setrlimit(resource.RLIMIT_AS, (limits.address_space, limits.address_space))
    # The monitor charges combined CPU; this per-worker ceiling is a backstop.
    resource.setrlimit(resource.RLIMIT_CPU, (math.ceil(limits.cpu), math.ceil(limits.cpu) + 1))


def _open_receipt(path):
    path = Path(path)
    if not path.is_absolute() or not path.parent.is_dir() or path.parent.resolve() != path.parent:
        raise ValueError("receipt requires an existing resolved absolute parent")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.fsync(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return descriptor


def write_receipt(descriptor, receipt):
    body = (json.dumps(receipt, indent=2, allow_nan=False) + "\n").encode()
    if len(body) > RECEIPT_RESERVE:
        raise RuntimeError("supervisor receipt exceeds reserved 64 KiB")
    view = memoryview(body)
    while view:
        view = view[os.write(descriptor, view):]
    os.fsync(descriptor)
    return len(body)


def supervise(command, *, cwd, output, limits, receipt, metadata=None, start=None, cpu_origin=None):
    """Bounded stdlib core; small limits are used only by fictional unit tests."""
    # Adopted children can be attributed to the worker only in a fresh monitor.
    # A shared parent may already own a resource tracker or another actor's job.
    require_isolated_monitor()
    start = time.monotonic() if start is None else start
    cpu_origin = time.process_time() if cpu_origin is None else cpu_origin
    output, receipt = Path(output), Path(receipt)
    if receipt == output or output in receipt.parents:
        raise ValueError("supervisor receipt must be external to private payload")
    descriptor = _open_receipt(receipt)
    proof = dict(metadata or {})
    proof.update(version=VERSION, supervisor_pid=os.getpid(), supervisor_start_ticks=proc(os.getpid())["start_ticks"],
                 state="FAILED", reason=None, worker_pid=None, worker_start_ticks=None,
                 resource_limits=vars(limits), receipt_reserve_bytes=RECEIPT_RESERVE,
                 payload_terminal_reserve_bytes=PAYLOAD_TERMINAL_RESERVE,
                 sample_poll_seconds=limits.poll, worker_returncode=None, observed_descendants=[],
                 term_sent=False, kill_sent=False, reaped=[], process_tree_clean=False)
    worker = None
    known = {}
    peaks = {"rss": 0, "cpu": 0.}
    reaped_cpu = 0.
    worker_rusage = None
    term_at = None
    external_signal = []
    previous_subreaper = ctypes.c_int()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(37, ctypes.byref(previous_subreaper), 0, 0, 0) != 0:
        os.close(descriptor)
        raise RuntimeError("cannot inspect child subreaper")
    old_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    for sig in old_handlers:
        signal.signal(sig, lambda number, _frame: external_signal.append(number))
    try:
        # Become a subreaper so forbidden grandchildren cannot be left as zombies.
        if libc.prctl(36, 1, 0, 0, 0) != 0:
            raise RuntimeError("cannot install child subreaper")
        environment = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(cwd)}
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "OMP_THREAD_LIMIT", "ARROW_IO_THREADS"):
            environment[name] = "2"
        if "LD_LIBRARY_PATH" in os.environ:
            environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        parent = os.getpid()
        worker = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                                  preexec_fn=lambda: _linux_child_setup(parent, limits))
        initial = proc(worker.pid)
        proof.update(worker_pid=worker.pid, worker_start_ticks=initial["start_ticks"])
        known[worker.pid] = initial["start_ticks"]
        while True:
            entries = snapshot(worker.pid, initial["start_ticks"], known)
            descendants = {pid: item for pid, item in entries.items() if pid != worker.pid}
            seen = {item["pid"] for item in proof["observed_descendants"]}
            proof["observed_descendants"].extend({"pid": pid, "start_ticks": item["start_ticks"]}
                                                 for pid, item in descendants.items() if pid not in seen)
            own = proc(os.getpid())
            rss = own["rss"] + sum(item["rss"] for item in entries.values())
            cpu = time.process_time() - cpu_origin + max(reaped_cpu, sum(item["cpu"] for item in entries.values()))
            wall = time.monotonic() - start
            peaks["rss"], peaks["cpu"] = max(peaks["rss"], rss), max(peaks["cpu"], cpu)
            payload_size = retained_bytes(output)
            if proof["reason"] is None:
                if external_signal:
                    proof["reason"] = "SUPERVISOR_SIGNAL"
                elif descendants:
                    proof["reason"] = "UNEXPECTED_DESCENDANT"
                elif rss > limits.rss:
                    proof["reason"] = "RSS_LIMIT"
                elif rss >= limits.rss - min(64 * 1024**2, limits.rss // 16):
                    proof["reason"] = "RSS_SOFT_LIMIT"
                elif payload_size > limits.retained - RECEIPT_RESERVE:
                    proof["reason"] = "RETAINED_BYTE_LIMIT"
                elif cpu >= limits.cpu - limits.soft_reserve:
                    proof["reason"] = "CPU_SOFT_LIMIT"
                elif wall >= limits.wall - limits.soft_reserve:
                    proof["reason"] = "WALL_SOFT_LIMIT"
            hard = cpu >= limits.cpu or wall >= limits.wall or rss > limits.rss
            if proof["reason"] and term_at is None:
                signal_owned(worker.pid, known, signal.SIGTERM)
                term_at = time.monotonic()
                proof.update(term_sent=True, term_at_CPU_seconds=cpu, term_at_wall_seconds=wall)
            if hard or (term_at is not None and time.monotonic() - term_at >= limits.grace):
                signal_owned(worker.pid, known, signal.SIGKILL)
                proof["kill_sent"] = True
                if hard:
                    proof["hard_limit_reason"] = "RSS_LIMIT" if rss > limits.rss else "CPU_LIMIT" if cpu >= limits.cpu else "WALL_LIMIT"
            # Reap only owned processes, retaining their actual wait4 rusage.
            for pid in list(known):
                if any(item["pid"] == pid for item in proof["reaped"]):
                    continue
                try:
                    waited, status, usage = os.wait4(pid, os.WNOHANG)
                except ChildProcessError:
                    continue  # A live grandchild is not adoptable until its parent exits.
                if waited:
                    reaped_cpu += usage.ru_utime + usage.ru_stime
                    proof["reaped"].append({"pid": pid, "returncode": os.waitstatus_to_exitcode(status),
                                           "CPU_seconds": usage.ru_utime + usage.ru_stime,
                                           "ru_maxrss_bytes": usage.ru_maxrss * 1024})
                    if pid == worker.pid:
                        worker.returncode = os.waitstatus_to_exitcode(status)
                        worker_rusage = usage
                        proof["worker_returncode"] = worker.returncode
            live = {pid: item for pid, item in entries.items() if item["state"] != "Z"}
            if worker.returncode is not None and not live:
                # A fresh pass discovers any just-adopted child before declaring clean.
                remaining = snapshot(worker.pid, initial["start_ticks"], known)
                if not remaining:
                    proof["process_tree_clean"] = True
                    break
            time.sleep(limits.poll)
    except BaseException as error:
        proof["reason"] = proof["reason"] or "SUPERVISOR_EXCEPTION_" + type(error).__name__
    finally:
        if worker is not None and not proof["process_tree_clean"]:
            if worker.pid not in known:
                # The still-unreaped direct child cannot have a reused PID.
                try:
                    os.killpg(worker.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                waited, status, usage = os.wait4(worker.pid, 0)
                worker.returncode = os.waitstatus_to_exitcode(status)
                worker_rusage = usage
                reaped_cpu += usage.ru_utime + usage.ru_stime
                proof["worker_returncode"] = worker.returncode
                proof["reaped"].append({"pid": waited, "returncode": worker.returncode,
                                       "CPU_seconds": usage.ru_utime + usage.ru_stime,
                                       "ru_maxrss_bytes": usage.ru_maxrss * 1024})
            signal_owned(worker.pid, known, signal.SIGKILL)
            proof["kill_sent"] = True
            for pid in list(known):
                if any(item["pid"] == pid for item in proof["reaped"]):
                    continue
                try:
                    waited, status, usage = os.wait4(pid, 0)
                except ChildProcessError:
                    continue
                reaped_cpu += usage.ru_utime + usage.ru_stime
                proof["reaped"].append({"pid": waited, "returncode": os.waitstatus_to_exitcode(status),
                                       "CPU_seconds": usage.ru_utime + usage.ru_stime, "ru_maxrss_bytes": usage.ru_maxrss * 1024})
                if waited == worker.pid:
                    worker.returncode = os.waitstatus_to_exitcode(status)
                    worker_rusage = usage
                    proof["worker_returncode"] = worker.returncode
            proof["process_tree_clean"] = not snapshot(worker.pid, proof["worker_start_ticks"], known)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        libc.prctl(36, previous_subreaper.value, 0, 0, 0)
        cpu = max(peaks["cpu"], reaped_cpu + time.process_time() - cpu_origin)
        wall = time.monotonic() - start
        try:
            payload_size = retained_bytes(output)
        except OSError:
            payload_size = None
            proof["reason"] = proof["reason"] or "FINAL_RETENTION_INSPECTION_FAILURE"
        except RuntimeError:
            payload_size = None
            proof["reason"] = proof["reason"] or "INVALID_PAYLOAD_ENTRY"
        child_peak = 0 if worker_rusage is None else worker_rusage.ru_maxrss * 1024
        monitor_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        conservative_rss_bound = monitor_peak + child_peak
        if proof["reason"] is None and (cpu >= limits.cpu or wall >= limits.wall or conservative_rss_bound > limits.rss):
            proof["reason"] = "FINAL_RESOURCE_LIMIT"
        if proof["reason"] is None and payload_size is not None and payload_size > limits.retained - RECEIPT_RESERVE:
            proof["reason"] = "FINAL_RETAINED_BYTE_LIMIT"
        if proof["reason"] is None and proof["worker_returncode"] == 0 and proof["process_tree_clean"]:
            proof["state"] = "COMPLETED"
        elif proof["reason"] is None:
            proof["reason"] = "WORKER_EXIT_FAILURE"
        proof.update(CPU_seconds=cpu, wall_seconds=wall, peak_sampled_combined_RSS_bytes=peaks["rss"],
                     wait4_worker_peak_RSS_bytes=child_peak, reaped_CPU_seconds=reaped_cpu,
                     monitor_peak_RSS_bytes=monitor_peak, conservative_combined_RSS_bound_bytes=conservative_rss_bound,
                     RSS_soft_reserve_bytes=min(64 * 1024**2, limits.rss // 16),
                     payload_retained_bytes=payload_size,
                     retained_bytes_with_receipt_reserve=None if payload_size is None else payload_size + RECEIPT_RESERVE,
                     CPU_scope="monitor plus worker and observed descendants; max(sampled, wait4 reaped)",
                     RSS_scope="sampled simultaneous monitor and process tree; conservative monitor-HWM plus worker wait4-HWM acceptance bound; peaks need not coincide",
                     resource_measurement_boundary="immediately before receipt serialization and fsync",
                     worker_parent_death_signal="SIGKILL with parent PID race check", network_calls_by_supervisor=0)
        try:
            write_receipt(descriptor, proof)
        finally:
            os.close(descriptor)
    return proof


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("sha256")
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    def offline(event, _values):
        if event.startswith("socket."):
            raise RuntimeError("supervisor network forbidden")
    sys.addaudithook(offline)
    try:
        manifest, command, cwd, output, limits = verify(args.manifest, args.sha256)
    except BaseException as error:
        descriptor = _open_receipt(Path(args.receipt))
        try:
            write_receipt(descriptor, {"version": VERSION, "state": "REJECTED_BEFORE_LAUNCH",
                                      "reason": type(error).__name__, "manifest_sha256": args.sha256,
                                      "supervisor_sha256": sha(__file__), "worker_pid": None,
                                      "CPU_seconds": time.process_time(), "wall_seconds": time.monotonic() - START_WALL})
        finally:
            os.close(descriptor)
        raise SystemExit(1)
    proof = supervise(command, cwd=cwd, output=output, limits=limits, receipt=args.receipt,
                      metadata={"manifest_sha256": args.sha256, "registration": manifest["registration"],
                                "source_bindings": manifest["code"], "worker_binding": manifest["worker"]},
                      start=START_WALL, cpu_origin=0.)
    raise SystemExit(0 if proof["state"] == "COMPLETED" else 1)


if __name__ == "__main__":
    main()
