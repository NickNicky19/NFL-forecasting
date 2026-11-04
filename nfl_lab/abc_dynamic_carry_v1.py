"""A-owned forward-only credited-carry state and finite-allocation adapter.

No injury scenarios, snaps, routes, target-game participation or designed-run
claims. Forecast laws condition on appearance. The caller binds source rights,
identity, clocks and the eligible pregame roster. This is a research adapter.
"""
from __future__ import annotations
import math
from functools import lru_cache
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.special import expit, gammaln, betaln
from scipy.stats import nbinom

VERSION = "A::dynamic-credited-carry-state-v1"
FEATURES = ["f_dcarry_share", "f_dcarry_share_sd", "f_dcarry_logit_var",
    "f_dcarry_observations", "f_dcarry_days_since", "f_dcarry_innovation",
    "f_dcarry_recency_share", "f_dcarry_team_mu", "f_dcarry_team_var",
    "f_dcarry_expected", "f_dcarry_peer_RB_share", "f_dcarry_other_share"]
ROLES = ("QB", "RB", "FB", "WR", "TE")
RHO = .95
TAIL = 1e-12

@dataclass
class TeamGame:
    season: int
    week: int
    game: str
    team: str
    kickoff: pd.Timestamp
    available: pd.Timestamp
    total: int
    known: dict
    unresolved: int

def compile_history(frame):
    h = frame.copy()
    if h.duplicated(["game_id", "player_id"]).any():
        raise ValueError("duplicated player-game history")
    for name in ("kickoff_utc", "outcome_available_utc"):
        h[name] = pd.to_datetime(h[name], utc=True, errors="raise")
    if h[["kickoff_utc", "outcome_available_utc"]].isna().any(axis=None):
        raise ValueError("missing history clock")
    if not (h.outcome_available_utc > h.kickoff_utc).all():
        raise ValueError("availability is not after game")
    records = []
    for (team, game), g in h.groupby(["team", "game_id"], sort=False):
        if g.kickoff_utc.nunique()!=1 or g.outcome_available_utc.nunique()!=1:
            raise ValueError("team-game clocks differ")
        total = pd.to_numeric(g.team_stat_rush_att, errors="coerce").dropna().unique()
        if len(total)!=1 or not np.isfinite(total[0]) or total[0]<0 or total[0]%1:
            raise ValueError("unqualified provider all-position team total")
        total = int(total[0]); known = {}
        for r in g.itertuples():
            c = getattr(r, "rush_att")
            if r.participation_state != "played" or pd.isna(c):
                continue  # Unknown/DNP/missing are never zero observations.
            if not np.isfinite(c) or c<0 or c%1 or c>total:
                raise ValueError("invalid credited carry count")
            known[str(r.player_id)] = (int(c), str(r.position))
        residual = total - sum(c for c, _ in known.values())
        if residual<0:
            raise ValueError("supported players exceed provider team total")
        r = g.iloc[0]
        records.append(TeamGame(int(r.season), int(r.week), str(game), str(team),
            r.kickoff_utc, r.outcome_available_utc, total, known, residual))
    return sorted(records, key=lambda r:(r.available,r.kickoff,r.game,r.team))

