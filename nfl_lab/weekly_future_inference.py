"""Weekly adaptive v1 future-query artifacts; legacy replay contracts stay fixed.

No acquisition or fitting occurs on import. A caller supplies quota-owned
storage and authenticated source/feature receipts. Historical query-bound
artifacts are never accepted as this new trained-inference schema.
"""
from __future__ import annotations

from io import BytesIO
from copy import copy
from importlib import metadata
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import cdf_engine as cdf
from .state import digest, now_utc, utc

VERSION = 'weekly-adaptive-release-v1-future-inference'
COUNT_A_FALLBACK_VERSION = 'count-a-prior-mean-fallback-v2-20261025'
IDENTITY = cdf.KEYS + ['team','opponent','position','kickoff_utc','cutoff_utc']
FAMILIES = ('leaf_cdf_base','count_A','catboost_medium','cdf_small_correction')
CODE_FILES = ('weekly_future_inference.py','cdf_engine.py','role_boosting.py',
              'direct_boosters.py','median_boosting.py','baseline_correction.py')
LANES = {'original_pregame','credible_asof_reconstruction','current_vintage_availability_uncertain'}


def require(value, message):
    if not value: raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as handle: return hashlib.file_digest(handle,'sha256').hexdigest()


def binding(path):
    p=Path(path).absolute()
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))


def code_pins():
    root=Path(__file__).parent
    return {name:sha(root/name) for name in CODE_FILES}


def environment():
    result={name:metadata.version(name) for name in ('numpy','pandas','scipy','scikit-learn','joblib')}
    try:result['catboost']=metadata.version('catboost')
    except metadata.PackageNotFoundError:result['catboost']=None
    return result


def model_contract(model, family):
    from .role_boosting import RoleCountBoostingModel
    from .direct_boosters import DirectBoosterModel
    from .baseline_correction import BaselineCorrection,METHODS
    correction=None
    if family=='cdf_small_correction':
        require(isinstance(model,dict) and set(model)=={'base','correction'},'base/correction pair required')
        correction=model['correction'];base=model['base']
        require(isinstance(correction,BaselineCorrection),'existing correction predictor required')
        require(correction.method in METHODS,'fixed intercept/context correction required')
        model=base
    if family in ('leaf_cdf_base','cdf_small_correction'):
        require(isinstance(model,cdf.LeafCDFModel) and model.panel=='base','base LeafCDF model required')
    elif family=='count_A':
        require(isinstance(model,RoleCountBoostingModel) and model.variant=='A'
                and model.category['support']=='count','CountA count model required')
    elif family=='catboost_medium':
        require(isinstance(model,DirectBoosterModel) and model.library=='catboost'
                and model.complexity=='medium' and model.panel=='base','fixed CatBoost medium/base required')
    else: raise ValueError('undeclared weekly family')
    category=dict(model.category);cdf.validate_category(category)
    require(category['target']!='fantasy_ppr','exact PPR remains label blocked')
    if correction is not None:require(correction.category==category,'correction/base category mismatch')
    features=list(category['panels']['base'])
    if correction is not None and correction.method=='cdf_offset_context_v1':
        features+=category['panels']['context']
    features=list(dict.fromkeys(features+['f_player_games_prior']))
    require(all(n.startswith('f_') and not cdf._FORBIDDEN.search(n)
                and n!='f_'+category['target'] for n in features),'outcome feature forbidden')
    return category,features


def query_projection(frame, features):
    require(frame.columns.is_unique,'duplicate query columns')
    names=list(dict.fromkeys(IDENTITY+['feature_max_source_available_utc']+features))
    require(set(names)<=set(frame),'query identity/source clock/feature column missing')
    # Never hash, coerce, copy or otherwise inspect target/outcome columns.
    result=frame.loc[:,names].copy()
    require(not result[cdf.KEYS].isna().any(axis=None) and not result.duplicated(cdf.KEYS).any(),
            'all offered identities must be unique and nonnull')
    return result


def frame_digest(frame):
    return hashlib.sha256(pd.util.hash_pandas_object(frame,index=False).values.tobytes()
        + json.dumps([(str(n),str(t)) for n,t in frame.dtypes.items()]).encode()).hexdigest()


def product(category):
    return {'count':('point_mean','expected_mean','MSE'),
            'signed_integer':('point_median','intended_median','MAE'),
            'bernoulli':('binary_probability','event_probability','Brier')}[category['support']]


def procedure_version(family,source_contract):
    return digest(dict(registration='weekly-adaptive-release-v1',family=family,source_contract=source_contract,
        count_fallback_version=COUNT_A_FALLBACK_VERSION if family=='count_A' else None,
        code_pins=code_pins(),category_contract_sha256='9154f113d75b8b6af3cbc21e0c407e7af4b79b29e53a288d487a2dc868473de4',
        training_rule='annual earlier seasons since2019; fixed correction earlierOOF since2022; pass_td context/pass_att intercept initially',
        fallback='existing role/global priors; all offered preserved'))


def _runtime_state(model):
    if isinstance(model,dict):return {k:_runtime_state(v) for k,v in model.items()}
    result=copy(model)
    for name in ('training_binding','prior_training_binding','training_leaf_ids'):
        if hasattr(result,name):setattr(result,name,None)
    return result


