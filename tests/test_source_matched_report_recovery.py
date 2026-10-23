"""Fictional report-only fixtures; no NFL values, fitting or network."""
from contextlib import contextmanager
import importlib.metadata
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import joblib
import pandas as pd
import pytest

from nfl_lab import source_matched_report_recovery as recovery
from nfl_lab import source_matched_benchmark as base
from test_source_matched_benchmark import (categories, fixture_source, _fake_prediction,
    _fake_cdf_score, OrchestrationFixtureStorage)


def binding(path):
    return {"path": str(path.absolute()), "sha256": base.sha(path), "bytes": path.stat().st_size}


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, sort_keys=True, allow_nan=False))
    return path


@pytest.fixture
def packet(tmp_path, monkeypatch):
    root = tmp_path
    source = root / "features.parquet"; fixture_source(source)
    manifest = write(root / "source-manifest.json", {})
    policy = write(root / "source-policy.json", {})
    category = write(root / "categories.json", {"categories": categories()})
    parent, output = root / "parent", root / "recovery"
    parent.mkdir()
    parent_config = write(root / "parent-config.json", {"registration_id": base.VERSION,
        "methods": list(base.METHODS), "partitions": {"evaluation_years": list(base.YEARS)},
        "input_features": binding(source), "source_manifest": binding(manifest), "source_policy": binding(policy),
        "category_contract": binding(category), "cache": str(root / "cache"), "output": str(parent),
        "budgets": {"max_wall_seconds": 1200, "max_CPU_seconds": 1800, "max_RSS_bytes": 2*1024**3,
            "reporting_reserve_seconds": 180, "max_fit_attempts": 168, "max_reference_calls": 66,
            "max_query_prediction_or_law_row_incidences": 3_000_000}})
    slots, bindings = base.planned_slots(categories()), {}
    def remember(path):
        bindings[str(path.relative_to(parent))] = base.sha(path)
    def frame(relative, value):
        path = parent / relative; path.parent.mkdir(parents=True, exist_ok=True)
        value.to_parquet(path, index=False); remember(path)
        return relative
    for year in base.YEARS:
        query, _ = base.read_partition(source, year, "query")
        query_name = frame(f"private/queries/{year}.parquet", query)
        completed = {}
        for slot in [s for s in slots if s["year"] == year and s["kind"] != "blocked"]:
            target, method = slot["target"], slot["method"]
            c = base._category(categories(), target)
            relative = f"private/cells/{year}/{target}/{method}"
            model = SimpleNamespace(category=c, family="cdf" if method == "leaf_cdf" else "point")
            forecast = base.normalized(_fake_prediction(model, query), c, method)
            slot.update(state="PREDICTION_FROZEN", query=query_name, rows=len(query),
                forecast=frame(relative + "/forecast-frozen.parquet", forecast))
            if slot["kind"] == "model":
                path = parent / relative / "model.joblib"; joblib.dump(model, path); remember(path)
                slot["model"] = str(path.relative_to(parent))
            if method == "leaf_cdf":
                slot["prior_forecast"] = frame(relative + "/role-prior-frozen.parquet",
                    base.normalized(_fake_prediction(model, query, prior_only=True), c, "role_prior"))
            if slot["kind"] == "alias":
                slot["alias_of"] = completed[(target, slot["alias_method"])]["forecast"]
            completed[(target, method)] = slot
    while len(bindings) < 1407:
        remember(write(parent / f"fictional-provenance/{len(bindings):04d}.json", {"fictional": len(bindings)}))
    usage = {"wall_seconds": 797., "CPU_seconds": 846., "max_RSS_bytes": 600_000_000,
        "estimator_attempts": 168, "reference_calls": 66, "query_prediction_or_law_row_incidences": 1_733_424,
        "alias_copied_rows": 258720}
    freeze = write(parent / "forecast-freeze.json", {"state": "GLOBAL_FORECASTS_FROZEN", "fatal": None,
        "registration_sha256": base.sha(parent_config), "slots": slots, "bindings": bindings, "usage": usage})
    completion = write(parent / "completion.json", {"state": "FAILED", "returncode": -9, "limit_reason": "WALL_LIMIT",
        "wall_seconds": 1198., "CPU_seconds": 1269., "peak_combined_RSS_bytes": 760_000_000,
        "threads": 2, "new_HTTP_attempts_official_forecasts_confirmation": 0})
    packages = ("numpy", "pandas", "pyarrow", "pytest", "requests", "scikit-learn", "scipy", "threadpoolctl", "joblib")
    originals = [binding(write(root / f"original-code/{i}.json", {"original": i})) for i in range(82)]
    for item in originals:
        info = Path(item["path"]).stat()
        item.update(inode=[info.st_dev, info.st_ino], mode=oct(info.st_mode))
    execution = write(root / "parent-execution.json", {"plan_sha256": base.sha(parent_config),
        "actual_benchmark_invocations_fits_predictions_scoring_at_freeze": 0, "bindings": originals,
        "environment": {"executable": sys.executable, "python": sys.version, "threads": 2,
            "packages": {name: importlib.metadata.version(name) for name in packages}}})
    plan = write(root / "recovery-policy.json", {"parent_policy_sha256": base.sha(parent_config),
        "parent_freeze_sha256": base.sha(execution), "output": str(output)})
    clarification = write(root / "clarifications.json", {"parent_plan_sha256": base.sha(plan),
        "original_forecast_freeze_sha256": base.sha(freeze), "original_completion_sha256": base.sha(completion),
        "observed_parent": {"wall_seconds": 1198., "CPU_seconds": 1269., "peak_combined_RSS_bytes": 760_000_000,
            "query_or_law_rows": 1_733_424}})
    config = write(root / "execution.json", {"registration_id": recovery.VERSION, "policy": binding(plan),
        "clarifications": binding(clarification), "parent_config": binding(parent_config),
        "parent_execution_freeze": binding(execution), "parent_completion": binding(completion),
        "parent_forecast_freeze": binding(freeze), "output": str(output),
        "additional_bindings": [binding(Path(recovery.__file__)), binding(Path(recovery.owned_reference_batch.__file__))]})
    monkeypatch.setattr(recovery, "POLICY_SHA256", base.sha(plan))
    monkeypatch.setattr(recovery, "CLARIFICATIONS_SHA256", base.sha(clarification))
    monkeypatch.setattr(base, "OperationalStorage", OrchestrationFixtureStorage)
    monkeypatch.setattr(base.operational_sources, "load_source_policy", lambda path: {"_policy_sha256": base.sha(policy)})
    monkeypatch.setattr(base.cdf, "score_frozen_rows", _fake_cdf_score)
    events = []
    def batch(storage, files):
        assert len(files) == 1408
        for path, expected in files.items():
            if base.sha(path) != expected:
                raise base.StorageIntegrityError("fictional batch found changed original")
        events.append("batch")
        return {path: {"sha256": expected} for path, expected in files.items()}, {
            "fictional_storage_double": True, "validated_references": len(files), "full_scan_calls": 2}
    monkeypatch.setattr(recovery, "validate_owned_references", batch)
    original_read = base.read_partition
    def read(path, year, lane, **kwargs):
        assert lane == "labels" and kwargs == {"allow_labels": True}
        assert events[0] == "batch"
        assert (output / "REPAIR_SCORE_CONSUMED.json").exists()
        assert not (parent / "SCORE_CONSUMED.json").exists()
        events.append(year)
        return original_read(path, year, lane, **kwargs)
    monkeypatch.setattr(base, "read_partition", read)
    return SimpleNamespace(root=root, config=config, parent=parent, output=output, freeze=freeze,
        completion=completion, execution=execution, clarification=clarification, plan=plan, events=events)


