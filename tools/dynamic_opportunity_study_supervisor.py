"""600s owned-child/resource guard for the single opportunity study.

The sampler and termination transition are the already accepted implementations.
Only their bounded observations are retained: every sample is checked, while
receipts retain peaks, counters, last32 observations and exact failure/exit
snapshots. A full high-frequency resource timeline is not claimed.
"""
from collections import deque
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import time

START = time.monotonic()
MARKER_FIELDS = {"active", "pid", "process_start_ticks", "process_cpu_start", "cpu_clock", "monotonic_start",
                 "attempt", "max_wall_seconds", "max_CPU_seconds", "generated_at"}


def package_guard(marker, *, pid, start_ticks, cpu_now, monotonic_now, previous):
    if not isinstance(marker, dict) or set(marker) != MARKER_FIELDS:
        return "MALFORMED_PACKAGE_GUARD", previous
    if (type(marker["active"]) is not bool or marker["pid"] != pid or marker["process_start_ticks"] != start_ticks
            or type(marker["attempt"]) is not int or not max(1, previous) <= marker["attempt"] <= 54
            or marker["max_wall_seconds"] != 20 or marker["max_CPU_seconds"] != 20
            or marker["cpu_clock"] != "proc_utime_plus_stime_over_CLK_TCK"
            or not isinstance(marker["generated_at"], str) or not marker["generated_at"]):
        return "PACKAGE_GUARD_IDENTITY_OR_LIMIT_CONFLICT", previous
    for name in ("process_cpu_start", "monotonic_start"):
        if type(marker[name]) not in (int, float) or not math.isfinite(marker[name]) or marker[name] < 0:
            return "PACKAGE_GUARD_CLOCK_INVALID", previous
    if marker["process_cpu_start"] > cpu_now + .03 or marker["monotonic_start"] > monotonic_now + .1:
        return "PACKAGE_GUARD_CLOCK_FUTURE", previous
    if marker["active"]:
        if monotonic_now - marker["monotonic_start"] >= 19:
            return "PER_PACKAGE_WALL_LIMIT", marker["attempt"]
        if cpu_now - marker["process_cpu_start"] >= 19:
            return "PER_PACKAGE_CPU_LIMIT", marker["attempt"]
    return None, marker["attempt"]


