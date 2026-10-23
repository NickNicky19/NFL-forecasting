"""Registered empirical-leaf marginal laws; no operational default is changed.

Every law is conditional on played. The tree partitions use old labels only;
each leaf retains the original labels rather than an invented residual family.
Signed integer yards, counts, and Bernoulli events share this implementation.
The exact support prior gives positive mass without probability clipping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits

VERSION = "all12-leaf-cdf-v1-20261023"
PRIOR_WEIGHT = .05
TREE_PARAMETERS = dict(n_estimators=32, criterion="squared_error", max_depth=8,
                       min_samples_leaf=30, max_features=1.0, bootstrap=False,
                       random_state=1701, n_jobs=2)
COUNT_MEAN_FLOOR = .05
SIGNED_SCALE_FLOOR = 1.0
KEYS = ["season", "week", "game_id", "player_id"]
SUPPORTS = {"signed_integer", "count", "bernoulli"}
_FORBIDDEN = re.compile(r"(?:^|_)(?:actual|outcome|future|postgame|realized|label|next|current_game|same_game)(?:_|$)")


def numeric(frame: pd.DataFrame, name: str) -> np.ndarray:
    if name not in frame:
        return np.full(len(frame), np.nan)
    return pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=float, na_value=np.nan)


def strings(frame: pd.DataFrame, name: str) -> np.ndarray:
    return frame[name].fillna("<unknown>").astype(str).to_numpy() if name in frame else np.full(len(frame), "<unknown>")


def valid_support(values, support: str) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    good = np.isfinite(values) & (values == np.floor(values))
    if support == "count":
        good &= values >= 0
    elif support == "bernoulli":
        good &= np.isin(values, [0, 1])
    elif support != "signed_integer":
        raise ValueError("unsupported exact label contract: " + support)
    return good


def validate_category(category: dict) -> None:
    if category["state"] != "READY":
        raise ValueError("category is blocked: " + category["state"])
    if category["support"] not in SUPPORTS:
        raise ValueError("unsupported outcome support")
    if not category["modeled_roles"] or not category["primary_roles"]:
        raise ValueError("explicit role populations required")
    if not set(category["primary_roles"]) <= set(category["modeled_roles"]):
        raise ValueError("primary roles must be modeled")
    if set(category["panels"]) != {"base", "context"}:
        raise ValueError("exactly two fixed feature panels required")
    if not set(category["panels"]["base"]) <= set(category["panels"]["context"]):
        raise ValueError("context panel must include base")
    for names in category["panels"].values():
        if not names or len(names) != len(set(names)):
            raise ValueError("feature panel empty or duplicated")
        for name in names:
            if not name.startswith("f_") or _FORBIDDEN.search(name) or name == "f_" + category["target"]:
                raise ValueError("unqualified feature name: " + name)


def assert_clock_contract(frame: pd.DataFrame) -> None:
    required = KEYS + ["position", "kickoff_utc", "cutoff_utc", "outcome_available_utc",
                       "feature_max_source_available_utc", "participation_state"]
    if missing := set(required) - set(frame):
        raise ValueError("missing temporal/identity fields: " + repr(sorted(missing)))
    if frame[KEYS].isna().any(axis=None) or frame.duplicated(KEYS).any():
        raise ValueError("missing or duplicate player-game keys")
    cutoff = pd.to_datetime(frame.cutoff_utc, utc=True, errors="coerce")
    kickoff = pd.to_datetime(frame.kickoff_utc, utc=True, errors="coerce")
    source = pd.to_datetime(frame.feature_max_source_available_utc, utc=True, errors="coerce")
    if cutoff.isna().any() or kickoff.isna().any() or (cutoff > kickoff).any():
        raise ValueError("invalid cutoff/kickoff")
    if (source.notna() & (source >= cutoff)).any():
        raise ValueError("feature source is not strictly earlier than cutoff")
    if not frame.participation_state.isin(["played", "DNP", "unknown"]).all():
        raise ValueError("unrecognized participation state")


def chronological_split(frame: pd.DataFrame, season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    assert_clock_contract(frame)
    test = frame.loc[frame.season.eq(season)].copy()
    if test.empty:
        return frame.iloc[:0].copy(), test
    cutoff = pd.to_datetime(test.cutoff_utc, utc=True).min()
    kickoff = pd.to_datetime(frame.kickoff_utc, utc=True)
    available = pd.to_datetime(frame.outcome_available_utc, utc=True, errors="coerce")
    train = frame.loc[(frame.season < season) & (kickoff < cutoff) & available.notna() & (available < cutoff)]
    return train.sort_values(["kickoff_utc", "game_id", "player_id"], kind="stable").copy(), test


def assert_composite_contract(frame: pd.DataFrame, category: dict):
    """A composite nonmissing label requires every supported source component.

    This assertion never constructs missing outcomes or overwrites the pinned
    cache. A bad adapter blocks its category rather than silently losing rows.
    """
    target = category["target"]
    if target not in {"anytime_td", "rush_rec_yd"}:
        return
    y = numeric(frame, target)
    has_label = np.isfinite(y)
    if target == "anytime_td":
        rush, rec = numeric(frame, "rush_td"), numeric(frame, "rec_td")
        supported = valid_support(rush, "count") & valid_support(rec, "count")
        expected = ((rush + rec) > 0).astype(float)
    else:
        rush, rec = numeric(frame, "rush_yd"), numeric(frame, "rec_yd")
        supported = valid_support(rush, "signed_integer") & valid_support(rec, "signed_integer")
        expected = rush + rec
    if (has_label & (~supported | (y != expected))).any():
        raise ValueError("source-invalid composite target: " + target)


@dataclass(frozen=True)
class SupportPrior:
    support: str
    center: int = 0
    q: float = 0.0
    p: float = 0.0
    n: int = 0

    @classmethod
    def fit(cls, y, support: str):
        y = np.asarray(y, dtype=float)
        if not len(y) or not valid_support(y, support).all():
            raise ValueError("prior requires supported old played outcomes")
        if support == "bernoulli":
            return cls(support, p=float((y.sum() + 1) / (len(y) + 2)), n=len(y))
        if support == "count":
            mu = max(COUNT_MEAN_FLOOR, float(y.mean()))
            return cls(support, q=mu / (1 + mu), n=len(y))
        center = int(np.partition(y, (len(y) - 1) // 2)[(len(y) - 1) // 2])
        scale = max(SIGNED_SCALE_FLOOR, float(np.abs(y - center).mean()))
        return cls(support, center=center, q=scale / (1 + scale), n=len(y))

    @property
    def mean(self):
        return self.p if self.support == "bernoulli" else self.q / (1 - self.q) if self.support == "count" else float(self.center)

    @property
    def variance(self):
        return self.p * (1 - self.p) if self.support == "bernoulli" else (1 if self.support == "count" else 2) * self.q / (1 - self.q) ** 2

    def logpmf(self, x):
        x = np.asarray(x, dtype=float)
        valid = valid_support(x, self.support)
        if self.support == "bernoulli":
            value = np.where(x == 1, np.log(self.p), np.log1p(-self.p))
        elif self.support == "count":
            value = np.log1p(-self.q) + x * np.log(self.q)
        else:
            value = np.log1p(-self.q) - np.log1p(self.q) + np.abs(x - self.center) * np.log(self.q)
        return np.where(valid, value, -np.inf)

    def cdf(self, x):
        x = np.floor(np.asarray(x, dtype=float))
        if self.support == "bernoulli":
            return np.where(x < 0, 0., np.where(x < 1, 1 - self.p, 1.))
        if self.support == "count":
            return np.where(x < 0, 0., -np.expm1((np.maximum(x, 0) + 1) * np.log(self.q)))
        d = x - self.center
        # Evaluate only nonnegative exponents, avoiding overflow in the unused arm.
        return np.where(d < 0, np.power(self.q, np.maximum(-d, 0)) / (1 + self.q),
                        1 - np.power(self.q, np.maximum(d + 1, 0)) / (1 + self.q))

    def absolute_moment(self, x):
        """E|P-x| at integer x; no truncation of infinite support."""
        x = np.asarray(x, dtype=float)
        if not (np.isfinite(x) & (x == np.floor(x))).all():
            raise ValueError("absolute moment requires integer threshold")
        if self.support == "bernoulli":
            return (1 - self.p) * np.abs(x) + self.p * np.abs(1 - x)
        if self.support == "count":
            nonnegative = np.maximum(x, 0)
            value = nonnegative - self.mean + 2 * self.q ** (nonnegative + 1) / (1 - self.q)
            return np.where(x < 0, self.mean - x, value)
        d = np.abs(x - self.center)
        return d + 2 * self.q ** (d + 1) / (1 - self.q ** 2)

    @property
    def pair_absolute_moment(self):
        """E|P-P'| for independent draws from the same PRIOR only."""
        q = self.q
        if self.support == "bernoulli":
            return 2 * self.p * (1 - self.p)
        if self.support == "count":
            return 2 * q / (1 - q ** 2)
        return 4 * q * (1 + q + q ** 2) / ((1 - q) * (1 + q) ** 3)


