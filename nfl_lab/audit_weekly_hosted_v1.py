"""One owner-authorized weekly correction in the existing serialized workflow.

Every phase authenticates the real current Actions job. Historical identities
remain historical. New native requests are derived only after that check and
are scoped to one source/root/request. Numerical children remain isolated;
this parent never fits, searches, loads outcomes or calls a paid service.
"""
from __future__ import annotations

import base64
import csv
from datetime import datetime, timedelta, timezone
import io
import gzip
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from . import private_draft_store as store, gha_private_checkpoint as cp
from . import audit_count_retained_v1 as retained, audit_count_requalify_v1 as bounds
from . import audit_weekly_origin_v1 as origin, audit_weekly_epoch_v1 as epoch
from . import audit_weekly_runtime_v1 as runtime, audit_weekly_archive_v1 as archive
from . import audit_reference_capture_v1 as reference
from . import audit_weekly_public_v1 as public, audit_weekly_retained_v1 as weekly_retained
from .audit_weekly_template_v1 import retained_registration
from . import operational_failure_v1 as failure
from . import audit_numerical_runtime_v1 as numerical
from . import audit_weekly_operations_authority_v1 as operations_authority
from .operational_storage import OperationalStorage, _OWNER
from .owned_reference_batch import validate_owned_references
from .state import digest, now_utc, utc

VERSION = "audit-weekly-hosted-v2"
MODE = "audit-weekly-producer-v1"
ROOT = Path(__file__).resolve().parents[1]
JOBS = dict(produce="audit-weekly-produce-v1", restore="audit-weekly-restore-v1", consume="audit-weekly-export-v1")
FAILURE_JOB = "audit-weekly-failure-restore-v1"
EXECUTION_JOBS = dict(JOBS, evidence=FAILURE_JOB)
OPERATIONS_PHASES = {"operations-prepare":("produce","operations-prepared"),
    "operations-retained":("produce","operations-retained"),
    "operations-grade-retained-write":("restore","operations-grade-retained-write"),
    "operations-grade-retained-read":("consume","operations-grade-retained-read"),
    "operations-grade-write":("restore","operations-grade-write"),
    "operations-grade-read":("consume","operations-grade-read"),
    "controller-template-write":("produce","controller-template-write"),
    "controller-template-read":("restore","controller-template-read"),
    "controller-template-seal":("consume","controller-template-seal")}
LIMITS = dict(wall_seconds=1500, CPU_seconds=900, address_space_bytes=4 << 30,
    global_private_bytes=512 << 20, runtime_bytes=32 << 20, fits=0, searches=0,
    automatic_retry=False, maximum_dispatches=1, public_raw_or_models=False)
ROOT_KEYS = {"schema_version", "approved", "repository", "mode", "operation", "source_sha", "workflow_ref",
    "owner_authorization", "issued_at_utc", "expires_at_utc", "single_writer_group", "code_pins",
    "limits", "jobs", "failure_restorer", "retained_registration", "original_selected_handoff", "qualified_runtime",
    "pending_census", "source_config", "cutoff_lead_seconds", "publication", "publication_registration", "effective_epoch"}
PINS = tuple(sorted(set(retained.CURRENT_FILES) | set(origin.FILES) | set(runtime.PIN_PATHS) |
    set(archive.PIN_PATHS) | set(public.PIN_PATHS) | set(weekly_retained.PIN_PATHS) |
    {"nfl_lab/audit_weekly_hosted_v1.py", "tools/audit_weekly_hosted_v1.py",
    "nfl_lab/audit_reference_capture_v1.py", "tools/audit_reference_capture_v1.py",
    "tests/test_audit_weekly_hosted_v1.py", "tests/test_audit_weekly_epoch_v1.py",
    "tests/test_audit_weekly_origin_v1.py", "tests/test_audit_weekly_archive_v1.py",
    "tests/test_audit_reference_capture_v1.py", "tools/audit_process_guard_v1.py", "requirements-audit-weekly-metadata-v1.lock",
    "nfl_lab/audit_weekly_delivery_v1.py", "tools/audit_weekly_delivery_v1.py", "tests/test_audit_weekly_delivery_v1.py",
    "nfl_lab/public_release_plan_v1.py",
    "nfl_lab/operational_failure_v1.py",
    "tests/test_audit_weekly_failed_scope_v1.py", "tests/test_audit_weekly_failure_wire_v1.py",
    "tests/test_audit_weekly_receipt_bundle_v1.py",
    "tests/test_audit_weekly_child_status_v1.py", "tests/test_audit_weekly_archive_scale_v1.py",
    "tests/test_audit_weekly_archive_packing_v1.py",
    "nfl_lab/audit_numerical_runtime_v1.py", "tests/test_audit_numerical_runtime_v1.py",
    "config/audit-weekly-numerical-runtime-v1.json",
    ".github/workflows/audit-source-checks.yml",
    # Executable operational closure and the independently required bootstrap
    # checks. Standalone preparation CLIs are not invoked by this workflow.
    # The full repository CI still checks their exact committed source.
    "nfl_lab/audit_weekly_controller_v1.py", "tools/audit_weekly_controller_v1.py",
    "nfl_lab/audit_weekly_controller_bootstrap_v1.py", "tools/audit_weekly_controller_bootstrap_v1.py",
    "tests/test_audit_weekly_controller_v1.py", "tests/test_audit_weekly_controller_bootstrap_v1.py",
    "nfl_lab/audit_weekly_template_v1.py", "nfl_lab/audit_weekly_discovery_v1.py",
    "nfl_lab/audit_weekly_resume_v1.py", "nfl_lab/audit_weekly_grade_v1.py",
    "nfl_lab/audit_weekly_grade_checkpoint_v1.py", "nfl_lab/audit_weekly_provider_v1.py",
    "nfl_lab/audit_weekly_operations_v1.py", "nfl_lab/audit_weekly_operations_authority_v1.py",
    "nfl_lab/audit_weekly_operations_restore_v1.py", "tools/audit_weekly_operations_restore_v1.py",
    "nfl_lab/audit_weekly_operations_worker_v1.py", "tools/audit_weekly_operations_worker_v1.py",
    "nfl_lab/audit_weekly_operations_grade_v1.py", "tools/audit_weekly_operations_grade_v1.py",
    "tests/test_audit_weekly_operations_worker_v1.py", "tests/test_audit_weekly_operations_restore_v1.py",
    "tests/test_audit_weekly_operations_grade_v1.py", "tests/test_audit_weekly_operations_grade_scale_v1.py",
    "nfl_lab/audit_weekly_controller_registration_v1.py", "tools/audit_weekly_controller_registration_v1.py",
    "tests/test_audit_weekly_controller_registration_v1.py", "tests/test_audit_weekly_archive_packing_v1.py",
    "tools/mask_dispatch_inputs.py", "tests/test_private_dispatch_masking_v1.py",
    "nfl_lab/audit_weekly_grade_history_v1.py", "tests/test_audit_weekly_grade_history_v1.py",
    "nfl_lab/audit_weekly_parent_v1.py", "tools/audit_weekly_parent_v1.py", "tests/test_audit_weekly_parent_v1.py",
    "nfl_lab/cadence.py", "nfl_lab/state.py", "nfl_lab/weekly_grading.py",
    "tests/test_audit_weekly_grade_checkpoint_v1.py", "tests/test_audit_weekly_parent_workflow_v1.py", "tests/test_cadence.py",
    "tools/audit_weekly_grade_checkpoint_v1.py", "tools/audit_weekly_grade_v1.py"}
    - {"tests/test_audit_weekly_child_status_v1.py"}))
# Runtime pins cover the complete executable closure and mandatory protocol
# tests. These three additional qualification suites remain in full exact-source
# CI, not in the private Root's bounded runtime inventory; no test is skipped.
CI_ONLY_QUALIFICATION_TESTS=("tests/test_audit_weekly_child_status_v1.py",
    "tests/test_audit_weekly_workflow_composition_v1.py", "tests/test_audit_weekly_delivery_grading_v1.py")
NATIVE_KEYS={"schema_version","phase","request_sha256","owner_root_go_sha256","repository","source_sha",
    "run_id","run_attempt","job_id","workflow_ref","api_job_id","issued_at_utc","expires_at_utc",
    "actual_actions_api_authenticated","owner_root_checked","fits","public_release"}


def require(ok, code):
    if not ok: raise store.StoreError(code)


def pins(): return {p:store.sha(store.read_local(ROOT/p,2 << 20)) for p in PINS}


def publication_configuration(go, *, now):
    """Decode only root-approved bounded metadata, never forecast bytes.

    The exact canonical policy is registered in the owner root before current
    source reads. Compression is only for Actions' finite input-size ceiling.
    The producer archives the decoded body unchanged before acquiring values.
    """
    if go["publication"] is False:
        require(go["publication_registration"] is None,"NO_IMPLICIT_PUBLICATION_REGISTRATION")
        return None
    value=go["publication_registration"]
    require(type(value) is dict and set(value)=={"policy_gzip_base64","policy_sha256","rights_authority","r0"},
        "CLOSED_ROOT_PUBLICATION_REGISTRATION")
    encoded=value["policy_gzip_base64"]
    require(type(encoded) is str and 0<len(encoded)<=48 << 10,"FINITE_PUBLIC_METADATA_INPUT")
    try:
        packed=base64.b64decode(encoded,validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as source:
            body=source.read((128 << 10)+1)
        require(0<len(body)<=128 << 10 and store.sha(body)==value["policy_sha256"],"EXACT_BOUNDED_PUBLIC_POLICY_BODY")
        policy=cp.strict_json(body)
    except store.StoreError:raise
    except Exception:raise store.StoreError("PUBLIC_METADATA_ENCODING_INVALID") from None
    require(body==store.canonical(policy),"CANONICAL_ROOT_PUBLIC_POLICY")
    public.policy_check(policy,at=now.isoformat())
    replay=retained_registration(go)["origin"]["replay_catalog"]
    require(policy["source_sha"]==go["source_sha"] and policy["source_branch"]=="research/weekly-storage-probe-v1"
        and policy["jobs"]==JOBS
        and (utc(policy["registered_at_utc"])<=utc(go["issued_at_utc"]) if go.get("operation")=="RECURRING_CAPTURE"
             else policy["registered_at_utc"]==go["issued_at_utc"])
        and policy["workflow_sha256"]==store.sha(store.read_local(ROOT/".github/workflows/lab.yml",128 << 10))
        and policy["approved_candidates"]==[{k:s[k] for k in ("target","family","method_id","procedure_version")} for s in replay["slots"]],
        "EXACT_CURRENT_ROOT_PUBLICATION_SCOPE_BEFORE_VALUES")
    rights=value["rights_authority"];r0=value["r0"]
    from .public_release_plan_v1 import RIGHTS
    require(type(rights) is dict and set(rights)==RIGHTS and rights.get("schema_version")=="weekly-selected-derived-rights-authority-v1"
        and rights.get("state")=="ROOT_REGISTERED" and rights.get("scope")=="SELECTED_DERIVED_ONLY"
        and rights.get("authority_kind")=="ROOT_APPROVED_DERIVED_PUBLICATION"
        and rights.get("public_raw_or_model_weights") is False and rights.get("human_approval") is False
        and rights.get("source_policy_sha256")==cp.POLICY_SHA
        and rights.get("public_fields")==list(public.overlay.ROW_FIELDS)
        and public.feed.h(rights["source_review_sha256"]) and type(rights["basis"]) is str and 0<len(rights["basis"])<=4096
        and rights["upstream_blanket_grant"] is False
        and digest(rights) in policy["rights_authorities"] and digest(r0) in policy["r0_identities"],
        "REGISTERED_DERIVED_SOURCE_RIGHTS_AND_ORIGINAL_R0_REQUIRED")
    require(type(r0) is dict and r0.get("schema_version")=="weekly-actual-r0-freeze-v1"
        and r0.get("state")=="ACTUAL_FIRST_RELEASE_R0_FROZEN" and type(r0.get("deployment_id")) is int and r0["deployment_id"]>0
        and re.fullmatch(r"[a-f0-9]{40}",str(r0.get("deployed_source_sha"))) and public.feed.h(r0.get("visible_board_sha256"))
        and r0.get("engine_sha256")==policy["engine_sha256"]
        and utc(r0["frozen_at"])<=utc(policy["registered_at_utc"]),"ORIGINAL_R0_FROZEN_BEFORE_NEW_POLICY_AND_VALUES")
    return dict(policy=policy,rights_authority=rights,r0=r0)


def validate_root(go, *, now):
    from . import audit_weekly_template_v1 as template
    require(type(go) is dict and set(go)==template.root_keys(go)
        and go["approved"] is True and go["repository"]==store.REPO and go["mode"]==MODE
        and go["owner_authorization"]=="OWNER_NFL_AUDIT_CONTINUATION_20261025"
        and go["single_writer_group"]=="nfl-lab-single-writer" and go["limits"]==LIMITS
        and go["jobs"]==JOBS and go["failure_restorer"]==FAILURE_JOB and go["code_pins"]==pins(), "CLOSED_CURRENT_WEEKLY_ROOT_REQUIRED")
    require(re.fullmatch(r"[a-f0-9]{40}",str(go["source_sha"]))
        and go["workflow_ref"]==store.REPO+"/.github/workflows/lab.yml@refs/heads/research/weekly-storage-probe-v1",
        "EXACT_REGISTERED_WEEKLY_SOURCE_BRANCH")
    issued,expires=utc(go["issued_at_utc"]),utc(go["expires_at_utc"])
    require(issued<=now<expires and 0<(expires-issued).total_seconds()<=3600,"CURRENT_WEEKLY_GO_CLOCK")
    require(type(go["cutoff_lead_seconds"]) is int and go["cutoff_lead_seconds"]==5400
        and type(go["publication"]) is bool,
        "EXPLICIT_INITIAL_CORRECTION_SCOPE_NO_BACKFILL")
    require(go["operation"] in {"ORIGIN_METADATA_ONLY","CURRENT_CORRECTION_CAPTURE","RECURRING_CAPTURE","CONTROLLER_REGISTRATION"}
        and (go["publication"] is False or go["operation"] in {"CURRENT_CORRECTION_CAPTURE","RECURRING_CAPTURE","CONTROLLER_REGISTRATION"}),
        "EXPLICIT_WEEKLY_PUBLICATION_SCOPE")
    if go['schema_version'] == template.ROOT_V3:
        require(go['operation'] in {'RECURRING_CAPTURE','CONTROLLER_REGISTRATION'}, 'EXPLICIT_DUAL_RUNTIME_OPERATION')
        template.prior_runtime(go, before=go['issued_at_utc'])
    if go["operation"]=="RECURRING_CAPTURE":
        from . import audit_weekly_operations_v1 as operations
        operations.context(go["effective_epoch"])
        require(go['schema_version'] != template.ROOT_V3 or go['effective_epoch']['schema_version']==operations.CONTEXT_V4,
            'EXPLICIT_DUAL_RUNTIME_HISTORY_PROTOCOL')
    elif go["operation"]=="CONTROLLER_REGISTRATION":
        from . import audit_weekly_controller_registration_v1 as registration
        try:registration.context(go["effective_epoch"])
        except registration.RegistrationError:
            raise store.StoreError("EXACT_OWNER_CONTROLLER_REGISTRATION_CONTEXT") from None
    else:require(go["effective_epoch"] is None,"NO_IMPLICIT_RECURRING_CONTEXT")
    retained.validate_registration(retained_registration(go))
    require(go["qualified_runtime"]["schema_version"]=="audit-private-rotation-v1-qualified-runtime"
        and go["qualified_runtime"]["runtime_reserved_bytes"]==32 << 20,
        "NEW_GENUINELY_QUALIFIED_NAMESPACE_REQUIRED")
    runtime.config_check(go["source_config"],dict(season=2026,week=8))
    require(go["source_config"].get("purpose")=="CURRENT_OPERATIONAL_INFERENCE","FROZEN_INFERENCE_PURPOSE_REQUIRED_NO_TUNING")
    publication_configuration(go,now=now)
    return go


def read_owned(storage, ref, cap=4 << 20, *, raw=False):
    validate_owned_references(storage,{ref["path"]:ref["sha256"]})
    body=cp.read_ref(ref,cap)
    return body if raw else cp.strict_json(body)


def read_owned_stdio(storage,ref):
    """Raw child stdio may be empty; checkpoint/JSON references remain nonempty."""
    require(type(ref) is dict and set(ref)=={"path","bytes","sha256"}
        and type(ref["path"]) is str and Path(ref["path"]).suffix in {".stdout",".stderr"}
        and type(ref["bytes"]) is int and 0<=ref["bytes"]<=64 << 10
        and type(ref["sha256"]) is str and store.HASH.fullmatch(ref["sha256"]),"EXACT_OWNED_STDIO_REFERENCE")
    validate_owned_references(storage,{ref["path"]:ref["sha256"]})
    body=store.read_local(ref["path"],64 << 10)
    require(len(body)==ref["bytes"] and store.sha(body)==ref["sha256"],"OWNED_STDIO_REFERENCE_HASH_OR_LENGTH")
    return body


def write(storage,path,value):
    storage.write_bytes(path,store.canonical(value));return cp.binding(path)


def actual_failure(env, *, python_failure_recorded, action_failure_recorded=False):
    value=env.get("AUDIT_WEEKLY_ORIGINAL_EXIT_CODE","")
    require(value=="" or re.fullmatch(r"[1-9][0-9]{0,2}",value) and int(value)<=255,"ACTUAL_FAILED_STEP_EXIT_CODE_REQUIRED")
    code=int(value) if value else None
    kind="DEADLINE" if code==124 else "INTERRUPTION" if code in {130,137,143} or not (python_failure_recorded or action_failure_recorded) else "EXCEPTION"
    return dict(kind=kind,code="WEEKLY_ACTION_STEP_FAILED" if action_failure_recorded else "WEEKLY_PHASE_FAILED_RETAINED",exit_code=code)


def error_diagnostic(error):
    """Public code locations and type only; never exception text/values."""
    kind=type(error).__name__
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}",kind):kind="Exception"
    frames=[];trace=error.__traceback__
    while trace is not None:
        path=Path(trace.tb_frame.f_code.co_filename).resolve()
        if path.is_relative_to(ROOT):
            name=path.relative_to(ROOT)
            if name.parts[0] in {"nfl_lab","tools"} and name.suffix==".py":
                frames.append(dict(file=name.as_posix(),line=trace.tb_lineno))
        trace=trace.tb_next
    return dict(error_type=kind,source_frames=frames[-5:])


