"""Full-record identity quarantine prerequisite; no statistics or label repair."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import time

VERSION = "raw-orphan-context-v1"
GAME = "2024_01_BAL_KC"
RAW = ["game_id", "season", "week", "season_type", "player_id", "team", "opponent_team", "position"]
OFFERED = ["season", "week", "game_id", "player_id", "position", "team", "opponent"]
GSIS = re.compile(r"^[0-9]{2}-[0-9]{7}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
BUDGETS = {"invocations": 1, "HTTP": 0, "automatic_retries": 0, "wall_seconds": 60,
    "CPU_seconds": 60, "combined_RSS_bytes": 268435456, "numerical_threads": 1,
    "raw_rows": 200, "union_units": 200, "new_retained_bytes": 1048576,
    "fits": 0, "predictions": 0, "forecast_scores": 0, "primitive_columns_read": 0, "zeros_applied": 0}
PROJECTION = {"fixed_game": GAME, "raw_columns": RAW, "offered_columns": OFFERED,
    "expected_raw_records": 67, "expected_offered_records": 31,
    "expected_appearance_rows": 163, "expected_witnesses": 92, "maximum_raw_rows": 200}
CODE = ["nfl_lab/raw_orphan_context.py", "nfl_lab/ftn_zero_join.py",
    "nfl_lab/operational_storage.py", "nfl_lab/owned_reference_batch.py"]
INPUTS = ["source_manifest", "raw_statistics", "appearance_projection", "global_forecast_freeze",
    "screen_query", "prior_context_diagnosis", "prior_context_supervisor"]
PRIOR = {"prior_context_diagnosis": "94833d4da0ae532b608de02c64b7509dae6c8de1193b09896adb791bf41793b0",
    "prior_context_supervisor": "e7e778fec941625ab835dd5513588615deca7f01cd316a2ee02eb6da73820c4a"}


def _identity(value):
    return isinstance(value, str) and GSIS.fullmatch(value) is not None


def _contexts(rows, columns, *, raw):
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError("bounded complete context records required")
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(columns):
            raise ValueError("exact registered context columns required")
        required = [x for x in columns if x != "position" and (not raw or x != "player_id")]
        if any(row[x] is None for x in required):
            raise ValueError("nonnull original context fields required")
        if (row["game_id"] != GAME or row["season"] != 2024 or row["week"] != 1
                or (raw and row["season_type"] != "REG")):
            raise ValueError("fixed-game context mismatch")
        opposite = "opponent_team" if raw else "opponent"
        if row["team"] not in ("BAL", "KC") or row[opposite] != {"BAL": "KC", "KC": "BAL"}[row["team"]]:
            raise ValueError("fixed-game team/opponent mismatch")
        if row["player_id"] is not None and not _identity(row["player_id"]):
            raise ValueError("nonnull identity must be canonical; no repair")
        if not raw and not _identity(row["player_id"]):
            raise ValueError("original offered identity must remain known")
        if row["position"] is not None and not isinstance(row["position"], str):
            raise ValueError("position type is unsupported; no coercion")


def _union(raw_ids, offered_ids, witnesses, orphan_count):
    known = raw_ids | offered_ids | witnesses
    if len(known) + orphan_count > 200:
        raise ValueError("complete known union plus unidentified records exceeds200")
    return known


def partition_context(raw, offered, witnesses, *, raw_projection_sha256):
    """Return private full inventory/union and public counts, without a stat join.

    No input record is repaired, dropped or chosen from a duplicate group. An
    ordinal is local to the immutable projection and is never a player identity.
    """
    _contexts(raw, RAW, raw=True)
    _contexts(offered, OFFERED, raw=False)
    if len(raw) != 67 or len(offered) != 31:
        raise ValueError("complete pinned67 raw/31 offered record counts required")
    if not isinstance(raw_projection_sha256, str) or SHA.fullmatch(raw_projection_sha256) is None:
        raise ValueError("immutable raw projection digest required")
    if (not isinstance(witnesses, set) or len(witnesses) != 92
            or any(not _identity(x) for x in witnesses)):
        raise ValueError("all92 canonical positive witnesses required")
    offered_ids = {x["player_id"] for x in offered}
    if len(offered_ids) != len(offered):
        raise ValueError("ambiguous original offered identities")
    counts = Counter(x["player_id"] for x in raw if x["player_id"] is not None)
    raw_ids, orphan_count = set(counts), sum(x["player_id"] is None for x in raw)
    known = _union(raw_ids, offered_ids, witnesses, orphan_count)
    offers = {x["player_id"]: x for x in offered}
    records = []
    for ordinal, row in enumerate(raw):
        player = row["player_id"]
        q = offers.get(player)
        conflict = None if q is None else row["team"] != q["team"] or row["opponent_team"] != q["opponent"]
        state = ("QUARANTINED_MISSING_PLAYER_ID" if player is None else
            "AMBIGUOUS_DUPLICATE_RAW_ID" if counts[player] > 1 else
            "QUARANTINED_RAW_OFFERED_TEAM_CONFLICT" if conflict else "IDENTIFIED_CONTEXT_RECORD")
        records.append({**row, "record_ordinal": ordinal,
            "record_locator": f"{raw_projection_sha256}:{ordinal}", "identity_state": state,
            "eligible_for_identified_context_view": state == "IDENTIFIED_CONTEXT_RECORD",
            "position_missing": row["position"] is None,
            "offered_team_context_conflict": conflict,
            "duplicate_raw_id_group": player is not None and counts[player] > 1})
    union = [{"player_id": player, "raw_record_count": counts.get(player, 0),
        "offered": player in offered_ids, "positive_ftn_witness": player in witnesses,
        "ambiguous_raw_id": counts.get(player, 0) > 1,
        "raw_offered_team_context_conflict": any(r["player_id"] == player
            and r["offered_team_context_conflict"] is True for r in records),
        "identified_context_view_match": any(r["player_id"] == player
            and r["eligible_for_identified_context_view"] for r in records),
        "identified_raw_match": player in raw_ids} for player in sorted(known)]
    aggregate = {"state": "STRUCTURAL_QUARANTINE_ONLY", "raw_planned_records": len(raw),
        "raw_inventory_records": len(records), "identified_raw_records": sum(counts.values()),
        "missing_identity_raw_records": orphan_count, "unique_identified_raw_players": len(raw_ids),
        "duplicate_raw_id_groups": sum(n > 1 for n in counts.values()),
        "duplicate_raw_records": sum(n for n in counts.values() if n > 1),
        "identified_context_view_records": sum(r["eligible_for_identified_context_view"] for r in records),
        "unresolved_raw_records": sum(not r["eligible_for_identified_context_view"] for r in records),
        "raw_offered_team_context_conflict_records": sum(r["offered_team_context_conflict"] is True for r in records),
        "raw_position_missing_records": sum(x["position"] is None for x in raw),
        "raw_identity_and_position_both_missing_records": sum(x["player_id"] is None and x["position"] is None for x in raw),
        "offered_position_missing_records": sum(x["position"] is None for x in offered),
        "original_offered_players": len(offered_ids), "positive_ftn_witness_players": len(witnesses),
        "known_union_players": len(known), "conservative_union_plus_orphan_units": len(known) + orphan_count,
        "offered_without_identified_raw": len(offered_ids - raw_ids),
        "witness_without_identified_raw": len(witnesses - raw_ids),
        "raw_without_witness": len(raw_ids - witnesses),
        "offered_without_raw_or_witness": len(offered_ids - raw_ids - witnesses),
        "inventory_reconciles": len(raw) == sum(counts.values()) + orphan_count,
        "all_original_offered_and_witnesses_retained": True,
        "identity_repairs_primitive_columns_zero_labels_fits_predictions_scores": 0,
        "no_participation_DNP_PPR_or_historical_availability_qualification": True}
    return records, union, aggregate


def _load_spec(path, expected):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_absolute() or ".." in path.parts:
        raise ValueError("canonical registration required")
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > 1048576:
        raise ValueError("bounded registration required")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError("registration digest mismatch")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate registration key")
            value[key] = item
        return value
    def invalid(value):
        raise ValueError("nonfinite registration value")
    spec = json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)
    keys = {"schema_version", "state", "budgets", "projection", "cache", "output", "screen_output",
        "source_policy", "code_sha256", "environment", "software_check_budget", "agent_settings", *INPUTS}
    if (set(spec) != keys or spec["schema_version"] != VERSION or spec["state"] != "BOUND_READY"
            or spec["budgets"] != BUDGETS or spec["projection"] != PROJECTION):
        raise ValueError("exact bound structural registration required")
    return spec


def run_prerequisite(path, config_sha256):
    spec = _load_spec(path, config_sha256)  # Unbound denial before heavy imports/readers.
    from .ftn_zero_join import (_read, _json, _fixed_table, _witnesses, PINNED,
        APPEARANCE_COLUMNS, validate_global_freeze)
    from .operational_storage import OperationalStorage
    from .owned_reference_batch import validate_owned_references
    import pandas as pd
    import pyarrow.parquet as pq
    started, cpu_started = time.monotonic(), time.process_time()
    root = Path(__file__).resolve().parent.parent
    if set(spec["code_sha256"]) != set(CODE):
        raise ValueError("exact unchanged helper and new module pins required")
    def check():
        if time.monotonic() - started >= 45 or time.process_time() - cpu_started >= 45:
            raise TimeoutError("structural audit finalization reserve")
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != config_sha256:
            raise ValueError("registration changed")
        for name, digest in spec["code_sha256"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
                raise ValueError("frozen code changed")
    check()
    for name in ("source_manifest", "raw_statistics", "appearance_projection", "source_policy"):
        if spec[name]["sha256"] != PINNED[name]:
            raise ValueError("original source binding changed")
    for name, digest in PRIOR.items():
        if spec[name]["sha256"] != digest:
            raise ValueError("prior successful diagnosis changed")
    parent = Path(spec["screen_output"])
    if (Path(spec["global_forecast_freeze"]["path"]) != parent / "forecast-freeze.json"
            or Path(spec["screen_query"]["path"]) != parent / "private/queries/2024.parquet"):
        raise ValueError("original frozen query path changed")
    validate_global_freeze(_json(_read(spec["global_forecast_freeze"])), spec["screen_query"]["sha256"])
    source = _json(_read(spec["source_manifest"]))["sources"]["stats_player_week_2024.parquet"]
    if any(source[k] != spec["raw_statistics"][k] for k in ("sha256", "bytes")):
        raise ValueError("source manifest mismatch")
    prior = _json(_read(spec["prior_context_diagnosis"]))
    terminal = _json(_read(spec["prior_context_supervisor"]))
    if (prior["state"] != "CONTEXT_METADATA_DIAGNOSIS_ONLY" or prior["diagnosis"]["projected_rows"] != 67
            or terminal["state"] != "CONTEXT_METADATA_DIAGNOSIS_ONLY" or prior["zeros_applied"] != 0):
        raise ValueError("successful original67-row context diagnosis required")
    storage = OperationalStorage(spec["cache"], _json(_read(spec["source_policy"])))
    refs = {spec[k]["path"]: spec[k]["sha256"] for k in INPUTS}
    resolved, entry = validate_owned_references(storage, refs)
    if any(resolved[spec[k]["path"]]["bytes"] != spec[k]["bytes"] for k in INPUTS):
        raise ValueError("owned input byte mismatch")
    output = Path(spec["output"])
    if output.exists() or output != Path("/workspace/website-methods-research/resumed/raw-orphan-context-v1-20261023"):
        raise ValueError("fresh fixed structural namespace required")
    storage.register_root(output)
    storage.atomic_json(output / "PREREQUISITE_CONSUMED.json", {
        "schema_version": VERSION, "config_sha256": config_sha256, "HTTP": 0,
        "at": datetime.now(timezone.utc).isoformat(), "automatic_retries": 0})
    state = "FAILED"
    try:
        check()
        raw = _fixed_table(spec["raw_statistics"]["path"], RAW, limit=200)
        offered = _fixed_table(spec["screen_query"]["path"], OFFERED, limit=200)
        app = _fixed_table(spec["appearance_projection"]["path"], APPEARANCE_COLUMNS, "nflverse_game_id", 10000)
        if raw.column_names != RAW or offered.column_names != OFFERED:
            raise ValueError("exact context-only projection required")
        buffer = io.BytesIO(); pq.write_table(raw, buffer, compression="zstd")
        body = buffer.getvalue(); projection_sha = hashlib.sha256(body).hexdigest()
        # Persist the complete bounded raw projection before identity partition;
        # a later contract failure cannot silently remove the orphan record.
        storage.write_bytes(output / "private/raw-context.parquet", body)
        if app.num_rows != 163:
            raise ValueError("complete163-play appearance projection required")
        witnesses = _witnesses(app.to_pandas(types_mapper=pd.ArrowDtype))
        records, union, aggregate = partition_context(raw.to_pylist(), offered.to_pylist(), witnesses,
            raw_projection_sha256=projection_sha)
        if (aggregate["missing_identity_raw_records"] != prior["diagnosis"]["null_counts"]["player_id"]
                or aggregate["raw_position_missing_records"] != prior["diagnosis"]["null_counts"]["position"]):
            raise ValueError("pinned prior context counts changed; no repair")
        storage.atomic_json(output / "private/raw-record-inventory.json", records)
        storage.atomic_json(output / "private/known-player-union.json", union)
        check()
        _, exit_receipt = validate_owned_references(storage, refs)
        _read(spec["source_policy"]); check()
        report = {"schema_version": VERSION, "state": "STRUCTURAL_QUARANTINE_ONLY", "coverage": aggregate,
            "config_sha256": config_sha256, "raw_projection_sha256": projection_sha,
            "input_sha256s": {k: spec[k]["sha256"] for k in INPUTS}, "HTTP": 0, "zeros_applied": 0,
            "source_policy_accepted_labels_forecasts_changed": False,
            "requested_agent_settings": spec["agent_settings"],
            "usage_before_result_write": {"wall_seconds": time.monotonic() - started,
                "CPU_seconds": time.process_time() - cpu_started}}
        storage.atomic_json(output / "aggregate.json", report)
        storage.atomic_json(output / "reference-validation.json", {"before_decode": entry, "after_decode": exit_receipt})
        state = "STRUCTURAL_QUARANTINE_ONLY"
        return report
    except BaseException as error:
        storage.atomic_json(output / "PREREQUISITE_FAILURE.json", {"state": "FAILED",
            "error_type": type(error).__name__, "reason": "STRUCTURAL_FAILURE_NO_RETRY",
            "HTTP": 0, "no_successful_subset": True, "zeros_applied": 0})
        raise
    finally:
        storage.atomic_json(output / "PREREQUISITE_FINISHED.json", {"state": state,
            "config_sha256": config_sha256, "HTTP": 0, "zeros_applied": 0,
            "wall_seconds_before_final_write": time.monotonic() - started,
            "CPU_seconds_before_final_write": time.process_time() - cpu_started})
