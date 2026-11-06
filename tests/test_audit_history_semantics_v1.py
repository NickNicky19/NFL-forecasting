"""Fictional audit Appendix B cases; no models or NFL outcomes."""
import numpy as np
import pandas as pd
import pytest
from nfl_lab import features


def row(game, kickoff, available, value, *, player='fictional-qb', played=True):
    return dict(game_id=game, player_id=player, team='AA', opponent='BB',
        season=2024, week=1, position='QB', kickoff_utc=pd.Timestamp(kickoff),
        outcome_available_utc=available, participation_state='played' if played else 'unknown',
        pass_yd=value, pass_att=20. if played else np.nan,
        pass_cmp=10. if played else np.nan, rush_att=2. if played else np.nan,
        rush_yd=5. if played else np.nan, rec_yd=0. if played else np.nan)


def unknown_clock_frame():
    return pd.DataFrame([row('old', '2024-08-01T00:00:00Z', pd.NaT, 999.),
        row('target', '2024-09-01T00:00:00Z', pd.NaT, np.nan, played=False)])


def late_publication_frame():
    return pd.DataFrame([
        row('g1', '2024-08-01T00:00:00Z', '2024-08-30T00:00:00Z', 100.),
        row('g2', '2024-08-08T00:00:00Z', '2024-08-10T00:00:00Z', 10.),
        row('g3', '2024-08-15T00:00:00Z', '2024-08-17T00:00:00Z', 20.),
        row('g4', '2024-08-22T00:00:00Z', '2024-08-24T00:00:00Z', 30.),
        row('target', '2024-09-01T00:00:00Z', pd.NaT, np.nan, played=False)])


def target_result(module, frame):
    return module.build_features(frame).loc[frame.game_id.eq('target')].iloc[0]


def test_explicit_unknown_historical_clock_is_not_invented():
    result = target_result(features, unknown_clock_frame())
    assert result.f_player_games_prior == 0
    assert np.isnan(result.f_player_pass_yd_mean3)
    assert np.isnan(result.f_team_pass_yd_mean3)


def test_admit_by_availability_then_choose_recent_games_by_kickoff():
    result = target_result(features, late_publication_frame())
    assert result.f_player_games_prior == 4
    assert result.f_player_pass_yd_mean3 == 20.
    assert result.f_team_pass_yd_mean3 == 20.


def test_absent_availability_column_keeps_declared_reconstruction_policy():
    frame = unknown_clock_frame().drop(columns='outcome_available_utc')
    result = target_result(features, frame)
    assert result.f_player_games_prior == 1
    assert result.f_player_pass_yd_mean3 == 999.


def test_future_target_outcome_clock_may_remain_unknown():
    result = target_result(features, late_publication_frame())
    assert pd.isna(result.outcome_available_utc)
    assert result.f_player_games_prior == 4


@pytest.mark.parametrize('permutation', [[4, 3, 2, 1, 0], [2, 0, 4, 1, 3]])
def test_late_game_order_is_independent_of_input_order(permutation):
    original = late_publication_frame()
    expected = target_result(features, original)
    actual = target_result(features, original.iloc[permutation].reset_index(drop=True))
    for name in ['f_player_pass_yd_mean3', 'f_player_pass_yd_n3', 'f_team_pass_yd_mean3']:
        assert actual[name] == expected[name]


def test_exact_seven_day_boundary_remains_strict_and_disclosed():
    frame = pd.DataFrame([row('old', '2024-08-01T00:00:00Z', '2024-08-08T00:00:00Z', 12.),
        row('target', '2024-08-08T00:00:00Z', pd.NaT, np.nan, played=False)])
    assert target_result(features, frame).f_player_games_prior == 0
    frame.loc[frame.game_id.eq('target'), 'cutoff_utc'] = pd.Timestamp('2024-08-08T00:00:01Z')
    frame.loc[frame.game_id.eq('target'), 'kickoff_utc'] = pd.Timestamp('2024-08-08T00:00:01Z')
    frame.loc[frame.game_id.eq('old'), 'cutoff_utc'] = pd.Timestamp('2024-08-01T00:00:00Z')
    assert target_result(features, frame).f_player_games_prior == 1


def test_duplicate_player_game_versions_require_explicit_upstream_resolution():
    frame = late_publication_frame()
    with pytest.raises(ValueError, match='duplicate player/game'):
        features.build_features(pd.concat([frame, frame.iloc[[0]]], ignore_index=True))


def test_unknown_stat_still_consumes_recent_game_slot():
    frame = late_publication_frame()
    frame.loc[frame.game_id.eq('g3'), 'pass_yd'] = np.nan
    result = target_result(features, frame)
    assert result.f_player_pass_yd_n3 == 2
    assert result.f_player_pass_yd_mean3 == 20.


@pytest.mark.parametrize('source_unit,target_unit', [('ns', 'us'), ('us', 'ns'), ('s', 'ns'), ('ms', 'us')])
def test_lookup_normalizes_datetime_storage_units(source_unit, target_unit):
    frame = late_publication_frame()
    source = frame.iloc[:-1].copy()
    target = frame.iloc[[-1]].reset_index(drop=True)
    source['outcome_available_utc'] = pd.to_datetime(source.outcome_available_utc, utc=True).dt.as_unit(source_unit)
    source['kickoff_utc'] = pd.to_datetime(source.kickoff_utc, utc=True).dt.as_unit(source_unit)
    target['cutoff_utc'] = pd.to_datetime(target.kickoff_utc, utc=True).dt.as_unit(target_unit)
    result = features._lookup_windows(source, target, 'player_id', ['pass_yd'], (3,))
    assert result['games'][0] == 4
    assert result[('pass_yd', 3, 'mean')][0] == 20.