class Runner:
    def __init__(self, phase, env, *, existing=False):
        from tools.private_draft_store_v2 import actions_context
        require(phase in EXECUTION_JOBS,"CLOSED_WEEKLY_PHASE")
        self.phase,self.env=phase,env
        raw=env.get("AUDIT_WEEKLY_ROOT_GO_JSON","").encode()
        require(0<len(raw)<=60 << 10 and store.sha(raw)==env.get("AUDIT_WEEKLY_ROOT_GO_SHA256"),"EXACT_WEEKLY_ROOT_INPUT")
        self.go=validate_root(cp.strict_json(raw),now=now_utc());self.go_sha=store.sha(raw)
        require(store.canonical(self.go)==raw,"CANONICAL_WEEKLY_ROOT")
        self.operations_proof=operations_authority.current(env,raw,ROOT)
        require(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
            and env.get("GITHUB_REPOSITORY")==store.REPO and env.get("GITHUB_RUN_ATTEMPT")=="1"
            and env.get("GITHUB_SHA")==env.get("GITHUB_WORKFLOW_SHA")==self.go["source_sha"]
            and env.get("GITHUB_WORKFLOW_REF")==self.go["workflow_ref"] and env.get("GITHUB_JOB")==EXECUTION_JOBS[phase]
            and env.get("STORE_PERMISSION")=="write","GENUINE_OWNER_WEEKLY_JOB_REQUIRED")
        event=cp.strict_json(store.read_local(env["GITHUB_EVENT_PATH"],256 << 10))
        require(event.get("repository",{}).get("full_name")==store.REPO
            and event.get("inputs",{}).get("mode")==MODE
            and event["inputs"].get("inference_builder_go_json")==raw.decode()
            and event["inputs"].get("inference_builder_go_sha256")==self.go_sha,"ACTUAL_WEEKLY_DISPATCH_INPUTS")
        require(subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()==self.go["source_sha"]
            and subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",*PINS],cwd=ROOT,text=True)=="",
            "CLEAN_EXACT_COMMITTED_WEEKLY_SOURCE")
        numerical=cp.strict_json(store.read_local(ROOT/"config/weekly-owner-private-bootstrap-v1.json",1 << 20))["numerical_environment"]
        require(all(env.get(k)==v for k,v in numerical.items()),"EXACT_WEEKLY_NUMERICAL_STARTUP")
        self.root=store.parents_safe(env["RUNNER_TEMP"])/(VERSION+"-"+env["GITHUB_RUN_ID"]+"-"+phase)
        require((self.root.is_dir() and not self.root.is_symlink()) if existing else not self.root.exists(),"ONE_WEEKLY_INVOCATION_NO_RETRY")
        if not existing:self.root.mkdir(mode=0o700)
        self.storage=OperationalStorage(self.root/"cache",ROOT/"config/operational-source-policy-v2.json",state=self.root/"state")
        self.storage.register_root(self.root)
        self.journal=self.root/"journal"
        if not existing:self.journal.mkdir(mode=0o700)
        self.job=actions_context(env,"write")
        if existing:
            self.root_ref=cp.binding(self.root/"OWNER_ROOT.json");self.package_ref=cp.binding(self.root/"QUALIFIED_RUNTIME.json")
            require(read_owned(self.storage,self.root_ref)==self.go and read_owned(self.storage,self.package_ref)==self.go["qualified_runtime"],"EXACT_ORIGINAL_FAILED_ROOT_REQUIRED")
        else:
            self.root_ref=write(self.storage,self.root/"OWNER_ROOT.json",self.go)
            self.package_ref=write(self.storage,self.root/"QUALIFIED_RUNTIME.json",self.go["qualified_runtime"])
            # Persist the local start AFTER static event/source checks, BEFORE
            # the first authentication request. This is not an API proof.
            write(self.storage,self.root/"BOOTSTRAP_STARTED.json",dict(schema_version=VERSION+"-bootstrap-start",
                state="STATIC_SOURCE_AND_EVENT_CHECKED_API_AUTHENTICATION_PENDING",actual_started_at=now_utc().isoformat(),
                root_go_sha256=self.go_sha,run_id=env["GITHUB_RUN_ID"],source_sha=env["GITHUB_SHA"],
                job_id=EXECUTION_JOBS[phase],workflow_ref=env["GITHUB_WORKFLOW_REF"],actual_actions_api_authenticated=False))
        start=read_owned(self.storage,cp.binding(self.root/"BOOTSTRAP_STARTED.json"))
        require(start["schema_version"]==VERSION+"-bootstrap-start" and start["root_go_sha256"]==self.go_sha
            and start["run_id"]==env["GITHUB_RUN_ID"] and start["source_sha"]==env["GITHUB_SHA"]
            and start["job_id"]==EXECUTION_JOBS[phase] and start["workflow_ref"]==env["GITHUB_WORKFLOW_REF"]
            and start["actual_actions_api_authenticated"] is False
            and utc(self.go["issued_at_utc"])<=utc(start["actual_started_at"])<=now_utc(),"EXACT_ORIGINAL_STATIC_BOOTSTRAP_START")
        class Metadata(archive.Client):
            def request(self,url,*,method="GET",**kw):
                require(method=="GET" and kw.get("data") is None,"ROOT_METADATA_GET_ONLY")
                return super().request(url,method=method,**kw)
        try:
            self.client=Metadata(env.get("GITHUB_TOKEN"),env["GITHUB_RUN_ID"],source_sha=env["GITHUB_SHA"],journal=self.journal,
                job=self.job,operation="metadata",qualification=self.go["qualified_runtime"]["qualification"])
            self.client.authenticate_actions_job();self.client.bind(self.go["qualified_runtime"]["binding"])
            operations_authority.attach(self.client,self.operations_proof,env,raw)
            archive.authenticate_qualification(self.client,self.go["qualified_runtime"],self.go["pending_census"])
            jobs=archive.jobs_for(self.client);self.identity=cp.client_identity(self.client)
            current=[j for j in jobs if j.get("id")==self.identity["api_job_id"]]
            require(len(current)==1 and utc(current[0]["started_at"])<=utc(start["actual_started_at"])<=now_utc(),
                "ORIGINAL_LOCAL_START_WITHIN_GENUINE_CURRENT_JOB")
        except Exception as error:
            code=error.code if isinstance(error,store.StoreError) else "WEEKLY_BOOTSTRAP_AUTHENTICATION_FAILED"
            if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}",code):code="WEEKLY_BOOTSTRAP_AUTHENTICATION_FAILED"
            path=self.root/"BOOTSTRAP_FAILED.json"
            if not path.exists():write(self.storage,path,dict(state="FAILED_RETAINED",reason=code,actual_observed_at=now_utc().isoformat(),
                original_start_sha256=cp.binding(self.root/"BOOTSTRAP_STARTED.json")["sha256"],successful_forecast=False,public_release=False,
                diagnostic=error_diagnostic(error)))
            raise
        if not existing:
            write(self.storage,self.root/"PARENT_STARTED.json",dict(actual_started_at=start["actual_started_at"],actual_identity=self.identity))
        elif not (self.root/"PARENT_STARTED.json").exists():
            # Fresh preservation authenticated the original static start now.
            # Do not invent an API-authenticated original process or receipt.
            write(self.storage,self.root/"BOOTSTRAP_REAUTHENTICATED.json",dict(state="ORIGINAL_STATIC_START_AUTHENTICATED_FOR_FAILURE_ONLY",
                original_start_sha256=cp.binding(self.root/"BOOTSTRAP_STARTED.json")["sha256"],current_identity=self.identity,
                actual_authenticated_at=now_utc().isoformat(),original_process_api_proof_retained=False,public_release=False))
        self.publication=publication_configuration(self.go,now=now_utc())
        if self.operations_proof is not None and self.publication is not None:
            from . import audit_weekly_controller_bootstrap_v1 as bootstrap
            bootstrap.authorize_policy(self.operations_proof,raw,store.canonical(self.publication["policy"]))
        if (self.root/"PARENT_STARTED.json").exists():
            original_start=read_owned(self.storage,cp.binding(self.root/"PARENT_STARTED.json"))
            require(original_start["actual_identity"]["run_id"]==self.identity["run_id"]
                and original_start["actual_identity"]["api_job_id"]==self.identity["api_job_id"],"SAME_ORIGINAL_FAILED_JOB")
        self.started=utc(start["actual_started_at"]);self.child_number=0

    def check(self):
        require(store.sha(store.canonical(self.go))==self.go_sha,"OWNER_ROOT_METADATA_CHANGED_DURING_OPERATION")
        validate_root(self.go,now=now_utc())
        total=[resource.getrusage(k) for k in (resource.RUSAGE_SELF,resource.RUSAGE_CHILDREN)]
        require(sum(x.ru_utime+x.ru_stime for x in total)<=LIMITS["CPU_seconds"],"WEEKLY_AGGREGATE_CPU_CAP")

    def fresh_operations_proof(self):
        """A long numerical phase cannot extend an earlier metadata proof."""
        self.check()
        if self.go["operation"]=="RECURRING_CAPTURE":
            self.operations_proof=operations_authority.current(self.env,store.canonical(self.go),ROOT)
        return self.operations_proof

    def native(self, version, phase, request, *, zero_fields=()):
        self.check()
        return dict(schema_version=version+"-native-authority",phase=phase,
            request_sha256=store.sha(store.canonical(request)),owner_root_go_sha256=self.go_sha,
            repository=store.REPO,source_sha=self.identity["source_sha"],run_id=self.identity["run_id"],run_attempt=1,
            job_id=self.identity["job_id"],workflow_ref=self.identity["workflow_ref"],api_job_id=self.identity["api_job_id"],
            issued_at_utc=now_utc().isoformat(),expires_at_utc=self.go["expires_at_utc"],
            actual_actions_api_authenticated=True,owner_root_checked=True,fits=0,public_release=False,
            **{f:0 for f in zero_fields})

    def child(self, tool, phase, request, authority, namespace, seconds):
        self.child_number+=1;name=f"{self.child_number:02}-{phase}"
        ref=write(self.storage,self.root/"requests"/(name+".json"),request)
        env=dict(self.env,**{namespace+"_JSON":store.canonical(authority).decode(),namespace+"_SHA256":store.sha(store.canonical(authority)),
            "AUDIT_WEEKLY_PARENT_PID":str(os.getpid())})
        command=[sys.executable,"-I","-B",str(ROOT/"tools"/(tool+".py")),phase,"--execute","--request",ref["path"],"--request-sha256",ref["sha256"]]
        # Each child installs its existing phase envelope. The parent allows
        # 4GiB-AS so it cannot accidentally prevent a valid numerical child.
        p=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        try:
            out,err=p.communicate(timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate()
            require(len(out)<=64 << 10 and len(err)<=64 << 10,"BOUNDED_PRIVATE_CHILD_STATUS")
            self.storage.write_bytes(self.root/"phase-status"/(name+".stdout"),out)
            self.storage.write_bytes(self.root/"phase-status"/(name+".stderr"),err)
            write(self.storage,self.root/"phase-status"/(name+".json"),dict(state="DEADLINE",exit_code=p.returncode,
                stdout_sha256=store.sha(out),stderr_sha256=store.sha(err),actual_completed_at=now_utc().isoformat()))
            raise store.StoreError("WEEKLY_CHILD_DEADLINE") from None
        require(len(out)<=64 << 10 and len(err)<=64 << 10,"BOUNDED_PRIVATE_CHILD_STATUS")
        # Child summaries contain fixed codes only. Retain original bytes
        # privately; never print arbitrary library text or partial forecasts.
        self.storage.write_bytes(self.root/"phase-status"/(name+".stdout"),out)
        self.storage.write_bytes(self.root/"phase-status"/(name+".stderr"),err)
        try: result=cp.strict_json(out)
        except Exception:
            # A signal, interpreter exit or malformed summary must retain the
            # actual return code even when there is no JSON child status.
            write(self.storage,self.root/"phase-status"/(name+".json"),dict(state="INVALID_CHILD_STATUS",exit_code=p.returncode,
                stdout_sha256=store.sha(out),stderr_sha256=store.sha(err),actual_completed_at=now_utc().isoformat()))
            raise store.StoreError("WEEKLY_CHILD_STATUS_INVALID") from None
        write(self.storage,self.root/"phase-status"/(name+".json"),dict(exit_code=p.returncode,status=result,actual_completed_at=now_utc().isoformat()))
        if p.returncode:
            code=result.get("reason")
            raise store.StoreError(code if type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}",code) else "WEEKLY_CHILD_FAILED")
        self.check();return result

    def claim(self):
        """A fixed root-dependent blob makes duplicate GO use detectable."""
        package=self.go["qualified_runtime"]
        class ClaimClient(archive.Client):
            def upload(self,name,body,*,reuse_completed=False):
                # GitHub's unique asset name is the atomic duplicate guard.
                # A payload that appeared after our census must not be reused.
                return super().upload(name,body,reuse_completed=False)
        client=ClaimClient(self.env.get("GITHUB_TOKEN"),self.identity["run_id"],source_sha=self.identity["source_sha"],
            journal=self.journal,job=self.job,operation="append",qualification=package["qualification"])
        client.authenticate_actions_job();client.bind(package["binding"])
        operations_authority.attach(client,self.operations_proof,self.env,store.canonical(self.go))
        archive.authenticate_qualification(client,package,self.go["pending_census"])
        body=store.canonical(dict(schema_version=VERSION+"-root-consumption",root_go_sha256=self.go_sha,maximum_dispatches=1,fits=0))
        assets,total=client.inventory()
        require(not any(a["name"]=="blob-"+store.sha(body)+".bin" for a in assets),"OWNER_ROOT_ALREADY_CONSUMED_NO_RETRY")
        require(total+len(body)+(32 << 10)<store.TOTAL_CAP and len(assets)+2<=store.MAX_ASSETS,"ROOT_CLAIM_CAPACITY")
        manifest=dict(schema_version="weekly-private-payload-v2",payload_kind="runtime_manifest",format="json",bytes=len(body),sha256=store.sha(body),source_policy_sha256=cp.POLICY_SHA)
        ref=store.append(client,body,manifest,package["qualification"])
        write(self.storage,self.root/"ROOT_CONSUMED.json",dict(descriptor=ref,actual_identity=cp.client_identity(client),actual_completed_at=now_utc().isoformat()))

    def recover_origin(self):
        request=origin.prepare_request(ROOT,self.go["original_selected_handoff"],cache=self.storage.cache,state_root=self.root/"state",output=self.root/"origin")
        request["approved"]=True
        a=self.native(origin.VERSION,"origin",request,zero_fields=("remote_writes","protected_outcome_reads"))
        self.child("audit_weekly_origin_v1","recover",request,a,"AUDIT_WEEKLY_ORIGIN_AUTHORITY",190)
        return cp.binding(self.root/"origin"/"ORIGIN_RESULT.json")

    def recover_models(self):
        request=dict(schema_version=VERSION+"-model-request",registration=retained_registration(self.go),cache=str(self.storage.cache),
            state_root=str(self.root/"state"),output=str(self.root/"retained"),code_pins=pins())
        a=self.native(VERSION,"models",request)
        self.child("audit_weekly_hosted_v1","models",request,a,"AUDIT_WEEKLY_NATIVE_AUTHORITY",430)
        return cp.binding(self.root/"retained"/"RESTORED.json")

    def recurring_prepare(self):
        """Recover the exact previous issue, then register a fresh capture.

        Qualified prior bodies are immutable inputs, never a replacement for
        fresh current-source acquisition. The worker validates the original
        canonical choice and rejects an unsupported previous grading state.
        """
        from . import audit_weekly_operations_worker_v1 as worker
        from . import audit_weekly_operations_restore_v1 as recovery
        from .operational_io import quota_downloader
        require(self.go["operation"]=="RECURRING_CAPTURE" and self.operations_proof is not None,
            "LIVE_RECURRING_CAPTURE_ROOT_REQUIRED")
        self.claim()
        prior_metadata=self.prior_public_metadata()
        request=dict(schema_version=recovery.VERSION+"-request",phase=recovery.PHASE,code_pins=pins(),
            limits=recovery.LIMITS,cache=str(self.storage.cache),state_root=str(self.root/"state"),
            output=str(self.root/recovery.PHASE),inputs={k:prior_metadata[k] for k in ("receipt","historical_source_sha256")})
        recovered=self.child("audit_weekly_operations_restore_v1",recovery.PHASE,request,
            self.native(VERSION,recovery.PHASE,request),"AUDIT_WEEKLY_NATIVE_AUTHORITY",190)
        retained_ref=recovered["retained_result"]
        retained_result=read_owned(self.storage,retained_ref)
        require(retained_result["current_root_go_sha256"]==self.go_sha
            and retained_result["validation"].get("qualified_selected") is True,
            "EXACT_AUTHENTICATED_PRIOR_CAPTURE_REQUIRED")
        models=self.recover_models()
        aliases=retained_result["aliases"]
        canonical=aliases.get("context/canonical_weekly_choice.json",aliases["runtime/WEEKLY_CHOICE.json"])
        original_choice_sha256=digest(read_owned(self.storage,canonical))
        calendar_root=self.storage.register_root(self.root/"current-calendar")
        started=now_utc()
        receipt=quota_downloader(self.storage)(calendar_root,"schedules.csv",worker.CALENDAR_URL,refresh_daily=False)
        require(receipt.get("status")=="acquired" and receipt.get("cache_reused") is False
            and not receipt.get("stale") and started<=utc(receipt["retrieved_utc"])<=now_utc(),
            "GENUINELY_FRESH_FULL_CALENDAR_REQUIRED")
        body=cp.binding(calendar_root/"schedules.csv")
        require(body["bytes"]<=worker.LIMITS["calendar_bytes"] and body["sha256"]==receipt["sha256"],
            "EXACT_FULL_CALENDAR_BODY_AND_RECEIPT")
        calendar=dict(body=body,receipt=cp.binding(calendar_root/"schedules.csv.receipt.json"))
        inputs=dict(retained_result=retained_ref,retained_models=models,calendar=calendar,
            canonical_weekly_choice_sha256=original_choice_sha256,
            capture_id=digest(dict(root_go_sha256=self.go_sha,canonical_weekly_choice_sha256=original_choice_sha256,
                stream="weekly-corrected-primary-player-game-v1")),previous_grade_snapshot=prior_metadata["previous_grade_snapshot"])
        request=dict(schema_version=worker.VERSION+"-request",phase=worker.PHASE,code_pins=pins(),limits=worker.LIMITS,
            cache=str(self.storage.cache),state_root=str(self.root/"state"),output=str(self.root/worker.OUTPUT_NAME),inputs=inputs)
        prepared=self.child("audit_weekly_operations_worker_v1",worker.PHASE,request,
            self.native(VERSION,worker.PHASE,request),"AUDIT_WEEKLY_NATIVE_AUTHORITY",190)
        manifest=read_owned(self.storage,prepared["manifest"])
        require(manifest["current_root_go_sha256"]==self.go_sha and manifest["current_values_used"] is False
            and manifest["no_reselection"] is manifest["no_cutoff_extension"] is True,
            "ACTUAL_PREVALUE_RECURRING_METADATA_REQUIRED")
        return retained_result,manifest

    def prior_public_metadata(self):
        """Exact registered public receipt/source, never a latest-feed query."""
        from . import audit_weekly_operations_v1 as operations
        from . import audit_weekly_discovery_v1 as discovery
        from . import audit_weekly_grade_history_v1 as history
        context=operations.context(self.go["effective_epoch"])
        require(self.operations_proof is not None,"LIVE_RECURRING_ROOT_REQUIRED")
        previous=context["previous_capture"]
        def content(path,ref,cap):
            url=store.API+"/contents/"+path+"?ref="+ref
            # Fixed repository, registered hash and fixed eight source names.
            # Metadata client rejects every method other than GET.
            self.client.allowed.add(url);value=self.client.json(url)
            require(type(value) is dict and value.get("type")=="file" and value.get("path")==path
                and value.get("encoding")=="base64" and type(value.get("size")) is int
                and 0<value["size"]<=cap,"BOUNDED_RECURRING_PUBLIC_METADATA_FILE")
            raw=base64.b64decode(value["content"].replace("\n",""),validate=True)
            from . import audit_weekly_controller_v1 as controller
            require(len(raw)==value["size"] and controller.blob_sha(raw)==value.get("sha"),
                "EXACT_IMMUTABLE_PUBLIC_METADATA_BLOB")
            return raw
        path="state/public/weekly-adaptive-v1/receipts/"+previous["feed_sha256"]+".json.gz"
        compressed=content(path,"lab-state",64 << 10)
        require(store.sha(compressed)==previous["receipt_sha256"],"EXACT_REGISTERED_PRIOR_COMPRESSED_RECEIPT")
        value=archive.unpack(compressed,64 << 10);plain=store.canonical(value)
        discovery.receipt(plain,store.sha(plain))
        require(value["feed_sha256"]==previous["feed_sha256"] and value["run_id"]!=self.identity["run_id"],
            "EXACT_PRIOR_FEED_FROM_DISTINCT_RUN")
        historical={name:store.sha(content(name,value["source_sha"],256 << 10))
            for name in weekly_retained.HISTORICAL_FILES}
        folder=self.storage.register_root(self.root/"operations-public-metadata")
        self.storage.write_bytes(folder/"PUBLIC_RECEIPT.json.gz",compressed)
        receipt_ref=cp.binding(folder/"PUBLIC_RECEIPT.json.gz")
        checkpoint=history.previous_checkpoint(self.go)
        pair=None
        if checkpoint is not None:
            if checkpoint.get("schema_version")==history.LOCATOR_REF:
                history.require_latest(self.client,checkpoint)
                path=history.LOCATOR_ROOT+"/"+checkpoint["path"]
            else:path="state/controller-v1/grade-checkpoints/"+previous["feed_sha256"]+".json.gz"
            packed=content(path,"lab-state",history.LIMITS["sidecar_bytes"])
            require(store.sha(packed)==checkpoint["sha256"],"EXACT_ROOT_PRIOR_GRADING_SIDECAR_HASH_BEFORE_VALUES")
            self.storage.write_bytes(folder/"PREVIOUS_GRADE_CHECKPOINT.json.gz",packed)
            pair=dict(sidecar=cp.binding(folder/"PREVIOUS_GRADE_CHECKPOINT.json.gz"),public_receipt=receipt_ref)
        return dict(receipt=receipt_ref,historical_source_sha256=historical,previous_grade_snapshot=pair)

    def metadata(self, origin_ref, retained_ref):
        old=read_owned(self.storage,origin_ref);restored=read_owned(self.storage,retained_ref)
        read=lambda role,raw=False:read_owned(self.storage,old[role],raw=raw)
        replay=retained_registration(self.go)["origin"]["replay_catalog"]
        e=epoch.prepare_epoch(read("original_choice",True),read("original_terminal_witness"),read("original_slate"),
            read("original_catalog"),read("original_policy"),replay,history_binding=old["history_binding"],
            effective_controls=dict(R0=reference.control_spec()))
        eref=write(self.storage,self.root/"metadata"/"EPOCH.json",e.document)
        actual_write=now_utc()
        cas=epoch.owned_cas_readback(self.storage,dict(epoch=eref),dict(epoch=e.document),scope="EPOCH_METADATA",written_at=actual_write)
        registration=dict(schema_version=epoch.VERSION+"-registration-completion",epoch_sha256=e.sha256,catalog_sha256=digest(e.document["catalog"]),
            selection_recipe_sha256=digest(e.document["selection_recipe"]),persisted_completed_at=cas["readback_completed_at"],
            owner_registration_sha256=self.go_sha,qualified_artifact_restore=dict(scope="EFFECTIVE18_MODELS_ONLY",proof_sha256=digest(restored["proofs"]),
                replay_catalog_sha256=digest(replay),model_pairs=18),metadata_cas_readback=cas,metadata_remote_durability_qualified=False,current_values_used=False,fits=0)
        regref=write(self.storage,self.root/"metadata"/"EPOCH_REGISTRATION.json",registration)
        registered=epoch.bind_registration(e,registration,now=now_utc())
        body=read_owned(self.storage,old["original_source_pairs"]["schedules.csv"]["body"],32 << 20,raw=True)
        schedule=schedule_metadata(body,season=e.origin["slate"]["season"],week=e.origin["slate"]["week"])
        observed=now_utc()
        cutoffs={r["game_id"]:(utc(r["kickoff_utc"])-timedelta(seconds=self.go["cutoff_lead_seconds"])).isoformat()
            for r in schedule if utc(r["kickoff_utc"])>observed}
        choice=epoch.continue_week(registered,schedule,cutoffs)
        cref=write(self.storage,self.root/"metadata"/"CHOICE.json",choice.document)
        return dict(epoch=eref,epoch_registration=regref,original_choice=old["original_choice"],original_completion=old["original_terminal_witness"],
            original_slate=old["original_slate"],original_catalog=old["original_catalog"],original_policy=old["original_policy"],choice=cref,retained_restore=retained_ref)

    def register_publication(self, inputs):
        if self.publication is None:return None
        policy=self.publication["policy"]
        require(inputs["original_choice"]["sha256"]==policy["origin_choice_sha256"],
            "ROOT_PUBLICATION_MUST_BIND_RECOVERED_ORIGINAL_CHOICE")
        ref=write(self.storage,self.root/"metadata"/"PUBLIC_POLICY.json",policy)
        require(ref["sha256"]==self.go["publication_registration"]["policy_sha256"],
            "ORIGINAL_APPROVED_PUBLIC_POLICY_ARCHIVE_BYTES")
        return ref

    def capture(self, inputs, origin_ref):
        from tools.audit_weekly_runtime_v1 import template
        old=read_owned(self.storage,origin_ref)
        request=template();request.update(approved=True,cache=str(self.storage.cache),state_root=str(self.root/"state"),inputs=inputs,
            history_binding=old["history_binding"],config=self.go["source_config"],historical_sources=old["historical_sources"])
        outputs={"prepare":self.root/"prepared","acquire":self.root/"source","infer":self.root/"runtime"}
        for phase in ("prepare","acquire","infer"):
            request["output"]=str(outputs[phase])
            self.child("audit_weekly_runtime_v1",phase,request,self.native(runtime.VERSION,phase,request),"AUDIT_WEEKLY_RUNTIME_AUTHORITY",430)
            if phase=="prepare":
                request["prepared"]=cp.binding(outputs[phase]/"PREPARED.json")
                request["choice_completion"]=read_owned(self.storage,request["prepared"])["choice_completion"]
            elif phase=="acquire":request["source"]=cp.binding(outputs[phase]/"SOURCE_FINISHED.json")
        return request

    def reference(self, inputs, request, *, previous_state=None, previous_state_aliases=None):
        payload=dict(schema_version=VERSION+"-reference-request",inputs=inputs,history_binding=request["history_binding"],
            config=self.go["source_config"],cache=str(self.storage.cache),state_root=str(self.root/"state"),
            prepared=request["prepared"],source=request["source"],runtime_root=str(self.root/"runtime"),
            output=str(self.root/"reference"),repository=self.env["NFL_R0_SOURCE_REPOSITORY"],code_pins=pins())
        if self.go["operation"]=="RECURRING_CAPTURE":
            require(previous_state is not None and type(previous_state_aliases) is dict,
                "QUALIFIED_PRIOR_ORIGINAL_R0_STATE_REQUIRED")
            payload.update(previous_state=previous_state,previous_state_aliases=previous_state_aliases)
        else:require(previous_state is previous_state_aliases is None,"NO_IMPLICIT_REFERENCE_STATE_OVERRIDE")
        a=self.native(VERSION,"reference",payload)
        self.child("audit_weekly_hosted_v1","reference",payload,a,"AUDIT_WEEKLY_NATIVE_AUTHORITY",430)
        return cp.binding(self.root/"reference"/"CAPTURE_COMPLETE.json")

    def archive_request(self, phase, *, context=None, r0=None, handoff=None, reader_handoff=None):
        from tools.audit_weekly_archive_v1 import template
        local=self.root/("archive-"+phase)
        request=template();request.update(approved=True,phase=phase,jobs=JOBS,cache=str(self.storage.cache),
            state_root=str(self.root/"state"),local_root=str(local),output=str(local/"transport"),qualified_runtime=self.package_ref,
            pending_census=self.go["pending_census"],runtime_root=str(self.root/"runtime"),context=context,r0=r0,
            handoff=handoff,reader_handoff=reader_handoff)
        return request

    def archive_call(self, phase, request):
        result=self.child("audit_weekly_archive_v1",phase,request,self.native(archive.VERSION,phase,request),"AUDIT_WEEKLY_ARCHIVE_AUTHORITY",190)
        return result

    def grading_phase(self, phase, restored, *, handoff=None, previous_history=None, planning=None):
        """Use independent guarded workers; grading failure stops export."""
        from . import audit_weekly_operations_grade_v1 as grading
        from . import audit_weekly_grade_checkpoint_v1 as checkpoint
        require(self.go["operation"]=="RECURRING_CAPTURE" and phase in grading.PHASES,
            "EXPLICIT_RECURRING_GRADING_PHASE_REQUIRED")
        inputs=dict(archive_restored=restored)
        if phase==grading.PHASES[0]:
            require(handoff is None,"NO_PRETENDED_PRIOR_GRADING_STATE")
            inputs["previous_snapshot"]=None
        else:
            checkpoint.safe_handoff(handoff)
            require(handoff["current_root_go_sha256"]==self.go_sha,"EXACT_CURRENT_GRADING_HANDOFF_ROOT")
            inputs["checkpoint_handoff"]=handoff
        request=dict(schema_version=grading.VERSION+"-request",phase=phase,code_pins=pins(),limits=grading.LIMITS,
            cache=str(self.storage.cache),state_root=str(self.root/"state"),output=str(self.root/phase),inputs=inputs)
        if previous_history is not None:
            require(self.go["effective_epoch"].get("plan",{}).get("kind")=="GRADE_ONLY", "EXPLICIT_GRADE_ONLY_HISTORY")
            request["schema_version"]=grading.VERSION+"-request-v2"
            inputs["previous_history"]=previous_history
            if planning is not None:
                from . import audit_weekly_grade_history_v1 as history
                require(self.go["effective_epoch"]["schema_version"]==history.CONTEXT_V4,"EXPLICIT_V4_PLANNING_INPUT")
                request["schema_version"]=grading.VERSION+"-request-v3"
                inputs["planning"]=planning
        result=self.child("audit_weekly_operations_grade_v1",phase,request,self.native(VERSION,phase,request),
            "AUDIT_WEEKLY_NATIVE_AUTHORITY",190)
        expected="PRIVATE_GRADE_APPENDED_FRESH_READER_REQUIRED" if phase==grading.PHASES[0] \
            else "PRIVATE_OPERATIONAL_GRADING_FRESH_READER_VERIFIED"
        require(result["state"]==expected and result["successful_forecast"] is result["public_release"] is False,
            "REAL_OPERATIONAL_GRADING_PHASE_REQUIRED")
        if phase==grading.PHASES[0]:
            body=checkpoint.safe_handoff(result["checkpoint_handoff"])
            require(result["checkpoint_handoff"]["current_root_go_sha256"]==self.go_sha,
                "EXACT_APPENDED_GRADING_HANDOFF_ROOT")
            with open(self.env["GITHUB_OUTPUT"],"a") as stream:
                stream.write("grade_checkpoint_handoff_json="+body.decode()+"\n"
                    "grade_checkpoint_handoff_sha256="+store.sha(body)+"\n")
                stream.flush();os.fsync(stream.fileno())
        return result

    def grade_only(self, *, handoff=None):
        """Fresh native original-body GETs in each grading job; no inference/feed.

        The returned checkpoint is private. It cannot masquerade as the
        per-feed public sidecar consumed by the current scheduled Parent.
        """
        from . import audit_weekly_operations_restore_v1 as recovery
        from . import audit_weekly_grade_checkpoint_v1 as checkpoint
        from . import audit_weekly_operations_v1 as operations
        value=operations.context(self.go["effective_epoch"])
        require(value.get("plan",{}).get("kind")=="GRADE_ONLY" and self.phase in {"restore","consume"},
            "EXPLICIT_CURRENT_GRADE_ONLY_JOB_REQUIRED")
        metadata=self.prior_public_metadata()
        require(metadata["previous_grade_snapshot"] is not None,"QUALIFIED_ORIGINAL_PRIMARY_HISTORY_REQUIRED")
        phase=recovery.PHASES[1 if self.phase=="restore" else 2]
        request=dict(schema_version=recovery.VERSION+"-request",phase=phase,code_pins=pins(),limits=recovery.LIMITS,
            cache=str(self.storage.cache),state_root=str(self.root/"state"),output=str(self.root/phase),
            inputs={k:metadata[k] for k in ("receipt","historical_source_sha256")})
        recovered=self.child("audit_weekly_operations_restore_v1",phase,request,self.native(VERSION,phase,request),
            "AUDIT_WEEKLY_NATIVE_AUTHORITY",190)
        require(recovered["state"]=="PRIVATE_PRIOR_CAPTURE_RECOVERED_FOR_RECURRING", "ACTUAL_GRADE_ONLY_ORIGINAL_RECOVERY")
        restored=read_owned(self.storage,recovered["retained_result"])
        aliases=restored["aliases"]
        canonical=read_owned(self.storage,aliases.get("context/canonical_weekly_choice.json",aliases["runtime/WEEKLY_CHOICE.json"]))
        require((canonical["slate"]["season"],canonical["slate"]["week"])==(value["plan"]["season"],value["plan"]["week"])
            and all(utc(t)<=now_utc() for t in canonical["slate"]["game_cutoffs"].values()),
            "GRADE_ONLY_ORIGINAL_FROZEN_CAPTURE_WINDOW_MUST_HAVE_ELAPSED")
        planning=None
        if value["schema_version"]==operations.CONTEXT_V4:
            from . import audit_weekly_grade_history_v1 as history
            raw=self.env.get("AUDIT_WEEKLY_HISTORY_PLANNING_JSON","").encode()
            require(0<len(raw)<=32<<10 and store.sha(raw)==self.env.get("AUDIT_WEEKLY_HISTORY_PLANNING_SHA256"),
                "EXACT_PRODUCER_HISTORY_PLANNING_OUTPUT")
            marker=cp.strict_json(raw)
            require(type(marker) is dict and set(marker)=={"root_go_sha256","planning"}
                and marker["root_go_sha256"]==self.go_sha,"CLOSED_SAME_ROOT_HISTORY_PLANNING_OUTPUT")
            seed=history.validate_planning(marker["planning"])
            require(digest(seed["current"]["schedule"])==value["plan"]["calendar_sha256"]
                and seed["current"]["canonical_choice_sha256"]==digest(canonical),"ORIGINAL_CANONICAL_PLANNING_ONLY")
            planning=write(self.storage,self.root/"grade-only-planning/HISTORY_PLANNING.json",seed)
        result=self.grading_phase("operations-grade-write" if self.phase=="restore" else "operations-grade-read",
            recovered["retained_result"],handoff=handoff,previous_history=metadata["previous_grade_snapshot"],
            **({"planning":planning} if planning is not None else {}))
        evidence=None
        if self.phase=="consume":evidence=self.retain_grade_only_evidence(result["manifest"])
        self.check()
        return dict(state="PRIVATE_GRADE_ONLY_APPENDED_FRESH_READER_REQUIRED" if self.phase=="restore"
            else "PRIVATE_GRADE_ONLY_FRESH_READER_VERIFIED",grading=result,
            checkpoint_handoff=result.get("checkpoint_handoff",handoff),fits=0,public_release=False,successful_forecast=False,
            evidence=evidence,public_feed_written=False,
            scheduled_parent_discoverable=bool(evidence and evidence.get("scheduled_parent_discoverable")))

    def publish_history_locator(self, envelope, handoff, proof, descriptor, producer, *, anchor, kind, folder, append_client):
        """Publish metadata only. Later Parent requires the completed API run."""
        from . import audit_weekly_grade_history_v1 as history
        from .audit_weekly_delivery_v1 import quiet_publisher
        from .operational_io import operational_io
        from tools import persist_state
        require((self.go.get("effective_epoch") or {}).get("schema_version")==history.CONTEXT_V4
            and envelope["root_go"]==self.go,"EXACT_CURRENT_ROOT_HISTORY_ENVELOPE")
        require(kind==("GRADING_ONLY" if self.go["effective_epoch"]["plan"]["kind"]=="GRADE_ONLY" else "CAPTURE_AND_GRADE")
            and (kind!="GRADING_ONLY" or anchor==self.go["effective_epoch"]["previous_capture"]),"EXACT_NONFORECAST_LOCATOR_KIND_AND_ORIGINAL_ANCHOR")
        require(isinstance(append_client,archive.Client) and append_client.operation=="append"
            and cp.client_identity(append_client)==producer and producer["job_id"]==JOBS["consume"],
            "ACTUAL_SAME_JOB_NATIVE_EVIDENCE_APPENDER_REQUIRED")
        # Reuse the just-authenticated native appender and its original finite
        # budget. Runner's initial metadata client may already be 180s old.
        jobs=archive.jobs_for(append_client)
        refs={}
        for role,name in JOBS.items():
            matches=[j for j in jobs if j.get("name")==name and j.get("head_sha")==self.identity["source_sha"]
                and j.get("run_id")==int(self.identity["run_id"])]
            require(len(matches)==1,"ACTUAL_CURRENT_HISTORY_THREE_JOB_IDENTITIES")
            j=matches[0]
            require((j.get("status")=="in_progress" and j.get("conclusion") is None) if role=="consume"
                else (j.get("status")=="completed" and j.get("conclusion")=="success"),"ORIGINAL_HISTORY_JOB_PHASES")
            refs[role]=dict(job_id=name,api_job_id=j["id"])
        cohort=dict(schema_version=history.LOCATOR_VERSION+"-cohort",kind=kind,repository=store.REPO,
            source_sha=self.identity["source_sha"],run_id=self.identity["run_id"],root_go_sha256=self.go_sha,
            workflow_sha256=self.go["code_pins"][".github/workflows/lab.yml"],epoch_sha256=handoff["epoch_sha256"],
            feed_sha256=anchor["feed_sha256"],jobs=refs,root_issued_at_utc=self.go["issued_at_utc"],
            verified_at=proof["known_by_at"],created_at=now_utc().isoformat(),fits=0,public_release=False,successful_forecast=False)
        value=history.locator_document(anchor,cohort,handoff,proof,descriptor,producer,envelope["planning"],code_pins=self.go["code_pins"])
        encoded=gzip.compress(store.canonical(value),mtime=0)
        require(len(encoded)<=history.LIMITS["sidecar_bytes"],"BOUNDED_PUBLIC_HISTORY_LOCATOR")
        name=history.LOCATOR_ROOT.removeprefix("state/")+"/"+history.locator_filename(value)
        public_state=self.storage.register_root(folder/"history-public-state")
        self.storage.write_bytes(public_state/name,encoded)
        write(self.storage,folder/"LOCATOR_INTENT.json",dict(path=name,sha256=store.sha(encoded),
            evidence_descriptor_sha256=store.sha(store.canonical(descriptor)),public_feed_written=False))
        self.check()
        with quiet_publisher(ROOT),operational_io(self.storage,run_root=ROOT/"runs"):
            persist_state.persist(ROOT,public_state,storage=self.storage,
                policy_path=ROOT/"config/operational-source-policy-v2.json",files={name:store.sha(encoded)})
        self.check()
        return dict(path=name,sha256=store.sha(encoded))

    def retain_grade_only_evidence(self, manifest_ref):
        """Retain the original reader evidence privately without a feed receipt."""
        from . import audit_weekly_grade_history_v1 as history,audit_weekly_grade_checkpoint_v1 as checkpoint
        self.check()
        require(self.phase=="consume" and self.go["effective_epoch"]["plan"]["kind"]=="GRADE_ONLY",
            "EXPLICIT_GRADE_ONLY_EVIDENCE_APPEND")
        report=read_owned(self.storage,manifest_ref,128 << 10)
        require(report["schema_version"]=="audit-weekly-operations-grade-v1-read"
            and report["state"]=="PRIVATE_OPERATIONAL_GRADING_FRESH_READER_VERIFIED"
            and report["root_go_sha256"]==self.go_sha and report["fits"]==0
            and report["public_release"] is report["successful_forecast"] is False,
            "ORIGINAL_GRADE_ONLY_NATIVE_READ_MANIFEST")
        handoff=report["checkpoint_handoff"];checkpoint.safe_handoff(handoff)
        proof=read_owned(self.storage,report["proof"],128 << 10)
        require(proof==report["grade_read_proof"] and handoff["current_root_go_sha256"]==self.go_sha
            and proof["snapshot_sha256"]==handoff["snapshot_sha256"]
            and proof["restored_body_sha256"]==handoff["body_sha256"]
            and all(proof["reader"][k]==self.identity[k] for k in ("repository","run_id","source_sha","job_id","api_job_id"))
            and proof["reader"]["job_id"]==JOBS["consume"], "SAME_CURRENT_GRADE_ONLY_READER")
        body=read_owned(self.storage,report["evidence_envelope"],history.LIMITS["envelope_bytes"],raw=True)
        envelope=history._unpack(body,history.LIMITS["envelope_bytes"])
        modern=(self.go.get("effective_epoch") or {}).get("schema_version")==history.CONTEXT_V4
        require(set(envelope)==(history.ENVELOPE_V2_KEYS if modern else history.ENVELOPE_KEYS)
            and envelope["schema_version"]==(history.LOCATOR_VERSION if modern else history.VERSION)+"-evidence-envelope"
            and envelope["handoff_sha256"]==store.sha(checkpoint.safe_handoff(handoff))
            and envelope["grade_read_proof"]==proof,"COMPLETE_ORIGINAL_GRADE_ONLY_READER_EVIDENCE")
        folder=self.storage.register_root(self.root/"grade-only-evidence")
        intent=dict(schema_version="audit-weekly-grade-only-evidence-v1",root_go_sha256=self.go_sha,
            previous_capture=self.go["effective_epoch"]["previous_capture"],evidence_sha256=store.sha(body),
            checkpoint_handoff=handoff,grade_read_proof=proof,fits=0,public_release=False,successful_forecast=False)
        write(self.storage,folder/"APPEND_INTENT.json",intent)
        client=self.failure_client("append")
        assets,total=client.inventory()
        require(total+len(body)+cp.ENTRY_CAP<=store.TOTAL_CAP and client.inventory_slots+2<=store.MAX_ASSETS,
            "GRADING_EVIDENCE_APPEND_QUOTA_BEFORE_POST")
        self.check()
        descriptor=store.append(client,body,cp.payload(body),self.go["qualified_runtime"]["qualification"])
        identity=cp.client_identity(client)
        require(all(identity[k]==self.identity[k] for k in ("repository","run_id","source_sha","job_id","api_job_id")),
            "ACTUAL_CURRENT_GRADE_ONLY_EVIDENCE_APPEND")
        ref=write(self.storage,folder/"APPENDED.json",dict(intent,descriptor=descriptor,producer=identity,
            actual_completed_at=now_utc().isoformat()))
        self.check()
        locator=None
        if modern:locator=self.publish_history_locator(envelope,handoff,proof,descriptor,identity,
            anchor=self.go["effective_epoch"]["previous_capture"],kind="GRADING_ONLY",folder=folder,append_client=client)
        return dict(receipt=ref,evidence_descriptor_sha256=store.sha(store.canonical(descriptor)),locator=locator,
            public_feed_written=False,scheduled_parent_discoverable=modern)

    def grading_delivery(self, manifest_ref, public_receipt):
        """Append original reader evidence, then publish its closed locator.

        This runs only after the actual guarded grade-read child succeeds and
        before delivery publishes either the forecast feed or its receipt. An
        orphan locator from a later feed failure conveys no successful run.
        """
        from . import audit_weekly_grade_history_v1 as history
        from . import audit_weekly_grade_checkpoint_v1 as checkpoint
        from .audit_weekly_delivery_v1 import quiet_publisher
        from tools import persist_state
        self.check()
        require(self.phase=="consume" and self.go["operation"]=="RECURRING_CAPTURE"
            and self.go["publication"] is True,"CURRENT_RECURRING_EXPORT_GRADING_REQUIRED")
        report=read_owned(self.storage,manifest_ref,128 << 10)
        require(report["schema_version"]=="audit-weekly-operations-grade-v1-read"
            and report["state"]=="PRIVATE_OPERATIONAL_GRADING_FRESH_READER_VERIFIED"
            and report["root_go_sha256"]==self.go_sha
            and report["fits"]==0 and report["public_release"] is report["successful_forecast"] is False,
            "ORIGINAL_NATIVE_GRADE_READ_MANIFEST_REQUIRED")
        handoff=report["checkpoint_handoff"];checkpoint.safe_handoff(handoff)
        proof=report["grade_read_proof"]
        require(handoff["current_root_go_sha256"]==public_receipt["root_go_sha256"]==self.go_sha
            and handoff["epoch_sha256"]==public_receipt["epoch_sha256"]
            and proof==read_owned(self.storage,report["proof"],128 << 10)
            and public_receipt["jobs"]["restore"]=={k:proof["producer"][k] for k in ("job_id","api_job_id")}
            and public_receipt["jobs"]["consume"]=={k:proof["reader"][k] for k in ("job_id","api_job_id")},
            "SAME_NATIVE_GRADING_AND_FEED_COHORT")
        envelope_ref=report["evidence_envelope"]
        body=read_owned(self.storage,envelope_ref,history.LIMITS["envelope_bytes"],raw=True)
        envelope=history._unpack(body,history.LIMITS["envelope_bytes"])
        modern=(self.go.get("effective_epoch") or {}).get("schema_version")==history.CONTEXT_V4
        require(set(envelope)==(history.ENVELOPE_V2_KEYS if modern else history.ENVELOPE_KEYS)
            and envelope["schema_version"]==(history.LOCATOR_VERSION if modern else history.VERSION)+"-evidence-envelope"
            and envelope["handoff_sha256"]==store.sha(checkpoint.safe_handoff(handoff))
            and envelope["grade_read_proof"]==proof,
            "COMPLETE_ORIGINAL_NATIVE_READ_EVIDENCE_REQUIRED")
        folder=self.storage.register_root(self.root/"grading-delivery")
        write(self.storage,folder/"APPEND_INTENT.json",dict(schema_version="audit-weekly-grading-delivery-v1-intent",
            root_go_sha256=self.go_sha,feed_sha256=public_receipt["feed_sha256"],evidence_sha256=envelope_ref["sha256"],fits=0))
        client=self.failure_client("append")  # Actual same-job API auth and fresh Root authority.
        assets,total=client.inventory()
        require(total+len(body)+cp.ENTRY_CAP<=store.TOTAL_CAP and client.inventory_slots+2<=store.MAX_ASSETS,
            "GRADING_EVIDENCE_APPEND_QUOTA_BEFORE_POST")
        self.check()
        descriptor=store.append(client,body,cp.payload(body),self.go["qualified_runtime"]["qualification"])
        current=cp.client_identity(client)
        require(current["job_id"]==JOBS["consume"] and current["api_job_id"]==self.identity["api_job_id"]
            and current["source_sha"]==self.go["source_sha"] and current["run_id"]==self.identity["run_id"],
            "ACTUAL_CURRENT_EXPORT_EVIDENCE_APPEND_REQUIRED")
        write(self.storage,folder/"APPENDED.json",dict(descriptor=descriptor,producer=current,
            evidence_sha256=envelope_ref["sha256"],actual_completed_at=now_utc().isoformat()))
        sidecar=history.sidecar_document(public_receipt,handoff,proof,descriptor,current)
        encoded=gzip.compress(store.canonical(sidecar),mtime=0)
        require(len(encoded)<=history.LIMITS["sidecar_bytes"],"BOUNDED_PUBLIC_GRADING_LOCATOR")
        public_state=self.storage.register_root(folder/"public-state")
        name="controller-v1/grade-checkpoints/"+public_receipt["feed_sha256"]+".json.gz"
        self.storage.write_bytes(public_state/name,encoded)
        self.check()
        # The generic reviewed-map publisher preserves all existing paths and
        # verifies this one owned file in the remote commit. The existing
        # two-file forecast publisher and its schema stay unchanged.
        from .operational_io import operational_io
        with quiet_publisher(ROOT),operational_io(self.storage,run_root=ROOT/"runs"):
            persist_state.persist(ROOT,public_state,storage=self.storage,
                policy_path=ROOT/"config/operational-source-policy-v2.json",files={name:store.sha(encoded)})
        self.check()
        if modern:self.publish_history_locator(envelope,handoff,proof,descriptor,current,
            anchor=dict(feed_sha256=public_receipt["feed_sha256"],receipt_sha256=store.sha(gzip.compress(store.canonical(public_receipt),mtime=0))),
            kind="CAPTURE_AND_GRADE",folder=folder,append_client=client)
        return dict(schema_version="audit-weekly-grading-delivery-v1",feed_sha256=public_receipt["feed_sha256"],
            sidecar_sha256=store.sha(encoded),sidecar_path=name,evidence_descriptor_sha256=store.sha(store.canonical(descriptor)))

    def controller_registration(self, phase):
        """Prepare the native seal; the whole run must finish before adoption."""
        from . import audit_weekly_controller_registration_v1 as registration
        require(self.go["operation"]=="CONTROLLER_REGISTRATION" and phase in registration.PHASES,
            "EXPLICIT_OWNER_CONTROLLER_REGISTRATION_REQUIRED")
        role,folder=registration.PHASES[phase]
        require(self.phase==role,"EXACT_CONTROLLER_REGISTRATION_JOB_ROLE")
        if role=="produce":self.claim()
        names=registration.INPUT_KEYS[phase]
        inputs={}
        for name in sorted(names):
            if name=="readiness":inputs[name]=None;continue
            prefix="AUDIT_WEEKLY_CONTROLLER_"+name.upper()
            raw=self.env.get(prefix+"_JSON","").encode()
            require(0<len(raw)<=64 << 10 and store.sha(raw)==self.env.get(prefix+"_SHA256"),
                "EXACT_CONTROLLER_NATIVE_STAGE_HANDOFF")
            document=cp.strict_json(raw)
            require(store.canonical(document)==raw,"CANONICAL_CONTROLLER_NATIVE_STAGE_HANDOFF")
            inputs[name]=write(self.storage,self.root/"controller-inputs"/(name+".json"),document)
        request=registration.build_request(phase,code_pins=pins(),cache=self.storage.cache,state_root=self.root/"state",
            output=self.root/folder,inputs=inputs)
        result=self.child("audit_weekly_controller_registration_v1",phase,request,self.native(VERSION,phase,request),
            "AUDIT_WEEKLY_NATIVE_AUTHORITY",190)
        expected=set(registration.OUTPUT_FILES[phase])
        require(result["phase"]==phase and set(result["artifacts"])==expected
            and result["public_root"] is result["registry_created"] is result["registration_run_completed"] is False,
            "ACTUAL_NATIVE_CONTROLLER_STAGE_REQUIRED")
        public_metadata={}
        with open(self.env["GITHUB_OUTPUT"],"a") as stream:
            for name,ref in sorted(result["artifacts"].items()):
                require(Path(ref["path"])==self.root/folder/registration.OUTPUT_FILES[phase][name],
                    "EXACT_CLOSED_CONTROLLER_ARTIFACT_OUTPUT")
                value=read_owned(self.storage,ref,64 << 10,raw=True)
                require(value==store.canonical(cp.strict_json(value)) and b"\n" not in value,
                    "CANONICAL_CONTROLLER_ARTIFACT_OUTPUT")
                stream.write("controller_"+name+"_json="+value.decode()+"\n"
                    "controller_"+name+"_sha256="+store.sha(value)+"\n")
                if name=="safe_seal":stream.write("controller_safe_seal_path="+ref["path"]+"\n")
                if name in {"registration","locator_registration"}:public_metadata[name]=cp.strict_json(value)
            stream.flush();os.fsync(stream.fileno())
        summary=dict(state=result["state"],phase=phase,fits=0,public_release=False,successful_forecast=False,
            public_root=False,registry_created=False,registration_run_completed=False)
        if role=="consume":
            require(set(public_metadata)=={"registration","locator_registration"},"COMPLETE_CLEARED_REGISTRATION_METADATA")
            summary.update(public_metadata_scope="CLEARED_CONTROLLER_REGISTRATION_METADATA_ONLY",**public_metadata)
        require(len(store.canonical(summary))<=64 << 10,"CLOSED_PUBLIC_REGISTRATION_SUMMARY_BOUND")
        return summary

    def produce(self):
        if self.go["operation"]=="ORIGIN_METADATA_ONLY":
            ref=self.recover_origin();old=read_owned(self.storage,ref)
            witness=read_owned(self.storage,old["original_terminal_witness"])
            choice=read_owned(self.storage,old["original_choice"])
            slate=read_owned(self.storage,old["original_slate"])
            return dict(state="ORIGINAL_METADATA_RECOVERED_AND_VERIFIED",original_choice_sha256=old["original_choice"]["sha256"],
                original_choice_actual_frozen_at=choice["actual_frozen_at"],original_declared_weekly_deadline=slate["weekly_deadline_utc"],
                original_decision_write_clock=witness["actual_decision_persist_completed_at"],
                new_witness_created_at=witness["created_at_utc"],raw_original_completion_file_retained=False,
                source_sha=self.identity["source_sha"],run_id=self.identity["run_id"],fits=0,model_decodes=0,forecasts=0,remote_writes=0,public_release=False)
        if self.go["operation"]=="CONTROLLER_REGISTRATION":
            return self.controller_registration("controller-template-write")
        recurring=self.go["operation"]=="RECURRING_CAPTURE"
        if recurring:
            prior,operations=self.recurring_prepare()
            if operations.get("execution_plan",{}).get("kind")=="GRADE_ONLY":
                require(self.go["effective_epoch"].get("plan",{}).get("kind")=="GRADE_ONLY", "EXPLICIT_GRADE_ONLY_ROOT_BEFORE_NO_FEED")
                self.check()
                # Job coordination metadata only. Every following job still
                # obtains its own live Root/API proof and restores originals.
                marker=dict(schema_version=VERSION+"-grade-only-plan",root_go_sha256=self.go_sha,
                    plan=operations["execution_plan"],fits=0,public_release=False,successful_forecast=False)
                encoded=store.canonical(marker)
                require(len(encoded)<=4 << 10,"BOUNDED_GRADE_ONLY_JOB_CONTROL")
                with open(self.env["GITHUB_OUTPUT"],"a") as stream:
                    stream.write("grade_only_plan_json="+encoded.decode()+"\n"
                        "grade_only_plan_sha256="+store.sha(encoded)+"\n")
                    stream.flush();os.fsync(stream.fileno())
                if "history_planning" in operations:
                    from . import audit_weekly_grade_history_v1 as history
                    history.validate_planning(operations["history_planning"])
                    encoded=store.canonical(dict(root_go_sha256=self.go_sha,planning=operations["history_planning"]))
                    require(len(encoded)<=32<<10,"BOUNDED_PUBLIC_SAFE_HISTORY_PLANNING_OUTPUT")
                    with open(self.env["GITHUB_OUTPUT"],"a") as stream:
                        stream.write("history_planning_json="+encoded.decode()+"\n"+"history_planning_sha256="+store.sha(encoded)+"\n")
                        stream.flush();os.fsync(stream.fileno())
                return dict(state="ORIGINAL_CAPTURE_RECOVERED_GRADE_ONLY_NO_NEW_FORECAST",execution_plan=operations["execution_plan"],
                    fits=0,public_release=False,successful_forecast=False,public_feed_written=False)
            origin_ref=self.recover_origin()
            inputs=operations["inputs"];retained_ref=inputs["retained_restore"]
        else:
            self.claim()
            origin_ref=self.recover_origin()
            retained_ref=self.recover_models()
            inputs=self.metadata(origin_ref,retained_ref)
        policy_ref=self.register_publication(inputs)
        request=self.capture(inputs,origin_ref)
        r0=self.reference(inputs,request,previous_state=prior["previous_state"] if recurring else None,
            previous_state_aliases=prior["previous_state_aliases"] if recurring else None)
        context=dict(epoch=inputs["epoch"],epoch_registration=inputs["epoch_registration"],original_choice=inputs["original_choice"],
            origin_witness=inputs["original_completion"],original_slate=inputs["original_slate"],original_catalog=inputs["original_catalog"],
            original_policy=inputs["original_policy"],retained_models=retained_ref,prepared=request["prepared"],source=request["source"])
        if policy_ref is not None:context["public_policy"]=policy_ref
        if recurring:
            context.update({k:v for k,v in operations["archive_context"].items() if v is not None})
        result=self.archive_call("produce",self.archive_request("produce",context=context,r0=r0))
        require(result["archive_state"]=="COMPLETE_CAPTURE","PARTIAL_ARCHIVE_NOT_A_SUCCESSFUL_FORECAST")
        terminal=read_owned(self.storage,cp.binding(self.root/"runtime"/"FINISHED.json"))
        ref=write(self.storage,self.root/"PRODUCER_FINISHED.json",dict(schema_version=VERSION+"-result",state="PRIVATE_CAPTURE_APPENDED_RESTORE_REQUIRED",
            epoch_sha256=terminal["epoch_sha256"],choice_sha256=terminal["choice_sha256"],root_go_sha256=self.go_sha,
            original_completion_file_retained=False,old_history_retained=True,fits=0,model_pairs=18,selected_rows=terminal["selected_rows"],
            candidate_rows=terminal["prediction_rows"],R0_capture="ORIGINAL_DEFAULT_REFRESH_PRIVATE",public_release=False,successful_forecast=False,
            actual_completed_at=now_utc().isoformat()))
        return read_owned(self.storage,ref)

    def restore(self):
        failure_text=self.env.get("AUDIT_WEEKLY_FAILURE_HANDOFF_JSON","").encode()
        if not failure_text and (self.go.get("effective_epoch") or {}).get("plan",{}).get("kind")=="GRADE_ONLY":
            return self.grade_only()
        if self.go["operation"]=="CONTROLLER_REGISTRATION" and not failure_text:
            return self.controller_registration("controller-template-read")
        if failure_text:
            require(store.sha(failure_text)==self.env.get("AUDIT_WEEKLY_FAILURE_HANDOFF_SHA256"),"EXACT_FAILED_ATTEMPT_HANDOFF")
            value=cp.strict_json(failure_text)
            require(value["schema_version"]==VERSION+"-failure-handoff" and value["root_go_sha256"]==self.go_sha
                and value["binding"]==self.go["qualified_runtime"]["binding"],"SAME_ROOT_FAILED_ATTEMPT")
            client=self.failure_client("restore")
            inputs={k:store.canonical(value[k]) for k in ("binding","descriptor")}
            go=self.operation_go("restore",inputs)
            result=failure.restore_failure(client,self.storage,self.root/"failure-restored",authorization=store.canonical(go),
                authorization_sha256=store.sha(store.canonical(go)),inputs=inputs)
            archive_restored=False
            archive_raw=self.env.get("AUDIT_WEEKLY_ARCHIVE_HANDOFF_JSON","").encode()
            if archive_raw:
                require(store.sha(archive_raw)==self.env.get("AUDIT_WEEKLY_ARCHIVE_HANDOFF_SHA256"),"EXACT_FAILED_ARCHIVE_HANDOFF")
                handoff=cp.strict_json(archive_raw)
                require(handoff["archive_state"]=="FAILURE_EVIDENCE" and handoff["root_go_sha256"]==self.go_sha,"FAILURE_ARCHIVE_NOT_SELECTED_OUTPUT")
                restored=self.archive_call("restore",self.archive_request("restore",handoff=handoff))
                require(restored["state"]=="PRIVATE_FAILURE_ARCHIVE_RESTORED","COMPLETE_FAILED_BYTES_RESTORE_REQUIRED")
                archive_restored=True
            return dict(state="PRIVATE_FAILURE_RESTORED",fits=0,public_release=False,successful_forecast=False,
                original_attempt=result["attempt"],receipt_sha256=store.sha(store.canonical(result)),opaque_failed_capture_restored=archive_restored)
        raw=self.env.get("AUDIT_WEEKLY_ARCHIVE_HANDOFF_JSON","").encode()
        require(0<len(raw)<=16 << 10 and store.sha(raw)==self.env.get("AUDIT_WEEKLY_ARCHIVE_HANDOFF_SHA256"),"EXACT_ARCHIVE_JOB_HANDOFF")
        handoff=cp.strict_json(raw);archive.safe_handoff(handoff)
        require(handoff["root_go_sha256"]==self.go_sha and handoff["jobs"]==JOBS,"SAME_WEEKLY_ROOT_RESTORE")
        result=self.archive_call("restore",self.archive_request("restore",handoff=handoff))
        if self.go["operation"]=="RECURRING_CAPTURE":
            self.grading_phase("operations-grade-write",cp.binding(self.root/"archive-restore"/"transport"/"RESTORED.json"))
        return result

    def consume(self):
        if self.go["operation"]=="CONTROLLER_REGISTRATION":
            return self.controller_registration("controller-template-seal")
        if (self.go.get("effective_epoch") or {}).get("plan",{}).get("kind")=="GRADE_ONLY":
            raw=self.env.get("AUDIT_WEEKLY_GRADE_HANDOFF_JSON","").encode()
            require(0<len(raw)<=16 << 10 and store.sha(raw)==self.env.get("AUDIT_WEEKLY_GRADE_HANDOFF_SHA256"),
                "EXACT_NATIVE_GRADING_WRITER_HANDOFF_REQUIRED")
            return self.grade_only(handoff=cp.strict_json(raw))
        raw=self.env.get("AUDIT_WEEKLY_READER_HANDOFF_JSON","").encode()
        require(0<len(raw)<=32 << 10 and store.sha(raw)==self.env.get("AUDIT_WEEKLY_READER_HANDOFF_SHA256"),"EXACT_READER_JOB_HANDOFF")
        reader=cp.strict_json(raw)
        require(reader["archive"]["root_go_sha256"]==self.go_sha and reader["archive"]["jobs"]==JOBS,"SAME_WEEKLY_ROOT_EXPORT")
        if self.go["operation"]=="RECURRING_CAPTURE":
            raw_handoff=self.env.get("AUDIT_WEEKLY_GRADE_HANDOFF_JSON","").encode()
            require(0<len(raw_handoff)<=16 << 10
                and store.sha(raw_handoff)==self.env.get("AUDIT_WEEKLY_GRADE_HANDOFF_SHA256"),
                "EXACT_NATIVE_GRADING_WRITER_HANDOFF_REQUIRED")
            # This first complete archive read belongs to grading. The later
            # public-delivery process performs its own complete live read and
            # acceptance. Neither a saved JSON flag nor this phase substitutes
            # for that acceptance; failed grading never reaches publication.
            self.archive_call("consume",self.archive_request("consume",reader_handoff=reader))
            grading_result=self.grading_phase("operations-grade-read",cp.binding(self.root/"archive-consume"/"transport"/"RESTORED.json"),
                handoff=cp.strict_json(raw_handoff))
        if self.publication is not None:
            from . import audit_weekly_delivery_v1 as delivery
            clients=[];package=self.go["qualified_runtime"]
            proof=self.fresh_operations_proof()
            def factory(operation):
                self.check()
                require(operation=="restore" and len(clients)<archive.MAX_CLIENTS,"FINITE_PUBLIC_DELIVERY_GET_ONLY")
                client=archive.Client(self.env.get("GITHUB_TOKEN"),self.identity["run_id"],source_sha=self.identity["source_sha"],
                    journal=self.journal,job=self.job,operation="restore",qualification=package["qualification"],readonly=True)
                client.authenticate_actions_job();client.bind(package["binding"])
                operations_authority.attach(client,proof,self.env,store.canonical(self.go))
                require(cp.client_identity(client)["api_job_id"]==self.identity["api_job_id"],"SAME_AUTHENTICATED_PUBLIC_EXPORT_JOB")
                clients.append(client);return client
            result=delivery.deliver(reader,package,factory,self.storage,self.root/"delivery",self.go_sha,self.go["pending_census"],
                self.publication,ROOT,expected_source_sha=self.go["source_sha"],
                expected_original_choice_sha256=self.publication["policy"]["origin_choice_sha256"],root_go=self.go,
                before_publication=(lambda receipt:self.grading_delivery(grading_result["manifest"],receipt))
                    if self.go["operation"]=="RECURRING_CAPTURE" else None)
            self.check()
            return dict(result,public_release=True,successful_forecast=True,scientific_qualification=False)
        result=self.archive_call("consume",self.archive_request("consume",reader_handoff=reader))
        require(result["state"]=="PRIVATE_CAPTURE_EXPORT_INPUTS_VERIFIED","FAILED_OR_PARTIAL_CAPTURE_CANNOT_EXPORT")
        return result

    def failure_client(self, operation):
        proof=self.fresh_operations_proof()
        client=archive.Client(self.env.get("GITHUB_TOKEN"),self.identity["run_id"],source_sha=self.identity["source_sha"],
            journal=self.journal,job=self.job,operation=operation,qualification=self.go["qualified_runtime"]["qualification"],
            readonly=operation=="restore")
        client.authenticate_actions_job();client.bind(self.go["qualified_runtime"]["binding"])
        operations_authority.attach(client,proof,self.env,store.canonical(self.go))
        return client

    def operation_go(self,operation,inputs,*,manifest=None):
        package=self.go["qualified_runtime"]
        return dict(schema_version="weekly-private-operation-GO-v2.1",approved=True,operation=operation,repository=store.REPO,
            run_id=self.identity["run_id"],source_sha=self.identity["source_sha"],config_sha256=store.config_sha(),
            scope_manifest_sha256=digest(manifest) if operation=="append" else None,
            qualification_sha256=digest(package["qualification"]) if operation=="append" else None,
            single_writer_group="nfl-lab-single-writer",runtime_id=package["binding"]["runtime_id"],
            input_sha256={k:store.sha(v) for k,v in inputs.items()},job_id=self.identity["job_id"],workflow_ref=self.identity["workflow_ref"])

    def verify_external_failure(self):
        """An environment flag cannot invent an artifact-action failure."""
        name=self.env.get("AUDIT_WEEKLY_FAILED_ACTION_STEP","")
        if not name:return False
        require(self.go["operation"]=="CONTROLLER_REGISTRATION" and self.phase=="consume"
            and name=="Upload only the closed controller SAFE_SEAL metadata",
            "CLOSED_EXTERNAL_ACTION_FAILURE_SCOPE")
        self.check()
        jobs=archive.jobs_for(self.client)
        current=[j for j in jobs if j.get("id")==self.identity["api_job_id"]]
        require(len(current)==1 and type(current[0].get("steps")) is list,"ACTUAL_FAILED_ACTION_JOB_REQUIRED")
        found=[s for s in current[0]["steps"] if s.get("name")==name]
        require(len(found)==1 and found[0].get("status")=="completed" and found[0].get("conclusion")=="failure"
            and type(found[0].get("number")) is int and found[0]["number"]>0
            and self.started<=utc(found[0]["started_at"])<=utc(found[0]["completed_at"])<=now_utc(),
            "GENUINE_FAILED_ACTION_API_EVIDENCE_REQUIRED")
        write(self.storage,self.root/"phase-status"/"EXTERNAL_ACTION_FAILED.json",dict(state="FAILED_RETAINED",
            root_go_sha256=self.go_sha,current_identity=self.identity,actual_step=found[0],
            actual_observed_at=now_utc().isoformat(),original_process_exit_code_retained=False,
            successful_forecast=False,public_release=False))
        return True

    def preserve_failure(self):
        """A distinct fresh process; no original command or source is retried."""
        output=self.root/"failure-evidence"
        require(not output.exists(),"FAILED_ATTEMPT_PRESERVATION_ALREADY_CONSUMED")
        action_failure=self.verify_external_failure()
        controls=self.storage.register_root(self.root/"failure-controls")
        # A secondary archive failure must not suppress the independent
        # original-failure envelope. Never retry an existing archive intent.
        archive_result=None
        try:
            if not (self.root/"failure-archive-produce").exists():
                archive_result=self.preserve_opaque_outputs()
        except Exception as error:
            code=error.code if isinstance(error,store.StoreError) else "SECONDARY_ARCHIVE_FAILED"
            if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}",code):code="SECONDARY_ARCHIVE_FAILED"
            write(self.storage,controls/"SECONDARY_PRESERVATION_FAILURE.json",dict(state="FAILED_RETAINED",reason=code,
                original_failure_replaced=False,partial_forecast_durability_established=False,successful_forecast=False,public_release=False))
        graph=[];attachments=[]
        for folder in (self.root/"phase-status",self.root/"requests",self.root/"metadata",self.root/"runtime",self.root/"reference"):
            if not folder.exists():continue
            for path in sorted(folder.rglob("*")):
                require(not path.is_symlink(),"FAILED_ATTEMPT_SYMLINK_FORBIDDEN")
                if path.is_file():
                    ref=cp.binding(path);graph.append(dict(relative_path=path.relative_to(self.root).as_posix(),reference=ref))
        delivery=self.root/"delivery"
        if delivery.is_dir():
            for path in sorted(delivery.glob("DELIVERY_*.json")):
                require(path.is_file() and not path.is_symlink(),"ORIGINAL_DELIVERY_FAILURE_STATUS_REQUIRED")
                ref=cp.binding(path);graph.append(dict(relative_path=path.relative_to(self.root).as_posix(),reference=ref))
        require(len(graph)<=1024,"FINITE_FAILURE_FILE_GRAPH")
        inventory=write(self.storage,controls/"ORIGINAL_FILE_GRAPH.json",dict(schema_version=VERSION+"-failed-file-graph",files=graph,
            raw_HTTP_corpus_archived=False,successful_forecast=False,public_release=False))
        attachments.append(dict(label="file-graph",kind="control",reference=inventory))
        attachments.append(dict(label="owner-root",kind="control",reference=self.root_ref))
        import base64
        journals=[]
        for path in sorted(self.root.rglob("*.reservation.json")):
            require(not path.is_symlink(),"ORIGINAL_POST_JOURNAL_SYMLINK")
            raw=store.read_local(path,32 << 10)
            journals.append(dict(relative_path=path.relative_to(self.root).as_posix(),bytes=len(raw),sha256=store.sha(raw),body_base64=base64.b64encode(raw).decode()))
        journal_ref=write(self.storage,controls/"ORIGINAL_POST_RESERVATIONS.json",dict(schema_version=VERSION+"-original-post-journals",records=journals))
        require(journal_ref["bytes"]<=failure.ATTACHMENT_CAP,"FULL_ORIGINAL_POST_JOURNAL_BOUND")
        attachments.append(dict(label="original-post-reservations",kind="post_reservation",reference=journal_ref))
        auxiliary=[];auxiliary_groups=[]
        fixed=[self.root/name for name in ("BOOTSTRAP_STARTED.json","BOOTSTRAP_FAILED.json","BOOTSTRAP_REAUTHENTICATED.json","PARENT_STARTED.json")]
        fixed += sorted(delivery.glob("DELIVERY_*.json")) if delivery.is_dir() else []
        fixed += sorted((self.root/"phase-status").glob("*.stdout"))
        fixed += sorted((self.root/"phase-status").glob("*.stderr"))
        for path in fixed:
            if not path.exists():continue
            ref=cp.binding(path);require(ref["bytes"]<=64 << 10,"BOUNDED_COMPLETE_FAILED_PHASE_CONTROL")
            value=read_owned_stdio(self.storage,ref) if path.suffix in {".stdout",".stderr"} else read_owned(self.storage,ref,64 << 10,raw=True)
            item=dict(relative_path=path.relative_to(self.root).as_posix(),bytes=len(value),sha256=store.sha(value),
                body_base64=base64.b64encode(value).decode())
            candidate=dict(schema_version=VERSION+"-complete-auxiliary-controls",files=auxiliary+[item])
            if len(store.canonical(candidate))>failure.ATTACHMENT_CAP:
                require(auxiliary,"SINGLE_FAILED_PHASE_CONTROL_MUST_FIT")
                auxiliary_groups.append(auxiliary);auxiliary=[]
            auxiliary.append(item)
        if auxiliary:
            auxiliary_groups.append(auxiliary)
        for n,group in enumerate(auxiliary_groups):
            suffix="" if n==0 else f"-{n:02}"
            aux=write(self.storage,controls/("ORIGINAL_AUXILIARY_CONTROLS"+suffix+".json"),dict(schema_version=VERSION+"-complete-auxiliary-controls",files=group))
            require(aux["bytes"]<=failure.ATTACHMENT_CAP,"COMPLETE_FAILED_PHASE_AUXILIARY_CONTROL_BOUND")
            attachments.append(dict(label="complete-auxiliary-controls"+suffix,kind="original_failure",reference=aux))
        secondary=controls/"SECONDARY_PRESERVATION_FAILURE.json"
        if secondary.is_file():
            attachments.append(dict(label="secondary-preservation-failure",kind="original_failure",reference=cp.binding(secondary)))
        status_paths=sorted((self.root/"phase-status").glob("*.json"))
        require(len(status_paths)+len(attachments)<=failure.ATTACHMENT_COUNT,"ALL_FAILED_PHASE_CONTROLS_MUST_FIT_NO_OMISSION")
        for n,path in enumerate(status_paths):
            ref=cp.binding(path)
            require(ref["bytes"]<=failure.ATTACHMENT_CAP,"COMPLETE_FAILED_PHASE_STATUS_BOUND")
            attachments.append(dict(label=f"phase-{n:02}",kind="original_failure",reference=ref))
        attempt={k:self.identity[k] for k in failure.ATTEMPT_KEYS if k!="run_attempt"};attempt["run_attempt"]=1
        request=dict(schema_version=failure.VERSION+"-request",attempt=attempt,
            operation={"produce":"producer","restore":"checkpoint","consume":"export"}.get(self.phase,"checkpoint"),state="FAILED",
            failure=actual_failure(self.env,python_failure_recorded=(self.root/"phase-status/PARENT_FAILED.json").exists() or (self.root/"BOOTSTRAP_FAILED.json").exists(),
                action_failure_recorded=action_failure),
            clocks=dict(started_at_utc=self.started.isoformat(),observed_at_utc=now_utc().isoformat(),original={}),
            input_contract_sha256=self.go_sha,attachments=attachments)
        failure.record_failure(request,self.storage,output)
        manifest=read_owned(self.storage,cp.binding(output/"PAYLOAD.json"))
        package=self.go["qualified_runtime"]
        inputs={k:store.canonical(v) for k,v in dict(binding=package["binding"],payload_manifest=manifest,qualification=package["qualification"]).items()}
        go=self.operation_go("append",inputs,manifest=manifest)
        client=self.failure_client("append")
        value=failure.append_failure(client,self.storage,output,authorization=store.canonical(go),authorization_sha256=digest(go),inputs=inputs)
        handoff=dict(schema_version=VERSION+"-failure-handoff",root_go_sha256=self.go_sha,binding=package["binding"],descriptor=value["descriptor"])
        body=store.canonical(handoff)
        require(len(body)<=16 << 10 and not any(x in body for x in (b"https://",b"/tmp/",b"ghs_")),"SAFE_FAILED_HANDOFF")
        with open(self.env["GITHUB_OUTPUT"],"a") as stream:
            stream.write("failure_handoff_json="+body.decode()+"\nfailure_handoff_sha256="+store.sha(body)+"\n");stream.flush();os.fsync(stream.fileno())
        return dict(state="FAILED_ATTEMPT_APPENDED_READER_REQUIRED",fits=0,public_release=False,successful_forecast=False,
            partial_forecast_archive_state=archive_result.get("archive_state") if archive_result else "UNQUALIFIED_SEE_ORIGINAL_FILE_GRAPH_AND_SECONDARY_STATUS")

    def preserve_opaque_outputs(self):
        """Retain failed native/partial forecast bytes as FAILURE_EVIDENCE.

        This is a closed filesystem snapshot, not a repaired success receipt.
        It does not run model decoding, forecast validation or provider reads.
        Raw HTTP/source intermediates and qualified model weights remain outside
        this declared capture scope; every included byte is bounded and owned.
        """
        import base64
        import re
        files=[];physical_origins={};observations=[];observation_bytes=0
        collection=self.storage.register_root(self.root/"failure-opaque-collection")
        def add(path,logical):
            require(not path.is_symlink() and path.is_file(),"FAILED_SNAPSHOT_SYMLINK")
            require(len(files)<archive.MAX_FILES and path.stat().st_size<=store.ASSET_CAP,"ALL_FAILED_FILES_WITHIN_CLOSED_CAPS")
            ref=cp.binding(path);physical_origins[logical]=dict(ref)
            alias=collection/logical
            self.storage.import_file(path,alias,expected_sha256=ref["sha256"])
            files.append(cp.file_item(cp.binding(alias),logical,"forecast" if path.suffix==".gz" else "control"))
        # Full fixed controls survive even if the separate core-failure
        # envelope cannot finish. Raw source caches and weights stay excluded.
        for name in ("OWNER_ROOT.json","QUALIFIED_RUNTIME.json","BOOTSTRAP_STARTED.json","BOOTSTRAP_FAILED.json",
                "BOOTSTRAP_REAUTHENTICATED.json","PARENT_STARTED.json"):
            path=self.root/name
            if path.exists():add(path,"failed/bootstrap/"+name)
        for folder,names in (("source",("SOURCE_FINISHED.json","SOURCE_FAILED.json","CONSUMED.json")),
                ("prepared",("PREPARED.json",))):
            for name in names:
                path=self.root/folder/name
                if path.exists():add(path,"failed/"+folder+"-metadata/"+name)
        # Keep the failed normal archive's own intent, descriptors and POST
        # journals. Its preencoded bodies duplicate the original runtime scope
        # below and are not retried or presented as successful output.
        normal=self.root/"archive-produce"
        if normal.exists():
            for name in ("CONSUMED.json","ADMISSION.json","HANDOFF.json","APPEND_FAILED.json","APPENDED.json",
                    *(f"APPEND_INTENT_{n}.json" for n in range(9))):
                path=normal/"transport"/name
                if path.exists():add(path,"failed/original-archive/"+name)
            original_pending=[]
            journal=normal/"journal"
            if journal.exists():
                for path in sorted(journal.rglob("*")):
                    require(not path.is_symlink(),"ORIGINAL_ARCHIVE_JOURNAL_SYMLINK")
                    if not path.is_file() or path.name==_OWNER:continue
                    add(path,"failed/original-archive/journal/"+path.relative_to(journal).as_posix())
                    if path.name.endswith(".reservation.json"):
                        original_pending.append(cp.strict_json(store.read_local(path,32 << 10)))
            # Native admission must still charge every unresolved earlier POST.
            # This copies original reservation metadata, never retries a POST.
            if original_pending:cp.seed_pending(self.journal,original_pending)
        for folder in ("runtime","reference","metadata","phase-status","requests","journal",
                "operations-grade-write","operations-grade-read","operations-prepared","grading-delivery",
                "controller-template-write","controller-template-read","controller-template-seal"):
            base=self.root/folder
            if not base.exists():continue
            for path in sorted(base.rglob("*")):
                require(not path.is_symlink(),"FAILED_SNAPSHOT_SYMLINK")
                if not path.is_file() or path.name==_OWNER:continue
                logical="failed/"+path.relative_to(self.root).as_posix()
                if folder=="reference" and path.parent==base/"source-observations" and re.fullmatch(r"[0-9]{4}-(?:BEGIN|END)\.json",path.name):
                    # Preserve all original small receipts in one bounded
                    # container. Do not spend one of 512 transport-file slots
                    # per receipt, raise the cap, or discard hard rows.
                    ref=cp.binding(path)
                    require(len(observations)<1024 and ref["bytes"]<=64 << 10,"FINITE_FULL_ORIGINAL_OBSERVATION_CONTROLS")
                    raw=archive.read_owned(self.storage,ref,64 << 10,raw=True)
                    observation_bytes+=len(raw)
                    require(observation_bytes<=1 << 20,"COMPLETE_ORIGINAL_OBSERVATION_BYTES_CAP")
                    observations.append(dict(logical_path=logical,reference=ref,body_base64=base64.b64encode(raw).decode()))
                    continue
                # Files left by an interrupted atomic write may not yet be CAS
                # aliases. Import exact original bytes; never rewrite them.
                add(path,logical)
        bundled={}
        if observations:
            observations.sort(key=lambda r:r["logical_path"])
            value=dict(schema_version=archive.FAILURE_OBSERVATIONS_SCHEMA,records=observations)
            body=store.canonical(value)
            require(len(body)<=1 << 20,"FULL_ENCODED_ORIGINAL_OBSERVATION_BYTES_CAP")
            bundle_root=self.storage.register_root(self.root/"failure-observation-bundle")
            path=bundle_root/"SOURCE_OBSERVATIONS_BUNDLE.json"
            self.storage.write_bytes(path,body)
            add(path,archive.FAILURE_OBSERVATIONS_NAME)
            bundled[archive.FAILURE_OBSERVATIONS_NAME]=[{k:r[k] for k in ("logical_path","reference")} for r in observations]
        if not files:return None
        census=dict(schema_version=archive.VERSION+"-failed-opaque-census",archive_state="FAILURE_EVIDENCE",
            raw_HTTP_corpus_archived=False,model_weights_reuploaded=False,actual_collected_at=now_utc().isoformat(),
            source_started_at=self.started.isoformat(),source_completed_at=now_utc().isoformat(),
            logical_files=len(files),logical_bytes=sum(f["bytes"] for f in files),physical_origins=physical_origins,
            fits=0,successful_forecast=False,public_release=False)
        if bundled:census["bundled_control_sources"]=bundled
        snapshot=dict(files=sorted(files,key=lambda f:f["logical_path"]),census=census)
        package=self.go["qualified_runtime"];clients=[]
        proof=self.fresh_operations_proof()
        def factory(operation):
            require(operation=="append" and len(clients)<archive.MAX_CLIENTS,"FINITE_FAILED_ARCHIVE_APPEND")
            c=archive.Client(self.env.get("GITHUB_TOKEN"),self.identity["run_id"],source_sha=self.identity["source_sha"],journal=self.journal,
                job=self.job,operation=operation,qualification=package["qualification"])
            c.authenticate_actions_job();c.bind(package["binding"])
            operations_authority.attach(c,proof,self.env,store.canonical(self.go))
            clients.append(c);return c
        # A failed normal archive is immutable. This is a separate failure-only
        # append with its own intent, never a retry of that normal archive.
        handoff=archive.produce(snapshot,factory,package,storage=self.storage,output=self.root/"failure-archive-produce",
            root_go_sha256=self.go_sha,jobs=JOBS,pending_census=self.go["pending_census"])
        body=archive.safe_handoff(handoff)
        with open(self.env["GITHUB_OUTPUT"],"a") as stream:
            stream.write("archive_handoff_json="+body.decode()+"\narchive_handoff_sha256="+store.sha(body)+"\n");stream.flush();os.fsync(stream.fileno())
        return handoff


