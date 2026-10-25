"""Grid-CDF response splits with the shared empirical-leaf predictive law.

Multioutput squared-error trees learn weighted CDF indicators rather than the
numeric outcome mean. This is a fixed-grid distribution-sensitive approximation,
not an implementation of a particular DRF or MMD algorithm. Leaves retain real
training outcomes, and all prediction, fallback and law arithmetic is inherited
from LeafCDFModel. No operational default or source contract changes here.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits

from .cdf_engine import (
    FixedDesign, KEYS, LeafCDFModel, PRIOR_WEIGHT, SupportPrior, TREE_PARAMETERS,
    numeric, strings, valid_support, validate_category,
)
from .threshold_cdf import THRESHOLD_GRIDS

VERSION = "distribution-split-leaf-cdf-v1-20261025"


def threshold_weights(thresholds):
    """Normalized trapezoid weights on the already registered fixed grid."""
    grid = np.asarray(thresholds, dtype=float)
    if grid.ndim != 1 or len(grid) < 2 or not np.isfinite(grid).all() or not (np.diff(grid) > 0).all():
        raise ValueError("CDF split grid must be finite, ordered and distinct")
    weights = np.empty(len(grid), dtype=float)
    weights[0], weights[-1] = (grid[1] - grid[0]) / 2, (grid[-1] - grid[-2]) / 2
    weights[1:-1] = (grid[2:] - grid[:-2]) / 2
    return weights / weights.sum()


def cdf_split_response(y, thresholds):
    """Embed old integer outcomes as sqrt(w_j) times 1[Y <= threshold_j]."""
    values = np.asarray(y, dtype=float)
    if values.ndim != 1 or not valid_support(values, "signed_integer").all():
        raise ValueError("CDF split response requires finite integer outcomes")
    grid = np.asarray(thresholds, dtype=float)
    weights = threshold_weights(grid)
    return (values[:, None] <= grid[None, :]) * np.sqrt(weights)[None, :]


class DistributionSplitCDFModel(LeafCDFModel):
    """Shared leaf-CDF model whose partitions use the fixed CDF response vector."""

    @classmethod
    def fit(cls, train: pd.DataFrame, category: dict, panel: str):
        validate_category(category)
        if panel not in category["panels"]:
            raise ValueError("unknown fixed feature panel")
        target, support = category["target"], category["support"]
        if target == "fantasy_ppr":
            raise ValueError("exact PPR remains label-blocked")
        if target == "anytime_td" or support == "bernoulli":
            raise ValueError("UNCHANGED anytime-TD alias: caller must reuse the exact fresh CDF; zero new fit")
        if target not in THRESHOLD_GRIDS:
            raise ValueError("no registered fixed CDF split grid for target: " + target)
        thresholds = THRESHOLD_GRIDS[target]
        weights = threshold_weights(thresholds)
        y = numeric(train, target)
        played = strings(train, "participation_state") == "played"
        good = played & valid_support(y, support)
        supported = train.loc[good]
        model = cls(category, panel, None, None, np.array([0.]))
        model.audit = {
            "version": VERSION, "training_rows": len(train),
            "supported_played_training_rows": int(good.sum()),
            "played_missing_outcome": int((played & ~np.isfinite(y)).sum()),
            "played_invalid_support": int((played & np.isfinite(y) & ~valid_support(y, support)).sum()),
            "participation_states": train.participation_state.value_counts(dropna=False).to_dict(),
            "tree_parameters": dict(TREE_PARAMETERS), "prior_weight": PRIOR_WEIGHT,
            "split_response": "sqrt(normalized_trapezoid_weight) * indicator(Y <= fixed_threshold)",
            "split_thresholds": list(thresholds), "split_threshold_weights": weights.tolist(),
            "split_response_columns": len(thresholds),
            "method_identity": "fixed_grid_CDF_distribution_sensitive_split_approximation; not_exact_DRF_or_MMD",
            "leaf_outcomes": "original supported modeled training outcomes; no synthetic atoms",
            "probability_semantics": "conditional_on_played; marginal_only; calibration_unestablished",
        }
        if supported.empty:
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
                           role_priors={role: vars(prior) for role, prior in model.priors.items()},
                           global_prior=vars(model.global_prior))
        if len(modeled) < 2 * TREE_PARAMETERS["min_samples_leaf"]:
            model.audit["fit_state"] = "INSUFFICIENT_MODELED_TRAINING"
            return model
        model.design = FixedDesign.fit(modeled, category["panels"][panel])
        x, y = model.design.transform(modeled), numeric(modeled, target)
        response = cdf_split_response(y, thresholds)
        with threadpool_limits(limits=2):
            model.forest = ExtraTreesRegressor(**TREE_PARAMETERS).fit(x, response)
            leaf_ids = model.forest.apply(x)
        model.training_leaf_ids = leaf_ids.astype(np.int32)
        model.support, codes = np.unique(y, return_inverse=True)
        for j, tree in enumerate(model.forest.estimators_):
            counts = sparse.coo_matrix((np.ones(len(y)), (leaf_ids[:, j], codes)),
                                      shape=(tree.tree_.node_count, len(model.support))).tocsr()
            totals = np.asarray(counts.sum(axis=1)).ravel()
            inverse = np.divide(1., totals, out=np.zeros_like(totals), where=totals > 0)
            model.leaf_histograms.append(sparse.diags(inverse) @ counts)
        model.audit.update(fit_state="FITTED", numeric_features=model.design.names,
                           numeric_medians=model.design.medians, categorical_roles=model.design.roles,
                           empirical_support_size=len(model.support),
                           leaf_histogram_nnz=int(sum(hist.nnz for hist in model.leaf_histograms)))
        return model

    def save(self, directory: Path):
        """Use shared serialization while identifying this distinct research model."""
        manifest = super().save(directory)
        manifest["version"] = VERSION
        (Path(directory) / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        return manifest
