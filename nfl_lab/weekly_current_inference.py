"""One frozen current-feature snapshot, existing future estimators, no fits/HTTP.

Publication/selection and remote durability are separate. Canonical GSIS/game
identities are retained beside an exact source-bound Sleeper/ESPN bridge.
"""
from __future__ import annotations

from datetime import datetime,timezone
import json
from pathlib import Path

import pandas as pd

from .state import digest,utc,now_utc
from . import weekly_future_inference as future
from . import weekly_current_query as query

VERSION='weekly-current-inference-capture-v1'
CUTOFF='2026-10-24T12:00:00Z'
TARGETS={'pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td'}
EXPECTED={(t,'LAB_CDF') for t in TARGETS}|{(t,'COUNT_A') for t in ('rush_att','rec')}|{(t,'CATBOOST_MEDIUM') for t in ('pass_yd','rush_yd','rec_yd','rush_rec_yd','anytime_td')}
BRIDGE_COLUMNS=['season','week','game_id','player_id','sleeper_id','team','opponent','position','kickoff_utc','cutoff_utc','participation_state','identity_status']
SCHEDULE_COLUMNS=query.SCHEDULE_COLUMNS+['espn']


def require(value,message):
    if not value:raise ValueError(message)


def read_metadata(reference):
    require(future.binding(reference['path'])==reference,'metadata binding changed')
    return json.loads(Path(reference['path']).read_bytes())



def validate_startup_policy(policy,decision_clock,actual_clock):
    require(policy['schema_version']=='weekly-provisional-live-policy-v1' and policy['state']=='REGISTERED_STAGED_NOT_ACTIVATED',
            'root-registered staged startup policy required; no activation claim')
    require(policy['initial_slate_id']=='2026-REG-W07-remaining-initial-v1'
        and utc(policy['initial_input_deadline_utc'])==utc(CUTOFF),'exact initial remaining W7 policy scope required')
    require(utc(policy['registered_at_utc'])<=utc(decision_clock)<=actual_clock<utc(CUTOFF),
            'actual startup choice must follow registration and precede actual issuance; no future12Z decision fiction')
    return policy['registered_at_utc']


def validate_manifests(records,source_contract,*,strict_initial=True):
    """Declared JSON schema only, before any trained object is decoded."""
    seen=set();versions=set()
    for record in records:
        m=record['manifest'];b=record['binding'];target=m['category']['target'];key=(target,m['method_id'])
        require(key not in seen and b['sha256'] not in versions,'duplicate registered model/slot')
        seen.add(key);versions.add(b['sha256'])
        require(m['schema_version']==future.VERSION and m['artifact_kind']=='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY',
                'authentic generic future-query artifact required')
        require(m['source_contract']==source_contract and m['family']=={'LAB_CDF':'leaf_cdf_base','COUNT_A':'count_A','CATBOOST_MEDIUM':'catboost_medium'}.get(m['method_id']),
                'original source contract/fixed family required; correction reservations unused')
        require(not m['dependencies'] and isinstance(m['fit_receipt'],dict),'standalone authentic fit receipt required')
        require(m['product']==future.product(m['category'])[0] and m['procedure_version'],'declared product/procedure required')
        fit=m['fit_receipt']
        require(utc(fit['training_source_capture_completed_at'])<=utc(fit['training_started_at'])<=utc(fit['training_completed_at'])
            and utc(m['training_max_available_utc'])<utc(fit['training_started_at'])
            and utc(m['training_max_available_utc'])<utc(m['training_cutoff_utc'])<=utc(CUTOFF),
            'actual fit and earlier training chronology required')
        require(target in TARGETS and record['eligible_roles'] and len(record['eligible_roles'])==len(set(record['eligible_roles']))
            and set(record['eligible_roles'])<=set(m['category']['modeled_roles']),
                'explicit eligible role subset of trained role contract required')
    if strict_initial:require(seen==EXPECTED and len(records)==18,'exact17V3+1V4 eighteen-model initial catalog required')
    return records


