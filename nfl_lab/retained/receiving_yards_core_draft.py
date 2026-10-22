"""New research arithmetic core. NOT a recovered, registered or validated model.

The caller MUST separately qualify exactly the latest three eligible prior
appearances and the same-cutoff original projections. This module cannot verify
that source records are authentic or that omitted earlier opportunities exist.
No network, training, outcome scoring, registry, or issuance functions are present.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Mapping, Sequence

VERSION = 'rec-ypt-core-draft-20261022-01'


@dataclass(frozen=True)
class Result:
    value: Decimal | None
    state: str
    reason: str
    version: str = VERSION
    evidence_tier: str = 'ARITHMETIC_CORE_ONLY_NOT_SOURCE_QUALIFIED'


def _number(value: Any, *, integer: bool = False, nonnegative: bool = False) -> Decimal:
    # Source numeric types only; reject string coercion and bool-as-int.
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError('not_numeric')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('not_numeric') from exc
    if not number.is_finite():
        raise ValueError('nonfinite')
    if integer and number != number.to_integral_value():
        raise ValueError('not_integer')
    if nonnegative and number < 0:
        raise ValueError('negative_count')
    return number


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError('missing_time')
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid_time') from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('naive_time')
    return stamp


def _id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('missing_identity')
    return value


def evaluate_core(context: Mapping[str, Any], selected_history: Sequence[Mapping[str, Any]]) -> Result:
    """Evaluate an already-selected triple without fitting or replacing history.

    Context keys: player_id, game_id, team, opponent, period, season, week,
    cutoff_at, kickoff_at, projection_observed_at, website_yards,
    projected_targets, projection_source_ref.

    History keys: same identities plus ended_at, stats_observed_at,
    participation='played', targets, yards, source_ref. Exactly three records,
    newest first, are required. Missing/invalid selected input causes unchanged
    website fallback; another older game is never substituted by this core.

    Source refs are provenance pointers, NOT authentication. Neither internal
    consistency nor this result establishes full input eligibility or issuance.
    """
    def abstain(reason: str) -> Result:
        return Result(None, 'ABSTAIN', reason)

    if not isinstance(context, Mapping):
        return abstain('invalid_context')
    # Without a valid target identity, cutoff and original baseline this core
    # cannot safely attach even a fallback to a real forecast opportunity.
    try:
        for key in ('player_id', 'game_id', 'team', 'opponent', 'period', 'projection_source_ref'):
            _id(context.get(key))
        if context['team'] == context['opponent']:
            raise ValueError('same_teams')
        season = _number(context.get('season'), integer=True, nonnegative=True)
        week = _number(context.get('week'), integer=True, nonnegative=True)
        if season == 0 or week == 0:
            raise ValueError('invalid_period')
        cutoff = _time(context.get('cutoff_at'))
        kickoff = _time(context.get('kickoff_at'))
        observed = _time(context.get('projection_observed_at'))
        if not observed <= cutoff < kickoff:
            raise ValueError('late_projection_or_cutoff')
        baseline = _number(context.get('website_yards'))
    except (KeyError, ValueError) as exc:
        return abstain(str(exc))

    def fallback(reason: str) -> Result:
        return Result(baseline, 'UNCHANGED_WEBSITE_FALLBACK', reason)

    try:
        projected_targets = _number(context.get('projected_targets'), nonnegative=True)
    except ValueError as exc:
        return fallback('projected_targets:' + str(exc))
    if not isinstance(selected_history, (list, tuple)) or len(selected_history) != 3:
        return fallback('exactly_three_selected_appearances_required')

    seen_games: set[str] = set()
    targets: list[Decimal] = []
    yards: list[Decimal] = []
    previous_end: datetime | None = None
    for row in selected_history:
        try:
            if not isinstance(row, Mapping):
                raise ValueError('invalid_history_row')
            game_id = _id(row.get('game_id'))
            if game_id == context['game_id'] or game_id in seen_games:
                raise ValueError('target_or_duplicate_game')
            seen_games.add(game_id)
            for key in ('player_id', 'team', 'period'):
                if _id(row.get(key)) != context[key]:
                    raise ValueError('history_identity_mismatch')
            if _id(row.get('opponent')) == row['team']:
                raise ValueError('same_history_teams')
            _id(row.get('source_ref'))
            if _number(row.get('season'), integer=True) != season:
                raise ValueError('history_season_mismatch')
            history_week = _number(row.get('week'), integer=True, nonnegative=True)
            if not 0 < history_week < week:
                raise ValueError('history_week_not_earlier')
            ended = _time(row.get('ended_at'))
            available = _time(row.get('stats_observed_at'))
            if not ended <= available <= cutoff or not ended < cutoff:
                raise ValueError('history_not_available_by_cutoff')
            if previous_end is not None and not ended < previous_end:
                raise ValueError('history_not_strictly_newest_first')
            previous_end = ended
            if row.get('participation') != 'played':
                raise ValueError('selected_appearance_not_confirmed_played')
            targets.append(_number(row.get('targets'), integer=True, nonnegative=True))
            yards.append(_number(row.get('yards'), integer=True))
        except (KeyError, ValueError) as exc:
            return fallback(str(exc))

    if sum(targets) <= 0:
        return fallback('pooled_targets_not_positive')
    # Signed yards, fractional point forecasts and supported zero target
    # forecasts are kept. No rounding, nonnegative-yard clamp or target haircut.
    # A zero-target historical record with yards is NOT rejected automatically;
    # its source accounting must be qualified outside this arithmetic core.
    with localcontext() as decimal_context:
        decimal_context.prec = 40
        value = projected_targets * sum(yards) / sum(targets)
    if not value.is_finite():
        return fallback('nonfinite_arithmetic')
    return Result(value, 'CANDIDATE_ARITHMETIC', 'prequalified_triple_assumed_not_verified')
