"""Saved fictional aggregate exports only; no fitting or score calculation."""
import copy
import hashlib
import json

import pytest

from nfl_lab.website_cdf_export import TARGETS, export_aggregates


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, indent=2) + "\n"
    path.write_text(body)
    return hashlib.sha256(body.encode()).hexdigest()


def fictional_run(tmp_path):
    run = tmp_path / "fictional-completed-run"
    run.mkdir()
    completed_hash = write(run / "completion.json", {"state": "COMPLETED_DESCRIPTIVE"})
    registry = {"categories": {target: {"target": target, "state": "READY", "panels": {"base": ["f_old"], "context": ["f_old", "f_context"]}} for target in TARGETS},
        "inputs": {"training_features": {"path": "/private/train.parquet", "sha256": "a" * 64}},
        "source_bindings": {}, "code_bindings": [{"path": "/private/engine.py", "sha256": "b" * 64}],
        "private_poison": {"player_id": "DO_NOT_EXPORT_PLAYER_ROW"}}
    write(run / "registry.json", registry)
    freeze_hash = write(run / "forecast-freeze.json", {"bindings": {"trials/pass_att/base/model/model.joblib": "c" * 64}})
    write(run / "environment.json", {"python": "fictional", "packages": {"fictional": "1"}, "executable": "/private/python"})
    write(run / "coherence-audit.json", {"evidence": "fictional technical aggregate only", "forecast_freeze_sha256": freeze_hash,
        "results": [{"panel": "base", "audit": "fictional expected means", "finite_triples": 3, "absolute_gap_mean": 2,
            "player_id": "DO_NOT_EXPORT_PLAYER_ROW"}], "bindings": {}, "interpretation": "No joint law claim"})
    pairs = []
    for method, count, candidate, baseline in [("website", 3, 2., 4.), ("raw", 2, 3., 5.), ("simple", 0, None, None)]:
        metrics = {"rows": count, "mae": candidate, "rmse": 8., "bias_prediction_minus_actual": -2., "absolute_error_p90": 10.}
        pairs.append({"comparator": method, "population": "all_original_offered", "status": "primary" if method == "website" else "secondary",
            "offered_rows": 5, "supported_played_rows": 3, "paired_rows": count, "candidate_point": "median", "primary_loss": "mae",
            "candidate_loss": candidate, "control_loss": baseline, "improvement_pct": 50. if method == "website" else None,
            "games": 2 if count else 0, "weeks": 1 if count else 0,
            "candidate_point_metrics": metrics, "control_literal_point_metrics": dict(metrics, mae=baseline)})
    pure = {"target": "pass_att", "method_family": "pure_cdf", "paired": pairs,
        "candidate_summary": {"population_rows": 5, "supported_played_outcomes": 3, "fallback_rows": 1,
            "outcome_states": {"played": 3, "unknown": 2}, "fallback_reasons": {"": 4, "cold_start_role_prior": 1}},
        "subgroups": [{"dimension": "history_state", "value": "warm", "population_rows": 4},
                      {"dimension": "player_id", "value": "DO_NOT_EXPORT_PLAYER_ROW", "population_rows": 1}]}
    ensemble = copy.deepcopy(pure)
    ensemble.update(method_family="website_equalweight", point_semantics="point heuristic, no probability law")
    ensemble["subgroups"] = [{"dimension": "abstention", "value": "", "offered_rows": 4}, {"dimension": "abstention", "value": "missing_literal_website", "offered_rows": 1}]
    pure_hash = write(run / "trials/pass_att/base/report.json", pure)
    ensemble_hash = write(run / "trials/pass_att/base/ensemble-report.json", ensemble)
    slots = []
    for target in TARGETS:
        for panel in ["base", "context"]:
            for family in ["pure_cdf", "website_equalweight"]:
                slot = {"target": target, "panel": panel, "method_family": family, "state": "BLOCKED_CATEGORY_CONTRACT"}
                if target == "pass_att" and panel == "base":
                    slot.update(state="SCORED_DESCRIPTIVE", report_sha256=pure_hash if family == "pure_cdf" else ensemble_hash, primary=pairs[0])
                slots.append(slot)
    write(run / "website-cdf-report.json", {"registration_id": "fictional", "evidence": "fictional reconstruction", "slots": slots,
        "original_offered_rows": 5, "original_outcome_states": {"played": 3, "unknown": 2}, "ensemble_design": {"fixed": .5}, "budget": {"fits": 22}})
    return run, completed_hash


