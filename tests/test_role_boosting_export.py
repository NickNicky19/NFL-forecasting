"""Fictional metadata fixtures only; no NFL rows, fitted bytes or model calls."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nfl_lab.role_boosting_export import (MetadataReader, PERIODS, TARGETS, VARIANTS, VERSION,
    digest_bytes, export_aggregates, package_kind)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, allow_nan=False).encode()
    path.write_bytes(body)
    return digest_bytes(body)


def fictional_run(tmp_path):
    run = tmp_path / "fictional-completed"
    run.mkdir(parents=True)
    poison = "PRIVATE_POISON"
    roles = {t: ["QB"] if t.startswith("pass_") else ["RB", "WR", "TE"] for t in TARGETS}
    categories = {t: {"target": t, "state": "BLOCKED_LABEL_CONTRACT" if t == "fantasy_ppr" else "READY",
        "support": "bernoulli" if t == "anytime_td" else "fractional_ppr" if t == "fantasy_ppr" else "count",
        "modeled_roles": roles[t], "primary_roles": roles[t], "panels": {"base": ["f_earlier"]}, "player_id": poison} for t in TARGETS}
    write(run / "registry.json", {"registration_id": VERSION, "categories": categories,
        "study_source_relation": "same_exact_parent_hgb_input_packet", "ensemble_design": {"enabled": False, "additional_fits": 0},
        "inputs": {k: {"path": "/private/" + poison + ".parquet", "sha256": "a" * 64, "bytes": 3} for k in ("training_features", "query_features", "opportunities", "outcomes")},
        "parent_boosting_registry": {"path": "/private/" + poison + ".json", "sha256": "b" * 64},
        "code_bindings": [{"path": "/private/" + poison + ".py", "sha256": "c" * 64}],
        "cumulative_budget_amendment": {"prior_audited_completed_fit_lower_bound": 632, "new_maximum_estimator_fit_attempts": 136}})
    write(run / "environment.json", {"threads": 2, "executable": "/private/" + poison, "packages": {poison: poison}})
    (run / "rows.parquet").write_bytes(b"forbidden football row poison")
    (run / "model.joblib").write_bytes(b"forbidden fitted model poison")
    metric = {"rows": 5, "mae": 3., "mse": 16., "rmse": 4., "bias_prediction_minus_actual": -1., "absolute_error_p95": 8., "player_id": poison}
    log = {"rows": 5, "natural_log_loss": None, "log_loss_state": "positive_infinity", "infinite_log_losses": 1,
           "finite_log_loss_sum": 2., "finite_log_loss_count": 4, "probability_clipping": "none", "game_id": poison}
    bins = [{"bin": i, "rows": 5 if i == 0 else 0, "mean_probability": 0. if i == 0 else None,
             "observed_rate": .2 if i == 0 else None, "upper_inclusive": i == 9, "player_id": poison} for i in range(10)]

    def comparison(method, population, primary=False, binary=False, period="2022"):
        item = {"population": population, "comparator": method, "status": "primary" if primary else "secondary",
            "primary_loss": "brier" if binary else "mae", "offered_rows": 7, "supported_played_rows": 6,
            "paired_rows": 4 if method == "raw" else 5, "candidate_missing_rows": 0, "control_missing_rows": 1 if method == "raw" else 0,
            "candidate_loss": 3., "control_loss": 2., "delta_candidate_minus_control": 1., "improvement_pct": -50.,
            "players": 4, "games": 2, "weeks": 1, "candidate_point_metrics": metric, "control_literal_point_metrics": metric,
            "point": 999., "actual": -999., "player_id": poison, "candidate_point": "/private/" + poison}
        if period != "website_week6":
            item["intervals"] = [{"cluster": "week", "replicates": 500, "seed": 1701, "interval": [-.1, 2.],
                                  "mean_delta_candidate_minus_control": 1., "primary_roles_only": population == "prior_primary_roles", "player_id": poison}]
        if binary:
            item["paired_binary"] = {"candidate": log, "control": log, "candidate_reliability_deciles": bins, "control_reliability_deciles": bins}
        return item

    def report(target, variant, period):
        historical = period != "website_week6"
        methods = ["old_hgb", "old_cdf", "pooled", "recent"] if historical else ["website", "old_hgb", "old_cdf", "raw", "simple"]
        paired = [comparison(m, p, primary=(period == "pooled2022-2024" and m == "old_hgb" and p == "prior_primary_roles") or
                             (not historical and m == "website" and p == "all_original_offered"),
                             binary=target == "anytime_td", period=period)
                  for m in methods for p in ("all_original_offered", "prior_primary_roles")]
        result = {"target": target, "variant": variant, "period": period, "paired": paired,
            "summary": {"offered_rows": 7, "scored_rows": 6, "players": 4, "games": 2, "weeks": 1, "point_metrics": metric,
                        "outcome_states": {"played_zero": 2, "played_nonzero": 4, "unknown": 1, poison: 7}},
            "role_prior": {"offered_rows": 7, "point_metrics": metric},
            "common_all_controls": [dict(paired[0], status="secondary_common_all_controls", finite_common_rows=3)],
            "source_comparisons": [{"method": "old_cdf", "candidate_offered_rows": 7, "retained_control_offered_rows": 9,
                                    "common_rows": 6, "candidate_only_rows": 1, "control_only_rows": 3,
                                    "retained_source_binding": {"path": "/private/" + poison, "sha256": "d" * 64}}],
            "subgroups": [{"dimension": "team", "value": "BUF", "games": 2, "point_metrics": metric},
                          {"dimension": "fallback", "value": poison, "offered_rows": 1},
                          {"dimension": "player_id", "value": poison}],
            "comparator_availability": {m: "N/A_not_recorded_for_exact_panel" if historical else "literal_original_offers; exact paired/missing counts in each cell" for m in ("website", "raw", "simple")},
            "private_note": poison}
        if period == "pooled2022-2024":
            result.update(compared_complete_years=[2022, 2023, 2024], excluded_years=[])
        return result

    supported = {"pass_att", "anytime_td"}
    slots, primaries, pooled, freezes, common, ablations = [], [], [], {}, [], []
    for target in TARGETS:
        for variant in VARIANTS:
            for period in PERIODS:
                kind = package_kind(target, variant)
                slot = {"target": target, "variant": variant, "period": period, "kind": kind,
                        "state": "BLOCKED_CATEGORY_CONTRACT" if target == "fantasy_ppr" else "SCORED_DESCRIPTIVE" if target in supported else "FAILED_CONSUMED",
                        "fit_attempts": 1 if target in supported and kind == "model" else 0,
                        "trial": "/private/" + poison, "reason": "/private/" + poison}
                if target == "fantasy_ppr":
                    slot["blocked_subfit_slots"] = 1 if variant == "A" else 5
                if target in supported:
                    detail = report(target, variant, period)
                    slot["report_sha256"] = write(run / f"trials/{target}/{variant}/{period}/report.json", detail)
                    freezes[f"trials/{target}/{variant}/{period}/candidate-frozen.parquet"] = "e" * 64
                    for pop in ("all_original_offered", "prior_primary_roles"):
                        common.append(dict(comparison("old_hgb", pop, period=period), target=target, variant=variant, period=period,
                                           status="secondary_A_B_all_controls_common_cohort", finite_common_rows=3))
                slots.append(slot)
            for period in ("pooled2022-2024", "website_week6"):
                detail = report(target, variant, period) if target in supported else None
                if detail and period == "pooled2022-2024":
                    pooled.append(detail)
                primaries.append({"target": target, "variant": variant, "period": period,
                    "state": "BLOCKED_CATEGORY_CONTRACT" if target == "fantasy_ppr" else "SCORED_DESCRIPTIVE" if detail else "PARTIAL_OR_FAILED_RETAINED",
                    "primary": next((x for x in detail["paired"] if x["status"] == "primary"), None) if detail else None})
        if target in supported:
            for period in PERIODS:
                ablations.append(dict(comparison("old_hgb", "all_original_offered", period=period), target=target, period=period, comparison="B_minus_A"))
    fit_attempts = sum(s["fit_attempts"] for s in slots)
    write(run / "forecast-freeze.json", {"bindings": freezes, "fit_attempts": fit_attempts, "packages": 96})
    report_sha = write(run / "role-boosting-report.json", {"registration_id": VERSION,
        "study_source_relation": "same_exact_parent_hgb_input_packet", "slots": slots, "primary_slots": primaries,
        "historical_pooled": pooled, "role_loss_ablations": ablations, "common_cohort_diagnostics": common,
        "comparator_availability": {p: {m: "N/A_not_recorded_for_exact_panel" if p != "website_week6" else "literal_original_offers; exact paired/missing counts in each cell" for m in ("website", "raw", "simple")} for p in PERIODS},
        "coherence": [{"variant": v, "period": p, "audit": a, "offered_union_rows": 7, "common_available_rows": 5,
                       "missing_component_rows": 2, "mean_point_gap": -1., "max_absolute_gap": 2., "positive_gap_rows": 1,
                       "absent_or_missing_by_target": {"pass_att": 2}, "game_id": poison}
                      for v in VARIANTS for p in PERIODS for a in ("completion_minus_attempt", "direct_combined_minus_components")],
        "planned_packages": 96, "planned_new_model_packages": 48, "planned_alias_packages": 40, "blocked_ppr_packages": 8,
        "primary_contrast_slots": 48, "blocked_ppr_primary_contrasts": 4, "maximum_estimator_attempts": 136, "score_passes": 1,
        "model_design": {"parameters": {"max_iter": 150, "early_stopping": False}, "threads": 2, "minimum_modeled_rows": 60, "private_training_label": poison},
        "budgets": {"maximum_candidate_fit_attempts": 136}, "source_qualification": {"private_note": poison}})
    completion_sha = write(run / "completion.json", {"state": "COMPLETED_DESCRIPTIVE", "reporting": {"returncode": 0},
        "score_pass_consumed": True, "fit_attempts_consumed": fit_attempts, "statuses": slots})
    return run, completion_sha, report_sha


def test_complete_matrix_losers_distinct_cohorts_and_private_fields(tmp_path):
    run, completion, report = fictional_run(tmp_path)
    output = tmp_path / "public"
    receipt = export_aggregates(run, output, completion, report)
    public = json.loads((output / "aggregate-report.json").read_text())
    assert len(public["package_matrix"]) == 96 and len(public["primary_matrix"]) == 48
    assert len(public["coherence"]) == 16
    assert sum(x["target"] == "fantasy_ppr" and x["state"] == "BLOCKED_CATEGORY_CONTRACT" for x in public["package_matrix"]) == 8
    assert sum(x["reused_alias"] for x in public["package_matrix"]) == 40
    primary = next(x["primary"] for x in public["primary_matrix"] if x["target"] == "pass_att" and x["variant"] == "A" and x["period"] == "pooled2022-2024")
    assert primary["population"] == "prior_primary_roles" and primary["comparator"] == "old_hgb" and primary["improvement_pct"] == -50.
    assert primary["candidate_point_metrics"]["mse"] == 16. and primary["candidate_point_metrics"]["absolute_error_p95"] == 8.
    website = next(x for x in public["package_matrix"] if x["target"] == "pass_att" and x["variant"] == "A" and x["period"] == "website_week6")
    assert next(p for p in website["aggregate"]["paired"] if p["comparator"] == "raw")["paired_rows"] == 4
    assert website["aggregate"]["source_comparisons"][0]["control_only_rows"] == 3
    assert public["common_cohort_diagnostics"][0]["finite_common_rows"] == 3
    assert public["common_cohort_diagnostics"][0]["status"] == "secondary_A_B_all_controls_common_cohort"
    binary = next(x["primary"] for x in public["primary_matrix"] if x["target"] == "anytime_td" and x["variant"] == "A" and x["period"] == "website_week6")
    assert binary["paired_binary"]["candidate"]["log_loss_state"] == "positive_infinity"
    assert all(receipt[k] == 0 for k in ("row_data_reads", "model_data_reads", "new_fits", "new_forecasts", "new_scores", "resampling_passes"))
    for path in output.iterdir():
        text = path.read_text()
        assert "PRIVATE_POISON" not in text and "/private/" not in text
        assert '"player_id"' not in text and '"game_id"' not in text and '"point"' not in text and '"actual"' not in text
        assert ".parquet" not in text and ".joblib" not in text and "trials/" not in text
    with pytest.raises(ValueError, match="new directory"):
        export_aggregates(run, output, completion, report)


def test_completion_gate_and_report_pin_precede_detailed_accuracy_reads(tmp_path, monkeypatch):
    run, completion, report = fictional_run(tmp_path)
    original = (run / "completion.json").read_bytes()
    bad = write(run / "completion.json", {"state": "INCOMPLETE_RETAINED_NO_RESTART"})
    calls, original_read = [], MetadataReader.read
    def read(self, relative, *args, **kwargs):
        calls.append(str(relative))
        return original_read(self, relative, *args, **kwargs)
    monkeypatch.setattr(MetadataReader, "read", read)
    with pytest.raises(ValueError, match="completed-run receipt"):
        export_aggregates(run, tmp_path / "public", bad, report)
    assert calls == ["completion.json"]
    (run / "completion.json").write_bytes(original)
    calls.clear()
    with pytest.raises(ValueError, match="hash changed"):
        export_aggregates(run, tmp_path / "public", completion, "0" * 64)
    assert calls == ["completion.json", "role-boosting-report.json"]
    assert not (tmp_path / "public").exists()


def test_tampered_detail_missing_slots_and_forbidden_metadata_paths(tmp_path):
    run, completion, report = fictional_run(tmp_path)
    reader = MetadataReader(run)
    for name in ("rows.parquet", "model.joblib", "model/manifest.json", "coherence/rows.json", "../outside.json"):
        with pytest.raises(ValueError, match="allowlisted aggregate"):
            reader.read(name)
    path = run / "trials/pass_att/A/2022/report.json"
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="hash changed"):
        export_aggregates(run, tmp_path / "public", completion, report)
    path.write_bytes(original)
    top = json.loads((run / "role-boosting-report.json").read_text())
    top["slots"].pop()
    changed = write(run / "role-boosting-report.json", top)
    with pytest.raises(ValueError, match="96 package statuses"):
        export_aggregates(run, tmp_path / "public", completion, changed)
    assert not (tmp_path / "public").exists()


def test_export_module_imports_only_metadata_dependencies():
    code = "import sys; import nfl_lab.role_boosting_export; forbidden={'numpy','pandas','sklearn','joblib','nfl_lab.role_boosting','nfl_lab.role_boosting_campaign'}; assert not forbidden.intersection(sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
