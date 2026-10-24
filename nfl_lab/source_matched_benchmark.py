"""Finite same-source base benchmark with a global prediction/score boundary.

This opt-in orchestrator reuses frozen learners and scorers. It never invokes
old campaign CLIs or saved old-source controls. All artifacts and row results
are private; publication and qualification are outside this module.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import time
from unittest.mock import patch

import numpy as np
import pandas as pd

from . import cdf_engine as cdf, median_boosting as median, role_boosting as role
from . import models, operational_models, operational_sources
from .operational_storage import OperationalStorage, StorageQuotaError, StorageIntegrityError
from .reference_runtime import _deadline
from .state import digest

VERSION = "source-matched-base-benchmark-v1-20261023"
METHODS = ("leaf_cdf", "median_hgb", "count_A", "role_B", "recent", "pooled")
YEARS = (2022, 2023, 2024)
META = tuple(dict.fromkeys(cdf.KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc",
    "outcome_available_utc", "feature_max_source_available_utc", "season_type"]))
QUALIFICATION = ("official_physical_event", "participation_evidence", "source_policy", "stats_observed")
LABELS = tuple(t for t in models.TARGETS if t != "fantasy_ppr") + ("rush_td", "rec_td")
LAW_FIELDS = ("p10", "p90", "variance", "crps", "log_score", "cdf_actual_below", "cdf_actual", "brier")
REPORT_FIELDS = tuple(dict.fromkeys(cdf.KEYS + ["year", "target", "method", "point", "probability", "mean", "median",
    "actual", "participation_state", "outcome_state", "primary_role", "fallback", "history_state", "position", "team",
    "opponent", "kickoff_utc", "cutoff_utc", *LAW_FIELDS]))


class BudgetExhausted(RuntimeError):
    pass


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return {"numeric_state": "positive_infinity" if value > 0 else "negative_infinity" if value < 0 else "missing"}
    return value


def _spec(binding):
    path = Path(binding["path"])
    if path.is_symlink() or not path.is_file() or sha(path) != binding["sha256"]:
        raise ValueError("frozen file binding changed: " + path.name)
    if "bytes" in binding and path.stat().st_size != binding["bytes"]:
        raise ValueError("frozen input size changed")
    return path


def _category(categories, target):
    return {**categories[target], "target": target}


def package_kind(category, method):
    if category["state"] != "READY":
        return "blocked", None
    if method == "count_A" and category["support"] != "count":
        return "alias", "median_hgb"
    if method == "role_B" and len(category["modeled_roles"]) == 1:
        return "alias", "count_A"
    return ("reference", None) if method in ("recent", "pooled") else ("model", None)


def planned_slots(categories):
    return [{"year": year, "target": target, "method": method,
        "state": "BLOCKED" if package_kind(_category(categories, target), method)[0] == "blocked" else "UNRUN",
        "kind": package_kind(_category(categories, target), method)[0],
        "alias_method": package_kind(_category(categories, target), method)[1]}
        for year in YEARS for target in models.TARGETS for method in METHODS]


class Budget:
    def __init__(self, limits, *, prior=None, phase="run"):
        self.limits, self.phase = limits, phase
        self.prior = dict(prior or {})
        self.start, self.cpu_start = time.monotonic(), time.process_time()
        self.fits = int(self.prior.get("estimator_attempts", 0))
        self.references = int(self.prior.get("reference_calls", 0))
        self.rows = int(self.prior.get("query_prediction_or_law_row_incidences", 0))
        self.alias_rows = int(self.prior.get("alias_copied_rows", 0))

    def usage(self):
        return {"wall_seconds": self.prior.get("wall_seconds", 0.) + time.monotonic() - self.start,
            "CPU_seconds": self.prior.get("CPU_seconds", 0.) + time.process_time() - self.cpu_start,
            "max_RSS_bytes": max(self.prior.get("max_RSS_bytes", 0), resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
            "RSS_accounting": "single process high water; outer frozen supervisor enforces process tree",
            "estimator_attempts": self.fits, "reference_calls": self.references,
            "query_prediction_or_law_row_incidences": self.rows, "alias_copied_rows": self.alias_rows}

    def check(self, *, rows=0, fit=False, reference=False):
        u, b = self.usage(), self.limits
        reserve = b["reporting_reserve_seconds"] if self.phase == "run" else 0
        if (u["wall_seconds"] >= b["max_wall_seconds"] - reserve or u["CPU_seconds"] >= b["max_CPU_seconds"]
                or u["max_RSS_bytes"] > b["max_RSS_bytes"] or self.fits + int(fit) > b["max_fit_attempts"]
                or self.references + int(reference) > b["max_reference_calls"]
                or self.rows + rows > b["max_query_prediction_or_law_row_incidences"]):
            raise BudgetExhausted("registered cumulative benchmark budget exhausted")
        self.fits += int(fit)
        self.references += int(reference)
        self.rows += rows


class Session:
    def __init__(self, config, config_sha256, *, phase, prior=None):
        config = Path(config)
        if sha(config) != config_sha256:
            raise ValueError("benchmark registration hash mismatch")
        self.config_sha256, self.spec = config_sha256, json.loads(config.read_text())
        s = self.spec
        if s["registration_id"] != VERSION or s["methods"] != list(METHODS) or s["partitions"]["evaluation_years"] != list(YEARS):
            raise ValueError("fixed benchmark protocol required")
        self.budget = Budget(s["budgets"], prior=prior, phase=phase)
        self.source = _spec(s["input_features"])
        self.source_manifest = _spec(s["source_manifest"])
        self.policy = operational_sources.load_source_policy(_spec(s["source_policy"]))
        self.categories = json.loads(_spec(s["category_contract"]).read_text())["categories"]
        if set(self.categories) != set(models.TARGETS) or self.categories["fantasy_ppr"]["state"] == "READY":
            raise ValueError("all twelve categories including blocked exact PPR required")
        for target in models.TARGETS:
            if target != "fantasy_ppr":
                cdf.validate_category(_category(self.categories, target))
        self.storage = OperationalStorage(s["cache"], self.policy)
        self.output = self.storage.register_root(s["output"])
        self.bindings = {}

    def write(self, relative, value, *, freeze=True):
        path = self.output / relative
        self.storage.atomic_json(path, clean(value))
        if freeze:
            self.bindings[str(relative)] = sha(path)
        return path

    def frame(self, relative, frame, *, freeze=True):
        path = self.output / relative
        value = frame.copy()
        value.attrs.clear()
        self.storage.write_dataframe(value, path, index=False, compression="zstd")
        if freeze:
            self.bindings[str(relative)] = sha(path)
        return path

    def model(self, relative, model):
        import joblib
        body = io.BytesIO()
        joblib.dump(model, body, compress=3)
        self.storage.write_bytes(self.output / relative, body.getvalue())
        self.bindings[str(relative)] = sha(self.output / relative)

    def failure(self, relative, error):
        self.write(relative, {"generated_at": now(), "exception": type(error).__name__, "message": str(error)[:500]})


def _dataset(path):
    import pyarrow.dataset as ds
    return ds.dataset(path, format="parquet")


def read_partition(path, year, lane, *, allow_labels=False):
    """Arrow projects columns and filters seasons before semantic value decoding."""
    import pyarrow.dataset as ds
    if type(year) is not int or year not in YEARS:
        raise ValueError("protected or unregistered evaluation year; no values decoded")
    dataset = _dataset(path)
    names = dataset.schema.names
    query_columns = [c for c in names if c in META or c.startswith("f_")]
    if lane == "query":
        columns = query_columns
        predicate = ds.field("season") == year
    elif lane in ("train", "labels"):
        if lane == "labels" and not allow_labels:
            raise ValueError("evaluation labels require global forecast freeze and score consumption")
        columns = [c for c in names if c in (set(query_columns) if lane == "train" else set(cdf.KEYS) | set(META))
                   or c in LABELS or c == "participation_state" or c in QUALIFICATION]
        predicate = ((ds.field("season") >= 2019) & (ds.field("season") < year)) if lane == "train" else ds.field("season") == year
    else:
        raise ValueError("unknown semantic input lane")
    if "season_type" in names:
        predicate &= ds.field("season_type") == "REG"
    elif "game_type" in names:
        predicate &= ds.field("game_type") == "REG"
    frame = dataset.to_table(columns=columns, filter=predicate).to_pandas()
    if frame.empty or frame[cdf.KEYS].isna().any(axis=None) or frame.duplicated(cdf.KEYS).any():
        raise ValueError("missing, empty or duplicate partition identities")
    if lane == "query":
        if set(LABELS) & set(frame) or "participation_state" in columns:
            raise AssertionError("query read projected evaluation labels")
        frame["participation_state"] = "unknown"
    if not frame.season.between(2019, 2024).all():
        raise ValueError("protected season decoded")
    return frame, {"lane": lane, "year": year, "projected_columns": columns,
        "predicate": str(predicate), "rows": len(frame), "frame_sha256": operational_models.frame_hash(frame)}


def fold(path, year):
    query, query_audit = read_partition(path, year, "query")
    cdf.assert_clock_contract(query)
    train, training_audit = read_partition(path, year, "train")
    cutoff = pd.to_datetime(query.cutoff_utc, utc=True).min()
    keep = ((pd.to_datetime(train.kickoff_utc, utc=True) < cutoff)
        & (pd.to_datetime(train.outcome_available_utc, utc=True, errors="coerce") < cutoff))
    train = train.loc[keep].sort_values(["kickoff_utc", "game_id", "player_id"], kind="stable").copy()
    cdf.assert_clock_contract(train)
    training_audit.update(eligible_rows=len(train), eligible_frame_sha256=operational_models.frame_hash(train),
        excluded_chronology_rows=int((~keep).sum()), fit_before_utc=cutoff.isoformat(),
        disclosure="Earlier exposed evaluation years may serve only as later-fold training; scoring-role label access is separate")
    return train, query, {"query": query_audit, "training": training_audit}


@contextmanager
def cpu_deadline(seconds):
    """Interrupt at the process CPU ceiling, including estimator threads."""
    def exhausted(signum, frame):
        raise BudgetExhausted("per-estimator process CPU deadline exceeded")
    previous = signal.signal(signal.SIGPROF, exhausted)
    prior_timer = signal.setitimer(signal.ITIMER_PROF, max(.001, seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_PROF, *prior_timer)
        signal.signal(signal.SIGPROF, previous)


@contextmanager
def estimator_cpu_guard(session, attempt):
    """Quota-owned live control for the independent outer native-call monitor.

    The outer supervisor kills the whole group before the declared wall/CPU
    caps if a native fit delays Python's signal handlers. This mutable control
    is intentionally excluded from immutable forecast bindings; old CAS bodies
    remain retained and counted by the unchanged storage implementation.
    """
    path = session.output / "estimator-cpu-guard.json"
    proc = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    process_cpu = (int(proc[11]) + int(proc[12])) / os.sysconf("SC_CLK_TCK")
    marker = {"active": True, "pid": os.getpid(), "process_start_ticks": int(proc[19]),
        "process_cpu_start": process_cpu, "cpu_clock": "proc_utime_plus_stime_over_CLK_TCK",
        "monotonic_start": time.monotonic(), "attempt": attempt,
        "max_wall_seconds": session.budget.limits["per_estimator_wall_seconds"],
        "max_CPU_seconds": session.budget.limits["per_estimator_CPU_seconds"]}
    def publish(active):
        with session.storage.capture_writes(roots=[path]):
            session.storage.atomic_json(path, {**marker, "active": active, "generated_at": now()}, replace=True)
    publish(True)
    try:
        yield
    finally:
        publish(False)


@contextmanager
def fit_instrumentation(session, slot):
    """Observe existing estimator calls; Role A/B consume through before_fit."""
    budget = session.budget
    role_method = slot["method"] in ("count_A", "role_B")
    pending = []
    def consume(detail):
        budget.check(fit=True)
        number = budget.fits
        session.write(f"consumption/estimator-{number:03d}.json", {"generated_at": now(), **slot,
            "state": "ESTIMATOR_ATTEMPT_CONSUMED", "estimator_attempt": number, "forest_convention": "one32treeforest=oneattempt", "detail": detail})
        return number
    def before_fit(detail):
        if pending:
            raise RuntimeError("unconsumed role estimator callback")
        pending.append(consume(detail))
    def instrument(original):
        def wrapped(estimator, *args, **kwargs):
            if role_method:
                if not pending:
                    raise RuntimeError("role estimator bypassed before_fit callback")
                number = pending.pop()
            else:
                number = consume({"class": type(estimator).__name__})
            cpu_start, wall_start = time.process_time(), time.monotonic()
            try:
                with estimator_cpu_guard(session, number), _deadline(budget.limits["per_estimator_wall_seconds"]), cpu_deadline(budget.limits["per_estimator_CPU_seconds"]):
                    value = original(estimator, *args, **kwargs)
                if time.process_time() - cpu_start > budget.limits["per_estimator_CPU_seconds"]:
                    raise BudgetExhausted("per-estimator CPU ceiling exceeded")
                budget.check()
                session.write(f"estimator-results/{number:03d}.json", {"state": "RETURNED", "generated_at": now(),
                    "wall_seconds": time.monotonic()-wall_start, "CPU_seconds": time.process_time()-cpu_start})
                return value
            except BaseException as error:
                session.failure(f"estimator-results/{number:03d}.json", error)
                raise
        return wrapped
    with ExitStack() as stack:
        for cls in (cdf.ExtraTreesRegressor, median.HistGradientBoostingRegressor, median.HistGradientBoostingClassifier):
            stack.enter_context(patch.object(cls, "fit", instrument(cls.fit)))
        yield before_fit
        if pending:
            raise RuntimeError("role callback consumed without an estimator call")


@contextmanager
def no_fits():
    def forbidden(*args, **kwargs):
        raise AssertionError("no fitting allowed in reference/scoring/report phase")
    with ExitStack() as stack:
        for cls in (cdf.ExtraTreesRegressor, median.HistGradientBoostingRegressor, median.HistGradientBoostingClassifier,
                    models.LogisticRegression, models.Ridge, models.PoissonRegressor):
            stack.enter_context(patch.object(cls, "fit", forbidden))
        yield


def normalized(rows, category, method):
    result = rows.copy()
    if method in ("leaf_cdf", "role_prior"):
        result["point"] = result["mean"] if category["support"] == "bernoulli" else result["median"]
    result["method"], result["year"] = method, result.season
    result["probability"] = result.point if category["support"] == "bernoulli" else np.nan
    for name in ("mean", "median", *LAW_FIELDS):
        if name not in result:
            result[name] = np.nan
    return result


def reference_rows(session, train, query, category, method, relative, source_manifest):
    session.budget.check(reference=True, rows=len(query))
    session.write(relative + "/reference-consumed.json", {"generated_at": now(), "call": session.budget.references})
    binding = operational_models.model_binding(session.policy, source_manifest, train, query,
        digest({"registration_sha256": session.config_sha256, "year": int(query.season.iloc[0]),
                "query_sha256": operational_models.frame_hash(query), "method": method, "target": category["target"]}))
    artifact = session.output / relative / "reference.json"
    with no_fits():
        prediction = operational_models.fit_operational_reference(train, query, category["target"], method,
            artifact_path=artifact, binding=binding, storage=session.storage)
    session.bindings[str(artifact.relative_to(session.output))] = sha(artifact)
    result = query[[c for c in cdf.KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc", "season_type"] if c in query]].copy()
    result["target"], result["point"], result["fallback"] = category["target"], prediction["mean"].to_numpy(), prediction.fallback.to_numpy()
    result["primary_role"] = result.position.isin(category["primary_roles"])
    history = cdf.numeric(query, "f_player_games_prior")
    result["history_state"] = np.where(~np.isfinite(history) | (history <= 0), "cold_or_unknown", "warm")
    result["conditional_on"], result["distribution"] = "played", "bernoulli" if category["support"] == "bernoulli" else "none_point_control"
    result["actual"], result["participation_state"], result["outcome_state"] = np.nan, "unread", "unread"
    session.write(relative + "/training-audit.json", prediction.attrs)
    return normalized(result, category, method)


def _verify_bindings(session, freeze):
    if freeze["registration_sha256"] != session.config_sha256:
        raise ValueError("frozen benchmark config differs")
    for relative, expected in freeze["bindings"].items():
        path = session.output / relative
        if path.resolve() != path.absolute() or session.output not in path.parents:
            raise ValueError("unsafe frozen artifact path")
        session.storage.validate_reference(path, expected_sha256=expected)


def run_benchmark(config, *, config_sha256):
    """RUN: freeze every planned result before any scoring-role label read."""
    from threadpoolctl import threadpool_limits
    session = Session(config, config_sha256, phase="run")
    if (session.output / "RUN_CONSUMED.json").exists():
        raise RuntimeError("benchmark run already consumed; no retry or new fit")
    slots = planned_slots(session.categories)
    session.write("RUN_CONSUMED.json", {"generated_at": now(), "registration_sha256": config_sha256, "state": "CONSUMED"})
    session.write("planned-slots.json", slots)
    fatal = None
    try:
        manifest = operational_sources._verify(session.source_manifest.parent, storage=session.storage)
        with threadpool_limits(limits=2):
            for year in YEARS:
                session.budget.check()
                train, query, audit = fold(session.source, year)
                query_path = session.frame(f"private/queries/{year}.parquet", query)
                session.write(f"partitions/{year}.json", audit)
                completed = {}
                for slot in [s for s in slots if s["year"] == year]:
                    if slot["kind"] == "blocked":
                        continue
                    target, method = slot["target"], slot["method"]
                    category, relative = _category(session.categories, target), f"private/cells/{year}/{target}/{method}"
                    try:
                        session.budget.check()
                        session.write(relative + "/PACKAGE_CONSUMED.json", {"generated_at": now(), **slot, "state": "PACKAGE_CONSUMED"})
                        if slot["kind"] == "alias":
                            parent = completed.get((target, slot["alias_method"]))
                            if parent is None:
                                raise ValueError("current-source alias dependency did not freeze")
                            rows = pd.read_parquet(session.output / parent["forecast"])
                            rows["method"] = method
                            session.budget.alias_rows += len(rows)
                            session.write(relative + "/alias.json", {"alias_of": parent["forecast"],
                                "alias_forecast_sha256": session.bindings[parent["forecast"]],
                                "source_packet_sha256": config_sha256, "additional_fits": 0})
                            slot["alias_of"] = parent["forecast"]
                        elif slot["kind"] == "reference":
                            rows = reference_rows(session, train, query, category, method, relative, manifest)
                        else:
                            with fit_instrumentation(session, slot) as before_fit:
                                model = (cdf.LeafCDFModel.fit(train, category, "base") if method == "leaf_cdf" else
                                    median.MedianBoostingModel.fit(train, category, "base") if method == "median_hgb" else
                                    role.RoleCountBoostingModel.fit(train, category, "A" if method == "count_A" else "B", before_fit=before_fit))
                            session.model(relative + "/model.joblib", model)
                            session.write(relative + "/training-audit.json", model.audit)
                            session.budget.check(rows=len(query))
                            raw = cdf.prediction_rows(model, query, score=False) if method == "leaf_cdf" else (
                                median.prediction_rows(model, query) if method == "median_hgb" else role.prediction_rows(model, query))
                            rows = normalized(raw, category, method)
                            slot["model"] = relative + "/model.joblib"
                            if method == "leaf_cdf":
                                session.budget.check(rows=len(query))
                                prior = normalized(cdf.prediction_rows(model, query, prior_only=True, score=False), category, "role_prior")
                                session.frame(relative + "/role-prior-frozen.parquet", prior)
                                slot["prior_forecast"] = relative + "/role-prior-frozen.parquet"
                            del model
                        if not rows[cdf.KEYS].reset_index(drop=True).equals(query[cdf.KEYS].reset_index(drop=True)):
                            raise ValueError("forecast changed offered identities/order")
                        session.frame(relative + "/forecast-frozen.parquet", rows)
                        slot.update(state="PREDICTION_FROZEN", forecast=relative + "/forecast-frozen.parquet",
                            query=str(query_path.relative_to(session.output)), rows=len(rows))
                        completed[(target, method)] = slot
                        session.write(relative + "/FROZEN.json", {"generated_at": now(), **slot})
                    except (BudgetExhausted, StorageQuotaError, StorageIntegrityError):
                        slot["state"] = "FAILED_RESOURCE"
                        raise
                    except Exception as error:
                        slot.update(state="FAILED", reason=type(error).__name__)
                        session.failure(relative + "/FAILURE.json", error)
                # Later-fold training may now read this exposed year's labels.
                session.write(f"year-freezes/{year}.json", {"generated_at": now(), "state": "YEAR_FORECASTS_FROZEN",
                    "slots": [s for s in slots if s["year"] == year]})
    except BaseException as error:
        fatal = error
        session.failure("RUN_FAILURE.json", error)
    finally:
        session.write("attempts.json", slots)
    freeze = {"state": "GLOBAL_FORECASTS_FROZEN", "generated_at": now(), "registration_sha256": config_sha256,
        "slots": slots, "usage": session.budget.usage(), "bindings": dict(session.bindings),
        "fatal": type(fatal).__name__ if fatal else None,
        "labels": "No scoring-role labels decoded; earlier years used only in later-fold training after earlier-year output freeze",
        "evidence": "EXPOSED_SOURCE_MATCHED_DEVELOPMENT; no accuracy claim before scoring"}
    session.write("forecast-freeze.json", freeze, freeze=False)
    return freeze


def _outcomes(query, labels, category):
    if not query[cdf.KEYS].reset_index(drop=True).equals(labels[cdf.KEYS].reset_index(drop=True)):
        keys = query[cdf.KEYS].merge(labels[cdf.KEYS], on=cdf.KEYS, how="outer", indicator=True, validate="one_to_one")
        if not keys._merge.eq("both").all():
            raise ValueError("scoring labels change offered population")
        labels = query[cdf.KEYS].merge(labels, on=cdf.KEYS, how="left", sort=False, validate="one_to_one")
    for field in ("position", "team", "opponent", "cutoff_utc", "kickoff_utc"):
        if not query[field].reset_index(drop=True).equals(labels[field].reset_index(drop=True)):
            raise ValueError("scoring source context/cutoff mismatch")
    result = query.copy()
    for name in LABELS + QUALIFICATION + ("participation_state",):
        if name in labels:
            result[name] = labels[name].to_numpy()
    cdf.assert_composite_contract(result, category)
    return result


def report_benchmark(config, *, config_sha256, resume_frozen=False, spent_usage=None):
    """REPORT: one label/scoring pass, then explicit frozen-row-only continuation."""
    import joblib
    from .source_matched_reporting import build_target_report, reporting_header
    session = Session(config, config_sha256, phase="report")
    session.storage.validate_reference(session.output / "forecast-freeze.json")
    freeze = json.loads((session.output / "forecast-freeze.json").read_text())
    _verify_bindings(session, freeze)
    scoring_consumed = session.output / "SCORE_CONSUMED.json"
    score_freeze_path = session.output / "scored-freeze.json"
    previous = freeze["usage"]
    attempts = sorted((session.output / "report-attempts").glob("*-finished.json"))
    consumed_attempts = list((session.output / "report-attempts").glob("*-consumed.json"))
    if attempts:
        previous = json.loads(attempts[-1].read_text())["usage"]
    if len(consumed_attempts) > len(attempts) and spent_usage is None:
        raise RuntimeError("incomplete report attempt requires separately frozen authoritative outer spent_usage")
    if spent_usage is not None:
        for name in ("wall_seconds", "CPU_seconds"):
            if spent_usage.get(name, -1) < previous[name]:
                raise ValueError("continuation cannot decrease cumulative resource use")
        if set(spent_usage) - {"wall_seconds", "CPU_seconds", "max_RSS_bytes"}:
            raise ValueError("outer usage may supplement clocks/RSS only; frozen work counters cannot change")
        if spent_usage.get("max_RSS_bytes", previous.get("max_RSS_bytes", 0)) < previous.get("max_RSS_bytes", 0):
            raise ValueError("continuation cannot decrease cumulative RSS")
        previous = {**previous, **spent_usage}
    initial_start, initial_cpu = session.budget.start, session.budget.cpu_start
    session.budget = Budget(session.spec["budgets"], prior=previous, phase="report")
    session.budget.start, session.budget.cpu_start = initial_start, initial_cpu
    number = len(consumed_attempts) + 1
    if (session.output / "report.json").exists():
        raise RuntimeError("benchmark report already completed")
    if scoring_consumed.exists() and (not resume_frozen or not score_freeze_path.exists()):
        raise RuntimeError("score already consumed; only explicit fully frozen scored-row continuation is permitted")
    session.write(f"report-attempts/{number:03d}-consumed.json", {"generated_at": now(), "registration_sha256": config_sha256,
        "resume_frozen": resume_frozen, "prior_usage": previous}, freeze=False)
    try:
        with no_fits():
            if not scoring_consumed.exists():
                session.budget.check()
                session.write("SCORE_CONSUMED.json", {"generated_at": now(), "forecast_freeze_sha256": sha(session.output / "forecast-freeze.json"),
                    "score_phases": 1}, freeze=False)
                scored_slots = [dict(s) for s in freeze["slots"]]
                scored_files = []
                for year in YEARS:
                    successful = [s for s in scored_slots if s["year"] == year and s["state"] == "PREDICTION_FROZEN"]
                    if not successful:
                        continue
                    session.budget.check()
                    labels, label_audit = read_partition(session.source, year, "labels", allow_labels=True)
                    session.write(f"scoring/label-read-{year}.json", label_audit)
                    for slot in successful:
                        category = _category(session.categories, slot["target"])
                        relative = f"private/scored/{year}/{slot['target']}/{slot['method']}"
                        try:
                            session.budget.check()
                            query = pd.read_parquet(session.output / slot["query"])
                            offered = _outcomes(query, labels, category)
                            frozen = pd.read_parquet(session.output / slot["forecast"])
                            if slot["method"] == "leaf_cdf":
                                model = joblib.load(io.BytesIO((session.output / slot["model"]).read_bytes()))
                                session.budget.check(rows=len(query))
                                scored = cdf.score_frozen_rows(model, offered, frozen)
                                prior = pd.read_parquet(session.output / slot["prior_forecast"])
                                session.budget.check(rows=len(query))
                                scored_prior = cdf.score_frozen_rows(model, offered, prior, prior_only=True)
                                session.frame(relative + "/role-prior.parquet", normalized(scored_prior, category, "role_prior"))
                                scored_files.append(relative + "/role-prior.parquet")
                                del model
                            else:
                                scored = median.score_frozen_rows(offered, frozen, category)
                            session.frame(relative + "/rows.parquet", normalized(scored, category, slot["method"]))
                            scored_files.append(relative + "/rows.parquet")
                            slot["state"] = "COMPLETED"
                        except (BudgetExhausted, StorageQuotaError, StorageIntegrityError):
                            slot["state"] = "SCORING_FAILED_RESOURCE"
                            raise
                        except Exception as error:
                            slot.update(state="SCORING_FAILED", reason=type(error).__name__)
                            session.failure(relative + "/FAILURE.json", error)
                scored_freeze = {"state": "SCORED_ROWS_FROZEN",
                    "forecast_freeze_sha256": sha(session.output / "forecast-freeze.json"), "generated_at": now(), "registration_sha256": config_sha256,
                    "slots": scored_slots, "scored_files": scored_files, "bindings": dict(session.bindings), "usage": session.budget.usage()}
                session.write("scored-freeze.json", scored_freeze, freeze=False)
            else:
                session.storage.validate_reference(scoring_consumed)
                session.storage.validate_reference(score_freeze_path)
                if json.loads(scoring_consumed.read_text())["forecast_freeze_sha256"] != sha(session.output / "forecast-freeze.json"):
                    raise ValueError("score consumption references different global freeze")
                scored_freeze = json.loads(score_freeze_path.read_text())
                if scored_freeze["forecast_freeze_sha256"] != sha(session.output / "forecast-freeze.json"):
                    raise ValueError("scored rows reference different global freeze")
                _verify_bindings(session, scored_freeze)
            session.budget.check()
            categories = {target: _category(session.categories, target) for target in models.TARGETS}
            for target in categories:
                categories[target]["benchmark_slots"] = [{k: s[k] for k in ("year", "method", "state", "reason") if k in s}
                    for s in scored_freeze["slots"] if s["target"] == target]
            report = reporting_header(replicates=500, seed=1703)
            paired_files = []
            for target in models.TARGETS:
                session.budget.check()
                selected = [relative for relative in scored_freeze["scored_files"] if Path(relative).parts[3] == target]
                frames = [pd.read_parquet(session.output / relative, columns=list(REPORT_FIELDS)) for relative in selected]
                if frames:
                    rows = pd.concat(frames, ignore_index=True)
                else:
                    text = {"game_id", "player_id", "target", "method", "participation_state", "outcome_state",
                        "fallback", "history_state", "position", "team", "opponent", "kickoff_utc", "cutoff_utc"}
                    rows = pd.DataFrame({name: pd.Series(dtype=bool if name == "primary_role" else object if name in text else float)
                        for name in REPORT_FIELDS})
                item, pairs = build_target_report(rows, categories, target=target, replicates=500, seed=1703)
                session.budget.check()
                pair_path = f"private/paired-losses/{target}.parquet"
                session.frame(pair_path, pairs, freeze=False)
                paired_files.append({"target": target, "path": pair_path, "sha256": sha(session.output / pair_path), "rows": len(pairs)})
                report["targets"][target] = item
                del frames, rows, pairs
            session.write("private/paired-losses-manifest.json", {"files": paired_files}, freeze=False)
            session.write("report.json", {"generated_at": now(), "registration_sha256": config_sha256,
                "forecast_freeze_sha256": sha(session.output / "forecast-freeze.json"),
                "scored_freeze_sha256": sha(score_freeze_path), "usage": session.budget.usage(), "report": report,
                "private_pairs_manifest_sha256": sha(session.output / "private/paired-losses-manifest.json"),
                "promotion": "NONE", "evidence": "EXPOSED_SOURCE_MATCHED_DEVELOPMENT; no independent confirmation or website-relative claim"}, freeze=False)
            return report
    except BaseException as error:
        session.failure(f"report-attempts/{number:03d}-failure.json", error)
        raise
    finally:
        session.write(f"report-attempts/{number:03d}-finished.json", {"generated_at": now(), "usage": session.budget.usage()}, freeze=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("run", "report"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--resume-frozen", action="store_true")
    parser.add_argument("--spent-usage", type=Path, help="Separately frozen authoritative outer cumulative usage JSON")
    args = parser.parse_args(argv)
    if args.phase == "run":
        if args.resume_frozen or args.spent_usage:
            parser.error("continuation flags are report-only")
        result = run_benchmark(args.config, config_sha256=args.config_sha256)
    else:
        result = report_benchmark(args.config, config_sha256=args.config_sha256, resume_frozen=args.resume_frozen,
            spent_usage=json.loads(args.spent_usage.read_text()) if args.spent_usage else None)
    print(json.dumps(clean(result), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
