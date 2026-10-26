"""Once-and-exit native daily parent; default and --contract perform no IO."""
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
    parser.add_argument("--contract", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    if not args.execute or args.contract:
        from nfl_lab import audit_weekly_parent_v1 as parent
        result = parent.contract() if args.contract else dict(state="PARENT_PREPARATION_ONLY_NO_IO",
            remote_calls=0, POSTs=0, child_completion_claimed=False, public_root=False, fits=0)
        print(json.dumps(result, sort_keys=True))
        return 0 if args.contract else 2
    try:
        from tools.private_draft_store_v2 import limits
        limits()
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
        from nfl_lab import audit_weekly_parent_v1 as parent
        result = parent.run(os.environ if environ is None else environ, transport=transport)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        reason = getattr(error, "code", str(error))
        if type(reason) is not str or re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason) is None:
            reason = "PARENT_EXECUTION_BLOCKED"
        print(json.dumps(dict(state="PARENT_BLOCKED", reason=reason, child_completion_claimed=False,
            public_root=False, fits=0, automatic_retry=False), sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
