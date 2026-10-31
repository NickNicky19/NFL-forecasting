"""Source-only all-seven-week historical query/feature preparation.

No action occurs on import. Root must authenticate sources, pin these helpers,
register finite resources and authorize invocation in its own sealed runner.
This module does not load models, labels, offers or fitted forecasts and writes
nothing. It never creates an operational source manifest or pregame receipt.
"""
from __future__ import annotations

VERSION = "matched12-roster-historical-preparation-v1"
KEYS = ("season", "week", "game_id", "player_id")
WEEKS = tuple(range(1, 8))
EVIDENCE = "CURRENT_VINTAGE_TIMING_UNVERIFIED_HISTORICAL_RECONSTRUCTION"


def _authorize(authority):
    if not isinstance(authority, dict) or authority.get("integrator") != "/root" or authority.get("numeric_preparation_authorized") is not True or authority.get("adapter_version") != VERSION:
        raise ValueError("root's separately sealed finite numerical-preparation authority required")


def roster_queries(roster, schedule, *, query_builder, normalize_team, authority,
                   season=2026, weeks=WEEKS, maximum_rows_per_week=1000):
    """All eligible weekly roster rows, including all scheduled games.

    A temporary enumeration cutoff precedes every game. It is not an historical
    issue timestamp. Returned cutoffs name the declared reconstructed-kickoff
    information horizon, matching the old W1-6 benchmark. Historical roster
    publication remains unknown; neither roster status nor positive statistics
    are used to manufacture participation or select the query population.
    """
    _authorize(authority)
    import pandas as pd
    if season != 2026 or tuple(weeks) != WEEKS or maximum_rows_per_week != 1000:
        raise ValueError("this bounded panel is exactly 2026 REG Weeks1-7")
    roster_columns = ["season", "week", "game_type", "team", "gsis_id", "position", "status", "full_name", "sleeper_id"]
    schedule_columns = ["game_id", "season", "week", "game_type", "gameday", "gametime", "away_team", "home_team"]
    if not set(roster_columns) <= set(roster) or not set(schedule_columns) <= set(schedule):
        raise ValueError("existing roster/schedule contract required")
    # Project metadata before any optional column can enter this procedure.
    roster = roster.loc[:, roster_columns].copy()
    schedule = schedule.loc[:, schedule_columns].copy()
    annual = schedule.loc[schedule.season.eq(season) & schedule.game_type.eq("REG") & schedule.week.isin(weeks)]
    if set(annual.week) != set(weeks):
        raise ValueError("a scheduled target week is missing")
    if not set(weeks) <= set(roster.loc[roster.season.eq(season) & roster.game_type.eq("REG"), "week"]):
        raise ValueError("a required historical weekly roster is missing")
    queries, quarantine, coverage = [], [], []
    for week in weeks:
        games = annual.loc[annual.week.eq(week)].copy()
        if games.empty or games.game_id.isna().any() or games.game_id.duplicated().any():
            raise ValueError("complete unambiguous game identities required")
        day = pd.to_datetime(games.gameday.astype("string"), errors="raise").min()
        enumeration_cutoff = day.tz_localize("UTC") - pd.Timedelta(days=1)
        packet = query_builder(roster, schedule, season=season, week=week,
            cutoff_utc=enumeration_cutoff, maximum_rows=maximum_rows_per_week,
            expected_remaining_games=len(games))
        q = packet["queries"].copy()
        if packet["coverage"]["elapsed_games"] or not packet["no_remaining_game"].empty:
            raise ValueError("historical enumeration omitted an already elapsed game")
        if set(q.game_id) != set(games.game_id):
            raise ValueError("no eligible queried players for at least one scheduled game")
        q["cutoff_utc"] = pd.to_datetime(q.kickoff_utc, utc=True)
        home = games.assign(home_team=normalize_team(games.home_team)).set_index("game_id").home_team
        q["is_home"] = q.team.eq(q.game_id.map(home))
        q["participation_state"] = "unknown"
        q["historical_horizon"] = "reconstructed_kickoff"
        q["historical_horizon_version"] = "reconstructed-kickoff-horizon-v1"
        q["evidence_kind"] = EVIDENCE
        q["original_forecast_issued_at"] = pd.NaT
        q["original_roster_publication_utc"] = pd.NaT
        q["historical_preparation_version"] = VERSION
        q.attrs.clear()
        queries.append(q)
        bad = packet["quarantine"].copy(); bad["target_week"] = week
        quarantine.append(bad)
        coverage.append({"season": season, "week": week,
            "scheduled_games": len(games), "queried_games": q.game_id.nunique(),
            "roster_skill_rows": packet["coverage"]["retained_weekly_skill_rows"],
            "query_rows": len(q), "quarantine_rows": len(bad),
            "original_issue_or_roster_publication_authenticated": False,
            "pregame_statistical_participation_used_for_population": False})
    all_queries = pd.concat(queries, ignore_index=True)
    if all_queries.duplicated(list(KEYS)).any():
        raise ValueError("cross-week query keys are not unique")
    all_queries = all_queries.sort_values(["week", "kickoff_utc", "game_id", "player_id"], kind="stable").reset_index(drop=True)
    return {"queries": all_queries, "quarantine": pd.concat(quarantine, ignore_index=True),
            "coverage": coverage, "version": VERSION, "evidence_kind": EVIDENCE}