def _points(model, family, frame):
    category,_=model_contract(model,family);support=category['support']
    if family in ('leaf_cdf_base','cdf_small_correction'):
        base=model['base'] if family=='cdf_small_correction' else model
        points=np.full(len(frame),np.nan);reasons=np.full(len(frame),'no_supported_training_outcomes',dtype=object)
        for indices,law,fallback in base.predict_batches(frame,batch_size=256):
            reasons[indices]=fallback
            if law is not None: points[indices]=law.quantile(.5) if support=='signed_integer' else law.mean
        if family=='cdf_small_correction':
            base_reasons=reasons.copy();points,reasons=model['correction'].predict(frame,points)
            reasons=np.array([f'base:{a};correction:{b or "applied"}' if a else b
                              for a,b in zip(base_reasons,reasons)],dtype=object)
    else:points,reasons=model.predict(frame)
    points=np.asarray(points,dtype=float);reasons=np.asarray(reasons,dtype=str)
    require(points.shape==reasons.shape==(len(frame),),'every offered row must remain')
    if family=='count_A':
        # The frozen research model deliberately retains numeric prior medians.
        # This versioned weekly mean product changes only explicit fallbacks;
        # warm fitted values and the historical model object remain unchanged.
        points=points.copy()
        roles=cdf.strings(frame,'position')
        for i in np.flatnonzero(reasons!=''):
            prior=model.priors.get(str(roles[i]),model.global_prior)
            if prior is not None:
                require(prior.support=='count' and np.isfinite(prior.mean)
                    and prior.mean>=0,'invalid stored count fallback prior')
                points[i]=prior.mean
    finite=np.isfinite(points)
    require(not np.isinf(points).any(),'infinite forecast')
    if support=='count': require((points[finite]>=0).all(),'negative count point')
    if support=='bernoulli':require(((points[finite]>=0)&(points[finite]<=1)).all(),'invalid event probability')
    return points,reasons


def prediction_bits(model, family, frame):
    points,reasons=_points(model,family,frame)
    return dict(float64_hex=points.astype('<f8').tobytes().hex(),fallback=reasons.tolist())


