"""Fictional reporting repair fixtures; no NFL rows, fits or forecasts."""
import ast
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_lab import role_boosting_reporting_repair as repair
from nfl_lab.cdf_engine import KEYS


def scored_fixture():
    candidate = pd.DataFrame({"season": np.array([3001, 3001, 3001], dtype="int32"),
        "week": np.array([1, 2, 2], dtype="int32"), "game_id": ["fiction-1", "fiction-2", "fiction-2"],
        "player_id": ["fiction-a", "fiction-a", "fiction-b"], "target": "pass_att",
        "point": [3., -0., np.nan], "probability": [np.nan, np.nan, np.nan],
        "actual": [2., 0., np.nan], "participation_state": ["played", "played", "unknown"],
        "outcome_state": ["played_nonzero", "played_zero", "unknown"], "primary_role": True,
        "fallback": "", "position": "QB", "team": "FA", "opponent": "FB", "history_state": "warm"})
    controls = []
    for method in ["old_hgb", "website"]:
        control = candidate.copy()
        control["season"], control["week"] = control.season.astype("int64"), control.week.astype("int64")
        control["method"] = method
        controls.append(control)
    return candidate, pd.concat(controls, ignore_index=True)


def test_key_width_only_fix_preserves_order_outcomes_states_and_float_bits():
    candidate, controls = scored_fixture()
    left, right = repair.normalize_scored_frames(candidate, controls)
    assert left.season.dtype == right.season.dtype == np.dtype("int64")
    assert left.week.dtype == right.week.dtype == np.dtype("int64")
    assert left[KEYS].values.tolist() == candidate[KEYS].values.tolist()
    for before, after in [(candidate, left), (controls, right)]:
        pd.testing.assert_frame_equal(before.drop(columns=KEYS), after.drop(columns=KEYS), check_exact=True)
        for name in ["point", "actual", "probability"]:
            assert before[name].to_numpy().tobytes() == after[name].to_numpy().tobytes()
    # Existing report and cohort checks now accept identical canonical keys.
    category = {"target": "pass_att", "support": "count", "primary_roles": ["QB"]}
    report, _ = repair.original.report_cell(left, right, category, historical=False)
    assert report["summary"]["offered_rows"] == 3
    assert len(report["common_all_controls"]) == 4
    assert len(repair.original.common_cohort_reports(left, left.copy(), right, category)) == 8


@pytest.mark.parametrize("kind", ["id", "order", "outcome", "participation", "duplicate", "fraction", "boolean", "null", "numeric_id"])
def test_identity_and_outcome_changes_fail_closed(kind):
    candidate, controls = scored_fixture()
    if kind == "id":
        controls.loc[0, "player_id"] = "fiction-changed"
    elif kind == "order":
        controls = controls.iloc[[1, 0, 2, 3, 4, 5]].reset_index(drop=True)
    elif kind == "outcome":
        controls.loc[0, "actual"] = 999.
    elif kind == "participation":
        controls.loc[0, "participation_state"] = "DNP"
    elif kind == "duplicate":
        controls = pd.concat([controls, controls.iloc[[0]]], ignore_index=True)
    elif kind == "fraction":
        candidate["week"] = [1., 2.5, 2.]
    elif kind == "boolean":
        candidate["season"] = [True, False, True]
    elif kind == "null":
        candidate.loc[0, "game_id"] = None
    else:
        candidate["player_id"] = [1, 2, 3]
    with pytest.raises(ValueError):
        repair.normalize_scored_frames(candidate, controls)


def test_original_snapshot_rejects_changes_additions_and_preserves_failed_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ["failed-trace.log", "score-consumed.json", "candidate-scored.parquet"]:
        (source / name).write_bytes(b"fictional opaque retained bytes")
    frozen = repair.source_snapshot(source)
    repair.verify_source_snapshot(source, frozen)
    (source / "candidate-scored.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hashes changed"):
        repair.verify_source_snapshot(source, frozen)
    (source / "candidate-scored.parquet").write_bytes(b"fictional opaque retained bytes")
    (source / "extra.txt").write_text("unregistered")
    with pytest.raises(ValueError, match="inventory"):
        repair.verify_source_snapshot(source, frozen)


def test_create_only_second_attempt_and_marker_rejected(tmp_path):
    directory = tmp_path / "REPORT_REPAIR_01"
    directory.mkdir()
    repair.create_json(directory / "repair-consumed.json", {"fictional": True})
    with pytest.raises(FileExistsError):
        repair.create_json(directory / "repair-consumed.json", {})
    with pytest.raises(FileExistsError, match="second repair attempt"):
        repair.run(tmp_path / "does-not-exist.json", directory)