def module(binding, name):
    spec = importlib.util.spec_from_file_location(name, binding["path"])
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def main():
    from run_dynamic_opportunity_study import arguments, load, verify, extensions, THREADS
    from direct_booster_frozen_report_supervisor import external_guard
    args = arguments()
    def deny(event, values):
        if event.startswith("socket."):
            raise RuntimeError("dynamic supervisor forbids network")
    sys.addaudithook(deny)
    freeze = load(args.freeze, args.freeze_sha256)
    from nfl_lab.dynamic_opportunity_recovery import caps
    limits = caps(freeze["execution_metadata"])
    if freeze["execution_metadata"].get("recovery_envelope"):
        def cumulative_exhausted(signum, frame):
            raise RuntimeError("remaining recovery resource ceiling exhausted")
        signal.signal(signal.SIGALRM, cumulative_exhausted)
        signal.signal(signal.SIGPROF, cumulative_exhausted)
        signal.setitimer(signal.ITIMER_REAL, max(.001, limits["wall_seconds"] - (time.monotonic() - START)))
        signal.setitimer(signal.ITIMER_PROF, max(.001, limits["CPU_seconds"] - time.process_time()))
    spec = verify(freeze)
    if spec.get("recovery_envelope"):
        from nfl_lab.dynamic_opportunity_recovery import expected_external_argv
        parent = Path("/proc") / str(os.getppid())
        if (parent / "exe").resolve() != Path(freeze["external_timeout"]["path"]):
            raise ValueError("independent pinned recovery GNU timeout parent required")
        actual = [p.decode("utf-8") for p in (parent / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")]
        if actual != expected_external_argv(freeze, args):
            raise ValueError("recovery native timeout argv differs from exact remaining540s bound")
        stat = (parent / "stat").read_text().rsplit(")", 1)[1].split()
        parent_guard = dict(pid=os.getppid(), process_start_ticks=int(stat[19]),
            executable_sha256=freeze["external_timeout"]["sha256"], duration_seconds=limits["wall_seconds"])
    else:
        parent_guard = external_guard(freeze, args)
    import pyarrow as pa
    pa.set_cpu_count(2); pa.set_io_thread_count(2)
    from offline_report_imports_v1 import offline_dependency_imports
    with offline_dependency_imports():
        extensions(freeze)
    from nfl_lab.dynamic_opportunity_backend import make_storage
    from nfl_lab import termination_accounting as accounting
    guard = module(freeze["resource_guard"], "dynamic_accepted_resource_guard")
    sampler = module(freeze["resource_sampler"], "dynamic_accepted_resource_sampler")
    store, output = make_storage(spec)
    if (output / "dynamic-supervisor-consumed.json").exists():
        raise RuntimeError("sole dynamic invocation already consumed")
    store.atomic_json(output / "dynamic-supervisor-consumed.json", dict(invocations=1, at=time.time(),
        freeze_sha256=args.freeze_sha256, external_timeout_parent=parent_guard), replace=False)
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": freeze["code_root"]}
    for name in THREADS:
        env[name] = "2"
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    command = [freeze["environment"]["executable"], "-B", freeze["tools"]["run"]["path"],
               "--freeze", args.freeze, "--freeze-sha256", args.freeze_sha256, "--parent-pid", str(os.getpid())]
    process = subprocess.Popen(command, cwd=freeze["code_root"], env=env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    child = dict(pid=process.pid, start_ticks=int(sampler.process_stat(process.pid)[19]))
    own = dict(pid=os.getpid(), start_ticks=int(sampler.process_stat(os.getpid())[19]))
    timeout_parent = dict(pid=parent_guard["pid"], start_ticks=parent_guard["process_start_ticks"])
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    log = bytearray(); parse_buffer = bytearray(); ring = deque(maxlen=32)
    count = peak = peak_cpu = previous = 0
    reason = None; failure_snapshot = None; transfer = None; reaped_charge = None
    ready = None; released = False; marker_seen = False; child_cpu_lower = 0.
    startup = time.monotonic(); startup_samples = 0
    try:
        while process.poll() is None or selector.get_map():
            for key, _ in selector.select(timeout=.05):
                body = os.read(key.fileobj.fileno(), 65536)
                if body:
                    log.extend(body); parse_buffer.extend(body)
                    while b"\n" in parse_buffer:
                        line, _, rest = parse_buffer.partition(b"\n"); parse_buffer = bytearray(rest)
                        if line.startswith(b"DYNAMIC_READY "):
                            if ready is not None:
                                raise RuntimeError("duplicate worker READY")
                            ready = json.loads(line[len(b"DYNAMIC_READY "):])
                else:
                    selector.unregister(key.fileobj)
            supervisor_observation = guard.sample(sampler, own, stage="SUPERVISOR", allow_startup_zero=False)
            timeout_observation = guard.sample(sampler, timeout_parent, stage="EXTERNAL_TIMEOUT", allow_startup_zero=False)
            try:
                if transfer is None:
                    worker_observation = guard.sample(sampler, child, stage="RUNNING" if released else "STARTUP",
                                                     allow_startup_zero=not released, allow_exit=False)
                else:
                    worker_observation = None
            except guard.GuardFailure as error:
                if not released:
                    raise
                transfer = accounting.confirm_owned_child_exit(process, child, reason_code=error.code, snapshot=error.snapshot)
                worker_observation = None
            count += 1
            if not released:
                startup_samples += 1
            if worker_observation is not None:
                child_cpu_lower = max(child_cpu_lower, worker_observation["CPU_seconds"])
            rss = supervisor_observation["charged_RSS_bytes"] + timeout_observation["charged_RSS_bytes"]
            cpu = time.process_time() + child_cpu_lower + timeout_observation["CPU_seconds"]
            if worker_observation is not None:
                rss += worker_observation["charged_RSS_bytes"]
            peak = max(peak, rss); peak_cpu = max(peak_cpu, cpu)
            ring.append(dict(monotonic=time.monotonic(), combined_live_RSS_bytes=rss,
                cumulative_CPU_lower_bound=cpu, worker=worker_observation,
                worker_exit_transfer=transfer if worker_observation is None else None))
            if ready is not None and not released:
                expected = dict(state="DYNAMIC_WORKER_READY_NO_SCIENCE_IMPORTED", pid=child["pid"], start_ticks=child["start_ticks"],
                    parent_pid=os.getpid(), freeze_sha256=args.freeze_sha256, PDEATHSIG_armed=True)
                if ready != expected:
                    raise RuntimeError("worker READY identity conflict")
                if worker_observation is not None and worker_observation["charged_RSS_bytes"] > 0:
                    release = dict(state="GO", pid=child["pid"], start_ticks=child["start_ticks"], parent_pid=os.getpid(),
                                   freeze_sha256=args.freeze_sha256, positive_RSS_verified=True)
                    process.stdin.write((json.dumps(release, sort_keys=True) + "\n").encode()); process.stdin.flush()
                    released = True
                    # Small, source-free handover proof, durably inside same cap.
                    store.atomic_json(output / "dynamic-startup-barrier.json", dict(ready=ready, go=release,
                        verified_worker_observation=worker_observation, startup_samples=startup_samples), replace=False)
            if not released and time.monotonic() - startup >= 2:
                reason = "STARTUP_BARRIER_LIMIT"
            marker = output / "estimator-cpu-guard.json"
            if marker.exists() and worker_observation is not None:
                marker_seen = True
                marker_reason, previous = package_guard(json.loads(marker.read_text()), pid=process.pid, start_ticks=child["start_ticks"],
                    cpu_now=worker_observation["CPU_seconds"], monotonic_now=time.monotonic(), previous=previous)
                reason = reason or marker_reason
            elif marker_seen and not marker.exists():
                reason = reason or "PACKAGE_GUARD_DISAPPEARED"
            if time.monotonic() - START >= limits["wall_seconds"] - 5:
                reason = reason or "WALL_LIMIT"
            elif cpu >= limits["CPU_seconds"] - 5:
                reason = reason or "CPU_LIMIT"
            elif rss >= 1073741824 - 24 * 1024**2:
                reason = reason or "RSS_LIMIT"
            elif len(log) > 1048576:
                reason = reason or "LOG_LIMIT"
            elif os.statvfs(output).f_bavail == 0:
                reason = reason or "PHYSICAL_DISK_FULL"
            if reason:
                break
    except BaseException as error:
        reason = getattr(error, "code", "MONITOR_EXCEPTION_" + type(error).__name__)
        failure_snapshot = getattr(error, "snapshot", None)
    finally:
        selector.close()
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3); process.stdout.close(); process.stdin.close()
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    child_cpu = children.ru_utime + children.ru_stime
    try:
        if transfer is not None:
            reaped_charge = accounting.validate_reaped_accounting(transfer, child_CPU_seconds=child_cpu,
                                                                 child_highwater_bytes=children.ru_maxrss * 1024)
        elif child_cpu < child_cpu_lower or children.ru_maxrss <= 0:
            raise RuntimeError("post-reap accounting contradicts live observations")
    except BaseException as error:
        reason = reason or "POST_REAP_ACCOUNTING_" + type(error).__name__
    cpu = max(peak_cpu, time.process_time() + child_cpu)
    complete = process.returncode == 0 and reason is None and released and previous == 54 and (output / "report.json").exists()
    receipt = dict(state="COMPLETED" if complete else "FAILED", returncode=process.returncode, limit_reason=reason,
        wall_seconds=time.monotonic() - START, CPU_seconds=cpu, peak_sampled_combined_RSS_bytes=peak,
        child_ru_maxrss_bytes=children.ru_maxrss * 1024, worker_pid=child["pid"], worker_start_ticks=child["start_ticks"],
        supervisor_ru_maxrss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        checked_resource_samples=count, last_observed_package=previous, startup_released=released,
        all_samples_checked=True, retained_timeline="last32 only; peaks/counts/failure/exit snapshots; no full trace claim",
        last_samples=list(ring), monitor_failure_snapshot=failure_snapshot,
        termination_transfer=transfer, post_reap_charge=reaped_charge,
        RSS_scope="explicit known worker/supervisor/external timeout; sampled peaks can miss brief combined maxima; child ru_maxrss cross-check",
        threads=2, new_HTTP_model_loads_fits=0, retention=store.report_retention())
    store.write_bytes(output / "dynamic-supervisor.log", bytes(log[:1048576]), replace=False)
    receipt["wall_seconds"] = time.monotonic() - START
    receipt["CPU_seconds"] = max(cpu, time.process_time() + child_cpu)
    receipt["supervisor_ru_maxrss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if spec.get("recovery_envelope"):
        previous = spec["recovery_envelope"]["previous_consumption"]
        receipt["previous_campaign_consumption"] = previous
        receipt["campaign_wall_seconds"] = previous["wall_seconds"] + receipt["wall_seconds"]
        receipt["campaign_CPU_seconds"] = previous["CPU_seconds"] + receipt["CPU_seconds"]
        receipt["remaining_execution_limits"] = limits
        if receipt["campaign_wall_seconds"] >= 600 or receipt["campaign_CPU_seconds"] >= 600:
            receipt.update(state="FAILED", limit_reason=reason or "ORIGINAL_CAMPAIGN_RESOURCE_LIMIT")
    if (receipt["wall_seconds"] >= limits["wall_seconds"] or receipt["CPU_seconds"] >= limits["CPU_seconds"]
            or max(children.ru_maxrss * 1024, receipt["supervisor_ru_maxrss_bytes"]) >= 1073741824):
        receipt.update(state="FAILED", limit_reason=reason or "FINAL_RESOURCE_LIMIT")
    store.atomic_json(output / "dynamic-supervisor-completion.json", receipt, replace=False)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("last_samples", "monitor_failure_snapshot")}), flush=True)
    if receipt["state"] != "COMPLETED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
