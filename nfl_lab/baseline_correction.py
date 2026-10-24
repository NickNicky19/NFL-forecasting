"""Small, zero-centered corrections to earlier out-of-fold CDF forecasts.

This module never loads sources or baseline models. Numeric outputs are points,
not reconstructed predictive laws. Every learned layer requires later evidence.
"""
from dataclasses import dataclass
import warnings

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.linear_model import QuantileRegressor

from .cdf_engine import numeric, valid_support

VERSION = 'baseline-correction-v1-20261023'
METHODS = ('cdf_offset_intercept_v1', 'cdf_offset_context_v1')


def context_columns(target):
    if target.startswith('pass_'):
        return ('pass_att',), 'f_team_pass_att_mean3'
    if target in {'rush_yd', 'rush_att'}:
        return ('rush_att',), 'f_team_rush_att_mean3'
    if target in {'rec', 'rec_yd'}:
        return ('rec_tgt',), 'f_team_pass_att_mean3'
    if target in {'rush_rec_yd', 'anytime_td'}:
        return ('rush_att', 'rec_tgt'), 'f_team_offense_plays_mean3'
    raise ValueError('unsupported correction target')


def context_features(frame, target):
    stats, team_name = context_columns(target)
    # A missing component does not become a supported zero opportunity.
    windows = []
    for window in (3, 8):
        components = np.column_stack([numeric(frame, f'f_player_{s}_mean{window}') for s in stats])
        good = np.isfinite(components).all(axis=1) & (components >= 0).all(axis=1)
        windows.append(np.where(good, components.sum(axis=1), np.nan))
    a, b = windows
    trend = (a - b) / (1 + np.abs(b))
    games, team = numeric(frame, 'f_player_games_prior'), numeric(frame, team_name)
    with np.errstate(invalid='ignore', divide='ignore'):
        games = np.where(np.isfinite(games) & (games >= 0), np.log1p(games), np.nan)
        team = np.where(np.isfinite(team) & (team >= 0), np.log1p(team), np.nan)
    return np.column_stack([trend, games, team])


def context_audit(frame, target):
    stats, team_name = context_columns(target)
    names = [f'f_player_{s}_mean{w}' for s in stats for w in (3, 8)]
    names += ['f_player_games_prior', team_name]
    return {name: dict(missing_or_nonfinite=int((~np.isfinite(numeric(frame, name))).sum()),
                       invalid_negative=int((np.isfinite(numeric(frame, name)) & (numeric(frame, name) < 0)).sum()))
            for name in names}


@dataclass
class CorrectionDesign:
    method: str
    target: str
    median: np.ndarray
    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, frame, method, target):
        if method not in METHODS:
            raise ValueError('unregistered correction arm')
        if method == METHODS[0]:
            return cls(method, target, np.empty(0), np.empty(0), np.empty(0))
        raw = context_features(frame, target)
        medians = np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else 0.0 for c in raw.T])
        filled = np.where(np.isfinite(raw), raw, medians)
        mean, scale = filled.mean(axis=0), filled.std(axis=0, ddof=0)
        scale[scale == 0] = 1.0
        return cls(method, target, medians, mean, scale)

    def transform(self, frame):
        if self.method == METHODS[0]:
            return np.ones((len(frame), 1))
        raw = context_features(frame, self.target)
        missing = ~np.isfinite(raw)
        filled = np.where(missing, self.median, raw)
        return np.column_stack([np.ones(len(frame)), (filled - self.mean) / self.scale, missing.astype(float)])

    def manifest(self):
        return dict(method=self.method, target=self.target, median=self.median.tolist(),
                    mean=self.mean.tolist(), scale=self.scale.tolist(), ddof=0,
                    missing_indicators='unscaled; all missing training column uses0')


def baseline_support(base, support, *, fitting=False):
    base = np.asarray(base, dtype=float)
    valid = np.isfinite(base)
    if support == 'count':
        return valid & (base > 0 if fitting else base >= 0)
    if support == 'bernoulli':
        return valid & ((base > 0) & (base < 1) if fitting else (base >= 0) & (base <= 1))
    if support != 'signed_integer':
        raise ValueError('unregistered correction support')
    return valid


def offset(base, support):
    if support == 'count':
        return np.log(base)
    if support == 'bernoulli':
        return np.log(base) - np.log1p(-base)
    return base


def smooth_objective(beta, X, base_offset, y, support):
    eta = base_offset + X @ beta
    if support == 'count':
        with np.errstate(over='raise', invalid='raise'):
            mean = np.exp(eta)
        value = np.mean(mean - y * eta)
    elif support == 'bernoulli':
        mean = expit(eta)
        value = np.mean(np.logaddexp(0, eta) - y * eta)
    else:
        raise ValueError('smooth objective only for count/binary')
    value += 0.5 * np.dot(beta, beta)
    gradient = X.T @ (mean - y) / len(y) + beta
    if not np.isfinite(value) or not np.isfinite(gradient).all():
        raise FloatingPointError('nonfinite correction objective')
    return float(value), gradient


