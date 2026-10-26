"""Preparation CLI; actual resume uses the parent's authenticated in-process API."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nfl_lab import audit_weekly_resume_v1 as adapter, private_draft_store as store


def run(*args, **kwargs):
    result = adapter.resume(*args, **kwargs)
    return dict(state=result.document["state"], resumed=result, binding=result.binding,
        inputs=result.inputs, history_binding=result.document["history_binding"],
        archive_context=result.document["archive_context"], capture_authorized=False,
        fits=0, HTTP_calls=0, public_release=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["contract", "resume"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.phase == "resume":
        print('{"state":"LIVE_IN_PROCESS_PARENT_AUTHENTICATION_REQUIRED","HTTP_calls":0}')
        return 2
    document = dict(schema_version=adapter.VERSION + "-contract", approved=False,
        limits=adapter.LIMITS, helper_sha256=adapter.pins(),
        capture_scope_location="EXTERNAL_OWNED_RECORD_ONLY_EPOCH_CHOICE_CHANGES_ONLY_SLATE_GAME_CUTOFFS",
        original_weekly_choice_sha256="REQUIRED_PARENT_AUTHENTICATED_CANONICAL_WEEKLY_COMMITMENT",
        archive_context_roles=["canonical_weekly_choice", "capture_scope"],
        grade_population_authority_required=True, existing_primary_assignments_unchanged=True,
        capture_authorized=False, public_release=False)
    body = store.canonical(document)
    if args.output:
        store.create_local(args.output, body)
    print(json.dumps(dict(state="PREPARED_UNREGISTERED", contract_sha256=store.sha(body)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
