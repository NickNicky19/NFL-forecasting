"""Actual C request-name predicate over canonical metadata; no runtime imports."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools import hosted_initial_plan_builder_v1 as builder

ROOT=Path(__file__).resolve().parents[1]


class RequestDigestChecks(unittest.TestCase):
    def setUp(self):
        self.source_body=(ROOT/'nfl_lab/operational_sources.py').read_bytes()
        self.request=dict(asof_utc='2026-10-24T21:00:00+00:00',seasons=[2019,2026],
            allowed_periods={'2019':[1,2],'2026':[1,2,3,4,5]},code_sha256s={'fictional_source.py':'a'*64},
            metadata_label='fictional unicode \u00e9; no NFL rows')
        tree=ast.parse((ROOT/'tools/hosted_initial_plan_builder_v1.py').read_bytes())
        self.request_name_predicate=next(node for node in ast.walk(tree) if isinstance(node,ast.Compare)
            and isinstance(node.left,ast.Attribute) and node.left.attr=='name'
            and isinstance(node.left.value,ast.Call) and isinstance(node.left.value.func,ast.Name)
            and node.left.value.func.id=='Path' and 'request_binding' in ast.unparse(node.left))

    def predicate(self,name):
        namespace=dict(Path=Path,ROOT=ROOT,prepared={'request_binding':{'path':'/fictional/requests/'+name}},
            manifest={'request':self.request},source_request_digest=builder.source_request_digest,
            core=SimpleNamespace(read_local=lambda path,cap:self.source_body))
        return eval(compile(ast.Expression(self.request_name_predicate),'actual_C_request_filename_predicate','eval'),namespace)

    def test_actual_C_gate_accepts_adapter_newline_digest_and_rejects_old_no_newline_digest(self):
        canonical=json.dumps(self.request,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        original_name=hashlib.sha256(canonical+b'\n').hexdigest()+'.json'
        old_wrong_name=hashlib.sha256(canonical).hexdigest()+'.json'
        self.assertNotEqual(original_name,old_wrong_name)
        self.assertTrue(self.predicate(original_name));self.assertFalse(self.predicate(old_wrong_name))
        self.assertFalse(self.predicate('0'*64+'.json'))

    def test_source_serializer_preserves_original_ascii_and_trailing_newline_rules(self):
        expected=hashlib.sha256((json.dumps(self.request,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()).hexdigest()
        self.assertEqual(builder.source_request_digest(self.request,self.source_body),expected)
        different=hashlib.sha256((json.dumps(self.request,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()).hexdigest()
        self.assertNotEqual(expected,different)

    def test_next_registration_uses_distinct_fixed_id_path_and_unchanged_horizon(self):
        from nfl_lab import weekly_initial_continuation_v3 as cont,initial_horizon
        self.assertEqual(cont.REGISTRATION_ID,'2026-REG-W07-continuation-run40129209279-chain-gates-v6')
        self.assertEqual(cont.REGISTRATION_PATH,'config/weekly-initial-continuation-v6-registration.json')
        self.assertEqual(initial_horizon.CONTINUATION.registration_path,cont.REGISTRATION_PATH)
        self.assertEqual(cont.CUTOFF,'2026-10-25T00:00:00Z')
        self.assertTrue((ROOT/'config/weekly-initial-continuation-v3-registration.json').is_file())


if __name__=='__main__':unittest.main()
