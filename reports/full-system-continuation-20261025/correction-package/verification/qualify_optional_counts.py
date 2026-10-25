"""The negative-count fix applies only to the exact presence-aware predecessor."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
PACKAGE=Path(__file__).resolve().parents[1]
AUDIT=PACKAGE.parent
SOURCE=AUDIT/'website-phase2/pull/scoring.py'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def main():
    main_source=AUDIT/'website-caption/pull/scoring.py'
    ordinary=load('original_main_scoring',main_source)
    assert not hasattr(ordinary,'component') and not hasattr(ordinary,'PRESENCE_VERSION')
    raw=SOURCE.read_bytes();source=raw.decode()
    original=load('original_phase2_scoring',SOURCE)
    assert original.PRESENCE_VERSION=='nfl-data-presence-v2'
    old='''        if not projection and ((key in ACTUAL_COUNTS and value < 0)
                               or key in ACTUAL_COUNTS | {"pass_yd", "rush_yd", "rec_yd"} and int(value) != value):'''
    new='''        if ((key in ACTUAL_COUNTS and value < 0)
                or not projection and key in ACTUAL_COUNTS | {"pass_yd", "rush_yd", "rec_yd"} and int(value) != value):'''
    assert source.count(old)==1
    corrected=source.replace(old,new)
    path=PACKAGE/'phase2/optional-negative-count/files/pull/scoring.py'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(corrected)
    fixed=load('corrected_phase2_counts',path)
    checks=0
    def check(condition):
        nonlocal checks
        assert condition
        checks+=1
    for key in ['rec','pass_att','pass_cmp','pass_td','pass_int','rush_att']:
        check(original.component({key:-1},key,projection=True)['value']==-1)
        check(fixed.component({key:-1},key,projection=True)==dict(value=None,state='invalid_value'))
        check(fixed.component({key:.25},key,projection=True)['value']==.25)
        check(fixed.component({key:0},key,projection=True)==dict(value=0,state='reported_zero'))
        check(fixed.component({key:None},key,projection=True)['value'] is None)
        check(fixed.component({},key,projection=True)['value'] is None)
        check(fixed.component({key:.25},key)['value'] is None)
    for key in ['pass_yd','rush_yd','rec_yd']:
        check(fixed.component({key:-5.25},key,projection=True)['value']==-5.25)
        check(fixed.component({key:-5},key)['value']==-5)
    check(fixed.ppr_points({'gp':1,'rec':0,'rush_yd':-20})==-2)
    for value in [True,'1',float('nan'),float('inf')]:
        check(fixed.component({'rec':value},'rec',projection=True)['value'] is None)
    patch=''.join(difflib.unified_diff(source.splitlines(keepends=True),corrected.splitlines(keepends=True),
        fromfile='a/pull/scoring.py',tofile='b/pull/scoring.py'))
    (PACKAGE/'phase2/optional-negative-count/presence-only.patch').write_text(patch)
    result=dict(state='PASS',checks=checks,main_applicability='REFUSED_MISSING_PRESENCE_PREREQUISITE',
        required_presence_version=original.PRESENCE_VERSION,required_preimage_sha256=sha(raw),
        postimage_sha256=sha(corrected.encode()),source_base='e415912b9c3d3ff52e8f435517af02e794d97fa4',
        production_main_modified=False,engine_registration_still_required=True,
        scope='Component-derived projection/PPR domain only; raw gamemodel rollup and TD helper are not a universal invalid-count contract')
    (PACKAGE/'phase2/optional-negative-count/qualification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result))
if __name__=='__main__':main()