def schedule_metadata(raw, *, season, week):
    """Calendar only: score/workload/outcome columns are never used."""
    result=[]
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
        if int(row["season"])!=season or int(row["week"])!=week or row["game_type"]!="REG":continue
        local=datetime.fromisoformat(row["gameday"]+"T"+row["gametime"]).replace(tzinfo=ZoneInfo("America/New_York"))
        result.append(dict(season=season,week=week,game_type="REG",game_id=row["game_id"],kickoff_utc=local.astimezone(timezone.utc).isoformat()))
    require(result and len({r["game_id"] for r in result})==len(result),"COMPLETE_UNIQUE_WEEK_CALENDAR")
    return result


def child_context(args,env,phase,*,operations_proof=None):
    """Both native children independently bind the complete current authority."""
    from tools.private_draft_store_v2 import actions_context
    require(phase in {"models","reference"}|set(OPERATIONS_PHASES),"CLOSED_HOSTED_CHILD_PHASE")
    raw_authority=env.get("AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON","").encode()
    require(0<len(raw_authority)<=16 << 10 and store.sha(raw_authority)==env.get("AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256"),
        "EXACT_HOSTED_NATIVE_AUTHORITY_HASH")
    a=cp.strict_json(raw_authority)
    require(type(a) is dict and set(a)==NATIVE_KEYS and store.canonical(a)==raw_authority
        and a["schema_version"]==VERSION+"-native-authority" and a["phase"]==phase
        and a["repository"]==store.REPO and type(a["api_job_id"]) is int and a["api_job_id"]>0
        and type(a["run_attempt"]) is int and a["run_attempt"]==1 and type(a["fits"]) is int and a["fits"]==0
        and a["public_release"] is False and a["actual_actions_api_authenticated"] is a["owner_root_checked"] is True,
        "CLOSED_HOSTED_NATIVE_AUTHORITY")
    root_body=env.get("AUDIT_WEEKLY_ROOT_GO_JSON","").encode()
    require(0<len(root_body)<=60 << 10 and store.sha(root_body)==env.get("AUDIT_WEEKLY_ROOT_GO_SHA256"),"EXACT_CHILD_ROOT_GO_HASH")
    go=validate_root(cp.strict_json(root_body),now=now_utc())
    if go["operation"]=="RECURRING_CAPTURE":
        if operations_proof is None:operations_proof=operations_authority.current(env,root_body,ROOT)
        operations_authority._verify(operations_proof,env,root_body)
    else:require(operations_proof is None and operations_authority.owner(env),"ORIGINAL_OWNER_CHILD_REQUIRED")
    role,output_name=OPERATIONS_PHASES.get(phase,("produce","retained" if phase=="models" else "reference"))
    require(store.canonical(go)==root_body and a["owner_root_go_sha256"]==store.sha(root_body)
        and env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
        and env.get("GITHUB_REPOSITORY")==store.REPO and env.get("GITHUB_RUN_ATTEMPT")=="1"
        and env.get("STORE_PERMISSION")=="write" and a["source_sha"]==env.get("GITHUB_SHA")==env.get("GITHUB_WORKFLOW_SHA")==go["source_sha"]
        and a["run_id"]==env.get("GITHUB_RUN_ID") and a["job_id"]==env.get("GITHUB_JOB")==JOBS[role]
        and a["workflow_ref"]==env.get("GITHUB_WORKFLOW_REF")==go["workflow_ref"]
        and utc(go["issued_at_utc"])<=utc(a["issued_at_utc"])<=now_utc()<utc(a["expires_at_utc"])==utc(go["expires_at_utc"]),
        "ACTUAL_HOSTED_CHILD_ROOT_AND_IDENTITY")
    event=cp.strict_json(store.read_local(env["GITHUB_EVENT_PATH"],256 << 10))
    require(event.get("repository",{}).get("full_name")==store.REPO and event.get("inputs",{}).get("mode")==MODE
        and event["inputs"].get("inference_builder_go_json")==root_body.decode()
        and event["inputs"].get("inference_builder_go_sha256")==a["owner_root_go_sha256"],"ACTUAL_CHILD_ROOT_EVENT")
    require(subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()==go["source_sha"]
        and subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",*PINS],cwd=ROOT,text=True)=="",
        "CLEAN_COMMITTED_CHILD_SOURCE")
    expected=store.parents_safe(env["RUNNER_TEMP"])/(VERSION+"-"+env["GITHUB_RUN_ID"]+"-"+role)
    request_path=store.parents_safe(args.request)
    require(request_path.is_relative_to(expected/"requests"),"CURRENT_OWNED_CHILD_REQUEST_PATH")
    raw=store.read_local(request_path,512 << 10);request=cp.strict_json(raw)
    require(raw==store.canonical(request) and store.sha(raw)==args.request_sha256==a["request_sha256"]
        and request["code_pins"]==pins() and request["cache"]==str(expected/"cache")
        and request["state_root"]==str(expected/"state")
        and request["output"]==str(expected/output_name),"SEALED_CONFINED_CURRENT_CHILD_REQUEST")
    job=actions_context(env,"write")
    require(job["job_id"]==a["job_id"] and job["workflow_ref"]==a["workflow_ref"] and job["workflow_sha"]==a["source_sha"],
        "ACTUAL_NATIVE_JOB_MATCHES_AUTHORITY")
    return request,a,job,go


