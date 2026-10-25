"""Version-pinned CPU challengers using the shared design, priors and evaluator.

Numeric objectives supply points, not calibrated count/yardage distributions.
No source loading or outcome scoring occurs here. Callers must freeze a finite
study and pass a gate that consumes an estimator attempt before each fit.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from io import BytesIO
import hashlib
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from .cdf_engine import (FixedDesign, KEYS, SupportPrior,
                         assert_composite_contract, numeric, strings,
                         valid_support, validate_category)
from .median_boosting import (MedianBoostingModel, prediction_rows as shared_rows,
                              prior_point, score_frozen_rows)

VERSION = "direct-boosters-v1-20261023"
LIBRARIES = {"xgboost": "xgboost-cpu", "lightgbm": "lightgbm", "catboost": "catboost"}
COMPLEXITIES = {"small": (64, 3), "medium": (128, 5)}
MINIMUM_ROWS = 60


def product(support):
    return {"count": ("conditional_mean_objective_point", "MSE"),
            "signed_integer": ("median_objective_point_heuristic", "MAE"),
            "bernoulli": ("genuine_bernoulli_probability", "Brier")}[support]


def parameters(library, complexity, support):
    """Return exact settings; no eval-set selection or early stopping."""
    if library not in LIBRARIES or complexity not in COMPLEXITIES:
        raise ValueError("undeclared library or complexity")
    product(support)  # reject unsupported products before imports/fits
    trees, depth = COMPLEXITIES[complexity]
    if library == "xgboost":
        params = dict(n_estimators=trees, max_depth=depth, learning_rate=.05,
            reg_lambda=10., reg_alpha=0., min_child_weight=30., max_bin=255,
            subsample=1., colsample_bytree=1., tree_method="hist", device="cpu",
            n_jobs=2, random_state=1751, verbosity=0)
        params["objective"] = {"count": "count:poisson", "signed_integer": "reg:quantileerror",
                               "bernoulli": "binary:logistic"}[support]
        if support == "signed_integer":
            params["quantile_alpha"] = .5
    elif library == "lightgbm":
        params = dict(n_estimators=trees, max_depth=depth,
            num_leaves=7 if complexity == "small" else 31,
            learning_rate=.05, reg_lambda=10., reg_alpha=0.,
            min_child_samples=30, max_bin=255, subsample=1., colsample_bytree=1.,
            n_jobs=2, random_state=1752, deterministic=True, force_col_wise=True,
            verbosity=-1)
        params["objective"] = {"count": "poisson", "signed_integer": "quantile",
                               "bernoulli": "binary"}[support]
        if support == "signed_integer":
            params["alpha"] = .5
    else:
        params = dict(iterations=trees, depth=depth, learning_rate=.05,
            l2_leaf_reg=10., thread_count=2, random_seed=1753,
            task_type="CPU", boosting_type="Plain", bootstrap_type="No",
            random_strength=0., rsm=1., allow_writing_files=False,
            verbose=False, use_best_model=False)
        params["loss_function"] = {"count": "Poisson", "signed_integer": "Quantile:alpha=0.5",
                                   "bernoulli": "Logloss"}[support]
    return params


def installed_version(library):
    return metadata.version(LIBRARIES[library])


def native_estimator(library, support, params):
    """Lazy imports keep optional packages outside the frozen base environment."""
    if library == "xgboost":
        from xgboost import XGBClassifier, XGBRegressor
        cls = XGBClassifier if support == "bernoulli" else XGBRegressor
    elif library == "lightgbm":
        from lightgbm import LGBMClassifier, LGBMRegressor
        cls = LGBMClassifier if support == "bernoulli" else LGBMRegressor
    elif library == "catboost":
        from catboost import CatBoostClassifier, CatBoostRegressor
        cls = CatBoostClassifier if support == "bernoulli" else CatBoostRegressor
    else:
        raise ValueError("undeclared library")
    return cls(**params)


@dataclass
class NativeOutput:
    """Validate native outputs before inherited count handling can hide errors."""
    estimator: object
    library: str
    support: str

    @property
    def classes_(self):
        return self.estimator.classes_

    def predict(self, x):
        raw = (self.estimator.predict(x, prediction_type="Exponent")
               if self.library == "catboost" and self.support == "count"
               else self.estimator.predict(x))
        raw = np.asarray(raw, dtype=float)
        if raw.shape != (len(x),) or not np.isfinite(raw).all():
            raise ValueError("native prediction has invalid shape/nonfinite values")
        if self.support == "count" and (raw < 0).any():
            raise ValueError("native count mean is negative")
        return raw

    def predict_proba(self, x):
        raw = np.asarray(self.estimator.predict_proba(x), dtype=float)
        if raw.shape != (len(x), len(self.classes_)) or not np.isfinite(raw).all():
            raise ValueError("native probability has invalid shape/nonfinite values")
        if ((raw < 0) | (raw > 1)).any() or not np.allclose(raw.sum(axis=1), 1., rtol=0, atol=1e-12):
            raise ValueError("native probability is outside simplex")
        return raw


@dataclass
class DirectBoosterModel(MedianBoostingModel):
    library: str = ""
    complexity: str = ""
    package_version: str = ""

    @classmethod
    def fit(cls, train, category, panel, *, library, complexity, expected_version, fit_gate):
        validate_category(category)
        if panel not in category["panels"]:
            raise ValueError("undeclared feature panel")
        if not callable(fit_gate):
            raise ValueError("a consuming fit gate is required")
        params = parameters(library, complexity, category["support"])
        if not isinstance(expected_version, str) or not expected_version or installed_version(library) != expected_version:
            raise ValueError("installed package differs from frozen version")
        assert_composite_contract(train, category)
        target, support = category["target"], category["support"]
        y = numeric(train, target)
        played = strings(train, "participation_state") == "played"
        good = played & valid_support(y, support)
        supported = train.loc[good]
        model = cls(category, panel, library=library, complexity=complexity,
                    package_version=expected_version)
        semantics, primary = product(support)
        model.audit = dict(version=VERSION, library=library, complexity=complexity,
            package=LIBRARIES[library], package_version=expected_version, parameters=params,
            point_semantics=semantics, primary_metric=primary, conditional_on="played",
            numeric_distribution="none", threads=2, training_rows=len(train),
            supported_played_training_rows=int(good.sum()),
            played_missing_outcome=int((played & ~np.isfinite(y)).sum()),
            played_invalid_support=int((played & np.isfinite(y) & ~valid_support(y, support)).sum()),
            participation_states=train.participation_state.value_counts(dropna=False).to_dict())
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
        if len(modeled) < MINIMUM_ROWS:
            model.audit["fit_state"] = "INSUFFICIENT_MODELED_TRAINING"
            return model
        labels = numeric(modeled, target)
        if support == "bernoulli" and len(np.unique(labels)) < 2:
            model.audit["fit_state"] = "SINGLE_CLASS_BINARY_ROLE_PRIOR"
            return model
        if support == "count" and not np.any(labels > 0):
            model.audit["fit_state"] = "ALL_ZERO_COUNT_ROLE_PRIOR"
            return model
        model.design = FixedDesign.fit(modeled, category["panels"][panel])
        fit_gate(dict(library=library, complexity=complexity, target=target,
                      package_version=expected_version, rows=len(modeled)))
        estimator = native_estimator(library, support, params)
        with threadpool_limits(limits=2):
            estimator.fit(model.design.transform(modeled), labels)
        model.estimator = NativeOutput(estimator, library, support)
        model.audit.update(fit_state="FITTED", numeric_features=model.design.names,
            numeric_medians=model.design.medians, categorical_roles=model.design.roles)
        return model

    def predict(self, frame, *, prior_only=False):
        points, reasons = super().predict(frame, prior_only=prior_only)
        if self.category["support"] == "count":
            roles = strings(frame, "position")
            for i in np.flatnonzero(reasons != ""):
                prior = self.priors.get(str(roles[i]), self.global_prior)
                if prior is not None:
                    points[i] = prior.mean
            if self.audit["fit_state"] == "ALL_ZERO_COUNT_ROLE_PRIOR":
                reasons[reasons == "insufficient_modeled_training_role_prior"] = "all_zero_count_role_prior"
        return points, reasons

    def save(self, directory, *, storage=None):
        """All artifact bytes use the caller's unchanged quota-owned storage."""
        if storage is None:
            raise ValueError("quota-owned storage is required")
        import joblib
        directory = Path(directory)
        if directory.exists():
            raise FileExistsError(directory)
        stream = BytesIO()
        joblib.dump(self, stream, compress=3)
        body = stream.getvalue()
        digest = hashlib.sha256(body).hexdigest()
        manifest = dict(version=VERSION, artifact="model.joblib", sha256=digest,
            bytes=len(body), category=self.category, panel=self.panel, audit=self.audit)
        metadata_body = (json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        storage.write_bytes(directory / "model.joblib", body)
        storage.write_bytes(directory / "manifest.json", metadata_body)
        return manifest


def prediction_rows(model, frame, *, prior_only=False):
    result = shared_rows(model, frame, prior_only=prior_only)
    semantics, primary = product(model.category["support"])
    result["method"] = ("prior_" if prior_only else "") + "direct_" + model.library + "_" + model.complexity
    result["model_version"], result["package_version"] = VERSION, model.package_version
    result["point_semantics"], result["primary_metric"] = semantics, primary
    return result
