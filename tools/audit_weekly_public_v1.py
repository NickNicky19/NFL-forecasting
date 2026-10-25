"""Preparation CLI and in-process typed exporter for the parent orchestrator.

No transport, credential lookup, repository write or GHA dispatch. The parent
calls run(live, at=...) in the same process that verified genuine archive/API
evidence. There is deliberately no JSON-to-live-acceptance execution route.
Returned feed bytes are only a reviewable derived artifact; parent owns all
publication persistence, root authority and website policy installation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nfl_lab import audit_weekly_public_v1 as public
from nfl_lab import private_draft_store as store,gha_private_checkpoint as cp


def run(live,*,at):
    document=public.export(live,at=at)
    body=public.feed.canonical(document)
    return dict(document=document,body=body,sha256=store.sha(body),rows=len(document["rows"]),
        repository_writes=0,remote_writes=0,website_activation=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["template","check-policy","export"])
    parser.add_argument("--output",type=Path)
    parser.add_argument("--policy",type=Path);parser.add_argument("--policy-sha256");parser.add_argument("--at")
    args=parser.parse_args(argv)
    if args.phase=="export":
        print('{"state":"IN_PROCESS_LIVE_ACCEPTANCE_REQUIRED","public_export_authorized":false}')
        return 2
    try:
        if args.phase=="template":
            public.require(args.output is not None,"PRIVATE_TEMPLATE_PATH_REQUIRED")
            body=store.canonical(public.policy_template())
            store.create_local(args.output,body)
            result=dict(state="PREPARED_UNREGISTERED",policy_sha256=store.sha(body),public_export_authorized=False)
        else:
            public.require(args.policy is not None and args.policy_sha256 is not None and args.at is not None,"EXACT_POLICY_INPUTS_REQUIRED")
            body=store.read_local(args.policy,128 << 10)
            public.require(store.sha(body)==args.policy_sha256,"EXACT_POLICY_HASH")
            policy=cp.strict_json(body);public.require(body==store.canonical(policy),"CANONICAL_NEW_POLICY_REQUIRED")
            public.policy_check(policy,at=args.at)
            result=dict(state="POLICY_METADATA_CHECKED_NO_LIVE_AUTHORITY",public_export_authorized=False)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as error:
        code=str(error) if isinstance(error,public.PublicError) else "PUBLIC_METADATA_PREPARATION_FAILED"
        if not __import__("re").fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code):code="PUBLIC_METADATA_PREPARATION_FAILED"
        print(json.dumps(dict(state="PREPARATION_REJECTED",reason=code,public_export_authorized=False),sort_keys=True));return 1


if __name__=="__main__":raise SystemExit(main())
