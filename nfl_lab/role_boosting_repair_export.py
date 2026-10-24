"""Export aggregate JSON from one zero-fit repair while retaining original failure.

The original exporter and study are unchanged. Only allowlisted saved aggregate
reports and receipts are read; no estimator, prediction, outcome-row or replay
module is imported. Original and repair completion states stay distinct.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from .role_boosting_export import (
    BUDGET_FIELDS, NOTES, PERIODS, PRIMARY_PERIODS, ROLES, STATES, TARGETS,
    VARIANTS, VERSION as SOURCE_VERSION, availability, binding, coherence,
    digest_bytes, enum, forecast_hashes, hash_value, matrix, numbers, pair,
    public_input_hashes, report_summary, status, years,
    markdown_report as original_markdown_report,
)
from .website_cdf_export import AggregateReader, MAX_INPUT_BYTES

VERSION = "role-count-reporting-repair-v1-20261023"
SUCCESS = "COMPLETED_REPORTING_REPAIR_DESCRIPTIVE"
ORIGINAL_FAILURE = "INCOMPLETE_RETAINED_NO_RESTART"
REPAIR_BUDGET_FIELDS = (
    "maximum_candidate_fit_attempts", "maximum_prediction_calls", "report_attempts",
    "wall_seconds", "cpu_seconds", "maximum_threads", "memory_bytes",
    "combined_private_output_bytes",
)
REPAIR_NOTES = [
    "The original study remains INCOMPLETE_RETAINED_NO_RESTART after 136 fits and one failed, consumed reporting phase. Its registry, forecast freeze and failed completion remain pinned.",
    "A separately registered repair reuses the original frozen forecasts and report definitions. It consumes one additional reporting/scoring phase: two cumulative phases, zero new fits, predictions or independent observations. Successful repair reporting does not make the original attempt successful.",
    "Original registered budgets below are historical settings, including one original score pass. They do not replace the cumulative two consumed reporting/scoring phases.",
]


class MetadataReader(AggregateReader):
    """Bound both receipt roots to a shared JSON-only input and wall budget."""
    def __init__(self, root, kind, budget=None):
        super().__init__(root)
        self.kind = kind
        self.budget = budget if budget is not None else {"bytes": 0, "started": self.started}
        self.started = self.budget["started"]

    def read(self, relative, expected_hash=None):
        relative = str(relative)
        fixed = ({"completion.json", "registry.json", "forecast-freeze.json", "environment.json", "score-consumed.json"}
                 if self.kind == "source" else
                 {"completion.json", "repair-registry.json", "repair-consumed.json", "role-boosting-report.json"})
        cell = re.fullmatch(r"trials/([a-z_]+)/(A|B)/(2022|2023|2024|website_week6)/report\.json", relative)
        if relative not in fixed and not (self.kind == "repair" and cell and cell.group(1) in TARGETS):
            raise ValueError("only allowlisted aggregate/receipt JSON may be read")
        if expected_hash is not None:
            hash_value(expected_hash)
        # Reject escapes before stat and enforce one aggregate input budget.
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("metadata path escapes receipt root")
        if relative not in self.cache and self.budget["bytes"] + path.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("combined aggregate JSON input budget exceeded")
        before = self.bytes
        try:
            return super().read(relative, expected_hash)
        finally:
            self.budget["bytes"] += self.bytes - before


def exact(value, expected, label):
    if type(value) is not type(expected) or value != expected:
        raise ValueError("fixed repair metadata differs: " + label)


def validate_provenance(value):
    expected = {
        "repair_registration_id": VERSION, "source_registration_id": SOURCE_VERSION,
        "original_state": ORIGINAL_FAILURE, "original_fit_attempts_consumed": 136,
        "original_score_pass_consumed": True, "original_failed_report_attempts": 1,
        "repair_report_attempts_consumed": 1, "cumulative_report_attempts": 2,
        "new_fits": 0, "new_predictions": 0, "new_independent_observations": 0,
    }
    for key, wanted in expected.items():
        exact(value.get(key), wanted, key)
    for key in ("source_registry_sha256", "source_freeze_sha256",
                "source_failed_completion_sha256", "source_consumed_marker_sha256"):
        expected[key] = hash_value(value.get(key))
    expected["key_repair"] = "existing normalize_keys on derived scored frames only"
    exact(value.get("key_repair"), expected["key_repair"], "key_repair")
    return expected


def repair_completion(value):
    return {"state": SUCCESS, "original_state": ORIGINAL_FAILURE,
            "source_files_unchanged": True, "original_fit_attempts_consumed": 136,
            "new_fit_attempts_consumed": 0, "new_prediction_calls": 0,
            "original_failed_report_attempts": 1, "repair_report_attempts_consumed": 1,
            "cumulative_report_attempts": 2,
            "reporting": {"returncode": 0, **numbers(value["reporting"],
                ("wall_seconds", "cpu_seconds", "sampled_peak_combined_rss_bytes"))},
            **numbers(value, ("output_bytes_before_completion", "combined_private_output_bytes_before_completion"))}


def input_hashes(reader, source_reader):
    return {**{"repair:" + key: value for key, value in public_input_hashes(reader).items()},
            **{"source:" + key: value for key, value in public_input_hashes(source_reader).items()}}


def gated_inputs(reader, source_reader, completion_sha256, report_sha256):
    completion = reader.read("completion.json", completion_sha256)
    for key, wanted in {"registration_id": VERSION, "state": SUCCESS,
            "source_files_unchanged": True, "original_fit_attempts_consumed": 136,
            "new_fit_attempts_consumed": 0, "new_prediction_calls": 0,
            "repair_report_attempts_consumed": 1, "cumulative_report_attempts": 2}.items():
        exact(completion.get(key), wanted, "successful repair completion " + key)
    exact(completion.get("reporting", {}).get("returncode"), 0, "repair returncode")
    exact(completion["reporting"].get("reason"), None, "repair reporting reason")
    provenance = validate_provenance(completion.get("repair_provenance", {}))
    repair_registry = reader.read("repair-registry.json")
    repair_marker = reader.read("repair-consumed.json")
    exact(repair_registry.get("registration_id"), VERSION, "repair registry registration")
    exact(repair_marker.get("repair_registry_sha256"), reader.hashes["repair-registry.json"], "repair registry consumed hash")
    for key, wanted in {"report_attempts": 1, "new_fits": 0, "new_predictions": 0}.items():
        exact(repair_marker.get(key), wanted, "repair consumption " + key)
    expected_files = repair_registry.get("source_file_sha256", {})
    source_bindings = {"registry.json": "source_registry_sha256", "forecast-freeze.json": "source_freeze_sha256",
                       "completion.json": "source_failed_completion_sha256", "score-consumed.json": "source_consumed_marker_sha256"}
    source = {}
    for filename, key in source_bindings.items():
        exact(expected_files.get(filename), provenance[key], filename + " provenance")
        source[filename] = source_reader.read(filename, provenance[key])
    exact(repair_registry.get("source_registry", {}).get("sha256"), provenance["source_registry_sha256"], "sealed source registry")
    old = source["completion.json"]
    exact(old.get("state"), ORIGINAL_FAILURE, "original failed state")
    exact(old.get("fit_attempts_consumed"), 136, "original consumed fits")
    exact(old.get("score_pass_consumed"), True, "original consumed report phase")
    exact(old.get("reporting", {}).get("returncode"), 1, "original failed reporting returncode")
    exact(completion.get("source_statuses"), old.get("statuses"), "original package statuses")
    freeze, marker = source["forecast-freeze.json"], source["score-consumed.json"]
    exact(freeze.get("fit_attempts"), 136, "frozen original fits")
    exact(freeze.get("packages"), 96, "frozen original packages")
    exact(marker.get("score_passes"), 1, "original consumed score phase")
    exact(marker.get("forecast_freeze_sha256"), provenance["source_freeze_sha256"], "consumed forecast freeze")
    runtime = source_reader.read("environment.json", hash_value(expected_files.get("environment.json")))
    top = reader.read("role-boosting-report.json", report_sha256)
    exact(top.get("repair_registration_id"), VERSION, "repair report registration")
    exact(top.get("cumulative_report_attempts"), 2, "report cumulative phases")
    exact(validate_provenance(top.get("repair_provenance", {})), provenance, "report/completion provenance")
    exact(top.get("repair_budgets"), repair_registry.get("budgets"), "repair budget binding")
    budgets = top.get("repair_budgets", {})
    for key, wanted in {"maximum_candidate_fit_attempts": 0, "maximum_prediction_calls": 0, "report_attempts": 1}.items():
        exact(budgets.get(key), wanted, "zero-fit repair budget " + key)
    return completion, top, source["registry.json"], freeze, runtime, old, provenance


def build_export(reader, source_reader, completion_sha256, report_sha256):
    completion, top, registry, freeze, runtime, old, provenance = gated_inputs(
        reader, source_reader, completion_sha256, report_sha256)
    if top.get("registration_id") != SOURCE_VERSION or registry.get("registration_id") != SOURCE_VERSION:
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
    matrix(old["statuses"], expected_cells, ("target", "variant", "period"), "96 completion statuses")
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
    exported = {"registration_id": SOURCE_VERSION, "evidence": "Exposed source-constant role/count learner research; pinned saved aggregates only",
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
            "completion": repair_completion(completion),
            "runtime_manifest": {"threads": numbers(runtime, ("threads",)).get("threads"), "actual_agent_configuration": "not independently observed by metadata exporter"},
            "source_and_evidence_limits": [*REPAIR_NOTES, *NOTES], "aggregate_input_hashes": input_hashes(reader, source_reader),
            "new_qualified_replacements": [], "technical_replay_performed_by_exporter": False,
            "export_semantics": "Explicit aggregate field allowlists only; no row/model/label reads, fits, forecasts, scores, resampling, replay or selection"}

    original_statuses = matrix(old["statuses"], expected_cells, ("target", "variant", "period"), "96 original statuses")
    exact(sum(item.get("fit_attempts", 0) for item in original_statuses.values()), 136, "all original package fits")
    exact(sum(item.get("state") == "PREDICTION_FROZEN" for item in original_statuses.values()), 88, "original frozen packages")
    for key, saved in index.items():
        before = original_statuses[key]
        exact(saved.get("kind"), before.get("kind"), "retained package kind")
        exact(saved.get("fit_attempts", 0), before.get("fit_attempts", 0), "retained package fits")
        expected_state = "SCORED_DESCRIPTIVE" if before["state"] == "PREDICTION_FROZEN" else before["state"]
        exact(saved.get("state"), expected_state, "retained package state")
    exported.update(
        registration_id=VERSION, source_registration_id=SOURCE_VERSION,
        evidence="Exposed role/count research aggregates from a separately registered zero-fit reporting repair; original reporting failure retained",
        repair_provenance=provenance,
        original_completion={"state": ORIGINAL_FAILURE, "fit_attempts_consumed": 136,
                             "score_pass_consumed": True, "reporting_returncode": 1},
        original_registered_score_passes=1, score_passes=2, cumulative_report_attempts=2,
        original_fit_attempts_consumed=136, new_fit_attempts_consumed=0,
        new_prediction_calls=0, new_independent_observations=0,
        original_registered_budgets=exported.pop("budgets"),
        repair_budgets=numbers(top.get("repair_budgets", {}), REPAIR_BUDGET_FIELDS),
        aggregate_input_hashes=input_hashes(reader, source_reader),
    )
    return exported


def markdown_report(value):
    rendered = original_markdown_report(value).splitlines()
    introduction = ["# Role and count reporting repair", "", value["evidence"], "",
        "Original attempt: INCOMPLETE_RETAINED_NO_RESTART; 136 consumed fits; reporting failed.",
        "Repair: COMPLETED_REPORTING_REPAIR_DESCRIPTIVE; 0 new fits; 0 predictions; 0 independent observations.",
        "Consumed reporting/scoring phases: 1 failed original + 1 repair = 2 cumulative phases. Original registered score passes: 1.", ""]
    return "\n".join(introduction + rendered[4:] + ["", *REPAIR_NOTES]) + "\n"


def export_aggregates(source_run_directory, repair_run_directory, output_directory, completion_sha256, report_sha256):
    hash_value(completion_sha256)
    hash_value(report_sha256)
    source, repair, output = (Path(p).resolve() for p in (source_run_directory, repair_run_directory, output_directory))
    if source == repair or source.is_relative_to(repair) or repair.is_relative_to(source):
        raise ValueError("separate original and repair receipt roots required")
    if output.exists() or output.is_relative_to(source) or output.is_relative_to(repair):
        raise ValueError("export destination must be a new directory outside immutable run outputs")
    budget = {"bytes": 0, "started": time.monotonic()}
    source_reader = MetadataReader(source, "source", budget)
    reader = MetadataReader(repair, "repair", budget)
    exported = build_export(reader, source_reader, completion_sha256, report_sha256)
    body = json.dumps(exported, indent=2, allow_nan=False) + "\n"
    markdown = markdown_report(exported)
    reader.check_time()
    output.mkdir(parents=True, exist_ok=False)
    (output / "aggregate-report.json").write_text(body)
    (output / "aggregate-report.md").write_text(markdown)
    manifest = {"registration_id": VERSION, "source_registration_id": SOURCE_VERSION,
        "aggregate_input_hashes": input_hashes(reader, source_reader),
        "successful_repair_completion_sha256": completion_sha256, "successful_repair_report_sha256": report_sha256,
        "original_failed_completion_sha256": exported["repair_provenance"]["source_failed_completion_sha256"],
        "original_forecast_freeze_sha256": exported["repair_provenance"]["source_freeze_sha256"],
        "exporter_code_sha256": digest_bytes(Path(__file__).read_bytes()),
        "original_exporter_code_sha256": digest_bytes(Path(__file__).with_name("role_boosting_export.py").read_bytes()),
        "reader_code_sha256": digest_bytes(Path(__file__).with_name("website_cdf_export.py").read_bytes()),
        "output_sha256": {"aggregate-report.json": digest_bytes(body.encode()), "aggregate-report.md": digest_bytes(markdown.encode())},
        "read_bytes": budget["bytes"], "wall_seconds": time.monotonic() - budget["started"],
        "original_fit_attempts_consumed": 136, "cumulative_report_attempts": 2,
        "row_data_reads": 0, "model_data_reads": 0, "new_fits": 0, "new_forecasts": 0,
        "new_scores": 0, "resampling_passes": 0, "technical_replay_performed": False}
    (output / "hash-manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    reader.check_time()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_run_directory")
    parser.add_argument("repair_run_directory")
    parser.add_argument("output_directory")
    parser.add_argument("--completion-sha256", required=True)
    parser.add_argument("--report-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(export_aggregates(args.source_run_directory, args.repair_run_directory,
        args.output_directory, args.completion_sha256, args.report_sha256), allow_nan=False))


if __name__ == "__main__":
    main()