def run(packet):
    return recovery.run_recovery(packet.config, config_sha256=base.sha(packet.config))


def repin(packet):
    """Freeze fictional changed metadata as a distinct test declaration."""
    clarification = json.loads(packet.clarification.read_text())
    clarification.update(original_forecast_freeze_sha256=base.sha(packet.freeze), original_completion_sha256=base.sha(packet.completion))
    write(packet.clarification, clarification)
    cfg = json.loads(packet.config.read_text())
    cfg.update(parent_forecast_freeze=binding(packet.freeze), parent_completion=binding(packet.completion),
        clarifications=binding(packet.clarification))
    write(packet.config, cfg)


def test_first_score_of_frozen_parent_then_target_local_real_reporting(packet, monkeypatch):
    from nfl_lab import source_matched_reporting as reporting
    old = {str(p): (base.sha(p), p.stat().st_ino, p.stat().st_mode) for p in packet.parent.rglob("*") if p.is_file()}
    original_builder = reporting.build_target_report
    targets = []
    def builder(*args, **kwargs):
        assert (packet.output / "scored-freeze.json").exists()
        targets.append(kwargs["target"])
        return original_builder(*args, **kwargs)
    monkeypatch.setattr(reporting, "build_target_report", builder)
    report = run(packet)
    assert set(report["targets"]) == set(base.models.TARGETS) and targets == list(base.models.TARGETS)
    assert packet.events == ["batch", 2022, 2023, 2024, "batch"]
    scored = json.loads((packet.output / "scored-freeze.json").read_text())
    assert sum(s["state"] == "COMPLETED" for s in scored["slots"]) == 198
    assert sum(s["state"] == "BLOCKED" for s in scored["slots"]) == 18
    assert scored["usage"]["query_prediction_or_law_row_incidences"] == 1_733_424 + 330
    assert scored["usage"]["estimator_attempts"] == 168 and scored["usage"]["reference_calls"] == 66
    envelope = json.loads((packet.output / "report.json").read_text())
    resources = envelope["resources"]
    assert resources["parent_failed"]["state"] == "FAILED"
    assert resources["sequential_total"]["wall_seconds"] > 1198
    assert resources["recovery_additional"]["wall_seconds"] < 600
    assert len(json.loads((packet.output / "private/paired-losses-manifest.json").read_text())["files"]) == 12
    assert old == {str(p): (base.sha(p), p.stat().st_ino, p.stat().st_mode) for p in packet.parent.rglob("*") if p.is_file()}
    with pytest.raises(RuntimeError, match="already consumed"):
        run(packet)
    assert packet.events.count(2022) == packet.events.count(2023) == packet.events.count(2024) == 1


