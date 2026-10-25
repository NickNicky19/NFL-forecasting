"""Parent-native authority child: GET-only original input/choice recovery."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import resource
import signal
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("recover",));parser.add_argument("--execute",action="store_true")
    parser.add_argument("--request");parser.add_argument("--request-sha256")
    args=parser.parse_args(argv)
    if not args.execute:
        print('{"state":"ORIGIN_PREPARATION_ONLY_NO_IO"}');return 2
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    try:
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
        resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
        signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(180)
        from nfl_lab import audit_weekly_origin_v1 as origin,private_draft_store as store
        from nfl_lab.operational_storage import OperationalStorage
        from tools.private_draft_store_v2 import actions_context
        env=os.environ
        authority=origin.checked_authority(env.get("AUDIT_WEEKLY_ORIGIN_AUTHORITY_JSON","").encode(),
            env.get("AUDIT_WEEKLY_ORIGIN_AUTHORITY_SHA256"),args.request_sha256,env,root)
        job=actions_context(env,"write")
        raw=store.read_local(args.request,256 << 10)
        origin.require(store.sha(raw) == args.request_sha256,"EXACT_ORIGIN_REQUEST_HASH")
        request=origin.cp.strict_json(raw)
        origin.require(store.canonical(request) == raw,"CANONICAL_ORIGIN_REQUEST_REQUIRED")
        origin.validate_request(request,root)
        runner=store.parents_safe(env["RUNNER_TEMP"])
        origin.require(all(Path(request[k]).is_absolute() and Path(request[k]).is_relative_to(runner)
            for k in ("cache","state_root","output")),"PRIVATE_ORIGIN_RUNNER_ROOTS_REQUIRED")
        storage=OperationalStorage(request["cache"],root/"config/operational-source-policy-v2.json",state=request["state_root"])
        result=origin.recover(request,authority,storage,job,env,root)
        body=store.canonical(result)
        print(json.dumps(dict(state=result["state"],result_sha256=store.sha(body),result_bytes=len(body),
            original_source_sha=result["historical_source_sha"],current_source_sha=result["current_source_sha"],opaque_candidates_retained=18,
            original_completion_file_retained=False,model_decodes=0,fits=0,remote_writes=0,public_release=False),sort_keys=True))
        return 0
    except Exception as error:
        from nfl_lab import private_draft_store as store,audit_count_requalify_v1 as audit
        code=str(error) if isinstance(error,(store.StoreError,audit.AuditGuardError)) else "ORIGIN_RECOVERY_GUARD"
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code):code="ORIGIN_RECOVERY_GUARD"
        observation=None
        if 'request' in locals():
            path=Path(request["output"])/"ORIGIN_CLOCK_OBSERVATION.json"
            if path.is_file():
                candidate=origin.cp.strict_json(store.read_local(path,16384))
                if candidate.get("schema_version")==origin.VERSION+"-observed-original-clocks" and candidate.get("fits")==0:
                    observation=candidate
        print(json.dumps(dict(state="ORIGIN_RECOVERY_FAILED",reason=code,model_decodes=0,fits=0,remote_writes=0,public_release=False,
            original_clock_observation=observation),sort_keys=True));return 1


if __name__=="__main__":raise SystemExit(main())