class MixtureBatch:
    """Rows share finite empirical support and one full-support role prior."""
    def __init__(self, support, weights, prior: SupportPrior, *, prior_weight=PRIOR_WEIGHT):
        self.support = np.asarray(support, dtype=float)
        self.weights = np.atleast_2d(np.asarray(weights, dtype=float))
        self.prior = prior
        self.b = float(prior_weight)
        self.a = 1 - self.b
        if not 0 <= self.b <= 1 or not valid_support(self.support, prior.support).all():
            raise ValueError("invalid mixture support/weight")
        if len(self.support) and (not (np.diff(self.support) > 0).all()):
            raise ValueError("empirical support must be sorted unique")
        if self.weights.shape[1] != len(self.support) or not np.isfinite(self.weights).all() or (self.weights < 0).any():
            raise ValueError("invalid empirical histogram")
        if not np.allclose(self.weights.sum(axis=1), 1., atol=1e-12, rtol=0):
            raise ValueError("empirical histogram does not sum to one")
        self.cumulative = np.cumsum(self.weights, axis=1)
        self.weighted_cumulative = np.cumsum(self.weights * self.support, axis=1)

    def _thresholds(self, x):
        x = np.broadcast_to(np.asarray(x, dtype=float), (len(self.weights),))
        slots = np.searchsorted(self.support, x, side="right") - 1
        index = np.maximum(slots, 0)
        return x, slots, index

    def cdf(self, x):
        x, slots, index = self._thresholds(np.floor(x))
        empirical = np.where(slots >= 0, self.cumulative[np.arange(len(self.weights)), index], 0.)
        return self.a * empirical + self.b * self.prior.cdf(x)

    def logpmf(self, x):
        x, slots, index = self._thresholds(x)
        matches = (slots >= 0) & (self.support[index] == x)
        empirical = np.where(matches, self.weights[np.arange(len(self.weights)), index], 0.)
        with np.errstate(divide="ignore"):
            return np.logaddexp(np.log(self.a) + np.log(empirical), np.log(self.b) + self.prior.logpmf(x))

    @property
    def mean(self):
        return self.a * (self.weights @ self.support) + self.b * self.prior.mean

    @property
    def variance(self):
        second = self.a * (self.weights @ self.support ** 2) + self.b * (self.prior.variance + self.prior.mean ** 2)
        return np.maximum(second - self.mean ** 2, 0.)

    def quantile(self, p: float):
        if not 0 < p < 1:
            raise ValueError("finite quantiles require 0<p<1")
        n = len(self.weights)
        low = np.full(n, min(int(self.support.min()) - 1, self.prior.center - 1, -1), dtype=np.int64)
        high = np.full(n, max(int(self.support.max()), self.prior.center, 1), dtype=np.int64)
        # Geometrically expand support until the exact full law brackets p.
        step = 1
        for _ in range(63):
            move_low, move_high = self.cdf(low) >= p, self.cdf(high) < p
            if not move_low.any() and not move_high.any():
                break
            low[move_low] -= step
            high[move_high] += step
            step *= 2
        else:
            raise ValueError("quantile exceeds int64 numerical budget")
        while (high - low > 1).any():
            middle = low + (high - low) // 2
            upper = self.cdf(middle) >= p
            high = np.where(upper, middle, high)
            low = np.where(upper, low, middle)
        return high.astype(float)

    def crps(self, y):
        y = np.broadcast_to(np.asarray(y, dtype=float), (len(self.weights),))
        if not valid_support(y, self.prior.support).all():
            raise ValueError("CRPS outcome violates law support")
        empirical_y = np.sum(self.weights * np.abs(self.support[None, :] - y[:, None]), axis=1)
        # For ordered atoms, E|E-E'|=2 sum_j w_j(s_j F_{j-1}-M_{j-1}).
        previous_mass = self.cumulative - self.weights
        previous_moment = self.weighted_cumulative - self.weights * self.support
        empirical_pair = 2 * np.sum(self.weights * (self.support * previous_mass - previous_moment), axis=1)
        cross = self.weights @ self.prior.absolute_moment(self.support)
        first = self.a * empirical_y + self.b * self.prior.absolute_moment(y)
        pair = self.a ** 2 * empirical_pair + 2 * self.a * self.b * cross + self.b ** 2 * self.prior.pair_absolute_moment
        result = first - .5 * pair
        if (result < -1e-8).any() or not np.isfinite(result).all():
            raise ValueError("invalid exact CRPS")
        return np.maximum(result, 0.)  # Remove floating roundoff, never clip mass.


