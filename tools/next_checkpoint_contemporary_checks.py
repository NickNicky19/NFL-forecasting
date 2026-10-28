"""Fictional cached-source admission, transport and scoring checks only."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import time
import resource

import numpy as np
import pandas as pd

from nfl_lab import next_checkpoint_contemporary as c


def main():
    start, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (20, 21))
    n = 2999
    query = pd.DataFrame({"season": 2026, "week": np.arange(n) % 6 + 1,
        "game_id": "FICTIONAL", "player_id": ["fixture" + str(i) for i in range(n)],
        "team": "A", "opponent": "B", "position": "RB",
        "kickoff_utc": pd.Timestamp("2026-09-10T00:00:00Z"), "cutoff_utc": pd.Timestamp("2026-09-10T00:00:00Z")})
    source = query.copy(); source["median"] = -3.; source["point"] = -3.; source["fallback"] = "stored_prior"
    spec = {"authority": "FICTIONAL", "authority_checks": {"state": "FROZEN"}, "forecast": "FICTIONAL",
        "target": "rush_yd", "value_column": "median", "fallback_column": "fallback", "functional": "yard_median",
        "target_column": False, "point_bit_identity": True, "training_cutoff_utc": "2026-09-01T00:00:00Z",
        "training_max_available_utc": "2026-01-01T00:00:00Z"}
    checks = []
    def vector(frame, authority=None):
        with patch.object(c, "document", return_value=authority or {"state": "FROZEN"}), patch.object(c, "read_frame", return_value=frame):
            return c.source_vector(spec, query)
    good = vector(source)
    assert good.cached_value.eq(-3).all() and good.admission.eq("ACCEPTED_CACHED").all()
    checks.append("signed_yards_and_stored_prior_retained")
    target = query.head(3).copy()
    v, why, _ = c.attach_values(target, good, [20., 20., 20.])
    assert np.array_equal(v, [-3., -3., -3.])
    changed = good.copy(); changed.loc[1, "team"] = "C"; changed = changed.loc[changed.player_id.ne("fixture2")]
    v, why, _ = c.attach_values(target, changed, [20., 21., 22.])
    assert np.array_equal(v, [-3., 21., 22.]) and len(why) == 3
    checks.append("context_and_missing_key_use_corresponding_aged_point_without_row_drop")
    bad = source.copy(); bad.loc[1, ["point", "median"]] = np.nan
    invalid = vector(bad)
    v, why, _ = c.attach_values(target, invalid, [20., 21., 22.])
    assert np.array_equal(v, [-3., 21., -3.])
    checks.append("unavailable_cached_value_preserves_original_case")
    bad = source.copy(); bad.loc[0, "point"] += 1
    try:
        vector(bad)
    except ValueError:
        checks.append("point_functional_bit_mismatch_is_fatal_not_relabelled")
    else:
        raise AssertionError("mismatched explicit original point accepted")
    try:
        vector(source, {"state": "WRONG"})
    except ValueError:
        checks.append("wrong_source_authority_is_fatal")
    else:
        raise AssertionError("wrong source authority accepted")
    clock = source.copy(); clock.loc[0, "cutoff_utc"] = pd.Timestamp("2026-08-01T00:00:00Z")
    assert vector(clock).admission.iloc[0] == "CACHED_TRAINING_AFTER_QUERY"
    checks.append("annual_training_cutoff_enforced")
    part = pd.DataFrame({"target": ["pass_yd"] * 3, "actual": [10., 0., 20.], "line": [10., 10., 10.]})
    metric = c.point_metrics(part, [10., 10., 30.])
    assert metric["forecast_ties"] == 2 and metric["actual_pushes"] == 1
    assert metric["side_decisive_rows"] == 1 and metric["correct_side_rows"] == 1
    assert metric["strict_close_rate"] == 1/3 and metric["inclusive_close_rate"] == 1.
    assert metric["correct_side_all_rate"] == 1/3 and metric["correct_side_decisive_rate"] == 1.
    checks.append("side_denominators_pushes_ties_and_strict_inclusive_precision")
    tie = c.point_metrics(part, part.line)
    assert tie["side_decisive_rows"] == 0 and tie["correct_side_decisive_rate"] is None
    checks.append("line_heuristic_has_no_decisive_side_accuracy")
    original = pd.DataFrame({"season": [2026, 2026], "week": [1, 1], "game_id": ["F1", "F2"],
        "player_id": ["p1", "p2"], "target": ["pass_yd", "pass_yd"], "book_id": [68, 68],
        "actual": [5., np.nan], "outcome_state": ["supported_played", "unknown_participation"]})
    forecasts = original[c.UNIT + ["book_id"]].copy(); forecasts["line"] = 4.; forecasts["F_probability"] = .5
    for arm in c.POINT_ARMS + ["FC_LAD", "H_LAD", "MODERN_FC_LAD", "MODERN_H_LAD"]:
        if arm != "OFFERED_LINE_HEURISTIC": forecasts[arm + "_point"] = 5.
    forecasts["MODERN_CDF_reason"] = "ACCEPTED_CACHED"; forecasts["RECENT_LEADER_reason"] = "ACCEPTED_CACHED"
    class Budget:
        def check(self):
            pass
    with patch.object(c, "read_frame", return_value=original):
        report, graded = c.score_forecasts({"inputs": {"original_matched": "FICTIONAL"}, "recent_leaders": {"pass_yd": {"recipe": "ANNUAL_CDF"}}}, forecasts, Budget())
    assert len(graded) == 2 and report["cells"][0]["rows"] == 1
    assert report["cells"][0]["metrics"][0]["MAE"] == 0.
    checks.append("unknown_participation_unscored_and_frozen_rows_preserved")
    directory = Path("reports/next-nfl-checkpoint-contemporary-v1"); directory.mkdir(parents=True, exist_ok=True)
    path = directory / "FICTIONAL_CHECKS.json"
    body = {"state": "FICTIONAL_CACHED_CONTEMPORARY_CHECKS_PASS", "checks": checks,
        "NFL_reads": 0, "fits": 0, "model_loads": 0, "law_queries": 0, "HTTP": 0, "invocations": 1,
        "CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - start,
        "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