def seal_fixture(tmp_path, monkeypatch):
    source = tmp_path / "RUN_01"
    source.mkdir()
    registry = {"output_directory": str(source)}
    registry_file = tmp_path / "original-registry.json"
    repair.create_json(registry_file, registry)
    (source / "registry.json").write_bytes(registry_file.read_bytes())
    statuses = [{"target": t, "variant": v, "period": p,
        "state": "BLOCKED_CATEGORY_CONTRACT" if t == "fantasy_ppr" else "PREDICTION_FROZEN",
        "fit_attempts": 136 if (t, v, p) == ("pass_yd", "A", "2022") else 0,
        "blocked_subfit_slots": (1 if v == "A" else 5) if t == "fantasy_ppr" else 0}
        for t in repair.original.TARGETS for v in repair.original.VARIANTS for p in repair.original.PERIODS]
    repair.create_json(source / "attempts.json", statuses)
    repair.create_json(source / "forecast-freeze.json", {"bindings": {}, "fit_attempts": 136,
        "attempts_sha256": repair.digest(source / "attempts.json")})
    repair.create_json(source / "completion.json", {"state": "INCOMPLETE_RETAINED_NO_RESTART",
        "fit_attempts_consumed": 136, "score_pass_consumed": True,
        "reporting": {"returncode": 1}, "statuses": statuses})
    repair.create_json(source / "score-consumed.json", {"score_passes": 1,
        "forecast_freeze_sha256": repair.digest(source / "forecast-freeze.json")})
    module = Path(repair.__file__).resolve()
    payload = {"registration_id": repair.VERSION, "budgets": repair.LIMITS,
        "new_independent_observations": 0, "source_registry": {"path": str(registry_file), "sha256": repair.digest(registry_file)},
        "source_run_directory": str(source), "output_directory": str(tmp_path / "REPORT_REPAIR_01"),
        "source_file_sha256": repair.source_snapshot(source),
        "code_bindings": [{"path": str(module), "sha256": repair.digest(module)}]}
    plan = tmp_path / "PLAN.json"
    repair.create_json(plan, dict(payload, state="FOR_REVIEW"))
    sealed = dict(payload, state="SEALED_ROOT_AND_REVIEWER", seal={"integrator": "/root",
        "reviewer": "/root/fictional_reviewer", "decision": "PASS_BOUNDED_REPORTING_REPAIR_ONLY",
        "reviewed_plan_path": str(plan), "reviewed_plan_sha256": repair.digest(plan)})
    seal = tmp_path / "SEALED.json"
    repair.create_json(seal, sealed)
    # The unchanged old seal has its own comprehensive fictional tests. This
    # fixture isolates new seal checks without opening any original NFL files.
    monkeypatch.setattr(repair.original, "check_seal", lambda _: registry)
    return seal, sealed


def test_repair_seal_checks_original_failure_marker_inventory_and_budget(tmp_path, monkeypatch):
    seal, payload = seal_fixture(tmp_path, monkeypatch)
    accepted, _, statuses = repair.check_seal(seal)
    assert accepted["budgets"]["maximum_candidate_fit_attempts"] == 0
    assert len(statuses) == 96
    source = Path(payload["source_run_directory"])
    (source / "score-consumed.json").write_text("{}")
    with pytest.raises(ValueError, match="hashes changed"):
        repair.check_seal(seal)


def test_no_fit_predict_model_load_or_original_controller_entrypoint():
    tree = ast.parse(inspect.getsource(repair))
    forbidden = {"fit", "predict", "load", "prediction_rows", "prediction_trial", "load_prediction_inputs", "score_report"}
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if isinstance(call.func, ast.Attribute):
            assert call.func.attr not in forbidden
            assert not (isinstance(call.func.value, ast.Name) and call.func.value.id == "original" and call.func.attr == "run")
    assert repair.LIMITS["maximum_candidate_fit_attempts"] == repair.LIMITS["maximum_prediction_calls"] == 0
    candidate, controls = scored_fixture()
    repair.normalize_scored_frames(candidate, controls)


def test_provenance_honestly_retains_failed_original_and_two_attempts(tmp_path):
    payload = {"source_registry": {"sha256": "a" * 64},
        "source_file_sha256": {k: "b" * 64 for k in ["forecast-freeze.json", "completion.json", "score-consumed.json"]}}
    value = repair.provenance(payload, tmp_path)
    assert value["original_state"] == "INCOMPLETE_RETAINED_NO_RESTART"
    assert value["original_fit_attempts_consumed"] == 136
    assert value["original_failed_report_attempts"] == value["repair_report_attempts_consumed"] == 1
    assert value["cumulative_report_attempts"] == 2
    assert value["new_fits"] == value["new_predictions"] == value["new_independent_observations"] == 0
