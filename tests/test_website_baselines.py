import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nfl_lab.state import append_outcomes, capture, digest, records, save
from nfl_lab.website_baselines import (capture_website_bindings, prepare_website_snapshot,
    record_website_publication, score_saved_website)

NOW = datetime(2026, 10, 22, 17, tzinfo=timezone.utc)
COMMIT = "a" * 40
TREE = "b" * 40


def fixture(tmp_path, *, target="pass_yd", raw=205., adjusted=213., chance=.4):
    root = tmp_path / "root"; cache = root / "data"; state = root / "state"
    (root / "config").mkdir(parents=True)
    policy = json.loads((Path(__file__).parents[1] / "config/website-baseline-v1.json").read_text())
    (root / "config/website-baseline-v1.json").write_text(json.dumps(policy))
    games = [{"game_id": "espn:1", "home": "NYG", "away": "WAS", "kickoff_utc": "2026-10-23T00:15:00Z"}]
    board = {"season": 2026, "week": 7, "generated_at": (NOW - timedelta(minutes=30)).isoformat(),
        "games": [{"id": "1", "home": "NYG", "away": "WAS", "kickoff": games[0]["kickoff_utc"], "state": "pre"}],
        "players": [{"id": "s1", "pos": "QB", "team": "WAS", "game_id": "1", "props": [
            {"key": target, "proj": raw, "adj": adjusted, "td_chance": chance}]}]}
    changes = {}

    def download(directory, name, url):
        meta = {k: board[k] for k in ["season", "week", "generated_at"]}
        encode = lambda d: json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
        bodies = {"output/data/week.json": encode(board), "output/data/meta.json": encode(meta)}
        entries = [{"path": k, "type": "blob", "mode": "100644", "sha": v} for k, v in policy["engine_blobs"].items()]
        entries += [{"path": k, "type": "blob", "mode": "100644", "sha": hashlib.sha1(b"blob " + str(len(v)).encode() + b"\0" + v).hexdigest()} for k, v in bodies.items()]
        if changes.get("engine"):
            entries[0]["sha"] = "c" * 40
        if url.endswith("branches/main"):
            body = encode({"commit": {"sha": COMMIT, "commit": {"tree": {"sha": TREE}}}})
        elif "git/trees" in url:
            body = encode({"sha": TREE, "truncated": changes.get("truncated", False), "tree": entries})
        elif url.endswith("week.json"):
            body = bodies["output/data/week.json"]
        elif url.endswith("meta.json"):
            body = bodies["output/data/meta.json"]
        else:
            raise AssertionError("unexpected external URL")
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(body)
        return {"sha256": hashlib.sha256(body).hexdigest(), "url": url,
                "retrieved_utc": (NOW - timedelta(minutes=1)).isoformat(), "name": name}

    return root, cache, state, games, board, changes, download


def lab_batch(state, games, *, target="pass_yd", cutoff=None, mean=210.):
    row = {"player_id": "00-1", "sleeper_id": "s1", "game_id": "espn:1", "team": "WAS", "opponent": "NYG",
        "position": "QB", "season": 2026, "week": 7, "target": target, "period": "full_game", "model_id": "lab-v1.1-tree",
        "scoring_id": "nfl-full-game-v1", "input_sha256": "a" * 64, "code_sha256": "b" * 64,
        "kickoff_utc": games[0]["kickoff_utc"], "mean": mean, "fallback": "", "family": "normal", "scale": 10.,
        "p_participation": .9, "feature_cutoff_utc": (cutoff or NOW + timedelta(minutes=1)).isoformat(),
        "code_integrity": "pre_post_source_digest_required"}
    issued = max(NOW + timedelta(minutes=2), datetime.fromisoformat(row["feature_cutoff_utc"]) + timedelta(minutes=1))
    return capture(state, [row], clock=lambda: issued)["batch"]


def prepared(f):
    root, cache, _, games, _, _, download = f
    return prepare_website_snapshot(root, cache, games, 2026, 7, clock=lambda: NOW, downloader=download)


def bind(f, *, cutoff=None, target="pass_yd", mean=210.):
    _, _, state, games, _, _, _ = f
    p = prepared(f); batch = lab_batch(state, games, cutoff=cutoff, target=target, mean=mean)
    persisted = max(NOW + timedelta(minutes=3), (cutoff or NOW) + timedelta(minutes=2))
    result = capture_website_bindings(state, p, batch, clock=lambda: persisted)
    return batch, result


