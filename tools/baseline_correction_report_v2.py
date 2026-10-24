"""Finish seven immutable correction reports; reuse four completed reports."""
from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
import resource
import time
from unittest.mock import patch

import pandas as pd
from threadpoolctl import threadpool_limits

from direct_booster_frozen_report import no_science, relative
from direct_xgboost_binary_recovery import storage as original_storage, process_free_threads
from nfl_lab import direct_booster_screen as parent, source_matched_benchmark as shared
from nfl_lab.owned_reference_batch import validate_owned_references
from nfl_lab.reference_runtime import _deadline
import baseline_correction_orchestrator as original_correction

VERSION = "baseline-correction-report-v2-20261023"
POLICY_SHA256 = "0259cb78935551534453d71458af866037498da3aa1e8b5add95b7b7906eda49"
REUSE = ("pass_yd", "pass_td", "pass_cmp", "pass_att")
REMAINING = ("pass_int", "rush_yd", "rush_att", "rec", "rec_yd", "rush_rec_yd", "anytime_td")
METHODS = ("cdf_offset_intercept_v1", "cdf_offset_context_v1")


def work_plan(categories):
    if (set(categories) != set(REUSE + REMAINING + ("fantasy_ppr",))
            or categories["fantasy_ppr"]["state"] == "READY"
            or any(categories[t]["state"] != "READY" for t in REUSE + REMAINING)):
        raise ValueError("exact four reused/seven remaining/PPR blocked required")
    return {target: "REUSE_EXACT_BYTES" if target in REUSE else "AGGREGATE_FROZEN_ROWS" if target in REMAINING
        else "BLOCKED_EXACT_PPR" for target in shared.models.TARGETS}


def storage(spec):
    store, output = original_storage(spec)  # Original64MiB helper plus stricter16MiB admission.
    inherited = store.report_retention
    def retention():
        value = dict(inherited())
        value["borrowed_helper_limit_bytes"] = value["limit_bytes"]
        value["limit_bytes"] = 16777216
        return value
    store.report_retention = retention
    return store, output


def frozen_slot_paths(spec, forecast, scored):
    planned = [(year, target, method) for year in shared.YEARS
        for target in shared.models.TARGETS if target != "fantasy_ppr" for method in METHODS]
    identity = lambda row: (row["year"], row["target"], row["method"])
    if ([identity(row) for row in forecast["slots"]] != planned
            or [identity(row) for row in scored["slots"]] != planned):
        raise ValueError("exact66 original frozen slot sequence required")
    owned = {}
    for slot, source in zip(scored["slots"], forecast["slots"]):
        name = f"private/scored/{slot['year']}/{slot['target']}/{slot['method']}.parquet"
        expected_forecast = f"private/forecasts/{slot['year']}/{slot['target']}/{slot['method']}.parquet"
        if (slot["scored"] != name or slot["forecast"] != expected_forecast
                or slot["rows"] != {2022:8686, 2023:8606, 2024:8580}[slot["year"]]
                or any(slot[key] != value for key, value in source.items())
                or name not in scored["bindings"]):
            raise ValueError("original scored identity/count/forecast association changed")
        owned[str(relative(Path(spec["parent_root"]), name))] = scored["bindings"][name]
    if sum(name.startswith("private/scored/") for name in scored["bindings"]) != 66:
        raise ValueError("extra or missing original scored artifact")
    return owned


def control_paths(spec, controls):
    owned = {}
    for year in shared.YEARS:
        for target in REUSE + REMAINING:
            for method in parent.CONTROLS:
                name = f"private/scored/{year}/{target}/{method}/rows.parquet"
                if name not in controls["scored_files"]:
                    raise ValueError("original five-control inventory incomplete")
                owned[str(relative(Path(spec["control_root"]), name))] = controls["bindings"][name]
    if len(owned) != 165:
        raise ValueError("exact165 original control references required")
    return owned


class Session:
    write = shared.Session.write
    frame = shared.Session.frame

    def __init__(self, spec):
        self.spec = spec
        self.start, self.cpu_start = time.monotonic(), time.process_time()
        self.storage, self.output = storage(spec)
        self.bindings = {}

    def check(self):
        if (time.monotonic() - self.start >= 590 or time.process_time() - self.cpu_start >= 590
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 >= 1073741824):
            raise RuntimeError("separate reporting resource reserve exhausted")


@contextmanager
def report_only():
    def forbidden(*a, **k):
        raise AssertionError("continuation forbids fits/inference/labels/source/models/law/scoring")
    with no_science(), ExitStack() as guards:
        import pickle
        blocked = [(parent.direct, "score_frozen_rows"),
            (original_correction, "run"), (original_correction, "query_frame"),
            (original_correction, "baseline_projection"), (original_correction, "labels_from"),
            (original_correction, "training_frame"), (original_correction, "forecast_rows"),
            (original_correction, "fit_package"),
            (original_correction.correction.BaselineCorrection, "fit"),
            (original_correction.correction.BaselineCorrection, "predict"),
            (original_correction.correction.CorrectionDesign, "fit"),
            (shared.cdf.LeafCDFModel, "fit"), (shared.cdf.LeafCDFModel, "predict_batches"),
            (shared.cdf, "prediction_rows"),
            (pickle, "load"), (pickle, "loads")]
        for owner, name in blocked:
            guards.enter_context(patch.object(owner, name, forbidden))
        yield