def model_child(args, env):
    """Dedicated numerical process; source/model restoration does zero fits."""
    root_bytes=env.get("AUDIT_WEEKLY_ROOT_GO_JSON","").encode()
    proof=operations_authority.child(env,root_bytes,ROOT)
    request,a,job,go=child_context(args,env,"models",operations_proof=proof)
    numerical.loaded(ROOT,env)
    require(set(request)=={"schema_version","registration","cache","state_root","output","code_pins"}
        and request["schema_version"]==VERSION+"-model-request" and request["registration"]==retained_registration(go),
        "CLOSED_CURRENT_MODEL_REQUEST")
    storage=OperationalStorage(request["cache"],ROOT/"config/operational-source-policy-v2.json",state=request["state_root"])
    archived=cp.strict_json(store.read_local(ROOT/"reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json",store.META_CAP))
    journal=Path(request["output"]).parent/"retained-journal";journal.mkdir(mode=0o700)
    cp.seed_pending(journal,request["registration"]["pending_reservations"])
    class Factory:
        qualification=archived["qualification"]
        clients=[]
        def __call__(self,operation):
            require(operation=="restore" and len(self.clients)<9,"NINE_MODEL_GET_ONLY_OPERATIONS")
            c=retained.ReadClient(env.get("GITHUB_TOKEN"),env["GITHUB_RUN_ID"],journal=journal,source_sha=env["GITHUB_SHA"],job=job,
                operation=operation,extra_routes=retained.routes(request["registration"],self.qualification))
            c.authenticate_actions_job();c.bind(archived["binding"])
            operations_authority.attach(c,proof,env,root_bytes)
            require(c.job["api_job_id"]==a["api_job_id"],"CURRENT_MODEL_API_JOB_REQUIRED")
            self.clients.append(c);return c
    factory=Factory()
    def offline():
        def deny(event,unused):
            if event.startswith(("socket.","subprocess.")) or event in {"os.fork","os.forkpty","os.exec","os.posix_spawn","os.system"}:
                raise store.StoreError("MODEL_REPLAY_NO_HTTP_OR_CHILDREN")
        sys.addaudithook(deny)
        import pyarrow as pa
        pa.set_cpu_count(2);pa.set_io_thread_count(2);pa.set_memory_pool(pa.system_memory_pool())
    envelope=dict(runtime_envelopes=bounds.shared_envelopes(),code_pins={"tools/review_direct_booster_screen_guard_v4.py":pins()["tools/review_direct_booster_screen_guard_v4.py"]})
    with bounds.resource_envelope(envelope,"requalify",ROOT):
        result=retained.restore(request["registration"],factory,storage=storage,output=request["output"],current_go_sha256=a["owner_root_go_sha256"],
            before_replay=offline,check_authority=lambda:require(now_utc()<utc(a["expires_at_utc"]),"WEEKLY_ROOT_EXPIRED"))
    return dict(state=result["state"],model_pairs=18,fits=0,remote_writes=0,public_release=False)


