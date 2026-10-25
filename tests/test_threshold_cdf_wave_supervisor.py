"""Three synthetic process fixtures; no NFL inputs, fits or remote calls."""
import json
from pathlib import Path
import sys

import pytest

from tools.threshold_cdf_wave_supervisor import Limits, RECEIPT_RESERVE, supervise


def run_worker(tmp_path, source, limits):
    script = tmp_path / "fictional_worker.py"
    script.write_text(source)
    output = tmp_path / "private-payload"
    receipt = tmp_path / "external-receipt.json"
    proof = supervise([sys.executable, str(script), str(output)], cwd=tmp_path,
                      output=output, limits=limits, receipt=receipt,
                      metadata={"fictional_only": True, "manifest_sha256": "fictional-binding"})
    assert json.loads(receipt.read_text()) == proof
    assert receipt.stat().st_size <= RECEIPT_RESERVE
    assert proof["process_tree_clean"]
    assert any(item["pid"] == proof["worker_pid"] for item in proof["reaped"])
    assert not Path("/proc", str(proof["worker_pid"])).exists()
    assert proof["CPU_seconds"] >= proof["reaped_CPU_seconds"]
    return proof, output, receipt


def test_normal_exit_reaps_actual_usage_and_preserves_exclusive_receipt(tmp_path):
    # The test host may have already imported the numerical research suite.
    # Its measured high water counts; production remains fixed at 4 GiB.
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
    before = receipt.read_bytes()
    with pytest.raises(FileExistsError):
        supervise([sys.executable, "-c", "raise RuntimeError('must not launch')"], cwd=tmp_path,
                  output=output, limits=limits, receipt=receipt)
    assert receipt.read_bytes() == before


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
