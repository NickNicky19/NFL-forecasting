"""Focused fictional cohort and numerical-fallback checks; zero NFL reads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from nfl_lab import next_checkpoint_lad as lad


def main():
    results = []
    try:
        with patch("numpy.linalg.solve", side_effect=np.linalg.LinAlgError("fictional failure")):
            lad.fit_lad(np.arange(5.)[:, None], np.arange(5.))
    except lad.SolverFailure:
        results.append("linear_algebra_failure_maps_to_solver_failure")
    else:
        raise AssertionError("linear-algebra failure did not become a declared fit failure")
    rows = []
    for player, book, state, actual, h in [("fixture1", 68, "supported_played", 12., 10.),
            ("fixture1", 69, "supported_played", 12., 11.),
            ("fixture2", 68, "unknown_participation", np.nan, 8.)]:
        rows.append({"season": 2024, "week": 1, "game_id": "FICTIONAL", "player_id": player, "target": "pass_yd",
                     "book_id": book, "primary_role": True, "source_collection_naive": "FICTIONAL", "source_row_number": book,
                     "line": 9., "actual": actual, "outcome_state": state, "F_point": 9., "FC_point": 10., "M_point": 9., "H_point": h})
    old = pd.DataFrame(rows)
    forecasts = old[lad.UNIT + ["book_id"]].copy()
    forecasts["FC_LAD_point"] = [10., 12., 10.]
    forecasts["H_LAD_point"] = [10., 12., 8.]
    forecasts["FC_LAD_reason"] = ["ORIGINAL_L2_FALLBACK_NUMERICAL_FIT_FAILURE", "ACCEPTED_LAD_CORRECTION", "ACCEPTED_LAD_CORRECTION"]
    forecasts["H_LAD_reason"] = forecasts.FC_LAD_reason
    class Budget:
        def check(self):
            pass
    with patch.object(lad, "member_frame", return_value=old):
        report, cohort = lad.score_forecasts({"inputs": {"matched_scores": "FICTIONAL"}}, forecasts, Budget())
    assert len(cohort) == 1 and cohort.book_id.iloc[0] == 68
    results.append("original_book_priority_preserved_despite_better_other_book_LAD")
    assert cohort.FC_LAD_point.iloc[0] == cohort.FC_point.iloc[0]
    assert cohort.H_LAD_point.iloc[0] == cohort.H_point.iloc[0]
    results.append("original_corresponding_L2_fallback_points_preserved")
    assert "fixture2" not in set(cohort.player_id)
    results.append("unknown_participation_never_zero_or_scored")
    metrics = {m["arm"]: m for m in report["cells"][0]["metrics"]}
    assert metrics["FC_LAD"]["corrected_rows"] == 0 and metrics["FC_LAD"]["model_only"]["rows"] == 0
    assert metrics["FC_LAD"]["paired_MAE_difference_vs_original_L2"] == 0.
    results.append("system_and_model_only_fallback_metrics_distinct")
    bad = forecasts.copy()
    bad.loc[bad.book_id.eq(68), "H_LAD_point"] = np.nan
    try:
        with patch.object(lad, "member_frame", return_value=old):
            lad.score_forecasts({"inputs": {"matched_scores": "FICTIONAL"}}, bad, Budget())
    except ValueError:
        results.append("missing_new_point_is_fatal_instead_of_switching_book")
    else:
        raise AssertionError("missing point changed the common cohort")
    body = {"state": "FICTIONAL_CONTRACT_CHECKS_PASS", "NFL_reads": 0, "NFL_fits": 0, "HTTP": 0,
            "fictional_failed_linear_solve_attempts": 1, "checks": results}
    path = Path("reports/next-nfl-checkpoint-lad-v1/FICTIONAL_CONTRACT_CHECKS.json")
    path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "state": body["state"]}))


if __name__ == "__main__":
    main()
