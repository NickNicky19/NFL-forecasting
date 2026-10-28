"""At most twenty hand-checked fictional chart cases; no NFL data or fits."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nfl_lab.next_checkpoint_chart_ppr import (WEIGHTS, NFL_FIELDS, ReturnAggregate,
    score_observed, score_component_expectations, event_credits, nflverse_components, label_observation)


def run():
    cases = []
    def check(name, expected, components=None, operation=None, error=False):
        try:
            result = operation() if operation else score_observed({**dict.fromkeys(WEIGHTS, 0), **(components or {})})
            actual = result.value if hasattr(result, "value") else result
            passed = not error and (actual == expected if not isinstance(expected, (float, int))
                                   else math.isclose(actual, expected, rel_tol=0, abs_tol=1e-10))
        except Exception as exc:
            actual = {"error": type(exc).__name__, "message": str(exc)}
            passed = error and isinstance(exc, ValueError)
        cases.append({"name": name, "expected": "ValueError" if error else expected,
                      "actual": actual, "passed": passed})
    z = dict.fromkeys(WEIGHTS, 0)
    identity = {"player_id": "FICTIONAL-P", "game_id": "FICTIONAL-G", "team": "AAA",
                "opponent": "BBB", "season": 2024, "week": 1, "season_type": "REG"}
    ref = {"sha256": "fictional-no-source-data", "qualification_id": "fictional-v1"}
    def bundle(updates=None):
        return nflverse_components({**{v: 0 for v in NFL_FIELDS.values()}, **(updates or {})}, source_ref=ref,
            broad_zero_contract={"version": "nflverse-chart-broad-zero-v1", "qualification_id": "fictional-v1",
            "present_group_complete": True, "return_superset_contains_all_three_classes": True,
            "recovery_superset_includes_lateral_td_recipients": True},
            event_components={k: {"value": 0, "qualification_id": "fictional-v1"}
                              for k in ("off_fum_rec_td", "kick_return_td", "punt_return_td", "fg_return_td")})
    def label(state, updates=None):
        return label_observation(bundle(updates), identity=identity, participation=state,
                                 participation_evidence=None if state == "unknown" else "fictional independent witness")["state"]
    check("ordinary production, fractional final score", 44.04,
          {"pass_yd": 251, "pass_td": 2, "pass_int": 1, "rush_yd": 30, "rush_td": 1,
           "rec": 5, "rec_yd": 80, "rec_td": 1, "fum_lost": 1})
    check("signed official yards", -.9, {"pass_yd": -10, "rush_yd": -3, "rec_yd": -2})
    ignored = [{"player_id": "P", "kind": k} for k in ("ordinary_fumble_recovery", "forced_fumble", "blocked_kick", "return_yards")]
    check("recovered fumble and unlisted bonuses score zero", 0, operation=lambda: score_observed(
        {**z, **event_credits(ignored, player_id="P", complete_components=["fum_lost"], qualification_id="F")["components"]}))
    lost = [{"player_id": "P", "kind": "fum_lost", "fumble_id": "same-credit", "phase": p} for p in ("offense", "special_teams")]
    check("unique lost fumble across phase duplicates", -1, operation=lambda: score_observed(
        {**z, **event_credits(lost, player_id="P", complete_components=["fum_lost"], qualification_id="F")["components"]}))
    check("passing conversion credit", 2, {"pass_2pt": 1})
    check("rushing conversion credit", 2, {"rush_2pt": 1})
    check("receiving conversion has no ordinary reception", 2, {"rec_2pt": 1})
    check("offensive recovery TD ignores old IDP exception", 6, {"off_fum_rec_td": 1, "idp_fum_rec": 1})
    check("kick return TD", 6, {"kick_return_td": 1})
    check("punt return TD", 6, {"punt_return_td": 1})
    check("field goal return TD", 6, {"fg_return_td": 1})
    overlap = [{"player_id": "P", "kind": k, "event_id": "one-touchdown"} for k in ("rush_td", "off_fum_rec_td")]
    check("same TD cannot overlap scorer classes", None, error=True, operation=lambda: event_credits(
        overlap, player_id="P", complete_components=["rush_td", "off_fum_rec_td"], qualification_id="F"))
    check("qualified three-class return aggregate used once", 12, operation=lambda: score_observed(
        {k:v for k,v in z.items() if not k.endswith("return_td")}, return_aggregate=ReturnAggregate(2, "F")))
    check("aggregate cannot overlap primitive return credits", None, error=True, operation=lambda: score_observed(
        z, return_aggregate=ReturnAggregate(1, "F")))
    check("missing field remains unsupported despite generic total", None,
          operation=lambda: score_observed({k:v for k,v in {**z, "fantasy_points_ppr": 100}.items() if k != "fum_lost"}))
    check("fractional component means give linear expectation", 1.9, operation=lambda: score_component_expectations(
        {**z, "pass_td": .5, "fum_lost": .1}, summary_kind="conditional_mean"))
    check("component medians rejected", None, error=True, operation=lambda: score_component_expectations(z, summary_kind="median"))
    check("played supported zero", "played_zero", operation=lambda: label("played"))
    check("known DNP distinct from zero", "known_dnp", operation=lambda: label("dnp"))
    check("unknown and played-missing remain distinct", ("unknown_participation", "played_missing"), operation=lambda:
          (label("unknown"), label("played", {"fumbles_lost_total": None})))
    assert len(cases) <= 20
    return {"state": "PASS" if all(c["passed"] for c in cases) else "FAIL", "fictional_cases": len(cases),
            "NFL_rows_read": 0, "predictive_fits": 0, "accuracy_experiments": 0, "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    result["scorer_sha256"] = hashlib.sha256((Path(__file__).resolve().parents[1] / "nfl_lab/next_checkpoint_chart_ppr.py").read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit("existing evidence must be preserved; choose a fresh receipt")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k != "cases"}, sort_keys=True))
    raise SystemExit(0 if result["state"] == "PASS" else 1)
