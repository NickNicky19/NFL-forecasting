"""Pure metadata limits for the one explicit source-repair continuation.

No NFL rows, sources, fitting, scoring, managed writes or budget authorization.
The integrator's independently frozen envelope supplies prior consumption.
"""
import hashlib
import json
import math
from pathlib import Path

VERSION = "dynamic-opportunity-source-recovery-v2-20261024"
ORIGINAL = "dynamic-opportunity-study-v1-20261023"
CAMPAIGN_BYTES = 50331648


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate(envelope, *, source_plan=None, output=None):
    """Reject a budget reset, changed search, unsafe reuse or missing charge."""
    _require(set(envelope) == {"schema_version", "state", "original_registration_id", "original_output", "output",
        "previous_consumption", "remaining_limits", "source_phase_consumption", "reuse", "previous_receipts"},
        "exact recovery envelope required")
    _require(envelope["schema_version"] == VERSION and envelope["original_registration_id"] == ORIGINAL
             and envelope["state"] == "REGISTERED_NO_INVOCATION", "explicit registered recovery only")
    _require(envelope["output"] != envelope["original_output"]
             and all(Path(envelope[k]).is_absolute() for k in ("output", "original_output")), "fresh absolute recovery namespace required")
    if output is not None:
        _require(output == envelope["output"], "recovery output changed")
    previous = envelope["previous_consumption"]; limits = envelope["remaining_limits"]
    _require(set(previous) == {"CPU_seconds", "wall_seconds", "prior_vector_reservations", "forecast_packages",
             "forecast_row_incidences", "retained_bytes"}, "all earlier consumption must remain charged")
    _require(set(limits) == {"CPU_seconds", "wall_seconds", "campaign_retention_bytes", "prior_vector_formations", "planned_prior_vectors"},
             "exact recovery ceilings required")
    for key in ("CPU_seconds", "wall_seconds"):
        _require(_number(previous[key]) and type(limits[key]) is int and 0 < limits[key] <= 540
                 and previous[key] + limits[key] <= 600, "remaining time exceeds original cumulative600")
    _require(previous["forecast_packages"] == previous["forecast_row_incidences"] == 0,
             "this continuation cannot reset spent packages or forecast rows")
    _require(type(previous["prior_vector_reservations"]) is int and previous["prior_vector_reservations"] == 2
             and limits["prior_vector_formations"] == 14 and limits["planned_prior_vectors"] == 13
             and previous["prior_vector_reservations"] + limits["prior_vector_formations"] <= 16,
             "old reserved priors plus new prior limit exceed original16")
    _require(type(previous["retained_bytes"]) is int and previous["retained_bytes"] > 0
             and limits["campaign_retention_bytes"] == CAMPAIGN_BYTES
             and previous["retained_bytes"] < CAMPAIGN_BYTES, "old evidence or campaign48MiB charge missing")
    phase = envelope["source_phase_consumption"]
    _require(set(phase) == {"wall_seconds", "CPU_seconds"}
             and all(_number(phase[k]) and phase[k] < 100 and phase[k] <= previous[k] for k in phase),
             "earlier source phase charge invalid")
    reuse = envelope["reuse"]
    _require(set(reuse) == {"calendar", "contexts", "source_identity"}
             and set(reuse["contexts"]) == {str(y) for y in range(2020, 2025)}, "all five contexts and calendar must be bound")
    original = Path(envelope["original_output"])
    _require(reuse["calendar"]["path"] == str(original / "calendar.json")
             and all(item["path"] == str(original / "private" / "context" / (year + ".parquet"))
                     for year, item in reuse["contexts"].items()), "aliases must name the exact original context/calendar slots")
    for item in (reuse["calendar"], *reuse["contexts"].values(), *envelope["previous_receipts"]):
        _require({"path", "sha256", "bytes"} <= set(item) and Path(item["path"]).is_absolute()
                 and type(item["bytes"]) is int and item["bytes"] > 0
                 and isinstance(item["sha256"], str) and len(item["sha256"]) == 64
                 and all(c in "0123456789abcdef" for c in item["sha256"]), "exact immutable reuse/receipt binding required")
    _require(len(envelope["previous_receipts"]) == 4, "original failure and diagnosis receipts required")
    if source_plan is not None:
        identity = reuse["source_identity"]
        _require(set(identity) == {"source_policy", "calendar", "queries", "accepted_features"}
                 and all(identity[k] == source_plan[k] for k in identity), "reused contexts have different source identities")
    return envelope


def caps(spec):
    envelope = spec.get("recovery_envelope")
    if envelope is None:
        return dict(wall_seconds=600, CPU_seconds=600, prior_retained_bytes=0, prior_reserved=0)
    validate(envelope, source_plan=spec["source_plan"], output=spec["output"])
    limits = envelope["remaining_limits"]; previous = envelope["previous_consumption"]
    return dict(wall_seconds=limits["wall_seconds"], CPU_seconds=limits["CPU_seconds"],
                prior_retained_bytes=previous["retained_bytes"], prior_reserved=previous["prior_vector_reservations"])


def campaign_charge(previous, newly_charged, incoming=0):
    _require(all(type(v) is int and v >= 0 for v in (previous, newly_charged, incoming)), "retention counters must be nonnegative integers")
    total = previous + newly_charged + incoming
    _require(total <= CAMPAIGN_BYTES, "combined failed+recovery48MiB exhausted before write")
    return total


def expected_external_argv(freeze, supplied):
    """Exact native timeout command; a Python timer cannot replace this bound."""
    duration = caps(freeze["execution_metadata"])["wall_seconds"]
    _require(freeze.get("external_timeout_seconds", 600) == duration, "native outer timeout differs from remaining cap")
    return [freeze["external_timeout"]["path"], "--signal=KILL", "--kill-after=1s", str(duration) + "s",
            freeze["environment"]["executable"], "-B", freeze["tools"]["supervisor"]["path"],
            "--freeze", supplied.freeze, "--freeze-sha256", supplied.freeze_sha256]


def expand_environment(freeze, *, pin):
    """Authenticate and expand a compact reference, preserving EVERY old pin."""
    if "environment_reference" not in freeze:
        _require("environment" in freeze and not freeze["execution_metadata"].get("recovery_envelope"),
                 "explicit recovery must use authenticated inherited environment reference")
        return freeze
    _require("environment" not in freeze, "environment cannot be both inline and referenced")
    ref = freeze["environment_reference"]
    _require(set(ref) == {"path", "bytes", "sha256", "json_pointer", "environment_sha256"}
             and ref["json_pointer"] == "/environment", "exact environment reference required")
    _require({k: ref[k] for k in ("path", "bytes", "sha256")} == freeze["parent_execution"],
             "environment must come from original authenticated parent")
    matches = [b for b in freeze["bindings"] if b["path"] == ref["path"]]
    _require(len(matches) == 1 and all(matches[0][k] == ref[k] for k in ("path", "bytes", "sha256")),
             "environment parent missing from full identity inventory")
    pin(matches[0])
    environment = json.loads(Path(ref["path"]).read_text())["environment"]
    body = json.dumps(environment, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    _require(hashlib.sha256(body).hexdigest() == ref["environment_sha256"] and environment.get("file_bindings"),
             "complete inherited environment inventory changed")
    result = dict(freeze); result["environment"] = environment
    return result
