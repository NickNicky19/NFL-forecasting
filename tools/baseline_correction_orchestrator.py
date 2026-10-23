"""Finite corrections to cached chronological OOF points; no CDF model access."""
from contextlib import contextmanager, ExitStack
import hashlib
import json
from pathlib import Path
import resource
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from direct_booster_frozen_report import cap_output, relative
from direct_xgboost_binary_recovery import process_free_threads
from nfl_lab import baseline_correction as correction
from nfl_lab import direct_booster_screen as parent, source_matched_benchmark as shared
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.owned_reference_batch import validate_owned_references
from nfl_lab.reference_runtime import _deadline
from nfl_lab.source_matched_reporting import CONTEXT as ORIGINAL_CONTEXT

VERSION='baseline-correction-v1-20261023'
POLICY_SHA256='0e94af3599fb525e933989c6adaa29385f4da6ef13f6cba5258f47d205aea03a'
CONTEXT=tuple(dict.fromkeys(shared.cdf.KEYS+list(ORIGINAL_CONTEXT)))
BASE_FORECAST=('target','method','primary_role','point','mean','median','probability','fallback','history_state')
LABELS=('actual','participation_state','outcome_state')
LIMIT=50331648


def slots(categories):
    return [dict(year=year,target=target,method=method,state='BLOCKED_EXACT_PPR' if categories[target]['state']!='READY' else 'UNRUN')
        for year in shared.YEARS for target in shared.models.TARGETS for method in correction.METHODS]


class Sequence:
    def __init__(self,categories,*,expected_rows=569184):
        self.planned=[s for s in slots(categories) if s['state']!='BLOCKED_EXACT_PPR']
        self.frozen=[];self.rows=0;self.fits=0;self.fit_slots=set();self.reserved=None;self.global_frozen=False;self.expected_rows=expected_rows
    def before(self,slot):
        identity=lambda s:tuple(s[k] for k in ('year','target','method'))
        if len(self.frozen)>=len(self.planned) or identity(slot)!=identity(self.planned[len(self.frozen)]):
            raise ValueError('exact year/target/arm sequence required')
    def reserve(self,slot,rows):
        self.before(slot)
        if self.reserved is not None or type(rows) is not int or rows<=0 or self.rows+rows>600000:
            raise ValueError('forecast row budget exhausted before inference')
        self.reserved=(slot['year'],slot['target'],slot['method'],rows);self.rows+=rows
    def consume_fit(self,slot):
        self.before(slot)
        identity=tuple(slot[k] for k in ('year','target','method'))
        if slot['year']==2022 or self.fits>=44 or self.reserved is None or identity in self.fit_slots:
            raise ValueError('unregistered/repeated correction fit')
        self.fit_slots.add(identity);self.fits+=1
        return self.fits
    def freeze(self,slot,rows):
        self.before(slot)
        if self.reserved!=(slot['year'],slot['target'],slot['method'],rows):raise ValueError('forecast rows uncharged')
        self.frozen.append(dict(slot));self.reserved=None
    def year_frozen(self,year):
        return sum(s['year']==year for s in self.frozen)==sum(s['year']==year for s in self.planned)
    def before_labels(self,year,*,scoring=False):
        if scoring:
            if not self.global_frozen:raise ValueError('scoring labels forbidden before global freeze')
        elif year not in (2022,2023) or not self.year_frozen(year):
            raise ValueError('earlier OOF labels forbidden before all same-year forecasts freeze')
    def global_freeze(self):
        if len(self.frozen)!=66 or self.rows!=self.expected_rows or self.fits!=44 or self.reserved is not None:
            raise ValueError('all66 forecasts/all44 consumed fits/exact rows required')
        self.global_frozen=True


