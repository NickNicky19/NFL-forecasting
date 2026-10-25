"""Opt-in, exact-source player context; no collector, model or numerical effects.

The caller supplies an independently trusted manifest digest. Local capture
evidence establishes observed-by availability, never upstream publication or
historical game participation. Source rows and excerpts remain private.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .context import GSIS, _canonical_url, _clock, normalize_observations, observations_asof
from .data import _sha

SCHEMA = "player-context-source-manifest-v1"
SOURCE_URLS = {
    "sleeper_nfl_players": "https://api.sleeper.app/v1/players/nfl",
    "espn_nfl_public_news": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=50",
}
CLOCKS = ("retrieval_started_at", "retrieved_at", "first_observed_at", "captured_at")
RECEIPT_BINDINGS = ("source_id", "source_url", "sha256", "body_bytes", *CLOCKS,
                    "clock_basis", "upstream_publication_at")
PLAYER_FIELDS = ("player_id", "gsis_id", "espn_id", "team", "position", "fantasy_positions",
                 "status", "active", "injury_status", "injury_body_part", "injury_start_date",
                 "injury_practice_participation", "injury_practice_status", "injury_notes", "news_updated")


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _json(body: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("nonfinite JSON constant: " + value)

    return json.loads(body, object_pairs_hook=unique, parse_constant=invalid_constant)


def _hash(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("expected lowercase SHA-256 digest")
    return value


def _id(value):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("identity must be an exact nonempty string")
    return value


def _manifest_entry(manifest: bytes, trusted_sha256: str, source_id: str) -> dict:
    if _digest(manifest) != _hash(trusted_sha256):
        raise ValueError("trusted manifest SHA-256 mismatch")
    doc = _json(manifest)
    if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA or not isinstance(doc.get("sources"), list):
        raise ValueError("unsupported source manifest schema")
    entries = doc["sources"]
    if any(not isinstance(e, dict) or e.get("source_id") not in SOURCE_URLS for e in entries):
        raise ValueError("unsupported source manifest entry")
    ids = [e["source_id"] for e in entries]
    if len(ids) != len(set(ids)) or source_id not in ids:
        raise ValueError("duplicate or absent manifest source identity")
    return entries[ids.index(source_id)]


@dataclass(frozen=True)
class SourceSnapshot:
    """Immutable bytes bound to an externally supplied trusted manifest SHA.

    Adapter entry points recheck all bindings, including when a caller uses
    dataclasses.replace. Mutable decoded rows are never used as trusted inputs.
    """
    source_id: str
    body: bytes
    receipt: bytes
    manifest: bytes
    trusted_manifest_sha256: str
    origin_receipt: bytes | None = None


def _verify(snapshot: SourceSnapshot) -> tuple[dict, dict]:
    if not isinstance(snapshot, SourceSnapshot):
        raise ValueError("load a manifest-bound SourceSnapshot")
    if any(type(value) is not bytes for value in (snapshot.body, snapshot.receipt, snapshot.manifest)):
        raise ValueError("source snapshot requires immutable bytes")
    entry = _manifest_entry(snapshot.manifest, snapshot.trusted_manifest_sha256, snapshot.source_id)
    if entry.get("source_url") != SOURCE_URLS[snapshot.source_id]:
        raise ValueError("source URL does not match registered source")
    if _digest(snapshot.body) != _hash(entry.get("sha256")):
        raise ValueError("source body SHA-256 mismatch")
    if type(entry.get("body_bytes")) is not int or entry["body_bytes"] != len(snapshot.body):
        raise ValueError("source body byte count mismatch")
    if len(snapshot.body) > 33554432:
        raise ValueError("source body exceeds registered intake budget")
    if _digest(snapshot.receipt) != _hash(entry.get("receipt_sha256")):
        raise ValueError("source receipt SHA-256 mismatch")
    receipt = _json(snapshot.receipt)
    if not isinstance(receipt, dict) or any(k not in entry or k not in receipt or entry[k] != receipt[k] for k in RECEIPT_BINDINGS):
        raise ValueError("manifest/receipt binding mismatch")
    mode = entry.get("capture_mode", "direct_http")
    if receipt.get("capture_mode", "direct_http") != mode:
        raise ValueError("manifest/receipt capture mode mismatch")
    basis = "local_capture_receipt" if mode == "direct_http" else "local_cache_replay_receipt"
    if mode not in ("direct_http", "authenticated_cache_replay") or entry["clock_basis"] != basis or entry["upstream_publication_at"] is not None:
        raise ValueError("v1 requires declared local capture clocks and unknown upstream publication")
    clocks = [_clock(entry[k]) for k in CLOCKS]
    if any(pd.isna(c) for c in clocks) or clocks != sorted(clocks):
        raise ValueError("capture clocks missing or out of order")
    vintage, content_retrieved = clocks[2], clocks[1]
    if mode == "authenticated_cache_replay":
        for key in ("capture_mode", "source_vintage_at", "origin_receipt_sha256"):
            if key not in entry or key not in receipt or entry[key] != receipt[key]:
                raise ValueError("cache replay manifest/receipt binding mismatch")
        if type(snapshot.origin_receipt) is not bytes or _digest(snapshot.origin_receipt) != _hash(entry["origin_receipt_sha256"]):
            raise ValueError("cache replay origin receipt SHA-256 mismatch")
        origin = _json(snapshot.origin_receipt)
        if not isinstance(origin, dict) or origin.get("url") != entry["source_url"] or origin.get("sha256") != entry["sha256"] or type(origin.get("bytes")) is not int or origin["bytes"] != len(snapshot.body):
            raise ValueError("cache replay origin receipt source/body mismatch")
        vintage = _clock(entry["source_vintage_at"])
        original_retrieval = _clock(origin.get("retrieved_utc"))
        if pd.isna(vintage) or pd.isna(original_retrieval) or vintage != original_retrieval or vintage > clocks[0]:
            raise ValueError("cache replay source vintage must equal original retrieval before local replay")
        content_retrieved = original_retrieval
    elif snapshot.origin_receipt is not None or any(k in entry or k in receipt for k in ("source_vintage_at", "origin_receipt_sha256", "origin_receipt_path")):
        raise ValueError("origin receipt fields require explicit cache replay mode")
    payload = _json(snapshot.body)
    if not isinstance(payload, dict):
        raise ValueError("source body must be a JSON object")
    provenance = {k: entry[k] for k in RECEIPT_BINDINGS}
    provenance.update(receipt_sha256=entry["receipt_sha256"],
                      trusted_manifest_sha256=snapshot.trusted_manifest_sha256,
                      source_version_id=_digest((entry["sha256"] + ":" + entry["receipt_sha256"]).encode()),
                      capture_mode=mode, source_vintage_at=vintage.isoformat(),
                      content_retrieved_at=content_retrieved.isoformat(),
                      availability_basis="local_cache_replay_capture; not original availability evidence" if mode == "authenticated_cache_replay" else "local_complete_body_capture; upstream publication unknown")
    if mode == "authenticated_cache_replay":
        provenance["origin_receipt_sha256"] = entry["origin_receipt_sha256"]
    return payload, provenance


def load_source_snapshot(manifest_path: Path, *, trusted_manifest_sha256: str, source_id: str) -> SourceSnapshot:
    """Read existing immutable capture files; never fetch, write or infer trust."""
    path = Path(manifest_path)
    manifest = path.read_bytes()
    if _sha(path) != _digest(manifest):
        raise ValueError("source manifest changed while reading")
    entry = _manifest_entry(manifest, trusted_manifest_sha256, source_id)

    def read_bound(key, digest_key):
        value = entry.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError("source manifest requires body and receipt paths")
        target = Path(value)
        target = target if target.is_absolute() else path.parent / target
        body = target.read_bytes()
        if _sha(target) != _digest(body) or _digest(body) != _hash(entry.get(digest_key)):
            raise ValueError("source file SHA-256 mismatch or changed while reading")
        return body

    origin = read_bound("origin_receipt_path", "origin_receipt_sha256") if entry.get("capture_mode") == "authenticated_cache_replay" else None
    snapshot = SourceSnapshot(source_id, read_bound("body_path", "sha256"),
                              read_bound("receipt_path", "receipt_sha256"), manifest, trusted_manifest_sha256, origin)
    _verify(snapshot)
    return snapshot


def field_state(record: dict, field: str) -> dict:
    """Preserve absence, JSON null, empty strings/containers and exact values."""
    if field not in record:
        return {"state": "absent"}
    value = record[field]
    state = "null" if value is None else "empty" if value in ("", [], {}) else "value"
    return {"state": state, "value": value}


def _optional_string(record, field):
    if field in record and record[field] is not None and not isinstance(record[field], str):
        raise ValueError("optional identity field must be a string or null")
    state = field_state(record, field)
    if state["state"] != "value":
        return None
    return _id(state["value"])


def _bindings(records, source_key):
    if isinstance(records, (dict, str, bytes)):
        raise ValueError("identity bindings must retain individual exact-ID rows")
    by_source, by_player = defaultdict(list), defaultdict(set)
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("identity binding must be a mapping")
        sid, pid = _id(row.get(source_key)), _id(row.get("player_id"))
        if source_key == "espn_id":
            sid = _provider_id(sid)
        if not GSIS.fullmatch(pid):
            raise ValueError("identity binding requires exact GSIS player_id")
        team = _optional_string(row, "team")
        by_source[sid].append((pid, team))
        by_player[pid].add(sid)
    return by_source, by_player


def sleeper_context(snapshot: SourceSnapshot, *, identity_bindings=()) -> list[dict]:
    """All provider rows, including unlinked/inactive/non-skill identities.

    Exact optional crosswalk rows have sleeper_id/player_id and optional team.
    Status/injury/roster flags are advisory source values, never game DNP proof.
    """
    payload, provenance = _verify(snapshot)
    if snapshot.source_id != "sleeper_nfl_players":
        raise ValueError("expected Sleeper player source")
    bindings, reverse = _bindings(identity_bindings, "sleeper_id")
    rows = []
    for sid, source in payload.items():
        _id(sid)
        if not isinstance(source, dict):
            raise ValueError("Sleeper player record must be an object")
        reasons, candidates = [], {p for p, _ in bindings[sid]}
        try:
            embedded = _optional_string(source, "player_id")
            if embedded != sid:
                reasons.append("source_key_player_id_mismatch_or_unknown")
        except ValueError:
            reasons.append("invalid_source_player_id")
        try:
            direct = _optional_string(source, "gsis_id")
            if direct is not None and not GSIS.fullmatch(direct):
                raise ValueError("invalid GSIS")
            if direct:
                candidates.add(direct)
        except ValueError:
            direct = None
            reasons.append("invalid_source_gsis_id")
        try:
            team = _optional_string(source, "team")
        except ValueError:
            team = None
            reasons.append("invalid_source_team")
        if len(candidates) > 1:
            reasons.append("conflicting_gsis_bindings")
        if any(t is not None and (team is None or t != team) for _, t in bindings[sid]):
            reasons.append("registry_source_team_conflict_or_unknown")
        for pid in candidates:
            reverse[pid].add(sid)
        rows.append({"sleeper_id": sid, "source_gsis_id": direct, "team": team,
                     "source_fields": {k: field_state(source, k) for k in PLAYER_FIELDS},
                     "source_record": source, "identity_reasons": reasons, "_candidates": candidates,
                     "provenance": dict(provenance), "participation_state": "unknown",
                     "context_role": "advisory_source_flags_only", "numerical_effects_qualified": False})
    for row in rows:
        candidates = row.pop("_candidates")
        if any(len(reverse[p]) > 1 for p in candidates):
            row["identity_reasons"].append("gsis_bound_to_multiple_sleeper_ids")
        if row["identity_reasons"]:
            row.update(player_id=None, identity_status="quarantined")
        elif candidates:
            row.update(player_id=next(iter(candidates)), identity_status="source_exact_gsis" if row["source_gsis_id"] else "exact_registry_binding")
        else:
            row.update(player_id="sleeper:" + row["sleeper_id"], identity_status="unlinked_cold_start")
    return rows


def _select(snapshots, source_id, cutoff_utc, max_age_hours):
    cutoff = _clock(cutoff_utc)
    if pd.isna(cutoff) or type(max_age_hours) not in (int, float) or not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("timezone-explicit cutoff and finite positive declared freshness required")
    versions = {}
    for snapshot in snapshots:
        _, provenance = _verify(snapshot)
        if snapshot.source_id != source_id:
            raise ValueError("mixed source types in as-of selection")
        # Same body with a different authenticated receipt remains a separate
        # capture. Repeating the identical body/receipt version adds no evidence.
        versions.setdefault(provenance["source_version_id"], (snapshot, provenance))
    eligible = [(s, p) for s, p in versions.values() if _clock(p["captured_at"]) < cutoff]
    if not eligible:
        return None, None, "no_snapshot_before_cutoff"
    newest = max(_clock(p["captured_at"]) for _, p in eligible)
    latest = [(s, p) for s, p in eligible if _clock(p["captured_at"]) == newest]
    if len({p["sha256"] for _, p in latest}) > 1:
        return None, None, "conflicting_source_versions_at_same_capture"
    snapshot, provenance = min(latest, key=lambda pair: pair[1]["source_version_id"])
    # Capture/packaging delay cannot freshen an older complete-body observation.
    if cutoff - _clock(provenance["source_vintage_at"]) > pd.Timedelta(hours=max_age_hours):
        return None, provenance, "source_snapshot_stale"
    return snapshot, provenance, None


def player_context_asof(snapshots, cutoff_utc, *, sleeper_id: str, max_age_hours: float,
                        player_id: str | None = None, team: str | None = None, identity_bindings=()) -> dict:
    """Select one exact pre-cutoff snapshot; preserve forecast query/fallback.

    A latest snapshot's missing/quarantined player never falls through to an old
    roster row. Unlinked source IDs remain queryable in their Sleeper namespace.
    """
    _id(sleeper_id)
    if player_id is not None and player_id != "sleeper:" + sleeper_id and (not isinstance(player_id, str) or not GSIS.fullmatch(player_id)):
        raise ValueError("query player_id requires exact GSIS or matching Sleeper namespace")
    if team is not None:
        _id(team)
    snapshot, provenance, reason = _select(snapshots, "sleeper_nfl_players", cutoff_utc, max_age_hours)
    row = None
    if snapshot is not None:
        row = next((r for r in sleeper_context(snapshot, identity_bindings=identity_bindings) if r["sleeper_id"] == sleeper_id), None)
        if row is None:
            reason = "source_player_absent"
        elif row["identity_status"] == "quarantined":
            reason = "quarantined_source_identity"
        elif player_id is not None and row["player_id"] != player_id:
            reason = "query_player_id_conflict"
        elif team is not None and row["team"] != team:
            reason = "query_team_conflict_or_unknown"
    return {"context_status": "fallback" if reason else "available_advisory", "fallback_reason": reason,
            "context": row if not reason else None, "selected_source": provenance,
            "participation_state": "unknown", "forecast_action": "retain_existing_forecast_and_fallback",
            "numerical_effects_qualified": False}


def _provider_id(value):
    # ESPN's feed may encode an ID as an integer token. This lossless decimal
    # representation is explicit; floats, booleans and names never bind IDs.
    token = str(value) if type(value) is int and value >= 0 else _id(value)
    if not token.isascii() or not token.isdecimal() or (len(token) > 1 and token[0] == "0"):
        raise ValueError("ESPN identity must be a canonical ASCII decimal token")
    return token


def news_context(snapshot: SourceSnapshot, *, identity_bindings=()) -> pd.DataFrame:
    """Feed excerpts plus exact category mentions, never extracted injury claims.

    Optional crosswalk rows have espn_id/player_id and optional team. Unknown
    publication remains unknown and fails the canonical observation as-of gate.
    """
    payload, provenance = _verify(snapshot)
    if snapshot.source_id != "espn_nfl_public_news":
        raise ValueError("expected ESPN news source")
    bindings, reverse = _bindings(identity_bindings, "espn_id")
    articles = payload.get("articles")
    if not isinstance(articles, list) or any(not isinstance(a, dict) for a in articles):
        raise ValueError("news source requires an articles list")
    records, skipped = [], 0
    article_ids = set()
    for article in articles:
        aid = _provider_id(article.get("id"))
        if aid in article_ids:
            raise ValueError("duplicate news article identity")
        article_ids.add(aid)
        fields = {k: field_state(article, k) for k in ("id", "description", "headline", "published", "lastModified", "premium", "categories", "links")}
        text = next((article[k] for k in ("description", "headline") if isinstance(article.get(k), str) and article[k].strip()), None)
        links = article.get("links")
        web = links.get("web") if isinstance(links, dict) else None
        url = web.get("href") if isinstance(web, dict) else None
        if text is None or url is None:
            skipped += 1
            continue
        _canonical_url(url)
        categories = article.get("categories", [])
        if categories is None:
            categories = []
        if not isinstance(categories, list):
            raise ValueError("news categories must be a list or null")
        mentions = defaultdict(list)
        for category in categories:
            if not isinstance(category, dict) or category.get("type") != "athlete":
                continue
            athlete = category.get("athlete")
            try:
                sid = _provider_id(athlete.get("id") if isinstance(athlete, dict) else None)
            except ValueError:
                mentions[(None, None, "invalid_category_identity")].append(None)
                continue
            matches = set(bindings[sid])
            if len(matches) == 1 and len(reverse[next(iter(matches))[0]]) == 1:
                pid, team = next(iter(matches))
                key = (pid, team, "exact_id_category_mention")
            else:
                key = (None, None, "conflicting_category_binding" if matches else "unbound_category_mention")
            mentions[key].append(sid)
        if not mentions:
            mentions[(None, None, "no_athlete_category")]
        for (pid, team, status), source_ids in mentions.items():
            records.append({"source_url": url, "source_article_id": aid, "claim_text": text,
                            "group": "news", "claim_type": "reporter_interpretation", "player_id": pid, "team": team,
                            "published_utc": article.get("published"), "updated_utc": article.get("lastModified"),
                            "retrieved_utc": provenance["content_retrieved_at"], "identity_status": status,
                            "source_category_athlete_ids": sorted(set(i for i in source_ids if i is not None)),
                            "entity_relationship": "source_category_mention_only", "source_fields": fields,
                            "source_access": "public_feed_excerpt", "provenance": dict(provenance),
                            "participation_state": "unknown", "injury_claim_qualification": "not_established",
                            "numerical_effects_qualified": False})
    # Keep exact article/category rows even when the canonical helper finds
    # equivalent prose at one URL. Canonical claim identity is still retained.
    result = pd.concat([normalize_observations([record]) for record in records], ignore_index=True) if records else normalize_observations([])
    result.attrs.update(source_provenance=provenance, source_articles=len(articles),
                        articles_without_accessible_excerpt=skipped,
                        limitations="category mention is not claim subject; no numerical effects or DNP inference")
    return result


def news_context_asof(snapshots, cutoff_utc, *, max_snapshot_age_hours: float, max_content_age_hours: float,
                     identity_bindings=(), player_id: str | None = None, team: str | None = None) -> pd.DataFrame:
    """Gate the exact captured feed and then canonical article source clocks."""
    if type(max_content_age_hours) not in (int, float) or not math.isfinite(max_content_age_hours) or max_content_age_hours <= 0:
        raise ValueError("finite positive declared content freshness required")
    if player_id is not None and (not isinstance(player_id, str) or not GSIS.fullmatch(player_id)):
        raise ValueError("news query requires exact GSIS player_id")
    if team is not None:
        _id(team)
    snapshot, provenance, reason = _select(snapshots, "espn_nfl_public_news", cutoff_utc, max_snapshot_age_hours)
    if snapshot is None:
        result = normalize_observations([])
    else:
        result = observations_asof(news_context(snapshot, identity_bindings=identity_bindings), cutoff_utc,
                                   player_id=player_id, team=team, max_age_hours=max_content_age_hours)
    result.attrs.update(selected_source=provenance, fallback_reason=reason,
                        forecast_action="retain_existing_forecast_and_fallback", numerical_effects_qualified=False)
    return result
