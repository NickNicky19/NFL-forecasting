"""Bounded native controller registration; default/contract performs no IO."""
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
    parser.add_argument("phase", choices=("contract", "controller-template-write", "controller-template-read", "controller-template-seal"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--request")
    parser.add_argument("--request-sha256")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    if not args.execute:
        from nfl_lab import audit_weekly_controller_registration_v1 as worker
        result = worker.contract() if args.phase == "contract" else dict(state="CONTROLLER_REGISTRATION_PREPARATION_ONLY_NO_IO",
            fits=0, registry_created=False, registration_run_completed=False, public_root=False)
        print(json.dumps(result, sort_keys=True))
        return 0 if args.phase == "contract" else 2
    try:
        from tools.private_draft_store_v2 import limits
        limits()
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
        from nfl_lab import audit_weekly_controller_registration_v1 as worker
        worker.require(args.phase != "contract" and args.request is not None and args.request_sha256 is not None,
            "NATIVE_REGISTRATION_REQUEST_REQUIRED")
        result = worker.run(args, os.environ if environ is None else environ, transport=transport)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        reason = getattr(error, "code", str(error))
        if type(reason) is not str or re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason) is None:
            reason = "CONTROLLER_REGISTRATION_WORKER_FAILED"
        print(json.dumps(dict(state="FAILED_LOCAL", reason=reason, public_root=False, fits=0,
            registry_created=False, registration_run_completed=False), sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
