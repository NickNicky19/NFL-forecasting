"""Fictional aggregate receipts only; no football rows or model execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nfl_lab import role_boosting_repair_export as exporter
from test_role_boosting_export import fictional_run, write


def fictional_repair(tmp_path):
    repair, _, _ = fictional_run(tmp_path)
    source = tmp_path / "fictional-failed-original"
    source.mkdir()
    for name in ("registry.json", "environment.json"):
        (source / name).write_bytes((repair / name).read_bytes())
        (repair / name).unlink()
    top = json.loads((repair / "role-boosting-report.json").read_text())
    slots, original_statuses, pooled, primary = [], [], [], []
    bindings = {}
    for slot in top["slots"]:
        item = dict(slot)
        target, variant, period = (item[k] for k in ("target", "variant", "period"))
        kind = item["kind"]
        fits = 0 if kind != "model" else 1 if variant == "A" else 3 if target == "anytime_td" else 5
        item["fit_attempts"] = fits
        if target != "fantasy_ppr":
            template = repair / f"trials/pass_att/{variant}/{period}/report.json"
            detail = json.loads(template.read_text()) if target != "anytime_td" else json.loads((repair / f"trials/anytime_td/{variant}/{period}/report.json").read_text())
            detail["target"] = target
            item.update(state="SCORED_DESCRIPTIVE", report_sha256=write(repair / f"trials/{target}/{variant}/{period}/report.json", detail))
            bindings[f"trials/{target}/{variant}/{period}/candidate-frozen.parquet"] = "e" * 64
        slots.append(item)
        original = {k: v for k, v in item.items() if k not in {"report_sha256", "primary_comparisons"}}
        original["state"] = "PREDICTION_FROZEN" if target != "fantasy_ppr" else "BLOCKED_CATEGORY_CONTRACT"
        original_statuses.append(original)
    for target in exporter.TARGETS:
        for variant in exporter.VARIANTS:
            for period in exporter.PRIMARY_PERIODS:
                template = next(x for x in top["primary_slots"] if x["target"] == ("anytime_td" if target == "anytime_td" else "fantasy_ppr" if target == "fantasy_ppr" else "pass_att") and x["variant"] == variant and x["period"] == period)
                primary.append(dict(copy.deepcopy(template), target=target))
            if target != "fantasy_ppr":
                template = next(x for x in top["historical_pooled"] if x["target"] == ("anytime_td" if target == "anytime_td" else "pass_att") and x["variant"] == variant)
                pooled.append(dict(copy.deepcopy(template), target=target))
    assert sum(x["fit_attempts"] for x in original_statuses) == 136
    freeze_sha = write(source / "forecast-freeze.json", {"bindings": bindings, "fit_attempts": 136, "packages": 96})
    (repair / "forecast-freeze.json").unlink()
    marker_sha = write(source / "score-consumed.json", {"score_passes": 1, "forecast_freeze_sha256": freeze_sha})
    original_sha = write(source / "completion.json", {"state": exporter.ORIGINAL_FAILURE,
        "fit_attempts_consumed": 136, "score_pass_consumed": True, "statuses": original_statuses,
        "reporting": {"returncode": 1, "reason": "/private/PRIVATE_POISON"}})
    source_hashes = {name: exporter.digest_bytes((source / name).read_bytes()) for name in (
        "registry.json", "forecast-freeze.json", "completion.json", "score-consumed.json", "environment.json")}
    provenance = {"repair_registration_id": exporter.VERSION, "source_registration_id": exporter.SOURCE_VERSION,
        "original_state": exporter.ORIGINAL_FAILURE, "original_fit_attempts_consumed": 136,
        "original_score_pass_consumed": True, "original_failed_report_attempts": 1,
        "repair_report_attempts_consumed": 1, "cumulative_report_attempts": 2,
        "new_fits": 0, "new_predictions": 0, "new_independent_observations": 0,
        "source_registry_sha256": source_hashes["registry.json"], "source_freeze_sha256": freeze_sha,
        "source_failed_completion_sha256": original_sha, "source_consumed_marker_sha256": marker_sha,
        "source_directory": "/private/PRIVATE_POISON", "key_repair": "existing normalize_keys on derived scored frames only",
        "model_weights": [123., 456.], "private_note": "PRIVATE_POISON"}
    budgets = {"maximum_candidate_fit_attempts": 0, "maximum_prediction_calls": 0, "report_attempts": 1,
        "wall_seconds": 600, "cpu_seconds": 900, "maximum_threads": 2, "memory_bytes": 1536 * 1024**2,
        "combined_private_output_bytes": 800 * 1024**2, "model_weights": "PRIVATE_POISON"}
    registry_sha = write(repair / "repair-registry.json", {"registration_id": exporter.VERSION,
        "source_registry": {"path": "/private/PRIVATE_POISON", "sha256": source_hashes["registry.json"]},
        "source_file_sha256": source_hashes, "budgets": budgets, "source_run_directory": "/private/PRIVATE_POISON"})
    write(repair / "repair-consumed.json", {"repair_registry_sha256": registry_sha,
        "report_attempts": 1, "new_fits": 0, "new_predictions": 0})
    top.update(slots=slots, primary_slots=primary, historical_pooled=pooled,
        repair_registration_id=exporter.VERSION, cumulative_report_attempts=2,
        repair_provenance=provenance, repair_budgets=budgets)
    report_sha = write(repair / "role-boosting-report.json", top)
    completion_sha = write(repair / "completion.json", {"registration_id": exporter.VERSION, "state": exporter.SUCCESS,
        "repair_provenance": provenance, "reporting": {"returncode": 0, "reason": None, "wall_seconds": 1., "cpu_seconds": 2.},
        "source_files_unchanged": True, "original_fit_attempts_consumed": 136, "new_fit_attempts_consumed": 0,
        "new_prediction_calls": 0, "repair_report_attempts_consumed": 1, "cumulative_report_attempts": 2,
        "source_statuses": original_statuses})
    return source, repair, completion_sha, report_sha


def test_export_retains_failure_repairs_and_all_aggregate_views_without_private_fields(tmp_path):
    source, repair, completion, report = fictional_repair(tmp_path)
    originals = {p.name: p.read_bytes() for p in source.iterdir()}
    output = tmp_path / "public"
    manifest = exporter.export_aggregates(source, repair, output, completion, report)
    public = json.loads((output / "aggregate-report.json").read_text())
    assert public["registration_id"] == exporter.VERSION
    assert public["source_registration_id"] == exporter.SOURCE_VERSION
    assert public["original_completion"]["state"] == exporter.ORIGINAL_FAILURE
    assert public["completion"]["state"] == exporter.SUCCESS
    assert public["original_fit_attempts_consumed"] == 136
    assert public["new_fit_attempts_consumed"] == public["new_prediction_calls"] == public["new_independent_observations"] == 0
    assert public["score_passes"] == public["cumulative_report_attempts"] == 2
    assert public["original_registered_score_passes"] == 1
    assert len(public["package_matrix"]) == 96 and len(public["primary_matrix"]) == 48
    assert len(public["coherence"]) == 16 and public["common_cohort_diagnostics"]
    assert len(public["historical_pooled"]) == 22
    assert sum(x["state"] == "BLOCKED_CATEGORY_CONTRACT" for x in public["package_matrix"]) == 8
    assert sum(x["reused_alias"] for x in public["package_matrix"]) == 40
    loser = next(x["primary"] for x in public["primary_matrix"] if x["target"] == "pass_att" and x["variant"] == "A" and x["period"] == "pooled2022-2024")
    assert loser["improvement_pct"] == -50. and loser["candidate_point_metrics"]["mse"] == 16.
    assert public["repair_provenance"]["source_failed_completion_sha256"] == exporter.digest_bytes(originals["completion.json"])
    assert manifest["original_forecast_freeze_sha256"] == exporter.digest_bytes(originals["forecast-freeze.json"])
    assert all(manifest[k] == 0 for k in ("row_data_reads", "model_data_reads", "new_fits", "new_forecasts", "new_scores", "resampling_passes"))
    assert originals == {p.name: p.read_bytes() for p in source.iterdir()}
    for path in output.iterdir():
        text = path.read_text()
        for forbidden in ("PRIVATE_POISON", "/private/", '"player_id"', '"game_id"', '"point"', '"actual"', "model_weights", ".parquet", ".joblib", "trials/"):
            assert forbidden not in text
    markdown = (output / "aggregate-report.md").read_text()
    assert exporter.ORIGINAL_FAILURE in markdown and "2 cumulative phases" in markdown
    with pytest.raises(ValueError, match="new directory"):
        exporter.export_aggregates(source, repair, output, completion, report)


@pytest.mark.parametrize("field,value", [("state", "COMPLETED_DESCRIPTIVE"), ("cumulative_report_attempts", 1),
    ("new_fit_attempts_consumed", 1), ("new_prediction_calls", 1), ("source_files_unchanged", False),
    ("original_fit_attempts_consumed", 135), ("new_fit_attempts_consumed", False)])
def test_repair_success_gate_precedes_accuracy_reads(tmp_path, monkeypatch, field, value):
    source, repair, _, report = fictional_repair(tmp_path)
    completion = json.loads((repair / "completion.json").read_text())
    completion[field] = value
    changed = write(repair / "completion.json", completion)
    calls, read = [], exporter.MetadataReader.read
    def watched(self, relative, *args, **kwargs):
        calls.append((self.kind, relative))
        return read(self, relative, *args, **kwargs)
    monkeypatch.setattr(exporter.MetadataReader, "read", watched)
    with pytest.raises(ValueError):
        exporter.export_aggregates(source, repair, tmp_path / "public", changed, report)
    assert calls == [("repair", "completion.json")]
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("filename", ["completion.json", "forecast-freeze.json", "registry.json", "score-consumed.json", "environment.json"])
def test_original_receipts_must_match_pinned_failure_and_freeze(tmp_path, filename):
    source, repair, completion, report = fictional_repair(tmp_path)
    path = source / filename
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash changed"):
        exporter.export_aggregates(source, repair, tmp_path / "public", completion, report)
    assert not (tmp_path / "public").exists()


def test_tampered_reports_and_mismatched_provenance_are_rejected(tmp_path):
    source, repair, completion, report = fictional_repair(tmp_path)
    detail = repair / "trials/pass_att/A/2022/report.json"
    original = detail.read_bytes()
    detail.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="hash changed"):
        exporter.export_aggregates(source, repair, tmp_path / "public", completion, report)
    detail.write_bytes(original)
    top = json.loads((repair / "role-boosting-report.json").read_text())
    top["repair_provenance"]["new_independent_observations"] = 1
    changed = write(repair / "role-boosting-report.json", top)
    with pytest.raises(ValueError, match="new_independent_observations"):
        exporter.export_aggregates(source, repair, tmp_path / "public", completion, changed)
    assert not (tmp_path / "public").exists()


def test_metadata_reader_rejects_rows_models_paths_and_source_cell_reports(tmp_path):
    source, repair, _, _ = fictional_repair(tmp_path)
    for root, kind in ((source, "source"), (repair, "repair")):
        reader = exporter.MetadataReader(root, kind)
        for name in ("rows.parquet", "model.joblib", "coherence/rows.json", "../completion.json", "reporting/stderr.log"):
            with pytest.raises(ValueError, match="allowlisted aggregate"):
                reader.read(name)
    with pytest.raises(ValueError, match="allowlisted aggregate"):
        exporter.MetadataReader(source, "source").read("trials/pass_att/A/2022/report.json")


def test_repair_consumed_marker_and_report_pins_prevent_export(tmp_path):
    source, repair, completion, report = fictional_repair(tmp_path)
    with pytest.raises(ValueError, match="hash changed"):
        exporter.export_aggregates(source, repair, tmp_path / "public", completion, "0" * 64)
    path = repair / "repair-registry.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="repair registry consumed hash"):
        exporter.export_aggregates(source, repair, tmp_path / "public", completion, report)
    assert not (tmp_path / "public").exists()


def test_original_success_cannot_replace_failed_history(tmp_path):
    source, repair, completion, report = fictional_repair(tmp_path)
    old = json.loads((source / "completion.json").read_text())
    old["state"] = "COMPLETED_DESCRIPTIVE"
    changed = write(source / "completion.json", old)
    public = tmp_path / "public"
    # Even consistently rewritten metadata cannot authenticate original success
    # under this failure-specific repair contract.
    top = json.loads((repair / "role-boosting-report.json").read_text())
    top["repair_provenance"]["source_failed_completion_sha256"] = changed
    report = write(repair / "role-boosting-report.json", top)
    done = json.loads((repair / "completion.json").read_text())
    done["repair_provenance"]["source_failed_completion_sha256"] = changed
    completion = write(repair / "completion.json", done)
    registry = json.loads((repair / "repair-registry.json").read_text())
    registry["source_file_sha256"]["completion.json"] = changed
    registry_sha = write(repair / "repair-registry.json", registry)
    marker = json.loads((repair / "repair-consumed.json").read_text())
    marker["repair_registry_sha256"] = registry_sha
    write(repair / "repair-consumed.json", marker)
    with pytest.raises(ValueError, match="original failed state"):
        exporter.export_aggregates(source, repair, public, completion, report)
    assert not public.exists()


def test_shared_input_budget_and_symlink_escapes_are_rejected(tmp_path, monkeypatch):
    source, repair, _, _ = fictional_repair(tmp_path)
    monkeypatch.setattr(exporter, "MAX_INPUT_BYTES", 1)
    with pytest.raises(ValueError, match="combined aggregate JSON input budget"):
        exporter.MetadataReader(source, "source").read("registry.json")
    (source / "environment.json").unlink()
    (source / "environment.json").symlink_to(repair / "completion.json")
    with pytest.raises(ValueError, match="escapes receipt root"):
        exporter.MetadataReader(source, "source").read("environment.json")


def test_import_has_no_row_or_model_dependencies():
    script = "import sys; import nfl_lab.role_boosting_repair_export; forbidden={'numpy','pandas','sklearn','joblib','nfl_lab.role_boosting','nfl_lab.role_boosting_campaign','nfl_lab.role_boosting_reporting_repair'}; assert not forbidden.intersection(sys.modules)"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
