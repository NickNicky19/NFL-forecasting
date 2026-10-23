"""Fictional software acceptance; no real NFL inputs or accuracy evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import types

import numpy as np
import pandas as pd
import pytest

from nfl_lab import cli, experiment, live, operational_models as models
from nfl_lab.model_artifacts import ArtifactError, load_artifact
from nfl_lab.state import digest, records
from test_models import histories


@pytest.fixture
def policy():
    return {"_policy_sha256": "a" * 64, "operational_routing": {"weekly_reference_budget": {
        "max_supported_packages": 22, "max_wall_seconds": 1200}}}


@pytest.fixture
def source(monkeypatch, policy):
    module = types.ModuleType("nfl_lab.operational_sources")
    module.load_source_policy = lambda value: policy
    monkeypatch.setitem(sys.modules, "nfl_lab.operational_sources", module)
    monkeypatch.setattr(models, "code_hashes", lambda: {"fictional_code.py": "c" * 64})
    return module


def manifest(policy, snapshot="b"):
    return {"policy_sha256": policy["_policy_sha256"], "snapshot_sha256": snapshot * 64,
            "training_view_sha256": "d" * 64, "namespace": "fictional-isolated-snapshot",
            "seasons": [2021], "asof_utc": "2023-01-02T00:00:00Z", "allowed_periods": None,
            "source_receipts": {"stats_player_week_2021.parquet": {
                "sha256": "e" * 64, "retrieved_utc": "2023-01-01T00:00:00Z", "status": "acquired"}}}


def feature_fixture(policy):
    train, query = histories(40)
    train = train.reset_index(drop=True)
    train["outcome_available_utc"] = train.kickoff_utc + pd.Timedelta(days=7)
    train.attrs["operational_manifest"] = manifest(policy)
    return train, query


@pytest.mark.parametrize("command", ["acquire", "experiment", "daily", "grade"])
def test_current_cli_requires_explicit_policy(monkeypatch, command):
    monkeypatch.setattr(sys, "argv", ["nfl-lab", command])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2


@pytest.mark.parametrize("command", ["acquire", "experiment", "daily", "grade"])
def test_cli_routes_every_operational_command(tmp_path, monkeypatch, command):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/research.json").write_text("{}")
    seen = []
    def run(*args, **kwargs):
        seen.append((args, kwargs))
        return {"state": "fictional"}
    monkeypatch.setattr(experiment, "acquire_operational_features", run)
    monkeypatch.setattr(experiment, "run_experiment", run)
    monkeypatch.setattr(live, "daily", run)
    monkeypatch.setattr(live, "grade_only", run)
    monkeypatch.setattr(live, "fetch", lambda *args: ({"season": "2025"}, {}))
    monkeypatch.setattr(sys, "argv", ["nfl-lab", command, "--root", str(tmp_path),
                                      "--source-policy", "config/source.json", "--seasons", "2024"])
    cli.main()
    args, kwargs = seen[0]
    if command == "acquire":
        assert args[1] == [2024, 2025]
        assert args[2] == tmp_path / "config/source.json"
    else:
        assert kwargs["source_policy"] == tmp_path / "config/source.json"


def test_feature_snapshot_isolation_and_code_integrity(tmp_path, monkeypatch, source, policy):
    frame, _ = feature_fixture(policy)
    source.acquire_operational_history = lambda *args: {"state": "fictional"}
    source.load_operational_history = lambda *args: frame.copy()
    source.build_operational_features = lambda frame, **kwargs: frame.copy()
    legacy = tmp_path / "processed/features.parquet"
    legacy.parent.mkdir()
    legacy.write_bytes(b"poisoned legacy feature table must remain unread")
    experiment.acquire_operational_features(tmp_path, [2021], policy, "2023-01-02T00:00:00Z")
    loaded, document = experiment.load_operational_features(tmp_path, policy)
    assert len(loaded) == len(frame)
    assert document["source_binding"]["policy_sha256"] == policy["_policy_sha256"]
    assert legacy.read_bytes() == b"poisoned legacy feature table must remain unread"
    monkeypatch.setattr(models, "code_hashes", lambda: {"fictional_code.py": "f" * 64})
    with pytest.raises(ValueError, match="code binding mismatch"):
        experiment.load_operational_features(tmp_path, policy)


def test_reference_artifact_participation_and_exact_replay_pins(tmp_path, source, policy):
    train, query = feature_fixture(policy)
    binding = models.model_binding(policy, manifest(policy), train, query, "f" * 64)
    artifact = tmp_path / "reference.json"
    expected = models.fit_operational_reference(train, query, "pass_yd", "recent", artifact_path=artifact, binding=binding)
    payload = load_artifact(artifact)["artifact"]
    assert payload["participation"] == {"kind": "unavailable"}
    assert payload["training_audit"]["participation"] == models.PARTICIPATION
    assert expected.p_participation.isna().all()
    actual = models.predict_operational_artifact(artifact, query, binding=binding)
    np.testing.assert_allclose(expected["mean"], actual["mean"])
    assert actual.p_participation.isna().all()
    assert "game-0" not in artifact.read_text()
    for key in ("policy_sha256", "training_view_sha256", "snapshot_sha256", "input_sha256"):
        changed = {**binding, key: "0" * 64}
        with pytest.raises(ArtifactError, match="binding mismatch"):
            models.predict_operational_artifact(artifact, query, binding=changed)
    with pytest.raises(ArtifactError, match="code binding mismatch"):
        models.predict_operational_artifact(artifact, query, binding={**binding, "code_sha256": {"changed": "0" * 64}})
    changed = query.copy()
    changed.loc[changed.index[0], "f_player_pass_yd_mean3"] += 1
    with pytest.raises(ArtifactError, match="query binding mismatch"):
        models.predict_operational_artifact(artifact, changed, binding=binding)
    with pytest.raises(ArtifactError, match="target/method mismatch"):
        models.fit_operational_reference(train, query, "pass_att", "recent", artifact_path=artifact, binding=binding)
    with pytest.raises(ValueError, match="PPR"):
        models.fit_operational_reference(train, query, "fantasy_ppr", "recent", artifact_path=tmp_path / "ppr.json", binding=binding)
    with pytest.raises(ValueError, match="recent/pooled"):
        models.fit_operational_reference(train, query, "pass_yd", "ridge", artifact_path=tmp_path / "ridge.json", binding=binding)


def test_weekly_refresh_has_no_campaign_scoring_and_at_most_22_packages(tmp_path, monkeypatch, source, policy):
    train, _ = feature_fixture(policy)
    document = {"asof_utc": "2023-01-02T00:00:00Z", "feature_sha256": "f" * 64,
                "source_binding": models.source_binding(policy, manifest(policy)), "operational_manifest": manifest(policy)}
    monkeypatch.setattr(experiment, "load_operational_features", lambda *args: (train, document))
    def forbidden(*args, **kwargs):
        raise AssertionError("weekly references cannot run the historical campaign/scoring")
    monkeypatch.setattr("nfl_lab.evaluation.campaign", forbidden)
    result = experiment.run_experiment(tmp_path, tmp_path / "cache", tmp_path / "state", {}, source_policy=policy)
    assert result["package_count"] == 22
    assert {package["method"] for package in result["packages"]} == {"recent", "pooled"}
    assert "fantasy_ppr" not in {package["target"] for package in result["packages"]}
    assert result["new_hyperparameter_searches"] == result["new_accuracy_scores"] == 0
    assert result["promotion"] == "NONE"
    receipt = next(records(tmp_path / "state", "training"))
    assert receipt["state"] == "COMPLETED"
    assert "player-0" not in json.dumps(receipt)
    # Exact retry replays immutable parameters and does not refit.
    monkeypatch.setattr("nfl_lab.models.fit_predict", forbidden)
    retry = experiment.run_reference_learning(tmp_path, tmp_path / "cache", tmp_path / "state", policy)
    assert retry["packages"] == result["packages"]


def test_daily_failure_grades_without_legacy_fallback(tmp_path, monkeypatch, source, policy):
    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden legacy/capture path")
    monkeypatch.setattr("nfl_lab.data.acquire_history", forbidden)
    monkeypatch.setattr("nfl_lab.data.load_history", forbidden)
    monkeypatch.setattr(live, "capture", forbidden)
    monkeypatch.setattr(live, "grade_only", lambda *args, **kwargs: {"grading": {"preserved": True}})
    def failed(*args):
        raise RuntimeError("fictional permitted source unavailable")
    source.acquire_operational_history = failed
    source.load_operational_history = forbidden
    monkeypatch.setattr(live, "fetch", lambda *args: ({"season_type": "regular", "season": "2025", "week": 18}, {}))
    # Fail at the permitted acquisition rather than the unrelated schedule parser.
    monkeypatch.setattr(live, "schedule_games", lambda *args: [{"game_id": "espn:fictional"}])
    def fetch(cache, name, url):
        if name == "state":
            return {"season_type": "regular", "season": "2025", "week": 18}, {}
        if name.startswith("schedule"):
            return {"season": {"year": 2025}, "week": {"number": 18}}, {}
        return {}, {}
    monkeypatch.setattr(live, "fetch", fetch)
    selected = tmp_path / "reports/initial-campaign/selected.json"
    selected.parent.mkdir(parents=True)
    selected.write_text("invalid selected method file must remain unread")
    result = live.daily(tmp_path, tmp_path / "cache", tmp_path / "state", [2024], source_policy=policy)
    assert result["state"] == "PERMITTED_SOURCE_ISSUANCE_ABSTAINED"
    assert "permitted source unavailable" in result["error"]
    assert result["grading"]["preserved"] and result["new_forecasts"] == 0
    assert list(records(tmp_path / "state", "forecasts")) == []


def test_daily_snapshot_refresh_preserves_frozen_opportunities_and_nfl_season(tmp_path, monkeypatch, source, policy):
    from nfl_lab.state import capture
    clock = datetime(2030, 1, 10, tzinfo=timezone.utc)
    train, _ = feature_fixture(policy)
    original_hash = models.frame_hash(train)
    requests = []
    snapshots = [0]
    def acquire(cache, seasons, policy, asof):
        requests.append(seasons)
        snapshots[0] += 1
        return {"state": "fictional"}
    def history_load(*args):
        frame = train.copy()
        frame.attrs["operational_manifest"] = manifest(policy, "b" if snapshots[0] == 1 else "f")
        return frame
    def build(history, *, policy, queries=None):
        assert models.frame_hash(history) == original_hash
        if queries is None:
            return history.copy()
        result = queries.copy()
        for column in train:
            if column.startswith("f_"):
                result[column] = train.iloc[-1][column]
        return result
    source.acquire_operational_history = acquire
    source.load_operational_history = history_load
    source.build_operational_features = build
    source.load_operational_identity = lambda *args: pd.DataFrame({"player_id": ["00-0030001"], "sleeper_id": ["123"], "identity_status": ["source_exact_binding"]})
    calls = []
    def fake_fit(train, query, target, method, *, artifact_path, binding):
        calls.append((target, method))
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("fictional reference package")
        return prediction(query)
    def prediction(query):
        return pd.DataFrame({"mean": 1., "scale": 1., "family": "normal", "p10": 0., "p50": 1., "p90": 2., "p_participation": np.nan, "fallback": ""}, index=query.index)
    monkeypatch.setattr(models, "fit_operational_reference", fake_fit)
    monkeypatch.setattr(models, "predict_operational_artifact", lambda path, query, **kwargs: prediction(query))
    monkeypatch.setattr(live, "now_utc", lambda: clock)
    monkeypatch.setattr(live, "capture", lambda state, rows: capture(state, rows, clock=lambda: clock))
    monkeypatch.setattr(live, "grade_saved", lambda *args, **kwargs: {"preserved": True})
    monkeypatch.setattr("nfl_lab.website_baselines.prepare_website_snapshot", lambda *args: {"report": {"state": "fictional"}})
    monkeypatch.setattr("nfl_lab.website_baselines.capture_website_bindings", lambda *args: {"state": "fictional"})
    def fetch(cache, name, url):
        receipt = {"sha256": "e" * 64, "retrieved_utc": clock.isoformat()}
        if name == "state":
            return {"season_type": "regular", "season": "2029", "week": 18}, receipt
        if name == "players":
            return {"123": {"position": "QB", "team": "A", "active": True, "gsis_id": "00-0030001"}}, receipt
        if name.startswith("schedule"):
            return {"season": {"year": 2029}, "week": {"number": 18}}, receipt
        return {}, receipt
    monkeypatch.setattr(live, "fetch", fetch)
    monkeypatch.setattr(live, "schedule_games", lambda *args: [{"game_id": "espn:fictional", "kickoff_utc": "2030-01-11T17:00:00Z", "home": "A", "away": "B", "final": False}])
    first = live.daily(tmp_path, tmp_path / "cache", tmp_path / "state", [2028], source_policy=policy)
    assert first["capture"]["recorded"] == 22
    before = {path: path.read_bytes() for path in (tmp_path / "state/forecasts").glob("*")}
    second = live.daily(tmp_path, tmp_path / "cache", tmp_path / "state", [2028], source_policy=policy)
    assert second["capture"]["recorded"] == 0
    assert second["already_frozen_opportunities"] == 22
    assert requests == [[2028, 2029], [2028, 2029]]
    assert len(calls) == 22
    assert all(path.read_bytes() == body for path, body in before.items())
    rows = [row for batch in records(tmp_path / "state", "forecasts") for row in batch["rows"]]
    assert all(row["p_participation"] is None for row in rows)
    assert all(row["target"] != "fantasy_ppr" for row in rows)
    assert {row["model_id"].rsplit("-", 1)[-1] for row in rows} == {"recent", "pooled"}


def test_postcapture_failure_reports_actual_immutable_issuance(tmp_path, monkeypatch, source, policy):
    from nfl_lab.state import capture
    clock = datetime(2030, 1, 10, tzinfo=timezone.utc)
    row = {"player_id": "fictional", "game_id": "fictional-game", "team": "A", "opponent": "B",
           "target": "rec", "model_id": "fictional-reference", "scoring_id": "nfl-full-game-v1",
           "input_sha256": "a" * 64, "code_sha256": "b" * 64,
           "kickoff_utc": "2030-01-11T17:00:00Z", "mean": 1.}
    def failed_daily(root, cache, state, *args, **kwargs):
        capture(state, [row], clock=lambda: clock)
        raise RuntimeError("fictional failure after capture")
    monkeypatch.setattr(live, "_daily", failed_daily)
    monkeypatch.setattr(live, "grade_only", lambda *args, **kwargs: {"grading": {"preserved": True}})
    result = live.daily(tmp_path, tmp_path / "cache", tmp_path / "state", [2029], source_policy=policy)
    assert result["state"] == "PERMITTED_OPERATION_FAILED_AFTER_ISSUANCE"
    assert result["new_forecasts"] == 1 and result["grading"]["preserved"]
    assert len(next(records(tmp_path / "state", "forecasts"))["rows"]) == 1


def test_permitted_grading_only_reads_same_policy_cache(tmp_path, monkeypatch, source, policy):
    from nfl_lab.grading_sources import load_permitted_grading_context
    from test_grading_sources import fixtures
    context, _, _ = fixtures()
    history = context["history"]
    history.attrs["operational_manifest"] = manifest(policy)
    calls = []
    def history_load(*args, **kwargs):
        calls.append((args[1], kwargs))
        return history
    source.load_operational_history = history_load
    identity_calls = []
    def identity_load(*args, **kwargs):
        identity_calls.append((args[1:], kwargs))
        return context["identity"]
    source.load_operational_identity = identity_load
    def forbidden(*args, **kwargs):
        raise AssertionError("legacy grading source read")
    monkeypatch.setattr("nfl_lab.grading_sources.load_history", forbidden)
    monkeypatch.setattr("nfl_lab.grading_sources.load_identity", forbidden)
    result = load_permitted_grading_context(tmp_path, [2026], policy, "2026-10-23T00:00:00Z")
    assert calls == [([2026], {"latest": True})]
    assert identity_calls == [(([2021], policy, "2023-01-02T00:00:00Z"), {"allowed_periods": None})]
    assert result["operational_manifest"]["policy_sha256"] == policy["_policy_sha256"]


def test_scheduler_is_single_and_grades_after_failures():
    workflow = (Path(__file__).parents[1] / ".github/workflows/lab.yml").read_text()
    assert workflow.count("- cron:") == 1
    assert workflow.count("runs-on:") == 1
    assert "nfl-lab-single-writer" in workflow
    for command in ("daily", "acquire", "experiment", "grade"):
        assert f"nfl_lab.cli {command} --source-policy config/operational-source-policy-v1.json" in workflow
    assert workflow.index("id: training") < workflow.index("id: grading")
    assert "steps.daily.outcome == 'failure'" in workflow
    assert "steps.training.outcome == 'failure'" in workflow
    assert "if: always() && steps.acceptance.outcome == 'success'" in workflow
    assert "timeout-minutes: 40" in workflow
    assert "timeout 540" in workflow and "timeout 720" in workflow
    assert workflow.count("timeout 180") == 2
    assert "retention-days: 14" in workflow


def test_operational_storage_cap_combines_sources_features_and_models(tmp_path, policy):
    policy = {**policy, "namespaces": {"private_retention_bytes": 10}}
    source = tmp_path / "cache/operational-source-v1/policy/source"
    feature = tmp_path / "cache/processed/operational-source-v1/policy/features"
    model = tmp_path / "state/models" / models.VERSION / "model"
    for path in (source, feature, model):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"123")
    assert models.check_operational_storage(tmp_path / "cache", policy, state=tmp_path / "state") == 9
    with pytest.raises(RuntimeError, match="combined operational"):
        models.check_operational_storage(tmp_path / "cache", policy, state=tmp_path / "state", reserve_bytes=2)
    assert all(path.read_bytes() == b"123" for path in (source, feature, model))
