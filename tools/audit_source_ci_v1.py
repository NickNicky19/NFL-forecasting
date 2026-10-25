"""Software CI only: independent full collection, four shards, durable coverage.

No network, credentials, numerical imports or production worker authority.
The supervisor stops before the existing job deadline to reserve artifact time.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

VERSION = "audit-source-ci-v1"
SHARDS = 4
MAX_NODES = 20000
FILE_CAP = 32 << 20
DIAGNOSTIC_CAP = 8192
SUCCESS = {"passed", "skipped", "xfailed", "xpassed"}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def node_label(node):
    return node if len(node) <= 256 else node[:256] + "... sha256=" + hashlib.sha256(node.encode()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def identity():
    value = {key: os.environ.get(key, "LOCAL") for key in
        ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID")}
    return dict(value, GITHUB_RUN_ATTEMPT=os.environ.get("GITHUB_RUN_ATTEMPT", "1"))


def save(path, value):
    raw = canonical(value)
    require(len(raw) <= FILE_CAP, "BOUNDED_CI_RECEIPT")
    path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as output:
        output.write(raw);output.flush();os.fsync(output.fileno())
    os.replace(temp, path)


def read(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= FILE_CAP,
        "BOUNDED_REGULAR_CI_RECEIPT_REQUIRED")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_CI_JSON_KEY")
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=pairs)


def partition(nodes, shard):
    require(type(shard) is int and 0 <= shard < SHARDS, "FOUR_CI_SHARDS_ONLY")
    modules = {}
    for node in sorted(nodes):modules.setdefault(node.split("::", 1)[0], []).append(node)
    plans, loads = [[] for _ in range(SHARDS)], [0] * SHARDS
    # Keep module autouse fixtures local; balance whole modules by node count.
    for module, items in sorted(modules.items(), key=lambda pair:(-len(pair[1]), pair[0])):
        chosen = min(range(SHARDS), key=lambda i:(loads[i], i))
        plans[chosen] += items;loads[chosen] += len(items)
    return sorted(plans[shard])


def journal(directory, event):
    raw = canonical(event) + b"\n"
    path = Path(directory) / "events.jsonl"
    require(path.stat().st_size + len(raw) <= FILE_CAP,
        "BOUNDED_CI_EVENT_JOURNAL")
    with path.open("ab") as output:
        output.write(raw);output.flush();os.fsync(output.fileno())


def events(directory):
    path = Path(directory) / "events.jsonl"
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= FILE_CAP,
        "DURABLE_CI_EVENT_JOURNAL_REQUIRED")
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def start(directory, mode, shard=None):
    directory = Path(directory).absolute()
    require(not directory.exists(), "CI_ATTEMPT_OUTPUT_MUST_BE_NEW")
    directory.mkdir(parents=True)
    (directory / "events.jsonl").touch()
    save(directory / "run.json", dict(schema_version=VERSION, identity=identity(), mode=mode,
        shard=shard, shards=SHARDS, started_at=stamp()))
    return directory


class Recorder:
    def __init__(self, directory, mode, shard):
        self.directory, self.mode, self.shard = Path(directory), mode, shard
        self.nodes, self.reports, self.diagnostic_bytes = [], {}, {}

    def pytest_itemcollected(self, item):
        self.nodes.append(item.nodeid)

    def pytest_deselected(self, items):
        journal(self.directory, dict(type="collection_error", reason="EXTERNAL_TEST_DESELECTION_FORBIDDEN"))

    def pytest_collectreport(self, report):
        if report.failed:
            message = str(report.longrepr)[:DIAGNOSTIC_CAP]
            journal(self.directory, dict(type="collection_error", reason=message))
            print("SOURCE_CI_COLLECTION_ERROR " + json.dumps(message), flush=True)

    def pytest_collection_modifyitems(self, session, config, items):
        import pytest
        # itemcollected sees the complete discovery BEFORE any selection hooks.
        nodes = sorted(self.nodes)
        checks = dict(bounded_count=0 < len(nodes) <= MAX_NODES, unique=len(set(nodes)) == len(nodes),
            bounded_ids=all(type(n) is str and 0 < len(n) <= 4 << 20 for n in nodes),
            full_items=Counter(item.nodeid for item in items) == Counter(nodes),
            no_keyword=not config.option.keyword, no_mark_filter=not config.option.markexpr,
            no_ignore=not config.option.ignore, no_ignore_glob=not config.option.ignore_glob,
            no_deselect=not config.option.deselect, no_last_failed=not getattr(config.option, "lf", False),
            no_failed_first=not getattr(config.option, "failedfirst", False))
        valid = all(checks.values())
        assigned = nodes if self.mode == "collect" else partition(nodes, self.shard)
        save(self.directory / "collection.json", dict(schema_version=VERSION, nodes=nodes,
            nodes_sha256=digest(nodes), assigned=assigned, unfiltered=valid))
        if not valid:
            reason = "UNFILTERED_FULL_COLLECTION_REQUIRED:" + ",".join(k for k,v in checks.items() if not v)
            journal(self.directory, dict(type="collection_error", reason=reason))
            print("SOURCE_CI_COLLECTION_ERROR " + reason, flush=True)
            raise pytest.UsageError("UNFILTERED_FULL_COLLECTION_REQUIRED")
        if self.mode != "collect":
            selected = set(assigned)
            items[:] = [item for item in items if item.nodeid in selected]

    def pytest_runtest_logstart(self, nodeid, location):
        self.reports[nodeid] = []
        journal(self.directory, dict(type="attempted", nodeid=nodeid))
        print("SOURCE_CI_START " + json.dumps(node_label(nodeid)), flush=True)

    def pytest_runtest_logreport(self, report):
        row = dict(type="report", nodeid=report.nodeid, when=report.when, outcome=report.outcome,
            wasxfail=str(getattr(report, "wasxfail", ""))[:1024],
            reason=str(report.longrepr)[:1024] if report.skipped else "")
        self.reports.setdefault(report.nodeid, []).append(row)
        journal(self.directory, row)
        if report.failed:
            remaining = DIAGNOSTIC_CAP - self.diagnostic_bytes.get(report.nodeid, 0)
            if remaining > 0:
                message = str(report.longrepr)[:remaining]
                self.diagnostic_bytes[report.nodeid] = DIAGNOSTIC_CAP - remaining + len(message)
                diagnostic = dict(type="diagnostic", nodeid=report.nodeid, when=report.when, message=message)
                journal(self.directory, diagnostic)
                print("SOURCE_CI_FAILURE " + json.dumps(dict(diagnostic, nodeid=node_label(report.nodeid))), flush=True)

    def pytest_runtest_logfinish(self, nodeid, location):
        rows = self.reports[nodeid]
        kind = outcome(rows)
        journal(self.directory, dict(type="completed", nodeid=nodeid, outcome=kind))


def outcome(rows):
    if any(row["outcome"] == "failed" for row in rows):return "failed"
    if any(row["outcome"] == "skipped" for row in rows):
        return "xfailed" if any(row["wasxfail"] for row in rows) else "skipped"
    if any(row["wasxfail"] for row in rows):return "xpassed"
    return "passed"


def worker(directory, mode, shard):
    # Match `python -m pytest`: the selected checkout, not tools/ or an
    # unrelated editable installation, supplies the project's imports.
    sys.path.insert(0, str(Path.cwd()))
    import pytest
    # Runs last, so another collection hook cannot silently remove test nodes.
    Recorder.pytest_collection_modifyitems = pytest.hookimpl(trylast=True)(Recorder.pytest_collection_modifyitems)
    recorder = Recorder(directory, mode, shard)
    args = ["-q", "--tb=no", "--no-summary", "--show-capture=no", "--maxfail=0", "-p", "no:cacheprovider"]
    if mode == "collect":args += ["--collect-only", "-q"]
    code = int(pytest.main(args, plugins=[recorder]))
    save(Path(directory) / "worker.json", dict(exit_code=code, finished_at=stamp()))
    if code == 5 and mode == "run":
        collected = read(Path(directory) / "collection.json")
        if collected["unfiltered"] and collected["nodes"] and not collected["assigned"]:
            return 0  # Actual pytest code 5 remains in worker.json; this partition is empty.
    return code


def materialize(directory, *, state=None, returncode=None, step_status=None, job_status=None, persist=True):
    directory = Path(directory)
    meta = read(directory / "run.json")
    collection = read(directory / "collection.json") if (directory / "collection.json").exists() else None
    worker_result = read(directory / "worker.json") if (directory / "worker.json").exists() else None
    attempted, completed, results, errors, reasons = [], [], {}, [], {}
    for row in events(directory):
        kind = row["type"]
        if kind == "attempted":attempted.append(row["nodeid"])
        elif kind == "completed":
            completed.append(row["nodeid"]);results[row["nodeid"]] = row["outcome"]
        elif kind == "collection_error":errors.append(row["reason"])
        elif kind == "report" and row["outcome"] == "skipped":reasons[row["nodeid"]] = row["reason"]
        else:require(kind in {"report", "diagnostic"}, "CLOSED_CI_EVENT_TYPE")
    previous = read(directory / "receipt.json") if (directory / "receipt.json").exists() else {}
    receipt = dict(meta, collection=collection, attempted=attempted, completed=completed,
        outcomes=results, skip_reasons=reasons, collection_errors=errors, worker=worker_result,
        state=state or previous.get("state", "INCOMPLETE"),
        returncode=returncode if returncode is not None else previous.get("returncode"),
        step_status=step_status or previous.get("step_status"), job_status=job_status or previous.get("job_status"),
        observed_at=stamp())
    if persist:save(directory / "receipt.json", receipt)
    return receipt


def supervise(directory, mode, shard, seconds=960):
    require(0 < seconds <= 960, "BOUNDED_SOFTWARE_CI_DEADLINE")
    directory = start(directory, mode, shard)
    start_epoch = os.environ.get("AUDIT_SOURCE_CI_STARTED_EPOCH")
    if start_epoch:
        # Stop by minute 18 of the UNCHANGED 20-minute job; artifact time is reserved.
        seconds = min(seconds, float(start_epoch) + 1080 - time.time())
    code, state, child = 124, "TIMED_OUT", None
    def interrupt(signum, frame):raise InterruptedError("CI_JOB_INTERRUPTED")
    old_handlers = {sig:signal.signal(sig, interrupt) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        if seconds > 0:
            command = [sys.executable, "-u", "-B", str(Path(__file__).resolve()), "_worker",
                "--output", str(directory), "--mode", mode]
            if shard is not None:command += ["--shard", str(shard)]
            child = subprocess.Popen(command, start_new_session=True)
            try:
                code = child.wait(timeout=seconds)
                state = "COMPLETED" if code == 0 else "FAILED"
            except subprocess.TimeoutExpired:pass
    except InterruptedError:
        state, code = "INTERRUPTED", 130
    finally:
        # Ignore repeated cancellation while preserving the already fsynced journal.
        for sig in old_handlers:signal.signal(sig, signal.SIG_IGN)
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL);child.wait(timeout=5)
        materialize(directory, state=state, returncode=code)
        for sig, handler in old_handlers.items():signal.signal(sig, handler)
    return code


def verified_receipt(directory, *, mode, shard, expected_identity):
    directory = Path(directory)
    saved = read(directory / "receipt.json")
    # Reconstruct all claimed progress from the actual append-only event journal.
    observed = materialize(directory, persist=False)
    require({k:v for k,v in saved.items() if k != "observed_at"}
        == {k:v for k,v in observed.items() if k != "observed_at"}, "CI_RECEIPT_JOURNAL_MISMATCH")
    require(observed["schema_version"] == VERSION and observed["identity"] == expected_identity
        and observed["mode"] == mode and observed["shard"] == shard and observed["shards"] == SHARDS,
        "EXACT_CI_ATTEMPT_SOURCE_AND_SHARD")
    pytest_ok = observed["worker"] is not None and (observed["worker"]["exit_code"] == 0
        or mode == "run" and observed["worker"]["exit_code"] == 5
        and observed["collection"] is not None and observed["collection"]["assigned"] == [])
    require(observed["state"] == "COMPLETED" and observed["returncode"] == 0 and pytest_ok
        and observed["step_status"] == observed["job_status"] == "success"
        and not observed["collection_errors"], "ALL_CI_WORKER_AND_JOB_STATUSES_MUST_SUCCEED")
    c = observed["collection"]
    require(type(c) is dict and c["schema_version"] == VERSION and c["unfiltered"] is True
        and 0 < len(c["nodes"]) <= MAX_NODES and c["nodes"] == sorted(set(c["nodes"]))
        and c["nodes_sha256"] == digest(c["nodes"]), "FULL_UNFILTERED_CI_COLLECTION_REQUIRED")
    return observed


def verify(root, needs, attempt):
    require(type(needs) is dict and set(needs) == {"collect", "shards"}
        and all(needs[k].get("result") == "success" for k in needs), "ACTUAL_UPSTREAM_CI_JOBS_MUST_SUCCEED")
    root = Path(root)
    expected = {f"audit-source-ci-collection-{attempt}"} | {f"audit-source-ci-shard-{i}-{attempt}" for i in range(SHARDS)}
    require(root.is_dir() and {p.name for p in root.iterdir()} == expected, "EXACT_FIVE_CI_ATTEMPT_ARTIFACTS_REQUIRED")
    ident = identity()
    require(ident["GITHUB_RUN_ATTEMPT"] == str(attempt), "EXACT_CURRENT_CI_ATTEMPT_REQUIRED")
    collect = verified_receipt(root / f"audit-source-ci-collection-{attempt}", mode="collect", shard=None, expected_identity=ident)
    nodes = collect["collection"]["nodes"]
    require(collect["collection"]["assigned"] == nodes and not collect["attempted"] and not collect["completed"],
        "INDEPENDENT_COLLECTION_MUST_NOT_EXECUTE_TESTS")
    all_attempted, all_completed, outcomes, skips = [], [], {}, {}
    for shard in range(SHARDS):
        r = verified_receipt(root / f"audit-source-ci-shard-{shard}-{attempt}", mode="run", shard=shard, expected_identity=ident)
        assigned = partition(nodes, shard)
        require(r["collection"]["nodes"] == nodes and r["collection"]["assigned"] == assigned,
            "EACH_SHARD_MUST_INDEPENDENTLY_COLLECT_THE_FULL_SAME_SUITE")
        require(Counter(r["attempted"]) == Counter(assigned) and Counter(r["completed"]) == Counter(assigned)
            and set(r["outcomes"]) == set(assigned) and set(r["outcomes"].values()) <= SUCCESS,
            "EVERY_ASSIGNED_NODE_MUST_BE_ATTEMPTED_AND_COMPLETED_EXACTLY_ONCE")
        # A completed node must have actual setup/teardown reports and a call or explicit setup skip/error.
        reports = {}
        for row in events(root / f"audit-source-ci-shard-{shard}-{attempt}"):
            if row["type"] == "report":reports.setdefault(row["nodeid"], []).append(row)
        require(set(reports) == set(assigned), "ACTUAL_PER_TEST_PHASE_REPORTS_REQUIRED")
        for node in assigned:
            rows = reports[node];phases = {row["when"] for row in rows}
            require({"setup", "teardown"} <= phases and phases <= {"setup", "call", "teardown"}
                and ("call" in phases or any(row["when"] == "setup" and row["outcome"] == "skipped" for row in rows))
                and outcome(rows) == r["outcomes"][node], "COMPLETE_TEST_PHASE_OUTCOME_REQUIRED")
        all_attempted += r["attempted"];all_completed += r["completed"]
        outcomes.update(r["outcomes"]);skips.update(r["skip_reasons"])
    require(Counter(all_attempted) == Counter(nodes) == Counter(all_completed), "NO_MISSING_OR_DUPLICATE_CI_NODE_EXECUTIONS")
    return dict(schema_version=VERSION + "-coverage", state="ALL_COLLECTED_TESTS_COVERED_AND_JOBS_SUCCESSFUL",
        identity=ident, collected=len(nodes), attempted=len(all_attempted), completed=len(all_completed),
        nodes_sha256=digest(nodes), outcome_counts=dict(Counter(outcomes.values())), explicit_skips=skips)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["collect", "run", "finish", "verify", "_worker"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard", type=int, choices=range(SHARDS))
    parser.add_argument("--mode", choices=["collect", "run"])
    parser.add_argument("--seconds", type=float, default=960)
    parser.add_argument("--step-status")
    parser.add_argument("--job-status")
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args(argv)
    if args.phase in {"collect", "run"}:
        require((args.shard is not None) == (args.phase == "run"), "EXPLICIT_FOUR_SHARD_SELECTION")
        return supervise(args.output, args.phase, args.shard, args.seconds)
    if args.phase == "_worker":return worker(args.output, args.mode, args.shard)
    if args.phase == "finish":
        materialize(args.output, step_status=args.step_status, job_status=args.job_status)
        return 0
    require(args.artifacts is not None, "CI_ARTIFACT_DIRECTORY_REQUIRED")
    try:
        result = verify(args.artifacts, json.loads(os.environ["AUDIT_SOURCE_CI_NEEDS_JSON"]), os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    except Exception as error:
        result = dict(schema_version=VERSION + "-coverage", state="COVERAGE_REJECTED", reason=str(error)[:256], identity=identity())
        save(args.output, result);print(json.dumps(result, sort_keys=True), flush=True)
        return 1
    save(args.output, result);print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
