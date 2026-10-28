"""Cached 2026 annual football controls on a fixed archived market cohort.

This separate study permits qualified pre-existing 2025 football lineage. It
never reads 2025 market quotes, fits models, loads fitted objects, or queries a
law. Ordinary line probabilities cannot be inferred from point summaries.
"""
from __future__ import annotations

import io
import json

import numpy as np
import pandas as pd

from .historical_market_comparison import (KEYS, UNIT, authenticate, read_capsule_member,
    primary_offers, apply_ridge, require, paired_interval, probability_metrics)

VERSION = "next-nfl-checkpoint-contemporary-v1-20261028"
YARDS = {"pass_yd", "rush_yd", "rec_yd", "rush_rec_yd"}
CONTEXT = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
POINT_ARMS = ["F", "FC", "H", "M", "OFFERED_LINE_HEURISTIC", "MODERN_CDF", "MODERN_FC_L2", "MODERN_H_L2", "RECENT_LEADER"]


def read_frame(ref, columns=None, filters=None):
    import pyarrow as pa
    import pyarrow.parquet as pq
    body = read_capsule_member(ref) if "container" in ref else authenticate(ref).read_bytes()
    return pq.read_table(pa.BufferReader(body), columns=columns, filters=filters, use_threads=False).to_pandas()


def document(ref):
    return json.loads(read_capsule_member(ref) if "container" in ref else authenticate(ref).read_bytes())


def normalize_context(frame):
    frame = frame.copy()
    for name in ["kickoff_utc", "cutoff_utc"]:
        if name in frame:
            frame[name] = pd.to_datetime(frame[name], utc=True, errors="raise")
    return frame


def source_vector(spec, query):
    """Admit each cached source row without changing the receiving cohort."""
    authority = document(spec["authority"])
    for path, expected in spec["authority_checks"].items():
        actual = authority
        for field in path.split("."):
            actual = actual[field]
        require(actual == expected, "cached source authority differs: " + path)
    columns = list(dict.fromkeys(KEYS + CONTEXT + [spec["value_column"], spec["fallback_column"]]
                                  + (["point"] if spec.get("point_bit_identity") else [])))
    filters = [("season", "=", 2026)]
    if spec.get("target_column"):
        filters.append(("target", "=", spec["target"]))
    frame = normalize_context(read_frame(spec["forecast"], columns=columns, filters=filters))
    require(len(frame) == 2999 and not frame.duplicated(KEYS).any() and frame.season.eq(2026).all()
            and set(frame.week) == set(range(1, 7)), "cached source full annual identity differs")
    if spec.get("point_bit_identity"):
        left, right = frame.point.to_numpy(float), frame[spec["value_column"]].to_numpy(float)
        require(np.array_equal(left.view(np.uint64), right.view(np.uint64)), "original explicit point/law-functional bits differ")
    checked = frame.merge(query[KEYS + CONTEXT], on=KEYS, how="left", validate="one_to_one", suffixes=("", "_query"), indicator=True)
    reasons = pd.Series("ACCEPTED_CACHED", index=checked.index, dtype=object)
    reasons.loc[checked._merge.ne("both")] = "ANNUAL_QUERY_KEY_MISSING"
    for column in CONTEXT:
        equal = checked[column].eq(checked[column + "_query"]) & checked[column].notna()
        reasons.loc[~equal] = "ANNUAL_QUERY_CONTEXT_MISMATCH_" + column
    values = checked[spec["value_column"]].to_numpy(float)
    valid = np.isfinite(values)
    if spec["functional"] == "count_mean":
        valid &= values >= 0
    elif spec["functional"] == "event_probability":
        valid &= (values >= 0) & (values <= 1)
    else:
        valid &= values == np.floor(values)
    reasons.loc[~valid] = "CACHED_FUNCTIONAL_UNAVAILABLE_OR_INVALID"
    cutoff = pd.Timestamp(spec["training_cutoff_utc"])
    maximum = pd.Timestamp(spec["training_max_available_utc"])
    require(maximum < cutoff, "cached annual training chronology differs")
    reasons.loc[~checked.cutoff_utc.ge(cutoff)] = "CACHED_TRAINING_AFTER_QUERY"
    result = checked[KEYS + CONTEXT].copy()
    result["cached_value"] = values
    result["source_fallback"] = checked[spec["fallback_column"]].fillna("").astype(str)
    result["admission"] = reasons
    return result


