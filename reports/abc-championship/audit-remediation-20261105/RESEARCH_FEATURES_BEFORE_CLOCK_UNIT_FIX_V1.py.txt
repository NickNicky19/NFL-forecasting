"""Deterministic features built only from outcomes available before each cutoff.

The default historic availability is kickoff plus seven days; this is an
explicit reconstruction assumption. Source revisions and historic roster
publication times remain unverified. Target-game box-score fields never enter
their own features. All model inputs have the ``f_`` prefix.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from nfl_lab.data import TARGETS

PLAYER_STATS = list(TARGETS) + ["rec_tgt", "rush_td", "rec_td", "offense_snaps"]
TEAM_STATS = ["pass_yd", "rush_yd", "pass_att", "rush_att", "rec_yd"]
FEATURE_VERSION = "cutoff-features-v2-20261025"


def _times(series: pd.Series) -> np.ndarray:
    return pd.to_datetime(series, utc=True).astype("int64").to_numpy()


def _lookup_windows(source: pd.DataFrame, target: pd.DataFrame, entity: str,
                    columns: list[str], windows: tuple[int, ...] = (3, 8)) -> dict:
    """Vectorized cumulative windows at each independently supplied cutoff."""
    result = {(col, win, kind): np.full(len(target), np.nan)
              for col in columns for win in windows for kind in ("mean", "n", "sum")}
    result["games"] = np.zeros(len(target))
    result["max_available"] = np.full(len(target), np.iinfo(np.int64).min, dtype=np.int64)
    source_groups = {key: group.sort_values(["outcome_available_utc", "kickoff_utc"], kind="stable")
                     for key, group in source.loc[source.outcome_available_utc.notna()].groupby(entity, sort=False, dropna=True)}
    for key, indices in target.groupby(entity, sort=False, dropna=True).indices.items():
        group = source_groups.get(key)
        if group is None:
            continue
        positions = np.asarray(indices)
        available = _times(group.outcome_available_utc)
        right = np.searchsorted(available, _times(target.iloc[positions].cutoff_utc), side="left")
        result["games"][positions] = right
        good = right > 0
        result["max_available"][positions[good]] = available[right[good] - 1]
        vals = group[columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        kickoffs = _times(group.kickoff_utc)
        if np.any(kickoffs[1:] < kickoffs[:-1]):
            # Availability admits observations; game chronology defines recency.
            # Keep the cumulative fast path below for ordinary monotone clocks.
            # Unknown values still consume a game slot inside the chosen window.
            for position, stop in zip(positions, right):
                order = np.argsort(kickoffs[:stop], kind="stable")
                for win in windows:
                    selected = vals[order[-win:]]
                    finite = np.isfinite(selected)
                    ns = finite.sum(axis=0)
                    totals = np.where(finite, selected, 0).sum(axis=0)
                    means = np.divide(totals, ns, out=np.full(len(columns), np.nan), where=ns > 0)
                    for j, col in enumerate(columns):
                        result[(col, win, "mean")][position] = means[j]
                        result[(col, win, "n")][position] = ns[j]
                        result[(col, win, "sum")][position] = totals[j] if ns[j] else np.nan
            continue
        finite = np.isfinite(vals)
        sums = np.vstack([np.zeros(len(columns)), np.cumsum(np.where(finite, vals, 0), axis=0)])
        counts = np.vstack([np.zeros(len(columns)), np.cumsum(finite, axis=0)])
        for win in windows:
            left = np.maximum(0, right - win)
            totals = sums[right] - sums[left]
            ns = counts[right] - counts[left]
            means = np.divide(totals, ns, out=np.full_like(totals, np.nan), where=ns > 0)
            for j, col in enumerate(columns):
                result[(col, win, "mean")][positions] = means[:, j]
                result[(col, win, "n")][positions] = ns[:, j]
                result[(col, win, "sum")][positions] = np.where(ns[:, j] > 0, totals[:, j], np.nan)
    return result


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(numerator, denominator, out=np.full_like(numerator, np.nan, dtype=float),
                     where=np.isfinite(denominator) & (denominator > 0))


def _team_table(history: pd.DataFrame) -> pd.DataFrame:
    keys = ["game_id", "team", "opponent", "kickoff_utc", "outcome_available_utc"]
    rows = history[history.participation_state.eq("played")].copy()
    # The adapter computes full-team totals before limiting player positions.
    if all("team_stat_" + col in history for col in TEAM_STATS):
        rows = history.copy()
        team = rows.groupby(keys, dropna=False, as_index=False)[["team_stat_" + c for c in TEAM_STATS]].first()
        team = team.rename(columns={"team_stat_" + c: c for c in TEAM_STATS})
    else:
        team = rows.groupby(keys, dropna=False, as_index=False)[TEAM_STATS].sum(min_count=1)
    # A future or unsupported game is a target context, never an observed zero.
    team = team[team[TEAM_STATS].notna().any(axis=1)].copy()
    team["offense_plays"] = team.pass_att + team.rush_att
    team = team.sort_values(["outcome_available_utc", "game_id", "team"]).reset_index(drop=True)
    return team


def _league_prior(team: pd.DataFrame, targets: pd.DataFrame, col: str) -> np.ndarray:
    if team.empty:
        return np.full(len(targets), np.nan)
    available = _times(team.outcome_available_utc)
    right = np.searchsorted(available, _times(targets.cutoff_utc), side="left")
    vals = team[col].to_numpy(float)
    valid = np.isfinite(vals)
    sums = np.r_[0.0, np.cumsum(np.where(valid, vals, 0))]
    counts = np.r_[0, np.cumsum(valid)]
    return _ratio(sums[right], counts[right])


def build_features(history: pd.DataFrame) -> pd.DataFrame:
    """Return original rows/order plus prior player/team/opponent numeric inputs.

    Optional ``cutoff_utc`` allows a forecast collected before kickoff. Missing
    outcomes stay missing. Window size means last roster-eligible games whose
    assumed outcomes are available, so unknown intervening rows consume a slot.
    No look-ahead filling, cross-player averaging or target-game weather occurs.
    """
    started = time.monotonic()
    required = {"player_id", "game_id", "team", "opponent", "kickoff_utc", "participation_state"}
    if required - set(history):
        raise ValueError(f"history missing {sorted(required - set(history))}")
    if history.duplicated(["game_id", "player_id"]).any():
        raise ValueError("duplicate player/game identity")
    original_index = history.index.copy()
    out = history.copy().reset_index(drop=True)
    out["kickoff_utc"] = pd.to_datetime(out.kickoff_utc, utc=True)
    if out.kickoff_utc.isna().any():
        raise ValueError("missing kickoff")
    if "cutoff_utc" not in out:
        out["cutoff_utc"] = out.kickoff_utc
    else:
        out["cutoff_utc"] = pd.to_datetime(out.cutoff_utc, utc=True).fillna(out.kickoff_utc)
    if out.cutoff_utc.isna().any() or (out.cutoff_utc > out.kickoff_utc).any():
        raise ValueError("cutoff must be at or before kickoff")
    if "outcome_available_utc" not in out:
        out["outcome_available_utc"] = out.kickoff_utc + pd.Timedelta(days=7)
    out["outcome_available_utc"] = pd.to_datetime(out.outcome_available_utc, utc=True)
    if (out.outcome_available_utc <= out.kickoff_utc).any():
        raise ValueError("outcome availability must be after its game kickoff")
    for col in PLAYER_STATS:
        if col not in out:
            out[col] = np.nan
    # An absent availability column declares the historical reconstruction
    # assumption above. An explicitly unknown clock cannot establish availability.
    source = out.loc[out.outcome_available_utc.notna()].copy()
    source["known_play"] = np.where(source.participation_state.eq("played"), 1.0,
                                   np.where(source.participation_state.eq("DNP"), 0.0, np.nan))
    player = _lookup_windows(source, out, "player_id", PLAYER_STATS + ["known_play"])
    features = {}
    for col in PLAYER_STATS:
        for win in (3, 8):
            features[f"f_player_{col}_mean{win}"] = player[(col, win, "mean")]
            features[f"f_player_{col}_n{win}"] = player[(col, win, "n")]
    # targets is an explicitly named alias for downstream workload adapters.
    for win in (3, 8):
        features[f"f_player_targets_mean{win}"] = player[("rec_tgt", win, "mean")]
        features[f"f_player_targets_n{win}"] = player[("rec_tgt", win, "n")]
    features["f_player_games_prior"] = player["games"]
    features["f_player_play_rate8"] = player[("known_play", 8, "mean")]
    features["f_player_known_participation_n8"] = player[("known_play", 8, "n")]
    for name, num, den in [("pass_ypa3", "pass_yd", "pass_att"), ("comp_rate3", "pass_cmp", "pass_att"),
                           ("rush_ypa3", "rush_yd", "rush_att"), ("rec_ypt3", "rec_yd", "rec_tgt"),
                           ("rec_catch_rate3", "rec", "rec_tgt")]:
        # Match numerator/denominator availability, preserving unknown exposure.
        valid = source[[num, den]].notna().all(axis=1)
        pair = source[["player_id", "kickoff_utc", "outcome_available_utc", num, den]].copy()
        pair.loc[~valid, [num, den]] = np.nan
        pooled = _lookup_windows(pair, out, "player_id", [num, den], (3,))
        features["f_player_" + name] = _ratio(pooled[(num, 3, "sum")], pooled[(den, 3, "sum")])

    team = _team_table(source)
    team_columns = TEAM_STATS + ["offense_plays"]
    own = _lookup_windows(team, out, "team", team_columns)
    defense = team.rename(columns={"team": "offense", "opponent": "team"})
    opponents = out.copy()
    opponents["team"] = out.opponent
    allowed = _lookup_windows(defense, opponents, "team", team_columns)
    for col in team_columns:
        features[f"f_team_{col}_mean3"] = own[(col, 3, "mean")]
        features[f"f_opp_{col}_allowed_mean3"] = allowed[(col, 3, "mean")]
    features["f_team_pass_rate3"] = _ratio(own[("pass_att", 3, "sum")], own[("offense_plays", 3, "sum")])
    features["f_team_games_prior"] = own["games"]
    features["f_opp_games_prior"] = allowed["games"]

    # Earlier-opponent adjustment: subtract that opponent's pregame shrunken
    # mean, then average those earlier residuals and add the current league mean.
    # Every expectation is fitted from games available at that earlier cutoff.
    if not team.empty:
        earlier = team.copy()
        earlier["cutoff_utc"] = earlier.kickoff_utc
        prior_own = _lookup_windows(team, earlier, "team", ["pass_yd", "rush_yd"], (8,))
        earlier_opponent = earlier.copy()
        earlier_opponent["team"] = earlier.opponent
        prior_def = _lookup_windows(defense, earlier_opponent, "team", ["pass_yd", "rush_yd"], (8,))
        for col in ("pass_yd", "rush_yd"):
            base = _league_prior(team, earlier, col)
            own_n = prior_own[(col, 8, "n")]
            def_n = prior_def[(col, 8, "n")]
            own_expected = (np.nan_to_num(prior_own[(col, 8, "sum")]) + 4 * base) / (own_n + 4)
            def_expected = (np.nan_to_num(prior_def[(col, 8, "sum")]) + 4 * base) / (def_n + 4)
            earlier[col + "_off_residual"] = earlier[col].to_numpy() - def_expected
            earlier[col + "_def_residual"] = earlier[col].to_numpy() - own_expected
        residual_cols = [c + "_off_residual" for c in ("pass_yd", "rush_yd")]
        adj_own = _lookup_windows(earlier, out, "team", residual_cols, (8,))
        def_residuals = earlier.rename(columns={"team": "offense", "opponent": "team"})
        adj_def = _lookup_windows(def_residuals, opponents, "team", [c + "_def_residual" for c in ("pass_yd", "rush_yd")], (8,))
        for col in ("pass_yd", "rush_yd"):
            base_now = _league_prior(team, out, col)
            features[f"f_team_{col}_adjusted_mean8"] = base_now + adj_own[(col + "_off_residual", 8, "mean")]
            features[f"f_opp_{col}_adjusted_allowed_mean8"] = base_now + adj_def[(col + "_def_residual", 8, "mean")]
    else:
        for col in ("pass_yd", "rush_yd"):
            features[f"f_team_{col}_adjusted_mean8"] = np.full(len(out), np.nan)
            features[f"f_opp_{col}_adjusted_allowed_mean8"] = np.full(len(out), np.nan)
    # Rest uses only earlier game dates in the known schedule, never outcomes.
    schedule = out[["game_id", "team", "kickoff_utc"]].drop_duplicates().sort_values("kickoff_utc")
    schedule["f_rest_days"] = schedule.groupby("team").kickoff_utc.diff().dt.total_seconds() / 86400
    rest_map = schedule.set_index(["game_id", "team"]).f_rest_days
    features["f_rest_days"] = rest_map.reindex(pd.MultiIndex.from_frame(out[["game_id", "team"]])).to_numpy()
    features["f_is_home"] = pd.to_numeric(out.get("is_home", pd.Series(np.nan, index=out.index)), errors="coerce").to_numpy(float)
    result = pd.concat([out, pd.DataFrame(features)], axis=1)
    # Adjusted ratings also depend on the earlier league mean, not only the
    # selected player's/team's records. Include its latest eligible source.
    league_max = np.full(len(out), np.iinfo(np.int64).min, dtype=np.int64)
    if not team.empty:
        available = _times(team.outcome_available_utc)
        right = np.searchsorted(available, _times(out.cutoff_utc), side="left")
        good = right > 0
        league_max[good] = available[right[good] - 1]
    max_available = np.maximum.reduce([player["max_available"], own["max_available"], allowed["max_available"], league_max])
    result["feature_max_source_available_utc"] = pd.to_datetime(max_available, utc=True)
    result.index = original_index
    result.attrs["feature_profile"] = {"version": FEATURE_VERSION, "rows": len(result), "numeric_feature_count": len(features),
                                      "elapsed_seconds": round(time.monotonic() - started, 3),
                                      "availability": "strictly before each cutoff_utc; absent column reconstructs lag 7 days; explicit unknown excluded",
                                      "pace_semantics": "pass attempts + rush attempts per game, not neutral-situation or clock pace",
                                      "unimplemented": ["historic authenticated news", "injuries", "routes", "NGS features", "weather forecasts", "private schemes"]}
    return result