def export_trained_artifact(directory, model, *, family, method_id, training_frame,
                            training_cutoff_utc, source_contract, training_sources,
                            replay_fixture, storage,base_artifact=None, maximum_serialized_bytes=None):
    """Export already-trained state; never fit or relax a historical wrapper."""
    import joblib
    directory=Path(directory);require(not directory.exists(),'fresh artifact directory required')
    category,features=model_contract(model,family);cutoff=utc(training_cutoff_utc)
    require(bool(training_sources) and set(source_contract)>={'source_policy_sha256','feature_builder_sha256','availability_rule'},
            'explicit training source/preprocessing contract required')
    from .operational_storage import OperationalStorage
    if isinstance(storage,OperationalStorage):
        from .owned_reference_batch import validate_owned_references
        items=training_sources+([base_artifact] if base_artifact else [])
        validate_owned_references(storage,{b['path']:b['sha256'] for b in items})
    else:require(getattr(storage,'fictional_test_storage',False),'production export requires original quota-owned storage')
    require(len(training_frame)>0 and {'kickoff_utc','outcome_available_utc'}<=set(training_frame),'training clock columns required')
    for name in ('kickoff_utc','outcome_available_utc'):
        values=pd.to_datetime(training_frame[name],utc=True,errors='coerce')
        require(values.notna().all() and (values<cutoff).all(),'training must be strictly earlier and available')
    base=model['base'] if family=='cdf_small_correction' else model
    for name in ('training_binding','prior_training_binding'):
        fitted=getattr(base,name,None)
        require(fitted is not None and len(fitted)>0,'retained actual estimator/prior training identity required')
        require(set(map(tuple,fitted[cdf.KEYS].to_numpy()))<=set(map(tuple,training_frame[cdf.KEYS].to_numpy())),
                'model training rows outside authenticated training view')
        require((pd.to_datetime(fitted.outcome_available_utc,utc=True)<cutoff).all(),'model contains later labels')
        indexed=training_frame.set_index(cdf.KEYS)
        original=indexed.loc[pd.MultiIndex.from_frame(fitted[cdf.KEYS])].reset_index()
        pd.testing.assert_frame_equal(fitted.reset_index(drop=True),original[fitted.columns].reset_index(drop=True),
                                      check_dtype=False,check_exact=True)
    clean=query_projection(replay_fixture,features)
    expected=prediction_bits(model,family,clean)
    if base_artifact is not None:
        require(family=='cdf_small_correction','only correction may reference a base artifact')
        require(binding(base_artifact['path'])==base_artifact,'base artifact identity changed')
        parent=json.loads(Path(base_artifact['path']).read_text())
        require(parent['family']=='leaf_cdf_base' and parent['source_contract']==source_contract
            and parent['category']==category,'correction/base source contract mismatch')
    runtime=_runtime_state(model['correction'] if base_artifact else model)
    bundle=dict(model=runtime,fixture=clean,expected_bits=expected,
                base_artifact_sha256=base_artifact['sha256'] if base_artifact else None)
    stream=BytesIO();joblib.dump(bundle,stream,compress=3);body=stream.getvalue()
    if maximum_serialized_bytes is not None:
        require(type(maximum_serialized_bytes) is int and maximum_serialized_bytes > 262144
            and len(body)+262144 <= maximum_serialized_bytes,
            'trained artifact exceeds remaining model allocation; preserve prior evidence')
    model_path=directory/'trained.joblib';storage.write_bytes(model_path,body)
    fit_receipt=getattr(base,'weekly_fit_receipt',None)
    if family=='cdf_small_correction':
        fit_receipt=getattr(model['correction'],'weekly_fit_receipt',None)
    manifest=dict(schema_version=VERSION,artifact_kind='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY',
        family=family,method_id=method_id,procedure_version=procedure_version(family,source_contract),category=category,features=features,
        count_fallback_version=COUNT_A_FALLBACK_VERSION if family=='count_A' else None,
        dependencies=[base_artifact] if base_artifact else [],
        model=dict(path=str(model_path.absolute()),bytes=len(body),sha256=hashlib.sha256(body).hexdigest()),
        training_cutoff_utc=cutoff.isoformat(),training_max_available_utc=pd.to_datetime(training_frame.outcome_available_utc,utc=True).max().isoformat(),
        artifact_created_at=now_utc().isoformat(),training_frame_sha256=frame_digest(training_frame),
        fit_receipt=fit_receipt,fit_clock_status='RECORDED' if fit_receipt else 'LEGACY_UNAVAILABLE_NOT_OPERATIONALLY_READY',
        training_sources=training_sources,source_contract=source_contract,code_pins=code_pins(),environment=environment(),
        preprocessing='existing trained FixedDesign/CorrectionDesign; no query refit',
        fallback='existing trained role/global prior; all offered rows; absent supported prior abstains',
        roles=category['modeled_roles'],product=product(category)[0],metric=product(category)[2],
        probability_law=('EMPIRICAL_LEAF_PLUS_SUPPORT_PRIOR' if family=='leaf_cdf_base' else
                         'BERNOULLI' if category['support']=='bernoulli' else 'NONE_POINT_ONLY'),
        calibration='UNESTABLISHED',historical_artifact_checks='UNCHANGED',
        raw_training_row_arrays_retained=False,private_artifact=True,
        replay_fixture_sha256=frame_digest(clean),replay_bits_sha256=digest(expected))
    path=directory/'future-inference.json'
    manifest_body=(json.dumps(manifest,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(manifest_body)<=262144,'artifact manifest exceeds reserved retention')
    storage.write_bytes(path,manifest_body)
    return binding(path)


class FutureInferenceSession:
    """Authenticate once per operation, load each trained object once, chunk freely.

    Production uses ``from_storage``: original exclusive-lock/global quota scan,
    inode/readonly/hash validation at entry and exit remain unchanged. No cached
    result survives close or grants write admission. Tests may inject an
    authenticator over fictional immutable files.
    """
    def __init__(self, authenticator):
        require(callable(authenticator),'owned authenticator required')
        self.authenticate=authenticator;self.models={};self.refs={};self.stamps={};self.closed=False

    @classmethod
    def from_storage(cls,storage):
        from .owned_reference_batch import validate_owned_references
        def authenticate(items):
            return validate_owned_references(storage,{i['path']:i['sha256'] for i in items})[0]
        return cls(authenticate)

    def _verify(self,items,*,force=False):
        require(not self.closed,'session closed')
        unique={i['path']:i for i in items}
        require(len(unique)==len(items),'duplicate authenticated path')
        pending=[]
        def stamp(p):
            s=Path(p).lstat();require(not Path(p).is_symlink() and not s.st_mode&0o222,'immutable regular owned file required')
            return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        for p,item in unique.items():
            if p in self.refs:
                require(self.refs[p]==item and stamp(p)==self.stamps[p],'verified identity changed within operation')
            if force or p not in self.refs:pending.append(item)
        if not pending:return
        references=self.authenticate(pending)
        for item in pending:
            p=item['path']
            ref=references.get(p)
            require(isinstance(ref,dict) and all(ref.get(k)==item[k] for k in ('path','bytes','sha256')),
                    'owned source/artifact binding mismatch')
            self.stamps[p]=stamp(p)
        self.refs.update(unique)

    def prepare(self,manifest_bindings):
        import joblib
        self._verify(manifest_bindings);manifests={}
        current_code,current_environment=code_pins(),environment()
        for b in manifest_bindings:
            m=json.loads(Path(b['path']).read_text())
            require(m['schema_version']==VERSION and m['artifact_kind']=='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY',
                    'new future-query schema required; old query checks cannot be bypassed')
            require(m['code_pins']==current_code and m['environment']==current_environment,'trained code/environment changed')
            if m['family']=='count_A':
                require(m.get('count_fallback_version')==COUNT_A_FALLBACK_VERSION,
                    'versioned weekly count-mean fallback artifact required; requalification needed')
            manifests[b['sha256']]=m
        self._verify([m['model'] for m in manifests.values()])
        for version,m in sorted(manifests.items(),key=lambda item:item[1]['family']=='cdf_small_correction'):
            bundle=joblib.load(m['model']['path']);model=bundle['model']
            if bundle['base_artifact_sha256'] is not None:
                parent=bundle['base_artifact_sha256']
                require(parent in self.models and m['dependencies']==[next(b for b in manifest_bindings if b['sha256']==parent)],
                        'authenticated base dependency required before correction')
                pm,base=self.models[parent]
                require(pm['family']=='leaf_cdf_base' and pm['source_contract']==m['source_contract']
                    and pm['category']==m['category'],'correction dependency contract mismatch')
                model={'base':base,'correction':model}
            require(model_contract(model,m['family'])==(m['category'],m['features']),'trained schema/preprocessing changed')
            require(frame_digest(bundle['fixture'])==m['replay_fixture_sha256'],'replay fixture changed')
            bits=prediction_bits(model,m['family'],bundle['fixture'])
            require(bits==bundle['expected_bits'] and digest(bits)==m['replay_bits_sha256'],'trained replay bits changed')
            self.models[version]=(m,model)
        return self

    def predict_chunks(self,version,frame,*,context,batch_size=256,clock=now_utc):
        require(not self.closed and version in self.models,'prepared immutable model required')
        require(type(batch_size) is int and 1<=batch_size<=2048,'bounded chunk size required')
        m,model=self.models[version];clean=query_projection(frame,m['features']);query_sha=frame_digest(clean)
        cutoff=utc(context['cutoff_utc']);lane=context['evidence_lane']
        weekly_choice=utc(context['weekly_decision_cutoff_utc'])
        require(lane in LANES and context['reference_stream'] in ('candidate','historical_LAB_CDF'),'separate reference stream required')
        require(context['source_contract']==m['source_contract'],'future query source/preprocessing version mismatch')
        require(utc(m['training_cutoff_utc'])<=cutoff,'training cutoff after decision')
        require((pd.to_datetime(clean.cutoff_utc,utc=True)==cutoff).all(),'single exact per-game input cutoff required')
        require((pd.to_datetime(clean.kickoff_utc,utc=True)>weekly_choice).all(),'weekly choice must precede slate kickoffs')
        source=pd.to_datetime(clean.feature_max_source_available_utc,utc=True,errors='coerce')
        warm=cdf.numeric(clean,'f_player_games_prior')>0
        require(not (source.isna()&warm).any() and (source.dropna()<cutoff).all(),'query source availability must precede cutoff')
        operational=lane=='original_pregame'
        equal_clock=(pd.to_datetime(clean.kickoff_utc,utc=True)==cutoff).any()
        if equal_clock:
            require(not operational and context.get('replay_horizon')=='reconstructed_kickoff'
                and context.get('replay_horizon_version')=='reconstructed-kickoff-horizon-v1',
                'exact historical kickoff horizon must be explicitly declared')
        if operational:
            receipt=context['feature_capture_receipt'];self._verify([receipt])
            doc=json.loads(Path(receipt['path']).read_text())
            require(doc['schema_version']=='weekly-feature-capture-v1'
                and doc['source_contract']==m['source_contract']
                and doc['query_projection_sha256']==query_sha
                and utc(doc['feature_persist_completed_at'])<cutoff,'actual current feature-capture receipt required')
        else:
            require(context.get('frozen_before_grading') is True and context.get('replay_cutoff_utc')==context['cutoff_utc']
                and bool(context.get('authenticated_replay_binding')),'historical replay evidence must be explicit')
        p,functional,metric=product(m['category'])
        for start in range(0,len(clean),batch_size):
            part=clean.iloc[start:start+batch_size];issued=clock()
            if operational:
                require(issued<cutoff and (pd.to_datetime(part.kickoff_utc,utc=True)>cutoff).all(),
                        'actual issuance must precede per-game input cutoff/kickoff')
                fit=m['fit_receipt'];require(isinstance(fit,dict),'actual fit clocks missing')
                require(utc(fit['training_source_capture_completed_at'])<=utc(fit['training_started_at'])
                    <=utc(fit['training_completed_at'])<=issued
                    and utc(m['training_max_available_utc'])<utc(fit['training_started_at'])
                    and utc(m['training_max_available_utc'])<issued
                    and utc(doc['feature_persist_completed_at'])<=issued,'fit/source availability is after actual issuance')
                actual_sources=pd.to_datetime(part.feature_max_source_available_utc,utc=True,errors='coerce').dropna()
                require((actual_sources<=issued).all(),'query source is after actual issuance')
            points,reasons=_points(model,m['family'],part);rows=[]
            for ordinal,((_,q),point,reason) in enumerate(zip(part.iterrows(),points,reasons),start):
                identity={k:q[k].item() if isinstance(q[k],np.generic) else q[k] for k in cdf.KEYS}
                offered=digest({**identity,'category':m['category']['target']})
                value=float(point) if np.isfinite(point) else None
                row=dict(offered_id=offered,category=m['category']['target'],season=int(q.season),week=int(q.week),
                    slate_id=context['slate_id'],horizon='player_game',method_id=m['method_id'],model_version=version,
                    procedure_version=m['procedure_version'],
                    product=p,prediction_functional=functional,forecast_value=value,metric=metric,
                    player_id=str(q.player_id),game_id=str(q.game_id),team=str(q.team),opponent=str(q.opponent),position=str(q.position),
                    issued_at=issued.isoformat(),cutoff_utc=cutoff.isoformat(),kickoff_utc=utc(q.kickoff_utc).isoformat(),
                    weekly_decision_cutoff_utc=weekly_choice.isoformat(),
                    operational_eligible=bool(operational and value is not None),evidence_lane=lane,
                    reference_stream=context['reference_stream'],fallback=bool(reason),fallback_reason=str(reason),
                    training_cutoff_utc=m['training_cutoff_utc'],training_max_available_utc=m['training_max_available_utc'],source_policy_sha256=m['source_contract']['source_policy_sha256'],
                    training_started_at=m['fit_receipt']['training_started_at'] if m['fit_receipt'] else None,
                    training_completed_at=m['fit_receipt']['training_completed_at'] if m['fit_receipt'] else None,
                    source_capture_completed_at=doc['feature_persist_completed_at'] if operational else None,
                    training_source_capture_completed_at=m['fit_receipt']['training_source_capture_completed_at'] if m['fit_receipt'] else None,
                    feature_max_source_available_utc=utc(q.feature_max_source_available_utc).isoformat() if pd.notna(q.feature_max_source_available_utc) else None,
                    query_source_sha256=context['query_source_sha256'],artifact_sha256=version,
                    distribution_kind=m['probability_law'],distribution_ref=dict(artifact_sha256=version,
                        query_projection_sha256=query_sha,row_ordinal=ordinal) if m['probability_law']!='NONE_POINT_ONLY' else None,
                    scientific_qualification=False,publication_status='PRIVATE_PENDING_DURABLE_COMPLETION')
                if not operational:row.update(replay_cutoff_utc=context['replay_cutoff_utc'],frozen_before_grading=True,
                    authenticated_replay_binding=context['authenticated_replay_binding'],replay_eligible=value is not None)
                rows.append(row)
            yield rows

    def close(self):
        if not self.closed:
            self._verify(list(self.refs.values()),force=True)
            current=code_pins()
            require(all(m['code_pins']==current for m,_ in self.models.values()),'code changed during operation')
            self.models.clear();self.closed=True

    def __enter__(self):return self
    def __exit__(self,*unused):self.close()


def export_policy_inputs(chunks,sink):
    """Stream JSONL in chunk-sized writes to the caller's existing quota sink.

    No per-row CAS objects or full-cache validation loops are introduced. A
    caller must retain a separate actual persistence-completion receipt before
    operational use; generating rows alone never claims completed durability.
    """
    count=0;h=hashlib.sha256()
    for rows in chunks:
        body=b''.join((json.dumps(r,sort_keys=True,separators=(',', ':'),allow_nan=False)+'\n').encode() for r in rows)
        sink.write(body);h.update(body);count+=len(rows)
    return dict(schema_version=VERSION+'-policy-input',rows=count,sha256=h.hexdigest(),
                durability='REQUIRES_ORIGINAL_SINK_COMPLETION_RECEIPT')


def cached_forecast_chunks(frame,*,category,contract,slates,batch_size=256):
    """Project authenticated old numeric forecasts without changing their clock.

    The caller first authenticates every binding through the session's original
    owned batch validator. This pure projection does not re-predict or acquire.
    Actual per-row issuance unavailable in older files stays explicitly unknown;
    their authentic GLOBAL freeze completion supplies a conservative known-by
    generation bound, never a fabricated historical pregame clock.
    """
    require(contract['schema_version']=='weekly-cached-per-game-v1','explicit cached product contract required')
    require(contract['frozen_before_grading'] is True,'original forecast-before-grading freeze required')
    freeze=json.loads(Path(contract['forecast_freeze_binding']['path']).read_text())
    require(freeze['bindings'].get(contract['original_relative_path'])==contract['forecast_binding']['sha256'],
            'cached forecast outside authenticated original freeze')
    clock_field=contract.get('generation_clock_field','generated_at')
    require(clock_field in freeze,'authentic generation clock unavailable; never fabricate issuance')
    generated=utc(freeze[clock_field]);column=contract['point_column'];p,functional,metric=product(category)
    require(set(IDENTITY+[column,'fallback'])<=set(frame),'complete cached row product/identity required')
    require(not frame.duplicated(cdf.KEYS).any(),'duplicate cached offered identities')
    for start in range(0,len(frame),batch_size):
        rows=[]
        for _,q in frame.iloc[start:start+batch_size].iterrows():
            identity={k:q[k].item() if isinstance(q[k],np.generic) else q[k] for k in cdf.KEYS}
            slate=slates[f'{int(q.season)}-{int(q.week)}'];value=float(q[column]) if pd.notna(q[column]) else None
            if utc(q.cutoff_utc)==utc(q.kickoff_utc):
                require(contract.get('replay_horizon')=='reconstructed_kickoff'
                    and contract.get('replay_horizon_version')=='reconstructed-kickoff-horizon-v1',
                    'old kickoff cutoff requires an explicit reconstruction horizon')
            if value is not None:
                require(np.isfinite(value) and (category['support']!='count' or value>=0)
                    and (category['support']!='bernoulli' or 0<=value<=1),'cached point support violation')
            rows.append(dict(**identity,offered_id=digest({**identity,'category':category['target']}),category=category['target'],
                slate_id=slate['slate_id'],horizon='player_game',weekly_decision_cutoff_utc=slate['weekly_decision_cutoff_utc'],
                cutoff_utc=str(q.cutoff_utc),kickoff_utc=str(q.kickoff_utc),method_id=contract['method_id'],
                model_version=contract['model_version'],procedure_version=contract['procedure_version'],product=p,
                prediction_functional=functional,metric=metric,forecast_value=value,fallback=bool(q['fallback']),fallback_reason=str(q['fallback']),
                issued_at=generated.isoformat(),original_row_issued_at=None,
                issuance_clock_semantics='AUTHENTIC_GLOBAL_FORECAST_FREEZE_KNOWN_BY_BOUND; original per-row issuance unavailable',
                evidence_lane='current_vintage_availability_uncertain',reference_stream=contract['reference_stream'],
                operational_eligible=False,replay_eligible=value is not None,replay_cutoff_utc=str(q.cutoff_utc),frozen_before_grading=True,
                authenticated_replay_binding=contract['forecast_freeze_binding']['sha256'],
                training_cutoff_utc=contract['training_cutoff_utc'],training_max_available_utc=contract.get('training_max_available_utc'),
                source_policy_sha256=contract['source_policy_sha256'],original_forecast_sha256=contract['forecast_binding']['sha256'],
                scientific_qualification=False))
        yield rows


def replay_outcome_rows(frame,*,category,snapshot_id,clock_policy,stream_revision=1):
    """Actual known_at stays untouched; replay assumption is a separate field."""
    require(set(clock_policy)=={'policy_sha256','basis_column','lag_hours'} and len(clock_policy['policy_sha256'])==64,
            'separately frozen replay availability policy required')
    require(clock_policy['basis_column'] in ('kickoff_utc','ended_at') and clock_policy['lag_hours']>=0,
            'explicit clock basis/lag required; no default manufactured publication')
    require({'actual','participation_state','known_at',clock_policy['basis_column']}<=set(frame),'original outcome clock/state required')
    result=[]
    require(type(stream_revision) is int and stream_revision>0,'positive declared new-stream revision required')
    for _,r in frame.iterrows():
        identity={k:r[k].item() if isinstance(r[k],np.generic) else r[k] for k in cdf.KEYS}
        state=r['participation_state'];require(state in ('played','DNP','unknown'),'unknown participation never becomes zero')
        actual=float(r['actual']) if pd.notna(r['actual']) else None
        require(state=='played' or actual is None,'DNP/unknown cannot have numeric outcomes')
        if actual is not None:require(cdf.valid_support([actual],category['support'])[0],'invalid supported outcome')
        known=utc(r['known_at']);assumed=utc(r[clock_policy['basis_column']])+pd.Timedelta(hours=clock_policy['lag_hours'])
        result.append(dict(offered_id=digest({**identity,'category':category['target']}),**identity,category=category['target'],
            participation_state=state,actual=actual,available_at=known.isoformat(),actual_known_at=known.isoformat(),
            replay_available_at=assumed.isoformat(),replay_availability_policy_sha256=clock_policy['policy_sha256'],
            replay_availability_uncertain=True,replay_clock_basis=clock_policy['basis_column'],
            upstream_publication_utc=None,snapshot_id=snapshot_id,revision=stream_revision,
            original_revision=r.get('revision','original'),
            outcome_state='played_zero' if state=='played' and actual==0 else 'played_missing' if state=='played' and actual is None else state))
    return result


def replay_week_clock(*,actual_grade_completed_at,outcomes,clock_policy_sha256,all_games_final):
    """Separate explicit replay grade bound; genuine grade clock is retained."""
    require(bool(outcomes) and all(r['replay_availability_policy_sha256']==clock_policy_sha256
        and r['replay_availability_uncertain'] is True for r in outcomes),'same frozen replay clock policy required')
    return dict(grade_completed_at=utc(actual_grade_completed_at).isoformat(),
        replay_grade_completed_at=max(utc(r['replay_available_at']) for r in outcomes).isoformat() if all_games_final else None,
        replay_availability_policy_sha256=clock_policy_sha256,replay_availability_uncertain=True,
        all_games_final=bool(all_games_final),finality_proof='CALLER_MUST_BIND_COMPLETE_GAME_CENSUS')


def control_forecast_rows(frame,*,category,context,clock=now_utc):
    """Existing saved R0/RAW source points, with no invented upstream training.

    Caller authenticates original capture/policy/source bytes first. Literal
    website prop.proj is site_extracted_raw_sleeper, not a direct raw feed.
    """
    method=context['method_id'];require(method in ('R0','RAW'),'only original reference/raw controls')
    required=('control_policy_sha256','control_source_version','source_receipt_sha256','source_capture_completed_at')
    require(all(context.get(k) for k in required),'exact source-control policy/receipt identity required')
    require(context['reference_stream'] in ('live_R0','direct_provider_raw','site_extracted_raw_sleeper'),
            'explicit control source semantics required')
    support=category['support'];binary=support=='bernoulli'
    if binary:
        require(method=='R0' and context.get('saved_event_probability') is True
            and context.get('event_contract')=='anytime_rush_or_receive_td',
            'raw TD count cannot become an event probability')
    issued=clock();cutoff=utc(context['cutoff_utc'])
    require(utc(context['source_capture_completed_at'])<=issued<cutoff,'source control unavailable by actual issuance/cutoff')
    require((pd.to_datetime(frame.kickoff_utc,utc=True)>cutoff).all(),'control input cutoff before kickoff required')
    result=[]
    for _,q in frame.iterrows():
        identity={k:q[k].item() if isinstance(q[k],np.generic) else q[k] for k in cdf.KEYS}
        value=float(q['forecast_value']) if pd.notna(q['forecast_value']) else None
        if value is not None:require(np.isfinite(value) and (not binary or 0<=value<=1),'invalid saved source-control point')
        result.append(dict(**identity,offered_id=digest({**identity,'category':category['target']}),category=category['target'],
            slate_id=context['slate_id'],horizon='player_game',weekly_decision_cutoff_utc=context['weekly_decision_cutoff_utc'],
            cutoff_utc=cutoff.isoformat(),kickoff_utc=utc(q.kickoff_utc).isoformat(),issued_at=issued.isoformat(),
            method_id=method,model_version=context['model_version'],procedure_version=context['procedure_version'],
            product='binary_probability' if binary else 'point_legacy',prediction_functional='event_probability' if binary else 'legacy_unknown',
            forecast_value=value,fallback=value is None,fallback_reason='' if value is not None else 'saved_control_unavailable',
            reference_stream=context['reference_stream'],evidence_lane='original_pregame',operational_eligible=value is not None,
            training_state='UPSTREAM_TRAINING_UNOBSERVED',control_policy_sha256=context['control_policy_sha256'],
            control_source_version=context['control_source_version'],source_receipt_sha256=context['source_receipt_sha256'],
            source_capture_completed_at=context['source_capture_completed_at'],saved_event_probability=binary,
            event_contract=context.get('event_contract') if binary else None,scientific_qualification=False))
    return result


def persist_policy_inputs(path,chunks,*,storage,max_serialized_bytes,clock=now_utc):
    """One compressed body admission, not a CAS write/scan per row or chunk."""
    import gzip
    require(type(max_serialized_bytes) is int and 0<max_serialized_bytes<=64*1024*1024,'finite compressed export cap<=64MiB required')
    buffer=BytesIO();started=clock();rows=0;minimum_cutoff=None
    with gzip.GzipFile(fileobj=buffer,mode='wb',mtime=0) as compressed:
        for chunk in chunks:
            export_policy_inputs([chunk],compressed);rows+=len(chunk)
            for r in chunk:
                if r['operational_eligible']:
                    value=utc(r['cutoff_utc']);minimum_cutoff=value if minimum_cutoff is None else min(minimum_cutoff,value)
            require(buffer.tell()<=max_serialized_bytes,'compressed export capacity exhausted before admission')
    body=buffer.getvalue();require(len(body)<=max_serialized_bytes,'final serialized export exceeds cap')
    storage.write_bytes(path,body);completed=clock();late=minimum_cutoff is not None and completed>=minimum_cutoff
    result=dict(schema_version=VERSION+'-persistence',state='FAILED_LATE' if late else 'PERSISTED',
        binding=binding(path),rows=rows,persist_started_at=started.isoformat(),completed_at=completed.isoformat(),
        private_only=True,remote_durability='NOT_ESTABLISHED',scientific_qualification=False)
    storage.write_bytes(Path(path).with_suffix('.completion.json'),(json.dumps(result,sort_keys=True,indent=2)+'\n').encode())
    require(not late,'export completed after input cutoff; failed immutable evidence retained')
    return result


def fit_future_model(train,category,family,*,training_cutoff_utc,fit_gate,
                     training_source_capture_completed_at,expected_native_version=None,clock=now_utc):
    """Finite caller-gated training entry; never called during preparation.

    Existing estimators, feature design, roles, priors and objective parameters
    are reused. This is a new training policy, not a mutation of old artifacts.
    """
    cdf.validate_category(category);require(category['target']!='fantasy_ppr','PPR blocked')
    require(callable(fit_gate),'consuming finite fit gate required')
    cutoff=utc(training_cutoff_utc)
    for name in ('kickoff_utc','outcome_available_utc'):
        values=pd.to_datetime(train[name],utc=True,errors='coerce')
        require(values.notna().all() and (values<cutoff).all(),'strictly earlier training required')
    started=clock();require(utc(training_source_capture_completed_at)<=started,'training source captured after fit start')
    require((pd.to_datetime(train.outcome_available_utc,utc=True)<started).all(),'training availability after actual fit start')
    def finish(model):
        model.weekly_fit_receipt=dict(training_started_at=started.isoformat(),training_completed_at=clock().isoformat(),
            training_source_capture_completed_at=utc(training_source_capture_completed_at).isoformat(),clock_basis='ACTUAL_FIT_CALL')
        return model
    require(family in ('leaf_cdf_base','count_A','catboost_medium'),'correction needs separate earlier OOF fit')
    if family=='catboost_medium':
        from .direct_boosters import DirectBoosterModel
        return finish(DirectBoosterModel.fit(train,category,'base',library='catboost',complexity='medium',
            expected_version=expected_native_version,fit_gate=fit_gate))
    fit_gate(dict(family=family,category=category['target'],kind='ESTIMATOR_ATTEMPT_RESERVED'))
    if family=='leaf_cdf_base':return finish(cdf.LeafCDFModel.fit(train,category,'base'))
    if family=='count_A':
        from .role_boosting import RoleCountBoostingModel
        require(category['support']=='count','CountA numeric count only')
        return finish(RoleCountBoostingModel.fit(train,category,'A'))
    raise ValueError('correction requires authentic earlier OOF predictions, not in-sample refit')


def persist_feature_capture(path,frame,*,features,source_contract,source_bindings,storage,clock=now_utc):
    """Current local feature-availability witness, never upstream publication.

    Authenticate existing retained source bodies before writing this feature
    snapshot. Seven-day reconstructed historical eligibility stays explicitly
    in source_contract; observing a cache now does not backdate that history.
    """
    from .owned_reference_batch import validate_owned_references
    require(bool(source_bindings),'actual retained source bodies required')
    validate_owned_references(storage,{b['path']:b['sha256'] for b in source_bindings})
    started=clock();clean=query_projection(frame,features);stream=BytesIO()
    clean.to_parquet(stream,index=False,compression='zstd')
    storage.write_bytes(path,stream.getvalue());completed=clock()
    receipt=Path(path).with_suffix('.capture.json')
    storage.write_bytes(receipt,(json.dumps(dict(schema_version='weekly-feature-capture-v1',
        capture_started_at=started.isoformat(),feature_persist_completed_at=completed.isoformat(),
        feature_binding=binding(path),query_projection_sha256=frame_digest(clean),source_contract=source_contract,
        source_bindings=source_bindings,upstream_publication='NOT_INFERRED',
        historical_availability_rule=source_contract['availability_rule']),sort_keys=True,indent=2)+'\n').encode())
    return binding(path),binding(receipt)


def build_future_features(history,queries,*,policy,source_contract):
    """Existing permitted builder, same source policy and historical lag lane."""
    from .operational_sources import build_operational_features
    require(policy.get('_policy_sha256')==source_contract['source_policy_sha256'],'source policy version mismatch')
    require(source_contract['availability_rule']=='FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION',
            'new genuine-availability policies require their own adapter, never retrofitting old history')
    require(sha(Path(__file__).parent/'operational_sources.py')==source_contract['feature_builder_sha256'],
            'feature builder identity changed')
    # Existing loader must already have applied its before-stat-read predicates.
    # This is not an alternative source loader or a way to inspect future labels.
    require('operational_manifest' in history.attrs,'qualified source manifest required')
    return build_operational_features(history,policy=policy,queries=queries)


def fit_small_correction(oof,base,category,*,training_cutoff_utc,oof_receipt,fit_gate,
                         training_source_capture_completed_at,method=None,clock=now_utc):
    """Existing fixed small correction, new explicit earlier-OOF gate."""
    from .baseline_correction import (BaselineCorrection,CorrectionDesign,baseline_support,
        offset,smooth_objective,METHODS)
    from scipy.optimize import minimize
    from sklearn.linear_model import QuantileRegressor
    cutoff=utc(training_cutoff_utc);cdf.validate_category(category);started=clock()
    require(utc(training_source_capture_completed_at)<=started,'OOF source captured after fit start')
    require((pd.to_datetime(oof.outcome_available_utc,utc=True)<started).all(),'OOF label availability after actual fit start')
    require(category['target']!='fantasy_ppr' and callable(fit_gate),'supported category and finite fit gate required')
    require(oof_receipt.get('frozen_before_scoring') is True and bool(oof_receipt.get('fold_forecast_bindings')),
            'authentic frozen earlier OOF forecasts required; no in-sample residual fitting')
    required={'outcome_available_utc','baseline_training_cutoff_utc','kickoff_utc'}
    require(required<=set(oof),'OOF chronology evidence required')
    require((pd.to_datetime(oof.outcome_available_utc,utc=True)<cutoff).all()
        and (pd.to_datetime(oof.baseline_training_cutoff_utc,utc=True)<pd.to_datetime(oof.kickoff_utc,utc=True)).all(),
        'OOF labels/training must be earlier than their boundaries')
    base=np.asarray(base,dtype=float);require(base.shape==(len(oof),),'all OOF rows retained')
    y=cdf.numeric(oof,category['target']);support=category['support']
    eligible=(oof.participation_state.eq('played').to_numpy()&oof.position.isin(category['primary_roles']).to_numpy()
              &cdf.valid_support(y,support)&baseline_support(base,support,fitting=True))
    require(eligible.any(),'no supported earlier OOF correction rows')
    method=method or (METHODS[1] if category['target']=='pass_td' else METHODS[0])
    require(method in METHODS,'fixed correction arm required')
    part=oof.loc[eligible];design=CorrectionDesign.fit(part,method,category['target']);x=design.transform(part)
    fit_gate(dict(family='cdf_small_correction',category=category['target'],kind='ESTIMATOR_ATTEMPT_RESERVED'))
    if support=='signed_integer':
        estimator=QuantileRegressor(quantile=.5,alpha=.1,fit_intercept=False,solver='highs',
            solver_options={'time_limit':15.,'threads':1})
        estimator.fit(x,y[eligible]-base[eligible]);beta=estimator.coef_
    else:
        result=minimize(smooth_objective,np.zeros(x.shape[1]),args=(x,offset(base[eligible],support),y[eligible],support),
            jac=True,method='L-BFGS-B',options={'maxiter':100,'ftol':1e-10,'gtol':1e-7})
        require(result.success,'fixed correction optimizer did not converge');beta=result.x
    require(np.isfinite(beta).all(),'nonfinite correction')
    model=BaselineCorrection(category,method,design,np.asarray(beta),dict(
        version=VERSION,fit_rule='same fixed correction; strictly earlier authenticated OOF only',
        training_cutoff_utc=cutoff.isoformat(),oof_receipt=oof_receipt,fitted_rows=int(eligible.sum())))
    model.weekly_fit_receipt=dict(training_started_at=started.isoformat(),training_completed_at=clock().isoformat(),
        training_source_capture_completed_at=utc(training_source_capture_completed_at).isoformat(),clock_basis='ACTUAL_FIT_CALL')
    return model
