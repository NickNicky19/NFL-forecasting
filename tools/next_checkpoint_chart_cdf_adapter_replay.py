"""One bounded trusted chart-artifact adapter replay; no fit or outcome grading.

The separate root seal is required before any NFL/model decoding. Reference
forecasts are historical reconstruction, not genuine future issuance.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

BASE = Path(__file__).resolve().parents[1]
VERSION = "next-checkpoint-chart-cdf-adapter-replay-v1"
CAPS = {"CPU_seconds": 15, "wall_seconds": 30, "RSS_bytes": 512 * 1024**2,
        "invocations": 1, "model_loads": 1, "query_replays": 1,
        "fits": 0, "grading_runs": 0, "HTTP": 0, "managed_writes": 0,
        "automatic_retries": 0, "safe_metadata_bytes": 20 * 1024, "threads": 2}
CODE = ("tools/next_checkpoint_chart_cdf_adapter_replay.py",
        "nfl_lab/next_checkpoint_chart_cdf_inference.py", "nfl_lab/cdf_engine.py",
        "tools/next_checkpoint_chart_cdf_contract.py", "tools/next_checkpoint_chart_cdf_run.py")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    p = Path(value)
    require(p.is_absolute() and p.resolve() == p
            and not any(x.is_symlink() for x in (p, *p.parents)), "canonical nonsymlink path required")
    return p


def authenticate(ref):
    p = canonical(ref["path"])
    before = p.stat()
    require(before.st_size == ref["bytes"], "pinned input size differs")
    body = p.read_bytes()
    after = p.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            and sha(body) == ref["sha256"], "pinned input hash/stamp differs")
    return body


def load(ref, name):
    authenticate(ref)
    spec = importlib.util.spec_from_file_location(name, ref["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(plan, go, digest):
    require(plan.get("version") == VERSION and plan.get("state") == "ROOT_AND_INDEPENDENT_SEALED"
            and plan.get("execution_authorized") is True and plan.get("independent_review") == "PASS"
            and (plan.get("root_registration") or {}).get("registered_by") == "/root",
            "separate sealed technical registration required")
    require(go.get("state") == "ROOT_AND_INDEPENDENT_GO" and go.get("registered_by") == "/root"
            and go.get("independent_review") == "PASS" and go.get("plan_sha256") == digest
            and go.get("model_loads") == 1 and go.get("query_replays") == 1
            and go.get("predictive_fits") == 0 and go.get("grading_runs") == 0,
            "separate exact zero-fit/regrade root GO required")
    require(plan.get("resources") == CAPS, "exact new technical caps required")
    require(set(plan["code_bindings"]) == set(CODE)
            and go.get("code_sha256") == {k: v["sha256"] for k, v in plan["code_bindings"].items()},
            "complete replay code binding required")


def main():
    start_wall, start_cpu = time.monotonic(), time.process_time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    raw = canonical(args.plan).read_bytes()
    require(sha(raw) == args.sha256, "exact root sealed replay plan hash required")
    plan, go = json.loads(raw), json.loads(canonical(args.go).read_bytes())
    validate(plan, go, args.sha256)
    require(sys.flags.dont_write_bytecode, "invoke Python with -B")
    require(Path(sys.executable).resolve() == Path(plan["environment"]["interpreter"]["path"]),
            "exact reviewed Python interpreter required")
    for item in plan["environment"]["bindings"]:
        authenticate(item)
    authenticate(plan["environment"]["interpreter"])
    for relative in CODE:
        authenticate(plan["code_bindings"][relative])
        require(canonical(plan["code_bindings"][relative]["path"]) == BASE / relative,
                "replay source location differs")
    require(plan["original_study"]["sha256"] ==
            "250f187df9ddea7fdb19173cf958f33f97c1cbd0ce0ae449e76853502c5aafd7",
            "original successful study identity required")
    authenticate(plan["original_study"])
    root = canonical(plan["native_control_root"])
    require(root == BASE / "reports/next-nfl-checkpoint-chart-ppr-20261028/CDF_ADAPTER_REPLAY_NATIVE_V1"
            and not root.exists(), "one fresh technical attempt required")
    root.mkdir(mode=0o700)
    written = 0

    def record(name, value):
        nonlocal written
        body = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        require(written + len(body) <= CAPS["safe_metadata_bytes"], "safe metadata allowance exhausted")
        with (root / name).open("xb") as out:
            out.write(body)
            out.flush()
            os.fsync(out.fileno())
        written += len(body)

    record("CONSUMED.json", {"state": "ONE_SEPARATE_ADAPTER_REPLAY_ALLOCATION_CONSUMED_BEFORE_NFL_OR_MODEL_DECODE",
                            "version": VERSION, "plan_sha256": args.sha256, "resources": CAPS,
                            "prior_failures_and_allocations_preserved": True})
    phase = "guarded_imports"
    counts = {"model_loads": 0, "query_replays": 0, "forest_apply_calls": 0,
              "fit_attempts": 0, "grading_runs": 0, "socket_attempts": 0, "child_attempts": 0}
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS", "ARROW_NUM_THREADS", "ARROW_IO_THREADS"]:
        os.environ[name] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["MALLOC_ARENA_MAX"] = "1"
    sys.dont_write_bytecode = True
    resource.setrlimit(resource.RLIMIT_CPU, (15, 16))
    signal.signal(signal.SIGALRM, lambda *unused: (_ for _ in ()).throw(TimeoutError("bounded replay deadline")))
    signal.alarm(29)
    private_root = "/workspace/website-methods-research/"
    allowed_private = {x["path"] for x in plan["inputs"].values()}

    def guard(event, values):
        if event.startswith("socket."):
            counts["socket_attempts"] += 1
            raise ValueError("technical replay sockets forbidden")
        if event in {"subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"}:
            counts["child_attempts"] += 1
            raise ValueError("technical replay children forbidden")
        if event == "open" and isinstance(values[0], (str, bytes, os.PathLike)):
            path = os.fsdecode(values[0])
            if path.startswith(private_root) and path not in allowed_private:
                raise ValueError("unregistered private outcome/source read forbidden")
            mode, flags = values[1:3]
            write = isinstance(mode, str) and any(s in mode for s in "wax+")
            write = write or isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if write and not path.startswith(str(root) + "/"):
                raise ValueError("replay may write only counted safe receipts")

    sys.addaudithook(guard)
    try:
        runner = load(plan["code_bindings"]["tools/next_checkpoint_chart_cdf_run.py"], "chart_replay_guarded_bootstrap")
        runner.bootstrap_threadpool(plan["technical_bootstrap"])
        sys.path[:0] = [str(BASE / "tools"), str(BASE)]
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        from nfl_lab import next_checkpoint_chart_cdf_inference as adapter
        from next_checkpoint_chart_cdf_contract import normalized_team, key
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        for module, expected in plan["environment"]["versions"].items():
            if module == "python":
                require(sys.version.split()[0] == expected, "Python version differs")
            else:
                imported = __import__(module)
                require(imported.__version__ == expected, "reviewed dependency version differs")

        phase = "authenticate_freeze_and_feature_projection"
        frozen_bytes = authenticate(plan["inputs"]["frozen_model_and_predictions"])
        query_bytes = authenticate(plan["inputs"]["query2026"])
        # Leave unused training labels/numbers as lexemes. Only reference point
        # values and query identity metadata are converted, never graded outcomes.
        doc = json.loads(gzip.decompress(frozen_bytes), parse_int=str, parse_float=str)
        require(doc["target"] == "nick-chart-ppr-v1" and doc["plan_sha256"] == plan["original_study"]["sha256"]
                and doc["fitted_model_sha256"] == plan["model_sha256"]
                and int(doc["fitted_tree_count"]) == 32 and int(doc["score_lattice_scale"]) == 50
                and len(doc["forecasts"]) == 2117, "exact successful original model/reference contract differs")
        projection = list(dict.fromkeys([*adapter.IDENTITY, *adapter.CLOCKS, *adapter.FEATURES]))
        frame = pq.read_table(io.BytesIO(query_bytes), columns=projection,
                              filters=[("season", "==", 2026), ("week", "<=", 6)]).to_pandas()
        require(not frame.duplicated(["game_id", "team", "player_id"]).any(), "duplicate original feature query")
        query_by = {key(r): r for r in frame.to_dict("records")}
        require(len(query_by) == len(frame), "canonical alias collision in original query")
        rows, references = [], []
        for previous in doc["forecasts"]:
            ident = previous["identity"]
            lookup = key(ident)
            original = query_by.get(lookup)
            require(original is not None and previous["feature_query_available"] is True,
                    "reference with absent required query/clock requires distinct admission; no invented time")
            require(int(original["season"]) == int(ident["season"]) and int(original["week"]) == int(ident["week"])
                    and normalized_team(original["opponent"]) == normalized_team(ident["opponent"]),
                    "reference/query identity differs")
            row = {name: original.get(name, np.nan) for name in adapter.FEATURES + adapter.CLOCKS}
            for name in ["cutoff_utc", "kickoff_utc"]:
                require(pd.notna(row[name]) and pd.Timestamp(row[name]) == pd.Timestamp(previous[name]),
                        "reference/query required horizon differs")
            clock = row["feature_max_source_available_utc"]
            old = previous["source_feature_max_utc"]
            require((pd.isna(clock) and old is None) or
                    (pd.notna(clock) and old is not None and pd.Timestamp(clock) == pd.Timestamp(old)),
                    "reference/query feature clock differs")
            row.update({name: int(ident[name]) if name in {"season", "week"} else ident[name]
                        for name in adapter.IDENTITY if name != "position"})
            row.update(position=previous["position"], team=normalized_team(ident["team"]),
                       opponent=normalized_team(ident["opponent"]), feature_query_available=True)
            rows.append(row)
            references.append(previous)

        phase = "one_trusted_model_load"
        model_body = base64.b64decode(doc["fitted_model_pickle_base64"], validate=True)
        require(sha(model_body) == plan["model_sha256"], "exact frozen trusted model digest differs")
        for bad_body, bad_hash in [(model_body + b"invalid", plan["model_sha256"]), (model_body, "0" * 64)]:
            try:
                adapter.load_reviewed_model(bad_body, expected_sha256=bad_hash)
            except ValueError:
                pass
            else:
                raise AssertionError("unreviewed model accepted")
        counts["model_loads"] += 1
        model = adapter.load_reviewed_model(model_body, expected_sha256=plan["model_sha256"])

        def deny_fit(*unused, **unused_keywords):
            counts["fit_attempts"] += 1
            raise ValueError("technical replay fit forbidden")

        adapter.engine.LeafCDFModel.fit = classmethod(deny_fit)
        model.forest.fit = deny_fit
        original_apply = model.forest.apply

        def counted_apply(*args, **kwargs):
            counts["forest_apply_calls"] += 1
            require(counts["forest_apply_calls"] <= 1, "one combined query forest application allowed")
            return original_apply(*args, **kwargs)

        model.forest.apply = counted_apply
        # Fictional unseen players exercise inference shape only; no NFL
        # evidence or outcomes are added. All four share one combined replay.
        fictional = []
        for index, role in enumerate(["QB", "RB", "WR", "TE"]):
            row = dict(zip(adapter.FEATURES, model.design.medians))
            row.update(season=2026, week=9, game_id="FICTIONAL-ADAPTER-ONLY", player_id=f"FICTIONAL-{index}",
                       team="ZZZ", opponent="YYY", position=role,
                       cutoff_utc="2026-11-01T17:30:00+00:00", kickoff_utc="2026-11-01T19:00:00+00:00",
                       feature_max_source_available_utc="2026-10-30T18:00:00+00:00",
                       f_player_games_prior=3., feature_query_available=True)
            if index == 1:
                row["f_player_games_prior"] = 0.
            if index == 2:
                row["feature_max_source_available_utc"] = None
            if index == 3:
                row["feature_query_available"] = False
            fictional.append(row)
        source = plan["source_policy_sha256"]
        rejections = []
        bad_queries = [pd.DataFrame([fictional[0], fictional[0]]), pd.DataFrame([dict(fictional[0], actual=0.)]),
                       pd.DataFrame([dict(fictional[0], feature_max_source_available_utc=fictional[0]["cutoff_utc"])])]
        for name, query in zip(["duplicate_identity", "target_outcome", "equal_source_cutoff"], bad_queries):
            try:
                adapter.predict_reviewed(model, query, source_policy_sha256=source, expected_source_policy_sha256=source)
            except ValueError:
                rejections.append(name)
            else:
                raise AssertionError("adversarial query accepted")
        try:
            adapter.predict_reviewed(model, pd.DataFrame([fictional[0]]),
                                     source_policy_sha256="0" * 64, expected_source_policy_sha256=source)
        except ValueError:
            rejections.append("source_policy")
        else:
            raise AssertionError("unreviewed source policy accepted")
        require(counts["forest_apply_calls"] == 0, "invalid queries reached model inference")
        phase = "one_reference_plus_fictional_query_replay"
        counts["query_replays"] += 1
        outputs = adapter.predict_reviewed(model, pd.DataFrame(rows + fictional),
                                           source_policy_sha256=source, expected_source_policy_sha256=source)
        require(len(outputs) == 2121, "complete single replay output missing")
        worst = {name: 0. for name in ["mean", "median", "p10", "p90"]}
        for result, reference in zip(outputs[:2117], references):
            expected = {"mean": reference["predictions"]["LEAF_CDF_CHART_MEAN_V1"],
                        "median": reference["predictions"]["LEAF_CDF_CHART_MEDIAN_V1"],
                        **reference["distribution_intervals"]["LEAF_CDF"]}
            require(result["fallback"] == reference["fallback"], "reference fallback differs")
            for name in worst:
                delta = abs(result[name] - float(expected[name]))
                require(np.isfinite(result[name]) and delta <= 1e-10, "exact-law reference functional replay differs")
                worst[name] = max(worst[name], delta)
        expected_fictional = ["", "cold_or_unknown_history_position_prior", "unknown_feature_clock_position_prior",
                              "missing_feature_query_position_prior"]
        require([r["fallback"] for r in outputs[2117:]] == expected_fictional,
                "fictional future query/fallback contract differs")
        require(all(np.isfinite(r[name]) for r in outputs for name in worst), "nonfinite replay output")
        require(all(r["p10"] <= r["median"] <= r["p90"] for r in outputs), "invalid replay quantile order")
        use = {"CPU_seconds": time.process_time() - start_cpu, "wall_seconds": time.monotonic() - start_wall,
               "RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        require(use["CPU_seconds"] <= 15 and use["wall_seconds"] <= 30 and use["RSS_bytes"] <= 512 * 1024**2,
                "technical replay resource allowance exceeded")
        require(counts == {"model_loads": 1, "query_replays": 1, "forest_apply_calls": 1,
                           "fit_attempts": 0, "grading_runs": 0, "socket_attempts": 0, "child_attempts": 0},
                "exact technical work/zero-attempt guard differs")
        result = {"state": "HISTORICAL_REFERENCE_AND_FICTIONAL_ADAPTER_REPLAY_PASS", "version": VERSION,
                  "plan_sha256": args.sha256, "frozen_capsule_sha256": plan["inputs"]["frozen_model_and_predictions"]["sha256"],
                  "model_sha256": plan["model_sha256"], "reference_rows": 2117, "fictional_unseen_rows": 4,
                  "maximum_absolute_reference_difference": worst, "rejected_adversarial_queries": rejections,
                  "fictional_fallbacks": expected_fictional, "work_counters": counts, "resources": use,
                  "NFL_outcome_grading": False, "genuine_future_issuance": False, "new_live_use": False,
                  "remaining": ["current-source-query admission", "approved producer artifact restoration",
                                "genuine pregame durable capture", "policy selection and validated consumer"]}
        record("COMPLETE.json", result)
        print(json.dumps({"state": result["state"], "resources": use, "work_counters": counts,
                          "safe_receipt_bytes": written}, sort_keys=True))
    except BaseException as exc:
        record("FAILED.json", {"state": "ADAPTER_REPLAY_TECHNICAL_FAILURE_RETAINED", "version": VERSION,
                               "plan_sha256": args.sha256, "phase": phase, "failure_type": type(exc).__name__,
                               "work_counters": counts, "prior_allocations_remain_consumed": True,
                               "automatic_retry": False, "raw_values_or_vectors_logged": False})
        print(json.dumps({"state": "ADAPTER_REPLAY_TECHNICAL_FAILURE_RETAINED", "phase": phase,
                          "failure_type": type(exc).__name__, "work_counters": counts}, sort_keys=True))
        raise SystemExit(1)
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
