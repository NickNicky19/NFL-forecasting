"""New fictional metadata-only guard checks; no previous suite is rerun."""
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

source=Path(__file__).resolve().parents[1]/"tools/hosted_safety_guard.py"
spec=importlib.util.spec_from_file_location("hosted_safety_guard",source)
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


class HostedSafetyChecks(unittest.TestCase):
    def document(self,root,**changes):
        values=dict(repository=guard.REPOSITORY,source_commit="a"*40,run_id="123",run_attempt="1",
            observed_at=datetime(2000,1,1,tzinfo=timezone.utc));values.update(changes)
        return guard.readiness(root,**values)

    def test_missing_source_and_publication_are_explicitly_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            result=self.document(root)
            self.assertIn("PERMITTED_SOURCE_POLICY_FILE_ABSENT",result["reasons"])
            self.assertIn("EXACT_PUBLICATION_REVIEW_ABSENT",result["reasons"])
            self.assertEqual(result["exit_code"],78);self.assertFalse(result["capture_started"])

    def test_file_existence_never_authorizes_activation_or_publication(self):
        with tempfile.TemporaryDirectory() as root:
            config=Path(root)/"config";config.mkdir()
            for name in ["operational-source-policy-v2.json","operational-publication-review-v2.json"]:
                (config/name).write_text('{"fake":"must never be read or trusted"}')
            result=self.document(root)
            self.assertEqual(result["state"],"BLOCKED_PENDING_QUALIFIED_HANDOVER")
            self.assertFalse(result["state_publication_started"])
            self.assertIn("PRIVATE_DURABILITY_NOT_VERIFIED",result["reasons"])

    def test_metadata_does_not_echo_untrusted_or_secret_like_values(self):
        with tempfile.TemporaryDirectory() as root:
            result=self.document(root,repository="untrusted/other",source_commit="secret-like-value",run_id="bad",run_attempt="bad")
            self.assertEqual(result["repository"],"UNEXPECTED_REPOSITORY")
            self.assertIsNone(result["source_commit"]);self.assertIsNone(result["run_id"])
            self.assertNotIn("secret-like-value",json.dumps(result))

    def test_exact_receipt_is_bounded_and_retries_never_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"receipt.json";document=self.document(root)
            guard.save_receipt(path,document)
            self.assertEqual(json.loads(path.read_text()),document)
            self.assertLess(path.stat().st_size,guard.MAX_RECEIPT_BYTES)
            with self.assertRaises(FileExistsError):guard.save_receipt(path,document)

    def test_receipt_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"real";target.mkdir();link=Path(root)/"link";link.symlink_to(target,target_is_directory=True)
            with self.assertRaises(ValueError):guard.save_receipt(link/"receipt.json",self.document(root))

    def test_cli_emits_blocked_receipt_without_operational_imports(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"readiness.json"
            with patch("sys.argv",["guard","--root",root,"--receipt",str(path)]), \
                    patch.dict("os.environ",{"GITHUB_REPOSITORY":guard.REPOSITORY,
                        "GITHUB_SHA":"a"*40,"GITHUB_RUN_ID":"123","GITHUB_RUN_ATTEMPT":"1"},clear=True), \
                    patch("builtins.print"):
                self.assertEqual(guard.main(),78)
            result=json.loads(path.read_text())
            self.assertEqual(result["source_commit"],"a"*40)
            self.assertEqual(result["scientific_confirmation"],"NO_NEW_EVIDENCE")
            self.assertFalse(result["acquisition_started"])

    def test_oversize_metadata_is_not_written(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"receipt.json"
            with self.assertRaises(ValueError):guard.save_receipt(path,{"bad":"x"*(guard.MAX_RECEIPT_BYTES+1)})
            self.assertFalse(path.exists())

    def test_workflow_keeps_one_cron_writer_and_preflight_before_actions(self):
        workflow=(source.parents[1]/".github/workflows/lab.yml").read_text()
        self.assertEqual(workflow.count("- cron:"),1)
        self.assertEqual(workflow.count("group: nfl-lab-single-writer"),1)
        self.assertIn("- cron: '36 12,13,14 * * *'",workflow)
        self.assertIn("cancel-in-progress: false",workflow)
        self.assertLess(workflow.index("id: readiness"),workflow.index("Install exact tested dependencies"))
        self.assertLess(workflow.index("id: readiness"),workflow.index("actions/setup-python@v5"))
        self.assertIn("if: always() && steps.readiness.outcome == 'success'",workflow)
        self.assertIn("path: ${{ runner.temp }}/nfl-lab-readiness.json",workflow)


if __name__=="__main__":unittest.main()
