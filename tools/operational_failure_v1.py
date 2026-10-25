"""Record SYS006 evidence; append/restore only under the existing exact GO.

This entrypoint never runs or retries the original command. Its exit code
reports preservation only; the orchestrator must retain the original failure.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nfl_lab import operational_failure_v1 as failure, private_draft_store as store


def main(argv=None, *, environ=None, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["record", "append", "restore"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--source-policy", type=Path, default=ROOT / "config/operational-source-policy-v2.json")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--request-sha256")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--authorization-sha256")
    parser.add_argument("--binding", type=Path)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--payload-manifest", type=Path)
    parser.add_argument("--descriptor", type=Path)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps(dict(state="PREPARATION_ONLY_NO_IO", automatic_retries=0, **failure.NEGATIVE_GATES)))
        return 2
    client = None
    try:
        failure.require(all(getattr(args, name) is not None for name in ("cache", "state_root", "output_root")),
                        "EXPLICIT_PRIVATE_ROOTS_REQUIRED")
        if args.operation == "record":
            failure.require(args.request is not None and args.request_sha256 is not None, "EXACT_FAILURE_REQUEST_REQUIRED")
            body = store.read_local(args.request, failure.METADATA_CAP)
            failure.require(store.sha(body) == args.request_sha256, "FAILURE_REQUEST_HASH")
            request = failure.check_request(failure.document(body))
        else:
            failure.require(all(getattr(args, name) is not None for name in (
                "authorization", "authorization_sha256", "binding", "journal")), "EXACT_PRIVATE_GO_INPUTS_REQUIRED")
            authorization = store.read_local(args.authorization, failure.METADATA_CAP)
            failure.require(store.sha(authorization) == args.authorization_sha256, "GO_HASH")
            go = failure.document(authorization)
            env = os.environ if environ is None else environ
            # The shared genuine-checkout contract executes before token access.
            from tools.private_draft_store_v2 import actions_context, limits
            failure.require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == store.REPO
                            and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
                            and env.get("GITHUB_RUN_ATTEMPT") == "1" and env.get("STORE_PERMISSION") == "write"
                            and go.get("run_id") == env.get("GITHUB_RUN_ID")
                            and go.get("source_sha") == env.get("GITHUB_SHA"), "GENUINE_FAILURE_JOB_CONTEXT")
            job = actions_context(env, "write")
            fields = {"binding": args.binding}
            if args.operation == "append":
                fields.update(payload_manifest=args.payload_manifest or args.output_root / "PAYLOAD.json",
                              qualification=args.qualification)
            else:
                fields.update(descriptor=args.descriptor)
            failure.require(all(path is not None for path in fields.values()), "EXACT_PRIVATE_GO_INPUTS_REQUIRED")
            inputs = {name: store.read_local(path, store.META_CAP) for name, path in fields.items()}
            failure.require(args.journal.is_dir(), "EXISTING_ACCOUNTED_PRIVATE_JOURNAL_REQUIRED")
            # No credential search, custom CLI token, transport switch or fallback.
            limits()
            client = store.Client(env.get("GITHUB_TOKEN"), env["GITHUB_RUN_ID"], journal=args.journal,
                                  source_sha=env["GITHUB_SHA"], job=job, operation=args.operation, transport=transport)
            failure.authorize(client, authorization, args.authorization_sha256, args.operation, inputs)
        policy_body = store.read_local(args.source_policy, 1 << 20)
        failure.require(store.sha(policy_body) == failure.checkpoint.POLICY_SHA, "EXACT_PERMITTED_SOURCE_POLICY_REQUIRED")
        from nfl_lab.operational_storage import OperationalStorage
        storage = OperationalStorage(args.cache, failure.document(policy_body, 1 << 20), state=args.state_root)
        if client is not None:
            storage.register_root(args.journal)
        if args.operation == "record":
            status = failure.record_failure(request, storage, args.output_root)
        else:
            method = failure.append_failure if args.operation == "append" else failure.restore_failure
            result = method(client, storage, args.output_root, authorization=authorization,
                            authorization_sha256=args.authorization_sha256, inputs=inputs)
            status = result["status"]
        # Never print the request, envelope, opaque bodies, descriptor or proof.
        print(json.dumps(status, sort_keys=True))
        return 0
    except Exception as error:
        status = failure.safe_status("FAILURE_PRESERVATION_BLOCKED", HTTP_calls=client.calls if client else 0)
        code = error.code if isinstance(error, store.StoreError) else "FAILURE_PRESERVATION_FAILED"
        status["reason"] = code if re.fullmatch(r"[A-Z0-9_]{1,90}", code) else "FAILURE_PRESERVATION_FAILED"
        print(json.dumps(status, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
