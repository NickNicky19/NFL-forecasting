"""Fictional saved-aggregate exporter checks; no forecasts or error scoring."""
import hashlib
import json

import pytest

from nfl_lab.median_boosting_export import MetadataReader, PANELS, PERIODS, TARGETS, export_aggregates


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, indent=2) + "\n"
    path.write_text(body)
    return hashlib.sha256(body.encode()).hexdigest()


def fixture_run(tmp_path):
    run = tmp_path / "fictional-completed-run"
    run.mkdir(parents=True)
    completion = write(run / "completion.json", {"state": "COMPLETED_DESCRIPTIVE", "score_pass_consumed": True,
        "fit_attempts_consumed": 88, "reporting": {"returncode": 0}, "wall_seconds": 100, "cpu_seconds": 180})
    categories = {t: {"target": t, "state": "BLOCKED" if t == "fantasy_ppr" else "READY",
        "support": "bernoulli" if t == "anytime_td" else "count", "modeled_roles": ["QB"], "primary_roles": ["QB"],
        "panels": {"base": ["f_old"], "context": ["f_old", "f_context"]}, "player_id": "PRIVATE_PLAYER_POISON"} for t in TARGETS}
    write(run / "registry.json", {"categories": categories, "source_packet_mode": "joint_learner_source_reconstruction",
        "inputs": {"training_features": {"path": "/private/features.parquet", "sha256": "a" * 64}},
        "source_contract": {"path": "/private/APPROVED.json", "sha256": "b" * 64},
        "code_bindings": [{"path": "/private/median_boosting.py", "sha256": "c" * 64}],
        "player_id": "PRIVATE_PLAYER_POISON"})
    write(run / "environment.json", {"python": "fictional", "packages": {"fictional": "1"}, "threads": 2, "executable": "/private/python"})
    write(run / "forecast-freeze.json", {"bindings": {"trials/pass_att/base/website_week6/model/model.joblib": "d" * 64}})
    # These private byte artifacts are deliberately unreadable as data.
    (run / "model.joblib").write_bytes(b"must never read fitted bytes")
    (run / "rows.parquet").write_bytes(b"must never read player rows")
    metrics = {"rows": 5, "mae": 3., "rmse": 4., "bias_prediction_minus_actual": -1., "absolute_error_p90": 6.,
        "absolute_error_p95": 7., "absolute_error_max": 8., "player_id": "PRIVATE_PLAYER_POISON"}
    log = {"rows": 5, "natural_log_loss": None, "log_loss_state": "positive_infinity", "infinite_log_losses": 2,
        "finite_log_loss_sum": 1.5, "finite_log_loss_count": 3, "probability_clipping": "none", "player_id": "PRIVATE_PLAYER_POISON"}
    deciles = [{"bin": i, "lower_inclusive": i / 10, "upper": (i + 1) / 10, "upper_inclusive": i == 9,
        "rows": 5 if i == 0 else 0, "mean_probability": 0. if i == 0 else None, "observed_rate": .4 if i == 0 else None,
        "player_id": "PRIVATE_PLAYER_POISON"} for i in range(10)]
    def comparison(method, primary=False, binary=False):
        p = {"population": "all_original_offered", "offered_rows": 7, "supported_played_rows": 6,
            "paired_rows": 4 if method == "raw" else 5, "candidate_loss": 3., "control_loss": 2.,
            "delta_candidate_minus_control": 1., "improvement_pct": -50., "players": 4, "games": 2, "weeks": 1,
            "comparator": method, "status": "primary" if primary else "secondary", "primary_loss": "brier" if binary else "mae",
            "candidate_point": "point", "candidate_point_metrics": metrics, "control_literal_point_metrics": metrics,
            "player_id": "PRIVATE_PLAYER_POISON"}
        if binary:
            p["paired_binary"] = {"candidate": log, "control": dict(log, log_loss_state="finite", natural_log_loss=.3),
                "candidate_reliability_deciles": deciles, "control_reliability_deciles": deciles}
        return p
    def report(target, panel, period, family="pure", pooled=False):
        binary = target == "anytime_td"
        methods = ["old_cdf", "pooled", "recent"] if pooled or period != "website_week6" else ["website", "raw", "simple", "old_cdf"]
        pairs = [comparison(m, family == "pure" and ((pooled and m == "old_cdf") or (period == "website_week6" and m == "website")), binary) for m in methods]
        value = {"target": target, "panel": panel, "method_family": family,
            "paired": pairs, "summary": {"offered_rows": 7, "scored_rows": 6, "missing_points": 0, "players": 4, "games": 2, "weeks": 1,
                "point_metrics": metrics, "outcome_states": {"played_zero": 1, "played_nonzero": 5, "unknown": 1}, **(dict(log, reliability_deciles=deciles) if binary else {})},
            "source_comparisons": [{"version": "fictional", "method": "old_cdf", "candidate_offered_rows": 7,
                "retained_control_offered_rows": 8, "common_rows": 6, "candidate_only_rows": 1, "control_only_rows": 2,
                "participation_qualification_changes": 1, "raw_actual_conflicts_quarantined": 0,
                "retained_source_binding": {"path": "/private/old-cdf.parquet", "sha256": "e" * 64}, "player_id": "PRIVATE_PLAYER_POISON"}],
            "subgroups": [{"dimension": "fallback", "value": "cold_start_role_prior", "offered_rows": 1},
                {"dimension": "player_id", "value": "PRIVATE_PLAYER_POISON", "offered_rows": 1}],
            "player_id": "PRIVATE_PLAYER_POISON"}
        if pooled:
            value.update(compared_complete_years=[2022, 2023, 2024], excluded_years=[])
            value["paired"][0]["intervals"] = [{"cluster": "week", "replicates": 500, "seed": 1701,
                "interval": [-.2, 2.], "paired_rows": 5, "player_id": "PRIVATE_PLAYER_POISON"}]
        return value
    primaries, cells, pooled_reports = [], [], []
    for t in TARGETS:
        for p in PANELS:
            supported = t in {"pass_att", "anytime_td"} and p == "base"
            blocked = t == "fantasy_ppr"
            historical = report(t, p, "pooled2022-2024", pooled=True) if supported else None
            website = report(t, p, "website_week6") if supported else None
            if historical:
                pooled_reports.append(historical)
            for period, saved in [("pooled2022-2024", historical), ("website_week6", website)]:
                primaries.append({"target": t, "panel": p, "period": period, "method_family": "pure",
                    "state": "BLOCKED_CATEGORY_CONTRACT" if blocked else "SCORED_DESCRIPTIVE" if supported else "FAILED_OR_SKIPPED_RETAINED",
                    "primary": next((x for x in saved["paired"] if x["status"] == "primary"), None) if saved else None})
            for period in PERIODS:
                for family in (["pure", "website_equalweight_secondary"] if period == "website_week6" else ["pure"]):
                    slot = {"target": t, "panel": p, "period": period, "method_family": family,
                        "state": "BLOCKED_CATEGORY_CONTRACT" if blocked else "SCORED_DESCRIPTIVE" if supported else "FAILED_CONSUMED"}
                    if supported:
                        saved = report(t, p, period, family)
                        name = "report.json" if family == "pure" else "ensemble-report.json"
                        slot["report_sha256"] = write(run / f"trials/{t}/{p}/{period}/{name}", saved)
                    cells.append(slot)
    write(run / "median-boosting-report.json", {"registration_id": "fictional", "source_packet_mode": "joint_learner_source_reconstruction",
        "primary_slots": primaries, "slots": cells, "historical_pooled": pooled_reports, "context_ablations": [],
        "model_design": {"numeric_estimator": "HistGradientBoostingRegressor", "numeric_loss": "absolute_error", "parameters": {"max_iter": 150},
            "training_labels": ["PRIVATE_PLAYER_POISON"]}, "ensemble_design": {"weight_website": .5, "weight_candidate": .5},
        "source_qualification": {"private_note": "PRIVATE_PLAYER_POISON"}, "comparisons": {}, "budgets": {"maximum_candidate_fit_attempts": 88}})
    return run, completion


