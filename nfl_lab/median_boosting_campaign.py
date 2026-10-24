"""One finite, sealed point-model study with a single global outcome phase.

All historical and website predictions freeze before any evaluation labels or
saved scored controls are opened. Attempts and failures are create-only. This
runner has no scheduler, network, publication, ledger or promotion entrypoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from .cdf_campaign import digest, directory_bytes, event, proc_usage, terminate_group, write_json
from .median_boosting import DESIGN, VERSION
from .website_cdf import TARGETS, environment_receipt, training_split

PERIODS = ("2022", "2023", "2024", "website_week6")
LIMITS = dict(maximum_candidate_fit_attempts=88, maximum_threads=2,
              campaign_wall_seconds=1200, campaign_cpu_seconds=1800,
              per_trial_wall_seconds=60, per_trial_cpu_seconds=90,
              memory_bytes=2 * 1024 ** 3, private_output_bytes=512 * 1024 ** 2,
              reporting_wall_reserve_seconds=180, bootstrap_replicates=500, score_passes=1)
ENSEMBLE_DESIGN = {"weight_website": .5, "weight_candidate": .5,
    "scope": "website_week6_only_secondary", "missing_website": "abstain and retain offer",
    "numeric_semantics": "fixed point heuristic; no forecast mean, law median or distribution",
    "binary_semantics": "genuine Bernoulli probability", "weight_search": "none", "additional_fits": 0}
COMPARISONS = {"historical_primary": "pooled2022-2024 ROWS, all offered exact eligible pairs; point MAE or probability Brier vs exact saved same-panel CDF median/probability only;22supported+2PPRblocked slots",
    "historical_secondary": "annual cells; same-pair literal pooled/recent points; prior_primary_roles exact pairs; context minus base; week/game nominal95 unadjusted500draw intervals",
    "website_primary": "descriptive point MAE or probability Brier vs literal original website; all original offered roles",
    "website_secondary": "raw/simple/same-panel prior CDF; original primary roles; only fixed50/50website blend",
    "selection": "all panels/years/categories retained; no winner selection, independent confirmation or promotion"}


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
        raise ValueError("wrong study or target slots")
    if registry.get("model_design") != DESIGN or registry.get("ensemble_design") != ENSEMBLE_DESIGN or registry.get("comparisons") != COMPARISONS:
        raise ValueError("fixed topology/semantics/comparisons changed")
    budgets = registry["budgets"]
    if set(budgets) != set(LIMITS) or any(budgets[k] != v for k, v in LIMITS.items() if k != "maximum_candidate_fit_attempts"):
        raise ValueError("fixed resource budget changed")
    if not isinstance(budgets["maximum_candidate_fit_attempts"], int) or not 1 <= budgets["maximum_candidate_fit_attempts"] <= 88:
        raise ValueError("fit budget may only be reduced before launch")
    if registry.get("periods") != list(PERIODS) or not Path(registry["output_directory"]).is_absolute():
        raise ValueError("fixed periods and absolute output required")
    if set(registry["inputs"]) != {"training_features", "query_features", "opportunities", "outcomes"}:
        raise ValueError("exact separate inputs required")
    bindings = [registry["prior_registry"], registry["website_registry"], registry["source_contract"], *registry["inputs"].values(),
                *registry["code_bindings"], *registry["prerequisite_bindings"]]
    for target, panels in registry["saved_controls"].items():
        for panel, periods in panels.items():
            for period, controls in periods.items():
                bindings.extend(controls.values())
    for binding in bindings:
        if digest(binding["path"]) != binding["sha256"]:
            raise ValueError("sealed bytes changed: " + binding["path"])
    prior = json.loads(Path(registry["prior_registry"]["path"]).read_text())
    website = json.loads(Path(registry["website_registry"]["path"]).read_text())
    if registry["categories"] != prior["categories"] or registry["categories"] != website["categories"]:
        raise ValueError("prior feature panels/role contracts changed")
    mode = registry.get("source_packet_mode")
    if mode not in {"same_retained_packet", "joint_learner_source_reconstruction"}:
        raise ValueError("explicit learner/source attribution required")
    if mode == "same_retained_packet" and (registry["inputs"] != website["inputs"] or registry["inputs"]["training_features"]["sha256"] != prior["source"]["sha256"]):
        raise ValueError("claimed same-source packet differs")
    source_contract = json.loads(Path(registry["source_contract"]["path"]).read_text())
    if source_contract.get("state") != "APPROVED_FREE_TRAINING_AND_INFERENCE" or source_contract.get("inputs") != registry["inputs"]:
        raise ValueError("approved source receipt must bind the exact final input packet")
    if registry["categories"]["fantasy_ppr"]["state"] == "READY" or sum(c["state"] == "READY" for c in registry["categories"].values()) != 11:
        raise ValueError("eleven supported targets and blocked PPR required")
    expected_engine = next(x["sha256"] for x in prior["code_bindings"] if Path(x["path"]).name == "cdf_engine.py")
    if digest(Path(__file__).with_name("cdf_engine.py")) != expected_engine:
        raise ValueError("registered CDF engine changed")
    required = {str(Path(__file__).with_name(name).resolve()) for name in
        ["median_boosting.py", "median_boosting_campaign.py", "cdf_engine.py", "cdf_campaign.py",
         "cdf_evaluation.py", "website_cdf.py", "website_cdf_evaluation.py", "median_boosting_evaluation.py"]}
    if not required <= {str(Path(x["path"]).resolve()) for x in registry["code_bindings"]}:
        raise ValueError("runner and imported code must be bound")
    for target in TARGETS:
        if registry["categories"][target]["state"] != "READY":
            continue
        for panel in ["base", "context"]:
            for period in PERIODS:
                expected = {"old_cdf"} if period == "website_week6" else {"old_cdf", "pooled", "recent"}
                if set(registry["saved_controls"][target][panel][period]) != expected:
                    raise ValueError("all exact saved comparator row bindings required")
    return registry


def load_prediction_inputs(registry, target, period):
    """One loader; historical evaluation labels are excluded at Parquet read."""
    import pandas as pd
    import pyarrow.parquet as pq
    from .cdf_engine import KEYS, chronological_split
    from .website_cdf_evaluation import target_query
    paths = registry["inputs"]
    if period == "website_week6":
        features = pd.read_parquet(paths["training_features"]["path"], filters=[("season", ">=", 2019), ("season", "<=", 2025)])
        query_all = pd.read_parquet(paths["query_features"]["path"])
        query, offers = target_query(query_all, pd.read_parquet(paths["opportunities"]["path"]), target)
        train, audit = training_split(features, query_all)
        # No target outcome/statistic is necessary for prediction provenance.
        query = query.drop(columns=[c for c in TARGETS if c in query], errors="ignore")
        query["participation_state"] = "unknown"
        return train, query, offers, audit
    year = int(period)
    source = paths["training_features"]["path"]
    metadata = set(KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc", "season_type",
                          "outcome_available_utc", "feature_max_source_available_utc"])
    names = [c for c in pq.ParquetFile(source).schema_arrow.names if c in metadata or c.startswith("f_")]
    query = pd.read_parquet(source, filters=[("season", "==", year)], columns=names)
    query["participation_state"] = "unknown"
    old = pd.read_parquet(source, filters=[("season", "<", year)])
    train, _ = chronological_split(pd.concat([old, query], ignore_index=True), year)
    return train, query, None, {"eligible_training_rows": len(train), "query_rows": len(query),
        "training_seasons": sorted(int(y) for y in train.season.unique()),
        "availability_policy": "same current-vintage seven-day assumed lag; publication vintage unverified"}


def prediction_trial(registry_path, directory, target, panel, period):
    from .median_boosting import MedianBoostingModel, equalweight_rows, prediction_rows
    registry, directory = check_seal(registry_path), Path(directory).resolve()
    expected = Path(registry["output_directory"]).resolve() / "trials" / target / panel / period
    if directory != expected or not (directory / "attempt-consumed.json").is_file():
        raise ValueError("sealed trial and consumed attempt required")
    if (directory / "events.jsonl").exists():
        raise FileExistsError("prediction trial already started; no retry")
    log = directory / "events.jsonl"
    event(log, "PREDICTION_TRIAL_STARTED", target=target, panel=panel, period=period)
    train, query, offers, audit = load_prediction_inputs(registry, target, period)
    query.to_parquet(directory / "query.parquet", index=False)
    if offers is not None:
        offers.to_parquet(directory / "literal-offers.parquet", index=False)
    write_json(directory / "training-gate.json", audit)
    event(log, "FIT_CONSUMED", **audit)
    model = MedianBoostingModel.fit(train, registry["categories"][target], panel)
    manifest = model.save(directory / "model")
    event(log, "MODEL_FROZEN", sha256=manifest["sha256"], fit_state=model.audit["fit_state"])
    for prior_only, name in [(False, "candidate"), (True, "role-prior")]:
        frozen = prediction_rows(model, query, prior_only=prior_only)
        frozen.to_parquet(directory / (name + "-frozen.parquet"), index=False)
    if offers is not None:
        ensemble = equalweight_rows(prediction_rows(model, query), offers, registry["categories"][target])
        ensemble.to_parquet(directory / "ensemble-frozen.parquet", index=False)
    bindings = {str(p.relative_to(directory)): digest(p) for p in directory.rglob("*")
                if p.is_file() and p.name not in {"events.jsonl", "stdout.log", "stderr.log"}}
    write_json(directory / "prediction-manifest.json", {"target": target, "panel": panel, "period": period,
        "bindings": bindings, "fit_attempts": 1, "score_passes": 0, "fit_state": model.audit["fit_state"]})
    event(log, "PREDICTION_TRIAL_COMPLETED", manifest_sha256=digest(directory / "prediction-manifest.json"))


def saved_control(binding, offered, category, method, *, mode="same_retained_packet", audit_directory=None, panel=None):
    import pandas as pd
    from .cdf_evaluation import bind_saved_control
    from .cdf_engine import numeric
    saved = pd.read_parquet(binding["path"])
    if method == "old_cdf":
        expected = "leaf_cdf_" + panel if panel else "leaf_cdf_(base|context)"
        if not saved.method.str.fullmatch(expected).all():
            raise ValueError("saved CDF comparator method differs")
        saved = saved.copy()
        saved["original_method"] = saved.method
        saved["point"] = numeric(saved, "mean" if category["support"] == "bernoulli" else "median")
        saved["source_field"] = "saved_cdf_probability" if category["support"] == "bernoulli" else "saved_cdf_lower_median"
        saved["method"] = method
        if category["support"] == "bernoulli":
            saved["family"] = "bernoulli"
    else:
        saved = saved.copy()
        saved["point"], saved["source_field"] = numeric(saved, "mean"), "literal_saved_point"
    if mode == "joint_learner_source_reconstruction":
        from .median_boosting_evaluation import source_change_control
        result, audit, receipt = source_change_control(saved, offered, category, method)
        receipt["retained_source_binding"] = binding
        if audit_directory is not None:
            audit.to_parquet(Path(audit_directory) / (method + "-outer-source-audit.parquet"), index=False)
            write_json(Path(audit_directory) / (method + "-source-comparison.json"), receipt)
        result.attrs["source_comparison"] = receipt
        return result
    return bind_saved_control(saved, offered, category, method)


def interval(candidate, control, category, role_subset, cluster):
    """Reuse the registered evaluator with explicit temporary point aliases.

    The old API requires mean/median column names. These local aliases exist
    only to pass point losses into that calculation; they are never persisted
    as model outputs and establish no mean/median semantics for this model.
    """
    from .cdf_evaluation import paired_interval
    a, b = candidate.copy(), control.copy()
    a["mean"], a["median"], b["mean"] = a.point, a.point, b.point
    value = paired_interval(a, b, category["support"], cluster=cluster,
                            primary_roles_only=role_subset, replicates=500)
    value["primary_loss"] = "brier" if category["support"] == "bernoulli" else "point_mae"
    value["point_api_adapter"] = "temporary old-evaluator aliases only; candidate remains point heuristic"
    return value


def point_summary(rows, category):
    import numpy as np
    from .cdf_engine import numeric, valid_support
    from .website_cdf_evaluation import point_metrics
    y, point = numeric(rows, "actual"), numeric(rows, "point")
    good = rows.participation_state.eq("played").to_numpy() & valid_support(y, category["support"]) & np.isfinite(point)
    result = {"offered_rows": len(rows), "scored_rows": int(good.sum()), "missing_points": int((~np.isfinite(point)).sum()),
        "outcome_states": rows.outcome_state.value_counts(dropna=False).to_dict(),
        "point_metrics": point_metrics(point[good], y[good]),
        "players": int(rows.loc[good, "player_id"].nunique()), "games": int(rows.loc[good, "game_id"].nunique()),
        "weeks": len(rows.loc[good, ["season", "week"]].drop_duplicates())}
    if category["support"] == "bernoulli":
        from .median_boosting_evaluation import log_loss_summary, reliability
        result.update(brier=float(np.mean((point[good] - y[good]) ** 2)) if good.any() else None,
            **log_loss_summary(point[good], y[good]), reliability_deciles=reliability(point[good], y[good]))
    return result


def point_pairs(candidate, control, category, *, role_subset=False):
    """Adapt the old evaluator without its candidate/control point collision."""
    from .website_cdf_evaluation import paired_rows
    adapted = candidate.copy()
    adapted["comparison_candidate_point"] = adapted.point
    report, rows = paired_rows(adapted, control, category, role_subset=role_subset,
                              candidate_point="comparison_candidate_point")
    report["candidate_point"] = "point"
    return report, rows.drop(columns="comparison_candidate_point")


def report_cell(candidate, controls, category, *, historical, family="pure", pooled_primary=False):
    import pandas as pd
    report = {"target": category["target"], "method_family": family,
        "summary": point_summary(candidate, category), "paired": [], "subgroups": [],
        "semantics": DESIGN["numeric_semantics"] if category["support"] != "bernoulli" else "genuine Bernoulli probability"}
    deltas = []
    for method, control in controls.groupby("method", sort=True):
        for role_subset in [False, True]:
            result, rows = point_pairs(candidate, control, category, role_subset=role_subset)
            result.update(comparator=method, status="primary" if family == "pure" and
                ((historical and pooled_primary and method == "old_cdf" and not role_subset) or (not historical and method == "website" and not role_subset)) else "secondary")
            eligible = rows.loc[rows.paired_eligible]
            result["players"] = int(eligible.player_id.nunique())
            if category["support"] == "bernoulli":
                from .median_boosting_evaluation import log_loss_summary, reliability
                result["paired_binary"] = {
                    "candidate": log_loss_summary(eligible.candidate_point, eligible.actual),
                    "control": log_loss_summary(eligible.literal_control_point, eligible.actual),
                    "candidate_reliability_deciles": reliability(eligible.candidate_point, eligible.actual),
                    "control_reliability_deciles": reliability(eligible.literal_control_point, eligible.actual)}
            if historical:
                result["uncertainty"] = "exposed current-vintage historical reconstruction; all fixed comparisons retained"
                result["intervals"] = [interval(candidate, control, category, role_subset, c) for c in ["week", "game"]]
            rows["comparator"], rows["population"] = method, result["population"]
            report["paired"].append(result)
            deltas.append(rows)
    for dimension in ["position", "season", "team", "opponent", "fallback", "history_state", "outcome_state"]:
        if dimension in candidate:
            for value, part in candidate.groupby(dimension, dropna=False):
                report["subgroups"].append({"dimension": dimension, "value": str(value), **point_summary(part, category)})
    return report, pd.concat(deltas, ignore_index=True)


def score_report(registry_path, output):
    import pandas as pd
    from .cdf_engine import KEYS, assert_composite_contract
    from .median_boosting import score_frozen_rows
    from .website_cdf_evaluation import bind_outcomes, literal_controls, normalize_keys
    registry, output = check_seal(registry_path), Path(output).resolve()
    freeze_path = output / "forecast-freeze.json"
    if output != Path(registry["output_directory"]).resolve() or not freeze_path.is_file() or (output / "score-consumed.json").exists():
        raise ValueError("sealed global freeze required; one score pass only")
    freeze = json.loads(freeze_path.read_text())
    if digest(output / "attempts.json") != freeze["attempts_sha256"]:
        raise ValueError("attempt status changed after freeze")
    for relative, sha in freeze["bindings"].items():
        if digest(output / relative) != sha:
            raise ValueError("frozen bytes changed: " + relative)
    with (output / "score-consumed.json").open("x") as handle:
        json.dump({"at": datetime.now(timezone.utc).isoformat(), "forecast_freeze_sha256": digest(freeze_path), "score_passes": 1}, handle)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    event(output / "events.jsonl", "SCORE_PASS_CONSUMED")
    # Both outcome lanes are first opened after the sole score consumption.
    history = pd.read_parquet(registry["inputs"]["training_features"]["path"], filters=[("season", ">=", 2022), ("season", "<=", 2024)])
    outcomes = normalize_keys(pd.read_parquet(registry["inputs"]["outcomes"]["path"]))
    opportunities = normalize_keys(pd.read_parquet(registry["inputs"]["opportunities"]["path"]))
    identity = KEYS + ["target"]
    coverage = opportunities[identity].merge(outcomes[identity], on=identity, how="outer", indicator=True, validate="one_to_one")
    if not coverage._merge.eq("both").all():
        raise ValueError("all original opportunities including blocked PPR must remain")
    statuses, slots, pooled = json.loads((output / "attempts.json").read_text()), [], {}
    panel_rows = {}
    for status in statuses:
        slot = dict(status)
        if status["state"] != "PREDICTION_FROZEN":
            slots.append(dict(slot, method_family="pure"))
            if status["period"] == "website_week6":
                slots.append(dict(slot, method_family="website_equalweight_secondary"))
            continue
        target, panel, period = status["target"], status["panel"], status["period"]
        category, directory = registry["categories"][target], output / status["trial"]
        query = pd.read_parquet(directory / "query.parquet")
        historical = period != "website_week6"
        if historical:
            offered = history.loc[history.season.eq(int(period))].copy()
            # Restore original offered order using unique identity, never outcomes.
            offered = query[KEYS].merge(offered, on=KEYS, how="left", sort=False, validate="one_to_one")
            assert_composite_contract(offered, category)
        else:
            offered = bind_outcomes(query, outcomes, category)
        scored = score_frozen_rows(offered, pd.read_parquet(directory / "candidate-frozen.parquet"), category)
        scored.to_parquet(directory / "candidate-scored.parquet", index=False)
        prior = score_frozen_rows(offered, pd.read_parquet(directory / "role-prior-frozen.parquet"), category)
        prior.to_parquet(directory / "role-prior-scored.parquet", index=False)
        controls = [saved_control(binding, offered, category, method, mode=registry["source_packet_mode"], audit_directory=directory, panel=panel)
            for method, binding in registry["saved_controls"][target][panel][period].items()]
        source_comparisons = [c.attrs["source_comparison"] for c in controls if "source_comparison" in c.attrs]
        if not historical:
            controls.append(literal_controls(pd.read_parquet(directory / "literal-offers.parquet"), scored, category))
        controls = pd.concat(controls, ignore_index=True)
        controls.to_parquet(directory / "controls-scored.parquet", index=False)
        report, deltas = report_cell(scored, controls, category, historical=historical)
        report["role_prior"] = point_summary(prior, category)
        report["source_comparisons"] = source_comparisons
        write_json(directory / "report.json", report)
        deltas.to_parquet(directory / "paired-row-deltas.parquet", index=False)
        slots.append(dict(slot, state="SCORED_DESCRIPTIVE", method_family="pure", primary_comparisons=[x for x in report["paired"] if x["status"] == "primary"], report_sha256=digest(directory / "report.json")))
        # Persist full provenance above, but retain only point-scoring columns
        # across cells so88 wide source/control frames cannot exhaust RSS.
        candidate_fields = KEYS + ["actual", "participation_state", "outcome_state", "primary_role", "fallback",
            "point", "position", "team", "opponent", "history_state", "probability", "log_score", "target"]
        compact_candidate = scored[[c for c in candidate_fields if c in scored]].copy()
        panel_rows[(target, panel, period)] = compact_candidate
        if historical:
            control_fields = KEYS + ["actual", "participation_state", "point", "primary_role", "method"]
            compact_controls = controls[control_fields].copy()
            pooled.setdefault((target, panel), []).append((compact_candidate, compact_controls, int(period)))
        else:
            ensemble = score_frozen_rows(offered, pd.read_parquet(directory / "ensemble-frozen.parquet"), category)
            ensemble.to_parquet(directory / "ensemble-scored.parquet", index=False)
            blend_report, blend_deltas = report_cell(ensemble, controls, category, historical=False, family="website_equalweight_secondary")
            write_json(directory / "ensemble-report.json", blend_report)
            blend_deltas.to_parquet(directory / "ensemble-paired-row-deltas.parquet", index=False)
            slots.append(dict(slot, state="SCORED_DESCRIPTIVE", method_family="website_equalweight_secondary", report_sha256=digest(directory / "ensemble-report.json")))
    aggregate = []
    for (target, panel), cells in pooled.items():
        candidate = pd.concat([x[0] for x in cells], ignore_index=True)
        controls = pd.concat([x[1] for x in cells], ignore_index=True)
        report, _ = report_cell(candidate, controls, registry["categories"][target], historical=True, pooled_primary=True)
        report.update(panel=panel, compared_complete_years=[x[2] for x in cells], excluded_years=[int(p) for p in PERIODS[:-1] if int(p) not in [x[2] for x in cells]],
            partial_failure_policy="only complete same annual cells paired; no surviving-panel selection")
        aggregate.append(report)
    ablations = []
    for target in TARGETS:
        if registry["categories"][target]["state"] != "READY":
            continue
        for period in PERIODS:
            if (target, "base", period) not in panel_rows or (target, "context", period) not in panel_rows:
                continue
            base, context = panel_rows[(target, "base", period)], panel_rows[(target, "context", period)]
            for role_subset in [False, True]:
                value, rows = point_pairs(context, base, registry["categories"][target], role_subset=role_subset)
                value.update(target=target, period=period, comparison="context_minus_base", status="secondary")
                if period != "website_week6":
                    value["intervals"] = [interval(context, base, registry["categories"][target], role_subset, c) for c in ["week", "game"]]
                    value["uncertainty"] = "exposed reconstructed historical; nominal descriptive intervals"
                ablations.append(value)
    primary_slots = []
    for target in TARGETS:
        for panel in ["base", "context"]:
            blocked = registry["categories"][target]["state"] != "READY"
            pooled_report = next((x for x in aggregate if x["target"] == target and x["panel"] == panel), None)
            primary = next((x for x in pooled_report["paired"] if x["status"] == "primary"), None) if pooled_report else None
            primary_slots.append({"target": target, "panel": panel, "period": "pooled2022-2024", "method_family": "pure",
                "state": "BLOCKED_CATEGORY_CONTRACT" if blocked else "SCORED_DESCRIPTIVE" if pooled_report and not pooled_report["excluded_years"] else "PARTIAL_ANNUAL_FAILURES_RETAINED" if pooled_report else "FAILED_OR_SKIPPED_RETAINED",
                "primary": primary, "compared_complete_years": pooled_report["compared_complete_years"] if pooled_report else [],
                "excluded_years": pooled_report["excluded_years"] if pooled_report else [2022, 2023, 2024]})
            website_slot = next((x for x in slots if x["target"] == target and x["panel"] == panel and x["period"] == "website_week6" and x.get("method_family") == "pure"), None)
            primary_slots.append({"target": target, "panel": panel, "period": "website_week6", "method_family": "pure",
                "state": "BLOCKED_CATEGORY_CONTRACT" if blocked else website_slot["state"] if website_slot else "FAILED_OR_SKIPPED_RETAINED",
                "primary": next(iter(website_slot.get("primary_comparisons", [])), None) if website_slot else None})
    write_json(output / "median-boosting-report.json", {"registration_id": VERSION, "slots": slots, "primary_slots": primary_slots,
        "primary_contrast_slots": 48, "supported_primary_contrasts": 44, "blocked_ppr_primary_contrasts": 4,
        "planned_target_panel_period_slots": 96, "blocked_ppr_attempt_slots": 8, "secondary_website_blend_slots": 24,
        "historical_pooled": aggregate, "context_ablations": ablations, "model_design": DESIGN,
        "ensemble_design": ENSEMBLE_DESIGN, "comparisons": COMPARISONS,
        "original_opportunity_rows": len(opportunities), "source_qualification": registry["source_qualification"],
        "prior_search_and_exposure": registry["prior_search_and_exposure"], "budgets": registry["budgets"],
        "score_passes": 1, "new_qualified_replacements": [], "source_packet_mode": registry["source_packet_mode"],
        "confirmation": "none; all periods exposed; no independent confirmation, prospective or promotion claim"})
    event(output / "events.jsonl", "SCORE_REPORT_COMPLETED", sha256=digest(output / "median-boosting-report.json"))


def monitored_process(arguments, output, directory, *, remaining_wall, remaining_cpu, per_trial=True):
    begin, before, reason, peak = time.monotonic(), resource.getrusage(resource.RUSAGE_CHILDREN), None, 0
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
               MKL_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2", PYTHONPATH=str(root))
    with (directory / "stdout.log").open("x") as stdout, (directory / "stderr.log").open("x") as stderr:
        process = subprocess.Popen([sys.executable, "-m", "nfl_lab.median_boosting_campaign", *arguments], cwd=root,
            env=env, stdout=stdout, stderr=stderr, start_new_session=True)
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
        raise ValueError("output differs from sealed create-only directory")
    output.mkdir(parents=True, exist_ok=False)
    began, parent_cpu, cpu_used, attempts, statuses = time.monotonic(), time.process_time(), 0., 0, []
    log, budget = output / "events.jsonl", registry["budgets"]
    write_json(output / "registry.json", registry)
    write_json(output / "environment.json", environment_receipt())
    event(log, "CAMPAIGN_STARTED", registry_sha256=digest(registry_path), budgets=budget)
    # Historical cells are attempted first; no phase is scored until all freeze.
    for period in PERIODS:
        for target in TARGETS:
            for panel in ["base", "context"]:
                relative = f"trials/{target}/{panel}/{period}"
                status = {"target": target, "panel": panel, "period": period, "trial": relative}
                remaining_wall = budget["campaign_wall_seconds"] - (time.monotonic() - began)
                remaining_cpu = budget["campaign_cpu_seconds"] - cpu_used - (time.process_time() - parent_cpu)
                if registry["categories"][target]["state"] != "READY":
                    status["state"] = "BLOCKED_CATEGORY_CONTRACT"
                elif remaining_wall <= budget["reporting_wall_reserve_seconds"] or remaining_cpu <= 0:
                    status["state"] = "SKIPPED_CAMPAIGN_BUDGET"
                elif attempts >= budget["maximum_candidate_fit_attempts"]:
                    status["state"] = "SKIPPED_FIT_BUDGET"
                elif directory_bytes(output) >= budget["private_output_bytes"]:
                    status["state"] = "SKIPPED_OUTPUT_BUDGET"
                if "state" not in status:
                    attempts += 1
                    directory = output / relative
                    directory.mkdir(parents=True, exist_ok=False)
                    write_json(directory / "attempt-consumed.json", {"attempt": attempts, **status})
                    event(log, "ATTEMPT_CONSUMED", attempt=attempts, **status)
                    usage = monitored_process(["predict-trial", str(registry_path), str(directory), target, panel, period], output, directory,
                        remaining_wall=remaining_wall - budget["reporting_wall_reserve_seconds"], remaining_cpu=remaining_cpu)
                    cpu_used += usage["cpu_seconds"]
                    frozen = usage["returncode"] == 0 and (directory / "prediction-manifest.json").is_file()
                    status.update(usage, state="PREDICTION_FROZEN" if frozen else "FAILED_CONSUMED")
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
    write_json(output / "forecast-freeze.json", {"bindings": bindings, "attempts_sha256": digest(output / "attempts.json"),
        "fit_attempts": attempts, "score_passes": 0, "evidence": "postgame calculation order only; no prospective issuance"})
    event(log, "ALL_FORECASTS_FROZEN", sha256=digest(output / "forecast-freeze.json"), fit_attempts=attempts)
    reporting = output / "reporting"
    reporting.mkdir(exist_ok=False)
    remaining_wall = budget["campaign_wall_seconds"] - (time.monotonic() - began)
    remaining_cpu = budget["campaign_cpu_seconds"] - cpu_used - (time.process_time() - parent_cpu)
    if remaining_wall > 0 and remaining_cpu > 0 and directory_bytes(output) < budget["private_output_bytes"]:
        usage = monitored_process(["score-report", str(registry_path), str(output)], output, reporting,
            remaining_wall=remaining_wall, remaining_cpu=remaining_cpu, per_trial=False)
        cpu_used += usage["cpu_seconds"]
    else:
        usage = {"reason": "CAMPAIGN_BUDGET_BEFORE_SCORE", "returncode": None}
    completed = usage["returncode"] == 0 and (output / "median-boosting-report.json").is_file()
    write_json(output / "completion.json", {"state": "COMPLETED_DESCRIPTIVE" if completed else "INCOMPLETE_RETAINED_NO_RESTART",
        "fit_attempts_consumed": attempts, "score_pass_consumed": (output / "score-consumed.json").exists(),
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
    p.add_argument("panel", choices=["base", "context"])
    p.add_argument("period", choices=PERIODS)
    args = parser.parse_args()
    if args.command == "run":
        if not run(args.registry, args.output):
            raise SystemExit(1)
    elif args.command == "predict-trial":
        prediction_trial(args.registry, args.output, args.target, args.panel, args.period)
    else:
        score_report(args.registry, args.output)


if __name__ == "__main__":
    main()
