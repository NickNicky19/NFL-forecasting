"""New fixed PASS_ATT family kernels for the existing shared study harness.

No file/network/store access, fit on import, alternative evaluator or scheduler.
The caller supplies authenticated, projected, cutoff-qualified shared inputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from numbers import Integral, Real


TARGET = "pass_att"
HALF_LIFE_DAYS = 365
FAMILIES = (
    "F1_CURRENT_SEASON_PLAYER_MEAN",
    "F2_PRIOR_PLUS_CURRENT_PLAYER_MEAN",
    "F3_FIXED_TIME_WEIGHTED_MULTI_SEASON",
    "F4_EARLIER_TRAINED_SHARED_WORKLOAD",
)
QUERY_FEATURES = (
    "f_player_pass_att_mean3", "f_player_pass_att_n3",
    "f_player_pass_att_mean8", "f_player_pass_att_n8",
    "f_player_games_prior", "f_team_pass_att_mean3",
)
FORBIDDEN_QUERY_COLUMNS = {
    "actual", "pass_att", "pass_cmp", "pass_td", "pass_int", "pass_yd",
    "rush_att", "rush_yd", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td",
}
QUERY_METADATA = {
    "season", "week", "game_id", "player_id", "team", "opponent", "position",
    "kickoff_utc", "cutoff_utc", "outcome_available_utc",
    "feature_max_source_available_utc", "participation_state", "is_home",
}


def utc(value):
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("aware source/query clocks required")
    return parsed.astimezone(timezone.utc)


def count(value):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0 or value != math.floor(value):
        raise ValueError("explicit finite nonnegative integral count required")
    return float(value)


def query_contract(query):
    year, week = query["season"], query["week"]
    if (isinstance(year, bool) or not isinstance(year, Integral) or year not in {2025, 2026}
            or isinstance(week, bool) or not isinstance(week, Integral)):
        raise ValueError("exact registered query years required")
    if not 1 <= week <= (18 if year == 2025 else 6) or query["position"] != "QB":
        raise ValueError("protected/unregistered period or role")
    cutoff, kickoff = utc(query["cutoff_utc"]), utc(query["kickoff_utc"])
    if cutoff > kickoff or not query["player_id"] or not query["game_id"]:
        raise ValueError("invalid frozen query identity/cutoff")
    return year, cutoff


def arithmetic_forecasts(query, eligible_history, cold_prior):
    """Three native-window means with the same fallback value when needed.

    History is already projected by the shared loader before target decoding.
    This second guard checks clocks and participation before touching each
    target value; unknown and DNP observations are never converted to zeros.
    """
    year, cutoff = query_contract(query)
    if isinstance(cold_prior, bool) or not isinstance(cold_prior, Real) or not math.isfinite(cold_prior) or cold_prior < 0:
        raise ValueError("earlier fitted conditional QB arithmetic mean required")
    same_player, seen = [], set()
    states = {"played_missing_statistic": 0, "unknown": 0, "DNP": 0}
    for row in eligible_history:
        season, week = row["season"], row["week"]
        maximum_week = 6 if season == 2026 else 17 if season in {2019, 2020} else 18
        if (isinstance(season, bool) or not isinstance(season, Integral) or not 2019 <= season <= year
                or isinstance(week, bool) or not isinstance(week, Integral)
                or not 1 <= week <= maximum_week):
            raise ValueError("unregistered history period before statistic access")
        kickoff, available = utc(row["kickoff_utc"]), utc(row["outcome_available_utc"])
        if not kickoff < available < cutoff or row["game_id"] == query["game_id"]:
            raise ValueError("history must be strictly earlier; equality is excluded")
        key = (season, week, row["game_id"], row["player_id"])
        if key in seen:
            raise ValueError("duplicate player-game history cannot multiply evidence")
        seen.add(key)
        if row["player_id"] != query["player_id"]:
            continue
        state = row["participation_state"]
        if state in {"unknown", "DNP"}:
            states[state] += 1
            continue
        if state != "played":
            raise ValueError("unrecognized qualified participation state")
        value = row.get(TARGET)
        if value is None or isinstance(value, Real) and math.isnan(value):
            states["played_missing_statistic"] += 1
            continue
        same_player.append((season, kickoff, count(value)))
    current = [value for season, _, value in same_player if season == year]
    pooled = [value for season, _, value in same_player if season >= year - 1]
    audit = dict(current_supported_history=len(current), pooled_supported_history=len(pooled),
                 full_supported_history=len(same_player), current_season_cold=not current,
                 native_fallback={FAMILIES[0]: not current, FAMILIES[1]: not pooled,
                                  FAMILIES[2]: not same_player}, older_shared_fallback_value=True,
                 ignored_history_states=states, half_life_days=HALF_LIFE_DAYS)
    weighted = [(2 ** (-(cutoff - kickoff).total_seconds() / (86400 * HALF_LIFE_DAYS)), value)
                for _, kickoff, value in same_player]
    denominator = math.fsum(weight for weight, _ in weighted)
    if same_player and denominator <= 0:
        raise ValueError("positive finite recency denominator required")
    return {
        FAMILIES[0]: math.fsum(current) / len(current) if current else float(cold_prior),
        FAMILIES[1]: math.fsum(pooled) / len(pooled) if pooled else float(cold_prior),
        FAMILIES[2]: math.fsum(weight * value for weight, value in weighted) / denominator if same_player else float(cold_prior),
    }, audit


class AnnualEstimationBudget:
    """At most two annual parameter-estimation attempts, including failures."""
    def __init__(self, persist_attempt):
        self.used = set()
        self.persist_attempt = persist_attempt

    def reserve(self, year):
        if type(year) is not int or year not in {2025, 2026} or year in self.used or len(self.used) >= 2:
            raise ValueError("annual estimation attempt already spent or unregistered")
        self.used.add(year)
        self.persist_attempt(year=year, target=TARGET, pipeline_attempt=len(self.used),
                             optimizer_calls=0, retry_allowed=False)


def shared_workload_fold(train, query, *, shared_models, clock_check, budget):
    """Use the existing mean/workload machinery once per earlier-season fold.

    No new optimization, design fitting, model-selection loop or distribution
    is added. The shared caller retains the returned prior/share state and
    vectors before any query evaluation labels may be read.
    """
    if set(query.columns) & FORBIDDEN_QUERY_COLUMNS or set(query.columns) - QUERY_METADATA - set(QUERY_FEATURES):
        raise ValueError("query projection leaked target/statistic columns")
    clock_check(train)
    clock_check(query)
    years = set(query.season.astype(int))
    if len(years) != 1 or next(iter(years)) not in {2025, 2026}:
        raise ValueError("one exact annual fold required")
    year = next(iter(years))
    if (not query.position.eq("QB").all() or not train.position.eq("QB").all()
            or not train.season.lt(year).all() or train.empty):
        raise ValueError("earlier-only QB fold required")
    cutoff = min(utc(value) for value in query.cutoff_utc)
    if any(not utc(row.kickoff_utc) < utc(row.outcome_available_utc) < cutoff
           for row in train.itertuples()):
        raise ValueError("annual training availability reaches query period")
    values = shared_models._numeric(train, TARGET)
    support = shared_models._support(values, TARGET) & train.participation_state.eq("played").to_numpy()
    supported = train.loc[support].copy()
    if supported.empty:
        raise ValueError("no supported earlier conditional played count population")
    budget.reserve(year)
    global_prior, position_priors = shared_models._priors(supported, TARGET)
    state = {}
    workload, reasons = shared_models._workload(supported, query, TARGET, global_prior, position_priors, state=state)
    recent, recent_reasons = shared_models._recent(supported, query, TARGET, global_prior, position_priors, window=3)
    pooled, pooled_reasons = shared_models._recent(supported, query, TARGET, global_prior, position_priors, window=8)
    return dict(older_QB_mean=float(global_prior.mean), workload=workload, workload_reasons=reasons,
                recent3=recent, recent3_reasons=recent_reasons, pooled8=pooled, pooled8_reasons=pooled_reasons,
                fitted_workload_state=state, annual_estimation_attempt=year, optimizer_calls=0)


def combine_families(query, history, fitted_workload, cold_prior):
    values, audit = arithmetic_forecasts(query, history, cold_prior)
    if (isinstance(fitted_workload, bool) or not isinstance(fitted_workload, Real)
            or not math.isfinite(fitted_workload) or fitted_workload < 0):
        values[FAMILIES[3]] = float(cold_prior)
        audit["workload_fallback"] = "unsupported_shared_workload_shared_older_mean"
    else:
        values[FAMILIES[3]] = float(fitted_workload)
    return values, audit


def shared_point_summary(frame, *, evaluation, loss_function):
    """Existing shared coverage and loss evaluator; no probability invention."""
    result = evaluation.summarize(frame, include_distribution=False, value_column="point")
    observed = frame.participation_state.eq("played") & frame.actual.notna() & frame.point.notna()
    result.update(loss_function(frame.loc[observed, "point"], frame.loc[observed, "actual"]))
    result["primary_metric"] = "MSE"
    result["target_product"] = "conditional_played_count_mean_estimate"
    result["calibrated_probability_claim"] = False
    return result
