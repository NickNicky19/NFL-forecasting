"""One fixed-game, eight-column diagnostic; no statistics, joins or repairs.

Only aggregate field-null/mismatch counts may be retained. Context rows remain
in memory and are never published. A failed prior join stays failed and consumed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

VERSION = "ftn-context-metadata-diagnosis-v2"
GAME = "2024_01_BAL_KC"
CONTEXT = ["game_id", "season", "week", "season_type", "player_id", "team", "opponent_team", "position"]
BUDGETS = {"invocations": 1, "HTTP": 0, "automatic_retries": 0, "wall_seconds": 60,
           "CPU_seconds": 60, "combined_RSS_bytes": 268435456, "numerical_threads": 1,
           "raw_rows": 200, "new_retained_bytes": 1048576, "fits": 0, "forecast_scores": 0}
CODE = ["nfl_lab/ftn_context_metadata_diagnosis.py", "nfl_lab/ftn_context_metadata_diagnosis_v2.py", "nfl_lab/ftn_zero_join.py",
        "nfl_lab/operational_storage.py", "nfl_lab/owned_reference_batch.py"]


# Reuse the unchanged counts-only arithmetic; this version changes execution
# orchestration/provenance only, not a field, row, missingness or gate definition.
from .ftn_context_metadata_diagnosis import diagnose_context


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
                     "prior_supervisor_receipt", "prior_diagnosis_failure", "code_sha256", "environment"}
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
    diagnosis_failure = _json(_read(spec["prior_diagnosis_failure"]))
    if (prior.get("state") != "NOT_READY" or prior.get("diagnostic", {}).get("reason") != "fixed-game context mismatch"
            or supervisor.get("state") != "FAILED" or supervisor.get("zeros_applied") != 0
            or diagnosis_failure.get("state") != "FAILED"
            or diagnosis_failure.get("stop_reason") != "COMBINED_RSS_SAFETY_MARGIN"
            or diagnosis_failure.get("zeros_applied") != 0):
        raise ValueError("exact failed prior attempt required")
    policy = _json(_read(spec["source_policy"]))
    storage = OperationalStorage(spec["cache"], policy)
    inputs = ("raw_statistics", "source_manifest", "prior_join_failure", "prior_supervisor_receipt", "prior_diagnosis_failure")
    refs = {spec[name]["path"]: spec[name]["sha256"] for name in inputs}
    resolved, before = validate_owned_references(storage, refs)
    if any(resolved[spec[name]["path"]]["bytes"] != spec[name]["bytes"] for name in inputs):
        raise ValueError("owned input size mismatch")
    output = Path(spec["output"])
    if output.exists() or output != Path("/workspace/website-methods-research/resumed/ftn-context-metadata-diagnosis-v2-20261023"):
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
