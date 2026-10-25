"""Skill-position mechanisms sharing the lab model engine and data contract.

These are newly versioned hypotheses, not recovered RB fits or validated gains.
Component means add. Joint samples retain shared participation and empirical
dependence; quantiles are computed after aggregation rather than added.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from numbers import Real
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from .scoring import PPR_COMPONENTS, SIGNED_COMPONENTS, ppr_points

SKILL_TARGETS = frozenset({"rush_yd", "rush_att", "rec", "rec_yd", "rush_rec_yd",
                           "fantasy_ppr", "anytime_td"})
METHOD_VERSIONS = {
    "rb_team_share": "rb-team-volume-shrunken-share-new-v1",
    "workload_efficiency": "signed-workload-pooled-efficiency-new-v1",
    "component_means": "rush-rec-compatible-component-means-new-v1",
    "joint_components": "empirical-copula-coherent-passing-components-new-v2",
}


@dataclass(frozen=True)
class MechanismEstimate:
    mean: float | None
    workload: float | None
    efficiency: float | None
    fallback: str | None
    method: str


def _number(value: Any, *, signed: bool = False) -> float:
    if (isinstance(value, bool) or not isinstance(value, (Real, Decimal))
            or not math.isfinite(float(value)) or (not signed and value < 0)):
        raise ValueError("invalid_numeric_component")
    return float(value)


def rb_team_share_workload(team_carry_mean: float, player_carries: Sequence[float],
                           team_carries: Sequence[float], *, prior_share: float,
                           prior_team_opportunities: float,
                           position: str = "RB") -> MechanismEstimate:
    """Separate RB volume × pooled shrunk share; caller declares the new prior.

    Arrays must contain matched, complete earlier games. No missing numerator
    is dropped and no original five-prior-season RB protocol is reconstructed.
    """
    method = METHOD_VERSIONS["rb_team_share"]
    if position != "RB":
        return MechanismEstimate(None, None, None, "rb_only_method", method)
    volume = _number(team_carry_mean)
    prior = _number(prior_share)
    weight = _number(prior_team_opportunities)
    if prior > 1 or len(player_carries) != len(team_carries):
        raise ValueError("invalid_share_or_unpaired_history")
    try:
        player = np.asarray([_number(x) for x in player_carries])
        team = np.asarray([_number(x) for x in team_carries])
        if np.any(player > team):
            raise ValueError("player_workload_exceeds_team")
    except ValueError:
        return MechanismEstimate(volume * prior, volume, prior, "incomplete_history_uses_declared_prior", method)
    denominator = float(team.sum()) + weight
    share = (float(player.sum()) + weight * prior) / denominator if denominator else prior
    reason = "cold_start_declared_prior" if not len(player) or not team.sum() else None
    return MechanismEstimate(volume * share, volume, share, reason, method)


def signed_workload_efficiency(projected_opportunity: float,
                                historical_yards: Sequence[float],
                                historical_opportunity: Sequence[float], *,
                                prior_efficiency: float,
                                prior_opportunities: float) -> MechanismEstimate:
    """Pool signed yards/exposure, with an explicit caller-supplied prior."""
    method = METHOD_VERSIONS["workload_efficiency"]
    workload = _number(projected_opportunity)
    prior = _number(prior_efficiency, signed=True)
    weight = _number(prior_opportunities)
    if len(historical_yards) != len(historical_opportunity):
        raise ValueError("unpaired_efficiency_history")
    try:
        yards = [_number(x, signed=True) for x in historical_yards]
        exposure = [_number(x) for x in historical_opportunity]
    except ValueError:
        return MechanismEstimate(workload * prior, workload, prior,
                                 "incomplete_history_uses_declared_prior", method)
    denominator = sum(exposure) + weight
    efficiency = (sum(yards) + weight * prior) / denominator if denominator else prior
    reason = "cold_start_declared_prior" if not sum(exposure) else None
    return MechanismEstimate(workload * efficiency, workload, efficiency, reason, method)


def combine_mean_predictions(rushing: pd.DataFrame, receiving: pd.DataFrame, *,
                              correlation: float = 0.) -> pd.DataFrame:
    """Add compatible means; use declared covariance for normal moment intervals.

    This interface rejects unaligned rows and different participation estimates.
    The supplied normal intervals are an explicit moment approximation, never
    a sum of component medians or quantiles.
    """
    if not rushing.index.equals(receiving.index):
        raise ValueError("component_rows_not_identically_aligned")
    if not math.isfinite(correlation) or not -1 <= correlation <= 1:
        raise ValueError("invalid_component_correlation")
    if "p_participation" in rushing and "p_participation" in receiving:
        if not np.allclose(rushing.p_participation, receiving.p_participation, equal_nan=True):
            raise ValueError("incompatible_component_participation")
    mean = rushing["mean"] + receiving["mean"]
    variance = (rushing["scale"] ** 2 + receiving["scale"] ** 2
                + 2 * correlation * rushing["scale"] * receiving["scale"])
    scale = np.sqrt(np.maximum(variance, 0))
    result = pd.DataFrame({"mean": mean, "scale": scale,
                           "family": "moment_matched_signed_normal_component_sum"}, index=rushing.index)
    for q in (.1, .5, .9):
        result[f"p{int(q * 100)}"] = mean + stats.norm.ppf(q) * scale
    result["p_participation"] = rushing.get("p_participation", np.nan)
    left = rushing.get("fallback", pd.Series(None, index=rushing.index, dtype=object))
    right = receiving.get("fallback", pd.Series(None, index=receiving.index, dtype=object))
    result["fallback"] = [";".join(dict.fromkeys(str(x) for x in (a, b)
                                                if x is not None and pd.notna(x) and str(x))) or None
                          for a, b in zip(left, right)]
    result["method"] = METHOD_VERSIONS["component_means"]
    return result


def fit_predict_skill(train: pd.DataFrame, test: pd.DataFrame, target: str,
                       method: str) -> pd.DataFrame:
    """The category hook; all fitted models use the shared engine."""
    if target not in SKILL_TARGETS:
        raise ValueError("unsupported_skill_target")
    from .models import fit_predict
    return fit_predict(train, test, target, method)


def independent_combined_yard_predictions(train: pd.DataFrame, test: pd.DataFrame,
                                           method: str) -> pd.DataFrame:
    """Emit direct combined and mean-sum candidates for independent paired scoring.

    No outcomes are inspected here. The evaluator must score rush_rec_yd itself;
    a coherence discrepancy is not an accuracy result or automatic repair.
    """
    from .models import fit_predict
    direct = fit_predict(train, test, "rush_rec_yd", method)
    rushing = fit_predict(train, test, "rush_yd", method)
    receiving = fit_predict(train, test, "rec_yd", method)
    summed = combine_mean_predictions(rushing, receiving)
    return pd.DataFrame({"direct_mean": direct["mean"], "component_mean": summed["mean"],
                         "rush_mean": rushing["mean"], "rec_mean": receiving["mean"],
                         "direct_fallback": direct["fallback"],
                         "component_fallback": summed["fallback"]}, index=test.index)


def sample_joint_components(component_means: Mapping[str, float],
                            complete_history: pd.DataFrame, *, draws: int = 4000,
                            seed: int = 20261022,
                            p_participation: float = 1.,
                            population: str = "conditional_on_playing",
                            cutoff_utc: Any = None) -> pd.DataFrame:
    """Draw one aligned component vector using a training-only empirical copula.

    Nonempty histories require outcome_available_utc and an aware cutoff_utc;
    only records strictly available before that cutoff enter the copula. Common
    reconstructed availability remains reconstructed evidence. Row ranks retain
    empirical cross-component dependence. Missing histories
    fall back to independent uniforms, reported in DataFrame attrs. When their
    exposure components are supplied, catches/TDs are drawn within opportunities.
    Passing completions, touchdown completions and interceptions share a
    mutually exclusive allocation; passing yards require completion exposure.
    Nonempty histories require canonical played participation. Yards are signed.
    All-player samples share one participation draw across every component.
    This is a separate research distribution, not a calibrated superiority claim.
    """
    if not isinstance(draws, int) or isinstance(draws, bool) or draws < 1:
        raise ValueError("positive_draw_count_required")
    if population not in {"conditional_on_playing", "all_player"}:
        raise ValueError("unknown_population")
    play = _number(p_participation)
    if play > 1:
        raise ValueError("invalid_participation_probability")
    names = list(component_means)
    means = {k: _number(v, signed=k in SIGNED_COMPONENTS) for k, v in component_means.items()}
    passing_counts = {"pass_cmp", "pass_td", "pass_int"} & means.keys()
    if passing_counts and "pass_att" not in means:
        raise ValueError("passing_attempt_exposure_required")
    if ("pass_td" in means or "pass_yd" in means) and "pass_cmp" not in means:
        raise ValueError("passing_completion_exposure_required")
    if "pass_att" in means:
        attempts = means["pass_att"]
        completions = means.get("pass_cmp", 0.)
        interceptions = means.get("pass_int", 0.)
        if completions + interceptions > attempts:
            raise ValueError("passing_mean_allocation_exceeds_attempts")
        if means.get("pass_td", 0.) > completions:
            raise ValueError("passing_touchdown_mean_exceeds_completions")
    generator = np.random.default_rng(seed)
    eligible = complete_history
    if len(complete_history):
        if cutoff_utc is None or "outcome_available_utc" not in complete_history:
            raise ValueError("joint_training_cutoff_and_availability_required")
        cutoff = pd.Timestamp(cutoff_utc)
        if cutoff.tzinfo is None:
            raise ValueError("aware_joint_training_cutoff_required")
        available = pd.to_datetime(complete_history.outcome_available_utc, utc=True, errors="coerce")
        eligible = complete_history.loc[available.notna() & (available < cutoff)]
        if "participation_state" not in eligible:
            raise ValueError("canonical_joint_participation_required")
        if not eligible.participation_state.dropna().isin(["played", "DNP", "unknown"]).all():
            raise ValueError("invalid_canonical_joint_participation")
        if "participation" in eligible:
            legacy = eligible.participation.astype("string").str.lower()
            canonical = eligible.participation_state.astype("string").str.lower()
            if (legacy.notna() & legacy.ne(canonical).fillna(True)).any():
                raise ValueError("conflicting_joint_participation")
        eligible = eligible.loc[eligible.participation_state.eq("played")]
    history = eligible.reindex(columns=names).replace([np.inf, -np.inf], np.nan).dropna()
    fallback = None
    if len(history) >= 3:
        rank_min = history.rank(method="min", pct=False).to_numpy(dtype=float)
        rank_max = history.rank(method="max", pct=False).to_numpy(dtype=float)
        chosen = generator.integers(0, len(history), size=draws)
        # One sampled historical row supplies all marginal ranks.
        uniforms = (rank_min[chosen] - 1 + generator.random((draws, len(names)))
                    * (rank_max[chosen] - rank_min[chosen] + 1)) / len(history)
    else:
        uniforms = generator.random((draws, len(names)))
        fallback = "insufficient_complete_joint_history_independent_copula"
    uniforms = np.clip(uniforms, 1e-9, 1 - 1e-9)
    u = {name: uniforms[:, i] for i, name in enumerate(names)}
    result: dict[str, np.ndarray] = {}
    for name in names:
        if name not in SIGNED_COMPONENTS:
            result[name] = stats.poisson.ppf(u[name], means[name])
    # Sequential binomials implement one four-category multinomial partition:
    # TD completion, other completion, interception, other incomplete. Each
    # innovation is independent of its exposure to preserve marginal means.
    if "pass_cmp" in means:
        rate = means["pass_cmp"] / means["pass_att"] if means["pass_att"] else 0.
        result["pass_cmp"] = stats.binom.ppf(generator.random(draws), result["pass_att"], rate)
    if "pass_td" in means:
        rate = means["pass_td"] / means["pass_cmp"] if means["pass_cmp"] else 0.
        result["pass_td"] = stats.binom.ppf(generator.random(draws), result["pass_cmp"], rate)
    if "pass_int" in means:
        incomplete_mean = means["pass_att"] - means.get("pass_cmp", 0.)
        rate = means["pass_int"] / incomplete_mean if incomplete_mean else 0.
        incomplete = result["pass_att"] - result.get("pass_cmp", 0.)
        result["pass_int"] = stats.binom.ppf(generator.random(draws), incomplete, rate)
    for count, exposure in (("rec", "rec_tgt"), ("rush_td", "rush_att"), ("rec_td", "rec")):
        if count in means and exposure in means:
            if means[count] > means[exposure]:
                raise ValueError("count_mean_exceeds_opportunity:" + count)
            rate = means[count] / means[exposure] if means[exposure] else 0.
            # Conditional binomial innovations must be independent of the
            # exposure draw to preserve the declared marginal mean.
            result[count] = stats.binom.ppf(generator.random(draws), result[exposure], rate)
    for name in names:
        if name not in SIGNED_COMPONENTS:
            continue
        exposure = {"rush_yd": "rush_att", "rec_yd": "rec", "pass_yd": "pass_cmp"}[name]
        observed = history[name].to_numpy(dtype=float) if len(history) else np.array([])
        sigma = float(np.std(observed, ddof=1)) if len(observed) > 1 else max(abs(means[name]) * .5, 1.)
        if exposure in means:
            if not means[exposure] and means[name]:
                raise ValueError("yards_mean_with_zero_opportunity:" + name)
            rate = means[name] / means[exposure] if means[exposure] else 0.
            # Scale the yard residual per opportunity; no nonnegative clipping.
            spread = sigma / math.sqrt(max(means[exposure], 1.))
            workload = result[exposure]
            residual = np.sqrt(workload) * spread * stats.norm.ppf(u[name])
            active = workload > 0
            if active.any():
                residual[active] -= residual[active].mean()
            result[name] = workload * rate + residual
        else:
            result[name] = means[name] + sigma * stats.norm.ppf(u[name])
    samples = pd.DataFrame({name: result[name] for name in names})
    participating = generator.random(draws) < play
    if population == "all_player":
        samples.loc[~participating, :] = 0.
    samples.attrs.update(method=METHOD_VERSIONS["joint_components"], fallback=fallback,
                         population=population, p_participation=play, seed=seed,
                         complete_history_rows=len(history), cutoff_utc=str(cutoff_utc),
                         supplied_history_rows=len(complete_history),
                         history_vintage=";".join(sorted(set(eligible.get("history_vintage", pd.Series(dtype=str)).dropna().astype(str)))))
    return samples


def summarize_joint_components(samples: pd.DataFrame) -> dict[str, Mapping[str, float]]:
    """Score each joint draw first, including the nonlinear fumble exception."""
    if samples.empty:
        raise ValueError("empty_joint_samples")
    targets: dict[str, np.ndarray] = {}
    if {"rush_yd", "rec_yd"}.issubset(samples.columns):
        targets["rush_rec_yd"] = (samples.rush_yd + samples.rec_yd).to_numpy()
    if {"rush_td", "rec_td"}.issubset(samples.columns):
        targets["anytime_td"] = ((samples.rush_td + samples.rec_td) > 0).to_numpy(dtype=float)
    if set(PPR_COMPONENTS).issubset(samples.columns):
        scored = [ppr_points(row) for row in samples.to_dict("records")]
        if any(value is None for value in scored):
            raise ValueError("invalid_joint_ppr_component")
        targets["fantasy_ppr"] = np.asarray(scored, dtype=float)
    summary = {}
    for target, values in targets.items():
        if not np.isfinite(values).all():
            raise ValueError("nonfinite_joint_components")
        quantiles = np.quantile(values, [.1, .5, .9])
        summary[target] = {"mean": float(np.mean(values)), "scale": float(np.std(values)),
                           **{f"p{p}": float(value) for p, value in zip((10, 50, 90), quantiles)}}
    return summary
