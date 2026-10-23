"""Pregame hash bindings to read-only website points; no raw-feed exports.

Only new lab forecasts may acquire a comparator. Numeric website/provider
values stay in the ignored source cache. Later grading must recover the same
immutable upstream bytes; an unavailable source is an abstention.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .data import TARGETS, _download
from .evaluation import paired_week_interval, summarize
from .scoring import SCORING_VERSION
from .state import digest, now_utc, records, resolved_outcomes, save, utc, writer

REPO = "NickNicky19/nicks-expert-nfl-picks"
COUNTS = {"pass_td", "pass_cmp", "pass_att", "pass_int", "rush_att", "rec"}
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
ENGINE_BLOBS = {
    "pull/build.py": "e691985174387ed0dc6ecdda1f35b55c1012499c",
    "pull/matchup.py": "3753d8e252513785dd1b9cf573f7d2616462945e",
    "pull/scoring.py": "0c532e695e7abefc2203f95344218ffc07bb4c0f",
    "pull/books.py": "406c24755aa9823311c01e3116662845854cf393",
    "pull/gamemodel.py": "9c94d3889402c702e6a7ad1d239ea8f4d22b2cdf",
    "pull/sources.py": "99b9029acf9a046a590589f001d99b242cc5576f",
    "pull/news.py": "b29edaa0cfe1df29c3ee4741d63225ab43fa8249",
}


def _json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate website JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("nonfinite website JSON constant")

    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


def _read(directory, name, url, policy, downloader, on_read=None):
    receipt = downloader(directory, name, url)
    path=directory/name
    if path.stat().st_size > policy["max_json_bytes"]:
        raise ValueError("website JSON exceeds acceptance limit")
    body = path.read_bytes()
    if on_read is not None:on_read(len(body))
    if receipt.get("sha256") != hashlib.sha256(body).hexdigest():
        raise ValueError("website source checksum mismatch")
    return _json(body), receipt, body


def _policy(root):
    policy = json.loads((Path(root) / "config/website-baseline-v1.json").read_text())
    _validate_policy(policy)
    return policy


def _validate_policy(policy):
    if policy["repo"] != REPO or policy["branch"] != "main":
        raise ValueError("unsupported website repository")
    if policy["board_path"] != "output/data/week.json" or policy["meta_path"] != "output/data/meta.json":
        raise ValueError("unsupported website source paths")
    if not 0 < policy["max_build_age_minutes"] <= 120:
        raise ValueError("unsupported website freshness policy")
    if policy["engine_blobs"] != ENGINE_BLOBS:
        raise ValueError("website engine policy differs from registered v1")
    if type(policy["max_json_bytes"]) is not int or not 0 < policy["max_json_bytes"] <= 5*1024*1024:
        raise ValueError("unsupported website JSON acceptance budget")


def _snapshot(cache, policy, commit, tree_sha, downloader, on_read=None):
    _validate_policy(policy)
    if not HEX40.fullmatch(commit) or not HEX40.fullmatch(tree_sha):
        raise ValueError("invalid immutable website commit/tree")
    directory = Path(cache) / "raw/website_snapshots" / commit
    directory.mkdir(parents=True, exist_ok=True)
    tree, tr, _ = _read(directory, "tree.json",
        f"https://api.github.com/repos/{REPO}/git/trees/{tree_sha}?recursive=1", policy, downloader, on_read)
    if tree.get("sha") != tree_sha or tree.get("truncated") is not False:
        raise ValueError("incomplete website source tree")
    paths = {}
    for entry in tree["tree"]:
        if entry["path"] in paths:
            raise ValueError("duplicate website tree path")
        paths[entry["path"]] = entry
    for path, expected in policy["engine_blobs"].items():
        entry = paths.get(path, {})
        if entry.get("type") != "blob" or entry.get("sha") != expected:
            raise ValueError("website engine differs from pinned version")
    docs = {}; receipts = {"tree": tr}; blob_ids = {}
    for label, path in [("board", policy["board_path"]), ("meta", policy["meta_path"])]:
        entry = paths.get(path, {})
        if entry.get("type") != "blob" or entry.get("mode") not in {"100644", "100755"}:
            raise ValueError("website data is absent or not a regular blob")
        doc, receipt, body = _read(directory, label + ".json",
            f"https://raw.githubusercontent.com/{REPO}/{commit}/{path}", policy, downloader, on_read)
        git_blob = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
        if git_blob != entry["sha"]:
            raise ValueError("website blob differs from pinned tree")
        docs[label] = doc; receipts[label] = receipt; blob_ids[label] = git_blob
    for key in ["generated_at", "season", "week"]:
        if docs["board"].get(key) != docs["meta"].get(key):
            raise ValueError("website board/meta mismatch")
    return docs["board"], {"commit": commit, "tree_sha": tree_sha, "blob_ids": blob_ids,
        "body_sha256": {k: v["sha256"] for k, v in receipts.items()},
        "source_receipts": receipts, "policy": policy, "policy_sha256": digest(policy)}


def _finite(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _lab_scope(row, header):
    return (row.get("target") in TARGETS and row.get("period") == "full_game"
        and type(row.get("season")) is int and type(row.get("week")) is int
        and (row["season"], row["week"]) == (header["season"], header["week"])
        and row.get("scoring_id") == (SCORING_VERSION if row["target"] == "fantasy_ppr" else "nfl-full-game-v1"))


def _point_matches_lab(point, row):
    return all(point.get(k) == row.get(k) for k in ["game_id", "sleeper_id", "target", "team", "opponent", "position"]) and utc(point["kickoff_utc"]) == utc(row["kickoff_utc"])


def _points(board):
    """Private numeric index; literal published fields, no probability invention."""
    from .live import TEAMS
    games = {}; points = {}; player_ids = set()
    for game in board["games"]:
        gid = str(game["id"])
        if gid in games:
            raise ValueError("duplicate website game")
        games[gid] = game
    for player in board["players"]:
        sid = str(player["id"])
        if sid in player_ids:
            raise ValueError("duplicate website player")
        player_ids.add(sid)
        if player.get("pos") not in {"QB", "RB", "FB", "WR", "TE"}:
            continue
        game = games[str(player["game_id"])]; team = TEAMS.get(player["team"], player["team"])
        home = TEAMS.get(game["home"], game["home"]); away = TEAMS.get(game["away"], game["away"])
        if team not in {home, away}:
            raise ValueError("website player/team/game mismatch")
        if player.get("late") or game.get("state") != "pre":
            continue
        categories = set()
        for prop in player.get("props", []):
            target = "fantasy_ppr" if prop["key"] == "fpts" else prop["key"]
            if target in categories:
                raise ValueError("duplicate website category")
            categories.add(target)
            if target not in TARGETS:
                continue
            fields = [("raw_sleeper", "proj"), ("pinned_website", "adj")]
            if target == "anytime_td":
                fields = [("pinned_website", "td_chance")] if _finite(prop.get("proj")) and prop["proj"] >= 0 else []
            for method, field in fields:
                value = prop.get(field)
                if value is None:
                    continue
                if not _finite(value) or (target in COUNTS and value < 0) or (target == "anytime_td" and not 0 <= value <= 1):
                    raise ValueError("invalid website forecast support")
                gid = "espn:" + str(game["id"])
                points[(gid, sid, target, method)] = {
                    "game_id": gid, "sleeper_id": sid, "target": target, "method": method,
                    "team": team, "opponent": away if team == home else home, "home": home, "away": away, "position": player["pos"],
                    "kickoff_utc": utc(game["kickoff"]).isoformat(), "field": field,
                    "source_prop_sha256": digest(prop), "value": float(value),
                    "fallback": "website_historical_average" if method == "pinned_website" and field == "adj" and prop.get("proj") is None else ""}
    return points


def prepare_website_snapshot(root, cache, games, season, week, *, clock=now_utc, downloader=_download):
    """Call before the lab feature cutoff. The returned private index is RAM only."""
    policy = _policy(root); started = clock()
    directory = Path(cache) / "raw/website_branches" / started.date().isoformat()
    directory.mkdir(parents=True, exist_ok=True)
    branch, receipt, _ = _read(directory, "main.json",
        f"https://api.github.com/repos/{REPO}/branches/main", policy, downloader)
    commit = branch["commit"]["sha"]; tree_sha = branch["commit"]["commit"]["tree"]["sha"]
    board, header = _snapshot(cache, policy, commit, tree_sha, downloader)
    observed = clock(); generated = utc(board["generated_at"])
    if type(board["season"]) is not int or type(board["week"]) is not int or (board["season"], board["week"]) != (season, week):
        raise ValueError("website period mismatch")
    age = (observed - generated).total_seconds() / 60
    header.update(observed_at=observed.isoformat(), generated_at=board["generated_at"],
                  season=season, week=week, branch_receipt=receipt)
    if any(utc(r["retrieved_utc"]) > observed for r in [receipt, *header["source_receipts"].values()]):
        raise ValueError("website receipt clock is in the future")
    report = {"state": "READY", "commit": commit, "observed_at": observed.isoformat(),
              "generated_at": board["generated_at"], "build_age_minutes": age}
    if age < 0 or age > policy["max_build_age_minutes"]:
        return {"report": {**report, "state": "STALE_OR_FUTURE_BOARD"}, "header": header, "_private_points": {}}
    expected = {g["game_id"]: g for g in games}
    points = _points(board); accepted = {}; excluded = Counter()
    for key, point in points.items():
        game = expected.get(point["game_id"])
        if not game or (point["home"], point["away"]) != (game["home"], game["away"]) or point["team"] == point["opponent"] or utc(point["kickoff_utc"]) != utc(game["kickoff_utc"]):
            excluded["independent_schedule_mismatch"] += 1; continue
        if utc(point["kickoff_utc"]) <= observed:
            excluded["game_started"] += 1; continue
        accepted[key] = point
    return {"report": {**report, "offered_points": len(points), "qualified_points": len(accepted), "exclusions": dict(excluded)},
            "header": header, "_private_points": accepted}


def capture_website_bindings(state, prepared, lab_batch, *, clock=now_utc):
    """Bind only this intake's new forecasts; a later retry cannot fill gaps."""
    if prepared["report"]["state"] != "READY":
        return prepared["report"]
    if not lab_batch:
        return {**prepared["report"], "state": "NO_NEW_LAB_FORECASTS_NO_BASELINE_BACKFILL", "bound": 0}
    batches = [b for b in records(state, "forecasts") if digest(b) == lab_batch]
    if len(batches) != 1:
        raise ValueError("website binding requires exactly one new immutable lab batch")
    header = prepared["header"]; points = prepared["_private_points"]; bindings = []; excluded = Counter()
    for row in batches[0]["rows"]:
        from .recorded_research import FUNCTIONAL
        if row.get("prediction_functional")==FUNCTIONAL:
            excluded["research_point_comparator_binding_not_implemented"] += 1; continue
        if row.get("code_integrity") != "pre_post_source_digest_required":
            raise ValueError("unqualified lab code cannot acquire website baseline")
        if not _lab_scope(row, header):
            excluded["unsupported_lab_period_season_week_or_scoring"] += 1; continue
        if utc(row["feature_cutoff_utc"]) > utc(row["issued_at"]):
            excluded["invalid_lab_cutoff_after_issuance"] += 1; continue
        if utc(header["observed_at"]) > utc(row["feature_cutoff_utc"]) or utc(header["generated_at"]) > utc(row["feature_cutoff_utc"]):
            excluded["website_observed_after_original_lab_cutoff"] += 1; continue
        if (utc(row["feature_cutoff_utc"]) - utc(header["generated_at"])).total_seconds() > header["policy"]["max_build_age_minutes"] * 60:
            excluded["website_stale_at_original_lab_cutoff"] += 1; continue
        for method in ["raw_sleeper", "pinned_website"]:
            point = points.get((row["game_id"], row["sleeper_id"], row["target"], method))
            if not point:
                excluded["website_point_unavailable"] += 1; continue
            if not _point_matches_lab(point, row):
                excluded["lab_source_identity_mismatch"] += 1; continue
            bindings.append({k: v for k, v in point.items() if k != "value"} | {
                "value_sha256": digest({"target": point["target"], "method": method, "value": point["value"]}),
                "lab_forecast_sha256": digest(row), "lab_player_id": row["player_id"],
                "lab_model_id": row["model_id"], "lab_issued_at": row["issued_at"],
                "lab_feature_cutoff_utc": row["feature_cutoff_utc"], "season": row["season"], "week": row["week"],
                "period": row["period"], "scoring_id": row["scoring_id"]})
    with writer(state):
        if any(b["lab_batch"] == lab_batch for b in records(state, "website_bindings")):
            return {"state": "ALREADY_BOUND", "bound": 0}
        persisted = clock()
        if persisted < utc(batches[0]["persist_started_at"]):
            raise ValueError("website persistence clock precedes original lab persistence")
        surviving = [b for b in bindings if utc(b["kickoff_utc"]) > persisted]
        excluded["missed_during_calculation"] += len(bindings) - len(surviving)
        if not surviving:
            return {**prepared["report"], "state": "NO_QUALIFIED_COMMON_ROWS", "bound": 0, "binding_exclusions": dict(excluded)}
        key = save(state, "website_bindings", {"schema_version": "website-point-bindings-v1", "lab_batch": lab_batch,
            "header": header, "persist_started_at": persisted.isoformat(), "rows": surviving,
            "scope": "Source observation precedes original lab cutoff; numeric values must be recovered from immutable upstream blob."})
        completed = clock()
        save(state, "website_persistence", {"snapshot": key, "completed_at": completed.isoformat(),
            "late_games": sorted({r["game_id"] for r in surviving if utc(r["kickoff_utc"]) <= completed})})
    return {**prepared["report"], "snapshot": key, "bound": len(surviving), "binding_exclusions": dict(excluded)}


