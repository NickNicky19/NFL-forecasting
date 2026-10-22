import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_lab.ppr_sources import (NFL_FIELDS, RARE_GAPS, audit_cached_coverage,
                                 audit_pbp_event_coverage, nflverse_components, sleeper_components)
from nfl_lab.scoring import PPR_COMPONENTS


def test_explicit_nflverse_zero_is_known_but_absence_and_rare_bridges_stay_unknown():
    raw = {field: 0 for field in NFL_FIELDS.values()}
    result = nflverse_components(raw)
    assert all(result["components"][key] == 0 for key in NFL_FIELDS)
    assert all(result["components"][key] is None for key in RARE_GAPS)
    assert result["qualified_exact"] is False and result["exact_ppr"] is None
    assert set(result["missing_components"]) == set(RARE_GAPS)
    del raw["passing_yards"]
    assert nflverse_components(raw)["components"]["pass_yd"] is None
    raw["fantasy_points_ppr"] = 99
    assert nflverse_components(raw)["exact_ppr"] is None


def test_all_phase_fumbles_are_explicit_and_not_reconstructed_from_offense_parts():
    raw = {field: 0 for field in NFL_FIELDS.values()}
    raw.update(fumbles_lost_total=1, sack_fumbles_lost=0, rushing_fumbles_lost=0, receiving_fumbles_lost=0)
    assert nflverse_components(raw)["components"]["fum_lost"] == 1
    del raw["fumbles_lost_total"]
    assert nflverse_components(raw)["components"]["fum_lost"] is None


def test_signed_yards_and_invalid_nonfinite_boolean_or_fractional_observed_counts():
    raw = {field: 0 for field in NFL_FIELDS.values()}
    raw.update(rushing_yards=-3, receiving_yards=-2.5, passing_yards=-1)
    result = nflverse_components(raw)
    assert result["components"]["rush_yd"] == -3
    assert result["components"]["rec_yd"] == -2.5
    for value in [-1, 0.5, True, float("inf")]:
        result = nflverse_components({**raw, "receptions": value})
        assert result["components"]["rec"] is None
        assert "rec" in result["invalid_components"]
    result = nflverse_components({**raw, "receptions": np.nan})
    assert result["coverage"]["rec"]["status"] == "missing"


def test_sparse_sleeper_keys_never_become_zero_or_generic_total_substitution():
    result = sleeper_components({"rec": 2, "rec_yd": 11, "pts_ppr": 3.1})
    assert result["exact_ppr"] is None and result["components"]["st_ff"] is None
    assert result["coverage"]["st_ff"]["status"] == "missing"
    result = sleeper_components({key: 0 for key in PPR_COMPONENTS})
    assert result["qualified_exact"] and result["exact_ppr"] == 0


def test_explicit_rare_events_and_nonlinear_defensive_fumble_exception():
    raw = {key: 0 for key in PPR_COMPONENTS}
    raw.update(pass_yd=10, rush_yd=-4, rec=2, rec_yd=15.5, fum_lost=1,
               st_td=1, st_fum_rec=1, st_ff=1, fum_rec_td=1, idp_blk_kick=1)
    offense = sleeper_components(raw)
    defensive = sleeper_components({**raw, "idp_fum_rec": 1})
    assert offense["exact_ppr"] == 17.55
    assert defensive["exact_ppr"] == 11.55
    del raw["idp_fum_rec"]
    assert sleeper_components(raw)["exact_ppr"] is None


def event(**changes):
    return {"game_id": "game", "play_id": 1, "play_type": "punt", "play_deleted": 0,
            "special_teams_play": 1, "fumble": 0, "fumble_lost": 0, "fumble_forced": 0,
            "fumble_out_of_bounds": 0, "fumble_recovery_1_player_id": None,
            "fumble_recovery_2_player_id": None, "forced_fumble_player_1_player_id": None,
            "forced_fumble_player_2_player_id": None, "blocked_player_id": None,
            "punt_blocked": 0, "field_goal_result": None, "extra_point_result": None, **changes}


def test_pbp_nullified_deleted_missing_live_flags_and_out_of_bounds_are_distinct():
    pbp = pd.DataFrame([event(), event(play_id=2, play_type="no_play", fumble=np.nan),
                        event(play_id=3, play_deleted=1, fumble=np.nan),
                        event(play_id=4, fumble=np.nan),
                        event(play_id=5, fumble=1, fumble_lost=1, fumble_out_of_bounds=1),
                        event(play_id=6, punt_blocked=1, blocked_player_id="00-0030001"),
                        event(play_id=7, play_deleted=np.nan)])
    result = audit_pbp_event_coverage(pbp)
    assert result["excluded_administrative_nullified_or_deleted_rows"] == 3
    assert result["unknown_deletion_status_rows"] == 1
    assert result["missing_flags_on_eligible_rows"]["fumble"] == 1
    assert result["lost_fumbles_without_recoverer"] == result["lost_fumbles_without_recoverer_out_of_bounds"] == 1
    assert result["blocked_kicks_missing_player_id"] == 0
    assert "no inferred Sleeper" in result["source_credit_bridge"]
    with pytest.raises(ValueError, match="duplicate"):
        audit_pbp_event_coverage(pd.concat([pbp, pbp.iloc[[0]]], ignore_index=True))
    with pytest.raises(ValueError, match="schema missing"):
        audit_pbp_event_coverage(pbp.drop(columns="blocked_player_id"))


def test_real_cached_source_schema_and_unknown_zero_contract():
    cache = Path(os.environ.get("NFL_LAB_CACHE", "/workspace/NFL-forecasting/data"))
    required = [cache / "raw" / "play_by_play_2023.parquet", cache / "raw" / "stats_player_week_2023.parquet",
                cache / "raw" / "live/2026-10-22/archive-stats-2026-6.json"]
    if not all(p.exists() for p in required):
        pytest.skip("optional real ignored source cache is not present")
    report = audit_cached_coverage(cache)
    assert report["nflverse"]["rows"] > 1000
    assert report["pbp_events"]["games"] == 285
    assert report["nflverse"]["all18_explicit_qualified_rows"] == 0
    assert report["sleeper_played_skill"]["all18_explicit_qualified_rows"] == 0
    assert all(report["sleeper_played_skill"]["components"][key]["explicit_zero"] == 0 for key in PPR_COMPONENTS)
    assert all(report["nflverse"]["components"][key]["unqualified_credit_bridge"] == report["nflverse"]["rows"] for key in RARE_GAPS)
