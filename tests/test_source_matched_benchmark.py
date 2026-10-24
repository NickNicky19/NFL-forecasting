"""Fictional orchestration fixtures; optimizer/parameter fits are inert stubs."""
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nfl_lab import source_matched_benchmark as bench


def categories():
    result = {}
    for target in bench.models.TARGETS:
        passing = target.startswith("pass_")
        roles = ["QB"] if passing else ["RB", "WR", "TE"] if target == "anytime_td" else ["QB", "RB", "FB", "WR", "TE"]
        result[target] = {"state": "BLOCKED_LABEL_CONTRACT" if target == "fantasy_ppr" else "READY",
            "support": "bernoulli" if target == "anytime_td" else "count" if target in bench.models.COUNT_TARGETS else "signed_integer",
            "modeled_roles": roles, "primary_roles": roles if passing or target == "anytime_td" else ["RB"],
            "panels": {"base": ["f_player_games_prior"], "context": ["f_player_games_prior", "f_context_lag"]}}
    return result


def fixture_source(path):
    rows = []
    for year in (2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026):
        for i, role in enumerate(("QB", "RB", "FB", "WR", "TE")):
            kickoff = pd.Timestamp(f"{year}-09-01T12:00Z") + pd.Timedelta(days=i)
            row = {"season": year, "week": i + 1, "game_id": f"fictional-{year}-{i}", "player_id": f"p-{i}",
                "position": role, "team": "A", "opponent": "B", "kickoff_utc": kickoff,
                "cutoff_utc": kickoff - pd.Timedelta(hours=1), "outcome_available_utc": kickoff + pd.Timedelta(days=7),
                "feature_max_source_available_utc": kickoff - pd.Timedelta(days=7), "participation_state": "played",
                "season_type": "REG", "f_player_games_prior": 3., "f_context_lag": 2.}
            row.update({target: 1. if year <= 2024 else 999999. for target in bench.LABELS})
            row["rush_rec_yd"] = row["rush_yd"] + row["rec_yd"]
            row["anytime_td"] = 1.
            row["fantasy_ppr"] = "forbidden-projected-value"
            rows.append(row)
    pd.DataFrame(rows).to_parquet(path, index=False)


def test_complete_fixed_plan_and_current_source_aliases():
    slots = bench.planned_slots(categories())
    assert len(slots) == 216
    assert sum(s["kind"] == "blocked" for s in slots) == 18
    assert sum(s["kind"] == "alias" for s in slots) == 30
    assert sum(s["kind"] == "reference" for s in slots) == 66
    assert sum(s["kind"] == "model" for s in slots) == 102
    assert all(s["alias_method"] == "median_hgb" for s in slots if s["method"] == "count_A" and s["kind"] == "alias")
    assert all(s["alias_method"] == "count_A" for s in slots if s["method"] == "role_B" and s["kind"] == "alias")


def test_arrow_projection_season_predicates_and_strict_temporal_training(tmp_path):
    path = tmp_path / "fictional.parquet"
    fixture_source(path)
    query, audit = bench.read_partition(path, 2022, "query")
    assert query.season.eq(2022).all()
    assert not set(bench.LABELS) & set(query) and "fantasy_ppr" not in query
    assert query.participation_state.eq("unknown").all()
    assert "participation_state" not in audit["projected_columns"]
    train, probe, audit = bench.fold(path, 2022)
    assert train.season.between(2019, 2021).all()
    assert pd.to_datetime(train.outcome_available_utc, utc=True).max() < probe.cutoff_utc.min()
    with pytest.raises(ValueError, match="global forecast"):
        bench.read_partition(path, 2022, "labels")


def test_exact_serialized_joblib_write_and_role_callback_counts(tmp_path, monkeypatch):
    policy = {"storage": {"version": "operational-storage-v2", "limit_bytes": 8 * 1024**2},
        "namespaces": {"private_retention_bytes": 8 * 1024**2}}
    storage = bench.OperationalStorage(tmp_path / "cache", policy)
    output = storage.register_root(tmp_path / "output")
    session = SimpleNamespace(storage=storage, output=output, bindings={})
    bench.Session.model(session, "private/model.joblib", SimpleNamespace(fictional=True))
    path = output / "private/model.joblib"
    storage.validate_reference(path)
    assert session.bindings["private/model.joblib"] == bench.sha(path)


