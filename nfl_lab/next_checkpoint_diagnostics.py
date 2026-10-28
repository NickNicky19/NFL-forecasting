"""Evaluation-only tails and side denominators on frozen LAD cohort rows."""
from __future__ import annotations

import numpy as np

from .historical_market_comparison import UNIT, require

VERSION = "next-nfl-checkpoint-lad-diagnostics-v1-20261028"
ARMS = ["F", "FC", "M", "H", "OFFERED_LINE_HEURISTIC", "FC_LAD", "H_LAD"]


def summarize_cell(frame, arm):
    values = frame.line.to_numpy(float) if arm == "OFFERED_LINE_HEURISTIC" else frame[arm + "_point"].to_numpy(float)
    actual, line = frame.actual.to_numpy(float), frame.line.to_numpy(float)
    require(np.isfinite(values).all() and np.isfinite(actual).all() and np.isfinite(line).all(), "original frozen diagnostic cohort must stay complete")
    absolute = np.abs(values - actual)
    push, tie = actual == line, values == line
    decisive = ~push & ~tie
    correct = decisive & (np.sign(values - line) == np.sign(actual - line))
    return {"arm": arm, "rows": len(frame), "absolute_error_p90_linear": float(np.quantile(absolute, .90, method="linear")),
        "absolute_error_p95_linear": float(np.quantile(absolute, .95, method="linear")), "maximum_absolute_error": float(absolute.max()),
        "actual_pushes": int(push.sum()), "forecast_ties": int(tie.sum()), "both_push_and_tie": int((push & tie).sum()),
        "actual_decisive_rows": int((~push).sum()), "joint_decisive_rows": int(decisive.sum()),
        "correct_side_rows": int(correct.sum()), "wrong_side_rows": int((decisive & ~correct).sum()),
        "correct_side_all_rate": float(correct.mean()),
        "correct_side_decisive_rate": float(correct.sum() / decisive.sum()) if decisive.any() else None,
        "strict_close_rate": float((absolute < 10).mean()), "inclusive_close_rate": float((absolute <= 10).mean()),
        "correct_side_and_strict_close_rate": float((correct & (absolute < 10)).mean()),
        "correct_side_and_inclusive_close_rate": float((correct & (absolute <= 10)).mean())}


def evaluate(frame, expected_cells):
    require(len(frame) == sum(expected_cells.values()) and not frame.duplicated(UNIT).any(), "exact original fixed diagnostic row set required")
    require(frame.outcome_state.eq("supported_played").all() and frame.primary_role.all(), "diagnostic population cannot add unknown/DNP/secondary rows")
    records = []
    for (year, target), group in frame.groupby(["season", "target"], observed=True, sort=True):
        require(len(group) == expected_cells[str(year) + "/" + target], "original cell size differs")
        for arm in ARMS:
            records.append({"season": int(year), "target": target, **summarize_cell(group, arm)})
    require(len(records) == 56, "all eight cells and seven fixed arms required")
    return {"version": VERSION, "state": "FROZEN_LAD_TAIL_SIDE_DIAGNOSTICS_COMPLETE", "records": records,
        "row_count": len(frame), "record_count": len(records), "quantile_convention": "numpy quantile method=linear (type7)",
        "side_definition": "strict correct side excludes actual pushes and prediction ties; all-rate denominator is full cell, decisive-rate denominator excludes both; null when denominator0",
        "fits": 0, "new_forecasts": 0, "model_loads": 0, "law_queries": 0, "HTTP": 0,
        "claim": "Descriptive diagnostics on already exposed frozen rows; no selection, live, payout or scientific qualification claim"}
