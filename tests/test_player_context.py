"""Fictional-only player-context provenance, identity and clock fixtures."""
from dataclasses import replace
import hashlib
import json

import pandas as pd
import pytest

from nfl_lab.player_context import (SOURCE_URLS, field_state, load_source_snapshot,
                                    news_context, news_context_asof, player_context_asof,
                                    sleeper_context)

PLAYER = "00-0999001"
OTHER = "00-0999002"
LOCAL = "2026-10-23T10:00:00+00:00"
CUTOFF = "2026-10-23T11:00:00+00:00"


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encode(doc):
    return json.dumps(doc, ensure_ascii=False).encode()


def player(**updates):
    return {"player_id": "990001", "gsis_id": PLAYER, "team": "FIC", "position": "WR", **updates}


def source(tmp_path, payload=None, *, source_id="sleeper_nfl_players", clocks=None,
           entry_updates=None, receipt_updates=None, replay_origin=None, body=None):
    directory = tmp_path / str(len(list(tmp_path.iterdir())))
    directory.mkdir()
    body = encode(payload if payload is not None else {"990001": player()}) if body is None else body
    entry = {"source_id": source_id, "source_url": SOURCE_URLS[source_id],
             "sha256": digest(body), "body_bytes": len(body), "body_path": "body.json",
             "receipt_path": "receipt.json", "retrieval_started_at": LOCAL, "retrieved_at": LOCAL,
             "first_observed_at": LOCAL, "captured_at": LOCAL,
             "clock_basis": "local_capture_receipt", "upstream_publication_at": None,
             **(clocks or {})}
    if replay_origin is not None:
        original = encode({"url": entry["source_url"], "sha256": entry["sha256"], "bytes": len(body),
                           "retrieved_utc": replay_origin, "status": "acquired"})
        (directory / "origin.receipt.json").write_bytes(original)
        entry.update(capture_mode="authenticated_cache_replay", clock_basis="local_cache_replay_receipt",
                     source_vintage_at=replay_origin, origin_receipt_path="origin.receipt.json",
                     origin_receipt_sha256=digest(original))
    entry.update(entry_updates or {})
    receipt = {k: v for k, v in entry.items() if k not in ("body_path", "receipt_path", "origin_receipt_path")}
    receipt.update(receipt_updates or {})
    receipt_bytes = encode(receipt)
    entry["receipt_sha256"] = digest(receipt_bytes)
    manifest = encode({"schema_version": "player-context-source-manifest-v1", "sources": [entry]})
    (directory / "body.json").write_bytes(body)
    (directory / "receipt.json").write_bytes(receipt_bytes)
    path = directory / "manifest.json"
    path.write_bytes(manifest)
    return load_source_snapshot(path, trusted_manifest_sha256=digest(manifest), source_id=source_id)


def query(snapshots, **kwargs):
    return player_context_asof(snapshots, CUTOFF, sleeper_id="990001", max_age_hours=24, **kwargs)


def article(**updates):
    return {"id": "999001", "description": "Fictional athlete discussion; category mentions do not assign a claim.",
            "headline": "Fictional fixture", "published": "2026-10-23T08:00:00Z",
            "lastModified": "2026-10-23T09:00:00Z", "premium": False,
            "links": {"web": {"href": "https://example.invalid/fictional-news"}},
            "categories": [{"type": "athlete", "athlete": {"id": "990011"}}], **updates}


def news_source(tmp_path, articles=None, **kwargs):
    return source(tmp_path, {"articles": [article()] if articles is None else articles},
                  source_id="espn_nfl_public_news", **kwargs)


def news_asof(snapshots, **kwargs):
    return news_context_asof(snapshots, CUTOFF, max_snapshot_age_hours=24,
                            max_content_age_hours=24, **kwargs)


def test_exact_body_receipt_manifest_and_mutated_bytes_fail_closed(tmp_path):
    snapshot = source(tmp_path)
    assert sleeper_context(snapshot)[0]["player_id"] == PLAYER
    for changed in (replace(snapshot, body=snapshot.body + b" "),
                    replace(snapshot, receipt=snapshot.receipt + b" "),
                    replace(snapshot, manifest=snapshot.manifest + b" "),
                    replace(snapshot, body=bytearray(snapshot.body))):
        with pytest.raises(ValueError):
            query([changed])
    with pytest.raises(TypeError):
        load_source_snapshot(tmp_path, trusted_manifest_sha256="0" * 64,
                             source_id="sleeper_nfl_players", trusted=True)
    manifest = json.loads(snapshot.manifest)
    body_path = tmp_path / "0" / manifest["sources"][0]["body_path"]
    body_path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="SHA-256"):
        load_source_snapshot(tmp_path / "0" / "manifest.json", trusted_manifest_sha256=snapshot.trusted_manifest_sha256,
                             source_id="sleeper_nfl_players")
    # Already loaded immutable bytes retain the authenticated original version.
    assert query([snapshot])["context"]["player_id"] == PLAYER