def validate_shared_snapshot(features,queries,capture,*,feature_binding,source_contract,cutoff=CUTOFF):
    require(capture['schema_version']=='weekly-feature-capture-v1' and capture['source_contract']==source_contract
        and capture['feature_binding']==feature_binding,'original actual shared feature capture required')
    names=[n for n in features if n.startswith('f_')]
    require(future.frame_digest(future.query_projection(features,names))==capture['query_projection_sha256'],
            'shared feature bytes/schema differ from authentic capture')
    require(utc(capture['capture_started_at'])<=utc(capture['feature_persist_completed_at'])<utc(cutoff),
            'actual feature capture must precede fixed input cutoff; no future-asof clock')
    require(set(BRIDGE_COLUMNS)<=set(queries) and len(features)==len(queries)<=1000,'all offered current identity rows required')
    require(not queries.duplicated(['game_id','player_id']).any() and not queries.sleeper_id.duplicated().any(),
            'unique current exact GSIS/Sleeper offer binding required')
    for name in future.IDENTITY:
        if name in ('kickoff_utc','cutoff_utc'):
            equal=(pd.to_datetime(features[name],utc=True).reset_index(drop=True)==pd.to_datetime(queries[name],utc=True).reset_index(drop=True)).all()
        else:equal=features[name].tolist()==queries[name].tolist()
        require(equal,'feature/query identity or ordering mismatch: '+name)
    require(queries.participation_state.eq('unknown').all(),'roster status cannot establish participation/DNP')
    require(queries.identity_status.eq('source_exact_weekly_gsis_sleeper_team_game_binding').all(),'source-exact identity bridge required')
    require(queries.season.eq(2026).all() and queries.week.eq(7).all()
        and (pd.to_datetime(features.cutoff_utc,utc=True)==utc(cutoff)).all()
        and (pd.to_datetime(features.kickoff_utc,utc=True)>utc(cutoff)).all(),'one same-cutoff future-only W7 slate required')
    return features


def exact_bridge(queries,schedule,*,schedule_binding,query_binding):
    """No names or inferred game IDs: retain both source ID namespaces."""
    require(set(SCHEDULE_COLUMNS)<=set(schedule),'original schedule ESPN identity projection required')
    games=schedule.loc[schedule.season.eq(2026)&schedule.week.eq(7)&schedule.game_type.eq('REG'),SCHEDULE_COLUMNS].copy()
    require(not games.game_id.duplicated().any(),'ambiguous original schedule game')
    local=pd.to_datetime(games.gameday.astype('string')+' '+games.gametime.astype('string'),errors='coerce')
    games['kickoff_utc']=local.dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('UTC')
    for column in ('home_team','away_team'):games[column]=query.data._team(games[column])
    games['website_game_id']=games.espn.map(query._sleeper)
    require(games.website_game_id.notna().all() and not games.website_game_id.duplicated().any(),'exact unique original ESPN IDs required')
    indexed=games.set_index('game_id');result={}
    for q in queries[BRIDGE_COLUMNS].to_dict('records'):
        require(query._gsis(q['player_id'])==q['player_id'] and query._sleeper(q['sleeper_id'])==q['sleeper_id'],
                'canonical exact source GSIS and Sleeper IDs required')
        require(q['game_id'] in indexed.index,'current game missing original schedule')
        g=indexed.loc[q['game_id']];sides={g.home_team:g.away_team,g.away_team:g.home_team}
        require(sides.get(q['team'])==q['opponent'] and utc(g.kickoff_utc)==utc(q['kickoff_utc']),
                'source game/team/opponent/kickoff bridge mismatch')
        key=(int(q['season']),int(q['week']),q['game_id'],q['player_id'])
        record=dict(gsis_id=q['player_id'],gsis_game_id=q['game_id'],sleeper_id=q['sleeper_id'],
            website_player_id=q['sleeper_id'],website_game_id=g.website_game_id,
            team=q['team'],opponent=q['opponent'],kickoff_utc=utc(q['kickoff_utc']).isoformat(),
            query_source_sha256=query_binding['sha256'],schedule_source_sha256=schedule_binding['sha256'],
            identity_bridge_kind='EXACT_ORIGINAL_WEEKLY_ROSTER_AND_SCHEDULE_NOT_NAMES',
            actual_visible_board_compatibility='NOT_YET_CHECKED')
        record['identity_binding_sha256']=digest(record);result[key]=record
    return result


