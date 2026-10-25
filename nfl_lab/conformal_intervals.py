"""Fixed CQR interval arithmetic over authenticated, unchanged saved CDF rows.

No fitting of a base model, source access, I/O, or probability-law construction.
Callers own exact source/forecast authentication and chronological persistence.
"""
from collections import Counter
import math
import re

from .state import digest, utc

VERSION = "cdf-split-cqr-80-v1-20261024"
ALPHA = .2
BLOCKS = ((2022, 2023), (2023, 2024))
SUPPORTS = {"pass_yd": "signed_integer", "pass_td": "count", "pass_cmp": "count",
    "pass_att": "count", "pass_int": "count", "rush_yd": "signed_integer", "rush_att": "count",
    "rec": "count", "rec_yd": "signed_integer", "rush_rec_yd": "signed_integer"}
SHA = re.compile(r"[0-9a-f]{64}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def missing(value):
    return value is None or (type(value) is float and math.isnan(value))


def supported(value, support):
    return finite(value) and value == math.floor(value) and (support != "count" or value >= 0)


def interval_bounds(lower, upper, support):
    """Unavailable endpoints abstain; invalid present endpoints never repair."""
    for value in (lower, upper):
        require(missing(value) or finite(value), "invalid present saved interval endpoint")
    if missing(lower) or missing(upper):
        return None
    require(lower <= upper and (support != "count" or lower >= 0), "saved interval support/order conflict")
    return lower, upper


def _identity(row):
    values = tuple(row.get(name) for name in ("season", "week", "game_id", "player_id"))
    require(type(values[0]) is int and type(values[1]) is int and values[1] >= 1
        and all(isinstance(v, str) and v for v in values[2:]), "exact saved player-game identity required")
    return values


def _contract(binding):
    fields = {"source_policy_sha256", "qualification_policy_sha256", "forecast_freeze_sha256",
        "scored_freeze_sha256", "query_freeze_sha256", "qualifier_code_sha256",
        "base_method", "qualifier", "base_out_of_sample", "evidence_lane"}
    require(set(binding) == fields, "exact authenticated interval binding required")
    require(all(isinstance(binding[k], str) and SHA.fullmatch(binding[k]) for k in fields if k.endswith("sha256")),
        "complete original source/forecast/qualifier hashes required")
    require(binding['base_method'] == 'leaf_cdf' and binding['base_out_of_sample'] is True
        and binding['qualifier'] == 'nfl_lab.cdf_evaluation._observed'
        and binding['evidence_lane'] == 'EXPOSED_HISTORICAL_RECONSTRUCTION', "unchanged base/eligibility lane required")


def fit_radius(rows, *, target, calibration_season, evaluation_season, evaluation_start_utc, binding):
    """One radius from earlier OOS primary-role played labels, including zeros.

    ``eligible`` must be the unchanged existing CDF _observed flag. Equality
    with that rule is checked here to reject positive-only or DNP-zero panels.
    Complete planned rows are retained in the input and aggregate exclusions.
    """
    require(target in SUPPORTS and (calibration_season, evaluation_season) in BLOCKS,
        "fixed numeric target and chronological block required")
    _contract(binding)
    cutoff, support = utc(evaluation_start_utc), SUPPORTS[target]
    scores, admitted, identities, exclusions = [], [], set(), Counter()
    zeros = negatives = fallbacks = 0
    for row in rows:
        key = _identity(row)
        require(key not in identities, "duplicate calibration player-game")
        identities.add(key)
        require(row['season'] == calibration_season and row['target'] == target and row['method'] == 'leaf_cdf',
            "calibration source/season/target mismatch")
        require(utc(row['cutoff_utc']) <= utc(row['kickoff_utc']), "original replay cutoff exceeds kickoff")
        expected = row['participation_state'] == 'played' and supported(row.get('actual'), support)
        require(type(row.get('eligible')) is bool and row['eligible'] == expected,
            "eligible flag differs from supported-played qualifier, including zero")
        require(type(row.get('primary_role')) is bool, "original primary-role flag required")
        if not row['eligible']:
            exclusions['unsupported_or_not_played'] += 1
            continue
        if not row['primary_role']:
            exclusions['outside_fixed_primary_role_calibration_population'] += 1
            continue
        available = row.get('outcome_available_utc')
        if available is None:
            exclusions['missing_original_outcome_availability'] += 1
            continue
        available = utc(available)
        require(available >= utc(row['kickoff_utc']), "outcome availability precedes game")
        if available >= cutoff:
            exclusions['outcome_not_available_strictly_before_evaluation'] += 1
            continue
        bounds = interval_bounds(row.get('p10'), row.get('p90'), support)
        if bounds is None:
            exclusions['missing_saved_interval'] += 1
            continue
        lower, upper = bounds
        actual = row['actual']
        scores.append(max(lower-actual, actual-upper))
        admitted.append(key)
        zeros += actual == 0
        negatives += actual < 0
        fallbacks += bool(row.get('fallback'))
    count = len(scores)
    # Exact ceil((n+1)*.8), avoiding a floating-point rank boundary.
    rank = (4*(count+1)+4)//5
    ready = rank <= count
    radius = max(0., sorted(scores)[rank-1]) if ready else None
    return dict(version=VERSION, target=target, support=support, alpha=ALPHA,
        calibration_season=calibration_season, evaluation_season=evaluation_season,
        evaluation_start_utc=cutoff.isoformat(), planned_calibration_rows=len(identities),
        admitted_calibration_rows=count, order_statistic_rank=rank, radius=radius,
        state='RADIUS_FROZEN' if ready else 'UNCALIBRATED_FALLBACK_INSUFFICIENT_N',
        excluded=dict(exclusions), supported_played_zero_rows=zeros, negative_outcome_rows=negatives,
        admitted_original_fallback_rows=fallbacks, admitted_identity_sha256=digest(admitted),
        binding_sha256=digest(binding), calibration_population='original_primary_roles_supported_played',
        all_input_rows_accounted=len(identities) == count+sum(exclusions.values()),
        radius_rule='max(0, kth max(p10-y,y-p90)); no interpolation or shrinkage',
        guarantee='NONE: dependent, drifting NFL chronology; exposed reconstruction only')


def apply_radius(rows, frozen):
    """Preserve every prediction-only offer and saved point/quantile value."""
    require(frozen['version'] == VERSION and frozen['target'] in SUPPORTS and frozen['alpha'] == ALPHA,
        "exact fixed interval artifact required")
    radius = frozen['radius']
    require((radius is None and frozen['state'] == 'UNCALIBRATED_FALLBACK_INSUFFICIENT_N')
        or (finite(radius) and radius >= 0 and frozen['state'] == 'RADIUS_FROZEN'), "invalid frozen radius")
    support, output, seen = SUPPORTS[frozen['target']], [], set()
    for row in rows:
        require(not {'actual', 'participation_state', 'eligible', 'outcome_state'} & set(row),
            "interval issuance cannot consume evaluation outcomes/participation")
        key = _identity(row)
        require(key not in seen, "duplicate evaluation offer")
        seen.add(key)
        require(row['target'] == frozen['target'] and row['season'] == frozen['evaluation_season']
            and row['method'] == 'leaf_cdf', "evaluation source/season/target mismatch")
        require(utc(frozen['evaluation_start_utc']) <= utc(row['cutoff_utc']) <= utc(row['kickoff_utc']),
            "radius not frozen before original evaluation cutoff")
        bounds = interval_bounds(row.get('p10'), row.get('p90'), support)
        result = dict(row, interval_version=VERSION, radius_artifact_sha256=digest(frozen),
            interval_lower=None, interval_upper=None, interval_status='ABSTAIN_MISSING_BASE_INTERVAL')
        if bounds is not None:
            lower, upper = bounds
            if radius is not None:
                lower, upper = lower-radius, upper+radius
                if support == 'count':
                    lower = max(0., lower)
            result.update(interval_lower=lower, interval_upper=upper,
                interval_status=frozen['state'])
        output.append(result)
    return output


def interval_losses(actual, lower, upper):
    require(finite(actual) and finite(lower) and finite(upper) and lower <= upper,
        "finite actual and ordered interval required")
    width = upper-lower
    return dict(interval_score=width+(2/ALPHA)*(max(0., lower-actual)+max(0., actual-upper)),
        width=width, covered=float(lower <= actual <= upper),
        below=float(actual < lower), above=float(actual > upper))


def evaluate_interval_frame(rows, *, target, guard):
    """Reuse existing supported-played eligibility and paired cluster bootstrap.

    DataFrame adapter only; caller freezes candidate intervals before attaching
    the original, unchanged saved outcomes. No point/distribution is replaced.
    """
    import numpy as np
    from .cdf_evaluation import _observed
    from .cdf_engine import numeric
    from .source_matched_reporting import _bootstrap

    require(target in SUPPORTS, 'fixed numeric target required')
    require(rows.columns.is_unique and rows.target.eq(target).all() and rows.method.eq('leaf_cdf').all(),
        'exact original one-target CDF frame required')
    require(not rows.duplicated(['season', 'week', 'game_id', 'player_id']).any(),
        'duplicate evaluation player-game')
    support = SUPPORTS[target]
    y, lo, hi = (numeric(rows, key) for key in ('actual', 'p10', 'p90'))
    lower, upper = (numeric(rows, key) for key in ('interval_lower', 'interval_upper'))
    observed = _observed(rows, support)
    baseline_good = observed & np.isfinite(lo) & np.isfinite(hi)
    candidate_good = observed & np.isfinite(lower) & np.isfinite(upper)
    require(np.array_equal(baseline_good, candidate_good), 'interval coverage cohort differs from unchanged base')
    good = baseline_good & candidate_good
    require(not (good & ((lo > hi) | (lower > upper))).any(), 'paired interval order conflict')
    require(support != 'count' or not (good & ((lo < 0) | (lower < 0))).any(), 'count interval below support')
    work = rows.copy()
    reports = []
    for population, mask in (('all_offered', good), ('primary_roles', good & rows.primary_role.to_numpy(dtype=bool))):
        control = dict(width=hi-lo, covered=((y >= lo) & (y <= hi)).astype(float),
            interval_score=(hi-lo)+(2/ALPHA)*(np.maximum(0, lo-y)+np.maximum(0, y-hi)))
        candidate = dict(width=upper-lower, covered=((y >= lower) & (y <= upper)).astype(float),
            interval_score=(upper-lower)+(2/ALPHA)*(np.maximum(0, lower-y)+np.maximum(0, y-upper)))
        metrics = {}
        for name in ('interval_score', 'width', 'covered'):
            guard()
            work['delta_candidate_minus_control'] = candidate[name]-control[name]
            metrics[name] = dict(candidate=float(candidate[name][mask].mean()) if mask.any() else None,
                saved_cdf=float(control[name][mask].mean()) if mask.any() else None,
                mean_delta=float(work.loc[mask, 'delta_candidate_minus_control'].mean()) if mask.any() else None,
                week=_bootstrap(work, mask, 'week', 500, 1703), game=_bootstrap(work, mask, 'game', 500, 1703))
        reports.append(dict(population=population, planned_rows=len(rows) if population == 'all_offered'
            else int(rows.primary_role.sum()), paired_rows=int(mask.sum()), metrics=metrics,
            supported_played_zero_rows=int((mask & (y == 0)).sum()), negative_outcome_rows=int((mask & (y < 0)).sum()),
            lower_miss_frequency=dict(saved_cdf=float((y[mask] < lo[mask]).mean()) if mask.any() else None,
                candidate=float((y[mask] < lower[mask]).mean()) if mask.any() else None),
            upper_miss_frequency=dict(saved_cdf=float((y[mask] > hi[mask]).mean()) if mask.any() else None,
                candidate=float((y[mask] > upper[mask]).mean()) if mask.any() else None)))
    return dict(version=VERSION, target=target, alpha=ALPHA, reports=reports,
        outcome_states=rows.outcome_state.value_counts(dropna=False).to_dict(),
        interval_states=rows.interval_status.value_counts(dropna=False).to_dict(),
        original_fallbacks=rows.fallback.value_counts(dropna=False).to_dict(),
        primary='interval_score_lower_is_better', coverage_direction='higher_is_not_automatically_better',
        interpretation='EXPOSED_DESCRIPTIVE_INTERVAL_ONLY; no coverage guarantee, point gain, CDF calibration or release')
