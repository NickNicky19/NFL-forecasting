"""Isolated synthetic process fixtures; no NFL inputs, fits or remote calls."""
import json
from pathlib import Path
import subprocess
import sys

from tools.threshold_cdf_wave_supervisor import Limits, RECEIPT_RESERVE


# A fresh stdlib interpreter owns the monitor, worker and any fictional sentinel.
# Pytest's resource tracker, numerical threads and lifetime RSS remain in pytest.
MONITOR_HELPER = r'''
import ctypes
import json
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from tools.threshold_cdf_wave_supervisor import Limits, proc, supervise

request = json.load(sys.stdin)
limits = Limits(**request["limits"])
arguments = dict(cwd=request["cwd"], output=request["output"], limits=limits,
                 receipt=request["receipt"], metadata={"fictional_only": True,
                 "manifest_sha256": "fictional-binding"})
if request.get("preexisting_child"):
    sentinel = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    identity = proc(sentinel.pid)["start_ticks"]
    libc = ctypes.CDLL(None, use_errno=True)
    def subreaper():
        value = ctypes.c_int()
        assert libc.prctl(37, ctypes.byref(value), 0, 0, 0) == 0
        return value.value
    before_subreaper = subreaper()
    before_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    result = {"rejection": None}
    try:
        try:
            supervise(request["command"], **arguments)
        except RuntimeError as error:
            result.update(rejection=type(error).__name__, reason=str(error))
        result.update(sentinel_alive=sentinel.poll() is None,
                      sentinel_identity_unchanged=Path("/proc", str(sentinel.pid)).exists()
                      and proc(sentinel.pid)["start_ticks"] == identity,
                      receipt_exists=Path(request["receipt"]).exists(),
                      output_exists=Path(request["output"]).exists(),
                      subreaper_unchanged=subreaper() == before_subreaper,
                      handlers_unchanged=all(signal.getsignal(sig) == handler
                                             for sig, handler in before_handlers.items()))
    finally:
        if sentinel.poll() is None:
            sentinel.terminate()
        sentinel.wait(timeout=3)
elif request.get("preexisting_thread"):
    import threading
    release = threading.Event()
    peer = threading.Thread(target=release.wait)
    peer.start()
    result = {"rejection": None}
    try:
        try:
            supervise(request["command"], **arguments)
        except RuntimeError as error:
            result.update(rejection=type(error).__name__, reason=str(error))
        result.update(peer_alive=peer.is_alive(),
                      receipt_exists=Path(request["receipt"]).exists(),
                      output_exists=Path(request["output"]).exists())
    finally:
        release.set()
        peer.join(timeout=3)
else:
    proof = supervise(request["command"], **arguments)
    receipt = Path(request["receipt"])
    before = receipt.read_bytes()
    try:
        supervise([sys.executable, "-c", "raise RuntimeError('must not launch')"], **arguments)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing receipt was not rejected")
    assert receipt.read_bytes() == before
    result = {"proof": proof, "exclusive_receipt_preserved": True}
print(json.dumps(result))
'''


def run_monitor(tmp_path, source, limits, *, preexisting_child=False, preexisting_thread=False):
    script = tmp_path / "fictional_worker.py"
    script.write_text(source)
    output = tmp_path / "private-payload"
    receipt = tmp_path / "external-receipt.json"
    request = {"command": [sys.executable, str(script), str(output)],
               "cwd": str(tmp_path), "output": str(output), "receipt": str(receipt),
               "limits": vars(limits), "preexisting_child": preexisting_child,
               "preexisting_thread": preexisting_thread}
    helper = subprocess.run([sys.executable, "-c", MONITOR_HELPER,
                             str(Path(__file__).resolve().parents[1])],
                            input=json.dumps(request), text=True, capture_output=True,
                            timeout=12, check=True)
    assert not helper.stderr
    return json.loads(helper.stdout), output, receipt


def run_worker(tmp_path, source, limits):
    result, output, receipt = run_monitor(tmp_path, source, limits)
    proof = result["proof"]
    assert result["exclusive_receipt_preserved"]
    assert json.loads(receipt.read_text()) == proof
    assert receipt.stat().st_size <= RECEIPT_RESERVE
    assert proof["process_tree_clean"]
    assert any(item["pid"] == proof["worker_pid"] for item in proof["reaped"])
    assert not Path("/proc", str(proof["worker_pid"])).exists()
    assert proof["CPU_seconds"] >= proof["reaped_CPU_seconds"]
    return proof, output, receipt


