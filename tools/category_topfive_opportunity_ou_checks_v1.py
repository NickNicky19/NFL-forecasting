"""Fictional software cases only; no NFL data, model, source or network access."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys
from decimal import Decimal


def main():
    p=argparse.ArgumentParser();p.add_argument('--scorer',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    source=Path(a.scorer);body=source.read_bytes();spec=importlib.util.spec_from_file_location('fictional_ou',source);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
    out=Path(a.out);assert not out.exists();cases=[]
    def case(name,check):
        assert check(), name
        cases.append(name)
    def d(side='over',line='1.5',point='2',**extra):
        return dict(game_id='fictional-game',week=1,opportunity_id='fictional-opportunity',line=line,point=point,selected_side=side,conditional_p_over=None,p_over=None,p_under=None,p_push=None,**extra)
    case('half_integer_over',lambda:s.grade(d(),'2','supported_played')['direction_result']=='CORRECT')
    case('half_integer_under',lambda:s.grade(d(side='under',point='1'),'1','supported_played')['direction_result']=='CORRECT')
    case('integer_push_distinct_from_hit',lambda:s.grade(d(line='2'),'2','supported_played')['direction_result']=='PUSH_STATISTIC')
    case('equal_point_abstains',lambda:s.point_side('2','2')==(None,'POINT_EQUALS_LINE_ABSTAIN'))
    case('no_epsilon_tie_or_rounding',lambda:s.point_side('2.0000000000000001','2')[0]=='over')
    case('DNP_not_zero',lambda:s.grade(d(),None,'known_DNP_void')['actual_direction'] is None)
    case('unknown_not_zero',lambda:s.grade(d(),None,'unknown_participation')['direction_result']=='UNRESOLVED')
    case('played_missing_not_zero',lambda:s.grade(d(),None,'played_missing_or_invalid_statistic')['actual_direction'] is None)
    case('genuine_played_zero_retained',lambda:s.grade(d(side='under',line='.5',point='0'),'0','supported_played')['direction_result']=='CORRECT')
    case('early_exit_still_scored',lambda:s.grade(d(side='over',line='4.5',point='6'),'1','supported_played')['direction_result']=='INCORRECT')
    case('missing_point_abstains',lambda:s.point_side(None,'2')[0] is None)
    case('strict_and_inclusive_tolerance_differ',lambda:s.grade(d(point='2'),'3','supported_played')['strict_error_lt1'] is False and s.grade(d(point='2'),'3','supported_played')['inclusive_error_le1'] is True)
    case('missing_price_no_EV',lambda:s.estimated_ev('.6','.4',None) is None)
    case('zero_odds_rejected',lambda:s.decimal_from_american('0') is None)
    case('sentinel_odds_quarantined',lambda:s.decimal_from_american('-100000') is None)
    case('American_150_decimal',lambda:s.decimal_from_american('150')==Decimal('2.5'))
    case('push_mass_preserved',lambda:s.law('.4','.3','.3')['push']==Decimal('.3'))
    case('invalid_law_rejected',lambda:s.law('.7','.7','0') is None)
    case('zero_decisive_mass_abstains',lambda:s.law_side('0','0','1')==(None,'ZERO_DECISIVE_MASS_ABSTAIN'))
    case('conditional_probability_tie_abstains',lambda:s.conditional_side('.5')[0] is None)
    case('impossible_log_loss_retained',lambda:s.log_score('0')['state']=='POSITIVE_INFINITY')
    case('half_line_complementary_probability',lambda:s.law('.7','.3','0')['over']+s.law('.7','.3','0')['under']==1)
    contract='EXPLORATORY_ASSUMED_REFUND_PUSH_VOID_ACTUAL_BOOK_UNQUALIFIED'
    case('assumed_push_refund',lambda:s.assumed_settlement('over','2','2','supported_played','1.9',contract)==(Decimal(0),'assumed_push_refund'))
    case('DNP_assumed_void_not_statistical_hit',lambda:s.assumed_settlement('over',None,'2','known_DNP_void','1.9',contract)==(Decimal(0),'assumed_DNP_void_refund'))
    case('unqualified_contract_not_authenticated_settlement',lambda:s.assumed_settlement('over','3','2','supported_played','1.9','UNKNOWN')[0] is None)
    case('EV_with_push_mass',lambda:s.estimated_ev('.4','.3','2')==Decimal('.1'))
    original=d(line='4.5',point='5');before=s.grade(original,'5','supported_played');after=s.grade(original,'4','supported_played')
    case('outcome_correction_retains_forecast_and_old_grade',lambda:before['direction_result']=='CORRECT' and after['direction_result']=='INCORRECT' and before['point']==after['point']=='5' and original.get('actual') is None)
    case('changed_line_is_separate_opportunity',lambda:s.point_side('5','4.5')[0]=='over' and s.point_side('5','5.5')[0]=='under')
    zero=d();zero['conditional_p_over']='0';finite=d();finite['conditional_p_over']='.5'
    summary=s.summarize([s.grade(zero,'2','supported_played'),s.grade(finite,'2','supported_played')])
    case('summary_retains_infinite_logloss_denominator',lambda:summary['log_loss_decisive']['state']=='POSITIVE_INFINITY' and summary['log_loss_decisive']['denominator']==2 and summary['log_loss_decisive']['impossible_events']==1)
    push=d(line='2');push.update(p_over='.4',p_under='.3',p_push='.3',conditional_p_over=str(Decimal(4)/7))
    push_summary=s.summarize([s.grade(push,'2','supported_played')])
    case('push_full_statistic_score_separate_from_decisive',lambda:push_summary['Brier_rows']==0 and push_summary['full_statistic_Brier_rows']==1 and abs(push_summary['full_statistic_Brier']-.74)<1e-15)
    abstain=d(side=None);abstain['conditional_p_over']='.5'
    cover=s.summarize([s.grade(abstain,'2','supported_played'),s.grade(d(),None,'unknown_participation')])
    case('abstention_unknown_and_probability_coverage',lambda:cover['offered_decisions']==2 and cover['supported_statistic_rows']==1 and cover['counts']=={'ABSTAIN':1,'UNRESOLVED':1} and cover['decisive_selected_denominator']==0 and cover['Brier_rows']==1 and cover['statistical_status_counts']=={'CORRECT':0,'INCORRECT':0,'PUSH_STATISTIC':0,'ABSTAIN':1,'UNRESOLVED':1} and cover['book_settlement_counts']=={'WIN':0,'LOSS':0,'PUSH':0,'VOID':0,'PENDING':0,'UNRESOLVED':1,'ABSTAIN':1} and cover['by_selected_side']['over']['unresolved']==1 and cover['by_selected_side']['over']['incorrect']==0 and cover['by_selected_side']['under']['book_settlement_counts']=={'WIN':0,'LOSS':0,'PUSH':0,'VOID':0,'PENDING':0,'UNRESOLVED':0,'ABSTAIN':0})
    paired=s.paired([s.grade(d(),'2','supported_played')],[s.grade(d(side='under'),'2','supported_played')])
    case('paired_direction_difference_and_cluster_floor',lambda:paired['paired_rows']==1 and paired['candidate_minus_control']==-1 and paired['clusters']==1 and paired['nominal95_interval'] is None)
    r={'state':'PASS','cases':len(cases),'case_names':cases,'scorer_sha256':hashlib.sha256(body).hexdigest(),'NFL_rows_models_fits_HTTP_CAS':0,'kind':'ONE_FICTIONAL_SOFTWARE_SUITE_NOT_FORECASTING_EXPERIMENTS'}
    out.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n');print(json.dumps(r,sort_keys=True))


if __name__=='__main__':main()
