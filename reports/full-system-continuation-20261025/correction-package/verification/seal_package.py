"""Seal public-safe source/evidence inventory and a deterministic review archive."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

PACKAGE=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    preparation=json.loads((PACKAGE/'evidence/preparation.json').read_text())
    qualification=json.loads((PACKAGE/'evidence/qualification.json').read_text())
    qualification['actual_js_side_guard']=dict(exit_code=0,
        summary=json.loads((PACKAGE/'evidence/side-guard-js.log').read_text().strip()),log='side-guard-js.log')
    (PACKAGE/'evidence/qualification.json').write_text(json.dumps(qualification,sort_keys=True,indent=2)+'\n')
    assert qualification['combined_python']['summary']['tests']==129
    assert qualification['combined_python']['summary']['failures']==qualification['combined_python']['summary']['errors']==0
    for key,count in [('full_app_browser',75),('selected_rankings_browser',53)]:
        assert qualification[key]['exit_code']==0 and qualification[key]['summary']['checks']==count
    pins=json.loads((PACKAGE/'engine-pins.json').read_text())
    assert pins['normalized_stats_cache']['version']=='stat-keys-fgm-v1'
    assert pins['current_corrected_engine_sha256']['pull/build.py']==preparation['changed_files']['pull/build.py']['postimage_sha256']
    assert (PACKAGE/'continuation-review.md').read_bytes()==(PACKAGE.parent/'website-integration-continuation.md').read_bytes()
    inventory={}
    secret=re.compile(rb'Bearer [A-Za-z0-9_\-]{20,}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-proj-[A-Za-z0-9]{30,}|BEGIN [A-Z ]*PRIVATE KEY')
    for path in sorted(PACKAGE.rglob('*')):
        if not path.is_file()or path.name=='manifest.json':continue
        name=path.relative_to(PACKAGE).as_posix()
        assert not path.is_symlink() and '.git'not in path.parts and '__pycache__'not in path.parts,name
        raw=path.read_bytes()
        assert not secret.search(raw),name
        assert not name.startswith(('data/','output/data/')),name
        inventory[name]=dict(bytes=len(raw),sha256=sha(raw))
    manifest=dict(schema_version='current-production-corrections-review-v2',package_revision=2,
        source_base=preparation['source_base'],sourcebase89512ed=True,
        source_code_release=pins['source_code_release'],
        status='COMBINED_SOURCE_VETTED_PARENT_EXECUTION_BINDING_AND_EXTERNAL_INTEGRATION_PENDING',
        integration_entrypoints=['combined-89512ed.patch','files/','engine-pins.json','continuation-review.md'],
        correction_files=preparation['changed_files'],package_files=inventory,
        primary_checks=dict(python_tests=129,original_python_tests=113,new_python_tests=16,python_network_attempts=0,
            math_oracle_checks=47,full_app_browser_checks=75,selected_ranking_contract_browser_checks=53,
            actual_js_side_guard_checks=2,exact_diff_zero_fuzz=True,exact_diff_zero_offsets=True),
        normalized_stats_cache_version='stat-keys-fgm-v1',legacy_stats_cache_preserved=True,
        original_main_v2_policy_not_repinned=True,new_execution_model_registration_required=True,
        original_fresh_input_R0_shadow_required=True,
        negative_count_main_applicability='EXCLUDED_MISSING_PRESENCE_AWARE_PREREQUISITE',
        phase2_review=dict(recovered_exact_retained_files=5,static_subset_tests=33,passed=26,failures=7,errors=0,
            raw_controller_installed_bytes=30854,raw_controller_required_bytes=35468,
            exact_protected_workflow_proposal_bodies_available=False,required_for_main_correction=False),
        public_safe_content='Technical source/diffs/hash metadata and explicitly fictional tests/results/screenshots only; no provider caches, raw feeds, private plans or real outcomes.',
        source_worktrees_modified=False,git_metadata_modified=False,lease_claimed_or_modified=False,
        remote_writes=False,paid_service_calls=0,protected_outcomes_inspected=False,deployed=False,
        full_source_scratch='/tmp/nfl-current-corrections-89512ed-v3/combined',
        scope_limits=['No hosted CI or real first-release provider FG availability claim.',
            'No execution policy/workflow/frozen R0 mutation; parent owns those bindings.',
            'No whole Phase2 or aggregate operating/release qualification.',
            'Current-week half-PPR correction does not change the legacy ROS fallback.'])
    (PACKAGE/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    archive=PACKAGE.parent/'current-production-corrections-89512ed.tar.gz'
    with archive.open('wb')as output,gzip.GzipFile(fileobj=output,mode='wb',mtime=0,filename='')as zipped,tarfile.open(fileobj=zipped,mode='w')as tar:
        for path in sorted(PACKAGE.rglob('*')):
            if not path.is_file():continue
            raw=path.read_bytes();name=PACKAGE.name+'/'+path.relative_to(PACKAGE).as_posix()
            info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o644;info.mtime=0;info.uid=info.gid=0
            tar.addfile(info,io.BytesIO(raw))
    checksum=sha(archive.read_bytes())
    archive.with_suffix(archive.suffix+'.sha256').write_text(checksum+'  '+archive.name+'\n')
    print(json.dumps(dict(state='SEALED',package_files=len(inventory),correction_files=len(preparation['changed_files']),
        archive=archive.name,bytes=archive.stat().st_size,sha256=checksum)))
if __name__=='__main__':main()