def test_normal_exit_reaps_actual_usage_and_preserves_exclusive_receipt(tmp_path):
    limits = Limits(cpu=3., wall=4., rss=1024 * 1024**2, retained=1024**2, soft_reserve=.5, grace=.2)
    proof, output, receipt = run_worker(tmp_path,
        "from pathlib import Path\nimport sys\np=Path(sys.argv[1]);p.mkdir();(p/'completion.json').write_text('{}')\n", limits)
    assert proof["state"] == "COMPLETED"
    assert proof["reason"] is None and proof["worker_returncode"] == 0
    assert not proof["term_sent"] and not proof["kill_sent"]
    assert proof["worker_start_ticks"] > 0 and proof["supervisor_start_ticks"] > 0
    assert proof["peak_sampled_combined_RSS_bytes"] > 0
    assert proof["wait4_worker_peak_RSS_bytes"] > 0
    assert proof["conservative_combined_RSS_bound_bytes"] == proof["wait4_worker_peak_RSS_bytes"] + proof["monitor_peak_RSS_bytes"]
    assert proof["conservative_combined_RSS_bound_bytes"] <= limits.rss
    assert proof["payload_retained_bytes"] == 2
    assert proof["retained_bytes_with_receipt_reserve"] == 2 + RECEIPT_RESERVE


def test_preexisting_child_refusal_preserves_unrelated_owned_sentinel(tmp_path):
    limits = Limits(cpu=3., wall=4., rss=1024 * 1024**2, retained=1024**2, soft_reserve=.5, grace=.2)
    result, _, _ = run_monitor(tmp_path,
        "from pathlib import Path\nimport sys\nPath(sys.argv[1]).mkdir()\n", limits,
        preexisting_child=True)
    assert result["rejection"] == "RuntimeError"
    assert result["reason"] == "supervisor refuses preexisting direct children"
    assert result["sentinel_alive"] and result["sentinel_identity_unchanged"]
    assert not result["receipt_exists"] and not result["output_exists"]
    assert result["subreaper_unchanged"] and result["handlers_unchanged"]


def test_concurrent_thread_refusal_prevents_ambiguous_child_ownership(tmp_path):
    limits = Limits(cpu=3., wall=4., rss=1024 * 1024**2, retained=1024**2, soft_reserve=.5, grace=.2)
    result, _, _ = run_monitor(tmp_path,
        "from pathlib import Path\nimport sys\nPath(sys.argv[1]).mkdir()\n", limits,
        preexisting_thread=True)
    assert result["rejection"] == "RuntimeError"
    assert result["reason"] == "supervisor requires a single-threaded isolated monitor"
    assert result["peer_alive"]
    assert not result["receipt_exists"] and not result["output_exists"]


def test_cpu_cap_sends_term_and_retains_worker_failure_before_hard_limit(tmp_path):
    limits = Limits(cpu=.65, wall=3., rss=1024 * 1024**2, retained=1024**2, soft_reserve=.25, grace=.3)
    proof, output, _ = run_worker(tmp_path,
        "import signal,sys\nfrom pathlib import Path\np=Path(sys.argv[1]);p.mkdir()\n"
        "def stop(*_):\n (p/'terminal-failure.json').write_text('{\"state\":\"synthetic failure retained\"}');sys.exit(23)\n"
        "signal.signal(signal.SIGTERM,stop)\nwhile True: pass\n", limits)
    assert proof["state"] == "FAILED"
    assert proof["reason"] == "CPU_SOFT_LIMIT"
    assert proof["term_sent"] and not proof["kill_sent"]
    assert proof["worker_returncode"] == 23
    assert proof["CPU_seconds"] < limits.cpu
    assert proof["wall_seconds"] < limits.wall
    assert (output / "terminal-failure.json").is_file()


def test_forbidden_process_descendant_is_detected_killed_and_reaped(tmp_path):
    limits = Limits(cpu=3., wall=4., rss=1024 * 1024**2, retained=1024**2, soft_reserve=.5, grace=.2)
    proof, _, _ = run_worker(tmp_path,
        "import os,sys,time\nfrom pathlib import Path\nPath(sys.argv[1]).mkdir()\n"
        "if os.fork(): sys.exit(0)\nos.setsid()\ntime.sleep(3)\n", limits)
    assert proof["state"] == "FAILED"
    assert proof["reason"] == "UNEXPECTED_DESCENDANT"
    assert proof["term_sent"]
    assert len(proof["observed_descendants"]) == 1
    assert len(proof["reaped"]) == 2
    descendant = proof["observed_descendants"][0]
    assert not Path("/proc", str(descendant["pid"])).exists()
