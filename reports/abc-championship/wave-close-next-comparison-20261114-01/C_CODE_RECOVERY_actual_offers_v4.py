"""Exact-line manual importer/evaluator. No collection, default lines or prices."""
import argparse,hashlib,json,math
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
from safe_models_v4 import law_load
from offer_validator_v2 import instant
from selection import point_side,probability_side,counts,brier
from contracts_v2 import grade
from coherence_v4 import state_for

TIERS={'AUTHENTICATED_PREGAME_CAPTURE','TIMING_UNVERIFIED_HISTORICAL_DIAGNOSTIC'}
PROBABILITY_TIE_TOLERANCE=1e-12 # registered selector v4.1; no actual offers graded before it

def probabilities(offer,forecast):
    if offer.get('record_kind')!='ACTUAL_OFFER':raise ValueError('SYNTHETIC_OR_HYPOTHETICAL_NOT_AN_ACTUAL_OFFER')
    law=law_load(forecast['law']);category=forecast['category']
    if category=='anytime_td':
        if offer.get('comparator')!='AT_LEAST_ONE_RUSH_REC_TD':raise ValueError('ANYTIME_EVENT_CONTRACT_MISMATCH')
        p=law.probability(.5)['over'];return dict(under=1-p,push=0.,over=p)
    line=offer.get('line')
    if not isinstance(line,(int,float)) or isinstance(line,bool) or not math.isfinite(line):raise ValueError('PROP_LINE_UNAVAILABLE_NO_SYNTHETIC_DEFAULT')
    if offer.get('comparator')=='STRICT_OVER_UNDER':return law.probability(line)
    if offer.get('comparator')=='AT_LEAST':
        k=int((Decimal(str(line))*law.scale).to_integral_value(rounding='ROUND_CEILING'));u=law.cdf(k-1)
        return dict(under=u,push=0.,over=1-u)
    raise ValueError('UNSUPPORTED_COMPARATOR')

def qualify(offer,forecast,cutoff,mode):
    reasons=[]
    for key in ['offer_id','venue','product','tier','player_id','game_id','category','period','scoring_contract_id','identity_evidence_reference','source_evidence_reference','lifecycle','offered_sides']:
        if offer.get(key) in [None,'',[]]:reasons.append('MISSING_'+key.upper())
    if offer.get('record_kind')!='ACTUAL_OFFER':reasons.append('NOT_ACTUAL_OFFER')
    if offer.get('lifecycle')!='OPEN':reasons.append('NOT_OPEN')
    if offer.get('period')!='FULL_GAME_INCLUDING_OT':reasons.append('PERIOD_CONTRACT_MISMATCH')
    for key in ['player_id','game_id','category','scoring_contract_id']:
        if offer.get(key)!=forecast.get(key):reasons.append('FORECAST_'+key.upper()+'_MISMATCH')
    try:same_kickoff=instant(offer.get('kickoff_UTC'))==instant(forecast.get('kickoff_UTC'))
    except (ValueError,TypeError):same_kickoff=False
    if offer.get('espn_event_id')!=forecast.get('espn_event_id') or not same_kickoff:reasons.append('EVENT_VERSION_OR_NATIVE_ID_MISMATCH')
    allowed=['YES'] if forecast['category']=='anytime_td' else ['OVER','UNDER']
    sides=offer.get('offered_sides',[])
    if not isinstance(sides,list) or not sides or len(sides)!=len(set(sides)) or any(x not in allowed for x in sides):reasons.append('UNSUPPORTED_OFFERED_SIDE')
    if offer.get('side_states')!={s:'OPEN' for s in sides}:reasons.append('SIDE_LIFECYCLE_UNKNOWN_OR_SUSPENDED')
    if mode=='PROSPECTIVE':
        try:
            observed=instant(offer['observed_at_UTC']);source=instant(offer['source_asof_UTC']);persisted=instant(offer['persisted_at_UTC'])
            if not source<=observed<=persisted<=cutoff:reasons.append('INVALID_OFFER_CLOCK_ORDER')
            if (cutoff-source).total_seconds()>900 or (cutoff-observed).total_seconds()>900:reasons.append('STALE_QUOTE')
            if not instant(forecast['generated_UTC'])<=cutoff<instant(forecast['kickoff_UTC']):reasons.append('NOT_FUTURE_AT_DECISION')
            if (instant(forecast['kickoff_UTC'])-cutoff).total_seconds()<=300:reasons.append('TOO_CLOSE_OR_STARTED')
        except (ValueError,KeyError,TypeError):reasons.append('OFFER_CLOCK_UNQUALIFIED')
    elif mode!='HISTORICAL_DIAGNOSTIC':reasons.append('INVALID_EVALUATION_MODE')
    if instant(forecast['information_cutoff_UTC'])>cutoff:reasons.append('FORECAST_FROM_AFTER_DECISION')
    if forecast.get('selection_availability')=='BLOCKED_OUT':reasons.append('OUT_OR_DOUBTFUL')
    if forecast.get('category')=='fpts' and forecast.get('readiness')=='EXPERIMENTAL_SHADOW_LABEL_COVERAGE':reasons.append('FANTASY_LABEL_COVERAGE_UNQUALIFIED_FOR_OFFERS')
    coherence=forecast.get('coherence_state') or state_for(forecast['forecast_id'])
    if coherence=='COMPLETION_ATTEMPT_CONTRADICTION':reasons.append('MARGINAL_COHERENCE_FAILURE')
    if forecast['category'] in ['pass_cmp','pass_att'] and coherence=='CROSS_STATISTIC_COHERENCE_UNCHECKED':reasons.append(coherence)
    try:probabilities(offer,forecast)
    except (ValueError,AssertionError,KeyError,TypeError) as e:reasons.append(str(e))
    return sorted(set(reasons))

