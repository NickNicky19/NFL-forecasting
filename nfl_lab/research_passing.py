"""Explicit opt-in pooled-H3 YPA reconstruction; never a daily/default model.

Source pins authenticate caller-supplied bytes, not provider truth/publication.
The original missing runner is not recovered by this separately versioned code.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

from .receiving import SourceDocument, _document, _time
from .state import digest

METHOD = "website-held-attempts-h3-ypa-research-v1"
SOURCE_RECIPE = "fixed_methods.py:rate_candidate; SHA256 0f4bbc4a253f6fdebc1f861ba321209805a9609f50c88b97c3613165eb6cd2b6"
CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
IDENTITY = ("player_id", "game_id", "team", "opponent", "season", "season_type", "week", "period")


def _number(value: Any, *, count: bool = False, nonnegative: bool = False) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)) or not math.isfinite(float(value)):
        raise ValueError("missing_or_invalid_numeric_field")
    result = Fraction(str(value))
    if count and (result < 0 or result.denominator != 1):
        raise ValueError("invalid_attempt_count")
    if nonnegative and result < 0:
        raise ValueError("negative_held_attempt_projection")
    return result


def pooled_point(held_attempts: Any, selected: list[Mapping[str, Any]]) -> float:
    """Arithmetic only. Caller must qualify the exact selected history first."""
    held = _number(held_attempts, nonnegative=True)
    if len(selected) != 3:
        raise ValueError("exactly_three_selected_appearances_required")
    yards, attempts = Fraction(0), Fraction(0)
    for row in selected:
        y, a = _number(row.get("pass_yd")), _number(row.get("pass_att"), count=True)
        if a == 0 and y != 0:
            raise ValueError("zero_attempt_nonzero_passing_yards")
        yards += y
        attempts += a
    if attempts <= 0:
        raise ValueError("nonpositive_pooled_attempts")
    value = float(held * yards / attempts)
    if not math.isfinite(value):
        raise ValueError("nonfinite_arithmetic")
    return value


@dataclass(frozen=True)
class ResearchPoint:
    method: str
    point: float | None
    state: str
    reason: str
    history_game_ids: tuple[str, ...]
    context: dict
    calculated_at: str
    calculation_lane: str
    input_sha256: str
    source_sha256: dict
    code_sha256: str = CODE_SHA256
    point_semantics: str = "fixed_opportunity_rate_point; mean_or_median_unverified"
    target: str = "pass_yd"
    qualified_for_default: bool = False
    original_runner_reproduced: bool = False
    recorded_pregame: bool = False
    upstream_publication_verified: bool = False
    uncertainty: None = None

    def to_dict(self) -> dict:
        return {**asdict(self), "history_game_ids": list(self.history_game_ids)}


def evaluate(context: Mapping[str, Any], *, opportunities: SourceDocument,
             statistics: SourceDocument, projection: SourceDocument,
             trusted_hashes: Mapping[str, str]) -> ResearchPoint:
    """Evaluate exactly three current-team/season appearances or literal fallback.

    Projection is an explicitly extracted same-receipt unchanged website point
    pair, not a challenger attempt forecast. Opportunities cover every earlier
    week, including byes/not-rostered states; unknown intervening participation
    or fields stops the scan. Signed passing yards remain legal.

    This function records an actual calculation clock, never forecast issuance.
    No source request, persistence, fitting or scheduler is invoked.
    """
    actual_now = datetime.now(timezone.utc)
    docs = (opportunities, statistics, projection)
    hashes = {d.reference: hashlib.sha256(d.payload).hexdigest()
              for d in docs if isinstance(d, SourceDocument) and isinstance(d.reference, str) and isinstance(d.payload, bytes)}
    def metadata(value):
        if isinstance(value, Real) and not math.isfinite(float(value)):
            return None
        return value if isinstance(value, (str, bool, int, float, type(None))) else repr(value)
    identity = {k: metadata(context.get(k)) for k in (*IDENTITY, "cutoff_at", "kickoff_at", "baseline_receipt_sha256")}
    source_bindings = {
        role: {"reference": metadata(d.reference),
               "payload_sha256": hashlib.sha256(d.payload if isinstance(d.payload, bytes) else repr(d.payload).encode()).hexdigest(),
               "payload_type": type(d.payload).__name__, "observed_at": metadata(d.observed_at), "time_basis": metadata(d.time_basis)}
        if isinstance(d, SourceDocument) else {"invalid_source_type": type(d).__name__}
        for role, d in zip(("opportunities", "statistics", "projection"), docs)
    }
    pin_manifest_sha256 = hashlib.sha256(json.dumps(dict(trusted_hashes), sort_keys=True, default=repr).encode()).hexdigest()
    lane = "INVALID_CONTEXT_RESEARCH"
    selected: list[Mapping[str, Any]] = []

    def result(value, state, reason):
        return ResearchPoint(METHOD, value, state, reason,
                             tuple(str(r["game_id"]) for r in selected), identity,
                             actual_now.isoformat(), lane,
                             digest({"method": METHOD, "context_json": json.dumps(dict(context), sort_keys=True, default=repr),
                                     "sources_by_role": source_bindings, "trusted_pin_manifest_sha256": pin_manifest_sha256}), hashes)

    try:
        if (any(not isinstance(d, SourceDocument) or not isinstance(d.reference, str) or not d.reference for d in docs)
                or len({d.reference for d in docs}) != 3):
            raise ValueError("invalid_or_duplicate_source_references")
        for key in ("player_id", "game_id", "team", "opponent"):
            if not isinstance(context.get(key), str) or not context[key]:
                raise ValueError("missing_identity:" + key)
        if context["team"] == context["opponent"]:
            raise ValueError("invalid_team_opponent")
        if type(context.get("season")) is not int or context["season"] < 1920 or type(context.get("week")) is not int or not 1 <= context["week"] <= 22:
            raise ValueError("invalid_season_or_week")
        if context.get("season_type") != "REG" or context.get("period") != "full_game_with_ot":
            raise ValueError("unsupported_season_type_or_period")
        cutoff, kickoff = _time(context["cutoff_at"]), _time(context["kickoff_at"])
        if cutoff >= kickoff:
            raise ValueError("cutoff_not_before_kickoff")
        lane = ("RETROSPECTIVE_ARITHMETIC" if actual_now >= kickoff else
                "AFTER_CUTOFF_UNRECORDED_ARITHMETIC" if actual_now > cutoff else
                "PREGAME_UNRECORDED_ARITHMETIC")
        original = _document(projection, trusted_hashes, cutoff)
        if _time(projection.observed_at) > actual_now:
            raise ValueError("projection_capture_is_in_future")
        for key in (*IDENTITY, "website_yards", "cutoff_at", "kickoff_at",
                    "projection_observed_at", "baseline_receipt_sha256"):
            if key not in original or original[key] != context.get(key):
                raise ValueError("original_projection_binding_mismatch:" + key)
        if original.get("website_attempts") != context.get("website_attempts"):
            raise ValueError("original_projection_binding_mismatch:website_attempts")
        receipt = original["baseline_receipt_sha256"]
        if not isinstance(receipt, str) or len(receipt) != 64 or any(c not in "0123456789abcdef" for c in receipt):
            raise ValueError("invalid_baseline_receipt_digest")
        if original.get("attempts_origin") != "same_receipt_unchanged_website":
            raise ValueError("held_attempts_are_not_original_website")
        if context.get("projection_source_ref") != projection.reference or _time(original["projection_observed_at"]) != _time(projection.observed_at):
            raise ValueError("original_projection_source_or_clock_mismatch")
        fallback = float(_number(original["website_yards"]))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        return result(None, "ABSTAIN", str(exc))

    try:
        schedule = _document(opportunities, trusted_hashes, cutoff)
        stats = _document(statistics, trusted_hashes, cutoff)
        if any(_time(d.observed_at) > actual_now for d in (opportunities, statistics)):
            raise ValueError("history_capture_is_in_future")
        for doc in (schedule, stats):
            for key in ("player_id", "season", "season_type", "period"):
                if doc.get(key) != context[key]:
                    raise ValueError("history_header_mismatch:" + key)
        if schedule.get("through_week") != context["week"] - 1:
            raise ValueError("schedule_does_not_cover_all_prior_weeks")
        weeks = schedule.get("weeks")
        if (not isinstance(weeks, list) or any(not isinstance(w, dict) or type(w.get("week")) is not int for w in weeks)
                or sorted(w["week"] for w in weeks) != list(range(1, context["week"]))):
            raise ValueError("missing_or_duplicate_prior_week")
        records = stats.get("records")
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError("invalid_history_records")
        by_game: dict[str, list] = {}
        for row in records:
            by_game.setdefault(str(row.get("game_id")), []).append(row)
        newer_kickoff = kickoff
        for game in sorted(weeks, key=lambda g: g["week"], reverse=True):
            if game.get("team") != context["team"]:
                raise ValueError("different_team_stops_spell")
            state = game.get("state")
            if state == "not_rostered":
                raise ValueError("not_rostered_stops_spell")
            if state == "bye":
                if game.get("game_id") is not None:
                    raise ValueError("bye_contains_game")
                continue
            if state != "game" or game.get("completed") is not True:
                raise ValueError("unknown_or_incomplete_prior_opportunity")
            if (not isinstance(game.get("game_id"), str) or not game["game_id"]
                    or not isinstance(game.get("opponent"), str) or not game["opponent"] or game["opponent"] == game["team"]):
                raise ValueError("missing_or_invalid_prior_game_identity")
            prior_kickoff = _time(game.get("kickoff_at"))
            final_observed = _time(game.get("final_observed_at"))
            if not prior_kickoff < newer_kickoff or not prior_kickoff < final_observed <= _time(opportunities.observed_at):
                raise ValueError("invalid_prior_chronology_or_final_clock")
            newer_kickoff = prior_kickoff
            rows = by_game.get(str(game.get("game_id")), [])
            if len(rows) != 1:
                raise ValueError("intervening_missing_or_duplicate_player_game")
            row = rows[0]
            for key in ("player_id", "season", "season_type", "period"):
                if row.get(key) != context[key]:
                    raise ValueError("history_identity_mismatch:" + key)
            for key in ("game_id", "team", "opponent", "week", "kickoff_at"):
                if row.get(key) != game.get(key):
                    raise ValueError("schedule_statistics_identity_mismatch:" + key)
            if row.get("source_ref") != statistics.reference:
                raise ValueError("history_source_pointer_mismatch")
            # A later independent final-status poll is not the actual game end.
            if not prior_kickoff < _time(row.get("stats_observed_at")) <= _time(statistics.observed_at):
                raise ValueError("history_availability_clock_mismatch")
            if row.get("participation") == "dnp":
                continue
            if row.get("participation") != "played":
                raise ValueError("intervening_unknown_participation")
            # Validate before closing H3, never replace an invalid selected game.
            a, y = _number(row.get("pass_att"), count=True), _number(row.get("pass_yd"))
            if a == 0 and y != 0:
                raise ValueError("zero_attempt_nonzero_passing_yards")
            selected.append(row)
            if len(selected) == 3:
                break
        value = pooled_point(original.get("website_attempts"), selected)
        return result(value, "CANDIDATE_ARITHMETIC", "exact_three_pooled_yards_per_attempt")
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        return result(fallback, "UNCHANGED_WEBSITE_FALLBACK", str(exc))


def main():
    parser = argparse.ArgumentParser(description="Explicit opt-in research point; no default activation, capture or source requests")
    parser.add_argument("--method", choices=[METHOD], required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text())
    documents = {name: SourceDocument(**bundle[name]) for name in ("opportunities", "statistics", "projection")}
    # Bundles use literal JSON payload strings; hashes refer to their UTF-8 bytes.
    documents = {name: SourceDocument(d.reference, d.payload.encode("utf-8"), d.observed_at, d.time_basis)
                 for name, d in documents.items()}
    result = evaluate(bundle["context"], **documents, trusted_hashes=json.loads(args.pins.read_text())).to_dict()
    body = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x") as stream:
            stream.write(body)
    else:
        print(body, end="")


if __name__ == "__main__":
    main()