def reference_child(args, env):
    """Private original R0; metadata/source identities were fixed before values."""
    root_bytes=env.get("AUDIT_WEEKLY_ROOT_GO_JSON","").encode()
    proof=operations_authority.child(env,root_bytes,ROOT)
    p,a,job,go=child_context(args,env,"reference",operations_proof=proof)
    extra={"previous_state","previous_state_aliases"} if go["operation"]=="RECURRING_CAPTURE" else set()
    require(set(p)=={"schema_version","inputs","history_binding","config","cache","state_root","prepared","source",
        "runtime_root","output","repository","code_pins"}|extra and p["schema_version"]==VERSION+"-reference-request"
        and p["config"]==go["source_config"] and p["repository"]==env.get("NFL_R0_SOURCE_REPOSITORY")==str(ROOT/"r0-public-reference")
        and p["runtime_root"]==str(Path(p["output"]).parent/"runtime"),"CLOSED_REGISTERED_ORIGINAL_REFERENCE_REQUEST")
    storage=OperationalStorage(p["cache"],ROOT/"config/operational-source-policy-v2.json",state=p["state_root"])
    journal=Path(p["output"]).parent/"reference-journal";journal.mkdir(mode=0o700)
    c=store.Client(env.get("GITHUB_TOKEN"),env["GITHUB_RUN_ID"],source_sha=env["GITHUB_SHA"],journal=journal,job=job,operation="metadata")
    c.authenticate_actions_job()
    operations_authority.attach(c,proof,env,root_bytes)
    require(c.job["api_job_id"]==a["api_job_id"] and c.job["job_id"]==a["job_id"]==env["GITHUB_JOB"]
        and a["source_sha"]==env["GITHUB_SHA"]
        and a["run_id"]==env["GITHUB_RUN_ID"] and a["job_id"]==JOBS["produce"]
        and a["owner_root_go_sha256"]==store.sha(env["AUDIT_WEEKLY_ROOT_GO_JSON"].encode())==env["AUDIT_WEEKLY_ROOT_GO_SHA256"]
        and a["actual_actions_api_authenticated"] is a["owner_root_checked"] is True
        and utc(a["issued_at_utc"])<=now_utc()<utc(a["expires_at_utc"]),"CURRENT_REAL_REFERENCE_JOB")
    inp=p["inputs"];read=lambda name,raw=False:read_owned(storage,inp[name],raw=raw)
    e=epoch.restore_epoch(read("epoch"),read("original_choice",True),read("original_completion"),read("original_slate"),
        read("original_catalog"),read("original_policy"),history_binding=p["history_binding"],now=now_utc())
    registered=epoch.bind_registration(e,read("epoch_registration"),now=now_utc())
    doc=read("choice");choice=epoch.EpochChoice(doc,digest(doc))
    backend=runtime.Runtime(storage,registered,choice,inp["retained_restore"],p["config"])
    prepared=read_owned(storage,p["prepared"]);completion=read_owned(storage,prepared["choice_completion"])
    permit=epoch.authorize_capture(registered,choice,completion,relocated_replays=(backend.replay,))
    import pandas as pd
    q=pd.read_parquet(Path(p["runtime_root"])/"queries.parquet")
    bridge=read_owned(storage,cp.binding(Path(p["runtime_root"])/"IDENTITY_BRIDGE.json"))["identities"]
    offers=runtime.generic.offers(q,backend.records,choice.document["slate"])
    pref=reference.prepare_reference(storage,p["output"],repository=p["repository"],permit=permit,
        slate=choice.document["slate"],control=e.document["catalog"]["methods"]["R0"],offers=offers,bridge=bridge,
        previous_state=p.get("previous_state"),previous_state_aliases=p.get("previous_state_aliases"))
    ref=reference.capture_reference(storage,pref);finished=read_owned(storage,ref)
    return dict(state=finished["state"],available_rows=finished["available_rows"],unavailable_rows=finished["unavailable_rows"],fits=0,public_release=False)


def execute(phase, env):
    actual=phase
    if phase=="preserve":
        matches=[k for k,v in JOBS.items() if v==env.get("GITHUB_JOB")]
        require(len(matches)==1,"ONLY_ORIGINAL_FAILED_PHASE_MAY_BE_PRESERVED")
        actual=matches[0]
    runner=Runner(actual,env,existing=phase=="preserve")
    action={"produce":runner.produce,"restore":runner.restore,"consume":runner.consume,
        "evidence":runner.restore,"preserve":runner.preserve_failure}[phase]
    try:return action()
    except Exception as error:
        if phase!="preserve":
            code=error.code if isinstance(error,store.StoreError) else "WEEKLY_UNEXPECTED_PHASE_FAILURE"
            if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}",code):code="WEEKLY_UNEXPECTED_PHASE_FAILURE"
            write(runner.storage,runner.root/"phase-status"/"PARENT_FAILED.json",dict(state="FAILED_RETAINED",phase=actual,
                reason=code,actual_observed_at=now_utc().isoformat(),public_release=False,successful_forecast=False,diagnostic=error_diagnostic(error)))
        raise