def evaluate(offer,forecast,cutoff,mode='PROSPECTIVE'):
    if offer.get('record_kind')!='ACTUAL_OFFER':raise ValueError('SYNTHETIC_OR_HYPOTHETICAL_NOT_AN_ACTUAL_OFFER')
    reasons=qualify(offer,forecast,cutoff,mode)
    base=dict(offer_id=offer.get('offer_id'),forecast_id=forecast['forecast_id'],player_id=forecast['player_id'],game_id=forecast['game_id'],category=forecast['category'],line=offer.get('line'),venue=offer.get('venue'),product=offer.get('product'),tier=offer.get('tier'),comparator=offer.get('comparator'),offered_sides=offer.get('offered_sides'),observation_UTC=offer.get('observed_at_UTC'),source_asof_UTC=offer.get('source_asof_UTC'),decision_UTC=cutoff.isoformat(),kickoff_UTC=forecast['kickoff_UTC'],model_id=forecast.get('model_id'),scoring_contract_id=forecast['scoring_contract_id'],appearance_conditioning=forecast.get('appearance_conditioning'),book_settlement='UNVERIFIED',evidence_tier='PREGAME_EXACT_LINE_CANDIDATE_AWAITING_SERVER_PROOF' if mode=='PROSPECTIVE' else 'TIMING_UNVERIFIED_HISTORICAL_DIAGNOSTIC',record_kind='ACTUAL_OFFER',price=offer.get('prices'),selection_receipt_state='AWAITING_GITHUB_SERVER_PROOF',paper_only=True,reason=reasons)
    if reasons:return base|dict(state='UNAVAILABLE_NOT_ABSTENTION',p_under=None,p_push=None,p_over=None,P1_side=None,P2_side=None)
    p=probabilities(offer,forecast);direction='ABSTAIN' if abs(p['over']-p['under'])<=PROBABILITY_TIE_TOLERANCE else probability_side(**p);sides=offer['offered_sides'];event=forecast['category']=='anytime_td'
    if event:direction='YES' if p['over']>.5+PROBABILITY_TIE_TOLERANCE else 'ABSTAIN'
    elif direction not in sides:direction='ABSTAIN'
    point=None if event else point_side(forecast.get('median'),offer['line'])
    if point not in sides and point not in [None,'ABSTAIN','UNAVAILABLE']:point='ABSTAIN'
    # AT_LEAST uses its explicit winning event; the strict P1 rule is inapplicable.
    if offer['comparator']=='AT_LEAST':point=None
    return base|dict(state='EXPERIMENTAL_CONDITIONAL_PAPER_CANDIDATE',selector_id='P2_EXACT_LINE_SELECTOR-v4.1',probability_tie_tolerance=PROBABILITY_TIE_TOLERANCE,p_under=p['under'],p_push=p['push'],p_over=p['over'],P1_side=point,P2_side=direction,median=forecast.get('median'),mean=forecast.get('mean'),eventual_outcome=None)

