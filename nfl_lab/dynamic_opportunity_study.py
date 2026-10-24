"""Finite 54-package orchestration over an authenticated existing backend.

This draft creates no second loader/evaluator/storage implementation. The
backend must bind ProjectionSource, the original shared scorer/report helpers,
owned storage and outer guards in the actual independently sealed execution.
There is no CLI that can bypass those prerequisites.
"""
from __future__ import annotations

from contextlib import contextmanager
import math
import time

from . import dynamic_opportunity_core as core

VERSION = "dynamic-opportunity-study-v1-20261023"
TASKS = ("rush_att", "rec_tgt")
FINAL_TARGETS = ("rush_att", "rec_tgt", "rec", "rec_yd")
ALL_TARGETS = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd", "rush_att",
               "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td")
PHASE_LIMITS = {"source_prior": 100, "development_forecast": 120, "selection": 10,
                "forward_forecast": 120, "scoring": 60, "reporting": 160}
# 570 assigned seconds plus 30 for terminal/failure persistence; no automatic
# phase transfer or expansion. The outer immutable supervisor owns600 totals.


def slots():
    planned = [dict(phase="development", year=year, target=task, method=setting)
               for year in (2020, 2021) for task in TASKS for setting in core.SETTINGS]
    for year in (2022, 2023, 2024):
        planned.extend(dict(phase="forward", year=year, target=target, method=method)
                       for target in FINAL_TARGETS for method in ("selected_dynamic", "matched_static"))
        planned.extend(dict(phase="forward", year=year, target="rec_tgt", method=method)
                       for method in ("aux_recent3", "aux_pooled8"))
    return planned


def slot_key(slot):
    return tuple(slot[k] for k in ("phase", "year", "target", "method"))


class Sequence:
    """Reserve before work; no repeated packages or widened spent budgets."""
    def __init__(self):
        self.planned = slots(); self.frozen = []; self.pending = None
        self.row_incidences = 0; self.prior_vectors = set(); self.selection_frozen = False
        self.global_frozen = False; self.start = time.monotonic(); self.cpu = time.process_time()
        self.phase = "FORECAST"; self.year_receipts = {}

    def check(self):
        if time.monotonic() - self.start >= 600 or time.process_time() - self.cpu >= 600:
            raise RuntimeError("finite dynamic study time budget consumed")

    def reserve(self, slot, rows):
        self.check()
        if (self.phase != "FORECAST" or self.pending is not None or type(rows) is not int or rows <= 0
                or self.row_incidences + rows > 600000 or len(self.frozen) >= 54
                or slot_key(slot) != slot_key(self.planned[len(self.frozen)])):
            raise ValueError("unplanned, repeated or unreserved forecast package")
        if slot["phase"] == "forward" and not self.selection_frozen:
            raise ValueError("forward forecasts require immutable development selection")
        self.pending = (*slot_key(slot), rows); self.row_incidences += rows

    def freeze(self, slot, rows, binding):
        if self.pending != (*slot_key(slot), rows) or not binding:
            raise ValueError("exact pending forecast/persistence receipt required")
        self.frozen.append(dict(slot, rows=rows, binding=binding)); self.pending = None

    def form_prior_vector(self, year, kind):
        if kind not in ("rush_att", "rec_tgt", "fixed_efficiency") or year not in (2020, 2021, 2022, 2023, 2024):
            raise ValueError("unregistered earlier-only prior vector")
        key = (year, kind)
        if key in self.prior_vectors or len(self.prior_vectors) >= 16:
            raise ValueError("repeated or exhausted prior-vector formation")
        self.prior_vectors.add(key)

    def freeze_year(self, year, binding):
        expected = [s for s in self.planned if s["year"] == year]
        actual = [s for s in self.frozen if s["year"] == year]
        if len(actual) != len(expected) or self.pending is not None or not binding:
            raise ValueError("all same-year output must persist before later training")
        self.year_receipts[year] = binding

    def before_development_labels(self, year):
        if year not in (2020, 2021) or year not in self.year_receipts:
            raise ValueError("development outcome access requires same-year forecast freeze")

    def freeze_selection(self, binding):
        if len(self.frozen) != 24 or any(y not in self.year_receipts for y in (2020, 2021)) or not binding:
            raise ValueError("exact complete development freeze required")
        self.selection_frozen = True

    def freeze_global(self, binding):
        if len(self.frozen) != 54 or self.pending is not None or not binding or any(y not in self.year_receipts for y in (2022, 2023, 2024)):
            raise ValueError("all54 original package outputs must freeze before final scoring")
        self.global_frozen = True; self.phase = "SCORE"

    def before_final_labels(self):
        if not self.global_frozen or self.phase not in ("SCORE", "REPORT"):
            raise ValueError("final evaluation labels forbidden before global freeze")


