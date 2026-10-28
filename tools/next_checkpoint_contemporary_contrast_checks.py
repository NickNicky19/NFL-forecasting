"""Fictional-only verification of the required modern-control contrasts."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json

import numpy as np
import pandas as pd

from nfl_lab import next_checkpoint_contemporary as c


def main():
    frame = pd.DataFrame({"game_id": list("ABCDEFGH"), "week": [1, 2, 3, 4, 5, 1, 2, 3]})
    one = np.ones(8)
    equal = c.contrast(frame, one, one, "LEFT", "RIGHT", "MSE")
    assert equal["mean_loss_difference"] == 0 and equal["paired_game"]["lower95"] == 0 and equal["paired_game"]["upper95"] == 0
    assert equal["paired_week"]["state"] == "N_A_FEWER_THAN_8_CLUSTERS"
    losing = c.contrast(frame, 2*one, one, "LEFT", "RIGHT", "MSE")
    assert losing["mean_loss_difference"] == 1 and losing["positive_difference_favors"] == "RIGHT"
    infinite = c.contrast(frame, np.r_[np.inf, np.ones(7)], np.r_[np.inf, np.ones(7)], "LEFT", "RIGHT", "log_loss")
    assert infinite["rows"] == 8 and infinite["finite_difference_rows"] == 7 and infinite["both_infinite_losses"] == 1
    assert infinite["mean_loss_difference"] is None and infinite["paired_game"]["state"].startswith("N_A_NONFINITE")
    old = pd.DataFrame({"season": [2026, 2026], "week": [1, 2], "game_id": ["FICTIONAL_A", "FICTIONAL_B"],
        "player_id": ["fixture1", "fixture2"], "target": "anytime_td", "book_id": 68,
        "actual": [0., 1.], "outcome_state": "supported_played"})
    forecasts = old[c.UNIT + ["book_id"]].copy()
    forecasts["F_probability"] = .5
    for arm, values in {"MODERN_CDF": [.2, .8], "CAT_ATD": [.4, .6], "RECENT_LEADER": [.4, .6], "EQUAL_ATD": [.3, .7]}.items():
        forecasts[arm + "_point"] = values; forecasts[arm + "_reason"] = "ACCEPTED_CACHED"
    class Budget:
        def check(self):
            pass
    with patch.object(c, "read_frame", return_value=old):
        report, graded = c.score_forecasts({"inputs": {"original_matched": "FICTIONAL"}, "recent_leaders": {"anytime_td": {"recipe": "CATBOOST_MEDIUM_BINARY_PROBABILITY"}}}, forecasts, Budget())
    contrasts = report["cells"][0]["prespecified_contrasts"]
    assert len(graded) == 2 and len(contrasts) == 6
    expected = {("MODERN_CDF", "CAT_ATD"): -.12, ("EQUAL_ATD", "MODERN_CDF"): .05, ("EQUAL_ATD", "CAT_ATD"): -.07}
    for item in contrasts:
        assert item["rows"] == 2
        if item["metric"] == "Brier":
            assert abs(item["mean_loss_difference"] - expected[(item["left"], item["right"])]) < 1e-12
        else:
            left = forecasts[item["left"] + "_point"].to_numpy(float)
            right = forecasts[item["right"] + "_point"].to_numpy(float)
            y = old.actual.to_numpy(float)
            a = np.where(y == 1, -np.log(left), -np.log1p(-left))
            b = np.where(y == 1, -np.log(right), -np.log1p(-right))
            assert abs(item["mean_loss_difference"] - np.mean(a-b)) < 1e-12
    checks = ["zero_contrast_and_exact_game_interval", "week_minimum8_kept", "positive_difference_favors_right", "infinite_logloss_not_clipped_or_dropped", "all_three_fixed_event_pairs_retained", "Brier_and_logloss_hand_arithmetic"]
    body = {"state": "FICTIONAL_MODERN_CONTROL_CONTRASTS_PASS", "checks": checks, "NFL_reads": 0,
        "fits": 0, "model_loads": 0, "law_queries": 0, "HTTP": 0, "invocations": 1}
    path = Path("reports/next-nfl-checkpoint-contemporary-v1/FICTIONAL_CONTRAST_CHECKS.json")
    path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
