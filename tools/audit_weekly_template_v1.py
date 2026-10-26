"""Local static-metadata preparation only; Root calls authenticated library I/O.

This tool never discovers credentials or constructs a transport. Native append,
fresh-reader restore and schedule recovery require live Python callbacks from
the pinned parent Root/controller, which cannot be supplied as JSON flags.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','validate'))
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--template-sha256')
    parser.add_argument('--template-bytes',type=int)
    args=parser.parse_args(argv)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from nfl_lab import audit_weekly_template_v1 as t, private_draft_store as store
    try:
        raw=store.read_local(args.input,t.PLAIN_CAP if args.phase=='prepare' else t.PACKED_CAP)
        if args.phase=='prepare':
            t.require(args.output is not None,'PRIVATE_STATIC_TEMPLATE_OUTPUT_REQUIRED')
            prepared=t.prepare(t.decode_json(raw))
            store.create_local(args.output,prepared.body)
        else:
            prepared=t.decode_static(raw,template_sha256=args.template_sha256,template_bytes=args.template_bytes)
        print(json.dumps(dict(state='STATIC_METADATA_ONLY_NO_EXECUTION_AUTHORITY',template_sha256=store.sha(prepared.plain),
            template_bytes=len(prepared.plain),packed_sha256=store.sha(prepared.body),packed_bytes=len(prepared.body),
            fits=0,remote_calls=0,native_durability_claimed=False),sort_keys=True));return 0
    except Exception as error:
        reason=str(error) if isinstance(error,(t.TemplateError,store.StoreError)) else 'STATIC_TEMPLATE_GUARD'
        if re.fullmatch('[A-Z][A-Z0-9_]{0,95}',reason) is None:reason='STATIC_TEMPLATE_GUARD'
        print(json.dumps(dict(state='STATIC_TEMPLATE_BLOCKED',reason=reason,fits=0,remote_calls=0),sort_keys=True));return 1


if __name__=='__main__':raise SystemExit(main())
