"""Two-target completion over immutable rows; nine exact report triplet aliases."""
from contextlib import contextmanager
import json
from pathlib import Path
import resource
import time
from unittest.mock import patch

import pandas as pd
from threadpoolctl import threadpool_limits
import baseline_correction_report_v2 as prior
from direct_xgboost_binary_recovery import process_free_threads
from nfl_lab.owned_reference_batch import validate_owned_references
from nfl_lab.reference_runtime import _deadline
from compact_report_contract_v3 import compact_reference

VERSION = "baseline-correction-report-v3-20261023"
POLICY_SHA256 = "d0421bec77493eb9aa884c9ba89163129abec572ec633d8ac12902c974198eb0"
REUSE = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd", "rush_att", "rec", "rec_yd")
REMAINING = ("rush_rec_yd", "anytime_td")
parent, shared, relative = prior.parent, prior.shared, prior.relative
storage = prior.storage


def report_partition(categories):
    if (set(categories) != set(REUSE + REMAINING + ("fantasy_ppr",))
            or categories["fantasy_ppr"]["state"] == "READY"
            or any(categories[target]["state"] != "READY" for target in REUSE + REMAINING)):
        raise ValueError("exact nine reused/two unfinished/PPR blocked required")
    return {target: "REUSE_EXACT_BYTES" if target in REUSE else "AGGREGATE_FROZEN_ROWS" if target in REMAINING
        else "BLOCKED_EXACT_PPR" for target in shared.models.TARGETS}


def decode_paths(spec, scored):
    allowed = {str(relative(Path(spec["parent_root"]), slot["scored"]))
        for slot in scored["slots"] if slot["target"] in REMAINING}
    allowed |= {str(relative(Path(spec["control_root"]),
        f"private/scored/{year}/{target}/{method}/rows.parquet"))
        for year in shared.YEARS for target in REMAINING for method in parent.CONTROLS}
    if len(allowed) != 42:
        raise ValueError("exact twelve frozen candidates/thirty controls required")
    return allowed


@contextmanager
def frozen_reads_only(spec, scored):
    allowed = decode_paths(spec, scored)
    original = pd.read_parquet
    def read(path, *args, **kwargs):
        if str(path) not in allowed:
            raise AssertionError("V3 forbids source/query/model/reused-target semantic reads")
        return original(path, *args, **kwargs)
    with patch.object(pd, "read_parquet", read):
        yield


def failed_contract(supervisor, failure, finished):
    if (supervisor["state"] != "FAILED" or supervisor["returncode"] != 1
            or supervisor["new_fits_inference_scoring_labeljoins_raw_model_law_HTTP"] != 0
            or failure["state"] != "FAILED" or failure["error_type"] != "RuntimeError"
            or failure["reason"] != "SEPARATE_REPORT_FAILURE_NO_RETRY"
            or failure["parent_failure_preserved"] is not True or finished["state"] != "FAILED"
            or finished["new_fits_inference_scoring_labeljoins_raw_model_law_HTTP"] != 0):
        raise ValueError("both predecessor failures must remain exact and unresolved")


class Session(prior.Session):
    def check(self):
        if (time.monotonic() - self.start >= 290 or time.process_time() - self.cpu_start >= 290
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 >= 1073741824):
            raise RuntimeError("V3 finalization resource reserve exhausted")


def metadata(spec):
    inherited = spec["_inherited_execution"]
    original_spec = inherited["execution_metadata"]
    meta, owned = prior.metadata(original_spec)  # Original full66/165/source contracts unchanged.
    for key in ("cache", "control_root", "source_policy", "loaded_libc"):
        if spec[key] != original_spec[key]:
            raise ValueError("V3 changed an original operational contract:" + key)
    if spec["reused_targets"] != list(REUSE) or spec["remaining_targets"] != list(REMAINING):
        raise ValueError("exact nine/two partition required")
    if spec["methods"] != original_spec["methods"]:
        raise ValueError("original two arms changed")
    categories = meta["category_contract"]["categories"]
    report_partition(categories)
    proofs = {key: json.loads(shared._spec(spec[key]).read_text()) for key in (
        "V2_failed_supervisor", "V2_worker_failure", "V2_worker_finished")}
    failed_contract(proofs["V2_failed_supervisor"], proofs["V2_worker_failure"], proofs["V2_worker_finished"])
    owned.update({spec[key]["path"]: spec[key]["sha256"] for key in (
        "inherited_execution", "V2_failed_supervisor", "V2_worker_failure", "V2_worker_finished", "V2_failed_log")})
    if set(spec["completed_outputs"]) != set(REUSE):
        raise ValueError("all nine complete report triplets required")
    old_root = Path(spec["inherited_execution"]["path"]).parent
    for target, files in spec["completed_outputs"].items():
        if set(files) != {"report", "pairs", "subgroups"}:
            raise ValueError("all completed triplet members required")
        for key, name in (("report", f"target-reports/{target}.json"),
                ("pairs", f"private/paired-losses/{target}.parquet"), ("subgroups", f"private/subgroups/{target}.parquet")):
            if files[key]["path"] != str(relative(old_root, name)):
                raise ValueError("completed target escaped immutable V2 namespace")
            owned[files[key]["path"]] = files[key]["sha256"]
    return meta, owned