def test_all_fixed_slots_losers_exact_cohorts_and_private_hashes_survive_export(tmp_path):
    run, receipt = fixture_run(tmp_path)
    output = tmp_path / "public-export"
    manifest = export_aggregates(run, output, receipt)
    public = json.loads((output / "aggregate-report.json").read_text())
    assert len(public["primary_matrix"]) == 48 and len(public["attempt_slots"]) == 96 and len(public["cell_matrix"]) == 120
    assert sum(x["method_family"] == "website_equalweight_secondary" for x in public["cell_matrix"]) == 24
    assert sum(x["target"] == "fantasy_ppr" and x["state"] == "BLOCKED_CATEGORY_CONTRACT" for x in public["primary_matrix"]) == 4
    p = next(x for x in public["primary_matrix"] if x["target"] == "pass_att" and x["panel"] == "base" and x["period"] == "website_week6")
    assert p["primary"]["improvement_pct"] == -50.
    cell = next(x for x in public["cell_matrix"] if x["target"] == "pass_att" and x["panel"] == "base" and x["period"] == "website_week6" and x["method_family"] == "pure")
    assert next(x for x in cell["aggregate"]["paired"] if x["comparator"] == "raw")["paired_rows"] == 4
    assert cell["model_and_forecast_hashes"]["model/model.joblib"] == "d" * 64
    assert public["historical_pooled"][0]["paired"][0]["intervals"][0]["interval"] == [-.2, 2.]
    assert all(manifest[k] == 0 for k in ["row_data_reads", "model_data_reads", "new_fits", "new_forecasts", "new_scores"])
    for artifact in output.iterdir():
        assert "PRIVATE_PLAYER_POISON" not in artifact.read_text() and "/private/" not in artifact.read_text()
    assert set(p.name for p in output.iterdir()) == {"aggregate-report.json", "aggregate-report.md", "hash-manifest.json"}
    assert "RMSE / bias / p90 AE" in (output / "aggregate-report.md").read_text()