@pytest.mark.parametrize("mutation", ["score-marker", "scored-file", "not-failed", "fatal", "slot", "counter", "changed-owned", "changed-code", "missing-binding"])
def test_ineligible_parent_fails_before_first_labels(packet, monkeypatch, mutation):
    freeze = json.loads(packet.freeze.read_text())
    if mutation == "score-marker":
        write(packet.parent / "SCORE_CONSUMED.json", {})
    elif mutation == "scored-file":
        write(packet.parent / "private/scored/fictional.json", {})
    elif mutation == "not-failed":
        c = json.loads(packet.completion.read_text()); c["state"] = "COMPLETED"; write(packet.completion, c)
    elif mutation == "fatal":
        freeze["fatal"] = "fictional failure"
    elif mutation == "slot":
        freeze["slots"][0]["state"] = "FAILED"
    elif mutation == "counter":
        freeze["usage"]["estimator_attempts"] = 167
    elif mutation == "changed-owned":
        (packet.parent / next(iter(freeze["bindings"]))).write_bytes(b"changed fictional bytes")
    elif mutation == "changed-code":
        original = json.loads(packet.execution.read_text())["bindings"][0]
        Path(original["path"]).write_text("changed fictional code")
    else:
        freeze["bindings"].pop(next(iter(freeze["bindings"])))
    if mutation not in {"changed-owned", "changed-code"}:
        write(packet.freeze, freeze)
    repin(packet)
    monkeypatch.setattr(recovery, "CLARIFICATIONS_SHA256", base.sha(packet.clarification))
    with pytest.raises((ValueError, base.StorageIntegrityError)):
        run(packet)
    assert not (packet.output / "REPAIR_SCORE_CONSUMED.json").exists()
    assert not any(isinstance(event, int) for event in packet.events)


def test_guard_and_cumulative_budget_forbid_new_work():
    with recovery.no_new_models_or_network():
        for call in (base.models.fit_predict, base.operational_models.fit_operational_reference,
                     base.operational_models.predict_operational_artifact, base.report_benchmark,
                     base.cdf.LeafCDFModel.fit, recovery.socket.getaddrinfo):
            with pytest.raises(AssertionError, match="forbids"):
                call()
    usage = {"estimator_attempts": 168, "reference_calls": 66,
        "query_prediction_or_law_row_incidences": 1_733_424, "alias_copied_rows": 258720}
    budget = recovery.RecoveryBudget(usage, started=recovery.time.monotonic(), cpu_started=recovery.time.process_time())
    assert budget.usage()["wall_seconds"] < 1
    with pytest.raises(AssertionError): budget.check(fit=True)
    with pytest.raises(AssertionError): budget.check(reference=True)
    with pytest.raises(base.BudgetExhausted): budget.check(rows=3_000_000-1_733_424+1)
    assert budget.rows == 1_733_424
    budget.start -= 601
    with pytest.raises(base.BudgetExhausted): budget.check()


def test_resource_failure_keeps_scoring_status_and_never_retries(packet, monkeypatch):
    def interrupted_score(session, freeze):
        session.scoring_slots = [dict(slot) for slot in freeze["slots"]]
        session.scoring_slots[0]["state"] = "SCORING_FAILED_RESOURCE"
        raise base.BudgetExhausted("fictional interrupted first score")
    monkeypatch.setattr(recovery, "_score", interrupted_score)
    with pytest.raises(base.BudgetExhausted, match="fictional"):
        run(packet)
    statuses = json.loads((packet.output / "scoring-attempts.json").read_text())["slots"]
    assert len(statuses) == 216 and statuses[0]["state"] == "SCORING_FAILED_RESOURCE"
    assert sum(slot["state"] == "BLOCKED" for slot in statuses) == 18
    assert (packet.output / "REPAIR_SCORE_CONSUMED.json").exists()
    assert not (packet.output / "scored-freeze.json").exists()
    with pytest.raises(RuntimeError, match="already consumed"):
        run(packet)
    assert not any(isinstance(event, int) for event in packet.events)
