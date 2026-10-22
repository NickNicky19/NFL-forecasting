"""Finite, train-only forecasting candidates shared by every lab category.

The forecasts describe a player conditional on playing. ``p_participation`` is a
separate estimate and must not be used as a settlement rule. ``scale`` is the
conditional standard deviation, including for the negative binomial family.
Feature clocks and authentic source bindings are the caller's responsibility;
this module additionally rejects obvious label/future columns and future train
rows. These new candidates do not reproduce any missing historical executable.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import bernoulli, nbinom, norm, poisson
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import LogisticRegression, PoissonRegressor, Ridge
from threadpoolctl import threadpool_limits


MODEL_VERSION = "shared-train-only-v1-20261022"
METHODS = (
    "recent", "pooled", "raw_sleeper", "pinned_website", "workload", "ridge",
    "tree", "distributional", "ensemble", "ridge_without_opponent",
    "ridge_without_workload", "ridge_without_team",
)
TARGETS = (
    "pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd",
    "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td",
)
COUNT_TARGETS = frozenset({"pass_td", "pass_cmp", "pass_att", "pass_int", "rush_att", "rec"})
SEED = 1701
RIDGE_ALPHA = 32.0
MAX_FIT_ROWS = 120_000
_BAD_TOKEN = re.compile(r"(?:^|_)(?:actual|outcome|future|postgame|realized|label|next|current_game|same_game)(?:_|$)")
_TEMPORAL = re.compile(r"(?:mean\d*|n\d+|rate\d*|ypa\d*|ypt\d*|prior|lag\d*|last\d*|rolling|adjusted|rest_days|home|pregame|forecast|travel|roof|surface)")


def _numeric(frame: pd.DataFrame, name: str) -> np.ndarray:
    if name == "targets" and name not in frame and "rec_tgt" in frame:
        name = "rec_tgt"
    if name not in frame:
        return np.full(len(frame), np.nan)
    return pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=float, na_value=np.nan)


def _strings(frame: pd.DataFrame, name: str) -> np.ndarray:
    if name not in frame:
        return np.full(len(frame), "<unknown>", dtype=object)
    return frame[name].fillna("<unknown>").astype(str).to_numpy()


def _support(values: np.ndarray, target: str) -> np.ndarray:
    valid = np.isfinite(values)
    if target in COUNT_TARGETS:
        valid &= (values >= 0) & (values == np.floor(values))
    elif target == "anytime_td":
        valid &= (values == 0) | (values == 1)
    return valid


def _family(target: str) -> str:
    return "bernoulli" if target == "anytime_td" else "negbin" if target in COUNT_TARGETS else "normal"


def feature_group(name: str) -> str:
    """Fixed ablation groups; no group is selected using evaluation outcomes."""
    if name == "opponent" or name.startswith(("f_opp_", "f_opponent_")):
        return "opponent"
    if name == "team" or name.startswith("f_team_"):
        return "team"
    if name.startswith("f_player_") and (
        any(f"_{target}_" in name for target in TARGETS + ("targets",))
        or "games_prior" in name or "participation" in name or "play_rate" in name
    ):
        return "workload"
    return "ability_or_context"


def _feature_names(train: pd.DataFrame, test: pd.DataFrame, method: str) -> tuple[list[str], list[str]]:
    names, rejected = [], []
    for name in sorted(set(train.columns) | set(test.columns)):
        if not name.startswith("f_"):
            continue
        # Prefix alone is insufficient: raw targets and unlagged numeric columns
        # are deliberately excluded. Qualified rolling target histories are valid.
        safe = not _BAD_TOKEN.search(name) and bool(_TEMPORAL.search(name))
        safe &= name not in {f"f_{target}" for target in TARGETS}
        if not safe:
            rejected.append(name)
            continue
        group = feature_group(name)
        removed = method.removeprefix("ridge_without_") if method.startswith("ridge_without_") else None
        if group != removed and name in train and name in test:
            names.append(name)
    return names, rejected


def _temporal_training(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fit once before the earliest test kickoff, never on later test-era labels."""
    train = train.copy()
    audit: dict[str, Any] = {"input_rows": len(train), "removed_future_or_unknown_time_rows": 0}
    if len(test) and "kickoff_utc" in test:
        test_time = pd.to_datetime(test["kickoff_utc"], utc=True, errors="coerce")
        if test_time.notna().any():
            cutoff = test_time.min()
            if "cutoff_utc" in test:
                issued_cutoff = pd.to_datetime(test["cutoff_utc"], utc=True, errors="coerce")
                if issued_cutoff.notna().any():
                    cutoff = min(cutoff, issued_cutoff.min())
            train_time = pd.to_datetime(train.get("kickoff_utc", pd.Series(pd.NaT, index=train.index)), utc=True, errors="coerce")
            keep = train_time.notna() & (train_time < cutoff)
            if "outcome_available_utc" in train:
                available = pd.to_datetime(train["outcome_available_utc"], utc=True, errors="coerce")
                keep &= available.notna() & (available < cutoff)
                audit["label_availability_checked"] = True
            else:
                audit["label_availability_checked"] = False
            audit["removed_future_or_unknown_time_rows"] = int((~keep).sum())
            audit["fit_before_utc"] = cutoff.isoformat()
            train = train.loc[keep].copy()
    sort_cols = [c for c in ("kickoff_utc", "game_id", "player_id") if c in train]
    if sort_cols:
        train = train.sort_values(sort_cols, kind="stable")
    if len(train) > MAX_FIT_ROWS:
        audit["bounded_rows_removed"] = len(train) - MAX_FIT_ROWS
        train = train.tail(MAX_FIT_ROWS).copy()
    audit["time_contract"] = "earlier train kickoff and supplied label availability; caller verifies original source clocks and lag"
    return train, audit


