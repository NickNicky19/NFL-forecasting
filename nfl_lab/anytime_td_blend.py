"""Two preregistered Bernoulli blends; accepted probability/evaluation contract."""
from dataclasses import dataclass
import numpy as np
from nfl_lab.anytime_calibration import probabilities
from nfl_lab.cdf_engine import valid_support

VERSION = "anytime-td-blend-v1-20261025"
ALPHA = .001
ARMS = ("fixed_half", "shrunk_brier")


def components(cdf, cat):
    cdf, cat = probabilities(cdf), probabilities(cat)
    if cdf.ndim != 1 or cdf.shape != cat.shape:
        raise ValueError("one aligned component pair required")
    if not np.array_equal(np.isfinite(cdf), np.isfinite(cat)):
        raise ValueError("component forecast coverage differs; intersection forbidden")
    return cdf, cat


def mixture(cdf, cat, weight):
    cdf, cat = components(cdf, cat)
    if not np.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("invalid registered mixture weight")
    result = np.full(len(cdf), np.nan)
    good = np.isfinite(cdf) & np.isfinite(cat)
    result[good] = weight*cdf[good] + (1-weight)*cat[good]
    return probabilities(result)


@dataclass
class Weight:
    wCDF: float
    audit: dict

    @classmethod
    def fit(cls, cdf, cat, actual):
        cdf, cat = components(cdf, cat)
        actual = np.asarray(actual, dtype=float)
        if actual.shape != cdf.shape:
            raise ValueError("weight training labels differ in shape")
        good = np.isfinite(cdf) & np.isfinite(cat) & valid_support(actual, "bernoulli")
        y, a, b = actual[good], cdf[good], cat[good]
        audit = dict(version=VERSION, alpha=ALPHA, attempt_charged=True,
            input_rows=len(actual), supported_rows=len(y), unsupported_rows=int((~good).sum()),
            positives=int(y.sum()), negatives=int(len(y)-y.sum()), optimizer_calls=0,
            state="FIXED_HALF_FALLBACK", reason="insufficient_training_rows_or_classes")
        if len(y)<200 or y.sum()<30 or len(y)-y.sum()<30:
            return cls(.5, audit)
        d = a-b
        numerator = float(np.mean((y-b)*d)+ALPHA*.5)
        denominator = float(np.mean(d*d)+ALPHA)
        if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator<=0:
            audit["reason"] = "nonfinite_closed_form_fixed_half_fallback"
            return cls(.5, audit)
        weight = float(np.clip(numerator/denominator, 0., 1.))
        audit.update(state="FITTED_CLOSED_FORM", reason="", numerator=numerator, denominator=denominator)
        return cls(weight, audit)

    def manifest(self):
        return dict(version=VERSION, wCDF=self.wCDF, wCat=1-self.wCDF, audit=self.audit)
