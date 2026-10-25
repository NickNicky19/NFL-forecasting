"""Parent-authorized GET-only recovery of a completed prior weekly capture."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout,redirect_stderr
import json
import os
from pathlib import Path
import re
import sys


class Quiet:
    def write(self,value):return len(value)
    def flush(self):pass


def run(args,env,*,transport=None):
    from nfl_lab import audit_weekly_retained_v1 as retained,private_draft_store as store
    from nfl_lab.operational_storage import OperationalStorage
    from tools.private_draft_store_v2 import actions_context
    root=Path(__file__).resolve().parents[1]
    a=retained.checked_authority(env.get("AUDIT_WEEKLY_RETAINED_AUTHORITY_JSON","").encode(),
        env.get("AUDIT_WEEKLY_RETAINED_AUTHORITY_SHA256"),args.request_sha256,env,root)
    job=actions_context(env,"write")
    raw=store.read_local(args.request,512 << 10);p=retained.cp.strict_json(raw)
    retained.require(raw==store.canonical(p) and store.sha(raw)==args.request_sha256,"EXACT_CANONICAL_RETAINED_WEEKLY_REQUEST")
    retained.validate_request(p,root)
    numerical=retained.cp.strict_json(store.read_local(root/"config/weekly-owner-private-bootstrap-v1.json",2 << 20))["numerical_environment"]
    retained.require(all(env.get(k)==v for k,v in numerical.items()),"EXACT_NATIVE_RETAINED_NUMERICAL_ENVIRONMENT")
    runner=store.parents_safe(env["RUNNER_TEMP"])
    retained.require(all(Path(p[k]).is_absolute() and Path(p[k]).is_relative_to(runner) for k in ("cache","state_root","output")),
        "PRIVATE_CURRENT_RETAINED_RUNNER_ROOTS")
    storage=OperationalStorage(p["cache"],root/"config/operational-source-policy-v2.json",state=p["state_root"])
    # A separate new local journal retains every prior unresolved reservation;
    # it never appends, clears a receipt, or borrows an old execution authority.
    output=Path(p["output"]);retained.require(not output.exists(),"FRESH_RETAINED_OUTPUT_NO_RETRY")
    journal=output.parent/(output.name+"-journal")
    retained.require(not journal.exists(),"FRESH_RETAINED_JOURNAL_NO_RETRY")
    storage.register_root(journal);retained.cp.seed_pending(journal,p["pending_reservations"])
    class Factory:
        def __init__(self):self.clients=[]
        def __call__(self,operation):
            retained.require(operation=="restore" and len(self.clients)<retained.MAX_CLIENTS,"FINITE_NATIVE_RETAINED_GET_OPERATIONS")
            c=retained.ReadClient(env.get("GITHUB_TOKEN"),a["run_id"],journal=journal,source_sha=a["source_sha"],job=job,
                operation="restore",extra_routes=retained.routes(p),transport=transport)
            c.bind(p["qualified_runtime"]["binding"]);self.clients.append(c);return c
    result=retained.restore(p,Factory(),storage=storage,authority=a,root=root)
    body=store.canonical(result)
    return dict(state=result["state"],result_sha256=store.sha(body),result_bytes=len(body),
        original_source_sha=result["original_archive"]["source_sha"],current_source_sha=result["current"]["source_sha"],
        files=len(result["aliases"]),historical_reader_proofs=len(result["historical_reader_witness"]["proofs"]),
        current_restore_proofs=len(result["current_restore_proofs"]),R0_state_files=len(result["previous_state_aliases"]),
        HTTP_calls=result["HTTP_calls"],RSS_peak_bytes=result["RSS_peak_bytes"],fits=0,model_decodes=0,
        remote_writes=0,protected_outcome_reads=0,public_release=False,successful_forecast=False)


def main(argv=None,*,environ=None,transport=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("restore",));parser.add_argument("--execute",action="store_true")
    parser.add_argument("--request",type=Path);parser.add_argument("--request-sha256")
    args=parser.parse_args(argv)
    if not args.execute:print('{"state":"RETAINED_PREPARATION_ONLY_NO_IO","public_release":false}');return 2
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    try:
        # Enforce the existing actual native envelope before importing pandas
        # through owned storage, or Arrow through the unchanged capture reader.
        from tools.private_draft_store_v2 import limits
        limits()
        with redirect_stdout(Quiet()),redirect_stderr(Quiet()):result=run(args,os.environ if environ is None else environ,transport=transport)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as error:
        from nfl_lab import private_draft_store as store
        reason=str(error) if isinstance(error,store.StoreError) else "RETAINED_WEEKLY_OPERATION_FAILED"
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",reason):reason="RETAINED_WEEKLY_OPERATION_FAILED"
        print(json.dumps(dict(state="RETAINED_WEEKLY_FAILED",reason=reason,fits=0,remote_writes=0,public_release=False),sort_keys=True));return 1


if __name__=="__main__":raise SystemExit(main())
