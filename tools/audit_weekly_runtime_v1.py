"""Parent-authorized prepare/acquire/infer child; private output only.

Parent first authenticates the actual current Actions API identity and sealed
owner root GO, all epoch/retained/private completion inputs, then supplies the
closed native authority below. This child does not manufacture API proof.
No token, network, private body or genuine-context discovery without --execute.
Root uses the existing workflow/single scheduler. No export/checkpoint here.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nfl_lab import audit_weekly_runtime_v1 as runtime, audit_weekly_epoch_v1 as epoch
from nfl_lab import audit_count_requalify_v1 as audit, private_draft_store as private
from nfl_lab import gha_private_checkpoint as cp
from nfl_lab.operational_storage import OperationalStorage

REQUEST_KEYS = {"schema_version","approved","repository","code_pins","limits","acquisition_limits",
    "cache","state_root","output","config","inputs","history_binding","prepared","source","choice_completion","historical_sources"}
INPUT_KEYS = {"epoch","epoch_registration","original_choice","original_completion","original_slate",
    "original_catalog","original_policy","choice","retained_restore"}
AUTHORITY_KEYS = {"schema_version","phase","request_sha256","owner_root_go_sha256","repository","source_sha",
    "run_id","run_attempt","job_id","workflow_ref","api_job_id","issued_at_utc","expires_at_utc",
    "actual_actions_api_authenticated","owner_root_checked","fits","public_release"}


def template():
    return dict(schema_version=runtime.VERSION+"-request",approved=False,repository=private.REPO,code_pins=runtime.pins(),
        limits=runtime.LIMITS,acquisition_limits=runtime.ACQUISITION_LIMITS,cache=None,state_root=None,output=None,
        config=dict(history_seasons=[2026],allowed_periods={"2026":[1,2,3,4,5]},
            freshness_seconds=dict(schedule=86400,current_roster=86400,current_statistics=86400,players=604800)),
        inputs={key:None for key in INPUT_KEYS},history_binding=None,prepared=None,source=None,choice_completion=None,historical_sources={})


def context(args,env):
    """Parent's native API attestation plus independent actual checkout checks."""
    from tools.private_draft_store_v2 import actions_context
    from hashlib import sha256
    import subprocess
    runtime.require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == private.REPO
        and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("GITHUB_RUN_ATTEMPT") == "1", "ACTUAL_OWNER_ACTIONS_CHILD_ONLY")
    job=actions_context(env,"write")
    body=env.get("AUDIT_WEEKLY_RUNTIME_AUTHORITY_JSON","").encode()
    runtime.require(0 < len(body) <= 16 << 10 and sha256(body).hexdigest() == env.get("AUDIT_WEEKLY_RUNTIME_AUTHORITY_SHA256"), "EXACT_PARENT_NATIVE_AUTHORITY_HASH")
    authority=cp.strict_json(body)
    runtime.require(body == private.canonical(authority) and set(authority) == AUTHORITY_KEYS
        and authority["schema_version"] == runtime.VERSION+"-native-authority" and authority["phase"] == args.phase
        and authority["request_sha256"] == args.request_sha256 and authority["repository"] == private.REPO
        and authority["actual_actions_api_authenticated"] is authority["owner_root_checked"] is True
        and type(authority["api_job_id"]) is int and authority["api_job_id"] > 0
        and authority["source_sha"] == env.get("GITHUB_SHA") and authority["run_id"] == env.get("GITHUB_RUN_ID")
        and type(authority["run_attempt"]) is int and authority["run_attempt"] == 1
        and authority["job_id"] == job["job_id"] and authority["workflow_ref"] == job["workflow_ref"]
        and type(authority["fits"]) is int and authority["fits"] == 0 and authority["public_release"] is False,
        "CLOSED_ACTUAL_PARENT_NATIVE_AUTHORITY")
    issued,expires=private.utc(authority["issued_at_utc"]),private.utc(authority["expires_at_utc"])
    runtime.require(issued <= runtime.now_utc() < expires and 0 < (expires-issued).total_seconds() <= 3600, "FRESH_PARENT_NATIVE_AUTHORITY")
    event=cp.strict_json(private.read_local(env["GITHUB_EVENT_PATH"],256 << 10))
    root=event.get("inputs",{}).get("inference_builder_go_json","").encode()
    runtime.require(event.get("repository",{}).get("full_name") == private.REPO and root
        and private.HASH.fullmatch(str(authority["owner_root_go_sha256"]))
        and private.sha(root) == authority["owner_root_go_sha256"] == event["inputs"].get("inference_builder_go_sha256"), "ACTUAL_SEALED_OWNER_ROOT_INPUT_REQUIRED")
    from nfl_lab import audit_weekly_operations_authority_v1 as operations_authority
    operations_proof=operations_authority.child(env,root,ROOT)
    dirty=subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",
        ".github","nfl_lab","tools","config","schemas","requirements.lock","requirements-hosted-fixed-build-v1.lock"],cwd=ROOT,text=True)
    runtime.require(dirty == "", "CLEAN_COMMITTED_RUNTIME_SOURCE_REQUIRED")
    root_document=cp.strict_json(root)
    if root_document.get("schema_version") == "audit-weekly-hosted-v5-root-GO":
        from nfl_lab.weekly_mae_display_runtime_v1 import checked_context
        return checked_context(authority,root,operations_proof,env,ROOT)
    return authority