def attach_values(receiving, source, baseline):
    """Keep every original row; metadata incompatibility uses aged controls."""
    merged = receiving[KEYS + CONTEXT].merge(source, on=KEYS, how="left", validate="one_to_one", suffixes=("", "_modern"), indicator=True)
    reasons = merged.admission.fillna("MODERN_KEY_MISSING").astype(str)
    for column in CONTEXT:
        equal = merged[column].eq(merged[column + "_modern"]) & merged[column].notna()
        reasons.loc[merged._merge.eq("both") & ~equal] = "OFFERED_CONTEXT_MISMATCH_" + column
    accepted = reasons.eq("ACCEPTED_CACHED").to_numpy()
    output = np.asarray(baseline, float).copy()
    output[accepted] = merged.loc[accepted, "cached_value"].to_numpy(float)
    return output, reasons.to_numpy(), merged.source_fallback.fillna("").to_numpy()


def prepare_forecasts(plan, budget):
    """Select original prediction cohorts before reading modern values/labels."""
    original = read_frame(plan["inputs"]["original_evaluation"], filters=[("season", "=", 2026)])
    require(len(original) == 9485 and set(original.season) == {2026}, "old study forecast membership differs")
    original = original.loc[original.season.eq(2026) & original.primary_role].copy()
    ordinary = original.loc[original.target.ne("anytime_td") & original.target.ne("fantasy_ppr")]
    ordinary = primary_offers(ordinary.loc[ordinary[[a + "_point" for a in ["F", "FC", "M", "H"]]].notna().all(axis=1)])
    event = primary_offers(original.loc[original.target.eq("anytime_td") & original.F_probability.notna()])
    keep = UNIT + ["book_id", "team", "opponent", "position", "kickoff_utc", "source_collection_naive", "source_row_number", "line", "primary_role", "F_point", "FC_point", "M_point", "H_point", "F_probability", "F_fallback"]
    cohort = pd.concat([ordinary[keep], event[keep]], ignore_index=True)
    require(not cohort.duplicated(UNIT).any() and cohort.week.between(1, 5).all(), "fixed original market cohort differs")
    # The original football query clock is recovered from its unchanged source
    # metadata only. No stat, target, feature builder or new inference is used.
    import pyarrow.dataset as ds
    raw = ds.dataset(authenticate(plan["inputs"]["original_primitive"]), format="parquet")
    cols = KEYS + ["kickoff_utc"] + (["cutoff_utc"] if "cutoff_utc" in raw.schema.names else [])
    clocks = raw.to_table(columns=cols, filter=(ds.field("season") == 2026) & ds.field("week").isin([1, 2, 3, 4, 5])).to_pandas()
    if "cutoff_utc" not in clocks:
        clocks["cutoff_utc"] = clocks.kickoff_utc
    clocks = normalize_context(clocks)
    clocks["cutoff_utc"] = clocks.cutoff_utc.fillna(clocks.kickoff_utc)
    require(not clocks.duplicated(KEYS).any(), "ambiguous original query clocks")
    cohort = normalize_context(cohort).merge(clocks[KEYS + ["cutoff_utc"]], on=KEYS, how="left", validate="many_to_one")
    require(cohort.cutoff_utc.notna().all(), "original forecast query clock absent")
    query = normalize_context(read_frame(plan["inputs"]["annual_query"], columns=KEYS + CONTEXT + ["feature_max_source_available_utc"]))
    require(len(query) == 2999 and not query.duplicated(KEYS).any() and query.season.eq(2026).all(), "full modern annual query differs")
    source_clock = pd.to_datetime(query.feature_max_source_available_utc, utc=True, errors="raise")
    require((source_clock.isna() | source_clock.lt(query.cutoff_utc)).all(), "modern retained feature cutoff violated")
    old_parameters = document(plan["inputs"]["original_parameters"])["parameters"]
    lad_parameters = document(plan["inputs"]["lad_parameters"])
    old_lad = read_frame(plan["inputs"]["lad_forecasts"], filters=[("season", "=", 2026)])
    old_lad = old_lad.loc[old_lad.season.eq(2026)]
    old_lad = old_lad[UNIT + ["book_id", "FC_LAD_point", "H_LAD_point"]]
    cohort = cohort.merge(old_lad, on=UNIT + ["book_id"], how="left", validate="one_to_one")
    audits = []
    for target, source_spec in plan["modern_cdf"].items():
        at = cohort.index[cohort.target.eq(target)]
        part = cohort.loc[at].reset_index(drop=True)
        baseline = part.F_probability if target == "anytime_td" else part.F_point
        vector = source_vector(source_spec, query)
        values, reasons, fallback = attach_values(part, vector, baseline)
        cohort.loc[at, "MODERN_CDF_point"] = values
        cohort.loc[at, "MODERN_CDF_reason"] = reasons
        cohort.loc[at, "MODERN_CDF_source_fallback"] = fallback
        accepted = reasons == "ACCEPTED_CACHED"
        for arm in ["FC", "H"]:
            if target == "anytime_td":
                continue
            cohort.loc[at, "MODERN_" + arm + "_L2_point"] = part[arm + "_point"].to_numpy(float)
            for book in [68, 69, 79]:
                positions = np.flatnonzero(accepted & part.book_id.eq(book).to_numpy())
                if not len(positions):
                    continue
                old = next(r for r in old_parameters if r.get("target") == target and r.get("excluded_offering_book") == book)["point"]
                require(isinstance(old, dict), "original earlier-only correction unavailable on old common pool")
                x = values[positions, None] if arm == "FC" else np.column_stack([values[positions], part.M_point.to_numpy(float)[positions]])
                result = apply_ridge(old["models"][arm], x)
                if source_spec["functional"] == "count_mean":
                    result = np.maximum(0., result)
                require(np.isfinite(result).all(), "transport produced nonfinite point")
                cohort.loc[at[positions], "MODERN_" + arm + "_L2_point"] = result
                if target in YARDS:
                    record = next(r for r in lad_parameters if r["target"] == target and r["excluded_offering_book"] == book and r["arm"] == arm + "_LAD")
                    require(record["state"] == "FIT_CERTIFIED" and record["training_seasons"] == [2023], "LAD transport authority differs")
                    cohort.loc[at[positions], "MODERN_" + arm + "_LAD_point"] = apply_ridge(record["model"], x)
            if target in YARDS:
                column = "MODERN_" + arm + "_LAD_point"
                if column not in cohort:
                    cohort[column] = np.nan
                missing = at[cohort.loc[at, column].isna()]
                cohort.loc[missing, column] = cohort.loc[missing, arm + "_LAD_point"]
                require(cohort.loc[at, column].notna().all(), "old LAD fallback point missing")
        leader_spec = plan["recent_leaders"][target]
        leader = vector if leader_spec["recipe"] == "ANNUAL_CDF" else source_vector(leader_spec["source"], query)
        leader_values, leader_reasons, leader_fallback = attach_values(part, leader, baseline)
        cohort.loc[at, "RECENT_LEADER_point"] = leader_values
        cohort.loc[at, "RECENT_LEADER_reason"] = leader_reasons
        cohort.loc[at, "RECENT_LEADER_source_fallback"] = leader_fallback
        cohort.loc[at, "RECENT_LEADER_recipe"] = leader_spec["recipe"]
        if target == "anytime_td":
            for name in ["CAT_ATD", "EQUAL_ATD"]:
                vector_extra = source_vector(plan["event_controls"][name], query)
                v, why, prior = attach_values(part, vector_extra, baseline)
                cohort.loc[at, name + "_point"] = v
                cohort.loc[at, name + "_reason"] = why
                cohort.loc[at, name + "_source_fallback"] = prior
        audits.append({"target": target, "original_fixed_rows": len(part), "modern_admitted_rows": int(accepted.sum()),
                       "modern_admission_reasons": pd.Series(reasons).value_counts().to_dict(),
                       "cached_model_fallback_reasons": pd.Series(fallback).value_counts().to_dict(),
                       "recent_leader_recipe": leader_spec["recipe"], "recent_leader_reasons": pd.Series(leader_reasons).value_counts().to_dict()})
        budget.check()
    return cohort, {"state": "CACHED_2026_TRANSPORT_POINTS_READY_UNSCORED", "audits": audits,
        "original_primary_book_offers": len(original), "fixed_original_point_UNIT_rows": len(ordinary),
        "fixed_original_ATD_UNIT_rows": len(event),
        "models_loaded": 0, "fits": 0, "law_queries": 0, "new_source_acquisition": 0,
        "2025_football_lineage": "pre-existing qualified annual model lineage; no2025 market quotes, new fits, or evaluation",
        "calibration": "fixed original2023 parameters only; transport is a new exposed research procedure, not refit or calibration qualification"}


