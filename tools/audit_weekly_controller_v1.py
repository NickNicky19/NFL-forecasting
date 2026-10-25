"""Controller metadata contract only; no credentials, dispatch or activation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def verify_child(*args,**kwargs):
    from nfl_lab import audit_weekly_controller_v1 as controller
    return controller.verify_child(*args,**kwargs)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["template","execute"])
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if args.phase=="execute":
        print('{"state":"IN_PROCESS_RAW_METADATA_CALLBACK_AND_EXTERNAL_OWNER_SEAL_REQUIRED","POSTs":0,"activation_authorized":false}')
        return 2
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from nfl_lab import audit_weekly_controller_v1 as controller
    body=controller.canonical(controller.registration_template())
    if args.output:
        with args.output.open("xb") as out:
            out.write(body)
    print(json.dumps(dict(state="PREPARED_UNREGISTERED",registration_sha256=controller.sha(body),POSTs=0,activation_authorized=False)))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
