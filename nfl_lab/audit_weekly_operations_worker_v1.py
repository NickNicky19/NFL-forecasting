"""Native phase-1 operations bridge for the existing serialized hosted writer.

Only operations-prepare is implemented. Receipt discovery and qualified native
retention/replay happen UPSTREAM; this worker accepts their authenticated owned
metadata references. Root v2 history is independently recovered through live
native GETs before population reconciliation. No calendar download, model
restore/inference, new labels, grading, dispatch or publication occurs here.
Same-week scope uses unchanged resume/calendar/role/population APIs. An explicit
Root v3 plan can instead grade original preassigned captures or select a later
REG week from independently recovered durable current-epoch history.

The hosted child_context and operations_authority modules are parent-owned.
They must accept recurring ROOTs and this phase before genuine execution. No
JSON flags, CLI callback names or saved proof can substitute for those gates.
Every worker obtains a NEW current proof; a numerical parent's old 180s proof
is not reused. Bootstrap V2 is copied/bound by the parent, not this module.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import resource
import signal
import time

VERSION = "audit-weekly-operations-worker-v1"
ROOT = Path(__file__).resolve().parents[1]
PHASE = "operations-prepare"
OUTPUT_NAME = "operations-prepared"
PENDING_PHASES = ("operations-grade-write", "operations-grade-read")
FILES = ("nfl_lab/audit_weekly_operations_worker_v1.py", "tools/audit_weekly_operations_worker_v1.py",
         "tests/test_audit_weekly_operations_worker_v1.py")
REQUEST_KEYS = {"schema_version", "phase", "code_pins", "limits", "cache", "state_root", "output", "inputs"}
INPUT_KEYS = {"retained_result", "retained_models", "calendar", "canonical_weekly_choice_sha256", "capture_id", "previous_grade_snapshot"}
HISTORY_INPUT_KEYS = {"sidecar", "public_receipt"}
HISTORY_ARCHIVE_ROLES = ("ops_previous_checkpoint_sidecar", "ops_previous_public_receipt")
LIMITS = dict(wall_seconds=180, CPU_seconds=120, address_space_bytes=512 << 20, RSS_bytes=512 << 20,
    global_bytes=512 << 20, request_bytes=512 << 10, metadata_bytes=16 << 20, calendar_bytes=8 << 20,
    manifest_bytes=512 << 10, fits=0, model_decodes=0, source_acquisitions=0, label_acquisitions=0, retries=0)
CALENDAR_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
_KEY = object()


class WorkerError(ValueError):
    """Fixed public-safe codes only."""


def require(ok, code):
    if not ok:
        raise WorkerError(code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _hash(value):
    return type(value) is str and re.fullmatch("[a-f0-9]{64}", value) is not None


def native_envelope():
    for kind, maximum in ((resource.RLIMIT_CPU, 120), (resource.RLIMIT_AS, 512 << 20)):
        soft, hard = resource.getrlimit(kind)
        require(type(soft) is int and type(hard) is int and 0 < soft <= hard <= maximum,
                "OPERATIONS_NATIVE_CPU_AS_GUARD_REQUIRED")
    remaining, interval = signal.getitimer(signal.ITIMER_REAL)
    require(signal.getsignal(signal.SIGALRM) == signal.SIG_DFL and 0 < remaining <= 180 and interval == 0,
            "OPERATIONS_NATIVE_WALL_GUARD_REQUIRED")


def _reference(value, base, cap):
    require(type(value) is dict and set(value) == {"path", "bytes", "sha256"}
            and type(value["path"]) is str and Path(value["path"]).is_absolute()
            and ".." not in Path(value["path"]).parts and Path(value["path"]).is_relative_to(base)
            and type(value["bytes"]) is int and 0 < value["bytes"] <= cap and _hash(value["sha256"]),
            "OPERATIONS_CURRENT_OWNED_METADATA_REFERENCE_REQUIRED")


def validate_request(request, phase):
    require(phase == PHASE, "OPERATIONS_PHASE_NOT_IMPLEMENTED")
    require(type(request) is dict and set(request) == REQUEST_KEYS and request["schema_version"] == VERSION + "-request"
            and request["phase"] == phase and _canonical(request["limits"]) == _canonical(LIMITS)
            and type(request["inputs"]) is dict and set(request["inputs"]) == INPUT_KEYS,
            "CLOSED_OPERATIONS_PREPARE_REQUEST_REQUIRED")
    paths = [Path(request[key]) for key in ("cache", "state_root", "output")]
    require(all(p.is_absolute() and ".." not in p.parts for p in paths)
            and paths[0].name == "cache" and paths[1] == paths[0].parent / "state"
            and paths[2] == paths[0].parent / OUTPUT_NAME, "OPERATIONS_EXACT_PHASE_PATHS_REQUIRED")
    base = paths[0].parent
    inputs = request["inputs"]
    _reference(inputs["retained_result"], base, 4 << 20)
    _reference(inputs["retained_models"], base, 4 << 20)
    require(type(inputs["calendar"]) is dict and set(inputs["calendar"]) == {"body", "receipt"},
            "OWNED_FULL_CALENDAR_AND_NATIVE_RECEIPT_REQUIRED")
    _reference(inputs["calendar"]["body"], base, LIMITS["calendar_bytes"])
    _reference(inputs["calendar"]["receipt"], base, 64 << 10)
    require(_hash(inputs["canonical_weekly_choice_sha256"]) and _hash(inputs["capture_id"]),
            "REGISTERED_CANONICAL_CHOICE_AND_CAPTURE_IDS_REQUIRED")
    if inputs["previous_grade_snapshot"] is not None:
        history = inputs["previous_grade_snapshot"]
        require(type(history) is dict and set(history) == HISTORY_INPUT_KEYS,
                "LIVE_HISTORY_SIDECAR_AND_PUBLIC_RECEIPT_PAIR_REQUIRED")
        for ref in history.values():
            _reference(ref, base, 64 << 10)
    return request


class Authenticated:
    """One process-bound current ROOT/request/job, never serializable authority."""
    def __init__(self, request, authority, job, go, env, client, proof, actor_binding, key):
        require(key is _KEY, "LIVE_OPERATIONS_GUARD_REQUIRED")
        self.request, self.authority, self.job, self.go = map(deepcopy, (request, authority, job, go))
        self.client, self.proof, self.actor_binding = client, proof, actor_binding
        self.env = env
        self.wall, self.cpu = time.monotonic(), time.process_time()
        self.root_sha256 = authority["owner_root_go_sha256"]
        self._sha = _digest(dict(request=request, authority=authority, job=job, go=go))

    def verify(self):
        native_envelope()
        require(self._sha == _digest(dict(request=self.request, authority=self.authority, job=self.job, go=self.go))
                and time.monotonic() - self.wall <= 180 and time.process_time() - self.cpu <= 120
                and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= 512 << 20,
                "OPERATIONS_CONTEXT_CHANGED_OR_NATIVE_BUDGET_EXCEEDED")
        from . import state, audit_weekly_operations_authority_v1 as authority
        require(state.utc(self.authority["issued_at_utc"]) <= state.now_utc() < state.utc(self.authority["expires_at_utc"]),
                "OPERATIONS_CURRENT_AUTHORITY_EXPIRED")
        # The central module owns process/proof binding and current actor rules.
        binding = getattr(self.client, "_audit_operations_current", None)
        require(type(binding) is authority.CurrentClient, "LIVE_RECURRING_CLIENT_BINDING_REQUIRED")
        binding.verify(self.client)
        authority.authorize_client_actor(self.client, self.actual_run)
        return self

    def __reduce__(self):
        raise WorkerError("OPERATIONS_JSON_IS_NOT_LIVE_AUTHORITY")


def authenticate_child(args, env, *, phase, transport=None):
    """Shared actual native ROOT/API guard; caller validates its payload schema.

    Only exact parent-declared hosted.OPERATIONS_PHASES are eligible. The owned
    control request is read by hosted.child_context; none of its payload refs
    are opened here. Callers pass their own literal phase, never a CLI callback.
    """
    native_envelope()
    from . import audit_weekly_hosted_v1 as hosted, audit_weekly_operations_v1 as operations
    from . import audit_weekly_operations_authority_v1 as authority, private_draft_store as store
    require(type(phase) is str and phase in hosted.OPERATIONS_PHASES and args.phase == phase,
            "EXACT_HOSTED_OPERATIONS_PHASE_REQUIRED")
    root_bytes = env.get("AUDIT_WEEKLY_ROOT_GO_JSON", "").encode()
    require(0 < len(root_bytes) <= 60 << 10 and store.sha(root_bytes) == env.get("AUDIT_WEEKLY_ROOT_GO_SHA256"),
            "OPERATIONS_EXACT_ROOT_PREIMAGE_REQUIRED")
    go = hosted.cp.strict_json(root_bytes)
    require(store.canonical(go) == root_bytes, "OPERATIONS_CANONICAL_ROOT_REQUIRED")
    # Reject invalid attestation flags before bootstrap HTTP or client creation.
    raw_native = env.get("AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON", "").encode()
    require(0 < len(raw_native) <= 16 << 10 and store.sha(raw_native) == env.get("AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256"),
            "OPERATIONS_EXACT_NATIVE_AUTHORITY_PREIMAGE_REQUIRED")
    early = hosted.cp.strict_json(raw_native)
    require(type(early) is dict and set(early) == hosted.NATIVE_KEYS and raw_native == store.canonical(early)
            and early["schema_version"] == hosted.VERSION + "-native-authority" and early["phase"] == phase
            and early["actual_actions_api_authenticated"] is early["owner_root_checked"] is True
            and early["public_release"] is False and type(early["fits"]) is int and early["fits"] == 0
            and early["owner_root_go_sha256"] == store.sha(root_bytes), "CLOSED_OPERATIONS_NATIVE_AUTHORITY_REQUIRED")
    hosted.validate_root(go, now=hosted.now_utc())
    operations.context(go["effective_epoch"])
    require(go["operation"] == "RECURRING_CAPTURE", "EXPLICIT_RECURRING_ROOT_REQUIRED")
    proof = authority.current(env, root_bytes, ROOT)
    authority._verify(proof, env, root_bytes)
    request, native, job, go = hosted.child_context(args, env, phase, operations_proof=proof)
    operations.context(go["effective_epoch"])
    require(go["operation"] == "RECURRING_CAPTURE", "EXPLICIT_RECURRING_ROOT_REQUIRED")
    require(request["code_pins"] == hosted.pins() and request["code_pins"] == go["code_pins"]
            and all(name in request["code_pins"] for name in FILES), "CURRENT_SOURCE_INVENTORY_INCLUDES_OPERATIONS_WORKER")
    require(store.canonical(go) == root_bytes and store.sha(root_bytes) == native["owner_root_go_sha256"],
            "OPERATIONS_EXACT_ROOT_PREIMAGE_REQUIRED")
    # The authenticated hosted parent already created/registered this journal.
    journal = Path(request["cache"]).parent / "journal"
    client = store.Client(env.get("GITHUB_TOKEN"), env["GITHUB_RUN_ID"], journal=journal,
        source_sha=env["GITHUB_SHA"], job=job, operation="metadata", transport=transport)
    client.authenticate_actions_job()
    authority.attach(client, proof, env, root_bytes)
    binding = client._audit_operations_current
    run = client.json(client.allow(store.API + "/actions/runs/" + client.run_id))
    authority.authorize_client_actor(client, run)
    role, output_name = hosted.OPERATIONS_PHASES[phase]
    require(Path(request["output"]) == Path(request["cache"]).parent / output_name
            and client.job["api_job_id"] == native["api_job_id"] and client.job["job_id"] == hosted.JOBS[role]
            and client.source_sha == native["source_sha"] == go["source_sha"] and client.run_id == native["run_id"],
            "OPERATIONS_GENUINE_CURRENT_API_JOB_REQUIRED")
    result = Authenticated(request, native, client.job, go, env, client, proof, binding, _KEY)
    result.actual_run = deepcopy(run)
    return result.verify()


def guard(args, env, *, transport=None):
    native_envelope()
    require(args.phase == PHASE, "OPERATIONS_PHASE_NOT_IMPLEMENTED")
    context = authenticate_child(args, env, phase=PHASE, transport=transport)
    validate_request(context.request, PHASE)
    return context


def _match_callback(kind, document, *, context, clock):
    """Exact digest callback for the unchanged resume/grade metadata APIs."""
    expected = _digest(document)
    def authenticate(request):
        context.verify()
        from . import state
        return (type(request) is dict and request.get("kind") == kind and request.get("inputs_sha256") == expected
                and state.utc(request["at"]) <= state.utc(clock()))
    return authenticate


def prepare(context, *, clock=None, transport=None):
    require(type(context) is Authenticated, "LIVE_OPERATIONS_CONTEXT_REQUIRED")
    context.verify()
    from . import audit_weekly_operations_v1 as operations, audit_weekly_resume_v1 as resume
    from . import audit_weekly_grade_v1 as grade, audit_weekly_runtime_v1 as runtime
    from . import audit_weekly_grade_history_v1 as history
    from . import private_draft_store as store, gha_private_checkpoint as cp, state
    from .operational_storage import OperationalStorage
    clock = clock or state.now_utc
    request, inputs = context.request, context.request["inputs"]
    validate_request(request, PHASE)
    operations.context(context.go["effective_epoch"])
    locator = history.previous_checkpoint(context.go)
    if context.go["effective_epoch"]["schema_version"] in {operations.CONTEXT_V4,operations.CONTEXT_V5} and locator is not None:
        require(locator.get("schema_version")==history.LOCATOR_REF,"EXPLICIT_V4_HISTORY_LOCATOR_REQUIRED")
        history.require_latest(context.client,locator)
    pair = inputs["previous_grade_snapshot"]
    require((locator is None) == (pair is None), "EXACT_ROOT_HISTORY_INPUT_PAIR_REQUIRED")
    if pair is not None:
        require(pair["sidecar"]["sha256"] == locator["sha256"]
                and pair["public_receipt"]["sha256"] == context.go["effective_epoch"]["previous_capture"]["receipt_sha256"],
                "EXACT_ROOT_HISTORY_INPUT_HASHES_REQUIRED")
    storage = OperationalStorage(request["cache"], ROOT / "config/operational-source-policy-v2.json", state=request["state_root"])
    read_bytes = [0]
    def read(ref, cap=4 << 20, raw=False):
        context.verify()
        require(type(ref) is dict and type(ref.get("bytes")) is int and 0 < ref["bytes"] <= cap,
                "OPERATIONS_BOUNDED_METADATA_INPUT_REQUIRED")
        read_bytes[0] += ref["bytes"]
        require(read_bytes[0] <= LIMITS["metadata_bytes"], "OPERATIONS_TOTAL_METADATA_BYTE_CAP")
        return runtime.read_owned(storage, ref, cap, raw=raw)
    retained = read(inputs["retained_result"])
    models = read(inputs["retained_models"])
    prior_operations = {"context/ops_population.json", "ops_population", "context/ops_previous_checkpoint.json"}
    prior_operations.update("context/" + role + ".json" for role in HISTORY_ARCHIVE_ROLES)
    require(pair is not None or not prior_operations & set(retained["aliases"]),
            "QUALIFIED_PREVIOUS_PRIMARY_ASSIGNMENT_REQUIRED")
    require(retained["current_root_go_sha256"] == models["current_go_sha256"] == context.root_sha256,
            "OPERATIONS_RESTORATIONS_BELONG_TO_CURRENT_ROOT")
    identity = cp.client_identity(context.client)
    fields = ("repository", "run_id", "run_attempt", "source_sha", "workflow_ref", "job_id", "api_job_id")
    require(all(retained["current"][key] == models["current"][key] == identity[key] for key in fields)
            and state.utc(models["actual_completed_at"]) <= state.utc(clock()),
            "ORIGINAL_CURRENT_REPLAY_AND_RETENTION_PRECEDE_PREPARE")
    verified = None
    previous = None
    if pair is not None:
        # References transport bytes; only a same-process recovery grants a
        # history. Never decode an archived ops_previous_checkpoint as authority.
        verified = history.restore_previous(context, storage, pair["sidecar"], pair["public_receipt"], transport=transport)
        require(type(verified) is history.VerifiedHistory and verified.context is context,
                "LIVE_CURRENT_VERIFIED_HISTORY_REQUIRED")
        verified.verify()
        previous = verified.durable
        read_bytes[0] += sum(ref["bytes"] for ref in pair.values())
        require(read_bytes[0] <= LIMITS["metadata_bytes"], "OPERATIONS_TOTAL_METADATA_BYTE_CAP")
    old_choice = read(retained["aliases"]["runtime/WEEKLY_CHOICE.json"])
    raw = read(inputs["calendar"]["body"], LIMITS["calendar_bytes"], True)
    receipt = read(inputs["calendar"]["receipt"], 64 << 10)
    require(type(receipt) is dict and receipt.get("url") == CALENDAR_URL and receipt.get("status") == "acquired"
            and receipt.get("sha256") == inputs["calendar"]["body"]["sha256"] and receipt.get("bytes") == len(raw)
            and state.utc(context.go["issued_at_utc"]) <= state.utc(receipt["retrieved_utc"]) <= state.utc(clock()),
            "ACTUAL_CURRENT_FULL_CALENDAR_RECEIPT_REQUIRED")
    full = operations.calendar(raw, season=old_choice["slate"]["season"], week=old_choice["slate"]["week"])
    schedule = [{key: row[key] for key in ("season", "week", "game_type", "game_id", "kickoff_utc")} for row in full]
    epoch_doc = read(retained["aliases"]["context/epoch.json"])
    auth = _match_callback("GENUINE_RETAINED_CAPTURE_AND_FRESH_EFFECTIVE18", dict(retained_result=retained,
        retained_ref=inputs["retained_models"], original_weekly_choice_sha256=inputs["canonical_weekly_choice_sha256"],
        helper_sha256=resume.pins(), source_policy_sha256=cp.POLICY_SHA), context=context, clock=clock)
    calendar_auth = _match_callback("CURRENT_COMPLETE_SAME_WEEK_CALENDAR", dict(full_schedule=schedule,
        original_weekly_choice_sha256=inputs["canonical_weekly_choice_sha256"], epoch_sha256=state.digest(epoch_doc),
        current_root_go_sha256=context.root_sha256), context=context, clock=clock)
    require(not Path(request["output"]).exists(), "ONE_OPERATIONS_PREPARE_NO_RETRY")
    output = Path(request["output"])
    storage.register_root(output)
    declared = context.go["effective_epoch"].get("plan")
    if declared is None:
        declared = dict(kind="FUTURE_CAPABLE", season=old_choice["slate"]["season"], week=old_choice["slate"]["week"])
    require(declared["season"] == old_choice["slate"]["season"] and declared["week"] >= old_choice["slate"]["week"],
        "ROOT_PLAN_CANNOT_CHANGE_SEASON_OR_RETURN_TO_OLD_WEEK")
    anchor = resume._restore_anchor(retained, inputs["retained_models"], schedule, storage=storage, output=output/"resume",
        original_weekly_choice_sha256=inputs["canonical_weekly_choice_sha256"], authenticate=auth,
        authenticate_calendar=calendar_auth, clock=clock)
    full = operations.calendar(raw, season=declared["season"], week=declared["week"])
    target_schedule = [{key:row[key] for key in ("season", "week", "game_type", "game_id", "kickoff_utc")} for row in full]
    lead = context.go.get("cutoff_lead_seconds", 900)
    expected_plan = dict(original_choice_sha256=anchor["original"].sha256, full_schedule=target_schedule,
        cutoff_lead_seconds=lead)
    def plan_auth(value):
        context.verify()
        if value.get("kind") == "RECURRING_EXECUTION_PLAN_BEFORE_VALUES":
            return value.get("inputs_sha256") == grade._digest(expected_plan)
        if value.get("kind") == "NEXT_FULL_WEEK_SLATE_BEFORE_VALUES":
            from .weekly_generic_producer import prepare_slate
            from datetime import timedelta
            cutoffs = {r["game_id"]:(state.utc(r["kickoff_utc"])-timedelta(seconds=lead)).isoformat() for r in target_schedule}
            slate = prepare_slate(target_schedule, season=declared["season"], week=declared["week"], game_cutoffs=cutoffs, now=anchor["at"])
            return value.get("inputs_sha256") == grade._digest(dict(slate=slate, full_schedule=target_schedule))
        return False
    if context.go["effective_epoch"]["schema_version"] in {operations.CONTEXT_V4,operations.CONTEXT_V5} and locator is not None:
        history.require_latest(context.client,locator)
        require(verified is not None and "planning" in verified.proof,"LIVE_PRIVATE_HISTORY_PLANNING_REQUIRED")
        expected=history.next_plan(verified.proof["planning"],at=state.utc(context.go["issued_at_utc"]))
        require(expected==declared,"EXACT_PARENT_ROUTING_FROM_FRESHEST_PRIVATE_CAUSAL_HISTORY")
    target, execution = operations.recurring_plan(anchor["registered"], anchor["original"], target_schedule,
        authenticate=plan_auth, durable=previous, cutoff_lead_seconds=lead,
        relocated_replays=(anchor["replay"],), clock=lambda:anchor["at"])
    planning=None
    if context.go["effective_epoch"]["schema_version"] in {operations.CONTEXT_V4,operations.CONTEXT_V5}:
        require(state.digest(target_schedule)==declared["calendar_sha256"],"ROOT_FROZEN_COMPLETE_CALENDAR_CHANGED")
        if declared["kind"]=="FUTURE_CAPABLE":
            expected=target.document["slate"]["game_cutoffs"]
            if declared["week"]==anchor["original"].document["slate"]["week"]:
                expected={r["game_id"]:expected[r["game_id"]] for r in target_schedule if state.utc(r["kickoff_utc"])>anchor["at"]}
            require(expected==declared["game_cutoffs"] and state.utc(clock())<state.utc(declared["deadline_utc"]),
                "ACTUAL_FROZEN_DEADLINE_AND_CUTOFFS_BEFORE_NEW_VALUES")
        planning=operations.planning_seed(anchor["registered"],target,target_schedule,raw,receipt,cutoff_lead_seconds=lead)
    if context.go["effective_epoch"].get("schema_version") not in {operations.CONTEXT_V3,operations.CONTEXT_V4,operations.CONTEXT_V5} and execution["kind"] == "GRADE_ONLY":
        resume._calendar(schedule, anchor["original"], anchor["at"])
    require(declared["kind"] != "GRADE_ONLY" or execution["kind"] == "GRADE_ONLY", "EXPLICIT_GRADE_ONLY_PLAN_CANNOT_CAPTURE")
    if execution["kind"] == "GRADE_ONLY":
        require(declared["kind"] == "GRADE_ONLY", "EXPLICIT_ROOT_GRADE_ONLY_PLAN_REQUIRED")
        require(previous is not None and pair is not None and {"context/ops_population.json", "context/ops_roles.json", "context/ops_schedule.json"} <= set(retained["aliases"]),
            "ORIGINAL_PREVALUE_PRIMARY_CAPTURES_REQUIRED_NO_POSTHOC_ASSIGNMENT")
        require(declared["week"] == old_choice["slate"]["week"], "GRADE_ONLY_RETAINS_ORIGINAL_WEEK")
        manifest = dict(schema_version=VERSION+"-prepared", state="ORIGINAL_CAPTURES_GRADE_ONLY_READY_LOCAL",
            current_root_go_sha256=context.root_sha256, execution_plan=execution, current_values_used=False,
            inputs=None, archive_context={}, grade_inputs=dict(retained_result=inputs["retained_result"], previous_grade_snapshot=pair),
            actual_completed_at=state.utc(clock()).isoformat(), no_reselection=True, no_cutoff_extension=True,
            fits=0, model_decodes=0, source_acquisitions=0, label_acquisitions=0, public_release=False, successful_forecast=False)
        if planning is not None:manifest["history_planning"]=planning
        context.verify(); verified.verify()
        ref = runtime.write(storage, output/"PREPARED.json", manifest)
        return dict(state=manifest["state"], manifest=ref, fits=0, public_release=False, successful_forecast=False)
    if target.document["slate"]["week"] > anchor["original"].document["slate"]["week"]:
        resumed = resume.prepare_next(anchor, target, target_schedule, inputs["retained_models"], storage=storage,
            output=output/"resume", clock=clock)
    else:
        resumed = resume._resume_anchor(anchor, retained, inputs["retained_models"], schedule, storage=storage,
            output=output / "resume", authenticate_calendar=calendar_auth, clock=clock)
    require(verified is None or verified.registered.epoch.sha256 == resumed.registered.epoch.sha256,
            "EXACT_RESUMED_REGISTERED_HISTORY_EPOCH_REQUIRED")
    require(read_bytes[0] + resumed.document["metadata_bytes_read"] + sum(ref["bytes"] for ref in models["models"])
            <= LIMITS["metadata_bytes"], "OPERATIONS_TOTAL_METADATA_BYTE_CAP")
    def role_auth(value):
        context.verify()
        return value == dict(schema_version=operations.VERSION + "-authentication-request",
            kind="QUALIFIED_CURRENT_MODEL_MANIFEST_METADATA", binding=inputs["retained_models"])
    roles = operations.roles_from_manifests(storage, inputs["retained_models"], authenticate=role_auth)
    population = grade.population_template(resumed.registered, resumed.choice)
    # primary_population owns assignment reconciliation. Its live callback closes
    # the actual population against this request, epoch, choice and role map.
    def population_auth(value):
        context.verify()
        require(value.get("kind") == "POPULATION_BEFORE_VALUES", "EXACT_PREVALUE_POPULATION_CALLBACK_REQUIRED")
        return value["inputs_sha256"] == population_expected[0]
    # Build the expected assignments with the SAME explicit preserved map; the
    # existing operations function independently checks conflicts/role streams.
    old = {}
    if previous is not None:
        for capture in previous.document["captures"]:
            for gid, assigned in capture["population"]["assignments"].items():
                require(gid not in old or old[gid] == assigned, "NO_CONFLICTING_PRIOR_PRIMARY_ASSIGNMENTS")
                old[gid] = assigned
        # An archived refresh may name earlier primaries. Its claims must be
        # represented in the independently recovered complete history.
        for role in ("context/ops_population.json", "ops_population"):
            if role in retained["aliases"]:
                prior = read(retained["aliases"][role])
                require(prior.get("epoch_sha256") == resumed.registered.epoch.sha256
                        and prior.get("stream_id") == operations.STREAM
                        and prior.get("role_catalog_sha256") == state.digest(roles)
                        and type(prior.get("assignments")) is dict and prior["assignments"]
                        and all(old.get(gid) == assigned for gid, assigned in prior["assignments"].items()),
                        "ARCHIVED_PRIMARY_ASSIGNMENTS_REQUIRE_COMPLETE_LIVE_HISTORY")
    require(read_bytes[0] + resumed.document["metadata_bytes_read"] + sum(ref["bytes"] for ref in models["models"])
            <= LIMITS["metadata_bytes"], "OPERATIONS_TOTAL_METADATA_BYTE_CAP")
    stamp = clock()
    population.update(state="ROOT_REGISTERED", stream_id=operations.STREAM, registered_at=state.utc(stamp).isoformat(),
        role_catalog_sha256=state.digest(roles), assignments={gid:old.get(gid, inputs["capture_id"]) for gid in population["assignments"]})
    population_expected = [state.digest(population)]
    bound, assignment = operations.primary_population(resumed.registered, resumed.choice, roles,
        capture_id=inputs["capture_id"], authenticate=population_auth, previous=previous, clock=lambda:stamp)
    refs = dict(ops_population=runtime.write(storage, output / "OPS_POPULATION.json", bound.document),
        ops_roles=runtime.write(storage, output / "OPS_ROLES.json", roles),
        ops_schedule=runtime.write(storage, output / "OPS_SCHEDULE.json", full),
        canonical_weekly_choice=resumed.document["canonical_weekly_choice"],
        capture_scope=resumed.document["capture_scope_binding"],
        ops_previous_checkpoint=verified.binding if verified is not None else None)
    if planning is not None:refs["ops_planning"]=runtime.write(storage,output/"HISTORY_PLANNING.json",planning)
    if verified is not None:
        refs.update(zip(HISTORY_ARCHIVE_ROLES, (pair["sidecar"], pair["public_receipt"])))
    assignment_ref = runtime.write(storage, output / "ASSIGNMENT.json", assignment)
    context.verify(); resumed.verify(clock())
    if verified is not None:
        verified.verify()
    scope = resumed.document["capture_scope"]
    manifest = dict(schema_version=VERSION + "-prepared", state="SAME_WEEK_PREVALUE_METADATA_READY_LOCAL",
        execution_plan=execution,
        current_root_go_sha256=context.root_sha256, native_authority_sha256=state.digest(context.authority),
        request_sha256=state.digest(request), actual_completed_at=state.utc(clock()).isoformat(),
        capture_id=inputs["capture_id"], epoch_sha256=resumed.registered.epoch.sha256, choice_sha256=resumed.choice.sha256,
        original_weekly_choice_sha256=inputs["canonical_weekly_choice_sha256"], resumed=resumed.binding,
        inputs=resumed.inputs, history_binding=resumed.document["history_binding"], archive_context=refs,
        assignment=assignment_ref, partially_elapsed_week=bool(scope["elapsed_game_ids"]),
        elapsed_game_ids=scope["elapsed_game_ids"], active_game_ids=scope["active_game_ids"],
        no_reselection=True, no_cutoff_extension=True, current_values_used=False, metadata_remote_durability_qualified=False,
        model_decodes=0, source_acquisitions=0, label_acquisitions=0, fits=0, public_release=False, successful_forecast=False)
    require(len(store.canonical(manifest)) <= LIMITS["manifest_bytes"], "FINITE_COMPLETE_OPERATIONS_MANIFEST")
    ref = runtime.write(storage, output / "PREPARED.json", manifest)
    return dict(state=manifest["state"], manifest=ref, capture_id=inputs["capture_id"],
        partially_elapsed_week=manifest["partially_elapsed_week"], fits=0, public_release=False, successful_forecast=False)


def run(args, env, *, transport=None):
    return prepare(guard(args, env, transport=transport), transport=transport)


def contract():
    return dict(schema_version=VERSION + "-contract", state="PARENT_ROOT_AND_NATIVE_PHASE_WIRING_REQUIRED",
        supported_phases=[PHASE], unimplemented_phases=list(PENDING_PHASES), request_keys=sorted(REQUEST_KEYS),
        input_keys=sorted(INPUT_KEYS), limits=LIMITS, same_week_only=False, upstream_exact_receipt_discovery_required=True,
        same_week_future_guards_unchanged=True, later_week_requires_durable_resolved_history=True,
        grade_only_requires_original_prevalue_population=True, scheduled_grade_only_discovery_ready=False,
        previous_checkpoint_requires_unimplemented_live_native_restore=False,
        history_input_keys=sorted(HISTORY_INPUT_KEYS), history_archive_roles=list(HISTORY_ARCHIVE_ROLES),
        history_requires_live_native_restore=True, history_json_is_authority=False,
        history_compatibility="SAME_SOURCE_SHA_AND_EXACT_UNCHANGED_GRADE_CHECKPOINT_PINS", output_name=OUTPUT_NAME,
        source_acquisitions=0, model_decodes=0, fits=0, public_release=False)
