"""Fictional aggregate-only transfer and same-cohort difference checks."""
import copy
import hashlib
import json

import pytest

from nfl_lab.recorded_thresholds_export import LANES, MetadataReader, TARGETS, export_aggregates


METHODS = ["raw", "website", "recent", "pooled", "original_692_reconstruction", "cdf_base_median", "cdf_context_median",
    "cdf_website_blend_base", "cdf_website_blend_context", "hgb_base_point", "hgb_context_point", "hgb_website_blend_base", "hgb_website_blend_context"]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, indent=2) + "\n"
    path.write_text(body)
    return hashlib.sha256(body.encode()).hexdigest()


def fixture(tmp_path):
    root, run = tmp_path / "fictional", tmp_path / "fictional/run"
    run.mkdir(parents=True)
    approved = {method: list(TARGETS) for method in METHODS}
    approved["original_692_reconstruction"] = list(TARGETS[:4])
    def metrics(method, target, n=5):
        supported = target in approved[method] and target not in TARGETS[-2:]
        n = n if supported else 0
        baseline = method == "website"
        miss, mae = (.4, 4.) if baseline else (.6, 5.) if method == "raw" else (.2, 3.)
        if target == "pass_int" and baseline:
            miss, mae = 0., 0.
        return {"offered_rows": 60, "scored_rows": n, "games": 2 if n else 0, "players": 3 if n else 0, "weeks": 1 if n else 0,
            "point_mae": mae if n else None, "point_rmse": 5. if n else None, "point_bias_prediction_minus_actual": 1. if n else None,
            "point_absolute_error_p90": 8. if n else None, "point_absolute_error_p95": 9. if n else None, "point_absolute_error_max": 10. if n else None,
            "three_way_accuracy": 1 - miss if n else None, "three_way_misclassification_rate": miss if n else None,
            "three_way_correct_rows": 3 if n else 0, "actual_equal_threshold_rows": 0, "actual_equal_threshold_rate": 0. if n else None,
            "prediction_equal_threshold_rows": 0, "nonpush_secondary_rows": n, "nonpush_secondary_accuracy": 1 - miss if n else None,
            "nonpush_prediction_equal_rows": 0, "eligibility_states": {"eligible": n}, "source_coverage": {"both": 60},
            "player_id": "PRIVATE_ROW_POISON", "actual": 9999, "line": 42.5}
    slots = [{"target": t, "method": m, **metrics(m, t, n=58)} for t in TARGETS for m in METHODS]
    common = {m: ["raw", "website", "recent", "pooled"] for m in METHODS if m != "website"}
    comparisons = []
    for lane in LANES:
        for target in TARGETS:
            for candidate in METHODS:
                if candidate == "website":
                    continue
                controls = common[candidate] if lane == "declared_common_controls" else ["website"]
                n = 5 if target in approved[candidate] and target not in TARGETS[-2:] else 0
                methods = {m: metrics(m, target, n=n) for m in dict.fromkeys([candidate] + controls)}
                comparisons.append({"target": target, "candidate": candidate, "controls": controls, "cohort": lane,
                    "common_rows": n, "methods": methods, "cohort_semantics": "same fictional offers", "player_id": "PRIVATE_ROW_POISON"})
    groups = [{"target": "pass_yd", "method": "raw", "field": "source_coverage", "group": f"fictional_group_{i}", **metrics("raw", "pass_yd")}
        for i in range(8998)]
    plan = {"registration_id": "fictional", "methods": METHODS,
        "inputs": {"source_manifest": {"path": "/private/source03-manifest.json", "sha256": "a" * 64}},
        "population": {"offered_rows": 2083, "player_contexts": 396, "games": 13, "weeks": 1},
        "primary": {"metric": "three_way_misclassification_rate"}, "secondary": ["pairwise SITE"], "cutoffs": "literal clocks only",
        "budget_accounting": "old budgets spent", "correction_policy": "no restart", "source_wording": "provider-fed references",
        "code": {"evaluator": {"path": "/private/evaluator.py", "sha256": "b" * 64}}, "source_bindings": [],
        "player_id": "PRIVATE_ROW_POISON"}
    plan_path = root / "plan.json"
    plan_sha = write(plan_path, plan)
    seal_path = root / "seal.json"
    seal_sha = write(seal_path, {"decision": "PASS_FICTIONAL", "plan": {"path": str(plan_path), "sha256": plan_sha}})
    freeze_sha = write(run / "forecast-freeze.json", {"plan_sha256": plan_sha, "seal_sha256": seal_sha, "rows": 27079})
    report = {"registration_id": "fictional", "evidence": "fictional aggregate transfer only", "plan_sha256": plan_sha,
        "source_manifest_sha256": "a" * 64, "forecast_freeze_sha256": freeze_sha,
        "metrics": {"declared_methods": {m: m for m in METHODS}, "reference_method": "website", "common_controls": common,
            "supported_targets_by_method": approved, "method_target_summaries": slots, "comparisons": comparisons},
        "grouped_summaries": groups, "all_12_qualification": "WAITING_FOR_EVIDENCE", "uncertainty": "one exposed week, no intervals",
        "source_market_counts": [{"target": "pass_yd", "threshold_group": "reference", "line_from": "dk", "rows": 5, "player_id": "PRIVATE_ROW_POISON"}],
        "outcome_state_coverage": [{"target": "pass_yd", "threshold_group": "reference", "participation_state": "unknown", "outcome_state": "unknown", "rows": 2}],
        "bounds": {"new_NFL_fits": 0, "bootstrap_replicates": 0}, "scored_rows_sha256": "c" * 64, "player_id": "PRIVATE_ROW_POISON"}
    report_sha = write(run / "report.json", report)
    completion = {"state": "COMPLETED_DESCRIPTIVE", "global_score_passes": 1, "new_fits": 0, "new_model_predictions": 0,
        "report_sha256": report_sha, "forecast_freeze_sha256": freeze_sha, "frozen_direction_rows": 27079}
    completion_sha = write(run / "completion.json", completion)
    (run / "rows.parquet").write_bytes(b"do not open player data")
    return run, plan_path, seal_path, completion_sha, report_sha