def storage(spec):
    store=OperationalStorage(spec['cache'],json.loads(shared._spec(spec['source_policy']).read_text()))
    output=store.register_root(spec['output']);cap_output(store,output)
    original=store.write_bytes;retained=store.report_retention
    def bounded(path,body,*,replace=False):
        digest=hashlib.sha256(body).hexdigest()
        incoming=0 if (store.blob_root/digest).exists() else len(body)
        if retained()['charged_bytes']+incoming>LIMIT:raise RuntimeError('48MiB correction retention exhausted before write')
        return original(path,body,replace=replace)
    store.write_bytes=bounded
    def report():
        value=dict(retained());value['borrowed_helper_limit_bytes']=value['limit_bytes'];value['limit_bytes']=LIMIT
        return value
    store.report_retention=report
    return store,output


class Session:
    write=shared.Session.write;frame=shared.Session.frame;failure=shared.Session.failure
    def __init__(self,spec):
        self.spec=spec;self.storage,self.output=storage(spec);self.bindings={}
        self.start=time.monotonic();self.cpu_start=time.process_time()
    def check(self):
        if (time.monotonic()-self.start>=590 or time.process_time()-self.cpu_start>=590
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>=1073741824):
            raise RuntimeError('correction cumulative inner resource budget exhausted')
    def usage(self,sequence):
        return dict(wall_seconds=time.monotonic()-self.start,CPU_seconds=time.process_time()-self.cpu_start,
            correction_fit_attempts=sequence.fits,forecast_row_incidences=sequence.rows,
            forecast_files=len(sequence.frozen),CDF_refits_model_loads_law_calls_HTTP=0)


@contextmanager
def only_corrections():
    def forbidden(*a,**k):raise AssertionError('correction cannot fit/load/query another model or original source')
    with shared.no_fits(),ExitStack() as guards:
        import joblib,pickle
        blocked=((parent,'run_screen'),(parent,'report_screen'),(parent.direct.DirectBoosterModel,'fit'),
            (parent.direct.DirectBoosterModel,'predict'),(parent.direct,'prediction_rows'),
            (shared,'fold'),(shared,'read_partition'),(shared,'_dataset'),(shared,'_outcomes'),
            (shared.operational_sources,'_verify'),(shared.models,'fit_predict'),
            (shared.operational_models,'fit_operational_reference'),(shared.operational_models,'predict_operational_artifact'),
            (shared.cdf.LeafCDFModel,'fit'),(shared.cdf.LeafCDFModel,'predict_batches'),
            (shared.cdf,'prediction_rows'),(joblib,'load'),(pickle,'load'),(pickle,'loads'))
        for owner,name in blocked:guards.enter_context(patch.object(owner,name,forbidden))
        yield


def query_frame(spec,year):
    info=spec['query_metadata'][str(year)];columns=info['projected_columns']
    if (set(LABELS)&set(columns) or any(c not in (*CONTEXT,'season_type','feature_max_source_available_utc') and not c.startswith('f_') for c in columns)):
        raise ValueError('query projection includes unregistered labels/metadata')
    frame=pd.read_parquet(spec['queries'][str(year)]['path'],columns=columns)
    if len(frame)!=info['rows'] or not frame.columns.is_unique or not frame.season.eq(year).all():raise ValueError('query dimensions/year changed')
    if frame[list(shared.cdf.KEYS)].isna().any(axis=None) or frame.duplicated(shared.cdf.KEYS).any():raise ValueError('query identity missing/duplicate')
    cutoff=pd.to_datetime(frame.cutoff_utc,utc=True,errors='raise');kickoff=pd.to_datetime(frame.kickoff_utc,utc=True,errors='raise')
    source=pd.to_datetime(frame.feature_max_source_available_utc,utc=True,errors='coerce')
    if (cutoff.isna().any() or kickoff.isna().any() or (cutoff>kickoff).any()
            or (source.notna()&(source>=cutoff)).any()
            or (source.isna()&(shared.cdf.numeric(frame,'f_player_games_prior')>0)).any()):
        raise ValueError('original query clock contract violated')
    return frame