def record_website_publication(state, commit, observed):
    prior = {p["snapshot"] for p in records(state, "website_publication")}; count = 0
    for snapshot in records(state, "website_bindings"):
        key = digest(snapshot)
        if key in prior:
            continue
        save(state, "website_publication", {"snapshot": key, "commit": commit,
            "observed_remote_readback_at": observed.isoformat(),
            "timely_rows": sum(utc(r["kickoff_utc"]) > observed for r in snapshot["rows"]),
            "scope": "Remote readback of hash bindings, not a copy of numeric website/provider forecasts."})
        count += 1
    return count


def score_saved_website(state, cache, *, downloader=_download):
    """Grade recovered points on identical lab rows; export aggregate results only."""
    snapshots = list(records(state, "website_bindings"))
    if not snapshots:
        return {"state": "NO_QUALIFIED_BASELINES", "paired_rows": 0, "promoted": []}
    persistence = {p["snapshot"]: p for p in records(state, "website_persistence")}
    publication = {p["snapshot"]: p for p in records(state, "website_publication")}
    lab_persist = {p["batch"]: p for p in records(state, "persistence")}
    lab_public = {p["batch"]: p for p in records(state, "publication")}
    needed = {s["lab_batch"] for s in snapshots}
    lab = {digest(batch): {digest(row): row for row in batch["rows"]} for batch in records(state, "forecasts") if digest(batch) in needed}
    outcomes = resolved_outcomes(state); coverage = Counter(); rows = []; limits = []
    recovered_points = {}; failed_sources = {}; attempted_sources = set(); started = time.monotonic(); processed_bytes = 0
    def charge_source_bytes(size):
        nonlocal processed_bytes
        processed_bytes += size
    for snapshot in snapshots:
        header = snapshot["header"]; key = digest(snapshot)
        if key not in persistence or key not in publication or snapshot["lab_batch"] not in lab_persist or snapshot["lab_batch"] not in lab_public:
            coverage["unpublished_or_unpersisted"] += len(snapshot["rows"]); continue
        if not any(outcomes.get((b["lab_player_id"], b["game_id"], b["target"]), {}).get("actual") is not None for b in snapshot["rows"]):
            for b in snapshot["rows"]:
                coverage[outcomes.get((b["lab_player_id"], b["game_id"], b["target"]), {}).get("state", "pending")] += 1
            continue
        source_key = (header["commit"], header["tree_sha"], header["policy_sha256"])
        if source_key in failed_sources:
            coverage["immutable_upstream_unavailable_or_invalid"] += len(snapshot["rows"])
            limits.append(failed_sources[source_key]); continue
        if source_key not in attempted_sources and (len(attempted_sources) >= 128 or time.monotonic()-started >= 120 or processed_bytes >= 497*1024*1024):
            coverage["rehydration_budget_pending"] += len(snapshot["rows"]); continue
        attempted_sources.add(source_key)
        try:
            policy = header["policy"]
            if policy["repo"] != REPO or digest(policy) != header["policy_sha256"]:
                raise ValueError("website policy binding mismatch")
            if source_key not in recovered_points:
                board, recovered = _snapshot(cache, policy, header["commit"], header["tree_sha"], downloader, charge_source_bytes)
                recovered_points[source_key] = (recovered, _points(board), (board["season"], board["week"], board["generated_at"]))
            recovered, points, recovered_period = recovered_points[source_key]
            if recovered["body_sha256"] != header["body_sha256"] or recovered["blob_ids"] != header["blob_ids"]:
                raise ValueError("website immutable bytes differ from pregame binding")
            if recovered_period != (header["season"], header["week"], header["generated_at"]):
                raise ValueError("website recovered period or generation clock mismatch")
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            coverage["immutable_upstream_unavailable_or_invalid"] += len(snapshot["rows"])
            error = type(exc).__name__ + ": " + str(exc)[:200]
            if source_key not in recovered_points:
                failed_sources[source_key] = error
            limits.append(error); continue
        for binding in snapshot["rows"]:
            row = lab.get(snapshot["lab_batch"], {}).get(binding["lab_forecast_sha256"])
            if not row:
                coverage["lab_row_unavailable"] += 1; continue
            if not _lab_scope(row, header) or row.get("code_integrity") != "pre_post_source_digest_required" or any(binding.get(k) != row.get(k) for k in ["season", "week", "period", "scoring_id", "game_id", "sleeper_id", "target", "team", "opponent", "position"]):
                coverage["unsupported_lab_period_season_week_or_scoring"] += 1; continue
            kickoff = utc(row["kickoff_utc"])
            clocks = [persistence[key]["completed_at"], publication[key]["observed_remote_readback_at"],
                      lab_persist[snapshot["lab_batch"]]["completed_at"], lab_public[snapshot["lab_batch"]]["observed_remote_readback_at"]]
            if (any(utc(t) >= kickoff for t in clocks) or utc(header["observed_at"]) > utc(row["feature_cutoff_utc"])
                or utc(row["feature_cutoff_utc"]) > utc(row["issued_at"])
                or utc(persistence[key]["completed_at"]) < utc(lab_persist[snapshot["lab_batch"]]["completed_at"])
                or (utc(row["feature_cutoff_utc"]) - utc(header["generated_at"])).total_seconds() > policy["max_build_age_minutes"]*60):
                coverage["late_or_after_original_cutoff"] += 1; continue
            point = points.get((binding["game_id"], binding["sleeper_id"], binding["target"], binding["method"]))
            if not point or not _point_matches_lab(point, row) or point["source_prop_sha256"] != binding["source_prop_sha256"] or digest({"target": point["target"], "method": point["method"], "value": point["value"]}) != binding["value_sha256"]:
                coverage["point_binding_mismatch"] += 1; continue
            outcome = outcomes.get((row["player_id"], row["game_id"], row["target"]))
            state_name = outcome["state"] if outcome else "pending"
            coverage[state_name] += 1
            if not outcome or state_name not in {"played", "played_corrected"} or outcome["actual"] is None:
                continue
            binary = row["target"] == "anytime_td"
            common = {**row, "actual": outcome["actual"], "participation_state": "played", "scale": 1. if binary else np.nan,
                      "family": "bernoulli" if binary else None, "p_participation": np.nan, "baseline_method": binding["method"],
                      "lab_model_id": row["model_id"]}
            rows.extend([{**common, "method": "lab", "mean": row["mean"]},
                         {**common, "method": binding["method"], "mean": point["value"], "fallback": point["fallback"]}])
    summaries = []; paired = []
    if rows:
        frame = pd.DataFrame(rows)
        for (target, model, baseline), group in frame.groupby(["target", "lab_model_id", "baseline_method"]):
            for method, g in group.groupby("method"):
                summaries.append({"target": target, "lab_model_id": model, "baseline": baseline,
                                  "method": method, **summarize(g)})
            for cluster in ["week", "game"]:
                interval = paired_week_interval(group, baseline, "lab", cluster=cluster, family_size=240)
                paired.append({"target": target, "lab_model_id": model, "baseline": baseline, **interval})
        private = Path(cache).parent / "runs/website-comparison"
        private.mkdir(parents=True, exist_ok=True)
        row_hash = digest([{k: r[k] for k in ["lab_model_id", "baseline_method", "method", "player_id", "game_id", "target", "actual", "mean"]} for r in rows])
        destination = private / (row_hash + ".parquet")
        if not destination.exists():
            buffer = io.BytesIO(); frame.to_parquet(buffer, index=False); body = buffer.getvalue()
            if sum(p.stat().st_size for p in private.glob("*.parquet")) + len(body) > 256*1024*1024:
                limits.append("Private comparison row retention cap reached; no evidence deleted.")
            else:
                from .operational_io import active_storage
                storage = active_storage()
                if storage is not None:
                    try:storage.write_bytes(destination, body, replace=False)
                    except FileExistsError:pass
                else:
                    temporary = None
                    try:
                        with tempfile.NamedTemporaryFile(dir=private, prefix=".pending-", delete=False) as f:
                            temporary = Path(f.name); f.write(body); f.flush(); os.fsync(f.fileno())
                        try:os.link(temporary, destination)
                        except FileExistsError:pass
                    finally:
                        if temporary is not None:temporary.unlink(missing_ok=True)
    report = {"schema_version": "website-paired-scorecard-v1", "state": "SCORED" if rows else "PENDING_OR_UNSUPPORTED",
              "paired_rows": len(rows) // 2, "coverage": dict(coverage), "summaries": summaries, "paired": paired,
              "limits": sorted(set(limits)), "promoted": [],
              "scope": "Same original lab rows and cutoff; strict timely hash bindings; no selected-line or EV claim. Confirmation gates remain separate."}
    if coverage["rehydration_budget_pending"]:
        report["state"] = "PARTIAL_REHYDRATION_BUDGET_PENDING"
    report["resource_profile"] = {"unique_snapshots_attempted": len(attempted_sources), "unique_snapshots_recovered": len(recovered_points), "source_bytes_processed": processed_bytes,
                                  "seconds": time.monotonic()-started, "budget": "128 snapshots, 512MiB including last bounded snapshot, 120s launch cutoff; shared HTTP retries/timeouts unchanged"}
    save(state, "website_comparisons", report)
    return report