def procedure_catalog(records,*,registered_at,query_result_binding,source_contract):
    categories={}
    for record in records:
        m=record['manifest'];target=m['category']['target'];p,functional,_=future.product(m['category'])
        category=categories.setdefault(target,dict(support=m['category']['support'],product=p,prediction_functional=functional,
            eligible_roles=record['eligible_roles'],primary_roles=m['category']['primary_roles'],methods={}))
        require(category['eligible_roles']==record['eligible_roles'],'category models must share one offered cohort')
        category['methods'][m['method_id']]=dict(model_version=record['binding']['sha256'],model_binding=m['model'],
            procedure_version=m['procedure_version'],family=m['family'],fit_receipt=m['fit_receipt'],
            training_cutoff_utc=m['training_cutoff_utc'],training_max_available_utc=m['training_max_available_utc'],
            fallback=m['fallback'],probability_law=m['probability_law'],calibration='UNESTABLISHED')
    return dict(schema_version=VERSION+'-procedure-catalog',registered_at=registered_at,categories=categories,
        exact_PPR='BLOCKED_LABEL_CONTRACT',query_result=query_result_binding,source_contract=source_contract,
        selection='ALL_REGISTERED_CANDIDATE_SHADOWS; no chosen procedure or R0 claimed',
        corrections='TWO_REMAINING_FIT_RESERVATIONS_UNTOUCHED',scientific_qualification=False)


def projection_receipts(records,features,capture,capture_binding,*,storage,output,clock=now_utc):
    """Seven identity/role/feature views of ONE already-persisted shared snapshot.

    Original capture clocks remain genuine; the new descriptor records its own
    actual local persistence separately. No feature source is re-observed or
    recomputed, and no second physical feature matrix is saved.
    """
    result={};roles={}
    for record in records:
        m=record['manifest'];key=digest(dict(features=m['features'],eligible_roles=record['eligible_roles']))
        if key not in result:
            clean=future.query_projection(features,m['features'])
            view=clean.loc[clean.position.isin(record['eligible_roles'])]
            clean=view;doc=dict(capture)
            doc.update(query_projection_sha256=future.frame_digest(clean),parent_shared_capture=capture_binding,
                projection_kind='AUTHENTICATED_SUBSET_OF_SAME_IMMUTABLE_SHARED_FEATURE_SNAPSHOT',
                projection_features=m['features'],projection_eligible_roles=record['eligible_roles'],
                projection_rows=len(clean),projection_descriptor_started_at=clock().isoformat())
            path=Path(output)/'projections'/(key+'.json');storage.write_bytes(path,(json.dumps(doc,sort_keys=True,indent=2)+'\n').encode())
            result[key]=dict(binding=future.binding(path),ready_at=clock().isoformat(),view=view)
        roles[record['binding']['sha256']]=key
    return result,roles


