import pandas as pd
import pytest

from nfl_lab.evaluation import paired_week_interval


def test_game_and_week_clusters_are_distinct_without_changing_matching_keys():
    rows = []
    for game in range(8):
        for method, value in [("baseline", 2.), ("candidate", 1.)]:
            rows.append({"season": 2024, "week": game // 4 + 1, "game_id": str(game), "player_id": "p",
                "target": "rec", "method": method, "actual": 1., "mean": value, "participation_state": "played"})
    frame = pd.DataFrame(rows)
    week = paired_week_interval(frame, "baseline", "candidate")
    game = paired_week_interval(frame, "baseline", "candidate", cluster="game", family_size=240)
    assert week["interval"] is None and week["weeks"] == 2
    assert game["weeks"] == 2 and game["clusters"] == 8 and game["cluster_unit"] == "game"
    assert game["paired_n"] == 8 and game["interval"] == [-1., -1.]
    assert game["simultaneous_confidence"] == pytest.approx(1 - .05 / 240)
    with pytest.raises(ValueError):
        paired_week_interval(frame, "baseline", "candidate", replicates=501)
