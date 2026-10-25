"""Closed metadata composition for the existing weekly writer.

This module never acquires a source, loads a model, reads outcome bodies, posts,
dispatches or publishes. The current hosted parent authenticates each input and
supplies the live grading callback. Repeated refreshes retain their original
primary assignment instead of creating additional football observations.
"""
from __future__ import annotations

from copy import deepcopy
import csv
from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from . import audit_weekly_archive_v1 as archive, audit_weekly_epoch_v1 as epoch
from . import audit_weekly_grade_v1 as grade, audit_weekly_resume_v1 as resume
from . import gha_private_checkpoint as cp, private_draft_store as store
from . import state
from .owned_reference_batch import validate_owned_references

VERSION = "audit-weekly-operations-v1"
CONTEXT_SCHEMA = "audit-weekly-recurring-v1-context"
CONTEXT_KEYS = {"schema_version", "controller_context", "previous_capture"}
CONTEXT_V2 = "audit-weekly-recurring-v2-context"
CONTEXT_V3 = "audit-weekly-recurring-v3-context"
FILES = ("nfl_lab/audit_weekly_operations_v1.py", "tests/test_audit_weekly_operations_v1.py")
STREAM = "weekly-corrected-primary-player-game-v1"
PLAN_KEYS = {"schema_version", "kind", "reason", "epoch_sha256", "canonical_choice_sha256",
    "target_choice_sha256", "season", "week", "planned_at", "history_sha256", "future_game_ids",
    "capture_allowed", "publication_allowed", "current_values_used", "fits"}


class OperationsError(ValueError):
    pass


def require(value, code):
    if not value:
        raise OperationsError(code)


def context(value):
    require(type(value) is dict and value.get("schema_version") in {CONTEXT_SCHEMA,CONTEXT_V2,CONTEXT_V3}
        and set(value)==(CONTEXT_KEYS if value["schema_version"]==CONTEXT_SCHEMA
            else CONTEXT_KEYS|{"previous_checkpoint"}|({"plan"} if value["schema_version"]==CONTEXT_V3 else set())),
        "CLOSED_RECURRING_CONTEXT_REQUIRED")
    previous = value["previous_capture"]
    require(type(previous) is dict and set(previous) == {"feed_sha256", "receipt_sha256"}
        and all(type(v) is str and store.HASH.fullmatch(v) for v in previous.values()),
        "EXACT_PRIOR_SUCCESSFUL_CAPTURE_LOCATOR_REQUIRED")
    require(value["controller_context"] is None or type(value["controller_context"]) is dict,
        "EXPLICIT_OWNER_OR_SEALED_CONTROLLER_CONTEXT")
    if value["schema_version"] in {CONTEXT_V2,CONTEXT_V3}:
        checkpoint=value["previous_checkpoint"]
        require(checkpoint is None or type(checkpoint) is dict and set(checkpoint)=={"sha256"}
            and type(checkpoint["sha256"]) is str and store.HASH.fullmatch(checkpoint["sha256"]),
            "EXACT_REGISTERED_PREVIOUS_GRADING_SIDECAR_HASH")
    if value["schema_version"] == CONTEXT_V3:
        plan = value["plan"]
        require(type(plan) is dict and set(plan) == {"kind", "season", "week"}
            and plan["kind"] in {"GRADE_ONLY", "FUTURE_CAPABLE"}
            and type(plan["season"]) is int and 2019 <= plan["season"] <= 2100
            and type(plan["week"]) is int and 1 <= plan["week"] <= 18,
            "CLOSED_ROOT_RECURRING_PLAN_REQUIRED")
    return deepcopy(value)


