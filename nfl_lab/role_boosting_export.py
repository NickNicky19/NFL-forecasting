"""Export pinned saved aggregates only; no model, row, score or replay access."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import time

from .website_cdf_export import AggregateReader, POINT_FIELDS, digest_bytes

VERSION = "all12-role-count-boosting-v1-20261023"
TARGETS = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd",
           "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td")
VARIANTS = ("A", "B")
PERIODS = ("2022", "2023", "2024", "website_week6")
PRIMARY_PERIODS = ("pooled2022-2024", "website_week6")
COUNTS = {"pass_td", "pass_cmp", "pass_att", "pass_int", "rush_att", "rec"}
PASSING = {"pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int"}
ROLES = {"QB", "RB", "FB", "WR", "TE"}
METRICS = (*POINT_FIELDS, "mse")
COMPARATORS = {"old_hgb", "old_cdf", "pooled", "recent", "website", "raw", "simple"}
POPULATIONS = {"prior_primary_roles", "all_original_offered"}
STATES = {"SCORED_DESCRIPTIVE", "BLOCKED_CATEGORY_CONTRACT", "PREDICTION_FROZEN", "FAILED_CONSUMED",
          "SKIPPED_FAILED_ALIAS_SOURCE", "SKIPPED_CAMPAIGN_BUDGET", "SKIPPED_FIT_BUDGET",
          "SKIPPED_OUTPUT_BUDGET", "PARTIAL_OR_FAILED_RETAINED", "FAILED_RETAINED"}
OUTCOMES = {"played", "unknown", "DNP", "played_zero", "played_nonzero", "played_missing_statistic",
            "played_invalid_support", "missing_outcome", "quarantined", "exact_scoring_contract_blocked"}
FALLBACKS = {"", "none", "cold_start_role_prior", "nonmodeled_role_prior", "global_prior_unknown_role",
             "insufficient_modeled_training_role_prior", "single_class_binary_role_prior", "role_prior_control",
             "all_zero_count_role_prior", "no_supported_played_training_outcomes"}
TEAMS = set("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LAR LV MIA MIN NE NO NYG NYJ OAK PHI PIT SD SEA SF STL TB TEN WAS".split())
NUMERIC_SUMMARY = ("offered_rows", "scored_rows", "missing_points", "players", "games", "weeks", "brier")
PAIR_NUMBERS = ("offered_rows", "supported_played_rows", "paired_rows", "candidate_missing_rows", "control_missing_rows",
                "candidate_loss", "control_loss", "delta_candidate_minus_control", "improvement_pct",
                "players", "games", "weeks", "finite_common_rows")
LOG_NUMBERS = ("rows", "natural_log_loss", "infinite_log_losses", "finite_log_loss_sum", "finite_log_loss_count")
SOURCE_NUMBERS = ("candidate_offered_rows", "retained_control_offered_rows", "common_rows", "candidate_only_rows",
                  "control_only_rows", "raw_actual_conflicts_quarantined", "confirmed_participation_conflicts_quarantined",
                  "participation_qualification_changes", "old_missing_new_finite", "old_finite_new_missing")
BUDGET_FIELDS = ("maximum_candidate_fit_attempts", "maximum_threads", "campaign_wall_seconds", "campaign_cpu_seconds",
                 "per_trial_wall_seconds", "per_trial_cpu_seconds", "memory_bytes", "private_output_bytes",
                 "reporting_wall_reserve_seconds", "bootstrap_replicates", "score_passes")
NOTES = [
    "The new learner procedures use exactly the parent HGB NFL-only source packet. Older CDF/recent/pooled comparators retain separate source-change qualification and contradiction quarantines.",
    "All 2019-2025 and 2026 Week6 periods and source coverage are exposed. Current-vintage postgame reconstruction and assumed seven-day availability do not authenticate original publication, correction order or original SITE input vintage.",
    "Historical primary losses pool exact 2022-2024 paired rows in unchanged category primary_roles against frozen old HGB base. The mandatory all-offered view is secondary. Week6 primary is all original offers against literal SITE. Each comparator keeps its own exact cohort; common-all-controls diagnostics are separate.",
    "All 96 packages remain: 48 new model packages, 40 byte aliases and 8 blocked exact-PPR packages. At most136 new estimator attempts are permitted. Aliases are reused forecasts and are not new fits or independent validation. No context panel, blend, new feature or winning variant is selected.",
    "A changes six counts from L1/identity/clamp to Poisson loss/log link together. B versus A changes role partitioning including training medians and vocabulary. Passing yards A/B are unchanged old HGB forecast bytes and contribute zero new research gain. Full-training role/global priors and cold/nonmodeled routing remain fixed. All-zero counts and single-class binary groups use priors without pseudolabels.",
    "Numeric outputs remain point heuristics without a numeric predictive-law or conditional-mean accuracy claim. Only anytimeTD supplies a genuine event probability; logloss is not clipped. Unknown participation, played zeros, played missing statistics and all blocked offers remain explicit.",
    "Saved historical week/game intervals use500 fixed-seed replicates and are nominal95%, unadjusted and descriptive. Week6 has no intervals. No significance, untouched confirmation, prospective qualification or promotion follows.",
    "Coherence diagnostics use only common available completion/attempt or direct-combined/component forecasts. They do not create a summed candidate, new outcome score, joint law or borrowed performance gain.",
    "This exporter copies explicitly allowlisted aggregate metadata only. It does not import estimators, open row or model artifacts, fit, forecast, score, resample, replay or select results. Existing rec-half/H3/RB evidence and spent budgets remain unchanged.",
]


class MetadataReader(AggregateReader):
    def read(self, relative, expected_hash=None):
        relative = str(relative)
        fixed = {"completion.json", "registry.json", "forecast-freeze.json", "environment.json", "role-boosting-report.json"}
        cell = re.fullmatch(r"trials/([a-z_]+)/(A|B)/(2022|2023|2024|website_week6)/report\.json", relative)
        if relative not in fixed and (cell is None or cell.group(1) not in TARGETS):
            raise ValueError("only allowlisted aggregate/receipt JSON may be read")
        return super().read(relative, expected_hash)


def numbers(value, names):
    result = {}
    for name in names:
        if name not in value:
            continue
        item = value[name]
        if item is not None and (isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item)):
            raise ValueError("aggregate numeric field has invalid type: " + name)
        result[name] = item
    return result


def enum(value, allowed, *, default="other_or_unknown"):
    return value if isinstance(value, str) and value in allowed else default


def years(value):
    if not isinstance(value, list) or any(type(x) is not int or x not in {2022, 2023, 2024} for x in value):
        raise ValueError("only fixed evaluation years may be exported")
    return list(value)


def counts(value, allowed):
    return numbers(value, tuple(k for k in value if k in allowed))


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("exact SHA256 metadata required")
    return value


def binding(name, value):
    # Do not copy even private basenames from path-bearing metadata.
    return {"name": name, "sha256": hash_value(value["sha256"]), **numbers(value, ("bytes",))}


def reliability(value):
    return [{**numbers(x, ("bin", "lower_inclusive", "upper", "rows", "mean_probability", "observed_rate")),
             "upper_inclusive": x.get("upper_inclusive") is True} for x in value]


def log_summary(value):
    return {**numbers(value, LOG_NUMBERS),
            "log_loss_state": enum(value.get("log_loss_state"), {"finite", "positive_infinity", "unavailable"}),
            "probability_clipping": "none"}


def summary(value):
    result = {**numbers(value, NUMERIC_SUMMARY), "point_metrics": numbers(value.get("point_metrics", {}), METRICS),
              "outcome_states": counts(value.get("outcome_states", {}), OUTCOMES)}
    if "log_loss_state" in value:
        result.update(log_summary(value))
    if "reliability_deciles" in value:
        result["reliability_deciles"] = reliability(value["reliability_deciles"])
    return result


def interval(value):
    result = numbers(value, ("paired_rows", "clusters", "mean_delta_candidate_minus_control", "replicates", "seed",
                             "monte_carlo_tail_probability_se"))
    result["cluster"] = enum(value.get("cluster"), {"week", "game"})
    result["primary_roles_only"] = value.get("primary_roles_only") is True
    result["primary_loss"] = enum(value.get("primary_loss"), {"mae", "point_mae", "brier"})
    bounds = value.get("interval")
    if bounds is not None and (not isinstance(bounds, list) or len(bounds) != 2):
        raise ValueError("saved aggregate interval must have two bounds")
    result["interval"] = None if bounds is None else [numbers({"bound": x}, ("bound",))["bound"] for x in bounds]
    for name in ("candidate_years", "control_years", "compared_complete_years", "excluded_unpaired_years"):
        if name in value:
            result[name] = years(value[name])
    result["semantics"] = "saved nominal unadjusted descriptive historical interval"
    return result


def pair(value, *, period=None):
    result = numbers(value, PAIR_NUMBERS)
    result.update(population=enum(value.get("population"), POPULATIONS),
                  comparator=enum(value.get("comparator"), COMPARATORS),
                  status=enum(value.get("status"), {"primary", "secondary", "secondary_common_all_controls", "secondary_A_B_all_controls_common_cohort"}),
                  primary_loss=enum(value.get("primary_loss"), {"mae", "point_mae", "brier"}))
    for name in ("candidate_point_metrics", "control_literal_point_metrics"):
        result[name] = numbers(value.get(name, {}), METRICS)
    if "intervals" in value:
        if period == "website_week6" and value["intervals"]:
            raise ValueError("Week6 intervals are not permitted")
        result["intervals"] = [interval(x) for x in value["intervals"]]
    if "paired_binary" in value:
        binary = value["paired_binary"]
        result["paired_binary"] = {k: log_summary(binary.get(k, {})) for k in ("candidate", "control")}
        for k in ("candidate_reliability_deciles", "control_reliability_deciles"):
            result["paired_binary"][k] = reliability(binary.get(k, []))
    if value.get("comparison") == "B_minus_A":
        result["comparison"] = "B_minus_A"
    if value.get("target") in TARGETS:
        result["target"] = value["target"]
    if value.get("period") in PERIODS:
        result["period"] = value["period"]
    if value.get("variant") in VARIANTS:
        result["variant"] = value["variant"]
    return result


def availability(value):
    allowed = {"N/A_not_recorded_for_exact_panel", "literal_original_offer_values; per-comparator paired/missing counts below",
               "literal_original_offers; exact paired/missing counts in each cell"}
    return {key: enum(value[key], allowed) for key in ("website", "raw", "simple") if key in value}


def source_comparison(value):
    result = {**numbers(value, SOURCE_NUMBERS), "method": enum(value.get("method"), COMPARATORS)}
    for name in ("candidate_participation_states", "retained_participation_states", "candidate_outcome_states", "retained_outcome_states"):
        result[name] = counts(value.get(name, {}), OUTCOMES)
    if "retained_source_binding" in value:
        result["retained_source_binding"] = binding("frozen_" + result["method"], value["retained_source_binding"])
    result["qualification"] = "retained strict source-change common-pair quarantine; original cutoff may be unverified"
    return result


def group_label(dimension, value):
    allowed = {"position": ROLES, "team": TEAMS, "opponent": TEAMS, "fallback": FALLBACKS,
               "history_state": {"cold_or_unknown", "warm"}, "outcome_state": OUTCOMES,
               "season": {"2022", "2023", "2024", "2026"}}
    return enum(value, allowed[dimension])


def report_summary(value, period):
    result = {"target": value["target"], "variant": value["variant"], "summary": summary(value.get("summary", {})),
              "paired": [pair(x, period=period) for x in value.get("paired", [])],
              "common_all_controls": [pair(x, period=period) for x in value.get("common_all_controls", [])],
              "source_comparisons": [source_comparison(x) for x in value.get("source_comparisons", [])],
              "comparator_availability": availability(value.get("comparator_availability", {})), "subgroups": []}
    for name in ("compared_complete_years", "excluded_years"):
        if name in value:
            result[name] = years(value[name])
    if "role_prior" in value:
        result["role_prior"] = summary(value["role_prior"])
    for item in value.get("subgroups", []):
        dimension = item.get("dimension")
        if dimension in {"position", "season", "team", "opponent", "fallback", "history_state", "outcome_state"}:
            result["subgroups"].append({"dimension": dimension, "value": group_label(dimension, item.get("value")), **summary(item)})
    return result


def package_kind(target, variant):
    if target == "fantasy_ppr":
        return "blocked"
    if variant == "A":
        return "model" if target in COUNTS else "old_base_alias"
    return "A_alias" if target in PASSING else "model"


def status(value):
    result = {k: value[k] for k in ("target", "variant", "period")}
    expected = package_kind(value["target"], value["variant"])
    if value.get("kind") != expected or value.get("state") not in STATES:
        raise ValueError("package kind/status differs from the fixed matrix")
    result.update(kind=expected, state=value["state"], reused_alias=expected in {"old_base_alias", "A_alias"})
    result.update(numbers(value, ("fit_attempts", "blocked_subfit_slots", "returncode", "wall_seconds", "cpu_seconds", "sampled_peak_process_group_rss_bytes")))
    if expected != "model" and value.get("fit_attempts", 0) != 0:
        raise ValueError("aliases and blocked packages cannot claim estimator fits")
    if "report_sha256" in value:
        result["report_sha256"] = hash_value(value["report_sha256"])
    if value.get("reason") is not None:
        result["retained_private_reason_sha256"] = digest_bytes(str(value["reason"]).encode())
    return result


def forecast_hashes(freeze, target, variant, period):
    prefix = f"trials/{target}/{variant}/{period}/"
    labels = {"candidate-frozen.parquet": "candidate_forecast_sha256", "old-hgb-frozen.parquet": "old_hgb_forecast_sha256",
              "role-prior-frozen.parquet": "role_prior_forecast_sha256", "prediction-manifest.json": "prediction_manifest_sha256",
              "alias.json": "alias_metadata_sha256"}
    return {label: hash_value(freeze.get("bindings", {})[prefix + name]) for name, label in labels.items()
            if prefix + name in freeze.get("bindings", {})}


def coherence(value):
    result = {"variant": enum(value.get("variant"), set(VARIANTS)), "period": enum(value.get("period"), set(PERIODS)),
              "audit": enum(value.get("audit"), {"completion_minus_attempt", "direct_combined_minus_components"}),
              **numbers(value, ("offered_union_rows", "common_available_rows", "missing_component_rows", "games", "weeks", "mean_point_gap", "max_absolute_gap", "positive_gap_rows")),
              "absent_or_missing_by_target": counts(value.get("absent_or_missing_by_target", {}), set(TARGETS))}
    if value.get("state") == "NO_PACKAGES":
        result["state"] = "NO_PACKAGES"
    return result


def matrix(values, expected, dimensions, label):
    keys = [tuple(x[k] for k in dimensions) for x in values]
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError("complete fixed " + label + " required")
    return dict(zip(keys, values))


def public_input_hashes(reader):
    result = {}
    for name, sha in reader.hashes.items():
        cell = re.fullmatch(r"trials/([a-z_]+)/(A|B)/(2022|2023|2024|website_week6)/report\.json", name)
        label = "cell:" + ":".join(cell.groups()) if cell else "receipt:" + name.removesuffix(".json").replace("-", "_")
        result[label] = sha
    return result


def build_export(reader, completion_sha256, report_sha256):
    completion = reader.read("completion.json", completion_sha256)
    if completion.get("state") != "COMPLETED_DESCRIPTIVE" or completion.get("reporting", {}).get("returncode") != 0 or completion.get("score_pass_consumed") is not True:
        raise ValueError("pinned successful completed-run receipt required before accuracy reads")
    top = reader.read("role-boosting-report.json", report_sha256)
    registry, freeze, runtime = reader.read("registry.json"), reader.read("forecast-freeze.json"), reader.read("environment.json")
    if top.get("registration_id") != VERSION or registry.get("registration_id") != VERSION:
        raise ValueError("wrong role/count study registration")
    if registry.get("study_source_relation") != "same_exact_parent_hgb_input_packet" or top.get("study_source_relation") != registry["study_source_relation"]:
        raise ValueError("explicit same-parent-HGB source attribution required")
    if registry.get("ensemble_design", {}).get("enabled") is not False or registry.get("ensemble_design", {}).get("additional_fits") != 0:
        raise ValueError("blends must remain disabled")
    totals = {"planned_packages": 96, "planned_new_model_packages": 48, "planned_alias_packages": 40,
              "blocked_ppr_packages": 8, "primary_contrast_slots": 48, "blocked_ppr_primary_contrasts": 4,
              "maximum_estimator_attempts": 136, "score_passes": 1}
    if any(top.get(k) != v for k, v in totals.items()):
        raise ValueError("fixed package/estimator budget metadata changed")
    expected_cells = {(t, v, p) for t in TARGETS for v in VARIANTS for p in PERIODS}
    index = matrix(top["slots"], expected_cells, ("target", "variant", "period"), "96 package statuses")
    matrix(completion["statuses"], expected_cells, ("target", "variant", "period"), "96 completion statuses")
    expected_primary = {(t, v, p) for t in TARGETS for v in VARIANTS for p in PRIMARY_PERIODS}
    primary = matrix(top["primary_slots"], expected_primary, ("target", "variant", "period"), "48 primary slots")
    if sum(x["target"] == "fantasy_ppr" and x["state"] == "BLOCKED_CATEGORY_CONTRACT" for x in top["slots"]) != 8:
        raise ValueError("all eight exact-PPR packages must remain blocked")
    if sum(x["target"] == "fantasy_ppr" and x["state"] == "BLOCKED_CATEGORY_CONTRACT" for x in top["primary_slots"]) != 4:
        raise ValueError("all four exact-PPR primary slots must remain blocked")
    if set(registry["categories"]) != set(TARGETS):
        raise ValueError("all twelve category contracts required")
    matrix(top.get("coherence", []), {(v, p, a) for v in VARIANTS for p in PERIODS
           for a in ("completion_minus_attempt", "direct_combined_minus_components")},
           ("variant", "period", "audit"), "16 coherence summaries")
    methods = []
    for target in TARGETS:
        category = registry["categories"][target]
        methods.append({"target": target, "state": enum(category.get("state"), {"READY", "BLOCKED_LABEL_CONTRACT"}),
                        "support": enum(category.get("support"), {"count", "signed_integer", "fractional_ppr", "bernoulli"}),
                        "modeled_roles": [enum(x, ROLES) for x in category["modeled_roles"]],
                        "primary_roles": [enum(x, ROLES) for x in category["primary_roles"]],
                        "used_feature_panel": "base", "numeric_feature_count": len(category.get("panels", {}).get("base", []))})
    primary_matrix = []
    for target in TARGETS:
        for variant in VARIANTS:
            for period in PRIMARY_PERIODS:
                saved = primary[target, variant, period]
                row = {"target": target, "variant": variant, "period": period,
                       "state": enum(saved.get("state"), STATES),
                       "primary_roles": next(x["primary_roles"] for x in methods if x["target"] == target),
                       "primary": pair(saved["primary"], period=period) if saved.get("primary") is not None else None}
                if "compared_complete_years" in saved:
                    row["compared_complete_years"] = years(saved["compared_complete_years"])
                if row["primary"] is not None:
                    wanted = ("old_hgb", "prior_primary_roles") if period == "pooled2022-2024" else ("website", "all_original_offered")
                    if (row["primary"]["comparator"], row["primary"]["population"]) != wanted:
                        raise ValueError("primary comparator/population changed")
                primary_matrix.append(row)
    cells = []
    for period in PERIODS:
        for target in TARGETS:
            for variant in VARIANTS:
                saved = index[target, variant, period]
                row = {**status(saved), "forecast_hashes": forecast_hashes(freeze, target, variant, period), "aggregate": None}
                if saved["state"] == "SCORED_DESCRIPTIVE":
                    detailed = reader.read(f"trials/{target}/{variant}/{period}/report.json", saved["report_sha256"])
                    if detailed.get("target") != target or detailed.get("variant") != variant or detailed.get("period") != period:
                        raise ValueError("cell aggregate identity differs")
                    row["aggregate"] = report_summary(detailed, period)
                    if period == "website_week6":
                        matches = [x for x in row["aggregate"]["paired"] if x["status"] == "primary"]
                        wanted = primary[target, variant, period].get("primary")
                        if matches != ([pair(wanted, period=period)] if wanted else []):
                            raise ValueError("website top/detail primary differs")
                cells.append(row)
    pooled = []
    for item in top.get("historical_pooled", []):
        if item.get("target") not in TARGETS or item.get("variant") not in VARIANTS:
            raise ValueError("pooled aggregate identity differs")
        report = report_summary(item, "pooled2022-2024")
        actual = [x for x in report["paired"] if x["status"] == "primary"]
        wanted = primary[item["target"], item["variant"], "pooled2022-2024"].get("primary")
        if actual != ([pair(wanted, period="pooled2022-2024")] if wanted else []):
            raise ValueError("historical top/detail primary differs")
        pooled.append(report)
    for row in primary_matrix:
        if row["period"] == "pooled2022-2024" and row["primary"] is not None and sum(x["target"] == row["target"] and x["variant"] == row["variant"] for x in pooled) != 1:
            raise ValueError("every available pooled primary requires one detail")
    sources = [binding(name, registry["inputs"][name]) for name in ("training_features", "query_features", "opportunities", "outcomes")]
    sources += [binding(name, registry[name]) for name in ("source_contract", "prior_registry", "website_registry", "parent_boosting_registry") if name in registry]
    model = top.get("model_design", {})
    budgets = numbers(top.get("budgets", {}), BUDGET_FIELDS)
    return {"registration_id": VERSION, "evidence": "Exposed source-constant role/count learner research; pinned saved aggregates only",
            "study_source_relation": "same_exact_parent_hgb_input_packet",
            "old_secondary_controls": "retained source-change qualification and quarantine",
            **totals, **numbers(top, ("original_opportunity_rows", "blocked_ppr_subfit_slots")),
            "primary_matrix": primary_matrix, "package_matrix": cells, "historical_pooled": pooled,
            "role_loss_ablations": [pair(x, period=x.get("period")) for x in top.get("role_loss_ablations", [])],
            "common_cohort_diagnostics": [pair(x, period=x.get("period")) for x in top.get("common_cohort_diagnostics", [])],
            "comparator_availability": {p: availability(top.get("comparator_availability", {}).get(p, {})) for p in PERIODS},
            "coherence": [coherence(x) for x in top.get("coherence", [])], "method_manifest": methods,
            "source_manifest": sources,
            "code_manifest": [binding("bound_code_" + str(i + 1), x) for i, x in enumerate(registry.get("code_bindings", []))],
            "model_parameter_schema": {"parameters": numbers(model.get("parameters", {}), ("max_iter", "learning_rate", "max_leaf_nodes", "max_depth", "min_samples_leaf", "l2_regularization", "random_state")),
                                       "early_stopping": model.get("parameters", {}).get("early_stopping") is True,
                                       **numbers(model, ("threads", "minimum_modeled_rows", "maximum_estimator_attempts")),
                                       "count_loss": "poisson", "count_link": "log", "signed_loss": "absolute_error", "binary_loss": "log_loss",
                                       "private_values_exported": False, "numeric_distribution": "none"},
            "budgets": budgets,
            "cumulative_budget": {**numbers(registry.get("cumulative_budget_amendment", {}), ("prior_audited_completed_fit_lower_bound", "new_maximum_estimator_fit_attempts", "A_count_maximum", "B_skill_role_maximum", "B_binary_role_maximum")),
                                  "prior_count_is_not_an_exact_lifetime_total": registry.get("cumulative_budget_amendment", {}).get("prior_count_is_not_an_exact_lifetime_total") is True,
                                  "old_88_fit_study_spent": registry.get("cumulative_budget_amendment", {}).get("old_88_fit_study_spent") is True},
            "completion": {"state": "COMPLETED_DESCRIPTIVE", "score_pass_consumed": True, **numbers(completion, ("fit_attempts_consumed", "wall_seconds", "cpu_seconds", "output_bytes_before_completion"))},
            "runtime_manifest": {"threads": numbers(runtime, ("threads",)).get("threads"), "actual_agent_configuration": "not independently observed by metadata exporter"},
            "source_and_evidence_limits": NOTES, "aggregate_input_hashes": public_input_hashes(reader),
            "new_qualified_replacements": [], "technical_replay_performed_by_exporter": False,
            "export_semantics": "Explicit aggregate field allowlists only; no row/model/label reads, fits, forecasts, scores, resampling, replay or selection"}


def markdown_report(value):
    lines = ["# Role and count boosting research", "", value["evidence"], "",
             "Historical primary: unchanged primary roles versus old HGB. Week6 primary: all original offers versus SITE. Numeric loss is MAE; anytime TD loss is Brier.", "",
             "| Category | Variant | Period | State | Comparator | Pairs / games / weeks | Candidate | Control | Delta |",
             "|---|---|---|---|---|---:|---:|---:|---:|"]
    def cell(x):
        return "—" if x is None else f"{x:.5g}" if isinstance(x, float) else str(x)
    for row in value["primary_matrix"]:
        p = row["primary"] or {}
        vals = [row["target"], row["variant"], row["period"], row["state"], p.get("comparator"),
                " / ".join(cell(p.get(x)) for x in ("paired_rows", "games", "weeks")), p.get("candidate_loss"), p.get("control_loss"), p.get("delta_candidate_minus_control")]
        lines.append("| " + " | ".join(cell(x) for x in vals) + " |")
    lines += ["", "## Coverage and secondary comparisons", "", "JSON retains all96 package statuses, all saved comparator-specific losses, primary-role and all-offered views, common-all-controls diagnostics, MSE/RMSE/bias/p95 tails, coarse groups and coherence summaries. Aliases are reused forecasts; blocked PPR and failures remain visible.", ""]
    lines += ["- " + text for text in NOTES]
    return "\n".join(lines) + "\n"


def export_aggregates(run_directory, output_directory, completion_sha256, report_sha256):
    hash_value(completion_sha256)
    hash_value(report_sha256)
    run, output = Path(run_directory).resolve(), Path(output_directory).resolve()
    if output.exists() or output.is_relative_to(run):
        raise ValueError("export destination must be a new directory outside immutable run outputs")
    reader = MetadataReader(run)
    exported = build_export(reader, completion_sha256, report_sha256)
    body = json.dumps(exported, indent=2, allow_nan=False) + "\n"
    markdown = markdown_report(exported)
    reader.check_time()
    output.mkdir(parents=True, exist_ok=False)
    (output / "aggregate-report.json").write_text(body)
    (output / "aggregate-report.md").write_text(markdown)
    manifest = {"aggregate_input_hashes": public_input_hashes(reader), "successful_completion_sha256": completion_sha256,
                "successful_report_sha256": report_sha256, "exporter_code_sha256": digest_bytes(Path(__file__).read_bytes()),
                "reader_code_sha256": digest_bytes(Path(__file__).with_name("website_cdf_export.py").read_bytes()),
                "output_sha256": {"aggregate-report.json": digest_bytes(body.encode()), "aggregate-report.md": digest_bytes(markdown.encode())},
                "read_bytes": reader.bytes, "wall_seconds": time.monotonic() - reader.started,
                "row_data_reads": 0, "model_data_reads": 0, "new_fits": 0, "new_forecasts": 0, "new_scores": 0,
                "resampling_passes": 0, "technical_replay_performed": False}
    (output / "hash-manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    reader.check_time()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory")
    parser.add_argument("output_directory")
    parser.add_argument("--completion-sha256", required=True)
    parser.add_argument("--report-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(export_aggregates(args.run_directory, args.output_directory, args.completion_sha256, args.report_sha256), allow_nan=False))


if __name__ == "__main__":
    main()
