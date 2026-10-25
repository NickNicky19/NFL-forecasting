"""Fixed role/loss ablation; numeric outputs remain point heuristics.

Poisson is a count training objective with a log link. It supplies no calibrated
count law. All fallback priors use the complete supported earlier training set
before any estimator partition. No frozen v1 implementation is changed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from .cdf_engine import (FixedDesign, KEYS, SupportPrior, assert_composite_contract,
                         numeric, strings, valid_support, validate_category)
from .median_boosting import PARAMETERS, prior_point, prediction_rows as old_prediction_rows

VERSION = "all12-role-count-boosting-v1-20261023"
VARIANTS = ("A", "B")
ROLES = ("QB", "RB", "FB", "WR", "TE")
COUNT_TARGETS = ("pass_td", "pass_cmp", "pass_att", "pass_int", "rush_att", "rec")
DESIGN = {
    "parameters": PARAMETERS, "threads": 2, "minimum_modeled_rows": 60,
    "count_loss": "poisson", "count_link": "log", "signed_loss": "absolute_error",
    "binary_loss": "log_loss", "panel": "base", "modeled_roles": "unchanged category contracts",
    "A": "pooled count Poisson; signed yards and binary alias frozen old base HGB",
    "B": "per-role estimators; singleton passing category aliases A exactly",
    "preprocessing": "unchanged FixedDesign fit per estimator training partition",
    "priors": "once on complete earlier supported played training rows, before role partitions",
    "fallback": "unchanged trained role/global prior numeric median or binary probability; cold/nonmodeled unchanged",
    "all_zero_count": "ALL_ZERO_COUNT_ROLE_PRIOR; no optimizer, epsilon or pseudo labels",
    "numeric_semantics": "point heuristic; count Poisson objective fitted mean is not a calibrated law or mean-accuracy claim; no numeric distribution",
    "signed_transform": "identity", "count_transform": "nonnegative Poisson log-link output; no rounding",
    "binary_transform": "genuine event probability without clipping",
    "maximum_estimator_attempts": 136, "maximum_new_model_packages": 48,
    "alias_packages": 40, "blocked_ppr_packages": 8, "planned_packages": 96,
    "new_features": 0, "blends": 0, "tuning": "none",
}


def package_kind(category, variant):
    if category["state"] != "READY":
        return "blocked"
    if variant == "A":
        return "model" if category["support"] == "count" else "old_base_alias"
    if variant == "B":
        return "A_alias" if len(category["modeled_roles"]) == 1 else "model"
    raise ValueError("undeclared variant")


@dataclass
class RoleCountBoostingModel:
    category: dict
    variant: str
    panel: str = "base"
    estimators: dict = field(default_factory=dict)
    designs: dict = field(default_factory=dict)
    priors: dict = field(default_factory=dict)
    global_prior: SupportPrior | None = None
    audit: dict = field(default_factory=dict)
    training_binding: object | None = None
    prior_training_binding: object | None = None

    @classmethod
    def fit(cls, train, category, variant, *, before_fit=None):
        validate_category(category)
        if package_kind(category, variant) != "model":
            raise ValueError("alias packages must never refit")
        assert_composite_contract(train, category)
        target, support = category["target"], category["support"]
        y = numeric(train, target)
        played = strings(train, "participation_state") == "played"
        good = played & valid_support(y, support)
        supported = train.loc[good]
        model = cls(category, variant)
        model.audit = {"version": VERSION, "design": DESIGN, "training_rows": len(train),
            "supported_played_training_rows": int(good.sum()), "conditional_on": "played",
            "played_missing_outcome": int((played & ~np.isfinite(y)).sum()),
            "played_invalid_support": int((played & np.isfinite(y) & ~valid_support(y, support)).sum()),
            "participation_states": train.participation_state.value_counts(dropna=False).to_dict(),
            "fit_attempts": 0, "subfits": [], "numeric_distribution": "none"}
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
            role_priors={k: vars(v) for k, v in model.priors.items()}, global_prior=vars(model.global_prior))
        groups = [("pooled", modeled)] if variant == "A" else [
            (role, modeled.loc[modeled.position.eq(role)]) for role in category["modeled_roles"]]
        for role, part in groups:
            labels = numeric(part, target)
            receipt = {"role": role, "training_rows": len(part), "fit_attempts": 0}
            if len(part) < DESIGN["minimum_modeled_rows"]:
                receipt["state"] = "INSUFFICIENT_MODELED_TRAINING_ROLE_PRIOR"
            elif support == "count" and np.all(labels == 0):
                receipt["state"] = "ALL_ZERO_COUNT_ROLE_PRIOR"
            elif support == "bernoulli" and len(np.unique(labels)) < 2:
                receipt["state"] = "SINGLE_CLASS_BINARY_ROLE_PRIOR"
            else:
                design = FixedDesign.fit(part, category["panels"]["base"])
                estimator = (HistGradientBoostingClassifier(loss="log_loss", **PARAMETERS)
                    if support == "bernoulli" else HistGradientBoostingRegressor(
                        loss="poisson" if support == "count" else "absolute_error", **PARAMETERS))
                if before_fit is not None:
                    before_fit(dict(receipt, state="ESTIMATOR_ATTEMPT_CONSUMED"))
                model.audit["fit_attempts"] += 1
                receipt["fit_attempts"] = 1
                with threadpool_limits(limits=2):
                    estimator.fit(design.transform(part), labels)
                model.estimators[role], model.designs[role] = estimator, design
                receipt.update(state="FITTED", fitted_iterations=int(estimator.n_iter_),
                    numeric_features=design.names, numeric_medians=design.medians, categorical_roles=design.roles)
            model.audit["subfits"].append(receipt)
        model.audit["fit_state"] = "FITTED_OR_EXPLICIT_ROLE_PRIORS"
        return model

    def predict(self, frame, *, prior_only=False):
        roles, history = strings(frame, "position"), numeric(frame, "f_player_games_prior")
        points = np.full(len(frame), np.nan)
        reasons = np.full(len(frame), "no_supported_played_training_outcomes", dtype=object)
        states = {r["role"]: r["state"].lower() for r in self.audit["subfits"]}
        for role in np.unique(roles):
            indices = np.flatnonzero(roles == role)
            prior = self.priors.get(str(role), self.global_prior)
            if prior is None:
                continue
            points[indices], reasons[indices] = prior_point(prior), ""
            key = "pooled" if self.variant == "A" else str(role)
            if prior_only:
                reasons[indices] = "role_prior_control"
            elif str(role) not in self.category["modeled_roles"]:
                reasons[indices] = "nonmodeled_role_prior"
            elif key not in self.estimators:
                reasons[indices] = states.get(key, "insufficient_modeled_training_role_prior")
            else:
                cold = ~np.isfinite(history[indices]) | (history[indices] <= 0)
                reasons[indices[cold]] = "cold_start_role_prior"
            if str(role) not in self.priors:
                reasons[indices] = "global_prior_unknown_role"
            warm = indices[reasons[indices] == ""]
            if not len(warm):
                continue
            with threadpool_limits(limits=2):
                x = self.designs[key].transform(frame.iloc[warm])
                estimator = self.estimators[key]
                raw = (estimator.predict_proba(x)[:, list(estimator.classes_).index(1.)]
                    if self.category["support"] == "bernoulli" else estimator.predict(x))
            if not np.isfinite(raw).all():
                raise ValueError("nonfinite model point")
            if self.category["support"] == "count" and (raw < 0).any():
                raise ValueError("negative Poisson point")
            if self.category["support"] == "bernoulli" and ((raw < 0) | (raw > 1)).any():
                raise ValueError("binary probability outside [0,1]")
            points[warm] = raw
        return points, reasons

    def save(self, directory):
        import joblib
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        artifact = directory / "model.joblib"
        joblib.dump(self, artifact, compress=3)
        with artifact.open("rb") as handle:
            sha = hashlib.file_digest(handle, "sha256").hexdigest()
        manifest = {"version": VERSION, "artifact": artifact.name, "sha256": sha,
            "category": self.category, "variant": self.variant, "panel": self.panel, "audit": self.audit}
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        return manifest


def prediction_rows(model, frame, *, prior_only=False):
    result = old_prediction_rows(model, frame, prior_only=prior_only)
    result["method"] = "role_prior" if prior_only else "role_count_boosting_" + model.variant
    if model.category["support"] != "bernoulli":
        result["point_semantics"] = DESIGN["numeric_semantics"]
    return result
