"""Explicit operation CLI for the existing single-writer workflow; no cron."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_lab import private_draft_store as s

OPERATIONS=("initialize","pin","boundary","qualify","append","restore")
INPUTS={"initialize":(),"pin":("binding",),"boundary":("binding","before"),"qualify":("binding","before","read_proof"),
        "append":("binding","payload_manifest","qualification"),"restore":("binding","descriptor")}


def checkout_identity(env):
    root=Path(__file__).resolve().parents[1]
    return env.get("GITHUB_WORKSPACE")==str(root) and s.read_local(root/".git/HEAD",4096).decode().strip()==env.get("GITHUB_SHA")


def actions_context(env,permission):
    if (env.get("CI")!="true" or env.get("RUNNER_ENVIRONMENT")!="github-hosted" or not checkout_identity(env)
            or env.get("GITHUB_WORKFLOW_SHA")!=env.get("GITHUB_SHA")
            or env.get("GITHUB_WORKFLOW_REF")!=s.REPO+"/.github/workflows/lab.yml@"+env.get("GITHUB_REF","")
            or not s.re.fullmatch(r"refs/heads/[A-Za-z0-9_./-]+",env.get("GITHUB_REF",""))
            or not s.re.fullmatch(r"[A-Za-z0-9_-]+",env.get("GITHUB_JOB",""))): raise s.StoreError("REAL_ACTIONS_CHECKOUT_REQUIRED")
    return dict(execution_lane="github_actions",workflow_ref=env["GITHUB_WORKFLOW_REF"],workflow_sha=env["GITHUB_SHA"],
                job_id=env["GITHUB_JOB"],permission=permission,event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)


def limits():
    resource.setrlimit(resource.RLIMIT_CPU,(120,120))
    resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(180)


def load(path,cap=256<<10):
    if not path: raise s.StoreError("MISSING_PRIVATE_INPUT")
    return json.loads(s.read_local(path,cap))


def main(argv=None,*,environ=None,transport=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation",choices=OPERATIONS)
    parser.add_argument("--execute",action="store_true")
    for field in ["authorization","authorization-sha256","journal","binding","runtime-id","before","read-proof","qualification","descriptor","payload","payload-manifest","destination","receipt"]:
        parser.add_argument("--"+field)
    args=parser.parse_args(argv)
    # Preparation/help never discovers credentials or starts a transport.
    if not args.execute:
        print(json.dumps(dict(state="PREPARATION_ONLY_NO_IO",private_durability_qualified=False)));return 2
    client=None
    try:
        limits();go=load(args.authorization)
        if s.sha(s.read_local(args.authorization,256<<10))!=args.authorization_sha256: raise s.StoreError("GO_HASH")
        keys={"schema_version","approved","operation","repository","run_id","source_sha","config_sha256","scope_manifest_sha256","qualification_sha256","single_writer_group","runtime_id","input_sha256","job_id","workflow_ref"}
        env=os.environ if environ is None else environ
        permission="read" if args.operation=="boundary" else "write"
        if (set(go)!=keys or go["schema_version"]!="weekly-private-operation-GO-v2.1" or go["approved"] is not True
                or go["operation"]!=args.operation or go["repository"]!=s.REPO or go["config_sha256"]!=s.config_sha()
                or go["single_writer_group"]!="nfl-lab-single-writer"
                or env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_REPOSITORY")!=s.REPO
                or env.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or env.get("GITHUB_RUN_ATTEMPT")!="1"
                or env.get("STORE_PERMISSION")!=permission or env.get("GITHUB_RUN_ID")!=go["run_id"]
                or env.get("GITHUB_SHA")!=go["source_sha"] or go["job_id"]!=env.get("GITHUB_JOB")
                or go["workflow_ref"]!=env.get("GITHUB_WORKFLOW_REF")): raise s.StoreError("OPERATION_GO_OR_JOB_IDENTITY")
        if (not s.re.fullmatch(r"[a-f0-9]{32}",str(go["runtime_id"])) or not isinstance(go["input_sha256"],dict)
                or set(go["input_sha256"])!=set(INPUTS[args.operation])
                or any(not s.HASH.fullmatch(str(v)) for v in go["input_sha256"].values())
                or args.operation!="append" and (go["scope_manifest_sha256"] is not None or go["qualification_sha256"] is not None)):
            raise s.StoreError("EXACT_INPUT_PINS_REQUIRED")
        inputs={}
        for field in INPUTS[args.operation]:
            body=s.read_local(getattr(args,field),256<<10)
            if s.sha(body)!=go["input_sha256"][field]: raise s.StoreError("PHASE_INPUT_HASH")
            inputs[field]=json.loads(body)
        if args.operation=="initialize":
            if args.runtime_id!=go["runtime_id"]: raise s.StoreError("RUNTIME_GO_MISMATCH")
        elif inputs["binding"].get("runtime_id")!=go["runtime_id"]: raise s.StoreError("RUNTIME_GO_MISMATCH")
        job=actions_context(env,permission)
        client=s.Client(env.get("GITHUB_TOKEN"),go["run_id"],journal=args.journal,source_sha=go["source_sha"],transport=transport,job=job,operation=args.operation)
        client.authenticate_actions_job()
        if args.operation=="initialize":
            result=s.initialize(client,args.runtime_id)
        else:
            client.bind(inputs["binding"])
            if args.operation=="pin":result=s.pin_canary(client)
            elif args.operation=="boundary":result=s.boundary(client,inputs["before"])
            elif args.operation=="qualify":result=s.qualify(client,inputs["before"],inputs["read_proof"])
            elif args.operation=="append":
                manifest=inputs["payload_manifest"];qualification=inputs["qualification"]
                if (go["scope_manifest_sha256"]!=s.sha(s.canonical(manifest))
                        or go["qualification_sha256"]!=s.sha(s.canonical(qualification))): raise s.StoreError("PAYLOAD_AUTHORIZATION")
                result=s.append(client,s.read_local(args.payload,s.ASSET_CAP),manifest,qualification)
            else:result=s.restore(client,inputs["descriptor"],args.destination)
        s.create_local(args.receipt,s.canonical(result))
        # No private paths, asset metadata, URLs, headers, bodies or tokens.
        safe=dict(state="COMPLETE",operation=args.operation,receipt_sha256=s.sha(s.canonical(result)),HTTP_calls=client.calls,transfer_bytes=client.transferred,
                  private_durability_qualified=False,restricted_payload_uploaded=args.operation=="append")
        print(json.dumps(safe,sort_keys=True));return 0
    except Exception as error:
        code=error.code if isinstance(error,s.StoreError) else "PRIVATE_STORE_FAILED"
        print(json.dumps(dict(state="FAILED",reason=code,HTTP_calls=client.calls if client else 0,private_durability_qualified=False),sort_keys=True));return 1


if __name__=="__main__":raise SystemExit(main())
