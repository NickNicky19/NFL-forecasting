"""Exact finite GO gate for metadata-only frozen-score diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import resource
import signal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    raw = Path(args.plan).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise ValueError("exact sealed diagnostic plan required")
    plan = json.loads(raw)
    expected = {"state": "GO", "root": "/root", "independent_review": "PASS", "plan_sha256": args.sha256,
                "scope": "ONE_NEXT_NFL_CHECKPOINT_LAD_DIAGNOSTICS_V1"}
    if (plan["state"] != "ROOT_AND_REVIEWER_SEALED" or plan["execution_authorized"] is not True
            or json.loads(Path(args.go).read_bytes()) != expected):
        raise ValueError("exact diagnostic root/reviewer GO required before NFL score rows")
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("finite diagnostic wall cap")))
    signal.alarm(14)
    from nfl_lab.historical_market_comparison import authenticate, read_capsule_member, Budget, clean
    from nfl_lab.next_checkpoint_diagnostics import VERSION, evaluate
    import pandas as pd
    budget = Budget(plan["resources"])
    for ref in plan["implementation_bindings"]:
        authenticate(ref)
    authenticate(plan["metadata_descriptor"])
    if plan["version"] != VERSION:
        raise ValueError("diagnostic version mismatch")
    output = Path(plan["output"])
    if output.exists():
        raise ValueError("one fresh diagnostic invocation; no retry")
    output.mkdir(parents=True)
    (output / "CONSUMED.json").write_text(json.dumps({"state": "ONE_FROZEN_SCORE_DIAGNOSTIC_INVOCATION_CONSUMED", "plan_sha256": args.sha256}) + "\n")
    try:
        rows = pd.read_parquet(io.BytesIO(read_capsule_member(plan["input"])))
        report = evaluate(rows, plan["expected_cells"])
        report.update(input=plan["input"], resources=budget.receipt(), offhost_restoration="UNPROVEN")
        body = (json.dumps(clean(report), sort_keys=True, indent=2) + "\n").encode()
        if len(body) > 65536:
            raise ValueError("64KiB safe aggregate output cap")
        path = output / "DIAGNOSTICS.json"
        with path.open("xb") as stream:
            stream.write(body)
        budget.check()
        print(json.dumps({"state": report["state"], "path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "resources": budget.receipt()}))
    except BaseException as error:
        (output / "FAILED.json").write_text(json.dumps({"state": "DIAGNOSTIC_FAILED_NO_RETRY", "error": str(error), "resources": budget.receipt()}) + "\n")
        raise
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
