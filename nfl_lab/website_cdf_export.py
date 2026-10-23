"""Export saved website-CDF aggregates; never load row data or score models.

Invoke only after completion is confirmed. A pinned successful completion
receipt is required before the exporter opens any accuracy report. Outputs are
create-only JSON/Markdown and contain counts, aggregate errors, and hashes only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time

TARGETS = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd",
           "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td")
FAMILIES = ("pure_cdf", "website_equalweight")
MAX_WALL_SECONDS = 120
MAX_INPUT_BYTES = 128 * 1024 ** 2
MAX_JSON_BYTES = 16 * 1024 ** 2
PAIR_FIELDS = ("population", "offered_rows", "supported_played_rows", "paired_rows",
               "candidate_missing_rows", "control_missing_rows", "candidate_point", "primary_loss",
               "candidate_loss", "control_loss", "delta_candidate_minus_control", "improvement_pct", "games", "weeks")
POINT_FIELDS = ("rows", "mae", "rmse", "bias_prediction_minus_actual", "absolute_error_p90",
                "absolute_error_p95", "absolute_error_max", "fraction_absolute_error_ge5", "fraction_absolute_error_ge50")
LIMITS_TEXT = [
    "New reconstruction calculated after exposed 2026 Week 6 games; candidate forecasts are neither the original runner nor prospective evidence.",
    "One exposed week and 13 original games. All fixed panels and both families are shown; no interval, significance, selected winner, qualification, or promotion follows.",
    "Training uses eligible retained 2019–2025 labels. Historical publication/correction clocks are unauthenticated; the declared seven-day label availability assumption is retained.",
    "All retained training years and Week 6 outcomes are exposed. V2 uses current revisions and postgame roster evidence; reconstruction does not authenticate the original pregame roster or publication vintage.",
    "Current-vintage prior-week inputs, identity coverage, missing histories, and trained-prior fallbacks do not establish fully authenticated historical as-of inputs.",
    "Each comparison uses its own identical supported-played, finite-candidate, finite-control paired rows. Raw/simple matched cohorts can differ from the primary website cohort; losses must not be compared across different denominators.",
    "Pure numeric primary points are same-law medians. Equalweight numeric blends are point heuristics, with no law-mean, law-median, distribution, or CRPS claim. TD uses genuine Bernoulli probabilities.",
    "DNP, unknown participation, played missing, quarantines, blocked PPR, failed attempts, and unavailable controls remain explicit. Missing values are not zero.",
]


def digest_bytes(body):
    return hashlib.sha256(body).hexdigest()


class AggregateReader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.started = time.monotonic()
        self.bytes = 0
        self.hashes = {}
        self.cache = {}

    def check_time(self):
        if time.monotonic() - self.started >= MAX_WALL_SECONDS:
            raise TimeoutError("120-second aggregate export budget consumed")

    def read(self, relative, expected_hash=None):
        self.check_time()
        relative = str(relative)
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or path.suffix != ".json":
            raise ValueError("exporter accepts bounded JSON metadata inside the completed run only")
        if relative not in self.cache:
            size = path.stat().st_size
            if size > MAX_JSON_BYTES or self.bytes + size > MAX_INPUT_BYTES:
                raise ValueError("aggregate JSON input budget exceeded")
            body = path.read_bytes()
            self.bytes += len(body)
            self.hashes[relative] = digest_bytes(body)
            self.cache[relative] = json.loads(body)
        if expected_hash is not None and self.hashes[relative] != expected_hash:
            raise ValueError("saved aggregate/receipt hash changed: " + relative)
        return self.cache[relative]


def public_binding(name, binding):
    if not isinstance(binding, dict):
        raise ValueError("source/code binding must be a metadata object")
    return {"name": name, "artifact": Path(binding.get("path", name)).name,
            **{field: binding[field] for field in ["sha256", "bytes"] if field in binding}}


def paired_summary(value):
    result = {field: value.get(field) for field in PAIR_FIELDS}
    for name in ["candidate_point_metrics", "control_literal_point_metrics"]:
        result[name] = {field: value.get(name, {}).get(field) for field in POINT_FIELDS}
    return result


def find_comparison(report, comparator):
    matches = [item for item in report["paired"]
               if item.get("comparator") == comparator and item.get("population") == "all_original_offered"
               and item.get("status") in {"primary", "secondary"}]
    if len(matches) != 1:
        raise ValueError("exactly one saved primary-point comparison required: " + comparator)
    return paired_summary(matches[0])


def coverage_summary(report):
    summary = report.get("candidate_summary", {})
    result = {field: summary.get(field) for field in ["population_rows", "supported_played_outcomes", "supported_played_zero_rows", "fallback_rows"]}
    for field in ["outcome_states", "fallback_reasons"]:
        result[field] = summary.get(field, {})
    result["history_states"] = {item["value"]: item["population_rows"] for item in report.get("subgroups", [])
                                if item.get("dimension") == "history_state"}
    return result


def model_hashes(freeze, target, panel):
    prefix = f"trials/{target}/{panel}/"
    bindings = freeze.get("bindings", {})
    names = ["model/model.joblib", "model/manifest.json", "prediction-manifest.json",
             "candidate-frozen.parquet", "ensemble-frozen.parquet", "role-prior-frozen.parquet", "query-leaves.npz"]
    return {name: bindings.get(prefix + name) for name in names}


def coherence_summary(reader, freeze):
    if not (reader.root / "coherence-audit.json").is_file():
        return None
    saved = reader.read("coherence-audit.json")
    if saved.get("forecast_freeze_sha256") != reader.hashes["forecast-freeze.json"]:
        raise ValueError("coherence audit is not bound to the saved forecast freeze")
    for name, expected in saved.get("bindings", {}).items():
        if freeze.get("bindings", {}).get(name) != expected:
            raise ValueError("coherence source binding differs from forecast freeze")
    fields = ["panel", "audit", "common_offers", "finite_pairs", "violations_gt_1e_9", "largest_excess",
              "combined_offers", "rush_offers", "rec_offers", "finite_triples", "combined_offers_without_both_components",
              "nonadditive_gt_0_03", "absolute_gap_mean", "absolute_gap_max"]
    return {"evidence": saved["evidence"], "source_aggregate_sha256": reader.hashes["coherence-audit.json"],
        "forecast_freeze_sha256": saved["forecast_freeze_sha256"], "audit_code_sha256": saved.get("audit_code_sha256"),
        "results": [{field: item[field] for field in fields if field in item} for item in saved["results"]],
        "interpretation": saved["interpretation"], "point_repairs": 0, "joint_law_claim": False}


def build_export(reader, completion_hash):
    completion = reader.read("completion.json", completion_hash)
    if completion.get("state") != "COMPLETED_DESCRIPTIVE":
        raise ValueError("successful completed-run receipt required before reading accuracy reports")
    registry = reader.read("registry.json")
    freeze = reader.read("forecast-freeze.json")
    runtime = reader.read("environment.json")
    top = reader.read("website-cdf-report.json")
    expected_slots = {(target, panel, family) for target in TARGETS for panel in ["base", "context"] for family in FAMILIES}
    actual = {(slot["target"], slot["panel"], slot["method_family"]) for slot in top["slots"]}
    if actual != expected_slots or len(top["slots"]) != 48:
        raise ValueError("complete fixed 48-slot all-category matrix required")
    indexed = {(slot["target"], slot["panel"], slot["method_family"]): slot for slot in top["slots"]}
    rows = []
    for target in TARGETS:
        for panel in ["base", "context"]:
            for family in FAMILIES:
                reader.check_time()
                slot = indexed[target, panel, family]
                row = {"target": target, "panel": panel, "method_family": family, "state": slot["state"],
                       "reason": slot.get("reason"), "model_and_forecast_hashes": model_hashes(freeze, target, panel)}
                if slot["state"] != "SCORED_DESCRIPTIVE":
                    row.update(website=None, raw=None, simple=None, coverage=None, point_semantics=None)
                    rows.append(row)
                    continue
                relative = f"trials/{target}/{panel}/" + ("report.json" if family == "pure_cdf" else "ensemble-report.json")
                report = reader.read(relative, slot["report_sha256"])
                if report.get("target") != target or report.get("method_family") != family:
                    raise ValueError("saved report target/family differs from planned slot")
                for method in ["website", "raw", "simple"]:
                    row[method] = find_comparison(report, method)
                if row["website"] != paired_summary(slot["primary"]):
                    raise ValueError("top-level and detailed saved primary aggregates differ")
                pure_slot = indexed[target, panel, "pure_cdf"]
                pure_report = reader.read(f"trials/{target}/{panel}/report.json", pure_slot["report_sha256"])
                row["coverage"] = coverage_summary(pure_report)
                row["coverage_semantics"] = "pure CDF component offered/outcome/fallback coverage; paired eligibility recorded separately for each method"
                row["ensemble_abstentions"] = {item["value"]: item["offered_rows"] for item in report.get("subgroups", [])
                                               if item.get("dimension") == "abstention"} if family == "website_equalweight" else None
                row["point_semantics"] = report.get("point_semantics", "same-law probability" if target == "anytime_td" else "same-law numeric median primary; mean secondary")
                row["secondary_mean_point_comparisons"] = [dict(paired_summary(item), comparator=item["comparator"])
                    for item in report.get("paired", []) if item.get("status") in {"secondary_same_law_mean", "secondary_mean_point_blend"}]
                row["proper_law_diagnostics"] = ({"distribution": pure_report.get("candidate_summary", {}).get("distribution"),
                    "role_prior_distribution": pure_report.get("role_prior_summary", {}).get("distribution"),
                    "distribution_vs_role_prior": pure_report.get("distribution_vs_role_prior", [])} if family == "pure_cdf"
                    else {"bernoulli_law": report.get("bernoulli_law")} if target == "anytime_td" else None)
                row["saved_control_diagnostics"] = []
                for item in pure_report.get("control_summaries", []):
                    entry = {field: item.get(field) for field in ["method", "offered_rows", "missing_points", "brier", "log_loss", "infinite_log_losses", "log_loss_state"]}
                    entry["literal_point"] = {field: item.get("literal_point", {}).get(field) for field in POINT_FIELDS}
                    row["saved_control_diagnostics"].append(entry)
                rows.append(row)
    source_bindings = [public_binding(name, value) for name, value in registry.get("inputs", {}).items()]
    source_bindings += [public_binding(name, value) for name, value in registry.get("source_bindings", {}).items()]
    if registry.get("prior_registry"):
        source_bindings.append(public_binding("prior_registry", registry["prior_registry"]))
    methods = []
    for target in TARGETS:
        category = registry["categories"][target]
        methods.append({field: category.get(field) for field in ["target", "state", "support", "modeled_roles", "primary_roles", "panels"]})
    reader.check_time()
    public_notes = registry.get("public_source_notes", [])
    if not isinstance(public_notes, list) or not all(isinstance(note, str) for note in public_notes):
        raise ValueError("optional public source notes must be prose strings, never row objects")
    coherence = coherence_summary(reader, freeze)
    return {"registration_id": top["registration_id"], "evidence": top["evidence"],
        "original_offered_rows": top["original_offered_rows"], "original_outcome_states": top["original_outcome_states"],
        "planned_primary_contrasts": 48, "planned_fit_attempts": 22, "blocked_ppr_contrasts": 4,
        "matrix": rows, "source_vintage_limits": LIMITS_TEXT,
        "public_source_notes": public_notes,
        "source_manifest": source_bindings, "method_manifest": methods,
        "runtime_manifest": {field: runtime.get(field) for field in ["python", "packages", "threads", "runtime_agent_configuration"]},
        "source_qualification_sha256": digest_bytes(json.dumps(top.get("source_qualification"), sort_keys=True, separators=(",", ":")).encode()),
        "model_parameter_schema": {"topology": {"class": "ExtraTreesRegressor", "n_estimators": 32, "criterion": "squared_error",
            "max_depth": 8, "min_samples_leaf": 30, "max_features": 1., "bootstrap": False, "random_state": 1701, "n_jobs": 2},
            "prior_weight": .05, "preprocessing": "training-only numeric medians, explicit missingness indicators, training-only role vocabulary",
            "law": "training-label terminal-leaf empirical marginal laws plus trained full-support role prior; cold/nonmodeled roles use entire role/global prior",
            "private_parameter_fields": ["numeric_medians", "categorical_roles", "role_priors", "global_prior", "tree_parameters", "leaf_histograms", "training_binding", "training_leaf_ids"],
            "training_label_or_leaf_values_exported": False},
        "replay_contract": {"replay_performed_by_exporter": False, "public_model_artifacts": False,
            "requires_private_frozen_artifacts": ["model.joblib", "query feature snapshot", "training/label/leaf provenance", "matching code/runtime/source hashes"],
            "semantics": "Hashes and parameter schemas identify retained private artifacts; this aggregate export does not generate forecasts, replay models, fit parameters, or rescore outcomes."},
        "coherence_audit": coherence,
        "code_manifest": [public_binding(Path(item["path"]).name, item) for item in registry.get("code_bindings", [])],
        "fixed_ensemble_design": top["ensemble_design"], "budgets": top["budget"],
        "model_hash_semantics": "Only saved artifact hashes; no model, training label, player-row, forecast-row, or raw-feed bytes exported",
        "aggregate_input_hashes": dict(reader.hashes), "new_qualified_replacements": [],
        "export_semantics": "Saved aggregate values copied verbatim; no new forecasts, losses, resampling, ranking, selection, or denominator changes"}


def formatted(value):
    if value is None:
        return "—"
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def markdown_report(exported):
    lines = ["# Original website CDF reconstruction", "", exported["evidence"], "",
             "All 12 categories, both fixed panels, and both method families are retained. Numeric primary error is MAE; anytime TD primary error is Brier. Each SITE/raw/simple comparison uses its own identical paired rows.", "",
             "| Category | Panel | Family | State | SITE n / games / weeks | Candidate error | SITE error | Improvement % | Raw n / candidate / raw error | Simple n / candidate / simple error |",
             "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in exported["matrix"]:
        site = row["website"]
        if site is None:
            values = [row["target"], row["panel"], row["method_family"], row["state"], "—", "—", "—", "—", "—", "—"]
        else:
            def control_cell(name):
                item = row[name]
                return " / ".join(formatted(item[field]) for field in ["paired_rows", "candidate_loss", "control_loss"])
            values = [row["target"], row["panel"], row["method_family"], row["state"],
                " / ".join(formatted(site[field]) for field in ["paired_rows", "games", "weeks"]),
                formatted(site["candidate_loss"]), formatted(site["control_loss"]), formatted(site["improvement_pct"]),
                control_cell("raw"), control_cell("simple")]
        lines.append("| " + " | ".join(values) + " |")
    lines += ["", "## Point diagnostics on the SITE paired cohort", "",
              "| Category | Panel | Family | Candidate RMSE / bias / p90 AE | SITE RMSE / bias / p90 AE | Offered / supported played / CDF fallback |",
              "|---|---|---|---:|---:|---:|"]
    for row in exported["matrix"]:
        if row["website"] is None:
            continue
        site, coverage = row["website"], row["coverage"]
        def diagnostics(name):
            return " / ".join(formatted(site[name].get(field)) for field in ["rmse", "bias_prediction_minus_actual", "absolute_error_p90"])
        counts = " / ".join(formatted(coverage.get(field)) for field in ["population_rows", "supported_played_outcomes", "fallback_rows"])
        lines.append("| " + " | ".join([row["target"], row["panel"], row["method_family"], diagnostics("candidate_point_metrics"), diagnostics("control_literal_point_metrics"), counts]) + " |")
    lines += ["", "## Source and evidence limits", ""] + ["- " + note for note in exported["source_vintage_limits"]]
    if exported.get("coherence_audit"):
        lines += ["", "## Technical coherence audit", "", exported["coherence_audit"]["interpretation"], "",
                  "| Panel | Audit | Common finite rows | Violations | Mean absolute gap | Maximum absolute gap | Combined offers without both components |",
                  "|---|---|---:|---:|---:|---:|---:|"]
        for item in exported["coherence_audit"]["results"]:
            lines.append("| " + " | ".join([item["panel"], item["audit"],
                formatted(item.get("finite_triples", item.get("finite_pairs"))),
                formatted(item.get("nonadditive_gt_0_03", item.get("violations_gt_1e_9"))),
                formatted(item.get("absolute_gap_mean")), formatted(item.get("absolute_gap_max")),
                formatted(item.get("combined_offers_without_both_components"))]) + " |")
        lines += ["", "This saved technical audit makes no new error-score or joint-law claim and applies no point repair."]
    lines += ["", "Exact aggregate inputs, source/code/model hashes, feature panels, proper-law diagnostics, outcome states, and fallback reasons are retained in aggregate-report.json and hash-manifest.json. No raw/player/model-label rows are included.", ""]
    return "\n".join(lines)


def export_aggregates(run_directory, output_directory, completion_sha256):
    if not re.fullmatch(r"[0-9a-f]{64}", completion_sha256):
        raise ValueError("exact successful completion receipt SHA256 required")
    output = Path(output_directory).resolve()
    run = Path(run_directory).resolve()
    if output.exists() or output.is_relative_to(run):
        raise ValueError("export destination must be a new directory outside immutable run outputs")
    reader = AggregateReader(run)
    exported = build_export(reader, completion_sha256)
    markdown = markdown_report(exported)
    reader.check_time()
    output.mkdir(parents=True, exist_ok=False)
    body = json.dumps(exported, indent=2, allow_nan=False) + "\n"
    (output / "aggregate-report.json").write_text(body)
    (output / "aggregate-report.md").write_text(markdown)
    if exported.get("coherence_audit"):
        (output / "coherence-audit.json").write_text(json.dumps(exported["coherence_audit"], indent=2, allow_nan=False) + "\n")
    manifest = {"aggregate_input_hashes": reader.hashes,
        "exporter_code_sha256": digest_bytes(Path(__file__).read_bytes()),
        "output_sha256": {"aggregate-report.json": digest_bytes(body.encode()), "aggregate-report.md": digest_bytes(markdown.encode())},
        "read_bytes": reader.bytes, "wall_seconds": time.monotonic() - reader.started,
        "maximum_wall_seconds": MAX_WALL_SECONDS, "row_data_reads": 0, "new_forecasts": 0, "new_scores": 0}
    if exported.get("coherence_audit"):
        manifest["output_sha256"]["coherence-audit.json"] = digest_bytes((output / "coherence-audit.json").read_bytes())
    (output / "hash-manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    reader.check_time()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory")
    parser.add_argument("new_export_directory")
    parser.add_argument("--completion-sha256", required=True)
    args = parser.parse_args()
    export_aggregates(args.run_directory, args.new_export_directory, args.completion_sha256)


if __name__ == "__main__":
    main()