def historical_features(history_parts, packet, *, features_module, assert_clock_contract,
                        authority, augment_week=None):
    """Reuse unchanged old learner features under an explicit seven-day lane.

    Sources can include the retained raw2019-2025/2026W1-5 history and normalized
    qualified W6 history. Do NOT pass W6 query features as raw history. Unknown
    availability is excluded with a count, never fabricated by the old builder.
    Each target week uses earlier weeks only, so its target-game values are not
    read as features and later target weeks retain earlier observed histories.
    """
    _authorize(authority)
    import numpy as np
    import pandas as pd
    if packet.get("version") != VERSION or packet.get("evidence_kind") != EVIDENCE:
        raise ValueError("exact newly named roster query packet required")
    if not history_parts:
        raise ValueError("authenticated prior raw history required")
    parts = []
    for history in history_parts:
        if any(str(c).startswith("f_") for c in history):
            raise ValueError("raw history only; do not recycle fitted query features")
        required = {*KEYS, "team", "opponent", "position", "kickoff_utc", "outcome_available_utc", "participation_state"}
        if not required <= set(history):
            raise ValueError("qualified raw history schema differs")
        h = history.copy(); h.attrs.clear()
        if not (h.season.between(2019, 2025) | h.season.eq(2026) & h.week.between(1, 6)).all():
            raise ValueError("only prior2019-2025/2026W1-6 history is admitted")
        parts.append(h)
    history = pd.concat(parts, ignore_index=True)
    if history.duplicated(list(KEYS)).any():
        raise ValueError("overlapping history inputs require explicit original-key reconciliation")
    history["kickoff_utc"] = pd.to_datetime(history.kickoff_utc, utc=True)
    history["outcome_available_utc"] = pd.to_datetime(history.outcome_available_utc, utc=True)
    unknown_availability = history.outcome_available_utc.isna()
    omitted_unknown_availability = int(unknown_availability.sum())
    history = history.loc[~unknown_availability].copy()
    if history.kickoff_utc.isna().any() or not history.outcome_available_utc.eq(history.kickoff_utc + pd.Timedelta(days=7)).all():
        raise ValueError("this unchanged-feature adapter admits only the explicitly assumed seven-day lane; genuinely different timing needs another adapter")
    blank_fields = [*features_module.PLAYER_STATS, *("team_stat_" + x for x in features_module.TEAM_STATS)]
    results, coverage = [], []
    for week in WEEKS:
        q = packet["queries"].loc[packet["queries"].week.eq(week)].copy().reset_index(drop=True)
        source = history.loc[history.season.lt(2026) | history.season.eq(2026) & history.week.lt(week)].copy()
        source["cutoff_utc"] = source.kickoff_utc
        source.attrs.clear(); q.attrs.clear()
        target_keys = pd.MultiIndex.from_frame(q.loc[:, list(KEYS)])
        source = source.loc[~pd.MultiIndex.from_frame(source.loc[:, list(KEYS)]).isin(target_keys)].copy()
        # Internal builder placeholder only. All target values remain null; no
        # placeholder can become an earlier history observation in this week.
        internal_placeholder = q.kickoff_utc + pd.Timedelta(days=7)
        if (internal_placeholder <= q.cutoff_utc.max()).any():
            raise ValueError("target-week schedule span requires a distinct rowwise preparation")
        q["outcome_available_utc"] = internal_placeholder
        q["participation_state"] = "unknown"
        for field in blank_fields:
            q[field] = np.nan
        combined = features_module.build_features(pd.concat([source, q], ignore_index=True))
        result = combined.iloc[len(source):].copy().reset_index(drop=True)
        result["f_player_play_rate8"] = np.nan
        result["participation_probability_state"] = "unavailable_incomplete_nonappearance_denominator"
        result["feature_max_assumed_history_available_utc"] = result.feature_max_source_available_utc
        result["historical_preparation_version"] = VERSION
        if augment_week is not None:
            # Only an independently pinned/root-reviewed earlier-information
            # augmenter may supply ordered/backfield columns. No default proxy.
            result = augment_week(source, q, result)
        if result[list(KEYS)].to_dict("records") != q[list(KEYS)].to_dict("records") or not result.participation_state.eq("unknown").all():
            raise ValueError("feature builder/augmenter changed original query identity or participation")
        assert_clock_contract(result)
        keep = [c for c in packet["queries"].columns if c in result]
        keep += [c for c in result if c.startswith("f_") or c in {"feature_max_source_available_utc", "feature_max_assumed_history_available_utc", "participation_probability_state"}]
        result = result.loc[:, list(dict.fromkeys(keep))].copy()
        if set(blank_fields) & set(result):
            raise ValueError("target values escaped feature-only projection")
        result.attrs.clear(); results.append(result)
        coverage.append({"week": week, "query_rows": len(q), "history_rows_before_week": len(source),
            "feature_columns": sum(c.startswith("f_") for c in result),
            "history_availability_unknown_rows_omitted_across_panel": omitted_unknown_availability,
            "availability_rule": "FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION",
            "operational_manifest_or_genuine_pregame_receipt_created": False})
    frame = pd.concat(results, ignore_index=True)
    if frame.duplicated(list(KEYS)).any():
        raise ValueError("prepared historical query keys changed")
    return {"features": frame, "coverage": coverage, "version": VERSION, "evidence_kind": EVIDENCE}


