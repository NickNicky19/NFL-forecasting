"""Fixed ordered-prior-game information group for a new CDF comparison.

No source acquisition, training or scoring occurs on import. Availability is
tested before game chronology; unknown participation retains its game slot.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VERSION = "ordered-recent-v1-20261029"
KEYS = ["season", "week", "game_id", "player_id"]
CONTEXT = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
SLOTS = 4
STATS = ("rush_att", "rec", "rec_tgt")
STATES = ("played", "DNP", "unknown")


def columns(target):
    if target not in ("rush_att", "rec"):
        raise ValueError("exact two registered targets required")
    names = [f"f_ordered_{stat}_lag{lag}" for stat in (("rush_att",) if target == "rush_att" else ("rec", "rec_tgt")) for lag in range(1, 5)]
    names += [f"f_ordered_slot_{field}_lag{lag}" for field in ("age_days", "played", "DNP", "unknown") for lag in range(1, 5)]
    return names


ALL_COLUMNS = list(dict.fromkeys(columns("rush_att") + columns("rec")))


def augment(frame, history):
    """Append fixed four-slot features; callers qualify source-clock identities.

    Training history can contain later rows than a given training example, but
    every lookup masks by *both* strictly earlier availability and kickoff.
    Future-query callers must project source numeric values only after their
    registered availability predicate. This function never reads target labels
    from frame and does not alter any existing base feature.
    """
    if frame.duplicated(KEYS).any() or history.duplicated(["player_id", "game_id"]).any():
        raise ValueError("unique query and history identities required")
    if not history.participation_state.isin(STATES).all():
        raise ValueError("unregistered source participation state")
    h = history.copy()
    h["kickoff_utc"] = pd.to_datetime(h.kickoff_utc, utc=True, errors="raise")
    h["outcome_available_utc"] = pd.to_datetime(h.outcome_available_utc, utc=True, errors="raise")
    if h.kickoff_utc.isna().any() or h.outcome_available_utc.isna().any() or not (h.outcome_available_utc > h.kickoff_utc).all():
        raise ValueError("history clocks must already be qualified, never fabricated")
    q = frame.copy().reset_index(drop=True)
    cutoff = pd.to_datetime(q.cutoff_utc, utc=True, errors="raise")
    if cutoff.isna().any():
        raise ValueError("query cutoff unavailable")
    result = np.full((len(q), len(ALL_COLUMNS)), np.nan)
    slots_used = np.zeros(len(q), dtype=np.int16)
    index = {name: j for j, name in enumerate(ALL_COLUMNS)}
    groups = {str(player): t.sort_values(["kickoff_utc", "game_id"], kind="stable") for player, t in h.groupby("player_id", sort=False)}
    for player, positions in q.groupby("player_id", sort=False).groups.items():
        old = groups.get(str(player))
        if old is None:
            continue
        ko = old.kickoff_utc.astype("datetime64[ns, UTC]").astype("int64").to_numpy()
        av = old.outcome_available_utc.astype("datetime64[ns, UTC]").astype("int64").to_numpy()
        states = old.participation_state.astype(str).to_numpy()
        vals = {stat: pd.to_numeric(old[stat], errors="coerce").to_numpy(float) for stat in STATS}
        for pos in positions:
            limit = cutoff.iloc[pos].value
            selected = np.flatnonzero((av < limit) & (ko < limit))[-SLOTS:][::-1]
            slots_used[pos] = len(selected)
            for lag, source in enumerate(selected, start=1):
                state = states[source]
                result[pos, index[f"f_ordered_slot_age_days_lag{lag}"]] = (limit-ko[source])/86_400_000_000_000
                for name in STATES:
                    result[pos, index[f"f_ordered_slot_{name}_lag{lag}"]] = float(state == name)
                for stat in STATS:
                    value = vals[stat][source]
                    # Known participation alone is not a complete statistic.
                    if state == "played" and np.isfinite(value) and value >= 0 and value == np.floor(value):
                        result[pos, index[f"f_ordered_{stat}_lag{lag}"]] = value
    for j, name in enumerate(ALL_COLUMNS):
        q[name] = result[:, j]
    q["ordered_prior_slots"] = slots_used
    return q


def check_fictional():
    """Tiny deterministic source-contract checks, not NFL experiments."""
    h = pd.DataFrame([
        {"player_id":"p","game_id":"a","kickoff_utc":"2020-01-01T00:00:00Z","outcome_available_utc":"2020-01-02T00:00:00Z","participation_state":"played","rush_att":2,"rec":1,"rec_tgt":2},
        {"player_id":"p","game_id":"b","kickoff_utc":"2020-01-03T00:00:00Z","outcome_available_utc":"2020-01-08T00:00:00Z","participation_state":"played","rush_att":9,"rec":2,"rec_tgt":4},
        {"player_id":"p","game_id":"c","kickoff_utc":"2020-01-05T00:00:00Z","outcome_available_utc":"2020-01-06T00:00:00Z","participation_state":"unknown","rush_att":99,"rec":99,"rec_tgt":99},
        {"player_id":"p","game_id":"d","kickoff_utc":"2020-01-07T00:00:00Z","outcome_available_utc":"2020-01-09T00:00:00Z","participation_state":"DNP","rush_att":0,"rec":0,"rec_tgt":0}])
    q = pd.DataFrame([{"season":2020,"week":2,"game_id":"q","player_id":"p","cutoff_utc":"2020-01-09T00:00:00Z","unrelated_base":123}])
    x = augment(q,h)
    assert x.ordered_prior_slots.iloc[0] == 3
    assert np.isnan(x.f_ordered_rush_att_lag1.iloc[0]) and x.f_ordered_slot_unknown_lag1.iloc[0] == 1
    assert x.f_ordered_rush_att_lag2.iloc[0] == 9  # game chronology, not availability order
    assert x.f_ordered_rush_att_lag3.iloc[0] == 2
    assert np.isnan(x.f_ordered_rush_att_lag4.iloc[0])
    assert x.unrelated_base.iloc[0] == 123
    later=q.copy();later.cutoff_utc="2020-01-10T00:00:00Z";y=augment(later,h)
    assert y.ordered_prior_slots.iloc[0]==4 and y.f_ordered_slot_DNP_lag1.iloc[0]==1
    assert np.isnan(y.f_ordered_rush_att_lag1.iloc[0])  # DNP is not played zero
    return {"state":"PASS","fictional_cases":8,"NFL_observations":0}
