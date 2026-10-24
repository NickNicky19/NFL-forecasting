"""Fixed startup materialization from immutable forecasts; no model/outcome API."""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

from .state import digest, utc, now_utc

VERSION = 'weekly-private-selected-policy-v1'
CUTOFF = '2026-10-24T12:00:00Z'
SLATE = '2026-REG-W07-remaining-initial-v1'
CHOICES = {**{t:'LAB_CDF' for t in ('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd')},
    'rush_att':'COUNT_A','rec':'COUNT_A','rec_yd':'CATBOOST_MEDIUM','rush_rec_yd':'CATBOOST_MEDIUM','anytime_td':'TD_EQUAL_CDF_CAT'}
PRODUCTS = {'count':('point_mean','expected_mean','MSE'), 'signed_integer':('point_median','intended_median','MAE'),
    'bernoulli':('binary_probability','event_probability','Brier')}
SAME = ('season','week','player_id','game_id','category','offered_id','position','team','opponent',
    'slate_id','horizon','kickoff_utc','cutoff_utc','source_cutoff_utc','weekly_decision_cutoff_utc',
    'query_source_sha256','schedule_source_sha256','identity_binding_sha256','source_policy_sha256',
    'source_capture_completed_at','startup_policy_sha256','startup_policy_registered_at','participation_state')


def require(condition, message):
    if not condition: raise ValueError(message)


class ReadBudget:
    """One shared semantic-read cap, including metadata and inflated JSONL."""
    def __init__(self, maximum=64*1024*1024):
        require(0<maximum<=64*1024*1024,'finite64MiB semantic-read cap required')
        self.maximum=maximum;self.bytes=0;self.rows=0

    def charge(self, size):
        require(size>=0 and self.bytes+size<=self.maximum,'semantic source-body cap exhausted; no truncation')
        self.bytes+=size

    @staticmethod
    def decode(body):
        def invalid(_): raise ValueError('nonfinite JSON number forbidden')
        return json.loads(body,parse_constant=invalid)

    def metadata(self, path):
        with Path(path).open('rb') as stream:body=stream.read(min(self.maximum-self.bytes+1,2*1024*1024+1))
        require(len(body)<=2*1024*1024,'metadata body exceeds2MiB')
        self.charge(len(body));return self.decode(body)

    def forecasts(self, path, expected_rows):
        result=[]
        with gzip.open(path,'rb') as stream:
            while True:
                body=stream.readline(32769)
                if not body:break
                require(len(body)<=32768 and body.endswith(b'\n'),'bounded complete JSONL row required')
                self.charge(len(body));self.rows+=1
                require(self.rows<=7672 and len(result)<expected_rows,'declared original row cap exceeded')
                row=self.decode(body);require(isinstance(row,dict),'forecast JSON object required');result.append(row)
        require(len(result)==expected_rows,'original completion row count differs; no prefix accepted')
        return result


