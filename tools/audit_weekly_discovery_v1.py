"""Metadata-only contract preparation and parent-composed discovery entry.

The parent supplies genuine root authentication, its qualified native GET-only
factory and native180s/120CPU/512MiB envelope. No JSON execution authority,
credentials, provider acquisition or fallback namespace search is supplied.
"""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_lab import audit_weekly_discovery_v1 as discovery, private_draft_store as store


def run(*args,**kwargs):
    result=discovery.discover(*args,**kwargs)
    return dict(state=result.document["state"],discovery=result,binding=result.binding,
        HTTP_calls=result.document["HTTP_calls"],native_clients=result.document["native_clients"],
        capture_durability_established=False,public_authority=False,remote_writes=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["contract","discover"]);parser.add_argument("--execute",action="store_true")
    parser.add_argument("--output",type=Path);args=parser.parse_args(argv)
    if args.phase == "discover":
        print('{"state":"LIVE_PARENT_FACTORY_AND_AUTHENTICATION_REQUIRED","remote_writes":0}')
        return 2
    document=dict(schema_version=discovery.VERSION+"-contract",approved=False,limits=discovery.LIMITS,
        helper_sha256=discovery.pins(),public_receipt_keys=sorted(discovery.delivery.RECEIPT_KEYS),
        historical_source_files=list(discovery.retained.HISTORICAL_FILES),public_authority=False)
    body=store.canonical(document)
    if args.output:store.create_local(args.output,body)
    print(json.dumps(dict(state="PREPARED_UNREGISTERED",contract_sha256=store.sha(body)),sort_keys=True));return 0


if __name__=="__main__":raise SystemExit(main())
