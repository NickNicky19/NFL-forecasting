"""Versioned aligned source-timing sensitivity; no I/O, fits or promotion.

Only rows from the explicitly bound historical seven-day reconstruction may be
retimed. No proxy clock is authenticated publication. Explicit unknowns remain
unknown; nonproxy clocks are retained. Upcoming queries remain nonobservations.
The old seven-day modules are neither mutated nor monkeypatched.
"""
from __future__ import annotations
from collections import defaultdict
import time
import numpy as np
import pandas as pd
from .abc_player_rushing_context_v1 import Context, eligible, counts, sums, GROUPS, N
from .player_context_rush_efficiency_v1 import (
    EfficiencyContext, aggregate, total, overall, smoothed, bucket, context_codes,
    LEVELS, LEVEL_INDEX, SHRINK, DEFAULT, WINDOW,
)
VERSION = "A::PROFILE-INCREMENT-CLOSURE-AND-NEXT-02::ALIGNED_48H_SENSITIVITY-v1"
ORIGINAL = "RECONSTRUCTED_KICKOFF_PLUS_7_DAYS"
ALTERNATIVE = "KICKOFF_PLUS_48H_RECONSTRUCTED_SENSITIVITY"
POLICIES = {ORIGINAL: 168, ALTERNATIVE: 48}
CLOCK_KIND_FIELD = "availability_clock_kind"
CLOCK_KINDS = {ORIGINAL, "AUTHENTICATED_ORIGINAL_OBSERVATION", "AUTHENTICATED_CORRECTION_OBSERVATION", "UNVERIFIED_VERSION_CLOCK", "UNKNOWN"}
PROVENANCE = ["timing_original_available_utc", "timing_original_proxy", "timing_original_clock_kind", "timing_policy_id"]

def aware(values):
    s=pd.Series(values).copy()
    parsed=s.map(lambda v: pd.Timestamp(v) if pd.notna(v) else pd.NaT)
    if any(pd.notna(v) and v.tzinfo is None for v in parsed):
        raise ValueError("unknown or naive source time is not authenticated")
    return pd.to_datetime(parsed, utc=True)

def retime_history(history, policy, *, declared_source_lane):
    if policy not in POLICIES or declared_source_lane != ORIGINAL:
        raise ValueError("explicit bound reconstruction lane and registered policy required")
    if not {"kickoff_utc", "outcome_available_utc"} <= set(history):
        raise ValueError("explicit availability column required; absent is not authenticated")
    if set(PROVENANCE) & set(history):
        raise ValueError("history already carries timing provenance; do not apply twice")
    h=history.copy();k=aware(h.kickoff_utc);a=aware(h.outcome_available_utc)
    if k.isna().any() or (a.notna() & a.le(k)).any():
        raise ValueError("invalid historical kickoff/availability ordering")
    if CLOCK_KIND_FIELD in h:
        kind=h[CLOCK_KIND_FIELD].fillna("UNKNOWN").astype(str)
        if not kind.isin(CLOCK_KINDS).all():
            raise ValueError("clock-kind semantics require an explicit source mapping")
    else:
        # This fallback is licensed only by the hash-bound whole-source lane,
        # never by a numerical clock equality as proof of observation timing.
        kind=pd.Series(ORIGINAL,index=h.index)
    proxy=a.notna() & a.eq(k+pd.Timedelta(days=7)) & kind.eq(ORIGINAL)
    h["timing_original_clock_kind"]=kind
    h["timing_original_available_utc"]=a
    h["timing_original_proxy"]=proxy.to_numpy(bool)
    h["timing_policy_id"]=policy
    replacement=k+pd.Timedelta(hours=POLICIES[policy])
    h["outcome_available_utc"]=a.where(~proxy,replacement)
    audit=dict(policy=policy,declared_source_lane=declared_source_lane,rows=len(h),
        proxy_rows=int(proxy.sum()),unknown_preserved=int(a.isna().sum()),
        nonproxy_known_preserved=int((a.notna() & ~proxy).sum()),
        explicitly_authenticated_rows_preserved=int((a.notna() & kind.isin(["AUTHENTICATED_ORIGINAL_OBSERVATION","AUTHENTICATED_CORRECTION_OBSERVATION"])).sum()),
        authenticated_observation_clocks=False,
        meaning="Current-vintage timing sensitivity, not actual historical observation or availability")
    return h,audit

