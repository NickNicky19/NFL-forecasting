"""Create-only export of saved aggregate metadata after pinned completion.

This module does not import the estimator, load row/model artifacts, calculate
losses, fit, predict, resample or select a panel. It copies explicit aggregate
fields only and preserves the entire fixed experimental matrix.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from .website_cdf_export import AggregateReader, POINT_FIELDS, digest_bytes, public_binding

TARGETS = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd",
           "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td")
PANELS = ("base", "context")
PERIODS = ("2022", "2023", "2024", "website_week6")
PAIR_FIELDS = ("population", "offered_rows", "supported_played_rows", "paired_rows", "candidate_missing_rows",
    "control_missing_rows", "candidate_point", "primary_loss", "candidate_loss", "control_loss",
    "delta_candidate_minus_control", "improvement_pct", "players", "games", "weeks", "uncertainty",
    "comparator", "status", "comparison", "period", "target")
LOG_FIELDS = ("rows", "natural_log_loss", "log_loss_state", "infinite_log_losses", "finite_log_loss_sum",
              "finite_log_loss_count", "probability_clipping")
INTERVAL_FIELDS = ("paired_rows", "clusters", "cluster", "candidate_years", "control_years", "compared_complete_years",
    "excluded_unpaired_years", "partial_failure_policy", "primary_roles_only", "primary_loss",
    "mean_delta_candidate_minus_control", "interval", "replicates", "seed", "monte_carlo_tail_probability_se",
    "monte_carlo_error_semantics", "interval_semantics", "reason", "point_api_adapter")
SOURCE_FIELDS = ("version", "method", "candidate_offered_rows", "retained_control_offered_rows", "common_rows",
    "candidate_only_rows", "control_only_rows", "raw_actual_conflicts_quarantined", "confirmed_participation_conflicts_quarantined",
    "participation_qualification_changes", "old_missing_new_finite", "old_finite_new_missing", "cutoff_binding", "outcome_policy")
STATUS_FIELDS = ("target", "panel", "period", "method_family", "state", "returncode", "reason", "wall_seconds",
                 "cpu_seconds", "sampled_peak_process_group_rss_bytes", "report_sha256")
NOTES = [
    "This is a joint learner and source reconstruction candidate. Model inputs use the separately approved NFL-statistics and eligible-roster packet; inherited PFR-dependent models are retained as frozen comparators only. No universal source-rights grant is claimed.",
    "All retained years and Week6 are exposed. Current revisions, postgame source qualification and the assumed seven-day historical label lag do not authenticate historical publication, pregame availability or contemporaneous improvement.",
    "Historical primary errors pool the2022–2024 paired rows before calculation. They are not averages of annual MAEs. Both fixed panels, every category, all losses and all failures remain visible.",
    "The48 primary slots include4 blocked exact-PPR slots. The96 planned target/panel/period attempts include8 blocked PPR slots and at most88 fits. The24 fixed website-blend slots are secondary, including2 blocked PPR slots.",
    "Each comparator has its own exact supported-played, finite-point paired cohort. Source changes can alter qualified outcomes and denominators. Common, candidate-only and control-only counts, participation changes, missingness and quarantined contradictions are retained. Losses on different cohorts are not interchangeable.",
    "Numeric outputs are MAE-objective point heuristics, not a forecast mean, integer-law median or distribution. Counts have the declared max(0,prediction) transform and can be fractional; signed yards are not clamped. Only anytime TD supplies a genuine probability, without clipping.",
    "Historical week/game intervals use the saved500-draw fixed-seed evaluator and are nominal95%, unadjusted and descriptive. Week6 has no intervals. No untouched confirmation, significance, selected winner, qualification or promotion follows.",
    "The website blend is only the predeclared secondary50/50 website/candidate point or probability, with no extra fit or weight search. Missing site points remain abstentions. DNP, unknown participation, played missing, played zero and quarantines remain distinct.",
    "The exporter copies saved aggregates and metadata only. It does not read player/game rows, training labels or fitted model bytes, and performs no fit, forecast, scoring, resampling or technical replay.",
]


class MetadataReader(AggregateReader):
    def read(self, relative, expected_hash=None):
        relative = str(relative)
        fixed = {"completion.json", "registry.json", "forecast-freeze.json", "environment.json", "median-boosting-report.json"}
        cell = re.fullmatch(r"trials/([a-z_]+)/(base|context)/(2022|2023|2024|website_week6)/(report|ensemble-report)\.json", relative)
        if relative not in fixed and (cell is None or cell.group(1) not in TARGETS):
            raise ValueError("only saved aggregate/receipt JSON names are allowed")
        return super().read(relative, expected_hash)


def fields(value, names):
    return {name: value[name] for name in names if name in value}


def bins(value):
    names = ("bin", "lower_inclusive", "upper", "upper_inclusive", "rows", "mean_probability", "observed_rate")
    return [fields(item, names) for item in value]


def summary(value):
    result = fields(value, ("offered_rows", "scored_rows", "missing_points", "players", "games", "weeks", "brier", *LOG_FIELDS))
    result["point_metrics"] = fields(value.get("point_metrics", {}), POINT_FIELDS)
    result["outcome_states"] = dict(value.get("outcome_states", {}))
    if "reliability_deciles" in value:
        result["reliability_deciles"] = bins(value["reliability_deciles"])
    return result


def pair(value):
    result = fields(value, PAIR_FIELDS)
    for name in ["candidate_point_metrics", "control_literal_point_metrics"]:
        result[name] = fields(value.get(name, {}), POINT_FIELDS)
    if "intervals" in value:
        result["intervals"] = [fields(item, INTERVAL_FIELDS) for item in value["intervals"]]
    if "paired_binary" in value:
        binary = value["paired_binary"]
        result["paired_binary"] = {name: fields(binary.get(name, {}), LOG_FIELDS) for name in ["candidate", "control"]}
        for name in ["candidate_reliability_deciles", "control_reliability_deciles"]:
            result["paired_binary"][name] = bins(binary.get(name, []))
    return result


def source_comparison(value):
    result = fields(value, SOURCE_FIELDS)
    for name in ["candidate_participation_states", "retained_participation_states", "candidate_outcome_states", "retained_outcome_states"]:
        result[name] = dict(value.get(name, {}))
    if "retained_source_binding" in value:
        result["retained_source_binding"] = public_binding("frozen_" + value.get("method", "control"), value["retained_source_binding"])
    return result


def report_summary(value):
    result = fields(value, ("target", "panel", "method_family", "semantics", "compared_complete_years", "excluded_years", "partial_failure_policy"))
    result["summary"] = summary(value.get("summary", {}))
    result["paired"] = [pair(item) for item in value.get("paired", [])]
    result["source_comparisons"] = [source_comparison(item) for item in value.get("source_comparisons", [])]
    if "role_prior" in value:
        result["role_prior"] = summary(value["role_prior"])
    allowed = {"position", "season", "team", "opponent", "fallback", "history_state", "outcome_state"}
    result["subgroups"] = [{"dimension": item["dimension"], "value": item["value"], **summary(item)}
        for item in value.get("subgroups", []) if item.get("dimension") in allowed]
    return result


def forecast_hashes(freeze, target, panel, period):
    prefix = f"trials/{target}/{panel}/{period}/"
    names = ["model/model.joblib", "model/manifest.json", "prediction-manifest.json", "query.parquet",
             "candidate-frozen.parquet", "role-prior-frozen.parquet", "ensemble-frozen.parquet"]
    return {name: freeze.get("bindings", {}).get(prefix + name) for name in names
            if prefix + name in freeze.get("bindings", {})}


def build_export(reader, completion_sha256):
    # No accuracy-containing JSON is opened until this exact receipt passes.
    completion = reader.read("completion.json", completion_sha256)
    if completion.get("state") != "COMPLETED_DESCRIPTIVE" or completion.get("reporting", {}).get("returncode") != 0 or not completion.get("score_pass_consumed"):
        raise ValueError("pinned successful completed-run receipt required before accuracy reads")
    registry, freeze, runtime = reader.read("registry.json"), reader.read("forecast-freeze.json"), reader.read("environment.json")
    if registry.get("source_packet_mode") != "joint_learner_source_reconstruction":
        raise ValueError("explicit joint learner/source reconstruction attribution required")
    top = reader.read("median-boosting-report.json")
    primary_expected = {(t, p, period) for t in TARGETS for p in PANELS for period in ["pooled2022-2024", "website_week6"]}
    primary_actual = {(s["target"], s["panel"], s["period"]) for s in top["primary_slots"]}
    if primary_actual != primary_expected or len(top["primary_slots"]) != 48:
        raise ValueError("complete fixed48 primary slots required")
    cell_expected = {(t, p, period, "pure") for t in TARGETS for p in PANELS for period in PERIODS}
    cell_expected |= {(t, p, "website_week6", "website_equalweight_secondary") for t in TARGETS for p in PANELS}
    cell_actual = {(s["target"], s["panel"], s["period"], s["method_family"]) for s in top["slots"]}
    if cell_actual != cell_expected or len(top["slots"]) != 120:
        raise ValueError("all96 attempt slots and24 secondary blend slots required")
    if sum(s["target"] == "fantasy_ppr" and s["state"] == "BLOCKED_CATEGORY_CONTRACT" for s in top["primary_slots"]) != 4:
        raise ValueError("all four exact-PPR primary slots must remain blocked")
    primary_index = {(s["target"], s["panel"], s["period"]): s for s in top["primary_slots"]}
    primary_matrix = []
    for target in TARGETS:
        for panel in PANELS:
            for period in ["pooled2022-2024", "website_week6"]:
                item = primary_index[target, panel, period]
                row = fields(item, ("target", "panel", "period", "method_family", "state", "compared_complete_years", "excluded_years"))
                row["primary"] = pair(item["primary"]) if item.get("primary") is not None else None
                primary_matrix.append(row)
    pooled = [report_summary(item) for item in top.get("historical_pooled", [])]
    for item in pooled:
        primary = next((p for p in item["paired"] if p.get("status") == "primary"), None)
        expected = primary_index[item["target"], item["panel"], "pooled2022-2024"].get("primary")
        if primary != (pair(expected) if expected is not None else None):
            raise ValueError("pooled top/detail primary aggregate differs")
    cell_index = {(s["target"], s["panel"], s["period"], s["method_family"]): s for s in top["slots"]}
    cells = []
    for period in PERIODS:
        for target in TARGETS:
            for panel in PANELS:
                families = ["pure", "website_equalweight_secondary"] if period == "website_week6" else ["pure"]
                for family in families:
                    slot = cell_index[target, panel, period, family]
                    row = fields(slot, STATUS_FIELDS)
                    row["model_and_forecast_hashes"] = forecast_hashes(freeze, target, panel, period)
                    row["aggregate"] = None
                    if slot["state"] == "SCORED_DESCRIPTIVE":
                        name = "report.json" if family == "pure" else "ensemble-report.json"
                        relative = f"trials/{target}/{panel}/{period}/{name}"
                        saved = reader.read(relative, slot["report_sha256"])
                        if saved.get("target") != target or saved.get("method_family") != family:
                            raise ValueError("saved aggregate target/family differs")
                        row["aggregate"] = report_summary(saved)
                        if period == "website_week6" and family == "pure":
                            primary = next((pair(p) for p in saved["paired"] if p.get("status") == "primary"), None)
                            expected = primary_index[target, panel, period].get("primary")
                            if primary != (pair(expected) if expected is not None else None):
                                raise ValueError("website top/detail primary aggregate differs")
                    cells.append(row)
    methods = [fields(registry["categories"][target], ("target", "state", "support", "modeled_roles", "primary_roles", "panels")) for target in TARGETS]
    sources = [public_binding(name, value) for name, value in registry.get("inputs", {}).items()]
    for name in ["source_contract", "prior_registry", "website_registry"]:
        if name in registry:
            sources.append(public_binding(name, registry[name]))
    model = top.get("model_design", {})
    model_fields = ("numeric_estimator", "numeric_loss", "binary_estimator", "binary_loss", "threads", "count_transform",
        "signed_transform", "binary_transform", "fallback", "minimum_modeled_rows", "single_class_binary", "numeric_semantics")
    topology = fields(model.get("parameters", {}), ("max_iter", "learning_rate", "max_leaf_nodes", "max_depth", "min_samples_leaf", "l2_regularization", "early_stopping", "random_state"))
    return {"registration_id": top["registration_id"], "evidence": "Exposed joint learner/source historical and original-website reconstruction; saved aggregates only",
        "source_packet_mode": registry["source_packet_mode"], "primary_contrast_slots": 48, "blocked_ppr_primary_contrasts": 4,
        "planned_target_panel_period_slots": 96, "blocked_ppr_attempt_slots": 8, "maximum_candidate_fits": 88,
        "secondary_website_blend_slots": 24, "primary_matrix": primary_matrix, "historical_pooled": pooled,
        "cell_matrix": cells, "context_ablations": [pair(item) for item in top.get("context_ablations", [])],
        "attempt_slots": [fields(s, STATUS_FIELDS) for s in cells if s["method_family"] == "pure"],
        "source_and_evidence_limits": NOTES, "source_manifest": sources, "method_manifest": methods,
        "model_parameter_schema": {**fields(model, model_fields), "parameters": topology,
            "preprocessing": "unchanged FixedDesign training-only median imputation, missing indicators and trained role vocabulary",
            "private_values_exported": False, "numeric_distribution": "none"},
        "fixed_secondary_ensemble_design": fields(top.get("ensemble_design", {}), ("weight_website", "weight_candidate", "scope", "missing_website", "numeric_semantics", "binary_semantics", "weight_search", "additional_fits")),
        "comparisons": fields(top.get("comparisons", {}), ("historical_primary", "historical_secondary", "website_primary", "website_secondary", "selection")),
        "budgets": fields(top.get("budgets", {}), ("maximum_candidate_fit_attempts", "maximum_threads", "campaign_wall_seconds", "campaign_cpu_seconds", "per_trial_wall_seconds", "per_trial_cpu_seconds", "memory_bytes", "private_output_bytes", "reporting_wall_reserve_seconds", "bootstrap_replicates", "score_passes")),
        "completion": fields(completion, ("state", "fit_attempts_consumed", "score_pass_consumed", "wall_seconds", "cpu_seconds", "output_bytes_before_completion")),
        "runtime_manifest": fields(runtime, ("python", "packages", "threads", "runtime_agent_configuration")),
        "code_manifest": [public_binding(Path(value["path"]).name, value) for value in registry.get("code_bindings", [])],
        "source_qualification_sha256": digest_bytes(json.dumps(top.get("source_qualification"), sort_keys=True, separators=(",", ":")).encode()),
        "aggregate_input_hashes": dict(reader.hashes), "new_qualified_replacements": [],
        "technical_replay_performed_by_exporter": False,
        "export_semantics": "Only saved aggregate fields and hash/schema metadata copied; no row/model/label reads, new forecasts, losses, resampling or selection"}


def formatted(value):
    return "—" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)


def markdown_report(exported):
    lines = ["# Fixed absolute-error boosting reconstruction", "", exported["evidence"], "",
        "Numeric error is MAE; anytime TD error is Brier. Historical primary rows are pooled before calculation. Every fixed panel and category remains visible.", "",
        "| Category | Panel | Period | State | Comparator | n / games / weeks | Candidate error | Control error | Improvement % |",
        "|---|---|---|---|---|---:|---:|---:|---:|"]
    for row in exported["primary_matrix"]:
        p = row["primary"] or {}
        values = [row["target"], row["panel"], row["period"], row["state"], p.get("comparator", "—"),
            " / ".join(formatted(p.get(k)) for k in ["paired_rows", "games", "weeks"]),
            formatted(p.get("candidate_loss")), formatted(p.get("control_loss")), formatted(p.get("improvement_pct"))]
        lines.append("| " + " | ".join(values) + " |")
    lines += ["", "## All annual and website comparisons", "",
        "Annuals, recent/pooled controls, role subsets and fixed website blends are secondary. Each comparator keeps its own paired cohort. All statuses and both role populations are retained in JSON.", "",
        "| Category | Panel | Period | Family | State | Comparator | n / games / weeks | Candidate error | Control error | Delta |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|"]
    for row in exported["cell_matrix"]:
        comparisons = [p for p in (row.get("aggregate") or {}).get("paired", []) if p.get("population") == "all_original_offered"] or [{}]
        for p in comparisons:
            values = [row["target"], row["panel"], row["period"], row["method_family"], row["state"], p.get("comparator", "—"),
                " / ".join(formatted(p.get(k)) for k in ["paired_rows", "games", "weeks"]),
                formatted(p.get("candidate_loss")), formatted(p.get("control_loss")), formatted(p.get("delta_candidate_minus_control"))]
            lines.append("| " + " | ".join(values) + " |")
    lines += ["", "## Primary paired point diagnostics", "",
        "| Category | Panel | Period | Candidate RMSE / bias / p90 AE / p95 AE / max AE | Control RMSE / bias / p90 AE / p95 AE / max AE |",
        "|---|---|---|---:|---:|"]
    for row in exported["primary_matrix"]:
        if row["primary"] is None:
            continue
        p = row["primary"]
        def diagnostic(name):
            return " / ".join(formatted(p[name].get(k)) for k in ["rmse", "bias_prediction_minus_actual", "absolute_error_p90", "absolute_error_p95", "absolute_error_max"])
        lines.append("| " + " | ".join([row["target"], row["panel"], row["period"], diagnostic("candidate_point_metrics"), diagnostic("control_literal_point_metrics")]) + " |")
    lines += ["", "## Source and evidence limits", ""] + ["- " + note for note in exported["source_and_evidence_limits"]]
    lines += ["", "Exact saved intervals, tail errors, fallback/outcome/source-lineage counts, probability log losses and reliability deciles, all attempt statuses and private-artifact hashes are retained in aggregate-report.json. No player/game rows or fitted values are published.", ""]
    return "\n".join(lines)


def export_aggregates(run_directory, output_directory, completion_sha256):
    if not re.fullmatch(r"[0-9a-f]{64}", completion_sha256):
        raise ValueError("exact successful completion SHA256 required")
    run, output = Path(run_directory).resolve(), Path(output_directory).resolve()
    if output.exists() or output.is_relative_to(run):
        raise ValueError("export destination must be a new directory outside immutable run outputs")
    reader = MetadataReader(run)
    exported = build_export(reader, completion_sha256)
    markdown = markdown_report(exported)
    reader.check_time()
    output.mkdir(parents=True, exist_ok=False)
    body = json.dumps(exported, indent=2, allow_nan=False) + "\n"
    (output / "aggregate-report.json").write_text(body)
    (output / "aggregate-report.md").write_text(markdown)
    manifest = {"aggregate_input_hashes": dict(reader.hashes), "successful_completion_sha256": completion_sha256,
        "exporter_code_sha256": digest_bytes(Path(__file__).read_bytes()),
        "reader_code_sha256": digest_bytes(Path(__file__).with_name("website_cdf_export.py").read_bytes()),
        "output_sha256": {"aggregate-report.json": digest_bytes(body.encode()), "aggregate-report.md": digest_bytes(markdown.encode())},
        "read_bytes": reader.bytes, "wall_seconds": time.monotonic() - reader.started,
        "row_data_reads": 0, "model_data_reads": 0, "new_fits": 0, "new_forecasts": 0, "new_scores": 0,
        "technical_replay_performed": False}
    (output / "hash-manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    reader.check_time()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory")
    parser.add_argument("output_directory")
    parser.add_argument("--completion-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(export_aggregates(args.run_directory, args.output_directory, args.completion_sha256), allow_nan=False))


if __name__ == "__main__":
    main()
