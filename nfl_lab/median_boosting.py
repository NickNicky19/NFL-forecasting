"""Fixed MAE-directed point challenger; no numeric forecast law is invented.

Numeric predictions minimize an absolute-error training objective. Fractional
count points remain valid heuristics; they are not medians of an integer law.
Only the binary classifier supplies a predictive probability. All predictions
are conditional on played and retain the inherited cold/role prior policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from .cdf_engine import (FixedDesign, KEYS, MixtureBatch, SupportPrior,
                         assert_composite_contract, numeric, strings,
                         valid_support, validate_category)

VERSION = "all12-median-boosting-v1-20261023"
PARAMETERS = dict(max_iter=150, learning_rate=.05, max_leaf_nodes=15,
                  max_depth=3, min_samples_leaf=30, l2_regularization=10.,
                  early_stopping=False, random_state=1702)
DESIGN = {"numeric_estimator": "HistGradientBoostingRegressor", "numeric_loss": "absolute_error",
          "binary_estimator": "HistGradientBoostingClassifier", "binary_loss": "log_loss",
          "parameters": PARAMETERS, "threads": 2,
          "count_transform": "max(0, raw_prediction); fractional point retained",
          "signed_transform": "identity; signed yards never clamped",
          "binary_transform": "predict_proba event class1; no clipping",
          "fallback": "inherited trained role/global full-support prior median (numeric) or probability (binary)",
          "minimum_modeled_rows": 60, "single_class_binary": "trained role/global prior probability",
          "numeric_semantics": "MAE-objective point heuristic; not forecast mean, integer-law median, CDF or distribution"}


def prior_point(prior: SupportPrior):
    if prior.support == "bernoulli":
        return prior.p
    return float(MixtureBatch([0.], [[1.]], prior, prior_weight=1.).quantile(.5)[0])


@dataclass
class MedianBoostingModel:
    category: dict
    panel: str
    design: FixedDesign | None = None
    estimator: object | None = None
    priors: dict = field(default_factory=dict)
    global_prior: SupportPrior | None = None
    audit: dict = field(default_factory=dict)
    training_binding: pd.DataFrame | None = None
    prior_training_binding: pd.DataFrame | None = None

    @classmethod
    def fit(cls, train, category, panel):
        validate_category(category)
        if panel not in category["panels"]:
            raise ValueError("undeclared feature panel")
        assert_composite_contract(train, category)
        target, support = category["target"], category["support"]
        y = numeric(train, target)
        played = strings(train, "participation_state") == "played"
        good = played & valid_support(y, support)
        supported = train.loc[good]
        model = cls(category, panel)
        model.audit = {"version": VERSION, "design": DESIGN,
            "training_rows": len(train), "supported_played_training_rows": int(good.sum()),
            "played_missing_outcome": int((played & ~np.isfinite(y)).sum()),
            "played_invalid_support": int((played & np.isfinite(y) & ~valid_support(y, support)).sum()),
            "participation_states": train.participation_state.value_counts(dropna=False).to_dict(),
            "conditional_on": "played", "numeric_distribution": "none"}
        if supported.empty:
            model.audit["fit_state"] = "NO_SUPPORTED_TRAINING_LABELS"
            return model
        columns = [c for c in KEYS + ["position", "kickoff_utc", "outcome_available_utc", target] if c in train]
        model.prior_training_binding = supported[columns].copy()
        model.global_prior = SupportPrior.fit(y[good], support)
        model.priors = {str(role): SupportPrior.fit(numeric(part, target), support)
                        for role, part in supported.groupby("position", dropna=True)}
        modeled = supported.loc[supported.position.isin(category["modeled_roles"])]
        model.training_binding = modeled[columns].copy()
        model.audit.update(modeled_training_rows=len(modeled),
            role_priors={role: vars(prior) for role, prior in model.priors.items()},
            global_prior=vars(model.global_prior))
        if len(modeled) < DESIGN["minimum_modeled_rows"]:
            model.audit["fit_state"] = "INSUFFICIENT_MODELED_TRAINING"
            return model
        if support == "bernoulli" and len(np.unique(numeric(modeled, target))) < 2:
            model.audit["fit_state"] = "SINGLE_CLASS_BINARY_ROLE_PRIOR"
            return model
        model.design = FixedDesign.fit(modeled, category["panels"][panel])
        estimator = (HistGradientBoostingClassifier(loss="log_loss", **PARAMETERS) if support == "bernoulli"
                     else HistGradientBoostingRegressor(loss="absolute_error", **PARAMETERS))
        with threadpool_limits(limits=2):
            model.estimator = estimator.fit(model.design.transform(modeled), numeric(modeled, target))
        model.audit.update(fit_state="FITTED", numeric_features=model.design.names,
            numeric_medians=model.design.medians, categorical_roles=model.design.roles,
            fitted_iterations=int(model.estimator.n_iter_))
        return model

    def predict(self, frame, *, prior_only=False):
        """Return points and reasons without reading labels or participation."""
        roles, history = strings(frame, "position"), numeric(frame, "f_player_games_prior")
        points = np.full(len(frame), np.nan)
        reason = np.full(len(frame), "no_supported_played_training_outcomes", dtype=object)
        for role in np.unique(roles):
            indices = np.flatnonzero(roles == role)
            prior = self.priors.get(str(role), self.global_prior)
            if prior is None:
                continue
            points[indices] = prior_point(prior)
            reason[indices] = ""
            if prior_only:
                reason[indices] = "role_prior_control"
            elif str(role) not in self.category["modeled_roles"]:
                reason[indices] = "nonmodeled_role_prior"
            elif self.estimator is None:
                reason[indices] = ("single_class_binary_role_prior" if self.audit["fit_state"] == "SINGLE_CLASS_BINARY_ROLE_PRIOR"
                                   else "insufficient_modeled_training_role_prior")
            else:
                cold = ~np.isfinite(history[indices]) | (history[indices] <= 0)
                reason[indices[cold]] = "cold_start_role_prior"
            if str(role) not in self.priors:
                reason[indices] = "global_prior_unknown_role"
        warm = np.flatnonzero(reason == "")
        if len(warm):
            with threadpool_limits(limits=2):
                x = self.design.transform(frame.iloc[warm])
                if self.category["support"] == "bernoulli":
                    classes = list(self.estimator.classes_)
                    raw = self.estimator.predict_proba(x)[:, classes.index(1.)]
                else:
                    raw = self.estimator.predict(x)
            if self.category["support"] == "count":
                raw = np.maximum(0., raw)
            if not np.isfinite(raw).all():
                raise ValueError("estimator returned nonfinite prediction")
            if self.category["support"] == "bernoulli" and ((raw < 0) | (raw > 1)).any():
                raise ValueError("estimator probability outside [0,1]")
            points[warm] = raw
        return points, reason

    def save(self, directory):
        import joblib
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        artifact = directory / "model.joblib"
        joblib.dump(self, artifact, compress=3)
        with artifact.open("rb") as handle:
            sha = hashlib.file_digest(handle, "sha256").hexdigest()
        manifest = {"version": VERSION, "artifact": artifact.name, "sha256": sha,
                    "category": self.category, "panel": self.panel, "audit": self.audit}
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        return manifest


def prediction_rows(model, frame, *, prior_only=False):
    fields = KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc", "season_type"]
    result = frame[[c for c in fields if c in frame]].copy()
    result["target"], result["method"] = model.category["target"], "role_prior" if prior_only else "median_boosting_" + model.panel
    result["evidence"] = "current_vintage_exposed_reconstruction"
    result["conditional_on"] = "played"
    binary = model.category["support"] == "bernoulli"
    result["point_semantics"] = "genuine_bernoulli_probability" if binary else DESIGN["numeric_semantics"]
    result["distribution"] = "bernoulli" if binary else "none_point_heuristic"
    result["primary_role"] = result.position.isin(model.category["primary_roles"])
    history = numeric(frame, "f_player_games_prior")
    result["history_state"] = np.where(~np.isfinite(history) | (history <= 0), "cold_or_unknown", "warm")
    points, reasons = model.predict(frame, prior_only=prior_only)
    result["point"], result["fallback"] = points, reasons
    result["probability"] = points if binary else np.nan
    result["actual"], result["participation_state"], result["outcome_state"] = np.nan, "unread", "unread"
    return result


def score_frozen_rows(frame, frozen, category):
    """Attach qualified outcomes and score points without refitting/inference."""
    if not frozen[KEYS].reset_index(drop=True).equals(frame[KEYS].reset_index(drop=True)):
        raise ValueError("frozen forecast identity/order differs")
    result = frozen.copy()
    actual, state = numeric(frame, category["target"]), strings(frame, "participation_state")
    valid = (state == "played") & valid_support(actual, category["support"])
    result["actual"], result["participation_state"] = actual, state
    result["outcome_state"] = np.where(state != "played", state, np.where(~np.isfinite(actual), "played_missing_statistic",
        np.where(~valid, "played_invalid_support", np.where(actual == 0, "played_zero", "played_nonzero"))))
    for name in frame:
        if name.startswith("qualified_"):
            result[name] = frame[name].to_numpy()
    for name in ["official_physical_event", "participation_evidence", "source_policy", "stats_observed"]:
        if name in frame and "qualified_" + name not in result:
            result["qualified_" + name] = frame[name].to_numpy()
    if "qualified_outcome_state" in frame:
        result["outcome_state"] = frame.qualified_outcome_state.to_numpy()
    point = numeric(result, "point")
    good = valid & np.isfinite(point)
    result["absolute_error"], result["brier"], result["log_score"] = np.nan, np.nan, np.nan
    result.loc[good, "absolute_error"] = np.abs(point[good] - actual[good])
    if category["support"] == "bernoulli":
        if (np.isfinite(point) & ((point < 0) | (point > 1))).any():
            raise ValueError("binary probability outside [0,1]")
        result.loc[good, "brier"] = (point[good] - actual[good]) ** 2
        with np.errstate(divide="ignore", invalid="ignore"):
            result.loc[good, "log_score"] = -np.where(actual[good] == 1, np.log(point[good]), np.log1p(-point[good]))
    return result


def equalweight_rows(candidate, offers, category):
    if not candidate[KEYS].reset_index(drop=True).equals(offers[KEYS].reset_index(drop=True)):
        raise ValueError("website blend identity/order differs")
    result = candidate.copy()
    binary = category["support"] == "bernoulli"
    website = numeric(offers, "website_probability" if binary else "website_point")
    if binary and (np.isfinite(website) & ((website < 0) | (website > 1))).any():
        raise ValueError("website probability outside [0,1]")
    pure = numeric(candidate, "point")
    result["literal_website_value"], result["pure_candidate_point"] = website, pure
    result["point"] = np.where(np.isfinite(website) & np.isfinite(pure), .5 * website + .5 * pure, np.nan)
    result["probability"] = result.point if binary else np.nan
    result["method"] = "website_equalweight_" + candidate.method.iloc[0] if len(candidate) else "website_equalweight"
    result["point_semantics"] = "genuine_bernoulli_probability" if binary else "fixed_equalweight_point_heuristic_not_law_mean_or_median"
    result["abstention"] = np.where(~np.isfinite(website), "missing_literal_website", np.where(~np.isfinite(pure), "missing_candidate", ""))
    return result
