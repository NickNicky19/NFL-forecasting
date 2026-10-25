"""Prepare a private package, or run its separately sealed genuine hosted phases.

No dispatch, upload, fit, ledger write, adapter edit or public export is provided.
Preparation reads local metadata and the fixed public source Git object only.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab import audit_count_requalify_v1 as audit


class Quiet:
    """Discard library diagnostics; private data and exception strings never log."""
    def write(self, text):
        return len(text)

    def flush(self):
        pass


def run_phase(args, env, *, transport=None):
    from nfl_lab import gha_private_checkpoint as cp, private_draft_store as core
    from nfl_lab.operational_storage import OperationalStorage
    body = audit.read_bytes(Path(args.package) / "PLAN.json", 1 << 20)
    go_body = audit.read_bytes(args.go, 256 << 10)
    audit.require(audit.sha(body) == args.plan_sha256 and audit.sha(go_body) == args.go_sha256,
                  "EXACT_PLAN_AND_GO_HASH_REQUIRED")
    plan, go = cp.strict_json(body), cp.strict_json(go_body)
    audit.require(plan["schema_version"] == audit.VERSION + "-plan" and plan["repository"] == audit.REPO,
                  "EXACT_PLAN_SCHEMA")
    job = audit.validate_go(plan, args.plan_sha256, go, args.command, env, ROOT)
    policy_body = audit.read_bytes(ROOT / "config/operational-source-policy-v2.json", 1 << 20)
    audit.require(audit.sha(policy_body) == plan["source_policy_sha256"] == cp.POLICY_SHA, "EXACT_SOURCE_POLICY_REQUIRED")
    output = core.parents_safe(go["output_root"])
    if args.command == "restore":
        audit.require(go["restore_receipt"] is None and not output.exists(), "NEW_RESTORE_ROOT_NO_RETRY")
        output.mkdir(mode=0o700)
    else:
        audit.require(output.is_dir() and not output.stat().st_mode & 0o077, "PRIVATE_RESTORED_ROOT_REQUIRED")
    storage = OperationalStorage(go["local_cache"], cp.strict_json(policy_body), state=go["local_state"])
    storage.register_root(output)
    consumed = output / (args.command + "-CONSUMED.json")
    with storage.transaction():
        audit.require(not consumed.exists(), "ONE_PHASE_NO_RETRY")
        storage.write_bytes(consumed, audit.canonical(dict(phase=args.command, GO_sha256=args.go_sha256,
            plan_sha256=args.plan_sha256, current_run_id=go["run_id"], current_source_sha=go["source_sha"],
            started_at_utc=audit.now().isoformat(), fits=0)))
    with audit.resource_envelope(plan, args.command, ROOT) as resources:
        if args.command == "restore":
            result = audit.restore_checkpoint(plan, go, storage, job, env, transport=transport)
        else:
            def deny(event, unused):
                if event.startswith(("socket.", "subprocess.")) or event in {"os.fork", "os.forkpty", "os.exec", "os.posix_spawn", "os.system"}:
                    raise RuntimeError("REQUALIFICATION_NO_HTTP_OR_CHILDREN")
            sys.addaudithook(deny)
            import pyarrow as pa
            import threadpoolctl
            from tools.ngboost_law_software_v1 import process_free_threads
            pa.set_cpu_count(2)
            pa.set_io_thread_count(2)
            pa.set_memory_pool(pa.system_memory_pool())
            libc_path = Path("/usr/lib/x86_64-linux-gnu/libc.so.6").resolve(strict=True)
            libc_ref = dict(path=str(libc_path), bytes=libc_path.stat().st_size,
                            sha256=audit.sha(audit.read_bytes(libc_path, 8 << 20)))
            with process_free_threads(threadpoolctl, libc_ref), threadpoolctl.threadpool_limits(limits=2):
                result = audit.requalify_restored(plan, go, storage, args.package)
            resources["runtime_libc"] = libc_ref
    storage.write_bytes(output / (args.command + "-RESOURCE_FINISHED.json"), audit.canonical(resources))
    return result


def main(argv=None, *, environ=None, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    inventory = prepare.add_mutually_exclusive_group(required=True)
    inventory.add_argument("--inventory")
    inventory.add_argument("--refresh-inventory", action="store_true")
    prepare.add_argument("--original-source")
    prepare.add_argument("--output", required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("phase", choices=("restore", "requalify"))
    seal.add_argument("--package", required=True)
    seal.add_argument("--plan-sha256", required=True)
    for name in ("restore", "requalify"):
        phase = sub.add_parser(name)
        phase.add_argument("--execute", action="store_true")
        for flag in ("package", "plan-sha256", "go", "go-sha256"):
            phase.add_argument("--" + flag)
    args = parser.parse_args(argv)
    if args.command in {"restore", "requalify"} and not args.execute:
        print(json.dumps(dict(state="PREPARATION_ONLY_NO_IO", fits=0, private_durability_qualified=False)))
        return 2
    result = None
    try:
        # No user-controlled/private strings from downstream libraries are emitted.
        with contextlib.redirect_stdout(Quiet()), contextlib.redirect_stderr(Quiet()):
            if args.command == "prepare":
                if args.refresh_inventory:
                    inventory_path = Path(args.output).with_name(Path(args.output).name + ".inventory.json")
                    witness = audit.refresh_inventory(inventory_path)
                else:
                    inventory_path, witness = args.inventory, None
                result = audit.prepare_package(ROOT, inventory_path, args.output, original_source=args.original_source)
                if witness:
                    audit.private_write(Path(args.output) / "METADATA_REFRESH.json", audit.canonical(witness))
            elif args.command == "seal":
                body = audit.read_bytes(Path(args.package) / "PLAN.json", 1 << 20)
                audit.require(audit.sha(body) == args.plan_sha256, "EXACT_PLAN_HASH_REQUIRED")
                plan = json.loads(body)
                go = audit.seal_phase(plan, args.plan_sha256, args.phase, os.environ if environ is None else environ, ROOT)
                go_body = audit.canonical(go)
                audit.private_write(Path(args.package) / ("GO." + args.phase + ".json"), go_body)
                audit.private_write(Path(args.package) / ("GO." + args.phase + ".sha256"), (audit.sha(go_body) + "\n").encode())
                result = dict(state="SEALED_FROM_FRESH_OWNER_DISPATCH", plan_sha256=args.plan_sha256, fits=0)
            else:
                result = run_phase(args, os.environ if environ is None else environ, transport=transport)
        summary = {k: result[k] for k in ("state", "plan_sha256", "model_pairs", "logical_files", "fits", "private_body_reads", "hosted_execution") if k in result}
        summary.update(remote_writes=0, protected_outcome_reads=0, private_durability_qualified=False)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except Exception as error:
        # Only explicit guard types are eligible. A library ValueError with an
        # uppercase private string is still deliberately opaque.
        from nfl_lab.private_draft_store import StoreError
        code = getattr(error, "code", None) if isinstance(error, (audit.AuditGuardError, StoreError)) else None
        reason = code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "COUNT_REQUALIFICATION_GUARD_OR_OPERATION_FAILED"
        print(json.dumps(dict(state="FAILED_RETAINED", phase=args.command,
            reason=reason, fits=0,
            remote_writes=0, protected_outcome_reads=0, private_durability_qualified=False)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
