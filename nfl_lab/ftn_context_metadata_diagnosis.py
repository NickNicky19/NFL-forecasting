"""One fixed-game, eight-column diagnostic; no statistics, joins or repairs.

Only aggregate field-null/mismatch counts may be retained. Context rows remain
in memory and are never published. A failed prior join stays failed and consumed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

VERSION = "ftn-context-metadata-diagnosis-v1"
GAME = "2024_01_BAL_KC"
CONTEXT = ["game_id", "season", "week", "season_type", "player_id", "team", "opponent_team", "position"]
REQUIRED = [x for x in CONTEXT if x != "position"]
GSIS = re.compile(r"^[0-9]{2}-[0-9]{7}$")
BUDGETS = {"invocations": 1, "HTTP": 0, "automatic_retries": 0, "wall_seconds": 60,
           "CPU_seconds": 60, "combined_RSS_bytes": 268435456, "numerical_threads": 1,
           "raw_rows": 200, "new_retained_bytes": 1048576, "fits": 0, "forecast_scores": 0}
CODE = ["nfl_lab/ftn_context_metadata_diagnosis.py", "nfl_lab/ftn_zero_join.py",
        "nfl_lab/operational_storage.py", "nfl_lab/owned_reference_batch.py"]


def diagnose_context(rows):
    """Return counts only, retaining every projected row, even invalid identities."""
    if (not isinstance(rows, list) or len(rows) > 200
            or any(not isinstance(x, dict) or set(x) != set(CONTEXT) for x in rows)):
        raise ValueError("exact eight-column context rows and cap required")
    nulls = {field: sum(row[field] is None for row in rows) for field in CONTEXT}
    expected = {"game_id": GAME, "season": 2024, "week": 1, "season_type": "REG"}
    mismatches = {field: sum(row[field] is not None and row[field] != value for row in rows)
                  for field, value in expected.items()}
    mismatches["team_outside_fixed_game_nonnull"] = sum(
        row["team"] is not None and row["team"] not in ("BAL", "KC") for row in rows)
    mismatches["opponent_not_reciprocal_for_supported_team_nonnull"] = sum(
        row["team"] in ("BAL", "KC") and row["opponent_team"] is not None
        and row["opponent_team"] != {"BAL": "KC", "KC": "BAL"}[row["team"]] for row in rows)
    mismatches["player_id_noncanonical_nonnull"] = sum(
        row["player_id"] is not None and (not isinstance(row["player_id"], str)
        or GSIS.fullmatch(row["player_id"]) is None) for row in rows)
    # Match the original gate order without invoking it or filtering its inputs.
    stage_one = sum(any(row[x] is None for x in REQUIRED)
                    or any(row[field] != value for field, value in expected.items()) for row in rows)
    stage_two = sum(row["team"] not in ("BAL", "KC")
                    or row["opponent_team"] != {"BAL": "KC", "KC": "BAL"}.get(row["team"]) for row in rows)
    stage_three = sum(not isinstance(row["player_id"], str)
                      or GSIS.fullmatch(row["player_id"]) is None for row in rows)
    return {"projected_rows": len(rows), "projected_columns": list(CONTEXT),
        "null_counts": nulls, "nonnull_mismatch_counts": mismatches,
        "original_context_gate_fail_counts": {"first_fixed_game_context_gate": stage_one,
            "second_team_opponent_gate": stage_two, "third_identity_gate": stage_three},
        "original_context_gate_would_pass": not any((stage_one, stage_two, stage_three)),
        "all_projected_rows_retained_in_counts": True, "raw_context_rows_persisted": 0,
        "player_ids_or_statistic_values_reported": 0, "primitive_columns_read": 0,
        "repairs_filters_joins_or_applied_zeros": 0}


def run_diagnosis(path, config_sha256):
    """Execute only after a separately bound registration/freeze and root GO."""
    from .ftn_zero_join import _read, _json, _fixed_table, PINNED
    from .operational_storage import OperationalStorage
    from .owned_reference_batch import validate_owned_references
    started, cpu_started = time.monotonic(), time.process_time()
    config_path = Path(path)
    body = _read({"path": str(config_path), "sha256": config_sha256, "bytes": config_path.stat().st_size})
    spec = _json(body)
    if (set(spec) != {"schema_version", "state", "budgets", "projection", "cache", "output",
                     "source_manifest", "raw_statistics", "source_policy", "prior_join_failure",
                     "prior_supervisor_receipt", "code_sha256", "environment"}
            or spec["schema_version"] != VERSION or spec["state"] != "BOUND_READY"
            or spec["budgets"] != BUDGETS
            or spec["projection"] != {"fixed_game": GAME, "columns": CONTEXT, "maximum_rows": 200}):
        raise ValueError("exact bound context-only registration required")
    root = Path(__file__).resolve().parent.parent
    if set(spec["code_sha256"]) != set(CODE):
        raise ValueError("exact original and diagnostic code pins required")
    def code_check():
        for name, digest in spec["code_sha256"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
                raise ValueError("frozen code changed")
        if hashlib.sha256(config_path.read_bytes()).hexdigest() != config_sha256:
            raise ValueError("frozen registration changed")
    code_check()
    for name in ("raw_statistics", "source_manifest", "source_policy"):
        if spec[name]["sha256"] != PINNED[name]:
            raise ValueError("original source or quota-policy binding changed")
    source = _json(_read(spec["source_manifest"]))["sources"]["stats_player_week_2024.parquet"]
    if any(source[key] != spec["raw_statistics"][key] for key in ("sha256", "bytes")):
        raise ValueError("source manifest mismatch")
    # The failed receipts authenticate provenance only; their result is immutable.
    prior = _json(_read(spec["prior_join_failure"]))
    supervisor = _json(_read(spec["prior_supervisor_receipt"]))
    if (prior.get("state") != "NOT_READY" or prior.get("diagnostic", {}).get("reason") != "fixed-game context mismatch"
            or supervisor.get("state") != "FAILED" or supervisor.get("zeros_applied") != 0):
        raise ValueError("exact failed prior attempt required")
    policy = _json(_read(spec["source_policy"]))
    storage = OperationalStorage(spec["cache"], policy)
    inputs = ("raw_statistics", "source_manifest", "prior_join_failure", "prior_supervisor_receipt")
    refs = {spec[name]["path"]: spec[name]["sha256"] for name in inputs}
    resolved, before = validate_owned_references(storage, refs)
    if any(resolved[spec[name]["path"]]["bytes"] != spec[name]["bytes"] for name in inputs):
        raise ValueError("owned input size mismatch")
    output = Path(spec["output"])
    if output.exists() or output != Path("/workspace/website-methods-research/resumed/ftn-context-metadata-diagnosis-v1-20261023"):
        raise ValueError("fresh fixed diagnosis namespace required; no retry")
    storage.register_root(output)
    storage.atomic_json(output / "DIAGNOSIS_CONSUMED.json", {
        "schema_version": VERSION, "config_sha256": config_sha256, "consumed_utc": datetime.now(timezone.utc).isoformat(),
        "invocations": 1, "HTTP": 0, "automatic_retries": 0, "primitive_columns_read": 0})
    terminal = "FAILED"
    try:
        if time.monotonic() - started >= 45 or time.process_time() - cpu_started >= 45:
            raise TimeoutError("context read finalization reserve")
        table = _fixed_table(spec["raw_statistics"]["path"], CONTEXT, limit=200)
        if table.column_names != CONTEXT:
            raise ValueError("unapproved context projection")
        aggregate = diagnose_context(table.to_pylist())
        del table
        _, after = validate_owned_references(storage, refs)
        code_check()
        _read(spec["source_policy"])
        result = {"schema_version": VERSION, "state": "CONTEXT_METADATA_DIAGNOSIS_ONLY",
            "config_sha256": config_sha256, "diagnosis": aggregate,
            "input_sha256s": {name: spec[name]["sha256"] for name in inputs},
            "prior_join_stays_failed_and_consumed": True, "source_or_accepted_data_changed": False,
            "HTTP": 0, "fits": 0, "forecast_scores": 0, "zeros_applied": 0,
            "historical_availability_or_participation_established": False,
            "usage_before_result_write": {"wall_seconds": time.monotonic() - started,
                "CPU_seconds": time.process_time() - cpu_started}}
        storage.atomic_json(output / "aggregate.json", result)
        storage.atomic_json(output / "reference-validation.json", {"before_decode": before, "after_decode": after})
        terminal = "CONTEXT_METADATA_DIAGNOSIS_ONLY"
        return result
    except BaseException as error:
        storage.atomic_json(output / "DIAGNOSIS_FAILURE.json", {
            "state": "FAILED", "error_type": type(error).__name__, "reason": "DIAGNOSIS_FAILED_NO_RETRY",
            "HTTP": 0, "zeros_applied": 0, "no_source_values_or_rows_reported": True})
        raise
    finally:
        storage.atomic_json(output / "DIAGNOSIS_FINISHED.json", {"state": terminal,
            "config_sha256": config_sha256, "HTTP": 0, "zeros_applied": 0,
            "wall_seconds_before_final_write": time.monotonic() - started,
            "CPU_seconds_before_final_write": time.process_time() - cpu_started})