def setting_rank(name):
    family, half_life, kappa, hazard = core.SETTINGS[name]
    return (0 if family == "smooth" else 1, -half_life, -kappa, hazard)


def select_once(loss_sums):
    """Pooled MSE on the same setting-invariant supported dev opportunities."""
    selected = {}
    for task in TASKS:
        rows = loss_sums[task]
        if set(rows) != set(core.SETTINGS):
            raise ValueError("all six fixed settings retained")
        identities = {rows[name]["cohort_sha256"] for name in rows}
        counts = {rows[name]["rows"] for name in rows}
        if len(identities) != 1 or len(counts) != 1:
            raise ValueError("setting-specific development population forbidden")
        count = next(iter(counts))
        if type(count) is not int or count <= 0:
            selected[task] = None
            continue
        if any(not isinstance(r["squared_error_sum"], (int, float)) or not math.isfinite(r["squared_error_sum"])
               or r["squared_error_sum"] < 0 for r in rows.values()):
            raise ValueError("finite saved development MSE components required")
        selected[task] = min(core.SETTINGS, key=lambda s: (rows[s]["squared_error_sum"] / count, setting_rank(s)))
    return selected


def predict_request(request, prior, *, setting, static=False):
    """Frozen arithmetic only; a failed request does not invent a fallback."""
    if request.get("state") != "READY_CORE_REQUEST" or setting is None:
        return dict(point=None, state="BASELINE_FALLBACK_REQUIRED", reason=request.get("reason", "no_selected_recipe"))
    query = core.Query.from_manifest(request["core_query"])
    history = [core.Slot.from_manifest(s) for s in request["history"]]
    result = core.forecast(query, prior, history, setting=setting,
                           volume=request["volume"], volume_supported=request["volume_supported"])
    if result["state"] == "READY_POINT" and static:
        observed = [core.paired_count(s) for s in history]
        c = sum(row[2] for row in observed if row[0]); t = sum(row[3] for row in observed if row[0])
        kappa = core.SETTINGS[setting][2]
        share = (kappa * prior.share + c) / (kappa + t)
        result = dict(result, point=request["volume"] * share, share=share, components=[],
                      reason="same_history_prior_volume_and_kappa_static_control", static_control=True)
    return result


