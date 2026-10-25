"""Parent-root-authorized effective18 append and fresh-job verification.

Only bounded descriptor handoff is emitted to GITHUB_OUTPUT. Private files,
model diagnostics and arbitrary exception strings never enter stdout/stderr.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab import audit_count_checkpoint_v1 as checkpoint, audit_count_requalify_v1 as audit
from nfl_lab import gha_private_checkpoint as cp, private_draft_store as store, owner_private_bootstrap as owner


def run(operation, env, *, transport=None):
    from tools.audit_count_hosted_v1 import checked_root
    from tools.private_draft_store_v2 import actions_context
    from nfl_lab.operational_storage import OperationalStorage
    body = env["AUDIT_COUNT_ROOT_GO_JSON"].encode()
    root_sha = env["AUDIT_COUNT_ROOT_GO_SHA256"]
    checked_root(body, root_sha, env)
    event = cp.strict_json(audit.read_bytes(env["GITHUB_EVENT_PATH"], 256 << 10))
    checkpoint.require(event.get("inputs", {}).get("inference_builder_go_json") == body.decode()
        and event["inputs"].get("inference_builder_go_sha256") == root_sha, "EXACT_ACTUAL_CHECKPOINT_ROOT_INPUT")
    label = checkpoint.WRITER_JOB if operation == "produce" else checkpoint.READER_JOB
    checkpoint.require(env.get("GITHUB_JOB") == label, "EXACT_CHECKPOINT_PHASE_JOB")
    checkpoint.require(operation != "produce" or env.get("GITHUB_OUTPUT"), "GENUINE_BOUNDED_HANDOFF_OUTPUT_REQUIRED")
    numerical = audit.read_json(ROOT / "config/weekly-owner-private-bootstrap-v1.json")["numerical_environment"]
    checkpoint.require(all(env.get(k) == v for k, v in numerical.items()), "EXACT_CHECKPOINT_NUMERICAL_STARTUP")
    policy_body = audit.read_bytes(ROOT / "config/operational-source-policy-v2.json", 1 << 20)
    checkpoint.require(store.sha(policy_body) == cp.POLICY_SHA, "EXACT_CHECKPOINT_SOURCE_POLICY")
    root = store.parents_safe(env["RUNNER_TEMP"]) / (audit.VERSION + "-" + env["GITHUB_RUN_ID"])
    if operation == "produce":
        checkpoint.require(root.is_dir(), "ACTUAL_REQUALIFIED_ROOT_REQUIRED")
        from tools import audit_count_failure_v1 as failure_bridge
        checkpoint.require(getattr(failure_bridge, "COUNT_FAILURE_CONTRACT_SHA256", None)
            == checkpoint.COUNT_FAILURE_CONTRACT_SHA256, "COUNT_FAILURE_VARIANT_MUST_BE_SOURCE_BOUND")
    else:
        checkpoint.require(not root.exists(), "FRESH_READER_PRIVATE_ROOT_REQUIRED")
        root.mkdir(mode=0o700)
    storage = OperationalStorage(root / "cache", cp.strict_json(policy_body), state=root / "state")
    storage.register_root(root)
    journal = root / "private-journal"
    if not journal.exists():
        journal.mkdir(mode=0o700)
    checkpoint.require(journal.is_dir() and not journal.stat().st_mode & 0o077, "PRIVATE_CHECKPOINT_JOURNAL")
    actual = audit.read_json(ROOT / "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json")
    owner.archived_qualification(actual["binding"], actual["qualification"])
    config = audit.read_json(ROOT / "config/gha-private-checkpoint-v3.json")
    checkpoint.require(store.sha(store.canonical(actual["binding"])) == config["binding_sha256"]
        and store.sha(store.canonical(actual["qualification"])) == config["qualification_sha256"], "QUALIFIED_EXISTING_CHECKPOINT_STORE")
    with storage.transaction():
        storage._require(64 << 10)
        cp.seed_pending(journal, config["external_pending_reservations"])
    job = actions_context(env, "write")

    class QuotaClient(store.Client):
        def reserve(self, key, payload, *, name=None):
            with storage.transaction():
                storage._require(16 << 10)
                super().reserve(key, payload, name=name)
                storage.snapshot()

        def request(self, url, *, method="GET", **kwargs):
            checkpoint.require(operation != "restore" or method == "GET", "EFFECTIVE_READER_GET_ONLY")
            return super().request(url, method=method, **kwargs)

    clients = []
    def factory(action):
        checkpoint.require(action == ("append" if operation == "produce" else "restore")
                           and len(clients) < 9, "NINE_CHECKPOINT_CORE_OPERATIONS")
        client = QuotaClient(env.get("GITHUB_TOKEN"), env["GITHUB_RUN_ID"], journal=journal,
            source_sha=env["GITHUB_SHA"], job=job, operation=action, transport=transport)
        clients.append(client)
        client.authenticate_actions_job()
        client.bind(actual["binding"])
        if len(clients) == 1:
            owner.authenticate_past_run(client, actual["qualification"])
            owner.verify_canary(client)
        return client
    envelope = dict(runtime_envelopes=audit.shared_envelopes(), code_pins={
        "tools/review_direct_booster_screen_guard_v4.py": store.sha(audit.read_bytes(ROOT / "tools/review_direct_booster_screen_guard_v4.py", 1 << 20))})
    phase = "restore" if operation == "produce" else "requalify"
    with audit.resource_envelope(envelope, phase, ROOT) as resources:
        if operation == "produce":
            result_ref = cp.binding(root / "REQUALIFICATION_FINISHED.json")
            restore_ref = cp.binding(root / "RESTORE_RECEIPT.json")
            files = checkpoint.collect(result_ref, restore_ref, storage, source_sha=env["GITHUB_SHA"], run_id=env["GITHUB_RUN_ID"])
            handoff = checkpoint.produce(files, factory, actual["qualification"], storage=storage,
                output=root / "effective-checkpoint", root_go_sha256=root_sha, pending=config["external_pending_reservations"])
            handoff_body = checkpoint.safe_handoff(handoff)
            checkpoint.require(env.get("GITHUB_OUTPUT"), "GENUINE_BOUNDED_HANDOFF_OUTPUT_REQUIRED")
            # One canonical line, descriptor only; no source paths or values.
            with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                stream.write("handoff_json=" + handoff_body.decode() + "\nhandoff_sha256=" + store.sha(handoff_body) + "\n")
            summary = dict(state="EFFECTIVE18_APPENDED_RESTORE_REQUIRED", model_pairs=18, fits=0,
                handoff_sha256=store.sha(handoff_body), model_artifact_durability=False, public_release=False)
        else:
            text = env.get("AUDIT_COUNT_HANDOFF_JSON", "")
            checkpoint.require(0 < len(text.encode()) <= 16384
                and store.sha(text.encode()) == env.get("AUDIT_COUNT_HANDOFF_SHA256"), "EXACT_SUCCESS_HANDOFF_HASH")
            handoff = cp.strict_json(text)
            def before_replay():
                def deny(event, unused):
                    if event.startswith(("socket.", "subprocess.")) or event in {"os.fork", "os.forkpty", "os.exec", "os.posix_spawn", "os.system"}:
                        raise RuntimeError("EFFECTIVE_REPLAY_NO_HTTP_OR_CHILDREN")
                sys.addaudithook(deny)
                import pyarrow as pa
                pa.set_cpu_count(2)
                pa.set_io_thread_count(2)
                pa.set_memory_pool(pa.system_memory_pool())
            result = checkpoint.restore(handoff, factory, storage=storage, before_replay=before_replay,
                output=root / "effective-checkpoint-restore", root_go_sha256=root_sha)
            summary = {k: result[k] for k in ("state", "model_pairs", "fits", "model_artifact_durability", "public_release")}
            summary["replay_catalog"] = result["replay_catalog"]
            summary["replay_catalog_sha256"] = result["replay_catalog_sha256"]
    storage.write_bytes(root / (operation + "-CHECKPOINT_RESOURCES.json"), store.canonical(resources))
    summary.update(HTTP_calls=sum(c.calls for c in clients), private_durability_qualified=False,
                   scientific_qualification=False, protected_outcome_reads=0)
    return summary


def main(argv=None, *, environ=None, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("produce", "restore"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print('{"state":"CHECKPOINT_PREPARATION_ONLY_NO_IO","fits":0}')
        return 2
    try:
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            result = run(args.operation, os.environ if environ is None else environ, transport=transport)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        code = getattr(error, "code", None) if isinstance(error, (store.StoreError, audit.AuditGuardError)) else None
        reason = code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "EFFECTIVE_CHECKPOINT_OPERATION_FAILED"
        print(json.dumps(dict(state="EFFECTIVE_CHECKPOINT_FAILED_RETAINED", phase=args.operation,
            reason=reason, fits=0, model_artifact_durability=False, private_durability_qualified=False, public_release=False)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
