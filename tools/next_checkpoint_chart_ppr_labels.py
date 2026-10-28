"""Finite zero-fit chart-label reconstruction; persistence belongs to root CAS.

``build_result`` returns one compressed private capsule and safe aggregates.
It never writes private rows or changes the execution ledger/old studies.
"""
from __future__ import annotations

import base64
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import resource
import time

import pyarrow.parquet as pq

from nfl_lab.next_checkpoint_chart_ppr import (WEIGHTS, NFL_FIELDS, RETURN_COMPONENTS,
    SOURCE_VERSION, SCORING_VERSION, nflverse_components, label_observation)
from nfl_lab.ppr_outcomes import _participation

VERSION = "next-checkpoint-chart-ppr-label-runner-v1"
GENERATOR_SHA = "0ccd41c78355ee89c08929c79e81dac75b4d3f7b22d691cddd4f7f875acfac28"
QUALIFICATION = "nflverse-explicit-weekly-current-vintage-chart-v1"
PBP_COLUMNS = ["game_id", "play_id", "posteam", "defteam", "td_team", "td_player_id",
    "play_deleted", "play_type", "touchdown", "two_point_attempt", "fumble", "special",
    "pass_touchdown", "rush_touchdown", "return_touchdown", "kickoff_attempt", "punt_attempt",
    "field_goal_attempt", "punt_blocked", "own_kickoff_recovery_td", "interception",
    "fumble_recovery_1_player_id", "fumble_recovery_2_player_id", "lateral_recovery",
    "passer_player_id", "rusher_player_id", "receiver_player_id"]


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def stamp(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def authenticate(ref):
    path = Path(ref["path"])
    if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("canonical immutable source path required")
    before = stamp(path)
    if before[2] != ref["bytes"]:
        raise ValueError("source size differs before decode")
    body = path.read_bytes()
    if stamp(path) != before or sha(body) != ref["sha256"]:
        raise ValueError("source hash/stamp differs before decode")
    return body, before


def require_go(plan, go, plan_bytes):
    if (go.get("state") != "ROOT_AND_INDEPENDENT_GO" or go.get("plan_sha256") != sha(plan_bytes)
            or go.get("registered_by") != "/root" or go.get("independent_review") != "PASS"
            or go.get("predictive_fits") != 0):
        raise ValueError("exact root and independent source/label GO required")
    if plan["version"] != "next-checkpoint-chart-ppr-label-plan-v1":
        raise ValueError("exact bounded label plan required")
    if (plan.get("state") != "ROOT_AND_INDEPENDENT_SEALED" or plan.get("execution_authorized") is not True
            or (plan.get("root_registration") or {}).get("registered_by") != "/root"
            or plan.get("independent_review") != "PASS"
            or go.get("source_native_broad_zero_qualification") != "PASS"):
        raise ValueError("sealed authorized plan and reviewed source-native zero contract required")
    base = Path(__file__).resolve().parents[1]
    for relative in ["nfl_lab/next_checkpoint_chart_ppr.py", "tools/next_checkpoint_chart_ppr_labels.py"]:
        if go.get("code_sha256", {}).get(relative) != sha((base / relative).read_bytes()):
            raise ValueError("GO code binding differs: " + relative)
    caps = plan["resources"]
    if any(caps[k] != 0 for k in ("fits", "forecast_inference", "accuracy_comparisons", "HTTP", "retries")):
        raise ValueError("source-label lane requires zero fits/inference/accuracy/HTTP/retries")
    all_refs = plan["sources"] + plan["auxiliary_sources"]
    if len({r["path"] for r in all_refs}) != len(all_refs):
        raise ValueError("source references must be unique")
    if sum(r["bytes"] for r in all_refs) > caps["maximum_input_bytes"]:
        raise ValueError("source input budget exceeds plan")


def _finite_positive(value):
    from numbers import Real
    import math
    return (isinstance(value, Real) and not isinstance(value, bool)
            and math.isfinite(float(value)) and value > 0)


def participation(stats, pbp_actor_witness=False):
    # Preserve the stricter existing gp/snap/inactive contract when available.
    state, evidence = _participation({"stats": stats})
    if state != "unknown":
        return ("dnp" if state == "DNP" else state), evidence
    # Positive credited events establish playing; statistical row presence does
    # not. No snap fields or unqualified PFR source are read by this runner.
    fields = ["attempts", "completions", "carries", "targets", "receptions",
        "passing_tds", "rushing_tds", "receiving_tds", "passing_2pt_conversions",
        "rushing_2pt_conversions", "receiving_2pt_conversions", "kickoff_returns", "punt_returns"]
    witnessed = [k for k in fields if _finite_positive(stats.get(k))]
    if witnessed:
        return "played", "explicit_credited_official_event:" + ",".join(witnessed)
    if pbp_actor_witness:
        return "played", "matched_nondeleted_nonnullified_PBP_actor_event"
    return "unknown", None


def pbp_inventory(table):
    rows = table.to_pylist()
    if len({(r["game_id"], r["play_id"]) for r in rows}) != len(rows):
        raise ValueError("duplicate retained PBP game/play identity")
    by_scorer, actor_witnesses = defaultdict(list), set()
    for row in rows:
        if row["play_deleted"] != 0 or row["play_type"] in (None, "no_play") or row["two_point_attempt"] != 0:
            continue
        for field in ("passer_player_id", "rusher_player_id", "receiver_player_id"):
            if row[field] and row["posteam"]:
                actor_witnesses.add((row["game_id"], row["posteam"], row[field]))
        if row["touchdown"] == 1 and row["td_player_id"] and row["td_team"]:
            by_scorer[(row["game_id"], row["td_team"], row["td_player_id"])].append(row)
    return by_scorer, actor_witnesses


def rare_classification(stats, touchdowns):
    """Use broad-total reconciliation; never turn a positive superset into zero."""
    result, diagnostics = {}, []
    recovery = stats.get("fumble_recovery_tds")
    if _finite_positive(recovery):
        found = [e for e in touchdowns if e["fumble"] == 1
                 and e["pass_touchdown"] == 0 and e["rush_touchdown"] == 0]
        if len(found) != recovery:
            diagnostics.append("recovery_TD_inventory_does_not_reconcile")
        elif any(e["special"] not in (0, 1) or e["special"] == 1 for e in found):
            diagnostics.append("special_phase_recovery_TD_needs_exact_return_taxonomy")
        elif any(e["td_team"] not in (e["posteam"], e["defteam"]) for e in found):
            diagnostics.append("recovery_TD_possession_team_unknown")
        else:
            offense = [e for e in found if e["td_team"] == e["posteam"]]
            if any(e["td_player_id"] not in (e["fumble_recovery_1_player_id"], e["fumble_recovery_2_player_id"])
                   and e["lateral_recovery"] != 1 for e in offense):
                diagnostics.append("offensive_recovery_TD_final_credit_not_verified")
            else:
                result["off_fum_rec_td"] = {"value": len(offense), "qualification_id": "PBP2024-reconciled-recovery-v1"}
    special = stats.get("special_teams_tds")
    if _finite_positive(special):
        found = [e for e in touchdowns if e["special"] == 1 and e["fumble"] == 0]
        counts = dict.fromkeys(RETURN_COMPONENTS, 0)
        problem = len(found) != special
        for e in found:
            flags = [e[k] for k in ("kickoff_attempt", "punt_attempt", "field_goal_attempt")]
            if (any(v not in (0, 1) for v in flags) or sum(flags) > 1
                    or e["own_kickoff_recovery_td"] != 0):
                problem = True
            elif e["return_touchdown"] == 1 and sum(flags) == 1:
                if e["punt_attempt"] == 1 and e["punt_blocked"] != 0:
                    problem = True
                else:
                    counts[RETURN_COMPONENTS[flags.index(1)]] += 1
            elif e["rush_touchdown"] == 1 or e["pass_touchdown"] == 1 or e["interception"] == 1:
                pass  # Official nonreturn TD class; ordinary scorer handles its credit.
            else:
                problem = True
        if problem:
            diagnostics.append("special_TD_inventory_or_three_class_mapping_unqualified")
        else:
            result.update({k: {"value": v, "qualification_id": "PBP2024-reconciled-three-return-classes-v1"}
                           for k, v in counts.items()})
    return result, diagnostics


def build_result(plan_bytes, go):
    start_wall, start_cpu = time.monotonic(), time.process_time()
    plan = json.loads(plan_bytes)
    require_go(plan, go, plan_bytes)
    caps = plan["resources"]
    bodies, stamps, input_total = {}, {}, 0
    for ref in plan["sources"] + plan["auxiliary_sources"]:
        body, identity = authenticate(ref)
        bodies[ref["path"]], stamps[ref["path"]] = body, identity
        input_total += len(body)
    generator = next(r for r in plan["auxiliary_sources"] if r["kind"] == "generator_source")
    if generator["sha256"] != GENERATOR_SHA:
        raise ValueError("inspected generator evidence differs")
    pbp_ref = next(r for r in plan["sources"] if r["kind"] == "PBP")
    pf = pq.ParquetFile(io.BytesIO(bodies[pbp_ref["path"]]))
    if pf.metadata.num_rows > caps["maximum_PBP_source_rows"]:
        raise ValueError("PBP row envelope exceeded before decode")
    touchdowns, actors = pbp_inventory(pf.read(columns=PBP_COLUMNS))
    labels, aggregate, weekly_count = [], {}, 0
    zero_contract = {"version": "nflverse-chart-broad-zero-v1", "qualification_id": "generator-" + GENERATOR_SHA,
        "present_group_complete": True, "return_superset_contains_all_three_classes": True,
        "recovery_superset_includes_lateral_td_recipients": True}
    for ref in [r for r in plan["sources"] if r["kind"] == "weekly"]:
        pf = pq.ParquetFile(io.BytesIO(bodies[ref["path"]]))
        weekly_count += pf.metadata.num_rows
        if weekly_count > caps["maximum_weekly_source_rows"]:
            raise ValueError("weekly row envelope exceeded before decode")
        columns = ["player_id", "game_id", "team", "opponent_team", "position", "season", "week", "season_type",
            *NFL_FIELDS.values(), "fumble_recovery_tds", "special_teams_tds", "attempts", "completions", "carries",
            "targets", "punt_returns", "kickoff_returns"]
        filters = [("season", "==", ref["season"]), ("season_type", "==", "REG"),
                   ("position", "in", ["QB", "RB", "FB", "WR", "TE"])]
        if ref["season"] == 2026:
            filters.append(("week", "<=", 6))
        # Apply the authorized row predicate inside Arrow before materializing
        # numerical rows; later 2026 weeks are never exposed then discarded.
        rows = pq.read_table(io.BytesIO(bodies[ref["path"]]), columns=list(dict.fromkeys(columns)),
                             filters=filters).to_pylist()
        totals, missing, states, classifications, component_status = Counter(), Counter(), Counter(), Counter(), defaultdict(Counter)
        seen = set()
        for stats in rows:
            if (stats["season"] != ref["season"] or stats["season_type"] != "REG"
                    or stats["position"] not in {"QB", "RB", "FB", "WR", "TE"}
                    or (stats["season"] == 2026 and stats["week"] > 6)):
                continue
            identity = {k: stats[k] for k in ("player_id", "game_id", "team", "season", "week", "season_type")}
            identity["opponent"] = stats["opponent_team"]
            key = stats["game_id"], stats["team"], stats["player_id"]
            if key in seen:
                raise ValueError("duplicate planned source player/game/team")
            seen.add(key)
            rare, diagnostics = rare_classification(stats, touchdowns.get(key, [])) if ref["season"] == 2024 else ({}, [])
            bundle = nflverse_components(stats, source_ref={"sha256": ref["sha256"], "qualification_id": QUALIFICATION},
                                        broad_zero_contract=zero_contract, event_components=rare)
            state, witness = participation(stats, key in actors if ref["season"] == 2024 else False)
            label = label_observation(bundle, identity=identity, participation=state, participation_evidence=witness)
            label["rare_classification_diagnostics"] = diagnostics
            labels.append(label)
            totals["planned_rows"] += 1
            totals["numeric_chart_labels"] += label["value"] is not None
            totals["rare_positive_planned_rows"] += bool(_finite_positive(stats["fumble_recovery_tds"]) or _finite_positive(stats["special_teams_tds"]))
            totals["rare_positive_numeric_labels"] += bool(label["value"] is not None and (_finite_positive(stats["fumble_recovery_tds"]) or _finite_positive(stats["special_teams_tds"])))
            states[label["state"]] += 1
            missing.update(label["missing_components"])
            classifications.update(diagnostics)
            for k, evidence in bundle["coverage"].items():
                component_status[k][evidence["status"]] += 1
        aggregate[str(ref["season"])] = {**dict(totals), "states": dict(states), "missing_components": dict(missing),
            "classification_diagnostics": dict(classifications), "component_coverage": {k:dict(v) for k,v in component_status.items()}}
    # Preserve the actual corrupt binding without decoding or overwriting it.
    bad = next(r for r in plan["auxiliary_sources"] if r["kind"] == "quarantine_original")
    receipt = next(r for r in plan["auxiliary_sources"] if r["kind"] == "quarantine_receipt")
    original = bodies[bad["path"]]
    original_receipt = json.loads(bodies[receipt["path"]])
    quarantine = {"path": bad["path"], "actual_bytes": len(original), "actual_sha256": sha(original),
        "receipt": original_receipt, "decoded": False, "original_bytes_base64": base64.b64encode(original).decode()}
    if sha(original) == original_receipt["sha256"]:
        raise ValueError("quarantine original changed; preserve and stop")
    private = {"version": VERSION, "target": SCORING_VERSION, "source_adapter": SOURCE_VERSION,
               "plan_sha256": sha(plan_bytes), "labels": labels, "quarantine": quarantine}
    payload = gzip.compress(encoded(private), mtime=0)
    if len(payload) > caps["private_label_bytes"]:
        raise ValueError("complete label/quarantine capsule exceeds retained budget; no truncation")
    for path, before in stamps.items():
        if stamp(Path(path)) != before:
            raise ValueError("source changed during reconstruction")
    usage = {"CPU_seconds": time.process_time()-start_cpu, "wall_seconds": time.monotonic()-start_wall,
             "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    if usage["CPU_seconds"] > caps["CPU_seconds"] or usage["wall_seconds"] > caps["wall_seconds"] or usage["peak_RSS_bytes"] > caps["RSS_bytes"]:
        raise ValueError("finite resource budget exceeded; preserve failure")
    summary = {"version": VERSION, "state": "LABELS_RECONSTRUCTED_NOT_PREDICTIVELY_EVALUATED", "target": SCORING_VERSION,
        "plan_sha256": sha(plan_bytes), "seasons": aggregate, "source_rows": weekly_count,
        "PBP_source_rows": 49492, "authenticated_input_bytes": input_total,
        "quarantine": {k:v for k,v in quarantine.items() if k != "original_bytes_base64"},
        "private_capsule_bytes": len(payload), "private_capsule_sha256": sha(payload), "resources": usage,
        "fits": 0, "forecasts": 0, "accuracy_comparisons": 0, "HTTP": 0,
        "evaluation_population_admissible": False,
        "population_limit": "source-listed player-games only; rare-positive unsupported rows retained; no event-free-only predictive evaluation",
        "vintage": "current-vintage source reconstruction, not original publication or prospective evidence"}
    if len(encoded(summary)) > caps["aggregate_metadata_bytes"]:
        raise ValueError("safe aggregate metadata budget exceeded")
    return payload, summary