def publish(state, batch, *, late=False):
    clock = NOW + timedelta(minutes=4) if not late else NOW + timedelta(days=1)
    save(state, "publication", {"batch": batch, "observed_remote_readback_at": clock.isoformat()})
    record_website_publication(state, "d" * 40, clock)


def outcome(state, target="pass_yd", actual=230.):
    append_outcomes(state, [{"player_id": "00-1", "game_id": "espn:1", "target": target, "actual": actual,
        "participation_state": "played", "source": "test", "source_sha256": "e" * 64,
        "observed_at": (NOW + timedelta(days=1)).isoformat(), "source_timestamp": None}])


def test_ready_source_binds_hashes_only_and_round_trips_private_points(tmp_path):
    f = fixture(tmp_path, raw=123.456789, adjusted=234.567891)
    batch, result = bind(f); _, cache, state, _, _, _, download = f
    assert result["bound"] == 2
    snapshot = next(records(state, "website_bindings"))
    exported = json.dumps(snapshot)
    assert "123.456789" not in exported and "234.567891" not in exported
    assert all("value" not in r and "value_sha256" in r for r in snapshot["rows"])
    publish(state, batch); outcome(state)
    report = score_saved_website(state, cache, downloader=download)
    assert report["paired_rows"] == 2 and report["state"] == "SCORED"
    assert all(p["paired_n"] == 1 for p in report["paired"])
    assert {p["cluster_unit"] for p in report["paired"]} == {"game", "week"}
    assert list((tmp_path / "root/runs/website-comparison").glob("*.parquet"))
    assert report["promoted"] == []


def test_missing_publication_cannot_score_and_late_publication_cannot_repair(tmp_path):
    f = fixture(tmp_path); batch, _ = bind(f); _, cache, state, _, _, _, download = f
    outcome(state)
    report = score_saved_website(state, cache, downloader=download)
    assert report["paired_rows"] == 0 and report["coverage"]["unpublished_or_unpersisted"] == 2
    publish(state, batch, late=True)
    report = score_saved_website(state, cache, downloader=download)
    assert report["paired_rows"] == 0 and report["coverage"]["late_or_after_original_cutoff"] == 2


def test_retry_is_idempotent_and_cannot_backfill_old_lab_cutoff(tmp_path):
    f = fixture(tmp_path); batch, result = bind(f)
    again = capture_website_bindings(f[2], prepared(f), batch, clock=lambda: NOW + timedelta(minutes=4))
    assert again["state"] == "ALREADY_BOUND"
    assert len(list(records(f[2], "website_bindings"))) == 1
    assert capture_website_bindings(f[2], prepared(f), None)["state"] == "NO_NEW_LAB_FORECASTS_NO_BASELINE_BACKFILL"
    other = fixture(tmp_path / "old"); _, rejected = bind(other, cutoff=NOW - timedelta(minutes=2))
    assert rejected["bound"] == 0
    assert rejected["binding_exclusions"]["website_observed_after_original_lab_cutoff"] == 1
    assert list(records(other[2], "website_bindings")) == []


@pytest.mark.parametrize("change", ["stale", "future"])
def test_stale_or_future_website_board_abstains(tmp_path, change):
    f = fixture(tmp_path)
    f[4]["generated_at"] = (NOW - timedelta(hours=16) if change == "stale" else NOW + timedelta(minutes=1)).isoformat()
    p = prepared(f)
    assert p["report"]["state"] == "STALE_OR_FUTURE_BOARD"
    assert p["_private_points"] == {}


@pytest.mark.parametrize("change", ["engine", "truncated"])
def test_changed_engine_or_incomplete_tree_fails_closed(tmp_path, change):
    f = fixture(tmp_path); f[5][change] = True
    with pytest.raises(ValueError):
        prepared(f)


def test_independent_schedule_home_away_mismatch_is_not_qualified(tmp_path):
    f = fixture(tmp_path)
    f[3][0].update(home="WAS", away="NYG")
    p = prepared(f)
    assert p["report"]["qualified_points"] == 0
    assert p["report"]["exclusions"]["independent_schedule_mismatch"] == 2