def annual_parameters(records, year):
    """Empirical-Bayes parameters use ONLY earlier-season available records.

    The first year has disclosed fixed startup constants, not future priors.
    Process variance is a bounded deconvolved logit-change moment; no search.
    """
    origin = pd.Timestamp(f"{year}-09-01", tz="UTC")
    old = [r for r in records if r.season<year and r.available<origin]
    byrole = {p:[] for p in ROLES}; sequences = {}
    for r in old:
        for player, (c, role) in r.known.items():
            if role not in byrole: continue
            z = math.log((c+.5)/(r.total-c+.5))
            v = 1/(c+.5)+1/(r.total-c+.5)
            byrole[role].append((z,v,c,r.total))
            sequences.setdefault((r.team,player,role),[]).append((z,v,r))
    params = {}
    for role in ROLES:
        values = byrole[role]
        if not values:
            share = {"RB":.2,"QB":.1,"FB":.02,"WR":.015,"TE":.01}[role]
            params[role] = dict(center=math.log(share/(1-share)),variance=1.,q=.10,
                share=share,rows=0,startup="FIXED_UNTRAINED_ROLE_PRIOR")
            continue
        means = [np.mean([x[0] for x in a]) for k,a in sequences.items() if k[2]==role]
        changes = []
        for k, a in sequences.items():
            if k[2]!=role: continue
            for x,y in zip(a,a[1:]):
                if x[2].season==y[2].season:
                    changes.append((y[0]-x[0])**2-y[1]-x[1])
        q = min(1.5,max(.01,float(np.mean(changes)) if changes else .10))
        params[role] = dict(center=float(np.mean(means)),variance=max(.25,float(np.var(means))),
            q=q,share=float(sum(x[2] for x in values)/sum(x[3] for x in values)),
            rows=len(values),startup=None)
    params["team_mean"] = float(np.mean([r.total for r in old])) if old else 27.
    params["other_prior"] = (sum(r.total-sum(c for c,role in r.known.values() if role=="RB") for r in old)/sum(r.total for r in old)) if old else .4
    params["training_before_utc"] = origin.isoformat()
    params["earlier_team_games"] = len(old)
    params["maximum_parameter_source_utc"] = max((r.available.isoformat() for r in old),default=None)
    return params

@lru_cache(maxsize=4)
def _quadrature(nodes):
    return np.polynomial.hermite.hermgauss(nodes)

def logistic_moments(mean, variance, nodes=41):
    x,w = _quadrature(nodes)
    p = expit(mean+np.sqrt(2*variance)*x)
    mu = float(w@p/np.sqrt(np.pi))
    var = max(0.,float(w@(p*p)/np.sqrt(np.pi))-mu*mu)
    return mu,var

def checked_moments(mean,variance):
    previous=logistic_moments(mean,variance,41)
    for nodes in (81,161,321):
        current=logistic_moments(mean,variance,nodes)
        error=max(abs(current[0]-previous[0]),abs(current[1]-previous[1]))
        if error<=1e-6:return (*current,nodes,error)
        previous=current
    raise ValueError('actual-state deterministic quadrature convergence')

def predict_state(state, parameters, index):
    p = parameters
    if state is None:
        return p["center"],p["variance"],0,None,0.
    mean,var,last,n,clock,innovation = state
    dt = max(1,index-last)
    decay = RHO**dt
    var = decay**2*var+p["q"]*(1-decay**2)/(1-RHO**2)
    return p["center"]+decay*(mean-p["center"]),var,n,clock,innovation

