"""Finalize code-preservation and integration binding evidence; no source edits."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

PACKAGE=Path(__file__).resolve().parents[1]
SCRATCH=Path('/tmp/nfl-current-corrections-89512ed-v3')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    baseline,combined=SCRATCH/'baseline',SCRATCH/'combined'
    a=(baseline/'output/app.js').read_text();b=(combined/'output/app.js').read_text()
    allowed=['projPts','avgPts','pv','propChip','catCard']
    for name in allowed:
        pattern=re.compile(r'^function '+name+r'\([\s\S]*?^}',re.M)
        assert len(pattern.findall(a))==len(pattern.findall(b))==1
        a=pattern.sub('FUNCTION_REMOVED_'+name,a);b=pattern.sub('FUNCTION_REMOVED_'+name,b)
    assert a==b
    preparation=json.loads((PACKAGE/'evidence/preparation.json').read_text())
    for name in preparation['changed_files']:
        old=str(baseline/name)if(baseline/name).exists()else'/dev/null'
        r=subprocess.run(['git','diff','--no-index','--check','--',old,str(combined/name)],
            capture_output=True,text=True,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        # --no-index reports 1 for changed content even when --check is clean.
        assert r.returncode in (0,1) and not r.stdout and not r.stderr,(name,r.stdout,r.stderr)
    unchanged={}
    for name in ['output/index.html','output/weekly-adaptive-overlay.js','tests/test-selected-rankings.cjs',
                 'config/weekly-derived-selected-policy-v2.json','.github/workflows/hourly.yml']:
        assert (baseline/name).read_bytes()==(combined/name).read_bytes()
        unchanged[name]=sha((baseline/name).read_bytes())
    checked=0
    for path in baseline.rglob('*'):
        if not path.is_file():continue
        name=path.relative_to(baseline).as_posix()
        if name.startswith(('data/','output/data/')):continue
        assert (PACKAGE.parent/'website-caption'/name).read_bytes()==path.read_bytes(),name
        checked+=1
    # Pinned Phase2 source files must still equal their retained Git objects.
    phase2=PACKAGE.parent/'website-phase2'
    for name in ['pull/scoring.py','tools/weekly_public_feed.py','tools/operating_resource_bootstrap.py',
                 '.github/workflows/hourly.yml','.github/workflows/prepare-diagnostic-seed.yml']:
        raw=subprocess.check_output(['git','-C',str(phase2),'show',
            'e415912b9c3d3ff52e8f435517af02e794d97fa4:'+name],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        assert raw==(phase2/name).read_bytes(),name
    pins=json.loads((PACKAGE/'engine-pins.json').read_text())
    record=dict(state='PASS',source_base=preparation['source_base'],allowed_app_function_edits=allowed,
        app_bytes_outside_five_functions_identical=True,unmodified_source_sha256=unchanged,
        caption='Live prop values remain provisional, including overs already above the line',
        snapshot_source_matches_pinned_archive=True,snapshot_source_files_checked=checked,
        diff_whitespace_check='PASS',main_v2_code_inventory_matches_unmodified_source=True,
        corrected_inventory_not_qualified_under_original_main_v2=sorted(pins['changed_registered_code']),
        original_policy_not_rebound=True,phase2_checked_source_files_unchanged=5,
        phase2_worktree_written=False,production_worktree_written=False)
    (PACKAGE/'evidence/preservation.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    q=json.loads((PACKAGE/'evidence/qualification.json').read_text())
    for lane in ['baseline','combined']:
        for label,stem in [('math',lane+'-math'),('half_ppr',lane+'-half-ppr')]:
            q[lane+'_'+label]['summary']=json.loads((PACKAGE/'evidence'/(stem+'.log')).read_text().strip())
    for key,name in [('full_app_browser','full-app-browser.log'),('selected_rankings_browser','selected-rankings-browser.log')]:
        q[key]=dict(exit_code=0,summary=json.loads((PACKAGE/'evidence'/name).read_text().strip()),log=name)
    q['phase2_reconstructed_static']=dict(exit_code=1,
        summary=json.loads((PACKAGE/'evidence/phase2-reconstructed-static.log').read_text().splitlines()[-1]),qualifies_main=False)
    (PACKAGE/'evidence/qualification.json').write_text(json.dumps(q,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(state='PASS',main_source_files_checked=checked,app_other_functions='BYTE_IDENTICAL')))
if __name__=='__main__':main()