def require_policy_history(history, policy):
    if policy not in POLICIES or not set(PROVENANCE) <= set(history):
        raise ValueError("registered policy/provenance required for contextual construction")
    if not history.timing_policy_id.eq(policy).all():
        raise ValueError("mixed source timing policies")
    k=aware(history.kickoff_utc);a=aware(history.outcome_available_utc)
    old=aware(history.timing_original_available_utc)
    proxy=history.timing_original_proxy
    if not proxy.isin([True,False]).all():raise ValueError("invalid proxy provenance")
    expected=old.where(~proxy,k+pd.Timedelta(hours=POLICIES[policy]))
    if not (a.eq(expected) | (a.isna() & expected.isna())).all():
        raise ValueError("availability policy altered without matching provenance")
    kind=history.timing_original_clock_kind
    if not kind.isin(CLOCK_KINDS).all():raise ValueError("invalid original clock-class provenance")
    if not (proxy == (old.notna() & old.eq(k+pd.Timedelta(days=7)) & kind.eq(ORIGINAL))).all():
        raise ValueError("proxy membership does not match bound original lane")
    if (a.notna() & a.le(k)).any():raise ValueError("historical availability must follow game")

class TimingContext(Context):
    def __init__(self, frames, history, policy):
        require_policy_history(history, policy)
        self.players=defaultdict(list);self.teams=defaultdict(list);self.defenses=defaultdict(list)
        self.league=[];self.source_games=[];self.component_rows=[];self._league_cache={};self.withheld_future_source_games=set()
        if history.duplicated(['game_id','player_id']).any() or history[['game_id','player_id','team']].isna().any(axis=None):
            raise ValueError('missing or duplicate canonical historical identity')
        for _,gg in history.groupby('game_id',sort=False):
            for name in ['kickoff_utc','outcome_available_utc']:
                values=pd.to_datetime(gg[name],utc=True,errors='coerce')
                if values.isna().any()or values.nunique()!=1:raise ValueError('conflicting or explicitly unknown context clock: '+name)
            # Exact source-policy provenance was checked before construction.
            # All subsequent admission/recency/residual calculations use its clocks.
        clocks=history.groupby('game_id').agg(kickoff=('kickoff_utc','first'),available=('outcome_available_utc','first'))
        clocks['kickoff']=pd.to_datetime(clocks.kickoff,utc=True,errors='raise')
        clocks['available']=pd.to_datetime(clocks.available,utc=True,errors='coerce')
        hmap={(str(r.game_id),str(r.player_id)):r for r in history.itertuples()}
        entries=[];seen=set()
        for frame in frames:
            frame=frame.copy()
            # Existing nfl_lab.data._team canonical identity policy; exact alias,
            # never name fuzzing or today's roster for a historical game.
            for name in ['posteam','defteam']:
                frame[name]=frame[name].replace({'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'})
            if not frame.season_type.eq('REG').all()or frame[['game_id','play_id']].isna().any(axis=None):raise ValueError('REG identity boundary')
            keys=list(zip(frame.game_id.astype(str),frame.play_id.astype(str)))
            if len(set(keys))!=len(keys)or seen.intersection(keys):raise ValueError('duplicate source play including non-carry denominator')
            seen.update(keys)
            for name,lo,hi in [('down',1,4),('ydstogo',0,100),('yardline_100',0,100)]:
                vv=pd.to_numeric(frame[name],errors='coerce');known=frame[name].notna()
                if (known&(~np.isfinite(vv)|~vv.between(lo,hi))).any():raise ValueError('invalid observed context support: '+name)
            for (game,team),g in frame.groupby(['game_id','posteam'],sort=False):
                if pd.isna(team):continue
                if game not in clocks.index:
                    # W7 target rows need no known-outcome clock. Their PBP is
                    # deliberately outside the retained W1-6 history admission.
                    if g.season.eq(2026).all()and g.week.eq(7).all():
                        self.withheld_future_source_games.add(str(game));continue
                    raise ValueError('source game missing declared history identity')
                clock=clocks.loc[game]
                if pd.isna(clock.available)or clock.available<=clock.kickoff:raise ValueError('invalid retained history clock')
                a=g.loc[g.rush_attempt.eq(1)&g.two_point_attempt.eq(0)]
                o=g.loc[g.two_point_attempt.eq(0)&(g.play_type.isin(['pass','run','qb_kneel','qb_spike'])|g.rush_attempt.eq(1))]
                if o.empty:continue
                defender=g.defteam.dropna().unique()
                if len(defender)!=1:raise ValueError('ambiguous historical defense')
                # No-play/nullifier and penalties follow official credited flag, not convenience filtering.
                r=dict(game=str(game),team=str(team),opponent=str(defender[0]),kickoff=clock.kickoff,
                  available=clock.available,season=int(g.season.iloc[0]),week=int(g.week.iloc[0]),
                  attempts=len(a),offensive=len(o),mix=counts(a),metrics=sums(a),
                  down_runs=np.array([a.down.eq(i).sum()for i in range(1,5)],float),
                  down_opps=np.array([o.down.eq(i).sum()for i in range(1,5)],float),
                  location_runs=np.array([a.run_location.fillna('UNKNOWN').eq(x).sum()for x in GROUPS['location']],float))
                playercounts=a.groupby('rusher_player_id',dropna=False).size().to_dict()
                r['players']={}
                for player,ap in a.groupby('rusher_player_id',dropna=False):
                    if pd.isna(player):raise ValueError('unknown rusher bucket must be explicitly supported')
                    h=hmap.get((str(game),str(player)))
                    if h is not None and str(h.team)!=str(team):raise ValueError('historical player-team identity mismatch')
                    role=str(h.position)if h is not None else'UNKNOWN'
                    pr={**{k:r[k]for k in ['game','team','opponent','kickoff','available','season','week']},
                      'attempts':len(ap),'mix':counts(ap),'metrics':sums(ap),'role':role,
                      'down_runs':np.array([ap.down.eq(i).sum()for i in range(1,5)],float),'team_record':r}
                    r['players'][str(player)]=pr
                if sum(x['attempts']for x in r['players'].values())!=r['attempts']:raise ValueError('nonconserving credited source')
                entries.append(r)
        # Add supported played-zero appearances; never manufacture unknown/DNP zeros.
        bygame={(r['game'],r['team']):r for r in entries}
        for h in history.itertuples():
            r=bygame.get((str(h.game_id),str(h.team)))
            if r is None or str(h.player_id)in r['players']or h.participation_state!='played' or pd.isna(h.rush_att)or h.rush_att!=0:continue
            r['players'][str(h.player_id)]={**{k:r[k]for k in ['game','team','opponent','kickoff','available','season','week']},
              'attempts':0,'mix':np.zeros(N),'metrics':np.zeros(7),'role':str(h.position),'down_runs':np.zeros(4),'team_record':r}
        for r in sorted(entries,key=lambda x:(x['kickoff'],x['game'],x['team'])):
            old=eligible(self.teams[r['team']],r['kickoff'],8)
            # Historical opponent residual is relative to that offense's EARLIER history.
            n=sum(x['attempts']for x in old);op=sum(x['offensive']for x in old)
            league=eligible(self.league,r['kickoff'],512)
            ln=sum(x['attempts']for x in league);lop=sum(x['offensive']for x in league)
            lmetric=sum((x['metrics']for x in league),np.zeros(7))/ln if ln else np.array([4.,.4,.1,.25,.4,0.,0.])
            lm=sum((x['metrics']for x in old),np.zeros(7))
            expected=(lm+40*lmetric)/(n+40)
            rate=(n+40*((ln/lop)if lop else .45))/(op+40)
            r['run_residual']=r['attempts']-r['offensive']*rate
            r['metric_residual']=r['metrics']-r['attempts']*expected
            do=sum((x['down_opps']for x in old),np.zeros(4));dr=sum((x['down_runs']for x in old),np.zeros(4))
            r['down_residual']=r['down_runs']-r['down_opps']*(dr+10*rate)/(do+10)
            loc=sum((x['location_runs']for x in old),np.zeros(4));priorloc=sum((x['location_runs']for x in league),np.zeros(4))
            priorloc=(priorloc+1)/(ln+4)
            r['location_residual']=r['location_runs']-r['attempts']*(loc+10*priorloc)/(n+10)
            self.teams[r['team']].append(r);self.defenses[r['opponent']].append(r);self.league.append(r)
            self.source_games.append(r)
            for player,p in r['players'].items():self.players[player].append(p)


