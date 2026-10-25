"""One bounded backend for the registered exposed opportunity screen.

Uses the existing source projection, arithmetic, evaluator and owned storage.
No acquisition, model fitting/loading, provider reconstruction, joint allocator
or prospective issuance. Importing this module performs no data reads.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
import hashlib
import json
import math
from pathlib import Path
import resource
import time
from unittest.mock import patch

import numpy as np
import pandas as pd

from . import dynamic_opportunity_core as core
from . import dynamic_opportunity_history as history
from . import dynamic_opportunity_source as source
from . import dynamic_opportunity_study as study
from . import direct_booster_screen as evaluator
from . import source_matched_benchmark as shared
from .operational_storage import OperationalStorage, StorageIntegrityError, StorageQuotaError
from .owned_reference_batch import validate_owned_references
from .reference_runtime import _deadline
from .source_matched_reporting import CONTEXT as PAIR_CONTEXT, _bootstrap
from .state import digest, utc
from . import dynamic_opportunity_recovery as recovery

VERSION = study.VERSION
LIMIT = 48 * 1024 * 1024
PERSISTED_CONTEXT = tuple(dict.fromkeys([*shared.cdf.KEYS, *PAIR_CONTEXT]))
FORECAST_COLUMNS = ("row_ordinal", "point", "fallback", "history_state", "baseline_fallback")
EVIDENCE = "EXPOSED_HISTORICAL_REPLAY; current-vintage strict kickoff+7days reconstruction; no original issuance"


def _json(value):
    """Strict compact private manifests; no NaN-as-zero substitution."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def restore_request_view(manifest, records, tables):
    """Pure inverse of the new flat persisted request contract.

    The reader must first authenticate every named file/hash through the owned
    storage contract. This function receives already-authenticated DataFrames;
    it does not acquire sources, reconstruct NFL zeros or run the filters.
    """
    from .dynamic_opportunity_source_helpers import restore_factored_requests
    if (len(records) != manifest["original_rows"] or set(tables) != set(manifest["table_bindings"])
            or not records.columns.is_unique):
        raise ValueError("factored request population/table inventory changed")
    decoded = {}
    for name, table in tables.items():
        if (list(table.columns) != ["payload_json"]
                or len(table) != manifest["table_bindings"][name]["rows"]):
            raise ValueError("factored request table shape changed")
        decoded[name] = [core.decode_json(value) for value in table.payload_json]
    flat = records.to_dict("records")
    for row in flat:
        for key in ("history_indices", "slot_audit_indices"):
            value = row[key]
            row[key] = value.tolist() if isinstance(value, np.ndarray) else value
    packet = {k: v for k, v in manifest.items() if k not in
              ("records_binding", "table_bindings", "serializer", "consumer")}
    packet.update(records=flat, tables=decoded)
    return restore_factored_requests(packet)


def development_nomination(report):
    """The new CDF+matched-static development rule, never a release gate."""
    reasons = []
    pairs = report["pairs"] + report["matched_static_pairs"]
    for comparator in ("leaf_cdf", "matched_static"):
        selected = [p for p in pairs if p["candidate"] == "selected_dynamic"
                    and p["comparator"] == comparator and p["population"] == "primary_roles"]
        pooled = next((p for p in selected if p["period"] == "pooled_2022_2024"), None)
        if pooled is None or pooled.get("missing_required_years"):
            reasons.append(comparator + ":missing_required_years"); continue
        if not _finite(pooled.get("improvement_pct")) or pooled["improvement_pct"] < 2:
            reasons.append(comparator + ":less_than_2pct_primary_gain")
        if not pooled.get("forecast_finite_masks_equal", False):
            reasons.append(comparator + ":forecast_coverage_changed")
        for name in ("bias_prediction_minus_actual", "absolute_error_p95"):
            a = pooled["candidate_point_metrics"][name]; b = pooled["control_literal_point_metrics"][name]
            if not _finite(a) or not _finite(b) or abs(a) > 1.02 * abs(b):
                reasons.append(comparator + ":secondary_regression:" + name)
        annual = [p for p in selected if p["period"] in shared.YEARS]
        if {p["period"] for p in annual} != set(shared.YEARS):
            reasons.append(comparator + ":missing_annual_cell")
        for p in annual:
            a, b = p["candidate_loss"], p["control_loss"]
            if not _finite(a) or not _finite(b) or a > 1.05 * b:
                reasons.append(comparator + ":annual_regression:" + str(p["period"]))
    return dict(method="selected_dynamic", comparators=["leaf_cdf", "matched_static"],
        decision="DEVELOPMENT_LEAD_REQUIRES_LATER_CONFIRMATION" if not reasons else "NOT_NOMINATED",
        reasons=reasons, scientific_qualification=False, release_ready=False)


def make_storage(spec):
    """Same accepted CAS admission, tightened to this48MiB namespace."""
    from direct_booster_frozen_report import cap_output
    store = OperationalStorage(spec["cache"], json.loads(shared._spec(spec["source_policy"]).read_text()))
    output = store.register_root(spec["output"]); cap_output(store, output)
    original, retained = store.write_bytes, store.report_retention
    prior_charge = recovery.caps(spec)["prior_retained_bytes"]
    def bounded(path, body, *, replace=False):
        body_digest = hashlib.sha256(body).hexdigest()
        incoming = 0 if (store.blob_root / body_digest).exists() else len(body)
        try:
            recovery.campaign_charge(prior_charge, retained()["charged_bytes"], incoming)
        except ValueError as error:
            raise StorageQuotaError(str(error)) from error
        return original(path, body, replace=replace)
    store.write_bytes = bounded
    def retention():
        value = dict(retained()); value["borrowed_helper_limit_bytes"] = value["limit_bytes"]
        value["limit_bytes"] = LIMIT
        value["newly_charged_bytes"] = value["charged_bytes"]
        value["previous_campaign_retained_bytes"] = prior_charge
        value["charged_bytes"] = recovery.campaign_charge(prior_charge, value["charged_bytes"])
        value["scope"] += "; unchanged earlier failed campaign charge remains reserved"
        return value
    store.report_retention = retention
    return store, output