@dataclass
class _Prior:
    mean: float
    variance: float
    n: int


def _priors(train: pd.DataFrame, target: str) -> tuple[_Prior, dict[str, _Prior]]:
    y = _numeric(train, target)
    def make(values: np.ndarray) -> _Prior:
        mean = float(np.mean(values))
        variance = float(np.var(values, ddof=1)) if len(values) > 1 else max(abs(mean), 1.0)
        return _Prior(mean, variance, len(values))
    global_prior = make(y)
    positions = _strings(train, "position")
    return global_prior, {str(position): make(y[positions == position]) for position in np.unique(positions)}


def _prior_vectors(frame: pd.DataFrame, global_prior: _Prior, position_priors: dict[str, _Prior]) -> tuple[np.ndarray, np.ndarray]:
    priors = [position_priors.get(str(position), global_prior) for position in _strings(frame, "position")]
    return np.array([p.mean for p in priors]), np.array([p.variance for p in priors])


def _history_summary(train: pd.DataFrame, frame: pd.DataFrame, target: str, window: int, *, fitting: bool) -> tuple[np.ndarray, np.ndarray]:
    means, counts = np.full(len(frame), np.nan), np.zeros(len(frame))
    if target not in train or "player_id" not in train or "player_id" not in frame:
        return means, counts
    if fitting:
        # Only used to estimate fitted training residual spread. Exclude the row
        # itself from the rolling summary even though all fitting labels are old.
        work = train[["player_id", target]].copy()
        work["_row"] = np.arange(len(work))
        for _, group in work.groupby("player_id", sort=False, dropna=False):
            values = pd.to_numeric(group[target], errors="coerce")
            earlier = values.shift(1)
            slots = group["_row"].to_numpy()
            means[slots] = earlier.rolling(window, min_periods=1).mean().to_numpy()
            counts[slots] = earlier.rolling(window, min_periods=1).count().to_numpy()
        return means, counts
    history: dict[str, tuple[float, int]] = {}
    for player, group in train.groupby("player_id", sort=False, dropna=False):
        values = pd.to_numeric(group[target], errors="coerce").dropna().tail(window)
        if len(values):
            history[str(player)] = (float(values.mean()), len(values))
    for i, player in enumerate(_strings(frame, "player_id")):
        if str(player) in history:
            means[i], counts[i] = history[str(player)]
    return means, counts


