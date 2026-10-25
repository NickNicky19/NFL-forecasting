"""Closed Phase 2/V4 binding checks; fictional values and local source only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import phase2_capture
import weekly_public_feed as feed
import weekly_public_feed_v4 as current


class Phase2V4BindingTests(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_actual_phase2_policy_reader_uses_closed_current_execution_and_all_pipeline_files(self):
        config = json.loads((ROOT / 'config/phase2.json').read_bytes())
        policy = phase2_capture._weekly_policy(ROOT, config)
        self.assertEqual(policy['schema_version'], 'weekly-derived-selected-policy-v4')
        self.assertEqual(policy['current_execution']['model'], 'sleeper-matchup-classic-data-integrity-v2')
        self.assertEqual(policy['current_execution'], feed.current_execution_contract(ROOT))
        self.assertEqual(len(policy['website_code_sha256']), 32)
        for name in ('tools/phase2_capture.py', 'tools/source_ci.py', 'tools/build_recorded.py',
                     'tools/weekly_public_feed.py', 'tools/weekly_public_feed_v4.py'):
            self.assertEqual(policy['website_code_sha256'][name], hashlib.sha256((ROOT / name).read_bytes()).hexdigest())

    def test_active_phase2_binding_rejects_wrong_physical_policy_and_unknown_schema(self):
        config = json.loads((ROOT / 'config/phase2.json').read_bytes())
        wrong = deepcopy(config); wrong['weekly_publication']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'policy bytes differ'):
            phase2_capture._weekly_policy(ROOT, wrong)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'config/weekly-derived-selected-policy-v99.json'
            path.parent.mkdir(); raw = feed.canonical(dict(schema_version='weekly-derived-selected-policy-v99'))
            path.write_bytes(raw)
            setting = dict(weekly_publication=dict(path=path.relative_to(root).as_posix(), sha256=feed.sha(raw)))
            with self.assertRaisesRegex(ValueError, 'V3_POLICY_CONTRACT'):
                phase2_capture._weekly_policy(root, setting)

    def test_full_pipeline_corruption_rejects_even_when_engine_and_file_size_are_unchanged(self):
        p = json.loads((ROOT / 'config/weekly-derived-selected-policy-v4.json').read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in p['website_code_sha256']:
                target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            subprocess.run(['git', 'init', '-q', str(root)], check=True, capture_output=True)
            for oid, item in feed.registration_objects(ROOT).items():
                actual = subprocess.check_output(['git', '-C', str(root), 'hash-object', '-w', '-t', item['type'], '--stdin'], input=item['body']).decode().strip()
                self.assertEqual(actual, oid)
            current.policy_check(p, root=root)
            target = root / 'tools/phase2_capture.py'; before = target.read_bytes()
            target.write_bytes(b'!' + before[1:])
            self.assertEqual(target.stat().st_size, len(before))
            with self.assertRaisesRegex(ValueError, 'V4_CURRENT_EXECUTION_OR_INVENTORY'):
                current.policy_check(p, root=root)


if __name__ == '__main__':
    unittest.main()
