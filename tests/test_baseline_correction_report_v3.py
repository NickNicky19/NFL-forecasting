"""Four NEW fictional V3 delta contracts; no old suites or NFL arrays."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from offline_report_imports_v1 import offline_dependency_imports
with offline_dependency_imports():
    from baseline_correction_run import extension
    extension({"path":str(ROOT/"nfl_lab/baseline_correction.py"),
        "sha256":"077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2"})
    spec=importlib.util.spec_from_file_location("fictional_v3_delta",ROOT/"tools/baseline_correction_report_v3.py")
    subject=importlib.util.module_from_spec(spec);spec.loader.exec_module(subject)


class V3DeltaContracts(unittest.TestCase):
    def test_nine_reused_two_remaining_and_byte_alias_route(self):
        categories={target:{"state":"BLOCKED" if target=="fantasy_ppr" else "READY"}
            for target in subject.shared.models.TARGETS}
        work=subject.report_partition(categories)
        self.assertEqual(sum(x=="REUSE_EXACT_BYTES" for x in work.values()),9)
        self.assertEqual(sum(x=="AGGREGATE_FROZEN_ROWS" for x in work.values()),2)
        self.assertEqual(work["fantasy_ppr"],"BLOCKED_EXACT_PPR")
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"fictional-report.json";path.write_text('{"target":"rec"}\n')
            files={kind:{"path":str(path),"sha256":"a"*64} for kind in ("report","pairs","subgroups")}
            session=SimpleNamespace(storage=SimpleNamespace(import_file=Mock()),output=Path(folder)/"new",
                authenticated_controls={str(path):{"sha256":"a"*64}},bindings={})
            self.assertEqual(subject.reuse_target(session,"rec",files),{"target":"rec"})
            self.assertEqual(session.storage.import_file.call_count,3)
            self.assertEqual(session.bindings["private/paired-losses/rec.parquet"],"a"*64)

    def test_exact_twelve_candidate_thirty_control_decode_paths(self):
        slots=[dict(target=target,scored=f"private/scored/{year}/{target}/{method}.parquet")
            for year in subject.shared.YEARS for target in subject.REUSE+subject.REMAINING
            for method in subject.prior.METHODS]
        scope={"parent_root":"/tmp/fictional-scientific-parent","control_root":"/tmp/fictional-controls"}
        paths=subject.decode_paths(scope,{"slots":slots})
        self.assertEqual(len(paths),42)
        self.assertTrue(all("/rush_rec_yd/" in p or "/anytime_td/" in p for p in paths))
        self.assertFalse(any("/rec_yd/" in p or "/queries/" in p for p in paths))
        with self.assertRaises(ValueError):subject.decode_paths(scope,{"slots":[]})

    def test_failed_predecessor_contract_cannot_be_relabeled_success(self):
        supervisor=dict(state="FAILED",returncode=1,new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0)
        failure=dict(state="FAILED",error_type="RuntimeError",reason="SEPARATE_REPORT_FAILURE_NO_RETRY",parent_failure_preserved=True)
        finished=dict(state="FAILED",new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0)
        subject.failed_contract(supervisor,failure,finished)
        supervisor["state"]="COMPLETED"
        with self.assertRaises(ValueError):subject.failed_contract(supervisor,failure,finished)

    def test_compact_reference_delegates_full_original_verification(self):
        binding=dict(path="/tmp/fictional-sealed-freeze.json",sha256="b"*64,bytes=999)
        env=dict(executable="fictional-python",python="fictional-version",packages={"fictional":"1"})
        inherited=dict(environment=dict(env,file_bindings=[{"fictional":"full original inventory"}]))
        freeze=dict(inherited_execution=binding,environment=env)
        policy=dict(inherited_execution=binding)
        verifier=Mock(return_value="FULL_VERIFICATION_CALLED")
        self.assertEqual(subject.compact_reference(freeze,policy,inherited,verifier),"FULL_VERIFICATION_CALLED")
        verifier.assert_called_once_with(inherited)
        self.assertNotIn("file_bindings",freeze["environment"])
        bad=dict(freeze,inherited_execution=dict(binding,sha256="c"*64))
        with self.assertRaises(ValueError):subject.compact_reference(bad,policy,inherited,verifier)


if __name__=="__main__":unittest.main()
