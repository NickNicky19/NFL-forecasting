"""Nick's linear chart, independent of the preserved pinned-site scorer.

Numerical scoring does not authenticate a source. The source adapter below
reports the evidence for each value and never treats omitted fields as zero.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from numbers import Real
from typing import Mapping, Sequence

SCORING_VERSION = "nick-chart-ppr-v1"
INPUT_SCHEMA = "nick-chart-ppr-components-v1"
OUTPUT_SCHEMA = "nick-chart-ppr-result-v1"
LABEL_VERSION = "nick-chart-ppr-observed-label-v1"
SOURCE_VERSION = "nick-chart-ppr-nflverse-weekly-v1"
SIGNED = frozenset({"pass_yd", "rush_yd", "rec_yd"})
RETURN_COMPONENTS = ("kick_return_td", "punt_return_td", "fg_return_td")
WEIGHTS = {"pass_yd": .04, "pass_td": 4., "pass_int": -1.,
           "rush_yd": .1, "rush_td": 6., "rec": 1., "rec_yd": .1,
           "rec_td": 6., "fum_lost": -1., "pass_2pt": 2.,
           "rush_2pt": 2., "rec_2pt": 2., "off_fum_rec_td": 6.,
           "kick_return_td": 6., "punt_return_td": 6., "fg_return_td": 6.}
NFL_FIELDS = {"pass_yd": "passing_yards", "pass_td": "passing_tds",
              "pass_int": "passing_interceptions", "rush_yd": "rushing_yards",
              "rush_td": "rushing_tds", "rec": "receptions",
              "rec_yd": "receiving_yards", "rec_td": "receiving_tds",
              "fum_lost": "fumbles_lost_total", "pass_2pt": "passing_2pt_conversions",
              "rush_2pt": "rushing_2pt_conversions", "rec_2pt": "receiving_2pt_conversions"}
IGNORED_EVENTS = frozenset({"ordinary_fumble_recovery", "forced_fumble",
                            "blocked_kick", "return_yards", "defensive_recovery_td"})
SCORER_TDS = frozenset({"rush_td", "rec_td", "off_fum_rec_td", *RETURN_COMPONENTS})


@dataclass(frozen=True)
class ReturnAggregate:
    """Caller binds an independently qualified, exactly-three-class source."""
    value: float
    qualification_id: str
    covered_components: tuple[str, ...] = RETURN_COMPONENTS


@dataclass(frozen=True)
class Score:
    value: float | None
    missing: tuple[str, ...]
    invalid: tuple[str, ...]
    product: str
    scoring_version: str = SCORING_VERSION
    output_schema: str = OUTPUT_SCHEMA

    def to_dict(self):
        return asdict(self)


def _value(value, component, *, expectation=False):
    if value is None or (isinstance(value, Real) and math.isnan(float(value))):
        return None, "missing"
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        return None, "invalid"
    number = float(value)
    if component not in SIGNED and (number < 0 or (not expectation and not number.is_integer())):
        return None, "invalid"
    return number, "supported"


def _score(components, *, expectation, aggregate=None):
    missing, invalid, terms = [], [], []
    covered = set()
    if aggregate is not None:
        if (not isinstance(aggregate, ReturnAggregate) or not aggregate.qualification_id
                or aggregate.covered_components != RETURN_COMPONENTS):
            raise ValueError("exact three-class return aggregate qualification required")
        if any(components.get(k) is not None for k in RETURN_COMPONENTS):
            raise ValueError("return aggregate and primitive return credits overlap")
        value, status = _value(aggregate.value, "return_td_aggregate", expectation=expectation)
        if status != "supported":
            (missing if status == "missing" else invalid).append("return_td_aggregate")
        else:
            terms.append(6 * value)
        covered.update(RETURN_COMPONENTS)
    for key, weight in WEIGHTS.items():
        if key in covered:
            continue
        value, status = _value(components.get(key), key, expectation=expectation)
        if status == "missing":
            missing.append(key)
        elif status == "invalid":
            invalid.append(key)
        else:
            terms.append(weight * value)
    return Score(None if missing or invalid else math.fsum(terms), tuple(missing), tuple(invalid),
                 "conditional_mean" if expectation else "observed_score")


def score_observed(components: Mapping, *, return_aggregate: ReturnAggregate | None = None) -> Score:
    """Observed event counts are integers; official yardage remains signed."""
    return _score(components, expectation=False, aggregate=return_aggregate)


def score_component_expectations(components: Mapping, *, summary_kind: str,
                                 return_aggregate: ReturnAggregate | None = None) -> Score:
    """Linear E[S]; fractional event expectations are allowed, medians are not.

    An anytime probability cannot be passed as an expected touchdown count.
    Distributional summaries require a separately qualified joint procedure.
    """
    if summary_kind != "conditional_mean":
        raise ValueError("chart expectation requires component conditional means")
    return _score(components, expectation=True, aggregate=return_aggregate)


def event_credits(events: Sequence[Mapping], *, player_id: str,
                  complete_components: Sequence[str], qualification_id: str) -> dict:
    """Normalize an already qualified event inventory, preserving unique credits.

    One credited fumble_id is counted once across phase copies. A scoring TD
    cannot be credited to two disjoint scorer classes. Passing TD credit is a
    different player statistic. No completeness is inferred from an empty list.
    """
    if not qualification_id or not set(complete_components) <= set(WEIGHTS) - SIGNED:
        raise ValueError("explicit event-inventory component qualification required")
    counts = {k: 0 for k in complete_components}
    seen, scorer_tds = {}, {}
    ignored = 0
    for event in events:
        if event.get("player_id") != player_id:
            continue
        kind = event.get("kind")
        if kind in IGNORED_EVENTS:
            ignored += 1
            continue
        if kind not in counts:
            raise ValueError("event outside qualified component inventory: " + str(kind))
        credit_id = event.get("fumble_id") if kind == "fum_lost" else event.get("event_id")
        if not isinstance(credit_id, str) or not credit_id:
            raise ValueError("unique credited event identity required")
        if kind in SCORER_TDS:
            old = scorer_tds.setdefault(credit_id, kind)
            if old != kind:
                raise ValueError("one touchdown overlaps disjoint chart categories")
        key = (kind, credit_id)
        if key not in seen:
            counts[kind] += 1
            seen[key] = True
    return {"components": counts, "qualification_id": qualification_id,
            "ignored_unlisted_events": ignored, "unique_scoring_credits": len(seen)}


def nflverse_components(stats: Mapping, *, source_ref: Mapping,
                       broad_zero_contract: Mapping | None = None,
                       event_components: Mapping | None = None) -> dict:
    """Explicit common fields plus independently qualified rare-event evidence.

    The inspected generator's fumble_recovery_tds contains all recovery TD
    credits (including lateral recipients). Its special_teams_tds includes
    kick/punt/other special-play TDs and is NOT the chart return aggregate.
    A qualified complete nonnegative superset equal to zero proves subset
    zeros; positive supersets require classification, with no event-free study.
    """
    if not source_ref.get("sha256") or not source_ref.get("qualification_id"):
        raise ValueError("authenticated source reference and qualification ID required")
    values, coverage = {}, {}
    for component in WEIGHTS:
        field = NFL_FIELDS.get(component)
        if field:
            values[component], status = _value(stats.get(field), component)
            coverage[component] = {"status": status, "source_field": field}
        else:
            values[component] = None
            coverage[component] = {"status": "unqualified_event_classification"}
    contract = broad_zero_contract or {}
    if contract:
        if (contract.get("version") != "nflverse-chart-broad-zero-v1"
                or not contract.get("qualification_id") or not contract.get("present_group_complete")
                or not contract.get("return_superset_contains_all_three_classes")
                or not contract.get("recovery_superset_includes_lateral_td_recipients")):
            raise ValueError("complete present-group broad-zero contract required")
        for field, keys in [("fumble_recovery_tds", ("off_fum_rec_td",)),
                            ("special_teams_tds", RETURN_COMPONENTS)]:
            value, status = _value(stats.get(field), "td_count")
            for key in keys:
                if status == "supported" and value == 0:
                    values[key] = 0.
                    coverage[key] = {"status": "qualified_superset_zero", "source_field": field,
                                     "qualification_id": contract["qualification_id"]}
                else:
                    coverage[key] = {"status": "positive_superset_requires_classification" if status == "supported"
                                     else status, "source_field": field}
    for key, evidence in (event_components or {}).items():
        if key not in WEIGHTS or key in NFL_FIELDS:
            raise ValueError("rare event component mapping required")
        if not evidence.get("qualification_id"):
            raise ValueError("rare event classification qualification required")
        value, status = _value(evidence.get("value"), key)
        if values[key] is not None and value != values[key]:
            raise ValueError("event and complete aggregate-zero evidence conflict")
        values[key] = value
        coverage[key] = {"status": status, "qualification_id": evidence["qualification_id"]}
    scored = score_observed(values)
    return {"source_adapter": SOURCE_VERSION, "input_schema": INPUT_SCHEMA,
            "source_ref": dict(source_ref), "components": values, "coverage": coverage,
            "score": scored.to_dict(), "label_version": LABEL_VERSION}


def label_observation(bundle: Mapping, *, identity: Mapping, participation: str,
                      participation_evidence: str | None) -> dict:
    """Keep every planned row, including DNP, played-missing and unknown."""
    keys = ("player_id", "game_id", "team", "opponent", "season", "week", "season_type")
    if any(identity.get(k) is None or str(identity[k]).strip() == "" for k in keys):
        raise ValueError("complete canonical player/game/team/opponent/period identity required")
    if participation not in {"played", "dnp", "unknown"}:
        raise ValueError("explicit participation state required")
    if participation != "unknown" and not participation_evidence:
        raise ValueError("played/DNP requires independent evidence")
    score = bundle["score"]
    value = score["value"] if participation == "played" else None
    state = ("played_missing" if value is None else "played_zero" if value == 0 else "played_score")
    if participation != "played":
        state = "known_dnp" if participation == "dnp" else "unknown_participation"
    if participation == "dnp" and any(v not in (None, 0) for v in bundle["components"].values()):
        state = "participation_conflict"
    return {"identity": dict(identity), "scoring_version": SCORING_VERSION,
            "label_version": LABEL_VERSION, "state": state, "value": value,
            "participation_evidence": participation_evidence,
            "missing_components": list(score["missing"]), "invalid_components": list(score["invalid"]),
            "components": dict(bundle["components"]), "coverage": dict(bundle["coverage"])}