def roles_from_manifests(storage, restored_ref, *, authenticate):
    """Only qualified manifest metadata; the caller authenticates restoration."""
    require(callable(authenticate) and authenticate(dict(schema_version=VERSION+"-authentication-request",
        kind="QUALIFIED_CURRENT_MODEL_MANIFEST_METADATA", binding=deepcopy(restored_ref))) is True,
        "LIVE_CURRENT_MODEL_RESTORATION_AUTHENTICATION_REQUIRED")
    restored = archive.read_owned(storage, restored_ref)
    require(type(restored) is dict and set(restored) == resume.MODEL_KEYS
        and restored["state"] == "CROSS_RUN_EFFECTIVE18_RESTORED_AND_REPLAYED_PRIVATE"
        and restored["model_pairs"] == 18 and restored["fits"] == 0
        and restored["current_loader_replay"] is restored["model_artifact_durability"] is True,
        "QUALIFIED_CURRENT_EFFECTIVE18_METADATA_REQUIRED")
    refs = restored["models"]
    require(type(refs) is list and len(refs) == len(cp.JOBS), "EXACT18_MANIFEST_ROLE_CENSUS")
    validate_owned_references(storage, {ref["path"]:ref["sha256"] for ref in refs})
    result = {}
    for ref, (target, family, method) in zip(refs, cp.JOBS):
        manifest = cp.strict_json(cp.read_ref(ref, 256 << 10))
        require((manifest["category"]["target"], manifest["family"], manifest["method_id"])
            == (target, family, method), "EXACT_RETAINED_MANIFEST_ROLE_IDENTITY")
        category = manifest["category"]
        roles = {k:deepcopy(category[k]) for k in ("modeled_roles", "primary_roles")}
        require(all(type(v) is list and v and len(set(v)) == len(v)
            and all(type(r) is str and r in {"QB", "RB", "FB", "WR", "TE"} for r in v)
            for v in roles.values()) and set(roles["primary_roles"]) <= set(roles["modeled_roles"]),
            "ORIGINAL_MODELED_AND_PRIMARY_ROLES_REQUIRED")
        require(target not in result or result[target] == roles, "CANDIDATES_MUST_SHARE_REGISTERED_CATEGORY_ROLES")
        result[target] = roles
    require(set(result) == set(cp.TARGETS), "ALL_ELEVEN_ROLE_CONTRACTS_REQUIRED")
    return result


def calendar(raw, *, season, week):
    """Full calendar identities only; no score/workload/result field is used."""
    import pandas as pd
    from . import data, weekly_current_query as query
    require(type(raw) is bytes and 0 < len(raw) <= 8 << 20
        and type(season) is int and type(week) is int and 1 <= week <= 18,
        "BOUNDED_FULL_CURRENT_WEEK_CALENDAR_REQUIRED")
    zone = ZoneInfo("America/New_York")
    result = []
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    require(reader.fieldnames is not None and {"season", "week", "game_type", "game_id", "gameday", "gametime",
        "espn", "home_team", "away_team"} <= set(reader.fieldnames), "COMPLETE_CALENDAR_METADATA_COLUMNS_REQUIRED")
    for row in reader:
        if int(row["season"]) != season or int(row["week"]) != week or row["game_type"] != "REG":
            continue
        try:
            naive = datetime.fromisoformat(row["gameday"] + "T" + row["gametime"])
            require(naive.tzinfo is None, "LOCAL_SCHEDULE_CLOCK_REQUIRED")
            a, b = naive.replace(tzinfo=zone, fold=0), naive.replace(tzinfo=zone, fold=1)
            require(a.utcoffset() == b.utcoffset()
                and a.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == naive,
                "UNKNOWN_AMBIGUOUS_OR_NONEXISTENT_KICKOFF_FORBIDDEN")
            kickoff = a.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            raise OperationsError("QUALIFIED_KICKOFF_CLOCK_REQUIRED") from None
        website_id = query._sleeper(row["espn"])
        home, away = data._team(pd.Series([row["home_team"], row["away_team"]], dtype=str)).tolist()
        require(type(row["game_id"]) is str and row["game_id"]
            and website_id is not None and re.fullmatch(r"[1-9][0-9]*", website_id)
            and type(home) is str and type(away) is str and home != away,
            "EXACT_CANONICAL_GAME_TEAMS_AND_ESPN_ID_REQUIRED")
        result.append(dict(season=season, week=week, game_type="REG", game_id=row["game_id"],
            website_game_id=website_id, kickoff_utc=kickoff, home=home, away=away))
    require(0 < len(result) <= 32 and len({r["game_id"] for r in result}) == len(result)
        and len({r["website_game_id"] for r in result}) == len(result),
        "COMPLETE_UNIQUE_FULL_WEEK_CALENDAR_REQUIRED")
    return sorted(result, key=lambda r:(r["kickoff_utc"], r["game_id"]))