@dataclass
class FixedDesign:
    names: list[str]
    medians: list[float]
    roles: list[str]

    @classmethod
    def fit(cls, frame: pd.DataFrame, names: list[str]):
        medians = []
        for name in names:
            values = numeric(frame, name)
            finite = values[np.isfinite(values)]
            medians.append(float(np.median(finite)) if len(finite) else 0.)
        return cls(list(names), medians, sorted(set(strings(frame, "position"))))

    def transform(self, frame: pd.DataFrame):
        columns = []
        for name, median in zip(self.names, self.medians):
            values = numeric(frame, name)
            missing = ~np.isfinite(values)
            columns.extend([np.where(missing, median, values), missing.astype(float)])
        role = strings(frame, "position")
        columns.extend([(role == value).astype(float) for value in self.roles])
        return np.asarray(np.column_stack(columns), dtype=np.float32)


@dataclass
class LeafCDFModel:
    category: dict
    panel: str
    design: FixedDesign | None
    forest: ExtraTreesRegressor | None
    support: np.ndarray
    leaf_histograms: list = field(default_factory=list)
    priors: dict[str, SupportPrior] = field(default_factory=dict)
    global_prior: SupportPrior | None = None
    audit: dict = field(default_factory=dict)
    training_binding: pd.DataFrame | None = None
    training_leaf_ids: np.ndarray | None = None
    prior_training_binding: pd.DataFrame | None = None

    @classmethod
    def fit(cls, train: pd.DataFrame, category: dict, panel: str):
        validate_category(category)
        target, support = category["target"], category["support"]
        y = numeric(train, target)
        played = strings(train, "participation_state") == "played"
        good = played & valid_support(y, support)
        supported = train.loc[good]
        model = cls(category, panel, None, None, np.array([0.]))
        model.audit = {"version": VERSION, "training_rows": len(train), "supported_played_training_rows": int(good.sum()),
                       "played_missing_outcome": int((played & ~np.isfinite(y)).sum()),
                       "played_invalid_support": int((played & np.isfinite(y) & ~valid_support(y, support)).sum()),
                       "participation_states": train.participation_state.value_counts(dropna=False).to_dict(),
                       "tree_parameters": TREE_PARAMETERS, "prior_weight": PRIOR_WEIGHT,
                       "probability_semantics": "conditional_on_played; marginal_only; calibration_unestablished"}
        if not len(supported):
            model.audit["fit_state"] = "NO_SUPPORTED_TRAINING_LABELS"
            return model
        binding_columns = [c for c in KEYS + ["position", "kickoff_utc", "outcome_available_utc", target] if c in supported]
        model.prior_training_binding = supported[binding_columns].copy()
        model.global_prior = SupportPrior.fit(y[good], support)
        for role, group in supported.groupby("position", dropna=True):
            model.priors[str(role)] = SupportPrior.fit(numeric(group, target), support)
        modeled = supported.loc[supported.position.isin(category["modeled_roles"])]
        model.training_binding = modeled[binding_columns].copy()
        model.audit["modeled_training_rows"] = len(modeled)
        model.audit["role_priors"] = {role: vars(prior) for role, prior in model.priors.items()}
        model.audit["global_prior"] = vars(model.global_prior)
        if len(modeled) < 2 * TREE_PARAMETERS["min_samples_leaf"]:
            model.audit["fit_state"] = "INSUFFICIENT_MODELED_TRAINING"
            return model
        model.design = FixedDesign.fit(modeled, category["panels"][panel])
        x, y = model.design.transform(modeled), numeric(modeled, target)
        with threadpool_limits(limits=2):
            model.forest = ExtraTreesRegressor(**TREE_PARAMETERS).fit(x, y)
            leaf_ids = model.forest.apply(x)
        model.training_leaf_ids = leaf_ids.astype(np.int32)
        model.support, codes = np.unique(y, return_inverse=True)
        for tree_index, tree in enumerate(model.forest.estimators_):
            leaf = leaf_ids[:, tree_index]
            counts = sparse.coo_matrix((np.ones(len(y)), (leaf, codes)), shape=(tree.tree_.node_count, len(model.support))).tocsr()
            totals = np.asarray(counts.sum(axis=1)).ravel()
            inverse = np.divide(1., totals, out=np.zeros_like(totals), where=totals > 0)
            model.leaf_histograms.append(sparse.diags(inverse) @ counts)
        model.audit.update(fit_state="FITTED", numeric_features=model.design.names,
                           numeric_medians=model.design.medians, categorical_roles=model.design.roles,
                           empirical_support_size=len(model.support),
                           leaf_histogram_nnz=int(sum(hist.nnz for hist in model.leaf_histograms)))
        return model

    def predict_batches(self, frame: pd.DataFrame, batch_size=256, *, prior_only=False):
        """Yield positions and exact laws. Never read target labels or participation."""
        roles = strings(frame, "position")
        history = numeric(frame, "f_player_games_prior")
        has_history_field = "f_player_games_prior" in frame
        leaf_ids = None
        if self.forest is not None and not prior_only:
            with threadpool_limits(limits=2):
                leaf_ids = self.forest.apply(self.design.transform(frame))
        for role in np.unique(roles):
            positions = np.flatnonzero(roles == role)
            prior = self.priors.get(str(role), self.global_prior)
            if prior is None:
                yield positions, None, np.full(len(positions), "no_supported_played_training_outcomes", dtype=object)
                continue
            reason = np.full(len(positions), "", dtype=object)
            if prior_only:
                reason[:] = "role_prior_control" if str(role) in self.priors else "global_prior_unknown_role"
            elif str(role) not in self.category["modeled_roles"]:
                reason[:] = "nonmodeled_role_prior"
            elif leaf_ids is None:
                reason[:] = "insufficient_modeled_training_role_prior"
            else:
                cold = (~np.isfinite(history[positions]) | (history[positions] <= 0)) if has_history_field else np.zeros(len(positions), dtype=bool)
                reason[cold] = "cold_start_role_prior"
            if str(role) not in self.priors:
                reason[:] = "global_prior_unknown_role"
            for fallback in [False, True]:
                indices = positions[(reason != "") == fallback]
                for start in range(0, len(indices), batch_size):
                    batch = indices[start:start + batch_size]
                    batch_reason = reason[np.searchsorted(positions, batch)]
                    if fallback:
                        law = MixtureBatch(np.array([0.]), np.ones((len(batch), 1)), prior, prior_weight=1.)
                    else:
                        weights = np.zeros((len(batch), len(self.support)))
                        for j, histogram in enumerate(self.leaf_histograms):
                            weights += histogram[leaf_ids[batch, j]].toarray()
                        weights /= len(self.leaf_histograms)
                        law = MixtureBatch(self.support, weights, prior)
                    yield batch, law, batch_reason

    def save(self, directory: Path):
        import joblib
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        artifact = directory / "model.joblib"
        joblib.dump(self, artifact, compress=3)
        manifest = {"version": VERSION, "artifact": artifact.name,
                    "sha256": hashlib.file_digest(artifact.open("rb"), "sha256").hexdigest(),
                    "audit": self.audit, "category": self.category, "panel": self.panel}
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        return manifest


