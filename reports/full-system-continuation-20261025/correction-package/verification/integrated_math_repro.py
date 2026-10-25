#!/usr/bin/env python3
"""Hermetic fictional math review; never runs a provider request or edits a website.

Run: python -B website_math_repro.py [--root PATH] [--expect-patches]
Default: run fresh child processes for both pinned website snapshots and emit JSON.
An exit of zero means the observed behavior matches the explicit audit assertions;
it does NOT mean the unpatched implementation is correct or qualified for release.
"""
import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_FICTIONAL_REPRO")


def install_network_guard():
    # The workspace has no requests dependency. This deliberately tiny substitute
    # permits module import only: all HTTP operations fail, including Session.get.
    module = types.ModuleType("requests")
    class Session:
        def __init__(self):
            self.headers = {}
        get = staticmethod(blocked)
        request = staticmethod(blocked)
    module.Session = Session
    module.sessions = types.SimpleNamespace(Session=Session)
    module.get = blocked
    module.request = blocked
    module.RequestException = RuntimeError
    sys.modules["requests"] = module
    socket.create_connection = blocked
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked


def fixture():
    prop = dict(key="rec", line=4.5, proj=6, adj=6, lean="over",
                source="model", line_from="dk", mf=1)
    game = dict(id="fictional-game", home="AAA", away="BBB",
                kickoff="2099-01-01T00:00:00Z", state="post", detail="Final",
                home_score=7, away_score=0, odds=None, ours=None)
    player = dict(id="fictional-player", name="Fictional Receiver", pos="WR",
                  team="AAA", opp="BBB", game_id=game["id"], proj_ppr=12,
                  matchup="neutral", injury=None, props=[prop])
    pick = dict(prop, player_id=player["id"], game_id=game["id"])
    archive = dict(season=2099, week=1, games=[game], players=[player],
                   picks={"over": [pick], "under": []})
    return archive, player, game


