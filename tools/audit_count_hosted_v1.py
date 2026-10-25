"""Genuine existing-workflow bridge for separately authorized zero-fit recovery.

Only fixed metadata is logged. Original private bodies, model diagnostics and
exceptions stay private. This command does not issue or publish forecasts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab import audit_count_requalify_v1 as audit
from nfl_lab import private_draft_store as store
from nfl_lab import gha_private_checkpoint as checkpoint
from tools.private_draft_store_v2 import actions_context

ROOT_KEYS = {"schema_version", "approved", "repository", "source_sha", "workflow_ref",
             "job_id", "single_writer_group", "issued_at_utc", "expires_at_utc",
             "operation", "maximum_new_fits", "protected_outcome_reads", "publication",
             "helper_sha256", "owner_authorization"}
OPERATION = "QUALIFIED_RESTORE_REQUALIFY_AND_DURABLY_VERIFY"
READER_JOB = "audit-count-effective-restore-v1"
WORKFLOW_REF = audit.REPO+"/.github/workflows/lab.yml@refs/heads/research/weekly-storage-probe-v1"


@contextmanager
def metadata_deadline(seconds=180):
    """The unchanged private client requires a native timer before real HTTP.

    Scope it to metadata preparation. Child restore/requalification processes
    establish their own separate registered envelopes after this scope ends.
    """
    before=signal.getitimer(signal.ITIMER_REAL)
    handler=signal.getsignal(signal.SIGALRM)
    audit.require(before[1] == 0 and type(seconds) is int and 0 < seconds <= 180,
                  "FINITE_METADATA_WALL_ENVELOPE")
    started=time.monotonic()
    signal.signal(signal.SIGALRM,signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL,min(float(seconds),before[0]) if before[0]>0 else float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,handler)
        if before[0]>0:
            remaining=before[0]-(time.monotonic()-started)
            signal.setitimer(signal.ITIMER_REAL,max(.001,remaining))
            audit.require(remaining>0,"OUTER_METADATA_DEADLINE_EXHAUSTED")


def checked_root(body, expected, env):
    audit.require(audit.sha(body) == expected, "ROOT_GO_HASH")
    go = checkpoint.strict_json(body)
    audit.require(set(go) == ROOT_KEYS and go["schema_version"] == "audit-count-root-GO-v1"
        and go["approved"] is True and go["repository"] == audit.REPO
        and go["operation"] == OPERATION and go["publication"] is False
        and type(go["maximum_new_fits"]) is int and go["maximum_new_fits"] == 0
        and type(go["protected_outcome_reads"]) is int and go["protected_outcome_reads"] == 0
        and go["single_writer_group"] == "nfl-lab-single-writer"
        and go["owner_authorization"] == "OWNER_NFL_AUDIT_CONTINUATION_20261025", "CLOSED_OWNER_ROOT_GO")
    current = datetime.now(timezone.utc)
    issued, expires = store.utc(go["issued_at_utc"]), store.utc(go["expires_at_utc"])
    audit.require(issued <= current < expires and 0 < (expires-issued).total_seconds() <= 3600,
                  "ROOT_GO_CURRENT_CLOCK")
    audit.require(go["source_sha"] == env.get("GITHUB_SHA") == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        and go["workflow_ref"] == env.get("GITHUB_WORKFLOW_REF") == WORKFLOW_REF
        and go["job_id"] == audit.RESTORE_JOB
        and env.get("GITHUB_JOB") in {audit.RESTORE_JOB, READER_JOB}
        and env.get("GITHUB_ACTOR") == "NickNicky19" and env.get("GITHUB_ACTOR_ID") == "208912933",
                  "EXACT_OWNER_SOURCE_CONTEXT")
    expected_pins = {name:audit.sha((ROOT/name).read_bytes()) for name in
        ["tools/audit_count_hosted_v1.py", "tools/audit_count_requalify_v1.py",
         "nfl_lab/audit_count_requalify_v1.py", "nfl_lab/weekly_future_inference.py",
         ".github/workflows/lab.yml", "nfl_lab/audit_count_checkpoint_v1.py",
         "tools/audit_count_checkpoint_v1.py", "tools/audit_count_failure_v1.py",
         "nfl_lab/operational_failure_v1.py", "tools/operational_failure_v1.py",
         "tools/audit_count_verification_receipt_v1.py"]}
    audit.require(go["helper_sha256"] == expected_pins, "EXACT_REVIEWED_HOSTED_SOURCE")
    changes = subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",
        ".github","nfl_lab","tools","config","schemas","pyproject.toml",
        "requirements.lock","requirements-hosted-fixed-build-v1.lock"],cwd=ROOT,text=True)
    audit.require(changes == "", "CLEAN_EXACT_HOSTED_SOURCE_REQUIRED")
    event = checkpoint.strict_json(audit.read_bytes(env["GITHUB_EVENT_PATH"], 256 << 10))
    audit.require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == audit.REPO
        and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("GITHUB_RUN_ATTEMPT") == "1"
        and env.get("STORE_PERMISSION") == "write"
        and event.get("repository", {}).get("full_name") == audit.REPO
        and event.get("inputs", {}).get("mode") == audit.MODE
        and event["inputs"].get("inference_builder_go_json") == body.decode()
        and event["inputs"].get("inference_builder_go_sha256") == expected, "EXACT_NEW_ACTIONS_MODE")
    return go


def execute(command, *, env, receipt, timeout):
    # This reviewed child prints a closed, coarse summary only. Keep the exact
    # output privately, including on failure; never rerun the original phase.
    with receipt.open("xb") as output, receipt.with_suffix(".stderr").open("xb") as errors:
        os.chmod(receipt, 0o600)
        os.chmod(receipt.with_suffix(".stderr"), 0o600)
        result = subprocess.run(command, cwd=ROOT, env=env, timeout=timeout,
                                stdout=output, stderr=errors)
    if result.returncode:
        reason = "COUNT_CHILD_PHASE_FAILED"
        try:
            status = checkpoint.strict_json(audit.read_bytes(receipt, 32 << 10))
            candidate = status.get("reason")
            if isinstance(candidate, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", candidate):
                reason = candidate
        except Exception:
            pass
        raise audit.AuditGuardError(reason)


def prepare_package(env):
    runner = store.parents_safe(env["RUNNER_TEMP"])
    package_root = runner/("audit-count-package-"+env["GITHUB_RUN_ID"])
    audit.require(not package_root.exists(), "ONE_REVIEWED_HOSTED_INVOCATION")
    package_root.mkdir(mode=0o700)
    journal = package_root/"journal"
    journal.mkdir(mode=0o700)
    registration = json.loads((ROOT/"config/weekly-initial-continuation-v6-registration.json").read_text())
    config = json.loads((ROOT/"config/gha-private-checkpoint-v3.json").read_text())
    checkpoint.seed_pending(journal, config["external_pending_reservations"])
    client = store.Client(env.get("GITHUB_TOKEN"), env["GITHUB_RUN_ID"], journal=journal,
        source_sha=env["GITHUB_SHA"], job=actions_context(env,"write"), operation="restore")
    client.authenticate_actions_job()
    client.bind(registration["parent"]["handoff"]["runtime_binding"])
    client.draft()
    assets, total = client.inventory()
    release = client.json(client.path("/releases/"+str(client.binding["release_id"])))
    release["assets"] = assets
    inventory = package_root/"inventory.json"
    audit.private_write(inventory, audit.canonical([release]))
    package = package_root/"package"
    audit.prepare_package(ROOT, inventory, package)
    return package_root,package,total


def run(env):
    root_body = env["AUDIT_COUNT_ROOT_GO_JSON"].encode()
    checked_root(root_body, env["AUDIT_COUNT_ROOT_GO_SHA256"], env)
    audit.require(env.get("GITHUB_JOB") == audit.RESTORE_JOB, "WRITER_JOB_ONLY")
    with metadata_deadline():
        package_root,package,total=prepare_package(env)
    runner=store.parents_safe(env["RUNNER_TEMP"])
    plan_sha = (package/"PLAN.sha256").read_text().strip()
    plan = checkpoint.strict_json((package/"PLAN.json").read_bytes())
    output = runner/(audit.VERSION+"-"+env["GITHUB_RUN_ID"])
    audit.require(not output.exists(), "FRESH_RUN_DESTINATION")
    for phase in ("restore", "requalify"):
        go = audit.seal_phase(plan, plan_sha, phase, env, ROOT)
        go_body = audit.canonical(go)
        go_path = package/("GO."+phase+".json")
        audit.private_write(go_path, go_body)
        execute([sys.executable,"-I","-B",str(ROOT/"tools/audit_count_requalify_v1.py"),phase,"--execute",
                 "--package",str(package),"--plan-sha256",plan_sha,"--go",str(go_path),
                 "--go-sha256",audit.sha(go_body)],env=env,receipt=package_root/(phase+"-STATUS.json"),
                timeout=plan["runtime_envelopes"][phase]["wall_seconds"]+10)
    result = checkpoint.strict_json((output/"REQUALIFICATION_FINISHED.json").read_bytes())
    audit.require(result["state"] == "ZERO_FIT_REQUALIFIED_PRIVATE_PENDING_INTEGRATION"
                  and result["model_pairs"] == 18 and result["fits"] == 0, "COMPLETE_ZERO_FIT_REQUALIFICATION")
    return dict(state=result["state"], model_pairs=18, fits=0, protected_outcome_reads=0,
                public_release=False, private_durability_qualified=False,
                effective_result_sha256=checkpoint.binding(output/"REQUALIFICATION_FINISHED.json")["sha256"],
                original_inventory_bytes=total)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not args.execute:
        print('{"state":"REQUIRES_EXACT_ROOT_GO"}')
        return 2
    try:
        # Never let downstream private exception text or model values reach logs.
        with open(os.devnull,"w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            result=run(dict(os.environ))
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception as error:
        code = error.code if isinstance(error, (audit.AuditGuardError,store.StoreError)) else None
        reason = code if isinstance(code,str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code) else "HOSTED_COUNT_RECOVERY_FAILED"
        print(json.dumps(dict(state="FAILED_RETAINED",reason=reason,fits=0,public_release=False)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
