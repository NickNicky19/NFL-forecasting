"""Pure diagnostic fictionals; no source, models, credentials, clients or dispatch."""
import ast
from contextlib import redirect_stdout
import importlib.util
import inspect
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hosted_build_diagnostic_fictional',ROOT/'tools/genuine_hosted_fixed_build_v1.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
SECRET='FICTIONAL_TOKEN_PATH_ROW_NEVER_PRINT'


class SafeDiagnosticChecks(unittest.TestCase):
    def setUp(self):driver._diagnostic_phase='PRECHECK';driver._diagnostic_state='ENTER'

    def test_preparation_is_identical_and_does_no_execution_IO_or_native_mutation(self):
        with patch.object(driver,'read',side_effect=AssertionError('control/source IO')),\
                patch.object(driver,'verify_sources',side_effect=AssertionError('source verification')),\
                patch.object(driver,'preflight',side_effect=AssertionError('environment/credentials')),\
                patch.object(driver,'run_build',side_effect=AssertionError('pipeline execution')),\
                patch.object(driver.resource,'setrlimit',side_effect=AssertionError('native mutation')),\
                patch.object(driver.signal,'signal',side_effect=AssertionError('signal mutation')),\
                patch.object(driver.signal,'setitimer',side_effect=AssertionError('timer mutation')),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(driver.main([]),2)
        self.assertEqual(output.getvalue(),'{"state":"HOSTED_FIXED_BUILD_PREPARATION_ONLY_NO_IO"}\n')

    def test_checkpoint_phase_and_state_are_closed_constant_bounded_records(self):
        with redirect_stdout(io.StringIO()) as output:
            for phase in sorted(driver.DIAGNOSTIC_PHASES):
                for state in sorted(driver.DIAGNOSTIC_STATES):driver.diagnostic_checkpoint(phase,state)
        for line in output.getvalue().splitlines():
            row=json.loads(line);self.assertLess(len(line),256)
            self.assertEqual(set(row),{'state','phase','phase_state'});self.assertEqual(row['state'],'HOSTED_FIXED_BUILD_CHECKPOINT')
        with redirect_stdout(io.StringIO()) as output:
            for phase,state in [(SECRET,'ENTER'),('PRECHECK',SECRET),(object(),'ENTER')]:
                with self.assertRaises(ValueError):driver.diagnostic_checkpoint(phase,state)
        self.assertEqual(output.getvalue(),'')

    def test_unknown_errors_never_render_text_args_tracebacks_class_names_or_code(self):
        class Poison(Exception):
            code=SECRET
            def __str__(self):raise AssertionError('exception text rendered')
            def __repr__(self):raise AssertionError('exception repr rendered')
        private_type=type(SECRET,(Poison,),{})
        for error in (Poison(SECRET),private_type(SECRET),ValueError(SECRET),ImportError(SECRET),KeyError(SECRET)):
            output=json.dumps(driver.safe_failure(error),sort_keys=True)
            self.assertNotIn(SECRET,output);self.assertLess(len(output),1024)
            self.assertIsNone(json.loads(output)['fatal_code'])
        self.assertEqual(driver.safe_failure(private_type())['fatal_error_type'],'UNLISTED_ERROR_TYPE')

    def test_only_constant_actual_GuardStop_and_StoreError_codes_are_exposed(self):
        from nfl_lab.private_draft_store import StoreError
        for error,expected in [(driver.GuardStop('AUTHENTIC_ONE_TIME_SOURCE_CLAIM_REQUIRED'),'AUTHENTIC_ONE_TIME_SOURCE_CLAIM_REQUIRED'),
                               (driver.GuardStop(SECRET),'UNLISTED_GUARD_CODE'),
                               (StoreError('ACTIONS_API_JOB_IDENTITY'),'ACTIONS_API_JOB_IDENTITY'),(StoreError(SECRET),'UNLISTED_STORE_CODE')]:
            report=driver.safe_failure(error);self.assertEqual(report['fatal_code'],expected)
            self.assertNotIn(SECRET,json.dumps(report));self.assertIn(report['fatal_code_class'],{'GuardStop','StoreError'})
        class Spoof(ValueError):code='ACTIONS_API_JOB_IDENTITY'
        self.assertIsNone(driver.safe_failure(Spoof(SECRET))['fatal_code'])

    def execute_failure(self,run=None,preflight=None):
        with patch.object(driver.resource,'setrlimit'),patch.object(driver.signal,'signal'),patch.object(driver.signal,'setitimer'),\
                patch.object(driver,'verify_sources',return_value={}),patch.object(driver,'preflight',side_effect=preflight or (lambda *a,**k:{})),\
                patch.object(driver,'run_build',side_effect=run or (lambda *a,**k:(_ for _ in ()).throw(ImportError(SECRET)))),\
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(driver.main(['--execute']),1)
        return [json.loads(line) for line in output.getvalue().splitlines()]

    def test_main_keeps_precheck_pass_last_subphase_and_all_unattested_counts_unknown(self):
        def fail(*unused, **kwargs):
            driver.diagnostic_checkpoint('ACTIONS_AUTH');driver.diagnostic_checkpoint('ACTIONS_AUTH','PASSED')
            driver.diagnostic_checkpoint('SOURCE_CLAIM_VERIFY');raise driver.GuardStop('SOURCE_CLAIM_GENUINE_CURRENT_JOB')
        rows=self.execute_failure(run=fail)
        self.assertEqual(rows[0]['phase'],'PRECHECK');self.assertEqual(rows[1]['phase_state'],'PASSED')
        fatal=rows[-1];self.assertEqual(fatal['phase'],'SOURCE_CLAIM_VERIFY');self.assertEqual(fatal['phase_state'],'ENTER')
        self.assertEqual(fatal['fatal_code'],'SOURCE_CLAIM_GENUINE_CURRENT_JOB')
        for key in ['source_attempts','source_roundtrips','control_API_calls','new_fits_reserved','model_artifacts','scores','forecasts_issued']:
            self.assertIsNone(fatal[key])
        self.assertEqual(fatal['counters_attestation'],'UNKNOWN_NO_TRUSTED_TERMINAL')
        self.assertNotIn(SECRET,json.dumps(rows))
        rows=self.execute_failure(preflight=lambda *a,**k:(_ for _ in ()).throw(ValueError(SECRET)))
        self.assertEqual(len(rows),2);self.assertEqual(rows[-1]['phase'],'PRECHECK');self.assertEqual(rows[-1]['phase_state'],'ENTER')

    def test_static_checkpoints_precede_operations_without_executing_pipeline(self):
        body=ast.parse(inspect.getsource(driver.run_build)).body[0]
        checkpoints=sorted([(n.lineno,n.args[0].value,n.args[1].value if len(n.args)>1 else 'ENTER')
            for n in ast.walk(body) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='diagnostic_checkpoint'])
        self.assertEqual(len(checkpoints),22)
        before=next(line for line,phase,status in checkpoints if phase=='BEFORE_SOURCE')
        acquire=next(n.lineno for n in ast.walk(body) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='acquire_operational_history')
        self.assertLess(before,acquire)
        for method,phase in [('process_binding','SAMPLER'),('authenticate_actions_job','ACTIONS_AUTH')]:
            operation=next(n.lineno for n in ast.walk(body) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr==method)
            self.assertTrue(any(line<operation and p==phase and status=='ENTER' for line,p,status in checkpoints))
        claims=sorted(n.lineno for n in ast.walk(body) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='verify_source_claim')
        for operation in claims:
            self.assertIn((operation-1,'SOURCE_CLAIM_VERIFY','ENTER'),checkpoints)
            self.assertIn((operation+1,'SOURCE_CLAIM_VERIFY','PASSED'),checkpoints)
        for phase in ('FINISHED_METADATA_ENVIRONMENT','TERMINAL_WRITE','TERMINAL_READ'):
            self.assertEqual([status for line,p,status in checkpoints if p==phase],['ENTER','PASSED'])
        main=inspect.getsource(driver.main)
        self.assertIn('resource.setrlimit(resource.RLIMIT_CPU,(600,600))',main)
        self.assertIn('resource.setrlimit(resource.RLIMIT_AS,(4294967296,4294967296))',main)
        self.assertIn('signal.setitimer(signal.ITIMER_REAL,1200)',main)


if __name__=='__main__':unittest.main()
