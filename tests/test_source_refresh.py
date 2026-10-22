"""Mutable acquisition clocks, immutable history and version preservation."""
import hashlib
import json

import pytest
import requests

from nfl_lab.data import _download, acquire_history


def seed(raw, name="current.parquet", day="2026-10-22", body=b"old-body"):
    raw.mkdir(exist_ok=True)
    path = raw / name
    path.write_bytes(body)
    receipt = {"name": name, "url": "https://example.org/" + name,
               "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
               "status": "acquired", "retrieved_utc": day + "T12:00:00+00:00"}
    metadata = raw / (name + ".receipt.json")
    metadata.write_text(json.dumps(receipt, indent=2) + "\n")
    return path, metadata, receipt


class Response:
    headers = {"ETag": '"new-version"'}

    def __init__(self, body=b"new-body"):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, *args):
        yield self.body


def test_mutable_source_same_utc_day_reuses_without_network(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    path, metadata, original = seed(raw)
    monkeypatch.setattr("nfl_lab.data._utc_now", lambda: "2026-10-22T23:59:59+00:00")
    def unexpected(*args, **kwargs):
        pytest.fail("same-day cache reuse touched the network")
    monkeypatch.setattr("nfl_lab.data.requests.get", unexpected)
    actual = _download(raw, path.name, original["url"], refresh_daily=True)
    assert actual["cache_reused"] is True
    assert actual["retrieved_utc"] == original["retrieved_utc"]
    assert not (raw / "versions").exists()


def test_next_utc_day_refresh_archives_exact_old_body_and_receipt(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    path, metadata, original = seed(raw)
    old_receipt = metadata.read_bytes()
    monkeypatch.setattr("nfl_lab.data._utc_now", lambda: "2026-10-23T00:00:01+00:00")
    calls = []
    def download(*args, **kwargs):
        calls.append(args[0])
        return Response()
    monkeypatch.setattr("nfl_lab.data.requests.get", download)
    actual = _download(raw, path.name, original["url"], refresh_daily=True)
    assert len(calls) == 1
    assert path.read_bytes() == b"new-body"
    assert actual["retrieved_utc"] == "2026-10-23T00:00:01+00:00"
    archived = actual["previous_version"]
    assert (raw / archived["body"]).read_bytes() == b"old-body"
    assert (raw / archived["receipt"]).read_bytes() == old_receipt
    assert archived["sha256"] == original["sha256"]
    assert archived["receipt_sha256"] == hashlib.sha256(old_receipt).hexdigest()
    assert actual["sha256"] == hashlib.sha256(b"new-body").hexdigest()
    again = _download(raw, path.name, original["url"], refresh_daily=True)
    assert again["cache_reused"] is True
    assert len(calls) == 1


def test_failed_refresh_is_explicitly_stale_preserves_bytes_and_source_clock(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    path, metadata, original = seed(raw)
    old_receipt = metadata.read_bytes()
    clock = ["2026-10-23T00:00:01+00:00"]
    monkeypatch.setattr("nfl_lab.data._utc_now", lambda: clock[0])
    monkeypatch.setattr("nfl_lab.data.time.sleep", lambda _: None)
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(args[0])
        raise requests.ConnectionError("temporary source outage")
    monkeypatch.setattr("nfl_lab.data.requests.get", unavailable)
    actual = _download(raw, path.name, original["url"], refresh_daily=True)
    assert len(calls) == 3
    assert actual["status"] == "stale_cache" and actual["stale"] is True
    assert "temporary source outage" in actual["refresh_error"]
    assert actual["retrieved_utc"] == original["retrieved_utc"]
    assert actual["sha256"] == original["sha256"]
    assert path.read_bytes() == b"old-body"
    assert (raw / actual["previous_version"]["receipt"]).read_bytes() == old_receipt
    assert json.loads(metadata.read_text())["status"] == "stale_cache"
    repeated = _download(raw, path.name, original["url"], refresh_daily=True)
    assert repeated["stale"] is True and len(calls) == 3
    # The next day permits one new bounded attempt, retaining the same source clock.
    clock[0] = "2026-10-24T00:00:01+00:00"
    later = _download(raw, path.name, original["url"], refresh_daily=True)
    assert later["stale"] is True and len(calls) == 6
    assert later["retrieved_utc"] == original["retrieved_utc"]


def test_historical_file_reuses_fixed_campaign_version_on_later_day(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    path, metadata, original = seed(raw, name="stats_player_week_2025.parquet")
    monkeypatch.setattr("nfl_lab.data._utc_now", lambda: "2026-12-23T00:00:01+00:00")
    def unexpected(*args, **kwargs):
        pytest.fail("fixed historical cache touched the network")
    monkeypatch.setattr("nfl_lab.data.requests.get", unexpected)
    actual = _download(raw, path.name, original["url"])
    assert actual["cache_reused"] is True
    assert actual["retrieved_utc"] == original["retrieved_utc"]


def test_acquisition_uses_two_threads_and_refreshes_only_mutable_groups(tmp_path, monkeypatch):
    jobs = []
    workers = []
    class SequentialPool:
        def __init__(self, max_workers):
            workers.append(max_workers)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def map(self, fn, inputs):
            return map(fn, inputs)
    def fake_download(raw, name, url, *, optional=False, refresh_daily=False):
        jobs.append((name, refresh_daily))
        return {"name": name, "status": "unavailable"}
    monkeypatch.setattr("nfl_lab.data.ThreadPoolExecutor", SequentialPool)
    monkeypatch.setattr("nfl_lab.data._download", fake_download)
    monkeypatch.setattr("nfl_lab.data._utc_now", lambda: "2026-10-22T12:00:00+00:00")
    acquire_history(tmp_path, [2025, 2026])
    policy = dict(jobs)
    assert workers == [2]
    assert policy["schedules.csv"] and policy["players.parquet"]
    assert policy["ngs_release.json"]
    for kind in ("stats_player_week", "roster_weekly", "snap_counts"):
        assert policy[f"{kind}_2026.parquet"]
        assert not policy[f"{kind}_2025.parquet"]
