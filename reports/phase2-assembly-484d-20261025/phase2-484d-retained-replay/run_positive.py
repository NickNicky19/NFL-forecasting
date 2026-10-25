"""Run only one existing CI positive case for the selected retained family."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import traceback

BASE=Path(__file__).parent
SOURCE=BASE/'source'
sys.path[:0]=[str(SOURCE/'tests'),str(SOURCE/'tools'),str(SOURCE/'pull')]
import test_phase2_e2e as cases

family=sys.argv[1]
if family=='e2d':
    cls=cases.RetainedRankedSourcePipelineTests
    method='test_closed_original_source_and_pinned_ledger_replay_and_cold_process'
else:
    assert family=='045'
    cls=cases.Retained045RankedSourcePipelineTests
    method='test_actual045_saved_observation_ledger_and_independent_cold_replay'
out=BASE/'evidence'/family
out.mkdir(exist_ok=True)
result=dict(family=family,test=cls.__name__+'.'+method,fixture_only=True,source=str(SOURCE))
case=None
try:
    cls.setUpClass()
    case=cls(method);case.setUp()
    getattr(case,method)()
    result['state']='PASS'
except Exception as error:
    result.update(state='FAIL',error_type=type(error).__name__,error=str(error))
    traceback.print_exc()
finally:
    for attr in ('base','root'):
        path=getattr(case,attr,None) if case is not None else getattr(cls,attr,None)
        if path is not None and Path(path).is_dir():
            target=out/('fictional-'+attr)
            if not target.exists():shutil.copytree(path,target)
    if hasattr(cls,'state'):result['fictional_fixture_state']=cls.state
    if case is not None:case.doCleanups()
    cls.doClassCleanups()
    (out/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='fictional_fixture_state'},sort_keys=True),flush=True)
raise SystemExit(0 if result['state']=='PASS' else 1)
