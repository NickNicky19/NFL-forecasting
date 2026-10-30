"""One bounded fictional regression for exact-functional startup tie retention."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import resource
import signal
import sys
import time


def stamp():
    return datetime.now(timezone.utc).isoformat()


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--root", required=True, type=Path)
    cli.add_argument("--protocol", required=True, type=Path)
    cli.add_argument("--sha256", required=True)
    cli.add_argument("--output", required=True, type=Path)
    a = cli.parse_args()
    raw = a.protocol.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == a.sha256
    plan = json.loads(raw)
    assert plan["experiment_id"] == "e:mae-point-policy-functional-tie-v21-20261030"
    assert plan["resources"] == {"CPU_seconds": 10, "wall_seconds": 15, "RSS_bytes": 134217728,
        "attempts": 1, "fictional_cases": 8, "NFL_decodes_models_fits_forecasts_HTTP_CAS": 0}
    for rel, pin in plan["source_pins"].items():
        body = (a.root / rel).read_bytes()
        assert len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"]
    assert Path(__file__).resolve() == a.root.resolve()/"tools/category_topfive_mae_policy_v21_checks.py"
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (134217728, 134217728))
    signal.signal(signal.SIGALRM, lambda *args: (_ for _ in ()).throw(TimeoutError("15-second fictional bound")))
    signal.alarm(15)
    blocked = {"sockets": 0, "children": 0, "restricted_data_reads": 0}
    def audit(event, args):
        if event.startswith("socket."):
            blocked["sockets"] += 1
            raise RuntimeError("No network in fictional regression")
        if event in ("subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"):
            blocked["children"] += 1
            raise RuntimeError("No child in fictional regression")
        if event == "open" and isinstance(args[0], str) and args[0].endswith((".parquet", ".joblib", ".zip", ".csv")):
            blocked["restricted_data_reads"] += 1
            raise RuntimeError("No NFL source/model/forecast data in fictional regression")
    sys.addaudithook(audit)
    a.output.mkdir(parents=True, exist_ok=False)
    def save(name, item):
        b = (json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()
        assert len(b) <= 8192
        with (a.output/name).open("xb") as f:
            f.write(b)
    save("CONSUMED.json", {"state": "ONE_FICTIONAL_ATTEMPT_CONSUMED", "started_at_UTC": stamp(),
        "protocol_sha256": a.sha256, "experiment_id": plan["experiment_id"], "automatic_retries": 0})
    start, cpu = time.monotonic(), time.process_time()
    cases = []
    try:
        sys.path.insert(0, str(a.root))
        new = importlib.import_module("nfl_lab.category_topfive_median_policy_v21")
        old = importlib.import_module("nfl_lab.next_checkpoint_median_policy_v2")
        assert new.VERSION == "research-informed-stat-point-mae-v2.1"
        panel = dict(target="pass_att", scoring_target="pass_att", season=2026, season_type="REG",
            weeks=[1], role_population=["QB"], horizon_contract="FICTIONAL", source_availability_policy="FICTIONAL",
            comparison_receipt_sha256="a"*64)
        coverage = dict(offered_rows=10, scored_rows=8, games=2, weeks=1)
        def row(name, product="point_mean", functional="expected_mean", mae=1.0):
            return dict(method_id=name, product=product, functional=functional, MAE_2026=mae,
                mean_eligible=product=="point_mean", scoring_target="pass_att", comparison_identity=deepcopy(panel),
                coverage=deepcopy(coverage), score_source_receipt_sha256="b"*64, declared_fallback_included=True,
                diagnostics={"MSE_2026": 2.0}, operational_gates={k: True for k in new.REQUIRED_GATES})
        def request(product="point_mean", functional="expected_mean"):
            return dict(policy_version=new.VERSION, target="pass_att", scoring_target="pass_att", product=new.PRODUCT,
                primary="MAE", comparison_identity=deepcopy(panel), expected_coverage=deepcopy(coverage),
                current_display={"method_id": "Z_CURRENT", "product": product, "functional": functional, "version": "ORIGINAL_ACTUAL"},
                candidates=[row("A_STABLE", product, functional), row("Z_CURRENT", product, functional)])
        def check(name, condition):
            assert condition, name
            cases.append(name)
        r = request(); z = new.choose_numeric_projection(r)
        check("identical_mean_tie_retains_current", z["research_leader"] == z["operational_candidate"] == "Z_CURRENT")
        r = request("point_median", "full_cdf_lower_median")
        r["candidates"][1]["functional"] = "median_objective_point"
        z = new.choose_numeric_projection(r)
        check("changed_median_functional_uses_stable_ID", z["research_leader"] == "A_STABLE" and z["actual_prior_display"] == r["current_display"])
        r = request(); r["candidates"][1]["functional"] = "valid_mean_objective_point"
        check("changed_mean_functional_uses_stable_ID", new.choose_numeric_projection(r)["research_leader"] == "A_STABLE")
        r = request(); r["candidates"][1].update(product="point_median", functional="full_cdf_lower_median")
        check("changed_product_uses_stable_ID", new.choose_numeric_projection(r)["research_leader"] == "A_STABLE")
        r["candidates"][1]["MAE_2026"] = 0.5
        check("functional_change_is_not_new_accuracy_veto", new.choose_numeric_projection(r)["research_leader"] == "Z_CURRENT")
        r = request(); r["candidates"][1]["functional"] = "valid_mean_objective_point"
        for c in r["candidates"]: c["operational_gates"]["consumer_contract"] = False
        z = new.choose_numeric_projection(r)
        check("original_fallback_exact_no_alias_or_sentinel", z["operational_candidate"] is None and z["actual_prior_display"] == r["current_display"] == z["unchanged_fallback_contract"])
        r = request(); r["candidates"][1]["functional"] = "valid_mean_objective_point"
        r["candidates"].append(row("0_RESEARCH", mae=0.25)); r["candidates"][-1]["operational_gates"]["future_inference"] = False
        z = new.choose_numeric_projection(r)
        check("operational_tie_correct_independent_of_research_lead", z["research_leader"] == "0_RESEARCH" and z["operational_candidate"] == "A_STABLE")
        r = request(); r["candidates"][1]["functional"] = "valid_mean_objective_point"; r["policy_version"] = old.VERSION
        check("original_V2_behavior_preserved_under_original_ID", old.choose_numeric_projection(r)["research_leader"] == "Z_CURRENT")
        assert len(cases) == plan["resources"]["fictional_cases"]
        for rel, pin in plan["source_pins"].items():
            assert hashlib.sha256((a.root/rel).read_bytes()).hexdigest() == pin["sha256"]
        save("RESULT.json", {"state": "FICTIONAL_FUNCTIONAL_TIE_V21_PASS", "completed_at_UTC": stamp(),
            "protocol_sha256": a.sha256, "case_count": len(cases), "cases": cases, "blocked_attempts": blocked,
            "CPU_seconds": time.process_time()-cpu, "wall_seconds": time.monotonic()-start,
            "RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            "NFL_decodes_models_fits_forecasts_HTTP_CAS": 0, "original_V2_and_36_checks_unchanged": True})
    except BaseException as exc:
        save("FAILED.json", {"state": "FICTIONAL_FUNCTIONAL_TIE_V21_FAILED", "completed_at_UTC": stamp(),
            "error_type": type(exc).__name__, "error": str(exc), "completed_cases": cases,
            "CPU_seconds": time.process_time()-cpu, "wall_seconds": time.monotonic()-start,
            "automatic_retry": False})
        raise
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