def execute(args,env):
    checked=context(args,env)  # Existing native/API/Root checks precede private reads.
    mae_owner=None
    if type(checked) is dict:
        authority=checked
    else:
        from nfl_lab.weekly_mae_display_runtime_v1 import NativeContext
        runtime.require(type(checked) is NativeContext,"ACTUAL_NATIVE_MAE_CONTEXT_REQUIRED")
        mae_owner=checked;mae_owner.verify();authority=mae_owner.authority
    body=private.read_local(args.request,512 << 10)
    runtime.require(private.sha(body) == args.request_sha256,"EXACT_RUNTIME_REQUEST_HASH")
    p=cp.strict_json(body)
    expected_keys=REQUEST_KEYS if mae_owner is None else REQUEST_KEYS|{"mae_registration"}
    expected_schema=runtime.VERSION+"-request" if mae_owner is None else "audit-weekly-runtime-v2-display-request"
    runtime.require(mae_owner is None or p.get("mae_registration")==mae_owner.registration_ref,
        "SAME_NATIVE_ROOT_MAE_REGISTRATION_REQUIRED")
    runtime.require(body == private.canonical(p) and set(p) == expected_keys and p["approved"] is True
        and p["schema_version"] == expected_schema and p["repository"] == private.REPO
        and p["code_pins"] == runtime.pins() and p["limits"] == runtime.LIMITS
        and p["acquisition_limits"] == runtime.ACQUISITION_LIMITS and set(p["inputs"]) == INPUT_KEYS, "SEALED_EXACT_RUNTIME_REQUEST_REQUIRED")
    numerical=cp.strict_json(private.read_local(ROOT/"config/weekly-owner-private-bootstrap-v1.json",1 << 20))["numerical_environment"]
    runtime.require(all(env.get(k) == v for k,v in numerical.items()),"EXACT_NUMERICAL_STARTUP_ENVIRONMENT")
    runner=private.parents_safe(env["RUNNER_TEMP"])
    runtime.require(all(Path(p[k]).is_absolute() and Path(p[k]).is_relative_to(runner) for k in ("cache","state_root","output")), "PRIVATE_CURRENT_RUNNER_ROOTS_REQUIRED")
    runtime.require((Path(p["cache"])/"operational-storage-v2"/"registry.json").is_file(),"EXISTING_OWNED_RETAINED_STORE_REQUIRED")
    storage=OperationalStorage(p["cache"],ROOT/"config/operational-source-policy-v2.json",state=p["state_root"])
    def read(key,raw=False):return runtime.read_owned(storage,p["inputs"][key],raw=raw)
    # No prediction, HTTP or outcome body in these epoch metadata inputs.
    now=runtime.now_utc()
    corrected=epoch.restore_epoch(read("epoch"),read("original_choice",True),read("original_completion"),read("original_slate"),
        read("original_catalog"),read("original_policy"),history_binding=p["history_binding"],now=now)
    registered=epoch.bind_registration(corrected,read("epoch_registration"),now=now)
    choice_doc=read("choice");choice=epoch.EpochChoice(choice_doc,runtime.digest(choice_doc))
    def progress():runtime.require(runtime.now_utc() < private.utc(authority["expires_at_utc"]),"PARENT_NATIVE_AUTHORITY_EXPIRED")
    options={} if mae_owner is None else {"mae_owner":mae_owner}
    backend=runtime.Runtime(storage,registered,choice,p["inputs"]["retained_restore"],p["config"],progress=progress,**options)
    actual=backend.restored["current"]
    runtime.require(all(actual[key] == authority[key] for key in ("source_sha","run_id","job_id","workflow_ref","api_job_id")), "SAME_ACTUAL_RETAINED_RUNTIME_JOB_REQUIRED")
    if args.phase == "infer":
        def deny(event,unused):
            if event.startswith(("socket.","subprocess.")) or event in {"os.fork","os.forkpty","os.exec","os.posix_spawn","os.system"}:
                raise runtime.RuntimeErrorCode("OFFLINE_INFERENCE_NO_HTTP_OR_CHILDREN")
        sys.addaudithook(deny)
    if args.phase == "prepare":
        ref=backend.prepare(p["output"])
    elif args.phase == "acquire":
        completion=runtime.read_owned(storage,p["choice_completion"])
        ref=backend.acquire(p["prepared"],completion,p["historical_sources"],p["output"])
    else:
        ref=backend.infer(p["prepared"],p["source"],p["output"])
    result=runtime.read_owned(storage,ref)
    return public_summary(result,args.phase,ref["sha256"])


