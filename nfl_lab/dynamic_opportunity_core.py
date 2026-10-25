"""Deterministic conditional-share arithmetic; no sources, fitted learners or I/O.

Caller-owned source/identity/window assertions are required, never authenticated
here. No participation probabilities, numeric forecast laws or joint player
allocation are created. Missing team-game slots propagate without zero updates.
"""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
import json
import math

VERSION='dynamic-opportunity-core-v1-20261023'
TASK_ROLES={'rush_att':('RB',),'rec_tgt':('RB','WR','TE')}
SETTINGS={
    'smooth-H2-k25':('smooth',2,25,0.),
    'smooth-H2-k100':('smooth',2,100,0.),
    'smooth-H8-k25':('smooth',8,25,0.),
    'smooth-H8-k100':('smooth',8,100,0.),
    'changepoint-H8-k100-q1of16':('changepoint',8,100,1/16),
    'changepoint-H8-k100-q1of4':('changepoint',8,100,1/4),
}


def _time(value):
    if not isinstance(value,str):raise ValueError('explicit timezone-aware ISO clock required')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:raise ValueError('naive clock forbidden')
    return result.astimezone(timezone.utc)


def _text(value):return isinstance(value,str) and bool(value.strip())


def _count(value):
    if type(value) not in (int,float):return False
    try:return math.isfinite(value) and value>=0 and value==math.floor(value)
    except (ValueError,OverflowError):return False


def _exact(value,fields):
    if not isinstance(value,dict) or set(value)!=set(fields):raise ValueError('exact versioned JSON fields required')


def encode_json(value):
    """Pure strict serialization; callers own every storage/publication decision."""
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def decode_json(value):
    def invalid(token):raise ValueError('nonfinite JSON constant forbidden: '+token)
    def pairs(items):
        result={}
        for key,item in items:
            if key in result:raise ValueError('duplicate JSON field forbidden: '+key)
            result[key]=item
        return result
    return json.loads(value,parse_constant=invalid,object_pairs_hook=pairs)


@dataclass(frozen=True)
class Slot:
    player_id:str
    team:str
    season:int
    spell_id:str
    task:str
    role:str
    game_id:str
    kickoff_utc:str
    available_utc:str|None
    participation_state:str
    source_qualified:bool
    player_count:int|float|None
    team_count:int|float|None

    def manifest(self):return asdict(self)

    @classmethod
    def from_manifest(cls,value):
        _exact(value,cls.__dataclass_fields__)
        return cls(**value)


@dataclass(frozen=True)
class Query:
    player_id:str
    team:str
    season:int
    spell_id:str
    task:str
    role:str
    game_id:str
    kickoff_utc:str
    cutoff_utc:str
    selected_slots_complete:bool
    window_origin:str

    def manifest(self):return asdict(self)

    @classmethod
    def from_manifest(cls,value):
        _exact(value,cls.__dataclass_fields__)
        return cls(**value)


@dataclass(frozen=True)
class Prior:
    task:str
    role:str
    query_season:int
    training_before_utc:str
    state:str
    reason:str
    share:float|None
    total_player_count:int
    total_repeated_team_exposure:int
    training_rows:int
    supported_rows:int
    unique_supported_team_games:int

    def manifest(self):return dict(schema_version='dynamic-opportunity-prior-v1',version=VERSION,**asdict(self))

    @classmethod
    def from_manifest(cls,value):
        fields={'schema_version','version',*cls.__dataclass_fields__};_exact(value,fields)
        if value['schema_version']!='dynamic-opportunity-prior-v1' or value['version']!=VERSION:
            raise ValueError('prior version changed')
        result=cls(**{k:value[k] for k in cls.__dataclass_fields__})
        if result.state not in ('READY','FALLBACK_REQUIRED') or not _text(result.reason):raise ValueError('prior state/reason invalid')
        expected_reason='interior_training_only_individual_role_prior' if result.state=='READY' else 'missing_or_boundary_prior_baseline_fallback'
        if result.reason!=expected_reason:raise ValueError('prior reason changed')
        _time(result.training_before_utc)
        for name in ('query_season','total_player_count','total_repeated_team_exposure','training_rows','supported_rows','unique_supported_team_games'):
            if type(getattr(result,name)) is not int or getattr(result,name)<0:raise ValueError('prior integer audit invalid')
        if result.task not in TASK_ROLES or result.role not in TASK_ROLES[result.task]:raise ValueError('prior task/role invalid')
        if (result.supported_rows>result.training_rows or result.unique_supported_team_games>result.supported_rows
                or result.total_player_count>result.total_repeated_team_exposure
                or result.supported_rows==0 and (result.total_player_count or result.total_repeated_team_exposure or result.unique_supported_team_games)
                or result.supported_rows>0 and result.unique_supported_team_games==0):
            raise ValueError('prior row accounting invalid')
        if result.state=='READY':
            if (type(result.share) not in (int,float) or not math.isfinite(result.share) or not 0<result.share<1
                    or result.total_repeated_team_exposure<=0 or not 0<result.total_player_count<result.total_repeated_team_exposure
                    or result.share!=result.total_player_count/result.total_repeated_team_exposure):
                raise ValueError('prior sufficient counts/share invalid')
        elif result.share is not None or (result.total_repeated_team_exposure>0 and 0<result.total_player_count<result.total_repeated_team_exposure):
            raise ValueError('fallback prior cannot invent or hide an interior share')
        return result