def validate_metadata(policy,capture,catalog,readback,completions,*,policy_ref,now,strict_initial=True):
    require(capture['state']=='CURRENT_CANDIDATE_FORECASTS_LOCAL_READBACK' and capture['fatal'] is None,
        'successful immutable parent capture required')
    require(capture['startup_policy']==policy_ref and policy['schema_version']=='weekly-provisional-live-policy-v1'
        and policy['state']=='REGISTERED_STAGED_NOT_ACTIVATED','exact unactivated startup policy required')
    require(utc(policy['registered_at_utc'])==utc(capture['startup_policy_registered_at'])
        <=utc(capture['weekly_decision_cutoff_utc'])<=utc(capture['actual_completed_at'])<=now<utc(CUTOFF),
        'actual registered choice/capture/materialization clocks must precede cutoff')
    require(capture['input_cutoff_utc']==CUTOFF and policy['initial_input_deadline_utc']==CUTOFF
        and policy['initial_slate_id']==SLATE,'exact initial remaining W7 scope required')
    ready={c['category']:c for c in policy['categories'] if c['category']!='fantasy_ppr'}
    require({t:c['startup_method_id'] for t,c in ready.items()}==CHOICES,'prespecified eleven startup choices required')
    require(policy['TD_EQUAL_CDF_CAT']['members']=={'LAB_CDF':0.5,'CATBOOST_MEDIUM':0.5},'exact registered half/half TD mixture required')
    require(any(c['category']=='fantasy_ppr' and c['status']=='BLOCKED_EXACT_LABEL_CONTRACT' for c in policy['categories']),'PPR stays blocked')
    require(catalog['registered_at']==policy['registered_at_utc'] and catalog['scientific_qualification'] is False,
        'parent procedure catalog registration mismatch')
    slots={};expected_refs={}
    for entry in capture['capture']['models']:
        key=(entry['target'],entry['method_id']);require(key not in slots,'duplicate parent model slot')
        require(entry['state']=='CAPTURED' and entry['failure'] is None and entry['unissued_rows']==0,
            'complete original model attempt required; old failures never hidden')
        receipt=entry['persistence'];body=receipt['binding'];completion=completions[key]
        require(completion==receipt and receipt['state']=='PERSISTED' and receipt['rows']==entry['forecast_rows']==entry['expected_rows'],
            'exact original body completion required')
        require(utc(receipt['persist_started_at'])<=utc(receipt['completed_at'])<=utc(capture['actual_completed_at'])<utc(CUTOFF),
            'original body must actually complete before input cutoff')
        model=catalog['categories'][key[0]]['methods'][key[1]]
        require(model['model_version']==entry['artifact']['sha256'],'catalog model differs from original capture')
        slots[key]=entry;expected_refs[body['path']]=body
    require(sum(s['forecast_rows'] for s in slots.values())==capture['capture']['counts']['prediction_rows'],
        'broad parent coverage count differs')
    if strict_initial:
        expected={(t,'LAB_CDF') for t in CHOICES}|{(t,'COUNT_A') for t in ('rush_att','rec')}|{(t,'CATBOOST_MEDIUM') for t in ('pass_yd','rush_yd','rec_yd','rush_rec_yd','anytime_td')}
        require(set(slots)==expected and capture['capture']['counts']['prediction_rows']==7672 and capture['models_restored_once']==18,
            'exact broad7672-row eighteen-model parent required')
    require(readback['state']=='SAME_PROCESS_OWNED_IMMUTABLE_READBACK','original owned readback required')
    declared={r['path']:r for r in readback['body_and_receipt_refs']}
    require(all(declared.get(path)==ref for path,ref in expected_refs.items()),'parent body absent from owned readback')
    for target,choice in ready.items():
        category=catalog['categories'][target]
        require(category['primary_roles']==choice['initial_public_roles'] and category['product']==choice['output'],
            'registered initial role/product differs from original category')
    return slots


def decision(policy,catalog,slots,*,policy_ref,capture_ref,bridge_ref,materialization_started_at,startup_choice_at,source_capture_at,code_pins_sha256):
    categories={}
    for target,method in CHOICES.items():
        category=catalog['categories'][target]
        members={method:1.} if method!='TD_EQUAL_CDF_CAT' else {'LAB_CDF':0.5,'CATBOOST_MEDIUM':0.5}
        lineage=[]
        for member,weight in members.items():
            original=category['methods'][member];entry=slots[(target,member)]
            lineage.append(dict(method_id=member,weight=weight,model_version=original['model_version'],
                procedure_version=original['procedure_version'],forecast_body=entry['persistence']['binding'],
                original_persist_completed_at=entry['persistence']['completed_at'],projection=entry['projection']))
        model_version=digest(dict(category=target,members=[{k:m[k] for k in ('method_id','weight','model_version')} for m in lineage]))
        procedure_version=digest(dict(version=VERSION,policy_sha256=policy_ref['sha256'],category=target,method=method,
            code_pins_sha256=code_pins_sha256,
            members=[{k:m[k] for k in ('method_id','weight','procedure_version')} for m in lineage],
            roles=category['primary_roles'],product=category['product'],missing='NO_R0_PROVIDED_ABSTAIN_NO_RENORMALIZATION'))
        categories[target]=dict(method_id=method,model_version=model_version,procedure_version=procedure_version,
            members=lineage,primary_roles=category['primary_roles'],support=category['support'],product=category['product'])
    return dict(schema_version=VERSION+'-decision',policy_id='P2',policy_state='STARTUP_NO_COMPARABLE_LIVE_R0_EVIDENCE',
        code_pins_sha256=code_pins_sha256,
        materialization_started_at=materialization_started_at,startup_choice_at=startup_choice_at,
        shared_feature_persist_completed_at=source_capture_at,
        startup_policy_registered_at=policy['registered_at_utc'],startup_policy=policy_ref,parent_capture=capture_ref,
        identity_bridge=bridge_ref,categories=categories,R0='NOT_PROVIDED',historical_LAB_CDF_losses='NOT_LIVE_COMPARATORS',
        outcome_loss_score_reads=0,scientifically_qualified=False,actual_website_board_membership='NOT_YET_CHECKED',
        public_export_authorized=False,website_activation=False,private_only=True)


