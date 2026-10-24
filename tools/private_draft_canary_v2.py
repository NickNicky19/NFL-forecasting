"""Four canary-only CLI operations across three existing-workflow jobs.

No credential is read here. Source/config verification precedes importing the
store; genuine automatic-token access is confined to separately guarded CLIs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"config/private-draft-canary-v2.json"
CONFIG_SHA256="5d65f67c103b192e9fb65b6cea5b39d7f1ae8d28e0a3fbf66d61b7dc7e0c24ea"
REPO="NickNicky19/NFL-forecasting"
MODE="private-draft-canary-v2"
RUNTIME=hashlib.sha256(b"NFLweeklyruntime20261024v2").hexdigest()[:32]
JOBS={"write":"private-draft-v2-write","read":"private-draft-v2-read","qualify":"private-draft-v2-qualify"}
OPERATIONS={"write":("initialize","pin"),"read":("boundary",),"qualify":("qualify",)}
PINNED_FILES={"nfl_lab/__init__.py","nfl_lab/private_draft_store.py","nfl_lab/private_draft_probe_helpers.py","tools/private_draft_store_v2.py","schemas/private-draft-store-v2.json","config/private-draft-storage-v2.json",".github/workflows/lab.yml"}


class CanaryError(Exception):pass


def digest(body):return hashlib.sha256(body).hexdigest()
def canonical(doc):return json.dumps(doc,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def safe_read(path,cap):
    path=Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file() or path.stat().st_size>cap:raise CanaryError("SOURCE_OR_INPUT_BOUND")
    body=path.read_bytes()
    if len(body)>cap:raise CanaryError("SOURCE_OR_INPUT_BOUND")
    return body


def verify_sources():
    body=safe_read(CONFIG,16384)
    if digest(body)!=CONFIG_SHA256:raise CanaryError("CANARY_CONFIG_HASH")
    config=json.loads(body)
    if (config.get("schema_version")!="weekly-private-canary-driver-v2" or config.get("runtime_id")!=RUNTIME
            or config.get("mode")!=MODE or config.get("operations")!={k:list(v) for k,v in OPERATIONS.items()}
            or config.get("restricted_payload_operations")!=[] or config.get("root_dispatch_required") is not True
            or set(config.get("source_sha256",{}))!=PINNED_FILES):raise CanaryError("CANARY_SCOPE")
    for name,expected in config["source_sha256"].items():
        if digest(safe_read(ROOT/name,2<<20))!=expected:raise CanaryError("PINNED_SOURCE_CHANGED")
    return config


def preflight(phase,env):
    config=verify_sources()
    if (phase not in JOBS or env.get("GITHUB_ACTIONS")!="true" or env.get("CI")!="true" or env.get("RUNNER_ENVIRONMENT")!="github-hosted"
            or env.get("GITHUB_REPOSITORY")!=REPO or env.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
            or env.get("GITHUB_RUN_ATTEMPT")!="1" or env.get("CANARY_MODE")!=MODE or env.get("GITHUB_JOB")!=JOBS[phase]
            or env.get("STORE_PERMISSION")!=("read" if phase=="read" else "write")
            or not re.fullmatch(r"[1-9][0-9]{0,19}",env.get("GITHUB_RUN_ID",""))
            or not re.fullmatch(r"[a-f0-9]{40}",env.get("GITHUB_SHA","")) or env.get("GITHUB_WORKFLOW_SHA")!=env.get("GITHUB_SHA")
            or env.get("GITHUB_WORKSPACE")!=str(ROOT) or safe_read(ROOT/".git/HEAD",4096).decode().strip()!=env.get("GITHUB_SHA")
            or env.get("GITHUB_WORKFLOW_REF")!=REPO+"/.github/workflows/lab.yml@"+env.get("GITHUB_REF","")):
        raise CanaryError("HOSTED_CANARY_CONTEXT_REQUIRED")
    event=json.loads(safe_read(env.get("GITHUB_EVENT_PATH",""),256<<10))
    if (event.get("inputs",{}).get("mode")!=MODE or event.get("repository",{}).get("full_name")!=REPO
            or event.get("ref") not in {env["GITHUB_REF"],env["GITHUB_REF"].removeprefix("refs/heads/")}):raise CanaryError("DISPATCH_SCOPE_REQUIRED")
    return config


def handoff(env,label):
    text=env.get("CANARY_"+label.upper()+"_JSON","")
    expected=env.get("CANARY_"+label.upper()+"_SHA256","")
    if len(text.encode())>65536 or not re.fullmatch(r"[a-f0-9]{64}",expected):raise CanaryError("HANDOFF_BOUND")
    document=json.loads(text)
    if canonical(document).decode()!=text or digest(text.encode())!=expected:raise CanaryError("HANDOFF_HASH_OR_CANONICAL")
    return document


def make_go(operation,inputs,env,config,store):
    if operation not in {"initialize","pin","boundary","qualify"}:raise CanaryError("NO_PAYLOAD_OPERATION")
    return dict(schema_version="weekly-private-operation-GO-v2.1",approved=True,operation=operation,repository=REPO,
        run_id=env["GITHUB_RUN_ID"],source_sha=env["GITHUB_SHA"],config_sha256=store.config_sha(),scope_manifest_sha256=None,
        qualification_sha256=None,single_writer_group="nfl-lab-single-writer",runtime_id=config["runtime_id"],
        input_sha256={k:digest(canonical(v)) for k,v in inputs.items()},job_id=env["GITHUB_JOB"],workflow_ref=env["GITHUB_WORKFLOW_REF"])


def run_cli(argv,timeout):
    child=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        stdout,stderr=child.communicate(timeout=timeout)
        if len(stdout.encode())>16384 or len(stderr.encode())>16384:raise CanaryError("CANARY_CLI_OUTPUT_BOUND")
        if child.returncode!=0:
            safe=dict(operation=argv[4],state="FAILED",exit_code=child.returncode,reason="CANARY_CLI_TERMINATED",HTTP_calls=None)
            try:
                failed=json.loads(stdout)
                if (set(failed)=={"state","reason","HTTP_calls","private_durability_qualified"} and failed["state"]=="FAILED"
                        and isinstance(failed["reason"],str) and re.fullmatch(r"[A-Z0-9_]{1,80}",failed["reason"])
                        and type(failed["HTTP_calls"]) is int and 0<=failed["HTTP_calls"]<=40 and failed["private_durability_qualified"] is False):
                    safe.update(reason=failed["reason"],HTTP_calls=failed["HTTP_calls"])
            except (ValueError,TypeError):pass
            print("PRIVATE_DRAFT_CANARY_CLI_FAILURE_V2 "+json.dumps(safe,sort_keys=True))
            raise CanaryError("CANARY_CLI_FAILED")
        result=json.loads(stdout)
        if result.get("state")!="COMPLETE":raise CanaryError("CANARY_CLI_FAILED")
        return result
    except subprocess.TimeoutExpired:
        raise CanaryError("CANARY_CLI_DEADLINE") from None
    finally:
        if child.poll() is None:child.kill()
        child.wait()  # CLI starts no descendants; outer timeout kills whole group.


def run_operation(operation,inputs,env,config,store,directory,deadline,runner):
    go=make_go(operation,inputs,env,config,store);go_path=directory/(operation+"-GO.json")
    store.create_local(go_path,canonical(go));receipt=directory/(operation+"-receipt.json")
    argv=[sys.executable,"-I","-B",str(ROOT/"tools/private_draft_store_v2.py"),operation,"--execute","--authorization",str(go_path),
          "--authorization-sha256",digest(canonical(go)),"--journal",str(directory/"journal"),"--receipt",str(receipt)]
    if operation=="initialize":argv +=["--runtime-id",RUNTIME]
    for key,value in inputs.items():
        path=directory/(operation+"-"+key+".json");store.create_local(path,canonical(value));argv +=["--"+key.replace("_","-"),str(path)]
    remaining=deadline-time.monotonic()
    if remaining<=0:raise CanaryError("CANARY_PHASE_DEADLINE")
    result=runner(argv,min(180,remaining))
    body=store.read_local(receipt,65536);document=json.loads(body)
    if (canonical(document)!=body or result.get("receipt_sha256")!=digest(body) or result.get("operation")!=operation
            or type(result.get("HTTP_calls")) is not int or not 0<=result["HTTP_calls"]<=40
            or result.get("restricted_payload_uploaded") is not False or result.get("private_durability_qualified") is not False):raise CanaryError("CANARY_CHILD_RECEIPT")
    return document,result["HTTP_calls"]


def public_safe(doc):
    body=canonical(doc)
    if len(body)>65536 or any(marker in body for marker in [b"https://",b"http://",b"/workspace/",b"/tmp/",b"ghs_"]):raise CanaryError("UNSAFE_CANARY_METADATA")
    return body.decode()


def output_records(env,records,store):
    path=env.get("GITHUB_OUTPUT","")
    parent,name=store.parent_fd(path)
    try:fd=os.open(name,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW,dir_fd=parent)
    finally:os.close(parent)
    try:
        with os.fdopen(os.dup(fd),"a") as stream:
            for label,doc in records.items():
                text=public_safe(doc);stream.write(label+"_json="+text+"\n"+label+"_sha256="+digest(text.encode())+"\n")
            stream.flush();os.fsync(stream.fileno())
    finally:os.close(fd)


def run_phase(phase,env,config,*,runner=run_cli):
    # All target imports occur after the entrypoint's config/code/schema pins.
    if phase not in JOBS or config!=verify_sources():raise CanaryError("PINNED_CANARY_PHASE_REQUIRED")
    sys.path.insert(0,str(ROOT))
    from nfl_lab import private_draft_store as store
    directory=store.parents_safe(Path(env["RUNNER_TEMP"])/("weekly-canary-v2-"+env["GITHUB_RUN_ID"]+"-"+phase))
    directory.mkdir(mode=0o700);(directory/"journal").mkdir(mode=0o700)
    # Check output destination before allowing the first harmless POST.
    output_records(env,{},store)
    deadline=time.monotonic()+(360 if phase=="write" else 180);calls=0
    verifier=SimpleNamespace(run_id=env["GITHUB_RUN_ID"],source_sha=env["GITHUB_SHA"],process=store.process_identity(),job=dict(execution_lane="github_actions",workflow_ref=env["GITHUB_WORKFLOW_REF"]))
    records={};qualified_proof=None
    if phase=="write":
        binding,n=run_operation("initialize",{},env,config,store,directory,deadline,runner);calls+=n
    else:binding=handoff(env,"binding")
    store.checked_binding(binding)
    if binding["runtime_id"]!=RUNTIME or binding["origin_run_id"]!=env["GITHUB_RUN_ID"]:raise CanaryError("EXACT_NEW_CANARY_REQUIRED")
    verifier.binding=binding
    if phase=="write":
        # Preserve harmless destination identity even if the later pin fails.
        print("PRIVATE_DRAFT_CANARY_INITIALIZED_V2 "+public_safe(binding))
        before,n=run_operation("pin",dict(binding=binding),env,config,store,directory,deadline,runner);calls+=n
        store.check_proof(verifier,before,"write_pin")
        if before["job"]["job_id"]!=JOBS["write"]:raise CanaryError("WRITE_JOB_PROOF")
        records=dict(binding=binding,before=before)
    else:
        before=handoff(env,"before");store.check_proof(verifier,before,"write_pin")
        if before["job"]["job_id"]!=JOBS["write"]:raise CanaryError("WRITE_JOB_PROOF")
        if phase=="read":
            read,n=run_operation("boundary",dict(binding=binding,before=before),env,config,store,directory,deadline,runner);calls+=n
            store.check_proof(verifier,read,"read_boundary")
            if read["job"]["job_id"]!=JOBS["read"]:raise CanaryError("READ_JOB_PROOF")
            records=dict(read=read)
        else:
            read=handoff(env,"read");store.check_proof(verifier,read,"read_boundary")
            if read["job"]["job_id"]!=JOBS["read"]:raise CanaryError("READ_JOB_PROOF")
            proof,n=run_operation("qualify",dict(binding=binding,before=before,read_proof=read),env,config,store,directory,deadline,runner);calls+=n
            store.check_proof(verifier,proof,"qualified")
            if proof["job"]["job_id"]!=JOBS["qualify"]:raise CanaryError("QUALIFY_JOB_PROOF")
            qualified_proof=proof
    if calls>40*len(OPERATIONS[phase]) or time.monotonic()>deadline:raise CanaryError("CANARY_PHASE_BUDGET")
    output_records(env,records,store)
    if qualified_proof is not None:
        print("PRIVATE_DRAFT_CANARY_BINDING_V2 "+public_safe(binding))
        print("PRIVATE_DRAFT_CANARY_QUALIFICATION_V2 "+public_safe(qualified_proof))
    print(json.dumps(dict(state="CANARY_PHASE_COMPLETE",phase=phase,HTTP_calls=calls,restricted_payload_uploaded=False,strict_v1_unchanged="INCONCLUSIVE"),sort_keys=True))
    return records


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("phase",choices=tuple(JOBS));parser.add_argument("--execute",action="store_true");args=parser.parse_args(argv)
    if not args.execute:print('{"state":"CANARY_PREPARATION_ONLY_NO_IO"}');return 2
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
        config=preflight(args.phase,os.environ)
        run_phase(args.phase,os.environ,config);return 0
    except Exception as error:
        reason=getattr(error,"code",error.args[0] if isinstance(error,CanaryError) and error.args else "CANARY_DRIVER_GUARD")
        if not isinstance(reason,str) or not re.fullmatch(r"[A-Z0-9_]{1,80}",reason):reason="CANARY_DRIVER_GUARD"
        print(json.dumps(dict(state="CANARY_DRIVER_FAILED",reason=reason,restricted_payload_uploaded=False),sort_keys=True));return 1


if __name__=="__main__":raise SystemExit(main())
