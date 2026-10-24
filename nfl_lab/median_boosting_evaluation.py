"""Strict, separately versioned comparisons after an explicit source change."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .cdf_engine import KEYS, numeric, valid_support
from .median_boosting import score_frozen_rows
from .website_cdf_evaluation import normalize_keys

SOURCE_COMPARISON_VERSION = "strict-source-change-common-pairs-v1-20261023"


def source_change_control(saved, offered, category, method):
    """Retain the outer population; align literal points to clean query rows.

    Both-finite outcome contradictions are quarantined. Missingness and changed
    participation qualification remain explicit lineage differences. The new
    qualified outcome is used universally for the eligible pair mask. No saved
    point, source artifact, raw outcome or raw participation value is repaired.
    """
    saved, offered = normalize_keys(saved), normalize_keys(offered)
    if saved.duplicated(KEYS).any() or offered.duplicated(KEYS).any():
        raise ValueError("duplicate source-change identity")
    if not saved.method.eq(method).all() or not saved.target.eq(category["target"]).all():
        raise ValueError("saved source-change method/target differs")
    required = ["team", "opponent", "position", "kickoff_utc"]
    if set(required + ["point", "actual", "participation_state"]) - set(saved):
        raise ValueError("saved source-change binding fields missing")
    provenance = [c for c in offered if c.startswith("qualified_") or c in
                  {"official_physical_event", "participation_evidence", "source_policy", "stats_observed"}]
    clean = offered[KEYS + required + ["cutoff_utc", "participation_state"] + provenance].copy()
    clean["actual"] = numeric(offered, category["target"])
    clean = clean.rename(columns={c: "candidate_" + c for c in clean if c not in KEYS})
    retained = saved.rename(columns={c: "retained_" + c for c in saved if c not in KEYS})
    audit = clean.merge(retained, on=KEYS, how="outer", sort=False, validate="one_to_one", indicator="coverage")
    common = audit.coverage.eq("both").to_numpy()
    fields = required + (["cutoff_utc"] if "cutoff_utc" in saved else [])
    for name in fields:
        left, right = audit["candidate_" + name], audit["retained_" + name]
        if name.endswith("_utc"):
            left, right = pd.to_datetime(left, utc=True, errors="coerce"), pd.to_datetime(right, utc=True, errors="coerce")
        if (common & ~left.eq(right).to_numpy()).any():
            raise ValueError("source-change common context mismatch: " + name)
    old_y, new_y = numeric(audit, "retained_actual"), numeric(audit, "candidate_actual")
    finite_old, finite_new = np.isfinite(old_y), np.isfinite(new_y)
    audit["both_finite_actual_conflict"] = common & finite_old & finite_new & (old_y != new_y)
    old_state = audit.retained_participation_state.fillna("absent")
    new_state = audit.candidate_participation_state.fillna("absent")
    for prefix, values, states in [("candidate", new_y, new_state), ("retained", old_y, old_state)]:
        audit[prefix + "_derived_outcome_state"] = np.where(states != "played", states,
            np.where(~np.isfinite(values), "played_missing_statistic", np.where(~valid_support(values, category["support"]),
            "played_invalid_support", np.where(values == 0, "played_zero", "played_nonzero"))))
    audit["participation_qualification_changed"] = common & ~old_state.eq(new_state).to_numpy()
    # Finite old played statistics contradict a newly confirmed DNP. Old
    # inferred DNP -> newly proved played remains an explicit qualification
    # change unless the old control carries independent DNP confirmation.
    confirmed_old = audit.get("retained_participation_confirmed", pd.Series(False, index=audit.index)).fillna(False).astype(bool).to_numpy()
    audit["confirmed_participation_conflict"] = common & (
        (old_state.eq("played").to_numpy() & finite_old & new_state.eq("DNP").to_numpy()) |
        (old_state.eq("DNP").to_numpy() & confirmed_old & new_state.eq("played").to_numpy()))
    audit["old_missing_new_finite"] = common & ~finite_old & finite_new
    audit["old_finite_new_missing"] = common & finite_old & ~finite_new
    audit["pair_quarantined"] = audit.both_finite_actual_conflict | audit.confirmed_participation_conflict
    audit["source_comparison_version"] = SOURCE_COMPARISON_VERSION
    audit["control_cutoff_binding"] = "exact_recorded_cutoff_on_common" if "cutoff_utc" in saved else "unrecorded_in_saved_control; original_clock_not_reconstructed_or_authenticated"
    # The aligned comparison retains ALL clean query rows, including absent
    # controls. All control-only keys remain in the separate outer audit.
    columns = KEYS + [c for c in audit if c.startswith("retained_") or c in {"pair_quarantined", "both_finite_actual_conflict", "confirmed_participation_conflict", "participation_qualification_changed", "old_missing_new_finite", "old_finite_new_missing", "control_cutoff_binding"}]
    result = offered[[c for c in KEYS + required + ["cutoff_utc"] if c in offered]].merge(audit[columns], on=KEYS, how="left", sort=False, validate="one_to_one")
    result["target"], result["method"] = category["target"], method
    result["primary_role"] = result.position.isin(category["primary_roles"])
    point = numeric(result, "retained_point")
    if category["support"] == "bernoulli" and (np.isfinite(point) & ((point < 0) | (point > 1))).any():
        raise ValueError("retained event probability outside [0,1]")
    result["point"] = np.where(result.pair_quarantined, np.nan, point)
    result["source_field"] = result.get("retained_source_field", "literal_saved_point")
    result = score_frozen_rows(offered, result, category)
    history = numeric(offered, "f_player_games_prior")
    result["history_state"] = np.where(~np.isfinite(history) | (history <= 0), "cold_or_unknown", "warm")
    result["fallback"] = result.get("retained_fallback", "")
    receipt = {"version": SOURCE_COMPARISON_VERSION, "method": method,
        "candidate_offered_rows": len(offered), "retained_control_offered_rows": len(saved),
        "common_rows": int(common.sum()), "candidate_only_rows": int(audit.coverage.eq("left_only").sum()),
        "control_only_rows": int(audit.coverage.eq("right_only").sum()),
        "raw_actual_conflicts_quarantined": int(audit.both_finite_actual_conflict.sum()),
        "confirmed_participation_conflicts_quarantined": int(audit.confirmed_participation_conflict.sum()),
        "participation_qualification_changes": int(audit.participation_qualification_changed.sum()),
        "old_missing_new_finite": int(audit.old_missing_new_finite.sum()),
        "old_finite_new_missing": int(audit.old_finite_new_missing.sum()),
        "candidate_participation_states": offered.participation_state.value_counts(dropna=False).to_dict(),
        "retained_participation_states": saved.participation_state.value_counts(dropna=False).to_dict(),
        "candidate_outcome_states": result.outcome_state.value_counts(dropna=False).to_dict(),
        "retained_outcome_states": audit.loc[~audit.coverage.eq("left_only"), "retained_derived_outcome_state"].value_counts(dropna=False).to_dict(),
        "cutoff_binding": audit.control_cutoff_binding.iloc[0] if len(audit) else "no_rows",
        "outcome_policy": "new clean source-qualified outcome universally; both-finite disagreements quarantined; raw retained values unchanged"}
    return result, audit, receipt


def log_loss_summary(probability, actual):
    probability, actual = np.asarray(probability, float), np.asarray(actual, float)
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any() or not valid_support(actual, "bernoulli").all():
        raise ValueError("log-loss requires genuine supported probability/outcome pairs")
    with np.errstate(divide="ignore", invalid="ignore"):
        losses = -np.where(actual == 1, np.log(probability), np.log1p(-probability))
    finite = np.isfinite(losses)
    infinite = int(np.isposinf(losses).sum())
    return {"rows": len(losses), "natural_log_loss": float(losses.mean()) if len(losses) and not infinite else None,
        "log_loss_state": "positive_infinity" if infinite else "finite" if len(losses) else "unavailable",
        "infinite_log_losses": infinite, "finite_log_loss_sum": float(losses[finite].sum()),
        "finite_log_loss_count": int(finite.sum()), "probability_clipping": "none"}


def reliability(probability, actual):
    probability, actual = np.asarray(probability, float), np.asarray(actual, float)
    # Fixed deciles, with p=1 included in the last bin; no probability clipping.
    bins = np.minimum((probability * 10).astype(int), 9)
    return [{"bin": i, "lower_inclusive": i / 10, "upper": (i + 1) / 10,
        "upper_inclusive": i == 9, "rows": int((bins == i).sum()),
        "mean_probability": float(probability[bins == i].mean()) if (bins == i).any() else None,
        "observed_rate": float(actual[bins == i].mean()) if (bins == i).any() else None}
        for i in range(10)]
