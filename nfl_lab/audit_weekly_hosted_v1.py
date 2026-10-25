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
from . import operational_failure_v1 as failure
from . import audit_numerical_runtime_v1 as numerical
from .operational_storage import OperationalStorage, _OWNER
from .owned_reference_batch import validate_owned_references
from .state import digest, now_utc, utc

VERSION = "audit-weekly-hosted-v2"
MODE = "audit-weekly-producer-v1"
ROOT = Path(__file__).resolve().parents[1]
JOBS = dict(produce="audit-weekly-produce-v1", restore="audit-weekly-restore-v1", consume="audit-weekly-export-v1")
FAILURE_JOB = "audit-weekly-failure-restore-v1"
EXECUTION_JOBS = dict(JOBS, evidence=FAILURE_JOB)
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
    "nfl_lab/audit_numerical_runtime_v1.py", "tests/test_audit_numerical_runtime_v1.py",
    "config/audit-weekly-numerical-runtime-v1.json",
    ".github/workflows/audit-source-checks.yml"}))
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
    replay=go["retained_registration"]["origin"]["replay_catalog"]
    require(policy["source_sha"]==go["source_sha"] and policy["source_branch"]=="research/weekly-storage-probe-v1"
        and policy["jobs"]==JOBS and policy["registered_at_utc"]==go["issued_at_utc"]
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
    require(type(go) is dict and set(go)==ROOT_KEYS and go["schema_version"]==VERSION+"-root-GO"
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
        and type(go["publication"]) is bool and go["effective_epoch"] is None,
        "EXPLICIT_INITIAL_CORRECTION_SCOPE_NO_BACKFILL")
    require(go["operation"] in {"ORIGIN_METADATA_ONLY","CURRENT_CORRECTION_CAPTURE"}
        and (go["publication"] is False or go["operation"]=="CURRENT_CORRECTION_CAPTURE"),"EXPLICIT_WEEKLY_PUBLICATION_SCOPE")
    retained.validate_registration(go["retained_registration"])
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


def write(storage,path,value):
    storage.write_bytes(path,store.canonical(value));return cp.binding(path)


def actual_failure(env, *, python_failure_recorded):
    value=env.get("AUDIT_WEEKLY_ORIGINAL_EXIT_CODE","")
    require(value=="" or re.fullmatch(r"[1-9][0-9]{0,2}",value) and int(value)<=255,"ACTUAL_FAILED_STEP_EXIT_CODE_REQUIRED")
    code=int(value) if value else None
    kind="DEADLINE" if code==124 else "INTERRUPTION" if code in {130,137,143} or not python_failure_recorded else "EXCEPTION"
    return dict(kind=kind,code="WEEKLY_PHASE_FAILED_RETAINED",exit_code=code)


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
        require(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
            and env.get("GITHUB_REPOSITORY")==store.REPO and env.get("GITHUB_RUN_ATTEMPT")=="1"
            and env.get("GITHUB_ACTOR")=="NickNicky19" and env.get("GITHUB_ACTOR_ID")=="208912933"
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
        request=dict(schema_version=VERSION+"-model-request",registration=self.go["retained_registration"],cache=str(self.storage.cache),
            state_root=str(self.root/"state"),output=str(self.root/"retained"),code_pins=pins())
        a=self.native(VERSION,"models",request)
        self.child("audit_weekly_hosted_v1","models",request,a,"AUDIT_WEEKLY_NATIVE_AUTHORITY",430)
        return cp.binding(self.root/"retained"/"RESTORED.json")

    def metadata(self, origin_ref, retained_ref):
        old=read_owned(self.storage,origin_ref);restored=read_owned(self.storage,retained_ref)
        read=lambda role,raw=False:read_owned(self.storage,old[role],raw=raw)
        replay=self.go["retained_registration"]["origin"]["replay_catalog"]
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

    def reference(self, inputs, request):
        payload=dict(schema_version=VERSION+"-reference-request",inputs=inputs,history_binding=request["history_binding"],
            config=self.go["source_config"],cache=str(self.storage.cache),state_root=str(self.root/"state"),
            prepared=request["prepared"],source=request["source"],runtime_root=str(self.root/"runtime"),
            output=str(self.root/"reference"),repository=self.env["NFL_R0_SOURCE_REPOSITORY"],code_pins=pins())
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
        self.claim()
        origin_ref=self.recover_origin();old=read_owned(self.storage,origin_ref)
        retained_ref=self.recover_models()
        inputs=self.metadata(origin_ref,retained_ref)
        policy_ref=self.register_publication(inputs)
        request=self.capture(inputs,origin_ref)
        r0=self.reference(inputs,request)
        context=dict(epoch=inputs["epoch"],epoch_registration=inputs["epoch_registration"],original_choice=inputs["original_choice"],
            origin_witness=inputs["original_completion"],original_slate=inputs["original_slate"],original_catalog=inputs["original_catalog"],
            original_policy=inputs["original_policy"],retained_models=retained_ref,prepared=request["prepared"],source=request["source"])
        if policy_ref is not None:context["public_policy"]=policy_ref
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
        return self.archive_call("restore",self.archive_request("restore",handoff=handoff))

    def consume(self):
        raw=self.env.get("AUDIT_WEEKLY_READER_HANDOFF_JSON","").encode()
        require(0<len(raw)<=32 << 10 and store.sha(raw)==self.env.get("AUDIT_WEEKLY_READER_HANDOFF_SHA256"),"EXACT_READER_JOB_HANDOFF")
        reader=cp.strict_json(raw)
        require(reader["archive"]["root_go_sha256"]==self.go_sha and reader["archive"]["jobs"]==JOBS,"SAME_WEEKLY_ROOT_EXPORT")
        if self.publication is not None:
            from . import audit_weekly_delivery_v1 as delivery
            clients=[];package=self.go["qualified_runtime"]
            def factory(operation):
                self.check()
                require(operation=="restore" and len(clients)<archive.MAX_CLIENTS,"FINITE_PUBLIC_DELIVERY_GET_ONLY")
                client=archive.Client(self.env.get("GITHUB_TOKEN"),self.identity["run_id"],source_sha=self.identity["source_sha"],
                    journal=self.journal,job=self.job,operation="restore",qualification=package["qualification"],readonly=True)
                client.authenticate_actions_job();client.bind(package["binding"])
                require(cp.client_identity(client)["api_job_id"]==self.identity["api_job_id"],"SAME_AUTHENTICATED_PUBLIC_EXPORT_JOB")
                clients.append(client);return client
            result=delivery.deliver(reader,package,factory,self.storage,self.root/"delivery",self.go_sha,self.go["pending_census"],
                self.publication,ROOT,expected_source_sha=self.go["source_sha"],
                expected_original_choice_sha256=self.publication["policy"]["origin_choice_sha256"],root_go=self.go)
            self.check()
            return dict(result,public_release=True,successful_forecast=True,scientific_qualification=False)
        result=self.archive_call("consume",self.archive_request("consume",reader_handoff=reader))
        require(result["state"]=="PRIVATE_CAPTURE_EXPORT_INPUTS_VERIFIED","FAILED_OR_PARTIAL_CAPTURE_CANNOT_EXPORT")
        return result

    def failure_client(self, operation):
        client=archive.Client(self.env.get("GITHUB_TOKEN"),self.identity["run_id"],source_sha=self.identity["source_sha"],
            journal=self.journal,job=self.job,operation=operation,qualification=self.go["qualified_runtime"]["qualification"],
            readonly=operation=="restore")
        client.authenticate_actions_job();client.bind(self.go["qualified_runtime"]["binding"])
        return client

    def operation_go(self,operation,inputs,*,manifest=None):
        package=self.go["qualified_runtime"]
        return dict(schema_version="weekly-private-operation-GO-v2.1",approved=True,operation=operation,repository=store.REPO,
            run_id=self.identity["run_id"],source_sha=self.identity["source_sha"],config_sha256=store.config_sha(),
            scope_manifest_sha256=digest(manifest) if operation=="append" else None,
            qualification_sha256=digest(package["qualification"]) if operation=="append" else None,
            single_writer_group="nfl-lab-single-writer",runtime_id=package["binding"]["runtime_id"],
            input_sha256={k:store.sha(v) for k,v in inputs.items()},job_id=self.identity["job_id"],workflow_ref=self.identity["workflow_ref"])

    def preserve_failure(self):
        """A distinct fresh process; no original command or source is retried."""
        output=self.root/"failure-evidence"
        require(not output.exists(),"FAILED_ATTEMPT_PRESERVATION_ALREADY_CONSUMED")
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
            value=read_owned(self.storage,ref,64 << 10,raw=True)
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
            failure=actual_failure(self.env,python_failure_recorded=(self.root/"phase-status/PARENT_FAILED.json").exists() or (self.root/"BOOTSTRAP_FAILED.json").exists()),
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
        for folder in ("runtime","reference","metadata","phase-status","requests","journal"):
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
        def factory(operation):
            require(operation=="append" and len(clients)<archive.MAX_CLIENTS,"FINITE_FAILED_ARCHIVE_APPEND")
            c=archive.Client(self.env.get("GITHUB_TOKEN"),self.identity["run_id"],source_sha=self.identity["source_sha"],journal=self.journal,
                job=self.job,operation=operation,qualification=package["qualification"])
            c.authenticate_actions_job();c.bind(package["binding"]);clients.append(c);return c
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


def child_context(args,env,phase):
    """Both native children independently bind the complete current authority."""
    from tools.private_draft_store_v2 import actions_context
    require(phase in {"models","reference"},"CLOSED_HOSTED_CHILD_PHASE")
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
    require(store.canonical(go)==root_body and a["owner_root_go_sha256"]==store.sha(root_body)
        and env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
        and env.get("GITHUB_REPOSITORY")==store.REPO and env.get("GITHUB_RUN_ATTEMPT")=="1"
        and env.get("GITHUB_ACTOR")=="NickNicky19" and env.get("GITHUB_ACTOR_ID")=="208912933"
        and env.get("STORE_PERMISSION")=="write" and a["source_sha"]==env.get("GITHUB_SHA")==env.get("GITHUB_WORKFLOW_SHA")==go["source_sha"]
        and a["run_id"]==env.get("GITHUB_RUN_ID") and a["job_id"]==env.get("GITHUB_JOB")==JOBS["produce"]
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
    expected=store.parents_safe(env["RUNNER_TEMP"])/(VERSION+"-"+env["GITHUB_RUN_ID"]+"-produce")
    request_path=store.parents_safe(args.request)
    require(request_path.is_relative_to(expected/"requests"),"CURRENT_OWNED_CHILD_REQUEST_PATH")
    raw=store.read_local(request_path,512 << 10);request=cp.strict_json(raw)
    require(raw==store.canonical(request) and store.sha(raw)==args.request_sha256==a["request_sha256"]
        and request["code_pins"]==pins() and request["cache"]==str(expected/"cache")
        and request["state_root"]==str(expected/"state")
        and request["output"]==str(expected/("retained" if phase=="models" else "reference")),"SEALED_CONFINED_CURRENT_CHILD_REQUEST")
    job=actions_context(env,"write")
    require(job["job_id"]==a["job_id"] and job["workflow_ref"]==a["workflow_ref"] and job["workflow_sha"]==a["source_sha"],
        "ACTUAL_NATIVE_JOB_MATCHES_AUTHORITY")
    return request,a,job,go


def model_child(args, env):
    """Dedicated numerical process; source/model restoration does zero fits."""
    request,a,job,go=child_context(args,env,"models")
    numerical.loaded(ROOT,env)
    require(set(request)=={"schema_version","registration","cache","state_root","output","code_pins"}
        and request["schema_version"]==VERSION+"-model-request" and request["registration"]==go["retained_registration"],
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
    p,a,job,go=child_context(args,env,"reference")
    require(set(p)=={"schema_version","inputs","history_binding","config","cache","state_root","prepared","source",
        "runtime_root","output","repository","code_pins"} and p["schema_version"]==VERSION+"-reference-request"
        and p["config"]==go["source_config"] and p["repository"]==env.get("NFL_R0_SOURCE_REPOSITORY")==str(ROOT/"r0-public-reference")
        and p["runtime_root"]==str(Path(p["output"]).parent/"runtime"),"CLOSED_REGISTERED_ORIGINAL_REFERENCE_REQUEST")
    storage=OperationalStorage(p["cache"],ROOT/"config/operational-source-policy-v2.json",state=p["state_root"])
    journal=Path(p["output"]).parent/"reference-journal";journal.mkdir(mode=0o700)
    c=store.Client(env.get("GITHUB_TOKEN"),env["GITHUB_RUN_ID"],source_sha=env["GITHUB_SHA"],journal=journal,job=job,operation="metadata")
    c.authenticate_actions_job()
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
        slate=choice.document["slate"],control=e.document["catalog"]["methods"]["R0"],offers=offers,bridge=bridge)
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