class TimingEfficiencyContext(EfficiencyContext):
    def __init__(self, frames, history, policy):
        self.timing_policy = policy
        self.accepted = TimingContext(frames, history, policy)
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

    def profile(self, player, team, opponent, cutoff, window=WINDOW, rich=True):
        values, clock, detail = super().profile(player, team, opponent, cutoff, window, rich)
        if detail is not None:
            detail["parent_profile_version"] = detail["profile_version"]
            detail["profile_version"] = VERSION + "::" + self.timing_policy
            detail["source_policy"] = self.timing_policy
            detail["authenticated_source_observation"] = False
        return values, clock, detail

KEY = ["season", "week", "game_id", "player_id"]
CTX = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
BASE_STATS=("rush_att","rush_yd","rec_tgt","rec","rec_yd","offense_snaps")
BASE30=tuple("f_player_"+stat+"_"+kind+str(window) for stat in BASE_STATS for window in (3,8)for kind in ("mean","n"))+(
    "f_player_games_prior","f_player_play_rate8","f_player_known_participation_n8",
    "f_player_rush_ypa3","f_player_rec_ypt3","f_player_rec_catch_rate3")


def raw_features_input(frame, features_module):
    """Project retained raw facts; never treat cached f_* values as new input."""
    names = list(dict.fromkeys(KEY + CTX + ["season_type", "game_type", "participation_state", "outcome_available_utc", "is_home", CLOCK_KIND_FIELD] +
        features_module.PLAYER_STATS + ["team_stat_" + n for n in features_module.TEAM_STATS]))
    out = frame.loc[:, [n for n in names if n in frame]].copy()
    if not {"game_id", "player_id", "team", "opponent", "kickoff_utc", "participation_state", "outcome_available_utc"} <= set(out):
        raise ValueError("qualified raw feature identities/clocks required")
    out["kickoff_utc"] = aware(out.kickoff_utc)
    out["outcome_available_utc"] = aware(out.outcome_available_utc)
    if "cutoff_utc" not in out:
        out["cutoff_utc"] = out.kickoff_utc
    else:
        out["cutoff_utc"] = aware(out.cutoff_utc)
    if out.cutoff_utc.isna().any() or out.cutoff_utc.gt(out.kickoff_utc).any():
        raise ValueError("explicit raw source/target cutoff contract required")
    if out.duplicated(["game_id", "player_id"]).any():
        raise ValueError("raw source identity/version overlap unresolved")
    out.attrs.clear()
    return out


