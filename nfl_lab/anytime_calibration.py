"""Four fixed monotone, global anytime-TD probability calibrators.

Logistic endpoint convention, fixed before fitting: q(0)=0 and q(1)=1 for
every finite intercept and allowed slope, including zero slopes. This defines
a monotone extension with possible endpoint jumps; it avoids 0*infinity.
Compatible endpoint observations contribute zero NLL and zero gradient.
Any contrary endpoint observation makes logistic training NLL irreducibly
infinite: charge the attempt and retain the unchanged base as explicit failure.
No endpoint is clipped, dropped, offset or replaced by epsilon.

Isotonic instead learns its mapping from all input probabilities, including
0/1. Its out_of_bounds='clip' means constant monotone endpoint extension of the
learned function, never clipping an input forecast or an observed event loss.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.isotonic import IsotonicRegression
from threadpoolctl import threadpool_limits

from .cdf_engine import KEYS, numeric, valid_support
from .source_matched_reporting import _bootstrap

VERSION = "anytime-calibration-v1-20261025"
METHODS = ("intercept", "platt", "beta", "isotonic")
BASES = ("fresh_cdf", "catboost_medium")
MIN_ROWS, MIN_CLASS = 200, 30
PENALTY = .01
MAX_ITER = 200
CONTEXT = KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]


def probabilities(values):
    values = np.asarray(values, dtype=float)
    if np.isinf(values).any() or (np.isfinite(values) & ((values < 0) | (values > 1))).any():
        raise ValueError("probability outside [0,1]; no clipping allowed")
    return values


def logistic_design(p, method):
    """Interior rows only. Intercept is always the first, unpenalized column."""
    logp, log1m = np.log(p), np.log1p(-p)
    if method == "intercept":
        return np.column_stack([np.ones(len(p))]), logp - log1m, np.array([0.])
    if method == "platt":
        return np.column_stack([np.ones(len(p)), logp - log1m]), np.zeros(len(p)), np.array([0., 1.])
    return np.column_stack([np.ones(len(p)), logp, -log1m]), np.zeros(len(p)), np.array([0., 1., 1.])


@dataclass
class Calibrator:
    method: str
    parameters: list = field(default_factory=list)
    knots: list = field(default_factory=list)
    values: list = field(default_factory=list)
    audit: dict = field(default_factory=dict)

    @classmethod
    def fit(cls, p, y, method):
        if method not in METHODS:
            raise ValueError("unregistered calibration method")
        p, y = probabilities(p), np.asarray(y, dtype=float)
        if p.shape != y.shape or p.ndim != 1:
            raise ValueError("one aligned calibration vector required")
        # Caller supplies chronologically eligible played rows; unsupported
        # base outputs/labels remain explicit audit counts rather than zeros.
        good = np.isfinite(p) & valid_support(y, "bernoulli")
        model = cls(method)
        p, y = p[good], y[good]
        model.audit = dict(version=VERSION, method=method, input_rows=len(good), supported_rows=len(y),
            unsupported_rows=int((~good).sum()), positives=int(y.sum()), negatives=int(len(y)-y.sum()),
            attempt_charged=True, optimizer_attempts=0, max_iterations=MAX_ITER,
            penalty=PENALTY, intercept_penalized=False, threads=2,
            endpoint_convention="learned_monotone_endpoint_extension" if method == "isotonic" else "exact_base_0_1_invariant_including_zero_slopes",
            state="UNCHANGED_BASE_FALLBACK", reason="insufficient_calibration_rows_or_classes")
        if len(y) < MIN_ROWS or y.sum() < MIN_CLASS or len(y)-y.sum() < MIN_CLASS:
            return model
        if method == "isotonic":
            try:
                with threadpool_limits(limits=2):
                    fitted = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(p, y)
            except Exception as error:
                model.audit.update(reason="single_isotonic_attempt_exception", exception=type(error).__name__)
                return model
            model.knots, model.values = fitted.X_thresholds_.tolist(), fitted.y_thresholds_.tolist()
            model.audit.update(state="FITTED", reason="", algorithm="PAVA_one_attempt", optimizer_attempts=1)
            return model
        contrary = ((p == 0) & (y == 1)) | ((p == 1) & (y == 0))
        if contrary.any():
            model.audit.update(reason="irreducible_infinite_endpoint_training_NLL", contrary_endpoint_events=int(contrary.sum()))
            return model
        interior = (p > 0) & (p < 1)
        x, offset, identity = logistic_design(p[interior], method)
        yi, total = y[interior], len(y)
        def objective(theta):
            with np.errstate(over="ignore", invalid="ignore"):
                z = x @ theta + offset
                penalty = .5 * PENALTY * np.sum((theta[1:] - 1) ** 2)
            if not np.isfinite(z).all() or not np.isfinite(penalty):
                return np.inf, np.zeros_like(theta)
            residual = expit(z) - yi
            # Denominator includes compatible endpoints: their exact NLL is0.
            loss = np.sum(np.logaddexp(0., z) - yi*z) / total + penalty
            gradient = x.T @ residual / total
            gradient[1:] += PENALTY * (theta[1:] - 1)
            return float(loss), gradient
        bounds = [(None, None)] + [(0., None)] * (len(identity)-1)
        model.audit["optimizer_attempts"] = 1
        try:
            with threadpool_limits(limits=2):
                fitted = minimize(objective, identity, method="L-BFGS-B", jac=True, bounds=bounds,
                    options=dict(maxiter=MAX_ITER, ftol=1e-12, gtol=1e-8, maxls=20))
        except Exception as error:
            model.audit.update(reason="single_optimizer_attempt_exception", exception=type(error).__name__)
            return model
        model.audit.update(optimizer_success=bool(fitted.success), optimizer_status=int(fitted.status),
                           iterations=int(fitted.nit), objective=float(fitted.fun) if np.isfinite(fitted.fun) else None)
        if not fitted.success or not np.isfinite(fitted.x).all() or not np.isfinite(fitted.fun):
            model.audit["reason"] = "single_optimizer_attempt_failed"
            return model
        model.parameters = fitted.x.tolist()
        model.audit.update(state="FITTED", reason="")
        return model

    def predict(self, p):
        p = probabilities(p)
        q = p.copy()
        if self.audit.get("state") != "FITTED":
            return q
        good = np.isfinite(p)
        if self.method == "isotonic":
            q[good] = np.interp(p[good], self.knots, self.values, left=self.values[0], right=self.values[-1])
        else:
            interior = good & (p > 0) & (p < 1)
            x, offset, _ = logistic_design(p[interior], self.method)
            q[interior] = expit(x @ np.asarray(self.parameters) + offset)
        return probabilities(q)

    def manifest(self):
        return dict(version=VERSION, method=self.method, parameters=self.parameters,
                    knots=self.knots, values=self.values, audit=self.audit)

    @classmethod
    def from_manifest(cls, value):
        if value["version"] != VERSION or value["method"] not in METHODS:
            raise ValueError("calibrator version mismatch")
        if value["audit"].get("state") == "FITTED":
            if value["method"] == "isotonic":
                x,y=np.asarray(value["knots"]),probabilities(value["values"])
                if (not len(x) or len(x)!=len(y) or not np.isfinite(x).all() or not np.isfinite(y).all()
                        or (np.diff(x)<=0).any() or (np.diff(y)<0).any()):
                    raise ValueError("invalid serialized monotone isotonic map")
            else:
                theta=np.asarray(value["parameters"],dtype=float)
                if len(theta)!={"intercept":1,"platt":2,"beta":3}[value["method"]] or not np.isfinite(theta).all() or (theta[1:]<0).any():
                    raise ValueError("invalid serialized constrained logistic parameters")
        return cls(**{key:value[key] for key in ("method", "parameters", "knots", "values", "audit")})


def binary_losses(p, y, supported=None):
    p, y = probabilities(p), np.asarray(y, dtype=float)
    good = np.isfinite(p) & valid_support(y, "bernoulli")
    if supported is not None:
        good &= np.asarray(supported, dtype=bool)
    brier, logloss = np.full(len(p), np.nan), np.full(len(p), np.nan)
    brier[good] = (p[good]-y[good])**2
    with np.errstate(divide="ignore"):
        # Selecting the observed branch avoids 0*log(0) and retains true +inf.
        logloss[good] = -np.where(y[good] == 1, np.log(p[good]), np.log1p(-p[good]))
    return brier, logloss


def align_context(reference, source):
    """Same offered player-games, teams, roles and exact recorded cutoffs."""
    if reference.duplicated(KEYS).any() or source.duplicated(KEYS).any():
        raise ValueError("duplicate forecast player-game identity")
    aligned = reference[KEYS].assign(_ordinal=np.arange(len(reference))).merge(
        source, on=KEYS, how="outer", indicator=True, validate="one_to_one", sort=False)
    if not aligned._merge.eq("both").all() or len(aligned) != len(reference):
        raise ValueError("base forecast coverage differs")
    aligned = aligned.sort_values("_ordinal", kind="stable").drop(columns=["_merge","_ordinal"]).reset_index(drop=True)
    for name in CONTEXT:
        a, b = reference[name].reset_index(drop=True), aligned[name]
        if name.endswith("_utc"):
            a, b = pd.to_datetime(a, utc=True), pd.to_datetime(b, utc=True)
        if not a.eq(b).all():
            raise ValueError("base forecast context/cutoff differs: " + name)
    return aligned


def summary(rows):
    p, y = numeric(rows, "probability"), numeric(rows, "actual")
    observed = rows.participation_state.eq("played").to_numpy()
    brier, logs = binary_losses(p, y, observed)
    good = ~np.isnan(brier)
    bins = []
    for j in range(10):
        selected = good & (p >= j/10) & ((p < (j+1)/10) if j < 9 else (p <= 1))
        bins.append(dict(lo=j/10, hi=(j+1)/10, n=int(selected.sum()),
                         p=float(p[selected].mean()) if selected.any() else None,
                         event_rate=float(y[selected].mean()) if selected.any() else None))
    cdf0 = 1-p[good]
    low, high = (cdf0 < .1).astype(float), (cdf0 < .9).astype(float)
    return dict(offered=len(rows), forecasted=int(np.isfinite(p).sum()), scored=int(good.sum()),
        unsupported_forecasts=int((~np.isfinite(p)).sum()),
        DNP=int(rows.participation_state.eq("DNP").sum()), unknown=int(rows.participation_state.eq("unknown").sum()),
        played_missing_label=int((observed & ~np.isfinite(y)).sum()),
        played_invalid_label=int((observed & np.isfinite(y) & ~valid_support(y,"bernoulli")).sum()),
        played_zero=int((good & (y==0)).sum()), played_event=int((good & (y==1)).sum()),
        base_fallback_offered=int(rows.base_fallback.ne("").sum()),
        calibration_fallback_offered=int(rows.calibration_fallback.ne("").sum()),
        Brier=float(brier[good].mean()) if good.any() else None,
        log_loss=float(logs[good].mean()) if good.any() and not np.isinf(logs[good]).any() else None,
        log_loss_state="positive_infinity" if np.isposinf(logs).any() else "finite" if good.any() else "unavailable",
        infinite_log_losses=int(np.isposinf(logs).sum()), reliability_fixed_tenths=bins,
        low_tail_rows=int((good & (p <= .1)).sum()), high_tail_rows=int((good & (p >= .9)).sum()),
        coverage80=float(((y[good] >= low) & (y[good] <= high)).mean()) if good.any() else None,
        mean_interval_width80=float((high-low).mean()) if good.any() else None)


def paired(rows, control, metric):
    if metric not in {"Brier", "log_loss"}:
        raise ValueError("unregistered binary calibration metric")
    control = align_context(rows, control)
    if not rows.participation_state.reset_index(drop=True).equals(control.participation_state) or not np.allclose(
            numeric(rows,"actual"), numeric(control,"actual"), equal_nan=True, atol=0, rtol=0):
        raise ValueError("paired calibration labels differ")
    played = rows.participation_state.eq("played").to_numpy()
    x = binary_losses(numeric(rows,"probability"), numeric(rows,"actual"), played)[metric == "log_loss"]
    y = binary_losses(numeric(control,"probability"), numeric(control,"actual"), played)[metric == "log_loss"]
    good = ~np.isnan(x) & ~np.isnan(y)
    extended = np.isinf(x[good]).any() or np.isinf(y[good]).any()
    loss = rows[KEYS].copy()
    loss["delta_candidate_minus_control"] = np.nan
    if not extended:
        loss.loc[good,"delta_candidate_minus_control"] = x[good]-y[good]
    return dict(metric=metric, n=int(good.sum()), candidate_infinite=int(np.isposinf(x[good]).sum()),
        control_infinite=int(np.isposinf(y[good]).sum()), delta=None if extended or not good.any() else float((x[good]-y[good]).mean()),
        delta_state="undefined_both_infinite" if np.isinf(x[good]).any() and np.isinf(y[good]).any() else
                    "positive_infinity" if np.isinf(x[good]).any() else "negative_infinity" if np.isinf(y[good]).any() else "finite" if good.any() else "unavailable",
        intervals={kind:_bootstrap(loss, good, kind, 500, seed) for kind,seed in [("week",1931),("game",1932)]})
