"""Prepare unapproved retained metadata templates, or genuinely restore once.

Parent wiring: existing lab.yml dispatch mode audit-count-retained-v1; current
job contents:write/actions:read; automatic GITHUB_TOKEN and STORE_PERMISSION=write;
AUDIT_COUNT_RETAINED_GO_JSON/SHA256 from inference_builder_go_json/SHA256 inputs.
The fresh owner GO binds the registration and current source/workflow/job. The
actual current run is authenticated and attested at runtime, never predicted.
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
from nfl_lab import audit_count_retained_v1 as retained, audit_count_requalify_v1 as audit
from nfl_lab import gha_private_checkpoint as cp, private_draft_store as store, owner_private_bootstrap as owner


class Quiet:
    def write(self,value):
        return len(value)

    def flush(self):
        pass


def run(args, env, *, transport=None):
    body = store.read_local(args.registration,retained.REGISTRATION_CAP)
    retained.require(store.sha(body) == args.registration_sha256,"EXACT_RETAINED_REGISTRATION_HASH")
    registration = retained.validate_registration(cp.strict_json(body))
    retained.require(body == store.canonical(registration),"CANONICAL_RETAINED_REGISTRATION_REQUIRED")
    go_body = env.get("AUDIT_COUNT_RETAINED_GO_JSON","").encode()
    retained.require(0 < len(go_body) <= retained.GO_CAP and store.sha(go_body) == env.get("AUDIT_COUNT_RETAINED_GO_SHA256"),
        "EXACT_FRESH_RETAINED_GO_HASH")
    go = cp.strict_json(go_body)
    retained.require(go_body == store.canonical(go),"CANONICAL_CURRENT_RETAINED_GO")
    job = retained.validate_go(go,args.registration_sha256,env,ROOT)
    retained.require(env["GITHUB_RUN_ID"] != registration["origin"]["run_id"]
        and store.utc(registration["registered_at_utc"]) <= store.utc(go["issued_at_utc"]),"NEW_AUTHORITY_AFTER_RETAINED_REGISTRATION")
    retained.require(retained.model_pins(ROOT) == registration["model_code_sha256"],"REQUALIFICATION_REQUIRED_MODEL_CODE_CHANGED")
    numerical = cp.strict_json(store.read_local(ROOT/"config/weekly-owner-private-bootstrap-v1.json",1 << 20))["numerical_environment"]
    retained.require(all(env.get(k) == v for k,v in numerical.items()),"EXACT_RETAINED_NUMERICAL_STARTUP")
    policy_body = store.read_local(ROOT/"config/operational-source-policy-v2.json",1 << 20)
    retained.require(store.sha(policy_body) == cp.POLICY_SHA,"EXACT_RETAINED_SOURCE_POLICY")
    archived = cp.strict_json(store.read_local(ROOT/"reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json",store.META_CAP))
    binding, qualification = archived["binding"],archived["qualification"]
    retained.require(binding == registration["origin"]["handoff"]["runtime_binding"]
        and store.sha(store.canonical(binding)) == registration["qualified_runtime"]["binding_sha256"]
        and store.sha(store.canonical(qualification)) == registration["qualified_runtime"]["qualification_sha256"],
        "EXACT_RETAINED_QUALIFIED_RUNTIME")
    owner.archived_qualification(binding,qualification)
    from nfl_lab.operational_storage import OperationalStorage
    root = store.parents_safe(env["RUNNER_TEMP"])/(retained.VERSION+"-"+env["GITHUB_RUN_ID"])
    retained.require(not root.exists(),"ONE_RETAINED_INVOCATION_NO_RETRY")
    root.mkdir(mode=0o700)
    storage = OperationalStorage(root/"cache",cp.strict_json(policy_body),state=root/"state")
    storage.register_root(root)
    journal = root/"journal"
    journal.mkdir(mode=0o700)
    with storage.transaction():
        storage._require(64 << 10)
        cp.seed_pending(journal,registration["pending_reservations"])
    class Factory:
        def __init__(self):
            self.clients=[]
            self.qualification=qualification

        def __call__(self,operation):
            retained.require(operation == "restore" and len(self.clients) < 9,"NINE_GET_ONLY_RETAINED_OPERATIONS")
            client = retained.ReadClient(env.get("GITHUB_TOKEN"),env["GITHUB_RUN_ID"],journal=journal,
                source_sha=env["GITHUB_SHA"],job=job,operation="restore",transport=transport,
                extra_routes=retained.routes(registration,qualification))
            self.clients.append(client)
            client.authenticate_actions_job()
            client.bind(binding)
            return client
    factory = Factory()
    envelope = dict(runtime_envelopes=audit.shared_envelopes(),code_pins={
        "tools/review_direct_booster_screen_guard_v4.py":go["helper_sha256"]["tools/review_direct_booster_screen_guard_v4.py"]})
    def before_replay():
        def deny(event,unused):
            if event.startswith(("socket.","subprocess.")) or event in {"os.fork","os.forkpty","os.exec","os.posix_spawn","os.system"}:
                raise RuntimeError("RETAINED_REPLAY_NO_HTTP_OR_CHILDREN")
        sys.addaudithook(deny)
        import pyarrow as pa
        pa.set_cpu_count(2);pa.set_io_thread_count(2);pa.set_memory_pool(pa.system_memory_pool())
    def check_authority():
        retained.require(retained.now() < store.utc(go["expires_at_utc"]),"RETAINED_GO_EXPIRED_BEFORE_READ")
    try:
        # Use the existing420s/300CPU/4GiB-AS/1GiB-RSS reader envelope once.
        # Setting a512MiB hard limit first would prevent this larger phase.
        with audit.resource_envelope(envelope,"requalify",ROOT) as resources:
            result = retained.restore(registration,factory,storage=storage,output=root/"retained",
                current_go_sha256=store.sha(go_body),before_replay=before_replay,check_authority=check_authority)
        storage.write_bytes(root/"RESOURCE_FINISHED.json",store.canonical(resources))
        return dict(state=result["state"],model_pairs=18,fits=0,remote_writes=0,protected_outcome_reads=0,
            successful_forecast=False,public_release=False,catalog_epoch_ready=False,weekly_choice_restored=False,
            receipt_sha256=store.sha(store.canonical(result)),HTTP_calls=sum(c.calls for c in factory.clients))
    except BaseException:
        try:
            storage.write_bytes(root/"FAILED_RETAINED.json",store.canonical(dict(schema_version=retained.VERSION,
                state="RETAINED_RESTORE_FAILED_NO_RETRY",fits=0,remote_writes=0,successful_forecast=False,public_release=False)))
        except Exception:
            pass
        raise


def main(argv=None, *, environ=None, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["prepare","restore"])
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--registration",type=Path)
    parser.add_argument("--registration-sha256")
    parser.add_argument("--verification",type=Path)
    parser.add_argument("--catalog",type=Path)
    parser.add_argument("--handoff",type=Path)
    parser.add_argument("--check-run-id",type=int)
    parser.add_argument("--origin-conclusion",choices=["success","failure"])
    args = parser.parse_args(argv)
    if args.phase == "restore" and not args.execute:
        print('{"state":"PREPARATION_ONLY_NO_IO","fits":0,"public_release":false}')
        return 2
    try:
        with redirect_stdout(Quiet()),redirect_stderr(Quiet()):
            if args.phase == "prepare":
                retained.require(args.output is not None and not args.execute,"LOCAL_PREPARATION_ONLY")
                inputs=(args.verification,args.catalog,args.handoff,args.check_run_id)
                retained.require(all(v is not None for v in inputs) or all(v is None for v in inputs),"COMPLETE_RETAINED_METADATA_INPUTS")
                if args.verification is None:
                    registration,go=retained.templates(ROOT)
                else:
                    registration,go=retained.prepare_from_metadata(ROOT,*inputs,run_conclusion=args.origin_conclusion)
                output=store.parents_safe(args.output)
                retained.require(not output.exists(),"FRESH_RETAINED_PREPARATION_ROOT")
                output.mkdir(parents=True,mode=0o700)
                store.create_local(output/"REGISTRATION.template.json",store.canonical(registration))
                store.create_local(output/"GO.template.json",store.canonical(go))
                result=dict(state="PREPARED_UNREGISTERED",approved=False,registration_sha256=store.sha(store.canonical(registration)),
                    fits=0,private_body_reads=0,remote_writes=0,public_release=False)
            else:
                retained.require(args.registration is not None and args.registration_sha256 is not None,"RETAINED_REGISTRATION_INPUTS_REQUIRED")
                result=run(args,os.environ if environ is None else environ,transport=transport)
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception as error:
        code=error.code if isinstance(error,store.StoreError) else "RETAINED_ADAPTER_GUARD_OR_OPERATION_FAILED"
        if not isinstance(code,str) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code) is None:
            code="RETAINED_ADAPTER_GUARD_OR_OPERATION_FAILED"
        print(json.dumps(dict(state="FAILED_RETAINED",reason=code,fits=0,remote_writes=0,successful_forecast=False,public_release=False),sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