@pytest.mark.parametrize("updates", [
    {"retrieval_started_at": "2026-10-23T10:01:00Z"},
    {"retrieved_at": "2026-10-23T10:01:00Z"},
    {"first_observed_at": "2026-10-23T10:01:00Z"},
    {"captured_at": "2026-10-23T09:59:00Z"},
    {"first_observed_at": None}, {"captured_at": "2026-10-23T10:00:00"},
])
def test_adversarial_clock_order_missing_and_timezone(tmp_path, updates):
    with pytest.raises(ValueError):
        source(tmp_path, clocks=updates)


@pytest.mark.parametrize("entry_updates,receipt_updates", [
    ({"body_bytes": True}, None),
    ({"source_url": "https://example.invalid/other"}, None),
    ({"upstream_publication_at": "2020-01-01T00:00:00Z"}, None),
    ({"clock_basis": "trusted_boolean"}, None),
    (None, {"captured_at": "2026-10-23T10:01:00Z"}),
    (None, {"capture_mode": "authenticated_cache_replay"}),
    (None, {"source_vintage_at": "2026-10-01T00:00:00Z"}),
])
def test_manifest_receipt_binding_and_untrusted_clock_claims(tmp_path, entry_updates, receipt_updates):
    with pytest.raises(ValueError):
        source(tmp_path, entry_updates=entry_updates, receipt_updates=receipt_updates)


@pytest.mark.parametrize("body", [b'{"990001":{},"990001":{}}', b'{"990001":{"active":NaN}}'])
def test_duplicate_provider_keys_and_nonfinite_json_rejected(tmp_path, body):
    with pytest.raises(ValueError):
        source(tmp_path, body=body)


def test_four_optional_states_and_no_healthy_or_participation_inference(tmp_path):
    states = {}
    for label, values in [("absent", {}), ("null", {"injury_status": None}),
                          ("empty", {"injury_status": ""}), ("value", {"injury_status": "Out"})]:
        snapshot = source(tmp_path, {"990001": player(active=False, status="Inactive", injury_start_date="1999-01-01",
                                                      news_updated=1, **values)})
        result = query([snapshot])
        row = result["context"]
        states[label] = row["source_fields"]["injury_status"]
        assert row["participation_state"] == "unknown"
        assert result["context_status"] == "available_advisory"
        assert result["numerical_effects_qualified"] is False
        assert result["forecast_action"] == "retain_existing_forecast_and_fallback"
        assert row["provenance"]["upstream_publication_at"] is None
        assert not any(key.startswith("f_") for key in row)
    assert states == {"absent": {"state": "absent"}, "null": {"state": "null", "value": None},
                      "empty": {"state": "empty", "value": ""}, "value": {"state": "value", "value": "Out"}}
    for value in (False, 0):
        assert field_state({"x": value}, "x") == {"state": "value", "value": value}
    for value in ([], {}):
        assert field_state({"x": value}, "x")["state"] == "empty"


@pytest.mark.parametrize("updates", [{"player_id": "990002"}, {"player_id": None},
                                     {"player_id": 990001}, {"gsis_id": "Fictional Name"},
                                     {"gsis_id": []}, {"team": {}}])
def test_key_embedded_id_and_invalid_identity_types_quarantine(tmp_path, updates):
    snapshot = source(tmp_path, {"990001": player(**updates)})
    row = sleeper_context(snapshot)[0]
    assert row["identity_status"] == "quarantined" and row["player_id"] is None
    assert query([snapshot])["fallback_reason"] == "quarantined_source_identity"


def test_gsis_crosswalk_collision_and_team_conflicts_quarantine(tmp_path):
    snapshot = source(tmp_path, {"990001": player(), "990002": player(player_id="990002")})
    assert all(r["identity_status"] == "quarantined" for r in sleeper_context(snapshot))
    snapshot = source(tmp_path)
    for binding in ([{"sleeper_id": "990001", "player_id": OTHER}],
                    [{"sleeper_id": "990002", "player_id": PLAYER}],
                    [{"sleeper_id": "990001", "player_id": PLAYER, "team": "OTH"}]):
        assert query([snapshot], identity_bindings=binding)["fallback_reason"] == "quarantined_source_identity"
    assert query([snapshot], player_id=OTHER)["fallback_reason"] == "query_player_id_conflict"
    assert query([snapshot], team="OTH")["fallback_reason"] == "query_team_conflict_or_unknown"
    with pytest.raises(ValueError, match="GSIS"):
        query([snapshot], identity_bindings=[{"sleeper_id": "990001", "player_id": "Fictional Name"}])


