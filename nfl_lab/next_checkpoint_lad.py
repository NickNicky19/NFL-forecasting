"""One bounded, training-scaled absolute-error yardage correction.

The original frozen experiment is read only. These empirical corrected points
are not CDF medians and have no live, probability, or confirmation claim.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np

VERSION = "next-nfl-checkpoint-lad-v1-20261028"
TARGETS = ("pass_yd", "rush_yd", "rec_yd", "rush_rec_yd")
BOOKS = (68, 69, 79)
KEYS = ["season", "week", "game_id", "player_id"]
UNIT = KEYS + ["target"]


class SolverFailure(RuntimeError):
    """A consumed fit could not meet its predeclared numerical certificate."""


def lower_median(values):
    values = np.asarray(values, float)
    return float(np.partition(values, (len(values) - 1) // 2)[(len(values) - 1) // 2])


def fit_lad(train_x, train_y, *, max_iter=20000, gap_tolerance=1e-7, check=None):
    """ADMM for LAD + fixed training-scaled L2 penalty, with a dual bound.

    Physical objective: sum(abs(y - Xb)) + (10 / s) * sum(slopes**2).
    The dimensionless declaration divides this expression by s. Feature
    scaling, unpenalized intercept, and nonnegative slopes match original L2.
    Rho is fixed at 1; no solver, penalty, or response-scale search occurs.
    """
    train_x, y = np.asarray(train_x, float), np.asarray(train_y, float)
    if (train_x.ndim != 2 or train_x.shape[1] not in (1, 2)
            or len(y) < 1 or len(train_x) != len(y)
            or not np.isfinite(train_x).all() or not np.isfinite(y).all()):
        raise ValueError("finite one/two-input training matrix required")
    center, scale = train_x.mean(axis=0), train_x.std(axis=0)
    scale[scale == 0] = 1.
    z = (train_x - center) / scale
    # np.median, including its even-n midpoint convention, is preregistered.
    response_scale = max(1., 1.4826 * float(np.median(np.abs(y - np.median(y)))))
    alpha = 10. / response_scale
    x = np.column_stack([np.ones(len(y)), z])
    penalty = np.diag([0.] + [2. * alpha] * z.shape[1])
    # Enumerate every slope active set. Each tiny solve is precomputed;
    # no n-by-n optimizer, hidden fit, or dependency installation is needed.
    systems = []
    for mask in range(1 << z.shape[1]):
        columns = [0] + [j + 1 for j in range(z.shape[1]) if mask & (1 << j)]
        design = x[:, columns]
        gram = design.T @ design + penalty[np.ix_(columns, columns)]
        try:
            transform = np.linalg.solve(gram, design.T)
        except np.linalg.LinAlgError as error:
            raise SolverFailure("tiny active-set linear solve failed: " + str(error)) from error
        if not np.isfinite(transform).all():
            raise SolverFailure("tiny active-set transform is nonfinite")
        systems.append((columns, transform))
    beta = np.r_[lower_median(y), np.zeros(z.shape[1])]
    residual = y - x @ beta
    dual_scaled = np.zeros(len(y))
    last = None
    for iteration in range(1, max_iter + 1):
        desired = y - residual - dual_scaled
        best, best_value = None, np.inf
        for columns, transform in systems:
            free = transform @ desired
            if np.any(free[1:] < 0.):
                continue
            candidate = np.zeros(x.shape[1])
            candidate[columns] = free
            value = alpha * float(candidate[1:] @ candidate[1:]) + .5 * float(np.sum((x @ candidate - desired) ** 2))
            if value < best_value:
                best, best_value = candidate, value
        if best is None:
            raise SolverFailure("no finite feasible active-set update")
        beta = best
        fitted = x @ beta
        value = y - fitted - dual_scaled
        residual = np.sign(value) * np.maximum(np.abs(value) - 1., 0.)
        dual_scaled += fitted + residual - y
        if iteration % 25 and iteration != max_iter:
            continue
        if check is not None:
            check()
        # Exact minimization over the unpenalized intercept improves the
        # primal upper bound without changing the objective or slope fit.
        candidate = beta.copy()
        candidate[0] = lower_median(y - z @ candidate[1:])
        primal = float(np.sum(np.abs(y - x @ candidate)) + alpha * np.sum(candidate[1:] ** 2))
        # Any zero-sum vector within [-1,1] is dual feasible. Centering and
        # rescaling is deterministic; its bound is valid without projection.
        w = -dual_scaled.copy()
        w -= w.mean()
        w /= max(1., float(np.max(np.abs(w))))
        dual = float(y @ w - np.sum(np.maximum(z.T @ w, 0.) ** 2) / (4. * alpha))
        gap = primal - dual
        feasibility = float(abs(w.sum()))
        last = {"iterations": iteration, "physical_primal": primal, "physical_dual": dual,
                "physical_gap": gap, "dimensionless_primal": primal / response_scale,
                "dual_sum_absolute": feasibility, "dual_max_absolute": float(np.max(np.abs(w))),
                "relative_gap_tolerance": gap_tolerance}
        if (np.isfinite([primal, dual, gap]).all() and feasibility <= 1e-8
                and gap >= -1e-9 * (1. + abs(primal))
                and gap <= gap_tolerance * (1. + primal)):
            return {"center": center, "scale": scale, "coef": candidate,
                    "response_scale": response_scale, "physical_alpha": alpha,
                    "dimensionless_alpha": 10., "rho": 1., "certificate": last}
    raise SolverFailure("predeclared LAD convergence cap exhausted: " + json.dumps(last, sort_keys=True))


def apply_lad(model, values):
    values = np.asarray(values, float)
    return np.column_stack([np.ones(len(values)), (values - model["center"]) / model["scale"]]) @ model["coef"]


def member_frame(ref, columns=None):
    import pandas as pd
    from .historical_market_comparison import read_capsule_member
    return pd.read_parquet(io.BytesIO(read_capsule_member(ref)), columns=columns)


def fit_forecasts(plan, budget, progress=None):
    """Only 2023 labels are opened; all original outer controls stay frozen."""
    from .historical_market_comparison import load_labels, read_capsule_member, require
    football = member_frame(plan["inputs"]["football"])
    evaluated = member_frame(plan["inputs"]["evaluation"])
    original = json.loads(read_capsule_member(plan["inputs"]["calibrators"]))["parameters"]
    require(not football.season.eq(2025).any() and not evaluated.season.eq(2025).any(), "excluded season in frozen forecasts")
    require(set(football.season.unique()) == {2023, 2024, 2026}, "frozen training/evaluation season identity changed")
    require(set(evaluated.season.unique()) == {2024, 2026}, "outer forecast season identity changed")
    evaluated = evaluated.loc[evaluated.target.isin(TARGETS) & evaluated.primary_role].copy().reset_index(drop=True)
    require(len(evaluated) == 20212 and not evaluated.duplicated(UNIT + ["book_id"]).any(), "frozen primary yardage population changed")
    evaluated = evaluated[UNIT + ["book_id", "position", "team", "opponent", "kickoff_utc", "source_collection_naive",
        "line", "source_row_number", "primary_role", "F_point", "FC_point", "M_point", "H_point", "F_fallback"]].copy()
    for arm in ["FC", "H"]:
        evaluated[arm + "_LAD_point"] = evaluated[arm + "_point"]
        evaluated[arm + "_LAD_reason"] = "ORIGINAL_L2_FALLBACK_UNFITTED"
    labels = load_labels(plan["original_plan"], [2023])
    labels = labels.loc[labels.target.isin(TARGETS)]
    train = football.loc[football.season.eq(2023) & football.target.isin(TARGETS)].merge(labels, on=UNIT, how="left", validate="many_to_one", sort=False)
    records = []
    for target in TARGETS:
        for book in BOOKS:
            earlier = train.loc[train.target.eq(target) & train.book_id.eq(book) & train.primary_role & train.outcome_state.eq("supported_played")]
            fitting = earlier.loc[np.isfinite(earlier.F_point) & np.isfinite(earlier.M_point)].copy()
            old = next(r for r in original if r.get("target") == target and r.get("excluded_offering_book") == book)["point"]
            require(len(fitting) == old["rows"] and len(fitting) >= 100 and not fitting.duplicated(KEYS).any(), "original training panel changed")
            require(all(str(book) not in str(v).split(",") for v in fitting.independent_point_books), "offering book entered training market features")
            current = evaluated.index[evaluated.target.eq(target) & evaluated.book_id.eq(book)]
            panel_hash = hashlib.sha256(fitting[KEYS].to_csv(index=False, lineterminator="\n").encode()).hexdigest()
            for arm, columns in [("FC", ["F_point"]), ("H", ["F_point", "M_point"])]:
                budget.check("meta_fits", 1)
                record = {"target": target, "excluded_offering_book": book, "arm": arm + "_LAD", "training_rows": len(fitting),
                          "training_seasons": [2023], "training_key_sha256": panel_hash, "columns": columns,
                          "fallback": "corresponding original frozen L2 point; preserve original book and cohort"}
                if progress is not None:
                    progress(len(records) + 1, {**record, "state": "FIT_ATTEMPT_STARTED"})
                try:
                    model = fit_lad(fitting[columns].to_numpy(float), fitting.actual.to_numpy(float), check=budget.check)
                    good = current[np.isfinite(evaluated.loc[current, columns]).all(axis=1)]
                    prediction = apply_lad(model, evaluated.loc[good, columns].to_numpy(float))
                    if not np.isfinite(prediction).all():
                        raise SolverFailure("new LAD prediction is nonfinite")
                    evaluated.loc[good, arm + "_LAD_point"] = prediction
                    evaluated.loc[good, arm + "_LAD_reason"] = "ACCEPTED_LAD_CORRECTION"
                    record.update(state="FIT_CERTIFIED", model=model, applied_rows=len(good))
                except SolverFailure as error:
                    evaluated.loc[current, arm + "_LAD_reason"] = "ORIGINAL_L2_FALLBACK_NUMERICAL_FIT_FAILURE"
                    record.update(state="FIT_FAILED_ORIGINAL_L2_FALLBACK", error=str(error), applied_rows=0)
                records.append(record)
                if progress is not None:
                    progress(len(records), record)
                budget.check()
    require(len(records) == 24, "exact bounded attempt count changed")
    return evaluated, records


def score_forecasts(plan, forecasts, budget):
    """Use the exact old outcomes and choose old cohort before LAD availability."""
    from .historical_market_comparison import primary_offers, paired_interval, require
    old = member_frame(plan["inputs"]["matched_scores"])
    require(not old.season.eq(2025).any(), "excluded outcomes in original matched member")
    old = old.loc[old.target.isin(TARGETS) & old.primary_role].copy()
    added = forecasts[UNIT + ["book_id", "FC_LAD_point", "H_LAD_point", "FC_LAD_reason", "H_LAD_reason"]]
    matched = old.merge(added, on=UNIT + ["book_id"], how="left", validate="one_to_one", sort=False)
    require(len(matched) == len(old), "original matched row membership changed")
    supported = matched.loc[matched.outcome_state.eq("supported_played")]
    reports, cohort_frames = [], []
    for (year, target), raw in supported.groupby(["season", "target"], observed=True, sort=True):
        # All eligibility and book priority use only original frozen arms.
        common = raw.loc[raw[[a + "_point" for a in ["F", "FC", "M", "H"]]].notna().all(axis=1)]
        point = primary_offers(common)
        require(len(point) > 0 and point[["FC_LAD_point", "H_LAD_point"]].notna().all().all(), "new arm cannot remove or switch an original case")
        cohort_frames.append(point)
        metrics = []
        for arm in ["F", "FC", "M", "H", "OFFERED_LINE_HEURISTIC", "FC_LAD", "H_LAD"]:
            values = point.line if arm == "OFFERED_LINE_HEURISTIC" else point[arm + "_point"]
            error = values.to_numpy(float) - point.actual.to_numpy(float)
            absolute = np.abs(error)
            side = (np.sign(values - point.line) == np.sign(point.actual - point.line)) & point.actual.ne(point.line) & values.ne(point.line)
            item = {"arm": arm, "rows": len(point), "MAE": float(absolute.mean()), "MSE": float(np.mean(error ** 2)),
                    "RMSE": float(np.sqrt(np.mean(error ** 2))), "bias": float(error.mean()),
                    "strict_close_rate": float(np.mean(absolute < 10)), "inclusive_close_rate": float(np.mean(absolute <= 10)),
                    "side_correct_and_strict_close_rate": float(np.mean(side & (absolute < 10))),
                    "side_correct_and_inclusive_close_rate": float(np.mean(side & (absolute <= 10)))}
            if arm in ["FC_LAD", "H_LAD"]:
                old_arm = arm.split("_")[0]
                difference = absolute - np.abs(point[old_arm + "_point"].to_numpy(float) - point.actual.to_numpy(float))
                item.update(original_L2_arm=old_arm, paired_MAE_difference_vs_original_L2=float(difference.mean()),
                            paired_vs_original_L2_game=paired_interval(point, difference, "game_id"),
                            paired_vs_original_L2_week=paired_interval(point, difference, "week"),
                            corrected_rows=int(point[arm + "_reason"].eq("ACCEPTED_LAD_CORRECTION").sum()),
                            fallback_reasons=point[arm + "_reason"].value_counts().to_dict())
                corrected = point[arm + "_reason"].eq("ACCEPTED_LAD_CORRECTION")
                item["model_only"] = {"rows": int(corrected.sum()), "MAE": float(absolute[corrected].mean()) if corrected.any() else None}
            metrics.append(item)
        reports.append({"season": int(year), "target": target, "rows": len(point), "games": int(point.game_id.nunique()),
                        "weeks": int(point.week.nunique()), "metrics": metrics,
                        "original_common_cohort_key_sha256": hashlib.sha256(point[UNIT + ["book_id"]].to_csv(index=False, lineterminator="\n").encode()).hexdigest()})
        budget.check()
    import pandas as pd
    return {"version": VERSION, "state": "EXPOSED_ARCHIVE_RESEARCH_COMPLETE", "primary_loss": "MAE yards",
            "interpretation": "2024 and2026W1-5 already exposed; timing-unverified exploration; no independent confirmation, live, probability or website claim",
            "scale_disclosure": "one dimensionless LAD recipe with training-only MAD response scale; relative shrinkage differs from original physical-unit L2; no scale/alpha/rho search",
            "cells": reports}, pd.concat(cohort_frames, ignore_index=True)
