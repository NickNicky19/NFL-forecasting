"""A-owned preparation for PROFILE-INCREMENT-TO-RELEASE-01 v2.

Pure transformations only: no collection, storage, fitting, model loading,
prediction or grading. Callers must bind the accepted source and registration.
The defense component maps onto C's rate-field contract; it is not a competing
common schema. Historical profiles retain the accepted availability policy.
"""
from __future__ import annotations

from copy import deepcopy
import math

import numpy as np
import pandas as pd

from .abc_player_rushing_context_v1 import eligible
from .player_context_rush_efficiency_v1 import (
    EFFICIENCY_FEATURES, GROUPS, LEVELS, LEVEL_INDEX, SHRINK, total,
)

VERSION = "A::PROFILE-INCREMENT-TO-RELEASE-01-v2-preparation-v1"
TEAMS = tuple("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split())
ALIASES = {"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"}
COMMON_PROFILE_SCHEMA = {
    "repository": "NickNicky19/NFL-forecasting-NGS-C",
    "commit": "06da9bb77c6122d870e18067c8dbdf34813fc4cb",
    "path": "reports/player-context-matchup-01/completion-decision-v1/profiles/SCHEMA.json",
    "git_blob_sha": "faa1e8b80b4f03272e72e062f4ca542cd62765d0",
    "schema": "C-ASOF-RECEIVING-PROFILE-v1",
    "defense_mapping": "A_COMPONENT_PENDING_C_COMMON_DEFENSE_SCHEMA_ADMISSION",
}

# Preserve original source feature order inside each block. Neither age nor
# availability timestamps are silently introduced as new model predictors.
SUPPORT = tuple(x for x in EFFICIENCY_FEATURES
                if x.rsplit("_", 1)[-1] in {"games", "carries", "supported"})
INTERACTIONS = tuple(x for x in EFFICIENCY_FEATURES if x.startswith("f_pce_match_"))
DEFENSE = tuple(x for x in EFFICIENCY_FEATURES
                if x.startswith("f_pce_opp_") and x not in SUPPORT)
PLAYER_OFFENSE = tuple(x for x in EFFICIENCY_FEATURES
                       if x not in SUPPORT + DEFENSE + INTERACTIONS)


def arm_category(category, arm, *, modeled_roles=None):
    """Return a fitted-input contract; this function does not fit anything.

    Changing modeled_roles creates a different baseline and forbids reuse of a
    saved broad-role R0 as an identical-fit counterfactual. Existing fallback
    priors remain the selected family's contract unless separately registered.
    """
    blocks = {"R0": (), "R1": SUPPORT, "R2": SUPPORT + PLAYER_OFFENSE,
              "R3": SUPPORT + PLAYER_OFFENSE + DEFENSE,
              "R4": tuple(EFFICIENCY_FEATURES)}
    if arm not in blocks:
        raise ValueError("unregistered arm")
    result = deepcopy(category)
    if result.get("target", "rush_yd") != "rush_yd":
        raise ValueError("this package is restricted to rush_yd")
    result["target"] = "rush_yd"
    base = list(result["panels"]["base"])
    if len(base) != len(set(base)) or set(base) & set(EFFICIENCY_FEATURES):
        raise ValueError("baseline columns are duplicated or already augmented")
    columns = base + list(blocks[arm])
    result["panels"] = {"base": list(columns), "context": list(columns)}
    if modeled_roles is not None:
        result["modeled_roles"] = list(modeled_roles)
    return result


def verify_partition():
    """Structural invariants, not an NFL evidence or accuracy observation."""
    blocks = SUPPORT + PLAYER_OFFENSE + DEFENSE + INTERACTIONS
    if tuple(map(len, (SUPPORT, PLAYER_OFFENSE, DEFENSE, INTERACTIONS))) != (9, 89, 36, 8):
        raise ValueError("conditional feature contract changed")
    if len(blocks) != len(set(blocks)) or set(blocks) != set(EFFICIENCY_FEATURES):
        raise ValueError("conditional feature partition is not exhaustive/disjoint")
    return {"support": 9, "player_offense_values": 89,
            "defense_values": 36, "interactions": 8}


def rb_training_population(train):
    """Role filter before the selected CDF family estimates *any* parameters.

    Filtering only modeled_roles inside LeafCDFModel.fit would still construct
    all-position priors. This explicit population control also gives the RB-only
    baseline, support arm and value arms identical prior-training populations.
    Temporal and supported-label admission remain the frozen caller's contract.
    """
    if "position" not in train:
        raise ValueError("historical role is required for RB training admission")
    return train.loc[train.position.eq("RB")].copy()


def _clock(value):
    clock = pd.Timestamp(value)
    if pd.isna(clock) or clock.tzinfo is None:
        raise ValueError("explicit timezone-aware clock required")
    return clock.tz_convert("UTC")


def priority_cohorts(board, *, minimum_expected_carries=5., top_k=20):
    """Annotate a full, externally admitted RB board without deleting anyone.

    Inputs must include actual pregame universe qualification, source cutoff,
    frozen reference workload identity/mean, offer qualification and explicit
    replacement support. No outcome/participation column is consulted. Top20
    is per same-kickoff rolling batch, not an executable Thursday weekly list.
    Unknown/stale reference means cannot enter the focus ranking. This rule is
    a separately evaluated scoped procedure, never inherited qualification.
    """
    required = {"season", "week", "game_id", "player_id", "position",
                "kickoff_utc", "cutoff_utc", "universe_qualified",
                "offer_qualified", "reference_expected_carries",
                "reference_available_utc", "reference_procedure_id",
                "replacement_role_qualified", "replacement_source_id"}
    if required - set(board):
        raise ValueError("missing cohort fields: " + ",".join(sorted(required - set(board))))
    if not board.position.eq("RB").all():
        raise ValueError("RB-only profile package; retain other roles in their owning board")
    key = ["season", "week", "game_id", "player_id"]
    if board.duplicated(key).any():
        raise ValueError("cohort board must be unique player-game, not repeated books/lines")
    result = board.copy()
    for col in ("universe_qualified", "offer_qualified", "replacement_role_qualified"):
        if not result[col].map(lambda x: isinstance(x, (bool, np.bool_))).all():
            raise ValueError("explicit boolean required: " + col)
    result["focus_reasons"] = [[] for _ in range(len(result))]
    result["top20_workload"] = False
    result["reference_eligible"] = False
    for at, row in result.iterrows():
        cut, kickoff = _clock(row.cutoff_utc), _clock(row.kickoff_utc)
        if cut >= kickoff:
            raise ValueError("target is not future at its declared cutoff")
        mean = pd.to_numeric(pd.Series([row.reference_expected_carries]), errors="coerce").iloc[0]
        if pd.notna(row.reference_available_utc):
            available = _clock(row.reference_available_utc)
            valid_reference = (available <= cut and math.isfinite(mean) and mean >= 0
                               and pd.notna(row.reference_procedure_id)
                               and bool(str(row.reference_procedure_id).strip()))
        else:
            valid_reference = False
        result.at[at, "reference_eligible"] = bool(valid_reference)
        reasons = []
        if row.universe_qualified and row.offer_qualified:
            reasons.append("QUALIFIED_OFFER")
        if row.universe_qualified and valid_reference and mean >= minimum_expected_carries:
            reasons.append("UNCHANGED_REFERENCE_EXPECTED_CARRIES_AT_LEAST_5")
        if row.universe_qualified and row.replacement_role_qualified:
            if pd.isna(row.replacement_source_id) or not str(row.replacement_source_id).strip():
                raise ValueError("replacement role needs its actual source identity")
            reasons.append("SOURCE_SUPPORTED_REPLACEMENT")
        result.at[at, "focus_reasons"] = reasons
    result["detailed_priority"] = result.focus_reasons.map(bool)
    result["cohort_state"] = np.where(result.universe_qualified,
        "PREGAME_UNIVERSE_ADMITTED", "RECONSTRUCTED_OR_UNQUALIFIED_UNIVERSE_BASIC_ONLY")
    for _, group in result.groupby(["season", "week", "kickoff_utc", "cutoff_utc"], sort=True):
        pool = group.loc[group.universe_qualified & group.reference_eligible].copy()
        pool["_mean"] = pd.to_numeric(pool.reference_expected_carries)
        pool = pool.sort_values(["_mean", "player_id", "game_id"],
                                ascending=[False, True, True], kind="stable")
        result.loc[pool.head(top_k).index, "top20_workload"] = True
    result["top20_schedule"] = "ROLLING_SAME_KICKOFF_AND_CUTOFF_BATCH_NOT_FIXED_WEEKLY_LIST"
    return result


def current_query_adapter(context, queries, *, execution_utc, source_observed_field="query_source_observed_utc"):
    """Profile qualified future queries without requiring their own outcomes.

    The existing audited base-feature builder supplies the original30 fields.
    This adapter adds the already registered conditional block and validates
    current role/event/source admission. It does not authenticate a historical
    source vintage, predict a starter or turn a prior-week roster into current
    qualification. No fitted model, target statistics or outcome clock is read.
    """
    execution = _clock(execution_utc)
    required = {"player_id", "game_id", "team", "opponent", "position",
        "cutoff_utc", "kickoff_utc", "current_role_qualified", "event_team_qualified",
        source_observed_field, "query_source_id", "feature_max_source_available_utc"}
    if required - set(queries):
        raise ValueError("missing current-query admission fields: " + ",".join(sorted(required-set(queries))))
    if not queries.position.eq("RB").all():
        raise ValueError("A current-query adapter is RB-only")
    if queries.duplicated(["game_id", "player_id"]).any():
        raise ValueError("duplicate current player-game query")
    for row in queries.to_dict("records"):
        cutoff, kickoff, observed = (_clock(row[k]) for k in ("cutoff_utc", "kickoff_utc", source_observed_field))
        if not observed <= cutoff <= execution < kickoff:
            raise ValueError("source receipt/cutoff/execution/future event order does not qualify")
        for field in ("current_role_qualified", "event_team_qualified"):
            if not isinstance(row[field], (bool, np.bool_)) or not row[field]:
                raise ValueError("qualified current role and historical event-team source required")
        if pd.isna(row["query_source_id"]) or not str(row["query_source_id"]).strip():
            raise ValueError("actual current source binding required")
    clean = queries.copy()
    # Outcome columns are intentionally omitted. Their absence is valid for a
    # future query, and their supplied values cannot affect this transformation.
    clean.drop(columns=[x for x in ("rush_yd", "rush_att", "actual", "outcome_available_utc", "participation_state") if x in clean], inplace=True)
    transformed, profiles = context.augment(clean, rich=True)
    return transformed, profiles, dict(state="CURRENT_QUERY_PROFILE_AVAILABLE",
        rows=len(clean), execution_UTC=execution.isoformat(), model_inference=0,
        source_qualification="EXPLICIT_CURRENT_SOURCE_ROLE_EVENT_ADMISSION",
        forecast_qualification="NOT_ESTABLISHED_BY_PROFILE_ALONE")


def prepare_defense_frames(context, frames):
    """Index the same admitted frames once for many historical cutoffs."""
    source = {(r["game"], r["team"]): r for r in context.accepted.source_games}
    projected = {}
    for frame in frames:
        f = frame.copy()
        for col in ("posteam", "defteam"):
            f[col] = f[col].replace(ALIASES)
        for (game, team), group in f.groupby(["game_id", "posteam"], sort=False):
            key = str(game), str(team)
            if key in source:
                if key in projected:
                    raise ValueError("duplicate admitted source game-team across frames")
                projected[key] = group
    if set(source) != set(projected):
        raise ValueError("accepted source manifest and raw frame membership differ")
    return projected


def defense_components(context, frames, cutoff, *, window=8, source_bindings=None, projected=None):
    """Build all32 basic as-of rushing-defense records from admitted raw plays.

    context is an already constructed EfficiencyContext. Passing the same raw
    frames is intentional: it permits signed-yard quantiles/dispersion and
    field position without inventing those from the cached aggregate features.
    No extra source or changed admission policy is introduced here. New raw
    descriptive fields are not automatically added to fitted model inputs.
    """
    cut = _clock(cutoff)
    if window not in (4, 8, 16):
        raise ValueError("undeclared appearance lookback")
    source = {(r["game"], r["team"]): r for r in context.accepted.source_games}
    if projected is None:
        projected = prepare_defense_frames(context, frames)
    elif set(source) != set(projected):
        raise ValueError("cached same-source frame membership changed")
    output = []
    for defense in TEAMS:
        records = eligible(context.defenses.get(defense, []), cut, window)
        chunks = []
        for r in records:
            key = r["game"], r["team"]
            if key not in projected:
                raise ValueError("accepted defense source bytes not supplied")
            g = projected[key]
            a = g.loc[g.rush_attempt.eq(1) & g.two_point_attempt.eq(0)].copy()
            if len(a) != r["attempts"]:
                raise ValueError("credited attempts changed after source admission")
            if not a.defteam.eq(defense).all():
                raise ValueError("historical defense identity changed")
            role = {p: v["role"] for p, v in source[key]["players"].items()}
            a["_role"] = a.rusher_player_id.astype(str).map(role).fillna("UNKNOWN")
            a["_game"] = r["game"]
            chunks.append(a)
        a = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        clock = max((r["available"] for r in records), default=pd.NaT)
        latest_game = max((r["kickoff"] for r in records), default=pd.NaT)
        profile = {"component_schema": VERSION, "component": "rushing_defense",
            "common_schema_binding": COMMON_PROFILE_SCHEMA, "team": defense,
            "information_cutoff_UTC": cut.isoformat(), "lookback_games": window,
            "eligible_games": len(records), "source_bindings": source_bindings or {},
            "latest_admitted_game_UTC": latest_game.isoformat() if pd.notna(latest_game) else None,
            "latest_source_available_UTC": clock.isoformat() if pd.notna(clock) else None,
            "source_age_days": (cut - clock).total_seconds() / 86400 if pd.notna(clock) else None,
            "state": "HISTORICAL_PROFILE_AVAILABLE" if records else "ABSENT_HISTORY",
            "availability_tier": "INHERITED_ACCEPTED_CONTEXT_POLICY_NOT_AUTHENTICATED_BY_THIS_ADAPTER",
            "descriptive_cells": [], "conditional_adjustment": []}
        if len(a):
            y = pd.to_numeric(a.rushing_yards, errors="coerce").to_numpy(float)
            if not np.isfinite(y).all():
                raise ValueError("explicit missing signed yards after accepted source")
            a["direction"] = a.run_location.fillna("UNKNOWN")
            a["gap"] = a.run_gap.fillna("UNKNOWN")
            a["down_bin"] = a.down.map(lambda x: str(int(x)) if pd.notna(x) and x in (1, 2, 3, 4) else "UNKNOWN")
            a["distance"] = a.ydstogo.map(lambda x: "UNKNOWN" if pd.isna(x) else "short" if x <= 2 else "medium" if x <= 6 else "long")
            a["field"] = a.yardline_100.map(lambda x: "UNKNOWN" if pd.isna(x) else "redzone" if x <= 20 else "backedup" if x >= 80 else "middle")
            a["rush_kind"] = np.select([a.qb_kneel.eq(1), a.qb_scramble.eq(1), a._role.eq("QB"), a._role.eq("RB"), a._role.isin(["FB", "WR", "TE"])],
                ["QB_KNEEL", "QB_SCRAMBLE", "QB_OTHER_NOT_DESIGNED_IDENTIFIED", "RB", "OTHER_SKILL"], default="UNKNOWN_ROLE")
            groups = [("ALL", "ALL", a)]
            for column in ("direction", "gap", "down_bin", "distance", "field", "rush_kind"):
                groups += [(column, str(k), v) for k, v in a.groupby(column, sort=True)]
            for group, value, part in groups:
                yy = pd.to_numeric(part.rushing_yards).to_numpy(float)
                epa = pd.to_numeric(part.epa, errors="coerce").to_numpy(float)
                fd = pd.to_numeric(part.first_down_rush, errors="coerce").to_numpy(float)
                if not np.isfinite(epa).all() or not np.isin(fd, [0, 1]).all():
                    raise ValueError("missing/unqualified success denominator")
                profile["descriptive_cells"].append({"context_group": group, "context": value,
                    "attempts": len(part), "eligible_games": int(part._game.nunique()),
                    "signed_yards": float(yy.sum()), "mean_signed_yards": float(yy.mean()),
                    "median_signed_yards": float(np.median(yy)), "variance_population": float(yy.var()),
                    "p10": float(np.quantile(yy, .1)), "p90": float(np.quantile(yy, .9)),
                    "nonpositive_count": int((yy <= 0).sum()), "explosive10_count": int((yy >= 10).sum()),
                    "epa_positive_count": int((epa > 0).sum()), "first_down_count": int(fd.sum()),
                    "success_definition": "EPA>0; first_down separately credited first_down_rush",
                    "denominator": "OFFICIALLY_CREDITED_NON_2PT_RUSH_ATTEMPTS",
                    "opponent_quality": "RAW_DESCRIPTIVE_NOT_CAUSAL_DEFENSIVE_TALENT",
                    "uncertainty": "DESCRIPTIVE_SUPPORT_ONLY_NOT_FORECAST_PROBABILITY"})
        main, residual = total(records), total(records, "residual")
        for i, (group, value) in enumerate(LEVELS):
            n = float(main[i, 0])
            for j, metric in ((1, "signed_yards"), (2, "epa_positive"), (3, "first_down")):
                numerator = float(residual[i, j])
                profile["conditional_adjustment"].append({
                    "definition": f"{metric} residual against offense's earlier same-context shrunk expectation",
                    "context_group": group, "context": value, "numerator": numerator,
                    "denominator": n, "raw_estimate": numerator / n if n else None,
                    "shrunk_estimate": numerator / (n + SHRINK["defense"]),
                    "prior": 0., "prior_strength_carries": SHRINK["defense"],
                    "state": "ABSENT_HISTORY" if not records else "UNDEFINED_DENOMINATOR" if not n else "KNOWN_ZERO" if numerator == 0 else "OBSERVED",
                    "eligible_games": len(records), "uncertainty": "SUPPORT_ONLY_NOT_CAUSAL_IDENTIFICATION"})
        output.append(profile)
    return output