def identity_map(document):
    require(document['visible_board_match']=='NOT_YET_CHECKED' and document['name_matching'] is False,'unverified exact source bridge required')
    result={}
    for identity in document['identities']:
        require(identity['identity_binding_sha256']==digest({k:v for k,v in identity.items() if k!='identity_binding_sha256'}),
            'original canonical bridge digest differs')
        key=(identity['gsis_game_id'],identity['gsis_id'])
        require(key not in result and identity['actual_visible_board_compatibility']=='NOT_YET_CHECKED','duplicate or unverified bridge claim')
        result[key]=identity
    return result


def validate_row(row,slot,category,bridge,*,policy_ref,startup_choice_at):
    require(not {'actual','loss','label','brier','crps','log_score'}&set(row),'outcome/score fields forbidden in source forecast')
    require(row['category']==slot['target'] and row['method_id']==slot['method_id'] and row['season']==2026 and row['week']==7,
        'original target/model/season identity differs')
    method=category['methods'][row['method_id']];receipt=slot['persistence']
    require(row['model_version']==row['artifact_sha256']==method['model_version'] and row['procedure_version']==method['procedure_version'],
        'original model/procedure version differs')
    require(row['offered_id']==digest({k:row[k] for k in ('season','week','game_id','player_id','category')}),'canonical opportunity digest differs')
    expected=bridge.get((row['game_id'],row['player_id']))
    require(expected is not None and all(row.get(k)==v for k,v in expected.items()),'exact original GSIS/Sleeper/ESPN bridge differs')
    require(row['cutoff_utc']==row['source_cutoff_utc'] and utc(row['cutoff_utc'])==utc(CUTOFF)<utc(row['kickoff_utc'])
        and row['slate_id']==SLATE and row['evidence_lane']=='original_pregame' and row['horizon']=='player_game',
        'same-cutoff future-only original operational forecast required')
    require(utc(receipt['persist_started_at'])<=utc(row['issued_at'])<=utc(receipt['completed_at'])<utc(CUTOFF),
        'base issuance or completed persistence timing differs')
    require(row['startup_policy_sha256']==policy_ref['sha256'] and row['weekly_decision_cutoff_utc']==startup_choice_at
        and row['participation_state']=='unknown','original policy/unknown-participation lineage differs')
    require(row['source_projection_receipt']==slot['projection'],'original exact feature projection differs')
    require(utc(row['source_capture_completed_at'])<=utc(row['issued_at']) and utc(row['source_projection_receipt_completed_at'])<=utc(row['issued_at']),
        'source capture/projection follows original issuance')
    require((row['product'],row['prediction_functional'],row['metric'])==PRODUCTS[category['support']],
        'original point functional/metric differs')
    require(type(row['primary_role']) is bool and type(row['public_initial_scope_eligible']) is bool
        and row['primary_role']==(row['position'] in category['primary_roles'])
        and row['public_initial_scope_eligible']==(row['operational_eligible'] and row['primary_role']),
        'original initial-role/public flags differ')
    value=row['forecast_value']
    require(value is None or (type(value) in (float,int) and math.isfinite(value)
        and (category['support']!='count' or value>=0) and (category['support']!='bernoulli' or 0<=value<=1)),
        'unsupported original forecast; never clip/convert')
    require(row['operational_eligible']==(value is not None),'original operational eligibility differs from value')


