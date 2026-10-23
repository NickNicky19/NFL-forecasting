"""New fictional process-state contracts only; no source audit or child runs."""
import ast
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
guard=load('fictional_zero_guard_v3','raw_orphan_zero_audit_execute_v3.py')

def fields(state='S',ticks=42):
    result=['0']*22;result[0]=state;result[11]='100';result[12]='20';result[19]=str(ticks)
    return result
def segment(source,name):
    return ast.get_source_segment(source,next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name==name))

class TransitionChecks(unittest.TestCase):
    def sample(self,before,after,status,allow=True):
        with patch.object(guard,'process_stat',side_effect=[before,after]),patch.object(guard.Path,'read_text',return_value=status):
            return guard.process_usage({'pid':777,'start_ticks':42},allow_exited_child=allow)
    def test_accepted_functions_byte_identical(self):
        actual=(ROOT/'tools/raw_orphan_zero_audit_execute_v3.py').read_text()
        accepted=(ROOT/'tools/review_direct_booster_screen_guard_v4.py').read_text()
        for name in ('require','process_usage','required_usage'):
            self.assertEqual(segment(actual,name),segment(accepted,name))
    def test_live_positive_RSS_is_required_and_counted(self):
        rss,cpu=self.sample(fields(),fields(),'Pid:\t777\nVmRSS:\t100 kB\n')
        self.assertEqual(rss,102400);self.assertEqual(cpu,120/os.sysconf('SC_CLK_TCK'))
    def test_known_zombie_is_authenticated_before_and_after(self):
        self.assertEqual(self.sample(fields('Z'),fields('Z'),'')[0],0)
        with self.assertRaises(ValueError):self.sample(fields('Z'),fields('Z',43),'')
    def test_known_dead_is_authenticated_before_and_after(self):
        self.assertEqual(self.sample(fields('X'),fields('X'),'')[0],0)
    def test_live_missing_RSS_fails_closed(self):
        with self.assertRaises(ValueError):self.sample(fields(),fields(),'Pid:\t777\n')
    def test_required_parent_zombie_has_no_terminal_exception(self):
        with self.assertRaises(ValueError):self.sample(fields('Z'),fields('Z'),'Pid:\t777\n',False)
    def test_terminal_transition_requires_status_identity(self):
        self.assertEqual(self.sample(fields(),fields('Z'),'Pid:\t777\n')[0],0)
        with self.assertRaises(ValueError):self.sample(fields(),fields('Z'),'Pid:\t778\n')
    def test_reused_live_PID_fails_closed(self):
        with self.assertRaises(ValueError):self.sample(fields(),fields(ticks=43),'Pid:\t777\nVmRSS:\t100 kB\n')
    def test_live_worker_disappearance_requires_exact_exit(self):
        child=Mock();child.poll.side_effect=[None,None]
        def use(binding,**kwargs):
            if binding['pid']==3:raise FileNotFoundError('fictional')
            return 10,1
        with patch.object(guard,'process_usage',side_effect=use),self.assertRaises(FileNotFoundError):
            guard.required_usage([{'pid':1},{'pid':2}],child,{'pid':3})
    def test_confirmed_original_child_exit_during_drain(self):
        child=Mock();child.poll.side_effect=[None,0]
        def use(binding,**kwargs):
            if binding['pid']==3:raise FileNotFoundError('fictional')
            return 10,1
        with patch.object(guard,'process_usage',side_effect=use),patch.object(guard.resource,'getrusage',return_value=SimpleNamespace(ru_utime=2,ru_stime=3)):
            self.assertEqual(guard.required_usage([{'pid':1},{'pid':2}],child,{'pid':3}),(20,7))
    def test_old_limits_numeric_core_and_fresh_supervisor(self):
        old=load('fictional_zero_guard_v2','raw_orphan_zero_audit_execute_v2.py')
        self.assertEqual(guard.LIMITS,old.LIMITS);self.assertEqual(guard.OUTPUT,old.OUTPUT)
        self.assertNotEqual(guard.SUPERVISOR,old.SUPERVISOR)
        self.assertEqual(guard.VERSION,'raw-orphan-explicit-zero-execution-v3')
        for name in ('preflight','storage_for','worker','bootstrap','supervisor'):
            a=(ROOT/'tools/raw_orphan_zero_audit_execute_v3.py').read_text();b=(ROOT/'tools/raw_orphan_zero_audit_execute_v2.py').read_text()
            self.assertEqual(segment(a,name),segment(b,name))
    def test_failure_diagnostics_are_code_metadata_only(self):
        source=segment((ROOT/'tools/raw_orphan_zero_audit_execute_v3.py').read_text(),'run_phase')
        for value in ('CHILD_LAUNCH','CHILD_IDENTITY','EXACT_PID_RESOURCE_SAMPLE','PIPE_DRAIN','EXACT_CHILD_WAIT','code_function','code_line'):
            self.assertIn(value,source)
        self.assertNotIn('str(exc)',source)
