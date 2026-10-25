"""Emit exact tested code bindings for the parent's separate version transition."""
from pathlib import Path
import hashlib
import json

PACKAGE=Path(__file__).resolve().parents[1]
SCRATCH=Path('/tmp/nfl-current-corrections-89512ed-v3')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def main():
    old,new=SCRATCH/'baseline',SCRATCH/'combined'
    raw=(old/'config/weekly-derived-selected-policy-v2.json').read_bytes();policy=json.loads(raw)
    before={name:sha((old/name).read_bytes())for name in policy['website_code_sha256']}
    after={name:sha((new/name).read_bytes())for name in policy['website_code_sha256']}
    assert before==policy['website_code_sha256']
    assert all(policy['engine_sha256'][name]==before[name]for name in policy['engine_sha256'])
    engines={name:after[name]for name in policy['engine_sha256']}
    grader=sha((new/'pull/grade.py').read_bytes())
    record=dict(source_base='89512ed952308dacc1f6a930915ddbcdccd460d9',
        source_code_release='a2047854bece90ba354f7e379846cafc499fa7d6',
        historical_main_v2_policy_physical_sha256=sha(raw),original_r0_identities=policy['r0_identities'],
        historical_engine_sha256=policy['engine_sha256'],current_corrected_engine_sha256=engines,
        current_classic_grader_sha256=grader,
        current_execution_required_engine_and_grader_sha256=dict(engines,**{'pull/grade.py':grader}),
        current_website_code_sha256=after,current_website_code_inventory_sha256=sha(canonical(after)),
        changed_registered_code={name:dict(before=before[name],after=after[name])for name in before if before[name]!=after[name]},
        grading_version='statistical-v3-identity-20261025',
        corrected_model_version='UNREGISTERED_REQUIRES_NEW_DISTINCT_CLASSIC_EXECUTION_MODEL',
        cannot_use_existing_phase2_model='sleeper-matchup-data-integrity-v2',
        registration_status='PARENT_OWNS_ANALOGOUS_V3_TRANSITION; NO_POLICY_OR_WORKFLOW_EDIT_INCLUDED',
        original_fresh_input_R0_shadow='Retain original engine execution on the same newly captured raw inputs under its original identity; corrected normalization is a distinct execution.',
        historical_policy_and_freeze='Preserve exact bytes and fixed R0 engine map. Repinning both engine_sha256 and website_code_sha256 under the old R0 identity is invalid.',
        lab_publication_authority_and_scientific_registrations='UNCHANGED',
        normalized_stats_cache=dict(version='stat-keys-fgm-v1',
            corrected_path_template='data/cache/stat-keys-fgm-v1/stats_{season}_{week:02d}.json',
            original_R0_path_template='data/cache/stats_{season}_{week:02d}.json',
            original_cache_read_or_overwritten_by_corrected_builder=False,
            first_corrected_read='Refetch if the versioned cache is absent, including refresh=False; no legacy fallback.',
            absent_upstream_total='Not reconstructed. The path only changes which normalization contract is trusted.',
            first_release_real_provider_FG_availability='NOT_OBSERVED; fictional source-function traces only',
            private_capture_and_recovery_path_allowances='Parent must bind the new cache lane in any applicable evidence/capture/recovery contracts; no such protected edit is included.'),
        advisory_diagnostics='Legacy tools/verify.py and tools/compare_lines.py still read original cache paths; their historical diagnostic scope was not rewritten.')
    (PACKAGE/'engine-pins.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    q=json.loads((PACKAGE/'evidence/qualification.json').read_text())
    trace=q['combined_python']['summary']['fgm_cache_trace']
    (PACKAGE/'evidence/fgm-cache-trace.json').write_text(json.dumps(dict(
        source_base=record['source_base'],cache_version='stat-keys-fgm-v1',
        evidence='ACTUAL_SOURCE_FUNCTIONS_FICTIONAL_INPUTS_NETWORK_DENIED',traces=trace),indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(corrected_build_sha256=engines['pull/build.py'],grading_version=record['grading_version'],cache_version='stat-keys-fgm-v1')))
if __name__=='__main__':main()
