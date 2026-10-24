"""Causal P0--P4 selection over authenticated flat forecasts, never a model runner.

Uses the existing canonical identities, UTC parser and immutable storage seam.
Rows are conditional on played. Missing grades never become zero outcomes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter, OrderedDict
from pathlib import Path
from types import MappingProxyType

from .state import canonical, digest, save, utc

VERSION = "weekly-adaptive-release-v1"
IMPLEMENTATION_REVISION = 2
PRODUCTS = {"point_mean": ("point_mse", "expected_mean"),
            "point_median": ("point_mae", "intended_median"),
            "binary_probability": ("brier", "event_probability")}
GRID = ((1, 0.), (1, .005), (4, 0.), (4, .005))
STARTUP = (4, 0.)
ANYTIME_EVENT_CONTRACT = "anytime_rush_or_receive_td"
REPLAY_HORIZON = "reconstructed_kickoff"
REPLAY_HORIZON_VERSION = "reconstructed-kickoff-horizon-v1"
EVIDENCE_CACHE_BYTES = 4 * 1024 * 1024
EVIDENCE_CACHE_ENTRIES = 64
POLICY = dict(schema_version=VERSION, policies=["P0", "P1", "P2", "P3", "P4"],
              implementation_revision=IMPLEMENTATION_REVISION,
              choice_clock="weekly_decision_cutoff_utc; independent_of_current_week_forecasts",
              materialization_clock="authentic_per_game_cutoff_utc; never_reselect_after_choice",
              initial_online_category_method_cap=4,
              p3_grid=[dict(half_life_weeks=h, switch_margin=m) for h, m in GRID],
              p3_minimum_earlier_validation_folds=2,
              startup=dict(half_life_weeks=4, switch_margin=0.),
              ties="current_if_best_then_reference_then_stable_method_id",
              p2_period="current_season_all_earlier_completed_graded_slates",
              loss_weighting="equal_row_weight; P3 multiplies by 2**(-week_age/half_life)",
              p4="prespecified_equal_weights; unavailable_member_uses_reference_without_reweighting",
              full_cdf_blend="UNSUPPORTED", exact_PPR="BLOCKED_LABEL_CONTRACT")
LANES = {"original_pregame", "credible_asof_reconstruction",
         "current_vintage_availability_uncertain"}


def offered_id(row):
    return digest({k: row[k] for k in ("season", "week", "game_id", "player_id", "category")})


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _loss(prediction, actual, metric):
    # Same row losses as the common point/Bernoulli evaluator; no distribution
    # is constructed for count objectives or signed point heuristics.
    delta = prediction - actual
    value = abs(delta) if metric == "point_mae" else delta * delta
    if not math.isfinite(value):
        raise ValueError("nonfinite proper point loss; no clipping or row deletion")
    return value


def _key(row):
    return row["category"], row["season"], row["week"], row["slate_id"]


def procedure_catalog(catalog):
    """Freeze recipes/capabilities, independently of later fitted artifact pins."""
    fields = ("procedure_version", "registered_at", "retired_at", "retirement_kind",
              "retirement_reason", "procedure_operational_eligible", "procedure_replay_eligible",
              "role", "training_state", "control_policy_sha256", "control_source_version", "event_contract")
    return dict(schema_version=catalog["schema_version"], categories=catalog["categories"],
                replay_catalog_frozen=catalog.get("replay_catalog_frozen", False),
                replay_availability_policy_sha256=catalog.get("replay_availability_policy_sha256"),
                methods={name: {key: value[key] for key in fields if key in value} for name, value in catalog["methods"].items()})


class Panel:
    """A single versioned catalog plus append-only forecast/grade snapshots.

    Offers are independent of method coverage. A method missing any original
    offer cannot compete on a smaller/easier cohort. It remains in the catalog.
    """

    def __init__(self, bundle, catalog, *, cache_bytes=EVIDENCE_CACHE_BYTES):
        if catalog.get("schema_version") != VERSION or bundle.get("schema_version") != VERSION:
            raise ValueError("versioned weekly contract required")
        if type(cache_bytes) is not int or not 0 <= cache_bytes <= EVIDENCE_CACHE_BYTES:
            raise ValueError("evidence cache must fit the finite four-MiB ceiling")
        self.bundle, self.catalog = dict(bundle), copy.deepcopy(catalog)
        catalog = self.catalog
        self._cache_limit, self._cache_bytes = cache_bytes, 0
        self._evidence_cache = OrderedDict()
        self._cache_counts = Counter()
        self.methods, self.categories = catalog["methods"], catalog["categories"]
        if not 1 <= len(self.methods) <= 16 or not 1 <= len(self.categories) <= 12 or len(bundle["offers"]) > 100_000:
            raise ValueError("finite panel bound exceeded")
        if len(bundle["forecasts"]) > 1_600_000 or len(bundle["outcomes"]) > 1_600_000:
            raise ValueError("finite row bound exceeded")
        self.offers, self.forecasts, self.outcomes = {}, {}, {}
        self.weeks = {}
        self.decision_contracts = {}
        if (bundle.get("replay_horizon") is not None or bundle.get("replay_horizon_version") is not None) and (
                bundle.get("replay_horizon") != REPLAY_HORIZON or
                bundle.get("replay_horizon_version") != REPLAY_HORIZON_VERSION):
            raise ValueError("explicit versioned reconstructed kickoff horizon required")
        for decision in bundle["decisions"]:
            key = _key(decision)
            if key in self.decision_contracts:
                raise ValueError("duplicate weekly decision contract")
            self.decision_contracts[key] = dict(decision)
            if decision.get("replay_horizon") is not None or decision.get("replay_horizon_version") is not None:
                self.validate_replay_horizon(decision)
        for name, spec in self.methods.items():
            if not name or not isinstance(spec.get("model_versions"), list) or not all(isinstance(v, str) and v for v in spec["model_versions"]):
                raise ValueError("exact model artifact versions required")
            utc(spec["registered_at"])
            if not isinstance(spec.get("procedure_version"), str) or not spec["procedure_version"]:
                raise ValueError("frozen model procedure version required independently of artifact")
            if spec.get("retired_at") and not spec.get("retirement_reason"):
                raise ValueError("retirement requires a recorded defect/data/resource reason")
            if spec.get("retired_at") and spec.get("retirement_kind") not in {"defect", "data", "resource"}:
                raise ValueError("one negative week is not a retirement category")
        for target, spec in self.categories.items():
            if target == "fantasy_ppr":
                if spec.get("state") != "BLOCKED_LABEL_CONTRACT":
                    raise ValueError("exact PPR remains label blocked")
                continue
            if spec.get("state") != "READY" or spec["product"] not in PRODUCTS or spec["primary_metric"] != PRODUCTS[spec["product"]][0]:
                raise ValueError("registered product/metric mismatch")
            if spec["support"] not in {"count", "signed_integer", "bernoulli"}:
                raise ValueError("unsupported outcome support")
            expected = {"count": "point_mean", "signed_integer": "point_median", "bernoulli": "binary_probability"}
            if spec["product"] != expected[spec["support"]]:
                raise ValueError("support/product mismatch")
            if spec["reference_id"] not in {"LAB_CDF", "R0"} or spec["reference_id"] not in self.methods or not spec["shortlist"] or len(set(spec["shortlist"])) != len(spec["shortlist"]):
                raise ValueError("fixed reference and unique prespecified shortlist required")
            if not set(spec["shortlist"]) <= set(self.methods):
                raise ValueError("unregistered shortlist member")
            eligible = spec.get("eligible_methods", list(dict.fromkeys([spec["reference_id"], *spec["shortlist"]])))
            if (not eligible or len(eligible) != len(set(eligible)) or not set(eligible) <= set(self.methods)
                    or spec["reference_id"] not in eligible or not set(spec["shortlist"]) <= set(eligible)):
                raise ValueError("explicit registered category selection universe required")
            if spec["support"] == "bernoulli" and "RAW" in eligible:
                raise ValueError("raw count/point provider output is not a TD event probability")
        for offer in bundle["offers"]:
            if (type(offer["season"]) is not int or type(offer["week"]) is not int
                    or not 1 <= offer["week"] <= 22 or not 1900 <= offer["season"] <= 2200
                    or any(not isinstance(offer[k], str) or not offer[k] for k in ("game_id", "player_id", "slate_id"))):
                raise ValueError("explicit season/week/slate/player-game identity required")
            identity = offered_id(offer)
            if offer["offered_id"] != identity or identity in self.offers:
                raise ValueError("changed/duplicate offered identity")
            if offer["category"] not in self.categories or offer["horizon"] != "player_game":
                raise ValueError("unknown category or horizon")
            cutoff, kickoff = utc(offer["cutoff_utc"]), utc(offer["kickoff_utc"])
            if cutoff > kickoff:
                raise ValueError("per-game cutoff after kickoff")
            if cutoff == kickoff:
                decision = self.decision_contracts.get(_key(offer))
                if decision is None or not self.reconstructed_kickoff(decision):
                    raise ValueError("kickoff equality requires a bound reconstructed kickoff decision")
            self.offers[identity] = dict(offer)
        for row in bundle["forecasts"]:
            identity, method = row["offered_id"], row["method_id"]
            if identity not in self.offers or method not in self.methods:
                raise ValueError("unregistered forecast identity/method")
            if (identity, method) in self.forecasts:
                raise ValueError("duplicate forecast; append new catalog/artifact snapshot instead")
            offer = self.offers[identity]
            for name in ("category", "season", "week", "slate_id", "horizon", "cutoff_utc", "kickoff_utc", "game_id", "player_id"):
                if row[name] != offer[name]:
                    raise ValueError("forecast/offer contract mismatch: " + name)
            if row["evidence_lane"] not in LANES:
                raise ValueError("explicit evidence lane required")
            if utc(offer["cutoff_utc"]) == utc(offer["kickoff_utc"]) and (
                    row["evidence_lane"] != self.decision_contracts[_key(offer)]["evidence_lane"]
                    or row["evidence_lane"] == "original_pregame"):
                raise ValueError("kickoff horizon forecast lane differs from bound reconstruction decision")
            if row["model_version"] not in self.methods[method]["model_versions"]:
                raise ValueError("unbound model artifact version")
            if row.get("procedure_version") != self.methods[method]["procedure_version"]:
                raise ValueError("forecast artifact uses a different frozen model procedure")
            utc(row["issued_at"])
            self.forecasts[identity, method] = dict(row)
        for outcome in bundle["outcomes"]:
            if outcome["offered_id"] not in self.offers:
                raise ValueError("outcome outside original offers")
            if outcome["participation_state"] not in {"played", "DNP", "unknown"}:
                raise ValueError("unknown participation state")
            if type(outcome["revision"]) is not int or outcome["revision"] < 1:
                raise ValueError("append-only positive outcome revision required")
            utc(outcome["available_at"])
            rows = self.outcomes.setdefault(outcome["offered_id"], [])
            if any(r["revision"] == outcome["revision"] for r in rows):
                raise ValueError("duplicate/conflicting outcome revision")
            rows.append(dict(outcome))
        for rows in self.outcomes.values():
            rows.sort(key=lambda r: r["revision"])
            if any(utc(a["available_at"]) >= utc(b["available_at"]) for a, b in zip(rows, rows[1:])):
                raise ValueError("correction revision availability must increase")
            clocks = [self.available_clock(r, "credible_asof_reconstruction") for r in rows]
            if any(a >= b for a, b in zip(clocks, clocks[1:])):
                raise ValueError("replay revision clocks must increase; corrected labels cannot backfill an earlier grade")
        for week in bundle["weeks"]:
            k = _key(week)
            if k in self.weeks:
                raise ValueError("duplicate completed-week record")
            if utc(week["completed_at"]) > utc(week["grade_completed_at"]):
                raise ValueError("grading precedes completion")
            if utc(week["weekly_decision_cutoff_utc"]) >= utc(week["slate_first_kickoff_utc"]):
                raise ValueError("weekly procedure choice must precede the slate")
            if (week.get("replay_grade_completed_at") and
                    self.available_clock(week, "credible_asof_reconstruction", actual="grade_completed_at", replay="replay_grade_completed_at") < utc(week["completed_at"])):
                raise ValueError("assumed replay grading cannot precede completed slate")
            self.weeks[k] = dict(week)
        week_counts = Counter((w["category"], w["season"]) for w in self.weeks.values())
        if len({w["season"] for w in self.weeks.values()}) > 32 or any(n > 30 for n in week_counts.values()):
            raise ValueError("finite weekly history bound exceeded")
        self.offers = MappingProxyType({key: MappingProxyType(row) for key, row in self.offers.items()})
        groups = {}
        for row in self.offers.values():
            groups.setdefault(_key(row), []).append(row)
        self._offers_by_key = {key: tuple(sorted(rows, key=lambda r: r["offered_id"])) for key, rows in groups.items()}
        self.forecasts = MappingProxyType({key: MappingProxyType(row) for key, row in self.forecasts.items()})
        self.outcomes = MappingProxyType({key: tuple(MappingProxyType(row) for row in rows) for key, rows in self.outcomes.items()})
        self.weeks = MappingProxyType({key: MappingProxyType(row) for key, row in self.weeks.items()})

    def reconstructed_kickoff(self, decision):
        return (self.bundle.get("replay_horizon") == REPLAY_HORIZON
                and self.bundle.get("replay_horizon_version") == REPLAY_HORIZON_VERSION
                and decision.get("replay_horizon") == REPLAY_HORIZON
                and decision.get("replay_horizon_version") == REPLAY_HORIZON_VERSION
                and decision.get("evidence_lane") in LANES - {"original_pregame"})

    def validate_replay_horizon(self, decision):
        bound = self.decision_contracts.get(_key(decision))
        if not self.reconstructed_kickoff(decision) or bound is None or any(
                decision.get(k) != bound.get(k) for k in ("replay_horizon", "replay_horizon_version",
                "evidence_lane", "weekly_decision_cutoff_utc", "slate_first_kickoff_utc", "horizon")):
            raise ValueError("reconstructed kickoff horizon must match frozen bundle/decision/lane")

    def available_clock(self, row, lane, *, actual="available_at", replay="replay_available_at"):
        if lane != "original_pregame" and row.get(replay) is not None:
            policy = self.catalog.get("replay_availability_policy_sha256")
            if (not isinstance(policy, str) or len(policy) != 64 or any(c not in "0123456789abcdef" for c in policy)
                    or row.get("replay_availability_policy_sha256") != policy
                    or row.get("replay_availability_uncertain") is not True):
                raise ValueError("replay availability needs an exact frozen policy and explicit uncertainty")
            return utc(row[replay])
        return utc(row[actual])

    def grade(self, identity, cutoff, lane="original_pregame"):
        rows = [r for r in self.outcomes.get(identity, ()) if self.available_clock(r, lane) < utc(cutoff)]
        return dict(max(rows, key=lambda r: r["revision"])) if rows else None

    def valid_actual(self, actual, category):
        if not _finite(actual) or actual != math.floor(actual):
            return False
        support = self.categories[category]["support"]
        return actual >= 0 if support == "count" else actual in (0, 1) if support == "bernoulli" else True

    def procedure_available(self, method, decision):
        """Weekly choice eligibility depends on catalog/clock, never new forecasts."""
        category = self.categories[decision["category"]]
        universe = category.get("eligible_methods", list(dict.fromkeys([category["reference_id"], *category["shortlist"]])))
        if method not in self.methods or method not in universe:
            return False
        spec = self.methods[method]
        cutoff = utc(decision["weekly_decision_cutoff_utc"])
        if spec.get("retired_at") and utc(spec["retired_at"]) <= cutoff:
            return False
        if decision["evidence_lane"] == "original_pregame":
            return spec.get("procedure_operational_eligible") is True and utc(spec["registered_at"]) < cutoff
        return (method not in {"R0", "RAW"} and spec.get("procedure_replay_eligible") is True
                and self.catalog.get("replay_catalog_frozen") is True)

    def eligible(self, method, offer, lane):
        """Per-game materialization eligibility, separate from weekly choice."""
        if method in {"R0", "RAW"} and lane != "original_pregame":
            return False
        spec = self.methods[method]
        cutoff = utc(offer["cutoff_utc"])
        kickoff = utc(offer["kickoff_utc"])
        if cutoff > kickoff:
            return False
        if cutoff == kickoff:
            bound = self.decision_contracts.get(_key(offer))
            if lane == "original_pregame" or bound is None or not self.reconstructed_kickoff(bound) or bound["evidence_lane"] != lane:
                return False
        if (spec.get("retired_at") and utc(spec["retired_at"]) <= cutoff):
            return False
        row = self.forecasts.get((offer["offered_id"], method))
        if row is None or row["evidence_lane"] != lane:
            return False
        category = self.categories[offer["category"]]
        product = category["product"]
        unknown_control = (row.get("prediction_functional") == "legacy_unknown" and method in {"R0", "RAW"}
                           and product != "binary_probability")
        if (row.get("product") != product and not (unknown_control and row.get("product") == "point_legacy")) or not _finite(row.get("forecast_value")):
            return False
        functional = row.get("prediction_functional")
        if functional != PRODUCTS[product][1] and not unknown_control:
            return False
        value = row["forecast_value"]
        if (product == "point_mean" and value < 0) or (product == "binary_probability" and not 0 <= value <= 1):
            return False
        reference = category["reference_id"]
        if method == "RAW" and row.get("reference_stream") not in {"direct_provider_raw", "site_extracted_raw_sleeper"}:
            return False
        if method == reference:
            expected = "live_R0" if method == "R0" else "historical_LAB_CDF"
            if row.get("reference_stream") != expected:
                return False
        if row.get("training_state") == "UPSTREAM_TRAINING_UNOBSERVED":
            # Observing an authentic control point is not a trained-candidate
            # capability claim. Only these exact IDs/roles have this contract.
            if (lane != "original_pregame" or method not in {"R0", "RAW"}
                    or spec.get("role") not in {"reference", "raw_control"}
                    or spec.get("training_state") != "UPSTREAM_TRAINING_UNOBSERVED"
                    or not _sha(spec.get("control_policy_sha256"))
                    or row.get("control_policy_sha256") != spec["control_policy_sha256"]
                    or not spec.get("control_source_version")
                    or row.get("control_source_version") != spec["control_source_version"]
                    or not _sha(row.get("source_receipt_sha256"))
                    or not row.get("source_capture_completed_at")):
                return False
            if product != "binary_probability" and not unknown_control:
                return False  # A proprietary observed point does not become a mean/median.
            if product == "binary_probability" and (method != "R0" or row.get("saved_event_probability") is not True
                    or row.get("event_contract") != ANYTIME_EVENT_CONTRACT
                    or spec.get("event_contract") != ANYTIME_EVENT_CONTRACT
                    or category.get("event_contract") != ANYTIME_EVENT_CONTRACT):
                return False
            return (row.get("operational_eligible") is True and utc(spec["registered_at"]) < cutoff
                    and utc(row["source_capture_completed_at"]) <= utc(row["issued_at"]) <= cutoff)
        if not row.get("training_cutoff_utc") or utc(row["training_cutoff_utc"]) > cutoff:
            return False
        if row.get("training_max_available_utc") and utc(row["training_max_available_utc"]) >= utc(row["training_cutoff_utc"]):
            return False
        if lane == "original_pregame":
            required = ("training_max_available_utc", "training_started_at", "training_completed_at",
                        "training_source_capture_completed_at", "source_capture_completed_at")
            if any(not row.get(k) for k in required):
                return False  # Unknown archived fit clocks cannot qualify live issuance.
            issued, started, completed = map(utc, (row["issued_at"], row["training_started_at"], row["training_completed_at"]))
            return (row.get("operational_eligible") is True and utc(spec["registered_at"]) < cutoff
                    and utc(row["training_source_capture_completed_at"]) <= started <= completed <= issued < cutoff
                    and utc(row["training_max_available_utc"]) < started
                    and utc(row["source_capture_completed_at"]) <= issued)
        # Replay is never relabelled a contemporary issuance or operational PASS.
        return (row.get("replay_eligible") is True and self.catalog.get("replay_catalog_frozen") is True and
                row.get("replay_cutoff_utc") == offer["cutoff_utc"] and row.get("frozen_before_grading") is True)

    def offers_for(self, key):
        self._cache_counts["offer_index_lookups"] += 1
        return self._offers_by_key.get(key, ())

    def cache_receipt(self):
        """Operational counters only; they never enter choices or score results."""
        return dict(payload_and_key_budget_bytes=self._cache_limit, charged_retained_bytes=self._cache_bytes,
                    retained_entries=len(self._evidence_cache), maximum_entries=EVIDENCE_CACHE_ENTRIES,
                    indexed_offers=len(self.offers), indexed_slates=len(self._offers_by_key),
                    counters=dict(self._cache_counts), semantics="bounded JSON snapshots; no disk cache; decoded working RSS separately guarded")

    def evidence(self, decision, history):
        """One reference-defined offered/grade cohort; no entrant shrinkage."""
        history = tuple(history)
        # The panel is an immutable snapshot. Exact decision cutoff, lane and
        # history metadata bind the latest eligible correction versions; a new
        # outcome/catalog snapshot requires a new Panel, not cache invalidation.
        key = digest(dict(decision)), digest([dict(w) for w in history])
        if self._cache_limit and key in self._evidence_cache:
            self._cache_counts["evidence_hits"] += 1
            body, _ = self._evidence_cache.pop(key)
            self._evidence_cache[key] = body, len(body) + 512
            value = json.loads(body)
            return value["losses"], value["audit"]
        self._cache_counts["evidence_misses"] += 1
        losses, audit = self._compute_evidence(decision, history)
        if self._cache_limit:
            body = canonical(dict(losses=losses, audit=audit))
            charge = len(body) + 512  # conservative bounded key/LRU-entry allowance
            if charge <= self._cache_limit:
                while self._evidence_cache and (self._cache_bytes + charge > self._cache_limit or len(self._evidence_cache) >= EVIDENCE_CACHE_ENTRIES):
                    _, (_, removed) = self._evidence_cache.popitem(last=False)
                    self._cache_bytes -= removed
                    self._cache_counts["evidence_evictions"] += 1
                self._evidence_cache[key] = body, charge
                self._cache_bytes += charge
            else:
                self._cache_counts["oversize_entries_not_cached"] += 1
        return losses, audit

    def _compute_evidence(self, decision, history):
        target = decision["category"]
        reference = self.categories[target]["reference_id"]
        metric = self.categories[target]["primary_metric"]
        methods = [m for m in self.methods if self.procedure_available(m, decision)]
        losses = {m: [] for m in methods}
        exclusions, weeks = {}, []
        for week in history:
            offers = self.offers_for(_key(week))
            historical_choice = dict(week, evidence_lane=decision["evidence_lane"])
            if (not offers or not self.procedure_available(reference, historical_choice)
                    or not all(self.eligible(reference, o, decision["evidence_lane"]) for o in offers)):
                weeks.append(dict(key=list(_key(week)), state="UNAVAILABLE_REFERENCE", scored_rows=0))
                continue
            graded = [(o, self.grade(o["offered_id"], decision["weekly_decision_cutoff_utc"], decision["evidence_lane"])) for o in offers]
            scored = [(o, g) for o, g in graded if g and g["participation_state"] == "played" and self.valid_actual(g.get("actual"), target)]
            weeks.append(dict(key=list(_key(week)), state="GRADED" if scored else "NO_SUPPORTED_GRADES",
                              offered_rows=len(offers), scored_rows=len(scored),
                              outcome_versions=[[o["offered_id"], g["revision"]] for o, g in graded if g]))
            for method in list(losses):
                if (not self.procedure_available(method, historical_choice)
                        or not all(self.eligible(method, o, decision["evidence_lane"]) for o in offers)):
                    exclusions[method] = "incomplete_common_period_or_offered_coverage"
                    del losses[method]
                    continue
                for offer, grade in scored:
                    value = self.forecasts[offer["offered_id"], method]["forecast_value"]
                    losses[method].append([week["week"], _loss(value, grade["actual"], metric)])
        return losses, dict(weeks=weeks, exclusions=exclusions, common_period=[list(_key(w)) for w in history],
                            replay_availability_policy_sha256=self.catalog.get("replay_availability_policy_sha256"),
                            comparison="all_original_offers; supported played grades available strictly before cutoff",
                            all_negative_weeks_retained=True)


def _history(panel, decision):
    return sorted((w for w in panel.weeks.values() if w["category"] == decision["category"]
        and w["season"] == decision["season"] and w["week"] < decision["week"]
        and panel.available_clock(w, decision["evidence_lane"], actual="grade_completed_at", replay="replay_grade_completed_at") < utc(decision["weekly_decision_cutoff_utc"])),
        key=lambda w: (w["week"], utc(w["completed_at"]), panel.available_clock(w, decision["evidence_lane"], actual="grade_completed_at", replay="replay_grade_completed_at"),
                       utc(w["weekly_decision_cutoff_utc"]), w["slate_id"]))


def _winner(scores, current, reference, margin=0.):
    best = min(scores.values())
    tied = {m for m, v in scores.items() if math.isclose(v, best, rel_tol=1e-12, abs_tol=1e-12)}
    winner = current if current in tied else reference if reference in tied else min(tied)
    if current in scores and winner != current:
        gain = (scores[current] - scores[winner]) / max(abs(scores[current]), 1e-12)
        if gain <= margin:
            winner = current
    return winner


def _rank(panel, decision, history, current, half_life=None, margin=0.):
    losses, evidence = panel.evidence(decision, history)
    scores = {}
    for method, rows in losses.items():
        if rows:
            weighted = [(2 ** (-(decision["week"] - week) / half_life) if half_life else 1., loss) for week, loss in rows]
            scores[method] = math.fsum(w * loss for w, loss in weighted) / math.fsum(w for w, _ in weighted)
    ref = panel.categories[decision["category"]]["reference_id"]
    valid = lambda m: panel.procedure_available(m, decision)
    fallback = current if valid(current) else ref if valid(ref) else None
    return (_winner(scores, current, ref, margin) if scores else fallback), dict(evidence, scores=scores,
        reason="comparable_earlier_losses" if scores else "no_evidence_retain_last_valid_or_reference")


def select(panel, decision, policy, current_id=None):
    """Freeze model PROCEDURES/weights before the slate, not forecast realizations.

    Current-week rows may be absent entirely. Only earlier forecasts and grades
    available at the weekly choice clock influence policy scores.
    """
    if policy not in {"P0", "P1", "P2", "P3", "P4"}:
        raise ValueError("unregistered policy")
    target = decision["category"]
    spec = panel.categories[target]
    base = dict(schema_version=VERSION, implementation_revision=IMPLEMENTATION_REVISION,
                policy=policy, decision=dict(decision), catalog_sha256=digest(procedure_catalog(panel.catalog)),
                primary_metric=spec.get("primary_metric"), scientifically_qualified=False)
    if target == "fantasy_ppr":
        return dict(base, state="BLOCKED_LABEL_CONTRACT", members=[], evidence={})
    bound = panel.decision_contracts.get(_key(decision), {})
    if decision.get("replay_horizon") is not None or bound.get("replay_horizon") is not None:
        panel.validate_replay_horizon(decision)
    if (decision["horizon"] != "player_game" or
            utc(decision["weekly_decision_cutoff_utc"]) >= utc(decision["slate_first_kickoff_utc"])):
        raise ValueError("weekly procedure choice must strictly precede declared slate kickoff")
    if decision["evidence_lane"] not in LANES:
        raise ValueError("explicit decision evidence lane required")
    universe = spec.get("eligible_methods", list(dict.fromkeys([spec["reference_id"], *spec["shortlist"]])))
    if decision["evidence_lane"] == "original_pregame" and len(universe) > 4:
        raise ValueError("initial online category catalog is capped at four methods")
    ref = spec["reference_id"]
    if decision["evidence_lane"] != "original_pregame" and ref != "LAB_CDF":
        raise ValueError("historical LAB_CDF must remain separate from unavailable SITE/R0")
    history, evidence = _history(panel, decision), {}
    chosen = ref
    if policy == "P1":
        latest = history[-1:]  # Never skip a losing/latest completed graded week.
        chosen, evidence = _rank(panel, decision, latest, current_id)
    elif policy == "P2":
        chosen, evidence = _rank(panel, decision, history, current_id)
    elif policy == "P3":
        folds = [w for w in history if len([p for p in history if p["week"] < w["week"]]) >= 1]
        # One fixed validation cohort per fold, independent of the grid winner
        # and of whether that winner is still eligible on the outer slate.
        validation = []
        for fold in folds:
            fold_offers = panel.offers_for(_key(fold))
            if not fold_offers or not all(panel.eligible(ref, o, decision["evidence_lane"]) for o in fold_offers):
                continue
            grades = [(o, panel.grade(o["offered_id"], decision["weekly_decision_cutoff_utc"], decision["evidence_lane"])) for o in fold_offers]
            graded = [(o, g) for o, g in grades if g and g["participation_state"] == "played" and panel.valid_actual(g.get("actual"), target)]
            inner = dict(category=target, season=fold["season"], week=fold["week"], slate_id=fold["slate_id"],
                         weekly_decision_cutoff_utc=fold["weekly_decision_cutoff_utc"],
                         slate_first_kickoff_utc=fold["slate_first_kickoff_utc"],
                         horizon=decision["horizon"], evidence_lane=decision["evidence_lane"])
            training_losses, _ = panel.evidence(inner, _history(panel, inner))
            if graded and training_losses.get(ref):
                validation.append((fold, fold_offers, graded))
        # Interleave the four independent grid simulations by fold so the same
        # bounded prior-evidence entry is reused immediately, not after a full
        # pass over every other fold. Each grid retains its original sum/order.
        states = {key: dict(prior=ref, total=0., count=0, complete=True, simulations=[]) for key in GRID}
        for fold, fold_offers, graded in validation:
            inner = dict(category=target, season=fold["season"], week=fold["week"], slate_id=fold["slate_id"],
                         weekly_decision_cutoff_utc=fold["weekly_decision_cutoff_utc"],
                         slate_first_kickoff_utc=fold["slate_first_kickoff_utc"],
                         horizon=decision["horizon"], evidence_lane=decision["evidence_lane"])
            for half_life, margin in GRID:
                state = states[half_life, margin]
                pick, proof = _rank(panel, inner, _history(panel, inner), state["prior"], half_life, margin)
                if pick is None:
                    state["complete"] = False
                    values = []
                else:
                    # The procedure was chosen before these per-game forecasts.
                    # Missing/late realization uses the reference, never reselection.
                    values = []
                    for offer, grade in graded:
                        effective = pick if panel.eligible(pick, offer, decision["evidence_lane"]) else ref
                        value = panel.forecasts[offer["offered_id"], effective]["forecast_value"]
                        values.append(_loss(value, grade["actual"], spec["primary_metric"]))
                    state["total"] += math.fsum(values)
                    state["count"] += len(values)
                state["simulations"].append(dict(half_life_weeks=half_life, switch_margin=margin, inner_week=fold["week"],
                                                 picked=pick, training_weeks=proof["common_period"], graded_rows=len(values)))
                state["prior"] = pick
        grid_scores = {key: state["total"] / state["count"] if state["count"] and state["complete"] else None for key, state in states.items()}
        simulations = [entry for key in GRID for entry in states[key]["simulations"]]
        usable = [key for key, value in grid_scores.items() if value is not None]
        enough = len(validation) >= 2 and len(usable) == len(GRID)
        # Grid ties prefer the preregistered startup pair, then stable grid order.
        selected = min(usable, key=lambda key: (grid_scores[key], key != STARTUP, GRID.index(key))) if enough else STARTUP
        chosen, evidence = _rank(panel, decision, history, current_id, *selected)
        evidence.update(hyperparameters=dict(half_life_weeks=selected[0], switch_margin=selected[1]),
                        nested_grid=[dict(half_life_weeks=k[0], switch_margin=k[1], loss=v) for k, v in grid_scores.items()],
                        nested_simulations=simulations, startup=not enough,
                        tuning_scope="only earlier completed folds; no current outer outcomes")
    elif policy == "P4":
        members = list(spec["shortlist"])
        if decision["evidence_lane"] != "original_pregame" and {"R0", "RAW"} & set(members):
            raise ValueError("historical R0/RAW blend unavailable; use a separately named reconstruction")
        evidence = dict(reason="prespecified_equal_weights", unavailable_members_use_reference_without_reweighting=True,
                        full_cdf_blend="UNSUPPORTED_NO_VALID_LAW_IMPLEMENTATION")
        return dict(base, state="SELECTED", members=[dict(method_id=m, procedure_version=panel.methods[m]["procedure_version"],
                    choice_eligible=panel.procedure_available(m, decision), weight=1 / len(members)) for m in members], evidence=evidence)
    valid = panel.procedure_available(chosen, decision)
    return dict(base, state="SELECTED" if valid else "ABSTAIN_NO_ELIGIBLE_PROCEDURE",
                members=[dict(method_id=chosen, procedure_version=panel.methods[chosen]["procedure_version"],
                              choice_eligible=True, weight=1.)] if valid else [], evidence=evidence)


def issue(panel, selection):
    """Materialize frozen procedures per game, with fallback and NO reselection."""
    if (selection.get("implementation_revision") != IMPLEMENTATION_REVISION or
            selection["catalog_sha256"] != digest(procedure_catalog(panel.catalog))):
        raise ValueError("frozen selection/catalog binding differs")
    decision = selection["decision"]
    bound = panel.decision_contracts.get(_key(decision), {})
    if decision.get("replay_horizon") is not None or bound.get("replay_horizon") is not None:
        panel.validate_replay_horizon(decision)
    offers = panel.offers_for(_key(decision))
    spec = panel.categories[decision["category"]]
    selection_sha256 = digest(selection)
    materialization_catalog_sha256 = digest(panel.catalog)
    rows = []
    for offer in offers:
        if (offer["horizon"] != decision["horizon"] or
                utc(offer["kickoff_utc"]) < utc(decision["slate_first_kickoff_utc"])):
            raise ValueError("per-game horizon/kickoff differs from the declared weekly slate")
        components, reasons = [], []
        if not selection["members"]:
            reasons.append(selection["state"])
        for member in selection["members"]:
            method = member["method_id"]
            if member["procedure_version"] != panel.methods[method]["procedure_version"]:
                raise ValueError("chosen model procedure changed after weekly freeze")
            if not member["choice_eligible"] or not panel.eligible(method, offer, decision["evidence_lane"]):
                reasons.append(method + ":unavailable_use_reference")
                method = spec["reference_id"]
                if not panel.procedure_available(method, decision):
                    components = []
                    reasons.append("reference_ineligible_at_weekly_choice_abstain")
                    break
            row = panel.forecasts.get((offer["offered_id"], method)) if panel.eligible(method, offer, decision["evidence_lane"]) else None
            if row is None:
                components = []
                reasons.append("no_valid_reference_abstain")
                break
            components.append(dict(method_id=method, model_version=row["model_version"], weight=member["weight"],
                                   value=row["forecast_value"], prediction_functional=row["prediction_functional"],
                                   fallback_reason=row.get("fallback_reason", ""),
                                   provenance={key: row[key] for key in (
                                       "issued_at", "cutoff_utc", "training_cutoff_utc", "training_max_available_utc",
                                       "training_started_at", "training_completed_at", "source_capture_completed_at",
                                       "training_source_capture_completed_at", "procedure_version",
                                       "training_state", "source_receipt_sha256", "control_policy_sha256",
                                       "control_source_version", "event_contract", "saved_event_probability",
                                       "source_policy_sha256", "query_source_sha256", "artifact_sha256", "evidence_lane",
                                       "reference_stream", "operational_eligible", "replay_eligible", "replay_cutoff_utc",
                                       "frozen_before_grading") if key in row}))
        value = math.fsum(r["weight"] * r["value"] for r in components) if components else None
        product = spec.get("product")
        functional = PRODUCTS[product][1] if product in PRODUCTS else None
        if selection["policy"] == "P4" and any(c["prediction_functional"] == "legacy_unknown" for c in components):
            product, functional = "point_blend", "equal_weight_mean_of_points; includes_legacy_unknown"
        elif selection["policy"] == "P4" and product == "point_median":
            product, functional = "point_blend", "equal_weight_mean_of_median_points; not_a_mixture_median"
        elif len(components) == 1:
            functional = components[0]["prediction_functional"]
            if functional == "legacy_unknown":
                product = "point_legacy"
        rows.append(dict(offer, selection_sha256=selection_sha256, forecast_value=value, product=product,
                         replay_horizon=decision.get("replay_horizon"),
                         replay_horizon_version=decision.get("replay_horizon_version"),
                         weekly_decision_cutoff_utc=decision["weekly_decision_cutoff_utc"],
                         evidence_lane=decision["evidence_lane"], requires_actual_publication_receipt=True,
                         materialization_catalog_sha256=materialization_catalog_sha256,
                         prediction_functional=functional, components=components, fallback_reason=";".join(reasons),
                         state="FORECAST" if value is not None else "ABSTAIN", primary_metric=spec.get("primary_metric")))
    return rows


def evaluate(panel, issued, as_of):
    """Append a grading view; never mutate the frozen issued selection/rows."""
    if len({(r["category"], r["primary_metric"]) for r in issued}) > 1:
        raise ValueError("different category units must not be pooled")
    counts, losses, versions = Counter(), [], []
    for row in issued:
        counts["offered"] += 1
        counts["forecast" if row["forecast_value"] is not None else "abstain"] += 1
        counts["fallback"] += bool(row["fallback_reason"] or any(c["fallback_reason"] for c in row["components"]))
        grade = panel.grade(row["offered_id"], as_of)
        if grade is None:
            counts["missing_grade"] += 1
            continue
        versions.append([row["offered_id"], grade["revision"]])
        state = grade["participation_state"]
        if row["category"] == "fantasy_ppr":
            counts["unsupported_label_contract"] += 1
        elif state != "played":
            counts[state] += 1
        elif not panel.valid_actual(grade.get("actual"), row["category"]):
            counts["played_missing_or_unsupported"] += 1
        else:
            counts["played_zero"] += grade["actual"] == 0
            if row["forecast_value"] is not None:
                counts["scored"] += 1
                counts["scored_played_zero"] += grade["actual"] == 0
                losses.append(_loss(row["forecast_value"], grade["actual"], row["primary_metric"]))
    return dict(as_of=as_of, coverage=dict(counts), primary_loss=math.fsum(losses) / len(losses) if losses else None,
                outcome_versions=versions, frozen_forecasts_sha256=digest(issued), no_selection_rewrite=True)


def load_authenticated(path, sha256):
    path = Path(path)
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("authenticated flat cache size/hash mismatch")
    body = path.read_bytes()
    if len(body) > 128 * 1024 * 1024 or hashlib.sha256(body).hexdigest() != sha256:
        raise ValueError("authenticated flat cache size/hash mismatch")
    return json.loads(body)


def load_row_reference(reference, *, storage=None):
    """Thin authenticated cache projection, sharing the owned-reference guard.

    Mapping/metadata declarations are hash-bound in the parent bundle. There
    is no inference, source join or missing-to-zero fill. Parquet uses the
    existing dataframe reader lazily, only in a separately authorized runtime.
    """
    path = Path(reference["path"])
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("cached row artifact byte bound exceeded")
    if storage is not None:
        from .owned_reference_batch import validate_owned_references
        validate_owned_references(storage, {str(path.resolve()): reference["sha256"]})
    with path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != reference["sha256"]:
            raise ValueError("cached row artifact hash mismatch")
    kind = reference["format"]
    mapping, constants = reference.get("field_map", {}), reference.get("constants", {})
    if set(constants) & {"actual", "participation_state", "forecast_value"}:
        raise ValueError("outcomes, participation and predictions cannot be invented constants")
    if kind == "parquet":
        import pandas as pd
        if not mapping:
            raise ValueError("explicit cached parquet column projection required")
        frame = pd.read_parquet(path, columns=sorted(set(mapping.values())))
        source = frame.to_dict("records")
    elif kind == "json":
        source = load_authenticated(path, reference["sha256"])
    elif kind == "jsonl":
        with path.open() as handle:
            source = [json.loads(line) for line in handle if line.strip()]
    else:
        raise ValueError("unsupported authenticated cached row format")
    if not isinstance(source, list) or len(source) > 1_600_000:
        raise ValueError("cached artifact must be a bounded row array")
    rows = []
    for row in source:
        projected = {new: row[old] for new, old in mapping.items()} if mapping else dict(row)
        if set(projected) & set(constants):
            raise ValueError("cache metadata must not overwrite a stored column")
        for key, value in list(projected.items()):
            if kind == "parquet" and pd.isna(value):
                projected[key] = None
            elif hasattr(value, "isoformat"):
                projected[key] = value.isoformat()
        rows.append(dict(projected, **constants))
    return rows


def freeze_record(output, kind, document, *, storage=None):
    """Reuse the existing immutable writer and its scoped quota adapter."""
    if storage is None:
        return save(output, kind, document, max_bytes=128 * 1024 * 1024)
    from .operational_io import operational_io
    with operational_io(storage, run_root=output):
        return save(output, kind, document, max_bytes=128 * 1024 * 1024)


def run_cached(bundle_path, bundle_sha256, catalog_path, catalog_sha256, *, policy_path=None,
               policy_sha256=None, storage=None, output=None):
    """No acquisition/fits: consume the normalized authenticated cache contract.

    A runtime caller supplies its existing OperationalStorage for quota-owned
    persistence. Without it, the existing immutable state.save seam is used.
    """
    bundle = load_authenticated(bundle_path, bundle_sha256)
    catalog = load_authenticated(catalog_path, catalog_sha256)
    if policy_path is not None and load_authenticated(policy_path, policy_sha256) != POLICY:
        raise ValueError("frozen selector policy differs from implementation")
    for kind, references in bundle.get("row_artifacts", {}).items():
        if kind not in {"offers", "forecasts", "outcomes"}:
            raise ValueError("unregistered cached row artifact kind")
        for reference in references:
            bundle[kind].extend(load_row_reference(reference, storage=storage))
    panel = Panel(bundle, catalog)
    results = []
    currents = {}
    for decision in sorted(bundle["decisions"], key=lambda d: (utc(d["weekly_decision_cutoff_utc"]), d["category"], d["slate_id"])):
        for policy in ("P0", "P1", "P2", "P3", "P4"):
            k = (decision["category"], policy)
            selection = select(panel, decision, policy, currents.get(k))
            if output is not None:
                freeze_record(output, "weekly-choices", selection, storage=storage)
            rows = issue(panel, selection)
            if output is not None:
                freeze_record(output, "weekly-forecasts", dict(selection_sha256=digest(selection), rows=rows), storage=storage)
            if len(selection["members"]) == 1:
                currents[k] = selection["members"][0]["method_id"]
            results.append(dict(selection=selection, forecasts=rows,
                                grade=evaluate(panel, rows, bundle["grade_as_of"])))
    report = dict(schema_version=VERSION, bundle_sha256=bundle_sha256, catalog_sha256=catalog_sha256,
                  policy=POLICY, policy_sha256=digest(POLICY), results=results,
                  historical_catalog_availability=("hindsight_exposed_research_only" if any(
                      d["evidence_lane"] != "original_pregame" for d in bundle["decisions"])
                      else "original_pregame_procedure_clock_checked; publication_acceptance_separate"),
                  independent_confirmation=False, deployment_changed=False)
    if output is not None:
        freeze_record(output, "weekly-adaptive", report, storage=storage)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "bundle-sha256", "catalog", "catalog-sha256", "policy", "policy-sha256", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = run_cached(args.bundle, args.bundle_sha256, args.catalog, args.catalog_sha256,
                        policy_path=args.policy, policy_sha256=args.policy_sha256, output=args.output)
    print(json.dumps(dict(schema_version=VERSION, results=len(result["results"]), report_sha256=digest(result)), sort_keys=True))


if __name__ == "__main__":
    main()
