"""Prepare and validate an unqualified H3 point for the existing lab writer.

This module does not acquire sources, write records, fit models or register a
confirmation experiment. Source authenticity remains the upstream binder's job.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from . import research_passing
from .receiving import _document
from .state import digest, now_utc, source_tree_digest, utc

FUNCTIONAL = "fixed_opportunity_rate_point; mean_or_median_unverified"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/recorded-research-point-v1.json"
RESEARCH_SCHEMA = ROOT / "schemas/research-point-v1.json"
CONFIG = ROOT / "config/research-passing-v1.json"
SCHEMA_NAME = "nfl-lab-recorded-research-point-v1"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validator():
    registry = Registry().with_resource("urn:nfl-lab:research-point-v1",
        Resource.from_contents(json.loads(RESEARCH_SCHEMA.read_text())))
    return Draft202012Validator(json.loads(SCHEMA.read_text()), registry=registry,
                                format_checker=FormatChecker())


def validate_recorded_point(row, *, require_issued=True):
    """Check the strict envelope, immutable result binding and actual clocks."""
    checked = row
    if not require_issued:
        checked = {**row, "issued_at": row["calculation_completed_at"]}
    _validator().validate(checked)
    if isinstance(row["point"],bool) or not math.isfinite(row["point"]):
        raise ValueError("invalid research point")
    result = row["research_result"]
    context = result["context"]
    if digest(result) != row["research_result_sha256"]:
        raise ValueError("research result checksum mismatch")
    if row["recorded_schema_sha256"] != _sha(SCHEMA) or row["research_schema_sha256"] != _sha(RESEARCH_SCHEMA):
        raise ValueError("research schema release mismatch")
    if row["model_config_sha256"] != _sha(CONFIG):
        raise ValueError("research configuration release mismatch")
    if row["research_module_sha256"] != result["code_sha256"]:
        raise ValueError("research module binding mismatch")
    if row["research_module_sha256"] != _sha(research_passing.__file__):
        raise ValueError("research module release mismatch")
    if row["input_sha256"] != result["input_sha256"]:
        raise ValueError("research input binding mismatch")
    metadata = row["projection_identity"]
    if (digest(metadata) != row["projection_identity_sha256"]
            or metadata["payload_sha256"] != result["source_sha256"].get(metadata["reference"])
            or any(row[field] != metadata[field] for field in ("player_id", "game_id", "sleeper_id", "position"))):
        raise ValueError("projection operational identity binding mismatch")
    for field in ("player_id", "game_id", "team", "opponent", "season", "week", "baseline_receipt_sha256"):
        if row[field] != context.get(field):
            raise ValueError("research identity binding mismatch: " + field)
    if context.get("season_type") != "REG" or context.get("period") != "full_game_with_ot":
        raise ValueError("unsupported research period")
    if row["team"] == row["opponent"]:
        raise ValueError("invalid research opponent")
    if utc(row["feature_cutoff_utc"]) != utc(context["cutoff_at"]) or utc(row["kickoff_utc"]) != utc(context["kickoff_at"]):
        raise ValueError("research clock binding mismatch")
    if row["point"] != result["point"] or result["state"] == "ABSTAIN":
        raise ValueError("unrecordable research result")
    expected_fallback = result["reason"] if result["state"] == "UNCHANGED_WEBSITE_FALLBACK" else None
    if row["fallback"] != expected_fallback:
        raise ValueError("research fallback binding mismatch")
    cutoff, start, calculated, completed, kickoff = map(utc, (
        row["feature_cutoff_utc"], row["calculation_started_at"], result["calculated_at"],
        row["calculation_completed_at"], row["kickoff_utc"]))
    if not cutoff <= start <= calculated <= completed < kickoff:
        raise ValueError("invalid research calculation chronology")
    if result["calculation_lane"] not in {"PREGAME_UNRECORDED_ARITHMETIC", "AFTER_CUTOFF_UNRECORDED_ARITHMETIC"}:
        raise ValueError("retrospective research result cannot be issued")
    if require_issued and not completed <= utc(row["issued_at"]) < kickoff:
        raise ValueError("invalid research issuance chronology")


def prepare_recorded_point(context, *, opportunities, statistics, projection, trusted_hashes):
    """Calculate from supplied authenticated documents; return a row or abstain.

Operational identity comes from the validated result. Sleeper ID and position
must be explicit in its same authenticated projection, rather than overrides.
The returned row has no issuance clock; only state.capture may add that clock.
An ABSTAIN returns None and cannot become a forecast or an invented fallback.
"""
    initial_code = source_tree_digest(ROOT)
    config_sha, schema_sha, research_schema_sha = _sha(CONFIG), _sha(SCHEMA), _sha(RESEARCH_SCHEMA)
    module_sha = _sha(research_passing.__file__)
    if module_sha != research_passing.CODE_SHA256:
        raise ValueError("loaded research module differs from source")
    started = now_utc()
    result = research_passing.evaluate(deepcopy(context), opportunities=opportunities,
        statistics=statistics, projection=projection, trusted_hashes=trusted_hashes).to_dict()
    # Validate the extra operational metadata against the same pinned bytes.
    original = None if result["state"] == "ABSTAIN" else _document(
        projection, trusted_hashes, utc(result["context"]["cutoff_at"]))
    if (source_tree_digest(ROOT) != initial_code or _sha(SCHEMA) != schema_sha
            or _sha(RESEARCH_SCHEMA) != research_schema_sha or _sha(CONFIG) != config_sha):
        raise ValueError("source changed during research calculation")
    completed = now_utc()
    if result["state"] == "ABSTAIN":
        return None
    identity = result["context"]
    metadata = {"player_id":identity["player_id"],"game_id":identity["game_id"],
        "sleeper_id":original.get("sleeper_id"), "position":original.get("position"),
        "reference":projection.reference,"payload_sha256":hashlib.sha256(projection.payload).hexdigest()}
    row = {key: identity[key] for key in (
        "player_id", "game_id", "team", "opponent", "season", "week", "baseline_receipt_sha256")}
    row.update(schema_version="lab-recorded-research-point-v1", sleeper_id=original.get("sleeper_id"),
        position=original.get("position"), target="pass_yd", period="full_game",
        model_id=research_passing.METHOD, model_state="UNQUALIFIED_SHADOW", scoring_id="nfl-full-game-v1",
        model_config_sha256=config_sha, input_sha256=result["input_sha256"], code_sha256=initial_code,
        research_module_sha256=module_sha, research_schema_sha256=research_schema_sha,
        recorded_schema_sha256=schema_sha, research_result_sha256=digest(result), research_result=result,
        projection_identity=metadata, projection_identity_sha256=digest(metadata),
        kickoff_utc=utc(identity["kickoff_at"]).isoformat(),
        feature_cutoff_utc=utc(identity["cutoff_at"]).isoformat(),
        calculation_started_at=started.isoformat(), calculation_completed_at=completed.isoformat(),
        point=result["point"], prediction_functional=FUNCTIONAL,
        fallback=result["reason"] if result["state"] == "UNCHANGED_WEBSITE_FALLBACK" else None,
        qualified_for_default=False, original_runner_reproduced=False,
        code_integrity="pre_post_source_digest_required")
    validate_recorded_point(row, require_issued=False)
    if (source_tree_digest(ROOT) != initial_code or _sha(SCHEMA) != schema_sha
            or _sha(RESEARCH_SCHEMA) != research_schema_sha or _sha(CONFIG) != config_sha):
        raise ValueError("source changed during research preparation validation")
    return row