def evaluate(root, expect_patches=False):
    install_network_guard()
    sys.path[:0] = [str(root / "pull"), str(root / "tools")]
    import build
    import books
    import gamemodel
    import grade
    import matchup
    import scoring

    modern = hasattr(scoring, "component")
    result = {"root": str(root), "presence_aware": modern,
              "patched_expectations": expect_patches, "checks": 0}

    def check(condition, label):
        result["checks"] += 1
        if not condition:
            raise AssertionError(label)

    def props(raw, pos="WR"):
        return {p["key"]: p for p in build.player_props(
            {"pos": pos}, raw, [], 2099, "BBB", matchup.Matchups({}, {}))}

    # Independent all12 arithmetic oracle; no copying production formulas into
    # expected values at runtime. Includes net negative yardage and no aggregate
    # double count (a spurious rush_rec_yd value must not be used).
    raw = {key: 0 for key in set(scoring.PPR) | {"idp_fum_rec"}}
    raw.update(pass_yd=250, pass_td=2, pass_int=1, pass_cmp=20, pass_att=30,
               rush_yd=-2, rush_att=3, rec=4, rec_yd=51, rush_td=1, rec_td=1,
               fum_lost=1, rush_rec_yd=999)
    expected = dict(pass_yd=250, pass_td=2, pass_cmp=20, pass_att=30, pass_int=1,
                    rush_yd=-2, rush_att=3, rec=4, rec_yd=51, rush_rec_yd=49,
                    anytime_td=2, fpts=35.9)
    observed = {key: scoring.stat_value(key, raw) for key in scoring.CATEGORIES}
    check(observed == expected, "all12 arithmetic")
    check(scoring.fantasy_points(raw, "WR", half=True) == 33.9, "half PPR")
    check(scoring.ppr_points({"pass_yd": -5}) == -0.2, "signed passing yards")
    check(scoring.ppr_points({"rush_yd": -2, "fum_lost": 1}) == -2.2, "negative PPR")
    check(scoring.ppr_points({"fum_rec_td": 1}) == 6, "offensive fumble-return TD")
    check(scoring.ppr_points({"fum_rec_td": 1, "idp_fum_rec": 1}) == 0, "defensive fumble exclusion")
    check(scoring.ppr_points({"st_td": 1, "st_fum_rec": 1, "st_ff": 1, "idp_blk_kick": 1}) == 10,
          "special teams PPR exceptions")
    check(scoring.ppr_points({"pass_2pt": 1, "rush_2pt": 1, "rec_2pt": 1}) == 6, "two point conversions")
    check(scoring.ppr_points({"pts_ppr": 999}) == 0, "provider fantasy total is not a weighted component")
    check(scoring.fantasy_points({"fgm_50p": 2, "fgm_60p": 1}, "K") == 11, "50-plus inclusive split")
    check(scoring.fantasy_points({}, "DEF") == 10, "legacy missing defense allows-shutout assumption")
    result["all12"] = observed

    history = {1: {"fictional-peer": {"opp": "BBB", "stats": {"gp": 1, "rec_yd": 100}}},
               2: {"fictional-peer": {"opp": "CCC", "stats": {"gp": 1, "rec_yd": 50}}}}
    model = matchup.Matchups(history, {"fictional-peer": "WR"})
    check(model.factor("BBB", "WR", "rec_yd", 60) == (1.111, 1), "independent shrunk matchup factor")
    for adjusted, expected_lean in ((54, None), (55, "over"), (45, "under")):
        candidate = {"key": "rec_yd", "line": adjusted + .5, "adj": adjusted, "proj": 40, "values": []}
        build.apply_book([candidate], {"rec_yd": {"open": 50, "close": 50}})
        check(candidate["lean"] == expected_lean, "adjusted projection and strict lean boundary")

    # Receiving yardage is a direct field, independent of targets/receptions.
    check(scoring.stat_value("rec_yd", {"rec": 4, "rec_tgt": 8, "rec_yd": 51}) == 51,
          "receiving yards must not be targets or receptions")
    check(props({"rec_yd": 0, "pts_ppr": 1})["rec_yd"]["proj"] == 0, "explicit projection zero")
    missing = props({"pts_ppr": 15, "rec": 4})
    combined = scoring.stat_value("rush_rec_yd", {"rush_yd": 30}, **({"projection": True} if modern else {}))
    check(("rec_yd" not in missing) if modern else missing["rec_yd"]["proj"] == 0, "missing receiving field")
    check(combined is None if modern else combined == 30, "missing combined component")
    result["missing_projection"] = {"receiving_prop": missing.get("rec_yd"), "partial_combined": combined}
    with patch.object(build.sources, "week_projections", return_value=[
            {"player_id": "fictional-stat-only", "stats": {"rec_yd": 60}}]):
        normalized = build.projections(2099, 1)
    check(("fictional-stat-only" in normalized) == modern, "independent statistic without PPR total")

    trimmed = build.trim_stats([{"player_id": "fictional-player", "team": "AAA", "opponent": "BBB",
                                "stats": {"gp": 1, "rec": 0, "rec_yd": None}}],
                               **({"source_context": {"adapter": "sleeper-week-stats-v1", "season": 2099, "week": 1}}
                                  if modern else {}))["fictional-player"]
    check(("rec" in trimmed["stats"]) == modern, "retain reported zero")
    check(("rec_yd" in trimmed["stats"]) == modern, "retain explicit null")
    unknown = grade._prop_result({"key": "rec_yd", "line": 30.5}, "under", trimmed)
    check(unknown == ((None, "unresolved") if modern else (0, "hit")), "explicit null grade")
    result["null_actual"] = unknown
    invalids = {}
    for label, value in (("negative", -1), ("boolean", True), ("fractional", 1.5)):
        answer = grade._prop_result({"key": "rec", "line": .5}, "over",
                                    {"stats": {"gp": 1, "rec": value}})
        check(answer == (None, "unresolved") if modern else answer[0] == value,
              "invalid actual count: " + label)
        invalids[label] = answer
    result["invalid_actual_counts"] = invalids
    check(grade._prop_result({"key": "pass_yd", "line": -4.5}, "under",
                              {"stats": {"gp": 1, "pass_yd": -5}}) == (-5, "hit"), "negative actual passing")

    # A remaining Phase2 domain gap: count expectations can be fractional, but
    # never negative. Valid signed yards and negative fantasy points stay valid.
    negative_projection = props({"rec": -1, "rec_yd": 50, "pts_ppr": 5})
    check(("rec" not in negative_projection) if expect_patches and modern
          else negative_projection["rec"]["proj"] == -1, "negative projected receptions")
    result["negative_count_projection"] = negative_projection.get("rec")
    if modern:
        for key in ("pass_cmp", "pass_att", "pass_td", "pass_int", "rush_att", "rec"):
            answer = scoring.component({key: -1}, key, projection=True)
            check(answer["value"] is None if expect_patches else answer["value"] == -1,
                  "negative projection domain " + key)
        check(scoring.component({"rec": 1.25}, "rec", projection=True)["value"] == 1.25,
              "fractional nonnegative expectation")
        check(scoring.component({"rec_yd": -1}, "rec_yd", projection=True)["value"] == -1,
              "signed yard expectation")

    # Full field-goal normalization path, not a standalone rollup mock.
    rows = [{"player_id": "home-qb", "stats": {"pts_ppr": 20, "pass_td": 2}},
            {"player_id": "home-k", "stats": {"pts_ppr": 0, "fgm": 3, "xpm": 2}},
            {"player_id": "away-qb", "stats": {"pts_ppr": 24, "pass_td": 3}},
            {"player_id": "away-k", "stats": {"pts_ppr": 0, "fgm": 1, "xpm": 3}}]
    teams = {"home-qb": ("QB", "AAA"), "home-k": ("K", "AAA"),
             "away-qb": ("QB", "BBB"), "away-k": ("K", "BBB")}
    games = [{"id": "fictional-game", "home": "AAA", "away": "BBB", "odds": {"spread": 1, "total": 44}}]
    with patch.object(build.sources, "week_projections", return_value=rows):
        normalized = build.projections(2099, 1)
    direct = gamemodel.finish(games, gamemodel.rollup({r["player_id"]: r["stats"] for r in rows}, teams), 22)
    actual = gamemodel.finish(games, gamemodel.rollup(normalized, teams), 22)
    check(direct["fictional-game"]["spread"] == 1.0, "independent game oracle")
    check(actual["fictional-game"]["spread"] == (1.0 if expect_patches else 8.8), "field goals retained")
    check(actual["fictional-game"]["lean_spread"] == (None if expect_patches else "BBB"), "field goals change lean")
    result["field_goal_loss"] = {"direct": direct, "after_normalization": actual}

    # Classic grading joins solely by player ID, despite explicit contradictory
    # team/opponent data. Stronger Phase2 scorecard supplies a negative control.
    archive, player, game = fixture()
    wrong = {"team": "CCC", "opp": "DDD", "stats": {"gp": 1, "rec": 6}}
    record = grade.grade_week(archive, {player["id"]: wrong}, {game["id"]})
    check(record["top_over"]["unresolved" if expect_patches else "hit"] == 1, "wrong stats identity")
    check(record["leans"]["unresolved" if expect_patches else "hit"] == 1, "wrong identity lean")
    result["wrong_identity_classic"] = record["top_over"]["picks"]
    ppr_archive = copy.deepcopy(archive)
    ppr_archive["players"][0]["props"].append(dict(key="fpts", line=12.5, adj=12, proj=12,
                                                 source="model", line_from="ours", lean=None))
    ppr_grade = grade.grade_week(ppr_archive, {player["id"]: wrong}, {game["id"]})
    check(ppr_grade["ppr"]["n"] == (0 if expect_patches else 1), "wrong stats excluded from PPR MAE")
    good = {"team": "AAA", "opp": "BBB", "stats": {"gp": 1, "rec": 6}}
    good_record = grade.grade_week(archive, {player["id"]: good}, {game["id"]})
    check(good_record["top_over"]["hit"] == 1, "valid same game control")
    mismatch = copy.deepcopy(archive)
    mismatch["picks"]["over"][0]["game_id"] = "fictional-other-game"
    cross = grade.grade_week(mismatch, {player["id"]: good}, {game["id"], "fictional-other-game"})
    check(cross["top_over"]["unresolved" if expect_patches else "hit"] == 1, "Top pick/player game join")
    result["wrong_top_game"] = cross["top_over"]["picks"]
    # Missing stats are unknown; explicit sourced DNP is not a loss; repeated
    # selected cohorts must not be added as independent outcomes.
    check(grade.grade_week(archive, {}, {game["id"]})["top_over"]["unresolved"] == 1, "missing player")
    dnp = {"participation_status": "dnp", "participation_source": "FICTIONAL_ONLY"}
    check(grade.grade_week(archive, {player["id"]: dnp}, {game["id"]})["top_over"]["dnp"] == 1, "explicit DNP")
    check(grade.grade_week(archive, {player["id"]: good}, set())["top_over"]["n_decided"] == 0,
          "pending final excluded")
    check(grade.result("over", 4, 4) == grade.result("under", 4, 4) == "push", "statistical equality")
    check(grade.tally(["hit", "miss", "push", "dnp", "unresolved"])["pct"] == 50.0,
          "rate denominator")
    result["combined_tally"] = grade.combine_tallies([grade.tally(["hit"]), grade.tally(["miss", "push"])])
    check(result["combined_tally"]["pct"] == 50.0, "combined hit-rate weighting")

    # Exercise actual build.run -> load_games -> grade_all with a cancelled post
    # response. Everything outside that path is a fictional injected dependency;
    # all output is under a newly allocated /tmp directory.
    response = {"events": [{"id": game["id"], "date": "2098-12-31T00:00:00Z", "competitions": [{
        "status": {"type": {"state": "post", "shortDetail": "Canceled", "completed": False}},
        "competitors": [{"homeAway": side, "score": "0", "team": {"abbreviation": team}}
                        for side, team in (("home", "AAA"), ("away", "BBB"))]}]}]}
    with tempfile.TemporaryDirectory(prefix="website-math-fictional-") as temporary:
        temp = Path(temporary)
        replacements = dict(OUT=temp / "out", ARCHIVE=temp / "out/archive", WEEKS=temp / "out/weeks", CACHE=temp / "cache",
            now_utc=lambda: __import__("datetime").datetime(2100, 1, 1, tzinfo=__import__("datetime").timezone.utc),
            load_players=lambda: ({}, {}), projections=lambda *a: {}, load_stats_through=lambda *a, **k: {},
            week_stats=lambda *a, **k: {player["id"]: good},
            point_in_time=lambda *a: ({}, {}, 0), assemble=lambda *a: ([dict(copy.deepcopy(player), matchup={"label": "neutral"})], copy.deepcopy(archive["picks"])),
            kdef_entries=lambda *a: [], league_points_per_team=lambda *a: 22, future_weeks=lambda *a: {},
            season_schedule=lambda *a: {}, depth_charts=lambda *a: {})
        with patch.multiple(build, **replacements), patch.object(build.sources, "nfl_state", return_value={"season": "2099", "week": 1, "season_type": "regular"}), \
             patch.object(build.sources, "scoreboard", return_value=response), \
             patch.object(books, "week_lines", return_value={}), patch.object(books, "sleeper_lines", return_value={}), \
             patch.object(books, "game_odds", return_value=None), patch.object(build.news, "injury_report", return_value={}), \
             patch.object(build.news, "update_timeline", return_value={}), contextlib.redirect_stdout(io.StringIO()):
            build.run()
        classic = json.loads((temp / "out/track_record.json").read_text())["weeks"][0]
    check(classic["top_over"]["n_decided"] == (0 if expect_patches else 1), "cancelled post must not be final")
    result["cancelled_post_classic"] = {"top_over": classic["top_over"], "games_complete": classic["games_complete"]}
    if expect_patches:
        from datetime import datetime, timezone
        with patch.object(build, "now_utc", return_value=datetime(2100, 1, 1, tzinfo=timezone.utc)):
            check(build.confirmed_final(dict(game, completed=True)), "completed past game control")
            check(not build.confirmed_final(dict(game, completed=False)), "canceled final guard")
            check(not build.confirmed_final(dict(game, completed=True, kickoff="2101-01-01T00:00:00Z")),
                  "future completed game guard")
            check(not build.confirmed_final(dict(game, completed=True, kickoff="not-a-date")), "invalid kickoff guard")

    if modern:
        import scorecard
        row = {"season": 2099, "week": 1, "player_id": player["id"], "game_id": game["id"],
               "team": "AAA", "category": "rec", "kickoff": game["kickoff"]}
        binding = scorecard._outcome_identity({"games": [game]}, row, wrong)
        check(binding["outcome_identity_status"] == "quarantined", "Phase2 scorecard identity control")
        result["phase2_scorecard_identity"] = binding
        check(scorecard.latest_outcomes([{"schema_version": "forecast-outcomes-v1", "mode": "replay",
                  "collected_at": "2100-01-01T00:00:00Z", "rows": []}]) == {}, "replay excluded by default")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--expect-patches", action="store_true")
    args = parser.parse_args()
    if args.root:
        result = evaluate(args.root.resolve(), args.expect_patches)
    else:
        result = {}
        for label in ("website-audit", "website-phase2"):
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--root", str(AUDIT / label)]
            child = subprocess.run(command, text=True, capture_output=True)
            if child.returncode:
                sys.stderr.write(child.stderr)
                child.check_returncode()
            result[label] = json.loads(child.stdout)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
