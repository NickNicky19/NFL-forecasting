"""Independent game order and unknown-clock controls; fictional observations."""
import numpy as np
import pandas as pd
from nfl_lab.features import _lookup_windows, build_features, FEATURE_VERSION


def test_delayed_old_game_does_not_replace_a_more_recent_game():
    source = pd.DataFrame({"player_id": ["fictional"]*4,
        "kickoff_utc": pd.to_datetime(["2001-01-01", "2001-01-08", "2001-01-15", "2001-01-22"], utc=True),
        "outcome_available_utc": pd.to_datetime(["2001-01-30", "2001-01-09", "2001-01-16", "2001-01-23"], utc=True),
        "yards": [100., 10., 20., 30.]})
    targets = pd.DataFrame({"player_id": ["fictional"]*3,
        "cutoff_utc": pd.to_datetime(["2001-01-30", "2001-02-01", "2001-01-09"], utc=True)})
    values = _lookup_windows(source, targets, "player_id", ["yards"], (3,))
    np.testing.assert_array_equal(values[("yards",3,"mean")][:2], [20., 20.])
    assert np.isnan(values[("yards",3,"mean")][2])  # strict boundary
    np.testing.assert_array_equal(values["games"], [3,4,0])
    assert pd.Timestamp(values["max_available"][1], tz="UTC") == pd.Timestamp("2001-01-30", tz="UTC")
    source.loc[2, "yards"] = np.nan
    values = _lookup_windows(source, targets.iloc[[1]], "player_id", ["yards"], (3,))
    assert values[("yards",3,"n")][0] == 2
    assert values[("yards",3,"mean")][0] == 20.  # (10+30)/2, old100 not restored


def test_unknown_availability_cannot_supply_player_team_or_league_features():
    history = pd.DataFrame({"player_id": ["fictional"]*2, "game_id": ["old","query"],
        "team": ["A"]*2, "opponent": ["B"]*2, "participation_state": ["played","unknown"],
        "kickoff_utc": pd.to_datetime(["2001-01-01","2001-02-01"], utc=True),
        "outcome_available_utc": [pd.NaT,pd.NaT], "rush_yd": [999.,np.nan]})
    out = build_features(history)
    assert out.outcome_available_utc.isna().all()
    assert out.f_player_rush_yd_mean3.isna().all()
    assert out.f_team_rush_yd_mean3.isna().all()
    assert out.f_player_games_prior.eq(0).all()
    assert out.feature_max_source_available_utc.isna().all()
    assert out.attrs["feature_profile"]["version"] == FEATURE_VERSION
    # Omitting the whole column explicitly selects the established reconstruction.
    reconstructed = build_features(history.drop(columns="outcome_available_utc"))
    assert reconstructed.f_player_rush_yd_mean3.iloc[-1] == 999.