def primary_population(registered, choice, roles, *, capture_id, authenticate,
        previous=None, clock=state.now_utc):
    """Register before values; an already assigned game stays with its capture."""
    at = clock()
    require(type(registered) is epoch.RegisteredEpoch and type(choice) is epoch.EpochChoice
        and type(capture_id) is str and store.HASH.fullmatch(capture_id), "CURRENT_TYPED_PRIMARY_POPULATION_REQUIRED")
    choice.verify(registered, at)
    require(set(roles) == set(cp.TARGETS), "EXACT_REGISTERED_ROLE_CATALOG_REQUIRED")
    old = {}
    if previous is not None:
        require(type(previous) in {grade.Snapshot, grade.DurableHistory}, "TYPED_PRIOR_GRADING_STATE_REQUIRED")
        previous.verify()
        require(previous.document["epoch_sha256"] == registered.epoch.sha256,
            "NO_PRIMARY_ASSIGNMENT_ACROSS_DIFFERENT_EPOCHS")
        for capture in previous.document["captures"]:
            pop = capture["population"]
            require(pop["role_catalog_sha256"] == state.digest(roles) and pop["stream_id"] == STREAM,
                "ORIGINAL_PRIMARY_ROLE_STREAM_MUST_REMAIN_FIXED")
            for gid, assigned in pop["assignments"].items():
                require(gid not in old or old[gid] == assigned, "NO_CONFLICTING_PRIMARY_CAPTURE_ASSIGNMENTS")
                old[gid] = assigned
    document = grade.population_template(registered, choice)
    document.update(state="ROOT_REGISTERED", stream_id=STREAM, registered_at=state.utc(at).isoformat(),
        role_catalog_sha256=state.digest(roles), assignments={gid:old.get(gid, capture_id)
            for gid in document["assignments"]})
    new = [gid for gid, assigned in document["assignments"].items() if assigned == capture_id]
    require(not new or len(new) == len(document["assignments"]),
        "MIXED_PRIMARY_AND_REFRESH_SCOPE_REQUIRES_EXPLICIT_RECONCILIATION")
    population = grade.bind_population(document, registered, choice, authenticate=authenticate, at=at)
    return population, dict(schema_version=VERSION+"-assignment", capture_id=capture_id,
        state="FIRST_PREVALUE_PRIMARY_CAPTURE" if new else "REFRESH_NOT_ANOTHER_PRIMARY_OBSERVATION",
        primary_game_ids=sorted(new), preserved_assignment_game_ids=sorted(set(document["assignments"])-set(new)),
        population_sha256=population.sha256, current_values_used=False, fits=0)


