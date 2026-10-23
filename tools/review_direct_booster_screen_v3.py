"""One sealed, read-only arithmetic audit; no model import, fit or inference.

Prepared without reading NFL values. Invoked only after the original run's
report-continuation COMPLETE/runtime/outer and original FAILED receipts have
been sealed by the root. Original V1 is uninvoked; consumed V2 remains failed.
V3 removes only a controller that attempted forbidden process creation; pure
NumPy reductions retain the two-thread environment and nonparallel Arrow reads.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time

START = time.monotonic()
CPU_START = time.process_time()
KEYS = ["season", "week", "game_id", "player_id"]
CONTEXT = ["position", "team", "opponent", "kickoff_utc", "cutoff_utc"]
FIELDS = KEYS + CONTEXT + ["target", "method", "point", "probability", "mean", "actual", "primary_role", "participation_state", "outcome_state", "fallback", "history_state"]
YEARS = [2022, 2023, 2024]
CONTROLS = ["leaf_cdf", "count_A", "role_B", "recent", "pooled"]
CHECKS = Counter()
ERRORS = []


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checktime():
    require(time.monotonic() - START < 178, "registered wall budget exhausted")
    require(time.process_time() - CPU_START < 178, "registered CPU budget exhausted")


def filepin(item):
    path = Path(item["path"])
    require(path.is_absolute() and path.resolve(strict=True) == path, "noncanonical exact binding")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), "binding is not regular file")
    require(info.st_size == item["bytes"] and digest(path) == item["sha256"], "bound bytes changed: " + str(path))
    if "inode" in item:
        require([info.st_dev, info.st_ino] == item["inode"], "bound inode changed")
    if "mode" in item:
        require(oct(info.st_mode) == item["mode"], "bound mode changed")
    CHECKS["exact_file_bindings"] += 1


def compare(actual, expected, label):
    """Arithmetic tolerance only; identity/support/probability bounds stay exact."""
    CHECKS["comparison_fields"] += 1
    if isinstance(expected, dict):
        require(isinstance(actual, dict), label + ": object missing")
        for key, value in expected.items():
            require(key in actual, label + ": missing " + key)
            compare(actual[key], value, label + "/" + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), label + ": list differs")
        for index, value in enumerate(expected):
            compare(actual[index], value, label + "/" + str(index))
    elif expected is None or isinstance(expected, (str, bool)):
        require(actual == expected, label + ": value differs")
    elif isinstance(expected, (int, float)):
        require(isinstance(actual, (int, float)) and not isinstance(actual, bool), label + ": numeric missing")
        if isinstance(expected, int):
            require(actual == expected, label + ": count differs")
        else:
            require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-10), label + ": arithmetic differs")
    else:
        raise TypeError("unsupported check type")


def numeric(frame, column):
    return pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)


def support_mask(values, support):
    mask = np.isfinite(values) & (values == np.floor(values))
    return mask & ((values == 0) | (values == 1)) if support == "bernoulli" else mask & (values >= 0) if support == "count" else mask


def metrics(prediction, actual):
    error = prediction - actual
    absolute = np.abs(error)
    if len(error) == 0:
        return {key: (0 if key == "rows" else None) for key in ["rows", "mae", "mse", "rmse", "bias_prediction_minus_actual", "absolute_error_p90", "absolute_error_p95", "absolute_error_max", "fraction_absolute_error_ge5", "fraction_absolute_error_ge50"]}
    return dict(rows=len(error), mae=float(absolute.mean()), mse=float(np.mean(error ** 2)),
        rmse=float(np.sqrt(np.mean(error ** 2))), bias_prediction_minus_actual=float(error.mean()),
        absolute_error_p90=float(np.quantile(absolute, .9)), absolute_error_p95=float(np.quantile(absolute, .95)),
        absolute_error_max=float(absolute.max()), fraction_absolute_error_ge5=float(np.mean(absolute >= 5)),
        fraction_absolute_error_ge50=float(np.mean(absolute >= 50)))


def logs(probability, actual):
    require(np.isfinite(probability).all() and ((probability >= 0) & (probability <= 1)).all(), "invalid Bernoulli probability")
    with np.errstate(divide="ignore", invalid="ignore"):
        loss = -np.where(actual == 1, np.log(probability), np.log1p(-probability))
    finite = np.isfinite(loss)
    infinite = int(np.isposinf(loss).sum())
    return dict(rows=len(loss), natural_log_loss=float(loss.mean()) if len(loss) and not infinite else None,
        log_loss_state="positive_infinity" if infinite else "finite" if len(loss) else "unavailable",
        infinite_log_losses=infinite, finite_log_loss_sum=float(loss[finite].sum()), finite_log_loss_count=int(finite.sum()), probability_clipping="none")


def reliability(probability, actual):
    bins = np.minimum((probability * 10).astype(int), 9)
    return [dict(bin=index, lower_inclusive=index / 10, upper=(index + 1) / 10,
        upper_inclusive=index == 9, rows=int((bins == index).sum()),
        mean_probability=float(probability[bins == index].mean()) if (bins == index).any() else None,
        observed_rate=float(actual[bins == index].mean()) if (bins == index).any() else None) for index in range(10)]


def readframe(path, category, method, *, forecast=False):
    frame = pd.read_parquet(path, columns=FIELDS if not forecast else [c for c in FIELDS if c not in {"history_state"}], use_threads=False)
    require(not frame[KEYS].isna().any(axis=None) and not frame.duplicated(KEYS).any(), "null/duplicate identity")
    require(frame.target.eq(category["target"]).all() and frame.method.eq(method).all(), "target/method differs")
    require(frame.primary_role.eq(frame.position.isin(category["primary_roles"])).all(), "primary role changed")
    require(frame.participation_state.isin(["unread"] if forecast else ["played", "DNP", "unknown"]).all(), "participation state differs")
    for column in ["kickoff_utc", "cutoff_utc"]:
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="raise")
    require(not frame["cutoff_utc"].isna().any() and not frame["kickoff_utc"].isna().any(), "missing clocks")
    require(frame.cutoff_utc.le(frame.kickoff_utc).all(), "cutoff after kickoff")
    point, probability = numeric(frame, "point"), numeric(frame, "probability")
    require(not np.isinf(point).any(), "infinite point")
    if category["support"] == "count":
        require(not (point < 0).any() and not np.isfinite(probability).any(), "count support/product changed")
    elif category["support"] == "bernoulli":
        require(not (np.isfinite(point) & ((point < 0) | (point > 1))).any() and np.array_equal(point, probability, equal_nan=True), "binary product changed")
    else:
        require(not np.isfinite(probability).any(), "numeric probability invented")
    return frame.sort_values(KEYS, kind="stable").reset_index(drop=True)


def samecontext(a, b, *, outcomes=True):
    require(len(a) == len(b) and all(a[column].eq(b[column]).all() for column in KEYS + CONTEXT + ["primary_role"]), "identity/context/role masks differ")
    if outcomes:
        require(np.array_equal(numeric(a, "actual"), numeric(b, "actual"), equal_nan=True), "actuals differ")
        require(a.participation_state.equals(b.participation_state), "participation differs")
    CHECKS["aligned_row_populations"] += 1


def summarize(frame, category):
    y, point = numeric(frame, "actual"), numeric(frame, "point")
    mask = frame.participation_state.eq("played").to_numpy() & support_mask(y, category["support"]) & np.isfinite(point)
    out = dict(offered_rows=len(frame), scored_rows=int(mask.sum()), missing_points=int((~np.isfinite(point)).sum()),
        outcome_states=frame.outcome_state.value_counts(dropna=False).to_dict(), point_metrics=metrics(point[mask], y[mask]),
        players=int(frame.loc[mask, "player_id"].nunique()), games=int(frame.loc[mask, "game_id"].nunique()),
        weeks=len(frame.loc[mask, ["season", "week"]].drop_duplicates()), fallback_reasons=frame.fallback.fillna("").value_counts().to_dict())
    if category["support"] == "bernoulli":
        out.update(brier=float(np.mean((point[mask] - y[mask]) ** 2)) if mask.any() else None,
            **logs(point[mask], y[mask]), reliability_deciles=reliability(point[mask], y[mask]))
    return out


def paired(a, b, category, primary):
    y, pa, pb = numeric(a, "actual"), numeric(a, "point"), numeric(b, "point")
    observed = a.participation_state.eq("played").to_numpy() & support_mask(y, category["support"])
    mask = observed & np.isfinite(pa) & np.isfinite(pb)
    if primary:
        mask &= a.primary_role.to_numpy()
    squared = category["support"] in {"count", "bernoulli"}
    la = (pa[mask] - y[mask]) ** 2 if squared else np.abs(pa[mask] - y[mask])
    lb = (pb[mask] - y[mask]) ** 2 if squared else np.abs(pb[mask] - y[mask])
    ac, bc = (float(loss.mean()) if len(loss) else None for loss in (la, lb))
    out = dict(offered_rows=len(a), supported_played_rows=int(observed.sum()), paired_rows=int(mask.sum()),
        candidate_missing_rows=int((observed & ~np.isfinite(pa)).sum()), control_missing_rows=int((observed & ~np.isfinite(pb)).sum()),
        primary_loss="mse" if category["support"] == "count" else "brier" if squared else "mae",
        candidate_loss=ac, control_loss=bc, improvement_pct=100 * (bc - ac) / bc if bc not in (None, 0) else None,
        candidate_point_metrics=metrics(pa[mask], y[mask]), control_literal_point_metrics=metrics(pb[mask], y[mask]),
        games=int(a.loc[mask, "game_id"].nunique()), weeks=len(a.loc[mask, ["season", "week"]].drop_duplicates()),
        forecast_finite_masks_equal=bool(np.array_equal(np.isfinite(pa), np.isfinite(pb))))
    # Count reporter subtracts aggregate means; other products average deltas.
    out["delta_candidate_minus_control"] = ac - bc if category["support"] == "count" and ac is not None else float((la - lb).mean()) if len(la) else None
    if category["support"] == "bernoulli":
        out["paired_binary"] = dict(candidate=logs(pa[mask], y[mask]), control=logs(pb[mask], y[mask]),
            candidate_reliability_deciles=reliability(pa[mask], y[mask]), control_reliability_deciles=reliability(pb[mask], y[mask]))
    return out, mask, la, lb


def interval_metadata(actual, frame, mask, cluster):
    keys = ["season", "week"] if cluster == "week" else ["season", "game_id"]
    clusters = len(frame.loc[mask, keys].drop_duplicates())
    expected = dict(cluster=cluster, paired_rows=int(mask.sum()), clusters=clusters,
        state="DESCRIPTIVE" if clusters >= 8 else "N/A", replicates=500, seed=1703,
        generator="PCG64", percentile_method="linear", level=.95)
    compare(actual, expected, "bootstrap_metadata")
    if clusters >= 8:
        bounds = actual["interval"]
        require(isinstance(bounds, list) and len(bounds) == 2 and all(isinstance(x, (float, int)) and math.isfinite(x) for x in bounds) and bounds[0] <= bounds[1], "invalid bootstrap interval")
    else:
        require(actual["interval"] is None, "small-cluster interval should be unavailable")
    CHECKS["bootstrap_membership_config_only_no_resample"] += 1


def nominations(report):
    """Independent fixed-rule evaluation, with no learned thresholds."""
    output = []
    for method in sorted({p["candidate"] for p in report["pairs"]}):
        reasons = []
        for control in ["leaf_cdf", "role_B"]:
            rows = [p for p in report["pairs"] if p["candidate"] == method and p["comparator"] == control and p["population"] == "primary_roles"]
            pooled = next((p for p in rows if p["period"] == "pooled_2022_2024"), None)
            finite = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            if pooled is None or pooled.get("missing_required_years"):
                reasons.append(control + ":missing_required_years")
                continue
            if not all(finite(pooled[key]) for key in ["improvement_pct", "candidate_loss", "control_loss"]) or pooled["improvement_pct"] < 2:
                reasons.append(control + ":less_than_2pct_primary_gain")
            if not pooled["forecast_finite_masks_equal"]:
                reasons.append(control + ":forecast_coverage_changed")
            for metric in ["bias_prediction_minus_actual", "absolute_error_p95"]:
                pa, pb = pooled["candidate_point_metrics"][metric], pooled["control_literal_point_metrics"][metric]
                if not finite(pa) or not finite(pb) or abs(pa) > 1.02 * abs(pb):
                    reasons.append(control + ":secondary_regression:" + metric)
            annual = [p for p in rows if p["period"] in YEARS]
            if {p["period"] for p in annual} != set(YEARS):
                reasons.append(control + ":missing_annual_cell")
            for cell in annual:
                pa, pb = cell["candidate_loss"], cell["control_loss"]
                if not finite(pa) or not finite(pb) or pa > 1.05 * pb:
                    reasons.append(control + ":annual_regression:" + str(cell["period"]))
        output.append(dict(method=method, decision="NOT_NOMINATED" if reasons else "DEVELOPMENT_LEAD_REQUIRES_LATER_CONFIRMATION",
            reasons=reasons, scientific_qualification=False, release_ready=False))
    return output


def run(packet):
    config = json.loads(Path(packet["config_path"]).read_text())
    root = Path(packet["screen_output"])
    report_root = Path(packet["report_output"])
    require(root == Path(config["output"]), "different original output")
    policy = json.loads(Path(packet["policy_path"]).read_text())
    require(policy["budgets"]["invocations"] == 1 and policy["budgets"]["fits_inference_source_acquisition_HTTP"] == 0, "wrong finite reviewer policy")
    for pin in packet["bindings"]:
        filepin(pin)
    # The final runner completion is metadata only; exact expected objects and
    # their field names are supplied by root's finished-packet seal.
    for key in ["runtime_path", "outer_path", "original_failed_path"]:
        require(Path(packet[key]).is_file(), "original completion missing")
    require(json.loads(Path(packet["original_failed_path"]).read_text())["state"] == "FAILED", "original failure not retained")
    require(json.loads(Path(packet["outer_path"]).read_text())["state"] == "COMPLETED", "reporting continuation not complete")
    require(json.loads(Path(packet["runtime_path"]).read_text())["state"] == "COMPLETED", "reporting runtime not complete")
    final = json.loads(Path(packet["report_path"]).read_text())
    report = final["report"]
    require(report["historical_raw_Sleeper"] == "UNAVAILABLE" and report["historical_SITE"] == "UNAVAILABLE" and report["promotion"] == "NONE", "evidence/status misrepresented")
    require(report["evidence"] == "EXPOSED_SOURCE_MATCHED_DEVELOPMENT", "exposed data relabeled")
    globalfreeze = json.loads((root / "forecast-freeze.json").read_text())
    scoredfreeze = json.loads((root / "scored-freeze.json").read_text())
    require(globalfreeze["state"] == "GLOBAL_FORECASTS_FROZEN" and globalfreeze["fatal"] is None, "original global freeze invalid")
    require(len(globalfreeze["slots"]) == 216 and len(scoredfreeze["slots"]) == 192, "planned/scored slots differ")
    require(Counter(slot["state"] for slot in globalfreeze["slots"]) == Counter(PREDICTION_FROZEN=192, FAILED=6, BLOCKED_EXACT_PPR=18), "original failed/blocked slots lost")
    require(Counter(slot["state"] for slot in report["slots"]) == Counter(COMPLETED=192, FAILED=6, BLOCKED_EXACT_PPR=18), "report failed/blocked slots lost")
    slotkey = lambda slot: (slot["year"], slot["target"], slot["method"])
    original_slots = {slotkey(slot): slot for slot in globalfreeze["slots"]}
    final_slots = {slotkey(slot): slot for slot in report["slots"]}
    scored_slots = {slotkey(slot): slot for slot in scoredfreeze["slots"]}
    require(len(original_slots) == len(final_slots) == 216 and len(scored_slots) == 192 and original_slots.keys() == final_slots.keys(), "duplicate or changed slot identity")
    for identity, original_slot in original_slots.items():
        final_slot = final_slots[identity]
        if original_slot["state"] == "PREDICTION_FROZEN":
            require(identity in scored_slots and final_slot == scored_slots[identity], "completed report slot differs")
            require(all(scored_slots[identity].get(key) == value for key, value in original_slot.items() if key != "state"), "scored slot changed frozen metadata")
        else:
            require(final_slot == original_slot and identity not in scored_slots, "failed/blocked slot overwritten")
        CHECKS["preserved_slot_identities"] += 1
    require(final["scored_freeze_sha256"] == digest(root / "scored-freeze.json"), "report scored freeze differs")
    require(final["original_completion_sha256"] == digest(packet["original_failed_path"]), "report original FAILED identity differs")
    require(final["new_fits_predictions_law_calls_source_label_reads_HTTP"] == 0 and final["original_consumed_estimator_attempts"] == 198, "report work counters differ")
    oldfreeze = json.loads(Path(config["control_scored_freeze"]["path"]).read_text())
    category_file = Path(config["category_contract"]["path"])
    categories = json.loads(category_file.read_text())["categories"]
    require(len(categories) == 12 and categories["fantasy_ppr"]["state"] != "READY", "exact PPR contract changed")
    owned = {}
    for freeze in [globalfreeze, scoredfreeze]:
        for relative, checksum in freeze["bindings"].items():
            path = root / relative
            require(path.resolve() == path and root in path.parents, "unsafe frozen path")
            if str(path) in owned:
                require(owned[str(path)] == checksum, "inconsistent freeze binding")
            owned[str(path)] = checksum
    for year in YEARS:
        for target, category in categories.items():
            if category["state"] != "READY":
                continue
            for control in CONTROLS:
                relative = f"private/scored/{year}/{target}/{control}/rows.parquet"
                require(relative in oldfreeze["scored_files"], "original control missing")
                owned[str(Path(config["control_root"]) / relative)] = oldfreeze["bindings"][relative]
    # Sealed completion/report/new paired-loss sidecars are CAS references too.
    pinned_owned_paths = {pin["path"] for pin in packet["owned_bindings"]}
    required_sidecars = {str(report_root / f"private/{folder}/{target}.parquet")
        for target, category in categories.items() if category["state"] == "READY"
        for folder in ["paired-losses", "subgroups"]}
    require(required_sidecars <= pinned_owned_paths, "all paired-loss and subgroup sidecars must be sealed before reading")
    for pin in packet["owned_bindings"]:
        owned[pin["path"]] = pin["sha256"]
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab.owned_reference_batch import validate_owned_references
    storage = OperationalStorage(config["cache"], json.loads(Path(config["source_policy"]["path"]).read_text()))
    _, entry = validate_owned_references(storage, owned)
    CHECKS["owned_reference_bindings"] = len(owned)
    require(set(report["targets"]) == set(categories), "twelve-category report changed")
    aggregate = []
    for target, category in categories.items():
        checktime()
        target_report = report["targets"][target]
        if category["state"] != "READY":
            require(target == "fantasy_ppr" and target_report["state"] == "BLOCKED_EXACT_PPR", "unsupported category fabricated")
            continue
        methods = sorted({slot["method"] for slot in scoredfreeze["slots"] if slot["target"] == target})
        frames, controls = {}, {}
        for method in methods:
            pieces = []
            for slot in scoredfreeze["slots"]:
                if slot["target"] != target or slot["method"] != method:
                    continue
                scored = readframe(root / slot["scored"], category, method)
                frozen = readframe(root / slot["forecast"], category, method, forecast=True)
                samecontext(scored, frozen, outcomes=False)
                for column in ["point", "probability", "mean"]:
                    require(np.array_equal(numeric(scored, column), numeric(frozen, column), equal_nan=True), "score phase changed frozen forecast")
                require(not np.isfinite(numeric(frozen, "actual")).any() and frozen.outcome_state.eq("unread").all(), "frozen forecast has evaluation values")
                pieces.append(scored)
                CHECKS["forecast_to_scored_cells"] += 1
            frames[method] = pd.concat(pieces, ignore_index=True).sort_values(KEYS, kind="stable").reset_index(drop=True)
        reference = next(iter(frames.values()))
        for frame in frames.values():
            samecontext(reference, frame)
        for control in CONTROLS:
            pieces = []
            for year in YEARS:
                old = readframe(Path(config["control_root"]) / f"private/scored/{year}/{target}/{control}/rows.parquet", category, control)
                if control == "leaf_cdf" and category["support"] == "count":
                    old["point"] = numeric(old, "mean")
                pieces.append(old)
            controls[control] = pd.concat(pieces, ignore_index=True).sort_values(KEYS, kind="stable").reset_index(drop=True)
            samecontext(reference, controls[control])
        summary_index = {(cell["method"], cell["period"], cell["population"]): cell for cell in target_report["summaries"]}
        pair_index = {(cell["candidate"], cell["comparator"], cell["period"], cell["population"]): cell for cell in target_report["pairs"]}
        require(len(summary_index) == len(methods) * 8 and len(pair_index) == len(methods) * 40, "duplicate/missing report cells")
        # Pooled private losses are deliberately verified without resampling.
        saved_losses = pd.read_parquet(report_root / f"private/paired-losses/{target}.parquet", use_threads=False)
        require(not saved_losses.duplicated(KEYS + ["candidate", "comparator"]).any(), "duplicate private paired loss")
        grouped_losses = {(str(a), str(b)): frame.sort_values(KEYS, kind="stable").reset_index(drop=True)
            for (a, b), frame in saved_losses.groupby(["candidate", "comparator"], observed=True, sort=False)}
        require(set(grouped_losses) == {(a, b) for a in methods for b in CONTROLS}, "private paired-loss cells missing")
        for method, whole in frames.items():
            for period in [*YEARS, "pooled_2022_2024"]:
                checktime()
                choose = np.ones(len(whole), dtype=bool) if isinstance(period, str) else whole.season.eq(period).to_numpy()
                frame = whole.loc[choose].reset_index(drop=True)
                years = sorted(int(x) for x in frame.season.unique())
                missing = sorted(set(YEARS) - set(years)) if isinstance(period, str) else []
                for primary in [False, True]:
                    population = "primary_roles" if primary else "all_offered"
                    common = dict(included_years=years, missing_required_years=missing,
                        completion="PARTIAL_REQUIRED_YEARS" if missing else "COMPLETE_REQUIRED_YEARS" if isinstance(period, str) else "ANNUAL")
                    subset = frame.loc[frame.primary_role].reset_index(drop=True) if primary else frame
                    compare(summary_index[(method, period, population)], {**summarize(subset, category), **common}, "summary/" + target)
                    CHECKS["summary_cells"] += 1
                    for control, oldwhole in controls.items():
                        old = oldwhole.loc[choose].reset_index(drop=True)
                        expected, mask, la, lb = paired(frame, old, category, primary)
                        actual = pair_index[(method, control, period, population)]
                        compare(actual, {**expected, **common}, "pair/" + target)
                        CHECKS["paired_cells"] += 1
                        if isinstance(period, str):
                            interval_metadata(actual["week_interval"], frame, mask, "week")
                            interval_metadata(actual["game_interval"], frame, mask, "game")
                            if not primary:
                                saved = grouped_losses[(method, control)]
                                require(len(saved) == len(frame) and all(saved[column].eq(frame[column]).all() for column in KEYS), "private loss identities differ")
                                require(np.array_equal(saved.primary_role.to_numpy(), frame.primary_role.to_numpy()) and np.array_equal(saved.paired_eligible.to_numpy(), mask), "private loss eligibility differs")
                                for column, values in [("candidate_loss", la), ("control_loss", lb), ("delta_candidate_minus_control", la - lb)]:
                                    column_values = numeric(saved, column)
                                    require(np.isnan(column_values[~mask]).all() and np.allclose(column_values[mask], values, rtol=1e-12, atol=1e-12), "private paired arithmetic differs")
                                CHECKS["private_paired_loss_groups"] += 1
                        if primary and period == "pooled_2022_2024" and control in ["leaf_cdf", "role_B"]:
                            aggregate.append(dict(target=target, method=method, comparator=control, **expected))
        compare(target_report["research_nominations"], nominations(target_report), "research_nominations/" + target)
        CHECKS["category_nomination_lists"] += 1
        del saved_losses, grouped_losses, frames, controls
    _, exit_receipt = validate_owned_references(storage, owned)
    for pin in packet["bindings"]:
        filepin(pin)
    checktime()
    return dict(state="PASS_FROZEN_CACHED_ROW_ARITHMETIC_ONLY", new_football_observations=0,
        fits=0, predictions_inference_lawcalls=0, HTTP=0, requested_model="GPT-6.1 Sol Extra High",
        actual_backend_attestation="Unavailable; not claimed", original_failed_binary_cells=6,
        exact_PPR_blocked_slots=18, historical_SITE_raw="UNAVAILABLE", checks=dict(CHECKS),
        limitations=["Same exposed 2022-2024 outcomes; no new confirmation", "Original source timing and participation limitations retained", "Bootstrap parameters and cluster membership checked; intervals not resampled", "Private subgroup files authenticated; subgroup metrics not independently recomputed"],
        entry=entry, exit=exit_receipt, paired_primary_aggregates=aggregate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    require(digest(args.freeze) == args.sha256, "root sealed review freeze changed")
    packet = json.loads(Path(args.freeze).read_text())
    require(packet["state"] == "SEALED_REVIEW_READY" and packet["seal"]["integrator"] == "/root", "root review seal missing")
    require(packet["seal"]["reporting_continuation_complete"] is True, "reporting continuation still pending")
    # Pinned imports only after exact packet authentication. No model imported.
    sys.path.insert(0, packet["code_root"])
    # The separately frozen supervisor has already armed a 170s worker alarm,
    # a combined-CPU stop and a Linux orphan guard. Do not reset its clocks.
    def deny(event, args):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.fork"}:
            raise RuntimeError("review permits no network or child process")
    sys.addaudithook(deny)
    global np, pd
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(2)
    pa.set_io_thread_count(2)
    output = Path(packet["review_output"])
    require(not output.exists(), "review already invoked/output exists")
    from nfl_lab.operational_storage import OperationalStorage
    config = json.loads(Path(packet["config_path"]).read_text())
    storage = OperationalStorage(config["cache"], json.loads(Path(config["source_policy"]["path"]).read_text()))
    storage.write_bytes(output / "REVIEW_CONSUMED.json", (json.dumps({"freeze_sha256": args.sha256, "at_monotonic": START}) + "\n").encode())
    try:
        receipt = run(packet)
    except BaseException as error:
        receipt = dict(state="FAILED_PRESERVED_NO_RETRY", failure_type=type(error).__name__, failure=str(error), checks=dict(CHECKS))
    receipt.update(freeze_sha256=args.sha256, wall_seconds=time.monotonic() - START,
        CPU_seconds=time.process_time() - CPU_START, max_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    destination = output / "review-receipt.json"
    storage.write_bytes(destination, (json.dumps(receipt, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode())
    print(json.dumps({"state": receipt["state"], "receipt": str(destination), "sha256": digest(destination), "bytes": destination.stat().st_size, "checks": dict(CHECKS), "wall_seconds": receipt["wall_seconds"], "CPU_seconds": receipt["CPU_seconds"], "max_RSS_bytes": receipt["max_RSS_bytes"]}, sort_keys=True))
    if receipt["state"] != "PASS_FROZEN_CACHED_ROW_ARITHMETIC_ONLY":
        sys.exit(1)


if __name__ == "__main__":
    main()
