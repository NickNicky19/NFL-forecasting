"""Metadata-only same-week recovery; no API, source, model or outcome reads.

The parent LIVE-authenticates the unchanged retained result and fresh effective18
receipt before any owned metadata is opened. Calendar authority is separate.
The frozen epoch implementation closes EpochChoice's top-level fields, so the
new capture_scope is an external owned record committing both choice hashes.
Only slate.game_cutoffs changes in the ordinary typed EpochChoice. A refresh
with the same active cutoffs preserves that choice SHA; the separate sidecar
records its new clock without creating another primary grading observation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re
import resource
import time

from . import audit_weekly_archive_v1 as archive, audit_weekly_retained_v1 as retained
from . import audit_weekly_epoch_v1 as epoch, audit_weekly_runtime_v1 as runtime
from . import audit_count_retained_v1 as models, gha_private_checkpoint as cp
from . import private_draft_store as store, weekly_durable_acceptance as acceptance
from .operational_storage import OperationalStorage
from .state import digest, utc

VERSION = "audit-weekly-resume-v1"
LIMITS = dict(wall_seconds=180, CPU_seconds=120, RSS_bytes=512 << 20,
    global_bytes=512 << 20, metadata_bytes=16 << 20, metadata_files=20,
    games=32, model_pairs=18, fits=0, model_decodes=0, outcome_decodes=0,
    forecast_decodes=0, source_acquisitions=0, HTTP_calls=0, retries=0)
CONTEXT_ROLES = {"epoch", "epoch_registration", "original_choice", "origin_witness",
    "original_slate", "original_catalog", "original_policy"}
CANONICAL_ROLE = "context/canonical_weekly_choice.json"
SCOPE_ROLE = "context/capture_scope.json"
RETAINED_KEYS = {"schema_version", "state", "created_at_utc", "registration_sha256", "current_root_go_sha256", "current",
    "original_archive", "original_reader_handoff", "original_index", "original_reader_witness", "historical_producer_proof",
    "historical_reader_witness", "historical_job_evidence", "current_restore_proofs", "original_exporter_proof_scope",
    "aliases", "metadata", "r0", "previous_state", "previous_state_aliases", "original_physical_bindings", "validation",
    "files_sha256", "HTTP_calls", "RSS_peak_bytes", "fits", "model_decodes", "source_acquisitions", "protected_outcome_reads",
    "remote_writes", "model_replay_performed", "public_export_authorized", "public_release", "successful_forecast"}
MODEL_KEYS = {"schema_version", "state", "origin", "current", "current_go_sha256", "registration_sha256", "models", "model_pairs", "files",
    "proofs", "index_sha256", "group_sha256", "relocation_catalog", "fits", "source_feed_acquisitions", "remote_writes",
    "protected_outcome_reads", "current_loader_replay", "model_artifact_durability", "successful_forecast",
    "scientifically_qualified", "public_release", "catalog_epoch_ready", "weekly_choice_restored", "actual_completed_at"}
SCOPE_KEYS = {"schema_version", "original_weekly_choice_sha256", "prior_capture_choice_sha256", "scoped_choice_sha256",
    "weekly_payload_sha256", "epoch_sha256", "actual_scoped_at", "active_game_ids", "elapsed_game_ids",
    "schedule_identity_sha256", "no_reselection", "no_cutoff_extension", "current_values_used", "fits"}
_LIVE = object()


class ResumeError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise ResumeError(code)


def now():
    return datetime.now(timezone.utc)


def pins():
    root = Path(__file__).resolve().parents[1]
    names = set(epoch.PIN_PATHS) | {"nfl_lab/audit_weekly_resume_v1.py", "tools/audit_weekly_resume_v1.py",
        "nfl_lab/audit_weekly_retained_v1.py", "nfl_lab/audit_weekly_runtime_v1.py", "nfl_lab/audit_weekly_archive_v1.py",
        "nfl_lab/audit_weekly_origin_v1.py", "nfl_lab/audit_count_retained_v1.py", "nfl_lab/gha_private_checkpoint.py",
        "nfl_lab/private_draft_store.py", "nfl_lab/owner_bootstrap_bundle.py", "nfl_lab/weekly_durable_acceptance.py",
        "nfl_lab/operational_storage.py", "nfl_lab/owned_reference_batch.py"}
    return {name: store.sha(store.read_local(root / name, 2 << 20)) for name in sorted(names)}


def _auth(callback, kind, document, at):
    require(callable(callback), "LIVE_PARENT_AUTHENTICATOR_REQUIRED")
    request = dict(schema_version=VERSION + "-authentication", kind=kind,
        inputs_sha256=digest(document), at=utc(at).isoformat())
    require(callback(deepcopy(request)) is True, "LIVE_PARENT_AUTHENTICATION_REJECTED")
    return request


class _Metadata:
    def __init__(self, storage):
        self.storage = storage
        self.started, self.cpu = time.monotonic(), time.process_time()
        self.bytes, self.files = 0, 0

    def guard(self):
        require(time.monotonic() - self.started <= LIMITS["wall_seconds"]
            and time.process_time() - self.cpu <= LIMITS["CPU_seconds"]
            and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= LIMITS["RSS_bytes"],
            "FINITE_METADATA_RESUME_ENVELOPE")

    def read(self, reference, cap=2 << 20, *, raw=False):
        self.guard()
        require(type(reference) is dict and set(reference) == {"path", "bytes", "sha256"}
            and type(reference["bytes"]) is int and 0 < reference["bytes"] <= cap,
            "BOUNDED_OWNED_METADATA_REFERENCE")
        self.files += 1
        self.bytes += reference["bytes"]
        require(self.files <= LIMITS["metadata_files"] and self.bytes <= LIMITS["metadata_bytes"],
            "FINITE_METADATA_ONLY_FILE_AND_BYTE_CENSUS")
        result = runtime.read_owned(self.storage, reference, cap, raw=raw)
        self.guard()
        return result


def _proof(proof, identity, at, binding_sha256=None):
    require(type(proof) is dict and set(proof) == store.BASE_PROOF_FIELDS | store.PHASE_FIELDS["restore"]
        and proof["schema_version"] == "weekly-private-proof-v2.1" and proof["phase"] == "restore"
        and proof["operation"] == "restore" and proof["config_sha256"] == store.config_sha()
        and set(proof["job"]) == store.JOB_FIELDS and proof["job"]["run_authenticated"] is True
        and proof["job"]["workflow_sha"] == proof["source_sha"] and proof["job"]["event_name"] == "workflow_dispatch"
        and acceptance.restored_identity(proof) == identity
        and proof["exact_readback"] is proof["separate_process"] is proof["draft_before_after"] is True
        and type(proof["HTTP_calls"]) is int and 10 <= proof["HTTP_calls"] <= store.MAX_CALLS
        and type(proof["transfer_bytes"]) is int and 0 < proof["transfer_bytes"] <= store.TRANSFER_CAP
        and type(proof["bytes"]) is int and 0 < proof["bytes"] <= store.ASSET_CAP
        and all(store.HASH.fullmatch(str(proof[k])) for k in ("payload_sha256", "binding_sha256"))
        and (binding_sha256 is None or proof["binding_sha256"] == binding_sha256)
        and utc(proof["started_at_utc"]) <= utc(proof["created_at_utc"]) <= utc(at),
        "EXACT_PARENT_AUTHENTICATED_NATIVE_RECOVERY_METADATA")


def _capture(value, reader, at):
    require(type(value) is dict and set(value) == RETAINED_KEYS and value["schema_version"] == retained.VERSION + "-result"
        and value["state"] == "PRIVATE_PRIOR_CAPTURE_RESTORED"
        and value["validation"].get("qualified_selected") is value["validation"].get("replay_ready") is True
        and all(type(value[k]) is int and value[k] == 0 for k in
            ("fits", "model_decodes", "source_acquisitions", "protected_outcome_reads", "remote_writes"))
        and value["model_replay_performed"] is value["public_export_authorized"] is value["public_release"] is value["successful_forecast"] is False,
        "UNCHANGED_COMPLETE_RETAINED_RESULT_REQUIRED")
    handoff = value["original_archive"]
    archive.safe_handoff(handoff)
    require(handoff["archive_state"] == "COMPLETE_CAPTURE" and value["files_sha256"] == handoff["files_sha256"],
        "FAILED_CAPTURE_CANNOT_RESUME")
    current = acceptance.identity(value["current"])
    require(current["run_id"] != handoff["run_id"]
        and utc(value["created_at_utc"]) <= utc(at), "CURRENT_RETAINED_IDENTITY_AND_HONEST_RECOVERY_CLOCK")
    producer=acceptance.identity(handoff["producer"])
    original_reader=acceptance.identity(value["original_reader_handoff"]["restorer"])
    require(original_reader["run_id"]==producer["run_id"]==handoff["run_id"]
        and original_reader["source_sha"]==producer["source_sha"]==handoff["source_sha"]
        and current["api_job_id"] not in {producer["api_job_id"],original_reader["api_job_id"],
            value["historical_job_evidence"].get("consume",{}).get("api_job_id")}
        and current["process_identity"] not in {producer["process_identity"],original_reader["process_identity"]},
        "FRESH_RETAINED_JOB_AND_PROCESS")
    raw = reader.read(value["original_index"], archive.INDEX_CAP, raw=True)
    require(store.sha(raw) == handoff["index_descriptor"]["entry"]["payload"]["sha256"], "EXACT_RETAINED_INDEX_BYTES")
    index = archive.check_index(archive.unpack(raw, archive.INDEX_PLAIN_CAP), handoff)
    originals = {f["logical_path"]: f for f in index["files"]}
    aliases = value["aliases"]
    require(set(aliases) == set(originals) and all((aliases[n]["bytes"], aliases[n]["sha256"]) == (f["bytes"], f["sha256"])
        for n, f in originals.items()) and index["census"]["physical_origins"] == value["original_physical_bindings"],
        "EXACT_RETAINED_ALIAS_CENSUS_WITHOUT_BODY_READS")
    raw_witness = reader.read(value["original_reader_witness"], archive.WITNESS_CAP, raw=True)
    old = value["original_reader_handoff"]
    require(set(old) == {"schema_version", "archive", "restorer", "witness_descriptor"}
        and old["schema_version"] == archive.VERSION + "-reader-handoff" and old["archive"] == handoff,
        "UNMODIFIED_ORIGINAL_READER_HANDOFF")
    entry = cp.descriptor_meta(old["witness_descriptor"], archive.WITNESS_CAP)
    witness = archive.unpack(raw_witness, archive.WITNESS_CAP)
    require(store.sha(raw_witness) == entry["payload"]["sha256"] and witness == value["historical_reader_witness"]
        and set(witness) == retained.WITNESS_KEYS and witness["index_sha256"] == store.sha(raw)
        and witness["files_sha256"] == handoff["files_sha256"] and witness["validation"] == value["validation"]
        and witness["restorer"] == old["restorer"] and witness["archive_state"] == "COMPLETE_CAPTURE"
        and witness["producer_proof_sha256"] == digest(index["producer_proof"])
        and value["historical_producer_proof"] == index["producer_proof"], "ORIGINAL_READER_WITNESS_AND_PRODUCER_METADATA")
    binding_sha = digest(handoff["runtime_binding"])
    expected = [(len(raw), store.sha(raw)), (len(raw_witness), store.sha(raw_witness))]
    expected += [(g["bytes"], g["sha256"]) for g in index["groups"]]
    proofs = value["current_restore_proofs"]
    require(type(proofs) is list and [(p["bytes"], p["payload_sha256"]) for p in proofs] == expected,
        "CURRENT_INDEX_WITNESS_AND_ALL_GROUP_RECOVERY_PROOFS")
    for proof in proofs:
        _proof(proof, current, value["created_at_utc"], binding_sha)
    return index


def _models(value, reader, current, at):
    require(type(value) is dict and set(value) == MODEL_KEYS and value["schema_version"] == models.VERSION + "-restore"
        and value["state"] == "CROSS_RUN_EFFECTIVE18_RESTORED_AND_REPLAYED_PRIVATE"
        and value["model_pairs"] == len(value["models"]) == 18 and value["files"] == 38
        and value["current_loader_replay"] is value["model_artifact_durability"] is True
        and all(type(value[k]) is int and value[k] == 0 for k in ("fits", "source_feed_acquisitions", "protected_outcome_reads", "remote_writes"))
        and all(value[k] is False for k in ("successful_forecast", "scientifically_qualified", "public_release", "catalog_epoch_ready", "weekly_choice_restored"))
        and all(value["current"][k] == current[k] for k in ("repository", "run_id", "run_attempt", "source_sha", "workflow_ref", "job_id", "api_job_id"))
        and utc(value["actual_completed_at"]) <= utc(at), "FRESH_CURRENT_EFFECTIVE18_MODELS_ONLY_RESULT")
    identity = acceptance.identity(value["current"])
    require(type(value["proofs"]) is list and 1 <= len(value["proofs"]) <= 9, "FRESH_EFFECTIVE18_NATIVE_PROOFS_REQUIRED")
    for proof in value["proofs"]:
        _proof(proof, identity, value["actual_completed_at"])
    aliases = reader.read(value["relocation_catalog"], 512 << 10)
    return runtime.relocated_catalog(value, aliases)


def _calendar_fields(schedule):
    fields = {"season", "week", "game_type", "game_id", "kickoff_utc"}
    require(type(schedule) is list and 0 < len(schedule) <= LIMITS["games"]
        and all(type(r) is dict and set(r) == fields and type(r["season"]) is int and type(r["week"]) is int
            and r["game_type"] == "REG" and type(r["kickoff_utc"]) is str and 0 < len(r["kickoff_utc"]) <= 40
            and type(r["game_id"]) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", r["game_id"]) for r in schedule)
        and len({r["game_id"] for r in schedule}) == len(schedule), "FULL_CLOSED_SAME_WEEK_CALENDAR_REQUIRED")


def _calendar(schedule, original, at):
    _calendar_fields(schedule)
    slate = original.document["slate"]
    require(all((r["season"], r["week"]) == (slate["season"], slate["week"]) for r in schedule),
        "FULL_CLOSED_SAME_WEEK_CALENDAR_REQUIRED")
    identity = digest(sorted((r["game_id"], utc(r["kickoff_utc"]).isoformat()) for r in schedule))
    require(identity == slate["schedule_identity_sha256"] and len(schedule) == slate["scheduled_games"],
        "CHANGED_OR_INCOMPLETE_FULL_CALENDAR_REJECTED")
    future = {r["game_id"]: r for r in schedule if utc(r["kickoff_utc"]) > utc(at)}
    require(bool(future), "NO_FUTURE_GAMES_SAME_WEEK")
    require(set(future) <= set(slate["game_cutoffs"]), "ALL_FUTURE_GAMES_MUST_HAVE_ORIGINAL_CUTOFFS")
    cutoffs = {g: slate["game_cutoffs"][g] for g in sorted(future)}
    require(all(utc(at) < utc(cutoffs[g]) < utc(r["kickoff_utc"]) for g, r in future.items()),
        "EXPIRED_FUTURE_CUTOFF_NO_EXTENSION_OR_COVERAGE_CUT")
    return identity, cutoffs, sorted(set(r["game_id"] for r in schedule) - set(future))


class Resumed:
    def __init__(self, registered, original, choice, replay, inputs, document, binding, key):
        require(key is _LIVE, "LIVE_RESUME_REQUIRED")
        self.registered, self.original_choice, self.choice = registered, original, choice
        self.replay, self.inputs, self.document, self.binding = map(deepcopy, (replay, inputs, document, binding))
        self.sha256 = digest(document)
        self._bindings_sha256 = digest(dict(inputs=inputs, binding=binding, replay=replay))

    def verify(self, at):
        self.original_choice.verify(self.registered, utc(at))
        self.choice.verify(self.registered, utc(at))
        require(digest(self.document) == self.sha256
            and digest(dict(inputs=self.inputs, binding=self.binding, replay=self.replay)) == self._bindings_sha256
            and self.original_choice.sha256 == self.document["capture_scope"]["original_weekly_choice_sha256"]
            and digest(self.original_choice.document["choice"]) == self.document["capture_scope"]["weekly_payload_sha256"]
            and self.choice.sha256 == self.document["capture_scope"]["scoped_choice_sha256"], "LIVE_RESUME_CHANGED")

    def __reduce__(self):
        raise ResumeError("RESUME_JSON_IS_NOT_LIVE_AUTHORITY")


def resume(retained_result, retained_ref, full_schedule, *, storage, output,
        original_weekly_choice_sha256, authenticate, authenticate_calendar, clock=now):
    """Return sealed typed metadata for unchanged Runtime; acquisition is later.

    authenticate(request) must LIVE-bind the request digest to the exact genuine
    retained result/current proofs AND fresh owned effective18 retained_ref.
    authenticate_calendar(request) must LIVE-bind the full calendar digest to
    actual current calendar provenance, never a saved true flag. Neither callback
    performs provider/model/outcome reads on this adapter's behalf.
    original_weekly_choice_sha256 is the parent's separately registered original
    full EpochChoice commitment, not a hash newly chosen from a daily projection.
    """
    require(isinstance(storage, OperationalStorage), "EXISTING_OPERATIONAL_STORAGE_REQUIRED")
    at = utc(clock())
    _calendar_fields(full_schedule)  # Bound calendar-only scalars before hashing or private I/O.
    require(type(retained_result) is dict and len(store.canonical(retained_result)) <= 2 << 20,
        "BOUNDED_RETAINED_METADATA_RESULT")
    require(type(original_weekly_choice_sha256) is str and store.HASH.fullmatch(original_weekly_choice_sha256),
        "REGISTERED_CANONICAL_WEEKLY_CHOICE_HASH_REQUIRED")
    authority = _auth(authenticate, "GENUINE_RETAINED_CAPTURE_AND_FRESH_EFFECTIVE18", dict(
        retained_result=retained_result, retained_ref=retained_ref, original_weekly_choice_sha256=original_weekly_choice_sha256,
        helper_sha256=pins(), source_policy_sha256=cp.POLICY_SHA), at)
    reader = _Metadata(storage)
    _capture(retained_result, reader, at)
    aliases = retained_result["aliases"]
    require({"context/" + role + ".json" for role in CONTEXT_ROLES} | {"runtime/WEEKLY_CHOICE.json", "prepared/choice.json"} <= set(aliases),
        "COMPLETE_AUTHENTICATED_EPOCH_CONTEXT_REQUIRED")
    # No artifact manifest/model/forecast/source-body alias is opened here.
    restored_models = reader.read(retained_ref)
    replay = _models(restored_models, reader, retained_result["current"], at)
    context = {role: aliases["context/" + role + ".json"] for role in CONTEXT_ROLES}
    documents = {role: reader.read(ref, 4 << 20 if role == "origin_witness" else epoch.CAP,
        raw=role == "original_choice") for role, ref in sorted(context.items())}
    history_binding = deepcopy(documents["epoch"]["original"]["history_binding"])
    corrected = epoch.restore_epoch(documents["epoch"], documents["original_choice"], documents["origin_witness"],
        documents["original_slate"], documents["original_catalog"], documents["original_policy"], history_binding=history_binding, now=at)
    registered = epoch.bind_registration(corrected, documents["epoch_registration"], now=at)
    prior_raw = reader.read(aliases["runtime/WEEKLY_CHOICE.json"], epoch.CAP, raw=True)
    require((aliases["prepared/choice.json"]["bytes"], aliases["prepared/choice.json"]["sha256"]) == (len(prior_raw), store.sha(prior_raw)),
        "EXACT_RUNTIME_AND_PREPARED_FULL_WEEKLY_CHOICE")
    prior_doc = cp.strict_json(prior_raw)
    prior = epoch.EpochChoice(prior_doc, digest(prior_doc))
    prior.verify(registered, at)
    require((CANONICAL_ROLE in aliases) == (SCOPE_ROLE in aliases), "CANONICAL_WEEKLY_ANCHOR_AND_SCOPE_MUST_TRAVEL_TOGETHER")
    canonical_raw = prior_raw
    if CANONICAL_ROLE in aliases:
        canonical_raw = reader.read(aliases[CANONICAL_ROLE], epoch.CAP, raw=True)
        old_scope = reader.read(aliases[SCOPE_ROLE], 16 << 10)
        require(set(old_scope) == SCOPE_KEYS and old_scope["schema_version"] == VERSION + "-capture-scope"
            and old_scope["scoped_choice_sha256"] == prior.sha256 and old_scope["original_weekly_choice_sha256"] == digest(cp.strict_json(canonical_raw))
            and utc(old_scope["actual_scoped_at"]) <= utc(retained_result["created_at_utc"]), "EXACT_ORIGINAL_CANONICAL_WEEKLY_ANCHOR")
    original_doc = cp.strict_json(canonical_raw)
    original = epoch.EpochChoice(original_doc, digest(original_doc))
    original.verify(registered, at)
    require(original.sha256 == original_weekly_choice_sha256, "REGISTERED_CANONICAL_WEEKLY_CHOICE_REQUIRED")
    expected_prior = deepcopy(original_doc)
    expected_prior["slate"]["game_cutoffs"] = prior_doc["slate"]["game_cutoffs"]
    require("capture_scope" not in original_doc["slate"], "ONLY_EXTERNAL_CAPTURE_SCOPE_METADATA_ALLOWED")
    if CANONICAL_ROLE in aliases:
        require(old_scope["epoch_sha256"] == corrected.sha256 and old_scope["weekly_payload_sha256"] == digest(original_doc["choice"])
            and old_scope["active_game_ids"] == sorted(prior_doc["slate"]["game_cutoffs"])
            and old_scope["schedule_identity_sha256"] == original_doc["slate"]["schedule_identity_sha256"]
            and utc(original_doc["choice"]["actual_frozen_at"]) <= utc(old_scope["actual_scoped_at"])
            and old_scope["no_reselection"] is old_scope["no_cutoff_extension"] is True
            and old_scope["current_values_used"] is False and old_scope["fits"] == 0, "EXACT_PREVIOUS_CAPTURE_SCOPE")
    require(expected_prior == prior_doc and set(prior_doc["slate"]["game_cutoffs"]) <= set(original_doc["slate"]["game_cutoffs"])
        and all(v == original_doc["slate"]["game_cutoffs"][g] for g, v in prior_doc["slate"]["game_cutoffs"].items()),
        "PRIOR_CAPTURE_CANNOT_REWRITE_FROZEN_WEEKLY_METADATA")
    calendar_request = _auth(authenticate_calendar, "CURRENT_COMPLETE_SAME_WEEK_CALENDAR", dict(
        full_schedule=full_schedule, original_weekly_choice_sha256=original.sha256, epoch_sha256=corrected.sha256,
        current_root_go_sha256=retained_result["current_root_go_sha256"]), at)
    identity, cutoffs, elapsed = _calendar(full_schedule, original, at)
    scoped_doc = deepcopy(original_doc)
    scoped_doc["slate"]["game_cutoffs"] = cutoffs
    choice = epoch.EpochChoice(scoped_doc, digest(scoped_doc))
    choice.verify(registered, at)
    versions = epoch.selected_versions(registered, choice, relocated_replays=(replay,), now=at)
    old_versions = epoch.selected_versions(registered, original, relocated_replays=(replay,), now=at)
    require(versions["rows"] == old_versions["rows"] and choice.document["choice"] == original.document["choice"],
        "CAPTURE_SCOPE_MUST_PRESERVE_ALL_WEEKLY_SELECTIONS_AND_PROCEDURES")
    scope = dict(schema_version=VERSION + "-capture-scope", original_weekly_choice_sha256=original.sha256,
        prior_capture_choice_sha256=prior.sha256, scoped_choice_sha256=choice.sha256, weekly_payload_sha256=digest(original_doc["choice"]),
        epoch_sha256=corrected.sha256, actual_scoped_at=at.isoformat(), active_game_ids=sorted(cutoffs), elapsed_game_ids=elapsed,
        schedule_identity_sha256=identity, no_reselection=True, no_cutoff_extension=True, current_values_used=False, fits=0)
    reader.guard()
    require(utc(clock()) < min(map(utc, cutoffs.values())), "CUTOFF_EXPIRED_DURING_METADATA_RESUME")
    output = archive.fresh(storage, output)
    storage.write_bytes(output / "CANONICAL_WEEKLY_CHOICE.json", canonical_raw)
    canonical_ref = cp.binding(output / "CANONICAL_WEEKLY_CHOICE.json")
    choice_ref = archive.write(storage, output / "SCOPED_CHOICE.json", scoped_doc)
    scope_ref = archive.write(storage, output / "CAPTURE_SCOPE.json", scope)
    version_ref = archive.write(storage, output / "SELECTED_VERSION_CATALOG.json", versions)
    inputs = {key: context[key] for key in ("epoch", "epoch_registration", "original_choice", "original_slate", "original_catalog", "original_policy")}
    inputs.update(original_completion=context["origin_witness"], choice=choice_ref, retained_restore=deepcopy(retained_ref))
    completed = utc(clock())
    require(at <= completed < min(map(utc, cutoffs.values())), "CUTOFF_EXPIRED_BEFORE_RESUME_COMPLETION")
    document = dict(schema_version=VERSION + "-result", state="SAME_WEEK_CAPTURE_METADATA_READY", actual_completed_at=completed.isoformat(),
        epoch_sha256=corrected.sha256, original_registration_completion_sha256=registered.completion_sha256,
        capture_scope=scope, capture_scope_binding=scope_ref, inputs=inputs, history_binding=history_binding,
        canonical_weekly_choice=canonical_ref, selected_versions=version_ref,
        archive_context=dict(canonical_weekly_choice=canonical_ref, capture_scope=scope_ref),
        source_retained_result_sha256=digest(retained_result), current_model_restore_sha256=retained_ref["sha256"],
        authority=authority, calendar_authority=calendar_request, metadata_files_read=reader.files, metadata_bytes_read=reader.bytes,
        grade_population_registered=False, prospective_grade_evidence=False, grade_population_authority_required=True,
        existing_primary_assignments_unchanged=True,
        source_refresh_required=True, capture_authorized=False, metadata_remote_durability_qualified=False,
        successful_forecast=False, public_release=False, fits=0, HTTP_calls=0)
    binding = archive.write(storage, output / "RESUMED.json", document)
    reader.guard()
    return Resumed(registered, original, choice, replay, inputs, document, binding, _LIVE)