def exact_context(query,base,category,year):
    if (not query.columns.is_unique or not base.columns.is_unique or len(query)!=len(base)
            or any(c not in query or c not in base for c in CONTEXT)):
        raise ValueError('original nine-column context incomplete')
    pd.testing.assert_frame_equal(query[list(CONTEXT)].reset_index(drop=True),base[list(CONTEXT)].reset_index(drop=True),check_dtype=True,check_exact=True)
    presence=('season_type' in query,'season_type' in base)
    if presence[0]!=presence[1]:raise ValueError('season_type persisted on only one side')
    if presence[0]:pd.testing.assert_series_equal(query.season_type.reset_index(drop=True),base.season_type.reset_index(drop=True),check_dtype=True,check_exact=True)
    if (not base.target.eq(category['target']).all() or not base.method.eq('leaf_cdf').all()
            or not base.season.eq(year).all() or not base.primary_role.equals(base.position.isin(category['primary_roles']))):
        raise ValueError('original CDF category/role/year changed')
    return dict(columns=list(CONTEXT),exact_order_context_dtypes=True,
        season_type='PRESENT_BOTH_EXACT' if presence[0] else 'ABSENT_BOTH_FROZEN_LEGACY_PROJECTIONS',invented_season_type_values=False)


def baseline_projection(spec,query,category,year,*,with_labels=False):
    metadata=spec['control_metadata'][str(year)][category['target']]['leaf_cdf']
    columns=list(metadata['forecast_columns'])
    if with_labels:columns+=metadata['label_columns']
    elif set(columns)&set(LABELS):raise ValueError('current-year baseline projection contains labels')
    base=pd.read_parquet(metadata['binding']['path'],columns=list(dict.fromkeys(columns)))
    receipt=exact_context(query,base,category,year)
    support=category['support'];field='mean' if support=='count' else 'median' if support=='signed_integer' else 'probability'
    values=shared.cdf.numeric(base,field)
    if support=='bernoulli' and not np.allclose(values,shared.cdf.numeric(base,'point'),rtol=0,atol=0,equal_nan=True):
        raise ValueError('saved CDF event probability does not match its recorded point')
    return base,values,dict(receipt,baseline_column=field,labels_semantically_read=with_labels)


def labels_from(query,donor,category):
    if not donor.participation_state.isin(['played','DNP','unknown']).all():raise ValueError('original participation state changed')
    result=query.copy();result[category['target']]=donor.actual.to_numpy()
    result['participation_state']=donor.participation_state.to_numpy();result['qualified_outcome_state']=donor.outcome_state.to_numpy()
    for c in donor:
        if c.startswith('qualified_') or c in shared.QUALIFICATION:result[c]=donor[c].to_numpy()
    return result


def training_frame(spec,queries,category,query_year,sequence):
    frames=[];bases=[];audit=[]
    earliest=pd.to_datetime(queries[query_year].cutoff_utc,utc=True).min()
    for year in range(2022,query_year):
        sequence.before_labels(year)
        donor,base,context=baseline_projection(spec,queries[year],category,year,with_labels=True)
        offered=labels_from(queries[year],donor,category)
        available=pd.to_datetime(offered.kickoff_utc,utc=True)+pd.Timedelta(days=7)
        keep=available.lt(earliest)
        frames.append(offered.loc[keep]);bases.append(base[keep.to_numpy()])
        audit.append(dict(year=year,offered_rows=len(offered),chronology_retained_rows=int(keep.sum()),
            chronology_excluded_rows=int((~keep).sum()),earliest_query_cutoff=earliest.isoformat(),
            availability='reconstructed earlier kickoff+7days strictly before earliest query cutoff',context=context))
    return pd.concat(frames,ignore_index=True),np.concatenate(bases),audit