def _recent(train: pd.DataFrame, frame: pd.DataFrame, target: str, global_prior: _Prior, position_priors: dict[str, _Prior], *, window: int = 3, fitting: bool = False, state: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    prior, _ = _prior_vectors(frame, global_prior, position_priors)
    mean = _numeric(frame, f"f_player_{target}_mean{window}")
    count = _numeric(frame, f"f_player_{target}_n{window}")
    historic_mean, historic_count = _history_summary(train, frame, target, window, fitting=fitting)
    # A missing count is not an assertion of a full history.
    valid_feature = np.isfinite(mean) & np.isfinite(count) & (count > 0) & (count <= window) & (count == np.floor(count))
    if target in COUNT_TARGETS or target == "targets":
        valid_feature &= mean >= 0
    elif target == "anytime_td":
        valid_feature &= (mean >= 0) & (mean <= 1)
    provided = f"f_player_{target}_mean{window}" in frame and f"f_player_{target}_n{window}" in frame
    if state is not None:
        state.update(kind="recent", target=target, window=window,
                     global_prior=vars(global_prior), position_priors={p: vars(value) for p, value in position_priors.items()},
                     required_summary_columns=[f"f_player_{target}_mean{window}", f"f_player_{target}_n{window}"],
                     qualified_summary_columns_present=provided)
    # An explicitly empty/unknown qualified window cannot be silently extended
    # farther into the past to find favorable supported games.
    if provided:
        mean = np.where(valid_feature, mean, np.nan)
        count = np.where(valid_feature, count, 0)
    else:
        mean = np.where(valid_feature, mean, historic_mean)
        count = np.where(valid_feature, count, historic_count)
    valid = np.isfinite(mean) & (count > 0)
    strength = 3.0 if window == 3 else 5.0
    prediction = np.where(valid, (np.nan_to_num(mean) * count + strength * prior) / (count + strength), prior)
    reason = np.where(valid_feature, "", np.where(valid, "training_history_fallback", "position_prior"))
    unknown_position = ~np.isin(_strings(frame, "position"), list(position_priors))
    reason = np.where(~valid & unknown_position, "global_prior_unknown_position", reason)
    return prediction, reason.astype(object)


def _component_recent(train: pd.DataFrame, frame: pd.DataFrame, target: str, *, fitting: bool, state: dict | None = None) -> np.ndarray:
    values = _numeric(train, target)
    played = _strings(train, "participation_state") == "played"
    valid = played & np.isfinite(values)
    if target in COUNT_TARGETS or target == "targets":
        valid &= (values >= 0) & (values == np.floor(values))
    supported = train.loc[valid]
    if not len(supported):
        if state is not None:
            state.update(kind="unavailable")
        return np.full(len(frame), np.nan)
    gp, pp = _priors(supported, target)
    # frame may be a different subset than supported; fitting's rolling indexing
    # is valid only for the same frame. Source-provided lag features still work.
    if fitting and len(supported) != len(frame):
        return _recent(supported, frame, target, gp, pp, fitting=False, state=state)[0]
    return _recent(supported, frame, target, gp, pp, fitting=fitting, state=state)[0]


def _pooled_rate(train: pd.DataFrame, frame: pd.DataFrame, numerator: str, denominator: str, feature: str | None, *, bounded: bool = False, state: dict | None = None) -> np.ndarray:
    num, den = _numeric(train, numerator), _numeric(train, denominator)
    valid = np.isfinite(num) & np.isfinite(den) & (den > 0)
    if bounded:
        valid &= (num >= 0) & (num <= den)
    if not valid.any():
        if state is not None:
            state.update(kind="unavailable")
        return np.full(len(frame), np.nan)
    gp = float(num[valid].sum() / den[valid].sum())
    positions = _strings(train, "position")
    lookup = {}
    for position in np.unique(positions[valid]):
        rows = valid & (positions == position)
        lookup[str(position)] = (float(num[rows].sum()) + 30 * gp) / (float(den[rows].sum()) + 30)
    if state is not None:
        state.update(kind="pooled_rate", numerator=numerator, denominator=denominator,
                     feature=feature, bounded=bounded, global_rate=gp, position_rates=lookup)
    prior = np.array([lookup.get(str(p), gp) for p in _strings(frame, "position")])
    rate = _numeric(frame, feature) if feature else np.full(len(frame), np.nan)
    # A ratio of compatible lagged totals/means is used only when both exist.
    exposure = _numeric(frame, f"f_player_{denominator}_mean3")
    if feature is None:
        numerator_recent = _numeric(frame, f"f_player_{numerator}_mean3")
        rate = np.divide(numerator_recent, exposure, out=rate, where=np.isfinite(exposure) & (exposure > 0))
    recent_n = _numeric(frame, f"f_player_{denominator}_n3")
    exposure = np.where(np.isfinite(recent_n), exposure * np.minimum(recent_n, 3), np.nan)
    valid_recent = np.isfinite(rate) & np.isfinite(exposure) & (exposure > 0)
    if bounded:
        valid_recent &= (rate >= 0) & (rate <= 1)
    # Exposure pseudo-count is fixed at 30, not selected on validation outcomes.
    result = np.where(valid_recent, (np.nan_to_num(rate) * np.nan_to_num(exposure) + 30 * prior) / (np.nan_to_num(exposure) + 30), prior)
    return np.clip(result, 0, 1) if bounded else result


def _workload(train: pd.DataFrame, frame: pd.DataFrame, target: str, global_prior: _Prior, position_priors: dict[str, _Prior], *, fitting: bool = False, state: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    baseline_state = {} if state is not None else None
    baseline, reason = _recent(train, frame, target, global_prior, position_priors, fitting=fitting, state=baseline_state)
    candidate_state: dict = {"kind": "unavailable"}
    if state is not None:
        state.update(kind="workload", target=target, baseline=baseline_state, candidate=candidate_state)
    exposure_name: str | None = None
    rate_feature: str | None = None
    bounded = False
    if target in {"pass_yd", "pass_cmp", "pass_td", "pass_int"}:
        exposure_name = "pass_att"
        rate_feature = {"pass_yd": "f_player_pass_ypa3", "pass_cmp": "f_player_comp_rate3"}.get(target)
        bounded = target == "pass_cmp"
    elif target in {"rec", "rec_yd"}:
        exposure_name = "targets"
        rate_feature = "f_player_rec_catch_rate3" if target == "rec" else "f_player_rec_ypt3"
        bounded = target == "rec"
    elif target == "rush_yd":
        exposure_name = "rush_att"
        rate_feature = "f_player_rush_ypa3"
    if exposure_name:
        exposure_state, rate_state = {}, {}
        exposure = _component_recent(train, frame, exposure_name, fitting=fitting, state=exposure_state if state is not None else None)
        rate = _pooled_rate(train, frame, target, exposure_name, rate_feature, bounded=bounded, state=rate_state if state is not None else None)
        candidate_state.update(kind="exposure_rate", exposure=exposure_state, rate=rate_state)
        candidate = exposure * rate
    elif target in {"pass_att", "rush_att"}:
        team_feature = f"f_team_{target}_mean3"
        team_volume, train_volume = _numeric(frame, team_feature), _numeric(train, team_feature)
        y = _numeric(train, target)
        valid = np.isfinite(train_volume) & (train_volume > 0)
        if valid.any():
            global_share = float(y[valid].sum() / train_volume[valid].sum())
            pos = _strings(train, "position")
            shares = {}
            for p in np.unique(pos[valid]):
                rows = valid & (pos == p)
                shares[str(p)] = (float(y[rows].sum()) + 90 * global_share) / (float(train_volume[rows].sum()) + 90)
            candidate_state.update(kind="team_share", target=target, global_share=global_share, position_shares=shares)
            prior_share = np.array([shares.get(str(p), global_share) for p in _strings(frame, "position")])
            player_volume = _numeric(frame, f"f_player_{target}_mean3")
            n = _numeric(frame, f"f_player_{target}_n3")
            share = np.divide(player_volume, team_volume, out=np.full(len(frame), np.nan), where=team_volume > 0)
            w = np.where(np.isfinite(n), np.minimum(n, 3) / (np.minimum(n, 3) + 3), 0)
            share = np.where(np.isfinite(share), w * share + (1 - w) * prior_share, prior_share)
            candidate = team_volume * np.clip(share, 0, 1)
        else:
            candidate = np.full(len(frame), np.nan)
    elif target == "rush_rec_yd":
        # This is a new compatible mean-sum candidate, not a quantile sum.
        components = []
        component_states = []
        for component in ("rush_yd", "rec_yd"):
            vals = _numeric(train, component)
            valid = np.isfinite(vals)
            if not valid.any():
                components.append(np.full(len(frame), np.nan))
                component_states.append({"kind": "unavailable"})
                continue
            gp, pp = _priors(train.loc[valid], component)
            component_state = {}
            components.append(_workload(train.loc[valid], frame, component, gp, pp, fitting=False, state=component_state if state is not None else None)[0])
            component_states.append(component_state)
        candidate_state.update(kind="mean_sum", components=component_states)
        candidate = components[0] + components[1]
    else:
        # Exact PPR needs its scoring adapter. Binary probabilities use the
        # registered Bernoulli fit, rather than an arbitrary probability haircut.
        candidate = np.full(len(frame), np.nan)
    valid = np.isfinite(candidate)
    return np.where(valid, candidate, baseline), np.where(valid, "", "missing_workload_inputs:" + reason.astype(str)).astype(object)


class _Design:
    """Training medians/scales/categories; test rows never fit preprocessing."""
    def __init__(self, train: pd.DataFrame, test: pd.DataFrame, method: str):
        names, self.rejected = _feature_names(train, test, method)
        self.numeric = []
        self.medians, self.scales = [], []
        for name in names:
            x = _numeric(train, name)
            finite = x[np.isfinite(x)]
            if not len(finite):
                continue
            median = float(np.median(finite))
            scale = float(np.std(finite))
            if scale <= 1e-12:
                # Missingness itself can still carry signal in training.
                if len(finite) == len(x):
                    continue
                scale = 1.0
            self.numeric.append(name)
            self.medians.append(median)
            self.scales.append(scale)
        self.categorical = {}
        removed = method.removeprefix("ridge_without_") if method.startswith("ridge_without_") else None
        for name in ("position", "team", "opponent"):
            if name in train and feature_group(name) != removed:
                self.categorical[name] = sorted(set(_strings(train, name)))
        self.names = [part for name in self.numeric for part in (name, name + ":missing")]
        self.names += [f"{name}={value}" for name, values in self.categorical.items() for value in values]

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        parts = []
        for name, median, scale in zip(self.numeric, self.medians, self.scales):
            values = _numeric(frame, name)
            missing = ~np.isfinite(values)
            parts.extend([np.clip((np.where(missing, median, values) - median) / scale, -8, 8), missing.astype(float)])
        for name, values in self.categorical.items():
            observed = _strings(frame, name)
            parts.extend([(observed == value).astype(float) for value in values])
        return np.column_stack(parts) if parts else np.empty((len(frame), 0))

    def audit(self) -> dict[str, Any]:
        return {"feature_columns": self.numeric, "rejected_feature_columns": self.rejected,
                "numeric_medians": dict(zip(self.numeric, self.medians)), "numeric_scales": dict(zip(self.numeric, self.scales)),
                "categorical_levels": self.categorical,
                "feature_groups": {name: feature_group(name) for name in self.numeric},
                "transformed_columns": self.names, "standardized_feature_clip": [-8, 8]}


def _ml(train: pd.DataFrame, test: pd.DataFrame, target: str, method: str, global_prior: _Prior, position_priors: dict[str, _Prior], *, state: dict | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    baseline_state = {} if state is not None else None
    baseline_test, baseline_reason = _recent(train, test, target, global_prior, position_priors, state=baseline_state)
    baseline_train, _ = _recent(train, train, target, global_prior, position_priors, fitting=True)
    design = _Design(train, test, method)
    audit = design.audit()
    if state is not None:
        state.update(kind="ml", target=target, method=method, baseline=baseline_state, design=audit.copy(), fit_status="not_fitted")
        state["design"]["categorical_order"] = list(design.categorical)
    x, xt, y = design.transform(train), design.transform(test), _numeric(train, target)
    if len(train) < 20 or x.shape[1] == 0:
        audit["fit_status"] = "insufficient_supported_training_or_features"
        if state is not None:
            state.update(fit_status=audit["fit_status"])
        return baseline_test, baseline_train, np.full(len(test), "insufficient_fit:" , dtype=object) + baseline_reason, audit
    try:
        if target == "anytime_td":
            if len(np.unique(y)) < 2:
                audit["fit_status"] = "single_binary_class_position_prior"
                if state is not None:
                    state.update(fit_status=audit["fit_status"])
                return baseline_test, baseline_train, np.full(len(test), "single_binary_class", dtype=object), audit
            if method == "tree":
                model = ExtraTreesRegressor(n_estimators=24, max_depth=6, min_samples_leaf=30, max_features=0.8, random_state=SEED, n_jobs=2)
            else:
                model = LogisticRegression(C=1 / RIDGE_ALPHA, max_iter=150, tol=1e-5, random_state=SEED)
        elif method == "tree":
            model = ExtraTreesRegressor(n_estimators=24, max_depth=6, min_samples_leaf=30, max_features=0.8, random_state=SEED, n_jobs=2)
        elif method == "distributional" and target in COUNT_TARGETS and y.sum() > 0:
            model = PoissonRegressor(alpha=3.0, max_iter=100, tol=1e-5)
        else:
            model = Ridge(alpha=RIDGE_ALPHA, solver="cholesky")
        with threadpool_limits(limits=2):
            model.fit(x, y)
            if isinstance(model, LogisticRegression):
                prediction, fitted = model.predict_proba(xt)[:, 1], model.predict_proba(x)[:, 1]
            else:
                prediction, fitted = model.predict(xt), model.predict(x)
        # Limits are training-defined guards against numerical extrapolation.
        if target == "anytime_td":
            prediction, fitted = np.clip(prediction, 0, 1), np.clip(fitted, 0, 1)
        elif target in COUNT_TARGETS:
            upper = max(10.0, float(np.max(y)) * 2)
            prediction, fitted = np.clip(prediction, 0, upper), np.clip(fitted, 0, upper)
            audit["count_mean_bounds"] = [0, upper]
        valid = np.isfinite(prediction)
        prediction = np.where(valid, prediction, baseline_test)
        reason = np.where(valid, "", "nonfinite_fit:" + baseline_reason.astype(str)).astype(object)
        if design.numeric:
            all_missing = ~np.column_stack([np.isfinite(_numeric(test, name)) for name in design.numeric]).any(axis=1)
            prediction = np.where(all_missing, baseline_test, prediction)
            reason = np.where(all_missing, "all_numeric_features_missing:" + baseline_reason.astype(str), reason)
        audit["fit_status"] = "fitted"
        audit["estimator"] = type(model).__name__
        audit["estimator_params"] = model.get_params()
        if hasattr(model, "coef_"):
            audit["coefficients"] = np.asarray(model.coef_).tolist()
            audit["intercept"] = np.asarray(model.intercept_).tolist()
        if hasattr(model, "feature_importances_"):
            audit["feature_importances"] = model.feature_importances_.tolist()
        if state is not None:
            from .model_artifacts import estimator_state
            state.update(fit_status="fitted", estimator=estimator_state(model),
                         count_mean_bounds=audit.get("count_mean_bounds"))
        return prediction, fitted, reason, audit
    except (ValueError, FloatingPointError, OverflowError) as error:
        audit["fit_status"] = "failed_with_recorded_fallback"
        audit["fit_error"] = f"{type(error).__name__}: {error}"
        if state is not None:
            state.update(fit_status=audit["fit_status"], fit_error=audit["fit_error"])
        return baseline_test, baseline_train, np.full(len(test), "fit_failed:", dtype=object) + baseline_reason, audit


def _participation(train: pd.DataFrame, test: pd.DataFrame, *, state: dict | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    labels = _strings(train, "participation_state")
    known = np.isin(labels, ["played", "DNP"])
    audit = {"known_training_rows": int(known.sum()), "played_rows": int((labels == "played").sum()), "DNP_rows": int((labels == "DNP").sum()), "unknown_rows": int((~known).sum())}
    if not known.any():
        if state is not None:
            state.update(kind="unavailable")
        return np.full(len(test), np.nan), audit
    y = (labels == "played").astype(float)
    gp = float((y[known].sum() + 1) / (known.sum() + 2))
    positions = _strings(train, "position")
    lookup = {}
    for position in np.unique(positions[known]):
        rows = known & (positions == position)
        lookup[str(position)] = float((y[rows].sum() + 8 * gp) / (rows.sum() + 8))
    if state is not None:
        state.update(kind="participation", global_rate=gp, position_rates=lookup)
    prior = np.array([lookup.get(str(p), gp) for p in _strings(test, "position")])
    rate, count = _numeric(test, "f_player_play_rate8"), _numeric(test, "f_player_known_participation_n8")
    valid = np.isfinite(rate) & np.isfinite(count) & (rate >= 0) & (rate <= 1) & (count > 0)
    count = np.where(valid, np.minimum(count, 8), 0)
    result = (np.where(valid, rate, 0) * count + 8 * prior) / (count + 8)
    audit["global_beta_smoothed_rate"] = gp
    audit["limitation"] = "estimates participation in the supplied known-state population; missing box scores are not DNP"
    return result, audit


def _dispersion(train: pd.DataFrame, target: str, fitted: np.ndarray, global_prior: _Prior, position_priors: dict[str, _Prior], test: pd.DataFrame, mean: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    y = _numeric(train, target)
    residual_sq = (y - fitted) ** 2
    valid = np.isfinite(residual_sq) & np.isfinite(fitted)
    position = _strings(train, "position")
    def estimate(rows: np.ndarray) -> float:
        if target in COUNT_TARGETS:
            denominator = float(np.sum(fitted[rows] ** 2))
            return float(np.clip(np.sum(residual_sq[rows] - y[rows]) / max(denominator, 1), 0, 10))
        return float(max(np.mean(residual_sq[rows]), 1e-6))
    global_disp = estimate(valid) if valid.any() else global_prior.variance
    lookup = {}
    for p in np.unique(position[valid]):
        rows = valid & (position == p)
        local = estimate(rows)
        lookup[str(p)] = (rows.sum() * local + 30 * global_disp) / (rows.sum() + 30)
    value = np.array([lookup.get(str(p), global_disp) for p in _strings(test, "position")])
    if target in COUNT_TARGETS:
        variance = mean + value * mean ** 2
    else:
        variance = value
    return np.sqrt(np.maximum(variance, 0)), {"dispersion_kind": "NB2_alpha" if target in COUNT_TARGETS else "normal_residual_variance", "global_dispersion": global_disp, "position_dispersion": lookup, "fit_population": "training fitted residuals; calibration not established"}


def _quantiles(mean: np.ndarray, scale: np.ndarray, target: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    quantiles = []
    if target == "anytime_td":
        return tuple(bernoulli.ppf(q, mean) for q in (0.1, 0.5, 0.9))
    if target not in COUNT_TARGETS:
        return tuple(norm.ppf(q, loc=mean, scale=scale) for q in (0.1, 0.5, 0.9))
    for q in (0.1, 0.5, 0.9):
        values = np.full(len(mean), np.nan)
        zero = np.isfinite(mean) & np.isfinite(scale) & (mean == 0)
        values[zero] = 0
        valid = np.isfinite(mean) & np.isfinite(scale) & (mean > 0)
        over = valid & (scale ** 2 > mean + 1e-10)
        r = np.divide(mean ** 2, scale ** 2 - mean, out=np.ones(len(mean)), where=over)
        p = np.divide(r, r + mean, out=np.ones(len(mean)), where=over)
        values[over] = nbinom.ppf(q, r[over], p[over])
        equi = valid & ~over
        values[equi] = poisson.ppf(q, mean[equi])
        quantiles.append(values)
    return tuple(quantiles)


def _archived(test: pd.DataFrame, target: str, method: str) -> tuple[np.ndarray, np.ndarray]:
    prefix = f"baseline_{method}"
    value = _numeric(test, f"{prefix}_{target}")
    verified = test.get(f"{prefix}_cutoff_verified", pd.Series(False, index=test.index)).map(lambda v: isinstance(v, (bool, np.bool_)) and bool(v)).to_numpy(dtype=bool)
    forecast_time = pd.to_datetime(test.get(f"{prefix}_forecast_utc", pd.Series(pd.NaT, index=test.index)), utc=True, errors="coerce")
    kickoff = pd.to_datetime(test.get("kickoff_utc", pd.Series(pd.NaT, index=test.index)), utc=True, errors="coerce")
    hashes = _strings(test, f"{prefix}_source_sha256")
    hash_ok = np.array([bool(re.fullmatch(r"[a-fA-F0-9]{64}", str(value))) for value in hashes])
    # Archived count points may be fractional expectations; outcomes may not.
    support = np.isfinite(value)
    if target in COUNT_TARGETS:
        support &= value >= 0
    if target == "anytime_td":
        support &= (value >= 0) & (value <= 1)
    valid = support & verified & hash_ok & forecast_time.notna().to_numpy() & kickoff.notna().to_numpy() & (forecast_time < kickoff).to_numpy()
    return np.where(valid, value, np.nan), np.where(valid, "", "no_authentic_pregame_baseline_binding").astype(object)


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, target: str, method: str, *, artifact_path: Path | str | None = None) -> pd.DataFrame:
    """Fit one preregistered candidate and return forecasts indexed like ``test``.

    Required outcome support is an explicit ``participation_state == 'played'``
    and a finite supported target. Missing labels, known DNPs and unknown states
    never become played zeros. Only earlier labels are used when kickoff clocks
    are supplied. Numeric model inputs are qualified ``f_`` histories/context;
    metadata position/team/opponent are encoded from training categories only.

    The twelve names in ``METHODS`` are the complete finite candidate budget.
    Ensemble weights (ridge .50, workload .25, recent .25), ridge penalties,
    tree bounds and dispersion rules are fixed before evaluation. Attributes
    contain JSON-serializable fit parameters, exclusions and limitations.
    """
    if target not in TARGETS:
        raise ValueError(f"unsupported target: {target}")
    if method not in METHODS:
        raise ValueError(f"unregistered candidate: {method}")
    if artifact_path is not None and (Path(artifact_path).exists() or Path(artifact_path).is_symlink()):
        raise FileExistsError(f"immutable model artifact already exists: {artifact_path}")
    inference_state: dict | None = {"kind": "unavailable"} if artifact_path is not None else None
    participation_state: dict | None = {} if artifact_path is not None else None
    earlier, time_audit = _temporal_training(train, test)
    participation, participation_audit = _participation(earlier, test, state=participation_state)
    y = _numeric(earlier, target)
    valid = (_strings(earlier, "participation_state") == "played") & _support(y, target)
    supported = earlier.loc[valid].copy()
    audit: dict[str, Any] = {"model_version": MODEL_VERSION, "target": target, "method": method, "seed": SEED,
                             "temporal_training": time_audit, "supported_played_training_rows": len(supported),
                             "excluded_unsupported_or_not_played_rows": int((~valid).sum()),
                             "participation": participation_audit, "conditional_on": "played",
                             "scale_semantics": "conditional standard deviation", "count_support": "nonnegative integers",
                             "historical_method_status": "new reconstruction; no claim to reproduce missing original runners",
                             "feature_time_requirement": "caller-qualified pregame/lagged f_ features; prefix does not authenticate timing"}
    mean = np.full(len(test), np.nan)
    scale = np.full(len(test), np.nan)
    reason = np.full(len(test), "no_supported_played_training_outcomes", dtype=object)
    if method in {"raw_sleeper", "pinned_website"}:
        mean, reason = _archived(test, target, method)
        audit["distribution_status"] = "authentic point only; no invented conditional distribution"
        if inference_state is not None:
            inference_state.update(kind="archived", method=method, target=target)
    elif len(supported):
        gp, pp = _priors(supported, target)
        audit["position_priors"] = {p: vars(prior) for p, prior in pp.items()}
        audit["global_prior"] = vars(gp)
        if method in {"recent", "pooled", "workload"}:
            fn = _workload if method == "workload" else _recent
            kwargs = {"window": 8} if method == "pooled" else {}
            mean, reason = fn(supported, test, target, gp, pp, state=inference_state, **kwargs)
            fitted, _ = fn(supported, supported, target, gp, pp, fitting=True, **kwargs)
        elif method == "ensemble":
            ridge_state, workload_state, recent_state = {}, {}, {}
            ridge, fit_ridge, ridge_reason, ml_audit = _ml(supported, test, target, "ridge", gp, pp, state=ridge_state if inference_state is not None else None)
            workload, workload_reason = _workload(supported, test, target, gp, pp, state=workload_state if inference_state is not None else None)
            fit_workload, _ = _workload(supported, supported, target, gp, pp, fitting=True)
            recent, recent_reason = _recent(supported, test, target, gp, pp, state=recent_state if inference_state is not None else None)
            fit_recent, _ = _recent(supported, supported, target, gp, pp, fitting=True)
            mean = .5 * ridge + .25 * workload + .25 * recent
            fitted = .5 * fit_ridge + .25 * fit_workload + .25 * fit_recent
            reason = np.array([";".join(sorted({str(r) for r in row if r})) for row in zip(ridge_reason, workload_reason, recent_reason)], dtype=object)
            audit["fitted_model"] = ml_audit
            audit["ensemble_weights"] = {"ridge": .5, "workload": .25, "recent": .25}
            if inference_state is not None:
                inference_state.update(kind="ensemble", weights=[.5, .25, .25], components=[ridge_state, workload_state, recent_state])
        else:
            mean, fitted, reason, ml_audit = _ml(supported, test, target, method, gp, pp, state=inference_state)
            audit["fitted_model"] = ml_audit
        if target == "anytime_td":
            mean = np.clip(mean, 0, 1)
        elif target in COUNT_TARGETS:
            mean = np.maximum(mean, 0)
        if target != "anytime_td":
            scale, dispersion_audit = _dispersion(supported, target, fitted, gp, pp, test, mean)
            audit["distribution_fit"] = dispersion_audit
    if target == "anytime_td":
        scale = np.sqrt(mean * (1 - mean))
    p10, p50, p90 = _quantiles(mean, scale, target)
    result = pd.DataFrame({"mean": mean, "scale": scale, "family": _family(target), "p10": p10, "p50": p50, "p90": p90,
                           "p_participation": participation, "fallback": reason}, index=test.index)
    audit["fallback_rows"] = int(np.sum(reason != ""))
    audit["abstention_rows"] = int(np.sum(~np.isfinite(mean)))
    result.attrs.update(audit)
    if artifact_path is not None:
        from .model_artifacts import export_artifact
        export_artifact(artifact_path, inference_state, participation_state, audit, test)
    return result


def coherent_completion_samples(attempts: np.ndarray, completion_probability: float | np.ndarray, *, seed: int = SEED) -> np.ndarray:
    """Draw coherent completions given integer attempts and an actual rate.

    A completion rate is not the marginal completion mean. Invalid inputs raise
    instead of rounding/clamping incompatible forecasts into a claimed repair.
    This helper is a new joint construction, distinct from retained site points.
    """
    attempts = np.asarray(attempts, dtype=float)
    rate = np.asarray(completion_probability, dtype=float)
    if not np.all(np.isfinite(attempts) & (attempts >= 0) & (attempts == np.floor(attempts))):
        raise ValueError("attempt samples must have nonnegative integer support")
    if not np.all(np.isfinite(rate) & (rate >= 0) & (rate <= 1)):
        raise ValueError("completion probability must be in [0,1]")
    return np.random.default_rng(seed).binomial(attempts.astype(np.int64), rate)
