"""Preparation CLI and typed in-process operational grading bridge.

Parent root owns genuine source/API authentication, provider acquisition,
native 180s/120CPU/512MiB limits and private checkpoint/fresh-reader transport.
No serialized JSON execution authority or network/credential fallback exists.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_lab import audit_weekly_grade_v1 as grading
from nfl_lab import private_draft_store as store


def run(registered,captures,batches,*,storage,output,previous=None,clock=grading.now):
    snapshot = grading.grade(registered,captures,batches,storage=storage,output=output,previous=previous,clock=clock)
    return dict(state="LOCAL_OPERATIONAL_GRADING_PENDING_FRESH_DURABILITY",snapshot=snapshot,
        binding=snapshot.binding,new_revisions=snapshot.document["new_revisions"],
        fits=0,remote_writes=0,public_release=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["contract","execute"])
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if args.phase=="execute":
        print('{"state":"IN_PROCESS_PARENT_AUTHENTICATION_REQUIRED","public_release":false}')
        return 2
    document=dict(schema_version=grading.VERSION+"-prepared-contract",state="PREPARED_UNREGISTERED",
        population_rule=grading.POPULATION_RULE,horizon="player_game",limits=grading.LIMITS,
        policy=grading.selector.POLICY,code_pins=grading.pins(),
        provider_callback="EXISTING_E7_COMPLETED_GAME_COLLECTOR_ONLY; real body/status hashes and clocks required",
        local_grading_is_durable=False,scientific_qualification=False,public_release=False)
    if args.output:store.create_local(args.output,store.canonical(document))
    print(json.dumps(dict(state=document["state"],contract_sha256=store.sha(store.canonical(document))),sort_keys=True))
    return 0


if __name__=="__main__":raise SystemExit(main())