def reuse_target(session, target, files):
    if target not in REUSE:
        raise ValueError("unregistered reused target")
    for kind, name in (("report", f"target-reports/{target}.json"),
            ("pairs", f"private/paired-losses/{target}.parquet"), ("subgroups", f"private/subgroups/{target}.parquet")):
        source = files[kind]
        if session.authenticated_controls.get(source["path"], {}).get("sha256") != source["sha256"]:
            raise ValueError("byte-reused output not authenticated/owned")
        session.storage.import_file(source["path"], session.output/name, expected_sha256=source["sha256"])
        session.bindings[name] = source["sha256"]
    report = json.loads(Path(files["report"]["path"]).read_text())
    if report["target"] != target:
        raise ValueError("reused report target differs")
    return report


def run(spec, *, plan_sha256, final_static):
    if plan_sha256 != POLICY_SHA256 or spec["registration_id"] != VERSION:
        raise ValueError("separate compact reporting policy required")
    # Preserve the original scientific data root; never read candidate rows from
    # the failed reporting namespace or invent a replacement score artifact.
    spec = dict(spec, parent_root=spec["_inherited_execution"]["execution_metadata"]["parent_root"])
    session = Session(spec)
    if (session.output/"REPORT_V3_CONSUMED.json").exists():
        raise RuntimeError("one V3 invocation consumed; no retry")
    session.write("REPORT_V3_CONSUMED.json", dict(at=shared.now(), registration_sha256=plan_sha256,
        new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0))
    state = "FAILED"
    try:
        with _deadline(290), process_free_threads(spec["loaded_libc"]), threadpool_limits(limits=2), prior.report_only():
            meta, owned = metadata(spec)
            session.authenticated_controls, entry = validate_owned_references(session.storage, owned)
            session.control_freeze = meta["control_scored_freeze"]
            session.write("owned-input-entry.json", entry)
            session.write("report-work-plan.json", report_partition(meta["category_contract"]["categories"]))
            matrix = []
            with frozen_reads_only(spec, meta["parent_scored_freeze"]):
                for target in shared.models.TARGETS:
                    session.check()
                    if target == "fantasy_ppr": report = None
                    elif target in REUSE: report = reuse_target(session, target, spec["completed_outputs"][target])
                    else:
                        category = shared._category(meta["category_contract"]["categories"], target)
                        report = prior.aggregate_target(session, target, category, meta["parent_scored_freeze"]["slots"])
                    record = prior.matrix_record(session, target, report)
                    if target in REUSE: record["state"] = "BYTE_REUSED_COMPLETE_V2"
                    matrix.append(record)
            final_static(); metadata(spec)
            owned.update({str(session.output/name): digest for name, digest in session.bindings.items()})
            _, exit_receipt = validate_owned_references(session.storage, owned)
            session.write("owned-input-exit.json", exit_receipt)
            session.check()
            session.write("report.json", dict(version=VERSION, at=shared.now(), targets=matrix,
                inherited_execution=spec["inherited_execution"], original_science_state="FAILED_CPU_LIMIT_UNCHANGED",
                previous_report_state="FAILED_RETENTION_ADMISSION_UNCHANGED", previous_report_supervisor=spec["V2_failed_supervisor"],
                source_forecast_freeze=spec["_inherited_execution"]["execution_metadata"]["parent_forecast_freeze"],
                source_scored_freeze=spec["_inherited_execution"]["execution_metadata"]["parent_scored_freeze"],
                reused_reports=list(REUSE), newly_aggregated_reports=list(REMAINING), blocked_exact_PPR_slots=6,
                artifact_bindings=dict(session.bindings), usage=dict(wall_seconds=time.monotonic()-session.start,
                    CPU_seconds=time.process_time()-session.cpu_start, new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0),
                evidence="EXPOSED_CHRONOLOGICAL_OOF_DEVELOPMENT_RECONSTRUCTION; no new observations or confirmation",
                missing_comparators="Authentic historical raw Sleeper/SITE unavailable; N/A",
                scientific_qualification=False, release_ready=False, website_default_changed=False,
                retention=session.storage.report_retention()), freeze=False)
            state = "COMPLETED"
    except BaseException as error:
        session.write("REPORT_V3_FAILURE.json", dict(state="FAILED", error_type=type(error).__name__,
            reason="V3_FAILURE_NO_RETRY", both_previous_failures_preserved=True))
        raise
    finally:
        session.write("REPORT_V3_FINISHED.json", dict(state=state, new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0,
            retention=session.storage.report_retention()), freeze=False)