def rebuild_training(raw_warm_source, cached_fit_rows, features_module, policy):
    """Preserve complete warm history before selecting the exact old fit keys."""
    raw = raw_features_input(raw_warm_source, features_module)
    timed, audit = retime_history(raw, policy, declared_source_lane=ORIGINAL)
    built = features_module.build_features(timed)
    # The old exact operational contract leaves this denominator-unqualified
    # predictor missing; a new policy is not permission to make it a probability.
    built["f_player_play_rate8"] = np.nan
    wanted = pd.MultiIndex.from_frame(cached_fit_rows[KEY])
    index = built.set_index(KEY, drop=False)
    if wanted.has_duplicates or not wanted.isin(index.index).all():
        raise ValueError("registered training-key subset changed")
    out = index.loc[wanted].reset_index(drop=True)
    if not out[KEY].equals(cached_fit_rows[KEY].reset_index(drop=True)):
        raise ValueError("training identity order changed")
    if not out.position.eq("RB").all():
        raise ValueError("role population must precede design/forest/prior fitting")
    limit = pd.Timestamp("2026-09-01", tz="UTC")
    if not out.season.lt(2026).all() or out.outcome_available_utc.isna().any() or not out.outcome_available_utc.lt(limit).all():
        raise ValueError("2026 annual training origin admission changed")
    guard = aware(out.feature_max_source_available_utc)
    if (guard.notna() & guard.ge(out.cutoff_utc)).any():
        raise ValueError("training features contain a nonprior observation")
    out.attrs.clear()
    return out, audit


