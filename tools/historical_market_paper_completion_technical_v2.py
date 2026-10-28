"""Separate technical V2 accounting reconstruction; V1 remains failed and consumed.

Only driver resources, controls and destinations differ. The original numeric
helper and immutable forecast/grade inputs remain unchanged.
"""
from __future__ import annotations

import argparse
import gc
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
import zipfile


def authenticate(ref):
    path = Path(ref["path"])
    if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("canonical immutable input path required")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if path.stat().st_size != ref["bytes"] or digest != ref["sha256"]:
        raise ValueError("immutable input binding changed")
    if "blob" in ref and not Path(ref["blob"]).samefile(path):
        raise ValueError("CAS blob alias changed")
    return path


def read_member(ref, columns=None, maximum_rows=100000):
    """Hash one immutable member, then decode only projected Parquet columns."""
    import pyarrow.parquet as pq
    with zipfile.ZipFile(authenticate(ref["container"])) as archive:
        if archive.namelist().count(ref["member"]) != 1:
            raise ValueError("unique exact frozen member required")
        info = archive.getinfo(ref["member"])
        if info.file_size != ref["bytes"] or info.file_size > 32 * 1024**2:
            raise ValueError("member byte envelope changed")
        with archive.open(info) as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != ref["sha256"]:
            raise ValueError("frozen member bytes changed")
        with archive.open(info) as stream:
            if columns is None:
                return json.loads(stream.read())
            parquet = pq.ParquetFile(stream)
            if parquet.metadata.num_rows > maximum_rows:
                raise ValueError("frozen row envelope exceeded")
            available = [c for c in columns if c in parquet.schema_arrow.names]
            import pandas as pd
            chunks = [batch.to_pandas(strings_to_categorical=True) for batch in
                      parquet.iter_batches(batch_size=8192, columns=available, use_threads=False)]
            frame = pd.concat(chunks, ignore_index=True) if chunks else parquet.read(columns=available, use_threads=False).to_pandas(strings_to_categorical=True)
            del chunks
            for name in frame.select_dtypes(include="object"):
                frame[name] = frame[name].astype("category")
            return frame


