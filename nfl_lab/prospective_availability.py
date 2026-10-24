"""Opt-in local-capture availability validation; no I/O, selection or fitting.

The caller authenticates immutable source bytes and the source/qualification
contracts before calling. Hashes here bind the supplied documents; they do not
prove a publisher's accuracy, publication time, rights or durable storage.
Nothing in this module changes the historical seven-day feature/source lane.
"""
from __future__ import annotations

import math
import re

from .state import digest, utc

VERSION = "prospective-capture-availability-v1"
LANE = "original_local_capture_before_cutoff"
HISTORICAL_LANE = "reconstructed_kickoff_plus_7_days"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENTITY = ("player_id", "game_id", "season", "week", "season_type", "period",
            "team", "opponent", "kickoff_utc")
GAME_IDENTITY = tuple(k for k in IDENTITY if k != "player_id")
COUNTS = frozenset(("pass_att", "pass_cmp", "pass_td", "pass_int", "rec_tgt",
                    "rush_att", "rec", "rush_td", "rec_td", "pass_2pt", "rush_2pt",
                    "rec_2pt", "fum_lost", "st_td", "st_fum_rec", "st_ff",
                    "fum_rec_td", "idp_blk_kick", "idp_fum_rec"))
SIGNED = frozenset(("pass_yd", "rush_yd", "rec_yd"))
TARGETS = frozenset(("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int",
                     "rush_yd", "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td"))


class ContractError(ValueError):
    """Invalid metadata or incompatible version; never a zero-valued fallback."""


def _require(condition, reason):
    if not condition:
        raise ContractError(reason)