def forecast_rows(query,baseline,base,category,method,*,model=None,failure=None,startup=False):
    if startup or failure:
        points=np.where(correction.baseline_support(base,category['support']),base,np.nan)
        reasons=np.full(len(query),'no_earlier_oof' if startup else 'package_failure_baseline_retained',dtype=object)
        reasons[~np.isfinite(points)]='invalid_or_missing_baseline_abstain'
    else:points,reasons=model.predict(query,base)
    fields=[c for c in (*CONTEXT,'season_type') if c in query]
    rows=query[fields].copy();rows['target']=category['target'];rows['method']=method
    rows['point']=points;rows['probability']=points if category['support']=='bernoulli' else np.nan
    rows['primary_role']=rows.position.isin(category['primary_roles']);rows['fallback']=reasons
    rows['baseline_fallback']=baseline.fallback.to_numpy();rows['history_state']=baseline.history_state.to_numpy()
    rows['baseline_point']=base;rows['baseline_source_field']='mean' if category['support']=='count' else 'median' if category['support']=='signed_integer' else 'probability'
    rows['evidence']='exposed_current_vintage_chronological_OOF_correction_reconstruction'
    rows['conditional_on']='played';rows['point_semantics']=parent.direct.product(category['support'])[0]
    rows['distribution']='bernoulli' if category['support']=='bernoulli' else 'none_correction_point_only'
    rows['actual']=np.nan;rows['participation_state']='unread';rows['outcome_state']='unread'
    # Numeric-law values from the baseline must never travel with a changed point.
    for name in ('mean','median',*shared.LAW_FIELDS):rows[name]=np.nan
    return shared.normalized(rows,category,method)


def metadata(spec):
    names=('parent_science_registration','parent_forecast_freeze','control_scored_freeze','category_contract')
    values={name:json.loads(shared._spec(spec[name]).read_text()) for name in names}
    parent_config=values['parent_science_registration'];forecast=values['parent_forecast_freeze'];controls=values['control_scored_freeze']
    categories=values['category_contract']['categories']
    if set(categories)!=set(shared.models.TARGETS) or categories['fantasy_ppr']['state']=='READY' or any(categories[t]['state']!='READY' for t in shared.models.TARGETS if t!='fantasy_ppr'):
        raise ValueError('all12 with exactly11 ready targets required')
    if forecast['state']!='GLOBAL_FORECASTS_FROZEN' or forecast['fatal'] is not None:raise ValueError('original frozen source query inventory required')
    for key in ('cache','control_root','source_policy','category_contract','control_scored_freeze'):
        if spec[key]!=parent_config[key]:raise ValueError('unchanged source/control contract required:'+key)
    owned={spec[k]['path']:spec[k]['sha256'] for k in ('parent_forecast_freeze','control_scored_freeze')}
    for year in shared.YEARS:
        query=spec['queries'][str(year)];name=f'private/queries/{year}.parquet'
        if forecast['bindings'].get(name)!=query['sha256']:raise ValueError('original query binding changed')
        owned[query['path']]=query['sha256']
        for target in shared.models.TARGETS:
            if target=='fantasy_ppr':continue
            for method in parent.CONTROLS:
                meta=spec['control_metadata'][str(year)][target][method];binding=meta['binding']
                name=f'private/scored/{year}/{target}/{method}/rows.parquet'
                if (name not in controls['scored_files'] or controls['bindings'].get(name)!=binding['sha256']
                        or binding['path']!=str(relative(Path(spec['control_root']),name))):raise ValueError('exact165 source-matched controls required')
                owned[binding['path']]=binding['sha256']
    return values,owned


def later_descriptive_pairs(rows,controls,category):
    result=[]
    for method,part in rows.loc[rows.season.isin([2023,2024])].groupby('method',sort=False):
        for primary in (False,True):
            for comparator in parent.CONTROLS:
                baseline=controls.loc[controls.method.eq(comparator)&controls.season.isin([2023,2024])]
                report,_=parent.product_pairs(part,baseline,category,role_subset=primary)
                report.update(candidate=method,comparator=comparator,period='descriptive_2023_2024',
                    population='primary_roles' if primary else 'all_offered',
                    uncertainty='N/A: additional descriptive slice, no new interval or confirmation claim')
                result.append(report)
    return result


