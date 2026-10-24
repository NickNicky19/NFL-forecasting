"""Exact public configuration metadata only; no source values or real transports."""
from contextlib import redirect_stderr,redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nfl_lab import cli,frozen_source_policy as frozen

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/"config/operational-source-policy-v2.json"


class FrozenPolicyChecks(unittest.TestCase):
    def test_exact_policy_canonical_newline_and_original_global_quota(self):
        policy=frozen.load_frozen_source_policy(POLICY)
        clean={k:v for k,v in policy.items() if not k.startswith("_")}
        body=(json.dumps(clean,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
        self.assertEqual(policy["_policy_sha256"],frozen.FROZEN_POLICY_SHA256)
        self.assertEqual(policy["_canonical_policy_sha256"],hashlib.sha256(body).hexdigest())
        self.assertEqual(policy["storage"]["limit_bytes"],512<<20)
        self.assertEqual(policy["namespaces"]["private_retention_bytes"],512<<20)

    def test_changed_bytes_and_oversize_reject_before_json_decode(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"policy.json"
            for body in (b"not JSON",POLICY.read_bytes()+b"\n",b"x"*(frozen.MAX_BYTES+1)):
                p.write_bytes(body)
                with patch.object(frozen.json,"loads",side_effect=AssertionError("JSON before exact hash")),self.assertRaises(ValueError):
                    frozen.load_frozen_source_policy(p)

    def test_Path_regular_file_and_every_ancestor_nonsymlink_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=root/"original";original.mkdir();p=original/"policy.json";p.write_bytes(POLICY.read_bytes())
            self.assertEqual(frozen.load_frozen_source_policy(p),frozen.load_frozen_source_policy(POLICY))
            alias=root/"alias.json";alias.symlink_to(p)
            parent=root/"parent";parent.symlink_to(original,target_is_directory=True)
            for candidate in (alias,parent/"policy.json",original):
                with self.subTest(candidate=candidate),self.assertRaises((OSError,ValueError)):frozen.load_frozen_source_policy(candidate)
            for candidate in ({},str(POLICY),p/".."/"policy.json"):
                with self.subTest(candidate=candidate),self.assertRaises(ValueError):frozen.load_frozen_source_policy(candidate)

    def test_cli_flag_rejects_nonpublication_or_missing_policy_before_input_read(self):
        for args in (["grade","--source-policy",str(POLICY),"--frozen-public-policy"],
                     ["acquire","--source-policy",str(POLICY),"--frozen-public-policy"],
                     ["publication","--frozen-public-policy"]):
            with patch("sys.argv",["fictional-cli",*args]),patch.object(Path,"read_text",side_effect=AssertionError("input read before unsupported flag rejection")),\
                    redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as caught:
                cli.main()
            self.assertEqual(caught.exception.code,2)

    def test_cli_publication_uses_pure_loader_for_entry_and_scope_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/"config").mkdir();(root/"config/research.json").write_text("{}")
            args=["publication","--root",str(root),"--cache",str(root/"same-cache"),"--state",str(root/"derived-state"),
                "--source-policy",str(POLICY),"--frozen-public-policy"]
            with patch("sys.argv",["fictional-cli",*args]),patch.object(cli,"_execute") as execute,\
                    patch.object(frozen,"load_frozen_source_policy",wraps=frozen.load_frozen_source_policy) as load:
                cli.main()
            self.assertEqual(load.call_count,1);self.assertEqual(execute.call_args.args[2],root/"same-cache")
            from nfl_lab import publication_scope
            args=SimpleNamespace(command="publication",publication_commit="a"*40,publication_scope_stdin=True,
                frozen_public_policy=True,output=None)
            with patch("sys.stdin",io.StringIO("{}")),patch.object(publication_scope,"record_scoped_publication",return_value={"verified":True}) as record,\
                    patch.object(frozen,"load_frozen_source_policy",wraps=frozen.load_frozen_source_policy) as load,redirect_stdout(io.StringIO()):
                cli._execute(args,root,root/"same-cache",root/"derived-state",POLICY,[],{})
            self.assertEqual(load.call_count,1);self.assertEqual(record.call_args.kwargs["policy_sha256"],frozen.FROZEN_POLICY_SHA256)


class NormalizedParityChecks(unittest.TestCase):
    def test_unchanged_full_loader_and_exact_reader_return_identical_normalization(self):
        from nfl_lab.operational_sources import load_source_policy
        self.assertEqual(frozen.load_frozen_source_policy(POLICY),load_source_policy(POLICY))


if __name__=="__main__":unittest.main()