def paired_count(slot):
    """Return (valid observation, reason, C, T); invalid pairs never get clipped."""
    if slot.participation_state not in ('played','DNP','unknown') or type(slot.source_qualified) is not bool:
        return False,'invalid_participation_contract',None,None
    if slot.participation_state=='DNP':return False,('confirmed_DNP_no_observation' if slot.source_qualified else 'unqualified_DNP_no_observation'),None,None
    if slot.participation_state=='unknown':return False,'unknown_participation_no_observation',None,None
    if not slot.source_qualified:return False,'unqualified_source_no_observation',None,None
    if slot.player_count is None:return False,'missing_player_count_no_observation',None,None
    if slot.team_count is None:return False,'missing_team_count_no_observation',None,None
    if not _count(slot.player_count) or not _count(slot.team_count):return False,'invalid_count_support',None,None
    c,t=int(slot.player_count),int(slot.team_count)
    if c>t:return False,'player_exceeds_team_count',None,None
    return True,'supported_zero_exposure' if t==0 else 'supported_played_zero' if c==0 else 'supported_played_positive',c,t


def form_prior(records,*,task,role,query_season,training_before_utc):
    """Earlier-season role prior from same-row individual repeated exposures.

    This function verifies caller-provided clocks/fields, not source authenticity
    or a complete participant population. No numerical optimizer is involved.
    """
    records=tuple(records);cutoff=_time(training_before_utc)
    if task not in TASK_ROLES or role not in TASK_ROLES[task] or type(query_season) is not int:raise ValueError('declared modeled task/role/season required')
    seen=set();total_c=total_t=observed=0;games=set()
    for row in records:
        if not isinstance(row,Slot):raise ValueError('typed source-qualified prior rows required')
        if type(row.season) is not int or row.season>=query_season:raise ValueError('same/later season cannot form prior')
        if (not all(_text(getattr(row,n)) for n in ('player_id','team','spell_id','game_id'))
                or row.task!=task or _time(row.kickoff_utc)>=cutoff):raise ValueError('prior task/identity/clock invalid')
        key=(row.player_id,row.game_id,row.task)
        if key in seen:raise ValueError('duplicate prior player-game inflates exposure')
        seen.add(key)
        if row.available_utc is not None and (_time(row.available_utc)>=cutoff or _time(row.available_utc)<=_time(row.kickoff_utc)):
            raise ValueError('prior availability must be after game and strictly before training cutoff')
        ok,reason,c,t=paired_count(row)
        if reason in ('invalid_participation_contract','invalid_count_support','player_exceeds_team_count'):
            raise ValueError('invalid prior row: '+reason)
        if row.role!=role:continue
        if ok:
            if row.available_utc is None:raise ValueError('observed prior row needs availability clock')
            total_c+=c;total_t+=t;observed+=1;games.add((row.game_id,row.team))
    share=total_c/total_t if total_t>0 else None
    reason='interior_training_only_individual_role_prior' if share is not None and 0<share<1 else 'missing_or_boundary_prior_baseline_fallback'
    ready=reason=='interior_training_only_individual_role_prior'
    return Prior(task,role,query_season,training_before_utc,'READY' if ready else 'FALLBACK_REQUIRED',reason,
        share if ready else None,total_c,total_t,len(records),observed,len(games))