def exported(tmp_path):
    run, plan, seal, completion, report = fixture(tmp_path)
    output = tmp_path / "public"
    manifest = export_aggregates(run, plan, seal, output, completion, report)
    return run, output, manifest, json.loads((output / "aggregate-report.json").read_text())


def test_complete_transfer_retains_all_groups_losers_and_same_cohort_named_differences(tmp_path):
    _, output, manifest, public = exported(tmp_path)
    assert len(public["method_target_summaries"]) == 156 and len(public["comparisons"]) == 288 and len(public["grouped_summaries"]) == 8998
    primary = [c for c in public["comparisons"] if c["cohort"] == "declared_common_controls"]
    assert sum(c["target"] in TARGETS[:10] for c in primary) == 120
    assert sum(c["market_status"].startswith("NONMARKET") for c in primary) == 24
    assert sum(c["market_status"] == "STRUCTURAL_METHOD_TARGET_UNSUPPORTED" for c in primary) == 6
    loss = next(c for c in primary if c["target"] == "pass_yd" and c["candidate"] == "raw")
    against_site = next(x for x in loss["candidate_vs_named_baselines"] if x["baseline"] == "website")
    assert against_site["misclassification_delta_candidate_minus_baseline"] == pytest.approx(.2)
    assert against_site["relative_misclassification_improvement_pct"] == pytest.approx(-50.)
    assert against_site["accuracy_difference_percentage_points"] == pytest.approx(-20.)
    assert against_site["point_mae_delta_candidate_minus_baseline"] == 1 and against_site["relative_point_mae_improvement_pct"] == -25.
    assert len(loss["candidate_vs_named_baselines"]) == 4
    assert public["population"]["saved_supported_SITE_category_rows"] == 580
    assert public["population"]["saved_raw_SITE_recent_pooled_common_category_rows"] == 50
    assert public["numeric_threshold_probabilities"] == "N/A" and public["new_qualified_replacements"] == []
    assert all(manifest[k] == 0 for k in ["row_reads", "model_reads", "new_fits", "new_model_predictions", "new_score_passes", "new_resamples"])
    for file in output.iterdir():
        text = file.read_text()
        assert "PRIVATE_ROW_POISON" not in text and "/private/" not in text
        assert '"player_id"' not in text and '"actual"' not in text and '"line"' not in text
    markdown = (output / "aggregate-report.md").read_text()
    assert "All120 numeric primary comparisons" in markdown and "All24 primary nonmarket blocks" in markdown