def point_metrics(frame, values):
    errors = np.asarray(values, float) - frame.actual.to_numpy(float)
    require(np.isfinite(errors).all(), "fixed cohort cannot drop an unavailable system point")
    absolute = np.abs(errors)
    threshold = 10 if frame.target.iloc[0] in YARDS else 1
    prediction = np.asarray(values, float)
    line = frame.line.to_numpy(float)
    actual = frame.actual.to_numpy(float)
    decisive = (prediction != line) & (actual != line)
    correct = decisive & (np.sign(prediction - line) == np.sign(actual - line))
    return {"rows": len(frame), "MAE": float(absolute.mean()), "MSE": float(np.mean(errors ** 2)),
            "RMSE": float(np.sqrt(np.mean(errors ** 2))), "bias": float(errors.mean()),
            "p95_absolute_error": float(np.quantile(absolute, .95, method="linear")), "maximum_absolute_error": float(absolute.max()),
            "close_threshold": threshold, "strict_close_rate": float(np.mean(absolute < threshold)),
            "inclusive_close_rate": float(np.mean(absolute <= threshold)),
            "actual_pushes": int(np.sum(actual == line)), "forecast_ties": int(np.sum(prediction == line)),
            "side_decisive_rows": int(decisive.sum()), "correct_side_rows": int(correct.sum()),
            "correct_side_all_rate": float(correct.mean()),
            "correct_side_decisive_rate": float(correct.sum() / decisive.sum()) if decisive.any() else None,
            "correct_side_and_strict_close_rate": float(np.mean(correct & (absolute < threshold))),
            "correct_side_and_inclusive_close_rate": float(np.mean(correct & (absolute <= threshold)))}