def rebuild_queries(raw_history, query_frame, features_module, policy, *, progress=None, own_source_projection=False, consumed_columns=None):
    """Apply the same policy as training at each original query's own cutoff.

    A future query has no own outcome availability. A separate internal-only
    nonobservation marker preserves old cold-group counts, lies after every
    target in the batch and carries no statistic/participation observation.
    """
    if own_source_projection and (policy != ALTERNATIVE or tuple(consumed_columns or ()) != BASE30):
        raise ValueError("source projection requires the exact registered own-player-only base30 whitelist")
    history = raw_features_input(raw_history, features_module)
    history, audit = retime_history(history, policy, declared_source_lane=ORIGINAL)
    if not (history.season.lt(2026) | history.season.eq(2026) & history.week.le(6)).all():
        raise ValueError("original retained real history is through2026W6 only")
    q = query_frame.loc[:, [n for n in KEY+CTX+["season_type", "is_home", "query_clock_contract", "query_evidence_tier"] if n in query_frame]].copy()
    if q.duplicated(KEY).any() or not q.position.eq("RB").all():
        raise ValueError("frozen RB query universe required")
    for name in ["kickoff_utc", "cutoff_utc"]:
        q[name] = aware(q[name])
    if q.cutoff_utc.isna().any() or q.kickoff_utc.isna().any() or q.cutoff_utc.gt(q.kickoff_utc).any():
        raise ValueError("invalid original query horizon")
    q["freshness_query_order"] = np.arange(len(q))
    blank = [*features_module.PLAYER_STATS, *("team_stat_" + x for x in features_module.TEAM_STATS)]
    result = []
    if policy == ORIGINAL:
        batches=[(week,q.loc[q.week.eq(week)].copy().reset_index(drop=True))for week in sorted(map(int,q.week.unique()))]
    else:
        batches=[(cut,group.copy().reset_index(drop=True))for cut,group in q.groupby("cutoff_utc",sort=True)]
    for batch_index,(batch_key,target) in enumerate(batches,1):
        batch_cpu=time.process_time();batch_wall=time.monotonic()
        if policy == ORIGINAL:
            # Exact old seven-day query recipe remains the parity comparator.
            source=history.loc[history.season.lt(2026) | history.season.eq(2026) & history.week.lt(int(batch_key))].copy()
        else:
            # Align the changed policy with historical training and context
            # construction: availability, not NFL-week membership, admits facts.
            cut=pd.Timestamp(batch_key)
            source=history.loc[history.outcome_available_utc.notna() & history.outcome_available_utc.lt(cut) & history.kickoff_utc.lt(cut)].copy()
            source=source.loc[~source.game_id.isin(target.game_id)].copy()
        target_keys=pd.MultiIndex.from_frame(target[KEY])
        source=source.loc[~pd.MultiIndex.from_frame(source[KEY]).isin(target_keys)].copy()
        full_source_rows=len(source)
        if own_source_projection:
            # This is an I/O/computation projection, not training/population
            # selection. Every historical role/team row for each query player
            # remains. The 30 consumed scalar fields have only own-player inputs;
            # full team/league PCE history is built separately and unchanged.
            source=source.loc[source.player_id.isin(target.player_id)].copy()
        source["cutoff_utc"] = source.kickoff_utc
        target["outcome_available_utc"] = target.kickoff_utc + pd.Timedelta(days=7)
        if target.outcome_available_utc.le(target.cutoff_utc.max()).any():
            raise ValueError("internal nonobservation marker would enter target batch history")
        target["participation_state"] = "unknown"
        for name in blank:
            target[name] = np.nan
        assembled = pd.concat([source, target], ignore_index=True)
        rebuilt = features_module.build_features(assembled).iloc[len(source):].copy()
        rebuilt["outcome_available_utc"] = pd.NaT
        rebuilt["participation_state"] = "unknown"
        rebuilt["f_player_play_rate8"] = np.nan
        rebuilt["participation_probability_state"] = "unavailable_incomplete_nonappearance_denominator"
        rebuilt["feature_max_assumed_history_available_utc"] = rebuilt.feature_max_source_available_utc
        # The original target values are never returned to a model adapter.
        rebuilt.drop(columns=[n for n in blank if n in rebuilt], inplace=True)
        for name in PROVENANCE:
            if name in rebuilt:
                rebuilt.drop(columns=name, inplace=True)
        rebuilt.attrs.clear(); result.append(rebuilt)
        if progress is not None:
            progress(dict(policy=policy,batch_index=batch_index,total_batches=len(batches),
                query_rows=len(target),source_rows=len(source),full_time_eligible_source_rows=full_source_rows,own_source_projection=own_source_projection,CPU_seconds=time.process_time()-batch_cpu,
                wall_seconds=time.monotonic()-batch_wall))
    out = pd.concat(result, ignore_index=True).sort_values("freshness_query_order",kind="stable").reset_index(drop=True)
    out.drop(columns="freshness_query_order",inplace=True)
    if not out[KEY].equals(query_frame[KEY].reset_index(drop=True)):
        raise ValueError("original query identity/order changed")
    guard = aware(out.feature_max_source_available_utc)
    if (guard.notna() & guard.ge(out.cutoff_utc)).any():
        raise ValueError("query features contain a nonprior observation")
    out.attrs.clear()
    return out, audit