def recurring_plan(registered, original, full_schedule, *, authenticate, durable=None,
        cutoff_lead_seconds, relocated_replays=(), clock=state.now_utc):
    """Choose a closed execution path from authenticated calendar metadata.

    A grade-only plan carries the original choice unchanged and creates no
    issuance population. A later-week choice requires actual durable resolved
    history; an absent history never falls back to the legacy research anchor.
    The caller separately authenticates/restores original capture bytes.
    """
    at = state.utc(clock())
    require(type(registered) is epoch.RegisteredEpoch and type(original) is epoch.EpochChoice,
        "TYPED_RECURRING_EPOCH_AND_CANONICAL_CHOICE_REQUIRED")
    original.verify(registered, at)
    resume._calendar_fields(full_schedule)
    weeks = {(r["season"], r["week"]) for r in full_schedule}
    require(len(weeks) == 1 and type(cutoff_lead_seconds) is int and 0 < cutoff_lead_seconds <= 86400,
        "EXACT_ONE_REG_WEEK_AND_REGISTERED_CUTOFF_LEAD")
    season, week = next(iter(weeks)); old = original.document["slate"]
    require(season == old["season"] and old["week"] <= week <= 18, "CURRENT_OR_LATER_SAME_SEASON_REG_WEEK")
    grade._authenticate(authenticate, "RECURRING_EXECUTION_PLAN_BEFORE_VALUES",
        dict(original_choice_sha256=original.sha256, full_schedule=full_schedule,
            cutoff_lead_seconds=cutoff_lead_seconds), at)
    choice = original; history_sha = None
    if week == old["week"]:
        identity = state.digest(sorted((r["game_id"], state.utc(r["kickoff_utc"]).isoformat()) for r in full_schedule))
        require(identity == old["schedule_identity_sha256"] and len(full_schedule) == old["scheduled_games"],
            "CHANGED_OR_INCOMPLETE_FULL_CALENDAR_REJECTED")
        future = {r["game_id"]: r for r in full_schedule if state.utc(r["kickoff_utc"]) > at}
        require(set(future) <= set(old["game_cutoffs"]), "ALL_FUTURE_GAMES_MUST_HAVE_ORIGINAL_CUTOFFS")
        available = bool(future) and all(at < state.utc(old["game_cutoffs"][g]) < state.utc(r["kickoff_utc"])
            for g, r in future.items())
        reason = "ORIGINAL_SAME_WEEK_CAPTURE_WINDOW" if available else "FROZEN_CAPTURE_WINDOW_ELAPSED_GRADE_ORIGINALS_ONLY"
        if available:
            resume._calendar(full_schedule, original, at)  # Unchanged future-only validation.
    else:
        require(type(durable) is grade.DurableHistory, "DURABLE_CAUSAL_HISTORY_REQUIRED_NO_FALLBACK")
        durable.verify()
        require(state.utc(durable.document["actual_completed_at"]) < at
            and all(state.utc(t["known_by_at"]) < at for k in ("known_versions", "known_weeks") for t in durable.document[k].values()),
            "HISTORY_MUST_BE_DURABLE_BEFORE_ACTUAL_DECISION")
        require(durable.document["epoch_sha256"] == registered.epoch.sha256
            and any(w["season"] == season and registered.epoch.origin["slate"]["week"] <= w["week"] < week
                for w in durable.document["weeks"]),
            "COMPLETE_PRIOR_CURRENT_EPOCH_WEEK_REQUIRED")
        from . import weekly_generic_producer as generic
        cutoffs = {r["game_id"]:(state.utc(r["kickoff_utc"])-timedelta(seconds=cutoff_lead_seconds)).isoformat()
            for r in full_schedule}
        slate = generic.prepare_slate(full_schedule, season=season, week=week, game_cutoffs=cutoffs, now=at)
        require(at < state.utc(slate["weekly_deadline_utc"]) and slate["elapsed_games"] == 0,
            "NEW_WEEK_DECISION_DEADLINE_ALREADY_ELAPSED")
        choice = grade.select_next(registered, durable, slate, original, full_schedule=full_schedule,
            authenticate=authenticate, relocated_replays=relocated_replays, clock=lambda:at)
        history_sha = durable.sha256; available = True; future = cutoffs
        reason = "NEW_WEEK_P2_FROM_PRIOR_DURABLE_RESOLVED_HISTORY"
    plan = dict(schema_version=VERSION+"-execution-plan", kind="FUTURE_CAPTURE" if available else "GRADE_ONLY",
        reason=reason, epoch_sha256=registered.epoch.sha256, canonical_choice_sha256=original.sha256,
        target_choice_sha256=choice.sha256, season=season, week=week, planned_at=at.isoformat(),
        history_sha256=history_sha, future_game_ids=sorted(future) if available else [],
        capture_allowed=bool(available), publication_allowed=bool(available), current_values_used=False, fits=0)
    require(set(plan) == PLAN_KEYS, "CLOSED_RECURRING_EXECUTION_PLAN")
    return choice, plan
