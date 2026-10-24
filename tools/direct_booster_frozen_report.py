"""One separately registered aggregation of immutable direct-screen scores.

The original experiment remains FAILED. This module has no feature, label,
model, fit, inference, or distribution-construction path. Existing statistical
helpers are imported from the original frozen code assembly by the caller.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import json
from pathlib import Path, PurePosixPath
import resource
import socket
import time
from unittest.mock import patch

import pandas as pd
from threadpoolctl import threadpool_limits

from nfl_lab import direct_booster_screen as original
from nfl_lab import source_matched_benchmark as shared
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.owned_reference_batch import validate_owned_references
from nfl_lab.reference_runtime import _deadline

VERSION = "direct-booster-report-recovery-v1-20261023"
POLICY_SHA256 = "7789249bdf56d7767ae87eea69184b0a1ea18d63db564e4fe4d1a83181b55e26"
LIMITS = dict(invocations=1,wall_seconds=600,CPU_seconds=600,
    combined_RSS_bytes=2147483648,numerical_threads=2,HTTP=0,
    fits_predictions_predictive_law_calls_source_label_reads=0,
    automatic_retries=0,new_retained_bytes=67108864,shared_retention_bytes=536870912)


def cap_output(storage,output):
    """64 MiB newly retained content cap before the unchanged global writer.

    Original retained CAS content remains free to alias in this namespace.
    Namespace-only content already imported at bootstrap (execution freeze and
    receipts) counts. The original 512 MiB global lock, peak-write quota,
    ownership and immutable writer remain in force.
    Only one worker writes during aggregation; supervisor writes after it exits.
    """
    original_write=storage.write_bytes
    digest_cache={}
    def namespace():
        inodes={}
        for file in output.rglob("*"):
            if file.is_symlink():
                raise ValueError("symlink in reporting namespace")
            if file.is_file():
                info=file.stat();key=(info.st_dev,info.st_ino)
                if key not in digest_cache:
                    digest_cache[key]=shared.sha(file)
                entry=inodes.setdefault(key,dict(bytes=info.st_size,links=info.st_nlink,
                    digest=digest_cache[key],aliases=0))
                entry["aliases"]+=1
        return list(inodes.values())
    baseline={p.name for p in storage.blob_root.iterdir() if p.is_file()}
    for entry in namespace():
        # One link is the CAS blob itself. No outside alias means this content
        # belongs to the newly created report namespace and is already charged.
        if entry["links"]==entry["aliases"]+1:
            baseline.discard(entry["digest"])
    admitted={}
    def retention():
        # Include every newly published CAS object, even if a later alias/write
        # failed. Reserved failed attempts remain charged for this invocation.
        retained={p.name:p.stat().st_size for p in storage.blob_root.iterdir()
            if p.is_file() and p.name not in baseline}
        pending={digest:size for digest,size in admitted.items() if digest not in retained and digest not in baseline}
        return dict(new_unique_CAS_bytes=sum(retained.values()),
            reserved_failed_or_inflight_bytes=sum(pending.values()),
            charged_bytes=sum(retained.values())+sum(pending.values()),limit_bytes=67108864,
            scope="All CAS content added after baseline, namespace-only bootstrap content, and unreleased attempted bodies; shared concurrent additions count conservatively")
    def write(path,body,*,replace=False):
        path=Path(path)
        if path.resolve()!=path.absolute() or output not in path.parents:
            raise ValueError("report writer escaped its separate namespace")
        digest=hashlib.sha256(body).hexdigest()
        charged=retention()["charged_bytes"]
        incoming=0 if digest in baseline or digest in admitted or (storage.blob_root/digest).exists() else len(body)
        if charged+incoming>67108864:
            raise RuntimeError("separate 64 MiB report retention budget exhausted before write")
        if digest not in baseline:
            admitted[digest]=len(body)
        return original_write(path,body,replace=replace)
    storage.write_bytes=write
    storage.report_retention=retention
    return storage


def relative(root, name):
    value = PurePosixPath(name)
    if (not name or value.is_absolute() or value.as_posix() != name or
            "\\" in name or any(part in {".", ".."} for part in value.parts)):
        raise ValueError("unsafe frozen relative path")
    path = root / name
    if path.resolve() != path.absolute() or root not in path.parents:
        raise ValueError("frozen reference escaped its namespace")
    return path


class Session:
    write = shared.Session.write
    frame = shared.Session.frame
    failure = shared.Session.failure

    def __init__(self, spec, *, start, cpu_start):
        self.spec, self.start, self.cpu_start = spec, start, cpu_start
        self.policy = json.loads(shared._spec(spec["source_policy"]).read_text())
        self.storage = OperationalStorage(spec["cache"], self.policy)
        self.output = self.storage.register_root(spec["output"])
        cap_output(self.storage,self.output)
        self.bindings = {}

    def check(self):
        if (time.monotonic() - self.start >= 598 or
                time.process_time() - self.cpu_start >= 598 or
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 >= 2147483648):
            raise RuntimeError("separate report-only resource budget exhausted")


@contextmanager
def no_science():
    """Fail closed if aggregation reaches a source/model execution route."""
    def forbidden(*args, **kwargs):
        raise AssertionError("report-only: fit/inference/law/source/network access forbidden")
    with shared.no_fits(), ExitStack() as stack:
        blocked = ((original, "run_screen"), (original, "report_screen"),
            (original.direct.DirectBoosterModel, "fit"),
            (original.direct.DirectBoosterModel, "predict"),
            (original.direct, "prediction_rows"),
            (shared, "read_partition"), (shared, "fold"),
            (shared, "_dataset"), (shared, "_outcomes"),
            (shared.models, "fit_predict"),
            (shared.operational_models, "fit_operational_reference"),
            (shared.operational_models, "predict_operational_artifact"),
            (shared.operational_sources, "_verify"),
            (socket.socket, "connect"), (socket.socket, "connect_ex"),
            (socket, "getaddrinfo"))
        for owner, name in blocked:
            stack.enter_context(patch.object(owner, name, forbidden))
        import joblib
        stack.enter_context(patch.object(joblib, "load", forbidden))
        yield


def metadata(spec):
    """Authenticate metadata only; scored parquet values remain unopened."""
    result = {name: json.loads(shared._spec(spec[name]).read_text()) for name in
        ("parent_config", "parent_execution_freeze", "parent_forecast_freeze",
         "parent_scored_freeze", "parent_completion", "control_scored_freeze",
         "category_contract")}
    parent, execution, forecast, scored, terminal = (result[name] for name in
        ("parent_config", "parent_execution_freeze", "parent_forecast_freeze",
         "parent_scored_freeze", "parent_completion"))
    if (terminal["state"] != "FAILED" or terminal["returncode"] != -9 or
            terminal["new_HTTP_attempts"] != 0 or terminal["threads"] != 2):
        raise ValueError("exact original terminal failure is required")
    if (execution["plan_sha256"] != spec["parent_config"]["sha256"] or
            forecast["registration_sha256"] != spec["parent_config"]["sha256"] or
            forecast["state"] != "GLOBAL_FORECASTS_FROZEN" or forecast["fatal"] is not None):
        raise ValueError("original global forecast provenance differs")
    if (parent["category_contract"] != spec["category_contract"] or
            parent["source_policy"] != spec["source_policy"] or
            parent["control_scored_freeze"] != spec["control_scored_freeze"] or
            parent["cache"] != spec["cache"] or parent["control_root"] != spec["control_root"]):
        raise ValueError("original scoring contracts, controls or cache changed")
    if (Path(spec["parent_root"]) != Path(parent["output"]) or
            Path(spec["parent_forecast_freeze"]["path"]) != Path(parent["output"])/"forecast-freeze.json" or
            Path(spec["parent_scored_freeze"]["path"]) != Path(parent["output"])/"scored-freeze.json" or
            Path(spec["parent_completion"]["path"]) != Path(parent["output"])/"screen-supervisor-completion.json"):
        raise ValueError("original receipt paths differ")
    categories = result["category_contract"]["categories"]
    if (set(categories) != set(shared.models.TARGETS) or
            categories["fantasy_ppr"]["state"] == "READY"):
        raise ValueError("all twelve categories with exact PPR blocked required")
    expected = original.planned_slots(categories, parent["versions"])
    slots = forecast["slots"]
    if len(slots) != 216 or len(expected) != 216 or len(scored["slots"]) != 192:
        raise ValueError("original complete 216-slot/192-scored inventory required")
    identity = lambda s: (s["year"], s["target"], s["method"])
    completed = {identity(s): s for s in scored["slots"]}
    if len(completed) != 192:
        raise ValueError("duplicate scored slot")
    for slot, planned in zip(slots, expected):
        if any(slot[k] != planned[k] for k in ("year", "target", "library", "complexity", "method")):
            raise ValueError("planned identities changed")
        key = identity(slot)
        if slot["target"] == "fantasy_ppr":
            if slot["state"] != "BLOCKED_EXACT_PPR" or key in completed:
                raise ValueError("original exact-PPR block changed")
        elif slot["library"] == "xgboost" and slot["target"] == "anytime_td":
            if slot["state"] != "FAILED" or slot.get("reason") != "ValueError" or key in completed:
                raise ValueError("original six native-simplex failures changed")
        else:
            done = completed.get(key)
            if not done or slot["state"] != "PREDICTION_FROZEN" or done["state"] != "COMPLETED":
                raise ValueError("original successful score missing")
            if any(done.get(k) != v for k, v in slot.items() if k != "state"):
                raise ValueError("scored slot differs from frozen forecast")
            name = f"private/scored/{slot['year']}/{slot['target']}/{slot['method']}.parquet"
            if done["scored"] != name or name not in scored["bindings"]:
                raise ValueError("exact frozen scored path missing")
    if sum(name.startswith("private/scored/") for name in scored["bindings"]) != 192:
        raise ValueError("extra or missing frozen scored file")
    if (forecast["usage"]["estimator_attempts"] != 198 or
            scored["usage"]["estimator_attempts"] != 198 or
            forecast["usage"]["query_prediction_or_law_row_incidences"] !=
            scored["usage"]["query_prediction_or_law_row_incidences"]):
        raise ValueError("original immutable fit/prediction counters differ")
    result["completed_slots"] = completed
    return result


def owned_inputs(spec, meta):
    parent, controls = Path(spec["parent_root"]), Path(spec["control_root"])
    owned = {spec[k]["path"]: spec[k]["sha256"] for k in
        ("parent_forecast_freeze", "parent_scored_freeze", "parent_completion", "control_scored_freeze")}
    scored, control = meta["parent_scored_freeze"], meta["control_scored_freeze"]
    for slot in scored["slots"]:
        name = slot["scored"]
        owned[str(relative(parent, name))] = scored["bindings"][name]
    for year in shared.YEARS:
        for target in shared.models.TARGETS:
            if target == "fantasy_ppr":
                continue
            for method in original.CONTROLS:
                name = f"private/scored/{year}/{target}/{method}/rows.parquet"
                if name not in control["scored_files"] or name not in control["bindings"]:
                    raise ValueError("exact original control binding missing")
                owned[str(relative(controls, name))] = control["bindings"][name]
    if len(owned) != 361:
        raise ValueError("exact 192 scored + 165 controls + four receipts required")
    return owned


def run(spec, *, plan_sha256, final_static):
    started, cpu_started = time.monotonic(), time.process_time()
    if spec["registration_id"] != VERSION or spec["state"] != "REGISTERED" or spec["budgets"] != LIMITS:
        raise ValueError("unregistered or changed report-only plan")
    meta = metadata(spec)
    parent = Path(spec["parent_root"])
    output = Path(spec["output"])
    controls = Path(spec["control_root"])
    if (output.resolve() != output.absolute() or any(output == x or output in x.parents or x in output.parents
            for x in (parent, controls))):
        raise ValueError("separate canonical report namespace required")
    session = Session(spec, start=started, cpu_start=cpu_started)
    if (session.output/"REPORT_CONSUMED.json").exists():
        raise RuntimeError("report-only invocation already consumed; no retry")
    session.write("REPORT_CONSUMED.json", dict(at=shared.now(), registration_sha256=plan_sha256,
        new_fits_predictions_law_calls_source_label_reads_HTTP=0))
    state = "FAILED"
    try:
        with _deadline(max(.001, 598-(time.monotonic()-started))), threadpool_limits(limits=2), no_science():
            final_static()
            owned = owned_inputs(spec, meta)
            session.authenticated_controls, receipt = validate_owned_references(session.storage, owned)
            session.control_freeze = meta["control_scored_freeze"]
            session.write("owned-input-entry.json", receipt)
            completed = meta["completed_slots"]
            report = dict(version=VERSION, at=shared.now(), evidence="EXPOSED_SOURCE_MATCHED_DEVELOPMENT",
                original_run_state="FAILED", historical_raw_Sleeper="UNAVAILABLE", historical_SITE="UNAVAILABLE",
                promotion="NONE", slots=[completed.get((s["year"],s["target"],s["method"]),s)
                    for s in meta["parent_forecast_freeze"]["slots"]], targets={})
            for target in shared.models.TARGETS:
                session.check()
                category = shared._category(meta["category_contract"]["categories"], target)
                selected = [s for s in completed.values() if s["target"] == target]
                if not selected:
                    item = dict(state="BLOCKED_EXACT_PPR" if target == "fantasy_ppr" else "NO_COMPLETED_FORECASTS")
                else:
                    frames = [pd.read_parquet(relative(parent,s["scored"])) for s in selected]
                    for slot, frame in zip(selected,frames):
                        if (len(frame) != slot["rows"] or not frame.method.eq(slot["method"]).all() or
                                not frame.target.eq(target).all() or not frame.season.eq(slot["year"]).all()):
                            raise ValueError("scored file dimensions/slot identities changed")
                    rows = pd.concat(frames, ignore_index=True)
                    control_rows = pd.concat([original._control(session,year,target,method,category)
                        for year in sorted(rows.season.unique()) for method in original.CONTROLS], ignore_index=True)
                    item, losses = original.target_report(rows,control_rows,category,session.check)
                    session.frame(f"private/paired-losses/{target}.parquet",losses)
                    session.frame(f"private/subgroups/{target}.parquet",original.subgroup_rows(rows,category))
                    del frames, rows, control_rows, losses
                report["targets"][target] = item
                session.write(f"private/target-reports/{target}.json",item)
                session.write(f"checkpoints/{target}.json",dict(at=shared.now(),target=target,state="REPORT_FROZEN"))
            final_static()
            metadata(spec)
            owned.update({str(session.output/name):sha for name,sha in session.bindings.items()})
            _, receipt = validate_owned_references(session.storage,owned)
            session.write("owned-input-exit.json",receipt)
            session.check()
            session.write("report.json",dict(report=report,at=shared.now(),registration_sha256=plan_sha256,
                original_completion_sha256=spec["parent_completion"]["sha256"],
                scored_freeze_sha256=spec["parent_scored_freeze"]["sha256"],
                original_run="FAILED; unchanged original budget and terminal receipt retained",
                original_resource_accounting=spec["original_resource_accounting"],
                new_fits_predictions_law_calls_source_label_reads_HTTP=0,
                original_consumed_estimator_attempts=198,
                original_consumed_query_prediction_or_law_row_incidences=
                    meta["parent_scored_freeze"]["usage"]["query_prediction_or_law_row_incidences"],
                promotion="NONE"),freeze=False)
            state="COMPLETED"
            return report
    except BaseException as error:
        session.failure("REPORT_FAILURE.json",error)
        raise
    finally:
        session.write("REPORT_FINISHED.json",dict(at=shared.now(),state=state,
            inner_wall_seconds=time.monotonic()-started,inner_CPU_seconds=time.process_time()-cpu_started,
            retention=session.storage.report_retention(),
            new_fits_predictions_law_calls_source_label_reads_HTTP=0),freeze=False)