def _stop(*_args):
    raise TimeoutError("bounded paper completion budget exhausted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    plan_body = Path(args.plan).read_bytes()
    if hashlib.sha256(plan_body).hexdigest() != args.sha256:
        raise ValueError("exact postprocess plan hash required")
    plan = json.loads(plan_body)
    expected = {"state": "GO", "root": "/root", "independent_review": "PASS", "plan_sha256": args.sha256,
                "scope": "ONE_ZERO_FIT_FROZEN_PAPER_COMPLETION_TECHNICAL_V2", "main_finished_writer_closed": True}
    if (json.loads(Path(args.go).read_bytes()) != expected or plan["state"] != "ROOT_AND_REVIEWER_SEALED"
            or plan["version"] != "historical-market-paper-completion-technical-v2"):
        raise ValueError("exact root/reviewer GO and closed main writer required before NFL decode")
    caps = plan["resources"]
    if (caps["CPU_seconds"] != 60 or caps["wall_seconds"] != 90 or caps["RSS_bytes"] != 268435456
            or caps["managed_write_attempts"] != 1 or caps["output_capsule_bytes"] != 8388608
            or any(caps[k] != 0 for k in ["fits", "model_loads", "new_selection", "new_probabilities", "HTTP_calls"])):
        raise ValueError("finite zero-fit postprocessing contract changed")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    signal.signal(signal.SIGALRM, _stop)
    signal.signal(signal.SIGXCPU, _stop)
    signal.alarm(90)
    started, cpu = time.monotonic(), time.process_time()
    terminal = {"state": "CONSUMED", "version": "historical-market-paper-completion-technical-v2", "plan_sha256": args.sha256,
                "V1_failed_attempt_preserved": True, "total_registered_postprocess_attempts": 2,
                "purpose": "new accounting reconstruction from retained official forecasts; not reproduction of unretained V1 capsule", "managed_write_attempts": 0, "fits": 0,
                "model_loads": 0, "new_selection": 0, "new_probabilities": 0, "HTTP_calls": 0}
    native = Path(plan["native_receipt"])
    if native.exists():
        raise ValueError("paper completion already attempted; preserve without retry")
    native.parent.mkdir(parents=True, exist_ok=True)
    with native.open("x") as stream:
        json.dump(terminal, stream, sort_keys=True)
    try:
        for ref in plan["code_bindings"]:
            authenticate(ref)
        prior = json.loads(authenticate(plan["prior_V1_failure"]).read_bytes())
        authenticate(plan["prior_V1_consumed"])
        no_alias = json.loads(authenticate(plan["prior_V1_no_alias"]).read_bytes())
        if (prior["state"] != "FAILED_OR_INTERRUPTED" or prior["managed_write_attempts"] != 1
                or prior["resources"]["CPU_seconds"] <= 30 or no_alias["exists"] is not False):
            raise ValueError("original V1 failure and consumed write must remain explicit")
        main_terminal = json.loads(authenticate(plan["main_terminal"]).read_bytes())
        if main_terminal["state"] != plan["main_terminal_state"] or plan["excluded_seasons"] != [2025]:
            raise ValueError("completed immutable main terminal and no2025 contract required")
        main_plan = json.loads(authenticate(plan["main_plan"]).read_bytes())
        supplement = main_plan["paper_completion_supplement_predeclared"]
        if supplement["state"] != "NEW_ZERO_FIT_POSTPROCESS_ONLY_AFTER_FROZEN_FORECAST_AND_GRADE_CAPSULES":
            raise ValueError("original paper supplement differs")
        from nfl_lab.historical_market_paper_completion import (FORECAST_COLUMNS, MATCHED_COLUMNS, PAPER_COLUMNS,
            GRADE_COLUMNS, validate_packets, summarize_paper, offered_coverage, write_readable_csv)
        freeze = read_member(plan["members"]["global_freeze"])
        if freeze["state"] != "ALL_FORECASTS_PARAMETERS_AND_PAPER_LISTS_FROZEN_BEFORE_EVALUATION_GRADING":
            raise ValueError("authentic global forecast-before-grade freeze required")
        bindings = main_terminal["bindings"]
        for name in ["forecasts", "paper_frozen", "global_freeze", "calibrators"]:
            actual, expected_ref = plan["members"][name]["container"], bindings["FORECASTS_FROZEN.zip"]
            if any(actual[k] != expected_ref[k] for k in ["path", "sha256", "bytes"]):
                raise ValueError("forecast member is not from the completed main capsule")
        for name in ["matched", "paper_graded", "main_report"]:
            actual, expected_ref = plan["members"][name]["container"], bindings["SCORES_COMPLETE.zip"]
            if any(actual[k] != expected_ref[k] for k in ["path", "sha256", "bytes"]):
                raise ValueError("score member is not from the completed main capsule")
        frozen_members = {item["member"]: item for item in freeze["members"]}
        for name in ["forecasts", "paper_frozen", "calibrators"]:
            ref = plan["members"][name]
            if any(frozen_members[ref["member"]][k] != ref[k] for k in ["bytes", "sha256"]):
                raise ValueError("forecast member differs from the original pregrade freeze")
        forecasts = read_member(plan["members"]["forecasts"], FORECAST_COLUMNS)
        matched = read_member(plan["members"]["matched"], MATCHED_COLUMNS)
        frozen = read_member(plan["members"]["paper_frozen"], PAPER_COLUMNS, 20000)
        graded = read_member(plan["members"]["paper_graded"], GRADE_COLUMNS, 20000)
        validation = validate_packets(forecasts, matched, frozen, graded)
        summary = summarize_paper(forecasts, graded, main_plan["category_dependencies"])
        summary["validation"] = validation
        summary["immutable_input_members"] = plan["members"]
        summary["original_main_plan_sha256"] = plan["main_plan"]["sha256"]
        summary["postprocessing_plan_sha256"] = args.sha256
        summary["technical_V2"] = {"V1_state": prior["state"], "V1_resources": prior["resources"],
            "V1_write_consumed": 1, "additional_V2_CPU_seconds": 60, "additional_V2_wall_seconds": 90,
            "new_managed_write_allocation": 1, "old_budget_reset_or_refund": False,
            "identity": "new format/accounting reconstruction from retained official forecasts, not reproduction of unretained V1 bytes",
            "reason": "measured full inherited private CAS checks exceeded old 30 CPU seconds; checks unchanged"}
        summary["point_semantics"] = main_plan["point_semantics"]
        summary["all_offered_support_coverage"] = offered_coverage(matched)
        summary["already_scored_main_aggregate"] = read_member(plan["members"]["main_report"])["report"]
        summary["CSV_scope"] = "all matched offered rows, including nonprimary roles and unknown/DNP outcomes; selected flags are copied from frozen lists"
        del frozen, forecasts
        gc.collect()
        names = {}
        if plan.get("display_rosters"):
            import pyarrow.parquet as pq
            for ref in plan["display_rosters"]:
                frame = pq.read_table(authenticate(ref), columns=["season", "week", "gsis_id", "full_name"], use_threads=False).to_pandas()
                if not set(frame.season.unique()) <= {2024, 2026}:
                    raise ValueError("display lookup includes excluded season")
                for key, group in frame.groupby(["season", "week", "gsis_id"], observed=True):
                    unique = group.full_name.dropna().unique()
                    if len(unique) == 1:
                        names[key] = str(unique[0])
                del frame
        sink = io.BytesIO()
        class CappedBuffer(io.RawIOBase):
            def writable(self): return True
            def seekable(self): return True
            def tell(self): return sink.tell()
            def seek(self, *a): return sink.seek(*a)
            def flush(self): return sink.flush()
            def write(self, body):
                if sink.tell() + len(body) > caps["output_capsule_bytes"]:
                    raise ValueError("8MiB private output capsule exhausted")
                return sink.write(body)
        with zipfile.ZipFile(CappedBuffer(), "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            info = zipfile.ZipInfo("SUMMARY.json", (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode())
            info = zipfile.ZipInfo("PREDICTIONS_ACTUALS.csv", (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            with archive.open(info, "w") as binary:
                with io.TextIOWrapper(binary, encoding="utf-8", newline="", write_through=True) as text:
                    rows = write_readable_csv(text, matched, graded, model_bindings=main_plan["models"], names=names,
                        packet_bindings={"forecasts": plan["members"]["forecasts"]["sha256"],
                            "matched": plan["members"]["matched"]["sha256"], "calibrators": plan["members"]["calibrators"]["sha256"]})
            info = zipfile.ZipInfo("GUIDE.html", (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, "<!doctype html><meta charset=utf-8><title>Frozen paper scorecard</title><h1>Frozen paper scorecard</h1><p>PREDICTIONS_ACTUALS.csv contains every matched offered row. Empty actual/error cells mean unsupported or unknown outcomes. Policy selected flags copy the original frozen lists.</p><p>SUMMARY.json reports exact stakes and settlement denominators, all losing weeks, known-only drawdown and common-opportunity comparisons. Pushes and DNP voids refund; unknowns remain ungraded. Each selected offer stakes one hypothetical unit.</p><p>Projectiongap is a laboratory point-gap proxy, not the actual website. These are timing-unverified exploratory assumed settlements; they establish no authenticated profit or live forecast advantage. Five 2026 weeks cannot support the registered minimum-eight-week interval.</p>")
        body = sink.getvalue()
        del matched, graded, summary, names
        gc.collect()
        helper_ref = plan["storage"]["helper"]
        spec = importlib.util.spec_from_file_location("approved_paper_storage", authenticate(helper_ref))
        helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        storage_plan = plan["storage"]
        base = helper.load_frozen(authenticate(storage_plan["forward_implementation"]), storage_plan["legacy_library_root"])
        market_policy = json.loads(authenticate(storage_plan["market_policy"]).read_bytes())
        legacy_policy = json.loads(authenticate(storage_plan["legacy_policy"]).read_bytes())
        prior_policy = json.loads(authenticate(storage_plan["prior_policy"]).read_bytes())
        store = helper.build_storage_class(base)(storage_plan["legacy_cache"], market_policy, legacy_policy, prior_policy)
        output = Path(plan["output"])
        if output.parent != store.live_root / "research/historical-market-paper-completion-technical-v2" or output.exists():
            raise ValueError("exact fresh private postprocessor destination required")
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > caps["RSS_bytes"]:
            raise MemoryError("paper completion RSS cap exceeded before managed write")
        terminal["managed_write_attempts"] = 1
        terminal["attempted_capsule_bytes"] = len(body)
        store.write_bytes(output, body)
        ref = store.validate_reference(output)
        if hashlib.sha256(body).hexdigest() != ref["sha256"]:
            raise ValueError("private capsule readback mismatch")
        terminal.update(state="COMPLETE_FROZEN_PAPER_ACCOUNTING_AND_READABLE_SCORECARD", capsule_reference=ref,
                        readable_rows=rows, private_only=True, new_source_or_model_work=False)
    except BaseException as error:
        terminal.update(state="FAILED_OR_INTERRUPTED", error_class=type(error).__name__)
    finally:
        signal.alarm(0)
        terminal["resources"] = {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                                 "RSS_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        violations = []
        if terminal["resources"]["CPU_seconds"] > caps["CPU_seconds"]:
            violations.append("CPU")
        if terminal["resources"]["wall_seconds"] > caps["wall_seconds"]:
            violations.append("WALL")
        if terminal["resources"]["RSS_peak_bytes"] > caps["RSS_bytes"]:
            violations.append("RSS")
        terminal["final_resource_gate"] = {"checked_after_managed_write_and_validation": True,
            "CPU_limit_seconds": 60, "wall_limit_seconds": 90, "RSS_limit_bytes": 268435456, "violations": violations}
        if violations:
            terminal["state"] = "FAILED_FINAL_RESOURCE_GATE"
        # The consumed marker is retained; terminal metadata uses a separate
        # O_EXCL file in the already accounted working-metadata scope.
        result = native.with_name(native.stem + "-terminal.json")
        with result.open("x") as stream:
            json.dump(terminal, stream, sort_keys=True, indent=2, allow_nan=False); stream.write("\n")
        print(json.dumps(terminal, sort_keys=True))
    if terminal["state"] != "COMPLETE_FROZEN_PAPER_ACCOUNTING_AND_READABLE_SCORECARD":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
