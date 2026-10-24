"""Sealed finite role/count ablation with create-only attempts and one score pass.

This opt-in research runner has no ledger, network, scheduler, publication or
promotion entrypoint. Every original offer and all 96 package statuses remain.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

from .cdf_campaign import digest, directory_bytes, event, proc_usage, terminate_group, write_json
from .median_boosting_campaign import (load_prediction_inputs, point_pairs as inherited_point_pairs, point_summary,
                                     interval, saved_control)
from .role_boosting import DESIGN, VERSION, VARIANTS, package_kind
from .website_cdf import TARGETS, environment_receipt

PERIODS = ("2022", "2023", "2024", "website_week6")
LIMITS = dict(maximum_candidate_fit_attempts=136, maximum_threads=2,
    campaign_wall_seconds=1800, campaign_cpu_seconds=2400, per_trial_wall_seconds=90,
    per_trial_cpu_seconds=120, memory_bytes=1536 * 1024 ** 2,
    private_output_bytes=800 * 1024 ** 2, reporting_wall_reserve_seconds=300,
    bootstrap_replicates=500, score_passes=1)
COMPARISONS = {
    "historical_primary": "pooled2022-2024 exact paired rows in unchanged primary_roles; numeric point MAE or binary Brier vs old_hgb base",
    "historical_secondary": "mandatory all-offered, annual and role/team/opponent/fallback slices; old CDF, pooled/recent, B-minus-A; nominal unadjusted 500-draw week/game intervals",
    "website_primary": "all original Week6 offers; exact pairs vs literal website; descriptive only",
    "website_secondary": "canonical primary_roles, old HGB/CDF/raw/simple, B-minus-A, common-all-controls cohort; no Week6 intervals",
    "numeric_secondary": "MSE, RMSE, prediction-minus-actual bias and absolute error tails",
    "binary_secondary": "unclipped natural log loss, Brier and fixed reliability deciles",
    "coherence": "completion<=attempt points and direct combined-minus-rush-minus-receiving points on common available identities; no summed candidate or borrowed gain",
    "selection": "all periods exposed; no selection, independent confirmation, blend, promotion or activation",
}


def check_seal(path):
    registry = json.loads(Path(path).read_text())
    seal = registry.get("seal", {})
    if registry.get("state") != "SEALED_ROOT_AND_REVIEWER" or seal.get("integrator") != "/root":
        raise ValueError("root and separate reviewer seal required")
    if not str(seal.get("reviewer", "")).startswith("/root/") or seal.get("decision") != "PASS_BOUNDED_EXPOSED_RESEARCH_ONLY":
        raise ValueError("distinct reviewer technical preclear required")
    plan = Path(seal["reviewed_plan_path"])
    if digest(plan) != seal["reviewed_plan_sha256"]:
        raise ValueError("reviewed plan bytes changed")
    if {k: v for k, v in registry.items() if k not in {"state", "seal"}} != {k: v for k, v in json.loads(plan.read_text()).items() if k != "state"}:
        raise ValueError("sealed payload differs from reviewed plan")
    if registry.get("registration_id") != VERSION or set(registry["categories"]) != set(TARGETS):
        raise ValueError("wrong version or categories")
    if registry.get("model_design") != DESIGN or registry.get("comparisons") != COMPARISONS or registry.get("budgets") != LIMITS:
        raise ValueError("fixed design, comparisons and resource limits required")
    if registry.get("variants") != list(VARIANTS) or registry.get("periods") != list(PERIODS):
        raise ValueError("fixed variants and periods required")
    if not Path(registry["output_directory"]).is_absolute():
        raise ValueError("absolute create-only output directory required")
    if set(registry["inputs"]) != {"training_features", "query_features", "opportunities", "outcomes"}:
        raise ValueError("separate exact inputs required")
    bindings = [registry[k] for k in ["prior_registry", "website_registry", "parent_boosting_registry", "source_contract"]]
    bindings += list(registry["inputs"].values()) + registry["code_bindings"] + registry["prerequisite_bindings"]
    ready = [t for t in TARGETS if registry["categories"][t]["state"] == "READY"]
    if len(ready) != 11 or "fantasy_ppr" in ready:
        raise ValueError("eleven ready targets and blocked PPR required")
    if set(registry["old_base_forecasts"]) != set(ready):
        raise ValueError("all eleven old base forecast target bindings required")
    for target in ready:
        if set(registry["old_base_forecasts"][target]) != set(PERIODS):
            raise ValueError("all four old forecast periods required")
        for period in PERIODS:
            bindings.append(registry["old_base_forecasts"][target][period])
            controls = registry["saved_controls"][target]["base"][period]
            expected = {"old_cdf"} if period == "website_week6" else {"old_cdf", "pooled", "recent"}
            if set(controls) != expected:
                raise ValueError("fixed secondary controls required")
            bindings.extend(controls.values())
    for binding in bindings:
        if digest(binding["path"]) != binding["sha256"]:
            raise ValueError("sealed bytes changed: " + binding["path"])
    parent = json.loads(Path(registry["parent_boosting_registry"]["path"]).read_text())
    prior = json.loads(Path(registry["prior_registry"]["path"]).read_text())
    website = json.loads(Path(registry["website_registry"]["path"]).read_text())
    if any(registry["categories"] != x["categories"] for x in [parent, prior, website]):
        raise ValueError("inherited category, feature or role contracts changed")
    if registry["inputs"] != parent["inputs"]:
        raise ValueError("ablation source packet differs from old HGB")
    contract = json.loads(Path(registry["source_contract"]["path"]).read_text())
    if contract.get("state") != "APPROVED_FREE_TRAINING_AND_INFERENCE" or contract.get("inputs") != registry["inputs"]:
        raise ValueError("approved exact source packet required")
    if registry.get("source_packet_mode") != parent["source_packet_mode"]:
        raise ValueError("inherited comparator source attribution changed")
    if registry.get("study_source_relation") != "same_exact_parent_hgb_input_packet":
        raise ValueError("explicit same-source learner attribution required")
    if registry.get("ensemble_design", {}).get("enabled") is not False or registry["ensemble_design"].get("additional_fits") != 0:
        raise ValueError("blends must be disabled")
    required = {str(Path(__file__).with_name(n).resolve()) for n in [
        "role_boosting.py", "role_boosting_campaign.py", "median_boosting.py", "median_boosting_campaign.py",
        "median_boosting_evaluation.py", "cdf_engine.py", "cdf_campaign.py", "cdf_evaluation.py",
        "website_cdf.py", "website_cdf_evaluation.py"]}
    if not required <= {str(Path(x["path"]).resolve()) for x in registry["code_bindings"]}:
        raise ValueError("all imported implementation code must be bound")
    expected_engine = next(x["sha256"] for x in prior["code_bindings"] if Path(x["path"]).name == "cdf_engine.py")
    if digest(Path(__file__).with_name("cdf_engine.py")) != expected_engine:
        raise ValueError("inherited CDF engine changed")
    parent_freeze = Path(parent["output_directory"]) / "forecast-freeze.json"
    freeze_binding = next((b for b in registry["prerequisite_bindings"] if Path(b["path"]).resolve() == parent_freeze.resolve()), None)
    if freeze_binding is None:
        raise ValueError("parent global forecast freeze must be bound")
    frozen = json.loads(parent_freeze.read_text())["bindings"]
    for target in ready:
        for period in PERIODS:
            binding = registry["old_base_forecasts"][target][period]
            relative = f"trials/{target}/base/{period}/candidate-frozen.parquet"
            if Path(binding["path"]).resolve() != (Path(parent["output_directory"]) / relative).resolve() or frozen.get(relative) != binding["sha256"]:
                raise ValueError("old base binding not authenticated by parent freeze")
    return registry


def verify_frozen(frame, query, category):
    import numpy as np
    import pandas as pd
    from .cdf_engine import KEYS, numeric
    if not frame[KEYS].reset_index(drop=True).equals(query[KEYS].reset_index(drop=True)):
        raise ValueError("frozen identity/order differs")
    for name in ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]:
        left, right = frame[name].reset_index(drop=True), query[name].reset_index(drop=True)
        if name.endswith("_utc"):
            left, right = pd.to_datetime(left, utc=True), pd.to_datetime(right, utc=True)
        if not left.equals(right):
            raise ValueError("frozen context differs: " + name)
    if not frame.target.eq(category["target"]).all() or not frame.participation_state.eq("unread").all() or not frame.outcome_state.eq("unread").all() or np.isfinite(numeric(frame, "actual")).any():
        raise ValueError("forecast must retain unread evaluation outcomes")
    if not frame.primary_role.eq(query.position.isin(category["primary_roles"])).all():
        raise ValueError("primary-role routing changed")
    if category["support"] == "count" and (numeric(frame, "point") < 0).any():
        raise ValueError("negative frozen count")
    return frame


def byte_copy(binding, destination):
    destination = Path(destination)
    if destination.exists() or digest(binding["path"]) != binding["sha256"]:
        raise ValueError("copy source changed or destination exists")
    with Path(binding["path"]).open("rb") as source, destination.open("xb") as target:
        shutil.copyfileobj(source, target)
    if digest(destination) != binding["sha256"]:
        raise ValueError("byte alias changed")


def prediction_trial(registry_path, directory, target, variant, period):
    import pandas as pd
    from .role_boosting import RoleCountBoostingModel, prediction_rows
    registry, directory = check_seal(registry_path), Path(directory).resolve()
    expected = Path(registry["output_directory"]).resolve() / "trials" / target / variant / period
    if directory != expected or not (directory / "package-consumed.json").is_file():
        raise ValueError("sealed consumed package required")
    log = directory / "events.jsonl"
    if log.exists():
        raise FileExistsError("no trial retries")
    event(log, "PREDICTION_PACKAGE_STARTED", target=target, variant=variant, period=period)
    category = registry["categories"][target]
    kind = package_kind(category, variant)
    train, query, offers, audit = load_prediction_inputs(registry, target, period)
    query.to_parquet(directory / "query.parquet", index=False)
    if offers is not None:
        offers.to_parquet(directory / "literal-offers.parquet", index=False)
    write_json(directory / "training-gate.json", audit)
    old_binding = registry["old_base_forecasts"][target][period]
    byte_copy(old_binding, directory / "old-hgb-frozen.parquet")
    verify_frozen(pd.read_parquet(directory / "old-hgb-frozen.parquet"), query, category)
    fits = []
    if kind == "model":
        def consume(receipt):
            count = len(fits) + 1
            ceiling = 1 if variant == "A" else len(category["modeled_roles"])
            if count > ceiling:
                raise ValueError("package estimator budget exceeded")
            write_json(directory / f"estimator-attempt-{count:02d}.json", dict(receipt,
                target=target, variant=variant, period=period, attempt=count))
            fits.append(receipt)
            event(log, "ESTIMATOR_ATTEMPT_CONSUMED", **receipt)
        model = RoleCountBoostingModel.fit(train, category, variant, before_fit=consume)
        manifest = model.save(directory / "model")
        frozen = prediction_rows(model, query)
        verify_frozen(frozen, query, category).to_parquet(directory / "candidate-frozen.parquet", index=False)
        prediction_rows(model, query, prior_only=True).to_parquet(directory / "role-prior-frozen.parquet", index=False)
        write_json(directory / "fit-slots.json", model.audit["subfits"])
        event(log, "MODEL_FROZEN", sha256=manifest["sha256"], fit_attempts=len(fits))
    else:
        source = old_binding if kind == "old_base_alias" else {
            "path": str(directory.parent.parent / "A" / period / "candidate-frozen.parquet"),
            "sha256": digest(directory.parent.parent / "A" / period / "candidate-frozen.parquet")}
        byte_copy(source, directory / "candidate-frozen.parquet")
        verify_frozen(pd.read_parquet(directory / "candidate-frozen.parquet"), query, category)
        write_json(directory / "alias.json", {"kind": kind, "binding": source,
            "copied_sha256": digest(directory / "candidate-frozen.parquet"), "fit_attempts": 0,
            "prediction_calls": 0, "method_field": "literal original retained; package variant identified by manifest"})
        event(log, "BYTE_ALIAS_FROZEN", kind=kind, sha256=source["sha256"])
    bindings = {str(p.relative_to(directory)): digest(p) for p in directory.rglob("*")
        if p.is_file() and p.name not in {"events.jsonl", "stdout.log", "stderr.log"}}
    write_json(directory / "prediction-manifest.json", {"target": target, "variant": variant,
        "period": period, "kind": kind, "bindings": bindings, "fit_attempts": len(fits), "score_passes": 0})
    event(log, "PREDICTION_PACKAGE_COMPLETED", sha256=digest(directory / "prediction-manifest.json"))


def summary(rows, category):
    result = point_summary(rows, category)
    rmse = result["point_metrics"]["rmse"]
    result["point_metrics"]["mse"] = rmse ** 2 if rmse is not None else None
    return result


def point_pairs(candidate, control, category, *, role_subset=False):
    report, rows = inherited_point_pairs(candidate, control, category, role_subset=role_subset)
    for field in ["candidate_point_metrics", "control_literal_point_metrics"]:
        rmse = report[field]["rmse"]
        report[field]["mse"] = rmse ** 2 if rmse is not None else None
    if category["support"] == "bernoulli":
        from .median_boosting_evaluation import log_loss_summary, reliability
        eligible = rows.loc[rows.paired_eligible]
        report["paired_binary"] = {"candidate": log_loss_summary(eligible.candidate_point, eligible.actual),
            "control": log_loss_summary(eligible.literal_control_point, eligible.actual),
            "candidate_reliability_deciles": reliability(eligible.candidate_point, eligible.actual),
            "control_reliability_deciles": reliability(eligible.literal_control_point, eligible.actual)}
    return report, rows


def validate_statuses(statuses, freeze):
    expected = {(t, v, p) for t in TARGETS for v in VARIANTS for p in PERIODS}
    actual = {(s["target"], s["variant"], s["period"]) for s in statuses}
    if actual != expected or len(statuses) != len(expected):
        raise ValueError("all 96 unique package statuses required")
    attempts = sum(s.get("fit_attempts", 0) for s in statuses)
    if attempts != freeze["fit_attempts"] or not 0 <= attempts <= LIMITS["maximum_candidate_fit_attempts"]:
        raise ValueError("frozen estimator consumption differs")
    ppr = [s for s in statuses if s["target"] == "fantasy_ppr"]
    if any(s["state"] != "BLOCKED_CATEGORY_CONTRACT" for s in ppr) or sum(s.get("blocked_subfit_slots", 0) for s in ppr) != 24:
        raise ValueError("all exact PPR package and subfit slots must stay blocked")


def common_cohort_reports(a, b, controls, category):
    """A/B and every control share one observed finite cohort, with no refit."""
    import numpy as np
    from .cdf_engine import KEYS, numeric
    mask = np.isfinite(numeric(a, "point")) & np.isfinite(numeric(b, "point"))
    if not a[KEYS].reset_index(drop=True).equals(b[KEYS].reset_index(drop=True)):
        raise ValueError("A/B common cohort identity differs")
    groups = list(controls.groupby("method", sort=True))
    for _, control in groups:
        if not a[KEYS].reset_index(drop=True).equals(control[KEYS].reset_index(drop=True)):
            raise ValueError("common control identity differs")
        mask &= np.isfinite(numeric(control, "point"))
    reports = []
    for variant, candidate in [("A", a), ("B", b)]:
        candidate = candidate.copy()
        candidate.loc[~mask, "point"] = np.nan
        for method, control in groups:
            for subset in [False, True]:
                value, _ = point_pairs(candidate, control, category, role_subset=subset)
                reports.append(dict(value, variant=variant, comparator=method,
                    finite_common_rows=int(mask.sum()), status="secondary_A_B_all_controls_common_cohort"))
    return reports


def report_cell(candidate, controls, category, *, historical, pooled=False):
    import numpy as np
    import pandas as pd
    from .cdf_engine import numeric
    report = {"target": category["target"], "summary": summary(candidate, category),
        "paired": [], "subgroups": [], "semantics": DESIGN["numeric_semantics"]
        if category["support"] != "bernoulli" else "genuine Bernoulli probability"}
    report["comparator_availability"] = ({"website": "N/A_not_recorded_for_exact_panel",
        "raw": "N/A_not_recorded_for_exact_panel", "simple": "N/A_not_recorded_for_exact_panel"}
        if historical else {"website": "literal_original_offer_values; per-comparator paired/missing counts below",
            "raw": "literal_original_offer_values; per-comparator paired/missing counts below",
            "simple": "literal_original_offer_values; per-comparator paired/missing counts below"})
    deltas = []
    for method, control in controls.groupby("method", sort=True):
        for role_subset in [False, True]:
            value, rows = point_pairs(candidate, control, category, role_subset=role_subset)
            primary = (historical and pooled and method == "old_hgb" and role_subset) or (
                not historical and method == "website" and not role_subset)
            value.update(comparator=method, status="primary" if primary else "secondary")
            eligible = rows.loc[rows.paired_eligible]
            value["players"] = int(eligible.player_id.nunique())
            if historical:
                value["intervals"] = [interval(candidate, control, category, role_subset, c) for c in ["week", "game"]]
                value["uncertainty"] = "exposed current-vintage reconstruction; nominal unadjusted descriptive intervals"
            else:
                value["interval"] = None
                value["uncertainty"] = "exposed Week6; CI not applicable; descriptive only"
            rows["comparator"], rows["population"] = method, value["population"]
            report["paired"].append(value)
            deltas.append(rows)
    # These diagnostics use the exact same finite cohort for every comparator.
    common = np.isfinite(numeric(candidate, "point"))
    control_groups = list(controls.groupby("method", sort=True))
    for _, control in control_groups:
        if not candidate[["season", "week", "game_id", "player_id"]].reset_index(drop=True).equals(
                control[["season", "week", "game_id", "player_id"]].reset_index(drop=True)):
            raise ValueError("common-cohort control order differs")
        common &= np.isfinite(numeric(control, "point"))
    report["common_all_controls"] = []
    for method, control in control_groups:
        a, b = candidate.copy(), control.copy()
        a.loc[~common, "point"], b.loc[~common, "point"] = np.nan, np.nan
        for subset in [False, True]:
            value, _ = point_pairs(a, b, category, role_subset=subset)
            report["common_all_controls"].append(dict(value, comparator=method, finite_common_rows=int(common.sum()), status="secondary_common_all_controls"))
    for dimension in ["position", "season", "team", "opponent", "fallback", "history_state", "outcome_state"]:
        if dimension in candidate:
            for value, part in candidate.groupby(dimension, dropna=False):
                report["subgroups"].append({"dimension": dimension, "value": str(value), **summary(part, category)})
    return report, pd.concat(deltas, ignore_index=True) if deltas else pd.DataFrame()


def coherence_audits(frames, output):
    import numpy as np
    import pandas as pd
    from .cdf_engine import KEYS, numeric
    output = Path(output)
    output.mkdir(exist_ok=False)
    reports = []
    for variant in VARIANTS:
        for period in PERIODS:
            for name, targets in [("completion_minus_attempt", ("pass_cmp", "pass_att")),
                                  ("direct_combined_minus_components", ("rush_rec_yd", "rush_yd", "rec_yd"))]:
                joined = None
                for target in targets:
                    frame = frames.get((target, variant, period))
                    if frame is None:
                        continue
                    part = frame[KEYS + ["point"]].rename(columns={"point": target + "_point"})
                    joined = part if joined is None else joined.merge(part, on=KEYS, how="outer", validate="one_to_one")
                if joined is None:
                    reports.append(dict(variant=variant, period=period, audit=name, state="NO_PACKAGES"))
                    continue
                values = [numeric(joined, t + "_point") for t in targets]
                available = np.logical_and.reduce([np.isfinite(v) for v in values])
                gap = values[0] - values[1] if len(values) == 2 else values[0] - values[1] - values[2]
                joined["all_components_available"], joined["point_gap"] = available, np.where(available, gap, np.nan)
                joined.to_parquet(output / f"{variant}-{period}-{name}.parquet", index=False)
                reports.append({"variant": variant, "period": period, "audit": name,
                    "offered_union_rows": len(joined), "common_available_rows": int(available.sum()),
                    "missing_component_rows": int((~available).sum()),
                    "absent_or_missing_by_target": {t: int((~np.isfinite(v)).sum()) for t, v in zip(targets, values)},
                    "mean_point_gap": float(gap[available].mean()) if available.any() else None,
                    "max_absolute_gap": float(np.abs(gap[available]).max()) if available.any() else None,
                    "positive_gap_rows": int((gap[available] > 0).sum()),
                    "semantics": "point coherence only; no invented components, sum forecast, outcome score or borrowed performance gain"})
    write_json(output / "coverage-and-gaps.json", reports)
    return reports


def score_report(registry_path, output):
    import pandas as pd
    from .cdf_engine import KEYS, assert_composite_contract
    from .median_boosting import score_frozen_rows
    from .website_cdf_evaluation import bind_outcomes, literal_controls, normalize_keys
    registry, output = check_seal(registry_path), Path(output).resolve()
    if output != Path(registry["output_directory"]).resolve() or not (output / "forecast-freeze.json").is_file():
        raise ValueError("sealed global freeze required")
    freeze = json.loads((output / "forecast-freeze.json").read_text())
    if digest(output / "attempts.json") != freeze["attempts_sha256"]:
        raise ValueError("package statuses changed after freeze")
    for relative, sha in freeze["bindings"].items():
        if digest(output / relative) != sha:
            raise ValueError("frozen bytes changed: " + relative)
    statuses = json.loads((output / "attempts.json").read_text())
    validate_statuses(statuses, freeze)
    with (output / "score-consumed.json").open("x") as handle:
        json.dump({"at": datetime.now(timezone.utc).isoformat(), "score_passes": 1,
            "forecast_freeze_sha256": digest(output / "forecast-freeze.json")}, handle)
        handle.flush()
        os.fsync(handle.fileno())
    event(output / "events.jsonl", "SCORE_PASS_CONSUMED")
    # First evaluation outcome reads in the complete campaign occur here.
    history = pd.read_parquet(registry["inputs"]["training_features"]["path"], filters=[("season", ">=", 2022), ("season", "<=", 2024)])
    outcomes = normalize_keys(pd.read_parquet(registry["inputs"]["outcomes"]["path"]))
    opportunities = normalize_keys(pd.read_parquet(registry["inputs"]["opportunities"]["path"]))
    identity = KEYS + ["target"]
    coverage = opportunities[identity].merge(outcomes[identity], on=identity, how="outer", indicator=True, validate="one_to_one")
    if not coverage._merge.eq("both").all():
        raise ValueError("all original offers including blocked PPR must remain")
    frames, controls_by_cell, slots = {}, {}, []
    compact = KEYS + ["point", "actual", "participation_state", "outcome_state", "primary_role", "fallback",
        "position", "season", "team", "opponent", "history_state", "probability", "target"]
    compact = list(dict.fromkeys(compact))
    for status in statuses:
        if status["state"] != "PREDICTION_FROZEN":
            slots.append(dict(status))
            continue
        target, variant, period = status["target"], status["variant"], status["period"]
        category, directory = registry["categories"][target], output / status["trial"]
        query = pd.read_parquet(directory / "query.parquet")
        historical = period != "website_week6"
        if historical:
            offered = query[KEYS].merge(history.loc[history.season.eq(int(period))], on=KEYS, how="left", sort=False, validate="one_to_one")
            assert_composite_contract(offered, category)
        else:
            offered = bind_outcomes(query, outcomes, category)
        scored = score_frozen_rows(offered, pd.read_parquet(directory / "candidate-frozen.parquet"), category)
        scored.to_parquet(directory / "candidate-scored.parquet", index=False)
        old = score_frozen_rows(offered, pd.read_parquet(directory / "old-hgb-frozen.parquet"), category)
        old["method"] = "old_hgb"
        controls = [old]
        controls.extend(saved_control(binding, offered, category, method, mode=registry["source_packet_mode"],
            audit_directory=directory, panel="base") for method, binding in registry["saved_controls"][target]["base"][period].items())
        source_receipts = [c.attrs["source_comparison"] for c in controls if "source_comparison" in c.attrs]
        if not historical:
            controls.append(literal_controls(pd.read_parquet(directory / "literal-offers.parquet"), scored, category))
        controls = pd.concat(controls, ignore_index=True)
        controls.to_parquet(directory / "controls-scored.parquet", index=False)
        frames[target, variant, period] = scored[[c for c in compact if c in scored]].copy()
        control_fields = KEYS + ["actual", "participation_state", "point", "primary_role", "method"]
        controls_by_cell[target, variant, period] = controls[control_fields].copy()
        report, deltas = report_cell(scored, controls, category, historical=historical)
        report.update(variant=variant, period=period, source_comparisons=source_receipts)
        if (directory / "role-prior-frozen.parquet").is_file():
            report["role_prior"] = summary(score_frozen_rows(offered, pd.read_parquet(directory / "role-prior-frozen.parquet"), category), category)
        write_json(directory / "report.json", report)
        deltas.to_parquet(directory / "paired-row-deltas.parquet", index=False)
        slots.append(dict(status, state="SCORED_DESCRIPTIVE", report_sha256=digest(directory / "report.json"),
            primary_comparisons=[v for v in report["paired"] if v["status"] == "primary"]))
    aggregate, primary_slots, ablations, common_diagnostics = [], [], [], []
    for target in TARGETS:
        category = registry["categories"][target]
        for variant in VARIANTS:
            years = [p for p in PERIODS[:-1] if (target, variant, p) in frames]
            primary = None
            if years:
                candidate = pd.concat([frames[target, variant, p] for p in years], ignore_index=True)
                controls = pd.concat([controls_by_cell[target, variant, p] for p in years], ignore_index=True)
                report, _ = report_cell(candidate, controls, category, historical=True, pooled=True)
                report.update(variant=variant, compared_complete_years=[int(p) for p in years],
                    excluded_years=[int(p) for p in PERIODS[:-1] if p not in years],
                    partial_failure_policy="only complete same annual cells paired; all failures retained")
                aggregate.append(report)
                primary = next(v for v in report["paired"] if v["status"] == "primary")
            blocked = category["state"] != "READY"
            primary_slots.append({"target": target, "variant": variant, "period": "pooled2022-2024",
                "state": "BLOCKED_CATEGORY_CONTRACT" if blocked else "SCORED_DESCRIPTIVE" if len(years) == 3 else "PARTIAL_OR_FAILED_RETAINED",
                "primary": primary, "compared_complete_years": [int(p) for p in years]})
            website = next((s for s in slots if s["target"] == target and s["variant"] == variant and s["period"] == "website_week6"), None)
            primary_slots.append({"target": target, "variant": variant, "period": "website_week6",
                "state": website["state"] if website else "FAILED_RETAINED", "primary": next(iter(website.get("primary_comparisons", [])), None) if website else None})
        if category["state"] != "READY":
            continue
        for period in PERIODS:
            if any((target, v, period) not in frames for v in VARIANTS):
                continue
            common_diagnostics.extend(dict(value, target=target, period=period) for value in common_cohort_reports(
                frames[target, "A", period], frames[target, "B", period], controls_by_cell[target, "A", period], category))
            for subset in [False, True]:
                b, a = frames[target, "B", period], frames[target, "A", period]
                value, _ = point_pairs(b, a, category, role_subset=subset)
                value.update(target=target, period=period, comparison="B_minus_A", status="secondary")
                if period != "website_week6":
                    value["intervals"] = [interval(b, a, category, subset, c) for c in ["week", "game"]]
                ablations.append(value)
    coherence = coherence_audits(frames, output / "coherence")
    write_json(output / "role-boosting-report.json", {"registration_id": VERSION, "slots": slots,
        "primary_slots": primary_slots, "historical_pooled": aggregate, "role_loss_ablations": ablations,
        "common_cohort_diagnostics": common_diagnostics,
        "comparator_availability": {p: {m: "N/A_not_recorded_for_exact_panel" for m in ["website", "raw", "simple"]}
            if p != "website_week6" else {m: "literal_original_offers; exact paired/missing counts in each cell" for m in ["website", "raw", "simple"]} for p in PERIODS},
        "coherence": coherence, "planned_packages": 96, "planned_new_model_packages": 48,
        "planned_alias_packages": 40, "blocked_ppr_packages": 8, "blocked_ppr_subfit_slots": 24,
        "primary_contrast_slots": 48, "blocked_ppr_primary_contrasts": 4,
        "maximum_estimator_attempts": 136, "model_design": DESIGN, "comparisons": COMPARISONS,
        "budgets": LIMITS, "original_opportunity_rows": len(opportunities), "score_passes": 1,
        "source_qualification": registry["source_qualification"], "source_packet_mode": registry["source_packet_mode"],
        "study_source_relation": registry["study_source_relation"],
        "prior_search_and_exposure": registry["prior_search_and_exposure"], "new_qualified_replacements": [],
        "confirmation": "none; all periods exposed; no independent confirmation, prospective or promotion claim"})
    event(output / "events.jsonl", "SCORE_REPORT_COMPLETED", sha256=digest(output / "role-boosting-report.json"))


def monitored_process(arguments, output, directory, *, remaining_wall, remaining_cpu, per_trial=True):
    begin, before, reason, peak = time.monotonic(), resource.getrusage(resource.RUSAGE_CHILDREN), None, 0
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2", PYTHONPATH=str(root))
    with (directory / "stdout.log").open("x") as stdout, (directory / "stderr.log").open("x") as stderr:
        process = subprocess.Popen([sys.executable, "-m", "nfl_lab.role_boosting_campaign", *arguments],
            cwd=root, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        while process.poll() is None:
            rss, cpu = proc_usage(process.pid)
            peak = max(peak, rss)
            elapsed = time.monotonic() - begin
            if rss > LIMITS["memory_bytes"]:
                reason = "RSS_LIMIT"
            elif elapsed >= remaining_wall:
                reason = "CAMPAIGN_WALL_LIMIT"
            elif cpu >= remaining_cpu:
                reason = "CAMPAIGN_CPU_LIMIT"
            elif per_trial and elapsed > LIMITS["per_trial_wall_seconds"]:
                reason = "TRIAL_WALL_LIMIT"
            elif per_trial and cpu > LIMITS["per_trial_cpu_seconds"]:
                reason = "TRIAL_CPU_LIMIT"
            elif directory_bytes(output) >= LIMITS["private_output_bytes"]:
                reason = "OUTPUT_LIMIT"
            if reason:
                terminate_group(process)
                break
            time.sleep(.1)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"returncode": process.returncode, "reason": reason, "wall_seconds": time.monotonic() - begin,
        "cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
        "sampled_peak_process_group_rss_bytes": peak}


def run(registry_path, output):
    registry_path, output = Path(registry_path).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError("output exists; campaign restart prohibited")
    registry = check_seal(registry_path)
    if output != Path(registry["output_directory"]).resolve():
        raise ValueError("sealed output differs")
    output.mkdir(parents=True, exist_ok=False)
    began, parent_cpu, cpu_used, consumed, statuses = time.monotonic(), time.process_time(), 0., 0, []
    log = output / "events.jsonl"
    write_json(output / "registry.json", registry)
    write_json(output / "environment.json", environment_receipt())
    event(log, "CAMPAIGN_STARTED", registry_sha256=digest(registry_path), budgets=LIMITS)
    for period in PERIODS:
        for target in TARGETS:
            for variant in VARIANTS:
                category = registry["categories"][target]
                kind = package_kind(category, variant)
                relative = f"trials/{target}/{variant}/{period}"
                status = dict(target=target, variant=variant, period=period, kind=kind, trial=relative)
                remaining_wall = LIMITS["campaign_wall_seconds"] - (time.monotonic() - began)
                remaining_cpu = LIMITS["campaign_cpu_seconds"] - cpu_used - (time.process_time() - parent_cpu)
                reserve = (1 if variant == "A" else len(category["modeled_roles"])) if kind == "model" else 0
                if kind == "blocked":
                    status.update(state="BLOCKED_CATEGORY_CONTRACT", blocked_subfit_slots=1 if variant == "A" else 5)
                elif kind == "A_alias" and not any(s["target"] == target and s["variant"] == "A" and s["period"] == period and s["state"] == "PREDICTION_FROZEN" for s in statuses):
                    status["state"] = "SKIPPED_FAILED_ALIAS_SOURCE"
                elif remaining_wall <= LIMITS["reporting_wall_reserve_seconds"] or remaining_cpu <= 0:
                    status["state"] = "SKIPPED_CAMPAIGN_BUDGET"
                elif consumed + reserve > LIMITS["maximum_candidate_fit_attempts"]:
                    status["state"] = "SKIPPED_FIT_BUDGET"
                elif directory_bytes(output) >= LIMITS["private_output_bytes"]:
                    status["state"] = "SKIPPED_OUTPUT_BUDGET"
                if "state" not in status:
                    directory = output / relative
                    directory.mkdir(parents=True, exist_ok=False)
                    write_json(directory / "package-consumed.json", dict(status, maximum_estimator_attempts=reserve))
                    usage = monitored_process(["predict-trial", str(registry_path), str(directory), target, variant, period], output, directory,
                        remaining_wall=remaining_wall - LIMITS["reporting_wall_reserve_seconds"], remaining_cpu=remaining_cpu)
                    cpu_used += usage["cpu_seconds"]
                    actual = len(list(directory.glob("estimator-attempt-*.json")))
                    consumed += actual
                    if actual > reserve or consumed > LIMITS["maximum_candidate_fit_attempts"]:
                        raise ValueError("estimator consumption exceeds fixed budget")
                    frozen = usage["returncode"] == 0 and (directory / "prediction-manifest.json").is_file()
                    status.update(usage, fit_attempts=actual, state="PREDICTION_FROZEN" if frozen else "FAILED_CONSUMED")
                statuses.append(status)
                event(log, status["state"], **{k: v for k, v in status.items() if k != "state"})
                write_json(output / "attempts.json", statuses)
    bindings = {}
    for status in statuses:
        if status["state"] != "PREDICTION_FROZEN":
            continue
        directory = output / status["trial"]
        manifest = json.loads((directory / "prediction-manifest.json").read_text())
        bindings.update({str((directory / p).relative_to(output)): sha for p, sha in manifest["bindings"].items()})
        bindings[str((directory / "prediction-manifest.json").relative_to(output))] = digest(directory / "prediction-manifest.json")
    # Failed consumed attempts also remain authenticated after global freeze.
    for receipt in output.glob("trials/*/*/*/estimator-attempt-*.json"):
        bindings[str(receipt.relative_to(output))] = digest(receipt)
    write_json(output / "forecast-freeze.json", {"bindings": bindings, "attempts_sha256": digest(output / "attempts.json"),
        "fit_attempts": consumed, "score_passes": 0, "packages": len(statuses), "evidence": "postgame calculation order only; no prospective issuance"})
    event(log, "ALL_FORECASTS_FROZEN", sha256=digest(output / "forecast-freeze.json"), fit_attempts=consumed)
    reporting = output / "reporting"
    reporting.mkdir(exist_ok=False)
    remaining_wall = LIMITS["campaign_wall_seconds"] - (time.monotonic() - began)
    remaining_cpu = LIMITS["campaign_cpu_seconds"] - cpu_used - (time.process_time() - parent_cpu)
    if remaining_wall > 0 and remaining_cpu > 0 and directory_bytes(output) < LIMITS["private_output_bytes"]:
        usage = monitored_process(["score-report", str(registry_path), str(output)], output, reporting,
            remaining_wall=remaining_wall, remaining_cpu=remaining_cpu, per_trial=False)
        cpu_used += usage["cpu_seconds"]
    else:
        usage = {"reason": "CAMPAIGN_BUDGET_BEFORE_SCORE", "returncode": None}
    completed = usage["returncode"] == 0 and (output / "role-boosting-report.json").is_file()
    write_json(output / "completion.json", {"state": "COMPLETED_DESCRIPTIVE" if completed else "INCOMPLETE_RETAINED_NO_RESTART",
        "fit_attempts_consumed": consumed, "score_pass_consumed": (output / "score-consumed.json").exists(),
        "statuses": statuses, "reporting": usage, "wall_seconds": time.monotonic() - began,
        "cpu_seconds": cpu_used + time.process_time() - parent_cpu, "output_bytes_before_completion": directory_bytes(output)})
    event(log, "CAMPAIGN_FINISHED", completed=completed)
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["run", "score-report"]:
        p = sub.add_parser(command)
        p.add_argument("registry")
        p.add_argument("output")
    p = sub.add_parser("predict-trial")
    p.add_argument("registry")
    p.add_argument("output")
    p.add_argument("target", choices=TARGETS)
    p.add_argument("variant", choices=VARIANTS)
    p.add_argument("period", choices=PERIODS)
    args = parser.parse_args()
    if args.command == "run":
        if not run(args.registry, args.output):
            raise SystemExit(1)
    elif args.command == "predict-trial":
        prediction_trial(args.registry, args.output, args.target, args.variant, args.period)
    else:
        score_report(args.registry, args.output)


if __name__ == "__main__":
    main()