def _logsumexp(values):
    maximum=max(values)
    return maximum+math.log(math.fsum(math.exp(x-maximum) for x in values))


def beta_binomial_logmass(c,t,alpha,beta):
    """Internal predictive likelihood only, never a published game forecast law."""
    if not _count(c) or not _count(t) or c>t or not all(math.isfinite(x) and x>0 for x in (alpha,beta)):
        raise ValueError('beta-binomial internal support invalid')
    if t==0:return 0.
    value=math.fsum([math.lgamma(t+1),-math.lgamma(c+1),-math.lgamma(t-c+1),
        math.lgamma(alpha+c),math.lgamma(beta+t-c),-math.lgamma(alpha+beta+t),
        -math.lgamma(alpha),-math.lgamma(beta),math.lgamma(alpha+beta)])
    if not math.isfinite(value):raise FloatingPointError('nonfinite internal predictive likelihood')
    return value


def _validate_query(query,history,prior):
    if not isinstance(query,Query) or not isinstance(prior,Prior):raise ValueError('typed query/prior required')
    # Re-validate even directly constructed prior objects, not only JSON imports.
    Prior.from_manifest(prior.manifest())
    if (query.task not in TASK_ROLES or query.role not in TASK_ROLES[query.task]
            or (prior.task,prior.role,prior.query_season)!=(query.task,query.role,query.season)):
        raise ValueError('prior/query task role or training season mismatch')
    if type(query.season) is not int or not all(_text(getattr(query,n)) for n in ('player_id','team','spell_id','game_id')):
        raise ValueError('query identity invalid')
    cutoff,kickoff=_time(query.cutoff_utc),_time(query.kickoff_utc)
    if cutoff>kickoff or _time(prior.training_before_utc)>cutoff:raise ValueError('query/prior cutoff invalid')
    if query.selected_slots_complete is not True or query.window_origin not in ('start_of_season_or_spell','last_eight_team_games'):
        raise ValueError('caller must declare complete latest-slot selection and boundary')
    if len(history)>8 or len(history)<8 and query.window_origin!='start_of_season_or_spell':
        raise ValueError('exact bounded/latest or genuine short window required')
    seen=set();previous=None;diagnostics=[]
    for slot in history:
        if not isinstance(slot,Slot):raise ValueError('typed prior slots required')
        if (slot.player_id,slot.team,slot.season,slot.spell_id,slot.task,slot.role)!=(query.player_id,query.team,query.season,query.spell_id,query.task,query.role):
            raise ValueError('history must reset at team/season/spell boundary')
        time=_time(slot.kickoff_utc)
        if slot.game_id==query.game_id or slot.game_id in seen or time>=cutoff or previous is not None and time<=previous:
            raise ValueError('duplicate/target/unsorted/nonprior team-game slot')
        seen.add(slot.game_id);previous=time
        ok,reason,c,t=paired_count(slot)
        if reason in ('invalid_participation_contract','invalid_count_support','player_exceeds_team_count'):
            raise ValueError('invalid paired slot: '+reason)
        if slot.available_utc is not None:
            available=_time(slot.available_utc)
            if available<=time:raise ValueError('source availability must follow its game')
            if available>=cutoff and (slot.player_count is not None or slot.team_count is not None):
                raise ValueError('post-cutoff statistic values cannot enter a query')
        if ok and (slot.available_utc is None or _time(slot.available_utc)>=cutoff):raise ValueError('observed prior slot lacks earlier availability')
        diagnostics.append(dict(game_id=slot.game_id,state=reason,participation_state=slot.participation_state,
            source_qualified=slot.source_qualified,observed=ok,c=c,t=t))
    return diagnostics