def reconcile(rows,outcomes):
    """Statistical grading only; source outcome and appearance qualification is upstream."""
    if any(r.get('record_kind')!='ACTUAL_OFFER' or r.get('evidence_tier') not in TIERS for r in rows):raise ValueError('SYNTHETIC_ROWS_FORBIDDEN_IN_ACTUAL_OFFER_RESULTS')
    result={}
    for method in ['P1','P2']:
        judged=[]
        for r in rows:
            a=outcomes.get((r['game_id'],r['player_id'],r['category']));side=r.get(method+'_side');state='PENDING' if a is None else a['appearance'];actual=None if a is None else a.get('actual')
            if side in [None,'UNAVAILABLE']:status='UNAVAILABLE'
            elif side=='ABSTAIN':status='ABSTAIN'
            elif r['comparator']=='AT_LEAST' and state=='PLAYED' and actual is not None:status='WIN' if (actual>=r['line'])==(side=='OVER') else 'LOSS'
            elif r['comparator']=='AT_LEAST_ONE_RUSH_REC_TD':status=grade(actual,.5,'OVER',state)
            else:status=grade(actual,r['line'],side,state)
            judged.append(dict(side='OVER' if side=='YES' else side,grade=status))
        c=counts(judged);c['eligible_offers']=len(rows);c['unavailable']=sum(r['grade']=='UNAVAILABLE' for r in judged);c['abstentions']=sum(r['grade']=='ABSTAIN' for r in judged)
        c['other_states']={s:sum(r['grade']==s for r in judged) for s in sorted({r['grade'] for r in judged}-{'WIN','LOSS','UNAVAILABLE','ABSTAIN'})};result[method]=c
    return result

def import_packet(path,rights_path,forecasts,cutoff,output,mode='PROSPECTIVE'):
    b=path.read_bytes();rights=json.loads(rights_path.read_text())
    if rights.get('export_SHA256')!=hashlib.sha256(b).hexdigest() or rights.get('public_retention_qualified') is not True or not rights.get('upstream_permission_evidence_reference'):raise ValueError('EXACT_EXPORT_RIGHTS_REVIEW_REQUIRED')
    packet=json.loads(b);assert packet['schema']=='C-ACTUAL-OFFERS-v4'
    if mode=='PROSPECTIVE' and cutoff>datetime.now(timezone.utc):raise ValueError('DECISION_FROM_FUTURE')
    index={(r['game_id'],r['player_id'],r['category']):r for r in forecasts}
    if len(index)!=len(forecasts):raise ValueError('DUPLICATE_FORECAST_KEYS_SELECT_DECLARED_SNAPSHOT_FIRST')
    seen={};rows=[]
    for o in packet['offers']:
        if o.get('record_kind')!='ACTUAL_OFFER':raise ValueError('SYNTHETIC_OR_HYPOTHETICAL_NOT_AN_ACTUAL_OFFER')
        key=(o.get('venue'),o.get('product'),o.get('offer_id'));encoded=json.dumps(o,sort_keys=True)
        if key in seen:
            if seen[key]!=encoded:raise ValueError('CONFLICTING_LIFECYCLE_OR_QUOTE')
            continue
        seen[key]=encoded;f=index.get((o.get('game_id'),o.get('player_id'),o.get('category')))
        if f:rows.append(evaluate(o,f,cutoff,mode))
        else:rows.append({k:o.get(k) for k in ['offer_id','player_id','game_id','category','period','line','comparator','venue','product','tier','offered_sides','observed_at_UTC','source_asof_UTC','source_evidence_reference','identity_evidence_reference','scoring_contract_id']}|dict(state='NO_MATCHED_FORECAST',record_kind='ACTUAL_OFFER',P1_side=None,P2_side=None,reason=['EXACT_FORECAST_IDENTITY_UNAVAILABLE']))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump(dict(schema='C-EXACT-OFFER-EVALUATION-v4',source_SHA256=hashlib.sha256(b).hexdigest(),rights_review_id=rights.get('id'),decision_UTC=cutoff.isoformat(),mode=mode,rows=rows,real_selections_persisted=False),f,separators=(',',':'),allow_nan=False)
    return rows

if __name__=='__main__':
    import gzip
    p=argparse.ArgumentParser();p.add_argument('--offers',type=Path,required=True);p.add_argument('--rights-review',type=Path,required=True);p.add_argument('--forecasts',type=Path,required=True);p.add_argument('--cutoff',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=['PROSPECTIVE','HISTORICAL_DIAGNOSTIC'],default='PROSPECTIVE');a=p.parse_args()
    data=a.forecasts.read_bytes();rows=json.loads(gzip.decompress(data) if a.forecasts.suffix=='.gz' else data);import_packet(a.offers,a.rights_review,rows,instant(a.cutoff),a.output,a.mode)
