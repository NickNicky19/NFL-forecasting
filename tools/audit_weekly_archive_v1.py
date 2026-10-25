"""Explicit private weekly archive child in the existing lab workflow.

Parent supplies a sealed request and a fresh native authority after checking
the owner root GO/actual Actions API identity. This child independently checks
the actual source, job API, qualified rotation/canary and predecessor proofs.
No import/help/template operation discovers credentials or starts transport.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout,redirect_stderr
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nfl_lab import audit_weekly_archive_v1 as archive
from nfl_lab import private_draft_store as store,gha_private_checkpoint as cp
from nfl_lab.operational_storage import OperationalStorage

REQUEST_KEYS={"schema_version","approved","repository","phase","helper_sha256","limits","jobs","cache","state_root",
    "local_root","output","qualified_runtime","pending_census","pending_reservations","runtime_root","context","r0","handoff","reader_handoff"}
AUTHORITY_KEYS={"schema_version","phase","request_sha256","owner_root_go_sha256","repository","source_sha","run_id","run_attempt",
    "job_id","workflow_ref","api_job_id","issued_at_utc","expires_at_utc","actual_actions_api_authenticated","owner_root_checked","fits","public_release"}


def template():
    return dict(schema_version=archive.VERSION+"-request",approved=False,repository=store.REPO,phase=None,helper_sha256=archive.pins(),
        limits=archive.LIMITS,jobs=dict(produce=None,restore=None,consume=None),cache=None,state_root=None,local_root=None,output=None,
        qualified_runtime=None,pending_census=None,pending_reservations=[],runtime_root=None,
        context={role:None for role in archive.CONTEXT},r0=None,handoff=None,reader_handoff=None)


def guard(args,env):
    from tools.private_draft_store_v2 import actions_context
    import subprocess
    archive.require(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")==store.REPO
        and env.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and env.get("GITHUB_RUN_ATTEMPT")=="1"
        and env.get("GITHUB_ACTOR")=="NickNicky19" and env.get("GITHUB_ACTOR_ID")=="208912933"
        and env.get("STORE_PERMISSION")=="write","GENUINE_OWNER_ARCHIVE_ACTIONS_REQUIRED")
    job=actions_context(env,"write")
    raw=env.get("AUDIT_WEEKLY_ARCHIVE_AUTHORITY_JSON","").encode()
    archive.require(0<len(raw)<=16384 and store.sha(raw)==env.get("AUDIT_WEEKLY_ARCHIVE_AUTHORITY_SHA256"),"EXACT_ARCHIVE_NATIVE_AUTHORITY_HASH")
    value=cp.strict_json(raw)
    archive.require(store.canonical(value)==raw and set(value)==AUTHORITY_KEYS
        and value["schema_version"]==archive.VERSION+"-native-authority" and value["phase"]==args.phase
        and value["request_sha256"]==args.request_sha256 and value["repository"]==store.REPO
        and value["source_sha"]==env.get("GITHUB_SHA") and value["run_id"]==env.get("GITHUB_RUN_ID")
        and type(value["run_attempt"]) is int and value["run_attempt"]==1
        and value["job_id"]==job["job_id"] and value["workflow_ref"]==job["workflow_ref"]
        and type(value["api_job_id"]) is int and value["api_job_id"]>0
        and value["actual_actions_api_authenticated"] is value["owner_root_checked"] is True
        and type(value["fits"]) is int and value["fits"]==0 and value["public_release"] is False,"CLOSED_ARCHIVE_NATIVE_AUTHORITY")
    issued,expires=store.utc(value["issued_at_utc"]),store.utc(value["expires_at_utc"])
    archive.require(issued<=datetime_now()<expires and 0<(expires-issued).total_seconds()<=3600,"FRESH_ARCHIVE_PHASE_AUTHORITY")
    event=cp.strict_json(store.read_local(env["GITHUB_EVENT_PATH"],256 << 10))
    root=event.get("inputs",{}).get("inference_builder_go_json","").encode()
    archive.require(event.get("repository",{}).get("full_name")==store.REPO and root
        and store.sha(root)==value["owner_root_go_sha256"]==event["inputs"].get("inference_builder_go_sha256"),"EXACT_ACTUAL_ARCHIVE_OWNER_ROOT_INPUT")
    dirty=subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",
        ".github","nfl_lab","tools","config","schemas","requirements.lock","requirements-hosted-fixed-build-v1.lock"],cwd=ROOT,text=True)
    archive.require(dirty=="","CLEAN_COMMITTED_ARCHIVE_SOURCE_REQUIRED")
    return value,job


def datetime_now():
    from datetime import datetime,timezone
    return datetime.now(timezone.utc)


def output_handle(env):
    archive.require(env.get("GITHUB_OUTPUT"),"ACTUAL_ARCHIVE_HANDOFF_OUTPUT_REQUIRED")
    parent,name=store.parent_fd(env["GITHUB_OUTPUT"])
    try:
        fd=os.open(name,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW,dir_fd=parent)
        archive.require(stat.S_ISREG(os.fstat(fd).st_mode),"REGULAR_ARCHIVE_OUTPUT_HANDLE")
        return fd
    finally:os.close(parent)


def run(args,env,*,transport=None):
    authority,job=guard(args,env)
    raw=store.read_local(args.request,512 << 10)
    archive.require(store.sha(raw)==args.request_sha256,"EXACT_ARCHIVE_REQUEST_HASH")
    p=cp.strict_json(raw)
    archive.require(raw==store.canonical(p) and set(p)==REQUEST_KEYS and p["approved"] is True
        and p["schema_version"]==archive.VERSION+"-request" and p["repository"]==store.REPO and p["phase"]==args.phase
        and p["helper_sha256"]==archive.pins() and p["limits"]==archive.LIMITS
        and set(p["jobs"])=={"produce","restore","consume"} and p["jobs"][args.phase]==job["job_id"],"SEALED_CLOSED_ARCHIVE_REQUEST")
    numerical=cp.strict_json(store.read_local(ROOT/"config/weekly-owner-private-bootstrap-v1.json",1 << 20))["numerical_environment"]
    archive.require(all(env.get(k)==v for k,v in numerical.items()),"EXACT_ARCHIVE_NUMERICAL_STARTUP_ENVIRONMENT")
    package=cp.strict_json(cp.read_ref(p["qualified_runtime"],64 << 10))
    runner=store.parents_safe(env["RUNNER_TEMP"])
    archive.require(all(Path(p[k]).is_absolute() and Path(p[k]).is_relative_to(runner) for k in ("cache","state_root","local_root","output"))
        and Path(p["output"]).is_relative_to(Path(p["local_root"])) and not Path(p["local_root"]).exists(),"FRESH_PRIVATE_ARCHIVE_RUNNER_ROOTS")
    fd=output_handle(env) if args.phase!="consume" else None
    try:
        storage=OperationalStorage(p["cache"],ROOT/"config/operational-source-policy-v2.json",state=p["state_root"])
        storage.register_root(p["local_root"])
        journal=Path(p["local_root"])/"journal";journal.mkdir(mode=0o700)
        cp.seed_pending(journal,p["pending_reservations"])
        class Factory:
            def __init__(self):self.clients=[]
            def __call__(self,operation):
                archive.require(len(self.clients)<archive.MAX_CLIENTS and operation in ({"restore"} if args.phase=="consume" else {"append","restore"}),"FINITE_ARCHIVE_NATIVE_OPERATIONS")
                archive.require(datetime_now()<store.utc(authority["expires_at_utc"]),"ARCHIVE_AUTHORITY_EXPIRED")
                class QuotaClient(archive.Client):
                    def reserve(self,key,body,*,name=None):
                        with storage.transaction():
                            storage._require(archive.ENTRY_CAP)
                            return super().reserve(key,body,name=name)
                client=QuotaClient(env.get("GITHUB_TOKEN"),env["GITHUB_RUN_ID"],journal=journal,source_sha=env["GITHUB_SHA"],
                    job=job,operation=operation,qualification=package["qualification"],readonly=args.phase=="consume",transport=transport)
                self.clients.append(client);client.authenticate_actions_job()
                archive.require(client.job["api_job_id"]==authority["api_job_id"],"ACTUAL_API_JOB_MATCHES_PARENT_AUTHORITY")
                client.bind(package["binding"])
                return client
        factory=Factory()
        if args.phase=="produce":
            # Genuine current identity and rotated qualification precede any
            # forecast/feature body read. Reuse this client for the first POST.
            first=factory("append");archive.authenticate_qualification(first,package,p["pending_census"]);archive.jobs_for(first)
            snapshot=archive.collect(p["runtime_root"],p["context"],storage=storage,output=Path(p["local_root"])/"collection",r0=p["r0"])
            used=False
            def reuse(operation):
                nonlocal used
                if not used:used=True;return first
                return factory(operation)
            handoff=archive.produce(snapshot,reuse,package,storage=storage,output=p["output"],root_go_sha256=authority["owner_root_go_sha256"],
                jobs=p["jobs"],pending_census=p["pending_census"],pending=p["pending_reservations"])
            body=archive.safe_handoff(handoff)
            summary=dict(state="PRIVATE_CAPTURE_APPENDED_RESTORE_REQUIRED",archive_state=handoff["archive_state"],handoff_sha256=store.sha(body))
            key="archive_handoff"
        else:
            handoff=p["handoff"] if args.phase=="restore" else p["reader_handoff"]["archive"]
            archive.require(handoff["jobs"]==p["jobs"],"EXACT_CURRENT_ARCHIVE_WORKFLOW_ROLES")
            result=archive.restore(handoff,factory,package,storage=storage,output=p["output"],root_go_sha256=authority["owner_root_go_sha256"],
                pending_census=p["pending_census"],reader_handoff=p["reader_handoff"] if args.phase=="consume" else None)
            summary=dict(state=result["state"],result_sha256=store.sha(store.canonical(result)),replay_ready=result["replay_ready"],model_replay_performed=False)
            if args.phase=="restore":
                body=store.read_local(Path(p["output"])/"READER_HANDOFF.json",16384);key="archive_reader_handoff"
                cp.strict_json(body)
        summary.update(fits=0,successful_forecast=False,public_release=False,scope_qualified_for_publication=False,
            HTTP_calls=sum(c.calls for c in factory.clients))
        if fd is not None:
            archive.require(len(body)<=16384 and b"\n" not in body,"BOUNDED_CANONICAL_ARCHIVE_HANDOFF_OUTPUT")
            os.write(fd,(key+"_json="+body.decode()+"\n"+key+"_sha256="+store.sha(body)+"\n").encode())
            os.fsync(fd)
        return summary
    finally:
        if fd is not None:os.close(fd)


class Quiet:
    def write(self,value):return len(value)
    def flush(self):pass


def main(argv=None,*,environ=None,transport=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["template","produce","restore","consume"])
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--request",type=Path);parser.add_argument("--request-sha256");parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if args.phase=="template":
        archive.require(not args.execute and args.output is not None,"UNAPPROVED_ARCHIVE_TEMPLATE_ONLY")
        store.create_local(args.output,store.canonical(template()));print('{"state":"PREPARED_UNAPPROVED","public_release":false}');return 0
    if not args.execute:print('{"state":"PREPARATION_ONLY_NO_IO","public_release":false}');return 2
    try:
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
        archive.require(args.request is not None and args.request_sha256 is not None,"ARCHIVE_REQUEST_REQUIRED")
        from tools.private_draft_store_v2 import limits
        limits()  # Original120CPU/512MiB-AS/native SIG_DFL180s; separate child.
        with redirect_stdout(Quiet()),redirect_stderr(Quiet()):
            result=run(args,os.environ if environ is None else environ,transport=transport)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as error:
        code=error.code if isinstance(error,store.StoreError) else "ARCHIVE_OPERATION_FAILED_NO_RETRY"
        if not isinstance(code,str) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code) is None:code="ARCHIVE_OPERATION_FAILED_NO_RETRY"
        print(json.dumps(dict(state="FAILED_ARCHIVE_RETAINED",reason=code,successful_forecast=False,public_release=False),sort_keys=True));return 1


if __name__=="__main__":raise SystemExit(main())