def fit_package(session,sequence,slot,train,train_base,query,baseline,base,category):
    attempt=sequence.consume_fit(slot);stem=f"private/packages/{slot['year']}/{slot['target']}/{slot['method']}"
    session.write(stem+'/CONSUMED.json',dict(attempt=attempt,slot=slot,at=shared.now(),per_fit_wall_CPU_seconds=20))
    class GuardBudget:limits=dict(per_estimator_wall_seconds=20,per_estimator_CPU_seconds=20)
    session.budget=GuardBudget()
    model=None;failure=None;start=time.monotonic();cpu=time.process_time()
    try:
        with shared.estimator_cpu_guard(session,attempt),shared.cpu_deadline(18),_deadline(18):
            model=correction.BaselineCorrection.fit(train,train_base,category,slot['method'],query_year=slot['year'])
        session.check()
        rows=forecast_rows(query,baseline,base,category,slot['method'],model=model)
    except (shared.StorageQuotaError,shared.StorageIntegrityError):raise
    except Exception as error:
        failure=dict(exception=type(error).__name__,message=str(error)[:500],entire_package_baseline_fallback=True)
        rows=forecast_rows(query,baseline,base,category,slot['method'],failure=failure)
    session.write(stem+'/parameters.json',dict(state='FAILED_BASELINE_RETAINED' if failure else 'FITTED',
        consumed_attempt=attempt,wall_seconds=time.monotonic()-start,CPU_seconds=time.process_time()-cpu,
        fitted_model=model.manifest() if model is not None else None,prediction_failure=failure,
        core_version=correction.VERSION,baseline='frozen genuine earlier CDF OOF appropriate point; no base fit/model load'))
    return rows,failure