def materialize(decision_doc,tables,catalog,bridge_doc,slots,*,policy_ref,clock=now_utc,progress=lambda:None):
    require(set(tables)==set(slots),'every declared parent body required, never silently shrink a category')
    bridge=identity_map(bridge_doc);by_target={t:{} for t in CHOICES};coverage={t:dict(parent_rows=0,excluded_initial_role=0,excluded_public_flag=0) for t in CHOICES}
    for key,rows in tables.items():
        slot=slots[key];category=catalog['categories'][key[0]];seen=set()
        for row in rows:
            validate_row(row,slot,category,bridge,policy_ref=policy_ref,startup_choice_at=decision_doc['startup_choice_at'])
            require(row['source_policy_sha256']==catalog['source_contract']['source_policy_sha256']
                and row['source_capture_completed_at']==decision_doc['shared_feature_persist_completed_at']
                and row['startup_policy_registered_at']==decision_doc['startup_policy_registered_at'],
                'exact original shared source capture/policy clock differs')
            require(row['offered_id'] not in seen,'duplicate source member opportunity');seen.add(row['offered_id'])
            opportunity=by_target[key[0]].setdefault(row['offered_id'],{})
            if opportunity:require(all(next(iter(opportunity.values()))[name]==row[name] for name in SAME),'member identity/cutoff/source lineage differs')
            opportunity[key[1]]=row;coverage[key[0]]['parent_rows']+=1
    selected=[]
    for target,opportunities in by_target.items():
        choice=decision_doc['categories'][target]
        for offered,parents in sorted(opportunities.items()):
            primary=[r for r in parents.values() if r['primary_role']]
            if not primary:coverage[target]['excluded_initial_role']+=1;continue
            eligible=[r for r in primary if r['public_initial_scope_eligible']]
            if not eligible:coverage[target]['excluded_public_flag']+=1;continue
            progress();base=eligible[0];issued=clock()
            require(utc(decision_doc['materialization_started_at'])<=issued<utc(CUTOFF),'actual selected issuance must precede cutoff')
            require(len(selected)<5000,'finite selected5000-row ceiling; never truncate')
            components=[];missing=[];value=0.;fallbacks=[]
            for member in choice['members']:
                row=parents.get(member['method_id']);valid=row is not None and row['public_initial_scope_eligible'] and row['operational_eligible']
                component=dict(member,forecast_row_sha256=digest(row) if row else None,
                    original_issued_at=row['issued_at'] if row else None,available=valid,
                    fallback_reason=row['fallback_reason'] if row else 'MISSING_COMPONENT')
                components.append(component)
                if not valid:missing.append(member['method_id'])
                else:
                    require(utc(row['issued_at'])<=issued,'selected issuance cannot precede a component')
                    value+=member['weight']*row['forecast_value']
                    if row['fallback_reason']:fallbacks.append(row['fallback_reason'])
            reason='NO_SAME_CUTOFF_R0_ABSTAIN_MISSING_COMPONENT:'+','.join(missing) if missing else ';'.join(fallbacks)
            if missing:value=None
            p,functional,metric=PRODUCTS[choice['support']]
            identity=bridge[(base['game_id'],base['player_id'])]
            chosen=parents.get(choice['members'][0]['method_id']) if len(components)==1 else None
            result={name:base[name] for name in SAME}
            result.update(identity,position=base['position'],method_id=choice['method_id'],model_version=choice['model_version'],
                procedure_version=choice['procedure_version'],product=p,prediction_functional=functional,metric=metric,
                forecast_value=value,issued_at=issued.isoformat(),materialized_at=issued.isoformat(),
                operational_eligible=value is not None,primary_role=True,public_initial_scope_eligible=value is not None,
                selected_initial_role_scope=True,fallback=bool(reason),fallback_reason=reason,components=components,
                policy_id='P2',policy_state=decision_doc['policy_state'],startup_choice_at=decision_doc['startup_choice_at'],
                decision_sha256=digest(decision_doc),evidence_lane='original_pregame',reference_stream='candidate',
                distribution_kind='BERNOULLI' if target=='anytime_td' and value is not None else
                    chosen.get('distribution_kind','NONE_POINT_ONLY') if chosen and value is not None else 'NONE_ABSTENTION',
                distribution_ref=chosen.get('distribution_ref') if chosen and value is not None else None,
                distribution_construction='REGISTERED_EQUAL_BERNOULLI_MIXTURE' if target=='anytime_td' else 'UNCHANGED_SELECTED_MEMBER_POINT',
                participation_state='unknown',conditional_on='played',scientific_qualification=False,
                calibration='UNESTABLISHED',
                publication_status='PRIVATE_PENDING_DURABILITY_AND_CONSUMER_ACCEPTANCE',public_export_authorized=False,
                actual_visible_board_compatibility='NOT_YET_CHECKED',website_activated=False)
            selected.append(result)
    require(len(selected)>0,'no initial selected offers; no success claim')
    return selected,dict(by_target=coverage,parent_forecast_rows=sum(len(v) for v in tables.values()),selected_rows=len(selected),
        selected_operational_rows=sum(r['operational_eligible'] for r in selected),abstentions=sum(not r['operational_eligible'] for r in selected),
        public_rows_exported=0,website_board_membership='NOT_YET_CHECKED',broad_private_population_retained=True)