def exact_columns(left, right, columns):
    if not left[KEY].reset_index(drop=True).equals(right[KEY].reset_index(drop=True)):
        raise ValueError("parity population/order differs")
    differences = {}
    for name in columns:
        a = pd.to_numeric(left[name],errors="raise").to_numpy(float)
        b = pd.to_numeric(right[name],errors="raise").to_numpy(float)
        n = int((~((a==b) | (np.isnan(a)&np.isnan(b)))).sum())
        if n: differences[name]=n
    return dict(rows=len(left), columns=len(columns), changed_columns=differences,
                state="PASS_EXACT_NUMERIC_AND_MISSINGNESS" if not differences else "FAIL_DIFFERENT_BASELINE")


def age_records(context, queries):
    """Source-only per-query membership/clock facts, never outcomes or grades."""
    out=[]
    for row in queries.itertuples():
        cutoff=pd.Timestamp(row.cutoff_utc)
        selected=context.selection(row.player_id,row.team,row.opponent,cutoff,8)
        record={k:int(getattr(row,k)) if k in {"season","week"} else str(getattr(row,k)) for k in KEY}
        record["cutoff_utc"]=cutoff.isoformat()
        for actor, rows in zip(["own","team","defense","league"],selected):
            game=max((r["kickoff"] for r in rows),default=pd.NaT)
            available=max((r["available"] for r in rows),default=pd.NaT)
            record[actor]=dict(eligible_games=len(rows),latest_prior_game_utc=game.isoformat() if pd.notna(game)else None,
                latest_assumed_availability_utc=available.isoformat() if pd.notna(available)else None,
                game_age_days=(cutoff-game).total_seconds()/86400 if pd.notna(game)else None,
                assumed_availability_age_days=(cutoff-available).total_seconds()/86400 if pd.notna(available)else None,
                authenticated_observation_age_days=None)
        out.append(record)
    return out


