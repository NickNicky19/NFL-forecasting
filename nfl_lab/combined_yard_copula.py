"""Fixed cached signed-yard marginal coupling; no base estimator fitting.

The joint law is defined by complete marginal inverse CDFs and a copula.
4096 coherent draws approximate its sum distribution; no prior tail is cut or
replaced by a normal yard distribution. Monte Carlo is not new NFL evidence.
"""
from __future__ import annotations
import hashlib
import json
import numpy as np
from scipy.special import ndtr, ndtri
from .threshold_cdf import StableMixtureBatch

VERSION = 'combined-yard-copula-v1-20261025'
DRAWS = 4096
SHRINK = 100
ARMS = ('independent_sum', 'shrunk_gaussian_sum')


def seed_for(identity, purpose):
    body = json.dumps([VERSION, purpose, list(identity)], separators=(',', ':'), default=str).encode()
    return int.from_bytes(hashlib.sha256(body).digest()[:16], 'little')


def cdf_grid(law, values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(law.weights) or np.isnan(values).any():
        raise ValueError('one CDF threshold vector per law row required')
    result = np.empty(values.shape)
    for i, thresholds in enumerate(values):
        slots = np.searchsorted(law.support, np.floor(thresholds), side='right') - 1
        empirical = np.where(slots >= 0, law.cumulative[i, np.maximum(slots, 0)], 0.)
        result[i] = law.a * empirical + law.b * law.prior.cdf(thresholds)
    result = np.where(np.isneginf(values), 0., np.where(np.isposinf(values), 1., result))
    if not np.isfinite(result).all() or ((result < 0) | (result > 1)).any():
        raise ValueError('invalid full marginal CDF')
    return result


def vector_quantile(law, probabilities):
    """Left integer inverse for each row/vector, including full signed prior."""
    p = np.asarray(probabilities, dtype=float)
    if p.ndim != 2 or p.shape[0] != len(law.weights) or not np.isfinite(p).all() or ((p <= 0) | (p >= 1)).any():
        raise ValueError('finite open-unit probabilities per row required')
    lo = np.full(p.shape, min(int(law.support.min())-1, law.prior.center-1, -1), dtype=np.int64)
    hi = np.full(p.shape, max(int(law.support.max()), law.prior.center, 1), dtype=np.int64)
    step = 1
    for _ in range(61):
        left, right = cdf_grid(law, lo) >= p, cdf_grid(law, hi) < p
        if not left.any() and not right.any():
            break
        if ((lo[left] < -(2**62)+step).any() or (hi[right] > 2**62-step).any()):
            raise ValueError('finite quantile integer budget exhausted; no tail clamp')
        lo[left] -= step; hi[right] += step; step *= 2
    else:
        raise ValueError('full-support quantile not bracketed')
    while (hi-lo > 1).any():
        mid = lo + (hi-lo)//2
        upper = cdf_grid(law, mid) >= p
        hi = np.where(upper, mid, hi); lo = np.where(upper, lo, mid)
    return hi


def fit_dependence(pit_rush, pit_rec):
    """One pooled Pearson PIT-normal correlation, one fixed n/(n+100) shrink."""
    a, b = np.asarray(pit_rush, float), np.asarray(pit_rec, float)
    if a.shape != b.shape or a.ndim != 1 or not np.isfinite(a).all() or not np.isfinite(b).all() or ((a <= 0)|(a >= 1)|(b <= 0)|(b >= 1)).any():
        raise ValueError('honest paired open-unit randomized PITs required')
    n = len(a)
    if n < 2:
        return dict(n=n, raw_correlation=None, rho=0., fallback='fewer_than_two_qualified_OOF_pairs')
    x, y = ndtri(a), ndtri(b)
    if np.var(x) == 0 or np.var(y) == 0:
        return dict(n=n, raw_correlation=None, rho=0., fallback='constant_PIT_normal_score')
    raw = float(np.corrcoef(x, y)[0, 1])
    if not np.isfinite(raw) or abs(raw) > 1+1e-12:
        raise ValueError('invalid PIT correlation')
    # Only binary64 correlation roundoff at its mathematical boundary is removed.
    raw = min(1., max(-1., raw))
    return dict(n=n, raw_correlation=raw, rho=raw*n/(n+SHRINK), fallback='')


def randomized_pit(law, actual, identities, purpose):
    y = np.asarray(actual, float)
    if len(law.weights) != len(y) or len(y) != len(identities):
        raise ValueError('PIT dimensions differ')
    lo, hi = law.cdf(y-1), law.cdf(y)
    u = np.array([np.random.Generator(np.random.PCG64(seed_for(k, purpose))).random() for k in identities])
    pit = lo + u*(hi-lo)
    valid = np.isfinite(pit) & (hi > lo) & (pit > 0) & (pit < 1)
    return pit, valid


def sum_draws(rush, receiving, rho, identities, draws=DRAWS):
    if draws != DRAWS or not np.isfinite(rho) or not -1 < rho < 1 or len(rush.weights) != len(receiving.weights) or len(identities) != len(rush.weights):
        raise ValueError('fixed finite coherent coupling required')
    if rush.prior.support != receiving.prior.support or rush.prior.support != 'signed_integer':
        raise ValueError('signed integer marginal laws required')
    z = np.stack([np.random.Generator(np.random.PCG64(seed_for(k, 'joint-draws'))).standard_normal((2, draws)) for k in identities])
    u, v = ndtr(z[:, 0]), ndtr(rho*z[:, 0]+np.sqrt(1-rho*rho)*z[:, 1])
    a, b = vector_quantile(rush, u), vector_quantile(receiving, v)
    if (np.abs(a) > 2**61).any() or (np.abs(b) > 2**61).any():
        raise ValueError('sum integer budget exhausted')
    return a+b, a, b


def empirical_sum_law(draws, original_prior):
    """Existing exact empirical-mixture CRPS applied to coherent finite draws.

    This is explicitly a Monte Carlo approximation, not an invented parametric
    tail. The underlying joint law still uses both full original marginal laws.
    """
    draws = np.asarray(draws)
    if draws.ndim != 1 or len(draws) != DRAWS or not np.isfinite(draws).all() or (draws != np.floor(draws)).any():
        raise ValueError('exact4096 signed sum draws required')
    support, count = np.unique(draws, return_counts=True)
    return StableMixtureBatch(support, [count/DRAWS], original_prior, prior_weight=0.)


def draw_digest(values):
    return hashlib.sha256(np.asarray(values, dtype='<i8').tobytes()).hexdigest()