def capture_registered(session,records,features,bridge,projections,projection_keys,*,storage,output,context,
                       max_rows,max_bytes,batch_size=128,clock=now_utc,progress=lambda:None):
    """One fixed inference attempt/model, bounded existing persistence, no retry."""
    results=[];counts={'prediction_rows':0,'models_attempted':0,'operational_forecasts':0,'abstentions':0};retained=0
    for record in records:
        progress();m=record['manifest'];version=record['binding']['sha256'];target=m['category']['target']
        require(clock()<utc(context['cutoff_utc']),'input cutoff elapsed; remaining models are not issued')
        require(utc(m['artifact_created_at'])<=clock(),'artifact creation is after actual inference clock')
        projection=projections[projection_keys[version]];view=projection['view']
        require(utc(projection['ready_at'])<=clock(),'actual projection receipt is after issuance')
        expected=[digest({**{k:q[k] for k in ('season','week','game_id','player_id')},'category':target}) for q in view.to_dict('records')]
        observed=[];failure=None;valid=0;counts['models_attempted']+=1
        def chunks():
            nonlocal failure,valid
            try:
                for rows in session.predict_chunks(version,view,context=dict(context,
                        feature_capture_receipt=projection['binding']),batch_size=batch_size,clock=clock):
                    progress()
                    require(counts['prediction_rows']+len(rows)<=max_rows,'finite all-model row ceiling; never truncate')
                    staged_ids=[]
                    for offset,row in enumerate(rows):
                        ordinal=len(observed)+offset
                        require(ordinal<len(expected) and row['offered_id']==expected[ordinal],'prediction lost/reordered an original eligible offer')
                        identity=(row['season'],row['week'],row['game_id'],row['player_id']);binding=bridge[identity]
                        require(utc(projection['ready_at'])<=utc(row['issued_at']),'projection descriptor persisted after actual model issuance')
                        row.update(**binding,source_cutoff_utc=row['cutoff_utc'],source_projection_receipt=projection['binding'],
                            source_projection_receipt_completed_at=projection['ready_at'],
                            participation_state='unknown',capture_registration_id=VERSION,
                            startup_policy_sha256=context.get('startup_policy_sha256'),
                            startup_policy_registered_at=context.get('startup_policy_registered_at'),
                            primary_role=row['position'] in m['category']['primary_roles'],
                            public_initial_scope_eligible=bool(row['operational_eligible'] and row['position'] in m['category']['primary_roles']),
                            slate_kind='INITIAL_REMAINING_W7',historical_feature_availability_uncertain=True,
                            historical_feature_availability_rule=m['source_contract']['availability_rule'],
                            upstream_publication='NOT_INFERRED_FROM_CURRENT_READBACK')
                        staged_ids.append(row['offered_id'])
                    observed.extend(staged_ids);counts['prediction_rows']+=len(rows)
                    nvalid=sum(row['operational_eligible'] and row.get('forecast_value') is not None for row in rows)
                    valid+=nvalid;counts['operational_forecasts']+=nvalid;counts['abstentions']+=len(rows)-nvalid
                    yield rows
            except Exception as error:
                failure=dict(error_type=type(error).__name__,message=str(error)[:500])
        path=Path(output)/'forecasts'/target/(m['method_id']+'.jsonl.gz')
        # Admission and complete-body bounds remain in the unchanged helper.
        receipt=future.persist_policy_inputs(path,chunks(),storage=storage,
            max_serialized_bytes=max_bytes-retained-262144,clock=clock)
        require(receipt['rows']==len(observed),'persisted prefix and model coverage must agree exactly')
        retained+=receipt['binding']['bytes']+Path(path).with_suffix('.completion.json').stat().st_size
        require(set(observed)<=set(expected),'forecast outside immutable eligible cohort')
        if failure is None:require(observed==expected,'all eligible rows must be retained or explicitly failed')
        results.append(dict(target=target,method_id=m['method_id'],artifact=record['binding'],
            expected_rows=len(expected),forecast_rows=len(observed),operational_forecast_rows=valid,abstention_rows=len(observed)-valid,
            query_universe_rows=len(features),noneligible_role_rows=len(features)-len(view),eligible_roles=record['eligible_roles'],
            unissued_rows=len(expected)-len(observed),
            expected_offered_ids_sha256=digest(expected),unissued_offered_ids=expected[len(observed):],
            state='FAILED_RETAINED' if failure else 'CAPTURED' if expected else 'NO_ELIGIBLE_ROWS',failure=failure,
            original_shared_features=True,projection=projection['binding'],persistence=receipt))
    return dict(schema_version=VERSION+'-capture',models=results,counts=counts,
        serialized_forecast_receipt_bytes=retained,scientific_qualification=False,remote_durability='NOT_ESTABLISHED')


class BoundedOutput:
    """Additional new-namespace bound, including dedup aliases and failed writes.

    Every mutation still uses the original quota store under its global flock.
    Two MiB remain for complete per-offer failure/status and terminal controls.
    """
    RESERVE=2*1024*1024
    def __init__(self,storage,root,maximum):
        self.storage=storage;self.root=Path(root);self.maximum=maximum;self.unpublished=0
        require(self.RESERVE<maximum<=8*1024*1024,'finite8MiB namespace with failure-control reserve required')
    def used(self):return sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())+self.unpublished
    def write_bytes(self,path,body):
        path=Path(path);body=bytes(body)
        require(path.is_relative_to(self.root),'inference output outside registered namespace')
        reserve=0 if path.name=='FINISHED.json' else self.RESERVE
        with self.storage.transaction():
            require(not path.exists(),'immutable inference output already exists')
            require(self.used()+len(body)+reserve<=self.maximum,'new inference output byte ceiling; retain all partials')
            self.unpublished+=len(body)
            self.storage.write_bytes(path,body)
            self.unpublished-=len(body)
    def atomic_json(self,path,value):
        self.write_bytes(path,(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())