def augment(frame, records):
    """Forward filter, batched by team/year/cutoff; no backward smoothing."""
    q = frame.copy().reset_index(drop=True)
    if q.duplicated(["game_id","player_id"]).any(): raise ValueError("duplicate queries")
    limits = pd.to_datetime(q.cutoff_utc,utc=True,errors="raise")
    kick = pd.to_datetime(q.kickoff_utc,utc=True,errors="raise")
    if limits.isna().any() or (limits>kick).any(): raise ValueError("query deadline")
    q["cutoff_utc"] = limits
    values = np.full((len(q),len(FEATURES)),np.nan)
    aux = [None]*len(q); params = {int(y):annual_parameters(records,int(y)) for y in q.season.unique()}
    by_team = {}
    for r in records: by_team.setdefault(r.team,[]).append(r)
    for (year,team), indices in q.groupby(["season","team"],sort=False).groups.items():
        par = params[int(year)]; old = by_team.get(str(team),[])
        states = {}; recent = {}; admitted=[]; cursor=0
        block = q.loc[indices]
        for cutoff, ix in block.groupby("cutoff_utc",sort=True).groups.items():
            while cursor<len(old) and old[cursor].available<cutoff:
                r = old[cursor]
                if r.kickoff>=cutoff: raise ValueError("future game in filter")
                index=len(admitted)
                for player,(c,role) in r.known.items():
                    if role not in par: continue
                    pp=par[role]; m,v,n,clock,innovation=predict_state(states.get(player),pp,index)
                    z=math.log((c+.5)/(r.total-c+.5));obsvar=1/(c+.5)+1/(r.total-c+.5)
                    gain=v/(v+obsvar)
                    states[player]=(m+gain*(z-m),(1-gain)*v,index,n+1,r.kickoff,float(z-m))
                    recent.setdefault(player,[]).append((index,c,r.total))
                admitted.append(r); cursor+=1
            if admitted and admitted[-1].available>=cutoff: raise ValueError("filter cutoff")
            last=admitted[-8:]; weights=np.array([2**(-(len(admitted)-1-j)/8) for j in range(len(admitted)-len(last),len(admitted))])
            totals=np.array([r.total for r in last],float)
            shape=2*par["team_mean"]+float(weights@totals);rate=2+float(weights.sum())
            team_mu=shape/rate;team_var=team_mu*(1+1/rate)
            snapshots={}
            for pos in ix:
                row=q.loc[pos];player=str(row.player_id);pp=par[str(row.position)]
                m,v,n,clock,innovation=predict_state(states.get(player),pp,len(admitted))
                mu,var,nodes,error=checked_moments(m,v)
                diag=par.setdefault('numerical_observed',{'maximum_nodes':0,'maximum_successive_error':0.,'state_rows':0,'maximum_logit_variance':0.})
                diag['maximum_nodes']=max(diag['maximum_nodes'],nodes);diag['maximum_successive_error']=max(diag['maximum_successive_error'],error);diag['state_rows']+=1;diag['maximum_logit_variance']=max(diag['maximum_logit_variance'],v)
                rr=recent.get(player,[])[-8:];w=np.array([2**(-(len(admitted)-1-r[0])/3) for r in rr])
                alpha=20*pp["share"]+sum(a*r[1] for a,r in zip(w,rr));beta=20*(1-pp["share"])+sum(a*(r[2]-r[1])for a,r in zip(w,rr))
                recmu=alpha/(alpha+beta);recvar=recmu*(1-recmu)/(alpha+beta+1)
                snapshots[pos]=(mu,var,v,n,(cutoff-clock).total_seconds()/86400 if clock is not None else np.nan,innovation,recmu,recvar)
            rb=[pos for pos in ix if q.loc[pos,"position"]=="RB" and
                ("pregame_roster_qualified" not in q or q.loc[pos,"pregame_roster_qualified"])]
            rbids={str(q.loc[pos,"player_id"]) for pos in rb}
            # Residual includes QB/non-RB, unlisted players and unresolved credits.
            # It is an explicit bucket, never silently redistributed to an RB.
            other=2*par["team_mean"]*par["other_prior"]+sum(w*(r.total-sum(c for p,(c,role) in r.known.items() if p in rbids))for w,r in zip(weights,last))
            other_share=max(1e-9,other/shape)
            peer_sum=sum(snapshots[pos][0] for pos in rb)
            for pos in ix:
                mu,var,v,n,days,innovation,recmu,recvar=snapshots[pos]
                values[pos]=[mu,math.sqrt(var),v,n,days,innovation,recmu,team_mu,team_var,team_mu*mu,
                    peer_sum-(mu if pos in rb else 0),other_share]
                aux[pos]={"shape":shape,"rate":rate,"raw_share":mu,"raw_variance":var,
                    "recency_share":recmu,"recency_variance":recvar,"other_weight":other_share,
                    "source_max_utc":admitted[-1].available.isoformat() if admitted else None,
                    "earlier_team_games":len(admitted),"known_player_games":n,
                    "unresolved_credits_last8":sum(r.unresolved for r in last)}
    for i,name in enumerate(FEATURES):q[name]=values[:,i]
    q["dynamic_source_max_utc"]=[a["source_max_utc"] for a in aux]
    original=pd.to_datetime(q.feature_max_source_available_utc,utc=True,errors="coerce")
    dynamic=pd.to_datetime(q.dynamic_source_max_utc,utc=True)
    q['dynamic_parameter_source_max_utc']=[params[int(y)]['maximum_parameter_source_utc']for y in q.season]
    parameter_clock=pd.to_datetime(q.dynamic_parameter_source_max_utc,utc=True)
    q["feature_max_source_available_utc"]=pd.concat([original,dynamic,parameter_clock],axis=1).max(axis=1)
    if (q.feature_max_source_available_utc.notna()&(q.feature_max_source_available_utc>=limits)).any():raise ValueError("future source")
    return q,aux,params