def fixed_efficiency(prior, selected_rows):
    """Identical untuned conversion in dynamic/static target propagation.

    Caller binds the same selected eight game slots and earlier-training role
    priors. Unknown/unsupported rows stay in the audit and contribute no counts.
    """
    if not prior or prior.get("state") != "READY":
        return dict(state="FALLBACK_REQUIRED", reason="missing_training_efficiency_prior", catch_rate=None, YPT=None)
    c0, y0 = prior["catch_rate"], prior["YPT"]
    if (type(c0) not in (int, float) or not math.isfinite(c0) or not 0 <= c0 <= 1
            or type(y0) not in (int, float) or not math.isfinite(y0) or len(selected_rows) > 8):
        raise ValueError("fixed efficiency prior/window invalid")
    catches = targets_c = yards = targets_y = 0.; audit = []
    for row in selected_rows:
        if row.get("source_qualified") is not True or row.get("participation_state") != "played":
            audit.append("unknown_or_unqualified_no_update"); continue
        t, c, y = (row.get(k) for k in ("targets", "receptions", "receiving_yards"))
        if t is None:
            audit.append("missing_targets_no_update"); continue
        if not core._count(t):
            raise ValueError("invalid explicit target exposure")
        if c is not None:
            if not core._count(c) or c > t:
                raise ValueError("invalid compatible catches/targets")
            catches += c; targets_c += t
        if y is not None:
            if type(y) not in (int, float) or not math.isfinite(y):
                raise ValueError("signed receiving yards invalid")
            yards += y; targets_y += t
        audit.append("explicit_paired_fields_only")
    return dict(state="READY", catch_rate=(100*c0+catches)/(100+targets_c),
                YPT=(100*y0+yards)/(100+targets_y), strength=100, slots=audit)


def propagated_point(target_point, efficiency, target):
    if target not in ("rec", "rec_yd"):
        raise ValueError("only fixed reception/receiving-yard propagation")
    if target_point is None or not efficiency or efficiency.get("state") != "READY":
        return None
    value = target_point * efficiency["catch_rate" if target == "rec" else "YPT"]
    if not math.isfinite(value) or target == "rec" and value < 0:
        raise ValueError("propagated point outside declared support")
    return value


def auxiliary_simple(selected_counts, role_mean, *, window):
    if window not in (3, 8) or type(role_mean) not in (int, float) or not math.isfinite(role_mean) or role_mean < 0:
        return None
    values = [v for v in selected_counts[-window:] if v is not None]
    if any(not core._count(v) for v in values):
        raise ValueError("auxiliary simple explicit counts invalid")
    strength = 3 if window == 3 else 5
    return (sum(values) + strength * role_mean) / (len(values) + strength)


def retention_estimate(package_rows, *, bytes_per_forecast_row=32, bytes_per_scored_row=40,
                       bytes_per_loss_row=20, loss_rows=0, request_rows=0, limit_bytes=50331648,
                       scored_label_view=None, paired_loss_view=None):
    """Predata conservative planning estimate; exact admission is still binding."""
    if len(package_rows) != 54 or any(type(n) is not int or n <= 0 for n in package_rows):
        raise ValueError("54 exact context-derived row counts required before work")
    rows = sum(package_rows)
    fixed = 4*1024*1024
    parts = dict(forecasts=rows*bytes_per_forecast_row, scored=rows*bytes_per_scored_row,
                 paired_losses=loss_rows*bytes_per_loss_row, factored_requests=request_rows*64,
                 metadata_reports_logs_failure_reserve=fixed)
    if scored_label_view is not None:
        if (scored_label_view.get("contract") != "FACTORED_SCORED_LABEL_VIEW"
                or not scored_label_view.get("context_and_forecast_bindings_required")
                or type(scored_label_view.get("unique_label_rows")) is not int
                or scored_label_view["unique_label_rows"] < 0):
            raise ValueError("exact replayable scored-view contract required")
        parts["scored"] = scored_label_view["unique_label_rows"] * 40 + 54*1024
    if paired_loss_view is not None:
        if (paired_loss_view.get("contract") != "REPLAYABLE_PAIRED_LOSS_VIEW"
                or not paired_loss_view.get("original_scorer_and_all_scored_bindings_required")
                or type(paired_loss_view.get("views")) is not int or paired_loss_view["views"] < 0):
            raise ValueError("exact replayable loss-view contract required")
        parts["paired_losses"] = paired_loss_view["views"] * 2048
    return dict(forecast_row_incidences=rows, parts_bytes=parts, estimated_new_bytes=sum(parts.values()),
                within_row_cap=rows <= 600000, within_retention_estimate=sum(parts.values()) <= limit_bytes,
                retention_limit_bytes=limit_bytes,
                logical_scored_rows=rows, logical_paired_loss_rows=loss_rows,
                scored_label_view=scored_label_view, paired_loss_view=paired_loss_view,
                guarantee=False, action="REJECT_BEFORE_FORECAST_IF_ESTIMATE_OR_EXACT_ADMISSION_FAILS")


