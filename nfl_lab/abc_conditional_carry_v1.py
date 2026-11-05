"""A3: individual conditional-on-appearance moments, not a joint allocation.

Inputs are earlier-only role moments and predicted team exposure. Beta moment
projection uses the existing concentration bounds; no target-game opportunity,
participation, injury penalty, confidence gate, fit or Monte Carlo is added.
"""
from __future__ import annotations
import math
from .abc_dynamic_carry_v1 import allocation_law

VERSION = 'A::conditional-played-carry-exposure-v1'


def parameters(raw):
    p = float(raw['raw_share'])
    variance = float(raw['raw_variance'])
    shape, rate = float(raw['shape']), float(raw['rate'])
    if not all(math.isfinite(x) for x in [p,variance,shape,rate]) or not 0 < p < 1 or variance < 0 or shape <= 0 or rate <= 0:
        raise ValueError('qualified earlier individual moments/exposure required')
    unbounded = p*(1-p)/max(variance,1e-12)-1
    concentration = min(200.,max(2.,unbounded))
    return {'shape':shape,'rate':rate,'allocation_share':p,
            'allocation_kappa':concentration,
            'moment_concentration_unbounded':unbounded,
            'moment_concentration_clipped':concentration!=unbounded,
            'raw_share':p,'raw_variance':variance,
            'law_contract':'INDIVIDUAL_CONDITIONAL_ON_APPEARANCE_NOT_JOINT_ALLOCATION'}


def predict(raw):
    params=parameters(raw)
    return params,allocation_law(params)