@contextmanager
def no_external_models():
    """The only new predictions are the separately frozen pure math core."""
    def deny(*args, **kwargs):
        raise AssertionError("dynamic screen forbids fitted models, original pipelines and model deserialization")
    with shared.no_fits(), ExitStack() as stack:
        import pickle
        import joblib
        blocked = ((pickle, "load"), (pickle, "loads"), (joblib, "load"),
                   (evaluator, "run_screen"), (evaluator, "report_screen"),
                   (shared, "fold"), (shared, "read_partition"), (shared, "_dataset"),
                   (shared.operational_sources, "_verify"), (shared.models, "fit_predict"),
                   (shared.operational_models, "fit_operational_reference"),
                   (shared.operational_models, "predict_operational_artifact"),
                   (shared.cdf.LeafCDFModel, "fit"), (shared.cdf.LeafCDFModel, "predict_batches"),
                   (evaluator.direct.DirectBoosterModel, "fit"),
                   (evaluator.direct.DirectBoosterModel, "predict"))
        for owner, name in blocked:
            stack.enter_context(patch.object(owner, name, deny))
        yield


def exact_context(query, donor, *, target, year, method):
    if (not query.columns.is_unique or not donor.columns.is_unique or len(query) != len(donor)
            or any(c not in query or c not in donor for c in PERSISTED_CONTEXT)):
        raise ValueError("nine persisted context fields and original complete population required")
    pd.testing.assert_frame_equal(query[list(PERSISTED_CONTEXT)].reset_index(drop=True),
        donor[list(PERSISTED_CONTEXT)].reset_index(drop=True), check_dtype=True, check_exact=True)
    presence = ("season_type" in query, "season_type" in donor)
    if presence[0] != presence[1]:
        raise ValueError("optional persisted season_type differs")
    if presence[0]:
        pd.testing.assert_series_equal(query.season_type.reset_index(drop=True),
            donor.season_type.reset_index(drop=True), check_dtype=True, check_exact=True)
    if not donor.target.eq(target).all() or not donor.method.eq(method).all() or not donor.season.eq(year).all():
        raise ValueError("saved control target/year/method mismatch")
    return dict(context=list(PERSISTED_CONTEXT), exact_dtype_order=True,
                season_type="PRESENT_BOTH_EXACT" if presence[0] else "ABSENT_BOTH_FROZEN_LEGACY_PROJECTIONS")


def cdf_baseline_point(rows, support):
    """Use the retained product's mean for counts and lower median for yards."""
    if support not in ("count", "signed_integer"):
        raise ValueError("only this study's genuine saved CDF products are allowed")
    return shared.cdf.numeric(rows, "mean" if support == "count" else "median")


def score_factored_view(query, saved, labels, category, method):
    """Single consumer for authenticated context+forecast+label row views."""
    if (len(query) != len(labels) or len(query) != len(saved)
            or not np.array_equal(saved.row_ordinal.to_numpy(), np.arange(len(query)))):
        raise ValueError("factored scoring population/ordinal changed")
    target = category["target"]
    rows = query[[c for c in PERSISTED_CONTEXT if c in query]].copy()
    for field in ("point", "fallback", "history_state", "baseline_fallback"):
        rows[field] = saved[field].to_numpy()
    rows["target"], rows["method"], rows["year"] = target, method, rows.season
    rows["primary_role"] = rows.position.isin(category["primary_roles"])
    rows["actual"], rows["participation_state"], rows["outcome_state"] = np.nan, "unread", "unread"
    rows["point_semantics"] = "conditional_mean_squared_error_objective" if category["support"] == "count" else "prespecified_MAE_point_heuristic"
    rows["conditional_on"], rows["distribution"] = "played", "none_point_only"
    for field in ("mean", "median", "probability", *shared.LAW_FIELDS):
        rows[field] = np.nan
    offered = query.copy(); offered[target] = labels.actual.to_numpy()
    offered["participation_state"] = labels.participation_state.to_numpy()
    if target != "rec_tgt":
        offered["qualified_outcome_state"] = labels.outcome_state.to_numpy()
    for name in labels:
        if name.startswith("qualified_") or name in shared.QUALIFICATION:
            offered[name] = labels[name].to_numpy()
    return shared.normalized(evaluator.direct.score_frozen_rows(offered, rows, category), category, method)


