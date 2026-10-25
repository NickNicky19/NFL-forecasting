"""Fixed-grid monotone threshold CDF research model, conditional on played.

One classifier learns P(Y <= t | X) from copies of each supported training
row at every registered threshold. Only the threshold has a monotone constraint.
Bin masses retain training-only empirical frequencies within each interval;
an empty interval receives its predeclared legal integer representative.
The Bernoulli case instead learns the native event P(Y=1 | X) directly.

StableMixtureBatch is also usable around an incumbent MixtureBatch. Its versioned
arithmetic accepts only normalized histograms within the incumbent's 1e-12
tolerance. It divides the nonnegative cumulative histogram by its own terminal
binary64 sum, then reconstructs masses by adjacent differences. Thus the stored
PMF, moments and cumulative use the same normalized law, and the last cumulative
entry is exactly one. CDF support boundaries and infinite limits are assigned
their mathematical values explicitly. Invalid probabilities are rejected;
there is no probability floor or substantive probability clipping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from .cdf_engine import (
    FixedDesign, KEYS, MixtureBatch, PRIOR_WEIGHT, SupportPrior,
    numeric, strings, valid_support, validate_category,
)

VERSION = "monotone-threshold-cdf-v1-20261025"
STABLE_MIXTURE_VERSION = "normalized-cumulative-mixture-v1-20261025"
THREADS = 2
CLASSIFIER_PARAMETERS = dict(max_iter=60, max_leaf_nodes=15, min_samples_leaf=40,
                             l2_regularization=10., learning_rate=.05,
                             early_stopping=False, random_state=1911)
THRESHOLD_GRIDS = {
    "pass_yd": (-25, 0, 50, 100, 150, 200, 250, 300, 350, 400, 500),
    "pass_td": (0, 1, 2, 3, 4),
    "pass_cmp": (0, 5, 10, 15, 20, 25, 30, 35),
    "pass_att": (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50),
    "pass_int": (0, 1, 2, 3),
    "rush_yd": (-10, 0, 10, 25, 50, 75, 100, 150, 200),
    "rush_att": (0, 2, 5, 10, 15, 20, 25, 30),
    "rec": (0, 1, 2, 3, 4, 5, 7, 10, 15),
    "rec_yd": (-10, 0, 10, 25, 50, 75, 100, 150, 200),
    "rush_rec_yd": (-10, 0, 20, 40, 60, 80, 100, 150, 200, 250),
}


class StableMixtureBatch(MixtureBatch):
    """MixtureBatch contract with a normalized PMF and exact CDF endpoints."""

    version = STABLE_MIXTURE_VERSION

    def __init__(self, support, weights, prior: SupportPrior, *, prior_weight=PRIOR_WEIGHT):
        # Inherit support, nonnegative mass and 1e-12 normalization validation.
        super().__init__(support, weights, prior, prior_weight=prior_weight)
        if not len(self.support):
            raise ValueError("empirical support must not be empty")
        parameter = prior.p if prior.support == "bernoulli" else prior.q
        if not np.isfinite(parameter) or not 0 < parameter < 1:
            raise ValueError("prior requires a valid full-support parameter")
        cumulative = np.cumsum(self.weights, axis=1)
        self.cumulative = cumulative / cumulative[:, -1:]
        self.weights = np.diff(self.cumulative, axis=1, prepend=0.)
        self.weighted_cumulative = np.cumsum(self.weights * self.support, axis=1)

    @classmethod
    def from_batch(cls, batch: MixtureBatch):
        return cls(batch.support, batch.weights, batch.prior, prior_weight=batch.b)

    def cdf(self, x):
        x, slots, index = self._thresholds(np.floor(x))
        if np.isnan(x).any():
            raise ValueError("CDF threshold must not be NaN")
        empirical = np.where(slots >= 0, self.cumulative[np.arange(len(self.weights)), index], 0.)
        prior_cdf = self.prior.cdf(x)
        if not np.isfinite(prior_cdf).all() or ((prior_cdf < 0) | (prior_cdf > 1)).any():
            raise ValueError("prior returned invalid CDF probabilities")
        result = self.a * empirical + self.b * prior_cdf
        result = np.where(np.isneginf(x), 0., np.where(np.isposinf(x), 1., result))
        if self.prior.support in {"count", "bernoulli"}:
            result = np.where(x < 0, 0., result)
        if self.prior.support == "bernoulli":
            result = np.where(x >= 1, 1., result)
        if not np.isfinite(result).all() or ((result < 0) | (result > 1)).any():
            raise ValueError("mixture returned invalid CDF probabilities")
        return result

    def logpmf(self, x):
        x, slots, index = self._thresholds(x)
        valid = valid_support(x, self.prior.support)
        matches = valid & (slots >= 0) & (self.support[index] == x)
        empirical = np.where(matches, self.weights[np.arange(len(self.weights)), index], 0.)
        # Evaluate the prior on legal inputs only; invalid +/-inf gets -inf mass.
        prior_logmass = self.prior.logpmf(np.where(valid, x, 0.))
        with np.errstate(divide="ignore"):
            value = np.logaddexp(np.log(self.a) + np.log(empirical), np.log(self.b) + prior_logmass)
        return np.where(valid, value, -np.inf)

    @property
    def median(self):
        return self.quantile(.5)


def _event_probability(classifier, x):
    """The single-class case still denotes its actual native binary event."""
    classes = list(classifier.classes_)
    if 1 not in classes:
        return np.zeros(len(x))
    if len(classes) == 1:
        return np.ones(len(x))
    probability = classifier.predict_proba(x)[:, classes.index(1)]
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError("classifier returned invalid event probabilities")
    return probability


def _binding_hash(frame):
    return hashlib.sha256(pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes()).hexdigest()


@dataclass
class ThresholdCDFModel:
    category: dict
    panel: str
    design: FixedDesign | None = None
    classifier: HistGradientBoostingClassifier | None = None
    support: np.ndarray = field(default_factory=lambda: np.array([0.]))
    thresholds: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    bin_histograms: np.ndarray | None = None
    priors: dict[str, SupportPrior] = field(default_factory=dict)
    global_prior: SupportPrior | None = None
    audit: dict = field(default_factory=dict)
    training_binding: pd.DataFrame | None = None
    prior_training_binding: pd.DataFrame | None = None

    @classmethod
    def fit(cls, train: pd.DataFrame, category: dict, panel: str):
        validate_category(category)
        if panel not in category["panels"]:
            raise ValueError("unknown fixed feature panel")
        target, support = category["target"], category["support"]
        if support != "bernoulli" and target not in THRESHOLD_GRIDS:
            raise ValueError("no registered threshold grid for target: " + target)
        y = numeric(train, target)
        played = strings(train, "participation_state") == "played"
        supported_mask = valid_support(y, support)
        good = played & supported_mask
        supported = train.loc[good]
        model = cls(category, panel)
        model.thresholds = np.asarray(THRESHOLD_GRIDS[target], dtype=float) if support != "bernoulli" else np.array([])
        model.audit = {
            "version": VERSION, "law_arithmetic_version": STABLE_MIXTURE_VERSION,
            "training_rows": len(train), "supported_played_training_rows": int(good.sum()),
            "played_missing_outcome": int((played & ~np.isfinite(y)).sum()),
            "played_invalid_support": int((played & np.isfinite(y) & ~supported_mask).sum()),
            "participation_states": train.participation_state.value_counts(dropna=False).to_dict(),
            "classifier_parameters": dict(CLASSIFIER_PARAMETERS), "threads": THREADS,
            "prior_weight": PRIOR_WEIGHT, "thresholds": model.thresholds.tolist(),
            "numeric_features": list(category["panels"][panel]),
            "procedure": "native_binary_event" if support == "bernoulli" else "one_monotone_threshold_classifier",
            "probability_semantics": "conditional_on_played; marginal_only; calibration_unestablished",
            "within_bin_rule": "modeled_training_empirical_frequencies; empty:first0_count_or_firstcut_signed,interior_leftplus1,high_lastplus1",
        }
        if not len(supported):
            model.audit["fit_state"] = "NO_SUPPORTED_TRAINING_LABELS"
            return model
        columns = [c for c in KEYS + ["position", "kickoff_utc", "outcome_available_utc", target] if c in supported]
        model.prior_training_binding = supported[columns].copy()
        model.global_prior = SupportPrior.fit(y[good], support)
        for role, group in supported.groupby("position", dropna=True):
            model.priors[str(role)] = SupportPrior.fit(numeric(group, target), support)
        modeled = supported.loc[supported.position.isin(category["modeled_roles"])]
        model.training_binding = modeled[columns].copy()
        model.audit.update(modeled_training_rows=len(modeled),
                           prior_training_binding_sha256=_binding_hash(model.prior_training_binding),
                           modeled_training_binding_sha256=_binding_hash(model.training_binding),
                           role_priors={role: vars(prior) for role, prior in model.priors.items()},
                           global_prior=vars(model.global_prior))
        if len(modeled) < 2 * CLASSIFIER_PARAMETERS["min_samples_leaf"]:
            model.audit["fit_state"] = "INSUFFICIENT_MODELED_TRAINING"
            return model
        model.design = FixedDesign.fit(modeled, category["panels"][panel])
        x, y = model.design.transform(modeled), numeric(modeled, target)
        feature_names = [part for name in model.design.names for part in (name, name + "__missing")]
        feature_names += ["position=" + role for role in model.design.roles]
        if support == "bernoulli":
            fit_x, fit_y = x, y.astype(np.int8)
            monotonic = [0] * x.shape[1]
            model.support = np.array([0., 1.])
        else:
            k = len(model.thresholds)
            fit_x = np.column_stack([np.repeat(x, k, axis=0), np.tile(model.thresholds, len(x))])
            fit_y = (np.repeat(y, k) <= np.tile(model.thresholds, len(y))).astype(np.int8)
            monotonic = [0] * x.shape[1] + [1]
            feature_names += ["__cdf_threshold"]
            bins = np.searchsorted(model.thresholds, y, side="left")
            representatives = np.r_[0 if support == "count" else model.thresholds[0], model.thresholds + 1]
            counts = np.bincount(bins, minlength=k + 1)
            model.support = np.unique(np.r_[y, representatives[counts == 0]])
            model.bin_histograms = np.zeros((k + 1, len(model.support)))
            for slot in range(k + 1):
                if counts[slot]:
                    atoms, frequency = np.unique(y[bins == slot], return_counts=True)
                    model.bin_histograms[slot, np.searchsorted(model.support, atoms)] = frequency / counts[slot]
                else:
                    model.bin_histograms[slot, np.searchsorted(model.support, representatives[slot])] = 1.
            model.audit.update(training_bin_counts=counts.tolist(),
                               empty_bin_representatives={str(i): float(representatives[i]) for i in np.flatnonzero(counts == 0)})
        with threadpool_limits(limits=THREADS):
            model.classifier = HistGradientBoostingClassifier(**CLASSIFIER_PARAMETERS, monotonic_cst=monotonic).fit(fit_x, fit_y)
        model.audit.update(fit_state="FITTED", expanded_training_rows=len(fit_y),
                           binary_training_class_counts=np.bincount(fit_y, minlength=2).tolist(),
                           classifier_count=1, feature_names=feature_names, monotonic_cst=monotonic,
                           numeric_medians=model.design.medians, categorical_roles=model.design.roles,
                           empirical_support_size=len(model.support))
        return model

    def threshold_probabilities(self, frame: pd.DataFrame):
        """Return raw constrained P(Y<=t), or native P(event) as one column."""
        if self.classifier is None or self.design is None:
            raise ValueError("model has no fitted classifier")
        x = self.design.transform(frame)
        with threadpool_limits(limits=THREADS):
            if self.category["support"] == "bernoulli":
                return _event_probability(self.classifier, x)[:, None]
            k = len(self.thresholds)
            expanded = np.column_stack([np.repeat(x, k, axis=0), np.tile(self.thresholds, len(x))])
            probabilities = _event_probability(self.classifier, expanded).reshape(len(x), k)
        if (np.diff(probabilities, axis=1) < 0).any():
            raise ValueError("threshold classifier violated its monotone constraint")
        return probabilities

    def predict_batches(self, frame: pd.DataFrame, batch_size=128, *, prior_only=False):
        """Yield positional indices, exact laws and explicit fallback reasons."""
        if not isinstance(batch_size, (int, np.integer)) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        roles = strings(frame, "position")
        history = numeric(frame, "f_player_games_prior")
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
            elif self.classifier is None:
                reason[:] = "insufficient_modeled_training_role_prior"
            else:
                reason[~np.isfinite(history[positions]) | (history[positions] < 1)] = "cold_start_role_prior"
            if str(role) not in self.priors:
                reason[:] = "global_prior_unknown_role"
            for fallback in [False, True]:
                indices = positions[(reason != "") == fallback]
                for start in range(0, len(indices), batch_size):
                    batch = indices[start:start + batch_size]
                    batch_reason = reason[np.searchsorted(positions, batch)]
                    if fallback:
                        law = StableMixtureBatch([0.], np.ones((len(batch), 1)), prior, prior_weight=1.)
                    else:
                        probability = self.threshold_probabilities(frame.iloc[batch])
                        if self.category["support"] == "bernoulli":
                            weights = np.column_stack([1 - probability[:, 0], probability[:, 0]])
                        else:
                            masses = np.diff(probability, axis=1, prepend=0., append=1.)
                            weights = masses @ self.bin_histograms
                        law = StableMixtureBatch(self.support, weights, prior)
                    yield batch, law, batch_reason

    def save(self, directory: Path):
        import joblib
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        artifact = directory / "model.joblib"
        joblib.dump(self, artifact, compress=3)
        with artifact.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        manifest = {"version": VERSION, "law_arithmetic_version": STABLE_MIXTURE_VERSION,
                    "artifact": artifact.name, "sha256": digest,
                    "audit": self.audit, "category": self.category, "panel": self.panel}
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        return manifest