def run_study(backend):
    """Bounded draft using one reviewed source/evaluator/storage backend.

    ``backend`` is part of the later exact code/environment freeze. It must
    implement the methods below with original shared modules, not a new score
    formula. No public command constructs or seals such a backend here.
    """
    if backend.state != "FROZEN_ROOT_REVIEWER_SEALED" or backend.version != VERSION:
        raise ValueError("one independently accepted backend and exact execution seal required")
    sequence = Sequence(); backend.verify_owned_entry(); backend.consume_once()
    try:
        with backend.cumulative_phase_limit("source_prior", 100, 100):
            estimate = backend.preflight(slots())
        if not estimate["within_row_cap"] or not estimate["within_retention_estimate"]:
            raise RuntimeError("predeclared source/forecast/score/report retention estimate does not fit")
        backend.save_plan_and_estimate(estimate)
        for year in (2020, 2021):
            sequence.check(); backend.guard()
            if year > 2020 and year-1 not in sequence.year_receipts:
                raise ValueError("previous-year freeze required before earlier outcomes enter training")
            for task in TASKS:
                sequence.form_prior_vector(year, task)
            with backend.cumulative_phase_limit("source_prior", 100, 100):
                backend.prepare_year(year, prior_kinds=TASKS)
            for slot in [s for s in sequence.planned if s["year"] == year]:
                rows = backend.query_count(year); sequence.reserve(slot, rows)
                with backend.cumulative_phase_limit("development_forecast", 120, 120), backend.package_limit(20, 20):
                    binding = backend.forecast_package(slot, selected=None, compute=predict_request)
                sequence.freeze(slot, rows, binding); backend.guard()
            sequence.freeze_year(year, backend.freeze_year(year))
        for year in (2020, 2021):
            sequence.before_development_labels(year)
        with backend.cumulative_phase_limit("selection", 10, 10):
            selected = select_once(backend.development_loss_sums())
        sequence.freeze_selection(backend.freeze_selection(selected))
        for year in (2022, 2023, 2024):
            if year-1 not in sequence.year_receipts:
                raise ValueError("earlier-year forecast boundary missing")
            for kind in (*TASKS, "fixed_efficiency"):
                sequence.form_prior_vector(year, kind)
            with backend.cumulative_phase_limit("source_prior", 100, 100):
                backend.prepare_year(year, prior_kinds=(*TASKS, "fixed_efficiency"))
            for slot in [s for s in sequence.planned if s["year"] == year]:
                rows = backend.query_count(year); sequence.reserve(slot, rows)
                with backend.cumulative_phase_limit("forward_forecast", 120, 120), backend.package_limit(20, 20):
                    binding = backend.forecast_package(slot, selected=selected, compute=predict_request)
                sequence.freeze(slot, rows, binding); backend.guard()
            sequence.freeze_year(year, backend.freeze_year(year))
        sequence.freeze_global(backend.freeze_global(sequence.frozen, selected))
        sequence.before_final_labels()
        with backend.cumulative_phase_limit("scoring", 60, 60):
            backend.score_saved_rows_only()  # unchanged original scorer; zero model/law/source calls
        sequence.phase = "REPORT"; sequence.before_final_labels()
        with backend.cumulative_phase_limit("reporting", 160, 160):
            result = backend.report_same_evaluator(replicates=500, seed=1703, all_targets=ALL_TARGETS)
        sequence.phase = "DONE"
        return result
    except BaseException as error:
        backend.retain_failure(error, sequence=sequence)
        raise
    finally:
        backend.verify_owned_exit()
