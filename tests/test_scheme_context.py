import numpy as np
import pandas as pd
import pytest

from nfl_lab.models import _feature_names
from nfl_lab.scheme_context import PBP_COLUMNS, aggregate_pbp, merge_scheme_asof, opponent_adjusted_history


def fixture():
    schedule, plays = [], []
    for game in range(1, 7):
        kickoff = pd.Timestamp("2000-09-01T17:00:00Z") + pd.Timedelta(days=8 * game)
        for team, other in (("A", "B"), ("B", "A")):
            schedule.append(dict(game_id=f"g{game}", team=team, opponent=other, season=2000,
                week=game, kickoff_utc=kickoff, available_utc=kickoff+pd.Timedelta(days=7),
                coach="Old" if game < 4 else "New", stadium_id="venue", roof="outdoors", surface="grass"))
        for play in range(6):
            own = "A" if play < 3 else "B"
            local = play % 3
            row = dict.fromkeys(PBP_COLUMNS, 0)
            row.update(game_id=f"g{game}", season=2000, play_id=play, posteam=own,
                defteam="B" if own == "A" else "A", play_type="pass" if local != 1 else "run",
                qb_dropback=1 if local != 1 else 0, qb_kneel=0, qb_spike=0,
                shotgun=1, no_huddle=0, qtr=1, down=1 if local != 1 else 2,
                score_differential=0, half_seconds_remaining=1000-local*30,
                yardline_100=[80, 15, 10][local], game_seconds_remaining=3500-play*30,
                drive=1 if own == "A" else 2)
            plays.append(row)
    schedule = pd.DataFrame(schedule)
    pbp = pd.DataFrame(plays)
    features = schedule.loc[schedule.team.eq("A") & schedule.week.eq(6),
                            ["season", "week", "game_id", "team", "opponent", "kickoff_utc"]].copy()
    features["player_id"] = "synthetic"
    features["f_player_ability_mean3"] = 8.
    features["actual_test_sentinel"] = 12345.
    return features, schedule, pbp


def prepared(pbp, schedule):
    return opponent_adjusted_history(aggregate_pbp(pbp, schedule))


def test_exact_features_base_preserved_pooled_rates_and_shared_engine_recognition():
    features, schedule, pbp = fixture()
    out = merge_scheme_asof(features, prepared(pbp, schedule))
    pd.testing.assert_frame_equal(out[list(features)], features)
    added = [col for col in out if col.startswith("f_scheme_")]
    assert len(added) == 47
    assert out.f_scheme_offense_dropback_rate_mean3.iloc[0] == pytest.approx(2/3)
    assert out.f_scheme_offense_dropback_rate_n3.iloc[0] == 3
    assert out.f_scheme_offense_clock_runoff_seconds_mean3.iloc[0] == 30
    assert out.f_scheme_offense_redzone_dropback_rate_mean3.iloc[0] == .5
    assert out.f_scheme_rest_days.iloc[0] == 8
    assert out.f_scheme_coach_change_prior.iloc[0] == 0
    assert out.f_scheme_venue_roof_closed_mean3.iloc[0] == 0
    assert out.f_scheme_venue_artificial_mean3.iloc[0] == 0
    names, rejected = _feature_names(out, out, "ridge")
    assert all(col in names for col in added) and not rejected


def test_target_outcomes_playmix_weather_coach_roof_do_not_change_own_features():
    features, schedule, pbp = fixture()
    expected = merge_scheme_asof(features, prepared(pbp, schedule))
    changed = pbp.copy()
    target = changed.game_id.eq("g6")
    changed.loc[target, ["qb_dropback", "no_huddle", "shotgun", "score_differential"]] = [0, 1, 0, 60]
    changed["weather"] = "Target actual weather must never be loaded"
    changed_schedule = schedule.copy()
    changed_schedule.loc[changed_schedule.game_id.eq("g6"), ["coach", "roof", "surface"]] = ["Future", "dome", "fieldturf"]
    actual = merge_scheme_asof(features, prepared(changed, changed_schedule))
    pd.testing.assert_frame_equal(expected, actual)


