"""Static and fictional-only checks: no NFL/native/model/label reads or execution."""
from __future__ import annotations
import argparse,ast,copy,gzip,hashlib,importlib.util,json,math
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c-code-cache",type=Path,required=True,help="Directory containing the exact pinned public C scorer source")
    args=parser.parse_args()
    s=load('next02_synthetic_scorer','tools/next02_freshness_score_v1.py')
    old=load('next02_synthetic_prior_scorer','tools/profile_increment_a_score_v2.py')
    helper=load('next02_synthetic_grading_helper','tools/player_context_completion_efficiency_score_v1.py')
    paths=['tools/profile_increment_a_score_v2.py','tools/next02_freshness_score_v1.py']
    trees=[ast.parse((ROOT/p).read_text())for p in paths]
    def fn(tree,n):return next(x for x in ast.walk(tree)if isinstance(x,ast.FunctionDef)and x.name==n)
    scientific=['enc','sha','check','local_module','read_ref','key','law_probabilities','probability_side','probability_scores','numerical_product','paired_probability','player_diagnostics','point_and_law']
    parity={n:ast.dump(fn(trees[0],n),include_attributes=False)==ast.dump(fn(trees[1],n),include_attributes=False)for n in scientific}
    assert all(parity.values())
    assert len(s.CANDIDATES)==26 and len(set(s.CANDIDATES))==26 and len(s.PAIRS)==99 and len({tuple(p)for p in s.PAIRS})==99 and len(s.COHORTS)==5
    for product in s.PRODUCTS:
        for a,b in [(1,0),(2,0),(3,2),(3,1)]:assert [s.ARMS[a]+'::'+product,s.ARMS[b]+'::'+product]in s.PAIRS
    # Compile ONLY the exact pinned pure C status function. No C build/load call.
    cp=args.c_code_cache/'abc_championship_v2.py';cb=cp.read_bytes()
    assert hashlib.sha256(cb).hexdigest()==helper.C_PINS[cp.name]
    st=ast.parse(cb);node=next(x for x in st.body if isinstance(x,ast.FunctionDef)and x.name=='status')
    ns={'Decimal':Decimal};exec(compile(ast.Module(body=[node],type_ignores=[]),str(cp),'exec'),ns);status=ns['status']
    law=dict(kind='leaf_cdf',support=[-1,0,1,2],weights=[.1,.3,.4,.2],prior=dict(support='signed_integer',center=0,q=.5),prior_weight=.1)
    pp=[s.law_probabilities(law,l)for l in [-1.5,-1,0,.5,1,1.5,2,10]]
    assert all(abs(sum(r[k]for k in ['p_under','p_push','p_over'])-1)<1e-12 for r in pp)
    assert all(a['p_over']>=b['p_over']for a,b in zip(pp,pp[1:]))
    assert all(a['p_under']<=b['p_under']for a,b in zip(pp,pp[1:]))
    assert pp[3]['p_push']==0 and pp[2]['p_push']>0
    assert s.probability_side(dict(p_over=.5,p_under=.5,p_push=0))=='ABSTAIN' and s.probability_side(None)is None
    # Four immutable parts are synthetic; aliases exist only in decoded memory.
    parts=[];bodies={};before={}
    for i,alias in enumerate(s.ARMS):
        arm=s.ORIGINAL_ARMS[i]if i<2 else alias
        rr=[dict(arm=arm,target='rush_yd',position='RB',season=2026,week=1,game_id='fictional-'+str(j),player_id='fictional-player',mean=0.,median=0,law=law)for j in range(1364)]
        body=gzip.compress(s.enc(rr),mtime=0);ref=dict(id='fictional-part-'+str(i),bytes=len(body),sha256=s.sha(body),namespace='PRIMARY'if i<2 else'FRESHNESS')
        bodies[ref['id']]=body;before[ref['id']]=body
        parts.append(dict(ref=ref,procedure_alias=alias,original_arm=arm,rows=1364))
    manifest=dict(format='IMMUTABLE_ALIAS_PART_MANIFEST_V1',version=s.FIT_VERSION,arm_order=s.ARMS,parts=parts,rows=5456,query_rows=1364)
    expected=[{k:p[k]for k in ['procedure_alias','original_arm','ref']}for p in parts[:2]]
    rows,commitments=s.alias_parts(manifest,bodies,expected)
    assert bodies==before and len(rows)==5456 and len(commitments)==4
    assert rows[0]['arm']==s.ARMS[0] and rows[0]['original_procedure_arm']==s.ORIGINAL_ARMS[0]
    for mutation in ['hash','arm','namespace','duplicate','rows','expected']:
        mm=copy.deepcopy(manifest);bb=dict(bodies);ee=copy.deepcopy(expected)
        if mutation=='hash':bb[parts[0]['ref']['id']]+=b'x'
        if mutation=='arm':mm['parts'][0]['original_arm']='WRONG'
        if mutation=='namespace':mm['parts'][2]['ref']['namespace']='PRIMARY'
        if mutation=='duplicate':mm['parts'][1]['ref']['id']=mm['parts'][0]['ref']['id']
        if mutation=='rows':mm['query_rows']=1363
        if mutation=='expected':ee[0]['ref']['sha256']='0'*64
        try:s.alias_parts(mm,bb,ee)
        except(ValueError,KeyError):pass
        else:raise AssertionError('alias mutation accepted: '+mutation)
    board={};broad={}
    for i,alias in enumerate(s.ARMS):
        for product in s.PRODUCTS:
            candidate=alias+'::'+product;br=[];nr=[]
            for week,actual,appearance,line,base,alt,basefb in [(1,0,'PLAYED',.5,1.,0.,None),(2,1,'PLAYED',1.,1.,2.,None),(3,None,'UNKNOWN',.5,1.,0.,None),(4,2,'PLAYED',.5,None,2.,'prior'),(5,1,'PLAYED',.5,0.,2.,'prior')]:
                point=base if i<2 else alt
                why='MISSING_FROZEN_FORECAST'if point is None else None
                fb=('UNAVAILABLE_FORECAST'if point is None else 'FALLBACK:prior'if basefb and i<2 else'LEARNED_EXPLICIT_NO_FALLBACK')
                probs=s.law_probabilities(law,line)if point is not None else None
                side=s.probability_side(probs)if product=='EXACT_LINE_P2'else helper.point_side(point,line)
                initial='UNAVAILABLE_FORECAST'if side is None else'ABSTAIN'if side=='ABSTAIN'else'UNKNOWN_PARTICIPATION'if appearance!='PLAYED'else'READY'
                r=dict(season=2026,week=week,game_id='fictional-game-'+str(week),player_id='fictional-player',opportunity_key='fictional-offer-'+str(week),point=None if product=='EXACT_LINE_P2'else point,actual=actual,appearance=appearance,line=line,comparator='STRICT_OVER_UNDER',selected_side=side,status=initial,source_panel='ANNUAL_NAMED_NJ',unavailability_reason=why,fallback_state=fb,p_under=probs['p_under']if probs else None,p_push=probs['p_push']if probs else None,p_over=probs['p_over']if probs else None)
                r['status']=status(r);br.append(r);nr.append({k:v for k,v in r.items()if k not in ['status','source_panel','line','selected_side','comparator','p_under','p_push','p_over']})
            board[candidate]=br;broad[candidate]=nr
    a=s.fallback_attribution(board,broad,helper)
    focus=[r for r in a['records']if r['panel']=='ANNUAL_W1_W5'and r['left']==s.ARMS[2]+'::MEAN_P1'and r['right']==s.ARMS[0]+'::MEAN_P1']
    by={r['group']:r for r in focus}
    assert by['FULL_SYSTEM']['cases']==5 and by['FULL_SYSTEM']['common_decided']==2
    assert by['LEARNED_TO_LEARNED']['common_numerical']==2 and by['LEARNED_TO_LEARNED']['common_decided']==1
    assert by['LEARNED_TO_LEARNED']['common_probability_events']==2 # integer push stays probability/numerical evidence
    assert by['UNAVAILABLE_TO_LEARNED']['cases']==1 and by['FALLBACK_TO_LEARNED']['cases']==1
    assert by['FULL_SYSTEM']['left_status_counts']['UNKNOWN_PARTICIPATION']==1
    bad=copy.deepcopy(board);bad[s.ARMS[0]+'::MEAN_P1'][0]['line']=9.
    try:s.fallback_attribution(bad,broad,helper)
    except ValueError:pass
    else:raise AssertionError('fallback changed line accepted')
    # Renaming preserves exact old baseline/control score cells. Current stable
    # core is a newly defined shared mask, so does not inherit old-core scores.
    current=[dict(period='W1_W7',cohort='ALL_ELIGIBLE',candidate_id=s.ARMS[0]+'::MEAN_P1',population='BROAD_QUERIES',numerical={'scored':1}),dict(period='W1_W7',cohort='STABLE_NEW_CORE',candidate_id=s.ARMS[0]+'::MEAN_P1',population='BROAD_QUERIES',numerical={'scored':0})]
    previous=dict(state='FROZEN_POINT_AND_EXACT_LINE_LAW_SCORING_COMPLETE',source_sha256={'fictional':'0'},summaries=[dict(current[0],candidate_id=s.ORIGINAL_ARMS[0]+'::MEAN_P1')],paired=[])
    par=s.baseline_parity(previous,current,[],{'fictional':'0'});assert par['state']=='PASS_EXACT_REUSED_BASELINE_AND_CONTROL_CELLS'and par['compared_summary_cells']==1
    changed=copy.deepcopy(current);changed[0]['numerical']['scored']=2;assert s.baseline_parity(previous,changed,[],{'fictional':'0'})['mismatch_count']==1
    outcome=dict(state='PASS_STATIC_AND_FICTIONAL_SCORER_CHECKS',NFL_rows_read=0,native_store_constructions=0,model_loads=0,fits=0,NFL_scoring_executions=0,scientific_function_AST_parity=parity,candidates=len(s.CANDIDATES),pairs=len(s.PAIRS),cohorts=len(s.COHORTS),alias_source_bytes_untouched=True,fallback_attribution='Push/abstain remain numerical/probability observations independently from direction; unavailable and prior-to-learned remain separate.',C_status_sha256=helper.C_PINS[cp.name],code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()for p in paths+['tools/next02_freshness_score_fixture_v1.py']})
    print(json.dumps(outcome,sort_keys=True))
if __name__=='__main__':main()
