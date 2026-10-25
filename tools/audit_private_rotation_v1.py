"""Explicit canary-only rotation in the parent's existing three-job workflow."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("write", "read", "qualify"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print('{"state":"ROTATION_PREPARATION_ONLY_NO_IO","private_payload_bytes":0}')
        return 2
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_AS, (512 << 20, 512 << 20))
        signal.signal(signal.SIGALRM, signal.SIG_DFL); signal.alarm(360 if args.phase == "write" else 180)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from nfl_lab import audit_private_rotation_v1 as rotation
        root = rotation.preflight(args.phase, os.environ)
        result = rotation.run_phase(args.phase, os.environ, root)
        if args.phase == "qualify":
            # The final job has no downstream consumer of GITHUB_OUTPUT. Keep
            # this checked metadata receipt outside the disposable runner too.
            # safe_output excludes secrets, URLs, private paths and bodies;
            # only the native canary proofs and quota/identity metadata remain.
            print("AUDIT_PRIVATE_ROTATION_QUALIFIED_JSON=" + rotation.safe_output(result).decode(), flush=True)
        print(json.dumps(dict(state="ROTATION_PHASE_COMPLETE", phase=args.phase, handoff_sha256=rotation.sha(rotation.canonical(result)),
            private_payload_bytes=0, private_durability_qualified=False), sort_keys=True))
        return 0
    except Exception as error:
        from nfl_lab import audit_private_rotation_v1 as rotation
        from nfl_lab import private_draft_store as store
        reason = str(error) if isinstance(error, (rotation.RotationError, store.StoreError)) else "ROTATION_DRIVER_GUARD"
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason):
            reason = "ROTATION_DRIVER_GUARD"
        print(json.dumps(dict(state="ROTATION_DRIVER_FAILED", reason=reason, private_payload_bytes=0, private_durability_qualified=False), sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
