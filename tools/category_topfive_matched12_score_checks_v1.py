"""One finite fictional functional suite; never opens retained NFL artifacts."""
import importlib.util,json,math,pathlib,resource,signal,time
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('matched12',ROOT/'tools/category_topfive_matched12_score_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def main():
 start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(10,11));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2);signal.alarm(20);cases=[]
 def check(name,condition):
  assert condition,name;cases.append(name)
 def rejects(name,call):
  try:call()
  except ValueError:cases.append(name);return
  raise AssertionError(name)
 def row(target='rec',prediction=1.88,actual=2.,state='played',method='CDF_MEAN',product='mean'):
  return dict(target=target,season=2026,week=1,game_id='fictional-game',player_id='fictional-player',team='A',opponent='B',position='WR',cutoff_utc=pd.Timestamp('2026-09-01',tz='UTC'),kickoff_utc=pd.Timestamp('2026-09-02',tz='UTC'),prediction=prediction,actual=actual,participation_state=state,method=method,product=product,fallback='')
 cfg={x:{'procedure_id':'LEAF_CDF','procedure_version':'fictional-v1','shortlist_group':'LEAF_CDF'} for x in ['CDF_MEAN','CDF_MEDIAN']}
 scope=dict(identity_namespace='FICTIONAL',source_policy_id='FICTIONAL',outcome_version='FICTIONAL',evidence_tier='FICTIONAL',seasons=[2026],weeks=[1],targets=['rec'],reference_output={'rec':['CDF_MEAN','mean']},primary_core_outputs={'rec':[['CDF_MEAN','mean'],['CDF_MEDIAN','median']]})
 f=m.normalize(pd.DataFrame([row(),row(prediction=2.,method='CDF_MEDIAN',product='median')]),scope,{'rec':cfg})
 check('mean_median_one_procedure',f.procedure.nunique()==1)
 s=m.metrics(f.iloc[:1],'rec');check('native_MAE',math.isclose(s['MAE'],.12));check('fractional_mean_not_exact_count',s['exact_count']['value'] is None)
 check('unrounded_integer_exact_count',m.metrics(f.iloc[1:],'rec')['exact_count']['value']==1)
 z=pd.DataFrame([row(actual=np.nan,state='unknown')]);check('unknown_not_zero',m.metrics(z,'rec')['scored']==0)
 rejects('count_actual_integer_support',lambda:m.normalize(pd.DataFrame([row(actual=1.5)]),scope,{'rec':cfg}))
 rejects('duplicate_output_key',lambda:m.normalize(pd.DataFrame([row(),row()]),scope,{'rec':cfg}))
 summary,_=m.score_panel(f,scope,{'rec':cfg},{'seed':1703,'replicates':5,'minimum_clusters':2});check('full_core_pairwise_present',len(summary['records'])==4 and len(summary['pairwise'])==2)
 atd=m.metrics(pd.DataFrame([row(target='anytime_td',prediction=.7,actual=1.,product='probability')]),'anytime_td');check('ATD_not_numeric_MAE',atd['MAE'] is None and atd['RMSE'] is None);check('ATD_MSE_is_Brier',math.isclose(atd['MSE'],.09))
 contract={'identity_namespace':'FICTIONAL','forecast_identity_namespace':'FICTIONAL'}
 def p1(target,p,y,line):
  frame=pd.DataFrame([row(target,p,y)]);offer=frame[m.ID+['cutoff_utc']].copy();offer['line']=line;offer['evidence_tier']='FICTIONAL';offer['primary_offer_policy']='FICTIONAL';offer['statistical_contract']='FICTIONAL'
  return m.point_sides(frame,offer,contract).iloc[0]
 for name,target,p,y,line,side,result in [('half_over','pass_td',1.88,2,1.5,'over','WIN'),('half_under','pass_td',1.12,2,1.5,'under','LOSS'),('point_tie','rec',4.5,5,4.5,'abstain','ABSTAIN'),('integer_push','rec',1.88,2,2,'under','PUSH'),('signed_yards','rush_yd',-4,-3,-1.5,'under','WIN'),('chart_fractional_push','chart_ppr',2,1.9400000000000002,1.94,'over','PUSH')]:
  r=p1(target,p,y,line);check(name,r.selected_side==side and r.statistical_result==result)
 def p2(line=4.5,y=5.,p=(.6,.4,0.)):
  r=row(actual=y);r.update(line=line,p_over=p[0],p_under=p[1],p_push=p[2],participation_contract='FICTIONAL_PLAYED',law_version='FICTIONAL_DISCRETE_LAW');return pd.DataFrame([r])
 check('probability_half_over',m.probability_sides(p2()).iloc[0].statistical_result=='WIN')
 rejects('half_integer_no_push_mass',lambda:m.probability_sides(p2(p=(.5,.4,.1))))
 impossible=m.offered_probability_metrics(p2(p=(0.,1.,0.)));check('infinite_logloss_retained',impossible['n']==1 and impossible['log_loss']['state']=='POSITIVE_INFINITY' and impossible['log_loss']['positive_infinite_rows']==1)
 pushes=m.offered_probability_metrics(p2(5.,5.,(.2,.5,.3)));check('three_outcome_push_Brier',math.isclose(pushes['Brier'],.78) and pushes['push_outcomes']==1)
 x=p2();x['target']='anytime_td';rejects('ATD_not_numeric_threshold',lambda:m.probability_sides(x))
 check('unknown_clock_phenotype',m.metrics(pd.DataFrame([dict(row(),cutoff_utc=pd.NaT)]),'rec')['clock_phenotypes']['cutoff_only_unknown']==1)
 rejects('known_naive_clock_not_UTC_fabricated',lambda:m.metrics(pd.DataFrame([dict(row(),cutoff_utc=pd.Timestamp('2026-09-01'))]),'rec'))
 out={'version':'matched12-score-fictional-v1','state':'PASS','cases':cases,'case_count':len(cases),'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'NFL_decode_fits_forecasts_network_CAS':0};signal.alarm(0)
 p=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/scoring/FICTIONAL_RESULT_V1_1.json'
 with p.open('x') as h:json.dump(out,h,sort_keys=True);h.write('\n')
 print(json.dumps(out))
if __name__=='__main__':main()