def run(spec,*,plan_sha256,final_static):
    if plan_sha256!=POLICY_SHA256 or spec['registration_id']!=VERSION:raise ValueError('exact registered correction study required')
    session=Session(spec);sequence=None;state='FAILED'
    if (session.output/'CORRECTION_CONSUMED.json').exists():raise RuntimeError('sole correction invocation consumed')
    session.write('CORRECTION_CONSUMED.json',dict(registration_sha256=plan_sha256,at=shared.now()))
    try:
        with _deadline(590),process_free_threads(spec['loaded_libc']),threadpool_limits(limits=2),only_corrections():
            values,owned=metadata(spec);categories=values['category_contract']['categories']
            sequence=Sequence(categories);session.control_freeze=values['control_scored_freeze']
            session.authenticated_controls,entry=validate_owned_references(session.storage,owned);session.write('owned-input-entry.json',entry)
            session.write('planned-slots.json',slots(categories));queries={};frozen=[];scored=[]
            for year in shared.YEARS:
                session.check();queries[year]=query_frame(spec,year)
                for target in shared.models.TARGETS:
                    category=shared._category(categories,target)
                    if category['state']!='READY':continue
                    baseline,base,context=baseline_projection(spec,queries[year],category,year)
                    session.write(f'context/{year}/{target}.json',context)
                    if year>2022:
                        train,train_base,training_audit=training_frame(spec,queries,category,year,sequence)
                        session.write(f'training/{year}/{target}.json',training_audit)
                    for method in correction.METHODS:
                        slot=dict(year=year,target=target,method=method);sequence.reserve(slot,len(queries[year]));failure=None
                        if year==2022:rows=forecast_rows(queries[year],baseline,base,category,method,startup=True)
                        else:rows,failure=fit_package(session,sequence,slot,train,train_base,queries[year],baseline,base,category)
                        name=f'private/forecasts/{year}/{target}/{method}.parquet';session.frame(name,rows)
                        sequence.freeze(slot,len(rows));frozen.append(dict(slot,forecast=name,rows=len(rows),
                            state='STARTUP_ALIAS' if year==2022 else 'FAILED_BASELINE_RETAINED' if failure else 'PREDICTION_FROZEN'))
                        session.check()
                    if year>2022:del train,train_base
                session.write(f'year-freezes/{year}.json',dict(state='ALL_YEAR_FORECASTS_FROZEN',year=year,
                    slots=[s for s in frozen if s['year']==year],bindings=dict(session.bindings),usage=session.usage(sequence)))
            sequence.global_freeze()
            session.write('forecast-freeze.json',dict(state='GLOBAL_66_FORECASTS_FROZEN',slots=frozen,
                bindings=dict(session.bindings),usage=session.usage(sequence),scoring_labels_or_candidate_losses_read=False,
                earlier_OOF_labels='2022/23 allowed only for later-year training after all own-year forecasts frozen'))
            for year in shared.YEARS:
                sequence.before_labels(year,scoring=True)
                for target in shared.models.TARGETS:
                    category=shared._category(categories,target)
                    if category['state']!='READY':continue
                    donor,_,_=baseline_projection(spec,queries[year],category,year,with_labels=True)
                    offered=labels_from(queries[year],donor,category)
                    for slot in [s for s in frozen if s['year']==year and s['target']==target]:
                        rows=pd.read_parquet(session.output/slot['forecast'])
                        result=parent.direct.score_frozen_rows(offered,rows,category)
                        name=f"private/scored/{year}/{target}/{slot['method']}.parquet"
                        session.frame(name,shared.normalized(result,category,slot['method']));scored.append(dict(slot,scored=name))
                    session.check()
            session.write('scored-freeze.json',dict(state='ALL66_SCORED_ROWS_FROZEN',slots=scored,bindings=dict(session.bindings)))
            reports=[]
            for target in shared.models.TARGETS:
                session.check();category=shared._category(categories,target)
                if category['state']!='READY':
                    reports.append(dict(target=target,state='BLOCKED_EXACT_PPR',rows=0,scientific_qualification=False));continue
                rows=pd.concat([pd.read_parquet(session.output/s['scored']) for s in scored if s['target']==target],ignore_index=True)
                controls=pd.concat([parent._control(session,year,target,method,category) for year in shared.YEARS for method in parent.CONTROLS],ignore_index=True)
                report,pairs=parent.target_report(rows,controls,category,session.check)
                report['later_2023_2024_descriptive_pairs']=later_descriptive_pairs(rows,controls,category)
                session.frame(f'private/paired-losses/{target}.parquet',pairs)
                session.frame(f'private/subgroups/{target}.parquet',parent.subgroup_rows(rows,category))
                session.write(f'target-reports/{target}.json',report);reports.append(report)
                del rows,controls,pairs
            final_static();metadata(spec)
            owned.update({str(session.output/name):digest for name,digest in session.bindings.items()})
            _,exit_receipt=validate_owned_references(session.storage,owned);session.write('owned-input-exit.json',exit_receipt)
            session.check();session.write('report.json',dict(version=VERSION,at=shared.now(),targets=reports,
                methods=list(correction.METHODS),blocked_exact_PPR_slots=6,usage=session.usage(sequence),retention=session.storage.report_retention(),
                evidence='EXPOSED_CHRONOLOGICAL_OOF_DEVELOPMENT_RECONSTRUCTION; not SITE/Sleeper or independent confirmation',
                startup='all22 original2022 CDF point aliases retained in whole-policy primary',
                missing_comparators='authentic historical raw Sleeper/SITE unavailable; N/A',
                scientific_qualification=False,release_ready=False,website_default_changed=False),freeze=False)
            state='COMPLETED'
    except BaseException as error:session.failure('CORRECTION_FAILURE.json',error);raise
    finally:
        session.write('CORRECTION_FINISHED.json',dict(state=state,usage=session.usage(sequence) if sequence else None,
            retention=session.storage.report_retention()),freeze=False)