def forecast(query,prior,history,*,setting,volume,volume_supported):
    """Return an expected-count hypothesis or require unchanged CDF fallback.

    The final observation-free transition advances to the forecast team game.
    Forecasts are conditional on played, with no joint-allocation claim.
    """
    result=dict(schema_version='dynamic-opportunity-point-v1',version=VERSION,state='BASELINE_FALLBACK_REQUIRED',
        reason='',setting=setting,point=None,share=None,components=[],slots=[],numeric_distribution='NONE',
        conditional_on='played',participation_probability='UNAVAILABLE',joint_allocation=False,
        verified_injury_role_claim=False,forecast_transition='ONE_OBSERVATION_FREE_TEAM_GAME',
        window_selection_authentication='CALLER_ASSERTION_ONLY_NO_SOURCE_ADAPTER')
    try:
        if not isinstance(history,(list,tuple)):raise ValueError('explicit bounded slot list/tuple required')
        history=tuple(history)
        if setting not in SETTINGS:raise ValueError('one of six frozen settings required')
        diagnostics=_validate_query(query,history,prior);result['slots']=diagnostics
        if prior.state!='READY':result['reason']=prior.reason;return result
        if volume_supported is not True or type(volume) not in (int,float) or not math.isfinite(volume) or volume<0:
            raise ValueError('explicit supported finite nonnegative fixed volume required')
        family,half_life,kappa,hazard=SETTINGS[setting];a0=kappa*prior.share;b0=kappa*(1-prior.share)
        decay=2**(-1/half_life)
        # Components carry logweights, alpha, beta, and elapsed run length.
        components=[(0.,a0,b0,0)]
        def transition(current):
            continued=[(w+(math.log1p(-hazard) if hazard else 0.),
                a0+decay*(a-a0),b0+decay*(b-b0),length+1) for w,a,b,length in current]
            return ([(math.log(hazard)+_logsumexp([p[0] for p in current]),a0,b0,0)]+continued) if hazard else continued
        for index,diagnostic in enumerate(diagnostics):
            # At window start reset/continuation are exactly the same prior;
            # represent once, with no approximation or discarded tail mass.
            if index:components=transition(components)
            if diagnostic['observed']:
                c,t=diagnostic['c'],diagnostic['t']
                weighted=[(w+beta_binomial_logmass(c,t,a,b),a+c,b+t-c,length) for w,a,b,length in components]
                norm=_logsumexp([p[0] for p in weighted]);components=[(w-norm,a,b,length) for w,a,b,length in weighted]
        # With no history the reset/continuation prior is likewise identical.
        if diagnostics:components=transition(components)
        if len(components)>9:raise RuntimeError('bounded run-length inventory exceeded')
        norm=_logsumexp([p[0] for p in components]);components=[(w-norm,a,b,length) for w,a,b,length in components]
        share=math.fsum(math.exp(w)*(a/(a+b)) for w,a,b,_ in components);point=volume*share
        if not math.isfinite(share) or not 0<=share<=1 or not math.isfinite(point) or point<0:
            raise FloatingPointError('invalid arithmetic result requires baseline fallback')
        result.update(state='READY_POINT',reason='supported_zero_volume' if volume==0 else 'conditional_share_point_only',share=share,point=point,
            components=[dict(logweight=w,alpha=a,beta=b,elapsed_run_length=length) for w,a,b,length in components],
            half_life_team_games=half_life,kappa=kappa,hazard=hazard,
            learned_hazard_claim='development setting selected externally; not injury or playing probability')
    except (ValueError,TypeError,OverflowError,FloatingPointError,RuntimeError) as error:
        result['reason']=type(error).__name__+':'+str(error)
    return result


def request_manifest(query,prior,history,*,setting,volume,volume_supported):
    return dict(schema_version='dynamic-opportunity-request-v1',version=VERSION,query=query.manifest(),
        prior=prior.manifest(),history=[s.manifest() for s in history],setting=setting,volume=volume,volume_supported=volume_supported)


def forecast_manifest(value):
    _exact(value,('schema_version','version','query','prior','history','setting','volume','volume_supported'))
    if value['schema_version']!='dynamic-opportunity-request-v1' or value['version']!=VERSION:raise ValueError('request version changed')
    return forecast(Query.from_manifest(value['query']),Prior.from_manifest(value['prior']),
        [Slot.from_manifest(row) for row in value['history']],setting=value['setting'],volume=value['volume'],volume_supported=value['volume_supported'])
