"""Fictional resource/orchestration guards; no NFL predictive observations."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from nfl_lab.cdf_campaign import check_seal, digest, directory_bytes, event, proc_usage, run, terminate_group


def test_private_event_append_retains_attempts(tmp_path):
    destination = tmp_path / "events.jsonl"
    event(destination, "ATTEMPT_STARTED", attempt=1)
    event(destination, "FAILED_CONSUMED", attempt=1)
    records = [json.loads(line) for line in destination.read_text().splitlines()]
    assert [x["event"] for x in records] == ["ATTEMPT_STARTED", "FAILED_CONSUMED"]


def test_output_bytes_includes_nested_models(tmp_path):
    (tmp_path / "a").write_bytes(b"123")
    (tmp_path / "model").mkdir()
    (tmp_path / "model/b").write_bytes(b"4567")
    assert directory_bytes(tmp_path) == 7


def test_unsealed_campaign_cannot_start(tmp_path):
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"state": "DRAFT"}))
    with pytest.raises(ValueError, match="reviewer seal"):
        run(registry, tmp_path / "outputs")
    assert not (tmp_path / "outputs").exists()


def test_process_group_rss_and_termination():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(15)"], start_new_session=True)
    try:
        rss, cpu = proc_usage(process.pid)
        assert rss >= 0 and cpu >= 0
        terminate_group(process)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()


def test_existing_output_never_restarted(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "old-evidence").write_text("retained")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"state": "SEALED_ROOT_AND_REVIEWER"}))
    with pytest.raises(FileExistsError):
        run(registry, output)
    assert (output / "old-evidence").read_text() == "retained"


def sealed_fixture(tmp_path):
    code = tmp_path / "fictional-engine.txt"
    code.write_text("fictional arithmetic v1")
    payload = {"code_bindings": [{"path": str(code), "sha256": digest(code)}], "prerequisite_bindings": []}
    plan = tmp_path / "fictional-review-plan.json"
    plan.write_text(json.dumps(dict(payload, state="AWAITING_REVIEW")))
    registry = tmp_path / "fictional-registry.json"
    registry.write_text(json.dumps(dict(payload, state="SEALED_ROOT_AND_REVIEWER", seal={
        "reviewer": "/root/campaign_reviewer", "integrator": "/root",
        "reviewed_plan_path": str(plan), "reviewed_plan_sha256": digest(plan)})))
    return registry, code


def test_seal_rejects_changed_code(tmp_path):
    registry, code = sealed_fixture(tmp_path)
    assert check_seal(registry)["state"] == "SEALED_ROOT_AND_REVIEWER"
    code.write_text("different bytes")
    with pytest.raises(ValueError, match="bytes changed"):
        check_seal(registry)


def test_seal_rejects_plan_drift(tmp_path):
    registry, _ = sealed_fixture(tmp_path)
    content = json.loads(registry.read_text())
    content["unreviewed_change"] = True
    registry.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="differs from reviewed"):
        check_seal(registry)


def test_all_blocked_cells_persist_before_aggregation(tmp_path, monkeypatch):
    import nfl_lab.cdf_campaign as campaign
    registry = {"state": "SEALED_ROOT_AND_REVIEWER", "categories": {"fantasy_ppr": {"state": "BLOCKED_LABEL_CONTRACT"}},
        "seasons": [2022, 2023, 2024], "budgets": {"campaign_wall_seconds": 30, "campaign_cpu_seconds": 30,
        "reporting_wall_reserve_seconds": 5, "maximum_candidate_fit_attempts": 6,
        "private_output_bytes": 1000000, "memory_bytes": 100000000}}
    source = tmp_path / "registry.json"
    source.write_text(json.dumps(registry))
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)

    class FictionalAggregation:
        returncode = 0

        def __init__(self, arguments, **kwargs):
            self.pid = 0
            output = Path(arguments[-1])
            statuses = json.loads((output / "attempts.json").read_text())
            assert len(statuses) == 6
            assert all(x["state"] == "BLOCKED_CATEGORY_CONTRACT" for x in statuses)
            (output / "campaign-report.json").write_text(json.dumps({"attempts": statuses}))

        def poll(self):
            return self.returncode

    monkeypatch.setattr(campaign.subprocess, "Popen", FictionalAggregation)
    output = tmp_path / "outputs"
    campaign.run(source, output)
    assert len(json.loads((output / "attempts.json").read_text())) == 6