def reusable_overlap(prepared, cached_queries, feature_columns, *, authority):
    """Return per-key eligibility for reusing cached predictions, no scores.

    Exact identities, context, cutoff and the actual model's feature columns
    must agree. All mismatches stay in the primary population for new inference.
    NaN is compared as the same missing input; other float64 bits must match.
    """
    _authorize(authority)
    import numpy as np
    import pandas as pd
    context = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
    columns = [*KEYS, *context, *feature_columns]
    if len(set(feature_columns)) != len(feature_columns) or not feature_columns:
        raise ValueError("explicit unique model feature list required")
    if any(not set(columns) <= set(f) or f.duplicated(list(KEYS)).any() for f in (prepared, cached_queries)):
        raise ValueError("exact feature/query projection required before cached prediction reuse")
    merged = prepared.loc[:, columns].merge(cached_queries.loc[:, columns], on=list(KEYS), how="left", suffixes=("_new", "_old"), indicator=True, validate="one_to_one")
    good = merged._merge.eq("both").to_numpy()
    for c in context:
        a,b = merged[c+"_new"],merged[c+"_old"]
        if c.endswith("_utc"):
            a,b = pd.to_datetime(a,utc=True),pd.to_datetime(b,utc=True)
        good &= (a.eq(b) | a.isna() & b.isna()).to_numpy()
    for c in feature_columns:
        a = pd.to_numeric(merged[c+"_new"],errors="raise").to_numpy(dtype="float64")
        b = pd.to_numeric(merged[c+"_old"],errors="raise").to_numpy(dtype="float64")
        good &= (a.view("uint64")==b.view("uint64")) | np.isnan(a) & np.isnan(b)
    out = merged.loc[:, list(KEYS)].copy(); out["cached_prediction_reuse_eligible"] = good
    out["reason"] = np.where(good,"EXACT_MODEL_FEATURE_CONTEXT_OVERLAP","NEW_OR_INCOMPATIBLE_QUERY_REQUIRES_INFERENCE")
    return out


if __name__ == "__main__":
    raise SystemExit("Source-only library: root's separately sealed runner must authenticate inputs, resources, managed storage and authorize invocation.")
