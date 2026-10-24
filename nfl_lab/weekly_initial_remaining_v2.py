"""Explicit midnight recovery metadata; shared source/model pipeline unchanged.

The consumed fifteen-Z registration is evidence, never a reusable authority.
Only a new root registration, fresh source claim and fresh finite fit budget may
authorize this operational stream. Importing this module grants none of them.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

from . import weekly_generic_producer as generic, weekly_initial_remaining_v1 as previous
from .state import utc

VERSION = "weekly-initial-remaining-v2"
REGISTRATION = VERSION + "-registration"
REGISTRATION_ID = "2026-REG-W07-remaining-20261025T00Z-recovery-v2"
CUTOFF = "2026-10-25T00:00:00Z"
REGISTRATION_PATH = "config/weekly-initial-remaining-v2-registration.json"
BUILD_REGISTRATION = "genuine-hosted-fixed-build-registration-v2"
BUILD_REGISTRATION_ID = "initial-remaining-2026W7-20261025T00Z-operational-build-v2"
FULL_FIRST, REMAINING_FIRST = previous.FULL_FIRST, previous.REMAINING_FIRST
ELAPSED, REMAINING, EXPECTED = previous.ELAPSED, previous.REMAINING, previous.EXPECTED
PREDECESSOR = dict(registration_id=previous.REGISTRATION_ID,
    registration_sha256="9fdae2c34732602c81155e7b6db0488043886ca45259f8c3560aa6787125ca72",
    disposition="EXPIRED_CONSUMED_FAILED_RETAINED", run_id="40103844901",
    source_sha="752a03b82be2ba73cf4798da2682c7c33568e0b8", source_claim_asset_id=672511497)
FIELDS = previous.FIELDS | {"predecessor", "operational_stream", "scientific_qualification"}
BUILD_FIELDS = {"schema_version", "registration_id", "approved", "repository", "source_sha", "config_sha256",
    "registered_at_utc", "input_cutoff_utc", "training_cutoff_utc", "scope", "maximum_new_fits",
    "old_artifact_reproduction", "scientific_qualification", "initial_registration", "initial_registration_sha256"}
validate_fresh_initial_metadata = previous.validate_fresh_initial_metadata


def validate_registration(registration, *, now):
    r = registration
    generic.require(type(r) is dict and set(r) == FIELDS, "closed recovery registration schema required")
    generic.require(r["schema_version"] == REGISTRATION and r["registration_id"] == REGISTRATION_ID
        and r["state"] == "FROZEN_ROOT_REGISTERED" and type(r["maximum_uses"]) is int and r["maximum_uses"] == 1,
        "one-time root-registered recovery required")
    generic.require(type(r["season"]) is int and type(r["week"]) is int
        and (r["season"], r["week"], r["season_type"], r["slate_id"], r["slate_kind"])
        == (2026, 7, "REG", REGISTRATION_ID, "INITIAL_REMAINING_RECOVERY_ONE_TIME"), "exact recovery REG W7 identity required")
    generic.require(r["remaining_game_ids"] == list(REMAINING) and r["elapsed_game_ids"] == list(ELAPSED)
        and type(r["remaining_game_count"]) is int and type(r["elapsed_game_count"]) is int
        and (r["remaining_game_count"], r["elapsed_game_count"]) == (13, 1), "literal thirteen remaining/one elapsed games required")
    generic.require(utc(r["full_week_first_kickoff_utc"]) == utc(FULL_FIRST)
        and utc(r["first_remaining_kickoff_utc"]) == utc(REMAINING_FIRST) and r["input_cutoff_utc"] == CUTOFF,
        "original full-week first and new midnight horizon must remain exact")
    generic.require(r["build_kind"] == "GENUINE_HOSTED_FIXED_BUILD_V1"
        and r["startup_policy_sha256"] == "0ee3eccf4f0e9ed85ee46c6ba4f6df404459fb4f3cabba469bf6dffd9ee2456c"
        and r["operational_stream"] == "weekly-adaptive-release-v1" and r["scientific_qualification"] is False,
        "unchanged shared build and provisional operational stream required")
    generic.require(r["predecessor"] == PREDECESSOR, "consumed predecessor evidence must remain exact")
    generic.require(r["registered_at_utc"] is not None
        and utc(previous.CUTOFF) <= utc(r["registered_at_utc"]) <= now < utc(CUTOFF)
        and now < utc(REMAINING_FIRST) - timedelta(hours=6),
        "actual recovery registration/choice must follow expired predecessor and precede midnight and remaining-slate deadline")
    return r


def validate_build_registration(registration, *, source_sha, config_sha256, initial_sha256, now):
    """Fresh fixed18 authorization; prior reservations never become this budget."""
    from .state import digest
    r = registration
    generic.require(type(config_sha256) is str and re.fullmatch('[a-f0-9]{64}', config_sha256)
        and type(initial_sha256) is str and re.fullmatch('[a-f0-9]{64}', initial_sha256)
        and type(source_sha) is str and re.fullmatch('[a-f0-9]{40}', source_sha), "exact recovery source/config/registration hashes required")
    generic.require(type(r) is dict and set(r) == BUILD_FIELDS
        and r["schema_version"] == BUILD_REGISTRATION and r["registration_id"] == BUILD_REGISTRATION_ID
        and r["approved"] is True and r["repository"] == "NickNicky19/NFL-forecasting"
        and r["source_sha"] == source_sha and r["config_sha256"] == config_sha256
        and r["input_cutoff_utc"] == CUTOFF and r["training_cutoff_utc"] == "2026-09-01T00:00:00Z"
        and r["scope"] == "SOURCE_AND_TRAIN_FIXED18_ONLY" and type(r["maximum_new_fits"]) is int
        and r["maximum_new_fits"] == 18 and r["old_artifact_reproduction"] is False
        and r["scientific_qualification"] is False, "exact separately registered recovery fixed18 budget required")
    initial = validate_registration(r["initial_registration"], now=now)
    generic.require(digest(initial) == r["initial_registration_sha256"] == initial_sha256
        and utc(initial["registered_at_utc"]) <= utc(r["registered_at_utc"]) <= now < utc(CUTOFF),
        "exact new initial recovery registration must precede fresh build inputs")
    return r


def prepare_initial_slate(schedule, registration, registration_ref, *, now):
    r = validate_registration(registration, now=now)
    rows = [s for s in schedule if s["season"] == 2026 and s["week"] == 7 and s["game_type"] == "REG"]
    generic.require(len(rows) == 14 and {s["game_id"] for s in rows} == set(REMAINING) | set(ELAPSED),
        "full original fourteen-game schedule required")
    future = [s for s in rows if utc(s["kickoff_utc"]) > now]
    generic.require(sorted(s["game_id"] for s in rows if utc(s["kickoff_utc"]) <= now) == list(ELAPSED)
        and sorted(s["game_id"] for s in future) == list(REMAINING)
        and min(utc(s["kickoff_utc"]) for s in rows) == utc(FULL_FIRST)
        and min(utc(s["kickoff_utc"]) for s in future) == utc(REMAINING_FIRST), "honest elapsed/remaining kickoff census differs")
    result = generic.prepare_slate(rows, season=2026, week=7, game_cutoffs={g:CUTOFF for g in REMAINING}, now=now)
    result.update(slate_id=REGISTRATION_ID, scheduled_first_kickoff_utc=utc(REMAINING_FIRST).isoformat(),
        weekly_deadline_utc=(utc(REMAINING_FIRST)-timedelta(hours=6)).isoformat(),
        slate_contract=dict(schema_version=VERSION, registration=registration_ref, registered_at_utc=r["registered_at_utc"],
            kind=r["slate_kind"], full_week_first_kickoff_utc=utc(FULL_FIRST).isoformat(),
            full_week_deadline_utc=(utc(FULL_FIRST)-timedelta(hours=6)).isoformat(), elapsed_game_ids=list(ELAPSED),
            remaining_game_ids=list(REMAINING), maximum_uses=1, build_kind=r["build_kind"],
            predecessor=dict(PREDECESSOR), operational_stream=r["operational_stream"], scientific_qualification=False))
    return result


def validate_plan(plan, *, now):
    from tools.weekly_current_query import pin
    generic.require(plan.get("initial_adapter", {}).get("schema_version") == VERSION, "explicit recovery adapter plan required")
    ref = plan["initial_adapter"]["registration"]
    pin(ref)
    registration = json.loads(Path(ref["path"]).read_text())
    validate_registration(registration, now=now)
    generic.require(plan["startup_policy"]["sha256"] == registration["startup_policy_sha256"]
        and plan["slate"]["slate_id"] == REGISTRATION_ID
        and plan["slate"]["game_cutoffs"] == {g:CUTOFF for g in REMAINING}
        and plan["slate"].get("slate_contract", {}).get("registration") == ref
        and plan["slate"]["slate_contract"]["schema_version"] == VERSION,
        "exact registration/policy/midnight recovery plan binding required")
    generic.require({"nfl_lab/initial_horizon.py", "nfl_lab/weekly_initial_remaining_v2.py", "tools/weekly_initial_remaining_v2.py",
        "nfl_lab/weekly_initial_remaining_v1.py"} <= set(plan["code_pins"]), "recovery adapter, shared metadata and dispatch code must be sealed")
    return registration


class InitialRemainingBackend(generic.ProductionBackend):
    """Metadata override only; inherited run owns all numerical execution."""
    def consume_registration(self, registration, registration_ref):
        root = Path(self.plan["cache"]) / VERSION / "registrations"
        path = root / (REGISTRATION_ID + ".json")
        with self.store.transaction():
            generic.require(not path.exists(), "one-time recovery registration already consumed; no new namespace retry")
            self.store.register_root(root)
            self.store.atomic_json(path, dict(schema_version=VERSION+"-consumed", registration=registration_ref,
                predecessor=dict(PREDECESSOR), output_root=self.plan["output_root"], actual_consumed_at=self.clock().isoformat(),
                maximum_uses=1, no_automatic_retry=True, persist_journal_with_private_runtime=True))

    def derive_slate(self, schedule):
        registration = validate_plan(self.plan, now=self.clock())
        ref = self.plan["initial_adapter"]["registration"]
        derived = prepare_initial_slate(schedule, registration, ref, now=self.clock())
        generic.require(derived == self.plan["slate"], "sealed recovery metadata differs from actual schedule")
        wanted = {"schedules.csv.receipt.json", "roster_weekly_2026.parquet.receipt.json", "stats_player_week_2026.parquet.receipt.json"}
        receipts = {Path(r["path"]).name:self.read(r) for r in self.plan["source_bindings"] if Path(r["path"]).name in wanted}
        slots = getattr(self, "slot_inventory", None)
        self.checkpoint("INITIAL_METADATA")
        metadata = slots["original_metadata"] if slots is not None else [self.read(r) for r in self.plan["artifacts"]]
        validate_fresh_initial_metadata(registration, metadata, receipts, now=self.clock(), slot_inventory=slots)
        self.checkpoint("INITIAL_CONSUME")
        self.consume_registration(registration, ref)
        return derived
