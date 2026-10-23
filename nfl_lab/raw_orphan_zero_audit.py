"""Separate orphan-aware zero-support audit; no accepted-label application."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import gzip
import io
import json
from pathlib import Path
import stat
import time

VERSION = "raw-orphan-explicit-zero-audit-v2"
PRIMITIVES = ["passing_yards", "passing_tds", "completions", "attempts", "passing_interceptions",
    "rushing_yards", "carries", "receptions", "receiving_yards", "rushing_tds", "receiving_tds"]
BUDGETS = {"invocations": 1, "HTTP": 0, "automatic_retries": 0, "wall_seconds": 60,
    "CPU_seconds": 60, "combined_RSS_bytes": 268435456, "numerical_threads": 1,
    "raw_rows": 200, "union_units": 200, "new_retained_bytes": 1048576,
    "fits": 0, "predictions": 0, "forecast_scores": 0, "zeros_applied": 0}
CODE = ["nfl_lab/raw_orphan_zero_audit.py", "nfl_lab/raw_orphan_context.py", "nfl_lab/ftn_zero_join.py",
    "nfl_lab/operational_storage.py", "nfl_lab/owned_reference_batch.py"]
INPUTS = ["source_manifest", "raw_statistics", "appearance_projection", "accepted_metadata",
    "global_forecast_freeze", "screen_query", "structural_aggregate", "structural_inventory",
    "structural_union", "structural_supervisor"]
PROJECTION = {"fixed_game": "2024_01_BAL_KC", "raw_records": 67, "offered_records": 31,
    "appearance_records": 163, "positive_witnesses": 92, "known_union_players": 97,
    "missing_identity_records": 1, "conservative_union_units": 98, "maximum_raw_rows": 200,
    "raw_primitive_columns": PRIMITIVES, "exact_PPR": "BLOCKED"}


def audit_zero_candidates(raw, offered, witnesses, accepted, *, projection_sha256,
        structural_projection_sha256, structural_records, structural_union, structural_coverage):
    """Audit all known opportunities and orphan coverage without changing inputs.

    Complete context reconciliation precedes primitive arithmetic. The unchanged
    v1 helper remains strict; its two pure arithmetic functions are called only
    for uniquely identified, structurally admissible source records.
    """
    from .raw_orphan_context import RAW, OFFERED, partition_context
    from .ftn_zero_join import (HISTORY_COLUMNS, TARGETS, _columns, _context,
        _old_support, _target)
    import pandas as pd
    if (not isinstance(raw, list) or len(raw) != 67
            or any(not isinstance(row, dict) or set(row) != set(RAW + PRIMITIVES) for row in raw)):
        raise ValueError("complete original19-column67-record projection required")
    if not isinstance(accepted, list) or len(accepted) > 200 or any(
            not isinstance(row, dict) or set(row) != set(HISTORY_COLUMNS) for row in accepted):
        raise ValueError("bounded original accepted metadata only required")
    context = [{name: row[name] for name in RAW} for row in raw]
    records, union, coverage = partition_context(context, offered, witnesses,
        raw_projection_sha256=structural_projection_sha256)
    if records != structural_records or union != structural_union or coverage != structural_coverage:
        raise ValueError("complete original structural inventory/union/coverage mismatch")
    if not isinstance(projection_sha256, str) or len(projection_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in projection_sha256):
        raise ValueError("new complete primitive projection digest required")
    history = pd.DataFrame(accepted, columns=HISTORY_COLUMNS)
    _columns(history, HISTORY_COLUMNS, 200); _context(history)
    if history.player_id.duplicated().any():
        raise ValueError("ambiguous original accepted identity metadata")
    old = {row["player_id"]: row for row in accepted}
    offers = {row["player_id"]: row for row in offered}
    groups = {}
    inventory = []
    for ordinal, (original, metadata) in enumerate(zip(raw, records)):
        inventory.append({**original, **{key: value for key, value in metadata.items() if key not in RAW},
            "structural_record_locator": metadata["record_locator"],
            "record_locator": f"{projection_sha256}:{ordinal}"})
        if original["player_id"] is not None:
            groups.setdefault(original["player_id"], []).append((original, metadata))
    rows, orphan_rows = [], []
    for member in union:
        player = member["player_id"]
        matches, q, h = groups.get(player, []), offers.get(player), old.get(player)
        valid_raw = len(matches) == 1 and matches[0][1]["eligible_for_identified_context_view"]
        raw_record = matches[0][0] if valid_raw else None
        history_conflict = q is not None and (h is None or any(
            not isinstance(q[name], str) or not isinstance(h[name], str) or q[name] != h[name]
            for name in ("position", "team", "opponent")))
        prior = _old_support(h)
        position = q["position"] if q is not None else None
        for target, (fields, roles, kind) in TARGETS.items():
            state, zero, zero_kind = _target(raw_record, fields, kind)
            if kind != "blocked" and len(matches) > 1:
                state, zero, zero_kind = "AMBIGUOUS_RAW_ROWS", False, ""
            elif kind != "blocked" and member["raw_offered_team_context_conflict"]:
                state, zero, zero_kind = "QUARANTINED_RAW_OFFERED_TEAM_CONFLICT", False, ""
            primary = q is not None and isinstance(position, str) and position in roles
            unknown_position = not isinstance(position, str) or not position.strip()
            population = ("NOT_OFFERED" if q is None else "OFFERED_UNKNOWN_POSITION" if unknown_position
                else "PRIMARY_OFFERED" if primary else "OFFERED_OUTSIDE_PRIMARY")
            reasons = []
            if q is None: reasons.append("NOT_ORIGINALLY_OFFERED")
            elif unknown_position: reasons.append("UNKNOWN_OFFERED_POSITION")
            elif not primary: reasons.append("OUTSIDE_ORIGINAL_PRIMARY_POPULATION")
            if not member["positive_ftn_witness"]: reasons.append("NO_POSITIVE_FTN_WITNESS")
            if not matches: reasons.append("NO_IDENTIFIED_RAW_MATCH")
            elif len(matches) > 1: reasons.append("AMBIGUOUS_RAW_ROWS")
            if member["raw_offered_team_context_conflict"]: reasons.append("RAW_OFFERED_TEAM_CONFLICT")
            if history_conflict: reasons.append("OFFERED_ACCEPTED_CONTEXT_CONFLICT")
            if prior == "UNRESOLVED": reasons.append("OLD_SUPPORT_UNRESOLVED")
            if kind == "blocked": reasons.append("EXACT_PPR_BLOCKED")
            elif not zero: reasons.append("TARGET_NOT_SUPPORTED_ZERO")
            eligible = not reasons and valid_raw
            new_support = bool(eligible and prior == "OLD_UNKNOWN")
            already = bool(eligible and prior == "ALREADY_PLAYED")
            rows.append({"player_id": player, "target": target, "raw_record_count": len(matches),
                "offered": q is not None, "position": position, "population": population,
                "positive_ftn_witness": member["positive_ftn_witness"],
                "structurally_usable_raw": bool(valid_raw), "old_support": prior,
                "raw_offered_context_conflict": member["raw_offered_team_context_conflict"],
                "offered_accepted_context_conflict": bool(history_conflict),
                "target_state": state, "known_zero": bool(zero), "zero_kind": zero_kind,
                "candidate_new_support": new_support, "already_supported_zero": already,
                "qualification_state": "CANDIDATE_NEW_ZERO_SUPPORT" if new_support else
                    "ALREADY_SUPPORTED_ZERO" if already else "UNRESOLVED_OR_INELIGIBLE",
                "unresolved_reasons": reasons})
    for record in inventory:
        if record["player_id"] is None:
            for target, (_, _, kind) in TARGETS.items():
                orphan_rows.append({"record_locator": record["record_locator"], "target": target,
                    "identity_state": "QUARANTINED_MISSING_PLAYER_ID", "known_zero": False,
                    "target_state": "BLOCKED_EXACT_PPR" if kind == "blocked" else "UNIDENTIFIED_RAW_RECORD",
                    "candidate_new_support": False, "already_supported_zero": False})
    target_counts = {}
    for target in TARGETS:
        selected = [row for row in rows if row["target"] == target]
        populations = {}
        for population in ("PRIMARY_OFFERED", "OFFERED_OUTSIDE_PRIMARY", "OFFERED_UNKNOWN_POSITION", "NOT_OFFERED"):
            packet = [row for row in selected if row["population"] == population]
            populations[population] = {"known_player_opportunities": len(packet),
                "target_states": dict(Counter(row["target_state"] for row in packet)),
                "known_zero_states": sum(row["known_zero"] for row in packet),
                "positive_witnesses": sum(row["positive_ftn_witness"] for row in packet),
                "candidate_new_support": sum(row["candidate_new_support"] for row in packet),
                "already_supported_zero": sum(row["already_supported_zero"] for row in packet),
                "unresolved_reason_counts": dict(Counter(reason for row in packet for reason in row["unresolved_reasons"]))}
        target_counts[target] = {"all_known_player_opportunities": len(selected),
            "original_offered_opportunities": sum(row["offered"] for row in selected),
            "unidentified_raw_record_opportunities": sum(row["target"] == target for row in orphan_rows),
            "populations": populations}
    aggregate = {"schema_version": VERSION, "state": "CANDIDATE_AUDIT_ONLY",
        "coverage": coverage, "known_player_target_rows": len(rows), "orphan_target_rows": len(orphan_rows),
        "targets": target_counts, "zeros_applied": 0, "fits_predictions_scores_HTTP": 0,
        "accepted_history_source_policy_or_forecasts_changed": False,
        "no_complete_participation_DNP_PPR_or_historical_availability_contract": True}
    return inventory, rows, orphan_rows, aggregate


def _load_spec(path, expected):
    path = Path(path)
    if (not path.is_absolute() or ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents))
            or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > 1048576):
        raise ValueError("canonical bounded registration required")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError("registration digest mismatch")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate registration key")
            result[key] = value
        return result
    def invalid(value): raise ValueError("nonfinite registration value")
    spec = json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)
    keys = {"schema_version", "state", "budgets", "projection", "cache", "output", "screen_output",
        "source_policy", "code_sha256", "environment", "software_check_budget", "agent_settings", *INPUTS}
    if (set(spec) != keys or spec["schema_version"] != VERSION or spec["state"] != "BOUND_READY"
            or spec["budgets"] != BUDGETS or spec["projection"] != PROJECTION):
        raise ValueError("exact bound orphan-aware audit registration required")
    return spec


def run_audit(path, config_sha256):
    spec = _load_spec(path, config_sha256)  # Unbound denial before source imports.
    from .raw_orphan_context import RAW, OFFERED
    from .ftn_zero_join import (_read, _json, _fixed_table, _witnesses, PINNED,
        APPEARANCE_COLUMNS, HISTORY_COLUMNS, validate_global_freeze)
    from .operational_storage import OperationalStorage
    from .owned_reference_batch import validate_owned_references
    import pandas as pd
    import pyarrow.parquet as pq
    started, cpu_started = time.monotonic(), time.process_time()
    root = Path(__file__).resolve().parent.parent
    if set(spec["code_sha256"]) != set(CODE):
        raise ValueError("exact original helpers plus separate wrapper required")
    def check():
        if time.monotonic() - started >= 45 or time.process_time() - cpu_started >= 45:
            raise TimeoutError("audit finalization reserve")
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != config_sha256:
            raise ValueError("registration changed")
        for name, digest in spec["code_sha256"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
                raise ValueError("frozen code changed")
    check()
    for name in ("source_manifest", "raw_statistics", "appearance_projection", "accepted_metadata", "source_policy"):
        if spec[name]["sha256"] != PINNED[name]:
            raise ValueError("original source/history/policy binding changed")
    parent = Path(spec["screen_output"])
    if (Path(spec["global_forecast_freeze"]["path"]) != parent / "forecast-freeze.json"
            or Path(spec["screen_query"]["path"]) != parent / "private/queries/2024.parquet"):
        raise ValueError("original frozen query association changed")
    validate_global_freeze(_json(_read(spec["global_forecast_freeze"])), spec["screen_query"]["sha256"])
    source = _json(_read(spec["source_manifest"]))["sources"]["stats_player_week_2024.parquet"]
    if any(source[k] != spec["raw_statistics"][k] for k in ("sha256", "bytes")):
        raise ValueError("original source manifest mismatch")
    storage = OperationalStorage(spec["cache"], _json(_read(spec["source_policy"])))
    refs = {spec[name]["path"]: spec[name]["sha256"] for name in INPUTS}
    resolved, entry = validate_owned_references(storage, refs)
    if any(resolved[spec[name]["path"]]["bytes"] != spec[name]["bytes"] for name in INPUTS):
        raise ValueError("owned input byte mismatch")
    prior, terminal = (_json(_read(spec[name])) for name in ("structural_aggregate", "structural_supervisor"))
    if (prior["state"] != "STRUCTURAL_QUARANTINE_ONLY" or terminal["state"] != "STRUCTURAL_QUARANTINE_ONLY"
            or prior["zeros_applied"] != 0 or prior["source_policy_accepted_labels_forecasts_changed"] is not False):
        raise ValueError("successful unchanged structural prerequisite required")
    for name, expected in (("raw_planned_records", 67), ("known_union_players", 97),
            ("missing_identity_raw_records", 1), ("original_offered_players", 31),
            ("positive_ftn_witness_players", 92), ("conservative_union_plus_orphan_units", 98)):
        if prior["coverage"][name] != expected:
            raise ValueError("original complete structural denominator changed")
    if any(prior["input_sha256s"][name] != spec[name]["sha256"] for name in (
            "source_manifest", "raw_statistics", "appearance_projection", "global_forecast_freeze", "screen_query")):
        raise ValueError("structural source/query versions changed")
    output = Path(spec["output"])
    if output.exists() or output != Path("/workspace/website-methods-research/resumed/raw-orphan-zero-audit-v2-20261023"):
        raise ValueError("fresh fixed audit namespace required")
    storage.register_root(output)
    storage.atomic_json(output / "AUDIT_CONSUMED.json", {"schema_version": VERSION,
        "config_sha256": config_sha256, "at": datetime.now(timezone.utc).isoformat(), "automatic_retries": 0})
    state = "FAILED"
    try:
        structural_records = _json(_read(spec["structural_inventory"]))
        structural_union = _json(_read(spec["structural_union"]))
        check()
        raw = _fixed_table(spec["raw_statistics"]["path"], RAW + PRIMITIVES, limit=200)
        offered = _fixed_table(spec["screen_query"]["path"], OFFERED, limit=200)
        accepted = _fixed_table(spec["accepted_metadata"]["path"], HISTORY_COLUMNS, limit=200)
        appearance = _fixed_table(spec["appearance_projection"]["path"], APPEARANCE_COLUMNS, "nflverse_game_id", 10000)
        if appearance.num_rows != 163:
            raise ValueError("complete original163-play projection required")
        witnesses = _witnesses(appearance.to_pandas(types_mapper=pd.ArrowDtype))
        buffer = io.BytesIO(); pq.write_table(raw, buffer, compression="zstd")
        body = buffer.getvalue(); projection_sha = hashlib.sha256(body).hexdigest()
        storage.write_bytes(output / "private/raw-context-primitives.parquet", body)
        inventory, rows, orphans, aggregate = audit_zero_candidates(raw.to_pylist(), offered.to_pylist(),
            witnesses, accepted.to_pylist(), projection_sha256=projection_sha,
            structural_projection_sha256=prior["raw_projection_sha256"], structural_records=structural_records,
            structural_union=structural_union, structural_coverage=prior["coverage"])
        # Full original primitive values (including null/nonfinite encodings)
        # stay in immutable Parquet. JSON inventory uses that exact row locator,
        # avoiding a nonfinite-to-zero conversion or lossy JSON coercion.
        storage.atomic_json(output / "private/raw-record-inventory.json", [
            {key: value for key, value in row.items() if key not in PRIMITIVES} for row in inventory])
        body = (json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        storage.write_bytes(output / "private/known-player-target-rows.json.gz", gzip.compress(body, mtime=0))
        storage.atomic_json(output / "private/orphan-target-rows.json", orphans)
        check()
        _, exit_receipt = validate_owned_references(storage, refs)
        _read(spec["source_policy"]); check()
        report = {**aggregate, "config_sha256": config_sha256, "raw_projection_sha256": projection_sha,
            "input_sha256s": {name: spec[name]["sha256"] for name in INPUTS}, "HTTP": 0,
            "agent_settings": spec["agent_settings"], "usage_before_result_write": {
                "wall_seconds": time.monotonic() - started, "CPU_seconds": time.process_time() - cpu_started}}
        storage.atomic_json(output / "aggregate.json", report)
        storage.atomic_json(output / "reference-validation.json", {"before_decode": entry, "after_decode": exit_receipt})
        state = "CANDIDATE_AUDIT_ONLY"
        return report
    except BaseException as error:
        storage.atomic_json(output / "AUDIT_FAILURE.json", {"state": "FAILED", "error_type": type(error).__name__,
            "reason": "AUDIT_FAILURE_NO_RETRY", "successful_subset_returned": False, "zeros_applied": 0})
        raise
    finally:
        storage.atomic_json(output / "AUDIT_FINISHED.json", {"state": state, "config_sha256": config_sha256,
            "HTTP": 0, "zeros_applied": 0, "wall_seconds_before_final_write": time.monotonic() - started,
            "CPU_seconds_before_final_write": time.process_time() - cpu_started})