@contextmanager
def frozen_reads_only(spec, scored):
    """Only the remaining42 candidate and105 control frames may be decoded."""
    allowed = {str(relative(Path(spec["parent_root"]), slot["scored"]))
        for slot in scored["slots"] if slot["target"] in REMAINING}
    allowed |= {str(relative(Path(spec["control_root"]),
        f"private/scored/{year}/{target}/{method}/rows.parquet"))
        for year in shared.YEARS for target in REMAINING for method in parent.CONTROLS}
    if len(allowed) != 147:
        raise ValueError("exact42 remaining scored plus105 control decode paths required")
    original_read = pd.read_parquet
    def read(path, *args, **kwargs):
        if str(path) not in allowed:
            raise AssertionError("unregistered source/query/reused-target semantic read")
        return original_read(path, *args, **kwargs)
    with patch.object(pd, "read_parquet", read):
        yield


def metadata(spec):
    names = ("parent_execution_freeze", "parent_forecast_freeze", "parent_scored_freeze",
        "parent_FAILED_completion", "parent_config", "category_contract", "control_scored_freeze")
    meta = {name: json.loads(shared._spec(spec[name]).read_text()) for name in names}
    execution, forecast, scored, terminal = (meta[name] for name in (
        "parent_execution_freeze", "parent_forecast_freeze", "parent_scored_freeze", "parent_FAILED_completion"))
    if (terminal["state"] != "FAILED" or terminal["limit_reason"] != "CPU_LIMIT"
            or terminal["returncode"] == 0 or terminal["new_HTTP"] != 0
            or terminal["threads"] != 2 or forecast["state"] != "GLOBAL_66_FORECASTS_FROZEN"
            or scored["state"] != "ALL66_SCORED_ROWS_FROZEN"
            or forecast["usage"]["correction_fit_attempts"] != 44
            or forecast["usage"]["forecast_files"] != 66
            or forecast["usage"]["forecast_row_incidences"] != 569184):
        raise ValueError("failed parent with all44fits/all66forecasts/scored required")
    if execution["plan_sha256"] != spec["parent_config"]["sha256"]:
        raise ValueError("original execution/science registration association changed")
    old = execution["execution_metadata"]
    for name in ("cache", "control_root", "source_policy", "category_contract", "control_scored_freeze", "source_manifest"):
        if spec[name] != old[name] or spec[name] != meta["parent_config"][name]:
            raise ValueError("original source/control contract changed:" + name)
    if (spec["parent_root"] != old["output"] or spec["methods"] != list(METHODS)
            or spec["reused_targets"] != list(REUSE) or spec["remaining_targets"] != list(REMAINING)):
        raise ValueError("exact correction arm/namespace/report partition required")
    categories = meta["category_contract"]["categories"]
    work_plan(categories)
    owned = {spec[name]["path"]: spec[name]["sha256"] for name in names
        if name not in ("parent_config", "category_contract")}
    owned[spec["source_manifest"]["path"]] = spec["source_manifest"]["sha256"]
    root = Path(spec["parent_root"])
    frozen = frozen_slot_paths(spec, forecast, scored)
    frozen.update(control_paths(spec, meta["control_scored_freeze"]))
    if frozen != spec["scored_and_control_bindings"]:
        raise ValueError("complete231 frozen data reference bindings changed")
    owned.update(frozen)
    if set(spec["completed_outputs"]) != set(REUSE):
        raise ValueError("exact four byte-reused reports required")
    for target, files in spec["completed_outputs"].items():
        if set(files) != {"report", "pairs", "subgroups"}:
            raise ValueError("all original report/private output references required")
        for kind, name in (("report", f"target-reports/{target}.json"),
                ("pairs", f"private/paired-losses/{target}.parquet"),
                ("subgroups", f"private/subgroups/{target}.parquet")):
            binding = files[kind]
            if binding["path"] != str(relative(root, name)):
                raise ValueError("reused completed output escaped original namespace")
            owned[binding["path"]] = binding["sha256"]
    return meta, owned


def reuse_target(session, target, files):
    if target not in REUSE:
        raise ValueError("unregistered completed target")
    for kind, name in (("report", f"target-reports/{target}.json"),
            ("pairs", f"private/paired-losses/{target}.parquet"),
            ("subgroups", f"private/subgroups/{target}.parquet")):
        source = files[kind]
        if session.authenticated_controls.get(source["path"], {}).get("sha256") != source["sha256"]:
            raise ValueError("original completed output not owned/authenticated")
        # All bytes already belong to immutable CAS. No private Parquet decode,
        # new bytes, recomputation, direct link syscall or alternate store.
        session.storage.import_file(source["path"], session.output / name, expected_sha256=source["sha256"])
        session.bindings[name] = source["sha256"]
    report = json.loads(Path(files["report"]["path"]).read_text())
    if report["target"] != target:
        raise ValueError("complete report target mismatch")
    return report


