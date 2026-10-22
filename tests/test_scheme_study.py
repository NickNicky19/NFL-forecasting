import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_lab.scheme_study import _validate_population


def fixture():
    return pd.DataFrame({"season": [2023, 2023], "week": [1, 2], "game_id": ["g1", "g2"],
        "player_id": ["synthetic", "synthetic"], "actual": [2., np.nan], "team": ["A", "A"],
        "opponent": ["B", "B"], "position": ["RB", "RB"],
        "kickoff_utc": pd.to_datetime(["2023-01-01T00:00:00Z", "2023-01-08T00:00:00Z"]),
        "participation_state": ["played", "unknown"]})


def test_pairing_preserves_missingness_and_all_metadata_with_arbitrary_row_order():
    baseline = fixture()
    _validate_population(baseline, baseline.iloc[::-1])
    changed = baseline.copy()
    changed.loc[1, "actual"] = 0
    with pytest.raises(ValueError, match="outcome_or_identity"):
        _validate_population(baseline, changed)
    changed = baseline.copy()
    changed.loc[0, "participation_state"] = "DNP"
    with pytest.raises(ValueError, match="metadata"):
        _validate_population(baseline, changed)


def test_preregistered_scope_and_fit_budget_are_fixed():
    registration = json.loads((Path(__file__).parents[1] / "config/scheme-study.json").read_text())
    assert registration["registered_before_scheme_fits"]
    assert registration["development_season"] == 2023
    assert registration["training_seasons"] == [2019, 2020, 2021, 2022]
    assert registration["budgets"]["new_fits_total"] == len(registration["targets"]) == 11
    assert registration["budgets"]["fit_seconds"] == 300
    assert registration["budgets"]["threads"] == 2
    assert "fantasy_ppr" not in registration["targets"]
    assert registration["base_features_sha256"] == "ff7a14bac024958f32cbf367e83f6d70e4f86572f461ca6ebd33a9207d04d297"