def test_export_retains_all48_slots_and_verbatim_control_specific_denominators(tmp_path):
    run, completion_hash = fictional_run(tmp_path)
    output = tmp_path / "aggregate-only-export"
    manifest = export_aggregates(run, output, completion_hash)
    report = json.loads((output / "aggregate-report.json").read_text())
    assert len(report["matrix"]) == 48
    assert sum(row["target"] == "fantasy_ppr" for row in report["matrix"]) == 4
    pure = next(row for row in report["matrix"] if row["target"] == "pass_att" and row["panel"] == "base" and row["method_family"] == "pure_cdf")
    assert pure["website"]["paired_rows"] == 3
    assert pure["website"]["candidate_loss"] == 2
    assert pure["website"]["improvement_pct"] == 50
    assert pure["raw"]["paired_rows"] == 2
    assert pure["raw"]["candidate_loss"] == 3
    assert pure["simple"]["paired_rows"] == 0
    assert pure["simple"]["candidate_loss"] is None
    assert pure["coverage"]["fallback_rows"] == 1
    assert pure["model_and_forecast_hashes"]["model/model.joblib"] == "c" * 64
    assert report["runtime_manifest"]["python"] == "fictional"
    assert report["replay_contract"]["replay_performed_by_exporter"] is False
    assert report["coherence_audit"]["results"][0]["absolute_gap_mean"] == 2
    assert (output / "coherence-audit.json").is_file()
    assert manifest["row_data_reads"] == manifest["new_scores"] == manifest["new_forecasts"] == 0
    for artifact in output.iterdir():
        assert "DO_NOT_EXPORT_PLAYER_ROW" not in artifact.read_text()
        assert "/private/" not in artifact.read_text()
    assert "Candidate RMSE / bias / p90 AE" in (output / "aggregate-report.md").read_text()
    with pytest.raises(ValueError, match="new directory"):
        export_aggregates(run, output, completion_hash)


def test_incomplete_receipt_blocks_before_accuracy_reports_are_read(tmp_path):
    run = tmp_path / "not-completed"
    run.mkdir()
    completion_hash = write(run / "completion.json", {"state": "INCOMPLETE_RETAINED_NO_RESTART"})
    (run / "website-cdf-report.json").write_text("not valid JSON; must not be opened")
    with pytest.raises(ValueError, match="completed-run receipt"):
        export_aggregates(run, tmp_path / "export", completion_hash)
    assert not (tmp_path / "export").exists()


def test_changed_completion_or_detailed_aggregate_hash_rejected(tmp_path):
    run, completion_hash = fictional_run(tmp_path)
    with pytest.raises(ValueError, match="hash changed"):
        export_aggregates(run, tmp_path / "export", "0" * 64)
    detailed = run / "trials/pass_att/base/report.json"
    detailed.write_text(detailed.read_text() + " ")
    with pytest.raises(ValueError, match="hash changed"):
        export_aggregates(run, tmp_path / "export", completion_hash)


def test_matrix_slot_loss_and_inside_run_output_rejected(tmp_path):
    run, completion_hash = fictional_run(tmp_path)
    with pytest.raises(ValueError, match="outside immutable"):
        export_aggregates(run, run / "export", completion_hash)
    top = json.loads((run / "website-cdf-report.json").read_text())
    top["slots"].pop()
    write(run / "website-cdf-report.json", top)
    with pytest.raises(ValueError, match="48-slot"):
        export_aggregates(run, tmp_path / "export", completion_hash)