def aggregate_target(session, target, category, slots):
    if target not in REMAINING:
        raise ValueError("completed target may not be aggregated again")
    rows = pd.concat([pd.read_parquet(relative(Path(session.spec["parent_root"]), slot["scored"]))
        for slot in slots if slot["target"] == target], ignore_index=True)
    controls = pd.concat([parent._control(session, year, target, method, category)
        for year in shared.YEARS for method in parent.CONTROLS], ignore_index=True)
    report, pairs = parent.target_report(rows, controls, category, session.check)
    report["later_2023_2024_descriptive_pairs"] = original_correction.later_descriptive_pairs(rows, controls, category)
    session.frame(f"private/paired-losses/{target}.parquet", pairs)
    session.frame(f"private/subgroups/{target}.parquet", parent.subgroup_rows(rows, category))
    session.write(f"target-reports/{target}.json", report)
    return report


def matrix_record(session, target, report):
    if target == "fantasy_ppr":
        return dict(target=target, state="BLOCKED_EXACT_PPR", rows=0,
            scientific_qualification=False, release_ready=False)
    name = f"target-reports/{target}.json"
    return dict(target=target, state="REUSED_COMPLETE" if target in REUSE else "AGGREGATED_FROZEN_ROWS",
        full_report=dict(path=name, sha256=session.bindings[name]),
        pooled_primary_pairs=[row for row in report["pairs"]
            if row["period"] == "pooled_2022_2024" and row["population"] == "primary_roles"],
        research_nominations=report["research_nominations"],
        scientific_qualification=False, release_ready=False)


def run(spec, *, plan_sha256, final_static):
    if plan_sha256 != POLICY_SHA256 or spec["registration_id"] != VERSION:
        raise ValueError("separate report-only registration required")
    session = Session(spec)
    if (session.output / "REPORT_CONTINUATION_CONSUMED.json").exists():
        raise RuntimeError("one reporting continuation already consumed; no retry")
    session.write("REPORT_CONTINUATION_CONSUMED.json", dict(at=shared.now(), registration_sha256=plan_sha256,
        new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0))
    state = "FAILED"
    try:
        with _deadline(590), process_free_threads(spec["loaded_libc"]), threadpool_limits(limits=2), report_only():
            meta, owned = metadata(spec)
            session.authenticated_controls, entry = validate_owned_references(session.storage, owned)
            session.control_freeze = meta["control_scored_freeze"]
            session.write("owned-input-entry.json", entry)
            session.write("report-work-plan.json", work_plan(meta["category_contract"]["categories"]))
            matrix = []
            with frozen_reads_only(spec, meta["parent_scored_freeze"]):
                for target in shared.models.TARGETS:
                    session.check()
                    if target == "fantasy_ppr": report = None
                    elif target in REUSE: report = reuse_target(session, target, spec["completed_outputs"][target])
                    else:
                        category = shared._category(meta["category_contract"]["categories"], target)
                        report = aggregate_target(session, target, category, meta["parent_scored_freeze"]["slots"])
                    matrix.append(matrix_record(session, target, report))
            final_static(); metadata(spec)
            owned.update({str(session.output / name): digest for name, digest in session.bindings.items()})
            _, exit_receipt = validate_owned_references(session.storage, owned)
            session.write("owned-input-exit.json", exit_receipt)
            session.check()
            session.write("report.json", dict(version=VERSION, at=shared.now(), targets=matrix,
                source_forecast_freeze=spec["parent_forecast_freeze"], source_scored_freeze=spec["parent_scored_freeze"],
                original_FAILED_completion=spec["parent_FAILED_completion"], original_state="FAILED_CPU_LIMIT_UNCHANGED",
                reused_reports=list(REUSE), newly_aggregated_reports=list(REMAINING), blocked_exact_PPR_slots=6,
                artifact_bindings=dict(session.bindings), usage=dict(wall_seconds=time.monotonic()-session.start,
                    CPU_seconds=time.process_time()-session.cpu_start, new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0),
                evidence="EXPOSED_CHRONOLOGICAL_OOF_DEVELOPMENT_RECONSTRUCTION; no new observations or confirmation",
                startup="All22 original2022 CDF aliases retained in whole-policy primary",
                missing_comparators="Authentic historical raw Sleeper/SITE unavailable; N/A",
                scientific_qualification=False, release_ready=False, website_default_changed=False,
                retention=session.storage.report_retention()), freeze=False)
            state = "COMPLETED"
    except BaseException as error:
        session.write("REPORT_CONTINUATION_FAILURE.json", dict(state="FAILED", error_type=type(error).__name__,
            reason="SEPARATE_REPORT_FAILURE_NO_RETRY", parent_failure_preserved=True))
        raise
    finally:
        session.write("REPORT_CONTINUATION_FINISHED.json", dict(state=state,
            new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0,
            retention=session.storage.report_retention()), freeze=False)
