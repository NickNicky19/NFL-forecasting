"""Explicit native in-process checkpoint bridge; no JSON/CLI execution authority."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def append(*args, **kwargs):
    from tools.private_draft_store_v2 import limits
    limits()
    from nfl_lab import audit_weekly_grade_checkpoint_v1 as checkpoint
    return checkpoint.append(*args, **kwargs)


def restore(*args, **kwargs):
    from tools.private_draft_store_v2 import limits
    limits()
    from nfl_lab import audit_weekly_grade_checkpoint_v1 as checkpoint
    return checkpoint.restore(*args, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["contract", "execute"])
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nfl_lab import audit_weekly_grade_checkpoint_v1 as checkpoint
    from nfl_lab import private_draft_store as store
    if args.phase == "execute":
        print('{"state":"LIVE_NATIVE_CLIENT_AND_PARENT_AUTHENTICATOR_REQUIRED","public_release":false}')
        return 2
    print(store.canonical(checkpoint.contract()).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
