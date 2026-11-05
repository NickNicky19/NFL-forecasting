"""Synthetic clock/typing/week-floor checks; zero NFL observations or fits."""
from pathlib import Path
import copy
import datetime
import importlib.util
import json
import os
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    start=time.process_time();checks=[]
    import numpy as np,pandas as pd
    from nfl_lab import count_a_mean_export_adapter_v1 as adapter
    from nfl_lab.product_test_week_floor_v1 import evaluate,require_primary
    corrector_path=ROOT/'tools/modern_count_a_mean_v3.py'
    spec=importlib.util.spec_from_file_location('synthetic_original_mean_corrector',corrector_path);fix=importlib.util.module_from_spec(spec);spec.loader.exec_module(fix)
    class SyntheticModel:
        category={'target':'pass_td','support':'count','panels':{'base':['f_player_games_prior']}}
        variant='A'
        priors={'QB':SimpleNamespace(support='count',q=.2,n=20,mean=1.8)}
        global_prior=None
        def __init__(self):self.calls=0
        def predict(self,frame):
            self.calls+=1
            return np.array([1.88 if x>0 else 1. for x in frame.f_player_games_prior]),np.array([''if x>0 else'cold_start_role_prior'for x in frame.f_player_games_prior])
    frame=pd.DataFrame([{'season':2026,'week':9,'game_id':'SYNTHETIC_ONLY','player_id':'SYNTHETIC_'+str(i),
        'team':'SYNTHETIC','opponent':'SYNTHETIC','position':'QB','kickoff_utc':'2026-11-06T01:15:00+00:00',
        'cutoff_utc':'2026-11-05T19:15:00+00:00','feature_max_source_available_utc':'2026-11-04T00:00:00+00:00',
        'f_player_games_prior':n}for i,n in enumerate([5,0])])
    binding={'model_sha256':adapter.MODEL,'parent_procedure_version':'9c48aab650f35a60631fd5d6af2cef4b8c513416fe0f9b2c61591d7f8af4b85f','training_cutoff_utc':'2026-09-01T00:00:00+00:00'}
    model=SyntheticModel();out=adapter.predict_verified_mean(model,frame,mean_corrector=fix.correct_fallbacks,binding=binding)
    assert out.expected_mean.tolist()==[1.88,1.8] and out.legacy_point_for_audit_only.tolist()==[1.88,1.]
    assert out.issued_at_UTC.isna().all()and out.probability.isna().all()and out.EV.isna().all()
    checks.append('original trained-prior mean correction, fractional warm mean, separate legacy/probability/issuance')
    mutated=frame.assign(actual=[99999,-99999],pass_td=[99999,-99999]);again=adapter.predict_verified_mean(SyntheticModel(),mutated,mean_corrector=fix.correct_fallbacks,binding=binding)
    assert np.array_equal(out.expected_mean.to_numpy(),again.expected_mean.to_numpy());checks.append('target-outcome mutation cannot alter typed means')
    for label,col,value in [('missing kickoff','kickoff_utc',None),('missing cutoff','cutoff_utc',None),
                            ('cutoff after kickoff','cutoff_utc','2026-11-07T00:00:00+00:00'),
                            ('feature after cutoff','feature_max_source_available_utc','2026-11-06T00:00:00+00:00'),
                            ('unknown warm source clock','feature_max_source_available_utc',None)]:
        bad=frame.copy();bad[col]=value;m=SyntheticModel()
        try:adapter.predict_verified_mean(m,bad,mean_corrector=fix.correct_fallbacks,binding=binding)
        except ValueError:assert m.calls==0;checks.append(label+' rejected before prediction')
        else:raise AssertionError(label)
    key={'procedure_version':'SYNTHETIC','target':'rec','output':'median','role_scope':['WR'],'selection_policy':'P1','history_rule':'EARLIER_ONLY'}
    rows=[{'key':key,'season':2026,'week':w,'completed_outcomes':True,'scored_eligible_cases':10}for w in range(1,8)]
    assert evaluate(key,rows)['completed_scored_week_count']==7;checks.append('seven distinct scored weeks counted')
    assert evaluate(key,[rows[0]]*5)['completed_scored_week_count']==1;checks.append('five repeats/folds from one week count once')
    empty=[{**r,'scored_eligible_cases':0}for r in rows];assert evaluate(key,empty)['five_week_floor']=='NOT_MET';checks.append('zero-selection or unresolved weeks do not pass')
    other=copy.deepcopy(key);other['output']='mean';assert evaluate(key,[{**r,'key':other}for r in rows])['completed_scored_week_count']==0;checks.append('different output cannot lend weeks')
    other=copy.deepcopy(key);other['selection_policy']='NEW_GATE';assert evaluate(key,[{**r,'key':other}for r in rows])['completed_scored_week_count']==0;checks.append('new selector cannot inherit old weeks')
    try:require_primary(key,rows[:4])
    except ValueError:checks.append('four-week primary rejected; shadow remains permitted by policy')
    else:raise AssertionError('four week primary admitted')
    mixed=rows[:4]+[{**rows[0],'season':2025}];assert evaluate(key,mixed)['completed_scored_week_count']==5;checks.append('season/week pairs distinct without pretending current-season-only validation')
    # New typed-core mean to the already pinned common selection/grading path.
    cache=Path(os.environ['ABC_C_CODE_CACHE']);sys.path.insert(0,str(cache));import abc_championship_v2 as common
    point=float(out.expected_mean.iloc[0]);assert point==1.88 and common.a.point_side(point,1.5)=='OVER'
    for side,expected in [('OVER',['LOSS','LOSS','WIN','WIN']),('UNDER',['WIN','WIN','LOSS','LOSS'])]:
        assert [common.status({'selected_side':side,'actual':y,'line':1.5,'appearance':'PLAYED','status':'WIN','comparator':'STRICT_OVER_UNDER'})for y in [0,1,2,3]]==expected
    checks.append('typed fractional passing-TD mean and actual integer1.5 thresholds; no rounded probability')
    for line,y,side,status in [(4.5,4,'UNDER','WIN'),(4.5,5,'OVER','WIN'),(19.5,19,'UNDER','WIN'),(19.5,20,'OVER','WIN'),(5.,5,'OVER','PUSH'),(-4.5,-5,'UNDER','WIN'),(17.5,17.75,'OVER','WIN')]:
        assert common.status({'selected_side':side,'actual':y,'line':line,'appearance':'PLAYED','status':'WIN','comparator':'STRICT_OVER_UNDER'})==status
    checks.append('receptions/completions/integer push/signed yards/fractional-score statistical comparisons')
    result={'state':'PASS_SYNTHETIC_SOFTWARE_ONLY','asof_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,
        'software_check_groups':len(checks),'CPU_seconds':time.process_time()-start,
        'new_NFL_observations_fits_model_deserializations':0,'scientific_qualification_or_deployment':'NOT_ESTABLISHED_BY_SOFTWARE_CHECKS'}
    (ROOT/'reports/abc-championship/post-wave-5w-v1/SOFTWARE_CHECKS_V1.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