def test_missing_intervening_game_consumes_slot_without_older_backfill():
    features, schedule, pbp = fixture()
    pbp = pbp.loc[pbp.game_id.ne("g4")].copy()
    expected = merge_scheme_asof(features, prepared(pbp, schedule))
    assert expected.f_scheme_offense_dropback_rate_n3.iloc[0] == 2
    # g2 lies outside the exact g5,g4,g3 slots, although g4 is unsupported.
    pbp.loc[pbp.game_id.eq("g2"), "qb_dropback"] = 0
    actual = merge_scheme_asof(features, prepared(pbp, schedule))
    assert actual.f_scheme_offense_dropback_rate_mean3.iloc[0] == expected.f_scheme_offense_dropback_rate_mean3.iloc[0]


def test_prior_rates_pool_supported_exposures_instead_of_averaging_game_ratios():
    features, schedule, pbp = fixture()
    pbp["qb_dropback"] = pbp.qb_dropback.astype(float)
    own = pbp.posteam.eq("A")
    pbp.loc[own & pbp.game_id.eq("g3"), "qb_dropback"] = 1
    pbp.loc[own & pbp.game_id.eq("g4"), "qb_dropback"] = [0., np.nan, np.nan]
    pbp.loc[own & pbp.game_id.eq("g5"), "qb_dropback"] = 0
    out = merge_scheme_asof(features, prepared(pbp, schedule))
    assert out.f_scheme_offense_dropback_rate_mean3.iloc[0] == pytest.approx(3/7)


def test_unknown_binary_flags_and_unsupported_venue_do_not_become_zero():
    features, schedule, pbp = fixture()
    pbp["shotgun"] = np.nan
    schedule["surface"] = "unknown material"
    out = merge_scheme_asof(features, prepared(pbp, schedule))
    assert pd.isna(out.f_scheme_offense_shotgun_rate_mean3.iloc[0])
    assert out.f_scheme_offense_shotgun_rate_n3.iloc[0] == 0
    assert pd.isna(out.f_scheme_venue_artificial_mean3.iloc[0])


def test_strict_lag_boundary_late_clock_and_cold_start_fallbacks():
    features, schedule, pbp = fixture()
    features["cutoff_utc"] = schedule.loc[schedule.game_id.eq("g5"), "available_utc"].iloc[0]
    out = merge_scheme_asof(features, prepared(pbp, schedule))
    assert (out.scheme_feature_max_source_available_utc < out.cutoff_utc).all()
    cold = features.copy()
    cold["team"] = "NEW"
    out = merge_scheme_asof(cold, prepared(pbp, schedule))
    assert pd.isna(out.f_scheme_offense_dropback_rate_mean3.iloc[0])
    assert out.f_scheme_offense_dropback_rate_n3.iloc[0] == 0
    assert pd.isna(out.f_scheme_rest_days.iloc[0])
    games = prepared(pbp, schedule)
    games.loc[games.game_id.eq("g1"), "available_utc"] = games.loc[games.game_id.eq("g1"), "kickoff_utc"]
    with pytest.raises(ValueError, match="seven_day_floor"):
        merge_scheme_asof(features, games)


def test_duplicate_or_conflicting_identity_and_late_cutoff_rejected():
    features, schedule, pbp = fixture()
    with pytest.raises(ValueError, match="duplicate_public_play"):
        aggregate_pbp(pd.concat([pbp, pbp]), schedule)
    bad = schedule.copy()
    bad.loc[bad.team.eq("A"), "opponent"] = "C"
    with pytest.raises(ValueError, match="team_opponent_mismatch"):
        aggregate_pbp(pbp, bad)
    features["cutoff_utc"] = features.kickoff_utc + pd.Timedelta(seconds=1)
    with pytest.raises(ValueError, match="cutoff_after"):
        merge_scheme_asof(features, prepared(pbp, schedule))


def test_offseason_staleness_keeps_absence_and_does_not_change_base_population():
    features, schedule, pbp = fixture()
    features["game_id"] = "future-new-season"
    features["kickoff_utc"] += pd.Timedelta(days=200)
    out = merge_scheme_asof(features, prepared(pbp, schedule))
    assert len(out) == len(features)
    assert pd.isna(out.f_scheme_offense_dropback_rate_mean3.iloc[0])
    assert out.f_scheme_offense_dropback_rate_n3.iloc[0] == 0
