"""Prospective V2.1 tie correction; original V2 source/36 checks remain intact.

Pure metadata logic. This module does not issue forecasts, fit models, activate
production, or turn a recorded historical leader into a prospective winner.
"""
from copy import deepcopy
from datetime import datetime
import math

from .next_checkpoint_research_selection_v1 import cumulative_choice

VERSION = "research-informed-stat-point-mae-v2.1"
PRODUCT = "stat_point_mae_v2"
PRIMARY = "MAE"
NUMERIC = frozenset({"pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int",
    "rush_yd", "rush_att", "rec", "rec_yd", "rush_rec_yd", "nick-chart-ppr-v1"})
MEDIAN_FUNCTIONALS = frozenset({"full_cdf_lower_median", "median_objective_point"})
FUNCTIONALS = {"point_median": MEDIAN_FUNCTIONALS,
    "point_mean": frozenset({"expected_mean", "valid_mean_objective_point"}),
    "point_empirical": frozenset({"empirical_point", "legacy_mixed_point", "arithmetic_point_blend", "market_line_heuristic"})}
REQUIRED_GATES = ("future_inference", "source_and_artifact_bindings", "durable_capture_restore",
    "consumer_contract", "fallback_rollback", "retained_owner_admission")
PANEL_KEYS = frozenset({"target", "scoring_target", "season", "season_type", "weeks",
    "role_population", "horizon_contract", "source_availability_policy",
    "comparison_receipt_sha256"})


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _loss(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _panel(value, target, scoring_target):
    if not isinstance(value, dict) or set(value) != PANEL_KEYS:
        raise ValueError("exact comparison identity required")
    if (value["target"] != target or value["scoring_target"] != scoring_target or scoring_target != target
            or value["season"] != 2026 or value["season_type"] != "REG"
            or not isinstance(value["weeks"], list) or not value["weeks"]
            or any(type(w) is not int or not 1 <= w <= 18 for w in value["weeks"])
            or value["weeks"] != sorted(set(value["weeks"]))
            or not isinstance(value["role_population"], list) or not value["role_population"]
            or not _hash(value["comparison_receipt_sha256"])):
        raise ValueError("target/year/coverage comparison contract differs")
    for field in ("horizon_contract", "source_availability_policy"):
        if not isinstance(value[field], str) or not value[field]:
            raise ValueError("named original timing and source policy required")


def choose_numeric_projection(request):
    """Return MAE point leader and a separately readiness-qualified candidate.

    Lower 2026 MAE controls numeric ranking. 2025, bias, RMSE, tails and intervals
    are retained diagnostics. They do not create hidden automatic vetoes.
    Comparison membership is supplied by an authenticated retained comparison
    receipt; matching aggregate row counts alone is not identity authentication.
    """
    target, scoring_target = request["target"], request["scoring_target"]
    if (request["policy_version"] != VERSION or target not in NUMERIC
            or request["product"] != PRODUCT or request["primary"] != PRIMARY):
        raise ValueError("separately versioned numeric point/MAE request required")
    if scoring_target != target:
        raise ValueError("exact registered statistic/chart scoring target required")
    common = request["comparison_identity"]
    _panel(common, target, scoring_target)
    expected = request["expected_coverage"]
    if (set(expected) != {"offered_rows", "scored_rows", "games", "weeks"}
            or any(type(v) is not int or v <= 0 for v in expected.values())
            or expected["scored_rows"] > expected["offered_rows"]
            or expected["weeks"] != len(common["weeks"])):
        raise ValueError("complete offered and supported comparison coverage required")
    methods, admitted, operational, reasons, diagnostics = {}, [], [], {}, {}
    for row in request["candidates"]:
        method = row["method_id"]
        if not isinstance(method, str) or not method or method in methods:
            raise ValueError("unique nonempty procedure IDs required")
        methods[method] = row
        why = []
        if row["functional"] not in FUNCTIONALS.get(row["product"], ()):
            why.append("unrecognized_or_mislabeled_original_point_contract")
        if row["product"] == "point_mean" and row.get("mean_eligible") is not True:
            why.append("legacy_or_unverified_point_must_not_be_labeled_mean")
        if row["scoring_target"] != scoring_target or row["comparison_identity"] != common:
            why.append("different_target_population_horizon_or_source_contract")
        if row["coverage"] != expected:
            why.append("incomplete_or_different_full_fallback_population")
        if not _loss(row["MAE_2026"]):
            why.append("missing_or_invalid_2026_MAE")
        if not _hash(row["score_source_receipt_sha256"]):
            why.append("score_source_receipt_identity_missing")
        if row.get("declared_fallback_included") is not True:
            why.append("registered_fallback_missing_from_system_scores")
        if not isinstance(row["diagnostics"], dict):
            raise ValueError("diagnostics must be retained as a separate record")
        diagnostics[method] = deepcopy(row["diagnostics"])
        reasons[method] = list(why)
        if not why:
            admitted.append(method)
            gates = row["operational_gates"]
            if set(gates) != set(REQUIRED_GATES):
                raise ValueError("all operational admission gates must be explicit")
            blocked = [name for name in REQUIRED_GATES if gates[name] is not True]
            reasons[method].extend("operational_pending:" + name for name in blocked)
            if not blocked:
                operational.append(method)
    current = request["current_display"]
    if not isinstance(current, dict) or not all(k in current for k in ("method_id", "product", "functional", "version")):
        raise ValueError("actual prior displayed contract must be retained")
    def winner(pool):
        if not pool:
            return None
        minimum = min(methods[name]["MAE_2026"] for name in pool)
        tied = [name for name in pool if methods[name]["MAE_2026"] == minimum]
        # Original functional stays explicit; a mean can win point-MAE without
        # becoming a median or winning the separate expected-value comparison.
        if (current["method_id"] in tied
                and methods[current["method_id"]]["product"] == current["product"]
                and methods[current["method_id"]]["functional"] == current["functional"]):
            return current["method_id"]
        return min(tied)
    research, selected = winner(admitted), winner(operational)
    medians = [name for name in admitted if methods[name]["product"] == "point_median"]
    means = [name for name in admitted if methods[name]["product"] == "point_mean"
             and methods[name].get("mean_eligible") is True
             and _loss(methods[name]["diagnostics"].get("MSE_2026"))]
    median_leader = winner(medians)
    mean_leader = min(means, key=lambda name:(methods[name]["diagnostics"]["MSE_2026"], name)) if means else None
    fallback = deepcopy(current) if selected is None else None
    return {"policy_version": VERSION, "target": target, "scoring_target": scoring_target,
        "product": PRODUCT, "primary": PRIMARY, "comparison_identity": deepcopy(common),
        "coverage": deepcopy(expected), "research_leader": research,
        "research_leader_MAE_2026": methods[research]["MAE_2026"] if research else None,
        "research_leader_original_product": methods[research]["product"] if research else None,
        "research_leader_original_functional": methods[research]["functional"] if research else None,
        "strict_median_MAE_leader": median_leader,
        "separate_valid_mean_MSE_leader": mean_leader,
        "operational_candidate": selected,
        "operational_candidate_MAE_2026": methods[selected]["MAE_2026"] if selected else None,
        "operational_candidate_original_product": methods[selected]["product"] if selected else None,
        "operational_candidate_original_functional": methods[selected]["functional"] if selected else None,
        "actual_prior_display": deepcopy(current), "unchanged_fallback_contract": fallback,
        "readiness_reasons": reasons, "diagnostics_reported_without_automatic_veto": diagnostics,
        "tie_rule": "current identically typed point if exactly tied, then stable method ID",
        "switching_margin": 0.0,
        "state": "CANDIDATE_SELECTED_REQUIRES_PRODUCER_ACTIVATION" if selected else "KEEP_TRUTHFULLY_TYPED_PRIOR_DISPLAY_PENDING_POINT_ADMISSION",
        "live_activation": False, "old_P2_and_v1_unchanged": True,
        "scientific_qualification": False,
        "evidence_lane": "exposed reconstructed development, not genuine P2 or untouched confirmation"}


def choose_future_numeric(records, *, methods, current, reference, epoch, horizon,
                          target, decision_at, expected_resolved_keys):
    """Reuse the unchanged tested cumulative rule in an explicitly new MAE epoch."""
    if target not in NUMERIC or not isinstance(epoch, str) or not epoch.startswith(VERSION + ":"):
        raise ValueError("new MAE point epoch and target required; never reuse original P2 epoch")
    identities = {}
    for row in records:
        issued = datetime.fromisoformat(row["issued_at"].replace("Z", "+00:00"))
        limit = datetime.fromisoformat(row["issue_deadline"].replace("Z", "+00:00"))
        if issued.tzinfo is None or limit.tzinfo is None or not issued < limit:
            raise ValueError("v2 point issuance must be strictly before its registered deadline")
        original = (row["forecast_product"], row["prediction_functional"])
        if original[1] not in FUNCTIONALS.get(original[0], ()):
            raise ValueError("future point must retain its original forecast functional")
        if original[0] == "point_mean" and row.get("mean_eligible") is not True:
            raise ValueError("future mean functional requires its valid mean contract")
        if row["scoring_target"] != target:
            raise ValueError("future point scoring target differs")
        if row["method"] in identities and identities[row["method"]] != original:
            raise ValueError("one method cannot change its point contract within an epoch")
        identities[row["method"]] = original
    return cumulative_choice(records, methods=methods, current=current, reference=reference,
        product=PRODUCT, primary=PRIMARY, epoch=epoch, horizon=horizon, category=target,
        decision_at=decision_at, expected_resolved_keys=expected_resolved_keys)