def prediction_rows(model: LeafCDFModel, frame: pd.DataFrame, *, prior_only=False, score=False):
    """One deterministic inference/scoring pass; observed labels are optional.

    Callers freeze model/input bytes before scoring. ``score=False`` never reads
    target labels or participation. This function does not write external state.
    """
    result = frame[[c for c in KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc", "season_type"] if c in frame]].copy()
    result["target"] = model.category["target"]
    result["method"] = "role_prior" if prior_only else "leaf_cdf_" + model.panel
    result["evidence"] = "current_vintage_exposed_historical_reconstruction"
    result["distribution"] = "empirical_leaf_plus_support_prior"
    result["conditional_on"] = "played"
    result["primary_role"] = result.position.isin(model.category["primary_roles"])
    for col in ["mean", "median", "p10", "p90", "variance", "crps", "log_score", "cdf_actual_below", "cdf_actual", "brier"]:
        result[col] = np.nan
    result["fallback"] = "no_supported_played_training_outcomes"
    result["actual"] = numeric(frame, model.category["target"]) if score else np.nan
    result["participation_state"] = strings(frame, "participation_state") if score else "unread"
    actual = result.actual.to_numpy()
    played = result.participation_state.eq("played").to_numpy()
    valid = played & valid_support(actual, model.category["support"])
    result["outcome_state"] = np.where(~played, result.participation_state,
                              np.where(~np.isfinite(actual), "played_missing_statistic",
                              np.where(~valid, "played_invalid_support", np.where(actual == 0, "played_zero", "played_nonzero"))))
    for positions, law, fallback in model.predict_batches(frame, prior_only=prior_only):
        result.iloc[positions, result.columns.get_loc("fallback")] = fallback
        if law is None:
            continue
        for name, values in [("mean", law.mean), ("median", law.quantile(.5)), ("p10", law.quantile(.1)),
                             ("p90", law.quantile(.9)), ("variance", law.variance)]:
            result.iloc[positions, result.columns.get_loc(name)] = values
        if score:
            supported = valid[positions]
            if supported.any():
                selected = positions[supported]
                selected_law = MixtureBatch(law.support, law.weights[supported], law.prior, prior_weight=law.b)
                outcome = actual[selected]
                for name, values in [("crps", selected_law.crps(outcome)), ("log_score", -selected_law.logpmf(outcome)),
                                     ("cdf_actual_below", selected_law.cdf(outcome - 1)), ("cdf_actual", selected_law.cdf(outcome))]:
                    result.iloc[selected, result.columns.get_loc(name)] = values
                if model.category["support"] == "bernoulli":
                    result.iloc[selected, result.columns.get_loc("brier")] = (selected_law.mean - outcome) ** 2
    return result


def score_frozen_rows(model: LeafCDFModel, frame: pd.DataFrame, frozen: pd.DataFrame, *, prior_only=False):
    """Score once after a caller has written a prediction-freeze receipt."""
    if not frozen[KEYS].reset_index(drop=True).equals(frame[KEYS].reset_index(drop=True)):
        raise ValueError("frozen forecast identities/order differ from input")
    result = frozen.copy()
    actual = numeric(frame, model.category["target"])
    state = strings(frame, "participation_state")
    played = state == "played"
    valid = played & valid_support(actual, model.category["support"])
    result["actual"], result["participation_state"] = actual, state
    result["outcome_state"] = np.where(~played, state,
                              np.where(~np.isfinite(actual), "played_missing_statistic",
                              np.where(~valid, "played_invalid_support", np.where(actual == 0, "played_zero", "played_nonzero"))))
    for positions, law, _ in model.predict_batches(frame, prior_only=prior_only):
        if law is None:
            continue
        supported = valid[positions]
        if supported.any():
            selected = positions[supported]
            selected_law = MixtureBatch(law.support, law.weights[supported], law.prior, prior_weight=law.b)
            outcome = actual[selected]
            for name, values in [("crps", selected_law.crps(outcome)), ("log_score", -selected_law.logpmf(outcome)),
                                 ("cdf_actual_below", selected_law.cdf(outcome-1)), ("cdf_actual", selected_law.cdf(outcome))]:
                result.iloc[selected, result.columns.get_loc(name)] = values
            if model.category["support"] == "bernoulli":
                result.iloc[selected, result.columns.get_loc("brier")] = (numeric(result.iloc[selected], "mean")-outcome)**2
    return result