def public_summary(result,phase,result_sha256):
    state=result.get("state","METADATA_PREPARED_PENDING_PARENT_AUTHENTICATED_COMPLETION")
    runtime.require(state in {"METADATA_PREPARED_PENDING_PARENT_AUTHENTICATED_COMPLETION","FRESH_E7_SOURCE_PREPARED",
        "PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE","FAILED_RETAINED","PARTIAL_RETAINED_NOT_QUALIFIED"},"CLOSED_RUNTIME_PHASE_STATUS")
    value=dict(state=state,phase=phase,result_sha256=result_sha256,fits=0,public_release=False,public_export_authorized=False)
    if state in {"FAILED_RETAINED","PARTIAL_RETAINED_NOT_QUALIFIED"}:
        code=result.get("reason","INCOMPLETE_CANDIDATE_CAPTURE" if state=="PARTIAL_RETAINED_NOT_QUALIFIED" else "UPSTREAM_OPERATION_FAILED")
        value["reason"]=code if type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}",code) else "UPSTREAM_OPERATION_FAILED"
    return value


class Quiet:
    def write(self,value):return len(value)
    def flush(self):pass


def main(argv=None,*,environ=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["template","prepare","acquire","infer"])
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--request",type=Path)
    parser.add_argument("--request-sha256")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if args.phase == "template":
        runtime.require(not args.execute and args.output is not None,"LOCAL_TEMPLATE_ONLY")
        private.create_local(args.output,private.canonical(template()))
        print('{"state":"PREPARED_UNAPPROVED","fits":0,"public_release":false}')
        return 0
    if not args.execute:
        print('{"state":"PREPARATION_ONLY_NO_IO","fits":0,"public_release":false}')
        return 2
    try:
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
        runtime.require(args.request is not None and args.request_sha256 is not None,"EXACT_RUNTIME_REQUEST_REQUIRED")
        env=os.environ if environ is None else environ
        sampler="tools/review_direct_booster_screen_guard_v4.py"
        envelope=dict(runtime_envelopes=audit.shared_envelopes(),code_pins={sampler:private.sha(private.read_local(ROOT/sampler,1 << 20))})
        with redirect_stdout(Quiet()),redirect_stderr(Quiet()):
            with audit.resource_envelope(envelope,"requalify",ROOT):
                import pyarrow as pa
                import threadpoolctl
                from tools.ngboost_law_software_v1 import process_free_threads
                pa.set_cpu_count(2);pa.set_io_thread_count(2);pa.set_memory_pool(pa.system_memory_pool())
                libc=Path("/usr/lib/x86_64-linux-gnu/libc.so.6").resolve(strict=True)
                binding=dict(path=str(libc),bytes=libc.stat().st_size,sha256=private.sha(private.read_local(libc,8 << 20)))
                with process_free_threads(threadpoolctl,binding),threadpoolctl.threadpool_limits(limits=2):
                    result=execute(args,env)
        print(json.dumps(result,sort_keys=True))
        return 0 if result["state"] not in {"FAILED_RETAINED","PARTIAL_RETAINED_NOT_QUALIFIED"} else 1
    except Exception as error:
        print(json.dumps(dict(state="FAILED_RETAINED",reason=runtime.reason(error),fits=0,public_release=False,public_export_authorized=False),sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
