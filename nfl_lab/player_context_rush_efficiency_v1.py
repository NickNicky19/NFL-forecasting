"""Earlier-only RB conditional efficiency, with a fixed external carry law.

Direction and gap describe credited PBP; they are not called blocking concepts.
Signed yards are never clamped. EPA>0 is a per-carry diagnostic, not a prop
probability. No complete-game yard law is claimed by this module.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from .abc_player_rushing_context_v1 import Context, eligible

VERSION = "A::PLAYER-CONTEXT-COMPLETION-DECISION-01-efficiency-v1"
GROUPS = {"direction": ("left", "middle", "right", "UNKNOWN"),
          "gap": ("end", "guard", "tackle", "UNKNOWN"),
          "down": ("1", "2", "3", "4", "UNKNOWN"),
          "distance": ("short", "medium", "long", "UNKNOWN")}
LEVELS = [(g, v) for g, vs in GROUPS.items() for v in vs]
LEVEL_INDEX = {x: i for i, x in enumerate(LEVELS)}
BUCKETS = ("0", "1-4", "5-9", "10-19", "20+")
WINDOW = 8
SHRINK = {"league": 40., "team": 40., "player": 20., "defense": 80., "mixture_team": 40., "mixture_player": 20.}
DEFAULT = np.array([4., .4, .25])  # Declared unsupported prior, not observed zero.
FEATURES = ["f_pce_" + actor + "_" + metric + "_" + g + "_" + v
            for actor in ("own", "team", "opp") for metric in ("yards", "success") for g, v in LEVELS]
FEATURES += ["f_pce_own_mix_" + g + "_" + v for g, v in LEVELS]
FEATURES += ["f_pce_player_share_" + g + "_" + v for g, v in LEVELS]
FEATURES += ["f_pce_team_run_rate_" + g + "_" + v for g, v in LEVELS if g in ("down", "distance")]
FEATURES += ["f_pce_" + actor + "_" + x for actor in ("own", "team", "opp") for x in ("games", "carries", "yards", "success", "supported")]
FEATURES += ["f_pce_match_" + metric + "_direction_" + v for metric in ("yards", "success") for v in GROUPS["direction"]]
# Opportunity rates and allocation shares are descriptive profile completion
# only. This wave's new predictor mechanism is conditional efficiency with a
# fixed external N law; a future opportunity change needs its own registration.
PROFILE_ONLY_FEATURES = [x for x in FEATURES if x.startswith(("f_pce_player_share_", "f_pce_team_run_rate_"))]
EFFICIENCY_FEATURES = [x for x in FEATURES if x not in PROFILE_ONLY_FEATURES]


def bucket(n):
    if n < 0 or int(n) != n:
        raise ValueError("carry stratum requires a nonnegative integer")
    return 0 if n == 0 else 1 if n <= 4 else 2 if n <= 9 else 3 if n <= 19 else 4


def context_codes(frame):
    """The accepted source already validated ranges, identities and duplicates."""
    direction = frame.run_location.fillna("UNKNOWN").astype(str)
    gap = frame.run_gap.fillna("UNKNOWN").astype(str)
    down = frame.down.map(lambda x: str(int(x)) if pd.notna(x) and x in (1, 2, 3, 4) else "UNKNOWN")
    distance = frame.ydstogo.map(lambda x: "UNKNOWN" if pd.isna(x) else "short" if x <= 2 else "medium" if x <= 6 else "long")
    return list(zip(direction, gap, down, distance))


def aggregate(frame):
    main = np.zeros((len(LEVELS), 4))  # n, signed yards, EPA>0, first down.
    cells = {}
    if not len(frame):
        return main, cells
    codes = context_codes(frame)
    for c, y, e, fd in zip(codes, frame.rushing_yards, frame.epa, frame.first_down_rush):
        value = np.array([1., float(y), float(e > 0), float(fd)])
        for g, v in zip(GROUPS, c):
            main[LEVEL_INDEX[g, v]] += value
        if c not in cells:
            cells[c] = np.zeros(4)
        cells[c] += value
    return main, cells


def total(records, name="main"):
    return sum((r[name] for r in records), np.zeros((len(LEVELS), 4)))


def overall(main):
    # Each carry appears once in each main-effect group.
    return main[:len(GROUPS["direction"])].sum(axis=0)


def smoothed(main, prior, strength):
    return (main[:, 1:] + strength * prior) / (main[:, :1] + strength)


def latest(records):
    return max((r["available"] for r in records), default=pd.NaT)


def iso(clock):
    return clock.isoformat() if pd.notna(clock) else None


class EfficiencyContext:
    """Reuse accepted source admission and preserve every declared query row."""

    def __init__(self, frames, history):
        self.accepted = Context(frames, history)
        self.players = defaultdict(list)
        self.teams = defaultdict(list)
        self.defenses = defaultdict(list)
        self.league = []
        self._league_cache = {}
        admitted = {(r["game"], r["team"]): r for r in self.accepted.source_games}
        projected = {}
        for frame in frames:
            f = frame.copy()
            for col in ("posteam", "defteam"):
                f[col] = f[col].replace({"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"})
            for (game, team), group in f.groupby(["game_id", "posteam"], sort=False):
                if (str(game), str(team)) in admitted:
                    projected[str(game), str(team)] = group
        for key, original in sorted(admitted.items(), key=lambda kv: (kv[1]["kickoff"], kv[0])):
            g = projected[key]
            a = g.loc[g.rush_attempt.eq(1) & g.two_point_attempt.eq(0)]
            main, cells = aggregate(a)
            r = {k: original[k] for k in ("game", "team", "opponent", "kickoff", "available", "season", "week")}
            r.update(main=main, cells=cells, attempts=len(a), players={})
            o = g.loc[g.two_point_attempt.eq(0) & (g.play_type.isin(["pass", "run", "qb_kneel", "qb_spike"]) | g.rush_attempt.eq(1))]
            r["opps"] = np.zeros(len(LEVELS))
            for code in context_codes(o):
                for group, value in zip(GROUPS, code):
                    if group in ("down", "distance"):
                        r["opps"][LEVEL_INDEX[group, value]] += 1
            # Defense effects are conditional residuals against that offense's
            # genuinely earlier same-context efficiency, not an overall scalar.
            old = eligible(self.teams[r["team"]], r["kickoff"], WINDOW)
            league = eligible(self.league, r["kickoff"], 512)
            lm = total(league)
            prior = smoothed(lm, np.tile(DEFAULT, (len(LEVELS), 1)), SHRINK["league"])
            expected = smoothed(total(old), prior, SHRINK["team"])
            r["residual"] = np.column_stack([main[:, 0], main[:, 1:] - main[:, :1] * expected])
            byplayer = {str(k): part for k, part in a.groupby("rusher_player_id", sort=False)}
            for player, op in original["players"].items():
                part = byplayer.get(player, a.iloc[:0])
                pm, pc = aggregate(part)
                pr = {k: r[k] for k in ("game", "team", "opponent", "kickoff", "available", "season", "week")}
                pr.update(player=player, role=op["role"], main=pm, cells=pc, attempts=len(part), bucket=bucket(len(part)), team_record=r)
                r["players"][player] = pr
                self.players[player].append(pr)
            self.teams[r["team"]].append(r)
            self.defenses[r["opponent"]].append(r)
            self.league.append(r)

    def selection(self, player, team, opponent, cutoff, window=WINDOW):
        if window not in (4, 8, 16):
            raise ValueError("undeclared appearance lookback")
        cut = pd.Timestamp(cutoff)
        if pd.isna(cut) or cut.tzinfo is None:
            raise ValueError("explicit aware profile cutoff required")
        own = eligible(self.players.get(str(player), []), cut, window)
        team_rows = eligible(self.teams.get(str(team), []), cut, window)
        defense = eligible(self.defenses.get(str(opponent), []), cut, window)
        if cut not in self._league_cache:
            self._league_cache[cut] = eligible(self.league, cut, 512)
        return own, team_rows, defense, self._league_cache[cut]

    def profile(self, player, team, opponent, cutoff, window=WINDOW, rich=True):
        own, team_rows, defense, league = self.selection(player, team, opponent, cutoff, window)
        # League RB prior is role-specific. Team and defense include all credited
        # carries; a role distinction remains explicit in their denominator.
        rb = [p for r in league for p in r["players"].values() if p["role"] == "RB"]
        pm, tm, dm, lm = total(own), total(team_rows), total(defense), total(rb)
        prior = smoothed(lm, np.tile(DEFAULT, (len(LEVELS), 1)), SHRINK["league"])
        ts = smoothed(tm, prior, SHRINK["team"])
        ps = smoothed(pm, ts, SHRINK["player"])
        residual = total(defense, "residual")
        ds = residual[:, 1:] / (dm[:, :1] + SHRINK["defense"])
        nt = overall(tm)[0]
        np_ = overall(pm)[0]
        league_n = overall(lm)[0]
        mix = np.zeros(len(LEVELS))
        for g, values in GROUPS.items():
            ix = [LEVEL_INDEX[g, v] for v in values]
            prior_mix = (lm[ix, 0] + 1.) / (league_n + len(values))
            mix[ix] = (pm[ix, 0] + SHRINK["player"] * prior_mix) / (np_ + SHRINK["player"])
        # Conditional player share uses team carries in that player's supported
        # prior appearances, distinct from own-carry mix and offensive plays.
        share_den = sum((p["team_record"]["main"][:, 0] for p in own), np.zeros(len(LEVELS)))
        share = (pm[:, 0] + 1.) / (share_den + 2.)
        op = sum((r["opps"] for r in team_rows), np.zeros(len(LEVELS)))
        runrate = (tm[:, 0] + .45 * 20.) / (op + 20.)
        f = {}
        for actor, values in (("own", ps), ("team", ts), ("opp", ds)):
            for j, metric in enumerate(("yards", "success")):
                for i, (g, v) in enumerate(LEVELS):
                    f[f"f_pce_{actor}_{metric}_{g}_{v}"] = float(values[i, j])
        for i, (g, v) in enumerate(LEVELS):
            f[f"f_pce_own_mix_{g}_{v}"] = float(mix[i])
            f[f"f_pce_player_share_{g}_{v}"] = float(share[i])
            if g in ("down", "distance"):
                f[f"f_pce_team_run_rate_{g}_{v}"] = float(runrate[i])
        for actor, records, main, values in (("own", own, pm, ps), ("team", team_rows, tm, ts), ("opp", defense, dm, ds)):
            n = overall(main)[0]
            # Weighted conditional means; missing-source prior is explicitly
            # flagged and is never reported as an observed played zero.
            weights = main[:4, 0] / n if n else np.full(4, .25)
            f.update({f"f_pce_{actor}_games": float(len(records)), f"f_pce_{actor}_carries": float(n),
                      f"f_pce_{actor}_yards": float(weights @ values[:4, 0]),
                      f"f_pce_{actor}_success": float(weights @ values[:4, 1]), f"f_pce_{actor}_supported": float(n > 0)})
        # The no-context control uses an unconditional own-YPC shrinkage. It
        # shares N exactly and does not inherit conditional-mixture advantages.
        lo, to, po = overall(lm), overall(tm), overall(pm)
        prior_overall = (lo[1:] + SHRINK["league"] * DEFAULT) / (lo[0] + SHRINK["league"])
        team_overall = (to[1:] + SHRINK["team"] * prior_overall) / (to[0] + SHRINK["team"])
        own_overall = (po[1:] + SHRINK["player"] * team_overall) / (po[0] + SHRINK["player"])
        f["f_pce_own_yards"] = float(own_overall[0])
        f["f_pce_own_success"] = float(own_overall[1])
        f["f_pce_team_yards"] = float(team_overall[0])
        f["f_pce_team_success"] = float(team_overall[1])
        for i, v in enumerate(GROUPS["direction"]):
            for j, metric in enumerate(("yards", "success")):
                f[f"f_pce_match_{metric}_direction_{v}"] = float(mix[i] * ds[i, j])
        clock = latest(own + team_rows + defense + league)
        if pd.notna(clock) and clock >= pd.Timestamp(cutoff):
            raise ValueError("profile source is not strictly earlier")
        if not rich:
            return f, clock, None
        tendencies = []
        for i, (g, v) in enumerate(LEVELS):
            for actor, records, main, values, strength in (("own", own, pm, ps, SHRINK["player"]), ("team", team_rows, tm, ts, SHRINK["team"]), ("opp", defense, dm, ds, SHRINK["defense"])):
                n = float(main[i, 0])
                dependencies = own + team_rows + league if actor == "own" else team_rows + league if actor == "team" else defense
                for j, metric in enumerate(("yards", "epa_positive", "first_down")):
                    numerator = float(residual[i, j + 1] if actor == "opp" else main[i, j + 1])
                    tendencies.append(dict(actor=actor, group=g, value=v, metric=metric + ("_earlier_offense_residual" if actor == "opp" else ""),
                        numerator=numerator, denominator=n, support_carries=int(n), support_games=int(sum(r["main"][i, 0] > 0 for r in records)),
                        lookback_appearances=window, raw=numerator / n if n else None, shrunk=float(values[i, j]),
                        prior_carries=strength, raw_latest_eligible_clock=iso(latest(records)), latest_eligible_clock=iso(latest(dependencies)),
                        state="SUPPORTED" if n else "UNSUPPORTED_SHRUNK_PRIOR"))
            for frequency, numerator, denominator, shrunk in (("own_carry_mix", pm[i, 0], np_, mix[i]), ("player_share_given_team_run", pm[i, 0], share_den[i], share[i])):
                dependencies = own + league if frequency == "own_carry_mix" else own
                tendencies.append(dict(actor="own", group=g, value=v, metric=frequency, numerator=float(numerator), denominator=float(denominator),
                    support_carries=int(numerator), support_games=len(own), lookback_appearances=window, raw=float(numerator / denominator) if denominator else None,
                    shrunk=float(shrunk), raw_latest_eligible_clock=iso(latest(own)), latest_eligible_clock=iso(latest(dependencies)),
                    state="SUPPORTED" if denominator else "UNSUPPORTED_SHRUNK_PRIOR"))
            if g in ("down", "distance"):
                tendencies.append(dict(actor="team", group=g, value=v, metric="team_runs_per_offensive_opportunity", numerator=float(tm[i, 0]), denominator=float(op[i]),
                    support_carries=int(tm[i, 0]), support_games=len(team_rows), lookback_appearances=window, raw=float(tm[i, 0] / op[i]) if op[i] else None,
                    shrunk=float(runrate[i]), latest_eligible_clock=iso(latest(team_rows)), state="SUPPORTED" if op[i] else "UNSUPPORTED_SHRUNK_PRIOR"))
        detail = dict(profile_version=VERSION, player_id=str(player), historical_team=str(team), opponent=str(opponent), cutoff_utc=iso(pd.Timestamp(cutoff)),
            source_information_max_utc=iso(clock), lookback_appearances=window, state="SUPPORTED_CARRIES" if np_ else "SUPPORTED_PLAYED_ZERO_ONLY" if own else "NO_ELIGIBLE_SOURCE_PLAYER_HISTORY",
            eligible_player_games=len(own), eligible_player_carries=int(np_), historical_teams=sorted({r["team"] for r in own}),
            source_policy="CURRENT_VINTAGE_RECONSTRUCTION_WITH_SEVEN_DAY_PROXY", tendencies=tendencies,
            role_policy="RB league mixtures; prior actual N stratum preserves workload dependence; no verified injury/limited-workload probability")
        return f, clock, detail

    def augment(self, frame, window=WINDOW, rich=False):
        rows, clocks, profiles = [], [], []
        for r in frame.itertuples():
            f, clock, detail = self.profile(r.player_id, r.team, r.opponent, r.cutoff_utc, window, rich)
            rows.append(f); clocks.append(clock)
            if rich:
                detail.update({k: int(getattr(r, k)) if k in ("season", "week") else str(getattr(r, k)) for k in ("season", "week", "game_id")})
                profiles.append(detail)
        out = pd.concat([frame.copy(), pd.DataFrame(rows, index=frame.index)], axis=1)
        old = pd.to_datetime(out.feature_max_source_available_utc, utc=True)
        new = pd.to_datetime(pd.Series(clocks, index=out.index), utc=True)
        out["feature_max_source_available_utc"] = pd.concat([old, new], axis=1).max(axis=1)
        if (out.feature_max_source_available_utc >= pd.to_datetime(out.cutoff_utc, utc=True)).any():
            raise ValueError("conditional efficiency chronology")
        return out, profiles

    def mixture(self, player, team, opponent, cutoff, stratum, window=WINDOW):
        """Joint observed contexts, shrunk within N stratum; no cross product."""
        own, team_rows, _, league = self.selection(player, team, opponent, cutoff, window)
        league_players = [p for r in league for p in r["players"].values() if p["role"] == "RB"]
        team_players = [p for r in team_rows for p in r["players"].values() if p["role"] == "RB"]
        def hist(records, b=None):
            out = Counter()
            for r in records:
                if b is None or r["bucket"] == b:
                    out.update({c: float(v[0]) for c, v in r["cells"].items()})
            return out
        # With no earlier support use a declared context prior. This is never
        # chosen from target participants, target N, or target down/direction mix.
        fallback = {("middle", "guard", "1", "long"): 1.}
        all_l = hist(league_players)
        base = {c: n / sum(all_l.values()) for c, n in all_l.items()} if all_l else fallback
        lh, th, ph = hist(league_players, stratum), hist(team_players, stratum), hist(own, stratum)
        def shrink(h, prior, strength):
            keys = sorted(set(h) | set(prior)); den = sum(h.values()) + strength
            return {c: (h[c] + strength * prior.get(c, 0.)) / den for c in keys}
        lp = shrink(lh, base, SHRINK["league"])
        tp = shrink(th, lp, SHRINK["mixture_team"])
        answer = shrink(ph, tp, SHRINK["mixture_player"])
        if not math.isclose(sum(answer.values()), 1., abs_tol=1e-12):
            raise ValueError("nonconserving context mixture")
        return answer, dict(bucket=BUCKETS[stratum], own_carries=sum(ph.values()), team_rb_carries=sum(th.values()), league_rb_carries=sum(lh.values()),
                            state="SUPPORTED_STRATUM" if ph else "SHRUNK_TEAM_LEAGUE_STRATUM", contexts=len(answer))


def carry_bucket_moments(law):
    """Exact E[N I_b] for external Leaf-CDF+geometric-prior count law.

    The unbounded 20+ tail is the full law mean minus the finite prefix moment.
    There is no truncation, simulation, plug-in mean N, or target opportunity.
    """
    if law.get("kind") != "leaf_cdf" or law["prior"]["support"] != "count":
        raise ValueError("supported fixed count-law contract required")
    support = np.asarray(law["support"], float)
    weights = np.asarray(law["weights"], float)
    b = float(law["prior_weight"]); q = float(law["prior"]["q"])
    if not (np.isfinite(support).all() and (support >= 0).all() and (support == np.floor(support)).all() and np.isfinite(weights).all()
            and (weights >= 0).all() and math.isclose(float(weights.sum()), 1., abs_tol=1e-8) and 0 <= b <= 1 and 0 < q < 1):
        raise ValueError("invalid retained count law")
    mean = (1 - b) * float(weights @ support) + b * q / (1 - q)
    ns = np.arange(20, dtype=float)
    pmf = (1 - b) * np.array([weights[support == n].sum() for n in ns]) + b * (1 - q) * q ** ns
    moment = [0., float(ns[1:5] @ pmf[1:5]), float(ns[5:10] @ pmf[5:10]), float(ns[10:20] @ pmf[10:20])]
    moment.append(mean - sum(moment))
    if min(moment) < -1e-9 or not math.isclose(sum(moment), mean, abs_tol=1e-10):
        raise ValueError("invalid exact count bucket first moments")
    return np.asarray(moment), mean


def carry_design(profile_features, context, stratum):
    """Interpretable main effects plus conditional defender-direction effects."""
    values = []
    for actor in ("own", "team", "opp"):
        for name in ("games", "carries"):
            values.append(math.log1p(profile_features[f"f_pce_{actor}_{name}"]))
        values += [profile_features[f"f_pce_{actor}_yards"], profile_features[f"f_pce_{actor}_success"]]
    for group, value in zip(GROUPS, context):
        values += [float(value == level) for level in GROUPS[group]]
        for actor in ("own", "team", "opp"):
            values += [profile_features[f"f_pce_{actor}_{metric}_{group}_{value}"] for metric in ("yards", "success")]
    values += [float(stratum == j) for j in range(1, 5)]
    direction = context[0]
    values += [profile_features[f"f_pce_match_{metric}_direction_{direction}"] for metric in ("yards", "success")]
    return np.asarray(values, float)


@dataclass
class ConditionalCarryModel:
    scaler: object
    yards: object | None = None
    success: object | None = None
    audit: dict | None = None

    def predict(self, features, context, stratum):
        y, p = self.predict_many(features, [(context, stratum)])
        return float(y[0]), float(p[0])

    def predict_many(self, features, contexts):
        x = self.scaler.transform(np.asarray([carry_design(features, c, b) for c, b in contexts]))
        if self.yards is None or self.success is None:
            raise ValueError("both returned conditional fits required")
        y = self.yards.predict(x)
        p = self.success.predict_proba(x)[:, list(self.success.classes_).index(1)]
        if not np.isfinite(y).all() or not ((p >= 0) & (p <= 1)).all():
            raise ValueError("invalid conditional model output")
        return y, p


def integrated_point(model, context, row, law, window=WINDOW):
    f, clock, _ = context.profile(row.player_id, row.team, row.opponent, row.cutoff_utc, window, False)
    moments, nmean = carry_bucket_moments(law)
    point, success_expected, mixtures = 0., 0., []
    for b in range(1, 5):
        mixture, audit = context.mixture(row.player_id, row.team, row.opponent, row.cutoff_utc, b, window)
        mu, ps = 0., 0.
        yy, pp = model.predict_many(f, [(c, b) for c in mixture])
        probabilities = np.asarray(list(mixture.values()))
        mu, ps = float(probabilities @ yy), float(probabilities @ pp)
        point += moments[b] * mu
        success_expected += moments[b] * ps
        mixtures.append(dict(**audit, carry_first_moment=float(moments[b]), conditional_signed_yards=mu, conditional_epa_positive=ps))
    return dict(point=float(point), no_context_fixed_n_point=float(nmean * f["f_pce_own_yards"]),
        fixed_n_mean=float(nmean), bucket_first_moments=moments.tolist(), mixtures=mixtures,
        per_carry_epa_positive=success_expected / nmean if nmean else None,
        source_information_max_utc=iso(clock), probability=None, outcome_law=None,
        point_semantics="EXPECTED_SIGNED_TOTAL_FROM_CONDITIONAL_MEAN_AND_FIXED_EXTERNAL_COUNT_LAW",
        probability_state="N/A_NO_COMPLETE_GAME_OUTCOME_LAW; per-carry success is not prop win probability")
