"""Fictional freeze, scoring, control identity and resource lifecycle checks."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import nfl_lab.median_boosting_campaign as campaign
from nfl_lab.cdf_engine import KEYS
from nfl_lab.median_boosting import MedianBoostingModel, prediction_rows, score_frozen_rows
from test_cdf_engine import fictional
from test_website_cdf import website_fixture


def test_source_change_retains_outer_rows_and_quarantines_values_without_hiding_qualification_changes():
    from nfl_lab.median_boosting_evaluation import source_change_control
    _, query, category = fictional()
    query = query.iloc[:5].copy()
    saved = query[KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc", "participation_state"]].copy()
    saved["target"], saved["method"], saved["point"], saved["source_field"] = "pass_att", "pooled", 4., "literal_saved_point"
    saved["actual"] = query.pass_att.to_numpy()
    saved.loc[saved.index[0], "actual"] += 1  # genuine both-finite conflict
    saved.loc[saved.index[1], "actual"] = np.nan  # availability difference
    saved.loc[saved.index[2], "participation_state"] = "DNP"  # old inferred status
    query.loc[query.index[3], "participation_state"] = "unknown"
    query.loc[query.index[3], "pass_att"] = np.nan
    extra = saved.iloc[[-1]].copy()
    extra["game_id"] = "fictional-old-control-only"
    saved = pd.concat([saved.iloc[:4], extra], ignore_index=True)
    original = saved.copy(deep=True)
    result, audit, receipt = source_change_control(saved, query, category, "pooled")
    pd.testing.assert_frame_equal(saved, original)
    assert len(result) == 5 and len(audit) == 6
    assert receipt["common_rows"] == 4 and receipt["candidate_only_rows"] == 1 and receipt["control_only_rows"] == 1
    assert receipt["raw_actual_conflicts_quarantined"] == 1 and receipt["old_missing_new_finite"] == 1
    assert receipt["participation_qualification_changes"] == 2
    assert np.isnan(result.point.iloc[0]) and result.retained_point.iloc[0] == 4
    assert np.isnan(result.retained_actual.iloc[1]) and result.point.iloc[1] == 4
    assert result.retained_participation_state.iloc[2] == "DNP" and result.participation_state.iloc[2] == "played"
    assert result.participation_state.iloc[3] == "unknown" and np.isnan(result.actual.iloc[3])
    assert np.isnan(result.point.iloc[4])
    saved.loc[0, "team"] = "wrong"
    with pytest.raises(ValueError, match="common context mismatch"):
        source_change_control(saved, query, category, "pooled")


def test_source_change_proved_dnp_contradiction_is_quarantined():
    from nfl_lab.median_boosting_evaluation import source_change_control
    _, query, category = fictional()
    saved = query[KEYS + ["team", "opponent", "position", "kickoff_utc", "participation_state"]].copy()
    saved["target"], saved["method"], saved["point"], saved["actual"] = "pass_att", "pooled", 4., np.nan
    saved["participation_state"], saved["participation_confirmed"] = "DNP", True
    result, _, receipt = source_change_control(saved, query, category, "pooled")
    assert result.point.isna().all()
    assert receipt["confirmed_participation_conflicts_quarantined"] == len(query)
    assert receipt["cutoff_binding"].startswith("unrecorded_in_saved_control")


def test_binary_summary_and_exact_pair_diagnostics_retain_infinity_and_fixed_deciles():
    train, query, category = fictional()
    category = dict(category, target="event", support="bernoulli")
    train["event"] = np.arange(len(train)) % 2
    query["event"] = 1
    scored = score_frozen_rows(query, prediction_rows(MedianBoostingModel.fit(train, category, "base"), query), category)
    scored["point"] = 0.
    control = scored.copy()
    control["method"], control["point"] = "website", 1.
    report, _ = campaign.report_cell(scored, control, category, historical=False)
    summary = report["summary"]
    assert summary["log_loss_state"] == "positive_infinity" and summary["infinite_log_losses"] == len(query)
    assert summary["finite_log_loss_count"] == 0 and summary["finite_log_loss_sum"] == 0
    assert len(summary["reliability_deciles"]) == 10 and summary["reliability_deciles"][0]["rows"] == len(query)
    paired = next(x for x in report["paired"] if x["status"] == "primary")
    assert paired["paired_binary"]["candidate"]["log_loss_state"] == "positive_infinity"
    assert paired["paired_binary"]["control"]["natural_log_loss"] == 0
    assert paired["paired_binary"]["control_reliability_deciles"][9]["rows"] == len(query)
    assert paired["players"] == query.player_id.nunique()


def test_saved_cdf_numeric_control_uses_saved_median_and_checks_exact_context_and_outcomes(tmp_path):
    train, query, category = fictional()
    frozen = prediction_rows(MedianBoostingModel.fit(train, category, "base"), query)
    saved = score_frozen_rows(query, frozen, category).drop(columns=["point", "probability"])
    saved["method"], saved["mean"], saved["median"] = "leaf_cdf_base", 999., 2.
    path = tmp_path / "cdf.parquet"
    saved.to_parquet(path, index=False)
    result = campaign.saved_control({"path": str(path)}, query, category, "old_cdf")
    assert result.point.eq(2.).all() and result.source_field.eq("saved_cdf_lower_median").all()
    bad = query.copy()
    bad.loc[bad.index[0], "team"] = "wrong"
    with pytest.raises(ValueError, match="context mismatch"):
        campaign.saved_control({"path": str(path)}, bad, category, "old_cdf")
    bad = query.copy()
    bad.loc[bad.index[0], "pass_att"] += 1
    with pytest.raises(ValueError, match="outcome mismatch"):
        campaign.saved_control({"path": str(path)}, bad, category, "old_cdf")


def test_historical_primary_is_all_original_offered_and_reuses_exact_interval_api():
    train, query, category = fictional()
    query.loc[query.index[0], "position"] = "WR"
    frozen = prediction_rows(MedianBoostingModel.fit(train, category, "base"), query)
    scored = score_frozen_rows(query, frozen, category)
    control = scored.copy()
    control["method"] = "old_cdf"
    control["point"] += 1
    report, rows = campaign.report_cell(scored, control, category, historical=True, pooled_primary=True)
    primary = next(x for x in report["paired"] if x["status"] == "primary")
    assert primary["population"] == "all_original_offered" and primary["paired_rows"] == len(query)
    expected = np.abs(scored.point - scored.actual).mean() - np.abs(control.point - control.actual).mean()
    assert primary["delta_candidate_minus_control"] == pytest.approx(expected)
    assert not np.array_equal(rows.candidate_point, rows.literal_control_point)
    assert all(x["replicates"] == 500 and x["primary_loss"] == "point_mae" for x in primary["intervals"])
    assert not {"mean", "median"} & set(scored)
    assert len(rows) == 2 * len(query)
    more = pd.concat([control, control.assign(method="pooled"), control.assign(method="recent")], ignore_index=True)
    all_report, _ = campaign.report_cell(scored, more, category, historical=True, pooled_primary=True)
    assert [(x["comparator"], x["population"]) for x in all_report["paired"] if x["status"] == "primary"] == [("old_cdf", "all_original_offered")]
    annual, _ = campaign.report_cell(scored, more, category, historical=True)
    assert all(x["status"] == "secondary" for x in annual["paired"])


def test_prediction_loader_never_opens_historical_evaluation_labels(tmp_path, monkeypatch):
    train, query, _ = fictional()
    source = tmp_path / "features.parquet"
    pd.concat([train, query], ignore_index=True).to_parquet(source, index=False)
    reader, calls = pd.read_parquet, []
    def tracked(path, *args, **kwargs):
        calls.append(kwargs)
        return reader(path, *args, **kwargs)
    monkeypatch.setattr(pd, "read_parquet", tracked)
    old, future, offers, _ = campaign.load_prediction_inputs({"inputs": {"training_features": {"path": str(source)}}}, "pass_att", "2022")
    assert len(old) == len(train) and len(future) == len(query) and offers is None
    assert "pass_att" not in calls[0]["columns"] and "participation_state" not in calls[0]["columns"]
    assert "pass_att" not in future and future.participation_state.eq("unknown").all()
    assert calls[1]["filters"] == [("season", "<", 2022)]


def test_fictional_website_freeze_score_roundtrip_is_once_and_labels_only_after_global_freeze(tmp_path, monkeypatch):
    train, query, offers, outcomes, category = website_fixture()
    paths = {}
    for name, frame in [("training_features", train), ("query_features", query), ("opportunities", offers), ("outcomes", outcomes)]:
        p = tmp_path / (name + ".parquet")
        frame.to_parquet(p, index=False)
        paths[name] = {"path": str(p), "sha256": campaign.digest(p)}
    # Literal prior CDF points are fictional constants, not a second model fit.
    old = offers.copy()
    old["method"], old["mean"], old["median"] = "leaf_cdf_base", 3., 2.
    old["actual"], old["participation_state"] = outcomes.actual, outcomes.participation_state
    old_path = tmp_path / "old-cdf.parquet"
    old.to_parquet(old_path, index=False)
    output = tmp_path / "output"
    registry = {"inputs": paths, "categories": {"pass_att": category}, "output_directory": str(output),
        "saved_controls": {"pass_att": {"base": {"website_week6": {"old_cdf": {"path": str(old_path)}}}}},
        "source_qualification": "fictional only", "prior_search_and_exposure": "fictional only",
        "budgets": campaign.LIMITS, "source_packet_mode": "same_retained_packet"}
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)
    monkeypatch.setattr(campaign, "TARGETS", ("pass_att",))
    reader, reads = pd.read_parquet, []
    def tracked(path, *args, **kwargs):
        reads.append(str(path))
        return reader(path, *args, **kwargs)
    monkeypatch.setattr(pd, "read_parquet", tracked)
    directory = output / "trials/pass_att/base/website_week6"
    directory.mkdir(parents=True)
    campaign.write_json(directory / "attempt-consumed.json", {"attempt": 1})
    campaign.prediction_trial("fictional", directory, "pass_att", "base", "website_week6")
    assert paths["outcomes"]["path"] not in reads and str(old_path) not in reads
    frozen = reader(directory / "candidate-frozen.parquet")
    assert frozen.actual.isna().all() and frozen.participation_state.eq("unread").all()
    assert "pass_att" not in reader(directory / "query.parquet")
    status = {"target": "pass_att", "panel": "base", "period": "website_week6", "trial": "trials/pass_att/base/website_week6", "state": "PREDICTION_FROZEN"}
    campaign.write_json(output / "attempts.json", [status])
    manifest = json.loads((directory / "prediction-manifest.json").read_text())
    bindings = {str((directory / name).relative_to(output)): sha for name, sha in manifest["bindings"].items()}
    campaign.write_json(output / "forecast-freeze.json", {"bindings": bindings, "attempts_sha256": campaign.digest(output / "attempts.json")})
    campaign.score_report("fictional", output)
    assert reads.count(paths["outcomes"]["path"]) == 1
    scored = reader(directory / "candidate-scored.parquet")
    pd.testing.assert_series_equal(scored.point, frozen.point)
    assert scored.qualified_outcome_source_version.eq("fictional-v1").all()
    report = json.loads((output / "median-boosting-report.json").read_text())
    assert len(report["slots"]) == 2 and report["score_passes"] == 1
    assert not report["historical_pooled"]
    with pytest.raises(ValueError, match="one score pass"):
        campaign.score_report("fictional", output)
    with pytest.raises(FileExistsError, match="no retry"):
        campaign.prediction_trial("fictional", directory, "pass_att", "base", "website_week6")


def test_parent_consumes_failures_and_freezes_all_periods_before_one_score(tmp_path, monkeypatch):
    registry = {"output_directory": str(tmp_path / "out"), "budgets": dict(campaign.LIMITS, maximum_candidate_fit_attempts=2),
        "categories": {"pass_att": {"state": "READY"}, "fantasy_ppr": {"state": "BLOCKED"}}}
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)
    monkeypatch.setattr(campaign, "TARGETS", ("pass_att", "fantasy_ppr"))
    calls = []
    def fake_monitor(arguments, output, directory, **kwargs):
        calls.append(arguments[0])
        if arguments[0] == "predict-trial":
            assert (directory / "attempt-consumed.json").is_file()
            return {"returncode": 1, "reason": "FICTIONAL_FAILURE", "cpu_seconds": .01}
        assert (output / "forecast-freeze.json").is_file()
        campaign.write_json(output / "median-boosting-report.json", {"fictional": True})
        return {"returncode": 0, "reason": None, "cpu_seconds": .01}
    monkeypatch.setattr(campaign, "monitored_process", fake_monitor)
    registry_path = tmp_path / "registry.json"
    campaign.write_json(registry_path, registry)
    assert campaign.run(registry_path, tmp_path / "out")
    assert calls == ["predict-trial", "predict-trial", "score-report"]
    statuses = json.loads((tmp_path / "out/attempts.json").read_text())
    assert len(statuses) == 16
    assert sum(x["state"] == "FAILED_CONSUMED" for x in statuses) == 2
    assert sum(x["state"] == "BLOCKED_CATEGORY_CONTRACT" for x in statuses) == 8
    with pytest.raises(FileExistsError, match="restart prohibited"):
        campaign.run(registry_path, tmp_path / "out")


def test_historical_source_change_roundtrip_keeps_denominators_pooled_reports_and_panel_ablation(tmp_path, monkeypatch):
    train, query, category = fictional()
    _, week6, offers, outcomes, _ = website_fixture()
    frames = {"training_features": pd.concat([train, query], ignore_index=True), "query_features": week6,
              "opportunities": offers, "outcomes": outcomes}
    inputs = {}
    for name, frame in frames.items():
        p = tmp_path / (name + ".parquet")
        frame.to_parquet(p, index=False)
        inputs[name] = {"path": str(p), "sha256": campaign.digest(p)}
    saved_controls = {"pass_att": {}}
    for panel in ["base", "context"]:
        saved_controls["pass_att"][panel] = {"2022": {}}
        for method in ["old_cdf", "recent", "pooled"]:
            old = query[KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc", "participation_state"]].iloc[:-1].copy()
            old["target"], old["actual"] = "pass_att", query.pass_att.iloc[:-1].to_numpy()
            old["method"] = "leaf_cdf_" + panel if method == "old_cdf" else method
            old["mean"], old["median"] = 99., 2.
            p = tmp_path / (panel + "-" + method + ".parquet")
            old.to_parquet(p, index=False)
            saved_controls["pass_att"][panel]["2022"][method] = {"path": str(p), "sha256": campaign.digest(p)}
    output = tmp_path / "out"
    registry = {"inputs": inputs, "output_directory": str(output), "categories": {"pass_att": category},
        "saved_controls": saved_controls, "source_packet_mode": "joint_learner_source_reconstruction",
        "source_qualification": "fictional only", "prior_search_and_exposure": "fictional only", "budgets": campaign.LIMITS}
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)
    monkeypatch.setattr(campaign, "TARGETS", ("pass_att",))
    statuses, bindings = [], {}
    for panel in ["base", "context"]:
        relative = f"trials/pass_att/{panel}/2022"
        directory = output / relative
        directory.mkdir(parents=True)
        campaign.write_json(directory / "attempt-consumed.json", {"attempt": len(statuses) + 1})
        campaign.prediction_trial("fictional", directory, "pass_att", panel, "2022")
        manifest = json.loads((directory / "prediction-manifest.json").read_text())
        bindings.update({str((directory / p).relative_to(output)): sha for p, sha in manifest["bindings"].items()})
        statuses.append({"target": "pass_att", "panel": panel, "period": "2022", "trial": relative, "state": "PREDICTION_FROZEN"})
    campaign.write_json(output / "attempts.json", statuses)
    campaign.write_json(output / "forecast-freeze.json", {"bindings": bindings, "attempts_sha256": campaign.digest(output / "attempts.json")})
    campaign.score_report("fictional", output)
    report = json.loads((output / "median-boosting-report.json").read_text())
    assert len(report["historical_pooled"]) == 2 and len(report["context_ablations"]) == 2
    for entry in report["historical_pooled"]:
        primary = next(x for x in entry["paired"] if x["status"] == "primary")
        assert primary["comparator"] == "old_cdf" and primary["paired_rows"] == len(query) - 1
        assert primary["control_loss"] == pytest.approx(np.abs(query.pass_att.iloc[:-1] - 2.).mean())
    receipt = json.loads((output / "trials/pass_att/base/2022/old_cdf-source-comparison.json").read_text())
    assert receipt["candidate_offered_rows"] == len(query) and receipt["candidate_only_rows"] == 1
    assert (output / "trials/pass_att/base/2022/old_cdf-outer-source-audit.parquet").is_file()


def test_no_real_launch_without_technical_seal(tmp_path):
    path = tmp_path / "registry.json"
    campaign.write_json(path, {"state": "DRAFT"})
    with pytest.raises(ValueError, match="seal required"):
        campaign.run(path, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_monitor_enforces_two_threads_and_kills_process_group_at_rss_limit(tmp_path, monkeypatch):
    class FictionalProcess:
        pid, returncode = 91234567, None
        def poll(self):
            return self.returncode
    process, observed = FictionalProcess(), {}
    def launch(args, **kwargs):
        observed.update(args=args, **kwargs)
        return process
    def kill_group(proc):
        assert proc is process
        proc.returncode = -15
    monkeypatch.setattr(campaign.subprocess, "Popen", launch)
    monkeypatch.setattr(campaign, "proc_usage", lambda _: (campaign.LIMITS["memory_bytes"] + 1, 0))
    monkeypatch.setattr(campaign, "terminate_group", kill_group)
    result = campaign.monitored_process(["predict-trial", "fictional"], tmp_path, tmp_path,
        remaining_wall=60, remaining_cpu=90)
    assert result["reason"] == "RSS_LIMIT" and result["returncode"] == -15
    assert observed["start_new_session"] is True
    assert all(observed["env"][k] == "2" for k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"])
    with pytest.raises(FileExistsError):
        campaign.monitored_process(["predict-trial", "fictional"], tmp_path, tmp_path, remaining_wall=60, remaining_cpu=90)


def test_seal_binds_exact_model_source_panels_controls_and_approved_receipt(tmp_path):
    from nfl_lab.median_boosting import DESIGN, VERSION
    def binding(path):
        return {"path": str(path), "sha256": campaign.digest(path)}
    dummy = tmp_path / "fictional-input.txt"
    dummy.write_text("FICTIONAL source, never NFL data\n")
    inputs = {name: binding(dummy) for name in ["training_features", "query_features", "opportunities", "outcomes"]}
    categories = {name: {"state": "BLOCKED" if name == "fantasy_ppr" else "READY", "fictional_only": True} for name in campaign.TARGETS}
    code_names = ["median_boosting.py", "median_boosting_campaign.py", "median_boosting_evaluation.py", "cdf_engine.py", "cdf_campaign.py", "cdf_evaluation.py", "website_cdf.py", "website_cdf_evaluation.py"]
    root = Path(campaign.__file__).parent
    code = [binding(root / name) for name in code_names]
    prior = tmp_path / "prior.json"
    campaign.write_json(prior, {"categories": categories, "source": binding(dummy), "code_bindings": code})
    website = tmp_path / "website.json"
    campaign.write_json(website, {"categories": categories, "inputs": inputs})
    receipt = tmp_path / "source-approved.json"
    campaign.write_json(receipt, {"state": "APPROVED_FREE_TRAINING_AND_INFERENCE", "inputs": inputs})
    controls = {target: {panel: {period: {m: binding(dummy) for m in (["old_cdf"] if period == "website_week6" else ["old_cdf", "pooled", "recent"])}
        for period in campaign.PERIODS} for panel in ["base", "context"]} for target in campaign.TARGETS if target != "fantasy_ppr"}
    payload = {"registration_id": VERSION, "categories": categories, "model_design": DESIGN,
        "ensemble_design": campaign.ENSEMBLE_DESIGN, "comparisons": campaign.COMPARISONS,
        "budgets": campaign.LIMITS, "periods": list(campaign.PERIODS), "output_directory": str(tmp_path / "output"),
        "inputs": inputs, "prior_registry": binding(prior), "website_registry": binding(website),
        "source_contract": binding(receipt), "source_packet_mode": "joint_learner_source_reconstruction",
        "code_bindings": code, "prerequisite_bindings": [], "saved_controls": controls}
    plan = tmp_path / "plan.json"
    campaign.write_json(plan, dict(payload, state="REVIEW_READY_FICTIONAL"))
    sealed = dict(payload, state="SEALED_ROOT_AND_REVIEWER", seal={"integrator": "/root", "reviewer": "/root/fictional_readonly_reviewer",
        "decision": "PASS_BOUNDED_EXPOSED_RESEARCH_ONLY", "reviewed_plan_path": str(plan), "reviewed_plan_sha256": campaign.digest(plan)})
    registry = tmp_path / "sealed.json"
    campaign.write_json(registry, sealed)
    assert campaign.check_seal(registry)["registration_id"] == VERSION
    sealed["budgets"] = dict(campaign.LIMITS, maximum_candidate_fit_attempts=89)
    campaign.write_json(registry, sealed)
    with pytest.raises(ValueError, match="sealed payload differs"):
        campaign.check_seal(registry)
    sealed["budgets"] = campaign.LIMITS
    campaign.write_json(registry, sealed)
    dummy.write_text("changed fictional source\n")
    with pytest.raises(ValueError, match="sealed bytes changed"):
        campaign.check_seal(registry)