def test_incomplete_or_wrong_completion_blocks_before_accuracy_reads(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    completion = write(run / "completion.json", {"state": "FAILED"})
    (run / "report.json").write_text("must never open accuracy JSON")
    calls, original = [], MetadataReader.read
    def tracked(self, name, *args, **kwargs):
        calls.append(name)
        return original(self, name, *args, **kwargs)
    monkeypatch.setattr(MetadataReader, "read", tracked)
    with pytest.raises(ValueError, match="completion required"):
        export_aggregates(run, tmp_path / "absent-plan.json", tmp_path / "absent-seal.json", tmp_path / "public", completion, "a" * 64)
    assert calls == ["completion"] and not (tmp_path / "public").exists()
    with pytest.raises(ValueError, match="pinned metadata hash"):
        export_aggregates(run, "plan.json", "seal.json", tmp_path / "public", "0" * 64, "a" * 64)


def test_hash_chain_and_same_cohort_mismatch_are_rejected(tmp_path):
    run, plan, seal, completion, report_sha = fixture(tmp_path)
    plan.write_text(plan.read_text() + " ")
    with pytest.raises(ValueError, match="pinned metadata hash"):
        export_aggregates(run, plan, seal, tmp_path / "public", completion, report_sha)
    run, plan, seal, completion, report_sha = fixture(tmp_path / "second")
    report = json.loads((run / "report.json").read_text())
    report["metrics"]["comparisons"][0]["methods"]["website"]["scored_rows"] = 4
    new_report_sha = write(run / "report.json", report)
    done = json.loads((run / "completion.json").read_text()); done["report_sha256"] = new_report_sha
    new_completion = write(run / "completion.json", done)
    with pytest.raises(ValueError, match="different cohorts"):
        export_aggregates(run, plan, seal, tmp_path / "public", new_completion, new_report_sha)


def test_zero_baselines_empty_cells_and_all_nonmarket_blocks_stay_explicit(tmp_path):
    _, _, _, public = exported(tmp_path)
    comparison = next(c for c in public["comparisons"] if c["target"] == "pass_int" and c["candidate"] == "raw")
    against = next(x for x in comparison["candidate_vs_named_baselines"] if x["baseline"] == "website")
    assert against["relative_misclassification_improvement_pct"] is None and against["relative_point_mae_improvement_pct"] is None
    assert against["misclassification_delta_candidate_minus_baseline"] == .6
    empty = next(c for c in public["comparisons"] if c["target"] == "rec_yd" and c["candidate"] == "original_692_reconstruction")
    assert empty["common_rows"] == 0 and all(x["point_mae_delta_candidate_minus_baseline"] is None for x in empty["candidate_vs_named_baselines"])
    assert all(c["common_rows"] == 0 for c in public["comparisons"] if c["target"] in ["fantasy_ppr", "anytime_td"])


def test_create_only_paths_forbidden_reads_and_matrix_loss_rejected(tmp_path):
    run, plan, seal, completion, report = fixture(tmp_path)
    reader = MetadataReader(run, plan, seal)
    with pytest.raises(ValueError, match="declared aggregate"):
        reader.read("rows.parquet")
    with pytest.raises(ValueError, match="new directory"):
        export_aggregates(run, plan, seal, run / "public", completion, report)
    output = tmp_path / "public"
    export_aggregates(run, plan, seal, output, completion, report)
    with pytest.raises(ValueError, match="new directory"):
        export_aggregates(run, plan, seal, output, completion, report)
    saved = json.loads((run / "report.json").read_text()); saved["metrics"]["comparisons"].pop()
    new_report = write(run / "report.json", saved)
    done = json.loads((run / "completion.json").read_text()); done["report_sha256"] = new_report
    new_completion = write(run / "completion.json", done)
    with pytest.raises(ValueError, match="288"):
        export_aggregates(run, plan, seal, tmp_path / "second-public", new_completion, new_report)
