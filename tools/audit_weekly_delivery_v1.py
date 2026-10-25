"""In-process delivery adapter; standalone execution cannot recreate live proof."""
from __future__ import annotations
import argparse
import json


def run(*args,**kwargs):
    from nfl_lab.audit_weekly_delivery_v1 import deliver
    return deliver(*args,**kwargs)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true")
    parser.parse_args(argv)
    print(json.dumps(dict(state="IN_PROCESS_AUTHENTICATED_EXPORTER_REQUIRED",public_release=False),sort_keys=True))
    return 2


if __name__=="__main__":raise SystemExit(main())
