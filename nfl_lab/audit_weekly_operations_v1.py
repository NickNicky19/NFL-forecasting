"""Closed metadata composition for the existing weekly writer.

This module never acquires a source, loads a model, reads outcome bodies, posts,
dispatches or publishes. The current hosted parent authenticates each input and
supplies the live grading callback. Repeated refreshes retain their original
primary assignment instead of creating additional football observations.
"""
from __future__ import annotations

from copy import deepcopy
import csv
from datetime import datetime, timezone
import io
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import pandas as pd

from . import audit_weekly_archive_v1 as archive, audit_weekly_epoch_v1 as epoch
from . import audit_weekly_grade_v1 as grade, audit_weekly_resume_v1 as resume
from . import gha_private_checkpoint as cp, private_draft_store as store
from . import weekly_current_query as query, data, state
from .owned_reference_batch import validate_owned_references

VERSION = "audit-weekly-operations-v1"
CONTEXT_SCHEMA = "audit-weekly-recurring-v1-context"
CONTEXT_KEYS = {"schema_version", "controller_context", "previous_capture"}
CONTEXT_V2 = "audit-weekly-recurring-v2-context"
FILES = ("nfl_lab/audit_weekly_operations_v1.py", "tests/test_audit_weekly_operations_v1.py")
STREAM = "weekly-corrected-primary-player-game-v1"


class OperationsError(ValueError):
    pass


def require(value, code):
    if not value:
        raise OperationsError(code)


def context(value):
    require(type(value) is dict and value.get("schema_version") in {CONTEXT_SCHEMA,CONTEXT_V2}
        and set(value)==(CONTEXT_KEYS if value["schema_version"]==CONTEXT_SCHEMA
            else CONTEXT_KEYS|{"previous_checkpoint"}), "CLOSED_RECURRING_CONTEXT_REQUIRED")
    previous = value["previous_capture"]
    require(type(previous) is dict and set(previous) == {"feed_sha256", "receipt_sha256"}
        and all(type(v) is str and store.HASH.fullmatch(v) for v in previous.values()),
        "EXACT_PRIOR_SUCCESSFUL_CAPTURE_LOCATOR_REQUIRED")
    require(value["controller_context"] is None or type(value["controller_context"]) is dict,
        "EXPLICIT_OWNER_OR_SEALED_CONTROLLER_CONTEXT")
    if value["schema_version"]==CONTEXT_V2:
        checkpoint=value["previous_checkpoint"]
        require(checkpoint is None or type(checkpoint) is dict and set(checkpoint)=={"sha256"}
            and type(checkpoint["sha256"]) is str and store.HASH.fullmatch(checkpoint["sha256"]),
            "EXACT_REGISTERED_PREVIOUS_GRADING_SIDECAR_HASH")
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