def contrast(frame, left_loss, right_loss, left, right, metric):
    """Prespecified paired full-cohort contrast; never discard infinite losses."""
    left_loss, right_loss = np.asarray(left_loss, float), np.asarray(right_loss, float)
    with np.errstate(invalid="ignore"):
        difference = left_loss - right_loss
    finite = np.isfinite(difference)
    result = {"left": left, "right": right, "metric": metric, "rows": len(frame),
              "positive_difference_favors": right,
              "mean_loss_difference": float(difference.mean()) if finite.all() else None,
              "finite_difference_rows": int(finite.sum()),
              "left_infinite_losses": int(np.isposinf(left_loss).sum()),
              "right_infinite_losses": int(np.isposinf(right_loss).sum()),
              "both_infinite_losses": int((np.isposinf(left_loss) & np.isposinf(right_loss)).sum())}
    if finite.all():
        result["paired_game"] = paired_interval(frame, difference, "game_id")
        result["paired_week"] = paired_interval(frame, difference, "week")
    else:
        result["paired_game"] = result["paired_week"] = {"state": "N_A_NONFINITE_PAIRED_LOSS_DIFFERENCES_FULL_COHORT_PRESERVED"}
    return result


def score_forecasts(plan, forecasts, budget):
    old = read_frame(plan["inputs"]["original_matched"], filters=[("season", "=", 2026)])
    labels = old[UNIT + ["book_id", "actual", "outcome_state"]]
    graded = forecasts.merge(labels, on=UNIT + ["book_id"], how="left", validate="one_to_one")
    require(len(graded) == len(forecasts), "original row membership changed in grading")
    supported = graded.loc[graded.outcome_state.eq("supported_played")]
    cells = []
    for target, part in supported.groupby("target", sort=True, observed=True):
        metrics, contrasts = [], []
        if target == "anytime_td":
            y = part.actual.to_numpy(int)
            for arm in ["F", "MODERN_CDF", "RECENT_LEADER", "CAT_ATD", "EQUAL_ATD"]:
                values = part.F_probability if arm == "F" else part[arm + "_point"]
                item = {"arm": arm, **probability_metrics(values, y)}
                item["weekly"] = [{"week": int(week), **probability_metrics(values.loc[group.index], group.actual.to_numpy(int))}
                                  for week, group in part.groupby("week", sort=True)]
                if arm != "F":
                    good = part[arm + "_reason"].eq("ACCEPTED_CACHED")
                    item["modern_admitted_only"] = probability_metrics(values.loc[good], y[good]) if good.any() else {"rows": 0}
                    item["age_fallback_rows"] = int((~good).sum())
                metrics.append(item)
            event_pairs = [("MODERN_CDF", "CAT_ATD"), ("EQUAL_ATD", "MODERN_CDF"), ("EQUAL_ATD", "CAT_ATD")]
            for left, right in event_pairs:
                a, b = part[left + "_point"].to_numpy(float), part[right + "_point"].to_numpy(float)
                contrasts.append(contrast(part, (a - y) ** 2, (b - y) ** 2, left, right, "Brier"))
                with np.errstate(divide="ignore"):
                    a_loss = np.where(y == 1, -np.log(a), -np.log1p(-a))
                    b_loss = np.where(y == 1, -np.log(b), -np.log1p(-b))
                contrasts.append(contrast(part, a_loss, b_loss, left, right, "log_loss"))
        else:
            arms = POINT_ARMS + (["FC_LAD", "H_LAD", "MODERN_FC_LAD", "MODERN_H_LAD"] if target in YARDS else [])
            for arm in arms:
                values = part.line if arm == "OFFERED_LINE_HEURISTIC" else part[arm + "_point"]
                item = {"arm": arm, **point_metrics(part, values)}
                item["weekly"] = [{"week": int(week), **point_metrics(group, values.loc[group.index])}
                                  for week, group in part.groupby("week", sort=True)]
                base_errors = part.F_point.to_numpy(float) - part.actual.to_numpy(float)
                errors = values.to_numpy(float) - part.actual.to_numpy(float)
                difference = np.abs(errors) - np.abs(base_errors) if target in YARDS else errors ** 2 - base_errors ** 2
                item["paired_vs_aged_F_game"] = paired_interval(part, difference, "game_id")
                if arm.startswith("MODERN") or arm == "RECENT_LEADER":
                    reason = "RECENT_LEADER_reason" if arm == "RECENT_LEADER" else "MODERN_CDF_reason"
                    good = part[reason].eq("ACCEPTED_CACHED")
                    item.update(age_fallback_rows=int((~good).sum()), admission_reasons=part[reason].value_counts().to_dict(),
                        modern_admitted_only=point_metrics(part.loc[good], values.loc[good]) if good.any() else {"rows": 0})
                metrics.append(item)
            pairs = [("MODERN_H_L2", "MODERN_FC_L2"), ("MODERN_H_L2", "MODERN_CDF"),
                     ("MODERN_H_L2", "M"), ("MODERN_H_L2", "RECENT_LEADER")]
            if target in YARDS:
                pairs += [("MODERN_H_LAD", "MODERN_FC_LAD"), ("MODERN_H_LAD", "MODERN_H_L2"), ("MODERN_H_LAD", "M")]
            for left, right in pairs:
                a = part[left + "_point"].to_numpy(float) - part.actual.to_numpy(float)
                b = part[right + "_point"].to_numpy(float) - part.actual.to_numpy(float)
                left_loss, right_loss = (np.abs(a), np.abs(b)) if target in YARDS else (a ** 2, b ** 2)
                contrasts.append(contrast(part, left_loss, right_loss, left, right, "MAE" if target in YARDS else "MSE"))
        cells.append({"season": 2026, "target": target, "rows": len(part), "games": int(part.game_id.nunique()),
                      "weeks": int(part.week.nunique()), "primary_loss": "Brier" if target == "anytime_td" else "MAE" if target in YARDS else "MSE",
                      "metrics": metrics, "prespecified_contrasts": contrasts})
        budget.check()
    return {"state": "CACHED_CONTEMPORARY_2026_COMPARISON_COMPLETE", "version": VERSION, "cells": cells,
        "timing": "timing-unverified exposed current-vintage reconstruction; original7day assumption; no historical SITE or live claim",
        "ordinary_prop_probabilities": "UNAVAILABLE_WITHOUT_NEW_LAW_QUERIES; point summaries are insufficient",
        "ATD_market_fair_probability": "UNAVAILABLE_NO_AUTHENTIC_NO_SIDE",
        "adjusted_point_semantics": "Empirical frozen-parameter transports, not CDF mean/median/probability claims",
        "multiplicity": "All52 fixed point contrasts and6 ATD proper-score contrasts retained; nominal exposed intervals, no independent scientific winner selection",
        "recent_leaders": {k: v["recipe"] for k, v in plan["recent_leaders"].items()}}, graded
