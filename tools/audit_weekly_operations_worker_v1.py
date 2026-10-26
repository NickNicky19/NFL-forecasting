"""Native operations metadata worker; preparation/contract performs no private IO."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None, *, environ=None, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["contract", "operations-prepare", "operations-grade-write", "operations-grade-read"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--request"); parser.add_argument("--request-sha256")
    args = parser.parse_args(argv)
    if not args.execute:
        if args.phase == "contract":
            sys.path.insert(0, str(ROOT))
            from nfl_lab import audit_weekly_operations_worker_v1 as worker
            print(json.dumps(worker.contract(), sort_keys=True))
        else:
            print('{"state":"OPERATIONS_PREPARATION_ONLY_NO_IO","fits":0,"public_release":false}')
        return 2
    try:
        sys.path.insert(0, str(ROOT))
        from tools.private_draft_store_v2 import limits
        limits()
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
        env = os.environ if environ is None else environ
        from nfl_lab import audit_numerical_runtime_v1 as numerical
        numerical.preflight(ROOT, env, scope="METADATA_ONLY")
        from nfl_lab import audit_weekly_operations_worker_v1 as worker
        result = worker.run(args, env, transport=transport)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        code = getattr(error, "code", str(error))
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code): code = "OPERATIONS_WORKER_FAILED"
        print(json.dumps(dict(state="FAILED_LOCAL", reason=code, metadata_remote_durability_qualified=False,
            fits=0, public_release=False, successful_forecast=False), sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
