"""Pure descriptive groups of one frozen, scored target-method population.

The caller authenticates the parent scored-file manifest and streams completed
annual cells. Player groups are private; this module never opens files or adds
predictions, comparisons, uncertainty intervals or model selection.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from .cdf_engine import KEYS, numeric, valid_support
from .cdf_evaluation import summarize as cdf_summary
from .models import COUNT_TARGETS, TARGETS
from .role_boosting_campaign import summary as point_summary

VERSION = "source-matched-frozen-subgroups-v1"
REGISTRATION_SHA256 = "f07cb07b9180129594ebdc0bba72386ceb777757756900ae4b4004924f6318bc"
YEARS = (2022, 2023, 2024)
METHODS = ("leaf_cdf", "median_hgb", "count_A", "role_B", "recent", "pooled")
DIMENSIONS = ("player_id", "team", "opponent", "position", "history_state", "fallback", "outcome_state")
LAW_FIELDS = ("p10", "p90", "variance", "crps", "log_score", "cdf_actual_below", "cdf_actual")
NUMERIC_FIELDS = ("point", "probability", "mean", "median", "actual", *LAW_FIELDS)
EXPOSURE = "Exposed 2022-2024 historical reconstruction; descriptive groups, no independent confirmation or promotion"


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return {"state": "positive_infinity" if value > 0 else "negative_infinity"}
        return float(value)
    return value


def _validate(rows, category):
    if not isinstance(category, dict) or category.get("target") not in TARGETS or category.get("target") == "fantasy_ppr":
        raise ValueError("supported fixed target required; exact PPR stays blocked")
    target = category["target"]
    support = "bernoulli" if target == "anytime_td" else "count" if target in COUNT_TARGETS else "signed_integer"
    roles = category.get("primary_roles")
    if category.get("state") != "READY" or category.get("support") != support or not isinstance(roles, list) or not roles or len(set(roles)) != len(roles) or not all(isinstance(r, str) and r for r in roles):
        raise ValueError("fixed ready category support and primary roles required")
    if not isinstance(rows, pd.DataFrame) or not rows.columns.is_unique or rows.empty:
        raise ValueError("one nonempty completed target-method dataframe required")
    required = {*KEYS, *DIMENSIONS, *NUMERIC_FIELDS, "year", "target", "method", "participation_state", "primary_role", "cutoff_utc", "kickoff_utc"}
    if required - set(rows):
        raise ValueError("missing normalized scored fields: " + repr(sorted(required - set(rows))))
    if not rows.target.eq(target).all() or rows.method.nunique(dropna=False) != 1 or not rows.method.isin(METHODS).all():
        raise ValueError("exactly one registered target-method required")
    if rows[KEYS].isna().any(axis=None) or rows.duplicated(KEYS).any():
        raise ValueError("unique nonnull player-game KEYS required")
    for field in ("game_id", "player_id"):
        if not rows[field].map(lambda v: isinstance(v, str) and bool(v)).all():
            raise ValueError("text identity required: " + field)
    for field in ("season", "year", "week"):
        values = numeric(rows, field)
        if not is_numeric_dtype(rows[field].dtype) or not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
            raise ValueError("integer season/year/week required")
    if not rows.year.eq(rows.season).all() or not rows.season.isin(YEARS).all() or not rows.week.between(1, 18).all():
        raise ValueError("only exposed 2022-2024 regular-season rows permitted")
    if "season_type" in rows and not rows.season_type.eq("REG").all():
        raise ValueError("only source-matched regular-season rows permitted")
    if not is_bool_dtype(rows.primary_role.dtype) or rows.primary_role.isna().any() or not rows.primary_role.eq(rows.position.isin(roles)).all():
        raise ValueError("frozen boolean primary-role mask differs")
    if not rows.participation_state.isin(("played", "DNP", "unknown")).all():
        raise ValueError("qualified participation required")
    for field in DIMENSIONS[1:]:
        if not rows[field].map(lambda v: pd.isna(v) or isinstance(v, str)).all():
            raise ValueError("group labels must be text or missing: " + field)
    for field in NUMERIC_FIELDS:
        if not is_numeric_dtype(rows[field].dtype):
            raise ValueError("numeric scored field required: " + field)
        values = numeric(rows, field)
        if field != "log_score" and np.isinf(values).any():
            raise ValueError("infinite point/outcome/law field forbidden: " + field)
    logs = numeric(rows, "log_score")
    if np.isneginf(logs).any() or (logs < 0).any():
        raise ValueError("log score must be missing, nonnegative or positive infinity")
    point, probability = numeric(rows, "point"), numeric(rows, "probability")
    if support == "bernoulli":
        if (np.isfinite(point) & ((point < 0) | (point > 1))).any() or not np.allclose(point, probability, rtol=0, atol=0, equal_nan=True):
            raise ValueError("genuine unchanged binary probabilities required")
    elif np.isfinite(probability).any() or support == "count" and (point < 0).any():
        raise ValueError("numeric point support/probability mismatch")
    if rows.method.iloc[0] == "leaf_cdf":
        expected = numeric(rows, "mean" if support == "bernoulli" else "median")
        if not np.allclose(point, expected, rtol=0, atol=0, equal_nan=True):
            raise ValueError("frozen CDF point semantics differ")
        scored = np.isfinite(numeric(rows, "crps"))
        below, at = numeric(rows, "cdf_actual_below"), numeric(rows, "cdf_actual")
        if (scored & (~np.isfinite(below) | ~np.isfinite(at) | (below < 0) | (at > 1) | (below > at))).any():
            raise ValueError("invalid frozen CDF bracket")
        if (numeric(rows, "crps") < 0).any() or (numeric(rows, "variance") < 0).any() or (numeric(rows, "p10") > numeric(rows, "p90")).any():
            raise ValueError("invalid frozen CDF loss/variance/quantiles")
        for field in ("median", "p10", "p90"):
            values = numeric(rows, field)
            if (np.isfinite(values) & ~valid_support(values, support)).any():
                raise ValueError("frozen quantile support differs")
    result = rows.copy(deep=False)
    for field in ("cutoff_utc", "kickoff_utc"):
        result[field] = pd.to_datetime(result[field], utc=True, errors="raise")
        if result[field].isna().any():
            raise ValueError("nonnull qualified clocks required")
    if result.cutoff_utc.gt(result.kickoff_utc).any():
        raise ValueError("cutoff follows kickoff")
    return result


def _summary(rows, category, method):
    # The frozen evaluators retain their point, support, binary and PIT rules.
    out = point_summary(rows, category)
    actual = numeric(rows, "actual")
    observed = rows.participation_state.eq("played").to_numpy() & valid_support(actual, category["support"])
    out.update(supported_played_outcomes=int(observed.sum()),
        supported_played_zero_rows=int((observed & (actual == 0)).sum()),
        supported_played_negative_rows=int((observed & (actual < 0)).sum()),
        missing_actual_rows=int((~np.isfinite(actual)).sum()),
        played_missing_actual_rows=int((rows.participation_state.eq("played").to_numpy() & ~np.isfinite(actual)).sum()),
        played_invalid_support_rows=int((rows.participation_state.eq("played").to_numpy() & np.isfinite(actual) & ~observed).sum()),
        unknown_participation_rows=int(rows.participation_state.eq("unknown").sum()),
        known_DNP_rows=int(rows.participation_state.eq("DNP").sum()),
        fallback_rows=int(rows.fallback.fillna("").ne("").sum()),
        offered_players=int(rows.player_id.nunique()), offered_games=int(rows.game_id.nunique()),
        offered_season_weeks=len(rows[["season", "week"]].drop_duplicates()))
    if method == "leaf_cdf":
        out["cdf_law"] = cdf_summary(rows, category["support"])
    return out


def build_frozen_subgroups(scored_rows: pd.DataFrame, category: dict) -> tuple[dict, dict]:
    """Return (public nonplayer aggregates, PRIVATE player aggregates).

    Input is one completed target-method's pooled 2022-2024 scored rows; missing
    annual cells are not synthesized. Caller retains all parent slot statuses,
    binds exact scored-file hashes before use, and owns private quota writes.
    No annual averages, cross-products, contrasts, intervals or rankings occur.
    """
    rows = _validate(scored_rows, category)
    target, method = category["target"], rows.method.iloc[0]
    header = {"version": VERSION, "registration_sha256": REGISTRATION_SHA256,
        "target": target, "method": method, "support": category["support"],
        "unit": "probability" if category["support"] == "bernoulli" else "yards" if target.endswith("_yd") else "events",
        "included_years": sorted(int(v) for v in rows.season.unique()),
        "absent_years": sorted(set(YEARS) - set(rows.season.unique())),
        "exposure": EXPOSURE, "uncertainty": "No subgroup intervals; parent category game/week intervals remain the reference",
        "slot_policy": "Completed annual cells only; parent preserves failed, unrun and blocked exact PPR slots"}
    public = {**header, "privacy": "Nonplayer aggregates and player coverage counts only", "populations": {}}
    private = {**header, "privacy": "PRIVATE_PLAYER_GROUPS_DO_NOT_PUBLISH", "populations": {}}
    cached_groups = {}
    for population, part in (("all_offered", rows), ("primary_roles", rows.loc[rows.primary_role])):
        aggregate = _summary(part, category, method)
        public_groups, player_groups = [], []
        for dimension in DIMENSIONS:
            for value, group in part.groupby(dimension, dropna=False, observed=True, sort=True):
                # A group wholly in the primary population has identical rows
                # in both passes. Reuse its exact evaluator output, not a second
                # calculation. Mixed-role groups still get a separate summary.
                key = (dimension, None if pd.isna(value) else value)
                cached = cached_groups.get(key)
                summary = cached[1] if cached and cached[0] == len(group) else _summary(group, category, method)
                if population == "all_offered":
                    cached_groups[key] = (len(group), summary)
                item = {"dimension": dimension, "value": None if pd.isna(value) else value,
                    "missing_group_value": bool(pd.isna(value)), "summary": summary}
                (player_groups if dimension == "player_id" else public_groups).append(item)
        coverage = {"offered_player_groups": len(player_groups),
            "scored_player_groups": sum(g["summary"]["scored_rows"] > 0 for g in player_groups),
            "unscored_player_groups": sum(g["summary"]["scored_rows"] == 0 for g in player_groups),
            "offered_rows": len(part), "scored_rows": aggregate["scored_rows"]}
        public["populations"][population] = {"summary": aggregate, "groups": public_groups, "player_group_coverage": coverage}
        private["populations"][population] = {"groups": player_groups, "coverage": coverage}
    return _json_safe(public), _json_safe(private)
