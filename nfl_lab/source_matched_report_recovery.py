"""Opt-in first scoring of a complete failed, pre-score benchmark freeze.

No learner, evaluator, old output, original limit or source assembly is changed.
Only the newly registered technical reporting namespace is writable here.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import io
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import socket
import platform
import stat
import sys
import time
from unittest.mock import patch

import pandas as pd

from . import source_matched_benchmark as base
from .owned_reference_batch import validate_owned_references
from . import owned_reference_batch
from .reference_runtime import _deadline

VERSION = "source-matched-report-recovery-v1-20261023"
POLICY_SHA256 = "d5e040355be0dd07ea0af0c4182e4f7c1fcd386fd8277b52d6a3217dfc196e35"
CLARIFICATIONS_SHA256 = "751c318afbae59c9f235cc9d43d57a1534446d9c4148f4ec7fe881b4e2b1e4f0"


def _pin(binding):
    path = base._spec(binding)
    if not path.is_absolute() or path.resolve() != path.absolute():
        raise ValueError("canonical absolute frozen path required")
    info = path.stat()
    if "inode" in binding and list(binding["inode"]) != [info.st_dev, info.st_ino]:
        raise ValueError("original frozen file inode changed")
    if "mode" in binding:
        mode = int(binding["mode"], 8)
        if mode != (stat.S_IMODE(info.st_mode) if mode <= 0o7777 else info.st_mode):
            raise ValueError("original frozen file mode changed")
    return path


def _read(binding):
    return json.loads(_pin(binding).read_text())


def _relative(root, relative):
    name = PurePosixPath(relative)
    if (not relative or name.is_absolute() or name.as_posix() != relative or "\\" in relative
            or any(part in {".", ".."} for part in name.parts)):
        raise ValueError("unsafe parent frozen output path")
    path = root / relative
    if path.resolve() != path.absolute() or root not in path.parents:
        raise ValueError("parent frozen path escaped its namespace")
    return path


def _pre_score(parent):
    if any((parent / name).exists() for name in ("SCORE_CONSUMED.json", "scored-freeze.json", "report.json")):
        raise ValueError("parent scoring already started; recovery ineligible")
    scored = parent / "private/scored"
    if scored.is_symlink() or any(p.is_file() or p.is_symlink() for p in scored.rglob("*")):
        raise ValueError("parent scored files exist; recovery ineligible")


def _environment(expected):
    if (expected["threads"] != 2 or expected["python"] not in {sys.version, platform.python_version()}
            or Path(expected["executable"]).resolve() != Path(sys.executable).resolve()):
        raise ValueError("frozen Python/runtime environment differs")
    if not isinstance(expected["packages"], dict) or len(expected["packages"]) != 9:
        raise ValueError("nine frozen package versions required")
    for package, version in expected["packages"].items():
        if importlib.metadata.version(package) != version:
            raise ValueError("frozen dependency version differs: " + package)


class RecoveryBudget(base.Budget):
    """Additional technical clocks, unchanged cumulative numerical counters."""
    def __init__(self, parent_usage, *, started, cpu_started):
        counters = {name: parent_usage[name] for name in ("estimator_attempts", "reference_calls",
            "query_prediction_or_law_row_incidences", "alias_copied_rows")}
        super().__init__({"max_wall_seconds": 600, "max_CPU_seconds": 900, "max_RSS_bytes": 2 * 1024**3,
            "reporting_reserve_seconds": 0, "max_fit_attempts": 168, "max_reference_calls": 66,
            "max_query_prediction_or_law_row_incidences": 3_000_000}, prior=counters, phase="report")
        self.start, self.cpu_start = started, cpu_started

    def check(self, *, rows=0, fit=False, reference=False):
        if fit or reference or self.fits != 168 or self.references != 66:
            raise AssertionError("recovery cannot consume an estimator or reference fit")
        return super().check(rows=rows)


@contextmanager
def no_new_models_or_network():
    def forbidden(*args, **kwargs):
        raise AssertionError("report recovery forbids fitting, reference inference and network")
    with base.no_fits(), ExitStack() as stack:
        for obj, name in ((base.models, "fit_predict"),
                (base.operational_models, "fit_operational_reference"),
                (base.operational_models, "predict_operational_artifact"),
                (base.cdf.LeafCDFModel, "fit"), (base.median.MedianBoostingModel, "fit"),
                (base.role.RoleCountBoostingModel, "fit"), (base, "run_benchmark"),
                (base, "report_benchmark"), (base, "fold"),
                (socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "getaddrinfo")):
            stack.enter_context(patch.object(obj, name, forbidden))
        yield


def _eligibility(session, spec, policy, clarification):
    completion = _read(spec["parent_completion"])
    execution = _read(spec["parent_execution_freeze"])
    freeze = _read(spec["parent_forecast_freeze"])
    if (spec["parent_config"]["sha256"] != policy["parent_policy_sha256"]
            or spec["parent_execution_freeze"]["sha256"] != policy["parent_freeze_sha256"]
            or spec["parent_forecast_freeze"]["sha256"] != clarification["original_forecast_freeze_sha256"]
            or spec["parent_completion"]["sha256"] != clarification["original_completion_sha256"]):
        raise ValueError("parent registration/failure/freeze differs from conditional repair")
    if (completion["state"] != "FAILED" or completion["returncode"] == 0 or completion["limit_reason"] != "WALL_LIMIT"
            or completion["threads"] != 2 or completion["new_HTTP_attempts_official_forecasts_confirmation"] != 0):
        raise ValueError("parent must have failed at its original wall limit before scoring")
    for observed, original in (("wall_seconds", "wall_seconds"), ("CPU_seconds", "CPU_seconds"),
                               ("peak_combined_RSS_bytes", "peak_combined_RSS_bytes")):
        if completion[observed] != clarification["observed_parent"][original]:
            raise ValueError("parent resource receipt differs from predeclared clarification")
    if (execution["plan_sha256"] != spec["parent_config"]["sha256"]
            or execution["actual_benchmark_invocations_fits_predictions_scoring_at_freeze"] != 0
            or len(execution["bindings"]) != 82):
        raise ValueError("parent execution freeze identity differs")
    if (freeze["state"] != "GLOBAL_FORECASTS_FROZEN" or freeze["fatal"] is not None
            or freeze["registration_sha256"] != spec["parent_config"]["sha256"] or len(freeze["bindings"]) != 1407):
        raise ValueError("complete original global prediction freeze required")
    slots, plan = freeze["slots"], base.planned_slots(session.categories)
    if len(slots) != 216:
        raise ValueError("all 216 original planned slots required")
    for slot, expected in zip(slots, plan):
        if any(slot[name] != expected[name] for name in ("year", "target", "method", "kind", "alias_method")):
            raise ValueError("original target/year/method/alias plan changed")
        if slot["state"] != ("BLOCKED" if expected["kind"] == "blocked" else "PREDICTION_FROZEN"):
            raise ValueError("198 complete frozen and 18 PPR-blocked slots required")
        if slot["state"] == "PREDICTION_FROZEN":
            needed = [slot["forecast"], slot["query"]]
            if slot["method"] == "leaf_cdf":
                needed += [slot["model"], slot["prior_forecast"]]
            if any(name not in freeze["bindings"] for name in needed) or type(slot["rows"]) is not int or slot["rows"] <= 0:
                raise ValueError("slot query/model/forecast dependency is not frozen")
    u = freeze["usage"]
    if (u["estimator_attempts"] != 168 or u["reference_calls"] != 66
            or u["query_prediction_or_law_row_incidences"] != clarification["observed_parent"]["query_or_law_rows"]
            or completion["wall_seconds"] < u["wall_seconds"] or completion["CPU_seconds"] < u["CPU_seconds"]
            or completion["peak_combined_RSS_bytes"] < u["max_RSS_bytes"]):
        raise ValueError("original immutable work/resource counters differ")
    _pre_score(session.parent_output)
    for binding in execution["bindings"]:
        _pin(binding)
    _environment(execution["environment"])
    verified_code = set()
    for binding in spec["additional_bindings"]:
        verified_code.add(_pin(binding))
    if not {Path(__file__).resolve(), Path(owned_reference_batch.__file__).resolve()} <= verified_code:
        raise ValueError("new recovery and batch helper code must be frozen explicitly")
    return freeze, completion, execution


def _resources(completion, budget):
    additional = budget.usage()
    parent = {name: completion[name] for name in ("state", "limit_reason", "wall_seconds", "CPU_seconds", "peak_combined_RSS_bytes")}
    return {"parent_failed": parent, "recovery_additional": additional,
        "sequential_total": {"wall_seconds": parent["wall_seconds"] + additional["wall_seconds"],
            "CPU_seconds": parent["CPU_seconds"] + additional["CPU_seconds"],
            "max_reported_phase_RSS_bytes": max(parent["peak_combined_RSS_bytes"], additional["max_RSS_bytes"]),
            "RSS_scope": "maximum across sequential phases; outer supervisor measures recovery process tree"},
        "original_limit_result": "FAILED; original budget is not reset or enlarged"}


def _score(session, freeze):
    import joblib
    parent = session.parent_output
    slots = [dict(slot) for slot in freeze["slots"]]
    session.scoring_slots = slots
    files = []
    for year in base.YEARS:
        session.budget.check()
        labels, audit = base.read_partition(session.source, year, "labels", allow_labels=True)
        session.write(f"scoring/label-read-{year}.json", audit)
        for slot in [s for s in slots if s["year"] == year and s["state"] == "PREDICTION_FROZEN"]:
            category = base._category(session.categories, slot["target"])
            relative = f"private/scored/{year}/{slot['target']}/{slot['method']}"
            try:
                session.budget.check()
                query = pd.read_parquet(parent / slot["query"])
                if len(query) != slot["rows"]:
                    raise ValueError("saved query row count changed")
                offered = base._outcomes(query, labels, category)
                frozen = pd.read_parquet(parent / slot["forecast"])
                if slot["method"] == "leaf_cdf":
                    model = joblib.load(io.BytesIO((parent / slot["model"]).read_bytes()))
                    session.budget.check(rows=len(query))
                    scored = base.cdf.score_frozen_rows(model, offered, frozen)
                    prior = pd.read_parquet(parent / slot["prior_forecast"])
                    session.budget.check(rows=len(query))
                    scored_prior = base.cdf.score_frozen_rows(model, offered, prior, prior_only=True)
                    session.frame(relative + "/role-prior.parquet", base.normalized(scored_prior, category, "role_prior"))
                    files.append(relative + "/role-prior.parquet")
                    del model
                else:
                    scored = base.median.score_frozen_rows(offered, frozen, category)
                session.frame(relative + "/rows.parquet", base.normalized(scored, category, slot["method"]))
                files.append(relative + "/rows.parquet")
                slot["state"] = "COMPLETED"
            except (base.BudgetExhausted, base.StorageQuotaError, base.StorageIntegrityError):
                slot["state"] = "SCORING_FAILED_RESOURCE"
                raise
            except Exception as error:
                slot.update(state="SCORING_FAILED", reason=type(error).__name__)
                session.failure(relative + "/FAILURE.json", error)
    result = {"state": "SCORED_ROWS_FROZEN", "generated_at": base.now(),
        "registration_sha256": session.config_sha256, "parent_forecast_freeze_sha256": session.parent_freeze_sha256,
        "slots": slots, "scored_files": files, "bindings": dict(session.bindings), "usage": session.budget.usage()}
    session.write("scored-freeze.json", result, freeze=False)
    return result


def _report(session, scored):
    from .source_matched_reporting import build_target_report, reporting_header
    categories = {target: base._category(session.categories, target) for target in base.models.TARGETS}
    for target in categories:
        categories[target]["benchmark_slots"] = [{k: s[k] for k in ("year", "method", "state", "reason") if k in s}
            for s in scored["slots"] if s["target"] == target]
    report, paired_files = reporting_header(replicates=500, seed=1703), []
    for target in base.models.TARGETS:
        session.budget.check()
        selected = [name for name in scored["scored_files"] if Path(name).parts[3] == target]
        frames = [pd.read_parquet(session.output / name, columns=list(base.REPORT_FIELDS)) for name in selected]
        if frames:
            rows = pd.concat(frames, ignore_index=True)
        else:
            text = {"game_id", "player_id", "target", "method", "participation_state", "outcome_state",
                "fallback", "history_state", "position", "team", "opponent", "kickoff_utc", "cutoff_utc"}
            rows = pd.DataFrame({name: pd.Series(dtype=bool if name == "primary_role" else object if name in text else float)
                for name in base.REPORT_FIELDS})
        item, pairs = build_target_report(rows, categories, target=target, replicates=500, seed=1703)
        session.budget.check()
        relative = f"private/paired-losses/{target}.parquet"
        session.frame(relative, pairs, freeze=False)
        paired_files.append({"target": target, "path": relative, "sha256": base.sha(session.output / relative), "rows": len(pairs)})
        report["targets"][target] = item
        del frames, rows, pairs
    session.write("private/paired-losses-manifest.json", {"files": paired_files}, freeze=False)
    return report


def run_recovery(config, *, config_sha256):
    """One separate zero-fit technical budget; no partial scoring continuation."""
    from threadpoolctl import threadpool_limits
    started, cpu_started = time.monotonic(), time.process_time()
    config = Path(config)
    if base.sha(config) != config_sha256:
        raise ValueError("recovery execution config hash mismatch")
    spec = json.loads(config.read_text())
    if spec["registration_id"] != VERSION:
        raise ValueError("fixed recovery registration required")
    policy, clarification = _read(spec["policy"]), _read(spec["clarifications"])
    if spec["policy"]["sha256"] != POLICY_SHA256 or spec["clarifications"]["sha256"] != CLARIFICATIONS_SHA256:
        raise ValueError("separately predeclared recovery policy required")
    if clarification["parent_plan_sha256"] != POLICY_SHA256:
        raise ValueError("recovery clarification policy mismatch")
    session = base.Session(_pin(spec["parent_config"]), spec["parent_config"]["sha256"], phase="report")
    session.parent_output = session.output
    if _pin(spec["parent_forecast_freeze"]) != session.parent_output / "forecast-freeze.json":
        raise ValueError("parent global forecast freeze path mismatch")
    destination = Path(spec["output"]).absolute()
    if (destination != Path(policy["output"]).absolute() or destination.resolve() != destination or destination == session.parent_output
            or session.parent_output in destination.parents or destination in session.parent_output.parents):
        raise ValueError("recovery requires a separate canonical output namespace")
    if (destination / "RECOVERY_CONSUMED.json").exists():
        raise RuntimeError("recovery invocation already consumed; no retry")
    session.output = session.storage.register_root(destination)
    session.config_sha256, session.bindings = config_sha256, {}
    session.write("RECOVERY_CONSUMED.json", {"generated_at": base.now(), "registration_sha256": config_sha256,
        "policy_sha256": POLICY_SHA256, "new_estimator_fits": 0, "new_reference_fits": 0})
    completion = None
    try:
        with _deadline(max(.001, 600 - (time.monotonic()-started))), threadpool_limits(limits=2), no_new_models_or_network():
            freeze, completion, execution = _eligibility(session, spec, policy, clarification)
            session.budget = RecoveryBudget(freeze["usage"], started=started, cpu_started=cpu_started)
            session.parent_freeze_sha256 = spec["parent_forecast_freeze"]["sha256"]
            bindings = {str(_relative(session.parent_output, name)): expected for name, expected in freeze["bindings"].items()}
            bindings[str(session.parent_output / "forecast-freeze.json")] = session.parent_freeze_sha256
            session.budget.check()
            refs, receipt = validate_owned_references(session.storage, bindings)
            session.budget.check()
            session.write("parent-owned-reference-validation.json", receipt)
            _pre_score(session.parent_output)
            session.write("REPAIR_SCORE_CONSUMED.json", {"generated_at": base.now(), "score_phases": 1,
                "parent_forecast_freeze_sha256": session.parent_freeze_sha256,
                "validated_parent_references": len(refs), "new_estimator_fits": 0, "new_reference_fits": 0})
            scored = _score(session, freeze)
            report = _report(session, scored)
            # Recheck immutable originals before a successful result is written.
            _eligibility(session, spec, policy, clarification)
            _, exit_receipt = validate_owned_references(session.storage, bindings)
            session.write("parent-owned-reference-final-validation.json", exit_receipt)
            session.budget.check()
            session.write("report.json", {"generated_at": base.now(), "registration_sha256": config_sha256,
                "parent_state": "FAILED", "parent_completion_sha256": spec["parent_completion"]["sha256"],
                "parent_forecast_freeze_sha256": session.parent_freeze_sha256,
                "scored_freeze_sha256": base.sha(session.output / "scored-freeze.json"),
                "resources": _resources(completion, session.budget), "report": report,
                "private_pairs_manifest_sha256": base.sha(session.output / "private/paired-losses-manifest.json"),
                "promotion": "NONE", "evidence": "EXPOSED_SOURCE_MATCHED_DEVELOPMENT; original run FAILED; separate zero-fit technical recovery"}, freeze=False)
            return report
    except BaseException as error:
        if hasattr(session, "scoring_slots"):
            session.write("scoring-attempts.json", {"generated_at": base.now(), "state": "FAILED",
                "slots": session.scoring_slots}, freeze=False)
        session.failure("RECOVERY_FAILURE.json", error)
        raise
    finally:
        session.write("RECOVERY_FINISHED.json", {"generated_at": base.now(),
            "state": "COMPLETED" if (session.output / "report.json").exists() else "FAILED",
            "resources": _resources(completion, session.budget) if completion else None}, freeze=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args(argv)
    result = run_recovery(args.config, config_sha256=args.config_sha256)
    print(json.dumps(base.clean(result), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