@pytest.mark.parametrize("team", [None, ""])
def test_unknown_team_does_not_satisfy_requested_team(tmp_path, team):
    snapshot = source(tmp_path, {"990001": player(team=team)})
    assert query([snapshot], team="FIC")["fallback_reason"] == "query_team_conflict_or_unknown"


def test_all_provider_rows_retained_and_unlinked_cold_fallback(tmp_path):
    snapshot = source(tmp_path, {"990001": player(gsis_id=None, position="K", active=False),
                                 "FIC": {"player_id": "FIC", "position": "DEF", "active": False}})
    rows = sleeper_context(snapshot)
    assert len(rows) == 2
    assert rows[0]["identity_status"] == "unlinked_cold_start"
    result = query([snapshot], player_id="sleeper:990001")
    assert result["context"]["player_id"] == "sleeper:990001"
    assert result["forecast_action"] == "retain_existing_forecast_and_fallback"
    assert query([snapshot], player_id=PLAYER)["fallback_reason"] == "query_player_id_conflict"


def test_exact_capture_cutoff_future_body_duplicates_and_freshness(tmp_path):
    old = source(tmp_path, {"990001": player(injury_status="Questionable")})
    new = source(tmp_path, {"990001": player(injury_status="Out", team="OTH")},
                 clocks={k: "2026-10-23T12:00:00Z" for k in ("retrieval_started_at", "retrieved_at", "first_observed_at", "captured_at")})
    for versions in ([old, new], [new, old, old]):
        result = query(versions)
        assert result["context"]["source_fields"]["injury_status"]["value"] == "Questionable"
        assert result["selected_source"]["sha256"] == digest(old.body)
    assert player_context_asof([old], LOCAL, sleeper_id="990001", max_age_hours=24)["fallback_reason"] == "no_snapshot_before_cutoff"
    assert player_context_asof([old], CUTOFF, sleeper_id="990001", max_age_hours=1)["context_status"] == "available_advisory"
    assert player_context_asof([old], CUTOFF, sleeper_id="990001", max_age_hours=.99)["fallback_reason"] == "source_snapshot_stale"
    repackaged = source(tmp_path, clocks={"captured_at": "2026-10-23T10:59:00Z"})
    assert player_context_asof([repackaged], CUTOFF, sleeper_id="990001", max_age_hours=.5)["fallback_reason"] == "source_snapshot_stale"
    repeated = source(tmp_path, clocks={k: "2026-10-23T10:30:00Z" for k in ("retrieval_started_at", "retrieved_at", "first_observed_at", "captured_at")})
    assert repeated.body == old.body.replace(b', "injury_status": "Questionable"', b"")
    first = source(tmp_path)
    assert repeated.body == first.body
    assert query([first, repeated])["selected_source"]["receipt_sha256"] != query([first])["selected_source"]["receipt_sha256"]
    # No fallback to an older row when a newer pre-cutoff roster omits it.
    absent = source(tmp_path, {}, clocks={k: "2026-10-23T10:30:00Z" for k in ("retrieval_started_at", "retrieved_at", "first_observed_at", "captured_at")})
    assert query([old, absent])["fallback_reason"] == "source_player_absent"


def test_same_capture_conflicting_body_abstains(tmp_path):
    a, b = source(tmp_path), source(tmp_path, {"990001": player(team="OTH")})
    assert query([a, b])["fallback_reason"] == "conflicting_source_versions_at_same_capture"


@pytest.mark.parametrize("age", [0, -1, float("nan"), float("inf"), True])
def test_declared_freshness_is_required_and_finite(tmp_path, age):
    with pytest.raises(ValueError):
        player_context_asof([source(tmp_path)], CUTOFF, sleeper_id="990001", max_age_hours=age)


def test_news_exact_mentions_interpretation_field_states_and_unknown_bindings(tmp_path):
    snapshot = news_source(tmp_path, [article(categories=[{"type": "athlete", "athlete": {"id": 990011}},
                                                        {"type": "athlete", "athlete": {"id": "990012"}},
                                                        {"type": "athlete", "athlete": {"id": "Named Player"}}])])
    bindings = [{"espn_id": "990011", "player_id": PLAYER, "team": "FIC"}]
    rows = news_context(snapshot, identity_bindings=bindings)
    assert len(rows) == 3  # bound, unbound and invalid mentions all survive
    exact = rows[rows.player_id.eq(PLAYER)].iloc[0]
    assert exact.source_category_athlete_ids == ["990011"]
    assert exact.claim_text == article()["description"]
    assert rows.claim_type.eq("reporter_interpretation").all()
    assert rows.entity_relationship.eq("source_category_mention_only").all()
    assert rows.injury_claim_qualification.eq("not_established").all()
    assert rows.participation_state.eq("unknown").all()
    assert not any(c.startswith("f_") for c in rows)
    assert len(news_asof([snapshot], identity_bindings=bindings, player_id=PLAYER, team="FIC")) == 1
    assert news_asof([snapshot], identity_bindings=bindings, team="OTH").empty


