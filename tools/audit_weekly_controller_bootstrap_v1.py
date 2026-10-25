"""Offline bootstrap ABI template only; no credential or private-template IO."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["template", "execute"])
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    from nfl_lab import audit_weekly_controller_v1 as controller
    if args.phase == "execute":
        print(controller.canonical(dict(state="PARENT_PRIVATE_WRITER_READER_AND_WORKFLOW_WIRING_REQUIRED",
            activation_authorized=False, POSTs=0, fits=0)).decode())
        return 2
    print(controller.canonical(bootstrap.integration_contract()).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
