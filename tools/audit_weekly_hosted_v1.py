"""Explicit entry point; preparation never discovers credentials or runs IO."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
import re
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class Quiet:
    def write(self,value): return len(value)
    def flush(self): pass

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("produce","restore","consume","evidence","preserve","models","reference"))
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--request");parser.add_argument("--request-sha256")
    args=parser.parse_args(argv)
    if not args.execute:
        print('{"state":"WEEKLY_PREPARATION_ONLY_NO_IO","fits":0,"public_release":false}');return 2
    from nfl_lab import audit_weekly_hosted_v1 as hosted,private_draft_store as store
    try:
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
        resource.setrlimit(resource.RLIMIT_CPU,(900,900));resource.setrlimit(resource.RLIMIT_AS,(4 << 30,4 << 30))
        signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(1500)
        with redirect_stdout(Quiet()),redirect_stderr(Quiet()):
            if args.phase=="models":result=hosted.model_child(args,os.environ)
            elif args.phase=="reference":result=hosted.reference_child(args,os.environ)
            else:result=hosted.execute(args.phase,os.environ)
        # Closed summaries/descriptors only, never source/model/forecast bytes.
        print(json.dumps(result,sort_keys=True));return 0 if result.get("state")!="FAILED_RETAINED" else 1
    except Exception as error:
        code=error.code if isinstance(error,store.StoreError) else "WEEKLY_HOSTED_GUARD"
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}",code):code="WEEKLY_HOSTED_GUARD"
        print(json.dumps(dict(state="FAILED_RETAINED",reason=code,fits=0,public_release=False,successful_forecast=False),sort_keys=True));return 1

if __name__=="__main__":raise SystemExit(main())
