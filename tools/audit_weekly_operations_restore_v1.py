"""Explicit native GET-only recurring archive recovery; no scheduler."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["operations-retained"])
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--request");parser.add_argument("--request-sha256")
    args=parser.parse_args(argv)
    if not args.execute:
        print('{"state":"RECURRING_RESTORE_PREPARATION_ONLY_NO_IO","remote_writes":0,"fits":0}');return 2
    try:
        sys.path.insert(0,str(ROOT))
        from tools.private_draft_store_v2 import limits
        limits()
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
        from nfl_lab import audit_numerical_runtime_v1 as numerical
        numerical.preflight(ROOT,os.environ,scope="METADATA_ONLY")
        from nfl_lab import audit_weekly_operations_restore_v1 as recovery
        result=recovery.run(args,os.environ)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as error:
        code=getattr(error,"code",str(error))
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code):code="RECURRING_RESTORE_FAILED"
        print(json.dumps(dict(state="FAILED_RETAINED",reason=code,public_release=False,successful_forecast=False,fits=0),sort_keys=True));return 1


if __name__=="__main__":raise SystemExit(main())
