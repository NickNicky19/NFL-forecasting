"""Invented aggregate transport and exact pre-data GO rejection checks only."""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json
import resource
import sys
import time
from unittest.mock import patch


def main():
    started=time.monotonic();cpu=time.process_time()
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--go',required=True);a=p.parse_args()
    raw=Path(a.plan).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.sha256
    plan=json.loads(raw);go=json.loads(Path(a.go).read_bytes())
    assert plan['state']=='ROOT_AND_REVIEWER_SEALED' and plan['execution_authorized'] is True
    assert go=={'state':'GO','registered_by':'/root','scope':'TOP_PLAYER_FICTIONAL_SHAPE_ONLY','plan_sha256':a.sha256}
    assert plan['resources']=={'CPU_seconds':12,'wall_seconds':20,'RSS_bytes':134217728,'NFL_decodes':0,'model_loads':0,'fits':0,'CAS_calls':0,'network':0,'invocations':1,'receipt_bytes':8192}
    out=Path(plan['output']);assert not out.exists()
    resource.setrlimit(resource.RLIMIT_CPU,(12,13))
    attempts=[]
    def deny(event,args):
        if event.startswith('socket.') or event in ['subprocess.Popen','os.system','os.fork','os.posix_spawn']:
            attempts.append(event);raise RuntimeError('offline fictional check')
    sys.addaudithook(deny)
    ref=plan['worker'];b=Path(ref['path']).read_bytes();assert len(b)==ref['bytes'] and hashlib.sha256(b).hexdigest()==ref['sha256']
    spec=importlib.util.spec_from_file_location('fictional_top_worker',ref['path']);worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    fictional={'version':worker.VERSION,'resources':worker.CAPS,'state':'ROOT_AND_REVIEWER_SEALED','execution_authorized':True,'review':'PREEXEC_PASS'}
    body=json.dumps(fictional).encode();h=hashlib.sha256(body).hexdigest()
    good={'state':'GO','registered_by':'/root','independent_review':'PASS','scope':worker.VERSION,'plan_sha256':h}
    rejected=0
    for field in good:
        bad={k:v for k,v in good.items() if k!=field}
        def read_bytes(path):
            if str(path)=='/fictional-plan':return body
            if str(path)=='/fictional-go':return json.dumps(bad).encode()
            raise AssertionError('unexpected source access after malformed GO')
        def read_text(path,*args,**kwargs):
            if str(path)=='/fictional-go':return json.dumps(bad)
            raise AssertionError('unexpected source access after malformed GO')
        with patch.object(sys,'argv',['worker','--plan','/fictional-plan','--sha256',h,'--go','/fictional-go']),patch.object(Path,'read_bytes',read_bytes),patch.object(Path,'read_text',read_text):
            try:worker.main()
            except ValueError as error:
                assert 'GO required before NFL decode' in str(error);rejected+=1
            else:raise AssertionError('incomplete GO admitted')
    records=[]
    for i in range(6216):
        n=1+i%211;mae=(i%1900+1)/(i%37+1);mse=mae*mae+((i*13)%91)/17
        metrics={'planned':n+3,'scored':n,'players':min(n,20),'games':min(n,93),'weeks':min(n,6),
            'outcome_states':{'played':n,'unknown':3},'played_missing':0,'played_zero':i%13,
            'fallback_planned':i%11,'fallback_scored':i%7,'rank_unavailable_planned':i%5,
            'original_forecast_clock_unknown':i%3,'MAE':mae,'MSE':mse,'RMSE':mse**.5,
            'bias':mae/3-2,'p90_AE':mae*1.7,'p95_AE':mae*2.1,'absolute_error_sum':mae*n,
            'tolerance':1,'strict_within':(i%101)/101,'inclusive_within':(i%100)/100,
            'probability_scores':None,'authentic_offer_side_or_close_and_correct':'UNAVAILABLE_NO_MATCHED_AUTHENTIC_LINES',
            'actual_prop_offered_population':'UNAVAILABLE_NOT_GENERIC_QUERY_POOL'}
        if i%11==0:
            metrics['probability_scores']={'Brier':(i%71)/91,'log_loss':{'state':'POSITIVE_INFINITY' if i%22==0 else 'FINITE','value':None if i%22==0 else .456789012345678,'positive_infinite_rows':1 if i%22==0 else 0},'reliability':[{'lower':j/10,'upper':(j+1)/10,'n':j+1,'mean_probability':(j+.5)/10,'event_rate':((i+j)%101)/101} for j in range(10)]}
        records.append({'target':worker.TARGETS[i%12],'position':['QB','RB','WR','TE','FB'][i%5],
            'group':worker.GROUPS[i%9],'period':'2026_W1_6' if i%7==0 else '2026_W'+str(i%6+1),
            'method':['CDF_MEAN','CDF_MEDIAN','CATBOOST_MEDIUM','COUNT_A_MEAN','HGB_CHART_MEDIAN_V1'][i%5],
            'product':['mean','median','median_objective_point','probability'][i%4],'metrics':metrics})
    contrasts=[{'target':worker.TARGETS[i%12],'position':['QB','RB','WR','TE','FB'][i%5],
        'group':worker.GROUPS[i%9],'candidate':'CDF_MEDIAN','control':'CATBOOST_MEDIUM','loss':'MAE',
        'cross_product_point_diagnostic':False,'paired_rows':i%211,'candidate_loss':(i%71)/11,
        'control_loss':(i%83)/13,'candidate_minus_control':(i%37)/17,'improvement_percent':(i%79)/31,
        'intervals':{'game_id':{'clusters':93,'interval':[-(i%101)/101,(i%107)/107],'state':'NOMINAL_EXPOSED_DEVELOPMENT'},'week':{'clusters':6,'interval':None,'state':'UNAVAILABLE_FEWER_THAN8CLUSTERS'}},'replicates':500,'seed':1703} for i in range(729)]
    doc={'version':'FICTIONAL_ONLY','records':records,'paired':contrasts,'full_population_unknowns_retained':True}
    compressed,encoding=worker.public_aggregate(doc);decoded=json.loads(gzip.decompress(compressed));assert decoded==doc
    assert len(compressed)<=worker.CAPS['safe_aggregate_bytes'] and len(records)==6216 and len(contrasts)==729
    assert worker.public_aggregate(doc)[0]==compressed and b'POSITIVE_INFINITY' in gzip.decompress(compressed)
    used=time.process_time()-cpu;elapsed=time.monotonic()-started;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    assert used<=12 and elapsed<=20 and rss<=134217728 and not attempts
    result={'state':'FICTIONAL_AGGREGATE_GZIP_AND_PREDECODE_GO_PASS','worker':ref,'plan_sha256':a.sha256,
        'fictional_records':6216,'fictional_contrasts':729,'representative_shape_not_universal_size_bound':True,
        'encoding':encoding,'missing_GO_fields_rejected_before_source_access':rejected,
        'all_weekly_records_and_infinite_loss_status_preserved':True,'NFL_decodes_model_loads_fits_CAS_network':0,
        'CPU_seconds':used,'wall_seconds':elapsed,'RSS_bytes':rss,'attempts':attempts}
    body=json.dumps(result,sort_keys=True,indent=2)+'\n';assert len(body.encode())<=8192
    with out.open('x') as f:f.write(body)
    print(json.dumps(result))


if __name__=='__main__':main()