def test_unsuccessful_or_wrong_receipt_blocks_before_any_accuracy_read(tmp_path, monkeypatch):
    run = tmp_path / "incomplete"
    run.mkdir()
    sha = write(run / "completion.json", {"state": "INCOMPLETE_RETAINED_NO_RESTART"})
    (run / "median-boosting-report.json").write_text("unreadable accuracy poison")
    reads, original = [], MetadataReader.read
    def tracked(self, relative, *args, **kwargs):
        reads.append(str(relative))
        return original(self, relative, *args, **kwargs)
    monkeypatch.setattr(MetadataReader, "read", tracked)
    with pytest.raises(ValueError, match="completed-run receipt"):
        export_aggregates(run, tmp_path / "public", sha)
    assert reads == ["completion.json"] and not (tmp_path / "public").exists()
    with pytest.raises(ValueError, match="hash changed"):
        export_aggregates(run, tmp_path / "public", "0" * 64)


def test_changed_detailed_aggregate_hash_and_forbidden_row_model_reads_rejected(tmp_path):
    run, sha = fixture_run(tmp_path)
    reader = MetadataReader(run)
    for name in ["rows.parquet", "model.joblib", "model/manifest.json", "../outside.json"]:
        with pytest.raises(ValueError, match="aggregate/receipt JSON"):
            reader.read(name)
    path = run / "trials/pass_att/base/2022/report.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="hash changed"):
        export_aggregates(run, tmp_path / "public", sha)


def test_missing_slots_and_non_create_only_destination_rejected(tmp_path):
    run, sha = fixture_run(tmp_path)
    with pytest.raises(ValueError, match="outside immutable"):
        export_aggregates(run, run / "export", sha)
    path = run / "median-boosting-report.json"
    top = json.loads(path.read_text())
    top["primary_slots"].pop()
    write(path, top)
    with pytest.raises(ValueError, match="48 primary"):
        export_aggregates(run, tmp_path / "public", sha)
    run2, sha2 = fixture_run(tmp_path / "second")
    output = tmp_path / "valid-export"
    export_aggregates(run2, output, sha2)
    with pytest.raises(ValueError, match="new directory"):
        export_aggregates(run2, output, sha2)


def test_binary_logs_calibration_source_lineage_and_parameter_schema_are_copied_only(tmp_path):
    run, sha = fixture_run(tmp_path)
    output = tmp_path / "public"
    export_aggregates(run, output, sha)
    public = json.loads((output / "aggregate-report.json").read_text())
    binary = next(x for x in public["primary_matrix"] if x["target"] == "anytime_td" and x["panel"] == "base" and x["period"] == "website_week6")["primary"]
    assert binary["paired_binary"]["candidate"]["log_loss_state"] == "positive_infinity"
    assert binary["paired_binary"]["candidate"]["finite_log_loss_count"] == 3
    assert len(binary["paired_binary"]["candidate_reliability_deciles"]) == 10
    source = public["historical_pooled"][0]["source_comparisons"][0]
    assert (source["candidate_offered_rows"], source["retained_control_offered_rows"], source["candidate_only_rows"], source["control_only_rows"]) == (7, 8, 1, 2)
    assert public["model_parameter_schema"]["parameters"]["max_iter"] == 150
    assert public["source_packet_mode"] == "joint_learner_source_reconstruction"
    assert public["new_qualified_replacements"] == [] and public["technical_replay_performed_by_exporter"] is False
