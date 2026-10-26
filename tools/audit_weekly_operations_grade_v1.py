"""Explicit same-run operations grading worker; no JSON execution shortcuts."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout,redirect_stderr
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]


class Quiet:
    def write(self,value):return len(value)
    def flush(self):pass


def main(argv=None,*,environ=None,transport=None,fetch=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["contract","operations-grade-write","operations-grade-read"])
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--request");parser.add_argument("--request-sha256")
    args=parser.parse_args(argv)
    sys.path.insert(0,str(ROOT))
    if not args.execute:
        if args.phase=="contract":
            from nfl_lab import audit_weekly_operations_grade_v1 as worker
            print(json.dumps(worker.contract(),sort_keys=True))
        else:print('{"state":"OPERATIONS_GRADE_PREPARATION_ONLY_NO_IO","fits":0,"public_release":false}')
        return 2
    try:
        with redirect_stdout(Quiet()),redirect_stderr(Quiet()):
            from tools.private_draft_store_v2 import limits
            limits()
            from tools.audit_process_guard_v1 import arm_parent_death
            arm_parent_death()
            env=os.environ if environ is None else environ
            from nfl_lab import audit_numerical_runtime_v1 as numerical
            numerical.preflight(ROOT,env,scope="METADATA_ONLY")
            from nfl_lab import audit_weekly_operations_grade_v1 as worker
            result=worker.run(args,env,transport=transport,fetch=fetch)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as error:
        fixed={("nfl_lab.private_draft_store","StoreError"),("nfl_lab.audit_weekly_operations_grade_v1","GradeBridgeError"),
            ("nfl_lab.audit_weekly_operations_worker_v1","WorkerError"),("nfl_lab.audit_weekly_grade_v1","GradeError"),
            ("nfl_lab.audit_weekly_grade_checkpoint_v1","CheckpointError"),("nfl_lab.audit_weekly_provider_v1","ProviderError"),
            ("nfl_lab.audit_weekly_epoch_v1","EpochError"),("nfl_lab.audit_numerical_runtime_v1","NumericalRuntimeError"),
            ("nfl_lab.audit_weekly_grade_history_v1","HistoryError"),
            ("nfl_lab.audit_weekly_controller_v1","ControllerError"),("nfl_lab.audit_weekly_controller_bootstrap_v1","BootstrapError")}
        code=getattr(error,"code",str(error)) if (type(error).__module__,type(error).__name__) in fixed else "OPERATIONS_GRADE_FAILED"
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code):code="OPERATIONS_GRADE_FAILED"
        print(json.dumps(dict(state="FAILED_LOCAL",reason=code,metadata_remote_durability_qualified=False,
            fits=0,public_release=False,successful_forecast=False),sort_keys=True))
        return 1


if __name__=="__main__":raise SystemExit(main())