class Backend:
    """The actual outer caller must authenticate this exact spec before entry.

    Required spec: sealed source_plan, cache/output, source_policy, categories,
    category_contract binding, control_freeze binding, control_metadata[year]
    [target][method] containing binding/forecast_columns/label_columns, exact
    owned_inputs and cumulative package supervisor marker protocol. All paths
    and imported software are additionally bound by the outer execution freeze.
    """
    version = VERSION
    write = shared.Session.write
    frame = shared.Session.frame
    failure = shared.Session.failure

    def __init__(self, spec, *, registration_sha256, final_static):
        if (spec.get("state") != "FROZEN_ROOT_REVIEWER_SEALED" or not spec.get("seal")
                or spec.get("registration_id") != VERSION):
            raise ValueError("exact sealed dynamic backend required")
        self.state = spec["state"]; self.spec = spec; self.registration_sha256 = registration_sha256
        self.final_static = final_static; self.start = time.monotonic(); self.cpu_start = time.process_time()
        self.execution_caps = recovery.caps(spec)
        self.storage, self.output = make_storage(spec)
        self.bindings = {}; self.queries = {}; self.requests = {}; self.efficiencies = {}
        self.priors = {}; self.role_means = {}; self.forecasts = {}; self.packages = []
        self.year_freezes = {}; self.phase_usage = defaultdict(lambda: [0., 0.])
        self.campaign_prior_reservations = self.execution_caps["prior_reserved"]
        if spec.get("recovery_envelope"):
            phase = spec["recovery_envelope"]["source_phase_consumption"]
            self.phase_usage["source_prior"] = [phase["wall_seconds"], phase["CPU_seconds"]]
        self.selected = None; self.global_frozen = False; self.labels = {}; self.source = None
        self.control_freeze = None; self.authenticated_controls = {}; self.owned = {}
        self._package_number = 0; self._derived_points = {}; self.context_receipts = []

    def guard(self):
        if (time.monotonic() - self.start >= self.execution_caps["wall_seconds"] - 10
                or time.process_time() - self.cpu_start >= self.execution_caps["CPU_seconds"] - 10
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 >= 1073741824):
            raise RuntimeError("finite dynamic study cumulative resource budget consumed")
    check = guard

    @contextmanager
    def cumulative_phase_limit(self, name, wall, cpu):
        if study.PHASE_LIMITS.get(name) != wall or wall != cpu:
            raise ValueError("fixed phase ceiling required")
        used = self.phase_usage[name]
        remaining_wall, remaining_cpu = wall - used[0], cpu - used[1]
        if min(remaining_wall, remaining_cpu) <= 0:
            raise RuntimeError("cumulative phase allowance consumed: " + name)
        started, cpu_started = time.monotonic(), time.process_time()
        try:
            with _deadline(remaining_wall), shared.cpu_deadline(remaining_cpu):
                yield
        finally:
            used[0] += time.monotonic() - started; used[1] += time.process_time() - cpu_started
            self.guard()
            if used[0] >= wall or used[1] >= cpu:
                raise RuntimeError("cumulative phase ceiling exceeded: " + name)

    @contextmanager
    def package_limit(self, wall, cpu):
        if (wall, cpu) != (20, 20):
            raise ValueError("fixed20s package guard required")
        self._package_number += 1
        if self._package_number > 54:
            raise RuntimeError("all54 package attempts consumed")
        # Existing reviewed marker/native timer protocol; supervisor must bind
        # max54 and these exact limits, including a process stuck in native code.
        class Budget:
            limits = dict(per_estimator_wall_seconds=20, per_estimator_CPU_seconds=20)
        self.budget = Budget()
        started, cpu_started = time.monotonic(), time.process_time()
        with shared.estimator_cpu_guard(self, self._package_number), _deadline(wall), shared.cpu_deadline(cpu):
            yield
        self.guard()
        if time.monotonic() - started >= wall or time.process_time() - cpu_started >= cpu:
            raise RuntimeError("per-package resource ceiling exceeded")

    def verify_owned_entry(self):
        self.final_static()
        self.owned = {r["path"]: r["sha256"] for r in self.spec["owned_inputs"]}
        if len(self.owned) != len(self.spec["owned_inputs"]):
            raise ValueError("duplicate owned binding")
        self.authenticated_controls, receipt = validate_owned_references(self.storage, self.owned)
        self.write("owned-input-entry.json", receipt)
        self.control_freeze = json.loads(shared._spec(self.spec["control_freeze"]).read_text())
        if self.control_freeze["state"] != "ALL_SCORED_ROWS_FROZEN":
            # Older accepted score-freeze uses this exact second state.
            if self.control_freeze["state"] != self.spec["control_freeze_state"]:
                raise ValueError("original source-matched control freeze changed")
        for year in shared.YEARS:
            for target in ("rush_att", "rec", "rec_yd"):
                for method in evaluator.CONTROLS:
                    item = self.spec["control_metadata"][str(year)][target][method]["binding"]
                    name = f"private/scored/{year}/{target}/{method}/rows.parquet"
                    if (name not in self.control_freeze["scored_files"]
                            or self.control_freeze["bindings"].get(name) != item["sha256"]
                            or self.owned.get(item["path"]) != item["sha256"]):
                        raise ValueError("all45 exact controls must be authenticated")
        source_plan = self.spec["source_plan"]
        def authenticate(bindings):
            if any(self.owned.get(path) != sha for path, sha in bindings.items()):
                raise ValueError("source projection escaped full owned entry")
            return {p: self.authenticated_controls[p] for p in bindings}
        self.source = source.ProjectionSource(source_plan, authenticator=authenticate)

    def verify_owned_exit(self):
        self.final_static()
        if self.source is not None:
            self.source.close()
        all_owned = {**self.owned, **{str(self.output / n): sha for n, sha in self.bindings.items()}}
        _, receipt = validate_owned_references(self.storage, all_owned)
        self.write("owned-input-exit.json", receipt)

    def consume_once(self):
        if (self.output / "DYNAMIC_CONSUMED.json").exists():
            raise RuntimeError("sole actual invocation already consumed")
        self.write("DYNAMIC_CONSUMED.json", dict(at=shared.now(), registration_sha256=self.registration_sha256,
            packages=54, forecast_row_cap=600000, retries=0, prior_vectors_cap=16,
            previous_consumption=self.spec.get("recovery_envelope", {}).get("previous_consumption"),
            remaining_execution_caps=self.execution_caps))

    def preflight(self, slots):
        self.calendar = self.source.calendar()
        for year in range(2020, 2025):
            rows = self.source.query_context(year)
            query = pd.DataFrame(rows)
            if (query.empty or not query.columns.is_unique or query.duplicated(shared.cdf.KEYS).any()
                    or not query.season.eq(year).all()):
                raise ValueError("nonempty unique original query context required")
            self.queries[year] = query
        counts = [self.query_count(s["year"]) for s in slots]
        request_rows = sum(2 * self.query_count(y) for y in range(2020, 2025))
        unique_labels = sum(2 * self.query_count(y) for y in (2020, 2021)) + sum(4 * self.query_count(y) for y in shared.YEARS)
        # Logical pair rows are retained through exact frozen scored-view refs,
        # not repeatedly copied across each of the five controls.
        loss_rows = sum(self.query_count(y) * 2 * 3 * 5 for y in shared.YEARS)
        estimate = study.retention_estimate(counts, request_rows=request_rows, loss_rows=loss_rows,
            scored_label_view=dict(contract="FACTORED_SCORED_LABEL_VIEW", context_and_forecast_bindings_required=True,
                                   unique_label_rows=unique_labels),
            paired_loss_view=dict(contract="REPLAYABLE_PAIRED_LOSS_VIEW", original_scorer_and_all_scored_bindings_required=True, views=36))
        estimate["context_rows"] = {str(y): self.query_count(y) for y in self.queries}
        estimate["source_values_read"] = False
        retention = self.storage.report_retention()
        bootstrap = max(6 * 1024 * 1024, retention["newly_charged_bytes"])
        context_reserve = 5 * 1024 * 1024  # One projected context/year; no copied source feature tables.
        if self.spec.get("recovery_envelope"):
            reuse = self.spec["recovery_envelope"]["reuse"]
            if json.loads(shared._spec(reuse["calendar"]).read_text()) != self.calendar:
                raise ValueError("reused calendar differs from exact original source projection")
            for year, query in self.queries.items():
                old = pd.read_parquet(shared._spec(reuse["contexts"][str(year)]), use_threads=False)
                pd.testing.assert_frame_equal(query, old, check_dtype=True, check_exact=True)
            context_reserve = 0  # All six bodies already retained and authenticated; aliases only.
            estimate["parts_bytes"]["previous_failed_campaign_retention"] = retention["previous_campaign_retained_bytes"]
            estimate["estimated_new_bytes"] += retention["previous_campaign_retained_bytes"]
            estimate["context_reuse"] = "EXACT_AUTHENTICATED_OWNED_ALIASES; zero newly-created context bodies"
        estimate["parts_bytes"]["execution_inventory_bootstrap_reserve"] = bootstrap
        estimate["parts_bytes"]["five_projected_contexts_reserve"] = context_reserve
        estimate["estimated_new_bytes"] += bootstrap + context_reserve
        estimate["metadata_reserve_note"] = "Original4MiB reporting/failure and6MiB inventory reserves unchanged; new context reserve0 only for exact authenticated existing aliases, otherwise5MiB"
        estimate["within_retention_estimate"] = estimate["estimated_new_bytes"] <= LIMIT
        return estimate

    def save_plan_and_estimate(self, estimate):
        self.write("preflight-estimate.json", estimate)
        self.write("plan.json", self.spec)
        if self.spec.get("recovery_envelope"):
            reuse = self.spec["recovery_envelope"]["reuse"]
            for name, binding in [("calendar.json", reuse["calendar"]),
                                  *[(f"private/context/{year}.parquet", reuse["contexts"][str(year)]) for year in self.queries]]:
                if (self.owned.get(binding["path"]) != binding["sha256"]
                        or not (self.storage.blob_root / binding["sha256"]).is_file()):
                    raise StorageIntegrityError("reuse must remain an authenticated existing CAS object")
                ref = self.storage.import_file(binding["path"], self.output / name, expected_sha256=binding["sha256"])
                self.bindings[name] = ref["sha256"]
        else:
            self.write("calendar.json", self.calendar)
            for year, query in self.queries.items():
                self.frame(f"private/context/{year}.parquet", query)

    def query_count(self, year):
        return len(self.queries[year])

    def _advance(self, cutoff):
        return self.source.advance(self.calendar, str(cutoff))

    def prepare_year(self, year, prior_kinds):
        # One source-owner index/cache implementation shared by all54 packages.
        # It retains the exact full-query ordinal before grouping by cutoff.
        from .dynamic_opportunity_source_helpers import AnnualInputs
        if self.campaign_prior_reservations + len(prior_kinds) > 16:
            raise RuntimeError("earlier failed reservations plus new prior formation exhaust original16")
        self.campaign_prior_reservations += len(prior_kinds)  # Reserve before work; failed work is not refunded.
        if not hasattr(self, "annual"):
            self.annual = AnnualInputs(self.source, self.calendar, self.spec["source_plan"],
                                       self.spec["source_plan"]["replay_policy"])
        original = self.spec["source_plan"]["queries"].get(str(year), self.spec["source_plan"]["accepted_features"])
        if year < 2022:
            context_name = f"private/context/{year}.parquet"
            original = dict(path=str(self.output / context_name), sha256=self.bindings[context_name],
                bytes=(self.output / context_name).stat().st_size, source_view=dict(parent=original,
                predicate={"season": year}, projected_columns=list(source.CONTEXT_COLUMNS),
                ordinal_contract="PERSISTED_ANNUAL_CONTEXT_ORDINAL_NOT_UNFILTERED_PARENT_ORDINAL"))
        prepared = self.annual.prepare(year, self.queries[year].to_dict("records"), original, prior_kinds)
        for task in study.TASKS:
            self.priors[year, task] = prepared["priors"][task]
            self.role_means[year, task] = prepared["simple_role_means"][task]
            self.requests[year, task] = self.annual.requests_for_year(year, task)
            if len(self.requests[year, task]) != self.query_count(year):
                raise ValueError("every original offered query requires a request/fallback")
            if year >= 2022 and task == "rec_tgt":
                for request in self.requests[year, task]:
                    request["fixed_efficiency"] = self.annual.efficiency_for_request(year, request)
            self.write(f"private/priors/{year}/{task}.json", dict(
                priors={role: prior.manifest() for role, prior in self.priors[year, task].items()},
                auxiliary_role_mean=self.role_means[year, task], training_before_utc=prepared["training_before_utc"]))
            packet = self.annual.factored_requests(year, task)
            stem = f"private/requests/{year}/{task}"
            self.frame(stem + "/records.parquet", pd.DataFrame(packet["records"]))
            table_bindings = {}
            for name, values in packet["tables"].items():
                relative = stem + "/" + name + ".parquet"
                self.frame(relative, pd.DataFrame(dict(payload_json=[_json(v) for v in values])))
                table_bindings[name] = dict(path=relative, sha256=self.bindings[relative], rows=len(values))
            self.write(stem + "/manifest.json", dict(
                **{k: v for k, v in packet.items() if k not in ("records", "tables")},
                records_binding=dict(path=stem + "/records.parquet", sha256=self.bindings[stem + "/records.parquet"]),
                table_bindings=table_bindings,
                serializer="original owned parquet/zstd; each interned table cell strict JSON",
                consumer="nfl_lab.dynamic_opportunity_backend.restore_request_view"))
        if "fixed_efficiency" in prior_kinds:
            self.efficiencies[year] = prepared["efficiency_priors"]
            self.write(f"private/priors/{year}/fixed_efficiency.json", self.efficiencies[year])
        self.write(f"source-prior-audit/{year}.json", dict(source=prepared["source_prior_audits"],
                                                       efficiency=prepared["efficiency_prior_audit"]))
        self.write(f"source-read-audit/{year}.json", self.source.read_audit)

    def _category(self, target):
        if target == "rec_tgt":
            return dict(target=target, state="READY", support="count", primary_roles=["RB", "WR", "TE"])
        return shared._category(self.spec["categories"], target)

    def _baseline(self, year, target):
        if year < 2022 or target == "rec_tgt":
            return None, np.full(self.query_count(year), np.nan)
        item = self.spec["control_metadata"][str(year)][target]["leaf_cdf"]
        columns = item["forecast_columns"]
        if set(columns) & {"actual", "participation_state", "outcome_state"}:
            raise ValueError("forecast-only CDF projection contains an outcome")
        rows = pd.read_parquet(item["binding"]["path"], columns=columns, use_threads=False)
        self.context_receipts.append(exact_context(self.queries[year], rows, target=target, year=year, method="leaf_cdf"))
        category = self._category(target)
        if not rows.primary_role.equals(rows.position.isin(category["primary_roles"])):
            raise ValueError("original CDF primary roles differ")
        return rows, cdf_baseline_point(rows, category["support"])

    def forecast_package(self, slot, selected, compute):
        year, target, method = (slot[k] for k in ("year", "target", "method"))
        category = self._category(target); task = "rush_att" if target == "rush_att" else "rec_tgt"
        baseline, points = self._baseline(year, target)
        fallback = ["missing_required_inputs_abstain" if baseline is None else "required_input_failure_saved_CDF_retained"] * len(points)
        states = []; package_failure = None
        try:
            for ordinal, req in enumerate(self.requests[year, task]):
                role = req["offer"]["position"]; states.append(req["reason"])
                if role not in core.TASK_ROLES[task]:
                    fallback[ordinal] = "outside_modeled_role_saved_reference" if baseline is not None else "outside_modeled_role_abstain"
                    continue
                if method in ("aux_recent3", "aux_pooled8"):
                    history_counts = [s["player_count"] if core.paired_count(core.Slot.from_manifest(s))[0] else None
                                      for s in req.get("history", [])]
                    point = (study.auxiliary_simple(history_counts, self.role_means[year, task][role],
                        window=3 if method == "aux_recent3" else 8) if req["state"] == "READY_CORE_REQUEST" else None)
                elif target in ("rec", "rec_yd"):
                    target_points = self._derived_points[year, method]
                    point = study.propagated_point(target_points[ordinal], req.get("fixed_efficiency"), target)
                else:
                    setting = method if slot["phase"] == "development" else selected[task]
                    result = compute(req, self.priors[year, task][role], setting=setting, static=method == "matched_static")
                    point = result.get("point") if result["state"] == "READY_POINT" else None
                    states[-1] = result.get("reason", states[-1])
                if point is not None:
                    if not _finite(point) or category["support"] == "count" and point < 0:
                        raise ValueError("arithmetic forecast support failure")
                    points[ordinal] = point; fallback[ordinal] = ""
        except (StorageQuotaError, StorageIntegrityError, TimeoutError):
            raise
        except Exception as error:
            # One failed package, no retry or favorable partial output.
            package_failure = dict(exception=type(error).__name__, message=str(error)[:300])
            baseline, points = self._baseline(year, target)
            fallback = ["package_failure_saved_CDF_retained" if baseline is not None else "package_failure_abstain"] * len(points)
            states = ["package_failure"] * len(points)
        if target == "rec_tgt" and method in ("selected_dynamic", "matched_static"):
            # Auxiliary failures abstain; no CDF points can be propagated.
            self._derived_points[year, method] = [None if fallback[i] else float(points[i]) for i in range(len(points))]
        frame = pd.DataFrame(dict(row_ordinal=np.arange(len(points)), point=points, fallback=fallback,
            history_state=states, baseline_fallback=baseline.fallback.to_numpy() if baseline is not None else "NO_ARCHIVED_CDF"))
        name = f"private/forecasts/{year}/{target}/{method}.parquet"; self.frame(name, frame)
        record = dict(slot, rows=len(frame), forecast=name, forecast_sha256=self.bindings[name], package_failure=package_failure)
        self.packages.append(record); self.forecasts[year, target, method] = frame
        self.write(f"package-results/{len(self.packages):02d}.json", dict(record, retention=self.storage.report_retention()))
        return dict(path=str(self.output / name), sha256=self.bindings[name])

    def freeze_year(self, year):
        name = f"year-freezes/{year}.json"
        self.write(name, dict(state="ALL_YEAR_FORECASTS_FROZEN", year=year,
            packages=[p for p in self.packages if p["year"] == year], scoring_outcomes_read=False,
            earlier_season_outcomes="permitted earlier-only priors; no original issuance", at=shared.now()))
        self.year_freezes[year] = self.bindings[name]
        # The original request/source receipts already persist; retain compact
        # forecast tables for selection/scoring, not five years of nested dicts.
        self.annual.release_requests(year)
        for task in study.TASKS:
            del self.requests[year, task]
        for method in ("selected_dynamic", "matched_static"):
            self._derived_points.pop((year, method), None)
        return dict(path=str(self.output / name), sha256=self.bindings[name])

    def _source_labels(self, year, target, cutoff):
        # A distinct scoring-role projection after the relevant immutable gate.
        if target not in study.TASKS:
            raise ValueError("only supported explicit workload labels use this projection")
        calendar = [g for g in self.calendar if g["season"] == year]
        filters = [[("season", "==", year), ("week", "==", g["week"]), ("team", "==", g["team"])] for g in calendar]
        stamp = str(cutoff) if cutoff is not None else shared.now()
        history_rows = self.source._project(self.spec["source_plan"]["qualified_history"], source.HISTORY_COLUMNS,
            filters, role="scoring_after_immutable_forecast_gate")
        raw_filters = [[("season", "==", year), ("season_type", "==", "REG"), ("week", "==", g["week"]),
                        ("team", "in", [g["team"]] + [a for a, t in source.TEAM_ALIASES.items() if t == g["team"]])]
                       for g in calendar]
        raw_rows = self.source._project(self.spec["source_plan"]["statistics"][str(year)], source.STAT_COLUMNS,
            raw_filters, role="explicit_count_scoring_after_immutable_forecast_gate")
        # Source helper also requires physical source pointers. Use the exact
        # original identity ordinal projection; no invented IDs or zero fields.
        ref = self.spec["source_plan"]["statistics"][str(year)]
        identity = self.source.identity_cache.get(("statistics", year))
        if identity is None:
            identity = self.source._project(ref, ("player_id", "season", "week", "season_type", "team"),
                [[]], role="identity_only_physical_ordinal")
            self.source.identity_cache["statistics", year] = identity
        periods = {(g["season"], g["week"], g["team"]) for g in calendar}
        raw_rows = source.attach_row_pointers(identity, raw_rows, body_sha256=ref["sha256"], kind="statistics", periods=periods)
        rows = source.qualified_player_rows(raw_rows, history_rows, calendar, task=target, cutoff=stamp)
        index = defaultdict(list)
        for row in rows:
            index[tuple(row[k] for k in shared.cdf.KEYS)].append(row)
        labels = []
        for query in self.queries[year].to_dict("records"):
            matches = index[tuple(query[k] for k in shared.cdf.KEYS)]
            row = matches[0] if len(matches) == 1 else None
            if row is not None:
                if any(row[k] != query[k] for k in ("team", "opponent", "position")) or utc(row["kickoff_utc"]) != utc(query["kickoff_utc"]):
                    raise ValueError("source outcome identity conflict")
                if row["participation_state"] not in ("played", "DNP", "unknown"):
                    raise ValueError("unsupported participation label")
            labels.append(dict(actual=row.get("count") if row else None,
                participation_state=row["participation_state"] if row else "unknown",
                outcome_state="SOURCE_QUALIFIED_FIELD" if row else "missing_or_ambiguous_or_unavailable_outcome"))
        return pd.DataFrame(labels)

    def development_loss_sums(self):
        if set(self.year_freezes) != {2020, 2021} or len(self.packages) != 24:
            raise ValueError("both development years must freeze before selecting")
        boundary = min(self.queries[2022].cutoff_utc, key=utc)
        self._advance(boundary)  # Never rewind; strict source clocks unchanged.
        results = {}
        for task in study.TASKS:
            frames = {name: [] for name in core.SETTINGS}; identities = []; outcomes = []
            masks = []
            for year in (2020, 2021):
                labels = self._source_labels(year, task, boundary)
                self.frame(f"private/labels/development/{year}/{task}.parquet", labels)
                y = pd.to_numeric(labels.actual, errors="coerce").to_numpy()
                mask = (labels.participation_state.eq("played").to_numpy() & shared.cdf.valid_support(y, "count")
                        & self.queries[year].position.isin(core.TASK_ROLES[task]).to_numpy())
                for setting in core.SETTINGS:
                    values = self.forecasts[year, task, setting].point.to_numpy()
                    mask &= np.isfinite(values); frames[setting].append(values)
                identities.extend(self.queries[year][shared.cdf.KEYS].to_dict("records")); outcomes.extend(y); masks.append(mask)
            mask = np.concatenate(masks); y = np.asarray(outcomes); cohort = digest([r for r, use in zip(identities, mask) if use])
            results[task] = {name: dict(rows=int(mask.sum()), cohort_sha256=cohort,
                squared_error_sum=float(np.square(np.concatenate(values)[mask] - y[mask]).sum())) for name, values in frames.items()}
        self.write("development-loss-components.json", results)
        return results

    def freeze_selection(self, selected):
        self.selected = selected
        name = "selection-freeze.json"; self.write(name, dict(state="DEVELOPMENT_SELECTION_FROZEN", selected=selected,
            tie_rule="smooth; largerH; largerkappa; smallerq", development_years=[2020, 2021], at=shared.now()))
        return dict(path=str(self.output / name), sha256=self.bindings[name])

    def freeze_global(self, packages, selected):
        if len(packages) != 54 or set(self.year_freezes) != set(range(2020, 2025)) or selected != self.selected:
            raise ValueError("all54 exact package freezes required")
        if self.spec.get("recovery_envelope"):
            envelope = self.spec["recovery_envelope"]
            expected = envelope["previous_consumption"]["prior_vector_reservations"] + envelope["remaining_limits"]["planned_prior_vectors"]
            if self.campaign_prior_reservations != expected:
                raise ValueError("exact old2+new13 prior reservations required; no restored budget")
        name = "forecast-freeze.json"; self.write(name, dict(state="GLOBAL_54_FORECASTS_FROZEN", selected=selected,
            packages=self.packages, bindings=dict(self.bindings), final_scoring_labels_read=False,
            evidence=EVIDENCE, at=shared.now()))
        self.global_frozen = True
        return dict(path=str(self.output / name), sha256=self.bindings[name])

    def _donor_labels(self, year, target):
        metadata = self.spec["control_metadata"][str(year)][target]["leaf_cdf"]
        columns = list(dict.fromkeys(metadata["forecast_columns"] + metadata["label_columns"]))
        donor = pd.read_parquet(metadata["binding"]["path"], columns=columns, use_threads=False)
        exact_context(self.queries[year], donor, target=target, year=year, method="leaf_cdf")
        if not donor.participation_state.isin(["played", "DNP", "unknown"]).all():
            raise ValueError("donor outcome participation state changed")
        fields = [c for c in donor if c in ("actual", "participation_state", "outcome_state", *shared.QUALIFICATION) or c.startswith("qualified_")]
        return donor[fields].reset_index(drop=True)

    def score_saved_rows_only(self):
        if not self.global_frozen:
            raise ValueError("all54 forecasts must freeze before final labels")
        views = []
        for year in shared.YEARS:
            for target in study.FINAL_TARGETS:
                labels = self._source_labels(year, target, None) if target == "rec_tgt" else self._donor_labels(year, target)
                self.labels[year, target] = labels
                name = f"private/labels/forward/{year}/{target}.parquet"; self.frame(name, labels)
                for package in [p for p in self.packages if p["phase"] == "forward" and p["year"] == year and p["target"] == target]:
                    view = dict(contract="FACTORED_SCORED_LABEL_VIEW", context=f"private/context/{year}.parquet",
                        context_sha256=self.bindings[f"private/context/{year}.parquet"], forecast=package["forecast"],
                        forecast_sha256=package["forecast_sha256"], labels=name, labels_sha256=self.bindings[name],
                        rows=self.query_count(year), target=target, method=package["method"],
                        scoring_callable="nfl_lab.direct_boosters.score_frozen_rows", category=self._category(target),
                        scorer_sha256=self.spec["scorer_sha256"], law_fields="ALL_NAN_POINT_ONLY_NO_INHERITED_CDF",
                        consumer="nfl_lab.dynamic_opportunity_backend.score_factored_view")
                    # Exercise the exact original scorer against each frozen
                    # view before declaring the scoring contract frozen.
                    self._scored(year, target, package["method"])
                    self.write(f"private/scored-views/{year}/{target}/{package['method']}.json", view); views.append(view)
            self.guard()
        self.write("scored-freeze.json", dict(state="ALL30_FACTORED_SCORED_VIEWS_FROZEN", views=views,
            bindings=dict(self.bindings), source_scoring_projection=True, new_model_law_fit_calls=0))

    def _scored(self, year, target, method):
        name = f"private/forecasts/{year}/{target}/{method}.parquet"
        saved = pd.read_parquet(shared._spec(dict(path=str(self.output / name), sha256=self.bindings[name])), use_threads=False)
        return score_factored_view(self.queries[year], saved, self.labels[year, target], self._category(target), method)

    def _informed_pairs(self, rows, controls, category):
        candidate = rows.loc[rows.method.eq("selected_dynamic")].copy()
        informed = candidate.fallback.fillna("").eq("").to_numpy()
        candidate.loc[~informed, "point"] = np.nan
        results = []
        for comparator in ("leaf_cdf", "matched_static"):
            control = (controls.loc[controls.method.eq(comparator)].copy() if comparator == "leaf_cdf"
                       else rows.loc[rows.method.eq(comparator)].copy())
            # Keep every offered key and state; only the prespecified diagnostic
            # score mask changes. It is never the primary nomination cohort.
            if not candidate[shared.cdf.KEYS].reset_index(drop=True).equals(control[shared.cdf.KEYS].reset_index(drop=True)):
                raise ValueError("informed diagnostics require exact full ordered controls")
            control.loc[~informed, "point"] = np.nan
            for primary in (False, True):
                report, _ = evaluator.product_pairs(candidate, control, category, role_subset=primary)
                report.update(candidate="selected_dynamic", comparator=comparator,
                    period="pooled_2022_2024", population="informed_primary_roles" if primary else "informed_all_offered",
                    decision_use="DESCRIPTIVE_ONLY; whole-policy primary retains all fallbacks")
                results.append(report)
        return results

    def _matched_static_report(self, rows, category):
        reports = []
        for period in (*shared.YEARS, "pooled_2022_2024"):
            part = rows if isinstance(period, str) else rows.loc[rows.season.eq(period)]
            candidate = part.loc[part.method.eq("selected_dynamic")]; control = part.loc[part.method.eq("matched_static")]
            for primary in (False, True):
                report, losses = evaluator.product_pairs(candidate, control, category, role_subset=primary)
                report.update(candidate="selected_dynamic", comparator="matched_static", period=period,
                              population="primary_roles" if primary else "all_offered")
                if isinstance(period, str):
                    mask = losses.paired_eligible.to_numpy()
                    report["week_interval"] = _bootstrap(losses, mask, "week", 500, 1703)
                    report["game_interval"] = _bootstrap(losses, mask, "game", 500, 1703)
                reports.append(report)
        return reports

    def _aux_report(self, rows, category):
        reports = []; summaries = []
        for method, candidate in rows.groupby("method", sort=False):
            for period in (*shared.YEARS, "pooled_2022_2024"):
                a = candidate if isinstance(period, str) else candidate.loc[candidate.season.eq(period)]
                for primary in (False, True):
                    subset = a.loc[a.primary_role] if primary else a
                    item = evaluator.summary(subset, category)
                    item.update(method=method, period=period, population="primary_roles" if primary else "all_offered")
                    summaries.append(item)
                    for comparator in ("matched_static", "aux_recent3", "aux_pooled8"):
                        if comparator == method:
                            continue
                        control = rows.loc[rows.method.eq(comparator) & rows.season.isin(a.season.unique())]
                        report, losses = evaluator.product_pairs(a, control, category, role_subset=primary)
                        report.update(candidate=method, comparator=comparator, period=period,
                                      population="primary_roles" if primary else "all_offered")
                        if isinstance(period, str):
                            mask = losses.paired_eligible.to_numpy()
                            report["week_interval"] = _bootstrap(losses, mask, "week", 500, 1703)
                            report["game_interval"] = _bootstrap(losses, mask, "game", 500, 1703)
                        reports.append(report)
        return dict(target="rec_tgt", auxiliary=True, summaries=summaries, pairs=reports,
                    raw_SITE_CDF="UNAVAILABLE_NOT_RECREATED", primary_metric="MSE")

    def report_same_evaluator(self, replicates, seed, all_targets):
        if (replicates, seed) != (500, 1703) or tuple(all_targets) != study.ALL_TARGETS or not self.global_frozen:
            raise ValueError("exact target/uncertainty contract and global freeze required")
        reports = {}; matrix = []
        # parent._control consumes these exact original bindings after freeze.
        self.spec["control_root"] = self.spec["source_plan"]["controls"]["root"]
        for target in ("rush_att", "rec", "rec_yd", "rec_tgt"):
            category = self._category(target)
            methods = ("selected_dynamic", "matched_static", "aux_recent3", "aux_pooled8") if target == "rec_tgt" else ("selected_dynamic", "matched_static")
            rows = pd.concat([self._scored(year, target, method) for year in shared.YEARS for method in methods], ignore_index=True)
            if target == "rec_tgt":
                report = self._aux_report(rows, category)
            else:
                controls = pd.concat([evaluator._control(self, year, target, method, category)
                                      for year in shared.YEARS for method in evaluator.CONTROLS], ignore_index=True)
                report, temporary_losses = evaluator.target_report(rows, controls, category, self.guard)
                del temporary_losses
                report["matched_static_pairs"] = self._matched_static_report(rows, category)
                report["legacy_evaluator_nominations"] = report.pop("research_nominations")
                # Legacy helper's role_B nomination is retained as an auxiliary
                # diagnostic, never substituted for this study's static gate.
                report["research_nominations"] = [development_nomination(report)]
                report["informed_only_diagnostics"] = self._informed_pairs(rows, controls, category)
            report.update(evidence=EVIDENCE, selected=self.selected, scientific_qualification=False, release_ready=False)
            informed = rows.fallback.fillna("").eq("") & rows.method.eq("selected_dynamic")
            report["informed_coverage"] = dict(offered=int(rows.method.eq("selected_dynamic").sum()), informed=int(informed.sum()),
                fallback_reasons=rows.loc[rows.method.eq("selected_dynamic"), "fallback"].value_counts().to_dict(),
                history_reasons=rows.loc[rows.method.eq("selected_dynamic"), "history_state"].value_counts().to_dict())
            self.frame(f"private/subgroups/{target}.parquet", evaluator.subgroup_rows(rows, category))
            views = dict(contract="REPLAYABLE_PAIRED_LOSS_VIEW", target=target, all_original_rows_retained=True,
                methods=list(methods), years=list(shared.YEARS), scored_view_root="private/scored-views",
                controls=self.spec["control_metadata"] if target != "rec_tgt" else None,
                callable="nfl_lab.direct_booster_screen.product_pairs", scorer_sha256=self.spec["pair_scorer_sha256"],
                population_masks=["all_offered", "primary_roles"], uncertainty=dict(replicates=500, seed=1703,
                clusters=["season_week", "season_game"], interpretation="nominal exposed-development only"))
            self.write(f"private/paired-loss-views/{target}.json", views)
            self.write(f"target-reports/{target}.json", report); reports[target] = report
            self.guard()
        for target in all_targets:
            matrix.append(dict(target=target, state="NEW_EXPOSED_POINT_COMPARISON" if target in reports else
                "BLOCKED_EXACT_PPR_LABELS" if target == "fantasy_ppr" else "RETAIN_EXISTING_REFERENCE_NO_NEW_EXPERIMENT",
                evidence=EVIDENCE if target in reports else "No gain transferred from related categories",
                scientific_qualification=False, release_ready=False))
        self.write("twelve-category-matrix.json", matrix)
        result = dict(state="REPORT_COMPLETE", version=VERSION, targets=reports, auxiliary_target="rec_tgt",
            categories=matrix, selected=self.selected, forecast_packages=54,
            evidence=EVIDENCE, missing_comparators="Historical raw Sleeper/SITE unavailable; N/A",
            source_proxy_totals="Recorded partial all-position sums, not certified complete NFL totals",
            prospective_issued_forecasts=0, scientific_qualification=False, release_ready=False,
            website_default_changed=False, phase_usage=dict(self.phase_usage), retention=self.storage.report_retention())
        self.write("report.json", result)
        self.write("DYNAMIC_FINISHED.json", dict(state="COMPLETED", at=shared.now(),
            packages=54, campaign_prior_reservations=self.campaign_prior_reservations,
            previous_consumption=self.spec.get("recovery_envelope", {}).get("previous_consumption"),
            phase_usage=dict(self.phase_usage), wall_seconds=time.monotonic()-self.start,
            CPU_seconds=time.process_time()-self.cpu_start, retention=self.storage.report_retention()), freeze=False)
        return result

    def retain_failure(self, error, sequence):
        self.failure("DYNAMIC_FAILURE.json", error)
        self.write("DYNAMIC_FINISHED.json", dict(state="FAILED", at=shared.now(),
            packages=len(sequence.frozen), pending=sequence.pending, row_incidences=sequence.row_incidences,
            prior_vectors=sorted(sequence.prior_vectors), campaign_prior_reservations=self.campaign_prior_reservations,
            previous_consumption=self.spec.get("recovery_envelope", {}).get("previous_consumption"), phase_usage=dict(self.phase_usage),
            wall_seconds=time.monotonic()-self.start, CPU_seconds=time.process_time()-self.cpu_start,
            retention=self.storage.report_retention()), freeze=False)


def run(spec, *, registration_sha256, final_static):
    """Called once by the independently sealed, resource-supervised CLI."""
    backend = Backend(spec, registration_sha256=registration_sha256, final_static=final_static)
    with no_external_models():
        return study.run_study(backend)
