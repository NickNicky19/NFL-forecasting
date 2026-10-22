"""Source and complete-history adapter for the unchanged retained YPT core.

Pins authenticate supplied bytes against a trusted manifest, not the truth of a
provider's statistics. Source clocks must reflect a genuine pre-cutoff capture;
downloading revised historical data today cannot qualify it retrospectively.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping

from .retained.receiving_yards_core_draft import evaluate_core

ADAPTER_VERSION = "rec-ypt-complete-week-adapter-v1"
CORE_SHA256 = "54c8ec8f274263cbfe9692777725828cf9ee4af8232c367c02eb98a9ff753ded"
RECEPTION_METHOD = "rec-half-adjustment-v1"
RECEPTION_REGISTERED_AT = "2026-10-16T19:36:46.224755Z"
RECEPTION_SEASON = 2026
RECEPTION_WEEKS = tuple(range(7, 15))


@dataclass(frozen=True)
class SourceDocument:
    reference: str
    payload: bytes
    observed_at: str
    # A contemporary historical download is explicitly unsupported here.
    time_basis: str = "pre_cutoff_capture"


@dataclass(frozen=True)
class ReceivingResult:
    value: Decimal | None
    state: str
    reason: str
    history_game_ids: tuple[str, ...] = ()
    version: str = ADAPTER_VERSION
    evidence_tier: str = "PINNED_CONTENT_AND_SEQUENCE_CHECK_NOT_PROVIDER_TRUTH_OR_ISSUANCE"


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing_time")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_time") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("naive_time")
    return stamp


def _document(document: SourceDocument, trusted_hashes: Mapping[str, str],
              cutoff: datetime) -> Mapping[str, Any]:
    if not isinstance(document, SourceDocument) or not document.reference:
        raise ValueError("missing_source_document")
    if document.time_basis != "pre_cutoff_capture":
        raise ValueError("historical_download_is_not_pre_cutoff_evidence")
    if _time(document.observed_at) > cutoff:
        raise ValueError("source_not_recorded_by_cutoff")
    expected = trusted_hashes.get(document.reference)
    if not expected or hashlib.sha256(document.payload).hexdigest() != expected:
        raise ValueError("untrusted_or_changed_source_content")
    try:
        value = json.loads(document.payload)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid_source_json") from exc
    if not isinstance(value, dict):
        raise ValueError("invalid_source_object")
    return value


def evaluate_receiving(context: Mapping[str, Any], *, opportunities: SourceDocument,
                       statistics: SourceDocument, projection: SourceDocument,
                       trusted_hashes: Mapping[str, str]) -> ReceivingResult:
    """Authenticate latest three earlier appearances without selecting around gaps.

    ``opportunities`` is a pinned player/roster/schedule extraction with keys
    player_id, season, period, through_week and weeks. It has one row per season
    week 1..target_week-1, including ``state=bye`` or ``not_rostered``. A game row
    has state=game, week, game_id, team, opponent and ended_at. The upstream
    roster/schedule extraction, including a trade's old team, must be preserved
    in that source. The adapter checks sequence completeness against this
    explicit season-week contract; it cannot prove a provider's roster truth.

    ``statistics`` contains records for those game identities, including DNPs
    and unknown participation. Each row has the exact retained core's history
    fields, including source_ref matching the statistics document reference.
    A missing row is unknown, and blocks selection if encountered before the
    third played appearance. An unfavorable/invalid played row is never skipped.
    ``projection`` contains the context's original baseline and target estimate.
    All three source documents must have caller-pinned content and genuine clocks.
    """
    baseline = evaluate_core(context, [])
    if baseline.state == "ABSTAIN":
        return ReceivingResult(None, baseline.state, baseline.reason)

    def fallback(reason: str, selected: tuple[str, ...] = ()) -> ReceivingResult:
        return ReceivingResult(baseline.value, "UNCHANGED_WEBSITE_FALLBACK", reason, selected)

    try:
        cutoff = _time(context["cutoff_at"])
        schedule = _document(opportunities, trusted_hashes, cutoff)
        stats = _document(statistics, trusted_hashes, cutoff)
        projected = _document(projection, trusted_hashes, cutoff)
        if context["projection_source_ref"] != projection.reference:
            raise ValueError("projection_source_identity_mismatch")
        for key in ("player_id", "game_id", "team", "opponent", "period", "season", "week",
                    "projected_targets", "website_yards", "projection_observed_at"):
            if key not in projected or projected[key] != context.get(key):
                raise ValueError("projection_content_mismatch:" + key)
        if _time(context["projection_observed_at"]) != _time(projection.observed_at):
            raise ValueError("projection_capture_clock_mismatch")
        for key in ("player_id", "season", "period"):
            if schedule.get(key) != context[key]:
                raise ValueError("schedule_identity_mismatch:" + key)
        if schedule.get("through_week") != context["week"] - 1:
            raise ValueError("schedule_does_not_cover_all_prior_weeks")
        weeks = schedule.get("weeks")
        if not isinstance(weeks, list) or any(not isinstance(row, dict) for row in weeks):
            raise ValueError("invalid_complete_week_sequence")
        expected_weeks = list(range(1, context["week"]))
        if any(isinstance(row.get("week"), bool) or not isinstance(row.get("week"), int)
               for row in weeks):
            raise ValueError("invalid_schedule_week")
        if sorted(row.get("week", -1) for row in weeks) != expected_weeks:
            raise ValueError("missing_or_duplicate_prior_week")
        records = stats.get("records")
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise ValueError("invalid_statistics_records")
        by_game: dict[str, Mapping[str, Any]] = {}
        for row in records:
            game_id = row.get("game_id")
            if not isinstance(game_id, str) or not game_id or game_id in by_game:
                raise ValueError("missing_or_duplicate_statistics_game")
            if row.get("player_id") != context["player_id"]:
                raise ValueError("statistics_player_mismatch")
            by_game[game_id] = row
        game_ids: set[str] = set()
        games: list[tuple[datetime, Mapping[str, Any]]] = []
        for row in weeks:
            state = row.get("state")
            if state in {"bye", "not_rostered"}:
                if row.get("game_id") is not None:
                    raise ValueError("nongame_week_contains_game")
                continue
            if state != "game":
                raise ValueError("unknown_schedule_state")
            game_id = row.get("game_id")
            if not isinstance(game_id, str) or not game_id or game_id in game_ids:
                raise ValueError("missing_or_duplicate_schedule_game")
            game_ids.add(game_id)
            ended = _time(row.get("ended_at"))
            if ended >= cutoff or ended > _time(opportunities.observed_at):
                raise ValueError("schedule_game_not_earlier")
            games.append((ended, row))
        if set(by_game) - game_ids:
            raise ValueError("statistics_game_not_in_complete_schedule")
        games.sort(key=lambda pair: pair[0], reverse=True)
        selected = []
        for _, game in games:
            record = by_game.get(game["game_id"])
            if record is None:
                raise ValueError("intervening_missing_statistics:" + game["game_id"])
            for key in ("game_id", "team", "opponent", "week", "ended_at"):
                if record.get(key) != game.get(key):
                    raise ValueError("schedule_statistics_identity_mismatch:" + key)
            if (record.get("source_ref") != statistics.reference
                    or record.get("season") != context["season"]
                    or record.get("period") != context["period"]):
                raise ValueError("statistics_source_or_period_mismatch")
            available = _time(record.get("stats_observed_at"))
            if not _time(record["ended_at"]) <= available <= _time(statistics.observed_at):
                raise ValueError("statistics_availability_clock_mismatch")
            if record.get("participation") == "dnp":
                continue
            if record.get("participation") != "played":
                raise ValueError("intervening_unknown_participation:" + game["game_id"])
            selected.append(record)
            if len(selected) == 3:
                break
        selected_ids = tuple(row["game_id"] for row in selected)
        result = evaluate_core(context, selected)
        if result.state != "CANDIDATE_ARITHMETIC":
            return ReceivingResult(result.value, result.state, result.reason, selected_ids)
        return ReceivingResult(result.value, "CANDIDATE_ARITHMETIC",
                               "latest_three_pinned_appearances_complete_sequence", selected_ids)
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        return fallback(str(exc))


def reception_half_adjustment(raw: Any, unchanged_adjusted: Any) -> Decimal:
    """Frozen arithmetic only; no capture, backfill, restart or official recorder."""
    from .retained.receiving_yards_core_draft import _number
    raw_value = _number(raw)
    adjusted_value = _number(unchanged_adjusted)
    return raw_value + Decimal("0.5") * (adjusted_value - raw_value)
