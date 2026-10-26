"""Offline contract CLI; execution requires in-process live parent authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_lab import audit_weekly_provider_v1 as provider
from nfl_lab import audit_weekly_grade_v1 as grade, private_draft_store as store


def run(captures, *, collector, authenticate, clock=provider.state.now_utc):
    """Parent supplies its genuine collector/source and grade authentication."""
    provider.require(type(collector) is provider.Collector, "LIVE_PROVIDER_COLLECTOR_REQUIRED")
    result = grade.acquire(captures,collect=collector,authenticate=authenticate,clock=clock)
    collector.capture.verify()
    return dict(state="LOCAL_PROVIDER_INPUT_PENDING_GRADING_AND_DURABILITY",observations=result,
        capture=collector.capture,remote_writes=0,fits=0,public_release=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["contract","execute"])
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if args.phase == "execute":
        print('{"state":"IN_PROCESS_PARENT_SOURCE_AUTHENTICATION_REQUIRED","public_release":false}')
        return 2
    doc=dict(schema_version=provider.VERSION+"-prepared-contract",state="PREPARED_UNREGISTERED",limits=provider.LIMITS,
        source_policy_sha256=provider.cp.POLICY_SHA,code_pins=provider.pins(),targets=sorted(provider.grading.TARGETS),
        collector_ABI="Collector(storage=owned_storage,output=NEW_PRIVATE_PATH,authenticate=LIVE_PARENT_CALLBACK)(grade.provider_request(...))",
        authentication_kinds=["AUTHORIZE_REGISTERED_REQUEST","AUTHENTICATE_SOURCE_BODY","COMPLETE_PROVIDER_OBSERVATIONS"],
        no_JSON_execution_authority=True,HTTP_status_requires_parent_API_authentication=True,source_timestamp=None,
        parent_native_worker_envelope_required=True,
        original_E7_downloader_attempts_per_URL=3,adapter_retries=0,explicit_DNP_source_unavailable=True,
        grade_authentication_and_fresh_durability_required_separately=True,fits=0,public_release=False)
    if args.output:
        store.create_local(args.output,store.canonical(doc))
    print(json.dumps(dict(state=doc["state"],contract_sha256=store.sha(store.canonical(doc))),sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
