"""Bounded direct-learner development screen on the existing source packet.

Reuse the common loader, qualification, point scores and paired uncertainty.
All new forecasts freeze before scoring; original controls are read only in
that later phase. This module never acquires data or changes a live model.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from . import direct_boosters as direct, source_matched_benchmark as shared
from . import cdf_engine as cdf, models, operational_sources
from .operational_storage import OperationalStorage, StorageIntegrityError, StorageQuotaError
from .owned_reference_batch import validate_owned_references
from .reference_runtime import _deadline
from .role_boosting_campaign import point_pairs, summary
from .source_matched_reporting import _aligned, _bootstrap

VERSION = "direct-booster-screen-v1-20261023"
METHODS = tuple("direct_" + library + "_" + complexity
                for library in direct.LIBRARIES for complexity in direct.COMPLEXITIES)
CONTROLS = ("leaf_cdf", "count_A", "role_B", "recent", "pooled")


class Session(shared.Session):
    def __init__(self, config, config_sha256, *, phase, prior=None):
        config = Path(config)
        if shared.sha(config) != config_sha256:
            raise ValueError("direct screen registration hash mismatch")
        self.config_sha256, self.spec = config_sha256, json.loads(config.read_text())
        s = self.spec
        if s["registration_id"] != VERSION or s["methods"] != list(METHODS) or s["partitions"]["evaluation_years"] != list(shared.YEARS):
            raise ValueError("fixed six-pipeline/three-block screen required")
        expected = {lib: {level: {support: direct.parameters(lib, level, support)
                    for support in ("count", "signed_integer", "bernoulli")}
                    for level in direct.COMPLEXITIES} for lib in direct.LIBRARIES}
        if s["native_parameters"] != expected or set(s["versions"]) != set(direct.LIBRARIES):
            raise ValueError("frozen algorithms or version inventory changed")
        self.budget = shared.Budget(s["budgets"], prior=prior, phase=phase)
        self.source = shared._spec(s["input_features"])
        self.source_manifest = shared._spec(s["source_manifest"])
        self.policy = operational_sources.load_source_policy(shared._spec(s["source_policy"]))
        self.categories = json.loads(shared._spec(s["category_contract"]).read_text())["categories"]
        if set(self.categories) != set(models.TARGETS) or self.categories["fantasy_ppr"]["state"] == "READY":
            raise ValueError("all twelve categories, exact PPR blocked, required")
        for target in models.TARGETS:
            if target != "fantasy_ppr":
                cdf.validate_category(shared._category(self.categories, target))
        self.control_freeze = json.loads(shared._spec(s["control_scored_freeze"]).read_text())
        self.storage = OperationalStorage(s["cache"], self.policy)
        self.output = self.storage.register_root(s["output"])
        self.bindings = {}


def planned_slots(categories, versions):
    slots = []
    for year in shared.YEARS:
        for target in models.TARGETS:
            for library in direct.LIBRARIES:
                for complexity in direct.COMPLEXITIES:
                    state = ("BLOCKED_EXACT_PPR" if categories[target]["state"] != "READY" else
                             "UNAVAILABLE_CAPABILITY" if not versions[library] else "UNRUN")
                    slots.append(dict(year=year, target=target, library=library,
                        complexity=complexity, method="direct_" + library + "_" + complexity, state=state))
    return slots


def run_screen(config, *, config_sha256):
    session = Session(config, config_sha256, phase="run")
    if (session.output / "RUN_CONSUMED.json").exists():
        raise RuntimeError("screen already consumed; no retraining or retry")
    slots = planned_slots(session.categories, session.spec["versions"])
    session.write("RUN_CONSUMED.json", {"at": shared.now(), "registration_sha256": config_sha256})
    session.write("planned-slots.json", slots)
    fatal = None
    try:
        operational_sources._verify(session.source_manifest.parent, storage=session.storage)
        with threadpool_limits(limits=2):
            for year in shared.YEARS:
                session.budget.check()
                train, query, audit = shared.fold(session.source, year)
                previous = json.loads(shared._spec(session.spec["partition_audits"][str(year)]).read_text())
                if audit != previous:
                    raise ValueError("source-matched feature/query/training partition differs from original controls")
                session.frame(f"private/queries/{year}.parquet", query)
                session.write(f"partitions/{year}.json", audit)
                for slot in [s for s in slots if s["year"] == year and s["state"] == "UNRUN"]:
                    category = shared._category(session.categories, slot["target"])
                    relative = f"private/cells/{year}/{slot['target']}/{slot['method']}"
                    try:
                        session.budget.check()
                        with ExitStack() as guards:
                            def consume(attempt):
                                session.budget.check(fit=True)
                                number = session.budget.fits
                                session.write(f"fit-attempts/{number:03d}.json", {"at": shared.now(), **slot, **attempt})
                                guards.enter_context(shared.estimator_cpu_guard(session, number))
                                guards.enter_context(shared.cpu_deadline(session.spec["budgets"]["per_estimator_CPU_seconds"]))
                                guards.enter_context(_deadline(session.spec["budgets"]["per_estimator_wall_seconds"]))
                            model = direct.DirectBoosterModel.fit(train, category, "base",
                                library=slot["library"], complexity=slot["complexity"],
                                expected_version=session.spec["versions"][slot["library"]], fit_gate=consume)
                        session.model(relative + "/model.joblib", model)
                        session.budget.check(rows=len(query))
                        rows = shared.normalized(direct.prediction_rows(model, query), category, slot["method"])
                        if not rows[cdf.KEYS].reset_index(drop=True).equals(query[cdf.KEYS].reset_index(drop=True)):
                            raise ValueError("forecast changed offered identities/order")
                        session.frame(relative + "/forecast-frozen.parquet", rows)
                        slot.update(state="PREDICTION_FROZEN", rows=len(rows), fit_state=model.audit["fit_state"],
                            forecast=relative + "/forecast-frozen.parquet", model=relative + "/model.joblib",
                            query=f"private/queries/{year}.parquet")
                        del model
                    except (shared.BudgetExhausted, StorageQuotaError, StorageIntegrityError):
                        slot["state"] = "FAILED_RESOURCE"
                        raise
                    except Exception as error:
                        slot.update(state="FAILED", reason=type(error).__name__)
                        session.failure(relative + "/FAILURE.json", error)
                session.write(f"year-freezes/{year}.json", {"at": shared.now(), "slots": [s for s in slots if s["year"] == year]})
    except BaseException as error:
        fatal = error
        session.failure("RUN_FAILURE.json", error)
    session.write("attempts.json", slots)
    freeze = dict(state="GLOBAL_FORECASTS_FROZEN", at=shared.now(), registration_sha256=config_sha256,
        slots=slots, usage=session.budget.usage(), bindings=dict(session.bindings),
        fatal=type(fatal).__name__ if fatal else None,
        labels="No scoring-role labels read; exposed earlier blocks used only for later-block training after their own freeze")
    session.write("forecast-freeze.json", freeze, freeze=False)
    return freeze


def product_pairs(candidate, control, category, *, role_subset=False):
    """Use existing identity/eligibility/metric evaluator; count means use MSE."""
    _aligned(candidate, control)
    report, rows = point_pairs(candidate, control, category, role_subset=role_subset)
    if category["support"] == "count":
        good = rows.paired_eligible.to_numpy()
        a, b, y = (cdf.numeric(rows, name) for name in ("candidate_point", "literal_control_point", "actual"))
        rows.loc[good, "candidate_loss"] = (a[good] - y[good]) ** 2
        rows.loc[good, "control_loss"] = (b[good] - y[good]) ** 2
        rows.loc[good, "delta_candidate_minus_control"] = rows.loc[good, "candidate_loss"] - rows.loc[good, "control_loss"]
        ac = float(rows.loc[good, "candidate_loss"].mean()) if good.any() else None
        bc = float(rows.loc[good, "control_loss"].mean()) if good.any() else None
        report.update(primary_loss="mse", candidate_loss=ac, control_loss=bc,
            delta_candidate_minus_control=ac - bc if ac is not None else None,
            improvement_pct=100 * (bc - ac) / bc if bc not in (None, 0) else None)
    report["uncertainty"] = "Exposed development; nominal whole-game/week diagnostics; no independent confirmation or promotion"
    report["forecast_finite_masks_equal"] = bool(np.array_equal(np.isfinite(cdf.numeric(rows, "candidate_point")), np.isfinite(cdf.numeric(rows, "literal_control_point"))))
    rows = rows.merge(candidate[cdf.KEYS + ["cutoff_utc", "kickoff_utc"]], on=cdf.KEYS, validate="one_to_one")
    return report, rows


def _control(session, year, target, method, category):
    relative = f"private/scored/{year}/{target}/{method}/rows.parquet"
    expected = session.control_freeze["bindings"].get(relative)
    if not expected or relative not in session.control_freeze["scored_files"]:
        raise ValueError("original exact scored control not frozen")
    path = Path(session.spec["control_root"]) / relative
    if session.authenticated_controls.get(str(path), {}).get("sha256") != expected:
        raise ValueError("control not authenticated in full owned-reference entry batch")
    fields = list(shared.REPORT_FIELDS)
    rows = pd.read_parquet(path, columns=fields)
    if method == "leaf_cdf" and category["support"] == "count":
        rows["point"] = rows["mean"]
        rows["point_semantics"] = "original_frozen_CDF_mean_not_median"
    rows["method"] = method
    return rows


def report_screen(config, *, config_sha256):
    session = Session(config, config_sha256, phase="report")
    freeze_path = session.output / "forecast-freeze.json"
    session.storage.validate_reference(freeze_path)
    freeze = json.loads(freeze_path.read_text())
    if freeze["registration_sha256"] != config_sha256:
        raise ValueError("forecast freeze has different registration")
    owned = {str(freeze_path): shared.sha(freeze_path)}
    for relative, expected in freeze["bindings"].items():
        path = session.output / relative
        if path.resolve() != path.absolute() or session.output not in path.parents:
            raise ValueError("unsafe frozen artifact path")
        owned[str(path)] = expected
    for year in shared.YEARS:
        for target in models.TARGETS:
            if target == "fantasy_ppr":
                continue
            for method in CONTROLS:
                relative = f"private/scored/{year}/{target}/{method}/rows.parquet"
                expected = session.control_freeze["bindings"].get(relative)
                path = Path(session.spec["control_root"]) / relative
                if not expected or relative not in session.control_freeze["scored_files"] or path.resolve() != path.absolute():
                    raise ValueError("required original control binding missing or unsafe")
                owned[str(path)] = expected
    owned[session.spec["control_scored_freeze"]["path"]] = session.spec["control_scored_freeze"]["sha256"]
    session.authenticated_controls, entry = validate_owned_references(session.storage, owned)
    started, cpu_started = session.budget.start, session.budget.cpu_start
    session.budget = shared.Budget(session.spec["budgets"], prior=freeze["usage"], phase="report")
    session.budget.start, session.budget.cpu_start = started, cpu_started
    if (session.output / "SCORE_CONSUMED.json").exists():
        raise RuntimeError("one score pass already consumed; no silent restart")
    session.write("owned-reference-entry.json", entry)
    session.write("SCORE_CONSUMED.json", {"at": shared.now(), "forecast_freeze_sha256": shared.sha(freeze_path)})
    scored_slots = []
    with shared.no_fits():
        for year in shared.YEARS:
            successful = [s for s in freeze["slots"] if s["year"] == year and s["state"] == "PREDICTION_FROZEN"]
            if not successful:
                continue
            session.budget.check()
            labels, audit = shared.read_partition(session.source, year, "labels", allow_labels=True)
            session.write(f"scoring/label-read-{year}.json", audit)
            query = pd.read_parquet(session.output / f"private/queries/{year}.parquet")
            for target in models.TARGETS:
                selected = [s for s in successful if s["target"] == target]
                if not selected:
                    continue
                category = shared._category(session.categories, target)
                offered = shared._outcomes(query, labels, category)
                for slot in selected:
                    session.budget.check()
                    frozen = pd.read_parquet(session.output / slot["forecast"])
                    scored = direct.score_frozen_rows(offered, frozen, category)
                    relative = f"private/scored/{year}/{target}/{slot['method']}.parquet"
                    session.frame(relative, shared.normalized(scored, category, slot["method"]))
                    scored_slots.append({**slot, "state": "COMPLETED", "scored": relative})
        session.write("scored-freeze.json", {"at": shared.now(), "slots": scored_slots,
            "bindings": dict(session.bindings), "usage": session.budget.usage()})
        report = dict(version=VERSION, at=shared.now(), evidence="EXPOSED_SOURCE_MATCHED_DEVELOPMENT",
            historical_raw_Sleeper="UNAVAILABLE", historical_SITE="UNAVAILABLE", promotion="NONE",
            slots=[next((done for done in scored_slots if (done["year"], done["target"], done["method"]) ==
                    (slot["year"], slot["target"], slot["method"])), slot) for slot in freeze["slots"]], targets={})
        for target in models.TARGETS:
            session.budget.check()
            category = shared._category(session.categories, target)
            selected = [s for s in scored_slots if s["target"] == target]
            if not selected:
                report["targets"][target] = dict(state="BLOCKED_EXACT_PPR" if target == "fantasy_ppr" else "NO_COMPLETED_FORECASTS")
                continue
            frames = [pd.read_parquet(session.output / s["scored"]) for s in selected]
            rows = pd.concat(frames, ignore_index=True)
            controls = pd.concat([_control(session, year, target, method, category)
                for year in sorted(rows.season.unique()) for method in CONTROLS], ignore_index=True)
            item, losses = target_report(rows, controls, category, session.budget.check)
            report["targets"][target] = item
            session.frame(f"private/paired-losses/{target}.parquet", losses)
            session.frame(f"private/subgroups/{target}.parquet", subgroup_rows(rows, category))
        for relative, expected in session.bindings.items():
            owned[str(session.output / relative)] = expected
        _, exit_receipt = validate_owned_references(session.storage, owned)
        session.write("owned-reference-exit.json", exit_receipt)
        session.budget.check()
        session.write("report.json", {"report": report, "usage": session.budget.usage(),
            "forecast_freeze_sha256": shared.sha(freeze_path)}, freeze=False)
    return report


def target_report(rows, controls, category, check=lambda: None):
    """Pure aggregation of already frozen/scored rows, no source/model access."""
    target = category["target"]
    report, private = dict(target=target, primary_metric=direct.product(category["support"])[1], summaries=[], pairs=[]), []
    for method, part in rows.groupby("method", sort=False):
        for period in (*shared.YEARS, "pooled_2022_2024"):
            a = part if isinstance(period, str) else part.loc[part.season.eq(period)]
            if a.empty:
                continue
            check()
            available = sorted(int(y) for y in a.season.unique())
            missing = sorted(set(shared.YEARS) - set(available)) if isinstance(period, str) else []
            completion = "PARTIAL_REQUIRED_YEARS" if missing else "COMPLETE_REQUIRED_YEARS" if isinstance(period, str) else "ANNUAL"
            for primary in (False, True):
                population = "primary_roles" if primary else "all_offered"
                subset = a.loc[a.primary_role] if primary else a
                value = summary(subset, category)
                value.update(method=method, period=period, population=population, included_years=available,
                    missing_required_years=missing, completion=completion,
                    fallback_reasons=subset.fallback.fillna("").value_counts().to_dict())
                report["summaries"].append(value)
                for comparator in CONTROLS:
                    b = controls.loc[controls.method.eq(comparator) & controls.season.isin(a.season.unique())]
                    paired, losses = product_pairs(a, b, category, role_subset=primary)
                    paired.update(candidate=method, comparator=comparator, period=period, population=population,
                        included_years=available, missing_required_years=missing, completion=completion)
                    if isinstance(period, str):
                        mask = losses.paired_eligible.to_numpy()
                        paired["week_interval"] = _bootstrap(losses, mask, "week", 500, 1703)
                        paired["game_interval"] = _bootstrap(losses, mask, "game", 500, 1703)
                        if not primary:
                            compact = losses[cdf.KEYS + ["primary_role", "paired_eligible", "candidate_loss", "control_loss", "delta_candidate_minus_control"]].copy()
                            compact["candidate"], compact["comparator"] = method, comparator
                            private.append(compact)
                    report["pairs"].append(paired)
    losses = pd.concat(private, ignore_index=True) if private else pd.DataFrame()
    for name in ("candidate", "comparator", "player_id", "game_id"):
        if name in losses:
            losses[name] = losses[name].astype("category")
    report["research_nominations"] = research_nominations(report)
    return report, losses


def research_nominations(report):
    """Apply frozen development checks; never scientific/release qualification."""
    def finite(value):
        return (isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_))
                and bool(np.isfinite(value)))
    result = []
    for method in sorted({p["candidate"] for p in report["pairs"]}):
        reasons = []
        for comparator in ("leaf_cdf", "role_B"):
            selected = [p for p in report["pairs"] if p["candidate"] == method
                        and p["comparator"] == comparator and p["population"] == "primary_roles"]
            pooled = next((p for p in selected if p["period"] == "pooled_2022_2024"), None)
            if pooled is None or pooled.get("missing_required_years"):
                reasons.append(comparator + ":missing_required_years")
                continue
            if (not finite(pooled["improvement_pct"]) or not finite(pooled["candidate_loss"])
                    or not finite(pooled["control_loss"]) or pooled["improvement_pct"] < 2):
                reasons.append(comparator + ":less_than_2pct_primary_gain")
            if not pooled["forecast_finite_masks_equal"]:
                reasons.append(comparator + ":forecast_coverage_changed")
            metrics = (pooled["candidate_point_metrics"], pooled["control_literal_point_metrics"])
            for name in ("bias_prediction_minus_actual", "absolute_error_p95"):
                a, b = (m[name] for m in metrics)
                if not finite(a) or not finite(b) or abs(a) > 1.02 * abs(b):
                    reasons.append(comparator + ":secondary_regression:" + name)
            annual = [p for p in selected if p["period"] in shared.YEARS]
            if {p["period"] for p in annual} != set(shared.YEARS):
                reasons.append(comparator + ":missing_annual_cell")
            for p in annual:
                a, b = p["candidate_loss"], p["control_loss"]
                if not finite(a) or not finite(b) or a > 1.05 * b:
                    reasons.append(comparator + ":annual_regression:" + str(p["period"]))
        result.append(dict(method=method, decision="DEVELOPMENT_LEAD_REQUIRES_LATER_CONFIRMATION" if not reasons else "NOT_NOMINATED",
            reasons=reasons, scientific_qualification=False, release_ready=False))
    return result


def subgroup_rows(rows, category):
    """Vectorized diagnostic errors/coverage; not subgroup winner selection."""
    y, point = cdf.numeric(rows, "actual"), cdf.numeric(rows, "point")
    good = rows.participation_state.eq("played").to_numpy() & cdf.valid_support(y, category["support"]) & np.isfinite(point)
    working = rows.copy()
    error = np.where(good, point - y, np.nan)
    working["absolute_error"], working["squared_error"], working["signed_error"] = np.abs(error), error ** 2, error
    working["supported"] = good
    working["fallback_row"] = working.fallback.fillna("").ne("")
    result = []
    for dimension in ("player_id", "position", "team", "opponent", "fallback", "history_state"):
        grouped = working.groupby(["method", dimension], sort=True, dropna=False).agg(
            offered_rows=("supported", "size"), scored_rows=("supported", "sum"),
            fallback_rows=("fallback_row", "sum"), mae=("absolute_error", "mean"),
            mse=("squared_error", "mean"), bias=("signed_error", "mean")).reset_index()
        grouped = grouped.rename(columns={dimension: "value"})
        grouped["dimension"], grouped["target"] = dimension, category["target"]
        grouped["value"] = grouped.value.astype(str)
        result.append(grouped)
    return pd.concat(result, ignore_index=True)