def finite_allocations(frame, aux, *, recency=False):
    """Project role moments to ONE coherent Dirichlet per eligible RB board."""
    out={};checks=[]
    for (game,team),ix in frame.groupby(["game_id","team"],sort=False).groups.items():
        if frame.loc[ix,'cutoff_utc'].nunique()!=1:raise ValueError('joint allocation mixes cutoffs')
        if len({(aux[i]['shape'],aux[i]['rate'])for i in ix})!=1:raise ValueError('joint allocation mixes volume bindings')
        ids=[i for i in ix if frame.loc[i,"position"]=="RB"]
        if not ids:continue
        key="recency_share" if recency else "raw_share"
        var_key="recency_variance" if recency else "raw_variance"
        raw=np.array([aux[i][key] for i in ids]+[aux[ids[0]]["other_weight"]])
        p=raw/raw.sum();vars_=np.array([aux[i][var_key] for i in ids])/raw.sum()**2
        kappas=p[:-1]*(1-p[:-1])/np.maximum(vars_,1e-12)-1
        concentration=float(np.clip(np.median(kappas),2,200))
        if not np.isfinite(p).all() or (p<=0).any() or abs(p.sum()-1)>1e-12:raise ValueError("allocation coherence")
        for j,i in enumerate(ids):out[i]={**aux[i],"allocation_share":float(p[j]),"allocation_kappa":concentration,"other_probability":float(p[-1])}
        checks.append({"game_id":str(game),"team":str(team),"players":len(ids),"sum":float(p.sum()),"other_share":float(p[-1]),"team_mu":aux[ids[0]]["shape"]/aux[ids[0]]["rate"],"sum_player_means":float(sum(p[:-1])*aux[ids[0]]["shape"]/aux[ids[0]]["rate"])})
    return out,checks

def allocation_law(parameters):
    """Exact NB x beta-binomial summation with an explicit 1e-12 tail bound."""
    shape,rate=parameters["shape"],parameters["rate"]
    p=parameters["allocation_share"];k=parameters["allocation_kappa"]
    a,b=k*p,k*(1-p)
    maximum=int(nbinom.ppf(1-TAIL,shape,rate/(rate+1)))
    n=np.arange(maximum+1);nmass=nbinom.pmf(n,shape,rate/(rate+1))
    result=np.zeros(maximum+1)
    for total,mass in enumerate(nmass):
        y=np.arange(total+1)
        logs=gammaln(total+1)-gammaln(y+1)-gammaln(total-y+1)+betaln(y+a,total-y+b)-betaln(a,b)
        result[:total+1]+=mass*np.exp(logs)
    omitted=float(nbinom.sf(maximum,shape,rate/(rate+1)))
    if omitted>1.01*TAIL or abs(result.sum()-(1-omitted))>1e-10:raise ValueError("exact marginal numerical error")
    # Normalization changes any event by <= omitted / (1-omitted).
    result/=result.sum()
    mean=shape/rate*p
    return dict(pmf=result,mean=float(mean),median=int(np.searchsorted(np.cumsum(result),.5)),
        omitted_mass_bound=omitted,approximation="exact-sum; tail-normalized below1.01e-12")

def event_probabilities(pmf,line):
    y=np.arange(len(pmf));return dict(p_under=float(pmf[y<line].sum()),p_push=float(pmf[y==line].sum()),p_over=float(pmf[y>line].sum()))
