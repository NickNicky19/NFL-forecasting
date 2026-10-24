"""Thin fixed18 operational orchestration; shared numeric/source APIs unchanged."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import signal
import threading
import time
from urllib.parse import urlsplit

VERSION='GENUINE_HOSTED_FIXED_BUILD_V1'
TARGETS=('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td')
CAT=('pass_yd','rush_yd','rec_yd','rush_rec_yd','anytime_td')
TRAINING_CUTOFF='2026-09-01T00:00:00Z'


class BuildStop(BaseException):pass


def jobs():
    return ([dict(target=t,method_id='LAB_CDF',family='leaf_cdf_base') for t in TARGETS]
        +[dict(target=t,method_id='COUNT_A',family='count_A') for t in ('rush_att','rec')]
        +[dict(target=t,method_id='CATBOOST_MEDIUM',family='catboost_medium') for t in CAT])


def allowed_periods():return {**{year:list(range(1,19)) for year in range(2019,2026)},2026:[1,2,3,4,5]}


class SourceBudget:
    """Wrap only transport admission; the downloader/retries/body contract stays original."""
    CDN=frozenset({'release-assets.githubusercontent.com','objects.githubusercontent.com','github-releases.githubusercontent.com'})
    def __init__(self,urls,*,record,clock=time.monotonic):
        if len(urls)!=19 or len(set(urls.values()))!=19:raise ValueError('EXACT19SOURCE_URLS')
        self.urls={v:k for k,v in urls.items()};self.record=record;self.clock=clock;self.started=clock()
        self.attempts=0;self.roundtrips=0;self.phase=True;self.local=threading.local()

    def request(self,original,session,method,url,**kwargs):
        if not self.phase or method.upper()!='GET' or url not in self.urls or self.attempts>=60 or self.clock()-self.started>=300:
            raise BuildStop('SOURCE_REQUEST_SCOPE_OR_BUDGET')
        self.attempts+=1
        self.record(self.attempts,dict(source_name=self.urls[url],official_url_sha256=hashlib.sha256(url.encode()).hexdigest(),attempt_consumed=True))
        # Prevent implicit netrc lookup, while retaining inherited proxy/CA settings.
        if kwargs.get('auth') is not None:raise BuildStop('PUBLIC_SOURCE_NO_CREDENTIALS')
        kwargs['auth']=lambda request:request
        return original(session,method,url,**kwargs)

    def send(self,original,adapter,request,**kwargs):
        parsed=urlsplit(request.url)
        if (not self.phase or request.method!='GET' or parsed.scheme!='https' or parsed.username or parsed.password or parsed.port
            or parsed.fragment or '\\' in request.url or request.url not in self.urls and parsed.hostname not in self.CDN
            or request.headers.get('Authorization') or request.headers.get('Cookie') or self.roundtrips>=180 or self.clock()-self.started>=300):
            raise BuildStop('SOURCE_PREPARED_REQUEST_SCOPE')
        self.roundtrips+=1;self.local.transport=True
        try:return original(adapter,request,**kwargs)
        finally:self.local.transport=False

    @contextmanager
    def install(self,requests):
        old_request=requests.sessions.Session.request;old_send=requests.adapters.HTTPAdapter.send;budget=self
        def request(session,method,url,**kwargs):return budget.request(old_request,session,method,url,**kwargs)
        def send(adapter,prepared,**kwargs):return budget.send(old_send,adapter,prepared,**kwargs)
        requests.sessions.Session.request=request;requests.adapters.HTTPAdapter.send=send
        try:yield
        finally:
            self.phase=False;requests.sessions.Session.request=old_request;requests.adapters.HTTPAdapter.send=old_send


def training_rows(frame,schedule):
    """REG by schedule identity; only earlier2019-25 labels can train2026."""
    import pandas as pd
    from .cdf_engine import assert_clock_contract
    required={'season','game_id','game_type'}
    if not required<=set(schedule) or schedule.game_id.duplicated().any():raise ValueError('UNAMBIGUOUS_REG_SCHEDULE_REQUIRED')
    games=schedule.loc[schedule.season.between(2019,2025)&schedule.game_type.eq('REG'),'game_id']
    cutoff=pd.Timestamp(TRAINING_CUTOFF)
    result=frame.loc[frame.season.between(2019,2025)&frame.game_id.isin(games)].copy()
    available=pd.to_datetime(result.outcome_available_utc,utc=True,errors='coerce');kickoff=pd.to_datetime(result.kickoff_utc,utc=True,errors='coerce')
    result=result.loc[available.notna()&kickoff.notna()&available.lt(cutoff)&kickoff.lt(cutoff)].copy()
    if result.empty:raise ValueError('NO_EARLIER_TRAINING_ROWS')
    assert_clock_contract(result);result.attrs.clear();return result


@contextmanager
def hard_deadline(seconds):
    """Native overrun terminates this packet, never retries a fit/source phase."""
    old=signal.getitimer(signal.ITIMER_REAL);started=time.monotonic()
    if old[0]<=0 or old[1] or signal.getitimer(signal.ITIMER_PROF)!=(0.,0.):raise BuildStop('WHOLE_PACKET_TIMER_REQUIRED')
    previous_real=signal.getsignal(signal.SIGALRM);previous_prof=signal.getsignal(signal.SIGPROF)
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.signal(signal.SIGPROF,signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL,min(seconds,old[0]));signal.setitimer(signal.ITIMER_PROF,seconds)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_PROF,0);left=old[0]-(time.monotonic()-started)
        signal.signal(signal.SIGALRM,previous_real);signal.signal(signal.SIGPROF,previous_prof)
        if left<=0:raise BuildStop('WHOLE_PACKET_WALL')
        signal.setitimer(signal.ITIMER_REAL,left)


def initial_training_report():
    return dict(slots=[dict(**job,state='NOT_ATTEMPTED',logical_fit_reservation=None,estimator_gate_calls=0) for job in jobs()],
        new_logical_fits_reserved=0,new_model_bytes=0,old_model_hash_reproduction_claim=False,old_fit_budgets_reset=False,searches=0,scores=0)


def train18(train,categories,*,future,storage,output,source_contract,source_bindings,source_completed_at,check,deadline=hard_deadline,maximum_model_bytes=12<<20,progress=lambda row:None,report=None):
    from .operational_storage import StorageQuotaError, StorageIntegrityError
    """One reservation/slot; actual fitter gate separate; no search/retry/scoring."""
    import pandas as pd
    output=Path(output);report=initial_training_report() if report is None else report;reserved=0;model_bytes=0
    for job,state in zip(jobs(),report['slots']):
        check();reserved+=1;report['new_logical_fits_reserved']=reserved
        state.update(logical_fit_reservation=reserved,state='FIT_RESERVED_NEW_OPERATIONAL_BUILD',estimator_gate_calls=0)
        storage.atomic_json(output/f'fit-reservations/{reserved:02}.json',dict(state,actual_reserved_at=future.now_utc().isoformat()))
        progress(dict(event='NEW_OPERATIONAL_FIT_RESERVED',reservation=reserved,target=job['target'],family=job['family']))
        def gate(info):
            if state['estimator_gate_calls']:raise BuildStop('ONE_ESTIMATOR_GATE_PER_LOGICAL_FIT')
            state['estimator_gate_calls']=1
            storage.atomic_json(output/f'estimator-attempts/{reserved:02}.json',dict(detail=info,actual_call_gate_at=future.now_utc().isoformat()))
        try:
            with deadline(60):
                model=future.fit_future_model(train,categories[job['target']],job['family'],training_cutoff_utc=TRAINING_CUTOFF,
                    fit_gate=gate,training_source_capture_completed_at=source_completed_at,
                    expected_native_version='1.2.10' if job['family']=='catboost_medium' else None)
            check();category=categories[job['target']]
            fixture=pd.concat([train.head(2),train.loc[train.position.isin(category['modeled_roles'])&train.f_player_games_prior.gt(0)].tail(2)]).drop_duplicates(future.cdf.KEYS)
            ref=future.export_trained_artifact(output/'models'/job['target']/job['family'],model,family=job['family'],method_id=job['method_id'],
                training_frame=train,training_cutoff_utc=TRAINING_CUTOFF,source_contract=source_contract,training_sources=source_bindings,
                replay_fixture=fixture,storage=storage,maximum_serialized_bytes=maximum_model_bytes-model_bytes)
            manifest=json.loads(Path(ref['path']).read_text());model_bytes+=manifest['model']['bytes']+ref['bytes']
            if model_bytes>maximum_model_bytes:raise BuildStop('MODEL_BYTES_CAP')
            state.update(state='NEW_OPERATIONAL_ARTIFACT_EXPORTED',artifact=ref,fit_receipt=manifest['fit_receipt'],model_bytes=manifest['model']['bytes'])
            report['new_model_bytes']=model_bytes
            del model
        except (MemoryError, StorageQuotaError, StorageIntegrityError) as error:
            state.update(state='GLOBAL_RESOURCE_OR_STORAGE_STOP_RETAINED',error_type=type(error).__name__)
            raise BuildStop('GLOBAL_RESOURCE_OR_STORAGE_STOP') from None
        except Exception as error:
            state.update(state='FAILED_FIT_RETAINED_NO_RETRY',error_type=type(error).__name__)
        storage.atomic_json(output/f"slots/{job['target']}-{job['family']}.json",state)
    return report