@dataclass
class BaselineCorrection:
    category: dict
    method: str
    design: CorrectionDesign
    coefficients: np.ndarray
    audit: dict

    @classmethod
    def fit(cls, frame, base, category, method, *, query_year):
        if category['target'] == 'fantasy_ppr' or category['state'] != 'READY':
            raise ValueError('exact PPR remains blocked')
        if query_year not in (2023, 2024) or not frame.season.isin(range(2022, query_year)).all():
            raise ValueError('only strictly earlier forward baseline years can train a correction')
        base = np.asarray(base, dtype=float)
        if base.shape != (len(frame),):
            raise ValueError('baseline row shape mismatch')
        support = category['support']
        y = numeric(frame, category['target'])
        eligible = (frame.participation_state.eq('played').to_numpy()
                    & frame.position.isin(category['primary_roles']).to_numpy()
                    & valid_support(y, support) & baseline_support(base, support, fitting=True))
        if not eligible.any():
            raise ValueError('no eligible earlier out-of-fold correction rows')
        fit_frame = frame.loc[eligible]
        design = CorrectionDesign.fit(fit_frame, method, category['target'])
        X, response = design.transform(fit_frame), y[eligible]
        if not np.isfinite(X).all():
            raise ValueError('nonfinite earlier-only correction design')
        audit = dict(version=VERSION, query_year=query_year, training_years=sorted(frame.season.unique().tolist()),
                     offered_training_rows=len(frame), fitted_rows=int(eligible.sum()),
                     excluded_training_rows=int((~eligible).sum()), coefficients_penalized='all including intercept',
                     original_feature_states=context_audit(fit_frame, category['target']),
                     lambda_L2=1.0 if support != 'signed_integer' else None,
                     quantile_alpha=0.1 if support == 'signed_integer' else None, warnings=[])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            if support == 'signed_integer':
                estimator = QuantileRegressor(quantile=0.5, alpha=0.1, fit_intercept=False, solver='highs',
                    solver_options={'time_limit': 15.0, 'threads': 1})
                estimator.fit(X, response - base[eligible])
                coefficients = estimator.coef_
                if not hasattr(estimator, 'n_iter_'):
                    raise RuntimeError('quantile optimizer completion unavailable')
                audit.update(optimizer='fixed_quantile_highs', iterations=int(estimator.n_iter_))
            else:
                result = minimize(smooth_objective, np.zeros(X.shape[1]),
                    args=(X, offset(base[eligible], support), response, support), jac=True,
                    method='L-BFGS-B', options={'maxiter': 100, 'ftol': 1e-10, 'gtol': 1e-7})
                if not result.success:
                    raise RuntimeError('fixed correction optimizer did not converge')
                coefficients = result.x
                audit.update(optimizer='L-BFGS-B', iterations=int(result.nit))
            audit['warnings'] = [str(w.message) for w in caught]
        if not np.isfinite(coefficients).all():
            raise FloatingPointError('nonfinite correction coefficients')
        return cls(category, method, design, np.asarray(coefficients), audit)

    def predict(self, frame, base):
        base = np.asarray(base, dtype=float)
        if base.shape != (len(frame),):
            raise ValueError('baseline row shape mismatch')
        support = self.category['support']
        valid = baseline_support(base, support)
        primary = frame.position.isin(self.category['primary_roles']).to_numpy()
        points, reasons = np.where(valid, base, np.nan), np.full(len(frame), '', dtype=object)
        reasons[~valid] = 'invalid_or_missing_baseline_abstain'
        reasons[valid & ~primary] = 'nonprimary_incumbent_reference'
        interior = baseline_support(base, support, fitting=True)
        reasons[valid & primary & ~interior] = 'exact_boundary_baseline_retained'
        apply = primary & interior
        if not np.any(self.coefficients):
            return points, reasons
        X = self.design.transform(frame.loc[apply])
        eta = offset(base[apply], support) + X @ self.coefficients
        with np.errstate(over='raise', invalid='raise'):
            changed = np.exp(eta) if support == 'count' else expit(eta) if support == 'bernoulli' else eta
        if not baseline_support(changed, support).all():
            raise FloatingPointError('invalid correction prediction; package must retain baseline')
        points[apply] = changed
        return points, reasons

    def manifest(self):
        return dict(version=VERSION, category=self.category, method=self.method,
                    design=self.design.manifest(), coefficients=self.coefficients.tolist(), audit=self.audit)

    @classmethod
    def from_manifest(cls, value):
        if (set(value) != {'version', 'category', 'method', 'design', 'coefficients', 'audit'}
                or value['version'] != VERSION or value['method'] not in METHODS):
            raise ValueError('exact correction manifest schema/version required')
        category, raw = value['category'], value['design']
        context_columns(category['target'])
        if (category['state'] != 'READY' or category['support'] not in {'count', 'signed_integer', 'bernoulli'}
                or raw['method'] != value['method'] or raw['target'] != category['target']
                or raw['ddof'] != 0):
            raise ValueError('correction manifest contract mismatch')
        arrays = [np.asarray(raw[name], dtype=float) for name in ('median', 'mean', 'scale')]
        size = 0 if value['method'] == METHODS[0] else 3
        coefficients = np.asarray(value['coefficients'], dtype=float)
        if (any(a.shape != (size,) or not np.isfinite(a).all() for a in arrays)
                or (arrays[2] <= 0).any() or coefficients.shape != (1 + 2 * size,)
                or not np.isfinite(coefficients).all()):
            raise ValueError('invalid frozen correction parameters')
        design = CorrectionDesign(value['method'], category['target'], *arrays)
        return cls(category, value['method'], design, coefficients, value['audit'])
