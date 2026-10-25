"""Two NEW offline-import contracts; never rerun the old ten test bodies."""
import importlib.util
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from offline_report_imports_v1 import offline_dependency_imports


class OfflineImportChecks(unittest.TestCase):
    def test_restore_and_skip_optional_probe_mock(self):
        previous=socket.has_ipv6
        probe=Mock(side_effect=AssertionError("mock probe should be skipped"))
        with patch.object(socket,"socket",probe):
            with offline_dependency_imports():
                self.assertFalse(socket.has_ipv6)
                if socket.has_ipv6:socket.socket()
            self.assertIs(socket.has_ipv6,previous)
            with self.assertRaisesRegex(RuntimeError,"fictional import exception"):
                with offline_dependency_imports():
                    raise RuntimeError("fictional import exception")
            self.assertIs(socket.has_ipv6,previous)
        probe.assert_not_called()

    def test_original_dependency_import_and_empty_guard_only(self):
        previous=socket.has_ipv6
        with offline_dependency_imports():
            path=ROOT/"tests/test_baseline_correction_report_v2.py"
            spec=importlib.util.spec_from_file_location("original_contract_definitions_not_executed",path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with module.subject.report_only():pass
        self.assertIs(socket.has_ipv6,previous)
        self.assertEqual(module.subject.REUSE,("pass_yd","pass_td","pass_cmp","pass_att"))


if __name__=="__main__":unittest.main()