@pytest.mark.parametrize("espn_id", ["Named Player", "0990011", "９９００１１", "990011.0", " 990011", 990011, True])
def test_news_crosswalk_ids_require_exact_decimal_strings(tmp_path, espn_id):
    with pytest.raises(ValueError):
        news_context(news_source(tmp_path), identity_bindings=[{"espn_id": espn_id, "player_id": PLAYER}])


def test_news_collision_does_not_bind_gsis_or_claim(tmp_path):
    snapshot = news_source(tmp_path)
    for bindings in ([{"espn_id": "990011", "player_id": PLAYER}, {"espn_id": "990011", "player_id": OTHER}],
                     [{"espn_id": "990011", "player_id": PLAYER}, {"espn_id": "990012", "player_id": PLAYER}]):
        rows = news_context(snapshot, identity_bindings=bindings)
        assert rows.player_id.isna().all()
        assert news_asof([snapshot], identity_bindings=bindings, player_id=PLAYER).empty


def test_news_unknown_future_stale_publication_and_changed_future_body(tmp_path):
    missing = article(id="999002", published=None, lastModified=None)
    future = article(id="999003", published="2026-10-23T10:01:00Z", lastModified=None)
    stale = article(id="999004", published="2026-09-01T00:00:00Z", lastModified=None)
    bad_update = article(id="999005", lastModified="2026-10-23T07:00:00Z")
    old = news_source(tmp_path, [article(), missing, future, stale, bad_update])
    rows = news_context(old)
    assert rows.loc[rows.source_article_id.eq("999002"), "clock_status"].iloc[0] == "publication_unknown"
    new = news_source(tmp_path, [article(description="Fictional future changed story.")],
                      clocks={k: "2026-10-23T12:00:00Z" for k in ("retrieval_started_at", "retrieved_at", "first_observed_at", "captured_at")})
    result = news_asof([new, old, old])
    assert len(result) == 1 and result.iloc[0].claim_text == article()["description"]
    assert news_context_asof([old], LOCAL, max_snapshot_age_hours=24, max_content_age_hours=24).empty
    for invalid in (0, float("inf"), float("nan"), True):
        with pytest.raises(ValueError):
            news_context_asof([old], CUTOFF, max_snapshot_age_hours=24, max_content_age_hours=invalid)


def test_news_missing_null_empty_excerpt_states_and_no_upstream_inference(tmp_path):
    snapshots = [news_source(tmp_path, [article(description=None)]), news_source(tmp_path, [article(description="")])]
    assert [news_context(s).iloc[0].source_fields["description"]["state"] for s in snapshots] == ["null", "empty"]
    a = article()
    del a["description"]
    assert news_context(news_source(tmp_path, [a])).iloc[0].source_fields["description"]["state"] == "absent"
    assert news_context(news_source(tmp_path, [article(description=None, headline="")])).empty
    with pytest.raises(ValueError, match="duplicate"):
        news_context(news_source(tmp_path, [article(), article()]))


def test_cache_replay_binds_origin_and_cannot_freshen_or_backdate(tmp_path):
    original = "2026-10-01T10:00:00Z"
    snapshot = source(tmp_path, replay_origin=original)
    assert query([snapshot])["fallback_reason"] == "source_snapshot_stale"
    result = player_context_asof([snapshot], CUTOFF, sleeper_id="990001", max_age_hours=1000)
    assert result["context"]["provenance"]["capture_mode"] == "authenticated_cache_replay"
    assert pd.Timestamp(result["selected_source"]["source_vintage_at"]) == pd.Timestamp(original)
    assert player_context_asof([snapshot], "2026-10-22T10:00:00Z", sleeper_id="990001", max_age_hours=1000)["fallback_reason"] == "no_snapshot_before_cutoff"
    for changed in (replace(snapshot, origin_receipt=snapshot.origin_receipt + b" "), replace(snapshot, origin_receipt=None)):
        with pytest.raises(ValueError, match="origin receipt"):
            query([changed])
    with pytest.raises(ValueError, match="vintage"):
        source(tmp_path, replay_origin="2026-10-24T00:00:00Z")
    with pytest.raises(ValueError, match="binding"):
        source(tmp_path, replay_origin=original, receipt_updates={"source_vintage_at": LOCAL})


def test_cache_replay_news_uses_original_retrieval_for_source_clock_validation(tmp_path):
    snapshot = news_source(tmp_path, replay_origin="2026-10-22T10:00:00Z")
    rows = news_context(snapshot)
    assert rows.iloc[0].clock_status == "source_clock_after_retrieval"
    assert news_context_asof([snapshot], CUTOFF, max_snapshot_age_hours=1000, max_content_age_hours=1000).empty