def ordinary_age_records(history, queries):
    """Actual finite-value support for base30, not the global guard timestamp."""
    groups={str(k):v.sort_values(["kickoff_utc","game_id"],kind="stable") for k,v in history.groupby("player_id",sort=False)}
    stats=["rush_att","rush_yd","rec_tgt","rec","rec_yd","offense_snaps"]
    policies=history.timing_policy_id.dropna().unique() if "timing_policy_id" in history else []
    if len(policies)!=1 or policies[0] not in POLICIES:
        raise ValueError("age audit requires one declared source timing policy")
    out=[]
    for r in queries.itertuples():
        cut=pd.Timestamp(r.cutoff_utc);h=groups.get(str(r.player_id))
        if h is None:h=history.iloc[:0]
        h=h.loc[h.outcome_available_utc.notna() & h.outcome_available_utc.lt(cut) & h.kickoff_utc.lt(cut) & h.game_id.ne(r.game_id)]
        if policies[0]==ORIGINAL:
            h=h.loc[h.season.lt(int(r.season)) | h.season.eq(int(r.season)) & h.week.lt(int(r.week))]
        item={k:int(getattr(r,k)) if k in {"season","week"} else str(getattr(r,k)) for k in KEY}
        item["cutoff_utc"]=cut.isoformat();item["eligible_prior_rows"]=len(h);item["fields"]={}
        for n in (3,8):
            chosen=h.tail(n)
            for stat in stats:
                values=pd.to_numeric(chosen[stat],errors="coerce") if stat in chosen else pd.Series(np.nan,index=chosen.index)
                good=chosen.loc[np.isfinite(values)]
                last=good.kickoff_utc.max() if len(good)else pd.NaT
                clock=good.outcome_available_utc.max() if len(good)else pd.NaT
                item["fields"][stat+"_last"+str(n)]=dict(window_rows=len(chosen),finite_values=len(good),
                    latest_value_game_utc=last.isoformat() if pd.notna(last)else None,
                    latest_assumed_availability_utc=clock.isoformat() if pd.notna(clock)else None,
                    game_age_days=(cut-last).total_seconds()/86400 if pd.notna(last)else None,
                    assumed_availability_age_days=(cut-clock).total_seconds()/86400 if pd.notna(clock)else None,
                    authenticated_observation_age_days=None)
        out.append(item)
    return out


def age_summary(records, kind, membership=None):
    """Public aggregate projection, with no identities or observed outcomes."""
    def dist(values):
        v=[float(x)for x in values if x is not None and np.isfinite(x)]
        return dict(known=len(v),minimum=min(v)if v else None,median=float(np.median(v))if v else None,
                    mean=float(np.mean(v))if v else None,p90=float(np.percentile(v,90))if v else None,maximum=max(v)if v else None)
    selected=[r for r in records if membership is None or tuple(r[k]for k in KEY)in membership]
    out=[]
    for week in sorted({r["week"]for r in selected}):
        rows=[r for r in selected if r["week"]==week]
        fields=sorted({name for r in rows for name in (r["fields"] if kind=="ordinary"else ["own","team","defense","league"])})
        for field in fields:
            vals=[r["fields"][field] if kind=="ordinary"else r[field] for r in rows]
            out.append(dict(season=2026,week=week,field=field,queries=len(rows),
                game_age_days=dist([v["game_age_days"]for v in vals]),
                assumed_availability_age_days=dist([v["assumed_availability_age_days"]for v in vals]),
                authenticated_observation_age_days=None,meaning="Reconstructed clocks; game age and availability age are distinct"))
    return out


def align_cached_queries(query_base, query_profile):
    """One-to-one KEY+CTX alignment; no positional or name-only matching."""
    keys=KEY+CTX
    if any(not set(keys)<=set(f) or f.duplicated(KEY).any() for f in [query_base,query_profile]):
        raise ValueError("missing or duplicate saved canonical query identities")
    if len(query_base)!=len(query_profile) or query_base[keys].isna().any(axis=None) or query_profile[keys].isna().any(axis=None):
        raise ValueError("saved context count/null contract differs")
    joined=query_base[keys].merge(query_profile,on=keys,how="left",validate="one_to_one",sort=False,indicator=True)
    if not joined._merge.eq("both").all():
        raise ValueError("saved profile missing or historical context conflicts")
    result=joined.loc[:,list(query_profile)].copy()
    if not result[KEY].reset_index(drop=True).equals(query_base[KEY].reset_index(drop=True)):
        raise ValueError("saved profile alignment changed canonical query order")
    return result
