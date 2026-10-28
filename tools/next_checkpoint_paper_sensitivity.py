"""Bounded accounting sensitivity on already frozen paper selections.

This never selects an offer, changes an outcome state or imputes an unknown.
The endpoints are outer bounds, not jointly attainable scenario forecasts.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import resource
import signal
import os
import threading
import time


def summarize(frame):
    import numpy as np

    odds = frame.decimal_odds.to_numpy(float)
    unknown = frame.settlement.eq("unknown_ungraded").to_numpy()
    values = frame.net_units.to_numpy(float)
    if not (np.isfinite(odds).all() and (odds > 1).all()
            and np.isnan(values[unknown]).all()
            and np.isfinite(values[~unknown]).all()):
        raise ValueError("frozen payouts or unknown states changed")
    net = float(values[~unknown].sum())
    count, pending = len(frame), int(unknown.sum())
    lower, upper = net - pending, net + float((odds[unknown] - 1).sum())
    return {"selected_unit_stakes": count, "known_settled_stakes": count-pending,
            "unresolved_unit_stakes": pending, "known_net_units": net,
            "all_unresolved_loss_outer_bound": lower,
            "all_unresolved_win_outer_bound": upper,
            "outer_ROI_on_all_selected_lower": lower/count if count else None,
            "outer_ROI_on_all_selected_upper": upper/count if count else None,
            "known_only_ROI": net/(count-pending) if count > pending else None,
            "zero_inside_outer_bounds": lower <= 0 <= upper}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    raw = Path(args.plan).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise ValueError("exact frozen sensitivity plan required")
    plan = json.loads(raw)
    go = {"state": "GO", "root": "/root", "independent_review": "PASS",
          "plan_sha256": args.sha256, "scope": "ONE_FROZEN_PAPER_SENSITIVITY_V1"}
    if (json.loads(Path(args.go).read_bytes()) != go
            or plan["state"] != "ROOT_AND_REVIEWER_SEALED"
            or not plan["execution_authorized"]):
        raise ValueError("root/reviewer gate required before private table decode")
    resource.setrlimit(resource.RLIMIT_CPU, (15, 16))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("30s sensitivity wall cap")))
    signal.signal(signal.SIGUSR1, lambda *_: (_ for _ in ()).throw(MemoryError("512MiB sensitivity peak RSS cap")))
    stop = threading.Event()
    def watch():
        while not stop.wait(.05):
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 > 512*1024**2:
                os.kill(os.getpid(), signal.SIGUSR1)
                return
    threading.Thread(target=watch, daemon=True).start()
    signal.alarm(29)
    start, cpu = time.monotonic(), time.process_time()
    output = Path(plan["output"])
    if output.exists():
        raise ValueError("one fresh invocation; retain all attempts")
    output.mkdir(parents=True)
    (output/"CONSUMED.json").write_text(json.dumps({"state": "ONE_FROZEN_PAPER_SENSITIVITY_CONSUMED", "plan_sha256": args.sha256})+"\n")
    def resources():
        return {"CPU_seconds": time.process_time()-cpu,
                "wall_seconds": time.monotonic()-start,
                "RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    try:
        from nfl_lab.historical_market_comparison import authenticate, read_capsule_member
        from nfl_lab.historical_market_paper_completion import OFFER, UNIT, POLICIES, STATES
        import numpy as np
        import pandas as pd
        for ref in plan["implementation_bindings"]:
            authenticate(ref)
        authenticate(plan["metadata_descriptor"])
        graded = pd.read_parquet(io.BytesIO(read_capsule_member(plan["inputs"]["graded"])))
        frozen = pd.read_parquet(io.BytesIO(read_capsule_member(plan["inputs"]["frozen"])))
        keys = ["policy"]+OFFER
        if (len(graded) != len(frozen) or len(graded) > plan["resources"]["max_selected_rows"]
                or graded.duplicated(["policy"]+UNIT).any()
                or set(graded.season.unique()) != {2024, 2026}
                or set(graded.policy.unique()) != set(POLICIES)
                or not graded.settlement.isin(STATES).all()):
            raise ValueError("original selection population changed")
        index = pd.MultiIndex.from_frame(frozen[keys])
        target = pd.MultiIndex.from_frame(graded[keys])
        positions = index.get_indexer(target)
        if not index.is_unique or not target.is_unique or (positions < 0).any():
            raise ValueError("frozen selection identity mismatch")
        for col in ["side", "decimal_odds"]:
            left = frozen.iloc[positions][col].reset_index(drop=True)
            right = graded[col].reset_index(drop=True)
            equal = (np.array_equal(left.to_numpy(float), right.to_numpy(float)) if col == "decimal_odds"
                     else np.array_equal(left.astype(object).to_numpy(), right.astype(object).to_numpy()))
            if not equal:
                raise ValueError("immutable selected side/payout differs")
        for state in STATES:
            group = graded.loc[graded.settlement.eq(state)]
            if state != "unknown_ungraded":
                expected = (group.decimal_odds-1 if state == "assumed_win"
                            else -1 if state == "assumed_loss" else 0)
                if not np.allclose(group.net_units, expected, atol=1e-12, rtol=0):
                    raise ValueError("stored settlement/payout arithmetic differs")
        season = [{"season": int(y), "policy": str(p), **summarize(g)}
                  for (y,p), g in graded.groupby(["season", "policy"], observed=True, sort=True)]
        category = [{"season": int(y), "target": str(t), "policy": str(p), **summarize(g)}
                    for (y,t,p), g in graded.groupby(["season", "target", "policy"], observed=True, sort=True)]
        result = {"version": plan["version"], "state": "FROZEN_PAPER_OUTER_SENSITIVITY_COMPLETE",
                  "inputs": plan["inputs"], "season_policy": season, "category_policy": category,
                  "rows": len(graded), "known_settlement_states_unchanged": True,
                  "fits": 0, "new_forecasts": 0, "new_selections": 0, "HTTP": 0,
                  "claim": "Timing-unverified exploratory assumed settlement; unknowns stay unknown. Outer endpoints allow each unresolved offer to lose or win at its original payout. They need not be jointly attainable across overlapping players/categories/opposite policies. No authenticated profitability or live selection claim.",
                  "ROI_denominator": "All selected flat-unit stakes for sensitivity bounds, including hypothetical refund stakes; known-only ROI separately conditions on known-settled stakes. Not a replacement for original ROI.",
                  "uncertainty": "Deterministic settlement sensitivity, not confidence intervals; original category/week uncertainty unchanged.",
                  "resources": resources()}
        body = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+"\n").encode()
        if len(body) > plan["resources"]["maximum_aggregate_bytes"]:
            raise ValueError("safe metadata cap exceeded")
        usage=resources()
        if usage["CPU_seconds"] > 15 or usage["wall_seconds"] > 30 or usage["RSS_bytes"] > 512*1024**2:
            raise ValueError("finite resource gate failed")
        path = output/"SENSITIVITY.json"
        path.open("xb").write(body)
        if path.read_bytes() != body:
            raise ValueError("safe aggregate readback differs")
        print(json.dumps({"state":result["state"], "rows":len(graded), "path":str(path), "bytes":len(body), "sha256":hashlib.sha256(body).hexdigest(), "resources":resources()}))
    except BaseException as error:
        (output/"FAILED.json").write_text(json.dumps({"state":"FAILED_NO_RETRY", "error":str(error), "resources":resources()})+"\n")
        raise
    finally:
        stop.set()
        signal.alarm(0)


if __name__ == "__main__":
    main()
