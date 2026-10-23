"""Export completed saved threshold aggregates without reading row artifacts.

Only a pinned completion/report and their plan/seal/freeze JSON chain are
opened. Derived values subtract or divide already saved SAME-cohort aggregate
metrics; no observations, models, forecasts or losses are reconstructed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import time

TARGETS = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd", "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td")
NUMERIC_TARGETS = TARGETS[:10]
LANES = ("declared_common_controls", "pairwise_literal_site")
SCALAR_FIELDS = ("offered_rows", "scored_rows", "games", "players", "weeks", "point_mae", "point_rmse",
    "point_bias_prediction_minus_actual", "point_absolute_error_p90", "point_absolute_error_p95", "point_absolute_error_max",
    "three_way_correct_rows", "three_way_accuracy", "three_way_misclassification_rate", "actual_equal_threshold_rows",
    "actual_equal_threshold_rate", "prediction_equal_threshold_rows", "nonpush_secondary_rows", "nonpush_secondary_accuracy",
    "nonpush_prediction_equal_rows", "coverage_count_population", "direction_semantics", "push_semantics", "timing_semantics")
COUNT_MAPS = ("eligibility_states", "threshold_classes", "line_source_states", "participation_states", "quarantine_states",
              "line_clock_vs_cutoff", "line_clock_vs_kickoff", "forecast_clock_vs_kickoff", "source_coverage")
GROUP_FIELDS = {"line_from", "opponent", "position", "source_coverage", "team", "model_fallback", "native_candidate_state"}
NOTES = [
    "One exposed2026Week6. Category rows repeat player-games across statistics, methods and strata. The common-control and SITE natural-coverage counts are separately labelled; neither is a count of independent NFL observations. No new independent sample is created.",
    "Thresholds are website-recorded provider-fed references: DraftKings via ESPN and Sleeper Picks. The original upstream quote body and publication timestamps are unavailable. This is not an authenticated raw sportsbook archive or a universal source-rights grant.",
    "Original local threshold/raw/SITE capture clocks are distinct from postgame calculation clocks for reconstructed challengers. Missing clocks remain unknown. No contemporaneous, prospective or complete historical as-of claim follows.",
    "This packet reuses frozen points only. Prior PFR-dependent fitted outputs are frozen comparators; no such features, model artifacts or training labels are read here. The original learner budgets, failures and source changes remain spent and exposed.",
    "Numeric output is a three-way point-direction rule: under/equal/over relative to the literal threshold. Numeric threshold probabilities and proper probability scores are N/A; point directions are not calibrated probabilities.",
    "Actual equality is reported separately. Nonpush accuracy is secondary and does not assume any market settlement, payout or return rule. No line, epsilon, threshold, weight, window or winner search is performed.",
    "Each candidate's primary intersection includes its valid point plus literal SITE/raw/recent/pooled points and supported played actuals on the same offers. Candidate/SITE-only secondary pairs retain separate denominators. Optional692 coverage never shrinks unrelated method/target cohorts.",
    "All156 method/target slots,288 comparisons and8998 declared group summaries remain, including zero/empty cells, six structurally missing numeric692 slots, and PPR/TD nonmarket blocks. No panel or method is selected by its result.",
    "Differences below are arithmetic on already computed same-cohort aggregate rates/errors. They are not a new score pass, refit, model prediction, confidence interval or independent validation. Zero baseline denominators produce null relative improvements.",
    "No intervals, significance, power, multiplicity claim, qualification, integration or promotion follows from one partly represented exposed week. DNP/unknown/missing/quarantined outcomes remain unscored and explicit.",
]


def digest(body):
    return hashlib.sha256(body).hexdigest()


def select(value, names):
    return {name: value[name] for name in names if name in value}


class MetadataReader:
    def __init__(self, run, plan, seal):
        self.paths = {"completion": Path(run) / "completion.json", "forecast_freeze": Path(run) / "forecast-freeze.json",
                      "saved_report": Path(run) / "report.json", "plan": Path(plan), "seal": Path(seal)}
        self.started, self.bytes, self.hashes = time.monotonic(), 0, {}

    def check(self):
        if time.monotonic() - self.started >= 120:
            raise TimeoutError("finite120-second aggregate export budget consumed")

    def read(self, name, expected=None):
        self.check()
        if name not in self.paths or self.paths[name].suffix != ".json":
            raise ValueError("only declared aggregate/plan/seal/freeze JSON may be read")
        path = self.paths[name]
        size = path.stat().st_size
        if size > 64 * 1024 ** 2 or self.bytes + size > 96 * 1024 ** 2:
            raise ValueError("finite aggregate JSON byte budget exceeded")
        body = path.read_bytes()
        sha = digest(body)
        if expected is not None and sha != expected:
            raise ValueError("pinned metadata hash changed: " + name)
        self.hashes[name] = sha
        self.bytes += len(body)
        return json.loads(body)


def binding(name, value):
    return {"name": name, "artifact": Path(value.get("path", name)).name, **select(value, ("sha256", "bytes"))}


def metric_summary(value):
    result = select(value, SCALAR_FIELDS)
    for name in COUNT_MAPS:
        result[name] = dict(value.get(name, {}))
    confusion = value.get("confusion_three_way", {})
    result["confusion_three_way"] = {p: {a: confusion.get(p, {}).get(a, 0) for a in ["under", "equal", "over"]}
                                     for p in ["under", "equal", "over"]}
    return result


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def delta(a, b):
    return a - b if finite(a) and finite(b) else None


def improvement(candidate, baseline):
    return 100 * (baseline - candidate) / baseline if finite(candidate) and finite(baseline) and baseline != 0 else None


def same_cohort_differences(candidate, baseline):
    """Arithmetic on saved aggregate metrics; no underlying outcomes are read."""
    accuracy = delta(candidate.get("three_way_accuracy"), baseline.get("three_way_accuracy"))
    return {"misclassification_delta_candidate_minus_baseline": delta(candidate.get("three_way_misclassification_rate"), baseline.get("three_way_misclassification_rate")),
        "relative_misclassification_improvement_pct": improvement(candidate.get("three_way_misclassification_rate"), baseline.get("three_way_misclassification_rate")),
        "accuracy_difference_percentage_points": 100 * accuracy if accuracy is not None else None,
        "point_mae_delta_candidate_minus_baseline": delta(candidate.get("point_mae"), baseline.get("point_mae")),
        "relative_point_mae_improvement_pct": improvement(candidate.get("point_mae"), baseline.get("point_mae")),
        "semantics": "differences of already saved same-cohort aggregate rates/errors only; positive signed deltas are worse"}


def market_status(target, method, supported):
    if target in {"fantasy_ppr", "anytime_td"}:
        return "NONMARKET_BLOCKED_PPR_UNCERTIFIED" if target == "fantasy_ppr" else "NONMARKET_TD_REFERENCE_ONLY"
    if target not in supported.get(method, []):
        return "STRUCTURAL_METHOD_TARGET_UNSUPPORTED"
    return "NUMERIC_POINT_DIRECTION_ONLY"


def assert_public(value):
    if isinstance(value, dict):
        if {"player_id", "game_id", "actual", "line", "point", "training_labels", "training_binding"} & set(value):
            raise ValueError("raw identity/value fields may not enter a public aggregate")
        for item in value.values():
            assert_public(item)
    elif isinstance(value, list):
        for item in value:
            assert_public(item)
    elif isinstance(value, str) and any(prefix in value for prefix in ["/workspace/", "/private/", "/tmp/", "/home/runner/"]):
        raise ValueError("private path may not enter a public aggregate")


def build_export(reader, completion_sha256, report_sha256):
    completion = reader.read("completion", completion_sha256)
    if completion.get("state") != "COMPLETED_DESCRIPTIVE" or completion.get("global_score_passes") != 1 or completion.get("new_fits") != 0 or completion.get("new_model_predictions") != 0 or completion.get("report_sha256") != report_sha256:
        raise ValueError("pinned successful zero-fit one-score completion required before accuracy reads")
    freeze = reader.read("forecast_freeze", completion["forecast_freeze_sha256"])
    plan = reader.read("plan", freeze["plan_sha256"])
    seal = reader.read("seal", freeze["seal_sha256"])
    if seal.get("plan", {}).get("sha256") != reader.hashes["plan"] or not str(seal.get("decision", "")).startswith("PASS"):
        raise ValueError("matching separate technical seal required")
    saved = reader.read("saved_report", report_sha256)
    if saved.get("plan_sha256") != reader.hashes["plan"] or saved.get("forecast_freeze_sha256") != reader.hashes["forecast_freeze"] or saved.get("source_manifest_sha256") != plan["inputs"]["source_manifest"]["sha256"]:
        raise ValueError("saved report plan/freeze/source hash chain differs")
    metrics = saved["metrics"]
    methods = list(metrics["declared_methods"])
    if len(methods) != 13 or methods != plan["methods"] or metrics.get("reference_method") != "website":
        raise ValueError("fixed13 declared methods and literal SITE reference required")
    slots = metrics["method_target_summaries"]
    expected = {(target, method) for target in TARGETS for method in methods}
    if len(slots) != 156 or {(s["target"], s["method"]) for s in slots} != expected:
        raise ValueError("all156 method-target summary slots required")
    comparisons = metrics["comparisons"]
    expected_comparisons = {(target, method, lane) for target in TARGETS for method in methods if method != "website" for lane in LANES}
    if len(comparisons) != 288 or {(s["target"], s["candidate"], s["cohort"]) for s in comparisons} != expected_comparisons:
        raise ValueError("all288 fixed comparison slots required")
    groups = saved["grouped_summaries"]
    if len(groups) != 8998 or any(g.get("field") not in GROUP_FIELDS for g in groups):
        raise ValueError("all8998 safe declared aggregate groups required")
    supported = metrics["supported_targets_by_method"]
    public_slots = [{"target": s["target"], "method": s["method"], "market_status": market_status(s["target"], s["method"], supported),
                     **metric_summary(s)} for s in slots]
    public_comparisons = []
    for comparison in comparisons:
        target, candidate, controls = comparison["target"], comparison["candidate"], comparison["controls"]
        named = list(dict.fromkeys([candidate] + controls))
        if set(comparison["methods"]) != set(named) or set(named) - set(methods):
            raise ValueError("saved comparison has undeclared candidate/control methods")
        summaries = {name: metric_summary(comparison["methods"][name]) for name in named}
        for field in ["scored_rows", "games", "players", "weeks"]:
            if len({s.get(field) for s in summaries.values()}) != 1:
                raise ValueError("candidate and named baselines have different cohorts")
        if summaries[candidate].get("scored_rows") != comparison["common_rows"]:
            raise ValueError("saved comparison common-row count differs")
        derived = [{"baseline": name, **same_cohort_differences(summaries[candidate], summaries[name])} for name in controls]
        public_comparisons.append({"target": target, "candidate": candidate, "controls": controls, "cohort": comparison["cohort"],
            "common_rows": comparison["common_rows"], "market_status": market_status(target, candidate, supported),
            "methods": summaries, "candidate_vs_named_baselines": derived,
            "cohort_semantics": comparison["cohort_semantics"]})
    site_category_rows = sum(s.get("scored_rows", 0) for s in public_slots if s["method"] == "website" and s["target"] in NUMERIC_TARGETS)
    common_category_rows = sum(c["common_rows"] for c in public_comparisons if c["cohort"] == "declared_common_controls" and c["candidate"] == "raw" and c["target"] in NUMERIC_TARGETS)
    public_groups = [{"target": g["target"], "method": g["method"], "field": g["field"], "group": g["group"], **metric_summary(g)} for g in groups]
    source_counts = [select(s, ("target", "threshold_group", "line_from", "rows")) for s in saved.get("source_market_counts", [])]
    outcome_counts = [select(s, ("target", "threshold_group", "participation_state", "outcome_state", "rows")) for s in saved.get("outcome_state_coverage", [])]
    output = {"registration_id": saved["registration_id"], "evidence": saved["evidence"],
        "planned_counts": {"method_target_slots": 156, "all_comparisons": 288, "declared_group_summaries": 8998,
            "numeric_primary_slots": 120, "structurally_unsupported_numeric_692_slots": 6, "nonmarket_primary_PPR_TD_slots": 24},
        "population": {**select(plan["population"], ("offered_rows", "player_contexts", "games", "weeks", "expected_external_numeric_thresholds", "expected_external_source_counts", "internal_reference_thresholds", "anytime_event_reference_thresholds")),
            "saved_supported_SITE_category_rows": site_category_rows,
            "saved_raw_SITE_recent_pooled_common_category_rows": common_category_rows,
            "category_row_count_semantics": "SITE natural coverage and the four-control intersection are separately defined cohorts; their counts can coincide and neither is an independent NFL sample size",
            "independent_NFL_observations_claimed": False},
        "declared_methods": dict(metrics["declared_methods"]), "supported_targets_by_method": supported,
        "common_controls": metrics["common_controls"], "method_target_summaries": public_slots,
        "comparisons": public_comparisons, "grouped_summaries": public_groups, "source_market_counts": source_counts,
        "outcome_state_coverage": outcome_counts, "numeric_threshold_probabilities": "N/A",
        "all_12_qualification": saved["all_12_qualification"], "uncertainty": saved["uncertainty"],
        "protocol": {"primary": select(plan["primary"], ("metric", "comparator", "paired_population", "maximum_contrast_slots", "structural_missing_reconstruction_slots", "functional", "tie_rule", "actual_push_rule", "delta", "no_qualification_from_primary", "baseline_metrics")),
            "secondary": list(plan["secondary"]), "source_wording": plan.get("source_wording"), "cutoffs": plan["cutoffs"],
            "budget_accounting": plan["budget_accounting"], "correction_policy": plan["correction_policy"]},
        "source_and_evidence_limits": NOTES, "bounds": dict(saved["bounds"]),
        "completion": select(completion, ("state", "frozen_direction_rows", "authoritative_direction_conversions", "additional_integrity_conversion_calls", "global_score_passes", "new_fits", "new_model_predictions", "wall_seconds", "cpu_seconds", "peak_RSS_bytes", "output_bytes_before_completion")),
        "source_manifest": [binding(name, value) for name, value in plan["inputs"].items()],
        "code_manifest": [binding(name, value) for name, value in plan["code"].items()],
        "source_binding_hashes": [binding("retained_source_" + str(i), value) for i, value in enumerate(plan.get("source_bindings", []))],
        "private_scored_rows_sha256": saved["scored_rows_sha256"], "aggregate_input_hashes": dict(reader.hashes),
        "new_qualified_replacements": [], "export_schema": {"copy_only": "whitelisted saved aggregate fields; no row/model/feature/training-label reads",
            "additional_arithmetic": "same-cohort saved-rate/error subtraction and relative percentage change only; denominator zero -> null",
            "point_direction": "under/equal/over heuristic only", "numeric_probability": "N/A", "new_score_passes": 0,
            "new_fits": 0, "new_model_predictions": 0, "new_resamples": 0, "ranking_or_selection": False}}
    assert_public(output)
    return output


def fmt(value):
    return "—" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)


def markdown_report(public):
    lines = ["# Original recorded-threshold point directions", "", public["evidence"], "",
        f"All 156 method/target slots, 288 comparisons and 8998 group summaries remain. The {public['population']['saved_raw_SITE_recent_pooled_common_category_rows']} four-control common category rows and {public['population']['saved_supported_SITE_category_rows']} SITE natural-coverage category rows use separately defined cohorts. Both repeat player-games across categories and are not independent NFL observations.", "",
        "## All120 numeric primary comparisons", "",
        "Lower misclassification is better. Signed deltas are candidate minus SITE; positive is worse. Accuracy difference is percentage points. Relative improvements are null for a zero baseline. Six structurally missing692 rows remain.", "",
        "| Target | Candidate | Status | n / games / weeks | Candidate miss | SITE miss | Miss delta | Miss improvement % | Accuracy pp | Candidate / SITE MAE | MAE improvement % |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for lane in LANES:
        if lane == "pairwise_literal_site":
            lines += ["", "## All120 numeric candidate/SITE-only secondary comparisons", "",
                "These have their own paired denominators and are not substitutes for the primary common-control cohort.", "",
                "| Target | Candidate | Status | n / games / weeks | Candidate miss | SITE miss | Miss delta | Miss improvement % | Accuracy pp | Candidate / SITE MAE | MAE improvement % |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for c in public["comparisons"]:
            if c["cohort"] != lane or c["target"] not in NUMERIC_TARGETS:
                continue
            candidate, site = c["methods"][c["candidate"]], c["methods"]["website"]
            differences = next(d for d in c["candidate_vs_named_baselines"] if d["baseline"] == "website")
            values = [c["target"], c["candidate"], c["market_status"], " / ".join(fmt(candidate.get(k)) for k in ["scored_rows", "games", "weeks"]),
                fmt(candidate.get("three_way_misclassification_rate")), fmt(site.get("three_way_misclassification_rate")),
                fmt(differences["misclassification_delta_candidate_minus_baseline"]), fmt(differences["relative_misclassification_improvement_pct"]),
                fmt(differences["accuracy_difference_percentage_points"]), fmt(candidate.get("point_mae")) + " / " + fmt(site.get("point_mae")),
                fmt(differences["relative_point_mae_improvement_pct"])]
            lines.append("| " + " | ".join(values) + " |")
    lines += ["", "## All24 primary nonmarket blocks", "", "| Target | Candidate | Status | n |", "|---|---|---|---:|"]
    for c in public["comparisons"]:
        if c["cohort"] == "declared_common_controls" and c["target"] not in NUMERIC_TARGETS:
            lines.append("| " + " | ".join([c["target"], c["candidate"], c["market_status"], fmt(c["common_rows"])]) + " |")
    lines += ["", "## All156 natural method/target slots", "",
        "| Target | Method | Offered / scored | Games / weeks | MAE / RMSE / bias | AE p90 / p95 / max | Push count / rate | Nonpush n / accuracy |",
        "|---|---|---:|---:|---:|---:|---:|---:|"]
    for s in public["method_target_summaries"]:
        values = [s["target"], s["method"], " / ".join(fmt(s.get(k)) for k in ["offered_rows", "scored_rows"]),
            " / ".join(fmt(s.get(k)) for k in ["games", "weeks"]),
            " / ".join(fmt(s.get(k)) for k in ["point_mae", "point_rmse", "point_bias_prediction_minus_actual"]),
            " / ".join(fmt(s.get(k)) for k in ["point_absolute_error_p90", "point_absolute_error_p95", "point_absolute_error_max"]),
            " / ".join(fmt(s.get(k)) for k in ["actual_equal_threshold_rows", "actual_equal_threshold_rate"]),
            " / ".join(fmt(s.get(k)) for k in ["nonpush_secondary_rows", "nonpush_secondary_accuracy"])]
        lines.append("| " + " | ".join(values) + " |")
    lines += ["", "## Source and evidence limits", ""] + ["- " + note for note in public["source_and_evidence_limits"]]
    lines += ["", "Every named baseline difference, all8998 source/role/team/opponent groups, confusion matrices, pushes, source/outcome/quarantine/clock coverage and input hashes are retained in aggregate-report.json. No raw thresholds, actuals, player/game IDs, private paths or fitted model bytes are published.", ""]
    return "\n".join(lines)


def export_aggregates(run_directory, plan_path, seal_path, output_directory, completion_sha256, report_sha256):
    if not all(re.fullmatch(r"[0-9a-f]{64}", value) for value in [completion_sha256, report_sha256]):
        raise ValueError("exact completion and saved-report SHA256 pins required")
    run, output = Path(run_directory).resolve(), Path(output_directory).resolve()
    if output.exists() or output.is_relative_to(run):
        raise ValueError("public output must be a new directory outside immutable run")
    reader = MetadataReader(run, plan_path, seal_path)
    public = build_export(reader, completion_sha256, report_sha256)
    markdown = markdown_report(public)
    reader.check()
    output.mkdir(parents=True, exist_ok=False)
    body = json.dumps(public, indent=2, allow_nan=False) + "\n"
    (output / "aggregate-report.json").write_text(body)
    (output / "aggregate-report.md").write_text(markdown)
    manifest = {"successful_completion_sha256": completion_sha256, "saved_report_sha256": report_sha256,
        "aggregate_input_hashes": reader.hashes, "exporter_code_sha256": digest(Path(__file__).read_bytes()),
        "output_sha256": {"aggregate-report.json": digest(body.encode()), "aggregate-report.md": digest(markdown.encode())},
        "read_bytes": reader.bytes, "wall_seconds": time.monotonic() - reader.started,
        "row_reads": 0, "model_reads": 0, "new_fits": 0, "new_model_predictions": 0, "new_score_passes": 0,
        "new_resamples": 0, "saved_aggregate_difference_arithmetic_only": True}
    (output / "hash-manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["run_directory", "plan_path", "seal_path", "output_directory"]:
        parser.add_argument(name)
    parser.add_argument("--completion-sha256", required=True)
    parser.add_argument("--report-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(export_aggregates(args.run_directory, args.plan_path, args.seal_path, args.output_directory,
        args.completion_sha256, args.report_sha256), allow_nan=False))


if __name__ == "__main__":
    main()