def _fake_prediction(model, query, *, prior_only=False, score=False):
    assert not set(bench.LABELS) & set(query)
    assert query.participation_state.eq("unknown").all()
    result = query[[c for c in bench.cdf.KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc", "season_type"] if c in query]].copy()
    result["target"] = model.category["target"]
    result["primary_role"] = result.position.isin(model.category["primary_roles"])
    result["history_state"], result["fallback"] = "warm", "fictional_stub"
    result["actual"], result["participation_state"], result["outcome_state"] = np.nan, "unread", "unread"
    result["point"], result["probability"] = 1., 1. if model.category["support"] == "bernoulli" else np.nan
    result["distribution"] = "bernoulli" if model.category["support"] == "bernoulli" else "none_point_heuristic"
    if model.family == "cdf":
        for name in ("mean", "median", "p10", "p90"):
            result[name] = 1.
        result["variance"] = 0.
        for name in ("crps", "log_score", "cdf_actual", "cdf_actual_below", "brier"):
            result[name] = np.nan
        result["distribution"] = "empirical_leaf_plus_support_prior"
    return result


def _fake_cdf_score(model, offered, frozen, *, prior_only=False):
    result = bench.median.score_frozen_rows(offered, frozen, model.category)
    good = result.participation_state.eq("played").to_numpy() & bench.cdf.valid_support(result.actual, model.category["support"])
    result.loc[good, "crps"] = np.abs(result.loc[good, "point"] - result.loc[good, "actual"])
    result.loc[good, "log_score"] = np.where(result.loc[good, "actual"].eq(1), 0., np.inf)
    result.loc[good, "cdf_actual_below"] = result.loc[good, "actual"].gt(1).astype(float)
    result.loc[good, "cdf_actual"] = result.loc[good, "actual"].ge(1).astype(float)
    return result


class OrchestrationFixtureStorage:
    """Storage double for call ordering, not a quota implementation or test.

    Real owned quota serialization is exercised separately above. Thousands of
    immutable quota scans would otherwise dominate this tiny orchestration test.
    """
    def __init__(self, cache, policy):
        pass
    def register_root(self, root):
        root = Path(root).absolute()
        root.mkdir(parents=True, exist_ok=True)
        return root
    def write_bytes(self, path, body, *, replace=False):
        path = Path(path)
        if path.exists() and not replace:
            assert path.read_bytes() == body
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    def atomic_json(self, path, value, *, replace=False):
        self.write_bytes(path, (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode(), replace=replace)
    def write_dataframe(self, frame, path, **kwargs):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, **kwargs)
    def validate_reference(self, path, expected_sha256=None):
        assert Path(path).is_file()
        assert expected_sha256 is None or bench.sha(path) == expected_sha256
    @contextmanager
    def capture_writes(self, roots=None):
        yield self


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    # Every optimizer and reference parameter fit is inert; the full fixed
    # three-year loop exercises counters and the global scoring boundary.
    monkeypatch.setattr(bench, "OperationalStorage", OrchestrationFixtureStorage)
    source = tmp_path / "features.parquet"
    fixture_source(source)
    for name, value in (("manifest.json", {}), ("policy.json", {}), ("categories.json", {"categories": categories()})):
        (tmp_path / name).write_text(json.dumps(value))
    def spec(path):
        return {"path": str(path), "sha256": bench.sha(path), "bytes": path.stat().st_size}
    cfg = {"registration_id": bench.VERSION, "methods": list(bench.METHODS), "partitions": {"evaluation_years": [2022, 2023, 2024]},
        "input_features": spec(source), "source_manifest": spec(tmp_path / "manifest.json"),
        "source_policy": spec(tmp_path / "policy.json"), "category_contract": spec(tmp_path / "categories.json"),
        "cache": str(tmp_path / "cache"), "output": str(tmp_path / "output"),
        "budgets": {"max_wall_seconds": 1200, "max_CPU_seconds": 1800, "max_RSS_bytes": 2 * 1024**3,
            "reporting_reserve_seconds": 180, "max_fit_attempts": 168, "max_reference_calls": 66,
            "max_query_prediction_or_law_row_incidences": 3_000_000, "per_estimator_wall_seconds": 60,
            "per_estimator_CPU_seconds": 90, "threads": 2}}
    config = tmp_path / "benchmark.json"
    config.write_text(json.dumps(cfg))
    policy = {"storage": {"version": "operational-storage-v2", "limit_bytes": 32 * 1024**2},
        "namespaces": {"private_retention_bytes": 32 * 1024**2}, "_policy_sha256": bench.sha(tmp_path / "policy.json")}
    monkeypatch.setattr(bench.operational_sources, "load_source_policy", lambda value: policy)
    monkeypatch.setattr(bench.operational_sources, "_verify", lambda *a, **k: {"adapter_version": "permitted-operational-nfl-history-v2",
        "policy_sha256": policy["_policy_sha256"], "snapshot_sha256": "b" * 64, "training_view_sha256": "c" * 64, "namespace": "fictional"})
    optimizer_calls = []
    def inert_optimizer(self, *args, **kwargs):
        expected = len(optimizer_calls) + 1
        receipt = tmp_path / f"output/consumption/estimator-{expected:03d}.json"
        assert json.loads(receipt.read_text())["state"] == "ESTIMATOR_ATTEMPT_CONSUMED"
        guard = json.loads((tmp_path / "output/estimator-cpu-guard.json").read_text())
        assert guard["active"] and guard["attempt"] == expected
        assert guard["process_start_ticks"] > 0 and guard["process_cpu_start"] >= 0
        assert guard["cpu_clock"] == "proc_utime_plus_stime_over_CLK_TCK"
        assert guard["max_CPU_seconds"] == 90 and guard["max_wall_seconds"] == 60
        optimizer_calls.append(expected)
        return self
    for cls in (bench.cdf.ExtraTreesRegressor, bench.median.HistGradientBoostingRegressor, bench.median.HistGradientBoostingClassifier):
        monkeypatch.setattr(cls, "fit", inert_optimizer)
    def model(train, category, family):
        assert train.season.lt(2025).all()
        return SimpleNamespace(category=category, family=family, audit={"supported_played_training_rows": len(train)})
    def cdf_fit(cls, train, category, panel):
        bench.cdf.ExtraTreesRegressor().fit([[0]], [1])
        return model(train, category, "cdf")
    def median_fit(cls, train, category, panel):
        bench.median.HistGradientBoostingRegressor().fit([[0]], [1])
        return model(train, category, "median")
    def role_fit(cls, train, category, variant, *, before_fit):
        for role in (["pooled"] if variant == "A" else category["modeled_roles"]):
            before_fit({"role": role, "state": "ESTIMATOR_ATTEMPT_CONSUMED"})
            bench.median.HistGradientBoostingRegressor().fit([[0]], [1])
        return model(train, category, "role")
    monkeypatch.setattr(bench.cdf.LeafCDFModel, "fit", classmethod(cdf_fit))
    monkeypatch.setattr(bench.median.MedianBoostingModel, "fit", classmethod(median_fit))
    monkeypatch.setattr(bench.role.RoleCountBoostingModel, "fit", classmethod(role_fit))
    monkeypatch.setattr(bench.cdf, "prediction_rows", _fake_prediction)
    monkeypatch.setattr(bench.median, "prediction_rows", _fake_prediction)
    monkeypatch.setattr(bench.role, "prediction_rows", _fake_prediction)
    monkeypatch.setattr(bench.cdf, "score_frozen_rows", _fake_cdf_score)
    def reference(train, query, target, method, *, artifact_path, binding, storage):
        assert (Path(artifact_path).parent / "reference-consumed.json").is_file()
        storage.atomic_json(artifact_path, {"fictional": True, "binding": binding})
        result = pd.DataFrame({"mean": 1., "fallback": "fictional_reference"}, index=query.index)
        result.attrs["supported_played_training_rows"] = len(train)
        return result
    monkeypatch.setattr(bench.operational_models, "fit_operational_reference", reference)
    original_read = bench.read_partition
    calls = []
    def guarded_read(path, year, lane, **kwargs):
        if lane == "train" and year > 2022:
            assert (tmp_path / f"output/year-freezes/{year-1}.json").is_file()
        if lane == "labels":
            assert (tmp_path / "output/forecast-freeze.json").is_file()
            assert (tmp_path / "output/SCORE_CONSUMED.json").is_file()
        calls.append(lane)
        return original_read(path, year, lane, **kwargs)
    monkeypatch.setattr(bench, "read_partition", guarded_read)
    return config, cfg, calls


def test_fictional_run_global_freeze_then_single_score_real_report_helper(pipeline, monkeypatch):
    reporting = pytest.importorskip("nfl_lab.source_matched_reporting")
    config, cfg, calls = pipeline
    freeze = bench.run_benchmark(config, config_sha256=bench.sha(config))
    assert freeze["fatal"] is None
    assert len(freeze["slots"]) == 216
    assert sum(s["state"] == "BLOCKED" for s in freeze["slots"]) == 18
    assert sum(s["state"] == "PREDICTION_FROZEN" for s in freeze["slots"]) == 198
    assert freeze["usage"]["estimator_attempts"] == 168
    assert freeze["usage"]["reference_calls"] == 66
    assert "estimator-cpu-guard.json" not in freeze["bindings"]
    assert not json.loads((Path(cfg["output"]) / "estimator-cpu-guard.json").read_text())["active"]
    assert calls == ["query", "train"] * 3
    assert not (Path(cfg["output"]) / "SCORE_CONSUMED.json").exists()
    original_builder = reporting.build_target_report
    def paused(*args, **kwargs):
        raise RuntimeError("fictional report pause after complete score freeze")
    monkeypatch.setattr(reporting, "build_target_report", paused)
    with pytest.raises(RuntimeError, match="fictional report pause"):
        bench.report_benchmark(config, config_sha256=bench.sha(config))
    monkeypatch.setattr(reporting, "build_target_report", original_builder)
    before_score_marker = bench.sha(Path(cfg["output"]) / "SCORE_CONSUMED.json")
    def no_work(*args, **kwargs):
        raise AssertionError("frozen-report continuation cannot read labels, infer or fit")
    monkeypatch.setattr(bench, "read_partition", no_work)
    monkeypatch.setattr(bench.cdf, "score_frozen_rows", no_work)
    monkeypatch.setattr(bench.median, "score_frozen_rows", no_work)
    monkeypatch.setattr(bench.cdf.LeafCDFModel, "fit", no_work)
    monkeypatch.setattr(bench.median.MedianBoostingModel, "fit", no_work)
    monkeypatch.setattr(bench.role.RoleCountBoostingModel, "fit", no_work)
    with pytest.raises(ValueError, match="cannot decrease"):
        bench.report_benchmark(config, config_sha256=bench.sha(config), resume_frozen=True,
            spent_usage={"wall_seconds": 0., "CPU_seconds": 0.})
    report = bench.report_benchmark(config, config_sha256=bench.sha(config), resume_frozen=True)
    assert bench.sha(Path(cfg["output"]) / "SCORE_CONSUMED.json") == before_score_marker
    assert calls == ["query", "train"] * 3 + ["labels"] * 3
    scored = json.loads((Path(cfg["output"]) / "scored-freeze.json").read_text())
    assert sum(s["state"] == "COMPLETED" for s in scored["slots"]) == 198
    assert scored["usage"]["estimator_attempts"] == 168
    assert (Path(cfg["output"]) / "report.json").is_file()
    # Small-fictional-frame equivalence of target-local streaming and the full
    # pure helper; this does no fitting, inference or source label access.
    frames = [pd.read_parquet(Path(cfg["output"]) / relative, columns=list(bench.REPORT_FIELDS)) for relative in scored["scored_files"]]
    cat = {t: bench._category(categories(), t) for t in bench.models.TARGETS}
    for target in cat:
        cat[target]["benchmark_slots"] = [{k: s[k] for k in ("year", "method", "state", "reason") if k in s}
            for s in scored["slots"] if s["target"] == target]
    expected_report, _ = reporting.build_reports(pd.concat(frames, ignore_index=True), cat)
    assert report == expected_report
    with pytest.raises(RuntimeError, match="already consumed"):
        bench.run_benchmark(config, config_sha256=bench.sha(config))
    with pytest.raises(RuntimeError, match="already completed"):
        bench.report_benchmark(config, config_sha256=bench.sha(config))


def test_budget_reserved_before_actual_work_and_reporting_can_continue():
    limits = {"max_wall_seconds": 1200, "reporting_reserve_seconds": 180, "max_CPU_seconds": 1800,
        "max_RSS_bytes": 2 * 1024**3, "max_fit_attempts": 1, "max_reference_calls": 1,
        "max_query_prediction_or_law_row_incidences": 10}
    budget = bench.Budget(limits)
    budget.check(fit=True, rows=10)
    with pytest.raises(bench.BudgetExhausted):
        budget.check(fit=True)
    assert budget.fits == 1 and budget.rows == 10
    prior = budget.usage()
    continued = bench.Budget(limits, prior=prior, phase="report")
    assert continued.usage()["CPU_seconds"] >= prior["CPU_seconds"]
    assert continued.fits == 1 and continued.rows == 10


def test_running_estimator_cpu_deadline_interrupts_and_restores_handler():
    import signal
    import time
    prior = signal.getsignal(signal.SIGPROF)
    with pytest.raises(bench.BudgetExhausted, match="CPU deadline"):
        with bench.cpu_deadline(.02):
            until = time.process_time() + 1.
            while time.process_time() < until:
                pass
    assert signal.getsignal(signal.SIGPROF) == prior
    assert signal.getitimer(signal.ITIMER_PROF) == (0., 0.)