def test_source_fresh_at_observation_but_stale_at_lab_cutoff_is_excluded(tmp_path):
    f = fixture(tmp_path); _, result = bind(f, cutoff=NOW + timedelta(hours=2))
    assert result["bound"] == 0
    assert result["binding_exclusions"]["website_stale_at_original_lab_cutoff"] == 1


def test_immutable_upstream_loss_or_revision_abstains(tmp_path):
    f = fixture(tmp_path); batch, _ = bind(f); _, cache, state, _, board, _, download = f
    publish(state, batch); outcome(state)
    board["players"][0]["props"][0]["adj"] += 1
    changed = score_saved_website(state, cache, downloader=download)
    assert changed["paired_rows"] == 0
    assert changed["coverage"]["immutable_upstream_unavailable_or_invalid"] == 2
    def unavailable(*args, **kwargs):
        raise RuntimeError("immutable source unavailable")
    lost = score_saved_website(state, cache, downloader=unavailable)
    assert lost["paired_rows"] == 0


def test_website_historical_fallback_is_not_raw_sleeper(tmp_path):
    f = fixture(tmp_path, raw=None); _, result = bind(f)
    snapshot = next(records(f[2], "website_bindings"))
    assert result["bound"] == 1
    assert snapshot["rows"][0]["method"] == "pinned_website"
    assert snapshot["rows"][0]["fallback"] == "website_historical_average"


def test_missing_td_count_does_not_create_website_probability_zero(tmp_path):
    f = fixture(tmp_path, target="anytime_td", raw=None, adjusted=None, chance=0.)
    assert prepared(f)["_private_points"] == {}


def test_literal_website_td_probability_scores_as_probability_not_count(tmp_path):
    f = fixture(tmp_path, target="anytime_td", raw=2., adjusted=None, chance=.65)
    batch, result = bind(f, target="anytime_td", mean=.4)
    publish(f[2], batch); outcome(f[2], target="anytime_td", actual=1.)
    report = score_saved_website(f[2], f[1], downloader=f[6])
    assert result["bound"] == 1
    site = next(s for s in report["summaries"] if s["method"] == "pinned_website")
    assert site["bernoulli"]["brier"] == pytest.approx((1 - .65) ** 2)
    assert all(p["primary_metric"] == "brier" for p in report["paired"])


def test_pending_unknown_and_identity_conflict_are_never_zeros(tmp_path):
    f = fixture(tmp_path); batch, _ = bind(f); publish(f[2], batch)
    pending = score_saved_website(f[2], f[1], downloader=f[6])
    assert pending["paired_rows"] == 0 and pending["coverage"]["pending"] == 2
    append_outcomes(f[2], [{"player_id": "00-1", "game_id": "espn:1", "target": "pass_yd", "actual": None,
        "participation_state": "unknown", "identity_quarantined": True, "source": "test", "source_sha256": "e" * 64,
        "observed_at": NOW.isoformat(), "source_timestamp": None}])
    report = score_saved_website(f[2], f[1], downloader=f[6])
    assert report["paired_rows"] == 0
    assert report["coverage"]["unresolved_identity_conflict"] == 2


def test_duplicate_properties_and_invalid_count_support_fail_closed(tmp_path):
    f = fixture(tmp_path, target="pass_att", raw=-1.)
    with pytest.raises(ValueError, match="support"):
        prepared(f)
    f[4]["players"][0]["props"][0]["proj"] = 1.
    f[4]["players"][0]["props"] *= 2
    with pytest.raises(ValueError, match="duplicate website category"):
        prepared(f)


def test_negative_yards_remain_valid_signed_forecasts(tmp_path):
    f = fixture(tmp_path, raw=-3., adjusted=-2.)
    p = prepared(f)
    assert sorted(point["value"] for point in p["_private_points"].values()) == [-3., -2.]


def test_source_cannot_acquire_binding_when_clock_precedes_lab_persistence(tmp_path):
    f = fixture(tmp_path); p = prepared(f); batch = lab_batch(f[2], f[3])
    with pytest.raises(ValueError, match="precedes original lab persistence"):
        capture_website_bindings(f[2], p, batch, clock=lambda: NOW + timedelta(minutes=1))