def _sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _clock(value):
    try:
        return utc(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractError("INVALID_CLOCK") from exc


def _bound(envelope, name):
    item = envelope[name]
    _require(isinstance(item, dict) and set(item) == {"document", "sha256"}
             and isinstance(item["document"], dict),
             "INVALID_EVIDENCE_ENVELOPE")
    _require(_sha(item["sha256"]) and digest(item["document"]) == item["sha256"],
             "EVIDENCE_HASH_MISMATCH")
    return item["document"], item["sha256"]


def _identity(row):
    _require(all(k in row for k in IDENTITY), "INCOMPLETE_IDENTITY")
    _require(all(isinstance(row[k], str) and row[k] for k in
                 ("player_id", "game_id", "team", "opponent")), "INVALID_IDENTITY")
    _require(row["team"] != row["opponent"] and row["season_type"] == "REG"
             and row["period"] == "full_game_including_overtime"
             and type(row["season"]) is int and type(row["week"]) is int
             and 1 <= row["week"] <= 18, "INVALID_PERIOD_OR_TEAMS")
    _clock(row["kickoff_utc"])
    return {k: row[k] for k in IDENTITY}


def validate_model_contract(binding, *, expected):
    """Require an explicit new artifact/feature/availability compatibility record.

    ``expected`` is a caller-authenticated policy, never inferred from a model's
    own claims. This accepts an explicitly versioned mixed training/inference
    lane, while conferring no confirmation, operational or release status.
    """
    _require(isinstance(binding, dict) and isinstance(expected, dict), "INVALID_MODEL_CONTRACT")
    _require(binding.get("schema_version") == VERSION + "-model-contract",
             "NEW_MODEL_CONTRACT_REQUIRED")
    for key in ("availability_policy_sha256", "source_policy_sha256",
                "qualification_policy_sha256", "feature_contract_sha256"):
        _require(_sha(expected.get(key)) and binding.get(key) == expected[key],
                 "MODEL_POLICY_OR_FEATURE_MISMATCH")
    for key in ("model_artifact_sha256", "training_manifest_sha256",
                "prospective_registration_sha256"):
        _require(_sha(binding.get(key)), "MODEL_OR_REGISTRATION_BINDING_MISSING")
    _require(isinstance(binding.get("model_id"), str) and bool(binding["model_id"]),
             "MODEL_ID_MISSING")
    _require(binding.get("inference_availability_lane") == LANE
             and binding.get("training_availability_lane") in {HISTORICAL_LANE, LANE},
             "MODEL_AVAILABILITY_LANE_MISMATCH")
    return {"model_contract_sha256": digest(binding), "inference_lane": LANE,
            "training_lane": binding["training_availability_lane"],
            "scientific_qualification": "NOT_CONFERRED_BY_SOFTWARE"}


def _capture(document, expected_policy):
    _require(document.get("schema_version") == "local-source-capture-success-v1"
             and document.get("status") == "success", "CAPTURE_SUCCESS_REQUIRED")
    _require(document.get("source_policy_sha256") == expected_policy
             and isinstance(document.get("source_id"), str) and bool(document["source_id"])
             and _sha(document.get("body_sha256"))
             and _sha(document.get("original_receipt_sha256")), "CAPTURE_BINDING_INVALID")
    clocks = [_clock(document[k]) for k in ("capture_started_utc", "body_completed_utc",
                                           "persist_started_utc", "persist_completed_utc")]
    _require(clocks == sorted(clocks), "CAPTURE_CLOCK_ORDER")
    # A publisher clock is optional evidence, never inferred from local clocks.
    if document.get("upstream_publication_utc") is not None:
        _require(_clock(document["upstream_publication_utc"]) <= clocks[1],
                 "INVALID_PUBLICATION_CLOCK")
    return clocks


def qualify_history_capture(version, *, query, model_binding, expected, parent_version=None):
    """Validate one already selected prior appearance and retain its availability.

    This does not search past a failed appearance, select a history window,
    resolve conflicting outcomes, infer participation, persist, or open files.
    Caller-side qualification must authenticate every supplied byte binding.
    ``query.calculation_started_utc`` is an actual recorded clock, not a planned
    completion. Call ``qualify_forecast_completion`` after durable capture.
    """
    try:
        _require(all(isinstance(v, dict) for v in (version, query, model_binding, expected)),
                 "INVALID_AVAILABILITY_ENVELOPE")
        model = validate_model_contract(model_binding, expected=expected)
        _require(version.get("schema_version") == VERSION + "-history-version",
                 "NEW_HISTORY_VERSION_REQUIRED")
        row, row_sha = _bound(version, "qualified_row")
        identity = _identity(row)
        _identity(query)
        _require(query["player_id"] == row["player_id"], "PLAYER_IDENTITY_MISMATCH")
        _require(query["game_id"] != row["game_id"], "TARGET_GAME_IN_HISTORY")
        _require(query["model_id"] == model_binding["model_id"], "QUERY_MODEL_MISMATCH")
        targets = query["requested_targets"]
        _require(isinstance(targets, list) and bool(targets) and len(targets) == len(set(targets))
                 and set(targets) <= TARGETS, "INVALID_REQUESTED_TARGETS")
        cutoff, kickoff = _clock(query["cutoff_utc"]), _clock(query["kickoff_utc"])
        calculation_start = _clock(query["calculation_started_utc"])
        _require(calculation_start <= cutoff < kickoff, "FORECAST_CLOCK_ORDER")
        _require(_clock(row["kickoff_utc"]) < cutoff, "NOT_PRIOR_GAME")
        capture, capture_sha = _bound(version, "source_capture")
        status_capture, status_capture_sha = _bound(version, "finality_capture")
        source_clocks = _capture(capture, expected["source_policy_sha256"])
        status_clocks = _capture(status_capture, expected["source_policy_sha256"])
        _require(capture["source_id"] == expected["statistics_source_id"]
                 and status_capture["source_id"] == expected["finality_source_id"],
                 "SOURCE_ROLE_MISMATCH")
        # An old cache is not made final by pairing it with a later status flag.
        _require(_clock(row["kickoff_utc"]) < status_clocks[1]
                 and status_clocks[-1] <= source_clocks[0], "FINALITY_BEFORE_STAT_CAPTURE_REQUIRED")
        _require(source_clocks[-1] <= calculation_start, "POST_CUTOFF_OR_CALCULATION_CAPTURE")
        finality, finality_sha = _bound(version, "finality")
        _require(finality.get("schema_version") == "completed-game-qualification-v1"
                 and finality.get("completed") is True
                 and finality.get("capture_sha256") == status_capture_sha
                 and finality.get("game_identity") == {k: identity[k] for k in GAME_IDENTITY}
                 and _sha(finality.get("parser_sha256")), "FINALITY_IDENTITY_OR_STATE_INVALID")
        qualification, qualification_sha = _bound(version, "qualification")
        _require(qualification.get("schema_version") == "qualified-history-row-v1"
                 and qualification.get("policy_sha256") == expected["qualification_policy_sha256"]
                 and qualification.get("qualified_row_sha256") == row_sha
                 and qualification.get("source_capture_sha256") == capture_sha
                 and qualification.get("finality_sha256") == finality_sha,
                 "QUALIFICATION_BINDING_INVALID")
        qualified = _clock(qualification["qualified_at_utc"])
        durable = _clock(qualification["persist_completed_utc"])
        _require(source_clocks[-1] <= qualified <= durable <= calculation_start,
                 "QUALIFICATION_CLOCK_ORDER")
        revision = version.get("revision")
        if revision == "original":
            _require(version.get("supersedes_version_sha256") is None and parent_version is None,
                     "ORIGINAL_HAS_CORRECTION_PARENT")
        elif revision == "append_correction":
            _require(isinstance(parent_version, dict)
                     and parent_version.get("schema_version") == VERSION + "-history-version"
                     and version.get("supersedes_version_sha256") == digest(parent_version),
                     "CORRECTION_PARENT_REQUIRED")
            parent_row, _ = _bound(parent_version, "qualified_row")
            parent_capture, _ = _bound(parent_version, "source_capture")
            parent_clocks = _capture(parent_capture, expected["source_policy_sha256"])
            _require(_identity(parent_row) == identity
                     and parent_capture["source_id"] == capture["source_id"]
                     and parent_clocks[-1] < source_clocks[0],
                     "CORRECTION_PARENT_MISMATCH")
        else:
            raise ContractError("INVALID_REVISION_STATE")
        _require(row.get("identity_state") == "qualified", "IDENTITY_UNQUALIFIED")
        _require(row.get("conflict_state") == "clear", "CONFLICT_QUARANTINED")
        participation = row.get("participation_state")
        _require(participation in {"played", "DNP", "unknown"}, "INVALID_PARTICIPATION_STATE")
        if participation != "played":
            return {"state": "UNAVAILABLE", "reason": "DNP" if participation == "DNP" else "UNKNOWN_PARTICIPATION",
                    "participation_state": participation, "version_sha256": digest(version)}
        fields = query["required_primitives"]
        _require(isinstance(fields, list) and bool(fields) and len(fields) == len(set(fields))
                 and set(fields) <= COUNTS | SIGNED, "INVALID_PRIMITIVE_CONTRACT")
        for field in fields:
            primitive = row["primitives"].get(field, {})
            support, value = primitive.get("support"), primitive.get("value")
            _require(support in {"explicit_value", "qualified_sparse_zero"}, "MISSING_OR_UNQUALIFIED_PRIMITIVE")
            _require(type(value) in (int, float) and math.isfinite(value), "INVALID_PRIMITIVE_VALUE")
            _require(field not in COUNTS or (value >= 0 and float(value).is_integer()),
                     "INVALID_COUNT_SUPPORT")
            if support == "qualified_sparse_zero":
                _require(value == 0 and _sha(qualification.get("zero_semantics_sha256")),
                         "ZERO_SEMANTICS_REQUIRED")
        if {"pass_cmp", "pass_att"} <= set(fields):
            _require(row["primitives"]["pass_cmp"]["value"] <= row["primitives"]["pass_att"]["value"],
                     "COMPLETIONS_EXCEED_ATTEMPTS")
        return {"state": "ELIGIBLE", "reason": None, "availability_lane": LANE,
                "source_available_utc": durable.isoformat(), "version_sha256": digest(version),
                "source_capture_sha256": capture_sha, "finality_capture_sha256": status_capture_sha,
                "qualification_sha256": qualification_sha, "model_contract_sha256": model["model_contract_sha256"],
                "participation_state": participation, "primitive_fields": list(fields),
                "query_identity": {k: query[k] for k in IDENTITY},
                "requested_targets": list(targets),
                "model_id": query["model_id"], "cutoff_utc": cutoff.isoformat(),
                "calculation_started_utc": calculation_start.isoformat(),
                "completion_status": "PENDING_ACTUAL_PERSISTENCE",
                "upstream_publication_utc": capture.get("upstream_publication_utc"),
                "historical_availability_claim": "NONE"}
    except ContractError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ContractError("MALFORMED_AVAILABILITY_INPUT") from exc


def qualify_forecast_completion(availability, *, calculation, batch, persistence):
    """Postflight validation using the existing immutable state capture receipts.

    The three arguments are ``{document, sha256}`` envelopes; the caller verifies
    original immutable files. The calculation receipt is a new explicit producer
    observation. Existing state.capture's batch and completion remain unchanged.
    No missing completion clock is filled from a later replay or wall clock.
    """
    try:
        _require(isinstance(availability, dict), "INVALID_AVAILABILITY_ENVELOPE")
        _require(availability.get("state") == "ELIGIBLE"
                 and availability.get("completion_status") == "PENDING_ACTUAL_PERSISTENCE"
                 and availability.get("availability_lane") == LANE,
                 "ELIGIBLE_PREFLIGHT_REQUIRED")
        envelopes = {"calculation": calculation, "batch": batch, "persistence": persistence}
        calc, calc_sha = _bound(envelopes, "calculation")
        doc, batch_sha = _bound(envelopes, "batch")
        receipt, receipt_sha = _bound(envelopes, "persistence")
        decision_sha = digest(availability)
        start = _clock(availability["calculation_started_utc"])
        end = _clock(calc["completed_at"])
        persist_start, persist_end = _clock(doc["persist_started_at"]), _clock(receipt["completed_at"])
        cutoff, kickoff = _clock(availability["cutoff_utc"]), _clock(availability["query_identity"]["kickoff_utc"])
        _require(calc.get("schema_version") == VERSION + "-calculation"
                 and calc.get("availability_sha256") == decision_sha
                 and _clock(calc["started_at"]) == start, "CALCULATION_BINDING_INVALID")
        _require(doc.get("schema_version") == "lab-forecast-batch-v1"
                 and receipt.get("batch") == batch_sha, "PERSISTENCE_BATCH_MISMATCH")
        _require(start <= end <= persist_start <= persist_end <= cutoff < kickoff,
                 "FORECAST_COMPLETION_CLOCK_ORDER")
        identity = availability["query_identity"]
        targets = availability["requested_targets"]
        _require(isinstance(targets, list) and bool(targets) and len(targets) == len(set(targets))
                 and set(targets) <= TARGETS, "INVALID_REQUESTED_TARGETS")
        for target in targets:
            matches = [r for r in doc["rows"] if r.get("player_id") == identity["player_id"]
                       and r.get("game_id") == identity["game_id"]
                       and r.get("model_id") == availability["model_id"] and r.get("target") == target]
            _require(len(matches) == 1, "REQUESTED_TARGET_ROW_COUNT")
            row = matches[0]
            _require(all(row.get(k) == identity[k] for k in IDENTITY)
                     and row.get("availability_sha256") == decision_sha
                     and row.get("calculation_receipt_sha256") == calc_sha
                     and end <= _clock(row["issued_at"]) <= persist_start,
                     "FORECAST_ROW_BINDING_INVALID")
        actual_late = sorted({r["game_id"] for r in doc["rows"] if _clock(r["kickoff_utc"]) <= persist_end})
        _require(receipt.get("late_games") == actual_late
                 and identity["game_id"] not in actual_late, "FORECAST_PERSISTED_LATE")
        return {"state": "LOCAL_COMPLETION_QUALIFIED", "availability_sha256": decision_sha,
                "calculation_receipt_sha256": calc_sha, "batch_sha256": batch_sha,
                "persistence_receipt_sha256": receipt_sha, "completed_at": persist_end.isoformat(),
                "qualified_targets": list(targets),
                "remote_durability": "NOT_ESTABLISHED", "scientific_qualification": "NOT_CONFERRED_BY_SOFTWARE"}
    except ContractError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ContractError("MALFORMED_COMPLETION_INPUT") from exc
